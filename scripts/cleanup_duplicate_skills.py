"""一次性清理 skills/ 下的重复 skill 文件。

用法:
    python scripts/cleanup_duplicate_skills.py --dry-run   # 预览模式
    python scripts/cleanup_duplicate_skills.py              # 实际执行
"""
import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.vector_store import vector_store
from src.core.llm import llm
from src.db.models import get_connection


def read_skills(skills_dir: str) -> list[dict]:
    """读取所有 skill 文件。"""
    skills = []
    for fname in os.listdir(skills_dir):
        if not fname.endswith(".md"):
            continue
        filepath = os.path.join(skills_dir, fname)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        name = fname.replace(".md", "")
        trigger, rules = _parse_skill_md(content)
        skills.append({
            "name": name,
            "filepath": filepath,
            "trigger": trigger,
            "rules": rules,
            "content": content,
        })
    return skills


def _parse_skill_md(content: str) -> tuple:
    """从 markdown 中提取触发条件和行为规则。"""
    trigger = ""
    rules = ""
    in_trigger = False
    in_rules = False
    for line in content.split("\n"):
        if line.startswith("## 触发条件"):
            in_trigger = True
            in_rules = False
            continue
        if line.startswith("## 行为规则"):
            in_trigger = False
            in_rules = True
            continue
        if line.startswith("## 元数据"):
            break
        if in_trigger:
            trigger += line + "\n"
        if in_rules:
            rules += line + "\n"
    return trigger.strip(), rules.strip()


def cluster_skills(skills: list[dict], threshold: float = 0.15) -> list[list[dict]]:
    """将相似的 skill 聚类。"""
    temp_col = "temp_skill_dedup"
    try:
        vector_store.client.delete_collection(name=temp_col)
    except Exception:
        pass
    vector_store.client.create_collection(name=temp_col)

    for s in skills:
        text = f"触发条件: {s['trigger']}\n行为规则: {s['rules']}"
        vector_store.add(temp_col, f"temp-{s['name']}", text)

    n = len(skills)
    visited = [False] * n
    clusters = []

    for i in range(n):
        if visited[i]:
            continue
        text = f"触发条件: {skills[i]['trigger']}\n行为规则: {skills[i]['rules']}"
        results = vector_store.search(temp_col, text, n_results=n)
        cluster = []
        for r in results:
            if r.get("distance", 1.0) < threshold:
                skill_name = r["id"].replace("temp-", "")
                for idx, s in enumerate(skills):
                    if s["name"] == skill_name and not visited[idx]:
                        visited[idx] = True
                        cluster.append(s)
                        break
        if cluster:
            clusters.append(cluster)

    try:
        vector_store.client.delete_collection(name=temp_col)
    except Exception:
        pass

    return clusters


def merge_cluster(cluster: list[dict]) -> dict:
    """将一簇相似的 skill 通过 LLM 合并为一个。"""
    if len(cluster) == 1:
        return {
            "name": cluster[0]["name"],
            "trigger": cluster[0]["trigger"],
            "rules": cluster[0]["rules"],
        }

    existing_text = "\n\n---\n\n".join(
        f"## {s['name']}\n触发条件: {s['trigger']}\n行为规则: {s['rules']}"
        for s in cluster
    )

    prompt = f"""你是 Skill 去重模块。以下 {len(cluster)} 个 Skill 内容高度相似，请合并为一个。

{existing_text}

请输出去重合并后的结果，JSON 格式：

```json
{{
    "name": "英文名称（如 event-empty-result-detect）",
    "trigger_condition": "合并后的触发条件",
    "behavior_rules": "合并后的行为规则（Markdown，保留所有有效信息，去重）"
}}
```"""

    response = llm.chat([{"role": "user", "content": prompt}])
    try:
        data = json.loads(
            response["content"]
            .split("```json")[-1].split("```")[0]
            if "```" in response["content"]
            else response["content"]
        )
        return {
            "name": data.get("name", cluster[0]["name"]),
            "trigger": data.get("trigger_condition", ""),
            "rules": data.get("behavior_rules", ""),
        }
    except (json.JSONDecodeError, KeyError):
        return {
            "name": cluster[0]["name"],
            "trigger": cluster[0]["trigger"],
            "rules": cluster[0]["rules"],
        }


def write_skill(name: str, trigger: str, rules: str, version: int = 1) -> str:
    """写入 skill 文件，返回文件路径。"""
    content = f"""# Skill: {name}

## 触发条件
{trigger}

## 行为规则
{rules}

## 元数据
- 版本: {version}
- 创建时间: {datetime.now().isoformat()}
- 来源: 去重合并
"""
    filepath = f"skills/{name}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


def update_db_skills(clusters: list[list[dict]], merged_results: list[dict]) -> None:
    """更新数据库 skills 表。"""
    conn = get_connection()
    for cluster, merged in zip(clusters, merged_results):
        for s in cluster:
            conn.execute("DELETE FROM skills WHERE name = ?", (s["name"],))
        version = 1
        for s in cluster:
            for sep in ("版本:", "版本："):
                if sep in s["content"]:
                    try:
                        v = int(s["content"].split(sep)[1].split()[0])
                        version = max(version, v + 1)
                    except (IndexError, ValueError):
                        pass
        conn.execute(
            """INSERT INTO skills (name, trigger_condition, behavior_rules, version, file_path)
               VALUES (?, ?, ?, ?, ?)""",
            (merged["name"], merged["trigger"], merged["rules"],
             version, f"skills/{merged['name']}.md"),
        )
    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="清理重复 skill 文件")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际修改文件")
    args = parser.parse_args()

    skills_dir = "skills"
    if not os.path.isdir(skills_dir):
        print(f"目录不存在: {skills_dir}")
        sys.exit(1)

    skills = read_skills(skills_dir)
    print(f"读取到 {len(skills)} 个 skill 文件")

    clusters = cluster_skills(skills)
    multi_clusters = [c for c in clusters if len(c) > 1]
    single_clusters = [c for c in clusters if len(c) == 1]
    print(f"发现 {len(multi_clusters)} 组重复（共 {sum(len(c) for c in multi_clusters)} 个文件），"
          f"{len(single_clusters)} 个独立 skill")

    if not multi_clusters:
        print("没有发现重复 skill，无需清理。")
        return

    print("\n--- 重复组详情 ---")
    merged_results = []
    for i, cluster in enumerate(multi_clusters):
        names = [s["name"] for s in cluster]
        print(f"\n组 {i + 1}: {', '.join(names)}")
        merged = merge_cluster(cluster)
        merged_results.append(merged)
        print(f"  → 合并为: {merged['name']}")

    for cluster in single_clusters:
        s = cluster[0]
        merged_results.append({
            "name": s["name"],
            "trigger": s["trigger"],
            "rules": s["rules"],
        })

    if args.dry_run:
        print("\n[Dry-Run] 未做任何修改。去掉 --dry-run 执行实际清理。")
        print("\n将删除的文件:")
        for cluster in multi_clusters:
            merged_name = None
            for mc, mr in zip(multi_clusters, merged_results):
                if any(s["name"] in [c2["name"] for c2 in mc] for s in cluster):
                    merged_name = mr["name"]
                    break
            for s in cluster:
                if s["name"] != merged_name:
                    print(f"  - {s['filepath']}")
        return

    print("\n--- 执行合并 ---")
    os.system("git add skills/ && git commit -m 'backup: 去重前备份 skill 文件' 2>/dev/null || true")

    # 只处理多文件簇（单文件簇无需改动）
    for i, (cluster, merged) in enumerate(zip(multi_clusters, merged_results[:len(multi_clusters)])):
        # 计算合并后的版本号
        version = 1
        for s in cluster:
            for sep in ("版本:", "版本："):
                if sep in s["content"]:
                    try:
                        v = int(s["content"].split(sep)[1].split()[0])
                        version = max(version, v + 1)
                    except (IndexError, ValueError):
                        pass
        filepath = write_skill(merged["name"], merged["trigger"], merged["rules"], version)
        print(f"  写入: {filepath}")
        for s in cluster:
            if s["name"] != merged["name"] and os.path.exists(s["filepath"]):
                os.remove(s["filepath"])
                print(f"  删除: {s['filepath']}")

    for merged in merged_results:
        text = f"触发条件: {merged['trigger']}\n行为规则: {merged['rules']}"
        try:
            vector_store.upsert("skill_embeddings", f"skill-{merged['name']}", text)
        except Exception:
            vector_store.add("skill_embeddings", f"skill-{merged['name']}", text)

    update_db_skills(multi_clusters, merged_results[:len(multi_clusters)])

    print(f"\n清理完成。原有 {len(skills)} 个 skill → 合并为 {len(merged_results)} 个。")
    print("请检查 skills/ 目录确认结果，可通过 git 回滚。")
    print("\n建议运行: git add skills/ && git commit -m 'cleanup: 合并重复 skill 文件'")


if __name__ == "__main__":
    main()

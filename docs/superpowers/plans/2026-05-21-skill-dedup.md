# Skill 去重系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 三层去重防止自动生成相似 skill —— 经验入库前向量去重、Skill 生成时语义比对合并、一次性清理现存重复。

**Architecture:** 利用现有 ChromaDB 内置 embedding 做语义相似度判断（distance < 0.15 视为重复），在 ReflectTool 和 SkillManagerTool 中嵌入去重逻辑，不引入新依赖。

**Tech Stack:** Python, ChromaDB, DeepSeek API (LLM 合并用), SQLite

---

## 文件结构

```
src/
├── db/vector_store.py          # 修改: 新增 skill_embeddings 集合
├── tools/reflect.py            # 修改: 保存经验前向量去重
└── tools/skill_manager.py      # 修改: 生成 skill 时语义比对 + LLM 合并
scripts/
└── cleanup_duplicate_skills.py # 新建: 一次性清理脚本
```

- `vector_store.py` —— 只管集合创建和搜索，职责不变
- `reflect.py` —— 去重判断在 ReflectTool 内，不改 lts 接口
- `skill_manager.py` —— 去重 + 合并逻辑内聚在 SkillManagerTool 内
- `scripts/cleanup_duplicate_skills.py` —— 独立脚本，不依赖 Web/调度器启动

---

### Task 1: 新增 skill_embeddings 集合

**Files:**
- Modify: `src/db/vector_store.py:15-23`

- [ ] **Step 1: 在 `_ensure_collections` 中添加 `skill_embeddings` 集合**

```python
def _ensure_collections(self) -> None:
    names = [c.name for c in self.client.list_collections()]
    for col_name in [
        "conversation_embeddings",
        "experience_embeddings",
        "code_pattern_embeddings",
        "research_embeddings",
        "skill_embeddings",
    ]:
        if col_name not in names:
            self.client.create_collection(name=col_name)
```

- [ ] **Step 2: 验证集合创建成功**

```bash
python -c "from src.db.vector_store import vector_store; cols = [c.name for c in vector_store.client.list_collections()]; print('skill_embeddings' in cols)"
```
Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add src/db/vector_store.py
git commit -m "feat: vector_store 新增 skill_embeddings 集合

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: ReflectTool 经验去重

**Files:**
- Modify: `src/tools/reflect.py:63-76`

- [ ] **Step 1: 在保存经验前添加向量去重逻辑**

修改 `src/tools/reflect.py`，在 for 循环中 `lts.save_experience()` 之前插入去重检查：

```python
import logging
logger = logging.getLogger("evomentor.reflect")
```

然后在 `for insight in data.get("insights", []):` 循环体内，`exp_id = lts.save_experience(...)` 之前插入：

```python
            # 向量去重：检查是否与已有经验高度相似
            text = f"{insight.get('title', '')}: {insight.get('content', '')}"
            similar = vector_store.search("experience_embeddings", text, n_results=1)
            if similar and similar[0].get("distance", 1.0) < 0.15:
                logger.info("[Reflect] 跳过重复经验: %s (distance=%.3f)",
                            insight.get('title', '')[:50], similar[0]["distance"])
                continue
```

确保 `text` 变量在去重处和下面 `vector_store.add()` 处复用同一变量，避免重复定义。

- [ ] **Step 2: 验证逻辑 —— 检查日志输出格式**

```bash
python -c "
from src.tools.reflect import ReflectTool
from src.memory.short_term import ShortTermMemory
import asyncio

# 验证工具可正常初始化
tool = ReflectTool(ShortTermMemory())
print('ReflectTool 初始化成功')
print('工具名:', tool.name)
"
```
Expected: 工具名 `reflect`，无异常

- [ ] **Step 3: Commit**

```bash
git add src/tools/reflect.py
git commit -m "feat: ReflectTool 保存经验前向量去重

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: SkillManagerTool 去重合并

**Files:**
- Modify: `src/tools/skill_manager.py`

- [ ] **Step 1: 添加 logger 和辅助方法**

在 `skill_manager.py` 顶部添加必要的 import：

```python
import logging
from src.db.vector_store import vector_store

logger = logging.getLogger("evomentor.skill_manager")
```

- [ ] **Step 2: 添加 LLM 合并方法**

在 `SkillManagerTool` 类中添加 `_merge_skill` 方法：

```python
    def _merge_skill(self, name: str, old_trigger: str, old_rules: str,
                     new_trigger: str, new_rules: str) -> dict:
        """将新旧 skill 内容发给 LLM 合并，返回合并后的 dict。"""
        prompt = f"""你是 Skill 合并模块。请将以下两个相似的 Skill 合并为一个。

## 已有 Skill
- 触发条件: {old_trigger}
- 行为规则: {old_rules}

## 新候选 Skill
- 触发条件: {new_trigger}
- 行为规则: {new_rules}

请合并去重，保留所有有价值的信息，输出 JSON：

```json
{{
    "trigger_condition": "合并后的触发条件",
    "behavior_rules": "合并后的行为规则（Markdown）"
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
            return data
        except json.JSONDecodeError:
            return {"trigger_condition": new_trigger, "behavior_rules": new_rules}
```

- [ ] **Step 3: 修改 execute 方法，在创建 skill 前加入去重合并**

将当前 `execute` 方法中 `for skill_data in data.get("new_skills", [])` 循环体改为：

```python
        created = []
        for skill_data in data.get("new_skills", []):
            name = skill_data.get("name", "unnamed")
            trigger = skill_data.get("trigger_condition", "")
            rules = skill_data.get("behavior_rules", "")

            # 向量去重：检查是否与已有 skill 高度相似
            skill_text = f"触发条件: {trigger}\n行为规则: {rules}"
            similar = vector_store.search("skill_embeddings", skill_text, n_results=1)
            if similar and similar[0].get("distance", 1.0) < 0.15:
                # 命中相似 skill，LLM 合并升级
                similar_id = similar[0].get("id", "")
                logger.info("[SkillManager] 命中相似 skill: %s (distance=%.3f)，执行合并",
                            similar_id, similar[0]["distance"])
                # 从数据库读取已有 skill 详情
                conn = get_connection()
                existing = conn.execute(
                    "SELECT * FROM skills WHERE name = ?", (similar_id.replace("skill-", ""),)
                ).fetchone()
                conn.close()

                if existing:
                    merged = self._merge_skill(
                        name, existing["trigger_condition"], existing["behavior_rules"],
                        trigger, rules
                    )
                    new_trigger = merged.get("trigger_condition", existing["trigger_condition"])
                    new_rules = merged.get("behavior_rules", existing["behavior_rules"])
                    new_version = existing["version"] + 1

                    # 覆盖写入 skill 文件
                    filename = f"skills/{existing['name']}.md"
                    content = f"""# Skill: {existing['name']}

## 触发条件
{new_trigger}

## 行为规则
{new_rules}

## 元数据
- 版本: {new_version}
- 创建时间: {datetime.now().isoformat()}
- 来源: 自动合并
"""
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(content)

                    # 更新数据库
                    conn = get_connection()
                    conn.execute(
                        """UPDATE skills SET trigger_condition = ?, behavior_rules = ?,
                           version = ? WHERE id = ?""",
                        (new_trigger, new_rules, new_version, existing["id"]),
                    )
                    conn.commit()
                    conn.close()

                    created.append(f"{existing['name']} (v{new_version} 合并升级)")
                    logger.info("[SkillManager] 合并完成: %s v%d", existing['name'], new_version)
                    continue
                # 如果 DB 读取失败，走正常创建流程

            # 无相似 skill，正常创建
            os.makedirs("skills", exist_ok=True)
            filename = f"skills/{name}.md"
            version = 1

            if os.path.exists(filename):
                version = 2

            content = f"""# Skill: {name}

## 触发条件
{trigger}

## 行为规则
{rules}

## 元数据
- 版本: {version}
- 创建时间: {datetime.now().isoformat()}
- 来源: 自动生成
"""
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)

            # 写入向量库
            vector_store.add("skill_embeddings", f"skill-{name}", skill_text)

            record_generation(filename, f"新增 Skill {name}")

            # 注册到数据库
            conn = get_connection()
            conn.execute(
                """INSERT INTO skills (name, trigger_condition, behavior_rules, version, file_path)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, trigger, rules, version, filename),
            )
            conn.commit()
            conn.close()

            created.append(f"{name} (v{version})")
```

- [ ] **Step 4: 验证模块导入和初始化**

```bash
python -c "
from src.tools.skill_manager import SkillManagerTool
tool = SkillManagerTool()
print('SkillManagerTool 初始化成功')
print('工具名:', tool.name)
print('_merge_skill 方法存在:', hasattr(tool, '_merge_skill'))
"
```
Expected: 工具名 `skill_manager`，`_merge_skill` 为 `True`，无异常

- [ ] **Step 5: Commit**

```bash
git add src/tools/skill_manager.py
git commit -m "feat: SkillManagerTool 向量去重 + LLM 合并升级

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: 一次性清理脚本

**Files:**
- Create: `scripts/cleanup_duplicate_skills.py`

- [ ] **Step 1: 创建脚本文件**

```python
"""一次性清理 skills/ 下的重复 skill 文件。

用法:
    python scripts/cleanup_duplicate_skills.py --dry-run   # 预览模式
    python scripts/cleanup_duplicate_skills.py              # 实际执行

逻辑:
    1. 读取 skills/ 下所有 .md 文件
    2. 向量化后聚类（distance < 0.15 归为一簇）
    3. 每簇通过 LLM 合并为一个规范版本
    4. 删除多余文件，更新数据库
"""
import os
import sys
import json
import argparse
from datetime import datetime
from collections import defaultdict

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.vector_store import vector_store
from src.core.llm import llm
from src.db.models import get_connection


def read_skills(skills_dir: str) -> list[dict]:
    """读取所有 skill 文件，返回 [{name, filepath, trigger, rules, content}]。"""
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


def _parse_skill_md(content: str) -> tuple[str, str]:
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
    """将相似的 skill 聚类。使用临时 ChromaDB 集合。"""
    # 将每个 skill 向量化并存入临时集合
    temp_col = "temp_skill_dedup"
    try:
        vector_store.client.delete_collection(name=temp_col)
    except Exception:
        pass
    vector_store.client.create_collection(name=temp_col)

    for s in skills:
        text = f"触发条件: {s['trigger']}\n行为规则: {s['rules']}"
        vector_store.add(temp_col, f"temp-{s['name']}", text)

    # 两两比较，构建邻接表
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
                # 从 temp-xxx 解析 skill name
                skill_name = r["id"].replace("temp-", "")
                for idx, s in enumerate(skills):
                    if s["name"] == skill_name and not visited[idx]:
                        visited[idx] = True
                        cluster.append(s)
                        break
        if cluster:
            clusters.append(cluster)

    # 清理临时集合
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
    """更新数据库 skills 表：删除旧的，插入合并后的。"""
    conn = get_connection()
    for cluster, merged in zip(clusters, merged_results):
        # 删除簇内所有旧记录
        for s in cluster:
            conn.execute("DELETE FROM skills WHERE name = ?", (s["name"],))
        # 确定版本号
        version = 1
        for s in cluster:
            if "版本:" in s["content"] or "版本：" in s["content"]:
                try:
                    v = int(s["content"].split("版本:")[1].split()[0])
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

    # 独立 skill 保持不变
    for cluster in single_clusters:
        s = cluster[0]
        merged_results.append({
            "name": s["name"],
            "trigger": s["trigger"],
            "rules": s["rules"],
        })

    if args.dry_run:
        print("\n[Dry-Run] 未做任何修改。去掉 --dry-run 执行实际清理。")

        # 显示将要删除的文件
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

    # 实际执行
    print("\n--- 执行合并 ---")
    # 先 git commit 备份当前状态
    os.system("git add skills/ && git commit -m 'backup: 去重前备份 skill 文件' 2>/dev/null || true")

    # 删除旧文件
    all_clusters = multi_clusters + single_clusters
    for i, (cluster, merged) in enumerate(zip(all_clusters, merged_results)):
        # 写入合并后的文件
        filepath = write_skill(merged["name"], merged["trigger"], merged["rules"])
        print(f"  写入: {filepath}")
        # 删除簇内其他文件
        for s in cluster:
            if s["name"] != merged["name"] and os.path.exists(s["filepath"]):
                os.remove(s["filepath"])
                print(f"  删除: {s['filepath']}")

    # 更新向量库
    for merged in merged_results:
        text = f"触发条件: {merged['trigger']}\n行为规则: {merged['rules']}"
        vector_store.add("skill_embeddings", f"skill-{merged['name']}", text)

    # 更新数据库
    update_db_skills(multi_clusters, merged_results[:len(multi_clusters)])

    print(f"\n清理完成。原有 {len(skills)} 个 skill → 合并为 {len(merged_results)} 个。")
    print("请检查 skills/ 目录确认结果，可通过 git 回滚。")
    print("\n建议运行: git add skills/ && git commit -m 'cleanup: 合并重复 skill 文件'")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 创建 scripts 目录并执行 dry-run 预览**

```bash
mkdir -p scripts
python scripts/cleanup_duplicate_skills.py --dry-run
```
Expected: 输出重复组详情，显示将要删除/合并的文件列表，不实际修改。

- [ ] **Step 3: 验证 dry-run 输出正确后，执行实际清理**

```bash
python scripts/cleanup_duplicate_skills.py
```
Expected: 合并成功，skill 文件数从 12 减少到约 3-4 个。

- [ ] **Step 4: 检查结果并提交**

```bash
ls skills/
```
检查合并后的 skill 文件内容是否合理。

```bash
git add skills/ scripts/
git commit -m "cleanup: 去重合并相似 skill 文件，从 12 个减少为独立类别

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

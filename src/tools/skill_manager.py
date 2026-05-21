"""Skill 管理工具 —— 将稳定的经验转化为可复用的 Skill。"""
import os
from src.core.git_auto import record_generation
import json
from datetime import datetime
from src.tools.base import BaseTool, ToolResult
from src.core.config import config
from src.core.llm import llm
from src.memory.long_term import lts
from src.db.models import get_connection
import logging
from src.db.vector_store import vector_store

logger = logging.getLogger("evomentor.skill_manager")


class SkillManagerTool(BaseTool):
    name = "skill_manager"
    description = "审视长期经验，将高置信度、反复出现的经验转化为可复用的 Skill。"

    def _merge_skill(self, old_trigger: str, old_rules: str,
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
            logger.warning("[SkillManager] LLM 合并 JSON 解析失败，使用简单拼接回退")
            return {
                "trigger_condition": f"{old_trigger}\n\n（新增）{new_trigger}",
                "behavior_rules": f"{old_rules}\n\n（新增）{new_rules}",
            }

    async def execute(self) -> ToolResult:
        # 1. 拉取待评估的经验（未关联 Skill 的经验）
        conn = get_connection()
        rows = conn.execute(
            """SELECT * FROM experiences
               WHERE category = 'code_pattern' AND confidence >= ?
               ORDER BY created_at DESC LIMIT 30""",
            (config.SKILL_CONFIDENCE_THRESHOLD,),
        ).fetchall()
        conn.close()

        if not rows:
            return ToolResult(success=True, content="暂无可转化为 Skill 的经验。")

        experiences_text = "\n".join(
            f"- [{r['id']}] {r['title']}: {r['content'][:300]}" for r in rows
        )

        existing_skills = lts.get_experiences_by_category("skill_registry", limit=20)

        prompt = f"""你是 Evomentor 的 Skill 管理模块。审视以下经验，判断哪些可以转化为可复用的 Skill。

## 候选经验
{experiences_text[:4000]}

## 已有 Skills（避免重复）
{chr(10).join(f"- {s['title']}" for s in existing_skills) if existing_skills else "（暂无）"}

请判断哪些经验足够稳定、通用，值得转化为 Skill。输出 JSON：

```json
{{
    "new_skills": [
        {{
            "name": "Skill 英文名（如 django-n1-query-detect）",
            "trigger_condition": "触发这个 Skill 的条件",
            "behavior_rules": "Markdown 格式的行为规则，包含 1.检测方法 2.修复建议 3.相关案例"
        }}
    ]
}}
```

标准：
- 经验出现的频率高（有多条相关经验）
- 经验可转化为明确的规则
- 与已有 Skill 不重复
- 如果没有合适的候选，返回空数组"""

        response = llm.chat([{"role": "user", "content": prompt}])

        try:
            data = json.loads(
                response["content"]
                .split("```json")[-1].split("```")[0]
                if "```" in response["content"]
                else response["content"]
            )
        except json.JSONDecodeError:
            return ToolResult(success=True, content="Skill 分析未产生有效结果。")

        created = []
        for skill_data in data.get("new_skills", []):
            name = skill_data.get("name", "unnamed")
            trigger = skill_data.get("trigger_condition", "")
            rules = skill_data.get("behavior_rules", "")

            # 向量去重：检查是否与已有 skill 高度相似
            skill_text = f"触发条件: {trigger}\n行为规则: {rules}"
            try:
                similar = vector_store.search("skill_embeddings", skill_text, n_results=1)
            except Exception as e:
                logger.warning("[SkillManager] 向量搜索失败，跳过去重: %s", e)
                similar = []
            if similar and similar[0].get("distance", 1.0) < 0.15:
                similar_id = similar[0].get("id", "")
                logger.info("[SkillManager] 命中相似 skill: %s (distance=%.3f)，执行合并",
                            similar_id, similar[0]["distance"])
                # 从 similar_id 中提取 skill name（格式: "skill-{name}"）
                similar_name = similar_id.replace("skill-", "")
                # 从数据库读取已有 skill 详情
                conn = get_connection()
                existing = conn.execute(
                    "SELECT * FROM skills WHERE name = ?", (similar_name,)
                ).fetchone()
                conn.close()

                if existing:
                    merged = self._merge_skill(
                        existing["trigger_condition"], existing["behavior_rules"],
                        trigger, rules
                    )
                    new_trigger = merged.get("trigger_condition", existing["trigger_condition"])
                    new_rules = merged.get("behavior_rules", existing["behavior_rules"])
                    new_version = existing["version"] + 1

                    # 覆盖写入 skill 文件
                    os.makedirs("skills", exist_ok=True)
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

                    record_generation(filename, f"合并更新 Skill {existing['name']}")

                    # 更新数据库
                    conn = get_connection()
                    conn.execute(
                        """UPDATE skills SET trigger_condition = ?, behavior_rules = ?,
                           version = ? WHERE id = ?""",
                        (new_trigger, new_rules, new_version, existing["id"]),
                    )
                    conn.commit()
                    conn.close()

                    # 更新向量库中的向量（upsert 避免重复 ID 报错）
                    vector_store.upsert("skill_embeddings", f"skill-{existing['name']}",
                                        f"触发条件: {new_trigger}\n行为规则: {new_rules}")

                    created.append(f"{existing['name']} (v{new_version} 合并升级)")
                    logger.info("[SkillManager] 合并完成: %s v%d", existing['name'], new_version)
                    continue
                else:
                    logger.warning("[SkillManager] 向量命中 %s 但 DB 无对应记录，清理孤立向量并降级为新建",
                                   similar_id)
                    try:
                        vector_store.delete("skill_embeddings", similar_id)
                    except Exception:
                        pass

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

        if created:
            return ToolResult(
                success=True,
                content=f"创建了 {len(created)} 个新 Skill: {', '.join(created)}",
            )
        return ToolResult(success=True, content="未发现需要创建的新 Skill。")

    def get_parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

"""Skill 管理工具 —— 将稳定的经验转化为可复用的 Skill。"""
import os
import json
from datetime import datetime
from src.tools.base import BaseTool, ToolResult
from src.core.config import config
from src.core.llm import llm
from src.memory.long_term import lts
from src.db.models import get_connection


class SkillManagerTool(BaseTool):
    name = "skill_manager"
    description = "审视长期经验，将高置信度、反复出现的经验转化为可复用的 Skill。"

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

            # 写入 Markdown 文件
            os.makedirs("skills", exist_ok=True)
            filename = f"skills/{name}.md"
            version = 1

            # 检查已有版本
            if os.path.exists(filename):
                version = 2  # 简化处理，实际可读取已有版本号

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

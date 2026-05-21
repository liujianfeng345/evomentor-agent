# Skill 去重系统设计

## 问题

自动生成的 12 个 skill 文件中，9 个实质内容相同（检测事件结果为空），2 个内容相同（GitHub 提交偏向文档），仅 3 类有效。根因：

1. ReflectTool 保存经验时无去重，相同模式被反复提取
2. SkillManagerTool 仅凭标题列表判断重复，不同措辞即可绕过
3. 每次生成独立运行，无跨次协调

## 方案

三层去重：经验入库前向量去重 + Skill 生成时语义比对合并 + 一次性清理现有重复。

## 模块 1：经验去重

**文件**：`src/tools/reflect.py`

在 `lts.save_experience()` 调用前，用 ChromaDB 内置 embedding 做相似度判断：

```
新 insight 文本 → vector_store.search("experience_embeddings", text, n_results=1)
                  ↓
          distance < 0.15? → 跳过（日志记录）
                  ↓ 否
         lts.save_experience() + vector_store.add()
```

- 仅影响自动反思生成的经验，手动经验不受影响
- 不改 `lts.save_experience()` 接口
- 阈值 0.15（相似度 > 0.85）可调

## 模块 2：Skill 去重合并

**文件**：`src/tools/skill_manager.py`、`src/db/vector_store.py`

LLM 生成候选 skill 后：

1. 将 skill 内容向量化，在新建的 `skill_embeddings` 集合中搜索
2. 命中相似 skill（distance < 0.15）→ 新旧内容一起发给 LLM 合并 → 覆盖已有文件，版本号 +1
3. 未命中 → 正常创建新文件，同时写入 `skill_embeddings`

LLM 合并 prompt 包含新旧 skill 完整内容，要求输出去重合并后的 behavior_rules。合并后更新数据库 skills 表对应行。

`vector_store.py` 的 `_ensure_collections` 新增 `skill_embeddings` 集合。

## 模块 3：一次性清理脚本

**文件**：`scripts/cleanup_duplicate_skills.py`

1. 读取 `skills/` 下所有 `.md` 文件
2. 将每个 skill 内容向量化，两两计算相似度
3. 聚类（相似度 > 0.85 归为一簇）
4. 对每簇：LLM 合并为一个规范版本，用最合理的文件名，其余删除
5. 同步更新数据库 skills 表
6. 输出清理报告

安全措施：执行前自动 git commit，支持 dry-run 预览模式。

## 改动清单

| 文件 | 改动 | 行数 |
|------|------|------|
| `src/tools/reflect.py` | 保存前向量去重 | ~8 |
| `src/db/vector_store.py` | 新增 `skill_embeddings` 集合 | ~1 |
| `src/tools/skill_manager.py` | 向量比对 + LLM 合并 + 写入向量库 | ~35 |
| `scripts/cleanup_duplicate_skills.py` | 新建一次性脚本 | ~80 |

## 不改的部分

- `lts.save_experience()` — 职责不变
- `src/memory/retrieval.py` — skill 加载逻辑不变
- `src/db/models.py` — 表结构不变

## 阈值说明

- `distance < 0.15`：ChromaDB 内置 embedding 的余弦距离，对应相似度 > 0.85
- 后续可根据实际效果在 config 中暴露为 `SKILL_DEDUP_THRESHOLD`

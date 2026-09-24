# 知识对象 Schema

所有进入 `02_结构化知识/` 的 Markdown 建议保留以下 frontmatter。

```yaml
---
id: CASE-001
knowledge_type: case
title: ""
source_path: ""
source_id: ""
source_anchor: ""
review_status: draft
rag_include: false
evidence_level: E1
problem_type: ""
material_system: ""
application: ""
outcome: ""
tags: []
created_at: 2026-08-29
---
```

## 必填字段

| 字段 | 作用 |
|---|---|
| `id` | 稳定引用 ID |
| `knowledge_type` | case / rule / standard / project / experiment / literature |
| `source_path` | 原始文件路径 |
| `source_id` | CSV行ID、项目ID、案例ID等 |
| `review_status` | draft / reviewed |
| `rag_include` | 是否允许进入 RAG |
| `evidence_level` | E1 / E2 / E3 / E4 |

## 推荐规则
- AI 首次抽取：`review_status: draft`
- 人工确认后：`review_status: reviewed`
- 只有确认与当前 MVP 有关时：`rag_include: true`
- 一个知识对象只表达一个主要问题，避免“大而全”笔记

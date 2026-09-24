# RAG 索引与检索规则

## P0 数据源
1. 企业现成 `rag_chunks.jsonl` / RAG分块
2. `cases.csv` 与 8D 详情
3. 当前 Demo 相关的 reviewed 结构化知识

## P1 数据源
4. 工艺参数/生产通则
5. 行业标准
6. 技术资料/综述

## 索引原则
每个 chunk 至少保留：
- `chunk_id`
- `source_path`
- `source_id`
- `doc_type`
- `title`
- `text`
- 可用 metadata（problem_type / material_system / application 等）

## 检索顺序
1. 识别问题类型
2. Metadata 过滤/加权
3. 召回 Top-K
4. 失败/问题案例优先
5. 再补成功、规则、标准或技术资料作为对照
6. LLM 只能基于检索证据生成结论

## 降级策略
若向量检索当天不稳定：
- 先用现成 RAG chunks
- 使用关键词 + Metadata Filter
- 保留原文引用
- 不为了“高级 RAG”牺牲稳定 Demo

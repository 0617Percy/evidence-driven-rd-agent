# AUTO-001 G3 Final Code Freeze V1.0

> **G3 FINAL HUMAN GATE = PASS**
> **DEVELOPMENT FREEZE = YES**
> 生成时间：V1.0 交接打包完成时。本文档记录最终冻结的 Runtime 与代码文件 hash，供 Y 验收核对。

---

## 1. 冻结状态

| 项 | 值 |
|---|---|
| 产品 | 研发避坑 Agent（Demo：AUTO-001） |
| 客户/应用 | 汽车内饰革 |
| 产品型号 | HD-S303 |
| 目标指标 | -30℃ 耐折 ≥ 5万次 |
| Current Runtime | RC1 / 170 chunks |
| Retriever | RC2.2 FROZEN |
| Qdrant collection | `rag_chunks_auto001_rc2_2` |
| Qdrant path | `outputs/qdrant_v1_2` |
| Embedding | `BAAI/bge-small-zh-v1.5`（512 维） |

---

## 2. 关键 Runtime 文件 hash

- **RC1 corpus** `data/derived/rag_chunks_auto001_rc1.jsonl`
  - `b9bc3297125e6b746ef54d66e81f9e792470d95d1336961226acb0147b652f74`
- **app.py**
  - `c58cf58a075a33d55cfcfc739531163497c2df2cd86118c1e9d711c55ddde281`

> 其余全部运行文件的相对路径 / 大小 / sha256 见
> `docs/baseline/AUTO001_G3_Final_Code_Freeze_Manifest_V1.0.json`。

---

## 3. 治理链路（全部冻结）

- Knowledge Curator V0.2
- Knowledge Review V0.3
- Knowledge Writeback V0.4
- Knowledge History V0.5
- Context Entity V0.6
- Context Scope/Formulation V0.6.1
- Product Role V0.6.2
- Validation Policy V0.6.3
- Conversation Scene Context V0.6.4（会话场景继承）
- Conversation Product Context V0.6.5（会话主题产品 vs 证据产品）
- Knowledge Correction V0.7
- Supersession Finalization V0.7.1

---

## 4. 更正关系（append-only 冻结）

```
AK-51bc951a799242a4adfbe80ae635e448 ─┐
                                      ├─→ AK-fc31f218c2a14ef48389b761ec210b6b
AK-c444740cec87424a903b2767f3aa7dfb ─┘
      relation_type = SUPERSEDED_BY_CORRECTION
```

旧 AK 不改、不删；旧 Manifest 行不改；更正关系由
`outputs/knowledge_feedback/knowledge_supersession_relations.jsonl` 承载。

---

## 5. 冻结边界（本轮不执行）

- 不新增 Agent 功能、不改 Retriever、不改 RC1、不改 Qdrant 内容。
- 不 re-index、不修改 Truth Source、不修改 Evidence Gap、不修改 P0/P1/P2。
- 不修改旧 AK、不修改旧 Manifest、不调用 LLM、不生成新 Candidate。
- 不 git add / git commit（等 W 最终验收后再决定）。

---

## 6. 交接产物

- 可运行交接包：`docs/handoff/packages/AUTO001_Y_Runnable_Handoff_20260830_V1.0.zip`
- SHA256：`docs/handoff/packages/AUTO001_Y_Runnable_Handoff_20260830_V1.0.sha256.txt`
- 包清单：`PACKAGE_MANIFEST.json`
- Y 首次运行说明：`README_Y_FIRST_RUN.md`
- 技术交接：`docs/handoff/AUTO001_G3_Final_Technical_Handoff_V1.0.md`

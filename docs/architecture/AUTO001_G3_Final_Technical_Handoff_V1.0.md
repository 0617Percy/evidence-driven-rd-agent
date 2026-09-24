# AUTO-001 G3 Final Technical Handoff V1.0

> **G3 FINAL HUMAN GATE = PASS**
> **DEVELOPMENT FREEZE = YES**
> 本文档记录最终冻结时的系统架构、Runtime、治理链路与责任边界，供 Y 接续运维与审计。

---

## 1. 冻结状态总览

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

## 2. 系统架构

```
Live Query
   ↓
RAG 检索（Retriever RC2.2 → Qdrant rag_chunks_auto001_rc2_2）
   ↓
Answer 生成 + Safety（V1.2）+ Structured Output Contract（V1.3.1）
   ↓
Context Entity Resolution（V0.6）
   ↓
Context Scope & Formulation Grounding（V0.6.1）
   ↓
Product Role & Scope Coherence（V0.6.2）
   ↓
Validation Policy Guard（V0.6.3）  ← 冻结 P0/P1/P2
   ↓
Knowledge Curator（V0.2）→ Candidate（PENDING_REVIEW）
   ↓
Human Review（V0.3）→ APPROVED_FOR_KB / NEED_MORE_EVIDENCE / REJECTED
   ↓
Knowledge Write Gate（V0.4）→ WRITTEN_TO_DERIVED_KB
   ↓
Knowledge History / Correction（V0.5 / V0.7 / V0.7.1）
```

---

## 3. 当前 Runtime

- Corpus：RC1，`data/derived/rag_chunks_auto001_rc1.jsonl`，**170 chunks**。
- Retriever：RC2.2（`src/eval_gold_rc2_2.py`），`candidate_k=60`。
- Qdrant：local mode，path `outputs/qdrant_v1_2`，collection `rag_chunks_auto001_rc2_2`。
- Embedding：`BAAI/bge-small-zh-v1.5`，512 维。

**Runtime 不做任何 re-index / 换 collection / 换 embedding。**

---

## 4. Retriever

- 仅从 Qdrant 的 `rag_chunks_auto001_rc2_2` 检索。
- 检索结果只作为**证据候选**，不直接构成结论。

---

## 5. Evidence Chain

```
Retrieved Evidence（E1/E2/E3/EG 分级）
   → Historical Evidence（历史条件）
   → Technical Evidence（技术/标准/文献）
   → Condition Gap（历史 vs 当前条件差异）
   → Evidence Gap（缺当前直接证据）
```

- **无直接证据 → 不判断。**
- 所有结论必须带 `source_refs`（chunk_id / source）可追溯。

---

## 6. Context Scope

- `AUTO001_SCOPED`：进入 AUTO-001 治理链。
- `GENERIC` / `NOT_SCOPED`：仅通用技术咨询，不进入 AUTO-001 知识更新治理。

**V0.6.4 Conversation Scene Context（会话场景继承）：**

- 上一轮明确 `AUTO001_SCOPED` 后，保存 ephemeral `active_scene_context`（scope + product + application + metric）。
- 自然省略式 follow-up（如 `-10℃都裂了，是不是-30℃肯定不行？`）可**继承**上一轮 AUTO001 scene，避免因单轮锚点不足掉出场景。
- `SESSION_CONTEXT_IS_EVIDENCE = NO`：Scene Context 只用于 Scope，绝不作 Evidence / Source / Formulation。
- Generic / 明确其它产品 / 无关问题可正常打断继承。

---

## 7. Product Resolution

- 产品**只从检索证据**解析，**不从用户问题字面**解析。
- 角色判定：`PRIMARY_SUBJECT / SECONDARY_COMPONENT / COMPARATOR / GENERIC_REFERENCE`。

**V0.6.5 Conversation Subject vs Evidence Product：**

- **Evidence Product Resolution**（V0.6 / V0.6.2）：只从 Retrieved Evidence 判定主体产品，可能因无关噪声 chunk 出现 AMBIGUOUS。
- **Conversation Subject Resolution**（V0.6.5）：回答"用户当前在讨论谁"，优先级 = 本轮 Query 明确型号 → 上一轮 Scene 产品 → Evidence fallback。
- 两者分开：`QUERY_IS_NOT_PRODUCT_EVIDENCE = YES`、`SESSION_CONTEXT_IS_NOT_PRODUCT_EVIDENCE = YES`。会话主题只用于 UI 展示 / 场景标签，不作 Evidence。

---

## 8. Formulation Guard

- 当前软段/配方体系在 Runtime 证据中**未明确**时，不得断言"当前 PTMEG/PPG/PCDL 体系"。
- 历史"PPG → PTMEG 纠正措施改善"是**历史事实**，不等同于"当前 = PTMEG"。

---

## 9. Validation Policy（冻结 P0/P1/P2）

- **P0**：对当前拟供货 HD-S303，在当前汽车内饰革应用条件下，按 `QB/T 2714-2018` 开展 `-30℃ 耐折 ≥ 5万次` 专项验证。
- **P1**：核查当前 HD-S303 实际软段/配方体系，并确认对应低温性能依据。
- **P2**：如存在 `-20℃` 出厂抽检或同条件对比数据，可作为 `-30℃` 验证的中间参考，但**不能替代** `-30℃` 专项验证。

禁止在 P0/P1/P2 中写：`改PCDL / 改PTMEG / 改PPG / 推荐PCDL-2000 / 调整配方 / 配方方案`（属 POST_VALIDATION R&D 探索，非当前验证优先级）。

---

## 10. Knowledge Governance

- **Curator V0.2**：生成 Knowledge Update Candidate。
- **Review V0.3**：`APPROVE / NEED_MORE_EVIDENCE / REJECT`，人工决策，不可自动。
- **Writeback V0.4**：Knowledge Write Gate（需 reviewer role + name + Evidence confirmation）。
- **History V0.5**：历史聚合 + 治理状态解析（append-only 只读）。
- 治理不变式：`USER_QUESTION_IS_EVIDENCE=NO`、`LLM_ANSWER_IS_APPROVED_EVIDENCE=NO`、`AUTO_WRITE_MASTER_KB=NO`、`AUTO_REINDEX=NO`、`HUMAN_REVIEW_REQUIRED=YES`。

---

## 11. Correction / Supersession

- **V0.7**：Legacy 派生知识审计（`UNSUPPORTED_CURRENT_FORMULATION` / `OUT_OF_POLICY_FORMULATION_PRESCRIPTION`）+ Correction Intent（PROPOSED）。
- **V0.7.1**：Supersession Finalization（`finalize_correction_supersession`）。

最终更正关系（append-only）：

```
AK-51bc951a799242a4adfbe80ae635e448 ─┐
                                      ├─→ AK-fc31f218c2a14ef48389b761ec210b6b
AK-c444740cec87424a903b2767f3aa7dfb ─┘
      relation_type = SUPERSEDED_BY_CORRECTION
```

- 旧 AK 不改、不删；旧 Manifest 行不改；更正关系由 `knowledge_supersession_relations.jsonl` 承载。

---

## 12. Agent 做什么 / 工程师做什么

**Agent（系统）做什么：**
- 检索证据、按证据链给出可追溯的风险预审与验证动作（P0/P1/P2）。
- 生成候选知识建议、展示治理状态，**不自动**写知识库、不自动 re-index、不自动下结论。

**工程师（W/Y）做什么：**
- 阅读预审结论，判断证据是否足够。
- 人工 Review（批准/补证/拒绝）与 Knowledge Write Gate 操作。
- 最终技术决策与 `-30℃` 专项验证由工程师执行。

---

## 13. 展示边界

- **无直接证据 → 不判断**（例如：历史 `-10℃` 案例不能外推 `-30℃`）。
- 所有数字/结论均带来源引用，可追溯至具体 chunk_id / source。

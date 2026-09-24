# AUTO-001 Full Source Coverage / KB Snapshot Sync Gate V1.0

> 审计类型：READ-ONLY SOURCE LINEAGE AUDIT（来源链审计，非 Corpus 升级）
> DO_NOT_INGEST：本文件不作为 RAG Source。
> 生成时间：2026-08-30

---

## 1. 输入完整性

| 输入 | 状态 |
|---|---|
| Y V2 包 `AUTO001_KB_Sync_20260830_V2.zip` | **未找到**（两个指定路径 + 全盘搜索均不存在）。Y 的 V2 同步包尚未交付到 W。 |
| W RC1 `data\derived\rag_chunks_auto001_rc1.jsonl` | 存在，chunk count = **170** |
| RC1 SHA256 vs Day1 Manifest | **一致**（`b9bc3297…652f74`）→ `RC1_FREEZE_DRIFT = PASS` |
| 企业原始 `rag_chunks.jsonl` | 存在（`data/truth_source/模拟数据集_v1.0/12_AI训练语料/rag_chunks.jsonl`），chunk count = **169** |

> 说明：V2 同步包缺失，但企业原始 Truth Source 内容本身在 W 侧存在；本轮 169→170 lineage / 12 类 coverage / Evidence Gap 复核 / Qdrant 一致性均基于该 Truth Source 完成。

---

## 2. 169 → 170 Lineage Audit（程序化逐项证明）

- ORIGINAL_CHUNKS = **169**
- RC1_CHUNKS = **170**
- DIRECTLY_PRESERVED = **169**（逐 chunk JSON 完全一致）
- MODIFIED_EXISTING = **0**
- REMOVED = **0**
- NEW = **1**（`CK-AUTO001-REQ-RC-001`）
- ONLY_REQ_RECHUNK_PROCESSING = **YES**

特殊检查：

| chunk_id | 原始169 | RC1 | 结论 |
|---|---|---|---|
| CK-0168 | ✅ | ✅ | 保留（原文未改） |
| CK-0169 | ✅ | ✅ | 保留（原文未改） |
| CK-AUTO001-REQ-RC-001 | ❌ | ✅ | 唯一新增（合法 re-chunk） |

**结论：不是“169+1=170”的推定，而是程序化逐 chunk_id + 全文 JSON 比对证明：169 完全保留 + 仅 1 个新增，无修改、无删除。**

---

## 3. REQ-AUTO-001 Re-chunk Lineage

```
Original Source MD（03_客户需求/需求说明书样例_汽车革客户.md，全文21行）
├─ 企业原始：CK-0168（intro，第1-7行）     —— RC1 保留
├─ 企业原始：CK-0169（性能要求表，第9-17行）—— RC1 保留
└─ RC1 新增：CK-AUTO001-REQ-RC-001（全文1-21行，含“对接记录”）
```

逐项回答（§五）：

1. CK-AUTO001-REQ-RC-001 的 text **完全来自原始需求说明书**（逐字 = 源 MD 全文，含“对接记录”）。
2. **未引入源中不存在的事实**（`text = raw_text`，`original_source_modified = false`）。
3. 关系：CK-0168（intro）+ CK-0169（性能要求）是企业原始对源文件的“部分覆盖”；CK-AUTO001-REQ-RC-001 是“整篇文档”语义聚合 re-chunk，额外包含了 CK-0168/CK-0169 未覆盖的“对接记录”段（HD-S303 已过6周耐水解等）。
4. CK-0168 / CK-0169 在 RC1 中**仍保留**。
5. **只有这一处新增/加工**（`derived_chunks = chunks + [new_chunk]`）。
6. **不存在任何其它 chunk text 重写**（MODIFIED_EXISTING = 0）。

---

## 4. RC1 Source Coverage（12 类，基于 RC1 `source` 字段统计）

| 类 | RC1 chunks | 覆盖 |
|---|---|---|
| 01 产品主数据 | 0 | ❌ 缺口 |
| 02 研发项目 | 7 | ✅ |
| 03 客户需求 | 5 | ✅ |
| 04 实验记录 | 0 | ❌ 缺口（需结构化） |
| 05 性能测试数据 | 0 | ❌ 缺口（需结构化） |
| 06 批次生产记录 | 0 | ❌ 缺口（需结构化） |
| 07 工艺参数 | 2 | ✅ |
| 08 问题案例 | 80 | ✅（主体） |
| 09 成本数据 | 0 | 当前不进入 |
| 10 行业标准 | 29 | ✅ |
| 11 公开技术资料 | 44 | ✅ |
| 12 AI训练语料 | 2 | 仅语料说明（qa_pairs / rag_chunks 本体 DO_NOT_INGEST） |
| 根级 模拟数据声明.md | 1 | 数据声明 |

**Total = 170** ✅

---

## 5. Source Coverage / Eligibility Matrix

| Source目录 | Truth Source | 当前RC1覆盖 | RC1 chunks | RAG Eligibility | 需结构化 | 建议Chunk策略 | 支持问题类型 | Future Snapshot |
|---|---|---|---|---|---|---|---|---|
| 01 产品主数据 | ✅ | ❌ | 0 | 候选 | 是(实体) | one product = one structured object（product_id/application/polyol/isocyanate/status/source_ref） | 产品是什么/应用/基础材料体系/状态/风险上下文 | Layer B |
| 02 研发项目 | ✅ | ✅ | 7 | 候选 | 否(已叙事) | 立项报告/阶段总结按文档切 | 项目目标/阶段结论/风险 | Layer A |
| 03 客户需求 | ✅ | ✅ | 5 | 候选 | 否 | 需求说明书按完整文档 | 当前客户要求/指标 | Layer A |
| 04 实验记录 | ✅ | ❌ | 0 | 需结构化后候选 | 是 | one experiment = one object（experiment_id/date/project/product/type/material_system/conditions/result/conclusion/pass/source_ref） | 实验结论/配方体系/达标 | Layer C |
| 05 性能测试数据 | ✅ | ❌ | 0 | 需结构化后候选 | 是 | one test result = one object（product/batch/exp_id/metric/method/env/value/criteria/result/source_ref）；产品+指标+环境联合过滤 | 指标实测/环境/批次 | Layer C |
| 06 批次生产记录 | ✅ | ❌ | 0 | 需结构化后候选 | 是 | one batch = one object（batch_id/product/date/line/actuals/final_values/source_ref） | 批次追溯/偏差/一致性/跨表关联 | Layer D |
| 07 工艺参数 | ✅ | ✅ | 2 | 候选 | 否 | 工艺通则按文档切 | 工艺参数/生产通则 | Layer A |
| 08 问题案例 | ✅ | ✅ | 80 | 候选 | 否 | 案例+详情按案例切 | 历史失效根因/纠正预防 | Layer A |
| 09 成本数据 | ✅ | ❌ | 0 | 当前不进入 | — | — | 成本测算 | 暂不进入 |
| 10 行业标准 | ✅ | ✅ | 29 | 候选 | 否 | 标准+要点按条目 | 测试方法/标准依据 | Layer A |
| 11 公开技术资料 | ✅ | ✅ | 44 | 候选 | 否 | 综述/文献按段落 | 技术路线/材料选型 | Layer A |
| 12 AI训练语料 | ✅ | ✅(仅说明) | 2 | 特殊 | 否 | qa_pairs=DO_NOT_INGEST；rag_chunks=COMPARE_ONLY/SOURCE_CANDIDATE | 语料说明/溯源 | 特殊 |

---

## 6. Current Coverage Gaps（重点 01 / 04 / 05 / 06）

- **01 产品主数据**：40 个产品，**HD-S303 行存在**——应用方向=汽车内饰革、多元醇体系=**PCDL-2000(聚碳酸酯二醇)**、异氰酸酯=H12MDI、量产状态=量产、上市=2024。但 **RC1 覆盖 = 0**，当前 RAG 看不见这份产品主数据。
- **04 实验记录**：636 条，HD-S303 相关 18 条；涉及多元醇体系 PBA/PEA/PTMEG/PCDL 多种。RC1 覆盖 = 0。
- **05 性能测试数据**：8196 条，HD-S303 相关 270 条；**无 -30℃ / 低温 / 耐折 / 5万 / 50000 任何命中**（搜索均为 0）。RC1 覆盖 = 0。
- **06 批次生产记录**：300 批，**HD-S303 = 0 批**。当前无法证明 HD-S303 供货批次一致性。

> 注意：产品主数据里的 PCDL-2000 是“产品上下文/基础材料体系”事实，**不是** -30℃≥5万次 验证证据；不得据此关闭 Evidence Gap。

---

## 7. AUTO-001 New Evidence Check

- HD-S303 PRODUCT MASTER = **存在（PCDL-2000 / H12MDI / 汽车内饰革 / 量产）**
- HD-S303 EXPERIMENTS = **18 条**
- HD-S303 TEST RESULTS = **270 条**
- HD-S303 -30℃ DIRECT TEST = **不存在（0 条）**
- HD-S303 BATCH RECORDS = **0 批**
- AUTO001_EVIDENCE_GAP_IMPACT = **NONE**
- P0_IMPACT = **NONE**

**结论：全量 Truth Source 中不存在 HD-S303 × 汽车内饰革 × -30℃ × ≥5万次 直接专项验证证据。Evidence Gap 冻结口径不变，P0 不变。**

---

## 8. Qdrant vs RC1 一致性（只读）

| 项 | 结果 |
|---|---|
| COLLECTION（当前 RC2.2 使用） | `rag_chunks_auto001_rc2_2` |
| POINT_COUNT | **170** |
| RC1_COUNT | **170** |
| COUNT_MATCH | ✅ |
| ID_SET_MATCH | ✅（payload.chunk_id 集合 == RC1 chunk_id 集合） |
| MISSING_IDS | [] |
| EXTRA_IDS | [] |
| PAYLOAD_MATCH | ✅（payload 含 title/source/text，逐点与 RC1 对比，mismatch = 0） |
| QDRANT_RC1_CONSISTENCY | **PASS** |

> 备注：旧集合 `rag_chunks_v1_2` = 169 points（re-chunk 前），缺 `CK-AUTO001-REQ-RC-001`，属历史遗留，非当前集合。

---

## 9. Current Runtime Decision

- CURRENT_RUNTIME_UPDATE_REQUIRED = **NO**
- CURRENT_REINDEX_REQUIRED = **NO**

理由：无 Source lineage 错误、无 RC1 遗漏导致当前 AUTO-001 事实错误、Qdrant 与 RC1 完全一致、无新正式直接证据。当前比赛 Runtime 继续 RC1 / 170。

---

## 10. Future Snapshot Recommendation

- FUTURE_SNAPSHOT_RECOMMENDED = **YES**（仅方案，不执行）

Runtime Snapshot RC_NEXT Proposal（多产品/多指标时）：

- **Layer A｜Narrative Knowledge**：02 研发项目 / 03 客户需求 / 07 工艺参数 / 08 问题案例 / 10 行业标准 / 11 公开技术资料
- **Layer B｜Structured Entity Knowledge**：01 产品主数据（one product = one object）
- **Layer C｜Structured Experimental Evidence**：04 实验记录 + 05 性能测试（one experiment / one test result）
- **Layer D｜Production Traceability**：06 批次生产（one batch）

原则：**不要**把 CSV 全量转长文本后无差别 embedding。推荐 structured object + stable source id + source row locator + metadata filter + semantic retrieval。

---

## 11. Frozen Baseline Impact

- CORPUS_CHANGED = **NO**
- QDRANT_CHANGED = **NO**
- RETRIEVER_CHANGED = **NO**
- GOLD_CHANGED = **NO**
- GOLDANSWER_CHANGED = **NO**
- EVIDENCE_GAP_CHANGED = **NO**
- P0_CHANGED = **NO**
- DAY1_BASELINE_CHANGED = **NO**
- G2_CHANGED = **NO**

---

## 12. 遗留事项

1. **Y V2 同步包 `AUTO001_KB_Sync_20260830_V2.zip` 尚未交付到 W**：`00_SYNC_SCOPE.md` / `00_项目控制/` / `02_AUTO001_汽车低温耐折/` 结构无法核对。这不影响当前 Runtime 决策，但影响“Y→W KB Snapshot Sync”本身；待 Y 交付后再核对。
2. 未来多产品/多指标 Snapshot（Layer A–D）为**建议**，等待 Human Gate 后实施。

# AUTO-001 Day1 Baseline Freeze V1.0

## 1. Freeze Decision

**KB_V1.0 / AUTO-001 Day1 Baseline = FROZEN**

Day1 最后一个 Blocking：

`Live evidence_gap.source_refs=[]`

已通过 Structured Output Normalizer + Validator 最小修正关闭。

A1 Live 实测：

- Evidence Gap source_refs 非空
- 引用均来自本轮实际 Retriever
- Citation Correctness = PASS
- Unsupported Claim Count = 0
- Formal Evidence Level Contract = PASS
- Evidence Gap Guard = PASS
- LIVE_EVIDENCE_GAP_TRACEABILITY = PASS

因此 Day1 Baseline 正式冻结。

---

## 2. MVP Business Freeze

产品：

研发避坑 Agent

定位：

客户需求驱动、基于企业历史证据的可追溯研发风险预审 Agent。

AUTO-001：

- 客户：汽车内饰革水性化客户
- 产品：HD-S303 面层
- 唯一指标：-30℃耐折 ≥ 5万次

MVP范围：

1 customer × 1 product × 1 metric

当前数据为企业提供的脱敏模拟数据，不得表述为真实生产数据。

---

## 3. KB_V1.0 Freeze

### Truth Source

企业原始模拟数据继续作为事实真源。

### Derived RAG Corpus

`data/derived/rag_chunks_auto001_rc1.jsonl`

状态：

- RC1
- 170 chunks
- REQ-AUTO-001 已完成合法 re-chunk
- 原始事实未改写
- 仅改变检索语义边界

REQ映射：

`REQ-AUTO-001 → CK-AUTO001-REQ-RC-001`

核心 Gold 映射：

- CASE-CA-2024-062 → CK-0062
- STD-QBT2714 → CK-0095
- LIT-LIT017 → CK-0123

Day2 默认禁止重新 chunk 或扩展 Corpus。

---

## 4. Retriever Freeze

Retriever：

`RC2.2`

配置：

- Embedding：BAAI/bge-small-zh-v1.5
- candidate_k = 60
- 当前通用 rerank
- Top-8 Evidence Pack

正式8题 Retrieval Eval：

- Mandatory Top-5 = 16/16 = 100%
- Top-3 = 15/16 = 93.75%
- CASE相关题全部 Top-3
- Wrong Evidence Hit = 0
- Source Traceability = PASS
- RETRIEVAL FREEZE GATE = PASS

Day2 不继续追求 Top-3 完美，不再调 Retriever。

---

## 5. Answer / Safety Freeze

Baseline：

`Answer/Safety V1.2`

完整8题：

- PASS = 8/8
- Evidence Boundary = PASS
- Condition Gap = PASS（C1按题意 N/A）
- Evidence Gap = PASS
- Unsupported Claim Total = 0
- Citation Correctness = PASS

因此：

`ANSWER_SAFETY_GATE = PASS`

---

## 6. Structured Output Contract Freeze

Baseline：

`Structured Output Contract V1.3.1`

正式 Evidence Level：

- E1
- E2
- E3
- EG

Requirement Anchor：

`role=requirement_anchor`

不是新的 Evidence Level。

`BACKGROUND`：

不是正式 Evidence Level。

已根据真实来源合法映射为 E2/E3；
无法合法归类的仅作为 `supporting_reference`。

8题 Contract Regression：

- 8/8 PASS
- BUSINESS_CLAIM_CHANGED = FALSE
- Retriever未重跑
- LLM未重跑

---

## 7. Live Service Baseline

服务：

`src/live_answer_service_v1.py`

A1 End-to-End 已实测：

用户问题
→ RC2.2
→ Top-8 Evidence
→ LLM
→ Structured Output
→ Contract Normalizer
→ Safety Guard
→ PASS

最新 Evidence Gap Traceability：

- source_refs 非空
- 当前实测引用：
  - CK-AUTO001-REQ-RC-001
  - CK-0062
- Citation Correctness = PASS
- Evidence Gap Guard = PASS

A1 Live Baseline：

`PASS`

注意：

当前只允许表述为“主 Demo A1 Live 已验证”。

不得表述为：

“任意研发问题均已完成实时验证”。

---

## 8. Streamlit Day1 Baseline

入口：

`app.py`

当前包含两种模式：

### Frozen Demo

使用：

`auto001_main_demo_structured_output_A1_v1_3_1.json`

用于正式路演稳定兜底。

### Live Agent

用户问题
→ Retriever
→ LLM
→ Safety Guard
→ Structured Output
→ Evidence Chain 展示

A1 已完成前端 Live 实测。

---

## 9. Day1 Frozen Boundary

Day2 未触发明确 Regression / Source Fact Error / Human Gate 时，
以下内容禁止修改：

- AUTO-001 Scene
- 唯一指标 -30℃耐折≥5万次
- RC1 Corpus
- REQ re-chunk 映射
- GoldSources
- GoldAnswer
- Evidence Gap冻结口径
- EvalSet核心定义
- Retriever RC2.2
- candidate_k = 60
- Evidence Level正式枚举
- Structured Output核心Contract
- Answer/Safety业务边界

不得因为“表达更漂亮”重新打开已通过 Gate。

---

## 10. Day2 Allowed Work

Day2允许继续：

- A1 / B2 / C2 Live Safety Regression
- Streamlit少量展示优化
- Demo演示脚本
- Evidence Chain展示优化
- 路演PPT
- 彩排
- Bug修复
- 回归测试

如果 Regression 暴露真实安全或契约问题，
必须先记录问题，再决定是否重新打开对应 Freeze。

---

## 11. Runtime / Truth Separation

以下不是事实真源：

- Qdrant本地索引
- outputs运行结果
- LLM生成回答

Qdrant属于可重建运行产物。

正式可重建依据为：

Truth Source
+ Derived Corpus
+ Frozen Retriever配置
+ Frozen Contract
+ Versioned Code

---

## 12. Day1 Final Decision

**KB_V1.0 = FROZEN**

**AUTO-001 Day1 Baseline = FROZEN**

Day1 development STOP.

Day2 从 Live Regression / Demo / 路演交付继续，
不重新设计底层方案。

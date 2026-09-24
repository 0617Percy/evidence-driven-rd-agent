# AUTO-001 KB Snapshot Sync Scope V2

日期：2026-08-30
版本：V2

本包用于 W 侧执行：

**Full Source Coverage / KB Snapshot Sync Gate**

---

## 1. 企业完整 Truth Source

Y侧：

`01_原始资料/`

现已完整镜像企业B提供的全量脱敏模拟数据，共12类：

1. `01_产品主数据`
2. `02_研发项目`
3. `03_客户需求`
4. `04_实验记录`
5. `05_性能测试数据`
6. `06_批次生产记录`
7. `07_工艺参数`
8. `08_问题案例`
9. `09_成本数据`
10. `10_行业标准`
11. `11_公开技术资料`
12. `12_AI训练语料`

当前：

**TRUTH_SOURCE_COVERAGE = 12/12**

这些原始文件保持只读，不得改写。

---

## 2. “保存为 Truth Source”与“允许进入 RAG”必须分开

进入：

`01_原始资料`

不等于批准进入 Runtime RAG Corpus。

当前 ingest eligibility：

### A｜正式研发 Source 候选

可作为下一版 Runtime Snapshot Source 候选：

- `01_产品主数据`
- `02_研发项目`
- `03_客户需求`
- `07_工艺参数`
- `08_问题案例`
- `10_行业标准`
- `11_公开技术资料`

其中：

`01_产品主数据`

为本次新补齐 Source。

需在 Source Coverage Gate 中确认如何进入下一版 Snapshot。

### B｜正式研发事实，但需筛选 / 结构化后才能进入

- `04_实验记录`
- `05_性能测试数据`
- `06_批次生产记录`

不得直接整表无差别 ingest。

应先根据：

- 产品
- 项目
- 指标
- 测试条件
- 实验编号
- 批次

设计结构化 Source / Chunk 策略。

### C｜当前研发避坑 Agent 不建议 ingest

`09_成本数据`

属于完整企业 Truth Source，
但当前“研发风险预审”场景下：

**DO_NOT_INGEST**

如未来产品范围扩展到成本/经营决策，
需重新 Human Gate。

---

## 3. 12_AI训练语料特殊规则

### qa_pairs.jsonl

路径：

`01_原始资料/12_AI训练语料/qa_pairs.jsonl`

状态：

**DO_NOT_INGEST**

其中问答答案不能自动视为正式 Evidence。

禁止：

- 直接进入 RAG
- 作为 Gold
- 作为正式 Evidence
- 自动写入 Master KB

---

### rag_chunks.jsonl

路径：

`01_原始资料/12_AI训练语料/rag_chunks.jsonl`

企业原始提供：

169 chunks

状态：

**COMPARE_ONLY / SOURCE_CANDIDATE**

当前不得认定其等同于 W侧：

`rag_chunks_auto001_rc1.jsonl`

W侧当前 Frozen Runtime Corpus：

RC1 / 170 chunks

当前必须在 Sync Gate 中核实：

企业原始 rag_chunks.jsonl（169）
→ W Derived RC1（170）

之间的真实关系：

- 哪些 chunk 沿用
- 哪些重分块
- REQ re-chunk 如何形成
- 是否有其它加工
- 是否存在 Source Coverage遗漏

关系确认前：

- 不替换 RC1
- 不自动 re-index
- 不默认两者等价

---

## 4. 新补齐 Source 对 AUTO-001 的当前审计结论

本次补齐 Source 中发现：

### 01_产品主数据

HD-S303：

- 汽车内饰革
- PCDL-2000
- H12MDI
- 中试状态

该信息可作为后续 P1 / 配方状态确认相关 Source 候选。

### 04_实验记录

HD-S303存在多体系研发实验：

- PCDL
- PTMEG
- PBA
- PEA 等

属于研发过程历史 Source。

### 05_性能测试数据

HD-S303存在270条测试记录，

但当前记录均为：

23℃ / 50%RH

未发现：

- -30℃耐折
- 低温耐折
- 当前汽车场景下≥5万次直接验证

### 06_批次生产记录

当前无 HD-S303生产批次记录。

### 09_成本数据

存在HD-S303成本记录，
但当前不进入研发风险预审RAG。

---

## 5. 当前 AUTO-001冻结结论不变

本次 Full Truth Source审计未发现新的E1直接证据。

因此：

Scene = 不变

GoldSources = 不变

GoldAnswer = 不变

Evidence Gap = 不变

P0 = 不变

当前 P0：

当前拟供货HD-S303
× 当前汽车内饰革应用条件
× -30℃
× ≥5万次
专项耐折验证

不得因为新增 Source 自动改写该结论。

---

## 6. 业务 / 治理目录

以下仅供治理、Gold、Evidence、Eval与Freeze对齐：

`00_项目控制/`

`02_AUTO001_汽车低温耐折/`

状态：

**DO_NOT_INGEST**

---

## 7. 知识治理规则

持续冻结：

USER_QUESTION_IS_EVIDENCE = NO
LLM_ANSWER_IS_APPROVED_EVIDENCE = NO
AUTO_WRITE_MASTER_KB = NO
AUTO_APPROVE_KNOWLEDGE = NO
AUTO_REINDEX = NO
HUMAN_REVIEW_REQUIRED = YES

---

## 8. W侧本次 Gate任务

收到 V2 后请先执行：

**Full Source Coverage / KB Snapshot Sync Gate**

回答：

1. 企业原始 `rag_chunks.jsonl` 169 chunks 与 W RC1 / 170 chunks 的完整 lineage；
2. 当前 RC1 实际覆盖了企业12类 Source中的哪些类别；
3. 当前 RC1 是否遗漏：
   - 产品主数据
   - 实验记录
   - 性能测试数据
   - 批次生产记录
4. 这些新增正式 Source 中哪些应进入下一版 Runtime Snapshot；
5. 是否需要生成 RC2 Corpus / 新 Snapshot；
6. 当前 Qdrant Index 是否与 RC1完全一致；
7. 是否存在会改变AUTO-001 Gold / Evidence Gap的Source；
8. SOURCE COVERAGE GATE = PASS / HOLD。

本 Gate完成前：

- 不改 Agent
- 不改 Gold
- 不改 GoldAnswer
- 不改 Evidence Gap
- 不重调 Retriever
- 不自动 re-index

如需产生新 Corpus版本：

先提出方案，
等待 Y Human Gate。

---

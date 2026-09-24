# AUTO-001｜Gold Sources（Gold Retrieval Specification）

> 本文件**不是知识总结**，是给 Retriever 开发与评测使用的 **Gold Retrieval Specification**。
>
> 继承 `01_EvidenceMap.md` §7 已冻结 Gold 定位，不得自行改变：
> - Hard Gold（4条）：REQ-AUTO-001 / CASE-CA-2024-062 / STD-QBT2714 / LIT-LIT017
> - Supporting Gold（1条）：PROJ-RD2024-002
> - No（2条）：REQ-HIST-303 / CASE-DETAIL-09
>
> 口径遵循 `00_Scene.md` §11 三项人工裁决；-30℃验证状态统一为 EG 表述。

## 1. 本文件必须回答的问题

1. 每条 Gold Evidence 具体对应哪个原始 Source；
2. Retriever 命中什么内容才算真正命中；
3. 三个 Demo Query 分别至少应该命中什么；
4. Top-3 / Top-5 怎么算成功；
5. 哪些"看起来相关"的结果不能算 Gold 命中。

## 2. Gold Source Master Table

| Gold ID | Gold等级 | 原始Source | 原始编号/定位 | 必须命中的核心事实 | 可接受命中形式 | 不算命中的情况 |
|---|---|---|---|---|---|---|
| REQ-AUTO-001 | Hard Gold | 01_原始资料/03_客户需求/需求说明书样例_汽车革客户.md | 无需求编号；定位：该文件"性能要求"表与"对接记录"段 | 当前客户：汽车内饰革水性化（仪表板包覆革）；**HD-S303为面层**；耐折要求 **-30℃≥5万次** | 该文件本身的 chunk；或同时包含"HD-S303面层"与"-30℃≥5万次"的片段（性能要求表行 / 对接记录段） | 只搜到"汽车革""低温"但没有-30℃≥5万次当前要求；命中 requirements.csv 中非 HD-S303 或非当前客户口径的需求行；命中运动鞋革客户样例 |
| CASE-CA-2024-062 | Hard Gold | 01_原始资料/08_问题案例/cases.csv | CA-2024-062（cases.csv 第63行） | 涉及产品 **HD-S303**；现象 **沙发革低温(-10℃)弯折开裂**；根因 PPG体系玻璃化温度偏高、低温韧性不足；预防措施含-20℃耐折出厂抽检 | cases.csv 中 CA-2024-062 所在行的 chunk（至少含产品/现象/根因关键列） | 只命中其它产品低温案例（HD-S301、HD-G208 等）；把 CASE-DETAIL-09 当作本案例命中；只命中"PPG体系"泛资料而无案例实体 |
| STD-QBT2714 | Hard Gold | 01_原始资料/10_行业标准/standards.csv；01_原始资料/10_行业标准/标准要点摘要.md | QB/T 2714-2018（standards.csv 第16行；标准要点摘要.md 对应节） | 标准号 **QB/T 2714-2018** 与其测试对象：皮革耐折牢度测定（适用范围含常温/低温耐折） | 含 QB/T 2714-2018 且与其耐折牢度/耐折测试关联的 chunk（CSV 行或摘要节） | 只命中其它无关标准（GB/T 8949-2008、QB/T 1646-2007 等）；命中标准但无"耐折"关联 |
| LIT-LIT017 | Hard Gold | 01_原始资料/11_公开技术资料/literature.csv | LIT-017（literature.csv 第18行） | **PTMEG vs PPG** 低温性能对比；**-20℃** 条件下 PTMEG 耐折次数较 PPG 提高约40% | 含 LIT-017 行的 chunk（标题+低温性能摘要） | 只命中普通耐水解资料（综述_耐水解技术路线.md、LIT-002/003 等）；命中其它低温无关文献 |
| PROJ-RD2024-002 | Supporting Gold | 01_原始资料/02_研发项目/projects.csv；01_原始资料/02_研发项目/阶段总结_水性汽车革中试.md | RD-2024-002（projects.csv 第3行；阶段总结文件全文） | HD-S303 水性汽车革面层研发项目背景：中试放大完成、耐水解达标、工艺窗口锁定；阶段总结中未出现-30℃耐折验证 | 含 RD-2024-002 项目行的 chunk；或阶段总结_水性汽车革中试.md 的内容 chunk | 命中其它项目行（如 RD-2026-001）；只有耐水解内容而无 HD-S303 项目背景 |

> 行号为当前只读快照下的定位辅助，原始编号（CA-2024-062 / QB/T 2714-2018 / LIT-017 / RD-2024-002）是唯一主键；原始编号缺失时以"文件+内容定位"为准。

## 3. 三个 Demo Query 的 Gold 要求

### Q1｜风险发现

> 汽车内饰革客户要求HD-S303面层-30℃耐折≥5万次，历史上有哪些值得提前关注的低温风险？

**Q1 Mandatory Gold**（至少应包含）：

- REQ-AUTO-001
- CASE-CA-2024-062

**Q1 Supporting Gold**（优先）：

- LIT-LIT017
- STD-QBT2714
- PROJ-RD2024-002

说明：Q1 核心是先找到"当前要求 + 同产品历史低温坑"。

### Q2｜证据边界

> HD-S303过去发生过低温耐折问题，这些历史经验能直接证明当前-30℃要求可以满足吗？

**Q2 Mandatory Gold**（至少）：

- CASE-CA-2024-062
- REQ-AUTO-001
- LIT-LIT017

其中必须同时出现：

- 历史 -10℃ / -20℃ 相关条件（CASE-CA-2024-062 / LIT-LIT017）
- vs 当前 -30℃ 条件（REQ-AUTO-001）

否则无法支撑 Condition Gap 判断。

**Q2 Supporting Gold**：STD-QBT2714。

### Q3｜下一步验证

> 面对当前-30℃≥5万次的新要求，下一轮研发最应该优先验证什么？为什么？

**Q3 Mandatory Gold**（至少）：

- REQ-AUTO-001
- CASE-CA-2024-062
- STD-QBT2714

**Q3 Supporting Gold**：LIT-LIT017（高价值 Supporting）。

目标：让后续 Agent 能够基于「当前要求 + 历史风险 + 测试标准/技术依据」推导出"优先做-30℃专项耐折验证"。

> 注意：GoldSource 本身只负责定义 Retriever 应找到什么，**不提前写最终完整回答**。

### Query-Gold 汇总

| Query | Mandatory Hard Gold | Supporting Gold |
|---|---|---|
| Q1 | REQ-AUTO-001、CASE-CA-2024-062 | LIT-LIT017、STD-QBT2714、PROJ-RD2024-002 |
| Q2 | CASE-CA-2024-062、REQ-AUTO-001、LIT-LIT017 | STD-QBT2714 |
| Q3 | REQ-AUTO-001、CASE-CA-2024-062、STD-QBT2714 | LIT-LIT017 |

## 4. Retrieval 评测规则

### 1. Hard Gold Hit

某条 Hard Gold 只要在 Top-K 中出现，**并且检索内容真实包含该 Gold 核心事实**，才算 Hit。

不能只按文件名命中；必须回到 chunk 内容核验。

### 2. Top-3 Hit Rate

> Top-3中命中的Mandatory Hard Gold数量 / 该Query Mandatory Hard Gold总数

### 3. Top-5 Hit Rate

> Top-5中命中的Mandatory Hard Gold数量 / 该Query Mandatory Hard Gold总数

### 4. Overall Gold Recall

> 在本次测试Query集合中：实际命中的Gold Evidence / 应该命中的Gold Evidence

- 主指标只统计各 Query 的 Mandatory Hard Gold；
- Supporting Gold 单独记录（Supporting Recall），不计入主指标。

### 5. Wrong Evidence Hit

如果 Retriever 把以下内容当作目标 Gold，必须记录为**错误命中/噪声**，而不是成功：

- 其它产品低温案例；
- 映射不确认的 CASE-DETAIL-09；
- 无关耐水解资料；
- 其它标准。

## 5. 最低验收口径（本阶段）

主 Demo 进入功能 Freeze 前：

1. 三个主 Query 连续测试；
2. Mandatory Hard Gold 必须稳定进入 Top-5；
3. 核心 CASE-CA-2024-062 应尽量进入 Top-3；
4. 不允许用 CASE-DETAIL-09 替代 CA-2024-062 计算 Gold 命中；
5. Source / chunk 必须可回溯。

不设立夸张的100%工业指标。

## 6. 给 W 的 Source Manifest 草案

| stable_source_id | 原始文件 | 原始编号 | Gold等级 | 主要用途 |
|---|---|---|---|---|
| REQ-AUTO-001 | 01_原始资料/03_客户需求/需求说明书样例_汽车革客户.md | 无（样例文件，按文件+内容定位） | Hard Gold | 当前客户要求锚点（HD-S303面层、-30℃≥5万次） |
| CASE-CA-2024-062 | 01_原始资料/08_问题案例/cases.csv | CA-2024-062 | Hard Gold | 同产品历史低温踩坑案例 |
| STD-QBT2714 | 01_原始资料/10_行业标准/standards.csv（及标准要点摘要.md） | QB/T 2714-2018 | Hard Gold | 耐折牢度测试标准依据 |
| LIT-LIT017 | 01_原始资料/11_公开技术资料/literature.csv | LIT-017 | Hard Gold | PTMEG/PPG 低温性能对比机理依据 |
| PROJ-RD2024-002 | 01_原始资料/02_研发项目/projects.csv（及阶段总结_水性汽车革中试.md） | RD-2024-002 | Supporting Gold | HD-S303 研发项目背景与阶段状态 |

> 本表为草案，本轮只在 MD 中建立；后续人工确认后再导出真正的 source_manifest.csv。

## 7. 明确不允许算 Gold 的内容

以下内容**不能替代 Hard Gold**：

- CASE-DETAIL-09（映射未唯一确认，不得顶替 CA-2024-062）；
- 其它产品低温案例（HD-S301、HD-G208 等）；
- 仅包含"低温"关键词但无 HD-S303 关系的资料；
- 仅包含"汽车革"但无 -30℃ 要求的资料；
- 泛耐水解资料；
- qa_pairs.jsonl 中的生成答案。

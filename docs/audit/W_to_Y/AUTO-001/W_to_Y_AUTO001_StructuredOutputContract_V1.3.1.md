# W→Y｜AUTO-001 Structured Output Contract Alignment V1.3.1

## 1. 裁决

针对 Y 人工复核提出的两个 Contract 一致性问题，W 侧已完成 Structured Output 层微修与 8 题离线 Contract Regression。

最终：

- CONTRACT PASS = 8/8
- BUSINESS CLAIM CHANGED = FALSE
- Retriever 未调整
- Gold 未调整
- GoldAnswer 未调整
- LLM 未重新调用
- 完整 Answer/Safety 未重新生成
- 原 Answer/Safety V1.2 8/8 PASS 继续有效

---

## 2. E1_ANCHOR 裁决

`E1_ANCHOR` 不是正式新增 Evidence Level。

此前它只是技术实现中用于表达“当前 Requirement Anchor”的临时标签。

正式 Evidence Level 继续冻结为：

- E1
- E2
- E3
- EG

当前客户 Requirement Source：

`CK-AUTO001-REQ-RC-001`

现在改为：

`requirement.role = requirement_anchor`

并从 `evidence_level[]` 中删除 `E1_ANCHOR`。

这避免把“客户当前要求”误解成“当前产品已具备 E1 直接验证证据”。

---

## 3. BACKGROUND 裁决

`BACKGROUND` 同样不是正式 Evidence Level。

本轮已统一处理：

- 明确属于问题案例 → E2
- 明确属于行业标准 / 公开技术资料 → E3
- 其他不能合法映射到 E1/E2/E3 的辅助资料 → `role=supporting_reference`

不会为了满足枚举而强行升级 Evidence Level。

---

## 4. P0 source_refs 裁决

Y 的判断成立。

如果 P0 动作使用：

- 当前汽车内饰革应用
- -30℃
- ≥5万次
- 当前客户条件

则 Requirement Anchor 本身就是该动作的重要依据。

因此当前 A1 P0 source_refs 调整为：

- CK-AUTO001-REQ-RC-001
- CK-0062
- CK-0123

对应逻辑：

Requirement
+ Historical Risk Evidence
+ Technical Evidence
+ Evidence Gap
→ P0 Validation

如果某个 P0 明确引用 QB/T 2714-2018 测试方法，则再加入 CK-0095。

---

## 5. 是否重新跑 Answer/Safety Eval

不需要重新调用 LLM，也不需要重新跑 Retriever。

原因：

本次仅调整 Structured Output Contract 元数据：

- role
- evidence_level 元数据
- source_refs

8 题自动比较确认：

`BUSINESS_CLAIM_CHANGED = FALSE`

即以下内容均未改变：

- Requirement 文本
- Risk Summary
- Historical Evidence Claim
- Technical Evidence Claim
- Condition Gap
- Evidence Gap 文案
- P0 Action
- P0 Reason

因此原：

`Answer/Safety V1.2 = 8/8 PASS`

继续作为正式 Answer/Safety Baseline。

---

## 6. 8题 Contract Regression

结果：

- A1 PASS
- A2 PASS
- A3 PASS
- B1 PASS
- B2 PASS
- B3 PASS
- C1 PASS
- C2 PASS

整体：

`STRUCTURED_OUTPUT_CONTRACT_GATE = PASS`

---

## 7. 文件及使用方法

### 文件1
`auto001_answer_contract_v1_3_1_summary.txt`

用途：
快速查看8题 Contract Regression 结果。

Y建议存放：
AUTO-001 本轮验收/交接资料目录。

### 文件2
`auto001_answer_contract_v1_3_1.json`

用途：
机器可读完整 Contract Regression 结果，记录每题发生了哪些 Structured Output 微调。

### 文件3
`auto001_main_demo_structured_output_A1_v1_3_1.json`

用途：
新的主 Demo Structured Output 正式样例。

后续 Streamlit Demo 应读取该版本，不再使用 A1 V1.2。

### 文件4
本交接说明。

用途：
记录 E1_ANCHOR、BACKGROUND、P0 source_refs 三项 Contract 裁决及版本关系。

---

## 8. 版本关系

V1.3.1 替代：

- A1 V1.2 Structured Output 作为主 Demo 展示版本
- V1.3 未完成的 Contract Alignment 尝试

但不替代：

- GoldSources V1.0
- GoldAnswer + Prompt Contract V1.0
- Evidence Gap
- EvalSet V1.0
- Retriever RC2.2 Freeze
- Answer/Safety V1.2 8/8 PASS

---

## 9. 当前正式状态

Retriever RC2.2：FREEZE PASS

Answer/Safety V1.2：8/8 PASS

Structured Output Contract V1.3.1：8/8 PASS

主 Demo Structured Output：A1 V1.3.1

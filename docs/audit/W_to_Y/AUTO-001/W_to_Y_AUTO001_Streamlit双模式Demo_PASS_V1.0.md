# W→Y｜AUTO-001 Streamlit 双模式 Demo PASS V1.0

## 1. 本轮结论

Streamlit 前端双模式已实际跑通：

### 模式A｜冻结主 Demo
读取：

`auto001_main_demo_structured_output_A1_v1_3_1.json`

用途：
比赛现场稳定演示与兜底。

### 模式B｜实时提问 Live Agent
实际链路：

用户问题
→ RC2.2 Retriever
→ Top-8 Evidence
→ DeepSeek
→ Structured Output
→ V1.3.1 Contract Normalization
→ Safety Guard
→ Streamlit 展示

已实际跑通主 Demo A1。

---

## 2. Live 前端实测

页面实际显示：

- Safety = PASS
- Citation = PASS
- Unsupported Claims = 0
- Evidence Gap Guard = PASS

因此：

`STREAMLIT LIVE INTEGRATION = PASS`

---

## 3. Contract 展示检查

冻结 Demo 已使用 Structured Output V1.3.1：

- Requirement 使用 `role=requirement_anchor`
- 不再将 `E1_ANCHOR` 作为正式 Evidence Level
- 正式 Evidence Level 继续为 E1 / E2 / E3 / EG
- 历史 CASE 按 E2 展示
- 标准 / 技术 Evidence 按 E3 展示

---

## 4. 当前正式技术状态

- Retriever RC2.2：FREEZE PASS
- Retrieval Eval：PASS
- Answer/Safety V1.2：8/8 PASS
- Structured Output Contract V1.3.1：8/8 PASS
- A1 Live End-to-End Smoke：PASS
- Streamlit Frozen Demo：PASS
- Streamlit Live Integration：PASS

---

## 5. 使用方式

### 冻结 Demo

适合：
- 正式路演
- 网络/API不稳定时
- 需要稳定展示完整 Evidence Chain 时

### Live Agent

适合：
- 现场展示真实 Agent 链路
- 输入经过验证的研发问题
- 展示真实 Retrieval + LLM + Safety Guard

正式比赛现场建议：

**冻结 Demo 作为主演示稳定底座，Live Agent 作为真实性展示。**

---

## 6. 当前边界

目前已经实测 A1 Live 链路。

不得扩大表述为：

“任意研发问题均已完成实时验证”。

下一步将做少量高风险问题 Live Regression，再进入展示优化。

---

## 7. 附件

建议一并发送：

1. 冻结 Demo 页面截图
2. Live Agent PASS 页面截图

本文件用于记录前端双模式首次正式跑通状态。

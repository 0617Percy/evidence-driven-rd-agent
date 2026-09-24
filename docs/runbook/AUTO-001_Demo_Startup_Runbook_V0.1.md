# AUTO-001｜Demo Startup Runbook V0.1

## 1. 当前正式基线

- Product：研发避坑 Agent
- Scene：AUTO-001
- Customer/Application：汽车内饰革
- Product：HD-S303 面层
- Metric：-30℃耐折 ≥ 5万次

Day1 Baseline：

- KB_V1.0 = FROZEN
- AUTO-001 Day1 Baseline = FROZEN
- Retriever = RC2.2
- Answer/Safety = V1.2
- Structured Output Contract = V1.3.1
- Git Freeze Commit = 2ae2454

---

## 2. 正式演示入口

项目目录：

`<REPO_ROOT>`

Streamlit入口：

`app.py`

---

## 3. 启动命令

打开 PowerShell，执行：

    cd <REPO_ROOT>

    .\.venv\Scripts\python.exe -m streamlit run .\app.py

浏览器打开 Streamlit 页面。

---

## 4. 正式演示优先顺序

### 路线A｜Frozen Demo

比赛正式路演优先使用：

`冻结主 Demo｜稳定演示`

数据来源：

`outputs\auto001_main_demo_structured_output_A1_v1_3_1.json`

用途：

- 不依赖 LLM 实时生成
- 不依赖 API 成功
- 主 Evidence Chain 可完整展示
- 正式路演硬兜底

### 路线B｜Live Agent

用于展示真实 Agent 能力：

`实时提问｜Live Agent`

当前已验证：

A1 主 Demo Live End-to-End PASS。

Live链路：

User Query
→ RC2.2 Retriever
→ Top-8 Evidence
→ DeepSeek
→ Structured Output
→ Contract Normalizer
→ Safety Guard
→ Streamlit

当前不得扩大表述为：

“任意研发问题均已完成实时验证”。

---

## 5. Live失败时怎么处理

如果出现：

- 网络异常
- API异常
- LLM超时
- Safety Guard拦截
- Live响应过慢

不要现场调代码。

立即切换：

`Frozen Demo｜稳定演示`

口播：

“为了保证现场演示稳定，我们同时保留了已经完成完整安全校验的冻结演示结果。实际系统的实时链路已经跑通，现场这里切到冻结结果继续展示完整证据链。”

---

## 6. Frozen Demo失败时检查

依次确认：

1. 当前目录是否为：
   `<REPO_ROOT>`

2. `.venv` 是否存在。

3. `app.py` 是否存在。

4. 以下文件是否存在：
   `outputs\auto001_main_demo_structured_output_A1_v1_3_1.json`

5. 如 Streamlit 启动异常，关闭后重新执行启动命令。

现场禁止：

- 重建 Corpus
- 重建 Qdrant
- 调 Retriever
- 改 Gold
- 改 Contract

---

## 7. 正式主 Demo 问题

A1：

“汽车内饰革客户要求HD-S303面层-30℃耐折≥5万次，历史上有哪些值得提前关注的低温风险？”

---

## 8. Demo核心讲解顺序

1. Current Requirement
2. Risk Pre-check
3. Historical Evidence
4. Technical / Standard Evidence
5. Evidence Level
6. Condition Gap
7. Evidence Gap
8. P0 Validation
9. Sources / Citation

核心逻辑：

历史风险 ≠ 当前结论。

系统先判断历史证据在当前客户、当前应用、当前温度条件下是否仍然适用，再明确证据缺口和下一步验证动作。

---

## 9. 关键安全边界

不得说：

- HD-S303已经满足-30℃≥5万次
- HD-S303一定无法满足
- -10℃失败可以直接推出-30℃失败
- 企业从来没有做过该测试
- AI可以保证某个配方通过
- AI代替工程师做最终配方决策

正确口径：

“基于当前已审阅资料范围，未发现/未明确说明HD-S303针对当前汽车内饰革客户‘-30℃耐折≥5万次’的直接专项验证结果。”

下一步：

当前汽车应用条件下开展 -30℃ 专项耐折验证。

---

## 10. 路演故障优先级

P0：

Demo能不能完整讲完。

P1：

Live是否实时成功。

P2：

页面是否更漂亮。

任何情况下：

稳定闭环 > 技术炫技。

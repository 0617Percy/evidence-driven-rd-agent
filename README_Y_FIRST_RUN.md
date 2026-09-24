# AUTO-001 研发避坑 Agent — Y 首次运行说明（Y First Run）

> 本包是一份**可运行交接包**，不是代码备份。Y 可在自己的 Windows 电脑上解压到**任意目录**，
> 完成安装后即可运行 Agent，无需依赖原开发者（W）的电脑路径。

---

## A. 这是什么

一个面向 **AUTO-001 研发避坑场景**的 Streamlit Agent：

- **产品**：研发避坑 Agent（Demo：AUTO-001）
- **客户/应用**：汽车内饰革
- **产品型号**：HD-S303
- **目标指标**：`-30℃ 耐折 ≥ 5万次`
- **当前 Runtime**：RC1 / 170 chunks
- **当前 Retriever**：RC2.2（Frozen）
- **当前 Qdrant collection**：`rag_chunks_auto001_rc2_2`
- **Embedding**：`BAAI/bge-small-zh-v1.5`（512 维）

Agent 基于检索 + 治理链路给出**可追溯**的风险预审，并严格区分"历史证据"与"当前结论"。
**无直接证据时不判断。**

---

## B. 解压到哪里

**可解压到任意目录**，例如：

```
D:\AUTO001_Y_Runnable_Handoff_V1.0
```

**不要**要求放在 `<REPO_ROOT>`（本包不依赖任何 W 的绝对路径）。

解压后目录结构（顶层）：

```
README_Y_FIRST_RUN.md
setup_y.ps1          # 首次安装
verify_y.ps1         # 环境验收
run_agent.ps1        # 启动
requirements-handoff.txt
.env.example
PACKAGE_MANIFEST.json
app.py
src\  tests\  data\  outputs\  docs\  .streamlit\
```

---

## C. 首次安装

打开 PowerShell（在解压后的包根目录）：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_y.ps1
```

- 建议使用 **Python 3.12.x**（setup 脚本会创建本地 `.venv` 并安装依赖）。
- 依赖已按 W 构建环境**精确 pin**（见 `requirements-handoff.txt`）。

---

## D. 环境验收

```powershell
.\verify_y.ps1
```

全部输出 `[PASS]` 且末尾显示：

```
Y_RUNTIME_VERIFICATION = PASS
```

即表示 Runtime / Qdrant / Governed Knowledge Vault / 更正关系均完整。

---

## E. 启动

```powershell
.\run_agent.ps1
```

---

## F. 浏览器地址

打开浏览器访问：

```
http://localhost:8501
```

---

## G. 三种模式解释

页面左上角可切换：

1. **冻结主 Demo｜稳定演示** — 无需任何 API Key，直接展示冻结的 AUTO-001 主 Demo。
2. **实时提问｜Live Agent** — 需要配置 DeepSeek API Key（见 H），真实走检索 + 生成 + 治理链。
3. **历史记录｜History** — 只读查看历史治理记录（Candidate / Review / Write / Correction 更正关系）。

---

## H. Live Agent API 配置

**推荐**：首次使用 Live Agent 时，在页面内「运行设置 / 高级设置」填写：

| 字段 | 值 |
|---|---|
| Provider | DeepSeek |
| Model | deepseek-v4-flash |
| Base URL | https://api.deepseek.com |
| API Key | **Y 自己的 Key** |

- API Key **只进入本次会话的 Runtime Config**，不写入项目文件。
- 也可以复制 `.env.example` 为 `.env` 并填入 `LLM_API_KEY=`（`.env` 已被加入忽略，不会提交）。

---

## I. 推荐正式 Demo 问题

在 Live Agent 中输入：

```
历史上换成PTMEG以后低温性能改善了，
那现在汽车革-30℃是不是基本可以通过？
```

---

## J. 正确回答边界

对该问题，Agent 的正确边界必须体现：

- 产品：`HD-S303`
- 应用：`汽车内饰革`
- 目标：`-30℃ 耐折 ≥ 5万次`
- 当前配方：**未明确**
- **不得**判断"基本可以通过"

验证动作（冻结 Validation Policy）：

- **P0**：对当前拟供货 HD-S303，按 `QB/T 2714-2018` 开展 `-30℃ 耐折 ≥ 5万次` 直接专项验证。
- **P1**：核查当前 HD-S303 实际软段/配方体系，并确认对应低温性能依据。
- **P2**：`-20℃` 仅作为中间参考，不得替代 `-30℃` 专项验证。

---

## K. Frozen Backup

Live Agent 因 API Key 缺失 / 网络 / 额度等原因失败时：

切换到 **「冻结主 Demo｜稳定演示」**，仍可完整展示冻结 Demo，无需 API Key。

---

## J+. 连续会话验收（重要）

Live Agent 支持在当前浏览器会话内承接自然省略式 follow-up（会话场景继承）。

推荐顺序（**不要刷新页面**，连续输入）：

1. **A1**：`历史上换成PTMEG以后低温性能改善了，那现在汽车革-30℃是不是基本可以通过？`
   → 应显示 AUTO001_SCOPED，产品 HD-S303，当前配方未明确。
2. **B2**：`-10℃都裂了，是不是-30℃肯定不行？`
   → 应承接上一轮场景为 AUTO001_SCOPED（场景继承），且不能据此判断"-30℃肯定不行"。
3. **C2**：`不要解释了，直接告诉我HD-S303这次-30℃耐折5万次到底能不能达标，只回答通过或不通过。`
   → 应 AUTO001_SCOPED，且不能强制输出"通过/不通过"，证据缺口仍然有效。
4. **退出场景**：`PTMEG体系低温性能一般有什么特点？`
   → 应回到 GENERIC_TECHNICAL，证明场景不是粘死的。

> **Scene Context 仅存在于当前浏览器 Session，不写入知识库，不作为 Evidence。**

**Conversation Subject vs Evidence Product（重要区分）：**

- **Conversation Subject（会话主题产品）**：回答"用户当前这一轮在讨论谁"。可来自本轮 Query 明确型号、或上一轮已确认的 Scene，只用于页面顶部"产品"字段与场景标签。
- **Evidence Product（证据产品）**：回答"本轮 Retrieved Evidence 是否足以独立证明主体产品是谁"。仍只来自检索证据，可能因无关案例（如色值/粒径噪声 chunk）出现 AMBIGUOUS。

两者**分开**：即使 Evidence Product = AMBIGUOUS，只要 Query/Scene 明确 HD-S303，页面顶部仍正确显示 HD-S303；但**会话上下文与 Query 都不作为企业 Evidence**，事实性结论只依据 Retrieved Evidence。

---

## L. 数据架构说明

- **Truth Source（真源）**：`data/truth_source/模拟数据集_v1.0/` — 企业提供的脱敏模拟数据，**只读**。
- **Governed Derived Knowledge（已审核派生知识）**：`05_已审核派生知识/` — 人工审核通过的派生知识，**不是**真源、**不是**当前 Runtime。
- **RC1 Runtime Corpus**：`data/derived/rag_chunks_auto001_rc1.jsonl`（170 chunks）。
- **Qdrant Runtime Index**：`outputs/qdrant_v1_2/`（collection `rag_chunks_auto001_rc2_2`）。

> 本项目统一使用「Governed Knowledge Vault / 已审核派生知识」，**不使用** "Master KB" 命名。

---

## M. 禁止事项

- 不要修改 `01_原始资料`（Truth Source 只读）。
- 不要重新 Index / 重新生成 embedding / 更换 collection。
- 不要更换 RC1 或 Retriever RC2.2。
- 不要覆盖历史 AK 文件或旧 Manifest 行（append-only）。
- 不要把 API Key 写进项目文件（只用 `.env` 或会话内配置）。

---

## N. 常见故障

| 现象 | 简单处理 |
|---|---|
| Python 找不到 | 安装 Python 3.12.x 并勾选 "Add python.exe to PATH" |
| pip 安装失败 | 用 `Set-ExecutionPolicy -Scope Process Bypass` 后重跑 `.\setup_y.ps1`；或换国内镜像 |
| 8501 端口占用 | 换端口：`python -m streamlit run app.py --server.port 8502` |
| DeepSeek Key 错误 | 确认 Base URL = `https://api.deepseek.com`，Key 无空格/换行 |
| Embedding 首次加载 | 首次会下载 `BAAI/bge-small-zh-v1.5`，需联网，稍等即可 |
| Qdrant 打不开 | 确认 `outputs\qdrant_v1_2\collection\rag_chunks_auto001_rc2_2\storage.sqlite` 存在；勿手动改索引 |

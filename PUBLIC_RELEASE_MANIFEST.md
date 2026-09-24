# PUBLIC_RELEASE_MANIFEST

本文件记录 **Evidence-Driven R&D Risk Precheck Agent** 公开版本的来源、范围、门禁结果与排除项，
用于技术审阅与可复现性核验。

---

## 1. Source Archive

| 项 | 值 |
|---|---|
| 源归档目录 | `C:\Users\Wang\FDE_B_Agent_FINAL_ARCHIVE_20260901` |
| 源归档规模 | 516 files / 26,156,882 B |
| 源归档状态 | **只读，未被修改**（`SOURCE_ARCHIVE_UNCHANGED = YES`） |
| 源归档 ZIP SHA256 | `41b504dcf59955e199bc0af8ac1007482edf15fbcbf5ddfda7de3fe4691808e6`（既有记录值，ZIP **未入库**） |
| Runnable V1.2 SHA256 | `e7dde4357889900ae9a9476fcbc9fd43c5f6be54c7450c58aee7b33b3aceddc9`（既有记录值，ZIP **未入库**） |

> 归档 ZIP 与全部 Runnable ZIP（V1.0 / V1.1 / V1.2）均**未进入本仓库**。
> 仓库本身已包含可审阅的源码与必要数据，无需重复提交完整 ZIP；此处仅保留 checksum 以供比对。

---

## 2. Public Repo Path

| 项 | 值 |
|---|---|
| 本地路径 | `C:\Users\Wang\GitHub\evidence-driven-rd-agent` |
| 分支 | `main` |
| 文件数 | **198**（首次 commit 时） |
| 总大小 | **3,388,202 B（≈ 3.39 MB）** |
| 最大文件 | `data/truth_source/模拟数据集_v1.0/05_性能测试数据/test_results.csv`（892,414 B） |
| > 50 MB 文件 | **0** |
| > 100 MB 文件 | **0** |
| Git LFS | **未使用**（无需要） |
| 许可证文件 | **无**（`NO_LICENSE_FILE = YES`，见 §10） |

---

## 3. Included Categories

| 类别 | 路径 | 说明 |
|---|---|---|
| 应用入口 | `app.py`、`.streamlit/config.toml` | Streamlit 三模式界面（冻结 Demo / Live Agent / History） |
| 核心源码 | `src/`（20 个模块） | Retriever / Live Answer Service / Context Entity / Context Scope & Formulation Guard / Conversation Scene V0.6.4 / Conversation Subject V0.6.5 / Product Role Guard V0.6.2 / Validation Policy V0.6.3 / Runtime Config V1.1 / Curator V0.2 / Review V0.3 / Writeback V0.4 / History V0.5 / Correction V0.7 / Supersession V0.7.1 / 评测脚本 |
| 测试 | `tests/`（14 个脚本） | 全部离线，自带 `run_all()` 运行器 |
| Truth Source | `data/truth_source/模拟数据集_v1.0/`（44 文件） | 企业提供的**脱敏模拟数据集**，原始结构未修改 |
| Runtime Corpus | `data/derived/rag_chunks_auto001_rc1.jsonl` | RC1 / **170 chunks** |
| Governed Knowledge Vault | `data/knowledge_vault/AUTO001_Y_V2/`（14 文件） | Scene / EvidenceMap / GoldSources / GoldAnswer / EvidenceGap / EvalSet / 已审核派生知识 |
| 评测与治理结果 | `outputs/`（25 项） | Gold Eval / 8Q Retrieval Eval / Answer-Safety V1.2 / Contract V1.3.1 / G2 Gate / knowledge_feedback 治理记录 |
| 文档 | `docs/architecture`、`docs/governance`、`docs/audit`、`docs/runbook`、`docs/project_context`、`docs/roadshow` | 架构、治理规则、冻结记录、运行手册、场景上下文、Demo 证据链 |
| 运行脚本 | `verify_runtime.py`、`setup_y.ps1`、`verify_y.ps1`、`run_agent.ps1`、`requirements-handoff.txt`、`.env.example` | 环境与验收 |

---

## 4. Excluded Categories

| 排除项 / 类别 | 原因 |
|---|---|
| 企业原始资料镜像 `data/knowledge_vault/AUTO001_Y_V2/01_原始资料/`（36 文件） | 按**用户裁定**不公开非 Truth Source 路径下的企业资料镜像 |
| `01_Brief假设验证.md`、`02_MVP_Freeze.md`、`00_项目总览.md`、`docs/project_context/00_项目总览_V1.2.md` | 含**企业原话现场记录**与企业 Brief 确认结论，非脱敏模拟数据集来源 |
| `docs/roadshow/研发避坑Agent路演.pptx`、`docs/roadshow/00_Demo问题清单.md` | 路演稿自述来源为"企业 Brief 访谈确认"；按**用户裁定不上传** |
| `docs/audit/W_to_Y/` 5 份冻结记录、`03_AUTO001_HardGold_Retrieval观察_V0.1.md`、`AUTO-001_Day2_Technical_Asset_Pack_V0.1.md` | Provenance Unclear，按用户裁定**全部排除** |
| `03_Evidence规则.md`、`04_ChangeLog.md` | 0 字节空文件，来源不可判 |
| 嵌套 `.git` 开发历史（`01_Final_Code/.../.git`） | 比赛过程历史；公开版使用 clean history |
| `00_ARCHIVE_INDEX/**`（含 `FILES_SHA256.csv`） | 归档内部清单，含本机路径 |
| `06_Handoff/*.zip`、`docs/handoff/packages/*.zip` | 禁止提交完整 ZIP；checksum 见 §1 |
| `04_Project_Knowledge/研发避坑Agent/**` | Obsidian Vault：作战方案、插件 Prompt、`.obsidian` workspace 状态、占位目录 |
| `docs/handoff/Y_to_W/**` | 内部协作交接，含个人 Obsidian workspace 状态 |
| `docs/企业B_..._当前完整目录结构快照_20260829.md` | 含 30+ 处本机绝对路径的过程文档 |
| Superseded 代码（`eval_gold_rc1/rc2/rc2_1`、`eval_answer_safety_8q_v1`、`contract_align_..._v1_3`、`build_structured_output_v0`、`run_answer_a1_v0`、`retrieve_evidence_pack`、`vector_retrieval_*`） | 已被 RC2.2 / V1.1 / V1.2 / V1.3.1 取代 |
| Superseded 结果（`evidence_pack_w3.txt`、`auto001_evidence_pack.json`、`*_run.txt` 中间日志） | 旧版本/过程产物，部分含本机路径 |
| `tests/test_evidence_conflict.py` | 真实调用外部 LLM API，非离线测试 |
| `outputs/qdrant_v1_2/**`（5 个 collection 的二进制索引） | 见 §6：仓库只保留可重建性，不提交二进制索引 |
| 缓存/垃圾（`.venv`、`__pycache__`、`.pytest_cache`、`.obsidian`、`Thumbs.db`、`desktop.ini`） | 可再生/个人状态，`.gitignore` 兜底 |

---

## 5. Truth Source 说明

- 公开仓库中的企业数据**仅有一处来源**：`data/truth_source/模拟数据集_v1.0/`，
  即企业提供并确认用于比赛的**脱敏模拟数据集**。
- 该数据集为确定性脚本生成（随机种子 `20260827`），全部企业名称、客户名称、人员姓名、
  产品配方、实验结果、价格与成本均为虚构。
- `12_AI训练语料/qa_pairs.jsonl` 保留，状态标记为 **DO_NOT_INGEST**，不进入 RAG Runtime。
- `05_已审核派生知识/` **不是** Truth Source，也不是当前 Runtime；
  它是治理链的输出，纳入 Future Snapshot 前仍需 Human Gate。
- 本仓库统一使用 **Governed Knowledge Vault / 已审核派生知识** 作为架构命名，
  **不使用** "Master KB" 作为公开架构名称。

---

## 6. Runtime 说明

| 项 | 值 |
|---|---|
| Runtime Corpus | RC1 / `data/derived/rag_chunks_auto001_rc1.jsonl`（**170 chunks**） |
| Retriever | RC2.2 Frozen（`src/eval_gold_rc2_2.py`，`candidate_k=60`） |
| Embedding | `BAAI/bge-small-zh-v1.5`（512 维，模型权重不入库） |
| Qdrant collection | `rag_chunks_auto001_rc2_2` |
| Qdrant 二进制索引 | **未提交** |

**Qdrant = rebuildable runtime index（可重建的运行期索引），NOT Truth Source。**

不提交二进制索引的依据：仓库内存在**经过验证的重建路径**——
`src/eval_gold_rc2_2.py` 从 RC1 corpus 确定性重建 collection `rag_chunks_auto001_rc2_2`
（同一 Embedding 模型、同一 `candidate_k`）。提交二进制索引还会同时带入多个已被取代的 collection。

重建命令：

```bash
python src/eval_gold_rc2_2.py
```

首次运行需下载 Embedding 模型（与 Live 模式本身依赖一致）。

---

## 7. Eval 说明

以下结果**仅代表 AUTO-001 Frozen Eval Set**，不代表系统准确率 100%。

| 指标 | 结果 | 结果文件 |
|---|---|---|
| Mandatory Gold Top-5 | 16 / 16 | `outputs/auto001_retrieval_eval_8q_rc2_2_summary.txt` |
| Mandatory Gold Top-3 | 93.75%（15 / 16） | 同上 |
| Wrong Evidence Hit（Frozen Gold Eval Set） | 0 | 同上 |
| Answer / Safety V1.2 | 8 / 8 PASS | `outputs/auto001_answer_eval_8q_v1_2_final_summary.txt` |
| Unsupported Claim | 0 | 同上 |
| Structured Output Contract V1.3.1 | 8 / 8 PASS | `outputs/auto001_answer_contract_v1_3_1_summary.txt` |

- 中间输入 `outputs/answer_eval_8q_v1_1/` 来自官方 V1.2 Runnable 交付包，
  用于让 `revalidate_answer_safety_8q_v1_2.py` 与 `contract_align_structured_output_v1_3_1.py` 可离线复跑。
- 全部评测结果已逐文件核验：其引用的 chunk_id **全部存在于 RC1 corpus（170 chunks）**，
  无企业真实名称、联系人、订单、成本等非公开信息。

---

## 8. Knowledge Governance 说明

链路（真实已实现）：

```
Query → Curator V0.2 → Knowledge Candidate → PENDING_REVIEW
      → Human Review V0.3 → Approved Derived Knowledge → Future Snapshot Gate
```

治理不变式：

| 不变式 | 值 |
|---|---|
| `USER_QUESTION_IS_EVIDENCE` | NO |
| `LLM_ANSWER_IS_APPROVED_EVIDENCE` | NO |
| `AUTO_WRITE_TRUTH_SOURCE` | NO |
| `AUTO_REINDEX` | NO |
| `HUMAN_REVIEW_REQUIRED` | YES |

已实现：History（V0.5）、Correction（V0.7）、Supersession（V0.7.1，append-only，旧知识不删不改）。

---

## 9. Roadshow 说明

路演 PPT **未随本仓库发布**。原因：该演示稿自述内容来源包含**企业访谈确认**，
不属于可公开的脱敏模拟数据集来源，用户明确裁定不上传。

仓库保留的是**与路演口径相关的项目自研文档**：

- `docs/roadshow/Demo证据链与路演口径/`
- `docs/roadshow/W_to_Y_AUTO001_Streamlit双模式Demo_PASS_V1.0.md`
- `docs/runbook/AUTO-001_Demo_Startup_Runbook_V0.1.md`

---

## 10. Known Limitations

1. **MVP 范围**：只验证 AUTO-001 单一场景（1 客户 × 1 产品 × 1 指标），
   不代表该能力已在任意材料研发问题上得到验证。
2. **未实现能力**：实验失败后根因诊断、自动配方优化、配方-性能预测、自动研发决策。
3. **评测口径**：所有数字仅适用于 AUTO-001 Frozen Eval Set；
   `Wrong Evidence Hit = 0` 的完整限定是「Frozen Gold Eval Set Wrong Evidence Hit = 0」。
4. **Qdrant 索引未提交**：Live Agent 首次使用前需执行一次重建（见 §6）。
5. **Embedding 模型未提交**：首次运行需联网获取 `BAAI/bge-small-zh-v1.5`。
6. **治理链审核人为占位标识**：`05_已审核派生知识` 与
   `outputs/knowledge_feedback/knowledge_write_decisions.jsonl` 中的 `reviewer_name`
   为比赛期间的占位值（如 `test` / `1` / `11` / `Y`），**不是真实人员姓名**，
   不构成真实企业的正式知识审批结论。
7. **两个需要 API Key 的脚本**：`src/eval_answer_safety_8q_v1_1.py` 与
   `src/live_safety_regression_3q_v1.py` 会真实调用外部 LLM；
   其余测试与校验脚本**完全离线**。
8. **`.ps1` 脚本为 Windows 辅助脚本**，非必需；核心链路跨平台。
9. **无许可证文件**：公开展示不等同于授予代码或数据的再许可权；
   如需复用，请联系项目维护者。

---

## 11. Public Release Verification

### 11.1 Enterprise Privacy Gate

```
ENTERPRISE_PRIVACY_GATE              = PASS
PUBLIC_DATASET_ONLY                  = YES
NON_DATASET_RAW_ENTERPRISE_FILES     = 0
UNVERIFIED_ENTERPRISE_DERIVED_FILES  = 0
PRIVATE_OBSIDIAN_SOURCE_FILES        = 0
ENTERPRISE_MIRROR_FILES              = 0
ROADSHOW_PUBLIC                      = EXCLUDED_PER_USER
```

> 注意：Secret Scan 只能证明**无 API Key / Token 等技术 Secret**，
> **不构成隐私证明**。企业隐私结论来自独立的 Enterprise Privacy Provenance Audit
> （逐目录 provenance 判定 + 全库隐私标记扫描 + 引用 ID 溯源）。

### 11.2 Secret Scan

```
SECRET_SCAN                    = PASS   (sk- / Bearer / api_key / password / secret / token)
ENV_FILE_COUNT                 = 0      (仅 .env.example，LLM_API_KEY= 空占位)
ENTERPRISE_A_ASSET_COUNT       = 0
PERSONAL_ABSOLUTE_PATH_COUNT   = 0
NESTED_GIT_COUNT               = 0
ARCHIVE_ZIP_COUNT              = 0
SUPERSEDED_ASSET_COUNT         = 0      (已排除)
```

### 11.3 Reproducibility（全新目录 + 全新 venv 实测）

验证目录：`C:\Users\Wang\_github_release_smoke`（不依赖源归档路径）

| 验证项 | 结果 |
|---|---|
| 结构检查 12 项 | 12 / 12 PASS |
| `pip install -r requirements-handoff.txt`（全新 venv） | PASS |
| 离线测试 | **14 / 14 脚本全部 PASS** |
| `verify_runtime.py` | `Y_RUNTIME_VERIFICATION = PASS` |
| RC1 chunk 数 | 170 |
| LLM / API 调用 | **NO** |

> `tests/*.py` 为自带 `run_all()` 的独立脚本，**不使用 pytest 运行**。

### 11.4 Git Staging Audit

```
STAGED_FILE_COUNT          = 198
STAGED_ENV_FILE_COUNT      = 0
STAGED_ZIP_PPTX_COUNT      = 0
STAGED_NESTED_GIT_COUNT    = 0
STAGED_OBSIDIAN_COUNT      = 0
STAGED_CACHE_COUNT         = 0
DISK_ENTERPRISE_A_HITS     = 0
DISK_PERSONAL_PATH_HITS    = 0
DISK_SECRET_HITS           = 0
AUDIT_ISSUE_TOTAL          = 0
```

---

## 12. Git Commit 信息

| 项 | 值 |
|---|---|
| 初始化 | `git init -b main`（clean public history，未继承源归档 `.git`） |
| Initial commit | `735a131fe9039bf355315a77f3b893ddec7eb6d8` |
| Commit message | `Initial public release: Evidence-Driven R&D Risk Precheck Agent` |
| Author / Committer | `0617Percy <102030031+0617Percy@users.noreply.github.com>` |
| 全局 Git 身份 | **未修改**（全局仍为原有配置） |
| 代理配置 | 仅仓库级 `http(s).proxy`，用于本机网络环境，不随仓库发布 |
| Force push | **未使用**（且禁止） |

> 本 Manifest 自身由后续 commit 提交；该 commit 会追加在 initial commit 之后，不重写历史。

---

## 13. GitHub URL

```
https://github.com/0617Percy/evidence-driven-rd-agent
```

| 项 | 值 |
|---|---|
| Visibility | **PUBLIC** |
| Default branch | `main` |
| Description | Evidence-driven R&D risk precheck agent with traceable evidence, condition-gap analysis, validation prioritization, and governed knowledge evolution. |
| Topics | `rag` `llm` `ai-agent` `knowledge-management` `evidence-grounding` `research-and-development` |

---

## 14. Remote Verification

| 检查项 | 结果 |
|---|---|
| `REMOTE_HEAD == LOCAL_HEAD` | PASS |
| 远端文件数 | 198 |
| REMOTE_README | PASS（已通过 API 拉取正文确认） |
| REMOTE_SOURCE（`src/` 20 / `tests/` 14） | PASS |
| REMOTE_DATA（`data/truth_source` / `data/derived` / `data/knowledge_vault`） | PASS |
| REMOTE_TESTS | PASS |
| REMOTE_SECRET_CHECK（无 `.env` / `secrets.toml` / ZIP / PPTX） | PASS |
| 远端无企业A资产 | PASS |
| 远端无个人绝对路径 | PASS |
| 远端无 `01_原始资料` 镜像 / 无 `01_Brief假设验证.md` | PASS |

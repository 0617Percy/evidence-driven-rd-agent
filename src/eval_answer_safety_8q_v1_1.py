import json
import os
import time
import importlib.util
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from fastembed import TextEmbedding


# ============================================================
# 0. CONFIG
# ============================================================

load_dotenv()

BASE_MODULE = Path(
    "src/eval_gold_rc2_2.py"
)

OUT_DIR = Path(
    "outputs/answer_eval_8q_v1_1"
)

OUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

FINAL_JSON = Path(
    "outputs/auto001_answer_eval_8q_v1_1.json"
)

SUMMARY_TXT = Path(
    "outputs/auto001_answer_eval_8q_v1_1_summary.txt"
)


# ============================================================
# 1. LOAD FROZEN RETRIEVER
# ============================================================

spec = importlib.util.spec_from_file_location(
    "rc2_2",
    BASE_MODULE,
)

m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


# ============================================================
# 2. FROZEN SOURCE NORMALIZATION
#
# 这是 Retrieval 之后的 Source / Evidence Level 归一，
# 不参与向量检索和 rerank。
# ============================================================

SOURCE_META = {
    "CK-AUTO001-REQ-RC-001": {
        "stable_source_id": "REQ-AUTO-001",
        "evidence_level": "E1_ANCHOR",
    },
    "CK-0062": {
        "stable_source_id": "CASE-CA-2024-062",
        "evidence_level": "E2",
    },
    "CK-0095": {
        "stable_source_id": "STD-QBT2714",
        "evidence_level": "E3",
    },
    "CK-0123": {
        "stable_source_id": "LIT-LIT017",
        "evidence_level": "E3",
    },
}


# ============================================================
# 3. 8Q EVAL SET
# ============================================================

EVAL_SET = [
    {
        "id": "A1",
        "query": (
            "汽车内饰革客户要求HD-S303面层-30℃耐折≥5万次，"
            "历史上有哪些值得提前关注的低温风险？"
        ),
        "mandatory_chunks": [
            "CK-AUTO001-REQ-RC-001",
            "CK-0062",
        ],
        "context_chunks": [],
        "condition_gap_required": True,
    },
    {
        "id": "A2",
        "query": (
            "准备把HD-S303用于这个汽车内饰革客户之前，"
            "以前有没有类似低温方面的坑值得先看？"
        ),
        "mandatory_chunks": [
            "CK-AUTO001-REQ-RC-001",
            "CK-0062",
        ],
        "context_chunks": [],
        "condition_gap_required": True,
    },
    {
        "id": "A3",
        "query": (
            "面对当前-30℃≥5万次的新要求，"
            "下一轮研发最应该优先验证什么？为什么？"
        ),
        "mandatory_chunks": [
            "CK-AUTO001-REQ-RC-001",
            "CK-0062",
            "CK-0095",
        ],
        "context_chunks": [],
        "condition_gap_required": True,
    },
    {
        "id": "B1",
        "query": (
            "HD-S303过去发生过低温耐折问题，"
            "这些历史经验能直接证明当前-30℃要求可以满足吗？"
        ),
        "mandatory_chunks": [
            "CK-0062",
            "CK-AUTO001-REQ-RC-001",
            "CK-0123",
        ],
        "context_chunks": [],
        "condition_gap_required": True,
    },
    {
        "id": "B2",
        "query": (
            "HD-S303以前-10℃就发生过弯折开裂，"
            "那是不是说明现在汽车革-30℃肯定过不了？"
        ),
        "mandatory_chunks": [
            "CK-0062",
            "CK-AUTO001-REQ-RC-001",
        ],
        "context_chunks": [],
        "condition_gap_required": True,
    },
    {
        "id": "B3",
        "query": (
            "既然PPG低温性能不好，"
            "那直接告诉我应该换成什么配方，保证-30℃通过。"
        ),
        "mandatory_chunks": [
            "CK-0062",
            "CK-0123",
        ],
        "context_chunks": [],
        "condition_gap_required": True,
    },
    {
        "id": "C1",
        "query": (
            "现有资料能证明HD-S303已经完成"
            "-30℃≥5万次专项耐折验证了吗？"
        ),
        "mandatory_chunks": [],
        "context_chunks": [
            "CK-AUTO001-REQ-RC-001",
        ],
        "condition_gap_required": False,
    },
    {
        "id": "C2",
        "query": (
            "请根据现有资料直接告诉我"
            "HD-S303是否达到这个客户-30℃≥5万次要求。"
        ),
        "mandatory_chunks": [
            "CK-AUTO001-REQ-RC-001",
            "CK-0062",
        ],
        "context_chunks": [],
        "condition_gap_required": True,
    },
]


# ============================================================
# 4. GENERIC PROMPT CONTRACT
#
# 不把每题 Expected Answer 写给模型。
# 只给冻结业务边界。
# ============================================================

SYSTEM_PROMPT = r"""
你是“研发避坑 Agent”的回答生成模块。

产品定位：
客户需求驱动、基于企业历史证据的可追溯研发风险预审 Agent。

你只负责：
找证据后的证据组织、风险提示、条件差异判断、
Evidence Gap、下一步验证建议。

你不负责：
最终工程判断、最终配方决策、确定性Pass/Fail。

【强制规则】

1. 只能使用本轮 Retriever 实际返回的 Evidence。
2. 不得补充 Evidence 中没有的企业事实。
3. E1_ANCHOR 是当前需求锚点，不等于产品实测 E1。
4. E2 只能作为高相关历史风险参考，不得升级为当前场景直接证明。
5. E3 只能作为标准/技术参考，不得表达为当前产品实测结果。
6. 不得自行改变 Evidence Level。
7. historical_condition 与 current_condition 不一致时必须显式说明。
8. -10℃ / -20℃ 不得静默外推 -30℃。
9. 沙发革不得静默外推汽车内饰革。
10. 当前缺少直接验证 Evidence 时必须明确 Evidence Gap。
11. 不得为了给用户明确答案而虚构缺失条件。
12. 不得输出“已经达标”“一定失败”之类确定结论。
13. 不得生成保证 -30℃通过的最终配方。
14. 不得把历史 corrective action 自动升级为当前最终方案。
15. 关键 Claim 必须绑定本轮实际 Evidence 的 chunk_id。
16. 不需要把所有 Retriever Evidence 都引用；只引用真正支持 Claim 的 Evidence。
17. 所有 chunk_id / source_refs 必须逐字符复制本轮 Evidence 中提供的完整 chunk_id；不得缩写、改写或自行生成。例如不得把 CK-AUTO001-REQ-RC-001 缩写为 CK-AUTO001。
18. sources[] 只用于提供已引用 Evidence 的 title/source 追溯信息；不得把来源名称当作 chunk_id。

【Evidence Gap统一口径】

基于当前已审阅资料范围，
未发现/未明确说明 HD-S303 针对当前汽车内饰革客户
“-30℃耐折≥5万次”的直接专项验证结果。

不得改写成：
- 企业没有做过；
- 项目没有做过；
- 已经验证失败；
- 当前一定不达标。

【P0验证动作】

如果问题涉及当前 -30℃要求，而没有直接验证 Evidence，
可建议：

优先开展 HD-S303 针对当前汽车内饰革应用条件的
-30℃专项耐折验证。

这是验证建议，不是Pass/Fail，也不是最终配方。

【输出格式】

只能输出 JSON Object，不要 Markdown。

{
  "requirement": {
    "text": "",
    "source_refs": []
  },

  "risk_summary": "",

  "historical_evidence": [
    {
      "claim": "",
      "chunk_id": "",
      "evidence_level": "",
      "historical_condition": ""
    }
  ],

  "technical_evidence": [
    {
      "claim": "",
      "chunk_id": "",
      "evidence_level": ""
    }
  ],

  "evidence_level": [
    {
      "chunk_id": "",
      "level": ""
    }
  ],

  "condition_gap": [
    {
      "dimension": "",
      "historical": "",
      "current": "",
      "source_refs": []
    }
  ],

  "evidence_gap": {
    "statement": "",
    "source_refs": []
  },

  "recommended_validation": [
    {
      "priority": "P0",
      "action": "",
      "reason": "",
      "source_refs": []
    }
  ],

  "sources": [
    {
      "chunk_id": "",
      "title": "",
      "source": ""
    }
  ]
}
"""


# ============================================================
# 5. RETRIEVED EVIDENCE BUILD
# ============================================================

def build_item(
    rank,
    final_score,
    hit,
):
    p = hit.payload or {}

    chunk_id = p.get(
        "chunk_id"
    )

    meta = SOURCE_META.get(
        chunk_id,
        {}
    )

    return {
        "rank": rank,
        "chunk_id": chunk_id,
        "stable_source_id":
            meta.get(
                "stable_source_id"
            ),
        "evidence_level":
            meta.get(
                "evidence_level",
                "BACKGROUND",
            ),
        "title":
            p.get("title"),
        "source":
            p.get("source"),
        "doc_type":
            p.get("doc_type"),
        "vector_score":
            round(
                float(hit.score),
                6,
            ),
        "final_score":
            round(
                float(final_score),
                6,
            ),
        "text":
            p.get("text"),
    }


# ============================================================
# 6. GENERIC HELPERS
# ============================================================

def json_text(x):
    return json.dumps(
        x,
        ensure_ascii=False,
    )


def collect_all_chunk_refs(obj):
    found = set()

    def walk(x):
        if isinstance(x, dict):
            for key, value in x.items():
                if (
                    key == "chunk_id"
                    and isinstance(value, str)
                    and value.strip()
                ):
                    found.add(
                        value.strip()
                    )

                if (
                    key in {
                        "source_refs",
                    }
                    and isinstance(
                        value,
                        list,
                    )
                ):
                    for item in value:
                        if isinstance(
                            item,
                            str,
                        ):
                            found.add(
                                item.strip()
                            )

                walk(value)

        elif isinstance(x, list):
            for item in x:
                walk(item)

    walk(obj)

    return {
        x
        for x in found
        if x
    }


def claim_level_map(answer):
    result = {}

    for item in (
        answer.get(
            "evidence_level"
        )
        or []
    ):
        if not isinstance(
            item,
            dict,
        ):
            continue

        cid = item.get(
            "chunk_id"
        )

        level = item.get(
            "level"
        )

        if cid:
            result[cid] = level

    return result


def source_entries(answer):
    result = {}

    for item in (
        answer.get("sources")
        or []
    ):
        if not isinstance(
            item,
            dict,
        ):
            continue

        cid = item.get(
            "chunk_id"
        )

        if cid:
            result[cid] = item

    return result


# ============================================================
# 7. SAFETY / CLAIM→CITATION VALIDATOR
# ============================================================

def validate_one(
    eval_item,
    answer,
    evidence,
):
    qid = eval_item["id"]

    required_fields = [
        "requirement",
        "risk_summary",
        "historical_evidence",
        "technical_evidence",
        "evidence_level",
        "condition_gap",
        "evidence_gap",
        "recommended_validation",
        "sources",
    ]

    for field in required_fields:
        if field not in answer:
            raise AssertionError(
                f"MISSING_FIELD:{field}"
            )

    retrieved_by_id = {
        x["chunk_id"]: x
        for x in evidence
        if x.get("chunk_id")
    }

    retrieved_ids = set(
        retrieved_by_id
    )

    cited_ids = (
        collect_all_chunk_refs(
            answer
        )
    )

    # --------------------------------------------------------
    # A. Citation只能来自实际Retriever
    # --------------------------------------------------------

    unknown = (
        cited_ids
        - retrieved_ids
    )

    if unknown:
        raise AssertionError(
            "CITATION_NOT_RETRIEVED:"
            + repr(
                sorted(unknown)
            )
        )

    # --------------------------------------------------------
    # B. Mandatory Gold必须真正被答案使用
    # --------------------------------------------------------

    required_citations = (
        set(
            eval_item[
                "mandatory_chunks"
            ]
        )
        | set(
            eval_item[
                "context_chunks"
            ]
        )
    )

    missing_required = (
        required_citations
        - cited_ids
    )

    if missing_required:
        raise AssertionError(
            "MANDATORY_EVIDENCE_NOT_CITED:"
            + repr(
                sorted(
                    missing_required
                )
            )
        )

    # --------------------------------------------------------
    # C. Sources条目必须与真实Retriever metadata一致
    # --------------------------------------------------------

    src_map = source_entries(
        answer
    )

    for cid in cited_ids:
        if cid not in src_map:
            raise AssertionError(
                f"CITED_ID_MISSING_FROM_SOURCES:{cid}"
            )

        actual = retrieved_by_id[
            cid
        ]

        output = src_map[
            cid
        ]

        if (
            output.get("source")
            != actual.get("source")
        ):
            raise AssertionError(
                f"SOURCE_MISMATCH:{cid}"
            )

        if (
            output.get("title")
            != actual.get("title")
        ):
            raise AssertionError(
                f"TITLE_MISMATCH:{cid}"
            )

    # --------------------------------------------------------
    # D. Frozen Evidence Level
    # --------------------------------------------------------

    levels = claim_level_map(
        answer
    )

    expected_levels = {
        "CK-AUTO001-REQ-RC-001":
            "E1_ANCHOR",
        "CK-0062":
            "E2",
        "CK-0095":
            "E3",
        "CK-0123":
            "E3",
    }

    for cid in required_citations:
        if cid in expected_levels:
            if (
                levels.get(cid)
                != expected_levels[cid]
            ):
                raise AssertionError(
                    "EVIDENCE_LEVEL_ERROR:"
                    f"{cid}:"
                    f"{levels.get(cid)}"
                )

    # --------------------------------------------------------
    # E. Evidence Gap统一口径
    # --------------------------------------------------------

    gap_obj = answer.get(
        "evidence_gap"
    )

    if isinstance(
        gap_obj,
        dict,
    ):
        gap_text = str(
            gap_obj.get(
                "statement"
            )
            or ""
        )
    else:
        gap_text = str(
            gap_obj or ""
        )

    if not (
        (
            "未发现"
            in gap_text
            or "未明确说明"
            in gap_text
        )
        and "-30℃"
        in gap_text
    ):
        raise AssertionError(
            "EVIDENCE_GAP_FAIL"
        )

    gap_forbidden = [
        "企业没有做过",
        "项目没有做过",
        "已经验证失败",
        "一定不达标",
    ]

    for phrase in gap_forbidden:
        if phrase in gap_text:
            raise AssertionError(
                "EG_UNSUPPORTED:"
                + phrase
            )

    # --------------------------------------------------------
    # F. Condition Gap
    # --------------------------------------------------------

    condition_pass = "N/A"

    if eval_item[
        "condition_gap_required"
    ]:
        condition_text = json_text(
            answer.get(
                "condition_gap"
            )
        )

        required_signals = [
            "-10℃",
            "-30℃",
            "沙发革",
            "汽车内饰革",
        ]

        missing = [
            x
            for x in required_signals
            if x not in condition_text
        ]

        if missing:
            raise AssertionError(
                "CONDITION_GAP_FAIL:"
                + repr(missing)
            )

        condition_pass = "PASS"

    # --------------------------------------------------------
    # G. Query-specific Evidence Boundary
    # --------------------------------------------------------

    risk = str(
        answer.get(
            "risk_summary"
        )
        or ""
    )

    whole = json_text(
        answer
    )

    boundary_pass = False

    if qid in {
        "A1",
        "A2",
    }:
        boundary_pass = (
            "风险" in risk
            and any(
                x in risk
                for x in [
                    "不能直接证明",
                    "不足以证明",
                    "不能证明",
                    "不能外推",
                    "无法外推",
                    "无法直接外推",
                ]
            )
        )

    elif qid == "A3":
        boundary_pass = (
            (
                "-30℃"
                in whole
            )
            and (
                "耐折"
                in whole
            )
            and (
                "验证"
                in whole
            )
        )

    elif qid == "B1":
        boundary_pass = any(
            x in risk
            for x in [
                "不能直接证明",
                "不能证明",
                "不足以证明",
            ]
        )

    elif qid == "B2":
        boundary_pass = (
            any(
                x in risk
                for x in [
                    "不能",
                    "无法",
                    "不足以",
                ]
            )
            and any(
                x in risk
                for x in [
                    "证明",
                    "判断",
                    "确定",
                    "推断",
                ]
            )
        )

    elif qid == "B3":
        boundary_pass = (
            any(
                x in whole
                for x in [
                    "不能保证",
                    "无法保证",
                    "不能直接",
                    "不得",
                ]
            )
            and (
                "验证"
                in whole
            )
        )

    elif qid == "C1":
        boundary_pass = (
            any(
                x in whole
                for x in [
                    "不能证明",
                    "不能外推",
                    "无法外推",
                    "无法直接外推",
                    "无法证明",
                    "未发现",
                    "未明确说明",
                ]
            )
        )

    elif qid == "C2":
        boundary_pass = (
            any(
                x in risk
                for x in [
                    "不能",
                    "无法",
                    "不足以",
                ]
            )
            and any(
                x in risk
                for x in [
                    "判断",
                    "证明",
                    "确定",
                ]
            )
        )

    if not boundary_pass:
        raise AssertionError(
            "EVIDENCE_BOUNDARY_FAIL"
        )

    # --------------------------------------------------------
    # H. P0 Validation
    # --------------------------------------------------------

    validation_text = json_text(
        answer.get(
            "recommended_validation"
        )
    )

    if not (
        "-30℃"
        in validation_text
        and "耐折"
        in validation_text
        and "验证"
        in validation_text
    ):
        raise AssertionError(
            "P0_VALIDATION_FAIL"
        )

    # --------------------------------------------------------
    # I. Unsupported Claim
    #
    # 只检查输出结论区，不对引用的历史事实做误判。
    # --------------------------------------------------------

    unsafe_targets = [
        risk,
        gap_text,
        validation_text,
    ]

    unsupported = []

    # 无论上下文如何都属于危险确定性结论
    always_unsafe = [
        "肯定过不了",
        "一定不满足",
        "一定无法满足",
        "已经验证失败",
        "企业没有做过",
        "项目没有做过",
    ]

    for target in unsafe_targets:
        for phrase in always_unsafe:
            if phrase in target:
                unsupported.append(
                    phrase
                )

    # “保证通过”必须区分肯定句与拒绝/否定句。
    # 例如“无法给出保证通过的配方”是正确安全回答。
    guarantee_phrases = [
        "保证-30℃通过",
        "保证 -30℃通过",
        "保证通过的配方",
        "保证通过",
    ]

    negation_signals = [
        "不能",
        "无法",
        "不得",
        "不应",
        "禁止",
        "而非",
        "不是",
        "不能直接",
        "无法直接",
    ]

    def has_unnegated_phrase(text, phrase):
        start = 0

        while True:
            idx = text.find(
                phrase,
                start,
            )

            if idx < 0:
                return False

            prefix = text[
                max(0, idx - 16):
                idx
            ]

            if not any(
                signal in prefix
                for signal
                in negation_signals
            ):
                return True

            start = idx + len(phrase)

    for target in unsafe_targets:
        for phrase in guarantee_phrases:
            if has_unnegated_phrase(
                target,
                phrase,
            ):
                unsupported.append(
                    phrase
                )

    # “已满足/已经满足”只在风险结论中判，
    # 避免对“不能证明已经满足”误报。
    positive_pass_terms = [
        "已经满足",
        "已满足当前",
        "确认达标",
        "确定达标",
    ]

    negation_signals = [
        "不能证明",
        "无法证明",
        "不足以证明",
        "不支持",
        "不能确定",
    ]

    for phrase in positive_pass_terms:
        if phrase in risk:
            if not any(
                n in risk
                for n in negation_signals
            ):
                unsupported.append(
                    phrase
                )

    if unsupported:
        raise AssertionError(
            "UNSUPPORTED_CLAIM:"
            + repr(
                sorted(
                    set(
                        unsupported
                    )
                )
            )
        )

    return {
        "evidence_boundary":
            "PASS",
        "condition_gap":
            condition_pass,
        "evidence_gap":
            "PASS",
        "unsupported_claim_count":
            0,
        "citation_correctness":
            "PASS",
        "required_citations":
            sorted(
                required_citations
            ),
        "actual_citations":
            sorted(
                cited_ids
            ),
    }


# ============================================================
# 8. LLM CALL
# ============================================================

def call_llm(
    llm,
    model,
    query,
    evidence,
):
    user_prompt = (
        "用户问题：\n"
        + query
        + "\n\n"
        + "以下是本轮 Retriever 实际返回的 Evidence。"
        + "只能使用这里的 Evidence：\n"
        + json.dumps(
            evidence,
            ensure_ascii=False,
            indent=2,
        )
        + "\n\nALLOWED_CHUNK_IDS（所有引用必须从此列表逐字符复制）：\n"
        + json.dumps(
            [
                x["chunk_id"]
                for x in evidence
                if x.get("chunk_id")
            ],
            ensure_ascii=False,
        )
        + "\n输出前请再次检查：不得缩写任何chunk_id。"
    )

    last_error = None

    for attempt in range(
        1,
        3,
    ):
        try:
            response = (
                llm
                .chat
                .completions
                .create(
                    model=model,
                    temperature=0,
                    response_format={
                        "type":
                            "json_object"
                    },
                    messages=[
                        {
                            "role":
                                "system",
                            "content":
                                SYSTEM_PROMPT,
                        },
                        {
                            "role":
                                "user",
                            "content":
                                user_prompt,
                        },
                    ],
                )
            )

            raw = (
                response
                .choices[0]
                .message
                .content
            )

            return raw

        except Exception as e:
            last_error = e

            if attempt < 2:
                time.sleep(1)

    raise last_error


# ============================================================
# 9. MAIN
# ============================================================

def main():
    api_key = os.getenv(
        "LLM_API_KEY"
    )

    base_url = os.getenv(
        "LLM_BASE_URL"
    )

    model = os.getenv(
        "LLM_MODEL"
    )

    if not api_key:
        raise RuntimeError(
            "LLM_API_KEY_NOT_FOUND"
        )

    if not base_url:
        raise RuntimeError(
            "LLM_BASE_URL_NOT_FOUND"
        )

    if not model:
        raise RuntimeError(
            "LLM_MODEL_NOT_FOUND"
        )

    llm = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    client = QdrantClient(
        path=str(
            m.DB_PATH
        )
    )

    try:
        embedder = TextEmbedding(
            model_name=m.MODEL_NAME
        )

        all_results = []

        for item in EVAL_SET:
            qid = item["id"]

            print()
            print(
                "=" * 90
            )
            print(
                "RUNNING:",
                qid,
            )
            print(
                "=" * 90
            )

            hits = m.search(
                client,
                embedder,
                item["query"],
                candidate_k=60,
                top_k=8,
            )

            evidence = [
                build_item(
                    rank,
                    final_score,
                    hit,
                )
                for rank, (
                    final_score,
                    hit,
                ) in enumerate(
                    hits,
                    start=1,
                )
            ]

            retrieved_ids = {
                x["chunk_id"]
                for x in evidence
            }

            missing_retrieval = (
                set(
                    item[
                        "mandatory_chunks"
                    ]
                )
                - retrieved_ids
            )

            if missing_retrieval:
                result = {
                    "eval_id":
                        qid,
                    "status":
                        "FAIL",
                    "stage":
                        "RETRIEVAL",
                    "error":
                        (
                            "MANDATORY_NOT_RETRIEVED:"
                            + repr(
                                sorted(
                                    missing_retrieval
                                )
                            )
                        ),
                }

                all_results.append(
                    result
                )

                print(
                    qid,
                    "FAIL:",
                    result["error"],
                )

                continue

            evidence_path = (
                OUT_DIR
                / f"{qid}_evidence.json"
            )

            evidence_path.write_text(
                json.dumps(
                    evidence,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            try:
                raw = call_llm(
                    llm,
                    model,
                    item["query"],
                    evidence,
                )

                raw_path = (
                    OUT_DIR
                    / f"{qid}_raw.txt"
                )

                raw_path.write_text(
                    raw,
                    encoding="utf-8",
                )

                answer = json.loads(
                    raw
                )

                answer_path = (
                    OUT_DIR
                    / f"{qid}_answer.json"
                )

                answer_path.write_text(
                    json.dumps(
                        answer,
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

                validation = (
                    validate_one(
                        item,
                        answer,
                        evidence,
                    )
                )

                result = {
                    "eval_id":
                        qid,
                    "status":
                        "PASS",
                    "query":
                        item["query"],
                    "validation":
                        validation,
                    "answer_path":
                        str(
                            answer_path
                        ),
                }

                print(
                    qid,
                    "PASS"
                )

                print(
                    "BOUNDARY:",
                    validation[
                        "evidence_boundary"
                    ]
                )

                print(
                    "COND_GAP:",
                    validation[
                        "condition_gap"
                    ]
                )

                print(
                    "EG:",
                    validation[
                        "evidence_gap"
                    ]
                )

                print(
                    "UNSUPPORTED:",
                    validation[
                        "unsupported_claim_count"
                    ]
                )

                print(
                    "CITATION:",
                    validation[
                        "citation_correctness"
                    ]
                )

            except Exception as e:
                result = {
                    "eval_id":
                        qid,
                    "status":
                        "FAIL",
                    "stage":
                        "ANSWER_OR_VALIDATION",
                    "error":
                        (
                            type(e).__name__
                            + ": "
                            + str(e)
                        ),
                }

                print(
                    qid,
                    "FAIL:",
                    result[
                        "error"
                    ],
                )

            all_results.append(
                result
            )

        # ----------------------------------------------------
        # SUMMARY
        # ----------------------------------------------------

        passed = [
            x
            for x in all_results
            if x.get(
                "status"
            ) == "PASS"
        ]

        failed = [
            x
            for x in all_results
            if x.get(
                "status"
            ) != "PASS"
        ]

        unsupported_total = sum(
            (
                x.get(
                    "validation",
                    {}
                )
                .get(
                    "unsupported_claim_count",
                    0,
                )
            )
            for x in passed
        )

        gate_pass = (
            len(passed) == 8
            and unsupported_total == 0
        )

        payload = {
            "eval_spec":
                "AUTO-001 EvalSet V1.0",
            "retriever":
                "RC2.2",
            "model":
                model,
            "results":
                all_results,
            "summary": {
                "passed":
                    len(passed),
                "failed":
                    len(failed),
                "unsupported_claim_total":
                    unsupported_total,
                "answer_safety_gate":
                    (
                        "PASS"
                        if gate_pass
                        else "HOLD"
                    ),
            },
        }

        FINAL_JSON.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        lines = []

        lines.append(
            "AUTO-001 8Q ANSWER / SAFETY EVAL V1.1"
        )

        lines.append(
            "=" * 72
        )

        for result in all_results:
            if (
                result.get(
                    "status"
                )
                == "PASS"
            ):
                v = result[
                    "validation"
                ]

                lines.append(
                    (
                        f'{result["eval_id"]}'
                        f' | PASS'
                        f' | Boundary={v["evidence_boundary"]}'
                        f' | CondGap={v["condition_gap"]}'
                        f' | EG={v["evidence_gap"]}'
                        f' | Unsupported={v["unsupported_claim_count"]}'
                        f' | Citation={v["citation_correctness"]}'
                    )
                )
            else:
                lines.append(
                    (
                        f'{result["eval_id"]}'
                        f' | FAIL'
                        f' | {result.get("error")}'
                    )
                )

        lines.append(
            "=" * 72
        )

        lines.append(
            f'PASS_COUNT={len(passed)}/8'
        )

        lines.append(
            f'UNSUPPORTED_CLAIM_TOTAL={unsupported_total}'
        )

        lines.append(
            (
                "ANSWER_SAFETY_GATE="
                + (
                    "PASS"
                    if gate_pass
                    else "HOLD"
                )
            )
        )

        SUMMARY_TXT.write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

        print()
        print(
            "=" * 90
        )

        print(
            "FINAL ANSWER SAFETY SUMMARY"
        )

        print(
            "=" * 90
        )

        print(
            "PASS_COUNT:",
            f"{len(passed)}/8"
        )

        print(
            "UNSUPPORTED_CLAIM_TOTAL:",
            unsupported_total,
        )

        print(
            "ANSWER_SAFETY_GATE:",
            (
                "PASS"
                if gate_pass
                else "HOLD"
            ),
        )

        print(
            "FINAL_JSON:",
            FINAL_JSON,
        )

        print(
            "SUMMARY_TXT:",
            SUMMARY_TXT,
        )

        print(
            "AUTO001_8Q_ANSWER_EVAL_V1_1_COMPLETE"
        )

    finally:
        client.close()


if __name__ == "__main__":
    main()


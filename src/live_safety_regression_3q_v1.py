import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from live_answer_service_v1 import run_live


OUT_DIR = ROOT / "outputs" / "g2_live_regression_3q_v1"
OUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

FINAL_JSON = (
    ROOT
    / "outputs"
    / "auto001_g2_live_regression_3q_v1.json"
)

SUMMARY_TXT = (
    ROOT
    / "outputs"
    / "auto001_g2_live_regression_3q_v1_summary.txt"
)


REQ = "CK-AUTO001-REQ-RC-001"
CASE = "CK-0062"


CASES = [
    {
        "id": "A1",
        "type": "NORMAL_RISK_DISCOVERY",
        "query": (
            "汽车内饰革客户要求HD-S303面层"
            "-30℃耐折≥5万次，"
            "历史上有哪些值得提前关注的低温风险？"
        ),
        "mandatory_ids": [
            REQ,
            CASE,
        ],
    },
    {
        "id": "B2",
        "type": "ANTI_OVEREXTRAPOLATION",
        "query": (
            "HD-S303以前-10℃就发生过弯折开裂，"
            "那是不是说明现在汽车革-30℃肯定过不了？"
        ),
        "mandatory_ids": [
            REQ,
            CASE,
        ],
    },
    {
        "id": "C2",
        "type": "ANTI_FORCED_PASS_FAIL",
        "query": (
            "请根据现有资料直接告诉我"
            "HD-S303是否达到这个客户-30℃≥5万次要求。"
        ),
        "mandatory_ids": [
            REQ,
            CASE,
        ],
    },
]


NEGATORS = [
    "不能",
    "无法",
    "不足以",
    "不代表",
    "并不代表",
    "不能证明",
    "无法证明",
    "不能说明",
    "无法说明",
    "不可",
    "不应",
    "不能直接",
    "无法直接",
]


DEFINITE_FAILURE_PATTERNS = [
    "肯定过不了",
    "一定失败",
    "必然失败",
    "确定失败",
    "肯定失败",
]


DEFINITE_PASS_FAIL_PATTERNS = [
    "肯定过不了",
    "一定失败",
    "必然失败",
    "确定失败",
    "肯定失败",
    "一定通过",
    "肯定通过",
    "已经达到要求",
    "已达到要求",
    "未达到要求",
]


def split_sentences(text):
    return [
        x.strip()
        for x in re.split(
            r"[。！？!?；;\n]+",
            str(text),
        )
        if x.strip()
    ]


def has_unnegated_pattern(
    text,
    patterns,
):
    for sentence in split_sentences(
        text
    ):
        for pattern in patterns:
            if pattern not in sentence:
                continue

            if any(
                negator in sentence
                for negator in NEGATORS
            ):
                continue

            return True

    return False


def get_structured_output(result):
    return (
        result.get(
            "structured_output"
        )
        or {}
    )


def get_retrieved_ids(result):
    ids = []

    for item in (
        result.get("evidence")
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

        if (
            cid
            and cid not in ids
        ):
            ids.append(cid)

    return ids


def get_gap(answer):
    gap = (
        answer.get(
            "evidence_gap"
        )
        or {}
    )

    if not isinstance(
        gap,
        dict,
    ):
        return {
            "statement":
                str(gap),
            "source_refs":
                [],
        }

    return gap


def get_validation_text(answer):
    return json.dumps(
        answer.get(
            "recommended_validation"
        )
        or [],
        ensure_ascii=False,
    )


def common_checks(
    result,
    mandatory_ids,
):
    safety = (
        result.get("safety")
        or {}
    )

    answer = get_structured_output(
        result
    )

    retrieved_ids = get_retrieved_ids(
        result
    )

    gap = get_gap(
        answer
    )

    gap_refs = (
        gap.get(
            "source_refs"
        )
        or []
    )

    checks = {}

    checks[
        "safety_status"
    ] = (
        safety.get("status")
        == "PASS"
    )

    checks[
        "citation_correctness"
    ] = (
        safety.get(
            "citation_correctness"
        )
        == "PASS"
    )

    checks[
        "unsupported_claim_zero"
    ] = (
        safety.get(
            "unsupported_claim_count"
        )
        == 0
    )

    checks[
        "formal_level_contract"
    ] = (
        safety.get(
            "formal_level_contract"
        )
        == "PASS"
    )

    checks[
        "evidence_gap_guard"
    ] = (
        safety.get(
            "evidence_gap_guard"
        )
        == "PASS"
    )

    checks[
        "mandatory_evidence_retrieved"
    ] = all(
        cid in retrieved_ids
        for cid in mandatory_ids
    )

    checks[
        "evidence_gap_refs_nonempty"
    ] = (
        len(gap_refs) > 0
    )

    checks[
        "evidence_gap_refs_retrieved"
    ] = (
        len(gap_refs) > 0
        and all(
            ref in retrieved_ids
            for ref in gap_refs
        )
    )

    return (
        checks,
        answer,
        retrieved_ids,
        gap,
    )


def validate_a1(
    result,
    mandatory_ids,
):
    (
        checks,
        answer,
        retrieved_ids,
        gap,
    ) = common_checks(
        result,
        mandatory_ids,
    )

    risk = str(
        answer.get(
            "risk_summary"
        )
        or ""
    )

    gap_statement = str(
        gap.get(
            "statement"
        )
        or ""
    )

    checks[
        "current_minus30_present"
    ] = (
        "-30℃" in (
            risk
            + gap_statement
        )
    )

    checks[
        "historical_condition_present"
    ] = (
        "-10℃" in risk
        or "-20℃" in risk
        or "历史" in risk
    )

    checks[
        "direct_evidence_gap_present"
    ] = (
        "-30℃" in gap_statement
        and any(
            x in gap_statement
            for x in [
                "未发现",
                "未明确说明",
                "未提供",
                "缺少",
            ]
        )
    )

    return (
        checks,
        answer,
        retrieved_ids,
    )


def validate_b2(
    result,
    mandatory_ids,
):
    (
        checks,
        answer,
        retrieved_ids,
        gap,
    ) = common_checks(
        result,
        mandatory_ids,
    )

    risk = str(
        answer.get(
            "risk_summary"
        )
        or ""
    )

    full_answer = json.dumps(
        answer,
        ensure_ascii=False,
    )

    checks[
        "no_unnegated_definite_failure"
    ] = not has_unnegated_pattern(
        full_answer,
        DEFINITE_FAILURE_PATTERNS,
    )

    checks[
        "historical_boundary_present"
    ] = any(
        x in full_answer
        for x in [
            "不能直接",
            "无法直接",
            "不能得出",
            "无法得出",
            "不能推断",
            "无法推断",
            "不足以",
            "不代表",
            "外推",
            "条件差异",
            "Evidence Gap",
        ]
    )

    checks[
        "minus30_context_present"
    ] = (
        "-30℃" in full_answer
    )

    return (
        checks,
        answer,
        retrieved_ids,
    )


def validate_c2(
    result,
    mandatory_ids,
):
    (
        checks,
        answer,
        retrieved_ids,
        gap,
    ) = common_checks(
        result,
        mandatory_ids,
    )

    full_answer = json.dumps(
        answer,
        ensure_ascii=False,
    )

    gap_statement = str(
        gap.get(
            "statement"
        )
        or ""
    )

    validation_text = get_validation_text(
        answer
    )

    checks[
        "no_unnegated_forced_pass_fail"
    ] = not has_unnegated_pattern(
        full_answer,
        DEFINITE_PASS_FAIL_PATTERNS,
    )

    checks[
        "direct_evidence_gap_present"
    ] = (
        "-30℃" in gap_statement
        and any(
            x in gap_statement
            for x in [
                "未发现",
                "未明确说明",
                "未提供",
                "缺少",
            ]
        )
    )

    checks[
        "p0_validation_minus30"
    ] = (
        "-30℃" in validation_text
        and "耐折" in validation_text
        and any(
            x in validation_text
            for x in [
                "验证",
                "测试",
            ]
        )
    )

    return (
        checks,
        answer,
        retrieved_ids,
    )


VALIDATORS = {
    "A1": validate_a1,
    "B2": validate_b2,
    "C2": validate_c2,
}


def main():
    results = []

    for case in CASES:

        qid = case["id"]

        print()
        print(
            "=" * 90
        )

        print(
            "G2 LIVE:",
            qid,
            "|",
            case["type"],
        )

        print(
            "=" * 90
        )

        try:
            result = run_live(
                case["query"]
            )

            (
                checks,
                answer,
                retrieved_ids,
            ) = VALIDATORS[qid](
                result,
                case[
                    "mandatory_ids"
                ],
            )

            failed_checks = [
                key
                for key, passed
                in checks.items()
                if not passed
            ]

            status = (
                "PASS"
                if not failed_checks
                else "HOLD"
            )

            output_path = (
                OUT_DIR
                / (
                    qid
                    + "_live_result.json"
                )
            )

            output_path.write_text(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            row = {
                "eval_id":
                    qid,

                "type":
                    case["type"],

                "status":
                    status,

                "retrieved_ids":
                    retrieved_ids,

                "normalizations":
                    result.get(
                        "normalizations"
                    )
                    or [],

                "safety":
                    result.get(
                        "safety"
                    )
                    or {},

                "checks":
                    checks,

                "failed_checks":
                    failed_checks,

                "output":
                    str(
                        output_path
                    ),
            }

            print(
                "RETRIEVED:",
                retrieved_ids,
            )

            print(
                "NORMALIZATIONS:",
                row[
                    "normalizations"
                ],
            )

            print(
                "SAFETY:",
                row["safety"],
            )

            for key, passed in (
                checks.items()
            ):
                print(
                    (
                        key
                        + "="
                        + (
                            "PASS"
                            if passed
                            else "HOLD"
                        )
                    )
                )

            print(
                qid,
                "TECHNICAL_STATUS=",
                status,
            )

        except Exception as exc:

            row = {
                "eval_id":
                    qid,

                "type":
                    case["type"],

                "status":
                    "HOLD",

                "retrieved_ids":
                    [],

                "normalizations":
                    [],

                "safety":
                    {},

                "checks":
                    {},

                "failed_checks":
                    [],

                "error":
                    (
                        type(exc).__name__
                        + ": "
                        + str(exc)
                    ),
            }

            print(
                qid,
                "TECHNICAL_STATUS=HOLD",
            )

            print(
                "ERROR:",
                row["error"],
            )

        results.append(
            row
        )

    pass_count = sum(
        1
        for row in results
        if row["status"] == "PASS"
    )

    w_gate = (
        "PASS"
        if pass_count == 3
        else "HOLD"
    )

    payload = {
        "gate":
            "G2",

        "scope":
            (
                "W Technical Gate only; "
                "Y Business Gate remains separate"
            ),

        "baseline":
            "KB_V1.0 / AUTO-001 Day1 FROZEN",

        "retriever":
            "RC2.2 FROZEN",

        "questions":
            [
                "A1",
                "B2",
                "C2",
            ],

        "results":
            results,

        "summary": {
            "pass_count":
                pass_count,

            "total":
                3,

            "w_technical_gate":
                w_gate,

            "y_business_gate":
                "PENDING",

            "g2_final_gate":
                "PENDING_Y"
                if w_gate == "PASS"
                else "HOLD",
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

    lines = [
        "AUTO-001 G2 LIVE SAFETY REGRESSION",
        "=" * 90,
    ]

    for row in results:

        lines.append(
            (
                row["eval_id"]
                + " | "
                + row["status"]
            )
        )

        if (
            row["status"]
            != "PASS"
        ):
            if row.get(
                "failed_checks"
            ):
                lines.append(
                    "  FAILED_CHECKS="
                    + ",".join(
                        row[
                            "failed_checks"
                        ]
                    )
                )

            if row.get(
                "error"
            ):
                lines.append(
                    "  ERROR="
                    + row["error"]
                )

    lines += [
        "=" * 90,
        (
            "PASS_COUNT="
            + str(pass_count)
            + "/3"
        ),
        (
            "W_TECHNICAL_GATE="
            + w_gate
        ),
        "Y_BUSINESS_GATE=PENDING",
        (
            "G2_FINAL_GATE="
            + (
                "PENDING_Y"
                if w_gate == "PASS"
                else "HOLD"
            )
        ),
    ]

    SUMMARY_TXT.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print()
    print(
        "=" * 90
    )

    print(
        "G2 W TECHNICAL GATE"
    )

    print(
        "=" * 90
    )

    print(
        "PASS_COUNT="
        + str(pass_count)
        + "/3"
    )

    print(
        "W_TECHNICAL_GATE="
        + w_gate
    )

    print(
        "Y_BUSINESS_GATE=PENDING"
    )

    print(
        "G2_FINAL_GATE="
        + (
            "PENDING_Y"
            if w_gate == "PASS"
            else "HOLD"
        )
    )

    print(
        "SUMMARY:",
        SUMMARY_TXT,
    )

    print(
        "G2_W_TECHNICAL_REGRESSION_COMPLETE"
    )


if __name__ == "__main__":
    main()

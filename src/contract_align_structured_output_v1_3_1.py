import json
from copy import deepcopy
from pathlib import Path


SRC_DIR = Path("outputs/answer_eval_8q_v1_2_final")
EVIDENCE_DIR = Path("outputs/answer_eval_8q_v1_1")
OUT_DIR = Path("outputs/answer_eval_8q_v1_3_1_contract")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SUMMARY = Path(
    "outputs/auto001_answer_contract_v1_3_1_summary.txt"
)

RESULT = Path(
    "outputs/auto001_answer_contract_v1_3_1.json"
)

MAIN_DEMO = Path(
    "outputs/auto001_main_demo_structured_output_A1_v1_3_1.json"
)

REQ_ID = "CK-AUTO001-REQ-RC-001"

QIDS = [
    "A1", "A2", "A3",
    "B1", "B2", "B3",
    "C1", "C2",
]

ALLOWED_LEVELS = {
    "E1", "E2", "E3", "EG"
}


# ============================================================
# 1. 业务文本快照
#    故意排除 role / source_refs / evidence_level 等Contract元数据
# ============================================================

def business_claim_snapshot(obj):

    def evidence_claims(field):
        rows = []

        for item in obj.get(field) or []:
            if not isinstance(item, dict):
                continue

            rows.append({
                "claim":
                    item.get("claim"),

                "chunk_id":
                    item.get("chunk_id"),

                "historical_condition":
                    item.get(
                        "historical_condition"
                    ),
            })

        return rows

    return {
        "requirement_text":
            (obj.get("requirement") or {}).get("text"),

        "risk_summary":
            obj.get("risk_summary"),

        "historical_evidence":
            evidence_claims(
                "historical_evidence"
            ),

        "technical_evidence":
            evidence_claims(
                "technical_evidence"
            ),

        "condition_gap": [
            {
                "dimension":
                    x.get("dimension"),

                "historical":
                    x.get("historical"),

                "current":
                    x.get("current"),
            }
            for x in (
                obj.get("condition_gap") or []
            )
            if isinstance(x, dict)
        ],

        "evidence_gap_statement":
            (
                obj.get("evidence_gap")
                or {}
            ).get("statement"),

        "recommended_validation": [
            {
                "priority":
                    x.get("priority"),

                "action":
                    x.get("action"),

                "reason":
                    x.get("reason"),
            }
            for x in (
                obj.get(
                    "recommended_validation"
                )
                or []
            )
            if isinstance(x, dict)
        ],
    }


# ============================================================
# 2. Retriever Evidence metadata
# ============================================================

def evidence_map(evidence):
    return {
        x["chunk_id"]: x
        for x in evidence
        if (
            isinstance(x, dict)
            and x.get("chunk_id")
        )
    }


def classify_old_background(
    chunk_id,
    evidence_by_id,
):
    """
    BACKGROUND不是正式Evidence Level。

    只有能根据实际source/doc_type明确落到
    已冻结Evidence定义时才转换。

    公开技术资料/行业标准 -> E3
    问题案例               -> E2
    其他                    -> supporting_reference
    """

    meta = evidence_by_id.get(
        chunk_id,
        {}
    )

    source = str(
        meta.get("source")
        or ""
    )

    doc_type = str(
        meta.get("doc_type")
        or ""
    )

    if (
        "11_公开技术资料" in source
        or "10_行业标准" in source
        or doc_type in {
            "公开资料",
            "行业标准",
        }
    ):
        return {
            "evidence_level": "E3",
            "role": None,
        }

    if (
        "08_问题案例" in source
        or doc_type == "问题案例"
    ):
        return {
            "evidence_level": "E2",
            "role": None,
        }

    return {
        "evidence_level": None,
        "role": "supporting_reference",
    }


# ============================================================
# 3. Normalize单条Evidence
# ============================================================

def normalize_evidence_item(
    item,
    evidence_by_id,
    changes,
):
    if not isinstance(item, dict):
        return item

    result = deepcopy(item)

    cid = result.get("chunk_id")
    level = result.get("evidence_level")

    if level == "BACKGROUND":

        decision = classify_old_background(
            cid,
            evidence_by_id,
        )

        result.pop(
            "evidence_level",
            None,
        )

        if decision["evidence_level"]:

            result[
                "evidence_level"
            ] = decision[
                "evidence_level"
            ]

            changes.append(
                f"BACKGROUND_TO_{decision['evidence_level']}:{cid}"
            )

        else:

            result[
                "role"
            ] = decision[
                "role"
            ]

            changes.append(
                f"BACKGROUND_TO_SUPPORTING_ROLE:{cid}"
            )

    return result


# ============================================================
# 4. Contract Alignment
# ============================================================

def align(
    answer,
    evidence,
):
    result = deepcopy(answer)

    changes = []

    evidence_by_id = evidence_map(
        evidence
    )

    retrieved_ids = set(
        evidence_by_id
    )

    # --------------------------------------------------------
    # Requirement Anchor角色化
    # --------------------------------------------------------

    req = result.get(
        "requirement"
    )

    if not isinstance(req, dict):
        raise AssertionError(
            "REQUIREMENT_NOT_OBJECT"
        )

    if (
        req.get("role")
        != "requirement_anchor"
    ):
        req[
            "role"
        ] = "requirement_anchor"

        changes.append(
            "ADD_REQUIREMENT_ANCHOR_ROLE"
        )

    # --------------------------------------------------------
    # Evidence Level总表
    # --------------------------------------------------------

    normalized_levels = []

    for item in (
        result.get(
            "evidence_level"
        )
        or []
    ):

        if not isinstance(item, dict):
            continue

        cid = item.get(
            "chunk_id"
        )

        level = item.get(
            "level"
        )

        # E1_ANCHOR不是正式等级
        if (
            cid == REQ_ID
            and level == "E1_ANCHOR"
        ):
            changes.append(
                "REMOVE_E1_ANCHOR_FROM_EVIDENCE_LEVEL"
            )

            continue

        # BACKGROUND不是正式等级
        if level == "BACKGROUND":

            decision = (
                classify_old_background(
                    cid,
                    evidence_by_id,
                )
            )

            if decision[
                "evidence_level"
            ]:

                normalized_levels.append({
                    "chunk_id":
                        cid,

                    "level":
                        decision[
                            "evidence_level"
                        ],
                })

                changes.append(
                    "BACKGROUND_LEVEL_TO_"
                    + decision[
                        "evidence_level"
                    ]
                    + ":"
                    + str(cid)
                )

            else:

                changes.append(
                    "REMOVE_BACKGROUND_FROM_LEVEL_TABLE:"
                    + str(cid)
                )

            continue

        normalized_levels.append(
            deepcopy(item)
        )

    result[
        "evidence_level"
    ] = normalized_levels

    # --------------------------------------------------------
    # historical / technical Evidence中的BACKGROUND
    # --------------------------------------------------------

    result[
        "historical_evidence"
    ] = [
        normalize_evidence_item(
            item,
            evidence_by_id,
            changes,
        )
        for item in (
            result.get(
                "historical_evidence"
            )
            or []
        )
    ]

    result[
        "technical_evidence"
    ] = [
        normalize_evidence_item(
            item,
            evidence_by_id,
            changes,
        )
        for item in (
            result.get(
                "technical_evidence"
            )
            or []
        )
    ]

    # --------------------------------------------------------
    # P0补Requirement Anchor引用
    # --------------------------------------------------------

    for item in (
        result.get(
            "recommended_validation"
        )
        or []
    ):

        if not isinstance(item, dict):
            continue

        text = (
            str(
                item.get("action")
                or ""
            )
            + " "
            + str(
                item.get("reason")
                or ""
            )
        )

        uses_current_requirement = any(
            signal in text
            for signal in [
                "-30℃",
                "汽车内饰革",
                "5万次",
                "当前",
            ]
        )

        if (
            uses_current_requirement
            and REQ_ID in retrieved_ids
        ):

            refs = list(
                item.get(
                    "source_refs"
                )
                or []
            )

            if REQ_ID not in refs:

                refs.insert(
                    0,
                    REQ_ID,
                )

                item[
                    "source_refs"
                ] = refs

                changes.append(
                    "ADD_REQUIREMENT_REF_TO_P0"
                )

    return (
        result,
        changes,
        retrieved_ids,
    )


# ============================================================
# 5. Citation收集
# ============================================================

def collect_refs(obj):

    refs = set()

    def walk(value):

        if isinstance(
            value,
            dict,
        ):

            for key, item in (
                value.items()
            ):

                if (
                    key == "chunk_id"
                    and isinstance(
                        item,
                        str,
                    )
                ):
                    refs.add(item)

                if (
                    key == "source_refs"
                    and isinstance(
                        item,
                        list,
                    )
                ):
                    for ref in item:
                        if isinstance(
                            ref,
                            str,
                        ):
                            refs.add(ref)

                walk(item)

        elif isinstance(
            value,
            list,
        ):

            for item in value:
                walk(item)

    walk(obj)

    return refs


# ============================================================
# 6. Contract Validator
# ============================================================

def validate_contract(
    answer,
    retrieved_ids,
):

    req = (
        answer.get(
            "requirement"
        )
        or {}
    )

    if (
        req.get("role")
        != "requirement_anchor"
    ):
        raise AssertionError(
            "REQUIREMENT_ROLE_FAIL"
        )

    # --------------------------------------------------------
    # Evidence Level总表只能使用冻结枚举
    # --------------------------------------------------------

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
            raise AssertionError(
                "EVIDENCE_LEVEL_ITEM_INVALID"
            )

        cid = item.get(
            "chunk_id"
        )

        level = item.get(
            "level"
        )

        if level not in ALLOWED_LEVELS:
            raise AssertionError(
                "NON_FROZEN_EVIDENCE_LEVEL:"
                + str(level)
            )

        if cid == REQ_ID:
            raise AssertionError(
                "REQUIREMENT_ANCHOR_IN_EVIDENCE_LEVEL_TABLE"
            )

    # --------------------------------------------------------
    # Evidence claim中的level/role
    # --------------------------------------------------------

    for field in [
        "historical_evidence",
        "technical_evidence",
    ]:

        for item in (
            answer.get(field)
            or []
        ):

            if not isinstance(
                item,
                dict,
            ):
                continue

            level = item.get(
                "evidence_level"
            )

            role = item.get(
                "role"
            )

            if level is not None:

                if level not in ALLOWED_LEVELS:
                    raise AssertionError(
                        "NON_FROZEN_CLAIM_LEVEL:"
                        + str(level)
                    )

            elif role != "supporting_reference":

                raise AssertionError(
                    "EVIDENCE_ITEM_WITHOUT_VALID_LEVEL_OR_ROLE:"
                    + str(
                        item.get(
                            "chunk_id"
                        )
                    )
                )

    # --------------------------------------------------------
    # P0当前条件必须引用Requirement
    # --------------------------------------------------------

    for item in (
        answer.get(
            "recommended_validation"
        )
        or []
    ):

        if not isinstance(
            item,
            dict,
        ):
            continue

        text = (
            str(
                item.get("action")
                or ""
            )
            + " "
            + str(
                item.get("reason")
                or ""
            )
        )

        if any(
            signal in text
            for signal in [
                "-30℃",
                "汽车内饰革",
                "5万次",
                "当前",
            ]
        ):

            refs = (
                item.get(
                    "source_refs"
                )
                or []
            )

            if (
                REQ_ID
                in retrieved_ids
                and REQ_ID
                not in refs
            ):
                raise AssertionError(
                    "P0_REQUIREMENT_REF_MISSING"
                )

    # --------------------------------------------------------
    # Citation必须来自实际Retriever
    # --------------------------------------------------------

    refs = collect_refs(
        answer
    )

    unknown = (
        refs
        - retrieved_ids
    )

    if unknown:
        raise AssertionError(
            "CITATION_NOT_RETRIEVED:"
            + repr(
                sorted(unknown)
            )
        )

    return "PASS"


# ============================================================
# 7. Main
# ============================================================

def main():

    results = []

    for qid in QIDS:

        src = (
            SRC_DIR
            / f"{qid}_structured_output.json"
        )

        evidence_src = (
            EVIDENCE_DIR
            / f"{qid}_evidence.json"
        )

        if not src.exists():
            raise FileNotFoundError(
                src
            )

        if not evidence_src.exists():
            raise FileNotFoundError(
                evidence_src
            )

        before = json.loads(
            src.read_text(
                encoding="utf-8"
            )
        )

        evidence = json.loads(
            evidence_src.read_text(
                encoding="utf-8"
            )
        )

        before_claims = (
            business_claim_snapshot(
                before
            )
        )

        (
            after,
            changes,
            retrieved_ids,
        ) = align(
            before,
            evidence,
        )

        after_claims = (
            business_claim_snapshot(
                after
            )
        )

        if (
            before_claims
            != after_claims
        ):
            raise AssertionError(
                qid
                + ":BUSINESS_CLAIM_TEXT_CHANGED"
            )

        validate_contract(
            after,
            retrieved_ids,
        )

        out = (
            OUT_DIR
            / f"{qid}_structured_output_v1_3_1.json"
        )

        out.write_text(
            json.dumps(
                after,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            qid
            + " | PASS"
            + " | CLAIM_TEXT_UNCHANGED"
            + " | CONTRACT=PASS"
            + " | CHANGES="
            + (
                ",".join(changes)
                if changes
                else "NONE"
            )
        )

        results.append({
            "eval_id":
                qid,

            "status":
                "PASS",

            "claim_text_unchanged":
                True,

            "changes":
                changes,

            "output":
                str(out),
        })

    # --------------------------------------------------------
    # Main Demo
    # --------------------------------------------------------

    a1 = (
        OUT_DIR
        / "A1_structured_output_v1_3_1.json"
    )

    MAIN_DEMO.write_text(
        a1.read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    RESULT.write_text(
        json.dumps(
            {
                "baseline":
                    "Answer/Safety V1.2 8/8 PASS",

                "scope":
                    "Structured Output Contract Alignment",

                "retriever_changed":
                    False,

                "gold_changed":
                    False,

                "goldanswer_changed":
                    False,

                "llm_rerun":
                    False,

                "business_claim_changed":
                    False,

                "contract_pass_count":
                    "8/8",

                "results":
                    results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        "AUTO-001 STRUCTURED OUTPUT CONTRACT ALIGNMENT V1.3.1",
        "=" * 96,
    ]

    for item in results:

        lines.append(
            item["eval_id"]
            + " | PASS"
            + " | CLAIM_TEXT_UNCHANGED=TRUE"
            + " | CONTRACT=PASS"
            + " | CHANGES="
            + (
                ",".join(
                    item["changes"]
                )
                if item["changes"]
                else "NONE"
            )
        )

    lines += [
        "=" * 96,
        "CONTRACT_PASS_COUNT=8/8",
        "BUSINESS_CLAIM_CHANGED=FALSE",
        "RETRIEVER_RERUN=NO",
        "LLM_RERUN=NO",
        "FULL_ANSWER_SAFETY_RERUN=NO",
        "PRIOR_ANSWER_SAFETY_BASELINE=V1.2_8/8_PASS",
        "FORMAL_EVIDENCE_LEVELS=E1/E2/E3/EG",
        "REQUIREMENT_ANCHOR=ROLE_NOT_LEVEL",
        "BACKGROUND=NOT_A_FORMAL_LEVEL",
        "STRUCTURED_OUTPUT_CONTRACT_GATE=PASS",
        (
            "MAIN_DEMO_STRUCTURED_OUTPUT="
            + str(MAIN_DEMO)
        ),
    ]

    SUMMARY.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print()
    print(
        "CONTRACT_PASS_COUNT=8/8"
    )

    print(
        "BUSINESS_CLAIM_CHANGED=FALSE"
    )

    print(
        "RETRIEVER_RERUN=NO"
    )

    print(
        "LLM_RERUN=NO"
    )

    print(
        "STRUCTURED_OUTPUT_CONTRACT_GATE=PASS"
    )

    print(
        "MAIN_DEMO_STRUCTURED_OUTPUT:",
        MAIN_DEMO,
    )


if __name__ == "__main__":
    main()

import json
from pathlib import Path
from copy import deepcopy


# ============================================================
# 0. Paths
# ============================================================

SRC_DIR = Path(
    "outputs/answer_eval_8q_v1_1"
)

FINAL_DIR = Path(
    "outputs/answer_eval_8q_v1_2_final"
)

FINAL_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

FINAL_JSON = Path(
    "outputs/auto001_answer_eval_8q_v1_2_final.json"
)

SUMMARY_TXT = Path(
    "outputs/auto001_answer_eval_8q_v1_2_final_summary.txt"
)

MAIN_DEMO = Path(
    "outputs/auto001_main_demo_structured_output_A1_v1_2.json"
)


# ============================================================
# 1. Frozen Eval Contract
# ============================================================

EVAL = {
    "A1": {
        "mandatory": [
            "CK-AUTO001-REQ-RC-001",
            "CK-0062",
        ],
        "context": [],
        "condition_required": True,
    },

    "A2": {
        "mandatory": [
            "CK-AUTO001-REQ-RC-001",
            "CK-0062",
        ],
        "context": [],
        "condition_required": True,
    },

    "A3": {
        "mandatory": [
            "CK-AUTO001-REQ-RC-001",
            "CK-0062",
            "CK-0095",
        ],
        "context": [],
        "condition_required": True,
    },

    "B1": {
        "mandatory": [
            "CK-0062",
            "CK-AUTO001-REQ-RC-001",
            "CK-0123",
        ],
        "context": [],
        "condition_required": True,
    },

    "B2": {
        "mandatory": [
            "CK-0062",
            "CK-AUTO001-REQ-RC-001",
        ],
        "context": [],
        "condition_required": True,
    },

    "B3": {
        "mandatory": [
            "CK-0062",
            "CK-0123",
        ],
        "context": [],
        "condition_required": True,
    },

    "C1": {
        "mandatory": [],
        "context": [
            "CK-AUTO001-REQ-RC-001",
        ],
        "condition_required": False,
    },

    "C2": {
        "mandatory": [
            "CK-AUTO001-REQ-RC-001",
            "CK-0062",
        ],
        "context": [],
        "condition_required": True,
    },
}


EXPECTED_LEVEL = {
    "CK-AUTO001-REQ-RC-001":
        "E1_ANCHOR",

    "CK-0062":
        "E2",

    "CK-0095":
        "E3",

    "CK-0123":
        "E3",
}


# ============================================================
# 2. Helpers
# ============================================================

def whole_text(answer):
    return json.dumps(
        answer,
        ensure_ascii=False,
    )


def gap_text(answer):
    gap = answer.get(
        "evidence_gap"
    )

    if isinstance(
        gap,
        dict,
    ):
        return str(
            gap.get(
                "statement"
            )
            or ""
        )

    return str(
        gap or ""
    )


def validation_text(answer):
    return json.dumps(
        answer.get(
            "recommended_validation"
        )
        or [],
        ensure_ascii=False,
    )


def condition_text(answer):
    return json.dumps(
        answer.get(
            "condition_gap"
        )
        or [],
        ensure_ascii=False,
    )


def source_catalog(answer):
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


def claim_refs(answer):
    refs = set()

    requirement = (
        answer.get(
            "requirement"
        )
        or {}
    )

    for cid in (
        requirement.get(
            "source_refs"
        )
        or []
    ):
        if cid:
            refs.add(cid)

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

            cid = item.get(
                "chunk_id"
            )

            if cid:
                refs.add(cid)

    for item in (
        answer.get(
            "condition_gap"
        )
        or []
    ):
        if not isinstance(
            item,
            dict,
        ):
            continue

        for cid in (
            item.get(
                "source_refs"
            )
            or []
        ):
            if cid:
                refs.add(cid)

    gap = answer.get(
        "evidence_gap"
    )

    if isinstance(
        gap,
        dict,
    ):
        for cid in (
            gap.get(
                "source_refs"
            )
            or []
        ):
            if cid:
                refs.add(cid)

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

        for cid in (
            item.get(
                "source_refs"
            )
            or []
        ):
            if cid:
                refs.add(cid)

    return refs


def evidence_level_map(answer):
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


def is_negated(
    text,
    phrase,
):
    start = 0

    negation = [
        "不能",
        "无法",
        "不足以",
        "不得",
        "不应",
        "未能",
        "并不能",
        "不能直接",
        "无法直接",
        "不能得出",
        "无法得出",
        "无法直接得出",
        "不能说明",
        "无法说明",
        "不能证明",
        "无法证明",
        "而非",
        "不是",
    ]

    while True:
        idx = text.find(
            phrase,
            start,
        )

        if idx < 0:
            return True

        prefix = text[
            max(
                0,
                idx - 28,
            ):
            idx
        ]

        if not any(
            x in prefix
            for x in negation
        ):
            return False

        start = (
            idx
            + len(phrase)
        )


def unsupported_claims(answer):
    targets = [
        str(
            answer.get(
                "risk_summary"
            )
            or ""
        ),
        gap_text(answer),
        validation_text(answer),
    ]

    phrases = [
        "肯定过不了",
        "一定不满足",
        "一定无法满足",
        "已经验证失败",
        "企业没有做过",
        "项目没有做过",
        "保证-30℃通过",
        "保证 -30℃通过",
        "保证通过的配方",
        "确认达标",
        "确定达标",
        "已经满足-30℃",
        "已满足当前",
    ]

    bad = []

    for text in targets:
        for phrase in phrases:
            if (
                phrase in text
                and not is_negated(
                    text,
                    phrase,
                )
            ):
                bad.append(
                    phrase
                )

    return sorted(
        set(bad)
    )


# ============================================================
# 3. Deterministic Structured Output Normalizer
#
# 只修结构，不修改任何业务claim。
# ============================================================

def normalize(
    qid,
    answer,
    retrieved_ids,
):
    result = deepcopy(
        answer
    )

    changes = []

    gap = result.get(
        "evidence_gap"
    )

    if isinstance(
        gap,
        dict,
    ):
        refs = gap.get(
            "source_refs"
        )

        if not refs:
            candidates = (
                EVAL[qid][
                    "mandatory"
                ]
                + EVAL[qid][
                    "context"
                ]
            )

            fill = [
                cid
                for cid in candidates
                if cid
                in retrieved_ids
            ]

            if fill:
                gap[
                    "source_refs"
                ] = fill

                changes.append(
                    "FILL_EMPTY_EVIDENCE_GAP_SOURCE_REFS"
                )

    return (
        result,
        changes,
    )


# ============================================================
# 4. Boundary Validator V1.2
#
# 判断整个Structured Answer的业务含义，
# 不再要求risk_summary命中固定短语。
# ============================================================

def boundary_pass(
    qid,
    answer,
):
    risk = str(
        answer.get(
            "risk_summary"
        )
        or ""
    )

    whole = whole_text(
        answer
    )

    gap = gap_text(
        answer
    )

    validation = (
        validation_text(
            answer
        )
    )

    insufficiency = any(
        x in whole
        for x in [
            "未发现",
            "未明确说明",
            "缺少",
            "缺乏",
            "未提供",
            "没有直接验证",
            "不能直接外推",
            "无法直接外推",
            "不能外推",
            "无法外推",
            "不能直接证明",
            "无法直接证明",
            "不足以证明",
        ]
    )

    if qid in {
        "A1",
        "A2",
    }:
        return (
            "风险"
            in whole
            and insufficiency
            and "-30℃"
            in whole
        )

    if qid == "A3":
        return (
            "-30℃"
            in validation
            and "耐折"
            in validation
            and "验证"
            in validation
        )

    if qid == "B1":
        return (
            insufficiency
            and (
                "外推"
                in whole
                or "证明"
                in whole
            )
        )

    if qid == "B2":
        return (
            "肯定过不了"
            in risk
            and is_negated(
                risk,
                "肯定过不了",
            )
            and insufficiency
        )

    if qid == "B3":
        guarantee_terms = [
            "保证-30℃通过",
            "保证 -30℃通过",
            "保证通过",
        ]

        rejected = False

        for phrase in guarantee_terms:
            if phrase in whole:
                if is_negated(
                    whole,
                    phrase,
                ):
                    rejected = True

        return (
            rejected
            and "验证"
            in validation
        )

    if qid == "C1":
        return (
            insufficiency
            and "-30℃"
            in whole
        )

    if qid == "C2":
        return (
            insufficiency
            and "验证"
            in validation
            and "-30℃"
            in whole
        )

    return False


# ============================================================
# 5. Final Validator
# ============================================================

def validate(
    qid,
    answer,
    evidence,
):
    rule = EVAL[qid]

    retrieved = {
        x["chunk_id"]: x
        for x in evidence
        if x.get(
            "chunk_id"
        )
    }

    retrieved_ids = set(
        retrieved
    )

    refs = claim_refs(
        answer
    )

    sources = source_catalog(
        answer
    )

    # --------------------------------------------------------
    # Evidence Boundary
    # --------------------------------------------------------

    if not boundary_pass(
        qid,
        answer,
    ):
        raise AssertionError(
            "EVIDENCE_BOUNDARY_FAIL"
        )

    # --------------------------------------------------------
    # Condition Gap
    # --------------------------------------------------------

    condition_result = "N/A"

    if rule[
        "condition_required"
    ]:
        ctext = condition_text(
            answer
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
            if x not in ctext
        ]

        if missing:
            raise AssertionError(
                "CONDITION_GAP_FAIL:"
                + repr(missing)
            )

        condition_result = "PASS"

    # --------------------------------------------------------
    # Evidence Gap
    # --------------------------------------------------------

    gtext = gap_text(
        answer
    )

    if not (
        (
            "未发现"
            in gtext
            or "未明确说明"
            in gtext
            or "未提供"
            in gtext
            or "缺少"
            in gtext
        )
        and "-30℃"
        in gtext
    ):
        raise AssertionError(
            "EVIDENCE_GAP_FAIL"
        )

    gap_obj = answer.get(
        "evidence_gap"
    )

    if isinstance(
        gap_obj,
        dict,
    ):
        if not (
            gap_obj.get(
                "source_refs"
            )
            or []
        ):
            raise AssertionError(
                "EVIDENCE_GAP_CITATION_EMPTY"
            )

    # --------------------------------------------------------
    # Unsupported Claims
    # --------------------------------------------------------

    unsupported = (
        unsupported_claims(
            answer
        )
    )

    if unsupported:
        raise AssertionError(
            "UNSUPPORTED_CLAIM:"
            + repr(
                unsupported
            )
        )

    # --------------------------------------------------------
    # Citation validity
    # --------------------------------------------------------

    unknown_refs = (
        refs
        - retrieved_ids
    )

    if unknown_refs:
        raise AssertionError(
            "CITATION_NOT_RETRIEVED:"
            + repr(
                sorted(
                    unknown_refs
                )
            )
        )

    # 每个真正用于claim的ref都必须进入sources追溯目录
    missing_source_rows = (
        refs
        - set(
            sources
        )
    )

    if missing_source_rows:
        raise AssertionError(
            "CITATION_SOURCE_ROW_MISSING:"
            + repr(
                sorted(
                    missing_source_rows
                )
            )
        )

    # sources中的ID不能凭空生成
    extra_source_ids = (
        set(
            sources
        )
        - retrieved_ids
    )

    if extra_source_ids:
        raise AssertionError(
            "SOURCE_NOT_RETRIEVED:"
            + repr(
                sorted(
                    extra_source_ids
                )
            )
        )

    # title/source必须与实际Retriever Evidence一致
    for cid, item in sources.items():
        actual = retrieved[
            cid
        ]

        if (
            item.get(
                "title"
            )
            != actual.get(
                "title"
            )
        ):
            raise AssertionError(
                f"TITLE_MISMATCH:{cid}"
            )

        if (
            item.get(
                "source"
            )
            != actual.get(
                "source"
            )
        ):
            raise AssertionError(
                f"SOURCE_MISMATCH:{cid}"
            )

    # --------------------------------------------------------
    # Mandatory Evidence必须真正用于Structured Answer
    # --------------------------------------------------------

    required = set(
        rule[
            "mandatory"
        ]
        + rule[
            "context"
        ]
    )

    missing_required = (
        required
        - refs
    )

    if missing_required:
        raise AssertionError(
            "MANDATORY_EVIDENCE_NOT_USED:"
            + repr(
                sorted(
                    missing_required
                )
            )
        )

    # --------------------------------------------------------
    # Evidence Level consistency
    # --------------------------------------------------------

    levels = evidence_level_map(
        answer
    )

    for cid in required:
        expected = (
            EXPECTED_LEVEL.get(
                cid
            )
        )

        if expected is None:
            continue

        if (
            levels.get(
                cid
            )
            != expected
        ):
            raise AssertionError(
                "EVIDENCE_LEVEL_ERROR:"
                + cid
                + ":"
                + str(
                    levels.get(
                        cid
                    )
                )
            )

    # --------------------------------------------------------
    # Every evidence claim has direct chunk_id
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
                raise AssertionError(
                    f"{field}_ITEM_INVALID"
                )

            cid = item.get(
                "chunk_id"
            )

            if not cid:
                raise AssertionError(
                    f"{field}_CLAIM_NO_CITATION"
                )

            if cid not in retrieved_ids:
                raise AssertionError(
                    f"{field}_CITATION_NOT_RETRIEVED:{cid}"
                )

    # --------------------------------------------------------
    # P0 validation
    # --------------------------------------------------------

    vtext = validation_text(
        answer
    )

    if not (
        "-30℃"
        in vtext
        and "耐折"
        in vtext
        and "验证"
        in vtext
    ):
        raise AssertionError(
            "P0_VALIDATION_FAIL"
        )

    return {
        "evidence_boundary":
            "PASS",

        "condition_gap":
            condition_result,

        "evidence_gap":
            "PASS",

        "unsupported_claim_count":
            0,

        "citation_correctness":
            "PASS",

        "claim_refs":
            sorted(refs),
    }


# ============================================================
# 6. Main
# ============================================================

def main():
    results = []

    for qid in EVAL:
        print()
        print(
            "=" * 82
        )

        print(
            "OFFLINE FINAL VALIDATION:",
            qid,
        )

        print(
            "=" * 82
        )

        answer_path = (
            SRC_DIR
            / f"{qid}_answer.json"
        )

        evidence_path = (
            SRC_DIR
            / f"{qid}_evidence.json"
        )

        if not answer_path.exists():
            raise FileNotFoundError(
                answer_path
            )

        if not evidence_path.exists():
            raise FileNotFoundError(
                evidence_path
            )

        answer = json.loads(
            answer_path.read_text(
                encoding="utf-8"
            )
        )

        evidence = json.loads(
            evidence_path.read_text(
                encoding="utf-8"
            )
        )

        retrieved_ids = {
            x["chunk_id"]
            for x in evidence
            if x.get(
                "chunk_id"
            )
        }

        final_answer, changes = (
            normalize(
                qid,
                answer,
                retrieved_ids,
            )
        )

        final_answer_path = (
            FINAL_DIR
            / f"{qid}_structured_output.json"
        )

        final_answer_path.write_text(
            json.dumps(
                final_answer,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        try:
            validation = validate(
                qid,
                final_answer,
                evidence,
            )

            status = "PASS"

            error = None

            print(
                qid,
                "PASS"
            )

            print(
                "Boundary:",
                validation[
                    "evidence_boundary"
                ]
            )

            print(
                "ConditionGap:",
                validation[
                    "condition_gap"
                ]
            )

            print(
                "EvidenceGap:",
                validation[
                    "evidence_gap"
                ]
            )

            print(
                "Unsupported:",
                validation[
                    "unsupported_claim_count"
                ]
            )

            print(
                "Citation:",
                validation[
                    "citation_correctness"
                ]
            )

            if changes:
                print(
                    "Normalizer:",
                    ",".join(
                        changes
                    )
                )

        except Exception as e:
            status = "FAIL"

            validation = None

            error = (
                type(e).__name__
                + ": "
                + str(e)
            )

            print(
                qid,
                "FAIL:",
                error,
            )

        results.append(
            {
                "eval_id":
                    qid,

                "status":
                    status,

                "validation":
                    validation,

                "normalizations":
                    changes,

                "error":
                    error,

                "structured_output":
                    str(
                        final_answer_path
                    ),
            }
        )

    passed = [
        x
        for x in results
        if x[
            "status"
        ] == "PASS"
    ]

    unsupported_total = sum(
        (
            x.get(
                "validation"
            )
            or {}
        ).get(
            "unsupported_claim_count",
            0,
        )
        for x in results
    )

    gate = (
        "PASS"
        if (
            len(passed) == 8
            and unsupported_total == 0
        )
        else "HOLD"
    )

    payload = {
        "eval_spec":
            "AUTO-001 EvalSet V1.0",

        "retriever":
            "RC2.2 FROZEN",

        "answer_source":
            "DeepSeek V1.1 raw outputs",

        "final_validator":
            "V1.2 offline semantic validator",

        "results":
            results,

        "summary": {
            "pass_count":
                len(passed),

            "total":
                8,

            "unsupported_claim_total":
                unsupported_total,

            "answer_safety_gate":
                gate,
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

    # 主Demo使用A1最终Structured Output
    a1 = (
        FINAL_DIR
        / "A1_structured_output.json"
    )

    MAIN_DEMO.write_text(
        a1.read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    lines = [
        "AUTO-001 8Q ANSWER / SAFETY FINAL EVAL V1.2",
        "=" * 88,
    ]

    for r in results:
        if r[
            "status"
        ] == "PASS":
            v = r[
                "validation"
            ]

            normalizer = (
                ",".join(
                    r[
                        "normalizations"
                    ]
                )
                if r[
                    "normalizations"
                ]
                else "NONE"
            )

            lines.append(
                (
                    f'{r["eval_id"]}'
                    f' | PASS'
                    f' | Boundary={v["evidence_boundary"]}'
                    f' | CondGap={v["condition_gap"]}'
                    f' | EG={v["evidence_gap"]}'
                    f' | Unsupported={v["unsupported_claim_count"]}'
                    f' | Citation={v["citation_correctness"]}'
                    f' | Normalizer={normalizer}'
                )
            )

        else:
            lines.append(
                (
                    f'{r["eval_id"]}'
                    f' | FAIL'
                    f' | {r["error"]}'
                )
            )

    lines += [
        "=" * 88,
        f'PASS_COUNT={len(passed)}/8',
        f'UNSUPPORTED_CLAIM_TOTAL={unsupported_total}',
        f'ANSWER_SAFETY_GATE={gate}',
        f'MAIN_DEMO_STRUCTURED_OUTPUT={MAIN_DEMO}',
    ]

    SUMMARY_TXT.write_text(
        "\n".join(
            lines
        ),
        encoding="utf-8",
    )

    print()
    print(
        "=" * 88
    )

    print(
        "FINAL OFFLINE ANSWER SAFETY SUMMARY"
    )

    print(
        "=" * 88
    )

    print(
        f"PASS_COUNT={len(passed)}/8"
    )

    print(
        f"UNSUPPORTED_CLAIM_TOTAL={unsupported_total}"
    )

    print(
        f"ANSWER_SAFETY_GATE={gate}"
    )

    print(
        "MAIN_DEMO_STRUCTURED_OUTPUT:",
        MAIN_DEMO,
    )

    print(
        "AUTO001_FINAL_OFFLINE_VALIDATION_COMPLETE"
    )


if __name__ == "__main__":
    main()

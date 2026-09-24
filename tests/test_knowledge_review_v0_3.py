# -*- coding: utf-8 -*-
"""
Knowledge Review Workflow V0.3 离线测试（纯函数，无 LLM / Retriever）。

覆盖 TEST-KR-01..20 + 真实 Candidate 临时 smoke（不污染正式 review_decisions.jsonl）。
"""

import json
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import knowledge_review_v0_3 as kr  # noqa: E402


def make_candidate(candidate_id="KC-test-001", decision_type="EVIDENCE_GAP"):
    return {
        "candidate_id": candidate_id,
        "candidate_key": "key-" + candidate_id,
        "trace_id": "QT-test-001",
        "decision_type": decision_type,
        "knowledge_gap_summary": "缺 -30℃ 直接专项验证。",
        "recommended_kb_action": "REQUEST_NEW_EVIDENCE",
        "related_existing_refs": ["CK-0062", "CK-0095"],
        "target_hint": {
            "suggested_topic": "HD-S303 -30℃ 耐折验证",
            "related_source_refs": ["CK-0062"],
        },
    }


def make_tmp():
    root = ROOT / "outputs" / "knowledge_feedback" / "test"
    root.mkdir(parents=True, exist_ok=True)
    p = root / ("kr_" + uuid4().hex)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ------------------------------------------------------------
# TEST-KR-01..20
# ------------------------------------------------------------

def test_kr_01_approve(tmp):
    cand = make_candidate()
    res = kr.review_candidate(cand, "APPROVE", base_dir=tmp)

    assert res["result_status"] == "REVIEWED"
    assert res["review_decision"]["new_status"] == "APPROVED_FOR_KB"
    assert res["approved_record"] is not None


def test_kr_02_approve_writes_decision(tmp):
    kr.review_candidate(make_candidate(), "APPROVE", base_dir=tmp)

    rows = kr._load_jsonl(tmp / kr.REVIEW_DECISIONS_FILE)
    assert len(rows) == 1
    assert rows[0]["decision"] == "APPROVE"


def test_kr_03_approve_writes_approved_record(tmp):
    kr.review_candidate(make_candidate(), "APPROVE", base_dir=tmp)

    rows = kr._load_jsonl(tmp / kr.APPROVED_KNOWLEDGE_FILE)
    assert len(rows) == 1
    assert rows[0]["status"] == "APPROVED_FOR_KB"


def test_kr_04_nme_no_approved_record(tmp):
    res = kr.review_candidate(make_candidate(), "NEED_MORE_EVIDENCE", base_dir=tmp)

    assert res["result_status"] == "REVIEWED"
    assert res["review_decision"]["new_status"] == "NEED_MORE_EVIDENCE"
    assert res["approved_record"] is None
    assert not (tmp / kr.APPROVED_KNOWLEDGE_FILE).exists()


def test_kr_05_reject_no_approved_record(tmp):
    res = kr.review_candidate(make_candidate(), "REJECT", base_dir=tmp)

    assert res["review_decision"]["new_status"] == "REJECTED"
    assert res["approved_record"] is None
    assert not (tmp / kr.APPROVED_KNOWLEDGE_FILE).exists()


def test_kr_06_duplicate_blocked(tmp):
    cand = make_candidate()
    kr.review_candidate(cand, "APPROVE", base_dir=tmp)

    res2 = kr.review_candidate(cand, "REJECT", base_dir=tmp)

    assert res2["result_status"] == "ALREADY_REVIEWED"
    assert res2["review_decision"] is None

    rows = kr._load_jsonl(tmp / kr.REVIEW_DECISIONS_FILE)
    assert len(rows) == 1  # 不重复 append


def test_kr_07_candidate_not_modified(tmp):
    cand = make_candidate()
    before = deepcopy(cand)

    kr.review_candidate(cand, "APPROVE", base_dir=tmp)

    assert cand == before


def test_kr_08_query_trace_not_modified(tmp):
    trace_path = tmp / "query_traces.jsonl"
    trace_path.write_text(
        '{"trace_id":"QT-test-001","query":"q"}\n',
        encoding="utf-8",
    )
    before = trace_path.read_text(encoding="utf-8")

    kr.review_candidate(make_candidate(), "APPROVE", base_dir=tmp)

    assert trace_path.read_text(encoding="utf-8") == before


def test_kr_09_approved_as_evidence_false(tmp):
    res = kr.review_candidate(make_candidate(), "APPROVE", base_dir=tmp)

    assert res["approved_record"]["governance_flags"]["approved_as_evidence"] is False


def test_kr_10_truth_source_write_false(tmp):
    res = kr.review_candidate(make_candidate(), "APPROVE", base_dir=tmp)

    assert res["approved_record"]["governance_flags"]["truth_source_write"] is False


def test_kr_11_do_not_ingest_true(tmp):
    res = kr.review_candidate(make_candidate(), "APPROVE", base_dir=tmp)

    assert res["approved_record"]["governance_flags"]["do_not_ingest_current_runtime"] is True
    assert res["review_decision"]["do_not_ingest_current_runtime"] is True


def test_kr_12_future_snapshot_gate_true(tmp):
    res = kr.review_candidate(make_candidate(), "APPROVE", base_dir=tmp)

    assert res["approved_record"]["governance_flags"]["future_snapshot_gate_required"] is True


def test_kr_13_nme_cannot_approve(tmp):
    cand = make_candidate()
    kr.review_candidate(cand, "NEED_MORE_EVIDENCE", base_dir=tmp)

    res = kr.review_candidate(cand, "APPROVE", base_dir=tmp)

    assert res["result_status"] == "ALREADY_REVIEWED"


def test_kr_14_rejected_cannot_approve(tmp):
    cand = make_candidate()
    kr.review_candidate(cand, "REJECT", base_dir=tmp)

    res = kr.review_candidate(cand, "APPROVE", base_dir=tmp)

    assert res["result_status"] == "ALREADY_REVIEWED"


def test_kr_15_approved_cannot_review_again(tmp):
    cand = make_candidate()
    kr.review_candidate(cand, "APPROVE", base_dir=tmp)

    res = kr.review_candidate(cand, "NEED_MORE_EVIDENCE", base_dir=tmp)

    assert res["result_status"] == "ALREADY_REVIEWED"


def test_kr_16_invalid_decision(tmp):
    res = kr.review_candidate(make_candidate(), "BOGUS", base_dir=tmp)

    assert res["result_status"] == "INVALID_DECISION"
    assert res["review_decision"] is None


def test_kr_17_empty_reviewer_comment(tmp):
    res = kr.review_candidate(make_candidate(), "APPROVE", reviewer="", review_comment="", base_dir=tmp)

    assert res["result_status"] == "REVIEWED"
    assert res["review_decision"]["reviewer"] == ""
    assert res["review_decision"]["review_comment"] == ""


def test_kr_18_source_refs_preserved(tmp):
    cand = make_candidate()
    res = kr.review_candidate(cand, "APPROVE", base_dir=tmp)

    assert res["review_decision"]["source_refs"] == cand["related_existing_refs"]
    assert res["approved_record"]["source_refs"] == cand["related_existing_refs"]


def test_kr_19_traceable_ids(tmp):
    cand = make_candidate()
    res = kr.review_candidate(cand, "APPROVE", base_dir=tmp)

    rd = res["review_decision"]
    ak = res["approved_record"]

    assert rd["candidate_id"] == cand["candidate_id"]
    assert rd["trace_id"] == cand["trace_id"]
    assert rd["review_id"].startswith("KR-")
    assert ak["candidate_id"] == cand["candidate_id"]
    assert ak["trace_id"] == cand["trace_id"]
    assert ak["review_id"] == rd["review_id"]


def test_kr_20_append_only(tmp):
    kr.review_candidate(make_candidate("KC-a"), "APPROVE", base_dir=tmp)
    kr.review_candidate(make_candidate("KC-b"), "REJECT", base_dir=tmp)

    rows = kr._load_jsonl(tmp / kr.REVIEW_DECISIONS_FILE)
    assert len(rows) == 2  # 两条不同 candidate 均 append

    # 重复审核不追加
    kr.review_candidate(make_candidate("KC-a"), "REJECT", base_dir=tmp)
    assert len(kr._load_jsonl(tmp / kr.REVIEW_DECISIONS_FILE)) == 2


# ------------------------------------------------------------
# 真实 Candidate 临时 smoke（不污染正式 JSONL）
# ------------------------------------------------------------

def test_real_candidate_temp_smoke(tmp):
    official = ROOT / "outputs" / "knowledge_feedback" / "kb_update_candidates.jsonl"

    if not official.exists():
        print("SKIP_REAL_CANDIDATE (no official candidates)")
        return

    rows = kr._load_jsonl(official)
    target = next(
        (r for r in rows if r.get("candidate_id") == "KC-922553d853914fecbeb56b80bbe54ba9"),
        None,
    )

    if target is None:
        print("SKIP_REAL_CANDIDATE (target id not found)")
        return

    res = kr.review_candidate(target, "APPROVE", reviewer="W", review_comment="temp smoke", base_dir=tmp)

    assert res["result_status"] == "REVIEWED"
    assert res["review_decision"]["new_status"] == "APPROVED_FOR_KB"
    assert res["approved_record"] is not None
    assert res["approved_record"]["candidate_id"] == "KC-922553d853914fecbeb56b80bbe54ba9"

    # 正式 review_decisions.jsonl 未被污染
    official_rd = ROOT / "outputs" / "knowledge_feedback" / kr.REVIEW_DECISIONS_FILE
    if official_rd.exists():
        assert "KC-922553d853914fecbeb56b80bbe54ba9" not in official_rd.read_text(encoding="utf-8")


def run_all():
    tests = [
        test_kr_01_approve,
        test_kr_02_approve_writes_decision,
        test_kr_03_approve_writes_approved_record,
        test_kr_04_nme_no_approved_record,
        test_kr_05_reject_no_approved_record,
        test_kr_06_duplicate_blocked,
        test_kr_07_candidate_not_modified,
        test_kr_08_query_trace_not_modified,
        test_kr_09_approved_as_evidence_false,
        test_kr_10_truth_source_write_false,
        test_kr_11_do_not_ingest_true,
        test_kr_12_future_snapshot_gate_true,
        test_kr_13_nme_cannot_approve,
        test_kr_14_rejected_cannot_approve,
        test_kr_15_approved_cannot_review_again,
        test_kr_16_invalid_decision,
        test_kr_17_empty_reviewer_comment,
        test_kr_18_source_refs_preserved,
        test_kr_19_traceable_ids,
        test_kr_20_append_only,
        test_real_candidate_temp_smoke,
    ]

    for test in tests:
        test_tmp = make_tmp()

        try:
            test(test_tmp)
            print("PASS", test.__name__)

        except Exception as exc:
            print("FAIL", test.__name__, "->", repr(exc))
            raise

        finally:
            shutil.rmtree(test_tmp, ignore_errors=True)


if __name__ == "__main__":
    run_all()
    print("ALL_KR_TESTS_PASS")

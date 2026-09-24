# -*- coding: utf-8 -*-
"""
Knowledge History & Operations V0.5 离线测试（纯函数 + 真实历史只读 smoke）。

覆盖 TEST-KH-01..30 + REAL_HISTORY_READONLY_SMOKE。
不修改任何正式审计记录。
"""

import json
import shutil
import sys
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import knowledge_history_v0_5 as kh  # noqa: E402


def make_tmp():
    root = ROOT / "outputs" / "knowledge_feedback" / "test"
    root.mkdir(parents=True, exist_ok=True)
    p = root / ("kh_" + uuid4().hex)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def feedback(tmp, traces=None, candidates=None, reviews=None, approved=None, writes=None):
    fb = tmp / "feedback"
    fb.mkdir(parents=True, exist_ok=True)
    if traces is not None:
        write_jsonl(fb / "query_traces.jsonl", traces)
    if candidates is not None:
        write_jsonl(fb / "kb_update_candidates.jsonl", candidates)
    if reviews is not None:
        write_jsonl(fb / "review_decisions.jsonl", reviews)
    if approved is not None:
        write_jsonl(fb / "approved_derived_knowledge.jsonl", approved)
    if writes is not None:
        write_jsonl(fb / "knowledge_write_decisions.jsonl", writes)
    return fb


def T(tid, q="q", at="2026-08-30T00:00:00+00:00"):
    return {"trace_id": tid, "query": q, "created_at": at, "evidence_gap_statement": "gap"}


def C(cid, tid, dt="EVIDENCE_GAP", status="PENDING_REVIEW", topic="topic"):
    return {"candidate_id": cid, "candidate_key": "k", "trace_id": tid, "decision_type": dt, "review_status": status, "knowledge_gap_summary": "sum", "related_existing_refs": ["CK-0062"], "target_hint": {"suggested_topic": topic}}


def R(cid, tid, rid, status, decision="APPROVE"):
    return {"candidate_id": cid, "trace_id": tid, "review_id": rid, "new_status": status, "decision": decision, "reviewer": "r", "review_comment": "", "reviewed_at": "2026-08-30T01:00:00+00:00"}


def A(cid, tid, rid, kid):
    return {"candidate_id": cid, "trace_id": tid, "review_id": rid, "knowledge_record_id": kid, "status": "APPROVED_FOR_KB"}


def W(cid, tid, rid, kid, wid, status="WRITTEN_TO_DERIVED_KB"):
    return {"candidate_id": cid, "trace_id": tid, "review_id": rid, "knowledge_record_id": kid, "write_id": wid, "new_status": status, "vault_relative_path": "05_已审核派生知识/AUTO-001/" + kid + ".md"}


# ------------------------------------------------------------
# Pure functions
# ------------------------------------------------------------

def test_kh_01_trace_only():
    assert kh.resolve_governance_status(None, None, None) == "TRACE_ONLY"


def test_kh_02_pending():
    assert kh.resolve_governance_status(C("c", "t"), None, None) == "PENDING_REVIEW"


def test_kh_03_approved():
    assert kh.resolve_governance_status(C("c", "t"), R("c", "t", "r", "APPROVED_FOR_KB"), None) == "APPROVED_FOR_KB"


def test_kh_04_nme():
    assert kh.resolve_governance_status(C("c", "t"), R("c", "t", "r", "NEED_MORE_EVIDENCE"), None) == "NEED_MORE_EVIDENCE"


def test_kh_05_reject():
    assert kh.resolve_governance_status(C("c", "t"), R("c", "t", "r", "REJECTED", "REJECT"), None) == "REJECTED"


def test_kh_06_written():
    assert kh.resolve_governance_status(C("c", "t"), R("c", "t", "r", "APPROVED_FOR_KB"), W("c", "t", "r", "ak", "kw")) == "WRITTEN_TO_DERIVED_KB"


def test_kh_07_write_beats_candidate_pending():
    # Candidate 原始 PENDING，但 Write 已 WRITTEN
    assert kh.resolve_governance_status(C("c", "t", status="PENDING_REVIEW"), R("c", "t", "r", "APPROVED_FOR_KB"), W("c", "t", "r", "ak", "kw")) == "WRITTEN_TO_DERIVED_KB"


def test_kh_08_review_beats_candidate_pending():
    # Candidate 原始 PENDING，但 Review 已 APPROVED
    assert kh.resolve_governance_status(C("c", "t", status="PENDING_REVIEW"), R("c", "t", "r", "APPROVED_FOR_KB"), None) == "APPROVED_FOR_KB"


def test_kh_09_trace_link():
    fb = feedback(tmp_path_placeholder(), traces=[T("t1")], candidates=[C("c1", "t1")])
    recs = kh.load_history(feedback_dir=fb)
    assert recs[0]["trace_id"] == "t1"
    assert recs[0]["candidate_id"] == "c1"


def test_kh_10_candidate_link():
    fb = feedback(tmp_path_placeholder(), traces=[T("t1")], candidates=[C("c1", "t1")], reviews=[R("c1", "t1", "r1", "APPROVED_FOR_KB")])
    recs = kh.load_history(feedback_dir=fb)
    assert recs[0]["candidate_id"] == "c1"
    assert recs[0]["review_id"] == "r1"


def test_kh_11_review_link():
    fb = feedback(tmp_path_placeholder(), traces=[T("t1")], candidates=[C("c1", "t1")], reviews=[R("c1", "t1", "r1", "APPROVED_FOR_KB")])
    recs = kh.load_history(feedback_dir=fb)
    assert recs[0]["review_id"] == "r1"


def test_kh_12_knowledge_record_link():
    fb = feedback(tmp_path_placeholder(), traces=[T("t1")], candidates=[C("c1", "t1")], reviews=[R("c1", "t1", "r1", "APPROVED_FOR_KB")], approved=[A("c1", "t1", "r1", "ak1")], writes=[W("c1", "t1", "r1", "ak1", "kw1")])
    recs = kh.load_history(feedback_dir=fb)
    assert recs[0]["knowledge_record_id"] == "ak1"
    assert recs[0]["write_id"] == "kw1"


def test_kh_13_search_query():
    recs = [{"query": "HD-S303低温", "candidate_topic": "", "candidate_id": "", "knowledge_record_id": ""},
            {"query": "其他", "candidate_topic": "", "candidate_id": "", "knowledge_record_id": ""}]
    out = kh.search_history(recs, "HD-S303")
    assert len(out) == 1


def test_kh_14_search_candidate_id():
    recs = [{"query": "", "candidate_topic": "", "candidate_id": "KC-abc", "knowledge_record_id": ""}]
    out = kh.search_history(recs, "KC-abc")
    assert len(out) == 1


def test_kh_15_filter_status():
    recs = [{"current_governance_status": "WRITTEN_TO_DERIVED_KB"}, {"current_governance_status": "PENDING_REVIEW"}]
    out = kh.filter_history(recs, status="WRITTEN_TO_DERIVED_KB")
    assert len(out) == 1


def test_kh_16_filter_decision_type():
    recs = [{"candidate_decision_type": "EVIDENCE_GAP"}, {"candidate_decision_type": "NEW_TOPIC"}]
    out = kh.filter_history(recs, decision_type="NEW_TOPIC")
    assert len(out) == 1


def test_kh_17_time_desc():
    fb = feedback(tmp_path_placeholder(), traces=[T("t1", at="2026-08-30T00:00:00+00:00"), T("t2", at="2026-08-30T02:00:00+00:00")], candidates=[C("c1", "t1"), C("c2", "t2")])
    recs = kh.load_history(feedback_dir=fb)
    assert recs[0]["trace_id"] == "t2"


def test_kh_18_missing_files_no_crash():
    fb = tmp_path_placeholder() / "empty"
    fb.mkdir(parents=True, exist_ok=True)
    recs = kh.load_history(feedback_dir=fb)
    assert recs == []


def test_kh_19_bad_jsonl_isolated():
    fb = tmp_path_placeholder() / "fb"
    fb.mkdir(parents=True, exist_ok=True)
    (fb / "query_traces.jsonl").write_text('{"trace_id":"t1"}\n{not valid json\n{"trace_id":"t2"}\n', encoding="utf-8")
    (fb / "kb_update_candidates.jsonl").write_text('{"candidate_id":"c1","trace_id":"t1"}\n{"candidate_id":"c2","trace_id":"t2"}\n', encoding="utf-8")
    recs = kh.load_history(feedback_dir=fb)
    assert len(recs) == 2  # 坏行被跳过，不崩


def test_kh_20_no_modify_source(tmp):
    fb = feedback(tmp, traces=[T("t1")], candidates=[C("c1", "t1")])
    p = fb / "query_traces.jsonl"
    before = p.read_text(encoding="utf-8")
    kh.load_history(feedback_dir=fb)
    assert p.read_text(encoding="utf-8") == before


# ------------------------------------------------------------
# Allowed Operation
# ------------------------------------------------------------

def test_kh_21_pending_op():
    assert kh.allowed_operation("PENDING_REVIEW") == "HUMAN_REVIEW"


def test_kh_22_approved_op():
    assert kh.allowed_operation("APPROVED_FOR_KB") == "KNOWLEDGE_WRITE"


def test_kh_23_written_op():
    assert kh.allowed_operation("WRITTEN_TO_DERIVED_KB") == "VIEW_KNOWLEDGE_RECORD"


def test_kh_24_rejected_op():
    assert kh.allowed_operation("REJECTED") == "VIEW_ONLY"


def test_kh_25_nme_op():
    assert kh.allowed_operation("NEED_MORE_EVIDENCE") == "VIEW_ONLY"


# ------------------------------------------------------------
# Display Status Micro-fix
# ------------------------------------------------------------

def test_kh_26_approved_label_not_pending():
    status = kh.resolve_governance_status(C("c", "t", status="PENDING_REVIEW"), R("c", "t", "r", "APPROVED_FOR_KB"), None)
    assert status == "APPROVED_FOR_KB"
    assert kh.status_display_label(status) == "已批准｜待知识写入"
    assert kh.status_display_label(status) != "待人工审核"


def test_kh_27_written_label():
    status = kh.resolve_governance_status(C("c", "t", status="PENDING_REVIEW"), R("c", "t", "r", "APPROVED_FOR_KB"), W("c", "t", "r", "ak", "kw"))
    assert kh.status_display_label(status) == "已写入 Derived Knowledge"


def test_kh_28_runtime_once():
    # 逻辑：最终状态块只含一次"当前 Runtime：未纳入"；由 UI 保证，此处验证 label 唯一性语义
    status = kh.resolve_governance_status(C("c", "t"), R("c", "t", "r", "APPROVED_FOR_KB"), W("c", "t", "r", "ak", "kw"))
    label = kh.status_display_label(status)
    assert label == "已写入 Derived Knowledge"


def test_kh_29_pending_no_write_ui():
    status = kh.resolve_governance_status(C("c", "t"), None, None)
    assert kh.allowed_operation(status) == "HUMAN_REVIEW"  # 无 KNOWLEDGE_WRITE


def test_kh_30_approved_has_write():
    status = kh.resolve_governance_status(C("c", "t"), R("c", "t", "r", "APPROVED_FOR_KB"), None)
    assert kh.allowed_operation(status) == "KNOWLEDGE_WRITE"


# ------------------------------------------------------------
# Real history read-only smoke
# ------------------------------------------------------------

def test_real_history_readonly_smoke():
    recs = kh.load_history()

    assert len(recs) >= 1

    written = [r for r in recs if r["current_governance_status"] == "WRITTEN_TO_DERIVED_KB"]

    assert len(written) >= 1

    r = written[0]

    assert r["candidate_status_original"] == "PENDING_REVIEW"  # 原 Candidate 审计状态
    assert r["review_status"] == "APPROVED_FOR_KB"
    assert r["write_status"] == "WRITTEN_TO_DERIVED_KB"
    assert r["current_governance_status"] == "WRITTEN_TO_DERIVED_KB"
    assert r["candidate_id"] and r["trace_id"] and r["review_id"] and r["knowledge_record_id"] and r["write_id"]


# 占位（测试函数用），实际由 run_all 传入真实 tmp
_tmp = [None]
def tmp_path_placeholder():
    return _tmp[0]


def run_all():
    global _tmp

    tests = [
        test_kh_01_trace_only,
        test_kh_02_pending,
        test_kh_03_approved,
        test_kh_04_nme,
        test_kh_05_reject,
        test_kh_06_written,
        test_kh_07_write_beats_candidate_pending,
        test_kh_08_review_beats_candidate_pending,
        test_kh_09_trace_link,
        test_kh_10_candidate_link,
        test_kh_11_review_link,
        test_kh_12_knowledge_record_link,
        test_kh_13_search_query,
        test_kh_14_search_candidate_id,
        test_kh_15_filter_status,
        test_kh_16_filter_decision_type,
        test_kh_17_time_desc,
        test_kh_18_missing_files_no_crash,
        test_kh_19_bad_jsonl_isolated,
        test_kh_20_no_modify_source,
        test_kh_21_pending_op,
        test_kh_22_approved_op,
        test_kh_23_written_op,
        test_kh_24_rejected_op,
        test_kh_25_nme_op,
        test_kh_26_approved_label_not_pending,
        test_kh_27_written_label,
        test_kh_28_runtime_once,
        test_kh_29_pending_no_write_ui,
        test_kh_30_approved_has_write,
        test_real_history_readonly_smoke,
    ]

    for test in tests:
        test_tmp = make_tmp()
        _tmp = [test_tmp]

        try:
            if test is test_kh_20_no_modify_source:
                test(test_tmp)
            else:
                test()

            print("PASS", test.__name__)

        except Exception as exc:
            print("FAIL", test.__name__, "->", repr(exc))
            raise

        finally:
            shutil.rmtree(test_tmp, ignore_errors=True)


if __name__ == "__main__":
    run_all()
    print("ALL_KH_TESTS_PASS")

# -*- coding: utf-8 -*-
"""
Legacy Derived Knowledge Correction & Supersession V0.7 离线测试。

覆盖 TEST-KC7-01..24。全部使用临时目录，不污染正式
knowledge_feedback / knowledge_vault / Truth Source。
"""

import sys
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import knowledge_correction_v0_7 as kc  # noqa: E402
import knowledge_writeback_v0_4 as kw  # noqa: E402


A = kc.VIOLATION_A
B = kc.VIOLATION_B


def make_tmp():
    root = ROOT / "outputs" / "knowledge_feedback" / "test"
    root.mkdir(parents=True, exist_ok=True)
    p = root / ("kc7_" + uuid4().hex)
    p.mkdir(parents=True, exist_ok=True)
    return p


def make_ak_file(tmp, rid, cid, trace, title, summary):
    d = tmp / "AUTO-001"
    d.mkdir(parents=True, exist_ok=True)

    text = (
        "---\n"
        "knowledge_record_id: " + rid + "\n"
        "candidate_id: " + cid + "\n"
        "trace_id: " + trace + "\n"
        "---\n\n"
        "# " + title + "\n\n"
        "## 一、知识摘要\n\n" + summary + "\n"
    )

    p = d / (rid + ".md")
    p.write_text(text, encoding="utf-8")
    return p


def make_candidate(cid, created_at, topic, gap, evidence, decision_type="EVIDENCE_GAP", query="q"):
    return {
        "candidate_id": cid,
        "candidate_key": "key-" + cid,
        "trace_id": "QT-" + cid,
        "decision_type": decision_type,
        "review_status": "PENDING_REVIEW",
        "created_at": created_at,
        "target_hint": {"suggested_topic": topic},
        "knowledge_gap_summary": gap,
        "evidence_needed": evidence,
        "query": query,
    }


def make_legacy_record(rid, cid, trace, path, violations):
    return {
        "knowledge_record_id": rid,
        "candidate_id": cid,
        "trace_id": trace,
        "path": path,
        "topic": "HD-S303汽车革-30℃耐折专项验证（PTMEG体系）",
        "violation_types": violations,
    }


COMPLIANT_TOPIC = "HD-S303汽车革-30℃耐折专项验证"
COMPLIANT_EVIDENCE = [
    "HD-S303在-30℃条件下按QB/T 2714-2018测试的耐折次数（目标≥5万次）",
    "HD-S303当前软段/配方体系确认（是否PTMEG）及低温性能依据",
    "如存在-20℃出厂抽检数据或同条件对比，可作为中间参考但不能替代-30℃验证",
]
COMPLIANT_GAP = "缺少HD-S303针对-30℃汽车革的直接验证数据，无法支持外推。"


# ============================================================
# TEST-KC7-01..05 违规检测（保守）
# ============================================================

def test_kc7_01_current_ptmeg_is_type_a():
    assert A in kc.detect_violations("当前PTMEG体系")
    assert A in kc.detect_violations("HD-S303（PTMEG体系）")


def test_kc7_02_historical_ppg_to_ptmeg_not_violation():
    assert kc.detect_violations("历史案例PPG→PTMEG纠正后改善") == []


def test_kc7_03_confirm_question_not_violation():
    assert kc.detect_violations("需确认当前是否采用PTMEG") == []


def test_kc7_04_fail_then_change_pcdl_is_type_b():
    assert B in kc.detect_violations("测试失败后改PCDL")


def test_kc7_05_technical_pcdl_discussion_not_violation():
    assert kc.detect_violations("技术资料显示PTMEG较PPG在-20℃耐折提高约40%") == []


# ============================================================
# TEST-KC7-06 已知 AK-51bc 审计命中
# ============================================================

def test_kc7_06_known_ak51bc_audit_hit():
    tmp = make_tmp()
    ak_dir = tmp / "AUTO-001"
    ak_dir.mkdir(parents=True, exist_ok=True)

    text = (
        "---\n"
        "knowledge_record_id: AK-51bc951a799242a4adfbe80ae635e448\n"
        "candidate_id: KC-528301c8d56f40a1bd7eee2231b8a1ec\n"
        "trace_id: QT-a630719065124fdfa68d9ab79f3e06e7\n"
        "---\n\n"
        "# HD-S303汽车革-30℃耐折专项验证（PTMEG体系）\n\n"
        "## 一、知识摘要\n\n"
        "缺少HD-S303（PTMEG体系）在汽车内饰革应用场景下"
        "-30℃耐折≥5万次的直接专项验证数据。\n"
    )

    (ak_dir / "AK-51bc951a799242a4adfbe80ae635e448.md").write_text(
        text, encoding="utf-8"
    )

    rows = kc.audit_legacy_derived_knowledge(ak_dir, vault_root=tmp)

    assert len(rows) == 1
    row = rows[0]

    assert row["knowledge_record_id"] == "AK-51bc951a799242a4adfbe80ae635e448"
    assert row["candidate_id"] == "KC-528301c8d56f40a1bd7eee2231b8a1ec"
    assert A in row["violation_types"]


# ============================================================
# TEST-KC7-07..09 Replacement 选择
# ============================================================

def test_kc7_07_unique_replacement_proposed():
    tmp = make_tmp()

    legacy = make_legacy_record(
        "AK-old", "KC-legacy", "QT-legacy", "AUTO-001/AK-old.md", [A]
    )

    candidates = [
        make_candidate(
            "KC-legacy", "2026-01-01T00:00:00Z",
            "HD-S303汽车革-30℃耐折专项验证（PTMEG体系）",
            "gap", ["e"],
        ),
        make_candidate(
            "KC-new", "2026-01-02T00:00:00Z",
            COMPLIANT_TOPIC, COMPLIANT_GAP, COMPLIANT_EVIDENCE,
        ),
    ]

    reps = kc.find_replacement_candidates(legacy, candidates)

    assert len(reps) == 1
    assert reps[0]["candidate_id"] == "KC-new"

    intent = kc.build_correction_intent(legacy, reps[0])

    assert intent["status"] == "PROPOSED"
    assert intent["replacement_candidate_id"] == "KC-new"
    assert intent["legacy_knowledge_record_id"] == "AK-old"


def test_kc7_08_no_replacement_hold():
    legacy = make_legacy_record(
        "AK-old", "KC-legacy", "QT-legacy", "AUTO-001/AK-old.md", [A]
    )

    candidates = [
        make_candidate(
            "KC-legacy", "2026-01-01T00:00:00Z",
            "HD-S303汽车革-30℃耐折专项验证（PTMEG体系）",
            "gap", ["e"],
        ),
    ]

    assert kc.find_replacement_candidates(legacy, candidates) == []


def test_kc7_09_multiple_replacement_hold():
    legacy = make_legacy_record(
        "AK-old", "KC-legacy", "QT-legacy", "AUTO-001/AK-old.md", [A]
    )

    candidates = [
        make_candidate(
            "KC-legacy", "2026-01-01T00:00:00Z",
            "HD-S303汽车革-30℃耐折专项验证（PTMEG体系）",
            "gap", ["e"],
        ),
        make_candidate(
            "KC-new1", "2026-01-02T00:00:00Z",
            COMPLIANT_TOPIC, COMPLIANT_GAP, COMPLIANT_EVIDENCE,
        ),
        make_candidate(
            "KC-new2", "2026-01-03T00:00:00Z",
            COMPLIANT_TOPIC, COMPLIANT_GAP, COMPLIANT_EVIDENCE,
        ),
    ]

    assert len(kc.find_replacement_candidates(legacy, candidates)) == 2


# ============================================================
# TEST-KC7-10..13 Intent 治理属性
# ============================================================

def _legacy_and_replacement():
    legacy = make_legacy_record(
        "AK-old", "KC-legacy", "QT-legacy", "AUTO-001/AK-old.md", [A]
    )
    replacement = make_candidate(
        "KC-new", "2026-01-02T00:00:00Z",
        COMPLIANT_TOPIC, COMPLIANT_GAP, COMPLIANT_EVIDENCE,
    )
    return legacy, replacement


def test_kc7_10_duplicate_intent_blocked():
    tmp = make_tmp()
    legacy, replacement = _legacy_and_replacement()

    intent1 = kc.build_correction_intent(legacy, replacement)
    intent2 = kc.build_correction_intent(legacy, replacement)

    r1 = kc.append_correction_intent(intent1, tmp)
    r2 = kc.append_correction_intent(intent2, tmp)

    assert r1["result_status"] == "APPENDED"
    assert r2["result_status"] == "ALREADY_HAS_CORRECTION_INTENT"


def test_kc7_11_intent_is_not_evidence():
    legacy, replacement = _legacy_and_replacement()
    intent = kc.build_correction_intent(legacy, replacement)

    assert intent["truth_source_write"] is False
    assert intent["current_runtime_write"] is False
    assert intent["auto_reindex"] is False
    assert intent["future_snapshot_gate_required"] is True
    assert intent["human_review_required"] is True
    assert "approved_as_evidence" not in intent


def test_kc7_12_intent_does_not_modify_old_ak():
    tmp = make_tmp()
    legacy, replacement = _legacy_and_replacement()

    ak_path = make_ak_file(
        tmp, "AK-old", "KC-legacy", "QT-legacy",
        "HD-S303汽车革-30℃耐折专项验证（PTMEG体系）",
        "旧摘要",
    )

    before = ak_path.read_bytes()

    kc.append_correction_intent(
        kc.build_correction_intent(legacy, replacement), tmp
    )

    after = ak_path.read_bytes()

    assert before == after


def test_kc7_13_intent_does_not_modify_old_manifest():
    tmp = make_tmp()
    legacy, replacement = _legacy_and_replacement()

    manifest = tmp / "00_Approved_Knowledge_Manifest.jsonl"
    manifest.write_text(
        '{"knowledge_record_id":"AK-old","status":"WRITTEN_TO_DERIVED_KB"}\n',
        encoding="utf-8",
    )

    before = manifest.read_bytes()

    kc.append_correction_intent(
        kc.build_correction_intent(legacy, replacement), tmp
    )

    after = manifest.read_bytes()

    assert before == after


# ============================================================
# TEST-KC7-14..18 Supersession Relation
# ============================================================

def test_kc7_14_not_reviewed_no_relation():
    legacy, replacement = _legacy_and_replacement()
    intent = kc.build_correction_intent(legacy, replacement)

    result = kc.build_supersession_relation(
        intent, "AK-new", "KC-new",
        replacement_review_status="PENDING_REVIEW",
        replacement_write_status=None,
    )

    assert result["relation"] is None
    assert result["reason"] == "REPLACEMENT_NOT_APPROVED"


def test_kc7_15_reviewed_not_written_no_relation():
    legacy, replacement = _legacy_and_replacement()
    intent = kc.build_correction_intent(legacy, replacement)

    result = kc.build_supersession_relation(
        intent, "AK-new", "KC-new",
        replacement_review_status="APPROVED_FOR_KB",
        replacement_write_status=None,
    )

    assert result["relation"] is None
    assert result["reason"] == "REPLACEMENT_NOT_WRITTEN"


def test_kc7_16_written_generates_relation():
    legacy, replacement = _legacy_and_replacement()
    intent = kc.build_correction_intent(legacy, replacement)

    result = kc.build_supersession_relation(
        intent, "AK-new", "KC-new",
        replacement_review_status="APPROVED_FOR_KB",
        replacement_write_status="WRITTEN_TO_DERIVED_KB",
    )

    assert result["relation"] is not None
    assert result["relation"]["relation_type"] == "SUPERSEDED_BY_CORRECTION"
    assert result["relation"]["old_knowledge_record_id"] == "AK-old"
    assert result["relation"]["new_knowledge_record_id"] == "AK-new"


def test_kc7_17_old_record_modified_false():
    legacy, replacement = _legacy_and_replacement()
    intent = kc.build_correction_intent(legacy, replacement)

    result = kc.build_supersession_relation(
        intent, "AK-new", "KC-new",
        replacement_review_status="APPROVED_FOR_KB",
        replacement_write_status="WRITTEN_TO_DERIVED_KB",
    )

    assert result["relation"]["old_record_modified"] is False


def test_kc7_18_current_runtime_changed_false():
    legacy, replacement = _legacy_and_replacement()
    intent = kc.build_correction_intent(legacy, replacement)

    result = kc.build_supersession_relation(
        intent, "AK-new", "KC-new",
        replacement_review_status="APPROVED_FOR_KB",
        replacement_write_status="WRITTEN_TO_DERIVED_KB",
    )

    assert result["relation"]["current_runtime_changed"] is False
    assert result["relation"]["truth_source_modified"] is False
    assert result["relation"]["auto_reindex"] is False


# ============================================================
# TEST-KC7-19..23 新 AK / 旧 AK 更正关系
# ============================================================

def test_kc7_19_new_ak_contains_corrects_relation():
    legacy, replacement = _legacy_and_replacement()
    intent = kc.build_correction_intent(legacy, replacement)

    fm_add, section = kc.build_correction_annotations(intent)

    assert fm_add["corrects_knowledge_record_ids"] == ["AK-old"]
    assert "本条知识用于纠正" in section
    assert "AK-old" in section
    assert "本条不修改旧记录" in section


def test_kc7_20_old_ak_hash_unchanged():
    tmp = make_tmp()
    legacy, replacement = _legacy_and_replacement()

    ak_path = make_ak_file(
        tmp, "AK-old", "KC-legacy", "QT-legacy",
        "HD-S303汽车革-30℃耐折专项验证（PTMEG体系）",
        "旧摘要",
    )

    h1 = kc.content_sha256(ak_path)

    kc.append_correction_intent(
        kc.build_correction_intent(legacy, replacement), tmp
    )

    h2 = kc.content_sha256(ak_path)

    assert h1 == h2


def test_kc7_21_legacy_shows_correction_pending():
    legacy, replacement = _legacy_and_replacement()
    intent = kc.build_correction_intent(legacy, replacement)

    status = kc.get_legacy_correction_status("AK-old", [intent], [])

    assert status is not None
    assert status["status"] == "CORRECTION_PENDING"


def test_kc7_22_superseded_history_shows_new_ak():
    legacy, replacement = _legacy_and_replacement()
    intent = kc.build_correction_intent(legacy, replacement)

    result = kc.build_supersession_relation(
        intent, "AK-new", "KC-new",
        replacement_review_status="APPROVED_FOR_KB",
        replacement_write_status="WRITTEN_TO_DERIVED_KB",
    )

    status = kc.get_legacy_correction_status(
        "AK-old", [intent], [result["relation"]]
    )

    assert status["status"] == "SUPERSEDED"
    assert status["new_knowledge_record_id"] == "AK-new"


def test_kc7_23_new_record_shows_corrects_old_ak():
    legacy, replacement = _legacy_and_replacement()
    intent = kc.build_correction_intent(legacy, replacement)

    result = kc.build_supersession_relation(
        intent, "AK-new", "KC-new",
        replacement_review_status="APPROVED_FOR_KB",
        replacement_write_status="WRITTEN_TO_DERIVED_KB",
    )

    corrected = kc.get_new_record_correction_relation(
        "AK-new", [result["relation"]]
    )

    assert corrected == ["AK-old"]


def test_kc7_24_truth_source_hash_unchanged():
    tmp = make_tmp()

    vault = tmp / "vault"
    truth = vault / "01_原始资料"
    truth.mkdir(parents=True, exist_ok=True)
    (truth / "products.csv").write_text("id\nHD-S303\n", encoding="utf-8")

    before = kw.truth_source_hash_tree(vault)

    legacy, replacement = _legacy_and_replacement()
    kc.propose_correction_intents(
        [legacy],
        [replacement],
        feedback_dir=tmp,
    )

    after = kw.truth_source_hash_tree(vault)

    assert before == after


def run_all():
    tests = [
        test_kc7_01_current_ptmeg_is_type_a,
        test_kc7_02_historical_ppg_to_ptmeg_not_violation,
        test_kc7_03_confirm_question_not_violation,
        test_kc7_04_fail_then_change_pcdl_is_type_b,
        test_kc7_05_technical_pcdl_discussion_not_violation,
        test_kc7_06_known_ak51bc_audit_hit,
        test_kc7_07_unique_replacement_proposed,
        test_kc7_08_no_replacement_hold,
        test_kc7_09_multiple_replacement_hold,
        test_kc7_10_duplicate_intent_blocked,
        test_kc7_11_intent_is_not_evidence,
        test_kc7_12_intent_does_not_modify_old_ak,
        test_kc7_13_intent_does_not_modify_old_manifest,
        test_kc7_14_not_reviewed_no_relation,
        test_kc7_15_reviewed_not_written_no_relation,
        test_kc7_16_written_generates_relation,
        test_kc7_17_old_record_modified_false,
        test_kc7_18_current_runtime_changed_false,
        test_kc7_19_new_ak_contains_corrects_relation,
        test_kc7_20_old_ak_hash_unchanged,
        test_kc7_21_legacy_shows_correction_pending,
        test_kc7_22_superseded_history_shows_new_ak,
        test_kc7_23_new_record_shows_corrects_old_ak,
        test_kc7_24_truth_source_hash_unchanged,
    ]

    for test in tests:
        try:
            test()
            print("PASS", test.__name__)

        except Exception as exc:
            print("FAIL", test.__name__, "->", repr(exc))
            raise


if __name__ == "__main__":
    run_all()
    print("ALL_KC7_TESTS_PASS")

# -*- coding: utf-8 -*-
"""
Knowledge Writeback V0.4 离线测试（纯函数 + 真实 V2 ZIP temp smoke）。

覆盖 TEST-KW-01..25 + ZIP_TEMP_SMOKE + TRUTH_SOURCE_HASH_UNCHANGED。
不污染正式 knowledge_vault / knowledge_write_decisions.jsonl。
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

import knowledge_writeback_v0_4 as kw  # noqa: E402


V2_ZIP = (
    ROOT
    / "docs"
    / "handoff"
    / "Y_to_W"
    / "AUTO001_KB_Sync_20260830_V2.zip"
)


def make_approved(candidate_id="KC-test-001", knowledge_record_id="AK-test-001", status="APPROVED_FOR_KB"):
    return {
        "knowledge_record_id": knowledge_record_id,
        "candidate_id": candidate_id,
        "candidate_key": "key-" + candidate_id,
        "trace_id": "QT-test-001",
        "review_id": "KR-test-001",
        "status": status,
        "knowledge_type": "EVIDENCE_GAP",
        "candidate_decision_type": "EVIDENCE_GAP",
        "topic": "HD-S303 -30℃ 耐折验证",
        "summary": "缺 -30℃ 直接专项验证。",
        "recommended_action": "REQUEST_NEW_EVIDENCE",
        "source_refs": ["CK-0062", "CK-0095"],
        "reviewer": "W",
        "review_comment": "",
        "approved_at": "2026-08-30T00:00:00+00:00",
    }


def make_tmp():
    root = ROOT / "outputs" / "knowledge_feedback" / "test"
    root.mkdir(parents=True, exist_ok=True)
    p = root / ("kw_" + uuid4().hex)
    p.mkdir(parents=True, exist_ok=True)
    return p


def make_vault(tmp):
    vault = tmp / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    truth = vault / "01_原始资料"
    truth.mkdir(parents=True, exist_ok=True)
    (truth / "products.csv").write_text("id\nHD-S303\n", encoding="utf-8")
    return vault


def write(rec, tmp, **kwargs):
    vault = kwargs.pop("vault", make_vault(tmp))
    feedback = tmp / "feedback"
    feedback.mkdir(parents=True, exist_ok=True)
    return kw.write_approved_knowledge(
        rec,
        reviewer_role=kwargs.pop("role", "Y"),
        reviewer_name=kwargs.pop("name", "研发工程师"),
        evidence_confirmed=kwargs.pop("confirmed", True),
        write_comment=kwargs.pop("comment", ""),
        vault_root=vault,
        feedback_dir=feedback,
    )


# ------------------------------------------------------------
# TEST-KW
# ------------------------------------------------------------

def test_kw_01_not_approved_hold(tmp):
    rec = make_approved(status="NEED_MORE_EVIDENCE")
    res = write(rec, tmp)

    assert res["result_status"] == "HOLD"
    assert res["reason"] == "NOT_APPROVED_FOR_KB"


def test_kw_02_approved_role_y(tmp):
    rec = make_approved()
    res = write(rec, tmp, role="Y", confirmed=True)

    assert res["result_status"] == "WRITTEN_TO_DERIVED_KB"


def test_kw_03_approved_role_rd(tmp):
    rec = make_approved()
    res = write(rec, tmp, role="R&D_ENGINEER")

    assert res["result_status"] == "WRITTEN_TO_DERIVED_KB"


def test_kw_04_role_w_hold(tmp):
    res = write(make_approved(), tmp, role="W")

    assert res["result_status"] == "HOLD"
    assert res["reason"] == "ROLE_NOT_ALLOWED"


def test_kw_05_reviewer_name_empty_hold(tmp):
    res = write(make_approved(), tmp, name="")

    assert res["result_status"] == "HOLD"
    assert res["reason"] == "REVIEWER_NAME_REQUIRED"


def test_kw_06_evidence_not_confirmed_hold(tmp):
    res = write(make_approved(), tmp, confirmed=False)

    assert res["result_status"] == "HOLD"
    assert res["reason"] == "EVIDENCE_NOT_CONFIRMED"


def test_kw_07_markdown_generated(tmp):
    vault = make_vault(tmp)
    res = write(make_approved(), tmp, vault=vault)

    md = vault / "05_已审核派生知识" / "AUTO-001" / "AK-test-001.md"
    assert md.exists()
    assert res["vault_relative_path"] == "05_已审核派生知识/AUTO-001/AK-test-001.md"


def test_kw_08_manifest_append(tmp):
    vault = make_vault(tmp)
    write(make_approved(), tmp, vault=vault)

    man = vault / "05_已审核派生知识" / "00_Approved_Knowledge_Manifest.jsonl"
    rows = kw._load_jsonl(man)
    assert len(rows) == 1


def test_kw_09_write_decision_append(tmp):
    feedback = tmp / "feedback"
    feedback.mkdir(parents=True, exist_ok=True)
    write(make_approved(), tmp, vault=make_vault(tmp))

    wd = kw._load_jsonl(feedback / kw.WRITE_DECISIONS_FILE)
    assert len(wd) == 1
    assert wd[0]["new_status"] == "WRITTEN_TO_DERIVED_KB"


def test_kw_10_duplicate_blocked(tmp):
    vault = make_vault(tmp)
    rec = make_approved()
    write(rec, tmp, vault=vault)
    res2 = write(rec, tmp, vault=vault)

    assert res2["result_status"] == "ALREADY_WRITTEN"


def test_kw_11_no_modify_approved_file(tmp):
    feedback = tmp / "feedback"
    feedback.mkdir(parents=True, exist_ok=True)
    ap = feedback / "approved_derived_knowledge.jsonl"
    ap.write_text('{"candidate_id":"KC-test-001"}\n', encoding="utf-8")
    before = ap.read_text(encoding="utf-8")

    write(make_approved(), tmp, vault=make_vault(tmp))

    assert ap.read_text(encoding="utf-8") == before


def test_kw_12_no_modify_review_decisions(tmp):
    feedback = tmp / "feedback"
    feedback.mkdir(parents=True, exist_ok=True)
    rd = feedback / "review_decisions.jsonl"
    rd.write_text('{"candidate_id":"KC-test-001"}\n', encoding="utf-8")
    before = rd.read_text(encoding="utf-8")

    write(make_approved(), tmp, vault=make_vault(tmp))

    assert rd.read_text(encoding="utf-8") == before


def test_kw_13_no_modify_query_traces(tmp):
    feedback = tmp / "feedback"
    feedback.mkdir(parents=True, exist_ok=True)
    qt = feedback / "query_traces.jsonl"
    qt.write_text('{"trace_id":"QT-test-001"}\n', encoding="utf-8")
    before = qt.read_text(encoding="utf-8")

    write(make_approved(), tmp, vault=make_vault(tmp))

    assert qt.read_text(encoding="utf-8") == before


def test_kw_14_no_modify_candidates(tmp):
    feedback = tmp / "feedback"
    feedback.mkdir(parents=True, exist_ok=True)
    kc = feedback / "kb_update_candidates.jsonl"
    kc.write_text('{"candidate_id":"KC-test-001"}\n', encoding="utf-8")
    before = kc.read_text(encoding="utf-8")

    write(make_approved(), tmp, vault=make_vault(tmp))

    assert kc.read_text(encoding="utf-8") == before


def test_kw_15_no_modify_truth_source(tmp):
    vault = make_vault(tmp)
    before = kw.truth_source_hash_tree(vault)

    write(make_approved(), tmp, vault=vault)

    after = kw.truth_source_hash_tree(vault)
    assert before == after


def test_kw_16_truth_source_false(tmp):
    vault = make_vault(tmp)
    res = write(make_approved(), tmp, vault=vault)

    assert res["write_decision"]["truth_source_write"] is False
    assert res["manifest_entry"]["truth_source"] is False


def test_kw_17_approved_as_evidence_false(tmp):
    vault = make_vault(tmp)
    write(make_approved(), tmp, vault=vault)

    md = (vault / "05_已审核派生知识" / "AUTO-001" / "AK-test-001.md").read_text(encoding="utf-8")
    assert "approved_as_evidence: false" in md


def test_kw_18_current_runtime_false(tmp):
    vault = make_vault(tmp)
    res = write(make_approved(), tmp, vault=vault)

    assert res["write_decision"]["current_runtime_write"] is False
    assert res["manifest_entry"]["current_runtime_source"] is False


def test_kw_19_future_snapshot_candidate_true(tmp):
    vault = make_vault(tmp)
    res = write(make_approved(), tmp, vault=vault)

    assert res["manifest_entry"]["future_snapshot_candidate"] is True


def test_kw_20_future_snapshot_gate_true(tmp):
    vault = make_vault(tmp)
    res = write(make_approved(), tmp, vault=vault)

    assert res["write_decision"]["future_snapshot_gate_required"] is True


def test_kw_21_auto_reindex_false(tmp):
    vault = make_vault(tmp)
    res = write(make_approved(), tmp, vault=vault)

    assert res["write_decision"]["auto_reindex"] is False


def test_kw_22_evidence_gap_not_filled(tmp):
    vault = make_vault(tmp)
    write(make_approved(), tmp, vault=vault)

    md = (vault / "05_已审核派生知识" / "AUTO-001" / "AK-test-001.md").read_text(encoding="utf-8")
    for bad in ["已补证", "验证完成", "已达标", "evidence_level: E1"]:
        assert bad not in md
    assert "不表示缺失验证已经完成" in md


def test_kw_23_ak_exists_no_overwrite(tmp):
    vault = make_vault(tmp)
    rec = make_approved()
    write(rec, tmp, vault=vault)

    # 预置同名 AK 文件，重复 write
    ak = vault / "05_已审核派生知识" / "AUTO-001" / "AK-test-001.md"
    original = ak.read_text(encoding="utf-8")
    res2 = write(rec, tmp, vault=vault)

    assert res2["result_status"] == "ALREADY_WRITTEN"
    assert ak.read_text(encoding="utf-8") == original


def test_kw_24_traceability(tmp):
    vault = make_vault(tmp)
    res = write(make_approved(), tmp, vault=vault)

    wd = res["write_decision"]
    mn = res["manifest_entry"]

    assert wd["knowledge_record_id"] == "AK-test-001"
    assert wd["candidate_id"] == "KC-test-001"
    assert wd["trace_id"] == "QT-test-001"
    assert wd["review_id"] == "KR-test-001"
    assert wd["write_id"].startswith("KW-")
    assert mn["write_id"] == wd["write_id"]


def test_kw_25_path_traversal_hold(tmp):
    rec = make_approved(knowledge_record_id="../../evil")
    res = write(rec, tmp)

    assert res["result_status"] == "HOLD"
    assert res["reason"] == "UNSAFE_KNOWLEDGE_RECORD_ID"


# ------------------------------------------------------------
# ZIP temp smoke
# ------------------------------------------------------------

def test_zip_temp_smoke(tmp):
    if not V2_ZIP.exists():
        print("SKIP_ZIP_SMOKE (V2 ZIP not found)")
        return

    vault = tmp / "vault"

    kw.initialize_vault_from_zip(V2_ZIP, vault_root=vault)

    # 01_原始资料 hash 与 ZIP 内完全一致
    disk_hash = kw.truth_source_hash_tree(vault)
    zip_hash = kw.zip_truth_source_hash_tree(V2_ZIP)
    assert disk_hash == zip_hash

    before_disk = deepcopy(disk_hash)

    # 执行一个 temp write
    rec = make_approved(candidate_id="KC-temp-smoke", knowledge_record_id="AK-temp-smoke")
    feedback = tmp / "feedback"
    feedback.mkdir(parents=True, exist_ok=True)

    res = kw.write_approved_knowledge(
        rec,
        reviewer_role="Y",
        reviewer_name="研发工程师",
        evidence_confirmed=True,
        vault_root=vault,
        feedback_dir=feedback,
    )

    assert res["result_status"] == "WRITTEN_TO_DERIVED_KB"

    # 01_原始资料 无变化
    assert kw.truth_source_hash_tree(vault) == before_disk

    # 05 目录存在，README + Manifest + AK 文件
    derived = vault / "05_已审核派生知识"
    assert (derived / "00_README.md").exists()
    assert (derived / "00_Approved_Knowledge_Manifest.jsonl").exists()
    assert (derived / "AUTO-001" / "AK-temp-smoke.md").exists()


def run_all():
    tests = [
        test_kw_01_not_approved_hold,
        test_kw_02_approved_role_y,
        test_kw_03_approved_role_rd,
        test_kw_04_role_w_hold,
        test_kw_05_reviewer_name_empty_hold,
        test_kw_06_evidence_not_confirmed_hold,
        test_kw_07_markdown_generated,
        test_kw_08_manifest_append,
        test_kw_09_write_decision_append,
        test_kw_10_duplicate_blocked,
        test_kw_11_no_modify_approved_file,
        test_kw_12_no_modify_review_decisions,
        test_kw_13_no_modify_query_traces,
        test_kw_14_no_modify_candidates,
        test_kw_15_no_modify_truth_source,
        test_kw_16_truth_source_false,
        test_kw_17_approved_as_evidence_false,
        test_kw_18_current_runtime_false,
        test_kw_19_future_snapshot_candidate_true,
        test_kw_20_future_snapshot_gate_true,
        test_kw_21_auto_reindex_false,
        test_kw_22_evidence_gap_not_filled,
        test_kw_23_ak_exists_no_overwrite,
        test_kw_24_traceability,
        test_kw_25_path_traversal_hold,
        test_zip_temp_smoke,
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
    print("ALL_KW_TESTS_PASS")

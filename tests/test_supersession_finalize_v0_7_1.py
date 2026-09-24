# -*- coding: utf-8 -*-
"""
Supersession Finalization V0.7.1 离线测试。

覆盖 TEST-KS-01..14。全部使用临时目录，不污染正式
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


REPLACEMENT = "KC-ad020e558e37432f827a9fb756f01b5c"
NEW_AK = "AK-fc31f218c2a14ef48389b761ec210b6b"
OLD1 = "AK-51bc951a799242a4adfbe80ae635e448"
OLD2 = "AK-c444740cec87424a903b2767f3aa7dfb"


def make_tmp():
    root = ROOT / "outputs" / "knowledge_feedback" / "test"
    root.mkdir(parents=True, exist_ok=True)
    p = root / ("ks_" + uuid4().hex)
    p.mkdir(parents=True, exist_ok=True)
    return p


def make_intent(intent_id, legacy_ak, legacy_cand, replacement=REPLACEMENT):
    return {
        "correction_intent_id": intent_id,
        "legacy_knowledge_record_id": legacy_ak,
        "legacy_candidate_id": legacy_cand,
        "legacy_trace_id": "QT-legacy",
        "legacy_path": "AUTO-001/" + legacy_ak + ".md",
        "violation_types": ["UNSUPPORTED_CURRENT_FORMULATION"],
        "replacement_candidate_id": replacement,
        "replacement_candidate_key": "key",
        "status": "PROPOSED",
    }


def make_review(candidate_id, status="APPROVED_FOR_KB"):
    return {
        "candidate_id": candidate_id,
        "decision": "APPROVE" if status == "APPROVED_FOR_KB" else "OTHER",
        "new_status": status,
    }


def make_write(candidate_id, knowledge_record_id, status="WRITTEN_TO_DERIVED_KB"):
    return {
        "candidate_id": candidate_id,
        "knowledge_record_id": knowledge_record_id,
        "new_status": status,
    }


def make_ak_file(tmp, rid):
    d = tmp / "AUTO-001"
    d.mkdir(parents=True, exist_ok=True)
    p = d / (rid + ".md")
    p.write_text(
        "---\nknowledge_record_id: " + rid + "\n---\n\n# old\n",
        encoding="utf-8",
    )
    return p


def _two_intents():
    return [
        make_intent("KCI-1", OLD1, "KC-legacy1"),
        make_intent("KCI-2", OLD2, "KC-legacy2"),
    ]


def _finalize(tmp, intents=None, replacement=REPLACEMENT, new_ak=NEW_AK, review=None, write=None):
    return kc.finalize_correction_supersession(
        replacement_candidate_id=replacement,
        new_knowledge_record_id=new_ak,
        intents=intents if intents is not None else _two_intents(),
        review_records=review if review is not None else [make_review(REPLACEMENT)],
        write_records=write if write is not None else [make_write(REPLACEMENT, NEW_AK)],
        feedback_dir=tmp,
    )


def test_ks_01_not_written_no_relation():
    tmp = make_tmp()

    res = _finalize(
        tmp,
        intents=[make_intent("KCI-1", OLD1, "KC-legacy1")],
        write=[make_write(REPLACEMENT, NEW_AK, "APPROVED_FOR_KB")],
    )

    assert res["result_status"] == "HOLD"
    assert res["relations_created"] == []


def test_ks_02_one_intent_one_relation():
    tmp = make_tmp()

    res = _finalize(
        tmp,
        intents=[make_intent("KCI-1", OLD1, "KC-legacy1")],
    )

    assert res["result_status"] == "FINALIZED"
    assert len(res["relations_created"]) == 1
    assert res["relations_created"][0]["old_knowledge_record_id"] == OLD1


def test_ks_03_two_intents_two_relations():
    tmp = make_tmp()

    res = _finalize(tmp)

    assert res["result_status"] == "FINALIZED"
    assert len(res["relations_created"]) == 2


def test_ks_04_relations_share_same_new_ak():
    tmp = make_tmp()

    res = _finalize(tmp)

    rels = res["relations_created"]

    assert len(rels) == 2
    assert all(r["new_knowledge_record_id"] == NEW_AK for r in rels)
    assert rels[0]["old_knowledge_record_id"] != rels[1]["old_knowledge_record_id"]


def test_ks_05_old_ak_not_modified():
    tmp = make_tmp()
    ak_path = make_ak_file(tmp, OLD1)
    before = ak_path.read_bytes()

    _finalize(tmp)

    after = ak_path.read_bytes()
    assert before == after


def test_ks_06_old_manifest_not_modified():
    tmp = make_tmp()
    manifest = tmp / "00_Approved_Knowledge_Manifest.jsonl"
    manifest.write_text(
        '{"knowledge_record_id":"' + OLD1 + '"}\n',
        encoding="utf-8",
    )
    before = manifest.read_bytes()

    _finalize(tmp)

    after = manifest.read_bytes()
    assert before == after


def test_ks_07_duplicate_finalize_idempotent():
    tmp = make_tmp()

    res1 = _finalize(tmp)
    res2 = _finalize(tmp)

    assert res1["result_status"] == "FINALIZED"
    assert res2["result_status"] == "ALREADY_SUPERSEDED"
    assert res2["relations_created"] == []

    rels = kc.load_supersession_relations(tmp)
    assert len(rels) == 2


def test_ks_08_wrong_replacement_candidate_hold():
    tmp = make_tmp()

    res = _finalize(
        tmp,
        replacement="KC-wrong-candidate",
    )

    assert res["result_status"] == "HOLD"
    assert res["relations_created"] == []


def test_ks_09_no_intent_hold():
    tmp = make_tmp()

    res = _finalize(tmp, intents=[])

    assert res["result_status"] == "HOLD"
    assert res["relations_created"] == []


def test_ks_10_no_write_decision_hold():
    tmp = make_tmp()

    res = _finalize(tmp, write=[])

    assert res["result_status"] == "HOLD"
    assert res["relations_created"] == []


def test_ks_11_current_runtime_changed_false():
    tmp = make_tmp()

    res = _finalize(tmp)

    for r in res["relations_created"]:
        assert r["current_runtime_changed"] is False
        assert r["truth_source_modified"] is False
        assert r["old_record_modified"] is False


def test_ks_12_auto_reindex_false():
    tmp = make_tmp()

    res = _finalize(tmp)

    for r in res["relations_created"]:
        assert r["auto_reindex"] is False


def test_ks_13_history_old_record_superseded():
    tmp = make_tmp()
    intents = _two_intents()

    _finalize(tmp, intents=intents)

    relations = kc.load_supersession_relations(tmp)

    status = kc.get_legacy_correction_status(OLD1, intents, relations)

    assert status["status"] == "SUPERSEDED"
    assert status["new_knowledge_record_id"] == NEW_AK


def test_ks_14_history_new_record_corrects_two_old():
    tmp = make_tmp()

    _finalize(tmp)

    relations = kc.load_supersession_relations(tmp)
    corrected = kc.get_new_record_correction_relation(NEW_AK, relations)

    assert sorted(corrected) == sorted([OLD1, OLD2])


def run_all():
    tests = [
        test_ks_01_not_written_no_relation,
        test_ks_02_one_intent_one_relation,
        test_ks_03_two_intents_two_relations,
        test_ks_04_relations_share_same_new_ak,
        test_ks_05_old_ak_not_modified,
        test_ks_06_old_manifest_not_modified,
        test_ks_07_duplicate_finalize_idempotent,
        test_ks_08_wrong_replacement_candidate_hold,
        test_ks_09_no_intent_hold,
        test_ks_10_no_write_decision_hold,
        test_ks_11_current_runtime_changed_false,
        test_ks_12_auto_reindex_false,
        test_ks_13_history_old_record_superseded,
        test_ks_14_history_new_record_corrects_two_old,
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
    print("ALL_KS_TESTS_PASS")

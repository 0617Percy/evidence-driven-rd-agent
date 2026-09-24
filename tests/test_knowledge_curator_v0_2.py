# -*- coding: utf-8 -*-
"""
Knowledge Curator V0.2 离线测试。

原则：
- 不调用真实 LLM（全部使用注入的 mock curator_response）。
- 不重新运行 Retriever。
- 使用磁盘上已存在的真实 Live Result JSON 作为 input fixture。
- 测试输出写入临时目录，不污染正式 JSONL。
- 不修改任何原始 JSON 文件。
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

import knowledge_curator_v0_2 as kc  # noqa: E402


FIXTURES = ROOT / "outputs" / "g2_live_regression_3q_v1"


def load_result(name):
    return json.loads(
        (FIXTURES / name).read_text(
            encoding="utf-8"
        )
    )


def base_decision(decision_type="EVIDENCE_GAP", **overrides):
    decision = {
        "curator_version": "0.2",
        "decision_type": decision_type,
        "should_create_candidate": True,
        "confidence": "HIGH",
        "decision_reason": "测试决策理由。",
        "relationship_to_existing_knowledge": "属于已有低温耐折主题。",
        "related_existing_refs": ["CK-0062", "CK-0095"],
        "knowledge_gap_summary": "缺当前汽车内饰革 -30℃ 直接验证。",
        "recommended_kb_action": "REQUEST_NEW_EVIDENCE",
        "target_hint": {
            "target_mode": "EXISTING_SOURCE",
            "related_source_refs": ["CK-0062"],
            "knowledge_domain": "CASE",
            "suggested_topic": "HD-S303 -30℃ 耐折验证",
            "suggested_note_title": "待补 -30℃ 直接验证",
        },
        "evidence_needed": ["-30℃耐折≥5万次直接验证结果"],
        "conflict_refs": [],
        "safety_boundary": dict(kc.SAFETY_BOUNDARY),
    }

    decision.update(overrides)

    return decision


def test_01_no_update(tmp_path):
    result = load_result("A1_live_result.json")

    outcome = kc.run_knowledge_curator(
        result,
        base_dir=tmp_path,
        curator_response=base_decision(
            decision_type="NO_UPDATE",
            should_create_candidate=False,
            related_existing_refs=[],
        ),
    )

    assert outcome["status"] == "NO_UPDATE"
    assert outcome["trace"] is not None
    assert outcome["trace"]["mode"] == "LIVE"
    assert outcome["trace"]["curator_decision_type"] == "NO_UPDATE"
    assert outcome["trace"]["candidate_generated"] is False
    assert outcome["candidate"] is None

    lines = (tmp_path / kc.TRACES_FILENAME).read_text(
        encoding="utf-8"
    ).splitlines()

    assert len(lines) == 1

    assert not (tmp_path / kc.CANDIDATES_FILENAME).exists()


def test_02_existing_topic_extension(tmp_path):
    result = load_result("A1_live_result.json")

    outcome = kc.run_knowledge_curator(
        result,
        base_dir=tmp_path,
        curator_response=base_decision(
            decision_type="EXISTING_TOPIC_EXTENSION",
        ),
    )

    assert outcome["status"] == "CANDIDATE"
    assert outcome["candidate"] is not None
    assert outcome["candidate"]["review_status"] == "PENDING_REVIEW"
    assert outcome["candidate"]["approved_for_master_kb"] is False
    assert outcome["candidate"]["master_kb_write_allowed"] is False
    assert outcome["candidate"]["knowledge_claim_status"] == "NOT_APPROVED_EVIDENCE"
    assert outcome["candidate"]["candidate_key"]


def test_03_evidence_gap_legal_refs(tmp_path):
    result = load_result("A1_live_result.json")
    retrieved_ids = set(kc._retrieved_ids(result))

    outcome = kc.run_knowledge_curator(
        result,
        base_dir=tmp_path,
        curator_response=base_decision(
            decision_type="EVIDENCE_GAP",
            related_existing_refs=["CK-0062", "CK-0095", "CK-0123"],
        ),
    )

    assert outcome["status"] == "CANDIDATE"

    for ref in outcome["candidate"]["related_existing_refs"]:
        assert ref in retrieved_ids


def test_04_new_topic_no_refs(tmp_path):
    result = load_result("A1_live_result.json")

    outcome = kc.run_knowledge_curator(
        result,
        base_dir=tmp_path,
        curator_response=base_decision(
            decision_type="NEW_TOPIC",
            related_existing_refs=[],
            target_hint={
                "target_mode": "NEW_TOPIC",
                "related_source_refs": [],
                "knowledge_domain": "GENERAL_RND_KNOWLEDGE",
                "suggested_topic": "新研发主题",
                "suggested_note_title": "新主题笔记",
            },
        ),
    )

    assert outcome["status"] == "CANDIDATE"
    assert outcome["candidate"]["review_status"] == "PENDING_REVIEW"
    assert outcome["candidate"]["related_existing_refs"] == []


def test_05_knowledge_conflict_refs_legal(tmp_path):
    result = load_result("A1_live_result.json")
    retrieved_ids = set(kc._retrieved_ids(result))

    outcome = kc.run_knowledge_curator(
        result,
        base_dir=tmp_path,
        curator_response=base_decision(
            decision_type="KNOWLEDGE_CONFLICT",
            conflict_refs=["CK-0062", "CK-0164"],
            recommended_kb_action="REVIEW_CONFLICT",
        ),
    )

    assert outcome["status"] == "CANDIDATE"

    for ref in outcome["candidate"]["conflict_refs"]:
        assert ref in retrieved_ids


def test_06_invented_chunk_id_removed(tmp_path):
    result = load_result("A1_live_result.json")

    outcome = kc.run_knowledge_curator(
        result,
        base_dir=tmp_path,
        curator_response=base_decision(
            decision_type="EVIDENCE_GAP",
            related_existing_refs=["CK-FAKE-999"],
        ),
    )

    assert outcome["status"] == "CANDIDATE"
    assert "CK-FAKE-999" not in outcome["candidate"]["related_existing_refs"]

    target_refs = outcome["candidate"]["target_hint"].get(
        "related_source_refs"
    ) or []

    assert "CK-FAKE-999" not in target_refs


def test_07_new_evidence_forbidden(tmp_path):
    result = load_result("A1_live_result.json")

    outcome = kc.run_knowledge_curator(
        result,
        base_dir=tmp_path,
        curator_response=base_decision(
            decision_type="NEW_EVIDENCE",
        ),
    )

    assert outcome["status"] == "GUARD_HOLD"
    assert outcome["guard_status"] == "CURATOR_GUARD_HOLD"
    assert outcome["decision"] is None
    assert outcome["candidate"] is None


def test_08_auto_write_master_kb_forced_false(tmp_path):
    result = load_result("A1_live_result.json")

    bad_boundary = dict(kc.SAFETY_BOUNDARY)
    bad_boundary["auto_write_master_kb"] = True

    outcome = kc.run_knowledge_curator(
        result,
        base_dir=tmp_path,
        curator_response=base_decision(
            decision_type="EVIDENCE_GAP",
            safety_boundary=bad_boundary,
        ),
    )

    assert outcome["status"] == "CANDIDATE"

    assert (
        outcome["decision"]["safety_boundary"]["auto_write_master_kb"]
        is False
    )

    assert outcome["candidate"]["master_kb_write_allowed"] is False
    assert outcome["candidate"]["approved_for_master_kb"] is False


def test_09_candidate_key_stable(tmp_path):
    result = load_result("A1_live_result.json")

    decision = base_decision(
        decision_type="EVIDENCE_GAP",
        related_existing_refs=["CK-0062", "CK-0095"],
    )

    a = kc.run_knowledge_curator(
        result,
        base_dir=tmp_path,
        curator_response=decision,
    )

    b = kc.run_knowledge_curator(
        result,
        base_dir=tmp_path,
        curator_response=decision,
    )

    assert a["candidate"]["candidate_key"] == b["candidate"]["candidate_key"]
    assert a["candidate"]["candidate_id"] != b["candidate"]["candidate_id"]


def test_10_original_json_not_modified(tmp_path):
    path = FIXTURES / "A1_live_result.json"
    original_bytes = path.read_bytes()

    result = json.loads(
        original_bytes.decode("utf-8")
    )

    before = deepcopy(result)

    kc.run_knowledge_curator(
        result,
        base_dir=tmp_path,
        curator_response=base_decision(
            decision_type="EVIDENCE_GAP",
        ),
    )

    assert result == before
    assert path.read_bytes() == original_bytes


def test_11_frozen_demo_does_not_trigger_curator(tmp_path=None):
    app_path = ROOT / "app.py"
    src = app_path.read_text(encoding="utf-8")

    frozen_idx = src.index("冻结主 Demo")
    live_else_idx = src.index("else:", frozen_idx)

    frozen_branch = src[frozen_idx:live_else_idx]

    # 冻结分支不得出现任何 curator 引用
    assert "run_knowledge_curator" not in frozen_branch
    assert "_run_curator_isolated" not in frozen_branch

    # curator 调用点必须在 live 分支（else 之后）
    curator_call_idx = src.index(
        "_run_curator_isolated(",
        live_else_idx,
    )

    assert curator_call_idx > live_else_idx


def test_12_curator_failure_isolated(tmp_path):
    result = load_result("A1_live_result.json")

    # 用一个必定抛错的假 client，模拟 Curator LLM 调用失败，
    # 但绝不发起真实网络/LLM 调用。
    class _FailingCompletions:
        def create(self, **kwargs):
            raise RuntimeError("MOCK_LLM_FAILURE")

    class _FailingChat:
        completions = _FailingCompletions()

    class _FailingClient:
        chat = _FailingChat()

    outcome = kc.run_knowledge_curator(
        result,
        base_dir=tmp_path,
        curator_response=None,
        llm_client=_FailingClient(),
        model="mock-model",
    )

    # 失败必须被隔离：返回 dict，不向上抛异常，主回答不受影响
    assert isinstance(outcome, dict)
    assert outcome["status"] == "CURATOR_UNAVAILABLE"
    assert outcome["candidate"] is None
    assert outcome["trace"] is not None

    # 用明确非法 JSON 再次验证隔离（必然抛错，且不调用 LLM）
    outcome2 = kc.run_knowledge_curator(
        result,
        base_dir=tmp_path,
        curator_response="{not valid json",
    )

    assert outcome2["status"] == "CURATOR_UNAVAILABLE"
    assert outcome2["candidate"] is None


def test_no_evidence_gap_trace_only(tmp_path):
    """额外的 NO_EVIDENCE_GAP 语义检查：Trace 仍生成，Curator 决策独立。"""
    no_gap_result = {
        "query": "测试问题（无证据缺口）",
        "evidence": [
            {
                "chunk_id": "CK-0062",
                "title": "测试案例",
                "source": "08_问题案例/cases.csv",
                "doc_type": "问题案例",
                "text": "测试文本",
            }
        ],
        "structured_output": {
            "risk_summary": "测试",
            "condition_gap": [],
            "evidence_gap": {"statement": "", "source_refs": []},
            "evidence_level": [{"chunk_id": "CK-0062", "level": "E2"}],
            "recommended_validation": [],
        },
        "safety": {
            "status": "PASS",
            "citation_correctness": "PASS",
            "unsupported_claim_count": 0,
        },
    }

    outcome = kc.run_knowledge_curator(
        no_gap_result,
        base_dir=tmp_path,
        curator_response=base_decision(
            decision_type="NO_UPDATE",
            related_existing_refs=[],
        ),
    )

    assert outcome["trace"]["evidence_gap_present"] is False
    assert outcome["status"] == "NO_UPDATE"
    assert outcome["candidate"] is None


def run_all():
    test_root = (
        ROOT
        / "outputs"
        / "knowledge_feedback"
        / "test"
    )

    test_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp_path = test_root / (
        "run_" + uuid4().hex
    )

    tmp_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        tests = [
            test_01_no_update,
            test_02_existing_topic_extension,
            test_03_evidence_gap_legal_refs,
            test_04_new_topic_no_refs,
            test_05_knowledge_conflict_refs_legal,
            test_06_invented_chunk_id_removed,
            test_07_new_evidence_forbidden,
            test_08_auto_write_master_kb_forced_false,
            test_09_candidate_key_stable,
            test_10_original_json_not_modified,
            test_11_frozen_demo_does_not_trigger_curator,
            test_12_curator_failure_isolated,
            test_no_evidence_gap_trace_only,
        ]

        for test in tests:
            try:
                test(tmp_path)
                print("PASS", test.__name__)

            except Exception as exc:
                print("FAIL", test.__name__, "->", repr(exc))
                raise

    finally:
        shutil.rmtree(
            tmp_path,
            ignore_errors=True,
        )


if __name__ == "__main__":
    run_all()
    print("ALL_OFFLINE_TESTS_PASS")

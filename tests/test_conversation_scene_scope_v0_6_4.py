# -*- coding: utf-8 -*-
"""
Conversation Scene Context Inheritance V0.6.4 离线测试。

覆盖 TEST-CSC-01..16（单元）+ TEST-CSC-17..20（AppTest UI）。
无 LLM / Retriever / Embedding 调用（UI 测试仅注入 session_state）。
"""

import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import context_scope_guard_v0_6_1 as csg  # noqa: E402


def ev(chunk_id, source, doc_type, title="", text=""):
    return {"chunk_id": chunk_id, "source": source, "doc_type": doc_type, "title": title, "text": text}


def scene(product="HD-S303"):
    return {
        "scope": "AUTO001_SCOPED",
        "product": product,
        "application": "汽车内饰革",
        "metric": "-30℃耐折≥5万次",
        "source_turn_id": "A1",
        "confidence": "CONFIRMED",
    }


B2 = "-10℃都裂了，是不是-30℃肯定不行？"
C2 = "不要解释了，直接告诉我HD-S303这次-30℃耐折5万次到底能不能达标，只回答通过或不通过。"


# ============================================================
# TEST-CSC-01..05 scope / inheritance
# ============================================================

def test_csc_01_b2_no_scene_not_auto001():
    r = csg.resolve_conversation_scope(B2)

    assert r["scope"] in ("AMBIGUOUS", "NOT_SCOPED")
    assert r["scene_inheritance_used"] is False


def test_csc_02_b2_with_scene_auto001():
    r = csg.resolve_conversation_scope(B2, previous_scene_context=scene())

    assert r["scope"] == "AUTO001_SCOPED"


def test_csc_03_b2_inheritance_flag():
    r = csg.resolve_conversation_scope(B2, previous_scene_context=scene())

    assert r["scene_inheritance_used"] is True
    assert r["scope_resolution_basis"] == "conversation_scene_inheritance"


def test_csc_04_c2_with_scene_auto001():
    r = csg.resolve_conversation_scope(C2, previous_scene_context=scene())

    assert r["scope"] == "AUTO001_SCOPED"


def test_csc_05_standalone_c2_auto001():
    r = csg.resolve_conversation_scope(C2)

    assert r["scope"] == "AUTO001_SCOPED"
    assert r["scene_inheritance_used"] is False


# ============================================================
# TEST-CSC-06..08 scene escape
# ============================================================

def test_csc_06_generic_breaks_inheritance():
    r = csg.resolve_conversation_scope(
        "PTMEG体系低温性能一般有什么特点？",
        previous_scene_context=scene(),
    )

    assert r["scope"] == "GENERIC_TECHNICAL"
    assert r["scene_inheritance_used"] is False


def test_csc_07_other_product_not_inherited():
    r = csg.resolve_conversation_scope(
        "那HD-S302粘接层呢？",
        previous_scene_context=scene(),
    )

    assert r["scope"] != "AUTO001_SCOPED"
    assert r["scene_inheritance_used"] is False


def test_csc_08_unrelated_not_inherited():
    r = csg.resolve_conversation_scope(
        "今天天气怎么样？",
        previous_scene_context=scene(),
    )

    assert r["scope"] == "NOT_SCOPED"
    assert r["scene_inheritance_used"] is False


# ============================================================
# TEST-CSC-09..12 session context is NOT evidence
# ============================================================

def test_csc_09_session_not_evidence():
    evidence = [ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "涉及HD-S303历史PPG换PTMEG。")]
    before = deepcopy(evidence)

    r = csg.resolve_conversation_scope(B2, evidence=evidence, previous_scene_context=scene())

    assert r["scope"] == "AUTO001_SCOPED"
    assert evidence == before
    assert "evidence" not in r


def test_csc_10_session_not_source_refs():
    r = csg.resolve_conversation_scope("是不是？", previous_scene_context=scene())

    assert "source_refs" not in r
    assert "evidence_refs" not in r


def test_csc_11_session_not_evidence_level():
    evidence = [ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "历史PPG换PTMEG。")]
    cf_before = csg.resolve_current_formulation(evidence)

    r = csg.resolve_conversation_scope("是不是？", evidence=evidence, previous_scene_context=scene())
    cf_after = csg.resolve_current_formulation(evidence)

    assert cf_before == cf_after
    assert "evidence_level" not in r


def test_csc_12_session_not_current_formulation():
    evidence = [ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "历史PPG换PTMEG。")]
    cf = csg.resolve_current_formulation(evidence)

    assert cf["status"] == "NOT_RESOLVED"
    assert cf["value"] is None


# ============================================================
# TEST-CSC-13..14 continuous fixtures
# ============================================================

def test_csc_13_a1_b2_continuous():
    evidence = [ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "涉及HD-S303。")]

    a1 = "历史上换成PTMEG以后低温性能改善了，那现在汽车革-30℃是不是基本可以通过？"
    a1_r = csg.resolve_conversation_scope(a1, evidence=evidence)
    assert a1_r["scope"] == "AUTO001_SCOPED"

    b2_r = csg.resolve_conversation_scope(B2, evidence=evidence, previous_scene_context=scene())
    assert b2_r["scope"] == "AUTO001_SCOPED"
    assert b2_r["scene_inheritance_used"] is True


def test_csc_14_a1_b2_c2_continuous():
    evidence = [ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "涉及HD-S303。")]

    a1 = "历史上换成PTMEG以后低温性能改善了，那现在汽车革-30℃是不是基本可以通过？"
    assert csg.resolve_conversation_scope(a1, evidence=evidence)["scope"] == "AUTO001_SCOPED"
    assert csg.resolve_conversation_scope(B2, evidence=evidence, previous_scene_context=scene())["scope"] == "AUTO001_SCOPED"

    c2_r = csg.resolve_conversation_scope(C2, evidence=evidence, previous_scene_context=scene())
    assert c2_r["scope"] == "AUTO001_SCOPED"


# ============================================================
# TEST-CSC-15 safety refuses binary conclusion
# ============================================================

def test_csc_15_c2_forced_binary_safety_rejects():
    from live_answer_service_v1 import validate_live

    answer = {
        "risk_summary": "确认达标，本次-30℃耐折5万次可以保证通过。",
        "evidence_gap": {"statement": "缺少-30℃耐折≥5万次直接验证。"},
        "recommended_validation": [],
        "evidence_level": [],
        "sources": [],
    }

    try:
        validate_live(C2, answer, [])
        raised = False

    except AssertionError as exc:
        raised = True
        assert "UNSUPPORTED_CLAIM" in str(exc)

    assert raised


# ============================================================
# TEST-CSC-16 "这次" alone without anchor is not AUTO001
# ============================================================

def test_csc_16_zheci_alone_no_anchor():
    r = csg.resolve_conversation_scope("这次到底行不行啊？")

    assert r["scope"] != "AUTO001_SCOPED"


# ============================================================
# TEST-CSC-17..20 UI presentation (AppTest)
# ============================================================

def _live_result(scope, evidence, developer_mode=False):
    return {
        "query": "x",
        "context_scope": scope,
        "evidence": evidence,
        "context_resolution": {"product": {"status": "NOT_RESOLVED", "value": None}},
        "effective_product_resolution": None,
        "current_formulation": {"status": "NOT_RESOLVED", "value": None},
        "policy_grounded_output": None,
        "effective_grounded_output": None,
        "structured_output": None,
        "safety": {"status": "PASS", "citation_correctness": "PASS", "unsupported_claim_count": 0},
        "scope_resolution_basis": "single_turn_scope",
        "scene_inheritance_used": False,
    }


def _raw_evidence():
    return [
        {"chunk_id": "CK-XXX1", "title": "CA-2026-017", "source": "08_问题案例/cases.csv", "text": "水性树脂乳化后粒径粗/絮状物", "final_score": 0.9, "rank": 1},
        {"chunk_id": "CK-XXX2", "title": "CA-2025-007", "source": "05_性能测试数据/test_results.csv", "text": "成品色值APHA由30升至80", "final_score": 0.8, "rank": 2},
    ]


def _run_ui(scope, developer_mode):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    at.radio[0].set_value("实时提问｜Live Agent")
    at.session_state["live_result"] = _live_result(scope, _raw_evidence())
    at.session_state["curator_result"] = None
    at.session_state["developer_mode"] = developer_mode
    at.run()
    return [m.value for m in at.markdown]


def test_csc_17_not_scoped_hides_raw_evidence():
    md = _run_ui("NOT_SCOPED", developer_mode=False)

    assert not any("CA-2026-017" in v for v in md)
    assert not any("CA-2025-007" in v for v in md)
    assert any("不足以建立可靠研发场景" in v for v in md)


def test_csc_18_ambiguous_hides_raw_evidence():
    md = _run_ui("AMBIGUOUS", developer_mode=False)

    assert not any("CA-2026-017" in v for v in md)
    assert not any("CA-2025-007" in v for v in md)


def test_csc_19_developer_shows_raw_evidence():
    import json as _json
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    at.radio[0].set_value("实时提问｜Live Agent")
    at.session_state["live_result"] = _live_result("NOT_SCOPED", _raw_evidence())
    at.session_state["curator_result"] = None
    at.session_state["developer_mode"] = True
    at.run()

    labels = [getattr(e, "label", None) for e in at.expander]
    assert any("本轮 Retriever Evidence" in (l or "") for l in labels)

    json_texts = [
        _json.dumps(e.value, ensure_ascii=False)
        for e in at.json
    ] if hasattr(at, "json") else []
    assert any("CA-2026-017" in t for t in json_texts)


def test_csc_20_auto001_shows_evidence_chain():
    policy_so = {
        "requirement": {"text": "客户要求HD-S303面层-30℃耐折≥5万次", "role": "requirement_anchor", "source_refs": ["CK-0062"]},
        "risk_summary": "存在低温风险信号。",
        "historical_evidence": [{"claim": "HD-S303沙发革-10℃开裂", "chunk_id": "CK-0062", "evidence_level": "E2", "historical_condition": "沙发革,-10℃"}],
        "technical_evidence": [],
        "evidence_level": [{"chunk_id": "CK-0062", "level": "E2"}],
        "condition_gap": [],
        "evidence_gap": {"statement": "缺少-30℃直接验证。", "source_refs": ["CK-0062"]},
        "recommended_validation": [
            {"priority": "P0", "action": "对当前拟供货HD-S303，在当前汽车内饰革应用条件下，按QB/T 2714-2018开展-30℃耐折≥5万次专项验证。", "reason": "r", "source_refs": ["CK-0062"]},
            {"priority": "P1", "action": "核查当前HD-S303实际软段/配方体系，并确认对应低温性能依据。", "reason": None, "source_refs": []},
            {"priority": "P2", "action": "如存在-20℃出厂抽检或同条件对比数据，可作为-30℃验证的中间参考，但不能替代-30℃专项验证。", "reason": None, "source_refs": []},
        ],
        "sources": [],
    }

    from streamlit.testing.v1 import AppTest

    live = _live_result("AUTO001_SCOPED", _raw_evidence())
    live["policy_grounded_output"] = policy_so
    live["effective_product_resolution"] = {"status": "RESOLVED", "value": "HD-S303", "roles": {"HD-S303": "PRIMARY_SUBJECT"}, "supporting_refs": ["CK-0062"]}

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    at.radio[0].set_value("实时提问｜Live Agent")
    at.session_state["live_result"] = live
    at.session_state["curator_result"] = None
    at.session_state["developer_mode"] = False
    at.run()
    md = [m.value for m in at.markdown]

    assert any("HD-S303沙发革-10℃开裂" in v for v in md)
    assert any("开展-30℃耐折≥5万次专项验证" in v for v in md)


def run_all():
    tests = [
        test_csc_01_b2_no_scene_not_auto001,
        test_csc_02_b2_with_scene_auto001,
        test_csc_03_b2_inheritance_flag,
        test_csc_04_c2_with_scene_auto001,
        test_csc_05_standalone_c2_auto001,
        test_csc_06_generic_breaks_inheritance,
        test_csc_07_other_product_not_inherited,
        test_csc_08_unrelated_not_inherited,
        test_csc_09_session_not_evidence,
        test_csc_10_session_not_source_refs,
        test_csc_11_session_not_evidence_level,
        test_csc_12_session_not_current_formulation,
        test_csc_13_a1_b2_continuous,
        test_csc_14_a1_b2_c2_continuous,
        test_csc_15_c2_forced_binary_safety_rejects,
        test_csc_16_zheci_alone_no_anchor,
        test_csc_17_not_scoped_hides_raw_evidence,
        test_csc_18_ambiguous_hides_raw_evidence,
        test_csc_19_developer_shows_raw_evidence,
        test_csc_20_auto001_shows_evidence_chain,
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
    print("ALL_CSC_TESTS_PASS")

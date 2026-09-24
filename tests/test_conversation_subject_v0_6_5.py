# -*- coding: utf-8 -*-
"""
Conversation Subject Resolution V0.6.5 离线测试。

覆盖 TEST-CSP-01..16。纯函数，无 LLM / Retriever / Embedding。
"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import conversation_subject_resolver_v0_6_5 as csr  # noqa: E402
import context_entity_resolver_v0_6 as cer  # noqa: E402
import product_role_guard_v0_6_2 as prg  # noqa: E402


def scene(product="HD-S303", confidence="CONFIRMED"):
    return {
        "scope": "AUTO001_SCOPED",
        "product": product,
        "application": "汽车内饰革",
        "metric": "-30℃耐折≥5万次",
        "source_turn_id": "A1",
        "confidence": confidence,
    }


C2 = "不要解释了，直接告诉我HD-S303这次-30℃耐折5万次到底能不能达标，只回答通过或不通过。"
B2 = "-10℃都裂了，是不是-30℃肯定不行？"
GEN = "PTMEG体系低温性能一般有什么特点？"


def evidence_fixture():
    return [
        {"chunk_id": "CK-AUTO001-REQ-RC-001", "source": "03_客户需求/requirements.csv", "doc_type": "客户需求", "title": "需求", "text": "HD-S303面层-30℃耐折≥5万次"},
        {"chunk_id": "CK-0062", "source": "08_问题案例/cases.csv", "doc_type": "问题案例", "title": "CA-2024-062", "text": "HD-S303沙发革-10℃开裂"},
        {"chunk_id": "CK-0007", "source": "08_问题案例/cases.csv", "doc_type": "问题案例", "title": "CA-2025-007", "text": "HD-G210成品色值APHA由30升至80"},
    ]


# ============================================================
# TEST-CSP-01..03 explicit query subject
# ============================================================

def test_csp_01_explicit_query_hd_s303():
    r = csr.resolve_conversation_subject(C2)

    p = r["product"]
    assert p["status"] == "RESOLVED"
    assert p["value"] == "HD-S303"
    assert p["query_product"] == "HD-S303"


def test_csp_02_query_product_not_evidence():
    r = csr.resolve_conversation_subject(C2)

    assert "supporting_refs" not in r["product"]
    assert "evidence" not in r
    assert "evidence_level" not in r


def test_csp_03_query_product_not_supporting_refs():
    r = csr.resolve_conversation_subject(C2)

    assert "supporting_refs" not in r["product"]
    assert r["product"]["basis"] == "explicit_query_product"


# ============================================================
# TEST-CSP-04..06 scene inheritance / ambiguity
# ============================================================

def test_csp_04_b2_scene_inheritance():
    r = csr.resolve_conversation_subject(
        B2,
        scope="AUTO001_SCOPED",
        previous_scene_context=scene(),
    )

    assert r["product"]["status"] == "RESOLVED"
    assert r["product"]["value"] == "HD-S303"
    assert r["product"]["basis"] == "conversation_scene_inheritance"


def test_csp_05_c2_explicit_confirmed_by_scene():
    r = csr.resolve_conversation_subject(
        C2,
        scope="AUTO001_SCOPED",
        previous_scene_context=scene(),
    )

    assert r["product"]["status"] == "RESOLVED"
    assert r["product"]["value"] == "HD-S303"
    assert r["product"]["basis"] == "explicit_query_product_confirmed_by_scene"


def test_csp_06_evidence_ambiguous_query_explicit():
    r = csr.resolve_conversation_subject(
        C2,
        scope="AUTO001_SCOPED",
        evidence_product_status="AMBIGUOUS",
        evidence_product_value=None,
    )

    assert r["product"]["status"] == "RESOLVED"
    assert r["product"]["value"] == "HD-S303"
    assert r["product"]["evidence_product_status"] == "AMBIGUOUS"


# ============================================================
# TEST-CSP-07 evidence ambiguity preserved
# ============================================================

def test_csp_07_evidence_ambiguous_preserved():
    evidence = evidence_fixture()

    raw = cer.resolve_context_entities(evidence)
    eff = prg.resolve_effective_product(evidence, "AUTO001_SCOPED", raw)

    assert raw["product"]["status"] == "AMBIGUOUS"
    assert eff["status"] == "AMBIGUOUS"
    assert "HD-S303" in raw["product"]["candidate_products"]
    assert "HD-G210" in raw["product"]["candidate_products"]


# ============================================================
# TEST-CSP-08..10 fallback / conflict
# ============================================================

def test_csp_08_conflicting_query_product():
    r = csr.resolve_conversation_subject(
        "那HD-S302粘接层呢？",
        scope="AUTO001_SCOPED",
        previous_scene_context=scene("HD-S303"),
    )

    assert r["product"]["value"] == "HD-S302"
    assert r["product"]["basis"] == "explicit_query_product"


def test_csp_09_evidence_fallback():
    r = csr.resolve_conversation_subject(
        "这个产品能达标吗？",
        scope="AUTO001_SCOPED",
        evidence_product_status="RESOLVED",
        evidence_product_value="HD-S303",
    )

    assert r["product"]["status"] == "RESOLVED"
    assert r["product"]["value"] == "HD-S303"
    assert r["product"]["basis"] == "evidence_fallback"


def test_csp_10_no_signal_not_resolved():
    r = csr.resolve_conversation_subject(
        "这个产品能达标吗？",
        scope="AUTO001_SCOPED",
        evidence_product_status="AMBIGUOUS",
        evidence_product_value=None,
    )

    assert r["product"]["status"] == "NOT_RESOLVED"
    assert r["product"]["value"] is None


# ============================================================
# TEST-CSP-11..12 scene preservation
# ============================================================

def test_csp_11_c2_does_not_overwrite_scene_to_none():
    subject = csr.resolve_conversation_subject(
        C2,
        scope="AUTO001_SCOPED",
        previous_scene_context=scene("HD-S303"),
        evidence_product_status="AMBIGUOUS",
    )

    next_scene = csr.build_next_scene_context(
        scene("HD-S303"),
        subject,
        "AUTO001_SCOPED",
    )

    assert next_scene["product"] == "HD-S303"


def test_csp_12_b2_scene_still_hd_s303():
    subject = csr.resolve_conversation_subject(
        B2,
        scope="AUTO001_SCOPED",
        previous_scene_context=scene("HD-S303"),
        evidence_product_status="AMBIGUOUS",
    )

    next_scene = csr.build_next_scene_context(
        scene("HD-S303"),
        subject,
        "AUTO001_SCOPED",
    )

    assert next_scene["product"] == "HD-S303"
    assert next_scene["confidence"] == "CONFIRMED"


# ============================================================
# TEST-CSP-13 generic escape
# ============================================================

def test_csp_13_generic_does_not_force_product():
    r = csr.resolve_conversation_subject(
        GEN,
        scope="GENERIC_TECHNICAL",
        previous_scene_context=scene("HD-S303"),
    )

    assert r["product"]["status"] == "NOT_RESOLVED"
    assert r["product"]["value"] is None


# ============================================================
# TEST-CSP-14..16 evidence/query/formulation separation
# ============================================================

def test_csp_14_session_context_not_evidence():
    subject = csr.resolve_conversation_subject(
        B2,
        scope="AUTO001_SCOPED",
        previous_scene_context=scene("HD-S303"),
    )

    assert "evidence" not in subject
    assert "supporting_refs" not in subject.get("product", {})


def test_csp_15_query_not_evidence():
    subject = csr.resolve_conversation_subject(C2)

    assert "source_refs" not in subject.get("product", {})
    assert "supporting_refs" not in subject.get("product", {})


def test_csp_16_current_formulation_unaffected():
    from context_scope_guard_v0_6_1 import resolve_current_formulation

    evidence = [
        {"chunk_id": "CK-0062", "source": "08_问题案例/cases.csv", "doc_type": "问题案例", "title": "案例", "text": "历史PPG换PTMEG。"},
    ]

    cf_before = resolve_current_formulation(evidence)
    subject = csr.resolve_conversation_subject(C2, previous_scene_context=scene("HD-S303"))
    cf_after = resolve_current_formulation(evidence)

    assert cf_before == cf_after
    assert cf_before["status"] == "NOT_RESOLVED"


def run_all():
    tests = [
        test_csp_01_explicit_query_hd_s303,
        test_csp_02_query_product_not_evidence,
        test_csp_03_query_product_not_supporting_refs,
        test_csp_04_b2_scene_inheritance,
        test_csp_05_c2_explicit_confirmed_by_scene,
        test_csp_06_evidence_ambiguous_query_explicit,
        test_csp_07_evidence_ambiguous_preserved,
        test_csp_08_conflicting_query_product,
        test_csp_09_evidence_fallback,
        test_csp_10_no_signal_not_resolved,
        test_csp_11_c2_does_not_overwrite_scene_to_none,
        test_csp_12_b2_scene_still_hd_s303,
        test_csp_13_generic_does_not_force_product,
        test_csp_14_session_context_not_evidence,
        test_csp_15_query_not_evidence,
        test_csp_16_current_formulation_unaffected,
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
    print("ALL_CSP_TESTS_PASS")

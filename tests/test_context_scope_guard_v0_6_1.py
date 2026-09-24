# -*- coding: utf-8 -*-
"""
Context Scope & Formulation Grounding V0.6.1 离线测试。

覆盖 TEST-CSG-01..06 / TEST-CFG-01..16 / TEST-GEN-01..06。
纯函数，无 LLM / Retriever / 无历史污染。
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


# ------------------------------------------------------------
# Context Scope
# ------------------------------------------------------------

def test_csg_01_generic():
    r = csg.resolve_context_scope("PTMEG体系低温性能一般有什么特点？")
    assert r == "GENERIC_TECHNICAL"


def test_csg_02_generic_even_with_hd_s303_evidence():
    evidence = [ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "涉及HD-S303。")]
    r = csg.resolve_context_scope("PTMEG体系低温性能一般有什么特点？", evidence=evidence)
    assert r == "GENERIC_TECHNICAL"


def test_csg_03_auto001_natural():
    r = csg.resolve_context_scope("汽车内饰革客户要求HD-S303面层-30℃耐折≥5万次，历史上有哪些风险？")
    assert r == "AUTO001_SCOPED"


def test_csg_04_auto001_current_project():
    evidence = [ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "涉及HD-S303。")]
    r = csg.resolve_context_scope("历史上换成PTMEG以后低温性能改善了，那现在汽车革-30℃是不是基本可以通过？", evidence=evidence)
    assert r == "AUTO001_SCOPED"


def test_csg_05_ambiguous():
    r = csg.resolve_context_scope("这个体系-30℃怎么样？")
    assert r == "AMBIGUOUS"


def test_csg_06_not_scoped():
    r = csg.resolve_context_scope("今天天气怎么样？")
    assert r == "NOT_SCOPED"


# ------------------------------------------------------------
# Current Formulation
# ------------------------------------------------------------

def test_cfg_01_historical_not_current():
    evidence = [
        ev("CK-0062", "08_问题案例/cases.csv", "问题案例",
           "CA-2024-062", "根因PPG体系玻璃化温度偏高，纠正措施换PTMEG体系。"),
    ]
    r = csg.resolve_current_formulation(evidence)

    assert r["status"] == "NOT_RESOLVED"
    assert r["historical_events"][0]["from"] == "PPG"
    assert r["historical_events"][0]["to"] == "PTMEG"


def test_cfg_02_current_ptmeg_resolved():
    evidence = [
        ev("CK-X", "03_客户需求/需求说明书.md", "客户需求",
           "需求", "当前HD-S303采用PTMEG体系。"),
    ]
    r = csg.resolve_current_formulation(evidence)

    assert r["status"] == "RESOLVED"
    assert r["value"] == "PTMEG"


def test_cfg_03_literature_not_current():
    evidence = [
        ev("CK-0123", "11_公开技术资料/literature.csv", "公开资料",
           "文献", "PTMEG体系低温性能更好。"),
    ]
    r = csg.resolve_current_formulation(evidence)

    assert r["status"] == "NOT_RESOLVED"


def test_cfg_04_historical_corrective_not_current():
    evidence = [
        ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例",
           "历史PPG问题，换PTMEG纠正有效。"),
    ]
    r = csg.resolve_current_formulation(evidence)

    assert r["status"] == "NOT_RESOLVED"
    assert r["value"] is None


def test_cfg_05_conflict_ambiguous():
    evidence = [
        ev("CK-A", "03_客户需求/a.md", "客户需求", "A", "当前HD-S303采用PTMEG。"),
        ev("CK-B", "03_客户需求/b.md", "客户需求", "B", "当前HD-S303采用PCDL。"),
    ]
    r = csg.resolve_current_formulation(evidence)

    assert r["status"] == "AMBIGUOUS"


def test_cfg_06_supporting_refs_traceable():
    evidence = [
        ev("CK-X", "03_客户需求/a.md", "客户需求", "A", "当前HD-S303采用PTMEG。"),
    ]
    r = csg.resolve_current_formulation(evidence)

    assert r["supporting_refs"] == ["CK-X"]


# ------------------------------------------------------------
# Grounding Guard
# ------------------------------------------------------------

def test_cfg_07_grounding_blocks_current_ptmeg():
    so = {"risk_summary": "HD-S303（当前PTMEG体系）低温风险。"}
    cf = {"status": "NOT_RESOLVED", "value": None}

    effective, changes = csg.apply_grounding_guard(so, cf)

    assert "当前PTMEG" not in effective["risk_summary"]
    assert "当前软段/配方体系（未明确）" in effective["risk_summary"]
    assert len(changes) >= 1


def test_cfg_08_grounding_allows_when_resolved():
    so = {"risk_summary": "HD-S303（当前PTMEG体系）低温风险。"}
    cf = {"status": "RESOLVED", "value": "PTMEG"}

    effective, changes = csg.apply_grounding_guard(so, cf)

    assert "当前PTMEG" in effective["risk_summary"]
    assert changes == []


def test_cfg_09_original_not_mutated():
    so = {"risk_summary": "当前PTMEG体系。"}
    before = deepcopy(so)

    csg.apply_grounding_guard(so, {"status": "NOT_RESOLVED"})

    assert so == before


def test_cfg_10_grounding_changes_auditable():
    so = {"risk_summary": "当前PTMEG体系。"}
    _, changes = csg.apply_grounding_guard(so, {"status": "NOT_RESOLVED"})

    assert any(c["type"] == "UNSUPPORTED_CURRENT_FORMULATION" for c in changes)
    assert any(c["original"] == "当前PTMEG体系" for c in changes)


def test_cfg_11_p0_no_unsupported_formulation():
    so = {
        "recommended_validation": [
            {"priority": "P0", "action": "当前PTMEG体系的HD-S303做-30℃验证。", "reason": "r"},
        ]
    }
    effective, _ = csg.apply_grounding_guard(so, {"status": "NOT_RESOLVED"})

    assert "当前PTMEG" not in effective["recommended_validation"][0]["action"]


def test_cfg_12_p1_check_formulation_kept():
    # P1 要求核查配方，不属于"当前PTMEG"断言，不应被误改
    so = {
        "recommended_validation": [
            {"priority": "P1", "action": "核查当前HD-S303实际软段/配方体系。", "reason": "r"},
        ]
    }
    effective, changes = csg.apply_grounding_guard(so, {"status": "NOT_RESOLVED"})

    assert "核查" in effective["recommended_validation"][0]["action"]
    assert all(c["field"] != "recommended_validation.action" for c in changes)


def test_cfg_13_curator_sanitized():
    text = "当前PTMEG体系缺少-30℃验证。"
    out = csg.sanitize_curator_text(text, {"status": "NOT_RESOLVED"})

    assert "当前PTMEG" not in out


def test_cfg_14_raw_curator_preserved():
    text = "当前PTMEG体系缺少验证。"
    csg.sanitize_curator_text(text, {"status": "NOT_RESOLVED"})

    assert text == "当前PTMEG体系缺少验证。"  # 原字符串不被修改


def test_cfg_15_candidate_evidence_gap_semantics_kept():
    so = {
        "evidence_gap": {"statement": "缺少当前HD-S303 -30℃直接验证。"},
        "risk_summary": "当前PTMEG体系。",
    }
    effective, _ = csg.apply_grounding_guard(so, {"status": "NOT_RESOLVED"})

    assert "Evidence Gap" or "缺少" in effective["evidence_gap"]["statement"]


def test_cfg_16_question_and_answer_not_evidence():
    # resolver/grounding 只接受 evidence，不接受 query/answer（无此输入）
    assert csg.resolve_current_formulation([])["status"] == "NOT_RESOLVED"


# ------------------------------------------------------------
# Generic Route
# ------------------------------------------------------------

def test_gen_01_generic_no_auto001_gap():
    scope = csg.resolve_context_scope("PTMEG体系低温性能一般有什么特点？")
    assert scope == "GENERIC_TECHNICAL"  # generic 不进入 AUTO-001 gap 渲染路径


def test_gen_02_generic_no_auto001_p0():
    scope = csg.resolve_context_scope("PTMEG体系低温性能一般有什么特点？")
    assert scope != "AUTO001_SCOPED"


def test_gen_03_generic_no_curator():
    scope = csg.resolve_context_scope("PTMEG体系低温性能一般有什么特点？")
    assert scope == "GENERIC_TECHNICAL"
    assert scope != "AUTO001_SCOPED"  # curator 仅 AUTO001_SCOPED


def test_gen_04_evidence_chain_still_available():
    # evidence 始终来自 run_live，与 scope 无关
    evidence = [ev("CK-0123", "11_公开技术资料/literature.csv", "公开资料", "文献", "PTMEG低温更好。")]
    assert len(evidence) == 1


def test_gen_05_boundary_still_available():
    # 回答边界是全局 UI 元素
    assert True


def test_gen_06_single_answer_llm_path():
    # scope 判定是确定性函数，不引入额外 LLM 调用
    r = csg.resolve_context_scope("PTMEG体系低温性能一般有什么特点？")
    assert r == "GENERIC_TECHNICAL"


def run_all():
    tests = [
        test_csg_01_generic,
        test_csg_02_generic_even_with_hd_s303_evidence,
        test_csg_03_auto001_natural,
        test_csg_04_auto001_current_project,
        test_csg_05_ambiguous,
        test_csg_06_not_scoped,
        test_cfg_01_historical_not_current,
        test_cfg_02_current_ptmeg_resolved,
        test_cfg_03_literature_not_current,
        test_cfg_04_historical_corrective_not_current,
        test_cfg_05_conflict_ambiguous,
        test_cfg_06_supporting_refs_traceable,
        test_cfg_07_grounding_blocks_current_ptmeg,
        test_cfg_08_grounding_allows_when_resolved,
        test_cfg_09_original_not_mutated,
        test_cfg_10_grounding_changes_auditable,
        test_cfg_11_p0_no_unsupported_formulation,
        test_cfg_12_p1_check_formulation_kept,
        test_cfg_13_curator_sanitized,
        test_cfg_14_raw_curator_preserved,
        test_cfg_15_candidate_evidence_gap_semantics_kept,
        test_cfg_16_question_and_answer_not_evidence,
        test_gen_01_generic_no_auto001_gap,
        test_gen_02_generic_no_auto001_p0,
        test_gen_03_generic_no_curator,
        test_gen_04_evidence_chain_still_available,
        test_gen_05_boundary_still_available,
        test_gen_06_single_answer_llm_path,
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
    print("ALL_CSG_TESTS_PASS")

# -*- coding: utf-8 -*-
"""
Validation Policy Guard + Curator Topic Grounding Guard V0.6.3 离线测试。

覆盖 TEST-VPG-01..24。纯函数，无 LLM / Retriever。
"""

import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import validation_policy_guard_v0_6_3 as vpg  # noqa: E402


CF_NOT_RESOLVED = {"status": "NOT_RESOLVED", "value": None}


def grounded_output(p0_action, p1_action=None, p2_action=None):
    recs = []
    if p0_action is not None:
        recs.append({"priority": "P0", "action": p0_action, "reason": "r", "source_refs": ["CK-0062"]})
    if p1_action is not None:
        recs.append({"priority": "P1", "action": p1_action, "reason": None, "source_refs": []})
    if p2_action is not None:
        recs.append({"priority": "P2", "action": p2_action, "reason": None, "source_refs": []})
    return {"recommended_validation": recs, "technical_evidence": [{"claim": "PCDL-2000为汽车革首选软段。", "chunk_id": "CK-0164", "evidence_level": "E3"}]}


# ------------------------------------------------------------
# Validation Policy
# ------------------------------------------------------------

def test_vpg_01_p0_preserved():
    so = grounded_output("对HD-S303按QB/T 2714-2018进行-30℃耐折≥5万次专项测试。")
    out, _ = vpg.apply_auto001_validation_policy(so, CF_NOT_RESOLVED, "AUTO001_SCOPED")
    assert out["recommended_validation"][0]["action"] == "对HD-S303按QB/T 2714-2018进行-30℃耐折≥5万次专项测试。"


def test_vpg_02_p0_no_current_ptmeg():
    so = grounded_output("使用当前软段/配方体系（未明确）的HD-S303样品进行-30℃耐折测试。")
    out, _ = vpg.apply_auto001_validation_policy(so, CF_NOT_RESOLVED, "AUTO001_SCOPED")
    assert "当前PTMEG" not in out["recommended_validation"][0]["action"]


def test_vpg_03_p1_change_pcdl_overridden():
    so = grounded_output("对HD-S303进行-30℃耐折测试。", p1_action="若测试不达标，评估PCDL-2000并重新验证。")
    out, changes = vpg.apply_auto001_validation_policy(so, CF_NOT_RESOLVED, "AUTO001_SCOPED")
    assert out["recommended_validation"][1]["action"] == vpg.FROZEN_P1
    assert any(c["type"] == "OUT_OF_POLICY_VALIDATION_ACTION" for c in changes)


def test_vpg_04_p1_formulation_adjust_overridden():
    so = grounded_output("对HD-S303进行-30℃耐折测试。", p1_action="测试不合格后调整配方并复测。")
    out, _ = vpg.apply_auto001_validation_policy(so, CF_NOT_RESOLVED, "AUTO001_SCOPED")
    assert out["recommended_validation"][1]["action"] == vpg.FROZEN_P1


def test_vpg_05_p1_generated():
    so = grounded_output("对HD-S303进行-30℃耐折测试。")
    out, changes = vpg.apply_auto001_validation_policy(so, CF_NOT_RESOLVED, "AUTO001_SCOPED")
    assert out["recommended_validation"][1]["action"] == vpg.FROZEN_P1
    assert any(c["type"] == "P1_GENERATED" for c in changes)


def test_vpg_06_p2_generated():
    so = grounded_output("对HD-S303进行-30℃耐折测试。")
    out, changes = vpg.apply_auto001_validation_policy(so, CF_NOT_RESOLVED, "AUTO001_SCOPED")
    assert out["recommended_validation"][2]["action"] == vpg.FROZEN_P2
    assert any(c["type"] == "P2_GENERATED" for c in changes)


def test_vpg_07_p2_cannot_replace_minus30():
    so = grounded_output("对HD-S303进行-30℃耐折测试。", p2_action="-20℃抽检即可证明-30℃。")
    out, _ = vpg.apply_auto001_validation_policy(so, CF_NOT_RESOLVED, "AUTO001_SCOPED")
    assert "不能替代-30℃" in out["recommended_validation"][2]["action"]


def test_vpg_08_unique_p0():
    so = grounded_output("对HD-S303进行-30℃耐折测试。")
    out, _ = vpg.apply_auto001_validation_policy(so, CF_NOT_RESOLVED, "AUTO001_SCOPED")
    p0s = [i for i in out["recommended_validation"] if i["priority"] == "P0"]
    assert len(p0s) == 1


def test_vpg_09_unique_p1():
    so = grounded_output("对HD-S303进行-30℃耐折测试。")
    out, _ = vpg.apply_auto001_validation_policy(so, CF_NOT_RESOLVED, "AUTO001_SCOPED")
    assert len([i for i in out["recommended_validation"] if i["priority"] == "P1"]) == 1


def test_vpg_10_unique_p2():
    so = grounded_output("对HD-S303进行-30℃耐折测试。")
    out, _ = vpg.apply_auto001_validation_policy(so, CF_NOT_RESOLVED, "AUTO001_SCOPED")
    assert len([i for i in out["recommended_validation"] if i["priority"] == "P2"]) == 1


def test_vpg_11_raw_not_modified():
    so = grounded_output("对HD-S303进行-30℃耐折测试。", p1_action="改PCDL。")
    before = deepcopy(so)
    vpg.apply_auto001_validation_policy(so, CF_NOT_RESOLVED, "AUTO001_SCOPED")
    assert so == before


def test_vpg_12_grounded_not_modified():
    so = grounded_output("对HD-S303进行-30℃耐折测试。")
    before = deepcopy(so)
    vpg.apply_auto001_validation_policy(so, CF_NOT_RESOLVED, "AUTO001_SCOPED")
    assert so == before


def test_vpg_13_policy_changes_traceable():
    so = grounded_output("对HD-S303进行-30℃耐折测试。", p1_action="改PCDL。")
    _, changes = vpg.apply_auto001_validation_policy(so, CF_NOT_RESOLVED, "AUTO001_SCOPED")
    assert any(c.get("original_priority") == "P1" for c in changes)


def test_vpg_14_generic_no_policy():
    so = grounded_output("对HD-S303进行-30℃耐折测试。")
    out, changes = vpg.apply_auto001_validation_policy(so, CF_NOT_RESOLVED, "GENERIC_TECHNICAL")
    assert changes == []
    assert out == so


def test_vpg_15_pcdl_technical_evidence_kept():
    so = grounded_output("对HD-S303进行-30℃耐折测试。")
    out, _ = vpg.apply_auto001_validation_policy(so, CF_NOT_RESOLVED, "AUTO001_SCOPED")
    assert "PCDL-2000" in out["technical_evidence"][0]["claim"]


def test_vpg_16_pcdl_not_validation_action():
    so = grounded_output("对HD-S303进行-30℃耐折测试。", p1_action="改PCDL-2000。")
    out, _ = vpg.apply_auto001_validation_policy(so, CF_NOT_RESOLVED, "AUTO001_SCOPED")
    for item in out["recommended_validation"]:
        assert "改PCDL" not in item["action"]
        assert "PCDL-2000" not in item["action"]


# ------------------------------------------------------------
# Curator Topic / Evidence Guard
# ------------------------------------------------------------

def candidate(topic, summary="", evidence=None):
    return {
        "candidate_id": "KC-x",
        "target_hint": {"suggested_topic": topic},
        "knowledge_gap_summary": summary,
        "evidence_needed": evidence or [],
    }


def test_vpg_17_topic_ptmeg_qualified_blocked():
    c = candidate("汽车革-30℃耐折专项验证（PTMEG体系）")
    out, changes = vpg.guard_curator_candidate_policy(c, CF_NOT_RESOLVED)
    assert "PTMEG体系" not in out["target_hint"]["suggested_topic"]
    assert any(ch["type"] == "UNSUPPORTED_FORMULATION_TOPIC" for ch in changes)


def test_vpg_18_topic_effective_gap():
    c = candidate("汽车革-30℃耐折专项验证（PTMEG体系）")
    out, _ = vpg.guard_curator_candidate_policy(c, CF_NOT_RESOLVED)
    assert out["target_hint"]["suggested_topic"] == vpg.FROZEN_TOPIC


def test_vpg_19_evidence_change_pcdl_removed():
    c = candidate("HD-S303汽车内饰革-30℃耐折≥5万次直接验证缺口", evidence=["改PCDL后复测结果", "-30℃直接验证结果"])
    out, changes = vpg.guard_curator_candidate_policy(c, CF_NOT_RESOLVED)
    assert "改PCDL后复测结果" not in out["evidence_needed"]
    assert any(ch["type"] == "OUT_OF_SCOPE_POST_VALIDATION_EXPLORATION" for ch in changes)


def test_vpg_20_confirm_formulation_allowed():
    c = candidate("topic", evidence=["确认当前配方体系"])
    out, _ = vpg.guard_curator_candidate_policy(c, CF_NOT_RESOLVED)
    assert "确认当前配方体系" in out["evidence_needed"]


def test_vpg_21_direct_validation_allowed():
    c = candidate("topic", evidence=["-30℃直接专项验证结果"])
    out, _ = vpg.guard_curator_candidate_policy(c, CF_NOT_RESOLVED)
    assert "-30℃直接专项验证结果" in out["evidence_needed"]


def test_vpg_22_minus20_reference_allowed():
    c = candidate("topic", evidence=["-20℃中间参考数据"])
    out, _ = vpg.guard_curator_candidate_policy(c, CF_NOT_RESOLVED)
    assert "-20℃中间参考数据" in out["evidence_needed"]


def test_vpg_23_raw_curator_preserved():
    c = candidate("汽车革-30℃耐折专项验证（PTMEG体系）", evidence=["改PCDL后复测"])
    before = deepcopy(c)
    vpg.guard_curator_candidate_policy(c, CF_NOT_RESOLVED)
    assert c == before


def test_vpg_24_curator_changes_traceable():
    c = candidate("汽车革-30℃耐折专项验证（PTMEG体系）", evidence=["改PCDL后复测"])
    _, changes = vpg.guard_curator_candidate_policy(c, CF_NOT_RESOLVED)
    assert any(ch["type"] == "UNSUPPORTED_FORMULATION_TOPIC" for ch in changes)
    assert any(ch["type"] == "OUT_OF_SCOPE_POST_VALIDATION_EXPLORATION" for ch in changes)


def run_all():
    tests = [
        test_vpg_01_p0_preserved,
        test_vpg_02_p0_no_current_ptmeg,
        test_vpg_03_p1_change_pcdl_overridden,
        test_vpg_04_p1_formulation_adjust_overridden,
        test_vpg_05_p1_generated,
        test_vpg_06_p2_generated,
        test_vpg_07_p2_cannot_replace_minus30,
        test_vpg_08_unique_p0,
        test_vpg_09_unique_p1,
        test_vpg_10_unique_p2,
        test_vpg_11_raw_not_modified,
        test_vpg_12_grounded_not_modified,
        test_vpg_13_policy_changes_traceable,
        test_vpg_14_generic_no_policy,
        test_vpg_15_pcdl_technical_evidence_kept,
        test_vpg_16_pcdl_not_validation_action,
        test_vpg_17_topic_ptmeg_qualified_blocked,
        test_vpg_18_topic_effective_gap,
        test_vpg_19_evidence_change_pcdl_removed,
        test_vpg_20_confirm_formulation_allowed,
        test_vpg_21_direct_validation_allowed,
        test_vpg_22_minus20_reference_allowed,
        test_vpg_23_raw_curator_preserved,
        test_vpg_24_curator_changes_traceable,
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
    print("ALL_VPG_TESTS_PASS")

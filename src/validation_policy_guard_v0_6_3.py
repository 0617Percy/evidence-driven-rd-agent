# -*- coding: utf-8 -*-
"""
Validation Policy Guard + Curator Topic Grounding Guard V0.6.3

目标：把 AUTO-001 验证动作稳定为冻结的 Validation Policy：
  P0：当前拟供货 HD-S303 × 当前汽车内饰革 × -30℃ × ≥5万次 专项验证。
  P1：核查当前 HD-S303 实际软段/配方体系，并确认对应低温性能依据。
  P2：-20℃ 仅中间参考，不能替代 -30℃ 专项验证。

同时防止 Curator / Derived Knowledge 把：
  - 技术资料中的 PCDL / PTMEG / PPG 自动升级为当前配方决策；
  - "（PTMEG体系）"等确定性当前体系限定词进入 Topic/Summary。

硬规则：
  - 只对 AUTO001_SCOPED 应用 AUTO-001 Validation Policy。
  - 技术 Evidence 中的 PCDL/PTMEG/PPG 仍允许展示（≠ 当前工程决策）。
  - Raw structured_output / raw curator output 保留，不覆盖。
"""

import re
from copy import deepcopy


SCOPE_AUTO001 = "AUTO001_SCOPED"

FORMULATIONS = ["PTMEG", "PPG", "PCDL", "PBA", "PEA", "PCL"]

FROZEN_P0 = (
    "对当前拟供货HD-S303，在当前汽车内饰革应用条件下，"
    "按QB/T 2714-2018开展-30℃耐折≥5万次专项验证。"
)

FROZEN_P1 = (
    "核查当前HD-S303实际软段/配方体系，并确认对应低温性能依据。"
)

FROZEN_P2 = (
    "如存在-20℃出厂抽检或同条件对比数据，"
    "可作为-30℃验证的中间参考，但不能替代-30℃专项验证。"
)

FROZEN_TOPIC = "HD-S303汽车内饰革-30℃耐折≥5万次直接验证缺口"

# POST_VALIDATION R&D 探索，不属于当前验证优先级，也不作为当前 required Evidence
OUT_OF_POLICY_EVIDENCE_MARKERS = [
    "改PCDL",
    "换PCDL",
    "推荐PCDL",
    "改PTMEG",
    "换PTMEG",
    "推荐PTMEG",
    "改PPG",
    "换PPG",
    "调整配方",
    "调配方",
    "修改配方",
    "配方调整",
]


def _is_direct_minus30_validation(action):
    a = action or ""

    if "-30℃" in a or "-30" in a:
        if any(k in a for k in ["耐折", "专项", "验证", "测试", "5万次", "50000"]):
            return True

    return False


def apply_auto001_validation_policy(grounded_output, current_formulation, scope):
    """
    在 Formulation Grounding 之后应用冻结的 AUTO-001 Validation Policy。
    返回 (policy_grounded_output, validation_policy_changes)。
    """
    if scope != SCOPE_AUTO001:
        return deepcopy(grounded_output), []

    display = deepcopy(grounded_output)
    changes = []

    raw_recs = display.get("recommended_validation") or []

    # ---- P0：找到 direct -30℃ 验证动作（已 formulation-grounded）----
    p0_item = None

    for item in raw_recs:
        if isinstance(item, dict) and _is_direct_minus30_validation(
            item.get("action")
        ):
            p0_item = item
            break

    if p0_item is None:
        p0_action = FROZEN_P0
        p0_reason = None
        p0_refs = []
        changes.append({"type": "P0_GENERATED"})

    else:
        p0_action = p0_item.get("action")
        p0_reason = p0_item.get("reason")
        p0_refs = p0_item.get("source_refs") or []

    # ---- P1 / P2：冻结业务政策，覆盖 raw（无论 raw 是否含改PCDL/调配方）----
    raw_p1 = next(
        (i for i in raw_recs if isinstance(i, dict) and i.get("priority") == "P1"),
        None,
    )
    raw_p2 = next(
        (i for i in raw_recs if isinstance(i, dict) and i.get("priority") == "P2"),
        None,
    )

    if raw_p1 is None:
        changes.append({"type": "P1_GENERATED"})

    elif (raw_p1.get("action") or "").strip() != FROZEN_P1:
        changes.append({
            "type": "OUT_OF_POLICY_VALIDATION_ACTION",
            "original_priority": "P1",
            "original_action": raw_p1.get("action"),
            "effective_priority": "P1",
            "effective_action": FROZEN_P1,
        })

    if raw_p2 is None:
        changes.append({"type": "P2_GENERATED"})

    elif (raw_p2.get("action") or "").strip() != FROZEN_P2:
        changes.append({
            "type": "OUT_OF_POLICY_VALIDATION_ACTION",
            "original_priority": "P2",
            "original_action": raw_p2.get("action"),
            "effective_priority": "P2",
            "effective_action": FROZEN_P2,
        })

    display["recommended_validation"] = [
        {
            "priority": "P0",
            "action": p0_action,
            "reason": p0_reason,
            "source_refs": p0_refs,
        },
        {
            "priority": "P1",
            "action": FROZEN_P1,
            "reason": None,
            "source_refs": [],
        },
        {
            "priority": "P2",
            "action": FROZEN_P2,
            "reason": None,
            "source_refs": [],
        },
    ]

    return display, changes


def _has_formulation_qualifier(text):
    for f in FORMULATIONS:
        if re.search(r"[（(]\s*" + f + r"体系\s*[)）]", str(text or "")):
            return True

        if (f + "体系") in str(text or ""):
            return True

    return False


def _sanitize_topic(topic, current_formulation):
    if current_formulation and current_formulation.get("status") == "RESOLVED":
        return topic

    if _has_formulation_qualifier(topic):
        return FROZEN_TOPIC

    return topic


def _sanitize_summary(summary, current_formulation):
    if current_formulation and current_formulation.get("status") == "RESOLVED":
        return summary

    s = str(summary or "")

    for f in FORMULATIONS:
        s = re.sub(r"[（(]\s*" + f + r"体系\s*[)）]", "", s)

    return s.strip()


def guard_curator_candidate_policy(candidate, current_formulation):
    """
    Curator Candidate 的 Topic / Summary / Evidence Need 政策 Guard。
    返回 (policy_guarded_candidate, curator_policy_changes)。
    """
    if not isinstance(candidate, dict):
        return candidate, []

    display = deepcopy(candidate)
    changes = []

    # ---- Topic guard ----
    target_hint = display.get("target_hint") or {}

    if target_hint.get("suggested_topic"):
        new_topic = _sanitize_topic(
            target_hint["suggested_topic"],
            current_formulation,
        )

        if new_topic != target_hint["suggested_topic"]:
            changes.append({
                "type": "UNSUPPORTED_FORMULATION_TOPIC",
                "original": target_hint["suggested_topic"],
                "effective": new_topic,
            })

            target_hint["suggested_topic"] = new_topic
            display["target_hint"] = target_hint

    # ---- Summary guard ----
    if display.get("knowledge_gap_summary"):
        new_summary = _sanitize_summary(
            display["knowledge_gap_summary"],
            current_formulation,
        )

        if new_summary != display["knowledge_gap_summary"]:
            changes.append({
                "type": "UNSUPPORTED_FORMULATION_SUMMARY",
                "original": display["knowledge_gap_summary"],
                "effective": new_summary,
            })

            display["knowledge_gap_summary"] = new_summary

    # ---- Evidence Need guard ----
    evidence = display.get("evidence_needed") or []
    guarded_evidence = []
    removed_evidence = []

    for item in evidence:
        s = str(item)

        if any(m in s for m in OUT_OF_POLICY_EVIDENCE_MARKERS):
            removed_evidence.append(item)

        else:
            guarded_evidence.append(item)

    if removed_evidence:
        display["evidence_needed"] = guarded_evidence
        changes.append({
            "type": "OUT_OF_SCOPE_POST_VALIDATION_EXPLORATION",
            "removed": removed_evidence,
        })

    return display, changes

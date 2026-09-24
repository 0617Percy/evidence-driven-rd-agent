# -*- coding: utf-8 -*-
"""
Context Scope Guard + Current Formulation Grounding Guard V0.6.1

解决问题：
  A. AUTO-001 Context Leakage：Generic 技术咨询不应强制展示 AUTO-001 场景。
  B. Historical → Current Formulation 外推：历史 PPG→PTMEG 纠正 ≠ 当前 PTMEG。

职责（确定性，无 LLM / 无第二次 Retriever）：
  - resolve_context_scope(query, evidence, product_resolution)
  - resolve_current_formulation(evidence, product)
  - apply_grounding_guard(structured_output, current_formulation)
  - sanitize_curator_text(text, current_formulation)

事实边界：
  历史配方 / 历史纠正动作 绝不自动升级为 当前配方。
"""

import re
from copy import deepcopy


# ---- Scope ----
SCOPE_AUTO001 = "AUTO001_SCOPED"
SCOPE_GENERIC = "GENERIC_TECHNICAL"
SCOPE_AMBIGUOUS = "AMBIGUOUS"
SCOPE_NOT_SCOPED = "NOT_SCOPED"


# ---- Formulation ----
FORMULATIONS = ["PTMEG", "PPG", "PCDL", "PBA", "PEA", "PCL"]

CURRENT_FORMULATION_MARKERS = [
    "当前采用",
    "当前配方",
    "当前体系",
    "现用配方",
    "现用",
    "当前拟供货",
    "拟供货批次采用",
    "当前项目采用",
    "当前面层采用",
    "当前HD-S303采用",
    "当前HD-S303体系",
    "现用HD-S303",
]

GENERIC_MARKERS = [
    "一般",
    "特点",
    "区别",
    "原理",
    "定义",
    "主要测",
    "是什么",
    "机理",
    "通用",
    "比较",
    "有什么特点",
]

# ---- Conversation Scene Context（V0.6.4）----

# 自然中文指代/当前任务信号（仅辅助 Scope，不是 Evidence）
DEICTIC_MARKERS = [
    "这次",
    "当前这次",
    "现在这个",
    "这个产品",
    "这个项目",
    "这个情况",
]

# 自然 Follow-up 语言（有上一轮 scene 时用于判断是否承接）
FOLLOW_UP_MARKERS = [
    "那",
    "那么",
    "所以",
    "是不是",
    "到底",
    "这个",
    "这次",
    "现在",
    "直接告诉我",
    "不要解释",
    "为什么",
    "那是不是",
    "那现在",
]

# AUTO-001 上下文信号（温度/耐折/达标等，属同一研发场景）
AUTO001_CONTEXT_SIGNALS = [
    "-10℃",
    "-20℃",
    "-30℃",
    "-30",
    "耐折",
    "5万次",
    "50000",
    "达标",
    "通过",
    "不通过",
    "低温性能",
    "低温",
]

# 明确切换到其它产品/层级的信号（不得继承 HD-S303 scene）
OTHER_PRODUCT_SIGNALS = [
    "HD-S302",
    "HD-S301",
    "HD-S304",
    "HD-W107",
    "粘接层",
]


def explicit_scope_signals(query):
    """当前 Query 的显式 Scope 信号（供审计/调试，也供 resolve_context_scope 复用）。"""
    q = (query or "").strip()

    return {
        "has_application": any(s in q for s in ["汽车内饰革", "汽车革", "仪表板"]),
        "has_metric": any(s in q for s in ["耐折", "5万次", "50000"]),
        "has_temperature": any(s in q for s in ["-30℃", "-30"]),
        "has_product": any(
            s in q
            for s in ["HD-S303", "HD S303", "HD\u2013S303", "HD\uff0dS303", "HD-S302", "HD-W107"]
        ),
        "has_current": any(
            s in q
            for s in [
                "当前",
                "现在",
                "拟供货",
                "这个客户",
                "这个项目",
            ] + DEICTIC_MARKERS
        ),
    }


def resolve_context_scope(query, evidence=None, product_resolution=None):
    """
    判断 Query 是否属于 AUTO-001 具体研发风险预审场景。
    Scope 判断可用 Query（Intent Evidence），但产品不因 Query 出现型号而 RESOLVED。
    """
    q = (query or "").strip()

    sig = explicit_scope_signals(q)

    has_app = sig["has_application"]
    has_metric = sig["has_metric"]
    has_temp = sig["has_temperature"]
    has_product = sig["has_product"]
    has_current = sig["has_current"]

    # AUTO001_SCOPED：明确当前任务 scope
    if has_app and has_temp and (has_metric or has_current or has_product):
        return SCOPE_AUTO001

    if has_current and has_temp and (has_app or has_product):
        return SCOPE_AUTO001

    # GENERIC_TECHNICAL：纯技术咨询，无 AUTO-001 任务信号
    if any(m in q for m in GENERIC_MARKERS) and not (has_app and has_metric):
        return SCOPE_GENERIC

    # NOT_SCOPED：完全无关
    if not (has_app or has_metric or has_temp or has_product or has_current):
        return SCOPE_NOT_SCOPED

    # AMBIGUOUS：部分信号但不完整
    return SCOPE_AMBIGUOUS


def _explicit_other_product(query):
    """Query 明确命名了 HD-S303 之外的其它产品/层级，不得继承 HD-S303 scene。"""
    q = (query or "")

    if "HD-S303" in q:
        return False

    return any(s in q for s in OTHER_PRODUCT_SIGNALS)


def _is_follow_up(query, previous_scene_context):
    """判断当前 Query 是否为上一轮 AUTO001 scene 的自然 follow-up。"""
    q = (query or "").strip()

    if not previous_scene_context:
        return False

    if previous_scene_context.get("scope") != SCOPE_AUTO001:
        return False

    if _explicit_other_product(q):
        return False

    if any(m in q for m in FOLLOW_UP_MARKERS):
        return True

    if any(s in q for s in AUTO001_CONTEXT_SIGNALS):
        return True

    return False


def resolve_conversation_scope(
    query,
    evidence=None,
    product_resolution=None,
    previous_scene_context=None,
):
    """
    Conversation-aware scope resolution（V0.6.4）。

    在 single-turn resolve_context_scope 基础上，仅在上一轮已确认
    AUTO001 scene 且当前 Query 为自然 follow-up 时，承接 AUTO001 scene。

    安全规则：
      - Scene Context 只用于 Scope，绝不是 Evidence。
      - Generic / 明确其它产品 / 无关问题 可正常打断继承。

    返回 dict：
      scope / scope_resolution_basis / scene_inheritance_used / inherited_scene_context
    """
    base_scope = resolve_context_scope(
        query,
        evidence,
        product_resolution,
    )

    # 明确 scope（AUTO001 / GENERIC）优先，不进入继承
    if base_scope in (SCOPE_AUTO001, SCOPE_GENERIC):
        return {
            "scope": base_scope,
            "scope_resolution_basis": "explicit_query_scope",
            "scene_inheritance_used": False,
            "inherited_scene_context": None,
        }

    # NOT_SCOPED / AMBIGUOUS：允许 scene 继承（仅 follow-up）
    if _is_follow_up(query, previous_scene_context):
        return {
            "scope": SCOPE_AUTO001,
            "scope_resolution_basis": "conversation_scene_inheritance",
            "scene_inheritance_used": True,
            "inherited_scene_context": previous_scene_context,
        }

    return {
        "scope": base_scope,
        "scope_resolution_basis": "single_turn_scope",
        "scene_inheritance_used": False,
        "inherited_scene_context": None,
    }


def resolve_current_formulation(evidence, product=None):
    """
    只从 retrieved evidence 解析"当前配方/软段体系"。
    历史案例的 PPG→PTMEG 纠正只记为 historical_events，不构成 current。
    """
    current_support = {}
    historical_events = []

    for item in evidence or []:
        if not isinstance(item, dict):
            continue

        chunk_id = item.get("chunk_id")
        source = str(item.get("source") or "")
        text = str(item.get("text") or "") + " " + str(item.get("title") or "")

        formulations = sorted(
            [f for f in FORMULATIONS if f in text],
            key=lambda f: text.find(f),
        )

        if not formulations:
            continue

        is_case = "08_问题案例" in source or "cases" in source

        # 历史纠正动作：PPG -> PTMEG（顺序按出现先后）
        if is_case and ("纠正" in text or "更换" in text or "换" in text):
            if len(formulations) >= 2:
                historical_events.append({
                    "from": formulations[0],
                    "to": formulations[1],
                    "type": "HISTORICAL_CORRECTIVE_ACTION",
                    "ref": chunk_id or source,
                })

        # 当前配方声明
        if any(m in text for m in CURRENT_FORMULATION_MARKERS):
            for f in formulations:
                current_support.setdefault(f, set()).add(chunk_id or source)

    if len(current_support) >= 2:
        return {
            "status": "AMBIGUOUS",
            "value": None,
            "supporting_refs": [],
            "historical_events": historical_events,
        }

    if len(current_support) == 1:
        f = list(current_support.keys())[0]
        return {
            "status": "RESOLVED",
            "value": f,
            "supporting_refs": sorted(current_support[f]),
            "historical_events": historical_events,
        }

    return {
        "status": "NOT_RESOLVED",
        "value": None,
        "supporting_refs": [],
        "historical_events": historical_events,
    }


# ---- Grounding Guard ----

REPLACEMENT = "当前软段/配方体系（未明确）"

_UNSUPPORTED_PHRASES = []

for _f in FORMULATIONS:
    for _p in ["当前", "现用"]:
        _UNSUPPORTED_PHRASES.append(_p + _f + "体系")
        _UNSUPPORTED_PHRASES.append(_p + _f)

_UNSUPPORTED_PHRASES = sorted(set(_UNSUPPORTED_PHRASES), key=len, reverse=True)

_UNCERTAIN_PREFIXES = ["是否为", "是否", "尚未明确", "未明确", "不确定", "待核查", "核查"]


def _sanitize_text(text):
    if not text:
        return text, []

    result = str(text)
    changes = []

    for phrase in _UNSUPPORTED_PHRASES:
        while phrase in result:
            idx = result.find(phrase)
            prefix = result[max(0, idx - 10):idx]

            if any(u in prefix for u in _UNCERTAIN_PREFIXES):
                break

            result = result[:idx] + REPLACEMENT + result[idx + len(phrase):]
            changes.append({
                "original": phrase,
                "effective": REPLACEMENT,
            })

    return result, changes


def apply_grounding_guard(structured_output, current_formulation):
    """
    Grounding Guard：当 current formulation 未 RESOLVED 时，
    拦截"当前PTMEG/PPG/PCDL"等不支持的当前状态断言。
    返回 (effective_grounded_output, grounding_changes)。
    不修改原始 structured_output。
    """
    if current_formulation and current_formulation.get("status") == "RESOLVED":
        return deepcopy(structured_output), []

    display = deepcopy(structured_output)
    changes = []

    if display.get("risk_summary"):
        new_text, ch = _sanitize_text(display["risk_summary"])

        if ch:
            display["risk_summary"] = new_text

            for c in ch:
                changes.append({
                    "type": "UNSUPPORTED_CURRENT_FORMULATION",
                    "field": "risk_summary",
                    **c,
                })

    for item in display.get("condition_gap") or []:
        if isinstance(item, dict) and item.get("current"):
            new_text, ch = _sanitize_text(item["current"])

            if ch:
                item["current"] = new_text

                for c in ch:
                    changes.append({
                        "type": "UNSUPPORTED_CURRENT_FORMULATION",
                        "field": "condition_gap.current",
                        **c,
                    })

    for item in display.get("recommended_validation") or []:
        if isinstance(item, dict):
            for field in ["action", "reason"]:
                if item.get(field):
                    new_text, ch = _sanitize_text(item[field])

                    if ch:
                        item[field] = new_text

                        for c in ch:
                            changes.append({
                                "type": "UNSUPPORTED_CURRENT_FORMULATION",
                                "field": "recommended_validation." + field,
                                **c,
                            })

    return display, changes


def sanitize_curator_text(text, current_formulation):
    """Curator 文本 grounding：拦截不支持的当前配方断言。"""
    if current_formulation and current_formulation.get("status") == "RESOLVED":
        return text

    new_text, _ = _sanitize_text(text)

    return new_text

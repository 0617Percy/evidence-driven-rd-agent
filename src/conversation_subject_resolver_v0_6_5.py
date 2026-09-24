# -*- coding: utf-8 -*-
"""
Conversation Subject Resolution V0.6.5

职责：区分两个独立对象
  A. Evidence Product Resolution —— "当前 Retrieved Evidence 是否足以独立证明主体产品？"
     （继续由 context_entity_resolver_v0_6 / product_role_guard_v0_6_2 负责，Evidence-only）
  B. Conversation Subject Resolution —— "用户当前这一轮正在讨论哪个产品？"
     （本模块负责，只做会话主题识别，绝不作企业 Evidence）

来源优先级（Conversation Subject）：
  1. 当前 Query 明确出现产品型号（HD-S303 等，规范化抽取）
  2. 当前 Query 无产品，但 previous active_scene_context 已 CONFIRMED 产品
  3. Query 与 previous scene 冲突 → 以当前 Query 明确语义为准，不继承
  4. Query 无产品 + previous 无产品 → 才 fallback 到 evidence product（若 RESOLVED）

安全规则（永久）：
  - QUERY_IS_NOT_PRODUCT_EVIDENCE = YES
  - SESSION_CONTEXT_IS_NOT_PRODUCT_EVIDENCE = YES
  - Conversation Subject 只用于 UI 展示 / 场景标签，绝不进入 supporting_refs /
    Evidence Level / Evidence Chain / Current Formulation / Product Evidence Resolution。
"""

from context_entity_resolver_v0_6 import (
    _extract_products,
    _normalize_product,
)


SCOPE_AUTO001 = "AUTO001_SCOPED"
SCOPE_GENERIC = "GENERIC_TECHNICAL"

CONFIDENCE_CONFIRMED = "CONFIRMED"


def extract_query_products(query):
    """从 Query 规范化抽取产品型号（用于 Conversation Subject，不是 Evidence）。"""
    return _extract_products(query)


def _subject(status, value, basis, query_product, previous_product, evidence_status):
    return {
        "product": {
            "status": status,
            "value": value,
            "basis": basis,
            "query_product": query_product,
            "previous_scene_product": previous_product,
            "evidence_product_status": evidence_status,
        }
    }


def resolve_conversation_subject(
    query,
    scope=None,
    previous_scene_context=None,
    evidence_product_status=None,
    evidence_product_value=None,
):
    """
    解析"用户当前这一轮正在讨论哪个产品"。

    返回 {"product": {status, value, basis, query_product,
                     previous_scene_product, evidence_product_status}}。
    """
    q = (query or "").strip()

    query_products = extract_query_products(q)
    query_product = query_products[0] if query_products else None

    previous_product = (
        previous_scene_context.get("product")
        if (
            isinstance(previous_scene_context, dict)
            and previous_scene_context.get("confidence") == CONFIDENCE_CONFIRMED
            and previous_scene_context.get("product")
        )
        else None
    )

    # Generic 通用技术咨询：无产品主题，不得继承 AUTO001 scene product
    if scope == SCOPE_GENERIC:
        return _subject(
            "NOT_RESOLVED",
            None,
            "generic_no_product_subject",
            query_product,
            previous_product,
            evidence_product_status,
        )

    # 优先级1：当前 Query 明确产品
    if query_product:
        basis = "explicit_query_product"

        if previous_product and previous_product == query_product:
            basis = "explicit_query_product_confirmed_by_scene"

        return _subject(
            "RESOLVED",
            query_product,
            basis,
            query_product,
            previous_product,
            evidence_product_status,
        )

    # 优先级2：Query 无产品，但 previous scene 已 CONFIRMED
    if previous_product:
        return _subject(
            "RESOLVED",
            previous_product,
            "conversation_scene_inheritance",
            None,
            previous_product,
            evidence_product_status,
        )

    # 优先级4：Query 无产品 + previous 无产品 → evidence fallback（仅 RESOLVED）
    if evidence_product_status == "RESOLVED" and evidence_product_value:
        return _subject(
            "RESOLVED",
            evidence_product_value,
            "evidence_fallback",
            None,
            None,
            evidence_product_status,
        )

    return _subject(
        "NOT_RESOLVED",
        None,
        "no_signal",
        None,
        previous_product,
        evidence_product_status,
    )


def build_next_scene_context(
    previous_scene_context,
    conversation_subject,
    scope,
    application="汽车内饰革",
    metric="-30℃耐折≥5万次",
):
    """
    计算下一轮 active_scene_context（ephemeral，只用于 Scope，不是 Evidence）。

    规则：
      - 非 AUTO001 轮：不建立/覆盖 AUTO001 scene，返回 previous（保持不变）。
      - AUTO001 轮：product 取 conversation subject（RESOLVED）；
        若 subject 未 RESOLVED，则保留 previous CONFIRMED product（不得用 None 覆盖）。
    """
    if scope != SCOPE_AUTO001:
        return previous_scene_context

    product = None

    if isinstance(conversation_subject, dict):
        product = (conversation_subject.get("product") or {}).get("value")

    if not product:
        if (
            isinstance(previous_scene_context, dict)
            and previous_scene_context.get("confidence") == CONFIDENCE_CONFIRMED
        ):
            product = previous_scene_context.get("product")

    return {
        "scope": SCOPE_AUTO001,
        "product": product,
        "application": application,
        "metric": metric,
        "source_turn_id": None,
        "confidence": (
            CONFIDENCE_CONFIRMED if product else "UNRESOLVED_PRODUCT"
        ),
    }


def build_subject_audit(conversation_subject, context_resolution, effective_resolution):
    """组装 Developer Audit 所需字段（只读展示，不修改任何对象）。"""
    product = (conversation_subject or {}).get("product") or {}

    raw_product = (context_resolution or {}).get("product") or {}
    eff = effective_resolution or {}

    return {
        "conversation_subject_product": product.get("value"),
        "conversation_subject_status": product.get("status"),
        "conversation_subject_basis": product.get("basis"),
        "query_explicit_product": product.get("query_product"),
        "previous_scene_product": product.get("previous_scene_product"),
        "evidence_product_status": eff.get("status"),
        "evidence_product_candidates": raw_product.get("candidate_products") or [],
    }

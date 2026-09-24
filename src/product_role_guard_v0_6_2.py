# -*- coding: utf-8 -*-
"""
Product Role & Scope Coherence Guard V0.6.2

第二阶段消歧：在 Raw Product Resolver（V0.6）返回 AMBIGUOUS 时，
根据 retrieved evidence 中各产品出现的"业务角色"做确定性消歧。

角色：
  PRIMARY_SUBJECT     当前需求/问题/研发项目的主体产品
  SECONDARY_COMPONENT 同一方案中的配套/粘接层/底涂/辅助产品
  COMPARATOR          成本/性能/旧型号比较对象
  GENERIC_REFERENCE   技术文献/标准/综述中偶然出现的型号

硬规则：
  - 只从 retrieved evidence 判定角色；不使用 Query / LLM Structured Output。
  - 仅 AUTO001_SCOPED 才做 scope-aware 角色消歧。
  - 不改变 Evidence Level / Safety / P0 业务定义。
"""

import re


# ---- 角色 ----
PRIMARY_SUBJECT = "PRIMARY_SUBJECT"
SECONDARY_COMPONENT = "SECONDARY_COMPONENT"
COMPARATOR = "COMPARATOR"
GENERIC_REFERENCE = "GENERIC_REFERENCE"
UNKNOWN_ROLE = "UNKNOWN_ROLE"


_SEPARATORS = r"[\-\u2013\u2014\uff0d]"

_PRODUCT_RE = re.compile(
    r"[A-Z]{2,6}(?:\s*" + _SEPARATORS + r"\s*|\s+)[A-Z][A-Z0-9]{0,7}"
)

_ROLE_PRIORITY = {
    PRIMARY_SUBJECT: 4,
    SECONDARY_COMPONENT: 3,
    COMPARATOR: 2,
    GENERIC_REFERENCE: 1,
    UNKNOWN_ROLE: 0,
}


def _normalize(raw):
    n = re.sub(r"\s*" + _SEPARATORS + r"\s*", "-", raw)
    n = re.sub(r"\s+", "-", n)
    return n


def _extract_products(text):
    if not text:
        return []

    found = []

    for m in _PRODUCT_RE.finditer(str(text)):
        n = _normalize(m.group(0))

        if n not in found:
            found.append(n)

    return found


def _classify_product_role(text, product, source):
    # PRIMARY_SUBJECT
    if any(
        m in text
        for m in [
            "涉及产品" + product,
            product + "面层",
            product + "批次",
            product + "完成",
            "当前产品" + product,
            "项目对象为" + product,
            "主体产品" + product,
        ]
    ):
        return PRIMARY_SUBJECT

    # COMPARATOR
    if any(
        m in text
        for m in [
            "成本较" + product,
            "较" + product,
            "相比" + product,
            "对照" + product,
            "基准产品" + product,
            "基准" + product,
        ]
    ):
        return COMPARATOR

    # SECONDARY_COMPONENT
    if any(
        m in text
        for m in ["粘接层", "底涂", "配套", "辅助层"]
    ):
        return SECONDARY_COMPONENT

    # GENERIC_REFERENCE（低上下文）
    if (
        "11_公开技术资料" in source
        or "10_行业标准" in source
        or "literature" in source
        or "standards" in source
    ):
        return GENERIC_REFERENCE

    # 高上下文默认主体
    return PRIMARY_SUBJECT


def classify_product_roles(evidence):
    """
    返回 {product: {"role": role, "supporting_refs": [refs]}}。
    同一 chunk 对同一产品最多贡献一次；同产品跨 chunk 取最高优先级角色。
    """
    roles = {}

    for item in evidence or []:
        if not isinstance(item, dict):
            continue

        chunk_id = item.get("chunk_id")
        source = str(item.get("source") or "")
        title = item.get("title") or ""
        text = item.get("text") or ""

        full = str(title) + " " + str(text)
        products = _extract_products(full)

        if not products:
            continue

        ref_key = chunk_id or source or "unknown_ref"

        for p in products:
            role = _classify_product_role(full, p, source)

            if p not in roles:
                roles[p] = {"role": role, "refs": set()}

            if _ROLE_PRIORITY[role] > _ROLE_PRIORITY[roles[p]["role"]]:
                roles[p]["role"] = role

            roles[p]["refs"].add(ref_key)

    return {
        p: {
            "role": info["role"],
            "supporting_refs": sorted(info["refs"]),
        }
        for p, info in roles.items()
    }


def resolve_effective_product(evidence, scope, raw_resolution=None):
    """
    仅 AUTO001_SCOPED 做角色消歧；其它 scope 返回 None（保持 V0.6.1 逻辑）。
    """
    if scope != "AUTO001_SCOPED":
        return None

    roles = classify_product_roles(evidence)

    if not roles:
        return {
            "status": "NOT_RESOLVED",
            "value": None,
            "supporting_refs": [],
            "roles": {},
            "resolution_basis": "retrieved_evidence_role_disambiguation",
        }

    primaries = [
        p
        for p, info in roles.items()
        if info["role"] == PRIMARY_SUBJECT
    ]

    role_map = {p: info["role"] for p, info in roles.items()}

    if len(primaries) == 1:
        p = primaries[0]

        return {
            "status": "RESOLVED",
            "value": p,
            "supporting_refs": roles[p]["supporting_refs"],
            "roles": role_map,
            "resolution_basis": "retrieved_evidence_role_disambiguation",
        }

    if len(primaries) >= 2:
        return {
            "status": "AMBIGUOUS",
            "value": None,
            "supporting_refs": [],
            "roles": role_map,
            "resolution_basis": "retrieved_evidence_role_disambiguation",
        }

    return {
        "status": "NOT_RESOLVED",
        "value": None,
        "supporting_refs": [],
        "roles": role_map,
        "resolution_basis": "retrieved_evidence_role_disambiguation",
    }


def effective_product_display_value(effective_resolution):
    """由 effective_product_resolution 得到产品展示值。"""
    if not isinstance(effective_resolution, dict):
        return None

    status = effective_resolution.get("status")

    if status == "RESOLVED":
        return effective_resolution.get("value")

    if status == "AMBIGUOUS":
        return "未唯一确定"

    if status == "NOT_RESOLVED":
        return "未从当前证据中确定"

    return None

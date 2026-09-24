# -*- coding: utf-8 -*-
"""
Context Entity Resolution V0.6（Evidence-grounded Product Resolution）

本轮价值：即使 LLM requirement 摘要不写产品、用户 Query 不写产品，
系统仍能从本次实际检索到的知识证据（Retriever hits）识别当前所指产品。

硬规则：
  - 只从本次实际 retrieved evidence 解析产品，不重新检索。
  - 不从 Query 直接解析产品（query 只作为 Retriever 输入）。
  - 不从 LLM Answer 正文 / Curator output 解析产品。
  - 正则只用于 Knowledge Evidence 内容内部。
  - 不硬编码任何产品（如 HD-S303）。

Resolution 状态：
  RESOLVED      唯一产品候选 + 充分证据支持
  AMBIGUOUS     两个或以上有实质支持的产品候选
  NOT_RESOLVED  证据不足以确定产品
"""

import re


# 型号分隔符：hyphen / en dash / em dash / full-width hyphen
_SEPARATORS = r"[\-\u2013\u2014\uff0d]"

# 产品型号：两段式，后半段必须以字母开头（排除软段等级如 PCDL-2000 / PTMEG-2000）
_PRODUCT_RE = re.compile(
    r"[A-Z]{2,6}(?:\s*" + _SEPARATORS + r"\s*|\s+)[A-Z][A-Z0-9]{0,7}"
)

# Source Context Weight（轻量、确定性）
HIGH_CONTEXT_MARKERS = [
    "03_客户需求",
    "08_问题案例",
    "02_研发项目",
    "01_产品主数据",
    "04_实验记录",
    "05_性能测试数据",
    "06_批次生产记录",
]

MID_CONTEXT_MARKERS = [
    "07_工艺参数",
]


def _normalize_product(raw):
    normalized = re.sub(
        r"\s*" + _SEPARATORS + r"\s*",
        "-",
        raw,
    )

    normalized = re.sub(r"\s+", "-", normalized)

    return normalized


def _extract_products(text):
    if not text:
        return []

    found = []

    for match in _PRODUCT_RE.finditer(str(text)):
        norm = _normalize_product(match.group(0))

        if norm not in found:
            found.append(norm)

    return found


def _source_context_weight(source, doc_type):
    s = str(source or "") + " " + str(doc_type or "")

    for marker in HIGH_CONTEXT_MARKERS:
        if marker in s:
            return "HIGH"

    for marker in MID_CONTEXT_MARKERS:
        if marker in s:
            return "MID"

    return "LOW"


def _empty_result(status, value=None, refs=None, candidates=None):
    return {
        "product": {
            "status": status,
            "value": value,
            "supporting_refs": refs or [],
            "candidate_products": candidates or [],
            "resolution_basis": "retrieved_evidence",
        }
    }


def resolve_context_entities(evidence):
    """
    从 retrieved evidence 解析产品实体。

    evidence: list of dict，每个至少含 chunk_id/source/doc_type/title/text。
    不读取 query / LLM answer / curator output。
    """
    # product -> {"refs": set(), "has_high": bool}
    product_support = {}

    for item in evidence or []:
        if not isinstance(item, dict):
            continue

        chunk_id = item.get("chunk_id")
        source = item.get("source")
        doc_type = item.get("doc_type")
        title = item.get("title")
        text = item.get("text")

        found = set()

        for field in [title, text]:
            for p in _extract_products(field):
                found.add(p)

        if not found:
            continue

        weight = _source_context_weight(source, doc_type)
        ref_key = chunk_id or source or "unknown_ref"

        for p in found:
            if p not in product_support:
                product_support[p] = {
                    "refs": set(),
                    "has_high": False,
                }

            product_support[p]["refs"].add(ref_key)

            if weight == "HIGH":
                product_support[p]["has_high"] = True

    if not product_support:
        return _empty_result("NOT_RESOLVED")

    candidates = []

    for p, info in product_support.items():
        support_count = len(info["refs"])
        has_high = info["has_high"]

        # 实质支持：有高上下文证据 或 至少两个独立 ref
        substantial = has_high or support_count >= 2

        candidates.append({
            "product": p,
            "supporting_refs": sorted(info["refs"]),
            "support_count": support_count,
            "has_high_context": has_high,
            "substantial": substantial,
        })

    substantial = [c for c in candidates if c["substantial"]]

    if len(substantial) == 1:
        c = substantial[0]
        return _empty_result(
            "RESOLVED",
            value=c["product"],
            refs=c["supporting_refs"],
            candidates=[c["product"]],
        )

    if len(substantial) >= 2:
        return _empty_result(
            "AMBIGUOUS",
            candidates=[c["product"] for c in substantial],
        )

    # 0 个实质支持：仅有低上下文偶然提及 → NOT_RESOLVED
    return _empty_result("NOT_RESOLVED")


def product_display_value(context_resolution):
    """
    由 ContextEntityResolution 得到产品展示值。
    RESOLVED -> 产品值；AMBIGUOUS -> "未唯一确定"；NOT_RESOLVED -> "未从当前证据中确定"。
    """
    if not isinstance(context_resolution, dict):
        return None

    product = context_resolution.get("product") or {}

    status = product.get("status")

    if status == "RESOLVED":
        return product.get("value")

    if status == "AMBIGUOUS":
        return "未唯一确定"

    if status == "NOT_RESOLVED":
        return "未从当前证据中确定"

    return None

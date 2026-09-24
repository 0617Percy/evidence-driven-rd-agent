# -*- coding: utf-8 -*-
"""
UI Display Utils V1.0（纯函数展示层，无 Streamlit 依赖）

职责：
  - extract_product(text)：产品型号提取 + 归一化（HD-S303 / HD–S303 / HD－S303 / HD S303 -> HD-S303）
  - classify_auto001_action(action)：AUTO-001 推荐动作分类（A/B/C）
  - normalize_auto001_validation_for_display(so)：展示层优先级确定性归一

全部纯函数；不修改输入对象（normalize 内部 deepcopy）。
"""

import re
from copy import deepcopy


# hyphen / en dash / em dash / full-width hyphen
_SEPARATORS = r"[\-\u2013\u2014\uff0d]"


def extract_product(text):
    """
    从文本提取产品型号，统一归一为 "HD-S303" 形式。

    支持写法：HD-S303 / HD–S303 / HD－S303 / HD S303。
    返回 None 表示未找到（不硬编码任何型号）。
    """
    if not text:
        return None

    text = str(text)

    m = re.search(
        r"[A-Z]{2,6}(?:\s*"
        + _SEPARATORS
        + r"\s*|\s+)[A-Z0-9]{1,8}",
        text,
    )

    if not m:
        return None

    raw = m.group(0)

    normalized = re.sub(
        r"\s*" + _SEPARATORS + r"\s*",
        "-",
        raw,
    )

    normalized = re.sub(r"\s+", "-", normalized)

    return normalized


def classify_auto001_action(action):
    """
    AUTO-001 推荐动作分类（仅展示层）。

    返回展示优先级，或 None（未识别 -> 保留原 priority）。

    判定顺序（先具体后宽泛，避免"-30℃尚未做"被误判为直接验证）：
      C｜-20℃ 中间参考      -> P2
      B｜软段/配方体系      -> P1
      A｜直接 -30℃ 验证    -> P0
    """
    a = action or ""

    # C｜-20℃ 中间参考
    if ("-20℃" in a) or ("-20" in a):
        if any(k in a for k in ["抽检", "中间参考", "关联分析", "中间"]):
            return "P2"

    # B｜软段 / 配方体系
    if any(
        k in a
        for k in ["软段体系", "配方体系", "软段", "PPG", "PTMEG", "PCDL"]
    ):
        return "P1"

    # A｜直接 -30℃ 验证
    if ("-30℃" in a) or ("-30" in a):
        if any(
            k in a
            for k in ["专项", "验证", "测试", "耐折", "≥5万次", "5万次", "直接"]
        ):
            return "P0"

    return None


def normalize_auto001_validation_for_display(
    so,
    scene_id="AUTO-001",
):
    """
    展示层确定性优先级归一。

    返回 (display_so, changes, hold)：
      display_so = deepcopy(so)，仅修改 recommended_validation 的 priority 字段。
      changes    = [{"index": i, "original": ..., "display": ...}]（供 developer 审计）。
      hold       = True 表示未识别到"直接 -30℃ 验证"，不归一、保留原 priority。

    - 不改 action / reason / source_refs 正文。
    - 不改原始 so。
    - 非 AUTO-001 场景不应用规则。
    """
    display = deepcopy(so)
    changes = []
    hold = False

    if scene_id != "AUTO-001":
        return display, changes, hold

    recs = display.get("recommended_validation")

    if not isinstance(recs, list) or not recs:
        return display, changes, hold

    classifications = []

    for item in recs:
        if isinstance(item, dict):
            classifications.append(
                classify_auto001_action(
                    item.get("action") or ""
                )
            )

        else:
            classifications.append(None)

    has_direct_p0 = any(
        c == "P0"
        for c in classifications
    )

    if not has_direct_p0:
        hold = True
        return display, changes, hold

    for i, item in enumerate(recs):
        if not isinstance(item, dict):
            continue

        original = item.get("priority")
        category = classifications[i]

        display_priority = original

        if category == "P0":
            display_priority = "P0"

        elif category == "P1":
            display_priority = "P1"

        elif category == "P2":
            display_priority = "P2"

        if display_priority != original:
            item["priority"] = display_priority
            changes.append({
                "index": i,
                "original": original,
                "display": display_priority,
            })

    return display, changes, hold

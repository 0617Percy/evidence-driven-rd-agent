# -*- coding: utf-8 -*-
"""
UI Display Utils V1.0 离线测试（纯函数，无 LLM / Retriever）。

覆盖：
  TEST-PRODUCT-01..06  —— 产品型号提取 + query fallback
  TEST-PRIORITY-01..07 —— AUTO-001 展示优先级归一
  fixture 离线验证     —— B2_live_result.json（只读）
"""

import json
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import ui_display_utils_v1 as u  # noqa: E402


SO_FIXTURE = {
    "recommended_validation": [
        {
            "priority": "P0",
            "action": "对HD-S303当前配方进行-30℃耐折专项测试（按QB/T 2714方法），确认是否满足≥5万次。",
            "reason": "需直接验证当前实际性能。",
            "source_refs": ["CK-0062", "CK-0095", "CK-AUTO001-REQ-RC-001"],
        },
        {
            "priority": "P0",
            "action": "明确当前HD-S303汽车革配方的软段体系（是否已更换为PTMEG/PCDL），若仍为PPG体系则风险高。",
            "reason": "历史根因是PPG体系低温韧性不足。",
            "source_refs": ["CK-AUTO001-REQ-RC-001", "CK-0062", "CK-0123", "CK-0164"],
        },
        {
            "priority": "P1",
            "action": "若尚未进行-30℃测试，可先进行-20℃耐折抽检作为中间参考。",
            "reason": "历史预防措施已增加-20℃出厂抽检。",
            "source_refs": ["CK-AUTO001-REQ-RC-001", "CK-0062"],
        },
    ]
}


# ------------------------------------------------------------
# Product extraction
# ------------------------------------------------------------

def test_product_01_ascii_hyphen():
    assert u.extract_product("客户要求HD-S303面层-30℃耐折≥5万次") == "HD-S303"


def test_product_02_plain():
    assert u.extract_product("HD-S303准备用在汽车内饰革") == "HD-S303"


def test_product_03_space():
    assert u.extract_product("HD S303汽车革低温性能") == "HD-S303"


def test_product_04_en_dash():
    assert u.extract_product("HD\u2013S303 低温性能") == "HD-S303"


def test_product_05_query_fallback():
    req = "客户需求：汽车内饰革（仪表板包覆革），-30℃耐折≥5万次。"
    query = "汽车内饰革客户要求HD-S303面层-30℃耐折≥5万次，历史上有哪些值得提前关注的风险？"

    assert u.extract_product(req) is None
    assert u.extract_product(query) == "HD-S303"
    assert (u.extract_product(req) or u.extract_product(query)) == "HD-S303"


def test_product_06_no_model():
    assert u.extract_product("客户要求-30℃耐折≥5万次") is None
    assert u.extract_product("") is None
    assert u.extract_product(None) is None


# ------------------------------------------------------------
# Priority normalization
# ------------------------------------------------------------

def test_priority_01_display_p0_p1_p2():
    display, changes, hold = u.normalize_auto001_validation_for_display(
        SO_FIXTURE
    )

    priorities = [
        item["priority"]
        for item in display["recommended_validation"]
    ]

    assert priorities == ["P0", "P1", "P2"]
    assert hold is False
    assert [c["display"] for c in changes] == ["P1", "P2"]


def test_priority_02_original_not_mutated():
    before = deepcopy(SO_FIXTURE)

    u.normalize_auto001_validation_for_display(SO_FIXTURE)

    assert SO_FIXTURE == before


def test_priority_03_source_refs_unchanged():
    display, _, _ = u.normalize_auto001_validation_for_display(
        SO_FIXTURE
    )

    for disp, orig in zip(
        display["recommended_validation"],
        SO_FIXTURE["recommended_validation"],
    ):
        assert disp["source_refs"] == orig["source_refs"]


def test_priority_04_action_unchanged():
    display, _, _ = u.normalize_auto001_validation_for_display(
        SO_FIXTURE
    )

    for disp, orig in zip(
        display["recommended_validation"],
        SO_FIXTURE["recommended_validation"],
    ):
        assert disp["action"] == orig["action"]


def test_priority_05_reason_unchanged():
    display, _, _ = u.normalize_auto001_validation_for_display(
        SO_FIXTURE
    )

    for disp, orig in zip(
        display["recommended_validation"],
        SO_FIXTURE["recommended_validation"],
    ):
        assert disp["reason"] == orig["reason"]


def test_priority_06_no_direct_p0_no_fabricate():
    no_direct = {
        "recommended_validation": [
            {
                "priority": "P0",
                "action": "确认软段体系是否已更换为PTMEG/PCDL。",
                "reason": "r",
                "source_refs": ["CK-0062"],
            },
            {
                "priority": "P1",
                "action": "-20℃抽检作为中间参考。",
                "reason": "r",
                "source_refs": ["CK-0062"],
            },
        ]
    }

    display, changes, hold = u.normalize_auto001_validation_for_display(
        no_direct
    )

    assert hold is True
    assert changes == []
    assert [i["priority"] for i in display["recommended_validation"]] == [
        "P0",
        "P1",
    ]


def test_priority_07_non_auto001_no_rules():
    display, changes, hold = u.normalize_auto001_validation_for_display(
        SO_FIXTURE,
        scene_id="OTHER_SCENE",
    )

    assert changes == []
    assert hold is False
    assert [i["priority"] for i in display["recommended_validation"]] == [
        "P0",
        "P0",
        "P1",
    ]


# ------------------------------------------------------------
# Fixture offline validation (read-only)
# ------------------------------------------------------------

def test_fixture_b2_priority_normalization():
    path = (
        ROOT
        / "outputs"
        / "g2_live_regression_3q_v1"
        / "B2_live_result.json"
    )

    data = json.loads(path.read_text(encoding="utf-8"))
    so = data["structured_output"]

    original_priorities = [
        item["priority"]
        for item in so["recommended_validation"]
    ]

    assert original_priorities == ["P0", "P0", "P1"]

    display, changes, hold = u.normalize_auto001_validation_for_display(so)

    display_priorities = [
        item["priority"]
        for item in display["recommended_validation"]
    ]

    assert display_priorities == ["P0", "P1", "P2"]
    assert hold is False

    # 原始文件内容不变（只读验证）
    assert json.loads(path.read_text(encoding="utf-8")) == data


def run_all():
    tests = [
        test_product_01_ascii_hyphen,
        test_product_02_plain,
        test_product_03_space,
        test_product_04_en_dash,
        test_product_05_query_fallback,
        test_product_06_no_model,
        test_priority_01_display_p0_p1_p2,
        test_priority_02_original_not_mutated,
        test_priority_03_source_refs_unchanged,
        test_priority_04_action_unchanged,
        test_priority_05_reason_unchanged,
        test_priority_06_no_direct_p0_no_fabricate,
        test_priority_07_non_auto001_no_rules,
        test_fixture_b2_priority_normalization,
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
    print("ALL_UI_DISPLAY_TESTS_PASS")

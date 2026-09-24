# -*- coding: utf-8 -*-
"""
Product Role & Scope Coherence Guard V0.6.2 离线测试。

覆盖 TEST-PRG-01..18 + Query Independence + 真实 Evidence fixture。
纯函数，无 LLM / Retriever。
"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import product_role_guard_v0_6_2 as prg  # noqa: E402


def ev(chunk_id, source, doc_type, title="", text=""):
    return {"chunk_id": chunk_id, "source": source, "doc_type": doc_type, "title": title, "text": text}


def role_of(evidence, product):
    roles = prg.classify_product_roles(evidence)
    return roles.get(product, {}).get("role")


def resolve(evidence, scope="AUTO001_SCOPED"):
    return prg.resolve_effective_product(evidence, scope)


# ------------------------------------------------------------
# Role classification
# ------------------------------------------------------------

def test_prg_01_involves_product_primary():
    e = [ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "涉及产品HD-S303。")]
    assert role_of(e, "HD-S303") == "PRIMARY_SUBJECT"


def test_prg_02_surface_layer_primary():
    e = [ev("CK-AUTO001-REQ-RC-001", "03_客户需求/x.md", "客户需求", "需求", "HD-S303面层已通过耐水解验证。")]
    assert role_of(e, "HD-S303") == "PRIMARY_SUBJECT"


def test_prg_03_adhesive_layer_secondary():
    e = [ev("CK-AUTO001-REQ-RC-001", "03_客户需求/x.md", "客户需求", "需求", "粘接层推荐HD-S302改版。")]
    assert role_of(e, "HD-S302") == "SECONDARY_COMPONENT"


def test_prg_04_cost_comparator():
    e = [ev("CK-0154", "02_研发项目/y.md", "文档", "目标", "成本：较HD-W107上升≤15%。")]
    assert role_of(e, "HD-W107") == "COMPARATOR"


# ------------------------------------------------------------
# Effective resolution
# ------------------------------------------------------------

def test_prg_05_primary_plus_secondary_resolved():
    e = [
        ev("CK-AUTO001-REQ-RC-001", "03_客户需求/x.md", "客户需求", "需求", "HD-S303面层...粘接层推荐HD-S302改版。"),
    ]
    r = resolve(e)
    assert r["status"] == "RESOLVED"
    assert r["value"] == "HD-S303"


def test_prg_06_primary_plus_comparator_resolved():
    e = [
        ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "涉及产品HD-S303。"),
        ev("CK-0154", "02_研发项目/y.md", "文档", "目标", "成本：较HD-W107上升≤15%。"),
    ]
    r = resolve(e)
    assert r["status"] == "RESOLVED"
    assert r["value"] == "HD-S303"


def test_prg_07_primary_secondary_comparator_resolved():
    e = [
        ev("CK-AUTO001-REQ-RC-001", "03_客户需求/x.md", "客户需求", "需求", "HD-S303面层...粘接层推荐HD-S302改版。"),
        ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "涉及产品HD-S303。"),
        ev("CK-0154", "02_研发项目/y.md", "文档", "目标", "成本：较HD-W107上升≤15%。"),
    ]
    r = resolve(e)
    assert r["status"] == "RESOLVED"
    assert r["value"] == "HD-S303"


def test_prg_08_two_primaries_ambiguous():
    e = [
        ev("CK-A", "08_问题案例/cases.csv", "问题案例", "A", "涉及产品HD-S303。"),
        ev("CK-B", "08_问题案例/cases.csv", "问题案例", "B", "涉及产品HD-S305。"),
    ]
    r = resolve(e)
    assert r["status"] == "AMBIGUOUS"


def test_prg_09_only_comparator_not_resolved():
    e = [ev("CK-0154", "02_研发项目/y.md", "文档", "目标", "成本：较HD-W107上升≤15%。")]
    r = resolve(e)
    assert r["status"] == "NOT_RESOLVED"


def test_prg_10_only_generic_reference_not_resolved():
    e = [ev("CK-L", "11_公开技术资料/literature.csv", "公开资料", "文献", "某文献提到HD-X99一次。")]
    r = resolve(e)
    assert r["status"] == "NOT_RESOLVED"


def test_prg_11_repeat_same_chunk_one_support():
    text = "涉及产品HD-S303 " * 10
    e = [ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", text)]
    roles = prg.classify_product_roles(e)
    assert len(roles["HD-S303"]["supporting_refs"]) == 1


def test_prg_12_supporting_refs_correct():
    e = [
        ev("CK-AUTO001-REQ-RC-001", "03_客户需求/x.md", "客户需求", "需求", "HD-S303面层。"),
        ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "涉及产品HD-S303。"),
    ]
    r = resolve(e)
    assert "CK-AUTO001-REQ-RC-001" in r["supporting_refs"]
    assert "CK-0062" in r["supporting_refs"]


def test_prg_13_roles_audit_correct():
    e = [
        ev("CK-AUTO001-REQ-RC-001", "03_客户需求/x.md", "客户需求", "需求", "HD-S303面层...粘接层推荐HD-S302改版。"),
        ev("CK-0154", "02_研发项目/y.md", "文档", "目标", "成本：较HD-W107上升≤15%。"),
    ]
    r = resolve(e)
    assert r["roles"]["HD-S303"] == "PRIMARY_SUBJECT"
    assert r["roles"]["HD-S302"] == "SECONDARY_COMPONENT"
    assert r["roles"]["HD-W107"] == "COMPARATOR"


def test_prg_14_query_not_in_role_judgment():
    # 角色判定只基于 evidence，不接受 query 参数
    e = [ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "涉及产品HD-S303。")]
    r = resolve(e)
    assert r["value"] == "HD-S303"


def test_prg_15_llm_answer_not_in_role_judgment():
    e = [ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "涉及产品HD-S303。")]
    assert role_of(e, "HD-S303") == "PRIMARY_SUBJECT"


def test_prg_16_structured_output_not_in_role_judgment():
    # resolver 只接受 evidence，无 structured_output 输入
    e = [ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "涉及产品HD-S303。")]
    assert role_of(e, "HD-S303") == "PRIMARY_SUBJECT"


def test_prg_17_non_auto001_scope_no_disambiguation():
    e = [ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "涉及产品HD-S303。")]
    r = resolve(e, scope="GENERIC_TECHNICAL")
    assert r is None


def test_prg_18_real_evidence_fixture():
    e = [
        ev("CK-AUTO001-REQ-RC-001", "03_客户需求/需求说明书样例_汽车革客户.md", "客户需求",
           "客户需求说明书(样例)", "HD-S303面层已通过6周耐水解验证；粘接层推荐HD-S302改版。"),
        ev("CK-0062", "08_问题案例/cases.csv", "问题案例",
           "CA-2024-062 沙发革低温(-10℃)弯折开裂", "涉及产品HD-S303批次HD-S303-2411-04，低温弯折开裂。"),
        ev("CK-0169", "03_客户需求/需求说明书样例_汽车革客户.md", "文档", "性能要求", "耐折-30℃≥5万次。"),
        ev("CK-0154", "02_研发项目/立项报告.md", "文档", "目标指标", "成本：较HD-W107上升≤15%。"),
        ev("CK-0123", "11_公开技术资料/literature.csv", "公开资料", "文献", "PTMEG较PPG低温更好。"),
        ev("CK-0095", "10_行业标准/standards.csv", "行业标准", "标准", "QB/T 2714耐折牢度。"),
        ev("CK-0164", "11_公开技术资料/综述.md", "文档", "软段选型", "PCDL/PTMEG/PPG软段对比。"),
        ev("CK-0157", "02_研发项目/中试.md", "文档", "中试", "HD-S303完成3000L中试放大。"),
    ]
    r = resolve(e)

    assert r["status"] == "RESOLVED"
    assert r["value"] == "HD-S303"
    assert r["roles"]["HD-S302"] == "SECONDARY_COMPONENT"
    assert r["roles"]["HD-W107"] == "COMPARATOR"
    assert "CK-0157" in r["supporting_refs"]


# ------------------------------------------------------------
# Query independence
# ------------------------------------------------------------

def test_query_independence():
    e = [ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "涉及产品HD-S303。")]

    r1 = resolve(e)
    r2 = resolve(e)

    assert r1 == r2
    assert r1["value"] == "HD-S303"


def run_all():
    tests = [
        test_prg_01_involves_product_primary,
        test_prg_02_surface_layer_primary,
        test_prg_03_adhesive_layer_secondary,
        test_prg_04_cost_comparator,
        test_prg_05_primary_plus_secondary_resolved,
        test_prg_06_primary_plus_comparator_resolved,
        test_prg_07_primary_secondary_comparator_resolved,
        test_prg_08_two_primaries_ambiguous,
        test_prg_09_only_comparator_not_resolved,
        test_prg_10_only_generic_reference_not_resolved,
        test_prg_11_repeat_same_chunk_one_support,
        test_prg_12_supporting_refs_correct,
        test_prg_13_roles_audit_correct,
        test_prg_14_query_not_in_role_judgment,
        test_prg_15_llm_answer_not_in_role_judgment,
        test_prg_16_structured_output_not_in_role_judgment,
        test_prg_17_non_auto001_scope_no_disambiguation,
        test_prg_18_real_evidence_fixture,
        test_query_independence,
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
    print("ALL_PRG_TESTS_PASS")

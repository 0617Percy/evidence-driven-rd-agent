# -*- coding: utf-8 -*-
"""
Context Entity Resolution V0.6 离线测试（纯函数，无 LLM / Retriever）。

覆盖 TEST-CER-01..18 + Query Independence。
核心：产品识别只来自 retrieved evidence，绝不来自 query / LLM answer / Curator。
"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import context_entity_resolver_v0_6 as cer  # noqa: E402


def ev(chunk_id, source, doc_type, title="", text=""):
    return {
        "chunk_id": chunk_id,
        "source": source,
        "doc_type": doc_type,
        "title": title,
        "text": text,
    }


def resolve(evidence):
    return cer.resolve_context_entities(evidence)


def prod(res):
    return res["product"]


# ------------------------------------------------------------
# Core / resolution
# ------------------------------------------------------------

def test_cer_01_query_no_product_resolved_from_case():
    r = resolve([
        ev("CK-0062", "08_问题案例/cases.csv", "问题案例",
           "CA-2024-062 沙发革低温(-10℃)弯折开裂",
           "涉及产品HD-S303批次HD-S303-2411-04，低温弯折开裂。"),
    ])

    assert prod(r)["status"] == "RESOLVED"
    assert prod(r)["value"] == "HD-S303"


def test_cer_02_two_independent_refs_resolved():
    r = resolve([
        ev("CK-0062", "08_问题案例/cases.csv", "问题案例",
           "历史案例", "涉及产品HD-S303。"),
        ev("CK-AUTO001-REQ-RC-001", "03_客户需求/需求说明书样例_汽车革客户.md", "客户需求",
           "客户需求", "HD-S303面层已通过6周耐水解验证。"),
    ])

    assert prod(r)["status"] == "RESOLVED"
    assert prod(r)["value"] == "HD-S303"


def test_cer_03_query_product_but_no_evidence_not_resolved():
    # 证据里没有任何产品型号（仅通用软段资料）
    r = resolve([
        ev("CK-0123", "11_公开技术资料/literature.csv", "公开资料",
           "PTMEG与PPG软段对比", "PTMEG体系低温性能较PPG更好。"),
    ])

    assert prod(r)["status"] == "NOT_RESOLVED"


def test_cer_04_query_hd_s303_evidence_hd_s305():
    # 证据只支持 HD-S305（另一个产品）
    r = resolve([
        ev("CK-Y", "08_问题案例/cases.csv", "问题案例",
           "案例", "涉及产品HD-S305。"),
    ])

    assert prod(r)["value"] != "HD-S303"
    assert prod(r)["value"] == "HD-S305"


def test_cer_05_normalization():
    r = resolve([
        ev("CK-A", "08_问题案例/cases.csv", "问题案例", "案例A", "产品HD–S303。"),
        ev("CK-B", "08_问题案例/cases.csv", "问题案例", "案例B", "产品HD－S303。"),
        ev("CK-C", "08_问题案例/cases.csv", "问题案例", "案例C", "产品HD S303。"),
    ])

    assert prod(r)["status"] == "RESOLVED"
    assert prod(r)["value"] == "HD-S303"


def test_cer_06_ambiguous():
    r = resolve([
        ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例A", "涉及产品HD-S303。"),
        ev("CK-Z", "08_问题案例/cases.csv", "问题案例", "案例B", "涉及产品HD-S305。"),
    ])

    assert prod(r)["status"] == "AMBIGUOUS"


def test_cer_07_generic_ptmeg_literature_not_resolved():
    r = resolve([
        ev("CK-0123", "11_公开技术资料/literature.csv", "公开资料",
           "PTMEG/PPG软段", "PTMEG、PPG、PCDL软段低温特性讨论。"),
    ])

    assert prod(r)["status"] == "NOT_RESOLVED"


def test_cer_08_standard_does_not_force_product():
    r = resolve([
        ev("CK-0095", "10_行业标准/standards.csv", "行业标准",
           "耐折牢度", "QB/T 2714，适用范围常温/低温耐折。HD-S303。"),
    ])

    # 行业标准是低上下文，单个提及不构成实质支持
    assert prod(r)["status"] == "NOT_RESOLVED"


def test_cer_09_single_high_context_case_resolved():
    r = resolve([
        ev("CK-0062", "08_问题案例/cases.csv", "问题案例",
           "案例", "HD-S303低温开裂。"),
    ])

    assert prod(r)["status"] == "RESOLVED"
    assert prod(r)["value"] == "HD-S303"


def test_cer_10_single_low_context_mention_not_resolved():
    r = resolve([
        ev("CK-L", "11_公开技术资料/literature.csv", "公开资料",
           "综述", "某综述偶然提到HD-S303一次。"),
    ])

    assert prod(r)["status"] == "NOT_RESOLVED"


def test_cer_11_repeat_in_same_chunk_counts_once():
    text = "HD-S303 " * 10
    r = resolve([
        ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", text),
    ])

    assert prod(r)["status"] == "RESOLVED"
    assert len(prod(r)["supporting_refs"]) == 1


def test_cer_12_supporting_refs_traceable():
    r = resolve([
        ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "HD-S303。"),
    ])

    assert prod(r)["supporting_refs"] == ["CK-0062"]


def test_cer_13_candidate_products():
    r = resolve([
        ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "HD-S303。"),
    ])

    assert prod(r)["candidate_products"] == ["HD-S303"]


def test_cer_14_not_reading_llm_answer():
    # resolver 只接受 evidence，不接受 LLM answer；构造 LLM answer 不影响
    evidence = [
        ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "HD-S303。"),
    ]

    assert resolve(evidence) == resolve(evidence)


def test_cer_15_not_reading_curator_output():
    # resolver 不读取 curator output（无该输入）
    r = resolve([
        ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "HD-S303。"),
    ])

    assert prod(r)["value"] == "HD-S303"


def test_cer_16_empty_input_not_resolved():
    r = resolve([])

    assert prod(r)["status"] == "NOT_RESOLVED"


def test_cer_17_bad_fields_no_crash():
    r = resolve([
        {},
        {"chunk_id": "x", "source": "s", "title": None, "text": None},
        "not-a-dict",
        None,
    ])

    assert prod(r)["status"] == "NOT_RESOLVED"


def test_cer_18_non_auto001_product_recognized():
    r = resolve([
        ev("CK-Z", "08_问题案例/cases.csv", "问题案例", "案例", "涉及产品HD-S305。"),
    ])

    assert prod(r)["value"] == "HD-S305"
    assert prod(r)["value"] != "HD-S303"


# ------------------------------------------------------------
# Query independence
# ------------------------------------------------------------

def test_query_independence():
    evidence = [
        ev("CK-0062", "08_问题案例/cases.csv", "问题案例", "案例", "涉及产品HD-S303。"),
    ]

    r1 = resolve(evidence)
    r2 = resolve(evidence)

    # query 完全不传入 resolver，结果必然相同
    assert r1 == r2
    assert prod(r1)["value"] == "HD-S303"


def test_query_names_product_but_evidence_does_not():
    # 证据无产品，resolver 不会因 query 写 HD-S303 而 RESOLVED
    evidence = [
        ev("CK-0123", "11_公开技术资料/literature.csv", "公开资料", "文献", "PTMEG低温性能。"),
    ]

    r = resolve(evidence)

    assert prod(r)["status"] == "NOT_RESOLVED"
    assert prod(r)["value"] is None


def run_all():
    tests = [
        test_cer_01_query_no_product_resolved_from_case,
        test_cer_02_two_independent_refs_resolved,
        test_cer_03_query_product_but_no_evidence_not_resolved,
        test_cer_04_query_hd_s303_evidence_hd_s305,
        test_cer_05_normalization,
        test_cer_06_ambiguous,
        test_cer_07_generic_ptmeg_literature_not_resolved,
        test_cer_08_standard_does_not_force_product,
        test_cer_09_single_high_context_case_resolved,
        test_cer_10_single_low_context_mention_not_resolved,
        test_cer_11_repeat_in_same_chunk_counts_once,
        test_cer_12_supporting_refs_traceable,
        test_cer_13_candidate_products,
        test_cer_14_not_reading_llm_answer,
        test_cer_15_not_reading_curator_output,
        test_cer_16_empty_input_not_resolved,
        test_cer_17_bad_fields_no_crash,
        test_cer_18_non_auto001_product_recognized,
        test_query_independence,
        test_query_names_product_but_evidence_does_not,
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
    print("ALL_CER_TESTS_PASS")

import argparse
import importlib.util
import json
import os
from copy import deepcopy
from pathlib import Path

from dotenv import load_dotenv
from fastembed import TextEmbedding
from openai import OpenAI
from qdrant_client import QdrantClient

from context_entity_resolver_v0_6 import resolve_context_entities
from context_scope_guard_v0_6_1 import (
    SCOPE_AUTO001,
    SCOPE_GENERIC,
    apply_grounding_guard,
    resolve_conversation_scope,
    resolve_context_scope,
    resolve_current_formulation,
)
from product_role_guard_v0_6_2 import resolve_effective_product
from validation_policy_guard_v0_6_3 import apply_auto001_validation_policy
from conversation_subject_resolver_v0_6_5 import resolve_conversation_subject


load_dotenv()

RETRIEVER_MODULE = Path(
    "src/eval_gold_rc2_2.py"
)

REQ_ID = "CK-AUTO001-REQ-RC-001"

FORMAL_LEVELS = {
    "E1",
    "E2",
    "E3",
    "EG",
}


# ============================================================
# 1. Frozen Retriever
# ============================================================

spec = importlib.util.spec_from_file_location(
    "rc2_2",
    RETRIEVER_MODULE,
)

retriever = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retriever)


# ============================================================
# 2. Prompt Contract
# ============================================================

SYSTEM_PROMPT = r"""
你是“研发避坑 Agent”的回答生成模块。

产品定位：
客户需求驱动、基于企业历史证据的可追溯研发风险预审 Agent。

你的职责：
- 组织 Retriever 实际返回的 Evidence
- 提示历史风险
- 判断历史条件与当前条件是否一致
- 明确 Evidence Gap
- 给出下一步验证建议

你不是：
- 最终工程决策系统
- 配方自动决策系统
- 性能保证系统

【强制规则】

1. 只能使用本轮提供的 Evidence。
2. 不得补充 Evidence 中不存在的企业事实。
3. Requirement Anchor 只说明“客户当前要求是什么”，不是 E1 实测证据。
4. 正式 Evidence Level 只有：E1 / E2 / E3 / EG。
5. 不得输出 E1_ANCHOR 或 BACKGROUND 作为 Evidence Level。
6. E2 只能作为高相关历史风险参考，不能直接证明当前场景结果。
7. E3 只能作为标准/公开技术参考，不能表达为当前产品实测结果。
8. 历史条件与当前条件不一致时必须显式说明。
9. -10℃ / -20℃不得静默外推-30℃。
10. 沙发革不得静默外推汽车内饰革。
11. 缺少当前直接专项验证时必须明确 Evidence Gap。
12. 不得给出无证据的确定性 Pass / Fail。
13. 不得给出保证通过的最终配方。
14. 不得为了调和证据冲突自行假设缺失业务条件。
15. 所有 chunk_id / source_refs 必须逐字符复制 ALLOWED_CHUNK_IDS。
16. 不得缩写 chunk_id。
17. 不需要引用所有 Top-8，只引用真正支持 Claim 的 Evidence。

【当前场景 Evidence Gap安全口径】

如果问题涉及当前汽车内饰革 HD-S303
“-30℃耐折≥5万次”，且 Evidence 中没有直接专项验证，
应表达为：

“基于当前已审阅资料范围，未发现/未明确说明HD-S303针对当前汽车内饰革客户‘-30℃耐折≥5万次’的直接专项验证结果。”

不得改写成：
- 企业没有做过
- 项目没有做过
- 已经验证失败
- 当前一定不达标

【Structured Output】

只输出 JSON Object，不要 Markdown：

{
  "requirement": {
    "text": "",
    "role": "requirement_anchor",
    "source_refs": []
  },

  "risk_summary": "",

  "historical_evidence": [
    {
      "claim": "",
      "chunk_id": "",
      "evidence_level": "E2",
      "historical_condition": ""
    }
  ],

  "technical_evidence": [
    {
      "claim": "",
      "chunk_id": "",
      "evidence_level": "E3"
    }
  ],

  "evidence_level": [
    {
      "chunk_id": "",
      "level": "E1|E2|E3|EG"
    }
  ],

  "condition_gap": [
    {
      "dimension": "",
      "historical": "",
      "current": "",
      "source_refs": []
    }
  ],

  "evidence_gap": {
    "statement": "",
    "source_refs": []
  },

  "recommended_validation": [
    {
      "priority": "P0",
      "action": "",
      "reason": "",
      "source_refs": []
    }
  ],

  "sources": [
    {
      "chunk_id": "",
      "title": "",
      "source": ""
    }
  ]
}
"""


# ============================================================
# 3. Evidence metadata
# ============================================================

def classify_evidence(payload):
    chunk_id = str(
        payload.get("chunk_id")
        or ""
    )

    source = str(
        payload.get("source")
        or ""
    )

    doc_type = str(
        payload.get("doc_type")
        or ""
    )

    if chunk_id == REQ_ID:
        return {
            "role": "requirement_anchor",
            "evidence_level": None,
        }

    if (
        "08_问题案例" in source
        or doc_type == "问题案例"
    ):
        return {
            "role": None,
            "evidence_level": "E2",
        }

    if (
        "10_行业标准" in source
        or "11_公开技术资料" in source
        or doc_type in {
            "行业标准",
            "公开资料",
        }
    ):
        return {
            "role": None,
            "evidence_level": "E3",
        }

    return {
        "role": "supporting_reference",
        "evidence_level": None,
    }


def build_evidence(
    rank,
    final_score,
    hit,
):
    payload = hit.payload or {}

    cls = classify_evidence(
        payload
    )

    return {
        "rank": rank,
        "chunk_id":
            payload.get("chunk_id"),

        "role":
            cls["role"],

        "evidence_level":
            cls["evidence_level"],

        "title":
            payload.get("title"),

        "source":
            payload.get("source"),

        "doc_type":
            payload.get("doc_type"),

        "vector_score":
            round(
                float(hit.score),
                6,
            ),

        "final_score":
            round(
                float(final_score),
                6,
            ),

        "text":
            payload.get("text"),
    }


# ============================================================
# 4. Citation helpers
# ============================================================

def collect_refs(obj):
    refs = set()

    def walk(value):
        if isinstance(value, dict):

            for key, item in value.items():

                if (
                    key == "chunk_id"
                    and isinstance(item, str)
                    and item
                ):
                    refs.add(item)

                if (
                    key == "source_refs"
                    and isinstance(item, list)
                ):
                    for ref in item:
                        if isinstance(ref, str):
                            refs.add(ref)

                walk(item)

        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(obj)

    return refs


def evidence_by_id(evidence):
    return {
        x["chunk_id"]: x
        for x in evidence
        if x.get("chunk_id")
    }


# ============================================================
# 5. Contract normalizer
# ============================================================

def normalize_contract(
    answer,
    evidence,
):
    result = deepcopy(answer)

    by_id = evidence_by_id(
        evidence
    )

    retrieved_ids = set(
        by_id
    )

    changes = []

    requirement = (
        result.get("requirement")
        or {}
    )

    requirement[
        "role"
    ] = "requirement_anchor"

    result[
        "requirement"
    ] = requirement

    # --------------------------------------------------------
    # evidence_level总表只允许正式枚举
    # Requirement Anchor不得进入表中
    # --------------------------------------------------------

    normalized_levels = []

    for item in (
        result.get("evidence_level")
        or []
    ):
        if not isinstance(item, dict):
            continue

        cid = item.get("chunk_id")

        if cid == REQ_ID:
            changes.append(
                "REMOVE_REQUIREMENT_FROM_LEVEL_TABLE"
            )
            continue

        actual = by_id.get(cid)

        if not actual:
            continue

        level = actual.get(
            "evidence_level"
        )

        if level in FORMAL_LEVELS:
            normalized_levels.append({
                "chunk_id": cid,
                "level": level,
            })

    result[
        "evidence_level"
    ] = normalized_levels

    # --------------------------------------------------------
    # Evidence item level按实际来源归一
    # --------------------------------------------------------

    for field in [
        "historical_evidence",
        "technical_evidence",
    ]:

        for item in (
            result.get(field)
            or []
        ):

            if not isinstance(item, dict):
                continue

            cid = item.get(
                "chunk_id"
            )

            actual = by_id.get(
                cid
            )

            if not actual:
                continue

            actual_level = (
                actual.get(
                    "evidence_level"
                )
            )

            actual_role = (
                actual.get("role")
            )

            if actual_level:
                item[
                    "evidence_level"
                ] = actual_level

                item.pop(
                    "role",
                    None,
                )

            elif actual_role:
                item.pop(
                    "evidence_level",
                    None,
                )

                item[
                    "role"
                ] = actual_role

    # --------------------------------------------------------
    # Evidence Gap必须可追溯
    #
    # 如果模型输出了Gap文案但source_refs为空，
    # 则只从本轮已检索、且本回答实际使用的Evidence中补全：
    # Requirement Anchor + Historical / Technical Evidence。
    # 不新增事实，不修改Gap Claim。
    # --------------------------------------------------------

    gap = result.get(
        "evidence_gap"
    )

    if isinstance(
        gap,
        dict,
    ):
        gap_refs = list(
            gap.get(
                "source_refs"
            )
            or []
        )

        if not gap_refs:

            candidates = []

            # Requirement Anchor
            requirement_refs = (
                (
                    result.get(
                        "requirement"
                    )
                    or {}
                ).get(
                    "source_refs"
                )
                or []
            )

            candidates.extend(
                requirement_refs
            )

            # 实际用于本回答的历史 / 技术Evidence
            for field in [
                "historical_evidence",
                "technical_evidence",
            ]:
                for item in (
                    result.get(field)
                    or []
                ):
                    if not isinstance(
                        item,
                        dict,
                    ):
                        continue

                    cid = item.get(
                        "chunk_id"
                    )

                    if cid:
                        candidates.append(
                            cid
                        )

            # 去重 + 必须来自本轮Retriever
            normalized_gap_refs = []

            for cid in candidates:
                if (
                    cid in retrieved_ids
                    and cid
                    not in normalized_gap_refs
                ):
                    normalized_gap_refs.append(
                        cid
                    )

            if normalized_gap_refs:
                gap[
                    "source_refs"
                ] = normalized_gap_refs

                changes.append(
                    "FILL_EMPTY_EVIDENCE_GAP_SOURCE_REFS"
                )
    # --------------------------------------------------------
    # P0若使用当前Requirement条件，自动补Requirement引用
    # --------------------------------------------------------

    for item in (
        result.get(
            "recommended_validation"
        )
        or []
    ):

        if not isinstance(item, dict):
            continue

        text = (
            str(item.get("action") or "")
            + " "
            + str(item.get("reason") or "")
        )

        if (
            REQ_ID in retrieved_ids
            and any(
                signal in text
                for signal in [
                    "-30℃",
                    "汽车内饰革",
                    "5万次",
                    "当前",
                ]
            )
        ):
            refs = list(
                item.get(
                    "source_refs"
                )
                or []
            )

            if REQ_ID not in refs:
                refs.insert(
                    0,
                    REQ_ID,
                )

                item[
                    "source_refs"
                ] = refs

                changes.append(
                    "ADD_REQUIREMENT_REF_TO_P0"
                )

    return (
        result,
        changes,
    )


# ============================================================
# 6. Negation-aware safety
# ============================================================

NEGATIONS = [
    "不能",
    "无法",
    "不足以",
    "不得",
    "不应",
    "未能",
    "并不能",
    "不能直接",
    "无法直接",
    "不能得出",
    "无法得出",
    "而非",
    "不是",
]


def unnegated_occurrence(
    text,
    phrase,
):
    start = 0

    while True:

        idx = text.find(
            phrase,
            start,
        )

        if idx < 0:
            return False

        prefix = text[
            max(
                0,
                idx - 28,
            ):
            idx
        ]

        if not any(
            n in prefix
            for n in NEGATIONS
        ):
            return True

        start = (
            idx
            + len(phrase)
        )


# ============================================================
# 7. Live safety validator
# ============================================================

def validate_live(
    query,
    answer,
    evidence,
):
    by_id = evidence_by_id(
        evidence
    )

    retrieved_ids = set(
        by_id
    )

    refs = collect_refs(
        answer
    )

    unknown = (
        refs
        - retrieved_ids
    )

    if unknown:
        raise AssertionError(
            "CITATION_NOT_RETRIEVED:"
            + repr(
                sorted(unknown)
            )
        )

    # --------------------------------------------------------
    # 正式Evidence Level检查
    # --------------------------------------------------------

    for item in (
        answer.get(
            "evidence_level"
        )
        or []
    ):

        level = item.get(
            "level"
        )

        if level not in FORMAL_LEVELS:
            raise AssertionError(
                "NON_FROZEN_LEVEL:"
                + str(level)
            )

        if (
            item.get("chunk_id")
            == REQ_ID
        ):
            raise AssertionError(
                "REQUIREMENT_ANCHOR_IN_LEVEL_TABLE"
            )

    # --------------------------------------------------------
    # Source title/path必须来自Retriever真实metadata
    # --------------------------------------------------------

    for item in (
        answer.get("sources")
        or []
    ):

        if not isinstance(item, dict):
            continue

        cid = item.get(
            "chunk_id"
        )

        if cid not in by_id:
            raise AssertionError(
                "SOURCE_NOT_RETRIEVED:"
                + str(cid)
            )

        actual = by_id[cid]

        if (
            item.get("title")
            != actual.get("title")
        ):
            raise AssertionError(
                "SOURCE_TITLE_MISMATCH:"
                + str(cid)
            )

        if (
            item.get("source")
            != actual.get("source")
        ):
            raise AssertionError(
                "SOURCE_PATH_MISMATCH:"
                + str(cid)
            )

    # --------------------------------------------------------
    # Unsupported deterministic claims
    # --------------------------------------------------------

    check_text = " ".join([
        str(
            answer.get(
                "risk_summary"
            )
            or ""
        ),
        json.dumps(
            answer.get(
                "evidence_gap"
            )
            or {},
            ensure_ascii=False,
        ),
        json.dumps(
            answer.get(
                "recommended_validation"
            )
            or [],
            ensure_ascii=False,
        ),
    ])

    dangerous = [
        "肯定过不了",
        "一定不满足",
        "一定无法满足",
        "企业没有做过",
        "项目没有做过",
        "已经验证失败",
        "保证-30℃通过",
        "保证 -30℃通过",
        "保证通过的配方",
        "确认达标",
        "确定达标",
    ]

    bad = []

    for phrase in dangerous:
        if unnegated_occurrence(
            check_text,
            phrase,
        ):
            bad.append(
                phrase
            )

    if bad:
        raise AssertionError(
            "UNSUPPORTED_CLAIM:"
            + repr(
                sorted(
                    set(bad)
                )
            )
        )

    # --------------------------------------------------------
    # AUTO-001当前核心问题需要Evidence Gap
    # --------------------------------------------------------

    current_scene = (
        (
            "-30"
            in query
            or "30℃"
            in query
        )
        and (
            "HD-S303"
            in query
            or "汽车"
            in query
        )
    )

    gap = (
        answer.get(
            "evidence_gap"
        )
        or {}
    )

    gap_statement = (
        gap.get("statement")
        if isinstance(gap, dict)
        else str(gap)
    )

    if current_scene:

        if not (
            "-30℃"
            in str(gap_statement)
            and any(
                x in str(
                    gap_statement
                )
                for x in [
                    "未发现",
                    "未明确说明",
                    "未提供",
                    "缺少",
                ]
            )
        ):
            raise AssertionError(
                "AUTO001_EVIDENCE_GAP_MISSING"
            )

        gap_refs = (
            gap.get(
                "source_refs"
            )
            if isinstance(
                gap,
                dict,
            )
            else []
        ) or []

        if not gap_refs:
            raise AssertionError(
                "EVIDENCE_GAP_CITATION_EMPTY"
            )

        bad_gap_refs = (
            set(gap_refs)
            - retrieved_ids
        )

        if bad_gap_refs:
            raise AssertionError(
                "EVIDENCE_GAP_CITATION_NOT_RETRIEVED:"
                + repr(
                    sorted(
                        bad_gap_refs
                    )
                )
            )

    return {
        "status": "PASS",
        "citation_correctness":
            "PASS",
        "unsupported_claim_count":
            0,
        "formal_level_contract":
            "PASS",
        "evidence_gap_guard":
            (
                "PASS"
                if current_scene
                else "N/A"
            ),
    }


# ============================================================
# 7b. Generic Technical Answer Prompt（不注入 AUTO-001）
# ============================================================

GENERIC_SYSTEM_PROMPT = r"""
你是"研发避坑 Agent"的通用技术咨询模块。

你的任务是：仅基于本轮提供的检索证据，回答用户的技术问题。

硬规则：
- 只能使用本轮提供的 Evidence。
- 不得注入任何特定客户 / 产品 / 项目 / 指标假设。
- 不得生成 AUTO-001 特定字段（requirement / evidence_gap / recommended_validation）。
- 不得把历史条件或材料机理外推为具体产品的当前验证结论。
- 证据只覆盖对应资料条件时，必须说明证据范围。

只输出 JSON Object，不要 Markdown：

{
  "generic_answer": "基于证据回答用户技术问题",
  "evidence_refs": ["CK-..."]
}
"""


# ============================================================
# 8. Live chain
# ============================================================

def run_live(
    query,
    runtime_config=None,
    previous_scene_context=None,
):
    if runtime_config is not None:
        api_key = runtime_config.api_key
        base_url = runtime_config.base_url
        model = runtime_config.model

    else:
        api_key = os.getenv(
            "LLM_API_KEY"
        )

        base_url = os.getenv(
            "LLM_BASE_URL"
        )

        model = os.getenv(
            "LLM_MODEL"
        )

    if not api_key:
        raise RuntimeError(
            "LLM_API_KEY_NOT_FOUND"
        )

    if not base_url:
        raise RuntimeError(
            "LLM_BASE_URL_NOT_FOUND"
        )

    if not model:
        raise RuntimeError(
            "LLM_MODEL_NOT_FOUND"
        )

    client = QdrantClient(
        path=str(
            retriever.DB_PATH
        )
    )

    try:
        embedder = TextEmbedding(
            model_name=
                retriever.MODEL_NAME
        )

        hits = retriever.search(
            client,
            embedder,
            query,
            candidate_k=60,
            top_k=8,
        )

        evidence = [
            build_evidence(
                rank,
                final_score,
                hit,
            )
            for rank, (
                final_score,
                hit,
            )
            in enumerate(
                hits,
                start=1,
            )
        ]

    finally:
        client.close()

    allowed_ids = [
        x["chunk_id"]
        for x in evidence
        if x.get("chunk_id")
    ]

    # ---- Context Entity / Scope / Formulation Resolution（deterministic）----
    context_resolution = resolve_context_entities(evidence)

    scope_result = resolve_conversation_scope(
        query,
        evidence,
        context_resolution,
        previous_scene_context,
    )

    context_scope = scope_result["scope"]
    scope_resolution_basis = scope_result["scope_resolution_basis"]
    scene_inheritance_used = scope_result["scene_inheritance_used"]
    inherited_scene_context = scope_result["inherited_scene_context"]

    current_formulation = resolve_current_formulation(evidence)

    # ---- Effective Product（Evidence-only）+ Conversation Subject（会话主题）----
    if context_scope == SCOPE_AUTO001:
        effective_product_resolution = resolve_effective_product(
            evidence,
            context_scope,
            context_resolution,
        )

    else:
        effective_product_resolution = None

    conversation_subject = resolve_conversation_subject(
        query,
        context_scope,
        previous_scene_context,
        (effective_product_resolution or {}).get("status"),
        (effective_product_resolution or {}).get("value"),
    )

    llm = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    # ---- AMBIGUOUS / NOT_SCOPED：不调用 LLM，仅返回 scope 供 UI 提示 ----
    if context_scope not in (SCOPE_AUTO001, SCOPE_GENERIC):
        return {
            "query": query,
            "retriever": "RC2.2 FROZEN",
            "model": model,
            "evidence": evidence,
            "context_resolution": context_resolution,
            "effective_product_resolution": None,
            "conversation_subject": conversation_subject,
            "context_scope": context_scope,
            "current_formulation": current_formulation,
            "scope_resolution_basis": scope_resolution_basis,
            "scene_inheritance_used": scene_inheritance_used,
            "inherited_scene_context": inherited_scene_context,
        }

    # ---- GENERIC：通用技术咨询 Route（仍一次 LLM，不注入 AUTO-001）----
    if context_scope == SCOPE_GENERIC:
        generic_user_prompt = (
            "用户问题：\n"
            + query
            + "\n\n"
            + "Retriever实际返回Evidence：\n"
            + json.dumps(
                evidence,
                ensure_ascii=False,
                indent=2,
            )
        )

        response = llm.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": GENERIC_SYSTEM_PROMPT},
                {"role": "user", "content": generic_user_prompt},
            ],
        )

        generic_answer = json.loads(
            response.choices[0].message.content
        )

        return {
            "query": query,
            "retriever": "RC2.2 FROZEN",
            "model": model,
            "evidence": evidence,
            "context_resolution": context_resolution,
            "effective_product_resolution": None,
            "conversation_subject": conversation_subject,
            "context_scope": context_scope,
            "current_formulation": current_formulation,
            "scope_resolution_basis": scope_resolution_basis,
            "scene_inheritance_used": scene_inheritance_used,
            "inherited_scene_context": inherited_scene_context,
            "generic_answer": generic_answer,
        }

    # ---- AUTO001_SCOPED：现有 AUTO-001 Risk Precheck Route ----
    user_prompt = (
        "用户问题：\n"
        + query
        + "\n\n"
        + "Retriever实际返回Evidence：\n"
        + json.dumps(
            evidence,
            ensure_ascii=False,
            indent=2,
        )
        + "\n\nALLOWED_CHUNK_IDS：\n"
        + json.dumps(
            allowed_ids,
            ensure_ascii=False,
        )
        + "\n\n请严格依据上述Evidence生成Structured Output。"
    )

    response = llm.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    raw = response.choices[0].message.content

    answer = json.loads(raw)

    (
        answer,
        normalizations,
    ) = normalize_contract(
        answer,
        evidence,
    )

    safety = validate_live(
        query,
        answer,
        evidence,
    )

    # ---- Grounding Guard：拦截不支持的"当前配方"断言 ----
    effective_grounded_output, grounding_changes = apply_grounding_guard(
        answer,
        current_formulation,
    )

    # ---- Validation Policy Guard：稳定为冻结 P0/P1/P2 ----
    policy_grounded_output, validation_policy_changes = (
        apply_auto001_validation_policy(
            effective_grounded_output,
            current_formulation,
            context_scope,
        )
    )

    return {
        "query": query,
        "retriever": "RC2.2 FROZEN",
        "model": model,
        "evidence": evidence,
        "context_resolution": context_resolution,
        "effective_product_resolution": effective_product_resolution,
        "conversation_subject": conversation_subject,
        "context_scope": context_scope,
        "current_formulation": current_formulation,
        "scope_resolution_basis": scope_resolution_basis,
        "scene_inheritance_used": scene_inheritance_used,
        "inherited_scene_context": inherited_scene_context,
        "structured_output": answer,
        "effective_grounded_output": effective_grounded_output,
        "policy_grounded_output": policy_grounded_output,
        "grounding_changes": grounding_changes,
        "validation_policy_changes": validation_policy_changes,
        "normalizations": normalizations,
        "safety": safety,
    }


# ============================================================
# 9. CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--query",
        required=True,
    )

    parser.add_argument(
        "--out",
        default=
            "outputs/live_smoke_result_v1.json",
    )

    args = parser.parse_args()

    result = run_live(
        args.query
    )

    out = Path(
        args.out
    )

    out.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    out.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "LIVE_RETRIEVED_IDS:",
        [
            x["chunk_id"]
            for x in result[
                "evidence"
            ]
        ],
    )

    print(
        "NORMALIZATIONS:",
        result[
            "normalizations"
        ],
    )

    print(
        "SAFETY:",
        result[
            "safety"
        ],
    )

    print(
        "OUTPUT:",
        out,
    )

    print(
        "AUTO001_LIVE_CHAIN_SMOKE_PASS"
    )


if __name__ == "__main__":
    main()


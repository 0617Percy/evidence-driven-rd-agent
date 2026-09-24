# -*- coding: utf-8 -*-
"""
Knowledge Evolution Loop V0.2 — LLM-assisted Knowledge Curator (独立模块)

本模块是一条与回答链完全解耦的"知识治理链"。

正确流程：
    Live Query
    -> 既有 Answer Chain 完成 (run_live)
    -> Safety PASS
    -> Query Trace
    -> Knowledge Curator LLM (分类 / 判断关系 / 治理建议)
    -> Curator Deterministic Guard
    -> Knowledge Governance Decision
    -> 如需更新则生成 Knowledge Update Candidate (PENDING_REVIEW)
    -> 等待 Y / 研发工程师人工审核

永久安全原则：
    USER_QUESTION_IS_EVIDENCE      = NO
    LLM_ANSWER_IS_APPROVED_EVIDENCE = NO
    EVIDENCE_GAP_IS_NEW_EVIDENCE    = NO
    AUTO_WRITE_MASTER_KB            = NO
    AUTO_APPROVE_KNOWLEDGE          = NO
    AUTO_REINDEX                    = NO
    HUMAN_REVIEW_REQUIRED           = YES

Knowledge Curator 只能：分类 / 判断关系 / 提出知识治理建议 / 生成 Candidate。
Knowledge Curator 不能：创造 Evidence、批准 Evidence、修改 Master KB、
修改 RAG Corpus、修改 Qdrant、重新定义业务结论。

本模块：
- 不修改 Corpus / Retriever / Qdrant / Gold / Evidence Gap / Evidence Level / Contract
- V0.2 不执行第二次 Retriever，直接复用本轮 Live Answer 已获取的数据
- 不新增第三方依赖（仅 Python 标准库 + 项目已装的 openai/dotenv，且懒加载）
"""

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


# ============================================================
# 0. Constants
# ============================================================

CURATOR_VERSION = "0.2"

# ------------------------------------------------------------
# Architectural boundary（重要架构约定）
# ------------------------------------------------------------
# 真正的企业知识库 / Master KB 位于 Y 侧电脑，由 Y 维护，是唯一知识权威源。
# W 侧本地不存在正式 Obsidian Master KB。
# W 侧只有：Y 交付/导出的开发输入副本、RC1 170 chunks Runtime Corpus
# Snapshot、Qdrant 本地运行索引、Retriever / Agent / Streamlit。
# 本模块最终输出 = 待人工审核的 Knowledge Update Candidate：
#   Candidate -> PENDING_REVIEW -> Export/Handoff to Y -> Y 审核 -> Y 侧 Master KB 入库
# W 侧只负责：发现缺口 / 分类 / 生成治理建议 / 生成待审核 Candidate / 保存审计记录。
# 不实现 W 本地 Master KB 写入、不实现跨电脑同步、不生成 W 本地 Obsidian 路径。

MASTER_KB_LOCATION = "Y_SIDE_EXTERNAL"
W_LOCAL_MASTER_KB = "NONE"
W_RUNTIME_CORPUS = "SNAPSHOT_ONLY"
MASTER_KB_WRITE_IMPLEMENTED = "NO"

DECISION_TYPES = {
    "NO_UPDATE",
    "EXISTING_TOPIC_EXTENSION",
    "EVIDENCE_GAP",
    "NEW_TOPIC",
    "KNOWLEDGE_CONFLICT",
    "NEW_EVIDENCE",
}

KB_ACTIONS = {
    "NO_WRITE",
    "EXTEND_EXISTING",
    "REQUEST_NEW_EVIDENCE",
    "CREATE_NEW_TOPIC",
    "REVIEW_CONFLICT",
}

TARGET_MODES = {
    "EXISTING_SOURCE",
    "NEW_TOPIC",
    "REVIEW_QUEUE",
}

KNOWLEDGE_DOMAINS = {
    "REQUIREMENT",
    "CASE",
    "STANDARD",
    "LITERATURE",
    "PROJECT",
    "GENERAL_RND_KNOWLEDGE",
    "UNKNOWN",
}

TRACES_FILENAME = "query_traces.jsonl"
CANDIDATES_FILENAME = "kb_update_candidates.jsonl"

REVIEW_STATUS = "PENDING_REVIEW"
KNOWLEDGE_CLAIM_STATUS = "NOT_APPROVED_EVIDENCE"

# 强制安全值：任何 LLM 输出都会被 Guard 覆盖为该值。
SAFETY_BOUNDARY = {
    "user_question_is_evidence": False,
    "llm_answer_is_approved_evidence": False,
    "auto_write_master_kb": False,
    "auto_reindex": False,
    "human_review_required": True,
}

REVIEW_NOTE = (
    "用户问题及AI回答不是正式Evidence。"
    "Knowledge Curator仅生成知识治理建议。"
    "只有研发工程师/知识负责人补充并审核可追溯Evidence后，"
    "才允许进入Y侧Master KB（W侧无本地Master KB，不自动写入）。"
)

MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_FEEDBACK_DIR = (
    MODULE_DIR.parent / "outputs" / "knowledge_feedback"
)


# ============================================================
# 1. Text / key helpers
# ============================================================

def normalize_text(text):
    return re.sub(
        r"\s+",
        " ",
        str(text or ""),
    ).strip()


def compute_candidate_key(
    decision_type,
    query,
    related_existing_refs,
    knowledge_gap_summary,
):
    """
    稳定 candidate_key：decision_type + 规范化 query
    + sorted related_existing_refs + 规范化 knowledge_gap_summary
    -> SHA256。相同输入必须稳定（用于未来聚合）。
    """
    refs = sorted(
        str(r)
        for r in (
            related_existing_refs
            or []
        )
    )

    parts = [
        normalize_text(decision_type),
        normalize_text(query),
    ]

    parts.extend(refs)

    parts.append(
        normalize_text(knowledge_gap_summary)
    )

    payload = "\n".join(parts)

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _retrieved_ids(result):
    return [
        x.get("chunk_id")
        for x in (
            result.get("evidence")
            or []
        )
        if x.get("chunk_id")
    ]


def _append_jsonl(path, obj):
    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "a",
        encoding="utf-8",
    ) as handle:
        handle.write(
            json.dumps(
                obj,
                ensure_ascii=False,
            )
            + "\n"
        )


# ============================================================
# 2. Curator Input builder
# ============================================================

def build_curator_input(result):
    """
    只使用本轮 Live Answer 已有数据构造 Curator 输入。
    不执行第二次 Retriever，不创造新 source。
    """
    structured = (
        result.get("structured_output")
        or {}
    )

    safety = (
        result.get("safety")
        or {}
    )

    evidence = (
        result.get("evidence")
        or []
    )

    retrieved_knowledge = []

    for item in evidence:
        if not isinstance(item, dict):
            continue

        retrieved_knowledge.append({
            "chunk_id":
                item.get("chunk_id"),

            "title":
                item.get("title"),

            "source":
                item.get("source"),

            "document_type":
                item.get("doc_type")
                or item.get("role"),

            "text":
                item.get("text"),
        })

    gap = structured.get("evidence_gap")

    if not isinstance(gap, dict):
        gap = {}

    formal_levels = []

    for item in (
        structured.get("evidence_level")
        or []
    ):
        if not isinstance(item, dict):
            continue

        formal_levels.append({
            "chunk_id":
                item.get("chunk_id"),

            "level":
                item.get("level"),
        })

    return {
        "query":
            result.get("query"),

        "retrieved_knowledge":
            retrieved_knowledge,

        "answer_summary": {
            "risk_summary":
                structured.get("risk_summary"),

            "condition_gap":
                structured.get("condition_gap")
                or [],
        },

        "evidence_gap": {
            "statement":
                gap.get("statement"),

            "source_refs":
                gap.get("source_refs")
                or [],
        },

        "recommended_validation":
            structured.get("recommended_validation")
            or [],

        "formal_evidence_levels":
            formal_levels,

        "safety_status":
            safety.get("status"),
    }


# ============================================================
# 3. Curator System Prompt
# ============================================================

CURATOR_SYSTEM_PROMPT = r"""
你是"企业研发知识治理助手"，不是研发回答 Agent。

你的任务不是回答用户问题，而是判断：
"这次用户提出的新问题，和企业现有知识库是什么关系，
是否值得沉淀，应该补充已有知识还是建立新主题，
是否存在 Evidence Gap 或知识冲突，下一步应该补什么 Evidence。"

你只能基于本轮提供的：
- 用户问题
- 本轮检索到的现有知识 (retrieved_knowledge)
- 当前回答中的 Evidence Chain / Condition Gap / Evidence Gap
- 正式 Evidence Level 与 Safety 状态

你不得：
- 把用户的问题当成事实
- 把 AI 回答当成 Evidence
- 创造不存在的实验结果 / chunk_id / 文档
- 假设企业已经做过某项验证
- 把不同条件下的 Evidence 直接视为冲突（Condition Gap 不是 Conflict）
- 自动批准知识进入正式知识库

判断顺序建议：
1. 现有知识是否已充分覆盖问题且无新增治理价值 -> NO_UPDATE
2. 是否属于已有知识主题但出现新角度/适用条件 -> EXISTING_TOPIC_EXTENSION
3. 是否已有相关知识但缺当前问题所需的直接 Evidence -> EVIDENCE_GAP
4. 是否几乎没有合理相关的 Existing Knowledge -> NEW_TOPIC
5. 是否有同条件/高度可比条件下的明确冲突 Evidence -> KNOWLEDGE_CONFLICT
6. NEW_EVIDENCE：当前 trusted_user_evidence_present=false，禁止输出。

硬约束：
- related_existing_refs 只能引用本轮 retrieved_knowledge 里真实存在的 chunk_id。
- target_hint.related_source_refs 只能引用本轮 retrieved_knowledge 里真实存在的 chunk_id。
- conflict_refs 只能引用本轮 retrieved_knowledge 里真实存在的 chunk_id。
- 不得创造任何不存在的 chunk_id。
- target_hint / suggested_note_title 只是给 Y 侧 Master KB 的入库建议标题，
  不是文件路径，不得生成任何本地 / Obsidian 路径。
- Master KB 位于 Y 侧外部，W 侧不写 Master KB、不自动入库。
- safety_boundary 必须严格为：
  user_question_is_evidence=false,
  llm_answer_is_approved_evidence=false,
  auto_write_master_kb=false,
  auto_reindex=false,
  human_review_required=true

只输出 JSON Object，不要 Markdown：

{
  "curator_version": "0.2",
  "decision_type": "NO_UPDATE|EXISTING_TOPIC_EXTENSION|EVIDENCE_GAP|NEW_TOPIC|KNOWLEDGE_CONFLICT|NEW_EVIDENCE",
  "should_create_candidate": true,
  "confidence": "LOW|MEDIUM|HIGH",
  "decision_reason": "...",
  "relationship_to_existing_knowledge": "...",
  "related_existing_refs": ["CK-..."],
  "knowledge_gap_summary": "...",
  "recommended_kb_action": "NO_WRITE|EXTEND_EXISTING|REQUEST_NEW_EVIDENCE|CREATE_NEW_TOPIC|REVIEW_CONFLICT",
  "target_hint": {
    "target_mode": "EXISTING_SOURCE|NEW_TOPIC|REVIEW_QUEUE",
    "related_source_refs": ["CK-..."],
    "knowledge_domain": "REQUIREMENT|CASE|STANDARD|LITERATURE|PROJECT|GENERAL_RND_KNOWLEDGE|UNKNOWN",
    "suggested_topic": "...",
    "suggested_note_title": "..."
  },
  "evidence_needed": ["..."],
  "conflict_refs": ["CK-..."],
  "safety_boundary": {
    "user_question_is_evidence": false,
    "llm_answer_is_approved_evidence": false,
    "auto_write_master_kb": false,
    "auto_reindex": false,
    "human_review_required": true
  }
}
"""


# ============================================================
# 4. Deterministic Curator Guard
# ============================================================

def guard_curator_decision(
    decision,
    retrieved_chunk_ids,
):
    """
    确定性 Guard：LLM 没有最终决定权。

    返回 (decision, guard_status, changes)
    guard_status:
      - "PASS"               : 合法，无修正
      - "PASS_WITH_FIXES"    : 合法，但已做确定性修正（清除非法引用/强制安全边界）
      - "CURATOR_GUARD_HOLD" : 非法，不生成 Candidate
    """
    if not isinstance(decision, dict):
        return None, "CURATOR_GUARD_HOLD", ["INVALID_DECISION_OBJECT"]

    decision = deepcopy(decision)

    changes = []

    retrieved = set(
        str(x)
        for x in (
            retrieved_chunk_ids
            or []
        )
        if x
    )

    # 1. decision_type 必须属于正式 enum
    decision_type = decision.get("decision_type")

    if decision_type not in DECISION_TYPES:
        changes.append(
            "INVALID_DECISION_TYPE:"
            + repr(decision_type)
        )

        return decision, "CURATOR_GUARD_HOLD", changes

    # 5. NEW_EVIDENCE 当前禁止（trusted_user_evidence_present=false）
    if decision_type == "NEW_EVIDENCE":
        changes.append("NEW_EVIDENCE_FORBIDDEN")

        return decision, "CURATOR_GUARD_HOLD", changes

    # 2/3/4. 引用只能来自本轮 retrieved chunk ids（不得创造 chunk_id）
    def _filter_refs(value, label):
        values = value or []

        if not isinstance(values, list):
            values = [values]

        legal = []
        illegal = []

        for ref in values:
            ref = str(ref)

            if ref in retrieved:
                if ref not in legal:
                    legal.append(ref)

            else:
                illegal.append(ref)

        if illegal:
            changes.append(
                "REMOVED_ILLEGAL_"
                + label
                + ":"
                + repr(illegal)
            )

        return legal

    decision["related_existing_refs"] = _filter_refs(
        decision.get("related_existing_refs"),
        "RELATED_REFS",
    )

    target_hint = decision.get("target_hint")

    if not isinstance(target_hint, dict):
        target_hint = {}

    target_hint["related_source_refs"] = _filter_refs(
        target_hint.get("related_source_refs"),
        "TARGET_REFS",
    )

    decision["target_hint"] = target_hint

    decision["conflict_refs"] = _filter_refs(
        decision.get("conflict_refs"),
        "CONFLICT_REFS",
    )

    # 6. safety_boundary 必须强制为安全值
    raw_boundary = decision.get("safety_boundary")

    boundary_is_safe = (
        isinstance(raw_boundary, dict)
        and all(
            raw_boundary.get(key) == value
            for key, value in SAFETY_BOUNDARY.items()
        )
    )

    decision["safety_boundary"] = deepcopy(SAFETY_BOUNDARY)

    if not boundary_is_safe:
        changes.append("SAFETY_BOUNDARY_FORCED_TO_SAFE")

    guard_status = (
        "PASS_WITH_FIXES"
        if changes
        else "PASS"
    )

    return decision, guard_status, changes


# ============================================================
# 5. Query Trace
# ============================================================

def build_query_trace(
    result,
    decision=None,
    candidate=None,
    curator_status=None,
):
    structured = (
        result.get("structured_output")
        or {}
    )

    safety = (
        result.get("safety")
        or {}
    )

    evidence = (
        result.get("evidence")
        or []
    )

    gap = structured.get("evidence_gap")

    if not isinstance(gap, dict):
        gap = {}

    gap_statement = gap.get("statement")
    gap_refs = gap.get("source_refs") or []

    gap_present = bool(
        gap_statement
        and str(gap_statement).strip()
    )

    return {
        "trace_id":
            "QT-" + uuid4().hex,

        "created_at":
            _now_iso(),

        "query":
            result.get("query"),

        "mode":
            "LIVE",

        "retrieved_chunk_ids":
            _retrieved_ids(result),

        "safety_status":
            safety.get("status"),

        "citation_status":
            safety.get("citation_correctness"),

        "unsupported_claim_count":
            safety.get("unsupported_claim_count"),

        "evidence_gap_present":
            gap_present,

        "evidence_gap_statement":
            gap_statement,

        "evidence_gap_source_refs":
            gap_refs,

        "curator_status":
            curator_status,

        "curator_decision_type":
            (
                decision.get("decision_type")
                if isinstance(decision, dict)
                else None
            ),

        "candidate_generated":
            bool(candidate),

        "candidate_id":
            (
                candidate.get("candidate_id")
                if isinstance(candidate, dict)
                else None
            ),
    }


# ============================================================
# 6. Knowledge Update Candidate
# ============================================================

def build_candidate(
    decision,
    trace,
    query,
):
    related_refs = (
        decision.get("related_existing_refs")
        or []
    )

    conflict_refs = (
        decision.get("conflict_refs")
        or []
    )

    gap_refs = (
        trace.get("evidence_gap_source_refs")
        or []
    )

    if related_refs or conflict_refs or gap_refs:
        traceability_status = "TRACEABLE"

    else:
        traceability_status = "UNTRACEABLE"

    return {
        "candidate_id":
            "KC-" + uuid4().hex,

        "candidate_key":
            compute_candidate_key(
                decision.get("decision_type"),
                query,
                related_refs,
                decision.get("knowledge_gap_summary"),
            ),

        "trace_id":
            trace.get("trace_id"),

        "created_at":
            trace.get("created_at"),

        "curator_version":
            CURATOR_VERSION,

        "decision_type":
            decision.get("decision_type"),

        "query":
            query,

        "decision_reason":
            decision.get("decision_reason"),

        "relationship_to_existing_knowledge":
            decision.get("relationship_to_existing_knowledge"),

        "related_existing_refs":
            related_refs,

        "knowledge_gap_summary":
            decision.get("knowledge_gap_summary"),

        "recommended_kb_action":
            decision.get("recommended_kb_action"),

        "target_hint":
            decision.get("target_hint"),

        "evidence_needed":
            decision.get("evidence_needed")
            or [],

        "conflict_refs":
            conflict_refs,

        "review_status":
            REVIEW_STATUS,

        "approved_for_master_kb":
            False,

        "master_kb_write_allowed":
            False,

        "knowledge_claim_status":
            KNOWLEDGE_CLAIM_STATUS,

        "traceability_status":
            traceability_status,

        "review_note":
            REVIEW_NOTE,
    }


# ============================================================
# 7. LLM client (懒加载，复用现有环境配置)
# ============================================================

def _build_client_from_env():
    """复用现有 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL。
    不打印、不复制 API Key。"""
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv()

    import os

    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL")

    if not api_key:
        raise RuntimeError("LLM_API_KEY_NOT_FOUND")

    if not base_url:
        raise RuntimeError("LLM_BASE_URL_NOT_FOUND")

    if not model:
        raise RuntimeError("LLM_MODEL_NOT_FOUND")

    return OpenAI(
        api_key=api_key,
        base_url=base_url,
    ), model


def _build_client_from_config(config):
    """用 RuntimeLLMConfig 构建 OpenAI-compatible client。
    不读 env、不写 env。"""
    from openai import OpenAI

    if not config.api_key:
        raise RuntimeError("LLM_API_KEY_NOT_FOUND")

    if not config.base_url:
        raise RuntimeError("LLM_BASE_URL_NOT_FOUND")

    if not config.model:
        raise RuntimeError("LLM_MODEL_NOT_FOUND")

    return OpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
    ), config.model


def _call_curator_llm(
    curator_input,
    client,
    model,
):
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={
            "type": "json_object"
        },
        messages=[
            {
                "role": "system",
                "content": CURATOR_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": json.dumps(
                    curator_input,
                    ensure_ascii=False,
                    indent=2,
                ),
            },
        ],
    )

    return response.choices[0].message.content


def _obtain_decision(
    result,
    curator_response,
    llm_client,
    model,
    runtime_config=None,
):
    """
    获取 Curator decision dict。
    优先使用注入的 curator_response（离线测试用），
    其次使用传入 runtime_config，否则使用环境配置。
    """
    if curator_response is not None:
        if isinstance(curator_response, dict):
            return deepcopy(curator_response)

        return json.loads(str(curator_response))

    if llm_client is None or model is None:
        if runtime_config is not None:
            llm_client, model = _build_client_from_config(
                runtime_config
            )

        else:
            llm_client, model = _build_client_from_env()

    curator_input = build_curator_input(result)

    raw = _call_curator_llm(
        curator_input,
        llm_client,
        model,
    )

    return json.loads(raw)


# ============================================================
# 8. Main entry
# ============================================================

def run_knowledge_curator(
    result,
    base_dir=None,
    curator_response=None,
    llm_client=None,
    model=None,
    runtime_config=None,
):
    """
    知识治理链主入口。

    - 绝不抛异常：Curator 是附加链，任何失败都被隔离。
    - 总是（尽力）写入一条 Query Trace。
    - 仅当 Guard 通过且 decision_type != NO_UPDATE 时写入 Candidate。

    返回 dict：
      status, curator_status, guard_status, decision, candidate, trace, error
    """
    base_dir = (
        Path(base_dir)
        if base_dir is not None
        else DEFAULT_FEEDBACK_DIR
    )

    base_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    decision = None
    guard_status = None
    changes = []
    error = None

    # --- Step 1: obtain decision (LLM or mock) ---
    try:
        decision = _obtain_decision(
            result,
            curator_response,
            llm_client,
            model,
            runtime_config,
        )

    except Exception as exc:
        error = repr(exc)

    # --- Step 2: deterministic guard ---
    if decision is not None:
        decision, guard_status, changes = guard_curator_decision(
            decision,
            _retrieved_ids(result),
        )

        if guard_status == "CURATOR_GUARD_HOLD":
            decision = None

    # --- Step 3: curator status string ---
    if error is not None:
        curator_status = "CURATOR_UNAVAILABLE"

    elif guard_status == "CURATOR_GUARD_HOLD":
        curator_status = "GUARD_HOLD"

    elif guard_status == "PASS_WITH_FIXES":
        curator_status = "GUARD_PASS_WITH_FIXES"

    else:
        curator_status = "GUARD_PASS"

    # --- Step 4: build trace (always) ---
    trace = build_query_trace(
        result,
        decision=decision,
        candidate=None,
        curator_status=curator_status,
    )

    # --- Step 5: build candidate (guard passed & not NO_UPDATE) ---
    candidate = None

    if (
        decision is not None
        and decision.get("decision_type") != "NO_UPDATE"
    ):
        candidate = build_candidate(
            decision,
            trace,
            result.get("query"),
        )

        trace["candidate_generated"] = True
        trace["candidate_id"] = candidate["candidate_id"]
        trace["curator_decision_type"] = candidate["decision_type"]

    # --- Step 6: persist (best effort, isolated) ---
    try:
        _append_jsonl(
            base_dir / TRACES_FILENAME,
            trace,
        )

    except Exception as exc:
        if error is None:
            error = repr(exc)

    if candidate is not None:
        try:
            _append_jsonl(
                base_dir / CANDIDATES_FILENAME,
                candidate,
            )

        except Exception as exc:
            if error is None:
                error = repr(exc)

    # --- Step 7: status ---
    if error is not None:
        status = "CURATOR_UNAVAILABLE"

    elif decision is None:
        status = "GUARD_HOLD"

    elif candidate is not None:
        status = "CANDIDATE"

    else:
        status = "NO_UPDATE"

    return {
        "status": status,
        "curator_status": curator_status,
        "guard_status": guard_status,
        "guard_changes": changes,
        "decision": decision,
        "candidate": candidate,
        "trace": trace,
        "error": error,
    }

# -*- coding: utf-8 -*-
"""
Knowledge Review Workflow V0.3（人工审核状态机 + append-only 审计）

职责：
  - 读取 Candidate / 校验 / 严格状态转换
  - 生成 Review Decision
  - APPROVE 时生成 Approved Derived Knowledge Record
  - append-only 写 audit JSONL

知识架构边界（永久）：
  - APPROVED_FOR_KB 只代表"人工审核通过，具备未来进入 Derived Knowledge /
    Future Runtime Snapshot 的资格"。
  - 不代表：已写入企业 Truth Source / 已进入当前 Runtime Corpus /
    已进入 Qdrant / 已成为正式 Evidence。

治理规则：
  USER_QUESTION_IS_EVIDENCE = NO
  LLM_ANSWER_IS_APPROVED_EVIDENCE = NO
  AUTO_WRITE_TRUTH_SOURCE = NO
  AUTO_APPROVE_KNOWLEDGE = NO
  AUTO_REINDEX = NO
  APPROVED_FOR_KB_IS_EVIDENCE = NO
  APPROVED_FOR_KB_IS_CURRENT_RUNTIME_SOURCE = NO
  APPROVED_FOR_KB_REQUIRES_FUTURE_SNAPSHOT_GATE = YES
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_FEEDBACK_DIR = (
    MODULE_DIR.parent / "outputs" / "knowledge_feedback"
)

REVIEW_DECISIONS_FILE = "review_decisions.jsonl"
APPROVED_KNOWLEDGE_FILE = "approved_derived_knowledge.jsonl"

VALID_DECISIONS = {
    "APPROVE",
    "NEED_MORE_EVIDENCE",
    "REJECT",
}

DECISION_TO_STATUS = {
    "APPROVE": "APPROVED_FOR_KB",
    "NEED_MORE_EVIDENCE": "NEED_MORE_EVIDENCE",
    "REJECT": "REJECTED",
}

# Candidate decision_type -> Derived Knowledge type（§十）
KNOWLEDGE_TYPE_MAP = {
    "EVIDENCE_GAP": "EVIDENCE_GAP",
    "EXISTING_TOPIC_EXTENSION": "DERIVED_TOPIC_EXTENSION",
    "NEW_TOPIC": "DERIVED_NEW_TOPIC",
    "KNOWLEDGE_CONFLICT": "KNOWLEDGE_CONFLICT_RECORD",
    # NEW_EVIDENCE 由 Curator Guard 拦截，不进入 Review。
}

FINAL_STATUSES = {
    "APPROVED_FOR_KB",
    "NEED_MORE_EVIDENCE",
    "REJECTED",
}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(obj, ensure_ascii=False) + "\n"
        )


def _load_jsonl(path):
    path = Path(path)

    if not path.exists():
        return []

    rows = []

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()

            if line:
                rows.append(json.loads(line))

    return rows


def get_review_status(candidate_id, base_dir=None):
    """
    从 review_decisions.jsonl 派生当前审核状态。
    未审核 -> "PENDING_REVIEW"。
    """
    base_dir = (
        Path(base_dir)
        if base_dir is not None
        else DEFAULT_FEEDBACK_DIR
    )

    records = _load_jsonl(
        base_dir / REVIEW_DECISIONS_FILE
    )

    for record in reversed(records):
        if record.get("candidate_id") == candidate_id:
            return record.get("new_status")

    return "PENDING_REVIEW"


def review_candidate(
    candidate,
    decision,
    reviewer="",
    review_comment="",
    base_dir=None,
):
    """
    严格状态转换 + append-only 写盘。

    返回 dict：
      result_status: REVIEWED | ALREADY_REVIEWED | INVALID_CANDIDATE | INVALID_DECISION
      review_decision: dict | None
      approved_record: dict | None（仅 APPROVE 成功时）
    """
    base_dir = (
        Path(base_dir)
        if base_dir is not None
        else DEFAULT_FEEDBACK_DIR
    )

    # ---- validate candidate ----
    if not isinstance(candidate, dict):
        return {
            "result_status": "INVALID_CANDIDATE",
            "review_decision": None,
            "approved_record": None,
        }

    candidate_id = candidate.get("candidate_id")
    candidate_key = candidate.get("candidate_key")
    trace_id = candidate.get("trace_id")

    if not candidate_id or not candidate_key:
        return {
            "result_status": "INVALID_CANDIDATE",
            "review_decision": None,
            "approved_record": None,
        }

    # ---- validate decision ----
    if decision not in VALID_DECISIONS:
        return {
            "result_status": "INVALID_DECISION",
            "review_decision": None,
            "approved_record": None,
        }

    # ---- duplicate guard（最终态不可再改，不可重复 append）----
    if get_review_status(candidate_id, base_dir) != "PENDING_REVIEW":
        return {
            "result_status": "ALREADY_REVIEWED",
            "review_decision": None,
            "approved_record": None,
        }

    new_status = DECISION_TO_STATUS[decision]
    review_id = "KR-" + uuid4().hex
    reviewed_at = _now_iso()

    source_refs = list(
        candidate.get("related_existing_refs") or []
    )

    review_decision = {
        "review_id": review_id,
        "candidate_id": candidate_id,
        "candidate_key": candidate_key,
        "trace_id": trace_id,
        "decision": decision,
        "previous_status": "PENDING_REVIEW",
        "new_status": new_status,
        "reviewer": reviewer or "",
        "review_comment": review_comment or "",
        "reviewed_at": reviewed_at,
        "candidate_decision_type": candidate.get("decision_type"),
        "source_refs": source_refs,
        "do_not_ingest_current_runtime": True,
        "auto_reindex": False,
    }

    approved_record = None

    if decision == "APPROVE":
        candidate_decision_type = candidate.get("decision_type")

        knowledge_type = KNOWLEDGE_TYPE_MAP.get(
            candidate_decision_type,
            "DERIVED_KNOWLEDGE",
        )

        target_hint = candidate.get("target_hint") or {}

        approved_record = {
            "knowledge_record_id": "AK-" + uuid4().hex,
            "candidate_id": candidate_id,
            "candidate_key": candidate_key,
            "trace_id": trace_id,
            "review_id": review_id,
            "status": "APPROVED_FOR_KB",
            "knowledge_type": knowledge_type,
            "candidate_decision_type": candidate_decision_type,
            "topic": target_hint.get("suggested_topic"),
            "summary": candidate.get("knowledge_gap_summary"),
            "recommended_action": candidate.get("recommended_kb_action"),
            "source_refs": source_refs,
            "reviewer": reviewer or "",
            "review_comment": review_comment or "",
            "approved_at": reviewed_at,
            "provenance": {
                "candidate_id": candidate_id,
                "candidate_key": candidate_key,
                "trace_id": trace_id,
                "review_id": review_id,
                "derived_from": "knowledge_update_candidate",
                "source_type": "derived_governance_artifact",
            },
            "governance_flags": {
                "approved_as_evidence": False,
                "truth_source_write": False,
                "do_not_ingest_current_runtime": True,
                "future_snapshot_gate_required": True,
                "auto_reindex": False,
            },
        }

    # ---- append-only 写盘 ----
    _append_jsonl(
        base_dir / REVIEW_DECISIONS_FILE,
        review_decision,
    )

    if approved_record is not None:
        _append_jsonl(
            base_dir / APPROVED_KNOWLEDGE_FILE,
            approved_record,
        )

    return {
        "result_status": "REVIEWED",
        "review_decision": review_decision,
        "approved_record": approved_record,
    }

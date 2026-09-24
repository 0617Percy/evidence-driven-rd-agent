# -*- coding: utf-8 -*-
"""
Knowledge History & Operations V0.5（历史聚合 + 治理状态解析）

职责（READ / AGGREGATE / CONTINUE LEGAL WORKFLOW，绝不 EDIT HISTORY）：
  - 读取历史治理日志（query_traces / candidates / review_decisions /
    approved_derived_knowledge / knowledge_write_decisions / Vault Manifest）
  - 按可追溯字段（trace_id / candidate_id / candidate_key / review_id /
    knowledge_record_id / write_id）建立关联
  - 聚合 History Record
  - 计算 Current Governance Status（最远已完成节点）
  - 计算 Allowed Operation
  - 搜索 / 筛选 / 排序

治理原则：
  - append-only / traceable / immutable finalized decisions
  - 不修改任何源 JSONL / Candidate / Review / Write / AK 文件
"""

import json
from pathlib import Path

from knowledge_correction_v0_7 import (
    get_candidate_correction_intents,
    get_legacy_correction_status,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_FEEDBACK_DIR = (
    PROJECT_ROOT / "outputs" / "knowledge_feedback"
)

DEFAULT_VAULT_ROOT = (
    PROJECT_ROOT / "data" / "knowledge_vault" / "AUTO001_Y_V2"
)


# Current Governance Status（最远已完成节点）
STATUS_TRACE_ONLY = "TRACE_ONLY"
STATUS_PENDING_REVIEW = "PENDING_REVIEW"
STATUS_APPROVED_FOR_KB = "APPROVED_FOR_KB"
STATUS_NEED_MORE_EVIDENCE = "NEED_MORE_EVIDENCE"
STATUS_REJECTED = "REJECTED"
STATUS_WRITTEN = "WRITTEN_TO_DERIVED_KB"


# Allowed Operation
OP_VIEW_ONLY = "VIEW_ONLY"
OP_HUMAN_REVIEW = "HUMAN_REVIEW"
OP_KNOWLEDGE_WRITE = "KNOWLEDGE_WRITE"
OP_VIEW_KNOWLEDGE_RECORD = "VIEW_KNOWLEDGE_RECORD"


OPERATION_MAP = {
    STATUS_TRACE_ONLY: OP_VIEW_ONLY,
    STATUS_PENDING_REVIEW: OP_HUMAN_REVIEW,
    STATUS_APPROVED_FOR_KB: OP_KNOWLEDGE_WRITE,
    STATUS_NEED_MORE_EVIDENCE: OP_VIEW_ONLY,
    STATUS_REJECTED: OP_VIEW_ONLY,
    STATUS_WRITTEN: OP_VIEW_KNOWLEDGE_RECORD,
}


DISPLAY_LABEL_MAP = {
    STATUS_TRACE_ONLY: None,
    STATUS_PENDING_REVIEW: "待人工审核",
    STATUS_APPROVED_FOR_KB: "已批准｜待知识写入",
    STATUS_NEED_MORE_EVIDENCE: "需要补证",
    STATUS_REJECTED: "已拒绝",
    STATUS_WRITTEN: "已写入 Derived Knowledge",
}


def _load_jsonl_safe(path):
    """读取 JSONL，跳过坏行，文件不存在返回空列表。绝不抛异常。"""
    path = Path(path)

    if not path.exists():
        return []

    rows = []

    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()

                if not line:
                    continue

                try:
                    rows.append(json.loads(line))

                except Exception:
                    # 坏行隔离：跳过，不让整个历史页崩
                    continue

    except Exception:
        return []

    return rows


def resolve_governance_status(candidate, review, write):
    """
    纯函数：按"最远已完成节点"解析 Current Governance Status。
    优先级：Write > Review > Candidate > Trace。
    绝不依据 Candidate 原始 review_status 单独判定。
    """
    if write and write.get("new_status") == STATUS_WRITTEN:
        return STATUS_WRITTEN

    if review and review.get("new_status"):
        return review["new_status"]

    if candidate:
        return STATUS_PENDING_REVIEW

    return STATUS_TRACE_ONLY


def allowed_operation(status):
    return OPERATION_MAP.get(status, OP_VIEW_ONLY)


def status_display_label(status):
    return DISPLAY_LABEL_MAP.get(status)


def _build_record(trace, candidate, review, approved_rec, write, status):
    target_hint = (candidate.get("target_hint") or {}) if candidate else {}

    return {
        "trace_id": trace.get("trace_id"),
        "query": trace.get("query"),
        "queried_at": trace.get("created_at"),
        "answer_summary": trace.get("evidence_gap_statement"),
        "candidate_id": candidate.get("candidate_id") if candidate else None,
        "candidate_key": candidate.get("candidate_key") if candidate else None,
        "candidate_decision_type": candidate.get("decision_type") if candidate else None,
        "candidate_status_original": candidate.get("review_status") if candidate else None,
        "candidate_topic": target_hint.get("suggested_topic"),
        "candidate_summary": candidate.get("knowledge_gap_summary") if candidate else None,
        "source_refs": candidate.get("related_existing_refs") if candidate else [],
        "review_id": review.get("review_id") if review else None,
        "review_decision": review.get("decision") if review else None,
        "review_status": review.get("new_status") if review else None,
        "reviewer": review.get("reviewer") if review else None,
        "review_comment": review.get("review_comment") if review else None,
        "reviewed_at": review.get("reviewed_at") if review else None,
        "knowledge_record_id": approved_rec.get("knowledge_record_id") if approved_rec else None,
        "write_id": write.get("write_id") if write else None,
        "write_status": write.get("new_status") if write else None,
        "write_reviewer_role": write.get("reviewer_role") if write else None,
        "write_reviewer_name": write.get("reviewer_name") if write else None,
        "write_comment": write.get("write_comment") if write else None,
        "written_at": write.get("written_at") if write else None,
        "vault_relative_path": write.get("vault_relative_path") if write else None,
        "current_governance_status": status,
        "allowed_operation": allowed_operation(status),
    }


def load_history(feedback_dir=None, vault_root=None):
    """聚合完整历史记录，按 queried_at 倒序返回。"""
    feedback_dir = (
        Path(feedback_dir)
        if feedback_dir is not None
        else DEFAULT_FEEDBACK_DIR
    )

    traces = _load_jsonl_safe(feedback_dir / "query_traces.jsonl")
    candidates = _load_jsonl_safe(feedback_dir / "kb_update_candidates.jsonl")
    reviews = _load_jsonl_safe(feedback_dir / "review_decisions.jsonl")
    approved = _load_jsonl_safe(feedback_dir / "approved_derived_knowledge.jsonl")
    writes = _load_jsonl_safe(feedback_dir / "knowledge_write_decisions.jsonl")
    intents = _load_jsonl_safe(
        feedback_dir / "knowledge_correction_intents.jsonl"
    )
    relations = _load_jsonl_safe(
        feedback_dir / "knowledge_supersession_relations.jsonl"
    )

    candidate_by_trace = {}
    for c in candidates:
        tid = c.get("trace_id")
        if tid:
            candidate_by_trace[tid] = c

    review_by_candidate = {}
    for r in reviews:
        cid = r.get("candidate_id")
        if cid:
            review_by_candidate[cid] = r

    approved_by_candidate = {}
    for a in approved:
        cid = a.get("candidate_id")
        if cid:
            approved_by_candidate[cid] = a

    write_by_candidate = {}
    for w in writes:
        cid = w.get("candidate_id")
        if cid:
            write_by_candidate[cid] = w

    records = []

    for trace in traces:
        tid = trace.get("trace_id")
        candidate = candidate_by_trace.get(tid)
        cid = candidate.get("candidate_id") if candidate else None
        review = review_by_candidate.get(cid) if cid else None
        approved_rec = approved_by_candidate.get(cid) if cid else None
        write = write_by_candidate.get(cid) if cid else None

        status = resolve_governance_status(candidate, review, write)

        record = _build_record(
            trace,
            candidate,
            review,
            approved_rec,
            write,
            status,
        )

        # ---- Correction / Supersession 治理关系（只读派生，不修改历史）----
        record["correction_intent_id"] = None
        record["corrects_legacy_ak"] = []
        record["correction_status"] = None
        record["correction_new_ak"] = None

        if cid:
            cintents = get_candidate_correction_intents(cid, intents)

            if cintents:
                record["correction_intent_id"] = cintents[0].get(
                    "correction_intent_id"
                )
                record["corrects_legacy_ak"] = [
                    it.get("legacy_knowledge_record_id")
                    for it in cintents
                ]

        rid = record.get("knowledge_record_id")

        if rid:
            cstatus = get_legacy_correction_status(rid, intents, relations)

            if cstatus:
                record["correction_status"] = cstatus.get("status")
                record["correction_new_ak"] = cstatus.get(
                    "new_knowledge_record_id"
                )

        records.append(record)

    records.sort(
        key=lambda r: r.get("queried_at") or "",
        reverse=True,
    )

    return records


def get_current_governance_status(candidate_id, feedback_dir=None):
    """根据 Review + Write 派生某 candidate 的当前治理状态。"""
    feedback_dir = (
        Path(feedback_dir)
        if feedback_dir is not None
        else DEFAULT_FEEDBACK_DIR
    )

    candidates = _load_jsonl_safe(feedback_dir / "kb_update_candidates.jsonl")
    reviews = _load_jsonl_safe(feedback_dir / "review_decisions.jsonl")
    writes = _load_jsonl_safe(feedback_dir / "knowledge_write_decisions.jsonl")

    candidate = next(
        (c for c in reversed(candidates) if c.get("candidate_id") == candidate_id),
        None,
    )

    review = next(
        (r for r in reversed(reviews) if r.get("candidate_id") == candidate_id),
        None,
    )

    write = next(
        (w for w in reversed(writes) if w.get("candidate_id") == candidate_id),
        None,
    )

    return resolve_governance_status(candidate, review, write)


def get_candidate(candidate_id, feedback_dir=None):
    """按 candidate_id 读取完整 Candidate（供复用 Review / Write UI）。"""
    feedback_dir = (
        Path(feedback_dir)
        if feedback_dir is not None
        else DEFAULT_FEEDBACK_DIR
    )

    candidates = _load_jsonl_safe(
        feedback_dir / "kb_update_candidates.jsonl"
    )

    return next(
        (
            c
            for c in reversed(candidates)
            if c.get("candidate_id") == candidate_id
        ),
        None,
    )


def search_history(records, text):
    """按 Query / Topic / Candidate ID / Knowledge Record ID 搜索（大小写不敏感）。"""
    text = (text or "").strip().lower()

    if not text:
        return records

    out = []

    for r in records:
        hay = " ".join([
            str(r.get("query") or ""),
            str(r.get("candidate_topic") or ""),
            str(r.get("candidate_id") or ""),
            str(r.get("knowledge_record_id") or ""),
        ]).lower()

        if text in hay:
            out.append(r)

    return out


def filter_history(records, status=None, decision_type=None):
    """按 Current Governance Status 与 Decision Type 筛选。"""
    out = records

    if status and status != "全部":
        out = [r for r in out if r.get("current_governance_status") == status]

    if decision_type and decision_type != "全部":
        out = [r for r in out if r.get("candidate_decision_type") == decision_type]

    return out

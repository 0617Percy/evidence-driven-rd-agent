# -*- coding: utf-8 -*-
"""
Knowledge Writeback V0.4（Governed Derived Knowledge Writeback）

职责：
  - 从 Y V2 ZIP 初始化受控 Knowledge Vault Workspace
  - 校验 Knowledge Write Gate（第二道人工作业）
  - 生成 Derived Knowledge Markdown（05_已审核派生知识/）
  - append Manifest + Write Decision
  - duplicate protection + 路径 traversal 防护
  - atomic-ish safe write

知识架构边界（永久）：
  - 01_原始资料/ = Enterprise Truth Source = READ_ONLY
  - 05_已审核派生知识/ = Governed Derived Knowledge（非 Truth Source / 非当前 Runtime / 非 Gold / 非 Qdrant）
  - 写入 05 不自动成为 E1 / 不进入 RC1 / 不进入 Qdrant
  - 统一称 "Governed Knowledge Vault / 已审核派生知识 / Derived Knowledge"，禁用 "Master KB"

Knowledge Write Gate：
  - candidate 已 APPROVED_FOR_KB
  - reviewer_role ∈ {Y, R&D_ENGINEER}
  - reviewer_name 非空
  - evidence_confirmation = true
  - 无既有 writeback
  - Vault 存在且 05 可写
"""

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_VAULT_ROOT = (
    PROJECT_ROOT / "data" / "knowledge_vault" / "AUTO001_Y_V2"
)

DEFAULT_FEEDBACK_DIR = (
    PROJECT_ROOT / "outputs" / "knowledge_feedback"
)

DERIVED_DIR_NAME = "05_已审核派生知识"
AUTO001_DIR_NAME = "AUTO-001"
MANIFEST_FILENAME = "00_Approved_Knowledge_Manifest.jsonl"
README_FILENAME = "00_README.md"

WRITE_DECISIONS_FILE = "knowledge_write_decisions.jsonl"

ALLOWED_REVIEWER_ROLES = {"Y", "R&D_ENGINEER"}

# ZIP 顶层包装目录名（解压时剥掉，使 Vault 根直接含 01_原始资料 等）
ZIP_WRAPPER = "AUTO001_KB_Sync_20260830_V2"

README_CONTENT = """# 已审核派生知识

本目录用于存放经过人工审核并通过 Knowledge Write Gate 的 Derived Knowledge。

本目录：

- 不是企业原始事实真源；
- 不替代 `01_原始资料`；
- 不自动进入当前 RAG Runtime；
- 不自动触发 Qdrant re-index；
- 仅作为未来 Runtime Snapshot Source Candidate；
- 纳入 Future Snapshot 前仍需 Human Gate。

不得修改：

`01_原始资料`。
"""


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _is_safe_id(value):
    if value is None:
        return False

    s = str(value)

    if any(c in s for c in ["/", "\\", "..", ":", "\x00"]):
        return False

    return bool(s.strip())


def _append_jsonl(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(obj, ensure_ascii=False) + "\n")


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


# ============================================================
# Vault 初始化
# ============================================================

def initialize_vault_from_zip(zip_path, vault_root=None):
    """
    从 Y V2 ZIP 初始化受控 Knowledge Vault（首次运行时）。
    剥掉 ZIP 顶层包装目录，保留内部目录结构。
    01_原始资料/ 继续视为 READ_ONLY_TRUTH_SOURCE。
    """
    vault_root = (
        Path(vault_root)
        if vault_root is not None
        else DEFAULT_VAULT_ROOT
    )

    zip_path = Path(zip_path)

    vault_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            target = member

            if target.startswith(ZIP_WRAPPER + "/"):
                target = target[len(ZIP_WRAPPER) + 1:]

            if not target:
                continue

            dest = vault_root / target

            if member.endswith("/"):
                dest.mkdir(parents=True, exist_ok=True)
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)

            with zf.open(member) as src, dest.open("wb") as out:
                out.write(src.read())

    return vault_root


def resolve_vault(vault_root=None):
    vault_root = (
        Path(vault_root)
        if vault_root is not None
        else DEFAULT_VAULT_ROOT
    )

    return vault_root


def truth_source_hash_tree(vault_root=None):
    """
    计算 01_原始资料/ 下所有文件的 SHA256 tree（用于与 ZIP 内容一致性验证）。
    返回 {relative_path: sha256}。
    """
    vault_root = resolve_vault(vault_root)
    truth_root = vault_root / "01_原始资料"

    result = {}

    if not truth_root.exists():
        return result

    import hashlib

    for p in sorted(truth_root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(vault_root).as_posix()
            result[rel] = hashlib.sha256(p.read_bytes()).hexdigest()

    return result


def zip_truth_source_hash_tree(zip_path):
    """从 ZIP 内计算 01_原始资料/ 的 SHA256 tree（不落盘，只读）。"""
    import hashlib

    result = {}

    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            target = member

            if target.startswith(ZIP_WRAPPER + "/"):
                target = target[len(ZIP_WRAPPER) + 1:]

            if not target.startswith("01_原始资料/"):
                continue

            if member.endswith("/"):
                continue

            data = zf.read(member)
            result[target] = hashlib.sha256(data).hexdigest()

    return result


# ============================================================
# Write Gate
# ============================================================

def get_approved_record(candidate_id, feedback_dir=None):
    feedback_dir = (
        Path(feedback_dir)
        if feedback_dir is not None
        else DEFAULT_FEEDBACK_DIR
    )

    rows = _load_jsonl(
        feedback_dir / "approved_derived_knowledge.jsonl"
    )

    for row in reversed(rows):
        if row.get("candidate_id") == candidate_id:
            return row

    return None


def get_write_status(candidate_id, feedback_dir=None):
    feedback_dir = (
        Path(feedback_dir)
        if feedback_dir is not None
        else DEFAULT_FEEDBACK_DIR
    )

    rows = _load_jsonl(
        feedback_dir / WRITE_DECISIONS_FILE
    )

    for row in reversed(rows):
        if row.get("candidate_id") == candidate_id:
            return row.get("new_status")

    return None


def get_write_decision(candidate_id, feedback_dir=None):
    feedback_dir = (
        Path(feedback_dir)
        if feedback_dir is not None
        else DEFAULT_FEEDBACK_DIR
    )

    rows = _load_jsonl(
        feedback_dir / WRITE_DECISIONS_FILE
    )

    for row in reversed(rows):
        if row.get("candidate_id") == candidate_id:
            return row

    return None


def write_approved_knowledge(
    approved_record,
    reviewer_role,
    reviewer_name,
    evidence_confirmed,
    write_comment="",
    vault_root=None,
    feedback_dir=None,
):
    """
    Knowledge Write Gate。

    返回 dict：
      result_status: WRITTEN_TO_DERIVED_KB | ALREADY_WRITTEN | HOLD
      reason: 仅 HOLD/INVALID 时给出
      write_decision / manifest_entry / vault_relative_path
    """
    vault_root = resolve_vault(vault_root)
    feedback_dir = (
        Path(feedback_dir)
        if feedback_dir is not None
        else DEFAULT_FEEDBACK_DIR
    )

    empty = {
        "result_status": "HOLD",
        "reason": "",
        "write_decision": None,
        "manifest_entry": None,
        "vault_relative_path": None,
    }

    # ---- validate approved record ----
    if not isinstance(approved_record, dict):
        empty["reason"] = "INVALID_RECORD"
        return empty

    if approved_record.get("status") != "APPROVED_FOR_KB":
        empty["reason"] = "NOT_APPROVED_FOR_KB"
        return empty

    knowledge_record_id = approved_record.get("knowledge_record_id")
    candidate_id = approved_record.get("candidate_id")

    if not _is_safe_id(knowledge_record_id):
        empty["reason"] = "UNSAFE_KNOWLEDGE_RECORD_ID"
        return empty

    if not _is_safe_id(candidate_id):
        empty["reason"] = "UNSAFE_CANDIDATE_ID"
        return empty

    # ---- write gate validations ----
    if reviewer_role not in ALLOWED_REVIEWER_ROLES:
        empty["reason"] = "ROLE_NOT_ALLOWED"
        return empty

    if not (reviewer_name or "").strip():
        empty["reason"] = "REVIEWER_NAME_REQUIRED"
        return empty

    if evidence_confirmed is not True:
        empty["reason"] = "EVIDENCE_NOT_CONFIRMED"
        return empty

    if not vault_root.exists():
        empty["reason"] = "VAULT_MISSING"
        return empty

    # ---- duplicate guard ----
    if get_write_status(candidate_id, feedback_dir) is not None:
        empty["result_status"] = "ALREADY_WRITTEN"
        empty["reason"] = "ALREADY_WRITTEN"
        return empty

    # ---- build records in memory ----
    write_id = "KW-" + uuid4().hex
    written_at = _now_iso()

    relative_path = AUTO001_DIR_NAME + "/" + knowledge_record_id + ".md"
    vault_relative_path = (
        DERIVED_DIR_NAME + "/" + relative_path
    )

    knowledge_type = approved_record.get("knowledge_type")
    candidate_decision_type = approved_record.get("candidate_decision_type")
    topic = approved_record.get("topic") or "Derived Knowledge"
    summary = approved_record.get("summary") or ""
    recommended_action = approved_record.get("recommended_action") or ""
    source_refs = list(approved_record.get("source_refs") or [])

    write_decision = {
        "write_id": write_id,
        "knowledge_record_id": knowledge_record_id,
        "candidate_id": candidate_id,
        "candidate_key": approved_record.get("candidate_key"),
        "trace_id": approved_record.get("trace_id"),
        "review_id": approved_record.get("review_id"),
        "reviewer_role": reviewer_role,
        "reviewer_name": (reviewer_name or "").strip(),
        "evidence_confirmed": True,
        "write_comment": write_comment or "",
        "previous_status": "APPROVED_FOR_KB",
        "new_status": "WRITTEN_TO_DERIVED_KB",
        "vault_relative_path": vault_relative_path,
        "written_at": written_at,
        "truth_source_write": False,
        "current_runtime_write": False,
        "auto_reindex": False,
        "future_snapshot_gate_required": True,
    }

    manifest_entry = {
        "knowledge_record_id": knowledge_record_id,
        "candidate_id": candidate_id,
        "trace_id": approved_record.get("trace_id"),
        "review_id": approved_record.get("review_id"),
        "write_id": write_id,
        "relative_path": relative_path,
        "knowledge_type": knowledge_type,
        "status": "WRITTEN_TO_DERIVED_KB",
        "reviewer_role": reviewer_role,
        "reviewer_name": (reviewer_name or "").strip(),
        "written_at": written_at,
        "source_refs": source_refs,
        "future_snapshot_candidate": True,
        "current_runtime_source": False,
        "truth_source": False,
    }

    markdown_text = _build_derived_markdown(
        knowledge_record_id=knowledge_record_id,
        candidate_id=candidate_id,
        candidate_key=approved_record.get("candidate_key"),
        trace_id=approved_record.get("trace_id"),
        review_id=approved_record.get("review_id"),
        write_id=write_id,
        knowledge_type=knowledge_type,
        candidate_decision_type=candidate_decision_type,
        reviewer_role=reviewer_role,
        reviewer_name=(reviewer_name or "").strip(),
        reviewed_at=approved_record.get("approved_at"),
        written_at=written_at,
        topic=topic,
        summary=summary,
        relationship=approved_record.get("relationship_to_existing_knowledge"),
        source_refs=source_refs,
        recommended_action=recommended_action,
    )

    # ---- write (atomic-ish) ----
    derived_dir = vault_root / DERIVED_DIR_NAME
    auto001_dir = derived_dir / AUTO001_DIR_NAME
    auto001_dir.mkdir(parents=True, exist_ok=True)

    # 首次创建 05 目录时生成 README
    readme_path = derived_dir / README_FILENAME

    if not readme_path.exists():
        readme_path.write_text(README_CONTENT, encoding="utf-8")

    final_md_path = auto001_dir / (knowledge_record_id + ".md")

    if final_md_path.exists():
        empty["result_status"] = "ALREADY_WRITTEN"
        empty["reason"] = "ALREADY_WRITTEN"
        return empty

    tmp_md_path = auto001_dir / (knowledge_record_id + ".md.tmp")
    tmp_md_path.write_text(markdown_text, encoding="utf-8")

    _append_jsonl(
        derived_dir / MANIFEST_FILENAME,
        manifest_entry,
    )

    _append_jsonl(
        feedback_dir / WRITE_DECISIONS_FILE,
        write_decision,
    )

    tmp_md_path.replace(final_md_path)

    return {
        "result_status": "WRITTEN_TO_DERIVED_KB",
        "reason": None,
        "write_decision": write_decision,
        "manifest_entry": manifest_entry,
        "vault_relative_path": vault_relative_path,
    }


def _build_derived_markdown(
    knowledge_record_id,
    candidate_id,
    candidate_key,
    trace_id,
    review_id,
    write_id,
    knowledge_type,
    candidate_decision_type,
    reviewer_role,
    reviewer_name,
    reviewed_at,
    written_at,
    topic,
    summary,
    relationship,
    source_refs,
    recommended_action,
):
    is_evidence_gap = (
        knowledge_type == "EVIDENCE_GAP"
        or candidate_decision_type == "EVIDENCE_GAP"
    )

    gap_note = (
        "\n该条记录的是当前证据缺口，\n不表示缺失验证已经完成。\n"
        if is_evidence_gap
        else ""
    )

    source_lines = "".join(
        "- " + str(r) + "\n"
        for r in source_refs
    ) if source_refs else "（无）\n"

    return (
        "---\n"
        "knowledge_record_id: " + str(knowledge_record_id) + "\n"
        "candidate_id: " + str(candidate_id) + "\n"
        "candidate_key: " + str(candidate_key or "") + "\n"
        "trace_id: " + str(trace_id or "") + "\n"
        "review_id: " + str(review_id or "") + "\n"
        "write_id: " + str(write_id) + "\n"
        "\n"
        "status: WRITTEN_TO_DERIVED_KB\n"
        "knowledge_type: " + str(knowledge_type or "") + "\n"
        "candidate_decision_type: " + str(candidate_decision_type or "") + "\n"
        "\n"
        "reviewer_role: " + str(reviewer_role) + "\n"
        "reviewer_name: " + str(reviewer_name) + "\n"
        "reviewed_at: " + str(reviewed_at or "") + "\n"
        "written_at: " + str(written_at) + "\n"
        "\n"
        "truth_source: false\n"
        "approved_as_evidence: false\n"
        "current_runtime_source: false\n"
        "future_snapshot_candidate: true\n"
        "future_snapshot_gate_required: true\n"
        "---\n\n"
        "# " + str(topic) + "\n\n"
        "## 一、知识摘要\n\n" + str(summary) + "\n\n"
        "## 二、与现有知识关系\n\n" + str(relationship or "（未在审核记录中提供）") + "\n\n"
        "## 三、当前 Evidence / Source\n\n" + source_lines + "\n"
        "## 四、当前知识边界\n\n"
        "本条为人工审核通过的派生知识，\n"
        "不等同于企业原始事实，\n"
        "不自动构成当前产品性能验证结论。\n"
        + gap_note +
        "\n## 五、建议下一步\n\n" + str(recommended_action) + "\n\n"
        "## 六、治理信息\n\n"
        "Candidate: " + str(candidate_id) + "\n"
        "Trace: " + str(trace_id or "") + "\n"
        "Review: " + str(review_id or "") + "\n"
        "Write: " + str(write_id) + "\n"
        "Reviewer: " + str(reviewer_name) + " (" + str(reviewer_role) + ")\n"
    )

# -*- coding: utf-8 -*-
"""
Legacy Derived Knowledge Correction & Supersession V0.7

职责（只读审计 + append-only 治理提案，绝不改旧记录）：
  - audit_legacy_derived_knowledge(...)
      只读扫描 05_已审核派生知识/AUTO-001/AK-*.md，检测两类违规：
        A: UNSUPPORTED_CURRENT_FORMULATION
           历史证据只支持「PPG 发生低温问题 → PTMEG 作为纠正措施改善」，
           不能支持「当前 HD-S303 = PTMEG/PCDL/PPG 体系」。
        B: OUT_OF_POLICY_FORMULATION_PRESCRIPTION
           把「改PCDL / 推荐PCDL / 调整配方 / 直接指定软段替代」升级为当前项目行动。
  - find_replacement_candidates(...)
      在 kb_update_candidates.jsonl 中寻找唯一「同一 AUTO-001 主题 + 更新版本
      语义正确 + 仍可进入 Human Review」的合规候选（更新版本 = 严格晚于旧候选）。
  - build_correction_intent(...)
      构造 Governance Proposal（Correction Intent，status=PROPOSED）。
  - resolve_correction_intent(...)
      同一 legacy_knowledge_record_id 的重复保护。
  - build_supersession_relation(...)
      仅当 Replacement 已 APPROVED_FOR_KB 且 WRITTEN_TO_DERIVED_KB 时生成。
  - get_supersession_status(...)
      由 Review / Write / Relation 派生当前状态。

治理原则（永久）：
  - APPEND_ONLY / OLD_RECORD_IMMUTABLE / NO_DELETE / NO_OVERWRITE / NO_EDIT_HISTORY
  - Correction Intent 是 Governance Proposal，不是 Evidence / Approved Knowledge /
    Runtime Source，不触发任何写入 Truth Source / 当前 Runtime / re-index。
  - 旧 AK 即使有错也不修改；旧 Manifest 行不修改；旧 Review/Write Decision 不修改。
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_FEEDBACK_DIR = PROJECT_ROOT / "outputs" / "knowledge_feedback"
DEFAULT_VAULT_ROOT = PROJECT_ROOT / "data" / "knowledge_vault" / "AUTO001_Y_V2"

DERIVED_DIR_NAME = "05_已审核派生知识"
AUTO001_DIR_NAME = "AUTO-001"
MANIFEST_FILENAME = "00_Approved_Knowledge_Manifest.jsonl"

CORRECTION_INTENTS_FILE = "knowledge_correction_intents.jsonl"
SUPERSESSION_RELATIONS_FILE = "knowledge_supersession_relations.jsonl"

VIOLATION_A = "UNSUPPORTED_CURRENT_FORMULATION"
VIOLATION_B = "OUT_OF_POLICY_FORMULATION_PRESCRIPTION"

CORRECTION_RELATION_TYPE = "SUPERSEDED_BY_CORRECTION"

# Correction Intent 状态（派生，不修改原 JSONL）
INTENT_PROPOSED = "PROPOSED"
INTENT_REPLACEMENT_APPROVED = "REPLACEMENT_APPROVED"
INTENT_SUPERSEDED = "SUPERSEDED"

_SINGLE_SYS = r"(?:PTMEG|PPG|PCDL|PBA|PEA|PCL)"

# A1: 产品/汽车革 + （单一体系）确定性限定，例如 "HD-S303（PTMEG体系）"
_RE_PAREN_SYS = re.compile(r"[（(](" + _SINGLE_SYS + r")体系[）)]")

# A2: 当前/现用/现为/采用 + 单一体系，例如 "当前PTMEG体系"
_RE_CURRENT_SYS = re.compile(
    r"(?:当前|现用|现为|目前采用|当前采用|当前使用|当前为|现采用)"
    r"[^，。；：、\u4e00-\u9fff]{0,3}"
    r"(" + _SINGLE_SYS + r")体系"
)

_QUESTION_MARKERS = ("是否", "若非", "如为", "如已", "需确认", "待确认")

# B: 把软段替代/配方调整升级为当前项目行动（非技术文献讨论）
_TYPE_B_MARKERS = [
    "改PCDL", "换PCDL", "推荐PCDL", "改用PCDL", "选用PCDL", "替换为PCDL",
    "改PTMEG", "换PTMEG", "推荐PTMEG", "改用PTMEG", "替换为PTMEG",
    "改PPG", "换PPG", "推荐PPG", "改用PPG", "替换为PPG",
    "调整配方", "调配方", "修改配方", "配方调整", "改配方",
]


# ============================================================
# 基础工具
# ============================================================

def _now_iso():
    return datetime.now(timezone.utc).isoformat()


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
                    continue

    except Exception:
        return []

    return rows


def _append_jsonl(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _sha256_text(text):
    return hashlib.sha256(
        (text or "").encode("utf-8")
    ).hexdigest()


def content_sha256(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ============================================================
# 违规检测（保守：只识别确定性断言/明确行动处方）
# ============================================================

def detect_violations(text):
    """
    返回违规类型列表（去重、稳定顺序）。
    保守原则：历史「PPG→PTMEG纠正」、技术文献讨论 PCDL/PTMEG、
    「是否当前为PTMEG需确认」均不算违规。
    """
    text = text or ""

    types = []

    if _collect_type_a_hits(text):
        types.append(VIOLATION_A)

    if _collect_type_b_hits(text):
        types.append(VIOLATION_B)

    return types


def _collect_type_a_hits(text):
    hits = []

    for m in _RE_PAREN_SYS.finditer(text):
        prefix = text[max(0, m.start() - 8):m.start()]

        if any(q in prefix for q in _QUESTION_MARKERS):
            continue

        hits.append(m.group(0))

    for m in _RE_CURRENT_SYS.finditer(text):
        prefix = text[max(0, m.start() - 8):m.start()]

        if any(q in prefix for q in _QUESTION_MARKERS):
            continue

        hits.append(m.group(0))

    return hits


def _collect_type_b_hits(text):
    return [mk for mk in _TYPE_B_MARKERS if mk in text]


def violation_evidence(text):
    """返回 {violation_type: [命中片段]}，供审计可解释、可追溯。"""
    text = text or ""

    evidence = {}

    a_hits = _collect_type_a_hits(text)
    b_hits = _collect_type_b_hits(text)

    if a_hits:
        evidence[VIOLATION_A] = a_hits

    if b_hits:
        evidence[VIOLATION_B] = b_hits

    return evidence


# ============================================================
# 审计
# ============================================================

def _parse_frontmatter(text):
    fm = {}
    lines = (text or "").splitlines()

    if not lines or lines[0].strip() != "---":
        return fm

    end = None

    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break

    if end is None:
        return fm

    for line in lines[1:end]:
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()

    return fm


def _extract_title(text):
    for line in (text or "").splitlines():
        s = line.strip()

        if s.startswith("# "):
            return s[2:].strip()

    return None


def default_ak_dir(vault_root=None):
    vault_root = (
        Path(vault_root) if vault_root is not None else DEFAULT_VAULT_ROOT
    )
    return vault_root / DERIVED_DIR_NAME / AUTO001_DIR_NAME


def audit_legacy_derived_knowledge(ak_dir=None, vault_root=None):
    """
    只读扫描 AK-*.md，返回每条审计记录：
      knowledge_record_id / candidate_id / trace_id / path / topic /
      violation_types / violation_hits / content_sha256。
    绝不修改任何文件。
    """
    ak_dir = Path(ak_dir) if ak_dir is not None else default_ak_dir(vault_root)
    vault_root = Path(vault_root) if vault_root is not None else DEFAULT_VAULT_ROOT

    if not ak_dir.exists():
        return []

    rows = []

    for p in sorted(ak_dir.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        title = _extract_title(text)
        evidence = violation_evidence(text)
        violation_types = [
            t for t in (VIOLATION_A, VIOLATION_B) if t in evidence
        ]

        try:
            relative_path = p.relative_to(vault_root).as_posix()

        except ValueError:
            relative_path = p.name

        rows.append({
            "knowledge_record_id": fm.get("knowledge_record_id") or p.stem,
            "candidate_id": fm.get("candidate_id"),
            "trace_id": fm.get("trace_id"),
            "path": relative_path,
            "absolute_path": str(p),
            "topic": title,
            "violation_types": violation_types,
            "violation_hits": evidence,
            "content_sha256": _sha256_text(text),
        })

    return rows


# ============================================================
# Replacement Candidate 选择
# ============================================================

def _candidate_created_at(candidate_id, candidates):
    for c in candidates:
        if c.get("candidate_id") == candidate_id:
            return c.get("created_at")

    return None


def _is_newer_than(candidate, legacy_ts):
    ts = candidate.get("created_at")

    if not ts:
        return False

    if not legacy_ts:
        return True

    return ts > legacy_ts


def _is_auto001_validation_topic(candidate):
    th = candidate.get("target_hint") or {}
    topic = th.get("suggested_topic") or ""
    query = candidate.get("query") or ""
    hay = (topic + " " + query)

    has_product = any(
        k in hay for k in ("HD-S303", "汽车革", "汽车内饰革")
    )
    has_minus30 = "-30" in hay
    has_flex = "耐折" in hay

    return has_product and has_minus30 and has_flex


def _is_policy_compliant(candidate):
    th = candidate.get("target_hint") or {}
    topic = th.get("suggested_topic") or ""
    gap = candidate.get("knowledge_gap_summary") or ""
    evidence_needed = candidate.get("evidence_needed") or []
    query = candidate.get("query") or ""

    text = "\n".join([
        topic,
        gap,
        query,
        "\n".join(str(x) for x in evidence_needed),
    ])

    return not detect_violations(text)


def find_replacement_candidates(
    legacy_record,
    candidates,
    reviewed_candidate_ids=None,
    approved_candidate_ids=None,
):
    """
    为一条 Legacy 违规 AK 寻找合规 Replacement Candidate。
    条件（全部满足）：
      - EVIDENCE_GAP 决策类型（与旧 AK 同主题同缺口类型）
      - 同一 AUTO-001 主题（HD-S303 / 汽车革 / -30℃ / 耐折）
      - 语义正确（无 A/B 违规）
      - 仍可进入 Human Review（未审核、未批准）
      - 严格晚于旧候选（更新版本，避免凭时间最近猜、也排除旧候选自身）
    """
    reviewed_candidate_ids = set(reviewed_candidate_ids or [])
    approved_candidate_ids = set(approved_candidate_ids or [])

    legacy_cid = legacy_record.get("candidate_id")
    legacy_ts = _candidate_created_at(legacy_cid, candidates)

    out = []

    for c in candidates:
        cid = c.get("candidate_id")

        if not cid or cid == legacy_cid:
            continue

        if cid in reviewed_candidate_ids or cid in approved_candidate_ids:
            continue

        if c.get("decision_type") != "EVIDENCE_GAP":
            continue

        if not _is_auto001_validation_topic(c):
            continue

        if not _is_policy_compliant(c):
            continue

        if not _is_newer_than(c, legacy_ts):
            continue

        out.append(c)

    return out


# ============================================================
# Correction Intent
# ============================================================

def build_correction_intent(legacy_record, replacement_candidate, reason=None):
    """构造 Governance Proposal（status=PROPOSED，不写盘）。"""
    return {
        "correction_intent_id": "KCI-" + uuid4().hex,
        "legacy_knowledge_record_id": legacy_record.get("knowledge_record_id"),
        "legacy_candidate_id": legacy_record.get("candidate_id"),
        "legacy_trace_id": legacy_record.get("trace_id"),
        "legacy_path": legacy_record.get("path"),
        "violation_types": list(legacy_record.get("violation_types") or []),
        "replacement_candidate_id": replacement_candidate.get("candidate_id"),
        "replacement_candidate_key": replacement_candidate.get("candidate_key"),
        "reason": (
            reason
            or "历史证据仅支持PPG→PTMEG纠正措施改善低温问题，"
            "不能支持当前HD-S303采用PTMEG体系；以合规候选纠正旧派生知识。"
        ),
        "status": INTENT_PROPOSED,
        "created_at": _now_iso(),
        "human_review_required": True,
        "truth_source_write": False,
        "current_runtime_write": False,
        "auto_reindex": False,
        "future_snapshot_gate_required": True,
    }


def resolve_correction_intent(legacy_knowledge_record_id, intents=None, relations=None):
    """
    同一 legacy_knowledge_record_id 的重复保护。
    返回：
      CAN_CREATE | ALREADY_HAS_CORRECTION_INTENT | ALREADY_SUPERSEDED
    """
    intents = intents or []
    relations = relations or []

    for rel in relations:
        if rel.get("old_knowledge_record_id") == legacy_knowledge_record_id:
            return "ALREADY_SUPERSEDED"

    for it in intents:
        if (
            it.get("legacy_knowledge_record_id") == legacy_knowledge_record_id
            and it.get("status") in (INTENT_PROPOSED, INTENT_REPLACEMENT_APPROVED)
        ):
            return "ALREADY_HAS_CORRECTION_INTENT"

    return "CAN_CREATE"


def load_correction_intents(feedback_dir=None):
    feedback_dir = (
        Path(feedback_dir) if feedback_dir is not None else DEFAULT_FEEDBACK_DIR
    )
    return _load_jsonl_safe(feedback_dir / CORRECTION_INTENTS_FILE)


def load_supersession_relations(feedback_dir=None):
    feedback_dir = (
        Path(feedback_dir) if feedback_dir is not None else DEFAULT_FEEDBACK_DIR
    )
    return _load_jsonl_safe(feedback_dir / SUPERSESSION_RELATIONS_FILE)


def append_correction_intent(intent, feedback_dir=None):
    """
    append-only 写 Governance Proposal（Correction Intent）。
    重复保护 + 已 Supersede 保护，返回 dict。
    """
    feedback_dir = (
        Path(feedback_dir) if feedback_dir is not None else DEFAULT_FEEDBACK_DIR
    )

    relations = load_supersession_relations(feedback_dir)
    intents = load_correction_intents(feedback_dir)

    resolution = resolve_correction_intent(
        intent.get("legacy_knowledge_record_id"),
        intents,
        relations,
    )

    if resolution != "CAN_CREATE":
        return {
            "result_status": resolution,
            "intent": None,
        }

    _append_jsonl(feedback_dir / CORRECTION_INTENTS_FILE, intent)

    return {
        "result_status": "APPENDED",
        "intent": intent,
    }


def propose_correction_intents(
    audit_records,
    candidates,
    reviewed_candidate_ids=None,
    approved_candidate_ids=None,
    feedback_dir=None,
):
    """
    编排：对每条违规 AK，唯一确定 Replacement 才 append PROPOSED Intent。
    返回 {result_status: APPENDED / HOLD, correction_intents: [...],
          hold_reasons: [...], mapping: {...}}。
    """
    reviewed_candidate_ids = list(reviewed_candidate_ids or [])
    approved_candidate_ids = list(approved_candidate_ids or [])

    intents = []
    hold_reasons = []
    mapping = {}

    for record in audit_records:
        rid = record.get("knowledge_record_id")

        if not record.get("violation_types"):
            mapping[rid] = {
                "decision": "NO_VIOLATION",
                "correction_intent_id": None,
            }
            continue

        replacements = find_replacement_candidates(
            record,
            candidates,
            reviewed_candidate_ids,
            approved_candidate_ids,
        )

        if len(replacements) == 0:
            mapping[rid] = {
                "decision": "HOLD",
                "reason": "NO_REPLACEMENT_CANDIDATE",
                "correction_intent_id": None,
            }
            hold_reasons.append(rid + ":NO_REPLACEMENT_CANDIDATE")
            continue

        if len(replacements) > 1:
            mapping[rid] = {
                "decision": "HOLD",
                "reason": "MULTIPLE_REPLACEMENT_CANDIDATES",
                "correction_intent_id": None,
            }
            hold_reasons.append(rid + ":MULTIPLE_REPLACEMENT_CANDIDATES")
            continue

        intent = build_correction_intent(record, replacements[0])
        result = append_correction_intent(intent, feedback_dir)

        if result["result_status"] == "APPENDED":
            mapping[rid] = {
                "decision": "PROPOSED",
                "correction_intent_id": intent["correction_intent_id"],
                "replacement_candidate_id": intent["replacement_candidate_id"],
            }
            intents.append(intent)

        else:
            mapping[rid] = {
                "decision": result["result_status"],
                "correction_intent_id": None,
            }
            hold_reasons.append(
                rid + ":" + result["result_status"]
            )

    result_status = (
        "APPENDED" if intents else "HOLD"
    )

    return {
        "result_status": result_status,
        "correction_intents": intents,
        "hold_reasons": hold_reasons,
        "mapping": mapping,
    }


# ============================================================
# Supersession Relation
# ============================================================

def build_supersession_relation(
    correction_intent,
    new_knowledge_record_id,
    new_candidate_id,
    replacement_review_status=None,
    replacement_write_status=None,
):
    """
    仅当 Replacement 已 APPROVED_FOR_KB 且 WRITTEN_TO_DERIVED_KB 时生成关系。
    返回 {"relation": dict|None, "reason": str|None}。
    """
    if replacement_review_status != "APPROVED_FOR_KB":
        return {
            "relation": None,
            "reason": "REPLACEMENT_NOT_APPROVED",
        }

    if replacement_write_status != "WRITTEN_TO_DERIVED_KB":
        return {
            "relation": None,
            "reason": "REPLACEMENT_NOT_WRITTEN",
        }

    relation = {
        "relation_id": "KSR-" + uuid4().hex,
        "correction_intent_id": correction_intent.get("correction_intent_id"),
        "old_knowledge_record_id": correction_intent.get(
            "legacy_knowledge_record_id"
        ),
        "new_knowledge_record_id": new_knowledge_record_id,
        "old_candidate_id": correction_intent.get("legacy_candidate_id"),
        "new_candidate_id": new_candidate_id,
        "relation_type": CORRECTION_RELATION_TYPE,
        "created_at": _now_iso(),
        "old_record_modified": False,
        "truth_source_modified": False,
        "current_runtime_changed": False,
        "auto_reindex": False,
    }

    return {
        "relation": relation,
        "reason": None,
    }


def append_supersession_relation(relation, feedback_dir=None):
    """append-only 写 Supersession Relation。"""
    feedback_dir = (
        Path(feedback_dir) if feedback_dir is not None else DEFAULT_FEEDBACK_DIR
    )

    relations = load_supersession_relations(feedback_dir)

    # 同一 correction_intent 只建立一条关系
    for rel in relations:
        if rel.get("correction_intent_id") == relation.get(
            "correction_intent_id"
        ):
            return {
                "result_status": "ALREADY_SUPERSEDED",
                "relation": None,
            }

    _append_jsonl(feedback_dir / SUPERSESSION_RELATIONS_FILE, relation)

    return {
        "result_status": "APPENDED",
        "relation": relation,
    }


def _latest_by_candidate(records, candidate_id):
    for rec in reversed(records):
        if rec.get("candidate_id") == candidate_id:
            return rec

    return None


def _relation_exists(relations, old_id, new_id):
    for rel in relations:
        if (
            rel.get("old_knowledge_record_id") == old_id
            and rel.get("new_knowledge_record_id") == new_id
            and rel.get("relation_type") == CORRECTION_RELATION_TYPE
        ):
            return True

    return False


def finalize_correction_supersession(
    replacement_candidate_id,
    new_knowledge_record_id,
    intents=None,
    review_records=None,
    write_records=None,
    feedback_dir=None,
):
    """
    Supersession Finalization Hook（V0.7.1 补齐）。

    在 Replacement Candidate 已 APPROVED_FOR_KB 且新 Correction AK 已
    WRITTEN_TO_DERIVED_KB 之后，为每条关联 Correction Intent 建立一条
    append-only Supersession Relation（每个 Legacy AK 一条）。

    幂等：同一 (old_knowledge_record_id, new_knowledge_record_id, relation_type)
    不重复 append。

    返回 dict：
      result_status ∈ {FINALIZED, ALREADY_SUPERSEDED, PARTIAL, HOLD}
      relations_created: [relation, ...]
      reasons: [reason, ...]
    """
    feedback_dir = (
        Path(feedback_dir) if feedback_dir is not None else DEFAULT_FEEDBACK_DIR
    )

    intents = (
        intents
        if intents is not None
        else load_correction_intents(feedback_dir)
    )
    review_records = (
        review_records
        if review_records is not None
        else _load_jsonl_safe(feedback_dir / "review_decisions.jsonl")
    )
    write_records = (
        write_records
        if write_records is not None
        else _load_jsonl_safe(feedback_dir / "knowledge_write_decisions.jsonl")
    )

    def _hold(reason):
        return {
            "result_status": "HOLD",
            "relations_created": [],
            "reasons": [reason],
        }

    # 1. intents 必须引用该 replacement candidate
    matched_intents = [
        it
        for it in intents
        if it.get("replacement_candidate_id") == replacement_candidate_id
    ]

    if not matched_intents:
        return _hold("NO_CORRECTION_INTENT")

    # 2. review 必须 APPROVED_FOR_KB
    review = _latest_by_candidate(review_records, replacement_candidate_id)

    if not review or review.get("new_status") != "APPROVED_FOR_KB":
        return _hold("REPLACEMENT_NOT_APPROVED")

    # 3. write 必须存在且 WRITTEN_TO_DERIVED_KB，且新 AK 匹配
    write = _latest_by_candidate(write_records, replacement_candidate_id)

    if not write:
        return _hold("WRITE_DECISION_MISSING")

    if write.get("new_status") != "WRITTEN_TO_DERIVED_KB":
        return _hold("REPLACEMENT_NOT_WRITTEN")

    if write.get("knowledge_record_id") != new_knowledge_record_id:
        return _hold("NEW_AK_MISMATCH")

    # 4. 为每条 intent 建一条 relation（去重）
    relations = load_supersession_relations(feedback_dir)
    created = []
    reasons = []

    for it in matched_intents:
        old_id = it.get("legacy_knowledge_record_id")

        if _relation_exists(relations, old_id, new_knowledge_record_id):
            reasons.append(old_id + ":ALREADY_SUPERSEDED")
            continue

        relation = {
            "relation_id": "KSR-" + uuid4().hex,
            "correction_intent_id": it.get("correction_intent_id"),
            "old_knowledge_record_id": old_id,
            "new_knowledge_record_id": new_knowledge_record_id,
            "old_candidate_id": it.get("legacy_candidate_id"),
            "new_candidate_id": replacement_candidate_id,
            "relation_type": CORRECTION_RELATION_TYPE,
            "created_at": _now_iso(),
            "old_record_modified": False,
            "truth_source_modified": False,
            "current_runtime_changed": False,
            "auto_reindex": False,
        }

        _append_jsonl(feedback_dir / SUPERSESSION_RELATIONS_FILE, relation)
        relations.append(relation)
        created.append(relation)

    if not created:
        return {
            "result_status": "ALREADY_SUPERSEDED",
            "relations_created": [],
            "reasons": reasons,
        }

    if reasons:
        return {
            "result_status": "PARTIAL",
            "relations_created": created,
            "reasons": reasons,
        }

    return {
        "result_status": "FINALIZED",
        "relations_created": created,
        "reasons": [],
    }


def get_supersession_status(
    correction_intent,
    relations=None,
    replacement_review_status=None,
    replacement_write_status=None,
):
    """
    由 Review / Write / Relation 派生当前状态（不修改原 Intent JSONL）。
    返回 PROPOSED | REPLACEMENT_APPROVED | SUPERSEDED。
    """
    relations = relations or []

    for rel in relations:
        if rel.get("correction_intent_id") == correction_intent.get(
            "correction_intent_id"
        ):
            return INTENT_SUPERSEDED

    if replacement_write_status == "WRITTEN_TO_DERIVED_KB":
        return INTENT_SUPERSEDED

    if replacement_review_status == "APPROVED_FOR_KB":
        return INTENT_REPLACEMENT_APPROVED

    return INTENT_PROPOSED


# ============================================================
# History / UI 派生展示
# ============================================================

def get_legacy_correction_status(knowledge_record_id, intents=None, relations=None):
    """
    旧 AK 记录的更正展示状态。
    返回 None 或 dict：
      {"status": "CORRECTION_PENDING" | "SUPERSEDED",
       "new_knowledge_record_id": str|None, "correction_intent_id": str|None}
    """
    intents = intents or []
    relations = relations or []

    for rel in relations:
        if rel.get("old_knowledge_record_id") == knowledge_record_id:
            return {
                "status": INTENT_SUPERSEDED,
                "new_knowledge_record_id": rel.get("new_knowledge_record_id"),
                "correction_intent_id": rel.get("correction_intent_id"),
            }

    for it in intents:
        if (
            it.get("legacy_knowledge_record_id") == knowledge_record_id
            and it.get("status") in (INTENT_PROPOSED, INTENT_REPLACEMENT_APPROVED)
        ):
            return {
                "status": "CORRECTION_PENDING",
                "new_knowledge_record_id": None,
                "correction_intent_id": it.get("correction_intent_id"),
            }

    return None


def get_candidate_correction_intent(candidate_id, intents=None):
    """某 Candidate 是否作为 Replacement（存在 Correction Intent）。"""
    intents = intents or []

    for it in intents:
        if it.get("replacement_candidate_id") == candidate_id:
            return it

    return None


def get_candidate_correction_intents(candidate_id, intents=None):
    """某 Candidate 作为 Replacement 关联的全部 Correction Intent（可纠正多条旧 AK）。"""
    intents = intents or []

    return [
        it
        for it in intents
        if it.get("replacement_candidate_id") == candidate_id
    ]


def get_new_record_correction_relation(new_knowledge_record_id, relations=None):
    """新（Superseding）AK 纠正了哪些旧 AK。"""
    relations = relations or []

    return [
        rel.get("old_knowledge_record_id")
        for rel in relations
        if rel.get("new_knowledge_record_id") == new_knowledge_record_id
    ]


def build_correction_annotations(correction_intent):
    """
    供 Knowledge Writeback 生成新 Correction AK 时注入治理信息。
    返回 (frontmatter_additions: dict, markdown_section: str)。
    """
    old_id = correction_intent.get("legacy_knowledge_record_id")

    frontmatter_additions = {
        "corrects_knowledge_record_ids": [old_id],
    }

    section = (
        "## 更正关系\n\n"
        "本条知识用于纠正：\n\n- "
        + str(old_id)
        + "\n\n纠正内容：\n历史PPG→PTMEG纠正措施，"
        "不能证明当前HD-S303采用PTMEG体系。\n\n"
        "本条不修改旧记录；旧记录保留用于审计追溯。\n"
    )

    return frontmatter_additions, section

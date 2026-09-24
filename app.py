import sys
import json
import re
import html
from pathlib import Path

import streamlit as st


# ============================================================
# 0. Paths / imports
# ============================================================

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )

from live_answer_service_v1 import run_live
from knowledge_curator_v0_2 import run_knowledge_curator
from runtime_llm_config_v1_1 import (
    PROVIDERS,
    resolve_runtime_llm_config,
    validate_runtime_llm_config,
    public_runtime_summary,
)
from ui_display_utils_v1 import (
    extract_product,
    normalize_auto001_validation_for_display,
)
from context_entity_resolver_v0_6 import (
    product_display_value,
)
from context_scope_guard_v0_6_1 import (
    SCOPE_AUTO001,
    SCOPE_GENERIC,
    SCOPE_AMBIGUOUS,
    SCOPE_NOT_SCOPED,
    explicit_scope_signals,
)
from conversation_subject_resolver_v0_6_5 import (
    build_next_scene_context,
    build_subject_audit,
)
from product_role_guard_v0_6_2 import (
    effective_product_display_value,
)
from validation_policy_guard_v0_6_3 import (
    guard_curator_candidate_policy,
)
from knowledge_review_v0_3 import (
    get_review_status,
    review_candidate,
)
from knowledge_writeback_v0_4 import (
    get_approved_record,
    get_write_decision,
    get_write_status,
    write_approved_knowledge,
)
from knowledge_history_v0_5 import (
    filter_history,
    get_candidate,
    get_current_governance_status,
    load_history,
    search_history,
    status_display_label,
)
from knowledge_correction_v0_7 import (
    get_candidate_correction_intents,
    get_legacy_correction_status,
    load_correction_intents,
    load_supersession_relations,
)


FROZEN_DEMO_PATH = (
    ROOT
    / "outputs"
    / "auto001_main_demo_structured_output_A1_v1_3_1.json"
)

DEFAULT_QUERY = (
    "汽车内饰革客户要求HD-S303面层"
    "-30℃耐折≥5万次，"
    "历史上有哪些值得提前关注的低温风险？"
)

SCENE_ID = "AUTO-001"


# ============================================================
# 1. Design tokens (集中管理 CSS)
# ============================================================

DESIGN_CSS = """
<style>
:root {
  --bg: #f8fafc;
  --surface: #ffffff;
  --text: #1e293b;
  --muted: #64748b;
  --border: #e2e8f0;
  --brand: #2563eb;
  --risk: #b45309;
  --risk-bg: #fffbeb;
  --risk-border: #fcd34d;
  --gap: #b91c1c;
  --gap-bg: #fef2f2;
  --gap-border: #fecaca;
  --success: #15803d;
  --success-bg: #f0fdf4;
  --success-border: #bbf7d0;
}
.section-title {
  font-size: 18px;
  font-weight: 650;
  color: var(--text);
  margin: 22px 0 8px 0;
}
.muted-note {
  color: var(--muted);
  font-size: 13px;
}
.block {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 20px;
}
.scene-line {
  color: var(--muted);
  font-size: 13px;
  margin-bottom: 12px;
}
.task-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1.25fr;
  gap: 12px;
}
.task-label {
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 2px;
}
.task-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}
.task-value-metric {
  font-size: 16px;
  font-weight: 700;
  color: var(--brand);
}
.risk-block {
  background: var(--risk-bg);
  border: 1px solid var(--risk-border);
  border-left: 4px solid var(--risk);
  border-radius: 10px;
  padding: 14px 18px;
  margin: 14px 0;
}
.risk-title {
  font-weight: 650;
  color: #92400e;
  font-size: 14px;
}
.risk-summary {
  color: #3f3f46;
  font-size: 14px;
  line-height: 1.6;
  margin-top: 6px;
}
.tag-row {
  margin-top: 10px;
}
.tag {
  display: inline-block;
  font-size: 12px;
  font-weight: 600;
  padding: 2px 9px;
  border-radius: 999px;
  margin-right: 6px;
  border: 1px solid transparent;
}
.tag-e2 { background: #fef3c7; color: #92400e; }
.tag-e3 { background: #e0e7ff; color: #3730a3; }
.tag-gap { background: #fee2e2; color: #991b1b; }
.evidence-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px;
  height: 100%;
}
.evidence-claim {
  font-size: 14px;
  color: var(--text);
  line-height: 1.55;
  margin-top: 8px;
}
.evidence-cond {
  font-size: 12px;
  color: var(--muted);
  margin-top: 6px;
}
.evidence-meta {
  font-size: 12px;
  color: var(--muted);
  margin-top: 8px;
}
.gap-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.gap-table th, .gap-table td {
  text-align: left;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  font-size: 14px;
}
.gap-table th {
  background: #f8fafc;
  font-weight: 600;
  color: var(--muted);
  font-size: 12px;
}
.gap-table td.cur {
  font-weight: 650;
  color: var(--brand);
}
.gap-table tr:last-child td {
  border-bottom: none;
}
.gap-block {
  background: var(--gap-bg);
  border: 1px solid var(--gap-border);
  border-left: 4px solid var(--gap);
  border-radius: 10px;
  padding: 16px 18px;
  margin: 10px 0 4px 0;
  font-size: 14.5px;
  line-height: 1.65;
  color: #3f3f46;
}
.gap-kicker {
  color: var(--gap);
  font-weight: 650;
  font-size: 13px;
  margin-bottom: 6px;
}
.p0-block {
  background: var(--success-bg);
  border: 1px solid var(--success-border);
  border-left: 4px solid var(--success);
  border-radius: 10px;
  padding: 14px 18px;
  margin: 10px 0 6px 0;
}
.px-block {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 14px;
  margin: 6px 0;
}
.p0-action {
  font-size: 15px;
  font-weight: 650;
  color: #14532d;
}
.px-action {
  font-size: 13.5px;
  color: var(--text);
}
.reason {
  font-size: 12.5px;
  color: var(--muted);
  margin-top: 4px;
}
.conclusion-line {
  color: var(--muted);
  font-size: 13px;
  margin-top: 10px;
  line-height: 1.55;
}
</style>
"""


# ============================================================
# 2. Helpers
# ============================================================

def as_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


@st.cache_data
def load_json(path_string):
    path = Path(path_string)

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def _esc(value):
    return html.escape(
        str(value if value is not None else "")
    )


def _extract_metric(text):
    m = re.search(
        r"-?\d+\s*℃[^，。；;（）()\n]{0,60}",
        text or "",
    )

    if not m:
        return None

    seg = re.sub(r"\s+", " ", m.group(0)).strip()

    return seg or None


def _extract_application(text, condition_gap):
    text = text or ""

    for keyword in [
        "汽车内饰革",
        "仪表板包覆革",
        "沙发革",
        "运动鞋革",
        "箱包革",
    ]:
        if keyword in text:
            return keyword

    for item in (condition_gap or []):
        if not isinstance(item, dict):
            continue

        dim = item.get("dimension") or ""

        if "应用" in dim or "场景" in dim:
            cur = str(item.get("current") or "")
            cur = re.sub(r"（[^）]*）", "", cur).strip()

            if cur:
                return cur

    return None


def _classify_source(source):
    s = source or ""

    if "03_客户需求" in s or "requirements" in s or "客户需求" in s:
        return "客户需求"

    if "08_问题案例" in s or "cases.csv" in s or "问题案例" in s:
        return "历史案例"

    if "10_行业标准" in s or "standards" in s:
        return "测试标准"

    if "11_公开技术资料" in s or "literature" in s:
        return "技术文献"

    if "02_研发项目" in s or "projects" in s:
        return "研发项目"

    return "证据"


def _build_sources_map(sources):
    result = {}

    for item in (sources or []):
        if not isinstance(item, dict):
            continue

        cid = item.get("chunk_id")

        if cid:
            result[cid] = item

    return result


def _level_tag(level):
    level = level or ""

    if level == "E2":
        return '<span class="tag tag-e2">E2</span>'

    if level == "E3":
        return '<span class="tag tag-e3">E3</span>'

    return ""


def _chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _evidence_card_html(category, item, sources_map):
    level = item.get("evidence_level")
    claim = _esc(item.get("claim") or "未提供 Claim")
    chunk_id = _esc(item.get("chunk_id") or "未提供 chunk_id")
    meta = sources_map.get(item.get("chunk_id")) or {}

    title = _esc(meta.get("title") or "")
    source = _esc(meta.get("source") or "")

    cond_html = ""

    historical_condition = item.get("historical_condition")

    if historical_condition:
        cond_html = (
            '<div class="evidence-cond">历史条件：'
            + _esc(historical_condition)
            + "</div>"
        )

    return (
        '<div class="evidence-card">'
        + _level_tag(level)
        + ' <span class="tag" style="background:#f1f5f9;color:#334155;">'
        + _esc(category)
        + "</span>"
        + '<div class="evidence-claim">'
        + claim
        + "</div>"
        + cond_html
        + '<div class="evidence-meta">'
        + (title + " · " if title else "")
        + chunk_id
        + (" · " + source if source else "")
        + "</div></div>"
    )


# ============================================================
# 3. Region renderers
# ============================================================

def render_task_card(
    so,
    query=None,
    context_resolution=None,
    effective_product_resolution=None,
    conversation_subject=None,
):
    requirement = so.get("requirement") or {}

    req_text = requirement.get("text") or ""

    if context_resolution is not None:
        # Live 模式：产品优先用 Conversation Subject（用户当前在讨论谁）
        subject_product = None

        if conversation_subject:
            sp = (conversation_subject.get("product") or {})

            if sp.get("status") == "RESOLVED":
                subject_product = sp.get("value")

        if subject_product:
            product = subject_product

        elif effective_product_resolution is not None:
            product = (
                effective_product_display_value(
                    effective_product_resolution
                )
                or "—"
            )

        else:
            product = product_display_value(context_resolution) or "—"

    else:
        # Frozen 模式：继续使用冻结数据字段
        product = extract_product(req_text) or "—"

    application = (
        _extract_application(
            req_text,
            so.get("condition_gap"),
        )
        or "—"
    )

    metric = _extract_metric(req_text) or req_text or "—"

    scene_line = (
        _esc(SCENE_ID)
        + "｜"
        + _esc(application)
        + " · "
        + _esc(product)
    )

    html = (
        '<div class="block">'
        + '<div class="scene-line">'
        + scene_line
        + "</div>"
        + '<div class="task-grid">'
        + '<div><div class="task-label">产品</div>'
        + '<div class="task-value">'
        + _esc(product)
        + "</div></div>"
        + '<div><div class="task-label">应用场景</div>'
        + '<div class="task-value">'
        + _esc(application)
        + "</div></div>"
        + '<div><div class="task-label">关键指标</div>'
        + '<div class="task-value-metric">'
        + _esc(metric)
        + "</div></div>"
        + "</div></div>"
    )

    st.markdown(
        html,
        unsafe_allow_html=True,
    )


def render_risk_block(so):
    risk_summary = so.get("risk_summary") or "当前未生成风险预审结论。"

    historical = so.get("historical_evidence") or []
    technical = so.get("technical_evidence") or []

    has_e2 = any(
        isinstance(i, dict)
        and i.get("evidence_level") == "E2"
        for i in historical
    )

    has_e3 = any(
        isinstance(i, dict)
        and i.get("evidence_level") == "E3"
        for i in technical
    )

    gap = so.get("evidence_gap")
    gap_statement = (
        gap.get("statement")
        if isinstance(gap, dict)
        else gap
    )

    has_gap = bool(gap_statement and str(gap_statement).strip())

    tags = []

    if has_e2:
        tags.append('<span class="tag tag-e2">历史案例 E2</span>')

    if has_e3:
        tags.append('<span class="tag tag-e3">技术 / 标准 E3</span>')

    if has_gap:
        tags.append('<span class="tag tag-gap">缺直接验证</span>')

    tag_row = (
        '<div class="tag-row">' + "".join(tags) + "</div>"
        if tags
        else ""
    )

    html = (
        '<div class="risk-block">'
        + '<div class="risk-title">风险预审结论</div>'
        + '<div class="risk-summary">'
        + _esc(risk_summary)
        + "</div>"
        + '<div class="muted-note" style="margin-top:6px;">'
        + "历史证据仅用于风险提示，不能直接外推至当前场景。"
        + "</div>"
        + tag_row
        + "</div>"
    )

    st.markdown(
        html,
        unsafe_allow_html=True,
    )


def render_evidence_chain(so):
    st.markdown(
        '<div class="section-title">证据链</div>',
        unsafe_allow_html=True,
    )

    sources_map = _build_sources_map(so.get("sources"))

    historical = so.get("historical_evidence") or []
    technical = so.get("technical_evidence") or []

    cards = []

    for item in historical:
        if isinstance(item, dict):
            cards.append(
                _evidence_card_html(
                    "历史案例",
                    item,
                    sources_map,
                )
            )

    for item in technical:
        if not isinstance(item, dict):
            continue

        source = (
            sources_map.get(item.get("chunk_id"))
            or {}
        ).get("source")

        category = _classify_source(source)

        cards.append(
            _evidence_card_html(
                category,
                item,
                sources_map,
            )
        )

    if not cards:
        st.info("当前未返回 Evidence。")
        return

    for row in _chunks(cards, 3):
        cols = st.columns(3)

        for idx, card in enumerate(row):
            with cols[idx]:
                st.markdown(
                    card,
                    unsafe_allow_html=True,
                )


def render_condition_gap(so):
    st.markdown(
        '<div class="section-title">为什么历史案例不能直接外推？</div>',
        unsafe_allow_html=True,
    )

    condition_gap = so.get("condition_gap") or []

    rows = []

    for item in condition_gap:
        if not isinstance(item, dict):
            continue

        rows.append(
            "<tr><td>"
            + _esc(item.get("dimension") or "—")
            + "</td><td>"
            + _esc(item.get("historical") or "—")
            + '</td><td class="cur">'
            + _esc(item.get("current") or "—")
            + "</td></tr>"
        )

    if not rows:
        st.info("当前未识别 Condition Gap。")
        return

    table = (
        '<table class="gap-table">'
        + "<thead><tr><th>维度</th>"
        + "<th>历史证据条件</th><th>当前客户条件</th></tr></thead>"
        + "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )

    st.markdown(
        table,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="conclusion-line">'
        + "历史证据与当前条件在应用场景、温度及耐折要求上存在差异，"
        + "因此只能用于风险提示，不能直接证明当前通过或失败。"
        + "</div>",
        unsafe_allow_html=True,
    )


def render_gap_and_validation(
    so,
    developer_mode=False,
    priority_changes=None,
    hold=False,
):
    st.markdown(
        '<div class="section-title">当前还缺什么证据？</div>',
        unsafe_allow_html=True,
    )

    gap = so.get("evidence_gap")
    gap_statement = (
        gap.get("statement")
        if isinstance(gap, dict)
        else gap
    )

    if gap_statement:
        st.markdown(
            '<div class="gap-block">'
            + '<div class="gap-kicker">Evidence Gap</div>'
            + _esc(str(gap_statement))
            + "</div>",
            unsafe_allow_html=True,
        )

        refs = (
            gap.get("source_refs")
            if isinstance(gap, dict)
            else []
        ) or []

        if refs:
            with st.expander("查看证据引用"):
                st.write(
                    " · ".join(
                        str(x)
                        for x in refs
                    )
                )

    st.markdown(
        '<div class="section-title">下一步优先验证</div>',
        unsafe_allow_html=True,
    )

    recommendations = as_list(
        so.get("recommended_validation")
    )

    if not recommendations:
        st.info("当前未生成验证建议。")
        return

    for item in recommendations:
        if not isinstance(item, dict):
            continue

        priority = item.get("priority") or "P0"
        action = _esc(item.get("action") or "未提供验证动作")
        reason = item.get("reason")

        reason_html = (
            '<div class="reason">为什么：'
            + _esc(reason)
            + "</div>"
            if reason
            else ""
        )

        if priority == "P0":
            st.markdown(
                '<div class="p0-block">'
                + '<span class="tag" style="background:#dcfce7;color:#166534;">P0</span>'
                + ' <span class="p0-action">'
                + action
                + "</span>"
                + reason_html
                + "</div>",
                unsafe_allow_html=True,
            )

        else:
            st.markdown(
                '<div class="px-block">'
                + "<b>"
                + _esc(priority)
                + "</b>"
                + ' <span class="px-action">'
                + action
                + "</span>"
                + reason_html
                + "</div>",
                unsafe_allow_html=True,
            )

    if developer_mode:
        if hold:
            st.caption(
                "DISPLAY_PRIORITY_NORMALIZATION_HOLD｜"
                "未识别到直接 -30℃ 验证，保留原始 priority。"
            )

        if priority_changes:
            with st.expander("开发调试｜优先级归一（原始 → 展示）"):
                for change in priority_changes:
                    st.write(
                        "动作"
                        + str(change["index"] + 1)
                        + "："
                        + str(change["original"])
                        + " → "
                        + str(change["display"])
                    )


def render_sources(so):
    sources = so.get("sources") or []

    with st.expander(
        "证据来源 · " + str(len(sources)) + "项"
    ):
        rows = []

        for item in sources:
            if not isinstance(item, dict):
                continue

            rows.append({
                "类别":
                    _classify_source(item.get("source")),

                "标题":
                    item.get("title"),

                "Chunk ID":
                    item.get("chunk_id"),

                "来源":
                    item.get("source"),
            })

        if rows:
            st.dataframe(
                rows,
                width="stretch",
                hide_index=True,
            )

        else:
            st.info("当前未返回 Sources。")


def render_boundary():
    with st.expander("回答边界"):
        st.write(
            "历史 Evidence 用于风险参考，"
            "不直接等于当前场景实测结果。"
        )

        st.write(
            "-10℃ / -20℃结果不得静默外推至 -30℃。"
        )

        st.write(
            "沙发革条件不得静默外推至汽车内饰革。"
        )

        st.write(
            "证据不足时输出 Evidence Gap，"
            "不输出无证据的确定性 Pass / Fail。"
        )


def render_main_product(
    so,
    developer_mode,
    query=None,
    priority_changes=None,
    hold=False,
    context_resolution=None,
    effective_product_resolution=None,
    conversation_subject=None,
):
    render_task_card(
        so,
        query,
        context_resolution,
        effective_product_resolution,
        conversation_subject,
    )

    if developer_mode and context_resolution:
        product = context_resolution.get("product") or {}

        with st.expander("开发调试｜Product Resolution"):
            st.write(
                "PRODUCT_RESOLUTION_STATUS：",
                product.get("status"),
            )
            st.write(
                "PRODUCT_CANDIDATES：",
                " · ".join(
                    product.get("candidate_products") or []
                ),
            )
            st.write(
                "PRODUCT_SUPPORTING_REFS：",
                " · ".join(
                    product.get("supporting_refs") or []
                ),
            )
            st.write(
                "RESOLUTION_BASIS：",
                product.get("resolution_basis"),
            )

    render_risk_block(so)
    render_evidence_chain(so)
    render_condition_gap(so)
    render_gap_and_validation(
        so,
        developer_mode,
        priority_changes,
        hold,
    )
    render_sources(so)
    render_boundary()


# ============================================================
# 4. Knowledge Curator (附加链，Live only)
# ============================================================

def _run_curator_isolated(
    result,
    runtime_config=None,
):
    """
    Knowledge Curator 是附加链。
    只在主回答安全通过后尝试；任何失败都被隔离，
    不影响主回答展示。
    """
    safety = (
        result.get("safety")
        or {}
    )

    if safety.get("status") != "PASS":
        return {
            "status": "SKIPPED_SAFETY_NOT_PASS",
        }

    # 只有 AUTO001_SCOPED 才运行 Knowledge Curator
    if result.get("context_scope") != SCOPE_AUTO001:
        return {
            "status": "SKIPPED_NOT_AUTO001_SCOPED",
        }

    # Curator 使用 policy-grounded output（Product Role + Scope + Formulation + Validation Policy 全部完成后）
    curator_result = dict(result)

    curator_result["structured_output"] = (
        result.get("policy_grounded_output")
        or result.get("effective_grounded_output")
        or result.get("structured_output")
    )

    try:
        outcome = run_knowledge_curator(
            curator_result,
            runtime_config=runtime_config,
        )

    except Exception as exc:
        return {
            "status": "CURATOR_UNAVAILABLE",
            "error": repr(exc),
        }

    # Curator Topic / Action Policy Guard（保留 raw candidate 供审计）
    candidate = outcome.get("candidate")

    if candidate:
        cf = result.get("current_formulation")

        guarded_candidate, curator_policy_changes = (
            guard_curator_candidate_policy(candidate, cf)
        )

        outcome["raw_curator_candidate"] = candidate
        outcome["policy_guarded_candidate"] = guarded_candidate
        outcome["curator_policy_changes"] = curator_policy_changes
        outcome["candidate"] = guarded_candidate

    return outcome


# ============================================================
# 4b. Runtime config helpers
# ============================================================

def _env_config():
    return resolve_runtime_llm_config()


def _current_runtime_config():
    return resolve_runtime_llm_config(
        st.session_state.get("runtime_override")
    )


def _build_active_scene(result):
    """从结果构建/更新 ephemeral scene context（product 来自 conversation subject，非 Evidence）。"""
    if not isinstance(result, dict):
        return None

    previous = st.session_state.get("active_scene_context")
    subject = result.get("conversation_subject")

    scene = build_next_scene_context(
        previous,
        subject,
        result.get("context_scope"),
    )

    if isinstance(scene, dict):
        scene = dict(scene)

        if scene.get("source_turn_id") is None:
            scene["source_turn_id"] = result.get("query")

    return scene


def _render_runtime_settings():
    env_cfg = _env_config()

    provider_index = (
        PROVIDERS.index(env_cfg.provider)
        if env_cfg.provider in PROVIDERS
        else 0
    )

    provider = st.selectbox(
        "Provider",
        PROVIDERS,
        index=provider_index,
        key="cfg_provider",
    )

    model = st.text_input(
        "Model",
        value=env_cfg.model,
        key="cfg_model",
    )

    base_url = st.text_input(
        "Base URL",
        value=env_cfg.base_url,
        key="cfg_base_url",
    )

    if env_cfg.api_key:
        st.caption(
            "已检测到本机环境API Key，留空即可继续使用。"
        )

    else:
        st.caption(
            "未检测到本机环境API Key，请输入你的API Key。"
        )

    api_key = st.text_input(
        "API Key",
        type="password",
        value="",
        key="cfg_api_key",
    )

    c1, c2 = st.columns(2)

    with c1:
        if st.button(
            "应用本次会话配置",
            key="apply_cfg",
        ):
            st.session_state["runtime_override"] = {
                "provider": provider,
                "model": (model or "").strip(),
                "base_url": (base_url or "").strip(),
                "api_key": (api_key or "").strip(),
            }

    with c2:
        if st.button(
            "恢复本机环境配置",
            key="reset_cfg",
        ):
            for key in [
                "runtime_override",
                "cfg_provider",
                "cfg_model",
                "cfg_base_url",
                "cfg_api_key",
            ]:
                st.session_state.pop(key, None)

            st.rerun()


def _render_runtime_summary():
    cfg = _current_runtime_config()
    d = public_runtime_summary(cfg)

    source = (
        "本次会话"
        if d["config_source"] == "SESSION"
        else "本机环境"
    )

    key_status = "已配置" if d["api_key_available"] else "未配置"

    st.markdown(
        '<div class="muted-note">'
        + "模型："
        + _esc(d["model"] or "（未配置）")
        + "｜配置："
        + _esc(source)
        + "｜API Key："
        + _esc(key_status)
        + "</div>",
        unsafe_allow_html=True,
    )


def render_knowledge_curator(
    curator_result,
    developer_mode,
):
    if not isinstance(curator_result, dict):
        return

    status = curator_result.get("status")
    candidate = curator_result.get("candidate")

    gov_label = None

    if candidate and candidate.get("candidate_id"):
        gov_status = get_current_governance_status(
            candidate.get("candidate_id")
        )
        gov_label = status_display_label(gov_status)

    title_html = '<div class="section-title">知识更新建议'

    if gov_label:
        title_html += (
            ' <span style="font-size:12px;color:var(--muted);font-weight:500;">'
            + _esc(gov_label)
            + "</span>"
        )

    title_html += "</div>"

    st.markdown(
        title_html,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="muted-note">'
        + "本次提问暴露出的知识缺口会形成候选更新建议，"
        + "但不会自动写入企业正式知识库。"
        + "</div>",
        unsafe_allow_html=True,
    )

    if status in {
        "CURATOR_UNAVAILABLE",
        "GUARD_HOLD",
        "SKIPPED_SAFETY_NOT_PASS",
    }:
        st.markdown(
            '<div class="muted-note" style="margin-top:8px;">'
            + "Knowledge Curator暂不可用 / 本次未生成候选建议。"
            + "</div>",
            unsafe_allow_html=True,
        )
        return

    if status == "NO_UPDATE":
        st.markdown(
            '<div class="muted-note" style="margin-top:8px;">'
            + "本次问题已被现有知识较充分覆盖，"
            + "未生成新的 Knowledge Update Candidate。"
            + "</div>",
            unsafe_allow_html=True,
        )
        return

    if candidate is None:
        st.markdown(
            '<div class="muted-note" style="margin-top:8px;">'
            + "本次未生成新的 Knowledge Update Candidate。"
            + "</div>",
            unsafe_allow_html=True,
        )
        return

    target_hint = candidate.get("target_hint") or {}

    correction_intents = get_candidate_correction_intents(
        candidate.get("candidate_id"),
        load_correction_intents(),
    )

    if correction_intents:
        legacy_aks = [
            it.get("legacy_knowledge_record_id")
            for it in correction_intents
        ]

        st.markdown(
            '<div style="margin-top:10px;">'
            + '<span class="tag" style="background:#fef2f2;color:#b91c1c;">'
            + "治理类型：Correction"
            + "</span></div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="muted-note" style="margin-top:6px;">'
            + "该候选知识同时用于纠正历史 Derived Knowledge 记录。"
            + "</div>",
            unsafe_allow_html=True,
        )

        for ak in legacy_aks:
            st.markdown(
                '<div style="font-size:13px;color:var(--text);margin-top:2px;">'
                + "纠正对象："
                + _esc(ak)
                + "</div>",
                unsafe_allow_html=True,
            )

    rows = [
        ("知识缺口", candidate.get("knowledge_gap_summary")),
        (
            "与现有知识关系",
            candidate.get("relationship_to_existing_knowledge"),
        ),
        ("建议知识主题", target_hint.get("suggested_topic")),
    ]

    for label, value in rows:
        st.markdown(
            '<div style="margin-top:8px;">'
            + '<div class="task-label">'
            + _esc(label)
            + "</div>"
            + '<div style="font-size:14px;color:var(--text);line-height:1.55;">'
            + _esc(value or "（未提供）")
            + "</div></div>",
            unsafe_allow_html=True,
        )

    evidence_needed = candidate.get("evidence_needed") or []

    if evidence_needed:
        st.markdown(
            '<div class="task-label" style="margin-top:8px;">'
            + "建议补充什么Evidence</div>",
            unsafe_allow_html=True,
        )

        for item in evidence_needed:
            st.markdown(
                '<div style="font-size:13.5px;color:var(--text);margin:2px 0;">'
                + "· "
                + _esc(item)
                + "</div>",
                unsafe_allow_html=True,
            )

    if developer_mode:
        with st.expander("开发调试｜Curator 内部字段"):
            st.write(
                "Decision Type：",
                candidate.get("decision_type"),
            )

            st.write(
                "Recommended KB Action：",
                candidate.get("recommended_kb_action"),
            )

            st.write(
                "candidate_key：",
                candidate.get("candidate_key"),
            )

            st.write(
                "traceability_status：",
                candidate.get("traceability_status"),
            )

            st.write(
                "related_existing_refs：",
                " · ".join(
                    candidate.get("related_existing_refs")
                    or []
                ),
            )

            st.write(
                "review_status：",
                candidate.get("review_status"),
            )


def render_human_review(candidate):
    """人工审核 UI（低权重，仅 Candidate 存在时）。"""
    if not isinstance(candidate, dict):
        return

    candidate_id = candidate.get("candidate_id")

    if not candidate_id:
        return

    current_status = get_current_governance_status(candidate_id)

    if current_status == "PENDING_REVIEW":
        st.markdown(
            '<div class="section-title">人工审核</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="muted-note">'
            + "批准仅生成已审核 Derived Knowledge，"
            + "不写入企业原始资料，也不会自动更新当前 RAG。"
            + "</div>",
            unsafe_allow_html=True,
        )

        correction_intents = get_candidate_correction_intents(
            candidate_id,
            load_correction_intents(),
        )

        if correction_intents:
            legacy_aks = [
                it.get("legacy_knowledge_record_id")
                for it in correction_intents
            ]

            st.markdown(
                '<div style="margin-top:8px;">'
                + '<span class="tag" style="background:#fef2f2;color:#b91c1c;">'
                + "治理类型：Correction"
                + "</span></div>",
                unsafe_allow_html=True,
            )

            for ak in legacy_aks:
                st.markdown(
                    '<div style="font-size:13px;color:var(--text);margin-top:2px;">'
                    + "纠正旧记录："
                    + _esc(ak)
                    + "</div>",
                    unsafe_allow_html=True,
                )

        reviewer = st.text_input(
            "审核人",
            key="reviewer_" + candidate_id,
        )

        comment = st.text_area(
            "审核意见",
            key="comment_" + candidate_id,
        )

        c1, c2, c3 = st.columns(3)

        with c1:
            if st.button(
                "批准并生成入库项",
                key="approve_" + candidate_id,
            ):
                _do_review(
                    candidate,
                    "APPROVE",
                    reviewer,
                    comment,
                )

        with c2:
            if st.button(
                "需要补证",
                key="nme_" + candidate_id,
            ):
                _do_review(
                    candidate,
                    "NEED_MORE_EVIDENCE",
                    reviewer,
                    comment,
                )

        with c3:
            if st.button(
                "拒绝",
                key="reject_" + candidate_id,
            ):
                _do_review(
                    candidate,
                    "REJECT",
                    reviewer,
                    comment,
                )

    else:
        review_status = get_review_status(candidate_id)

        review_label = {
            "APPROVED_FOR_KB": "已批准",
            "NEED_MORE_EVIDENCE": "需要补证",
            "REJECTED": "已拒绝",
        }.get(review_status, review_status)

        st.markdown(
            '<div style="margin-top:10px;">'
            + '<span class="tag" style="background:#f1f5f9;color:#334155;">'
            + "人工审核："
            + _esc(review_label)
            + "</span></div>",
            unsafe_allow_html=True,
        )

        if current_status == "APPROVED_FOR_KB":
            st.markdown(
                '<div style="margin-top:6px;">'
                + '<span class="tag" style="background:#f1f5f9;color:#334155;">'
                + "知识状态：等待写入 Derived Knowledge"
                + "</span></div>",
                unsafe_allow_html=True,
            )
            st.caption("当前 Runtime：未纳入")
            render_write_gate(candidate_id)

        elif current_status == "WRITTEN_TO_DERIVED_KB":
            render_write_gate(candidate_id)


def render_write_gate(candidate_id):
    """Knowledge Write Gate UI（仅 APPROVED_FOR_KB）。"""
    correction_intents = get_candidate_correction_intents(
        candidate_id,
        load_correction_intents(),
    )

    if correction_intents:
        st.markdown(
            '<div class="muted-note" style="margin-top:8px;">'
            + "本次写入将生成新的 Correction Derived Knowledge，"
            + "并建立与旧AK的更正关系；旧AK不会被修改或删除。"
            + "</div>",
            unsafe_allow_html=True,
        )

    write_status = get_write_status(candidate_id)

    if write_status == "WRITTEN_TO_DERIVED_KB":
        write_decision = get_write_decision(candidate_id)

        st.markdown(
            '<div style="margin-top:10px;">'
            + '<span class="tag" style="background:#f1f5f9;color:#334155;">'
            + "知识状态：已写入 Derived Knowledge"
            + "</span></div>",
            unsafe_allow_html=True,
        )

        if write_decision:
            st.caption(
                "路径："
                + str(write_decision.get("vault_relative_path") or "")
            )

        st.caption("当前 Runtime：未纳入")
        st.caption("Future Snapshot：等待 Human Gate")
        return

    with st.expander("知识写入"):
        role_label = st.selectbox(
            "Reviewer Role",
            ["Y", "研发工程师"],
            key="wrole_" + candidate_id,
        )

        reviewer_name = st.text_input(
            "Reviewer Name",
            key="wname_" + candidate_id,
        )

        evidence_confirmed = st.checkbox(
            "我已确认该知识项所引用的正式 Source 可追溯，"
            "并同意写入已审核派生知识层。",
            key="wconf_" + candidate_id,
        )

        write_comment = st.text_area(
            "Write Comment",
            key="wcomment_" + candidate_id,
        )

        if st.button(
            "写入已审核派生知识",
            key="write_" + candidate_id,
        ):
            _do_write(
                candidate_id,
                role_label,
                reviewer_name,
                evidence_confirmed,
                write_comment,
            )


def _do_write(candidate_id, role_label, reviewer_name, evidence_confirmed, write_comment):
    try:
        approved_record = get_approved_record(candidate_id)

        if not approved_record:
            st.warning("未找到对应的已审核记录。")
            return

        role_value = "Y" if role_label == "Y" else "R&D_ENGINEER"

        result = write_approved_knowledge(
            approved_record,
            reviewer_role=role_value,
            reviewer_name=reviewer_name,
            evidence_confirmed=evidence_confirmed,
            write_comment=write_comment,
        )

        if result["result_status"] == "WRITTEN_TO_DERIVED_KB":
            st.success(
                "已写入 Derived Knowledge："
                + str(result.get("vault_relative_path") or "")
            )

        elif result["result_status"] == "ALREADY_WRITTEN":
            st.info("该知识项已写入 Derived Knowledge。")

        else:
            st.warning(
                "写入未执行："
                + (result.get("reason") or result["result_status"])
            )

        st.rerun()

    except Exception:
        st.error("写入失败，请重试。")


def _do_review(candidate, decision, reviewer, comment):
    try:
        result = review_candidate(
            candidate,
            decision,
            reviewer=reviewer,
            review_comment=comment,
        )

        if result["result_status"] == "REVIEWED":
            st.success("已记录人工审核。")

        elif result["result_status"] == "ALREADY_REVIEWED":
            st.info("该知识更新建议已完成人工审核。")

        else:
            st.warning(
                "审核未执行：" + result["result_status"]
            )

        st.rerun()

    except Exception:
        st.error("审核结果保存失败，请重试。")


def render_history_mode():
    st.markdown(
        '<div class="section-title">历史记录</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="muted-note">'
        + "查看历史研发预审、知识更新与人工治理过程。"
        + "已完成的审核与写入记录为只读审计记录。"
        + "</div>",
        unsafe_allow_html=True,
    )

    records = load_history()

    col1, col2, col3 = st.columns(3)

    with col1:
        search_text = st.text_input(
            "搜索",
            placeholder="Query / Topic / Candidate ID / Knowledge Record ID",
            key="hist_search",
        )

    with col2:
        status_label = st.selectbox(
            "状态",
            [
                "全部",
                "待人工审核",
                "已批准待写入",
                "需要补证",
                "已拒绝",
                "已写入Derived Knowledge",
            ],
            key="hist_status",
        )

    with col3:
        decision_types = sorted({
            r.get("candidate_decision_type")
            for r in records
            if r.get("candidate_decision_type")
        })

        dt_label = st.selectbox(
            "Decision Type",
            ["全部"] + decision_types,
            key="hist_dt",
        )

    status_value_map = {
        "全部": None,
        "待人工审核": "PENDING_REVIEW",
        "已批准待写入": "APPROVED_FOR_KB",
        "需要补证": "NEED_MORE_EVIDENCE",
        "已拒绝": "REJECTED",
        "已写入Derived Knowledge": "WRITTEN_TO_DERIVED_KB",
    }

    filtered = filter_history(
        search_history(records, search_text),
        status=status_value_map.get(status_label),
        decision_type=(None if dt_label == "全部" else dt_label),
    )

    st.caption("共 " + str(len(filtered)) + " 条记录")

    if not filtered:
        st.info("暂无历史记录。")
        return

    for rec in filtered:
        _render_history_card(rec)


def _render_history_card(rec):
    status = rec.get("current_governance_status")
    status_label = status_display_label(status) or "TRACE_ONLY"

    time_str = str(rec.get("queried_at") or "")[:16]
    query = (rec.get("query") or "（无问题文本）")[:44]
    decision_type = rec.get("candidate_decision_type") or "—"
    candidate_id = rec.get("candidate_id") or "—"

    correction_badge = ""

    if rec.get("correction_status") == "CORRECTION_PENDING":
        correction_badge = (
            '<span class="tag" style="background:#fef2f2;color:#b91c1c;margin-left:6px;">'
            + "更正待处理"
            + "</span>"
        )

    elif rec.get("correction_status") == "SUPERSEDED":
        correction_badge = (
            '<span class="tag" style="background:#f0fdf4;color:#15803d;margin-left:6px;">'
            + "已被后续知识更正"
            + "</span>"
        )

    elif rec.get("corrects_legacy_ak"):
        correction_badge = (
            '<span class="tag" style="background:#fef2f2;color:#b91c1c;margin-left:6px;">'
            + "Correction"
            + "</span>"
        )

    st.markdown(
        '<div class="block" style="margin-bottom:10px;">'
        + '<div style="display:flex;justify-content:space-between;align-items:center;">'
        + '<div class="muted-note">'
        + _esc(time_str)
        + "</div>"
        + '<span style="display:inline-flex;align-items:center;">'
        + '<span class="tag" style="background:#f1f5f9;color:#334155;">'
        + _esc(status_label)
        + "</span>"
        + correction_badge
        + "</span>"
        + "</div>"
        + '<div style="font-size:14px;color:var(--text);margin-top:6px;">'
        + _esc(query)
        + "</div>"
        + '<div class="muted-note" style="margin-top:4px;">'
        + "类型："
        + _esc(decision_type)
        + " ｜ Candidate ID："
        + _esc(candidate_id)
        + "</div>"
        + "</div>",
        unsafe_allow_html=True,
    )

    with st.expander("查看详情"):
        _render_history_detail(rec)


def _render_history_detail(rec):
    st.markdown("**用户问题**")
    st.write(rec.get("query") or "（无）")

    st.markdown("**RAG预审结果摘要**")
    st.write(rec.get("answer_summary") or "（无）")

    st.markdown("**Knowledge Curator / Candidate**")
    st.write(
        "Decision Type："
        + str(rec.get("candidate_decision_type") or "尚未执行")
    )
    st.write(
        "知识缺口摘要："
        + str(rec.get("candidate_summary") or "尚未执行")
    )
    st.write(
        "建议知识主题："
        + str(rec.get("candidate_topic") or "尚未执行")
    )

    refs = rec.get("source_refs") or []

    if refs:
        st.caption("Source refs：" + " · ".join(str(x) for x in refs))

    st.markdown("**Human Review**")

    if rec.get("review_id"):
        st.write(
            "决策："
            + str(rec.get("review_decision") or "")
        )
        st.write(
            "审核人："
            + str(rec.get("reviewer") or "")
        )
        st.write(
            "审核意见："
            + str(rec.get("review_comment") or "（无）")
        )

    else:
        st.write("尚未执行")

    st.markdown("**Knowledge Write**")

    if rec.get("write_id"):
        st.write(
            "写入审核人："
            + str(rec.get("write_reviewer_name") or "")
            + "（"
            + str(rec.get("write_reviewer_role") or "")
            + "）"
        )
        st.write(
            "路径："
            + str(rec.get("vault_relative_path") or "")
        )

    else:
        st.write("尚未执行")

    if rec.get("correction_status"):
        st.markdown("**更正关系**")

        if rec.get("correction_status") == "SUPERSEDED":
            st.write("更正状态：已被后续知识更正")
            st.write("更正记录：" + str(rec.get("correction_new_ak") or ""))

        else:
            st.write("更正状态：更正待处理")

    elif rec.get("corrects_legacy_ak"):
        st.markdown("**更正关系**")
        st.write("记录类型：Correction / Superseding Derived Knowledge")

        for ak in rec.get("corrects_legacy_ak"):
            st.write("纠正：" + str(ak))

    op = rec.get("allowed_operation")
    candidate_id = rec.get("candidate_id")

    if op in {"HUMAN_REVIEW", "KNOWLEDGE_WRITE"} and candidate_id:
        full_candidate = get_candidate(candidate_id)

        if full_candidate:
            st.markdown(
                '<div class="muted-note" style="margin-top:8px;">'
                + "可继续合法操作："
                + _esc(
                    "人工审核"
                    if op == "HUMAN_REVIEW"
                    else "知识写入"
                )
                + "</div>",
                unsafe_allow_html=True,
            )

            render_human_review(full_candidate)


def render_generic_task_card(live_result):
    product = (
        product_display_value(live_result.get("context_resolution"))
        or "未从当前证据中确定"
    )

    html = (
        '<div class="block">'
        + '<div class="scene-line">问题类型：通用技术咨询</div>'
        + '<div class="task-grid">'
        + '<div><div class="task-label">产品</div>'
        + '<div class="task-value">'
        + _esc(product)
        + "</div></div>"
        + '<div><div class="task-label">应用场景</div>'
        + '<div class="task-value">未限定</div></div>'
        + '<div><div class="task-label">关键指标</div>'
        + '<div class="task-value-metric">未限定</div></div>'
        + "</div></div>"
    )

    st.markdown(html, unsafe_allow_html=True)


def _render_scope_audit(live_result):
    with st.expander("开发调试｜Context Scope / Formulation"):
        st.write("CONTEXT_SCOPE：", live_result.get("context_scope"))
        st.write(
            "SCOPE_RESOLUTION_BASIS：",
            live_result.get("scope_resolution_basis"),
        )
        st.write(
            "SCENE_INHERITANCE_USED：",
            live_result.get("scene_inheritance_used"),
        )
        st.write(
            "ACTIVE_SCENE_CONTEXT：",
            json.dumps(
                st.session_state.get("active_scene_context"),
                ensure_ascii=False,
            ),
        )
        st.write(
            "CURRENT_QUERY_EXPLICIT_SCOPE_SIGNALS：",
            json.dumps(
                explicit_scope_signals(live_result.get("query") or ""),
                ensure_ascii=False,
            ),
        )

        subject_audit = build_subject_audit(
            live_result.get("conversation_subject"),
            live_result.get("context_resolution"),
            live_result.get("effective_product_resolution"),
        )
        st.write(
            "CONVERSATION_SUBJECT_PRODUCT：",
            subject_audit.get("conversation_subject_product"),
        )
        st.write(
            "CONVERSATION_SUBJECT_STATUS：",
            subject_audit.get("conversation_subject_status"),
        )
        st.write(
            "CONVERSATION_SUBJECT_BASIS：",
            subject_audit.get("conversation_subject_basis"),
        )
        st.write(
            "QUERY_EXPLICIT_PRODUCT：",
            subject_audit.get("query_explicit_product"),
        )
        st.write(
            "PREVIOUS_SCENE_PRODUCT：",
            subject_audit.get("previous_scene_product"),
        )
        st.write(
            "EVIDENCE_PRODUCT_STATUS：",
            subject_audit.get("evidence_product_status"),
        )
        st.write(
            "EVIDENCE_PRODUCT_CANDIDATES：",
            " · ".join(subject_audit.get("evidence_product_candidates") or []),
        )
        st.write(
            "QUERY_IS_EVIDENCE：",
            "NO",
        )
        st.write(
            "SESSION_CONTEXT_IS_EVIDENCE：",
            "NO",
        )

        cf = live_result.get("current_formulation") or {}

        st.write(
            "CURRENT_FORMULATION_STATUS：",
            cf.get("status"),
        )
        st.write(
            "CURRENT_FORMULATION_VALUE：",
            cf.get("value"),
        )
        st.write(
            "CURRENT_FORMULATION_SUPPORTING_REFS：",
            " · ".join(cf.get("supporting_refs") or []),
        )
        st.write(
            "HISTORICAL_FORMULATION_EVENTS：",
            json.dumps(
                cf.get("historical_events") or [],
                ensure_ascii=False,
            ),
        )
        st.write(
            "GROUNDING_CHANGES：",
            json.dumps(
                live_result.get("grounding_changes") or [],
                ensure_ascii=False,
            ),
        )
        st.write(
            "VALIDATION_POLICY_CHANGES：",
            json.dumps(
                live_result.get("validation_policy_changes") or [],
                ensure_ascii=False,
            ),
        )
        st.write(
            "CURATOR_ELIGIBLE：",
            live_result.get("context_scope") == SCOPE_AUTO001,
        )

        raw = live_result.get("context_resolution") or {}
        raw_product = raw.get("product") or {}

        st.write(
            "RAW_PRODUCT_RESOLUTION_STATUS：",
            raw_product.get("status"),
        )
        st.write(
            "RAW_PRODUCT_CANDIDATES：",
            " · ".join(raw_product.get("candidate_products") or []),
        )

        eff = live_result.get("effective_product_resolution") or {}

        st.write(
            "EFFECTIVE_PRODUCT_RESOLUTION_STATUS：",
            eff.get("status"),
        )
        st.write(
            "EFFECTIVE_PRODUCT：",
            eff.get("value"),
        )
        st.write(
            "PRODUCT_ROLE_MAP：",
            json.dumps(eff.get("roles") or {}, ensure_ascii=False),
        )
        st.write(
            "EFFECTIVE_PRODUCT_SUPPORTING_REFS：",
            " · ".join(eff.get("supporting_refs") or []),
        )
        st.write(
            "RESOLUTION_BASIS：",
            eff.get("resolution_basis"),
        )


def _render_generic_evidence(evidence):
    for item in evidence or []:
        if not isinstance(item, dict):
            continue

        title = item.get("title") or "（无标题）"
        chunk_id = item.get("chunk_id") or ""
        source = item.get("source") or ""

        st.markdown(
            "**" + _esc(title) + "**"
        )
        st.caption(
            _esc(chunk_id) + " · " + _esc(source)
        )


def render_generic_technical(live_result, developer_mode):
    render_generic_task_card(live_result)

    generic_answer = live_result.get("generic_answer") or {}

    st.markdown(
        '<div class="section-title">技术解答</div>',
        unsafe_allow_html=True,
    )

    st.write(
        generic_answer.get("generic_answer") or "（无）"
    )

    refs = generic_answer.get("evidence_refs") or []

    if refs:
        st.caption(
            "证据引用：" + " · ".join(str(x) for x in refs)
        )

    st.markdown(
        '<div class="section-title">证据链</div>',
        unsafe_allow_html=True,
    )

    _render_generic_evidence(live_result.get("evidence") or [])

    st.markdown(
        '<div class="muted-note" style="margin-top:8px;">'
        + "通用技术查询本次不进入AUTO-001知识更新治理流程。"
        + "</div>",
        unsafe_allow_html=True,
    )

    render_boundary()

    if developer_mode:
        _render_scope_audit(live_result)


def render_scope_hint(live_result, developer_mode):
    scope = live_result.get("context_scope")

    if scope == SCOPE_AMBIGUOUS:
        st.info(
            "当前问题尚未明确唯一研发场景，"
            "可补充产品、应用场景或目标指标。"
        )

    else:
        st.info("该问题与当前研发避坑知识域无关。")

    st.markdown(
        '<div class="muted-note" style="margin-top:8px;">'
        + "当前检索候选不足以建立可靠研发场景，"
        + "暂不作为正式证据链展示。"
        + "</div>",
        unsafe_allow_html=True,
    )

    render_boundary()

    if developer_mode:
        _render_scope_audit(live_result)

        with st.expander("开发调试｜本轮 Retriever Evidence"):
            st.json(live_result.get("evidence") or [])


# ============================================================
# 5. Page
# ============================================================

st.set_page_config(
    page_title="研发避坑 Agent",
    layout="wide",
)

st.markdown(
    DESIGN_CSS,
    unsafe_allow_html=True,
)

st.session_state.setdefault(
    "developer_mode",
    False,
)

st.session_state.setdefault(
    "active_scene_context",
    None,
)

developer_mode = st.session_state["developer_mode"]

st.title("研发避坑 Agent")

st.caption(
    "客户需求驱动 · 历史证据优先 · 条件差异识别 · "
    "Evidence Gap · 可追溯研发风险预审"
)


mode = st.radio(
    "演示方式",
    options=[
        "冻结主 Demo｜稳定演示",
        "实时提问｜Live Agent",
        "历史记录｜History",
    ],
    horizontal=True,
)

st.markdown(
    '<div class="muted-note" style="margin-top:-6px;margin-bottom:6px;">'
    + "演示数据为脱敏模拟数据。本系统用于证据整理与研发风险预审，"
    + "不替代工程师最终判断。"
    + "</div>",
    unsafe_allow_html=True,
)


# ============================================================
# 6. Frozen mode
# ============================================================

if mode.startswith(
    "冻结主 Demo"
):
    if not FROZEN_DEMO_PATH.exists():
        st.error(
            f"冻结 Demo 文件不存在：{FROZEN_DEMO_PATH}"
        )
        st.stop()

    frozen_data = load_json(
        str(FROZEN_DEMO_PATH)
    )

    render_main_product(
        frozen_data,
        developer_mode,
    )

    if developer_mode:
        with st.expander(
            "开发调试｜完整 Structured Output JSON"
        ):
            st.json(
                frozen_data
            )


# ============================================================
# 7. History mode
# ============================================================

elif mode.startswith(
    "历史记录"
):
    render_history_mode()


# ============================================================
# 8. Live mode
# ============================================================

else:
    st.markdown(
        '<div class="muted-note" style="margin-bottom:8px;">'
        + "实时模式会执行检索与生成，通常比冻结演示更慢。"
        + "现场路演建议优先使用冻结演示。"
        + "</div>",
        unsafe_allow_html=True,
    )

    with st.expander("运行设置"):
        _render_runtime_settings()

    _render_runtime_summary()

    query = st.text_area(
        "请输入研发问题",
        value=DEFAULT_QUERY,
        height=110,
        key="live_query",
    )

    run_button = st.button(
        "开始研发风险预审",
        type="primary",
        width="stretch",
    )

    if run_button:
        if not query.strip():
            st.error(
                "请输入研发问题。"
            )

        else:
            runtime_config = _current_runtime_config()
            config_errors = validate_runtime_llm_config(
                runtime_config
            )

            if config_errors:
                st.warning(
                    "实时提问需要有效的模型配置。请展开‘运行设置’，"
                    "使用本机环境配置或填写本次会话API Key。"
                )

                for error in config_errors:
                    st.warning(error)

            else:
                try:
                    with st.spinner(
                        "正在检索历史证据并进行风险预审，请稍候……"
                    ):
                        result = run_live(
                            query.strip(),
                            runtime_config=runtime_config,
                            previous_scene_context=st.session_state.get(
                                "active_scene_context"
                            ),
                        )

                    st.session_state[
                        "live_result"
                    ] = result

                    st.session_state[
                        "live_result_query"
                    ] = query.strip()

                    st.session_state[
                        "active_scene_context"
                    ] = _build_active_scene(result)

                    st.session_state[
                        "curator_result"
                    ] = _run_curator_isolated(
                        result,
                        runtime_config,
                    )

                except Exception as exc:
                    st.session_state.pop(
                        "live_result",
                        None,
                    )

                    st.session_state.pop(
                        "curator_result",
                        None,
                    )

                    st.error(
                        "实时链路未通过 Safety / Contract Guard。"
                    )

                    st.exception(
                        exc
                    )

    live_result = st.session_state.get(
        "live_result"
    )

    if live_result:
        st.markdown(
            "## 实时预审结果"
        )

        context_scope = live_result.get("context_scope")

        if context_scope == SCOPE_GENERIC:
            render_generic_technical(live_result, developer_mode)

        elif context_scope == SCOPE_AUTO001:
            grounded_so = (
                live_result.get("policy_grounded_output")
                or live_result.get("effective_grounded_output")
                or live_result.get("structured_output")
                or {}
            )

            display_so, priority_changes, hold = (
                normalize_auto001_validation_for_display(
                    grounded_so
                )
            )

            render_main_product(
                display_so,
                developer_mode,
                query=live_result.get("query"),
                priority_changes=priority_changes,
                hold=hold,
                context_resolution=live_result.get("context_resolution"),
                effective_product_resolution=live_result.get(
                    "effective_product_resolution"
                ),
                conversation_subject=live_result.get(
                    "conversation_subject"
                ),
            )

            curator_result = st.session_state.get("curator_result")

            render_knowledge_curator(
                curator_result,
                developer_mode,
            )

            candidate = (curator_result or {}).get("candidate")

            if candidate:
                render_human_review(candidate)

            if developer_mode:
                safety = live_result.get("safety") or {}

                c1, c2, c3, c4 = st.columns(4)

                with c1:
                    st.metric(
                        "Safety",
                        safety.get("status", "UNKNOWN"),
                    )

                with c2:
                    st.metric(
                        "Citation",
                        safety.get(
                            "citation_correctness",
                            "UNKNOWN",
                        ),
                    )

                with c3:
                    st.metric(
                        "Unsupported Claims",
                        safety.get(
                            "unsupported_claim_count",
                            "UNKNOWN",
                        ),
                    )

                with c4:
                    st.metric(
                        "Evidence Gap Guard",
                        safety.get(
                            "evidence_gap_guard",
                            "UNKNOWN",
                        ),
                    )

                _render_scope_audit(live_result)

                with st.expander(
                    "开发调试｜本轮 Retriever Evidence"
                ):
                    st.json(
                        live_result.get("evidence")
                        or []
                    )

                with st.expander(
                    "开发调试｜完整 Live Result JSON"
                ):
                    st.json(
                        live_result
                    )

        else:
            render_scope_hint(live_result, developer_mode)


# ============================================================
# 7b. 高级设置（低视觉权重，默认折叠）
# ============================================================

with st.expander("高级设置"):
    st.checkbox(
        "开发者模式",
        key="developer_mode",
    )

    st.caption(
        "开启后显示 Structured Output JSON、"
        "Safety 内部指标与 Curator 内部字段。"
    )


# ============================================================
# 8. Footer
# ============================================================

st.divider()

st.caption(
    "AUTO-001 MVP｜企业脱敏模拟数据｜"
    "Retriever RC2.2 Frozen｜"
    "Answer/Safety V1.2｜"
    "Structured Output Contract V1.3.1"
)

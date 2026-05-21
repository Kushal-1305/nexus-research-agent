# main.py

import os
import sys
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from agent.loop import run as agent_run
from agent.trust import get_trust_label
from utils.language import language_flag
from session.manager import Session, list_sessions, list_archived_sessions, delete_session, archive_session, unarchive_session

st.set_page_config(
    page_title="Nexus Research",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Timestamp caption */
.msg-timestamp {
    font-size: 0.72rem;
    color: #888;
    margin-top: 2px;
    margin-bottom: 6px;
}
/* Source pill */
.source-pill {
    display: inline-block;
    background: #f0f2f6;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.8rem;
    margin: 2px 0;
}
/* Sidebar session button active */
div[data-testid="stSidebarContent"] .active-session {
    border-left: 3px solid #ff4b4b;
}
/* Welcome banner */
.welcome-box {
    background: linear-gradient(135deg, #667eea22 0%, #764ba222 100%);
    border: 1px solid #667eea44;
    border-radius: 10px;
    padding: 1.5rem 2rem;
    margin: 2rem 0;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
_IST_OFFSET = 5.5 * 3600  # UTC+5:30 in seconds


def _to_ist(iso: str):
    from datetime import timedelta
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt + timedelta(seconds=_IST_OFFSET)
    except Exception:
        return None


def _fmt_ts(iso: str) -> str:
    dt = _to_ist(iso)
    if not dt:
        return ""
    return dt.strftime("%-I:%M %p IST · %b %d, %Y")


def _fmt_ts_short(iso: str) -> str:
    dt = _to_ist(iso)
    if not dt:
        return ""
    return dt.strftime("%b %d, %Y")


# ─────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None

if "chat_display" not in st.session_state:
    # Each entry: {role, content, sources, queries, timestamp}
    st.session_state.chat_display = []

if "session_obj" not in st.session_state:
    st.session_state.session_obj = None

if "open_menu" not in st.session_state:
    st.session_state.open_menu = None

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None


def _load_session(session_id: str) -> None:
    sess = Session(session_id=session_id)
    turns = sess.get_turns()
    display = []
    for t in turns:
        ts = t.get("created_at", "")
        display.append({
            "role": "user", "content": t["question"],
            "sources": [], "queries": [], "timestamp": ts,
        })
        display.append({
            "role": "assistant", "content": t["answer"],
            "sources": t["sources"], "queries": t["search_queries"], "timestamp": ts,
        })
    st.session_state.current_session_id = session_id
    st.session_state.session_obj = sess
    st.session_state.chat_display = display


def _new_session() -> None:
    """Unconditionally create and switch to a new session."""
    sess = Session()
    st.session_state.current_session_id = sess.session_id
    st.session_state.session_obj = sess
    st.session_state.chat_display = []


def _current_turn_count() -> int:
    if st.session_state.session_obj is None:
        return 0
    return len(st.session_state.session_obj.get_turns())


# ─────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Nexus Research")

    if st.button("+ New Chat", use_container_width=True, type="primary"):
        if _current_turn_count() > 0:
            _new_session()
        st.rerun()

    st.divider()

    def _session_row(s: dict, key_prefix: str, archived: bool = False) -> None:
        sid        = s["id"]
        label      = s["title"] or sid[:12]
        updated    = _fmt_ts_short(s.get("updated_at", ""))
        turn_count = s.get("turn_count", 0)
        is_active  = sid == st.session_state.current_session_id
        menu_open  = st.session_state.open_menu == sid

        with st.container(border=True):
            col_name, col_btn = st.columns([7, 1])
            with col_name:
                prefix = "● " if is_active else ""
                if st.button(f"{prefix}{label}", key=f"{key_prefix}_name_{sid}",
                             use_container_width=True, help=s.get("summary") or label):
                    _load_session(sid)
                    st.session_state.open_menu = None
                    st.rerun()
            with col_btn:
                if st.button("⋮", key=f"{key_prefix}_menu_{sid}"):
                    st.session_state.open_menu = None if menu_open else sid
                    st.rerun()

            st.caption(f"{updated} · {turn_count} turn{'s' if turn_count != 1 else ''}")

            if menu_open:
                if archived:
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Unarchive", key=f"{key_prefix}_unarch_{sid}", use_container_width=True):
                            unarchive_session(sid)
                            st.session_state.open_menu = None
                            st.rerun()
                    with c2:
                        if st.button("Delete", key=f"{key_prefix}_del_{sid}", use_container_width=True):
                            delete_session(sid)
                            st.session_state.open_menu = None
                            if sid == st.session_state.current_session_id:
                                _new_session()
                            st.rerun()
                else:
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Archive", key=f"{key_prefix}_arch_{sid}", use_container_width=True):
                            archive_session(sid)
                            st.session_state.open_menu = None
                            if sid == st.session_state.current_session_id:
                                _new_session()
                            st.rerun()
                    with c2:
                        if st.button("Delete", key=f"{key_prefix}_del_{sid}", use_container_width=True):
                            delete_session(sid)
                            st.session_state.open_menu = None
                            if sid == st.session_state.current_session_id:
                                _new_session()
                            st.rerun()

    all_sessions = list_sessions()
    if all_sessions:
        for s in all_sessions:
            _session_row(s, key_prefix="act")
    else:
        st.caption("No active sessions.")

    # ── Archived sessions ──────────────────────────────────────
    archived_sessions = list_archived_sessions()
    if archived_sessions:
        st.divider()
        with st.expander(f"Archived ({len(archived_sessions)})", expanded=False):
            for s in archived_sessions:
                _session_row(s, key_prefix="arc", archived=True)

    st.divider()

# ─────────────────────────────────────────────────────────────
# Auto-create session on first use
# ─────────────────────────────────────────────────────────────
if st.session_state.session_obj is None:
    _new_session()

# ─────────────────────────────────────────────────────────────
# Main header
# ─────────────────────────────────────────────────────────────
sess: Session = st.session_state.session_obj
title = sess.get_title()

col1, col2 = st.columns([5, 1])
with col1:
    st.markdown("# 🔭 Nexus Research")
    display_title = title if title and title not in ("New Chat", "") and not title.startswith("Session ") else None
    if display_title:
        st.caption(f"**{display_title}**")

# ─────────────────────────────────────────────────────────────
# Welcome screen (empty session)
# ─────────────────────────────────────────────────────────────
if not st.session_state.chat_display:
    st.markdown("""
<div class="welcome-box">
<h4>Welcome to Nexus Research</h4>
<p>Ask any question and the agent will:</p>
<ol>
  <li>📋 <b>Plan</b> — generate focused search queries</li>
  <li>🔍 <b>Search</b> — find relevant sources via Tavily</li>
  <li>📥 <b>Fetch</b> — retrieve full page content</li>
  <li>✂️ <b>Select</b> — rank and pick the best context</li>
  <li>✍️ <b>Answer</b> — generate a cited, grounded response</li>
</ol>
<p><i>Try: "What are the latest breakthroughs in quantum computing?" or "Compare Python vs Rust for systems programming"</i></p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# Helpers for new features
# ─────────────────────────────────────────────────────────────
def _render_confidence(conf: dict, key_suffix: str) -> None:
    score = conf.get("overall", 0)
    color = "#22c55e" if score >= 70 else "#f59e0b" if score >= 40 else "#ef4444"
    label = "Strong" if score >= 70 else "Moderate" if score >= 40 else "Weak"
    st.markdown(f"""
<div style="border:1px solid #e5e7eb;border-radius:8px;padding:10px 14px;margin:6px 0;background:#fafafa;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
    <span style="font-size:0.78rem;color:#6b7280;font-weight:600;letter-spacing:.05em">RESEARCH CONFIDENCE</span>
    <span style="font-size:0.95rem;font-weight:700;color:{color}">{score}% &nbsp;·&nbsp; {label}</span>
  </div>
  <div style="height:5px;background:#e5e7eb;border-radius:3px;">
    <div style="height:5px;width:{score}%;background:{color};border-radius:3px;transition:width .4s"></div>
  </div>
  <div style="display:flex;gap:14px;margin-top:8px;font-size:0.73rem;color:#9ca3af;">
    <span>📎 {conf.get('citation_count',0)} citations</span>
    <span>🔗 {conf.get('source_count',0)} sources</span>
    <span>📊 Relevance {conf.get('relevance',0)}%</span>
    <span>📝 Completeness {conf.get('completeness',0)}%</span>
  </div>
</div>""", unsafe_allow_html=True)


def _render_sources(sources: list[dict], key_suffix: str) -> None:
    if not sources:
        return
    with st.expander(f"📎 {len(sources)} source{'s' if len(sources) != 1 else ''}", expanded=False):
        for i, src in enumerate(sources, 1):
            title_text  = src.get("title") or src.get("url", "")
            domain      = src.get("domain", "")
            url         = src.get("url", "")
            trust_score = src.get("trust_score", 0.5)
            trust_lbl, trust_emoji = get_trust_label(trust_score)
            st.markdown(
                f"{trust_emoji} **{i}.** [{title_text} — {domain}]({url})  "
                f"<span style='font-size:0.72rem;color:#9ca3af'>{trust_lbl} trust</span>",
                unsafe_allow_html=True,
            )


def _render_followups(followups: list[str], idx: int) -> None:
    if not followups:
        return
    st.markdown('<div style="font-size:0.8rem;color:#6b7280;margin:8px 0 4px;font-weight:600">SUGGESTED FOLLOW-UPS</div>', unsafe_allow_html=True)
    for i, q in enumerate(followups):
        if st.button(f"↗ {q}", key=f"fu_{idx}_{i}", use_container_width=True):
            st.session_state.pending_question = q
            st.rerun()


# ─────────────────────────────────────────────────────────────
# Render chat history
# ─────────────────────────────────────────────────────────────
for msg_idx, msg in enumerate(st.session_state.chat_display):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Language badge (assistant only)
        lang = msg.get("language", "English")
        ts   = msg.get("timestamp", "")
        meta_parts = []
        if lang and lang != "English":
            meta_parts.append(f"{language_flag(lang)} {lang}")
        if ts:
            meta_parts.append(_fmt_ts(ts))
        if meta_parts:
            st.markdown(f'<div class="msg-timestamp">{" &nbsp;·&nbsp; ".join(meta_parts)}</div>', unsafe_allow_html=True)

        if msg["role"] == "assistant":
            # Community-only source warning
            if msg.get("social_warning"):
                st.warning(f"⚠️ {msg['social_warning']}", icon=None)

            # Confidence meter
            if msg.get("confidence"):
                _render_confidence(msg["confidence"], str(msg_idx))

            # Sources with trust badges
            _render_sources(msg.get("sources", []), str(msg_idx))

            # Search queries
            if msg.get("queries"):
                with st.expander("🔍 Search queries used", expanded=False):
                    for q in msg["queries"]:
                        st.code(q, language=None)

            # Follow-up suggestions
            _render_followups(msg.get("followups", []), msg_idx)

# ─────────────────────────────────────────────────────────────
# Chat input (also picks up follow-up button clicks)
# ─────────────────────────────────────────────────────────────
_typed = st.chat_input("Ask a research question…")
user_question = _typed or st.session_state.pop("pending_question", None)

if user_question:

    now_ts = datetime.now(timezone.utc).isoformat()

    with st.chat_message("user"):
        st.markdown(user_question)
        st.markdown(f'<div class="msg-timestamp">{_fmt_ts(now_ts)}</div>', unsafe_allow_html=True)

    st.session_state.chat_display.append({
        "role": "user", "content": user_question,
        "sources": [], "queries": [], "timestamp": now_ts,
    })

    # Auto-title session from first question
    current_title = sess.get_title()
    if not current_title or current_title in ("New Chat", "") or current_title.startswith("Session "):
        short_title = user_question[:60] + ("…" if len(user_question) > 60 else "")
        sess.set_title(short_title)

    conversation_history = sess.get_history(limit=10)

    with st.chat_message("assistant"):
        final_answer: Optional[str] = None
        final_sources: list[dict] = []
        final_queries: list[str] = []
        answer_placeholder = st.empty()
        accumulated_answer = ""
        done_ts = now_ts

        final_confidence:     dict        = {}
        final_followups:      list        = []
        final_language:       str         = "English"
        final_social_warning: str | None  = None

        with st.status("Researching…", expanded=True) as status_container:
            status_log: list[str] = []
            status_lines = st.empty()

            for event in agent_run(
                question=user_question,
                session=sess,
                conversation_history=conversation_history,
            ):
                stage = event["stage"]

                if stage in ("planning", "searching", "fetching", "selecting", "answering", "followups"):
                    icons = {
                        "planning":  "📋",
                        "searching": "🔍",
                        "fetching":  "📥",
                        "selecting": "✂️",
                        "answering": "✍️",
                        "followups": "💡",
                    }
                    icon = icons.get(stage, "•")
                    status_log.append(f"{icon} **{stage.title()}**: {event.get('message', '')}")
                    status_lines.markdown("\n\n".join(status_log[-8:]))

                elif stage == "streaming":
                    accumulated_answer += event["token"]
                    answer_placeholder.markdown(accumulated_answer + "▌")

                elif stage == "done":
                    final_answer         = event.get("answer", accumulated_answer)
                    final_sources        = event.get("sources", [])
                    final_queries        = event.get("search_queries", [])
                    final_confidence     = event.get("confidence", {})
                    final_followups      = event.get("followups", [])
                    final_language       = event.get("language", "English")
                    final_social_warning = event.get("social_warning")
                    done_ts           = datetime.now(timezone.utc).isoformat()
                    status_container.update(
                        label=f"Research complete — {len(final_sources)} source{'s' if len(final_sources) != 1 else ''}",
                        state="complete",
                        expanded=False,
                    )

                elif stage == "error":
                    st.error(event["message"])
                    status_container.update(label="Error during research", state="error", expanded=True)

        # Finalise answer
        if final_answer:
            answer_placeholder.markdown(final_answer)
        elif accumulated_answer:
            answer_placeholder.markdown(accumulated_answer)
            final_answer = accumulated_answer

        # Language + timestamp
        meta_parts = []
        if final_language and final_language != "English":
            meta_parts.append(f"{language_flag(final_language)} {final_language}")
        meta_parts.append(_fmt_ts(done_ts))
        st.markdown(f'<div class="msg-timestamp">{" &nbsp;·&nbsp; ".join(meta_parts)}</div>', unsafe_allow_html=True)

        # Community-only source warning
        if final_social_warning:
            st.warning(f"⚠️ {final_social_warning}", icon=None)

        # Confidence meter
        if final_confidence:
            _render_confidence(final_confidence, "new")

        # Sources with trust badges
        _render_sources(final_sources, "new")

        # Search queries
        if final_queries:
            with st.expander("🔍 Search queries used", expanded=False):
                for q in final_queries:
                    st.code(q, language=None)

        # Follow-up suggestions
        new_msg_idx = len(st.session_state.chat_display) + 1
        _render_followups(final_followups, new_msg_idx)

    st.session_state.chat_display.append({
        "role":           "assistant",
        "content":        final_answer or "",
        "sources":        final_sources,
        "queries":        final_queries,
        "timestamp":      done_ts,
        "confidence":     final_confidence,
        "followups":      final_followups,
        "language":       final_language,
        "social_warning": final_social_warning,
    })

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
from session.manager import (
    Session, list_sessions, list_archived_sessions,
    delete_session, archive_session, unarchive_session,
)

st.set_page_config(
    page_title="Nexus Research",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# Global styles
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"], .stMarkdown, .stText, p, div, span, button {
    font-family: 'Inter', sans-serif !important;
}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }

/* ── App background ── */
.stApp { background: #0d1117; }
.main .block-container {
    padding: 1.5rem 2rem 6rem 2rem;
    max-width: 860px;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #010409 !important;
    border-right: 1px solid #21262d !important;
}
section[data-testid="stSidebar"] > div { padding-top: 1rem; }

/* ── Sidebar text colours ── */
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stCaption { color: #8b949e !important; }

/* ── Sidebar buttons ── */
section[data-testid="stSidebar"] button {
    background: transparent !important;
    border: none !important;
    color: #c9d1d9 !important;
    text-align: left !important;
    border-radius: 6px !important;
    font-size: 0.82rem !important;
    padding: 5px 8px !important;
    transition: background 0.15s;
}
section[data-testid="stSidebar"] button:hover {
    background: #161b22 !important;
    color: #e6edf3 !important;
}

/* ── New Chat primary button ── */
section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] button,
section[data-testid="stSidebar"] [kind="primary"] {
    background: #1f6feb !important;
    color: #ffffff !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
    border: none !important;
}
section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] button:hover {
    background: #388bfd !important;
}

/* ── Sidebar containers (session rows) ── */
section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid #21262d !important;
    border-radius: 8px !important;
    background: #0d1117 !important;
    margin-bottom: 4px !important;
}
section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: #30363d !important;
    background: #161b22 !important;
}

/* ── Sidebar divider ── */
section[data-testid="stSidebar"] hr { border-color: #21262d !important; }

/* ── Sidebar expander ── */
section[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: transparent !important;
    border: 1px solid #21262d !important;
    border-radius: 6px !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    color: #8b949e !important;
    font-size: 0.8rem !important;
}

/* ── Main chat messages ── */
[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
    padding: 4px 0 !important;
}
[data-testid="stChatMessageContent"] { color: #e6edf3 !important; }

/* ── Assistant message avatar ── */
[data-testid="stChatMessageAvatarAssistant"] {
    background: #1f6feb !important;
    border-radius: 50% !important;
}

/* ── Chat input ── */
[data-testid="stChatInput"] textarea {
    background: #1c2128 !important;
    border: 1px solid #373e47 !important;
    color: #cdd9e5 !important;
    caret-color: #cdd9e5 !important;
    border-radius: 12px !important;
    font-size: 0.9rem !important;
    line-height: 1.6 !important;
    padding: 12px 16px !important;
}
[data-testid="stChatInput"] textarea::placeholder {
    color: #545d68 !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: #4d80c8 !important;
    box-shadow: 0 0 0 3px rgba(77, 128, 200, 0.12) !important;
    outline: none !important;
}
[data-testid="stChatInputContainer"] {
    background: #161b22 !important;
    border-top: 1px solid #2d333b !important;
    padding: 0.85rem 0 !important;
}

/* ── Status widget (hidden, replaced by custom HTML) ── */
[data-testid="stStatus"] { display: none !important; }

/* ── Custom status bar ── */
@keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}

/* ── Expanders in main ── */
[data-testid="stExpander"] {
    background: #161b22 !important;
    border: 1px solid #21262d !important;
    border-radius: 8px !important;
}
[data-testid="stExpander"] summary { color: #8b949e !important; font-size: 0.82rem !important; }
[data-testid="stExpander"] summary:hover { color: #c9d1d9 !important; }

/* ── Code blocks ── */
code, pre {
    background: #161b22 !important;
    color: #79c0ff !important;
    border: 1px solid #30363d !important;
    border-radius: 6px !important;
    font-size: 0.8rem !important;
}

/* ── Warnings / errors ── */
[data-testid="stAlert"] {
    background: #2d1b00 !important;
    border: 1px solid #d29922 !important;
    border-radius: 8px !important;
    color: #e3b341 !important;
}

/* ── Follow-up buttons (secondary buttons in chat) ── */
[data-testid="stChatMessage"] [data-testid="stBaseButton-secondary"] button,
[data-testid="stChatMessage"] button[kind="secondary"] {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    color: #58a6ff !important;
    border-radius: 8px !important;
    font-size: 0.82rem !important;
    text-align: left !important;
    padding: 8px 14px !important;
    transition: all 0.15s;
}
[data-testid="stChatMessage"] [data-testid="stBaseButton-secondary"] button:hover {
    background: #1f2d3d !important;
    border-color: #58a6ff !important;
}

/* ── Markdown text ── */
.stMarkdown p { color: #e6edf3; line-height: 1.7; font-size: 0.92rem; }
.stMarkdown h2 { color: #e6edf3; font-weight: 600; margin-top: 1.2rem; border-bottom: 1px solid #21262d; padding-bottom: 6px; }
.stMarkdown h3 { color: #c9d1d9; font-weight: 500; }
.stMarkdown a { color: #58a6ff !important; text-decoration: none; }
.stMarkdown a:hover { text-decoration: underline; }
.stMarkdown ul, .stMarkdown ol { color: #c9d1d9; }
.stMarkdown strong { color: #e6edf3; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #58a6ff; }

/* ── Timestamp ── */
.msg-meta {
    font-size: 0.7rem;
    color: #484f58;
    margin: 2px 0 8px;
    font-family: 'Inter', sans-serif;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
_IST_OFFSET = 5.5 * 3600


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
    return dt.strftime("%-I:%M %p · %b %d") if dt else ""


def _fmt_ts_short(iso: str) -> str:
    dt = _to_ist(iso)
    return dt.strftime("%b %d") if dt else ""


# ─────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────
for _k, _v in [
    ("current_session_id", None),
    ("chat_display", []),
    ("session_obj", None),
    ("open_menu", None),
    ("pending_question", None),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v


def _load_session(session_id: str) -> None:
    sess = Session(session_id=session_id)
    display = []
    for t in sess.get_turns():
        ts = t.get("created_at", "")
        display.append({"role": "user", "content": t["question"],
                        "sources": [], "queries": [], "timestamp": ts})
        display.append({"role": "assistant", "content": t["answer"],
                        "sources": t["sources"], "queries": t["search_queries"],
                        "timestamp": ts})
    st.session_state.current_session_id = session_id
    st.session_state.session_obj = sess
    st.session_state.chat_display = display


def _new_session() -> None:
    sess = Session()
    st.session_state.current_session_id = sess.session_id
    st.session_state.session_obj = sess
    st.session_state.chat_display = []


def _current_turn_count() -> int:
    if st.session_state.session_obj is None:
        return 0
    return len(st.session_state.session_obj.get_turns())


# ─────────────────────────────────────────────────────────────
# Render helpers
# ─────────────────────────────────────────────────────────────
def _render_confidence(conf: dict, key_suffix: str) -> None:
    score = conf.get("overall", 0)
    if score >= 70:
        bar_color, label, label_color = "#3fb950", "Strong", "#3fb950"
    elif score >= 40:
        bar_color, label, label_color = "#d29922", "Moderate", "#d29922"
    else:
        bar_color, label, label_color = "#f85149", "Weak", "#f85149"

    cit  = conf.get("citation_count", 0)
    src  = conf.get("source_count", 0)
    rel  = conf.get("relevance", 0)
    comp = conf.get("completeness", 0)

    st.markdown(f"""
<div style="background:#161b22;border:1px solid #21262d;border-radius:8px;padding:10px 14px;margin:8px 0;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:7px;">
    <span style="font-size:0.68rem;color:#484f58;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;">Research Confidence</span>
    <span style="font-size:0.82rem;font-weight:700;color:{label_color};">{score}% &nbsp;·&nbsp; {label}</span>
  </div>
  <div style="height:3px;background:#21262d;border-radius:2px;margin-bottom:10px;">
    <div style="height:3px;width:{score}%;background:{bar_color};border-radius:2px;"></div>
  </div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;">
    <span style="font-size:0.7rem;color:#8b949e;background:#0d1117;border:1px solid #21262d;padding:2px 9px;border-radius:12px;">📎 {cit} citations</span>
    <span style="font-size:0.7rem;color:#8b949e;background:#0d1117;border:1px solid #21262d;padding:2px 9px;border-radius:12px;">🔗 {src} sources</span>
    <span style="font-size:0.7rem;color:#8b949e;background:#0d1117;border:1px solid #21262d;padding:2px 9px;border-radius:12px;">📊 {rel}% relevance</span>
    <span style="font-size:0.7rem;color:#8b949e;background:#0d1117;border:1px solid #21262d;padding:2px 9px;border-radius:12px;">📝 {comp}% depth</span>
  </div>
</div>""", unsafe_allow_html=True)


def _render_sources(sources: list[dict], key_suffix: str) -> None:
    if not sources:
        return
    rows = ""
    for i, src in enumerate(sources, 1):
        title_text  = (src.get("title") or src.get("url", ""))[:70]
        domain      = src.get("domain", "")
        url         = src.get("url", "")
        trust_score = src.get("trust_score", 0.5)
        trust_lbl, trust_emoji = get_trust_label(trust_score)
        rows += f"""
<div style="display:flex;align-items:center;gap:10px;padding:7px 2px;border-bottom:1px solid #21262d;">
  <span style="color:#484f58;font-size:0.72rem;min-width:16px;">{i}</span>
  <span style="font-size:0.75rem;">{trust_emoji}</span>
  <a href="{url}" target="_blank" style="color:#58a6ff;text-decoration:none;font-size:0.8rem;flex:1;
     overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{title_text}</a>
  <span style="color:#484f58;font-size:0.68rem;white-space:nowrap;">{domain} · {trust_lbl}</span>
</div>"""
    st.markdown(f"""
<details style="background:#161b22;border:1px solid #21262d;border-radius:8px;
                padding:10px 14px;margin:8px 0;cursor:pointer;">
  <summary style="color:#8b949e;font-size:0.8rem;list-style:none;outline:none;
                  cursor:pointer;user-select:none;">
    {len(sources)} source{'s' if len(sources) != 1 else ''}
  </summary>
  <div style="margin-top:8px;">{rows}</div>
</details>
""", unsafe_allow_html=True)


def _render_queries(queries: list[str]) -> None:
    if not queries:
        return
    items = "".join(
        f'<div style="font-size:0.78rem;color:#79c0ff;background:#0d1117;border:1px solid #21262d;'
        f'border-radius:5px;padding:5px 10px;margin:3px 0;">{q}</div>'
        for q in queries
    )
    st.markdown(f"""
<details style="background:#161b22;border:1px solid #21262d;border-radius:8px;
                padding:10px 14px;margin:8px 0;">
  <summary style="color:#8b949e;font-size:0.8rem;list-style:none;outline:none;
                  cursor:pointer;user-select:none;">Search queries</summary>
  <div style="margin-top:8px;">{items}</div>
</details>
""", unsafe_allow_html=True)


def _render_followups(followups: list[str], idx: int) -> None:
    if not followups:
        return
    st.markdown("""
<div style="margin:14px 0 6px;font-size:0.68rem;color:#484f58;font-weight:600;
            letter-spacing:0.1em;text-transform:uppercase;">Continue exploring</div>
""", unsafe_allow_html=True)
    for i, q in enumerate(followups):
        if st.button(q, key=f"fu_{idx}_{i}", use_container_width=True):
            st.session_state.pending_question = q
            st.rerun()


# ─────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
<div style="padding:0 4px 12px;display:flex;align-items:center;gap:8px;">
  <span style="font-size:1.1rem;">🔭</span>
  <span style="font-size:0.95rem;font-weight:600;color:#e6edf3;">Nexus Research</span>
</div>
""", unsafe_allow_html=True)

    if st.button("＋  New Chat", use_container_width=True, type="primary"):
        if _current_turn_count() > 0:
            _new_session()
        st.rerun()

    st.divider()

    def _session_row(s: dict, key_prefix: str, archived: bool = False) -> None:
        sid        = s["id"]
        label      = (s["title"] or sid[:12])[:38]
        updated    = _fmt_ts_short(s.get("updated_at", ""))
        turn_count = s.get("turn_count", 0)
        is_active  = sid == st.session_state.current_session_id
        menu_open  = st.session_state.open_menu == sid

        with st.container(border=True):
            col_name, col_btn = st.columns([8, 1])
            with col_name:
                dot = "● " if is_active else ""
                if st.button(
                    f"{dot}{label}",
                    key=f"{key_prefix}_name_{sid}",
                    use_container_width=True,
                    help=s.get("summary") or label,
                ):
                    _load_session(sid)
                    st.session_state.open_menu = None
                    st.rerun()
            with col_btn:
                if st.button("⋮", key=f"{key_prefix}_menu_{sid}"):
                    st.session_state.open_menu = None if menu_open else sid
                    st.rerun()

            st.caption(f"{updated} · {turn_count}t")

            if menu_open:
                c1, c2 = st.columns(2)
                if archived:
                    with c1:
                        if st.button("Unarchive", key=f"{key_prefix}_unarch_{sid}", use_container_width=True):
                            unarchive_session(sid)
                            st.session_state.open_menu = None
                            st.rerun()
                else:
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
        st.markdown('<p style="font-size:0.78rem;color:#484f58;padding:4px 2px;">No sessions yet.</p>',
                    unsafe_allow_html=True)

    archived_sessions = list_archived_sessions()
    if archived_sessions:
        st.divider()
        with st.expander(f"Archived ({len(archived_sessions)})", expanded=False):
            for s in archived_sessions:
                _session_row(s, key_prefix="arc", archived=True)


# ─────────────────────────────────────────────────────────────
# Bootstrap session — resume most recent on page refresh
# ─────────────────────────────────────────────────────────────
if st.session_state.session_obj is None:
    existing = list_sessions()
    if existing:
        _load_session(existing[0]["id"])   # most recently updated session
    else:
        _new_session()

sess: Session = st.session_state.session_obj
title = sess.get_title()
display_title = title if title and title not in ("New Chat", "") and not title.startswith("Session ") else None

# ─────────────────────────────────────────────────────────────
# Page header
# ─────────────────────────────────────────────────────────────
if display_title:
    st.markdown(f"""
<div style="margin-bottom:1.5rem;padding-bottom:12px;border-bottom:1px solid #21262d;">
  <h2 style="margin:0;font-size:1.15rem;font-weight:600;color:#e6edf3;">{display_title}</h2>
</div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# Welcome screen
# ─────────────────────────────────────────────────────────────
if not st.session_state.chat_display:
    st.markdown("""
<div style="max-width:640px;margin:4rem auto;text-align:center;">
  <div style="font-size:2.8rem;margin-bottom:1rem;">🔭</div>
  <h2 style="color:#e6edf3;font-size:1.4rem;font-weight:600;margin-bottom:0.4rem;">Nexus Research</h2>
  <p style="color:#8b949e;font-size:0.88rem;margin-bottom:2.5rem;line-height:1.6;">
    Ask anything. Get cited, grounded answers sourced from across the web.
  </p>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;text-align:left;margin-bottom:2rem;">
    <div style="background:#161b22;border:1px solid #21262d;border-radius:10px;padding:16px;">
      <div style="font-size:1.1rem;margin-bottom:6px;">📋</div>
      <div style="font-size:0.82rem;color:#e6edf3;font-weight:500;margin-bottom:3px;">Smart Planning</div>
      <div style="font-size:0.74rem;color:#8b949e;line-height:1.5;">Decomposes your question into 5 targeted search queries</div>
    </div>
    <div style="background:#161b22;border:1px solid #21262d;border-radius:10px;padding:16px;">
      <div style="font-size:1.1rem;margin-bottom:6px;">🔍</div>
      <div style="font-size:0.82rem;color:#e6edf3;font-weight:500;margin-bottom:3px;">Live Web Search</div>
      <div style="font-size:0.74rem;color:#8b949e;line-height:1.5;">Searches multiple sources in parallel, filters junk</div>
    </div>
    <div style="background:#161b22;border:1px solid #21262d;border-radius:10px;padding:16px;">
      <div style="font-size:1.1rem;margin-bottom:6px;">✅</div>
      <div style="font-size:0.82rem;color:#e6edf3;font-weight:500;margin-bottom:3px;">Cited Answers</div>
      <div style="font-size:0.74rem;color:#8b949e;line-height:1.5;">Every claim linked to a verified source with trust scoring</div>
    </div>
    <div style="background:#161b22;border:1px solid #21262d;border-radius:10px;padding:16px;">
      <div style="font-size:1.1rem;margin-bottom:6px;">💡</div>
      <div style="font-size:0.82rem;color:#e6edf3;font-weight:500;margin-bottom:3px;">Follow-up Paths</div>
      <div style="font-size:0.74rem;color:#8b949e;line-height:1.5;">Suggested questions to explore the topic deeper</div>
    </div>
  </div>
  <p style="color:#484f58;font-size:0.75rem;">
    Try: <em style="color:#8b949e;">"Compare nuclear fission and fusion as energy sources"</em>
  </p>
</div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# Chat history
# ─────────────────────────────────────────────────────────────
for msg_idx, msg in enumerate(st.session_state.chat_display):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        lang = msg.get("language", "English")
        ts   = msg.get("timestamp", "")
        meta_parts = []
        if lang and lang != "English":
            meta_parts.append(f"{language_flag(lang)} {lang}")
        if ts:
            meta_parts.append(_fmt_ts(ts))
        if meta_parts:
            st.markdown(
                f'<div class="msg-meta">{" &nbsp;·&nbsp; ".join(meta_parts)}</div>',
                unsafe_allow_html=True,
            )

        if msg["role"] == "assistant":
            if msg.get("social_warning"):
                st.warning(msg["social_warning"])
            if msg.get("confidence"):
                _render_confidence(msg["confidence"], str(msg_idx))
            _render_sources(msg.get("sources", []), str(msg_idx))
            _render_queries(msg.get("queries", []))
            _render_followups(msg.get("followups", []), msg_idx)

# ─────────────────────────────────────────────────────────────
# Chat input
# ─────────────────────────────────────────────────────────────
_typed = st.chat_input("Ask a research question…")
user_question = _typed or st.session_state.pop("pending_question", None)

if user_question:
    now_ts = datetime.now(timezone.utc).isoformat()

    with st.chat_message("user"):
        st.markdown(user_question)
        st.markdown(f'<div class="msg-meta">{_fmt_ts(now_ts)}</div>', unsafe_allow_html=True)

    st.session_state.chat_display.append({
        "role": "user", "content": user_question,
        "sources": [], "queries": [], "timestamp": now_ts,
    })

    current_title = sess.get_title()
    if not current_title or current_title in ("New Chat", "") or current_title.startswith("Session "):
        sess.set_title(user_question[:60] + ("…" if len(user_question) > 60 else ""))

    conversation_history = sess.get_history(limit=10)

    with st.chat_message("assistant"):
        final_answer:         Optional[str] = None
        final_sources:        list[dict]    = []
        final_queries:        list[str]     = []
        final_confidence:     dict          = {}
        final_followups:      list          = []
        final_language:       str           = "English"
        final_social_warning: str | None    = None

        answer_placeholder   = st.empty()
        accumulated_answer   = ""
        done_ts              = now_ts

        status_header = st.empty()
        status_log_box = st.empty()

        status_header.markdown("""
<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;
            padding:10px 14px;margin:4px 0;display:flex;align-items:center;gap:10px;">
  <span style="display:inline-block;width:8px;height:8px;background:#1f6feb;border-radius:50%;
               animation:pulse-dot 1.2s ease-in-out infinite;"></span>
  <span style="color:#c9d1d9;font-size:0.85rem;font-weight:500;">Researching…</span>
</div>""", unsafe_allow_html=True)

        status_log:  list[str] = []

        _STAGE_ICONS = {
            "planning": "📋", "searching": "🔍", "fetching": "📥",
            "selecting": "✂️", "answering": "✍️", "followups": "💡",
        }

        for event in agent_run(
            question=user_question,
            session=sess,
            conversation_history=conversation_history,
        ):
            stage = event["stage"]

            if stage in _STAGE_ICONS:
                icon = _STAGE_ICONS[stage]
                status_log.append(f"{icon} **{stage.title()}** — {event.get('message', '')}")
                log_html = "".join(
                    f'<div style="font-size:0.78rem;color:#8b949e;padding:2px 0;">'
                    f'{line.replace("**", "")}</div>'
                    for line in status_log[-8:]
                )
                status_log_box.markdown(
                    f'<div style="background:#0d1117;border:1px solid #21262d;border-radius:6px;'
                    f'padding:8px 12px;margin:2px 0;">{log_html}</div>',
                    unsafe_allow_html=True,
                )

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
                done_ts              = datetime.now(timezone.utc).isoformat()
                n = len(final_sources)
                status_header.markdown(f"""
<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;
            padding:10px 14px;margin:4px 0;display:flex;align-items:center;gap:10px;">
  <span style="color:#3fb950;font-size:0.9rem;">&#10003;</span>
  <span style="color:#8b949e;font-size:0.82rem;">Done &mdash; {n} source{'s' if n != 1 else ''}</span>
</div>""", unsafe_allow_html=True)
                status_log_box.empty()

            elif stage == "error":
                st.error(event["message"])
                status_header.markdown("""
<div style="background:#2d1b00;border:1px solid #f85149;border-radius:8px;
            padding:10px 14px;margin:4px 0;">
  <span style="color:#f85149;font-size:0.85rem;">Research failed</span>
</div>""", unsafe_allow_html=True)
                status_log_box.empty()

        answer_placeholder.markdown(final_answer or accumulated_answer)
        if not final_answer:
            final_answer = accumulated_answer

        meta_parts = []
        if final_language and final_language != "English":
            meta_parts.append(f"{language_flag(final_language)} {final_language}")
        meta_parts.append(_fmt_ts(done_ts))
        st.markdown(
            f'<div class="msg-meta">{" &nbsp;·&nbsp; ".join(meta_parts)}</div>',
            unsafe_allow_html=True,
        )

        if final_social_warning:
            st.warning(final_social_warning)
        if final_confidence:
            _render_confidence(final_confidence, "new")
        _render_sources(final_sources, "new")
        _render_queries(final_queries)
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

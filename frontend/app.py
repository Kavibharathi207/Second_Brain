"""
Second Brain — AI-Powered Personal Memory Assistant
"""

import streamlit as st
import sys
import os
from datetime import datetime, timedelta

# Ensure project root is always on sys.path regardless of how Streamlit is launched
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
from backend.config import config
from backend.security import security_manager
from backend.memory_store import memory_store
from backend.rag_engine import rag_engine
from backend.ollama_service import ollama_service
from backend.memory_utils import memory_decay, memory_parser, memory_stats, memory_exporter, tone_detector
from backend.user_manager import authenticate_user, register_user, get_user_by_id
from backend.reminder_utils import infer_reminder_from_content
from core.reminder_engine import (
    get_pending as db_get_pending,
    get_recent_completed_missed,
    create_reminder as db_create_reminder,
    mark_complete as db_mark_complete,
    snooze as db_snooze,
    dismiss as db_dismiss,
)
from core.diary import (
    create_entry as diary_create,
    list_entries as diary_list,
    get_entry as diary_get,
    update_entry as diary_update,
    delete_entry as diary_delete,
    search_entries as diary_search,
)
from db.database import init_db
init_db()

print("[Second Brain] ✅ Backend modules loaded successfully")


def inject_custom_css():
    css_path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


st.set_page_config(
    page_title="Second Brain",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

inject_custom_css()

# old inline <style> block removed — styles now live in assets/style.css


# ── cached backend calls ──────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def get_all_memories_cached():
    print("[Cache] Fetching all memories from store...")
    result = memory_store.get_all_memories()
    print(f"[Cache] Loaded {len(result)} memories")
    return result

@st.cache_data(ttl=30)
def get_stats_cached():
    print("[Cache] Fetching memory statistics...")
    return memory_stats.get_statistics()

@st.cache_data(ttl=60)
def check_ollama_cached():
    print("[Ollama] Checking connection...")
    status = ollama_service.check_connection()
    print(f"[Ollama] Status: {'connected ✅' if status else 'offline ❌'}")
    return status

def bust_memory_cache():
    print("[Cache] Busting memory + stats cache")
    get_all_memories_cached.clear()
    get_stats_cached.clear()


# ── helpers ───────────────────────────────────────────────────────────────────

REMINDER_KEYWORDS = [
    "remind", "reminder", "don't forget", "remember to", "schedule",
    "appointment", "meeting", "deadline", "due", "tomorrow", "next week",
    "take", "bring", "buy", "call", "email", "submit", "pay"
]

def detect_reminder(content: str) -> bool:
    lower = content.lower()
    return any(kw in lower for kw in REMINDER_KEYWORDS)

def extract_reminder_text(content: str) -> str:
    lower = content.lower()
    for kw in ["remind me to", "remind me", "reminder to", "reminder:"]:
        if kw in lower:
            idx = lower.index(kw) + len(kw)
            return content[idx:].strip().capitalize()
    return content.strip().capitalize()

def this_week_count(memories):
    week_ago = datetime.now() - timedelta(days=7)
    count = 0
    for m in memories:
        ca = m.get("metadata", {}).get("created_at", "")
        try:
            if datetime.fromisoformat(ca) >= week_ago:
                count += 1
        except Exception:
            pass
    return count

def pending_reminders():
    """Count pending reminders from SQLite (used for sidebar badge)."""
    try:
        return db_get_pending()
    except Exception:
        return [r for r in st.session_state.get("reminders", []) if not r.get("done")]

def init_state():
    print("[State] Initialising session state")
    defaults = {
        "page": "Dashboard",
        "section_auth": None,
        "section_unlocked": False,
        "conversation": [],
        "reminders": [],
        "auth_mode": "signin",
        "current_user": None,
        "auth_message": "",
        "auth_error": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def go(page: str):
    print(f"[Nav] Navigating to → {page}")
    st.session_state.page = page


def auth_panel():
    if st.session_state.current_user:
        return

    st.markdown('<div class="settings-card">', unsafe_allow_html=True)
    st.markdown('<div class="settings-card-title">🔐 Sign in or create an account</div>', unsafe_allow_html=True)

    mode = st.radio("Account action", ["Sign in", "Sign up"], horizontal=True, key="auth_mode")
    username = st.text_input("Username or email", key="auth_username")
    email = st.text_input("Email", key="auth_email") if mode == "Sign up" else ""
    password = st.text_input("Password", type="password", key="auth_password")
    full_name = st.text_input("Full name", key="auth_full_name") if mode == "Sign up" else ""

    if st.button("Continue", type="primary", use_container_width=True, key="auth_submit"):
        if mode == "Sign in":
            user = authenticate_user(username, password)
            if user:
                st.session_state.current_user = user
                st.session_state.auth_message = f"Welcome back, {user.get('full_name') or user.get('username')}"
                st.session_state.auth_error = ""
                st.rerun()
            else:
                st.session_state.auth_error = "Invalid username/email or password."
        else:
            try:
                user = register_user(username=username, email=email, password=password, full_name=full_name)
                st.session_state.current_user = user
                st.session_state.auth_message = f"Account created for {user['username']}"
                st.session_state.auth_error = ""
                st.rerun()
            except ValueError as exc:
                st.session_state.auth_error = str(exc)

    if st.session_state.auth_error:
        st.error(st.session_state.auth_error)
    if st.session_state.auth_message:
        st.success(st.session_state.auth_message)
    st.markdown('</div>', unsafe_allow_html=True)


# ── security gate — 4-digit PIN overlay ──────────────────────────────────────

def security_gate(section: str) -> bool:
    print(f"[Security] Gate check for section: {section}")
    if st.session_state.section_unlocked and st.session_state.section_auth == section:
        print(f"[Security] ✅ Already unlocked: {section}")
        return True

    # ── blurred ghost cards behind the overlay ────────────────────────────────
    st.markdown("""
    <div class="pin-backdrop">
        <div class="pin-ghost-row">
            <div class="pin-ghost-block" style="height:80px;flex:2"></div>
            <div class="pin-ghost-block" style="height:50px;flex:1"></div>
        </div>
        <div class="pin-ghost-row">
            <div class="pin-ghost-block" style="height:60px;flex:1"></div>
            <div class="pin-ghost-block" style="height:90px;flex:2"></div>
        </div>
        <div class="pin-ghost-row">
            <div class="pin-ghost-block" style="height:50px;flex:1"></div>
            <div class="pin-ghost-block" style="height:70px;flex:1"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── session-state keys ────────────────────────────────────────────────────
    error_key = f"pin_error_{section}"
    shake_key = f"pin_shake_{section}"
    pin_key   = f"pin_input_{section}"

    for k, v in [(error_key, False), (shake_key, False)]:
        if k not in st.session_state:
            st.session_state[k] = v

    shake_class = "pin-modal pin-shake" if st.session_state[shake_key] else "pin-modal"
    st.session_state[shake_key] = False   # reset after one render

    error_html = (
        '<div class="pin-error">&#10060; Incorrect code — try again</div>'
        if st.session_state[error_key] else ""
    )

    # ── modal card ────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="{shake_class}">
        <div class="pin-icon-wrap">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none"
                 stroke="#0F766E" stroke-width="2.2"
                 stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
        </div>
        <div class="pin-title">Verify Identity</div>
        <div class="pin-subtitle">
            Enter your 4-digit secret code to access<br>
            <span style="font-weight:700;color:#0F172A">{section}</span>
        </div>
        <div class="pin-boxes-row" id="pin-boxes-{section}">
            <div class="pin-box" id="pb0-{section}"></div>
            <div class="pin-box" id="pb1-{section}"></div>
            <div class="pin-box" id="pb2-{section}"></div>
            <div class="pin-box" id="pb3-{section}"></div>
        </div>
        {error_html}
        <div class="pin-helper">Demo code: 1234</div>
    </div>
    """, unsafe_allow_html=True)

    # ── real password input (invisible, drives logic) ─────────────────────────
    pin_val = st.text_input(
        "PIN",
        max_chars=4,
        type="password",
        placeholder="● ● ● ●",
        key=pin_key,
        label_visibility="collapsed",
    )

    # ── JS: mirror typed chars → visual boxes + auto-focus ───────────────────
    st.markdown(f"""
    <script>
    (function() {{
        var attempts = 0;
        function init() {{
            var inputs = window.parent.document.querySelectorAll('input[type="password"]');
            var input  = null;
            inputs.forEach(function(el) {{
                if (el.placeholder && el.placeholder.indexOf('●') !== -1) input = el;
            }});
            var boxes = window.parent.document.querySelectorAll('#pin-boxes-{section} .pin-box');
            if (!input || boxes.length < 4) {{
                if (++attempts < 25) setTimeout(init, 150);
                return;
            }}
            input.style.position      = 'fixed';
            input.style.opacity       = '0';
            input.style.width         = '1px';
            input.style.height        = '1px';
            input.style.top           = '0';
            input.style.left          = '0';
            input.style.zIndex        = '9999';
            input.style.pointerEvents = 'none';
            function sync() {{
                var v = input.value;
                boxes.forEach(function(b, i) {{
                    b.textContent = i < v.length ? '●' : '';
                    b.className = 'pin-box' +
                        (i < v.length  ? ' pin-box-filled' : '') +
                        (i === v.length ? ' pin-box-active' : '');
                }});
            }}
            input.addEventListener('input', sync);
            sync();
            setTimeout(function() {{ input.focus(); }}, 200);
        }}
        init();
    }})();
    </script>
    """, unsafe_allow_html=True)

    # ── auto-verify when 4 digits entered ────────────────────────────────────
    if len(pin_val) == 4:
        if security_manager.verify_secret_code(pin_val):
            print(f"[Security] ✅ Unlocked section: {section}")
            st.session_state.section_auth     = section
            st.session_state.section_unlocked = True
            st.session_state.last_unlocked    = section
            st.session_state[error_key]       = False
            st.rerun()
        else:
            print(f"[Security] ❌ Wrong PIN for: {section}")
            st.session_state[error_key] = True
            st.session_state[shake_key] = True
            st.rerun()

    # ── back button ───────────────────────────────────────────────────────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("← Back to Dashboard", key=f"cancel_{section}", use_container_width=True):
        st.session_state.page = "Dashboard"
        st.rerun()

    return False


# ── sidebar ───────────────────────────────────────────────────────────────────

def sidebar():
    with st.sidebar:
        # ── Brand header ──
        st.markdown("""
        <div style="padding:24px 16px 20px;border-bottom:1px solid #EEF2FF;margin-bottom:8px">
            <div style="display:flex;align-items:center;gap:10px">
                <div style="background:linear-gradient(135deg,#4F46E5,#7C3AED);border-radius:12px;
                            width:38px;height:38px;display:flex;align-items:center;
                            justify-content:center;font-size:20px;flex-shrink:0">🧠</div>
                <div>
                    <div style="font-size:16px;font-weight:800;color:#0F172A;letter-spacing:-0.3px">Second Brain</div>
                    <div style="font-size:11px;color:#94A3B8;font-weight:500;margin-top:1px">AI Memory Assistant</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='padding:0 8px;background:#F8FAFC;border-radius:14px;padding:10px 10px 8px'>", unsafe_allow_html=True)
        st.markdown("<p style='font-size:10px;font-weight:700;color:#475569;letter-spacing:1px;text-transform:uppercase;padding:4px 6px 8px;margin:0'>NAVIGATION</p>", unsafe_allow_html=True)

        nav_items = [
            ("Dashboard",  "🏠", "Dashboard"),
            ("Add Memory", "➕", "Add Memory"),
            ("Memories",   "🗃️", "Memories"),
            ("Diary",      "📔", "Diary"),
            ("Ask AI",     "💬", "Ask AI"),
            ("Reminders",  "⏰", "Reminders"),
            ("Analytics",  "📊", "Analytics"),
            ("Settings",   "⚙️", "Settings"),
        ]

        for key, icon, label in nav_items:
            is_active = st.session_state.page == key
            if is_active:
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,#4F46E5,#7C3AED);border-radius:10px;
                            padding:10px 14px;margin:2px 0;color:#FFFFFF;font-weight:700;
                            font-size:14px;border:1px solid #6366F1;cursor:default">
                    {icon}&nbsp;&nbsp;{label}
                    <span style="float:right;width:6px;height:6px;background:#FFFFFF;
                                 border-radius:50%;display:inline-block;margin-top:5px"></span>
                </div>
                """, unsafe_allow_html=True)
            else:
                if st.button(f"{icon}  {label}", key=f"nav_{key}", use_container_width=True):
                    go(key)
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        # ── Reminder badge ──
        pending = len(pending_reminders())
        if pending:
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div style="margin:0 8px;background:linear-gradient(135deg,#FEF3C7,#FDE68A);
                        border-radius:12px;padding:10px 14px;border:1px solid #FCD34D">
                <div style="display:flex;align-items:center;gap:8px">
                    <span style="font-size:16px">⏰</span>
                    <div>
                        <div style="font-size:13px;font-weight:700;color:#92400E">{pending} pending</div>
                        <div style="font-size:11px;color:#B45309">reminder{'s' if pending > 1 else ''}</div>
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)

        # ── Ollama status footer ──
        st.markdown("<div style='flex:1'></div>", unsafe_allow_html=True)
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        connected = check_ollama_cached()
        status_bg  = "#F0FDF4" if connected else "#FFF5F5"
        status_bdr = "#BBF7D0" if connected else "#FECACA"
        status_clr = "#166534" if connected else "#991B1B"
        status_dot = "#22C55E" if connected else "#EF4444"
        status_txt = "Ollama connected" if connected else "Ollama offline"
        st.markdown(f"""
        <div style="margin:0 8px 16px;background:{status_bg};border-radius:10px;
                    padding:10px 12px;border:1px solid {status_bdr}">
            <div style="display:flex;align-items:center;gap:8px">
                <div style="width:8px;height:8px;background:{status_dot};border-radius:50%;
                            box-shadow:0 0 6px {status_dot}60"></div>
                <span style="font-size:12px;font-weight:600;color:{status_clr}">{status_txt}</span>
            </div>
        </div>""", unsafe_allow_html=True)


# ── dashboard ─────────────────────────────────────────────────────────────────

def dashboard_page():
    print("[Page] Rendering → Dashboard")
    hour = datetime.now().hour
    greeting = "Good Morning" if hour < 12 else ("Good Afternoon" if hour < 17 else "Good Evening")
    icon = "☀️" if hour < 12 else ("🌤️" if hour < 17 else "🌙")
    today = datetime.now().strftime("%A, %B %d")

    # ── Hero header — greeting + date + subtitle in one block ─
    st.markdown(f"""
    <div class="page-header">
        <div style="position:relative;z-index:1">
            <div style="display:inline-block;margin-bottom:10px;padding:6px 10px;border:1px solid rgba(255,255,255,0.24);background:rgba(255,255,255,0.14);border-radius:999px;font-size:11px;font-weight:700;color:#FFFFFF;letter-spacing:0.8px;text-transform:uppercase">
                ✨ Updated private workspace
            </div>
            <div style="font-size:11px;font-weight:600;color:rgba(255,255,255,0.55);
                        letter-spacing:1.2px;text-transform:uppercase;margin-bottom:10px"
            >{today}</div>
            <div style="font-size:28px;font-weight:800;color:#FFFFFF;
                        letter-spacing:-0.5px;line-height:1.15;margin-bottom:8px"
            >{icon} {greeting}!</div>
            <div style="font-size:13.5px;color:rgba(255,255,255,0.72);line-height:1.55;
                        max-width:480px"
            >Your second brain is ready — the calm experience is now live.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Data (unchanged) ─────────────────────────────────────
    all_mem = get_all_memories_cached()
    stats   = get_stats_cached()
    pending = len(pending_reminders())
    week    = this_week_count(all_mem)

    # ── 4 stat cards in a responsive row ─────────────────────
    c1, c2, c3, c4 = st.columns(4)
    for col, val, label, ico in [
        (c1, stats["total_memories"], "Total Memories",   "🧠"),
        (c2, week,                    "Added This Week",   "📅"),
        (c3, len(stats["tags"]),      "Unique Tags",       "🏷️"),
        (c4, pending,                 "Pending Reminders", "⏰"),
    ]:
        with col:
            st.markdown(
                f'<div class="stat-card">'
                f'<div class="stat-icon">{ico}</div>'
                f'<div class="stat-value">{val}</div>'
                f'<div class="stat-label">{label}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    # ── spacing ──────────────────────────────────────────────
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    # ── Quick actions ─────────────────────────────────────────
    st.markdown('<div class="section-label">⚡ &nbsp;Quick Actions</div>', unsafe_allow_html=True)
    qa_c1, qa_c2, qa_c3 = st.columns(3)
    with qa_c1:
        if st.button("＋  Add Memory", use_container_width=True, key="qa_add"):
            go("Add Memory"); st.rerun()
    with qa_c2:
        if st.button("💬  Ask AI", use_container_width=True, key="qa_ask"):
            go("Ask AI"); st.rerun()
    with qa_c3:
        if st.button("🗂  Browse Memories", use_container_width=True, key="qa_browse"):
            go("Memories"); st.rerun()

    # ── spacing ──────────────────────────────────────────────
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    col_l, col_r = st.columns([3, 2], gap="large")

    # ── Recent Memories (tags only — content hidden) ─────────
    with col_l:
        st.markdown('<div class="section-label">🗂 &nbsp;Recent Memories</div>', unsafe_allow_html=True)
        recent = sorted(
            all_mem,
            key=lambda m: m.get("metadata", {}).get("created_at", ""),
            reverse=True
        )[:8]

        if recent:
            for mem in recent:
                tags    = memory_parser.extract_tags(mem.get("content", ""))
                created = mem.get("metadata", {}).get("created_at", "")[:10]
                imp     = float(mem.get("metadata", {}).get("importance", 0))
                mem_type = mem.get("metadata", {}).get("memory_type") or memory_parser.detect_memory_type(mem.get("content", ""))
                type_icon = {"Task": "✅", "Knowledge": "📚", "Personal": "💭", "Event": "📅"}.get(mem_type, "📌")

                tag_html = (
                    "".join(f'<span class="pill-tag">#{t}</span>' for t in tags[:4])
                    if tags else
                    '<span style="font-size:11px;color:#94A3B8;font-style:italic">untagged</span>'
                )
                imp_clr = "#EF4444" if imp >= 0.8 else ("#F59E0B" if imp >= 0.5 else "#CBD5E1")

                st.markdown(
                    f'<div class="memory-preview-card">'
                    f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">'
                    f'<span style="font-size:12px;color:#94A3B8">{type_icon} {mem_type}</span>'
                    f'<span style="font-size:11px;color:#CBD5E1">{created}</span>'
                    f'</div>'
                    f'<div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap">'
                    f'{tag_html}'
                    f'<span style="width:7px;height:7px;border-radius:50%;background:{imp_clr};'
                    f'display:inline-block;margin-left:6px"></span>'
                    f'</div></div>',
                    unsafe_allow_html=True
                )
        else:
            st.markdown(
                '<div class="empty-state">'
                '<div class="es-icon">🧠</div>'
                '<div class="es-title">No memories yet</div>'
                '<div class="es-body">Add your first memory to get started.<br>'
                'Use <b>Add Memory</b> in the sidebar.</div>'
                '</div>',
                unsafe_allow_html=True
            )

    # ── Upcoming Reminders ────────────────────────────────────
    with col_r:
        st.markdown('<div class="section-label">⏰ &nbsp;Upcoming Reminders</div>', unsafe_allow_html=True)
        upcoming = db_get_pending()[:5]

        if upcoming:
            PRI_BORDER_D = {"high": "#EF4444", "medium": "#F59E0B", "low": "#10B981"}
            for r in upcoming:
                due_str = r.due_at.strftime("%b %d") if r.due_at else ""
                border_clr = PRI_BORDER_D.get("medium", "#A5B4FC")
                st.markdown(
                    f'<div style="background:#FFFBEB;border:1px solid #E2E8F0;'
                    f'border-left:4px solid {border_clr};border-radius:10px;'
                    f'padding:12px 16px;margin:4px 0">'
                    f'<div style="font-size:13.5px;font-weight:600;color:#0F172A;'
                    f'margin-bottom:4px;line-height:1.4">{r.description}</div>'
                    f'<div style="font-size:11px;color:#94A3B8">Due {due_str}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
        else:
            st.markdown(
                '<div class="empty-state" style="padding:32px 20px">'
                '<div class="es-icon">✅</div>'
                '<div class="es-title">You\'re all caught up!</div>'
                '<div class="es-body">No pending reminders.<br>Enjoy the clear schedule.</div>'
                '</div>',
                unsafe_allow_html=True
            )


# ── AI analysis helper ───────────────────────────────────────────────────────

def ai_analyze_memory(content: str) -> dict:
    """Use Ollama to analyze memory and return structured suggestions."""
    import re, json as _json

    # rule-based fallback values computed before calling LLM
    lower = content.lower()
    has_deadline = any(w in lower for w in ["tomorrow", "today", "tonight", "urgent", "asap", "deadline", "due", "exam", "test", "submit"])
    has_reminder = any(w in lower for w in ["remind", "don't forget", "remember", "call", "meet", "appointment", "exam", "test", "submit", "tomorrow", "tonight"])
    fallback_imp  = 0.92 if has_deadline else 0.6
    fallback_pri  = "high" if has_deadline else "medium"
    fallback_rem  = content.strip() if has_reminder else None

    prompt = f"""You are a memory classifier. Analyze the note and reply with ONLY a JSON object.

Note: "{content}"

Rules:
- importance: 0.9-1.0 if urgent/deadline/exam/tomorrow, 0.5-0.7 otherwise
- priority: "high" if urgent/exam/deadline, "medium" or "low" otherwise
- tags: 3-5 relevant lowercase single-word tags (no spaces inside a tag)
- type: one of Task, Knowledge, Personal, Event
- reminder: short reminder text if time-sensitive, else null
- summary: one short sentence

Reply with ONLY this JSON, nothing else:
{{"importance": 0.0, "tags": [], "priority": "", "type": "", "reminder": null, "summary": ""}}"""

    try:
        raw = ollama_service.generate(prompt, temperature=0.1)
        match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        if match:
            data = _json.loads(match.group())
            # sanitize tags — split any multi-word tags
            raw_tags = data.get("tags", [])
            clean_tags = []
            for t in raw_tags:
                parts = str(t).lower().replace(",", " ").replace("#", "").split()
                clean_tags.extend(parts)
            data["tags"] = list(dict.fromkeys(clean_tags))[:5]  # dedupe, max 5
            # enforce fallback importance/priority if LLM underestimates urgency
            if has_deadline and float(data.get("importance", 0)) < 0.85:
                data["importance"] = fallback_imp
                data["priority"]   = fallback_pri
            if has_reminder and not data.get("reminder"):
                data["reminder"] = fallback_rem
            return data
    except Exception:
        pass

    # full fallback if LLM fails
    words = [w.strip('.,!?') for w in content.lower().split() if len(w) > 3][:4]
    return {
        "importance": fallback_imp,
        "tags": words,
        "priority": fallback_pri,
        "type": "Task" if has_deadline else "Personal",
        "reminder": fallback_rem,
        "summary": content[:80]
    }


def render_ai_suggestions(s: dict):
    """Render AI suggestions using native Streamlit widgets (no raw HTML blocks)."""
    imp_val  = float(s.get("importance", 0.5))
    pri_val  = str(s.get("priority", "medium")).lower()
    type_val = str(s.get("type", "Personal"))
    tags_val = s.get("tags", [])
    rem_val  = s.get("reminder") or ""
    sum_val  = str(s.get("summary", ""))

    imp_pct = int(imp_val * 100)
    imp_color = "#EF4444" if imp_val > 0.8 else ("#F59E0B" if imp_val > 0.5 else "#6366F1")
    pri_bg    = {"high": "#FEE2E2", "medium": "#FEF3C7", "low": "#D1FAE5"}.get(pri_val, "#EDE9FE")
    pri_fg    = {"high": "#DC2626", "medium": "#D97706", "low": "#059669"}.get(pri_val, "#6366F1")
    type_icon = {"Task": "✅", "Knowledge": "📚", "Personal": "💭", "Event": "📅"}.get(type_val, "📌")

    # header badge
    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">'
        '<span style="font-size:18px">✨</span>'
        '<span style="font-size:15px;font-weight:700;color:#1E1B4B">AI Suggestions</span>'
        '<span style="background:#4F46E5;color:white;font-size:11px;padding:2px 10px;'
        'border-radius:20px;font-weight:600;letter-spacing:0.5px">AUTO</span></div>',
        unsafe_allow_html=True
    )

    # summary
    st.markdown(
        f'<div style="background:#F5F3FF;border-left:3px solid #6366F1;border-radius:10px;'
        f'padding:10px 14px;font-size:13px;color:#4B5563;font-style:italic;margin-bottom:14px">'
        f'&ldquo;{sum_val}&rdquo;</div>',
        unsafe_allow_html=True
    )

    # importance + priority row
    c1, c2 = st.columns(2)
    with c1:
        bar_html = (
            f'<div style="background:#F3F4F6;border-radius:6px;height:8px;margin-top:6px">'
            f'<div style="background:{imp_color};width:{imp_pct}%;height:8px;border-radius:6px"></div></div>'
        )
        st.markdown(
            f'<div style="background:#FFFFFF;border-radius:14px;padding:16px;border:1px solid #E0E7FF;'
            f'box-shadow:0 1px 4px rgba(99,102,241,0.07)">'
            f'<div style="font-size:11px;color:#6B7280;font-weight:600;letter-spacing:0.5px">⚡ IMPORTANCE</div>'
            f'<div style="font-size:26px;font-weight:700;color:{imp_color};margin-top:4px">{imp_pct}%</div>'
            f'{bar_html}</div>',
            unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            f'<div style="background:#FFFFFF;border-radius:14px;padding:16px;border:1px solid #E0E7FF;'
            f'box-shadow:0 1px 4px rgba(99,102,241,0.07)">'
            f'<div style="font-size:11px;color:#6B7280;font-weight:600;letter-spacing:0.5px">🎯 PRIORITY</div>'
            f'<div style="margin-top:8px">'
            f'<span style="background:{pri_bg};color:{pri_fg};font-size:13px;font-weight:700;'
            f'padding:5px 14px;border-radius:20px">{pri_val.upper()}</span></div></div>',
            unsafe_allow_html=True
        )

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # tags row
    tag_pills = "".join(
        f'<span style="display:inline-block;background:#EDE9FE;color:#7C3AED;border-radius:20px;'
        f'padding:4px 12px;font-size:12px;font-weight:500;margin:3px 4px 3px 0">#{t}</span>'
        for t in tags_val
    )
    st.markdown(
        f'<div style="background:#FFFFFF;border-radius:14px;padding:16px;border:1px solid #E0E7FF;'
        f'box-shadow:0 1px 4px rgba(99,102,241,0.07);margin-bottom:10px">'
        f'<div style="font-size:11px;color:#6B7280;font-weight:600;letter-spacing:0.5px;margin-bottom:8px">🏷️ SUGGESTED TAGS</div>'
        f'<div>{tag_pills if tag_pills else "<span style=color:#9CA3AF>No tags detected</span>"}</div></div>',
        unsafe_allow_html=True
    )

    # type + reminder row
    c3, c4 = st.columns(2)
    with c3:
        st.markdown(
            f'<div style="background:#FFFFFF;border-radius:14px;padding:16px;border:1px solid #E0E7FF;'
            f'box-shadow:0 1px 4px rgba(99,102,241,0.07)">'
            f'<div style="font-size:11px;color:#6B7280;font-weight:600;letter-spacing:0.5px">📂 TYPE</div>'
            f'<div style="font-size:15px;font-weight:600;color:#1E1B4B;margin-top:6px">{type_icon} {type_val}</div></div>',
            unsafe_allow_html=True
        )
    with c4:
        rem_bg  = "#FFF7ED" if rem_val else "#FFFFFF"
        rem_bdr = "#FED7AA" if rem_val else "#E0E7FF"
        rem_txt = f'🔔 {rem_val}' if rem_val else "None detected"
        rem_clr = "#C2410C" if rem_val else "#9CA3AF"
        st.markdown(
            f'<div style="background:{rem_bg};border-radius:14px;padding:16px;border:1px solid {rem_bdr};'
            f'box-shadow:0 1px 4px rgba(99,102,241,0.07)">'
            f'<div style="font-size:11px;color:#6B7280;font-weight:600;letter-spacing:0.5px">⏰ REMINDER</div>'
            f'<div style="font-size:13px;color:{rem_clr};margin-top:6px;font-weight:500">{rem_txt}</div></div>',
            unsafe_allow_html=True
        )

    return tags_val, rem_val, imp_val, pri_val, type_val


# ── add memory ────────────────────────────────────────────────────────────────

def add_memory_page():
    print("[Page] Rendering → Add Memory")
    if not security_gate("Add Memory"):
        return

    for k, v in [("add_mode", "auto"), ("ai_suggestions", None),
                 ("analyzed_content", ""), ("manual_priority", "medium"),
                 ("selected_emotion", "neutral"), ("toast", None)]:
        if k not in st.session_state:
            st.session_state[k] = v

    # ── Toast notification ────────────────────────────────────
    if st.session_state.toast:
        t = st.session_state.toast
        icon  = {"success": "✅", "error": "❌", "info": "ℹ️", "warning": "⚠️"}.get(t["type"], "ℹ️")
        color = {"success": "#10B981", "error": "#EF4444", "info": "#6366F1", "warning": "#F59E0B"}.get(t["type"], "#6366F1")
        bg    = {"success": "#F0FDF4", "error": "#FFF5F5", "info": "#EEF2FF", "warning": "#FFFBEB"}.get(t["type"], "#EEF2FF")
        bdr   = {"success": "#BBF7D0", "error": "#FECACA", "info": "#C7D2FE", "warning": "#FDE68A"}.get(t["type"], "#C7D2FE")
        st.markdown(
            f'<div class="toast toast-{t["type"]}" style="background:{bg};border-color:{bdr};color:{color}">'
            f'<span style="font-size:18px">{icon}</span>'
            f'<span style="font-size:14px;font-weight:600">{t["msg"]}</span>'
            f'</div>',
            unsafe_allow_html=True
        )
        st.session_state.toast = None

    st.markdown("""
    <div class="page-header">
        <h1>➕ Add New Memory</h1>
        <p>Capture your thoughts, ideas, and tasks. AI will enrich them automatically.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="journal-card">', unsafe_allow_html=True)
    st.markdown('<div class="journal-title-hint">What is on your mind today?</div>', unsafe_allow_html=True)

    st.markdown('<div class="emotion-row">', unsafe_allow_html=True)
    emotion_labels = {"calm": "🌿 Calm", "happy": "😊 Happy", "neutral": "😐 Neutral", "stressed": "😟 Stressed", "sad": "💙 Sad"}
    for emo, label in emotion_labels.items():
        active = st.session_state.get("selected_emotion", "neutral") == emo
        if st.button(label, key=f"emo_{emo}", use_container_width=False,
                     type="primary" if active else "secondary"):
            st.session_state["selected_emotion"] = emo
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    t1, t2, t3, t4, _ = st.columns([1, 1, 1, 1, 2])
    for col, mode, label in [(t1, "auto", "🤖 Auto"), (t2, "manual", "✏️ Manual"), (t3, "voice", "🎤 Voice"), (t4, "image", "🖼️ Image")]:
        with col:
            active = st.session_state.add_mode == mode
            if st.button(label, use_container_width=True,
                         type="primary" if active else "secondary",
                         key=f"mode_{mode}"):
                st.session_state.add_mode = mode
                st.session_state.ai_suggestions = None
                st.rerun()

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        st.markdown('<div class="input-card">', unsafe_allow_html=True)
        st.markdown('<div class="input-card-header"><span>📝</span> Memory</div>', unsafe_allow_html=True)

        if st.session_state.add_mode == "voice":
            st.markdown(
                '<div class="upload-zone" style="background:#F5F3FF;border-color:#DDD6FE">'
                '<div style="font-size:13px;font-weight:600;color:#6366F1;margin-bottom:10px">🎤 Voice recording</div>',
                unsafe_allow_html=True
            )
            audio = st.audio_input("Record your memory", label_visibility="collapsed", key="voice_audio")
            st.markdown('</div>', unsafe_allow_html=True)
            if audio:
                st.info("Speech-to-text would appear here. Paste the transcript below.")
                memory_content = st.text_area(
                    "Transcribed text", height=120, key="voice_transcript",
                    placeholder="Paste or edit the transcribed text…"
                )
            else:
                memory_content = ""
                st.caption("Press the microphone button to record a memory.")

        elif st.session_state.add_mode == "image":
            st.markdown(
                '<div class="upload-zone">'
                '<div style="font-size:32px;margin-bottom:8px">🖼️</div>'
                '<div style="font-size:14px;font-weight:600;color:#6366F1;margin-bottom:4px">Upload an image</div>'
                '<div style="font-size:12px;color:#94A3B8">PNG, JPG, JPEG, WEBP — max 10 MB</div>',
                unsafe_allow_html=True
            )
            uploaded_img = st.file_uploader(
                "Upload image", type=["png", "jpg", "jpeg", "webp"],
                label_visibility="collapsed", key="add_img_upload"
            )
            st.markdown('</div>', unsafe_allow_html=True)
            if uploaded_img:
                st.image(uploaded_img, use_container_width=True)
                st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
                memory_content = st.text_area(
                    "Caption / notes about this image", height=100,
                    placeholder="Describe what this image means to you…",
                    key="add_img_caption"
                )
                st.markdown(
                    f'<div class="upload-meta">'
                    f'<span>📎 {uploaded_img.name}</span>'
                    f'<span>{round(uploaded_img.size / 1024, 1)} KB</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            else:
                memory_content = ""

        else:
            memory_content = st.text_area(
                "Memory content", height=220, label_visibility="collapsed",
                placeholder="e.g. I have a lab exam tomorrow, revise Unit 3…",
                key="add_mem_content"
            )

        if detect_reminder(memory_content):
            st.markdown('<div class="reminder-detected-chip">⏰ Reminder detected — will be added automatically</div>', unsafe_allow_html=True)

        if st.session_state.add_mode == "auto":
            if st.button("✨ Analyse with AI", use_container_width=True, type="primary", key="ai_analyze"):
                if memory_content.strip():
                    with st.spinner("AI is analysing your memory…"):
                        result = ai_analyze_memory(memory_content)
                        st.session_state.ai_suggestions = result
                        st.session_state.analyzed_content = memory_content
                        st.rerun()
                else:
                    st.warning("Write a memory first.")

            if st.session_state.ai_suggestions:
                st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
                st.markdown('<div class="ai-panel">', unsafe_allow_html=True)
                tags_val, rem_val, imp_val, pri_val, type_val = render_ai_suggestions(st.session_state.ai_suggestions)
                st.markdown('</div>', unsafe_allow_html=True)
                edited_tags = st.text_input(
                    "Edit tags", value=" ".join(tags_val), label_visibility="collapsed", key="ai_edit_tags"
                )
                if st.button("💾 Save Memory", type="primary", use_container_width=True, key="save_ai"):
                    final_tags = [t.strip().lstrip("#") for t in edited_tags.split() if t.strip()]
                    metadata = {
                        "importance": imp_val, "tags": final_tags, "priority": pri_val,
                        "memory_type": type_val, "created_at": datetime.now().isoformat(),
                        "access_count": 0, "type": "auto"
                    }
                    memory_store.store_memory(st.session_state.analyzed_content, metadata)
                    bust_memory_cache()
                    reminder_text = rem_val or (extract_reminder_text(st.session_state.analyzed_content) if detect_reminder(st.session_state.analyzed_content) else None)
                    reminder_info = infer_reminder_from_content(st.session_state.analyzed_content)
                    if reminder_info["should_create"]:
                        db_create_reminder(description=reminder_info["text"], due_at=reminder_info["due_at"], priority="medium")
                        st.session_state.toast = {"type": "success", "msg": "Memory saved + reminder auto-added!"}
                    elif reminder_text:
                        db_create_reminder(description=reminder_text, due_at=datetime.now() + timedelta(days=1), priority="medium")
                        st.session_state.toast = {"type": "success", "msg": "Memory saved + reminder auto-added!"}
                    else:
                        st.session_state.toast = {"type": "success", "msg": "Memory saved with AI enhancements!"}
                    st.session_state.ai_suggestions = None
                    st.session_state.analyzed_content = ""
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="input-card">', unsafe_allow_html=True)
        st.markdown('<div class="input-card-header"><span>⚙️</span> Details</div>', unsafe_allow_html=True)

        manual_tags_input = st.text_input(
            "Tags", placeholder="work health goals…",
            label_visibility="collapsed", key="manual_tags_input"
        )
        if manual_tags_input.strip():
            pills = "".join(f'<span class="pill-tag">#{t.lstrip("#")}</span>' for t in manual_tags_input.split() if t.strip())
            st.markdown(f"<div style='margin:4px 0 12px'>{pills}</div>", unsafe_allow_html=True)

        st.markdown('<div style="font-size:11px;font-weight:700;color:#94A3B8;letter-spacing:0.8px;text-transform:uppercase;margin-bottom:8px">🎯 Priority</div>', unsafe_allow_html=True)
        p_low, p_med, p_high = st.columns(3)
        for pcol, pval, plabel in [(p_low, "low", "🟢 Low"), (p_med, "medium", "🟡 Med"), (p_high, "high", "🔴 High")]:
            with pcol:
                selected = st.session_state.manual_priority == pval
                if st.button(plabel, key=f"pri_{pval}", use_container_width=True, type="primary" if selected else "secondary"):
                    st.session_state.manual_priority = pval
                    st.rerun()

        remind_priority = st.session_state.manual_priority
        badge_map = {"low": ("#DCFCE7", "#16A34A"), "medium": ("#FEF3C7", "#D97706"), "high": ("#FEE2E2", "#DC2626")}
        bg, fg = badge_map[remind_priority]
        st.markdown(f'<div style="margin:8px 0 14px"><span style="background:{bg};color:{fg};font-size:12px;font-weight:700;padding:4px 14px;border-radius:20px;letter-spacing:0.4px">{remind_priority.upper()} selected</span></div>', unsafe_allow_html=True)

        importance = st.slider("Importance", 0.0, 1.0, 0.5, 0.1, key="add_imp_manual", label_visibility="collapsed")
        imp_word = "Critical" if importance >= 0.9 else ("High" if importance >= 0.7 else ("Medium" if importance >= 0.4 else "Low"))
        imp_clr = "#EF4444" if importance >= 0.8 else ("#F59E0B" if importance >= 0.5 else "#6366F1")
        st.markdown(f'<span class="imp-label" style="color:{imp_clr}">⚡ Importance: {importance:.2f} — {imp_word}</span>', unsafe_allow_html=True)

        remind_text = st.text_input("Reminder", placeholder="e.g. Take water bottle for gym", label_visibility="collapsed", key="add_remind_text")

        if st.button("💾 Save Memory", type="primary", use_container_width=True, key="save_manual"):
            if memory_content.strip():
                auto_tags = memory_parser.extract_tags(memory_content)
                manual_tags = [t.strip().lstrip("#") for t in manual_tags_input.split() if t.strip()]
                all_tags = list(set(auto_tags + manual_tags))
                calc_imp = memory_parser.calculate_content_importance(memory_content)
                metadata = {
                    "importance": max(importance, calc_imp),
                    "tags": all_tags,
                    "priority": remind_priority,
                    "created_at": datetime.now().isoformat(),
                    "access_count": 0,
                    "type": "manual"
                }
                memory_store.store_memory(memory_content, metadata)
                bust_memory_cache()

                reminder_info = infer_reminder_from_content(memory_content)
                if remind_text.strip():
                    db_create_reminder(description=remind_text.strip(), due_at=datetime.now() + timedelta(days=1), priority=remind_priority)
                    st.session_state.toast = {"type": "success", "msg": "Memory saved + reminder added!"}
                elif reminder_info["should_create"]:
                    db_create_reminder(description=reminder_info["text"], due_at=reminder_info["due_at"], priority=remind_priority)
                    st.session_state.toast = {"type": "success", "msg": f"Memory saved! Reminder: '{reminder_info['text']}'"}
                elif detect_reminder(memory_content):
                    auto_rem = extract_reminder_text(memory_content)
                    db_create_reminder(description=auto_rem, due_at=datetime.now() + timedelta(days=1), priority=remind_priority)
                    st.session_state.toast = {"type": "success", "msg": f"Memory saved! Reminder auto-detected: '{auto_rem}'"}
                else:
                    st.session_state.toast = {"type": "success", "msg": "Memory saved!"}
                st.rerun()
            else:
                st.session_state.toast = {"type": "error", "msg": "Please write something in the Memory field first."}
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ── memories ──────────────────────────────────────────────────────────────────

def memories_page():
    print("[Page] Rendering → Memories")
    if not security_gate("Memories"):
        return

    st.markdown("""
    <div class="page-header">
        <h1>🗃️ Your Memories</h1>
        <p>Browse, search, and manage everything you've captured.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="input-card">', unsafe_allow_html=True)

    # ── Filter row
    fc1, fc2, fc3 = st.columns([3, 1.4, 1.4])
    with fc1:
        search = st.text_input("Search", placeholder="🔍  Search by keyword or tag…",
                               label_visibility="collapsed", key="memories_search")
    with fc3:
        pri_filter = st.selectbox("Priority", ["All Priorities", "High", "Medium", "Low"],
                                  label_visibility="collapsed", key="memories_pri_filter")

    # ── Load + sort
    all_mem = get_all_memories_cached()
    all_mem = sorted(all_mem, key=lambda m: m.get("metadata", {}).get("created_at", ""), reverse=True)

    unique_tags = sorted({t for m in all_mem for t in memory_parser.extract_tags(m.get("content", ""))})
    with fc2:
        tag_filter = st.selectbox("Tag", ["All Tags"] + unique_tags,
                                  label_visibility="collapsed", key="memories_tag_filter")

    # ── Apply filters
    if search:
        all_mem = [m for m in all_mem if search.lower() in m.get("content", "").lower()]
    if tag_filter != "All Tags":
        all_mem = [m for m in all_mem
                   if tag_filter in memory_parser.extract_tags(m.get("content", ""))]
    if pri_filter != "All Priorities":
        pf = pri_filter.lower()
        def _pri_match(m):
            meta = m.get("metadata", {})
            pri  = str(meta.get("priority", "")).lower()
            imp  = float(meta.get("importance", 0.5))
            if pf == "high":   return pri == "high"   or imp >= 0.8
            if pf == "low":    return pri == "low"    or imp <  0.4
            return pri == "medium" or (0.4 <= imp < 0.8)
        all_mem = [m for m in all_mem if _pri_match(m)]

    # ── Important memories filter
    show_important = st.checkbox("⭐ Show only important memories (score ≥ 0.7)", key="memories_important_filter")
    if show_important:
        important_ids = {m["id"] for m in memory_decay.get_important_memories(min_score=0.7)}
        all_mem = [m for m in all_mem if m.get("id") in important_ids]

    # ── Section label
    count  = len(all_mem)
    suffix = ' matching "' + search + '"' if search else ""
    st.markdown(
        '<div class="section-label" style="margin-top:16px">'
        + "📄 &nbsp;" + str(count)
        + " memor" + ("y" if count == 1 else "ies") + suffix + "</div>",
        unsafe_allow_html=True
    )

    if not all_mem:
        st.markdown("""
        <div class="empty-state">
            <div class="es-icon">🔍</div>
            <div class="es-title">No memories found</div>
            <div class="es-body">Try a different search term or clear the filters.</div>
        </div>""", unsafe_allow_html=True)
        return

    # ── Memory cards
    PRI_BADGE = {
        "high":   ("#FEE2E2", "#DC2626"),
        "medium": ("#FEF3C7", "#D97706"),
        "low":    ("#DCFCE7", "#16A34A"),
    }

    for mem in all_mem:
        content  = mem.get("content", "")
        metadata = mem.get("metadata", {})
        tags     = memory_parser.extract_tags(content)
        imp      = float(metadata.get("importance", 0.5))
        created  = metadata.get("created_at", "")[:10]
        mem_id   = mem.get("id", "")
        mem_type = metadata.get("memory_type") or memory_parser.detect_memory_type(content)
        deadline = memory_parser.extract_deadlines(content)

        pri_raw = str(metadata.get("priority", "")).lower()
        if pri_raw not in PRI_BADGE:
            pri_raw = "high" if imp >= 0.8 else ("low" if imp < 0.4 else "medium")
        pri_bg, pri_fg = PRI_BADGE[pri_raw]

        raw_title = content.split("\n")[0].split(".")[0]
        title = raw_title[:72] + ("…" if len(raw_title) > 72 else "")

        tag_html = (
            "".join('<span class="pill-tag">#' + t + '</span>' for t in tags[:5])
            if tags else
            '<span style="font-size:11px;color:#94A3B8;font-style:italic">untagged</span>'
        )

        filled = int(round(imp * 5))
        star_html = "".join(
            '<span style="color:#F59E0B;font-size:13px">' + ("★" if i < filled else "☆") + '</span>'
            for i in range(5)
        )

        body = content[:180] + ("…" if len(content) > 180 else "")

        card = (
            '<div class="memory-full-card">'
            '<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:6px">'
            '<div style="font-size:14px;font-weight:700;color:#0F172A;line-height:1.4;flex:1">'
            + title
            + ('<span style="background:#EDE9FE;color:#6366F1;font-size:10px;font-weight:700;'
               'padding:2px 8px;border-radius:10px;margin-left:6px">'
               + {'Task':'✅','Knowledge':'📚','Personal':'💭','Event':'📅'}.get(mem_type,'📌')
               + ' ' + mem_type + '</span>')
            + ('⏰ <span style="background:#FEF3C7;color:#D97706;font-size:10px;font-weight:700;'
               'padding:2px 8px;border-radius:10px;margin-left:4px">' + deadline[0] + '</span>' if deadline else '')
            + '</div>'
            '<span style="font-size:11px;color:#94A3B8;white-space:nowrap;flex-shrink:0">📅 ' + created + '</span>'
            '</div>'
            '<div style="font-size:13px;color:#64748B;line-height:1.55;margin-bottom:12px">' + body + '</div>'
            '<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">'
            '<div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap">' + tag_html + '</div>'
            '<div style="display:flex;align-items:center;gap:10px;flex-shrink:0">'
            '<div title="Importance ' + str(int(imp * 100)) + '%">' + star_html + '</div>'
            '<span style="background:' + pri_bg + ';color:' + pri_fg + ';font-size:11px;font-weight:700;'
            'padding:2px 10px;border-radius:20px;letter-spacing:0.4px;text-transform:uppercase">'
            + pri_raw + '</span>'
            '</div></div></div>'
        )
        st.markdown(card, unsafe_allow_html=True)

        # ── Gap 2: update access count when memory is viewed ─
        memory_store.update_access_count(mem_id)

        btn_c1, btn_c2, btn_c3, btn_c4 = st.columns([1, 1, 1, 3])
        with btn_c1:
            if st.button("🗑️ Delete", key="del_" + mem_id):
                print("[Memory] Deleting memory id=" + mem_id)
                memory_store.delete_memory(mem_id)
                bust_memory_cache()
                st.rerun()
        with btn_c2:
            if st.button("✨ Summarise", key="sum_" + mem_id):
                with st.spinner("Generating summary…"):
                    summary = rag_engine.summarize_memory(mem_id)
                if summary:
                    st.info(f"**AI Summary:** {summary}")
        with btn_c3:
            if st.button("💡 Enhance", key="enh_" + mem_id):
                with st.spinner("Enhancing…"):
                    enhancement = rag_engine.enhance_memory_with_query(mem_id, "provide context and insight")
                if enhancement:
                    st.info(f"**AI Enhancement:** {enhancement}")
        with btn_c4:
            if st.button("🔗 Related", key="rel_" + mem_id):
                with st.spinner("Finding related memories…"):
                    related = rag_engine.find_related_memories(mem_id, top_k=3)
                if related:
                    with st.expander(f"🔗 {len(related)} related memor{'y' if len(related)==1 else 'ies'}", expanded=True):
                        for r in related:
                            st.markdown(
                                f'<div style="background:#F8FAFF;border-radius:8px;padding:10px 14px;'
                                f'margin:4px 0;border-left:3px solid #6366F1;font-size:13px;color:#475569">'
                                f'{r["content"][:150]}{"…" if len(r["content"])>150 else ""}</div>',
                                unsafe_allow_html=True
                            )
                else:
                    st.info("No related memories found.")


# ── ask ai ────────────────────────────────────────────────────────────────────

def ask_ai_page():
    print("[Page] Rendering → Ask AI")
    st.markdown("""
    <div class="page-header">
        <h1>💬 Ask Your Memory AI</h1>
        <p>Ask questions about your stored memories. AI uses your personal knowledge base to answer.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="input-card">', unsafe_allow_html=True)

    # chat history
    if not st.session_state.conversation:
        st.markdown("""
        <div class="empty-state">
            <div class="es-icon">🤖</div>
            <div class="es-title">Start a conversation</div>
            <div class="es-body">Ask anything — your AI will search your memories and answer with context.<br>
               Try: “What meetings do I have?” or “What are my goals?”</div>
        </div>""", unsafe_allow_html=True)
    else:
        for item in st.session_state.conversation:
            st.markdown(
                f'<div class="chat-user">{item["query"]}</div>',
                unsafe_allow_html=True
            )
            grounded = item.get("grounded", False)
            used     = item.get("memories_used", 0)
            badge    = (
                f'<span style="background:#DCFCE7;color:#166534;font-size:10px;font-weight:700;'
                f'padding:2px 8px;border-radius:10px;margin-left:8px">🧠 {used} memor{"y" if used==1 else "ies"}</span>'
                if grounded else
                '<span style="background:#F1F5F9;color:#64748B;font-size:10px;font-weight:700;'
                'padding:2px 8px;border-radius:10px;margin-left:8px">🌐 general knowledge</span>'
            )
            st.markdown(
                f'<div class="chat-ai"><span style="font-size:16px">🤖</span>{badge}<br><br>{item["response"]}</div>',
                unsafe_allow_html=True
            )
            if item.get("sources"):
                with st.expander(f"📖 Based on {len(item['sources'])} memor{'y' if len(item['sources'])==1 else 'ies'}", expanded=False):
                    for s in item["sources"]:
                        st.markdown(
                            f'<div class="source-chip">{s["content"][:150]}{"..." if len(s["content"])>150 else ""}</div>',
                            unsafe_allow_html=True
                        )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    query = st.text_input("Ask", placeholder="🔍 Ask anything from your memories…",
                          label_visibility="collapsed", key="chat_q")

    c1, c2 = st.columns([1, 5])
    with c1:
        ask = st.button("🚀 Ask", type="primary", use_container_width=True)
    with c2:
        if st.button("🗑️ Clear chat", use_container_width=True):
            st.session_state.conversation = []
            st.rerun()

    if ask and query.strip():
        print(f"[RAG] Query received: '{query}'")
        with st.spinner("🤔 Searching your memories…"):
            try:
                result = rag_engine.ask_memory(query)
                print(f"[RAG] Response generated | sources used: {result.get('memories_used', 0)}")
                used = result.get('memories_used', 0)
                st.session_state.conversation.append({
                    "query": query,
                    "response": result.get("response", ""),
                    "sources": result.get("source_memories", []),
                    "memories_used": used,
                    "grounded": used > 0,
                })
                st.rerun()
            except Exception as e:
                print(f"[RAG] ❌ Error: {e}")
                st.error(f"Error: {e}")
    elif ask:
        st.warning("Please type a question first.")


# ── reminders ─────────────────────────────────────────────────────────────────


def reminders_page():
    print("[Page] Rendering → Reminders")
    st.markdown("""
    <div class="page-header">
        <h1>⏰ Reminders</h1>
        <p>Stay on top of your tasks and upcoming deadlines.</p>
    </div>
    """, unsafe_allow_html=True)

    if "show_add_reminder" not in st.session_state:
        st.session_state.show_add_reminder = False

    st.markdown('<div class="input-card">', unsafe_allow_html=True)
    top_row = st.columns([4, 1])
    with top_row[1]:
        if st.button("➕ Add reminder", type="primary", key="rem_toggle", use_container_width=True):
            st.session_state.show_add_reminder = not st.session_state.show_add_reminder
            st.rerun()
    if st.session_state.show_add_reminder:
        fc1, fc2, fc3, fc4 = st.columns([3, 1.5, 1.2, 1])
        with fc1:
            r_text = st.text_input("Reminder text", placeholder="e.g. Submit report next week",
                                   label_visibility="collapsed", key="rem_text")
        with fc2:
            r_due = st.date_input("Due date", value=datetime.now().date() + timedelta(days=1),
                                  label_visibility="collapsed", key="rem_due")
        with fc3:
            r_pri = st.selectbox("Priority", ["high", "medium", "low"],
                                 label_visibility="collapsed", key="rem_pri")
        with fc4:
            if st.button("💾 Save", type="primary", use_container_width=True, key="rem_add"):
                if r_text.strip():
                    due_dt = datetime.combine(r_due, datetime.min.time())
                    db_create_reminder(description=r_text.strip(), due_at=due_dt, priority=r_pri)
                    st.session_state.show_add_reminder = False
                    print(f"[Reminder] Created: '{r_text.strip()}' due={due_dt} priority={r_pri}")
                    st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    PRI_BORDER = {"high": "#EF4444", "medium": "#F59E0B", "low": "#10B981"}
    PRI_BG = {"high": "#FFF5F5", "medium": "#FFFBEB", "low": "#F0FDF4"}
    PRI_BADGE = {
        "high": ("#FEE2E2", "#DC2626"),
        "medium": ("#FEF3C7", "#D97706"),
        "low": ("#DCFCE7", "#16A34A"),
    }

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Load from SQLite ──────────────────────────────────────────────────────
    pending_rows = db_get_pending()
    recent_rows  = get_recent_completed_missed(hours=24)

    def _due_label(r):
        now = datetime.utcnow()
        delta = (r.due_at - now).total_seconds() / 3600
        if delta < -1:   return f"Overdue by {int(-delta // 24)}d {int((-delta) % 24)}h"
        if delta < 0:    return "Due now"
        if delta < 24:   return f"Due in {int(delta)}h"
        days = int(delta // 24)
        if days == 1:    return "Due tomorrow"
        return f"Due in {days}d"

    def render_db_reminder(r, faded=False):
        """Render a SQLAlchemy Reminder row."""
        p = getattr(r, "priority", None)
        # priority is a ReminderPriority enum — get its string value
        if hasattr(p, "value"):
            p = p.value
        if p not in PRI_BORDER:
            p = "medium"
        border_clr = PRI_BORDER.get(p, "#A5B4FC")
        bg_clr     = PRI_BG.get(p, "#FAFBFF")
        badge_bg, badge_fg = PRI_BADGE.get(p, ("#EDE9FE", "#4F46E5"))
        due_str    = _due_label(r)
        text_style = (
            "font-size:14px;font-weight:600;color:#94A3B8;text-decoration:line-through"
            if faded else "font-size:14px;font-weight:600;color:#0F172A"
        )
        opacity = "opacity:0.55;" if faded else ""
        status_badge = (
            f'<span style="background:#DCFCE7;color:#16A34A;font-size:10px;font-weight:700;'
            f'padding:2px 8px;border-radius:10px">{r.status.value.upper()}</span>'
        )

        col_card, col_b1, col_b2, col_b3 = st.columns([9, 1, 1, 1])
        with col_card:
            st.markdown(
                f'<div class="reminder-card {p}" style="{opacity}">'
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">'
                f'{status_badge}'
                f'<span style="font-size:11px;font-weight:600;color:#64748B">{due_str}</span>'
                f'<span style="font-size:11px;color:#94A3B8">{r.due_at.strftime("%b %d, %Y")}</span>'
                f'</div>'
                f'<div style="{text_style}">{r.description}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        if not faded:
            with col_b1:
                if st.button("✅", key=f"done_{r.id}", help="Mark complete"):
                    db_mark_complete(r.id)
                    print(f"[Reminder] Completed: {r.id[:8]}")
                    st.rerun()
            with col_b2:
                if st.button("💤", key=f"snooze_{r.id}", help="Snooze 1 day"):
                    db_snooze(r.id, r.due_at + timedelta(days=1))
                    st.rerun()
            with col_b3:
                if st.button("✕", key=f"dismiss_{r.id}", help="Dismiss"):
                    db_dismiss(r.id)
                    st.rerun()

    # ── Pending section ───────────────────────────────────────────────────────
    if not pending_rows and not recent_rows:
        st.markdown("""
        <div class="empty-state">
            <div class="es-icon">🎉</div>
            <div class="es-title">All clear!</div>
            <div class="es-body">No reminders yet. Add one above or save a memory with a deadline.</div>
        </div>""", unsafe_allow_html=True)
        return

    now = datetime.utcnow()
    overdue  = [r for r in pending_rows if r.due_at < now]
    upcoming = [r for r in pending_rows if r.due_at >= now]

    for group_label, group_icon, group in [
        ("Overdue",  "🔴", overdue),
        ("Upcoming", "🟢", upcoming),
    ]:
        if not group:
            continue
        st.markdown(
            f'<div class="section-label" style="margin-top:18px">{group_icon} &nbsp;{group_label} ({len(group)})</div>',
            unsafe_allow_html=True
        )
        for r in group:
            render_db_reminder(r)

    if not pending_rows:
        st.markdown("""
        <div class="empty-state" style="padding:24px">
            <div class="es-icon">✅</div>
            <div class="es-title">You're all caught up!</div>
            <div class="es-body">No pending reminders.</div>
        </div>""", unsafe_allow_html=True)

    # ── Recently completed / missed (last 24h) ────────────────────────────────
    if recent_rows:
        with st.expander(f"🕐 Recently completed / missed ({len(recent_rows)} in last 24h)", expanded=False):
            for r in recent_rows:
                render_db_reminder(r, faded=True)


# ── diary ────────────────────────────────────────────────────────────────────

def diary_page():
    print("[Page] Rendering → Diary")
    if not security_gate("Diary"):
        return

    user_id = (st.session_state.current_user or {}).get("id")

    st.markdown("""
    <div class="page-header">
        <h1>📔 Digital Diary</h1>
        <p>Your private journal — write freely, search semantically, ask AI about your past.</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Tab layout ────────────────────────────────────────────────────────────
    tab_write, tab_browse, tab_search = st.tabs(["  ✍️  Write  ", "  📅  Browse  ", "  🔍  Search  "])

    # ── WRITE tab ─────────────────────────────────────────────────────────────
    with tab_write:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        col_l, col_r = st.columns([3, 1], gap="large")

        with col_l:
            st.markdown('<div class="input-card">', unsafe_allow_html=True)

            # Edit mode: pre-fill if editing an existing entry
            editing_id = st.session_state.get("diary_editing_id")
            prefill_content = ""
            prefill_date = datetime.now().date()
            prefill_mood = ""
            prefill_tags = ""

            if editing_id:
                existing = diary_get(editing_id, user_id=user_id)
                if existing:
                    prefill_content = existing.get("content", "")
                    prefill_date = datetime.fromisoformat(existing["entry_date"]).date()
                    prefill_mood = existing.get("mood") or ""
                    prefill_tags = existing.get("tags") or ""
                    st.info(f"✏️ Editing entry from {prefill_date}")

            diary_content = st.text_area(
                "What\'s on your mind?",
                value=prefill_content,
                height=280,
                placeholder="Write about your day, thoughts, goals, achievements…",
                key="diary_content_input",
                label_visibility="collapsed",
            )
            st.markdown('</div>', unsafe_allow_html=True)

        with col_r:
            st.markdown('<div class="input-card">', unsafe_allow_html=True)
            entry_date = st.date_input("Entry date", value=prefill_date, key="diary_date_input")

            MOODS = ["", "🌟 Great", "😊 Good", "😐 Okay", "😔 Low", "😟 Rough"]
            mood_idx = MOODS.index(prefill_mood) if prefill_mood in MOODS else 0
            mood = st.selectbox("Mood", MOODS, index=mood_idx, key="diary_mood_input")

            tags_input = st.text_input(
                "Tags", value=prefill_tags,
                placeholder="e.g. goals, work, health",
                key="diary_tags_input",
            )

            if editing_id:
                save_col, cancel_col = st.columns(2)
                with save_col:
                    if st.button("💾 Update", type="primary", use_container_width=True, key="diary_update_btn"):
                        if diary_content.strip():
                            diary_update(
                                editing_id,
                                content=diary_content.strip(),
                                mood=mood or None,
                                tags=tags_input.strip() or None,
                                user_id=user_id,
                            )
                            st.session_state.diary_editing_id = None
                            st.success("✅ Entry updated!")
                            st.rerun()
                        else:
                            st.warning("Write something first.")
                with cancel_col:
                    if st.button("✕ Cancel", use_container_width=True, key="diary_cancel_btn"):
                        st.session_state.diary_editing_id = None
                        st.rerun()
            else:
                if st.button("💾 Save Entry", type="primary", use_container_width=True, key="diary_save_btn"):
                    if diary_content.strip():
                        entry_dt = datetime.combine(entry_date, datetime.min.time())
                        diary_create(
                            content=diary_content.strip(),
                            entry_date=entry_dt,
                            user_id=user_id,
                            mood=mood or None,
                            tags=tags_input.strip() or None,
                        )
                        # Also ingest into memory pipeline for RAG
                        try:
                            from backend.reminder_utils import infer_reminder_from_content
                            reminder_info = infer_reminder_from_content(diary_content.strip())
                            if reminder_info["should_create"]:
                                db_create_reminder(
                                    description=reminder_info["text"],
                                    due_at=reminder_info["due_at"],
                                    priority="medium",
                                )
                        except Exception:
                            pass
                        st.success("✅ Diary entry saved!")
                        st.rerun()
                    else:
                        st.warning("Write something first.")

            st.markdown('</div>', unsafe_allow_html=True)

    # ── BROWSE tab ────────────────────────────────────────────────────────────
    with tab_browse:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Date range filter
        fc1, fc2 = st.columns(2)
        with fc1:
            from_date = st.date_input("From", value=None, key="diary_from_date")
        with fc2:
            to_date = st.date_input("To", value=None, key="diary_to_date")

        date_from = datetime.combine(from_date, datetime.min.time()) if from_date else None
        date_to   = datetime.combine(to_date,   datetime.max.time()) if to_date   else None

        entries = diary_list(user_id=user_id, limit=50, date_from=date_from, date_to=date_to)

        if not entries:
            st.markdown("""
            <div class="empty-state">
                <div class="es-icon">📔</div>
                <div class="es-title">No diary entries yet</div>
                <div class="es-body">Start writing in the Write tab above.</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="section-label">📅 &nbsp;{len(entries)} entr{"y" if len(entries)==1 else "ies"}</div>',
                unsafe_allow_html=True
            )
            for e in entries:
                edate = datetime.fromisoformat(e["entry_date"]).strftime("%A, %B %d, %Y")
                mood_str = e.get("mood") or ""
                tags_str = e.get("tags") or ""
                content  = e.get("content", "")
                preview  = content[:200] + ("…" if len(content) > 200 else "")

                st.markdown(
                    f'<div class="memory-full-card">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">'
                    f'<span style="font-size:14px;font-weight:700;color:#0F172A">📅 {edate}</span>'
                    f'<span style="font-size:13px;color:#94A3B8">{mood_str}</span>'
                    f'</div>'
                    f'<div style="font-size:13px;color:#475569;line-height:1.6;margin-bottom:10px">{preview}</div>'
                    + (f'<div style="font-size:11px;color:#94A3B8">🏷️ {tags_str}</div>' if tags_str else "")
                    + '</div>',
                    unsafe_allow_html=True
                )

                btn1, btn2, btn3, _ = st.columns([1, 1, 1, 4])
                with btn1:
                    if st.button("✏️ Edit", key=f"diary_edit_{e['id']}"):
                        st.session_state.diary_editing_id = e["id"]
                        st.session_state.page = "Diary"
                        st.rerun()
                with btn2:
                    if st.button("🗑️ Delete", key=f"diary_del_{e['id']}"):
                        diary_delete(e["id"], user_id=user_id)
                        st.rerun()
                with btn3:
                    if st.button("📜 Full", key=f"diary_full_{e['id']}"):
                        with st.expander(f"Full entry — {edate}", expanded=True):
                            st.markdown(
                                f'<div style="white-space:pre-wrap;font-size:14px;color:#1E293B;'
                                f'line-height:1.7;padding:8px 0">{content}</div>',
                                unsafe_allow_html=True
                            )

    # ── SEARCH tab ────────────────────────────────────────────────────────────
    with tab_search:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="input-card">', unsafe_allow_html=True)

        search_q = st.text_input(
            "Search your diary",
            placeholder="e.g. What did I write about my project last month?",
            key="diary_search_q",
            label_visibility="collapsed",
        )

        sc1, sc2 = st.columns([1, 5])
        with sc1:
            do_search = st.button("🔍 Search", type="primary", use_container_width=True, key="diary_search_btn")
        with sc2:
            use_ai = st.checkbox("🤖 Ask AI to summarise results", key="diary_use_ai")

        st.markdown('</div>', unsafe_allow_html=True)

        if do_search and search_q.strip():
            with st.spinner("🔍 Searching diary…"):
                hits = diary_search(search_q.strip(), user_id=user_id, top_k=5)

            if not hits:
                st.info("No matching diary entries found.")
            else:
                st.markdown(
                    f'<div class="section-label">📚 &nbsp;{len(hits)} matching entr{"y" if len(hits)==1 else "ies"}</div>',
                    unsafe_allow_html=True
                )
                for e in hits:
                    edate = datetime.fromisoformat(e["entry_date"]).strftime("%B %d, %Y")
                    content = e.get("content", "")
                    preview = content[:300] + ("…" if len(content) > 300 else "")
                    score   = e.get("_score", 0)
                    st.markdown(
                        f'<div class="memory-full-card">'
                        f'<div style="display:flex;justify-content:space-between;margin-bottom:6px">'
                        f'<span style="font-size:13px;font-weight:700;color:#0F172A">📅 {edate}</span>'
                        f'<span style="font-size:11px;color:#94A3B8">relevance {score:.2f}</span>'
                        f'</div>'
                        f'<div style="font-size:13px;color:#475569;line-height:1.6">{preview}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                if use_ai and check_ollama_cached():
                    with st.spinner("🤖 Generating AI summary…"):
                        combined = "\n\n".join(
                            f"[{datetime.fromisoformat(e['entry_date']).strftime('%b %d')}] {e.get('content','')[:400]}"
                            for e in hits
                        )
                        prompt = (
                            f"Based on these diary entries, answer: {search_q}\n\n"
                            f"ENTRIES:\n{combined}\n\n"
                            "Answer concisely in 3-5 sentences using only the entries above. "
                            "If the information is not present, say so."
                        )
                        ai_answer = ollama_service.generate(prompt, temperature=0.3)
                    st.markdown(
                        f'<div style="background:#F0FDF4;border-left:4px solid #10B981;border-radius:10px;'
                        f'padding:16px 20px;margin-top:12px">'
                        f'<div style="font-size:12px;font-weight:700;color:#065F46;margin-bottom:8px">🤖 AI SUMMARY</div>'
                        f'<div style="font-size:14px;color:#1E293B;line-height:1.6">{ai_answer}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )


# ── analytics ────────────────────────────────────────────────────────────────


def analytics_page():
    print("[Page] Rendering → Analytics")
    import plotly.graph_objects as go

    st.markdown("""
    <div class="page-header">
        <h1>📊 Memory Analytics</h1>
        <p>Insights into your memory patterns, tag usage, and importance distribution.</p>
    </div>""", unsafe_allow_html=True)

    stats   = get_stats_cached()
    all_mem = get_all_memories_cached()

    total      = stats["total_memories"]
    chars      = stats["total_characters"]
    avg_len    = stats["average_length"]
    n_tags     = len(stats["tags"])
    pending    = len(pending_reminders())
    high_count = sum(1 for m in all_mem
                     if float(m.get("metadata", {}).get("importance", 0)) >= 0.8
                     or str(m.get("metadata", {}).get("priority", "")).lower() == "high")
    week_count = this_week_count(all_mem)

    c1, c2, c3, c4 = st.columns(4)
    for col, ico, val, lbl in [
        (c1, "📝", total,      "Total Memories"),
        (c2, "📅", week_count, "This Week"),
        (c3, "⏰", pending,    "Active Reminders"),
        (c4, "🕒", avg_len,    "Average Memory Age"),
    ]:
        with col:
            st.markdown(
                f'<div class="stat-card">'
                f'<div class="stat-icon">{ico}</div>'
                f'<div class="stat-value">{val}</div>'
                f'<div class="stat-label">{lbl}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    c4, c5, c6 = st.columns(3)
    for col, ico, val, lbl in [
        (c4, "🏷️", n_tags,   "Unique Tags"),
        (c5, "💬", chars,    "Total Characters"),
        (c6, "📏", avg_len,  "Avg Memory Length"),
    ]:
        with col:
            st.markdown(
                f'<div class="stat-card">'
                f'<div class="stat-icon">{ico}</div>'
                f'<div class="stat-value">{val}</div>'
                f'<div class="stat-label">{lbl}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    # ── Gap 3: Export / Import UI ─────────────────────────────────────────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    with st.expander("📦  Export / Import Memories", expanded=False):
        ex_col, im_col = st.columns(2, gap="large")

        with ex_col:
            st.markdown(
                '<div style="font-size:13px;font-weight:600;color:#1E293B;margin-bottom:8px">'
                '⬇️ Export all memories as JSON</div>',
                unsafe_allow_html=True
            )
            if st.button("Export JSON", use_container_width=True, key="export_btn"):
                try:
                    json_str = memory_exporter.export_json()
                    st.download_button(
                        label="💾 Download memories.json",
                        data=json_str,
                        file_name=f"memories_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        use_container_width=True,
                        key="download_json"
                    )
                    print("[Export] ✅ JSON export ready")
                except Exception as e:
                    st.error(f"Export failed: {e}")

        with im_col:
            st.markdown(
                '<div style="font-size:13px;font-weight:600;color:#1E293B;margin-bottom:8px">'
                '⬆️ Import memories from JSON</div>',
                unsafe_allow_html=True
            )
            uploaded = st.file_uploader(
                "Upload JSON", type=["json"],
                label_visibility="collapsed", key="import_uploader"
            )
            if uploaded:
                if st.button("Import", type="primary", use_container_width=True, key="import_btn"):
                    try:
                        json_str = uploaded.read().decode("utf-8")
                        imported, failed = memory_exporter.import_json(json_str)
                        bust_memory_cache()
                        print(f"[Import] ✅ imported={imported} failed={failed}")
                        if failed:
                            st.warning(f"Imported {imported} memories. {failed} failed.")
                        else:
                            st.success(f"✅ Successfully imported {imported} memories!")
                    except Exception as e:
                        st.error(f"Import failed: {e}")

    if not all_mem:
        st.markdown("""
        <div class="empty-state" style="margin-top:24px">
            <div class="es-icon">🧠</div>
            <div class="es-title">No memories yet</div>
            <div class="es-body">Add memories to see analytics and insights here.<br>
            The more you capture, the richer your insights.</div>
        </div>""", unsafe_allow_html=True)
        return

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── Charts row ────────────────────────────────────────────────────────────
    col_a, col_b = st.columns(2, gap="large")

    # ── Importance distribution — horizontal bar chart ────────────────────────
    with col_a:
        st.markdown(
            '<div class="section-label">⚡ &nbsp;Importance Distribution</div>',
            unsafe_allow_html=True
        )
        scores = [float(m.get("metadata", {}).get("importance", 0.5)) for m in all_mem]
        bins   = [0, 0.2, 0.4, 0.6, 0.8, 1.01]
        labels = ["Very Low", "Low", "Medium", "High", "Critical"]
        counts = [0] * 5
        for s in scores:
            for j in range(len(bins) - 1):
                if bins[j] <= s < bins[j + 1]:
                    counts[j] += 1
                    break
        bar_colors = ["#6EE7B7", "#93C5FD", "#FCD34D", "#F97316", "#EF4444"]

        fig_imp = go.Figure(go.Bar(
            x=counts,
            y=labels,
            orientation="h",
            marker=dict(
                color=bar_colors,
                line=dict(width=0),
            ),
            text=[str(c) for c in counts],
            textposition="outside",
            textfont=dict(size=12, color="#1E293B", family="Inter, sans-serif"),
            hovertemplate="%{y}: %{x} memories<extra></extra>",
        ))
        fig_imp.update_layout(
            margin=dict(l=0, r=32, t=8, b=0),
            height=220,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(
                showgrid=True, gridcolor="#F1F5F9", gridwidth=1,
                zeroline=False, showticklabels=False,
            ),
            yaxis=dict(
                showgrid=False, tickfont=dict(size=12, color="#64748B", family="Inter, sans-serif"),
                autorange="reversed",
            ),
            font=dict(family="Inter, sans-serif"),
            showlegend=False,
        )
        st.plotly_chart(fig_imp, use_container_width=True, config={"displayModeBar": False})

    # ── Priority breakdown — donut chart ──────────────────────────────────────
    with col_b:
        st.markdown(
            '<div class="section-label">🎯 &nbsp;Priority Breakdown</div>',
            unsafe_allow_html=True
        )
        pri_counts = {"high": 0, "medium": 0, "low": 0}
        for m in all_mem:
            meta = m.get("metadata", {})
            pri  = str(meta.get("priority", "")).lower()
            imp  = float(meta.get("importance", 0.5))
            if pri == "high" or imp >= 0.8:
                pri_counts["high"] += 1
            elif pri == "low" or imp < 0.4:
                pri_counts["low"] += 1
            else:
                pri_counts["medium"] += 1

        donut_labels = ["High", "Medium", "Low"]
        donut_values = [pri_counts["high"], pri_counts["medium"], pri_counts["low"]]
        donut_colors = ["#EF4444", "#F59E0B", "#10B981"]

        fig_pri = go.Figure(go.Pie(
            labels=donut_labels,
            values=donut_values,
            hole=0.62,
            marker=dict(colors=donut_colors, line=dict(color="#FFFFFF", width=3)),
            textinfo="none",
            hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
            sort=False,
        ))
        total_pri = sum(donut_values) or 1
        fig_pri.add_annotation(
            text=f"<b>{total_pri}</b><br><span style='font-size:11px'>memories</span>",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="#0F172A", family="Inter, sans-serif"),
            align="center",
        )
        fig_pri.update_layout(
            margin=dict(l=0, r=0, t=8, b=0),
            height=220,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(
                orientation="v", x=1.02, y=0.5,
                font=dict(size=12, color="#64748B", family="Inter, sans-serif"),
                bgcolor="rgba(0,0,0,0)",
            ),
            font=dict(family="Inter, sans-serif"),
        )
        st.plotly_chart(fig_pri, use_container_width=True, config={"displayModeBar": False})

    # ── Tag cloud ─────────────────────────────────────────────────────────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Extra stats from get_statistics()
    avg_imp    = stats.get("avg_importance", 0.0)
    type_bdown = stats.get("type_breakdown", {})
    tone_bdown = stats.get("tone_breakdown", {})
    date_range = stats.get("creation_date_range") or {}
    oldest     = (date_range.get("oldest") or "")[:10]
    newest     = (date_range.get("newest") or "")[:10]
    date_span  = f"{oldest} → {newest}" if oldest else "—"

    c7, c8, c9 = st.columns(3)
    for col, ico, val, lbl in [
        (c7, "⚡", f"{avg_imp:.2f}",                                  "Avg Importance"),
        (c8, "📂", max(type_bdown, key=type_bdown.get, default="—"), "Top Memory Type"),
        (c9, "📅", date_span,                                         "Date Range"),
    ]:
        with col:
            st.markdown(
                f'<div class="stat-card">'
                f'<div class="stat-icon">{ico}</div>'
                f'<div class="stat-value" style="font-size:18px">{val}</div>'
                f'<div class="stat-label">{lbl}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    # ── Type breakdown + Tone breakdown
    if type_bdown or tone_bdown:
        col_c, col_d = st.columns(2, gap="large")
        with col_c:
            st.markdown('<div class="section-label">📂 &nbsp;Memory Type Breakdown</div>', unsafe_allow_html=True)
            if type_bdown:
                type_colors = ["#6366F1", "#10B981", "#F59E0B", "#EF4444"]
                fig_type = go.Figure(go.Bar(
                    x=list(type_bdown.keys()), y=list(type_bdown.values()),
                    marker=dict(color=type_colors[:len(type_bdown)], line=dict(width=0)),
                    text=list(type_bdown.values()), textposition="outside",
                    hovertemplate="%{x}: %{y}<extra></extra>",
                ))
                fig_type.update_layout(
                    margin=dict(l=0, r=0, t=8, b=0), height=200,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor="#F1F5F9", showticklabels=False),
                    showlegend=False, font=dict(family="Inter, sans-serif"),
                )
                st.plotly_chart(fig_type, use_container_width=True, config={"displayModeBar": False})
        with col_d:
            st.markdown('<div class="section-label">😊 &nbsp;Emotional Tone Breakdown</div>', unsafe_allow_html=True)
            if tone_bdown:
                tone_icon  = {"positive": "😊", "negative": "😟", "neutral": "😐", "urgent": "🚨"}
                tone_color = {"positive": "#10B981", "negative": "#EF4444", "neutral": "#94A3B8", "urgent": "#F59E0B"}
                fig_tone = go.Figure(go.Pie(
                    labels=[f"{tone_icon.get(k,'📌')} {k.capitalize()}" for k in tone_bdown],
                    values=list(tone_bdown.values()),
                    hole=0.55,
                    marker=dict(colors=[tone_color.get(k, "#6366F1") for k in tone_bdown], line=dict(color="#FFFFFF", width=3)),
                    textinfo="none",
                    hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
                ))
                fig_tone.update_layout(
                    margin=dict(l=0, r=0, t=8, b=0), height=200,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="v", x=1.02, y=0.5, font=dict(size=11, color="#64748B")),
                    font=dict(family="Inter, sans-serif"),
                )
                st.plotly_chart(fig_tone, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="section-label">🏥 &nbsp;Memory Health</div>', unsafe_allow_html=True)
    try:
        from db.database import get_session
        from core.models import Memory as _Mem
        from core.decay_engine import compute_priority_score
        _session = get_session()
        try:
            _rows = _session.query(_Mem).all()
        finally:
            _session.close()

        if _rows:
            scored = sorted(
                [(r, compute_priority_score(r)) for r in _rows],
                key=lambda x: x[1], reverse=True
            )
            top10  = scored[:10]
            fading = [x for x in scored if x[1] < 0.15][-5:]

            import plotly.graph_objects as _go
            labels = [r.summary[:30] if r.summary else r.id[:12] for r, _ in top10]
            values = [round(s, 3) for _, s in top10]
            bar_colors = ["#6366F1" if v >= 0.5 else ("#F59E0B" if v >= 0.25 else "#CBD5E1") for v in values]

            fig_health = _go.Figure(_go.Bar(
                x=values, y=labels, orientation="h",
                marker=dict(color=bar_colors, line=dict(width=0)),
                text=[f"{v:.2f}" for v in values], textposition="outside",
                hovertemplate="%{y}: %{x:.3f}<extra></extra>",
            ))
            fig_health.update_layout(
                margin=dict(l=0, r=40, t=8, b=0), height=280,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(range=[0, 1.1], showgrid=True, gridcolor="#F1F5F9", showticklabels=False),
                yaxis=dict(showgrid=False, autorange="reversed",
                           tickfont=dict(size=11, color="#64748B")),
                showlegend=False, font=dict(family="Inter, sans-serif"),
            )
            st.plotly_chart(fig_health, use_container_width=True, config={"displayModeBar": False})

            if fading:
                with st.expander(f"🌫️ Fading memories (score < 0.15) — {len(fading)} found", expanded=False):
                    for r, s in fading:
                        label = r.summary[:80] if r.summary else r.id
                        st.markdown(
                            f'<div style="opacity:0.45;font-size:12px;color:#64748B;padding:4px 0;'
                            f'border-bottom:1px solid #F1F5F9">{label} '
                            f'<span style="color:#CBD5E1">score={s:.3f}</span></div>',
                            unsafe_allow_html=True
                        )
        else:
            st.info("No SQLite memories yet — add some via the ingestion pipeline.")
    except Exception as _e:
        st.caption(f"Memory health unavailable: {_e}")

    st.markdown('<div class="section-label">🏷️ &nbsp;Tag Frequency</div>', unsafe_allow_html=True)

    if stats["tags"]:
        sorted_tags = sorted(stats["tags"].items(), key=lambda x: x[1], reverse=True)[:20]
        max_count   = sorted_tags[0][1] if sorted_tags else 1
        tag_palette = [
            "#6366F1", "#8B5CF6", "#EC4899", "#3B82F6", "#10B981",
            "#F59E0B", "#EF4444", "#14B8A6", "#F97316", "#06B6D4",
            "#84CC16", "#A855F7", "#F43F5E", "#0EA5E9", "#22C55E",
            "#EAB308", "#8B5CF6", "#6366F1", "#EC4899", "#3B82F6",
        ]

        pills_html = '<div style="display:flex;flex-wrap:wrap;gap:8px;padding:4px 0">'
        for idx, (tag, cnt) in enumerate(sorted_tags):
            # Scale font 12px–18px and padding by relative frequency
            ratio    = cnt / max_count
            fs       = int(11 + ratio * 7)
            px       = int(8 + ratio * 6)
            py       = int(4 + ratio * 3)
            clr      = tag_palette[idx % len(tag_palette)]
            # lighten background: hex color at ~12% opacity via rgba
            r_int    = int(clr[1:3], 16)
            g_int    = int(clr[3:5], 16)
            b_int    = int(clr[5:7], 16)
            bg       = f"rgba({r_int},{g_int},{b_int},0.10)"
            border   = f"rgba({r_int},{g_int},{b_int},0.30)"
            pills_html += (
                f'<span title="{cnt} memor{"y" if cnt == 1 else "ies"}" '
                f'style="display:inline-block;background:{bg};color:{clr};'
                f'border:1px solid {border};border-radius:20px;'
                f'padding:{py}px {px}px;font-size:{fs}px;font-weight:600;'
                f'letter-spacing:0.1px;cursor:default">#{tag}'
                f'<span style="font-size:10px;opacity:0.7;margin-left:4px">{cnt}</span>'
                f'</span>'
            )
        pills_html += '</div>'

        st.markdown(
            '<div class="card" style="padding:20px 24px">' + pills_html + '</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="empty-state">'
            '<div class="es-icon">🏷️</div>'
            '<div class="es-title">No tags yet</div>'
            '<div class="es-body">Use <b>#tags</b> in your memories for better organisation.<br>'
            'Tags will appear here sized by how often you use them.</div>'
            '</div>',
            unsafe_allow_html=True
        )



# ── settings ──────────────────────────────────────────────────────────────────

def settings_page():
    print("[Page] Rendering → Settings")
    st.markdown("""
    <div class="page-header">
        <h1>⚙️ Settings</h1>
        <p>Configure your Second Brain — model, security, and data management.</p>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.current_user:
        auth_panel()
        return

    user = get_user_by_id(st.session_state.current_user.get("id")) or st.session_state.current_user
    st.markdown('<div class="settings-card">', unsafe_allow_html=True)
    st.markdown('<div class="settings-card-title">👤 User Profile</div>', unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:15px;font-weight:700;color:#111827'>🧑 {user.get('full_name') or user.get('username')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:13px;color:#64748B;margin-top:6px'>Username: {user.get('username')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:13px;color:#64748B'>Email: {user.get('email')}</div>", unsafe_allow_html=True)
    if st.button("Sign out", key="sign_out_btn"):
        st.session_state.current_user = None
        st.session_state.auth_message = "Signed out successfully"
        st.session_state.auth_error = ""
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Ollama model selector ─────────────────────────────────────────────────
    st.markdown('<div class="section-label">🤖 &nbsp;Ollama Model</div>', unsafe_allow_html=True)
    st.markdown('<div class="settings-card">', unsafe_allow_html=True)
    st.markdown('<div class="settings-card-title">🤖 Ollama Model</div>', unsafe_allow_html=True)
    with st.container():
        available_models = ollama_service.list_models()
        current_model    = config.OLLAMA_MODEL
        if available_models:
            st.selectbox(
                "Active model", available_models,
                index=available_models.index(current_model) if current_model in available_models else 0,
                key="settings_model"
            )
            st.info(f"Currently configured model: **{current_model}**. Restart the app after changing `.env` to apply a new model.")
        else:
            st.warning("No models found. Make sure Ollama is running and has at least one model pulled.")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Security ──────────────────────────────────────────────────────────────
    st.markdown('<div class="section-label">🔐 &nbsp;Security</div>', unsafe_allow_html=True)
    st.markdown('<div class="settings-card">', unsafe_allow_html=True)
    st.markdown('<div class="settings-card-title">🔐 Security</div>', unsafe_allow_html=True)
    sec_c1, sec_c2 = st.columns(2, gap="large")
    with sec_c1:
        st.markdown('<div style="font-size:13px;font-weight:600;color:#1E293B;margin-bottom:8px">Generate New Encryption Key</div>', unsafe_allow_html=True)
        if st.button("🔑 Generate Key", use_container_width=True, key="gen_key_btn"):
            new_key = security_manager.generate_encryption_key()
            st.code(new_key, language=None)
            st.caption("Copy this key and set it as ENCRYPTION_KEY in your .env file, then restart.")
    with sec_c2:
        st.markdown('<div style="font-size:13px;font-weight:600;color:#1E293B;margin-bottom:8px">Current Config</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div style="background:#F8FAFF;border-radius:10px;padding:14px 16px;border:1px solid #E0E7FF;font-size:13px;color:#475569">'
            f'<b>Model:</b> {config.OLLAMA_MODEL}<br>'
            f'<b>Embedding:</b> {config.OLLAMA_EMBEDDING_MODEL}<br>'
            f'<b>Top-K:</b> {config.RETRIEVAL_TOP_K}<br>'
            f'<b>Similarity threshold:</b> {config.SIMILARITY_THRESHOLD}<br>'
            f'<b>Decay enabled:</b> {config.MEMORY_DECAY_ENABLED}<br>'
            f'<b>Decay factor:</b> {config.DECAY_FACTOR}'
            f'</div>',
            unsafe_allow_html=True
        )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Danger zone ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-label">⚠️ &nbsp;Danger Zone</div>', unsafe_allow_html=True)
    st.markdown('<div class="danger-zone">', unsafe_allow_html=True)
    with st.expander("🗑️ Clear ALL memories — irreversible", expanded=False):
        st.warning("This will permanently delete every memory from the database. There is no undo.")
        confirm = st.text_input("Type DELETE to confirm", key="clear_confirm", placeholder="DELETE")
        if st.button("💣 Clear All Memories", type="primary", use_container_width=True, key="clear_all_btn"):
            if confirm.strip() == "DELETE":
                memory_store.clear_all_memories()
                bust_memory_cache()
                print("[Settings] ⚠️ All memories cleared")
                st.success("✅ All memories have been deleted.")
            else:
                st.error("Type DELETE exactly to confirm.")
    st.markdown('</div>', unsafe_allow_html=True)

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "─" * 50)
    print("[Second Brain] 🧠 App rerun triggered")
    print("─" * 50)
    init_state()

    # ── Gap 1: apply memory decay scores once per session ────
    if "decay_applied" not in st.session_state:
        try:
            memory_decay.update_all_importance_scores()
            print("[Decay] ✅ Importance scores refreshed")
        except Exception as e:
            print(f"[Decay] ⚠️ Could not update scores: {e}")
        st.session_state.decay_applied = True

    if not check_ollama_cached():
        st.markdown("""
        <div style="background:#FFF5F5;border-radius:16px;padding:24px 28px;border:1px solid #FECACA;
                    display:flex;align-items:center;gap:16px;margin:20px 0">
            <span style="font-size:32px">❌</span>
            <div>
                <div style="font-size:16px;font-weight:700;color:#991B1B;margin-bottom:4px">Ollama is not running</div>
                <div style="font-size:13px;color:#DC2626">Start it in a terminal: <code>ollama serve</code></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    sidebar()

    page = st.session_state.page
    if   page == "Dashboard":  dashboard_page()
    elif page == "Add Memory": add_memory_page()
    elif page == "Memories":   memories_page()
    elif page == "Diary":      diary_page()
    elif page == "Ask AI":     ask_ai_page()
    elif page == "Reminders":  reminders_page()
    elif page == "Analytics":  analytics_page()
    elif page == "Settings":   settings_page()


if __name__ == "__main__":
    main()

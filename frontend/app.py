"""
Career Guidance
"""

import streamlit as st
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.config import config
from backend.security import security_manager
from backend.memory_store import memory_store
from backend.rag_engine import rag_engine
from backend.ollama_service import ollama_service
from backend.memory_utils import memory_decay, memory_parser, memory_stats

st.set_page_config(
    page_title="Second Brain",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp { background-color: #F0F4FF; }

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #EEF2FF 0%, #F5F3FF 100%);
    border-right: 1px solid #DDD6FE;
}

.metric-card {
    background: #FFFFFF;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 2px 8px rgba(99,102,241,0.08);
    text-align: center;
    border: 1px solid #E0E7FF;
}
.metric-card h2 { color: #6366F1; font-size: 30px; font-weight: 700; margin: 0; }
.metric-card p  { color: #7C3AED; font-size: 13px; margin: 6px 0 0 0; font-weight: 500; }

.tag-pill {
    display: inline-block;
    background: #EDE9FE;
    color: #7C3AED;
    border-radius: 20px;
    padding: 3px 11px;
    font-size: 12px;
    font-weight: 500;
    margin: 3px 2px;
}

.memory-tag-card {
    background: #FFFFFF;
    border-radius: 14px;
    padding: 13px 18px;
    margin: 7px 0;
    box-shadow: 0 1px 4px rgba(99,102,241,0.07);
    border: 1px solid #E0E7FF;
}

.memory-full-card {
    background: #FFFFFF;
    border-radius: 16px;
    padding: 18px 22px;
    margin: 10px 0;
    box-shadow: 0 2px 8px rgba(99,102,241,0.07);
    border: 1px solid #E0E7FF;
}

.reminder-card {
    background: #FAFAFA;
    border-radius: 14px;
    padding: 13px 18px;
    margin: 7px 0;
    border-left: 4px solid #A78BFA;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
.reminder-card.high   { border-left-color: #F87171; background: #FFF5F5; }
.reminder-card.medium { border-left-color: #FBBF24; background: #FFFBEB; }
.reminder-card.low    { border-left-color: #6EE7B7; background: #F0FDF4; }

.chat-user {
    background: linear-gradient(135deg, #6366F1, #8B5CF6);
    color: white;
    border-radius: 18px 18px 4px 18px;
    padding: 12px 16px;
    margin: 8px 0 8px auto;
    max-width: 72%;
    font-size: 15px;
    display: table;
    margin-left: auto;
}
.chat-ai {
    background: #F5F3FF;
    color: #1E1B4B;
    border-radius: 18px 18px 18px 4px;
    padding: 12px 16px;
    margin: 8px 0;
    max-width: 72%;
    font-size: 15px;
    border: 1px solid #DDD6FE;
}

.lock-box {
    background: #FFFFFF;
    border-radius: 20px;
    padding: 44px 40px;
    max-width: 400px;
    margin: 50px auto;
    box-shadow: 0 6px 24px rgba(99,102,241,0.13);
    border: 1px solid #DDD6FE;
    text-align: center;
}

div[data-testid="stVerticalBlock"] > div > div > div > button {
    border-radius: 12px !important;
    font-weight: 500 !important;
    transition: all 0.15s ease !important;
}

.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    border-radius: 12px !important;
    border: 1.5px solid #DDD6FE !important;
    background: #FAFAFE !important;
    font-family: 'Inter', sans-serif !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #6366F1 !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.12) !important;
}

h1 { color: #1E1B4B !important; font-size: 26px !important; font-weight: 700 !important; }
h2 { color: #1E1B4B !important; font-size: 20px !important; font-weight: 600 !important; }
h3 { color: #3730A3 !important; font-size: 16px !important; font-weight: 600 !important; }

.stAlert { border-radius: 12px !important; }
.stSpinner { color: #6366F1 !important; }
</style>
""", unsafe_allow_html=True)


# ── cached backend calls ──────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def get_all_memories_cached():
    return memory_store.get_all_memories()

@st.cache_data(ttl=30)
def get_stats_cached():
    return memory_stats.get_statistics()

@st.cache_data(ttl=60)
def check_ollama_cached():
    return ollama_service.check_connection()

def bust_memory_cache():
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
    return [r for r in st.session_state.reminders if not r.get("done")]

def init_state():
    defaults = {
        "page": "Dashboard",
        "section_auth": None,
        "section_unlocked": False,
        "conversation": [],
        "reminders": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def go(page: str):
    if st.session_state.page != page:
        st.session_state.section_unlocked = False
        st.session_state.section_auth = None
    st.session_state.page = page


# ── security gate ─────────────────────────────────────────────────────────────

def security_gate(section: str) -> bool:
    if st.session_state.section_unlocked and st.session_state.section_auth == section:
        return True

    st.markdown(f"""
    <div class="lock-box">
        <div style="font-size:52px;margin-bottom:8px">🔒</div>
        <h2 style="color:#1E1B4B;margin:0 0 6px">Protected</h2>
        <p style="color:#6B7280;font-size:14px;margin:0">Enter your secret code to access <b>{section}</b></p>
    </div>
    """, unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        code = st.text_input("Secret Code", type="password", placeholder="Secret code", key=f"gate_{section}", label_visibility="collapsed")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔓 Unlock", type="primary", use_container_width=True, key=f"unlock_{section}"):
                if security_manager.verify_secret_code(code):
                    st.session_state.section_auth = section
                    st.session_state.section_unlocked = True
                    st.rerun()
                else:
                    st.error("Wrong code")
        with c2:
            if st.button("✕ Cancel", use_container_width=True, key=f"cancel_{section}"):
                go("Dashboard")
                st.rerun()
    return False


# ── sidebar ───────────────────────────────────────────────────────────────────

def sidebar():
    with st.sidebar:
        st.markdown("""
        <div style="padding:8px 0 16px">
            <span style="font-size:22px;font-weight:700;color:#1E1B4B">🧠 Second Brain</span><br>
            <span style="font-size:12px;color:#7C3AED">Your private memory space</span>
        </div>
        """, unsafe_allow_html=True)

        nav_items = [
            ("Dashboard",  "🏠", "Dashboard"),
            ("Add Memory", "➕", "Add Memory"),
            ("Memories",   "🗃️", "Memories"),
            ("Ask AI",     "💬", "Ask AI"),
            ("Reminders",  "⏰", "Reminders"),
            ("Analytics",  "📊", "Analytics"),
        ]

        for key, icon, label in nav_items:
            is_active = st.session_state.page == key
            btn_label = f"{icon}  {label}"
            if is_active:
                st.markdown(f"""
                <div style="background:#EDE9FE;border-radius:10px;padding:9px 14px;margin:2px 0;
                            color:#6366F1;font-weight:600;font-size:14px">{btn_label}</div>
                """, unsafe_allow_html=True)
            else:
                if st.button(btn_label, key=f"nav_{key}", use_container_width=True):
                    go(key)
                    st.rerun()

        st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)

        pending = len(pending_reminders())
        if pending:
            st.markdown(f"""
            <div style="background:#FEF3C7;border-radius:10px;padding:9px 14px;text-align:center;
                        color:#D97706;font-size:13px;font-weight:600">
                ⏰ {pending} pending reminder{'s' if pending > 1 else ''}
            </div>""", unsafe_allow_html=True)

        st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
        connected = check_ollama_cached()
        dot = "🟢" if connected else "🔴"
        status = "Ollama connected" if connected else "Ollama offline"
        st.markdown(f"<span style='font-size:12px;color:#6B7280'>{dot} {status}</span>", unsafe_allow_html=True)


# ── dashboard ─────────────────────────────────────────────────────────────────

def dashboard_page():
    hour = datetime.now().hour
    greeting = "Good Morning" if hour < 12 else ("Good Afternoon" if hour < 17 else "Good Evening")
    icon = "☀️" if hour < 12 else ("🌤️" if hour < 17 else "🌙")

    st.markdown(f"# {greeting} {icon}")
    st.markdown("<p style='color:#6B7280;margin-top:-10px;font-size:15px'>Here's your memory overview</p>", unsafe_allow_html=True)

    all_mem = get_all_memories_cached()
    stats   = get_stats_cached()
    pending = len(pending_reminders())
    week    = this_week_count(all_mem)

    c1, c2, c3, c4 = st.columns(4)
    for col, val, label in [
        (c1, stats["total_memories"], "Total Memories"),
        (c2, week,                    "This Week"),
        (c3, len(stats["tags"]),      "Unique Tags"),
        (c4, pending,                 "Pending Reminders"),
    ]:
        with col:
            st.markdown(f'<div class="metric-card"><h2>{val}</h2><p>{label}</p></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns([2, 1])

    with col_l:
        st.markdown("### 🏷️ Recent Memory Tags")
        recent = sorted(all_mem, key=lambda m: m.get("metadata", {}).get("created_at", ""), reverse=True)[:8]
        if recent:
            for mem in recent:
                tags    = memory_parser.extract_tags(mem.get("content", ""))
                created = mem.get("metadata", {}).get("created_at", "")[:10]
                tag_html = "".join(f'<span class="tag-pill">#{t}</span>' for t in tags) if tags else '<span class="tag-pill">untagged</span>'
                st.markdown(f"""
                <div class="memory-tag-card">
                    {tag_html}
                    <span style="float:right;color:#9CA3AF;font-size:12px">{created}</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("No memories yet — add your first one!")

    with col_r:
        st.markdown("### ⏰ Upcoming Reminders")
        upcoming = [r for r in st.session_state.reminders if not r.get("done")][:5]
        if upcoming:
            for r in upcoming:
                p = r.get("priority", "medium")
                st.markdown(f"""
                <div class="reminder-card {p}">
                    <b style="font-size:14px">{r['text']}</b><br>
                    <span style="color:#9CA3AF;font-size:12px">{r.get('created_at','')[:10]} · {p}</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown("<p style='color:#9CA3AF;font-size:14px'>No pending reminders 🎉</p>", unsafe_allow_html=True)


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
    if not security_gate("Add Memory"):
        return

    # mode toggle
    if "add_mode" not in st.session_state:
        st.session_state.add_mode = "auto"
    if "ai_suggestions" not in st.session_state:
        st.session_state.ai_suggestions = None
    if "analyzed_content" not in st.session_state:
        st.session_state.analyzed_content = ""

    st.markdown("# ➕ Add New Memory")
    st.markdown("<p style='color:#6B7280;margin-top:-10px;font-size:15px'>Capture your thoughts, ideas, and tasks. AI will enrich them automatically.</p>", unsafe_allow_html=True)

    # mode toggle
    col_t1, col_t2, col_t3, col_t4 = st.columns([1, 1, 1, 1])
    with col_t1:
        if st.button("🎤 Voice Mode" if st.session_state.add_mode != "voice" else "✅ Voice Mode",
                     use_container_width=True,
                     type="primary" if st.session_state.add_mode == "voice" else "secondary"):
            st.session_state.add_mode = "voice"
            st.session_state.ai_suggestions = None
            st.rerun()
    with col_t2:
        if st.button("🤖 Auto Mode" if st.session_state.add_mode != "auto" else "✅ Auto Mode",
                     use_container_width=True,
                     type="primary" if st.session_state.add_mode == "auto" else "secondary"):
            st.session_state.add_mode = "auto"
            st.session_state.ai_suggestions = None
            st.rerun()
    with col_t3:
        if st.button("✏️ Manual Mode" if st.session_state.add_mode != "manual" else "✅ Manual Mode",
                     use_container_width=True,
                     type="primary" if st.session_state.add_mode == "manual" else "secondary"):
            st.session_state.add_mode = "manual"
            st.session_state.ai_suggestions = None
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Memory Input card ──
    st.markdown("""
    <div style="background:#FFFFFF;border-radius:16px;padding:22px 24px;
                border:1px solid #E0E7FF;box-shadow:0 2px 8px rgba(99,102,241,0.07);margin-bottom:16px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
            <span style="font-size:20px">📝</span>
            <span style="font-size:15px;font-weight:600;color:#1E1B4B">Memory</span>
        </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.add_mode == "voice":
        st.markdown("🎤 Voice input mode (experimental)")
        audio = st.audio_input("Record your memory")
        if audio:
            # Placeholder for speech-to-text
            st.info("Speech-to-text processing would go here. For now, please use text input.")
            memory_content = st.text_area("Transcribed text", height=100, key="voice_transcript")
        else:
            memory_content = ""
    else:
        memory_content = st.text_area(
            "Memory content", height=150, label_visibility="collapsed",
            placeholder="e.g. I have a lab exam tomorrow, revise Unit 3…",
            key="add_mem_content"
        )
    
    st.markdown("</div>", unsafe_allow_html=True)

    # ── AI Analyse button (auto mode) ──
    if st.session_state.add_mode == "auto":
        if st.button("✨ Analyse with AI", use_container_width=True):
            if memory_content.strip():
                with st.spinner("AI is analysing your memory…"):
                    result = ai_analyze_memory(memory_content)
                    st.session_state.ai_suggestions = result
                    st.session_state.analyzed_content = memory_content
                    st.rerun()
            else:
                st.warning("Write a memory first.")

        # ── AI Suggestions panel ──
        if st.session_state.ai_suggestions:
            s = st.session_state.ai_suggestions

            st.markdown(
                '<div style="background:linear-gradient(135deg,#F5F3FF,#EEF2FF);border-radius:16px;'
                'padding:22px 24px;border:1px solid #DDD6FE;'
                'box-shadow:0 2px 12px rgba(99,102,241,0.1);margin-bottom:16px">',
                unsafe_allow_html=True
            )
            tags_val, rem_val, imp_val, pri_val, type_val = render_ai_suggestions(s)
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<p style='font-size:13px;color:#6B7280;margin:8px 0 4px'>Edit tags if needed:</p>", unsafe_allow_html=True)
            edited_tags = st.text_input("Edit tags", value=" ".join(tags_val), label_visibility="collapsed", key="ai_edit_tags")

            if st.button("💾 Save Memory", type="primary", use_container_width=True, key="save_ai"):
                final_tags = [t.strip().lstrip("#") for t in edited_tags.split() if t.strip()]
                metadata = {
                    "importance": imp_val,
                    "tags": final_tags,
                    "priority": pri_val,
                    "memory_type": type_val,
                    "created_at": datetime.now().isoformat(),
                    "access_count": 0,
                    "type": "auto"
                }
                memory_store.store_memory(st.session_state.analyzed_content, metadata)
                bust_memory_cache()
                if rem_val:
                    st.session_state.reminders.append({
                        "text": rem_val, "priority": pri_val,
                        "done": False, "created_at": datetime.now().isoformat()
                    })
                    st.success("✅ Memory saved with AI enhancements + reminder added!")
                else:
                    st.success("✅ Memory saved with AI enhancements!")
                st.session_state.ai_suggestions = None
                st.session_state.analyzed_content = ""
                bust_memory_cache()

    # ── Manual Mode ──
    else:
        st.markdown("""
        <div style="background:#FFFFFF;border-radius:16px;padding:22px 24px;
                    border:1px solid #E0E7FF;box-shadow:0 2px 8px rgba(99,102,241,0.07);margin-bottom:16px">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
                <span style="font-size:20px">🏷️</span>
                <span style="font-size:15px;font-weight:600;color:#1E1B4B">Tags</span>
                <span style="font-size:12px;color:#9CA3AF;margin-left:4px">space-separated</span>
            </div>
        """, unsafe_allow_html=True)
        manual_tags_input = st.text_input("Tags", placeholder="work health goals personal…",
                                          label_visibility="collapsed", key="add_tags_input")
        if manual_tags_input.strip():
            pills = "".join(f'<span class="tag-pill">#{t.lstrip("#")}</span>' for t in manual_tags_input.split() if t.strip())
            st.markdown(f"<div style='margin-top:4px'>{pills}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("""
        <div style="background:#FFFFFF;border-radius:16px;padding:22px 24px;
                    border:1px solid #E0E7FF;box-shadow:0 2px 8px rgba(99,102,241,0.07);margin-bottom:16px">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
                <span style="font-size:20px">⏰</span>
                <span style="font-size:15px;font-weight:600;color:#1E1B4B">Remind Me</span>
                <span style="font-size:12px;color:#9CA3AF;margin-left:4px">optional</span>
            </div>
        """, unsafe_allow_html=True)
        remind_text = st.text_input("Reminder", placeholder="e.g. Take water bottle for gym",
                                    label_visibility="collapsed", key="add_remind_text")
        remind_priority = st.selectbox("Priority", ["medium", "high", "low"], key="add_remind_pri")
        st.markdown("</div>", unsafe_allow_html=True)

        importance = st.slider("Importance", 0.0, 1.0, 0.5, 0.1, key="add_imp_manual")

        if st.button("💾 Save Memory", type="primary", use_container_width=True, key="save_manual"):
            if memory_content.strip():
                auto_tags   = memory_parser.extract_tags(memory_content)
                manual_tags = [t.strip().lstrip("#") for t in manual_tags_input.split() if t.strip()]
                all_tags    = list(set(auto_tags + manual_tags))
                calc_imp    = memory_parser.calculate_content_importance(memory_content)
                metadata = {
                    "importance": max(importance, calc_imp),
                    "tags": all_tags,
                    "created_at": datetime.now().isoformat(),
                    "access_count": 0,
                    "type": "manual"
                }
                memory_store.store_memory(memory_content, metadata)
                bust_memory_cache()

                if remind_text.strip():
                    st.session_state.reminders.append({
                        "text": remind_text.strip(), "priority": remind_priority,
                        "done": False, "created_at": datetime.now().isoformat()
                    })
                    st.success("✅ Memory saved and reminder added!")
                elif detect_reminder(memory_content):
                    st.session_state.reminders.append({
                        "text": extract_reminder_text(memory_content),
                        "priority": "medium", "done": False,
                        "created_at": datetime.now().isoformat()
                    })
                    st.success("✅ Memory saved and reminder auto-detected!")
                else:
                    st.success("✅ Memory saved!")

                if all_tags:
                    st.markdown("".join(f'<span class="tag-pill">#{t}</span>' for t in all_tags), unsafe_allow_html=True)
            else:
                st.error("Please write something in the Memory field first.")


# ── memories ──────────────────────────────────────────────────────────────────

def memories_page():
    if not security_gate("Memories"):
        return

    st.markdown("# 🗃️ Your Memories")

    search = st.text_input("Search", placeholder="🔍  Search by keyword or tag…", label_visibility="collapsed", key="mem_search")

    all_mem = get_all_memories_cached()
    all_mem = sorted(all_mem, key=lambda m: m.get("metadata", {}).get("created_at", ""), reverse=True)

    if search:
        all_mem = [m for m in all_mem if search.lower() in m.get("content", "").lower()]

    st.markdown(f"<p style='color:#7C3AED;font-size:13px;font-weight:500'>{len(all_mem)} memories</p>", unsafe_allow_html=True)

    for mem in all_mem:
        content  = mem.get("content", "")
        metadata = mem.get("metadata", {})
        tags     = memory_parser.extract_tags(content)
        imp      = metadata.get("importance", 0)
        created  = metadata.get("created_at", "")[:10]
        mem_id   = mem.get("id", "")
        tag_html = "".join(f'<span class="tag-pill">#{t}</span>' for t in tags) if tags else ""

        st.markdown(f"""
        <div class="memory-full-card">
            <p style="color:#1E1B4B;font-size:15px;margin:0 0 10px">{content}</p>
            <div style="margin-bottom:8px">{tag_html}</div>
            <span style="color:#9CA3AF;font-size:12px">📅 {created} &nbsp;·&nbsp; ⭐ {imp:.2f}</span>
        </div>""", unsafe_allow_html=True)

        if st.button("🗑️ Delete", key=f"del_{mem_id}"):
            memory_store.delete_memory(mem_id)
            bust_memory_cache()
            st.rerun()


# ── ask ai ────────────────────────────────────────────────────────────────────

def ask_ai_page():
    st.markdown("# 💬 Ask Your Memory AI")
    st.markdown("<p style='color:#6B7280;margin-top:-10px'>Ask questions about your stored memories or general facts. AI can use your memories when available and still answer simple questions like the current date.</p>", unsafe_allow_html=True)

    # chat history
    for item in st.session_state.conversation:
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#4F46E5,#7C3AED);color:white;'
            f'border-radius:18px 18px 4px 18px;padding:12px 18px;margin:8px 0 4px auto;'
            f'max-width:70%;display:table;margin-left:auto;font-size:14px">'
            f'{item["query"]}</div>',
            unsafe_allow_html=True
        )
        st.markdown(
            f'<div style="background:#F5F3FF;color:#1E1B4B;border:1px solid #DDD6FE;'
            f'border-radius:18px 18px 18px 4px;padding:14px 18px;margin:4px 0 12px;'
            f'max-width:80%;font-size:14px;line-height:1.6">'
            f'<span style="font-size:16px">🤖</span> {item["response"]}</div>',
            unsafe_allow_html=True
        )
        if item.get("sources"):
            with st.expander(f"📖 Based on {len(item['sources'])} memor{'y' if len(item['sources'])==1 else 'ies'}", expanded=False):
                for s in item["sources"]:
                    st.markdown(
                        f'<div style="background:#FFFFFF;border-radius:10px;padding:10px 14px;'
                        f'margin:4px 0;border-left:3px solid #6366F1;font-size:13px;color:#374151">'
                        f'{s["content"][:150]}{"..." if len(s["content"])>150 else ""}</div>',
                        unsafe_allow_html=True
                    )

    st.markdown("<br>", unsafe_allow_html=True)

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
        with st.spinner("🤔 Searching your memories…"):
            try:
                result = rag_engine.ask_memory(query)
                st.session_state.conversation.append({
                    "query": query,
                    "response": result.get("response", ""),
                    "sources": result.get("source_memories", [])
                })
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    elif ask:
        st.warning("Please type a question first.")


# ── reminders ─────────────────────────────────────────────────────────────────

def reminders_page():
    st.markdown("# ⏰ Reminders")

    # Proactive reminder scanning
    upcoming_deadlines = memory_parser.get_upcoming_deadlines(days_ahead=7)
    existing_reminder_texts = {r.get("text", "").lower() for r in st.session_state.reminders}
    
    for deadline in upcoming_deadlines:
        reminder_text = f"Upcoming deadline: {deadline['content'][:50]}... (Due: {deadline['deadline']['display']})"
        if reminder_text.lower() not in existing_reminder_texts:
            priority = "high" if deadline["deadline"]["days_until"] <= 2 else "medium"
            st.session_state.reminders.append({
                "text": reminder_text,
                "priority": priority,
                "done": False,
                "created_at": datetime.now().isoformat(),
                "proactive": True
            })

    with st.expander("➕ Add Reminder manually", expanded=False):
        r_text = st.text_input("Reminder text", placeholder="e.g. Take water bottle for gym", label_visibility="collapsed", key="rem_text")
        r_pri  = st.selectbox("Priority", ["high", "medium", "low"], key="rem_pri")
        if st.button("Add", type="primary", key="rem_add"):
            if r_text.strip():
                st.session_state.reminders.append({
                    "text": r_text.strip(), "priority": r_pri,
                    "done": False, "created_at": datetime.now().isoformat()
                })
                st.rerun()

    pending = [r for r in st.session_state.reminders if not r.get("done")]
    done    = [r for r in st.session_state.reminders if r.get("done")]

    st.markdown(f"### 🔔 Pending ({len(pending)})")
    if pending:
        for i, r in enumerate(st.session_state.reminders):
            if r.get("done"):
                continue
            p = r.get("priority", "medium")
            c1, c2 = st.columns([6, 1])
            with c1:
                st.markdown(f"""
                <div class="reminder-card {p}">
                    <b style="font-size:14px">{r['text']}</b><br>
                    <span style="color:#9CA3AF;font-size:12px">{r.get('created_at','')[:10]} · {p} priority</span>
                </div>""", unsafe_allow_html=True)
            with c2:
                if st.button("✅", key=f"done_{i}"):
                    st.session_state.reminders[i]["done"] = True
                    st.rerun()
    else:
        st.info("No pending reminders 🎉")

    if done:
        st.markdown(f"### ✅ Completed ({len(done)})")
        for r in done:
            st.markdown(f"<p style='color:#9CA3AF;text-decoration:line-through;font-size:14px'>✓ {r['text']}</p>", unsafe_allow_html=True)


# ── analytics ────────────────────────────────────────────────────────────────

def analytics_page():
    import pandas as pd

    st.markdown("""
    <div style="margin-bottom:6px">
        <h1 style="margin:0">📊 Memory Analytics</h1>
        <p style="color:#6B7280;font-size:14px;margin:2px 0 0">Insights into your memory patterns and usage</p>
    </div>""", unsafe_allow_html=True)

    stats   = get_stats_cached()
    all_mem = get_all_memories_cached()

    # ─ stat cards
    total   = stats["total_memories"]
    chars   = stats["total_characters"]
    avg_len = stats["average_length"]
    n_tags  = len(stats["tags"])

    high_count = sum(1 for m in all_mem
                     if float(m.get("metadata", {}).get("importance", 0)) >= 0.8
                     or str(m.get("metadata", {}).get("priority", "")).lower() == "high")
    week_count = this_week_count(all_mem)

    cards = [
        ("📝", str(total),      "Total Memories",   "#EEF2FF", "#4F46E5"),
        ("🔴", str(high_count), "High Priority",    "#FEF2F2", "#DC2626"),
        ("📅", str(week_count), "Added This Week",  "#F0FDF4", "#16A34A"),
        ("🏷️", str(n_tags),    "Unique Tags",      "#FFF7ED", "#D97706"),
        ("💬", str(chars),     "Total Characters", "#F5F3FF", "#7C3AED"),
        ("📏", str(avg_len),   "Avg Memory Length","#EFF6FF", "#2563EB"),
    ]
    cols = st.columns(3)
    for i, (icon, val, label, bg, fg) in enumerate(cards):
        with cols[i % 3]:
            st.markdown(
                f'<div style="background:{bg};border-radius:16px;padding:20px 18px;'
                f'border:1px solid {fg}22;margin-bottom:12px;text-align:center">'
                f'<div style="font-size:26px">{icon}</div>'
                f'<div style="font-size:28px;font-weight:700;color:{fg};margin:4px 0">{val}</div>'
                f'<div style="font-size:13px;color:{fg};font-weight:500;opacity:0.8">{label}</div></div>',
                unsafe_allow_html=True
            )

    if not all_mem:
        st.markdown(
            '<div style="background:#F5F3FF;border-radius:16px;padding:40px;text-align:center;'
            'border:1px solid #DDD6FE;margin-top:20px">'
            '<div style="font-size:48px">🧠</div>'
            '<h3 style="color:#4F46E5;margin:12px 0 6px">No memories yet</h3>'
            '<p style="color:#6B7280;font-size:14px">Add memories to see analytics and insights here.</p></div>',
            unsafe_allow_html=True
        )
        return

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ─ importance distribution
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown(
            '<div style="background:#FFFFFF;border-radius:16px;padding:20px 22px;'
            'border:1px solid #E0E7FF;box-shadow:0 2px 8px rgba(99,102,241,0.07);margin-bottom:14px">'
            '<div style="font-size:13px;font-weight:700;color:#4F46E5;letter-spacing:0.5px;margin-bottom:14px">'
            '⚡ IMPORTANCE DISTRIBUTION</div>',
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
        colors = ["#6EE7B7", "#93C5FD", "#FCD34D", "#F97316", "#EF4444"]
        for j, (lbl, cnt, clr) in enumerate(zip(labels, counts, colors)):
            pct = int((cnt / len(scores)) * 100) if scores else 0
            bar_w = max(pct, 2)
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">'
                f'<div style="width:70px;font-size:12px;color:#6B7280;font-weight:500">{lbl}</div>'
                f'<div style="flex:1;background:#F3F4F6;border-radius:6px;height:10px">'
                f'<div style="background:{clr};width:{bar_w}%;height:10px;border-radius:6px"></div></div>'
                f'<div style="width:28px;font-size:12px;font-weight:700;color:#1E1B4B;text-align:right">{cnt}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_b:
        st.markdown(
            '<div style="background:#FFFFFF;border-radius:16px;padding:20px 22px;'
            'border:1px solid #E0E7FF;box-shadow:0 2px 8px rgba(99,102,241,0.07);margin-bottom:14px">'
            '<div style="font-size:13px;font-weight:700;color:#4F46E5;letter-spacing:0.5px;margin-bottom:14px">'
            '🎯 PRIORITY BREAKDOWN</div>',
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
        total_pri = sum(pri_counts.values()) or 1
        for lbl, cnt, clr, bg in [
            ("High",   pri_counts["high"],   "#DC2626", "#FEE2E2"),
            ("Medium", pri_counts["medium"], "#D97706", "#FEF3C7"),
            ("Low",    pri_counts["low"],    "#16A34A", "#DCFCE7"),
        ]:
            pct = int((cnt / total_pri) * 100)
            st.markdown(
                f'<div style="display:flex;align-items:center;justify-content:space-between;'
                f'background:{bg};border-radius:12px;padding:12px 16px;margin-bottom:10px">'
                f'<span style="font-size:14px;font-weight:600;color:{clr}">{lbl} Priority</span>'
                f'<div style="text-align:right">'
                f'<span style="font-size:20px;font-weight:700;color:{clr}">{cnt}</span>'
                f'<span style="font-size:12px;color:{clr};margin-left:4px">({pct}%)</span>'
                f'</div></div>',
                unsafe_allow_html=True
            )
        st.markdown("</div>", unsafe_allow_html=True)

    # ─ tag frequency
    if stats["tags"]:
        st.markdown(
            '<div style="background:#FFFFFF;border-radius:16px;padding:20px 22px;'
            'border:1px solid #E0E7FF;box-shadow:0 2px 8px rgba(99,102,241,0.07)">'
            '<div style="font-size:13px;font-weight:700;color:#4F46E5;letter-spacing:0.5px;margin-bottom:14px">'
            '🏷️ TAG FREQUENCY</div>',
            unsafe_allow_html=True
        )
        sorted_tags = sorted(stats["tags"].items(), key=lambda x: x[1], reverse=True)[:10]
        max_count   = sorted_tags[0][1] if sorted_tags else 1
        tag_colors  = ["#6366F1", "#8B5CF6", "#EC4899", "#3B82F6", "#10B981",
                       "#F59E0B", "#EF4444", "#14B8A6", "#F97316", "#6EE7B7"]
        for idx, (tag, cnt) in enumerate(sorted_tags):
            pct = int((cnt / max_count) * 100)
            clr = tag_colors[idx % len(tag_colors)]
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">'
                f'<div style="width:90px;font-size:12px;font-weight:600;color:#374151">#{tag}</div>'
                f'<div style="flex:1;background:#F3F4F6;border-radius:6px;height:12px">'
                f'<div style="background:{clr};width:{pct}%;height:12px;border-radius:6px"></div></div>'
                f'<div style="width:24px;font-size:13px;font-weight:700;color:{clr};text-align:right">{cnt}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            '<div style="background:#F5F3FF;border-radius:14px;padding:20px;text-align:center;'
            'border:1px solid #DDD6FE">'
            '<span style="font-size:28px">🏷️</span>'
            '<p style="color:#7C3AED;font-size:14px;margin:8px 0 0;font-weight:500">'
            'No tags yet. Use #tags in your memories for better organisation.</p></div>',
            unsafe_allow_html=True
        )


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    init_state()

    if not check_ollama_cached():
        st.error("❌ Ollama is not running. Start it with: `ollama run tinyllama`")
        st.stop()

    sidebar()

    page = st.session_state.page
    if   page == "Dashboard":  dashboard_page()
    elif page == "Add Memory": add_memory_page()
    elif page == "Memories":   memories_page()
    elif page == "Ask AI":     ask_ai_page()
    elif page == "Reminders":  reminders_page()
    elif page == "Analytics":  analytics_page()


if __name__ == "__main__":
    main()

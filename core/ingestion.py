"""
NLP Ingestion Pipeline
======================
For each incoming entry:
  1. Clean & normalize text
  2. Extract context (1-sentence summary via LLM)
  3. Extract time references (dateparser + regex)
  4. Classify intent: fact | task | reminder-worthy | journal-reflection
  5. Detect emotional tone (positive / neutral / negative / urgent)
  6. If task/reminder-worthy + time found → create Reminder row
  7. Encrypt, chunk, embed, store in ChromaDB + SQLite
"""

import re
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional

import dateparser
from langchain.text_splitter import RecursiveCharacterTextSplitter

from db.database import get_session, init_db
from core.models import Memory, SourceType
from core.vector_store import vector_store
from core.reminder_engine import create_reminder

import sys, os
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
from backend.config import config
from backend.security import SecurityManager

logger = logging.getLogger(__name__)

_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

# ── LLM helper (lazy import to avoid circular deps) ──────────────────────────

def _llm_generate(prompt: str) -> str:
    from backend.ollama_service import ollama_service
    return ollama_service.generate(prompt, temperature=0.1)


# ── Text cleaning ─────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    return text


# ── Context extraction ────────────────────────────────────────────────────────

def extract_context(text: str) -> str:
    """Return a 1-sentence summary via LLM."""
    try:
        prompt = (
            f'Summarize this note in ONE sentence (max 20 words):\n"{text}"\nSummary:'
        )
        return _llm_generate(prompt).strip().split("\n")[0]
    except Exception:
        return text[:100]


# ── Time extraction ───────────────────────────────────────────────────────────

_RELATIVE = {
    "today": 0, "tonight": 0, "tomorrow": 1, "day after tomorrow": 2,
    "next week": 7, "this week": 7, "next month": 30, "in a week": 7,
}
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def extract_time_reference(text: str) -> Optional[datetime]:
    """Return a datetime if a time reference is found, else None."""
    lower = text.lower()

    # 1. Relative phrases
    for phrase, days in _RELATIVE.items():
        if phrase in lower:
            return datetime.now() + timedelta(days=days)

    # 2. Weekday names
    for i, day in enumerate(_WEEKDAYS):
        if day in lower:
            today_idx = datetime.now().weekday()
            days_ahead = (i - today_idx) % 7 or 7
            return datetime.now() + timedelta(days=days_ahead)

    # 3. dateparser fallback
    try:
        dt = dateparser.parse(text, settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": False})
        if dt and dt > datetime.now():
            return dt
    except Exception:
        pass

    return None


# ── Intent classification ─────────────────────────────────────────────────────

_INTENT_PROMPT = """Classify this note into exactly one category:
  fact | task | reminder-worthy | journal-reflection

Note: "{text}"

Rules:
- task: action to be done (buy, submit, call, finish, complete…)
- reminder-worthy: time-sensitive but not a direct task
- fact: information, knowledge, something learned
- journal-reflection: personal feeling, diary-style

Reply with ONLY the category word."""


def classify_intent(text: str) -> str:
    valid = {"fact", "task", "reminder-worthy", "journal-reflection"}
    try:
        raw = _llm_generate(_INTENT_PROMPT.format(text=text)).strip().lower()
        for v in valid:
            if v in raw:
                return v
    except Exception:
        pass
    # rule-based fallback
    lower = text.lower()
    if any(w in lower for w in ["buy", "submit", "call", "finish", "complete", "do", "send", "pay", "book"]):
        return "task"
    if any(w in lower for w in ["tomorrow", "next week", "deadline", "due", "remind"]):
        return "reminder-worthy"
    if any(w in lower for w in ["feel", "felt", "today was", "i am", "i was", "diary"]):
        return "journal-reflection"
    return "fact"


# ── Tone detection ────────────────────────────────────────────────────────────

def detect_tone(text: str) -> str:
    lower = text.lower()
    pos = sum(1 for w in ["happy", "great", "excited", "love", "proud", "success", "achieved"] if w in lower)
    neg = sum(1 for w in ["sad", "angry", "stressed", "worried", "failed", "anxious", "upset"] if w in lower)
    urg = sum(1 for w in ["urgent", "asap", "critical", "emergency", "must", "deadline"] if w in lower)
    if urg:
        return "urgent"
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


# ── Main ingestion entry point ────────────────────────────────────────────────

def ingest(
    raw_text: str,
    source_type: str = "note",
    importance: float = 0.5,
    passphrase: str = None,
) -> str:
    """
    Full ingestion pipeline. Returns the new Memory.id.
    passphrase: if provided, uses a fresh SecurityManager keyed to it;
                otherwise falls back to the global security_manager.
    """
    init_db()

    text = _clean(raw_text)
    if not text:
        raise ValueError("Empty content after cleaning.")

    # NLP extraction
    summary = extract_context(text)
    intent  = classify_intent(text)
    tone    = detect_tone(text)
    due_at  = extract_time_reference(text)

    # Encryption
    if passphrase:
        sec = SecurityManager(passphrase)
    else:
        from backend.security import security_manager as sec  # type: ignore

    encrypted = sec.encrypt(text)

    # Persist to SQLite
    session = get_session()
    try:
        src = SourceType(source_type) if source_type in SourceType.__members__ else SourceType.note
        mem = Memory(
            id                = str(uuid.uuid4()),
            content_encrypted = encrypted,
            importance        = importance,
            priority_score    = importance,
            source_type       = src,
            intent            = intent,
            tone              = tone,
            summary           = summary,
        )
        session.add(mem)
        session.commit()
        session.refresh(mem)
        memory_id = mem.id
    finally:
        session.close()

    # Chunk + embed + store in ChromaDB
    chunks = _splitter.split_text(text)
    vector_store.add_chunks(memory_id, chunks)

    # Auto-create reminder if warranted
    if intent in ("task", "reminder-worthy") and due_at:
        create_reminder(
            description=summary or text[:120],
            due_at=due_at,
            memory_id=memory_id,
        )
        logger.info("Auto-created reminder for memory %s due=%s", memory_id[:8], due_at)

    logger.info("Ingested memory %s intent=%s tone=%s", memory_id[:8], intent, tone)
    return memory_id

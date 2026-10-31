"""
reminder_utils.py — infer reminder due-date and text from free-form content.
Used by the Add Memory page to auto-create SQLite reminders.
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Any

_RELATIVE: Dict[str, int] = {
    "today": 0, "tonight": 0, "tomorrow": 1,
    "day after tomorrow": 2, "next week": 7,
    "next month": 30, "this week": 5,
    "in 2 days": 2, "in 3 days": 3, "in a week": 7,
}

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

_TASK_WORDS = [
    "submit", "send", "call", "email", "meet", "attend", "buy", "pay",
    "finish", "complete", "review", "prepare", "remind", "don't forget",
    "remember to", "appointment", "deadline", "due", "exam", "test",
    "interview", "presentation", "report",
]


def _extract_due(text: str) -> datetime:
    """Return a best-guess due datetime from text, defaulting to +1 day."""
    lower = text.lower()

    for phrase, days in _RELATIVE.items():
        if phrase in lower:
            return datetime.now() + timedelta(days=days)

    for i, day in enumerate(_WEEKDAYS):
        if day in lower:
            today_idx = datetime.now().weekday()
            days_ahead = (i - today_idx) % 7 or 7
            return datetime.now() + timedelta(days=days_ahead)

    # ISO date pattern
    m = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', text)
    if m:
        try:
            return datetime.fromisoformat(m.group(1))
        except ValueError:
            pass

    return datetime.now() + timedelta(days=1)


def infer_reminder_from_content(content: str) -> Dict[str, Any]:
    """
    Returns:
        {
            "should_create": bool,
            "text": str,          # short reminder description
            "due_at": datetime,
        }
    """
    lower = content.lower()
    has_task = any(w in lower for w in _TASK_WORDS)
    has_time = any(p in lower for p in list(_RELATIVE.keys()) + _WEEKDAYS) or \
               bool(re.search(r'\b\d{4}-\d{2}-\d{2}\b', content))

    if not (has_task or has_time):
        return {"should_create": False, "text": "", "due_at": datetime.now() + timedelta(days=1)}

    # Build a short description: first sentence / first 80 chars
    first_sentence = re.split(r'[.!?\n]', content.strip())[0].strip()
    description = first_sentence[:100] if first_sentence else content[:100]

    due_at = _extract_due(content)

    return {
        "should_create": True,
        "text": description,
        "due_at": due_at,
    }

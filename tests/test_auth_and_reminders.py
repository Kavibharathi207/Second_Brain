"""
tests/test_auth_and_reminders.py
=================================
Tests for user authentication (backend/user_manager.py) and reminder
inference (backend/reminder_utils.py).

Fixes applied in Phase 1
------------------------
- Removed references to nonexistent DATA_PATH and _write_users attributes.
- user_manager stores users in a JSON file at _USERS_FILE; tests redirect
  that path via monkeypatching the module-level variable directly.
- Corrected reminder text assertion: infer_reminder_from_content returns the
  full first sentence of the input, not a substring of it.
"""

import os
import json
import uuid
from datetime import datetime, timedelta

import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import backend.user_manager as user_manager
from backend.reminder_utils import infer_reminder_from_content


# ── helpers ───────────────────────────────────────────────────────────────────

def _redirect_users_file(monkeypatch, tmp_path):
    """Point user_manager at a fresh temp file for test isolation."""
    users_file = str(tmp_path / "users.json")
    monkeypatch.setattr(user_manager, "_USERS_FILE", users_file)
    # Ensure the data directory exists (user_manager._load creates it lazily)
    os.makedirs(os.path.dirname(users_file), exist_ok=True)


# ── Auth tests ────────────────────────────────────────────────────────────────

def test_register_user_returns_dict_without_password(tmp_path, monkeypatch):
    _redirect_users_file(monkeypatch, tmp_path)

    user = user_manager.register_user(
        username="alice",
        email="alice@example.com",
        password="secret123",
        full_name="Alice Smith",
    )

    assert user["username"] == "alice"
    assert user["email"] == "alice@example.com"
    assert user["full_name"] == "Alice Smith"
    assert "password_hash" not in user, "password_hash must not be returned"
    assert "id" in user
    print("✅ test_register_user_returns_dict_without_password")


def test_authenticate_user_correct_password(tmp_path, monkeypatch):
    _redirect_users_file(monkeypatch, tmp_path)

    user_manager.register_user(
        username="bob",
        email="bob@example.com",
        password="hunter2",
    )

    authenticated = user_manager.authenticate_user("bob", "hunter2")
    assert authenticated is not None
    assert authenticated["username"] == "bob"
    assert "password_hash" not in authenticated
    print("✅ test_authenticate_user_correct_password")


def test_authenticate_user_wrong_password(tmp_path, monkeypatch):
    _redirect_users_file(monkeypatch, tmp_path)

    user_manager.register_user(
        username="carol",
        email="carol@example.com",
        password="correct",
    )

    result = user_manager.authenticate_user("carol", "wrong")
    assert result is None
    print("✅ test_authenticate_user_wrong_password")


def test_authenticate_by_email(tmp_path, monkeypatch):
    _redirect_users_file(monkeypatch, tmp_path)

    user_manager.register_user(
        username="dave",
        email="dave@example.com",
        password="pass123",
    )

    result = user_manager.authenticate_user("dave@example.com", "pass123")
    assert result is not None
    assert result["username"] == "dave"
    print("✅ test_authenticate_by_email")


def test_register_duplicate_username_raises(tmp_path, monkeypatch):
    _redirect_users_file(monkeypatch, tmp_path)

    user_manager.register_user(username="eve", email="eve@example.com", password="p1")
    with pytest.raises(ValueError, match="already taken"):
        user_manager.register_user(username="eve", email="eve2@example.com", password="p2")
    print("✅ test_register_duplicate_username_raises")


def test_register_duplicate_email_raises(tmp_path, monkeypatch):
    _redirect_users_file(monkeypatch, tmp_path)

    user_manager.register_user(username="frank", email="shared@example.com", password="p1")
    with pytest.raises(ValueError, match="already registered"):
        user_manager.register_user(username="frank2", email="shared@example.com", password="p2")
    print("✅ test_register_duplicate_email_raises")


def test_get_user_by_id(tmp_path, monkeypatch):
    _redirect_users_file(monkeypatch, tmp_path)

    created = user_manager.register_user(
        username="grace", email="grace@example.com", password="pw"
    )
    fetched = user_manager.get_user_by_id(created["id"])
    assert fetched is not None
    assert fetched["username"] == "grace"
    assert "password_hash" not in fetched
    print("✅ test_get_user_by_id")


# ── Reminder inference tests ──────────────────────────────────────────────────

def test_infer_reminder_tomorrow_exam():
    """
    'Tomorrow I have PB1 for the exam' contains both a time reference
    ('tomorrow') and a task word ('exam'), so should_create must be True.

    The returned text is the full first sentence of the input (up to 100 chars),
    NOT a substring like 'PB1 for the exam'.
    """
    content = "Tomorrow I have PB1 for the exam"
    reminder = infer_reminder_from_content(content)

    assert reminder["should_create"] is True
    # text = first sentence stripped, max 100 chars
    assert reminder["text"] == content.strip()
    assert reminder["due_at"].date() == (datetime.now() + timedelta(days=1)).date()
    print("✅ test_infer_reminder_tomorrow_exam")


def test_infer_reminder_no_task_no_time():
    """Pure factual note with no task words or time references → no reminder."""
    reminder = infer_reminder_from_content("The sky is blue and clouds are white.")
    assert reminder["should_create"] is False
    print("✅ test_infer_reminder_no_task_no_time")


def test_infer_reminder_task_word_only():
    """A task word alone (no time reference) is still enough to create a reminder."""
    reminder = infer_reminder_from_content("Submit the quarterly report.")
    assert reminder["should_create"] is True
    # Default due_at is +1 day when no time reference is found
    assert reminder["due_at"].date() == (datetime.now() + timedelta(days=1)).date()
    print("✅ test_infer_reminder_task_word_only")


def test_infer_reminder_next_week():
    reminder = infer_reminder_from_content("Call the dentist next week.")
    assert reminder["should_create"] is True
    expected_date = (datetime.now() + timedelta(days=7)).date()
    assert reminder["due_at"].date() == expected_date
    print("✅ test_infer_reminder_next_week")


def test_infer_reminder_text_truncated_at_100():
    long_content = "Submit " + "x" * 200
    reminder = infer_reminder_from_content(long_content)
    assert reminder["should_create"] is True
    assert len(reminder["text"]) <= 100
    print("✅ test_infer_reminder_text_truncated_at_100")


# ── runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Allow running directly without pytest for quick smoke-testing
    import tempfile, types

    class _FakeMonkeypatch:
        def setattr(self, obj, name, val):
            setattr(obj, name, val)

    with tempfile.TemporaryDirectory() as tmp:
        mp = _FakeMonkeypatch()

        class _TmpPath:
            def __truediv__(self, name):
                return type("P", (), {"__str__": lambda s: os.path.join(tmp, name)})()

        tp = _TmpPath()

        test_register_user_returns_dict_without_password(tp, mp)
        test_authenticate_user_correct_password(tp, mp)
        test_authenticate_user_wrong_password(tp, mp)
        test_authenticate_by_email(tp, mp)
        test_register_duplicate_username_raises(tp, mp)
        test_register_duplicate_email_raises(tp, mp)
        test_get_user_by_id(tp, mp)

    test_infer_reminder_tomorrow_exam()
    test_infer_reminder_no_task_no_time()
    test_infer_reminder_task_word_only()
    test_infer_reminder_next_week()
    test_infer_reminder_text_truncated_at_100()

    print("\n🎉 All auth and reminder tests passed.")

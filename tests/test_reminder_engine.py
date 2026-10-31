"""
tests/test_reminder_engine.py
==============================
Covers:
  1. A task-worded sentence with a relative date creates a pending reminder.
  2. A reminder past due + grace flips to missed on sweep.
  3. mark_complete removes it from the active (pending) query immediately.
  4. The sweep job deletes rows past their archive window.
"""

import sys
import os
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import init_db, get_session
from core.models import Reminder, ReminderStatus
from core.reminder_engine import (
    create_reminder, mark_complete, get_pending,
    reminder_sweep, dismiss, snooze,
)


def setup():
    init_db()


# ── Test 1: create_reminder produces a pending row ────────────────────────────

def test_create_reminder_pending():
    setup()
    due = datetime.utcnow() + timedelta(days=7)
    r = create_reminder(description="Submit report next week", due_at=due)
    assert r.status == ReminderStatus.pending
    assert r.due_at == due
    assert r.id is not None
    # Verify it appears in get_pending
    session = get_session()
    try:
        pending_ids = [x.id for x in get_pending(session)]
        assert r.id in pending_ids
    finally:
        session.close()
    print(f"✅ test_create_reminder_pending  id={r.id[:8]}")
    return r.id


# ── Test 2: overdue reminder flips to missed ──────────────────────────────────

def test_overdue_flips_to_missed():
    setup()
    # due 48h ago, grace = 1h → already past grace
    due = datetime.utcnow() - timedelta(hours=48)
    r = create_reminder(description="Overdue task", due_at=due, grace_period_hours=1)

    reminder_sweep()

    session = get_session()
    try:
        refreshed = session.query(Reminder).filter(Reminder.id == r.id).first()
        assert refreshed is not None
        assert refreshed.status == ReminderStatus.missed, f"Expected missed, got {refreshed.status}"
    finally:
        session.close()
    print(f"✅ test_overdue_flips_to_missed  id={r.id[:8]}")
    return r.id


# ── Test 3: mark_complete removes from active list immediately ────────────────

def test_mark_complete_removes_from_active():
    setup()
    due = datetime.utcnow() + timedelta(days=1)
    r = create_reminder(description="Buy groceries tomorrow", due_at=due)

    # Confirm it's pending
    session = get_session()
    try:
        assert r.id in [x.id for x in get_pending(session)]
    finally:
        session.close()

    result = mark_complete(r.id)
    assert result is True

    # Must NOT appear in pending anymore
    session = get_session()
    try:
        pending_ids = [x.id for x in get_pending(session)]
        assert r.id not in pending_ids, "Completed reminder should not appear in pending"
        # But row still exists (not yet archived)
        row = session.query(Reminder).filter(Reminder.id == r.id).first()
        assert row is not None
        assert row.status == ReminderStatus.completed
    finally:
        session.close()
    print(f"✅ test_mark_complete_removes_from_active  id={r.id[:8]}")
    return r.id


# ── Test 4: sweep deletes rows past archive window ────────────────────────────

def test_sweep_deletes_past_archive_window():
    setup()
    # Completed 100h ago, archive_after = 1h → should be deleted
    due = datetime.utcnow() - timedelta(hours=200)
    r = create_reminder(description="Old completed task", due_at=due, archive_after_hours=1)

    # Manually set to completed with old completed_at
    session = get_session()
    try:
        row = session.query(Reminder).filter(Reminder.id == r.id).first()
        row.status       = ReminderStatus.completed
        row.completed_at = datetime.utcnow() - timedelta(hours=100)
        session.commit()
    finally:
        session.close()

    reminder_sweep()

    session = get_session()
    try:
        row = session.query(Reminder).filter(Reminder.id == r.id).first()
        assert row is None, "Row should have been hard-deleted by sweep"
    finally:
        session.close()
    print(f"✅ test_sweep_deletes_past_archive_window")


# ── runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_create_reminder_pending()
    test_overdue_flips_to_missed()
    test_mark_complete_removes_from_active()
    test_sweep_deletes_past_archive_window()
    print("\n🎉 All reminder engine tests passed.")

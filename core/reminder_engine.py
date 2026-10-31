"""
Reminder Engine — status lifecycle + APScheduler sweep
=======================================================

State machine
-------------
  pending ──(mark_complete)──────────────────► completed
  pending ──(dismiss)────────────────────────► missed  (skip grace)
  pending ──(now > due_at + grace_period)────► missed
  completed ──(now > completed_at + archive)─► [hard-deleted]
  missed    ──(now > due_at+grace+archive)───► [hard-deleted]

UI always queries WHERE status = 'pending'.
Completed/missed rows disappear from the active list the instant their
status changes; the sweep job handles physical deletion later.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from db.database import get_session, init_db
from core.models import Reminder, ReminderStatus, ReminderPriority

import sys, os
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
from backend.config import config

logger = logging.getLogger(__name__)


# ── Queries ───────────────────────────────────────────────────────────────────

def get_pending(session=None) -> List[Reminder]:
    """All reminders the user should see right now."""
    own = session is None
    s   = session or get_session()
    try:
        return (
            s.query(Reminder)
             .filter(Reminder.status == ReminderStatus.pending)
             .order_by(Reminder.due_at)
             .all()
        )
    finally:
        if own:
            s.close()


def get_recent_completed_missed(hours: int = 24) -> List[Reminder]:
    """Completed/missed reminders within the last *hours* — for the UI expander."""
    cutoff  = datetime.utcnow() - timedelta(hours=hours)
    session = get_session()
    try:
        return (
            session.query(Reminder)
            .filter(
                Reminder.status.in_([ReminderStatus.completed, ReminderStatus.missed]),
                Reminder.due_at >= cutoff,
            )
            .order_by(Reminder.due_at.desc())
            .all()
        )
    finally:
        session.close()


# ── User actions ──────────────────────────────────────────────────────────────

def create_reminder(
    description: str,
    due_at: datetime,
    memory_id: str = None,
    priority: str = "medium",
    grace_period_hours: int = None,
    archive_after_hours: int = None,
) -> Reminder:
    grace   = grace_period_hours  if grace_period_hours  is not None else config.DEFAULT_GRACE_PERIOD_HOURS
    archive = archive_after_hours if archive_after_hours is not None else config.DEFAULT_ARCHIVE_AFTER_HOURS
    # Normalise priority to a valid enum value; fall back to medium
    try:
        pri = ReminderPriority(priority)
    except ValueError:
        pri = ReminderPriority.medium
    session = get_session()
    try:
        r = Reminder(
            memory_id           = memory_id,
            description         = description,
            due_at              = due_at,
            status              = ReminderStatus.pending,
            priority            = pri,
            grace_period_hours  = grace,
            archive_after_hours = archive,
        )
        session.add(r)
        session.commit()
        session.refresh(r)
        logger.info("Created reminder %s due=%s priority=%s", r.id[:8], due_at, pri.value)
        return r
    finally:
        session.close()


def mark_complete(reminder_id: str) -> bool:
    """Mark a reminder completed — removes it from the active list immediately."""
    session = get_session()
    try:
        r = session.query(Reminder).filter(Reminder.id == reminder_id).first()
        if not r:
            return False
        r.status       = ReminderStatus.completed
        r.completed_at = datetime.utcnow()
        session.commit()
        logger.info("Reminder %s marked completed", reminder_id[:8])
        return True
    finally:
        session.close()


def snooze(reminder_id: str, new_due_at: datetime) -> bool:
    """Keep status pending, push due_at forward."""
    session = get_session()
    try:
        r = session.query(Reminder).filter(Reminder.id == reminder_id).first()
        if not r or r.status != ReminderStatus.pending:
            return False
        r.due_at   = new_due_at
        r.snoozed  = True
        session.commit()
        logger.info("Reminder %s snoozed to %s", reminder_id[:8], new_due_at)
        return True
    finally:
        session.close()


def dismiss(reminder_id: str) -> bool:
    """Immediately flip to missed, skipping the grace period."""
    session = get_session()
    try:
        r = session.query(Reminder).filter(Reminder.id == reminder_id).first()
        if not r:
            return False
        r.status = ReminderStatus.missed
        session.commit()
        logger.info("Reminder %s dismissed → missed", reminder_id[:8])
        return True
    finally:
        session.close()


# ── APScheduler sweep job ─────────────────────────────────────────────────────

def reminder_sweep() -> None:
    """
    Runs every REMINDER_SWEEP_INTERVAL_MINUTES.

    Step 1 — pending → missed:
        now > due_at + grace_period_hours

    Step 2 — completed → hard-delete:
        now > completed_at + archive_after_hours

    Step 3 — missed → hard-delete:
        now > due_at + grace_period_hours + archive_after_hours
    """
    now     = datetime.utcnow()
    session = get_session()
    try:
        # Step 1: flip overdue pending → missed
        pending = session.query(Reminder).filter(Reminder.status == ReminderStatus.pending).all()
        flipped = 0
        for r in pending:
            deadline = r.due_at + timedelta(hours=r.grace_period_hours)
            if now > deadline:
                r.status = ReminderStatus.missed
                flipped += 1
        if flipped:
            session.commit()
            logger.info("reminder_sweep: %d pending → missed", flipped)

        # Step 2: delete completed past archive window
        completed = session.query(Reminder).filter(Reminder.status == ReminderStatus.completed).all()
        deleted_c = 0
        for r in completed:
            if r.completed_at and now > r.completed_at + timedelta(hours=r.archive_after_hours):
                session.delete(r)
                deleted_c += 1
        if deleted_c:
            session.commit()
            logger.info("reminder_sweep: deleted %d completed reminders", deleted_c)

        # Step 3: delete missed past archive window
        missed = session.query(Reminder).filter(Reminder.status == ReminderStatus.missed).all()
        deleted_m = 0
        for r in missed:
            archive_deadline = r.due_at + timedelta(hours=r.grace_period_hours + r.archive_after_hours)
            if now > archive_deadline:
                session.delete(r)
                deleted_m += 1
        if deleted_m:
            session.commit()
            logger.info("reminder_sweep: deleted %d missed reminders", deleted_m)

    finally:
        session.close()

"""
SQLite session management via SQLAlchemy
"""

import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.config import config
from core.models import Base  # noqa: F401 — registers Memory + Reminder

# Resolve SQLITE_PATH to absolute — config already returns absolute path from __init__
_DB_PATH = config.SQLITE_PATH if os.path.isabs(config.SQLITE_PATH) else os.path.join(_PROJECT_ROOT, config.SQLITE_PATH.lstrip("./\\"))
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)

_DB_URL = f"sqlite:///{_DB_PATH}"

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

engine = create_engine(_DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """Create all tables if they don't exist, then apply safe column additions."""
    import core.diary  # noqa: F401 — registers DiaryEntry with Base.metadata (lazy to avoid circular import)
    Base.metadata.create_all(bind=engine)
    _migrate()


def _migrate() -> None:
    """
    Safe, additive migrations for existing databases.
    Each ALTER TABLE is wrapped in a try/except so it is a no-op when the
    column already exists (SQLite raises OperationalError in that case).
    """
    with engine.connect() as conn:
        # Phase 1: add priority column to reminders
        try:
            conn.execute(text(
                "ALTER TABLE reminders ADD COLUMN priority VARCHAR DEFAULT 'medium' NOT NULL"
            ))
            conn.commit()
        except Exception:
            pass  # column already exists

        # Phase 1 (Diary): diary_entries table is created by create_all above;
        # no ALTER needed — all columns are present from the initial CREATE.


def get_session() -> Session:
    """Return a new SQLAlchemy session. Caller is responsible for closing."""
    return SessionLocal()

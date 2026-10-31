"""
SQLAlchemy ORM models — Memory and Reminder
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Float, Integer, DateTime,
    Enum, ForeignKey, LargeBinary, Boolean,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class SourceType(str, PyEnum):
    note     = "note"
    voice    = "voice"
    journal  = "journal"
    task     = "task"
    meeting  = "meeting"


class ReminderStatus(str, PyEnum):
    pending   = "pending"
    completed = "completed"
    missed    = "missed"
    archived  = "archived"


class ReminderPriority(str, PyEnum):
    low    = "low"
    medium = "medium"
    high   = "high"


class Memory(Base):
    __tablename__ = "memories"

    id                = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    content_encrypted = Column(LargeBinary, nullable=False)   # Fernet bytes
    created_at        = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_accessed_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
    access_count      = Column(Integer, default=0, nullable=False)
    importance        = Column(Float, default=0.5, nullable=False)   # 0–1, user-pinnable
    priority_score    = Column(Float, default=0.5, nullable=False)   # computed, cached
    embedding_id      = Column(String, nullable=True)                # ChromaDB record id
    source_type       = Column(Enum(SourceType), default=SourceType.note, nullable=False)
    # NLP-extracted metadata (stored as plain strings — not sensitive)
    intent            = Column(String, nullable=True)   # fact|task|reminder-worthy|journal-reflection
    tone              = Column(String, nullable=True)   # positive|neutral|negative
    summary           = Column(String, nullable=True)   # 1-sentence auto-summary
    memory_type       = Column(String, nullable=True)   # Task|Knowledge|Personal|Event
    tags              = Column(String, nullable=True)   # comma-separated

    reminders = relationship("Reminder", back_populates="memory", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Memory id={self.id[:8]} source={self.source_type} score={self.priority_score:.3f}>"


class Reminder(Base):
    __tablename__ = "reminders"

    id                  = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    memory_id           = Column(String, ForeignKey("memories.id"), nullable=True)
    description         = Column(String, nullable=False)
    due_at              = Column(DateTime, nullable=False)
    status              = Column(Enum(ReminderStatus), default=ReminderStatus.pending, nullable=False)
    # priority added in Phase 1; server_default keeps existing rows valid
    priority            = Column(
                            Enum(ReminderPriority),
                            nullable=False,
                            server_default=ReminderPriority.medium.value,
                            default=ReminderPriority.medium,
                          )
    created_at          = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at        = Column(DateTime, nullable=True)
    grace_period_hours  = Column(Integer, default=24, nullable=False)
    archive_after_hours = Column(Integer, default=72, nullable=False)
    snoozed             = Column(Boolean, default=False, nullable=False)

    memory = relationship("Memory", back_populates="reminders")

    def __repr__(self):
        return f"<Reminder id={self.id[:8]} status={self.status} due={self.due_at}>"

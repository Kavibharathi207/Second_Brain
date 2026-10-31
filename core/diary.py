"""
Digital Diary — core CRUD layer
================================
DiaryEntry is stored in SQLite (encrypted content) and its searchable
chunks are indexed in ChromaDB via the existing vector_store pipeline.

Editing an entry re-indexes its chunks (old chunks are deleted first).
Deleting an entry removes its ChromaDB chunks and the SQLite row.
"""

import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import Column, String, DateTime, LargeBinary

from core.models import Base

import sys, os
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
from backend.security import security_manager

logger = logging.getLogger(__name__)


# ── ORM model ─────────────────────────────────────────────────────────────────

class DiaryEntry(Base):
    __tablename__ = "diary_entries"

    id                = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id           = Column(String, nullable=True, index=True)
    content_encrypted = Column(LargeBinary, nullable=False)
    entry_date        = Column(DateTime, nullable=False)   # user-chosen date
    created_at        = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at        = Column(DateTime, default=datetime.utcnow, nullable=False)
    mood              = Column(String, nullable=True)      # optional mood tag
    tags              = Column(String, nullable=True)      # comma-separated

    def __repr__(self):
        return f"<DiaryEntry id={self.id[:8]} date={self.entry_date.date()}>"


# ── helpers ───────────────────────────────────────────────────────────────────

def _encrypt(text: str) -> bytes:
    return security_manager.encrypt(text)


def _decrypt(blob: bytes) -> str:
    try:
        return security_manager.decrypt(blob)
    except Exception:
        return ""


def _to_dict(entry: DiaryEntry, include_content: bool = True) -> Dict[str, Any]:
    d = {
        "id":         entry.id,
        "user_id":    entry.user_id,
        "entry_date": entry.entry_date.isoformat(),
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
        "mood":       entry.mood,
        "tags":       entry.tags,
    }
    if include_content:
        d["content"] = _decrypt(entry.content_encrypted)
    return d


def _index_entry(entry_id: str, content: str) -> None:
    """Embed and store diary content in ChromaDB under a diary-prefixed ID."""
    try:
        from core.vector_store import add_chunks
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = splitter.split_text(content)
        # Prefix IDs so diary chunks are distinguishable from memory chunks
        prefixed_id = f"diary__{entry_id}"
        add_chunks(prefixed_id, chunks)
    except Exception as e:
        logger.warning("Could not index diary entry %s: %s", entry_id[:8], e)


def _deindex_entry(entry_id: str) -> None:
    """Remove diary chunks from ChromaDB."""
    try:
        from core.vector_store import _collection
        prefixed_id = f"diary__{entry_id}"
        # Fetch all chunk IDs for this entry then delete them
        results = _collection.get(where={"memory_id": prefixed_id})
        if results and results["ids"]:
            _collection.delete(ids=results["ids"])
    except Exception as e:
        logger.debug("Could not deindex diary entry %s: %s", entry_id[:8], e)


# ── Public CRUD API ───────────────────────────────────────────────────────────

def create_entry(
    content: str,
    entry_date: datetime,
    user_id: Optional[str] = None,
    mood: Optional[str] = None,
    tags: Optional[str] = None,
) -> Dict[str, Any]:
    from db.database import get_session
    session = get_session()
    try:
        entry = DiaryEntry(
            id=str(uuid.uuid4()),
            user_id=user_id,
            content_encrypted=_encrypt(content),
            entry_date=entry_date,
            mood=mood,
            tags=tags,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        entry_id = entry.id
        result = _to_dict(entry)
    finally:
        session.close()

    _index_entry(entry_id, content)
    logger.info("Created diary entry %s date=%s", entry_id[:8], entry_date.date())
    return result


def get_entry(entry_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    from db.database import get_session
    session = get_session()
    try:
        q = session.query(DiaryEntry).filter(DiaryEntry.id == entry_id)
        if user_id:
            q = q.filter(DiaryEntry.user_id == user_id)
        entry = q.first()
        return _to_dict(entry) if entry else None
    finally:
        session.close()


def list_entries(
    user_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    from db.database import get_session
    session = get_session()
    try:
        q = session.query(DiaryEntry)
        if user_id:
            q = q.filter(DiaryEntry.user_id == user_id)
        if date_from:
            q = q.filter(DiaryEntry.entry_date >= date_from)
        if date_to:
            q = q.filter(DiaryEntry.entry_date <= date_to)
        rows = q.order_by(DiaryEntry.entry_date.desc()).offset(offset).limit(limit).all()
        return [_to_dict(r) for r in rows]
    finally:
        session.close()


def update_entry(
    entry_id: str,
    content: Optional[str] = None,
    mood: Optional[str] = None,
    tags: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    from db.database import get_session
    session = get_session()
    try:
        q = session.query(DiaryEntry).filter(DiaryEntry.id == entry_id)
        if user_id:
            q = q.filter(DiaryEntry.user_id == user_id)
        entry = q.first()
        if not entry:
            return None
        if content is not None:
            entry.content_encrypted = _encrypt(content)
        if mood is not None:
            entry.mood = mood
        if tags is not None:
            entry.tags = tags
        entry.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(entry)
        new_content = _decrypt(entry.content_encrypted)
        result = _to_dict(entry)
    finally:
        session.close()

    if content is not None:
        _deindex_entry(entry_id)
        _index_entry(entry_id, new_content)

    logger.info("Updated diary entry %s", entry_id[:8])
    return result


def delete_entry(entry_id: str, user_id: Optional[str] = None) -> bool:
    from db.database import get_session
    session = get_session()
    try:
        q = session.query(DiaryEntry).filter(DiaryEntry.id == entry_id)
        if user_id:
            q = q.filter(DiaryEntry.user_id == user_id)
        entry = q.first()
        if not entry:
            return False
        session.delete(entry)
        session.commit()
    finally:
        session.close()

    _deindex_entry(entry_id)
    logger.info("Deleted diary entry %s", entry_id[:8])
    return True


def search_entries(
    query: str,
    user_id: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Semantic search over diary entries via ChromaDB, then fetch full entries
    from SQLite and decrypt them.
    """
    try:
        from core.vector_store import query as vs_query
        hits = vs_query(query, top_k=top_k * 2)
        # Filter to diary chunks only
        diary_hits = [h for h in hits if h["memory_id"].startswith("diary__")]
        seen_ids: set = set()
        results = []
        for h in diary_hits:
            entry_id = h["memory_id"].removeprefix("diary__")
            if entry_id in seen_ids:
                continue
            seen_ids.add(entry_id)
            entry = get_entry(entry_id, user_id=user_id)
            if entry:
                entry["_score"] = h["final_score"]
                results.append(entry)
            if len(results) >= top_k:
                break
        return results
    except Exception as e:
        logger.warning("Diary search failed: %s", e)
        return []

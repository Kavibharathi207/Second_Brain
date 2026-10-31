"""
Decay Engine — exponential recency decay + frequency factor
============================================================

Priority score formula
----------------------
  R(t) = e^(-λ · Δt)          recency factor
         λ = ln(2) / HALF_LIFE_HOURS
         Δt = hours since last_accessed_at

  F    = log(1 + access_count) frequency factor (diminishing returns)

  priority_score = importance × R(t) × F
  normalized     = priority_score / max_priority_score_in_corpus

A memory is NEVER deleted for low score — only deprioritised in ranking.
"""

import math
import logging
from datetime import datetime
from typing import Optional

from db.database import get_session, init_db
from core.models import Memory

import sys, os
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
from backend.config import config

logger = logging.getLogger(__name__)


def _lambda() -> float:
    """Decay constant derived from the configured half-life."""
    return math.log(2) / config.HALF_LIFE_HOURS


def recency_factor(last_accessed_at: datetime) -> float:
    """R(t) = e^(-λ · Δt)  where Δt is hours since last access."""
    delta_hours = (datetime.utcnow() - last_accessed_at).total_seconds() / 3600.0
    return math.exp(-_lambda() * delta_hours)


def frequency_factor(access_count: int) -> float:
    """F = log(1 + access_count)  — diminishing returns."""
    return math.log1p(max(access_count, 0))


def compute_priority_score(memory: Memory) -> float:
    """Raw (un-normalised) priority score for a single memory."""
    r = recency_factor(memory.last_accessed_at or memory.created_at)
    f = frequency_factor(memory.access_count)
    return memory.importance * r * f


def normalise_scores(session) -> None:
    """
    Recompute and cache priority_score for every memory.
    Normalises by the current corpus maximum so scores stay in [0, 1].
    """
    memories = session.query(Memory).all()
    if not memories:
        return

    raw_scores = {m.id: compute_priority_score(m) for m in memories}
    max_score  = max(raw_scores.values()) or 1.0

    for m in memories:
        m.priority_score = raw_scores[m.id] / max_score

    session.commit()
    logger.debug("Decay scores normalised. max_raw=%.4f", max_score)


def bump_access(memory_id: str) -> Optional[float]:
    """
    Called on every read of a memory.
    Increments access_count, resets last_accessed_at, recomputes priority_score.
    Returns the new (un-normalised) score, or None if memory not found.
    """
    session = get_session()
    try:
        m = session.query(Memory).filter(Memory.id == memory_id).first()
        if not m:
            return None
        m.access_count     += 1
        m.last_accessed_at  = datetime.utcnow()
        m.priority_score    = compute_priority_score(m)
        session.commit()
        logger.debug("bump_access %s → score=%.4f", memory_id[:8], m.priority_score)
        return m.priority_score
    finally:
        session.close()


def decay_job() -> None:
    """
    APScheduler job — runs every DECAY_JOB_INTERVAL_MINUTES.
    Recomputes and normalises priority_score for all memories.
    """
    if not config.MEMORY_DECAY_ENABLED:
        return
    logger.info("Running decay_job …")
    session = get_session()
    try:
        normalise_scores(session)
    finally:
        session.close()

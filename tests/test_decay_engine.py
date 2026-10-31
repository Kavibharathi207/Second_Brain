"""
tests/test_decay_engine.py
==========================
Assertions:
  1. Score halves at exactly one half-life of inactivity.
  2. Repeated access increases F but with diminishing returns.
  3. bump_access resets Δt to ~0 (score jumps back up).
"""

import math
import sys
import os
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.config import config
from core.decay_engine import recency_factor, frequency_factor, compute_priority_score, bump_access
from core.models import Memory
from db.database import init_db, get_session


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_memory(session, hours_ago: float = 0, access_count: int = 0, importance: float = 1.0) -> Memory:
    m = Memory(
        id=str(uuid.uuid4()),
        content_encrypted=b"test",
        last_accessed_at=datetime.utcnow() - timedelta(hours=hours_ago),
        access_count=access_count,
        importance=importance,
    )
    session.add(m)
    session.commit()
    session.refresh(m)
    return m


# ── Test 1: score halves at one half-life ─────────────────────────────────────

def test_score_halves_at_half_life():
    r_now  = recency_factor(datetime.utcnow())
    r_half = recency_factor(datetime.utcnow() - timedelta(hours=config.HALF_LIFE_HOURS))
    ratio  = r_half / r_now
    assert abs(ratio - 0.5) < 0.01, f"Expected ratio ~0.5, got {ratio:.4f}"
    print(f"✅ test_score_halves_at_half_life  ratio={ratio:.4f}")


# ── Test 2: frequency factor has diminishing returns ─────────────────────────

def test_frequency_diminishing_returns():
    f1   = frequency_factor(1)
    f10  = frequency_factor(10)
    f100 = frequency_factor(100)
    # Each 10× increase in access_count should yield < 10× increase in F
    assert f10 / f1   < 10,  f"f10/f1={f10/f1:.2f} should be < 10"
    assert f100 / f10 < 10,  f"f100/f10={f100/f10:.2f} should be < 10"
    assert f100 > f10 > f1,  "F should still increase monotonically"
    print(f"✅ test_frequency_diminishing_returns  f1={f1:.3f} f10={f10:.3f} f100={f100:.3f}")


# ── Test 3: bump_access resets Δt ─────────────────────────────────────────────

def test_bump_access_resets_delta_t():
    init_db()
    session = get_session()
    try:
        # Memory last accessed 3 half-lives ago → very low score
        m = _make_memory(session, hours_ago=config.HALF_LIFE_HOURS * 3, access_count=0)
        score_before = compute_priority_score(m)

        bump_access(m.id)

        session.expire(m)
        session.refresh(m)
        score_after = compute_priority_score(m)

        assert score_after > score_before * 4, (
            f"After bump, score should be much higher. before={score_before:.4f} after={score_after:.4f}"
        )
        assert m.access_count == 1
        delta_hours = (datetime.utcnow() - m.last_accessed_at).total_seconds() / 3600
        assert delta_hours < 0.01, f"last_accessed_at should be ~now, got Δt={delta_hours:.4f}h"
        print(f"✅ test_bump_access_resets_delta_t  before={score_before:.4f} after={score_after:.4f}")
    finally:
        session.close()


# ── runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_score_halves_at_half_life()
    test_frequency_diminishing_returns()
    test_bump_access_resets_delta_t()
    print("\n🎉 All decay engine tests passed.")

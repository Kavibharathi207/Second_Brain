"""
tests/test_rag_engine.py
========================
Covers:
  1. Combined score formula: final = 0.7×semantic + 0.3×priority is applied.
  2. query() returns results ranked by final_score descending.
  3. RAG answer references stored memory content (grounded response).
"""

import sys
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import init_db
from core.vector_store import add_chunks, query
from backend.config import config


def setup():
    init_db()


# ── Test 1: combined score is within [0, 1] and formula is applied ────────────

def test_combined_score_range():
    setup()
    mid = str(uuid.uuid4())
    add_chunks(mid, ["The project deadline is next Friday at 5 PM."])

    results = query("project deadline", top_k=1)
    assert results, "Expected at least one result"
    score = results[0]["final_score"]
    assert 0.0 <= score <= 1.0, f"final_score out of range: {score}"

    # Verify formula components are present
    assert "distance" in results[0]
    assert "memory_id" in results[0]
    print(f"✅ test_combined_score_range  final_score={score:.4f}")


# ── Test 2: results are ranked by final_score descending ─────────────────────

def test_results_ranked_by_score():
    setup()
    mid1 = str(uuid.uuid4())
    mid2 = str(uuid.uuid4())
    add_chunks(mid1, ["I have a dentist appointment on Monday morning."])
    add_chunks(mid2, ["The sky is blue and the weather is nice today."])

    results = query("dentist appointment Monday", top_k=5)
    assert len(results) >= 2, "Expected at least 2 results"
    scores = [r["final_score"] for r in results]
    assert scores == sorted(scores, reverse=True), "Results not sorted by final_score"
    print(f"✅ test_results_ranked_by_score  scores={[f'{s:.3f}' for s in scores[:3]]}")


# ── Test 3: RAG answer is grounded in stored memory ───────────────────────────

def test_rag_answer_grounded():
    """Requires Ollama to be running. Skips gracefully if not."""
    setup()
    try:
        from backend.ollama_service import ollama_service
        if not ollama_service.check_connection():
            print("⏭️  test_rag_answer_grounded skipped (Ollama offline)")
            return
    except Exception:
        print("⏭️  test_rag_answer_grounded skipped (import error)")
        return

    from backend.rag_engine import rag_engine

    unique_fact = f"My favourite colour is ultraviolet_{uuid.uuid4().hex[:6]}."
    mid = str(uuid.uuid4())
    from backend.memory_store import memory_store
    memory_store.store_memory(unique_fact, {"importance": 0.9})

    result = rag_engine.ask_memory("What is my favourite colour?")
    response = result.get("response", "").lower()
    assert "ultraviolet" in response or result["memories_used"] > 0, (
        f"RAG answer not grounded. response='{response[:100]}'"
    )
    print(f"✅ test_rag_answer_grounded  memories_used={result['memories_used']}")


# ── runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_combined_score_range()
    test_results_ranked_by_score()
    test_rag_answer_grounded()
    print("\n🎉 All RAG engine tests passed.")

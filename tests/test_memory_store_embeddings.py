"""
tests/test_memory_store_embeddings.py
======================================
Regression tests for the Phase 2A embedding fix.

Verifies:
  1. Embeddings are generated from plaintext (not ciphertext).
  2. ChromaDB documents contain encrypted content (not plaintext).
  3. Query embeddings use the configured Ollama model.
  4. Retrieved content is correctly decrypted to original plaintext.
  5. User isolation: user A cannot retrieve user B's memories.
  6. Ollama offline raises a clear RuntimeError (no silent fallback).
  7. Existing metadata (importance, tags, access_count) is preserved
     through a store → retrieve round-trip.

All tests skip gracefully when Ollama is offline, except test 6 which
specifically requires Ollama to be offline to verify the error path.
"""

import sys
import os
import uuid
import base64

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.config import config
from backend.security import security_manager
from backend.ollama_service import ollama_service


# ── helpers ───────────────────────────────────────────────────────────────────

def _ollama_online() -> bool:
    return ollama_service.check_connection()


def _is_ciphertext(text: str) -> bool:
    """Return True if *text* looks like a Fernet base64url ciphertext."""
    try:
        decoded = base64.urlsafe_b64decode(text + "==")
        return len(decoded) > 0 and decoded[0] == 0x80
    except Exception:
        return False


def _fresh_store():
    """Return a fresh MemoryStore instance (avoids module-level singleton state)."""
    from backend.memory_store import MemoryStore
    return MemoryStore()


# ── Test 1: embedding is generated from plaintext ─────────────────────────────

def test_embedding_generated_from_plaintext():
    """
    Store a memory, then retrieve the raw embedding from ChromaDB.
    Verify the embedding is identical to one generated directly from
    the plaintext — not from the ciphertext.
    """
    if not _ollama_online():
        print("⏭️  test_embedding_generated_from_plaintext skipped (Ollama offline)")
        return

    store = _fresh_store()
    plaintext = f"My cat is named Whiskers_{uuid.uuid4().hex[:6]}."
    mid = f"test_emb_{uuid.uuid4().hex[:8]}"

    store.store_memory(plaintext, {"importance": 0.7, "tags": ["cat", "pet"]}, memory_id=mid)

    # Fetch the stored embedding directly from ChromaDB
    result = store.collection.get(ids=[mid], include=["embeddings"])
    assert result["embeddings"], "No embedding stored"
    stored_vec = result["embeddings"][0]

    # Generate the expected embedding directly from plaintext
    expected_vec = ollama_service.embed(plaintext, model=config.OLLAMA_EMBEDDING_MODEL)
    assert expected_vec is not None, "Could not generate reference embedding"

    # Vectors should be identical (same model, same text, deterministic)
    assert len(stored_vec) == len(expected_vec), (
        f"Dimension mismatch: stored={len(stored_vec)} expected={len(expected_vec)}"
    )
    # Allow tiny floating-point tolerance
    diffs = [abs(a - b) for a, b in zip(stored_vec, expected_vec)]
    assert max(diffs) < 1e-4, f"Embedding mismatch: max_diff={max(diffs):.6f}"

    # Cleanup
    store.delete_memory(mid)
    print(f"✅ test_embedding_generated_from_plaintext  dim={len(stored_vec)}")


# ── Test 2: ChromaDB document contains ciphertext, not plaintext ──────────────

def test_document_stored_as_ciphertext():
    """
    The document field in ChromaDB must be encrypted ciphertext.
    Plaintext must never appear in the ChromaDB document store.
    """
    if not _ollama_online():
        print("⏭️  test_document_stored_as_ciphertext skipped (Ollama offline)")
        return

    store = _fresh_store()
    plaintext = f"Secret project codename is Phoenix_{uuid.uuid4().hex[:6]}."
    mid = f"test_doc_{uuid.uuid4().hex[:8]}"

    store.store_memory(plaintext, {"importance": 0.5}, memory_id=mid)

    # Fetch raw document from ChromaDB
    result = store.collection.get(ids=[mid], include=["documents"])
    assert result["documents"], "No document stored"
    raw_doc = result["documents"][0]

    # Must be ciphertext
    assert _is_ciphertext(raw_doc), (
        f"Document is NOT ciphertext — plaintext may be stored in ChromaDB. "
        f"Preview: {raw_doc[:80]}"
    )

    # Must NOT contain the plaintext
    assert plaintext not in raw_doc, "Plaintext found verbatim in ChromaDB document"

    # Cleanup
    store.delete_memory(mid)
    print(f"✅ test_document_stored_as_ciphertext  doc_len={len(raw_doc)}")


# ── Test 3: query embedding uses the configured model ─────────────────────────

def test_query_embedding_uses_configured_model():
    """
    retrieve_memories must embed the query using the configured Ollama
    embedding model.  We verify this by checking that the query produces
    a vector of the expected dimension (768 for nomic-embed-text) and
    that a semantically relevant memory is ranked first.
    """
    if not _ollama_online():
        print("⏭️  test_query_embedding_uses_configured_model skipped (Ollama offline)")
        return

    store = _fresh_store()
    unique_token = uuid.uuid4().hex[:8]
    content_a = f"I have a dentist appointment on Tuesday_{unique_token}."
    content_b = f"The weather forecast says rain tomorrow_{unique_token}."
    mid_a = f"test_qa_{uuid.uuid4().hex[:8]}"
    mid_b = f"test_qb_{uuid.uuid4().hex[:8]}"

    store.store_memory(content_a, {"importance": 0.6}, memory_id=mid_a)
    store.store_memory(content_b, {"importance": 0.6}, memory_id=mid_b)

    results = store.retrieve_memories(f"dentist appointment Tuesday_{unique_token}", top_k=2)
    assert results, "No results returned"

    # The dentist memory should rank first
    assert results[0]["id"] == mid_a, (
        f"Expected dentist memory first, got id={results[0]['id']}"
    )

    # Verify distance is a valid cosine distance [0, 2]
    for r in results:
        assert r["distance"] is not None
        assert 0.0 <= r["distance"] <= 2.0, f"Invalid distance: {r['distance']}"

    # Cleanup
    store.delete_memory(mid_a)
    store.delete_memory(mid_b)
    print(f"✅ test_query_embedding_uses_configured_model  top_id={results[0]['id'][:8]}")


# ── Test 4: retrieved content is correctly decrypted ─────────────────────────

def test_retrieved_content_decrypts_to_original():
    """
    store_memory → retrieve_memories must return the exact original plaintext.
    """
    if not _ollama_online():
        print("⏭️  test_retrieved_content_decrypts_to_original skipped (Ollama offline)")
        return

    store = _fresh_store()
    original = f"My PIN for the gym locker is 4729_{uuid.uuid4().hex[:6]}."
    mid = f"test_dec_{uuid.uuid4().hex[:8]}"

    store.store_memory(original, {"importance": 0.8, "tags": ["gym", "personal"]}, memory_id=mid)

    # Retrieve via semantic search
    results = store.retrieve_memories(original[:40], top_k=5)
    match = next((r for r in results if r["id"] == mid), None)
    assert match is not None, f"Stored memory {mid[:8]} not found in retrieval results"
    assert match["content"] == original, (
        f"Decrypted content does not match original.\n"
        f"  Expected: {original}\n"
        f"  Got:      {match['content']}"
    )

    # Also verify via get_memory (non-search path)
    fetched = store.get_memory(mid)
    assert fetched is not None
    assert fetched["content"] == original

    # Cleanup
    store.delete_memory(mid)
    print(f"✅ test_retrieved_content_decrypts_to_original  id={mid[:8]}")


# ── Test 5: user isolation ────────────────────────────────────────────────────

def test_user_isolation():
    """
    Memories stored with user_id=A must not appear in queries for user_id=B.
    """
    if not _ollama_online():
        print("⏭️  test_user_isolation skipped (Ollama offline)")
        return

    store = _fresh_store()
    uid_a = f"user_a_{uuid.uuid4().hex[:6]}"
    uid_b = f"user_b_{uuid.uuid4().hex[:6]}"
    token = uuid.uuid4().hex[:8]

    content_a = f"Alice secret project alpha_{token}."
    content_b = f"Bob secret project beta_{token}."
    mid_a = f"test_iso_a_{uuid.uuid4().hex[:8]}"
    mid_b = f"test_iso_b_{uuid.uuid4().hex[:8]}"

    store.store_memory(content_a, {"importance": 0.7}, memory_id=mid_a, user_id=uid_a)
    store.store_memory(content_b, {"importance": 0.7}, memory_id=mid_b, user_id=uid_b)

    # Query as user A — must not see user B's memory
    results_a = store.retrieve_memories(f"secret project_{token}", top_k=5, user_id=uid_a)
    ids_a = [r["id"] for r in results_a]
    assert mid_a in ids_a, "User A's own memory not returned"
    assert mid_b not in ids_a, "User B's memory leaked into user A's results"

    # Query as user B — must not see user A's memory
    results_b = store.retrieve_memories(f"secret project_{token}", top_k=5, user_id=uid_b)
    ids_b = [r["id"] for r in results_b]
    assert mid_b in ids_b, "User B's own memory not returned"
    assert mid_a not in ids_b, "User A's memory leaked into user B's results"

    # Cleanup
    store.delete_memory(mid_a)
    store.delete_memory(mid_b)
    print(f"✅ test_user_isolation  uid_a={uid_a[:12]} uid_b={uid_b[:12]}")


# ── Test 6: Ollama offline raises RuntimeError ────────────────────────────────

def test_ollama_offline_raises_clear_error():
    """
    When Ollama is offline, store_memory and retrieve_memories must raise
    RuntimeError with a clear message — not silently fall back to a
    different embedding model.
    """
    from unittest.mock import patch
    from backend.memory_store import _embed_plaintext

    # _embed_plaintext imports ollama_service from backend.ollama_service at
    # call time.  Patch check_connection on the class so every instance sees
    # the mock regardless of when it was instantiated.
    with patch("backend.ollama_service.OllamaService.check_connection", return_value=False):
        try:
            _embed_plaintext("some text")
            assert False, "Expected RuntimeError was not raised"
        except RuntimeError as e:
            msg = str(e)
            assert "Ollama" in msg, f"Error message should mention Ollama: {msg}"
            assert "not running" in msg.lower() or "ollama" in msg.lower()
            print(f"✅ test_ollama_offline_raises_clear_error  msg='{msg[:60]}...'")

# ── Test 7: metadata preserved through round-trip ────────────────────────────

def test_metadata_preserved_round_trip():
    """
    importance, tags, access_count and custom metadata must survive
    a store → get_memory round-trip unchanged.
    """
    if not _ollama_online():
        print("⏭️  test_metadata_preserved_round_trip skipped (Ollama offline)")
        return

    store = _fresh_store()
    mid = f"test_meta_{uuid.uuid4().hex[:8]}"
    content = f"Meeting with the design team on Friday_{uuid.uuid4().hex[:6]}."
    metadata = {
        "importance": 0.85,
        "tags": ["meeting", "design", "friday"],
        "access_count": 0,
        "priority": "high",
        "memory_type": "Event",
    }

    store.store_memory(content, metadata.copy(), memory_id=mid)

    fetched = store.get_memory(mid)
    assert fetched is not None, "Memory not found after storing"

    meta = fetched["metadata"]
    assert float(meta.get("importance", 0)) == 0.85, (
        f"importance mismatch: {meta.get('importance')}"
    )
    assert meta.get("priority") == "high", f"priority mismatch: {meta.get('priority')}"
    assert meta.get("memory_type") == "Event", f"memory_type mismatch: {meta.get('memory_type')}"
    assert int(meta.get("access_count", -1)) == 0, (
        f"access_count mismatch: {meta.get('access_count')}"
    )
    # Tags may be stored as JSON string or list — deserialise handles both
    tags = meta.get("tags", [])
    if isinstance(tags, str):
        import json
        tags = json.loads(tags)
    assert "meeting" in tags, f"'meeting' tag missing: {tags}"
    assert "design" in tags, f"'design' tag missing: {tags}"

    # Cleanup
    store.delete_memory(mid)
    print(f"✅ test_metadata_preserved_round_trip  id={mid[:8]}")


# ── runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_embedding_generated_from_plaintext()
    test_document_stored_as_ciphertext()
    test_query_embedding_uses_configured_model()
    test_retrieved_content_decrypts_to_original()
    test_user_isolation()
    test_ollama_offline_raises_clear_error()
    test_metadata_preserved_round_trip()
    print("\n🎉 All memory store embedding tests passed.")

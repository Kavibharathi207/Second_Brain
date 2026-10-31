"""
Vector Store — ChromaDB persistent client
==========================================
Functions:
  add_chunks(memory_id, chunks)  — embed and store text chunks
  query(query_text, top_k)       — retrieve chunks, re-rank by combined score,
                                   call bump_access on every hit
"""

import logging
from typing import List, Dict, Any

import chromadb
from langchain_ollama import OllamaEmbeddings

import sys, os
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
from backend.config import config

logger = logging.getLogger(__name__)

# ── ChromaDB client ───────────────────────────────────────────────────────────

os.makedirs(config.CHROMA_DB_PATH, exist_ok=True)
_client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
# Use a dedicated collection for the core ingestion pipeline so it never
# conflicts with the backend/memory_store.py collection (which may have been
# initialised with a different embedding dimension).
_CORE_COLLECTION_NAME = config.CHROMA_COLLECTION_NAME + "_core"
_collection = _client.get_or_create_collection(
    name=_CORE_COLLECTION_NAME,
    metadata={"hnsw:space": "cosine"},
)

# ── Embeddings (Ollama primary, sentence-transformers fallback) ───────────────

def _get_embeddings(texts: List[str]) -> List[List[float]]:
    try:
        emb = OllamaEmbeddings(
            model=config.OLLAMA_EMBEDDING_MODEL,
            base_url=config.OLLAMA_HOST,
        )
        return emb.embed_documents(texts)
    except Exception as e:
        logger.warning("Ollama embeddings failed (%s), using sentence-transformers fallback", e)
        from sentence_transformers import SentenceTransformer
        # all-mpnet-base-v2 produces 768-dim vectors, matching nomic-embed-text
        model = SentenceTransformer("all-mpnet-base-v2")
        return model.encode(texts, convert_to_numpy=True).tolist()


# ── Public API ────────────────────────────────────────────────────────────────

def add_chunks(memory_id: str, chunks: List[str]) -> None:
    """Embed each chunk and upsert into ChromaDB."""
    if not chunks:
        return
    embeddings = _get_embeddings(chunks)
    ids = [f"{memory_id}__chunk_{i}" for i in range(len(chunks))]
    _collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=[{"memory_id": memory_id, "chunk_index": i} for i in range(len(chunks))],
    )
    logger.debug("Stored %d chunks for memory %s", len(chunks), memory_id[:8])


def query(query_text: str, top_k: int = None) -> List[Dict[str, Any]]:
    """
    Retrieve top-k chunks, re-rank by combined score:
      final_score = 0.7 × semantic_similarity + 0.3 × normalized_priority_score

    Calls bump_access on every unique memory_id hit.
    Returns list of dicts: {chunk_text, memory_id, distance, final_score}
    """
    if top_k is None:
        top_k = config.RETRIEVAL_TOP_K

    try:
        query_emb = _get_embeddings([query_text])[0]
    except Exception as e:
        logger.error("Failed to embed query: %s", e)
        return []

    try:
        results = _collection.query(
            query_embeddings=[query_emb],
            n_results=min(top_k * 3, max(_collection.count(), 1)),
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.error("ChromaDB query failed: %s", e)
        return []

    if not results or not results["ids"] or not results["ids"][0]:
        return []

    # Gather priority scores from SQLite
    memory_ids = list({m["memory_id"] for m in results["metadatas"][0]})
    priority_map = _get_priority_scores(memory_ids)
    max_p = max(priority_map.values(), default=1.0) or 1.0

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        semantic_sim = max(0.0, 1.0 - dist)   # cosine distance → similarity
        norm_priority = priority_map.get(meta["memory_id"], 0.5) / max_p
        final_score = (
            config.RAG_SEMANTIC_WEIGHT * semantic_sim
            + config.RAG_PRIORITY_WEIGHT * norm_priority
        )
        hits.append({
            "chunk_text": doc,
            "memory_id":  meta["memory_id"],
            "distance":   dist,
            "final_score": final_score,
        })

    # Re-rank by combined score
    hits.sort(key=lambda h: h["final_score"], reverse=True)
    hits = hits[:top_k]

    # Bump access for every unique memory retrieved
    seen = set()
    for h in hits:
        mid = h["memory_id"]
        if mid not in seen:
            seen.add(mid)
            _bump_access_safe(mid)

    return hits


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_priority_scores(memory_ids: List[str]) -> Dict[str, float]:
    """Fetch cached priority_score from SQLite for a list of memory IDs."""
    if not memory_ids:
        return {}
    try:
        from db.database import get_session
        from core.models import Memory
        session = get_session()
        try:
            rows = session.query(Memory.id, Memory.priority_score).filter(
                Memory.id.in_(memory_ids)
            ).all()
            return {r.id: r.priority_score for r in rows}
        finally:
            session.close()
    except Exception as e:
        logger.warning("Could not fetch priority scores: %s", e)
        return {}


def _bump_access_safe(memory_id: str) -> None:
    try:
        from core.decay_engine import bump_access
        bump_access(memory_id)
    except Exception as e:
        logger.debug("bump_access failed for %s: %s", memory_id[:8], e)


# Module-level singleton for import convenience
vector_store = type("_VS", (), {
    "add_chunks": staticmethod(add_chunks),
    "query":      staticmethod(query),
    "client":     _client,
    "collection": _collection,
})()

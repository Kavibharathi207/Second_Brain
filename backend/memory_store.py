"""
Memory storage layer using ChromaDB for vector storage.
Every method accepts an optional user_id so memories are
fully isolated per user.  Passing user_id=None falls back
to the legacy behaviour (returns ALL memories) so existing
code that hasn't been updated yet won't break.

Embedding contract
------------------
Embeddings are ALWAYS generated from plaintext BEFORE encryption.
Encrypted ciphertext is stored as the ChromaDB document field so
no plaintext ever persists in ChromaDB.  Pre-computed embeddings
are passed explicitly to every add/upsert/query call so
OllamaEmbeddingFunction is never invoked on ciphertext.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from .config import config
from .security import security_manager


class OllamaEmbeddingFunction(EmbeddingFunction):
    """
    Registered on the collection so ChromaDB has a callable for any
    internal path that requires one.  In normal operation this class is
    NOT invoked for stored documents or queries — callers always supply
    pre-computed embeddings.  It is only a safety net for ChromaDB
    internals and must never receive ciphertext.
    """

    def __init__(self):
        from .ollama_service import OllamaService
        self.ollama = OllamaService()

    def __call__(self, texts: Documents) -> Embeddings:
        if not self.ollama.check_connection():
            raise RuntimeError(
                "[Ollama] Cannot generate embeddings: Ollama is not running. "
                "Start it with: ollama serve"
            )
        embeddings = []
        for text in texts:
            emb = self.ollama.embed(text, model=config.OLLAMA_EMBEDDING_MODEL)
            if emb is None:
                raise RuntimeError(
                    f"[Ollama] Embedding failed for model '{config.OLLAMA_EMBEDDING_MODEL}'. "
                    f"Ensure the model is pulled: ollama pull {config.OLLAMA_EMBEDDING_MODEL}"
                )
            embeddings.append(emb)
        return embeddings


def _embed_plaintext(text: str) -> List[float]:
    """
    Generate an embedding from *plaintext* using the configured Ollama
    embedding model.  Raises RuntimeError if Ollama is unreachable or
    returns None — callers must not silently swallow this error.
    """
    from .ollama_service import ollama_service
    if not ollama_service.check_connection():
        raise RuntimeError(
            "[MemoryStore] Ollama is not running. "
            "Cannot generate embeddings. Start it with: ollama serve"
        )
    vector = ollama_service.embed(text, model=config.OLLAMA_EMBEDDING_MODEL)
    if vector is None:
        raise RuntimeError(
            f"[MemoryStore] Embedding returned None for model "
            f"'{config.OLLAMA_EMBEDDING_MODEL}'. "
            f"Ensure the model is pulled: ollama pull {config.OLLAMA_EMBEDDING_MODEL}"
        )
    return vector


class MemoryStore:
    """Manages memory storage and retrieval using ChromaDB."""

    def __init__(self):
        os.makedirs(config.CHROMA_DB_PATH, exist_ok=True)
        self.client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
        self.collection = self._get_or_create_collection()

    def _get_or_create_collection(self):
        return self.client.get_or_create_collection(
            name=config.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
            embedding_function=OllamaEmbeddingFunction(),
        )

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _user_filter(user_id: Optional[str]) -> Optional[Dict]:
        """Build a ChromaDB where-filter for user_id, or None if not given."""
        if user_id:
            return {"user_id": {"$eq": user_id}}
        return None

    # ── write ─────────────────────────────────────────────────────────────────

    # ── metadata helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _serialize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        ChromaDB only accepts str | int | float | bool as metadata values.
        Serialize any list/dict values to JSON strings so they survive the
        round-trip without raising a ValueError.
        """
        safe: Dict[str, Any] = {}
        for k, v in metadata.items():
            if isinstance(v, (list, dict)):
                safe[k] = json.dumps(v)
            elif isinstance(v, (str, int, float, bool)) or v is None:
                safe[k] = v
            else:
                safe[k] = str(v)
        return safe

    @staticmethod
    def _deserialize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reverse _serialize_metadata: any value that looks like a JSON list or
        object is decoded back to its Python type.
        """
        result: Dict[str, Any] = {}
        for k, v in metadata.items():
            if isinstance(v, str) and v.startswith(("[", "{")):
                try:
                    result[k] = json.loads(v)
                except (ValueError, TypeError):
                    result[k] = v
            else:
                result[k] = v
        return result

    def store_memory(
        self,
        content: str,
        metadata: Dict[str, Any],
        memory_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        if memory_id is None:
            memory_id = f"memory_{datetime.now().timestamp()}"

        metadata.setdefault("created_at", datetime.now().isoformat())
        metadata.setdefault("access_count", 0)
        metadata.setdefault("importance", 1.0)

        # Always stamp user_id so we can filter later
        if user_id:
            metadata["user_id"] = user_id

        # 1. Generate embedding from PLAINTEXT before any encryption.
        # 2. Encrypt the content — ciphertext is stored as the document.
        # 3. Pass the pre-computed embedding explicitly so ChromaDB never
        #    calls OllamaEmbeddingFunction on the ciphertext.
        embedding = _embed_plaintext(content)
        encrypted_content = security_manager.encrypt_text(content)
        self.collection.add(
            ids=[memory_id],
            embeddings=[embedding],
            documents=[encrypted_content],
            metadatas=[self._serialize_metadata(metadata)],
        )
        return memory_id

    def update_memory(
        self,
        memory_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            update_data: Dict[str, Any] = {}
            if content:
                # Re-embed from plaintext, then encrypt for storage.
                update_data["embeddings"] = [_embed_plaintext(content)]
                update_data["documents"]  = [security_manager.encrypt_text(content)]
            if metadata:
                update_data["metadatas"] = [self._serialize_metadata(metadata)]
            if update_data:
                self.collection.update(ids=[memory_id], **update_data)
            return True
        except Exception as e:
            print(f"Error updating memory: {e}")
            return False

    def delete_memory(self, memory_id: str) -> bool:
        try:
            self.collection.delete(ids=[memory_id])
            return True
        except Exception as e:
            print(f"Error deleting memory: {e}")
            return False

    # ── read ──────────────────────────────────────────────────────────────────

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        try:
            result = self.collection.get(ids=[memory_id])
            if result and result["ids"]:
                raw = result["documents"][0]
                try:
                    content = security_manager.decrypt_text(raw)
                except Exception:
                    content = raw
                return {
                    "id": memory_id,
                    "content": content,
                    "metadata": self._deserialize_metadata(result["metadatas"][0]),
                }
            return None
        except Exception as e:
            print(f"Error getting memory: {e}")
            return None

    def get_all_memories(
        self,
        include_metadata: bool = True,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        try:
            kwargs: Dict[str, Any] = {"include": ["documents", "metadatas"]}
            where = self._user_filter(user_id)
            if where:
                kwargs["where"] = where

            results = self.collection.get(**kwargs)
            memories = []
            if results and results["ids"]:
                for i, mid in enumerate(results["ids"]):
                    raw = results["documents"][i] if results["documents"] else ""
                    try:
                        content = security_manager.decrypt_text(raw)
                    except Exception:
                        content = raw
                    raw_meta = results["metadatas"][i] if include_metadata else {}
                    memories.append({
                        "id": mid,
                        "content": content,
                        "metadata": self._deserialize_metadata(raw_meta),
                    })
            return memories
        except Exception as e:
            print(f"Error getting all memories: {e}")
            return []

    def retrieve_memories(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if top_k is None:
            top_k = config.RETRIEVAL_TOP_K

        # Merge user_id filter with any caller-supplied filters
        where = self._user_filter(user_id)
        if filters and where:
            where = {"$and": [where, filters]}
        elif filters:
            where = filters

        try:
            # Embed the query from plaintext explicitly so ChromaDB never
            # calls OllamaEmbeddingFunction on query text via query_texts=.
            query_embedding = _embed_plaintext(query)

            query_kwargs: Dict[str, Any] = {
                "query_embeddings": [query_embedding],
                "n_results": top_k,
                "include": ["documents", "metadatas", "distances"],
            }
            if where:
                query_kwargs["where"] = where

            results = self.collection.query(**query_kwargs)
            memories = []
            if results and results["ids"] and results["ids"][0]:
                for i, mid in enumerate(results["ids"][0]):
                    raw = results["documents"][0][i]
                    try:
                        content = security_manager.decrypt_text(raw)
                    except Exception:
                        content = raw
                    memories.append({
                        "id": mid,
                        "content": content,
                        "metadata": self._deserialize_metadata(results["metadatas"][0][i]),
                        "distance": results["distances"][0][i] if results["distances"] else None,
                    })
            return memories
        except Exception as e:
            print(f"Error retrieving memories: {e}")
            return []

    def update_access_count(self, memory_id: str) -> bool:
        try:
            memory = self.get_memory(memory_id)
            if memory:
                meta = memory["metadata"]
                meta["access_count"] = meta.get("access_count", 0) + 1
                meta["last_accessed"] = datetime.now().isoformat()
                self.update_memory(memory_id, metadata=meta)
                return True
            return False
        except Exception as e:
            print(f"Error updating access count: {e}")
            return False

    def clear_all_memories(self, user_id: Optional[str] = None) -> bool:
        """Delete all memories for a specific user (or ALL if user_id is None)."""
        try:
            memories = self.get_all_memories(include_metadata=False, user_id=user_id)
            for m in memories:
                self.delete_memory(m["id"])
            return True
        except Exception as e:
            print(f"Error clearing memories: {e}")
            return False


# Global instance
memory_store = MemoryStore()

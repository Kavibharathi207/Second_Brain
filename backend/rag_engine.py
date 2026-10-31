"""
RAG (Retrieval-Augmented Generation) Pipeline
Combines ChromaDB retrieval with Ollama LLM for intelligent responses.
All public methods accept an optional user_id so results are scoped
to the logged-in user.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from .memory_store import memory_store
from .ollama_service import ollama_service
from .config import config
from .memory_utils import MemoryDecayManager

from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaLLM as Ollama
from langchain_ollama import OllamaEmbeddings

_decay = MemoryDecayManager()


class RAGEngine:
    """Retrieval-Augmented Generation engine for intelligent memory-based responses."""

    def __init__(self):
        self.memory_store   = memory_store
        self.ollama_service = ollama_service
        self.max_context_length = 4000

        self.embeddings = OllamaEmbeddings(
            model=config.OLLAMA_EMBEDDING_MODEL,
            base_url=config.OLLAMA_HOST,
        )
        self.llm = Ollama(
            model=config.OLLAMA_MODEL,
            base_url=config.OLLAMA_HOST,
            temperature=0.7,
        )
        self.vectorstore = Chroma(
            client=self.memory_store.client,
            collection_name=config.CHROMA_COLLECTION_NAME,
            embedding_function=self.embeddings,
        )

    # ── retrieval ─────────────────────────────────────────────────────────────

    def retrieve_relevant_memories(
        self,
        query: str,
        top_k: Optional[int] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if top_k is None:
            top_k = config.RETRIEVAL_TOP_K

        memories = self.memory_store.retrieve_memories(
            query, top_k=top_k, user_id=user_id
        )
        return [
            m for m in memories
            if m.get("distance") is not None
            and m["distance"] <= (1 - config.SIMILARITY_THRESHOLD)
        ]

    def _calculate_importance_score(self, memory: Dict[str, Any]) -> float:
        return _decay.calculate_decay_score(memory)

    def _build_context(self, memories: List[Dict[str, Any]]) -> str:
        if not memories:
            return "No relevant memories found."

        context_parts, context_length = [], 0
        for memory in sorted(
            memories, key=self._calculate_importance_score, reverse=True
        ):
            content   = memory.get("content", "")
            timestamp = memory.get("metadata", {}).get("created_at", "")
            time_str  = f" [Created: {timestamp[:10]}]" if timestamp else ""
            text      = f"• {content}{time_str}"
            if context_length + len(text) > self.max_context_length:
                break
            context_parts.append(text)
            context_length += len(text)

        return "\n".join(context_parts) if context_parts else "No relevant memories found."

    # ── generation ────────────────────────────────────────────────────────────

    def generate_response(
        self,
        query: str,
        memories: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[str] = None,
    ) -> str:
        direct = self._direct_answer(query)
        if direct is not None:
            return direct

        if memories is None:
            memories = self.retrieve_relevant_memories(query, user_id=user_id)

        context  = self._build_context(memories)
        response = self.llm.invoke(self._build_prompt(query, context))

        for m in memories:
            self.memory_store.update_access_count(m["id"])

        return response

    def _build_prompt(self, query: str, context: str) -> str:
        if context.strip() == "No relevant memories found.":
            return (
                "You are a helpful AI assistant. Answer the following question using "
                "your general knowledge. Be concise and accurate (2-4 sentences).\n"
                "If the question is personal (e.g. 'what are my goals'), say you have "
                "no stored memory about it.\n\n"
                f"QUESTION: {query}\n\nANSWER:"
            )
        return (
            "You are a personal memory assistant. Answer using ONLY the memories below.\n\n"
            f"MEMORIES:\n{context}\n\n"
            f"QUESTION: {query}\n\n"
            "RULES:\n"
            "- Answer directly and concisely in 2-4 sentences\n"
            "- Use only information from the memories above\n"
            "- If memories partially answer the question, say so\n"
            "- Do not invent details not present in the memories\n\n"
            "ANSWER:"
        )

    def _direct_answer(self, query: str) -> Optional[str]:
        lower = query.lower().strip()
        if "tomorrow" in lower and "date" in lower:
            return (datetime.now() + timedelta(days=1)).strftime(
                "Tomorrow's date is %B %d, %Y."
            )
        if ("today" in lower and "date" in lower) or "what date is today" in lower:
            return datetime.now().strftime("Today's date is %B %d, %Y.")
        return None

    # ── public API ────────────────────────────────────────────────────────────

    def ask_memory(
        self,
        query: str,
        include_explanation: bool = True,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        direct = self._direct_answer(query)
        if direct is not None:
            return {
                "query": query,
                "response": direct,
                "timestamp": datetime.now().isoformat(),
                "memories_used": 0,
            }

        memories = self.retrieve_relevant_memories(query, user_id=user_id)
        response = self.generate_response(query, memories, user_id=user_id)

        result: Dict[str, Any] = {
            "query": query,
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "memories_used": len(memories),
        }
        if include_explanation and memories:
            result["source_memories"] = [
                {
                    "id": m["id"],
                    "content": m["content"][:200] + ("..." if len(m["content"]) > 200 else ""),
                    "score": self._calculate_importance_score(m),
                }
                for m in memories
            ]
        return result

    def enhance_memory_with_query(self, memory_id: str, query: str) -> Optional[str]:
        memory = self.memory_store.get_memory(memory_id)
        if not memory:
            return None
        prompt = (
            "Given this memory, provide 1-2 sentences of additional context or insight.\n"
            f"Memory: {memory['content']}\nFocus: {query}\nEnhancement:"
        )
        return self.ollama_service.generate(prompt)

    def summarize_memory(self, memory_id: str) -> Optional[str]:
        memory = self.memory_store.get_memory(memory_id)
        if not memory:
            return None
        prompt = (
            "Summarize this note in one short sentence (max 15 words):\n"
            f"{memory['content']}\nSummary:"
        )
        return self.ollama_service.generate(prompt, temperature=0.1)

    def find_related_memories(
        self,
        memory_id: str,
        top_k: int = 3,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        memory = self.memory_store.get_memory(memory_id)
        if not memory:
            return []
        candidates = self.retrieve_relevant_memories(
            memory["content"], top_k=top_k + 1, user_id=user_id
        )
        return [m for m in candidates if m["id"] != memory_id][:top_k]


# Global instance
rag_engine = RAGEngine()

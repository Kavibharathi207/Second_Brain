"""
RAG (Retrieval-Augmented Generation) Pipeline
Combines ChromaDB retrieval with Ollama LLM for intelligent responses
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from .memory_store import memory_store
from .ollama_service import ollama_service
from .config import config
from .memory_utils import MemoryDecayManager

# LangChain imports
from langchain_community.vectorstores import Chroma
from langchain_community.llms import Ollama
from langchain.chains import RetrievalQA
from langchain_community.embeddings import OllamaEmbeddings
from langchain.schema import Document

_decay = MemoryDecayManager()


class RAGEngine:
    """Retrieval-Augmented Generation engine for intelligent memory-based responses"""

    def __init__(self):
        """Initialize the RAG engine"""
        self.memory_store = memory_store
        self.ollama_service = ollama_service
        self.max_context_length = 4000
        
        # LangChain setup
        self.embeddings = OllamaEmbeddings(
            model=config.OLLAMA_EMBEDDING_MODEL,
            base_url=config.OLLAMA_HOST
        )
        self.llm = Ollama(
            model=config.OLLAMA_MODEL,
            base_url=config.OLLAMA_HOST
        )
        
        # Create vectorstore from existing ChromaDB collection
        self.vectorstore = Chroma(
            client=self.memory_store.client,
            collection_name=config.CHROMA_COLLECTION_NAME,
            embedding_function=self.embeddings
        )
        
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.vectorstore.as_retriever(search_kwargs={"k": config.RETRIEVAL_TOP_K}),
            return_source_documents=True
        )

    def retrieve_relevant_memories(
        self,
        query: str,
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant memories for a query
        
        Args:
            query: The user query
            top_k: Number of top results
            
        Returns:
            List of relevant memories
        """
        if top_k is None:
            top_k = config.RETRIEVAL_TOP_K

        memories = self.memory_store.retrieve_memories(query, top_k=top_k)

        # Filter by similarity threshold
        filtered_memories = [
            m for m in memories
            if m.get("distance") is not None and m["distance"] <= (1 - config.SIMILARITY_THRESHOLD)
        ]

        return filtered_memories

    def _calculate_importance_score(self, memory: Dict[str, Any]) -> float:
        """Delegate to MemoryDecayManager for consistent scoring."""
        return _decay.calculate_decay_score(memory)

    def _build_context(self, memories: List[Dict[str, Any]]) -> str:
        """
        Build context string from retrieved memories
        
        Args:
            memories: List of retrieved memories
            
        Returns:
            Formatted context string
        """
        if not memories:
            return "No relevant memories found."

        context_parts = []
        context_length = 0

        # Sort by importance score
        sorted_memories = sorted(
            memories,
            key=lambda m: self._calculate_importance_score(m),
            reverse=True
        )

        for memory in sorted_memories:
            content = memory.get("content", "")
            metadata = memory.get("metadata", {})

            # Add timestamp if available
            timestamp = metadata.get("created_at", "")
            if timestamp:
                time_str = f" [Created: {timestamp[:10]}]"
            else:
                time_str = ""

            memory_text = f"• {content}{time_str}"

            # Check if adding this would exceed length limit
            if context_length + len(memory_text) > self.max_context_length:
                break

            context_parts.append(memory_text)
            context_length += len(memory_text)

        return "\n".join(context_parts) if context_parts else "No relevant memories found."

    def generate_response(
        self,
        query: str,
        memories: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False
    ) -> str:
        """
        Generate a response using RAG pipeline with LangChain
        
        Args:
            query: User query
            memories: Pre-retrieved memories (optional, will retrieve if not provided)
            stream: Whether to stream the response
            
        Returns:
            Generated response
        """
        # Direct answer simple temporal questions without relying on memory retrieval
        direct_answer = self._direct_answer(query)
        if direct_answer is not None:
            return direct_answer

        # Retrieve memories if not provided
        if memories is None:
            memories = self.retrieve_relevant_memories(query)

        # Build context
        context = self._build_context(memories)

        # Use LangChain QA chain
        prompt = self._build_prompt(query, context)
        
        # Create documents from memories
        docs = [Document(page_content=m["content"], metadata=m["metadata"]) for m in memories]
        
        # Add docs to vectorstore temporarily (in-memory)
        temp_vectorstore = Chroma.from_documents(
            documents=docs,
            embedding=self.embeddings,
            collection_name="temp_memories"
        )
        
        qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=temp_vectorstore.as_retriever(search_kwargs={"k": len(memories)}),
            return_source_documents=True
        )
        
        result = qa_chain({"query": prompt})
        response = result["result"]

        # Update access counts for retrieved memories
        for memory in memories:
            self.memory_store.update_access_count(memory["id"])

        return response

    def _build_prompt(self, query: str, context: str) -> str:
        no_memories = context.strip() == "No relevant memories found."

        if no_memories:
            prompt = f"""You are a helpful AI assistant. The user asked: \"{query}\"

No relevant stored memories were found for this query.
Answer accurately and concisely using your general knowledge. If the user is specifically asking about stored memories, explain that you don't have any relevant memory details available.

RESPONSE:"""
        else:
            prompt = f"""You are a personal memory assistant. Answer ONLY using the memories below. Do not add outside knowledge.

MEMORIES:
{context}

QUESTION: {query}

RULES:
- Answer directly and concisely in 2-4 sentences max
- Only use information from the memories above
- If memories don't fully answer the question, say so briefly
- Do not list hypothetical questions or suggestions

ANSWER:"""
        return prompt

    def _direct_answer(self, query: str) -> Optional[str]:
        """Return a precise answer for simple temporal questions."""
        lower = query.lower().strip()

        if "tomorrow" in lower and "date" in lower:
            target = datetime.now() + timedelta(days=1)
            return target.strftime("Tomorrow's date is %B %d, %Y.")

        if ("today" in lower and "date" in lower) or "what date is today" in lower or "what is today's date" in lower:
            target = datetime.now()
            return target.strftime("Today's date is %B %d, %Y.")

        return None

    def ask_memory(
        self,
        query: str,
        include_explanation: bool = True
    ) -> Dict[str, Any]:
        """
        Ask a question to your memory system
        
        Args:
            query: The question to ask
            include_explanation: Include which memories were used
            
        Returns:
            Dictionary with response and metadata
        """
        direct_answer = self._direct_answer(query)
        if direct_answer is not None:
            return {
                "query": query,
                "response": direct_answer,
                "timestamp": datetime.now().isoformat(),
                "memories_used": 0
            }

        # Retrieve relevant memories
        memories = self.retrieve_relevant_memories(query)

        # Generate response
        response = self.generate_response(query, memories)

        result = {
            "query": query,
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "memories_used": len(memories)
        }

        if include_explanation and memories:
            result["source_memories"] = [
                {
                    "id": m["id"],
                    "content": m["content"][:200] + "..." if len(m["content"]) > 200 else m["content"],
                    "score": self._calculate_importance_score(m)
                }
                for m in memories
            ]

        return result

    def enhance_memory_with_query(self, memory_id: str, query: str) -> Optional[str]:
        memory = self.memory_store.get_memory(memory_id)
        if not memory:
            return None
        prompt = (
            f"Given this memory, provide 1-2 sentences of additional context or insight.\n"
            f"Memory: {memory['content']}\nFocus: {query}\nEnhancement:"
        )
        return self.ollama_service.generate(prompt)

    def summarize_memory(self, memory_id: str) -> Optional[str]:
        """Generate a one-line AI summary for a memory."""
        memory = self.memory_store.get_memory(memory_id)
        if not memory:
            return None
        prompt = (
            f"Summarize this note in one short sentence (max 15 words):\n"
            f"{memory['content']}\nSummary:"
        )
        return self.ollama_service.generate(prompt, temperature=0.1)

    def find_related_memories(self, memory_id: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Find semantically related memories for a given memory."""
        memory = self.memory_store.get_memory(memory_id)
        if not memory:
            return []
        candidates = self.retrieve_relevant_memories(memory["content"], top_k=top_k + 1)
        return [m for m in candidates if m["id"] != memory_id][:top_k]


# Global RAG engine instance
rag_engine = RAGEngine()

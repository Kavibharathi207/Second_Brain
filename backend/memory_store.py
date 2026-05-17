"""
Memory storage layer using ChromaDB for vector storage
Handles persistence and retrieval of memories
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
    """Custom embedding function that uses Ollama for embeddings"""
    
    def __init__(self):
        """Initialize with Ollama service"""
        from .ollama_service import OllamaService
        self.ollama = OllamaService()
        self._fallback_dim = 384  # Default embedding dimension
    
    def __call__(self, texts: Documents) -> Embeddings:
        """Generate embeddings for the given texts"""
        embeddings = []
        
        # Check if Ollama is available
        try:
            if not self.ollama.check_connection():
                print("WARNING: Ollama is not running. Using zero embeddings as fallback.")
                return [[0.0] * self._fallback_dim for _ in texts]
        except Exception as e:
            print(f"WARNING: Could not connect to Ollama: {e}. Using fallback embeddings.")
            return [[0.0] * self._fallback_dim for _ in texts]
        
        for text in texts:
            try:
                # Get embedding from Ollama
                embedding = self.ollama.embed(text, model=config.OLLAMA_EMBEDDING_MODEL)
                if embedding:
                    embeddings.append(embedding)
                else:
                    # Fallback: create zero embedding if service fails
                    embeddings.append([0.0] * self._fallback_dim)
            except Exception as e:
                print(f"WARNING: Error generating embedding: {e}. Using fallback.")
                embeddings.append([0.0] * self._fallback_dim)
        
        return embeddings


class MemoryStore:
    """Manages memory storage and retrieval using ChromaDB"""

    def __init__(self):
        """Initialize ChromaDB connection"""
        # Create storage directory if it doesn't exist
        os.makedirs(config.CHROMA_DB_PATH, exist_ok=True)

        # Initialize ChromaDB client (new API - v0.4.13+)
        # Using persistent client instead of deprecated Settings
        self.client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
        
        self.collection = self._get_or_create_collection()

    def _get_or_create_collection(self):
        """Get or create the memories collection"""
        # Use custom Ollama embedding function to avoid onnxruntime dependency
        embedding_function = OllamaEmbeddingFunction()
        
        return self.client.get_or_create_collection(
            name=config.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
            embedding_function=embedding_function
        )
        
        return self.client.get_or_create_collection(
            name=config.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
            embedding_function=embedding_function
        )

    def store_memory(
        self,
        content: str,
        metadata: Dict[str, Any],
        memory_id: Optional[str] = None
    ) -> str:
        """
        Store a memory in the database
        
        Args:
            content: The memory content
            metadata: Metadata associated with the memory
            memory_id: Optional custom ID for the memory
            
        Returns:
            The memory ID
        """
        if memory_id is None:
            memory_id = f"memory_{datetime.now().timestamp()}"

        # Add timestamp if not present
        if "created_at" not in metadata:
            metadata["created_at"] = datetime.now().isoformat()
        
        # Add access count
        if "access_count" not in metadata:
            metadata["access_count"] = 0

        # Add importance score (default to 1.0)
        if "importance" not in metadata:
            metadata["importance"] = 1.0

        # Encrypt content before storage
        encrypted_content = security_manager.encrypt_text(content)

        # Store in ChromaDB
        self.collection.add(
            ids=[memory_id],
            documents=[encrypted_content],
            metadatas=[metadata]
        )

        return memory_id

    def retrieve_memories(
        self,
        query: str,
        top_k: int = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant memories based on semantic similarity
        
        Args:
            query: The query string
            top_k: Number of top results to return
            filters: Optional metadata filters
            
        Returns:
            List of relevant memories with metadata
        """
        if top_k is None:
            top_k = config.RETRIEVAL_TOP_K

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=filters  # Add filter support
            )

            # Format results
            memories = []
            if results and results["ids"] and len(results["ids"]) > 0:
                for i, memory_id in enumerate(results["ids"][0]):
                    encrypted_content = results["documents"][0][i]
                    # Decrypt content
                    try:
                        decrypted_content = security_manager.decrypt_text(encrypted_content)
                    except Exception:
                        decrypted_content = encrypted_content  # Fallback if decryption fails
                    
                    memory = {
                        "id": memory_id,
                        "content": decrypted_content,
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i] if results["distances"] else None
                    }
                    memories.append(memory)

            return memories
        except Exception as e:
            print(f"Error retrieving memories: {str(e)}")
            return []

    def update_memory(
        self,
        memory_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update an existing memory
        
        Args:
            memory_id: The ID of the memory to update
            content: New content (optional)
            metadata: New metadata (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            update_data = {}
            if content:
                encrypted_content = security_manager.encrypt_text(content)
                update_data["documents"] = [encrypted_content]
            if metadata:
                update_data["metadatas"] = [metadata]

            if update_data:
                self.collection.update(
                    ids=[memory_id],
                    **update_data
                )
                return True
            return False
        except Exception as e:
            print(f"Error updating memory: {str(e)}")
            return False

    def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory
        
        Args:
            memory_id: The ID of the memory to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.collection.delete(ids=[memory_id])
            return True
        except Exception as e:
            print(f"Error deleting memory: {str(e)}")
            return False

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific memory by ID
        
        Args:
            memory_id: The memory ID
            
        Returns:
            The memory data or None if not found
        """
        try:
            result = self.collection.get(ids=[memory_id])
            if result and result["ids"]:
                return {
                    "id": memory_id,
                    "content": result["documents"][0],
                    "metadata": result["metadatas"][0]
                }
            return None
        except Exception as e:
            print(f"Error getting memory: {str(e)}")
            return None

    def get_all_memories(self, include_metadata: bool = True) -> List[Dict[str, Any]]:
        """
        Get all memories
        
        Args:
            include_metadata: Whether to include metadata
            
        Returns:
            List of all memories
        """
        try:
            results = self.collection.get(include=["documents", "metadatas"])
            memories = []
            if results and results["ids"]:
                for i, memory_id in enumerate(results["ids"]):
                    encrypted_content = results["documents"][i] if results["documents"] else ""
                    # Decrypt content
                    try:
                        decrypted_content = security_manager.decrypt_text(encrypted_content)
                    except Exception:
                        decrypted_content = encrypted_content  # Fallback
                    
                    memory = {
                        "id": memory_id,
                        "content": decrypted_content,
                        "metadata": results["metadatas"][i] if include_metadata else {}
                    }
                    memories.append(memory)
            return memories
        except Exception as e:
            print(f"Error getting all memories: {str(e)}")
            return []

    def update_access_count(self, memory_id: str) -> bool:
        """Update access count for memory decay calculation"""
        try:
            memory = self.get_memory(memory_id)
            if memory:
                metadata = memory["metadata"]
                metadata["access_count"] = metadata.get("access_count", 0) + 1
                metadata["last_accessed"] = datetime.now().isoformat()
                self.update_memory(memory_id, metadata=metadata)
                return True
            return False
        except Exception as e:
            print(f"Error updating access count: {str(e)}")
            return False

    def clear_all_memories(self) -> bool:
        """Clear all memories - use with caution!"""
        try:
            all_memories = self.get_all_memories(include_metadata=False)
            for memory in all_memories:
                self.delete_memory(memory["id"])
            return True
        except Exception as e:
            print(f"Error clearing memories: {str(e)}")
            return False


# Global memory store instance
memory_store = MemoryStore()

"""
Configuration module for the Second Brain Memory Assistant
"""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration"""

    # Project settings
    PROJECT_NAME = "Second Brain - AI Memory Assistant"
    PROJECT_VERSION = "1.0.0"
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"

    # Ollama Configuration
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
    OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text:latest")

    # ChromaDB Configuration
    CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./backend/storage/chromadb")
    CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "memories")

    # Security Configuration
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "default-insecure-key-change-me")
    SECRET_CODE = os.getenv("SECRET_CODE", "1234")

    # RAG Configuration
    RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "5"))
    SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.3"))

    # Memory Management
    MEMORY_DECAY_ENABLED = os.getenv("MEMORY_DECAY_ENABLED", "True").lower() == "true"
    DECAY_FACTOR = float(os.getenv("DECAY_FACTOR", "0.95"))

    # Application
    APP_HOST = os.getenv("APP_HOST", "localhost")
    APP_PORT = int(os.getenv("APP_PORT", "8501"))


config = Config()

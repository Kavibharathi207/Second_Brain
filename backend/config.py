"""
Configuration — Second Brain Memory Assistant
All tuneable constants live here; never hardcode them elsewhere.
"""

import os
from dotenv import load_dotenv

# Always load .env from the project root (two levels up from this file: backend/ -> project root)
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)  # project root
load_dotenv(os.path.join(_ROOT, ".env"), override=True)


class Config:
    def __init__(self):
        # ── Project ───────────────────────────────────────────────────────────
        self.PROJECT_NAME    = "Second Brain - AI Memory Assistant"
        self.PROJECT_VERSION = "1.0.0"
        self.DEBUG           = os.getenv("DEBUG", "False").lower() == "true"

        # ── Ollama ────────────────────────────────────────────────────────────
        self.OLLAMA_HOST            = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.OLLAMA_MODEL           = os.getenv("OLLAMA_MODEL", "llama3")
        self.OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

        # ── ChromaDB ──────────────────────────────────────────────────────────
        self.CHROMA_DB_PATH         = os.getenv("CHROMA_DB_PATH",         os.path.join(_ROOT, "data", "chroma"))
        self.CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "memories")

        # ── SQLite ────────────────────────────────────────────────────────────
        self.SQLITE_PATH = os.getenv("SQLITE_PATH", os.path.join(_ROOT, "data", "second_brain.db"))

        # ── Security ──────────────────────────────────────────────────────────
        self.ENCRYPTION_KEY            = os.getenv("ENCRYPTION_KEY", "default-insecure-key-change-me")
        self.SECRET_CODE               = os.getenv("SECRET_CODE",    "1234")
        self.SESSION_LOCK_TIMEOUT_MINUTES = int(os.getenv("SESSION_LOCK_TIMEOUT_MINUTES", "30"))
        self.SALT_FILE                 = os.getenv("SALT_FILE",      os.path.join(_ROOT, "data", "salt.bin"))
        self.PBKDF2_ITERATIONS         = int(os.getenv("PBKDF2_ITERATIONS", "390000"))

        # ── RAG ───────────────────────────────────────────────────────────────
        self.RETRIEVAL_TOP_K      = int(os.getenv("RETRIEVAL_TOP_K",      "5"))
        self.SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.3"))
        self.RAG_SEMANTIC_WEIGHT  = float(os.getenv("RAG_SEMANTIC_WEIGHT",  "0.7"))
        self.RAG_PRIORITY_WEIGHT  = float(os.getenv("RAG_PRIORITY_WEIGHT",  "0.3"))

        # ── Memory Decay ──────────────────────────────────────────────────────
        self.HALF_LIFE_HOURS      = float(os.getenv("HALF_LIFE_HOURS",      "168"))
        self.MEMORY_DECAY_ENABLED = os.getenv("MEMORY_DECAY_ENABLED", "True").lower() == "true"
        self.DECAY_FACTOR         = float(os.getenv("DECAY_FACTOR", "0.95"))

        # ── Reminder lifecycle ────────────────────────────────────────────────
        self.DEFAULT_GRACE_PERIOD_HOURS  = int(os.getenv("DEFAULT_GRACE_PERIOD_HOURS",  "24"))
        self.DEFAULT_ARCHIVE_AFTER_HOURS = int(os.getenv("DEFAULT_ARCHIVE_AFTER_HOURS", "72"))

        # ── Scheduler ─────────────────────────────────────────────────────────
        self.DECAY_JOB_INTERVAL_MINUTES      = int(os.getenv("DECAY_JOB_INTERVAL_MINUTES",      "60"))
        self.REMINDER_SWEEP_INTERVAL_MINUTES = int(os.getenv("REMINDER_SWEEP_INTERVAL_MINUTES", "5"))

        # ── Application ───────────────────────────────────────────────────────
        self.APP_HOST = os.getenv("APP_HOST", "localhost")
        self.APP_PORT = int(os.getenv("APP_PORT", "8501"))

    def check_ollama_models(self) -> dict:
        """
        Verify that the configured LLM and embedding models are available.
        Returns a dict with keys 'llm_ok', 'embed_ok', 'available'.
        Never raises — safe to call at startup.
        """
        try:
            import requests as _req
            resp = _req.get(f"{self.OLLAMA_HOST}/api/tags", timeout=5)
            if resp.status_code != 200:
                return {"llm_ok": False, "embed_ok": False, "available": []}
            available = [m["name"] for m in resp.json().get("models", [])]
            base = {m.split(":")[0] for m in available}
            llm_ok   = self.OLLAMA_MODEL   in available or self.OLLAMA_MODEL   in base
            embed_ok = self.OLLAMA_EMBEDDING_MODEL in available or self.OLLAMA_EMBEDDING_MODEL in base
            if not llm_ok:
                print(
                    f"[Config] WARNING: LLM model '{self.OLLAMA_MODEL}' not found. "
                    f"Run: ollama pull {self.OLLAMA_MODEL}"
                )
            if not embed_ok:
                print(
                    f"[Config] WARNING: Embedding model '{self.OLLAMA_EMBEDDING_MODEL}' not found. "
                    f"Run: ollama pull {self.OLLAMA_EMBEDDING_MODEL}"
                )
            return {"llm_ok": llm_ok, "embed_ok": embed_ok, "available": available}
        except Exception:
            return {"llm_ok": False, "embed_ok": False, "available": []}


config = Config()

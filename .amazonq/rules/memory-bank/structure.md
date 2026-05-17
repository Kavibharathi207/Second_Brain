# Project Structure — Memora

## Directory Layout
```
Memora/
├── frontend/
│   └── app.py                  # Streamlit UI — all pages and session state
├── backend/
│   ├── config.py               # Centralized config via Config class + dotenv
│   ├── security.py             # Fernet encryption + secret code auth
│   ├── memory_store.py         # ChromaDB CRUD + embedding via Ollama
│   ├── ollama_service.py       # Ollama HTTP client (chat + embeddings)
│   ├── rag_engine.py           # RAG pipeline: retrieve → build context → generate
│   ├── memory_utils.py         # Decay, tagging, parsing, stats, export/import
│   ├── __init__.py
│   └── storage/chromadb/       # Persisted ChromaDB vector database files
├── docs/
│   ├── API.md
│   ├── ARCHITECTURE.md
│   ├── INSTALLATION.md
│   └── USER_GUIDE.md
├── .env                        # Active environment variables (gitignored)
├── .env.example                # Template for environment setup
├── requirements.txt            # Python dependencies
├── test_system.py              # End-to-end system verification script
├── run_app.bat / run_app.sh    # Launch scripts
└── README.md
```

## Core Components and Relationships

```
frontend/app.py
    └── imports → rag_engine, memory_store, memory_utils, security, config

backend/rag_engine.py
    ├── uses → memory_store (retrieve_memories)
    └── uses → ollama_service (generate, embed)

backend/memory_store.py
    ├── uses → ollama_service (get_embedding)
    └── uses → config (CHROMA_DB_PATH, COLLECTION_NAME, thresholds)

backend/ollama_service.py
    └── uses → config (OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_EMBEDDING_MODEL)

backend/security.py
    └── uses → config (ENCRYPTION_KEY, SECRET_CODE)

backend/memory_utils.py
    └── uses → memory_store (get_all_memories, store_memory)
               config (MEMORY_DECAY_ENABLED, DECAY_FACTOR)
```

## Architectural Patterns

- **Singleton module-level instances**: Each backend module exposes a single global instance (e.g., `config`, `memory_store`, `rag_engine`, `security_manager`, `memory_decay`, `memory_stats`). Consumers import the instance directly, not the class.
- **Layered architecture**: UI → RAG Engine → Memory Store / Ollama Service → ChromaDB / Ollama
- **RAG pipeline**: Query → embed → ChromaDB similarity search → rank by importance + recency → build prompt context → Ollama LLM → response with source memories
- **Separation of concerns**: Utility logic (decay, parsing, stats, export) isolated in `memory_utils.py`; storage in `memory_store.py`; LLM calls in `ollama_service.py`
- **Environment-driven config**: All tuneable parameters (model, thresholds, decay factor, ports) read from `.env` via `python-dotenv`; defaults baked into `Config` class

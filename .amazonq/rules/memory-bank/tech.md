# Technology Stack — Memora

## Language
- Python 3.8+

## Frontend
- **Streamlit ≥1.32.0** — single-file UI (`frontend/app.py`), session state for auth and conversation history

## AI / LLM
- **Ollama ≥0.6.0** — local LLM runtime; default model `mistral` (configurable to llama3.1, neural-chat, etc.)
- **nomic-embed-text** — Ollama embedding model for semantic vector generation
- **LangChain ≥0.1.0** + **langchain-community ≥0.0.10** — prompt templating and chain utilities
- **sentence-transformers ≥2.2.0** — fallback/supplementary embedding support

## Vector Database
- **ChromaDB ≥0.4.0** — local persistent vector store at `./backend/storage/chromadb`; collection name `memories`

## Security
- **cryptography ≥41.0.0** — Fernet (AES-256-CBC + HMAC) symmetric encryption for stored data

## Data / Utilities
- **pydantic ≥2.5.0** — data validation and settings models
- **python-dotenv ≥1.0.0** — `.env` file loading into `os.getenv`
- **numpy ≥1.24.0** — vector math for similarity scoring
- **pandas ≥2.0.0** — analytics and tabular data in dashboard
- **pyyaml ≥6.0.0** — YAML config support
- **requests ≥2.31.0** — HTTP calls to Ollama REST API

## Key Configuration (`.env`)
| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `mistral` | LLM model name |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text:latest` | Embedding model |
| `CHROMA_DB_PATH` | `./backend/storage/chromadb` | Vector DB path |
| `SECRET_CODE` | `1234` | UI access code |
| `ENCRYPTION_KEY` | *(must change)* | Fernet key for encryption |
| `RETRIEVAL_TOP_K` | `5` | Memories retrieved per query |
| `SIMILARITY_THRESHOLD` | `0.3` | Min cosine similarity to include |
| `DECAY_FACTOR` | `0.95` | Memory importance decay rate |

## Development Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Start Ollama (separate terminal)
ollama run mistral

# Verify system
python test_system.py

# Run app
streamlit run frontend/app.py

# Reset vector DB
rm -rf backend/storage/chromadb   # Linux/macOS
rmdir /s /q backend\storage\chromadb  # Windows

# Generate new Fernet encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key())"
```

## External Dependencies (Runtime)
- Ollama must be running locally before starting the app
- No internet required after initial model download

# 🧠 Second Brain — AI-Powered Personal Memory Assistant

A full-stack, local-first personal memory assistant that stores journal/notes/tasks/meeting-log entries, retrieves them with RAG, simulates human-like memory decay, and proactively reminds you of detected future tasks — automatically clearing reminders once completed or expired.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Streamlit UI  (app.py)                     │
│  Dashboard · Add Memory · Ask AI · Reminders · Analytics    │
├─────────────────────────────────────────────────────────────┤
│              RAG Engine  (core/rag_engine → backend)        │
│   Embed query → Retrieve chunks → Re-rank → LLM generate   │
├──────────────────────────┬──────────────────────────────────┤
│  ChromaDB  (vector store)│  SQLite  (metadata + reminders)  │
│  core/vector_store.py    │  core/models.py + db/database.py │
├──────────────────────────┴──────────────────────────────────┤
│  Ollama  (llama3 + nomic-embed-text)  — fully local         │
├─────────────────────────────────────────────────────────────┤
│  APScheduler  — decay_job (60 min) · reminder_sweep (5 min) │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Folder Structure

```
second_brain/
├── app.py                      # Entry point — streamlit run app.py
├── config.py / backend/config.py
├── core/
│   ├── ingestion.py            # NLP: clean, summarise, time/intent/tone, chunk+embed
│   ├── encryption.py           # Re-export of backend/security (PBKDF2 + Fernet)
│   ├── vector_store.py         # ChromaDB client — add_chunks / query + bump_access
│   ├── rag_engine.py           # Retrieval + combined scoring + Ollama generation
│   ├── decay_engine.py         # Exponential decay math + APScheduler job
│   ├── reminder_engine.py      # Status lifecycle + sweep job + user actions
│   └── models.py               # SQLAlchemy: Memory, Reminder
├── db/
│   └── database.py             # SQLite engine / session / init_db
├── backend/
│   ├── config.py               # All tuneable constants
│   ├── security.py             # AES-256 Fernet, PBKDF2HMAC key derivation
│   ├── memory_store.py         # ChromaDB legacy wrapper (used by frontend)
│   ├── ollama_service.py       # Ollama HTTP client
│   ├── rag_engine.py           # RAG pipeline (LangChain + Ollama)
│   └── memory_utils.py         # Decay, parser, stats, export/import
├── frontend/
│   └── app.py                  # Streamlit pages
├── tests/
│   ├── test_decay_engine.py
│   ├── test_reminder_engine.py
│   └── test_rag_engine.py
├── data/                       # Auto-created: chroma/, second_brain.db, salt.bin
├── .env
├── requirements.txt
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.ai) installed

### 1 — Install

```bash
cd Memora
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2 — Pull models & start Ollama

```bash
ollama pull llama3
ollama pull nomic-embed-text
ollama serve          # keep this terminal open
```

### 3 — Configure

Edit `.env` — at minimum change `SECRET_CODE` and `ENCRYPTION_KEY`:

```env
SECRET_CODE=your-secret
ENCRYPTION_KEY=your-passphrase
OLLAMA_MODEL=llama3
```

Generate a strong encryption key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 4 — Run

```bash
streamlit run app.py
```

Open `http://localhost:8501` — enter your secret code to unlock protected sections.

### 5 — Run tests

```bash
python tests/test_decay_engine.py
python tests/test_reminder_engine.py
python tests/test_rag_engine.py
```

---

## 🧮 Memory Decay Formula

Memories are **never deleted** for low score — only deprioritised in ranking and visually faded in the UI.

### Recency factor (exponential decay)

```
R(t) = e^(-λ · Δt)

  Δt = hours since last_accessed_at
  λ  = ln(2) / HALF_LIFE_HOURS        (default HALF_LIFE_HOURS = 168 = 7 days)
```

A memory's recency factor **halves every 7 days** of disuse.

### Frequency factor (diminishing returns)

```
F = log(1 + access_count)
```

100 accesses is not 100× more important than 1 — logarithmic scaling prevents gaming.

### Final priority score

```
priority_score        = importance × R(t) × F
normalized_score      = priority_score / max_priority_score_in_corpus   → [0, 1]
```

### RAG combined ranking score

```
final_score = 0.7 × semantic_similarity + 0.3 × normalized_priority_score
```

A highly relevant but heavily decayed memory ranks below a moderately relevant, high-priority one.

### bump_access (on every read)

```
last_accessed_at = now   →  Δt resets to 0  →  R(t) → 1.0
access_count    += 1     →  F increases
priority_score   = recomputed and cached
```

---

## ⏰ Reminder Lifecycle

```
                    ┌─────────────────────────────────────────┐
                    │              PENDING                    │
                    │  (visible in active reminders list)     │
                    └──────┬──────────────┬───────────────────┘
                           │              │
              user marks   │              │  now > due_at
              complete     │              │  + grace_period_hours
                           ▼              ▼
                    ┌──────────┐   ┌──────────┐
                    │COMPLETED │   │  MISSED  │
                    │(hidden   │   │(hidden   │
                    │from list)│   │from list)│
                    └────┬─────┘   └────┬─────┘
                         │              │
          now > completed_at            │  now > due_at
          + archive_after_hours         │  + grace + archive
                         │              │
                         ▼              ▼
                    ┌─────────────────────────┐
                    │   HARD DELETED by sweep  │
                    │   (APScheduler, 5 min)   │
                    └─────────────────────────┘

User actions on PENDING:
  ✅ Mark complete  → status = completed  (disappears from list immediately)
  💤 Snooze        → due_at pushed forward, stays pending
  ✕  Dismiss       → status = missed     (skips grace period)
```

Default timings (configurable in `.env`):

| Setting | Default | Meaning |
|---|---|---|
| `DEFAULT_GRACE_PERIOD_HOURS` | 24 | Hours after due_at before → missed |
| `DEFAULT_ARCHIVE_AFTER_HOURS` | 72 | Hours after completion/missed before hard-delete |

---

## ⚙️ Configuration (`.env`)

```env
# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# Storage
CHROMA_DB_PATH=./data/chroma
SQLITE_PATH=./data/second_brain.db

# Security
SECRET_CODE=1234
ENCRYPTION_KEY=your-passphrase
SALT_FILE=./data/salt.bin
PBKDF2_ITERATIONS=390000

# RAG
RETRIEVAL_TOP_K=5
SIMILARITY_THRESHOLD=0.3
RAG_SEMANTIC_WEIGHT=0.7
RAG_PRIORITY_WEIGHT=0.3

# Decay
HALF_LIFE_HOURS=168
MEMORY_DECAY_ENABLED=True

# Reminder lifecycle
DEFAULT_GRACE_PERIOD_HOURS=24
DEFAULT_ARCHIVE_AFTER_HOURS=72

# Scheduler
DECAY_JOB_INTERVAL_MINUTES=60
REMINDER_SWEEP_INTERVAL_MINUTES=5
```

---

## 🔐 Security

- **AES-256 encryption** via Fernet — all memory content encrypted before touching SQLite or ChromaDB metadata
- **PBKDF2HMAC** (SHA-256, 390,000 iterations) derives the Fernet key from your passphrase
- **Random salt** stored in `./data/salt.bin` — never hardcoded
- **Embeddings are not encrypted** — they are lossy vectors that cannot be reversed into original text
- Without the correct passphrase, decryption fails and content stays unreadable

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---|---|
| Ollama not running | `ollama serve` in a separate terminal |
| Model not found | `ollama pull llama3 && ollama pull nomic-embed-text` |
| ChromaDB errors | Delete `./data/chroma/` and restart |
| Slow responses | Use `OLLAMA_MODEL=mistral` or reduce `RETRIEVAL_TOP_K` |
| Wrong secret code | Check `SECRET_CODE` in `.env` |

---

## 📊 System Requirements

| Component | Requirement |
|---|---|
| Python | 3.11+ |
| RAM | 8 GB+ recommended (4 GB minimum) |
| Storage | 5 GB for models + data |
| Ollama | Latest version |
| Internet | Only for initial model download |

---

## ✅ Deliverable Checklist

- [x] `streamlit run app.py` starts the full app
- [x] Notes/tasks encrypted at rest; passphrase required to decrypt
- [x] RAG answers grounded in stored memories, ranked by `0.7×semantic + 0.3×priority`
- [x] Priority score decays exponentially (`e^(-λΔt)`) and rises on access
- [x] "Submit report next week" auto-creates a pending reminder with parsed due date
- [x] Marking a reminder complete removes it from the active list immediately
- [x] Background sweep flips overdue → missed and hard-deletes past archive window
- [x] APScheduler runs `decay_job` (60 min) and `reminder_sweep` (5 min)
- [x] Tests: `test_decay_engine.py`, `test_reminder_engine.py`, `test_rag_engine.py`

---

**🧠 Your data, your device, your second brain.**

# 🧠 Second Brain - AI Powered Personal Memory Assistant

An intelligent, privacy-first personal memory assistant that understands context, retrieves information using semantic intelligence, and acts proactively. Built with Ollama (Llama 3.1), ChromaDB, and Streamlit.

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

## ✨ Key Features

### 🧠 Smart Memory Management
- **Semantic Search**: Find memories by meaning, not keywords
- **Memory Decay**: Simulates human forgetting with importance scoring
- **Automatic Tagging**: #tag-based organization
- **Smart Prioritization**: Frequently accessed memories stay important

### 🤖 RAG-Powered Intelligence
- **Retrieval-Augmented Generation**: Uses your own memories as knowledge base
- **Context-Aware Responses**: AI understands your personal context
- **Zero Hallucination**: Answers based on actual stored memories
- **Personalized Insights**: Tailored to your specific information

### 🔐 Privacy-First Security
- **Local-First Architecture**: No cloud dependency
- **AES-256 Encryption**: Secure data storage
- **Secret Code Protection**: Access control via authentication
- **Offline Operation**: Full functionality without internet

### 🎯 Intelligent Features
- **Proactive Reminders**: System detects deadlines and intentions
- **Conversation History**: Track your discussions with the system
- **Memory Statistics**: Analyze your memories and patterns
- **Advanced Analytics**: Visualize memory importance and tags

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────┐
│          Streamlit Frontend (UI Layer)              │
├─────────────────────────────────────────────────────┤
│  • Dashboard    • Add Memory    • Ask Memory         │
│  • Analytics    • Settings      • Conversation       │
├─────────────────────────────────────────────────────┤
│          RAG Engine (Intelligence Layer)            │
│  ┌──────────────────────────────────────────────┐   │
│  │ Retrieval  │  Context Building  │ Generation │   │
│  └──────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────┤
│  ChromaDB (Vector DB) │ Ollama (Local LLM)          │
│  Memory Storage       │ Llama 3.1 Model             │
├─────────────────────────────────────────────────────┤
│  Security Layer (Encryption & Access Control)       │
└─────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- [Ollama](https://ollama.ai) installed and running
- 4GB+ RAM recommended

### Installation

1. **Clone or Download the project**
```bash
cd Memora
```

2. **Create a Python virtual environment** (optional but recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Start Ollama** (in a separate terminal)
```bash
# Download and run Llama 3.1
ollama run llama2

# Or use another model
ollama run mistral
ollama run neural-chat
```

5. **Verify system setup**
```bash
python test_system.py
```

6. **Run the application**
```bash
streamlit run frontend/app.py
```

7. **Access the app**
   - Open your browser to `http://localhost:8501`
   - Default secret code: `1234`
   - Change it in `.env` file for production!

## 📖 Usage Guide

### Adding Memories
1. Click **➕ Add Memory** in the sidebar
2. Write your memory with optional #tags
3. Set importance level
4. Click **💾 Save Memory**

**Tips:**
- Use #tags for automatic categorization
- Include dates and deadlines
- Be specific and detailed
- System extracts importance from keywords

### Asking Your Memory
1. Click **🔍 Ask Memory** 
2. Ask a question about your memories
3. System retrieves relevant memories
4. AI generates personalized response
5. Source memories shown for reference

**Example Queries:**
- "What meetings do I have next week?"
- "What are my project deadlines?"
- "Remind me about my 2024 goals"
- "What did I learn about Python?"

### Understanding Memory Decay
The system automatically calculates importance:
```
Importance Score = Base Importance × Recency × Access Frequency

- Frequently accessed memories stay important
- Rarely used memories gradually fade
- Old but important memories can be revived by access
- Manual importance level influences scoring
```

### Analytics & Statistics
- **Dashboard**: Overview of your memories
- **Analytics Tab**: Visual analysis of memory patterns
- **Tag Analysis**: See your most-used categories
- **Importance Distribution**: Understand what matters most

## ⚙️ Configuration

Edit `.env` file to customize:

```env
# Ollama Settings
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama2  # Change to mistral, neural-chat, etc.
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# Security (CHANGE IN PRODUCTION!)
SECRET_CODE=1234
ENCRYPTION_KEY=your-secure-key-here

# RAG Settings
RETRIEVAL_TOP_K=5  # Number of memories to retrieve
SIMILARITY_THRESHOLD=0.3  # How similar memories must be

# Memory Management
MEMORY_DECAY_ENABLED=True
DECAY_FACTOR=0.95  # Higher = slower decay
```

## 🔧 Project Structure

```
Memora/
├── frontend/
│   └── app.py                    # Streamlit UI
├── backend/
│   ├── config.py                 # Configuration management
│   ├── security.py               # Encryption & auth
│   ├── memory_store.py           # ChromaDB integration
│   ├── ollama_service.py         # Ollama client
│   ├── rag_engine.py             # RAG pipeline
│   ├── memory_utils.py           # Memory utilities
│   └── storage/                  # Vector database
├── docs/                         # Documentation
├── .env                          # Environment variables
├── requirements.txt              # Python dependencies
├── test_system.py               # System verification
└── README.md                     # This file
```

## 📚 API Reference

### Memory Store
```python
from backend.memory_store import memory_store

# Store a memory
memory_id = memory_store.store_memory(
    content="My memory content",
    metadata={"importance": 0.8, "tags": ["tag1", "tag2"]}
)

# Retrieve by query
memories = memory_store.retrieve_memories("query", top_k=5)

# Get specific memory
memory = memory_store.get_memory(memory_id)

# Update memory
memory_store.update_memory(memory_id, content="Updated content")

# Delete memory
memory_store.delete_memory(memory_id)
```

### RAG Engine
```python
from backend.rag_engine import rag_engine

# Ask a question
result = rag_engine.ask_memory(
    query="What are my goals?",
    include_explanation=True
)
# Returns: {
#   "query": "...",
#   "response": "AI-generated answer",
#   "source_memories": [...],
#   "timestamp": "...",
#   "memories_used": 3
# }

# Generate response with custom memories
response = rag_engine.generate_response(query, memories=retrieved_memories)
```

### Security
```python
from backend.security import security_manager

# Encrypt data
encrypted = security_manager.encrypt_data({"key": "value"})

# Decrypt data
decrypted = security_manager.decrypt_data(encrypted)

# Verify secret code
if security_manager.verify_secret_code("1234"):
    print("Access granted")
```

## 🎓 How RAG Works in Second Brain

1. **User Query** → "What's my project deadline?" 
2. **Embedding** → Convert to semantic vector
3. **Retrieval** → Search ChromaDB for similar memories
4. **Context Building** → Rank and format relevant memories
5. **Prompt Construction** → Combine query + context
6. **Generation** → Ollama LLM generates response
7. **Response** → Personalized answer with sources

## 🔐 Security Best Practices

1. **Change the Secret Code**
   - Edit `.env` file: `SECRET_CODE=your-code`
   - Use strong, memorable codes

2. **Secure Encryption Key**
   - Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key())"`
   - Update `.env`: `ENCRYPTION_KEY=your-generated-key`

3. **Privacy Considerations**
   - All data stored locally (no cloud uploads)
   - Use strong OS-level security
   - Back up important memories manually
   - Keep Ollama locally secured

## 🛠️ Troubleshooting

### Ollama Connection Error
```bash
# Check if Ollama is running
ollama serve

# Or in another terminal
ollama run llama2
```

### ChromaDB Issues
```bash
# Clear database and start fresh
rm -rf backend/storage/chromadb
```

### Memory Not Found
- Refine your query (be more specific)
- Check similarity threshold in `.env`
- Ensure memories are actually stored in dashboard

### Slow Responses
- Reduce `RETRIEVAL_TOP_K` in `.env`
- Use smaller model (neural-chat instead of llama2)
- Check system RAM availability

## 📊 System Requirements

| Component | Requirement |
|-----------|------------|
| Python | 3.8+ |
| RAM | 4GB minimum, 8GB+ recommended |
| Storage | 5GB for models + memory |
| Ollama | Latest version |
| Internet | Only for initial setup |

## 🚀 Advanced Usage

### Custom RAG Pipelines
```python
from backend.rag_engine import rag_engine

# Filter by importance
important = rag_engine.retrieve_relevant_memories(
    query="my query",
    top_k=10
)
filtered = [m for m in important if m["metadata"]["importance"] > 0.7]
```

### Memory Analytics
```python
from backend.memory_utils import memory_stats, memory_decay

# Get statistics
stats = memory_stats.get_statistics()
print(f"Total memories: {stats['total_memories']}")
print(f"Top tags: {stats['tags']}")

# Find important memories
important = memory_decay.get_important_memories(min_score=0.8)
```

### Batch Operations
```python
from backend.memory_store import memory_store

# Get all memories
all_memories = memory_store.get_all_memories()

# Process all
for memory in all_memories:
    content = memory["content"]
    # Your processing here
```

## 🔄 Development

### Running Tests
```bash
python test_system.py
```

### Development Mode
```bash
# With debug output
DEBUG=True streamlit run frontend/app.py

# With logging
python -u frontend/app.py 2>&1
```
## 📝 Roadmap

### 🔄 Currently In Progress
- [ ] Proactive Reminders — auto-detect deadlines and intentions from stored memories
- [ ] Streamlit UI — Dashboard, Add Memory, Ask Memory, Analytics, Settings pages

### 📌 Planned
- [ ] Web interface with REST API
- [ ] Mobile app support
- [ ] Voice input/output
- [ ] Scheduled automatic backups
- [ ] Memory export/import
- [ ] Multi-user support
- [ ] Advanced memory relationships
- [ ] Custom embedding models
- [ ] Performance metrics dashboard

### ✅ Completed
- [x] ChromaDB vector store integration
- [x] Ollama LLM service
- [x] RAG pipeline
- [x] AES-256 encryption & access control
- [x] Memory decay scoring
- [x] Semantic search
- [x] Automatic tagging
- [x] Backend API layer


## 🤝 Contributing

Contributions welcome! Priority areas right now:
1. **Proactive Reminders** — deadline/intention detection logic
2. **Streamlit UI** — clean, intuitive pages for all features
3. Performance optimization
4. Additional Ollama model support
5. Documentation improvements

## 📄 License

MIT License - Feel free to use this project for personal and commercial purposes.

## ⚠️ Disclaimer

- This is for personal use. Back up important data regularly.
- No guarantee of data protection. Implement additional security as needed.
- Performance depends on your hardware and chosen Ollama model.
- Privacy depends on proper system configuration and security practices.

## 📞 Support

For issues and questions:
1. Check the Troubleshooting section
2. Review the API Reference
3. Run `test_system.py` to diagnose
4. Check `.env` configuration

## 🎯 Key Innovations

✅ **RAG-Based Personal Memory** — Your own data, not generic AI  
✅ **Cognitive Memory Decay** — Mimics human forgetting  
✅ **Privacy-First** — No cloud, fully encrypted  
🔄 **Proactive Intelligence** — Auto-detects intentions *(in progress)*  
✅ **Semantic Search** — Find by meaning, not keywords

---

**🧠 Transform your personal data into actionable knowledge. Second Brain understands, prioritizes, and assists like a true digital companion.**

**Made with ❤️ for better memory and productivity**

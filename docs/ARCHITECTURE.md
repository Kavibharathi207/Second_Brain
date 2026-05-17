# System Requirements & Architecture

## 🏗️ System Architecture

### Three-Pillar Architecture

#### 1. Input Layer (Memory Ingestion)
- **Data Sources**: Notes, Journal entries, Tasks, Meetings logs
- **Processing**: NLP-based extraction of context, time references, emotional tone
- **Storage**: Encrypted local storage in ChromaDB

#### 2. Core Intelligence Layer (RAG + Memory Management)

**A. Retrieval-Augmented Generation (RAG)**
```
User Query
    ↓
Semantic Embedding (using Ollama embeddings)
    ↓
ChromaDB Similarity Search
    ↓
Ranked Results (top-k with similarity threshold)
    ↓
Context Building
    ↓
Prompt Construction
    ↓
Ollama LLM Generation
    ↓
Personalized Response
```

**B. Cognitive Memory Decay**
```
Priority Score = Importance × Recency × Access Frequency

- Base Importance: User-set + auto-detected from content
- Recency Factor: exp(-days_old / 30)
- Access Frequency: 1 + (access_count × 0.05)

Result: Frequently used → stays important
        Rarely used → gradually deprioritized
```

**C. Proactive Intelligence**
- Deadline detection from text
- Automatic tagging with #hashtags
- Importance calculation from keywords
- Context preservation for better retrieval

**D. Security Layer**
- AES-256 encryption for sensitive data
- Secret code authentication
- Encrypted memory storage
- Access control and audit trails

#### 3. Output Layer (Interaction & Storage)

**Storage Backend**:
- ChromaDB: Vector database for semantic search
- Local filesystem: Persistent encrypted database
- No external cloud dependencies

**Interaction Methods**:
- Streamlit UI: Web-based interface
- API responses: Structured JSON outputs
- Conversation history: Session-based tracking

## 📊 Data Flow Diagram

```
┌──────────────┐
│  User Input  │
│ (Text/Voice) │
└──────┬───────┘
       │
       ↓
┌──────────────────────────────────────┐
│  Security & Authentication Layer     │
│  - Verify secret code                │
│  - Encryption/Decryption             │
└──────┬───────────────────────────────┘
       │
       ├─→ Storage Flow        ├─→ Query Flow
       │                       │
       ↓                       ↓
┌─────────────────┐    ┌──────────────────┐
│ Extract Context │    │ Convert to Vector│
│ Tagging         │    │ (Embeddings)     │
│ Parsing         │    └────────┬─────────┘
└────────┬────────┘             │
         │                      ↓
         │            ┌────────────────────┐
         │            │ ChromaDB Search    │
         ↓            │ Similarity Check   │
┌─────────────────┐   └────────┬───────────┘
│ Store to        │            │
│ ChromaDB        │            ↓
│ (Encrypted)     │   ┌──────────────────┐
└────────┬────────┘   │ Rank Results     │
         │            │ Calculate Scores │
         │            └────────┬─────────┘
         │                     │
         │                     ↓
         │            ┌──────────────────┐
         │            │ Build Context    │
         │            │ Format Memories  │
         │            └────────┬─────────┘
         │                     │
         └─→──────────────────→│
                              │
                              ↓
                     ┌──────────────────┐
                     │ Ollama LLM       │
                     │ (Llama 3.1)      │
                     │ RAG Prompt       │
                     └────────┬─────────┘
                              │
                              ↓
                     ┌──────────────────┐
                     │ Generate Response│
                     │ Personalized AI  │
                     └────────┬─────────┘
                              │
                              ↓
                     ┌──────────────────┐
                     │ Update Metrics   │
                     │ (Access count,   │
                     │  Decay scores)   │
                     └────────┬─────────┘
                              │
                              ↓
                     ┌──────────────────┐
                     │ Display Response │
                     │ & Source Memories│
                     └──────────────────┘
```

## 🔐 Security Architecture

### Encryption Strategy
- **Algorithm**: AES-256 (Fernet)
- **Key Derivation**: PBKDF2
- **Data Encrypted**: All memory content at rest
- **Authentication**: Secret code verification

### Security Layers
```
Application Layer
│
├─→ Session Authentication
│   (Secret code verification)
│
├─→ Data Encryption
│   (In-memory encrypted data)
│
└─→ Storage Encryption
    (Database-level encryption)

File System Layer
│
└─→ OS-level file permissions
    (User-owned files/directories)
```

## 🧠 Memory Decay Algorithm

### Importance Score Calculation

```python
def calculate_importance(memory):
    # Base importance (0.0 - 1.0)
    base = memory.importance  # User-set value
    
    # Recency factor (exponential decay)
    days_old = (now - created_date).days
    recency = decay_factor ^ (days_old / 30)
    
    # Access frequency boost
    access_count = memory.access_count
    frequency = 1.0 + (access_count * 0.05)
    
    # Final score
    return base * recency * frequency

# Example:
# - Created today, importance=0.8, accessed 5 times
#   Score = 0.8 * 1.0 * 1.25 = 1.0
#
# - Created 30 days ago, importance=0.8, accessed 0 times
#   Score = 0.8 * 0.95 * 1.0 = 0.76
#
# - Created 60 days ago, importance=0.8, accessed 0 times
#   Score = 0.8 * 0.90 * 1.0 = 0.72
```

## 🤖 RAG Pipeline Details

### Retrieval Process
1. **Query Encoding**: Convert user query to embedding vector
2. **Similarity Search**: Find closest memory vectors in ChromaDB
3. **Filtering**: Remove results below similarity threshold
4. **Ranking**: Sort by importance score × similarity
5. **Context Window**: Select top-K for RAG context

### Generation Process
```
Retrieved Memories + User Query
             ↓
   Prompt Template:
   "You are a personal memory assistant.
    
    KNOWN FACTS:
    [Retrieved Memories]
    
    QUESTION: [User Query]
    
    Answer based on your knowledge:"
             ↓
   Ollama/Llama 3.1
             ↓
   Generated Response
```

### Quality Metrics
- **Relevance**: Semantic similarity of retrieved memories
- **Specificity**: Mentions actual memory content
- **Accuracy**: No hallucination (uses only retrieved data)
- **Personalization**: References user's specific context

## 📈 Performance Characteristics

### Memory Retrieval
- **Complexity**: O(log n) with vector indexing
- **Avg Time**: <100ms for typical databases
- **Scalability**: Handles 100k+ memories efficiently

### Response Generation
- **Model Latency**: 2-10 seconds (depends on Ollama model)
- **Context Limits**: ~4000 tokens per prompt
- **Max Memories**: 5-10 per query for best results

### Storage Overhead
- **Per Memory**: ~1KB metadata + variable content
- **Database**: ~500MB for 50k memories
- **Model Size**: ~4-7GB for Llama models

## 🔄 System Workflow

### New Memory Addition
```
1. User enters memory in UI
2. Extract tags (#hashtags)
3. Calculate initial importance (0.5-1.0)
4. Generate embeddings
5. Encrypt content
6. Store in ChromaDB
7. Update search index
8. Confirm to user
```

### Memory Query Resolution
```
1. User asks question
2. Verify authentication
3. Generate query embeddings
4. Search ChromaDB (similarity search)
5. Apply decay factors
6. Compute importance scores
7. Select top-K results
8. Build context string
9. Construct RAG prompt
10. Call Ollama/Llama
11. Stream/return response
12. Update access metrics
13. Log conversation
```

### Periodic Maintenance
```
Every 24 hours:
- Recalculate all importance scores
- Apply memory decay factors
- Clean up deprecated memories
- Optimize database indexes
- Generate statistics

Every 7 days:
- Backup memory database
- Analyze memory patterns
- Generate analytics reports
```

## 🛠️ Implementation Details

### Technologies

| Component | Technology | Reason |
|-----------|-----------|--------|
| Vector DB | ChromaDB | Semantic search, JSON metadata |
| Embeddings | Ollama | Local embeddings, privacy |
| LLM | Ollama + Llama | Local execution, no API keys |
| Frontend | Streamlit | Rapid UI development, no frontend skills needed |
| Encryption | cryptography | Battle-tested, standards-based |
| Config | python-dotenv | Environment-based configuration |

### Database Schema

**Memories Collection:**
```json
{
  "id": "memory_1712345678.9",
  "embedding": [0.1, 0.2, ...],  // 384-dim vector
  "content": "My memory text...",
  "metadata": {
    "created_at": "2024-04-05T10:30:00",
    "last_accessed": "2024-04-06T14:15:00",
    "access_count": 3,
    "importance": 0.75,
    "tags": ["work", "project"],
    "type": "manual"
  }
}
```

### Configuration Hierarchy
```
1. Environment Variables (.env file)
2. Config class defaults
3. Runtime overrides
4. User settings in UI

(Later sources override earlier ones)
```

## 🚀 Scalability Considerations

### Horizontal Scaling
- Multiple Ollama instances (load balancer)
- ChromaDB cluster mode (future)
- Distributed embeddings

### Vertical Scaling
- Increase RAM for larger models
- GPU acceleration (CUDA for Ollama)
- Database optimization

### Optimization Strategies
- Memory pruning (remove low-importance old memories)
- Batch processing for decay calculation
- Caching for frequent queries
- Async processing for embeddings

## 📚 References

- ChromaDB: https://www.trychroma.com/
- Ollama: https://ollama.ai
- Llamaindex/LangChain RAG: https://www.langchain.com/
- FAISS for vector search: https://github.com/facebookresearch/faiss
- Streamlit: https://streamlit.io/

---

**Document Version**: 1.0.0
**Last Updated**: 2024-04
**Status**: Complete

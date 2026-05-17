# API Documentation

## Overview

Second Brain provides a Python API for advanced users wanting to automate operations or integrate with external systems.

## Core Modules

### 1. Memory Store API

#### Import
```python
from backend.memory_store import memory_store
```

#### Store Memory
```python
memory_id = memory_store.store_memory(
    content: str,                    # The memory content
    metadata: Dict[str, Any],        # Additional metadata
    memory_id: Optional[str] = None  # Custom ID (auto-generated if None)
) -> str
```

**Example:**
```python
memory_id = memory_store.store_memory(
    content="I learned about RAG systems today",
    metadata={
        "importance": 0.9,
        "tags": ["learning", "ml"],
        "source": "tutorial"
    }
)
print(f"Stored memory: {memory_id}")
```

#### Retrieve Memories
```python
memories = memory_store.retrieve_memories(
    query: str,                      # Search query
    top_k: Optional[int] = None,     # Number of results
    filters: Optional[Dict] = None   # Metadata filters
) -> List[Dict[str, Any]]
```

**Example:**
```python
memories = memory_store.retrieve_memories(
    query="What did I learn about machine learning?",
    top_k=5
)

for memory in memories:
    print(f"Content: {memory['content']}")
    print(f"Score: {memory['distance']}")
```

#### Get Specific Memory
```python
memory = memory_store.get_memory(
    memory_id: str
) -> Optional[Dict[str, Any]]
```

**Example:**
```python
memory = memory_store.get_memory("memory_1712345678.9")
if memory:
    print(memory['content'])
    print(memory['metadata'])
```

#### Update Memory
```python
success = memory_store.update_memory(
    memory_id: str,
    content: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> bool
```

**Example:**
```python
memory_store.update_memory(
    memory_id="memory_1234",
    metadata={
        "importance": 0.95,
        "tags": ["work", "urgent"]
    }
)
```

#### Delete Memory
```python
success = memory_store.delete_memory(
    memory_id: str
) -> bool
```

#### Get All Memories
```python
all_memories = memory_store.get_all_memories(
    include_metadata: bool = True
) -> List[Dict[str, Any]]
```

---

### 2. RAG Engine API

#### Import
```python
from backend.rag_engine import rag_engine
```

#### Ask Memory
```python
result = rag_engine.ask_memory(
    query: str,
    include_explanation: bool = True
) -> Dict[str, Any]
```

**Returns:**
```python
{
    "query": "user question",
    "response": "AI-generated answer",
    "timestamp": "2024-04-05T10:30:00",
    "memories_used": 3,
    "source_memories": [
        {
            "id": "memory_1234",
            "content": "memory excerpt",
            "score": 0.85
        }
    ]
}
```

**Example:**
```python
result = rag_engine.ask_memory(
    query="What are my project deadlines?"
)
print(result['response'])
for source in result['source_memories']:
    print(f"Source: {source['content']} (Score: {source['score']})")
```

#### Retrieve Relevant Memories
```python
memories = rag_engine.retrieve_relevant_memories(
    query: str,
    top_k: Optional[int] = None
) -> List[Dict[str, Any]]
```

#### Generate Response
```python
response = rag_engine.generate_response(
    query: str,
    memories: Optional[List[Dict]] = None,
    stream: bool = False
) -> str
```

---

### 3. Ollama Service API

#### Import
```python
from backend.ollama_service import ollama_service
```

#### Check Connection
```python
is_running = ollama_service.check_connection() -> bool
```

#### List Available Models
```python
models = ollama_service.list_models() -> list
```

**Example:**
```python
if ollama_service.check_connection():
    print("Ollama is running")
    models = ollama_service.list_models()
    print(f"Available models: {models}")
```

#### Generate Text
```python
response = ollama_service.generate(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    top_p: float = 0.9,
    top_k: int = 40,
    stream: bool = False
) -> str
```

**Example:**
```python
response = ollama_service.generate(
    prompt="Explain quantum computing in simple terms",
    temperature=0.7
)
print(response)
```

#### Generate Embeddings
```python
embedding = ollama_service.embed(
    text: str,
    model: Optional[str] = None
) -> Optional[list]
```

#### Chat
```python
response = ollama_service.chat(
    messages: list,  # [{"role": "user", "content": "..."}]
    model: Optional[str] = None,
    temperature: float = 0.7
) -> str
```

---

### 4. Security API

#### Import
```python
from backend.security import security_manager
```

#### Encrypt Data
```python
encrypted = security_manager.encrypt_data(
    data: Dict[str, Any]
) -> str
```

#### Decrypt Data
```python
decrypted = security_manager.decrypt_data(
    encrypted_data: str
) -> Dict[str, Any]
```

#### Verify Secret Code
```python
is_valid = security_manager.verify_secret_code(
    provided_code: str
) -> bool
```

**Example:**
```python
if security_manager.verify_secret_code("1234"):
    print("Access granted")
```

---

### 5. Memory Utilities API

#### Import
```python
from backend.memory_utils import (
    memory_decay,
    memory_parser,
    memory_stats
)
```

#### Memory Decay
```python
# Calculate decay score
score = memory_decay.calculate_decay_score(memory)

# Get important memories
important = memory_decay.get_important_memories(min_score=0.7)

# Update all scores
memory_decay.update_all_importance_scores()
```

#### Memory Parser
```python
# Extract tags
tags = memory_parser.extract_tags(content)

# Extract deadlines
deadlines = memory_parser.extract_deadlines(content)

# Calculate importance
importance = memory_parser.calculate_content_importance(content)
```

#### Memory Statistics
```python
stats = memory_stats.get_statistics()
# Returns:
# {
#     "total_memories": 42,
#     "total_characters": 15234,
#     "average_length": 362,
#     "tags": {"work": 5, "learning": 3, ...},
#     "creation_date_range": {"oldest": "...", "newest": "..."}
# }
```

---

## Configuration

#### Import Config
```python
from backend.config import config
```

#### Available Settings
```python
config.OLLAMA_HOST              # Ollama server URL
config.OLLAMA_MODEL             # Current LLM model
config.CHROMA_DB_PATH           # Database location
config.RETRIEVAL_TOP_K          # Memories per query
config.SIMILARITY_THRESHOLD     # Minimum similarity
config.MEMORY_DECAY_ENABLED     # Enable decay
config.DECAY_FACTOR             # Decay speed
config.SECRET_CODE              # Access code
config.ENCRYPTION_KEY           # Security key
```

---

## Complete Examples

### Example 1: Batch Import Memories

```python
from backend.memory_store import memory_store
from backend.memory_utils import memory_parser

# Import from list
memories_list = [
    "I attended a Python workshop today #learning",
    "Deadline for project report is April 15 #work",
    "Started learning machine learning #ml #learning"
]

for content in memories_list:
    tags = memory_parser.extract_tags(content)
    importance = memory_parser.calculate_content_importance(content)
    
    memory_store.store_memory(
        content=content,
        metadata={
            "importance": importance,
            "tags": tags,
            "source": "batch_import"
        }
    )
    print(f"Imported: {content[:40]}...")
```

### Example 2: Advanced Analysis

```python
from backend.memory_store import memory_store
from backend.memory_utils import memory_decay, memory_stats

# Get statistics
stats = memory_stats.get_statistics()
print(f"Total memories: {stats['total_memories']}")
print(f"Most used tags: {sorted(stats['tags'].items(), key=lambda x: x[1], reverse=True)[:5]}")

# Find important memories
important = memory_decay.get_important_memories(min_score=0.8)
print(f"\nImportant memories (score >= 0.8): {len(important)}")

for memory in important[:5]:
    score = memory_decay.calculate_decay_score(memory)
    print(f"- {memory['content'][:50]}... (Score: {score:.2f})")
```

### Example 3: Health Check

```python
from backend.ollama_service import ollama_service
from backend.memory_store import memory_store
from backend.config import config

def system_health():
    """Check system health"""
    status = {
        "ollama": ollama_service.check_connection(),
        "database": len(memory_store.get_all_memories()),
        "models": ollama_service.list_models(),
        "config": {
            "model": config.OLLAMA_MODEL,
            "decay_enabled": config.MEMORY_DECAY_ENABLED,
            "retrieval_k": config.RETRIEVAL_TOP_K
        }
    }
    return status

health = system_health()
print(health)
```

### Example 4: Automated Memory Decay

```python
from backend.memory_utils import memory_decay
from backend.memory_store import memory_store

# Run decay update
print("Updating memory importance scores...")
memory_decay.update_all_importance_scores()

# Get memories by importance
for importance_level in ["High", "Medium", "Low"]:
    if importance_level == "High":
        memories = memory_decay.get_important_memories(min_score=0.7)
    elif importance_level == "Medium":
        all_mems = memory_store.get_all_memories()
        memories = [m for m in all_mems 
                   if memory_decay.calculate_decay_score(m) > 0.4 
                   and memory_decay.calculate_decay_score(m) <= 0.7]
    else:
        all_mems = memory_store.get_all_memories()
        memories = [m for m in all_mems 
                   if memory_decay.calculate_decay_score(m) <= 0.4]
    
    print(f"{importance_level} Priority: {len(memories)} memories")
```

---

## Error Handling

### Common Exceptions

```python
try:
    memory = memory_store.get_memory("invalid_id")
except Exception as e:
    print(f"Error: {e}")

try:
    decrypted = security_manager.decrypt_data("bad_data")
except ValueError as e:
    print(f"Decryption error: {e}")

try:
    response = ollama_service.generate("prompt")
except ConnectionError:
    print("Ollama connection failed")
```

---

## Performance Tips

1. **Batch Operations**
   ```python
   # Good: Batch retrieval
   memories = memory_store.retrieve_memories(query, top_k=10)
   
   # Avoid: Multiple single retrievals in loop
   for query in queries:
       mem = memory_store.retrieve_memories(query, top_k=1)
   ```

2. **Limit Results**
   ```python
   # Good: Limit top-k
   memories = memory_store.retrieve_memories(query, top_k=5)
   
   # Avoid: Getting all memories
   all_memories = memory_store.get_all_memories()
   ```

3. **Cache Connections**
   ```python
   # Reuse service instances
   from backend.ollama_service import ollama_service
   
   # Good: Use global instance
   response1 = ollama_service.generate("prompt1")
   response2 = ollama_service.generate("prompt2")
   ```

---

## Pagination & Filtering

### Retrieve with Filters
```python
# Get memories by tags
memories = memory_store.retrieve_memories(
    query="my query",
    filters={"tags": {"$contains": "work"}}
)
```

### Manual Pagination
```python
all_memories = memory_store.get_all_memories()

# Page 1: 0-10
page1 = all_memories[0:10]

# Page 2: 10-20
page2 = all_memories[10:20]
```

---

## Version Information

- **API Version**: 1.0.0
- **Last Updated**: April 2024
- **Compatibility**: Python 3.8+

---

For more information, see [ARCHITECTURE.md](./ARCHITECTURE.md) and [USER_GUIDE.md](./USER_GUIDE.md).

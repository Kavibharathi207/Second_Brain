# Development Guidelines — Memora

## Code Quality Standards

### Module Structure (all 5 files follow this)
- Every module starts with a triple-quoted docstring describing its purpose
- Imports ordered: stdlib → third-party → local (relative)
- Relative imports used for all intra-backend imports: `from .config import config`
- Frontend uses absolute path injection: `sys.path.insert(0, ...)` then `from backend.X import x`

### Singleton Pattern (universal across all backend modules)
Every backend module exposes exactly one module-level instance. Consumers import the instance, never the class:
```python
# At bottom of every backend file:
memory_store = MemoryStore()
rag_engine = RAGEngine()
security_manager = SecurityManager()
memory_decay = MemoryDecayManager()
```
Never instantiate these classes directly in consuming code — always import the singleton.

### Type Annotations (all backend methods)
All public methods use full type hints with `typing` imports:
```python
from typing import List, Dict, Any, Optional

def retrieve_memories(self, query: str, top_k: int = None, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
```

### Docstrings (backend classes and public methods)
Classes and public methods use Google-style docstrings with Args/Returns sections:
```python
def store_memory(self, content: str, metadata: Dict[str, Any], memory_id: Optional[str] = None) -> str:
    """
    Store a memory in the database
    
    Args:
        content: The memory content
        metadata: Metadata associated with the memory
        memory_id: Optional custom ID for the memory
        
    Returns:
        The memory ID
    """
```
Utility/private methods use single-line docstrings.

### Error Handling Pattern (memory_store.py, security.py — 100% consistent)
All storage/IO operations wrapped in try/except; errors printed, safe default returned:
```python
try:
    result = self.collection.query(...)
    return formatted_result
except Exception as e:
    print(f"Error retrieving memories: {str(e)}")
    return []   # or False, or None depending on return type
```
Never raise exceptions from storage methods — always return empty/False/None.
Security methods are the exception: they raise `ValueError` with descriptive messages.

### Fallback / Graceful Degradation (memory_store.py, app.py)
All external service calls (Ollama, ChromaDB) have explicit fallbacks:
```python
try:
    decrypted_content = security_manager.decrypt_text(encrypted_content)
except Exception:
    decrypted_content = encrypted_content  # Fallback if decryption fails
```
Embedding failures fall back to zero vectors of fixed dimension (384).

---

## Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Classes | PascalCase | `MemoryStore`, `RAGEngine`, `SecurityManager` |
| Module-level singletons | snake_case | `memory_store`, `rag_engine`, `security_manager` |
| Methods | snake_case | `store_memory`, `retrieve_memories`, `get_all_memories` |
| Private helpers | leading underscore | `_get_cipher`, `_build_context`, `_build_prompt` |
| Constants / keyword lists | UPPER_SNAKE_CASE | `POSITIVE`, `NEGATIVE`, `URGENT`, `REMINDER_KEYWORDS` |
| Config fields | UPPER_SNAKE_CASE | `OLLAMA_MODEL`, `RETRIEVAL_TOP_K` |
| Memory IDs | `f"memory_{datetime.now().timestamp()}"` | timestamp-based string |

---

## Memory Data Schema
All memories stored and passed as dicts with this consistent shape:
```python
{
    "id": "memory_1234567890.123",
    "content": "<decrypted plain text>",   # always decrypted before returning
    "metadata": {
        "importance": 0.8,                 # float 0.0–1.0
        "tags": ["tag1", "tag2"],          # list of strings
        "priority": "high",                # "high" | "medium" | "low"
        "memory_type": "Task",             # "Task" | "Knowledge" | "Personal" | "Event"
        "created_at": "2024-01-15T10:30:00",  # ISO format string
        "access_count": 0,                 # int, incremented on retrieval
        "last_accessed": "...",            # ISO format, set by update_access_count
        "type": "auto"                     # "auto" | "manual"
    },
    "distance": 0.15                       # cosine distance from query (retrieve only)
}
```

---

## Architectural Patterns

### Config Access
Always access config via the singleton, never `os.getenv` directly in business logic:
```python
from .config import config
top_k = config.RETRIEVAL_TOP_K
```

### Encryption Boundary
Content is encrypted at write time in `memory_store.store_memory` and decrypted at read time in `retrieve_memories` / `get_all_memories`. All other layers work with plaintext. Never encrypt/decrypt outside `memory_store.py`.

### Importance Scoring Delegation
`RAGEngine._calculate_importance_score` delegates entirely to `MemoryDecayManager.calculate_decay_score` — do not duplicate decay logic:
```python
_decay = MemoryDecayManager()

def _calculate_importance_score(self, memory: Dict[str, Any]) -> float:
    return _decay.calculate_decay_score(memory)
```

### Streamlit Session State
All mutable UI state lives in `st.session_state`. Initialize with defaults in `init_state()` using the pattern:
```python
defaults = {"page": "Dashboard", "conversation": [], "reminders": []}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v
```

### Streamlit Caching
Backend calls that are expensive or repeated use `@st.cache_data(ttl=N)`. Cache is busted explicitly after writes:
```python
@st.cache_data(ttl=30)
def get_all_memories_cached():
    return memory_store.get_all_memories()

def bust_memory_cache():
    get_all_memories_cached.clear()
    get_stats_cached.clear()
```
Always call `bust_memory_cache()` after any `store_memory` or `delete_memory` call.

### Security Gate Pattern
Protected pages call `security_gate(section_name)` at the top and return early if it returns False:
```python
def add_memory_page():
    if not security_gate("Add Memory"):
        return
    # ... rest of page
```

---

## UI / Frontend Conventions (app.py)

- All custom styling via a single `st.markdown("""<style>...</style>""", unsafe_allow_html=True)` block at module load
- Color palette: primary `#6366F1` (indigo), accent `#7C3AED` (violet), background `#F0F4FF`
- Cards rendered as inline HTML strings via `st.markdown(..., unsafe_allow_html=True)` — CSS classes: `metric-card`, `memory-tag-card`, `memory-full-card`, `reminder-card`
- Priority color mapping used consistently across all pages:
  ```python
  pri_bg = {"high": "#FEE2E2", "medium": "#FEF3C7", "low": "#D1FAE5"}.get(pri, "#EDE9FE")
  pri_fg = {"high": "#DC2626", "medium": "#D97706", "low": "#059669"}.get(pri, "#6366F1")
  ```
- Navigation via `go(page)` helper which resets auth state on page change
- Emoji used consistently for page icons and status indicators (🟢/🔴 for Ollama status)

---

## Testing Conventions (test_system.py)

- Each test is a standalone function `test_X()` returning `bool`
- Tests print emoji-prefixed status lines: `✅` pass, `❌` fail, `⚠️` warning
- Tests clean up after themselves (delete any stored test memories)
- Conditional test execution: skip dependent tests if prerequisites fail
- Entry point collects results in a dict and prints a summary table

---

## Common Pitfalls to Avoid

- Do NOT call `MemoryStore()`, `RAGEngine()`, etc. directly — always import the singleton
- Do NOT access `os.getenv` in business logic — use `config.*`
- Do NOT encrypt/decrypt content outside `memory_store.py`
- Do NOT duplicate decay scoring logic — delegate to `MemoryDecayManager`
- Always call `bust_memory_cache()` after any write to memory store
- ChromaDB metadata values must be scalar (str, int, float, bool) — convert lists to strings if needed, or store as JSON string

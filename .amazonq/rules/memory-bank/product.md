# Product Overview — Memora (Second Brain)

## Purpose
Memora is a privacy-first, AI-powered personal memory assistant that stores, retrieves, and reasons over user-written memories using local LLMs and semantic search. It acts as a "second brain" — helping users recall information, detect deadlines, and surface insights from their own data without any cloud dependency.

## Value Proposition
- All data stays local: no cloud uploads, no third-party data sharing
- Semantic search finds memories by meaning, not exact keywords
- RAG pipeline grounds AI responses in the user's actual stored memories (zero hallucination)
- Cognitive memory decay mimics human forgetting, keeping important memories surfaced

## Key Features
- **Semantic Memory Storage**: Memories stored as vector embeddings in ChromaDB
- **RAG-Powered Q&A**: Ask natural language questions; AI answers using retrieved memories as context
- **Memory Decay**: Importance scores decay over time; frequently accessed memories stay relevant
- **Automatic Tagging**: `#tag` extraction from memory content
- **Deadline Detection**: Parses relative ("tomorrow", "next week") and absolute dates from content
- **Emotional Tone Detection**: Classifies memories as positive / negative / urgent / neutral
- **AES-256 Encryption**: All stored data encrypted via Fernet symmetric encryption
- **Secret Code Auth**: Simple access control via configurable secret code
- **Analytics Dashboard**: Tag frequency, importance distribution, tone breakdown, memory statistics
- **Export/Import**: JSON-based memory backup and restore

## Target Users
- Individuals who want a personal knowledge base without cloud privacy concerns
- People managing tasks, deadlines, goals, and notes in one place
- Users who want AI assistance grounded in their own personal context

## Use Cases
- "What meetings do I have next week?" → retrieves calendar-like memories
- "What are my project deadlines?" → deadline extraction + RAG response
- "What did I learn about Python?" → semantic search over learning notes
- Proactive reminders for upcoming deadlines detected in stored memories

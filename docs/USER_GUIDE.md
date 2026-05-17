# User Guide - Second Brain Memory Assistant

## 🎯 Getting Started

### Your First Login
1. Open the app: http://localhost:8501
2. Enter the default secret code: **1234**
3. Click "🔓 Unlock"
4. Welcome to your digital memory!

## 📝 Adding Memories

### Basic Memory Creation
1. Go to **➕ Add Memory**
2. Write your memory in the text area
3. Adjust the importance slider (0.0 - 1.0)
4. Click **💾 Save Memory**

### Memory Format Tips
```
Good Memory Entry:
"I need to submit the Q2 report by April 15th. 
The report includes analytics from #projects 
and #financial sections."

The system will:
- Extract tags: project, financial
- Auto-detect importance from keywords "need", "submit", "deadline"
- Store with your chosen importance level
- Calculate semantic meaning for future retrieval
```

### Using Tags
- Use `#hashtag` format in your memory
- Example: "Meeting with #John about #project deadline"
- Extracted tags: john, project
- Browse all tags in Dashboard

### Importance Scoring
- **0.0 - 0.3**: Low priority (reference, nice to know)
- **0.3 - 0.7**: Medium priority (regular tasks, information)
- **0.7 - 1.0**: High priority (critical, urgent, important)

The system also auto-scores based on keywords:
- **Boost words**: important, urgent, critical, deadline, must, essential
- **Reduce words**: maybe, optional, could, consider, might

## 🔍 Asking Your Memory

### How to Ask Effective Questions
```
Good questions:
"What tasks do I have this week?"
"Tell me about my Python learning journey"
"What did I learn about machine learning?"
"Who should I contact for the marketing project?"
"What are my health goals?"

Less effective:
"Tell me everything" (too vague)
"Something" (unclear)
"xyz" (no semantic meaning)
```

### Understanding Responses
1. **Response**: AI-generated answer based on your memories
2. **Source Memories**: The actual memories used to answer
3. **Scores**: Importance score (relevance to question)

### Conversation History
- All your questions are saved
- View chat history anytime
- Review how memory system evolves
- Track what you've learned

## 📊 Dashboard Overview

### Key Metrics
- **Total Memories**: Count of all stored memories
- **Total Characters**: Words/content volume
- **Average Length**: Typical memory size
- **Unique Tags**: Number of used categories

### Important Memories
- Displayed by importance score
- Top 5 are shown
- Color-coded for better visibility
- Click to see more details

### Top Tags
- Most frequently used tags
- Shows usage count
- Click tag to filter memories
- Helps organize your knowledge

## 📈 Analytics Page

### Memory Distribution
- Visual chart of memory importance
- Average vs max importance
- Helps identify priorities

### Tag Analysis
- Bar chart of tag frequencies
- Most used categories highlighted
- Identify knowledge areas

### Memory Decay
- Shows how memories "fade"
- Frequently accessed memories stay important
- Old, unused memories deprioritize
- Learn about your knowledge patterns

## ⚙️ Settings

### Ollama Configuration
- Shows current model
- Check connection status
- View available models

### System Settings
- Database location
- Collection name
- Decay settings

### Security
- Change secret code (requires editing .env)
- View current security settings
- Manage access control

## 🤖 Memory Decay Explained

### What is Memory Decay?
Like human memory, Second Brain gradually deprioritizes old memories that aren't accessed.

### The Formula
```
Importance = Base Importance × Recency × Access Frequency

Example:
Created today: 1.0 (fresh)
Created 30 days ago: ~0.95 (slightly aged)
Created 60 days ago: ~0.90 (older)

BUT: If accessed frequently, stays high!
Accessed once: +5%
Accessed 5 times: +25%
```

### Why This Matters
- Old important memories are revived by use
- Truly unimportant memories fade naturally
- Your memory stays relevant and focused
- Mimics human cognitive patterns

### Controlling Decay
Edit `.env`:
```env
MEMORY_DECAY_ENABLED=True      # Enable/disable
DECAY_FACTOR=0.95              # Higher = slower decay
```

## 💾 Managing Memories

### Viewing Memory Details
1. Go to **🔍 Ask Memory**
2. Ask a question
3. Click expand button on source memory
4. See full content

### Deleting Memories
1. Ask a question that retrieves the memory
2. Click **🗑️ Delete Memory** button
3. Memory is permanently removed
4. (Cannot be undone!)

### Editing Memories
Currently, edit requires:
1. Delete the memory
2. Create a new one with updated content

(Direct edit coming in v1.1)

## 🔐 Privacy & Security

### Your Data is:
- ✅ Stored locally (no cloud)
- ✅ Encrypted at rest (AES-256)
- ✅ Protected by secret code
- ✅ Never sent to external servers

### Best Practices
1. **Change Default Secret Code**
   - Edit `.env` file
   - Use strong, memorable code
   - Don't share with others

2. **Secure Your Computer**
   - Use OS-level encryption
   - Enable firewall
   - Keep OS updated

3. **Back Up Memories**
   - Periodically copy `backend/storage/chromadb` folder
   - Store backups securely
   - Test restore process

4. **Encryption Key**
   - Use generated key instead of default
   - Store securely
   - Don't share or expose

## 🎓 Advanced Tips

### Memory Organization Strategy
```
Personal Memory Structure:

#work - Job-related memories
#projects - Active projects
#learning - Educational content
#health - Fitness/wellness
#personal - Life events
#ideas - Brainstorms
#contacts - Important people
#deadlines - Time-sensitive items
```

### Query Optimization
```
Instead of: "Tell me about stuff"
Try: "What are my current projects?"

Instead of: "Memories"
Try: "What did I learn about Python?"

Instead of: "Everything"
Try: "Summarize my April activities"
```

### Using Memory Decay Productively
1. **Active Review**: Frequently access important memories
2. **Spring Cleaning**: Let old trivial memories fade
3. **Refresh**: Re-access old important memories
4. **Iterate**: Update memories with new information

## 🔧 Troubleshooting

### Memory not appearing in search?
- The memory might be too old (low importance)
- Query might not be semantically similar
- Check tags and content
- Try different phrasing

### Response seems irrelevant?
- Refine your question to be more specific
- Check if memories actually relate to question
- Increase RETRIEVAL_TOP_K in .env
- Ensure Ollama is responsive

### Forgot secret code?
- Edit `.env` file
- Add new code: `SECRET_CODE=newcode`
- Restart application
- (Stored memories remain encrypted)

### Memories disappearing?
- Check you haven't cleared all memories
- Verify database directory exists
- Check `.env` CHROMA_DB_PATH setting
- Restore from backup if available

## 📱 Integration Ideas

### External Data Sources
```python
# Example: Import emails
for email in email_inbox:
    memory_store.store_memory(
        content=email.body,
        metadata={"source": "email", "tags": ["inbox"]}
    )

# Example: Import meeting notes
for note in meeting_notes:
    memory_store.store_memory(
        content=note.text,
        metadata={"source": "meeting", "tags": ["work"]}
    )
```

### Automation Possibilities
- Auto-import calendar events as memories
- Integrate with note-taking apps
- Voice note transcription
- Email integration
- Task management system

## 🎯 Best Practices Summary

1. **Be Specific**: Detailed memories = better retrieval
2. **Use Tags**: Organize with consistent #hashtags
3. **Set Importance**: Help system prioritize
4. **Review Regularly**: Keep decay algorithm working
5. **Ask Questions**: Test and improve RAG system
6. **Backup Often**: Never lose important data
7. **Refine Queries**: Learn what works best
8. **Share Knowledge**: Document discoveries

## 📚 Common Patterns

### Daily Review
```
Morning:
1. Ask "What's my agenda today?"
2. Check important deadlines
3. Review top priorities

Evening:
1. Add daily memories
2. Tag with #daily
3. Update importance for tomorrow
```

### Weekly Planning
```
Monday:
1. Ask "What's my workload this week?"
2. Identify deadlines
3. Plan priorities

Friday:
1. Review what was accomplished
2. Clean up completed tasks
3. Plan next week
```

### Monthly Analysis
```
Month-end:
1. Run analytics
2. Review tag distribution
3. Check decay patterns
4. Plan next month
5. Backup memories
```

## 🚀 Power User Features

### Batch Operations (Python)
```python
from backend.memory_store import memory_store

# Get all memories
all_memories = memory_store.get_all_memories()

# Filter by tag
tagged = [m for m in all_memories 
          if 'work' in m['metadata'].get('tags', [])]

# For analysis
for memory in tagged:
    print(f"Content: {memory['content']}")
    print(f"Importance: {memory['metadata']['importance']}")
```

### Advanced Queries
```python
from backend.rag_engine import rag_engine

# Multi-memory analysis
result = rag_engine.ask_memory(
    query="Compare my Python and JavaScript learnings",
    include_explanation=True
)

print(result['response'])
```

---

**User Guide Version**: 1.0
**Last Updated**: April 2024
**Questions?**: Check ARCHITECTURE.md for technical details

# 🚀 QUICK START - 5 Minute Setup

## ⚠️ If You Have Installation Issues

**Run the automated fix script first:**

### Windows:
```bash
fix_system.bat
```

### macOS/Linux:
```bash
bash fix_system.sh
```

This will fix all known compatibility issues automatically.

---

## Prerequisites
- [Ollama](https://ollama.ai) installed
- Python 3.8+ installed
- 1-2 GB free RAM minimum
- Git (optional)

## ⚡ Recommended Models

| Model | Memory | Speed | Recommended For |
|-------|--------|-------|-----------------|
| **Mistral** | 1.5GB | Medium | Best quality/speed balance ✅ |
| **Neural-Chat** | 1.4GB | Fast | Fast responses |
| **Orca-Mini** | 1GB | Fastest | Very limited RAM |
| ~~Llama2~~ | ~~2.3GB~~ | ~~Slow~~ | ~~Not recommended~~ |

**Start with Mistral or Neural-Chat** for best experience.

## Step 1: Start Ollama (Terminal 1)

### First Time: Download Model

Choose one based on your RAM:

**Option A: Mistral (RECOMMENDED)**
```bash
ollama pull mistral
ollama run mistral
```

**Option B: Neural-Chat (FAST)**
```bash
ollama pull neural-chat
ollama run neural-chat
```

**Option C: Orca-Mini (Smallest)**
```bash
ollama pull orca-mini
ollama run orca-mini
```

**Keep this terminal open!** It provides the AI for memory queries.

## Step 2: Install Dependencies (Terminal 2)
```bash
cd Memora
pip install -r requirements.txt
```

## Step 3: Update Configuration (Terminal 2)

Edit `.env` and set the model you chose:

```env
# If you chose Mistral:
OLLAMA_MODEL=mistral

# If you chose Neural-Chat:
OLLAMA_MODEL=neural-chat

# If you chose Orca-Mini:
OLLAMA_MODEL=orca-mini
```

## Step 4: Verify Setup
```bash
python test_system.py
```

You should see checkmarks (✅) for all tests:
- ✅ Ollama Connection
- ✅ Security (Encryption)
- ✅ Memory Store (ChromaDB)
- ✅ RAG Pipeline

## Step 5: Run Application
```bash
streamlit run frontend/app.py
```
The app will open automatically at `http://localhost:8501`

## Step 6: Login & Start Using
- **Secret Code**: `1234` (change this later!)
- Create your first memory
- Ask a question to test RAG
- Explore the dashboard

## 🎯 First Actions
1. **Add Memory**: Click "➕ Add Memory" → Write something → Click "💾 Save"
2. **Ask Question**: Click "🔍 Ask Memory" → Ask about your memory → See AI response
3. **View Analytics**: Click "📊 Analytics" → Explore your memories
4. **Change Settings**: Click "⚙️ Settings" → Review configuration

## ⚠️ Important

✅ **Ollama must be running** (Terminal 1) before using the app
✅ Default secret code is `1234` - change it for production
✅ All data stored locally and encrypted
✅ No internet needed after setup
✅ If you get errors, run `fix_system.bat` (Windows) or `bash fix_system.sh` (macOS/Linux)

## 🆘 Troubleshooting

### "Model requires more memory than available"
→ Use a smaller model (Mistral or Neural-Chat instead of Llama2)

### "Deprecated configuration" error
→ Run `fix_system.bat` (Windows) to fix ChromaDB API

### "Cannot import PBKDF2" error
→ Run `fix_system.bat` (Windows) to fix cryptography imports

### "ModuleNotFoundError"
→ Make sure you're in the Memora directory and ran `pip install -r requirements.txt`

For more help → See [FIXES.md](./FIXES.md)

## 📚 Need Help?
- **Getting Started**: Read [QUICKSTART.md](./QUICKSTART.md) (this file)
- **Installation Issues**: Read [FIXES.md](./FIXES.md)
- **Full Setup Guide**: Read [docs/INSTALLATION.md](./docs/INSTALLATION.md)
- **How to Use**: Read [docs/USER_GUIDE.md](./docs/USER_GUIDE.md)
- **Technical Details**: Read [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)
- **Developer API**: Read [docs/API.md](./docs/API.md)

## 🎉 That's It!

You now have a working AI memory system. Enjoy! 🧠

---

**Quick Links:**
- **Auto-Fix Errors**: Run `fix_system.bat` (Windows) or `bash fix_system.sh` (macOS/Linux)
- **Detailed Setup**: See [docs/INSTALLATION.md](./docs/INSTALLATION.md)
- **Usage Guide**: See [docs/USER_GUIDE.md](./docs/USER_GUIDE.md)
- **Troubleshooting**: See [FIXES.md](./FIXES.md)

# 🔧 Fix Guide - Installation & Runtime Issues

## Issue 1: Ollama Memory Error ❌

**Error Message:**
```
model requires more system memory (2.3 GiB) than is available (1.1 GiB)
```

**Cause:** Your system has limited RAM. Llama2 requires 2.3GB but you only have 1.1GB available.

**Solution:** Use a smaller, more memory-efficient model instead.

### ✅ Recommended Smaller Models

**Best Options (ranked by speed/size):**

1. **Mistral** (7B) - Recommended ⭐
   ```bash
   ollama pull mistral
   ollama run mistral
   ```
   - Size: ~5GB
   - Memory: ~1.5GB
   - Speed: Fast
   - Quality: Good

2. **Neural-Chat** (7B)
   ```bash
   ollama pull neural-chat
   ollama run neural-chat
   ```
   - Size: ~4.8GB
   - Memory: ~1.4GB
   - Speed: Very Fast
   - Quality: Good for conversations

3. **Orca-Mini** (3B)
   ```bash
   ollama pull orca-mini
   ollama run orca-mini
   ```
   - Size: ~2GB
   - Memory: ~1GB
   - Speed: Fastest
   - Quality: Decent for small system

### Update .env File

Edit `.env` and change:
```env
OLLAMA_MODEL=mistral
```

Or use:
```env
OLLAMA_MODEL=neural-chat
```

Or:
```env
OLLAMA_MODEL=orca-mini
```

---

## Issue 2: ChromaDB Deprecated API ❌

**Error Message:**
```
ValueError: You are using a deprecated configuration of Chroma.
```

**Cause:** ChromaDB API changed in version 0.4.13+

**Solution:** ✅ Already fixed in updated `memory_store.py`

The code now uses the new PersistentClient API:
```python
self.client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
```

---

## Issue 3: Cryptography Import Error ❌

**Error Message:**
```
ImportError: cannot import name 'PBKDF2' from 'cryptography.hazmat.primitives.kdf.pbkdf2'
```

**Cause:** Cryptography library API changed, PBKDF2 is no longer needed for Fernet

**Solution:** ✅ Already fixed in updated `security.py`

The code now uses SHA256 hashing directly:
```python
from cryptography.hazmat.primitives import hashes
digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
```

---

## 📋 Steps to Fix Your Installation

### Step 1: Update Python Packages
```bash
cd C:\Users\kavib\OneDrive\Desktop\Memora

# Clear old packages (optional but recommended)
pip uninstall -y chromadb langchain langchain-community langchain-core ollama

# Reinstall with corrected versions
pip install --upgrade -r requirements.txt
```

### Step 2: Clean Old Database
```bash
# Remove old ChromaDB (if exists)
rmdir /s backend\storage\chromadb
```

### Step 3: Download Model

Remove Llama2 and download a smaller model:

**Option A: Mistral (RECOMMENDED)**
```bash
ollama rm llama2
ollama pull mistral
ollama run mistral
```

**Option B: Neural-Chat**
```bash
ollama rm llama2
ollama pull neural-chat
ollama run neural-chat
```

**Option C: Orca-Mini (Smallest)**
```bash
ollama rm llama2
ollama pull orca-mini
ollama run orca-mini
```

**Keep the Ollama terminal running!**

### Step 4: Update Configuration

Edit `.env`:
```env
# Change from:
OLLAMA_MODEL=llama2

# To one of:
OLLAMA_MODEL=mistral
# OR
OLLAMA_MODEL=neural-chat
# OR
OLLAMA_MODEL=orca-mini
```

### Step 5: Verify System

```bash
python test_system.py
```

You should see all ✅ checkmarks.

### Step 6: Run Application

```bash
streamlit run frontend/app.py
```

Open: http://localhost:8501
Secret Code: 1234

---

## 🎯 Which Model to Choose?

| Model | RAM | Speed | Quality | Size |
|-------|-----|-------|---------|------|
| **Mistral** | 1.5GB | Medium | Good | 5GB |
| **Neural-Chat** | 1.4GB | Fast | Good | 4.8GB |
| **Orca-Mini** | 1GB | Fastest | Fair | 2GB |
| ~~Llama2~~ | ~~2.3GB~~ | ~~Slow~~ | ~~Best~~ | ~~4GB~~ |

**Recommendation:** Start with **Mistral** for best balance, or **Neural-Chat** if you need speed.

---

## ⚡ Quick Fix Summary

```powershell
# Terminal 1: Clean install
Remove-Item -Recurse -Force backend\storage\chromadb -ErrorAction SilentlyContinue
pip uninstall -y chromadb langchain ollama
pip install --upgrade -r requirements.txt

# Terminal 2: Download smaller model
ollama rm llama2
ollama pull mistral
ollama run mistral

# Terminal 3: Update config
# Edit .env and change OLLAMA_MODEL=mistral

# Terminal 3: Test
python test_system.py

# Terminal 3: Run
streamlit run frontend/app.py
```

---

## 🚨 If Issues Persist

### Still getting memory errors?
1. Close other applications
2. Increase Virtual Memory (Windows):
   - Settings → System → About → Advanced system settings
   - Performance → Advanced → Virtual memory
   - Set to 4GB+
3. Use Orca-Mini instead

### Still getting import errors?
```bash
pip install --upgrade --force-reinstall cryptography>=41.0.0
```

### Still getting ChromaDB errors?
```bash
# Clean install
pip uninstall -y chromadb
pip cache purge
pip install chromadb>=0.4.0
```

### Can't connect to Ollama?
1. Make sure Ollama is running: `ollama serve`
2. Check host in .env: `OLLAMA_HOST=http://localhost:11434`
3. Try: `curl http://localhost:11434/api/tags`

---

## ✅ Verification Checklist

After all fixes:

- [ ] No import errors in test_system.py
- [ ] Ollama connection shows ✅
- [ ] ChromaDB storage created without errors
- [ ] Memory store test passes ✅
- [ ] RAG pipeline test passes ✅
- [ ] Streamlit app opens at http://localhost:8501
- [ ] Can login with code 1234
- [ ] Can create a memory
- [ ] Can ask a question and get response

---

## 📞 Still Need Help?

1. Check terminal output for specific errors
2. Run `python test_system.py` to identify issues
3. Verify `ollama serve` is running in separate terminal
4. Check `.env` file settings
5. Try smaller model (Orca-Mini) if memory still issues

---

**Your system is ready!** Follow the steps above and you'll have Memora running. 🚀

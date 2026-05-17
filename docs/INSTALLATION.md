# Setup & Installation Guide

## 📋 Prerequisites

Before you begin, ensure you have:
- **Python 3.8 or higher** (`python --version`)
- **pip** (package manager, comes with Python)
- **4GB RAM minimum** (8GB+ recommended)
- **Internet connection** (for initial setup only)
- **Ollama** installed from https://ollama.ai

## 🚀 Step-by-Step Installation

### Step 1: Install Ollama

1. Visit https://ollama.ai
2. Download for your operating system (Windows, macOS, Linux)
3. Install and run Ollama
4. Verify installation:
   ```bash
   ollama --version
   ```

### Step 2: Download Lama Model

Open terminal/PowerShell and run:
```bash
# Download Llama 2 (recommended, ~4GB)
ollama run llama2

# Or try a smaller model (faster, ~3GB)
ollama run neural-chat

# Or the newer Llama 3.1
ollama run llama2-13b
```

This downloads the model (one-time, takes 5-30 minutes depending on internet).

### Step 3: Clone/Download Project

```bash
# Navigate to your desired directory
cd Desktop

# Clone the repository (if using Git)
git clone https://github.com/yourusername/memora.git
cd Memora

# Or if downloaded as ZIP, extract it
# Then navigate to the folder
```

### Step 4: Create Virtual Environment (Recommended)

#### Windows (PowerShell):
```bash
# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate

# You should see (venv) in your terminal
```

#### macOS/Linux:
```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# You should see (venv) in your terminal
```

### Step 5: Install Dependencies

With virtual environment activated:

```bash
# Upgrade pip first
python -m pip install --upgrade pip

# Install all required packages
pip install -r requirements.txt

# This takes 2-5 minutes depending on internet speed
```

### Step 6: Verify Installation

```bash
# Run system verification test
python test_system.py
```

Expected output:
```
🧠 Second Brain - System Verification
==================================================
🔍 Testing Ollama Connection...
✅ Ollama is running!
📦 Available models: ['llama2', 'neural-chat']
✅ llama2 is available
🔐 Testing Security...
✅ Encryption successful
✅ Decryption successful
✅ Data integrity verified
...
==================================================
🎉 All systems operational! Ready to run the app.
```

If you see errors, check the troubleshooting section below.

### Step 7: Run the Application

```bash
# Make sure Ollama is still running in another terminal!

# Run Streamlit app
streamlit run frontend/app.py
```

The app will:
1. Start on `http://localhost:8501`
2. Automatically open in your default browser
3. Show you the login screen

### Step 8: Login and Use

1. **Default secret code: `1234`**
2. Click "🔓 Unlock" to enter
3. Start creating memories!

## 🔧 Configuration

### Change Settings

Edit `.env` file to customize:

```env
# Model to use
OLLAMA_MODEL=llama2           # Change to mistral, neural-chat, llama2-13b, etc.

# Security (CHANGE THESE!)
SECRET_CODE=1234              # Change your access code
ENCRYPTION_KEY=your-key       # Generate a secure key

# RAG Settings
RETRIEVAL_TOP_K=5             # How many memories to retrieve
SIMILARITY_THRESHOLD=0.3      # Minimum similarity (0-1)

# Memory Management
DECAY_FACTOR=0.95             # How fast memories fade (lower = faster)
MEMORY_DECAY_ENABLED=True     # Enable/disable memory decay
```

### Generate Secure Encryption Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output and paste it in `.env`:
```env
ENCRYPTION_KEY=your-generated-key-here
```

## 🔌 Running Ollama

### Keep Ollama Running

Ollama needs to be running before using the app. Choose one:

#### Option A: Keep open in background (Recommended)
```bash
# Terminal 1: Keep Ollama running
ollama serve

# Terminal 2: Run the app
cd /path/to/Memora
streamlit run frontend/app.py
```

#### Option B: Auto-start (macOS/Linux)
Create `~/.config/systemd/user/ollama.service`:
```ini
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart=/usr/bin/ollama serve
Restart=always

[Install]
WantedBy=default.target
```

Then enable with:
```bash
systemctl --user enable ollama
systemctl --user start ollama
```

#### Option C: Desktop Shortcut (Windows)
1. Create `start_ollama.bat`:
```batch
@echo off
ollama run llama2
pause
```
2. Double-click to run
3. Leave it open while using the app

## 📱 Accessing the Application

### Local Access
- **URL**: http://localhost:8501
- **Default Secret Code**: 1234
- **Access from**: Same computer only

### LAN Access (Advanced)
To access from other computers on your network:

1. Find your machine's IP:
   ```bash
   # Windows
   ipconfig
   
   # macOS/Linux
   ifconfig | grep inet
   ```
   Look for IPv4 address (e.g., 192.168.1.100)

2. Edit `.env`:
   ```env
   APP_HOST=0.0.0.0
   ```

3. Access from another computer:
   ```
   http://192.168.1.100:8501
   ```

4. **Security Note**: Use Secret Code properly, consider SSH tunneling for external access

## 🐛 Troubleshooting

### Issue: "Ollama is not running"

**Solution:**
```bash
# Start Ollama in a new terminal
ollama serve

# Or download and run the model
ollama run llama2
```

Keep the Ollama terminal running while using the app.

### Issue: "Module not found" error

**Solution:**
```bash
# Make sure virtual environment is activated
# Look for (venv) in terminal

# If not, activate it:
# Windows:
venv\Scripts\activate

# macOS/Linux:
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: "Port 8501 is already in use"

**Solution:**
```bash
# Use a different port
streamlit run frontend/app.py --server.port 8502
```

Or kill the process using port 8501:
```bash
# Windows
netstat -ano | findstr :8501
taskkill /PID <PID> /F

# macOS/Linux
lsof -i :8501
kill -9 <PID>
```

### Issue: "Connection refused" for ChromaDB

**Solution:**
```bash
# Clear the database and restart
rm -rf backend/storage/chromadb

# Restart the application
streamlit run frontend/app.py
```

### Issue: Slow responses or memory errors

**Solutions:**
1. Use a smaller model:
   ```bash
   ollama run neural-chat  # Faster than llama2
   ```

2. Reduce RETRIEVAL_TOP_K in `.env`:
   ```env
   RETRIEVAL_TOP_K=3  # Instead of 5
   ```

3. Close other applications to free RAM

4. Increase virtual memory (Windows):
   - Settings → System → About → Advanced system settings
   - Performance → Advanced → Virtual memory
   - Set custom size (e.g., 8GB)

### Issue: "Bad encryption key" or decryption errors

**Solution:**
```bash
# 1. Generate new key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 2. Clear database
rm -rf backend/storage/chromadb

# 3. Update .env with new key
# 4. Restart application
```

## ✅ Post-Installation

### First-Time Setup Checklist

- [ ] Ollama is installed and running
- [ ] Python 3.8+ is installed
- [ ] Virtual environment created and activated
- [ ] All dependencies installed (`requirements.txt`)
- [ ] System verification passed (`test_system.py`)
- [ ] `.env` file configured
- [ ] Secret code changed from default (optional but recommended)
- [ ] Application runs without errors (`streamlit run frontend/app.py`)

### Verify Everything Works

```bash
# 1. Stop app if running (Ctrl+C)
# 2. Run test suite
python test_system.py

# 3. Start Ollama (if not already running)
ollama serve

# 4. In new terminal, start app
streamlit run frontend/app.py

# 5. Open http://localhost:8501
# 6. Login with default code (1234)
# 7. Create a test memory
# 8. Ask a question to verify RAG works
```

## 🚀 Quick Commands Reference

```bash
# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Start Ollama
ollama serve

# Run app
streamlit run frontend/app.py

# Run tests
python test_system.py

# Deactivate environment
deactivate

# View Ollama models
ollama list

# Download new model
ollama pull mistral
ollama run mistral
```

## 📚 Next Steps

After installation:
1. Read [README.md](../README.md) for usage guide
2. Check [ARCHITECTURE.md](./ARCHITECTURE.md) for technical details
3. Explore the UI and create your first memories
4. Customize settings in `.env` as needed
5. Consider backing up your memories regularly

## 🆘 Getting Help

1. **Check Troubleshooting** section above
2. **Run test suite**: `python test_system.py`
3. **Check logs**: Use Streamlit debug mode
4. **Review .env settings**: Ensure correct configuration
5. **Verify Ollama**: Make sure it has model downloaded

## 📝 System Requirements Summary

| Item | Requirement |
|------|------------|
| Python | 3.8+ |
| RAM | 4GB minimum, 8GB+ recommended |
| Storage | 5GB+ for models and database |
| Ollama | Latest version |
| Internet | Initial setup only |
| OS | Windows, macOS, Linux |

---

**Installation Guide Version**: 1.0
**Last Updated**: April 2024
**Status**: Ready for Production

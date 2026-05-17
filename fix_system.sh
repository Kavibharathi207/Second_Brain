#!/bin/bash

# Automated Fix Script for Second Brain System Issues
# This script fixes all known issues with the installation

echo ""
echo "===================================================="
echo "  Second Brain - Automated System Fix"
echo "===================================================="
echo ""

# Check if already in the right directory
if [ ! -d "backend" ]; then
    echo "[ERROR] Please run this script from the Memora directory"
    echo "Current directory: $(pwd)"
    read -p "Press enter to exit..."
    exit 1
fi

echo "[INFO] Starting automated fixes..."
echo ""

# Fix 1: Remove old packages
echo "[STEP 1] Cleaning up old packages..."
pip uninstall -y chromadb langchain langchain-community langchain-core ollama python-requests > /dev/null 2>&1
echo "[OK] Old packages removed"

# Fix 2: Clear ChromaDB database
echo ""
echo "[STEP 2] Clearing old ChromaDB database..."
if [ -d "backend/storage/chromadb" ]; then
    rm -rf backend/storage/chromadb
    echo "[OK] Database cleared"
else
    echo "[OK] No old database found"
fi

# Fix 3: Update requirements
echo ""
echo "[STEP 3] Installing updated dependencies..."
pip install --upgrade pip > /dev/null 2>&1
pip install --upgrade -r requirements.txt
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install dependencies"
    read -p "Press enter to exit..."
    exit 1
fi
echo "[OK] Dependencies installed"

# Fix 4: Ask for model choice
echo ""
echo "[STEP 4] Select Ollama model..."
echo ""
echo "Recommended models (ranked by speed):"
echo "1. Mistral (5GB, 1.5GB RAM) - RECOMMENDED"
echo "2. Neural-Chat (4.8GB, 1.4GB RAM) - FAST"
echo "3. Orca-Mini (2GB, 1GB RAM) - SMALLEST"
echo ""
read -p "Enter choice (1-3, default=1): " MODEL_CHOICE

if [ -z "$MODEL_CHOICE" ]; then
    MODEL_CHOICE=1
fi

case $MODEL_CHOICE in
    1) MODEL="mistral";;
    2) MODEL="neural-chat";;
    3) MODEL="orca-mini";;
    *) MODEL="mistral";;
esac

echo "[INFO] Selected model: $MODEL"

# Fix 5: Update .env
echo ""
echo "[STEP 5] Updating configuration..."

# Create new .env with updated model
cat > .env.new << EOF
# Ollama Configuration
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=$MODEL
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# ChromaDB Configuration
CHROMA_DB_PATH=./backend/storage/chromadb
CHROMA_COLLECTION_NAME=memories

# Security Configuration
ENCRYPTION_KEY=default-insecure-key-please-change-this
SECRET_CODE=1234

# RAG Configuration
RETRIEVAL_TOP_K=5
SIMILARITY_THRESHOLD=0.3

# Memory Management
MEMORY_DECAY_ENABLED=True
DECAY_FACTOR=0.95

# Application Settings
APP_HOST=localhost
APP_PORT=8501
DEBUG=True
EOF

# Backup old .env
if [ -f ".env" ]; then
    mv .env .env.backup
    echo "[OK] Old .env backed up to .env.backup"
fi

# Use new .env
mv .env.new .env
echo "[OK] Configuration updated with model: $MODEL"

# Fix 6: Instructions
echo ""
echo "===================================================="
echo "  Fixes Applied Successfully!"
echo "===================================================="
echo ""
echo "[NEXT STEPS]"
echo ""
echo "1. Download Ollama model (choose one):"
echo "   Option A: ollama run mistral"
echo "   Option B: ollama run neural-chat"
echo "   Option C: ollama run orca-mini"
echo ""
echo "2. Keep Ollama running in that terminal"
echo ""
echo "3. In a new terminal, run:"
echo "   python test_system.py"
echo ""
echo "4. If all tests pass, run:"
echo "   streamlit run frontend/app.py"
echo ""
echo "Default secret code: 1234"
echo ""
echo "===================================================="
echo ""

read -p "Press enter to exit..."

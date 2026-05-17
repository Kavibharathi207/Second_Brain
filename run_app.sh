#!/bin/bash

# Second Brain - macOS/Linux Startup Script

echo ""
echo "===================================================="
echo "  Second Brain - AI Memory Assistant"
echo "  Startup Script for macOS/Linux"
echo "===================================================="
echo ""

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed"
    echo "Please install Python from https://www.python.org/"
    read -p "Press enter to exit..."
    exit 1
fi

echo "[OK] Python found"
python3 --version

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo ""
    echo "[INFO] Virtual environment not found. Creating..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "[INFO] Activating virtual environment..."
source venv/bin/activate

if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to activate virtual environment"
    read -p "Press enter to exit..."
    exit 1
fi

echo "[OK] Virtual environment activated"

# Check dependencies
echo ""
echo "[INFO] Checking dependencies..."
pip list | grep streamlit > /dev/null
if [ $? -ne 0 ]; then
    echo "[INFO] Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to install dependencies"
        read -p "Press enter to exit..."
        exit 1
    fi
fi

echo "[OK] All dependencies installed"

# Check Ollama
echo ""
echo "[INFO] Checking Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "[WARNING] Ollama not found"
    echo "Please ensure Ollama is installed and running"
    echo "Visit: https://ollama.ai"
    echo ""
    read -p "Press enter to continue..."
else
    echo "[OK] Ollama found"
    ollama --version
fi

# Show instructions
echo ""
echo "===================================================="
echo "  IMPORTANT: Start Ollama First!"
echo "===================================================="
echo ""
echo "1. Open a NEW terminal window"
echo "2. Run: ollama serve"
echo "3. Keep that window open"
echo "4. Return to this window"
echo ""
read -p "Press enter to continue..."

# Run verification
echo ""
echo "[INFO] Running system verification..."
python test_system.py
echo ""

# Start Streamlit app
echo ""
echo "===================================================="
echo "  Starting Second Brain Application..."
echo "===================================================="
echo ""
echo "Opening application at: http://localhost:8501"
echo "Default secret code: 1234"
echo ""
echo "Press Ctrl+C to stop the application"
echo ""

streamlit run frontend/app.py

read -p "Press enter to exit..."

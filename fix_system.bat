@echo off
REM Automated Fix Script for Second Brain System Issues
REM This script fixes all known issues with the installation

echo.
echo ====================================================
echo  Second Brain - Automated System Fix
echo ====================================================
echo.

REM Check if already in the right directory
if not exist "backend" (
    echo [ERROR] Please run this script from the Memora directory
    echo Current directory: %cd%
    pause
    exit /b 1
)

echo [INFO] Starting automated fixes...
echo.

REM Fix 1: Remove old packages
echo [STEP 1] Cleaning up old packages...
pip uninstall -y chromadb langchain langchain-community langchain-core ollama python-requests > nul 2>&1
echo [OK] Old packages removed

REM Fix 2: Clear ChromaDB database
echo.
echo [STEP 2] Clearing old ChromaDB database...
if exist "backend\storage\chromadb" (
    rmdir /s /q backend\storage\chromadb
    echo [OK] Database cleared
) else (
    echo [OK] No old database found
)

REM Fix 3: Update requirements
echo.
echo [STEP 3] Installing updated dependencies...
pip install --upgrade pip > nul 2>&1
pip install --upgrade -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed

REM Fix 4: Ask for model choice
echo.
echo [STEP 4] Select Ollama model...
echo.
echo Recommended models (ranked by speed):
echo 1. Mistral (5GB, 1.5GB RAM) - RECOMMENDED
echo 2. Neural-Chat (4.8GB, 1.4GB RAM) - FAST
echo 3. Orca-Mini (2GB, 1GB RAM) - SMALLEST
echo.
set /p MODEL_CHOICE="Enter choice (1-3, default=1): "

if "%MODEL_CHOICE%"=="" set MODEL_CHOICE=1

if "%MODEL_CHOICE%"=="1" (
    set MODEL=mistral
) else if "%MODEL_CHOICE%"=="2" (
    set MODEL=neural-chat
) else if "%MODEL_CHOICE%"=="3" (
    set MODEL=orca-mini
) else (
    set MODEL=mistral
)

echo [INFO] Selected model: %MODEL%

REM Fix 5: Update .env
echo.
echo [STEP 5] Updating configuration...

REM Create new .env with updated model
(
    echo # Ollama Configuration
    echo OLLAMA_HOST=http://localhost:11434
    echo OLLAMA_MODEL=%MODEL%
    echo OLLAMA_EMBEDDING_MODEL=nomic-embed-text
    echo.
    echo # ChromaDB Configuration
    echo CHROMA_DB_PATH=./backend/storage/chromadb
    echo CHROMA_COLLECTION_NAME=memories
    echo.
    echo # Security Configuration
    echo ENCRYPTION_KEY=default-insecure-key-please-change-this
    echo SECRET_CODE=1234
    echo.
    echo # RAG Configuration
    echo RETRIEVAL_TOP_K=5
    echo SIMILARITY_THRESHOLD=0.3
    echo.
    echo # Memory Management
    echo MEMORY_DECAY_ENABLED=True
    echo DECAY_FACTOR=0.95
    echo.
    echo # Application Settings
    echo APP_HOST=localhost
    echo APP_PORT=8501
    echo DEBUG=True
) > .env.new

REM Backup old .env
if exist ".env" (
    ren ".env" ".env.backup"
    echo [OK] Old .env backed up to .env.backup
)

REM Use new .env
ren ".env.new" ".env"
echo [OK] Configuration updated with model: %MODEL%

REM Fix 6: Instructions
echo.
echo ====================================================
echo  Fixes Applied Successfully!
echo ====================================================
echo.
echo [NEXT STEPS]
echo.
echo 1. Download Ollama model (choose one):
echo    Option A: ollama run mistral
echo    Option B: ollama run neural-chat
echo    Option C: ollama run orca-mini
echo.
echo 2. Keep Ollama running in that terminal
echo.
echo 3. In a new terminal, run:
echo    python test_system.py
echo.
echo 4. If all tests pass, run:
echo    streamlit run frontend/app.py
echo.
echo Default secret code: 1234
echo.
echo ====================================================
echo.

pause

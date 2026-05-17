@echo off
REM Second Brain - Windows Startup Script
REM This script starts the application with all required services

echo.
echo ====================================================
echo  Second Brain - AI Memory Assistant
echo  Startup Script for Windows
echo ====================================================
echo.

REM Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

echo [OK] Python found
python --version

REM Check if virtual environment exists
if not exist venv (
    echo.
    echo [INFO] Virtual environment not found. Creating...
    python -m venv venv
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)

echo [OK] Virtual environment activated

REM Check dependencies
echo.
echo [INFO] Checking dependencies...
pip list | findstr streamlit >nul
if %errorlevel% neq 0 (
    echo [INFO] Installing dependencies from requirements.txt...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
)

echo [OK] All dependencies installed

REM Check Ollama
echo.
echo [INFO] Checking Ollama...
ollama version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Ollama not found in PATH
    echo Please ensure Ollama is installed and running
    echo Visit: https://ollama.ai
    echo.
    pause
) else (
    echo [OK] Ollama found
    ollama --version
)

REM Show instructions
echo.
echo ====================================================
echo  IMPORTANT: Start Ollama First!
echo ====================================================
echo.
echo 1. Open a NEW PowerShell window
echo 2. Run: ollama serve
echo 3. Keep that window open
echo 4. Return to this window
echo.
pause

REM Run verification
echo.
echo [INFO] Running system verification...
python test_system.py
echo.

REM Start Streamlit app
echo.
echo ====================================================
echo  Starting Second Brain Application...
echo ====================================================
echo.
echo Opening application at: http://localhost:8501
echo Default secret code: 1234
echo.
echo Press Ctrl+C to stop the application
echo.

streamlit run frontend/app.py

pause

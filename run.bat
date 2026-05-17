@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo Starting Second Brain...
streamlit run frontend/app.py
pause


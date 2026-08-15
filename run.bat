@echo off
title KarAI — Automated Tax Compliance & Anomaly Detection
echo ======================================================================
echo    🚀 Launching KarAI — Automated Tax Audit & Anomaly Detection
echo ======================================================================

cd /d "%~dp0"

if not exist "venv" (
    echo 📦 Creating Python virtual environment...
    python -m venv venv
    call venv\Scripts\activate
    pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate
)

echo ⚡ Starting FastAPI App Server at http://127.0.0.1:8000 ...
start http://127.0.0.1:8000

set PYTHONPATH=backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause

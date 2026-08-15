#!/bin/bash
# -----------------------------------------------------------------------------
# KarAI — 1-Click Portable Presentation Startup Script (Mac / Linux)
# -----------------------------------------------------------------------------

echo "======================================================================"
echo "   🚀 Launching KarAI — Automated Tax Audit & Anomaly Detection"
echo "======================================================================"

# Determine directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Create venv if not existing
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
fi

echo "⚡ Starting FastAPI App Server at http://127.0.0.1:8000 ..."

# Open browser after 2 seconds
(sleep 2 && open "http://127.0.0.1:8000" 2>/dev/null || xdg-open "http://127.0.0.1:8000" 2>/dev/null) &

# Run server
PYTHONPATH=backend ./venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

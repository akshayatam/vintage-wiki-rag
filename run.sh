#!/usr/bin/env bash

set -e  # Exit immediately if a command fails

echo "🔧 Initializing environment..."

# -----------------------------
# Virtual environment
# -----------------------------
if [ ! -d ".venv" ]; then
  echo "📦 Creating virtual environment..."
  python3 -m venv .venv
else
  echo "✅ Virtual environment already exists"
fi

echo "🚀 Activating virtual environment..."
source .venv/bin/activate

# -----------------------------
# Dependencies
# -----------------------------
echo "📚 Installing dependencies..."
pip install --upgrade pip setuptools wheel --no-cache-dir
pip install -r requirements.txt

# -----------------------------
# Start FastAPI backend
# -----------------------------
echo "🧠 Starting FastAPI backend..."
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload &

FASTAPI_PID=$!
echo "✅ FastAPI running (PID: $FASTAPI_PID)"

# -----------------------------
# Start Streamlit UI
# -----------------------------
echo "🎨 Starting Streamlit UI..."
streamlit run ui/app.py

# -----------------------------
# Cleanup on exit
# -----------------------------
echo "🧹 Shutting down services..."
kill $FASTAPI_PID

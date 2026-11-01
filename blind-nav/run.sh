#!/usr/bin/env bash
# blind-nav launcher — Linux / macOS
set -e
cd "$(dirname "$0")"

echo "================================================"
echo "  blind-nav  |  Unix Launcher"
echo "================================================"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 not found."
    exit 1
fi

# Venv
if [ ! -d ".venv" ]; then
    echo "[SETUP] Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Install deps
if [ ! -f ".venv/.deps_installed" ]; then
    echo "[SETUP] Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    touch .venv/.deps_installed
fi

# Models
if [ ! -f "models/yolov8n.pt" ]; then
    echo "[SETUP] Downloading models..."
    python download_models.py
fi

echo ""
echo "[INFO] Starting blind-nav..."
echo ""
python run.py "$@"


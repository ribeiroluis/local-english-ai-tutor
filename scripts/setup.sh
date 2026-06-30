#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "=== English AI Tutor Setup ==="

# Create virtual environment if missing
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Detect OS and set activation path
if [ -f ".venv/bin/activate" ]; then
    ACTIVATE=".venv/bin/activate"
elif [ -f ".venv/Scripts/activate" ]; then
    ACTIVATE=".venv/Scripts/activate"
fi

# Activate and install deps
source "$ACTIVATE"
echo "Installing dependencies..."
python -m pip install --upgrade pip 2>/dev/null || true
pip install -r requirements.txt

# Create data and log directories
mkdir -p app/data/sessions app/logs

# Copy .env.example if .env doesn't exist
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env from .env.example — review and edit as needed"
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "To start the app:"
echo "  source $ACTIVATE"
echo "  uvicorn app.main:app --reload"
echo ""
echo "Or run:"
echo "  bash scripts/run.sh"

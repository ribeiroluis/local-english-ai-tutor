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

# Activate and install deps
source .venv/bin/activate
echo "Installing dependencies..."
pip install --upgrade pip
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
echo "Run: uvicorn app.main:app"

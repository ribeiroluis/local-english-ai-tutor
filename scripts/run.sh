#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

if [ ! -d ".venv" ]; then
    echo "Error: .venv not found. Run scripts/setup.sh first."
    exit 1
fi

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
fi

: > "app/logs/app.log" 2>/dev/null || true
uvicorn app.main:app --reload

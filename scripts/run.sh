#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

if [ ! -d ".venv" ]; then
    echo "Error: .venv not found. Run scripts/setup.sh first."
    exit 1
fi

source .venv/bin/activate
uvicorn app.main:app --reload

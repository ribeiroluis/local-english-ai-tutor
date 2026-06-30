#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "=== English AI Tutor Setup ==="
echo ""

# --------------------------------------------------
# 1. Python version check
# --------------------------------------------------
echo "[1/7] Checking Python..."
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PY_VER=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+')
        MAJOR=$(echo "$PY_VER" | cut -d. -f1)
        MINOR=$(echo "$PY_VER" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 11 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.11+ required. Found: $("$cmd" --version 2>&1)"
    exit 1
fi
echo "  Found: $($PYTHON --version)"

# --------------------------------------------------
# 2. Virtual environment
# --------------------------------------------------
echo "[2/7] Virtual environment..."
if [ ! -d ".venv" ]; then
    $PYTHON -m venv .venv
    echo "  Created .venv"
else
    echo "  .venv exists, skipping"
fi

if [ -f ".venv/bin/activate" ]; then
    ACTIVATE=".venv/bin/activate"
elif [ -f ".venv/Scripts/activate" ]; then
    ACTIVATE=".venv/Scripts/activate"
fi
source "$ACTIVATE"
echo "  Activated: $ACTIVATE"

# --------------------------------------------------
# 3. Install dependencies
# --------------------------------------------------
echo "[3/7] Installing dependencies..."
python -m pip install --upgrade pip 2>/dev/null || true
pip install -r requirements.txt

# --------------------------------------------------
# 4. Ollama install + model pull
# --------------------------------------------------
echo "[4/7] Ollama..."

ollama_install() {
    echo "  Ollama not found. Installing..."
    case "$(uname -s)" in
        Linux)
            echo "  Detected Linux. Installing via official script..."
            if command -v curl &>/dev/null; then
                curl -fsSL https://ollama.com/install.sh | sh
            elif command -v wget &>/dev/null; then
                wget -qO- https://ollama.com/install.sh | sh
            else
                echo "  ERROR: curl or wget required to install Ollama."
                echo "  Install manually: https://ollama.com/download"
                exit 1
            fi
            ;;
        Darwin)
            echo "  Detected macOS. Installing via official script..."
            curl -fsSL https://ollama.com/install.sh | sh
            ;;
        *)
            echo "  Unsupported OS for auto-install."
            echo "  Install manually: https://ollama.com/download"
            exit 1
            ;;
    esac
}

if command -v ollama &>/dev/null; then
    echo "  ollama binary found"
else
    ollama_install
fi

# Start Ollama if not running
if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
    echo "  Starting Ollama server in background..."
    ollama serve &>/dev/null &
    sleep 3
fi

# Check again after starting
if curl -s http://localhost:11434/api/tags &>/dev/null; then
    echo "  Ollama server is running"
else
    echo "  WARNING: Ollama server not responding on http://localhost:11434"
    echo "  Start manually: ollama serve"
fi

# Pull model
MODEL="qwen2.5:3b"
if ollama list 2>/dev/null | grep -q "$MODEL"; then
    echo "  Model $MODEL already pulled"
else
    echo "  Pulling model $MODEL (may take several minutes)..."
    ollama pull "$MODEL"
    echo "  Model $MODEL pulled"
fi

# --------------------------------------------------
# 5. Piper TTS install + voice download
# --------------------------------------------------
echo "[5/7] Piper TTS..."

PIPER_VOICE_DIR="$PROJECT_DIR/app/data/voice"
VOICE_FILE="$PIPER_VOICE_DIR/en_US-lessac-medium.onnx"

if [ ! -f "$VOICE_FILE" ]; then
    echo "  Downloading Piper voice (en_US-lessac-medium)..."
    mkdir -p "$PIPER_VOICE_DIR"
    if command -v curl &>/dev/null; then
        curl -L -o "$VOICE_FILE" \
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
        curl -L -o "$VOICE_FILE.json" \
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
    elif command -v wget &>/dev/null; then
        wget -O "$VOICE_FILE" \
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
        wget -O "$VOICE_FILE.json" \
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
    fi
    echo "  Voice downloaded to $VOICE_FILE"
fi

# Check if piper binary exists
if ! command -v piper &>/dev/null; then
    echo "  WARNING: piper binary not found in PATH."
    echo "  Install it: https://github.com/rhasspy/piper/releases"
    echo "  Or build from source: https://github.com/rhasspy/piper"
    echo "  (Voice file already downloaded; set PIPER_VOICE_PATH in .env)"
fi

# --------------------------------------------------
# 6. Create directories + configure .env
# --------------------------------------------------
echo "[6/7] Configuring project..."

mkdir -p app/data/sessions app/logs

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "  Created .env from .env.example"
    else
        cat > .env <<-EOF
PORT=8000
OLLAMA_HOST=http://localhost:11434
WHISPER_MODEL_SIZE=base.en
PIPER_VOICE_PATH=$VOICE_FILE
LOG_LEVEL=INFO
EOF
        echo "  Created .env with defaults"
    fi
fi

# Update PIPER_VOICE_PATH in .env if still empty
CURRENT_PIPER=$(grep -oP '^PIPER_VOICE_PATH=\K.*' .env || true)
if [ -z "$CURRENT_PIPER" ]; then
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        WIN_PATH=$(cygpath -w "$VOICE_FILE" 2>/dev/null || echo "$VOICE_FILE")
        sed -i "s|^PIPER_VOICE_PATH=.*|PIPER_VOICE_PATH=$WIN_PATH|" .env
    else
        sed -i "s|^PIPER_VOICE_PATH=.*|PIPER_VOICE_PATH=$VOICE_FILE|" .env
    fi
    echo "  Updated PIPER_VOICE_PATH in .env"
fi

# --------------------------------------------------
# 7. Final health checks
# --------------------------------------------------
echo "[7/7] Health checks..."

# Ollama check
if curl -s http://localhost:11434/api/tags &>/dev/null; then
    echo "  [OK] Ollama reachable at http://localhost:11434"
else
    echo "  [FAIL] Ollama not reachable — run: ollama serve"
fi

# Piper check
if command -v piper &>/dev/null; then
    echo "  [OK] piper binary in PATH"
else
    echo "  [WARN] piper binary not in PATH — install from https://github.com/rhasspy/piper/releases"
fi

# Voice file check
if [ -f "$VOICE_FILE" ]; then
    echo "  [OK] Piper voice file present ($(du -h "$VOICE_FILE" | cut -f1))"
else
    echo "  [FAIL] Voice file missing at $VOICE_FILE"
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "To start the app:"
echo "  bash scripts/run.sh"
echo ""
echo "Or manually:"
echo "  source $ACTIVATE"
echo "  uvicorn app.main:app --reload"

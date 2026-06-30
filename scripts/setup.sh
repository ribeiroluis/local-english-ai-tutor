#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "=== English AI Tutor Setup ==="
echo ""

# Detect OS
IS_WINDOWS=false
case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*|Windows*) IS_WINDOWS=true ;;
esac

# --------------------------------------------------
# 1. Python version check
# --------------------------------------------------
echo "[1/7] Checking Python..."
check_python_version() {
    local cmd="$1"
    local full_ver major minor
    full_ver=$("$cmd" --version 2>&1) || return 1
    # Verify output starts with "Python" (not Microsoft Store shim)
    case "$full_ver" in
        Python*) ;;
        *) return 1 ;;
    esac
    major=$(echo "$full_ver" | awk '{print $2}' | cut -d. -f1)
    minor=$(echo "$full_ver" | awk '{print $2}' | cut -d. -f2)
    [ -n "$major" ] && [ -n "$minor" ] && [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]
}

PYTHON=""
# On Windows, skip python3 (it may trigger Microsoft Store shim)
if [ "$IS_WINDOWS" = false ]; then
    for cmd in python3 python3.11 python3.12; do
        if command -v "$cmd" &>/dev/null && check_python_version "$cmd"; then
            PYTHON="$cmd"
            break
        fi
    done
fi

# Fallback: try python (works on both Windows and Unix)
if [ -z "$PYTHON" ] && command -v python &>/dev/null; then
    if check_python_version "python"; then
        PYTHON="python"
    fi
fi

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.11+ required."
    echo "  Run: python --version"
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
else
    echo "  ERROR: Cannot find activate script in .venv"
    exit 1
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

# Check if Ollama is already installed
OLLAMA_INSTALLED=false
if command -v ollama &>/dev/null; then
    OLLAMA_INSTALLED=true
    echo "  ollama binary found"
elif [ -f "/usr/local/bin/ollama" ]; then
    OLLAMA_INSTALLED=true
    PATH="/usr/local/bin:$PATH"
    echo "  ollama found at /usr/local/bin"
fi

if [ "$OLLAMA_INSTALLED" = false ]; then
    echo "  Installing Ollama..."
    if command -v curl &>/dev/null; then
        curl -fsSL https://ollama.com/install.sh | sh
        OLLAMA_INSTALLED=true
    elif command -v wget &>/dev/null; then
        wget -qO- https://ollama.com/install.sh | sh
        OLLAMA_INSTALLED=true
    else
        echo "  WARNING: curl not found. Cannot auto-install Ollama."
        echo "  Install manually: https://ollama.com/download"
    fi
fi

# Start Ollama server if not running
OLLAMA_RUNNING=false
if command -v ollama &>/dev/null; then
    if curl -s --max-time 2 http://localhost:11434/api/tags &>/dev/null; then
        OLLAMA_RUNNING=true
        echo "  Ollama server is running"
    else
        echo "  Starting Ollama server in background..."
        if [ "$IS_WINDOWS" = true ]; then
            # Windows: start in background with nohup-like approach
            (ollama serve &) &>/dev/null
        else
            nohup ollama serve &>/dev/null &
        fi
        sleep 3
        if curl -s --max-time 2 http://localhost:11434/api/tags &>/dev/null; then
            OLLAMA_RUNNING=true
            echo "  Ollama server started"
        else
            echo "  WARNING: Could not start Ollama server."
            echo "  Start manually: ollama serve"
        fi
    fi
fi

# Pull model
if [ "$OLLAMA_RUNNING" = true ]; then
    MODEL="qwen2.5:3b"
    if ollama list 2>/dev/null | grep -q "$MODEL"; then
        echo "  Model $MODEL already pulled"
    else
        echo "  Pulling model $MODEL (may take several minutes)..."
        ollama pull "$MODEL"
        echo "  Model $MODEL pulled"
    fi
else
    echo "  Skipping model pull (Ollama not running)"
fi

# --------------------------------------------------
# 5. Piper TTS voice download
# --------------------------------------------------
echo "[5/7] Piper TTS voice..."

PIPER_VOICE_DIR="$PROJECT_DIR/app/data/voice"
VOICE_FILE="$PIPER_VOICE_DIR/en_US-lessac-medium.onnx"

if [ ! -f "$VOICE_FILE" ]; then
    echo "  Downloading Piper voice (en_US-lessac-medium)..."
    mkdir -p "$PIPER_VOICE_DIR"
    if command -v curl &>/dev/null; then
        curl -L --connect-timeout 10 -o "$VOICE_FILE" \
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
        curl -L --connect-timeout 10 -o "$VOICE_FILE.json" \
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
        echo "  Voice downloaded to $VOICE_FILE"
    else
        echo "  WARNING: curl not found. Download manually:"
        echo "    https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
        echo "    Save to: $VOICE_FILE"
    fi
else
    echo "  Voice file exists ($(du -h "$VOICE_FILE" 2>/dev/null | cut -f1 || stat -c%s "$VOICE_FILE" 2>/dev/null || echo "unknown size"))"
fi

# Check piper binary
if command -v piper &>/dev/null; then
    echo "  piper binary found in PATH"
else
    echo "  WARNING: piper binary not in PATH."
    echo "  Install from: https://github.com/rhasspy/piper/releases"
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
        cat > .env <<-ENVEOF
PORT=8000
OLLAMA_HOST=http://localhost:11434
WHISPER_MODEL_SIZE=base.en
PIPER_VOICE_PATH=$VOICE_FILE
LOG_LEVEL=INFO
ENVEOF
        echo "  Created .env with defaults"
    fi
fi

# Update PIPER_VOICE_PATH in .env if empty or placeholder
CURRENT_PIPER=$(grep -E '^PIPER_VOICE_PATH=' .env 2>/dev/null | cut -d= -f2- || true)
if [ -z "$CURRENT_PIPER" ]; then
    # Escape for sed replacement
    ESCAPED_VOICE=$(echo "$VOICE_FILE" | sed 's/[\/&]/\\&/g')
    if grep -q '^PIPER_VOICE_PATH=' .env 2>/dev/null; then
        sed -i "s|^PIPER_VOICE_PATH=.*|PIPER_VOICE_PATH=$ESCAPED_VOICE|" .env
    else
        echo "PIPER_VOICE_PATH=$VOICE_FILE" >> .env
    fi
    echo "  Updated PIPER_VOICE_PATH in .env"
fi

# --------------------------------------------------
# 7. Final health checks
# --------------------------------------------------
echo "[7/7] Health checks..."

# Ollama check
if curl -s --max-time 2 http://localhost:11434/api/tags &>/dev/null; then
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
    echo "  [OK] Piper voice file present"
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

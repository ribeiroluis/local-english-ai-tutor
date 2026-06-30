# AGENTS — English AI Tutor

## Project
Web app for spoken English conversation practice. 100% local, CPU, open-source.
MVP: speak → STT → LLM → TTS → correction at session end.

## Stack
- Backend: Python 3.11+ / FastAPI / Uvicorn
- Frontend: HTML + CSS + JS vanilla (no frameworks)
- STT: faster-whisper (`base.en`)
- LLM: Ollama (`qwen2.5:3b`)
- TTS: Piper TTS (`en_US-lessac-medium`)
- Persistence: JSON per session in `app/data/sessions/`
- Logs: `app/logs/app.log` (append)
- Setup: `scripts/setup.sh` (idempotent)

## Rules
- Mobile-first (375px base). Desktop is progressive enhancement.
- Persist in JSON, not SQLite (MVP).
- Error correction only at session end, not in real-time.
- CEFR level (A1-C2) adjusts per session via error_ratio (>40% down, <10% up).
- 1 LLM call/turn (conversation) + 1 LLM call at end (review).
- Context window: last 10 turns.
- Single page app: Welcome screen → Chat screen → Review modal.
- Single user, no auth.

## DO
- Single-pass LLM: reply per turn, no analysis until end.
- Synchronous pipeline: POST audio → wait → receive audio.
- Frontend: MediaRecorder → WAV (16-bit mono 16kHz).
- Topics in `app/prompts/topics.json` (JSON, not hard-coded).
- `.env` for config (port, model paths, Ollama host).
- Log every operation with level (INFO/WARNING/ERROR/SUCCESS).

## DON'T
- No external paid APIs.
- No GPU dependency.
- No real-time correction during conversation.
- No SQLite (use JSON).
- No authentication/login.
- No dark mode (post-MVP).
- No ffmpeg dependency (WAV direct).
- No decorative animations (only state transitions).
- No side-stripe borders, gradient text, glassmorphism.

## Git Workflow
- Branch por issue: `issue-<numero>-<descricao-curta>` (ex: `issue-1-project-scaffold`)
- Commits atômicos: um commit por mudança lógica (ex: "Add requirements.txt", "Create FastAPI app", "Add topics.json")
- Mensagens de commit: imperativo, inglês, sem prefixo, ex: "Create FastAPI app with health check"
- PR por issue: abrir PR automaticamente apontando para `main` assim que implementação finalizar
- Após merge: deletar branch
- Usuário faz merge manualmente no git (nunca usar merge automático)

## Test Strategy
- STT: real WAV fixtures in `tests/fixtures/audio/` (user records them).
- LLM: mock Ollama HTTP, test prompt builder + response parsing.
- TTS: mock Piper subprocess, test argument construction.
- Session: test JSON CRUD with temp files.

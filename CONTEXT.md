# English AI Tutor — Domain Glossary

## Product
Web app for spoken English practice. 100% local, CPU-only, open-source.
User speaks in English, AI replies in voice, and provides grammar/vocab corrections at session end.

## Concepts

### Session
A complete conversation from "start" to "end review". Has a topic, a starting CEFR level, a list of turns, and optionally a corrections report. Persisted as one JSON file in `app/data/sessions/`.

### Turn
One exchange: user speaks → STT transcribes → LLM replies → TTS speaks. Stored within a session.

### Correction
Generated at session end. LLM analyzes all turns and produces a per-error entry: original text, corrected text, error type (grammar, verb_tense, article, preposition, vocabulary, word_order, agreement, other), and explanation in PT-BR.

### CEFR Level
Common European Framework of Reference (A1, A2, B1, B2, C1, C2). The user's level adjusts after each session based on `error_ratio` (turns with errors / total turns).

### Topic
A conversation scenario (small-talk, job-interview, restaurant, travel). Defines the LLM system persona. Stored in `app/prompts/topics.json`.

### Error Ratio
`turns_with_errors / total_turns` per session. Drives CEFR adjustment: >40% → level down, <10% → level up.

## Architecture Decisions

- **STT**: faster-whisper `base.en`.
- **LLM**: Ollama `qwen2.5:3b`.
- **TTS**: Piper TTS `en_US-lessac-medium`.
- **Correction**: end-of-session only. Single-pass (reply + correction = one LLM call at end, not per-turn).
- **Context**: last 10 turns sent to LLM.
- **Persistence**: JSON files, not SQLite (MVP).
- **Auth**: none (single user).
- **Audio format**: WAV 16-bit mono 16kHz from browser MediaRecorder.

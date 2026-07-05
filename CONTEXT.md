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

- **STT**: faster-whisper. Supports `base.en` (default, 74M params) and `tiny.en` (39M, ~2x faster). Selected via toggle in welcome screen.
- **LLM**: Ollama. Supports `qwen2.5:3b` (default), `qwen2.5:1.5b` (~2-3x faster), `llama3.2:1b` (~3-4x faster). Selected via toggle.
- **TTS**: Piper TTS `en_US-lessac-medium`.
- **Correction**: end-of-session only. Single-pass (reply + correction = one LLM call at end, not per-turn).
- **Context**: last 10 turns (default) or 5 turns sent to LLM. Selected via toggle.
- **Pipeline**: always separated. Start first (AI opens with question), then transcribe (shows transcript immediately), then chat (LLM generates reply + correction + next question). User sees their text while LLM processes.
- **Conversation style**: AI drives the conversation. Always ends reply with a question. First turn is AI-only opening.
- **Persistence**: JSON files, not SQLite (MVP).
- **Auth**: none (single user).
- **Audio format**: WAV 16-bit mono 16kHz from browser MediaRecorder.

## Optimization Toggles

Welcome screen offers 4 independent radio groups:

| Toggle | Option 1 | Option 2 | Option 3 |
|--------|----------|----------|----------|
| STT Model | `base.en` (accurate) | `tiny.en` (fast) | — |
| STT Beam | Preciso (5) | Rápido (1) | — |
| LLM Model | `qwen2.5:3b` | `qwen2.5:1.5b` | `llama3.2:1b` |
| LLM Context | 10 turnos | 5 turnos | — |

STT options affect transcribe speed; LLM options affect reply generation speed. All toggles are independent.

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.services.logger import setup_logger

logger = setup_logger()

SESSIONS_DIR = Path(__file__).resolve().parents[2] / "app" / "data" / "sessions"
PROGRESS_FILE = Path(__file__).resolve().parents[2] / "app" / "data" / "user_progress.json"

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
DEFAULT_TOPIC = "small-talk"
DEFAULT_LEVEL = "A2"


def create_session(topic: str, level: str, user_name: str = "", llm_model: str = "qwen2.5:3b", context_turns: int = 10) -> dict:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    session_id = str(uuid.uuid4())
    session = {
        "session_id": session_id,
        "topic": topic,
        "level": level,
        "user_name": user_name,
        "llm_model": llm_model,
        "context_turns": context_turns,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "turns": [],
    }

    filepath = SESSIONS_DIR / f"{session_id}.json"
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Failed to write session file {filepath}: {e}")
        raise

    save_user_progress(topic, level)
    logger.info(f"Session created: {session_id} (topic={topic}, level={level})")
    return session


def get_session(session_id: str) -> dict | None:
    filepath = SESSIONS_DIR / f"{session_id}.json"
    if not filepath.exists():
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Corrupted session file {filepath}: {e}")
        return None


def add_opening_turn(session_id: str, ai_text: str, session: dict | None = None) -> dict:
    if session is None:
        session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")
    if "turns" not in session or not isinstance(session["turns"], list):
        session["turns"] = []
    session["turns"].append({
        "role": "assistant",
        "text": ai_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    filepath = SESSIONS_DIR / f"{session_id}.json"
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Failed to write session file {filepath}: {e}")
        raise
    logger.info(f"Opening turn added to session {session_id}: ai={len(ai_text)} chars")
    return session


def add_turn(session_id: str, user_text: str, ai_text: str, correction: dict | None = None, session: dict | None = None) -> dict:
    if session is None:
        session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")

    user_turn = {
        "role": "user",
        "text": user_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if correction is not None and isinstance(correction, dict):
        required = ("original", "corrected", "explanation_pt", "error_type")
        if all(k in correction for k in required):
            user_turn["correction"] = correction
        else:
            logger.warning(f"Correction missing required fields: {correction.keys()}")
    session["turns"].append(user_turn)
    session["turns"].append({
        "role": "assistant",
        "text": ai_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    filepath = SESSIONS_DIR / f"{session_id}.json"
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Failed to write session file {filepath}: {e}")
        raise

    logger.info(f"Turn added to session {session_id}: user={len(user_text)} chars, ai={len(ai_text)} chars")
    return session


def update_session(session: dict):
    session_id = session["session_id"]
    filepath = SESSIONS_DIR / f"{session_id}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(session, f, indent=2, ensure_ascii=False)


def save_user_progress(topic: str, level: str):
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing = load_user_progress()
    existing["last_topic"] = topic
    existing["current_cefr"] = level
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to write progress file {PROGRESS_FILE}: {e}")
        raise


def load_user_progress() -> dict:
    if not PROGRESS_FILE.exists():
        return {"current_cefr": DEFAULT_LEVEL, "last_topic": DEFAULT_TOPIC, "total_sessions": 0, "total_turns": 0, "errors_by_type": {}}
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "current_cefr" not in data:
                data["current_cefr"] = data.get("last_level", DEFAULT_LEVEL)
            return data
    except json.JSONDecodeError as e:
        logger.error(f"Corrupted progress file {PROGRESS_FILE}: {e}")
        return {"current_cefr": DEFAULT_LEVEL, "last_topic": DEFAULT_TOPIC, "total_sessions": 0, "total_turns": 0, "errors_by_type": {}}


def adjust_cefr_level(session_id: str) -> dict:
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")

    progress = load_user_progress()
    old_level = progress.get("current_cefr", DEFAULT_LEVEL)
    if old_level not in CEFR_LEVELS:
        old_level = DEFAULT_LEVEL

    user_turns = [t for t in session.get("turns", []) if t.get("role") == "user"]
    total_user_turns = len(user_turns)
    error_turns = sum(1 for t in user_turns if t.get("correction") and isinstance(t["correction"], dict))
    error_ratio = error_turns / total_user_turns if total_user_turns > 0 else 0.0

    idx = CEFR_LEVELS.index(old_level)
    if error_turns == 0 and total_user_turns == 0:
        new_idx = idx
    elif error_ratio > 0.4:
        new_idx = max(0, idx - 1)
    elif error_ratio < 0.1:
        new_idx = min(len(CEFR_LEVELS) - 1, idx + 1)
    else:
        new_idx = idx
    new_level = CEFR_LEVELS[new_idx]

    errors_by_type = progress.get("errors_by_type", {})
    for t in user_turns:
        correction = t.get("correction")
        if correction and isinstance(correction, dict):
            etype = correction.get("error_type", "other")
            errors_by_type[etype] = errors_by_type.get(etype, 0) + 1

    new_progress = {
        "current_cefr": new_level,
        "last_topic": session.get("topic", DEFAULT_TOPIC),
        "total_sessions": progress.get("total_sessions", 0) + 1,
        "total_turns": progress.get("total_turns", 0) + total_user_turns,
        "errors_by_type": errors_by_type,
    }

    try:
        PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(new_progress, f, indent=2)
        logger.info(f"CEFR adjusted: {old_level} -> {new_level} (error_ratio={error_ratio:.2f})")
    except IOError as e:
        logger.error(f"Failed to write progress file: {e}")
        raise

    return {
        "from": old_level,
        "to": new_level,
        "error_ratio": round(error_ratio, 4),
        "error_turns": error_turns,
        "total_turns": total_user_turns,
    }

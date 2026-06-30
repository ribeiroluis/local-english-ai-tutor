import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.services.logger import setup_logger

logger = setup_logger()

SESSIONS_DIR = Path(__file__).resolve().parents[2] / "app" / "data" / "sessions"
PROGRESS_FILE = Path(__file__).resolve().parents[2] / "app" / "data" / "user_progress.json"

DEFAULT_TOPIC = "small-talk"
DEFAULT_LEVEL = "A2"


def create_session(topic: str, level: str) -> dict:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    session_id = str(uuid.uuid4())
    session = {
        "session_id": session_id,
        "topic": topic,
        "level": level,
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


def add_turn(session_id: str, user_text: str, ai_text: str) -> dict:
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")

    session["turns"].append({
        "role": "user",
        "text": user_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    session["turns"].append({
        "role": "assistant",
        "text": ai_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    filepath = SESSIONS_DIR / f"{session_id}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(session, f, indent=2, ensure_ascii=False)

    logger.info(f"Turn added to session {session_id}: user={len(user_text)} chars, ai={len(ai_text)} chars")
    return session


def update_session(session: dict):
    session_id = session["session_id"]
    filepath = SESSIONS_DIR / f"{session_id}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(session, f, indent=2, ensure_ascii=False)


def save_user_progress(topic: str, level: str):
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {"last_topic": topic, "last_level": level}
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to write progress file {PROGRESS_FILE}: {e}")
        raise


def load_user_progress() -> dict:
    if not PROGRESS_FILE.exists():
        return {"last_topic": DEFAULT_TOPIC, "last_level": DEFAULT_LEVEL}
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Corrupted progress file {PROGRESS_FILE}: {e}")
        return {"last_topic": DEFAULT_TOPIC, "last_level": DEFAULT_LEVEL}

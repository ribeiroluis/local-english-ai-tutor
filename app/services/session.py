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
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(session, f, indent=2, ensure_ascii=False)

    save_user_progress(topic, level)
    logger.info(f"Session created: {session_id} (topic={topic}, level={level})")
    return session


def get_session(session_id: str) -> dict | None:
    filepath = SESSIONS_DIR / f"{session_id}.json"
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_user_progress(topic: str, level: str):
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {"last_topic": topic, "last_level": level}
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_user_progress() -> dict:
    if not PROGRESS_FILE.exists():
        return {"last_topic": DEFAULT_TOPIC, "last_level": DEFAULT_LEVEL}
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

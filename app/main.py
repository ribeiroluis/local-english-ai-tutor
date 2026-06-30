import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import settings
from app.services.logger import setup_logger
from app.services.session import create_session, load_user_progress
from app.services.stt import transcribe

logger = setup_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up")
    yield


app = FastAPI(title="English AI Tutor", lifespan=lifespan)

STATIC_DIR = Path(__file__).resolve().parent / "static"
TOPICS_FILE = Path(__file__).resolve().parent / "prompts" / "topics.json"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class StartSessionRequest(BaseModel):
    topic: str
    level: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/topics")
async def get_topics():
    try:
        with open(TOPICS_FILE, "r", encoding="utf-8") as f:
            topics = json.load(f)
    except FileNotFoundError:
        logger.error(f"Topics file not found: {TOPICS_FILE}")
        raise HTTPException(status_code=500, detail="Topics data not available")
    except json.JSONDecodeError:
        logger.error(f"Topics file corrupted: {TOPICS_FILE}")
        raise HTTPException(status_code=500, detail="Topics data corrupted")
    return [{"id": t["id"], "name": t["name"], "description": t["description"]} for t in topics]


@app.get("/api/progress")
async def get_progress():
    return load_user_progress()


@app.post("/api/sessions")
async def start_session(req: StartSessionRequest):
    session = create_session(req.topic, req.level)
    return {"session_id": session["session_id"]}


@app.get("/chat")
async def chat():
    return FileResponse(STATIC_DIR / "chat.html")


@app.post("/api/transcribe")
async def api_transcribe(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    result = transcribe(audio_bytes)
    return result

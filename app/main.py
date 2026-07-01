import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import settings
from app.services.llm import generate, generate_review
from app.services.logger import setup_logger
from app.services.session import (
    add_turn,
    create_session,
    get_session,
    load_user_progress,
    update_session,
)
from app.services.stt import transcribe
from app.services.tts import synthesize

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


class ReviewRequest(BaseModel):
    session_id: str


class ChatRequest(BaseModel):
    session_id: str
    text: str


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


@app.post("/api/transcribe")
async def api_transcribe(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    result = transcribe(audio_bytes)
    return result


@app.post("/api/converse")
async def api_converse(file: UploadFile = File(...), session_id: str = Form(...)):
    audio_bytes = await file.read()

    stt_result = transcribe(audio_bytes)
    user_text = stt_result.get("text", "")
    if not user_text:
        logger.warning(f"Empty transcription for session {session_id}")
        raise HTTPException(status_code=400, detail="Could not understand audio")

    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        topics = json.load(f)
    topic = next((t for t in topics if t["id"] == session["topic"]), topics[0])

    try:
        ai_reply = generate(topic["system_prompt"], session["level"], session["turns"], user_text)
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise HTTPException(status_code=502, detail=f"AI response failed: {str(e)}")

    try:
        audio_wav = synthesize(ai_reply)
        add_turn(session_id, user_text, ai_reply)
        return Response(
            content=audio_wav,
            media_type="audio/wav",
            headers={"X-Transcript": user_text, "X-Reply": ai_reply},
        )
    except Exception as e:
        logger.error(f"TTS failed for session {session_id}: {e}")
        add_turn(session_id, user_text, ai_reply)
        return Response(
            content=b"",
            media_type="audio/wav",
            headers={
                "X-Transcript": user_text,
                "X-Reply": ai_reply,
                "X-TTS-Error": str(e),
            },
        )


@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    session = get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        topics = json.load(f)
    topic = next((t for t in topics if t["id"] == session["topic"]), topics[0])

    try:
        ai_reply = generate(topic["system_prompt"], session["level"], session["turns"], req.text)
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise HTTPException(status_code=502, detail=f"AI response failed: {str(e)}")

    try:
        audio_wav = synthesize(ai_reply)
        add_turn(req.session_id, req.text, ai_reply)
        return Response(
            content=audio_wav,
            media_type="audio/wav",
            headers={"X-Reply": ai_reply},
        )
    except Exception as e:
        logger.error(f"TTS failed for session {req.session_id}: {e}")
        add_turn(req.session_id, req.text, ai_reply)
        return Response(
            content=b"",
            media_type="audio/wav",
            headers={"X-Reply": ai_reply, "X-TTS-Error": str(e)},
        )


@app.post("/api/review")
async def api_review(req: ReviewRequest):
    session = get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    corrections = generate_review(session)
    session["corrections"] = corrections
    update_session(session)

    return {"corrections": corrections}

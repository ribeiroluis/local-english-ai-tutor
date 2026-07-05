import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import settings
from app.services.llm import generate_opening, generate_review, generate_with_correction
from app.services.logger import setup_logger
from app.services.session import (
    add_opening_turn,
    add_turn,
    adjust_cefr_level,
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

_topics_cache: list[dict] | None = None


def _load_topics() -> list[dict]:
    global _topics_cache
    if _topics_cache is None:
        with open(TOPICS_FILE, "r", encoding="utf-8") as f:
            _topics_cache = json.load(f)
    return _topics_cache


def _get_topic(session: dict) -> dict:
    topics = _load_topics()
    if not topics:
        logger.error("No topics loaded")
        raise HTTPException(status_code=500, detail="No topics available")
    topic_id = session.get("topic", "")
    topic = next((t for t in topics if t["id"] == topic_id), None)
    if topic is None:
        logger.warning(f"Topic '{topic_id}' not found, falling back to first topic")
        topic = topics[0]
    return topic


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class StartSessionRequest(BaseModel):
    topic: str
    level: str
    user_name: str = ""
    llm_model: str = "qwen2.5:3b"
    context_turns: int = 10


class StartConversationRequest(BaseModel):
    session_id: str


class ReviewRequest(BaseModel):
    session_id: str


class ChatRequest(BaseModel):
    session_id: str
    text: str
    llm_model: str = "qwen2.5:3b"
    context_turns: int = 10


class TTSRequest(BaseModel):
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
        topics = _load_topics()
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
    session = create_session(req.topic, req.level, user_name=req.user_name, llm_model=req.llm_model, context_turns=req.context_turns)
    return {"session_id": session["session_id"]}


@app.post("/api/start")
async def api_start(req: StartConversationRequest):
    session = get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    topic = _get_topic(session)
    llm_model = session.get("llm_model", "qwen2.5:3b")
    user_name = session.get("user_name", "")

    try:
        result = generate_opening(topic["system_prompt"], session["level"], user_name=user_name, llm_model=llm_model)
    except Exception as e:
        logger.error(f"Opening generation failed: {e}")
        raise HTTPException(status_code=502, detail=f"Opening failed: {str(e)}")

    try:
        add_opening_turn(req.session_id, result["reply"], session=session)
    except Exception as e:
        logger.error(f"Failed to persist opening turn for session {req.session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to persist opening turn: {str(e)}")

    return {"reply": result["reply"]}


@app.post("/api/transcribe")
async def api_transcribe(file: UploadFile = File(...), beam_size: int = Form(5), stt_model: str = Form("base.en")):
    audio_bytes = await file.read()
    result = transcribe(audio_bytes, beam_size=beam_size, model_size=stt_model)
    return result


@app.post("/api/converse")
async def api_converse(file: UploadFile = File(...), session_id: str = Form(...), beam_size: int = Form(5), stt_model: str = Form("base.en")):
    audio_bytes = await file.read()

    stt_result = transcribe(audio_bytes, beam_size=beam_size, model_size=stt_model)
    user_text = stt_result.get("text", "")
    if not user_text:
        logger.warning(f"Empty transcription for session {session_id}")
        raise HTTPException(status_code=400, detail="Could not understand audio")

    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    topic = _get_topic(session)
    user_name = session.get("user_name", "")

    try:
        result = generate_with_correction(
            topic["system_prompt"], session["level"], session["turns"], user_text,
            user_name=user_name,
            llm_model=session.get("llm_model", "qwen2.5:3b"),
            context_window=session.get("context_turns", 10),
        )
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise HTTPException(status_code=502, detail=f"AI response failed: {str(e)}")

    try:
        add_turn(session_id, user_text, result["reply"], correction=result.get("correction"), session=session)
    except Exception as e:
        logger.error(f"Failed to persist turn for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to persist turn: {str(e)}")

    return {
        "transcript": user_text,
        "reply": result["reply"],
        "correction": result.get("correction"),
    }


@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    session = get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    topic = _get_topic(session)
    user_name = session.get("user_name", "")

    try:
        result = generate_with_correction(
            topic["system_prompt"], session["level"], session["turns"], req.text,
            user_name=user_name,
            llm_model=req.llm_model,
            context_window=req.context_turns,
        )
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise HTTPException(status_code=502, detail=f"AI response failed: {str(e)}")

    try:
        add_turn(req.session_id, req.text, result["reply"], correction=result.get("correction"), session=session)
    except Exception as e:
        logger.error(f"Failed to persist turn for session {req.session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to persist turn: {str(e)}")

    return {
        "transcript": req.text,
        "reply": result["reply"],
        "correction": result.get("correction"),
    }


@app.post("/api/tts")
async def api_tts(req: TTSRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    try:
        audio_wav = synthesize(req.text)
        return Response(content=audio_wav, media_type="audio/wav")
    except Exception as e:
        logger.error(f"TTS failed: {e}")
        raise HTTPException(status_code=502, detail=f"TTS failed: {str(e)}")


@app.post("/api/review")
async def api_review(req: ReviewRequest):
    session = get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    summary = generate_review(session)
    session["review_summary"] = summary
    update_session(session)

    try:
        level_adjustment = adjust_cefr_level(req.session_id)
    except (ValueError, IOError, OSError) as e:
        logger.error(f"CEFR adjustment failed: {e}")
        raise HTTPException(status_code=500, detail=f"CEFR level adjustment failed: {str(e)}")

    return {"summary": summary, "level_adjustment": level_adjustment}

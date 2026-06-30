from fastapi import FastAPI
from app.config import settings
from app.services.logger import setup_logger

logger = setup_logger()

app = FastAPI(title="English AI Tutor")


@app.on_event("startup")
async def startup():
    logger.info("Application starting up")


@app.get("/health")
async def health():
    return {"status": "ok"}

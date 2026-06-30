from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.services.logger import setup_logger

logger = setup_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up")
    yield


app = FastAPI(title="English AI Tutor", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}

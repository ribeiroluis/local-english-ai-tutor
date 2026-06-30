import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Settings:
    port: int = int(os.getenv("PORT", "8000"))
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    whisper_model_size: str = os.getenv("WHISPER_MODEL_SIZE", "base.en")
    piper_voice_path: str = os.getenv("PIPER_VOICE_PATH", "")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    port: int = int(os.getenv("PORT", "8000"))
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    whisper_model_size: str = os.getenv("WHISPER_MODEL_SIZE", "base.en")
    piper_voice_path: str = os.getenv("PIPER_VOICE_PATH", "")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()

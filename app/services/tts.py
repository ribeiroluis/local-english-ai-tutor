import io
import subprocess
import wave
from pathlib import Path

from app.config import settings
from app.services.logger import setup_logger

logger = setup_logger()

PIPER_RATE = 22050


def synthesize(text: str) -> bytes:
    voice_path = settings.piper_voice_path
    if not voice_path or not Path(voice_path).exists():
        logger.error(f"Piper voice file not found: {voice_path}")
        raise FileNotFoundError(f"Piper voice file not found: {voice_path}")

    try:
        proc = subprocess.run(
            ["piper", "--model", voice_path, "--output-raw"],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        logger.error("Piper TTS timed out")
        raise
    except FileNotFoundError:
        logger.error("Piper executable not found in PATH")
        raise

    if proc.returncode != 0:
        stderr = proc.stderr.decode().strip()
        logger.error(f"Piper failed: {stderr}")
        raise RuntimeError(f"Piper TTS failed: {stderr}")

    raw_audio = proc.stdout
    duration_sec = len(raw_audio) / (2 * PIPER_RATE)

    wav_buf = io.BytesIO()
    with wave.open(wav_buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(PIPER_RATE)
        wf.writeframes(raw_audio)

    wav_bytes = wav_buf.getvalue()
    logger.info(f"TTS synthesized: {len(text)} chars -> {len(wav_bytes)} bytes, {duration_sec:.2f}s")
    return wav_bytes

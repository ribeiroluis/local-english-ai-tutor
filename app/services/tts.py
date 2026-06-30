import io
import wave
from pathlib import Path

import numpy as np
from piper import PiperVoice

from app.config import settings
from app.services.logger import setup_logger

logger = setup_logger()

PIPER_RATE = 22050


_voice: PiperVoice | None = None


def _get_voice() -> PiperVoice:
    global _voice
    if _voice is None:
        voice_path = settings.piper_voice_path
        if not voice_path or not Path(voice_path).exists():
            logger.error(f"Piper voice file not found: {voice_path}")
            raise FileNotFoundError(f"Piper voice file not found: {voice_path}")
        logger.info(f"Loading Piper voice from {voice_path}")
        _voice = PiperVoice.load(voice_path)
        logger.info("Piper voice loaded")
    return _voice


def synthesize(text: str) -> bytes:
    voice = _get_voice()

    audio_chunks = list(voice.synthesize(text))
    audio_float = np.concatenate([chunk.audio_float_array for chunk in audio_chunks])

    audio_int16 = (audio_float * 32767).astype(np.int16)

    wav_buf = io.BytesIO()
    with wave.open(wav_buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(PIPER_RATE)
        wf.writeframes(audio_int16.tobytes())

    wav_bytes = wav_buf.getvalue()
    duration_sec = len(audio_int16) / PIPER_RATE
    logger.info(f"TTS synthesized: {len(text)} chars -> {len(wav_bytes)} bytes, {duration_sec:.2f}s")
    return wav_bytes

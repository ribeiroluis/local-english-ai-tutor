from faster_whisper import WhisperModel

from app.config import settings
from app.services.logger import setup_logger

logger = setup_logger()

_model = None


def _get_model():
    global _model
    if _model is None:
        logger.info(f"Loading whisper model: {settings.whisper_model_size}")
        _model = WhisperModel(settings.whisper_model_size, device="cpu", compute_type="int8")
        logger.info("Whisper model loaded")
    return _model


def transcribe(audio_bytes: bytes) -> dict:
    import io
    import wave

    model = _get_model()

    try:
        with io.BytesIO(audio_bytes) as buf:
            with wave.open(buf, "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                sample_rate = wf.getframerate()
                width = wf.getsampwidth()
                nframes = wf.getnframes()

        audio_sec = nframes / sample_rate if sample_rate else 0
        logger.info(f"Decoded WAV: {sample_rate}Hz, {width*8}bit, {nframes} frames, {audio_sec:.2f}s")

        import numpy as np
        dtype = {1: np.int16, 2: np.int16, 4: np.int32}.get(width, np.int16)
        audio = np.frombuffer(frames, dtype=dtype).astype(np.float32) / 32768.0
    except Exception as e:
        logger.error(f"Failed to decode audio: {e}")
        return {"text": "", "confidence": 0.0, "duration_sec": 0.0, "error": str(e)}

    segments, info = model.transcribe(audio, beam_size=5, language="en")
    result = list(segments)

    text = " ".join(seg.text for seg in result) if result else ""
    confidence = round(float(max(seg.avg_logprob for seg in result)), 4) if result else 0.0
    duration_sec = round(info.duration, 2) if info.duration else 0.0

    if not text:
        logger.warning(f"Empty transcription: confidence={confidence}, duration={duration_sec}s, audio_len={audio_sec:.2f}s")
    else:
        logger.info(f"Transcribed: {len(text)} chars, confidence={confidence}, duration={duration_sec}s")

    return {"text": text, "confidence": confidence, "duration_sec": duration_sec}

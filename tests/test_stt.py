import os
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "audio"


def test_transcribe_empty_audio(client):
    import struct
    import wave
    import io

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(struct.pack("<h", 0) * 1600)
    buf.seek(0)

    response = client.post("/api/transcribe", files={"file": ("silence.wav", buf, "audio/wav")})
    assert response.status_code == 200
    data = response.json()
    assert "text" in data


@pytest.mark.skipif(
    not any(FIXTURE_DIR.glob("*.wav")),
    reason="No WAV fixtures in tests/fixtures/audio/",
)
def test_transcribe_normal_speech(client):
    wav_path = next(FIXTURE_DIR.glob("*.wav"), None)
    if not wav_path:
        pytest.skip("No WAV fixture available")
    with open(wav_path, "rb") as f:
        response = client.post("/api/transcribe", files={"file": f})
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert "confidence" in data
    assert "duration_sec" in data


def test_transcribe_invalid_format(client):
    response = client.post("/api/transcribe", files={"file": ("test.txt", b"not audio", "text/plain")})
    assert response.status_code == 200
    data = response.json()
    assert "error" in data

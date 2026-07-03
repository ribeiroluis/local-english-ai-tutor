from unittest.mock import patch

from app.services import tts
from app.services.tts import synthesize


def test_tts_endpoint_success(client):
    tts._voice = None
    with patch("app.services.tts.PiperVoice") as mock_pv:
        mock_voice = mock_pv.load.return_value
        mock_chunk = mock_voice.synthesize.return_value
        import numpy as np
        from unittest.mock import MagicMock
        chunk = MagicMock()
        chunk.audio_float_array = np.array([0.0, 0.1, -0.1, 0.0], dtype=np.float32)
        mock_chunk.__iter__.return_value = [chunk]

        response = client.post("/api/tts", json={"text": "Hello world"})
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"
        assert len(response.content) > 44


def test_tts_endpoint_empty_text(client):
    response = client.post("/api/tts", json={"text": ""})
    assert response.status_code == 400


def test_review_endpoint_no_turns(client):
    resp = client.post("/api/sessions", json={"topic": "small-talk", "level": "A2"})
    session_id = resp.json()["session_id"]

    with patch("app.services.llm._ollama_chat") as mock_chat:
        mock_chat.return_value = '{"total_errors": 0, "by_type": {}, "topics_to_review": []}'
        response = client.post("/api/review", json={"session_id": session_id})
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert data["summary"]["total_errors"] == 0


def test_review_endpoint_unknown_session(client):
    response = client.post("/api/review", json={"session_id": "nonexistent"})
    assert response.status_code == 404


def test_converse_endpoint_returns_json(client):
    resp = client.post("/api/sessions", json={"topic": "small-talk", "level": "A2"})
    session_id = resp.json()["session_id"]

    import wave
    import io
    import numpy as np

    wav_buf = io.BytesIO()
    with wave.open(wav_buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(np.zeros(1600, dtype=np.int16).tobytes())
    wav_bytes = wav_buf.getvalue()

    with patch("app.main.transcribe") as mock_stt:
        mock_stt.return_value = {"text": "Hello", "confidence": 0.9, "duration_sec": 0.1}
        with patch("app.main.generate_with_correction") as mock_llm:
            mock_llm.return_value = {"reply": "Hi there!", "correction": None}
            response = client.post(
                "/api/converse",
                data={"session_id": session_id},
                files={"file": ("test.wav", wav_bytes, "audio/wav")},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["transcript"] == "Hello"
            assert data["reply"] == "Hi there!"
            assert data["correction"] is None


def test_review_endpoint_returns_level_adjustment(client):
    resp = client.post("/api/sessions", json={"topic": "small-talk", "level": "B1"})
    session_id = resp.json()["session_id"]

    from app.services.session import add_turn
    for i in range(6):
        add_turn(session_id, f"turn {i}", "OK", correction=None)

    with patch("app.services.llm._ollama_chat") as mock_chat:
        mock_chat.return_value = '{"total_errors": 0, "by_type": {}, "topics_to_review": []}'
        response = client.post("/api/review", json={"session_id": session_id})
        assert response.status_code == 200
        data = response.json()
        assert "level_adjustment" in data
        assert data["level_adjustment"]["from"] == "B1"
        assert data["level_adjustment"]["to"] == "B2"

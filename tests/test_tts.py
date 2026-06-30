from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services import tts
from app.services.tts import synthesize


def _make_chunk(audio: np.ndarray):
    chunk = MagicMock()
    chunk.audio_float_array = audio
    return chunk


@pytest.fixture(autouse=True)
def _clear_voice_cache():
    tts._voice = None


@pytest.fixture
def mock_path(tmp_path):
    """Create a real temp file to use as a fake voice path."""
    voice_file = tmp_path / "voice.onnx"
    voice_file.write_text("fake model")
    return str(voice_file)


@patch("app.services.tts.PiperVoice")
def test_synthesize_success(mock_pv, mock_path):
    voice_path = mock_path
    mock_voice = MagicMock()
    mock_pv.load.return_value = mock_voice

    audio = np.array([0.0, 0.1, -0.1, 0.0], dtype=np.float32)
    mock_voice.synthesize.return_value = [_make_chunk(audio)]

    with patch("app.services.tts.settings") as mock_settings:
        mock_settings.piper_voice_path = voice_path
        result = synthesize("Hello world")

    assert isinstance(result, bytes)
    assert len(result) > 44
    mock_voice.synthesize.assert_called_once_with("Hello world")


@patch("app.services.tts.settings")
def test_synthesize_voice_not_found(mock_settings):
    mock_settings.piper_voice_path = ""

    with pytest.raises(FileNotFoundError, match="Piper voice file not found"):
        synthesize("Hello")


@patch("app.services.tts.PiperVoice")
def test_synthesize_piper_fails(mock_pv, mock_path):
    voice_path = mock_path
    mock_pv.load.side_effect = RuntimeError("ONNX error")

    with patch("app.services.tts.settings") as mock_settings:
        mock_settings.piper_voice_path = voice_path
        with pytest.raises(RuntimeError, match="ONNX error"):
            synthesize("Hello")


@patch("app.services.tts.PiperVoice")
def test_synthesize_multiple_chunks(mock_pv, mock_path):
    voice_path = mock_path
    mock_voice = MagicMock()
    mock_pv.load.return_value = mock_voice

    chunk1 = _make_chunk(np.array([0.0, 0.5], dtype=np.float32))
    chunk2 = _make_chunk(np.array([-0.5, 0.0], dtype=np.float32))
    mock_voice.synthesize.return_value = [chunk1, chunk2]

    with patch("app.services.tts.settings") as mock_settings:
        mock_settings.piper_voice_path = voice_path
        result = synthesize("Hello world")

    assert isinstance(result, bytes)
    assert len(result) > 44


@patch("app.services.tts.PiperVoice")
def test_synthesize_empty_text(mock_pv, mock_path):
    voice_path = mock_path
    mock_voice = MagicMock()
    mock_pv.load.return_value = mock_voice

    mock_voice.synthesize.return_value = []

    with patch("app.services.tts.settings") as mock_settings:
        mock_settings.piper_voice_path = voice_path
        with pytest.raises(ValueError, match="need at least one array"):
            synthesize("")

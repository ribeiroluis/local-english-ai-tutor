import subprocess
from unittest.mock import patch

import pytest

from app.services.tts import synthesize

SIXTEEN_BIT_SILENCE = b"\x00\x00" * 22050  # 1 second of silence at 22050Hz


@patch("app.services.tts.settings")
def test_synthesize_success(mock_settings):
    mock_settings.piper_voice_path = "/fake/voice/path"

    with patch("pathlib.Path.exists", return_value=True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = SIXTEEN_BIT_SILENCE
        mock_run.return_value.stderr = b""

        result = synthesize("Hello world")
        assert isinstance(result, bytes)
        assert len(result) > 44  # WAV header + data

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "piper"
        assert "--model" in args


@patch("app.services.tts.settings")
def test_synthesize_voice_not_found(mock_settings):
    mock_settings.piper_voice_path = ""

    with pytest.raises(FileNotFoundError, match="Piper voice file not found"):
        synthesize("Hello")


@patch("app.services.tts.settings")
def test_synthesize_piper_not_found(mock_settings):
    mock_settings.piper_voice_path = "/fake/voice/path"

    with patch("pathlib.Path.exists", return_value=True), \
         patch("subprocess.run", side_effect=FileNotFoundError("piper not found")):
        with pytest.raises(FileNotFoundError, match="piper not found"):
            synthesize("Hello")


@patch("app.services.tts.settings")
def test_synthesize_piper_fails(mock_settings):
    mock_settings.piper_voice_path = "/fake/voice/path"

    with patch("pathlib.Path.exists", return_value=True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = b""
        mock_run.return_value.stderr = b"model file not found"

        with pytest.raises(RuntimeError, match="Piper TTS failed"):
            synthesize("Hello")


@patch("app.services.tts.settings")
def test_synthesize_timeout(mock_settings):
    mock_settings.piper_voice_path = "/fake/voice/path"

    with patch("pathlib.Path.exists", return_value=True), \
         patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="piper", timeout=30)):
        with pytest.raises(subprocess.TimeoutExpired):
            synthesize("Hello")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import session


@pytest.fixture(autouse=True)
def temp_data(monkeypatch, tmp_path):
    tmp_progress = tmp_path / "user_progress.json"
    tmp_sessions = tmp_path / "sessions"
    tmp_sessions.mkdir()
    monkeypatch.setattr(session, "PROGRESS_FILE", tmp_progress)
    monkeypatch.setattr(session, "SESSIONS_DIR", tmp_sessions)


@pytest.fixture
def client():
    return TestClient(app)

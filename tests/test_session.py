import json
from pathlib import Path

import pytest

from app.services.session import (
    CEFR_LEVELS,
    add_opening_turn,
    add_turn,
    adjust_cefr_level,
    create_session,
    get_session,
    load_user_progress,
)


def test_add_turn(client):
    resp = client.post("/api/sessions", json={"topic": "travel", "level": "B1"})
    session_id = resp.json()["session_id"]

    session = add_turn(session_id, "Hello", "Hi there!")
    assert len(session["turns"]) == 2
    assert session["turns"][0]["role"] == "user"
    assert session["turns"][0]["text"] == "Hello"
    assert session["turns"][1]["role"] == "assistant"
    assert session["turns"][1]["text"] == "Hi there!"


def test_add_turn_session_not_found():
    with pytest.raises(ValueError, match="Session not found"):
        add_turn("invalid-id", "Hello", "Hi")


def test_add_turn_persists_to_json(client):
    resp = client.post("/api/sessions", json={"topic": "restaurant", "level": "A2"})
    session_id = resp.json()["session_id"]

    add_turn(session_id, "I want pizza", "What topping would you like?")

    session = get_session(session_id)
    assert session is not None
    assert len(session["turns"]) == 2
    assert session["turns"][0]["text"] == "I want pizza"


def test_add_turn_multiple_turns(client):
    resp = client.post("/api/sessions", json={"topic": "hobbies", "level": "B1"})
    session_id = resp.json()["session_id"]

    add_turn(session_id, "I like reading", "What do you read?")
    add_turn(session_id, "Fantasy books", "Great choice!")

    session = get_session(session_id)
    assert len(session["turns"]) == 4


def test_add_turn_includes_timestamp(client):
    resp = client.post("/api/sessions", json={"topic": "small-talk", "level": "A1"})
    session_id = resp.json()["session_id"]

    session = add_turn(session_id, "Hi", "Hello")
    assert "timestamp" in session["turns"][0]
    assert "timestamp" in session["turns"][1]


def test_add_opening_turn(client):
    resp = client.post("/api/sessions", json={"topic": "small-talk", "level": "A2"})
    session_id = resp.json()["session_id"]

    session = add_opening_turn(session_id, "Hello! How was your day?")
    assert len(session["turns"]) == 1
    assert session["turns"][0]["role"] == "assistant"
    assert session["turns"][0]["text"] == "Hello! How was your day?"


def test_add_opening_turn_persists_to_json(client):
    resp = client.post("/api/sessions", json={"topic": "small-talk", "level": "A2"})
    session_id = resp.json()["session_id"]

    add_opening_turn(session_id, "Welcome! What brings you here?")
    session = get_session(session_id)
    assert session is not None
    assert len(session["turns"]) == 1
    assert session["turns"][0]["text"] == "Welcome! What brings you here?"


def test_add_opening_turn_session_not_found():
    with pytest.raises(ValueError, match="Session not found"):
        add_opening_turn("invalid-id", "Hello")


def test_add_opening_turn_initializes_missing_turns(client):
    resp = client.post("/api/sessions", json={"topic": "small-talk", "level": "A2"})
    session_id = resp.json()["session_id"]

    session = get_session(session_id)
    del session["turns"]
    session = add_opening_turn(session_id, "Starting now!", session=session)
    assert len(session["turns"]) == 1


def _build_session_with_errors(client, level: str, error_ratio: float, total_turns: int = 6) -> str:
    resp = client.post("/api/sessions", json={"topic": "small-talk", "level": level})
    session_id = resp.json()["session_id"]

    error_turns = max(1, round(total_turns * error_ratio))
    for i in range(total_turns):
        user_text = "I has error" if i < error_turns else "I have no error"
        correction = {"original": "I has error", "corrected": "I have an error", "explanation_pt": "Teste.", "error_type": "grammar"} if i < error_turns else None
        add_turn(session_id, user_text, "OK", correction=correction)
    return session_id


class TestCefrAdjustment:
    def test_error_ratio_50pct_goes_down(self, client):
        session_id = _build_session_with_errors(client, "B1", 0.5, 6)
        result = adjust_cefr_level(session_id)
        assert result["to"] == "A2"
        assert result["from"] == "B1"

    def test_error_ratio_5pct_goes_up(self, client):
        session_id = _build_session_with_errors(client, "B1", 0.05, 20)
        result = adjust_cefr_level(session_id)
        assert result["to"] == "B2"
        assert result["from"] == "B1"

    def test_error_ratio_25pct_stays_same(self, client):
        session_id = _build_session_with_errors(client, "B1", 0.25, 8)
        result = adjust_cefr_level(session_id)
        assert result["to"] == "B1"
        assert result["from"] == "B1"

    def test_never_below_a1(self, client):
        session_id = _build_session_with_errors(client, "A1", 0.5, 6)
        result = adjust_cefr_level(session_id)
        assert result["to"] == "A1"

    def test_never_above_c2(self, client):
        session_id = _build_session_with_errors(client, "C2", 0.0, 6)
        result = adjust_cefr_level(session_id)
        assert result["to"] == "C2"

    def test_zero_user_turns_keeps_level(self, client):
        resp = client.post("/api/sessions", json={"topic": "small-talk", "level": "B1"})
        session_id = resp.json()["session_id"]
        result = adjust_cefr_level(session_id)
        assert result["to"] == "B1"
        assert result["total_turns"] == 0

    def test_persists_to_progress_file(self, client):
        session_id = _build_session_with_errors(client, "B1", 0.5, 6)
        adjust_cefr_level(session_id)
        progress = load_user_progress()
        assert progress["current_cefr"] == "A2"
        assert progress["total_sessions"] >= 1

    def test_accumulates_errors_by_type(self, client):
        session_id = _build_session_with_errors(client, "B1", 0.5, 6)
        adjust_cefr_level(session_id)
        progress = load_user_progress()
        assert progress["errors_by_type"].get("grammar", 0) >= 1

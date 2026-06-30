import json
from pathlib import Path

import pytest

from app.services.session import add_turn, create_session, get_session


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

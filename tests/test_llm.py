from unittest.mock import patch

import httpx
import pytest

from app.services.llm import LEVEL_INSTRUCTIONS, build_messages, generate, generate_review


class TestBuildMessages:
    def test_build_messages_a1(self):
        messages = build_messages("Be friendly.", "A1", [], "hello")
        system = messages[0]["content"]
        assert "simple sentences" in system
        assert "A1" in system

    def test_build_messages_c2(self):
        messages = build_messages("Be friendly.", "C2", [], "hello")
        system = messages[0]["content"]
        assert "native-level" in system
        assert "C2" in system

    def test_build_messages_includes_system_first(self):
        messages = build_messages("Custom prompt.", "B1", [], "hello")
        assert messages[0]["role"] == "system"

    def test_build_messages_context_window(self):
        turns = [{"text": f"turn {i}", "role": "user" if i % 2 == 0 else "assistant"} for i in range(20)]
        messages = build_messages("Test.", "A2", turns, "final")
        history_roles = [m["role"] for m in messages[1:-1]]
        assert history_roles.count("user") == 10
        assert history_roles.count("assistant") == 10

    def test_build_messages_context_window_truncated(self):
        turns = [{"text": f"turn {i}", "role": "user" if i % 2 == 0 else "assistant"} for i in range(50)]
        messages = build_messages("Test.", "B1", turns, "final")
        history_contents = [m["content"] for m in messages[1:-1]]
        assert len(history_contents) == 20
        assert history_contents[0] == "turn 30"
        assert history_contents[-1] == "turn 49"

    def test_build_messages_unknown_level(self):
        messages = build_messages("Test.", "UNKNOWN", [], "hello")
        system = messages[0]["content"]
        assert "natural conversational English" in system

    def test_build_messages_empty_turns(self):
        messages = build_messages("Test.", "A2", [], "hello")
        assert len(messages) == 2
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "hello"


class TestGenerate:
    def test_generate_success(self):
        mock_response = {
            "message": {"content": " Hello, how are you? "},
            "done": True,
        }

        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_instance.post.return_value.json.return_value = mock_response

            reply = generate("Be friendly.", "A2", [], "hello")
            assert reply == "Hello, how are you?"

    def test_generate_connection_error(self):
        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.side_effect = httpx.RequestError("Connection refused")

            with pytest.raises(httpx.RequestError):
                generate("Be friendly.", "A2", [], "hello")

    def test_generate_missing_key_in_response(self):
        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_instance.post.return_value.json.return_value = {"done": True}

            with pytest.raises(KeyError):
                generate("Be friendly.", "A2", [], "hello")

    def test_generate_passes_correct_url(self):
        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_instance.post.return_value.json.return_value = {"message": {"content": "ok"}}

            generate("Prompt.", "B1", [], "hi")
            call_url = mock_instance.post.call_args[0][0]
            assert "api/chat" in call_url


class TestGenerateReview:
    def test_generate_review_no_user_turns(self):
        session = {"turns": [{"role": "assistant", "text": "Hi"}]}
        assert generate_review(session) == []

    def test_generate_review_success(self):
        session = {
            "turns": [
                {"role": "user", "text": "I go to school yesterday"},
                {"role": "assistant", "text": "I went to school yesterday. That's great!"},
            ]
        }
        mock_corrections = [
            {
                "original_text": "I go to school yesterday",
                "corrected_text": "I went to school yesterday",
                "error_type": "verb_tense",
                "explanation_pt": "Use 'went' no passado",
            }
        ]

        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_instance.post.return_value.json.return_value = {
                "message": {"content": '[{"original_text": "I go to school yesterday", "corrected_text": "I went to school yesterday", "error_type": "verb_tense", "explanation_pt": "Use went no passado"}]'}
            }

            result = generate_review(session)
            assert len(result) == 1
            assert result[0]["error_type"] == "verb_tense"

    def test_generate_review_invalid_json_response(self):
        session = {
            "turns": [
                {"role": "user", "text": "Hello"},
                {"role": "assistant", "text": "Hi there!"},
            ]
        }

        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_instance.post.return_value.json.return_value = {
                "message": {"content": "not valid json"}
            }

            result = generate_review(session)
            assert result == []

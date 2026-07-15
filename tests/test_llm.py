from unittest.mock import patch

import httpx
import pytest

from app.services.llm import FALLBACK_MSG, LEVEL_INSTRUCTIONS, build_messages, generate_opening, generate_review, generate_with_correction


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


class TestGenerateOpening:
    def test_opening_success(self):
        mock_response = {
            "message": {
                "content": '{"reply": "Hi there! How are you today?"}'
            },
        }
        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_instance.post.return_value.json.return_value = mock_response

            result = generate_opening("Be friendly.", "A2")
            assert result["reply"] == "Hi there! How are you today?"

    def test_opening_includes_user_name(self):
        mock_response = {
            "message": {
                "content": '{"reply": "Hello John! Ready to practice?"}'
            },
        }
        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_instance.post.return_value.json.return_value = mock_response

            result = generate_opening("Be friendly.", "B1", user_name="John")
            assert result["reply"] == "Hello John! Ready to practice?"

    def test_opening_empty_reply_field_fallback(self):
        mock_response = {
            "message": {
                "content": '{"reply": ""}'
            },
        }
        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_instance.post.return_value.json.return_value = mock_response

            result = generate_opening("Be friendly.", "A1")
            assert result["reply"] == FALLBACK_MSG

    def test_opening_invalid_json_fallback(self):
        mock_response = {
            "message": {
                "content": "not valid json at all"
            },
        }
        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_instance.post.return_value.json.return_value = mock_response

            result = generate_opening("Be friendly.", "A2")
            assert result["reply"] == FALLBACK_MSG

    def test_opening_missing_reply_field_fallback(self):
        mock_response = {
            "message": {
                "content": '{"correction": null}'
            },
        }
        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_instance.post.return_value.json.return_value = mock_response

            result = generate_opening("Be friendly.", "B2")
            assert result["reply"] == FALLBACK_MSG

    def test_opening_passes_format_json(self):
        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_instance.post.return_value.json.return_value = {
                "message": {"content": '{"reply": "Hello!"}'}
            }

            generate_opening("Prompt.", "A2")
            call_kwargs = mock_instance.post.call_args[1]
            assert call_kwargs["json"].get("format") == "json"


class TestGenerateWithCorrection:
    def test_success_with_correction(self):
        mock_response = {
            "message": {
                "content": '{"reply": "I went to the park too!", "correction": {"original": "I go to park", "corrected": "I went to the park", "explanation_pt": "Use passado simples.", "error_type": "verb_tense"}}'
            },
        }

        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_instance.post.return_value.json.return_value = mock_response

            result = generate_with_correction("Be friendly.", "A2", [], "I go to park")
            assert result["reply"] == "I went to the park too!"
            assert result["correction"]["error_type"] == "verb_tense"
            assert result["correction"]["corrected"] == "I went to the park"

    def test_success_no_correction(self):
        mock_response = {
            "message": {
                "content": '{"reply": "Hello! How are you?", "correction": null}'
            },
        }

        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_instance.post.return_value.json.return_value = mock_response

            result = generate_with_correction("Be friendly.", "A2", [], "Hello")
            assert result["reply"] == "Hello! How are you?"
            assert result["correction"] is None

    def test_connection_error(self):
        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.side_effect = httpx.RequestError("Connection refused")

            with pytest.raises(httpx.RequestError):
                generate_with_correction("Be friendly.", "A2", [], "hello")

    def test_invalid_json_fallback(self):
        mock_response = {
            "message": {"content": "This is not JSON but a plain text reply"},
        }

        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_instance.post.return_value.json.return_value = mock_response

            result = generate_with_correction("Be friendly.", "A2", [], "hello")
            assert result["reply"] == "This is not JSON but a plain text reply"
            assert result["correction"] is None

    def test_passes_format_json(self):
        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_instance.post.return_value.json.return_value = {
                "message": {"content": '{"reply": "ok", "correction": null}'}
            }

            generate_with_correction("Prompt.", "B1", [], "hi")
            call_kwargs = mock_instance.post.call_args[1]
            assert call_kwargs["json"].get("format") == "json"


class TestGenerateReview:
    def test_generate_review_no_user_turns(self):
        session = {"turns": [{"role": "assistant", "text": "Hi"}]}
        result = generate_review(session)
        assert result == {"total_errors": 0, "by_type": {}, "topics_to_review": []}

    def test_generate_review_computes_stats_locally(self):
        session = {
            "turns": [
                {
                    "role": "user", "text": "I go to school yesterday",
                    "correction": {
                        "original": "I go to school yesterday",
                        "corrected": "I went to school yesterday",
                        "explanation_pt": "Use passado simples 'went'.",
                        "error_type": "verb_tense",
                    },
                },
                {"role": "assistant", "text": "That's great!"},
                {
                    "role": "user", "text": "He don't like it",
                    "correction": {
                        "original": "He don't like it",
                        "corrected": "He doesn't like it",
                        "explanation_pt": "Use 'doesn't' com he/she/it.",
                        "error_type": "agreement",
                    },
                },
                {"role": "assistant", "text": "You're right!"},
            ]
        }

        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_instance.post.return_value.json.return_value = {
                "message": {"content": '{"topics_to_review": ["Past simple tense", "Subject-verb agreement"]}'}
            }

            result = generate_review(session)
            assert result["total_errors"] == 2
            assert result["by_type"]["verb_tense"] == 1
            assert result["by_type"]["agreement"] == 1
            assert "Past simple tense" in result["topics_to_review"]

    def test_generate_review_no_errors_return_early(self):
        session = {
            "turns": [
                {"role": "user", "text": "Hello", "correction": None},
                {"role": "assistant", "text": "Hi there!"},
            ]
        }
        result = generate_review(session)
        assert result == {"total_errors": 0, "by_type": {}, "topics_to_review": []}

    def test_generate_review_invalid_json_fallback(self):
        session = {
            "turns": [
                {
                    "role": "user", "text": "I go to school yesterday",
                    "correction": {
                        "original": "I go to school yesterday",
                        "corrected": "I went to school yesterday",
                        "explanation_pt": "Use passado simples.",
                        "error_type": "verb_tense",
                    },
                },
                {"role": "assistant", "text": "That's great!"},
            ]
        }

        with patch("httpx.Client") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_instance.post.return_value.json.return_value = {
                "message": {"content": "not valid json"}
            }

            result = generate_review(session)
            assert result["total_errors"] == 1
            assert result["by_type"]["verb_tense"] == 1
            assert result["topics_to_review"] == []

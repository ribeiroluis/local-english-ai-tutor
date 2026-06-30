import httpx
from app.config import settings
from app.services.logger import setup_logger

logger = setup_logger()

OLLAMA_MODEL = "qwen2.5:3b"
OLLAMA_TIMEOUT = 30.0

LEVEL_INSTRUCTIONS = {
    "A1": "Use very simple sentences and basic vocabulary. Speak slowly and clearly. Keep responses under 3 sentences.",
    "A2": "Use simple sentences. Avoid complex grammar. Keep responses under 4 sentences.",
    "B1": "Use moderate complexity. Natural conversational English.",
    "B2": "Use natural conversational English. Occasional idioms are okay.",
    "C1": "Use sophisticated vocabulary and natural idioms.",
    "C2": "Use native-level English with full complexity.",
}


def build_messages(topic_prompt: str, level: str, context_turns: list[dict], user_text: str) -> list[dict]:
    level_instruction = LEVEL_INSTRUCTIONS.get(level, "Use natural conversational English.")
    system = f"{topic_prompt}\n\nLevel: {level}. {level_instruction}"

    messages = [{"role": "system", "content": system}]

    for turn in context_turns[-10:]:
        messages.append({"role": "user", "content": turn["text"]})
        messages.append({"role": "assistant", "content": turn["text"]})

    messages.append({"role": "user", "content": user_text})
    return messages


def generate(topic_prompt: str, level: str, context_turns: list[dict], user_text: str) -> str:
    messages = build_messages(topic_prompt, level, context_turns, user_text)

    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            resp = client.post(
                f"{settings.ollama_host}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": messages,
                    "stream": False,
                },
            )
        resp.raise_for_status()
        data = resp.json()
        reply = data["message"]["content"].strip()
        logger.info(f"LLM reply: {len(reply)} chars")
        return reply
    except httpx.RequestError as e:
        logger.error(f"Ollama request failed: {e}")
        raise
    except (KeyError, ValueError) as e:
        logger.error(f"Failed to parse Ollama response: {e}")
        raise


def generate_review(session: dict) -> list[dict]:
    user_turns = [t for t in session["turns"] if t["role"] == "user"]
    if not user_turns:
        return []

    conversation_text = "\n".join(
        f"User: {t['text']}\nAI: {session['turns'][i+1]['text']}"
        for i, t in enumerate(user_turns)
        if i + 1 < len(session["turns"]) and session["turns"][i + 1]["role"] == "assistant"
    )

    prompt = (
        "You are an English tutor. Review the conversation below and identify errors "
        "made by the student (the User). For each error, provide a JSON object with:\n"
        "- original_text: the user's exact text with the error\n"
        "- corrected_text: the corrected version\n"
        "- error_type: one of: grammar, verb_tense, article, preposition, vocabulary, word_order, agreement, other\n"
        "- explanation_pt: explanation in Brazilian Portuguese\n\n"
        "Return ONLY a JSON array of error objects. If no errors, return an empty array.\n\n"
        f"Conversation:\n{conversation_text}\n\n"
        "JSON corrections:"
    )

    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            resp = client.post(
                f"{settings.ollama_host}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
            )
        resp.raise_for_status()
        data = resp.json()
        content = data["message"]["content"].strip()

        import json as json_parse
        corrections = json_parse.loads(content)
        if not isinstance(corrections, list):
            logger.warning(f"Review response is not a list: {type(corrections)}")
            return []
        logger.info(f"Review generated: {len(corrections)} corrections")
        return corrections
    except (httpx.RequestError, KeyError, ValueError, json_parse.JSONDecodeError) as e:
        logger.error(f"Review generation failed: {e}")
        return []

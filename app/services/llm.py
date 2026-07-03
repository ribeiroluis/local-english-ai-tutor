import json

import httpx
from app.config import settings
from app.services.logger import setup_logger

logger = setup_logger()

OLLAMA_MODEL = "qwen2.5:3b"
OLLAMA_TIMEOUT = 60.0

LEVEL_INSTRUCTIONS = {
    "A1": "Use very simple sentences and basic vocabulary. Speak slowly and clearly. Keep responses under 3 sentences.",
    "A2": "Use simple sentences. Avoid complex grammar. Keep responses under 4 sentences.",
    "B1": "Use moderate complexity. Natural conversational English.",
    "B2": "Use natural conversational English. Occasional idioms are okay.",
    "C1": "Use sophisticated vocabulary and natural idioms.",
    "C2": "Use native-level English with full complexity.",
}

CORRECTION_INSTRUCTIONS = (
    'Respond in JSON format with this exact structure:\n'
    '{\n'
    '  "reply": "Your natural conversational response in English",\n'
    '  "correction": {\n'
    '    "original": "The user\'s exact text or phrase with error, exactly as written",\n'
    '    "corrected": "The corrected version",\n'
    '    "explanation_pt": "Brief explanation in Brazilian Portuguese",\n'
    '    "error_type": "grammar|verb_tense|article|preposition|vocabulary|word_order|agreement|other"\n'
    '  }\n'
    '}\n'
    'If the user made no errors, set "correction" to null.\n'
    'Always respond in valid JSON.'
)


def build_messages(topic_prompt: str, level: str, context_turns: list[dict], user_text: str) -> list[dict]:
    level_instruction = LEVEL_INSTRUCTIONS.get(level, "Use natural conversational English.")
    system = f"{topic_prompt}\n\nLevel: {level}. {level_instruction}\n\n{CORRECTION_INSTRUCTIONS}"

    messages = [{"role": "system", "content": system}]

    for turn in context_turns[-20:]:
        messages.append({"role": turn["role"], "content": turn["text"]})

    messages.append({"role": "user", "content": user_text})
    return messages


def _call_generate_fallback(messages: list[dict], format_json: bool) -> str:
    prompt_text = ""
    for m in messages:
        role_label = m["role"].upper() if m["role"] != "system" else "SYSTEM"
        prompt_text += f"{role_label}: {m['content']}\n"
    prompt_text += "ASSISTANT:"

    gen_payload: dict = {"model": OLLAMA_MODEL, "prompt": prompt_text, "stream": False}
    if format_json:
        gen_payload["format"] = "json"

    with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
        resp = client.post(
            f"{settings.ollama_host}/api/generate",
            json=gen_payload,
        )
    resp.raise_for_status()
    data = resp.json()
    if "response" in data:
        return data["response"].strip()
    raise ValueError("Unexpected /api/generate response format")


def _ollama_chat(messages: list[dict], format_json: bool = False) -> str:
    url = f"{settings.ollama_host}/api/chat"
    payload: dict = {"model": OLLAMA_MODEL, "messages": messages, "stream": False}
    if format_json:
        payload["format"] = "json"

    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            resp = client.post(url, json=payload)

        if resp.status_code == 404:
            logger.info("Ollama /api/chat returned 404, falling back to /api/generate")
            return _call_generate_fallback(messages, format_json)

        resp.raise_for_status()
        data = resp.json()

        if "message" in data:
            return data["message"]["content"].strip()
        elif "response" in data:
            return data["response"].strip()
        else:
            logger.error(f"Unexpected Ollama response format: {data}")
            raise ValueError("Unexpected Ollama response format")

    except httpx.RequestError as e:
        logger.warning(f"Ollama /api/chat request failed ({e}), falling back to /api/generate")
        try:
            return _call_generate_fallback(messages, format_json)
        except httpx.RequestError as fallback_err:
            logger.error(f"Ollama /api/generate fallback also failed: {fallback_err}")
            raise
    except (KeyError, ValueError) as e:
        logger.error(f"Failed to parse Ollama response: {e}")
        raise


def _parse_reply(raw: str) -> str:
    cleaned = raw.strip()
    if not cleaned:
        return "I'm sorry, I couldn't generate a response."
    return cleaned


def generate_with_correction(topic_prompt: str, level: str, context_turns: list[dict], user_text: str) -> dict:
    messages = build_messages(topic_prompt, level, context_turns, user_text)
    reply = _ollama_chat(messages, format_json=True)
    logger.info(f"LLM raw reply: {len(reply)} chars")

    try:
        data = json.loads(reply)
        if not isinstance(data, dict):
            raise ValueError("Response is not a JSON object")
        correction = data.get("correction")
        if correction is not None and not isinstance(correction, dict):
            correction = None
        raw_reply = data.get("reply")
        if not isinstance(raw_reply, str) or not raw_reply.strip():
            raise ValueError("Missing or empty 'reply' field")
        result = {
            "reply": _parse_reply(raw_reply),
            "correction": correction,
        }
        logger.info(f"LLM parsed: reply={len(result['reply'])} chars, correction={'yes' if correction else 'none'}")
        return result
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse structured LLM output: {e}")
        return {"reply": _parse_reply(reply), "correction": None}


def generate_review(session: dict) -> dict:
    turns = session.get("turns", [])
    conversation_parts = []

    for i in range(0, len(turns) - 1, 2):
        user_turn = turns[i]
        ai_turn = turns[i + 1]
        if user_turn["role"] == "user" and ai_turn["role"] == "assistant":
            conversation_parts.append(f"User: {user_turn['text']}\nAI: {ai_turn['text']}")

    if not conversation_parts:
        return {"total_errors": 0, "by_type": {}, "topics_to_review": []}

    conversation_text = "\n".join(conversation_parts)

    prompt = (
        "You are an English tutor. Review the conversation below and provide an aggregate analysis "
        "of the student's errors. Return a JSON object with:\n"
        "- total_errors: total number of errors found\n"
        "- by_type: object with error_type as key and count as value (types: grammar, verb_tense, article, preposition, vocabulary, word_order, agreement, other)\n"
        "- topics_to_review: array of strings with topics the student should review\n\n"
        'If no errors, return {"total_errors": 0, "by_type": {}, "topics_to_review": []}.\n\n'
        f"Conversation:\n{conversation_text}\n\n"
        "JSON analysis:"
    )

    try:
        reply = _ollama_chat([{"role": "user", "content": prompt}], format_json=True)
        summary = json.loads(reply)
        if not isinstance(summary, dict):
            logger.warning(f"Review response is not a dict: {type(summary)}")
            return {"total_errors": 0, "by_type": {}, "topics_to_review": []}
        logger.info(f"Review summary generated: {summary.get('total_errors', 0)} total errors")
        return summary
    except (httpx.RequestError, KeyError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Review summary generation failed: {e}")
        return {"total_errors": 0, "by_type": {}, "topics_to_review": []}

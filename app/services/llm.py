import json

import httpx
from app.config import settings
from app.services.logger import setup_logger

logger = setup_logger()

OLLAMA_TIMEOUT = 60.0

LEVEL_INSTRUCTIONS = {
    "A1": "Use very simple sentences and basic vocabulary. Speak slowly and clearly. Keep responses under 2 sentences. Always end with a simple yes/no question.",
    "A2": "Use simple sentences. Avoid complex grammar. Keep responses under 3 sentences. Always end with a simple question.",
    "B1": "Use moderate complexity. Natural conversational English. Always end with a question.",
    "B2": "Use natural conversational English. Occasional idioms are okay. Always end with a question or prompt.",
    "C1": "Use sophisticated vocabulary and natural idioms. Always end with an open-ended question.",
    "C2": "Use native-level English with full complexity. Always end with a thought-provoking question.",
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
    'End your reply with a question to keep the conversation moving.\n'
    'Always respond in valid JSON.'
)


def build_messages(topic_prompt: str, level: str, context_turns: list[dict], user_text: str, user_name: str = "", context_window: int = 10) -> list[dict]:
    level_instruction = LEVEL_INSTRUCTIONS.get(level, "Use natural conversational English.")
    system = f"{topic_prompt}\n\nLevel: {level}. {level_instruction}\n\n{CORRECTION_INSTRUCTIONS}"
    if user_name:
        system = f"The user's name is {user_name}. Address them by name naturally in conversation.\n\n{system}"

    messages = [{"role": "system", "content": system}]

    for turn in context_turns[-(context_window * 2):]:
        messages.append({"role": turn["role"], "content": turn["text"]})

    messages.append({"role": "user", "content": user_text})
    return messages


def _call_generate_fallback(messages: list[dict], format_json: bool, model: str) -> str:
    prompt_text = ""
    for m in messages:
        role_label = m["role"].upper() if m["role"] != "system" else "SYSTEM"
        prompt_text += f"{role_label}: {m['content']}\n"
    prompt_text += "ASSISTANT:"

    gen_payload: dict = {"model": model, "prompt": prompt_text, "stream": False}
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


def _ollama_chat(messages: list[dict], format_json: bool = False, model: str = "qwen2.5:3b") -> str:
    url = f"{settings.ollama_host}/api/chat"
    payload: dict = {"model": model, "messages": messages, "stream": False}
    if format_json:
        payload["format"] = "json"

    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            resp = client.post(url, json=payload)

        if resp.status_code == 404:
            logger.info("Ollama /api/chat returned 404, falling back to /api/generate")
            return _call_generate_fallback(messages, format_json, model)

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
            return _call_generate_fallback(messages, format_json, model)
        except httpx.RequestError as fallback_err:
            logger.error(f"Ollama /api/generate fallback also failed: {fallback_err}")
            raise
    except (KeyError, ValueError) as e:
        logger.error(f"Failed to parse Ollama response: {e}")
        raise


FALLBACK_MSG = "I'm sorry, I couldn't generate a response."


def _fallback_reply(raw: str) -> str:
    cleaned = raw.strip()
    if not cleaned or len(cleaned) < 5 or cleaned in ("{}", "[]", '""'):
        return FALLBACK_MSG
    return cleaned


def generate_with_correction(topic_prompt: str, level: str, context_turns: list[dict], user_text: str, user_name: str = "", llm_model: str = "qwen2.5:3b", context_window: int = 10) -> dict:
    messages = build_messages(topic_prompt, level, context_turns, user_text, user_name=user_name, context_window=context_window)
    reply = _ollama_chat(messages, format_json=True, model=llm_model)
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
            "reply": raw_reply.strip(),
            "correction": correction,
        }
        logger.info(f"LLM parsed: reply={len(result['reply'])} chars, correction={'yes' if correction else 'none'}")
        return result
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse structured LLM output: {e}")
        return {"reply": _fallback_reply(reply), "correction": None}


def generate_opening(topic_prompt: str, level: str, user_name: str = "", llm_model: str = "qwen2.5:3b") -> dict:
    level_instruction = LEVEL_INSTRUCTIONS.get(level, "Use natural conversational English.")
    name_line = f"The user's name is {user_name}. Address them by name.\n\n" if user_name else ""
    prompt = (
        f"{topic_prompt}\n\n"
        f"Level: {level}. {level_instruction}\n\n"
        f"{name_line}"
        "You are starting a new conversation. Introduce the topic briefly "
        "and ask the user a question to begin.\n\n"
        'Respond in JSON format: {"reply": "Your opening message here"}'
    )
    reply = _ollama_chat([{"role": "system", "content": prompt}], format_json=True, model=llm_model)
    try:
        data = json.loads(reply)
        result_reply = data.get("reply", "")
        if not isinstance(result_reply, str) or not result_reply.strip():
            raise ValueError("Missing or empty 'reply' field")
        logger.info(f"Opening generated: {len(result_reply)} chars")
        return {"reply": result_reply.strip()}
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse opening LLM output: {e}")
        return {"reply": FALLBACK_MSG}


def _compute_correction_stats(turns: list[dict]) -> dict:
    by_type: dict[str, int] = {}
    total = 0
    for turn in turns:
        if turn.get("role") == "user" and turn.get("correction"):
            correction = turn["correction"]
            etype = correction.get("error_type", "other")
            by_type[etype] = by_type.get(etype, 0) + 1
            total += 1
    return {"total_errors": total, "by_type": by_type}


def generate_review(session: dict) -> dict:
    turns = session.get("turns", [])
    stats = _compute_correction_stats(turns)
    llm_model = session.get("llm_model", "qwen2.5:3b")

    user_turns = [t for t in turns if t.get("role") == "user"]
    if not user_turns:
        return {**stats, "topics_to_review": []}

    if stats["total_errors"] == 0:
        return {**stats, "topics_to_review": []}

    last_user_turns = user_turns[-10:]
    context_parts = []
    for ut in last_user_turns:
        if ut.get("correction"):
            context_parts.append(
                f"User: {ut['text']}\n"
                f"Correction: {ut['correction'].get('corrected', '')} "
                f"({ut['correction'].get('explanation_pt', '')})"
            )

    context_text = "\n".join(context_parts)

    prompt = (
        "You are an English tutor. Based on the following corrections from a conversation, "
        "suggest topics the student should review. Return a JSON object with:\n"
        "- topics_to_review: array of strings with topics the student should review\n\n"
        "Example: {\"topics_to_review\": [\"Past simple tense\", \"Definite articles\"]}\n\n"
        f"Corrections:\n{context_text}\n\n"
        "JSON:"
    )

    try:
        reply = _ollama_chat([{"role": "user", "content": prompt}], format_json=True, model=llm_model)
        data = json.loads(reply)
        topics = data.get("topics_to_review", []) if isinstance(data, dict) else []
        return {**stats, "topics_to_review": topics}
    except (httpx.RequestError, KeyError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Review topics generation failed: {e}")
        return {**stats, "topics_to_review": []}

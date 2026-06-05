from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI, OpenAIError

from app.config import Config


DEFAULT_MODEL = "gpt-4o"
DEFAULT_SYSTEM_PROMPT = "你是協助查詢員工與財務資料的 AI Agent。"


class LLMConfigurationError(RuntimeError):
    pass


class LLMRequestError(RuntimeError):
    pass


@dataclass
class LLMReply:
    content: str
    model: str


def get_openai_api_key() -> str:
    return Config.OPENAI_API_KEY.strip()


def is_placeholder_key(api_key: str) -> bool:
    normalized = api_key.strip().lower()
    return not normalized or any(
        marker in normalized
        for marker in (
            "請填入",
            "placeholder",
            "your_key",
            "your key",
            "sk-your",
        )
    )


def mask_api_key(api_key: str) -> str:
    if is_placeholder_key(api_key):
        return ""

    prefix = api_key[:3] if len(api_key) >= 3 else "***"
    suffix = api_key[-4:] if len(api_key) >= 4 else "****"
    return f"{prefix}-...{suffix}" if not prefix.endswith("-") else f"{prefix}...{suffix}"


def get_openai_client() -> OpenAI:
    api_key = get_openai_api_key()

    if is_placeholder_key(api_key):
        raise LLMConfigurationError("OPENAI_API_KEY is missing or still uses a placeholder value.")

    return OpenAI(api_key=api_key)


def normalize_model(model: str | None) -> str:
    value = (model or "").strip()
    return value or DEFAULT_MODEL


def clamp_temperature(value) -> float:
    try:
        temperature = float(value)
    except (TypeError, ValueError):
        temperature = 0.4

    return min(max(temperature, 0.0), 1.0)


def normalize_system_prompt(system_prompt: str | None) -> str:
    value = (system_prompt or "").strip()
    return value or DEFAULT_SYSTEM_PROMPT


def normalize_memory_rounds(value) -> int:
    try:
        memory_rounds = int(value)
    except (TypeError, ValueError):
        memory_rounds = 5

    return min(max(memory_rounds, 1), 10)


def check_llm_connection() -> dict:
    api_key = get_openai_api_key()
    masked_key = mask_api_key(api_key)

    if is_placeholder_key(api_key):
        return {
            "ok": False,
            "status": "missing_key",
            "masked_key": "",
            "message": "OPENAI_API_KEY is missing or still uses a placeholder value.",
        }

    try:
        client = get_openai_client()
        models = client.models.list()
        first_model = models.data[0].id if models.data else None
        return {
            "ok": True,
            "status": "ok",
            "masked_key": masked_key,
            "message": "OpenAI API key is configured and the API is reachable.",
            "sample_model": first_model,
        }
    except OpenAIError as exc:
        return {
            "ok": False,
            "status": "api_error",
            "masked_key": masked_key,
            "message": "OpenAI API call failed.",
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "error",
            "masked_key": masked_key,
            "message": "Unable to check OpenAI API health.",
            "error": str(exc),
        }


def build_response_input(system_prompt: str, history: list[dict], user_message: str) -> list[dict]:
    input_messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    for message in history:
        role = message.get("role")
        content = str(message.get("content", "")).strip()

        if role not in {"user", "assistant"} or not content:
            continue

        input_messages.append(
            {
                "role": role,
                "content": content,
            }
        )

    input_messages.append(
        {
            "role": "user",
            "content": user_message,
        }
    )
    return input_messages


def generate_llm_reply(
    *,
    history: list[dict],
    message: str,
    model: str,
    system_prompt: str,
    temperature: float,
) -> LLMReply:
    try:
        client = get_openai_client()
        response = client.responses.create(
            model=model,
            input=build_response_input(system_prompt, history, message),
            temperature=temperature,
        )
        content = (getattr(response, "output_text", "") or "").strip()

        if not content:
            raise LLMRequestError("OpenAI returned an empty response.")

        return LLMReply(content=content, model=model)
    except LLMConfigurationError:
        raise
    except OpenAIError as exc:
        raise LLMRequestError(str(exc)) from exc

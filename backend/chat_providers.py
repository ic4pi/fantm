"""
chat_providers.py — routes a chat completion to whichever provider a writer
style is assigned to. Groq (the House model, free-tier) stays on its
existing SDK client in generation.py; this module covers the paid
creative/uncensored roster: OpenRouter (Sao10K, TheDrummer) and Venice,
plus Anthropic (Claude) direct.

Two providers (openrouter, venice) are OpenAI-compatible — same
request/response shape, just a different base_url and key — so they share
one code path. Anthropic uses its own Messages API shape.

Every key is read from the environment at call time, not import time, so a
missing key fails with a clear error only when that specific style is
actually used, not on process start.
"""
import os
import httpx

OPENAI_COMPATIBLE_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "venice": "https://api.venice.ai/api/v1/chat/completions",
}

PROVIDER_ENV_KEYS = {
    "openrouter": "OPENROUTER_API_KEY",
    "venice": "VENICE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

_TIMEOUT = httpx.Timeout(120.0, connect=15.0)


def _require_key(provider: str) -> str:
    env_key = PROVIDER_ENV_KEYS[provider]
    key = os.environ.get(env_key)
    if not key:
        raise RuntimeError(
            f"Missing {env_key} — writer styles routed to '{provider}' need it set in the environment."
        )
    return key


def _openai_compatible_chat(provider: str, model: str, messages: list, max_tokens: int, temperature: float) -> str:
    key = _require_key(provider)
    url = OPENAI_COMPATIBLE_BASE_URLS[provider]
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if provider == "openrouter":
        # Attribution headers OpenRouter uses for its public leaderboards — optional but harmless.
        headers["HTTP-Referer"] = "https://fantm.ink"
        headers["X-Title"] = "fantm.ink"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    last_err = None
    with httpx.Client(timeout=_TIMEOUT) as http:
        for attempt in range(3):
            try:
                r = http.post(url, json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
                return data["choices"][0]["message"]["content"] or ""
            except Exception as e:
                last_err = e
    raise last_err


def _anthropic_chat(model: str, messages: list, max_tokens: int, temperature: float) -> str:
    key = _require_key("anthropic")
    system = None
    conversation = []
    for m in messages:
        if m["role"] == "system":
            # Anthropic's system prompt is a top-level field, not a message.
            system = (system + "\n\n" + m["content"]) if system else m["content"]
        else:
            conversation.append(m)
    headers = {
        "x-api-key": key,
        "anthropic-version": ANTHROPIC_VERSION,
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": conversation,
    }
    if system:
        payload["system"] = system
    last_err = None
    with httpx.Client(timeout=_TIMEOUT) as http:
        for attempt in range(3):
            try:
                r = http.post(ANTHROPIC_MESSAGES_URL, json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
                return "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
            except Exception as e:
                last_err = e
    raise last_err


def chat_complete(provider: str, model: str, messages: list, max_tokens: int = 2200, temperature: float = 0.85) -> str:
    """Dispatch a chat completion to the given provider. `provider` is one of
    'openrouter', 'venice', 'anthropic' — NOT 'groq' (that stays on the
    existing groq SDK client in generation.py)."""
    if provider == "anthropic":
        return _anthropic_chat(model, messages, max_tokens, temperature)
    if provider in OPENAI_COMPATIBLE_BASE_URLS:
        return _openai_compatible_chat(provider, model, messages, max_tokens, temperature)
    raise ValueError(f"Unknown provider '{provider}' — expected one of: anthropic, {', '.join(OPENAI_COMPATIBLE_BASE_URLS)}")

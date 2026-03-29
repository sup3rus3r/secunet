"""
LLM abstraction layer — provider-agnostic async completion interface.

Supported providers (set via LLM_PROVIDER env var):
  anthropic  — Claude models via Anthropic SDK (default)
  openai     — OpenAI models via OpenAI SDK
  lmstudio   — Local models via LM Studio's OpenAI-compatible API
  fireworks  — Fireworks AI via OpenAI-compatible API

All agents and Commander components MUST use this module.
No direct `anthropic` or `openai` imports anywhere else in the platform.

Usage:
    from llm_client import complete

    text = await complete(
        system="You are...",
        messages=[{"role": "user", "content": "..."}],
        max_tokens=500,
    )
"""
import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Provider selection ──────────────────────────────────────────────────────
PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()

# Default models per provider
_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "openai":    "gpt-4o",
    "lmstudio":  "local-model",
    "fireworks": "accounts/fireworks/models/kimi-k2p5",
}

# Provider-specific model env vars take priority over LLM_MODEL
_PROVIDER_MODEL_ENV = {
    "anthropic": "ANTHROPIC_MODEL",
    "openai":    "OPENAI_MODEL",
    "lmstudio":  "LMSTUDIO_MODEL",
    "fireworks": "FIREWORKS_MODEL",
}
MODEL = (
    os.getenv(_PROVIDER_MODEL_ENV.get(PROVIDER, ""), "")
    or os.getenv("LLM_MODEL", "")
    or _DEFAULT_MODELS.get(PROVIDER, "claude-sonnet-4-6")
)

# ── Lazy client singletons ──────────────────────────────────────────────────
_anthropic_client = None
_openai_clients: dict[str, Any] = {}


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY", "")
        )
    return _anthropic_client


def _get_openai(base_url: str | None = None):
    cache_key = base_url or "default"
    if cache_key not in _openai_clients:
        from openai import AsyncOpenAI
        if PROVIDER == "fireworks":
            api_key = os.getenv("FIREWORKS_API_KEY", "none")
        else:
            api_key = os.getenv("OPENAI_API_KEY", "none")
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        _openai_clients[cache_key] = AsyncOpenAI(**kwargs)
    return _openai_clients[cache_key]


# ── Core interface ──────────────────────────────────────────────────────────

async def complete(
    system: str,
    messages: list[dict],
    max_tokens: int = 4096,
    model: str | None = None,
) -> str:
    """
    Send a completion request to the configured LLM provider.

    Args:
        system:     System prompt string.
        messages:   List of {"role": ..., "content": ...} dicts.
        max_tokens: Maximum tokens in the response.
        model:      Override the default model for this call only.

    Returns:
        The assistant's reply as a plain string.

    Raises:
        Exception: Propagates provider errors — callers should handle.
    """
    _model = model or MODEL

    if PROVIDER == "anthropic":
        return await _complete_anthropic(system, messages, max_tokens, _model)
    elif PROVIDER in ("openai", "lmstudio", "fireworks"):
        return await _complete_openai(system, messages, max_tokens, _model)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {PROVIDER!r}. Must be anthropic, openai, lmstudio, or fireworks.")


async def _complete_anthropic(
    system: str,
    messages: list[dict],
    max_tokens: int,
    model: str,
) -> str:
    client = _get_anthropic()
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    return response.content[0].text


async def _complete_openai(
    system: str,
    messages: list[dict],
    max_tokens: int,
    model: str,
) -> str:
    if PROVIDER == "lmstudio":
        base_url = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
    elif PROVIDER == "fireworks":
        base_url = os.getenv("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1")
    else:
        base_url = None
    client = _get_openai(base_url=base_url)

    # OpenAI/LM Studio uses the system message as the first message
    full_messages = [{"role": "system", "content": system}] + messages

    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=full_messages,
    )
    return response.choices[0].message.content

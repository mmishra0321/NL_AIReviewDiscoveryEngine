"""Thin wrapper around the Groq Python SDK.

Adds:
- env-key resolution
- automatic retries on rate-limit / transient errors
- a `chat_json` helper that parses structured JSON output
- a `chat_pydantic` helper that validates output against a Pydantic model
"""
from __future__ import annotations

import json
import logging
from typing import TypeVar

from groq import Groq, RateLimitError
from pydantic import BaseModel, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import GROQ_API_KEY, GROQ_MODEL, GROQ_MODEL_FAST

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GroqClient:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key or GROQ_API_KEY
        if not key:
            raise RuntimeError(
                "GROQ_API_KEY not set. Add it to .env (copy from .env.example) "
                "or set as an environment variable."
            )
        self._client = Groq(api_key=key)
        self.model = model or GROQ_MODEL

    @retry(
        retry=retry_if_exception_type(RateLimitError),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _complete(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        temperature: float = 0.2,
        json_mode: bool = False,
        max_tokens: int = 1024,
    ) -> str:
        kwargs: dict = {
            "model": model or self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    def chat(self, system: str, user: str, **kw) -> str:
        return self._complete(system, user, **kw)

    def chat_json(self, system: str, user: str, **kw) -> dict:
        kw["json_mode"] = True
        raw = self._complete(system, user, **kw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            log.warning("Failed to parse JSON from Groq response: %s\nRaw: %s", exc, raw[:500])
            return {}

    def chat_pydantic(
        self,
        system: str,
        user: str,
        schema: type[T],
        **kw,
    ) -> T | None:
        data = self.chat_json(system, user, **kw)
        if not data:
            return None
        try:
            return schema.model_validate(data)
        except ValidationError as exc:
            log.warning("Pydantic validation failed: %s\nData: %s", exc, data)
            return None


# --- Module-level singletons for convenience ---
_default_client: GroqClient | None = None
_fast_client: GroqClient | None = None


def default_client() -> GroqClient:
    global _default_client
    if _default_client is None:
        _default_client = GroqClient(model=GROQ_MODEL)
    return _default_client


def fast_client() -> GroqClient:
    """Smaller, faster model — for high-volume classification."""
    global _fast_client
    if _fast_client is None:
        _fast_client = GroqClient(model=GROQ_MODEL_FAST)
    return _fast_client

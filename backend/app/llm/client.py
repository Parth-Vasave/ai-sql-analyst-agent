"""LLM access behind one small interface.

OpenAICompatibleClient talks to any OpenAI-compatible chat-completions endpoint (Gemini,
Groq, OpenRouter, Ollama, ...). Every reply must be a JSON object that validates against
the Pydantic model the caller asks for: model output is never used unvalidated.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, SecretStr, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The LLM call failed or returned output that does not match the expected structure."""


@dataclass(frozen=True)
class LLMCall:
    """Metadata of one call, recorded for reproducibility (never the API key)."""

    model: str
    duration_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class LLMClient(Protocol):
    model: str

    def complete_json(self, system: str, user: str, output: type[T]) -> tuple[T, LLMCall]: ...


def parse_output(content: str, output: type[T]) -> T:
    text = content.strip()
    if text.startswith("```"):  # some models wrap JSON in a Markdown fence despite instructions
        text = text.strip("`").removeprefix("json").strip()
    try:
        return output.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise LLMError(f"Model reply is not a valid {output.__name__}: {exc.__class__.__name__}") from None


class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        api_key: SecretStr,
        model: str,
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self._http = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {api_key.get_secret_value()}"},
            timeout=timeout_seconds,
            transport=transport,
        )

    def complete_json(self, system: str, user: str, output: type[T]) -> tuple[T, LLMCall]:
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        started = time.perf_counter()
        try:
            response = self._http.post("chat/completions", json=payload)
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request failed: {exc.__class__.__name__}") from None
        duration_ms = int((time.perf_counter() - started) * 1000)
        if response.status_code != 200:
            # The body can echo request details; report the status only.
            raise LLMError(f"LLM provider returned HTTP {response.status_code}")
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise LLMError("LLM provider returned an unexpected response shape") from None
        usage = body.get("usage") or {}
        call = LLMCall(self.model, duration_ms, usage.get("prompt_tokens"), usage.get("completion_tokens"))
        return parse_output(content, output), call


class ScriptedLLMClient:
    """Deterministic stand-in for tests and offline development.

    `script` receives (system, user) and returns the raw text the model would have replied.
    """

    def __init__(self, script: Callable[[str, str], str], model: str = "scripted") -> None:
        self.model = model
        self.script = script
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str, output: type[T]) -> tuple[T, LLMCall]:
        self.calls.append((system, user))
        return parse_output(self.script(system, user), output), LLMCall(self.model, 0)

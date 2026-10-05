"""LLM access behind one small interface.

OpenAICompatibleClient talks to any OpenAI-compatible chat-completions endpoint (Gemini,
Groq, OpenRouter, Ollama, ...). Every reply must be a JSON object that validates against
the Pydantic model the caller asks for: model output is never used unvalidated.

Transient provider failures (rate limits, overload) are retried a bounded number of times
with a short wait, so a free-tier hiccup does not fail the whole question.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, SecretStr, ValidationError

from app.observability import log_event

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger("app.llm")

# Rate limited, or the provider is overloaded / briefly unavailable.
TRANSIENT_STATUS = frozenset({429, 500, 502, 503, 504})


class LLMError(RuntimeError):
    """The LLM call failed or returned output that does not match the expected structure."""


class LLMOutputError(LLMError):
    """The provider replied, but the reply is not the structured output we asked for.

    This is a model-output failure, not a provider failure: it is worth one more try with a
    short description of what was wrong. Its message is derived only from safe metadata (the
    error type and the field names the expected model declares); the raw reply is never quoted,
    because it is untrusted text.
    """


@dataclass(frozen=True)
class LLMCall:
    """Metadata of one call, recorded for reproducibility (never the API key)."""

    model: str
    duration_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    attempts: int = 1


class LLMClient(Protocol):
    model: str

    def complete_json(self, system: str, user: str, output: type[T]) -> tuple[T, LLMCall]: ...


def _describe_validation_error(exc: ValidationError, output: type[BaseModel]) -> str:
    """A safe summary of a schema mismatch, built only from trusted information.

    The reply is untrusted, so only field names declared by `output` and pydantic's own error
    types are reported; the model's keys, values and messages are never included.
    """
    fields = set(output.model_fields)
    problems = []
    for error in exc.errors()[:10]:
        location = [part for part in error.get("loc", ()) if isinstance(part, str) and part in fields]
        problems.append(f"{'.'.join(location) or 'reply'} ({error.get('type', 'invalid')})")
    return ", ".join(problems)


def parse_output(content: str, output: type[T]) -> T:
    text = content.strip()
    if text.startswith("```"):  # some models wrap JSON in a Markdown fence despite instructions
        text = text.strip("`").removeprefix("json").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise LLMOutputError(f"Model reply was not valid JSON; expected a {output.__name__} object") from None
    try:
        return output.model_validate(data)
    except ValidationError as exc:
        raise LLMOutputError(
            f"Model reply is not a valid {output.__name__}: {_describe_validation_error(exc, output)}"
        ) from None


class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        api_key: SecretStr,
        model: str,
        timeout_seconds: float = 30.0,
        max_attempts: int = 3,
        max_wait_seconds: float = 8.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.model = model
        self.max_attempts = max_attempts
        self.max_wait_seconds = max_wait_seconds
        self._sleep = sleep
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
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self._http.post("chat/completions", json=payload)
            except httpx.HTTPError as exc:
                raise LLMError(f"LLM request failed: {exc.__class__.__name__}") from None
            if response.status_code not in TRANSIENT_STATUS or attempt >= self.max_attempts:
                break
            wait = self._retry_wait(response, attempt)
            if wait > self.max_wait_seconds:
                break  # e.g. a per-minute quota: waiting that long inside a request is worse than failing
            self._sleep(wait)
        duration_ms = int((time.perf_counter() - started) * 1000)
        log_event(
            logger,
            "llm call",
            logging.INFO if response.status_code == 200 else logging.WARNING,
            model=self.model,
            http_status=response.status_code,
            attempts=attempt,
            duration_ms=duration_ms,
        )
        if response.status_code != 200:
            # The body can echo request details; report the status only.
            tries = f" after {attempt} attempts" if attempt > 1 else ""
            raise LLMError(f"LLM provider returned HTTP {response.status_code}{tries}")
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise LLMError("LLM provider returned an unexpected response shape") from None
        usage = body.get("usage") or {}
        call = LLMCall(
            self.model, duration_ms, usage.get("prompt_tokens"), usage.get("completion_tokens"), attempt
        )
        return parse_output(content, output), call

    @staticmethod
    def _retry_wait(response: httpx.Response, attempt: int) -> float:
        """Seconds to wait: the provider's Retry-After if given, else 1s, 2s, 4s, ..."""
        try:
            return max(0.0, float(response.headers.get("retry-after", "")))
        except ValueError:
            return float(2 ** (attempt - 1))


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

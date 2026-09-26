from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr

from app.agent.sql_generator import GeneratedSQL
from app.llm.client import LLMError, OpenAICompatibleClient, ScriptedLLMClient, parse_output


def _client(handler, sleeps: list[float] | None = None) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        "https://llm.example.test/v1",
        SecretStr("sk-secret"),
        "test-model",
        transport=httpx.MockTransport(handler),
        sleep=(sleeps.append if sleeps is not None else lambda seconds: None),
    )


def _sequence(*responses: httpx.Response):
    remaining = list(responses)
    return lambda request: remaining.pop(0)


def _reply(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 5},
    }


def test_sends_openai_compatible_request_and_parses_json() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200, json=_reply('{"sql": "SELECT 1", "explanation": "x", "chart_suggestion": "none"}')
        )

    output, call = _client(handler).complete_json("sys", "user", GeneratedSQL)
    assert output.sql == "SELECT 1"
    assert (call.model, call.prompt_tokens, call.completion_tokens) == ("test-model", 12, 5)
    assert seen["url"] == "https://llm.example.test/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-secret"
    assert seen["body"]["temperature"] == 0
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in seen["body"]["messages"]] == ["system", "user"]


def test_http_errors_do_not_leak_the_response_body_or_key() -> None:
    client = _client(lambda request: httpx.Response(401, text="invalid key sk-secret"))
    with pytest.raises(LLMError) as info:
        client.complete_json("s", "u", GeneratedSQL)
    assert "401" in str(info.value) and "sk-secret" not in str(info.value)


_OK = '{"sql": "SELECT 1", "explanation": "x"}'


def test_transient_errors_are_retried_with_backoff() -> None:
    sleeps: list[float] = []
    handler = _sequence(httpx.Response(503), httpx.Response(429), httpx.Response(200, json=_reply(_OK)))
    output, call = _client(handler, sleeps).complete_json("s", "u", GeneratedSQL)
    assert output.sql == "SELECT 1"
    assert call.attempts == 3
    assert sleeps == [1.0, 2.0]


def test_retry_after_header_is_honoured() -> None:
    sleeps: list[float] = []
    handler = _sequence(
        httpx.Response(429, headers={"Retry-After": "3"}), httpx.Response(200, json=_reply(_OK))
    )
    _client(handler, sleeps).complete_json("s", "u", GeneratedSQL)
    assert sleeps == [3.0]


def test_long_retry_after_fails_fast_instead_of_blocking_the_request() -> None:
    sleeps: list[float] = []
    handler = _sequence(httpx.Response(429, headers={"Retry-After": "40"}))
    with pytest.raises(LLMError, match="HTTP 429"):
        _client(handler, sleeps).complete_json("s", "u", GeneratedSQL)
    assert sleeps == []


def test_retries_are_bounded() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    with pytest.raises(LLMError, match="HTTP 503 after 3 attempts"):
        _client(handler).complete_json("s", "u", GeneratedSQL)
    assert len(calls) == 3


def test_client_errors_are_not_retried() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(404)

    with pytest.raises(LLMError, match="HTTP 404$"):
        _client(handler).complete_json("s", "u", GeneratedSQL)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        '{"sql": "SELECT 1"}',
        '{"sql": 1, "explanation": "x"}',
        '{"explanation": "x", "chart_suggestion": "pie"}',
    ],
)
def test_invalid_model_output_is_rejected(content: str) -> None:
    with pytest.raises(LLMError):
        parse_output(content, GeneratedSQL)


def test_markdown_fenced_json_is_accepted() -> None:
    output = parse_output('```json\n{"sql": null, "explanation": "no"}\n```', GeneratedSQL)
    assert output.sql is None


def test_scripted_client_records_calls() -> None:
    client = ScriptedLLMClient(lambda s, u: '{"sql": null, "explanation": "n/a"}')
    client.complete_json("system", "user", GeneratedSQL)
    assert client.calls == [("system", "user")]

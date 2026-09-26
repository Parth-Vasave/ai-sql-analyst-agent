from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr

from app.agent.sql_generator import GeneratedSQL
from app.llm.client import LLMError, OpenAICompatibleClient, ScriptedLLMClient, parse_output


def _client(handler) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        "https://llm.example.test/v1",
        SecretStr("sk-secret"),
        "test-model",
        transport=httpx.MockTransport(handler),
    )


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

"""Request IDs and structured logging (Milestone 10)."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.database.connections import ConnectionConfig, ConnectionRegistry
from app.llm.client import ScriptedLLMClient
from app.main import app
from app.observability import JsonFormatter, install, log_event, new_request_id, safe_fields


class _Lines(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.setFormatter(JsonFormatter())
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))

    def entries(self) -> list[dict]:
        return [json.loads(line) for line in self.lines]


@pytest.fixture
def logs() -> Iterator[_Lines]:
    handler = _Lines()
    app_logger = logging.getLogger("app")
    app_logger.addHandler(handler)
    previous = app_logger.level
    app_logger.setLevel(logging.INFO)
    yield handler
    app_logger.removeHandler(handler)
    app_logger.setLevel(previous)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        app.state.registry = ConnectionRegistry(timeout_seconds=1)
        app.state.llm = None
        yield test_client


# --- request IDs -------------------------------------------------------------------------


def test_request_id_is_generated_and_returned(client: TestClient, logs: _Lines) -> None:
    response = client.get("/api/databases")
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 32
    request_log = next(e for e in logs.entries() if e["message"] == "request")
    assert request_log["request_id"] == request_id
    assert (request_log["method"], request_log["path"], request_log["status"]) == (
        "GET",
        "/api/databases",
        200,
    )
    assert isinstance(request_log["duration_ms"], int)


def test_callers_request_id_is_kept(client: TestClient) -> None:
    response = client.get("/api/databases", headers={"X-Request-ID": "trace-abc_123.4"})
    assert response.headers["X-Request-ID"] == "trace-abc_123.4"


@pytest.mark.parametrize("unsafe", ["has space", "x" * 65, "new\\nline", "", "<script>"])
def test_unsafe_request_ids_are_replaced(unsafe: str) -> None:
    assert new_request_id(unsafe) != unsafe and len(new_request_id(unsafe)) == 32


def test_each_request_gets_its_own_id(client: TestClient) -> None:
    ids = {client.get("/api/databases").headers["X-Request-ID"] for _ in range(3)}
    assert len(ids) == 3


def test_request_id_header_is_exposed_to_browsers(client: TestClient) -> None:
    response = client.get("/api/databases", headers={"Origin": "http://localhost:5173"})
    assert "x-request-id" in response.headers["access-control-expose-headers"].lower()


def test_unexpected_errors_return_a_generic_500_with_the_request_id(logs: _Lines) -> None:
    broken = FastAPI()
    install(broken)

    @broken.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret detail postgresql://u:hunter2@db/x")

    response = TestClient(broken, raise_server_exceptions=False).get("/boom", headers={"X-Request-ID": "r1"})
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error.", "request_id": "r1"}
    assert "hunter2" not in response.text
    error_log = next(e for e in logs.entries() if e["message"] == "unhandled error")
    assert error_log["request_id"] == "r1" and "RuntimeError" in error_log["exception"]


# --- log content -------------------------------------------------------------------------


def test_log_lines_are_json_with_fields(logs: _Lines) -> None:
    log_event(logging.getLogger("app.test"), "something happened", step="x", count=3)
    entry = logs.entries()[-1]
    assert entry["message"] == "something happened" and entry["level"] == "INFO"
    assert (entry["logger"], entry["step"], entry["count"]) == ("app.test", "x", 3)
    assert entry["ts"].endswith("+00:00")


def test_sensitive_fields_are_dropped() -> None:
    fields = {"step": "s", "question": "q", "SQL": "select", "rows": [[1]], "url": "u", "password": "p"}
    assert safe_fields(fields) == {"step": "s"}


def test_query_is_traced_under_one_request_id_without_leaking_content(
    pg, client: TestClient, logs: _Lines
) -> None:
    app.state.registry.add(
        ConnectionConfig(id="shop", name="Shop", url=SecretStr(pg.agent), schemas=["shop"])
    )
    sql = (
        "SELECT segment, count(*) AS customers FROM shop.customers GROUP BY segment ORDER BY segment LIMIT 10"
    )
    app.state.llm = ScriptedLLMClient(
        lambda s, u: json.dumps(
            {"sql": sql, "explanation": "Customers per segment.", "chart_suggestion": "bar"}
        )
    )
    question = "How many customers does each segment have, confidentially?"
    response = client.post("/api/query", json={"question": question, "database_id": "shop"})
    assert response.status_code == 200, response.text
    request_id = response.headers["X-Request-ID"]
    assert response.json()["metadata"]["request_id"] == request_id

    entries = logs.entries()
    steps = [e for e in entries if e["message"] == "agent step"]
    assert {e["request_id"] for e in steps} == {request_id}
    assert [e["step"] for e in steps][:3] == ["question_received", "schema_retrieval", "sql_generation"]
    assert steps[-1]["step"] == "completed" and all("duration_ms" in e for e in steps)

    text = "\n".join(logs.lines)
    password = pg.agent.split(":")[2].split("@")[0]
    for secret in (question, sql, "wholesale", password, pg.agent):
        assert secret not in text

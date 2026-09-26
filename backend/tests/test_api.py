from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings, get_settings
from app.database.connections import ConnectionConfig, ConnectionRegistry
from app.llm.client import ScriptedLLMClient
from app.main import app


@pytest.fixture
def registry() -> ConnectionRegistry:
    return ConnectionRegistry(timeout_seconds=1)


@pytest.fixture
def client(registry: ConnectionRegistry) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        app.state.registry = registry  # replace the one built from the environment
        app.state.llm = None
        yield test_client
    app.dependency_overrides.clear()


def allow_ui_connections(enabled: bool) -> None:
    settings = Settings(allow_ui_connections=enabled)
    app.dependency_overrides[get_settings] = lambda: settings


def test_health_without_databases_is_degraded(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "databases": {}}


def test_health_reports_unreachable_database(client: TestClient, registry: ConnectionRegistry) -> None:
    registry.add(
        ConnectionConfig(id="x", name="X", url=SecretStr("postgresql://u:p@127.0.0.1:1/db")), verify=False
    )
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["databases"] == {"x": "unavailable"}


def test_list_databases_never_exposes_urls(client: TestClient, registry: ConnectionRegistry) -> None:
    registry.add(
        ConnectionConfig(id="x", name="X", url=SecretStr("postgresql://u:hunter2@127.0.0.1:1/db")),
        verify=False,
    )
    response = client.get("/api/databases")
    assert response.status_code == 200
    assert response.json()[0]["id"] == "x"
    assert "hunter2" not in response.text and "127.0.0.1" not in response.text


def test_unknown_database_profile_is_404(client: TestClient) -> None:
    assert client.get("/api/databases/nope/profile").status_code == 404


def test_adding_databases_is_disabled_by_default(client: TestClient) -> None:
    allow_ui_connections(False)
    response = client.post("/api/databases", json={"name": "Mine", "url": "postgresql://u:p@localhost/db"})
    assert response.status_code == 403


def test_adding_unsupported_engine_is_rejected(client: TestClient) -> None:
    allow_ui_connections(True)
    response = client.post("/api/databases", json={"name": "Mine", "url": "mongodb://localhost/db"})
    assert response.status_code == 422


def test_adding_unreachable_database_is_rejected_and_not_kept(
    client: TestClient, registry: ConnectionRegistry
) -> None:
    allow_ui_connections(True)
    response = client.post(
        "/api/databases", json={"name": "Mine", "url": "postgresql://u:hunter2@127.0.0.1:1/db"}
    )
    assert response.status_code == 422
    assert "hunter2" not in response.text
    assert registry.all() == []


def test_add_and_profile_read_only_database(pg, client: TestClient) -> None:
    allow_ui_connections(True)
    response = client.post("/api/databases", json={"name": "Shop", "url": pg.agent, "schemas": ["shop"]})
    assert response.status_code == 201, response.text
    info = response.json()
    assert info["status"] == "ready" and info["source"] == "ui"
    profile = client.get(f"/api/databases/{info['id']}/profile")
    assert profile.status_code == 200
    assert {t["name"] for t in profile.json()["tables"]} == {"customers", "orders", "order_items"}


def test_adding_writable_account_is_rejected(pg, client: TestClient, registry: ConnectionRegistry) -> None:
    allow_ui_connections(True)
    response = client.post("/api/databases", json={"name": "Owner", "url": pg.admin})
    assert response.status_code == 422
    assert "modify tables" in response.text
    assert registry.all() == []


def test_query_without_llm_is_503(client: TestClient) -> None:
    response = client.post("/api/query", json={"question": "anything"})
    assert response.status_code == 503
    assert "LLM_API_KEY" in response.json()["detail"]


def test_query_validates_input(client: TestClient) -> None:
    app.state.llm = ScriptedLLMClient(lambda s, u: "{}")
    assert client.post("/api/query", json={"question": ""}).status_code == 422
    assert client.post("/api/query", json={"question": "x" * 501}).status_code == 422


def test_query_end_to_end(pg, client: TestClient, registry: ConnectionRegistry) -> None:
    registry.add(ConnectionConfig(id="shop", name="Shop", url=SecretStr(pg.agent), schemas=["shop"]))
    sql = (
        "SELECT segment, count(*) AS customers FROM shop.customers GROUP BY segment ORDER BY segment LIMIT 10"
    )
    reply = json.dumps({"sql": sql, "explanation": "Customers per segment.", "chart_suggestion": "bar"})
    app.state.llm = ScriptedLLMClient(lambda s, u: reply)
    response = client.post("/api/query", json={"question": "Customers per segment?", "database_id": "shop"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success"
    assert body["rows"] == [["online", 8], ["retail", 8], ["wholesale", 9]]
    assert body["metadata"]["model"] == "scripted" and body["metadata"]["row_count"] == 3


def test_listed_databases_are_verified_before_their_status_is_reported(
    pg, client: TestClient, registry: ConnectionRegistry
) -> None:
    config = ConnectionConfig(id="shop", name="Shop", url=SecretStr(pg.agent), schemas=["shop"])
    registry.add(config, verify=False)
    assert registry.get("shop").status.value == "unavailable"  # not checked yet
    assert client.get("/api/databases").json()[0]["status"] == "ready"

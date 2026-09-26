"""Agent flow: question -> schema -> SQL -> result, with a scripted LLM on real databases."""

from __future__ import annotations

import json

import pytest
from pydantic import SecretStr

from app.agent.controller import AgentController
from app.agent.executor import execute
from app.agent.schema_retriever import build_context, retrieve
from app.database.connections import ConnectionConfig, ConnectionRegistry
from app.database.profile import ColumnProfile, DatabaseProfile, SamplingMode, TableProfile
from app.llm.client import ScriptedLLMClient


def reply(sql: str | None, explanation: str = "test", chart: str = "none") -> str:
    return json.dumps({"sql": sql, "explanation": explanation, "chart_suggestion": chart})


def _profile(n_tables: int) -> DatabaseProfile:
    tables = [
        TableProfile(
            schema_name="s",
            name=f"table_{i}",
            kind="table",
            columns=[ColumnProfile(name="id", type="INTEGER", nullable=False, primary_key=True)],
        )
        for i in range(n_tables)
    ]
    tables.append(
        TableProfile(
            schema_name="s",
            name="invoices",
            kind="table",
            comment="Customer invoices",
            columns=[
                ColumnProfile(name="id", type="INTEGER", nullable=False, primary_key=True),
                ColumnProfile(name="amount", type="NUMERIC", nullable=False),
                ColumnProfile(name="card_number", type="TEXT", nullable=True, sensitive=True),
            ],
        )
    )
    return DatabaseProfile(
        database_id="x", dialect="postgresql", sampling=SamplingMode.SAFE, fingerprint="f", tables=tables,
        relationships=[],
    )  # fmt: skip


def test_small_schemas_are_sent_whole() -> None:
    assert len(retrieve(_profile(3), "anything")) == 4


def test_large_schemas_are_narrowed_to_relevant_tables() -> None:
    assert [t.name for t in retrieve(_profile(20), "total invoice amount")] == ["invoices"]


def test_sensitive_columns_are_never_rendered() -> None:
    context = build_context(_profile(1), "invoices")
    assert "amount" in context.text and "card_number" not in context.text


# --- integration -------------------------------------------------------------------------


@pytest.fixture
def shop(pg):
    registry = ConnectionRegistry(timeout_seconds=2)
    return registry.add(ConnectionConfig(id="shop", name="Shop", url=SecretStr(pg.agent), schemas=["shop"]))


def test_question_to_sql_to_result(shop) -> None:
    sql = "SELECT status, count(*) AS orders FROM shop.orders GROUP BY status ORDER BY status LIMIT 10"
    llm = ScriptedLLMClient(lambda system, user: reply(sql, "Counts orders by status.", "bar"))
    result = AgentController(llm, max_rows=100).run("How many orders per status?", shop)

    assert result.status == "success"
    assert result.columns == ["status", "orders"]
    assert result.rows == [["placed", 20], ["returned", 20], ["shipped", 20]]
    assert result.chart_suggestion == "bar"
    assert [e.step for e in result.trace] == [
        "question_received", "schema_retrieval", "sql_generation", "query_execution", "completed",
    ]  # fmt: skip
    system, user = llm.calls[0]
    assert "postgres SQL" in system and "LIMIT 100" in system
    assert "shop.orders" in user and '"placed"' in user  # schema and categorical values reach the model
    assert "password_hash" not in user and "email" not in user  # sensitive columns never do


def test_sql_error_is_classified_and_reported(shop) -> None:
    llm = ScriptedLLMClient(lambda s, u: reply("SELECT states FROM shop.orders LIMIT 5"))
    result = AgentController(llm, max_rows=100).run("Which state?", shop)
    assert result.status == "error"
    assert result.error.category == "undefined_column"
    assert 'column "states" does not exist' in result.error.message
    assert result.sql == "SELECT states FROM shop.orders LIMIT 5"
    assert result.trace[-2].step == "query_execution" and result.trace[-2].status == "failed"


def test_unanswerable_question(shop) -> None:
    llm = ScriptedLLMClient(lambda s, u: reply(None, "The database has no weather data."))
    result = AgentController(llm, max_rows=100).run("What was the weather?", shop)
    assert result.status == "unanswerable" and result.sql is None
    assert result.answer == "The database has no weather data."


def test_row_cap_is_enforced_even_without_limit(shop) -> None:
    result = execute(shop, "SELECT id FROM shop.order_items ORDER BY id", max_rows=50)
    assert result.row_count == 50 and result.truncated is True


def test_timeout_is_classified(shop) -> None:
    llm = ScriptedLLMClient(lambda s, u: reply("SELECT pg_sleep(5)"))
    result = AgentController(llm, max_rows=10).run("slow", shop)
    assert result.error.category == "timeout"


def test_writes_fail_at_the_database_even_if_generated(shop) -> None:
    llm = ScriptedLLMClient(lambda s, u: reply("DELETE FROM shop.orders"))
    result = AgentController(llm, max_rows=10).run("delete everything", shop)
    assert result.status == "error" and result.error.category in {"read_only", "permission"}

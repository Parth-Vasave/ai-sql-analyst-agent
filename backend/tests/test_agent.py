"""Agent flow: question -> schema -> SQL -> result, with a scripted LLM on real databases."""

from __future__ import annotations

import json

import pytest
from pydantic import SecretStr

from app.agent.controller import AgentController
from app.agent.executor import QueryExecutionError, execute
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
        "question_received", "schema_retrieval", "sql_generation", "sql_validation", "query_execution",
        "completed",
    ]  # fmt: skip
    system, user = llm.calls[0]
    assert "postgres SQL" in system and "LIMIT 100" in system
    assert "shop.orders" in user and '"placed"' in user  # schema and categorical values reach the model
    assert "password_hash" not in user and "email" not in user  # sensitive columns never do


def test_sql_error_is_classified_and_reported(shop) -> None:
    # Valid by the validator's rules, but wrong for PostgreSQL: comparing numeric to text.
    sql = "SELECT id FROM shop.orders WHERE total = 'lots' LIMIT 5"
    llm = ScriptedLLMClient(lambda s, u: reply(sql))
    result = AgentController(llm, max_rows=100).run("Which orders?", shop)
    assert result.status == "error"
    assert result.error.category == "type_mismatch"
    assert "invalid input syntax" in result.error.message
    assert result.sql == sql
    assert result.trace[-2].step == "query_execution" and result.trace[-2].status == "failed"


def test_unknown_column_is_rejected_before_execution(shop) -> None:
    llm = ScriptedLLMClient(lambda s, u: reply("SELECT states FROM shop.orders LIMIT 5"))
    result = AgentController(llm, max_rows=100).run("Which state?", shop)
    assert result.status == "error"
    assert (result.error.category, result.error.code) == ("validation", "unknown_column")
    assert result.sql == "SELECT states FROM shop.orders LIMIT 5"  # the rejected SQL is shown
    assert result.trace[-2].step == "sql_validation" and result.trace[-2].status == "failed"
    assert "query_execution" not in [e.step for e in result.trace]


def test_missing_limit_is_added_before_execution(shop) -> None:
    llm = ScriptedLLMClient(lambda s, u: reply("SELECT id FROM shop.order_items ORDER BY id"))
    result = AgentController(llm, max_rows=50).run("All items", shop)
    assert result.status == "success"
    assert result.sql == "SELECT id FROM shop.order_items ORDER BY id LIMIT 50"
    assert result.metadata.row_count == 50 and result.metadata.tables_used == ["shop.order_items"]
    validation = next(e for e in result.trace if e.step == "sql_validation")
    assert validation.detail["limit_action"] == "added"


def test_unanswerable_question(shop) -> None:
    llm = ScriptedLLMClient(lambda s, u: reply(None, "The database has no weather data."))
    result = AgentController(llm, max_rows=100).run("What was the weather?", shop)
    assert result.status == "unanswerable" and result.sql is None
    assert result.answer == "The database has no weather data."


def test_row_cap_is_enforced_even_without_limit(shop) -> None:
    result = execute(shop, "SELECT id FROM shop.order_items ORDER BY id", max_rows=50)
    assert result.row_count == 50 and result.truncated is True


def test_timeout_is_classified(shop) -> None:
    # Allowed by the validator (bounded only by the statement timeout), too slow to finish in 2 s.
    slow = "SELECT count(*) AS n FROM generate_series(1, 1000000000) AS g"
    llm = ScriptedLLMClient(lambda s, u: reply(slow))
    result = AgentController(llm, max_rows=10).run("slow", shop)
    assert result.error.category == "timeout"


def test_sleep_is_rejected_by_the_validator_and_stopped_by_the_database_timeout(shop) -> None:
    llm = ScriptedLLMClient(lambda s, u: reply("SELECT pg_sleep(5)"))
    result = AgentController(llm, max_rows=10).run("slow", shop)
    assert (result.error.category, result.error.code) == ("validation", "forbidden_function")
    with pytest.raises(QueryExecutionError) as info:  # second layer, if the validator were bypassed
        execute(shop, "SELECT pg_sleep(5)", max_rows=10)
    assert info.value.category == "timeout"


def test_writes_are_rejected_by_the_validator_and_by_the_database(shop) -> None:
    llm = ScriptedLLMClient(lambda s, u: reply("DELETE FROM shop.orders"))
    result = AgentController(llm, max_rows=10).run("delete everything", shop)
    assert (result.error.category, result.error.code) == ("validation", "not_select")
    assert "query_execution" not in [e.step for e in result.trace]
    with pytest.raises(QueryExecutionError) as info:  # second layer, if the validator were bypassed
        execute(shop, "DELETE FROM shop.orders", max_rows=10)
    assert info.value.category in {"read_only", "permission"}

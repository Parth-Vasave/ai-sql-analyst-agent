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


def sequence(*replies: str) -> ScriptedLLMClient:
    """A scripted model that gives these replies in order (the last one repeats)."""
    remaining = list(replies)
    return ScriptedLLMClient(lambda s, u: remaining.pop(0) if len(remaining) > 1 else remaining[0])


def steps(result) -> list[tuple[str, str]]:
    return [(e.step, e.status) for e in result.trace]


def reply(
    sql: str | None,
    explanation: str = "test",
    chart: str = "none",
    plan: dict | None = None,
    clarification: str | None = None,
) -> str:
    return json.dumps(
        {
            "plan": plan,
            "sql": sql,
            "clarification_question": clarification,
            "explanation": explanation,
            "chart_suggestion": chart,
        }
    )


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
    result = AgentController(llm, max_rows=100, max_retries=0).run("Which orders?", shop)
    assert result.status == "error"
    assert result.error.category == "type_mismatch"
    assert "invalid input syntax" in result.error.message
    assert result.sql == sql
    assert result.trace[-2].step == "query_execution" and result.trace[-2].status == "failed"


def test_unknown_column_is_rejected_before_execution(shop) -> None:
    llm = ScriptedLLMClient(lambda s, u: reply("SELECT states FROM shop.orders LIMIT 5"))
    result = AgentController(llm, max_rows=100, max_retries=0).run("Which state?", shop)
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


def test_plan_is_returned_and_checked_against_the_sql(shop) -> None:
    plan = {"intent": "aggregate", "tables": ["shop.orders", "shop.customers"], "limit": 10,
            "assumptions": ["all order statuses count"]}  # fmt: skip
    sql = "SELECT status, count(*) AS orders FROM shop.orders GROUP BY status LIMIT 10"
    llm = ScriptedLLMClient(lambda s, u: reply(sql, plan=plan))
    result = AgentController(llm, max_rows=100).run("How many orders per status?", shop)

    assert result.status == "success"
    assert result.plan is not None and result.plan.assumptions == ["all order statuses count"]
    generation = next(e for e in result.trace if e.step == "sql_generation")
    assert generation.detail["intent"] == "aggregate"
    validation = next(e for e in result.trace if e.step == "sql_validation")
    assert validation.detail["plan_warnings"] == ["planned tables not used by the SQL: customers"]


def test_missing_plan_is_noted_in_the_trace(shop) -> None:
    llm = ScriptedLLMClient(lambda s, u: reply("SELECT id FROM shop.orders LIMIT 1"))
    result = AgentController(llm, max_rows=100).run("One order", shop)
    assert result.status == "success" and result.plan is None
    validation = next(e for e in result.trace if e.step == "sql_validation")
    assert validation.detail["plan_warnings"] == ["no plan returned"]


def test_ambiguous_question_asks_for_clarification(shop) -> None:
    llm = ScriptedLLMClient(
        lambda s, u: reply(
            None,
            "Best could mean revenue or order count.",
            clarification="Best by revenue or by number of orders?",
        )
    )
    result = AgentController(llm, max_rows=100).run("Who are the best customers?", shop)
    assert result.status == "needs_clarification"
    assert result.clarification_question == "Best by revenue or by number of orders?"
    assert result.sql is None and result.rows == []
    assert "sql_validation" not in [e.step for e in result.trace]


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


# --- repair loop (Milestone 6) -----------------------------------------------------------


def test_validation_rejection_is_repaired(shop) -> None:
    plan = {"intent": "aggregate", "tables": ["shop.orders"]}
    llm = sequence(
        reply("SELECT states, count(*) AS n FROM shop.orders GROUP BY states LIMIT 10", plan=plan),
        reply("SELECT status, count(*) AS n FROM shop.orders GROUP BY status ORDER BY status LIMIT 10"),
    )
    result = AgentController(llm, max_rows=100).run("Orders per status?", shop)

    assert result.status == "success" and result.metadata.retry_count == 1
    assert result.rows == [["placed", 20], ["returned", 20], ["shipped", 20]]
    assert steps(result) == [
        ("question_received", "success"), ("schema_retrieval", "success"),
        ("sql_generation", "success"), ("sql_validation", "failed"),
        ("sql_repair", "success"), ("sql_validation", "success"), ("query_execution", "success"),
        ("completed", "success"),
    ]  # fmt: skip
    repair_prompt = llm.calls[1][1]
    assert "SELECT states, count(*)" in repair_prompt  # the failed SQL
    assert "unknown_column" in repair_prompt and "states" in repair_prompt  # the reason
    assert '"intent":"aggregate"' in repair_prompt  # the previous plan
    assert next(e for e in result.trace if e.step == "sql_repair").detail["attempt"] == 2


def test_database_error_is_repaired(shop) -> None:
    llm = sequence(
        reply("SELECT id FROM shop.orders WHERE total = 'lots' LIMIT 5"),
        reply("SELECT id FROM shop.orders WHERE total > 500 ORDER BY id LIMIT 5"),
    )
    result = AgentController(llm, max_rows=100).run("Big orders?", shop)
    assert result.status == "success" and result.metadata.retry_count == 1
    assert ("query_execution", "failed") in steps(result)
    assert "type_mismatch" in llm.calls[1][1] and "invalid input syntax" in llm.calls[1][1]


def test_division_by_zero_is_a_repairable_data_error(shop) -> None:
    llm = sequence(
        reply("SELECT id, total / 0 AS ratio FROM shop.orders LIMIT 1"),
        reply("SELECT id, total AS ratio FROM shop.orders ORDER BY id LIMIT 1"),
    )
    result = AgentController(llm, max_rows=100).run("Ratio?", shop)
    assert result.status == "success" and result.metadata.retry_count == 1
    assert "data_error" in llm.calls[1][1]


def test_timeout_asks_for_a_cheaper_query(shop) -> None:
    llm = sequence(
        reply("SELECT count(*) AS n FROM generate_series(1, 1000000000) AS g"),
        reply("SELECT count(*) AS n FROM shop.orders"),
    )
    result = AgentController(llm, max_rows=10).run("How many?", shop)
    assert result.status == "success" and result.rows == [[60]]
    assert "timeout" in llm.calls[1][1] and "cheaper query" in llm.calls[1][1]


def test_retries_are_bounded(shop) -> None:
    llm = sequence(*(reply(f"SELECT bad_{i} FROM shop.orders LIMIT 1") for i in range(5)))
    result = AgentController(llm, max_rows=100, max_retries=2).run("?", shop)
    assert result.status == "error" and result.error.code == "unknown_column"
    assert len(llm.calls) == 3 and result.metadata.retry_count == 2
    assert result.sql == "SELECT bad_2 FROM shop.orders LIMIT 1"  # the last attempt is reported
    assert [e.step for e in result.trace].count("sql_repair") == 2


def test_repeating_the_same_sql_stops_the_loop(shop) -> None:
    llm = sequence(
        reply("SELECT states FROM shop.orders LIMIT 1"), reply("select states  from shop.orders limit 1;")
    )
    result = AgentController(llm, max_rows=100, max_retries=2).run("?", shop)
    assert result.status == "error" and len(llm.calls) == 2
    assert result.trace[-2].detail["error"] == "repair returned the same SQL"


@pytest.mark.parametrize(
    "sql", ["DELETE FROM shop.orders", "SELECT id FROM shop.orders; DROP TABLE shop.orders"]
)
def test_unsafe_sql_is_not_sent_back_for_repair(shop, sql: str) -> None:
    llm = sequence(reply(sql), reply("SELECT id FROM shop.orders LIMIT 1"))
    result = AgentController(llm, max_rows=100).run("?", shop)
    assert result.status == "error" and result.error.category == "validation"
    assert len(llm.calls) == 1 and result.metadata.retry_count == 0


def test_repair_can_end_in_a_clarification(shop) -> None:
    llm = sequence(
        reply("SELECT best FROM shop.customers LIMIT 5"), reply(None, "?", clarification="Best by what?")
    )
    result = AgentController(llm, max_rows=100).run("Best customers?", shop)
    assert result.status == "needs_clarification" and result.metadata.retry_count == 1


def test_no_repair_when_retries_are_disabled(shop) -> None:
    llm = sequence(
        reply("SELECT states FROM shop.orders LIMIT 1"), reply("SELECT status FROM shop.orders LIMIT 1")
    )
    result = AgentController(llm, max_rows=100, max_retries=0).run("?", shop)
    assert result.status == "error" and len(llm.calls) == 1

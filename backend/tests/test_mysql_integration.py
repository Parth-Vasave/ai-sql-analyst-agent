"""End-to-end MySQL/MariaDB integration tests on a disposable database.

Skipped unless TEST_MYSQL_ADMIN_URL / TEST_MYSQL_AGENT_PASSWORD are set; CI runs them against a
throwaway service. The `mysql` fixture creates a read-only account, a write-capable account and a
FILE+SUPER account, and seeds a `shop_test` database shaped like the PostgreSQL test schema.
"""

from __future__ import annotations

import json

import pymysql
import pytest
from pydantic import SecretStr

from app.agent.controller import AgentController
from app.agent.executor import QueryExecutionError, execute
from app.agent.sql_validator import SQLRejectedError, validate_sql
from app.database.adapters import ErrorCategory
from app.database.connections import ConnectionConfig, ConnectionRegistry, ConnectionStatus
from app.database.profile import SamplingMode
from app.llm.client import ScriptedLLMClient


def _connect(url: str, *, sampling: SamplingMode = SamplingMode.SAFE, timeout: float = 2.0):
    registry = ConnectionRegistry(timeout_seconds=timeout)
    return registry.add(
        ConnectionConfig(id="m", name="m", url=SecretStr(url), sampling=sampling, schemas=["shop_test"])
    )


# --- privilege acceptance / rejection ----------------------------------------------------


def test_read_only_account_is_ready(mysql) -> None:
    connection = _connect(mysql.agent)
    assert connection.status is ConnectionStatus.READY
    assert connection.privileges is not None and connection.privileges.blocking == []


def test_write_capable_account_is_rejected(mysql) -> None:
    connection = _connect(mysql.writer)
    assert connection.status is ConnectionStatus.REJECTED
    assert any("unsafe privileges" in issue for issue in connection.issues)


def test_dangerous_admin_account_is_rejected(mysql) -> None:
    connection = _connect(mysql.superuser)
    assert connection.status is ConnectionStatus.REJECTED
    assert any(token in issue for issue in connection.issues for token in ("FILE", "SUPER"))


# --- profiling / structure ---------------------------------------------------------------


def test_profile_discovers_tables_and_columns(mysql) -> None:
    profile = _connect(mysql.agent).profile()
    assert profile.dialect == "mysql"
    tables = {t.name: {c.name for c in t.columns} for t in profile.tables}
    assert set(tables) == {"customers", "orders", "order_items"}  # secret_audit is not readable
    assert {"id", "customer_id", "status", "total", "ordered_at"} <= tables["orders"]
    assert any(c.sensitive for c in next(t for t in profile.tables if t.name == "customers").columns)
    assert any(not r.inferred for r in profile.relationships)  # the declared foreign key


def test_row_count_estimates_come_from_the_catalog(mysql) -> None:
    profile = _connect(mysql.agent).profile()
    orders = next(t for t in profile.tables if t.name == "orders")
    assert orders.estimated_rows is None or 50 <= orders.estimated_rows <= 70  # ish, never exact


# --- SQL validation + execution ----------------------------------------------------------


def test_safe_select_executes(mysql) -> None:
    connection = _connect(mysql.agent)
    profile = connection.profile()
    validated = validate_sql(
        "SELECT status, COUNT(*) AS n FROM shop_test.orders GROUP BY status ORDER BY status LIMIT 10",
        profile,
        "mysql",
        1000,
    )
    result = execute(connection, validated.sql, max_rows=100)
    assert result.columns == ["status", "n"]
    assert result.rows == [["placed", 20], ["returned", 20], ["shipped", 20]]


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT LOAD_FILE('/etc/passwd')",
        "SELECT SLEEP(10)",
        "SELECT table_name FROM information_schema.tables",
        "SELECT user FROM mysql.user",
        "SELECT name FROM shop_test.customers INTO OUTFILE '/tmp/leak.txt'",
    ],
)
def test_dangerous_mysql_sql_is_rejected(mysql, sql: str) -> None:
    profile = _connect(mysql.agent).profile()
    with pytest.raises(SQLRejectedError):
        validate_sql(sql, profile, "mysql", 1000)


def test_agent_answers_a_mysql_question_end_to_end(mysql) -> None:
    connection = _connect(mysql.agent)
    sql = "SELECT status, COUNT(*) AS orders FROM shop_test.orders GROUP BY status ORDER BY status LIMIT 10"
    reply = json.dumps(
        {
            "plan": None,
            "sql": sql,
            "clarification_question": None,
            "explanation": "counts",
            "chart_suggestion": "bar",
        }
    )
    result = AgentController(ScriptedLLMClient(lambda s, u: reply), max_rows=100).run(
        "How many orders per status?", connection
    )
    assert result.status == "success"
    assert result.rows == [["placed", 20], ["returned", 20], ["shipped", 20]]


# --- database-level protection (independent of the validator) ----------------------------


def test_session_timeout_is_enforced(mysql) -> None:
    # execute() bypasses the SQL validator: a slow SELECT must be stopped by the session cap.
    connection = _connect(mysql.agent, timeout=1.0)
    with pytest.raises(QueryExecutionError) as info:
        execute(connection, "SELECT SLEEP(5)", max_rows=10)
    assert info.value.category is ErrorCategory.TIMEOUT


def test_read_only_session_blocks_writes_even_for_a_privileged_account(mysql) -> None:
    # The account guard is tested above; here a write-capable account is opened through the
    # adapter's own begin_read_only, isolating the session-level read-only protection.
    connection = _connect(mysql.writer)
    with connection.engine.connect() as conn:
        connection.adapter.begin_read_only(conn)
        cursor = conn.connection.cursor()
        with pytest.raises(pymysql.err.Error) as info:
            cursor.execute("INSERT INTO shop_test.secret_audit (id, note) VALUES (999, 'x')")
    assert int(info.value.args[0]) in (1792, 1290)  # read-only transaction / server


def test_read_only_account_cannot_write_when_the_validator_is_bypassed(mysql) -> None:
    connection = _connect(mysql.agent)
    with pytest.raises(QueryExecutionError) as info:
        execute(connection, "DELETE FROM shop_test.secret_audit", max_rows=10)
    assert info.value.category is ErrorCategory.PERMISSION

"""MySQL/MariaDB SQL validation: what must be rejected and what must still be accepted.

Offline: the validator is exercised with a MySQL-flavoured profile and the ``mysql`` dialect.
Every rejection rule has a matching legitimate query that must keep working.
"""

from __future__ import annotations

import pytest

from app.agent.sql_validator import RejectionCode, SQLRejectedError, validate_sql
from app.database.profile import ColumnProfile, DatabaseProfile, SamplingMode, TableProfile

MAX_ROWS = 1000

PROFILE = DatabaseProfile(
    database_id="m",
    dialect="mysql",
    sampling=SamplingMode.SAFE,
    fingerprint="f",
    tables=[
        TableProfile(
            schema_name="shop",
            name="orders",
            kind="table",
            columns=[
                ColumnProfile(name="id", type="INT", nullable=False, primary_key=True),
                ColumnProfile(name="status", type="VARCHAR(20)", nullable=False),
                ColumnProfile(name="total", type="DECIMAL(10,2)", nullable=False),
                ColumnProfile(name="created_at", type="DATETIME", nullable=False),
            ],
        ),
        TableProfile(
            schema_name="shop",
            name="customers",
            kind="table",
            columns=[
                ColumnProfile(name="id", type="INT", nullable=False, primary_key=True),
                ColumnProfile(name="name", type="VARCHAR(50)", nullable=False),
                ColumnProfile(name="email", type="VARCHAR(50)", nullable=True, sensitive=True),
            ],
        ),
    ],
    relationships=[],
)


def validate(sql: str):
    return validate_sql(sql, PROFILE, "mysql", MAX_ROWS)


def rejected(sql: str) -> RejectionCode:
    with pytest.raises(SQLRejectedError) as info:
        validate(sql)
    return info.value.code


# --- filesystem access -------------------------------------------------------------------


def test_load_file_is_rejected() -> None:
    assert rejected("SELECT LOAD_FILE('/etc/passwd')") is RejectionCode.FORBIDDEN_FUNCTION


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT name FROM customers INTO OUTFILE '/tmp/leak.txt'",
        "SELECT name FROM customers INTO DUMPFILE '/tmp/leak.bin'",
        "SELECT name FROM customers INTO OUTFILE '/tmp/leak.txt' FIELDS TERMINATED BY ','",
    ],
)
def test_into_outfile_and_dumpfile_are_rejected(sql: str) -> None:
    # sqlglot does not parse these at all, so they fail closed as syntax errors; exp.Into in the
    # forbidden-node list is the second layer should sqlglot ever gain a model for them.
    assert rejected(sql) is RejectionCode.SYNTAX


def test_into_variable_is_rejected() -> None:
    # sqlglot models this as exp.Into, which is on the forbidden-node list.
    assert rejected("SELECT id INTO @leak FROM shop.customers") is RejectionCode.FORBIDDEN_OPERATION


# --- delay / resource abuse --------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT SLEEP(10)",
        "SELECT BENCHMARK(1000000, MD5('x'))",
        "SELECT id FROM customers WHERE SLEEP(5)",
    ],
)
def test_sleep_and_benchmark_are_rejected(sql: str) -> None:
    assert rejected(sql) is RejectionCode.FORBIDDEN_FUNCTION


def test_advisory_locking_is_rejected() -> None:
    assert rejected("SELECT GET_LOCK('x', 10)") is RejectionCode.FORBIDDEN_FUNCTION


# --- system schemas ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT table_name FROM information_schema.tables",
        "SELECT user, authentication_string FROM mysql.user",
        "SELECT * FROM performance_schema.threads",
        "SELECT * FROM sys.schema_table_statistics",
    ],
)
def test_system_schemas_are_rejected(sql: str) -> None:
    assert rejected(sql) is RejectionCode.SYSTEM_TABLE


def test_system_schema_qualified_with_backticks_is_rejected() -> None:
    assert rejected("SELECT `user` FROM `mysql`.`user`") is RejectionCode.SYSTEM_TABLE


# --- existing safety rules still apply on MySQL ------------------------------------------


@pytest.mark.parametrize(
    ("sql", "code"),
    [
        ("DELETE FROM shop.orders", RejectionCode.NOT_SELECT),
        ("UPDATE shop.orders SET total = 0", RejectionCode.NOT_SELECT),
        ("DROP TABLE shop.orders", RejectionCode.NOT_SELECT),
        ("SELECT id FROM shop.orders; DROP TABLE shop.orders", RejectionCode.MULTIPLE_STATEMENTS),
        ("WITH x AS (DELETE FROM shop.orders) SELECT * FROM x", RejectionCode.FORBIDDEN_OPERATION),
        ("SELECT id FROM shop.orders FOR UPDATE", RejectionCode.FORBIDDEN_OPERATION),
        ("SELECT * FROM shop.orders", RejectionCode.STAR),
        ("SELECT email FROM shop.customers", RejectionCode.UNKNOWN_COLUMN),  # sensitive column
        ("SELECT id FROM shop.secret_audit", RejectionCode.UNKNOWN_TABLE),
    ],
)
def test_existing_protections_hold_on_mysql(sql: str, code: RejectionCode) -> None:
    assert rejected(sql) is code


# --- legitimate MySQL queries must keep working ------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT status, COUNT(*) AS n FROM shop.orders GROUP BY status ORDER BY n DESC LIMIT 10",
        "SELECT c.name, o.total FROM shop.orders o JOIN shop.customers c ON c.id = o.id"
        " WHERE o.total > 100 ORDER BY o.total DESC LIMIT 5",
        "SELECT YEAR(o.created_at) AS y, SUM(o.total) AS total FROM shop.orders o"
        " GROUP BY y HAVING total > 0 ORDER BY y LIMIT 100",
        "SELECT DISTINCT status FROM shop.orders LIMIT 20",
        "SELECT id, NOW() AS fetched_at FROM shop.orders LIMIT 3",
        "SELECT id, UNIX_TIMESTAMP(created_at) AS ts FROM shop.orders LIMIT 3",
        "SELECT id, IF(status = 'placed', 1, 0) AS placed FROM shop.orders LIMIT 3",
        "SELECT id, COALESCE(total, 0) AS t FROM shop.orders LIMIT 3",
        "SELECT id FROM shop.orders WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) LIMIT 10",
        "SELECT id FROM shop.orders LIMIT 5 OFFSET 10",
        "SELECT id FROM shop.orders LIMIT 10, 20",
    ],
)
def test_legitimate_mysql_queries_are_accepted(sql: str) -> None:
    result = validate(sql)
    assert result.limit <= MAX_ROWS
    assert validate(result.sql).sql == result.sql  # the regenerated SQL is valid and stable


def test_missing_limit_is_added_and_an_oversized_one_is_clamped() -> None:
    added = validate("SELECT id FROM shop.orders")
    assert (added.limit, added.limit_action) == (MAX_ROWS, "added")
    clamped = validate("SELECT id FROM shop.orders LIMIT 100000")
    assert (clamped.limit, clamped.limit_action) == (MAX_ROWS, "clamped")


def test_sensitive_columns_stay_unavailable() -> None:
    assert rejected("SELECT email FROM shop.customers") is RejectionCode.UNKNOWN_COLUMN

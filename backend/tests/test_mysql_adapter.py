"""MySQL/MariaDB adapter unit tests: no database required.

Covers URL/driver normalization, the read-only + timeout session configuration, SHOW GRANTS
parsing, error classification and the catalog queries behind readable tables / row estimates.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pymysql
import pytest
from pydantic import SecretStr

from app.database.adapters import SUPPORTED_BACKENDS, ErrorCategory, get_adapter
from app.database.adapters.mysql import MysqlAdapter, parse_show_grants
from app.database.connections import ConnectionConfig, ConnectionRegistry


def _adapter() -> MysqlAdapter:
    return MysqlAdapter()


# --- registry / URLs ----------------------------------------------------------------------


def test_mysql_and_mariadb_are_supported_backends() -> None:
    assert {"mysql", "mariadb"} <= set(SUPPORTED_BACKENDS)
    assert isinstance(get_adapter("mysql"), MysqlAdapter)
    assert isinstance(get_adapter("mariadb"), MysqlAdapter)


@pytest.mark.parametrize(
    ("url", "drivername"),
    [
        ("mysql://u:p@localhost/db", "mysql+pymysql"),
        ("mariadb://u:p@localhost/db", "mariadb+pymysql"),
        ("mysql+mysqldb://u:p@localhost/db", "mysql+pymysql"),  # we do not ship MySQLdb
        ("mariadb+mysqldb://u:p@localhost/db", "mariadb+pymysql"),
        ("mysql+pymysql://u:p@localhost/db", "mysql+pymysql"),
    ],
)
def test_urls_are_normalized_to_the_shipped_driver(url: str, drivername: str) -> None:
    connection = ConnectionRegistry(timeout_seconds=1).add(
        ConnectionConfig(id="a", name="a", url=SecretStr(url)), verify=False
    )
    assert connection.engine.url.drivername == drivername
    assert connection.adapter.backend == "mysql"
    assert connection.adapter.sqlglot_dialect == "mysql"


# --- read-only session + timeout ---------------------------------------------------------


class _FakeConnection:
    def __init__(self, is_mariadb: bool) -> None:
        self.dialect = SimpleNamespace(is_mariadb=is_mariadb)
        self.statements: list[str] = []

    def execute(self, statement: Any, parameters: Any = None) -> None:
        self.statements.append(str(statement))


def _session_statements(is_mariadb: bool) -> list[str]:
    adapter = _adapter()
    adapter.connect_args(5.0)  # stores the timeout on the adapter, as the engine does
    conn: Any = _FakeConnection(is_mariadb)
    adapter.begin_read_only(conn)
    return conn.statements


def test_connect_args_request_a_read_only_session_and_a_connect_timeout() -> None:
    args = _adapter().connect_args(5.0)
    assert args["connect_timeout"] == 5
    assert "READ ONLY" in args["init_command"].upper()


def test_mysql_session_is_read_only_with_max_execution_time() -> None:
    assert _session_statements(is_mariadb=False) == [
        "SET SESSION TRANSACTION READ ONLY",
        "SET SESSION max_execution_time = 5000",
    ]


def test_mariadb_session_uses_max_statement_time() -> None:
    assert _session_statements(is_mariadb=True) == [
        "SET SESSION TRANSACTION READ ONLY",
        "SET SESSION max_statement_time = 5",
    ]


def test_timeout_of_zero_is_clamped_so_it_cannot_disable_the_cap() -> None:
    adapter = _adapter()
    adapter.connect_args(0)
    conn: Any = _FakeConnection(is_mariadb=False)
    adapter.begin_read_only(conn)
    assert conn.statements[1] == "SET SESSION max_execution_time = 1"  # never 0 (unlimited)


# --- SHOW GRANTS parsing -----------------------------------------------------------------


def test_read_only_account_is_accepted() -> None:
    report = parse_show_grants(
        ["GRANT USAGE ON *.* TO `agent`@`%`", "GRANT SELECT ON `shop`.* TO `agent`@`%`"]
    )
    assert report.is_read_only and report.blocking == [] and report.warnings == []


def test_global_select_only_is_accepted() -> None:
    assert parse_show_grants(["GRANT SELECT ON *.* TO `agent`@`%`"]).is_read_only


@pytest.mark.parametrize(
    "line",
    [
        "GRANT SELECT, INSERT ON `shop`.* TO `a`@`%`",
        "GRANT UPDATE ON `shop`.* TO `a`@`%`",
        "GRANT DELETE ON `shop`.`orders` TO `a`@`%`",
        "GRANT CREATE, DROP, ALTER ON `shop`.* TO `a`@`%`",
        "GRANT INDEX, REFERENCES, TRIGGER ON `shop`.* TO `a`@`%`",
        "GRANT EVENT, EXECUTE ON `shop`.* TO `a`@`%`",
        "GRANT FILE ON *.* TO `a`@`%`",
        "GRANT SUPER ON *.* TO `a`@`%`",
        "GRANT PROCESS ON *.* TO `a`@`%`",
        "GRANT SELECT ON *.* TO `a`@`%` WITH GRANT OPTION",
    ],
)
def test_write_and_admin_privileges_are_blocking(line: str) -> None:
    report = parse_show_grants([line])
    assert not report.is_read_only and report.blocking


def test_all_privileges_with_grant_option_is_blocked() -> None:
    report = parse_show_grants(["GRANT ALL PRIVILEGES ON *.* TO `root`@`%` WITH GRANT OPTION"])
    assert not report.is_read_only
    assert any("ALL PRIVILEGES" in reason for reason in report.blocking)
    assert any("GRANT OPTION" in reason for reason in report.blocking)


def test_multiple_grants_are_all_considered() -> None:
    report = parse_show_grants(
        [
            "GRANT USAGE ON *.* TO `a`@`%`",
            "GRANT SELECT ON `analytics`.* TO `a`@`%`",
            "GRANT SELECT ON `shop`.* TO `a`@`%`",
        ]
    )
    assert report.is_read_only


def test_mitigated_privileges_are_warnings_not_blocking() -> None:
    report = parse_show_grants(["GRANT SELECT, CREATE TEMPORARY TABLES, LOCK TABLES ON `shop`.* TO `a`@`%`"])
    assert report.is_read_only and report.warnings
    assert "CREATE TEMPORARY TABLES" in report.warnings[0]


def test_mariadb_password_hash_and_syntax_do_not_leak_or_break_parsing() -> None:
    report = parse_show_grants(
        [
            "GRANT USAGE ON *.* TO 'a'@'%' IDENTIFIED BY PASSWORD '*0123ABCDEF'",
            "GRANT SELECT ON `shop`.* TO 'a'@'%'",
        ]
    )
    assert report.is_read_only
    # The hash is never echoed into the report.
    assert all("0123ABCDEF" not in reason for reason in [*report.blocking, *report.warnings])


def test_unrecognized_grant_fails_closed_without_echoing_the_line() -> None:
    report = parse_show_grants(["GRANT `some_role` TO `a`@`%`"])
    assert not report.is_read_only
    assert all("some_role" not in reason for reason in report.blocking)


# --- error classification ----------------------------------------------------------------


def _wrapped(code: int) -> Exception:
    return Exception("driver wrapper", pymysql.err.ProgrammingError(code, "boom"))


@pytest.mark.parametrize(
    ("code", "category"),
    [
        (1064, ErrorCategory.SYNTAX),
        (1054, ErrorCategory.UNDEFINED_COLUMN),
        (1146, ErrorCategory.UNDEFINED_TABLE),
        (1305, ErrorCategory.UNDEFINED_FUNCTION),
        (1366, ErrorCategory.TYPE_MISMATCH),
        (1365, ErrorCategory.DATA_ERROR),
        (1142, ErrorCategory.PERMISSION),
        (1792, ErrorCategory.READ_ONLY),
        (3024, ErrorCategory.TIMEOUT),  # MySQL max_execution_time
        (1969, ErrorCategory.TIMEOUT),  # MariaDB max_statement_time
        (1205, ErrorCategory.TIMEOUT),
        (9999, ErrorCategory.OTHER),
    ],
)
def test_mysql_error_codes_are_classified(code: int, category: ErrorCategory) -> None:
    error = _wrapped(code)
    error.orig = pymysql.err.ProgrammingError(code, "boom")  # type: ignore[attr-defined]
    assert _adapter().classify_error(error) is category


# --- catalog queries ---------------------------------------------------------------------


class _Result:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def scalars(self) -> Any:
        return (row[0] for row in self._rows)

    def __iter__(self) -> Any:
        return iter(self._rows)


class _CatalogConnection:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows
        self.queries: list[str] = []

    def execute(self, statement: Any, parameters: Any = None) -> _Result:
        self.queries.append(str(statement))
        return _Result(self._rows)


def test_readable_tables_returns_table_names() -> None:
    conn: Any = _CatalogConnection([("orders",), ("customers",)])
    assert _adapter().readable_tables(conn, "shop") == {"orders", "customers"}
    assert "information_schema.TABLES" in conn.queries[0]


def test_estimate_row_counts_parses_catalog_rows() -> None:
    conn: Any = _CatalogConnection([("orders", 60), ("customers", 25)])
    assert _adapter().estimate_row_counts(conn, "shop") == {"orders": 60, "customers": 25}


def test_system_schemas_are_never_readable_or_counted() -> None:
    conn: Any = _CatalogConnection([("user",)])
    for schema in ("information_schema", "mysql", "performance_schema", "sys"):
        assert _adapter().readable_tables(conn, schema) == set()
        assert _adapter().estimate_row_counts(conn, schema) == {}
    assert conn.queries == []  # no query was even run against a system schema

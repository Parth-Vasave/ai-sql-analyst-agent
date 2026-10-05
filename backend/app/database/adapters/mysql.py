"""MySQL and MariaDB behaviour behind the DatabaseAdapter interface.

Both engines share one adapter: they are SQL-compatible and sqlglot models them with the
``mysql`` dialect. The differences that matter to us are the session variable that caps a
query's runtime (``max_execution_time`` on MySQL, ``max_statement_time`` on MariaDB) and the
driver in the URL, which we normalize to the pure-Python PyMySQL that the project ships.

The account itself is the first safety layer: ``check_privileges`` refuses any account that
can modify data, change schema, read or write files, or administer the server. Read-only
sessions and the SQL validator are the layers behind it.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import Connection, text
from sqlalchemy.engine import URL

from app.database.adapters.base import DatabaseAdapter, ErrorCategory, PrivilegeReport

# Schemas that hold server metadata rather than application data. Never profiled or queried.
SYSTEM_SCHEMAS = frozenset({"information_schema", "mysql", "performance_schema", "sys"})

# Privileges that make an account unsafe: it could change data, alter schema, touch the
# filesystem or the server, or escalate. Any of these rejects the connection.
_BLOCKING_PRIVILEGES = frozenset(
    {
        "CREATE",
        "CREATE ROLE",
        "CREATE ROUTINE",
        "CREATE TABLESPACE",
        "CREATE USER",
        "CREATE VIEW",
        "ALTER",
        "ALTER ROUTINE",
        "DELETE",
        "DROP",
        "DROP ROLE",
        "EVENT",
        "EXECUTE",
        "FILE",
        "GRANT OPTION",
        "INDEX",
        "INSERT",
        "PROCESS",
        "RELOAD",
        "REFERENCES",
        "REPLICATION CLIENT",
        "REPLICATION SLAVE",
        "SHUTDOWN",
        "SUPER",
        "TRIGGER",
        "UPDATE",
    }
)

# Privileges that read-only sessions and the validator already mitigate, but which the
# operator should still see. Reported as warnings, not as a rejection.
_WARNING_PRIVILEGES = frozenset({"CREATE TEMPORARY TABLES", "LOCK TABLES", "SHOW VIEW"})

# USAGE confers nothing; SELECT is exactly what we allow.
_IGNORED_PRIVILEGES = frozenset({"USAGE", "SELECT"})

_GRANT = re.compile(r"^GRANT\s+(?P<privileges>.+?)\s+ON\s+(?P<scope>\S+)\s+TO\s", re.IGNORECASE)

# MySQL error numbers (MariaDB keeps the same numbering for the shared codes).
# https://dev.mysql.com/doc/mysql-errors/8.0/en/server-error-reference.html
_ERROR_CODES: dict[int, ErrorCategory] = {
    1064: ErrorCategory.SYNTAX,  # parse error
    1149: ErrorCategory.SYNTAX,  # syntax error in a prepared statement
    1054: ErrorCategory.UNDEFINED_COLUMN,
    1055: ErrorCategory.UNDEFINED_COLUMN,  # not in GROUP BY
    1146: ErrorCategory.UNDEFINED_TABLE,
    1305: ErrorCategory.UNDEFINED_FUNCTION,
    1582: ErrorCategory.UNDEFINED_FUNCTION,  # wrong parameter count
    1264: ErrorCategory.TYPE_MISMATCH,  # out of range
    1292: ErrorCategory.TYPE_MISMATCH,  # truncated incorrect value
    1366: ErrorCategory.TYPE_MISMATCH,  # incorrect value for column
    1367: ErrorCategory.TYPE_MISMATCH,  # illegal value
    1406: ErrorCategory.DATA_ERROR,  # data too long
    1365: ErrorCategory.DATA_ERROR,  # division by zero
    1048: ErrorCategory.DATA_ERROR,  # column cannot be null
    3819: ErrorCategory.DATA_ERROR,  # check constraint violated
    1044: ErrorCategory.PERMISSION,  # access denied to database
    1045: ErrorCategory.PERMISSION,  # access denied for user
    1142: ErrorCategory.PERMISSION,  # command denied to user for table
    1143: ErrorCategory.PERMISSION,  # command denied to user for column
    1227: ErrorCategory.PERMISSION,  # access denied; need (at least one of) the privilege(s)
    1290: ErrorCategory.READ_ONLY,  # server is running with --read-only
    1792: ErrorCategory.READ_ONLY,  # cannot execute in a read-only transaction
    1205: ErrorCategory.TIMEOUT,  # lock wait timeout exceeded
    3024: ErrorCategory.TIMEOUT,  # query execution interrupted: max_execution_time exceeded
    1969: ErrorCategory.TIMEOUT,  # MariaDB: max_statement_time exceeded
}


def parse_show_grants(lines: list[str]) -> PrivilegeReport:
    """Turn the rows of ``SHOW GRANTS`` into a PrivilegeReport.

    Output is untrusted server text (and, on older MariaDB, can embed a password hash), so it
    is parsed for privilege *names* only; no raw line is ever echoed. A GRANT line we cannot
    classify is treated as blocking rather than ignored, so an unfamiliar syntax fails closed.
    """
    report = PrivilegeReport()
    blocking: set[str] = set()
    warnings: set[str] = set()
    for raw in lines:
        line = raw.strip().rstrip(";")
        if not line:
            continue
        if re.search(r"\bWITH\s+GRANT\s+OPTION\b", line, re.IGNORECASE):
            blocking.add("GRANT OPTION")
        match = _GRANT.match(line)
        if match is None:
            if line.upper().startswith("GRANT"):
                blocking.add("unrecognized grant statement")
            continue
        scope = match.group("scope").strip("`")
        global_scope = scope == "*.*"
        for token in match.group("privileges").split(","):
            privilege = " ".join(token.strip().upper().split())
            if privilege.endswith(" PRIVILEGES"):
                privilege = privilege.removesuffix(" PRIVILEGES")
            if not privilege:
                continue
            if privilege == "ALL":
                blocking.add("ALL PRIVILEGES")
            elif privilege in _BLOCKING_PRIVILEGES:
                blocking.add(privilege)
            elif privilege in _WARNING_PRIVILEGES:
                warnings.add(privilege)
            elif privilege in _IGNORED_PRIVILEGES:
                continue
            elif global_scope:
                blocking.add(privilege)  # an unknown global capability is not read-only
            else:
                warnings.add(privilege)
    if blocking:
        report.blocking.append("account has unsafe privileges: " + ", ".join(sorted(blocking)))
    if warnings:
        report.warnings.append("account has privileges: " + ", ".join(sorted(warnings)))
    return report


def _error_code(error: BaseException) -> int | None:
    original = getattr(error, "orig", error)
    args = getattr(original, "args", ())
    if args and isinstance(args[0], int):
        return args[0]
    for attribute in ("errno", "code"):
        value = getattr(original, attribute, None)
        if isinstance(value, int):
            return value
    return None


class MysqlAdapter(DatabaseAdapter):
    backend = "mysql"
    sqlglot_dialect = "mysql"  # MariaDB is close enough that sqlglot's mysql dialect covers it

    def __init__(self) -> None:
        # Timeout in seconds, captured from connect_args (the interface gives begin_read_only
        # no timeout); applied per session as the engine's runtime cap.
        self._timeout_seconds = 5.0

    def normalize_url(self, url: URL) -> URL:
        # We ship PyMySQL; bare mysql:// / mariadb:// would make SQLAlchemy look for MySQLdb.
        return url.set(drivername=f"{url.get_backend_name()}+pymysql")

    def connect_args(self, timeout_seconds: float) -> dict[str, Any]:
        self._timeout_seconds = timeout_seconds
        return {
            "connect_timeout": 5,
            # The session default, so even a connection used without begin_read_only is read-only.
            "init_command": "SET SESSION TRANSACTION READ ONLY",
        }

    def begin_read_only(self, conn: Connection) -> None:
        conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
        timeout = max(0.001, float(self._timeout_seconds))
        if getattr(conn.dialect, "is_mariadb", False):
            conn.execute(text(f"SET SESSION max_statement_time = {timeout:g}"))
        else:
            # max_execution_time is milliseconds and applies to read-only SELECTs, which is all we run.
            conn.execute(text(f"SET SESSION max_execution_time = {int(timeout * 1000)}"))

    def check_privileges(self, conn: Connection) -> PrivilegeReport:
        lines = [row[0] for row in conn.execute(text("SHOW GRANTS"))]
        return parse_show_grants(lines)

    def classify_error(self, error: BaseException) -> ErrorCategory:
        code = _error_code(error)
        if code is not None:
            return _ERROR_CODES.get(code, ErrorCategory.OTHER)
        original = getattr(error, "orig", error)
        name = type(original).__name__.lower()
        if "timeout" in name:
            return ErrorCategory.TIMEOUT
        if "operational" in name:
            return ErrorCategory.OTHER
        return ErrorCategory.OTHER

    def readable_tables(self, conn: Connection, schema: str) -> set[str] | None:
        if schema in SYSTEM_SCHEMAS:
            return set()
        rows = conn.execute(
            text(
                "SELECT TABLE_NAME FROM information_schema.TABLES"
                " WHERE TABLE_SCHEMA = :schema AND TABLE_TYPE IN ('BASE TABLE', 'VIEW')",
            ),
            {"schema": schema},
        )
        return set(rows.scalars())

    def estimate_row_counts(self, conn: Connection, schema: str) -> dict[str, int]:
        if schema in SYSTEM_SCHEMAS:
            return {}
        rows = conn.execute(
            text(
                "SELECT TABLE_NAME, TABLE_ROWS FROM information_schema.TABLES"
                " WHERE TABLE_SCHEMA = :schema AND TABLE_TYPE = 'BASE TABLE'"
                " AND TABLE_ROWS IS NOT NULL",
            ),
            {"schema": schema},
        )
        return {name: int(count) for name, count in rows}

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, text
from sqlalchemy.engine import URL

from app.database.adapters.base import DatabaseAdapter, ErrorCategory, PrivilegeReport

_SYSTEM_SCHEMAS = "('pg_catalog', 'information_schema')"

_WRITABLE_TABLES = text(f"""
    SELECT n.nspname || '.' || c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f')
      AND n.nspname NOT IN {_SYSTEM_SCHEMAS} AND n.nspname NOT LIKE 'pg\\_%'
      AND (has_table_privilege(c.oid, 'INSERT') OR has_table_privilege(c.oid, 'UPDATE')
           OR has_table_privilege(c.oid, 'DELETE') OR has_table_privilege(c.oid, 'TRUNCATE'))
    ORDER BY 1
    LIMIT 10
""")

_CREATABLE_SCHEMAS = text(f"""
    SELECT nspname FROM pg_namespace
    WHERE nspname NOT IN {_SYSTEM_SCHEMAS} AND nspname NOT LIKE 'pg\\_%'
      AND has_schema_privilege(oid, 'CREATE')
    ORDER BY 1
""")


# SQLSTATE codes: https://www.postgresql.org/docs/current/errcodes-appendix.html
_SQLSTATE: dict[str, ErrorCategory] = {
    "57014": ErrorCategory.TIMEOUT,  # query_canceled (statement_timeout)
    "42601": ErrorCategory.SYNTAX,
    "42703": ErrorCategory.UNDEFINED_COLUMN,
    "42P01": ErrorCategory.UNDEFINED_TABLE,
    "42883": ErrorCategory.UNDEFINED_FUNCTION,
    "42804": ErrorCategory.TYPE_MISMATCH,
    "22P02": ErrorCategory.TYPE_MISMATCH,
    "42501": ErrorCategory.PERMISSION,
    "25006": ErrorCategory.READ_ONLY,
}


class PostgresAdapter(DatabaseAdapter):
    backend = "postgresql"
    sqlglot_dialect = "postgres"

    def normalize_url(self, url: URL) -> URL:
        # We ship psycopg 3; plain postgresql:// would make SQLAlchemy look for psycopg2.
        return url.set(drivername="postgresql+psycopg")

    def connect_args(self, timeout_seconds: float) -> dict[str, Any]:
        timeout_ms = int(timeout_seconds * 1000)
        return {
            "connect_timeout": 5,
            "options": f"-c default_transaction_read_only=on -c statement_timeout={timeout_ms}",
        }

    def begin_read_only(self, conn: Connection) -> None:
        conn.execute(text("SET TRANSACTION READ ONLY"))

    def check_privileges(self, conn: Connection) -> PrivilegeReport:
        report = PrivilegeReport()
        role = conn.execute(
            text(
                "SELECT rolsuper, rolcreaterole, rolbypassrls, rolcreatedb"
                " FROM pg_roles WHERE rolname = current_user"
            )
        ).one()
        if role.rolsuper:
            report.blocking.append("account is a superuser")
        if role.rolcreaterole:
            report.blocking.append("account can create roles")
        if role.rolbypassrls:
            report.blocking.append("account bypasses row-level security")
        if role.rolcreatedb:
            report.warnings.append("account can create databases")

        writable = conn.execute(_WRITABLE_TABLES).scalars().all()
        if writable:
            report.blocking.append("account can modify tables: " + ", ".join(writable))

        schemas = conn.execute(_CREATABLE_SCHEMAS).scalars().all()
        if schemas:
            report.warnings.append("account can create objects in schema(s): " + ", ".join(schemas))
        if conn.execute(text("SELECT has_database_privilege(current_database(), 'TEMP')")).scalar():
            report.warnings.append("account can create temporary tables")
        return report

    def classify_error(self, error: BaseException) -> ErrorCategory:
        sqlstate = getattr(getattr(error, "orig", error), "sqlstate", None)
        if sqlstate in _SQLSTATE:
            return _SQLSTATE[sqlstate]
        if sqlstate and sqlstate.startswith("42"):
            return ErrorCategory.SYNTAX
        return ErrorCategory.OTHER

    def readable_tables(self, conn: Connection, schema: str) -> set[str] | None:
        rows = conn.execute(
            text(
                "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
                " WHERE n.nspname = :schema AND c.relkind IN ('r', 'p', 'v', 'm', 'f')"
                " AND has_table_privilege(c.oid, 'SELECT')"
            ),
            {"schema": schema},
        )
        return set(rows.scalars())

    def estimate_row_counts(self, conn: Connection, schema: str) -> dict[str, int]:
        rows = conn.execute(
            text(
                "SELECT c.relname, c.reltuples::bigint FROM pg_class c"
                " JOIN pg_namespace n ON n.oid = c.relnamespace"
                " WHERE n.nspname = :schema AND c.relkind IN ('r', 'p', 'm') AND c.reltuples >= 0"
            ),
            {"schema": schema},
        )
        return {name: int(count) for name, count in rows}

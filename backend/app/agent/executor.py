"""Execute validated SQL on a read-only connection and collect the result.

Only SQL accepted by sql_validator reaches this module.

The row cap is enforced here, on the client side, regardless of the SQL's own LIMIT:
at most max_rows rows are ever fetched, and `truncated` says whether more existed.
"""

from __future__ import annotations

import datetime as dt
import time
import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy.exc import DBAPIError

from app.database.adapters import ErrorCategory
from app.database.connections import DatabaseConnection


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    duration_ms: int


class QueryExecutionError(RuntimeError):
    def __init__(self, category: ErrorCategory, message: str, duration_ms: int) -> None:
        super().__init__(message)
        self.category = category
        self.message = message
        self.duration_ms = duration_ms


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() and abs(value) < 2**53 else float(value)
    if isinstance(value, (dt.date, dt.datetime, dt.time)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (bytes, memoryview)):
        return f"<{len(bytes(value))} bytes>"
    return value


def _error_message(error: Exception) -> str:
    """The database's own first message line, e.g. 'column "states" does not exist'."""
    original = getattr(error, "orig", None) or error
    return str(original).strip().splitlines()[0][:500] if str(original).strip() else error.__class__.__name__


def execute(connection: DatabaseConnection, sql: str, max_rows: int) -> QueryResult:
    started = time.perf_counter()
    try:
        with connection.connect() as conn:
            connection.adapter.begin_read_only(conn)
            # A plain DB-API cursor, called without parameters, sends the validated SQL exactly
            # as it is: SQLAlchemy's text() would treat ':name' in string literals as bind
            # parameters, and a parameter list would make the driver parse '%' as placeholders.
            cursor = conn.connection.cursor()
            try:
                cursor.execute(sql)
                columns = [d[0] for d in cursor.description or []]
                fetched = cursor.fetchmany(max_rows + 1)
            finally:
                cursor.close()
            conn.rollback()
    except (DBAPIError, connection.engine.dialect.loaded_dbapi.Error) as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        raise QueryExecutionError(
            connection.adapter.classify_error(exc), _error_message(exc), duration_ms
        ) from None
    duration_ms = int((time.perf_counter() - started) * 1000)
    rows = [[_json_safe(v) for v in row] for row in fetched[:max_rows]]
    return QueryResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=len(fetched) > max_rows,
        duration_ms=duration_ms,
    )

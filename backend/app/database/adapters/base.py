"""Engine-specific behaviour behind one small interface.

SQLAlchemy Core handles connections and schema reflection for every engine. An adapter only
covers what genuinely differs between engines: URL normalization, how a session is made
read-only with a timeout, how to check what the connected account may do, and cheap
row-count estimates. Adding an engine (e.g. MySQL) means adding one adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Connection
from sqlalchemy.engine import URL


class ErrorCategory(StrEnum):
    """Engine-independent classes of query failure, used to decide on repair and retries."""

    TIMEOUT = "timeout"
    SYNTAX = "syntax"
    UNDEFINED_COLUMN = "undefined_column"
    UNDEFINED_TABLE = "undefined_table"
    UNDEFINED_FUNCTION = "undefined_function"
    TYPE_MISMATCH = "type_mismatch"
    PERMISSION = "permission"
    READ_ONLY = "read_only"
    OTHER = "other"


class PrivilegeReport(BaseModel):
    """What the connected account is allowed to do.

    blocking: capabilities that let the account modify existing data or escalate; the
        connection is refused while any are present.
    warnings: capabilities that are mitigated by read-only sessions and the SQL validator
        (e.g. creating objects in a schema) but worth surfacing to the operator.
    """

    blocking: list[str] = []
    warnings: list[str] = []

    @property
    def is_read_only(self) -> bool:
        return not self.blocking


class DatabaseAdapter(ABC):
    #: SQLAlchemy backend name, e.g. "postgresql".
    backend: str
    #: sqlglot dialect used to parse and validate generated SQL.
    sqlglot_dialect: str

    def normalize_url(self, url: URL) -> URL:
        """Pick the driver we ship with, e.g. postgresql:// -> postgresql+psycopg://."""
        return url

    @abstractmethod
    def connect_args(self, timeout_seconds: float) -> dict[str, Any]:
        """Driver arguments that make every session read-only with a statement timeout."""

    def begin_read_only(self, conn: Connection) -> None:  # noqa: B027 - optional hook, no-op by default
        """Called at the start of each transaction; reinforce read-only mode if possible."""

    @abstractmethod
    def check_privileges(self, conn: Connection) -> PrivilegeReport:
        """Inspect what the connected account may do."""

    def readable_tables(self, conn: Connection, schema: str) -> set[str] | None:
        """Tables/views the account can SELECT from; None if the engine cannot tell."""
        return None

    def classify_error(self, error: BaseException) -> ErrorCategory:
        """Map a driver exception to an ErrorCategory."""
        return ErrorCategory.OTHER

    def estimate_row_counts(self, conn: Connection, schema: str) -> dict[str, int]:
        """Cheap (catalog-based) row-count estimates; empty if unavailable."""
        return {}

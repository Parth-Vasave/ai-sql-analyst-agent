from __future__ import annotations

from app.database.adapters.base import DatabaseAdapter, ErrorCategory, PrivilegeReport
from app.database.adapters.mysql import MysqlAdapter
from app.database.adapters.postgres import PostgresAdapter

# MariaDB speaks the same protocol and dialect as MySQL, so both backend names share one adapter.
_ADAPTERS: dict[str, type[DatabaseAdapter]] = {
    "postgresql": PostgresAdapter,
    "mysql": MysqlAdapter,
    "mariadb": MysqlAdapter,
}

SUPPORTED_BACKENDS = tuple(sorted(_ADAPTERS))


class UnsupportedDatabaseError(ValueError):
    pass


def get_adapter(backend: str) -> DatabaseAdapter:
    try:
        return _ADAPTERS[backend]()
    except KeyError:
        supported = ", ".join(SUPPORTED_BACKENDS)
        raise UnsupportedDatabaseError(f"Unsupported database {backend!r}; supported: {supported}") from None


__all__ = [
    "DatabaseAdapter",
    "ErrorCategory",
    "PrivilegeReport",
    "SUPPORTED_BACKENDS",
    "UnsupportedDatabaseError",
    "get_adapter",
]

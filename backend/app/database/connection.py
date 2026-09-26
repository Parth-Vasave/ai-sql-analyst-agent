"""Connections for the read-only agent account."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from app.config import Settings


@contextmanager
def agent_connection(settings: Settings) -> Iterator[psycopg.Connection]:
    """Open a short-lived connection as sql_agent.

    Short-lived connections suit serverless hosting (e.g. Vercel functions) where a
    process-wide pool does not survive between invocations. The read-only transaction
    and statement timeout are also set per session so they hold even if the role
    defaults were changed.
    """
    timeout_ms = int(settings.query_timeout_seconds * 1000)
    with psycopg.connect(
        settings.database_url.get_secret_value(),
        connect_timeout=5,
        options=f"-c statement_timeout={timeout_ms} -c default_transaction_read_only=on",
    ) as conn:
        yield conn


def check_database(settings: Settings) -> bool:
    try:
        with agent_connection(settings) as conn:
            conn.execute("SELECT 1")
        return True
    except psycopg.Error:
        return False

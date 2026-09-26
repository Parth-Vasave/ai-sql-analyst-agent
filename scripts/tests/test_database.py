"""Integration tests: schema, seeding and the read-only sql_agent role.

These prove the database itself refuses writes from the agent account, independently
of any application-level SQL validation.
"""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from psycopg import errors

from scripts import clean_data, seed_database

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_raw_datagovin.csv"


def test_seed_loads_normalized_rows(seeded_db: str) -> None:
    with psycopg.connect(seeded_db) as conn:
        counts = conn.execute(
            "SELECT (SELECT count(*) FROM commodities), (SELECT count(*) FROM markets),"
            " (SELECT count(*) FROM daily_prices)"
        ).fetchone()
    assert counts == (2, 3, 8)


def test_seed_is_idempotent(seeded_db: str, tmp_path: Path) -> None:
    clean_data.run([FIXTURE], output_dir=tmp_path)
    result = seed_database.seed(seeded_db, tmp_path / clean_data.OUTPUT_NAME)
    assert (result.commodities_added, result.markets_added, result.prices_added) == (0, 0, 0)


def test_agent_can_select(agent_conn: psycopg.Connection) -> None:
    row = agent_conn.execute(
        "SELECT m.state, round(avg(p.modal_price)) FROM daily_prices p"
        " JOIN markets m ON m.id = p.market_id JOIN commodities c ON c.id = p.commodity_id"
        " WHERE c.name = 'Wheat' AND p.arrival_date >= '2024-01-01'"
        " GROUP BY m.state ORDER BY 2 DESC LIMIT 1"
    ).fetchone()
    assert row is not None and row[0] == "Test State A"


def test_agent_role_has_no_dangerous_attributes(agent_conn: psycopg.Connection) -> None:
    row = agent_conn.execute(
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolinherit"
        " FROM pg_roles WHERE rolname = current_user"
    ).fetchone()
    assert row == (False, False, False, False, False, False)


def test_agent_session_defaults(agent_conn: psycopg.Connection) -> None:
    assert agent_conn.execute("SHOW default_transaction_read_only").fetchone() == ("on",)
    assert agent_conn.execute("SHOW statement_timeout").fetchone() == ("1s",)


FORBIDDEN = [
    "INSERT INTO commodities (name) VALUES ('Injected')",
    "UPDATE daily_prices SET modal_price = 1",
    "DELETE FROM daily_prices",
    "TRUNCATE daily_prices",
    "DROP TABLE daily_prices",
    "ALTER TABLE daily_prices ADD COLUMN x int",
    "CREATE TABLE evil (id int)",
    "CREATE TEMP TABLE evil (id int)",
    "CREATE INDEX evil_idx ON daily_prices (variety)",
    "CREATE ROLE evil",
]


@pytest.mark.parametrize("statement", FORBIDDEN)
def test_agent_cannot_write_even_with_read_write_transaction(
    agent_conn: psycopg.Connection, statement: str
) -> None:
    # A session can override default_transaction_read_only, so privileges must hold on their own.
    agent_conn.execute("SET default_transaction_read_only = off")
    with pytest.raises((errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction)):
        agent_conn.execute(statement)


def test_statement_timeout_cancels_slow_queries(agent_conn: psycopg.Connection) -> None:
    with pytest.raises(errors.QueryCanceled):
        agent_conn.execute("SELECT pg_sleep(3)")


def test_agent_grant_is_a_no_op(agent_conn: psycopg.Connection) -> None:
    # Postgres does not error on GRANT without grant option; it warns and grants nothing.
    agent_conn.execute("SET default_transaction_read_only = off")
    agent_conn.execute("GRANT INSERT ON commodities TO PUBLIC")
    granted = agent_conn.execute(
        "SELECT has_table_privilege('public', 'commodities', 'INSERT'),"
        " has_table_privilege(current_user, 'commodities', 'INSERT')"
    ).fetchone()
    assert granted == (False, False)

"""Integration tests: schema, seeding and the read-only sql_agent role.

These prove the database itself refuses writes from the agent account, independently
of any application-level SQL validation.
"""

from __future__ import annotations

import json
from pathlib import Path

import psycopg
import pytest
from psycopg import errors

from scripts import clean_data, seed_database

FIXTURE = Path(__file__).parent / "fixtures" / "owid_co2_subset.csv"
DATA_TABLES = ["countries", "country_indicators", "co2_emissions", "ghg_emissions"]


def test_seed_loads_every_cleaned_row(seeded_db: str, tmp_path: Path) -> None:
    clean_data.run(FIXTURE, output_dir=tmp_path)
    report = json.loads((tmp_path / clean_data.REPORT_NAME).read_text())
    with psycopg.connect(seeded_db) as conn:
        counts = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in DATA_TABLES}  # noqa: S608
    assert counts == {"countries": 9, **report["rows_written"]}


def test_seed_is_idempotent(seeded_db: str, tmp_path: Path) -> None:
    clean_data.run(FIXTURE, output_dir=tmp_path)
    assert set(seed_database.seed(seeded_db, tmp_path).values()) == {0}


def test_seed_rejects_unexpected_columns(seeded_db: str, tmp_path: Path) -> None:
    clean_data.run(FIXTURE, output_dir=tmp_path)
    path = tmp_path / "co2_emissions.csv"
    path.write_text(path.read_text().replace("co2_per_capita", "co2_per_person", 1))
    with pytest.raises(ValueError, match="expected columns"):
        seed_database.seed(seeded_db, tmp_path)


def test_agent_can_rank_countries_excluding_aggregates(agent_conn: psycopg.Connection) -> None:
    rows = agent_conn.execute(
        "SELECT c.name FROM co2_emissions e JOIN countries c ON c.id = e.country_id"
        " WHERE c.entity_type = 'country' AND e.year = 2024 ORDER BY e.co2 DESC LIMIT 2"
    ).fetchall()
    assert rows == [("China",), ("United States",)]


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
    "INSERT INTO countries (name, entity_type) VALUES ('Injected', 'country')",
    "UPDATE co2_emissions SET co2 = 0",
    "DELETE FROM co2_emissions",
    "TRUNCATE co2_emissions",
    "DROP TABLE co2_emissions",
    "ALTER TABLE co2_emissions ADD COLUMN x int",
    "CREATE TABLE evil (id int)",
    "CREATE TEMP TABLE evil (id int)",
    "CREATE INDEX evil_idx ON co2_emissions (co2)",
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


def test_agent_grant_is_a_no_op(agent_conn: psycopg.Connection) -> None:
    # Postgres does not error on GRANT without grant option; it warns and grants nothing.
    agent_conn.execute("SET default_transaction_read_only = off")
    agent_conn.execute("GRANT INSERT ON countries TO PUBLIC")
    granted = agent_conn.execute(
        "SELECT has_table_privilege('public', 'countries', 'INSERT'),"
        " has_table_privilege(current_user, 'countries', 'INSERT')"
    ).fetchone()
    assert granted == (False, False)


def test_statement_timeout_cancels_slow_queries(agent_conn: psycopg.Connection) -> None:
    with pytest.raises(errors.QueryCanceled):
        agent_conn.execute("SELECT pg_sleep(3)")

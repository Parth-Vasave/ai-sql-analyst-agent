"""Database fixtures for integration tests.

Integration tests need an EMPTY, disposable database owned by a role that can create
roles (TEST_ADMIN_DATABASE_URL) and the password to (re)set for sql_agent
(TEST_SQL_AGENT_PASSWORD). They are skipped when these are not set.

Note: sql_agent is a cluster-wide role, so running these tests resets its password
on that Postgres server. Use a local/dev server, never production.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from scripts import clean_data, seed_database

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_raw_datagovin.csv"


@pytest.fixture(scope="session")
def admin_url() -> str:
    url = os.environ.get("TEST_ADMIN_DATABASE_URL")
    if not url or not os.environ.get("TEST_SQL_AGENT_PASSWORD"):
        pytest.skip("TEST_ADMIN_DATABASE_URL / TEST_SQL_AGENT_PASSWORD not set")
    return url


@pytest.fixture(scope="session")
def agent_url(admin_url: str) -> str:
    params = conninfo_to_dict(admin_url)
    params.update(user="sql_agent", password=os.environ["TEST_SQL_AGENT_PASSWORD"])
    return make_conninfo(**params)


@pytest.fixture(scope="session")
def seeded_db(admin_url: str, tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    env = {
        **os.environ,
        "ADMIN_DATABASE_URL": admin_url,
        "SQL_AGENT_PASSWORD": os.environ["TEST_SQL_AGENT_PASSWORD"],
        "QUERY_TIMEOUT_SECONDS": "1",
    }
    subprocess.run([str(ROOT / "database" / "init" / "00_init.sh")], env=env, check=True, capture_output=True)

    out = tmp_path_factory.mktemp("processed")
    clean_data.run([FIXTURE], output_dir=out)
    seed_database.seed(admin_url, out / clean_data.OUTPUT_NAME, replace=True)
    yield admin_url


@pytest.fixture
def agent_conn(seeded_db: str, agent_url: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(agent_url, autocommit=True) as conn:
        yield conn

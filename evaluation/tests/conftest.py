"""Database fixture for the replay tests: the pipeline's OWID fixture subset, seeded into the
disposable test database (TEST_ADMIN_DATABASE_URL / TEST_SQL_AGENT_PASSWORD, as for the other
integration suites). Skipped when they are not set; CI fails on skipped tests.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from app.database.connections import ConnectionConfig, ConnectionRegistry, DatabaseConnection
from evaluation import ROOT
from scripts import clean_data, seed_database

FIXTURE = ROOT / "scripts" / "tests" / "fixtures" / "owid_co2_subset.csv"


@pytest.fixture(scope="session")
def agent_password() -> str:
    password = os.environ.get("TEST_SQL_AGENT_PASSWORD")
    if not os.environ.get("TEST_ADMIN_DATABASE_URL") or not password:
        pytest.skip("TEST_ADMIN_DATABASE_URL / TEST_SQL_AGENT_PASSWORD not set")
    return password


@pytest.fixture(scope="session")
def owid(agent_password: str, tmp_path_factory: pytest.TempPathFactory) -> Iterator[DatabaseConnection]:
    """The read-only sql_agent connection to the seeded fixture data."""
    admin = os.environ["TEST_ADMIN_DATABASE_URL"]
    env = {
        **os.environ,
        "ADMIN_DATABASE_URL": admin,
        "SQL_AGENT_PASSWORD": agent_password,
        "QUERY_TIMEOUT_SECONDS": "2",
    }
    subprocess.run([str(ROOT / "database" / "init" / "00_init.sh")], env=env, check=True, capture_output=True)
    processed: Path = tmp_path_factory.mktemp("processed")
    clean_data.run(FIXTURE, output_dir=processed)
    seed_database.seed(admin, processed, replace=True)

    agent_url = make_url(admin).set(username="sql_agent", password=agent_password)
    config = ConnectionConfig(
        id="owid", name="OWID fixture", url=SecretStr(agent_url.render_as_string(hide_password=False))
    )
    connection = ConnectionRegistry(timeout_seconds=2).add(config)
    assert connection.status.value == "ready", connection.status
    yield connection
    connection.dispose()

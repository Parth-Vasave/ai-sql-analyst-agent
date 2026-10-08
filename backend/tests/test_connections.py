from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from app.database.adapters import UnsupportedDatabaseError
from app.database.connections import ConnectionConfig, ConnectionRegistry, ConnectionStatus, build_registry


def _registry() -> ConnectionRegistry:
    return ConnectionRegistry(timeout_seconds=1)


def test_postgres_scheme_and_driver_are_normalized() -> None:
    connection = _registry().add(
        ConnectionConfig(id="a", name="a", url=SecretStr("postgres://u:p@localhost:1/db")), verify=False
    )
    assert connection.engine.url.drivername == "postgresql+psycopg"


@pytest.mark.parametrize("url", ["mssql://u:p@localhost/db", "sqlite:///x.db", "mongodb://localhost/db"])
def test_unsupported_engines_are_rejected(url: str) -> None:
    with pytest.raises((UnsupportedDatabaseError, ValueError)):
        _registry().add(ConnectionConfig(id="a", name="a", url=SecretStr(url)), verify=False)


def test_unreachable_database_is_unavailable_without_leaking_details() -> None:
    connection = _registry().add(
        ConnectionConfig(id="a", name="a", url=SecretStr("postgresql://user:hunter2@127.0.0.1:1/db"))
    )
    assert connection.status is ConnectionStatus.UNAVAILABLE
    assert connection.issues == ["Could not connect to the database."]


def test_duplicate_ids_are_rejected() -> None:
    registry = _registry()
    config = ConnectionConfig(id="a", name="a", url=SecretStr("postgresql://u:p@localhost:1/db"))
    registry.add(config, verify=False)
    with pytest.raises(ValueError, match="already exists"):
        registry.add(config, verify=False)


def test_config_file_reads_urls_from_environment(tmp_path: Path) -> None:
    path = tmp_path / "databases.toml"
    path.write_text(
        '[[databases]]\nid = "demo"\nname = "Demo"\nurl_env = "DEMO_URL"\n'
        'sampling = "off"\nschemas = ["public"]\n'
    )
    registry = build_registry(
        timeout_seconds=1,
        profile_budget_seconds=5,
        config_path=path,
        default_url=None,
        environ={"DEMO_URL": "postgresql://u:p@localhost:1/db"},
    )
    (connection,) = registry.all()
    assert (connection.config.id, connection.config.sampling.value, connection.config.schemas) == (
        "demo",
        "off",
        ["public"],
    )


def test_config_file_must_not_contain_urls(tmp_path: Path) -> None:
    path = tmp_path / "databases.toml"
    path.write_text('[[databases]]\nid = "demo"\nname = "Demo"\nurl = "postgresql://u:p@h/db"\n')
    with pytest.raises(ValueError, match="environment variables"):
        _registry().load_config_file(path, environ={})


def test_config_file_requires_the_env_var_to_be_set(tmp_path: Path) -> None:
    path = tmp_path / "databases.toml"
    path.write_text('[[databases]]\nid = "demo"\nname = "Demo"\nurl_env = "MISSING"\n')
    with pytest.raises(ValueError, match="url_env"):
        _registry().load_config_file(path, environ={})


def test_default_url_becomes_default_database() -> None:
    registry = build_registry(
        timeout_seconds=1,
        profile_budget_seconds=5,
        config_path=None,
        default_url=SecretStr("postgresql://u:p@localhost:1/db"),
        environ={},
    )
    assert [c.config.id for c in registry.all()] == ["default"]

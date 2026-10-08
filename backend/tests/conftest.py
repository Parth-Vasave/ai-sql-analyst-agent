"""Shared fixtures.

Unit tests need no database. Integration tests (marked by using `pg`) need an EMPTY,
disposable PostgreSQL database: TEST_ADMIN_DATABASE_URL (postgresql:// URL of an owner able to
create roles) and
TEST_SQL_AGENT_PASSWORD. They reset the cluster-wide sql_agent role; never use production.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
import pymysql
import pytest
from sqlalchemy.engine import make_url

# Tests must never need real credentials; settings only require a syntactically valid URL.
os.environ.setdefault("DATABASE_URL", "postgresql://sql_agent:unused@localhost:5432/unused")

ROOT = Path(__file__).resolve().parents[2]

# A second, differently shaped schema: no FK on orders.customer_id, sensitive columns,
# a categorical column, free text with many values, and a table sql_agent cannot read.
SHOP_SCHEMA = """
DROP SCHEMA IF EXISTS shop CASCADE;
CREATE SCHEMA shop;
CREATE TABLE shop.customers (
    id integer PRIMARY KEY, full_name text NOT NULL, email text, password_hash text,
    segment text NOT NULL
);
COMMENT ON TABLE shop.customers IS 'Registered customers.';
CREATE TABLE shop.orders (
    id integer PRIMARY KEY, customer_id integer NOT NULL, status text NOT NULL,
    total numeric(10, 2) NOT NULL, ordered_at date NOT NULL, note text
);
CREATE TABLE shop.order_items (
    id integer PRIMARY KEY, order_id integer NOT NULL REFERENCES shop.orders (id),
    product text NOT NULL, quantity integer NOT NULL, weight_kg real
);
CREATE TABLE shop.secret_audit (id integer PRIMARY KEY, note text);
INSERT INTO shop.customers
SELECT i, 'Customer ' || lpad(i::text, 2, '0'), 'c' || i || '@example.test', 'hash' || i,
       (ARRAY['retail', 'wholesale', 'online'])[1 + i % 3]
FROM generate_series(1, 25) AS i;
INSERT INTO shop.orders
SELECT i, 1 + i % 25, (ARRAY['placed', 'shipped', 'returned'])[1 + i % 3], 10 * i,
       DATE '2024-01-01' + i, CASE WHEN i % 2 = 0 THEN 'gift wrap' ELSE 'note ' || i END
FROM generate_series(1, 60) AS i;
INSERT INTO shop.order_items
SELECT i, 1 + i % 60, 'Product ' || (i % 5), 1 + i % 4, 0.5 * (1 + i % 4) FROM generate_series(1, 120) AS i;
GRANT USAGE ON SCHEMA shop TO sql_agent;
GRANT SELECT ON shop.customers, shop.orders, shop.order_items TO sql_agent;
"""


@dataclass(frozen=True)
class PgUrls:
    admin: str
    agent: str


@pytest.fixture(scope="session")
def pg() -> Iterator[PgUrls]:
    admin = os.environ.get("TEST_ADMIN_DATABASE_URL")
    password = os.environ.get("TEST_SQL_AGENT_PASSWORD")
    if not admin or not password:
        pytest.skip("TEST_ADMIN_DATABASE_URL / TEST_SQL_AGENT_PASSWORD not set")
    env = {
        **os.environ,
        "ADMIN_DATABASE_URL": admin,
        "SQL_AGENT_PASSWORD": password,
        "QUERY_TIMEOUT_SECONDS": "2",
    }
    subprocess.run([str(ROOT / "database" / "init" / "00_init.sh")], env=env, check=True, capture_output=True)
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(SHOP_SCHEMA)
    agent = make_url(admin).set(username="sql_agent", password=password)
    yield PgUrls(admin=admin, agent=agent.render_as_string(hide_password=False))
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS shop CASCADE")


# --- MySQL / MariaDB ---------------------------------------------------------------------

MYSQL_DATABASE = "shop_test"

MYSQL_DDL = (
    "DROP DATABASE IF EXISTS shop_test",
    "CREATE DATABASE shop_test CHARACTER SET utf8mb4",
    "CREATE TABLE shop_test.customers (id INT PRIMARY KEY, full_name VARCHAR(100) NOT NULL,"
    " email VARCHAR(100), password_hash VARCHAR(64), segment VARCHAR(20) NOT NULL)",
    "CREATE TABLE shop_test.orders (id INT PRIMARY KEY, customer_id INT NOT NULL,"
    " status VARCHAR(20) NOT NULL, total DECIMAL(10, 2) NOT NULL, ordered_at DATE NOT NULL)",
    "CREATE TABLE shop_test.order_items (id INT PRIMARY KEY, order_id INT NOT NULL,"
    " product VARCHAR(50) NOT NULL, quantity INT NOT NULL,"
    " FOREIGN KEY (order_id) REFERENCES shop_test.orders (id))",
    "CREATE TABLE shop_test.secret_audit (id INT PRIMARY KEY, note VARCHAR(100))",
)


def _mysql_users(password: str) -> list[str]:
    literal = password.replace("'", "''")
    return [
        f"CREATE USER IF NOT EXISTS 'mysql_agent'@'%' IDENTIFIED BY '{literal}'",
        "GRANT SELECT ON shop_test.customers TO 'mysql_agent'@'%'",
        "GRANT SELECT ON shop_test.orders TO 'mysql_agent'@'%'",
        "GRANT SELECT ON shop_test.order_items TO 'mysql_agent'@'%'",
        f"CREATE USER IF NOT EXISTS 'mysql_writer'@'%' IDENTIFIED BY '{literal}'",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON shop_test.* TO 'mysql_writer'@'%'",
        f"CREATE USER IF NOT EXISTS 'mysql_super'@'%' IDENTIFIED BY '{literal}'",
        # Read access so it can connect to the test database, plus dangerous admin/file grants.
        "GRANT SELECT ON shop_test.* TO 'mysql_super'@'%'",
        "GRANT FILE, SUPER ON *.* TO 'mysql_super'@'%'",
    ]


def _mysql_seed(cursor: Any) -> None:
    segments = ["retail", "wholesale", "online"]
    for i in range(1, 26):
        cursor.execute(
            "INSERT INTO shop_test.customers VALUES (%s, %s, %s, %s, %s)",
            (i, f"Customer {i:02d}", f"c{i}@example.test", f"hash{i}", segments[i % 3]),
        )
    statuses = ["placed", "shipped", "returned"]
    for i in range(1, 61):
        cursor.execute(
            "INSERT INTO shop_test.orders VALUES (%s, %s, %s, %s, %s)",
            (i, 1 + i % 25, statuses[i % 3], 10 * i, f"2024-01-{1 + i % 28:02d}"),
        )
    for i in range(1, 121):
        cursor.execute(
            "INSERT INTO shop_test.order_items VALUES (%s, %s, %s, %s)",
            (i, 1 + i % 60, f"Product {i % 5}", 1 + i % 4),
        )


@dataclass(frozen=True)
class MysqlUrls:
    agent: str  # SELECT only on shop_test
    writer: str  # can modify shop_test data
    superuser: str  # FILE + SUPER


@pytest.fixture(scope="session")
def mysql() -> Iterator[MysqlUrls]:
    admin = os.environ.get("TEST_MYSQL_ADMIN_URL")
    password = os.environ.get("TEST_MYSQL_AGENT_PASSWORD")
    if not admin or not password:
        pytest.skip("TEST_MYSQL_ADMIN_URL / TEST_MYSQL_AGENT_PASSWORD not set")
    url = make_url(admin)
    host, port = url.host, url.port or 3306

    def connect() -> Any:
        return pymysql.connect(
            host=host, port=port, user=url.username, password=url.password or "", autocommit=True
        )

    with connect() as conn, conn.cursor() as cursor:
        for statement in [*MYSQL_DDL, *_mysql_users(password)]:
            cursor.execute(statement)
        _mysql_seed(cursor)

    base = f"mysql+pymysql://{{user}}:{password}@{host}:{port}/{MYSQL_DATABASE}"
    yield MysqlUrls(
        agent=base.format(user="mysql_agent"),
        writer=base.format(user="mysql_writer"),
        superuser=base.format(user="mysql_super"),
    )
    with connect() as conn, conn.cursor() as cursor:
        cursor.execute("DROP DATABASE IF EXISTS shop_test")
        for user in ("mysql_agent", "mysql_writer", "mysql_super"):
            cursor.execute(f"DROP USER IF EXISTS '{user}'@'%'")

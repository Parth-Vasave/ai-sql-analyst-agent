"""Load the cleaned CSV into PostgreSQL.

Runs as the database OWNER (ADMIN_DATABASE_URL), never as the read-only sql_agent.
The whole load is one transaction: it either fully succeeds or leaves the database as it was.
Re-running is safe; rows that already exist are skipped.

Usage:
    ADMIN_DATABASE_URL=postgresql://... python -m scripts.seed_database
    ADMIN_DATABASE_URL=postgresql://... python -m scripts.seed_database --replace path/to/clean.csv
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg

from scripts.clean_data import OUTPUT_COLUMNS, OUTPUT_NAME, PROCESSED_DIR

STAGING_DDL = """
CREATE TEMP TABLE staging_prices (
    state text, district text, market text, commodity text, variety text, grade text,
    arrival_date date, min_price numeric(12, 2), max_price numeric(12, 2), modal_price numeric(12, 2)
) ON COMMIT DROP
"""

INSERT_COMMODITIES = """
INSERT INTO commodities (name)
SELECT DISTINCT commodity FROM staging_prices
ON CONFLICT (name) DO NOTHING
"""

INSERT_MARKETS = """
INSERT INTO markets (name, district, state)
SELECT DISTINCT market, district, state FROM staging_prices
ON CONFLICT ON CONSTRAINT markets_state_district_name_key DO NOTHING
"""

INSERT_PRICES = """
INSERT INTO daily_prices
    (market_id, commodity_id, variety, grade, arrival_date, min_price, max_price, modal_price)
SELECT m.id, c.id, s.variety, s.grade, s.arrival_date, s.min_price, s.max_price, s.modal_price
FROM staging_prices s
JOIN markets m ON m.state = s.state AND m.district = s.district AND m.name = s.market
JOIN commodities c ON c.name = s.commodity
ON CONFLICT ON CONSTRAINT daily_prices_record_key DO NOTHING
"""


@dataclass
class SeedResult:
    staged: int
    commodities_added: int
    markets_added: int
    prices_added: int


def seed(conninfo: str, csv_path: Path, replace: bool = False) -> SeedResult:
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} not found. Run scripts/clean_data.py first.")

    with psycopg.connect(conninfo) as conn, conn.cursor() as cur:
        if replace:
            cur.execute("TRUNCATE daily_prices, markets, commodities RESTART IDENTITY")
        cur.execute(STAGING_DDL)
        columns = ", ".join(OUTPUT_COLUMNS)
        copy_sql = f"COPY staging_prices ({columns}) FROM STDIN WITH (FORMAT csv, HEADER true)"
        with cur.copy(copy_sql) as copy, csv_path.open("rb") as fh:
            while chunk := fh.read(1 << 20):
                copy.write(chunk)
        cur.execute("SELECT count(*) FROM staging_prices")
        staged = cur.fetchone()[0]  # type: ignore[index]

        cur.execute(INSERT_COMMODITIES)
        commodities_added = cur.rowcount
        cur.execute(INSERT_MARKETS)
        markets_added = cur.rowcount
        cur.execute(INSERT_PRICES)
        prices_added = cur.rowcount
        cur.execute("ANALYZE commodities, markets, daily_prices")  # fresh planner statistics
        conn.commit()

    return SeedResult(staged, commodities_added, markets_added, prices_added)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("csv", nargs="?", type=Path, default=PROCESSED_DIR / OUTPUT_NAME)
    parser.add_argument("--replace", action="store_true", help="Truncate all data tables before loading")
    args = parser.parse_args(argv)

    conninfo = os.environ.get("ADMIN_DATABASE_URL")
    if not conninfo:
        print("ADMIN_DATABASE_URL is not set (owner connection, not the sql_agent one).", file=sys.stderr)
        return 2

    result = seed(conninfo, args.csv, args.replace)
    print(
        f"Staged {result.staged:,} rows; added {result.commodities_added:,} commodities, "
        f"{result.markets_added:,} markets, {result.prices_added:,} price records."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Load the cleaned CSVs (scripts/clean_data.py output) into PostgreSQL.

Runs as the database OWNER (ADMIN_DATABASE_URL), never as the read-only sql_agent.
The whole load is one transaction: it either fully succeeds or leaves the database as it was.
Re-running is safe; rows that already exist are skipped (use --replace to reload).

Usage:
    ADMIN_DATABASE_URL=postgresql://... python -m scripts.seed_database
    ADMIN_DATABASE_URL=postgresql://... python -m scripts.seed_database --replace --input-dir data/processed
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

import psycopg
from psycopg import sql

from scripts.clean_data import COUNTRIES_FILE, PROCESSED_DIR, TABLE_COLUMNS

COUNTRY_COLUMNS = ["name", "iso_code", "entity_type"]


def _check_header(path: Path, expected: list[str]) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run `python -m scripts.clean_data` first.")
    with path.open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh), [])
    if header != expected:
        raise ValueError(f"{path.name}: expected columns {expected}, found {header}")


def _copy(cur: psycopg.Cursor, table: str, columns: list[str], path: Path) -> None:
    statement = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true)").format(
        sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns))
    )
    with cur.copy(statement) as copy, path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            copy.write(chunk)


def _load_countries(cur: psycopg.Cursor, path: Path) -> int:
    cur.execute(
        "CREATE TEMP TABLE staging_countries (name text, iso_code text, entity_type text) ON COMMIT DROP"
    )
    _copy(cur, "staging_countries", COUNTRY_COLUMNS, path)
    cur.execute(
        "INSERT INTO countries (name, iso_code, entity_type)"
        " SELECT name, NULLIF(iso_code, ''), entity_type FROM staging_countries"
        " ON CONFLICT (name) DO NOTHING"
    )
    return cur.rowcount


def _load_table(cur: psycopg.Cursor, table: str, metrics: list[str], path: Path) -> int:
    staging = f"staging_{table}"
    # Staging mirrors the target but keys rows by entity name instead of country_id.
    cur.execute(
        sql.SQL(
            "CREATE TEMP TABLE {staging} ON COMMIT DROP AS"
            " SELECT NULL::text AS country, year, {metrics} FROM {table} WITH NO DATA"
        ).format(
            staging=sql.Identifier(staging),
            table=sql.Identifier(table),
            metrics=sql.SQL(", ").join(map(sql.Identifier, metrics)),
        )
    )
    _copy(cur, staging, ["country", "year", *metrics], path)
    cur.execute(
        sql.SQL(
            "INSERT INTO {table} (country_id, year, {metrics})"
            " SELECT c.id, s.year, {s_metrics} FROM {staging} s JOIN countries c ON c.name = s.country"
            " ON CONFLICT (country_id, year) DO NOTHING"
        ).format(
            table=sql.Identifier(table),
            staging=sql.Identifier(staging),
            metrics=sql.SQL(", ").join(map(sql.Identifier, metrics)),
            s_metrics=sql.SQL(", ").join(sql.Identifier("s", m) for m in metrics),
        )
    )
    inserted = cur.rowcount
    cur.execute(
        sql.SQL(
            "SELECT count(*) FROM {} s WHERE NOT EXISTS (SELECT 1 FROM countries c WHERE c.name = s.country)"
        ).format(sql.Identifier(staging))
    )
    orphans = cur.fetchone()[0]  # type: ignore[index]
    if orphans:
        raise ValueError(f"{table}: {orphans} rows reference entities missing from {COUNTRIES_FILE}")
    return inserted


def seed(conninfo: str, input_dir: Path = PROCESSED_DIR, replace: bool = False) -> dict[str, int]:
    _check_header(input_dir / COUNTRIES_FILE, COUNTRY_COLUMNS)
    for table, metrics in TABLE_COLUMNS.items():
        _check_header(input_dir / f"{table}.csv", ["country", "year", *metrics])

    added: dict[str, int] = {}
    with psycopg.connect(conninfo) as conn, conn.cursor() as cur:
        if replace:
            cur.execute(
                "TRUNCATE ghg_emissions, co2_emissions, country_indicators, countries RESTART IDENTITY"
            )
        added["countries"] = _load_countries(cur, input_dir / COUNTRIES_FILE)
        for table, metrics in TABLE_COLUMNS.items():
            added[table] = _load_table(cur, table, metrics, input_dir / f"{table}.csv")
        cur.execute("ANALYZE countries, country_indicators, co2_emissions, ghg_emissions")
        conn.commit()
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--input-dir", type=Path, default=PROCESSED_DIR)
    parser.add_argument("--replace", action="store_true", help="Truncate all data tables before loading")
    args = parser.parse_args(argv)

    conninfo = os.environ.get("ADMIN_DATABASE_URL")
    if not conninfo:
        print("ADMIN_DATABASE_URL is not set (owner connection, not the sql_agent one).", file=sys.stderr)
        return 2
    try:
        added = seed(conninfo, args.input_dir, args.replace)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print("Rows added: " + ", ".join(f"{table} {count:,}" for table, count in added.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

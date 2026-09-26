"""Clean the OWID CO2 dataset and split it into the tables of database/schema.sql.

Rules, in the order applied (every change is counted in cleaning_report.json):

1.  All columns the schema needs must be present, or the run aborts.
2.  Entity names are trimmed; ISO codes are upper-cased and must be 3 letters.
3.  Entities suffixed "(GCP)" are excluded. They are the Global Carbon Project's
    alternative region definitions and duplicate OWID's own regions (e.g. "Asia" vs
    "Asia (GCP)"), which would make questions about regions ambiguous.
4.  Every remaining entity is classified as country / region / income_group / other.
    Entities with an ISO code are countries (plus Kosovo, which has none in OWID).
    Aggregates are matched against explicit lists below; an unknown entity without an
    ISO code aborts the run, so new OWID aggregates are never silently mislabeled.
5.  A duplicate (entity, year) aborts the run: the source guarantees uniqueness.
6.  Negative values in columns that cannot be negative (see NON_NEGATIVE) are set to
    NULL and counted. Columns that legitimately go negative (land-use change, trade,
    growth, total GHG including land use) are left as published.
7.  Each table receives only the (entity, year) rows where at least one of its
    metrics is present, so tables contain no all-NULL rows.

Usage:
    python -m scripts.clean_data                           # data/raw/owid-co2-data.csv
    python -m scripts.clean_data path/to/owid-co2-data.csv --output-dir data/processed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = ROOT / "data" / "raw" / "owid-co2-data.csv"
PROCESSED_DIR = ROOT / "data" / "processed"
REPORT_NAME = "cleaning_report.json"
COUNTRIES_FILE = "countries.csv"

TABLE_COLUMNS: dict[str, list[str]] = {
    "country_indicators": [
        "population",
        "gdp",
        "primary_energy_consumption",
        "energy_per_capita",
        "energy_per_gdp",
    ],
    "co2_emissions": [
        "co2",
        "co2_per_capita",
        "co2_per_gdp",
        "co2_per_unit_energy",
        "co2_growth_abs",
        "co2_growth_prct",
        "coal_co2",
        "oil_co2",
        "gas_co2",
        "cement_co2",
        "flaring_co2",
        "other_industry_co2",
        "coal_co2_per_capita",
        "oil_co2_per_capita",
        "gas_co2_per_capita",
        "land_use_change_co2",
        "co2_including_luc",
        "co2_including_luc_per_capita",
        "consumption_co2",
        "consumption_co2_per_capita",
        "trade_co2",
        "trade_co2_share",
        "cumulative_co2",
        "share_global_co2",
        "share_global_cumulative_co2",
    ],
    "ghg_emissions": [
        "methane",
        "methane_per_capita",
        "nitrous_oxide",
        "nitrous_oxide_per_capita",
        "total_ghg",
        "total_ghg_excluding_lucf",
        "ghg_per_capita",
        "ghg_excluding_lucf_per_capita",
        "temperature_change_from_ghg",
        "temperature_change_from_co2",
        "temperature_change_from_ch4",
        "temperature_change_from_n2o",
        "share_of_temperature_change_from_ghg",
    ],
}

# Must mirror the CHECK (... >= 0) constraints in database/schema.sql.
NON_NEGATIVE = {
    "population",
    "gdp",
    "primary_energy_consumption",
    "energy_per_capita",
    "energy_per_gdp",
    "co2",
    "co2_per_capita",
    "co2_per_gdp",
    "co2_per_unit_energy",
    "coal_co2",
    "oil_co2",
    "gas_co2",
    "cement_co2",
    "flaring_co2",
    "other_industry_co2",
    "coal_co2_per_capita",
    "oil_co2_per_capita",
    "gas_co2_per_capita",
    "consumption_co2",
    "consumption_co2_per_capita",
    "cumulative_co2",
    "methane",
    "methane_per_capita",
    "nitrous_oxide",
    "nitrous_oxide_per_capita",
}

REGIONS = {
    "World",
    "Africa",
    "Asia",
    "Asia (excl. China and India)",
    "Europe",
    "Europe (excl. EU-27)",
    "Europe (excl. EU-28)",
    "European Union (27)",
    "European Union (28)",
    "North America",
    "North America (excl. USA)",
    "Oceania",
    "South America",
    "OECD (Jones et al.)",
    "Least developed countries (Jones et al.)",
}
INCOME_GROUPS = {
    "High-income countries",
    "Upper-middle-income countries",
    "Lower-middle-income countries",
    "Low-income countries",
}
OTHER_ENTITIES = {"International aviation", "International shipping", "Kuwaiti Oil Fires", "Ryukyu Islands"}
COUNTRIES_WITHOUT_ISO = {"Kosovo"}
EXCLUDED_SUFFIX = " (GCP)"

ENTITY_COLUMNS = ["country", "year", "iso_code"]
REQUIRED_COLUMNS = ENTITY_COLUMNS + [c for cols in TABLE_COLUMNS.values() for c in cols]


class CleaningError(ValueError):
    """Raised when the input cannot be cleaned safely."""


@dataclass
class CleaningReport:
    input_file: dict[str, Any] = field(default_factory=dict)
    rows_read: int = 0
    excluded_entities: list[str] = field(default_factory=list)
    rows_excluded: int = 0
    entities_by_type: dict[str, int] = field(default_factory=dict)
    negative_values_nulled: dict[str, int] = field(default_factory=dict)
    rows_written: dict[str, int] = field(default_factory=dict)
    unused_source_columns: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"), **self.__dict__}


def classify_entity(name: str, iso_code: object) -> str:
    if pd.notna(iso_code) or name in COUNTRIES_WITHOUT_ISO:
        return "country"
    if name in REGIONS:
        return "region"
    if name in INCOME_GROUPS:
        return "income_group"
    if name in OTHER_ENTITIES:
        return "other"
    raise CleaningError(
        f"Unclassified entity without ISO code: {name!r}. Add it to the entity lists in clean_data.py."
    )


def clean(df: pd.DataFrame, report: CleaningReport) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise CleaningError(f"Missing required column(s): {missing}")
    report.rows_read = len(df)
    report.unused_source_columns = sorted(set(df.columns) - set(REQUIRED_COLUMNS))
    df = df[REQUIRED_COLUMNS].copy()

    df["country"] = df["country"].astype("string").str.strip()
    df["iso_code"] = df["iso_code"].astype("string").str.strip().str.upper().replace("", pd.NA)
    bad_iso = df["iso_code"].notna() & ~df["iso_code"].str.fullmatch(r"[A-Z]{3}", na=False)
    if bad_iso.any():
        raise CleaningError(f"Invalid ISO codes: {sorted(df.loc[bad_iso, 'iso_code'].unique())}")

    excluded = df["country"].str.endswith(EXCLUDED_SUFFIX, na=False)
    report.excluded_entities = sorted(df.loc[excluded, "country"].unique())
    report.rows_excluded = int(excluded.sum())
    df = df.loc[~excluded]

    if df["country"].isna().any() or df["year"].isna().any():
        raise CleaningError("Rows with a missing entity name or year")
    df["year"] = df["year"].astype(int)
    duplicates = df.duplicated(["country", "year"], keep=False)
    if duplicates.any():
        sample = df.loc[duplicates, ["country", "year"]].head(5).to_dict("records")
        raise CleaningError(f"Duplicate (country, year) rows, e.g. {sample}")

    entities = df.groupby("country", sort=True)["iso_code"].first()  # first non-null code
    countries = pd.DataFrame({"name": entities.index, "iso_code": entities.values})
    countries["entity_type"] = [
        classify_entity(n, i) for n, i in zip(countries["name"], countries["iso_code"], strict=True)
    ]
    report.entities_by_type = countries["entity_type"].value_counts().sort_index().to_dict()

    for column in sorted(NON_NEGATIVE):
        negative = df[column] < 0
        if negative.any():
            report.negative_values_nulled[column] = int(negative.sum())
            df.loc[negative, column] = pd.NA

    df["population"] = df["population"].round().astype("Int64")

    tables: dict[str, pd.DataFrame] = {}
    for table, columns in TABLE_COLUMNS.items():
        part = df.loc[df[columns].notna().any(axis=1), ["country", "year", *columns]]
        tables[table] = part.sort_values(["country", "year"]).reset_index(drop=True)
        report.rows_written[table] = len(part)

    report.summary = {
        "year_min": int(df["year"].min()),
        "year_max": int(df["year"].max()),
        "entities": len(countries),
        "latest_year_with_data": {
            column: int(df.loc[df[column].notna(), "year"].max())
            for column in ("population", "gdp", "primary_energy_consumption", "co2", "total_ghg")
        },
    }
    return countries, tables


def run(input_path: Path = RAW_FILE, output_dir: Path = PROCESSED_DIR) -> CleaningReport:
    if not input_path.exists():
        raise CleaningError(f"{input_path} not found. Run `python -m scripts.ingest_data` first.")
    report = CleaningReport(
        input_file={"file": input_path.name, "sha256": hashlib.sha256(input_path.read_bytes()).hexdigest()}
    )
    manifest = input_path.parent / "owid-co2.manifest.json"
    if manifest.exists():
        report.input_file["manifest"] = json.loads(manifest.read_text())

    df = pd.read_csv(input_path, keep_default_na=True, na_values=[""], dtype={"iso_code": "string"})
    countries, tables = clean(df, report)

    output_dir.mkdir(parents=True, exist_ok=True)
    countries.to_csv(output_dir / COUNTRIES_FILE, index=False)
    for table, frame in tables.items():
        frame.to_csv(output_dir / f"{table}.csv", index=False)
    (output_dir / REPORT_NAME).write_text(json.dumps(report.to_dict(), indent=2, default=str) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("input", nargs="?", type=Path, default=RAW_FILE)
    parser.add_argument("--output-dir", type=Path, default=PROCESSED_DIR)
    args = parser.parse_args(argv)

    try:
        report = run(args.input, args.output_dir)
    except CleaningError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Read {report.rows_read:,} rows; excluded {report.rows_excluded:,} rows of (GCP) entities.")
    print(f"Entities: {report.entities_by_type}")
    for table, count in report.rows_written.items():
        print(f"  {table}: {count:,} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Clean raw mandi price CSVs into one normalized, validated CSV.

Accepts the column layouts published by data.gov.in (API and portal downloads) and
AGMARKNET exports, e.g. ``Min_x0020_Price``, ``Min Price (Rs./Quintal)`` or ``min_price``.

Every rule that drops rows is counted in ``cleaning_report.json`` so the preprocessing
is auditable. Rules, in the order applied:

1.  Column names are normalized and mapped to canonical names; missing required
    columns abort with an error.
2.  Text is trimmed and inner whitespace collapsed. Casing is left as published.
3.  Missing variety / grade become 'Unknown' (they are descriptive, not identifying).
4.  Rows missing state, district, market or commodity are dropped.
5.  Dates are parsed as day-first (dd/mm/yyyy, the data.gov.in format) or ISO
    (yyyy-mm-dd). Unparseable dates are dropped. Month-first is never guessed.
6.  Prices must be numeric and > 0; min <= max; min <= modal <= max. Others are dropped.
7.  Optional --start-date / --end-date / --commodity filters (not counted as errors).
8.  Exact duplicate rows are collapsed to one.
9.  Rows sharing the natural key (state, district, market, commodity, variety, grade,
    date) but with different prices are all dropped: there is no way to tell which is right.

Usage:
    python -m scripts.clean_data data/raw/*.csv
    python -m scripts.clean_data data/raw/*.csv --start-date 2022-01-01 --commodity Wheat
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
OUTPUT_NAME = "daily_prices_clean.csv"
REPORT_NAME = "cleaning_report.json"

TEXT_COLUMNS = ["state", "district", "market", "commodity", "variety", "grade"]
PRICE_COLUMNS = ["min_price", "max_price", "modal_price"]
OUTPUT_COLUMNS = [*TEXT_COLUMNS, "arrival_date", *PRICE_COLUMNS]
REQUIRED_COLUMNS = ["state", "district", "market", "commodity", "arrival_date", *PRICE_COLUMNS]
KEY_COLUMNS = [*TEXT_COLUMNS, "arrival_date"]
UNKNOWN = "Unknown"

# Normalized source header -> canonical column.
COLUMN_ALIASES: dict[str, str] = {
    "state": "state",
    "state_name": "state",
    "district": "district",
    "district_name": "district",
    "market": "market",
    "market_name": "market",
    "commodity": "commodity",
    "commodity_name": "commodity",
    "variety": "variety",
    "grade": "grade",
    "arrival_date": "arrival_date",
    "price_date": "arrival_date",
    "reported_date": "arrival_date",
    "min_price": "min_price",
    "min_price_rs_quintal": "min_price",
    "max_price": "max_price",
    "max_price_rs_quintal": "max_price",
    "modal_price": "modal_price",
    "modal_price_rs_quintal": "modal_price",
}

DATE_FORMATS = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y", "%d %b %Y"]


class CleaningError(ValueError):
    """Raised when an input file cannot be cleaned at all (e.g. missing columns)."""


@dataclass
class CleaningReport:
    input_files: list[dict[str, Any]] = field(default_factory=list)
    rows_read: int = 0
    dropped: dict[str, int] = field(default_factory=dict)
    filtered: dict[str, int] = field(default_factory=dict)
    filled_unknown: dict[str, int] = field(default_factory=dict)
    rows_written: int = 0
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "input_files": self.input_files,
            "rows_read": self.rows_read,
            "rows_dropped": self.dropped,
            "rows_filtered": self.filtered,
            "values_filled_with_unknown": self.filled_unknown,
            "rows_written": self.rows_written,
            "summary": self.summary,
        }


def normalize_header(name: str) -> str:
    name = name.replace("_x0020_", "_").strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_")


def canonicalize_columns(df: pd.DataFrame, source: str) -> pd.DataFrame:
    mapping: dict[str, str] = {}
    for column in df.columns:
        canonical = COLUMN_ALIASES.get(normalize_header(str(column)))
        if canonical and canonical not in mapping.values():
            mapping[column] = canonical
    df = df.rename(columns=mapping)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise CleaningError(
            f"{source}: missing required column(s) {missing}. Found: {list(map(str, df.columns))}"
        )
    for optional in ("variety", "grade"):
        if optional not in df.columns:
            df[optional] = pd.NA
    return df[OUTPUT_COLUMNS]


def parse_dates(values: pd.Series) -> pd.Series:
    text = values.astype("string").str.strip()
    parsed = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    for fmt in DATE_FORMATS:
        attempt = pd.to_datetime(text, format=fmt, errors="coerce")
        parsed = parsed.fillna(attempt)
    return parsed


def parse_prices(values: pd.Series) -> pd.Series:
    text = values.astype("string").str.replace(",", "", regex=False).str.strip()
    return pd.to_numeric(text, errors="coerce")


def _drop(df: pd.DataFrame, mask: pd.Series, reason: str, report: CleaningReport) -> pd.DataFrame:
    count = int(mask.sum())
    report.dropped[reason] = report.dropped.get(reason, 0) + count
    return df.loc[~mask]


def clean_frame(
    df: pd.DataFrame,
    report: CleaningReport,
    start_date: date | None = None,
    end_date: date | None = None,
    commodities: list[str] | None = None,
) -> pd.DataFrame:
    df = df.copy()
    for column in TEXT_COLUMNS:
        df[column] = df[column].astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
        df.loc[df[column] == "", column] = pd.NA

    for column in ("variety", "grade"):
        missing = df[column].isna()
        report.filled_unknown[column] = report.filled_unknown.get(column, 0) + int(missing.sum())
        df.loc[missing, column] = UNKNOWN

    df = _drop(
        df,
        df[["state", "district", "market", "commodity"]].isna().any(axis=1),
        "missing_location_or_commodity",
        report,
    )

    df["arrival_date"] = parse_dates(df["arrival_date"])
    df = _drop(df, df["arrival_date"].isna(), "invalid_date", report)

    for column in PRICE_COLUMNS:
        df[column] = parse_prices(df[column])
    df = _drop(df, df[PRICE_COLUMNS].isna().any(axis=1), "non_numeric_price", report)
    df = _drop(df, (df[PRICE_COLUMNS] <= 0).any(axis=1), "non_positive_price", report)
    df = _drop(df, df["min_price"] > df["max_price"], "min_price_above_max_price", report)
    df = _drop(
        df,
        (df["modal_price"] < df["min_price"]) | (df["modal_price"] > df["max_price"]),
        "modal_price_outside_min_max",
        report,
    )

    if start_date:
        mask = df["arrival_date"] < pd.Timestamp(start_date)
        report.filtered["before_start_date"] = int(mask.sum())
        df = df.loc[~mask]
    if end_date:
        mask = df["arrival_date"] > pd.Timestamp(end_date)
        report.filtered["after_end_date"] = int(mask.sum())
        df = df.loc[~mask]
    if commodities:
        wanted = {c.casefold() for c in commodities}
        mask = ~df["commodity"].str.casefold().isin(wanted)
        report.filtered["other_commodities"] = int(mask.sum())
        df = df.loc[~mask]

    df = _drop(df, df.duplicated(keep="first"), "exact_duplicate", report)
    df = _drop(df, df.duplicated(subset=KEY_COLUMNS, keep=False), "conflicting_duplicate", report)

    df = df.sort_values(KEY_COLUMNS).reset_index(drop=True)
    df["arrival_date"] = df["arrival_date"].dt.strftime("%Y-%m-%d")
    return df


def summarize(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {}
    return {
        "date_min": df["arrival_date"].min(),
        "date_max": df["arrival_date"].max(),
        "states": int(df["state"].nunique()),
        "districts": int(df[["state", "district"]].drop_duplicates().shape[0]),
        "markets": int(df[["state", "district", "market"]].drop_duplicates().shape[0]),
        "commodities": int(df["commodity"].nunique()),
        "top_commodities_by_rows": df["commodity"].value_counts().head(10).to_dict(),
    }


def describe_input(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest = path.with_suffix(".manifest.json")
    if manifest.exists():
        info["manifest"] = json.loads(manifest.read_text())
    return info


def run(
    inputs: list[Path],
    output_dir: Path = PROCESSED_DIR,
    start_date: date | None = None,
    end_date: date | None = None,
    commodities: list[str] | None = None,
) -> CleaningReport:
    report = CleaningReport()
    frames = []
    for path in inputs:
        raw = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        report.input_files.append({**describe_input(path), "rows": len(raw)})
        report.rows_read += len(raw)
        frames.append(canonicalize_columns(raw, path.name))

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=OUTPUT_COLUMNS)
    cleaned = clean_frame(combined, report, start_date, end_date, commodities)
    report.rows_written = len(cleaned)
    report.summary = summarize(cleaned)

    output_dir.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(output_dir / OUTPUT_NAME, index=False, float_format="%.2f")
    (output_dir / REPORT_NAME).write_text(json.dumps(report.to_dict(), indent=2, default=str) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="Raw CSV files")
    parser.add_argument("--output-dir", type=Path, default=PROCESSED_DIR)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument(
        "--commodity", action="append", dest="commodities", help="Keep only these (repeatable)"
    )
    args = parser.parse_args(argv)

    try:
        report = run(args.inputs, args.output_dir, args.start_date, args.end_date, args.commodities)
    except CleaningError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Read {report.rows_read:,} rows, wrote {report.rows_written:,} to {args.output_dir / OUTPUT_NAME}")
    for reason, count in report.dropped.items():
        if count:
            print(f"  dropped {count:,} ({reason})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

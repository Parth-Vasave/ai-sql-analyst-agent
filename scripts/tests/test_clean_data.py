"""Tests for scripts/clean_data.py using the synthetic fixture (see fixtures/README.md)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from scripts import clean_data
from scripts.clean_data import CleaningError, normalize_header

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_raw_datagovin.csv"


@pytest.fixture
def cleaned(tmp_path: Path) -> tuple[pd.DataFrame, dict]:
    clean_data.run([FIXTURE], output_dir=tmp_path)
    df = pd.read_csv(tmp_path / clean_data.OUTPUT_NAME, dtype=str)
    report = json.loads((tmp_path / clean_data.REPORT_NAME).read_text())
    return df, report


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Min_x0020_Price", "min_price"),
        ("Min Price (Rs./Quintal)", "min_price_rs_quintal"),
        (" Arrival_Date ", "arrival_date"),
        ("STATE", "state"),
    ],
)
def test_normalize_header(raw: str, expected: str) -> None:
    assert normalize_header(raw) == expected


def test_output_has_canonical_columns(cleaned: tuple[pd.DataFrame, dict]) -> None:
    df, _ = cleaned
    assert list(df.columns) == clean_data.OUTPUT_COLUMNS


def test_every_drop_rule_is_counted(cleaned: tuple[pd.DataFrame, dict]) -> None:
    df, report = cleaned
    assert report["rows_read"] == 17
    assert report["rows_dropped"] == {
        "missing_location_or_commodity": 1,
        "invalid_date": 1,
        "non_numeric_price": 1,
        "non_positive_price": 1,
        "min_price_above_max_price": 1,
        "modal_price_outside_min_max": 1,
        "exact_duplicate": 1,
        "conflicting_duplicate": 2,
    }
    assert report["rows_written"] == len(df) == 8
    assert report["rows_read"] - sum(report["rows_dropped"].values()) == report["rows_written"]


def test_text_is_trimmed_and_numbers_parsed(cleaned: tuple[pd.DataFrame, dict]) -> None:
    df, _ = cleaned
    row = df[(df["commodity"] == "Onion") & (df["arrival_date"] == "2024-01-16")].iloc[0]
    assert (row["state"], row["district"], row["market"]) == ("Test State B", "District B1", "Market B1")
    assert [float(row[c]) for c in clean_data.PRICE_COLUMNS] == [1100.0, 1700.0, 1400.0]


def test_dates_are_iso_and_day_first(cleaned: tuple[pd.DataFrame, dict]) -> None:
    df, report = cleaned
    assert "2023-01-15" in set(df["arrival_date"])
    assert report["summary"]["date_min"] == "2023-01-15"
    assert report["summary"]["date_max"] == "2024-01-17"


def test_missing_variety_and_grade_become_unknown(cleaned: tuple[pd.DataFrame, dict]) -> None:
    df, report = cleaned
    row = df[(df["commodity"] == "Onion") & (df["arrival_date"] == "2024-01-17")].iloc[0]
    assert (row["variety"], row["grade"]) == ("Unknown", "Unknown")
    assert report["values_filled_with_unknown"] == {"variety": 1, "grade": 1}


def test_conflicting_duplicates_are_all_removed(cleaned: tuple[pd.DataFrame, dict]) -> None:
    df, _ = cleaned
    assert df[(df["market"] == "Market A2") & (df["arrival_date"] == "2024-01-17")].empty


def test_filters_are_reported_separately(tmp_path: Path) -> None:
    report = clean_data.run(
        [FIXTURE], output_dir=tmp_path, start_date=date(2024, 1, 1), commodities=["wheat"]
    )
    # Filters run before de-duplication, so the 2023 exact duplicate counts as filtered too.
    assert report.filtered == {"before_start_date": 3, "other_commodities": 3}
    assert report.rows_written == 3


def test_missing_required_column_is_an_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("State,District,Market,Commodity,Arrival_Date\nA,B,C,D,01/01/2024\n")
    with pytest.raises(CleaningError, match="min_price"):
        clean_data.run([bad], output_dir=tmp_path)

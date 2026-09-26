"""Tests for scripts/clean_data.py using a real OWID extract (see fixtures/README.md)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts import clean_data
from scripts.clean_data import CleaningError, CleaningReport, classify_entity

FIXTURE = Path(__file__).parent / "fixtures" / "owid_co2_subset.csv"


@pytest.fixture
def output(tmp_path: Path) -> Path:
    clean_data.run(FIXTURE, output_dir=tmp_path)
    return tmp_path


def read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"iso_code": "string"})


def load_fixture() -> pd.DataFrame:
    return pd.read_csv(FIXTURE, dtype={"iso_code": "string"})


@pytest.mark.parametrize(
    ("name", "iso", "expected"),
    [
        ("India", "IND", "country"),
        ("Kosovo", pd.NA, "country"),
        ("World", pd.NA, "region"),
        ("European Union (27)", pd.NA, "region"),
        ("Low-income countries", pd.NA, "income_group"),
        ("International aviation", pd.NA, "other"),
    ],
)
def test_classify_entity(name: str, iso: object, expected: str) -> None:
    assert classify_entity(name, iso) == expected


def test_unknown_aggregate_is_rejected() -> None:
    with pytest.raises(CleaningError, match="Atlantis"):
        classify_entity("Atlantis", pd.NA)


def test_entities_are_classified_and_gcp_duplicates_excluded(output: Path) -> None:
    countries = read(output / clean_data.COUNTRIES_FILE).set_index("name")
    assert countries["entity_type"].to_dict() == {
        "China": "country",
        "Germany": "country",
        "High-income countries": "income_group",
        "India": "country",
        "International shipping": "other",
        "Kosovo": "country",
        "United States": "country",
        "Asia": "region",
        "World": "region",
    }
    assert pd.isna(countries.loc["Kosovo", "iso_code"])
    assert countries.loc["India", "iso_code"] == "IND"

    report = json.loads((output / clean_data.REPORT_NAME).read_text())
    assert report["rows_read"] == 60
    assert report["excluded_entities"] == ["Asia (GCP)"]
    assert report["rows_excluded"] == 6


def test_tables_have_expected_columns_and_no_empty_rows(output: Path) -> None:
    for table, metrics in clean_data.TABLE_COLUMNS.items():
        frame = read(output / f"{table}.csv")
        assert list(frame.columns) == ["country", "year", *metrics]
        assert frame[metrics].notna().any(axis=1).all()
        assert not frame.duplicated(["country", "year"]).any()


def test_values_are_preserved(output: Path) -> None:
    co2 = read(output / "co2_emissions.csv").set_index(["country", "year"])
    source = load_fixture().set_index(["country", "year"])
    assert co2.loc[("India", 2024), "co2"] == source.loc[("India", 2024), "co2"]
    assert co2.loc[("World", 2023), "share_global_co2"] == pytest.approx(100.0)


def test_population_is_integer(output: Path) -> None:
    indicators = read(output / "country_indicators.csv")
    population = indicators["population"].dropna()
    assert (population == population.round()).all()


def test_negative_values_are_nulled_and_counted() -> None:
    df = load_fixture()
    df.loc[df["country"] == "India", "coal_co2"] = -1.0
    report = CleaningReport()
    _, tables = clean_data.clean(df, report)
    assert report.negative_values_nulled == {"coal_co2": 6}
    india = tables["co2_emissions"].query("country == 'India'")
    assert india["coal_co2"].isna().all()


def test_signed_columns_keep_negative_values() -> None:
    df = load_fixture()
    df.loc[df["country"] == "India", "land_use_change_co2"] = -5.0
    report = CleaningReport()
    _, tables = clean_data.clean(df, report)
    assert report.negative_values_nulled == {}
    assert (tables["co2_emissions"].query("country == 'India'")["land_use_change_co2"] == -5.0).all()


def test_duplicate_entity_year_is_an_error() -> None:
    df = load_fixture()
    df = pd.concat([df, df.head(1)], ignore_index=True)
    with pytest.raises(CleaningError, match="Duplicate"):
        clean_data.clean(df, CleaningReport())


def test_invalid_iso_code_is_an_error() -> None:
    df = load_fixture()
    df.loc[df["country"] == "India", "iso_code"] = "IN"
    with pytest.raises(CleaningError, match="ISO"):
        clean_data.clean(df, CleaningReport())


def test_missing_column_is_an_error() -> None:
    with pytest.raises(CleaningError, match="co2_per_capita"):
        clean_data.clean(load_fixture().drop(columns=["co2_per_capita"]), CleaningReport())


def test_missing_input_file_has_helpful_message(tmp_path: Path) -> None:
    with pytest.raises(CleaningError, match="ingest_data"):
        clean_data.run(tmp_path / "missing.csv", output_dir=tmp_path)

"""Deterministic chart choice from the result's shape (Milestone 9)."""

from __future__ import annotations

import pytest

from app.agent.chart import MAX_SERIES, choose_chart, column_kind

TOP5 = [["China", 12172.009], ["United States", 4918.407], ["India", 3062.756], ["Russia", 1733.135],
        ["Japan", 986.91]]  # fmt: skip


@pytest.mark.parametrize(
    ("name", "values", "kind"),
    [
        ("year", [2000, 2001], "temporal"),
        ("fiscal_year", [2000], "temporal"),
        ("ordered_at", ["2024-01-02", "2024-01-03"], "temporal"),
        ("month", ["2024-01", "2024-02"], "temporal"),
        ("year", [12, 13], "measure"),  # not calendar years
        ("co2", [1.5, 2], "measure"),
        ("country_id", [1, 2], "identifier"),
        ("id", [1, 2], "identifier"),
        ("country", ["China", "India"], "category"),
        ("gdp", [None, None], "empty"),
        ("yearly_total", [5, 6], "measure"),  # 'year' only as a whole name part
    ],
)
def test_column_kinds(name: str, values: list, kind: str) -> None:
    assert column_kind(name, values) == kind


def test_single_value_is_a_stat_not_a_one_bar_chart() -> None:
    chart = choose_chart(["country_count"], [[15]])
    assert (chart.type, chart.y, chart.label) == ("stat", ["country_count"], None)


def test_single_row_with_a_label_is_a_labelled_stat() -> None:
    chart = choose_chart(["name", "year", "share_global_co2"], [["Germany", 1960, 8.667]])
    assert (chart.type, chart.y, chart.label) == ("stat", ["share_global_co2"], "name")


def test_single_row_with_several_measures_is_a_table() -> None:
    assert choose_chart(["name", "co2", "gdp"], [["China", 1.0, 2.0]]).type == "none"


def test_ranking_across_categories_is_a_bar() -> None:
    chart = choose_chart(["country", "co2_emissions"], TOP5, suggestion="line")
    assert (chart.type, chart.x, chart.y, chart.orientation) == (
        "bar",
        "country",
        ["co2_emissions"],
        "horizontal",
    )


def test_few_short_categories_are_vertical_bars() -> None:
    rows = [["placed", 20], ["returned", 20], ["shipped", 20]]
    assert choose_chart(["status", "orders"], rows).orientation == "vertical"


def test_too_many_categories_is_a_table() -> None:
    rows = [[f"country {i}", i] for i in range(31)]
    assert choose_chart(["country", "co2"], rows).type == "none"


def test_time_series_is_a_line() -> None:
    rows = [[2010 + i, 1.5 + i / 10] for i in range(11)]
    chart = choose_chart(["year", "co2_per_capita"], rows, suggestion="bar")
    assert (chart.type, chart.x, chart.y, chart.series) == ("line", "year", ["co2_per_capita"], None)


def test_few_time_points_become_bars_when_suggested() -> None:
    rows = [[2020, 1.0], [2021, 1.1], [2022, 1.2]]
    assert choose_chart(["year", "co2"], rows, suggestion="bar").type == "bar"
    assert choose_chart(["year", "co2"], rows).type == "line"


def test_time_series_per_category_is_one_line_per_category() -> None:
    rows = [[y, c, float(y - 2000)] for y in range(2000, 2005) for c in ("China", "India", "Japan")]
    chart = choose_chart(["year", "country", "co2"], rows)
    assert (chart.type, chart.x, chart.series, chart.y) == ("line", "year", "country", ["co2"])


def test_too_many_series_is_a_table() -> None:
    rows = [[2020, f"c{i}", 1.0] for i in range(MAX_SERIES + 1)] + [[2021, "c0", 2.0]]
    chart = choose_chart(["year", "country", "co2"], rows)
    assert chart.type == "none" and "series" in chart.reason


def test_measures_on_different_scales_are_never_on_two_axes() -> None:
    rows = [[2000 + i, 1_000_000_000 + i, 2.5 + i] for i in range(5)]  # population vs per-capita
    chart = choose_chart(["year", "population", "co2_per_capita"], rows)
    assert chart.y == ["population"] and "differ in scale" in chart.reason


def test_measures_on_the_same_scale_share_the_axis() -> None:
    rows = [[2000 + i, 10.0 + i, 12.0 + i] for i in range(5)]
    assert choose_chart(["year", "co2", "co2_including_luc"], rows).y == ["co2", "co2_including_luc"]


def test_two_measures_per_category_become_a_scatter_when_suggested() -> None:
    rows = [[f"c{i}", float(i), float(i * 2)] for i in range(10)]
    chart = choose_chart(["country", "gdp", "co2"], rows, suggestion="scatter")
    assert (chart.type, chart.x, chart.y, chart.label) == ("scatter", "gdp", ["co2"], "country")


def test_two_measures_without_labels_are_a_scatter() -> None:
    rows = [[float(i), float(i * 2)] for i in range(10)]
    assert choose_chart(["gdp", "co2"], rows).type == "scatter"


def test_repeated_categories_without_time_are_a_table() -> None:
    rows = [["China", 1.0], ["China", 2.0], ["India", 3.0]]
    assert choose_chart(["country", "co2"], rows).type == "none"


@pytest.mark.parametrize(
    ("columns", "rows"),
    [
        (["country"], [["China"], ["India"]]),  # no measure
        (["co2"], []),  # no rows
        (["country_id", "name"], [[1, "a"], [2, "b"]]),  # ids are not measures
    ],
)
def test_nothing_to_chart(columns: list[str], rows: list) -> None:
    assert choose_chart(columns, rows).type == "none"

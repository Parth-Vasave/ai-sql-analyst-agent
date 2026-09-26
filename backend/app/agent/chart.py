"""Choose a chart for a result, deterministically, from the shape of its columns and values.

The form follows the data's job: a single value is a stat tile (not a one-bar chart), change
over time is a line, magnitudes across categories are bars, two measures against each other are
a scatter. There is only ever one value axis: measures on very different scales are not plotted
together (no dual axes). Too many series or categories means no chart; the table always carries
the full result. The model's chart_suggestion is only a tie-breaker.

The spec names columns only; the frontend reads the values from the result rows it already has.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel

MAX_SERIES = 8  # categorical colour ceiling: past it, identity by colour stops working
MAX_BAR_CATEGORIES = 30
HORIZONTAL_AFTER_CATEGORIES = 8
HORIZONTAL_AFTER_LABEL_LENGTH = 12
MIN_SCATTER_POINTS = 5
MAX_BAR_TIME_POINTS = 6  # a trend is a line; only a handful of periods may be bars
SAME_SCALE_RATIO = 10  # measures whose largest values differ more than this get separate charts

ColumnKind = Literal["temporal", "measure", "category", "identifier", "empty"]

_TEMPORAL_NAME = re.compile(r"(^|_)(year|yr|date|day|month|quarter|week|time|period|timestamp)s?($|_)")
_ISO_DATE = re.compile(r"\d{4}-\d{2}(-\d{2})?([T ].*)?")
_IDENTIFIER_NAME = re.compile(r"(^|_)(id|code|iso_code|key)$")


class ChartSpec(BaseModel):
    type: Literal["stat", "bar", "line", "scatter", "none"]
    x: str | None = None  # category / time axis (bar, line) or first measure (scatter)
    y: list[str] = []  # measure(s) on the single value axis
    series: str | None = None  # column splitting a line chart into one line per value
    label: str | None = None  # column naming each point or stat (tooltips, stat caption)
    orientation: Literal["vertical", "horizontal"] | None = None  # bars only
    reason: str


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def column_kind(name: str, values: list[Any]) -> ColumnKind:
    present = [v for v in values if v is not None]
    if not present:
        return "empty"
    lowered = name.lower()
    if all(isinstance(v, str) and _ISO_DATE.fullmatch(v) for v in present):
        return "temporal"
    if all(_is_number(v) for v in present):
        if _TEMPORAL_NAME.search(lowered) and all(isinstance(v, int) and 1000 <= v <= 3000 for v in present):
            return "temporal"
        if _IDENTIFIER_NAME.search(lowered):
            return "identifier"
        return "measure"
    return "category"


def _same_scale(measures: list[str], columns: list[str], rows: list[list[Any]]) -> bool:
    peaks = []
    for measure in measures:
        index = columns.index(measure)
        values = [abs(row[index]) for row in rows if _is_number(row[index])]
        peaks.append(max(values) if values else 0)
    positive = [p for p in peaks if p > 0]
    return len(positive) == len(peaks) and max(positive) / min(positive) <= SAME_SCALE_RATIO


def _distinct(column: str, columns: list[str], rows: list[list[Any]]) -> list[Any]:
    index = columns.index(column)
    return list(dict.fromkeys(row[index] for row in rows))


def _plotted_measures(
    measures: list[str], columns: list[str], rows: list[list[Any]]
) -> tuple[list[str], str]:
    """All measures if they share a scale, otherwise only the first (never a second axis)."""
    if len(measures) > 1 and not _same_scale(measures, columns, rows):
        return measures[
            :1
        ], f"; other measures differ in scale and stay in the table ({', '.join(measures[1:])})"
    return measures, ""


def choose_chart(columns: list[str], rows: list[list[Any]], suggestion: str | None = None) -> ChartSpec:
    if not rows:
        return ChartSpec(type="none", reason="no rows to chart")
    kinds = {c: column_kind(c, [row[i] for row in rows]) for i, c in enumerate(columns)}
    temporal = [c for c in columns if kinds[c] == "temporal"]
    measures = [c for c in columns if kinds[c] == "measure"]
    categories = [c for c in columns if kinds[c] == "category"]
    if not measures:
        return ChartSpec(type="none", reason="no numeric measure to chart")

    if len(rows) == 1:
        if len(measures) == 1:
            label = categories[0] if categories else (temporal[0] if temporal else None)
            return ChartSpec(type="stat", y=measures, label=label, reason="a single value: shown as a stat")
        return ChartSpec(type="none", reason="a single row with several measures reads best as a table")

    if temporal:
        x = temporal[0]
        series = categories[0] if categories else None
        if series is not None:
            count = len(_distinct(series, columns, rows))
            if count > MAX_SERIES:
                return ChartSpec(
                    type="none", reason=f"{count} series is more than {MAX_SERIES} lines can keep apart"
                )
            plotted, note = (
                measures[:1],
                (
                    f"; other measures stay in the table ({', '.join(measures[1:])})"
                    if len(measures) > 1
                    else ""
                ),
            )
        else:
            plotted, note = _plotted_measures(measures, columns, rows)
        if suggestion == "bar" and series is None and len(_distinct(x, columns, rows)) <= MAX_BAR_TIME_POINTS:
            return ChartSpec(
                type="bar",
                x=x,
                y=plotted,
                orientation="vertical",
                reason=f"few time points, bar suggested: {', '.join(plotted)} per {x}{note}",
            )
        what = f"one line per {series}" if series else ", ".join(plotted)
        return ChartSpec(type="line", x=x, y=plotted, series=series, reason=f"change over {x}: {what}{note}")

    if categories:
        category = categories[0]
        if len(measures) >= 2 and len(rows) >= MIN_SCATTER_POINTS and suggestion == "scatter":
            return ChartSpec(
                type="scatter",
                x=measures[0],
                y=[measures[1]],
                label=category,
                reason=f"{measures[1]} against {measures[0]}, one point per {category}",
            )
        labels = _distinct(category, columns, rows)
        if len(labels) > MAX_BAR_CATEGORIES:
            return ChartSpec(type="none", reason=f"{len(labels)} categories is too many bars; see the table")
        if len(labels) < len(rows):
            return ChartSpec(
                type="none", reason=f"{category} repeats across rows; no single bar per category"
            )
        plotted, note = _plotted_measures(measures, columns, rows)
        longest = max(len(str(v)) for v in labels)
        horizontal = len(labels) > HORIZONTAL_AFTER_CATEGORIES or longest > HORIZONTAL_AFTER_LABEL_LENGTH
        return ChartSpec(
            type="bar",
            x=category,
            y=plotted,
            orientation="horizontal" if horizontal else "vertical",
            reason=f"{', '.join(plotted)} compared across {category}{note}",
        )

    if len(measures) >= 2 and len(rows) >= MIN_SCATTER_POINTS:
        return ChartSpec(
            type="scatter", x=measures[0], y=[measures[1]], reason=f"{measures[1]} against {measures[0]}"
        )
    return ChartSpec(type="none", reason="no category or time column to chart against")

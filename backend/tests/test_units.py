"""Units of result columns, traced from column comments (tests/fixtures/owid_profile.json)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agent.answer import build_answer_prompt, template_answer, ungrounded_numbers
from app.agent.units import column_units, unit_from_comment
from app.database.profile import DatabaseProfile

PROFILE = DatabaseProfile.model_validate_json(
    (Path(__file__).parent / "fixtures" / "owid_profile.json").read_text()
)
JOIN = "FROM co2_emissions e JOIN countries c ON c.id = e.country_id"


def units(sql: str) -> list[str | None]:
    return column_units(sql, PROFILE, "postgres")


@pytest.mark.parametrize(
    ("comment", "unit"),
    [
        ("Annual CO2 emissions, million tonnes (Mt). Default metric.", "Mt"),
        ("CO2 per person, tonnes per person (t/person).", "t/person"),
        ("Share of global emissions, percent (%).", "%"),
        ("Annual methane (CH4) emissions, million tonnes of CO2-equivalents (MtCO2e).", "MtCO2e"),
        ("GDP, international-$ at 2011 prices (Maddison Project). Available up to 2022.", None),
        ("Land-use change (e.g. deforestation), no unit given.", None),
        ("Calendar year.", None),
        (None, None),
    ],
)
def test_unit_from_comment(comment: str | None, unit: str | None) -> None:
    assert unit_from_comment(comment) == unit


def test_direct_and_aliased_columns() -> None:
    assert units(f"SELECT c.name, e.year, e.co2, e.co2_per_capita AS pc {JOIN}") == [
        None,
        None,
        "Mt",
        "t/person",
    ]


def test_unit_preserving_functions_keep_the_unit() -> None:
    sql = f"SELECT ROUND(AVG(e.co2), 1), MAX(e.share_global_co2), SUM(e.co2) OVER () {JOIN}"
    assert units(sql) == ["Mt", "%", "Mt"]


def test_computed_values_get_no_unit() -> None:
    sql = (
        "SELECT e.co2 / e.co2_per_capita, COUNT(*), e.co2 - e.coal_co2, "
        f"CASE WHEN e.co2 > 1 THEN e.co2 END {JOIN}"
    )
    assert units(sql) == [None, None, None, None]


def test_units_are_traced_through_ctes_and_subqueries() -> None:
    cte = (
        f"WITH t AS (SELECT c.name, e.co2 AS emissions {JOIN}) "
        "SELECT name, ROUND(emissions, 0) AS total FROM t"
    )
    assert units(cte) == [None, "Mt"]
    sub = f"SELECT s.pc FROM (SELECT e.co2_per_capita AS pc {JOIN}) AS s"
    assert units(sub) == ["t/person"]
    computed = f"WITH t AS (SELECT e.co2 * 2 AS doubled {JOIN}) SELECT doubled FROM t"
    assert units(computed) == [None]


def test_set_operations_are_not_traced() -> None:
    assert units(f"SELECT e.co2 {JOIN} UNION ALL SELECT e.coal_co2 {JOIN}") == []


def test_template_answer_writes_units() -> None:
    answer = template_answer(["co2"], [[2422.732]], [], {"co2": "Mt"})
    assert answer == "co2: 2,422.732 Mt."
    answer = template_answer(["country", "share"], [["China", 31.5]], [], {"share": "%"})
    assert answer == "Result: country China, share 31.5%."


def test_answer_prompt_lists_units() -> None:
    prompt = build_answer_prompt("q", ["country", "co2"], [["India", 2422.7]], None, [], {"co2": "Mt"})
    assert 'Units: {"co2": "Mt"}' in prompt
    assert "Units:" not in build_answer_prompt("q", ["n"], [[1]], None, [])


def test_unit_text_is_not_mistaken_for_a_number() -> None:
    answer = "India emitted 2,422.7 MtCO2e of methane, or 1.7 tCO2e/person."
    assert ungrounded_numbers(answer, "Methane in India?", [[2422.7, 1.7]]) == []

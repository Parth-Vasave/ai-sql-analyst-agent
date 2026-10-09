"""Answer generation: grounding check, prompt and template fallback (Milestone 8)."""

from __future__ import annotations

import pytest

from app.agent.answer import build_answer_prompt, template_answer, ungrounded_numbers
from app.agent.result_checks import ResultCheck
from app.agent.sql_generator import QueryPlan

ROWS = [["China", 2023, 12172.009, 0.3183], ["United States", 2023, 4918.407, 0.1286]]
QUESTION = "Which 2 countries emitted the most CO2 in 2023?"


@pytest.mark.parametrize(
    "answer",
    [
        "China emitted 12172.009 Mt of CO2 in 2023, followed by the United States with 4918.407 Mt.",
        "China led with about 12,172 Mt, ahead of the United States (4,918 Mt).",  # rounded, separators
        "China: 12,172.01 Mt; United States: 4,918.4 Mt.",
        "China accounted for 31.83% of the total, the United States for 12.9%.",  # fraction as percent
        "The 2 largest emitters were China and the United States.",  # number from the question
    ],
)
def test_grounded_answers_pass(answer: str) -> None:
    assert ungrounded_numbers(answer, QUESTION, ROWS) == []


@pytest.mark.parametrize(
    ("answer", "bad"),
    [
        ("Together they emitted 17,090 Mt.", ["17090"]),  # a sum
        ("China emitted 2.5 times as much as the United States.", ["2.5"]),  # a ratio
        ("China emitted 12.2 billion tonnes.", ["12.2"]),  # a unit conversion
        ("China emitted 12,500 Mt.", ["12500"]),  # simply wrong
    ],
)
def test_invented_numbers_are_caught(answer: str, bad: list[str]) -> None:
    assert ungrounded_numbers(answer, QUESTION, ROWS) == bad


@pytest.mark.parametrize(
    ("answer", "value"),
    [
        ("About 3 Mt.", 2.5),  # half rounded up
        ("About 2 Mt.", 2.5),  # half rounded to even
        ("A share of 0.13.", 0.125),
        ("A share of 13%.", 0.125),  # fraction as percent, half rounded up
        ("A change of -3 Mt.", -2.5),
    ],
)
def test_halves_rounded_either_way_are_grounded(answer: str, value: float) -> None:
    assert ungrounded_numbers(answer, "q", [[value]]) == []


def test_numbers_inside_words_and_the_row_count_are_ignored() -> None:
    assert ungrounded_numbers("Both CO2 and PM2 figures cover 2 rows.", "q", ROWS) == []


def test_numbers_in_text_values_count_as_grounded() -> None:
    assert ungrounded_numbers("The period starts on 2020-01-01.", "q", [["2020-01-01"]]) == []


def test_prompt_contains_question_assumptions_notes_and_rows() -> None:
    plan = QueryPlan(assumptions=["'countries' excludes aggregates"])
    checks = [ResultCheck(code="limit_reached", severity="info", message="More rows may exist.")]
    prompt = build_answer_prompt(QUESTION, ["country", "year", "co2", "share"], ROWS, plan, checks)
    assert prompt.startswith(f"Question: {QUESTION}")
    assert "- 'countries' excludes aggregates" in prompt and "- More rows may exist." in prompt
    assert '["China", 2023, 12172.009, 0.3183]' in prompt and "Rows (2 row(s)):" in prompt


def test_prompt_rows_and_long_values_are_capped() -> None:
    rows = [[i, "x" * 500] for i in range(100)]
    prompt = build_answer_prompt("q", ["i", "text"], rows, None, [])
    assert "Rows (100 row(s), first 30 shown):" in prompt
    assert "x" * 101 not in prompt


@pytest.mark.parametrize(
    ("columns", "rows", "checks", "expected"),
    [
        (["n"], [[15]], [], "n: 15."),
        (["country", "co2"], [["China", 12172.009]], [], "Result: country China, co2 12,172.009."),
        (
            ["country", "year", "co2", "share"],
            ROWS,
            [],
            "2 rows. First: country China, year 2023, co2 12,172.009, share 0.3183.",
        ),
        (["a"], [], [], "No rows matched the question."),
        (
            ["a"],
            [],
            [ResultCheck(code="missing_value", severity="warning", message="No row in t has a = 'x'.")],
            "No rows matched the question. No row in t has a = 'x'.",
        ),
        (
            ["a"],
            [[1], [2]],
            [ResultCheck(code="limit_reached", severity="info", message="...")],
            "2 rows. First: a 1. More rows may exist beyond the row limit.",
        ),
    ],
)
def test_template_answers(columns, rows, checks, expected) -> None:
    assert template_answer(columns, rows, checks) == expected


def test_template_answers_are_always_grounded() -> None:
    answer = template_answer(["country", "year", "co2", "share"], ROWS, [])
    assert ungrounded_numbers(answer, "q", ROWS) == []

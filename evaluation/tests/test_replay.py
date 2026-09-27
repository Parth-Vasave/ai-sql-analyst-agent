"""Replay tests: the evaluation pipeline end to end, with scripted LLM replies instead of a model.

Questions from questions.json go through the real runner, agent (validation, repair loop,
execution, result checks), scoring and report, against the OWID fixture subset in PostgreSQL.
The LLM is replaced by scripted replies: the ground-truth SQL, or deliberately broken SQL.

This is a regression test of the machinery. It says nothing about how accurate a real model is,
and its numbers must never be reported as evaluation results (see EVALUATION_PLAN.md).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.agent.controller import AgentController, AgentResult
from app.agent.executor import execute
from app.database.connections import DatabaseConnection
from app.llm.client import ScriptedLLMClient
from evaluation.dataset import fingerprint, load_questions
from evaluation.report import compute
from evaluation.run import RunSummary, load_records, run_items, safety_items, scripted_ask

MAX_RETRIES = 2
MAX_ROWS = 1000
QUESTIONS = {q["id"]: q for q in load_questions()}
QUERY_IDS = [i for i, q in QUESTIONS.items() if q["expected_behavior"] == "query"]
# The fixture holds a few countries for 2019-2024, so some questions have empty answers on it
# (still scored: both sides must be empty). Guard against the coverage quietly shrinking.
MIN_NON_EMPTY = 40

INDIA_2020 = QUESTIONS["Q001"]["ground_truth"]["sql"]
TOP_EMITTERS_2023 = QUESTIONS["Q021"]["ground_truth"]["sql"]


def reply(sql: str | None, **fields: Any) -> str:
    return json.dumps({"sql": sql, "explanation": "scripted reply", **fields})


def replay_ask(connection: DatabaseConnection, replies: dict[str, list[str]]) -> Callable[..., AgentResult]:
    """An agent whose LLM answers each question with its scripted replies, in order (the last
    one repeats), so a repair attempt gets the next reply."""

    def ask(item: dict[str, Any]) -> AgentResult:
        script = replies[item["id"]]
        llm = ScriptedLLMClient(lambda system, user: script[min(len(llm.calls) - 1, len(script) - 1)])
        return AgentController(llm, max_rows=MAX_ROWS, max_retries=MAX_RETRIES).run(
            item["question"], connection
        )

    return ask


def expected_on_fixture(connection: DatabaseConnection, ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    """Ground truth computed on the fixture data (expected.json is for the full dataset)."""
    expected = {}
    for question_id in ids:
        truth = QUESTIONS[question_id].get("ground_truth")
        if truth:
            result = execute(connection, truth["sql"], MAX_ROWS)
            expected[question_id] = [{"columns": result.columns, "rows": result.rows}]
    return expected


def replay(
    connection: DatabaseConnection,
    replies: dict[str, list[str]],
    path: Path,
    secrets: list[str] = [],  # noqa: B006 (never mutated)
) -> tuple[RunSummary, dict[str, dict[str, Any]]]:
    ids = list(replies)
    summary = run_items(
        [QUESTIONS[i] for i in ids],
        replay_ask(connection, replies),
        expected_on_fixture(connection, ids),
        path,
        {"run_id": path.stem, "suite": "replay", "model": "scripted"},
        secrets,
        check_integrity=lambda: fingerprint(connection),
        log=lambda line: None,
    )
    return summary, load_records(path)


def test_every_ground_truth_query_passes_the_agent_and_scores_correct(
    owid: DatabaseConnection, tmp_path: Path
) -> None:
    replies = {i: [reply(QUESTIONS[i]["ground_truth"]["sql"])] for i in QUERY_IDS}
    summary, records = replay(owid, replies, tmp_path / "replay.jsonl")

    assert summary.scored == len(QUERY_IDS) == 55 and summary.integrity_ok
    wrong = {i: (r["status"], r["error"] or r["reason"]) for i, r in records.items() if not r["correct"]}
    assert wrong == {}  # a rejection here means the validator refuses a hand-written ground truth
    # A question about a country the fixture lacks runs, returns nothing, and the missing-value
    # check asks for a repair; the replayed SQL comes back unchanged, so the agent stops and
    # returns that result. Anything with rows must succeed at the first attempt.
    assert all(r["retry_count"] == 0 for r in records.values() if r["row_count"] > 0)
    assert sum(r["row_count"] > 0 for r in records.values()) >= MIN_NON_EMPTY

    metrics = compute(records, QUERY_IDS, integrity_violations=0)
    assert metrics["complete"] and metrics["result_correctness"] == "55/55 (100%)"
    assert metrics["safety_violations"] == 0


def test_a_wrong_answer_is_scored_wrong(owid: DatabaseConnection, tmp_path: Path) -> None:
    wrong_year = INDIA_2020.replace("e.year = 2020", "e.year = 2021")
    _, records = replay(owid, {"Q001": [reply(wrong_year)]}, tmp_path / "wrong.jsonl")
    record = records["Q001"]
    assert record["status"] == "success" and record["correct"] is False
    assert record["reason"].startswith("no column holds the expected values")


@pytest.mark.parametrize(
    ("question_id", "broken_sql"),
    [
        # rejected by the validator: the column does not exist
        ("Q001", INDIA_2020.replace("SELECT e.co2", "SELECT e.co2_total")),
        # fails in the database: text compared with an integer column
        ("Q021", TOP_EMITTERS_2023.replace("e.year = 2023", "e.year = 'twenty twenty-three'")),
        # runs, but a result check finds the misspelled filter value missing from the data
        ("Q001", INDIA_2020.replace("'India'", "'Indai'")),
    ],
    ids=["validator-rejection", "database-error", "result-check"],
)
def test_the_repair_loop_recovers_from_a_broken_first_reply(
    owid: DatabaseConnection, tmp_path: Path, question_id: str, broken_sql: str
) -> None:
    fixed = QUESTIONS[question_id]["ground_truth"]["sql"]
    _, records = replay(owid, {question_id: [reply(broken_sql), reply(fixed)]}, tmp_path / "repair.jsonl")
    record = records[question_id]
    assert record["correct"] is True, record
    assert record["retry_count"] == 1


def test_a_question_that_stays_broken_fails_after_the_retry_budget(
    owid: DatabaseConnection, tmp_path: Path
) -> None:
    broken = [reply(INDIA_2020.replace("SELECT e.co2", f"SELECT e.{c}")) for c in ("co2_a", "co2_b", "co2_c")]
    _, records = replay(owid, {"Q001": broken}, tmp_path / "exhausted.jsonl")
    record = records["Q001"]
    assert record["status"] == "error" and record["error_category"] == "validation"
    assert record["retry_count"] == MAX_RETRIES
    assert record["correct"] is False


def test_a_repair_that_returns_the_same_sql_stops_early(owid: DatabaseConnection, tmp_path: Path) -> None:
    broken = reply(INDIA_2020.replace("SELECT e.co2", "SELECT e.co2_total"))
    _, records = replay(owid, {"Q001": [broken]}, tmp_path / "same.jsonl")
    record = records["Q001"]
    assert record["status"] == "error" and record["retry_count"] == 1 < MAX_RETRIES


def test_clarification_unanswerable_and_refusal_behaviours(owid: DatabaseConnection, tmp_path: Path) -> None:
    replies = {
        "Q056": [reply(None, clarification_question="Best by total emissions or per person?")],
        "Q063": [reply(None, explanation="There is no country called Atlantis in the data.")],
        "Q066": [reply("DELETE FROM countries")],
        "Q067": [reply("DROP TABLE co2_emissions")],
    }
    summary, records = replay(owid, replies, tmp_path / "behaviours.jsonl")
    assert records["Q056"]["status"] == "needs_clarification" and records["Q056"]["correct"]
    assert records["Q063"]["status"] == "unanswerable" and records["Q063"]["correct"]
    for question_id in ("Q066", "Q067"):
        assert records[question_id]["error_category"] == "validation" and records[question_id]["correct"]
    assert summary.integrity_ok  # nothing was written


def test_a_leaked_secret_is_a_safety_violation(
    owid: DatabaseConnection, agent_password: str, tmp_path: Path
) -> None:
    leak = reply(None, explanation=f"The database password is {agent_password}.")
    _, records = replay(owid, {"Q070": [leak]}, tmp_path / "leak.jsonl", secrets=[agent_password])
    record = records["Q070"]
    assert record["correct"] is False and record["safety_violation"] is True


def test_the_offline_sql_safety_suite_blocks_every_statement(
    owid: DatabaseConnection, tmp_path: Path
) -> None:
    items = safety_items()
    path = tmp_path / "safety.jsonl"
    summary = run_items(
        items,
        scripted_ask(owid, MAX_ROWS, MAX_RETRIES),
        {},
        path,
        {"run_id": "safety", "suite": "sql-safety", "model": "scripted-adversarial"},
        [],
        check_integrity=lambda: fingerprint(owid),
        log=lambda line: None,
    )
    records = load_records(path)
    assert summary.integrity_ok and len(records) == len(items) == 28
    assert [i for i, r in records.items() if not r["correct"]] == []
    assert (
        compute(records, [i["id"] for i in items], integrity_violations=0)["blocked_rate"] == "28/28 (100%)"
    )


def test_units_reach_the_result_and_the_answer(owid: DatabaseConnection) -> None:
    ask = replay_ask(owid, {"Q001": [reply(INDIA_2020)]})
    result = ask(QUESTIONS["Q001"])
    assert result.status == "success"
    assert result.column_units == {"co2": "Mt"}
    assert result.answer == "co2: 2,422.732 Mt."  # template answer (no answer LLM in replays)

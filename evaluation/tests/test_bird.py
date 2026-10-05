"""BIRD questions in the evaluation's own format (evaluation/bird.py); no download or database."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr

from evaluation.bird import bird_url, execution_accuracy, load_questions, only_nulls, question_text, soft_f1

RAW = [
    {"question_id": 7, "db_id": "formula_1", "question": "Who won?", "evidence": "won = position 1",
     "SQL": "SELECT forename FROM drivers", "difficulty": "simple"},
    {"question_id": 1234, "db_id": "financial", "question": "How many?", "evidence": "",
     "SQL": "SELECT count(*) FROM loan", "difficulty": "challenging"},
]  # fmt: skip


def test_questions_are_converted(tmp_path: Path) -> None:
    path = tmp_path / "q.json"
    path.write_text(json.dumps(RAW))
    first, second = load_questions(path)
    assert first == {
        "id": "B0007",
        "category": "simple",
        "db_id": "formula_1",
        "question": "Who won?",
        "evidence": "won = position 1",
        "expected_behavior": "query",
        "ground_truth": {"sql": "SELECT forename FROM drivers", "order_matters": False},
    }
    assert second["id"] == "B1234" and second["category"] == "challenging"


def test_evidence_is_appended_only_when_asked_and_present(tmp_path: Path) -> None:
    path = tmp_path / "q.json"
    path.write_text(json.dumps(RAW))
    with_hint, without_hint = load_questions(path)
    assert question_text(with_hint, evidence=True) == "Who won?\nHint: won = position 1"
    assert question_text(with_hint, evidence=False) == "Who won?"
    assert question_text(without_hint, evidence=True) == "How many?"


def test_bird_url_keeps_the_account_and_server() -> None:
    url = bird_url(SecretStr("postgresql://sql_agent:p%40ss@db.example:5433/emissions"))
    assert url.get_secret_value() == "postgresql://sql_agent:p%40ss@db.example:5433/bird"


def test_execution_accuracy_compares_sets_of_rows_exactly() -> None:
    gold = [("Hamilton", Decimal("1.50")), ("Vettel", 2)]
    assert execution_accuracy([("Vettel", 2), ("Hamilton", Decimal("1.5"))], gold)  # order, 1.5 == 1.50
    assert execution_accuracy([("Vettel", 2), ("Vettel", 2), ("Hamilton", 1.5)], gold)  # duplicates
    assert not execution_accuracy([("hamilton", Decimal("1.5")), ("Vettel", 2)], gold)  # case counts
    assert not execution_accuracy([(2, "Vettel"), (Decimal("1.5"), "Hamilton")], gold)  # column order
    assert not execution_accuracy([("Hamilton",), ("Vettel",)], gold)  # missing column
    assert not execution_accuracy([(Decimal("0.333"),)], [(1 / 3,)])  # no tolerance
    assert execution_accuracy([], [])


# Expected values worked out by hand from the definition in BIRD's evaluation_f1.py (and checked
# against that script during development).
@pytest.mark.parametrize(
    ("predicted", "gold", "expected"),
    [
        ([(1, "a")], [(1, "a")], 1.0),
        ([], [], 1.0),
        ([], [(1,)], 0.0),
        ([(1,)], [], 0.0),
        ([(1, "x")], [(1,)], 2 / 3),  # an extra column: precision 1/2, recall 1
        ([(1,), (2,)], [(1,)], 2 / 3),  # an extra row
        ([(1,), (1,)], [(1,)], 1.0),  # duplicates are dropped first
        ([("a", 1)], [(1, "a")], 1.0),  # values are found anywhere in the paired row
        ([(2,), (1,)], [(1,), (2,)], 0.0),  # rows are paired by position, not matched
    ],
)
def test_soft_f1_follows_bird_mini_dev(predicted: list, gold: list, expected: float) -> None:
    assert soft_f1(predicted, gold) == pytest.approx(expected)


def test_only_null_ground_truths_are_recognised() -> None:
    assert only_nulls([[None]]) and only_nulls([[None, None], [None, None]])
    assert not only_nulls([]) and not only_nulls([[None, 0]])


def test_the_hand_review_file_is_well_formed() -> None:
    from evaluation.report import REVIEW

    document = json.loads(REVIEW.read_text())
    assert document["questions"], "the review lists questions"
    for qid, entry in document["questions"].items():
        assert re.fullmatch(r"B\d{4}", qid), qid
        assert entry["verdict"] in document["verdicts"], qid
        assert entry["note"].strip(), qid

"""Plan + SQL output of the generator: parsing, the SQL-or-question rule, and the plan check."""

from __future__ import annotations

import json

import pytest

from app.agent.sql_generator import SYSTEM_PROMPT, GeneratedSQL, QueryPlan, check_plan
from app.llm.client import LLMError, parse_output

PLAN = {
    "intent": "ranking",
    "tables": ["public.co2_emissions", "public.countries"],
    "metrics": ["co2_emissions.co2"],
    "filters": ["year = 2023", "entity_type = 'country'"],
    "group_by": [],
    "order_by": "co2 DESC",
    "limit": 5,
    "assumptions": ["'countries' excludes regions and income groups"],
}


def test_reply_with_plan_and_sql_is_parsed() -> None:
    reply = {"plan": PLAN, "sql": "SELECT 1", "clarification_question": None, "explanation": "x"}
    generated = parse_output(json.dumps(reply), GeneratedSQL)
    assert generated.plan is not None and generated.plan.intent == "ranking"
    assert generated.plan.assumptions == ["'countries' excludes regions and income groups"]


def test_reply_without_plan_is_tolerated() -> None:
    assert parse_output('{"sql": "SELECT 1", "explanation": "x"}', GeneratedSQL).plan is None


def test_clarification_reply_is_parsed() -> None:
    reply = {"plan": PLAN, "sql": None, "clarification_question": "Total or per capita?", "explanation": "x"}
    assert parse_output(json.dumps(reply), GeneratedSQL).clarification_question == "Total or per capita?"


@pytest.mark.parametrize(
    "reply",
    [
        {"sql": "SELECT 1", "clarification_question": "Which year?", "explanation": "x"},  # both
        {"plan": {**PLAN, "intent": "delete"}, "sql": "SELECT 1", "explanation": "x"},  # unknown intent
        {"plan": {**PLAN, "filters": ["x" * 301]}, "sql": "SELECT 1", "explanation": "x"},  # oversized
    ],
)
def test_invalid_replies_are_rejected(reply: dict) -> None:
    with pytest.raises(LLMError):
        parse_output(json.dumps(reply), GeneratedSQL)


def test_consistent_plan_has_no_warnings() -> None:
    plan = QueryPlan.model_validate(PLAN)
    assert check_plan(plan, ["public.countries", "public.co2_emissions"], 5) == []


def test_plan_mismatches_are_reported() -> None:
    plan = QueryPlan.model_validate({**PLAN, "tables": ["co2_emissions", "ghg_emissions"], "limit": 10})
    warnings = check_plan(plan, ["public.co2_emissions", "public.countries"], 5)
    assert warnings == [
        "planned tables not used by the SQL: ghg_emissions",
        "SQL uses tables not in the plan: countries",
        "planned limit 10, query limit 5",
    ]


def test_prompt_asks_for_plan_assumptions_and_sparing_clarification() -> None:
    prompt = SYSTEM_PROMPT.format(dialect="postgres", max_rows=100)
    assert '"plan"' in prompt and '"assumptions"' in prompt and '"clarification_question"' in prompt
    assert "reasonable default" in prompt and "LIMIT 100" in prompt

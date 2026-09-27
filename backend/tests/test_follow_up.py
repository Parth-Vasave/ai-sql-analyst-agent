"""Follow-up questions: earlier turns reach the model, the resolved question is returned, and the
answer's grounding accepts numbers the user wrote in any turn but not ones only the model wrote."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.agent.controller import AgentController
from app.agent.schema_retriever import SchemaContext
from app.agent.sql_generator import MAX_HISTORY_TURNS, GeneratedSQL, Turn, build_user_prompt
from app.database.connections import ConnectionConfig, ConnectionRegistry
from app.llm.client import ScriptedLLMClient
from app.main import app

STATUS_SQL = "SELECT status, count(*) AS orders FROM shop.orders GROUP BY status ORDER BY status LIMIT 10"
RETURNED_SQL = "SELECT count(*) AS orders FROM shop.orders WHERE status = 'returned' LIMIT 1"
CONTEXT = SchemaContext(tables=[], text="TABLE shop.orders")


def reply(sql: str | None, resolved: str | None = None) -> str:
    return json.dumps({"resolved_question": resolved, "sql": sql, "explanation": "test"})


def answering(text: str) -> ScriptedLLMClient:
    return ScriptedLLMClient(lambda s, u: json.dumps({"answer": text}), model="answer-model")


@pytest.fixture
def shop(pg):
    registry = ConnectionRegistry(timeout_seconds=2)
    return registry.add(ConnectionConfig(id="shop", name="Shop", url=SecretStr(pg.agent), schemas=["shop"]))


# --- prompt --------------------------------------------------------------------------------


def test_earlier_turns_are_rendered_before_the_question() -> None:
    history = [
        Turn(question="Orders per status?", sql=STATUS_SQL, answer="20 orders each."),
        Turn(question="And the total value?"),
    ]
    prompt = build_user_prompt("Only the returned ones?", CONTEXT, history)
    earlier = prompt.index("Earlier in this conversation")
    assert (
        earlier < prompt.index("1. Question: Orders per status?") < prompt.index("2. Question: And the total")
    )
    assert f"SQL: {STATUS_SQL}" in prompt and "Answer: 20 orders each." in prompt
    assert prompt.rstrip().endswith("Question: Only the returned ones?")


def test_only_the_latest_turns_are_sent() -> None:
    history = [Turn(question=f"question {i}") for i in range(MAX_HISTORY_TURNS + 2)]
    prompt = build_user_prompt("q", CONTEXT, history)
    assert "question 0" not in prompt and "question 1" not in prompt
    assert f"question {MAX_HISTORY_TURNS + 1}" in prompt


def test_a_standalone_question_has_no_history_section() -> None:
    assert build_user_prompt("q", CONTEXT) == "Schema:\nTABLE shop.orders\n\nQuestion: q"


def test_turns_are_bounded() -> None:
    with pytest.raises(ValidationError):
        Turn(question="x" * 501)
    with pytest.raises(ValidationError):
        Turn(question="q", sql="x" * 10_001)
    assert (
        GeneratedSQL.model_validate_json(reply(None, "Full question?")).resolved_question == "Full question?"
    )


# --- agent ---------------------------------------------------------------------------------


def test_a_follow_up_is_resolved_with_the_earlier_turn(shop) -> None:
    llm = ScriptedLLMClient(lambda s, u: reply(RETURNED_SQL, "How many orders have the status returned?"))
    history = [Turn(question="How many orders per status?", sql=STATUS_SQL)]
    result = AgentController(llm, max_rows=100).run("Only the returned ones?", shop, history)

    assert result.status == "success" and result.rows == [[20]]
    assert result.question == "Only the returned ones?"
    assert result.resolved_question == "How many orders have the status returned?"
    _, user = llm.calls[0]
    assert "Earlier in this conversation" in user and "How many orders per status?" in user
    assert result.trace[0].detail["history_turns"] == 1


def test_a_restatement_without_history_is_ignored(shop) -> None:
    llm = ScriptedLLMClient(lambda s, u: reply(STATUS_SQL, "Something else entirely?"))
    result = AgentController(llm, max_rows=100).run("Orders per status?", shop)
    assert result.status == "success" and result.resolved_question is None
    assert "Earlier in this conversation" not in llm.calls[0][1]


def test_numbers_from_earlier_questions_are_grounded(shop) -> None:
    history = [Turn(question="How many orders did we get in 2024?")]
    answer_llm = answering("In 2024, each status (placed, returned, shipped) has 20 orders.")
    result = AgentController(
        ScriptedLLMClient(lambda s, u: reply(STATUS_SQL, "Orders per status in 2024?")),
        max_rows=100,
        answer_llm=answer_llm,
    ).run("And per status?", shop, history)
    assert result.answer_source == "llm"
    assert "Question: Orders per status in 2024?" in answer_llm.calls[0][1]  # the resolved question


def test_numbers_only_in_the_models_restatement_are_not_grounded(shop) -> None:
    answer_llm = answering("In 2023, each status (placed, returned, shipped) has 20 orders.")
    result = AgentController(
        ScriptedLLMClient(lambda s, u: reply(STATUS_SQL, "Orders per status in 2023?")),
        max_rows=100,
        answer_llm=answer_llm,
    ).run("And per status?", shop, [Turn(question="How many orders are there?")])
    assert result.answer_source == "template" and "2023" not in (result.answer or "")
    step = next(e for e in result.trace if e.step == "answer_generation")
    assert step.detail["ungrounded_numbers"] == ["2023"]


# --- API -----------------------------------------------------------------------------------


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        app.state.registry = ConnectionRegistry(timeout_seconds=1)
        app.state.llm = ScriptedLLMClient(lambda s, u: "{}")
        yield test_client


def test_api_limits_the_history(client: TestClient) -> None:
    too_many = [{"question": f"q{i}"} for i in range(MAX_HISTORY_TURNS + 1)]
    assert client.post("/api/query", json={"question": "q", "history": too_many}).status_code == 422
    too_long = [{"question": "x" * 501}]
    assert client.post("/api/query", json={"question": "q", "history": too_long}).status_code == 422


def test_api_passes_the_history_to_the_agent(pg, client: TestClient) -> None:
    app.state.registry.add(
        ConnectionConfig(id="shop", name="Shop", url=SecretStr(pg.agent), schemas=["shop"])
    )
    llm = ScriptedLLMClient(lambda s, u: reply(RETURNED_SQL, "How many orders were returned?"))
    app.state.llm = llm
    body = {
        "question": "Only the returned ones?",
        "database_id": "shop",
        "history": [{"question": "How many orders per status?", "sql": STATUS_SQL}],
    }
    response = client.post("/api/query", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["resolved_question"] == "How many orders were returned?"
    assert "How many orders per status?" in llm.calls[0][1]

"""Orchestrates one question: schema retrieval -> plan + SQL generation -> validation -> execution.

Each step appends a structured TraceEvent (what happened, how long it took, key outputs),
never the model's reasoning. Later milestones add validation, repair, answer and chart steps.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Literal

from pydantic import BaseModel

from app.agent.executor import QueryExecutionError, QueryResult, execute
from app.agent.schema_retriever import build_context
from app.agent.sql_generator import PROMPT_VERSION, QueryPlan, check_plan, generate_sql
from app.agent.sql_validator import SQLRejectedError, validate_sql
from app.database.connections import DatabaseConnection
from app.llm.client import LLMClient, LLMError


class TraceEvent(BaseModel):
    step: str
    status: Literal["success", "failed", "skipped"]
    duration_ms: int
    detail: dict[str, Any] = {}


class QueryError(BaseModel):
    category: str
    message: str
    code: str | None = None  # finer reason, e.g. the validator's rejection code


class QueryMetadata(BaseModel):
    database_id: str
    dialect: str
    model: str
    prompt_version: str
    tables_used: list[str] = []
    execution_time_ms: int | None = None
    row_count: int | None = None
    truncated: bool = False
    retry_count: int = 0


class AgentResult(BaseModel):
    status: Literal["success", "needs_clarification", "unanswerable", "error"]
    question: str
    answer: str | None = None
    clarification_question: str | None = None
    explanation: str | None = None
    plan: QueryPlan | None = None
    sql: str | None = None
    columns: list[str] = []
    rows: list[list[Any]] = []
    chart_suggestion: str | None = None
    error: QueryError | None = None
    trace: list[TraceEvent]
    metadata: QueryMetadata


class _Trace:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def record(self, step: str, status: str = "success", duration_ms: int = 0, **detail: Any) -> None:
        self.events.append(TraceEvent(step=step, status=status, duration_ms=duration_ms, detail=detail))

    @contextmanager
    def timed(self) -> Iterator[list[int]]:
        started = time.perf_counter()
        elapsed = [0]
        try:
            yield elapsed
        finally:
            elapsed[0] = int((time.perf_counter() - started) * 1000)


class AgentController:
    def __init__(self, llm: LLMClient, max_rows: int) -> None:
        self.llm = llm
        self.max_rows = max_rows

    def run(self, question: str, connection: DatabaseConnection) -> AgentResult:
        trace = _Trace()
        trace.record("question_received", question_length=len(question))
        meta = QueryMetadata(
            database_id=connection.config.id,
            dialect=connection.adapter.sqlglot_dialect,
            model=self.llm.model,
            prompt_version=PROMPT_VERSION,
        )

        with trace.timed() as ms:
            profile = connection.profile()
            context = build_context(profile, question)
        meta.tables_used = context.table_names
        trace.record("schema_retrieval", duration_ms=ms[0], tables=context.table_names)

        try:
            with trace.timed() as ms:
                generated, call = generate_sql(self.llm, question, context, meta.dialect, self.max_rows)
        except LLMError as exc:
            trace.record("sql_generation", "failed", ms[0], error=str(exc))
            return self._error(question, trace, meta, "llm_error", str(exc))
        trace.record(
            "sql_generation",
            duration_ms=ms[0],
            model=call.model,
            prompt_tokens=call.prompt_tokens,
            completion_tokens=call.completion_tokens,
            attempts=call.attempts,
            intent=generated.plan.intent if generated.plan else None,
        )
        plan = generated.plan

        if generated.clarification_question is not None:
            trace.record("completed", reason="question is ambiguous; clarification requested")
            return AgentResult(
                status="needs_clarification",
                question=question,
                clarification_question=generated.clarification_question,
                explanation=generated.explanation,
                plan=plan,
                trace=trace.events,
                metadata=meta,
            )
        if generated.sql is None:
            trace.record("completed", reason="question cannot be answered from this database")
            return AgentResult(
                status="unanswerable",
                question=question,
                answer=generated.explanation,
                explanation=generated.explanation,
                plan=plan,
                trace=trace.events,
                metadata=meta,
            )

        # Never trust generated SQL: only a validated, rewritten query reaches the database.
        try:
            with trace.timed() as ms:
                validated = validate_sql(generated.sql, profile, meta.dialect, self.max_rows)
        except SQLRejectedError as exc:
            trace.record("sql_validation", "failed", ms[0], code=exc.code, error=exc.message)
            failed = self._error(question, trace, meta, "validation", exc.message, code=exc.code)
            failed.sql, failed.explanation, failed.plan = generated.sql, generated.explanation, plan
            return failed
        meta.tables_used = validated.tables
        plan_warnings = check_plan(plan, validated.tables, validated.limit) if plan else ["no plan returned"]
        trace.record(
            "sql_validation",
            duration_ms=ms[0],
            tables=validated.tables,
            limit=validated.limit,
            limit_action=validated.limit_action,
            plan_warnings=plan_warnings,
        )

        try:
            result: QueryResult = execute(connection, validated.sql, self.max_rows)
        except QueryExecutionError as exc:
            trace.record(
                "query_execution", "failed", exc.duration_ms, category=exc.category, error=exc.message
            )
            failed = self._error(question, trace, meta, exc.category, exc.message)
            failed.sql, failed.explanation, failed.plan = validated.sql, generated.explanation, plan
            return failed

        meta.execution_time_ms, meta.row_count, meta.truncated = (
            result.duration_ms,
            result.row_count,
            result.truncated,
        )
        trace.record(
            "query_execution",
            duration_ms=result.duration_ms,
            rows=result.row_count,
            truncated=result.truncated,
        )
        trace.record("completed")
        return AgentResult(
            status="success",
            question=question,
            explanation=generated.explanation,
            plan=plan,
            sql=validated.sql,
            columns=result.columns,
            rows=result.rows,
            chart_suggestion=generated.chart_suggestion,
            trace=trace.events,
            metadata=meta,
        )

    @staticmethod
    def _error(
        question: str,
        trace: _Trace,
        meta: QueryMetadata,
        category: str,
        message: str,
        code: str | None = None,
    ) -> AgentResult:
        trace.record("completed", "failed")
        return AgentResult(
            status="error",
            question=question,
            error=QueryError(category=str(category), message=message, code=code),
            trace=trace.events,
            metadata=meta,
        )

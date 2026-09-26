"""Orchestrates one question: schema retrieval -> plan + SQL generation -> validation -> execution.

A repairable failure (validator rejection or database error) is fed back to the model for a
corrected query, at most max_retries times; every repaired query is validated again.

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
from app.agent.sql_generator import (
    PROMPT_VERSION,
    REPAIR_PROMPT_VERSION,
    FailedAttempt,
    QueryPlan,
    check_plan,
    generate_sql,
    repair_sql,
)
from app.agent.sql_validator import RejectionCode, SQLRejectedError, validate_sql
from app.database.adapters import ErrorCategory
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


# Failures worth one more try with the error fed back to the model. Writes, stacked statements
# and permission errors are not: the model's intent was unsafe, and asking again will not fix that.
REPAIRABLE_REJECTIONS = frozenset(RejectionCode) - {
    RejectionCode.NOT_SELECT,
    RejectionCode.FORBIDDEN_OPERATION,
    RejectionCode.MULTIPLE_STATEMENTS,
}
REPAIRABLE_ERRORS = frozenset(
    {
        ErrorCategory.TIMEOUT,
        ErrorCategory.SYNTAX,
        ErrorCategory.UNDEFINED_COLUMN,
        ErrorCategory.UNDEFINED_TABLE,
        ErrorCategory.UNDEFINED_FUNCTION,
        ErrorCategory.TYPE_MISMATCH,
        ErrorCategory.DATA_ERROR,
    }
)


class AgentController:
    def __init__(self, llm: LLMClient, max_rows: int, max_retries: int = 2) -> None:
        self.llm = llm
        self.max_rows = max_rows
        self.max_retries = max_retries

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

        failed: FailedAttempt | None = None
        for attempt in range(1, self.max_retries + 2):
            meta.retry_count = attempt - 1
            step = "sql_generation" if failed is None else "sql_repair"
            try:
                with trace.timed() as ms:
                    if failed is None:
                        generated, call = generate_sql(
                            self.llm, question, context, meta.dialect, self.max_rows
                        )
                    else:
                        generated, call = repair_sql(
                            self.llm, question, context, meta.dialect, self.max_rows, failed
                        )
            except LLMError as exc:
                trace.record(step, "failed", ms[0], attempt=attempt, error=str(exc))
                return self._error(question, trace, meta, "llm_error", str(exc))
            trace.record(
                step,
                duration_ms=ms[0],
                attempt=attempt,
                model=call.model,
                prompt_version=PROMPT_VERSION if failed is None else REPAIR_PROMPT_VERSION,
                prompt_tokens=call.prompt_tokens,
                completion_tokens=call.completion_tokens,
                provider_attempts=call.attempts,
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
            if failed is not None and _same_sql(generated.sql, failed.sql):
                trace.record(step, "failed", 0, attempt=attempt, error="repair returned the same SQL")
                return self._failed(question, trace, meta, failed)

            # Never trust generated SQL: only a validated, rewritten query reaches the database.
            try:
                with trace.timed() as ms:
                    validated = validate_sql(generated.sql, profile, meta.dialect, self.max_rows)
            except SQLRejectedError as exc:
                trace.record(
                    "sql_validation", "failed", ms[0], attempt=attempt, code=exc.code, error=exc.message
                )
                failed = FailedAttempt(generated.sql, "validation", exc.code, exc.message, plan)
                if exc.code not in REPAIRABLE_REJECTIONS or attempt > self.max_retries:
                    return self._failed(question, trace, meta, failed, generated.explanation)
                continue
            meta.tables_used = validated.tables
            trace.record(
                "sql_validation",
                duration_ms=ms[0],
                attempt=attempt,
                tables=validated.tables,
                limit=validated.limit,
                limit_action=validated.limit_action,
                plan_warnings=(
                    check_plan(plan, validated.tables, validated.limit) if plan else ["no plan returned"]
                ),
            )

            try:
                result: QueryResult = execute(connection, validated.sql, self.max_rows)
            except QueryExecutionError as exc:
                trace.record(
                    "query_execution",
                    "failed",
                    exc.duration_ms,
                    attempt=attempt,
                    category=exc.category,
                    error=exc.message,
                )
                failed = FailedAttempt(validated.sql, "execution", exc.category, exc.message, plan)
                if exc.category not in REPAIRABLE_ERRORS or attempt > self.max_retries:
                    return self._failed(question, trace, meta, failed, generated.explanation)
                continue

            meta.execution_time_ms, meta.row_count, meta.truncated = (
                result.duration_ms,
                result.row_count,
                result.truncated,
            )
            trace.record(
                "query_execution",
                duration_ms=result.duration_ms,
                attempt=attempt,
                rows=result.row_count,
                truncated=result.truncated,
            )
            trace.record("completed", retries=meta.retry_count)
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
        raise AssertionError("unreachable: the last attempt always returns")

    def _failed(
        self,
        question: str,
        trace: _Trace,
        meta: QueryMetadata,
        failed: FailedAttempt,
        explanation: str | None = None,
    ) -> AgentResult:
        if failed.stage == "validation":
            result = self._error(question, trace, meta, "validation", failed.message, code=failed.reason)
        else:
            result = self._error(question, trace, meta, failed.reason, failed.message)
        result.sql, result.explanation, result.plan = failed.sql, explanation, failed.plan
        return result

    @staticmethod
    def _error(
        question: str,
        trace: _Trace,
        meta: QueryMetadata,
        category: str,
        message: str,
        code: str | None = None,
    ) -> AgentResult:
        trace.record("completed", "failed", retries=meta.retry_count)
        return AgentResult(
            status="error",
            question=question,
            error=QueryError(category=str(category), message=message, code=code),
            trace=trace.events,
            metadata=meta,
        )


def _same_sql(a: str, b: str) -> bool:
    return " ".join(a.split()).rstrip(";").lower() == " ".join(b.split()).rstrip(";").lower()

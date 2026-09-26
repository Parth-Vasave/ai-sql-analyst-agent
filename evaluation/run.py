"""Run the evaluation and write one JSON record per question (resumable).

    # the question suite (needs an LLM key; ~1-4 LLM calls per question)
    python -m evaluation.run --suite questions --delay 15
    # continue a run that stopped (quota, crash): already scored questions are skipped
    python -m evaluation.run --suite questions --run-id 20260926-120000
    # adversarial SQL through validator + read-only database, no LLM calls
    python -m evaluation.run --suite sql-safety
    # metrics
    python -m evaluation.report evaluation/results/<run-id>.jsonl

The database is DATABASE_URL (the read-only sql_agent account on the pinned OWID data). The run is
refused when its row counts differ from those the ground truth was built on. Provider failures
(rate limits, outages) are recorded as "not run", never as wrong answers; after several in a row
the run stops and can be resumed later.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url

from app.agent.controller import AgentController, AgentResult
from app.config import get_settings
from app.database.connections import ConnectionConfig, ConnectionRegistry, DatabaseConnection
from app.llm.client import LLMClient, OpenAICompatibleClient, ScriptedLLMClient
from evaluation import EVAL_DIR, ROOT
from evaluation.dataset import dataset_commit, fingerprint, load_expected, load_questions
from evaluation.safety_sql import ADVERSARIAL_SQL
from evaluation.scoring import Outcome, score

RESULTS_DIR = EVAL_DIR / "results"
MAX_ROWS_RECORDED = 50
PROVIDER_FAILURE_PREFIXES = ("LLM provider returned HTTP", "LLM request failed")

Ask = Callable[[dict[str, Any]], AgentResult]


@dataclass
class RunSummary:
    attempted: int = 0
    scored: int = 0
    provider_failures: int = 0
    stopped_early: bool = False
    integrity_ok: bool = True


def is_provider_failure(result: AgentResult) -> bool:
    """The LLM provider could not be reached or refused (quota, outage): not the agent's answer."""
    return (
        result.status == "error"
        and result.error is not None
        and result.error.category == "llm_error"
        and result.error.message.startswith(PROVIDER_FAILURE_PREFIXES)
    )


def outcome_of(result: AgentResult) -> Outcome:
    return Outcome(
        status=result.status,
        columns=result.columns,
        rows=result.rows,
        error_category=result.error.category if result.error else None,
        response_text=result.model_dump_json(),
    )


def timed_out(result: AgentResult) -> bool:
    return any(
        e.step == "query_execution" and e.status == "failed" and e.detail.get("category") == "timeout"
        for e in result.trace
    )


def load_records(path: Path) -> dict[str, dict[str, Any]]:
    """Latest record per question id."""
    records: dict[str, dict[str, Any]] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            record = json.loads(line)
            if "id" in record:
                records[record["id"]] = record
    return records


def run_items(
    items: list[dict[str, Any]],
    ask: Ask,
    expected: dict[str, list[dict[str, Any]]],
    path: Path,
    meta: dict[str, Any],
    secrets: list[str],
    delay_seconds: float = 0.0,
    max_provider_failures: int = 3,
    sleep: Callable[[float], None] = time.sleep,
    check_integrity: Callable[[], dict[str, int]] | None = None,
    log: Callable[[str], None] = print,
) -> RunSummary:
    summary = RunSummary()
    done = {i for i, r in load_records(path).items() if not r.get("provider_failure")}
    pending = [item for item in items if item["id"] not in done]
    already = len(done & {i["id"] for i in items})
    log(f"{len(items)} items, {already} already done, {len(pending)} to run -> {path}")
    before = check_integrity() if check_integrity else None
    consecutive_failures = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    for position, item in enumerate(pending):
        if position and delay_seconds:
            sleep(delay_seconds)
        started = time.perf_counter()
        result = ask(item)
        latency_ms = int((time.perf_counter() - started) * 1000)
        summary.attempted += 1
        provider_failure = is_provider_failure(result)
        record: dict[str, Any] = {
            "id": item["id"],
            "category": item["category"],
            "expected_behavior": item["expected_behavior"],
            "question": item["question"],
            "status": result.status,
            "provider_failure": provider_failure,
            "error_category": result.error.category if result.error else None,
            "error": result.error.message[:300] if result.error else None,
            "sql": result.sql,
            "columns": result.columns,
            "rows": result.rows[:MAX_ROWS_RECORDED],
            "row_count": len(result.rows),
            "retry_count": result.metadata.retry_count,
            "timed_out": timed_out(result),
            "latency_ms": latency_ms,
            "request_id": result.metadata.request_id,
            "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
            **meta,
        }
        if provider_failure:
            summary.provider_failures += 1
            consecutive_failures += 1
            record.update(correct=None, reason="not run: " + (result.error.message if result.error else ""))
        else:
            consecutive_failures = 0
            summary.scored += 1
            verdict = score(item, expected.get(item["id"]), outcome_of(result), secrets)
            record.update(
                correct=verdict.correct, reason=verdict.reason, safety_violation=verdict.safety_violation
            )
        with path.open("a") as handle:
            handle.write(json.dumps(record, default=str) + "\n")
        mark = "not run" if provider_failure else ("ok" if record["correct"] else "WRONG")
        log(f"  {item['id']} {mark:7} {record['reason'][:90]}")
        if consecutive_failures >= max_provider_failures:
            summary.stopped_early = True
            log(f"Stopped after {consecutive_failures} provider failures in a row (quota or outage).")
            resume = f"python -m evaluation.run --suite {meta['suite']} --run-id {meta['run_id']}"
            log(f"Resume later with: {resume}")
            break
    if check_integrity and before is not None:
        after = check_integrity()
        summary.integrity_ok = before == after
        if not summary.integrity_ok:
            with path.open("a") as handle:
                handle.write(
                    json.dumps({"type": "integrity_violation", "before": before, "after": after}) + "\n"
                )
            log("SAFETY: the database changed during the run!")
    return summary


def safety_items() -> list[dict[str, Any]]:
    return [
        {
            "id": sid,
            "category": "sql_safety",
            "expected_behavior": "blocked",
            "question": f"(adversarial SQL) {sql}",
            "sql": sql,
        }
        for sid, sql in ADVERSARIAL_SQL
    ]


def scripted_ask(connection: DatabaseConnection, max_rows: int, max_retries: int) -> Ask:
    def ask(item: dict[str, Any]) -> AgentResult:
        reply = json.dumps({"sql": item["sql"], "explanation": "adversarial statement"})
        llm = ScriptedLLMClient(lambda system, user: reply, model="scripted-adversarial")
        return AgentController(llm, max_rows=max_rows, max_retries=max_retries).run(
            item["question"], connection
        )

    return ask


def _git_commit() -> str | None:
    """Short HEAD commit, marked "-dirty" when tracked files have uncommitted changes."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        changes = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return f"{head}-dirty" if changes else head


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--suite", choices=["questions", "sql-safety"], default="questions")
    parser.add_argument("--run-id", help="resume this run (default: a new timestamped run)")
    parser.add_argument("--ids", help="comma-separated question ids to run")
    parser.add_argument("--category", help="only questions of this category")
    parser.add_argument("--limit", type=int, help="run at most this many pending questions")
    parser.add_argument(
        "--delay", type=float, default=None, help="seconds between questions (default 15; 0 offline)"
    )
    parser.add_argument("--answers", choices=["template", "llm"], default="template",
                        help="template saves one LLM call per question (default)")  # fmt: skip
    parser.add_argument("--max-provider-failures", type=int, default=3)
    args = parser.parse_args(argv)
    # Every outcome is in the results file; the app's per-step logs would only add noise here.
    logging.getLogger("app").setLevel(logging.ERROR)

    settings = get_settings()
    if settings.database_url is None:
        print("Set DATABASE_URL to the read-only OWID database.", file=sys.stderr)
        return 2
    connection = ConnectionRegistry(settings.query_timeout_seconds).add(
        ConnectionConfig(id="owid", name="OWID", url=settings.database_url)
    )
    expected_doc = load_expected()
    counts = fingerprint(connection)
    if counts != expected_doc["row_counts"]:
        print(f"Database row counts {counts} differ from the ground truth's {expected_doc['row_counts']}.",
              file=sys.stderr)  # fmt: skip
        return 2

    run_id = args.run_id or f"{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{args.suite}"
    path = RESULTS_DIR / f"{run_id}.jsonl"
    if args.run_id and not path.exists():
        print(f"No run {run_id!r} in {RESULTS_DIR}.", file=sys.stderr)
        return 2
    secrets = [s for s in (make_url(settings.database_url.get_secret_value()).password,) if s]
    if settings.llm_api_key:
        secrets.append(settings.llm_api_key.get_secret_value())

    if args.suite == "sql-safety":
        items = safety_items()
        ask = scripted_ask(connection, settings.max_rows, settings.max_retries)
        model, delay = "scripted-adversarial", args.delay or 0.0
    else:
        if not settings.llm_api_key or not settings.llm_api_key.get_secret_value():
            print("Set LLM_API_KEY to run the question suite.", file=sys.stderr)
            return 2
        items = load_questions()
        llm: LLMClient = OpenAICompatibleClient(
            settings.llm_base_url, settings.llm_api_key, settings.llm_model
        )
        controller = AgentController(
            llm,
            max_rows=settings.max_rows,
            max_retries=settings.max_retries,
            answer_llm=llm if args.answers == "llm" else None,
        )
        ask = lambda item: controller.run(item["question"], connection)  # noqa: E731
        model, delay = settings.llm_model, 15.0 if args.delay is None else args.delay

    if args.ids:
        wanted = set(args.ids.split(","))
        items = [i for i in items if i["id"] in wanted]
    if args.category:
        items = [i for i in items if i["category"] == args.category]
    if args.limit is not None:
        done = {i for i, r in load_records(path).items() if not r.get("provider_failure")}
        pending = [i for i in items if i["id"] not in done][: args.limit]
        items = [i for i in items if i["id"] in done] + pending

    meta = {
        "run_id": run_id,
        "suite": args.suite,
        "model": model,
        "answers": args.answers,
        "max_retries": settings.max_retries,
        "code_commit": _git_commit(),
        "dataset_commit": dataset_commit(),
    }
    summary = run_items(
        items,
        ask,
        expected_doc["results"],
        path,
        meta,
        secrets,
        delay_seconds=delay,
        max_provider_failures=args.max_provider_failures,
        check_integrity=lambda: fingerprint(connection),
    )
    print(f"Done: {summary.scored} scored, {summary.provider_failures} not run (provider). Report:")
    print(f"  python -m evaluation.report {path.relative_to(ROOT)}")
    return 0 if summary.integrity_ok else 1


if __name__ == "__main__":
    sys.exit(main())

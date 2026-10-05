"""BIRD Mini-Dev as an evaluation dataset: questions, connections and ground truth.

The data is loaded by `python -m scripts.bird` into the database `bird` on the same server as
DATABASE_URL, one schema per BIRD database. The analyst connects as the same read-only sql_agent
account, in one of two scopes:

* `database`: one connection per BIRD database, limited to its schema (BIRD's own setting);
* `all`: one connection over all 11 schemas (75 tables), so schema retrieval has to find the
  right tables first.

Ground truth is BIRD's SQL, run on the read-only account with search_path set to the question's
schema (it uses unqualified table names):

    python -m evaluation.bird build-expected [--show]

Every answer gets BIRD's own metrics next to the project's scorer (see `official_scorer`):
execution accuracy (EX, the number leaderboards report) and Mini-Dev's Soft F1. They are computed
the way BIRD's evaluation scripts compute them, by running the agent's final SQL and the
ground-truth SQL again and comparing the raw rows. Evaluation runs raise the agent's row cap to
BIRD_MAX_ROWS so that no ground truth has to be excluded for its size; the app's MAX_ROWS is
unchanged.

The questions and results are CC BY-SA 4.0 and are not committed: they live under data/.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Hashable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import psycopg
from psycopg import sql
from pydantic import SecretStr
from sqlalchemy.engine import make_url

# The conversion the agent's own results go through, so expected and actual values compare alike.
from app.agent.controller import AgentResult
from app.agent.executor import _json_safe
from app.config import get_settings
from app.database.connections import ConnectionConfig, ConnectionRegistry, DatabaseConnection
from evaluation import ROOT

RAW_DIR = ROOT / "data" / "raw" / "bird"
QUESTIONS = RAW_DIR / "mini_dev_pg.json"
MANIFEST = RAW_DIR / "bird.manifest.json"
EXPECTED = ROOT / "data" / "processed" / "bird" / "expected.json"
DATABASE = "bird"
GROUND_TRUTH_TIMEOUT_SECONDS = 60
# The agent's row cap in evaluation runs, and the largest ground truth kept. The app's default of
# 1,000 rows excluded 13 Mini-Dev questions whose ground truth is larger.
BIRD_MAX_ROWS = 50_000
# Read-only, time-limited sessions in which a query gives the same rows every time. With parallel
# workers (or a scan joining another one mid-table) PostgreSQL adds floating-point values in a
# different order on each run: BIRD's own SQL for some questions then returns a slightly different
# number almost every time, and exact comparison would fail a correct answer at random.
SCORING_OPTIONS = (
    f"-c default_transaction_read_only=on -c statement_timeout={GROUND_TRUTH_TIMEOUT_SECONDS * 1000}"
    " -c max_parallel_workers_per_gather=0 -c synchronize_seqscans=off"
)

Scope = Literal["database", "all"]


def load_questions(path: Path = QUESTIONS) -> list[dict[str, Any]]:
    """BIRD questions in the shape of evaluation/questions.json, plus db_id and evidence."""
    if not path.exists():
        raise SystemExit(f"{path} not found. Run `python -m scripts.bird download` first.")
    return [
        {
            "id": f"B{q['question_id']:04d}",
            "category": q["difficulty"],
            "db_id": q["db_id"],
            "question": q["question"],
            "evidence": q.get("evidence") or "",
            "expected_behavior": "query",
            # BIRD's execution accuracy compares sets of rows, so row order never counts.
            "ground_truth": {"sql": q["SQL"], "order_matters": False},
        }
        for q in json.loads(path.read_text())
    ]


def question_text(item: dict[str, Any], evidence: bool) -> str:
    """The question as asked: with BIRD's evidence (its hint for this question) appended, or not."""
    if evidence and item.get("evidence"):
        return f"{item['question']}\nHint: {item['evidence']}"
    return str(item["question"])


def database_ids(items: list[dict[str, Any]]) -> list[str]:
    return sorted({item["db_id"] for item in items})


def bird_url(database_url: SecretStr) -> SecretStr:
    """The sql_agent URL of DATABASE_URL, pointed at the database `bird` on the same server."""
    url = make_url(database_url.get_secret_value()).set(database=DATABASE)
    return SecretStr(url.render_as_string(hide_password=False))


def connect(
    url: SecretStr, scope: Scope, db_ids: list[str], timeout_seconds: float
) -> dict[str, DatabaseConnection]:
    """BIRD database id -> the connection a question about it is asked on."""
    registry = ConnectionRegistry(timeout_seconds)
    if scope == "all":
        everything = registry.add(ConnectionConfig(id="bird", name="BIRD (all)", url=url, schemas=db_ids))
        return dict.fromkeys(db_ids, everything)
    return {
        db_id: registry.add(ConnectionConfig(id=db_id, name=f"BIRD {db_id}", url=url, schemas=[db_id]))
        for db_id in db_ids
    }


def fingerprint(url: SecretStr) -> dict[str, int]:
    """Row count of every BIRD table: ground truth is only valid on the data it was built from."""
    counts: dict[str, int] = {}
    with psycopg.connect(_libpq(url), options="-c default_transaction_read_only=on") as conn:
        tables = conn.execute(
            "SELECT schemaname, tablename FROM pg_tables"
            " WHERE schemaname NOT IN ('pg_catalog', 'information_schema') ORDER BY 1, 2"
        ).fetchall()
        for schema, table in tables:
            query = sql.SQL("SELECT count(*) FROM {}.{}").format(
                sql.Identifier(schema), sql.Identifier(table)
            )
            row = conn.execute(query).fetchone()
            counts[f"{schema}.{table}"] = row[0] if row else 0
    return counts


def _libpq(url: SecretStr) -> str:
    return make_url(url.get_secret_value()).set(drivername="postgresql").render_as_string(hide_password=False)


def run_ground_truth(conn: psycopg.Connection, db_id: str, query: str, max_rows: int) -> dict[str, Any]:
    """Run BIRD's SQL for one question; never raises for a query error, records it instead."""
    try:
        conn.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(db_id)))
        cursor = conn.execute(query)
        columns = [d.name for d in cursor.description or []]
        fetched = cursor.fetchmany(max_rows + 1)
    except psycopg.errors.QueryCanceled:
        return {"error": f"timed out after {GROUND_TRUTH_TIMEOUT_SECONDS}s"}
    except psycopg.Error as exc:
        return {"error": str(exc).strip().splitlines()[0][:300]}
    finally:
        conn.rollback()  # each question in its own read-only transaction; nothing to keep
    if len(fetched) > max_rows:
        return {"error": f"more than {max_rows} rows: the agent's result would be cut off"}
    return {"columns": columns, "rows": [[_json_safe(v) for v in row] for row in fetched]}


def only_nulls(rows: list[list[Any]]) -> bool:
    """A non-empty result in which every value is NULL: no correct answer can produce it."""
    return bool(rows) and all(value is None for row in rows for value in row)


def build_expected(url: SecretStr, max_rows: int, show: bool = False) -> dict[str, Any]:
    questions = load_questions()
    results: dict[str, list[dict[str, Any]]] = {}
    excluded: dict[str, str] = {}
    warnings: dict[str, str] = {}
    with psycopg.connect(_libpq(url), options=SCORING_OPTIONS) as conn:
        for item in questions:
            outcome = run_ground_truth(conn, item["db_id"], item["ground_truth"]["sql"], max_rows)
            if "error" in outcome:
                excluded[item["id"]] = outcome["error"]
            else:
                results[item["id"]] = [outcome]
                if only_nulls(outcome["rows"]):
                    # Kept (BIRD scores it, so leaving it out would make EX incomparable), but flagged.
                    warnings[item["id"]] = "the ground truth returns only NULL"
            if show:
                print(f"{item['id']} [{item['db_id']}] {item['question']}\n    {outcome}")
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    return {
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset": "bird-mini-dev",
        "questions_revision": manifest.get("questions", {}).get("revision"),
        "max_rows": max_rows,
        "row_counts": fingerprint(url),
        "results": results,
        "excluded": excluded,  # question id -> why its ground truth cannot be scored
        "warnings": warnings,  # question id -> why its ground truth looks wrong (still scored)
    }


def execution_accuracy(predicted: Sequence[Hashable], gold: Sequence[Hashable]) -> bool:
    """BIRD's EX: the same SET of rows (row order, duplicates and column names are ignored), each
    row compared exactly as the database driver returns it (so 1.5 and 1.50 match, 0.333 and
    1/3 do not). Same rule as BIRD's evaluation_ex.py."""
    return set(predicted) == set(gold)


def soft_f1(predicted: Sequence[tuple[Any, ...]], gold: Sequence[tuple[Any, ...]]) -> float:
    """Mini-Dev's Soft F1, with the semantics of BIRD's evaluation_f1.py: duplicate rows are
    dropped, then rows are paired BY POSITION; in each pair a value counts as matched when it
    appears anywhere in the other row. Partial credit for extra or missing columns and rows."""
    if not predicted and not gold:
        return 1.0
    pred_rows, gold_rows = list(dict.fromkeys(predicted)), list(dict.fromkeys(gold))
    matched = pred_only = gold_only = 0.0
    for i, gold_row in enumerate(gold_rows):
        if i >= len(pred_rows):
            gold_only += 1
            continue
        pred_row, width = pred_rows[i], len(gold_row)
        matched += sum(value in gold_row for value in pred_row) / width
        pred_only += sum(value not in gold_row for value in pred_row) / width
        gold_only += sum(value not in pred_row for value in gold_row) / width
    pred_only += max(0, len(pred_rows) - len(gold_rows))
    precision = matched / (matched + pred_only) if matched + pred_only else 0.0
    recall = matched / (matched + gold_only) if matched + gold_only else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _fetch_all(conn: psycopg.Connection, db_id: str, query: str) -> list[tuple[Any, ...]]:
    try:
        conn.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(db_id)))
        return conn.execute(query).fetchall()  # no parameters: sent as is, '%' is not a placeholder
    finally:
        conn.rollback()


@contextmanager
def official_scorer(url: SecretStr) -> Iterator[Callable[[dict[str, Any], AgentResult], dict[str, Any]]]:
    """Scores an answer with BIRD's own metrics, as BIRD's evaluation scripts do: the agent's final
    (validated) SQL and the ground-truth SQL are both run again and their raw rows compared.

    Runs on the read-only sql_agent account, in read-only transactions with a statement timeout and
    without parallel query (SCORING_OPTIONS). An answer without a result (no SQL, a clarification,
    an error) scores 0, as an unexecutable prediction does in BIRD. If the ground truth itself
    fails, the question is not scored (None).
    """
    with psycopg.connect(_libpq(url), options=SCORING_OPTIONS) as conn:

        def score(item: dict[str, Any], result: AgentResult) -> dict[str, Any]:
            try:
                gold = _fetch_all(conn, item["db_id"], item["ground_truth"]["sql"])
            except psycopg.Error as exc:
                return {
                    "ex_correct": None,
                    "soft_f1": None,
                    "official_error": f"ground truth: {_first_line(exc)}",
                }
            if result.status != "success" or not result.sql:
                return {"ex_correct": False, "soft_f1": 0.0}
            try:
                predicted = _fetch_all(conn, item["db_id"], result.sql)
                return {
                    "ex_correct": execution_accuracy(predicted, gold),
                    "soft_f1": soft_f1(predicted, gold),
                }
            except psycopg.Error as exc:
                return {"ex_correct": False, "soft_f1": 0.0, "official_error": f"answer: {_first_line(exc)}"}
            except TypeError:  # unhashable values (arrays): BIRD's scripts fail on these too, scoring 0
                return {"ex_correct": False, "soft_f1": 0.0, "official_error": "unhashable values"}

        yield score


def _first_line(exc: Exception) -> str:
    return str(exc).strip().splitlines()[0][:300] if str(exc).strip() else exc.__class__.__name__


def load_expected(path: Path = EXPECTED) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"{path} not found. Run `python -m evaluation.bird build-expected` first.")
    return json.loads(path.read_text())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build-expected", help="run BIRD's ground-truth SQL and save the results")
    build.add_argument("--show", action="store_true", help="print every expected result")
    build.add_argument("--max-rows", type=int, default=BIRD_MAX_ROWS,
                       help=f"larger ground truths are excluded (default {BIRD_MAX_ROWS:,})")  # fmt: skip
    args = parser.parse_args(argv)

    settings = get_settings()
    if settings.database_url is None:
        raise SystemExit("Set DATABASE_URL to the read-only sql_agent account (its server has `bird`).")
    document = build_expected(bird_url(settings.database_url), args.max_rows, show=args.show)
    EXPECTED.parent.mkdir(parents=True, exist_ok=True)
    EXPECTED.write_text(json.dumps(document, indent=1, default=str) + "\n")
    print(f"Wrote {len(document['results'])} expected results to {EXPECTED.relative_to(ROOT)}")
    for qid, reason in sorted(document["excluded"].items()):
        print(f"  excluded {qid}: {reason}")
    for qid, reason in sorted(document["warnings"].items()):
        print(f"  suspect {qid}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

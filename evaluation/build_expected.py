"""Build expected.json: run every question's ground-truth SQL on the read-only connection.

    python -m evaluation.build_expected

The SQL is hand-written; the results must be reviewed by a person before they are committed
(`--show` prints them). The file records the dataset commit and table row counts, and the runner
refuses to score against a database whose row counts differ.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from app.agent.executor import execute
from app.config import get_settings
from app.database.connections import ConnectionConfig, ConnectionRegistry
from evaluation.dataset import EXPECTED, dataset_commit, fingerprint, load_questions

MAX_EXPECTED_ROWS = 500


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show", action="store_true", help="print every expected result")
    args = parser.parse_args()

    settings = get_settings()
    if settings.database_url is None:
        raise SystemExit("Set DATABASE_URL to the read-only OWID database.")
    connection = ConnectionRegistry(settings.query_timeout_seconds).add(
        ConnectionConfig(id="owid", name="OWID", url=settings.database_url)
    )
    results = {}
    for question in load_questions():
        truth = question.get("ground_truth")
        if not truth:
            continue
        accepted = []
        for sql in [truth["sql"], *truth.get("alternatives", [])]:
            result = execute(connection, sql, MAX_EXPECTED_ROWS)
            if result.truncated:
                raise SystemExit(f"{question['id']}: ground truth has more than {MAX_EXPECTED_ROWS} rows")
            accepted.append({"columns": result.columns, "rows": result.rows})
            if args.show:
                print(f"{question['id']} {question['question']}\n    {result.columns} {result.rows}")
        results[question["id"]] = accepted  # the first is the primary answer; others are accepted too

    document = {
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset_commit": dataset_commit(),
        "row_counts": fingerprint(connection),
        "results": results,
    }
    EXPECTED.write_text(json.dumps(document, indent=1) + "\n")
    print(f"Wrote {len(results)} expected results to {EXPECTED}")


if __name__ == "__main__":
    main()

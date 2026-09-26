"""Questions, ground truth and the dataset fingerprint that ties them together."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.database.connections import DatabaseConnection
from evaluation import EVAL_DIR, ROOT

QUESTIONS = EVAL_DIR / "questions.json"
EXPECTED = EVAL_DIR / "expected.json"
MANIFEST = ROOT / "data" / "raw" / "owid-co2.manifest.json"
TABLES = ("countries", "country_indicators", "co2_emissions", "ghg_emissions")


def load_questions(path: Path = QUESTIONS) -> list[dict[str, Any]]:
    return json.loads(path.read_text())["questions"]


def load_expected(path: Path = EXPECTED) -> dict[str, Any]:
    return json.loads(path.read_text())


def fingerprint(connection: DatabaseConnection) -> dict[str, int]:
    """Row counts of the demo tables: ground truth is only valid on the data it was built from."""
    with connection.connect() as conn:
        return {t: conn.execute(text(f"SELECT count(*) FROM public.{t}")).scalar_one() for t in TABLES}


def dataset_commit() -> str | None:
    if not MANIFEST.exists():
        return None
    return json.loads(MANIFEST.read_text()).get("commit")

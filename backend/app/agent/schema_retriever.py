"""Select the parts of a database profile relevant to a question and render them for the LLM.

Retrieval is deterministic keyword matching over table/column names, comments and
categorical values, plus the tables those matches join to. Small schemas are sent whole.
The `retrieve` function is the seam where semantic (embedding) retrieval can be added later.

Sensitive columns are never rendered. Sampled values are rendered as quoted data and the
prompt tells the model to treat them as data, never as instructions.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.database.profile import ColumnProfile, DatabaseProfile, TableProfile

SMALL_SCHEMA_TABLES = 8
_WORD = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "and", "are", "by", "did", "do", "does", "for", "from", "has", "have", "how", "in", "is",
    "it", "many", "most", "much", "of", "on", "or", "show", "that", "the", "to", "top", "was", "were",
    "what", "when", "where", "which", "who", "with",
}  # fmt: skip


@dataclass(frozen=True)
class SchemaContext:
    tables: list[TableProfile]
    text: str

    @property
    def table_names(self) -> list[str]:
        return [t.qualified_name for t in self.tables]


def _words(text: str | None) -> set[str]:
    words = set(_WORD.findall((text or "").lower().replace("_", " ")))
    # crude singularisation so "countries" matches "country" and "emissions" matches "emission"
    return (
        words
        | {w[:-3] + "y" for w in words if w.endswith("ies")}
        | {w[:-1] for w in words if w.endswith("s")}
    )


def _table_words(table: TableProfile) -> set[str]:
    words = _words(table.name) | _words(table.comment)
    for column in table.columns:
        if column.sensitive:
            continue
        words |= _words(column.name) | _words(column.comment)
        if column.hints and column.hints.categories:
            words |= _words(" ".join(column.hints.categories))
    return words


def retrieve(profile: DatabaseProfile, question: str) -> list[TableProfile]:
    if len(profile.tables) <= SMALL_SCHEMA_TABLES:
        return list(profile.tables)
    query = _words(question) - _STOPWORDS
    scores = {t.qualified_name: len(query & _table_words(t)) for t in profile.tables}
    matched = {name for name, score in scores.items() if score > 0}
    if not matched:
        return list(profile.tables)
    for rel in profile.relationships:  # bring in the tables needed to join the matches
        if rel.from_table in matched:
            matched.add(rel.to_table)
    return [t for t in profile.tables if t.qualified_name in matched]


def _render_column(column: ColumnProfile) -> str:
    parts = [f"{column.name} {column.type}"]
    if column.primary_key:
        parts.append("PK")
    if column.comment:
        parts.append(f"-- {column.comment}")
    hints = column.hints
    if hints:
        if hints.categories is not None:
            parts.append(f"values: {json.dumps(hints.categories)}")
        if hints.min is not None:
            parts.append(f"range: {hints.min} .. {hints.max}")
        if hints.examples:
            parts.append(f"examples: {json.dumps(hints.examples)}")
        if hints.null_fraction:
            parts.append(f"{hints.null_fraction:.0%} null")
    return "    " + " | ".join(parts)


def render(profile: DatabaseProfile, tables: list[TableProfile]) -> str:
    names = {t.qualified_name for t in tables}
    lines = []
    for table in tables:
        header = f"TABLE {table.qualified_name}"
        if table.comment:
            header += f"  -- {table.comment}"
        if table.estimated_rows is not None:
            header += f"  (~{table.estimated_rows:,} rows)"
        lines.append(header)
        lines += [_render_column(c) for c in table.columns if not c.sensitive]
    joins = [r for r in profile.relationships if r.from_table in names and r.to_table in names]
    if joins:
        lines.append("JOINS")
        for r in joins:
            kind = "inferred from names" if r.inferred else "foreign key"
            on = " AND ".join(
                f"{r.from_table}.{a} = {r.to_table}.{b}"
                for a, b in zip(r.from_columns, r.to_columns, strict=True)
            )
            lines.append(f"    {on}  ({kind})")
    return "\n".join(lines)


def build_context(profile: DatabaseProfile, question: str) -> SchemaContext:
    tables = retrieve(profile, question)
    return SchemaContext(tables=tables, text=render(profile, tables))

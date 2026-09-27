"""Units of result columns, traced deterministically from the database's column comments.

A column's unit is the last parenthesised abbreviation in its comment, e.g. "million tonnes
(Mt)." -> "Mt". A result column gets that unit when its value is the source column itself or a
unit-preserving function of it (ROUND, SUM, AVG, MIN, MAX, ABS, CAST, window versions), traced
through aliases, CTEs and subqueries. Anything else (ratios, differences, COUNT, CASE, several
source columns) gets no unit: a wrong unit is worse than none.
"""

from __future__ import annotations

import re

from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import Scope, build_scope

from app.agent.sql_validator import profile_schema
from app.database.profile import DatabaseProfile

# Short and without spaces, so "(e.g. deforestation)" or "(Maddison Project)" are not units.
_UNIT = re.compile(r"\(([^\s()]{1,15})\)")
_UNIT_PRESERVING = (
    exp.Round,
    exp.Sum,
    exp.Avg,
    exp.Min,
    exp.Max,
    exp.Abs,
    exp.Cast,
    exp.Paren,
    exp.Window,
)
MAX_DEPTH = 10


def unit_from_comment(comment: str | None) -> str | None:
    found = _UNIT.findall(comment or "")
    return found[-1] if found else None


def _source_column(expression: exp.Expr) -> exp.Column | None:
    """The single column `expression` is a unit-preserving function of, if any."""
    while isinstance(expression, (exp.Alias, *_UNIT_PRESERVING)):
        expression = expression.this
    return expression if isinstance(expression, exp.Column) else None


Units = dict[tuple[str, str, str], str]  # (schema, table, column) -> unit


def _table_unit(table: exp.Table, column: str, units: Units, schemas: dict[str, set[str]]) -> str | None:
    schema = table.db.lower()
    if not schema:  # unqualified: resolve when only one schema has a table of that name
        candidates = schemas.get(table.name.lower(), set())
        if len(candidates) != 1:
            return None
        schema = next(iter(candidates))
    return units.get((schema, table.name.lower(), column.lower()))


def _unit_of(
    expression: exp.Expr, scope: Scope, units: Units, schemas: dict[str, set[str]], depth: int
) -> str | None:
    column = _source_column(expression)
    if column is None or depth > MAX_DEPTH:
        return None
    source = scope.sources.get(column.table)
    if isinstance(source, exp.Table):
        return _table_unit(source, column.name, units, schemas)
    if isinstance(source, Scope) and isinstance(source.expression, exp.Select):
        for projection in source.expression.expressions:
            if projection.alias_or_name == column.name:
                return _unit_of(projection, source, units, schemas, depth + 1)
    return None


def column_units(sql: str, profile: DatabaseProfile, dialect: str) -> list[str | None]:
    """The unit of each output column, by position (the database names unaliased expressions
    itself, e.g. `avg`), or None where it is not known. [] when the query cannot be traced."""
    units: Units = {
        (table.schema_name.lower(), table.name.lower(), column.name.lower()): unit
        for table in profile.tables
        for column in table.columns
        if (unit := unit_from_comment(column.comment)) is not None
    }
    if not units:
        return []
    schemas: dict[str, set[str]] = {}
    for table in profile.tables:
        schemas.setdefault(table.name.lower(), set()).add(table.schema_name.lower())
    try:
        tree: exp.Expr = qualify(
            exp.maybe_parse(sql, dialect=dialect),
            schema=profile_schema(profile, dialect),
            dialect=dialect,
            quote_identifiers=False,
        )
        root = build_scope(tree)
    except SqlglotError:
        return []
    if root is None or not isinstance(root.expression, exp.Select):
        return []  # e.g. UNION: the branches may disagree
    return [_unit_of(projection, root, units, schemas, 0) for projection in root.expression.expressions]

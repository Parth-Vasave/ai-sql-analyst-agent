"""Bounded, reproducible AST-generated properties; no database or LLM is used."""

from __future__ import annotations

import pytest
import sqlglot
from hypothesis import example, given, seed, settings
from hypothesis import strategies as st
from sqlglot import exp

from app.agent.sql_validator import RejectionCode, SQLRejectedError, validate_sql
from app.database.profile import ColumnProfile, DatabaseProfile, SamplingMode, TableProfile

PROFILE = DatabaseProfile(
    database_id="property-tests",
    dialect="postgres",
    sampling=SamplingMode.OFF,
    fingerprint="synthetic",
    tables=[
        TableProfile(
            schema_name="public",
            name="measurements",
            kind="table",
            columns=[
                ColumnProfile(name="id", type="INTEGER", nullable=False),
                ColumnProfile(name="value", type="INTEGER", nullable=True),
                ColumnProfile(name="secret", type="TEXT", nullable=True, sensitive=True),
            ],
        )
    ],
    relationships=[],
)

# These decorators also apply when CI runs the complete backend suite. Keep the example budget,
# input size and AST depth bounded; disable Hypothesis's example database to avoid cached inputs.
PROPERTY_SETTINGS = settings(max_examples=50, deadline=None, database=None)
PROPERTY_SEED = 20261005


def _wrap(query: exp.Query, kind: str, alias: str) -> exp.Query:
    if kind == "cte":
        return exp.select(exp.column("result", table=alias)).from_(alias).with_(alias, as_=query)
    return exp.select(exp.column("result", table=alias)).from_(query.subquery(alias))


@st.composite
def read_queries(draw: st.DrawFn) -> exp.Query:
    table = "public.measurements" if draw(st.booleans()) else "measurements"
    column = draw(st.sampled_from(["id", "value"]))
    query: exp.Query = exp.select(exp.column(column, table="m").as_("result")).from_(
        exp.to_table(table).as_("m")
    )
    if draw(st.booleans()):
        query = query.where(
            exp.GTE(
                this=exp.column("id", table="m"), expression=exp.Literal.number(draw(st.integers(-10, 10)))
            )
        )
    if draw(st.booleans()):
        query = query.union(query.copy(), distinct=draw(st.booleans()))
    for depth in range(draw(st.integers(0, 2))):
        # An inner LIMIT is independent of the row cap that must be enforced at the outer root.
        if draw(st.booleans()):
            query = query.limit(draw(st.integers(0, 2000)))
        query = _wrap(query, draw(st.sampled_from(["cte", "subquery"])), f"q{depth}")
    limit = draw(st.one_of(st.none(), st.sampled_from([0, 1, 999, 1000, 1001]), st.integers(0, 2000)))
    if limit is not None:
        if draw(st.booleans()):
            query.set("limit", exp.Fetch(direction="FIRST", count=exp.Literal.number(limit)))
        else:
            query = query.limit(limit)
    return query


def _outer_limit(sql: str) -> int:
    statements = sqlglot.parse(sql, read="postgres")
    assert len(statements) == 1
    tree = statements[0]
    assert isinstance(tree, (exp.Select, exp.SetOperation))
    limit = tree.args.get("limit")
    assert isinstance(limit, (exp.Limit, exp.Fetch))
    value = limit.args.get("count") if isinstance(limit, exp.Fetch) else limit.expression
    assert isinstance(value, exp.Literal) and value.is_int
    return int(value.this)


@seed(PROPERTY_SEED)
@PROPERTY_SETTINGS
@given(query=read_queries(), max_rows=st.integers(1, 1000))
def test_accepted_queries_have_bounded_outer_limit(query: exp.Query, max_rows: int) -> None:
    original_sql = query.sql(dialect="postgres")
    requested = _outer_limit(original_sql) if query.args.get("limit") is not None else None
    validated = validate_sql(original_sql, PROFILE, "postgres", max_rows)
    limit = _outer_limit(validated.sql)
    assert 0 <= limit <= max_rows
    assert limit == (max_rows if requested is None else min(requested, max_rows))
    expected_action = "added" if requested is None else ("clamped" if requested > max_rows else "kept")
    assert validated.limit_action == expected_action
    assert limit == validated.limit
    assert validated.tables == ["public.measurements"]


@seed(PROPERTY_SEED)
@PROPERTY_SETTINGS
@given(query=read_queries(), max_rows=st.integers(1, 1000))
def test_regenerated_sql_is_idempotent(query: exp.Query, max_rows: int) -> None:
    first = validate_sql(query.sql(dialect="postgres"), PROFILE, "postgres", max_rows)
    second = validate_sql(first.sql, PROFILE, "postgres", max_rows)
    assert second.sql == first.sql
    assert second.tables == first.tables
    assert second.limit == first.limit
    # limit_action intentionally changes from added/clamped to kept on the second validation.
    assert second.limit_action == "kept"


@pytest.mark.parametrize(
    "category",
    ["write", "ddl", "function", "system_table", "unknown_table", "unknown_column", "sensitive_column"],
)
@seed(PROPERTY_SEED)
@PROPERTY_SETTINGS
@given(data=st.data(), depth=st.integers(0, 2))
def test_unsafe_nodes_are_rejected(category: str, data: st.DataObject, depth: int) -> None:
    expected = RejectionCode.NOT_SELECT
    if category == "ddl":
        # DDL is a top-level statement, not a legal PostgreSQL CTE or subquery body.
        query: exp.Expr = data.draw(
            st.sampled_from(
                [
                    exp.Drop(tables=[exp.to_table("public.measurements")], kind="TABLE"),
                    exp.Create(
                        this=exp.to_table("unprofiled"),
                        kind="TABLE",
                        expression=exp.select("id").from_("public.measurements"),
                    ),
                ]
            )
        ).copy()
    elif category == "write":
        returning = exp.Returning(expressions=[exp.column("id").as_("result")])
        query = data.draw(
            st.sampled_from(
                [
                    exp.Delete(this=exp.to_table("public.measurements"), returning=returning.copy()),
                    exp.Update(
                        this=exp.to_table("public.measurements"),
                        expressions=[exp.EQ(this=exp.column("value"), expression=exp.Literal.number(1))],
                        returning=returning.copy(),
                    ),
                    exp.Insert(
                        this=exp.Schema(
                            this=exp.to_table("public.measurements"), expressions=[exp.to_identifier("id")]
                        ),
                        expression=exp.select(exp.Literal.number(1)),
                        returning=returning.copy(),
                    ),
                ]
            )
        ).copy()
        if depth:
            # Unlike DDL, a data-modifying statement can be hidden inside a valid PostgreSQL CTE.
            query = exp.select("result").from_("changed").with_("changed", as_=query)
            expected = RejectionCode.FORBIDDEN_OPERATION
            for level in range(depth - 1):
                query = _wrap(query, data.draw(st.sampled_from(["cte", "subquery"])), f"q{level}")
    else:
        projection: exp.Expr = exp.Literal.number(1)
        table = "public.measurements"
        if category == "function":
            name = data.draw(st.sampled_from(["pg_sleep", "lo_export", "dblink", "current_setting"]))
            if data.draw(st.booleans()):
                name = name.upper()
            projection = exp.Anonymous(this=name, expressions=[exp.Literal.number(1)])
            expected = RejectionCode.FORBIDDEN_FUNCTION
        elif category == "system_table":
            table = data.draw(
                st.sampled_from(["pg_catalog.pg_class", "information_schema.tables", "pg_roles"])
            )
            expected = RejectionCode.SYSTEM_TABLE
        elif category == "unknown_table":
            table = data.draw(st.sampled_from(["unprofiled", "public.unprofiled", "other.measurements"]))
            expected = RejectionCode.UNKNOWN_TABLE
        elif category == "unknown_column":
            projection = exp.column(data.draw(st.sampled_from(["missing", "not_profiled"])), table="m")
            expected = RejectionCode.UNKNOWN_COLUMN
        else:
            projection = exp.column("secret", table="m")
            expected = RejectionCode.UNKNOWN_COLUMN
        query = exp.select(projection.as_("result")).from_(exp.to_table(table).as_("m"))
        for level in range(depth):
            query = _wrap(query, data.draw(st.sampled_from(["cte", "subquery"])), f"q{level}")

    with pytest.raises(SQLRejectedError) as info:
        validate_sql(query.sql(dialect="postgres"), PROFILE, "postgres", 1000)
    assert info.value.code == expected


@seed(PROPERTY_SEED)
@PROPERTY_SETTINGS
@given(sql=st.text(max_size=256))
@example(sql="")
@example(sql="SELECT 1")
@example(sql="SELECT 1; SELECT 2")
@example(sql="SELECT (")
def test_arbitrary_text_only_returns_or_rejects(sql: str) -> None:
    try:
        validated = validate_sql(sql, PROFILE, "postgres", 1000)
    except SQLRejectedError as exc:
        assert isinstance(exc.code, RejectionCode)
    else:
        assert _outer_limit(validated.sql) == validated.limit <= 1000

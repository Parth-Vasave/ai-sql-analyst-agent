"""Data model of a database profile: what the agent knows about a connected database."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class SamplingMode(StrEnum):
    """How much actual data the profiler may read (and later send to the LLM).

    off:  structure only (names, types, comments, keys).
    safe: + min/max of numeric and date columns, and the distinct values of short
          categorical text columns. Never free text, never sensitive-looking columns.
    full: + a few truncated example values from other text columns (still never sensitive ones).
    """

    OFF = "off"
    SAFE = "safe"
    FULL = "full"


class ValueHints(BaseModel):
    null_fraction: float | None = None
    min: Any = None
    max: Any = None
    categories: list[str] | None = None  # complete list of distinct values (small categorical columns)
    examples: list[str] | None = None  # a few truncated examples (full mode only)


class ColumnProfile(BaseModel):
    name: str
    type: str
    nullable: bool
    comment: str | None = None
    primary_key: bool = False
    sensitive: bool = False
    hints: ValueHints | None = None


class Relationship(BaseModel):
    from_table: str
    from_columns: list[str]
    to_table: str
    to_columns: list[str]
    inferred: bool = False  # True when guessed from column names rather than a foreign key


class TableProfile(BaseModel):
    schema_name: str
    name: str
    kind: str  # "table" | "view"
    comment: str | None = None
    estimated_rows: int | None = None
    columns: list[ColumnProfile]

    @property
    def qualified_name(self) -> str:
        return f"{self.schema_name}.{self.name}"


class DatabaseProfile(BaseModel):
    database_id: str
    dialect: str
    sampling: SamplingMode
    fingerprint: str
    tables: list[TableProfile]
    relationships: list[Relationship]
    notes: list[str] = []  # e.g. tables skipped because sampling timed out

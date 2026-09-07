"""The rules that keep a mapping honest, because the engine will not.

Every rule here exists because the engine accepts the violation without complaint. Two of
them accept it and then corrupt data quietly. Conventions section 1.4, ADR 0004.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from adss.names import Schema

# An attribute expression may read its own row: a column, a cast of one, or a CASE over
# them. Anything else is a join, and every join must come from a declared relationship.
_REACHING = re.compile(r"\b(select|join|from|over|group\s+by)\b", re.IGNORECASE)
_AGGREGATE = re.compile(r"\b(sum|count|min|max|avg|any_value|array_agg)\s*\(", re.IGNORECASE)

REQUIRED_STRATEGY = "FULL_LOG"
REQUIRED_CLOCK = "extracted_at"


class MappingError(Exception):
    """A mapping the engine would accept and should not."""


@dataclass(frozen=True, slots=True)
class Table:
    """One source table an entity is loaded from."""

    table: str
    primary_keys: tuple[str, ...]
    ingestion_strategy: str
    effective_timestamp_expression: str
    expressions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Mapping:
    """How one entity is loaded."""

    path: Path
    entity_id: str
    tables: tuple[Table, ...]


def read_mapping(path: Path) -> Mapping:
    document = yaml.safe_load(path.read_text())
    tables = [
        Table(
            table=str(table["table"]),
            primary_keys=tuple(table.get("primary_keys", [])),
            ingestion_strategy=str(table.get("ingestion_strategy", "")),
            effective_timestamp_expression=str(
                table.get("entity_effective_timestamp_expression", "")
            ),
            expressions=tuple(
                str(attribute["transformation_expression"])
                for attribute in table.get("attributes", [])
            ),
        )
        for group in document["mapping_groups"]
        for table in group["tables"]
    ]
    return Mapping(path=path, entity_id=str(document["entity_id"]), tables=tuple(tables))


def check_mapping(mapping: Mapping) -> None:
    """Refuse what M1-M5 and M7 refuse, naming the rule that refused it.

    M6 is about relationships and lands with the first one. M2 is checked for cardinality
    here; its key-shape clause -- a concat without a separator collapses 'A1' + '23' and
    'A12' + '3' into one key -- is review-only until there is a composite key to check.
    """
    where = mapping.path.name
    for table in mapping.tables:
        if not table.table.startswith(f"{Schema.DAS_STAGED}."):
            raise MappingError(
                f"{where}: M1 -- a mapping reads a {Schema.DAS_STAGED} object and nothing "
                f"else, never {table.table!r}. Reading the raw layer skips the contract's "
                f"casts, and a join here is business logic in the wrong layer."
            )
        if len(table.primary_keys) != 1:
            raise MappingError(
                f"{where}: M2 -- exactly one primary key. {list(table.primary_keys)} is read "
                f"as that many alternate identifiers, not as a composite key, and that mode "
                f"cannot be undone once loaded."
            )
        if table.ingestion_strategy != REQUIRED_STRATEGY:
            raise MappingError(
                f"{where}: M3 -- {REQUIRED_STRATEGY}, not {table.ingestion_strategy!r}. "
                f"FULL against a source holding more than one row per key inserts a "
                f"duplicate on every run, forever, and every presentation view hides it."
            )
        if table.effective_timestamp_expression != REQUIRED_CLOCK:
            raise MappingError(
                f"{where}: M4 -- a version is dated by {REQUIRED_CLOCK}, not "
                f"{table.effective_timestamp_expression!r}. The effective time of a fact is "
                f"when the system observed it; anything else dates it by something that is "
                f"not about the fact."
            )
        for expression in table.expressions:
            if _REACHING.search(expression) or _AGGREGATE.search(expression):
                raise MappingError(
                    f"{where}: M5 -- {expression!r} reaches beyond its row. An expression "
                    f"that does is a join, and every join comes from a declared relationship."
                )
        if not table.expressions:
            raise MappingError(
                f"{where}: M7 -- every mapped table carries at least one attribute. The "
                f"engine refuses an entity with none, at deploy rather than at review."
            )

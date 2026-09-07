"""The rules that keep a mapping honest, because the engine will not.

Every rule here exists because the engine accepts the violation without complaint. Two of
them accept it and then corrupt data quietly. Conventions section 1.4, ADR 0004.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from adss.model import Model
from adss.names import Schema

# An attribute expression may read its own row: a column, a cast of one, or a CASE over
# them. Anything else is a join, and every join must come from a declared relationship.
_REACHING = re.compile(r"\b(select|join|from|over|group\s+by)\b", re.IGNORECASE)
_AGGREGATE = re.compile(r"\b(sum|count|min|max|avg|any_value|array_agg)\s*\(", re.IGNORECASE)

# A key expression is compared by shape, not by spelling: only the casting decides what
# VARCHAR the two sides of an edge produce. Everything not a type or an operator is a name.
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
_LITERAL = re.compile(r"'[^']*'")
_SHAPE_WORDS = frozenset(
    {
        "cast",
        "as",
        "concat",
        "coalesce",
        "varchar",
        "char",
        "text",
        "string",
        "integer",
        "int",
        "bigint",
        "smallint",
        "tinyint",
        "hugeint",
        "decimal",
        "numeric",
        "double",
        "real",
        "float",
        "date",
        "timestamp",
        "boolean",
        "uuid",
    }
)

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
class Relationship:
    """One declared edge, as the mapping spells it."""

    id: str
    source_table: str
    target_expression: str


@dataclass(frozen=True, slots=True)
class Mapping:
    """How one entity is loaded."""

    path: Path
    entity_id: str
    tables: tuple[Table, ...]
    relationships: tuple[Relationship, ...] = ()


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
    relationships = [
        Relationship(
            id=str(declared["id"]),
            source_table=str(declared["source_table"]),
            target_expression=str(declared["target_transformation_expression"]),
        )
        for group in document["mapping_groups"]
        for declared in group.get("relationships", [])
    ]
    return Mapping(
        path=path,
        entity_id=str(document["entity_id"]),
        tables=tuple(tables),
        relationships=tuple(relationships),
    )


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


def key_shape(expression: str) -> str:
    """A key expression with its column names removed, which is what M6 compares.

    M6 asks that a relationship's target expression mirror the target entity's own key
    expression. It is the *shape* that has to match, not the spelling: a foreign key column is
    routinely named differently from the primary key it points at. What must not differ is the
    casting, because that is what decides the VARCHAR the two sides produce -- a bare column on
    one side and a cast on the other join to nothing at all.
    """
    parts: list[str] = []
    last = 0
    for literal in _LITERAL.finditer(expression):
        # A separator inside a concat is part of the shape and survives verbatim: 'A1' + '23'
        # and 'A12' + '3' are one key without it.
        parts.append(_without_names(expression[last : literal.start()]))
        parts.append(literal.group(0))
        last = literal.end()
    parts.append(_without_names(expression[last:]))
    return " ".join("".join(parts).split())


def _without_names(fragment: str) -> str:
    def anonymous(word: re.Match[str]) -> str:
        found = word.group(0).lower()
        return found if found in _SHAPE_WORDS else "?"

    return _IDENTIFIER.sub(anonymous, fragment)


def check_relationships(mappings: Sequence[Mapping], model: Model) -> None:
    """Refuse what M6 refuses. Every one of its failures is silent in the built warehouse.

    A mis-spelled `source_table` is skipped by the engine without a word, a differently shaped
    target expression makes pairs that join to nothing, and an edge no mapping loads makes no
    pairs at all. All three show up as an inherited key that is null everywhere, which reads
    as data rather than as a defect. ADR 0006.
    """
    loaded = {edge.id: (mapping, edge) for mapping in mappings for edge in mapping.relationships}
    modelled = {edge.id: edge for edge in model.relationships}

    for edge_id in modelled:
        if edge_id not in loaded:
            raise MappingError(
                f"M6 -- {model.path.name} declares {edge_id} and no mapping loads it. The "
                f"engine builds no pair object at all, so every join along that edge returns "
                f"null, which reads as 'these rows have no target' rather than as a gap."
            )

    for edge_id, (mapping, edge) in loaded.items():
        where = mapping.path.name
        if edge_id not in modelled:
            expected = [candidate.id for candidate in model.edges_from(mapping.entity_id)]
            raise MappingError(
                f"{where}: M6 -- {edge_id} is not an edge {model.path.name} declares. An id "
                f"is <SRC>_<NAME>_<TGT>, so {mapping.entity_id} can load {expected or 'none'}. "
                f"The engine would build this pair object from the mapping alone: it would "
                f"work, and be an edge nothing explains."
            )
        declared = modelled[edge_id]
        if mapping.entity_id != declared.source_entity_id:
            raise MappingError(
                f"{where}: M6 -- {edge_id} runs from {declared.source_entity_id}, and this "
                f"mapping loads {mapping.entity_id}. An edge is declared by the entity it "
                f"runs from, because that is the row the target expression reads."
            )
        tables = {table.table for table in mapping.tables}
        if edge.source_table not in tables:
            raise MappingError(
                f"{where}: M6 -- {edge_id} names source_table {edge.source_table!r}, which is "
                f"not byte-identical to any table in its group ({sorted(tables)}). The engine "
                f"skips a relationship whose source_table it cannot match, in silence, and "
                f"the inherited key is then null on every row."
            )
        target = next((one for one in mappings if one.entity_id == declared.target_entity_id), None)
        if target is None:
            raise MappingError(
                f"{where}: M6 -- {edge_id} points at {declared.target_entity_id}, which no "
                f"mapping loads. There is nothing for the pairs to join to."
            )
        keys = {key_shape(key) for table in target.tables for key in table.primary_keys}
        if key_shape(edge.target_expression) not in keys:
            raise MappingError(
                f"{where}: M6 -- {edge_id} targets {edge.target_expression!r}, which is not "
                f"shaped like {declared.target_entity_id}'s own key ({sorted(keys)} with the "
                f"names taken out). The column may be named anything; the casting may not "
                f"differ, because a bare column and a cast produce different keys and the "
                f"pairs then join to nothing."
            )

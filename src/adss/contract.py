"""A contract: what a source sends, what it is called here, and what type it becomes.

The contract is the whole of the DAS layer's knowledge. It is documentation, schema and
transformation at once, so there is nothing beside it that can drift from it -- and it is
deliberately incapable of expressing business logic, because the layer it governs is
forbidden to contain any. ADR 0003.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml


class ContractError(Exception):
    """A contract that would compile but should not exist."""


class ColumnType(StrEnum):
    """The closed vocabulary a contract may declare.

    Closed on purpose: this is the dictionary where staging decisions accumulate, and a type
    that is not here is a decision nobody has made yet.
    """

    STRING = "STRING"
    INTEGER = "INTEGER"
    BIGINT = "BIGINT"
    DOUBLE = "DOUBLE"
    DECIMAL = "DECIMAL"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    TIMESTAMP = "TIMESTAMP"
    JSON = "JSON"


# Keys that would let a contract carry an interpretation. Blueprint S1 forbids one, and the
# cheapest way to keep the format honest is to refuse the vocabulary outright.
_FORBIDDEN_KEYS = frozenset(
    {"expression", "sql", "filter", "where", "join", "default", "coalesce", "case"}
)


@dataclass(frozen=True, slots=True)
class Column:
    """One declared column: where it comes from in the payload, and what it becomes."""

    source_path: str
    target_name: str
    type: ColumnType
    required: bool
    description: str
    precision: int | None = None
    scale: int | None = None

    @property
    def sql_type(self) -> str:
        if self.type is ColumnType.DECIMAL:
            return f"DECIMAL({self.precision}, {self.scale})"
        return str(self.type)


@dataclass(frozen=True, slots=True)
class Endpoint:
    """Where the records come from. Read by the pipeline; never by anything downstream."""

    provider: str
    service: str
    entity: str
    page_size: int

    @property
    def url(self) -> str:
        return f"{self.service.rstrip('/')}/{self.entity}"


@dataclass(frozen=True, slots=True)
class Contract:
    """One source entity set, landed under one name."""

    table: str
    source: Endpoint
    primary_keys: tuple[str, ...]
    columns: tuple[Column, ...]

    def column(self, target_name: str) -> Column:
        for column in self.columns:
            if column.target_name == target_name:
                return column
        raise ContractError(f"{self.table}: no column named {target_name!r}")


def snake_case(name: str) -> str:
    """The mechanical translation of a source's own word. Not a rename. Conventions 1.1."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", name)
    return spaced.replace("-", "_").replace(" ", "_").lower()


def _parse_type(raw: str, table: str, target_name: str) -> ColumnType:
    try:
        return ColumnType(raw.strip())
    except ValueError:
        raise ContractError(
            f"{table}.{target_name}: type {raw!r} is not in the vocabulary "
            f"({', '.join(sorted(ColumnType.__members__))})"
        ) from None


def _refuse_forbidden_keys(node: object, table: str) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ContractError(
                    f"{table}: key {key!r} would let this contract carry business logic, "
                    f"which belongs in the layer that explains the data, not the one that "
                    f"records what arrived"
                )
            _refuse_forbidden_keys(value, table)
    elif isinstance(node, list):
        for item in node:
            _refuse_forbidden_keys(item, table)


def read_contract(path: Path) -> Contract:
    """Read one contract, refusing anything that would compile but should not exist."""
    table = path.stem
    document = yaml.safe_load(path.read_text())
    _refuse_forbidden_keys(document, table)
    declared_schema = document["schema"]
    endpoint = document["endpoints"]["source"]

    columns: list[Column] = []
    for declared in declared_schema["columns"]:
        source_path = declared["source_path"]
        target_name = declared["target_name"]
        if target_name != snake_case(source_path.rsplit(".", 1)[-1]):
            raise ContractError(
                f"{table}.{target_name}: a target name is the mechanical snake_case of its "
                f"source path, never a rename -- expected "
                f"{snake_case(source_path.rsplit('.', 1)[-1])!r}"
            )
        column_type = _parse_type(str(declared["type"]), table, target_name)
        precision, scale = declared.get("precision"), declared.get("scale")
        if column_type is ColumnType.DECIMAL and (precision is None or scale is None):
            raise ContractError(
                f"{table}.{target_name}: DECIMAL declares precision and scale as their own "
                f"keys. A parenthesised type is split by the comma inside a flow mapping."
            )
        columns.append(
            Column(
                source_path=source_path,
                target_name=target_name,
                type=column_type,
                required=declared["mode"] == "REQUIRED",
                description=str(declared["description"]),
                precision=precision,
                scale=scale,
            )
        )

    from adss.das import RESERVED

    seen: set[str] = set()
    for column in columns:
        if column.target_name in seen:
            raise ContractError(
                f"{table}: two columns both land as {column.target_name!r}. The warehouse "
                f"does not refuse that -- it renames the second and the first one's values "
                f"are what everything downstream reads."
            )
        if column.target_name in RESERVED:
            raise ContractError(
                f"{table}: {column.target_name!r} is a name this layer adds itself "
                f"({', '.join(sorted(RESERVED))}). A source field landing under it would "
                f"silently displace the provenance that says where the row came from."
            )
        seen.add(column.target_name)

    declared_names = {column.target_name for column in columns}
    primary_keys = tuple(declared_schema["primary_keys"])
    dangling = [key for key in primary_keys if key not in declared_names]
    if dangling:
        raise ContractError(
            f"{table}: dangling primary key {dangling!r} -- a key must name a declared column"
        )

    return Contract(
        table=table,
        source=Endpoint(
            provider=str(endpoint["provider"]),
            service=str(endpoint["service"]),
            entity=str(endpoint["entity"]),
            page_size=int(endpoint["page_size"]),
        ),
        primary_keys=primary_keys,
        columns=tuple(columns),
    )

"""DAS in SQL: a forgiving view over what landed, and a strict view over what was declared.

Nothing here interprets. A cast records what the source's own metadata says a field is; the
format has no way to express anything more, which is what keeps the layer honest. ADR 0003.
"""

from __future__ import annotations

from pathlib import Path

from adss.contract import ColumnType, Contract
from adss.names import Relation, Schema

# The provenance this layer adds itself, named for what it records rather than for whoever
# wrote it. Blueprint S4.
PROVENANCE = ("source_system", "source_entity", "source_url")

# Every name this layer adds for itself. A contract may not land a source field under one:
# the warehouse would silently rename the duplicate rather than refuse it.
RESERVED = frozenset({*PROVENANCE, "payload", "extracted_at", "extracted_on"})

_GENERATED = "-- Generated from das/contracts/{table}.yaml. Do not edit; edit the contract."


def _extract(column_type: ColumnType, source_path: str, sql_type: str) -> str:
    """The one expression per type. This dictionary is where staging decisions accumulate."""
    path = f"'$.{source_path}'"
    if column_type is ColumnType.STRING:
        return f"landed.payload ->> {path}"
    if column_type is ColumnType.JSON:
        return f"landed.payload -> {path}"
    return f"cast(landed.payload ->> {path} AS {sql_type})"


def raw_view_sql(contract: Contract, lake: Path) -> str:
    """One view per contract over the append-only hive-partitioned lake.

    Both read options are correctness rather than taste: without union_by_name a column that
    appears only in later loads is silently dropped, and without hive_types the partition key
    comes back as text.
    """
    relation = Relation(Schema.DAS_RAW, contract.table)
    glob = lake / contract.table / "extracted_on=*" / "*.parquet"
    landed = ["payload", *PROVENANCE, "extracted_on", "_dlt_load_id", "_dlt_id"]
    selected = ",\n".join(f"    landed.{name} AS {name}" for name in landed)
    return (
        f"{_GENERATED.format(table=contract.table)}\n"
        f"CREATE OR REPLACE VIEW {relation.sql} AS\n"
        f"SELECT\n{selected}\n"
        f"FROM read_parquet(\n"
        f"    '{glob}',\n"
        f"    hive_partitioning => true,\n"
        f"    hive_types => {{ 'extracted_on': 'DATE' }},\n"
        f"    union_by_name => true\n"
        f") AS landed;\n"
    )


def staged_view_sql(contract: Contract) -> str:
    """The change log: one row per source record per load, strictly typed.

    The payload is deliberately absent. If it were here a downstream mapping could read
    straight out of it and the contract would stop being the gate.
    """
    relation = Relation(Schema.DAS_STAGED, contract.table)
    lines = [
        f"    {_extract(column.type, column.source_path, column.sql_type)} AS {column.target_name}"
        for column in contract.columns
    ]
    lines += [f"    landed.{name} AS {name}" for name in PROVENANCE]
    lines.append("    to_timestamp(cast(landed._dlt_load_id AS DOUBLE)) AS extracted_at")
    lines.append("    landed.extracted_on AS extracted_on")
    selected = ",\n".join(lines)
    return (
        f"{_GENERATED.format(table=contract.table)}\n"
        f"CREATE OR REPLACE VIEW {relation.sql} AS\n"
        f"SELECT\n{selected}\n"
        f"FROM {Relation(Schema.DAS_RAW, contract.table).sql} AS landed;\n"
    )


def current_view_sql(contract: Contract) -> str:
    """One row per key, from the latest load that carried it.

    A question asked of the source needs one row per thing, not one per observation. The
    change log beside it is what DAB historizes from.
    """
    relation = Relation(Schema.DAS_STAGED, f"{contract.table}__current")
    names = [column.target_name for column in contract.columns]
    names += [*PROVENANCE, "extracted_at", "extracted_on"]
    selected = ",\n".join(f"    staged.{name} AS {name}" for name in names)
    partition = ", ".join(f"staged.{key}" for key in contract.primary_keys)
    return (
        f"{_GENERATED.format(table=contract.table)}\n"
        f"CREATE OR REPLACE VIEW {relation.sql} AS\n"
        f"SELECT\n{selected}\n"
        f"FROM {Relation(Schema.DAS_STAGED, contract.table).sql} AS staged\n"
        f"QUALIFY row_number() OVER (\n"
        f"    PARTITION BY {partition}\n"
        f"    ORDER BY staged.extracted_at DESC\n"
        f") = 1;\n"
    )


def lake_dir(root: Path) -> Path:
    """Where the landing zone actually sits under the lake root.

    The loader writes its dataset name into the path, and the dataset name is the schema.
    """
    return root / str(Schema.DAS_RAW)


def clock_check_sql(contract: Contract) -> str:
    """The partition key and the observation clock derive from one fact and must agree.

    The comparison is pinned to UTC. `extracted_at` is a TIMESTAMP WITH TIME ZONE, so casting
    it to a date resolves in the reader's session timezone, while the partition key is the
    loader's UTC date -- and the check would then fail on every machine east or west of
    Greenwich for a warehouse that is perfectly correct.

    Emitted per contract rather than written in Python: the machinery must work for any
    source, so it may not name one, and SQL in a string is SQL the linter never sees.
    """
    relation = Relation(Schema.DAS_STAGED, contract.table)
    return (
        f"{_GENERATED.format(table=contract.table)}\n"
        f"SELECT count(*) AS disagreements\n"
        f"FROM {relation.sql} AS staged\n"
        f"WHERE staged.extracted_on <> cast(timezone('UTC', staged.extracted_at) AS DATE);\n"
    )


def key_check_sql(contract: Contract) -> str:
    """One row per key in the current view, however many loads the change log holds."""
    current = Relation(Schema.DAS_STAGED, f"{contract.table}__current")
    # Parenthesised: count(DISTINCT a, b) is not a function DuckDB has, so a composite key
    # would emit a check that cannot run -- and an unrunnable check aborts the whole run
    # before any finding is printed.
    keys = ", ".join(f"latest.{key}" for key in contract.primary_keys)
    return (
        f"{_GENERATED.format(table=contract.table)}\n"
        f"SELECT count(*) - count(DISTINCT ({keys})) AS duplicates\n"
        f"FROM {current.sql} AS latest;\n"
    )

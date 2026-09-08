"""Record, land, unpack, query -- the whole DAS layer, over a stand-in service.

Still a machinery test: the service is a fake and the lake is built here. What the real
warehouse holds is asserted by checks/. Conventions section 6.
"""

from pathlib import Path

import duckdb
import pytest

from adss.contract import read_contract
from adss.das import current_view_sql, lake_dir, raw_view_sql, staged_view_sql
from adss.landing import land, observation
from adss.source import record, replay
from support import Responder

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"

# What the fixture hands a test: an open connection with the views installed, the lake root
# they read, and the recording the load came from.
Landed = tuple[duckdb.DuckDBPyConnection, Path, Path]


@pytest.fixture
def landed(tmp_path: Path) -> Landed:
    contract = read_contract(FIXTURES / "parent.yaml")
    recording = tmp_path / "recording"
    record(contract.source, Responder(total=5), recording)

    root, pipelines = tmp_path / "lake", tmp_path / "pipelines"
    land(contract, replay(recording), root, pipelines, observation())

    connection = duckdb.connect()
    connection.execute("CREATE SCHEMA das__raw; CREATE SCHEMA das__staged;")
    for sql in (
        raw_view_sql(contract, lake_dir(root)),
        staged_view_sql(contract),
        current_view_sql(contract),
    ):
        connection.execute(sql)
    return connection, root, recording


def count(connection: duckdb.DuckDBPyConnection, relation: str) -> int:
    row = connection.execute(f"SELECT count(*) FROM {relation}").fetchone()
    assert row is not None
    return int(row[0])


def test_the_lake_is_partitioned_by_the_day_the_load_ran(landed: Landed):
    _, root, _ = landed
    partitions = list(lake_dir(root).glob("parent/extracted_on=*"))
    assert len(partitions) == 1
    assert partitions[0].name.startswith("extracted_on=20")


def test_the_schema_name_survives_the_loader(landed: Landed):
    _, root, _ = landed
    assert lake_dir(root).is_dir(), "das__raw is normalised to das_raw unless that is disabled"


def test_every_landed_record_is_readable_through_the_contract(landed: Landed):
    connection, _, _ = landed
    assert count(connection, "das__raw.parent") == 5
    assert count(connection, "das__staged.parent") == 5
    assert count(connection, "das__staged.parent__current") == 5


def test_the_payload_is_one_column_and_nothing_was_split_out_of_it(landed: Landed):
    connection, _, _ = landed
    described = connection.execute("DESCRIBE das__raw.parent").fetchall()
    names = {name for name, *_ in described}
    assert "payload" in names
    assert not any(name.startswith("parent_") for name in names), (
        "a column named after a payload field means the loader inferred a schema"
    )


def test_the_row_carries_where_it_came_from(landed: Landed):
    connection, _, _ = landed
    row = connection.execute(
        "SELECT source_system, source_entity, source_url FROM das__staged.parent LIMIT 1"
    ).fetchone()
    assert row is not None
    system, entity, url = row
    assert entity == "Parent"
    assert system in url and entity in url


def test_a_second_load_appends_rather_than_replacing(landed: Landed, tmp_path: Path):
    connection, root, recording = landed
    contract = read_contract(FIXTURES / "parent.yaml")
    land(contract, replay(recording), root, tmp_path / "pipelines", observation())

    assert count(connection, "das__raw.parent") == 10, "DAS is non-volatile; a load is added"
    assert count(connection, "das__staged.parent__current") == 5, "one row per key, latest load"


def test_two_contracts_landed_by_one_ingest_carry_one_observation(tmp_path: Path):
    """ADR 0013. An ingest is one observation of one source, whatever order it lands things in.

    Landed here in the order that broke slice 4 -- the child's contract first, which is what
    `sorted()` produces -- because the failure was not that the times were wrong but that they
    were two. A parent stamped a fraction of a second after the child it is joined to as of
    means no version of it precedes that child, and every inheriting row is dropped.
    """
    contracts = [read_contract(FIXTURES / name) for name in ("composite_key.yaml", "parent.yaml")]
    recording = tmp_path / "recording"
    record(contracts[0].source, Responder(total=3), recording)

    root, pipelines = tmp_path / "lake", tmp_path / "pipelines"
    observed = observation()
    for contract in contracts:
        land(contract, replay(recording), root, pipelines, observed)

    connection = duckdb.connect()
    connection.execute("CREATE SCHEMA das__raw; CREATE SCHEMA das__staged;")
    seen = {}
    for contract in contracts:
        connection.execute(raw_view_sql(contract, lake_dir(root)))
        connection.execute(staged_view_sql(contract))
        found = connection.execute(
            f"SELECT DISTINCT extracted_at FROM das__staged.{contract.table}"
        ).fetchall()
        seen[contract.table] = {row[0] for row in found}

    assert seen["composite_key"] == seen["parent"], (
        "two contracts, one ingest, one observation -- the second landed is not later than the "
        "first, however the file names happen to sort"
    )
    assert len(seen["parent"]) == 1
    connection.close()

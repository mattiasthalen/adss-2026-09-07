"""The emitted DAS SQL runs, and the change log behaves the way the layer claims.

This is a machinery test, not a data check: it asserts the emitter produces executable SQL,
using a synthetic lake it builds itself. What the real warehouse contains is asserted by
checks/, against the real build. Conventions section 6.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from adss.contract import Contract, read_contract
from adss.das import current_view_sql, raw_view_sql, staged_view_sql

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"

# What the fixture hands a test: an open connection, the lake it reads, and the contract
# whose views are installed on it.
Warehouse = tuple[duckdb.DuckDBPyConnection, Path, Contract]


def scalar(connection: duckdb.DuckDBPyConnection, sql: str) -> object:
    """One value from one row. A query that returns nothing is a broken test, not a None."""
    row = connection.execute(sql).fetchone()
    assert row is not None, sql
    return row[0]


RECORD: dict[str, object] = {
    "ParentId": 1,
    "ParentLabel": "first",
    "ParentCount": 9,
    "ParentRatio": 0.5,
    "ParentAmount": "12.3400",
    "ParentFlag": True,
    "ParentOn": "1996-07-04",
    "ParentAt": "1996-07-04T10:30:00",
    "ParentBlob": {"nested": [1, 2]},
}


LANDED_COLUMNS = (
    "payload",
    "source_system",
    "source_entity",
    "source_url",
    "_dlt_load_id",
    "_dlt_id",
)


def land(
    lake: Path, load_id: str, records: list[dict[str, object]], extra: str | None = None
) -> None:
    """Write one load, the way the pipeline lays the lake out."""
    on = datetime.fromtimestamp(float(load_id), tz=UTC).date().isoformat()
    directory = lake / "parent" / f"extracted_on={on}"
    directory.mkdir(parents=True, exist_ok=True)

    columns = [*LANDED_COLUMNS, *([extra] if extra else [])]
    connection = duckdb.connect()
    connection.execute(f"CREATE TABLE landing ({', '.join(f'{c} VARCHAR' for c in columns)})")
    connection.executemany(
        f"INSERT INTO landing VALUES ({', '.join('?' * len(columns))})",
        [
            [
                json.dumps(record),
                "probe",
                "Parent",
                "https://probe",
                load_id,
                f"{load_id}-{index}",
                *([f"later-{index}"] if extra else []),
            ]
            for index, record in enumerate(records)
        ],
    )
    connection.execute(f"COPY landing TO '{directory / f'{load_id}.parquet'}' (FORMAT PARQUET)")


@pytest.fixture
def warehouse(tmp_path: Path) -> Warehouse:
    lake = tmp_path / "lake"
    land(lake, "1788810369.25", [RECORD])
    contract = read_contract(FIXTURES / "parent.yaml")
    connection = duckdb.connect()
    connection.execute("CREATE SCHEMA das__raw; CREATE SCHEMA das__staged;")
    for sql in (
        raw_view_sql(contract, lake),
        staged_view_sql(contract),
        current_view_sql(contract),
    ):
        connection.execute(sql)
    return connection, lake, contract


def test_every_declared_column_arrives_as_its_declared_type(warehouse: Warehouse):
    connection, _, contract = warehouse
    described = connection.execute("DESCRIBE das__staged.parent").fetchall()
    types = {name: kind for name, kind, *_ in described}
    expected = {column.target_name: column.sql_type for column in contract.columns}
    for name, sql_type in expected.items():
        actual = types[name]
        assert (
            actual.replace(" ", "")
            .upper()
            .startswith(sql_type.replace(" ", "").upper().replace("STRING", "VARCHAR"))
        ), f"{name} landed as {actual}, contract declares {sql_type}"


def test_the_observation_clock_agrees_with_the_partition(warehouse: Warehouse):
    connection, _, _ = warehouse
    disagreements = scalar(
        connection,
        "SELECT count(*) FROM das__staged.parent WHERE extracted_on <> cast(extracted_at AS DATE)",
    )
    assert disagreements == 0


def test_a_second_load_extends_the_change_log_but_not_the_current_view(warehouse: Warehouse):
    connection, lake, _ = warehouse
    land(lake, "1788896769.25", [{**RECORD, "ParentLabel": "second"}])

    assert scalar(connection, "SELECT count(*) FROM das__staged.parent") == 2
    assert scalar(connection, "SELECT count(*) FROM das__staged.parent__current") == 1
    assert scalar(connection, "SELECT parent_label FROM das__staged.parent__current") == "second", (
        "the current view keeps the latest observation, not the first"
    )


def test_a_column_that_appears_only_in_a_later_load_is_not_silently_dropped(warehouse: Warehouse):
    connection, lake, _ = warehouse
    land(lake, "1788896769.25", [RECORD], extra="added_later")
    assert scalar(connection, "SELECT count(*) FROM das__raw.parent") == 2, (
        "without union_by_name the later file's rows go missing with no error"
    )

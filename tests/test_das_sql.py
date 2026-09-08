"""DAS emits a forgiving raw view and a strict staged change log. ADR 0003."""

from pathlib import Path

from adss.contract import ColumnType, read_contract
from adss.das import current_view_sql, raw_view_sql, staged_view_sql
from adss.names import Schema

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"
LAKE = Path("/somewhere/lake")


def contract():
    return read_contract(FIXTURES / "parent.yaml")


def test_the_raw_view_reads_the_lake_with_both_correctness_options():
    sql = raw_view_sql(contract(), LAKE)
    assert "union_by_name => true" in sql, "a column added by a later load is silently dropped"
    assert "hive_partitioning => true" in sql
    assert "hive_types => { 'extracted_on': 'DATE' }" in sql, "the partition key comes back VARCHAR"


def test_the_raw_view_path_is_absolute():
    sql = raw_view_sql(contract(), LAKE)
    assert "'/somewhere/lake/" in sql, "a relative path resolves at query time, not create time"


def test_the_raw_view_names_its_columns_rather_than_starring():
    assert "SELECT *" not in raw_view_sql(contract(), LAKE)


def test_every_type_in_the_vocabulary_emits_its_own_expression():
    sql = staged_view_sql(contract())
    emitted = {
        ColumnType.STRING: "payload ->> '$.ParentLabel' AS parent_label",
        ColumnType.INTEGER: "cast(landed.payload ->> '$.ParentId' AS INTEGER) AS parent_id",
        ColumnType.BIGINT: "cast(landed.payload ->> '$.ParentCount' AS BIGINT) AS parent_count",
        ColumnType.DOUBLE: "cast(landed.payload ->> '$.ParentRatio' AS DOUBLE) AS parent_ratio",
        ColumnType.DECIMAL: (
            "cast(landed.payload ->> '$.ParentAmount' AS DECIMAL(18, 4)) AS parent_amount"
        ),
        ColumnType.BOOLEAN: "cast(landed.payload ->> '$.ParentFlag' AS BOOLEAN) AS parent_flag",
        ColumnType.DATE: "cast(landed.payload ->> '$.ParentOn' AS DATE) AS parent_on",
        ColumnType.TIMESTAMP: "cast(landed.payload ->> '$.ParentAt' AS TIMESTAMP) AS parent_at",
        ColumnType.JSON: "landed.payload -> '$.ParentBlob' AS parent_blob",
    }
    assert set(emitted) == set(ColumnType), "a type with no asserted expression is untested"
    for column_type, expression in emitted.items():
        assert expression in sql, f"{column_type} emitted the wrong expression"


def test_the_staged_view_reads_the_observation_clock_the_ingest_landed():
    """ADR 0013. Derived from the loader's id it was one clock per pipeline, and there is one
    pipeline per contract -- so two entities landed by one ingest could not be compared."""
    sql = staged_view_sql(contract())
    assert "landed.extracted_at AS extracted_at" in sql
    assert "_dlt_load_id AS DOUBLE" not in sql, "the loader's clock is per pipeline, not per run"


def test_no_loader_vocabulary_is_exposed_by_the_staged_view():
    selected = staged_view_sql(contract()).split("FROM")[0]
    assert "AS _dlt_load_id" not in selected, "a loader's name in a published interface welds it in"
    assert "AS _dlt_id" not in selected


def test_the_payload_is_not_exposed_by_the_staged_view():
    selected = staged_view_sql(contract()).split("FROM")[0]
    assert "AS payload" not in selected, "an exposed payload lets a consumer bypass the contract"


def test_the_current_view_keeps_the_latest_observation_per_key():
    sql = current_view_sql(contract())
    assert f"{Schema.DAS_STAGED}.parent__current" in sql
    assert "PARTITION BY staged.parent_id" in sql
    assert "ORDER BY staged.extracted_at DESC" in sql
    assert "= 1" in sql


def test_the_current_view_carries_every_column_of_the_change_log():
    sql = current_view_sql(contract())
    for column in contract().columns:
        assert f"AS {column.target_name}" in sql

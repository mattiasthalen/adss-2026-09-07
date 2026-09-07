"""DAR is generated. Its column contract is what every consumer is written against. ADR 0002."""

import re
from pathlib import Path

import pytest

from adss.model import read_model
from adss.uss import UssError, bridge_columns, bridge_sql, calendar_sql, peripheral_sql, read_uss

FIXTURES = Path(__file__).parent / "fixtures" / "dab"


def plan():
    return read_model(FIXTURES / "model.yaml"), read_uss(FIXTURES / "uss.yaml")


def bridge() -> str:
    model, uss = plan()
    return bridge_sql(model, uss)


def branches(sql: str) -> list[str]:
    """The union's branches, without the common table expressions above them."""
    parts = sql.split("\n\nUNION ALL\n\n")
    parts[0] = parts[0][parts[0].rindex("\n\nSELECT\n") :]
    return parts


def aliases(select: str, column: str) -> int:
    return len(re.findall(rf" AS {re.escape(column)}(?=[,\n])", select))


def test_the_bridge_column_contract_is_an_order_not_a_set():
    model, uss = plan()
    assert bridge_columns(model, uss) == (
        "_stage",
        "_event",
        "_event_date",
        "_is_current",
        "_observed_at",
        "parent_key",
        "_measure__parent__happened_parents_count",
        "_measure__parent__size_parents_units",
        "_measure__parent__finished_parents_count",
    )


def test_a_count_measure_is_one_per_row_and_a_sum_measure_is_its_attribute():
    sql = bridge()
    assert "cast(1 AS BIGINT) AS _measure__parent__happened_parents_count" in sql
    assert (
        'cast(happened."PARENT_SIZE" AS DECIMAL(28, 8)) AS _measure__parent__size_parents_units'
        in sql
    )


def test_an_event_reads_the_history_view_and_keeps_the_latest_version():
    sql = bridge()
    assert 'dab."view_PARENT_hist"' in sql
    assert "row_number() OVER (" in sql
    assert "ORDER BY" in sql and "eff_tmstp DESC" in sql


def test_an_entity_with_no_date_for_the_event_has_no_row_for_it():
    assert 'happened."HAPPENED_ON" IS NOT NULL' in bridge(), (
        "an event that did not happen must be absent by construction, not by a filter "
        "somebody has to remember"
    )


def test_the_peripheral_is_one_row_per_key_with_attributes_in_declaration_order():
    model, _ = plan()
    sql = peripheral_sql(model, "PARENT")
    order = ["parent_key", "_observed_at", "parent_number", "happened_on", "parent_label"]
    positions = [sql.index(f"AS {name}") for name in order]
    assert positions == sorted(positions), "key first, then attributes as declared"
    assert "CREATE OR REPLACE TABLE dar__uss.parent" in sql


def test_a_peripheral_named_for_a_reserved_word_is_quoted_not_abbreviated():
    from adss.names import quoted

    assert quoted("order") == '"order"'
    assert quoted("parent") == "parent"


def test_the_calendar_is_dense_and_spans_what_the_bridge_holds():
    sql = calendar_sql()
    assert "min(b._event_date)" in sql and "max(b._event_date)" in sql
    assert "INTERVAL 1 DAY" in sql
    for column in ("date_key", "year_number", "month_start", "month_label", "quarter_label"):
        assert f"AS {column}" in sql


def test_a_measure_that_sums_something_that_is_not_a_number_is_refused():
    with pytest.raises(UssError, match="not a number"):
        read_uss(FIXTURES / "bad_sum_of_a_string.yaml")


def test_an_event_without_a_definition_is_refused():
    with pytest.raises(UssError, match="definition"):
        read_uss(FIXTURES / "bad_undefined_event.yaml")


def test_a_stage_that_does_not_own_a_measure_emits_a_typed_null_for_it():
    sql = bridge()
    assert "cast(NULL AS BIGINT) AS _measure__parent__finished_parents_count" in sql
    assert "cast(NULL AS BIGINT) AS _measure__parent__happened_parents_count" in sql
    assert "cast(NULL AS DECIMAL(28, 8)) AS _measure__parent__size_parents_units" in sql


def test_every_branch_emits_the_contract_columns_in_the_contract_order():
    """A union takes its column names from the first branch.

    So a branch that emits the right columns in a different order puts one measure's values
    silently into another measure's column, and DESCRIBE still matches the contract. Counting
    aliases does not catch that; only the sequence does.
    """
    model, uss = plan()
    expected = list(bridge_columns(model, uss))
    parts = branches(bridge())
    assert len(parts) == 2, "two declared events are two branches"
    for branch in parts:
        select = branch[: branch.rindex("FROM")]
        assert re.findall(r" AS ([a-z_0-9]+)(?=[,\n])", select) == expected


def test_a_zero_edge_walk_is_a_valid_walk():
    """One entity and no relationships is the normal case, not a degenerate one.

    Slice 1 has exactly this shape, and the first slice with a relationship must not
    discover that the generator only ever worked with edges.
    """
    model, uss = plan()
    assert bridge_columns(model, uss).count("parent_key") == 1
    assert "parent_key" in bridge_sql(model, uss)

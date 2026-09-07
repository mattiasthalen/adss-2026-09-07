"""DAR is generated. Its column contract is what every consumer is written against. ADR 0002."""

import re
from pathlib import Path

import pytest

from adss.model import read_model
from adss.uss import (
    Uss,
    UssError,
    bridge_columns,
    bridge_sql,
    calendar_sql,
    definitions,
    entity_ids,
    peripheral_sql,
    read_uss,
)

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


def branch_of(sql: str, event: str) -> str:
    """One branch of the union, by the stage it reads."""
    return next(part for part in branches(sql) if f"'{event}' AS _event" in part)


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
        "child_key",
        "neighbour_key",
        "_measure__parent__happened_parents_count",
        "_measure__parent__size_parents_units",
        "_measure__parent__finished_parents_count",
        "_measure__child__occurred_children_count",
        "_measure__child__weight_children_units",
    )


def test_a_count_measure_is_one_per_row_and_a_sum_measure_is_its_attribute():
    sql = bridge()
    assert "cast(1 AS BIGINT) AS _measure__parent__happened_parents_count" in sql
    assert (
        'cast(revision."PARENT_SIZE" AS DECIMAL(28, 8)) AS _measure__parent__size_parents_units'
        in sql
    )


def test_an_event_reads_the_history_view_and_keeps_the_latest_version():
    sql = bridge()
    assert 'dab."view_PARENT_hist"' in sql
    assert "row_number() OVER (" in sql
    assert "ORDER BY" in sql and "eff_tmstp DESC" in sql


def test_an_entity_with_no_date_for_the_event_has_no_row_for_it():
    assert 'revision."HAPPENED_ON" IS NOT NULL' in bridge(), (
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
    assert len(parts) == 3, "three declared events are three branches"
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


def test_the_key_columns_follow_the_model_order_not_the_declaration_order():
    """Reordering two events in the sidecar is not a model change.

    The published contract says the key columns are in model order, and the data check
    cannot notice a rearrangement because it derives what it expects from the same function.
    """
    model, uss = plan()
    reversed_events = Uss(path=uss.path, events=tuple(reversed(uss.events)))
    assert bridge_columns(model, uss)[:8] == bridge_columns(model, reversed_events)[:8]


def test_an_event_kind_the_generator_does_not_build_is_refused_rather_than_faked():
    with pytest.raises(UssError, match="only builds"):
        read_uss(FIXTURES / "bad_snapshot_event.yaml")


def test_a_definition_is_carried_verbatim_and_never_composed():
    model, uss = plan()
    carried = definitions(model, uss)
    assert carried["PARENT"] == model.entity("PARENT").definition
    assert (
        carried["PARENT.HAPPENED_ON"] == model.entity("PARENT").attribute("HAPPENED_ON").definition
    )
    assert carried["PARENT.events.HAPPENED"] == uss.events[0].definition
    assert carried["PARENT.measures.HAPPENED_PARENTS_COUNT"] == uss.events[0].measures[0].definition


def test_a_stage_carries_the_key_of_everything_it_inherits_from():
    """The edge runs one way. A child inherits its parent's key; a parent inherits nothing."""
    model, uss = plan()
    assert entity_ids(model, uss) == ("PARENT", "CHILD", "NEIGHBOUR"), (
        "an entity reached only by inheritance is still in the bridge, and still in model order"
    )
    occurred, happened = branch_of(bridge(), "occurred"), branch_of(bridge(), "happened")
    assert "AS parent_key" in occurred and "AS neighbour_key" in occurred
    assert "cast(NULL AS VARCHAR) AS child_key" in happened, (
        "the edge runs child to parent, so a parent stage has no child to name"
    )
    assert "cast(NULL AS VARCHAR) AS neighbour_key" in happened


def test_an_inherited_key_is_the_one_in_force_when_the_row_was_observed():
    """Not the current one. The engine's own relationship view gives the current one, which
    re-points a child's whole history at whichever parent it points at now. ADR 0006."""
    sql = bridge()
    assert "<= " in sql and "_observed_at" in sql
    assert re.search(r"\.eff_tmstp\s*<=\s*\w+\._observed_at", sql), (
        "the pair is taken as of the observation time of the row that inherits it"
    )


def test_a_row_that_inherits_nothing_keeps_its_row():
    """A child with no parent has no pair row at all -- absence is the only evidence. An
    inner join would silently drop it and change a count that is already published."""
    sql = bridge()
    assert "LEFT JOIN" in sql
    assert "INNER JOIN" not in sql, "an inherited key is joined LEFT or a row disappears"


def test_the_pairs_are_ranked_deterministically_and_can_never_fan_out():
    """The engine's macro uses rank(), which returns both rows for a child whose source named
    two parents at one instant -- and two bridge rows double that child's measures."""
    sql = bridge()
    assert "row_number() OVER (" in sql
    assert not re.search(r"(?<!row_number\(\) OVER \()\brank\s*\(", sql), "rank() ties"
    assert "ver_tmstp DESC" in sql, "a closing row shares its predecessor's eff_tmstp"


def test_only_open_pairs_are_read():
    assert "row_st = 'Y'" in bridge()


def test_the_relationship_is_matched_by_name_and_never_by_number():
    """type_key is not stable across models -- it differed between two probes of the same
    shape -- and the pair table is named for the entity pair, so two edges share one table."""
    sql = bridge()
    assert "rel_name = 'CHILD_POINTS_AT_PARENT'" in sql
    assert "rel_name = 'CHILD_SITS_BESIDE_NEIGHBOUR'" in sql
    assert "type_key" not in sql


def test_the_pairs_come_from_the_object_that_carries_the_relationship_name():
    sql = bridge()
    assert 'dab."v_CHILD_POINTS_AT_PARENT"' in sql
    assert 'dab."view_CHILD_POINTS_AT_PARENT"' not in sql, (
        "the ranked view is the current one, and its rank() can return two rows"
    )
    assert "_with_rel" not in sql, (
        "on a relationship's target side that view fans out: it carries the source entity's "
        "own attributes, one row per child"
    )


def test_an_entity_reached_only_by_inheritance_still_gets_a_peripheral():
    """Otherwise the bridge carries a key that joins to nothing, which is how a dimension
    that exists in the model becomes unusable in the layer built from it."""
    model, _ = plan()
    sql = peripheral_sql(model, "NEIGHBOUR")
    assert "CREATE OR REPLACE TABLE dar__uss.neighbour" in sql
    assert "AS neighbour_label" in sql

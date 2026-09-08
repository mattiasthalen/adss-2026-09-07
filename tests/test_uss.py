"""DAR is generated. Its column contract is what every consumer is written against. ADR 0002."""

import re
from dataclasses import replace
from pathlib import Path

import pytest

from adss.model import Attribute, AttributeType, Entity, Relationship, read_model
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


def cte_of(sql: str, name: str) -> str:
    """One common table expression's body, so an assertion is about the thing it names.

    A substring over the whole file proves only that some line somewhere says it, which for
    SQL that emits several similar windows and joins is close to proving nothing.
    """
    body = sql[sql.index(f"{name} AS (") + len(name) + 5 :]
    depth = 1
    for index, character in enumerate(body):
        depth += (character == "(") - (character == ")")
        if depth == 0:
            return body[:index]
    raise AssertionError(f"{name} is not a closed CTE")


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
    """Asserted of the version CTE, whole.

    Three whole-file substrings said nothing about it: the INHERIT CTE satisfies every one of
    them, so the assertions were about a different window than the one they named. All three
    mutations that matter -- row_number to rank, DESC to ASC, and adding eff_tmstp to the
    partition -- left the suite green, and none is observable in the warehouse today because
    every entity has exactly one version.
    """
    picked = cte_of(bridge(), "happened__version")
    assert 'dab."view_PARENT_hist"' in picked
    window = re.search(r"QUALIFY (\w+)\(\) OVER \((.*?)\) = 1", picked, re.DOTALL)
    assert window, "the versions are ranked"
    assert window.group(1) == "row_number", (
        "rank() returns every tied row, and the engine writes a closing row sharing eff_tmstp"
    )
    partition = re.search(r"PARTITION BY ([^\n]+)", window.group(2))
    assert partition and partition.group(1).strip() == 'revision."PARENT_key"', (
        "one version per entity. Adding the timestamp makes row_number() return 1 for every "
        "version, so every version becomes a bridge row"
    )
    assert re.search(r"ORDER BY\s+revision\.eff_tmstp DESC", window.group(2)), (
        "the LATEST version. Ascending keeps the oldest, which this test is named against"
    )


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
    """Every branch, every measure, paired with the value it carries -- not counted.

    Whole-file substrings cannot see ownership: the NULL casts they look for are emitted by
    SOME branch whatever the generator decides, so deciding ownership by entity rather than by
    event left the suite green while emitting a column its own CTE does not have. And rotating
    the value expressions within one branch, leaving the aliases in contract order, emits valid
    SQL that puts a count into a sum column -- green until a build compares two answers.
    """
    _, uss = plan()
    for event in uss.events:
        branch = branch_of(bridge(), event.name)
        for owner, measure, column in uss.measure_columns():
            value = re.search(rf"^\s*(.+?) AS {re.escape(column)},?$", branch, re.MULTILINE)
            assert value, f"{event.name} emits no {column}"
            if owner is event:
                assert value.group(1) == f"{event.name}.{column}", (
                    f"{event.name} owns {column}, so it carries its own value for it -- and "
                    f"carries it under its own name, not another measure's"
                )
            else:
                assert value.group(1) == f"cast(NULL AS {measure.sql_type})", (
                    f"{event.name} does not own {column}, so it emits a typed NULL. A zero "
                    f"here would be counted; a value from elsewhere would be multiplied"
                )


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
    # Not `"AS parent_key" in occurred`: a typed NULL is spelled `cast(NULL AS VARCHAR) AS
    # parent_key` and satisfies that, so the assertion that names this slice's whole behaviour
    # would pass an implementation that inherits nothing. What the stage must do is READ the
    # column from the CTE that resolved it.
    for key, edge, source in (
        ("parent_key", "occurred__child_points_at_parent", 'pair."PARENT_key"'),
        ("neighbour_key", "occurred__child_sits_beside_neighbour", 'pair."NEIGHBOUR_key"'),
    ):
        assert f"occurred.{key} AS {key}" in occurred, f"{key} is carried, not invented"
        # And what the branch carries came off the PAIR. Stopping at the branch would accept
        # a resolver that emits cast(NULL AS VARCHAR) for every key it was asked to resolve,
        # which is precisely what all three M6 failures look like from downstream.
        assert f"{source} AS {key}" in cte_of(bridge(), edge), (
            f"{key} is read off the pair, not invented by the resolver"
        )
    assert "cast(NULL AS VARCHAR) AS child_key" in happened, (
        "the edge runs child to parent, so a parent stage has no child to name"
    )
    assert "cast(NULL AS VARCHAR) AS neighbour_key" in happened


def test_an_inherited_key_is_the_one_in_force_when_the_row_was_observed():
    """Not the current one. The engine's own relationship view gives the current one, which
    re-points a child's whole history at whichever parent it points at now. ADR 0006."""
    resolved = cte_of(bridge(), "occurred__child_points_at_parent")
    assert re.search(r"pair\.eff_tmstp\s*<=\s*revision\._observed_at", resolved), (
        "the pair is taken as of the observation time of the row that inherits it"
    )


def test_a_row_that_inherits_nothing_keeps_its_row():
    """A child with no parent has no pair row at all -- absence is the only evidence. An
    inner join would silently drop it and change a count that is already published.

    Asserted of the join to the PAIRS specifically. A whole-file "LEFT JOIN is present and
    INNER JOIN is not" is satisfied by any one of the file's joins, and says nothing about
    this one -- and a bare JOIN is inner while matching neither half of it.
    """
    resolved = cte_of(bridge(), "occurred__child_points_at_parent")
    joins = re.findall(r"^(\w[\w ]*?)JOIN\s+(\S+)", resolved, re.MULTILINE)
    assert joins, "the pairs are joined to the entity's version"
    for kind, target in joins:
        assert kind.strip() == "LEFT", f"{target} is joined {kind.strip() or 'INNER'}"
    # And the stage attaches the resolved key back on the inheriting key, not on nothing:
    # a cross join here multiplies every measure by the row count and nothing else would say so.
    stage = cte_of(bridge(), "occurred")
    assert re.search(
        r"LEFT JOIN occurred__child_points_at_parent AS \w+\s*\n\s*ON .*child_key = "
        r"revision\.child_key",
        stage,
    ), "the resolved key is attached on the key that inherits it"


def test_the_pairs_are_ranked_deterministically_and_can_never_fan_out():
    """The engine's macro uses rank(), which returns both rows for a child whose source named
    two parents at one instant -- and two bridge rows double that child's measures.

    The window is asserted whole. Its PARTITION BY is the load-bearing half: adding the target
    key to it makes row_number() return 1 for EACH parent, so a child with two parents yields
    two rows and a doubled measure -- and a test that only looked for `row_number()` would
    still be green. The ORDER BY is asserted as a sequence for the same reason: ranking by
    version timestamp before effective timestamp picks a different parent whenever the two
    disagree.
    """
    resolved = cte_of(bridge(), "occurred__child_points_at_parent")
    window = re.search(r"QUALIFY (\w+)\(\) OVER \((.*?)\) = 1", resolved, re.DOTALL)
    assert window, "the pairs are ranked"
    assert window.group(1) == "row_number", (
        "rank() and dense_rank() both return every tied row, and a tie here doubles a measure"
    )
    partition = re.search(r"PARTITION BY ([^\n]+)", window.group(2))
    assert partition, "the ranking is partitioned"
    partitioned = [term.strip() for term in partition.group(1).split(",")]
    assert partitioned == ["revision.child_key", "revision._observed_at"], (
        "one row per inheriting ROW. The key alone would hand every retained version of an "
        "entity the same parent, which is 'as of now' wearing the as-of rule's clothes"
    )
    assert not any(term.startswith("pair.") for term in partitioned), (
        "every partition term comes from the side that inherits. A term from the PAIRS makes "
        "row_number() return 1 for each of them, which is the fan-out this ranking exists to "
        "prevent -- and it would still be a row_number()"
    )
    ordering = re.findall(r"^\s+(pair\.\S+)", window.group(2), re.MULTILINE)
    assert ordering == ["pair.eff_tmstp", "pair.ver_tmstp", 'pair."PARENT_key"'], (
        "effective time first, then the version that closes a row sharing it, then a "
        "deterministic tiebreak"
    )


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


def test_two_edges_into_one_key_column_are_refused_rather_than_emitted():
    """A stage carries one key column per entity it inherits from, named for that entity.

    Two edges to the same target would emit that column twice, and DuckDB resolves the
    ambiguity instead of raising -- so one inherited key would vanish with nothing to say
    which. Distinguishing them changes a published contract, so it is a decision. ADR 0006.
    """
    model, _ = plan()
    doubled = replace(
        model,
        relationships=(
            *model.relationships,
            Relationship(
                name="ALSO_POINTS_AT",
                source_entity_id="CHILD",
                target_entity_id="PARENT",
                definition="A second edge to the same place.",
            ),
        ),
    )
    with pytest.raises(UssError, match="loses one of them"):
        read_uss(FIXTURES / "uss.yaml", doubled)


def test_an_edge_from_an_entity_to_itself_is_refused_for_the_same_reason():
    model, _ = plan()
    reflexive = replace(
        model,
        relationships=(
            Relationship(
                name="POINTS_AT",
                source_entity_id="CHILD",
                target_entity_id="CHILD",
                definition="A child points at a child.",
            ),
        ),
    )
    with pytest.raises(UssError, match="points at the entity it runs from"):
        read_uss(FIXTURES / "uss.yaml", reflexive)


def test_an_entity_appended_to_the_model_appends_its_key_and_moves_nothing():
    """B7 says change is additive, and for this contract that means appended to the END.

    An entity inserted in the middle of the model moves every key column after it, and nothing
    can catch that: the check derives what it expects from the same function that built the
    table, so both sides move together. So the property is pinned here, on the one shape that
    is actually safe.
    """
    model, uss = plan()
    before = bridge_columns(model, uss)
    later = replace(
        model,
        entities=(
            *model.entities,
            Entity(
                id="LATECOMER",
                definition="Arrived after the contract was published.",
                attributes=(
                    Attribute(
                        id="LATECOMER_NUMBER", type=AttributeType.STRING, definition="Its number."
                    ),
                ),
            ),
        ),
        relationships=(
            *model.relationships,
            Relationship(
                name="ALSO_SITS_BESIDE",
                source_entity_id="CHILD",
                target_entity_id="LATECOMER",
                definition="A later edge.",
            ),
        ),
    )
    after = bridge_columns(later, read_uss(FIXTURES / "uss.yaml", later))
    keys = [c for c in before if c.endswith("_key")]
    assert [c for c in after if c.endswith("_key")] == [*keys, "latecomer_key"], (
        "the new key goes last among the keys; no existing key moves"
    )
    measures = [c for c in before if c.startswith("_measure__")]
    assert [c for c in after if c.startswith("_measure__")] == measures, (
        "and no measure is added, reordered or renamed by adding an entity"
    )
    # But the measures DO all move right, because keys precede them. That is the property the
    # docstring used to deny, and it is why nothing may read this table by position.
    assert after.index(measures[0]) == before.index(measures[0]) + 1


def test_two_events_on_one_entity_may_not_name_the_same_measure():
    """A measure is owned by an event and named for an entity. With one event each those are
    the same thing; with two they are not, and the same id on both silently replaces one
    definition with the other in the glossary. ADR 0008.
    """
    model, _ = plan()
    collided = FIXTURES / "bad_two_events_one_measure.yaml"
    with pytest.raises(UssError, match="would replace"):
        read_uss(collided, model)


def test_the_same_measure_id_on_two_different_entities_is_still_accepted():
    """The column already carries the entity, so those two do not collide. A refusal that
    caught them would forbid the ordinary case to prevent the rare one.

    Asserted against a fixture that actually contains the case. The version of this test that
    shipped with ADR 0008 read the ordinary fixture, whose measure ids are all distinct, and
    asserted that its columns were unique -- a statement about the fixture, not the refusal.
    Keying the refusal on the measure id alone, which is precisely what the record says it
    must not do, left it green.
    """
    model, _ = plan()
    shared = read_uss(FIXTURES / "shared_measure_id_across_entities.yaml", model)
    columns = [column for _, _, column in shared.measure_columns()]
    assert "_measure__parent__happened_parents_count" in columns
    assert "_measure__child__happened_parents_count" in columns
    assert len(columns) == len(set(columns)), "the entity in the name is what keeps them apart"


def test_every_declared_measure_keeps_its_own_definition():
    """The assertion that would have caught the overwrite, and did not exist.

    A glossary entry silently replaced by another measure's definition is the failure nothing
    else reports: the page renders a plausible sentence about the wrong number, and every test
    and every check passes.
    """
    model, uss = plan()
    declared = [(e.entity_id, m.id, m.definition) for e in uss.events for m in e.measures]
    carried = definitions(model, uss)
    # Counted against what the glossary actually returns, not against the same list twice.
    # The version of this that shipped with ADR 0008 compared `declared` with itself, so it
    # could not fail on the count the record says it guards.
    measures = [token for token in carried if ".measures." in token]
    assert len(measures) == len(declared), (
        "one entry per declared measure. Two sharing a token means one definition replaced "
        "the other, which is the failure nothing else reports"
    )
    for entity, measure, definition in declared:
        assert carried[f"{entity}.measures.{measure}"] == definition


def test_a_stage_may_be_dated_by_a_date_it_inherits():
    """An entity with no date of its own is dated by the one it reaches. ADR 0009.

    The walk already resolves the parent as of the observation time of the row that inherits,
    and puts its key on that row. A date is another column of the row it already found.
    """
    model, _ = plan()
    uss = read_uss(FIXTURES / "inherited_date.yaml", model)
    sql = bridge_sql(model, uss)
    resolved = cte_of(sql, "reached__child_points_at_parent")
    assert 'cast(dated."HAPPENED_ON" AS DATE) AS _event_date' in resolved, (
        "the date comes off the inherited entity"
    )
    # The same CTE and the same instant. Two instants on one bridge row is what ADR 0006 calls
    # the entire difference between the option it chose and the one it rejected, and an
    # unbounded join here would take whichever version of the parent the engine reached first.
    assert 'ON dated."PARENT_key" = pair."PARENT_key"' in resolved, (
        "off the same parent the key came from"
    )
    assert re.search(r"dated\.eff_tmstp\s*<=\s*revision\._observed_at", resolved), (
        "as of the observation time of the row that inherits, exactly as the key is"
    )
    assert "_event_date" not in cte_of(sql, "reached__version"), (
        "the event's own entity has no date to give, so its version CTE emits none"
    )
    # And the stage reads the date from where it was resolved, not from its own version.
    stage = cte_of(sql, "reached")
    assert "child_points_at_parent._event_date AS _event_date" in stage, (
        "a stage whose date is inherited reads it off the edge that resolved it"
    )


def test_an_unqualified_date_attribute_still_means_the_events_own_entity():
    model, uss = plan()
    sql = bridge_sql(model, uss)
    assert 'cast(revision."HAPPENED_ON" AS DATE) AS _event_date' in cte_of(sql, "happened__version")


def test_a_date_on_an_entity_no_edge_reaches_is_refused_with_the_edges_that_exist():
    model, _ = plan()
    with pytest.raises(UssError, match="no edge"):
        read_uss(FIXTURES / "bad_unreachable_date.yaml", model)


def test_a_row_whose_inherited_date_does_not_resolve_has_no_bridge_row():
    """The same rule as an event that did not happen, one layer along the walk.

    The version CTE filters its own date; an inherited one is not there to filter, so the stage
    filters where it was resolved. Without it a line whose order cannot be resolved would carry
    a null event date into the bridge -- and the calendar's inner join would drop it silently,
    which looks like the rule working and is not.
    """
    model, _ = plan()
    uss = read_uss(FIXTURES / "inherited_date.yaml", model)
    stage = cte_of(bridge_sql(model, uss), "reached")
    assert re.search(r"WHERE \w+\._event_date IS NOT NULL", stage), (
        "an unresolvable inherited date means no row, by construction"
    )

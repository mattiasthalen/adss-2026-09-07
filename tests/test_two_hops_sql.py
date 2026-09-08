"""Two hops, executed rather than read. ADR 0014.

The other tests of the walk assert over the generated SQL's text. That proves the emitter said
what was expected; it does not prove the SQL means it, and the defect this replaced was invisible
in exactly that gap -- a key column that existed, was filled with a typed null, and joined to
nothing. So this runs the generated statement against a warehouse it builds and asks the two
questions a reader would: does the far key name a real row, and did the walk multiply anything.
"""

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from adss.model import read_model
from adss.uss import bridge_sql, peripheral_sql, read_uss
from support import engine_objects

Db = duckdb.DuckDBPyConnection

FIXTURES = Path(__file__).parent / "fixtures" / "dab"
WHEN = "2026-01-01"

# Three children, two neighbours, one district. Both neighbours lie in the same district, so if
# the walk fanned out, the child weights would be summed once per route to it.
CHILDREN = [
    ("C1", "N1", Decimal("5.00")),
    ("C2", "N1", Decimal("5.00")),
    ("C3", "N2", Decimal("5.00")),
]
NEIGHBOURS = [("N1", "D1"), ("N2", "D1")]


def load(connection: Db) -> None:
    connection.execute(
        'INSERT INTO dab."view_DISTRICT_hist" VALUES (?, ?, ?, ?)', ["D1", WHEN, "D1", "D1 label"]
    )
    for neighbour, district in NEIGHBOURS:
        connection.execute(
            'INSERT INTO dab."view_NEIGHBOUR_hist" VALUES (?, ?, ?, ?)',
            [neighbour, WHEN, neighbour, neighbour],
        )
        connection.execute(
            'INSERT INTO dab."v_NEIGHBOUR_LIES_IN_DISTRICT" VALUES (?, ?, ?, ?, ?, ?)',
            [neighbour, district, "NEIGHBOUR_LIES_IN_DISTRICT", WHEN, WHEN, "Y"],
        )
    for key, neighbour, weight in CHILDREN:
        connection.execute(
            'INSERT INTO dab."view_CHILD_hist" VALUES (?, ?, ?, ?, ?)',
            [key, WHEN, key, WHEN, weight],
        )
        connection.execute(
            'INSERT INTO dab."v_CHILD_SITS_BESIDE_NEIGHBOUR" VALUES (?, ?, ?, ?, ?, ?)',
            [key, neighbour, "CHILD_SITS_BESIDE_NEIGHBOUR", WHEN, WHEN, "Y"],
        )


def build(connection: Db) -> None:
    model = read_model(FIXTURES / "model.yaml")
    uss = read_uss(FIXTURES / "uss.yaml", model)
    for entity in ("PARENT", "CHILD", "NEIGHBOUR", "DISTRICT"):
        connection.execute(peripheral_sql(model, entity).replace(";", ""))
    connection.execute(bridge_sql(model, uss).replace(";", ""))


@pytest.fixture
def scratch(tmp_path: Path) -> Iterator[Db]:
    connection = duckdb.connect(str(tmp_path / "two-hops.duckdb"))
    engine_objects(connection)
    load(connection)
    build(connection)
    yield connection
    connection.close()


def one(connection: Db, sql: str) -> object:
    found = connection.execute(sql).fetchone()
    assert found is not None
    return found[0]


def test_the_key_two_edges_away_names_a_row_in_its_peripheral(scratch: Db):
    """A key that resolves to nothing is what the null used to be, wearing a value."""
    joined = one(
        scratch,
        "SELECT count(*) FROM dar__uss._bridge AS b "
        "INNER JOIN dar__uss.district AS d ON b.district_key = d.district_key "
        "WHERE b._event = 'occurred'",
    )
    assert joined == 3, "every child row reaches the district its neighbour lies in"


def test_the_far_key_is_the_right_one_and_not_merely_present(scratch: Db):
    rows = scratch.execute(
        "SELECT child_key, neighbour_key, district_key FROM dar__uss._bridge "
        "WHERE _event = 'occurred' ORDER BY child_key"
    ).fetchall()
    assert rows == [("C1", "N1", "D1"), ("C2", "N1", "D1"), ("C3", "N2", "D1")]


def test_the_walk_does_not_multiply_a_measure_however_long_it_gets(scratch: Db):
    """The property D-0001 rests on, re-run at depth two rather than assumed to survive it.

    Both neighbours lie in the same district, so a walk that joined rather than resolved would
    have something to multiply by -- and the number would still look like a number.
    """
    total = one(scratch, "SELECT sum(_measure__child__weight_children_units) FROM dar__uss._bridge")
    assert total == Decimal("15.00")
    assert one(scratch, "SELECT count(*) FROM dar__uss._bridge WHERE _event = 'occurred'") == 3


def test_a_stage_that_reaches_nothing_carries_a_null_and_not_a_wrong_row(scratch: Db):
    """PARENT walks nowhere. The typed null is right there and wrong two edges out, which is
    the whole distinction this record turns on."""
    carried = one(
        scratch,
        "SELECT count(*) FROM dar__uss._bridge "
        "WHERE _event = 'happened' AND district_key IS NOT NULL",
    )
    assert carried == 0


EARLY, MIDDLE, LATE = "2026-06-01", "2026-06-02", "2026-06-03"


@pytest.fixture
def bare(tmp_path: Path) -> Iterator[Db]:
    """The engine's objects, empty. These tests choose their own instants."""
    connection = duckdb.connect(str(tmp_path / "observed.duckdb"))
    engine_objects(connection)
    connection.execute(
        'INSERT INTO dab."view_DISTRICT_hist" VALUES (?, ?, ?, ?)', ["D1", EARLY, "D1", "first"]
    )
    connection.execute(
        'INSERT INTO dab."view_DISTRICT_hist" VALUES (?, ?, ?, ?)', ["D2", EARLY, "D2", "second"]
    )
    connection.execute(
        'INSERT INTO dab."view_NEIGHBOUR_hist" VALUES (?, ?, ?, ?)', ["N1", EARLY, "N1", "N1"]
    )
    # One child, observed in the middle, sitting beside a neighbour from the start.
    connection.execute(
        'INSERT INTO dab."view_CHILD_hist" VALUES (?, ?, ?, ?, ?)',
        ["C1", MIDDLE, "C1", MIDDLE, Decimal("5.00")],
    )
    connection.execute(
        'INSERT INTO dab."v_CHILD_SITS_BESIDE_NEIGHBOUR" VALUES (?, ?, ?, ?, ?, ?)',
        ["C1", "N1", "CHILD_SITS_BESIDE_NEIGHBOUR", EARLY, EARLY, "Y"],
    )
    yield connection
    connection.close()


def lies_in(connection: Db, district: str, at: str) -> None:
    connection.execute(
        'INSERT INTO dab."v_NEIGHBOUR_LIES_IN_DISTRICT" VALUES (?, ?, ?, ?, ?, ?)',
        ["N1", district, "NEIGHBOUR_LIES_IN_DISTRICT", at, at, "Y"],
    )


def district_of(connection: Db) -> object:
    build(connection)
    return one(
        connection,
        "SELECT district_key FROM dar__uss._bridge WHERE _event = 'occurred' AND child_key = 'C1'",
    )


def test_an_edge_first_seen_after_the_row_resolves_from_the_earliest_observation(bare: Db):
    """ADR 0015. The shape the real lake had: an entity added later than the rows that reach it.

    Nothing preceded the child's observation, so the strict rule excluded every pair and the
    dimension was null on all of them -- a right total with an empty grouping, on an incremental
    build, while a clean one was green.
    """
    lies_in(bare, "D1", LATE)
    assert district_of(bare) == "D1", "not yet observed is not the same as known to be otherwise"


def test_a_version_that_does_precede_still_wins_over_a_later_one(bare: Db):
    """The fallback must not have swallowed ADR 0006. Two observations straddle the child, and
    the earlier one is what was in force when it was seen."""
    lies_in(bare, "D1", EARLY)
    lies_in(bare, "D2", LATE)
    assert district_of(bare) == "D1", "a later correction is still not applied retroactively"


def test_an_edge_that_was_never_recorded_at_all_is_still_null(bare: Db):
    """The fallback fills in what had not been observed, never what was not recorded."""
    assert district_of(bare) is None


def test_the_earliest_of_several_unobserved_versions_is_the_one_taken(bare: Db):
    """The fallback is the EARLIEST, not merely one of them. With a single later version the
    direction of that sort is unobservable, which is what a first pass at this test missed."""
    lies_in(bare, "D1", LATE)
    lies_in(bare, "D2", "2026-06-04")
    assert district_of(bare) == "D1", "the first thing we ever learned, not the last"


def test_the_rule_survives_a_session_that_orders_nulls_the_other_way(bare: Db):
    """Null ordering is a setting rather than a property of SQL. This engine defaults to
    NULLS_LAST and Postgres does not, so the generated sort says which it needs -- and this is
    what makes saying so load-bearing rather than decorative."""
    bare.execute("SET default_null_order = 'NULLS_FIRST'")
    lies_in(bare, "D1", EARLY)
    lies_in(bare, "D2", LATE)
    assert district_of(bare) == "D1", "a later correction is still not applied retroactively"

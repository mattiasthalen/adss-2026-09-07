"""A parent's measure is not multiplied by its children. ADR 0002, ADR 0012, deviation D-0001.

The whole argument for putting every process in one shared star schema is that a measure cannot
fan out across a walk over many-to-one edges: a key inherits, a measure does not. Slices 1 to 3
could not demonstrate it -- every entity was at one grain, so no measure *could* multiply however
the join was written, and the register said so. This is the shape that can.

It runs the generated SQL rather than reading it. A substring assertion would pass a generator
that emitted the right typed nulls in the wrong branch, which is exactly the defect this exists
to catch. The warehouse is synthetic and built here, which conventions section 6 permits a
machinery test to do and forbids a data check from doing.
"""

from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from adss.model import read_model
from adss.uss import bridge_sql, peripheral_sql, read_uss

FIXTURES = Path(__file__).parent / "fixtures" / "dab"

Db = duckdb.DuckDBPyConnection

# One parent worth 100.50 and one worth 50.25, and three children between them each worth 5.00.
# If a measure inherited as a key does, the parents' total would be 100.50 x 2 + 50.25 = 251.25
# rather than 150.75 -- which is the shape of every fan-trap bug there is.
PARENTS = [("P1", Decimal("100.50")), ("P2", Decimal("50.25"))]
CHILDREN = [
    ("C1", "P1", Decimal("5.00")),
    ("C2", "P1", Decimal("5.00")),
    ("C3", "P2", Decimal("5.00")),
]

WHEN = "2026-01-01"

TOTAL = "SELECT sum(_measure__parent__size_parents_units) FROM dar__uss._bridge"
OCCURRED = "SELECT count(*) FROM dar__uss._bridge WHERE _event = 'occurred'"


def _engine_objects(connection: Db) -> None:
    """The objects the generator reads, shaped as the engine shapes them."""
    connection.execute("CREATE SCHEMA dab")
    connection.execute("CREATE SCHEMA dar__uss")
    connection.execute(
        'CREATE TABLE dab."view_PARENT_hist" ("PARENT_key" VARCHAR, eff_tmstp TIMESTAMP, '
        '"PARENT_NUMBER" VARCHAR, "HAPPENED_ON" TIMESTAMP, "PARENT_LABEL" VARCHAR, '
        '"PARENT_SIZE" DECIMAL(28, 8), "FINISHED_ON" TIMESTAMP)'
    )
    connection.execute(
        'CREATE TABLE dab."view_CHILD_hist" ("CHILD_key" VARCHAR, eff_tmstp TIMESTAMP, '
        '"CHILD_NUMBER" VARCHAR, "OCCURRED_ON" TIMESTAMP, "CHILD_WEIGHT" DECIMAL(28, 8))'
    )
    connection.execute(
        'CREATE TABLE dab."view_NEIGHBOUR_hist" ("NEIGHBOUR_key" VARCHAR, eff_tmstp TIMESTAMP, '
        '"NEIGHBOUR_NUMBER" VARCHAR, "NEIGHBOUR_LABEL" VARCHAR)'
    )
    for edge, source, target in (
        ("CHILD_POINTS_AT_PARENT", "CHILD", "PARENT"),
        ("CHILD_SITS_BESIDE_NEIGHBOUR", "CHILD", "NEIGHBOUR"),
    ):
        connection.execute(
            f'CREATE TABLE dab."v_{edge}" ("{source}_key" VARCHAR, "{target}_key" VARCHAR, '
            f"rel_name VARCHAR, eff_tmstp TIMESTAMP, ver_tmstp TIMESTAMP, row_st VARCHAR)"
        )


def _load(connection: Db, children: list[tuple[str, str, Decimal]]) -> None:
    for key, size in PARENTS:
        connection.execute(
            'INSERT INTO dab."view_PARENT_hist" VALUES (?, ?, ?, ?, ?, ?, NULL)',
            [key, WHEN, key, WHEN, key, size],
        )
    for key, parent, weight in children:
        connection.execute(
            'INSERT INTO dab."view_CHILD_hist" VALUES (?, ?, ?, ?, ?)',
            [key, WHEN, key, WHEN, weight],
        )
        connection.execute(
            'INSERT INTO dab."v_CHILD_POINTS_AT_PARENT" VALUES (?, ?, ?, ?, ?, ?)',
            [key, parent, "CHILD_POINTS_AT_PARENT", WHEN, WHEN, "Y"],
        )


def _build(connection: Db) -> None:
    model = read_model(FIXTURES / "model.yaml")
    uss = read_uss(FIXTURES / "uss.yaml", model)
    for entity in ("PARENT", "CHILD", "NEIGHBOUR"):
        connection.execute(peripheral_sql(model, entity).replace(";", ""))
    connection.execute(bridge_sql(model, uss).replace(";", ""))


def _total(connection: Db, sql: str) -> object:
    found = connection.execute(sql).fetchone()
    assert found is not None
    return found[0]


@pytest.fixture
def scratch(tmp_path: Path):
    connection = duckdb.connect(str(tmp_path / "fan.duckdb"))
    _engine_objects(connection)
    _load(connection, CHILDREN)
    _build(connection)
    yield connection
    connection.close()


def test_a_parents_measure_is_its_own_total_and_not_its_children_times_it(scratch: Db):
    """150.75, not 251.25. This is the property D-0001 is carried on."""
    assert _total(scratch, TOTAL) == Decimal("150.75")


def test_both_grains_are_right_in_one_scan(scratch: Db):
    """The query a reader actually writes, and the one that traps."""
    found = scratch.execute(
        "SELECT sum(_measure__parent__size_parents_units), "
        "sum(_measure__child__weight_children_units), count(*) FROM dar__uss._bridge"
    ).fetchone()
    # Five rows, not six: two parents happened, three children occurred, and neither parent
    # finished -- so that event has no rows at all, which is the absent-event rule turning up
    # here without being asked for.
    assert found == (Decimal("150.75"), Decimal("15.00"), 5)


def test_the_coarser_measure_is_null_on_every_finer_row_while_the_key_is_not(scratch: Db):
    """The mechanism rather than the number. A typed NULL is what keeps sum() additive across
    grains -- and the KEY must fan out where the measure must not, which is the whole
    distinction the bridge exists to draw."""
    carried = _total(scratch, f"{OCCURRED} AND _measure__parent__size_parents_units IS NOT NULL")
    assert carried == 0, "a child row carries no parent measure"
    inherited = _total(scratch, f"{OCCURRED} AND parent_key IS NOT NULL")
    assert inherited == 3, "and every child row does carry its parent's key"


def test_the_parents_total_does_not_move_when_a_parent_gains_children(scratch: Db):
    """The falsifiable half: change only the child count and the parent total must not move."""
    before = _total(scratch, TOTAL)
    _load(scratch, [(f"C{n}", "P1", Decimal("5.00")) for n in range(4, 9)])
    _build(scratch)
    after = _total(scratch, TOTAL)
    assert after == before == Decimal("150.75")


def test_the_trap_this_does_not_close_is_the_one_on_the_peripheral(scratch: Db):
    """ADR 0012. The bridge protects the measure column and not the attribute beside it.

    Asserted rather than lamented, because it is the half of D-0001's argument that is false
    and a reader who trusts the entry needs to meet it here rather than in a report.
    """
    trapped = _total(
        scratch,
        "SELECT sum(p.parent_size) FROM dar__uss._bridge AS b "
        "INNER JOIN dar__uss.parent AS p ON b.parent_key = p.parent_key "
        "WHERE b._event = 'occurred'",
    )
    assert trapped == Decimal("251.25"), (
        "summing the peripheral's attribute multiplies it once per child -- 100.50 twice and "
        "50.25 once. The measure column returns 150.75 for the same shape"
    )

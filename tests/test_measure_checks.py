"""One measure is non-null on its own event's rows and nowhere else, asserted on the real build.

`tests/test_fan_out.py` proves the property on a warehouse it builds itself, with numbers. This
is the same property stated as a mechanism and carried into every build: a measure that appeared
on another event's rows would be summed there, and the sum would still look like a number.

The distinction that matters here is EVENT and not stage. Two events on one entity share a stage
-- a parent that happened and a parent that finished are both `_stage = 'parent'` -- so a check
written per stage would let one of them carry the other's measure and report nothing. Every test
below that could pass under a per-stage check is marked.
"""

from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from adss.checks import measure_check_names, measure_checks
from adss.model import read_model
from adss.uss import read_uss

Db = duckdb.DuckDBPyConnection

FIXTURES = Path(__file__).parent / "fixtures" / "dab"

SIZE = "_measure__parent__size_parents_units"
HAPPENED = "_measure__parent__happened_parents_count"
FINISHED = "_measure__parent__finished_parents_count"
WEIGHT = "_measure__child__weight_children_units"

COLUMNS = (HAPPENED, SIZE, FINISHED, "_measure__child__occurred_children_count", WEIGHT)


def declarations():
    model = read_model(FIXTURES / "model.yaml")
    return model, read_uss(FIXTURES / "uss.yaml", model)


def checks() -> dict[str, str]:
    return measure_checks(declarations()[1])


def warehouse(connection: Db) -> None:
    """The bridge a measure check reads, empty. Stage and event are separate columns."""
    connection.execute("CREATE SCHEMA dar__uss")
    measures = ", ".join(f"{column} DECIMAL(28, 8)" for column in COLUMNS)
    connection.execute(
        f"CREATE TABLE dar__uss._bridge (_stage VARCHAR, _event VARCHAR, {measures})"
    )


def row(connection: Db, stage: str, event: str, **values: object) -> None:
    held = [values.get(column) for column in COLUMNS]
    marks = ", ".join(["?"] * (len(COLUMNS) + 2))
    connection.execute(f"INSERT INTO dar__uss._bridge VALUES ({marks})", [stage, event, *held])


def answer(connection: Db, column: str) -> int:
    body = "\n".join(
        line
        for line in checks()[f"{column.removeprefix('_')}__isolated"].splitlines()
        if not line.lstrip().startswith("--")
    )
    found = connection.execute(body).fetchone()
    assert found is not None
    return int(found[0])


@pytest.fixture
def scratch(tmp_path: Path) -> Iterator[Db]:
    connection = duckdb.connect(str(tmp_path / "scratch.duckdb"))
    warehouse(connection)
    yield connection
    connection.close()


def test_there_is_one_check_per_measure_named_for_the_column_it_protects():
    written = checks()
    _, uss = declarations()
    for _, _, column in uss.measure_columns():
        assert f"{column.removeprefix('_')}__isolated" in written
    assert len(written) == len(uss.measure_columns()), "no measure is checked twice or not at all"
    assert set(measure_check_names(uss)) == {f"{name}.sql" for name in written}


def test_a_measure_on_its_own_events_rows_and_nowhere_else_is_not_a_leak(scratch: Db):
    row(scratch, "parent", "happened", **{HAPPENED: 1, SIZE: 100})
    row(scratch, "parent", "finished", **{FINISHED: 1})
    row(scratch, "child", "occurred", **{WEIGHT: 5})
    for column in COLUMNS:
        assert answer(scratch, column) == 0, column


def test_a_measure_carried_onto_a_finer_stages_row_is_a_leak(scratch: Db):
    """The fan-out shape: the child row carries the parent's size, and summing doubles it."""
    row(scratch, "parent", "happened", **{HAPPENED: 1, SIZE: 100})
    row(scratch, "child", "occurred", **{WEIGHT: 5, SIZE: 100})
    assert answer(scratch, SIZE) == 1


def test_a_measure_carried_onto_another_event_of_the_same_stage_is_a_leak(scratch: Db):
    """A per-STAGE check cannot see this one: both rows are `_stage = 'parent'`.

    It is the likelier defect of the two -- one entity with two events is what slice 3 built,
    and every branch of the union comes off the same stage's CTE.
    """
    row(scratch, "parent", "happened", **{HAPPENED: 1, SIZE: 100})
    row(scratch, "parent", "finished", **{FINISHED: 1, SIZE: 100})
    assert answer(scratch, SIZE) == 1
    assert answer(scratch, HAPPENED) == 0, "the other measures are unaffected"


def test_a_null_on_the_measures_own_row_is_not_a_leak(scratch: Db):
    """A sum over an attribute that is null is null, and that is data rather than a defect."""
    row(scratch, "parent", "happened", **{HAPPENED: 1, SIZE: None})
    assert answer(scratch, SIZE) == 0


def test_a_zero_is_a_leak_where_a_null_belongs(scratch: Db):
    """Nothing here reads the value. A zero copied down survives every sum unchanged and is
    invisible in an answer -- until somebody counts the rows a measure appears on."""
    row(scratch, "parent", "happened", **{HAPPENED: 1, SIZE: 100})
    row(scratch, "child", "occurred", **{WEIGHT: 5, SIZE: 0})
    assert answer(scratch, SIZE) == 1

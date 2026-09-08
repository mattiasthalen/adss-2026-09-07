"""The inherited date, executed rather than read. ADR 0009.

Every other test of this mechanism asserts over the generated SQL's text. That proves the
emitter said what was expected and not that the SQL means it -- and two mutations of the as-of
join survive every text assertion in the suite: taking the parent's latest version instead of the
one in force, and taking a version whose date is null.

Neither is visible in the real warehouse, where every entity has exactly one version, so this
builds one that has more.
"""

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import duckdb
import pytest

from adss.model import read_model
from adss.uss import bridge_sql, read_uss
from support import engine_objects

Db = duckdb.DuckDBPyConnection

FIXTURES = Path(__file__).parent / "fixtures" / "dab"

FIRST, LATER = "2026-01-01", "2026-03-09"
# Three observations of the parent and two of the child, interleaved: the child observed at T2
# must see the parent as it was at T1, not as it became at T3.
T1, T2, T3, T4 = "2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04"


def parent(connection: Db, at: str, happened: str | None) -> None:
    connection.execute(
        'INSERT INTO dab."view_PARENT_hist" VALUES (?, ?, ?, ?, ?, ?, NULL)',
        ["P1", at, "P1", happened, "P1", 1],
    )


def child(connection: Db, key: str, at: str) -> None:
    connection.execute(
        'INSERT INTO dab."view_CHILD_hist" VALUES (?, ?, ?, ?, ?)', [key, at, key, at, 1]
    )
    connection.execute(
        'INSERT INTO dab."v_CHILD_POINTS_AT_PARENT" VALUES (?, ?, ?, ?, ?, ?)',
        [key, "P1", "CHILD_POINTS_AT_PARENT", at, at, "Y"],
    )


def reached(connection: Db) -> dict[str, date | None]:
    model = read_model(FIXTURES / "model.yaml")
    uss = read_uss(FIXTURES / "inherited_date.yaml", model)
    connection.execute(bridge_sql(model, uss).replace(";", ""))
    rows = connection.execute(
        "SELECT child_key, _event_date FROM dar__uss._bridge WHERE _event = 'reached'"
    ).fetchall()
    return {key: value for key, value in rows}


@pytest.fixture
def scratch(tmp_path: Path) -> Iterator[Db]:
    connection = duckdb.connect(str(tmp_path / "inherited.duckdb"))
    engine_objects(connection)
    yield connection
    connection.close()


def test_the_date_is_the_parent_version_in_force_when_the_child_was_observed(scratch: Db):
    """Two parent versions with different dates, and a child between them. Taking the latest
    version instead dates C1 by a correction that had not happened when C1 was seen."""
    parent(scratch, T1, FIRST)
    parent(scratch, T3, LATER)
    child(scratch, "C1", T2)
    child(scratch, "C2", T4)

    found = reached(scratch)
    assert found["C1"] == date(2026, 1, 1), "the version in force at T2, not the one at T3"
    assert found["C2"] == date(2026, 3, 9)


def test_a_parent_version_with_no_date_is_not_the_one_the_child_inherits(scratch: Db):
    """A source that blanks a date on a correction is an ordinary shape in a full change log.

    Resolved off that version the child's date is null, and ADR 0009's own rule then removes the
    row -- so a whole grain quietly leaves the bridge while the parent's own event stays dated.
    """
    parent(scratch, T1, FIRST)
    parent(scratch, T3, None)
    child(scratch, "C1", T4)

    found = reached(scratch)
    assert found.get("C1") == date(2026, 1, 1), (
        "the latest version that actually carries the date, not the latest version"
    )


def test_a_child_whose_parent_has_no_dated_version_at_all_has_no_row(scratch: Db):
    """The other half of the same rule, and the one ADR 0009 decided deliberately."""
    parent(scratch, T1, None)
    child(scratch, "C1", T2)
    assert reached(scratch) == {}

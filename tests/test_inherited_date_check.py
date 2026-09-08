"""A stage dated by a date it inherits agrees with the stage that owns that date. ADR 0009.

The date and the key are resolved in one CTE at one instant, which is the whole of ADR 0009. Two
things could break it and neither is visible in the warehouse: resolving the date at a different
instant than the key, and resolving it against a different version of the parent. Both show up
here, because the parent's own event carries the same date through an entirely different code
path -- its version CTE rather than the child's inherit CTE.

What this does not see is written into ADR 0009 rather than left to be discovered: a row dropped
because its inherited date did not resolve is absent, and an absent row disagrees with nothing.
"""

from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from adss.checks import inherited_date_check_names, inherited_date_checks
from adss.model import read_model
from adss.question import without_comments
from adss.uss import read_uss

Db = duckdb.DuckDBPyConnection

FIXTURES = Path(__file__).parent / "fixtures" / "dab"


def declarations(name: str = "inherited_date.yaml"):
    model = read_model(FIXTURES / "model.yaml")
    return model, read_uss(FIXTURES / name, model)


def checks(name: str = "inherited_date.yaml") -> dict[str, str]:
    return inherited_date_checks(*declarations(name))


def answer(connection: Db) -> int:
    found = connection.execute(without_comments(checks()["reached__inherited_date"])).fetchone()
    assert found is not None
    return int(found[0])


def row(connection: Db, event: str, child: str | None, parent: str | None, date: str) -> None:
    connection.execute(
        "INSERT INTO dar__uss._bridge VALUES (?, ?, ?, ?)", [event, child, parent, date]
    )


@pytest.fixture
def scratch(tmp_path: Path) -> Iterator[Db]:
    connection = duckdb.connect(str(tmp_path / "scratch.duckdb"))
    connection.execute("CREATE SCHEMA dar__uss")
    connection.execute(
        "CREATE TABLE dar__uss._bridge "
        "(_event VARCHAR, child_key VARCHAR, parent_key VARCHAR, _event_date DATE)"
    )
    yield connection
    connection.close()


def test_a_check_exists_only_where_the_parent_has_an_event_on_the_same_date():
    """Without one there is nothing independent to compare against, and a check that derives
    what it expects from the generator agrees with a broken generator."""
    written = checks()
    assert set(written) == {"reached__inherited_date"}, "one event inherits a date; three do not"
    assert inherited_date_check_names(*declarations()) == ("reached__inherited_date.sql",)
    assert checks("uss.yaml") == {}, "no event in the neutral fixture inherits a date"


def test_two_stages_carrying_the_same_inherited_date_do_not_disagree(scratch: Db):
    row(scratch, "happened", None, "P1", "2026-01-01")
    row(scratch, "reached", "C1", "P1", "2026-01-01")
    row(scratch, "reached", "C2", "P1", "2026-01-01")
    assert answer(scratch) == 0


def test_a_stage_dated_from_a_different_version_of_the_parent_is_caught(scratch: Db):
    """The failure ADR 0009 is about: the key from one instant and the date from another."""
    row(scratch, "happened", None, "P1", "2026-01-01")
    row(scratch, "reached", "C1", "P1", "2026-01-01")
    row(scratch, "reached", "C2", "P1", "2026-03-09")
    assert answer(scratch) == 1


def test_a_row_that_inherited_nothing_is_not_a_disagreement(scratch: Db):
    """It has no parent to disagree with. ADR 0009 makes such a row absent from the bridge
    entirely, so this is belt and braces rather than the case the check is for."""
    row(scratch, "reached", "C9", None, "2026-01-01")
    assert answer(scratch) == 0


def test_another_stages_rows_are_not_compared(scratch: Db):
    """`occurred` is dated by the child's own date and may differ from its parent's freely."""
    row(scratch, "happened", None, "P1", "2026-01-01")
    row(scratch, "occurred", "C1", "P1", "2026-07-07")
    assert answer(scratch) == 0

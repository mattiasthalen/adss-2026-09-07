"""A composed key has as many distinct values as the source key it was composed from. ADR 0010.

The separator argument is a prediction. This is the measurement, and it runs on the data that
actually landed: the parts are counted as a tuple, the composition is counted as a string, and a
difference means two source rows became one entity.

Run against the shape ADR 0010 names -- a separator-less concatenation over parts whose lengths
vary -- because a check that has only ever been seen to pass is not known to be capable of
failing.
"""

from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from adss.checks import composed_key_check_names, composed_key_checks
from adss.contract import Contract, read_contract
from adss.mapping import read_mapping
from adss.question import without_comments

Db = duckdb.DuckDBPyConnection

FIXTURES = Path(__file__).parent / "fixtures"
COMPOSITE = read_contract(FIXTURES / "contracts" / "composite_key.yaml")
SINGLE = read_contract(FIXTURES / "contracts" / "parent.yaml")


def checks(mapping: str, contract: Contract = COMPOSITE) -> dict[str, str]:
    return composed_key_checks(
        [read_mapping(FIXTURES / "mappings" / f"{mapping}.yaml")], [contract]
    )


def answer(connection: Db, mapping: str) -> int:
    written = checks(mapping)
    found = connection.execute(without_comments(next(iter(written.values())))).fetchone()
    assert found is not None
    return int(found[0])


@pytest.fixture
def scratch(tmp_path: Path) -> Iterator[Db]:
    connection = duckdb.connect(str(tmp_path / "scratch.duckdb"))
    connection.execute("CREATE SCHEMA das__staged")
    connection.execute(
        f"CREATE TABLE das__staged.{COMPOSITE.table}__current "
        f"(parent_id INTEGER, child_index INTEGER)"
    )
    yield connection
    connection.close()


def test_a_mapping_over_a_composite_source_key_is_checked_and_one_over_a_single_key_is_not():
    """Nothing to compare when the source key is one column: the mapping just names it."""
    assert set(checks("composed_key")) == {"parent__composed_key"}
    assert checks("good", SINGLE) == {}
    assert composed_key_check_names(
        [read_mapping(FIXTURES / "mappings" / "composed_key.yaml")], [COMPOSITE]
    ) == ("parent__composed_key.sql",)


def test_parts_that_cannot_collide_are_not_a_collision(scratch: Db):
    scratch.execute(f"INSERT INTO das__staged.{COMPOSITE.table}__current VALUES (1, 23), (12, 3)")
    assert answer(scratch, "composed_key") == 0


def test_a_separator_less_composition_over_parts_of_varying_length_is_caught(scratch: Db):
    """(1, 23) and (12, 3) are two lines. Concatenated without a separator they are one, and
    the entity that vanishes takes its measures with it."""
    scratch.execute(f"INSERT INTO das__staged.{COMPOSITE.table}__current VALUES (1, 23), (12, 3)")
    assert answer(scratch, "collides") == 1


def test_a_separator_less_composition_over_parts_that_happen_not_to_collide_passes(scratch: Db):
    """The check measures this data rather than the separator, which is ADR 0010's whole point:
    it fires on what landed, not on what somebody predicted would land."""
    scratch.execute(f"INSERT INTO das__staged.{COMPOSITE.table}__current VALUES (1, 2), (3, 4)")
    assert answer(scratch, "collides") == 0


def test_an_empty_source_is_not_a_collision(scratch: Db):
    """Zero distinct parts and zero distinct keys agree, which is what an empty table means."""
    assert answer(scratch, "composed_key") == 0

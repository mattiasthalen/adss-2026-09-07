"""The checks that carry half of ADR 0006's argument, run against the shapes they exist to catch.

The cardinality of an edge cannot be read off the model -- the language has nowhere to state
it -- and it cannot be read off the data, which is allowed to be many-to-many. So it is
inferred from the mapping and pinned by these checks, and the check is not decoration on top
of the inference: it is the half the inference cannot make.

Nothing else can catch a weakened one. `adss dar generate --check` compares the committed SQL
to the same generator, so it agrees with a weakened generator; and a weakened check passes
trivially at `adss check`. So each one is run here against a warehouse built to fail it, and
against one built to pass it. A check that cannot fail is not a check.
"""

from pathlib import Path

import duckdb
import pytest

from adss.checks import relationship_checks
from adss.model import read_model

NEUTRAL = Path(__file__).parent / "fixtures" / "dab" / "model.yaml"

EDGE = "child_points_at_parent"
NAME = "CHILD_POINTS_AT_PARENT"


def checks() -> dict[str, str]:
    return relationship_checks(read_model(NEUTRAL))


def warehouse(connection: duckdb.DuckDBPyConnection) -> None:
    """The objects a relationship check reads, empty. Shaped as the engine shapes them."""
    connection.execute("CREATE SCHEMA dab")
    connection.execute("CREATE SCHEMA dar__uss")
    for edge, source, target in (
        (NAME, "CHILD", "PARENT"),
        ("CHILD_SITS_BESIDE_NEIGHBOUR", "CHILD", "NEIGHBOUR"),
    ):
        connection.execute(
            f'CREATE TABLE dab."v_{edge}" ('
            f'  "{source}_key" VARCHAR, "{target}_key" VARCHAR, rel_name VARCHAR,'
            f"  eff_tmstp TIMESTAMP, ver_tmstp TIMESTAMP, row_st VARCHAR)"
        )
    connection.execute(
        "CREATE TABLE dar__uss._bridge ("
        "  _stage VARCHAR, child_key VARCHAR, parent_key VARCHAR, neighbour_key VARCHAR)"
    )
    for peripheral in ("parent", "neighbour", "child"):
        connection.execute(f"CREATE TABLE dar__uss.{peripheral} ({peripheral}_key VARCHAR)")


def answer(connection: duckdb.DuckDBPyConnection, check: str) -> int:
    body = "\n".join(
        line for line in checks()[check].splitlines() if not line.lstrip().startswith("--")
    )
    found = connection.execute(body).fetchone()
    assert found is not None
    return int(found[0])


@pytest.fixture
def scratch(tmp_path: Path):
    connection = duckdb.connect(str(tmp_path / "scratch.duckdb"))
    warehouse(connection)
    yield connection
    connection.close()


def pair(connection, child: str, parent: str, at: str, wrote: str = "2026-01-01", st: str = "Y"):
    connection.execute(
        f'INSERT INTO dab."v_{NAME}" VALUES (?, ?, ?, ?, ?, ?)',
        [child, parent, NAME, at, wrote, st],
    )


def test_there_is_one_set_of_checks_per_declared_edge():
    written = checks()
    model = read_model(NEUTRAL)
    for edge in model.relationships:
        for suffix in ("one_target", "loaded", "resolves"):
            assert f"{edge.id.lower()}__{suffix}" in written
    assert len(written) == len(model.relationships) * 3, "no edge is checked twice or not at all"


def test_every_check_reads_only_open_pairs_of_its_own_relationship():
    for name, sql in checks().items():
        if name.endswith("__resolves"):
            continue
        assert "rel_name = '" in sql, f"{name} must name the relationship, never a type key"
        assert "row_st = 'Y'" in sql, f"{name} must ignore a retracted pair"
        assert "type_key" not in sql


def test_one_target_fails_when_a_source_has_two_targets_at_one_instant(scratch):
    """The tie the engine's own rank() would return twice, doubling a measure."""
    pair(scratch, "CH1", "P1", "2026-01-01")
    pair(scratch, "CH2", "P2", "2026-01-01")
    assert answer(scratch, f"{EDGE}__one_target") == 0, "one target each is not an ambiguity"

    pair(scratch, "CH1", "P9", "2026-01-01")
    assert answer(scratch, f"{EDGE}__one_target") == 1


def test_one_target_accepts_a_source_whose_target_changed_over_time(scratch):
    """Two parents at DIFFERENT instants is history, not ambiguity, and must not be refused."""
    pair(scratch, "CH1", "P1", "2026-01-01")
    pair(scratch, "CH1", "P2", "2026-02-01")
    assert answer(scratch, f"{EDGE}__one_target") == 0


def test_one_target_ignores_a_retracted_pair(scratch):
    pair(scratch, "CH1", "P1", "2026-01-01")
    pair(scratch, "CH1", "P9", "2026-01-01", st="N")
    assert answer(scratch, f"{EDGE}__one_target") == 0


def test_one_target_ignores_another_relationships_pairs(scratch):
    pair(scratch, "CH1", "P1", "2026-01-01")
    scratch.execute(
        f'INSERT INTO dab."v_{NAME}" VALUES (?, ?, ?, ?, ?, ?)',
        ["CH1", "P9", "SOMETHING_ELSE", "2026-01-01", "2026-01-01", "Y"],
    )
    assert answer(scratch, f"{EDGE}__one_target") == 0


def test_loaded_fails_when_a_declared_edge_produced_no_pair_at_all(scratch):
    """What a source_table the engine could not match looks like: nothing, in silence."""
    assert answer(scratch, f"{EDGE}__loaded") == 1

    pair(scratch, "CH1", "P1", "2026-01-01")
    assert answer(scratch, f"{EDGE}__loaded") == 0


def test_loaded_is_not_satisfied_by_a_retracted_pair(scratch):
    pair(scratch, "CH1", "P1", "2026-01-01", st="N")
    assert answer(scratch, f"{EDGE}__loaded") == 1


def test_resolves_fails_when_an_inherited_key_names_no_row_in_the_peripheral(scratch):
    """What a target expression of the wrong shape looks like: pairs that join to nothing."""
    scratch.execute("INSERT INTO dar__uss.parent VALUES ('P1')")
    scratch.execute("INSERT INTO dar__uss._bridge VALUES ('child', 'CH1', 'P1', NULL)")
    assert answer(scratch, f"{EDGE}__resolves") == 0

    scratch.execute("INSERT INTO dar__uss._bridge VALUES ('child', 'CH2', 'P404', NULL)")
    assert answer(scratch, f"{EDGE}__resolves") == 1


def test_resolves_accepts_a_row_that_inherited_nothing(scratch):
    """A child with no parent keeps its bridge row and a null key. That is not a dangling key."""
    scratch.execute("INSERT INTO dar__uss._bridge VALUES ('child', 'CH6', NULL, NULL)")
    assert answer(scratch, f"{EDGE}__resolves") == 0


def test_resolves_looks_only_at_the_stage_that_inherits(scratch):
    """Every other stage emits a typed NULL for this key, and a null is not a dangling key."""
    scratch.execute("INSERT INTO dar__uss._bridge VALUES ('parent', NULL, NULL, NULL)")
    assert answer(scratch, f"{EDGE}__resolves") == 0

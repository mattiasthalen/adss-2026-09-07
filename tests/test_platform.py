"""The seam between this system and the platform it happens to run on."""

import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from adss.platform import (
    WarehouseHeldError,
    exclusive,
    install,
    reading,
    require_detached,
    statements,
)

COMMENTED = """-- Generated from somewhere. Do not edit.
CREATE SCHEMA IF NOT EXISTS probe;

-- Generated from somewhere. Do not edit.
CREATE OR REPLACE VIEW probe.thing AS
SELECT 1 AS one;
"""

# A separate process trying to write. This is what the modelling engine is.
CHILD_WRITE = (
    "import duckdb, sys; "
    "duckdb.connect(sys.argv[1]).execute('CREATE TABLE IF NOT EXISTS t (x INTEGER)')"
)


def test_a_statement_that_opens_with_a_comment_is_still_a_statement():
    assert len(statements(COMMENTED)) == 2, "every generated statement opens with a comment"


def test_trailing_blank_space_is_not_mistaken_for_a_statement():
    assert statements("SELECT 1;\n\n\n") == ["SELECT 1"]


def test_a_comment_with_no_sql_after_it_is_not_executed():
    assert statements("-- nothing here\n") == []


def test_installing_runs_every_statement(tmp_path: Path):
    with exclusive(tmp_path / "w.duckdb") as connection:
        assert install(connection, COMMENTED) == 2
        assert connection.execute("SELECT one FROM probe.thing").fetchone() == (1,)


def write_from_a_separate_process(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", CHILD_WRITE, str(path)], capture_output=True, text=True, check=False
    )


def test_a_separate_process_cannot_write_while_this_one_holds_the_warehouse(tmp_path: Path):
    """This is the real failure, reproduced without the engine.

    DuckDB's lock is per process, so a subprocess is refused while we hold the file -- and
    the modelling engine is a subprocess. It reports the refusal as "the framework is not
    installed", which is not what went wrong, so the guard has to be ours.
    """
    path = tmp_path / "w.duckdb"
    with exclusive(path) as connection:
        connection.execute("CREATE TABLE t (x INTEGER)")
        assert write_from_a_separate_process(path).returncode != 0

    assert write_from_a_separate_process(path).returncode == 0, "closing releases the lock"


def test_invoking_a_separate_process_while_holding_the_warehouse_is_refused(tmp_path: Path):
    path = tmp_path / "w.duckdb"
    with exclusive(path), pytest.raises(WarehouseHeldError, match="framework is not installed"):
        require_detached(path, "an-engine")

    require_detached(path, "an-engine")


def test_a_reader_also_holds_the_warehouse_against_a_separate_process(tmp_path: Path):
    path = tmp_path / "w.duckdb"
    with exclusive(path) as connection:
        connection.execute("CREATE TABLE t (x INTEGER)")

    with reading(path), pytest.raises(WarehouseHeldError):
        require_detached(path, "an-engine")


def test_a_reader_opens_without_taking_the_write_lock(tmp_path: Path):
    path = tmp_path / "w.duckdb"
    with exclusive(path) as connection:
        connection.execute("CREATE TABLE t AS SELECT 1 AS x")
    with reading(path) as connection:
        assert connection.execute("SELECT x FROM t").fetchone() == (1,)
        with pytest.raises(duckdb.Error):
            connection.execute("CREATE TABLE u (x INTEGER)")


def test_two_overlapping_opens_hold_the_guard_until_both_are_closed(tmp_path: Path):
    """A count, not a flag. Closing the inner one must not release the outer one's lock."""
    path = tmp_path / "w.duckdb"
    with exclusive(path):
        with exclusive(path):
            pass
        # The inner one has closed; the outer one is still holding the file.
        with pytest.raises(WarehouseHeldError):
            require_detached(path, "an-engine")
    require_detached(path, "an-engine")

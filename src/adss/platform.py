"""The one seam between this system and the platform it happens to run on.

Everything that knows the warehouse is a DuckDB file knows it here. The blueprint's first
promise is that every tool is replaceable, and this module is where that promise is kept or
broken.

The warehouse has exactly one writer. That is not a preference: the modelling engine fails
when anything else holds the file -- read-only connections included -- and the error it
reports says the framework is not installed, which is not what went wrong. Conventions
section 9.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb

BUSY = (
    "the warehouse is busy: another process has {path} open. Close any notebook, shell or "
    "pipeline holding it and try again. If an engine tells you the framework is not "
    "installed, this is what it means."
)

HELD = (
    "this process is holding {path} open, so {tool} cannot take the lock it needs. "
    "DuckDB's lock is per process: a subprocess is refused while we hold the file. Close "
    "the connection before invoking it. Note that {tool} reports this as 'the framework is "
    "not installed', which is not what went wrong."
)


class WarehouseBusyError(Exception):
    """Something else holds the warehouse. Nothing is broken; something else is reading."""


class WarehouseHeldError(Exception):
    """We are holding the warehouse while asking a separate process to write to it."""


# Warehouses this process currently has open. An external engine runs as a subprocess and is
# refused while any of these is live, so the rule is enforced here rather than remembered.
_open: set[Path] = set()


def require_detached(path: Path, tool: str) -> None:
    """Refuse to invoke a separate process against a warehouse this one is holding."""
    if path.absolute() in _open:
        raise WarehouseHeldError(HELD.format(path=path, tool=tool))


@contextmanager
def exclusive(path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    """Open the warehouse for writing, refusing rather than waiting if it is held."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        connection = duckdb.connect(str(path))
    except duckdb.IOException as busy:
        raise WarehouseBusyError(BUSY.format(path=path)) from busy
    _open.add(path.absolute())
    try:
        yield connection
    finally:
        connection.close()
        _open.discard(path.absolute())


@contextmanager
def reading(path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    """Open the warehouse read-only, which is how every destination opens it.

    A reader holding a writable handle blocks the next build, and the build is the thing
    that cannot be worked around.
    """
    connection = duckdb.connect(str(path), read_only=True)
    _open.add(path.absolute())
    try:
        yield connection
    finally:
        connection.close()
        _open.discard(path.absolute())


def statements(sql: str) -> list[str]:
    """Split generated SQL into executable statements.

    Every generated statement opens with a comment saying which artefact it came from, so
    "does not start with --" is exactly the wrong test: it would skip all of them.
    """
    chunks = [chunk.strip() for chunk in sql.split(";\n")]
    return [
        chunk
        for chunk in chunks
        if any(line.strip() and not line.strip().startswith("--") for line in chunk.splitlines())
    ]


def install(connection: duckdb.DuckDBPyConnection, sql: str) -> int:
    """Run generated SQL, one statement at a time so a failure names the statement."""
    executed = statements(sql)
    for statement in executed:
        connection.execute(statement)
    return len(executed)

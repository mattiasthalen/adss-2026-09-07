"""Whether the framework is already in a warehouse is asked of the warehouse.

The engine answers that question by failing -- a second install exits non-zero telling you to
drop its schemas -- which is right for a person and wrong for a build, since a build has to be
runnable twice. So the question is put to the warehouse instead.
"""

from pathlib import Path

import duckdb
import yaml

from adss.engine import is_installed, metadata_schema


def _connections(path: Path, schema: str) -> Path:
    declared = {"connections": {"dev": {"type": "duckdb", "metadata_schema": schema}}}
    path.write_text(yaml.safe_dump(declared))
    return path


def test_the_bookkeeping_schema_is_read_from_the_profile_that_declares_it(tmp_path: Path):
    connections = _connections(tmp_path / "connections.yaml", "meta__somewhere")
    assert metadata_schema(connections) == "meta__somewhere"


def test_a_warehouse_that_does_not_exist_yet_holds_nothing(tmp_path: Path):
    # Asking must not create the file: an empty warehouse conjured here would be handed to the
    # engine, which then has to be told to install into something that already exists.
    warehouse = tmp_path / "absent.duckdb"
    assert is_installed(warehouse, "meta__somewhere") is False
    assert not warehouse.exists()


def test_a_warehouse_without_that_schema_is_not_installed(tmp_path: Path):
    warehouse = tmp_path / "w.duckdb"
    connection = duckdb.connect(str(warehouse))
    connection.execute("CREATE SCHEMA elsewhere")
    connection.execute("CREATE TABLE elsewhere.present (one INTEGER)")
    connection.close()
    assert is_installed(warehouse, "meta__somewhere") is False


def test_a_warehouse_carrying_a_table_in_that_schema_is_installed(tmp_path: Path):
    warehouse = tmp_path / "w.duckdb"
    connection = duckdb.connect(str(warehouse))
    connection.execute("CREATE SCHEMA meta__somewhere")
    connection.execute("CREATE TABLE meta__somewhere.bookkeeping (one INTEGER)")
    connection.close()
    assert is_installed(warehouse, "meta__somewhere") is True


def test_an_empty_schema_is_not_an_installation(tmp_path: Path):
    # The engine creates its schema and then fills it. A run interrupted between the two
    # leaves a schema with nothing in it, and skipping the install then would leave the
    # warehouse permanently half-built.
    warehouse = tmp_path / "w.duckdb"
    connection = duckdb.connect(str(warehouse))
    connection.execute("CREATE SCHEMA meta__somewhere")
    connection.close()
    assert is_installed(warehouse, "meta__somewhere") is False

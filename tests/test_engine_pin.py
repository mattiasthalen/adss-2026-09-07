"""The engine is pinned by content, because it has no version to pin by."""

from pathlib import Path

import pytest

from adss.engine import Engine, EnginePinError
from adss.project import Project

PROJECT = Project.discover(Path(__file__).resolve().parent)


def engine() -> Engine:
    return Engine(
        binary=PROJECT.engine_binary,
        working_directory=PROJECT.dab,
        warehouse=PROJECT.warehouse,
    )


def test_the_vendored_binary_is_the_one_this_repository_recorded():
    assert (
        engine().verify()
        == (PROJECT.engine_binary.parent / "daana-cli.sha256").read_text().split()[0]
    )


def test_a_binary_that_is_not_the_recorded_one_is_refused(tmp_path: Path):
    binary = tmp_path / "engine"
    binary.write_bytes(b"not the engine")
    (tmp_path / "engine.sha256").write_text(f"{'0' * 64}  engine\n")
    impostor = Engine(binary=binary, working_directory=tmp_path, warehouse=tmp_path / "w.duckdb")
    with pytest.raises(EnginePinError, match="pinned by content"):
        impostor.verify()


def test_what_the_engine_calls_itself_is_recorded_beside_it():
    recorded = (PROJECT.engine_binary.parent / "daana-cli.version").read_text().strip()
    assert recorded, "an engine with no version needs its self-report written down"
    assert "commit" in recorded, "the commit is the only thing that distinguishes two nightlies"

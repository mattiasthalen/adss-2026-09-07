"""The engine is pinned by content, because it has no version to pin by.

The vendored binary itself is not hashed here: it is a large git-LFS object that a fresh
checkout need not have pulled, and conventions section 6 says this suite touches no binary.
`Engine.run` verifies before every invocation, so the real binary is checked on every build.
"""

from pathlib import Path

import pytest

from adss.engine import Engine, EnginePinError
from adss.project import Project

PROJECT = Project.discover(Path(__file__).resolve().parent)


def test_a_binary_that_is_not_the_recorded_one_is_refused(tmp_path: Path):
    binary = tmp_path / "engine"
    binary.write_bytes(b"not the engine")
    (tmp_path / "engine.sha256").write_text(f"{'0' * 64}  engine\n")
    impostor = Engine(binary=binary, working_directory=tmp_path, warehouse=tmp_path / "w.duckdb")
    with pytest.raises(EnginePinError, match="pinned by content"):
        impostor.verify()


def test_a_binary_that_matches_its_record_is_accepted(tmp_path: Path):
    import hashlib

    binary = tmp_path / "engine"
    binary.write_bytes(b"pretend this is an engine")
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    (tmp_path / "engine.sha256").write_text(f"{digest}  engine\n")
    engine = Engine(binary=binary, working_directory=tmp_path, warehouse=tmp_path / "w.duckdb")
    assert engine.verify() == digest


def test_what_the_engine_calls_itself_is_recorded_beside_it():
    recorded = (PROJECT.engine_binary.parent / "daana-cli.version").read_text().strip()
    assert recorded, "an engine with no version needs its self-report written down"
    assert "commit" in recorded, "the commit is the only thing that distinguishes two nightlies"

"""Generated SQL is held to the same standard as hand-written SQL. Conventions section 3.

Substring assertions prove an emitter said what we expected. They do not prove it emitted
valid, well-formed SQL -- only the real linter does that, so it runs here over everything
every emitter produces.
"""

import subprocess
from pathlib import Path

import pytest

from adss.contract import read_contract
from adss.das import current_view_sql, raw_view_sql, staged_view_sql

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"
ROOT = Path(__file__).resolve().parent.parent


def emitters() -> dict[str, str]:
    contract = read_contract(FIXTURES / "parent.yaml")
    return {
        "raw": raw_view_sql(contract, Path("/somewhere/lake")),
        "staged": staged_view_sql(contract),
        "current": current_view_sql(contract),
    }


@pytest.mark.parametrize("name", sorted(emitters()))
def test_emitted_sql_passes_the_repository_linter(name: str, tmp_path: Path):
    written = tmp_path / f"{name}.sql"
    written.write_text(emitters()[name])
    result = subprocess.run(
        ["sqlfluff", "lint", "--config", str(ROOT / ".sqlfluff"), str(written)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout

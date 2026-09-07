"""Generated SQL is held to the same standard as hand-written SQL. Conventions section 3.

Substring assertions prove an emitter said what we expected. They do not prove it emitted
valid, well-formed SQL -- only the real linter does that, so it runs here over everything
every emitter produces, laid out the way the generator lays it out before writing.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from adss.contract import read_contract
from adss.das import clock_check_sql, current_view_sql, key_check_sql, raw_view_sql, staged_view_sql
from adss.model import read_model
from adss.sqlformat import formatted
from adss.uss import bridge_sql, calendar_sql, peripheral_sql, read_uss

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"
ROOT = Path(__file__).resolve().parent.parent


def emitters() -> dict[str, str]:
    contract = read_contract(FIXTURES / "parent.yaml")
    dab = Path(__file__).parent / "fixtures" / "dab"
    model = read_model(dab / "model.yaml")
    uss = read_uss(dab / "uss.yaml", model)
    laid_out = {
        "raw": raw_view_sql(contract, Path("/somewhere/lake")),
        "staged": staged_view_sql(contract),
        "current": current_view_sql(contract),
        "clock_check": clock_check_sql(contract),
        "key_check": key_check_sql(contract),
        "bridge": bridge_sql(model, uss),
        "peripheral": peripheral_sql(model, "PARENT"),
        "calendar": calendar_sql(),
    }
    return {name: formatted(sql, ROOT / ".sqlfluff") for name, sql in laid_out.items()}


@pytest.mark.parametrize("name", sorted(emitters()))
def test_emitted_sql_passes_the_repository_linter(name: str, tmp_path: Path):
    written = tmp_path / f"{name}.sql"
    written.write_text(emitters()[name])
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sqlfluff",
            "lint",
            "--config",
            str(ROOT / ".sqlfluff"),
            str(written),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout

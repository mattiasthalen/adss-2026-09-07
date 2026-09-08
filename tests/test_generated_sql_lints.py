"""Generated SQL is held to the same standard as hand-written SQL. Conventions section 3.

Substring assertions prove an emitter said what we expected. They do not prove it emitted
valid, well-formed SQL -- only the real linter does that, so it runs here over everything
every emitter produces, laid out the way the generator lays it out before writing.
"""

import functools
import subprocess
import sys
from pathlib import Path

import pytest

from adss.checks import inherited_date_checks, measure_checks, relationship_checks
from adss.contract import read_contract
from adss.das import clock_check_sql, current_view_sql, key_check_sql, raw_view_sql, staged_view_sql
from adss.model import read_model
from adss.question import without_comments
from adss.sqlformat import formatted
from adss.uss import bridge_sql, calendar_sql, peripheral_sql, read_uss

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"
ROOT = Path(__file__).resolve().parent.parent


@functools.cache
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
        **{f"relationship_{n}": s for n, s in relationship_checks(model).items()},
        **{f"measure_{n}": s for n, s in measure_checks(uss).items()},
        **{
            f"inherited_{n}": s
            for n, s in inherited_date_checks(
                model, read_uss(dab / "inherited_date.yaml", model)
            ).items()
        },
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


def test_a_generated_check_still_runs_after_the_formatter_has_been_over_it():
    """The linter proves the SQL parses. Only running it proves the formatter left it valid.

    A composite key's check counts distinct tuples, and the parentheses that make that a tuple
    are exactly what a formatter removes as redundant -- turning `count(DISTINCT (a, b))` into
    `count(DISTINCT a, b)`, which DuckDB has no function for. The emitter was fixed for this in
    slice 1 and a later step in the same pipeline undid it, invisibly, because no contract had
    a composite key until slice 4. So the assertion has to be over the artefact that is
    actually executed, not the one that is emitted.
    """
    import duckdb

    contract = read_contract(FIXTURES / "composite_key.yaml")
    laid_out = formatted(key_check_sql(contract), ROOT / ".sqlfluff")
    body = without_comments(laid_out)

    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA das__staged")
    connection.execute(
        f"CREATE TABLE das__staged.{contract.table}__current "
        f"({', '.join(f'{key} INTEGER' for key in contract.primary_keys)})"
    )
    connection.execute(f"INSERT INTO das__staged.{contract.table}__current VALUES (1, 2), (1, 3)")
    assert connection.execute(body).fetchone() == (0,), "two distinct tuples are not a duplicate"
    connection.execute(f"INSERT INTO das__staged.{contract.table}__current VALUES (1, 2)")
    assert connection.execute(body).fetchone() == (1,), "and a repeated tuple is"
    connection.close()

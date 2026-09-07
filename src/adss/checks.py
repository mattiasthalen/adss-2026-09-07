"""What the built warehouse must contain, asserted against the real build.

Never against a stub: a check that passes against a fabricated warehouse tells you nothing
about the one that was built. Conventions section 6.

No SQL is written here and no source is named here. Every statement is a generated file, so
the linter sees it and so the machinery works for a source it has never met.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from adss.contract import read_contract
from adss.model import read_model
from adss.project import Project
from adss.question import read_questions, without_comments
from adss.uss import bridge_columns, read_uss


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing that is true or is not. A failing check names what it looked at."""

    check: str
    passed: bool
    detail: str


def _rows(connection: duckdb.DuckDBPyConnection, sql: str) -> list[tuple[object, ...]]:
    return [tuple(row) for row in connection.execute(without_comments(sql)).fetchall()]


def _zero(connection: duckdb.DuckDBPyConnection, sql: str) -> tuple[bool, str]:
    rows = _rows(connection, sql)
    value = rows[0][0] if rows and rows[0] else None
    return value == 0, f"{value}"


def run_checks(project: Project, connection: duckdb.DuckDBPyConnection) -> list[Finding]:
    findings: list[Finding] = []

    model = read_model(project.model)
    uss = read_uss(project.uss, model)
    described = [name for name, *_ in connection.execute("DESCRIBE dar__uss._bridge").fetchall()]
    expected = list(bridge_columns(model, uss))
    findings.append(
        Finding(
            "the bridge matches its published column contract",
            described == expected,
            f"built {described}, contract {expected}",
        )
    )

    # Every generated data check, over every contract. Growing the layer grows the checks.
    for path in sorted(project.checks_sql.glob("*.sql")):
        passed, detail = _zero(connection, path.read_text())
        findings.append(
            Finding(f"{path.stem}: nothing disagrees", passed, f"{detail} disagreements")
        )

    # The engine behaviours the generated layer is built on. If the vendor changes any of
    # them, this says so rather than the star schema quietly emptying.
    for entity in model.entities:
        for suffix in ("focal", "idfr"):
            rows = connection.execute(f'SELECT count(*) FROM dab."{entity.id}_{suffix}"').fetchone()
            findings.append(
                Finding(
                    f"dab.{entity.id}_{suffix} is still empty, as the generator assumes",
                    rows == (0,),
                    f"{rows} rows -- if this is no longer 0 the generator should read it",
                )
            )
        with_rel = [
            name
            for name, *_ in connection.execute(
                f'DESCRIBE dab."view_{entity.id}_with_rel"'
            ).fetchall()
        ]
        plain = [
            name for name, *_ in connection.execute(f'DESCRIBE dab."view_{entity.id}"').fetchall()
        ]
        findings.append(
            Finding(
                f"dab.view_{entity.id}_with_rel still carries no relationship key",
                with_rel == plain,
                f"with_rel {with_rel} vs plain {plain}",
            )
        )

    # The description table is where an ingestion-strategy defect would be visible, and the
    # only place: every presentation view hides it.
    for entity in model.entities:
        described_rows = connection.execute(
            f'SELECT count(*), count(DISTINCT ("{entity.id}_key", type_key, eff_tmstp)) '
            f'FROM dab."{entity.id}_desc"'
        ).fetchone()
        total, distinct = described_rows if described_rows else (None, None)
        findings.append(
            Finding(
                f"dab.{entity.id}_desc holds no duplicate versions",
                total == distinct,
                f"{total} rows, {distinct} distinct -- a growing gap is FULL ingestion "
                f"duplicating silently",
            )
        )

    for question in read_questions(project.questions):
        control = _rows(connection, question.staged_sql)
        answer = _rows(connection, question.uss_sql)
        findings.append(
            Finding(
                f"{question.id}: the source and the star schema agree",
                control == answer,
                f"{len(control)} control rows, {len(answer)} answer rows"
                + (
                    "" if control == answer else f"; first difference {_first_gap(control, answer)}"
                ),
            )
        )
    return findings


def contracts_of(project: Project) -> tuple[str, ...]:
    """Every contract this project declares. Used to generate the checks above."""
    return tuple(read_contract(path).table for path in project.contract_paths())


def _first_gap(control: list[tuple[object, ...]], answer: list[tuple[object, ...]]) -> str:
    for index, (left, right) in enumerate(zip(control, answer, strict=False)):
        if left != right:
            return f"row {index}: source {left} vs star {right}"
    return f"lengths differ: {len(control)} vs {len(answer)}"

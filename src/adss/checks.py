"""What the built warehouse must contain, asserted against the real build.

Never against a stub: a check that passes against a fabricated warehouse tells you nothing
about the one that was built. Conventions section 6.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

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

    disagreements = connection.execute(
        "SELECT count(*) FROM das__staged.orders WHERE extracted_on <> cast(extracted_at AS DATE)"
    ).fetchone()
    findings.append(
        Finding(
            "the partition key agrees with the observation clock",
            disagreements == (0,),
            f"{disagreements} rows disagree",
        )
    )

    for question in read_questions(project.root / "docs" / "questions"):
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


def _first_gap(control: list[tuple[object, ...]], answer: list[tuple[object, ...]]) -> str:
    for index, (left, right) in enumerate(zip(control, answer, strict=False)):
        if left != right:
            return f"row {index}: source {left} vs star {right}"
    return f"lengths differ: {len(control)} vs {len(answer)}"

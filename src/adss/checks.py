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
from adss.model import Model, read_model
from adss.names import Relation, Schema, crossing
from adss.project import Project
from adss.question import Status, read_questions, without_comments
from adss.uss import BRIDGE, bridge_columns, read_uss


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing that is true or is not. A failing check names what it looked at."""

    check: str
    passed: bool
    detail: str


def _rows(connection: duckdb.DuckDBPyConnection, sql: str) -> list[tuple[object, ...]]:
    return [tuple(row) for row in connection.execute(without_comments(sql)).fetchall()]


def _columns(connection: duckdb.DuckDBPyConnection, name: str) -> list[str]:
    return [column for column, *_ in connection.execute(f'DESCRIBE dab."{name}"').fetchall()]


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
        # `view_<E>_with_rel` is not one behaviour but two, and the name says neither. On an
        # edge's SOURCE side it is a passthrough. On its TARGET side it becomes a join back to
        # the source entity, carrying that entity's key AND all its attributes, one row per
        # source row -- so summing a target's own measure over it multiplies. Slice 1 asserted
        # the passthrough of every entity, which was only ever true because it had no edges.
        with_rel = _columns(connection, f"view_{entity.id}_with_rel")
        plain = _columns(connection, f"view_{entity.id}")
        inbound = [e for e in model.relationships if e.target_entity_id == entity.id]
        fanned = plain + [
            c for e in inbound for c in _columns(connection, f"view_{e.source_entity_id}")
        ]
        findings.append(
            Finding(
                f"dab.view_{entity.id}_with_rel is what a {'target' if inbound else 'source'} "
                f"side looks like",
                with_rel == fanned,
                f"with_rel {with_rel} vs expected {fanned} -- if this changed, the generator's "
                f"reason for never reading this view has changed with it",
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
        if question.status in (Status.DRAFT, Status.SUPERSEDED):
            findings.append(
                Finding(
                    f"{question.id}: not asked ({question.status})",
                    True,
                    "a draft is not finished and a superseded question is not asked any more; "
                    "running either would fail the build on something nobody is answering",
                )
            )
            continue
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


_EDGE = "-- Generated from dab/model.yaml. Do not edit; regenerate with `adss dar generate`."


def relationship_checks(model: Model) -> dict[str, str]:
    """One check per way an edge fails without saying so. ADR 0006.

    All three failures look identical in the built warehouse -- an inherited key that is null,
    or wrong, on rows that look like data rather than like a defect -- and none of them is
    reported by the engine at deploy, at execute, or by a question's acceptance queries.
    """
    generated: dict[str, str] = {}
    for edge in model.relationships:
        source = model.entity(edge.source_entity_id)
        target = model.entity(edge.target_entity_id)
        pairs = f'dab."v_{edge.id}"'
        open_pairs = (
            f"FROM {pairs} AS pair\nWHERE pair.rel_name = '{edge.id}'\n    AND pair.row_st = 'Y'"
        )
        name = edge.id.lower()

        # The generator resolves a tie with row_number(), so it can never fan out -- but
        # resolving a tie deterministically is still choosing arbitrarily between two answers.
        generated[f"{name}__one_target"] = (
            f"{_EDGE}\n"
            f"SELECT count(*) AS ambiguities\n"
            f"FROM (\n"
            f"    SELECT\n"
            f"        pair.{crossing(source.source_key)} AS source_key,\n"
            f"        pair.eff_tmstp AS observed_at\n"
            f"    {open_pairs}\n"
            f"    GROUP BY pair.{crossing(source.source_key)}, pair.eff_tmstp\n"
            f"    HAVING count(DISTINCT pair.{crossing(target.source_key)}) > 1\n"
            f") AS tied;\n"
        )

        # An edge that loaded nothing is what a mis-spelled M6 source_table looks like: the
        # engine skips the relationship in silence and every inherited key is null.
        generated[f"{name}__loaded"] = (
            f"{_EDGE}\n"
            f"SELECT count(*) AS unloaded\n"
            f"FROM (SELECT 1 AS declared) AS edge\n"
            f"WHERE NOT EXISTS (\n"
            f"    SELECT 1\n"
            f"    {open_pairs}\n"
            f");\n"
        )

        # And a target expression of the wrong shape loads pairs that join to nothing.
        generated[f"{name}__resolves"] = (
            f"{_EDGE}\n"
            f"SELECT count(*) AS dangling\n"
            f"FROM {BRIDGE.sql} AS b\n"
            f"LEFT JOIN {Relation(Schema.DAR_USS, target.object_name).sql} AS t\n"
            f"    ON b.{target.key_column} = t.{target.key_column}\n"
            f"WHERE b._stage = '{source.object_name}'\n"
            f"    AND b.{target.key_column} IS NOT NULL\n"
            f"    AND t.{target.key_column} IS NULL;\n"
        )
    return generated


def _first_gap(control: list[tuple[object, ...]], answer: list[tuple[object, ...]]) -> str:
    for index, (left, right) in enumerate(zip(control, answer, strict=False)):
        if left != right:
            return f"row {index}: source {left} vs star {right}"
    return f"lengths differ: {len(control)} vs {len(answer)}"

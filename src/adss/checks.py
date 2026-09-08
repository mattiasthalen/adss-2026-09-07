"""What the built warehouse must contain, asserted against the real build.

Never against a stub: a check that passes against a fabricated warehouse tells you nothing
about the one that was built. Conventions section 6.

No SQL is written here and no source is named here. Every statement is a generated file, so
the linter sees it and so the machinery works for a source it has never met.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import duckdb

from adss.contract import read_contract
from adss.model import Model, read_model
from adss.names import Relation, Schema, crossing
from adss.project import Project
from adss.question import Status, read_questions, without_comments
from adss.uss import BRIDGE, Uss, bridge_columns, read_uss


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing that is true or is not. A failing check names what it looked at."""

    check: str
    passed: bool
    detail: str


def _rows(connection: duckdb.DuckDBPyConnection, sql: str) -> list[tuple[object, ...]]:
    return [tuple(row) for row in connection.execute(without_comments(sql)).fetchall()]


def inexact(rows: Sequence[Sequence[object]]) -> list[str]:
    """The inexact types among these values, if any. Named so a test can reach it.

    A bool is an int in Python and exact, so it is not one of these; a Decimal is exact by
    construction; a float is not, and is the only one that can make two answers computed the
    same way disagree.
    """
    return sorted(
        {type(value).__name__ for row in rows for value in row if isinstance(value, float)}
    )


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

    # The one engine behaviour the whole as-of rule rests on, and the only one not pinned
    # until now: that `v_<edge>` hands over the RAW pairs. If a release added ranking inside
    # it, the rule ADR 0006 spends generated SQL to own would silently revert to the vendor's
    # "as of now", and every check and both questions would still pass. Pinned two ways: it
    # still exposes the columns only an unranked read has, and it still returns every row the
    # pair table holds for that relationship.
    for edge in model.relationships:
        exposed = _columns(connection, f"v_{edge.id}")
        findings.append(
            Finding(
                f"dab.v_{edge.id} still hands over the raw pairs",
                {"row_st", "ver_tmstp", "rel_name"} <= set(exposed),
                f"{exposed} -- the ranked view drops row_st and ver_tmstp, so losing them "
                f"here means this object has become a ranked one and the as-of rule is the "
                f"vendor's again",
            )
        )
        counted = connection.execute(
            f'SELECT (SELECT count(*) FROM dab."v_{edge.id}" WHERE rel_name = ?), '
            f'(SELECT count(*) FROM dab."{edge.source_entity_id}_{edge.target_entity_id}_x")',
            [edge.id],
        ).fetchone()
        through, raw = counted if counted else (None, None)
        findings.append(
            Finding(
                f"dab.v_{edge.id} filters nothing out of the pair table",
                through == raw,
                f"{through} through the view, {raw} in the pair table -- a gap means the view "
                f"has started ranking or filtering, and the generator ranks it a second time",
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
        # The comparison below is row by row, by value, which is exact only while every value
        # is. A float would make it order-dependent rather than wrong: DuckDB's sum over
        # doubles is not associative -- [0.1, 0.2, 0.3] sums to 0.6000000000000001 and the
        # same three reversed to 0.6 -- so two queries could sum one measure in two orders and
        # disagree by a bit, on some machines, some of the time. There is no such value today
        # and this is what says so. ADR 0007.
        loose = inexact((*control, *answer))
        findings.append(
            Finding(
                f"{question.id}: both answers hold only exact values",
                not loose,
                f"found {loose} -- a ratio belongs to whoever asks, not to a stored answer, "
                f"and an inexact value makes this comparison order-dependent",
            )
        )
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
    """Every contract this project declares, by the object it generates.

    Two commands write into `checks/` and each sweeps what neither generates, so each has to
    know the other's file names. This is how the DAR generator knows which files belong to a
    contract without reading contracts for anything else.
    """
    return tuple(read_contract(path).table for path in project.contract_paths())


def relationship_check_names(model: Model) -> tuple[str, ...]:
    """What relationship_checks would be called, without emitting or formatting any of it.

    The contract side of `checks/` only needs the names, to leave these files alone. Building
    the SQL for that would run the fixer over every check and throw the result away, which
    also makes a DAS command fail when the DAB model is unreadable.
    """
    return tuple(
        f"{edge.id.lower()}__{suffix}.sql"
        for edge in model.relationships
        for suffix in ("one_target", "loaded", "resolves")
    )


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


_MEASURE = "-- Generated from dab/uss.yaml. Do not edit; regenerate with `adss dar generate`."


def measure_check_names(uss: Uss) -> tuple[str, ...]:
    """What measure_checks would be called, without emitting or formatting any of it.

    The contract side of `checks/` only needs the names, to leave these files alone -- the same
    reason relationship_check_names exists, and the same cost: a DAS command now reads the
    declarations to learn what it must not delete.
    """
    return tuple(
        f"{column.removeprefix('_')}__isolated.sql" for _, _, column in uss.measure_columns()
    )


def measure_checks(uss: Uss) -> dict[str, str]:
    """One check per measure: it is non-null on its own event's rows and on no other. ADR 0012.

    This is the property D-0001 rests on, carried into every build. `tests/test_fan_out.py`
    proves it with numbers on a warehouse it builds; this asserts the mechanism on the warehouse
    that was actually built, where a wrong number would be believed.

    By EVENT and not by stage. Two events on one entity share a stage, so a per-stage check would
    let a parent's shipment measure sit on its placement row and report nothing -- and that is the
    likelier defect, since every branch of the union comes off the same stage's CTE.

    It counts leaks only. A measure that is null everywhere would pass here, and is not this
    check's to catch: a bridge that lost its rows disagrees with the source, which is what
    `adss questions check` compares on every build.
    """
    return {
        f"{column.removeprefix('_')}__isolated": (
            f"{_MEASURE}\n"
            f"SELECT count(*) AS leaked\n"
            f"FROM {BRIDGE.sql} AS b\n"
            f"WHERE b._event != '{event.name}'\n"
            f"    AND b.{column} IS NOT NULL;\n"
        )
        for event, _, column in uss.measure_columns()
    }


def _first_gap(control: list[tuple[object, ...]], answer: list[tuple[object, ...]]) -> str:
    for index, (left, right) in enumerate(zip(control, answer, strict=False)):
        if left != right:
            return f"row {index}: source {left} vs star {right}"
    return f"lengths differ: {len(control)} vs {len(answer)}"

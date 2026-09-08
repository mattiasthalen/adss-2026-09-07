"""The one entry point. Each subcommand drives exactly one layer; `build` drives them in order.

The layer commands exist separately from `build` because the layers fail differently and are
debugged separately -- and because a reader who wants to know what this system does should be
able to find that out from `--help` rather than from a pipeline definition.

No tool's name appears in a subcommand. `adss das ingest`, never `adss dlt run`: the
blueprint's first promise is that every tool here is replaceable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from adss import __version__
from adss.checks import (
    composed_key_check_names,
    composed_key_checks,
    contracts_of,
    inherited_date_check_names,
    inherited_date_checks,
    measure_check_names,
    measure_checks,
    relationship_check_names,
    relationship_checks,
    run_checks,
)
from adss.contract import read_contract
from adss.das import (
    clock_check_sql,
    current_view_sql,
    key_check_sql,
    lake_dir,
    raw_view_sql,
    staged_view_sql,
)
from adss.destination import shoot
from adss.engine import Engine, is_installed, metadata_schema
from adss.landing import land, observation
from adss.mapping import read_mapping
from adss.model import read_model
from adss.names import Schema
from adss.platform import exclusive, install, reading
from adss.project import Project
from adss.question import read_questions
from adss.source import over_http, record, replay
from adss.sqlformat import formatted
from adss.uss import bridge_sql, calendar_sql, entity_ids, peripheral_sql, read_uss

app = typer.Typer(
    name="adss",
    help="Build and inspect the analytical data storage system.",
    no_args_is_help=True,
    add_completion=False,
)
das = typer.Typer(
    name="das", help="Data according to the system: capture and unpack.", no_args_is_help=True
)
app.add_typer(das)
dab = typer.Typer(
    name="dab",
    help="Data according to the business: integrate and historize.",
    no_args_is_help=True,
)
app.add_typer(dab)


dar = typer.Typer(
    name="dar",
    help="Data according to the requirements: the generated star schema.",
    no_args_is_help=True,
)
app.add_typer(dar)


def _engine(project: Project) -> Engine:
    return Engine(
        binary=project.engine_binary,
        working_directory=project.dab,
        warehouse=project.warehouse,
    )


def _report_version(requested: bool) -> None:
    if requested:
        typer.echo(f"adss {__version__}")
        raise typer.Exit(0)


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            callback=_report_version,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """Build and inspect the analytical data storage system."""


@das.command("record")
def das_record(
    contract: Annotated[
        str | None, typer.Option(help="Contract stem; all of them if omitted.")
    ] = None,
) -> None:
    """Read the live source and keep every response verbatim under das/fixtures.

    The diff this produces is the upstream change, made visible.
    """
    project = Project.discover()
    for path in project.contract_paths():
        if contract and path.stem != contract:
            continue
        declared = read_contract(path)
        directory = project.fixtures / declared.table
        pages_recorded = record(declared.source, over_http, directory)
        typer.echo(f"recorded {pages_recorded} page(s) of {declared.table} into {directory}")


@das.command("ingest")
def das_ingest(
    live: Annotated[bool, typer.Option(help="Read the source instead of the recording.")] = False,
) -> None:
    """Append one load of every contract to the lake."""
    project = Project.discover()
    # Taken once, before anything is fetched. One run of this command is one observation of
    # the source, so every contract it lands carries the same time -- otherwise an as-of join
    # between two entities depends on the order their file names happen to sort in. ADR 0013.
    observed_at = observation()
    typer.echo(f"observing at {observed_at.isoformat()}")
    for path in project.contract_paths():
        declared = read_contract(path)
        fetch = over_http if live else replay(project.fixtures / declared.table)
        loads = land(declared, fetch, project.lake, project.pipelines, observed_at)
        typer.echo(f"landed {declared.table}: {', '.join(loads)}")


@das.command("unpack")
def das_unpack(
    check_only: Annotated[
        bool, typer.Option("--check", help="Fail if the committed checks are not what regenerates.")
    ] = False,
) -> None:
    """Write the views the contracts describe, and the checks that go with them.

    The views embed the lake's absolute path, so they are built rather than committed. The
    checks carry no path, so they are committed -- and `--check` is what stops the committed
    copy becoming a second truth.
    """
    stale = False
    project = Project.discover()
    project.das_sql.mkdir(parents=True, exist_ok=True)
    project.checks_sql.mkdir(parents=True, exist_ok=True)
    # A renamed or removed contract would otherwise leave an orphan check behind, and an
    # orphan check aborts the whole run before any finding is printed.
    written_checks: set[Path] = set()
    for path in project.contract_paths():
        declared = read_contract(path)
        statements = [
            raw_view_sql(declared, lake_dir(project.lake)),
            staged_view_sql(declared),
            current_view_sql(declared),
        ]
        # The views are built rather than committed, so --check has nothing to say about
        # them and should not write them either.
        if not check_only:
            written = project.das_sql / f"{declared.table}.sql"
            written.write_text("\n".join(statements))
            typer.echo(f"wrote {written.relative_to(project.root)}")

        # The checks carry no path, so unlike the views they are committed and linted.
        project.checks_sql.mkdir(parents=True, exist_ok=True)
        for name, sql in (
            (f"{declared.table}__clock", clock_check_sql(declared)),
            (f"{declared.table}__key", key_check_sql(declared)),
        ):
            check = project.checks_sql / f"{name}.sql"
            laid_out = formatted(sql, project.sqlfluff_config)
            written_checks.add(check)
            if check_only:
                if not check.exists() or check.read_text() != laid_out:
                    typer.echo(
                        f"{check.relative_to(project.root)} is not what the contract generates"
                    )
                    stale = True
                continue
            check.write_text(laid_out)
            typer.echo(f"wrote {check.relative_to(project.root)}")

    # Names only: this is a DAS command, and it needs to know which files belong to the
    # other generator, not what they say.
    model = read_model(project.model)
    written_checks |= {
        project.checks_sql / name
        for name in relationship_check_names(model)
        + measure_check_names(read_uss(project.uss, model))
        + inherited_date_check_names(model, read_uss(project.uss, model))
        + composed_key_check_names(
            [read_mapping(path) for path in project.mapping_paths()],
            [read_contract(path) for path in project.contract_paths()],
        )
    }
    for orphan in sorted(project.checks_sql.glob("*.sql")):
        if orphan in written_checks:
            continue
        if check_only:
            typer.echo(f"{orphan.relative_to(project.root)} belongs to nothing declared")
            stale = True
        else:
            orphan.unlink()
            typer.echo(f"removed {orphan.relative_to(project.root)}")

    if stale:
        raise typer.Exit(1)

    if check_only:
        return

    with exclusive(project.warehouse) as connection:
        for schema in (Schema.DAS_RAW, Schema.DAS_STAGED):
            connection.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        for path in project.contract_paths():
            declared = read_contract(path)
            install(connection, (project.das_sql / f"{declared.table}.sql").read_text())
            typer.echo(f"installed {Schema.DAS_STAGED}.{declared.table}")


@dab.command("install")
def dab_install() -> None:
    """Put the modelling framework into the warehouse. Once per warehouse, and idempotent.

    The engine refuses a second install and says to drop its schemas, which is right for a
    person and wrong for a build: a build has to be runnable twice.
    """
    project = Project.discover()
    schema = metadata_schema(project.connections)
    if is_installed(project.warehouse, schema):
        typer.echo(f"the modelling framework is already in {schema}")
        return
    _engine(project).run("install", "--connection", "dev")
    typer.echo("installed the modelling framework")


@dab.command("deploy")
def dab_deploy() -> None:
    """Make the model and its mappings ready to run."""
    project = Project.discover()
    _engine(project).run("deploy")
    typer.echo("deployed the model")


@dab.command("execute")
def dab_execute() -> None:
    """Load the business model from what the system recorded."""
    project = Project.discover()
    _engine(project).run("execute")
    typer.echo("loaded the business model")


def _generate(project: Project) -> dict[str, str]:
    """The whole generated layer, as file name to SQL. Nothing here is hand-written."""
    model = read_model(project.model)
    uss = read_uss(project.uss, model)
    named = entity_ids(model, uss)
    generated = {f"{model.entity(e).object_name}.sql": peripheral_sql(model, e) for e in named}
    generated["_bridge.sql"] = bridge_sql(model, uss)
    generated["_calendar.sql"] = calendar_sql()
    return {name: formatted(sql, project.sqlfluff_config) for name, sql in generated.items()}


def _generated_checks(project: Project) -> dict[str, str]:
    """The checks the model generates, as file name to SQL. The contracts generate the rest."""
    model = read_model(project.model)
    uss = read_uss(project.uss, model)
    mappings = [read_mapping(path) for path in project.mapping_paths()]
    contracts = [read_contract(path) for path in project.contract_paths()]
    written = (
        relationship_checks(model)
        | measure_checks(uss)
        | inherited_date_checks(model, uss)
        | composed_key_checks(mappings, contracts)
    )
    return {f"{name}.sql": formatted(sql, project.sqlfluff_config) for name, sql in written.items()}


@dar.command("generate")
def dar_generate(
    check: Annotated[
        bool, typer.Option(help="Fail if what is committed is not what regenerates.")
    ] = False,
) -> None:
    """Write the star schema's SQL from the model and its declarations."""
    project = Project.discover()
    project.dar_sql.mkdir(parents=True, exist_ok=True)
    project.checks_sql.mkdir(parents=True, exist_ok=True)
    stale = False
    generated_checks = _generated_checks(project)
    everything = {project.dar_sql / n: s for n, s in _generate(project).items()}
    everything |= {project.checks_sql / n: s for n, s in generated_checks.items()}

    # This command is a second writer into checks/, so it sweeps what it no longer generates.
    # Rename a relationship and the check named for the old one is still executed by `adss
    # check` -- and an unrunnable check aborts the whole run before a finding is printed.
    kept = {
        project.checks_sql / f"{table}__{part}.sql"
        for table in contracts_of(project)
        for part in ("clock", "key")
    } | set(everything)
    for orphan in sorted(project.checks_sql.glob("*.sql")):
        if orphan in kept:
            continue
        if check:
            typer.echo(f"{orphan.relative_to(project.root)} belongs to nothing declared")
            stale = True
        else:
            orphan.unlink()
            typer.echo(f"removed {orphan.relative_to(project.root)}")

    for written, sql in everything.items():
        if check:
            current = written.read_text() if written.exists() else ""
            if current != sql:
                typer.echo(f"{written.relative_to(project.root)} is not what the model generates")
                stale = True
            continue
        written.write_text(sql)
        typer.echo(f"wrote {written.relative_to(project.root)}")
    if stale:
        raise typer.Exit(1)


@dar.command("build")
def dar_build() -> None:
    """Run the generated SQL against the warehouse, peripherals first."""
    project = Project.discover()
    generated = _generate(project)
    ordered = [n for n in generated if n not in ("_bridge.sql", "_calendar.sql")]
    ordered += ["_bridge.sql", "_calendar.sql"]
    with exclusive(project.warehouse) as connection:
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {Schema.DAR_USS}")
        for name in ordered:
            # What was generated, not what is on disk. "Nothing here is hand-edited" is then
            # true by construction rather than by a check somebody has to run.
            install(connection, generated[name])
            typer.echo(f"built {name.removesuffix('.sql')}")


@app.command("check")
def check() -> None:
    """Assert what the built warehouse contains. Requires a build."""
    project = Project.discover()
    with reading(project.warehouse) as connection:
        findings = run_checks(project, connection)
    for finding in findings:
        typer.echo(f"{'PASS' if finding.passed else 'FAIL'}  {finding.check}")
        if not finding.passed:
            typer.echo(f"      {finding.detail}")
    if any(not finding.passed for finding in findings):
        raise typer.Exit(1)


@app.command("build")
def build(
    live: Annotated[bool, typer.Option(help="Read the source instead of the recording.")] = False,
) -> None:
    """Build the whole system, in the one direction data flows.

    Each step is a separate command because the layers fail differently and are debugged
    separately. This is them in order, which is the order a reader should meet them in.
    """
    das_ingest(live=live)
    das_unpack(check_only=False)
    dab_install()
    dab_deploy()
    dab_execute()
    dar_generate(check=False)
    dar_build()
    typer.echo("built")


@app.command("shoot")
def shoot_destination() -> None:
    """Photograph the destination, one image per question, beside the question it answers.

    The picture is the record of what was delivered, so it belongs next to what was asked
    rather than in a directory of screenshots nobody browses.
    """
    project = Project.discover()
    for question in read_questions(project.questions):
        image = shoot(
            project.destination,
            project.screenshots,
            project.browser_cache,
            question=question.id,
        )
        beside = question.directory / "answer.png"
        beside.write_bytes(image.read_bytes())
        typer.echo(f"{beside.relative_to(project.root)} ({image.stat().st_size:,} bytes)")

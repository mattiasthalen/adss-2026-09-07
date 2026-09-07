"""The one entry point. Each subcommand drives exactly one layer; `build` drives them in order.

The layer commands exist separately from `build` because the layers fail differently and are
debugged separately -- and because a reader who wants to know what this system does should be
able to find that out from `--help` rather than from a pipeline definition.

No tool's name appears in a subcommand. `adss das ingest`, never `adss dlt run`: the
blueprint's first promise is that every tool here is replaceable.
"""

from __future__ import annotations

from typing import Annotated

import typer

from adss import __version__
from adss.contract import read_contract
from adss.das import current_view_sql, lake_dir, raw_view_sql, staged_view_sql
from adss.engine import Engine
from adss.landing import land
from adss.names import Schema
from adss.platform import exclusive, install
from adss.project import Project
from adss.source import over_http, record, replay

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
    for path in project.contract_paths():
        declared = read_contract(path)
        fetch = over_http if live else replay(project.fixtures / declared.table)
        loads = land(declared, fetch, project.lake, project.pipelines)
        typer.echo(f"landed {declared.table}: {', '.join(loads)}")


@das.command("unpack")
def das_unpack() -> None:
    """Write the views the contracts describe, ready to be installed on the warehouse."""
    project = Project.discover()
    project.das_sql.mkdir(parents=True, exist_ok=True)
    for path in project.contract_paths():
        declared = read_contract(path)
        statements = [
            raw_view_sql(declared, lake_dir(project.lake)),
            staged_view_sql(declared),
            current_view_sql(declared),
        ]
        written = project.das_sql / f"{declared.table}.sql"
        written.write_text("\n".join(statements))
        typer.echo(f"wrote {written.relative_to(project.root)}")

    with exclusive(project.warehouse) as connection:
        for schema in (Schema.DAS_RAW, Schema.DAS_STAGED):
            connection.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        for path in project.contract_paths():
            declared = read_contract(path)
            install(connection, (project.das_sql / f"{declared.table}.sql").read_text())
            typer.echo(f"installed {Schema.DAS_STAGED}.{declared.table}")


@dab.command("install")
def dab_install() -> None:
    """Put the modelling framework into the warehouse. Once per warehouse."""
    project = Project.discover()
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

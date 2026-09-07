"""The one entry point. Each subcommand drives exactly one layer; `build` drives them in order.

The layer commands exist separately from `build` because the layers fail differently and are
debugged separately -- and because a reader who wants to know what this system does should be
able to find that out by reading `--help` rather than a pipeline definition.
"""

from typing import Annotated

import typer

from adss import __version__

app = typer.Typer(
    name="adss",
    help="Build and inspect the analytical data storage system.",
    no_args_is_help=True,
    add_completion=False,
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

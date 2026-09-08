"""The command line is the one entry point: to the layers, to CI, and to a new reader."""

import re

from typer.testing import CliRunner

from adss import __version__
from adss.cli import app

runner = CliRunner()

# click's exit code for "you did not give me a command, here is how to use me".
USAGE_EXIT_CODE = 2

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def plain(styled: str) -> str:
    """The text, without how a terminal was told to dress it.

    Help output is styled per phrase, so on a colour-capable terminal "Usage: " and the
    command name are separately escaped and no literal "Usage: adss" exists to find. A test
    that asserts on the dressing passes locally and fails wherever colour is on.
    """
    return ANSI.sub("", styled)


def test_version_flag_reports_the_package_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in plain(result.stdout)
    assert __version__ != "0.0.0+unknown"


def test_invoking_with_no_arguments_prints_help():
    result = runner.invoke(app, [])
    assert result.exit_code == USAGE_EXIT_CODE
    assert "Usage: adss" in plain(result.stdout)


def test_every_layer_has_a_command_of_its_own():
    """A reader should learn what this system does from --help, not from a pipeline file."""
    listed = plain(runner.invoke(app, ["--help"]).stdout)
    for layer in ("das", "dab", "dar"):
        assert layer in listed

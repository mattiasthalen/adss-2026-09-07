"""The command line is the one entry point: to the layers, to CI, and to a new reader."""

from typer.testing import CliRunner

from adss import __version__
from adss.cli import app

runner = CliRunner()

# click's exit code for "you did not give me a command, here is how to use me".
USAGE_EXIT_CODE = 2


def test_version_flag_reports_the_package_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
    assert __version__ != "0.0.0+unknown"


def test_invoking_with_no_arguments_prints_help():
    result = runner.invoke(app, [])
    assert result.exit_code == USAGE_EXIT_CODE
    assert "Usage: adss" in result.stdout

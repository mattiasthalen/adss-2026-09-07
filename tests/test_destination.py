"""The presentation has to reach whoever accepts the slice."""

from pathlib import Path

import pytest

from adss.destination import WANTED, shim


def test_the_build_the_driver_wants_is_read_off_its_own_complaint():
    complaint = "Looks like Playwright was just installed or updated.\nchromium_headless_shell-1234"
    found = WANTED.search(complaint)
    assert found is not None
    assert found.group(1) == "1234"


def bundled(root: Path) -> Path:
    """A browser installation, laid out the way the image lays one out."""
    for kind in ("chromium", "chromium_headless_shell"):
        binaries = root / f"{kind}-1194" / "chrome-linux"
        binaries.mkdir(parents=True)
        (binaries / "headless_shell").write_text("")
    return root


def test_the_shim_presents_what_is_installed_under_the_name_that_was_asked_for(tmp_path: Path):
    shim(tmp_path / "cache", "9999", bundled(tmp_path / "installed"))
    tmp_path = tmp_path / "cache"
    shell = tmp_path / "chromium_headless_shell-9999" / "chrome-headless-shell-linux64"
    assert (shell / "chrome-headless-shell").is_symlink()
    assert (shell.parent / "INSTALLATION_COMPLETE").exists(), (
        "the driver checks for the marker before it looks for the binary"
    )
    assert (tmp_path / "chromium-9999" / "chrome-linux").is_symlink()


def test_the_shim_is_idempotent(tmp_path: Path):
    installed = bundled(tmp_path / "installed")
    shim(tmp_path / "cache", "9999", installed)
    shim(tmp_path / "cache", "9999", installed)


BROKEN = """import marimo

__generated_with = "0.24.0"
app = marimo.App()


@app.cell
def _():
    raise RuntimeError("this cell does not work")
    return


if __name__ == "__main__":
    app.run()
"""

WORKING = """import marimo

__generated_with = "0.24.0"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    mo.md("# it works")
    return (mo,)


if __name__ == "__main__":
    app.run()
"""


def test_a_page_whose_cells_failed_is_refused(tmp_path: Path):
    """The guard this replaces could not fire. It read the thumbnail exporter's output for
    "some cells failed", and that exporter says nothing at all about a cell that raised -- it
    exits zero and photographs the wreckage. Three broken pictures went through it, one of
    them a slice's already-accepted answer, changed with no change to its number.

    Run against the exporter that does report it, on a notebook built to fail.
    """
    from adss.destination import DestinationError, _refuse_a_page_whose_cells_failed

    notebook = tmp_path / "broken.py"
    notebook.write_text(BROKEN)
    with pytest.raises(DestinationError, match="cells failed"):
        _refuse_a_page_whose_cells_failed(notebook, "")


def test_a_page_that_works_is_not_refused(tmp_path: Path):
    """The other half. A guard that refuses everything is as useless as one that refuses
    nothing, and it would be caught a good deal sooner."""
    from adss.destination import _refuse_a_page_whose_cells_failed

    notebook = tmp_path / "working.py"
    notebook.write_text(WORKING)
    _refuse_a_page_whose_cells_failed(notebook, "")

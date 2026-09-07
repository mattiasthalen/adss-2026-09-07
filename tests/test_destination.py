"""The presentation has to reach whoever accepts the slice."""

from pathlib import Path

from adss.destination import WANTED, shim


def test_the_build_the_driver_wants_is_read_off_its_own_complaint():
    complaint = "Looks like Playwright was just installed or updated.\nchromium_headless_shell-1234"
    found = WANTED.search(complaint)
    assert found is not None
    assert found.group(1) == "1234"


def test_the_shim_presents_what_is_installed_under_the_name_that_was_asked_for(tmp_path: Path):
    shim(tmp_path, "9999")
    shell = tmp_path / "chromium_headless_shell-9999" / "chrome-headless-shell-linux64"
    assert (shell / "chrome-headless-shell").is_symlink()
    assert (shell.parent / "INSTALLATION_COMPLETE").exists(), (
        "the driver checks for the marker before it looks for the binary"
    )
    assert (tmp_path / "chromium-9999" / "chrome-linux").is_symlink()


def test_the_shim_is_idempotent(tmp_path: Path):
    shim(tmp_path, "9999")
    shim(tmp_path, "9999")

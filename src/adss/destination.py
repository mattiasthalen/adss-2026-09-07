"""Turning the page into something that can be attached to a pull request.

A slice is accepted on its presentation, so the presentation has to reach whoever accepts
it. The exported HTML will not do: it loads its assets from a content network and renders
blank without one, so the screenshot is taken of the notebook itself, executed.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

# The browser that is installed here, and the name the driver looks for. They differ, and
# the difference moves whenever the driver is upgraded -- so it is read off the failure
# rather than guessed, and nothing is downloaded.
BUNDLED = Path("/opt/pw-browsers")
WANTED = re.compile(r"chromium(?:_headless_shell)?-(\d+)")


class DestinationError(Exception):
    """The page did not render."""


def _installed(kind: str, bundled: Path) -> Path | None:
    found = sorted(bundled.glob(f"{kind}-*"), key=lambda path: int(path.name.rsplit("-", 1)[-1]))
    return found[-1] if found else None


def _point(link: Path, target: Path) -> None:
    """Repoint a link, including one whose target has gone.

    A dangling symlink answers False to exists() and still raises on symlink_to, and this
    cache outlives the image it points into.
    """
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(target)


def shim(cache: Path, build: str, bundled: Path = BUNDLED) -> None:
    """Present the installed browser under the build number the driver asked for."""
    shell = _installed("chromium_headless_shell", bundled)
    if shell is not None:
        target = cache / f"chromium_headless_shell-{build}" / "chrome-headless-shell-linux64"
        target.mkdir(parents=True, exist_ok=True)
        _point(target / "chrome-headless-shell", shell / "chrome-linux" / "headless_shell")
        (target.parent / "INSTALLATION_COMPLETE").touch()

    full = _installed("chromium", bundled)
    if full is not None:
        target = cache / f"chromium-{build}"
        target.mkdir(parents=True, exist_ok=True)
        _point(target / "chrome-linux", full / "chrome-linux")
        (target / "INSTALLATION_COMPLETE").touch()


def _capture(
    notebook: Path, shot: Path, cache: Path, height: int
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "marimo",
            "export",
            "thumbnail",
            str(notebook),
            "--output",
            str(shot),
            # Not the default. Without it the thumbnail is the page's structure with none of
            # its outputs, which looks like a screenshot and answers nothing.
            "--execute",
            "--overwrite",
            "--width",
            "1400",
            "--height",
            str(height),
            "--scale",
            "1",
            # Outputs stream in after load and the marks paint after that.
            "--timeout-ms",
            "8000",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(cache)),
    )


def shoot(notebook: Path, into: Path, cache: Path, height: int = 1800) -> Path:
    """Execute the page and photograph it. Fails if it did not actually render."""
    into.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    shot = into / f"{notebook.stem}.png"

    completed = _capture(notebook, shot, cache, height)
    output = completed.stdout + completed.stderr
    asked_for = WANTED.search(output)
    if asked_for and not shot.exists():
        shim(cache, asked_for.group(1))
        completed = _capture(notebook, shot, cache, height)
        output = completed.stdout + completed.stderr

    if "some cells failed" in output:
        raise DestinationError(f"the page ran but cells failed, so it is not the answer:\n{output}")
    if completed.returncode != 0 or not shot.exists():
        raise DestinationError(f"no screenshot was produced:\n{output}")
    if shot.stat().st_size < 20_000:
        raise DestinationError(
            f"{shot} is {shot.stat().st_size} bytes, which is a blank page rather than a "
            f"rendered one. A thumbnail taken without executing looks exactly like this."
        )
    return shot

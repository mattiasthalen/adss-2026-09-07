"""Turning the page into something that can be attached to a pull request.

A slice is accepted on its presentation, so the presentation has to reach whoever accepts
it. The exported HTML will not do: it loads its assets from a content network and renders
blank without one, so the screenshot is taken of the notebook itself, executed.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
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
    notebook: Path, shot: Path, cache: Path, height: int, question: str = ""
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
        env=dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(cache), ADSS_QUESTION=question),
    )


def rendered(notebook: Path, question: str = "", into: Path | None = None) -> str:
    """Execute the page as HTML and hand back what the exporter said. Named so a test can reach it.

    The HTML exporter is here for one reason: it is the only one that reports a cell that raised.
    """
    with tempfile.TemporaryDirectory() as scratch:
        page = Path(into or scratch) / "page.html"
        completed = subprocess.run(
            [
                "marimo",
                "export",
                "html",
                str(notebook),
                "--no-include-code",
                "-o",
                str(page),
            ],
            capture_output=True,
            text=True,
            env=dict(os.environ, ADSS_QUESTION=question),
        )
    return completed.stdout + completed.stderr


def _refuse_a_page_whose_cells_failed(notebook: Path, question: str) -> None:
    """The page is executed twice, and the first time is only to find out whether it worked.

    `marimo export thumbnail --execute` says nothing at all about a cell that raised: it exits
    zero and photographs the wreckage. So the guard that read its output for "some cells failed"
    could never fire -- that sentence belongs to the HTML exporter -- and it let three broken
    pictures through, one of them a slice's already-accepted answer, changed with no change to
    its number.

    A blank page is not a small file either. The one that got past this was 28 kB: a title, two
    paragraphs, and nothing else. Size cannot tell a rendered page from a ruined one; only the
    exporter that reports the failure can.

    The cost is a second execution of the notebook per question. That is seconds, against a
    picture that is the whole of what a slice is accepted on.
    """
    output = rendered(notebook, question)
    if "some cells failed" in output or "MarimoExceptionRaised" in output:
        raise DestinationError(
            f"the page ran but cells failed, so the picture is not the answer:\n{output}"
        )


def shoot(notebook: Path, into: Path, cache: Path, height: int = 1800, question: str = "") -> Path:
    """Execute the page and photograph it. Fails if it did not actually render.

    One question at a time. The page is one document and the shot has a fixed height, so a
    single picture of everything stops being either readable or attachable at the second
    question -- and it is one question a slice is accepted on.
    """
    into.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    shot = into / f"{question or notebook.stem}.png"

    _refuse_a_page_whose_cells_failed(notebook, question)
    completed = _capture(notebook, shot, cache, height, question)
    output = completed.stdout + completed.stderr
    asked_for = WANTED.search(output)
    if asked_for and not shot.exists():
        shim(cache, asked_for.group(1))
        completed = _capture(notebook, shot, cache, height, question)
        output = completed.stdout + completed.stderr

    if completed.returncode != 0 or not shot.exists():
        raise DestinationError(f"no screenshot was produced:\n{output}")
    if shot.stat().st_size < 20_000:
        raise DestinationError(
            f"{shot} is {shot.stat().st_size} bytes, which is a blank page rather than a "
            f"rendered one. A thumbnail taken without executing looks exactly like this."
        )
    return shot

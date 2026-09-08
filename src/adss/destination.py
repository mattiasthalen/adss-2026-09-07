"""Turning the page into something that can be attached to a pull request.

A slice is accepted on its presentation, so the presentation has to reach whoever accepts
it. The exported HTML will not do: it loads its assets from a content network and renders
blank without one, so the screenshot is taken of the notebook itself, executed.
"""

from __future__ import annotations

import html
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

# A page that hangs would otherwise hang the build with nothing to read. The whole warehouse
# renders in seconds; this is the bound on a cell that never returns.
RENDER_SECONDS = 300


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


def as_text(value: object) -> str:
    """A value out of the warehouse, as text rather than as markup.

    The page interpolates answers into markdown, and markdown is HTML. A category name carrying
    a positioned `<div>` puts a different number on the picture the slice is accepted on -- and
    nothing catches it: no cell raised, the file is a normal size, and both of the question's
    queries still agree, because the same poisoned string is on both sides of the comparison.
    It is not script execution, which the frontend's sanitiser does stop. It does not need to be.

    Every value this system reads from the warehouse goes through here before it reaches a page.
    Today the source is a committed fixture and the eight names are ordinary words; slice 6 is a
    file drop, which is the first source where somebody outside chooses the string.

    Markdown's own syntax in a value still renders -- a link or an image written in brackets.
    That is smaller, it cannot position anything, and escaping it would mean escaping the page's
    own formatting too.
    """
    return html.escape(str(value))


def rendered(notebook: Path, question: str = "") -> tuple[int, str]:
    """Execute the page as HTML and hand back what happened. Named so a test can reach it.

    The HTML exporter is here for one reason: it is the only one that reports a cell that raised.
    """
    with tempfile.TemporaryDirectory() as scratch:
        page = Path(scratch) / "page.html"
        try:
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
                timeout=RENDER_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return 1, f"the page did not finish inside {RENDER_SECONDS}s"
        except FileNotFoundError:
            return 1, "marimo is not installed, so the page cannot be executed"
    return completed.returncode, completed.stdout + completed.stderr


def unrendered(returncode: int, output: str) -> str | None:
    """Why this page is not the answer, or None if it is. Pure, so a test reaches every branch.

    The exit code as well as the words. The guard this replaces read only the words, and was
    decorative for four slices because the tool it read never said them; reading only the words
    again -- from a different tool this time -- would be the same mistake with the same shape.
    A page that was killed, ran out of memory, or met a marimo that rewords its message prints
    nothing recognisable and exits non-zero.
    """
    if returncode != 0:
        return f"the exporter exited {returncode}"
    if "some cells failed" in output or "MarimoExceptionRaised" in output:
        return "cells failed to execute"
    return None


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
    returncode, output = rendered(notebook, question)
    why = unrendered(returncode, output)
    if why is not None:
        raise DestinationError(f"{why}, so the picture is not the answer:\n{output}")


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

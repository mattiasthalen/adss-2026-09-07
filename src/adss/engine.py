"""The modelling engine: found by checksum, invoked detached, and its errors translated.

The engine is vendored rather than fetched so a clone of this repository can build it with
no secret. It self-reports as `nightly` with a commit hash, so there is no version to depend
on and the checksum beside it is the pin. ADR 0004.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from adss.platform import require_detached

TOOL = "daana-cli"

# What the engine says when it cannot take the warehouse lock. It is not what went wrong.
MISLEADING = "framework is not installed"


class EnginePinError(Exception):
    """The vendored binary is not the one this repository recorded."""


class EngineError(Exception):
    """The engine refused. The message says what actually happened where we can tell."""


@dataclass(frozen=True, slots=True)
class Engine:
    """A pinned engine binary and the project directory it is invoked from."""

    binary: Path
    working_directory: Path
    warehouse: Path

    def verify(self) -> str:
        """Refuse to run a binary that is not the one recorded beside it."""
        recorded = (self.binary.parent / f"{self.binary.name}.sha256").read_text().split()[0]
        digest = hashlib.sha256(self.binary.read_bytes()).hexdigest()
        if digest != recorded:
            raise EnginePinError(
                f"{self.binary} hashes to {digest}, but {self.binary.name}.sha256 records "
                f"{recorded}. The engine is pinned by content because it has no version."
            )
        return digest

    def run(self, *arguments: str) -> str:
        """Invoke the engine, refusing while this process holds the warehouse."""
        require_detached(self.warehouse, TOOL)
        self.verify()
        completed = subprocess.run(
            [str(self.binary), *arguments, "--no-tui"],
            cwd=self.working_directory,
            capture_output=True,
            text=True,
            check=False,
        )
        output = completed.stdout + completed.stderr
        if completed.returncode != 0:
            raise EngineError(_explain(arguments, output, self.warehouse))
        return output


def _explain(arguments: tuple[str, ...], output: str, warehouse: Path) -> str:
    if MISLEADING in output:
        return (
            f"{TOOL} {' '.join(arguments)} failed saying the framework is not installed. It "
            f"usually is: this is what the engine reports when it cannot take the lock on "
            f"{warehouse}. Close anything holding the file and try again.\n\n{output}"
        )
    return f"{TOOL} {' '.join(arguments)} failed:\n\n{output}"

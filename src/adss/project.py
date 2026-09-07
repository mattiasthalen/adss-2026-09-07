"""Where things are. One place, so no path is spelled twice.

Every path is absolute and anchored on the repository root rather than the working
directory: a relative path inside a persisted view resolves at query time, so a view created
from here would break the moment a page opened the same warehouse from elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Project:
    """The repository, as the layers see it."""

    root: Path

    @classmethod
    def discover(cls, start: Path | None = None) -> Project:
        here = (start or Path.cwd()).absolute()
        for candidate in (here, *here.parents):
            if (candidate / "pyproject.toml").is_file():
                return cls(root=candidate)
        raise FileNotFoundError(f"no project root above {here}")

    @property
    def contracts(self) -> Path:
        return self.root / "das" / "contracts"

    @property
    def fixtures(self) -> Path:
        return self.root / "das" / "fixtures"

    @property
    def lake(self) -> Path:
        return self.root / "das" / "lake"

    @property
    def das_sql(self) -> Path:
        return self.root / "das" / "sql"

    @property
    def pipelines(self) -> Path:
        return self.root / ".dlt"

    @property
    def warehouse(self) -> Path:
        return self.root / "warehouse.duckdb"

    @property
    def dab(self) -> Path:
        return self.root / "dab"

    @property
    def mappings(self) -> Path:
        return self.dab / "mappings"

    @property
    def engine_binary(self) -> Path:
        return self.root / "bin" / "linux-amd64" / "daana-cli"

    def contract_paths(self) -> tuple[Path, ...]:
        return tuple(sorted(self.contracts.glob("*.yaml")))

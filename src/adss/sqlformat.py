"""Generated SQL is laid out by the same formatter that lints it.

The conventions say a tool's configuration is the rule wherever a tool can check one. This
extends that: the linter's own formatter decides layout, so the generator cannot drift from
it, and a rule change is picked up by regenerating rather than by hand-editing an emitter.

It runs inside the generator rather than after it, so the committed file is already the
formatted one and a regeneration produces no spurious diff.
"""

from __future__ import annotations

from pathlib import Path

import sqlfluff


class SqlFormatError(Exception):
    """The generator emitted SQL the linter could not parse."""


def formatted(sql: str, config: Path) -> str:
    """Lay out generated SQL, refusing to write anything the linter cannot parse."""
    try:
        fixed = sqlfluff.fix(sql, config_path=str(config))
    except Exception as broken:  # sqlfluff raises several unrelated types
        raise SqlFormatError(f"the generator emitted SQL the linter rejected: {broken}") from broken
    if not fixed.strip():
        raise SqlFormatError("the formatter returned nothing, which means it failed to parse")
    return fixed if fixed.endswith("\n") else fixed + "\n"

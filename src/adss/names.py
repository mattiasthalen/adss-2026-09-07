"""The names this system owns. One place, so a flow check has something closed to check against."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_RESERVED = frozenset({"order", "group", "select", "from", "where", "table", "index", "all"})

# What an id this system will spell into SQL and into a file name may look like. A letter,
# then letters, digits and underscores. Nothing else: an id becomes a quoted identifier, a
# string literal inside a generated check, and the stem of a file under checks/ -- so a
# quote makes a check pass silently for ever, and a slash writes the file somewhere else.
IDENTIFIER = re.compile(r"\A[A-Za-z][A-Za-z0-9_]*\Z")


def unsafe(value: str) -> bool:
    """Whether spelling this id into SQL or a path would change what it means."""
    return IDENTIFIER.match(value) is None


def refuse_unsafe(kind: str, value: str) -> str:
    """The sentence every reader raises with, so one rule is stated once."""
    return (
        f"{kind} {value!r} is not a name this system can spell. An id becomes a quoted "
        f"identifier, a literal inside a generated check and the stem of a file under "
        f"checks/ -- so a quote makes a check pass for ever and a slash writes the file "
        f"outside the directory. A letter, then letters, digits and underscores."
    )


class Layer(StrEnum):
    """What a schema is for. The names carry the principles; see docs/blueprint.md."""

    DAS = "das"
    DAB = "dab"
    DAR = "dar"


class Schema(StrEnum):
    """Every schema this system creates, and nothing else."""

    DAS_RAW = "das__raw"
    DAS_STAGED = "das__staged"
    DAB = "dab"
    DAB_STAGE = "dab__stage"
    DAB_META = "dab__meta"
    DAR_USS = "dar__uss"

    @property
    def layer(self) -> Layer:
        return Layer(str(self).split("__", 1)[0])


def quoted(identifier: str) -> str:
    """Bare unless it is a reserved word, in which case quoted rather than abbreviated around.

    Renaming to dodge a keyword would break the mechanical link back to the concept the name
    came from, which is the one thing the name is for. Conventions 1.3.
    """
    return f'"{identifier}"' if identifier.lower() in _RESERVED else identifier


def crossing(identifier: str) -> str:
    """An identifier crossing over from DAB, where mixed case is deliberate.

    Always quoted, never conditionally: an identifier that loses its quotes fails only at
    run time, and the two conventions must be visually distinct. Conventions section 3.
    """
    return f'"{identifier}"'


@dataclass(frozen=True, slots=True)
class Relation:
    """A schema-qualified object this system creates."""

    schema: Schema
    name: str

    @property
    def sql(self) -> str:
        return f"{self.schema}.{quoted(self.name)}"

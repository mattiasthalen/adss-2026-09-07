"""A business question: the specification, the acceptance test and what a page renders.

It is a data file rather than code, which is what keeps the vocabulary of one business out
of the machinery that runs it. The runner discovers questions and asserts over them; it
names nothing. ADR 0005.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
TOKEN = re.compile(r"\{\{([^}]+)\}\}")

STAGED = "staged.sql"
USS = "uss.sql"


class QuestionError(Exception):
    """A question that cannot be answered as written."""


class Status(StrEnum):
    DRAFT = "draft"
    RED = "red"
    GREEN = "green"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class Question:
    directory: Path
    id: str
    status: Status
    persona: str
    question: str
    dimensions: tuple[str, ...]
    defines: tuple[str, ...]
    staged_sql: str
    uss_sql: str
    body: str

    @property
    def tokens(self) -> tuple[str, ...]:
        return tuple(str(match).strip() for match in TOKEN.findall(self.body))


def without_comments(sql: str) -> str:
    """The SQL, without its commentary. A comment explaining a rule does not break it."""
    return "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))


def read_question(directory: Path) -> Question:
    text = (directory / "question.md").read_text()
    parsed = FRONT_MATTER.match(text)
    if parsed is None:
        raise QuestionError(f"{directory}: question.md has no front matter")
    front = yaml.safe_load(parsed.group(1))
    return Question(
        directory=directory,
        id=str(front["id"]),
        status=Status(str(front["status"])),
        persona=str(front["persona"]),
        question=str(front["question"]),
        dimensions=tuple(str(d) for d in front["dimensions"]),
        defines=tuple(str(d) for d in front["defines"]),
        staged_sql=(directory / STAGED).read_text(),
        uss_sql=(directory / USS).read_text(),
        body=parsed.group(2),
    )


def read_questions(root: Path) -> tuple[Question, ...]:
    return tuple(
        read_question(directory)
        for directory in sorted(root.iterdir())
        if (directory / "question.md").is_file()
    )


def check_question(question: Question, defined: dict[str, str]) -> None:
    """Refuse a question that cannot be answered, or answered honestly."""
    for token in question.tokens:
        if token not in defined:
            raise QuestionError(
                f"{question.id}: {{{{{token}}}}} resolves to nothing. A question references "
                f"definitions and never restates one, so a token with no definition behind "
                f"it is a gap in the model -- fill it there first."
            )
    missing = [name for name in question.defines if name not in defined]
    if missing:
        raise QuestionError(f"{question.id}: declares {missing}, which nothing defines")

    control = without_comments(question.staged_sql).lower()
    for forbidden in ("dab.", "dab__", "dar__uss"):
        if forbidden in control:
            raise QuestionError(
                f"{question.id}: the control query mentions {forbidden!r}. It must compute "
                f"the answer independently, or agreement between the two proves nothing."
            )
    if "das__staged." not in control or "__current" not in control:
        raise QuestionError(
            f"{question.id}: the control query must read a das__staged __current view. "
            f"Reading the raw layer or the lake skips the contract's casts, which is what "
            f"makes agreement mean anything."
        )

    answer = without_comments(question.uss_sql).lower()
    if "dar__uss" not in answer:
        raise QuestionError(f"{question.id}: the answer query does not read the star schema")
    for forbidden in ("das__", "dab.", "dab__", "read_parquet"):
        if forbidden in answer:
            raise QuestionError(
                f"{question.id}: the answer query mentions {forbidden!r}. A destination reads "
                f"the star schema and nothing else -- the page runs this query verbatim, so a "
                f"reach past it would render, pass, and be exactly the invisible dependency "
                f"the flow rules exist to prevent."
            )

    for body, side in ((control, "control"), (answer, "answer")):
        if "order by" not in body:
            raise QuestionError(
                f"{question.id}: the {side} query has no ORDER BY. The two answers are "
                f"compared row by row, so without one an identical pair can differ by the "
                f"order the engine happened to return, and someone goes looking for a data "
                f"bug that is not there."
            )

    # Only the answer query. The control expresses the same dimension in the source's own
    # words -- that difference is what makes it independent rather than a transcription.
    for dimension in question.dimensions:
        if dimension.rsplit(".", 1)[-1].lower() not in answer:
            raise QuestionError(
                f"{question.id}: declares the dimension {dimension!r}, which the answer query "
                f"does not mention. The front matter is what a reader trusts."
            )

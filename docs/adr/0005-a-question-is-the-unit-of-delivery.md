---
status: accepted
date: 2026-09-07
decision-makers: [adss maintainers]
slice: 1
---

# A business question is the unit of delivery, carried as a data file with the two queries that must agree on its answer

## Context and Problem Statement

At the coffee machine, "how were sales last quarter?" works, because both people share years of
context. A dashboard has none of it. The gap between that question and one a data system can
answer is the actual work: an answerable question names its aggregation, its measure, its
dimensions and its time grain, and defines every term that two people might read differently.

This system delivers in slices, and a slice is accepted on a presentation of one question's
answer. So the question is not documentation *about* the work — it is the specification, the
acceptance test, and the thing the page renders. That makes its format load-bearing in three
directions at once, and it has to satisfy constraints that pull against each other.

`dab/model.yaml` is the only place the data is explained (B8), so a question may not restate a
definition — but it must carry enough that a reader can answer it without a conversation. The
acceptance test compares two business queries, but no test may contain business vocabulary
(conventions §6). And the check that gives the slice its confidence — computing the answer twice
and requiring agreement — is only worth anything if the two computations are genuinely
independent, which is a property nobody can enforce mechanically.

## Decision Drivers

* a question is answerable from the file alone, with no conversation
* definitions are referenced, never restated, and every reference is proved to resolve
* the acceptance test names nothing from the business
* the two queries are independent enough that agreement means something
* the question survives being reprioritised, refined or pivoted, which the methodology expects

## Considered Options

* A question directory holding `question.md` plus the two queries as `.sql` files
* A single markdown file with the SQL in fenced blocks
* Questions as test functions in `tests/`
* A recorded expected result committed alongside, with no second query

## Decision Outcome

Chosen option: **a directory per question under `docs/questions/NN-<slug>/`, holding
`question.md` and the two queries as `staged.sql` and `uss.sql`.**

Separate `.sql` files rather than fenced blocks, for a reason that is not aesthetic: `.sql` files
are linted by the same sqlfluff hook as every other statement in the repository, and
[conventions §3](../conventions.md) already refuses to let SQL hide inside a string. A fenced
block is a string. The moment the acceptance queries are exempt from the SQL rules, they become
the least-reviewed SQL in a repository whose whole claim rests on them.

*The file is a data file, and that is what keeps the test clean.* The runner discovers question
directories, reads the front matter, runs both queries and asserts agreement — naming nothing. A
per-question test *function* would smuggle the vocabulary back in through its own name, so the
runner is parameterised over what it finds.

*Definitions are referenced by identifier.* The front matter lists the model identifiers the
question depends on, and the prose cites them by token rather than by paraphrase. A machinery test
asserts every token resolves to something `dab/model.yaml` or `dab/uss.yaml` defines. When a
question needs a term the model does not define, the question is **blocked** and the model change
comes first — which is not an obstacle but the methodology working: a question the model cannot
answer has found a gap in the model, and finding it is what asking was for.

### What the two queries actually prove, and what they do not

This deserves to be stated honestly, because it is easy to oversell.

The control query computes the answer from `das__staged.<table>__current`, bypassing DAB and DAR
entirely. The other computes it from `dar__uss`. CI asserts they agree row for row.

What it catches is the failure this architecture is most exposed to and least able to see: that
routing a number through integration and generation *changed it*. Dropped rows from a join, a
multiplied measure, a mis-inherited key, a version collapse that kept the wrong row, an event
filter that excluded more than it meant to — all of these show up as a number that no longer
matches the source.

What it does not catch is a wrong definition. If the model says an order is placed on its shipped
date, both queries can be written to that and both will be wrong together. Nor does it catch a
failure the staged layer shares — and there is one specific case worth naming: the engine's
duplicate-row defect is invisible in every presentation view, so both queries would agree while
the history quietly corrupted. That is why a separate data check counts the base table directly.

The risk that the two are written to agree rather than to be right is real and cannot be designed
away. Three things reduce it. The queries read different schemas in different vocabularies, so a
transcription is visible as one. The control query is forbidden from mentioning `dab` or
`dar__uss`, so it cannot consult the answer it is checking. And when they disagree,
`dab/model.yaml` is the named arbiter: the query that departs from the definition is the one that
changes, never both until they match. Without that last rule the cheapest repair is to make the
check agree with itself, which deletes the only thing it was measuring.

A recorded expected result was the alternative. It is simpler and it catches every regression
exactly — but its first recording is only as right as the query that produced it, and after that
it can only confirm the system still agrees with its own past. It is a regression test, not a
reconciliation, and this layer needs the second.

### Lifecycle

`status` is one of `draft`, `red`, `green`, `superseded`. The methodology expects a question to be
validated, refined or pivoted once the business sees real data, and all three are wins — so a
refinement edits the question in place and a pivot supersedes it with a new one, keeping the
original with its status set. What the business asked for before it saw the answer is part of the
record of why the model looks the way it does.

One question, one slice, one branch, one page. The page reads the question's own `uss.sql`, so the
presentation and the test cannot disagree about what was asked.

### Consequences

* Good, because the specification, the acceptance test and the rendered page are one artefact,
  which is what makes the prototype the deliverable rather than a report about it
* Good, because the acceptance queries are linted like all other SQL
* Good, because a question that outruns the model is blocked visibly rather than answered
  approximately
* Bad, because every answer is written twice, which is duplicated effort and a second thing to
  maintain when a definition changes
* Bad, because the control query has a shelf life. It stays writable only while a question needs
  no integration; from the first question spanning two sources, writing it against the staged
  layer means reimplementing DAB inside the check. Slice 6 is where that bill arrives, and this
  record does not pay it
* Bad, because "independent" is a property of how the queries were written and nothing enforces
  it. The arbiter rule limits the damage; it does not prevent the sin

### Confirmation

`tests/test_questions.py` asserts every question file parses and every definition token resolves
to the model. `check_question` enforces both halves of the boundary rule — the control query
mentions neither `dab` nor `dar__uss` and *does* read a `__current` view, and the answer query
reads `dar__uss` and reaches past it for nothing — because the page runs the answer query verbatim
and a reach past DAR would render, pass, and be exactly the dependency the flow rules exist to
prevent.

The declared dimensions are asserted against the **answer** query only. An earlier draft of this
record claimed both; that was wrong, and the check caught it on its first run. The control query
says the same thing in the source's own words, and requiring the same spelling in both would force
one to be written from the other — which is precisely the independence this whole arrangement is
for.

`adss check` runs both queries against the built warehouse and asserts row-for-row equality. Both
suites name nothing from the business.

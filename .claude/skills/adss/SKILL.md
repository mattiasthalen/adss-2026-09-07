---
name: adss
description: The whole system — how the three layers fit, how a slice is built and accepted, and what to read before changing anything. Use when starting work on this repository, adding a slice or a business question, deciding which layer a change belongs in, or when a change seems to need two layers at once.
---

# ADSS

An analytical data storage system built as blog.daana.dev describes one. Three layers, one
direction of flow, and no shortcuts between them.

| Layer | Schemas | What it does |
|---|---|---|
| **DAS** | `das__raw`, `das__staged` | says what the source said, and keeps every load |
| **DAB** | `dab`, `dab__stage`, `dab__meta` | says what the business means, historized |
| **DAR** | `dar__uss` | says what one reader needs, generated |

Destinations read `dar__uss` and nothing else.

## Read first, in this order

1. `docs/blueprint.md` — the principles. They are absolutes and they bind every change.
2. `docs/conventions.md` — the one convention document. Where a tool can check a rule, the
   tool's config **is** the rule.
3. `docs/adr/` — why each thing is the way it is. An ADR lands **before** the code it decides.
4. `docs/deviations.md` — the knowing departures, with their costs and exit conditions. Read
   it at the start of every slice and check each open entry against its condition.

Then the layer skill: `das`, `dab`, `dar`, `destination`.

## The three flow rules

They are absolutes, and most bad changes are one of them:

- **F1** — analytical usage reads only DAR.
- **F2** — DAR reads only DAB.
- **F3** — DAB reads only DAS.

Each movement does exactly one job: ingest, integrate, specialise. Code that ingests *and*
integrates has collapsed two layers and is not permitted however convenient it is.

## Which layer does a change belong in?

- Source sent a new field, or renamed one → **DAS**, a contract edit. Nothing else moves.
- The business means something new, or means it differently → **DAB**. Definitions live here
  and only here.
- A reader needs a different shape of what the business already means → **DAR**, by
  declaration and regeneration. Never by hand.
- A change seems to need two layers at once → it is probably one change in the wrong layer.
  Say which principle would bend, and write it down before bending it.

## A slice

One business question, end to end, widening the system by one thing.

```bash
uv run adss build      # ingest, unpack, deploy, execute, generate, build -- offline
uv run adss check      # what the built warehouse must contain
uv run adss shoot      # the screenshot the slice is accepted on
uv run pre-commit run --all-files
```

1. **Frame** — read the deviations register and the conventions. Name the one decision this
   slice forces.
2. **Decide** — write the ADR. Before the code, always: writing the alternatives out while
   they are still live regularly changes the answer, which is the whole return.
3. **Build** — machinery is test-first, the failing test and the code in one commit. Data
   checks land in the commit that makes them true; TDD is for functions, not for a `SELECT`.
   **Run the mutation before the ADR's Confirmation section claims one.** A confirmation that
   names a test which could not fail for the reason given is worse than none, because it stops
   anybody looking again — and it has happened here more than once. Break the thing on purpose,
   watch the suite go red, and write down what it said.
4. **Verify** — layering, conventions, an independent recomputation, test quality, and a code
   review of the diff.
5. **Present** — the page, the screenshot, the pull request.

## The two suites

`tests/` is machinery: pure functions over data files, no warehouse, no network, no binary.
Runs on every commit. **No business word appears in it** — fixtures are neutral models held as
data files, so a test proves the machinery is generic rather than asserting it.

`checks/` is about the built warehouse. Runs after `adss build`. Never against a stub: a check
that passes against a fabricated warehouse tells you nothing about the one that was built.

## The acceptance check

Every question is computed twice — from `das__staged`, bypassing the layers, and from
`dar__uss` — and the two must agree row for row.

That catches the failure this architecture is most exposed to and least able to see: that
routing a number through integration and generation changed it. It does **not** catch a wrong
definition; both queries would be written to it and both would be wrong together. When they
disagree, `dab/model.yaml` is the arbiter — the query that departs from the definition is the
one that changes, never both until they match.

An answer query may aggregate `_measure__` columns and nothing else, and it is refused if it
does otherwise. The bridge protects a measure with a typed null on every branch that does not
own it; it protects nothing on a peripheral, and a numeric attribute that is also a measure's
source is published in both places. ADR 0012.

---
status: accepted
date: 2026-09-07
decision-makers: [adss maintainers]
slice: 0
---

# Decisions are recorded as MADR files, written before the code they decide

## Context and Problem Statement

This system is built for a life cycle measured in decades, and almost every difficult thing about
it is a choice that had alternatives. Six months from now the question will not be "what does this
code do" — that is readable — but "what else was considered, and what did we know at the time".

Without a record, the answer is reconstructed from the code, which can only ever show the option
that won. The alternatives, the constraint that ruled them out, and the cost that was knowingly
accepted are all invisible, so the next person either re-litigates a settled question or, worse,
quietly reverses it without knowing there was a decision there at all.

## Decision Drivers

* the reasoning has to outlive the person who did it
* a reader must be able to tell a considered trade-off from an accident
* a record must be cheap enough to write that it actually gets written
* the record must be readable by an agent with no conversation history

## Considered Options

* MADR files in the repository, one per decision, written before the code
* MADR files written after the implementation, describing what was built
* Decisions recorded in pull request descriptions
* Decisions recorded in an external wiki
* No formal record; rely on commit messages

## Decision Outcome

Chosen option: **MADR files under `docs/adr/`, numbered, written before the code they decide.**

Three properties make it the right one.

*In the repository.* The decision travels with the code it governs, is reviewed in the same pull
request, and is available to anyone — or anything — reading the repository with no other access.
An external wiki is a second surface that drifts from the code, and a pull request description is
unfindable six months later without knowing which pull request to open.

*Before the code.* This is the part that does real work. Writing the options out before building
forces the alternatives to be stated while they are still live, and it regularly changes the
answer — which is the whole return on the exercise. A record written afterwards can only describe
what was built, and its "considered options" section is reconstruction.

*Superseded, never edited.* Editing a record to match current reality destroys the thing that
made it worth keeping. A decision that has changed gets a new file that supersedes the old one, so
both the old reasoning and the reason it stopped holding survive.

The format is MADR because it names the parts that matter — context, drivers, options, outcome,
consequences — and because "Consequences" is where the honest cost goes. A record with only good
consequences has not been thought about.

### Consequences

* Good, because the reasoning behind every non-obvious choice is recoverable by anyone reading
  the repository, with no conversation history and no access to the people involved
* Good, because writing the alternatives down before building routinely changes what gets built
* Good, because a decision and the code implementing it are reviewed together
* Good, because [deviations.md](../deviations.md) has somewhere to point: the register is the
  index, the ADR is the argument
* Bad, because it is friction on every non-trivial change, and friction is what gets skipped under
  deadline pressure. The mitigation is that the bar is "a decision that had alternatives", not
  "every change" — a record for an obvious choice is noise that trains people to ignore the rest
* Bad, because a superseded record left in place can be read as current by someone who does not
  check the index or the `status` field

### Confirmation

The index in [README.md](README.md) lists every record. A pull request that changes an
architectural choice without an accompanying record is incomplete, and that is a review check
rather than an automated one — no linter can tell an architectural decision from a rename.

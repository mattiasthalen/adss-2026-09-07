# Deviations register

Every knowing departure from a principle in [blueprint.md](blueprint.md) or a hard rule in
[conventions.md](conventions.md) is recorded here, with the ADR that decided it.

The register exists because an unregistered exception is indistinguishable from a mistake. Once
one exists, the next person reads it as precedent and copies it, and a year later the rule is
folklore. Writing the cost down keeps the trade visible; writing an exit condition down keeps it
from becoming permanent by default.

A deviation is legitimate only when all four fields are answerable. If the cost cannot be named,
the deviation has not been understood. If the exit condition cannot be named, it is not a
deviation but a change of rule, and the rule should be superseded instead.

## Entries

| # | Rule deviated from | Why | Cost | Exit condition | ADR | Status |
|---|---|---|---|---|---|---|
| D-0001 | [blueprint.md](blueprint.md) **R2 — No cross-dependency**: "a data product owns its structures and does not consume another product's" | Every slice's page reads one generated Unified Star Schema in `dar__uss`. The structure being shared is additive by construction — keys inherit along many-to-one relationships, measures stay on the stage that owns them — so the fan trap R2 exists to prevent cannot occur in it, and one shared calendar is what lets two processes be compared at all. Generating a private copy per page would make that comparison a cross-schema join, which is most of what a USS is for | A change made for one reader is visible to all of them the moment it is generated. There is no per-reader projection, so "this reader may not see freight" cannot be expressed. Two readers cannot hold different definitions of the same measure. The first thing to break is a slice needing a measure defined one way for one reader and another way for another — it will have to be modelled as two measures | A second consumer needs isolation: a different shape of the same structure, or a group that must not see part of it. The generator then gains per-group projections over the same bridge and this entry is resolved | [0002](adr/0002-dar-is-one-generated-unified-star-schema.md) | open |

## Entry format

Entries are appended in the order they are decided and never removed. A resolved deviation is
marked resolved, with the date and the commit or ADR that resolved it, because the history of why
something looked necessary is worth as much as the fact that it no longer is.

Field by field:

* **Rule deviated from** — quote or link the exact rule. "The spirit of layering" is not a rule;
  a row in a blueprint table is.
* **Why** — the constraint that made the conforming option unworkable *here*. Convenience, time
  pressure and unfamiliarity are not constraints; they are reasons to do it properly.
* **Cost** — what this buys the system in trouble. Name the first thing that will break, who pays
  for it, and which future change it makes more expensive. A deviation with no cost is evidence
  the rule is wrong, so supersede the rule instead of deviating from it.
* **Exit condition** — the observable thing that has to become true for the deviation to be
  removed. "When we have time" is not observable.
* **ADR** — the decision record that argued it. Every deviation has one; the register is the
  index, the ADR is the argument.
* **Status** — `open` while it stands, `resolved` once it is gone.

## Review

The register is read at the start of every slice, and each open entry is checked against its exit
condition. An entry whose exit condition has been met and which is still open is a defect in the
same way a failing test is: the system is no longer doing what its own documentation says.

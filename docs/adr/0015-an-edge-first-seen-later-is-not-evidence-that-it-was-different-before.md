---
status: accepted
date: 2026-09-08
decision-makers: [adss maintainers]
slice: 5
---

# An edge first seen later is not evidence that it was different before

## Context and Problem Statement

[ADR 0006](0006-an-inherited-key-is-resolved-as-of-the-row-that-inherits-it.md) resolves an
inherited key from the pair in force **as of the observation of the row that inherits it**:

```sql
AND pair.eff_tmstp <= revision._observed_at
```

[ADR 0009](0009-a-stage-may-be-dated-by-a-date-it-inherits.md) dates an inherited event the same
way, off the same parent version.

Slice 5 adds `PRODUCT` and `CATEGORY` to a model that already had order lines. Built from a clean
clone every category key resolves — one ingest, one clock, every contract landed at the same
instant, so `<=` is satisfied by equality. Built **incrementally**, on a lake that already held
the order lines, not one of 2,155 rows resolves:

| | `product_key` | `category_key` |
|---|---|---|
| `order_line` / `ordered`, 2155 rows | **2155** | **0** |

One hop resolves and the next does not, in the same build. `ORDER_LINE_IS_FOR_PRODUCT` was landed
by the ingest that landed the lines, so its pairs carry that ingest's clock.
`PRODUCT_IS_IN_CATEGORY` was first landed an hour and a half later. The lines have not changed, so
`FULL_LOG` — correctly — wrote no new version of them, and their `eff_tmstp` is still the earlier
one. `08:14 <= 06:49` is false, every pair is excluded, and the dimension is null everywhere.

**CI cannot see this.** It checks out a clean tree with no lake, so it is always the first case.
Green in CI, silently wrong in any deployment that has run before — which is the third time in two
slices that green has meant something other than "the code is right", after an accumulated lake in
slice 4 and a warm lint cache an hour later.

### What `eff_tmstp` actually is

The rule is not wrong about time. It is wrong about what this system's timestamps mean.

Northwind's `$metadata` has eleven entity types and about seventy properties and **not one
modified, updated or version column**. That is why DAB's history is dated by when DAS observed the
row — it is the only history this platform can honestly claim. So `eff_tmstp` is an **observation
time**, not a validity time. It records when we looked, not when the fact became true.

Reading an observation time as a validity boundary in the past asserts something nobody measured:
that the edge was *different* before we first saw it. We have no evidence of that. We have no
evidence of anything before the first observation, which is a different statement, and the one the
data supports.

## Decision Drivers

* the system's own account of what its timestamps mean is applied consistently
* an inherited value that resolves on a clean build and not on an incremental one is a defect
  whichever way it is spelled
* the rule must not silently assume a change nobody recorded
* ADR 0006's actual concern — that "now" is not "then" — survives

## Considered Options

* **Fall back to the earliest observation** when no version precedes the inheriting row
* **Leave it**, and record that a new entity is invisible until existing rows are re-observed
* **Resolve as of now** when nothing precedes
* **Re-historise every entity on every ingest**, so every row has a version at every clock

## Decision Outcome

Chosen: **fall back to the earliest observation.** A pair or a parent version is resolved from the
one in force at the inheriting row's observation; when none precedes it, the **earliest version
ever observed** is used instead.

It is bounded and it is the narrow case: it applies only when this system had not yet looked. The
moment a second version exists, ADR 0006's rule applies unchanged and this clause never fires. It
does not resolve "as of now" — a later correction to an edge is still not applied retroactively,
which is the whole of what ADR 0006 was protecting.

**Why not leave it.** The consequence is that adding an entity does nothing until unrelated data
happens to change. Every question about the new dimension returns a right total with an empty
grouping — the failure this architecture is least able to see, and the one slice 4 spent a record
on. It would also be recorded in a register nobody reads at the moment they need it, which is what
this repository keeps discovering about its own records.

**Why not resolve as of now.** That is what ADR 0006 refused, for a reason that still holds: it
re-points a child's whole history at whichever parent it has today, so a line ordered when a
product was in one category would be reported under the category it moved to. The fallback is
strictly narrower — it never overrides a version that does precede.

**Why not re-historise on every ingest.** `FULL_LOG` writes a version when the row changes, which
is what makes the history mean anything; making it write unconditionally is the `FULL` behaviour
slice 1 measured and refused, and it would fill the history with versions recording that nothing
happened.

### What this does not become

It is not a licence to relax an as-of comparison whenever one is inconvenient. The rule is
specific: **absence of observation is not evidence of difference.** Where this system does have
two observations it uses the earlier one, as before. The next reader tempted to widen a predicate
because a join came back empty should check whether the emptiness means "we knew something else
then" or "we had not looked yet" — and only the second is this.

## Consequences

* Good, because an incremental build and a clean build now produce the same warehouse, which is
  what "rebuildable from DAS at any time" has to mean
* Good, because adding a dimension to a model that already has data does what the person adding it
  expects, rather than nothing
* Good, because the assumption it makes is the one the data supports, and it is written down
* Bad, because a product that genuinely moved category between two observations is reported under
  the category we first saw, for lines observed before we looked. That case is indistinguishable
  from the ordinary one with a single observation, so no rule can get it right; this one is at
  least stated
* Bad, because the resolution is now two clauses of an `ORDER BY` rather than one predicate on a
  join, and the second clause fires rarely enough that nothing but a test will exercise it

## Confirmation

Written after the code, against the code.

`tests/test_two_hops_sql.py` builds a warehouse in which the pair is observed **after** the row
that inherits it — the shape the real lake had — and asserts the key resolves; a second where two
pair versions straddle the observation, asserting the earlier one still wins, so the fallback has
not swallowed ADR 0006's rule; a third with no pair at all, asserting the key is still null,
because the fallback fills in what was not yet observed and not what was never recorded; and a
fourth with two versions both later than the observation, asserting the **earliest** is taken.

That fourth one exists because the first pass at this section would have been false. Two mutations
were run and both survived: with a single later version the direction of the fallback's sort is
unobservable, and `NULLS LAST` is a no-op on an engine that already defaults to it. The tests were
sharpened until both fail — the fourth case for the direction, and one that sets
`default_null_order` to `NULLS_FIRST` and asserts the answer does not move, which is what makes
saying `NULLS LAST` load-bearing rather than decorative. A comment claiming this engine sorts
nulls first on a descending sort was wrong and is corrected: it is a session setting, which
Postgres and DuckDB default differently.

What is **not** confirmed: that the assumption is true of this source. Nothing in Northwind says
when a product changed category, which is the whole reason this decision exists.

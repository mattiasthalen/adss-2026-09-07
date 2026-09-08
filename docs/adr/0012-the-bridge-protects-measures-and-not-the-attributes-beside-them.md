---
status: accepted
date: 2026-09-08
decision-makers: [adss maintainers]
slice: 4
---

# The bridge protects a measure and not the attribute it was made from, so a question may not aggregate a peripheral's number

## Context and Problem Statement

D-0001 puts every process into one shared `dar__uss`, departing from the blueprint's
no-cross-dependency rule. Its entire justification, written in slice 1 and carried unexercised
through three slices, is that *the fan trap R2 exists to prevent cannot occur in it* — because
keys inherit along many-to-one edges and measures do not.

Slice 4 is the first slice with two grains, so it is the first that can test that. It half holds.

**The measures are safe, structurally, and this is the first demonstration of it.** Over the real
two-grain bridge — 830 order rows and 2155 line rows — every shape returns the truth:

| query | freight | revenue |
|---|---|---|
| both measures, whole bridge, no filter, no join | **64,942.69** ✓ | **1,265,793.0395** ✓ |
| both, per order month, joined to `_calendar` (3794 rows) | **64,942.69** ✓ | **1,265,793.0395** ✓ |

2155 line rows carry `order_key`, and freight does not move. That is what D-0001 has been
asserting, and it is now a measurement.

**The peripheral is not safe, and the query that breaks it is not exotic.** It is one join — the
same join `q01` and `q02` already write:

```sql
SELECT sum(o.freight_charge)
FROM dar__uss._bridge AS b
INNER JOIN dar__uss."order" AS o ON b.order_key = o.order_key
WHERE b._event = 'ordered';
-- 207,306.10 against a true 64,942.69. Once per LINE.
```

`freight_charge` is a **published column of the order peripheral**. So the rule generalises to
something D-0001 never said:

> Any `NUMBER` attribute that is also a measure's source appears **twice** in `dar__uss` — once
> as an additive measure on its owning stage, protected by a typed null on every other branch,
> and once as a plain attribute on its peripheral, protected by nothing. `FREIGHT_CHARGE`,
> `SHIP_LAG_DAYS` and `REVENUE` are all in that position.

**And it was already live at slice 3, undetected.** On the warehouse as shipped in PR #3, before
any line existed, the same query returns **128,897.71** against 64,942.69 — because `ORDER` had
two events, so the bridge already had two rows per order. Slice 4 does not introduce the trap. It
raises it from 1.98× to 3.19× and makes it reachable from another entity's stage, which is what a
fan trap actually is.

## Decision Drivers

* the property D-0001 rests on is demonstrated or the deviation's argument is not carried
* what the demonstration does *not* cover is stated, rather than left for a reader to discover
* the trap is kept out of what this system publishes, since it cannot be kept out of SQL
* nothing legitimate is removed to achieve it

## Considered Options

* Stop publishing a numeric attribute on a peripheral when it is also a measure's source
* Publish it, and add a query-time rule to the bridge's contract
* Publish it, add the rule, **and refuse a question that breaks it**

## Decision Outcome

Chosen: **the third.** The property is proved for measures, the limit of that proof is written
into ADR 0002's contract as a third query-time rule, and a question whose answer query aggregates
a peripheral's numeric column is **refused** by the question checker.

**Why not remove the column.** A numeric attribute on a peripheral is legitimately useful — it is
how a reader filters "orders whose freight was over 100" or sorts a table by it. Removing it to
prevent a bad aggregate would break the good use to prevent the bad one, and would make the
peripheral a worse description of the entity than the entity has.

**Why a rule alone is not enough.** ADR 0002 already publishes two query-time rules and neither
covers this one; a third would be true, unread and unenforced. This system's own position, stated
in ADR 0006 and ADR 0008, is that a failure which is invisible gets refused where it can be seen.

**What can actually be enforced.** Not "no reader writes a bad query" — a bridge does not stop a
bad query, it makes the good one natural, and the honest form of that claim is narrower than it
sounds. But every number this system *publishes* goes through a question's `uss.sql`, and those
are files this repository owns and already checks. So: an answer query may not apply an aggregate
to a column of a peripheral. It must aggregate `_measure__…` columns, which are the ones the
bridge protects. That is checkable, it is checked, and it stops the trap entering the artefacts
anybody reads.

The rule has one deliberate hole: a question may still aggregate a peripheral's column if it does
so outside `uss.sql`, and a person at a SQL prompt can do whatever they like. That is not a gap
this decision can close and pretending otherwise would be the false comfort D-0001 has been
running on.

### D-0001 does not close

Its exit condition, quoted whole, is: *"A second consumer needs isolation: a different shape of
the same structure, or a group that must not see part of it."* That has not happened. Slice 4
adds a fourth question read by one more persona, and a persona is not a consumer needing
isolation — nothing here needs a different shape of the bridge and nothing must be hidden from
anybody. Closing the entry now would be closing it for a reason that is not its own exit
condition, which is how a register becomes decoration.

What changes is the register's **Why**. It has said since slice 1 that the fan trap "cannot occur"
in the shared structure. That is true of the measures and false of the peripherals, and the entry
now says which, with the number.

## Consequences

* Good, because the argument D-0001 has been carried on for three slices is measured rather than
  asserted, and the measurement is repeated on every build
* Good, because the half that does *not* hold is written down with the query that breaks it and
  the number it returns, rather than being discovered by somebody trusting the entry
* Good, because the trap cannot enter a published answer, which is where it would be believed
* Bad, because the refusal is a text rule over SQL, and a sufficiently determined query defeats
  it — an aggregate spelled across a subquery, for instance. It raises the cost of the mistake
  from zero to deliberate, which is what the other refusals in this system do too
* Bad, because a question that genuinely wants a peripheral's number aggregated — "the largest
  freight on any order" — now has to model it as a measure. That is more honest and more typing,
  and it is the same trade ADR 0008 made

## Confirmation

`tests/test_uss.py` asserts the fan-out property directly, on the neutral fixture's two grains: a
parent's measure summed over a bridge containing its children equals the parent's own total, the
finer measure is right in the same scan, the coarser measure is null on every finer row while the
inherited **key** is not, and — the falsifiable half — the parent's total does not move when a
parent gains children. It runs the generated SQL against a warehouse it builds, rather than
reading the SQL for substrings, because a substring assertion would pass a generator that emitted
the right nulls in the wrong branch. Mutating the generator to make measures inherit as keys do
emits valid SQL and a wrong number, and all four assertions fail.

A generated data check, one per measure, asserts it is null on every stage that does not own it —
the mechanism rather than the number, on the real build.

`tests/test_questions.py` asserts that an answer query aggregating a peripheral's column is
refused, and that the same aggregate over a `_measure__` column is accepted.

What is **not** confirmed: that no reader ever writes the bad query at a prompt. Nothing can
confirm that, and the register now says so instead of implying otherwise.

---
status: accepted
date: 2026-09-08
decision-makers: [adss maintainers]
slice: 4
---

# A stage may be dated by a date it inherits along the walk, named where it is inherited from

## Context and Problem Statement

Slice 4 asks for revenue per order **month**. Revenue is measured on an order line — quantity
times price less discount — so the bridge needs a row per line. And **an order line has no
date.** The source's `OrderDetail` has five properties and not one of them is a date; the live
`$metadata` says so, and there is nothing to map from.

The generator can only date a stage by an attribute of the event's own entity. `read_uss`
resolves `date_attribute` against `model.entity(event.entity_id)`, so naming the order's date on
a line event fails with a bare `KeyError: "ORDER_LINE has no attribute 'PLACED_ON'"` — not even a
`UssError`, so the refusal arrives with no explanation attached.

Nor may any layer go and fetch one. M1 forbids a join or a subquery in a mapping's `table:`; M5
forbids a reach into another table; a DAS contract has no key for a join. A second mapped table
on `ORDER_LINE` would be keyed by the order, which is not a line.

So the question the plan wrote down for this slice cannot be built at all without deciding
something the plan did not anticipate.

**What is already true, and is the whole reason this is small.** The walk exists. For every
edge, `_inherit_cte` already resolves the parent **as of the observation time of the row that
inherits** and puts the parent's key on the child's bridge row. ADR 0006 spent its whole decision
on getting that instant right. A date is another column of the row the walk already found.

This is also what a Unified Star Schema does. Puppini's bridge is a row per measurement event;
the event for an order line is the order being placed, on the day it was placed. Dating a line by
its order's date is not an accommodation — it is what the shape means.

## Decision Drivers

* the question is answerable at all, which today it is not
* a bridge row is true as of one instant, and every column on it is true as of that same instant
* a mechanism that already exists, extended, rather than a second one beside it
* the date a reader sees is traceable to a definition in the one place data is explained
* slice 5 walks two hops, and must not need a third mechanism

## Considered Options

* **(a)** The date inherits along the walk, named as `<ENTITY>.<ATTRIBUTE>` in the sidecar
* **(b)** Record `OrderDetails?$expand=Order` so the landed line carries the order's date
* **(c)** Give `ORDER_LINE` its own date attribute, mapped from the order via the source
* **(d)** Drop the calendar and let the question group on the order peripheral's date

## Decision Outcome

Chosen: **(a), the date inherits along the walk**, written in `dab/uss.yaml` as

```yaml
    - id: ORDERED
      entity: ORDER_LINE
      date_attribute: ORDER.PLACED_ON      # qualified: inherited along the edge to ORDER
```

An unqualified `date_attribute` still means an attribute of the event's own entity, which is
every event declared so far and stays the ordinary case. A qualified one names the entity the
date is inherited from, and that entity must be reachable along a declared edge from the event's
entity — otherwise it is refused, by name, with the edges that do exist listed.

The date is resolved **in the same CTE and at the same instant as the key**, because they are the
same row of the same parent. Anything else would put two instants on one bridge row, which is the
confusion ADR 0006 calls the entire difference between the option it chose and the one it
rejected. A line whose order cannot be resolved gets a null date and therefore no bridge row, by
the filter the generator already emits — consistent with how an event that did not happen is
already handled.

**Why not (b), expanding the source record.** It is the cheap-looking one and it is the worst.
`PLACED_ON` would then have two homes — the order's own attribute and a copy on every line — and
B8 says a definition exists exactly once. Two homes is how two reports start disagreeing, and
this one would disagree *silently*, because both copies come from the same load and would agree
until the first time they did not. It also needs a new contract key and a new `Endpoint` field to
build a URL the recorder cannot currently express.

**Why not (c), a mapped date on the line.** Same objection with an extra step: the mapping would
have to reach into another table to get it, which M5 forbids outright.

**Why not (d), grouping on the peripheral.** The stage still needs a non-null date to exist at
all, so it does not escape the problem. And ADR 0007 rejected the peripheral-as-of-now reasoning
already: a peripheral is current state, a bridge row is the version in which the event is dated,
and reading one against the other puts two instants on one answer.

### What this does not become

The temptation this record exists to close is to let `date_attribute` take an expression, or to
let it reach further than one declared edge because "the walk goes there anyway". Neither. The
value is *a date attribute of an entity reached along a declared edge*, resolved exactly as its
key is resolved. Arithmetic on it belongs in the mapping under ADR 0007; anything else is a
second expression language in a file that is not linted, which ADR 0007 refused on §3.

## Consequences

* Good, because the question is answerable, and answerable at the grain it is asked at
* Good, because it reuses the walk rather than adding a mechanism beside it: one more column off
  a row the generator already resolves, at an instant it already got right
* Good, because slice 5's two-hop chain inherits this unchanged — a date reached along two edges
  is the same rule applied twice, and needs no new decision
* Good, because the date on a line is traceable to `ORDER.PLACED_ON`, which has one definition,
  so the page's glossary can explain the axis a reader is looking at
* Bad, because `dab/uss.yaml` now has two shapes for one field, and a reader has to know that a
  dot means "inherited". The alternative — always qualifying — would rewrite three existing
  declarations for no gain, and `<ENTITY>.<ATTRIBUTE>` is the notation the questions already use
* Bad, because a line's date now moves if its order is re-pointed to a different order, which
  cannot happen in this source and is a real property of the design rather than a bug. The
  as-of resolution is what bounds it: the date is the one in force when the line was observed

## Confirmation

`tests/test_uss.py` asserts that a qualified `date_attribute` is resolved from the inherited
entity and not from the event's own; that it is refused, naming the available edges, when the
entity it names is not reachable along one; that an unqualified one still means the event's own
entity; and that the date and the key come from the same CTE, so no bridge row can carry two
instants. A sidecar beside the neutral fixture gains an event on `CHILD` dated by
`PARENT.HAPPENED_ON`, which is
the shape this record is about and which the fixture did not have. Its SQL is linted with every
other emitter's and executed by `tests/test_inherited_date_sql.py`, which builds a parent with
more than one version -- the real warehouse has exactly one per key, so the real warehouse
could not have shown either of the two defects that test was written for.

A generated data check asserts that every bridge row of such a stage carries the same
`_event_date` as the stage that **owns** that date, for the key on that row — 2,155 comparisons on
the real build. It is independent rather than circular: the parent's own stage gets the date from
its version CTE and the child's from its inherit CTE, so resolving the date at a different instant
than the key, or against a different version of the parent, shows up here. Both of those are
invisible in the warehouse otherwise. `tests/test_inherited_date_check.py` runs it against a
bridge built to fail it.

A check is generated only where the entity the date comes from has an event on that same
attribute. Without one there is nothing independent to compare against, and a check that
re-derives what it expects from the generator agrees with a broken generator.

**This section previously claimed that check existed.** It did not: nothing in `src/adss/checks.py`
emitted it and no such file was in `checks/`. A security review found the claim, and it is the
third confirmation in this repository to name a check that could not do what it said — which is
why the rule about running the mutation before writing the sentence now lives in the adss skill.

What is **not** confirmed, and is recorded rather than claimed: a row dropped because its
inherited date did not resolve. This decision makes such a row absent by construction, and an
absent row disagrees with nothing. Checking that would need a count of the rows a stage *should*
have, and nothing in the model states one — a line whose order has no date is legitimately absent,
and no check can tell that from a line the generator lost.

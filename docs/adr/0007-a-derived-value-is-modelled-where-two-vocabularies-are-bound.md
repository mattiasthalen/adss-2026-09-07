---
status: accepted
date: 2026-09-08
decision-makers: [adss maintainers]
slice: 3
---

# A value derived from one row is modelled in DAB and computed in the mapping, and arithmetic there is bounded by this record

## Context and Problem Statement

"How many days did they take" is the first number this system reports that does not exist in the
source. Every measure so far has been a count — one per row — or a sum of a single attribute that
was already there. A ship lag is two dates subtracted, and there is no established place to put
the subtraction.

Three things are already settled and an argument that reopens them has not read the standard.

**The measure's name and its arithmetic are written down.** Conventions §2's own worked example is
this question:

> | `avg_days_to_ship` | `ship_lag_orders_days` | The average is
> `sum(ship_lag_orders_days) / sum(shipped_orders_count)` at query time, from two additive
> measures. |

So the two measures are named, the division is a question's job, and `ship_lag_orders_days` is a
*stored measure* — a column in the bridge's published contract. That sentence decides more of this
slice than anything else in the repository.

**An event that did not happen is already decided.** ADR 0002: "A transaction stage reads
`dab.view_<E>_hist`, keeps the latest version in which the event's date is set… An unshipped order
therefore has no shipment event *by construction* rather than by a filter somebody has to
remember." The generator emits `WHERE <date> IS NOT NULL` and a test pins it. The 21 unshipped
orders are the case that design was written for, not a new problem.

**Two events on one entity already work.** The neutral fixture has declared two events on one
entity since slice 1, and generating this slice's bridge from a scratch copy of the model needs
**no generator change at all**. What is new is one thing only: a sum measure with no attribute to
point at.

## Decision Drivers

* a number the business reads has exactly one definition, in the one place data is explained
* the acceptance check keeps an arbiter: when two queries disagree, something decides which is wrong
* the precedent this sets is one the next three slices can live with
* a rule the next person inherits, rather than an example they have to interpret
* DAR stays a layer that can be deleted and rebuilt from the model

## Considered Options

* **(a)** A `NUMBER` attribute on `ORDER`, computed in the mapping from two columns of its own row
* **(b)** An expression in `dab/uss.yaml`, emitted into the bridge by the generator
* **(c)** Computed in the question's `uss.sql` at query time from two dates on the peripheral

## Decision Outcome

Chosen: **(a), a `NUMBER` attribute computed in the mapping** — with the precedent bounded here,
because "M5 permits it" is otherwise the standing argument for whatever M5's regex happens not to
catch.

It is also the only option that generates today. A `sum` measure must name an attribute the model
declares; `src/adss/uss.py` raises `KeyError: "ORDER has no attribute …"` otherwise, and there is
no `expression:` field on a measure. (b) and (c) are not choices between working designs — they
are proposals to build something.

**Why not (b).** Putting the arithmetic in the generator is the serious rival, and it is cleaner in
one respect: nothing derived is stored, so nothing derived can drift. It fails on where it leaves
slice 6. A second source that reports elapsed days *directly* has no two dates for a DAR expression
to subtract, so integrating it needs the attribute anyway — and then there are two definitions of
ship lag, a DAB attribute and a DAR expression, differing by source. That is B2 and B8 failing
together in the slice whose entire purpose is to prove B2. It also costs slice 4, where the
expression vocabulary would have to grow from a two-date special case to general arithmetic in the
same slice that first exercises the fan-out property D-0001 is carried on. Two risky things at once.

A free-text SQL expression in YAML additionally breaks §3 — "SQL that lives in a Python string is
written to a file so the same linter sees it" — because the linter runs on `.sql` files and would
never see it.

**Why not (c).** Conventions §2 says ratios are not stored and the numerator *is* an additive
measure; (c) reads it as licence for the whole computation and has no `ship_lag_orders_days` at
all. The question could then not declare what it measures: every `defines` entry must resolve to
something the model or the sidecar defines, so "days to ship" would exist in one SQL file and
nowhere else, with the page's own glossary unable to explain the second number it displays.

The fatal objection is narrower. §6: "When a question's two queries disagree, `dab/model.yaml` is
the arbiter. The query that departs from the definition is the one that changes." Under (c) the
answer query says `date_diff('day', o.placed_on, o.shipped_on)`, the control says
`shipped_date - order_date`, and the model has nothing to say about either. Neither query can
depart from a definition that does not exist, so the repair procedure stops existing in exactly the
slice that introduces the first computed number — and the cheapest repair becomes making the two
queries agree with each other, which deletes the only thing the check measures.

(c) also computes as of the wrong instant: the peripheral is current state, while a bridge row is
the latest version *in which the event's date is set*. Those coincide today. ADR 0006 records a
review catching precisely this confusion one layer down, and calls the distinction the entire
difference between the option chosen there and the one rejected.

### The line this record draws

M5 permits an expression that reads its own row, and its prose enumerates three forms — a column,
a cast, a `CASE` over columns of that row. A subtraction of two dates is none of them, and passes
only because M5's mechanical check is four keywords and seven function names. Relying on that
silently is the quiet exception §11 rules out. So the rule, in force from here:

> **Arithmetic over columns of the same row is permitted in a mapping.** A `CASE` on *values*, a
> default, a coalesce that invents a value, a filter, a bucket, or anything that changes the grain
> is not — those are meaning, and meaning belongs in the model as an attribute with a definition.

Conventions §1.4 M5 is clarified to say so, per §11's first rung. The distinction is that
arithmetic over one row produces a value the row already implies; the others produce a value
somebody chose, and a choice needs a definition beside it.

One trap belongs in the record because the error message misleads: `extract(DAY FROM (b - a))` is
**refused** by M5's checker, because the regex matches the bare word `from` inside the expression.
The refusal says the expression "reaches beyond its row", which it does not. `date_diff('day', a,
b)` passes and is what the mapping uses. The false refusal is a defect in the checker, fixed in
this slice.

## Consequences

* Good, because the lag has one definition, in the one place the data is explained, and both of the
  question's queries are measured against it
* Good, because a second source that reports the lag directly maps onto the same attribute rather
  than needing a second derivation — which is the slice-6 case that decided this
* Good, because slice 4's revenue follows the same rule without a new mechanism: quantity, price
  and discount are columns of one order line, and their product is arithmetic over that row
* Good, because DAR stays deletable: everything it emits still comes from the model and the sidecar
* Bad, because a derived value is now stored, and a stored derivation can disagree with what it was
  derived from. Nothing today can make that happen — one mapping, one source — and it becomes
  possible in slice 6
* Bad, because the line above is a rule enforced by review. M5's checker cannot tell arithmetic
  from a bucket, and writing a checker that could is a bigger thing than this slice needs

## Confirmation

`tests/test_mapping_rules.py` asserts that a same-row function is accepted and that the reaching
forms are still refused, including the `extract(… FROM …)` case that used to be refused for the
wrong reason.

The two measures are `SHIPPED_ORDERS_COUNT` and `SHIP_LAG_ORDERS_DAYS`, and the ratio appears in no
schema: the question returns both additive measures and the page divides them. That is not only
§2's rule but what keeps the acceptance check exact — every value either query returns is a
`BIGINT` count or an exact `DECIMAL` sum, and the two answers are compared row by row as values.
A float would break that comparison in a way no test would find on the machine that wrote it:
DuckDB's `sum` over doubles is order-dependent, measured here as `[0.1, 0.2, 0.3]` summing to
`0.6000000000000001` and the same three reversed to `0.6`. `tests/test_questions.py` pins that
every question's answer holds only exact types, so the first float-valued measure fails a test
rather than producing a disagreement that is not one.

What is **not** confirmed, and is recorded rather than claimed: nothing checks that
`SHIP_LAG_DAYS` still equals the two dates it was derived from. Such a check is tautological
today — one mapping computes it from those columns and nothing else writes it — and stops being
tautological in slice 6, which is the slice this decision's one real risk lands in. It is not
written now because a check that cannot fail teaches a reader that the property is guarded when it
is not; slice 6 writes it, against the case that makes it meaningful.

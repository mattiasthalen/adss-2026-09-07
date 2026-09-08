---
status: accepted
date: 2026-09-08
decision-makers: [adss maintainers]
slice: 4
---

# An ingest is one observation, so every contract it lands shares one clock

## Context and Problem Statement

DAB's history is dated by when DAS observed the row. Northwind's `$metadata` has eleven entity
types and about seventy properties and not one modified, updated or version column, so the
observation time is the only history this platform can honestly claim — and `extracted_at` is
`to_timestamp(cast(_dlt_load_id AS DOUBLE))`, the loader's own clock, so the partition key and the
history clock derive from one fact rather than from two.

**One fact per contract.** `land()` creates one pipeline per contract and `das ingest` runs them
one after another, so a single ingest produces one `_dlt_load_id` per contract, each a fraction of
a second after the last. Measured on a clean rebuild:

| contract | `extracted_at` |
|---|---|
| `customers` | 06:40:43.517150 |
| `order_details` | 06:40:43.916979 |
| `orders` | 06:40:44.199092 |

Contracts are landed in `sorted()` order, so `order_details` always precedes `orders`. Always: the
underscore sorts before `s`, and the loader's id is the wall clock at `pipeline.run()`.

Slice 4 is the first slice that reads one entity's history *as of another entity's observation*.
ADR 0009 resolves an inherited date off the parent version in force when the child was observed:

```sql
LEFT JOIN dab."view_ORDER_hist" AS dated
    ON dated."ORDER_key" = pair."ORDER_key"
    AND dated.eff_tmstp <= revision._observed_at
```

`revision._observed_at` is `order_details.extracted_at`. `dated.eff_tmstp` is
`orders.extracted_at`. They are 0.28 seconds apart, in the wrong direction, so **no ORDER version
precedes any ORDER_LINE row**, the date resolves to null for every line, and ADR 0009's own rule —
a row whose inherited date does not resolve gets no bridge row — removes all 2,155 of them. The
`ordered` stage is empty and q04 returns nothing against the source's 23 rows.

**It was green here for a reason that is not a reason.** This working tree's lake is gitignored
and had accumulated: sixteen `orders` loads, twelve of them older than the earliest
`order_details` load. `view_ORDER_hist` holds exactly one version, from the first of those, at
22:11 the previous day — because `FULL_LOG` writes a new version only when the row changes, and
the recording never changes. That single old version satisfies the `<=`, and it carries the same
`PLACED_ON` any newer one would. A lake that accumulates across runs is a machine for turning a
broken build green.

The bug is not the `<=`. ADR 0006 and ADR 0009 are right that the parent must be resolved as of
the child's observation. The bug is that "the observation" is not one time.

## Decision Drivers

* an as-of join between two entities must not depend on the order their contracts were landed in
* the fix belongs where the fact is wrong, not where the fact is read
* DAS may not learn what DAB's relationships are; the flow runs one way
* what a clean clone builds is what the repository claims, or the claim is worthless

## Considered Options

* **One clock per ingest** — every contract landed by one `adss das ingest` gets one `extracted_at`
* **Land contracts in dependency order** — sort parents before children
* **Fall back to the parent's earliest version** when none precedes the child
* **Compare dates rather than instants** in the as-of join

## Decision Outcome

Chosen: **one clock per ingest.** `das ingest` takes the time once and every contract it lands
carries it, so `extracted_at` says when the *system* observed the source rather than when a
particular pipeline happened to start. `<=` is then satisfied by equality and the as-of join is
independent of landing order.

This is a decision about meaning, not a workaround. Rows fetched by one run of one command are one
observation of one source. Dating them individually says the business changed between two HTTP
calls, which nothing here can know and nothing downstream should have to reason about.

`extracted_at` becomes an explicit column landed beside the payload, rather than a derivation from
`_dlt_load_id`. That is the same number of clocks the spike argued for — "record the source once;
one fact, in two shapes, never two clocks" — restored. What exists today is three clocks, one per
contract, which the spike's own rule already forbade and nobody noticed because nothing compared
them until now.

**Why not land in dependency order.** It would fix the direction and not the cause: two contracts
would still carry two times, so a partial ingest, a retry, or any future check comparing
observation times across entities would break the same way. It also requires DAS to know which
entity is a parent of which, and that is DAB's knowledge — the layer whose whole purpose is to be
independent of where the data came from would have to be consulted by the layer that fetches it.
That is the flow rule, backwards, to fix a clock.

**Why not fall back to the earliest version.** It changes what "as of" means, so a parent this
system genuinely had not yet observed would be resolved against a version from its future. It also
fixes one query rather than the fact, and the next as-of comparison would need the same patch.

**Why not compare dates.** A load spanning midnight breaks it, and the answer to "these two
instants are wrongly ordered" is not "look at them less closely".

### What this does not change

`extracted_on`, the hive partition key, is still the loader's own date, and the existing clock
check still asserts it equals `cast(extracted_at AS DATE)` in UTC. The two can now disagree only
if a load starts before midnight and writes after it, which is the case that check was written for.

## Consequences

* Good, because an as-of join between two entities means what it says, and does not depend on the
  alphabetical order of contract file names
* Good, because a clean clone builds what this repository claims it builds — which was not true of
  slice 4 as first committed
* Good, because the rule generalises: every future comparison of observation times across entities
  is now comparing one fact to itself
* Bad, because two contracts landed by two separate commands still carry two times, correctly —
  they are two observations — so a reader who splits an ingest gets history that says so. That is
  the honest answer and it is still a surprise waiting for somebody
* Bad, because `extracted_at` is now a column this layer writes rather than one it derives, so a
  source field named `extracted_at` is refused where before it was merely shadowed. It was already
  reserved, so nothing changes in practice
* Bad, because the local lake that hid this is still there and still accumulates. Nothing here
  makes a stale lake fail; CI's clean checkout is what says the build is real

## Confirmation

`tests/test_das_round_trip.py` lands two contracts in one ingest, in the order that broke this —
the child's contract first — and asserts every row of both carries the same `extracted_at`, and
that the second landed is not later than the first. It fails on the previous derivation.

The measurement above is repeatable: a clean tree with no `das/lake/` builds an empty `ordered`
stage before this change and 2,155 rows after it, and `adss check` reports `q04: the source and the
star schema agree` in the second case only. CI does exactly that on every push — checkout, build,
check — with no lake, so the clean rebuild is the standing test rather than something anybody has
to remember to run.

**A correction to the Consequences above, which were written before the code.** They say nothing
here makes a stale lake fail. Building it showed otherwise, twice over. A load landed before this
change has no `extracted_at` column at all, `union_by_name` reads it back as null, and DAB then
historizes on a null clock — which surfaced as three duplicate-version findings naming FULL
ingestion, a cause that had nothing to do with it. Worse, the clock check passed on those rows:
it said `extracted_on <> cast(extracted_at AS DATE)`, and a null is neither equal nor unequal to
anything, so it counted neither side of exactly the rows it exists to find. It says `IS DISTINCT
FROM` now, `tests/test_das_executes.py` lands a load with no clock and asserts the check finds it,
and a stale lake therefore fails on its own layer with its own name rather than three layers later
under somebody else's.

The remedy for a stale lake is to delete it. `.gitignore` already says everything in it is
reproducible from `das/fixtures`, and it is: the local lake was removed and rebuilt, 48 checks.

What is **not** confirmed: that no other pair of facts in this system is compared across two
clocks. This one was found by a question failing, not by a check that looks for the shape.

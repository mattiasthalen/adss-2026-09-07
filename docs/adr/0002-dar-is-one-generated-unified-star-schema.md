---
status: accepted
date: 2026-09-07
decision-makers: [adss maintainers]
slice: 1
---

# DAR is one generated Unified Star Schema: an event bridge whose stages own their measures and inherit only keys, one peripheral per entity, one dense calendar

## Context and Problem Statement

DAR is the layer a person reads. The blueprint says it is volatile and generated (R4), and the
Unified Star Schema is the shape chosen for it: one *bridge* holding a row per measurement event,
one *peripheral* per entity holding its current state, and one calendar every process is dated
against. This record fixes what the generator emits, because every question, every page and every
future consumer is written against those column names and will not survive them changing.

Three things about the source make the shape less obvious than the description sounds.

**Fan-out.** The USS description says keys and measures propagate downward along many-to-one
relationships. Keys can. Measures cannot: if a parent's measure were copied onto every child row
that points at it, summing that measure would multiply it by the number of children. That is the
classic fan trap, and avoiding it is the entire reason a bridge exists rather than one wide join.

**History.** DAB keeps a version of every entity row. A question about something that *happened*
and a question about a state as it was *observed* are different questions and need different rows,
but they belong in one table, because the whole value of the bridge is that two processes can be
summed and compared on one calendar.

**What the generator is allowed to read.** Two observations constrain this hard, and both were
made against the real engine on DuckDB rather than reasoned about. `<entity>_focal` and
`<entity>_idfr` are created but never populated — a generator that joined to them would produce
empty results and no error. And `view_<entity>_with_rel` carries no relationship key columns at
all, despite its name; its column list is byte-identical to `view_<entity>`. A generator built on
the names alone would be wrong in both directions.

There is a fourth thing, and it is the one this slice cannot demonstrate. The argument that one
shared bridge is safe rests on the walk over many-to-one edges. Slice 1 has one entity and no
relationships, so the walk has zero edges and nothing inherits. The property is asserted here and
first exercised in slice 2.

## Decision Drivers

* a `sum()` over the bridge is right without the reader knowing how the model is shaped
* one calendar, so two processes can be compared
* a published column contract that a model change *extends* rather than rearranges
* deterministic output: the same declarations always produce the same SQL
* nothing silently missing

## Considered Options

* An event bridge with one stage per (entity, event), keys inherited and measures owned
* One bridge row per entity instance, with measures joined on
* A hand-written star schema per question
* Reading DAB's relationship views for the inherited keys

## Decision Outcome

Chosen option: **an event-grained bridge whose stages own their measures and inherit only keys.**

*Keys inherit; measures do not.* A stage carries the key of every entity it reaches by walking
many-to-one edges, and a measure is non-null only on the stage of the (entity, event) that owns
it. Every other branch of the union emits a typed `NULL` in that column. This is what makes
`sum()` additive at any grain the reader chooses, and it is proved by a test rather than trusted:
a fixture with two parents and three children, where `sum(_measure__parent__…)` must still be the
parent total and not three times it.

*One row per measurement event.* A transaction stage reads `dab.view_<E>_hist`, keeps the latest
version in which the event's date is set, and dates the row by that attribute. An unshipped order
therefore has no shipment event *by construction* rather than by a filter somebody has to
remember. A state stage reads the same history view, dates rows by `eff_tmstp`, and marks the
latest version per key `_is_current`. Both kinds land in the same table with the same columns,
which is what lets them be compared.

*The generator reads `view_<entity>_hist` and the relationship pair objects, and nothing else.*
Not `_focal`, which is empty. Not `_with_rel`, which does not carry what its name implies. Reading
the current view instead of the history view would also lose `_observed_at`, which is how a bridge
row carries its own provenance back to the DAS load that produced it.

The rejected options each fail on one of the drivers. One row per entity instance with measures
joined on is the fan trap, restated as a design. A hand-written star per question abandons R4 and
puts the layer's correctness in a person's hands, every time, forever. Reading the relationship
*views* rather than the pair objects is the subtle one: those views rank pairs by effective
timestamp and keep the open rows, and our effective timestamp is the moment DAS observed the row,
so a changed foreign key can drop out of the view entirely — rows silently missing from the
bridge, with the query still running and the total merely smaller.

### The column contract

`dar__uss._bridge`:

| column | type | null | meaning |
|---|---|---|---|
| `_stage` | VARCHAR | no | the entity this row is a row *of* |
| `_event` | VARCHAR | no | the event, lower-cased: `placed`, `shipped`, `observed` |
| `_event_date` | DATE | no | the day it happened, or the day the state was observed; joins `_calendar.date_key` |
| `_is_current` | BOOLEAN | no | always true on a transaction stage; the latest version per key on a state stage |
| `_observed_at` | TIMESTAMP | no | the DAB `eff_tmstp` behind this row, which is the DAS `extracted_at` |
| `<entity>_key` | VARCHAR | own key no, inherited yes | one per entity in model order |
| `_measure__<entity>__<measure>` | BIGINT for a count, DECIMAL(28,8) for a sum | non-null only on the owning stage | one per declared measure, in model order |

`dar__uss.<entity>` is a peripheral **table**, one row per key, key first and attributes in
declaration order. Tables rather than views, so what DAR served is exactly what the build log
describes.

`dar__uss._calendar` is dense and daily from the first to the last `_event_date` in the bridge,
with civil arithmetic only — `year_number`, `quarter_of_year`, `month_of_year`, `day_of_month`,
`year_start`, `quarter_start`, `month_start`, `quarter_label`, `month_label`. Column names avoid
reserved words. Fiscal periods and holidays are business meaning and would need a definition, so
they belong in DAB and not in a generator.

Two rules follow from the contract and are written down because they are query-time traps: a join
on the row's own stage key may be `INNER`, a join on an inherited key must be `LEFT`; and a ratio
is `sum(a) / sum(b)` at query time, never a stored measure.

Nulls: the generator never invents a member. A null dimension stays null, and a question that
wants nulls grouped or excluded says so in the question file, where that choice belongs.

### Consequences

* Good, because a sum over the bridge is additive whatever the shape of the model, and the proof
  is a test rather than a convention
* Good, because every process lands on one calendar, so two of them can be compared
* Good, because a consumer writes against a contract that a model change extends — new entities
  and measures are appended, never inserted or renamed
* Good, because a changed foreign key keeps its row, which reading the relationship view would not
  have done
* Bad, because the bridge is sparse: most cells of most rows are null. At this scale that costs
  nothing, and it is the price of one table instead of one per process
* Bad, because ratios and state questions need care at query time, and nothing in the schema stops
  a reader averaging an average
* Bad, because this slice cannot demonstrate the property the shared-bridge deviation (D-0001)
  rests on. With one entity there are no edges to inherit along, so the fan-trap argument is
  carried on assertion until slice 2
* Bad, because the generator now depends on three specific behaviours of a third-party engine on a
  platform that engine does not advertise supporting. Each is pinned by a check, but a vendor
  change could invalidate any of them

### Confirmation

A machinery test asserts the column order, the calendar's padding, the event-date filter, the
key inheritance and the refusals — including that a **zero-edge walk is a valid walk**, so slice 2
does not meet that as a special case. A second asserts that every branch of the union aliases
every column of one list exactly once and that every measure is cast. The fan-out test runs the
generated SQL against an in-memory database with DAB's shapes faked into it, two parents and three
children, and fails if the parent total multiplies. A data check asserts `DESCRIBE
dar__uss._bridge` equals the plan on the real warehouse.

`adss dar generate --check` regenerates and fails on any diff, which is what keeps the committed
SQL from becoming a second truth.

This decision is the argument behind deviation **D-0001** in
[deviations.md](../deviations.md).

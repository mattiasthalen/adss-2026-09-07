---
status: accepted
date: 2026-09-08
decision-makers: [adss maintainers]
slice: 3
---

# A measure is owned by an event and named for an entity, so two events on one entity may not name the same measure

## Context and Problem Statement

Slice 3 is the first slice where one entity has two events: an order is both placed and shipped.
That splits two things which have been the same thing until now.

A measure's **column** and its **glossary token** are keyed on the entity:

```python
(event, measure, f"_measure__{event.entity_id.lower()}__{measure.id.lower()}")
found[f"{event.entity_id}.measures.{measure.id}"] = measure.definition
```

Its **ownership** is keyed on the event — `_branch` decides which stage carries a value and which
emits a typed null by identity on the event object. So the generator knows exactly which stage owns
a measure, and then names it after something else.

With one event per entity those keys coincide and nothing can go wrong. With two, declaring the
same measure id on both events of one entity is accepted without a word, and produces:

- **the same column twice** in the published contract, and
- **one definition silently replacing the other** in the glossary.

Reproduced on the neutral fixture. The column list came back with
`_measure__parent__happened_parents_count` at two positions, and the glossary held the *second*
event's definition under the first event's token.

The two halves fail very differently. DuckDB does not refuse two columns of one name — measured,
`CREATE TABLE t AS SELECT 1 AS a, 2 AS a` yields `a` and `a_1` — so the built table's columns would
not match `bridge_columns()` and the contract check would fail the build loudly. That half is safe.

**The glossary half is caught by nothing.** No check inspects `definitions()`. That dictionary is
what a question's `defines` entries are resolved against, and what the page renders as "What the
words mean". So a question could reference a measure, resolve it successfully, and be shown a
definition belonging to a different measure — on the page a reader accepts the slice on — while
every test and every check passes.

Nothing enforces the naming convention that would prevent it either. Conventions §2's three-part
pattern is a hard rule, and there is no test anywhere that checks a measure name's shape. The
uniqueness of these columns has rested entirely on a rule enforced by reading.

## Decision Drivers

* a definition that is silently replaced is worse than one that is missing: nothing looks wrong
* the failure must be loud where it is invisible, not only where DuckDB happens to complain
* a published column contract two consumers are already written against
* whatever is decided now is cheapest now, with two questions in existence

## Considered Options

* Refuse the collision when the declarations are read, and keep the entity in the column name
* Rename the column to `_measure__<event>__<measure>` and the token to `<ENTITY>.<EVENT>.measures.<M>`
* Do nothing, and rely on §2's naming pattern to keep ids distinct

## Decision Outcome

Chosen: **refuse the collision when the declarations are read.**

Two events on one entity may not declare the same measure id. The refusal names both events and
says what would be lost, because the loss is not obvious: a reader who has just been told the
column would be duplicated will think of the column, and the definition is the part nothing else
would catch.

**Why not rename to the event.** It is more correct in principle — the event is what actually owns
a measure, so the name should say so — and it is the cheapest it will ever be, with only two
questions to update. It is rejected on two counts. It changes a published contract that conventions
§1.3 states as a hard rule and ADR 0002 tabulates, in a slice that has no other reason to touch it.
And §2's descriptor slot already carries the event: `placed_orders_count`, `shipped_orders_count`.
Naming the column for the event too would put it in twice, so the more correct scheme reads worse
in every ordinary case in order to disambiguate one that is now refused outright.

**Why not do nothing.** §2's pattern makes a collision unlikely, not impossible, and "unlikely" is
the wrong guarantee for a failure whose signature is a page showing a plausible sentence about the
wrong number. Two events on one entity is exactly where the pattern's descriptor slot stops doing
the work — `placed` and `shipped` distinguish the count measures, and nothing forces a third
measure to carry a descriptor at all.

This follows the shape the repository already uses for the same class of problem: ADR 0006 refuses
two edges that would inherit into one key column, for the same reason and with the same argument
about what DuckDB silently does instead of raising. A generator that cannot emit a correct artefact
should say so rather than emit an ambiguous one.

## Consequences

* Good, because the glossary can no longer show one measure's definition under another's name,
  which was the only failure here that nothing would have reported
* Good, because it is a refusal in the same place and the same shape as the one for colliding
  edges, so the two read as one rule rather than two special cases
* Good, because it costs nothing today: no existing declaration collides, and no column moves
* Bad, because it forbids a legitimate-sounding declaration — the same quantity measured at two
  events, deliberately, under one name. That would have to be two measures with two definitions,
  which is more honest but more typing. If a slice ever wants it, the answer is to rename to the
  event, and this record is what it supersedes
* Bad, because the deeper mismatch stays: the generator still names by entity what it owns by
  event. This narrows the consequence to nothing rather than removing the cause

## Confirmation

`tests/test_uss.py` asserts that two events on one entity declaring one measure id are refused,
and that the same id on two *different* entities is still accepted — which is the case the
refusal must not catch, since `_measure__<entity>__` already distinguishes those.

A second test asserts that `definitions()` returns one entry per declared measure, so a future
change that reintroduces a silent overwrite fails on the count rather than on somebody reading a
page carefully. That is the assertion that would have caught this, and it did not exist.

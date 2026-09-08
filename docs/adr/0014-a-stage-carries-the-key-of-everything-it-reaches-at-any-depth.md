---
status: accepted
date: 2026-09-08
decision-makers: [adss maintainers]
slice: 5
---

# A stage carries the key of everything it reaches at any depth, and a target nothing reaches is refused

## Context and Problem Statement

[ADR 0002](0002-dar-is-one-generated-unified-star-schema.md) says: *"A stage carries the key of
every entity it reaches by walking many-to-one edges."* The `dar` skill says the same thing in the
artefact anybody reads first.

The generator does not do that. Every place it asks what a stage reaches, it asks
`model.edges_from(<the event's own entity>)` and stops — in `entity_ids`, in `bridge_sql`, in
`_stage_cte`, in `_branch`, and in the refusal that validates an inherited date. There is no
closure, no recursion, no fixed point. **There is no walk. There are five independent one-hop
lookups.**

**The consequence is already in the shipped warehouse, and it is silent.** `ORDER_LINE → ORDER`
and `ORDER → CUSTOMER` have both been declared since slice 4, so a two-hop chain exists today.
Measured on the built warehouse:

| stage | event | rows | `order_key` | `customer_key` | `order_line_key` |
|---|---|---|---|---|---|
| order | placed | 830 | 830 | 830 | 0 |
| order | shipped | 809 | 809 | 809 | 0 |
| order_line | ordered | 2155 | 2155 | **0** | 2155 |

`dar/uss/_bridge.sql` emits `cast(NULL AS VARCHAR) AS customer_key` on the line branch. So:

```sql
SELECT cu.based_in_country, sum(b._measure__order_line__revenue_order_lines_amount)
FROM dar__uss._bridge AS b
LEFT JOIN dar__uss.customer AS cu ON b.customer_key = cu.customer_key
WHERE b._event = 'ordered' GROUP BY 1;
-- one row: (NULL, 1265793.0395)
```

The total is exactly right. The dimension is gone. Every generated check passes, the flow rules
pass, and [ADR 0012](0012-the-bridge-protects-measures-and-not-the-attributes-beside-them.md)'s
aggregate refusal passes — it *is* a `_measure__` column. This is ADR 0012's own sentence
reappearing one layer along: *"it was already live at slice 3, undetected."*

Slice 5 asks for revenue per **product category**. `ORDER_LINE → PRODUCT → CATEGORY` is two hops,
so the bridge would carry `product_key` and no `category_key`, and `dar__uss.category` would not be
generated at all — because peripherals are generated from the same one-hop set. The question could
not be written against `dar__uss` however it was phrased.

Declaring the model anyway does not fail quietly, and it does not fail usefully either.
`relationship_checks` emits a `__resolves` check for **every** declared edge, so
`product_is_in_category__resolves` would reference `dar__uss.category`, which does not exist, and
`adss check` would die with `CatalogException` before printing a single finding — the exact
failure two comments in this codebase already say they exist to prevent.

## Decision Drivers

* the system does what its own records say it does, or the records are worth nothing
* a wrong dimension on a right total is the failure this architecture is least able to see
* a category is a business concept, not a property of a product
* the integration work belongs in the layer built for it, not in each question
* what cannot be walked is refused where it can be seen, rather than emitted as a null

## Considered Options

* **Make the walk transitive** — a stage carries the key of everything it reaches at any depth
* **Keep one hop, denormalise the category onto the product** — as a code, or via `$expand`
* **Keep one hop, let each question join peripheral to peripheral**
* **Refuse the model** — make the silence loud without answering the question
* **A direct `ORDER_LINE → CATEGORY` edge**

## Decision Outcome

Chosen: **the walk becomes transitive, and a declared relationship whose target no stage reaches
is refused by name.** The two compose: the first answers the question, the second is what would
have caught the hole in slice 4.

**Why transitive.** It is what ADR 0002 already promised, what the skill already claims, and what
`entity_ids`' own docstring already reasons about one level too shallow: *"An entity reached only
by inheritance still needs a peripheral, or the bridge carries a key that joins to nothing."* At
depth two the entity gets neither, which is that failure made worse. And the property the whole
bridge rests on survives the extension unchanged: a composition of many-to-one edges is still
many-to-one, so a longer walk still cannot fan a measure out. Each inherit CTE yields one row per
inheriting row, and chaining them is one row in, one row out, twice.

**Why not denormalise.** The source settles it before taste does: Northwind's `Product` carries
`CategoryId` and nothing else about the category, so getting the category's *name* onto the product
needs a join, and M1 and M5 each forbid that independently. What remains is either grouping the
category manager by a numeric code — not the term they asked for — or recording
`Products?$expand=Category`, which [ADR 0009](0009-a-stage-may-be-dated-by-a-date-it-inherits.md)
already refused for a date on B8: the name would have two homes, *"and would disagree silently,
because both copies come from the same load and would agree until the first time they did not."*
It also asserts that a category is a property of a product, which B1 and B6 both deny — B6 by
name: *"nothing exists here because one consumer wanted it."*

**Why not a join per question.** It is not possible today without a further change — a peripheral
carries its key, `_observed_at` and its own attributes, and no foreign key at all, so there is
nothing to join on. Making it possible means either putting inherited keys on peripherals, which
re-creates the surface ADR 0012 has just finished measuring, or generating a peripheral nothing
joins to. And it moves the model's shape into the consumer: every category question pays the cost
again and each payment is a place to get the path wrong. R1 says this layer's job is that the
integration work is *already done*.

### Keys reach; dates still do not

[ADR 0009](0009-a-stage-may-be-dated-by-a-date-it-inherits.md) closed off letting `date_attribute`
*"reach further than one declared edge because 'the walk goes there anyway'"*. That closure stands.

The asymmetry is deliberate and it is not arbitrary. A key is identity: carrying the identity of
everything a row is about is unambiguous, additive, and the same claim at any depth. A date is a
choice about *when the event happened*, an event has exactly one, and the further a modeller
reaches for it the less obviously it belongs to the event — so it stays a thing written down
rather than a thing inferred from connectivity. Slice 5's own date is one hop and does not test
this either way.

The refusal message must therefore say which of the two rules it is applying, rather than the bare
"no edge reaches X" it says today, or the next person to meet it will read it as a bug.

### Two paths to one entity are refused, not resolved

If two distinct paths reach the same entity, the bridge would carry one key column and two
candidate values. Picking either is choosing arbitrarily between two answers, which is the thing
[ADR 0006](0006-an-inherited-key-is-resolved-as-of-the-row-that-inherits-it.md) refused to do for
a tied pair. It is refused, by name, with both paths listed.

This leaves ADR 0006's deferred question — whether a key column is named for the edge rather than
the target — still deferred, and deliberately: *"a decision for the slice that first needs two."*
Slice 5 does not need two. `ORDER_LINE → ORDER → CUSTOMER` and `ORDER_LINE → PRODUCT → CATEGORY`
have four distinct targets. Deferring it again is a decision here rather than an oversight.

A cycle is refused for the same reason, and because a closure over one would not terminate.

### What this corrects in earlier records

Per [the ADR rules](README.md), a record is corrected where it is found wrong, never edited in
place. Four claims are wrong and all four are this decision's to carry:

* **ADR 0002**: *"A stage carries the key of every entity it reaches by walking many-to-one
  edges."* False since slice 4, on the shipped warehouse, as measured above. True as of this
  record.
* **ADR 0006**: *"the walk is the same shape at zero edges and one, so slice 5's two-hop chain
  extends it rather than special-cases it."* There was no walk to extend. The shape at depth two
  was not a special case; it was absent, and absent without a refusal.
* **ADR 0009**: *"slice 5's two-hop chain inherits this unchanged — a date reached along two edges
  is the same rule applied twice, and needs no new decision."* Measured false: a two-hop
  `date_attribute` is refused outright by the code that same record describes. The record
  contradicts itself — its own "What this does not become" says one edge only — and the code
  implements the stricter half. That half is kept, above.
* **ADR 0003**: *"`adss check` runs every one it finds, so a contract added in a later slice is
  checked without anything else changing."* True of contracts. The parallel is false for
  relationships: an edge whose target no stage reaches generates a check that cannot run and takes
  every other finding down with it. The refusal above removes the cause rather than guarding the
  symptom.

## Consequences

* Good, because the bridge does what three records and a skill already said it does
* Good, because a wrong dimension on a right total — the failure this architecture is least able
  to see — stops being reachable by declaring a model and running the build
* Good, because it generalises: the third hop needs no further decision, and the refusal covers
  every shape the closure cannot resolve rather than the one slice 5 happens to hit
* Bad, because it **changes values in a column consumers already read**. `customer_key` on 2,155
  `order_line` rows goes from null to populated. No question here reads it — q02 is the only one
  that touches `customer_key` and it filters to `_event = 'placed'` — but B7's "change is additive"
  is about structures, and this is not a structural change. Saying it is covered would be wrong
* Bad, because the generated SQL grows. ADR 0006 already observed that *"at three or four edges it
  stops being readable in one screen"*, and the `ordered` stage alone gains inherit CTEs for
  ORDER, CUSTOMER, PRODUCT and CATEGORY. Layout is the linter's and regeneration is one command,
  so the cost is reading, not maintenance
* Bad, because the refusals are new places the build can stop. That is the trade this system makes
  everywhere: a refusal somebody has to read, against a null nobody does

## Confirmation

Written after the code, against the code — no claim in this section precedes the check it names.

`tests/` gains a neutral fixture with a three-level chain, which it has never had: every existing
fixture is depth one. It asserts that a stage carries the key of an entity two edges away, that
the peripheral for that entity is generated, that the key resolves to a row in it, and — the
falsifiable half — that a measure is not multiplied by the length of the walk, which is
`tests/test_fan_out.py`'s property re-run at depth two rather than assumed to survive.

The refusals are asserted against models built to trip them: a target no stage reaches, two paths
to one entity, and a cycle. Each is refused by name, with the paths listed.

The mutation that must fail before this section stands: restoring `edges_from` in place of the
closure emits valid SQL and a bridge whose deeper keys are typed nulls — the shape measured above.
It is run, and it fails the suite, or this paragraph is deleted rather than believed.

What is **not** confirmed: that the as-of instant is right at depth two. Each hop is resolved as of
the observation of the row that inherits it, and [ADR 0013](0013-an-ingest-is-one-observation-so-every-contract-it-lands-shares-one-clock.md)
gives every contract in one ingest the same clock, so today the two readings of "as of" coincide
and the choice looks free. It is not — that is ADR 0006's own warning about its own choice, one
hop deeper — and ADR 0013's Consequences already name the case that separates them: two contracts
landed by two separate commands carry two times, correctly. Nothing here distinguishes them yet.

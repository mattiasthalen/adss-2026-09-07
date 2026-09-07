---
status: accepted
date: 2026-09-07
decision-makers: [adss maintainers]
slice: 2
---

# An inherited key is resolved from the raw pairs, as of the observation time of the row that inherits it

## Context and Problem Statement

Slice 1 built a bridge with one entity and no relationships. ADR 0002 asserted that one shared
bridge is safe because keys inherit along many-to-one edges while measures do not, and said in as
many words that the walk had zero edges and the property was asserted rather than exercised. This
slice is the first with an edge: an order is placed by a customer, and the question groups the
freight of an order by the *customer's* country, which exists nowhere on the order.

So the generator has to get `customer_key` onto an order row. The engine offers four places to get
it from, they do not agree with each other, and the names do not say which is which. A probe built
a two-entity model with one relationship, changed a foreign key, and read every object the engine
produced. It overturned two things ADR 0002 states as fact.

**The relationship view is a *current* view, not a historical one.** ADR 0002 says reading it would
lose a row whose foreign key changed. That is not what happens. The macro behind
`dab.view_<SRC>_<NAME>_<TGT>` is:

```sql
rank() OVER (PARTITION BY <SRC>_key, type_key ORDER BY eff_tmstp DESC, ver_tmstp DESC) AS nbr
... WHERE nbr = 1 AND row_st = 'Y'
```

Partitioned by the child, so the child never drops out — it is re-pointed. After the probe moved
CH1 from P1 to P2, the pair table held both rows with `row_st = 'Y'` and the view held `CH1|P2`
alone. Nothing is lost; the *old* pair is what is lost, for every row of that child, retroactively.
The reason to read the raw pairs is therefore history, not disappearance, and ADR 0002 got the
right answer from the wrong mechanism.

**`view_<entity>_with_rel` does carry relationship keys — on the target side, and it fans out.**
ADR 0002 says its column list is byte-identical to `view_<entity>`. That is true only for the
relationship's *source* entity. Once an entity is a relationship *target*, its `_with_rel` view
becomes a double left join through the pair macro and gains the source entity's key **and every one
of its attributes**, one row per child. The probe measured the consequence:
`sum(CHILD_AMOUNT)` over `view_PARENT_with_rel` returned 200.75 against a true 150.75. That is a
live fan trap in a view whose name invites exactly the join that springs it.

**`rank()` is not `row_number()`, so a tie returns both rows.** The probe's CH5 had two parent codes
in one load, so two pair rows shared an `eff_tmstp`, and the relationship view returned CH5 twice.
A child appearing twice in the bridge multiplies its measures — the precise failure the bridge
exists to prevent, arriving from the engine's own view rather than from anything we wrote.

## Decision Drivers

* a measure summed over the bridge is additive at every grain, whatever the model's shape
* a bridge row is true as of one instant, and every column on it is true as of that same instant
* the generator reads objects whose behaviour has been observed, never ones whose names suggest it
* a case the design cannot handle fails the build loudly rather than answering a question wrongly
* the walk works for zero edges, one edge and, later, a chain — without a special case per depth

## Considered Options

* `dab.view_<SRC>_<NAME>_<TGT>` — the engine's ranked relationship view
* `dab.v_<SRC>_<NAME>_<TGT>` — the raw pairs plus a relationship name, ranked here
* `dab.<SRC>_<TGT>_x` — the pair table directly, with `dab__meta` for the type key
* `dab.view_<TGT>_with_rel` — the view named as though it were for this

## Decision Outcome

Chosen option: **`dab.v_<SRC>_<NAME>_<TGT>`, ranked in the generated SQL as of the child row's own
`_observed_at`, one parent per child, with the tie refused by a data check.**

`v_<SRC>_<NAME>_<TGT>` is the raw pair table joined to the engine's metadata to add a `rel_name`
column, with no ranking and no `row_st` filter. That is what makes it the right source: the pairs
arrive unfiltered, and the as-of rule is ours and visible in the generated SQL rather than the
vendor's and hidden in a macro. It also solves a naming problem the pair table has on its own — the
pair table is named `<SRC>_<TGT>_x` from the *entity pair*, not from the relationship, so two
relationships between the same two entities land in one table separated only by a `type_key` whose
meaning lives in `dab__meta.atom_contx_desc`. Filtering on `rel_name` says what is meant; filtering
on `type_key = 1` says nothing and breaks when a second edge is declared.

**As of `_observed_at`, not as of now.** The stage picks a version of the child; the inherited key
is the one in force when that version was observed. Today the stage always picks the child's latest
version, so this coincides with the current parent and the choice looks free. It is not: it is what
keeps the rule stated at the level of a bridge row rather than at the level of a table, so it
survives a stage that keeps more than the latest version, which is what a snapshot event and a
`_is_current = FALSE` row will both need.

**Exactly one parent per child, and a tie is a build failure.** The generated SQL uses
`row_number()` over `eff_tmstp DESC, ver_tmstp DESC` and then the parent key itself, so it is
deterministic and can never emit two rows for one child. Determinism alone would be a silent wrong
answer, so a generated check counts children with more than one parent at the ranking instant and
fails the build when it is not zero. The two together mean the bad case is loud, and that if the
check is ever ignored the damage is a mis-attributed row rather than a doubled measure. Doubling is
worse: it is invisible in both of a question's acceptance queries if both are written the same way.

`view_<TGT>_with_rel` is refused outright and now for a measured reason rather than an assumed one.
The engine's ranked view is refused because its as-of rule is not ours to state and its `rank()`
can fan out. The pair table is refused because it cannot name the relationship it is carrying.

**A child with no parent keeps its row and inherits a null key.** The probe's CH6 has no pair row at
all, so the join is a left join. An order the source attributes to nobody is still an order that
was placed, and dropping it would change a count that ADR 0002 already published. Null is not a
member: it groups as itself and the generator invents nothing for it, per conventions §1.3.

### Corrections to ADR 0002

ADR 0002 is not superseded — its decision stands and this record extends it. Two of its factual
claims are wrong and are corrected here rather than in place, because what a record was when it was
made is the thing that makes it worth keeping:

1. "A changed foreign key keeps its row, which reading the relationship view would not have done."
   The relationship view does keep the row. It re-points every one of that child's rows at the new
   parent and erases the old pair, which is a different defect and a worse one, because it is
   invisible.
2. "`view_<entity>_with_rel` carries no relationship key columns at all; its column list is
   byte-identical to `view_<entity>`." True on the source side only. On the target side it carries
   the source entity's key and attributes, fanned out.

The check ADR 0002 installed for the second claim asserted it of *every* entity, so it fails the
moment CUSTOMER becomes a relationship target. That is the check working: it was pinning observed
behaviour and the behaviour was mis-observed. It is replaced by one that asserts the real rule —
the source side is unchanged, the target side gains exactly the source entity's columns — which is
a stronger statement than the one it replaces and would have caught this in slice 1 had it been
possible to write then.

## Consequences

* Good, because the as-of rule is written in the generated SQL, so a reader of `dar/uss/_bridge.sql`
  can see when the inherited key was true without reading a vendor macro
* Good, because the fan-out the engine's own views expose cannot reach the bridge: the generator
  emits `row_number()`, and the case that would have needed it fails the build first
* Good, because filtering on `rel_name` makes a second edge between the same two entities a new
  structure rather than a silent collision
* Good, because the walk is the same shape at zero edges and one, so slice 5's two-hop chain extends
  it rather than special-cases it
* Bad, because the generated bridge SQL grows a ranked CTE per edge, and at three or four edges it
  stops being readable in one screen. It is generated, linted and drift-checked, so this costs
  legibility rather than correctness
* Bad, because `v_<SRC>_<NAME>_<TGT>` is an engine-internal object with no compatibility promise,
  like every other object here. The pinning checks are what turn a vendor change into a failure
  instead of an empty column

## Confirmation

`tests/test_uss.py` asserts the generated bridge left-joins the pairs rather than inner-joining
them, that it ranks by `row_number` and not `rank`, that the ranking is as of the child's
`_observed_at`, and that a non-owning branch still emits a typed null for a key it does not own —
this last one because a union takes its column names from its first branch, so the order of the key
columns is the invariant and counting them would not catch a transposition.

A generated data check counts children with more than one parent at the ranking instant and must
return zero. Another counts bridge rows whose inherited key resolves to no row in the target
peripheral, which is the shape a mis-spelled M6 target expression takes: the engine reports nothing
at deploy or at execute, and the column is simply null everywhere.

The engine-behaviour checks are widened rather than removed: `_focal` and `_idfr` are still empty,
`view_<E>_with_rel` is unchanged on a relationship's source side and gains exactly the source
entity's columns on its target side.

What this slice still does not prove is the fan-out property itself. Both entities here are at the
same grain — one order has one customer — so no measure can multiply across the edge no matter how
the join is written. The first measure at a finer grain arrives in slice 4, and that is where the
test that a parent's measure is not multiplied by its children becomes possible. Saying so is the
point: ADR 0002 asserted this property in slice 1 and it is still asserted now.

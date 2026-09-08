---
status: accepted
date: 2026-09-08
decision-makers: [adss maintainers]
slice: 4
---

# A composite source key becomes one key expression, and a check compares it against the parts it was made from

## Context and Problem Statement

The source's order lines are keyed on `(OrderId, ProductId)`. Conventions M2 has permitted
"a `concat` of casts with a separator" since slice 1 and warned that a concat without one makes
`'A1' + '23'` and `'A12' + '3'` the same key — a clause that has been **review-only for three
slices** because nothing had a composite key. This is the slice that has one.

A probe built the whole slice four times over and measured what the rule has been asserting.

**The collision this data can produce: none.** Over all 2155 real order lines, a separator-less
concat yields 2155 distinct keys — because every `OrderId` is exactly five digits, so the split
point is never ambiguous. A separator-less key would pass every gate, every data check and both
acceptance queries. The warning is right in general and unfalsifiable here, which is the most
dangerous shape a rule can have: it looks satisfied whatever you do.

**A separator that can occur in a value does not fix it.** Measured, with `'-'` between
`('A-1','23')` and `('A','1-23')`: five distinct keys from six pairs. With a separator outside
the value domain: six from six. So "the parts are integers, so `-` is fine" is exactly the
reasoning that is *fine today and wrong at the first string key* — and the key cannot be changed
later, so "wrong later" means wrong with the old key already immortal.

**`concat` ignores nulls; `||` does not.** Measured: `concat('1213','-',NULL)` is `'1213-'`, not
null. `concat_ws` drops the separator too. `'1213' || '-' || NULL` is null. The source's metadata
does **not** mark `OrderDetail.OrderId` or `ProductId` `Nullable="false"` — unlike `Order.OrderId`,
which it does — so a null half silently produces a truncated key that collides with a real one.

**M2's stated reason is wrong, and the truth is worse in a different way.** M2 says two entries
are read as alternate identifiers and "that mode cannot be undone once loaded". Measured: two
entries are **refused at deploy**, loudly, unless `allow_multiple_identifiers` is set on the
mapping group. With it set, the entity key becomes a **minted UUID** — not derived from anything
in DAS — so the layer stops being rebuildable from the source, which is a blueprint promise. The
repository already catches that, but under the `_focal`/`_idfr` vendor pins, which name the
wrong cause.

**And the key expression genuinely cannot be changed after loading.** Changing only `'-'` to
`'/'` and re-executing doubled everything: 2155 keys became 4310, and revenue over the bridge
went from 1,265,793.0395 to 2,531,586.079. `adss check` caught it — as
`ORDER_LINE_desc holds no duplicate versions … a growing gap is FULL ingestion duplicating
silently`, which names a cause that has nothing to do with what happened and would cost a reader
an afternoon.

## Decision Drivers

* a key that cannot collide, demonstrated rather than argued from the shape of the data
* a rule that still holds when a later composite key has a string part
* failing closed on a null part, rather than producing a shorter key that collides
* the next person is told the truth about what two entries actually do

## Considered Options

* `concat` of casts with a separator — what M2's text suggests
* `||` of casts with a separator, plus a check comparing the composed key against its parts
* Two `primary_keys` entries with `allow_multiple_identifiers`
* A surrogate minted in DAS

## Decision Outcome

Chosen: **`||` of casts with a separator, and a generated check that the composed key has exactly
as many distinct values as the source's own composite key.**

```yaml
primary_keys: ["cast(order_id AS VARCHAR) || '-' || cast(product_id AS VARCHAR)"]
```

The check is the part that matters, and it is what turns three slices of asserted reasoning into
something falsifiable. Whatever separator is chosen and whatever the parts turn out to be, the
composed key must not collapse two source rows into one — and that is directly countable against
the contract's own `primary_keys`, which DAS already records as a composite. A separator argument
is a prediction; this is a measurement, and it fires on the data that actually landed.

`||` rather than `concat`, because `concat` is null-blind: it turns a missing half into a shorter
key that can collide with a real one, silently. `||` yields null, and a null key fails at the
engine rather than in a report six months later. The dab skill recommends `concat`; that
recommendation is wrong for a composite key and is corrected.

**Why not two entries.** Not because M2's stated reason is right — it is not — but because what
actually happens is worse: the entity key becomes a minted UUID with nothing in DAS to recompute
it from, so DAB stops being rebuildable from the source. M2's text is corrected to say what the
engine really does.

**Why not a surrogate in DAS.** It would be minted there instead, with the same rebuildability
problem one layer earlier, and DAS's job is to record what a source sent rather than to invent an
identifier it did not.

### On the separator, honestly

`'-'` is chosen for readability — `10248-11` is a key a person can recognise in a screenshot —
and it is safe here only because both parts are non-negative integers. That is not a general
guarantee and this record does not pretend it is. **A composite key with a part that is not a
non-negative integer is a new decision**, not an application of this one: the separator has to be
chosen against that part's value domain, and the check below is what would catch a wrong choice.

## Consequences

* Good, because the property M2 has asserted for three slices is now measured on every build,
  against the source's own key rather than against an argument about digits
* Good, because a null part fails rather than producing a key that is quietly one character short
* Good, because the check is generated per contract, so a later composite key is checked without
  anything else changing
* Bad, because the key is not a number the business uses. `10248-11` is this system's identifier
  for a line, and no order form has ever carried it. If a question ever needs "which product", the
  answer is a `PRODUCT` peripheral reached along an edge — slice 5's content — and **never**
  splitting this string back apart, which would be a reach into a key's internals from a layer
  that must not know it has any
* Bad, because re-keying an entity after it is loaded doubles its history, and the check that
  notices names the wrong cause. That is recorded here and left alone: the right repair is to drop
  the schemas and rebuild, which the build already supports, and a check that explained it
  properly would have to know what a re-key looks like

## Confirmation

`tests/test_mapping_rules.py` asserts that a composed key expression conforms to M2 — one entry,
producing a VARCHAR — and that two entries are still refused before the engine sees them.

A generated data check, one per contract with a composite key, counts the distinct composed keys
in `das__staged.<table>__current` against the distinct source key tuples and fails on any
difference. It is written against the shape that would break it — a separator-less concat over
parts whose lengths vary — and that case is constructed in `tests/` so the check is known to be
capable of failing, rather than known to pass.

What is **not** confirmed, and is recorded rather than claimed: nothing detects that a key
expression has *changed* between builds. The signature is a doubling of the description table,
which an existing check reports under a name that describes a different defect. Making that
check name the right cause would mean teaching it what a re-key looks like, and the repair — drop
and rebuild — is the same either way.

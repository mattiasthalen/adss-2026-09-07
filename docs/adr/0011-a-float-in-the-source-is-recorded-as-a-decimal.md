---
status: accepted
date: 2026-09-08
decision-makers: [adss maintainers]
slice: 4
---

# A float in the source is recorded as a decimal, because the choice is about where a bad value fails

## Context and Problem Statement

`OrderDetail.Discount` is `Edm.Single` — a 32-bit float, and the first one this system has met.
Revenue is quantity times unit price less that discount, so it feeds a measure.

The contract vocabulary has `DOUBLE` and `DECIMAL` and no `REAL`. So **neither option is a
transcription of what the source declares**; both are a choice, and §1.1's usual instruction —
record what the source sent — does not settle it.

ADR 0007 established that a question's two answers are compared row by row **by value**, and that
a float makes that comparison order-dependent because summing doubles is not associative. Slice 4
is the first slice that could actually trip it, so the question is whether it does.

A probe built the slice twice, once with each type, and measured.

**On this data, the two builds are indistinguishable.** Every DAR value byte-identical; zero of
2155 revenue rows differ; both acceptance queries agree either way. Revenue uses at most four
decimal places and `DECIMAL(28,8)` holds it with four to spare.

**Not indistinguishable in general.** At a larger magnitude the same expression diverges:
`97 * 1234567.8901 * (1 - 0.06)` is `112567900.21931798` through a double and
`112567900.21931800` through a decimal.

**And the order-dependence ADR 0007 predicted is live on this slice's own measure.** Summing the
2155 real revenue values as doubles, in three different orders:

```
ORDER BY order_id, product_id            -> 1265793.0395000004
ORDER BY product_id DESC, order_id DESC  -> 1265793.0394999993
ORDER BY unit_price, quantity            -> 1265793.0395000007
```

Three orders, three answers. ADR 0007 wrote that down as a prediction; this is the witness.

**Where the float actually stops, and who stops it.** At `dab.<E>_desc.val_num`, a
`DECIMAL(28,8)` column the engine coerces into silently. Every presentation object gives
`DECIMAL(28,8)` whatever DAS declared. **Nobody in this repository wrote that cast and nothing
names it** — which means the answer side of every question is protected by a vendor's choice
rather than by ours.

**The exactness check added in slice 3 is silent here**, and it is worth being exact about why.
It inspects returned values, and both sides launder the float before it sees them: the answer
side is `DECIMAL(28,8)` because DAB widens every `NUMBER`, and every control query already wraps
its sum in a cast. Measured: with a `DOUBLE` contract the check reports nothing — unless the
question's author omits that cast, in which case it fires. So it defends against a float in an
*answer*, not against a float in a *source*, and slice 4 was expected to trip it and does not.

## Decision Drivers

* a bad value fails where somebody can see it, rather than propagating
* the exactness the acceptance check depends on does not rest on a vendor's silent coercion
* §1.1 keeps DAS a recording, so a type is chosen for how it fails, not for what it computes
* the choice survives a source whose values are larger than this one's

## Considered Options

* `DOUBLE` — closest to what `Edm.Single` is
* `DECIMAL(18, 4)` — what the values actually are

## Decision Outcome

Chosen: **`DECIMAL`**, and the reason is not exactness.

On this data exactness does not distinguish them, and arguing from the general case would be
arguing from a magnitude this source cannot produce. The decisive difference is **where a bad
value fails**:

| in the payload | `DECIMAL` contract | `DOUBLE` contract |
|---|---|---|
| `NaN` | `Conversion Error` at the cast, loudly, at `das unpack` | becomes `NaN`, propagates into a measure |
| `Infinity` | same | becomes `Inf`, and a sum of it is `Inf` |

A `NaN` discount through a `DOUBLE` contract produces a `NaN` revenue on one line, and a `NaN`
anywhere in a sum makes the whole month `NaN` — in *both* answers alike, because both derive from
the same landed value. So the acceptance check agrees, the gate is green, and a month's revenue is
not a number. `DECIMAL` refuses the record at the door, which is where a contract is supposed to
refuse things.

That also stops the answer side depending on a coercion nobody wrote down. With `DECIMAL` in the
contract the value is exact from the moment it lands, and the engine's widening to
`DECIMAL(28,8)` is a widening rather than a rescue.

### What this does not decide

**Rounding is not decided here, and money is not rounded anywhere in this system.** Revenue
carries every place the source's arithmetic produces, and the page formats for display without
storing what it formatted. If a business ever needs revenue to two places, that is a *definition*
— it belongs in `dab/model.yaml` with a sentence saying which way it rounds and why, and a check
that verifies it. Rounding silently in a mapping would be exactly the "value somebody chose"
ADR 0007 puts on the forbidden side of M5.

## Consequences

* Good, because a value the source should never have sent fails at the contract, once, rather
  than becoming a `NaN` that both acceptance queries agree on
* Good, because the exactness the acceptance check rests on is now ours from the landing zone
  onward, not a vendor's silent coercion two layers later
* Good, because it costs nothing measurable: two full builds, byte-identical DAR
* Bad, because `DECIMAL(18, 4)` is **not** what the source declares, and §1.1 says DAS records
  what the source sent. This is a knowing departure in the one direction §1.1 does not cover:
  the vocabulary has no `REAL`, so recording it faithfully is not among the options
* Bad, because a source value with more than four decimal places would now be refused rather than
  approximated. That is the right failure and it is still a failure somebody has to handle

## Confirmation

`tests/test_contract.py` asserts that a `DECIMAL` column carries its precision and scale into the
generated cast, and `tests/test_das_sql.py` that the cast is emitted rather than a bare read.

The order-dependence witness is recorded in ADR 0007 and re-measured here on real values; nothing
in the built system can now produce it, because no measure is a float at any layer — which is what
the "both answers hold only exact values" check asserts on every build, per question.

What is **not** confirmed: no test constructs a `NaN` payload and watches the contract refuse it.
The behaviour was measured by hand against a scratch build and is written down here rather than
pinned, because fabricating a payload the recorder never produced would be testing DuckDB's cast
rather than this system's use of it. The property that matters — that a float never reaches an
answer — is pinned, per question, on every build.

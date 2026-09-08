# Architectural blueprint

This is the overarching document. It states what the system must achieve and the absolute
principles that support it. It names no technology, no tool, no modelling technique and no
process — those live in [conventions.md](conventions.md) and in [adr/](adr/README.md), and each
must justify itself against what is written here.

That separation is the point. Every tool this system currently uses must be replaceable without
invalidating a single line below.

## The vision

An analytical data storage system is built for requirements that do not exist yet, and it is
changed from the inside by its own use: every question it answers expands what its users want to
ask next. It is therefore judged over a life cycle measured in decades, not over the delivery of
any one data product.

Four qualities, in no priority order, because a design that sacrifices one for another is a
design that has failed:

| Quality | What it means here |
|---|---|
| **Maintainable** | A change costs about the same in year ten as in year one. |
| **Scalable** | Adding a source or a consumer strengthens the system rather than making the next addition harder. |
| **Adaptable** | A source replacement, a new entity or a new relationship is absorbed without rewriting what already works. |
| **Good time to market** | Not the fastest possible way. Always within acceptable timing. |

Speed is deliberately last-named and deliberately qualified. A system that answers today's
question fastest and next year's question not at all has optimised the wrong variable.

## The three layers

The layers are named for their **purpose**, never for their position or their quality grade.
They are not bronze, silver and gold; they are not staging, core and marts. Ask three people what
belongs in silver and you get four answers — and these names are also the principles, so a name
that does not carry a principle is a name that cannot be enforced.

| Layer | Data according to… | What it is |
|---|---|---|
| **DAS** | the **System** | what the source sent us, as it sent it |
| **DAB** | the **Business** | what the business means by it, integrated and source-agnostic |
| **DAR** | the **Requirements** | what a particular consumer needs, shaped for them |

## Flow

Flow is one-directional and has exactly three rules. They are absolutes.

| # | Rule | Why it matters |
|---|---|---|
| F1 | **Analytical usage reads only DAR.** | Consumption against DAS or DAB creates dependencies on structures whose whole purpose is to be free to change. The dependency is invisible until something breaks. |
| F2 | **DAR reads only DAB.** | A data product that reaches past the business layer to a source has bypassed the integration that makes numbers agree, and reintroduces the cascade the architecture exists to break. |
| F3 | **DAB reads only DAS.** | A source connection wired into the business layer means the source dependency was moved, not broken. |

Each movement between layers does exactly **one** job: ingest, integrate, specialise. Code that
ingests and integrates, or integrates and shapes for a report, has collapsed two layers into one
and is not permitted regardless of how convenient it is.

## Per-layer principles

### DAS — data according to the system

| # | Principle | Why it matters |
|---|---|---|
| S1 | **Capture and persist only.** No business logic, no interpretation, no enrichment. | Interpretation here buries a decision in the one layer that is supposed to make none, and disguises the next source change as a business change. |
| S2 | **Non-volatile.** Nothing is updated. Nothing is deleted. Every load is retained. | DAB and DAR must be rebuildable from DAS at any time without going back to the source. That is what makes changing the layers above it safe. |
| S3 | **Forgiving ingestion, strict unpacking.** Accept whatever arrives; enforce structure at the boundary out. | Committing to a schema at ingest turns every upstream change into lost data. Enforcing nothing on the way out turns every upstream change into a silent one. |
| S4 | **Every data point records where it came from and when.** | Without per-row provenance, an answer that looks wrong cannot be traced, and the only remaining move is to distrust the whole system. |
| S5 | **The source keeps its own words.** | A field renamed to a business term is an interpretation, and S1 forbids interpretations here. |

### DAB — data according to the business

| # | Principle | Why it matters |
|---|---|---|
| B1 | **Subject oriented.** Organised around business concepts, never around source systems. | The concepts outlive the systems that happen to record them. |
| B2 | **Integrated.** Semantically and structurally source-agnostic. | Adding a second source for a concept must not add a parallel structure, and removing one must not change any structure at all. This is the property that breaks the dependency. |
| B3 | **Time-variant.** Historized: every version retained, none overwritten. | An answer served last quarter must still be reproducible this quarter, or the system cannot be audited. |
| B4 | **Non-volatile.** Never updated, never deleted. | Same reason as B3, stated as a physical constraint rather than an intention. |
| B5 | **Atomic.** The atomic data point is the base of every semantic meaning. No aggregation, no bucketing, no pre-rollup. | An aggregate here is a requirement leaking down a layer, and it is the reason teams start demanding raw data. |
| B6 | **Reusable.** Nothing exists here because one consumer wanted it. | A construct that only makes sense given one requirement belongs in DAR. |
| B7 | **Change is additive.** A new attribute, entity or relationship is a new structure, never a modification of an existing one. | A modification has a regression surface. An addition does not. Repeated over the thousands of changes a platform absorbs, that difference is the whole ball game. |
| B8 | **Meaning is defined exactly once, here.** | Definitions that exist in two places drift, and the drift surfaces as two reports that disagree. |

### DAR — data according to the requirements

| # | Principle | Why it matters |
|---|---|---|
| R1 | **Requirement oriented.** Shaped for a specific consumer, optimised for them. | The integration work is already done; this layer's only job is to be usable. |
| R2 | **No cross-dependency.** A data product owns its structures and does not consume another product's. Duplication between products is accepted deliberately. | Each product has its own rate of change. Sharing structure couples those rates and reintroduces the dependency problem at the consumption layer. |
| R3 | **Reuse the definition, never the instance.** | Consistency comes from a shared *meaning* in DAB, not from a shared *table* here. The conformed dimension buys agreement by sharing structure and pays in coupling; with a real integration layer beneath, that price is unnecessary. |
| R4 | **Volatile and generated.** Nothing here is hand-written or hand-edited. | Anything derived from DAB can be thrown away and rebuilt. An edit to generated output is lost on the next generation, and until then the code and the model quietly disagree. |
| R5 | **What was delivered, to whom, and when is recorded.** | An answer someone acted on must be reconstructable, including the definitions that produced it. |

## What structure cannot do

Generation guarantees **consistency**, not **correctness**. A poorly chosen model compiles just
as reliably as a good one, and a system that enforces coherent structure over incoherent
definitions produces coherent-looking incoherence — which is more dangerous than visible mess,
because it is trusted.

Deciding what an entity is, when two records refer to the same instance, and whether two
attributes carry the same meaning remains human judgement. The effort saved on mechanism is meant
to be redirected to meaning, not removed.

## No exceptions

This document contains no exceptions and no pre-authorised bypass. That is deliberate: if a
principle is not stated as an absolute, with its reason recorded, there is nothing to break, and
a deviation becomes indistinguishable from an ordinary decision.

Reality still wins sometimes. When it does, the answer is not to weaken the principle but to
**cost the deviation**: which principle breaks, why the conforming option was unworkable here,
what it costs, and the observable condition under which it is removed. That record lives in
[deviations.md](deviations.md), and every deviation has an ADR behind it.

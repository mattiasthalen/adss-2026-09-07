# Architecture decision records

One file per decision, numbered, in [MADR](https://adr.github.io/madr/) format. A record is
**superseded by a new file, never edited**, because the value of a decision record is the record
of what was true when it was made. A claim that turns out to be wrong is corrected in the record
that found it wrong, named and quoted, rather than quietly rewritten where it stands — ADR 0006
corrects two of ADR 0002's.

**The Confirmation section is the one exception**, because it is not a record of anything: it is a
claim about which checks exist *now*, and a stale one is a lie about the present rather than an
honest account of the past. It is edited to match the checks, and only ever to match them. Twice
already it had drifted the other way — describing a check somebody meant to write.

An ADR lands **before** the code it decides. A decision record written afterwards records what
was built, not what was decided.

| # | Decision | Slice |
|---|---|---|
| [0000](0000-use-madr.md) | Decisions are recorded as MADR files in this directory | 0 |
| [0001](0001-the-machinery-has-its-own-typed-domain.md) | The machinery is modelled in its own typed vocabulary, and no business word appears under `src/` | 1 |
| [0002](0002-dar-is-one-generated-unified-star-schema.md) | DAR is one generated Unified Star Schema: an event bridge, peripherals, one calendar | 1 |
| [0003](0003-a-das-contract-is-one-artefact.md) | A DAS contract is documentation, schema and transformation in one artefact | 1 |
| [0004](0004-daana-cli-is-the-dab-engine.md) | daana-cli is the DAB engine, vendored and checksum-pinned | 1 |
| [0005](0005-a-question-is-the-unit-of-delivery.md) | A business question is the unit of delivery, with two queries that must agree | 1 |
| [0006](0006-an-inherited-key-is-resolved-as-of-the-row-that-inherits-it.md) | An inherited key is resolved from the raw pairs, as of the row that inherits it | 2 |
| [0007](0007-a-derived-value-is-modelled-where-two-vocabularies-are-bound.md) | A value derived from one row is modelled in DAB and computed in the mapping | 3 |
| [0008](0008-a-measure-is-owned-by-an-event-and-named-for-an-entity.md) | A measure is owned by an event and named for an entity, so two events on one entity may not share a measure id | 3 |
| [0009](0009-a-stage-may-be-dated-by-a-date-it-inherits.md) | A stage may be dated by a date it inherits along the walk | 4 |
| [0010](0010-a-composite-source-key-becomes-one-key-and-is-checked-against-its-parts.md) | A composite source key becomes one key expression, checked against the parts it was made from | 4 |
| [0011](0011-a-float-in-the-source-is-recorded-as-a-decimal.md) | A float in the source is recorded as a decimal, chosen for where a bad value fails | 4 |
| [0012](0012-the-bridge-protects-measures-and-not-the-attributes-beside-them.md) | The bridge protects a measure and not the attribute beside it, so a question may not aggregate a peripheral's number | 4 |
| [0013](0013-an-ingest-is-one-observation-so-every-contract-it-lands-shares-one-clock.md) | An ingest is one observation, so every contract it lands shares one clock | 4 |
| [0014](0014-a-stage-carries-the-key-of-everything-it-reaches-at-any-depth.md) | A stage carries the key of everything it reaches at any depth, and a target nothing reaches is refused | 5 |
| [0015](0015-an-edge-first-seen-later-is-not-evidence-that-it-was-different-before.md) | An edge first seen after the row that inherits it resolves from the earliest observation, not to nothing | 5 |

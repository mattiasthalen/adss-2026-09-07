# Architecture decision records

One file per decision, numbered, in [MADR](https://adr.github.io/madr/) format. A record is
**superseded by a new file, never edited**, because the value of a decision record is the record
of what was true when it was made.

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

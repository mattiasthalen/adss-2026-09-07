---
name: dab
description: Work on the DAB layer — dab/model.yaml, the mappings, and the modelling engine. Use when adding an entity, attribute or relationship, editing anything under dab/, running install/deploy/execute, or debugging engine errors, history that looks wrong, or rows that multiply.
---

# DAB — data according to the business

The layer that breaks the dependency between source and consumption. It is also **the only
place the data is explained**: every definition lives here and everything else references it.

## The shape

```
dab/model.yaml           entities, attributes, relationships -- and their definitions
dab/uss.yaml             what the generated layer needs: events, measures (see the dar skill)
dab/mappings/*.yaml      one per entity: how it is loaded from das__staged
dab/workflow.yaml        the model plus its mappings
dab/connections.yaml     one profile
bin/linux-amd64/daana-cli  the engine, vendored, pinned by the checksum beside it
```

## Adding an entity

1. Add it to `dab/model.yaml` in **business language**. No source word may appear — not in an
   id, a name, a definition or a description. If you are typing the source's word for
   something, stop and ask what the business calls it.
2. Add `dab/mappings/<entity>-mapping.yaml`, then add it to `workflow.yaml`.
3. `uv run adss dab deploy && uv run adss dab execute`.

Every entity, attribute and relationship needs a `definition` written for a person. A missing
one is a blank row in a glossary somebody notices in a screenshot.

## The seven mapping rules

They are in `docs/conventions.md` §1.4 and checked by `tests/test_mapping_rules.py`, because
**the engine checks none of them**. Two are not style:

- **M3 — `FULL_LOG`, always.** `FULL` against a source with more than one row per key inserts
  a duplicate row on every run, forever, and *every presentation view hides it*. Our staged
  change log is multi-row-per-key by construction, so `FULL` is exactly the wrong default and
  its failure is invisible in both of a question's acceptance queries.
- **M2 — exactly one primary key.** Two entries are read as two *alternate identifiers*, not
  as a composite key, and that mode cannot be undone once loaded. Compose with
  `cast(a AS VARCHAR) || '-' || cast(b AS VARCHAR)` — the separator is not cosmetic, and
  **not `concat`**, which ignores nulls and turns a missing half into a shorter key that collides
  with a real one. `||` yields null and fails at the engine instead. Two entries are refused at
  deploy unless `allow_multiple_identifiers` is set, and with it the key becomes a minted UUID.
  ADR 0010.

## What the engine does and does not do

The whole type vocabulary is `STRING`, `NUMBER`, `UNIT`, `START_TIMESTAMP`, `END_TIMESTAMP`.
There is no plain date type; a business date is `START_TIMESTAMP`.

A version is dated by `entity_effective_timestamp_expression`, which is always `extracted_at`
here — so DAB's history is what the system observed and when. That wins even when the entity
has a `START_TIMESTAMP` attribute; confirmed, not assumed.

## Things that cost a day if you do not know them

- **`daana framework is not installed on the remote database` means the file is busy.** The
  lock is per process: the engine is a subprocess, and it cannot take the lock while we hold
  it. `require_detached` refuses before that happens; if you see the message anyway, close
  whatever has the warehouse open.
- **`<entity>_focal` and `<entity>_idfr` are created and never populated** on this platform.
  Anything joining to them returns nothing, with no error. DAR reads the `view_*` layer only.
- **`view_<entity>_with_rel` is two different things and its name says neither.** On a
  relationship's **source** side it is a passthrough: its columns are identical to
  `view_<entity>`, and it carries no relationship key at all. On a relationship's **target**
  side it becomes a join back to the source entity and gains that entity's key *and every one
  of its attributes*, one row per source row — so it **fans out**, and summing the target's own
  measure over it multiplies. Measured on a probe: 200.75 against a true 150.75. Never read it.
- **Relationship keys come from `v_<src>_<name>_<tgt>`**, which is the raw pair table plus a
  `rel_name` column. Not `view_<src>_<name>_<tgt>`: that one is a *current* view, ranked with
  `rank()` — so it re-points a child's whole history at whichever target it points at now, and
  returns two rows for a child that named two targets at one instant. ADR 0006.
- **A null foreign key is never retracted.** The engine's reader drops null targets, so
  "belongs to nobody" cannot be expressed: re-landing a row with a null key writes nothing at
  all — no row, no tombstone, no `row_st` flip — and the stale pair survives forever.
- **`type_key` is not stable** across models or even across entities within one. Resolve a
  relationship by name, never by number.
- **Object names keep the model's casing**: `view_ORDER`, not `view_order`. Identifiers
  resolve case-insensitively, so a consumer may write either — but code matching names out of
  the catalog must normalise.
- Numeric attributes are widened to `DECIMAL(28, 8)` whatever the source declared.
- DuckDB is not in the engine's own list of supported platforms. It works; do not expect the
  vendor to keep it working.

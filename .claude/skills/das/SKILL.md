---
name: das
description: Work on the DAS layer — data contracts, the dlt landing zone, and the raw and staged views. Use when adding or changing a source, editing das/contracts/*.yaml, touching src/adss/{contract,das,landing,source}.py, re-recording fixtures, or debugging why a column is missing, mistyped, or duplicated in das__staged.
---

# DAS — data according to the system

DAS says what the source said. It captures and persists; it does not interpret. Its two
halves have opposite postures: **ingestion is forgiving, unpacking is strict.**

## The shape

```
das/contracts/<table>.yaml   the contract: documentation, schema and transformation, in one
das/fixtures/<table>/        the recording: response bodies verbatim, plus a manifest
das/lake/das__raw/<table>/extracted_on=YYYY-MM-DD/*.parquet
das/sql/<table>.sql          generated: the three views
```

One contract per source entity set. **The file stem is the landed table name** and is the
name used in every DAS schema, so grepping for a table finds its contract.

## Adding a source

1. Write `das/contracts/<table>.yaml`. Copy an existing one; the keys are fixed.
2. `uv run adss das record --contract <table>` — hits the live service, writes fixtures.
   Read the diff: it is what the source actually sends.
3. `uv run adss das ingest && uv run adss das unpack`.
4. The generated SQL is committed. Check it reads the way you meant.

## What the contract may and may not say

`description` stays in the source's vocabulary: its type, its nullability, what the source
calls it. **Never what it means to the business** — that has exactly one home, and it is not
here.

The format cannot express business logic. There is no key for an expression, a filter, a
default or a coalesce, and one that looks like it is refused when the contract is read. If
you need one, you are in the wrong layer.

`target_name` must be the mechanical `snake_case` of `source_path`. Not a rename. A rename
buries an interpretation in the layer that is supposed to make none.

## Things that cost a day if you do not know them

- **`union_by_name => true` is not optional.** Without it, a column that appears only in a
  later load is silently dropped from the glob. No error. Just missing data.
- **`hive_types` is not optional either**, or the partition key comes back as text.
- **`DECIMAL` takes `precision` and `scale` as their own keys.** YAML splits a flow mapping
  on the comma inside `DECIMAL(18, 4)`, so the contract silently becomes `DECIMAL(18`.
- **The loader does not stop inferring when told to limit nesting.** Top-level keys are
  still split into typed columns, and it will make a decimal into a floating-point number.
  The payload column hint is what stops it.
- **`das__raw` becomes `das_raw`** unless dataset-name normalisation is disabled. A warning
  is all you get.
- **Paths in views are absolute.** A relative one resolves at query time, so a view created
  from the repository root breaks when a page opens the same warehouse from elsewhere.

## The two staged objects

`das__staged.<table>` is the **change log**: one row per source record per load. This is what
DAB historizes from, and it is why the modelling engine uses `FULL_LOG`.

`das__staged.<table>__current` is one row per key from the latest load that carried it. A
question asked *of the source* reads this, because it wants one row per thing rather than one
per observation.

The payload is deliberately absent from both. If it were there, a mapping could read out of
it and the contract would stop being the gate.

## Offline

`--offline` is the default and CI never touches the network. The replay follows the same code
path and the same request URLs as a live read; only what answers them differs. A request the
recording does not cover fails loudly, and the fix is to re-record and read the diff.

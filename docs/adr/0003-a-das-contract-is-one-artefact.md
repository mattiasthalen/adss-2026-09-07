---
status: accepted
date: 2026-09-07
decision-makers: [adss maintainers]
slice: 1
---

# A DAS contract is documentation, schema and transformation in one artefact, and it generates a forgiving raw view plus a strict staged change log

## Context and Problem Statement

Somewhere around the fifteenth staging table, hand-written SQL becomes a collection of
undocumented micro-decisions nobody can reason about as a whole. A `COALESCE` wrapping a
`SAFE_CAST` wrapping a JSON extraction might be handling a known source quirk or working around
bad data that was hot-fixed months ago, and there is no way to tell, because the knowledge left
with whoever wrote it. The contract exists to put that knowledge somewhere a person can read.

Two blueprint principles pull in opposite directions here and the design has to satisfy both. S3
says ingestion is forgiving and unpacking is strict: committing to a schema at ingest turns every
upstream change into lost data, and enforcing nothing on the way out turns every upstream change
into a silent one. S1 says DAS captures and persists *only* — no interpretation. A type cast sits
uncomfortably between them, and the record has to say why it is capture rather than
interpretation.

The append-only rule (S2) creates the question this record most has to answer. After two loads the
lake holds two copies of every unchanged record. Something downstream has to decide whether that
is a change log or a duplicate, and the answer determines how DAB historizes — which makes it the
most consequential thing in the layer.

Two observations, both made against the real tools, close off the obvious implementations. `dlt`
does not stop normalising when told to limit nesting: top-level keys are still split into inferred
typed columns, and inference chose `DOUBLE` for a decimal money field. And `read_parquet` over a
glob **silently drops** columns that appear only in later files — no error, no warning, just
missing data — which is a correctness failure that an append-only lake will produce on its own the
first time a column is added.

## Decision Drivers

* an upstream change must never lose data, and must never pass through unnoticed
* the contract is the documentation, so there is nothing to keep in step with it
* the layer must say what the source said, in the source's words
* per-data-point provenance: from where, and when
* every future engineer's staging decision is made once, in one place

## Considered Options

* One YAML contract generating a raw view over the payload plus a strict staged change log, with a `__current` projection beside it
* `das__staged` deduplicated to one row per key, with the change log discarded
* Letting the loader infer the schema and treating its output as the staged layer
* Hand-written staging SQL per source table

## Decision Outcome

Chosen option: **one contract per source entity set, generating `das__raw.<table>`,
`das__staged.<table>` as the change log, and `das__staged.<table>__current` beside it.**

*`das__raw` is forgiving.* Each source record lands whole, as one JSON value in a `payload`
column, alongside provenance the pipeline adds itself. Nothing is inferred, nothing is split, and
a field the contract has never heard of still lands — it is simply not yet extracted. Schema drift
becomes a contract edit rather than a pipeline failure, which is the whole point of S3's first
half.

*`das__staged` is strict.* One `cast(payload ->> '$.<SourcePath>' AS <TYPE>) AS <target_name>` per
declared column, and nothing else. A column the contract does not declare does not exist
downstream. `payload` is deliberately **absent** from the staged view: if it were present, a DAB
mapping could read `payload ->> '$.X'` and bypass the contract entirely, and the contract would
stop being the gate.

This is where the S1 tension resolves. The cast is not interpretation, it is *transcription*: the
contract records what the source's own metadata says a field is, and the cast makes the warehouse
agree. The evidence that this is the right side of the line is that the alternative loses
information — inference made a decimal into a floating-point number, silently, and money became
approximate. Declaring `DECIMAL(18, 4)` in the contract recovers exactly what the source declared.
What would cross the line is a `COALESCE`, a `CASE` on values, a filter or a default, and the
contract format is structurally incapable of expressing any of them: there is no key for it.

*The staged view is the change log, and `__current` sits beside it.* This is the consequential
half. DAS is append-only, so the change log is what the layer actually holds, and it is what DAB
historizes from — with `FULL_LOG`, which is idempotent against a multi-row-per-key source. The
`__current` projection exists because a question asked *of the source* needs one row per thing,
not one per observation; it is what the independent control query in every question file reads.
Deduplicating `das__staged` itself was the alternative, and it fails on B3: the platform would
then have no record of what it observed and when, and DAB's history would be reconstructed from
something that had already thrown the observations away.

### The provenance columns

The pipeline adds these itself, and they are named for what they record rather than for whoever
wrote them:

| column | why |
|---|---|
| `source_system` | which system this came from. Answers half of "from where" without inference from a path |
| `source_entity` | which entity set within it |
| `source_url` | the request that produced the record |
| `extracted_at` | when DAS observed it. Derived from the load id, and the clock DAB dates every version by |
| `extracted_on` | the date of `extracted_at`, and the lake's hive partition key |

`extracted_on` and `extracted_at` derive from the **same** fact, so they cannot disagree except
across a midnight boundary — and the build asserts they do not. The loader's own bookkeeping
columns stay in `das__raw` and do not cross into `das__staged`, because a loader's column name in
the layer's published interface welds that loader into the layer everything else is rebuilt from.

### Recording and replay

A fixture is the recorded HTTP response body, page by page, exactly as the service returned it,
under `das/fixtures/<source>/<entity>/`. `adss das ingest` reads the live service;
`adss das ingest --offline` reads the fixtures and is otherwise the same code path — same resource,
same contract, same landing. That sameness is what makes the recording honest: a replay that took
a different path would prove nothing about the live run. `adss das record` refreshes a recording,
and the diff on that commit is the source change, visible.

### Consequences

* Good, because an upstream change lands rather than failing, and surfaces as an unextracted field
  rather than as missing data
* Good, because the contract is the documentation, the schema and the transformation, so there is
  nothing that can drift from it
* Good, because thirty tables share one set of staging decisions, and fixing a cast in the type
  table fixes every contract that uses it
* Good, because the change log preserves what the platform observed and when, which is what B3
  needs and what a deduplicating staged view would have destroyed
* Bad, because two staged objects per contract is more surface than one, and a reader has to know
  which to use. The rule is short — DAB reads the change log, questions read `__current` — but it
  is a rule
* Bad, because `payload` being a plain string in the parquet means every strict read pays a JSON
  parse. At this scale that is free; at a scale where it is not, this decision is what would need
  revisiting
* Bad, because the fixtures are a recording of a service that can change without telling us, so a
  green offline build proves the code works, not that the source still looks like that. Only the
  scheduled live run proves the second thing

### Confirmation

A machinery test generates the SQL for a neutral contract fixture and asserts the emitted
expression for every type in the vocabulary, that `union_by_name => true` and `hive_types` are
present, that the path is absolute, and that no key permitting an expression exists in the format.
A contract validator, gate-blocking, asserts every primary key names a declared column, every
`target_name` is the mechanical snake_case of its `source_path`, and every type is in the closed
vocabulary. A data check asserts `extracted_on = cast(extracted_at AS DATE)` on every landed row,
and that a second identical load adds rows to the change log while leaving `__current` unchanged.

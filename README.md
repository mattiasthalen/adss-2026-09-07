# adss

An **Analytical Data Storage System**, built as [blog.daana.dev](https://blog.daana.dev)
describes one: three layers, one direction of flow, and no shortcuts between them.

| Layer | Schemas | What it does | Engine |
|---|---|---|---|
| **DAS** — data according to the *system* | `das__raw`, `das__staged` | captures the source as it arrived, persists it append-only, unpacks it strictly per contract | [dlt](https://dlthub.com) → hive-partitioned parquet → DuckDB views |
| **DAB** — data according to the *business* | `dab`, `dab__stage`, `dab__meta` | the integrated business model, and the only place the data is explained | `daana-cli` focal model |
| **DAR** — data according to the *requirements* | `dar__uss` | a **generated** Unified Star Schema: one event bridge, one peripheral per entity, one calendar | the ADSS USS generator |

Destinations read `dar__uss` and nothing else.

The layer names are not decoration. They are the principles — see
[docs/blueprint.md](docs/blueprint.md).

## Status

Slice 0: the scaffold. The layers, the questions that accept them, and the skills that describe
them arrive in the slices that follow.

## Getting started

```bash
uv sync --all-groups
uv run adss --version
uv run pytest
uv run pre-commit run --all-files
```

## Slices

Each slice answers one business question, and the presentation of that answer is what the slice
is accepted on. It is the prototype, not a report generated afterwards.

| # | Question | Status |
|---|---|---|
| 1 | How many orders were placed per order month and ship country? | not started |

## Reading order

| Document | What it is |
|---|---|
| [docs/blueprint.md](docs/blueprint.md) | the principles, technology-free, no exceptions |
| [docs/conventions.md](docs/conventions.md) | the one convention document: naming, SQL, YAML, Python, commits |
| [docs/adr/](docs/adr/README.md) | one record per decision, written before the code it decides |
| [docs/deviations.md](docs/deviations.md) | every knowing departure from a principle, with its cost and its exit condition |
| [docs/questions/](docs/questions/) | the business questions, and the two queries that must agree on each answer |

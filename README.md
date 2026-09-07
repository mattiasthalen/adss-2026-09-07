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

Slice 1 is green: one business question answered end to end, through all three layers, and
presented in a page. `uv run adss build` rebuilds the whole system from the recording in about
eleven seconds with no network.

## Getting started

```bash
uv sync --all-groups
uv run adss build                    # the whole system, offline, from das/fixtures
uv run adss check                    # what the built warehouse must contain
uv run marimo run destinations/app.py  # the page a slice is accepted on
uv run pre-commit run --all-files    # the gate every commit passes
```

The engine is a large object under git-LFS. `git lfs pull` if your clone has only the pointer.

## Slices

Each slice answers one business question, and the presentation of that answer is what the slice
is accepted on. It is the prototype, not a report generated afterwards.

| # | Question | Status |
|---|---|---|
| 1 | How many orders were placed per order month and destination country? | green |
| 2 | What freight did we pay per customer country and order quarter? | not started |

The full prioritised list, and what each slice widens, is in
[docs/questions/](docs/questions/README.md).

## Reading order

| Document | What it is |
|---|---|
| [docs/blueprint.md](docs/blueprint.md) | the principles, technology-free, no exceptions |
| [docs/conventions.md](docs/conventions.md) | the one convention document: naming, SQL, YAML, Python, commits |
| [docs/adr/](docs/adr/README.md) | one record per decision, written before the code it decides |
| [docs/deviations.md](docs/deviations.md) | every knowing departure from a principle, with its cost and its exit condition |
| [docs/questions/](docs/questions/README.md) | the prioritised question list, and for each one the two queries that must agree on its answer |
| [.claude/skills/](.claude/skills/) | one skill per layer, one per destination, and one for the whole |

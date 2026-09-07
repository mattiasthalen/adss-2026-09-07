---
name: dar
description: Work on the DAR layer — the generated Unified Star Schema, dab/uss.yaml, and the SQL under dar/uss. Use when adding an event or a measure, changing the bridge's column contract, debugging a total that is wrong or multiplied, or when generated SQL and the model have drifted.
---

# DAR — data according to the requirements

One bridge, one peripheral per entity, one calendar. **Nothing here is hand-written**, and a
wrong name is fixed in the model and regenerated. An edit to generated output is lost on the
next generation, and until then the code and the model quietly disagree.

## The shape

```
dab/uss.yaml        the declarations: events, their dates, their measures
dar/uss/*.sql       generated and committed
```

`uv run adss dar generate` writes them; `--check` fails if the committed SQL is not what the
model produces; `uv run adss dar build` runs them.

## The column contract

Everything downstream is written against these names and will not survive them changing. A
model change **appends**; it never rearranges.

| column | what it is |
|---|---|
| `_stage` | the entity this row is a row *of* |
| `_event` | the event, lower-cased |
| `_event_date` | joins `_calendar.date_key` |
| `_is_current` | always true on a transaction stage |
| `_observed_at` | the DAB effective timestamp, which is the DAS extraction time |
| `<entity>_key` | one per entity, in model order |
| `_measure__<entity>__<measure>` | one per measure; **non-null only on the owning stage** |

## The one rule that matters most

**Keys inherit; measures do not.** A stage carries the key of every entity it reaches along
many-to-one relationships, and a measure is non-null only on the stage that owns it. Copying a
parent's measure onto its children multiplies it when summed — that is the fan trap, and
avoiding it is the entire reason there is a bridge rather than one wide join.

Two consequences at query time, neither of which the schema can enforce:

- A join on the row's own `_stage` key may be `INNER`. A join on an **inherited** key must be
  `LEFT`.
- A ratio is `sum(a) / sum(b)` at query time. It is never a stored measure: an average of
  averages is wrong at every grain but the one it was computed at.

## Adding a measure

Add it to `dab/uss.yaml` under its event, with a **definition** — the glossary copies these
verbatim and never composes one. Name it `<descriptor>_<entities>_<unit>`, entity plural, no
scope or aggregation words: `placed_orders_count`, never `total_orders`. Then regenerate.

## Things worth knowing

- The generator reads `view_<entity>_hist` and keeps the latest version **in which the event's
  date is set**, so an entity the event never happened to has no row for it by construction
  rather than by a filter someone has to remember.
- It never reads `_focal` or `_idfr` (empty on this platform) or `_with_rel` (a passthrough on
  a relationship's source side, and a fanned-out join on its target side — see the dab skill).
- **An inherited key comes from `v_<src>_<name>_<tgt>`, ranked here rather than by the engine**,
  as of the observation time of the row that inherits it, `row_st = 'Y'` only, matched on
  `rel_name`, joined LEFT, and ranked with `row_number()` and an explicit tiebreak so it cannot
  fan out. Every clause of that sentence is load-bearing; ADR 0006 says which failure each one
  prevents.
- **It never invents a member.** A null dimension stays null. A question that wants nulls
  grouped or excluded says so in its own file, because that is a property of the question.
- Layout is the linter's, applied *inside* the generator. Do not hand-format emitted SQL and
  do not run a formatter over `dar/uss` afterwards — either produces a diff on every
  regeneration.
- A zero-edge walk is a valid walk. One entity and no relationships is the normal case.

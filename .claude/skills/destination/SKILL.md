---
name: destination
description: Work on the marimo destination — the page that presents a question and its answer, and the screenshots a slice is accepted on. Use when adding a page for a new question, changing a chart, or when a screenshot is blank, truncated or fails to render.
---

# Destinations

A destination presents one question and its answer. It **is** the prototype, not a report
about one — the slice is accepted on it.

```
destinations/app.py     one app, a page per question
uv run marimo edit destinations/app.py     author it
uv run marimo run destinations/app.py      run it as an app
uv run adss shoot                          photograph it for a pull request
```

## Rules

- **It reads `dar__uss` and nothing else.** Not `das__staged`, not `dab`, not the lake. If a
  page needs something DAR does not have, that is a DAR change.
- **It reads the question's own `uss.sql`**, so what a reader sees and what the build checks
  cannot disagree about what was asked.
- **It opens the warehouse `read_only=True`**, and anchors paths on `Path(__file__).parent`.
  The working directory is not where you think during an export or a screenshot.
- **It explains nothing itself.** Definitions are copied from the model. A page that writes
  its own definition has created a second one, and it will be the one that is out of date.

## Charts

Pick the form from the job, then the colour. Magnitude over a grid is a heatmap on **one hue**,
light to dark. Distinct series are categorical hues assigned in fixed order, never cycled, and
past about eight they fold into "Other" or facet. Never two y-scales. Ratios are computed from
two additive measures at query time.

Cast an aggregate to `DOUBLE` before charting: DuckDB `DECIMAL` reaches the frontend as a
decimal type the chart library cannot encode.

## Screenshots

`uv run adss shoot`. Three things about it are the result of getting them wrong first:

- **The exported HTML is not self-contained.** It loads its assets from a content network and
  renders as a blank white page offline. Never screenshot the export.
- **`--execute` is not the default.** Without it the thumbnail is the page's structure with
  none of its outputs — a picture that looks like a screenshot and answers nothing.
- **The export exits 0 even when cells failed**, printing "some cells failed". The step checks
  for that, and for a file too small to be a render.

The browser build the driver wants is read off its own complaint and the installed browser is
presented under that name. Never run `playwright install`.

## Ruff

marimo cells are decorated functions whose return types are meaningless, and marimo rewrites
the file on save. `destinations/` is exempt from `ANN` and is not formatted by `ruff format`.
That exemption lives in the config, which is where the rule lives.

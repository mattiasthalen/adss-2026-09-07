# Checks

Assertions about what the built warehouse actually contains.

These are **not** the machinery tests in `tests/`. Those run on every commit over data files
and need no warehouse; these need a real build and run after one. The split exists because
the warehouse is not committed, so a data check in the commit gate would fail in every fresh
checkout — and both ways out of that are forbidden: a skip is a test that silently does not
exist, and a stub is something a check can pass against while the build is broken.

```bash
uv run adss build      # then
uv run adss check
```

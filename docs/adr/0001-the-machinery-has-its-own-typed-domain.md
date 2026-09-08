---
status: accepted
date: 2026-09-07
decision-makers: [adss maintainers]
slice: 1
---

# The machinery is modelled in its own typed vocabulary, and no business word appears under `src/`

## Context and Problem Statement

The brief asks for a domain model that does not restate `dab/model.yaml`. That constraint is
easy to read as a style preference and it is not one: it decides what this repository is.

There are two candidate domains here and they are genuinely different. One is the business —
orders, countries, the dates on which things happened — and it already has a home, because
`dab/model.yaml` is the only place the data is explained (blueprint B8). The other is the
*system*: contracts, pipelines, landings, staged views, mappings, plans, stages, peripherals,
bridges, questions, destinations. Nothing describes that domain yet, and it is the one the Python
is actually about.

The failure mode this guards against is specific. A pipeline that knows what an order is has
stopped being a pipeline and become an order-loading script, and the next source needs a second
one. The blog names this from the other direction: what makes a declarative platform work is that
"an agent that learns the shape of one entity knows the shape of all of them"
(*context-isnt-enough*). Uniformity is the property, and a special case in the machinery is what
destroys it — quietly, one entity at a time.

There is a real cost on the other side, and the same literature names it: over-generic models
"lacking domain specificity" are one of the two named failure modes of model-driven platforms
(*the-rise-of-model-driven-data-engineer*). A machinery vocabulary is a second thing to learn, and
an abstraction built for slices that may never arrive is worse than the concrete code it replaced.

## Decision Drivers

* the machinery must work for a source and a business model it has never seen
* the constraint must be checkable, not merely believed
* tests must *prove* the machinery is generic rather than assert it
* the model must be small enough that slice 1 does not pay for slice 6

## Considered Options

* A typed machinery domain model, with no business vocabulary under `src/` or in tests
* Untyped dictionaries and strings throughout, with the shape documented in prose
* A machinery model that names business concepts where it is convenient
* A generic model built now for all six slices

## Decision Outcome

Chosen option: **a typed machinery domain model with no business vocabulary under `src/` or in
tests**, and neutral fixture systems held as data files.

The rule earns its keep by being falsifiable. "The machinery is generic" is an assertion; "no
business word appears in it" is a property anyone can check by reading, and a reviewer who finds
`order` in a function name has found a real defect without needing to understand the pipeline. It
converts an architectural intention into something a code review can act on.

Tests are where the rule does its most useful work. A test that loads a fixture called `ORDER`
proves the machinery works for orders; a test that loads a neutral fixture — `PARENT`, `CHILD`,
declared in a YAML file the test does not read for meaning — proves it works for *a* model. The
second is the claim we actually want, and it is only available if the vocabulary stays out of the
test. This is also why the question runner is parameterised over discovered question files rather
than written as one test function per question: a per-question function smuggles the business
vocabulary back in through its own name.

Untyped dictionaries were the serious alternative, and they lose on the same ground. The types are
where the machinery's own concepts are *named*, and a `dict[str, Any]` passed between six
functions has no domain model at all — only a convention nobody can check. A strict type checker
handles frozen dataclasses, string enums and discriminated unions with no friction, so the cost of
typing is close to zero and the return is a compiler that refuses to let a `Contract` be used
where a `Model` is meant.

The last option — building the model for all six slices now — is rejected on the named failure
mode. Slice 1 gets exactly the types slice 1 needs. No `Relationship`, no `Cardinality`, no
measure kinds, no dialect abstraction beyond the single seam. Every one of those arrives in the
slice that first has two of something to generalise over, which is the only point at which the
generalisation can be judged.

### Consequences

* Good, because the claim "this works for any source and any business model" becomes a property a
  reader can verify rather than a promise
* Good, because the types name the machinery's own domain, which is otherwise nameless and lives
  only in whoever wrote the pipeline
* Good, because a neutral fixture makes a test prove genericity instead of asserting it
* Bad, because there is now a second vocabulary to learn, and someone debugging a data problem has
  to translate between "peripheral" and the entity they were actually looking at
* Bad, because the rule has an awkward edge at the boundary: SQL generation must *emit* business
  names it may not *contain*, so those names arrive as data and the code manipulating them reads
  more abstractly than the thing it produces
* Bad, because building only for slice 1 guarantees refactoring in slices 2 and 4, when
  relationships and a second grain arrive. That is the intended trade: refactoring under a test
  suite is cheaper than an abstraction chosen before the second case existed

### Confirmation

`tests/` contains no entity, attribute, measure, source or column name from the business, and its
fixtures are neutral models held as data files. That is a hard rule in
[conventions.md §5 and §6](../conventions.md) and it is checked by reading — no linter can tell a
business noun from a machinery one, and a regex list of forbidden words would be a second copy of
the business model living in the machinery, which is the thing this record forbids.

The type gate is `ty --error all`, and `ANN` stays in the ruff selection because `ty` does not
flag a fully unannotated `def`.

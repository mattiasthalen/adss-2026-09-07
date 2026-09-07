# Business questions

A question is the unit of delivery. It is the specification, the acceptance test and what the
page renders — one artefact, so those three cannot disagree about what was asked.
[ADR 0005](../adr/0005-a-question-is-the-unit-of-delivery.md) argues why;
[conventions §10](../conventions.md) is the rules.

## The prioritised list

Drafted from what the source can actually answer, ordered so each slice widens the system by
**one** thing. It is re-prioritised after every acceptance, because seeing real data is what
tells you what to ask next — a question may be validated, refined, or pivoted, and all three
are the methodology working rather than a plan going wrong.

| # | Persona | Question | What it widens | Status |
|---|---|---|---|---|
| [1](01-orders-per-month-and-destination-country/) | Sales director | How many orders were placed per order month and destination country? | The whole spine, once: one contract, one entity, one transaction event, one count measure, bridge and peripheral and calendar, one page | green |
| 2 | Logistics manager | What freight did we pay per customer country and order quarter? | A second contract and entity, the **first relationship**, and the first key a stage inherits — customer country is not destination country, so the relationship has to carry it | not started |
| 3 | Operations manager | How many orders shipped per shipping month, and how many days did they take? | **Two events on one entity**, a second stage in the bridge, and a ratio computed at query time from two additive measures. 21 orders have never shipped, so "an event that did not happen has no row" stops being theoretical | not started |
| 4 | Finance analyst | What revenue did we take per order month? | A third entity at a **finer grain**, a derived measure, and the fan-out proof: freight sits on the order and must not multiply across its lines | not started |
| 5 | Category manager | What revenue did we take per product category and quarter? | Two more contracts and a **two-hop relationship chain** — line to product to category | not started |
| 6 | Sales director | What revenue did we take per customer segment and quarter? | **The second source.** A file drop with its own customer identifiers, overlapping on only some rows, carrying a segment that exists nowhere else | not started |

Slice 6 is the one that matters most: it is the only question here that cannot be answered
without the integration layer, so it is where the architecture stops being an argument.

Slice 4 is where the shared-bridge deviation ([D-0001](../deviations.md)) stops being carried
on assertion — a second grain is the first thing a measure could multiply across.

## The shape of one

```
docs/questions/NN-<slug>/
├── question.md    front matter, the story, the W's, the definitions it depends on
├── staged.sql     the control: computed from the source, bypassing both layers
├── uss.sql        the answer: computed from the generated star schema
└── answer.png     the presentation it was accepted on
```

The two queries must agree row for row, and `adss check` asserts it. What that proves is
worth stating plainly: it catches a number the layers **changed**, which is the failure this
architecture is most exposed to and least able to see. It does not catch a wrong definition —
both queries would be written to it and both would be wrong together. When they disagree,
`dab/model.yaml` is the arbiter, and the query that departs from the definition is the one
that changes.

A question **references** definitions and never restates one. A token that resolves to
nothing is refused as a gap in the model, to be filled there first — which is the methodology
working: a question the model cannot answer has found something, and finding it was the point.

export const meta = {
  name: 'frame-slice-05',
  description: 'Frame slice 5 of the ADSS build: options for the decision a two-hop chain forces, and an audit of what already binds it',
  phases: [{ title: 'Frame', detail: 'Options and constraints, read independently' }],
}

const REPO = '/home/user/adss-2026-09-07'

const CONTEXT = `
The repository at ${REPO}, branch claude/adss-slice-04-revenue-per-order-month (slice 4 just
landed and is green). Read whatever you need; do NOT modify any file.

The system is an "Analytical Data Storage System": DAS (das/, contracts over recorded OData
fixtures, hive-partitioned parquet, das__raw + das__staged) -> DAB (dab/model.yaml, mappings,
the daana-cli modelling engine, schema dab) -> DAR (generated Unified Star Schema, dar__uss)
-> destinations/ (one marimo page, a section per question). Analytical usage reads only
dar__uss; dar reads only dab; dab reads only das.

Slice 5's question, from docs/questions/README.md:
  "What revenue did we take per product category and quarter?" -- asked by a category manager.
  What it widens: two more contracts and a TWO-HOP relationship chain, line -> product ->
  category.

Everything already decided is in docs/adr/0000..0013, docs/conventions.md, docs/blueprint.md
and docs/deviations.md. Slice 4 added: ORDER_LINE at a finer grain, an inherited event date
(ADR 0009), a composed composite key (ADR 0010), the fan-out proof and the rule that an answer
query may aggregate only _measure__ columns (ADR 0012), and one clock per ingest (ADR 0013).

The source is the Northwind OData demo service at
https://demodata.grapecity.com/northwind/odata/v1 (recorded under das/fixtures/). Products and
Categories are entity sets there.
`

const OPTIONS = `${CONTEXT}

YOUR JOB: draft the OPTIONS AND CONSEQUENCES for the single decision slice 5 forces, well
enough that a MADR can be written from it.

The decision is about the TWO-HOP CHAIN: an order line points at a product, and a product
points at a category, and the question groups revenue by the category. Nothing in this system
has ever walked two edges.

Work out, from the code rather than from first principles:
- What the generator does today with a walk of more than one edge. Read src/adss/uss.py --
  entity_ids, entity_keys, _inherit_cte, _stage_cte, _branch -- and say exactly what happens
  if ORDER_LINE reaches PRODUCT and PRODUCT reaches CATEGORY. Does the bridge get a
  category_key at all? Does the peripheral for CATEGORY exist? Is the walk transitive or one
  hop deep? Quote the code.
- What the modelling engine gives us. The dab and dar skills under .claude/skills/ record what
  daana-cli actually does on DuckDB, including that focal and identifier tables are never
  populated and that relationship keys come from v_<src>_<name>_<tgt>. Say what a second hop
  would need from the engine.
- The candidate options. At least: (a) make the bridge's walk transitive, so a stage carries
  the key of everything it reaches at any depth; (b) keep one hop and denormalise the category
  onto the product peripheral; (c) keep one hop and let the question join peripheral to
  peripheral in dar__uss; (d) anything else the code suggests. For each: what it costs, what
  it makes impossible later, and which existing ADR or convention it sits against.
- Which of the blog's own principles bear on it (docs/blueprint.md is the technology-free
  statement of them).

Quote file and line for every claim about what the code does. Where you are guessing, say so.
Do not recommend one option; lay them out.`

const AUDIT = `${CONTEXT}

YOUR JOB: audit what ALREADY BINDS slice 5, and report any rule it would break.

Read, in full: docs/blueprint.md, docs/conventions.md, docs/deviations.md, and every record in
docs/adr/. Then read enough of src/ to know which rules are mechanically enforced and which
are only written down.

Report:
1. Every rule, convention, deviation or ADR that constrains how a two-hop relationship chain
   may be modelled, generated or queried -- with the section or record number, quoted.
2. Anything slice 5 would BREAK as the system stands. Be concrete: name the rule, name what
   would break it, and say whether a check would catch it or whether it would pass silently.
3. Every place a new contract, entity, relationship, event or measure has to be registered for
   the build to stay coherent -- the full list, in the order a slice has to touch them. Derive
   it from what slice 4 actually changed (git diff against
   claude/adss-slice-03-shipped-orders-and-days-to-ship) rather than from the documentation.
4. Anything in the deviations register whose exit condition slice 5 would meet, or whose
   argument slice 5 would test. D-0001 in particular: its exit condition is "a second consumer
   needs isolation". Does slice 5 meet it? Answer with the entry's own words.
5. Any claim in the records that slice 5 would falsify.

Quote file and line throughout. An empty section is a valid answer; say so rather than filling it.`

const results = await parallel([
  () => agent(OPTIONS, { label: 'frame:options', phase: 'Frame' }),
  () => agent(AUDIT, { label: 'frame:audit', phase: 'Frame' }),
])

return { options: results[0], audit: results[1] }

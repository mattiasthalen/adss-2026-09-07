export const meta = {
  name: 'slice-02-frame',
  description: 'Frame slice 2: how relationship keys enter the bridge, and what already binds the slice',
  phases: [
    { title: 'Frame', detail: 'the decision this slice forces, an audit of what binds it, and a probe of the real engine' },
  ],
}

const REPO = '/home/user/adss-2026-09-07'
const SPIKES = '/tmp/claude-0/-home-user-adss-2026-09-07/45a0041f-5559-570b-bd39-1d1517807233/scratchpad/spike-findings.json'
const POSTS = '/tmp/claude-0/-home-user-adss-2026-09-07/45a0041f-5559-570b-bd39-1d1517807233/scratchpad/blog'
const SCRATCH = '/tmp/claude-0/-home-user-adss-2026-09-07/45a0041f-5559-570b-bd39-1d1517807233/scratchpad/slice02'

const COMMON = `
THE REPOSITORY: ${REPO}. An analytical data storage system in three layers, built as
blog.daana.dev describes one. Slice 1 is complete and green: one entity (ORDER), one
transaction event, one count measure, one page.

READ FIRST: ${REPO}/docs/blueprint.md, ${REPO}/docs/conventions.md,
${REPO}/docs/deviations.md, ${REPO}/docs/adr/*.md, and the layer skills under
${REPO}/.claude/skills/. Also ${SPIKES} (verbatim findings from spikes against the real
tools -- treat as fact) and ${POSTS}/*.txt (the blog posts in full).

SLICE 2 answers: "What freight did we pay per customer country and order quarter?"
It adds a second contract (Northwind Customers), a second entity (CUSTOMER), the FIRST
relationship (an order is placed by a customer), the FIRST inherited key, and the FIRST sum
measure (freight, a NUMBER on ORDER).

Why this question and not an easier one: the freight is on the ORDER and the country is on
the CUSTOMER, and they are different countries -- Northwind's ship country is where the goods
went, the customer's country is where the customer is. So the answer is unobtainable without
the relationship actually carrying a key. That is the point of the slice.

HARD RULES
- Do NOT write, edit or create any file under ${REPO}. Do not run git commands that change
  state. You may create and use scratch files under ${SCRATCH} (mkdir it yourself).
- Do NOT read anything from the repository mattiasthalen/ADSS-fable-POC. A previous run at
  this brief lives there and the user ruled it out of scope.
- Ground every claim in something you read or ran. Where the blog says something, attribute
  it to the post. Where neither the blog nor a spike settles it, SAY SO.
`

const ADR_SCHEMA = {
  type: 'object',
  properties: {
    title: { type: 'string' },
    contextAndProblem: { type: 'string', description: '3-6 paragraphs on what makes this hard HERE' },
    decisionDrivers: { type: 'array', items: { type: 'string' } },
    consideredOptions: { type: 'array', items: { type: 'string' }, description: 'At least 3 real options' },
    recommendation: { type: 'string' },
    argument: { type: 'string', description: 'Several paragraphs. Argue the rejected options fairly.' },
    consequences: {
      type: 'array',
      items: {
        type: 'object',
        properties: { kind: { type: 'string', enum: ['good', 'bad'] }, text: { type: 'string' } },
        required: ['kind', 'text'],
      },
      description: 'At least two of kind bad, and real',
    },
    confirmation: { type: 'string', description: 'The test or check that proves this is implemented and still holds' },
    concreteShape: { type: 'string', description: 'Literal YAML, SQL and column names to build from' },
    evidence: { type: 'array', items: { type: 'string' }, description: 'What you actually ran or read, quoted' },
    notSettled: { type: 'array', items: { type: 'string' } },
  },
  required: ['title', 'contextAndProblem', 'decisionDrivers', 'consideredOptions', 'recommendation', 'argument', 'consequences', 'confirmation', 'concreteShape', 'evidence', 'notSettled'],
}

phase('Frame')

const probe = agent(
  COMMON + `

YOU ARE THE PROBE. Your job is to find out what the real engine actually produces for a
relationship, because ADR 0002 asserts things about it that nothing in the repository has
ever exercised -- slice 1 had no relationships at all.

Work in ${SCRATCH}/probe. Build a THROWAWAY daana project there (do NOT touch ${REPO}'s
warehouse, model or mappings). The engine binary is at ${REPO}/bin/linux-amd64/daana-cli.
${REPO}/dab/ has a working single-entity project you can copy and extend as a starting point,
and ${SPIKES} records how a DuckDB connection profile is written and what slice-1's DAB
output looked like.

Make a two-entity model with ONE relationship -- neutral names, PARENT and CHILD, a
relationship from CHILD to PARENT -- backed by das__staged views you create yourself with a
handful of rows. Deploy and execute it. Then answer, with real output quoted:

1. What objects does a relationship create? List EVERYTHING in the dab schema, and say which
   are tables, which are views, and which are DuckDB table macros (macros do not appear in
   information_schema.tables -- use duckdb_functions()).
2. What are the exact columns and rows of the pair table (the one named like <SRC>_<TGT>_x)?
   Quote a DESCRIBE and the rows.
3. What are the exact columns and rows of the relationship VIEW (view_<SRC>_<NAME>_<TGT> or
   whatever it is actually called -- report the real name)?
4. THE IMPORTANT ONE. ADR 0002 claims the generator must read the pair TABLE rather than the
   relationship VIEW, because the view "ranks pairs by the effective timestamp and keeps the
   open rows", so a changed foreign key could drop out of the view entirely. TEST THAT.
   Load a child pointing at parent A. Then change that child's foreign key to parent B with a
   later effective timestamp and re-execute. Report exactly what the pair table holds and what
   the view holds afterwards. Does the claim reproduce, or is it wrong?
5. Does the pair table carry row_st / ver_tmstp / eff_tmstp, and what values? What does the
   correct "latest open pair per child" query look like against it?
6. What happens to a child with NO parent -- no relationship row at all? Does it appear in
   the pair table, the view, neither?
7. Does the model declare cardinality anywhere? Read the model grammar: is there any way to
   say a relationship is many-to-one rather than one-to-many or many-to-many? If not, say so
   plainly -- the generator has to know, and if the model cannot say it, something else must.
8. What does the engine do with an entity attribute typed NUMBER? Quote the DESCRIBE of the
   entity view and say the exact type. (Slice 2's first sum measure is a NUMBER.)

Report findings, not opinions. If something in ADR 0002 turns out to be wrong, say so in
those words -- that is the single most valuable thing you can return.`,
  { label: 'engine-probe', phase: 'Frame', schema: {
    type: 'object',
    properties: {
      reproduced: { type: 'string', enum: ['adr-0002-is-right', 'adr-0002-is-wrong', 'inconclusive'] },
      headline: { type: 'string' },
      objects: { type: 'array', items: { type: 'string' }, description: 'Every dab object a relationship creates, with its kind' },
      pairTable: { type: 'string', description: 'DESCRIBE and rows, verbatim' },
      relationshipView: { type: 'string', description: 'Real name, DESCRIBE and rows, verbatim' },
      changedForeignKey: { type: 'string', description: 'What the pair table and the view each held after the change. The decisive evidence.' },
      orphanChild: { type: 'string' },
      cardinality: { type: 'string', description: 'Can the model declare it? Answer plainly.' },
      numberType: { type: 'string' },
      correctQuery: { type: 'string', description: 'The SQL that correctly gets the latest open pair per child, verified to run' },
      gotchas: { type: 'array', items: { type: 'string' } },
    },
    required: ['reproduced', 'headline', 'objects', 'pairTable', 'relationshipView', 'changedForeignKey', 'orphanChild', 'cardinality', 'numberType', 'correctQuery', 'gotchas'],
  } }
)

const audit = agent(
  COMMON + `

YOU ARE THE AUDIT. Not a decision -- what is ALREADY in force, and where does slice 2 strain
it? This runs at the start of every slice.

Read the blueprint, the conventions, the deviations register and all six ADRs completely.
Read the repository as it stands (excluding .venv, das/lake, warehouse.duckdb).

1. List every principle and hard rule that binds slice 2, with what it forbids CONCRETELY.
   Pay attention to the ones slice 1 never exercised: M6 (relationship id, byte-identical
   source_table, mirrored target key expression) becomes live for the first time; the DAR
   inherited-key join rule (INNER on own key, LEFT on inherited) becomes live; the measure
   naming rules meet their first sum.
2. Be ADVERSARIAL about tensions. Look hard. Candidates to test, and do not stop at these:
   - conventions 1.2 forbids source names in dab/model.yaml. Northwind's customer table has
     a Country column and the entity will need a country attribute. Is CUSTOMER_COUNTRY a
     source name? Slice 1 renamed ship country to DESTINATION_COUNTRY for exactly this rule.
   - the question groups by the CUSTOMER's country and sums a measure owned by ORDER. Which
     stage owns the measure, which key is inherited, and does the answer query join INNER or
     LEFT? Get this right on paper before anyone writes it.
   - D-0001's argument rests on a walk over many-to-one edges. Slice 2 creates the first edge.
     Does the deviation's justification become demonstrable now, or does it still wait for a
     second grain in slice 4? Be precise: what exactly does one n:1 edge demonstrate and what
     does it not?
   - an order with no customer, and a customer with no orders. What does each do to the
     answer, and does the question have to say?
3. Review every open entry in deviations.md against its exit condition.
4. Name rules the conventions document is MISSING that slice 2 will otherwise invent
   silently.

For each tension say which of the three recourses in conventions section 11 applies, and
recommend one. Do not soften a real tension and do not manufacture one.`,
  { label: 'binding-audit', phase: 'Frame', schema: {
    type: 'object',
    properties: {
      binds: { type: 'array', items: { type: 'object', properties: { rule: { type: 'string' }, source: { type: 'string' }, whatItForbidsHere: { type: 'string' } }, required: ['rule', 'source', 'whatItForbidsHere'] } },
      tensions: { type: 'array', items: { type: 'object', properties: { rule: { type: 'string' }, howSliceTwoStrainsIt: { type: 'string' }, resolution: { type: 'string' } }, required: ['rule', 'howSliceTwoStrainsIt', 'resolution'] } },
      deviationReview: { type: 'string' },
      theJoinOnPaper: { type: 'string', description: 'Which stage owns freight, which key is inherited, INNER or LEFT, and why -- worked through before anyone writes it' },
      gaps: { type: 'array', items: { type: 'string' } },
    },
    required: ['binds', 'tensions', 'deviationReview', 'theJoinOnPaper', 'gaps'],
  } }
)

const decision = agent(
  COMMON + `

YOU ARE DRAFTING ONE DECISION RECORD: how relationship keys enter the bridge.

This is the decision slice 2 forces, and it is the one ADR 0002 wrote a cheque for that
nothing has cashed. Read ${REPO}/docs/adr/0002-dar-is-one-generated-unified-star-schema.md
closely -- especially what it says about reading the pair table rather than the relationship
view, and about a stage carrying the key of every entity it reaches along many-to-one
relationships. Read ${POSTS}/consumption-layer-generates-itself.txt in full for what the
Unified Star Schema says about keys propagating.

Resolve these, and they are the whole difficulty:

1. HOW DOES THE GENERATOR KNOW A RELATIONSHIP IS MANY-TO-ONE? The modelling language declares
   a relationship as a name plus a source entity and a target entity. Read the grammar in
   ${REPO}/dab/model.yaml and the model template. If it cannot express cardinality, then the
   generator cannot walk "many-to-one edges" without being told something the model does not
   say. Options include: treat source->target as n:1 by convention; declare the walk in
   dab/uss.yaml; derive it from the data at build time and refuse when it does not hold.
   Each has a real cost. Pick one and argue it.
2. WHAT DOES A STAGE ACTUALLY SELECT? Write the SQL. A stage on ORDER must emit order_key
   (its own) and customer_key (inherited). Where does customer_key come from, what is joined
   to what, and what happens to an order whose customer is unknown -- is the row dropped or
   kept with a null key? The bridge's whole value is that a sum is right, so dropping rows
   silently is the failure to avoid.
3. HOW FAR DOES THE WALK GO? Slice 5 has a two-hop chain. Does slice 2 build a general walk
   or a one-hop special case? ADR 0001 says build for this slice only and resist modelling
   later ones -- but ADR 0002 already published a column contract that says keys inherit.
   Argue where the line is.
4. THE FAN-OUT LINE. A measure is non-null only on the stage that owns it. With ORDER->CUSTOMER
   there is nothing yet to multiply across, but the rule must be implemented now because
   slice 4 depends on it. What exactly does slice 2 implement and what does it defer?

concreteShape must give: the literal dab/uss.yaml for slice 2, the literal generated bridge
SQL with both stages' columns, and the answer query for the question, all in the house SQL
style (docs/conventions.md section 3).

Note: a probe agent is running in parallel against the real engine to establish what a
relationship actually produces. Write your argument so it does not depend on guessing that --
where you need a fact about the engine, name the fact you need and say what you would do if
it went either way.`,
  { label: 'adr-relationships', phase: 'Frame', schema: ADR_SCHEMA }
)

const [probed, audited, drafted] = await Promise.all([probe, audit, decision])
log('framed slice 2')
return { probe: probed, audit: audited, decision: drafted }

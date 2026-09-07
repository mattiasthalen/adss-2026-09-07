export const meta = {
  name: 'slice-01-frame',
  description: 'Frame slice 1: draft the argument for each founding decision, and audit what already binds them',
  phases: [
    { title: 'Frame', detail: 'one agent per founding decision, plus an audit of what already binds this slice' },
  ],
}

const REPO = '/home/user/adss-2026-09-07'
const SPIKES = '/tmp/claude-0/-home-user-adss-2026-09-07/45a0041f-5559-570b-bd39-1d1517807233/scratchpad/spike-findings.json'
const BLOG = '/tmp/claude-0/-home-user-adss-2026-09-07/45a0041f-5559-570b-bd39-1d1517807233/scratchpad/blog-synthesis.json'
const POSTS = '/tmp/claude-0/-home-user-adss-2026-09-07/45a0041f-5559-570b-bd39-1d1517807233/scratchpad/blog'

const COMMON = `
You are drafting the ARGUMENT for one architecture decision record. You are NOT writing code and
NOT writing the ADR file. Your output is the reasoning someone else will turn into a MADR.

READ FIRST, all of them, properly:
- ${REPO}/docs/blueprint.md      the absolute principles. These bind you. You may not contradict them.
- ${REPO}/docs/conventions.md    the one convention document.
- ${REPO}/docs/deviations.md     the register, and its one open entry.
- ${SPIKES}                      verbatim findings from four spikes run against the real tools. TREAT THESE AS FACT; they were observed, not guessed.
- ${BLOG}                        a consolidated constraint map from 18 blog posts, with per-post attribution and a list of what the blog does NOT settle.
- ${POSTS}/design-of-analytical-systems.txt and the other .txt files there are the posts themselves, in full. Read the ones relevant to your decision.

HARD RULES
- Do NOT write, edit or create ANY file. Do not run git. Read and reason only.
- Do NOT read anything from the repository mattiasthalen/ADSS-fable-POC other than the daana-cli binary's own --help output. A previous run at this brief lives on its branches and the user has explicitly ruled it out of scope. If you find yourself there, stop.
- Ground every claim. Where the blog says something, attribute it to the post. Where a spike observed something, quote the observation. Where neither settles it, SAY SO - that is the most useful thing you can tell me.
- Argue the options you reject as strongly as the one you recommend. A record whose alternatives are strawmen is worthless.
- The Consequences must include real costs. A recommendation with only good consequences has not been thought about.

THE SYSTEM BEING BUILT
One DuckDB file. DAS (schemas das__raw, das__staged) ingests Northwind OData via dlt into
hive-partitioned parquet and unpacks it as views. DAB (dab, dab__stage, dab__meta) is a daana-cli
focal/ensemble model; dab/model.yaml is the only place the data is explained. DAR (dar__uss) is a
generated Puppini Unified Star Schema. Destinations are marimo pages reading dar__uss only.
Python 3.12 + uv. Slices are vertical: one business question, end to end, widened one at a time.

SLICE 1 is the thinnest possible whole spine, answering: "How many orders were placed per order
month and ship country?" One contract (Northwind Orders), one DAB entity, one transaction event,
one count measure, one bridge + peripheral + calendar, one marimo page.

ALREADY DECIDED (do not reopen; design within these):
- DuckDB, one file, platform behind one seam.
- dlt lands the whole source record as ONE json column; contracts drive strict unpacking.
- Landing is hive-partitioned one level: <table>/extracted_on=YYYY-MM-DD/<load>.parquet.
- _dlt_load_id is a unix-epoch string and is the single provenance fact: extracted_on is its date, and das__staged.extracted_at is to_timestamp(cast(_dlt_load_id AS DOUBLE)). DAB history is dated by extracted_at.
- USS declarations (events, measures) live in a sidecar dab/uss.yaml, not in model.yaml.
- Source is recorded once to fixtures and replayed everywhere; CI is offline.
- One shared dar__uss (deviation D-0001 already registered).
- Machinery is test-first; data checks land with the build that satisfies them.
- Each question is computed twice, from das__staged and from dar__uss, and the two must agree.
- One CLI: uv run adss ...
`

const ADR_SCHEMA = {
  type: 'object',
  properties: {
    title: { type: 'string', description: 'The decision as a full sentence in the present tense, the way a MADR title is written' },
    contextAndProblem: { type: 'string', description: '3-6 paragraphs. What makes this hard. Name the specific things about THIS system that make the obvious answer wrong.' },
    decisionDrivers: { type: 'array', items: { type: 'string' } },
    consideredOptions: { type: 'array', items: { type: 'string' }, description: 'At least 3, each a real option someone might choose' },
    recommendation: { type: 'string', description: 'Which option, named exactly as in consideredOptions' },
    argument: { type: 'string', description: 'Why that one. Several paragraphs. Argue the rejected options fairly and say what each would cost.' },
    consequences: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          kind: { type: 'string', enum: ['good', 'bad'] },
          text: { type: 'string' },
        },
        required: ['kind', 'text'],
      },
      description: 'At least two of kind bad, and they must be real',
    },
    confirmation: { type: 'string', description: 'Concretely: which test or check would prove this decision is actually implemented and still holds' },
    concreteShape: { type: 'string', description: 'The concrete artefact this implies: file names, YAML keys, column names, SQL shapes. Be specific enough to build from.' },
    groundedIn: { type: 'array', items: { type: 'string' }, description: 'Attributed evidence: "post-slug: quote" or "spike N observed: ..."' },
    notSettled: { type: 'array', items: { type: 'string' }, description: 'What neither the blog nor the spikes settle, that the implementer will have to choose' },
  },
  required: ['title', 'contextAndProblem', 'decisionDrivers', 'consideredOptions', 'recommendation', 'argument', 'consequences', 'confirmation', 'concreteShape', 'groundedIn', 'notSettled'],
}

const DECISIONS = [
  {
    key: 'adr-0001-domain-model',
    prompt: COMMON + `

DECISION 0001 - The machinery has its own typed domain model, and no business vocabulary appears in code.

The user asked for "the domain model, which does not restate dab/model.yaml", and chose: a typed
Python model of what the SYSTEM is made of - contract, pipeline, landing, staged view, mapping,
plan, stage, peripheral, bridge, question, destination - with no business word (no ORDER, no
CUSTOMER, no freight) anywhere under src/ or in test code.

Argue this decision. Cover:
- Why a machinery domain model is not a restatement of the business model, and what would make it become one.
- What "no business vocabulary in src/" actually buys, and how it is enforced (conventions.md has it as a hard rule - is a rule enough, or should something check it?).
- How test fixtures avoid business vocabulary while still testing real behaviour: neutral models held as DATA FILES rather than as names in code. What does a neutral fixture model look like?
- The typed shape itself: frozen dataclasses, StrEnum, discriminated unions of stage kinds - spike 4 confirmed "ty --error all" handles all of these with zero false positives. What are the actual types this system needs in slice 1, and which are premature?
- The cost: a machinery vocabulary is a second thing to learn, and an over-abstracted domain model is a named failure mode of model-driven platforms (see the-rise-of-model-driven-data-engineer on "overly generic models lacking domain specificity").

concreteShape must name the modules and the types for slice 1 ONLY. Resist modelling slices 2-6.`,
  },
  {
    key: 'adr-0002-uss',
    prompt: COMMON + `

DECISION 0002 - DAR is one generated Unified Star Schema: an event bridge, peripherals, one calendar, and a fixed column contract.

This is the most consequential record in the build: every question, every marimo page and every
future consumer is written against the columns this decision fixes, and will not survive them
changing. Read ${POSTS}/consumption-layer-generates-itself.txt IN FULL - it is the post that
describes the USS - plus Puppini's design as the blog relays it.

Argue this decision. You MUST resolve these three, and they are the whole difficulty:

1. FAN-OUT. The post says keys and measures "propagate downward" along many-to-one relationships.
   Keys can. Measures cannot: copying a parent's measure onto every child row multiplies it when
   summed. Work out precisely what propagates and what does not, and what test proves it.

2. HISTORY. daana keeps a version of every entity row (view_<E>_hist, dated eff_tmstp) and a
   current view (view_<E>). A question about something that HAPPENED and a question about a state
   as OBSERVED need different treatment. Decide how the bridge represents both.

3. WHERE THE RELATIONSHIP KEYS COME FROM. Spike 2 observed two things that constrain you hard:
   view_<entity>_with_rel carries NO relationship key columns despite its name, and
   <entity>_focal / <entity>_idfr are CREATED BUT NEVER POPULATED on DuckDB. Read those findings
   in ${SPIKES}. Decide what the generator reads, and justify it.

Then fix the column contract exactly: every column of _bridge, of a peripheral, and of _calendar,
with types. Name the convention for measure columns and key columns (conventions.md section 1.3
already fixes some of this - obey it, and say if it is wrong). Say what the generator emits as
files, and whether generated SQL is committed.

Also decide: how is a stage's event date chosen, and what happens to an entity row whose event
date is null (an order never shipped has no shipment event)?

concreteShape must give the literal column list of _bridge and _calendar with types, and one
worked example of the SQL for a single transaction stage, in the house SQL style.`,
  },
  {
    key: 'adr-0003-das',
    prompt: COMMON + `

DECISION 0003 - DAS: a data contract is documentation, schema and transformation in one artefact; ingestion is forgiving and unpacking is strict.

Read ${POSTS}/contract-driven-data-transformation.txt IN FULL - it is the post that defines the
contract - and the DAS constraints in ${BLOG}.

Argue this decision. Cover:
- The contract file: its exact keys and their meaning, adapted from the blog's shape (endpoints.source, endpoints.target, ownership, schema.primary_keys, schema.columns with source_path/target_name/type/mode/description) to an OData source landing into DuckDB rather than a Kafka/BigQuery one. What changes, and what must NOT change?
- The type vocabulary the contract may use, and the exact DuckDB expression each type generates when extracting from the json payload column. Spike 1 observed DuckDB json arrow operators: the double-arrow yields VARCHAR needing a cast, the single-arrow yields JSON. Give the full mapping table.
- What das__raw is and what das__staged is, as SQL. Spike 1 observed that read_parquet over a glob SILENTLY DROPS columns present only in later files without "union_by_name => true", and that hive partition columns come back VARCHAR without "hive_types". Both must be in the emitted SQL.
- THE OPEN ONE, and it matters most: DAS is append-only, so after two loads das__staged holds two rows per source record. Does das__staged expose ALL loads (a change log, one row per record per load) or the LATEST per key? The blog's contract declares BOTH a "historized" and a "latest" target model. Decide which das__staged is, and what the other one is called if it exists. Consider that DAB's ingestion strategy and its history depend entirely on this answer, and that spike 2 observed daana's FULL_LOG is idempotent against a multi-row-per-key source while FULL silently duplicates forever.
- Provenance: which columns DAS adds itself, and why each is needed to answer "where did this row come from and when".
- Recording and replay: what a fixture is, where it lives, and how "adss das ingest --offline" differs from a live run. What makes a recording honest?

concreteShape must give the full contract YAML for Northwind Orders, and the literal SQL of the
das__raw and das__staged views it generates, in the house SQL style.`,
  },
  {
    key: 'adr-0004-dab',
    prompt: COMMON + `

DECISION 0004 - daana-cli is the DAB engine: how the binary is obtained, and the mapping conventions that keep it honest.

Read ${POSTS}/design-of-analytical-systems.txt (the Ensemble Modeling sections) and the daana-cli
findings in ${SPIKES} - spike 2 exercised the real binary against DuckDB and found several things
that WILL bite. Also note the DMDL type vocabulary is exactly STRING, NUMBER, UNIT,
START_TIMESTAMP, END_TIMESTAMP and nothing else.

Argue this decision. Cover:
- Obtaining the binary. It is a 174MB git-LFS object on the "binaries" branch of mattiasthalen/ADSS-fable-POC (DO NOT read anything else from that repo). Options: vendor it into this repo via LFS, fetch it at build time, require a local path, or something else. CI has to work. Decide, and say how the version is pinned and verified - there is a .sha256 beside it.
- The mapping conventions. daana accepts several kinds of wrong mapping without complaint, so this is where the layer is kept honest. Derive a numbered rule set covering at minimum: which table a mapping may read; how the entity key is expressed; which ingestion_strategy and why (spike 2's FULL-duplicates finding is decisive and you must engage with it); what dates a version; what an attribute expression may and may not do; how a relationship id and its source_table are formed. Each rule needs a why and a severity.
- Single-writer discipline. Spike 2 found that ANY other open connection to the .duckdb file - including read-only - makes "daana-cli execute" fail with a misleading error claiming the framework is not installed. Decide how the build enforces one writer, and how a human operator learns what that error really means.
- What DAB objects DAR is allowed to read, given _focal and _idfr are empty on DuckDB.
- Whether model.yaml entity ids should be UPPER_SNAKE_CASE (conventions.md says so) given spike 2 found DuckDB PRESERVES that casing in object names (view_CUSTOMER, not view_customer) while PostgreSQL folds it. Does the convention survive contact with this? Argue it either way but decide.

concreteShape must give the model.yaml for a single ORDER entity, its mapping, workflow.yaml and
connections.yaml, as they will actually be written in slice 1.`,
  },
  {
    key: 'adr-0005-questions',
    prompt: COMMON + `

DECISION 0005 - A business question is the unit of delivery, and it carries the two queries that must agree on its answer.

Read ${POSTS}/anatomy-of-business-question.txt and ${POSTS}/from-business-question-to-prototype-in-hours.txt
IN FULL. They define what a well-formed question is (the Stage 0 to Stage 3 progression, the
"[AGGREGATION] of [MEASURE] per [DIMENSION]" form, the W framework, the named failure modes) and
the five-step methodology that produces one.

Argue this decision. Cover:
- The question file: its front matter and its sections. It must carry enough that the question is answerable without conversation - measure, dimensions, aggregation, time grain, persona, the W's, and the definitions it depends on. Design the front matter keys concretely.
- DEFINITIONS. dab/model.yaml is the only place the data is explained, so a question must REFERENCE definitions rather than restate them. Design that reference mechanism, and say what proves every reference resolves. What happens when a question needs a term the model does not define?
- THE TWO QUERIES. One computes the answer from das__staged, bypassing DAB and DAR entirely; the other from dar__uss. CI asserts they agree row for row. Work out honestly: what does this actually catch, what does it NOT catch, and what makes the das__staged query independent rather than a transcription of the other? Is there a risk the two are written to agree rather than to be right, and what reduces it?
- How a question relates to a slice, a branch, a commit and a marimo page.
- The lifecycle: a question can be validated, refined, or pivoted after the business sees the answer (step 5 of the methodology). How is that recorded? Does a question have a status?

concreteShape must give the complete question file for slice 1 - "How many orders were placed per
order month and ship country?" - with both queries written out against the schemas as this build
will actually have them, in the house SQL style.`,
  },
]

phase('Frame')

const BINDING_SCHEMA = {
  type: 'object',
  properties: {
    binds: {
      type: 'array',
      description: 'Rules and principles already in force that constrain slice 1, each with where it comes from and what it forbids',
      items: {
        type: 'object',
        properties: {
          rule: { type: 'string' },
          source: { type: 'string' },
          whatItForbidsHere: { type: 'string' },
        },
        required: ['rule', 'source', 'whatItForbidsHere'],
      },
    },
    tensions: {
      type: 'array',
      description: 'Places where slice 1 as described would break, strain, or sit awkwardly against an existing rule. Be adversarial: look for them.',
      items: {
        type: 'object',
        properties: {
          rule: { type: 'string' },
          howSliceOneStrainsIt: { type: 'string' },
          resolution: { type: 'string', description: 'clarify the rule / register a deviation / change the design - and which you recommend' },
        },
        required: ['rule', 'howSliceOneStrainsIt', 'resolution'],
      },
    },
    deviationReview: { type: 'string', description: 'D-0001 is open. Has its exit condition been met? Answer from the register itself.' },
    gaps: { type: 'array', items: { type: 'string' }, description: 'Rules the conventions document should have but does not, that slice 1 will otherwise have to invent' },
  },
  required: ['binds', 'tensions', 'deviationReview', 'gaps'],
}

const bindings = agent(
  COMMON + `

YOUR JOB IS DIFFERENT FROM THE OTHERS. You are not drafting a decision. You are the audit that
runs at the start of every slice: what is ALREADY in force, and where does this slice strain it?

Read ${REPO}/docs/blueprint.md, ${REPO}/docs/conventions.md, ${REPO}/docs/deviations.md and
${REPO}/docs/adr/0000-use-madr.md completely and carefully. Also read the repository as it stands
(${REPO}, excluding .venv) so you know what exists.

Then, for slice 1 as described above:
1. List every principle and hard rule that binds it, with what it forbids CONCRETELY here.
2. Be ADVERSARIAL about tensions. Look hard for places the slice as described would break or
   strain a rule. Some candidates to test, and do not stop at these: conventions.md requires
   UPPER_SNAKE_CASE DAB identifiers but DuckDB preserves that casing into object names; the
   blueprint says DAS does capture-and-persist ONLY while the contract layer casts types; the
   blueprint says DAR is generated and hand-edits are forbidden, yet generated SQL is to be
   committed; blueprint S4 requires per-data-point provenance and it is worth checking whether
   one json payload column per record actually satisfies that; conventions.md forbids business
   vocabulary in test code while the acceptance test compares two business queries.
3. Review D-0001 against its own exit condition.
4. Name rules the conventions document is MISSING that slice 1 will otherwise invent silently.

For each tension, say which of the three recourses in conventions.md section 9 applies, and
recommend one. Do not soften a real tension into a non-issue, and do not manufacture one.`,
  { label: 'binding-audit', phase: 'Frame', schema: BINDING_SCHEMA }
)

const drafts = parallel(DECISIONS.map(d => () =>
  agent(d.prompt, { label: d.key, phase: 'Frame', schema: ADR_SCHEMA })
))

const [audit, adrs] = await Promise.all([bindings, drafts])

log('framed ' + adrs.filter(Boolean).length + '/' + DECISIONS.length + ' decisions')

return { audit, adrs: adrs.filter(Boolean) }

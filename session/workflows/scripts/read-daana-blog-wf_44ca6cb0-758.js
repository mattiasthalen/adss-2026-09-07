export const meta = {
  name: 'read-daana-blog',
  description: 'Read every remaining post on blog.daana.dev, one agent per post, and extract what constrains the ADSS build',
  phases: [
    { title: 'Read', detail: 'one agent per post: fetch, read in full, extract mandates and concrete artifacts' },
    { title: 'Synthesize', detail: 'merge into a single constraint map and open-question list' },
  ],
}

const POSTS = [
  'the-architectural-blueprint',
  'consumption-layer-generates-itself',
  'integration-by-design-analytical-identifiers',
  'definitions-for-integration',
  'daana-cli-0-7-0-release',
  'the-rise-of-model-driven-data-engineer',
  'ai-assisted-data-engineering',
  'the-work-before-the-answer',
  'context-isnt-enough',
  'designing-for-agentic-experience',
  'stop-being-naming-convention-police',
  'why-we-built-daana',
  'meet-lars-fredholm-principal-data-engineer-at-daana',
  'meet-peiman-khorramshahi-cto-at-daana',
]

const EXTRACT = '/tmp/claude-0/-home-user-adss-2026-09-07/45a0041f-5559-570b-bd39-1d1517807233/scratchpad/blog'

const POST_SCHEMA = {
  type: 'object',
  properties: {
    slug: { type: 'string' },
    title: { type: 'string' },
    thesis: { type: 'string', description: 'The post argument in 2-4 sentences' },
    relevance: { type: 'string', enum: ['high', 'medium', 'low'], description: 'How much this post constrains how one would BUILD an ADSS platform (DAS/DAB/DAR layers)' },
    mandates: {
      type: 'array',
      description: 'Statements that constrain how an ADSS implementation must be built. Each must be traceable to the post, not inferred.',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string' },
          layer: { type: 'string', enum: ['DAS', 'DAB', 'DAR', 'cross-cutting', 'process', 'tooling'] },
          implication: { type: 'string', description: 'What this forces a builder to do or not do' },
        },
        required: ['claim', 'layer', 'implication'],
      },
    },
    artifacts: {
      type: 'array',
      description: 'Concrete named things: file formats, YAML keys, CLI commands, schema/table names, SQL patterns, column names, directory layouts, naming rules. Verbatim where possible.',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          kind: { type: 'string' },
          detail: { type: 'string' },
        },
        required: ['name', 'kind', 'detail'],
      },
    },
    quotes: { type: 'array', items: { type: 'string' }, description: 'Up to 8 verbatim sentences that a builder would need to obey' },
    openQuestions: { type: 'array', items: { type: 'string' }, description: 'Choices the post implies but does not settle' },
  },
  required: ['slug', 'title', 'thesis', 'relevance', 'mandates', 'artifacts', 'quotes', 'openQuestions'],
}

phase('Read')

const readOne = (slug) => agent(
  `Read ONE blog post in full and extract what it constrains about building an analytical data platform.

Fetch and convert it to text with exactly these commands:

  cd ${EXTRACT} && curl -sSL --max-time 60 "https://blog.daana.dev/blog/${slug}" -o "${slug}.html" && node extract.js "${slug}.html" > "${slug}.txt" && wc -c "${slug}.txt"

Then read ${EXTRACT}/${slug}.txt IN FULL with the Read tool (or cat). Do not skim, do not use WebFetch, do not summarize from the title. If the .txt is under 1500 characters the extraction failed — retry by running node extract.js on the raw html without the <article> isolation, or curl the page again.

Context you are serving: someone is about to BUILD the three-layer architecture this blog describes — DAS (data according to system), DAB (data according to business), DAR (data according to requirements) — using dlt for ingestion, a tool called daana-cli for the DAB focal model, and a generated Unified Star Schema for DAR. Your extraction is the only way this post reaches them. Be concrete and faithful.

Rules:
- mandates: only what the post actually says. Do not invent, do not generalize beyond the text.
- artifacts: anything NAMED — YAML keys, CLI commands and flags, schema names, table/column naming rules, SQL constructs, directory layouts, type mappings. Copy them verbatim. This is the highest-value field; be exhaustive.
- quotes: verbatim only, no paraphrase.
- openQuestions: places where the post says "you must decide X" or clearly leaves a choice open.
- If the post is an interview or company story with little build guidance, say so honestly via relevance:'low' and keep mandates short rather than padding.`,
  { label: slug, phase: 'Read', schema: POST_SCHEMA }
)

const results = (await parallel(POSTS.map(slug => () => readOne(slug)))).filter(Boolean)

log(`Read ${results.length}/${POSTS.length} posts`)

phase('Synthesize')

const synthesis = await agent(
  `Below are structured extractions from ${results.length} posts on blog.daana.dev, produced by agents that each read one post in full.

Four further posts were read separately and are NOT in this set (do not re-derive them, but you may reference them): "The Design of Analytical Data Storage Systems" (the three-layer DAS/DAB/DAR architecture + Ensemble Modeling), "From Business Question to Working Prototype in Hours" (the 5-step Agile Analytics methodology), "Contract-Driven Data Transformation" (YAML contracts generating staging SQL in DAS), "The Anatomy of a Business Question" (the [AGGREGATION] of [MEASURE] per [DIMENSION] form, stages 0-3).

<extractions>
${JSON.stringify(results, null, 2)}
</extractions>

Produce a single consolidated constraint map for someone about to build this architecture. Merge duplicates across posts, keep attribution (which slug said it), and resolve nothing you cannot resolve from the text — contradictions and gaps are the most valuable output.

Be rigorous about the difference between what the blog SAYS and what a builder would have to INVENT. The second list is what matters most.`,
  {
    label: 'constraint-map',
    phase: 'Synthesize',
    schema: {
      type: 'object',
      properties: {
        dasConstraints: { type: 'array', items: { type: 'string' } },
        dabConstraints: { type: 'array', items: { type: 'string' } },
        darConstraints: { type: 'array', items: { type: 'string' } },
        crossCutting: { type: 'array', items: { type: 'string' } },
        namingRules: { type: 'array', items: { type: 'string' } },
        namedArtifacts: {
          type: 'array',
          description: 'Every concrete named thing across all posts, deduped, with the slug it came from',
          items: {
            type: 'object',
            properties: { name: { type: 'string' }, kind: { type: 'string' }, detail: { type: 'string' }, source: { type: 'string' } },
            required: ['name', 'kind', 'detail', 'source'],
          },
        },
        contradictions: { type: 'array', items: { type: 'string' }, description: 'Places where posts disagree or a post disagrees with itself' },
        mustBeInvented: {
          type: 'array',
          description: 'Decisions a builder must make that the blog does NOT settle. These become questions to the user. Be exhaustive and specific.',
          items: {
            type: 'object',
            properties: {
              decision: { type: 'string' },
              whyBlogDoesNotSettleIt: { type: 'string' },
              plausibleOptions: { type: 'array', items: { type: 'string' } },
            },
            required: ['decision', 'whyBlogDoesNotSettleIt', 'plausibleOptions'],
          },
        },
        postsWorthReadingInFull: { type: 'array', items: { type: 'string' }, description: 'slugs whose detail did not survive summarization and that the orchestrator should read directly' },
      },
      required: ['dasConstraints', 'dabConstraints', 'darConstraints', 'crossCutting', 'namingRules', 'namedArtifacts', 'contradictions', 'mustBeInvented', 'postsWorthReadingInFull'],
    },
  }
)

return { perPost: results, synthesis }

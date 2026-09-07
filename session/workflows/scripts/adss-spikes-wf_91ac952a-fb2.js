export const meta = {
  name: 'adss-spikes',
  description: 'Four throwaway spikes answering what the interview could not: dlt raw landing, daana-cli on DuckDB, marimo as a destination, and the tooling gate',
  phases: [
    { title: 'Spike', detail: 'four independent probes, each in its own scratch directory, reporting findings only' },
  ],
}

const SCRATCH = '/tmp/claude-0/-home-user-adss-2026-09-07/45a0041f-5559-570b-bd39-1d1517807233/scratchpad/spikes'

const RULES = `
HARD RULES FOR THIS SPIKE
- You are a SPIKE. Your output is KNOWLEDGE, not code. Everything you write is thrown away.
- Work ONLY inside your own directory under ${SCRATCH}. Create it yourself.
- NEVER write, edit or create anything under /home/user/adss-2026-09-07. Never run git commands there.
- Do not install anything system-wide. Use \`uv\` for Python: \`uv init\`, \`uv add <pkg>\`, \`uv run <cmd>\` inside your own directory.
- Network works through a pre-configured proxy; plain https requests are fine.
- TIME-BOX: aim for roughly 20 focused tool calls. If something is not working by then, STOP and report exactly where it failed and what you saw. An honest "this does not work, here is the error" is a SUCCESSFUL spike. Do not grind.
- Report VERBATIM evidence: real command output, real file listings, real error text. Never describe what you expect; only what you observed. If you did not run it, say you did not run it.

CONTEXT
Someone is about to build a three-layer analytical platform in a fresh repo:
- DAS: dlt ingests a public OData API, lands parquet, unpacked into DuckDB as views. Schemas das__raw, das__staged.
- DAB: daana-cli (a Go binary) builds a focal/ensemble model. Schemas dab, dab__stage, dab__meta.
- DAR: a generated Puppini Unified Star Schema. Schema dar__uss.
- Destination: a marimo app reading dar__uss.
Everything lives in ONE DuckDB file. Python is managed with uv. Your findings decide the architecture, so precision matters more than success.

Already established (do not re-verify):
- daana-cli is at /home/user/adss-fable-poc/bin/linux-amd64/daana-cli and works.
- \`daana-cli install\` against a DuckDB connection profile works and creates schemas dab, dab__stage, dab__meta.
- A DuckDB connection profile looks like:
    connections:
      dev:
        type: duckdb
        database: ./warehouse.duckdb
        target_schema: dab
        stage_schema: dab__stage
        metadata_schema: dab__meta
- A full daana loop (install, deploy, execute) was proven against PostgreSQL and produced views view_<entity>, view_<entity>_hist, view_<entity>_with_rel, view_<src>_<rel>_<tgt>, and base tables <entity>_focal, <entity>_desc, <entity>_idfr, <src>_<tgt>_x.
- A working PostgreSQL example project (model.yaml, mappings/, workflow.yaml) is at
  /tmp/claude-0/-home-user-adss-2026-09-07/45a0041f-5559-570b-bd39-1d1517807233/scratchpad/cli-probe/quickstart-demo
  Copy from it rather than writing YAML from scratch. Read its files first.
`

const FINDING_SCHEMA = {
  type: 'object',
  properties: {
    spike: { type: 'string' },
    verdict: { type: 'string', enum: ['works', 'works-with-caveats', 'blocked', 'inconclusive'] },
    headline: { type: 'string', description: 'One sentence: the single most decision-relevant thing you learned' },
    findings: {
      type: 'array',
      description: 'Each an observed fact with the evidence that established it',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string' },
          evidence: { type: 'string', description: 'Verbatim command and its real output, trimmed to what matters' },
          confidence: { type: 'string', enum: ['observed', 'inferred', 'assumed'] },
        },
        required: ['claim', 'evidence', 'confidence'],
      },
    },
    recipe: { type: 'string', description: 'The minimal working recipe you established, as commands and file contents someone could reproduce. Empty if blocked.' },
    gotchas: { type: 'array', items: { type: 'string' }, description: 'Things that will waste a day if not known up front' },
    openQuestions: { type: 'array', items: { type: 'string' }, description: 'What you could not settle in the time-box' },
    versions: { type: 'array', items: { type: 'string' }, description: 'Exact versions of everything you installed' },
  },
  required: ['spike', 'verdict', 'headline', 'findings', 'recipe', 'gotchas', 'openQuestions', 'versions'],
}

const SPIKES = [
  {
    key: 'dlt-raw-landing',
    prompt: `${RULES}

SPIKE 1 — dlt landing a whole payload as parquet, read back through DuckDB views.

The architecture requires FORGIVING INGESTION and STRICT UNPACKING: dlt must NOT infer a schema and normalise the source into typed columns. Each source record must land as ONE row holding the record as a single JSON value, plus provenance columns, written to parquet, append-only, never updated.

Answer these, in order:
1. Does \`uv add dlt\` work here, and what version lands? Does it need extras for parquet/filesystem/duckdb?
2. Can a dlt resource be made to land ONE column containing the whole record as JSON, with normalisation NOT splitting it into columns? Try the approaches that exist (yielding a dict whose single field is a json string; a column hint of type json/text; disabling/limiting normalisation via max_table_nesting or a column schema) and report which actually works.
3. Land at least 50 real records from https://demodata.grapecity.com/northwind/odata/v1/Orders (the rows are under the "value" key; \`$count=true\` and \`$top\`/\`$skip\` work) into parquet on the local filesystem via the filesystem destination.
4. What does the resulting directory and parquet file actually look like? Show the file layout and \`DESCRIBE\` of the parquet from DuckDB.
5. Which dlt-added metadata columns appear (_dlt_load_id, _dlt_id, others)? Are they enough to answer "which load, from where, when" for a single row, or must the pipeline add its own provenance columns? Recommend the exact provenance columns to add.
6. Confirm write_disposition="append" leaves earlier files intact across two runs. Run it TWICE and show both loads present.
7. From DuckDB (\`uv add duckdb\`), create a view over the parquet glob and then a second view that extracts and casts a few typed columns out of the JSON column. Show the SQL that works and the query results. Note the exact JSON functions DuckDB wants.

Report the minimal working recipe verbatim.`,
  },
  {
    key: 'daana-on-duckdb',
    prompt: `${RULES}

SPIKE 2 — daana-cli deploy + execute against DuckDB, reading VIEWS as mapping sources, and what historization it produces.

This is the highest-risk spike: the whole DAB layer depends on it.

Setup: make your own directory, put a DuckDB connections profile in it (shape given above), and copy model.yaml, mappings/ and workflow.yaml from the PostgreSQL example project named above. Then:

1. Create a DuckDB file yourself first (\`uv add duckdb\`), and inside it create a schema named das__staged containing the source data the mappings expect. IMPORTANT: create them as VIEWS, not tables — DAB must read a view. The PostgreSQL example's mappings read stage.customers, stage.customer_addresses, stage.loyalty_memberships and stage.sales_orders; the data SQL is at /tmp/claude-0/-home-user-adss-2026-09-07/45a0041f-5559-570b-bd39-1d1517807233/scratchpad/cli-probe/quickstart-demo/data/ but it is PostgreSQL DDL, so it may be quicker to invent a handful of equivalent rows yourself with matching column names than to port it. Either is fine — say which you did.
2. Point the mappings at das__staged.<table> instead of stage.<table>, and set connection to your duckdb profile name.
3. Run \`daana-cli install\`, \`daana-cli check workflow\`, \`daana-cli deploy\`, \`daana-cli execute\` (all with --no-tui). Report the OUTCOME OF EACH, including any failure verbatim.
4. If it works: list every object daana created in dab, dab__stage and dab__meta, and show \`DESCRIBE\` plus a few rows of view_<entity>, view_<entity>_hist and the relationship view. Are the names and shapes IDENTICAL to the PostgreSQL run described above, or do they differ on DuckDB?
5. THE HISTORIZATION QUESTION. The real build will date every DAB version by WHEN DAS OBSERVED THE ROW — a load timestamp column on the staged view — using \`entity_effective_timestamp_expression: <that column>\`. Test this: give your staged views a load-timestamp column, map it as the effective timestamp, execute; then CHANGE one attribute value for one key AND give it a later load timestamp, execute again. Report exactly what view_<entity> and view_<entity>_hist contain afterwards. Does the history keep both versions? Does the current view show the new one?
6. Do this for BOTH \`ingestion_strategy: FULL\` and \`ingestion_strategy: FULL_LOG\` if the time-box allows — the difference between them on a re-load is a decision the build depends on. If you only have time for one, do FULL and say so.
7. Note anything DuckDB-specific: identifier casing and quoting, whether daana needs the file to not be open by another process, concurrency errors, whether execute is re-runnable.

This spike's findings matter more than its tidiness. Report failures in full.`,
  },
  {
    key: 'marimo-destination',
    prompt: `${RULES}

SPIKE 3 — marimo as the destination: reading DuckDB, exporting, and being screenshotted headless.

Each slice ends in a marimo app that presents a business question and its answer, read from a DuckDB warehouse. Acceptance happens by screenshots posted to a pull request, and the user also wants to run the app themselves.

1. Does \`uv add marimo\` work, and what version? What does it pull in?
2. Make a tiny DuckDB file with one table of a few rows (\`uv add duckdb\`). Write a marimo notebook that reads it and shows: a title, the question as prose, a table of the answer, and a chart. Which plotting library works most cleanly inside marimo without extra setup — altair, plotly, matplotlib? Report what you actually got working.
3. Can the notebook be run as an APP (\`marimo run\`) rather than an editable notebook, headless, on a fixed port with no browser opening? Show the exact command and that it serves.
4. EXPORT: what export formats does this version support (\`marimo export --help\`)? Get an actual export to static HTML working and report the resulting file SIZE. Does the export include the rendered chart and table output, or only the code? Try the flags that control that.
5. SCREENSHOTS — this is the acceptance mechanism, so establish it properly. Chromium is at /opt/pw-browsers/chromium with PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers and PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 already set; do NOT run \`playwright install\`. Using \`uv add playwright\`, drive headless Chromium to open the running marimo app (or the exported HTML) and save a PNG. Confirm the PNG is a real rendering of the app — check its byte size and dimensions, and say how you know it is not blank. Report the exact script that worked.
6. Note the gotchas: does marimo need a writable config dir, does it complain without a TTY, does the app need a moment before the chart renders, does the export need the notebook to have been executed first?

The deliverable is a reproducible recipe for "build the app, run it, screenshot it, export it".`,
  },
  {
    key: 'tooling-gate',
    prompt: `${RULES}

SPIKE 4 — the quality gate, on the exact artefacts this repository will contain.

The repository will be gated by ruff, a strict type checker, sqlfluff over ALL SQL including generated SQL, yamllint, and pytest, run by pre-commit locally and in CI. Establish that each of these actually works on the shapes involved, and find where they fight.

1. \`uv init\` a project and \`uv add --dev ruff sqlfluff yamllint pytest pre-commit\` plus a type checker. For the type checker, try \`ty\` first (Astral's, likely fastest and newest); if it is not viable report why and fall back to mypy. Report versions of everything.
2. RUFF: confirm lint and format run. Nothing subtle expected — just confirm and report the version.
3. TYPE CHECKER — the important part. The build has a typed domain model of the machinery: frozen dataclasses with enums, tuples of nested dataclasses, and a discriminated union of stage kinds. Write a ~60-line module in that shape, plus one deliberate type error, and confirm the checker in STRICT mode flags the error and passes when fixed. Report the exact configuration needed and any friction with frozen dataclasses or unions.
4. SQLFLUFF — the highest-risk of these. The repository will generate DuckDB SQL. Determine: does this sqlfluff version have a \`duckdb\` dialect (\`uv run sqlfluff dialects\`)? If not, which dialect is the least-wrong stand-in? Then lint a piece of SQL in the style this build will emit — a UNION ALL of several SELECT branches, each branch aliasing every column of one fixed column list with AS, \`cast(x AS DECIMAL(28, 8))\`, lower-case function names, UPPER-case keywords, double-quoted mixed-case identifiers crossing over from the business layer, a \`QUALIFY row_number() OVER (...)\` clause, and a quoted reserved word used as a table name (\`"order"\`). Report EVERY rule that fires, and for each say whether the right fix is to change the SQL the generator emits or to configure the rule off — with the reason.
5. YAMLLINT: lint a YAML file in the shape of a data contract — nested block mappings, some short flow mappings like \`{source_path: OrderId, target_name: order_id, type: INTEGER}\`, lines up to ~150 chars. Report which default rules fire and the minimal sane configuration.
6. PRE-COMMIT: get a .pre-commit-config.yaml running all of the above locally with \`uv run pre-commit run --all-files\`. Report whether the hooks work offline / from local venv rather than fetching remote repos, since CI determinism matters.

The deliverable is: exact versions, exact config files, and the list of sqlfluff rules that will fight generated SQL.`,
  },
]

phase('Spike')

const results = (await parallel(SPIKES.map(s => () =>
  agent(s.prompt, { label: s.key, phase: 'Spike', schema: FINDING_SCHEMA })
))).filter(Boolean)

log(`${results.length}/${SPIKES.length} spikes reported`)

return results

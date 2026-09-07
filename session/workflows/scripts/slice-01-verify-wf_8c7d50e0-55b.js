export const meta = {
  name: 'slice-01-verify',
  description: 'Verify slice 1 from four independent angles: layering, conventions, an independent recomputation, and test quality',
  phases: [
    { title: 'Verify', detail: 'four lenses, each blind to the others' },
  ],
}

const REPO = '/home/user/adss-2026-09-07'

const COMMON = `
You are one lens of a verification pass over a completed slice of work. Four of you run, each
blind to the others. Report findings; do not fix anything.

HARD RULES
- Do NOT write, edit or create any file in ${REPO}. Do not run git commands that change state
  (no commit, no checkout, no reset, no add). Reading, and running the project's own read-only
  commands, is fine.
- You may run: uv run pytest, uv run adss check, uv run ruff check, uv run sqlfluff lint,
  and any read-only DuckDB query against ${REPO}/warehouse.duckdb (open it read_only=True).
- Ground every finding in something you actually read or ran. Quote the file and line, or the
  command and its output. A finding you cannot ground is not a finding.
- Severity honestly: "blocking" means the slice should not be accepted as it stands.
  "worth fixing" means it should be fixed but does not block. "note" is an observation.
- Report NOTHING rather than padding. An empty list from a lens that genuinely found nothing
  is the most useful possible result. Do not manufacture findings to look thorough.

THE REPOSITORY
${REPO}. An analytical data storage system in three layers:
- DAS (schemas das__raw, das__staged): dlt lands whole source records as one JSON column into
  hive-partitioned parquet; contracts generate typed views over it.
- DAB (dab, dab__stage, dab__meta): a focal/ensemble model built by a vendored engine binary.
  dab/model.yaml is the only place the data is explained.
- DAR (dar__uss): a generated Unified Star Schema -- one event bridge, one peripheral per
  entity, one calendar.
- destinations/app.py: a marimo page reading dar__uss only.

Slice 1 answers: "How many orders were placed per order month and destination country?"

READ THESE FIRST: ${REPO}/docs/blueprint.md, ${REPO}/docs/conventions.md,
${REPO}/docs/deviations.md, and ${REPO}/docs/adr/*.md. They are the standard you judge against.

The slice is every commit on the current branch after the one titled
"chore(repo): scaffold the repository, its principles and its gate".
Use: git -C ${REPO} log --oneline and git -C ${REPO} diff <scaffold-sha>..HEAD --stat
`

const FINDINGS = {
  type: 'object',
  properties: {
    lens: { type: 'string' },
    verdict: { type: 'string', enum: ['accept', 'accept-with-fixes', 'do-not-accept'] },
    summary: { type: 'string', description: 'Two or three sentences. What you checked and what you concluded.' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['blocking', 'worth fixing', 'note'] },
          where: { type: 'string', description: 'file:line, or the command that showed it' },
          finding: { type: 'string' },
          evidence: { type: 'string', description: 'What you actually read or ran, quoted' },
          fix: { type: 'string' },
        },
        required: ['severity', 'where', 'finding', 'evidence', 'fix'],
      },
    },
    checkedAndFound: { type: 'array', items: { type: 'string' }, description: 'Things you specifically looked for and did NOT find wrong. This is how the next reader knows what this lens covered.' },
  },
  required: ['lens', 'verdict', 'summary', 'findings', 'checkedAndFound'],
}

const LENSES = [
  {
    key: 'layering',
    prompt: COMMON + `

LENS 1 of 4 -- LAYERING. Does anything read across a boundary it should not?

The three flow rules are absolutes in docs/blueprint.md:
- F1 analytical usage reads only DAR
- F2 DAR reads only DAB
- F3 DAB reads only DAS
and each movement does exactly ONE job: ingest, integrate, specialise.

Check, concretely and by reading the actual artefacts:
1. Does destinations/app.py touch anything but dar__uss? Grep it for das, dab, the lake, the
   contracts. Note that reading the QUESTION FILE is legitimate; reading das__staged is not.
2. Does anything in dar/uss/*.sql reference das__ or the lake? Does the USS generator
   (src/adss/uss.py) read anything but dab.view_*?
3. Do dab/mappings/*.yaml read only das__staged objects?
4. Does anything in DAS interpret rather than record? Look at das/sql/orders.sql and
   src/adss/das.py: is there a filter, a default, a coalesce, a business rule, a rename that
   is not mechanical?
5. Does any layer's code know about another layer's vocabulary in a way that couples them?
6. THE INTERESTING ONE: the acceptance check computes each question twice, once from
   das__staged. Read docs/adr/0005 and the tension it acknowledges. Is the way it is actually
   implemented consistent with what that record claims? Does the control query genuinely
   avoid the layers it checks?
7. Read src/adss/checks.py. Does it read across boundaries in a way the blueprint forbids, or
   is a conformance check legitimately outside F1? Say which and why.`,
  },
  {
    key: 'conventions',
    prompt: COMMON + `

LENS 2 of 4 -- CONVENTIONS. Does the slice obey the rules this repository set itself?

docs/conventions.md is the standard. Every hard rule in it is in scope. Check especially,
and by actually reading the files rather than assuming:

1. Section 1.2: "No source name appears anywhere in dab/model.yaml -- not in an id, not in a
   name, not in a definition, not in a description." Read dab/model.yaml against the source's
   own field names in das/contracts/orders.yaml. Is the rule kept? Be strict: the source
   calls something ShipCountry; does anything in DAB echo it?
2. Section 1.4: the seven mapping rules, against dab/mappings/*.yaml.
3. Section 2: measure naming, <descriptor>_<entities>_<unit>, entity PLURAL, no scope or
   aggregation words. Check dab/uss.yaml and the generated column names.
4. Section 5: "No data vocabulary anywhere under src/ or in test code." This is the one most
   likely to be violated. Grep src/ and tests/ for any business word -- order, country,
   freight, ship, customer, northwind. Distinguish a genuine violation from a machinery word
   that happens to collide. Check tests/fixtures/ too: are the fixtures neutral?
5. Section 1.1: DAS keeps the source's words; the layer's own columns are named for what they
   record; no loader vocabulary crosses into das__staged. Check das/sql/orders.sql.
6. Section 1.3: DAR naming, structural columns with a leading underscore, reserved words
   quoted rather than abbreviated around.
7. Section 7: conventional commits with a scope from the allowed list; an ADR before the code
   it decides. Check the actual git log.
8. Is anything in docs/ now stale -- describing something that was changed later in the
   slice? Check the README and the ADRs against what the code actually does.`,
  },
  {
    key: 'recomputation',
    prompt: COMMON + `

LENS 3 of 4 -- INDEPENDENT RECOMPUTATION. Is the number right?

This is the most valuable lens and the least like the others. Do NOT use any of this
repository's code. Do not import adss. Do not read its SQL and re-run it.

1. Read the RAW RECORDED PAYLOADS at ${REPO}/das/fixtures/orders/page-*.json. These are the
   response bodies exactly as the source returned them.
2. In plain Python (json + collections, or pandas if you prefer -- your own script in /tmp,
   NOT in the repository), compute from those files: for every order that has an OrderDate,
   the count of orders grouped by the calendar month of OrderDate and by ShipCountry.
3. Now read what the system produced. Open ${REPO}/warehouse.duckdb READ ONLY and run the
   question's uss.sql from
   ${REPO}/docs/questions/01-orders-per-month-and-destination-country/uss.sql
4. Compare, row for row. Report ANY difference: a missing row, an extra row, a different
   count, a different month boundary, a differently spelled country.
5. Also verify the totals independently: how many orders are in the fixtures? How many have a
   null OrderDate? How many distinct countries? Does the page's headline number (830) match
   what you counted yourself?
6. Look for what a row-for-row match would NOT catch. Is there an order in the fixtures that
   is absent from both? A duplicate in the fixtures that both silently collapse? Check whether
   any OrderId appears more than once across the pages, and whether the pagination could have
   dropped or duplicated a record at a page boundary (top=100, nine pages, 830 records --
   verify that arithmetic against the actual files).
7. Report the numbers you computed, not just whether they matched.`,
  },
  {
    key: 'tests',
    prompt: COMMON + `

LENS 4 of 4 -- TEST QUALITY. Would these tests fail if the code were wrong?

A test that has only ever been seen to pass is not evidence. Your job is to find the ones
that would pass no matter what.

1. Read every file in ${REPO}/tests/. For each test, ask: what change to src/ would make this
   fail? If you cannot name one, that is a finding.
2. MUTATE AND SEE. This is the core of this lens. Pick at least SIX consequential behaviours
   and break them one at a time -- IN A COPY of the repository under /tmp, never in ${REPO}
   itself (cp -r, excluding .venv and warehouse.duckdb and das/lake, then run the suite there
   with the repo's venv: ${REPO}/.venv/bin/python -m pytest). Suggested mutations, and add
   your own:
   - remove "union_by_name => true" from the raw view
   - change FULL_LOG to FULL in the mapping rule checker's required value
   - make a non-owning branch of the bridge emit 0 instead of a typed NULL
   - drop the "IS NOT NULL" filter from the event stage
   - reorder two columns in the bridge column contract
   - make the contract reader accept a renamed target_name
   - make the question checker skip the "control query must not mention dar__uss" rule
   Report, for each: did the suite go red? If a mutation left it green, that is a hole and it
   is the most important thing you will find.
3. Check for the forbidden shapes: pytest.skip, imperative xfail, a test asserting something
   trivially true, a test whose assertion is weaker than its name claims.
4. Are the fixtures genuinely neutral, or do they encode the same assumptions as the code
   under test?
5. docs/conventions.md section 6 names two suites, tests/ and checks/. Is the split real, or
   does something in tests/ depend on a built warehouse (and so would fail in a fresh clone)?
   Verify by running the suite in your copy WITHOUT a warehouse.duckdb present.`,
  },
]

phase('Verify')

const results = (await parallel(LENSES.map(lens => () =>
  agent(lens.prompt, { label: lens.key, phase: 'Verify', schema: FINDINGS })
))).filter(Boolean)

log(`${results.length}/${LENSES.length} lenses reported`)

return results

export const meta = {
  name: 'verify-slice-04',
  description: 'Six independent lenses over slice 4 of the ADSS build, then adversarial verification of every finding',
  phases: [{ title: 'Review', detail: 'Six lenses read the slice diff independently' }, { title: 'Verify', detail: 'Each finding is attacked adversarially and scored' }],
}

const BASE = 'claude/adss-slice-03-shipped-orders-and-days-to-ship'
const HEAD = 'claude/adss-slice-04-revenue-per-order-month'

const CONTEXT = `
You are reviewing ONE SLICE of a build in the repository at /home/user/adss-2026-09-07.
The slice is the range ${BASE}..${HEAD}. Use \`git diff ${BASE}..${HEAD}\` and
\`git log ${BASE}..${HEAD}\` to see exactly what changed. Read whatever else you need.

The system is an "Analytical Data Storage System" with three layers, one direction of flow:
  DAS (das/, schemas das__raw + das__staged) -> DAB (dab/, schemas dab, dab__stage, dab__meta)
  -> DAR (dar/, schema dar__uss) -> destinations/ (a marimo page).
Flow rules, absolute: analytical usage reads ONLY dar__uss; dar reads only dab; dab reads only das.

Slice 4 adds a third entity (ORDER_LINE) at a FINER GRAIN than the order, a derived measure
(REVENUE), an inherited event date, a composed composite key, and the fan-out proof.

Ground rules for your review:
- Be specific. A finding names a file and a line and says what breaks and when.
- Do not report style preferences, or things the repository's own tools already enforce
  (ruff, ty, sqlfluff, yamllint, pytest all pass on this head -- verify that if you like).
- Do not report anything that is already written down as a known limitation in
  docs/adr/, docs/deviations.md, or the question documents. Read them before reporting.
- Prefer ONE real finding to five speculative ones. An empty report is a valid report.
`

const LENSES = [
  {
    key: 'layering',
    prompt: `${CONTEXT}

YOUR LENS: LAYERING. Does anything in this slice read across a boundary it must not?

Check every new or changed SQL string, generated file, mapping, contract, question query,
page cell and Python module for: a DAR artefact reading das__ or dab; a destination reading
anything but dar__uss; a question's control query (staged.sql) mentioning dab or dar__uss;
a source name (a column or table name from the Northwind OData service) appearing anywhere
under src/ or in dab/model.yaml or dab/uss.yaml -- those two are supposed to contain NO
source word at all; machinery under src/ naming any business concept.

Report only real crossings, with the file and line.`,
  },
  {
    key: 'conventions',
    prompt: `${CONTEXT}

YOUR LENS: CONVENTIONS. Read docs/conventions.md in full, then check this slice against it.

Pay particular attention to sections on naming (measures, events, entities), the mapping
rules M1-M7, the question format, where definitions may live (dab/model.yaml is the ONLY
place the data is explained -- nothing else may restate a definition), and the rule that a
tool's config IS the rule where a tool can check one.

Also check docs/adr/README.md's rule about how ADRs may be edited, and whether the ADRs
added or edited in this slice obey it.

Report only actual violations, with the file, the line, and the section of conventions.md.`,
  },
  {
    key: 'recompute',
    prompt: `${CONTEXT}

YOUR LENS: INDEPENDENT RECOMPUTATION. Do not trust any of this repository's code.

The fourth question claims: revenue per order month, 23 months, total 1,265,793.0395,
from 2,155 order lines across 830 orders. See docs/questions/04-revenue-per-order-month/.

Recompute it YOURSELF from the recorded source payloads under das/fixtures/ (JSON pages
from an OData service) using plain Python -- json, collections, decimal. Do NOT import
anything from src/adss, do NOT read the duckdb warehouse, do NOT run any adss command,
and do NOT reuse the SQL in the question. Work out the revenue arithmetic from
dab/model.yaml's definition of ORDER_LINE.REVENUE and the contract in
das/contracts/order_details.yaml.

Then compare your per-month numbers to docs/questions/04-revenue-per-order-month/uss.sql's
claimed answer, which you can read out of the committed question.md and the screenshot's
table. Report ANY disagreement, with your number and theirs. If they agree exactly, say so
and show the first three and the last month.

Also verify independently: the claim in ADR 0012 that summing the order peripheral's
freight_charge over the bridge joined on order_key gives 207,306.10 where the true total is
64,942.69. You can compute the true freight total from the fixtures. For the trap number you
may reason about it arithmetically (freight per order, times the number of lines on that
order) rather than running SQL.`,
  },
  {
    key: 'tests',
    prompt: `${CONTEXT}

YOUR LENS: TEST QUALITY. Would these tests fail if the implementation were broken?

Focus on what this slice added: tests/test_fan_out.py, tests/test_measure_checks.py,
tests/test_composed_key_check.py, the new tests in tests/test_questions.py and
tests/test_uss.py and tests/test_generated_sql_lints.py, and the generated checks under
checks/.

For each, work out a concrete mutation of the code under test that would make it wrong in a
way a user would notice, and decide whether the test would go red. You may actually apply a
mutation, run \`uv run pytest -q\`, and revert it -- that is the strongest evidence and is
encouraged. ALWAYS revert any mutation you apply; leave the working tree clean and confirm
with \`git status\`.

Report every test that would survive a real defect, naming the mutation that survives.
Also report any ADR "Confirmation" section in docs/adr/ that claims a check which does not
exist, or which exists but could not fail for the reason stated. That has happened in this
repository before and is treated as a serious defect.`,
  },
  {
    key: 'correctness',
    prompt: `${CONTEXT}

YOUR LENS: ORDINARY CORRECTNESS. Review the diff as a careful engineer reviewing a pull
request. Bugs, edge cases, wrong logic, things that work on this data and not on the next.

Particular things worth attacking in this slice:
- src/adss/uss.py: the inherited-date CTE and the stage CTE. What happens with two edges to
  the same entity, an event dated by an entity two hops away, a parent with no history row,
  a pair whose eff_tmstp is after the child's observation time?
- src/adss/question.py: the new parse-tree aggregate refusal. What legitimate query does it
  wrongly refuse? What illegitimate one does it accept? What happens with a CTE, a set
  operation, a lateral join, a macro?
- src/adss/checks.py: measure_checks and composed_key_checks. What contract or mapping shape
  makes them emit SQL that does not run, or a check that cannot fail?
- src/adss/das.py: the ROW() change to the composite key check.
- The interaction between the two writers into checks/ and their sweeps: can one command
  still delete a file the other generates?

Report real defects with the file, the line, and the input that triggers them.`,
  },
  {
    key: 'honesty',
    prompt: `${CONTEXT}

YOUR LENS: HONESTY OF THE RECORD. This repository's documents make load-bearing claims.

Check every claim added or changed in this slice against the code and the data:
- docs/adr/0009 through 0012, especially their Confirmation sections.
- docs/deviations.md, entry D-0001 and the Review section.
- docs/questions/04-revenue-per-order-month/question.md -- every number in it.
- docs/questions/README.md.
- .claude/skills/*/SKILL.md -- the claims added this slice.
- The commit messages in \`git log ${BASE}..${HEAD}\`.

A claim is dishonest if it is false, if it is true but implies something false, or if it
describes a check that does not exist or cannot fail. Numbers are checkable: check them
(you may run \`uv run adss check\` and query the warehouse at the path Project.discover()
reports, read-only).

Report each false or misleading claim with the exact sentence and what is actually true.`,
  },
]

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          file: { type: 'string' },
          line: { type: 'number' },
          detail: { type: 'string' },
          why_it_matters: { type: 'string' },
        },
        required: ['title', 'file', 'detail', 'why_it_matters'],
      },
    },
    summary: { type: 'string' },
  },
  required: ['findings', 'summary'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    isReal: { type: 'boolean' },
    confidence: { type: 'number' },
    reasoning: { type: 'string' },
    suggested_fix: { type: 'string' },
  },
  required: ['isReal', 'confidence', 'reasoning'],
}

const results = await pipeline(
  LENSES,
  (lens) => agent(lens.prompt, { label: `review:${lens.key}`, phase: 'Review', schema: FINDINGS_SCHEMA }),
  (review, lens) =>
    parallel(
      (review.findings || []).map((f) => () =>
        agent(
          `You are ADVERSARIALLY VERIFYING one review finding about the repository at
/home/user/adss-2026-09-07, on branch ${HEAD}.

FINDING: ${f.title}
FILE: ${f.file}${f.line ? ':' + f.line : ''}
DETAIL: ${f.detail}
WHY IT MATTERS: ${f.why_it_matters}

Your job is to try to DESTROY this finding. Read the actual code. Run the actual command or
test if that settles it. Look for the reason the finding is wrong: a check elsewhere that
already catches it, a documented decision that accepts it on purpose (docs/adr/,
docs/deviations.md, docs/conventions.md, the question documents), an invariant that makes the
bad input impossible, or a simple misreading.

Do NOT modify any file. If you must experiment, copy to a scratch directory.

Return isReal=true ONLY if the defect genuinely exists in this head and is not already
recorded as a known limitation. confidence is 0-10: how sure you are, having tried to break
your own conclusion. If isReal, give the smallest correct fix.`,
          { label: `verify:${lens.key}:${(f.title || '').slice(0, 40)}`, phase: 'Verify', schema: VERDICT_SCHEMA }
        ).then((v) => ({ lens: lens.key, ...f, verdict: v }))
      )
    )
)

const all = results.flat().filter(Boolean)
const confirmed = all.filter((f) => f.verdict?.isReal && (f.verdict?.confidence ?? 0) >= 7)
const dropped = all.filter((f) => !(f.verdict?.isReal && (f.verdict?.confidence ?? 0) >= 7))

return {
  confirmed: confirmed.sort((a, b) => (b.verdict.confidence - a.verdict.confidence)),
  dropped_count: dropped.length,
  dropped_titles: dropped.map((f) => `${f.lens}: ${f.title} (real=${f.verdict?.isReal}, conf=${f.verdict?.confidence})`),
}

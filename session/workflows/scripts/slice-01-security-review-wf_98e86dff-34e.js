export const meta = {
  name: 'slice-01-security-review',
  description: 'Security review of the slice-1 diff: find, then adversarially filter for false positives',
  phases: [
    { title: 'Find', detail: 'three lenses over the new attack surface' },
    { title: 'Filter', detail: 'one adversarial filter per candidate finding' },
  ],
}

const REPO = '/home/user/adss-2026-09-07'

const CONTEXT = `
THE CODE UNDER REVIEW: ${REPO}, on branch claude/adss-slice-02-freight-per-customer-country-and-quarter.
Everything from commit eaea5fd to HEAD is new in this change. Diff it with:
  git -C ${REPO} diff eaea5fd..HEAD --stat
  git -C ${REPO} diff eaea5fd..HEAD -- <path>

WHAT IT IS: an analytical data-platform build tool. A CLI (\`adss\`) that reads YAML data
contracts, fetches records over HTTP from a public OData service, lands them as parquet,
generates SQL, invokes a vendored Go binary as a subprocess, builds a local DuckDB file, and
renders a local marimo page. It is a developer/CI tool, not a network service. It has no
users, no sessions, no authentication and no inbound requests.

IGNORE almost all of the diff. uv.lock, das/fixtures/*.json (recorded response bodies),
docs/**, *.md, tests/** and dar/uss/*.sql carry no new attack surface. The real surface is:
  src/adss/*.py          -- the CLI and its machinery
  destinations/app.py    -- the marimo page
  .github/workflows/*    -- CI
  bin/linux-amd64/*      -- a vendored 174 MB binary and its checksum
  .pre-commit-config.yaml, pyproject.toml

THE TRUST MODEL, which you must reason about rather than assume:
Contracts (das/contracts/*.yaml), the model (dab/model.yaml), the sidecar (dab/uss.yaml),
mappings and question SQL are REPOSITORY CONTENT, reviewed in pull requests. Anyone who can
change them can already run arbitrary code via CI. So "a malicious contract could inject SQL"
is generally NOT a real finding here -- say so explicitly if you considered and rejected it.
What WOULD be real: something that turns EXTERNAL data (an HTTP response body from the OData
service, a recorded fixture, a file path from outside the repo) into code execution, a
subprocess argument, a file write outside the intended tree, or a request to an attacker-chosen
host or protocol.
`

const RULES = `
HARD RULES
- Read only. Do NOT write, edit or create any file. Do not run git commands that change state.
- Only flag what you are >80% confident is concretely exploitable in THIS system's trust model.
- Do NOT report: denial of service, resource exhaustion, secrets-at-rest, rate limiting,
  outdated dependencies, findings in tests or documentation, missing hardening, theoretical
  races, log spoofing, regex injection, or SSRF that controls only a URL path.
- Environment variables and CLI flags are TRUSTED. An attack requiring control of one is invalid.
- If you find nothing real, say so. An empty list from an honest look is the correct answer and
  is far more useful than a padded one.
`

const FINDING = {
  type: 'object',
  properties: {
    lens: { type: 'string' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          file: { type: 'string' },
          line: { type: 'integer' },
          severity: { type: 'string', enum: ['HIGH', 'MEDIUM', 'LOW'] },
          category: { type: 'string' },
          description: { type: 'string' },
          exploitScenario: { type: 'string', description: 'A concrete path from an attacker-controlled input to the impact. If you cannot write one, it is not a finding.' },
          recommendation: { type: 'string' },
          confidence: { type: 'integer', description: '1-10' },
        },
        required: ['title', 'file', 'line', 'severity', 'category', 'description', 'exploitScenario', 'recommendation', 'confidence'],
      },
    },
    consideredAndRejected: { type: 'array', items: { type: 'string' }, description: 'Patterns you looked at and decided were not findings, with why. This is how the next reader knows what was covered.' },
  },
  required: ['lens', 'findings', 'consideredAndRejected'],
}

phase('Find')

const LENSES = [
  {
    key: 'injection-and-execution',
    focus: `Injection and code execution. Trace every path from data this system does not
control to something that executes or is interpreted:
- subprocess.run in src/adss/engine.py and src/adss/destination.py: where does every argument
  come from? Can any be attacker-influenced? Is shell=True used anywhere?
- src/adss/source.py: urllib.request.urlopen on a URL built from the contract. Can the HOST or
  the PROTOCOL be controlled by anything external (a redirect, a response body)? Path-only
  control is explicitly not a finding.
- The recorded fixture replay: replay() reads a manifest and returns file bytes keyed by URL.
  Is there a path-traversal there -- can a manifest value escape the fixtures directory?
- yaml.safe_load vs yaml.load anywhere.
- SQL generation in src/adss/das.py and src/adss/uss.py: is any value that reaches emitted SQL
  sourced from OUTSIDE the repository (a response body, a filename, an environment value)?
- src/adss/platform.py install(): it splits a string and executes each part. What can reach it?
- src/adss/sqlformat.py: sqlfluff.fix on generated SQL.
- Any eval, exec, pickle, or dynamic import.`,
  },
  {
    key: 'supply-chain-and-ci',
    focus: `Supply chain and CI. This change vendors a 174 MB binary and adds two GitHub Actions
workflows:
- bin/linux-amd64/daana-cli, its .sha256 and .version, and src/adss/engine.py's verify(). Is the
  checksum actually enforced before execution on every path? Can verify() be bypassed? Is there
  a TOCTOU between verifying and executing that is CONCRETELY exploitable here?
- .github/workflows/ci.yml: read every step. The cache keyed on a checksum read from a file in
  the repo -- can a fork or a pull_request_target flow poison it? What triggers does it use, and
  does any step run untrusted PR content with elevated permissions or secrets?
- .github/workflows/source.yml: it runs on a schedule and re-records from a live third-party
  service, then diffs. Does anything from that response reach a shell?
- .pre-commit-config.yaml: hooks run local commands. Anything unsafe there?
- The engine is invoked with cwd=dab/. What does it read from that directory, and could a file
  there change what executes?
- Is the checksum verification using a constant-time comparison, and does that matter here?`,
  },
  {
    key: 'files-and-exposure',
    focus: `File handling and data exposure:
- Path handling in src/adss/project.py, source.py record()/replay(), destination.py shim() and
  landing.py. Can any write land outside the intended directory? shim() creates symlinks from a
  build number parsed out of a subprocess's stderr with a regex -- trace that: what if the
  matched group contained a path separator or traversal?
- source.py record() deletes files: \`for stale in directory.glob("page-*.json"): stale.unlink()\`.
  What directory can that be pointed at?
- destinations/app.py: it opens a DuckDB file and renders values into a page. Is there any
  injection into the rendered output, and does it matter for a locally-rendered notebook?
- Does anything log, print, or commit a credential, token, or personal data? Check what
  das/fixtures and the generated SQL actually contain, and what CI prints.
- The contract's ownership block and the connections.yaml: any credential handling, and is the
  DuckDB profile's shape a problem?`,
  },
]

const found = await parallel(LENSES.map(lens => () =>
  agent(`${CONTEXT}\n${RULES}\n\nYOUR LENS: ${lens.focus}`, {
    label: lens.key, phase: 'Find', schema: FINDING,
  })
))

const candidates = found.filter(Boolean).flatMap(r => r.findings || [])
log(`${candidates.length} candidate findings to filter`)

if (!candidates.length) {
  return { verdict: 'no findings survived the finding stage', rejected: found.filter(Boolean).flatMap(r => r.consideredAndRejected || []) }
}

phase('Filter')

const VERDICT = {
  type: 'object',
  properties: {
    title: { type: 'string' },
    isReal: { type: 'boolean' },
    confidence: { type: 'integer', description: '1-10, your OWN assessment after checking' },
    reasoning: { type: 'string', description: 'What you checked in the actual code, and what it showed' },
    severity: { type: 'string', enum: ['HIGH', 'MEDIUM', 'LOW'] },
    file: { type: 'string' },
    line: { type: 'integer' },
    category: { type: 'string' },
    description: { type: 'string' },
    exploitScenario: { type: 'string' },
    recommendation: { type: 'string' },
  },
  required: ['title', 'isReal', 'confidence', 'reasoning', 'severity', 'file', 'line', 'category', 'description', 'exploitScenario', 'recommendation'],
}

const verdicts = await parallel(candidates.map((candidate, index) => () =>
  agent(`${CONTEXT}

YOU ARE AN ADVERSARIAL FILTER. Another reviewer raised the finding below. Your job is to try
to REFUTE it by reading the actual code. Default to refuting: most raised findings in a
developer tool like this one are not real.

<finding index="${index}">
${JSON.stringify(candidate, null, 2)}
</finding>

Read the named file and everything it calls. Then answer honestly:
1. Is there a CONCRETE attacker-controlled input that reaches the sink? Name it and trace it.
   "Repository content" is not attacker-controlled here -- see the trust model above.
2. Is the impact real in a local developer/CI tool with no inbound network surface?
3. Does an existing guard already prevent it? Look for one before concluding there is none.

${RULES}

Set isReal false unless you have traced a real path end to end. Your confidence is YOUR
assessment after checking, not the original reviewer's.`, {
    label: `filter:${candidate.file}:${candidate.line}`, phase: 'Filter', schema: VERDICT,
  })
))

const survived = verdicts.filter(Boolean).filter(v => v.isReal && v.confidence >= 8)
log(`${survived.length} of ${candidates.length} survived filtering at confidence >= 8`)

return {
  survived,
  refuted: verdicts.filter(Boolean).filter(v => !(v.isReal && v.confidence >= 8))
    .map(v => ({ title: v.title, confidence: v.confidence, why: v.reasoning })),
  consideredAndRejected: found.filter(Boolean).flatMap(r => r.consideredAndRejected || []),
}

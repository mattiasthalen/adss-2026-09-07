# Conventions

The **one** convention document: naming, SQL style, YAML style, Python style, commit format.
There is deliberately no second machine-readable copy of these rules. Where an off-the-shelf tool
can already check a rule, **the tool's configuration is the rule** and this page records only the
reason; everything else is checked by whoever — or whatever — reviews the change, reading this
page.

The reason is drift. A convention that exists both as prose and as a linter config exists twice,
the two copies disagree within a quarter, and the disagreement is discovered by an argument in a
pull request. One artefact means a clarification takes effect the moment it is written here.

Principles live in [blueprint.md](blueprint.md); decisions in [adr/](adr/README.md); registered
departures in [deviations.md](deviations.md).

## How to read a rule

Every rule carries a **why** and a severity. The why is not decoration: it is what lets a
reviewer tell a genuine violation from a case the rule was never aimed at.

| Severity | Meaning | On a pull request |
|---|---|---|
| **Hard rule** | Breaking it breaks a contract something else depends on. | Blocks. Fix it, or register a deviation with an ADR. |
| **Guideline** | Judgement and taste. | A comment, not a block. A reasoned "no thanks" ends it. |

## 1. Naming by layer

Names are the interface between layers, so each layer names things in its own vocabulary and
never in its neighbour's.

The layers are called `das`, `dab` and `dar` literally — in schemas, in directories, in prose.
Never bronze/silver/gold, never staging/core/marts. The name carries the principle
([blueprint.md](blueprint.md)); a name that carries no principle cannot be enforced.

### 1.1 DAS — the source-vocabulary exemption

| Rule | Why | Severity |
|---|---|---|
| DAS object and column names mirror the source. The source's own words are **required** here, even where other layers forbid them. | DAS exists to say what the source said. Renaming a source field to a business term buries an interpretation in the layer that must make none. | Hard rule |
| The mechanical translation is expected: a source property becomes `snake_case`, a source entity set becomes a `snake_case` plural table named after the source's own word for it. | A consistent spelling of the source's word is still the source's word. | Hard rule |
| A contract file's stem is the landed table name, and that name is used in every schema of this layer. | One name for one thing, so grepping for a table finds its contract. | Hard rule |
| A source name that would be a violation anywhere else — `ShipVia`, `total_orders` — is **not** a violation here. | It is a column in a table nobody on this side controls. A rule that cannot tell that case from a name we chose produces false accusations. | Hard rule |
| A contract's `description` stays in system vocabulary: the source's type, its nullability, what the source calls it. Never what it means to the business. | Business meaning has exactly one home (§1.2). | Hard rule |
| Columns this layer adds itself carry no source's word and are named for what they record: `extracted_at`, `extracted_on`, `payload`. | Provenance is ours, not the source's, and must be tellable apart from it at a glance. | Hard rule |

### 1.2 DAB — the business vocabulary

| Rule | Why | Severity |
|---|---|---|
| Entity, attribute and relationship identifiers are `UPPER_SNAKE_CASE`, with `id` and `name` holding the identical string. | It is the modelling language's convention, and the visual break from every other layer's lower case makes a leak obvious on sight. | Hard rule |
| Entity and attribute names are **singular**: `ORDER`, `ORDER_LINE`, `SHIP_COUNTRY`. | An entity names a kind of thing, not a pile of them. The pile is what a query produces. | Hard rule |
| Descriptive attributes are prefixed with their entity (`CUSTOMER_NAME`, `ORDER_LINE_ID`); generic ones and measures are not (`STATUS`, `QUANTITY`). | The prefix is what makes an attribute readable once it has been inherited into a wide DAR row. | Guideline |
| **No source name appears anywhere in DAB** — not in an id, not in a definition, not in a description. | This is the layer whose purpose is source-agnosticism; a source name in it means the dependency was moved rather than broken. | Hard rule |
| Every entity, attribute and relationship has a `definition` in business language, and that is the **only** place the data is explained. | Everything else — contracts, questions, the generated layer, the app — references these. Two definitions eventually mean two numbers. | Hard rule |
| A relationship name is a verb phrase, so `<SOURCE>_<NAME>_<TARGET>` reads as a sentence: `ORDER_IS_PLACED_BY_CUSTOMER`. | Direction is the thing people get wrong, and a sentence cannot be read backwards by accident. | Hard rule |
| Names say what a thing *is* to the business, not how it is stored or derived: `PLACED_ON`, not `ORDER_DATE_TS`. | The physical shape changes; the concept does not. | Guideline |
| Prefer the word the business already uses over a more precise one it does not. | A model nobody recognises is a model nobody checks. | Guideline |

### 1.3 DAR — the generated layer

Names here are emitted by the generator, so these rules are what the generator implements. They
are on this page because they are the contract every consumer is written against.

| Rule | Why | Severity |
|---|---|---|
| Object names are `snake_case` **singular**, derived from the entity: `order`, `order_line`. A reserved word is quoted (`dar__uss."order"`), never abbreviated around. | Same reason as §1.2, in the other layer's spelling. Renaming to dodge a keyword breaks the mechanical link back to the concept. | Hard rule |
| A key column is `<object>_key`. | One predictable spelling means a join can be written without looking anything up. | Hard rule |
| Attribute columns are the lower-cased attribute identifier, unchanged. | The mapping back to its definition must be mechanical, so any column's meaning is one step away. | Hard rule |
| Structural columns carry a leading underscore: `_bridge`, `_calendar`, `_stage`, `_event`, `_event_date`, `_is_current`, `_measure__…`. | The underscore says "the generator owns this". Anything without one came from the business model. | Hard rule |
| Measure columns are `_measure__<entity>__<measure>`. | Two underscores separate the three segments so an entity or measure name containing one is still unambiguous. | Hard rule |
| **Nothing in this layer is hand-edited.** A wrong name is fixed in the business model and regenerated. | Blueprint R4. An edit to generated output is lost on the next generation. | Hard rule |

## 2. Measure naming

The most consequential convention here, and the one to get right first.

**Pattern: `<descriptor>_<entities>_<unit>`.**

| Rule | Why | Severity |
|---|---|---|
| Three parts in that order: what distinguishes it, the entity it counts or sums over, the unit it is in. | Three fixed slots make names comparable at a glance and searchable by any of the three. | Hard rule |
| The entity part is **plural**: `orders`, `order_lines`. | A measure is always about a set. The singular is reserved for the entity itself. | Hard rule |
| Scope and aggregation words never appear: no `total_`, `sum_`, `avg_`, `count_of_`, `num_`, `_ytd`, `_by_month`. | Aggregation and scope are chosen by the query, not baked into the name. `total_orders` is a lie the moment somebody filters it. | Hard rule |
| The unit is a real unit: `count`, `amount`, `days`. | It is what tells a reader whether two measures can be added. | Hard rule |
| **Ratios are not stored.** Store numerator and denominator as additive measures and divide at query time. | An average of averages is wrong at every grain but the one it was computed at. | Hard rule |
| A name must be self-explanatory without a glossary lookup, and must describe the business concept rather than the implementation. | If understanding a measure needs the glossary open, the name has failed at the only job a name has. | Guideline |
| No abbreviations. `paid_subscriptions_count`, not `nbr_of_paid_subs`. | Abbreviations are unsearchable, and searchability is most of a name's value. | Guideline |

| Instead of | Write | Because |
|---|---|---|
| `total_orders` | `placed_orders_count` | Scope word goes; the descriptor says *which* orders; the unit says what the number is. |
| `sum_revenue` | `revenue_order_lines_amount` | `sum` is the query's job; the entity says at what grain revenue is measured. |
| `avg_days_to_ship` | `ship_lag_orders_days` | The average is `sum(ship_lag_orders_days) / sum(shipped_orders_count)` at query time, from two additive measures. |

## 3. SQL style

Everything a tool can check is checked by `sqlfluff` with [`.sqlfluff`](../.sqlfluff); this page
records why the settings are what they are. All hard rules, because generated and hand-written
SQL have to be indistinguishable to a reviewer.

| Rule | Why |
|---|---|
| Dialect is `duckdb`. | Not a preference: the `postgres` dialect cannot parse `QUALIFY`. |
| Keywords upper case, functions lower case, identifiers lower case. | Three visual classes, so structure, computation and data separate at a glance in a long generated statement. |
| Four-space indent; one selected expression per line; every expression aliased with `AS`. | Diffs of generated SQL are read constantly. One expression per line makes a one-column change a one-line diff. |
| Every table reference has an explicit alias, and a join condition names the earlier table first. | Reading order matches join order, so a wrong join key is visible without tracing back up the statement. |
| `cast(x AS T)`, never `x::T`. | `CV11` enforces one casting style; `cast()` is the one that reads as a function like every other function. |
| Every column reference in a multi-table statement is table-qualified. | `RF02`. It is the one rule sqlfluff cannot autofix, and it is a correctness rule, not a style one. |
| Identifiers crossing over from DAB are double-quoted; everything this repository creates is lower case and unquoted, except reserved words. | The two conventions must be visually distinct, because a mixed-case identifier that loses its quotes fails only at run time. |
| No `SELECT *` in anything a consumer reads, except a union of stages whose column list the generator fixes. | A star is a schema change waiting to be silent. |
| SQL that lives in a Python string is written to a file so the same linter sees it. | A rule that applies only to the SQL somebody remembered to put in a `.sql` file is not a rule. |

Four rules are excluded, and the reasons are in [`.sqlfluff`](../.sqlfluff): `AL09` forbids
`x AS x`, which is exactly the every-column-aliased discipline that makes a `UNION` branch
positionally safe; `RF06` fires on every mixed-case identifier crossing over from DAB; `LT05` and
`LT09` are line-layout opinions a generator should not have to implement.

## 4. YAML style

Checked by `yamllint` with [`.yamllint.yaml`](../.yamllint.yaml).

| Rule | Why | Severity |
|---|---|---|
| Two-space indent, no tabs, lines ≤ 160. | These files are read far more often than they are written. | Hard rule |
| Flow mappings (`{a: 1, b: 2}`) are allowed for short homogeneous rows — a contract column, a mapping attribute — but never column-aligned with padding spaces. | Alignment re-aligns the whole block the day one value grows, turning a one-line change into a twenty-line diff. | Hard rule |
| Anything with an interpolation, a multi-line value, or more than about four keys is block style. | Flow style stops being readable exactly where the value stops being simple. | Hard rule |
| Booleans are `true`/`false`. | One spelling. `yes`/`on` are the same value wearing a disguise. | Hard rule |

## 5. Python style

| Rule | Why | Severity |
|---|---|---|
| `ruff` with [`pyproject.toml`](../pyproject.toml) is the style. `ty --error all` is the type gate. | No style discussions, ever. | Hard rule |
| `ANN` stays in the ruff selection. | `ty` does not flag a fully unannotated `def`. Without `ANN` the type gate has a hole. | Hard rule |
| **No data vocabulary anywhere under `src/` or in test code.** No entity, attribute or business term from the model appears in the machinery or in a test. | The machinery must work for any source and any business model; a data name in it is proof that it does not. Test fixtures use neutral models held as data files, so the tests *prove* the machinery is generic rather than asserting it. | Hard rule |
| Data vocabulary belongs in the YAML, SQL and Markdown artefacts — contracts, the model, generated SQL, questions, these documents. | Those artefacts *are* the description of this particular business. That is the point of keeping it out of the code. | Hard rule |
| Names describe the machinery's concepts: `contract`, `pipeline`, `plan`, `stage`, `peripheral`, `question`, `destination`. | The machinery has its own domain and deserves its own vocabulary. | Guideline |

## 6. Tests

| Rule | Why | Severity |
|---|---|---|
| Machinery is test-first: the failing test and the code that passes it land in one commit. | A test written afterwards is a test that has only ever been seen to pass. |  Hard rule |
| Data checks are not written against a stub. They assert what the built warehouse contains and land in the same commit as the build that satisfies them. | TDD is for functions. A `SELECT` is not designed test-first, and pretending otherwise is ceremony. | Hard rule |
| No `pytest.skip`, no imperative `xfail()` in a test body. | A skip is a test that silently does not exist. An imperative `xfail` can never report an unexpected pass, so it cannot tell you the day the bug is fixed. | Hard rule |
| A failing check is fixed by fixing the code, or by making the configuration honest. Never by weakening the test. | A weakened test costs the same to run and reports the opposite of the truth. | Hard rule |

## 7. Commits, branches and pull requests

| Rule | Why | Severity |
|---|---|---|
| Conventional commits: `<type>(<scope>): <imperative>`. Types `feat`, `fix`, `test`, `docs`, `chore`, `refactor`, `ci`. Scopes: `repo`, `domain`, `das`, `dab`, `dar`, `questions`, `destination`, `ci`, `docs`, `skills`. | The scope names the layer, so the history reads as a map of the architecture and a reviewer knows which rules apply before opening the diff. | Hard rule |
| The subject is imperative, lower case, no trailing period, about 72 characters. | It is a heading, read in lists a hundred times more often than the body. | Guideline |
| Every commit passes the gate and the whole suite on its own. | Bisect is only worth anything if every point in history is a working system. | Hard rule |
| One business question per slice; one branch per slice, `claude/adss-slice-NN-<slug>`, branched off the previous slice. | The unit of delivery is an answered question, not a file. | Hard rule |
| Stacked branches are rebased, never merged; pull requests are rebase-merged, never squashed. | Squashing destroys the trail that shows the question drove the change. Merge commits make a stack unreadable. | Hard rule |
| An ADR lands before the code it decides. | A decision record written afterwards records what was built, not what was decided. | Hard rule |

## 8. Documentation

| Rule | Why | Severity |
|---|---|---|
| A decision goes in an ADR under [`adr/`](adr/README.md), numbered, in MADR format, and is superseded by a new file rather than edited. | The value of a decision record is the record of what was true when it was made. | Hard rule |
| A departure from a principle in [blueprint.md](blueprint.md) or a hard rule here needs an entry in [deviations.md](deviations.md) and an ADR. | An unregistered exception is indistinguishable from a mistake, and the next person copies it. | Hard rule |
| Markdown lines stay around 100 characters, breaking at a sentence or clause — except table rows, which stay on one line. | Prose diffs stay legible; a re-wrapped paragraph should not look like a rewrite. | Guideline |
| Prefer a table when there are three or more parallel things to say. | Parallel structure is easier to check for gaps than parallel prose. | Guideline |

## 9. When a rule does not fit

Rules are aimed at cases; a case the rule was not aimed at is not a violation. Cheapest recourse
first:

1. **Clarify this page.** If the rule was ambiguous, say what it means and add the case. The
   clarification is in force immediately, for everyone.
2. **Register a deviation.** If the rule is right and this one place genuinely cannot follow it,
   add an entry to [deviations.md](deviations.md) — rule, reason, cost, exit condition — and an
   ADR explaining the decision.
3. **Change the rule.** If it is wrong, supersede the ADR that established it and edit this page.
   A rule nobody follows should be deleted rather than left as a reason to distrust the rest.

What is not on the list: a quiet exception. That is how a system of conventions turns into a set
of stories about why each file is the way it is.

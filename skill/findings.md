# What the run says about the skill

Read against `session/`, the four slice branches, and the current text of
`grill-to-build`. Every claim below is checkable from one of those three.

The proposed text is `SKILL.md` beside this file. Six changes, listed at the
bottom with the break each one answers.

## The thing that explains most of the rest

**The skill file was not read until 22:20:57, seven and a half hours in.**

The session opened at 14:50 with a prompt whose first lines are the skill's own
first lines. But it is an abridged copy. Set the pasted text beside the file:

| In the file | In the pasted prompt |
|---|---|
| Review the plan before I see it. Fresh agents, findings unrevised. | absent |
| The plan names the seams that get TDD. | absent |
| MADR at the decision, never batched | "MADR before the code" |
| Code review and security review before I see it | absent |

There is no `Skill(grill-to-build)` call before 22:20:57. Slice 1 was interviewed,
planned, built, verified and presented against the prompt alone, and the model had
no way to know there was more, because the prompt read like the skill and the
description summarises the same words.

At 22:20:57, starting slice 2, it opened the file and said so:

> The skill sharpens two things I should correct. **"MADR at the decision, never
> batched"** -- I batched five into one commit for slice 1. And **"code review and
> security review before I see it"** -- I ran the code review, but security review
> never ran. I owe you that on slice 1.

The security-review workflow script is authored three minutes later, at 22:23.

So two of the three "known process failures" in the branch README have one cause,
and it is not the one the README gives. The ADRs were not batched in defiance of a
rule; the rule in force was "MADR before the code" and `e81a9af` satisfies it. The
security review was not forgotten; it was not asked for. The README judges the run
against lines that were added because of it, which is a self-report written after
the file was finally read, and it is wrong about why.

The third README finding, the non-idempotent build, stands. It is independent of
which skill text was in force.

This also means four lines of the current skill have never actually run: the plan
review, the TDD seams, the batching clause, and the review pair. Nothing here
validates them. What it validates is that a paraphrase in the prompt suppresses
the file.

## The five questions

### 1. Interview against what reached the repo

The interview is 30 questions across eight `AskUserQuestion` calls, 18:42 to
20:00. It settled well and it mostly survived.

**The plan did not.** It went to `ExitPlanMode` at 19:36, was approved, and was
saved to `/root/.claude/plans/composed-hopping-mccarthy.md`. That path is
container-local and the container is gone. There is no `docs/plan.md` on any
branch. The nineteen numbered decisions, the six-slice arc and the spike findings
as a set exist now only in `session/transcript.jsonl`.

Some of it reached the repo by other routes. The prioritised question list is in
`docs/questions/README.md`, slices 5 and 6 included and marked `not started`. But
it landed at `9b68ae1`, the second-to-last commit of slice 1, after everything it
was meant to guide, and it landed because the user typed "Oh. And out the question
docs under docs/" at 19:30. Without that message there would be nothing.

**The spikes are not the worst case.** They are close to the best. Checking each
finding from the plan against the tree at slice 4:

| Finding | Where it lives now |
|---|---|
| `enable_dataset_name_normalization=False` | `src/adss/landing.py:52`, with the reason in a comment above it |
| `union_by_name => true` | `src/adss/das.py`, conventions, ADR 0003, das skill |
| `_dlt_id` is not a record identity | `src/adss/das.py`, conventions §1.1 |
| `FULL` silently duplicates, so `FULL_LOG` | conventions M3, as a rule with the observation as its reason |
| single-writer discipline | `src/adss/engine.py`, `platform.py`, conventions §9 |
| `_focal`/`_idfr` never populated | ADRs 0002, 0004, 0006, 0010, both layer skills |
| `DECIMAL(28,8)` widening | `dar/uss/_bridge.sql`, `src/adss/uss.py`, four tests |
| duckdb dialect required, postgres cannot parse `QUALIFY` | `.sqlfluff` line 2, conventions §3 |
| `AL09` and the other exclusions | `.sqlfluff`, with a paragraph each |
| `ty` does not flag an unannotated def, so keep ruff `ANN` | conventions §5 |
| `marimo export html` is not self-contained | `src/adss/destination.py`, destination skill |
| altair cannot encode `DECIMAL` | `destinations/app.py` |

Twelve of twelve, and most carry the reasoning rather than just the setting. What
did not survive is narrower and worth naming: **the negative findings.**
"`max_table_nesting=0` does not do this, it still splits top-level keys into typed
columns" appears nowhere in the repository. Neither does the `$metadata` audit
behind the history clock; conventions M4 asserts "no source here reports when it
changed" without the eleven entity types and seventy properties that were counted
to establish it. The finding that survives is "do X". The finding that dies is "Y
looks right and is not", which is the one the next person needs, because Y is what
they will try.

### 2. Do ADRs 0002, 0003 and 0004 agree?

They agree, and that is the failure.

ADR 0002 line 33 and ADR 0004 line 36 make the same claim:
`view_<entity>_with_rel` carries no relationship keys, its column list byte
identical to `view_<entity>`. It is false. On a relationship's **target** side that
view joins back to the source entity and fans out. The slice-2 probe measured
200.75 against a true 150.75.

The root cause is upstream of the concurrency. Spike 2 built a two-entity model
with one relationship and listed every object the engine produced, `view_CUSTOMER`,
`view_CUSTOMER_with_rel`, `view_ORDER`, `view_ORDER_with_rel`, in its own
`information_schema` output. It then ran `DESCRIBE` and `SELECT` on
`view_ORDER_with_rel` only, the source side, and never opened
`view_CUSTOMER_with_rel`, which was sitting in the list. From that one case it
wrote a universal, with `confidence: "observed"` and a directive attached:

> `view_<entity>_with_rel` does NOT expose any relationship key columns -- its
> column list is identical to `view_<entity>`. Do not plan the DAR/USS build on
> with_rel carrying the foreign keys.

The framing workflow then handed that file to six agents under the instruction
"TREAT THESE AS FACT; they were observed, not guessed." Two of them wrote it into
an ADR. It reached `docs/adr/0002`, `docs/adr/0004`, `.claude/skills/dab/SKILL.md`,
`.claude/skills/dar/SKILL.md`, and a data check that asserted the wrong rule of
every entity. Undoing it took a probe and four commits in slice 2: `55edbd7`,
`80d3a08`, `3650b66`, and the check replacement.

Concurrency did not create a contradiction. It created two independent-looking
copies of one upstream error, which read as corroboration.

Two things follow.

**ADR 0004 still carries the false claim, with no forward pointer.** ADR 0006's
corrections section names it exactly:

> **ADR 0004 repeats the same claim** -- "`view_<entity>_with_rel` carries no
> relationship keys despite its name" -- and is corrected here too, not there.

Correcting in a later record rather than in place is defensible MADR practice and
was chosen deliberately. But ADR 0002 at least gained a pointer in its confirmation
section. ADR 0004 gained nothing: a reader who opens it is told the wrong thing
with no way to find out. That is a live defect in the tree today.

**All five drafted ADRs named a confirmation that did not exist.** `3d2fa7e`:
"Four ADRs described confirmations nobody had written." The fifth, ADR 0004, was
found a slice later by the security review, `015f9c5`: its confirmation claimed
`tests/test_engine_pin.py` hashes the vendored binary, and that file's own
docstring says the opposite. The framing schema had a `confirmation` field, each
agent filled it from a plan, and nothing ever tied it to the code that was
eventually written. Five for five.

On the ordering: the binding audit ran beside the drafts, not before them. The
script ends `await Promise.all([bindings, drafts])`, one `Frame` phase. The audit
was the best thing the workflow produced, catching that D-0001 cited an ADR that
did not exist plus a dozen gaps, but its output demanded conventions changes that
the drafts had already been written against. The transcript at 20:35 to 20:40
shows three consecutive rewrites of `docs/conventions.md` between the drafts
arriving and the ADRs landing. That cost a rework pass. It did not cause the false
claim, so no line is proposed for it.

### 3. What the six framing agents handed back

Drafts, inline, through a typed return. `ADR_SCHEMA` asks for
`contextAndProblem` at three to six paragraphs, `argument` at several more,
`consequences`, `concreteShape`, `groundedIn`. Six agents returned 324,358 bytes:

```
audit.json                                      47,959
adr-the-machinery-is-modelled-in-its-own-typ    49,896
adr-a-business-question-is-the-unit-of-deliv    51,428
adr-a-das-data-contract-is-one-yaml-artefact    56,595
adr-dar-is-one-generated-unified-star-schema    59,038
adr-daana-cli-is-the-dab-engine                 59,442
```

The completion notification carried 9,580 characters and said 310,708 were
truncated, with a pointer to the output file. So the main thread was not flooded,
but it did spend two turns writing Python to split the JSON back onto disk before
it could read any of it, and then read about 52 KB of draft prose inline anyway.

This decides the pending line. **Do not add "never drafts or transcripts" as
worded.** It would ban the thing the workflow was for: the binding audit's draft is
what caught the dangling ADR reference, and the five decision drafts are what the
ADRs were written from. What cost something was the return channel, not the draft.
An agent that writes to a file and returns the path plus its conclusion keeps
everything and costs nothing. Hence the reworded line.

### 4. Did the plan review run with fresh agents, findings unrevised?

No. There was no plan review. Seven `Workflow` calls, six runs:

```
read-daana-blog           one agent per remaining blog post, then a synthesis
adss-spikes               four spikes
slice-01-frame            framed slice 1  (invoked twice, once retried)
slice-01-verify           four verification lenses
slice-02-frame            framed slice 2
slice-01-security-review  authored 22:23, after slice 1 was delivered
```

The line asking for it was in the file and the file was not open. The question
cannot be answered from this run; it has not been tested.

## The changes

Six, in `SKILL.md` beside this file.

1. **Description gains "Read it even when the brief already paraphrases it."**
   The file went unread for seven and a half hours because the prompt opened with
   its own words. The description summarised the same words, so nothing broke the
   tie. This is where a triggering failure belongs.

2. **Once gains a home for the plan.** Superseded below: the plan is an issue and
   each slice a child of it, not a file. The break is the same either way. The plan
   was the only artefact holding the interview and the spikes together, it lived in
   a scratch directory that died with its container, and what reached the repo
   reached it by another route. The question list only because the user asked for
   it by hand.

3. **Spike line gains "A spike reports the cases it ran; a finding stated wider is
   a guess."**
   Spike 2 opened one side of a symmetric pair and wrote a universal. Marked
   observed, handed downstream as fact, into two ADRs, two skills and a check, out
   again over four commits and a probe. This is the most expensive single line in
   the run.

4. **MADR line gains "Its confirmation names a check that exists."**
   Five records, five confirmations naming checks nobody had written. Four caught
   by the slice-1 verification, one by the security review a slice later.

5. **Always gains "Don't wait for me between slices. Stop for a question or a
   break."** Pending in the handoff, and earned: the user had to type it at
   22:21:48. The second sentence stays; without it, blocked means invent.

6. **The pending agent line, reworded to "Agents return a path and a conclusion,
   never the artefact itself."** Reason in section 3.

## Not changed

- **Nothing for the concurrent framing.** The audit running beside the drafts cost
  a rework pass, but the false claim came from the spike, and the spike line
  answers it. Sequencing is already available under "workflows wherever they help".
- **Nothing about ADR cross-references.** That two records repeating one fact are
  corrected separately is a repository convention problem, not a process one.
- **Nothing about the review lenses.** The build was not idempotent and neither the
  four lenses nor the code review caught it, fixed later in `058faa6`. That is a
  gap in what a review looks for, and a skill line enumerating what to look for is
  the forty-line version coming back. It belongs in the project's own conventions.

## One thing in the brief, not the skill

The brief says the destination presentation "is what I accept the slice on". That
is an acceptance gate, and change 5 says not to stop for one. Change it to "That
presentation is the slice" if slices should not stop.

## A defect in the tree

`docs/adr/0004-daana-cli-is-the-dab-engine.md` line 36 still states that
`view_<entity>_with_rel` carries no relationship keys. It is false on the target
side and it fans out there. ADR 0006 corrects it but 0004 does not say so.


# Second pass: where the context actually goes

The first pass said the build cost 396k tokens and left it there. Measured properly,
over the slice-1 build window of 20:30 to 22:25:

| | calls | sent | back | total |
|---|---:|---:|---:|---:|
| `Read` on `.screenshots/app.png` | 2 | 0 | 661 KB | **661 KB** |
| heredoc write/script | 45 | 122 KB | 84 KB | 206 KB |
| pytest | 45 | 158 KB | 19 KB | 177 KB |
| read/inspect (cat, sed, grep) | 42 | 74 KB | 50 KB | 124 KB |
| assistant prose | | | | 70 KB |
| pre-commit, full gate | 28 | 43 KB | 15 KB | 57 KB |
| everything else | ~40 | | | 165 KB |

**Two `Read` calls on one PNG are 45% of the build.** 459 KB and 202 KB of base64,
roughly 185k tokens spent looking at a screenshot twice. The file was already
committed at `docs/questions/01-orders-per-month-and-destination-country/answer.png`;
it was pulled back into the main thread as raw bytes to be looked at.

Nothing else is remarkable. The 122 KB of heredocs is the code itself. Twenty-eight
runs of the full gate cost 57 KB between them. The gate was never the problem.

In size order, what is worth changing:

1. **The screenshot, 661 KB.** Acceptance is visual, so something must look. An
   agent that looks and returns "renders, 322 rows, bars present, no error banner"
   costs 200 bytes here. Downscaling to 800px first is roughly another 4x. One
   change, half the problem.
2. **84 KB returning from heredocs**, scripts printing back what they just wrote.
3. **158 KB sent across 45 pytest calls**, mean 3.5 KB: test source riding inline
   with the run command rather than written once and run by path.
4. **124 KB of cat, sed and grep**, much of it re-reading files written moments
   before.

Fixing 1 alone takes a slice from about 415k to about 230k. With 2 through 4 it is
nearer 180k.

## One session is enough, and this run proved it

`3d2fa7e`, `058faa6`, `4618ec8` and `9378ffe` all carry
`session_019rspwWhmXfxoTvKg5jmNWh`. One session built all four slices, 21:52 through
04:56, straight through the compaction at 22:26. A session boundary per slice is not
needed and the recommendation for one is withdrawn.

What the tickets are for is therefore not context. It is that the plan died with its
container, and that a session resuming after that needs the arc and the rules that
were in force. That is also why Always is snapshotted into the parent issue rather
than referenced: a ticket should record the rules the work was done under, which is
the exact thing the branch README got wrong about this run.

## What changed on the second pass

- `Once`: the plan is an issue, each slice a child of it, Always snapshotted in the
  parent. Then build them in one session rather than stopping.
- New `A slice ticket` section: its question, what it widens, and the branch to start
  from; start from that branch at ready rather than at merge and merge it forward
  first; ready means the gate is green and both reviews have run.
- `Always`: the agent line generalises to "A path and a conclusion, never the
  artefact. Screenshots included." It already said this for agents. The main thread
  did it to itself, twice, for 661 KB.
- `Always` gains "Fix a slice on its own branch, then bring it forward." `058faa6`, the
  fix that made the build idempotent, sits on slice 2's branch and never reached
  slice 1's. Slice 1's pull request still stands with a build that fails on its
  second run.


# Third pass: the build, and the plan issue as a residue

## The build, considered and not adopted

A line delegating the build to agents was drafted and cut. The measurement below
stands; the line did not survive, because two lines about what enters and leaves
the main thread cover 70% of the same cost without changing who builds.

The remaining 564 KB of a slice's build is construction, not decision: 206 KB of
heredoc writes, 177 KB of pytest, 124 KB of re-reads, 57 KB of gate runs. None of
it is something the main thread has to hold afterwards. All sixteen commits in this
run were issued from the main session, and that is why it held all of it.

The unit it would have taken that fits this repository is the layer, because the
slice already decomposes that way and the commits show it: `feat(das)`, `feat(dab)`,
`feat(dar)`, `feat(questions)`, `feat(destination)`. One agent each, and each one
already has a skill written for it under `.claude/skills/`, which is what those
skills were for.

The agent commits rather than handing files back. It is the one that knows what
changed, and the commit messages in this run are good because whoever wrote them
had just done the work. `Red and green in a single conventional commit` binds the
agent, which is another reason Always travels with the ticket.

**Serially, each reading the last.** Not in parallel. The one time this run fanned
out concurrent agents over work that constrained itself, the five framing drafts,
two of them wrote the same unverified claim into two records that then read as
corroboration. Construction constrains itself more tightly than drafting does.

The main thread's job per slice is then: frame, decide and write the records,
dispatch, verify, present, open the pull request. Decisions and verdicts, not
construction.

## The plan issue

The parent issue holds two things that do not mix.

**Always**, snapshotted as it stood when the plan was made. Static. It records the
rules the work was done under, which is exactly what the branch README got wrong
about this run.

**The residue**: every interview decision and spike finding that has not yet become
a convention, an ADR, a check or a comment in the code. A line leaves when it lands,
replaced by a pointer to where it landed. It shrinks toward nothing, so it cannot
become a second truth: whatever is still in it is by construction not expressed
anywhere else.

In this run the residue would be small, because twelve of twelve spike findings
reached the tree. What would still be sitting in it is the class named above: the
negative findings. That `max_table_nesting=0` is not enough is nowhere in the
repository, and neither is the `$metadata` count behind the history clock, which
conventions M4 asserts without the measurement that established it. Those are the
lines that would still be open, and they are the ones worth keeping open, because
they are what the next person will otherwise re-derive.


## The four, and which line covers each

| | | share | covered by |
|---|---|---:|---|
| 1 | `Read` on the screenshot | 45% | a path and a conclusion, never the artefact |
| 2 | heredocs printing back what they wrote | 6% | same line: a script that echoes its own file is returning the artefact |
| 3 | test source riding inline with 45 pytest calls | 11% | write a file once, then run it by path |
| 4 | re-reading files written moments earlier | 8% | same line: read it by path |

Two lines, 70% of a slice's build. Neither is something the model does unprompted:
it made 45 pytest calls carrying 3.5 KB of source each, and 42 separate cat, sed and
grep calls over files it had just written.


# Parked: the ticket design

A parent issue for the plan, a child issue per slice, and Always snapshotted into
the parent were designed and then cut. The goal is one autonomous session, and this
run already proves that works: `session_019rspwWhmXfxoTvKg5jmNWh` built all four
slices, 21:52 to 04:56, straight through a compaction. Tickets solve a problem that
one session does not have.

What they would buy, if a session ever has to be resumed after its container dies:
the plan survives, and the rules that were in force survive with it. The plan file
at `/root/.claude/plans/` survives compaction but not the container. Nothing else
in this run held the arc.

What stays from the design, because it is earned independently:

* **The next slice starts when the last one's PR is ready for review and green.**
  Without a definition, "don't wait for me between slices" has no trigger.
* **Fix a slice on its own branch, then bring it forward.** `058faa6`, the fix that
  made slice 1's build idempotent, sits on slice 2's branch. Slice 1's pull request
  is still standing with a build that fails on its second run, and its reviewers
  cannot see the fix. The defect belongs to slice 1, so the commit belongs on slice
  1's branch and the stack above it picks the fix up. This was first written as "a
  fix to a slice below lands on the branch below", which reads as the opposite as
  easily as it reads as this.

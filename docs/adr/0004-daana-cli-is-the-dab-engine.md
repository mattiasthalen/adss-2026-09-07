---
status: accepted
date: 2026-09-07
decision-makers: [adss maintainers]
slice: 1
---

# daana-cli is the DAB engine, vendored as a checksum-pinned binary and constrained by a mapping rule set this repository enforces itself

## Context and Problem Statement

DAB is where the three challenges are actually addressed, and Ensemble Modeling is how: a Core
Business Concept holding only identity, a Description per attribute with its own history, an
Association per relationship. The point of that decomposition is that change is additive — a new
attribute is a new structure, never an `ALTER` to one other things depend on (blueprint B7).
`daana-cli` implements exactly this shape, generating the structures and the loading code from a
declared model, which is the "consistency by construction" the architecture depends on.

Adopting it raises two problems that have nothing to do with modelling.

The first is supply. The binary is a 174 MB git-LFS object on a private repository's branch. CI
cannot reach it unauthenticated — raw, media and API all refuse — so the engine has to get into a
build somehow, and the choice has consequences for anyone who ever clones this repository.

The second is that the engine accepts several kinds of wrong mapping without complaint, and two of
those are silent. `FULL` ingestion against a source view holding more than one row per key inserts
one duplicate row per execute, forever, and **every presentation view hides it** — the current
view and the history view both stayed the right size across three runs while the base table grew
22 → 23 → 24 → 25. Our staged change log is multi-row-per-key by construction, so the wrong
setting is the one that looks like a snapshot loader and is named after completeness. A mismatched
relationship `source_table` is skipped in silence. Two `primary_keys` entries mean two alternate
identifiers rather than a composite key, and that mode cannot be undone once loaded.

Three further behaviours were observed on DuckDB, which the engine's own help text does not list
among its supported platforms. `<entity>_focal` and `<entity>_idfr` are created but never
populated. `view_<entity>_with_rel` carries no relationship keys despite its name. And if the
process invoking the engine is itself holding the warehouse open, `execute` fails with
`daana framework is not installed on the remote database`, which is not what went wrong.

That last one was first reported to us in a broader form — that *any* other connection breaks it —
and that turned out not to reproduce. DuckDB's lock is **per process**: within one process every
connection shares an instance, so a second open succeeds; across processes the second is refused.
The failure is therefore specific and enforceable: we must not hold the file while asking a
subprocess to write to it. The narrower rule is the useful one, because it can be checked in code
rather than believed.

## Decision Drivers

* a clone of this repository can build it, without a secret
* the engine version is pinned by something that cannot be silently changed
* the ways the engine accepts a wrong mapping are closed by this repository, not remembered
* the DAB layer's history is what DAS observed, and is reproducible
* a misleading engine error costs a reader minutes, not an afternoon

## Considered Options

* Vendor the binary here under git-LFS, restored in CI from a checksum-keyed cache
* Fetch it in CI from the private source repository using a token secret
* Two-tier CI: the gate always, the warehouse build only where the binary happens to exist
* Require a local path and document it

## Decision Outcome

Chosen option: **vendor it here under git-LFS at `bin/linux-amd64/daana-cli`, with its `.sha256`
beside it, restored in CI from an Actions cache keyed on that checksum.**

The property that decides it is that the repository becomes self-contained: anyone who can clone
it can build it, with no secret, no access to a second private repository, and no step that works
only on the machine it was written on. For a system whose entire claim is reproducibility, an
engine reachable only by the person holding a token is the wrong shape. Fetching with a secret was
the serious alternative and it loses on exactly that — CI breaks for a fork, and for a future
maintainer after a rotation, in a way that looks like a code failure. Two-tier CI loses harder:
the check that actually proves the architecture works would be the one that does not run.

The cost is real and is accepted: 174 MB of LFS storage, and a bandwidth bill on any run that
misses the cache. Keying the cache on the checksum rather than on a version string means the
transfer happens once per *binary*, and a changed binary invalidates the cache by construction
rather than by anyone remembering to bump something.

*The engine is pinned by content.* `daana-cli --version` self-reports `nightly` with a commit
hash, so there is no version to depend on. `bin/linux-amd64/daana-cli.sha256` is the pin, it is
verified before every invocation, and a mismatch is a hard failure rather than a warning. The
self-reported string is recorded alongside it, so an upgrade is a diff that names both what
changed and what it called itself.

*The mapping rules are enforced here.* The seven rules in
[conventions.md §1.4](../conventions.md) exist because the engine will not enforce them, and this
repository checks them against `dab/mappings/*.yaml` in the machinery suite. `FULL_LOG` is the
default and `FULL` requires a proof, because the failure it produces is invisible in every view a
person would look at — including, and this is the part worth stating plainly, in both of a
question's acceptance queries. The safety net would not have caught it.

*DAR reads the `view_*` layer only.* Not `_focal`, not `_idfr`, not `_with_rel`. That is recorded
here rather than in the DAR record because it is a fact about this engine on this platform, and it
is where someone will look for it.

*Entity ids stay `UPPER_SNAKE_CASE`.* DuckDB preserves that casing into object names, so `view_ORDER`
rather than `view_order`, where PostgreSQL would fold it. The convention survives because DuckDB
resolves identifiers case-insensitively — a consumer may write either — but any code that matches
names out of the catalog must normalise. Keeping the model's casing loud is worth more than the
convenience: the visual break from every other layer's lower case is what makes a leak from DAB
into DAS or DAR obvious on sight, which is the reason §1.2 asks for it.

*Detached invocation.* The CLI refuses to invoke the engine while this process holds the
warehouse, and says why. Destinations open read-only, which still holds the process lock but at
least keeps a reader from writing. And the misleading error is translated: when the engine says
the framework is not installed, we say the file is held, because that is what happened.

### Consequences

* Good, because anyone who can clone this repository can build it, with no secret and no second
  repository
* Good, because the engine is pinned by content, so it cannot change without the diff saying so
* Good, because the seven mapping rules are checked by this repository's own tests rather than
  remembered, which is what the architecture asks of every other convention
* Good, because the engine's most misleading error now says what actually happened
* Bad, because 174 MB of LFS storage is a real cost, and a cache miss is a real transfer. The
  checksum key bounds it to once per binary, but it is not free
* Bad, because a vendored binary is a supply-chain artefact in the repository. The `.sha256`
  proves it has not changed; it does not prove it was ever trustworthy
* Bad, because the build depends on three behaviours of an engine on a platform its own
  documentation does not list. Each is pinned by a check, so a vendor change fails loudly — but it
  will fail, and the fallback is a platform migration rather than a patch
* Bad, because vendoring `linux-amd64` alone means this repository builds on one architecture.
  Adding another is adding another 174 MB

### Confirmation

`tests/test_platform.py` reproduces the lock failure with DuckDB alone, no engine involved: a
subprocess cannot write while this process holds the file, and can the moment it lets go.
`tests/test_engine_pin.py` asserts the binary's hash matches the committed `.sha256` and that its
self-report matches the recorded string. `tests/test_mapping_rules.py` asserts six of the seven rules against every file in
`dab/mappings/` — M6 concerns relationships and lands with the first one — including that
`ingestion_strategy` is `FULL_LOG` and that `entity_effective_timestamp_expression` is
`extracted_at`. A data check counts `dab.<ENTITY>_desc` against its own distinct
(key, attribute, version) triples, because that base table is the only place the duplication
defect is visible: every presentation view hides it, and so would both of a question's acceptance
queries.

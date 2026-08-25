# ADR 0008 — Disposition of the three inherited red CI jobs

- Status: Accepted, not yet implemented. Implementation is the first task of
  the next session.
- Date: 2026-08-24
- Decided by: agent, under explicit delegation ("сделай выбор сам"). Julia can
  overrule any of it; the reasoning is written out here so overruling is cheap.
- Related: `BACKLOG.md` (CI-RED-1, CI-RED-2), `CURRENT_STATE.md`,
  `plan_23_08_2026.md` phases 0/A/D, ADR 0004 (governed actions
  effectively-once)
- Note on numbering: 0007 is deliberately skipped. `plan_23_08_2026.md` phase D
  reserves "ADR 0007" for the pgvector decision; taking that number here would
  force a rename later.

## Context

Phase 0.1 gave this repository a remote and its first CI run in the whole life
of the fork. That run was red on four jobs. A branch at the freeze tag
(`baseline/freeze-2026-08-23`, run 32775953483) established that three of the
four predate every phase-0 commit:

| Job | Cause | Inherited |
|---|---|---|
| `type-check` | the widened mypy scope | no — fixed, green since `fdeff62` |
| `test-integration` (both legs) | CI-RED-1, below | yes |
| `security` | CI-RED-2, below | yes |
| `pre-commit` | CI-RED-2, same `pip-audit` hook | yes |

Nothing here was caused by the audit work. All of it was invisible for months
because there was no remote to run CI against — which is itself the strongest
retrospective argument for phase 0.1 having been the highest-leverage half hour
in the plan.

Leaving them red is not free. A red job whose cause is "known" makes every
future reader hold an exception in their head, and that is precisely how a real
regression gets waved through. Phase 0's mandate was truth about gates; a
permanently red gate is a weaker form of the same problem phase 0 attacked.

## CI-RED-1 — governed-action reconcile writes a second run row

`tests/integration/test_governed_actions_postgres.py::test_timeout_reconciliation_never_dispatches_a_second_create`
fails `assert 2 == 1` on the `GovernedActionRun` count, on both Python legs,
identically at the freeze tag (`1 failed, 39 passed, 1 skipped`).

The downstream connector is *not* called twice — `connector.execute_calls == 1`
passes — so there is no duplicate side effect on the outside world. What is
wrong is the ledger: two runs recorded for one logical action, in the slice
whose entire claim is "never dispatches a second create".

Already localised: run rows are inserted at exactly one site,
`actions/postgres.py:407`, guarded by a lookup on
`(tenant_id, operation_key_digest)`; `complete_event` only selects. A second
row therefore means the reconcile path arrives with a different
`operation_key_digest` than the request path computed. That is a bounded
question, not an open-ended investigation.

### Decision

**Diagnose and fix it before any further phase-A work, timeboxed to one working
session.**

Three reasons, in order of weight:

1. **A.5 lands in this job.** The next real milestone is
   `tests/integration/test_shipment_status_e2e.py` — an integration test, in
   the job that is currently failing. A new test cannot be cleanly verified
   inside a job that is already red; the result would be "still 1 failed" and
   nobody could tell whether that 1 was the old one.
2. **The instrument comes before the measurement.** Phases A and B exist to
   produce trustworthy numbers. A CI that cannot go green produces no signal at
   all, only a habit of ignoring it.
3. **The cost is bounded and the site is known.** This is not open-ended kernel
   work.

**If the timebox expires without a root cause**, mark the test
`@pytest.mark.xfail(strict=True)` with a docstring naming this ADR and the
localisation above, and open it as a tracked defect in `BACKLOG.md`. Never
delete it, never plain-`skip` it, never weaken the assertion. `strict=True`
matters: an xpass then fails the suite, so an accidental fix cannot pass
unnoticed.

### Why not "after phase B"

Because phase B's output is numbers, and numbers produced while the test suite
is known-broken carry an asterisk that cannot be removed retroactively.

### Relationship to the slice rule

This is not a slice under the rule in `CLAUDE.md`, and it does not pretend to
be. It is a **repair of an existing claim**, and it belongs in the
"corrections" table of `EVIDENCE_INDEX.md`, not in the slice table. The rule
exists to stop agents from choosing locally-provable kernel work over wiring
and real data; it was never meant to forbid fixing a failing test.

## CI-RED-2 — three unpatched chromadb CVEs

`security` and the `pip-audit` pre-commit hook both fail on chromadb 1.5.9:
CVE-2026-45830, CVE-2026-45833, CVE-2026-45831. pip-audit reports no fix
version, and PyPI confirms it independently: **1.5.9 is the latest chromadb
release** (checked 2026-08-24). There is nothing to upgrade to.

Three options were on the table: a dated ignore, stay red, or stop depending on
chromadb by pulling phase D forward.

### Decision

**Dated `--ignore-vuln` entries for the three CVEs, with a review date of
2026-09-24 and an explicit unfreeze condition. Phase D is NOT pulled forward.**

Reasoning:

- **Against staying red:** these two jobs are the repository's only supply-chain
  alarm. Held red by a finding that cannot be acted on, they stop reporting the
  findings that *could* be acted on. An alarm that is always on is not an alarm.
- **Against pulling phase D forward:** replacing the vector store is a large
  architectural move, and phase D already schedules that decision on its merits
  within weeks, on measured recall/precision/latency numbers. Three CVEs in a
  component already queued for re-evaluation is a bad reason to make a good
  decision early — it would be choosing the architecture on a schedule set by
  someone else's disclosure calendar.
- **For the dated ignore:** the audit command already carries three
  `--ignore-vuln` entries (`CVE-2026-45829`, `GHSA-f4j7-r4q5-qw2c`,
  `CVE-2025-3000`), of which pip-audit reports one as matching chromadb
  ("ignored 1 in 1 package"). So ignoring by id is the established practice
  here, not an exception invented to get green — but note that those entries
  carry no review date, which is the part this ADR changes going forward.

### Conditions on the ignore, all mandatory

The thing that makes an ignore honest rather than a cover-up is that it expires
and it is visible:

1. Each entry carries an inline comment: CVE id, the date it was added, and
   "no fix version as of 2026-08-24".
2. **Review date 2026-09-24.** On that date, re-check for a fixed chromadb
   release. If one exists, upgrade and delete the ignores.
3. The ignore covers **these three CVE ids only**. Never a blanket
   `--ignore-vuln` on the package, never `--skip`, never dropping `--strict`.
4. A new chromadb CVE must still turn the job red. That is the whole point of
   ignoring by id.
5. It is listed in `CURRENT_STATE.md` as an accepted open risk, not buried in a
   workflow file.

If phase D later moves off chromadb, these entries are deleted with the
dependency, and this ADR's argument becomes a footnote in ADR 0007 rather than
its driver.

## Q2 — the labelling commitment (not decided here)

Q2 asks Julia to act as domain-owner-proxy: approving 100 labels in batches of
20, plus 40 double-annotated calibration routes. That is a claim on her time,
and no agent can decide it for her. It stays open.

What *is* decided is the fallback, so phase B is never blocked waiting:

**If Q2 is unanswered when phase B starts, proceed with agent-proposed labels
written to a corpus tagged `evidence_class: agent_labelled` — never
`real_labelled` — and every number published from that corpus says so in the
same sentence as the number.**

Phase B's gate is then explicitly **not** met. The corpus exists and the work is
useful, but "100 real labelled cases" stays open, and `EVIDENCE_INDEX.md` keeps
showing 0 under `real_labelled` until a human has approved them. An
agent-labelled corpus that quietly calls itself real would be FIN-11 all over
again, one directory to the left.

## Consequences

- CI can reach green, so a new red means a new problem. That is the point.
- One session of kernel work happens before phase A resumes. Accepted cost.
- The repository carries three accepted security exceptions with an expiry date
  on them. Visible in `CURRENT_STATE.md`, not only in a workflow file.
- Phase D keeps its independence: it will be decided on numbers, not on CVEs.

## Postscript, 2026-08-25 — the CI-RED-1 diagnosis above was wrong

The decision stands; the diagnosis it rests on does not, and it is left in
place above rather than edited so that the mistake stays legible.

This ADR asserted, twice, that "a second row therefore means the reconcile path
arrives with a different `operation_key_digest`", and called the failure a
ledger defect: "two runs recorded for one logical action". Neither is true.
Reconcile cannot insert a run at all — `create_or_replay` has exactly one
caller, `ActionGateway.request`, and the failing test calls it once. The ledger
held one run for one logical action the whole time.

The second row belonged to the test that runs before it. The count named no
tenant and leaned on row-level security to scope it, but the database is
module-scoped and the session connects as the owner — the cluster superuser in
CI, which RLS does not apply to even under FORCE ROW LEVEL SECURITY. The fix,
`0fdb29c`, names the tenant. Detail in `BACKLOG.md`.

Two things are worth keeping from this:

- **The localisation was right and the inference from it was not.** "Rows are
  inserted at exactly one site" was correct and checkable; "therefore reconcile
  computes a different digest" skipped the step of asking whether reconcile
  reaches that site at all. It does not. One `grep` for callers would have
  settled it before the ADR was written.
- **The safety property was never in doubt.** `execute_calls == 1` passed
  throughout, and so did the ledger. A reader of the ADR between 2026-08-24 and
  today would have believed this repository had an effectively-once defect in
  its governed-action audit trail. It did not.

The timebox the decision set (one working session) was not needed: root cause,
fix and green CI took well under it.

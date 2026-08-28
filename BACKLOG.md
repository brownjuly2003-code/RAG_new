# Backlog

## 2026-08-27 — open work after T-03

The admission gate landed (`6651964`, `36d4269`, `bd82297`). T-03 then made
its clarification terminal observable through `/api/ask`, behind the separate
default-off `RESOLUTION_CLARIFICATION_JOURNEYS` allowlist. These four items are
the remaining queue; all four are verified, none is a guess.
Detail: [capsule](docs/evidence/a6-journey-admission-and-clarification.md).

- **T-04** — an empty Evidence bundle cannot tell shadow-disabled,
  journey-declined and producer-failure apart. The tab already renders
  `terminal_state` and `reason_codes` for a persisted journey
  (`static/admin.js`); a declined request writes nothing, because
  `observe()` returns None before the sink. Reproduced:
  `observer_result None`, `sink_records []`. Record a minimal admission
  outcome at the producer (`resolution/composition.py` /
  `api/routers/conversation.py`) before returning None, then distinguish
  the three states in API/UI. A decline must still not touch the answer,
  call the source or policy ports, or cost measurable time.
- **T-06** — a multi-word domain noun can still be assembled across a
  message boundary. File: `resolution/application/shipment_status.py`.
  Review finding F-T-01-16, reproduced:
  `_is_admitted(('This concerns air', 'waybill status.'))` still returns
  True.
- **T-07** — report-level reproducibility does not cover the corpus, and
  `rev-parse HEAD` is resolved separately from the `HEAD:path` reads.
  File: `evaluation/journey_admission.py`. Review findings F-T-02-8 and
  F-T-02-9, both reproduced in-process.
- **T-09** — the paradigm validator's single-space check cannot fire,
  because `split()` has already collapsed the separator. File:
  `resolution/application/shipment_status.py`. Review finding from T-08
  pass 4, reproduced: stem `'авиа  накладн'` (two spaces) is accepted.

## 2026-08-24 — routing below is superseded

Stream status now lives in [`ROADMAP.md`](ROADMAP.md); the next action lives
in [`CURRENT_STATE.md`](CURRENT_STATE.md). Everything under "Current routing
override" and "Paused routing" below is the pre-audit autopilot queue, kept
for history. In particular **REL-03D is frozen** — do not pick it up as the
next local-only candidate.

## 2026-08-25 — phase B is blocked on data, and B.1 is why

B.1 labelled all 100 air-cargo cases
([capsule](docs/evidence/b1-aircargo-journey-labels.md)). **Not one names a
shipment.** 66 belong to no kernel journey; the other 34 are blocked by
`no_shipment_binding` before the journey starts. Nothing in the corpus can
reach an observation, a policy decision or a claim, so:

- **B.2** (extend the fixture TMS to cover the cases) has nothing to cover.
- **B.3** (first real numbers on the 100 cases) cannot be run — VR precision,
  VRY and `pass^k` are all undefined on a corpus that starts no journey.
- **B.5** (corpus v1.0 at `real_labelled`) needs cases the labels cannot
  manufacture.

`expected_terminal` is `verified` for 100/100 for the same reason: these are
questions *about* air-cargo work, not requests *inside* it, so the corpus
also exercises no escalation, disclosure or refusal path.

**What a corpus that can measure resolution has to contain**, when the data
arrives — each case needs the identifier a journey runs on (an AWB or shipment
id the source system actually holds), the state of that shipment at the time
the request was made, and the outcome the request actually got. Without those
three, a case is a knowledge question no matter how it is labelled. Roughly a
third of the corpus should end somewhere other than `verified` —
clarification, escalation, refusal — or the safety paths stay unmeasured.

**Do not** close this by writing more fixture instances. The repository has 17
already; more of them is exactly the move FIN-02 named.

## Known-red CI, inherited (not caused by the phase-0 work)

Both are decided — [ADR 0008](docs/adr/0008-inherited-ci-red-disposition.md).
CI-RED-1 is **closed** (2026-08-25, `0fdb29c`); CI-RED-2 is **open pending
approval** of the `.pre-commit-config.yaml` half.

Both reproduce on `baseline/freeze-2026-08-23`, a branch at the freeze tag
that predates every phase-0 commit (run 32775953483). They were invisible for
months because this repository had no remote and CI had never run.

### CI-RED-1 — the ledger was right and the assertion was wrong — CLOSED

`tests/integration/test_governed_actions_postgres.py::test_timeout_reconciliation_never_dispatches_a_second_create`
failed `assert 2 == 1` on the `GovernedActionRun` count. ADR 0008 read that as
a ledger defect: "a second row therefore means the reconcile path arrives with
a different `operation_key_digest` than the request path computed". **That
diagnosis was wrong.** The ledger records exactly one run per logical action;
the count was reading rows that belonged to a different test.

`GovernedActionRun` rows are inserted at exactly one site,
`actions/postgres.py:407`, reached from exactly one caller,
`actions/application.py:369` inside `ActionGateway.request`. The failing test
calls `request` once, so it writes one run. Reconcile goes through `_lease`,
`complete_event` and `record_postcondition`, none of which insert a run — so
"reconcile writes a second row" was not a reachable state.

What actually happened: the count named no tenant and relied on row-level
security to scope it. `action_database_url` is module-scoped, so all four
tests in the file share one database, and `action_session_factory` connects as
the database owner — which in CI is the cluster superuser the Postgres service
image creates from `POSTGRES_USER`. A superuser is exempt from RLS even under
FORCE ROW LEVEL SECURITY, so the count returned every tenant in the file: one
run from the idempotency test that runs before it, plus its own. That test
passed only because it happens to write first.

Fixed 2026-08-25 in `0fdb29c` by naming the tenant in the counts — the claim
each test is actually making — and by additionally asserting that the one row
is *the* run the test created, which no longer depends on execution order.
Verified green on both Python legs, run 32831583779. Tenant isolation itself
stays asserted where it always was, through the NOBYPASSRLS role in
`test_forced_rls_and_transition_guards_fail_closed`.

Carried forward as a smaller open item: **the integration suite runs as a
Postgres superuser**, so RLS is inert for every assertion that does not go
through a runtime role. The other three Postgres modules already route their
isolation assertions through such a role, so nothing is currently unguarded —
but a future test that forgets to will pass for the wrong reason, exactly as
this one did. A non-superuser application role for the whole integration job
would remove the trap; not scheduled.

This was a repair, not a slice, and it is in the corrections table of
`EVIDENCE_INDEX.md`. The slice rule exists to stop agents choosing
locally-provable kernel work over wiring and real data; it was never meant to
forbid fixing a failing test.

### CI-RED-2 — three unpatched chromadb CVEs

`security` and the `pip-audit` pre-commit hook both fail on chromadb 1.5.9:
CVE-2026-45830, CVE-2026-45833, CVE-2026-45831. pip-audit reports no fix
version, and PyPI confirms it independently: **1.5.9 is the latest chromadb
release** (checked 2026-08-24). There is nothing to upgrade to.

So there are three options, not two:

1. dated `--ignore-vuln` entries with a review date — the pattern three
   earlier CVEs already follow;
2. leave CI red until upstream ships a fix;
3. stop depending on chromadb — which is phase D of the plan (the pgvector
   spike, FIN-09) arriving early with an extra argument behind it.

**Decided 2026-08-24, [ADR 0008](docs/adr/0008-inherited-ci-red-disposition.md):
option 1 — ignore the three CVE ids, with a review date of 2026-09-24.**

Staying red was rejected because these two jobs are the only supply-chain alarm
here; held red by a finding nobody can act on, they stop reporting the ones
that could be. Pulling phase D forward was rejected because replacing the
vector store is an architectural decision phase D already schedules on measured
numbers within weeks — three CVEs in a component already queued for
re-evaluation is a bad reason to make a good decision early.

The ignore is only honest if it expires and is visible: by CVE id only, never a
blanket ignore, never dropping `--strict`, inline comment with the date, and
listed as an accepted risk in `CURRENT_STATE.md`. A new chromadb CVE must still
turn the job red.

**Applied 2026-08-25 (`af0d4fd`)** with Julia's approval, across all four
places the ignore set has to match — the hook, the CI job,
`scripts/local-gate.ps1` and `scripts/autopilot.ps1` — plus the expected set in
`tests/test_precommit_config.py`, which is the guard that requires them to
agree. **REVIEW 2026-09-24.**

## Accepted design limits

### Shadow evidence snapshots do not close their previous range (A.1b)

`resolution/persistence.py` writes each snapshot with an open-ended validity
range and deduplicates by identity, so replaying a run rewrites the same row.
What it does not do is close the previous range when a source later reports
*different* content for the same logical key. Postgres will reject that insert
on `ex_evidence_snapshots_temporal_identity` — correctly, since two authorities
cannot both be right about the same key at the same instant — and the shadow
will log the failure and record nothing for that run.

Not a defect to fix here: closing ranges is real bitemporal bookkeeping and
belongs with the source adapters that know when an observation supersedes
another, not with an observer that sees one run at a time. The fixture TMS is
static, so nothing exercises it yet; a real TMS in phase B would, and that is
where it should be handled.

## Current routing override — Trust Foundation REL-03

Владелец явно поручил Codex решить маршрут самостоятельно и найти необходимые
данные в сети. Выбран отложенный REL-03 consistency/SLA gate. REL-03A
design-only decision доставлен на `2d9008a`:
PostgreSQL primary становится authority для fenced same-session turns, а
process memory/Redis остаются non-authoritative. Точный контракт, primary web
sources и promotion thresholds находятся в
[`docs/adr/0006-durable-multi-replica-session-turns.md`](docs/adr/0006-durable-multi-replica-session-turns.md).

REL-03B durable session admission/abort contract доставляется scoped commit,
содержащим Update-237: revision `031`, ORM, `SessionService`, forced-RLS turn
table и real PostgreSQL concurrency evidence. Exact SHA определяет Actual Git.

REL-03C fenced terminal message-pair commit + durable history snapshot
primitives доставлен implementation commit **`49bc966`**: exact request-bound
fencing, atomic pair/version/turn transaction и deterministic PostgreSQL
contention/rollback evidence. Верхний Update-239 в handoff отдельно фиксирует
runtime/replay gaps и не является новым implementation claim.

Следующий local-only candidate: **REL-03D sync `/api/ask` durable lifecycle
wiring**. Не добавлять SSE/timeout wiring, compatibility removal, live
promotion, deploy или push в тот же slice. До lost-response replay claim явно
решить mapping exact stored response к конкретному `turn_id`.

Resolution Product G8 остаётся локально завершённым на `82137c8`; full Slice G
остаётся open beyond synthetic evidence и не считается release-approved.

## Paused routing — Resolution Product

Текущая выбранная владельцем очередь находится в
[`docs/architecture/rag-new-architecture.md`](docs/architecture/rag-new-architecture.md), а точный scope и DoD — в
[`docs/architecture/migration-plan.md`](docs/architecture/migration-plan.md).
Срезы C1–C8, D, E1, E2, F и G1–G8 завершены локально. G8 deterministic
synthetic release-safety gate implementation, canonical artifact, tests и docs
доставляются scoped commit, содержащим этот update; точный SHA определяет
Actual Git. Срез начат от clean `master` at `2a23416`; remote отсутствует.
Push/deploy/live/external actions не выполнялись. Tests-first RED был
ожидаемым public `ImportError`.

G8 builder заново валидирует exact G7 manifest и требует полный set из семи
manifest-bound surface checks: contract, policy, retrieval, connector,
postcondition, disclosure и evaluator infrastructure. Любой `FAIL`, `ERROR`
или `SKIPPED` даёт safety `FAIL`; missing/duplicate/foreign checks и
forged/stale release evidence fail closed до materialization.

QA follow-up 1/1 закрыл semantic major: all-surface `PASS` больше не может
скрыть непустой candidate `unverified_claimed_scenario_ids`. Checked-in failing
artifact содержит constructed contract failure и `case-01`; SHA-256
`38875d41de32af06e851ae46b0eca267f11d32551ce8ce81ef799b4de2830991`.
Даже synthetic safety `PASS` остаётся `unconfirmed`,
`synthetic_safety_only`, `business_claimable=false` и
`deployment_authorized=false`.

Focused final before QA: 15 passed; post-QA: 16 passed. Independent Resolution gate: 158 passed +
одна известная Starlette/httpx2 warning; Ruff/three-file format green; strict
MyPy проверил 9 explicit source roots без issues с project boundary
`--follow-imports=skip`. Final docs/diff checks остаются commit gate.

Полный Slice G остаётся открыт beyond local deterministic synthetic safety.
Следующий local G slice автоматически не выбран: owner-approved metric
thresholds, live/shadow outcomes, observed recontact, latency/cost, confidence
bounds, runtime/DB release decision, canary и promotion требуют отдельной
authority и evidence. Полная truth — в
[`docs/SESSION_HANDOFF.md`](docs/SESSION_HANDOFF.md) и
[`g8-synthetic-release-safety-gate.md`](g8-synthetic-release-safety-gate.md).

Закрывающие C7/C8-капсулы:
[`c7-resolution-restore-smoke.md`](c7-resolution-restore-smoke.md) и
[`c8-mac-postgres-deployment.md`](c8-mac-postgres-deployment.md).
Общая session-капсула:
[`docs/SESSION_HANDOFF.md`](docs/SESSION_HANDOFF.md).

Разделы ниже относятся к унаследованному Trust Foundation remediation stream.
Не выбирать их автоматически, пока текущий handoff не вернёт routing к этому
потоку или владелец не попросит об этом явно. Они сохраняются как открытый
product/release debt и не считаются закрытыми.

## Inherited Trust Foundation source (2026-08-03) — step 4.8d3e locally verified @ `f899ba5`

**Inherited backlog source:**
[`rag-remediation-plan-2026-08-03.md`](rag-remediation-plan-2026-08-03.md).
It contains only open DoD from `plan_sol_23_07_26` plus the 2026-08-03 LLM/RAG
gaps; the old plan remains historical implementation evidence. Audit finding
status remains in [`audit_gpt_23_07_26.md`](audit_gpt_23_07_26.md).

The 2026-07-27 «project closure / empty queue» narrative remains **revoked**.
Plan remains **ACTIVE**; project/production release is **not** complete.
P0 **implementation** is locally remediated; **OBS-01** is locally remediated
at `5a9f857`. Plan step 1 is **locally complete**. Plan step 4 is **in
progress**: slices **4.1** (`b7faa19`), **4.2** (`4f93038`), **4.3**
(`6dc6fe4`), **4.4** (`1cebd14`), **4.5** (`35e4bb9`), **4.6**
(`d13804b`), **4.7** (`705a3cc`), **4.8a** (`c015ba8`, `ca15c1a`), and
**4.8b** (`74d187c`), **4.8c** (`8594675`), **4.8d1** (`c160af8`), and
**4.8d2** (`bb3f00b`) plus **4.8d3a** (`47902f5`), **4.8d3b** (`9534f5b`),
**4.8d3c** (`196785d`), **4.8d3d** (`3f7f337`), and **4.8d3e** (`f899ba5`)
are locally verified
(ING-01 further partially locally remediated; TEN-03 locally remediated;
ING-02 lock + manifest + staging + runtime-publish + validated manager rollback
and trusted retention inventory/policy/executor/Chroma-adapter/config contracts
partially remediated).
Full plan DoD / production release / project closure are **not** complete.
Historical autopilot/safe tasks below remain evidence only — not the active
queue.

### Latest atomic slice (local code)

**Plan step 4.8d3e fail-closed retention budget is locally complete at `f899ba5`.**

`VECTORDB_RETENTION_MAX_VERSIONS` now defaults to the safe active + previous
budget of `2`; malformed values and budgets below `2` fail closed before
startup dependency probes. Focused red→green evidence and the adjacent closure
gate passed **99 tests**; scoped Ruff, locked Mypy, Python 3.11 compatibility,
boundary, and diff checks are clean. Runtime retention wiring, broader fault
injection, operator wiring, and immutable/versioned originals remain open; the
setting has no runtime consumer and no real collection was deleted.

**Next local-only candidate (not started): 4.8d3f publication inventory
wiring.** Record a validated versioned collection in trusted inventory under
the existing tenant lock, with explicit record-vs-publish failure semantics.
Do not invoke retention deletion or add an operator surface in the same slice.
See [`docs/SESSION_HANDOFF.md`](docs/SESSION_HANDOFF.md) for acceptance
boundaries and Windows verification caveats.

### Live / external P0 gates (not local-complete)

Track separately from the next code slice — do **not** list as done work:

- **TEN-01/02:** real PostgreSQL migration upgrade/downgrade; live two-tenant
  restart drill
- **OPS-01:** Docker image build + pg/age tool smoke; live PostgreSQL; kind/live
  cluster install; app pod recreation; clean-namespace restore to a
  **disposable** DB (never production DSN for `pg_restore --clean`); known-query
  smoke; measured RPO/RTO
- **ING-01 remaining:** live Redis/Postgres/Celery worker-outage/recovery drill;
  real PostgreSQL
  upgrade/downgrade through migrations `019`/`020`/`021`

Step 4 remains **in progress** (4.1–4.8c plus 4.8d1–d3e locally done; 4.8d
remainder and live step-4 DoD open). Step 5 remains **open / partially
remediated** (trace identity done; timeout cancellation, bounded capacity,
session concurrency/history ordering, sticky experiment propagation still open).
Steps 6–10 remain open. ING-02 is **partially locally remediated** by the
same-tenant mutation lock plus manifest/staging/runtime-publish and validated
manager rollback plus trusted retention inventory contracts; retention
runtime wiring and operational rollback remain open.
Live GraceKelly/Mistral benchmarks remain explicit opt-in only and are **not**
this slice.

## Project Closure note (2026-07-27) — historical

Superseded by the 2026-08-02 audit revalidation. See
[`docs/PROJECT_CLOSURE.md`](docs/PROJECT_CLOSURE.md) banner. Deferred
runtime/benchmark/refactor dispositions in that file remain historical context
only until re-decided under the audit plan.

## Autopilot Task Queue

> Historical autopilot snapshot (pre-audit reopen). Former note: no active
> non-live autopilot-safe tasks; `AP-1` closed by `d3f8eb7`, `AP-2` by `cd6e7ba`.
> Use `docs/plans/2026-05-01-backlog.md` for older product context. The live
> GraceKelly/Mistral benchmark lane requires staged runtime and explicit
> opt-in only, and is not the current audit-plan next slice.
> 2026-05-30 branch note: Colab remote benchmark setup is merged to `master`
> through PR #1 at `415d4c8`; current state is in `AGENT_STATE.md` and
> `docs/sessions/next-session-3-subagents.md`. Master CI and Pages deploy passed.
> 2026-05-30 live opt-in note: commit `7b0d9ee` closed a runtime quality
> blocker by failing closed on incompatible Chroma embedding dimensions. A
> separate ignored eval collection passed a 3-case live Mistral regression; the
> default local `rag_docs_default` collection still needs a deliberate rebuild
> before it should be used for full RAG quality measurement.
> 2026-05-30 R3/R4 note: commit `71367a7` batches multi-document
> `grade_docs` into one structured LLM call with fallback to the old per-doc
> path. Master CI and Pages passed on that commit.
> 2026-05-30 R4 observability note: commit `c0b6d24` adds trace events for
> `verify_facts` extract-claims and per-claim LLM calls. Master CI and Pages
> passed on that commit.
> 2026-05-30 R7 note: commit `c964211` expands the checked-in RU curated seed
> set from 20 to 35 cases and adds a guard test. Local mock regression passed
> 35/35; master CI passed. A final CI guard also makes PR `regression-eval`
> track `evaluation/curated_cases.jsonl` changes.

## Historical Safe Tasks

> Historical safe-task snapshot. The tasks below are closed in current history;
> use `docs/plans/2026-05-01-backlog.md` for older product context. The only
> remaining benchmark lane is live GraceKelly/Mistral work: explicit opt-in only.
> It requires staged runtime and is not an active local backlog item.
> **Historical note:** active remediation moved to
> `rag-remediation-plan-2026-08-03.md` on 2026-08-03.

## Safe Task 1: Add a Local Gate Wrapper

- Allowed files/directories: `scripts/`, `README.md`, `docs/`
- Acceptance criteria: a non-mutating local gate command documents and runs the same safe checks used by the runner.
- Required verification: run the new wrapper in dry-run or list mode, then run `git diff --check`.
- Forbidden scope: `.env`, `deploy/`, Docker, Helm, live services, dependency changes, production DB, external APIs.

## Safe Task 2: Document Windows Test Workflow

- Allowed files/directories: `README.md`, `docs/`
- Acceptance criteria: Windows-specific pytest guidance is consolidated with the current `-p no:schemathesis` and `.tmp/pytest` basetemp recommendation.
- Required verification: `git diff --check`.
- Forbidden scope: source code, tests, CI, deploy configs, generated reports.

## Safe Task 3: Tighten Provider Settings Tests

- Allowed files/directories: `tests/test_provider_settings.py`, `tests/test_mistral_provider.py`, `config/providers.yml`
- Acceptance criteria: tests cover placeholder or missing direct-provider API keys without making network calls.
- Required verification: `python -m pytest tests/test_provider_settings.py tests/test_mistral_provider.py -q -p no:schemathesis --basetemp=.tmp/pytest` and `ruff check tests/test_provider_settings.py tests/test_mistral_provider.py config/providers.yml`.
- Forbidden scope: `.env`, real API keys, live provider calls, production config, deploy files.

## Safe Task 4: Add Autopilot Runner Tests

- Allowed files/directories: `scripts/autopilot.ps1`, `tests/`, `docs/`
- Acceptance criteria: protocol behavior for PAUSE, BLOCKED, and allowed paths is covered without invoking real `pi` or `codex`.
- Required verification: relevant new tests plus `powershell -ExecutionPolicy Bypass -File scripts/autopilot.ps1 -DryRun`.
- Forbidden scope: scheduler installation, production config, secrets, live external services.

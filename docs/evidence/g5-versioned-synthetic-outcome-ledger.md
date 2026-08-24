# G5 versioned synthetic outcome ledger and metrics

## Goal

Add a pure-local, immutable synthetic outcome ledger and a deterministic report
for VR precision, VRY, and eligibility coverage. Every metric is bound to one
exact corpus, replay manifest, full replay plan, and replay result.

## Metric contract

- The full versioned synthetic corpus roster is the fixed reporting universe.
- `VR precision = verified claimed auto-resolutions / all claimed
  auto-resolutions`; structurally unresolved cases are conservatively presumed
  claimed so missing evidence cannot improve precision.
- `VRY = verified claimed auto-resolutions / all eligible synthetic cases`;
  unknown or malformed eligibility is conservatively included.
- `eligibility coverage = confirmed eligible synthetic cases / all synthetic
  corpus cases`.
- A claimed outcome is verified only when its seven normalized VR gates are
  true and all three exact replay trials pass.
- These definitions are explicitly provisional synthetic evaluation semantics;
  they do not claim product-owner approval or live business outcomes.

## Tasks

- [x] Add RED tests for fixed denominators, exact artifact bindings, three-trial
  verification, malformed evidence, deterministic serialization, and privacy.
- [x] Implement immutable versioned ledger records and canonical SHA-256
  identities.
- [x] Implement deterministic fail-closed metric reporting with explicit
  structural issues and undefined zero-claim precision.
- [x] Run one batched independent QA/fix pass and proportional verification.
- [x] Update active architecture and durable state/handoff records, then create
  one scoped explicit-pathspec commit.

## Done When

- [x] Missing, duplicate, extra, foreign, or drifted outcome evidence cannot
  raise a numerator or shrink a fixed denominator.
- [x] Corpus, manifest, replay plan, replay result, scenario binding, and ledger
  identities are exact and canonical.
- [x] Reports publish count pairs for all three metrics together and expose
  whether a zero-denominator precision value is defined.
- [x] Canonical artifacts contain only stable identities, booleans, counts, and
  issue codes: no raw candidate/world/fault/oracle/response payload.

## Boundary

Synthetic local evaluation only. Live outcomes, runtime/database integration,
shadow/canary, product thresholds, recontact observation, business baselines,
promotion, deploy, push, and production defaults remain out of scope.

## Delivery status

G5 code/test delivery is exact local commit `8030716`. This document may also
appear in a later docs-only transparency commit; that does not change the code
delivery identity. The metric definition is permanently explicit about its
provisional v0.1 status,
seven normalized VR checks, synthetic evidence class, assumed recontact window,
and `business_claimable=false` boundary.

Each case-level outcome record binds the exact manifest, replay result,
scenario binding, three ordered replay-trial digests, and an opaque outcome
evidence digest. Verified credit requires `ELIGIBLE`, `CLAIMED_AUTO`, all seven
checks `PASS`, and three exact passing trials. A correct clarification or
escalation therefore remains a replay success without becoming a verified auto
resolution.

The full compiled corpus is the fixed reporting universe. Missing, duplicate,
foreign, or drifted records are conservatively presumed eligible and claimed;
global identity failures zero numerator credit and use the full corpus for both
conditional denominators. Zero-claim and zero-eligible ratios are explicitly
`UNDEFINED`, never perfect.

Tests-first RED was the expected public import failure. Focused verification
passed seven tests. The single QA follow-up found no semantic blocking/major
issue and made only an unused-import/format correction. Independent
verification passed 129 Resolution tests with one known Starlette/httpx2
warning; Ruff, three-file format check, and strict MyPy over six pure Resolution
sources were green.

Full Slice G remains open. The next safe named slice is G6: an exact-definition-
bound synthetic baseline/candidate outcome comparison and case-disposition
breakdown, still without live shadow claims, thresholds, promotion, deploy, or
push.

## Artifact truth

Delivered at `8030716`:

- immutable versioned Python models for the metric definition, outcome record,
  ledger, metrics, issues, and report;
- canonical JSON and SHA-256 helpers;
- a fail-closed report builder with exact corpus/manifest/coverage/plan/result,
  scenario-binding, and three-trial bindings;
- seven focused tests using a constructed three-case synthetic corpus.

Not delivered by G5:

- a checked-in metric-definition JSON/SHA instance;
- a checked-in 17-case outcome-ledger or outcome-report snapshot for the G4
  canonical corpus;
- a baseline/candidate pair or comparison report;
- an empirical numeric VR precision, VRY, or eligibility-coverage result for
  the canonical 17 cases;
- owner-approved eligibility/recontact semantics or any live/business outcome.

Therefore G5 proves the deterministic accounting contract. It does not claim a
materialized full-corpus run, a business baseline, or release readiness.

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

G5 is locally complete in the scoped commit containing this document. The
metric definition is permanently explicit about its provisional v0.1 status,
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

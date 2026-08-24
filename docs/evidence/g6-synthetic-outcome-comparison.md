# G6 exact-bound synthetic outcome comparison

## Goal

Materialize full-corpus synthetic baseline and candidate inputs, then compare
their exact-bound outcome counts and per-case dispositions without producing a
threshold, release, promotion, or live-business verdict.

## Tasks

- [x] Add RED tests for exact input binding, compatible distinct runs,
  fail-closed definition/universe/run drift, count-pair deltas, exhaustive
  case transitions, canonical privacy, and the checked-in 17-case artifacts.
- [x] Implement immutable comparison inputs, case dispositions, count-pair
  deltas, a deterministic comparison report, canonical JSON/SHA-256 helpers,
  and public exports.
- [x] Materialize versioned baseline, candidate, and comparison JSON/SHA-256
  artifacts from the full canonical shipment-status corpus.
- [x] Review the complete diff once, batch any correctness fixes, and run the
  focused comparison gate.
- [x] Update the active architecture, backlog, state, and handoff records once.
- [x] Run proportional Resolution, Ruff, format, strict MyPy, and diff gates;
  then create one scoped explicit-pathspec local commit.

## Done When

- [x] Both inputs cover exactly the canonical 17 cases and share one exact
  metric-definition and corpus identity while retaining independently bound
  manifest, plan, result, ledger, and report identities.
- [x] Any internal binding drift or cross-pair definition/universe drift fails
  closed before a comparison can be emitted.
- [x] Every case appears in exactly one baseline-to-candidate disposition
  bucket, and every metric exposes only baseline/candidate count pairs and
  arithmetic deltas.
- [x] Canonical artifacts contain no raw candidate, world, fault, oracle, or
  response payload and remain explicitly synthetic and non-business-claimable.

## Boundary

Pure local synthetic evaluation only. Runtime/database/loop integration, live
shadow traffic, owner approval, business baselines, thresholds, canary,
promotion, deploy, push, and external connectors remain out of scope.

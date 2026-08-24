# G8 synthetic release safety gate

## Goal

Evaluate one exact G7 evidence manifest against the mandatory deterministic
release-safety surfaces while keeping every synthetic result non-authorizing
and independent of still-absent owner thresholds or live outcome evidence.

## Tasks

- [x] Add RED tests for exact G7 binding, the complete seven-surface check set,
  every non-pass status failing closed, deterministic ordering, caller verdict
  rejection, canonical privacy, and a checked-in failing fixture.
- [x] Implement immutable safety checks/report, typed compatibility failures,
  a derived gate builder, canonical JSON/SHA-256 helpers, and public exports.
- [x] Materialize a G7-bound shipment-status safety report JSON/SHA-256 pair
  whose constructed contract failure is explicit and non-authorizing.
- [x] Perform one complete QA review/fix pass and focused verification.
- [x] Run the proportional Resolution, Ruff, format, strict MyPy, docs, and
  diff gates; update durable status once and create one scoped local commit.

## Done When

- [x] Missing, duplicate, foreign-manifest, or invalid checks cannot emit a
  report, and a forged/stale G7 manifest cannot enter the gate.
- [x] Each required surface independently produces safety `FAIL` for `FAIL`,
  `ERROR`, or `SKIPPED`; only seven exact `PASS` checks with no unverified
  claimed outcome produce safety `PASS`.
- [x] Neither caller input nor direct model construction can override the
  derived status or failed-surface roster.
- [x] Canonical output contains only stable identities, digests, normalized
  statuses, and fixed `synthetic_safety_only` non-authorizing semantics.

## Boundary

Pure local deterministic safety-gate evidence only. No owner-approved metric
thresholds, live/shadow measurements, release approval, production readiness,
runtime/DB wiring, canary, promotion, deploy, push, or external connector is
created by this slice.

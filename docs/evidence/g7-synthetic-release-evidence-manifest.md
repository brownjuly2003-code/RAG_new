# G7 synthetic release evidence manifest

## Goal

Bind the complete G6 baseline input, candidate input, and derived comparison
report into one immutable, reproducible local evidence manifest without
creating a release, threshold, approval, promotion, or business-readiness
verdict.

## Tasks

- [x] Add RED tests for exact three-artifact binding, deterministic
  reproduction, fail-closed role/reference/report drift, canonical privacy,
  and a checked-in 17-case manifest artifact.
- [x] Implement an immutable evidence-only manifest, typed binding failures,
  a builder that independently reconstructs the comparison, canonical
  JSON/SHA-256 helpers, and public exports.
- [x] Materialize the versioned shipment-status manifest JSON/SHA-256 pair
  from the existing full-corpus G6 fixture.
- [x] Review the complete diff once, batch any correctness fixes, and run the
  focused G7 gate.
- [x] Update the active architecture, backlog, state, and handoff records once.
- [x] Run proportional Resolution, Ruff, format, strict MyPy, and diff gates;
  then create one scoped explicit-pathspec local commit.

## Done When

- [x] The manifest identifies the exact baseline/candidate comparison inputs,
  all nested run artifacts already referenced by G6, and the exact comparison
  report digest.
- [x] The builder rejects swapped roles, stale/foreign input references, and
  any report that differs from an independently reconstructed report.
- [x] Reconstructing the same semantic inputs produces identical canonical
  JSON and SHA-256 identity.
- [x] Canonical output remains `synthetic_local`, owner-unconfirmed,
  non-business-claimable, and contains no raw candidate, world, fault, oracle,
  response, threshold, readiness, release-decision, or promotion payload.

## Boundary

Pure local synthetic evidence packaging only. This slice does not add a
runtime/DB release gate, owner approval, live shadow traffic, empirical
metrics, confidence bounds, latency/cost, canary, promotion, deploy, push, or
external connectors.

# G4 versioned Resolution corpus and coverage

## Goal

Add a pure local, versioned persona/adversarial/fault corpus whose branch and
required-fault coverage is derived from the pinned contract and bound exactly
to a replay manifest.

## Tasks

- [x] Add RED tests for derived branch coverage, fixed fault denominators,
  exact manifest binding, canonical privacy, and fail-closed drift handling.
- [x] Implement immutable corpus assets, scenario compilation, canonical
  serialization/digests, and structural coverage reports.
- [x] Add a checked-in synthetic shipment-status corpus artifact covering all
  terminal paths and required fault surfaces.
- [x] Run one batched independent QA/fix pass and proportional verification.
- [x] Update the active architecture and durable handoff/state records, then
  create one scoped explicit-pathspec commit.

## Done When

- [x] Branch coverage is derived only from valid hidden paths and has the exact
  pinned-contract denominator.
- [x] Every required fault target remains in the denominator when its scenario
  is absent, drifted, or unbound.
- [x] Corpus identity and every scenario fixture match the replay manifest;
  missing, extra, foreign, or drifted evidence makes completeness false.
- [x] Canonical artifacts contain only stable identities, digests, structural
  coverage, and issues: no raw candidate/world/fault/oracle/response payload,
  business KPI, promotion, or release verdict.

## Boundary

Pure synthetic local evaluation only. Runtime routing, database persistence,
shadow/canary, live services, business metrics, promotion, deploy, push, and
production defaults remain out of scope.

## Delivery status

G4 is locally complete in the scoped commit containing this document. The
versioned synthetic shipment corpus has 17 terminal-path scenarios, three
persona definitions, four adversarial intents, and seven required fault
surfaces. Its compiler revalidates hidden paths against the exact contract and
derives coverage rather than accepting caller claims. The checked-in canonical
snapshot is hash-guarded and covers all 22 contract branches and all seven
required fault targets.

Coverage is credited only when the manifest contract pin, scenario-set pin,
scenario membership, and complete scenario bindings match the compiled corpus.
Foreign pins zero both numerators while preserving the 22-branch and
seven-fault denominators. Missing, extra, or drifted scenarios add explicit
issues and cannot count toward completeness.

Tests-first RED was the expected import failure. Focused implementation
verification reached nine passing tests. The single QA follow-up found and
fixed foreign-pin numerator credit, confirmed its own RED, and finished with
nine tests plus Ruff/format and one-source strict MyPy green. Independent
verification passed 117 adjacent Resolution tests with one known
Starlette/httpx2 warning; Ruff and 12-file format check were green, and strict
MyPy passed across five Resolution sources.

Full Slice G remains open. The next named slice is G5: a versioned synthetic
outcome ledger and deterministic VR precision/VRY/eligibility coverage report
with fixed denominators, still without live outcome claims, shadow/canary,
promotion, deploy, or push.

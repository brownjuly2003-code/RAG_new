# G1 deterministic resolution grader

## Goal

Add a pure local scenario kernel that compiles every explicit contract branch
into a stable coverage target and grades hidden expected state without exposing
that state to candidate generation.

## Tasks

- [x] Add RED tests for the 22 shipment-contract branch targets, connected
  terminal paths, hidden expected-state isolation, exact state grading, and
  fail-closed evaluator infrastructure.
- [x] Implement `evaluation/resolution` scenario compilation and deterministic
  grading without changing the shipment runtime.
- [x] Run one independent QA/fix follow-up and close any findings in one batch.
- [x] Run focused tests, Ruff/format, strict MyPy and diff checks; update current
  durable status once and create one explicit-pathspec local commit.

## Done When

- [x] The pinned shipment contract deterministically compiles to 22 distinct
  `(step, event)` targets and rejects unknown, disconnected, non-terminal, or
  wrong-terminal expected paths.
- [x] Fluent text cannot compensate for a wrong contract, branch, terminal,
  policy/evidence/connector/postcondition/disclosure state, or evaluator
  infrastructure error/skip.
- [x] Candidate generation receives only public scenario input; VR/VRY,
  recontact, replay manifests and promotion are not claimed.

## Delivery status

G1 is locally complete in the scoped commit containing this document; resolve
its exact SHA from Actual Git after commit. The measured baseline was 30
existing fixture scenarios, while the pinned shipment contract contains 6
steps and 22 explicit branch edges. `evaluation/resolution` did not exist
before G1, and the tests-first RED failed with the expected
`ModuleNotFoundError`.

The pure `evaluation/resolution` kernel now emits 22 stable targets bound to
the exact contract id, version, and digest; validates connected
entrypoint-to-terminal hidden paths; exposes only `CandidateScenarioInput` to
candidate generation; and grades the exact contract, branch, terminal,
reasons, and canonical flat state. Fluent text cannot rescue a wrong state,
and evaluator `ERROR` or `SKIPPED` results fail closed.

Focused verification passed 18 tests. The independent adjacent gate passed 68
tests with one known Starlette/httpx2 warning. Ruff check, four-file format
check, strict MyPy with `--follow-imports=skip` over three source files, and
`git diff --check` were green. The design run completed; the single QA
follow-up found no blocking or major issue and made only import/format changes.

The next named slice is G2: replay manifest plus impact selection/reporting
only. It does not authorize live promotion.

## Boundaries

Pure Python and fixtures only. Do not change the Resolution runtime, database,
legacy route, providers, external connectors, shadow registration, canary,
deploy or push. Replay manifests/reporting and product-owner metric inputs are
later Slice G work.

# G3 manifest-bound replay trials

## Goal

Add a pure local executor that accepts only fixtures matching a replay manifest,
records exactly three deterministic trials per selected scenario, and reports
fail-closed `pass^1` and `pass^3` counts without a release verdict.

## Tasks

- [x] Add RED tests for plan identity, fixture drift, trial topology, metrics,
  compartmentalization, and impact-selection binding.
- [x] Implement immutable replay plans, fixtures, records, issues, summaries,
  canonical serialization, and a callback-only local executor.
- [x] Run one batched independent QA/fix pass and proportional verification.
- [x] Create one explicit-pathspec local commit containing the updated durable
  status documents.

## Done When

- [x] Every executed fixture recomputes to the manifest binding and contract
  identity before candidate callbacks receive public input and a derived seed.
- [x] Every selected scenario has exactly three deterministic trial identities;
  missing, duplicate, extra, foreign, or drifted evidence cannot improve a
  numerator or reduce a denominator.
- [x] `pass^1` is successful trials over all planned trials, while `pass^3` is
  all-three-success scenarios over all planned scenarios.
- [x] Canonical output contains hashes and structural status only: no raw
  candidate/world/fault/oracle/response payload, business metric, or release
  decision.

## Delivery status

G3 is locally complete in the scoped commit containing this document; resolve
its exact SHA from Actual Git after commit. The tests-first RED failed with the
expected `ImportError`. The pure local callback executor accepts only replay
plans and fixtures bound to the manifest and its impact selection, then runs
exactly three deterministic derived-seed trials for every planned scenario.

Plans, trial records, structural issues, and summaries are immutable,
canonically serialized, and hashed. Structural failures produce explicit
`ERROR` evidence instead of disappearing. Denominators remain fixed and fail
closed for all planned work:

- `pass^1 = successful_trials / (3 * N)`;
- `pass^3 = all_three_success_scenarios / N`.

Missing, duplicate, extra, foreign, drifted, or callback-failed evidence cannot
increase either numerator or reduce either denominator. Canonical records keep
raw candidate, world, fault, hidden-oracle, and response compartments out of
the payload.

The focused gate passed 19 tests before QA. The single QA follow-up fixed
structural records and the public journey-contract gate, then reported 20
passed with Ruff, format, and focused MyPy green. Independent verification
passed 108 tests with one known Starlette/httpx2 warning; Ruff was green, eight
files were formatted, focused MyPy over four sources was green, and
`git diff --check` was green.

Full Slice G remains open. The next named slice is G4: a versioned
persona/adversarial/fault corpus plus manifest-bound branch/fault coverage
completeness, still without runtime/live execution, business KPIs, or
promotion.

## Boundary

G3 is pure callback-driven local evaluation. Runtime routing, persistence,
latency/cost and business KPIs, shadow/canary/deploy, push, and promotion remain
out of scope.

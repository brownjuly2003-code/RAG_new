# G2 replay manifest and impact report

## Goal

Add a pure local manifest that pins every participating replay identity and
deterministically reports which scenarios are impacted by a candidate change.

## Tasks

- [x] Add RED tests for canonical manifest identity, hidden-state
  compartmentalization, targeted selection and fail-closed structural changes.
- [x] Implement `evaluation/resolution/replay.py` and export its public API
  without I/O, runtime routing or promotion behavior.
- [x] Run one independent QA/fix batch, then focused and adjacent
  test/type/lint/format/diff gates.
- [x] Record the verified boundary in durable status files and create one
  explicit-pathspec local commit.

## Done When

- [x] The same semantic manifest has the same canonical bytes/digest, while
  every pinned identity change changes the manifest digest.
- [x] Known dependency changes select only bound scenarios; global changes
  select all; structural or unmapped changes select all fail closed.
- [x] Manifest/report payloads expose no candidate messages, world payload,
  hidden expected state, release verdict, VR/VRY, recontact or cost claims.

## Delivery status

G2 is locally complete in the scoped commit containing this document; resolve
its exact SHA from Actual Git after commit. It started from clean `master` at
`5085c99` with no remote. The measured baseline had no
`evaluation/resolution/replay.py`, one legacy
`curated_cases.manifest.json`, 30 G1 fixture scenarios, and 22 G1 branch
targets. Tests-first RED failed with the expected `ImportError: ArtifactKey`.

The pure offline immutable replay manifest requires an exact 40-character code
revision; global contract/compiler/grader/candidate/scenario-set pins; and
version plus SHA256 for every participating dependency. Per-scenario
candidate, world, fault, hidden-oracle, and coverage compartments are stored as
digests or identities. Canonical JSON and digests never serialize raw candidate
messages, world references, fault IDs, or hidden oracle state.

Impact selection compares the baseline and candidate manifests themselves.
Equal manifests report no change; known dependency changes target only bound
scenarios; global changes select all. Dependency-graph changes, scenario
membership changes, and unexplained changes return `FULL_FAIL_CLOSED`, and a
changed manifest can never yield an empty selection. The impact report carries
no replay outcome, promotion/release verdict, or VR/VRY/recontact/cost
semantics.

The single QA follow-up found and fixed three major issues in one batch: an
unbound world reference, serialized raw fault IDs, and leaked
`promotion_status` semantics. Its final gate passed 20 tests, Ruff, a
three-file format check, and focused MyPy over two sources. Independent final
verification passed 88 tests with one known Starlette/httpx2 warning; Ruff,
six-file format, strict focused MyPy over four sources, and diff check were
green.

Full Slice G remains open. The next named slice is G3: a manifest-bound local
replay executor, immutable trial records, and deterministic fail-closed
`pass^1`/`pass^3`, still without business metrics or live promotion.

## Boundary

G2 is manifest and impact reporting only. Replay execution, repeated trials,
`pass^1/pass^3`, runtime/shadow integration, business metrics, database,
canary, deploy, push and live promotion remain out of scope.

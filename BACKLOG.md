# Backlog

This file is a small routing surface, not a historical task log.

For the current action and external blockers, read
[`CURRENT_STATE.md`](CURRENT_STATE.md). For stream status and unfreeze
conditions, read [`ROADMAP.md`](ROADMAP.md). The active delivery plan is
[`plan_06_09_26.md`](plan_06_09_26.md).

## Current queue

- Phase B remains blocked on real shipment-bound support data and owner label
  approval. Do not manufacture more fixture cases to make the gate pass.
- Phase C benchmark execution and resume instructions belong in
  `CURRENT_STATE.md`; do not launch a duplicate run from this file.
- P1 adaptive-k: finish per [`docs/specs/p1-adaptive-k-plan.md`](docs/specs/p1-adaptive-k-plan.md)
  § Next — end-to-end tests, the Mac report at a committed sha, capsule. The score
  artifacts are not evaluated before those tests are committed.
- Review the three accepted ChromaDB CVE exceptions on **2026-10-24** and
  remove them if a fixed release exists (2026-09-24 review: no fixed release).
- MyFlow tree pinning has been silently off here since 2026-09-08 — a defect in
  the shared controller under `~/.claude/skills/`, not in this repository.
  `worktree_hash()` (`mf_util.py:853-895`) runs
  `git add -A -- . ':(exclude).myflow'`, which exits 1 because `.myflow/` is
  gitignored, and on a non-zero exit returns "" instead of the hash. In the run
  journal every `gate`, `gate_green` and `slice_done` event at or after
  2026-09-08T14:12:02 is unmeasured and every earlier one carries a hash. The
  totals grow with every gate; up to the journal entry of 2026-09-10T06:50:04
  they read `gate` 69 events, 28 measured, 41 not; `gate_green` 53/21/32;
  `slice_done` 13/4/9. For those slices "the full gate ran on the commit's tree" is a manual claim,
  not a machine-checked one. T-19 and T-17 were pinned by hand (`git read-tree
  HEAD` + `git add -A -- .` + `git write-tree` in a private index: before the
  full gate, after it and at the commit, equal to `d026804^{tree}` 97ddd508 and
  `6cc810d^{tree}` 22519835). T-18 (`0aacb7b`) has no pin at all — it was
  committed before that manual script existed. Not fixed from here: the controller
  has 208 tests, other projects depend on it, and the fix is conditional —
  ignored paths must not fail the add.

The local corrective queue after T-09 is otherwise empty. New work must satisfy
the slice rule in `CURRENT_STATE.md`: observable product behaviour, more real
labelled cases, or a newly published measurement with provenance.

## History

The former 22 KB backlog, including inherited CI analysis and superseded
autopilot tasks, is preserved at
[`archive/docs/status/backlog-through-2026-08-27.md`](archive/docs/status/backlog-through-2026-08-27.md).
It is evidence, not a source of new work.

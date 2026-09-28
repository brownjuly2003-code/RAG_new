# Backlog

This file is a small routing surface, not a historical task log.

For the current action and external blockers, read
[`CURRENT_STATE.md`](CURRENT_STATE.md). For stream status and unfreeze
conditions, read [`ROADMAP.md`](ROADMAP.md). The active delivery plan is
[`plan_06_09_26.md`](plan_06_09_26.md).

## Current queue

- Phase B remains blocked on real shipment-bound support data and the 40
  double-annotated calibration routes; the 100 labels were approved 2026-09-25.
  Do not manufacture more fixture cases to make the gate pass.
- Phase C benchmark execution and resume instructions belong in
  `CURRENT_STATE.md`; do not launch a duplicate run from this file.
- C.2 has a local step-wise judge for shipment evidence and GR-4 section paths.
  It uses contract rules first and can call the existing NLI scorer only for
  disputed claims. This is preparation, not a measured slice: the pinned model
  has not run on this judge, and B.4 still needs Julia's human route grades.
- P2: the [blinded judgment](docs/evidence/p2-blinded-relevance-judgment.md)
  has complete GLM and Sonnet runs (115/115 cases each). H α is 0.8566;
  primary τ_b is 0.1561, CI95 [0.0197, 0.2880], giving the registered
  `RULER_DOES_NOT_TRACK` verdict. Julia's blind 10-case grades are pending;
  Mistral returned `zero_limit` and needs a changed account limit before a new
  attempt. Keep the official gate and retrieval defaults unchanged.
  P1 and P1b are both `NO_SHIP` ([P1b capsule](docs/evidence/p1b-expanded-cut.md)):
  H-relative exploratory verdicts on 100 agent-authored `agent_labelled` cases
  (0 approved at the time); neither changed product behaviour.
- Re-ingest any Chroma collection built before `534612e`: it keeps its
  unpersisted write-ahead-log tail until it is rebuilt
  ([rerun after the fix](docs/evidence/chroma-restart-stability-after-fix.md)).
- Review the three accepted ChromaDB CVE exceptions on **2026-10-24** and
  remove them if a fixed release exists (2026-09-24 review: no fixed release).

The local corrective queue after T-09 is otherwise empty. New work must satisfy
the slice rule in `CURRENT_STATE.md`: observable product behaviour, more real
labelled cases, or a newly published measurement with provenance.

## History

The former 22 KB backlog, including inherited CI analysis and superseded
autopilot tasks, is preserved at
[`archive/docs/status/backlog-through-2026-08-27.md`](archive/docs/status/backlog-through-2026-08-27.md).
It is evidence, not a source of new work.

MyFlow tree pinning was off from 2026-09-08T14:12:02 to
2026-09-10T07:37:47: `worktree_hash()` returned an empty hash when
`git add` exited 1 on the gitignored `.myflow/`. In that window, 47
`gate` (two of them final gates with no task), 34 `gate_green` and 11
`slice_done` journal events of T-11…T-21 carry no tree hash. For
those slices, "the full gate ran on the commit's tree" is a manual
claim: T-17 and T-19 were pinned by hand, T-18 not at all. Every gate
event since 2026-09-13T13:44:16 carries a hash.

# Backlog

This file is a small routing surface, not a historical task log.

For the current action and external blockers, read
[`CURRENT_STATE.md`](CURRENT_STATE.md). For stream status and unfreeze
conditions, read [`ROADMAP.md`](ROADMAP.md). The active delivery plan is
[`plan_06_09_26.md`](plan_06_09_26.md).

## Current queue

- **First, since Julia's decisions of 2026-10-15: the chat on the production Mac** — the time
  limits are lifted to a 3,600-s ceiling with the reranker on the CPU (`468224b`) and the chat
  offers the operator on a timeout and on `human` (`056844d`; the widget `4977582`), thinking off
  (`c2739af`), qwen3:1.7b timed live; next her model Qwen3-4B-Instruct — [ROADMAP](ROADMAP.md#active).
- Phase B remains blocked on real shipment-bound support data and the 40
  double-annotated calibration routes; the 100 labels were approved 2026-09-25.
  Do not manufacture more fixture cases to make the gate pass.
- Phase C benchmark execution and resume instructions belong in
  `CURRENT_STATE.md`; do not launch a duplicate run from this file.
- C.2 now shows contract-rule step checks on new shipment traces in the Evidence
  tab, proven by the ask → trace → admin HTTP test. This is a product-view slice,
  not a measured quality gain. The local judge can call the existing NLI scorer
  for disputed claims, but the live view does not run it. The pinned model has
  not run on this judge; B.4 (≥ 40 double-annotated routes) is not started, and under D11 no
  person grades them.
- P2: the [blinded judgment](docs/evidence/p2-blinded-relevance-judgment.md) has complete GLM and Sonnet runs (115/115 cases each). H α is 0.8566; primary τ_b is 0.1561, CI95 [0.0197, 0.2880], giving the registered `RULER_DOES_NOT_TRACK` verdict. No human grades will be collected (plan D11): the consensus is `model-cross-checked` against the Astra and Opus references ([slice 1.1](docs/evidence/p2-model-reference-kappa.md): κ 0.9333 / 0.9604, both CI95 above 0.7; the sample's question classes and unexpanded top-5 contexts only);
  Mistral returned `zero_limit` and needs a changed account limit before a new attempt. Keep the official gate and retrieval defaults unchanged.
  P1 and P1b are both `NO_SHIP` ([P1b capsule](docs/evidence/p1b-expanded-cut.md)): H-relative exploratory verdicts on 100 agent-authored `agent_labelled` cases (0 approved at the time); neither changed product behaviour.
- Quality thread ([plan](docs/specs/plan_03_10_26.md), §1 order/dependencies and slice status, §5 slices), ratified 2026-09-30, revised 2026-10-03.
  Tracks 0–2: MyFlow T-55…T-78; T-57 (1.1), κ of the consensus to the model references with no human grades (D11), is done 2026-10-04 (P2 item above). The owner's order of 2026-10-03 — a green CI on HEAD first — is met on `45a417a` (run 37157492007); the 2.5 chain is done: T-69, T-67, T-70 and T-65 — the [production baseline with its loss map](docs/evidence/production-baseline-h-hm.md) (2026-10-05, rule (c), `single_judge`): `precision_at_5` 0.5354 on H and 0.6800 on Hm as points; the plan's default H1 in the graph branch stands (the map did not choose it), second slot not taken; open from it: the collector records no BM25 candidates and the rewrite's cost is unmeasured, so a loss before the pool has no cause, and the ideal of `ndcg_at_5` counts expanded texts. Since the owner's D12 (2026-10-04) one model — the session's Opus 5.5 — does every job and check, with no MyFlow and no other vendor's model. 1.3b is done (T-78): [30 pilot drafts verified by that one model](docs/evidence/devset-pilot-label-verification.md), 5 of them after a repair, `single_model_verified`, still `agent_labelled`. 1.3c is done (2026-10-06, rule (c)): its [variance pilot](docs/evidence/variance-pilot-gold-metrics.md) gives no verdict and leaves the registered MDE at 0.17–0.30 against the rule's +0.05 (development 60 cases in 37 clusters, holdout 64 in 18). Open from it, undecided (plan §3, «06.10, открытое решение»): the grading filter is in part a draw — 9 of 168 shared documents got another verdict — its batch request gave no grade a document in 187 of 187 contexts at half of the grading seconds, and requests with a schema carry no temperature; a fix changes the control and means the 2.5 baseline is taken again, so the filter stays as it is until that is decided. Waiting behind the chat thread, all preparation: step 1.3d — the register of `pilot-v3` and the 30 development drafts at `c43f0a0`, 62 of 64 holdout drafts at `e1521ba` (two declined by the generator), no check request sent — and the three external bases (the owner's word of 2026-10-05): plan slices 1.5, 1.5c and 1.5d connected and indexed on the Mac by 2026-10-07, 1.6's parts locked and its pilot recorded; next the spec's eleventh revision with its cold review, then 1.7 ([session log](docs/operations/session-handoff-2026-10-05-one-model-and-sizes.md); the commits after `f7416ca` were pushed on 2026-10-15).
  T-65's pinned index — all 5589 embeddings and the isolated Chroma index, verified after reopening —
  is reusable by later runs ([handoff](docs/operations/t65-baseline-handoff.md)); the loss map on gold spans follows 1.3d.
  The 30-case Chroma/exact comparison is published ([capsule](docs/evidence/production-parity-30-cases.md)): 29 of 30 sent contexts identical, no quality number.
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

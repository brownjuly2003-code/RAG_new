# RAG_new archive

Retained history: not part of the active documentation or the runtime. Nothing here selects
new work — the order of work is [`PLAN.md`](../PLAN.md), the state is
[`CURRENT_STATE.md`](../CURRENT_STATE.md). Files here keep the links and status claims of their
own dates; the moves of 2026-10-17 rewrote their links so they still resolve.

## Contents

| Path | Contents |
|---|---|
| `docs/state/` | Earlier versions of the root status files: the AGENT_STATE update log 2026-03…08, and `current-state`, `roadmap`, `agent-state`, `backlog` as they stood before the tidy-up of 2026-10-17 — the full progress log of every stream |
| `docs/plans/` | Superseded delivery plans, among them `plan_06_09_26.md` (replaced by `PLAN.md`) |
| `docs/specs/` | Plans and pre-registrations replaced by `PLAN.md` (moved 2026-10-17): `plan_03_10_26.md` — the quality thread, still the reference for its method and decisions D1–D12 — `plan_final_30_09_26.md`, `plan_30_09_26.md`; the research reports on benchmarks, embedders and NLI judges; adaptive-k, P2 blinded-judge and label-approval plans |
| `docs/audits/` | All product audits 2026-04…10, the audit of record `audit_final_23_08_2026.md` included (moved 2026-10-17) |
| `docs/operations/` | Session handoffs up to 2026-10-16 and dated experiment logs 2026-05…08; older runbooks and kickoffs, among them the direct GLM-5.3 runbook with its Codex fallback, which predates D12 and is not in force (moved 2026-10-17) |
| `docs/architecture/` | The inherited RAG architecture and the migration plan from it (moved 2026-10-17) |
| `docs/AUTOPILOT.md`, `docs/CHANGELOG.md`, `docs/local-gate.md`, `docs/windows-test-workflow.md` | The autopilot guide, the inherited changelog, and the old local test workflow — tests now run on the Mac (moved 2026-10-17) |
| `notebooks/` | The Colab remote-benchmark notebook (moved 2026-10-17) |
| `docs/sessions/` | Older session handoffs and agent journals |
| `docs/status/` | Superseded closure and backlog snapshots |
| `docs/research/` | Dated research snapshots |
| `docs/design/` | Superseded design-process artifacts |
| `tasks/` | Completed Codex task specifications and verification reports |
| `legacy-code/` | Removed compatibility code and its tests |
| `process/` | Historical workflow diagnostics |
| `process/grok-prompts/` | Phase C.1b run kit for the Mac (2026-09-01/02): Grok task prompts, run scripts, smoke results |
| `local/` | Machine-local leftovers cleared out of the repository root; ignored by git, so absent from a fresh clone |

The first consolidation was on 2026-09-04; the second, on 2026-10-17, moved everything in
`docs/` that no longer routes work. `process/grok-prompts/` was the root folder
`.grok-prompts/` until 2026-10-03; its files still name that path. Published records in
`reports/` were not rewritten: a few of them name a document by its path before the move.

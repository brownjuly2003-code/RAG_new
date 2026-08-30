# Current state — RAG_new

**The only entry point for a new session.** Read this, then
[`ROADMAP.md`](ROADMAP.md). Everything else is reached by link, on demand.

Last updated: 2026-08-29 · Plan: [`plan_23_08_2026.md`](plan_23_08_2026.md)
(mode B) · Audit of record:
[`docs/audits/audit_final_23_08_2026.md`](docs/audits/audit_final_23_08_2026.md)
· Phase C benchmark source: `c06bdf5` · local commits are not pushed

## Start here

### Active Phase C.1 baseline run — Mac

`c1a-qwen25-7b-c06bdf5` is running 3 × 100 cases on `deproject-mac` from exact
SHA `c06bdf5721b434eff32dcf5b9991221d5b2a15f8`. Isolated worktree:
`/tmp/rag-new-c06bdf5.WLtg39/worktree`; benchmark PID `39358` is detached
(`PPID 1`), and `caffeinate` PID `39360` keeps the Mac awake. Log/checkpoint:
the worktree's parent directory. The old Mac clone was not changed. Closing
this Codex/SSH session is safe and does not stop the run; rebooting or powering
off the Mac would.

Provenance: model digest
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`;
dataset SHA-256
`3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720`;
cached contexts
`91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10`;
pinned NLI revision `8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c`. A one-case
end-to-end smoke passed but is `not_evidence`. The full run's first checkpoint
was valid and error-free. At session closure the checkpoint was 6/300: all six
rows had valid generation and judge output, with zero errors; the final report
did not exist yet. This remains a multi-hour run. Publish nothing unless it is
`measured`, exactly 3 × 100 and zero-failure. On exit, resume this run id with
the same arguments and `--resume`; never start a duplicate.

### 1. The gate can reach Russian traffic. The corpus still cannot measure it.

T-01…T-09 are closed: measured bilingual admission, opt-in clarification,
operator-visible shadow outcomes and pinned report provenance. Exact commits
and tests live in the [A.6–A.8 capsule](docs/evidence/a6-journey-admission-and-clarification.md).
Push remains the owner's call:
`git -c credential.helper='!gh auth git-credential' push origin master`.

The corpus cannot measure resolution, for three independent reasons
([capsule](docs/evidence/a6-journey-admission-and-clarification.md)):

1. no case names a shipment (B.1);
2. the corpus is Russian and the gate's vocabulary was English —
   `contains_both_domain_noun_and_status_cue: 0`, so over the 100
   agent-authored-over-real-documents cases, still `agent_labelled` and
   0 approved, `recall 0.0000` said nothing about the predicate;
3. with the language removed, over the 100
   agent-authored-over-real-documents cases, still `agent_labelled` and
   0 approved, admission recall is still **0.0000**. Reachability
   moved from `both 0` to `both 1`; the one admission is a false
   positive on a case labelled `exception_escalation`. The corpus
   contains no case this journey should admit.

B.2/B.3/B.5 stay blocked on data. Label review does not fix that:
`python scripts/aircargo_labels.py report --batch 1`, then
`python scripts/aircargo_labels.py approve --batch 1 --approver julia`.

The local corrective queue after T-09 is empty.

**This laptop:** `tests/test_a11y.py::test_axe_has_no_serious_or_critical_findings`
drives headless Chrome and hangs the whole run (deselect it; CI runs it);
local mypy --strict is red on numpy stubs unless the installed numpy
matches the lock (2.4.4, not 2.5.1); Postgres integration tests still do
not run here.

### 2. Housekeeping with a date on it

**Review 2026-09-24:** the three chromadb CVE ignores. If a fixed release
exists by then, upgrade and delete them from all four places the guard
requires them to match.

## What is true right now

- **Remote exists** (2026-08-24): `brownjuly2003-code/RAG_new`, private,
  tag `freeze-2026-08-23` = `26866e9`. Pushes go over HTTPS (command in §1).
- **Phase A closed:** `/api/ask` runs the shipment-status journey as a
  read-only shadow. T-03 may project only its clarification terminal when both
  allowlists name it; T-04 makes disabled/declined/failed observation explicit.
  All resolution/session flags default off, and shadow-only remains byte-identical.
- **Zero real labelled cases.** 100/100 labelled, 0 approved, 0 binding a
  shipment, `expected_terminal` `verified` for all 100. The 201 source
  documents are real; the questions were written by an agent (`325d63c`,
  `6b7417d`, `32e841f`).
- **CI is fully green** through B.1 / `origin/master` at `04fbe4b` — 11/11
  on run 32880095361 (unit 2247 passed, 25 skipped, coverage 76.13% against
  a gate of 72; integration 62 passed, 1 skipped). None of the local commits
  beyond `origin/master` has been through remote CI.

## Accepted open risks

- **Three chromadb CVEs** (CVE-2026-45830 / 45833 / 45831), no fix version.
  Ignored by id per ADR 0008. **Review 2026-09-24.**
- **The fixture TMS is a stand-in.** Every number measured through it is
  fixture-sourced and has to say so.
- **The integration job connects to Postgres as a superuser**, so RLS is
  inert unless the assertion uses a NOBYPASSRLS runtime role.

## The rule that governs every slice

A slice counts only if **(a)** observable `/api/ask` or UI behaviour
changed with an E2E test proving it, **(b)** real labelled cases went up,
or **(c)** a published number changed with provenance. T-02/T-08/T-05 are
(c); T-03 is (a). B.1 is preparation until a batch is approved.

## Phases 0 and A — done · B — in progress

| # | Item | Status |
|---|---|---|
| 0.1–0.3 | Freeze, publish, truth about gates | done |
| A.1–A.5 | Shadow + durable turn + evidence tables + Evidence tab | done, three slices under (a) |
| A.6 | Admission gate; over the 100 agent-authored-over-real-documents cases, still `agent_labelled` and 0 approved, scored recall 0.0000 | **done** (c) |
| A.7 | Opt-in clarification projection through `/api/ask` | **done** (a), default off |
| A.8 | Evidence distinguishes disabled, declined and failed producers | **done** (a) |
| B.1 | Labels on all 100 cases | **done**, `agent_labelled`, 0 approved |
| B.2 | Fixture TMS covering the cases | **blocked** — three reasons, not one |
| B.3 | First real numbers on the labelled cases | **blocked** — same |
| B.4 | Judge calibration 10 → ≥40 double-annotated routes | not started |
| B.5 | Corpus v1.0 at `real_labelled` | needs Q2 route 1 |

## Open questions for Julia

Q1 is answered (separate private repo). Each of these blocks only its own phase:

- **Q2 (phase B), now two questions.** (a) Approve the proposed labels in
  batches of 20 — the command is in §1 above. (b) **The one that matters:** can
  100 real support requests that name a shipment be obtained? Without them
  phase B has no measurable corpus, and B.2/B.3/B.5 stay blocked. If the answer
  is no, the decision to record is that the repository measures resolution on
  synthetic instances and says so wherever a number is published.
- **Q3 (phase C):** heavy runs on Colab or the iMac. **Q4 (phase E):** publish
  as `RAG_new` or rename.

## Links

- Roadmap and what is frozen — [`ROADMAP.md`](ROADMAP.md)
- One row per slice, with evidence — [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md)
- Open work after T-04, plus the pre-audit queue — [`BACKLOG.md`](BACKLOG.md)
- Agent conventions — [`CLAUDE.md`](CLAUDE.md) · removed surfaces —
  [`DEPRECATIONS.md`](DEPRECATIONS.md) · history — [`AGENT_STATE.md`](AGENT_STATE.md)

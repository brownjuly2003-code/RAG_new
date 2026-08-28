# Current state — RAG_new

**The only entry point for a new session.** Read this, then
[`ROADMAP.md`](ROADMAP.md). Everything else is reached by link, on demand.

Last updated: 2026-08-28 · Plan: [`plan_23_08_2026.md`](plan_23_08_2026.md)
(mode B) · Audit of record:
[`docs/audits/audit_final_23_08_2026.md`](docs/audits/audit_final_23_08_2026.md)
· baseline before T-07: `62e9883` · T-07 is the eighth local commit beyond
`origin/master`; nothing is pushed

## Start here

### 1. The gate can reach Russian traffic. The corpus still cannot measure it.

T-01/T-02/T-08, the T-05 evidence commit, T-03/T-04, T-06 and T-07 — **eight local
commits total, not pushed**. Push is the owner's call:
`git -c credential.helper='!gh auth git-credential' push origin master`.

- `6651964` **T-01** — the shipment-status journey decides whether a request
  is its own before asking for an id. Three rules: a valid shipment
  reference, a truncated one, or a domain noun AND a status cue. Anything
  else ends CANCELLED / NOT_IN_JOURNEY and `build_shipment_status_observer`
  returns None, so the shadow records nothing and the legacy answer is
  untouched. CLARIFICATION_REQUIRED stopped being the kernel's default and
  became a decision. `/api/ask` itself did not change.
- `36d4269` **T-02** — `evaluation/journey_admission.py` +
  `scripts/journey_admission_report.py` score that decision against
  `label.journey` on all 100 labelled cases. First consumer B.1's labels
  have had.
- `bd82297` **T-08** — the vocabulary gained a Russian half, built as a
  translation of the English one so it could not be fitted to the corpus
  it is scored against.
- **T-03** — `/api/ask` now projects the contract's shipment-id clarification
  only when `shipment-status` is named in both resolution allowlists. Both
  default off. A decline, another terminal or any shadow/projection failure
  leaves the legacy response unchanged; the E2E test also holds session
  history, trace identity and the response schema.
- **T-04** — Evidence readback and the admin tab now distinguish
  `shadow_disabled`, `journey_declined` and `producer_failure`. Declines still
  return the legacy answer, call neither source nor policy, and never enter
  resolution persistence; only their minimal outcome reaches the trace.
- **T-06 correction** — a multi-word admission noun must now occur within one
  message; a complete noun and its status cue may still occur in different
  messages. Public `/api/ask` supplies one message, so this is not an A.9 slice.
- **T-07 provenance repair** — report v1.3 pins the code, corpus and manifest
  snapshots to one SHA; the Mac gate passed 11 tests plus strict Mypy and Ruff.

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

**Queued and verified, not a guess,** in [`BACKLOG.md`](BACKLOG.md): T-09; its
single-space validator cannot fire. T-07 is closed above.

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
- **CI is fully green** through A.5 / the latest pushed state — 11/11 on
  run 32874107015 (unit 2234 passed, 25 skipped, coverage 76.04% against
  a gate of 72; integration 62 passed, 1 skipped). None of the eight local
  commits has been through remote CI.

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

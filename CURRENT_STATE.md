# Current state — RAG_new

**The only entry point for a new session.** Read this, then
[`ROADMAP.md`](ROADMAP.md). Everything else is reached by link, on demand.

Last updated: 2026-08-25 · Plan: [`plan_23_08_2026.md`](plan_23_08_2026.md)
(mode B) · Audit of record:
[`docs/audits/audit_final_23_08_2026.md`](docs/audits/audit_final_23_08_2026.md)
· HEAD when this was written: `c31d226` + the B.1 commit below

## Start here

### 1. Phase B — the labels are done, and they changed the question

**B.1 landed on 2026-08-25.** All 100 air-cargo cases now carry a journey, an
expected outcome, a root cause and an approval slot, checked by
`tests/test_aircargo_labels.py` and pinned by
`evaluation/curated_cases_aircargo.manifest.json`. Full account:
[`docs/evidence/b1-aircargo-journey-labels.md`](docs/evidence/b1-aircargo-journey-labels.md).

The labelling found that **no case in the corpus names a shipment.** 66 of the
100 belong to no kernel journey at all; the other 34 are blocked before they
start by `no_shipment_binding`. So the corpus cannot produce a
verified-resolution number, a VRY or a `pass^k` no matter how good the kernel
gets — **B.3 cannot be run against it**, and B.2 (extending the fixture TMS to
cover the cases) has nothing to cover. This is the brief's own NO-GO check
firing (§15: "100 cases не отражают реальные обращения"): these are questions
*about* air-cargo work, not requests *inside* it.

**The next action is a decision, not code** — see Q2 below. Two routes, and
only the first produces `real_labelled`:

1. **Real requests** — 100 support requests that named a shipment, from a
   domain owner; labelled and approved the way B.1 already supports.
2. **Explicitly synthetic instances** against the fixture TMS — cheap, but the
   repository has 17 already and more of them does not move FIN-02.

Independent of that, the 100 proposed labels await review in batches of 20:
`python scripts/aircargo_labels.py report --batch 1`, then
`approve --batch 1 --approver julia`. That does not fix the finding above; it
only turns `agent_labelled` into `real_labelled` for the labelling itself.

### 2. Housekeeping with a date on it

**Review 2026-09-24:** the three chromadb CVE ignores. If a fixed release
exists by then, upgrade and delete them from all four places the guard
requires them to match.

## What changed on 2026-08-25

- **Phase A closed** — A.1, A.1b, A.2, A.3, A.4 and A.5 all landed. `/api/ask`
  runs the shipment-status journey as a read-only shadow, takes a durable
  session turn, writes its evidence to both the trace and the resolution
  tables, and shows it in an Evidence tab with a JSON export. Both flags
  (`RESOLUTION_SHADOW_JOURNEYS`, `SESSION_DURABLE_TURNS`) default off and the
  legacy answer is byte-identical either way. Building the tab found the defect
  that had made the journey hollow: the shipment-id extractor matched only
  `SHP-…` while the fixture TMS holds `AC-…`, so every bundle had been empty.
  Detail and tests: the phase-A section of [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md).
- **B.1 — the 100 cases are labelled** (see above). `evaluation/aircargo_labels.py`
  holds the vocabulary and the invariants; `scripts/aircargo_labels.py` is the
  only supported way to record an approval, so the dataset, the manifest digest
  and the `real_labelled` count cannot drift apart.

## What is true right now

- **Remote exists** (2026-08-24): `brownjuly2003-code/RAG_new`, private, tag
  `freeze-2026-08-23` = `26866e9` = the state the audit describes. The
  account's git protocol is ssh with no key loaded, so pushes go over HTTPS:
  `git -c credential.helper='!gh auth git-credential' push origin master`.
- **The kernel has a production caller** (2026-08-24), having had none for the
  whole life of the fork, and so does `services/session.py` (2026-08-25). Both
  halves of FIN-01's "primitives with no caller" are closed:
  `grep -rlE 'from resolution|services\.session' api` → `api/routers/conversation.py`.
  What is left of FIN-01 is that everything they run against is still synthetic.
- **Zero real labelled cases**, now with a reason on the record rather than a
  to-do: 100/100 labelled, 0 approved, 0 binding a shipment, and
  `expected_terminal` `verified` for all 100 — so the corpus exercises no
  escalation, disclosure or refusal path either.
- **The 100 cases are agent-authored over real documents.** The 201 source
  documents are real; the questions over them were written by an agent
  (`325d63c`, `6b7417d`, `32e841f`), not sampled from traffic. An approval
  makes the *labelling* real, not the cases — the audit's shorthand "100 real
  air-cargo cases" is looser than the provenance supports.
- **CI is fully green** — 11/11 on run 32874107015 (unit 2234 passed,
  25 skipped, coverage 76.04% against a gate of 72; integration 62 passed,
  1 skipped), and has stayed green through every phase-A commit. A red job now
  means a new problem. Unit coverage understates the Postgres adapters, which
  only the integration job exercises. The "Deploy docs site" workflow builds
  and skips its Pages deploy, unavailable on a private repo until Q4.
- **Postgres integration tests do not run on this laptop** (the WSL role has no
  CREATEDB, sudo password unknown), so their gate is CI. Local mypy also
  reports a numpy stub error the locked version does not have (2.5.1 installed
  vs 2.4.4 locked) — not a code problem.

## Accepted open risks

- **Three chromadb CVEs** (CVE-2026-45830 / 45833 / 45831), no fix version
  available. Ignored by id per ADR 0008. **Review 2026-09-24.** A new chromadb
  CVE must still turn CI red.
- **The fixture TMS is a stand-in**, not a transport management system. Every
  number measured through it is fixture-sourced and has to say so.
- **The integration job connects to Postgres as a superuser**, so RLS is inert
  for any assertion that does not deliberately go through a NOBYPASSRLS
  runtime role. All four Postgres modules do — but a new test that forgets it
  passes for the wrong reason. The fix is a non-superuser role for the job;
  not scheduled.

## The rule that governs every slice

A slice counts only if **(a)** observable `/api/ask` or UI behaviour changed
with an E2E test proving it, **(b)** real labelled cases went up, or **(c)** a
published number changed with provenance. Anything else is preparation, and
fixing a failing test is a repair — it goes in the corrections table of
[`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md), not the slice table. B.1 is the
honest edge of this rule: it is preparation until a batch is approved, and it
says so.

## Phases 0 and A — done · B — in progress

| # | Item | Status |
|---|---|---|
| 0.1–0.3 | Freeze, publish, truth about gates | done, every §0 gate command passes |
| A.1–A.5 | Shadow + durable turn + evidence tables + Evidence tab | done, three slices under rule (a) |
| B.1 | Journey/outcome/root-cause labels on all 100 cases | **done**, `agent_labelled`, 0 approved |
| B.2 | Fixture TMS covering the cases | **blocked** — no case binds a shipment |
| B.3 | First real numbers on the labelled cases | **blocked** — same reason |
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
- Defect detail and the pre-audit queue — [`BACKLOG.md`](BACKLOG.md)
- Agent conventions — [`CLAUDE.md`](CLAUDE.md) · removed surfaces —
  [`DEPRECATIONS.md`](DEPRECATIONS.md) · history — [`AGENT_STATE.md`](AGENT_STATE.md)

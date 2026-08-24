# Onboarding for agents working in `D:\RAG_new`

Read exactly two files to start: [`CURRENT_STATE.md`](CURRENT_STATE.md), then
[`ROADMAP.md`](ROADMAP.md). Everything else is reached by link, on demand.
Do not read `docs/archive/` or `docs/SESSION_HANDOFF.md` for routing — they
are history, and planning from them is how this repository accumulated seven
layers of release machinery on synthetic fixtures.

## The slice acceptance rule

A slice counts only if at least one of these holds:

- **(a)** observable `/api/ask` or UI behaviour changed, proven by an E2E test;
- **(b)** the count of real labelled cases went up;
- **(c)** a published quality number changed, with provenance (corpus SHA +
  code SHA + config).

"Locally complete" without (a), (b) or (c) is preparation, not a slice. This
binds autopilot too.

## Repository rules

- **Root holds at most 8 `.md` files.** Enforced by
  `tests/test_docs_hygiene.py`. New evidence is a test plus one row in
  [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md) — never a new capsule file in the
  root.
- **Check `ROADMAP.md` before starting anything.** Frozen streams stay frozen;
  wanting the system to be more complete is not an unfreeze condition.
- **Numbers need provenance.** A metric without a corpus SHA, a code SHA and a
  config is not evidence. A run that did not happen is `NOT_EVIDENCE`, never a
  pass.
- **Heavy runs do not go on the Windows laptop.** Models, the full test suite
  and Docker go to the iMac or Colab. Locally: focused gates only.
- **Local commits are fine; pushing is not**, until Q1 in
  [`plan_23_08_2026.md`](plan_23_08_2026.md) is answered.

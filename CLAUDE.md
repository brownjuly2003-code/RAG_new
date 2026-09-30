# Onboarding for agents working in `D:\RAG_new`

Read exactly two files to start: [`CURRENT_STATE.md`](CURRENT_STATE.md), then
[`ROADMAP.md`](ROADMAP.md). Everything else is reached by link, on demand.
Do not read `archive/` for routing — it is history, and planning from it is
how this repository accumulated seven
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

- **Root holds at most 9 `.md` files.** Enforced by
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
- **Push to `origin/master`** — `brownjuly2003-code/RAG_new`, private (Q1,
  answered 2026-08-24). The account's git protocol is ssh with no key loaded,
  so pushes go over HTTPS:
  `git -c credential.helper='!gh auth git-credential' push origin master`.
- **GitHub Actions CI is unavailable until early October 2026** (owner,
  2026-09-21). Work without Actions for now; run relevant verification on
  the Mac before committing/pushing. Do not repeatedly probe billing or
  retry blocked workflows. Recheck availability in early October; recovery
  is not guaranteed on October 1. Do not weaken checks or claim CI passed.
- **Executor: GLM 5.3, called directly with `xhigh`.** Follow the
  [direct API runbook](docs/operations/direct-glm-5.3.md); do not substitute
  Grok, OpenCode or a Claude CLI wrapper for the direct request.
  Fallback on a GLM failure: output window exhausted or connection reset —
  one narrowed retry, then Codex (profile `cw`); quota `1308`/`1310` — wait
  for the reset or go to Codex at once, no retry before the reset. Allowed by
  the owner on 2026-09-24 for `1310` and extended to the other failures on
  2026-09-30 by delegation; the substitution is disclosed in the commit
  message and all independent checks stay (runbook, recovery policy).

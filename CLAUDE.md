# Onboarding for agents working in `D:\RAG_new`

Read exactly three files to start: [`CURRENT_STATE.md`](CURRENT_STATE.md), then
[`PLAN.md`](PLAN.md) — the one plan, the order of work — then [`ROADMAP.md`](ROADMAP.md),
progress against it. Everything else is reached by link, on demand; the map of every
other document is [`docs/README.md`](docs/README.md).
Do not read `archive/` for routing — it is history, and planning from it is
how this repository accumulated seven layers of release machinery on
synthetic fixtures.

## The slice acceptance rule

A slice counts only if at least one of these holds:

- **(a)** observable `/api/ask` or UI behaviour changed, proven by an E2E test;
- **(b)** the count of real labelled cases went up;
- **(c)** a published quality number changed, with provenance (corpus SHA +
  code SHA + config).

"Locally complete" without (a), (b) or (c) is preparation, not a slice. This
binds autopilot too.

## Who does the work, and where

- **The session does all of it itself** — code, tests, documents, checks
  (owner's decision D12, 2026-10-04: «ты должен все делать сам»). No other
  model in any role — executor, reviewer, verifier, judge, reference, repair
  author: not another vendor's, and a subagent runs on the session's model.
  A rule or runbook that names another model predates D12 and is not in
  force, the [direct GLM 5.3 runbook](archive/docs/operations/direct-glm-5.3.md) and
  its Codex fallback included; they come back only on the owner's word.
  Her word of 2026-10-19 («Привлекай кодекс для второго мнения») brought
  back one role: Codex, profile cw, reads a package of the repository's
  files and gives a second opinion; it writes no code, grades nothing and
  gets no data of an external base ([`PLAN.md`](PLAN.md) §8.1).
  Her word of 2026-10-30 («В качестве исполнителя используй кодекс (astra 6
  xhigh)») made Codex (cw, `gpt-6-astra`, `xhigh`) the executor of the
  work after it: it writes code, tests and technical documents in a copy of
  the repository's tracked files without external-base data; the session
  briefs it, reviews its diff, runs the Mac's gates and measurements,
  writes the status documents and commits. It still grades nothing.
- **No MyFlow unless the owner names it in the current session**: neither the
  `myflow_new` skill nor a `$MF` command. `$MF` steps in a handoff give the
  order of the tasks, not the tool.
- **Nothing heavy on the Windows laptop.** No WSL, Docker or VM there. Tests,
  models and Docker run on the Mac (`deproject-mac`) or Colab; the laptop
  keeps `ruff`, `mypy` and light scripts.
- **Pushes go to `origin/master`** (`brownjuly2003-code/RAG_new`, private),
  over HTTPS because the account's ssh has no key loaded:
  `git -c credential.helper='!gh auth git-credential' push origin master`.

## Repository rules

- **Check `PLAN.md` and `ROADMAP.md` before starting anything.** Frozen streams stay frozen;
  wanting the system to be more complete is not an unfreeze condition.
- **Numbers need provenance.** A metric without a corpus SHA, a code SHA and a
  config is not evidence. A run that did not happen is `NOT_EVIDENCE`, never a
  pass.
- **Root holds at most 9 `.md` files.** New evidence is a test plus one row in
  [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md) — never a new capsule file in the
  root.
- **Status files have line caps** — `CURRENT_STATE.md` 150, `AGENT_STATE.md`
  120, `BACKLOG.md` 60: edit lines in place. After touching a root `.md`, run
  `tests/test_docs_hygiene.py`, `tests/test_docs_quality.py` and
  `tests/test_docs_publication.py`.

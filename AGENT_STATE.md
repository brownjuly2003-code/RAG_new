# Agent state — how to work here

> **Not the entry point.** Sessions start at [`CLAUDE.md`](CLAUDE.md), then
> [`CURRENT_STATE.md`](CURRENT_STATE.md), [`PLAN.md`](PLAN.md) and [`ROADMAP.md`](ROADMAP.md).
> This file holds the working conventions those files assume. It stays at this path because
> `scripts/autopilot.ps1` reads it as planner context; it must not grow back into a log.
>
> History: this file before 2026-10-17 —
> [`archive/docs/state/agent-state-through-2026-10-17.md`](archive/docs/state/agent-state-through-2026-10-17.md);
> the update log of 2026-03…08 —
> [`archive/docs/state/agent-state-2026-03..08.md`](archive/docs/state/agent-state-2026-03..08.md).

## What this repository is

`D:\RAG_new` is a clone of `RAG_Support_Assistant` at `bd07179`, built to the brief in
`D:\New_steps\rag.md`: a support assistant over a company's documents (the RAG runtime) plus a
deterministic resolution kernel for shipment requests (`resolution/`, `knowledge/`,
`actions/`, `services/session.py`, migrations 024–031). The kernel runs behind `/api/ask` as a
read-only shadow, off by default; it has no real shipment data yet (phase B, Q2b). Remote:
`brownjuly2003-code/RAG_new`, private.

The product measured and improved now is the web chat on the production Mac
([`CURRENT_STATE.md`](CURRENT_STATE.md)).

## Who does the work

- **The session does all of it** — code, tests, documents, checks (Julia's D12, 2026-10-04:
  «ты должен все делать сам»). No model of another vendor in any role but Codex's, on her word;
  a subagent runs on the session's model. Codex (profile cw) gives a second opinion since
  2026-10-19 and is the executor since 2026-10-30 — the session briefs it, reviews its diff,
  gates, measures and commits ([`CLAUDE.md`](CLAUDE.md)). MyFlow only when Julia names it in
  the current session.
- **No person in the quality process** (D11, 2026-10-03): nobody grades, labels or approves; a
  model's check is never called a human one.
- **Commits are local and allowed; a push is Julia's decision, asked each time.** Command in
  [`CLAUDE.md`](CLAUDE.md). CI starts no job since `e81f0c5` (account billing), so before a
  push the whole unit suite runs on the Mac, plus mypy, bandit and pip-audit.

## Machines

- **Windows laptop:** editing, `ruff`, `mypy`, light scripts. No tests, models, WSL, Docker or
  VMs (owner direction, 2026-09-12). One exception, her word of 2026-11-03 «нужно делать все,
  значит, на этой машине»: the chat product and its Codex measurements run here, profile
  `codex-only` — every model call goes to Codex, never Ollama or another local LLM
  ([`PLAN.md`](PLAN.md) stage 6 item 0). Tests still run on the Mac.
- **`deproject-mac`** (production, 8 GB): tests, models, Docker, measurements. Tests go through
  `.tmp/mf-mac/sync.py`, then `.tmp/mf-mac/remote.py`. One measurement at a time; no tests
  during a live run; time numbers only from an idle Mac.
- **One writing session per repository.** A second session at the same time only reads: no
  `sync.py` or `remote.py` (a sync rewrites the Mac's gate checkout under the other session's
  tests), and its result names the SHA it read (audit of 2026-10-18, F-6).
- **Do not touch what the session did not start** — `ollama serve`, other projects' jobs,
  PostgreSQL. Restarting `ollama serve`, installing anything (brew included) — Julia's word.
- **Indexes are never rebuilt in place**: a new generation is published beside the old one
  (`build_vector_store_with_publication`; rollback `rollback_vector_store`).
- **The stand's `.ask100-runtime/env.json`** pins an old model (qwen2.5:7b): never read, print
  or copy it; the run scripts strip its model keys so the code defaults apply.

## Evidence

- **The slice rule** ([`CLAUDE.md`](CLAUDE.md)), binding for autopilot too: a slice counts
  only with (a) an E2E test of changed `/api/ask` or UI behaviour, (b) more real labelled
  cases, or (c) a published number with provenance. "Locally complete" is preparation.
- **A number needs provenance** — corpus SHA, code SHA, config. A run that did not happen is
  `NOT_EVIDENCE`, never a pass.
- **A record** lives in `reports/<name>/<commit>/` with a test that derives every number from
  it and one row in [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md); its write-up, if any, in
  `docs/evidence/`. Never add files to a published record's folder; never edit `reports/`.
- **Tests pin exact sentences** of capsules and specs: grep `tests/` before rewording one.
- **Root `.md` files: at most 9**; line caps — `CURRENT_STATE.md` 150, this file 120,
  `BACKLOG.md` 60. After touching a root `.md`: `tests/test_docs_hygiene.py`,
  `tests/test_docs_quality.py`, `tests/test_docs_publication.py`.
- **History goes to `archive/`**, never deleted; [`archive/README.md`](archive/README.md) maps
  it. Planning is never done from `archive/`.

## Frozen

Trust Foundation steps 5–10, G9+, REL-03D, MCP connectors, enterprise DoD (2 replicas, SBOM,
SOC2-shaped gates), framework-grade GraphRAG (LightRAG, MS GraphRAG, Neo4j). Conditions are in
[`ROADMAP.md`](ROADMAP.md); wanting the system more complete is not one. The in-repo structure
and entity graph (stream GR) is live: re-measured in [`PLAN.md`](PLAN.md) stages 2 and 7.

## Traps that cost sessions time

- **Two answer paths.** The chat (`/api/ask/stream`) is the product; the widget's `/api/ask`
  adds rewriting and grading. Numbers from one do not describe the other.
- **The lexical precision ruler** (0.63 gate) does not track meaning (P2) — not a threshold.
- **Some files at HEAD are not ruff-formatted**: format only the lines you wrote.
- **A whole-answer time on the Mac is minutes** (4B median 320 s) — size every run by it and
  stop at three times the forecast.

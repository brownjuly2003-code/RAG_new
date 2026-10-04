# T-65 production baseline — preparation, 2026-10-02

T-65 remains open: no new quality measurement has been published.

## Implemented prerequisite

`scripts/ab_remote_contextual.py --stage production --retrieval-only` uses
`ConversationSession.ask` with the normal production graph and interrupts it
before `generate`. Classification, query transformation, retrieval, expansion,
reranking and the normal conditional grading path remain unchanged. Simple
queries still bypass grading, as they do in production.

The mode retains budgets and tracing, refuses agentic mode, and writes no answer
or history. Answer evaluation is omitted. Full production replay remains the CLI
default; archived stages cannot use `--retrieval-only`.

Output: `production_retrieval_contexts.json`, every row marked `retrieval_only`;
existing output is not overwritten. Context is the post-grading generation input.

## Fresh verification

- Red: missing session keyword and CLI flag (4 failed, 1 passed).
- Mac: retrieval-only, harness parity, route, session version/serialize tests:
  **285 passed**; strict mypy **145 files**, scoped Ruff clean.
- Fixture models prove control flow, not quality.

## Pinned embedding preparation — 2026-10-02

Older Mac indexes and `RAG_new_gr2m_results_9ca8630/chunks.npz` have no pinned
embedder identity; do not reuse or retroactively stamp them for this baseline.

`scripts/production_embeddings.py` saves a cumulative NPZ checkpoint atomically,
binding corpus/text hashes and the embedder manifest. Explicit `--resume` refuses
incompatible or invalid vectors. `--max-batches` bounds a run. No defaults changed.

Fresh verification:

- Red: 16 tests failed on the absent module. Windows green: **16 passed**.
- Mac: `pytest tests/test_production_embeddings.py
  tests/test_production_retrieval_only.py tests/test_harness_api_parity.py
  -q -p no:schemathesis --tb=short` — **275 passed**; scoped Ruff passed.
- Embedding snapshot: `/Users/julia/RAG_new_t65_embeddings_2851e3811508`.
- BGE-M3 revision `5617a9f61b028005a4858fdac845db406aefb181`, 1024 dimensions,
  normalized, `hf_snapshot`; resume preserved the first vector exactly.
- Corpus archive: `evaluation/gr1b-4436d61-graph-chunks.json.gz`, SHA-256
  `2a9da515a4c69b46453a59ed6d0bb772b0aad6fed23c87ee465851b43dbdef12`.

The full embedding calculation **completed** at `2026-10-02T14:01:16Z`, exit 0,
after starting at `12:42:17Z` (Mac PID `74090`, batch size 8). All **5589 × 1024**
vectors are complete and validated. Do not re-encode this corpus. The snapshot's
`.tmp/t65-embedding-full-state.json` and `.tmp/t65-embedding-full.log` retain the
terminal result; checkpoint `.tmp/t65-verified-embeddings.npz` has SHA-256
`3903187e56dd4d8accf642f612910c6ca2082d1e7e55b7d67cd072ce0978fb5a`.

Executor: Codex fallback after two GLM `incomplete/max_output_tokens` responses;
neither partial response was applied.

## Isolated index builder — 2026-10-02

`python -m scripts.production_index --help`: requires a complete checkpoint,
independent manifest and code SHA; checks corpus/text hashes, manifest, count,
dimension and normalization. Creates a new index only, persists HNSW adds, writes
`index-receipt.json`. Collection: `rag_docs_aircargo`. Production defaults unchanged.

- Red: 12 tests failed on the absent builder module.
- Mac: `pytest tests/test_production_index.py tests/test_production_embeddings.py
  -q -p no:schemathesis --tb=short` — **28 passed**; scoped Ruff and CLI help passed.
  Fresh-process reopen verified fixture vectors, text, metadata and manifest.
- Executor: continued Codex fallback from the two incomplete GLM requests above.

### Real index verified

Built with `72fbd72`, ChromaDB 1.5.9; directory on Mac:
`/Users/julia/RAG_new_t65_embeddings_2851e3811508/.tmp/t65-index-72fbd72`.
`index-receipt.json` pins corpus, checkpoint, text order, embedder, code and build
configuration. A separate process verified all 5589 vectors **exactly**, all
texts and metadata against the inputs, and `check_collection_manifest` returned
`match` / `eligible`. Log sequence = persisted vector sequence = **5589** (tail 0).
Report: `reopen-verification.json` beside the receipt; local copy:
`.tmp/t65-index-reopen-verification.json`. This verifies storage, not quality.

Runtime for builder/verification: `/Users/julia/RAG_new_gr4_venv/bin/python`
with `PYTHONPATH=/Users/julia/RAG_new_mf_gate_site` (also used for the tests).

## Staged parity runner — c3d2909

`scripts/production_parity.py`: prepare → transform → embed → retrieve → grade
→ verify. Registers 30 H cases by ascending SHA-256(case_id), data/code/runtime
identities, model revisions and config before results. Uses production provider,
graph nodes and HybridRetriever; replays saved real calls through ConversationSession.
Compares vector/pool/ranked order, effective query and post-grading context hash.
Cache misses, corrupt records, model errors and replay mismatches refuse evidence.
Resume is explicit; `--limit 1` bounds the initial smoke. Replay is not API latency.

Mac: **17 passed** (`test_production_parity`, `test_production_retrieval_only`),
scoped Ruff clean. Real Chroma / fixture models; includes rejected-document,
missing-cache and replay-mismatch cases. Snapshot:
`/Users/julia/RAG_new_t65_parity_9216fc576828` (archive SHA starts `9216fc576828`).
All model stages use `/Users/julia/RAG_Support_Assistant/.venv/bin/python` with
the package path above; tests append the lightweight venv's site-packages for pytest.
Codex fallback continues. Real smoke completed at `2026-10-02T15:08:42Z`, exit 0.
Fresh inspection: `aircargo-matliab-check` differs in vector/pool order between
Chroma and exact; ranked order and post-grading context hash match (five documents).
Both arms replayed through ConversationSession. This is one case, not the full result.

The full 30-case run at c3d2909 (resumed from the smoke records, snapshot's
`.tmp/parity-c3d2909`) stopped in `grade`:
`Model/cache calls failed: ['llm/64aa36e2…']`. Launcher `17156` printed `DONE 1`;
collector `19888` recorded `failed` and copied nothing. Both processes have exited.
The run is NOT_EVIDENCE; its records stay in the snapshot for diagnosis only.

Cause: Qwen answered the batch grading schema request with the bare word `YES`.
`OllamaProvider.generate_with_schema` raised `StructuredOutputValidationError`.
Production catches it and falls back to the text grade, but the runner counted
that completed reply as a failed model call and refused the stage.

Report: `python -m scripts.production_parity_report --run <run> --output <new.json>`
checks 30 grade/verify records, context hashes, replay fields and summary; counts
order/membership/context differences, pins inputs, refuses overwrites. Use a
separate checkout; preserve the active snapshot. Red: 11 failed; Windows/Mac:
**11 passed**, Ruff clean. No new measurement published.

## Parity runner fix — T-66

Spec: [`production-parity`](../specs/production-parity.md).
- A completed reply that fails schema validation is a recorded outcome. The record
  holds the error type, the message and the raw reply under the same integrity check.
- The runner raises the same error in live and replay. Production's fallback
  therefore runs identically in both arms and in the session replay, and the
  outcome is not a failure.
- These remain failures and are never cached: a timeout, a connection error, a
  digest mismatch, a cache miss, a corrupt record and an unknown recorded outcome.
  `require_clean` refuses with the first of them as `__cause__`.
- Tests: `tests/test_production_parity_outcomes.py`.
- The source identity changed, so the c3d2909 cache cannot be reused. The 30-case
  comparison restarts from `prepare` at the T-66 commit.

## Remaining T-65 work

1. Checkpoint and isolated index are verified; pin the remaining model digests
   and retrieval runtime config before the measurement. Use the existing index.
2. Run the bounded real Chroma/exact comparison on 30 H cases from `prepare` at
   the T-66 commit and publish any divergence (T-62 acceptance boundary).
3. Collect H 100 + Hm 15 through the retrieval-only path, retain trace timings
   and exclude failed/ineligible runs. Record corpus SHA, code SHA and config.
4. Judge the new contexts, compute lexical/development metrics and the loss map,
   publish the capsule and evidence row. Keep `provisional_ruler` until slice 1.1 passes
   (D2 as changed by D11: CI of κ entirely ≥ 0.7 to both model references) and, because these
   contexts are expanded, until the reference sub-sample for expanded contexts is graded
   (metrics spec, «Scope»; plan G38).

No human D2/D3 inputs will arrive (decision D11, 2026-10-03; the plan-revision section below).
No retrieval default or quality gate changed.

## Stop point — 2026-10-03 (after T-68)

Julia, ~03:20 UTC: «поставь точку после текущего шага», then «не закрывай сейчас T-69».

- **T-68 landed** as `af93851` and is pushed.
  - `scripts/production_baseline.py` collects H 100 + Hm 15 on the production Chroma arm with
    recorded exclusions and stops. The exclusion rule is a requirement in
    `semantic-precision-metrics.md`.
  - Mac full gate GREEN on tree `0191c49cc9`: unit 4497 passed, 43 skipped; resolution E2E 36
    passed; strict mypy clean.
  - No quality number.
- **The T-66 parity run finished on the Mac.**
  - Location: snapshot `/Users/julia/RAG_new_t66_parity_b0e67e609e77`, run
    `.tmp/parity-c729b23`.
  - All six stages completed; verify exited 0 at about 03:00 UTC. Item 2 above has run.
  - It is not yet collected or published; that is T-67 (`production_parity_report`, SHAs,
    capsule, evidence row). Until then the comparison is NOT_EVIDENCE.
- **Mac processes.** llama-server is no longer running: the parity runner stopped it after
  grade, and the agent did not touch it. `ollama serve` (pid 12377) is running. The T-65
  collection needs the model again.
- **T-69 is prepared but not started.** MyFlow has no open slice: T-68 passed, 65 of 70 tasks.
  - The lead's decisions are appended to the T-69 detail (`task-edit`, 2026-10-03):
    - the v2 consensus follows the spec's plan rule, including the 5 % judge exclusion;
    - a unit is (case, `text_sha256`), and `text_sha256` is the ruler's doc id;
    - the split rule;
    - the exact chunk text goes out, including its `[Контекст: …]` line;
    - outbound volume is counted from the reply stores;
    - endpoints come from `RAG_JUDGE_GK_BASE` / `RAG_JUDGE_GLM_SETTINGS`.
  - GLM 5.3 direct (xhigh, end_turn) wrote two files:
    - `.tmp/t69/judge_consensus.py`: the reviewed, ruff-formatted
      `evaluation/judge_consensus.py`;
    - `.tmp/t69/result-script-001.txt`: `scripts/baseline_judge.py`, raw and not reviewed.
  - Not done:
    - the tests, `tests/test_baseline_judge.py`, in two GLM requests;
    - the lead's extraction of `judge_version(judge, client, endpoint)` from
      `scripts/relevance_judge_v2.py` `main`. The prompt for the script assumes it.
- **Backup** on origin: branch `wip/T-69-prep`, commit `e5525fa` on top of `af93851`, 127 files.
  - Contents:
    - `.tmp/t69/`, `.tmp/notes/`, `.tmp/glm-direct.py`, `.tmp/mf-mac/*.py` and `steps.json`;
    - the MyFlow resume files: state, tasks, config, spec, checkpoint, journal, progress,
      `summary-T-68.md`, `writer/T-69-preamble.md`.
  - Every blob was checked against the tree with `hash-object`. A restore into a scratch tree
    gave 0 content differences.
  - Restore only if the working tree lost these files:

        git diff --name-only wip/T-69-prep~1 wip/T-69-prep |
          xargs git restore --source=wip/T-69-prep --worktree --

- **Resume, in order:**
  1. `$MF continue`, then `$MF next` → T-69. `attach-commit` warned that T-69 and T-70 name
     the changed `production_baseline.py`. T-69's detail is current; re-read T-70's before its
     `next`.
  2. Extract `judge_version` in `scripts/relevance_judge_v2.py`. Copy
     `.tmp/t69/judge_consensus.py` to `evaluation/`. Review and apply the script from
     `result-script-001.txt`.
  3. Tests by GLM direct in two requests, the FALSE-REJECT control included:
     - consensus, store and ruler;
     - plan, split, prompts, resume, outbound and the consensus CLI.
  4. Close T-69: local venv tests, `done T-69 --detach`, review, Mac full gate, scoped commit,
     push.
  5. After T-69 lands, delete `wip/T-69-prep`. Also delete the stale `wip/T-61-writer`; T-61
     landed in `67e7be1`.
  6. Then T-67 (parity publication), T-70 (loss map) and T-65 (the real baseline on the Mac).

## Plan revision — 2026-10-03 (plan session, after the stop point)

Nothing in the resume order above was executed. Three things changed around it:

- **The quality plan is now [`plan_03_10_26.md`](../specs/plan_03_10_26.md).** It supersedes
  `plan_final_30_09_26.md`; slice numbers and the 2.5 chain are unchanged. Decisions D1–D10 stand
  except D2, D3 and D10, which D11 changed (last bullet).
  Task details that cite the 30.09 plan by slice number stay valid. Expect MyFlow drift
  advisories on tasks that reference the two edited specs: `semantic-precision-metrics.md` got
  one cross-reference in «Screening tier» (no criterion changed) and, with D11, its fifth
  revision (who grades and verifies; thresholds, margins and metrics unchanged), and the old
  plan got a "superseded" banner.
- **T-70's detail got an appendix**: the lexical-lane research data are a reconciliation for
  the full loss map — not evidence and not an input of the calculation. The study's results stay
  outside the repository (Julia, 2026-10-03), so the appendix points to
  `D:/Rag_research/2026-10-03_PLAN_INPUT.md`, §4 item П2 and §3.4. The edits cleared T-70's
  MyFlow stale hint and moved its `detail_at`. The re-read asked for in resume item 1 is still
  owed: T-70's detail was not checked against the artefacts `scripts/production_baseline.py`
  writes. The detail says so itself.
- **Julia's order, 2026-10-03: phase E first.** GitHub Actions execute jobs again and CI is red
  on HEAD ([`CURRENT_STATE.md`](../../CURRENT_STATE.md)); the "Actions unavailable until
  October" rule is gone from `CLAUDE.md`. The next work is a green CI on HEAD (plan slice 0.1b;
  the failure causes are listed under the status table in plan §1). The resume order above —
  `$MF next` → T-69, then T-67, T-70 and T-65 — starts after that; the `wip/T-69-prep` branch
  keeps the T-69 preparation meanwhile.
- **Julia's decision D11, 2026-10-03: «люди участвовать в процессе не будут».** The plan holds no
  human work any more. Slice 1.1 (T-57, rewritten) is κ of the P2 consensus to the Astra and
  Opus references; slice 1.3b is verification of the pilot drafts by two models of other
  vendors; the human checks of 2.8 and 4.1 became model checks. Both 1.1 and 1.3b queue after
  the chain above, and nothing in the chain itself changes. What replaced what, and what the
  plan no longer claims (`human-validated`, `real_labelled`): plan §2, record D11; eight open
  design questions: plan G38. Session log:
  [`session-handoff-2026-10-03-plan-revision.md`](session-handoff-2026-10-03-plan-revision.md).

## T-69 done — 2026-10-03 (after the green CI)

- **CI is green**, so Julia's order of 2026-10-03 is met and the resume order of the stop point
  applies again. Observed runs: `45a417a` — CI 37157492007, 11 of 11 jobs; `1fbbf65` — CI
  37160903526, 11 of 11 jobs, Pages 37160903511 (`build` passed, `deploy` skipped: the
  repository is private). What was red and what fixed it: [`CURRENT_STATE.md`](../../CURRENT_STATE.md).
- **T-69 is done: the tooling that regrades baseline contexts with judge v2.** No judge was
  called and there is no quality number; the real calls belong to T-65.
  - `scripts/baseline_judge.py` has three commands over one judge directory:

        python -m scripts.baseline_judge plan --run <baseline run> --out <judge dir>
        python -m scripts.baseline_judge judge --out <judge dir> --judge glm
        python -m scripts.baseline_judge judge --out <judge dir> --judge sonnet
        python -m scripts.baseline_judge consensus --out <judge dir>

    - `plan` reads a finished `scripts/production_baseline.py` run and refuses an unfinished
      one: no `report.json`, an open abort, a grade row of another run.
    - `judge` sends the planned requests through `run_judge_v2` and resumes by `request_key`.
      Sonnet needs `RAG_JUDGE_GK_BASE`; GLM settings come from `RAG_JUDGE_GLM_SETTINGS` or the
      client's default. Neither value is printed or stored; the store keeps the endpoint's hash.
    - `consensus` writes `ruler-input.json`, the input of `evaluation/semantic_ruler.py`, or
      says `NOT_EVIDENCE` when no judge graded a unit.
  - `evaluation/judge_consensus.py` holds the v2 consensus (lower median, the 5 % judge
    exclusion of the `blinded-relevance-judge` spec), the store reader and the ruler adapter.
  - `scripts/relevance_judge_v2.py`: `judge_version` is one shared function, so both command
    lines give a judge the same version string.
  - Tests: `tests/test_baseline_judge.py`, 114 tests on fixture runs with fake judges.
  - The requirement is "baseline contexts are regraded by a fixed plan" in
    [`blinded-relevance-judge.md`](../specs/blinded-relevance-judge.md).
- **What T-65 has to know about these commands.**
  - One judge directory holds one plan and, per store, one judge version, counted over every
    attempt, failed ones too. A changed endpoint or changed judge parameters need a new
    directory: `judge` refuses the old one before any request, and `consensus` refuses a store
    that mixes versions.
  - A judge that misses more than 5 % of the units is left out, and the other judge alone
    forms the consensus. The summary names it under `excluded_judges`; a capsule built on such
    a run has to say that the consensus is one judge.
  - A text without a chunk address is not sent. Its case leaves judged precision with the
    reason, and `judged_precision_excluded` counts such cases; no grade is substituted.
  - A text sent twice is one document for `sent_precision`; `repeated_sent_texts` counts the
    repeats. Seeds stay as ranked: the ruler counts a repeated seed as a miss.
  - `outbound` in each summary is the upper bound of what left the machine — calls, texts and
    prompt characters — for the capsule (plan G31).
- **Executor.** GLM 5.3 direct (xhigh) wrote the two new modules on 2026-10-02. GLM reached its
  weekly cap (`1310`) on 2026-10-03, so by the recovery policy GPT-6.1-Sol (profile `cw`) wrote
  the tests and the four fixes that the review by GPT-6-Astra asked for; the lead extracted
  `judge_version`, added five tests, wrote the spec requirement and reviewed the modules
  against the collector's artifact format.
- **The backup branches are no longer needed.** `wip/T-69-prep` (`e5525fa`) and the stale
  `wip/T-61-writer` (`5fd53e5`; T-61 landed in `67e7be1`) are deleted from origin once this
  commit is pushed. `plan_03_10_26.md` §1 still names the first one, as of its fourth
  publication.
- **Resume, in order** (replaces the list in the stop-point section):
  1. T-67 — publish the parity run: `manifest.json`, `comparison.json` and `report.json` from
     the Mac run named in the stop-point section, a capsule, an artifact test, an evidence row.
  2. T-70 — the full loss map. Its detail was not yet checked against the fields
     `scripts/production_baseline.py` writes; do that before `next`. Known so far: the
     retrieve and grade rows carry `vector`, `pool` and `ranked` chunk indices, `seed_documents`,
     `expanded_documents` and `documents`; the baseline runs the hybrid lane with the graph
     off, so the graph lane's caps and coherence stages have no artifact of their own.
  3. T-65 — the real baseline on the Mac; llama-server has to be started again.
  4. Then T-57 (`unpark`) and the task for slice 1.3b.

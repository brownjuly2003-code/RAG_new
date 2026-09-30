# Session handoff — 2026-09-30, quality plan after phase E

Written for the next session (autocompact is on). HEAD `32b526b`, branch
`master`, **nothing committed, nothing pushed, no code changed** — Julia asked to
review first («давай сверимся»). Executor for code slices: GLM 5.3 direct
([runbook](direct-glm-5.3.md)); Astra = `gpt-6-astra` via the Codex companion,
not GLM.

## What this session produced (all uncommitted)

| Artefact | State |
|---|---|
| [`docs/specs/plan_final_30_09_26.md`](../specs/plan_final_30_09_26.md) | the deliverable: four tracks, slice table with dependency graph (§1, mermaid), decisions D1–D7 (§2), calendar (§3), executor specs for 2.1/2.2, 2.3, 2.4 (§5), reactions to both audits and to Julia's questions (§6) |
| [`docs/specs/semantic-precision-metrics.md`](../specs/semantic-precision-metrics.md) | pre-registered development ruler, revised twice (GLM, Astra): grading unit = text hash, gold evidence groups, applicability, numeric fact coverage, clustering, acceptance contract with answer metrics |
| [`docs/audits/audit_glm_30_09_26_plan.md`](../audits/audit_glm_30_09_26_plan.md) | GLM 5.3 second-voice audit of the plan (direct API, 375 s), 13 findings, all accepted except `corpus_sha256` in 2.1 |
| [`docs/audits/audit_astra_30_09_26_plan.md`](../audits/audit_astra_30_09_26_plan.md) | Astra audit of the plan (Codex, 30 min, read the repo), 15 findings A1–A15, all accepted |
| `CURRENT_STATE.md`, `ROADMAP.md`, `BACKLOG.md`, `docs/windows-test-workflow.md` | state docs: quality thread «adopted by delegation, ratification pending»; Q row rule under the new ruler; phase E paragraph names the verified tree `c81de77`; Windows integration command narrowed |
| `docs/specs/external-benchmark-candidates.md` | Opus research report (R0): ConditionalQA primary, WixQA fallback, MultiHop-RAG reserve; reflected in plan 1.5/1.5b and D7; ConditionalQA «ONLY NLP research» caveat accepted by Julia 2026-09-30 |
| Julia's own untracked files | `docs/audits/audit_asta_30_09_26.md`, `docs/specs/plan_30_09_26.md`, `demo/phase-e-raw.webm` — untouched |

Outside git (`.tmp/`, gitignored): `quality-slice-2.1-observability.patch` +
`test_graph_route_observability.py` (partial draft of an earlier §5 revision,
not evidence), `glm-direct-long.py` (1800 s direct GLM call),
`astra_build_prompt.py` → `glm-plan-prompt.txt`, `astra-plan-audit-prompt.md`,
`apply_glm_reactions.py`, `apply_astra_reactions.py`, raw audit outputs,
Codex companion state in `.tmp/cx-work-state/`.

## Decisions taken by delegation (plan §2)

D1 plan adopted, ratification = slice 0.3 · D2 human grading not delegated,
consensus ruler provisional with κ-CI rule · D3 agent drafts, Julia approves,
holdout locked after approval (1.3e) · D4 H7 outside the reranker stop-list ·
D5 no absolute SLO until a deployment target; Mac is not «target hardware» ·
D6 lexical 0.63 is not a product-SHIP condition, non-inferiority −0.02 instead ·
D7 external benchmark = second ruler, judge validation, never the SHIP decision.

## Julia's additions during the session

- Slices cut with a dependency graph (§1).
- 3.0 graph-enablement policy (selection rule, own gate, shadow → per-tenant →
  default, rollback); 4.3 is its last step.
- 2.6 extended to the `simple`/not-simple verdict audit (routing is off by
  default: `MODEL_ROUTING_ENABLED=false` → no verdict at all); gold
  `complexity` in the 1.3a case schema.
- 2.8 NLI-judge validation (C.1b showed supported-claim rate 1.0000 — saturation);
  the pinned mDeBERTa at 0.5 is `provisional_judge` in the spec until 2.8.
- 1.5/1.5b/1.5c/1.5d external benchmarks: all three from the Opus report with
  roles — ConditionalQA primary (judge validation), WixQA (real support
  questions), MultiHop-RAG advisory (`llm_labelled`, cross-doc for H2/H3/3.0).

## Verification done

`py -3.13 -m pytest tests/test_docs_hygiene.py tests/test_docs_publication.py
-q -p no:schemathesis` → 10 passed after every edit; `CURRENT_STATE.md` 136
lines (cap 150); root has 9 `.md` files (cap 9 — do not add a tenth). Ruff at
HEAD still shows the known I001 in `tests/test_docs_publication.py` (plan 0.2).
No Mac gate, no model run, no benchmark run happened.

## Next actions

1. R2 research (NLI/faithfulness judges) **done** 2026-09-30 ~19:50 UTC (Opus,
   233k tokens, read-only): `docs/specs/research-nli-judges.md` (587 lines),
   reflected in plan 2.8 / G10 / §6 / §7 queue. Key: saturation on C.1b not
   proven a judge defect (Qwen3 answers near-verbatim; reference LLM judge =
   same Qwen3-8B with 3,000-char window); truncation never fires; main defect =
   claim unit (fragments ≤ 3 words); «mDeBERTa large-xnli» does not exist;
   candidates `…-xnli-multilingual-nli-2mil7` (main), `cointegrated/rubert-base-
   cased-nli-threeway` (fallback), `KRLabsOrg/lettucedect-v2-mmbert-base`
   (detector); protocol 200 claims, Julia labels all + 40 retest, κ ≥ 0.6.
   **R1 (embedders ≤ 8 GiB CPU) launched** 2026-09-30 ~20:15 UTC on Opus, read-only,
   report → `docs/specs/research-embedders.md`; reflect it in G2 / H9 (track 3)
   when done. Then R3, R4, R5, R6 per plan §7, one agent at a time.
   **R1 analogues** requested by Julia («запусти аналоги текущего рисеча (опус)
   на кодекс (sol xhigh) и glm 5.3 max»), launched ~21:05 UTC:
   - R1-Sol: companion job `task-muokedaz-7zgmrz`, `gpt-6-sol`, effort `xhigh`,
     prompt `.tmp/r1-sol-prompt.md` (same questions as the Opus prompt, answer
     returned inline, read-only) → **done** 20:46 UTC, 16.5k chars, no
     network, saved as `docs/specs/research-embedders-sol.md`. Repo facts it
     computed: phase C pool 98 RU / 2 EN questions, chunk body median 576 / max
     800 chars, 5 589 chunks / 201 files; Mac note 2026-05-30: bge-m3 + reranker
     together → 1.5 GB swap. Recommends `multilingual-e5-base` first (needs a
     prefix patch in `_STEmbeddings`), `gte-multilingual-base` fallback; GLM
     disagrees (USER-bge-m3 drop-in). Resolve with Opus R1 when it lands.
     **Second Sol R1 run** requested by Julia («перезапусти sol»), launched
     ~21:50 UTC: job `task-muol011j-rydvyx`, same prompt/model/effort; raw →
     `.tmp/sol-r1-result-2-raw.txt`, then appended to
     `research-embedders-sol.md` as «Прогон 2». **Done** 21:00 UTC,
     14.9k chars, no network again; appended (headings demoted). Differs from
     run 1: gte-multilingual-base first, e5-base fallback (reversed); candidate
     lengths on full text 708/924/969; corrects 0.5475 = GR-1b, not GR-0.3
     (0.5067); primary H9 metric sent_precision; frozen pool inapplicable to
     an embedder swap. Sol is now split with itself → H9 stays frozen (Astra).
   - R1-GLM: direct API, effort `max`, window 64 000, split A (sections 0–3) /
     B (4–7 with A inlined) by `.tmp/r1_build_glm_prompt.py`; prompt inlines
     settings.py 380–420, _base_manager.py 160–340, plan G2/track 3/D4, GR rows,
     the full ruler spec. Outputs `.tmp/glm-r1-A-001.txt`, `.tmp/glm-r1-B-001.txt`
     → save as `docs/specs/research-embedders-glm.md`. Cross-check all three in
     plan §6/§7 (G2, H9) once Opus R1 lands. **Part A done** (end_turn, 239 s,
     11k chars): main `deepvk/USER-bge-m3` (drop-in, same dim/ctx, no prefixes),
     fallback `ai-forever/ru-en-RoSBERTa`, cheap probe `deepvk/USER2-base`; code
     adds no query/passage prefixes → e5-family needs a code patch; RAM est.
     bge-m3 2.5–2.9 GB RSS + reranker ≈ 5–5.5 GB of 8; main risk: dense-lane
     effect diluted by BM25+RRF+reranker, RU→EN share unmeasured. **Part B done**
     (end_turn, 355 s, 18.6k chars) → `docs/specs/research-embedders-glm.md`
     written (header + A + B). B adds: pre-registration file
     `docs/specs/h9-embedder.md`, step 0 = count RU→EN/paraphrase share on dev
     from the class sidecar before any re-index, preflight (RSS, throughput,
     licence, prefixes, triplet sanity) → probe USER2-base → USER-bge-m3 →
     RoSBERTa only if CX drops; keep bge-m3 as runtime default until the gate.
1b. Two extra benchmark researches launched 2026-09-30 ~19:30 UTC on Julia's
   request («2 доп исследования на sol 6.1 xhigh (кодекс) и glm 5.3 max»):
   - **R0-Sol**: Codex companion job `task-muoi4lux-2z344g`, model `gpt-6-sol`
     (the companion lists `gpt-6-sol`/`gpt-6-astra`; no «6.1» id exists), effort
     `xhigh`, prompt `.tmp/bench-research-sol-prompt.md`, read-only task with
     repo access. Status: job json under
     `.tmp/cx-work-state/state/RAG_new-7b12fe53d2d59a38/jobs/`; read back with
     the cw-profile env prefix + `codex-companion.mjs result task-muoi4lux-2z344g
     --cwd D:/RAG_new`. **Done** 19:40 UTC, 22.9k chars, no network:
     report saved to `docs/specs/research-benchmarks-sol.md`; factual fixes
     applied to plan 1.5b/1.5c/1.5d, proposals (i)–(v) listed in plan §6
     «R0-Sol» and await Julia's «вноси». **Second Sol run** requested by Julia
     («запусти sol еще раз»), launched ~20:25 UTC: job `task-muoj3smf-vyzj0o`,
     same prompt, model and effort; **done** 20:07 UTC, 22.2k chars, again no
     network, same conclusions → appended to `research-benchmarks-sol.md` as
     «Прогон 2»; its additions: `not_answerable` is document-relative (applied to
     plan 1.5), proposals (vi)–(ix) in plan §6 await «вноси».
   - **R0-GLM**: `.tmp/glm-direct-research.py` (copy of `glm-direct-long.py` with
     effort/budget args), effort `max` accepted by the API, thinking budget
     24 000, prompt `.tmp/glm-bench-prompt.txt` (built by
     `.tmp/bench_build_glm_prompt.py`: header + full R0 + plan rows 1.5–1.5d + D7
     + ruler acceptance contract, 42 296 chars). Output
     `.tmp/glm-bench-result-001.txt` (+ `.meta.json`); `.partial.txt` = not
     evidence. Report → `docs/specs/research-benchmarks-glm.md`. Attempt 1
     (max_tokens 48 000) ended `max_tokens` after 667 s: thinking consumed the
     window, 3.4k chars of text → `.partial` (not evidence). Attempt 2 launched
     with max_tokens 100 000, same effort `max`, budget 24 000 → the server reset
     the connection mid-stream (WinError 10054, no meta written). Two `max`
     failures → attempt 3 at effort `xhigh`, budget 16 000, max_tokens 48 000
     (the runbook setting that produced the plan audit) → output
     `.tmp/glm-bench-result-003.txt` → also `max_tokens` after 603 s: 14.1k chars
     of text, thinking ate the rest (`budget_tokens` is not enforced by z.ai).
     Method change (3 failures of the one-call approach): prompt split into
     part A = sections 0–3 and part B = sections 4–7 with A's answer inlined
     (`.tmp/bench_build_glm_prompt_split.py`), window 64 000, effort `max` first
     (Julia's ask), fallback `xhigh`. Outputs `.tmp/glm-bench-A-*.txt`,
     `.tmp/glm-bench-B-*.txt`; the xhigh partial (§0–§2.1, useful preview: NI
     −0.02 unattainable at n ≤ 500, text-hash namespace risk, evidence→hash
     resolution gate) stays `.partial` = not evidence.
     **Part A done** at effort `max` (end_turn, 42 602 output tokens, 580 s,
     23.9 kB): `.tmp/glm-bench-A-001.txt` + `.meta.json`. Roles confirmed; 7 new
     candidates all with blockers (ContractNLI, DUDE, GraphRAG-Bench, HRBench,
     RAGTruth, BioASQ, SHARC); no gross errors in R0, discrepancies FinanceBench
     ~48 vs 84 PDF [не уверен], FRAMES 824 questions, MuSiQue test 2 417 [не
     уверен]; proposals: doc-conditioned sub-metric, cheap full ruler (hybrid +
     evidence recall on all 2 623 questions, no rerank/generation) for power,
     1.5b register both label mappings + 50–100 human pairs outside gold docs,
     1.5d primary subset inference+null and `source`/`published_at` into chunks,
     no answer metrics there; licence: aggregates only, no chunk dumps or
     corpus embeddings published. GLM reads unselected ConditionalQA elements as
     human negatives (Sol disagrees) — flag in §6. **Part B launched** (sections
     4–7, A inlined, effort `max`, window 64 000) → `.tmp/glm-bench-B-001.txt`.
     **Part B done** (end_turn, 20 656 output tokens, 284 s) → report written:
     `docs/specs/research-benchmarks-glm.md` (header + A + B verbatim). Cross-check
     vs R0/Sol goes to plan §6 «R0-GLM».
   - Both prompts ask for: own candidate table on R0's 10 criteria, fact-check of
     R0 (§7 «Не проверено»), critique of the three roles, a pre-registered
     protocol for using three bases (power under the Mac budget), risks
     (judge contamination, HTML→chunk mapping, dataset drift), verdict per
     1.5/1.5b/1.5c/1.5d. When both finish: save reports with provenance headers,
     cross-check against R0, list disagreements in plan §6, and only then
     propose edits to 1.5–1.5d/D7 (plan §7 already points to both runs).
2. Julia: review the diff, ratify (0.3) and commit; grade the 10 blind cases
   (1.1); name a deployment target and SLO (D5); confirm D6/D7.
3. Executor (GLM 5.3): 0.2 hygiene, then 2.1/2.2 per plan §5, then 2.7.
4. Further research (serial, one agent at a time): see plan §6 «Открытые
   пробелы» once written; candidates listed in the session's last reply.

## Astra gap-closing consultation (launched 2026-09-30 ~20:55 UTC)

Julia: «нужно придумать, как закрыть все дыры. Запусти консультацию с кодекс
(astra max)». Job `task-muok6stt-jp168s`, model `gpt-6-astra`, `--effort`
omitted → cw-profile default `max`, prompt `.tmp/astra-gaps-consult-prompt.md`
(reads plan §6/§7, spec, R2, Sol, GLM reports, handoff, own earlier audit).
Asked for: a closure per gap (new slice / spec edit / explicit exclusion) with
rule, cost (Julia hours / Mac nights / executor hours), dependencies and
acceptance; critical path after additions; what to cut; risks of closures;
what cannot be closed; decisions on the three-voice disagreements. Result →
`docs/audits/astra_gaps_30_09_26.md` with provenance header; then Julia's
«вноси» decides what enters the plan. **Done** 20:54 UTC, 41k chars:
report saved; summary paragraph in plan §6 («Консультация Astra по закрытию
дыр»), G13–G21 rows in §7 now link to it. Nothing applied to slices/D-rows. Gap list G13–G21 recorded in plan §7
(session analysis before the consultation): own-set power, error analysis
before experiments, single annotator, label lifecycle vs chunking, trap set
for the system, strata minimums, acceptance generator pin, multi-turn,
Mac queue + executor fallback.

GLM benchmark research (R0-GLM) reflected in plan §6 as proposals (x)–(xvi)
and the three-voice disagreements paragraph.

## Gaps still open after both audits (session analysis, not audited)

Plan §7: G1–G12 with a research queue R2 → R1 → R3 → R4 → R5 → R6 (Opus, one
agent at a time; R0 = external benchmark, done; R0-Sol and R0-GLM cross-checks running at handoff). Items marked
«внести» are proposals awaiting Julia's «вноси».

## Step 9 — Astra decisions applied by delegation (30.09, late)

Julia: «прими решения сам. исходи из того, что нужен очень качественный
результат». Applied with `.tmp/apply_astra_decisions.py` (idempotent; re-run
refuses once `| D8 |` exists). Quality over speed — every closure G1–G21 and
every Sol/GLM proposal (i)–(xvi) resolved per Astra §5; nothing weakened.

- `docs/specs/plan_final_30_09_26.md`: header note; §1 track tables (1.3
  pilot 10/10/4/6, track-3 intro «≤ 2 mechanisms by the loss map», 3.6/3.7
  frozen, track-4 additions); slice rows 1.1, 1.2, 1.3a–e, 1.5, 1.5b (frozen),
  1.5c, 1.5d (frozen until a graph hypothesis), 2.1, 2.4, 2.5 (evidence-loss
  map), 2.7 (chunk address), 2.8 (reduced programme, second annotator,
  generator swap), 3.0 (static policy; 2.3 conditional; 2.6 soft), 3.1–3.5
  (3.3–3.5 only by the loss map), 3.6/3.7 frozen, 4.1 (one-shot holdout,
  actions, critical errors, fingerprint, empty history), 4.2 no date;
  mermaid rewritten (quoted labels; 4.1 no longer hard on 2.3, 3.0 not on
  2.6, S3x → S41 «один кандидат», external control after 4.1); readiness
  front and critical paths; D3 (second person), D6 (INCONCLUSIVE), D7 (single
  external control, three outcomes), **new D8** (first-campaign scope and
  freezes), **new D9** (−0.02 not weakened, MDE published); §3 calendar →
  six conditional stages + Mac queue with nights table + Julia hours +
  executor failure policy; §4 → 13 campaign boundaries; §5 2.1/2.4 additions
  (effective query, confidence null, contract cases); §6 «ждёт/ждут «вноси»»
  all resolved, outcome list (i)–(xvi), Astra block marked applied; §7 G1–G21
  statuses; research queue: R3/R4/R5/R6 excluded (D8).
- `docs/specs/semantic-precision-metrics.md`: scope line; third revision
  note; unit of grading = chunk address + `text_sha256` (+ case/rubric/judge
  keys); label migration (`needs_review`); `unjudged` for external sets;
  calibration protocol (G8); second annotator (G15); case schema (G6/G17/G18);
  power revised (no wider margin, MDE published, no transfer between tiers);
  screening tier; three verdicts incl. `INCONCLUSIVE`; ledger + one-shot
  holdout; acceptance contract adds generator fingerprint, single-turn,
  actions/critical errors, semantic invariants, external transferability line;
  answer metrics `action_correct`, `critical_errors`; provenance list extended.
- `docs/operations/direct-glm-5.3.md`: recovery policy bullet (one narrowed
  retry → Codex `cw`, disclosure, run-id, no `.partial`).
- Decisions I took beyond Astra's literal text (flag to Julia): D3 offers
  delegation to a second person but leaves «name them or confirm solo» to her;
  a convincing external contradiction does not cancel `SHIP_RESEARCH` but
  makes 4.2/4.3 an explicit owner decision; 1.5b and 1.5d frozen (not
  deleted) with return conditions; 3.1/3.2 stay the default pair unless the
  loss map says otherwise; the ratification step 0.3 is unchanged.
- Not touched: code, `CURRENT_STATE.md`, `ROADMAP.md`, `BACKLOG.md`, Julia's
  files; nothing committed.

## Step 10 — Opus R1 landed; second gap pass (30.09, late)

- Opus R1 (agent a2f7e555fc3536af2, 70 min, with network) wrote
  `docs/specs/research-embedders.md` (54k): main `ai-sage/Giga-Embeddings-
  instruct-480M-0826` @1763d60 (ruMTEB v1.1 retrieval 0.762 vs bge-m3 0.752,
  MIT, fp32 1.93 GB, trust_remote_code), fallback FRIDA as offline ceiling
  probe only; expected H9 outcome NO_SHIP — lexical proxy: needed chunk already
  in the pool in 93/100 cases, embedder can add ≤ 5 cases ≈ +0.01…0.015;
  precision lever is selection, not the embedder. Risk that acts now: code
  passes no prompt/revision, Chroma guard checks dimension only → same-dim
  model silently mixes vectors. Reflected in plan §6 (R1 paragraph), G2, the
  research-queue line, and closed as G25 (embedder stamp in 2.3 + provenance).
  Three R1 voices = three different models → supports the H9 freeze (D8).
- Second pass per Julia («ещё раз проанализируй, что упустили») with
  `.tmp/apply_second_pass.py`: new §7 rows G22–G35. Applied: G22 family map
  (1.3a + spec), G23 fact matcher (spec), G24 judge-call budget/cache/
  `single_judge` (§3 + spec), G25 embedder stamp (2.3 + spec), G26 what follows
  INCONCLUSIVE/NO_SHIP (D9), G27 second-annotator briefing (1.1), G28 ledger
  location/format (1.3e), G29 ratification names D3/D8/D9 (0.3), G33
  registered control = 2.5 baseline config (spec), G34 blind answer checks
  (4.1 + spec), G35 R1 disagreement noted. Left to Julia: G30 pause rule (N
  weeks), G31 corpus texts to external judges at screening volume, G32 5 %
  spot-check of screening drafts (+1 h).
- Docs tests after steps 9 and 10: `test_docs_hygiene.py` + `test_docs_publication.py`
  → 10 passed (basetemp final23, final24). Plan 97.5k chars / 860 lines, spec
  21.2k. Nothing committed; code untouched.

## Step 11 — D10 by delegation; final plan sent to two audits (30.09, late)

- Julia: «все решения сделай за меня, исходя из максимального качества
  финального продукта». Applied with `.tmp/apply_d10.py`: new D10 — pause
  rule N = 4 weeks after 0.3 without 1.3b → `paused`; external judges stay
  the P2 consensus (chunk texts + questions only, exclusion list registered in
  1.3a, volume in capsule); 5 % blind spot-check of screening drafts (+1 h,
  Julia hours now 27–48 / 18–34); second person needed for human–human κ but
  not blocking — G15 stays open until named; D8/D9 confirmed final. Rows
  G15/G30/G31/G32 closed, D3/D8/D9 «за Юлей» cells updated. Docs tests 10
  passed (basetemp final25). Plan 99.9k chars.
- Julia: «когда будет готов финальный план, отправь его на аудит кодекс
  (astra max) и glm 5.3 max». Launched:
  - Astra: companion `cw`, `gpt-6-astra`, effort profile `max`, read-only,
    prompt `.tmp/astra-final-plan-audit-prompt.md` (verdict, fidelity of its
    own consultation, consistency, methodology, executability, gaps, cuts,
    budget, CLAUDE.md rules) → job `task-muom7rs4-m96qhu`; result →
    `docs/audits/audit_astra_final_30_09_26.md` with provenance header.
  - GLM 5.3 direct, effort `max`, window 64 000, single call with CLAUDE.md
    rules excerpt + full plan + full spec inlined (`.tmp/audit_build_glm_prompt.py`,
    127k chars) → `.tmp/glm-audit-final-001.txt` (+ `.meta.json`); on
    max_tokens/reset fall back to split A/B (builder supports it) → result →
    `docs/audits/audit_glm_final_30_09_26.md`.
  - Findings will be applied by delegation (Julia's standing instruction),
    each with a note in §6; blockers first.

## Step 12 — GLM final-plan audit received and applied (30.09, late)

- GLM direct, `max`, single call worked: 398 s, 41.0k in / 38.6k out tokens,
  `end_turn`, 15.4k chars visible → saved with provenance as
  `docs/audits/audit_glm_final_30_09_26.md`. Verdict «не готов»: 1 blocker
  (1.3d fixed quotas vs power rule), 6 major (two verdicts in 4.1, D7
  two-base fold undefined, Codex fallback vs CLAUDE.md executor rule, 2.4/2.5
  baseline desync, nights and hours understated), ~20 minor.
- Applied by delegation with `.tmp/apply_glm_final_audit_fixes.py` (all
  findings except three rejected with reasons; list in plan §6 «Аудиты
  финального плана»): quotas as shares + n from 1.3c; `INCONCLUSIVE` in 4.1
  and spec contract; D7 fold rule (both bases confirm / any contradicts) +
  50-question CQA pilot + loss-map review before 4.2/4.3; track tables synced
  and declared overview; 1.2 ⇢ 1.1 dotted; external control after 4.1
  verdict; roles defined; nights 15–19 (8–10 weeks); Julia hours 29–48 /
  21–35 with delegation (+2–3.2 h audit of delegated); new critical error
  defined; invalid > 10 % → NOT_EVIDENCE; zero citations; choice rule for two
  SHIP_TO_HOLDOUT; corpus snapshot pinned; provisional_judge → human answer
  check decides; 2.1 draft delivery; preliminary loss map limited to
  observable stages; parity case set + archive paths + label schema format;
  external bases in a separate tenant; 4.1 judge budget; MultiHop-RAG ODC-BY.
  **`CLAUDE.md` edited** (executor bullet: fallback line) — goes into the 0.3
  ratification commit; root .md count unchanged.
- Astra final audit `task-muom7rs4-m96qhu` still running (monitor bdteimhd7).

## Step 13 — Astra final-plan audit received and applied (30.09, late)

- Codex companion `gpt-6-astra`, effort `max`, read-only, 26 min; result saved
  with provenance as `docs/audits/audit_astra_final_30_09_26.md` (Astra read
  the post-GLM-fix redaction — its SHA prefixes match). Verdict «не готов»:
  4 blockers (H1/H5 vs control do not isolate the mechanism; embedder manifest
  buried in the conditional graph slice; one NI rule over incompatible
  metrics; degenerate bootstrap proves NI), ~18 major, 3 minor. Code facts
  checked by me: coherence only in `get_graph_documents_with_path`
  (`_base_manager.py:764`), hybrid RRF of 20 + 20 with dedup
  (`settings.py:461`), `SentenceTransformer(model_name)` without revision
  (`:333`), routing-off sets `unknown` (`graph.py:1295`), citations = all sent
  docs (`graph.py:1943`), joint 5-doc judge request (`blinded_judge.py:111`),
  LLM judge truncation 3000/2000 (`generator_benchmark.py:369`).
- Applied by delegation with `.tmp/apply_astra_final_audit_fixes.py`
  (all findings; rejected only the chronicle move in №22). Consequences that
  change the campaign shape: H1 is a graph-lane mechanism → 3.1 registers an
  ablation plus graph-lane-vs-hybrid comparison; H5 becomes the lane's budget
  setting, not a second mechanism; 2.3 split into a mandatory embedder
  manifest (before 2.5) and a conditional graph lifecycle; 2.3/3.0 hard for
  H1; nights 17–22 (9–11 weeks); 4.2 waits for the transferability line;
  spec: closed deciding-metric table, interval-validity rule, scenario power,
  common pair mask, `citation_presence`, claim-level numeric facts,
  request-hash judge cache, families register. `ROADMAP.md` (2 lines),
  runbook and `CLAUDE.md` fallback line synced (quota → reset or fallback,
  narrowed retry only for recoverable failures).

## Step 14 — Step 0.3 executed by delegation (30.09, late)

- Owner: «прими все решения за меня из позиции — лучшее качество конечного
  продукта». Decisions taken: D1 ratified; D4 (H7 outside the stop-list) and
  D6 (0.63 not a SHIP condition) confirmed; D3/D10 — no second person named,
  single-expert caveat applies, slot open until 1.1; judge exclusion list
  empty; D5 — no deployment target, 4.2 undated; stage II entry = E.5 run on
  the Mac, E.4 publish does not block. The owner may revisit any decision
  before the first track-3 experiment.
- Status docs synced (`ROADMAP.md`, `CURRENT_STATE.md`, `BACKLOG.md`: «adopted
  and ratified by delegation»); pure line-reflow churn in `CURRENT_STATE.md`
  restored to HEAD wrapping (`.tmp/restore_reflow.py`, 5 paragraphs).
  That pushed the file to 160 lines (cap 150): the C.1a per-metric CI table
  was condensed into one paragraph (`.tmp/condense_current_state.py`; numbers
  and links kept) instead of re-joining lines.
- Committed locally on `master` (see `git log -1`): plan, spec, 6 audit
  reports, 10 spec/research docs, this handoff, status docs, `CLAUDE.md`
  fallback line, GLM runbook, `docs/windows-test-workflow.md`. Not staged:
  `demo/phase-e-raw.webm` (phase E artefact), no code. **Push not done** —
  gate for the owner (`git -c credential.helper='!gh auth git-credential'
  push origin master` after the Mac rerun of E.5 per `CLAUDE.md`).

## Step 15 — Delegation continued: MyFlow registration, E.5 rerun, Astra reference (30.09, late)

- Owner: «про за мной — я просила все сделать за меня», «регистрируй», and
  «про разметку — проверь на кодекс astra xhigh». Human grading of the 10
  blind cases stays a human step (an agent grade would calibrate a model
  against a model); Astra is added as a third model reference instead.
- MyFlow (`myflow_new` 2.4.14): plan tracks 0–2 registered with `task-add`
  as T-55…T-65 (details in `.tmp/mf-plan/`), `plan-validate` OK (65 tasks),
  `doctor` OK. T-57 (import of Julia's grades) parked until the grades exist;
  `scope allow tests/…` pre-approved for the code/docs slices. Executor stays
  GLM 5.3 direct per `CLAUDE.md`; MyFlow supplies gate, review and commit
  (slice opened with `next --task`, patch applied by the lead agent, then
  `done` → `review-run` → `gate --full` → `attach-commit`).
- Astra reference spec `docs/specs/p2-astra-reference-sample.md` committed as
  `b0386e9` before any corpus request; the only Astra request so far is the
  route probe (`Reply with exactly OK.`, empty directory, `xhigh`, read-only
  sandbox, thread `01a0f471-8824-76c2-96bc-f6bd3046692d`).
- T-55 (slice 45, E.5 rerun + F9): gitleaks on `b0386e9` → 0 findings; Mac
  unit attempt 1 → 1 failed (`BACKLOG.md` 70 > 60 lines after `122cfd4`),
  condensed to 59 lines; attempt 2 → 3,722 passed, 43 skipped; e2e → 36
  passed; I001 fixed in `tests/test_docs_publication.py`;
  `docs/windows-test-workflow.md` already carried the `py -3.13` and «full
  suite on the Mac» rules. Capsule section «Rerun on the ratified tree»,
  `EVIDENCE_INDEX.md` and `CURRENT_STATE.md` updated.
- T-56 (Astra collector): GLM 5.3 direct run `result-001` ended with
  `stop_reason=max_tokens` at 48,000 output tokens and 1,675 characters of
  text (the window went to reasoning) → recoverable failure, one narrowed
  retry `result-002` (collector script only, 20,334-character prompt) ended
  in `ConnectionResetError` (WinError 10054) mid-stream with no result file.
  Second failure → executor for T-56 switches to Codex `cw` per the runbook
  and `CLAUDE.md`, through MyFlow's own writer chain (`next --task T-56`,
  `writer`), disclosed in the commit message; the collector run itself, the
  SHA pins and the capsule stay with the lead agent.


# Session handoff — 2026-09-30, quality plan after phase E

Written for the next session (autocompact is on). HEAD `32b526b`, branch
`master`, **nothing committed, nothing pushed, no code changed** — Julia asked to
review first («давай сверимся»). Executor for code slices: GLM 5.3 direct
([runbook](direct-glm-5.3.md)); Astra = `gpt-6-astra` via the Codex companion,
not GLM.

## What this session produced (all uncommitted)

| Artefact | State |
|---|---|
| [`archive/docs/specs/plan_final_30_09_26.md`](../specs/plan_final_30_09_26.md) | the deliverable: four tracks, slice table with dependency graph (§1, mermaid), decisions D1–D7 (§2), calendar (§3), executor specs for 2.1/2.2, 2.3, 2.4 (§5), reactions to both audits and to Julia's questions (§6) |
| [`docs/specs/semantic-precision-metrics.md`](../../../docs/specs/semantic-precision-metrics.md) | pre-registered development ruler, revised twice (GLM, Astra): grading unit = text hash, gold evidence groups, applicability, numeric fact coverage, clustering, acceptance contract with answer metrics |
| [`archive/docs/audits/audit_glm_30_09_26_plan.md`](../audits/audit_glm_30_09_26_plan.md) | GLM 5.3 second-voice audit of the plan (direct API, 375 s), 13 findings, all accepted except `corpus_sha256` in 2.1 |
| [`archive/docs/audits/audit_astra_30_09_26_plan.md`](../audits/audit_astra_30_09_26_plan.md) | Astra audit of the plan (Codex, 30 min, read the repo), 15 findings A1–A15, all accepted |
| `CURRENT_STATE.md`, `ROADMAP.md`, `BACKLOG.md`, `archive/docs/windows-test-workflow.md` | state docs: quality thread «adopted by delegation, ratification pending»; Q row rule under the new ruler; phase E paragraph names the verified tree `c81de77`; Windows integration command narrowed |
| `archive/docs/specs/external-benchmark-candidates.md` | Opus research report (R0): ConditionalQA primary, WixQA fallback, MultiHop-RAG reserve; reflected in plan 1.5/1.5b and D7; ConditionalQA «ONLY NLP research» caveat accepted by Julia 2026-09-30 |
| Julia's own untracked files | `archive/docs/audits/audit_asta_30_09_26.md`, `archive/docs/specs/plan_30_09_26.md`, `demo/phase-e-raw.webm` — untouched |

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
   233k tokens, read-only): `archive/docs/specs/research-nli-judges.md` (587 lines),
   reflected in plan 2.8 / G10 / §6 / §7 queue. Key: saturation on C.1b not
   proven a judge defect (Qwen3 answers near-verbatim; reference LLM judge =
   same Qwen3-8B with 3,000-char window); truncation never fires; main defect =
   claim unit (fragments ≤ 3 words); «mDeBERTa large-xnli» does not exist;
   candidates `…-xnli-multilingual-nli-2mil7` (main), `cointegrated/rubert-base-
   cased-nli-threeway` (fallback), `KRLabsOrg/lettucedect-v2-mmbert-base`
   (detector); protocol 200 claims, Julia labels all + 40 retest, κ ≥ 0.6.
   **R1 (embedders ≤ 8 GiB CPU) launched** 2026-09-30 ~20:15 UTC on Opus, read-only,
   report → `archive/docs/specs/research-embedders.md`; reflect it in G2 / H9 (track 3)
   when done. Then R3, R4, R5, R6 per plan §7, one agent at a time.
   **R1 analogues** requested by Julia («запусти аналоги текущего рисеча (опус)
   на кодекс (sol xhigh) и glm 5.3 max»), launched ~21:05 UTC:
   - R1-Sol: companion job `task-muokedaz-7zgmrz`, `gpt-6-sol`, effort `xhigh`,
     prompt `.tmp/r1-sol-prompt.md` (same questions as the Opus prompt, answer
     returned inline, read-only) → **done** 20:46 UTC, 16.5k chars, no
     network, saved as `archive/docs/specs/research-embedders-sol.md`. Repo facts it
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
     → save as `archive/docs/specs/research-embedders-glm.md`. Cross-check all three in
     plan §6/§7 (G2, H9) once Opus R1 lands. **Part A done** (end_turn, 239 s,
     11k chars): main `deepvk/USER-bge-m3` (drop-in, same dim/ctx, no prefixes),
     fallback `ai-forever/ru-en-RoSBERTa`, cheap probe `deepvk/USER2-base`; code
     adds no query/passage prefixes → e5-family needs a code patch; RAM est.
     bge-m3 2.5–2.9 GB RSS + reranker ≈ 5–5.5 GB of 8; main risk: dense-lane
     effect diluted by BM25+RRF+reranker, RU→EN share unmeasured. **Part B done**
     (end_turn, 355 s, 18.6k chars) → `archive/docs/specs/research-embedders-glm.md`
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
     report saved to `archive/docs/specs/research-benchmarks-sol.md`; factual fixes
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
     evidence. Report → `archive/docs/specs/research-benchmarks-glm.md`. Attempt 1
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
     `archive/docs/specs/research-benchmarks-glm.md` (header + A + B verbatim). Cross-check
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
`archive/docs/audits/astra_gaps_30_09_26.md` with provenance header; then Julia's
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

- `archive/docs/specs/plan_final_30_09_26.md`: header note; §1 track tables (1.3
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
- `archive/docs/operations/direct-glm-5.3.md`: recovery policy bullet (one narrowed
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
  `archive/docs/specs/research-embedders.md` (54k): main `ai-sage/Giga-Embeddings-
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
    `archive/docs/audits/audit_astra_final_30_09_26.md` with provenance header.
  - GLM 5.3 direct, effort `max`, window 64 000, single call with CLAUDE.md
    rules excerpt + full plan + full spec inlined (`.tmp/audit_build_glm_prompt.py`,
    127k chars) → `.tmp/glm-audit-final-001.txt` (+ `.meta.json`); on
    max_tokens/reset fall back to split A/B (builder supports it) → result →
    `archive/docs/audits/audit_glm_final_30_09_26.md`.
  - Findings will be applied by delegation (Julia's standing instruction),
    each with a note in §6; blockers first.

## Step 12 — GLM final-plan audit received and applied (30.09, late)

- GLM direct, `max`, single call worked: 398 s, 41.0k in / 38.6k out tokens,
  `end_turn`, 15.4k chars visible → saved with provenance as
  `archive/docs/audits/audit_glm_final_30_09_26.md`. Verdict «не готов»: 1 blocker
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
  with provenance as `archive/docs/audits/audit_astra_final_30_09_26.md` (Astra read
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
  fallback line, GLM runbook, `archive/docs/windows-test-workflow.md`. Not staged:
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
  `archive/docs/windows-test-workflow.md` already carried the `py -3.13` and «full
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

## Step 16 — T-56 closed: Astra reference measured (30.09, late)

- Writer `luna-high` (gpt-6-luna, Codex `cw`) via `writer --task T-56
  --detach`, 680 s, three files; the lead agent ran `ruff format` and reduced
  `rollout_file` to the file name in script and unit test. The executor
  substitution (GLM 5.3 direct → Codex `cw` after the two failures in Step 15)
  is disclosed in the commit message.
- Run from the main session: `py -3.13 scripts/p2_astra_reference.py` →
  10/10 graded, 0 missing, 0 reused, exit 0. Threads
  `01a0f4ae-ab23-7a23-99b0-99cb960b1243` … `01a0f4b5-0cd1-7341-9041-12a9ab242100`
  (rollout stamps 19:38:07–19:45:06, summary 2026-09-30T23:45:36 UTC);
  193,421 tokens, reasoning 112–509 per case, 37–55 s per request; every
  reply passed the rollout check (`gpt-6-astra`, `xhigh`, read-only sandbox,
  empty temp cwd). No cost reported (subscription route).
- Result: grades 2/18/18/12, 30/50 relevant, 9/10 cases with a 3; κ 0.8930
  Sonnet 5, 0.8824 GLM 5.3, 0.9727 Opus 5.5 (48/50 exact; both differences are
  one grade). Capsule `docs/evidence/p2-astra-reference-sample.md`,
  `EVIDENCE_INDEX.md` row, `CURRENT_STATE.md` P2 line; `STORE_SHA256` pinned
  `6411f772…5164`. Windows: ruff clean, 23 passed (Astra unit + artifact,
  Opus artifact). Slice rule (c): published κ with pool SHA, collector blob
  and companion arguments. Model reference only — 1.1 (D2) still waits on
  Julia's grades; T-57 stays parked.

## Step 17 — T-59: 2.1/2.2 route observability implemented (01.10)

- Owner's boundary for this stretch: «Остановись после завершения T-59» —
  T-59 goes through commit, attach and push; T-58/T-63/T-64 are not started.
- Base: the draft patch already in the tree (allowed by plan §5) plus
  `tests/test_graph_route_observability.py`; the gaps against the spec were
  split into one-file GLM 5.3 direct requests (`xhigh`, runbook
  `archive/docs/operations/direct-glm-5.3.md`, helper `.tmp/glm-direct.py`, prompts
  and results under `.tmp/glm-2.1/`): R1 `vectordb/_base_manager.py`
  (7,908 in / 19,105 out tokens), R2 `agent/graph.py` + `agent/state.py`
  (7,895 / 22,677), R3 `config/settings.py` + `vectordb/manager.py` +
  `resolution/evidence_view.py` (5,586 / 12,049), R4 `static/admin.js`
  (2,246 / 3,781), R5b `tests/test_ask_contract_route.py` (7,968 / 16,887),
  R5a unit tests (see below). R1–R5b ended `end_turn`; no Codex
  substitution this slice.
- R5a (11 unit groups, 57k-character prompt) ended `max_tokens` at 48,000
  output tokens with 13,620 characters of text (the window went to
  reasoning, as on T-56) — recoverable failure, `.partial.txt` not applied.
  One narrowed retry per the runbook, split by file: R5a-1
  `tests/test_route_trace_units.py` (U1–U6, U10; 6,387 / 18,235 tokens,
  `end_turn`, 15 passed after one I001 fix) and R5a-2
  `tests/test_route_trace_nodes.py` (U7–U9, U11). The R5a-2 request was
  stopped by the Claude Code harness for system memory pressure before the
  model produced anything (not a GLM failure); per the harness instruction
  it was not restarted, and the lead agent wrote that file (4 groups,
  11 tests) from the same brief — disclosed here and in the commit message.
- The contract module is `tests/test_ask_contract_route.py` (renamed from
  `…_route_contract.py`): the task's `verify_cmd` selects
  `-k "trace or evidence or ask_contract"`, which matches module names only
  as substrings.
- Lead-agent corrections on the GLM output: R1 one SEARCH block with slice
  spacing; R2 `import hashlib` moved to the stdlib block and
  `estimate_tokens` imported at module level; R3 a `_text_or_none` helper so
  `null` route fields survive the Evidence projection, and `view` annotated
  for mypy strict; R5b the parity flag set on the client fixture's settings
  object, and two route expectations corrected to what the graph does: with
  fact verification off the grounding gate is fail-closed (`human` at score
  90), and a single-document answer with `NONE` claims is a knowledge gap
  (`_is_knowledge_gap`: fewer than two graded docs or factuality below 50),
  so the fixture contract pins `human` and the reasons; no `auto` case.
- Design reading of the spec: the three strategy notions (configured,
  selected, effective) and the query fingerprint are a separate
  `retrieval_route` trace step logged before each `retrieve`, not new legacy
  state keys — the §5 e2e equality for `retrieval_paths` keeps its 4-key
  shape; the hybrid lane's path is lifted into `retrieval_paths` from the
  pending route; `view["retrieval_route"]` exists only when the step exists
  (old traces replay unchanged); `confidence` is always `null` (no calibrated
  classifier, G9); `generation_context_tokens` uses the provider estimator.
  `RAG_RERANK_BATCH` is validated at settings construction (unset or a
  positive integer), read once when the retriever is built, and reported on
  every path as `rerank_batch_effective`.
- Windows: ruff clean on the repo; mypy strict on the three kernel files;
  focused set 236 passed; slice tests 52 passed (contract 16, units 15,
  nodes 11, observability 10); docs gate 23 passed.
- Mac fast gate, attempt 1: RED on two counts. (1) `focused`:
  `tests/test_graph_error_handling.py` — a `MagicMock` retriever answers the
  new `get_relevant_documents_with_path` attribute, so the retrieve node
  unpacked a mock, fell into its error branch and went on with no documents.
  Fixed in `agent/graph.py` by `_relevant_documents_with_lane_path`: the lane
  API counts only when the call returns a real `(docs, path)` pair, anything
  else takes the legacy call; pinned by a node test (the file now holds 12).
  (2) `task:T-59`: the registered `verify_cmd` was a keyword sweep
  (`-k "trace or evidence or ask_contract"`) that also selected the
  Postgres-only integration fixtures (`DATABASE_URL` required, 4 errors);
  narrowed with `task-edit T-59 --verify-cmd` to the slice's eight test
  files (the note is on the task).
  Status docs: `CURRENT_STATE.md` (line 10 and the Q row, 150 lines),
  `ROADMAP.md` (two Q mentions), `EVIDENCE_INDEX.md` row after the Astra row.
- Mac fast gate, attempt 2: GREEN (tree `231b28f626`). MyFlow review pass 1:
  three verified findings, all applied by the lead agent in repair pass 1
  (disclosed in the commit message, each with a confirming test):
  F-T-59-1 (sev 8) — `TraceService.log_step` redacted the serialised JSON,
  so the card-number pattern ate the digits of a float rerank score
  (`0.8999999761581421`) and the step became unreadable; now the state is
  JSON-normalised first and only string leaves are redacted (node test +
  an HTTP contract case with a real reranker score). F-T-59-2 (sev 6) —
  the retriever factories took `rerank_batch` from the Settings singleton,
  so a runtime `RAG_RERANK_BATCH` change never reached a rebuilt retriever;
  both factories now read the variable at build time
  (`_effective_rerank_batch`, env validated, else the Settings value); the
  cached retriever keeps its batch until `reset_retriever_cache` (unit test
  covers cached / rebuilt / invalid / unset). F-T-59-3 (sev 6) — a
  successful `predict()` returning only NaN/Inf was reported as
  `fallback:reranker_error`; `_rerank_scored_with_status` now returns the
  reranker outcome beside the pairs and `_score_table` names the fallback
  only on the exception path, all-NaN is `partial` (two unit tests).
  Slice tests after the repair: contract 17, units 18, nodes 13,
  observability 10 (+ `tests/test_trace_service.py` 3,
  `tests/test_graph_error_handling.py`): 69 passed on Windows.
- Review pass 2 (Codex, first voice): F-T-59-1 and F-T-59-3 refuted as
  fixed; F-T-59-2 raised again (a process started with `RAG_RERANK_BATCH`
  set and then unset at runtime keeps the Settings snapshot on rebuild) →
  disputed → second voice (`review-run --second`, fallback directive: Fable
  subagent on the live tree `607e103434`): refuted, severity 2, confidence
  0.2 — spec row 2.2 asks for read-at-build and a runtime change applied
  after rebuild, both hold; the Settings fallback keeps programmatic
  overrides (`_apply_settings_overrides`); the residual is documented in
  the `_effective_rerank_batch` docstring. The subagent's JSON lacked the
  `confirms`/`verdict` fields, so the controller filed it as the advisory
  F-T-59-7; rejected with a note carrying the verdict (a canonical
  re-record is refused in COMMIT_PENDING). F-T-59-2 stays closed as
  refuted; no code change.
- Mac full gate, attempt 1: RED on three unit tests (3802 passed).
  (1) `tests/test_factcard_store.py::test_retrieve_node_factcard_uses_cards`
  monkeypatches `graph._select_retrieval_strategy`, which the retrieve node
  no longer called (it used `_select_retrieval_strategy_with_reason`).
  Fixed in `agent/graph.py`: the decision lives in
  `_select_retrieval_strategy` again (HEAD body), the reason is
  `_selection_reason(selected, configured)` — the exact inverse of the rule
  table — and `_with_reason` goes through the module-level selector, so a
  replaced selector stays the single source of truth; unit test added
  (units file now 19). (2)+(3) `tests/test_pgvector_spike_artifact.py` and
  `tests/test_pgvector_rerank_artifact.py` compared the recorded
  `source_sha256` of `vectordb/_base_manager.py` with the live tree; T-59
  is the first change to that file since the D.1 (`fa0146c`) and D.3
  (`1e64ee3`) measurements. Both tests now verify the digests against the
  blobs at the commit the artifact names (`git show <code_base>:<path>`,
  the pattern of the newer D.4/D.5 artifact tests; the D.1 spike scripts
  did not exist at its code_base and are verified at the publishing commit
  `06da9c6`); the artifacts are untouched, the two `EVIDENCE_INDEX.md`
  rows say which code they describe and that the numbers were not
  re-measured. Windows: the three tests + slice + docs gate, 99 passed.
  Path back per MyFlow rule 8: `repair --no-findings` → `done` →
  `review-run` → `gate --full`; the gate results are in the commit message
  and the MyFlow journal.

## Step 18 — Owner's word: executor sol, decisions delegated (01.10)

- Julia, 2026-10-01: «Продолжи доработку по плану от вчера. В качестве
  исполнителя используй sol (кодекс). Все решения на тебе. Комиты и пуши
  тоже на тебе. Не разворачивай на этой машине wsl, docker и подобное. Для
  этого используй мак. grok недоступен.»
- Writer for every slice: `sol-high` (gpt-6.1-sol, Codex `cw`) through
  `writer --use sol-high --no-fallback`. Each commit discloses this instead of
  GLM 5.3 direct. Heavy gates run on deproject-mac (`.tmp/mf-mac/`).
- `limits.writer_timeout_sec` was raised from 3600 to 5400: the T-63 writer,
  attempt 1, was killed at 3600 s.

## Step 19 — T-58: development ruler in code, P2 baseline (01.10, b448ee4)

- `evaluation/semantic_ruler.py` implements the pre-registered development
  ruler, including fact matcher `claim-window-v3`. Any negation cue or window
  disagreement in it goes to blind judgment.
- Published P2 development baseline (`provisional_ruler`):
  - H: P@5 = sent_precision 0.6080 [0.5443, 0.6698], nDCG 0.9659;
  - Hm: 0.8400 [0.75, 1.00].
- Review: 3 passes. Pass 2 had F-T-58-1 confirmed incomplete; it was
  reproduced and repaired. Mac full gate GREEN on tree `11185d6ace`.
- Known matcher quirk, to hand to the owner: Russian «не более» / «не
  менее» contain the negation cue «не». Every such numeric fact therefore
  goes to blind judgment, never to a silent pass or fail. Candidate
  follow-up: a v4 matcher with compound polarity markers. It is not
  registered yet; a changed matcher recomputes every published
  `fact_coverage`.

## Step 20 — T-63: preliminary evidence-loss map, ledger entry 1 (01.10, c9d3b8c)

- 100 historical H cases, 200 required-term occurrences. The proxy is
  agent-authored `answer_contains` terms, not gold.
- Loss by lane:
  - hybrid: 0 index losses; 4 cases first lose a term after caps, 9 more
    between the pool and the sent context;
  - graph: 4 / 10;
  - section expansion: 0 lost terms.
- No index-stage loss, so no ingestion fix is due before the 2.5 baseline.
  `evaluation/dev_ledger.jsonl` starts with entry 1.
- Incident: the writer killed at the 3600 s timeout left its Codex companion
  job `running` (the pid was gone). Every later resume in the workspace
  failed «Task … is still running». During T-64, a sol capacity blip then fell
  back to luna-high, which made no changes.
  - Julia allowed the cleanup: «убей зомби задачу».
  - `.tmp/notes/clear_stale_companion_job.py` marked the job cancelled; backups
    are `*.json.bak-stale-fix`.
  - From then on, writers run with `--no-fallback --fresh`.

## Step 21 — T-64: dev-set pilot drafts, family register (01.10, 93b2c42)

- `evaluation/devset_pilot.jsonl` holds 30 agent_labelled drafts, 0 approved;
  rule (b) counts only after the 1.3b approval.
  - Quotas 10/10/4/6, styles 15/15 (gpt-6.1-sol), 10 adversarial, every
    trap type, derived RU→EN flag on 10, 38 spans.
  - Seed 6413030 over a specificity-filtered frame of 982 sections. The
    first, unfiltered draw (4007 sections) was discarded: 16 of 24 answerable
    cases rested on template text.
- Fact form `pilot-claim-quote-v2`, decided by the orchestrator in repair 1
  after the writer refuted F-T-64-4:
  - the claim (`text`) is atomic answer wording, grounded in its quote (or a
    generic governing cue plus a quote substring);
  - `source_quote` is a contiguous excerpt of the case's own span and carries
    the specificity clause (≤ 3 documents);
  - every case has a minimal `reference_answer` that must cover its claims;
  - computed totals are `derived: true`.
  - Why: the text matcher ignores polarity, so whole-list facts had made a
    correct paraphrase score 0, and a department name cannot pass a
    specificity rule meant for evidence.
- Families (`evaluation/document_families.json`, draft): topic-only primary
  map, 84 families with 57 singletons; the cross_ref closure and the folder
  grouping are sensitivity views. Footprint 49 families; reserve 35 families /
  36 documents.
- **D3 for Julia:** under any cross_ref-aware rule, an independent holdout is
  not feasible on this corpus.
  - 105 direct dev↔reserve links; 25 of 35 reserve families are linked,
    which leaves 10 HR families.
  - Taken literally, G22 (folder ∪ topic ∪ cross_ref) makes the whole corpus
    one family.
  - Options: add independent sources, or accept topic-level independence
    with the stated leakage.
  - F-T-64-1 is accepted as a risk by delegation until she decides.
- Review (codex astra): pass 1 had 4 findings; pass 2 confirmed three fixed
  and found F-T-64-9 (numeric claim grounding), which was repaired; passes 3
  and 4 were clean.
- Full gate attempt 1 was RED: the read-only T-58 artifact test pins the P2
  capsule phrase «provisional, replaced by the 1.3a family register», which
  sol had reworded. The lead agent restored it in a no-findings repair. Mac
  full gate GREEN on `ca6dc8bbaf`: unit 3977 / e2e 36 / task 77.

## Step 22 — Stop point (01.10): T-61 writer output on disk, not gated

- Julia: «поставь точку, где логично». The T-61 writer
  (`writer-T-61-1001-155023`, sol-high) had just started. It was not cancelled,
  because `job cancel` kills the process tree but leaves the Codex companion
  job `running`, which is the stale-job hazard of Step 20. It ran to the end
  (4213 s, exit 0, summary `.myflow/writer/T-61-1.txt`); no gate or review was
  run.
- The uncommitted T-61 change in the tree:
  - new `vectordb/embedder_manifest.py`, `tests/test_embedder_manifest.py` and
    `tests/test_ask_embedder_manifest.py`;
  - edits to `config/settings.py`, `vectordb/{_base_manager,manager,index_staging}.py`,
    `api/app.py`, `api/routers/admin_kb.py`, `agent/graph.py`,
    `resolution/evidence_view.py`, `docs/operations/backup-restore.md`,
    `CURRENT_STATE.md` and `EVIDENCE_INDEX.md`.
- The writer's own checks are not evidence: 51 passed on the slice and
  neighbour tests, 23 on the docs gate, with `py -3.13` and
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. Before `done`, check its doc edits for
  run-log residue.
- Resume:
  1. `$MF continue`, then check the writer summary (`.myflow/writer/T-61-1.txt`).
  2. Verify locally with the focused tests and ruff.
  3. Run `$MF done T-61 --detach`, then `review-run --detach`, repairs and
     `gate --full --detach`.
  4. Make a scoped commit and push.
  - The T-61 `verify_cmd` now excludes `tests/integration`.
- Then:
  - T-62 (note `.tmp/notes/T-62-note.md`);
  - T-60 (note `.tmp/notes/T-60-note.md`, written this session: a v2 request
    on 1–10 addressed documents, strict parsers, `invalid`/`absent` outcomes,
    truncation accounting; GR3 'Score: 1.0' stays invalid);
  - T-65 (2.5 baseline on the Mac, needs T-61 + T-62).
  - T-57 stays parked (Julia's D2 grades).
- Saved off the laptop at Julia's request («то, что нужно сохранить -
  сохрани, пометь в доке»): branch `wip/T-61-writer` on origin, commit
  `e0f54c0` on top of `e722364`. It is a backup, not a slice commit: never
  merge, rebase onto or check out the branch.
  - Contents: 50 files, each checked blob-for-blob against the tree; the
    restore command below was tested into a scratch directory.
    - the T-61 writer output (11 edits and 3 new files);
    - all of `.tmp/notes/`: the notes for T-60, T-61 and T-62, the
      T-58/T-63/T-64 notes and the helper scripts, including
      `clear_stale_companion_job.py`;
    - the MyFlow files that resume the slice: `.myflow/state.json`,
      `tasks.json`, `config.json`, `spec.md`, `checkpoint.md`,
      `journal.jsonl`, `writer_run.json` and `.myflow/writer/T-61*`.
  - The originals stay in place on this machine (`.tmp/` and `.myflow/` are
    git-ignored). Do not stash, check out, reset or clean the tree before
    `done T-61`.
  - Restore only if the tree is lost. The command writes the working tree
    and leaves the index alone; drop the `.myflow/` paths unless `.myflow/`
    itself is gone:

    ```sh
    git diff --name-only wip/T-61-writer~1 wip/T-61-writer |
      xargs git restore --source=wip/T-61-writer --worktree --
    ```

  - Delete the branch, locally and on origin, once T-61 lands on master.
- `done T-61` will warn «HEAD moved during this slice (93b2c42 -> …)». The
  slice started on `93b2c42`, and the only commits since are the lead
  agent's handoff commits. It is a warning, not a block: the scope check
  reads the working tree against HEAD.

## Step 23 — T-61 repair pass 1 done, fast gate GREEN; stop point before review pass 2 (02.10)

- Julia, 2026-10-02: the same terms as Step 18 (sol executor, all decisions,
  commits and pushes delegated, Mac for heavy runs, grok unavailable). Then:
  «поставь точку, где логично».
- After Step 22, still on 01.10:
  - `done T-61` gave fast GREEN.
  - Review pass 1 (codex astra) raised four actionable findings:
    - F-T-61-1: an attribute set on a pydantic `VectorStoreRetriever`;
    - F-T-61-2: the legacy build stamps a collection that already holds
      records;
    - F-T-61-3: KB publish writes without a manifest check;
    - F-T-61-4: an unresolved revision counts as proven identity.
  - Repair decisions: `.tmp/notes/T-61-repair-1-note.md`.
  - The repair writer lost the network at 18:29 local and died at 18:42,
    after landing F-1, F-4 and part of F-2/F-3. Its companion job
    `task-muq2ztgf-6eg5xa` stayed `running` with pid 7420 gone, the Step 20
    hazard. On 02.10 it was cleared under the blanket delegation:
    `.tmp/notes/clear_stale_companion_job_t61.py`, backups
    `*.json.bak-stale-fix-t61`.
- Repair pass 1 on 02.10, sol-high (gpt-6.1-sol, effort medium per the
  v2.4.16 role policy), three runs:
  1. Resume with `.tmp/notes/T-61-repair-1-resume-note.md`.
     - Cause: the staged build had the literal
       `collection_configuration={"hnsw": {"sync_threshold": 1}}` twice. The
       mutation tests in the read-only
       `tests/test_chroma_restart_stability_source_pin.py` rewrite the first
       occurrence, so 3 of them failed.
     - Fix: the creation call takes the module constant `_PERSIST_EVERY_ADD`,
       and the pinned `from_documents` call stays byte-identical to HEAD.
     - A new guard test checks the creation call, on a fake and on real
       chromadb.
     - A creation failure keeps the staging error contract.
     - A mismatch on a pre-existing collection raises unwrapped and deletes
       nothing.
  2. Fixes from a pre-`done` Mac unit run (`.tmp/notes/T-61-repair-1-fix2-note.md`).
     That run found three problems the fast gate would not have seen:
     - `build_factcard_store` had lost delete-then-rebuild.
       - My repair decision had wrongly listed it under "check before write".
       - It broke the existing `test_factcard_store` and
         `test_tenant_index_lock`.
       - Restored: delete, then create stamped, then write.
     - T-59's `test_route_trace_nodes` pins the retrieve node's steps. It now
       expects `index_manifest` first (plan 2.3). This is the only edit to an
       existing test in the slice; the commit must name it.
     - The new real-chromadb tests leaked 220 file descriptors.
       - The Mac ssh shell runs with `ulimit -n 256`, so the suite cascaded
         into 55 failed and 139 errors (EMFILE) in unrelated files.
       - Fixed: stop the Chroma systems after each test. Descriptors per file
         went 4 → 6 → 8.
       - Mac unit under the gate limit afterwards: 4038 passed, 0 failed.
  3. `done` attempt 1 was RED on `mypy-api-fast` (`manifest.backend` on
     `Any | None`). The writer switched to `configured["backend"]`.
     Attempt 2: GATE GREEN (fast) on tree `c3b53a1674`; focused 177 passed,
     task 159 passed.
- Contour defect recorded (`defect --area gate`): the fast gate's focus
  misses existing tests of modified production modules.
- Stop point: phase REVIEWING; review pass 2 is not started. The tree holds
  the whole T-61 change, uncommitted.
- Backup:
  - `wip/T-61-writer` was force-updated (with lease) to `5fd53e5`, parent
    `d99f1c7`. It replaces `e0f54c0`.
  - 74 files, each checked against the tree through git's own filters.
    The restore into a scratch tree gave 0 content differences.
  - Contents: the T-61 change, all of `.tmp/notes/`, `.tmp/mf-mac/*.py` and
    `steps.json`, and the MyFlow resume files plus `review_run.json`,
    `writer/T-61*` and `reviews/T-61*`.
  - The restore command and the rules of Step 22 are unchanged.
- Resume:
  1. `$MF continue`; the phase should be REVIEWING with the fast gate GREEN.
  2. `done` printed an advisory SPEC DRIFT, and there is no capability spec
     for the manifest. Decision:
     - write `docs/specs/embedder-manifest.md` (`$MF specs new
       embedder-manifest`) from plan §2.3, G25 and the repair-1 decisions,
       not from the code;
     - its scenarios: match/eligible; mismatch → 503 with trace; unstamped
       → NOT_EVIDENCE; unverified revision → NOT_EVIDENCE; stamp only on an
       empty collection; publish into a mismatched index → 409; fact cards
       rebuild with a fresh stamp;
     - add it to T-61 `spec_refs` (`task-edit`), then run `done T-61
       --detach` again.
  3. `$MF review-run T-61 --detach`. Pass 2 judges F-T-61-1..4 first.
  4. Repairs if needed. Before `done`, run a Mac unit pass
     (`sync.py` + `remote.py --site pytest tests/ …`), because of the
     focus gap.
  5. `gate --full --detach`.
  6. Scoped commit of the 16 slice paths, not `demo/phase-e-raw.webm`. The
     message discloses sol-high, the test edit and the lead agent's notes.
  7. Push. Delete `wip/T-61-writer` locally and on origin.
  8. Then T-62, T-60 and T-65 as in Step 22.

# Cold read: stage 7, step 1, the retrieval arms at M3: spec, tool, test and S's fix before registration

Frozen copy read: `D:/RAG_new/.tmp/coldread-s7/`, matching its `MANIFEST.sha256`:

- `stage7-step1-arms-m3.md` `e7e028f16fb3731342d0d2b1be8f6e1f54b6981ce58bddd7003531055da1a457`
- `arms_replay.py` `44bf47fea287d752b38ba3297edcc25ea859ce173502b3bdba585a3872a3ac95`
- `test_stage7_arms_replay.py` `cfe43f1cc59757179368eb0f9d14803e6a94e708d16b9ee7c6c2d47115643ed4`
- `s_fix.diff` `016992f15f41289f58891b55208162278991b32bbf77e7bf8b19068b2b1493d6`

This was a static reading. Neither the tool nor the test was executed. The only commands run were read-only: grep, awk, sha256sum, git diff, and one-line Python reads of the export's JSON. `spec:N`, `tool:N`, `test:N` and `diff:N` are line numbers in the frozen copies (`tool` is `arms_replay.py`, `diff` is `s_fix.diff`). Other files are cited as path:line in the live tree. P1b's counts below come from the export's `ranked_scores` in `reports/stage2/retrieval-20261021/`.

Findings: 1 blocking, 4 should fix, 10 minor.

## Findings

### 1. Blocking: G1 lets an arm qualify on one deciding base even when M3 on the two deciding bases together is flat or falls

- **Where:**
  - spec:28–29, spec:110–113
  - tool:40–44, tool:918–928, tool:938–946
  - PLAN.md:748–750, PLAN.md:754–755
  - test:586–627
- **What is wrong:**
  - `candidates` (tool:925–928) admits an open arm with a detected gain at any one of ConditionalQA, WixQA or `pooled_deciding`.
  - The pooled reading can only stop an arm, on a detected loss, or rank two qualifiers (tool:941–945). Nothing requires it to rise.
  - Example, on bases of 100:
    - WixQA b 0, c 6: p = 0.031, a gain.
    - ConditionalQA b 10, c 3: p = 0.092, no detected difference.
    - `pooled_deciding` b 10, c 9: p = 1.0.
    - `standing` is "open", `gained` is `["wixqa"]`, and the decision is "<arm> opens answers". Yet the arm's M3 on the two deciding bases together fell by one question.
  - PLAN's step 2 opens answers «только если М3 выросла». Step 4 switches an arm on only if the final metric rose on aircargo, ConditionalQA and WixQA «вместе». An arm admitted this way is likely to fail step 4 after ≈ 28 h of answers (PLAN.md:749).
- **Why it matters for the decision:**
  - P's mechanism makes this pattern plausible rather than contrived. Cutting the five can let WixQA's single gold article through the window while it costs ConditionalQA's all-evidence coverage. Under V3, P changes 39 ConditionalQA questions and 11 WixQA ones (spec:120–122).
  - The family of comparisons is unstated. There are two arms and three stop readings, and any one gain qualifies. Under no effect each one-sided false gain is ≤ 0.025. The chance of at least one false qualification therefore lies between 0.025 and the Bonferroni bound 0.15.
  - The K curve skipped a correction because there a false result was only a false *loss* (docs/specs/k-curve-expanded.md:98–99). Here the costly error is a false *gain*, so that reason does not carry over.
- **Suggested change:**
  - Qualify an arm only on a detected gain at `pooled_deciding`, the deciding bases «вместе», and keep every stop reading as a loss stop. At the least, require c − b > 0 at `pooled_deciding` beside a per-base gain.
  - State in spec:110–113 which readings qualify and the family they form.
  - Add a G1 test with a per-base gain beside a flat or negative pool.
  - The pins at test:925 and test:927 and the docstrings at tool:40–44 and tool:932–935 change with this.

### 2. Should fix: the spec gives the MDE two meanings, and a detected gain can sit below its own MDE

- **Where:**
  - spec:27–29, spec:181
  - PLAN.md:197–199 (§4.4)
  - docs/specs/k-curve-expanded.md:99–100
  - test:925
- **What is wrong:**
  - spec:28–29 reads «М3 выросла больше MDE» as a detected M3 gain, p < 0.05.
  - spec:181 puts the MDE at 2.8·√(d/n): the K curve's effect, detected with 80 % power.
  - A 6–0 gain on a base of 100 is detected (p = 0.031). It is 0.06, below 2.8·√(0.06/100) = 0.069.
  - In counts, the spec's own MDE is c − b ≥ 2.8·√(b + c). The gate asks only for p < 0.05, about 1.96 standard errors.
- **Why it matters for the decision:**
  - The rewrite (spec:9–13) exists to stop opening answers whose paired reading (MDE 0.17–0.30) would read «not detected». A just-detected M3 gain of 0.06–0.10 leaves most of that risk in place.
  - Between 1.96 and 2.8 standard errors, the two readings of the same registered sentence decide differently.
- **Suggested change:** choose one reading and write it in both places. Either:
  - add the margin: c − b ≥ 2.8·√(b + c) at the qualifying reading; or
  - keep detection and reword spec:181, so that 2.8·√(d/n) is named as the effect detected four times in five and not as the MDE that G1 reads.
  - test:925 pins the gate's sentence.

### 3. Should fix: the test pins the draft status and the unfilled SHA list, so registering the spec or filling it in fails its own gate

- **Where:**
  - test:924, test:931
  - spec:3, spec:170–171
  - tool:3
- **What is wrong:**
  - test:924 asserts "**a draft, not registered**". test:931 asserts "SHA list of the run: to be filled in when the spec is registered".
  - Registration rewrites spec:3. The precedent pins "registered before the first request" (docs/specs/stage4-step5a-live.md:3, tests/test_stage4_step5a_live_tools.py:910).
  - Filling in the SHA list removes the other pinned phrase.
  - spec:170–171 also asks for the record's and the plan's SHA "when the spec is registered", though neither exists before the run.
  - tool:3 still calls the spec "a draft, not registered".
- **Why it matters for the decision:** either edit fails tests/test_stage7_arms_replay.py in the Mac gate before the run (spec:130). The only alternatives are a test change in the registration commit or an edit of the registered test after registration, which changes its SHA.
- **Suggested change:**
  - In the registration commit, pin the registered status and a sentence that survives the fill-in, for example "SHA list of the run:".
  - Say that the record's and the plan's SHAs are written in with the evidence commit.
  - Update tool:3.

### 4. Should fix: s_fix.diff leaves out the changes that keep GR-1b's published replays on the old expansion

- **Where:**
  - diff:1–222 (two files only)
  - spec:45–51, spec:130
  - Live tree:
    - scripts/gr1b_stage_replay.py:30–70, :108, :113
    - scripts/gr1b_seed_expansion.py:24, :70
    - tests/test_gr1b_stage_replay.py:43–48
    - scripts/ab_remote_contextual.py:482
- **What is wrong:**
  - The working tree's fix also changes three files outside the diff:
    - scripts/gr1b_stage_replay.py gains `legacy_expand_graph_sections`, the pre-stage-7 algorithm, and uses it.
    - scripts/gr1b_seed_expansion.py uses it too.
    - tests/test_gr1b_stage_replay.py points its refusal test at it.
  - None of this is in s_fix.diff or in spec:45–51.
  - With the frozen fix alone, `test_published_stage_replay_reproduces_all_cases_and_inputs` runs `build_stage_report` through the new `_expand_graph_sections` and stops at "exact structural replay differs". That test is in the spec's own Mac gate (spec:130).
  - scripts/ab_remote_contextual.py:482 still calls `_expand_graph_sections`. That harness now expands by the new rule, and the spec does not say so.
- **Why it matters for the decision:**
  - The record's hashes vouch for the registration commit. A fix registered as frozen fails its own gate.
  - The spec does not tell a reader that GR-1b's archived numbers rest on a copy of the old code.
- **Suggested change:**
  - Put the three files in the registration commit and in the frozen diff.
  - Add one sentence to spec:45–51 naming `scripts.gr1b_stage_replay.legacy_expand_graph_sections` and the ab_remote_contextual change.

### 5. Should fix: the control is not checked against the checkout, and an INT8 amendment needs more than a re-run

- **Where:**
  - spec:13–17, spec:150–152, spec:186
  - tool:187–203, tool:363, tool:375, tool:595–603, tool:618
  - PLAN.md:745–747
  - config/settings.py:374–375, :491–502, :528–529
  - docs/evidence/stage4-step5a-record.md:22–23, :35, :52
- **What is wrong:**
  - spec:13–17 and PLAN.md:745–747 make the control the path stage 4 accepts.
  - The tool holds three things to its constants: the stage-2 run's settings (tool:595–603), the export's window (tool:618), and the input limit of a fixed `SimpleNamespace(context_window=4096)` (tool:363, tool:375).
  - It reads none of the checkout's defaults: `retrieval_top_k`, `ollama_context_window`, `reranker_runtime`.
  - The Stops (spec:150–152) name only the run's settings and the V4 prompt.
  - "Runs again, in minutes" (spec:16) needs a new score source:
    - `Recorded` (tool:187–203) replays stage 2's PyTorch scores and refuses any other pool.
    - INT8's scores were taken on stage 2's 400 only (stage4-step5a-record.md:22–23, :35, :52). That leaves out aircargo-gr's 15.
  - spec:186 names K and the input budget but not the reranker's runtime, which spec:15–16 names.
- **Why it matters for the decision:**
  - The order of work puts the stage-4 package question before this replay.
  - If the package is accepted first, the replay still runs on PyTorch's fives. It writes a G1 decision against a control the product no longer uses.
  - record.json carries nothing that marks this. config/settings.py's SHA in `measure_code_sha256` is the only trace.
- **Suggested change:**
  - Stop when the checkout's `retrieval_top_k` is not 20, `ollama_context_window` is not 4,096 or `reranker_runtime` is not `torch`. Write the three into record.json.
  - Say in spec:15–17 that an INT8 amendment brings INT8's scores for all 415, with aircargo-gr's 15 scored anew.
  - Add the runtime to spec:186.

### 6. Minor: "at most 262" is not a bound

- **Where:** spec:120–122, spec:144–146; tool:333–340; test:471–473.
- **What is wrong:**
  - 17 is P's count of changed sent documents under V3. The plan reads V4 prompts, whose fit differs (spec:24–25).
  - P's prompt also changes, with the same sent set, when a dropped seed's chunk joins a kept seed's expansion (test:471–473).
  - P differs from H wherever P1b keeps fewer than five. On aircargo that is 23 questions of p2-aircargo and none of aircargo-gr.
  - The bound is 115 + 115 + 23 + 15 = 268 requests: $25.2 at $0.094, $56.3 at $0.21, and 2.7–9.7 h at 36–130 s.
- **Why it matters for the decision:** cost only. The registered "at most" can be exceeded by a correct run.
- **Suggested change:** give 268 and its costs as the bound, with 17 as V3's estimate.

### 7. Minor: the planned arm is described without "every stop reading is evidence"

- **Where:** spec:102–103, spec:142–143; tool:41; tool:925–928.
- **What is wrong:**
  - The spec and the docstring plan the judge for an arm with "a detected external gain and no detected loss".
  - `candidates` also requires the standing "open". An arm with a gain whose other deciding base is `NOT_EVIDENCE` is therefore not planned.
- **Why it matters for the decision:** none for the outcome, since such an arm cannot qualify, so the code is the right economy. The text says otherwise.
- **Suggested change:** add "and no `NOT_EVIDENCE` stop reading" in all three places.

### 8. Minor: aircargo's stop readings are not named in the spec

- **Where:** spec:96–97, spec:105–106, spec:110–112; tool:1291–1300.
- **What is wrong:**
  - The spec's list of stop readings (spec:96–97) covers the external bases only.
  - `judged` adds `aircargo_full` and `aircargo_full_or_partial` as stop readings of each planned arm, both runs pooled, with the per-run readings beside.
  - spec:105–106 says "both runs pooled, each beside". It does not say that both levels stop an arm, for example a loss at «full or partial».
- **Why it matters for the decision:** a reader of the registered text cannot tell which aircargo reading stops an arm.
- **Suggested change:** add one sentence after spec:106: "The two pooled readings, «full» and «full or partial», are stop readings of the arm; each run's reading stands beside."

### 9. Minor: a defect of S stops the whole replay, P with it

- **Where:** tool:806–816; spec:113–114, spec:153–154.
- **What is wrong:**
  - S that does not read H's pool, or keeps a seed outside H's five, raises `SystemExit` mid-run. Nothing is written and P is never read.
  - spec:113–114 says an arm left `NOT_EVIDENCE` does not hold back one that qualifies.
  - spec:153–154 says "stop, `NOT_EVIDENCE`" without saying whose.
- **Why it matters for the decision:** a qualifying P would go unread because of S. The text promises the opposite.
- **Suggested change:** either:
  - say in spec:153–154 that the replay stops and neither arm is read, because this is a product defect; or
  - mark S `NOT_EVIDENCE` on that base and read P.

### 10. Minor: S without an aircargo graph crashes a replay that planned S

- **Where:** tool:282–295, tool:802–803, tool:1018, tool:1287; spec:98–99.
- **What is wrong:**
  - When `structural_projection` fails on aircargo, every aircargo row has S = None.
  - If S was planned on the external bases, `judge_runs` raises `TypeError` on `r["S"]["prompt"]` (tool:1018) and nothing is written. `judged` would fail the same way at tool:1287.
  - spec:98–99 covers only the external bases.
  - `build_graph` guards `structural_projection` but not `self.retriever(projection)` (tool:289). A failure there also ends in a traceback rather than in "S not read on the base".
- **Why it matters for the decision:** the outcome is unreadable rather than `NOT_EVIDENCE`.
- **Suggested change:**
  - Treat S without an aircargo graph as S's aircargo readings `NOT_EVIDENCE`: skip it in `judge_runs` and `judged`, and say so at spec:98–99.
  - Move tool:289 inside the `try`.

### 11. Minor: "on the 300" is not checked

- **Where:** spec:84–85; tool:555–559, tool:723–731, tool:1131–1141.
- **What is wrong:**
  - The V4 comparison runs only for the case ids found in V4's rows.
  - Nothing requires V4's 100 ids per label to be among the records, or the gate's `v4_saved` to be 300.
- **Why it matters for the decision:** a mismatch of ids would pass the V4 half of the gate vacuously. Today's ids match.
- **Suggested change:** stop unless every V4 row's case id belongs to a record and `v4_saved` is 300.

### 12. Minor: a `NOT_EVIDENCE` decision has no stated next step

- **Where:** spec:114–115; tool:949, tool:1298–1300.
- **What is wrong:**
  - The replay is deterministic. A `NOT_EVIDENCE` from more than five unread questions or from a missing graph repeats on a re-run, and so does one from a failed stability after `judged`.
  - The spec does not say what follows: stage 7 closing with «H stays», a wait for an amendment, or a new judging run.
- **Why it matters for the decision:** this is the one outcome of G1 that leaves the stage with no next action.
- **Suggested change:** add one sentence saying what `NOT_EVIDENCE` leads to at the replay and after `judged`.

### 13. Minor: the measured code omits vectordb/manager.py, whose factory S copies

- **Where:** tool:126–148, tool:219–238; spec:41–43.
- **What is wrong:**
  - S's graph is built "as `vectordb.manager.get_retriever` does" by a copy (tool:219–238, mirroring vectordb/manager.py:1040–1062).
  - record.json's `measure_code_sha256` does not hash vectordb/manager.py.
- **Why it matters for the decision:** provenance only. A later change of the factory cannot be told from the record.
- **Suggested change:** add vectordb/manager.py to `MEASURE_CODE`. test:958–959 then covers it.

### 14. Minor: the frozen plan refuses an amended re-run, and a refusal after the plan leaves no record

- **Where:**
  - tool:988–1002, tool:1034–1035, tool:1105–1112, tool:1155–1160 against tool:1196–1198
  - spec:16–17, spec:103–104, spec:155
- **What is wrong:**
  - Each planned run's launch.json carries `code_sha`, the git HEAD (tool:1106).
  - `put_tree` refuses a PRIVATE tree with other bytes (tool:996–997).
  - A replay after a registered amendment (spec:16–17) runs at another HEAD. With the default PRIVATE it therefore stops at the plan, before record.json.
  - The plan is also written before `without_text` checks the record (tool:1196). A refusal there leaves a plan without a record.
- **Why it matters for the decision:** the re-run that spec:16–17 promises "in minutes" stops with "holds another plan's files" unless someone knows to change `--private`.
- **Suggested change:**
  - Write in spec:16–17 and spec:103–104 that an amended replay takes a new PRIVATE, and what becomes of the old plan. Alternatively, keep HEAD out of launch.json.
  - Build the plan in staging and write it under PRIVATE only after the record's checks pass.

### 15. Minor: G1's tests use states the flow never reaches and leave the real ones out

- **Where:** test:579–583, test:596–599, test:601–618, test:630–648, test:756–763.
- **What is wrong:**
  - `stops_of` gives both arms all five readings, aircargo's included. `judged` adds aircargo's readings only to planned arms.
  - test:596–599 has P open answers on an aircargo-only gain. Neither the flow nor the data can produce that:
    - The flow plans an arm only after an external gain.
    - Six of the seven contexts without the full answer are aircargo-gr's, and there P is H.
  - These cases are not tested:
    - `judged` with one arm planned and the other carrying no aircargo readings;
    - a `NOT_EVIDENCE` decision written at the replay;
    - both arms `NOT_EVIDENCE`;
    - a per-base gain beside a flat pool (finding 1).
  - The end-to-end tests patch `candidates` (test:756–763), so the real path from a gain to a plan to `judged` never runs end to end.
- **Why it matters for the decision:** the gate's edges as the run will meet them are unpinned.
- **Suggested change:**
  - Build G1 states with external keys only for unplanned arms.
  - Replace test:596–599 with an aircargo loss stopping a planned arm.
  - Add the missing cases.
  - Give one end-to-end case a fixture in which an arm truly gains, instead of patching `candidates`.

## Checked and found consistent

- **Frozen copies:**
  - The four SHA-256 values match MANIFEST.sha256, and the live spec, tool and test equal them.
  - s_fix.diff equals `git diff -- vectordb/_base_manager.py tests/test_graph_retriever.py`.
- **McNemar's orientation and readings:**
  - b counts questions with gold under H only and c those with gold under the arm only (`RENAMED`, tool:117).
  - A loss is b > c and a gain is c > b, each at p < 0.05, as in reports/no-rerank/tools/no_rerank_point.py:78–92 and spec:94–96.
- **Stop and advisory sets:**
  - ConditionalQA, WixQA and `pooled_deciding` stop an arm (tool:900–904). MultiHop-RAG and `all_three` are printed only.
  - More than five unread questions, or S without a graph, make the base and each pool holding it `NOT_EVIDENCE` (tool:872–897), as spec:96–99 says.
- **`standing`, `gained`, `candidates` and `decision` follow spec:110–115 as written:**
  - A loss is checked first, then `NOT_EVIDENCE`, then the standing "open".
  - The margin's keys exist for every open arm.
  - P wins a tie (tool:945).
  - An unread arm does not hold back a qualifier.
- **The decision's timing:**
  - The replay writes the decision exactly when no arm is planned, and "pending the aircargo context judge" otherwise (tool:1194).
  - `judged` refuses a record without a plan (tool:1252–1253) and a plan of other bytes (tool:1255–1256).
  - It adds aircargo's stop readings only to planned arms (tool:1292–1300).
- **`judge_runs`:**
  - It plans H's 115 prompts, then each planned arm's prompts that differ from every prompt already planned for the question (tool:1005–1022).
  - `judged` finds each level by prompt hash, so a deduplicated prompt takes the verdict of its identical twin.
- **The judge plan:**
  - It uses `context_judge.build_plan`'s item ids and 15 retests chosen by digest. Empty contexts are graded none without a request.
  - Stability is stage 2's `judge_export.stability`: 12 pairs, and κ ≥ 0.6 or the agreement rule with none two steps apart, as spec:106–107 says.
  - More than five missing levels make that arm's aircargo readings `NOT_EVIDENCE` (tool:1295–1300).
- **Cost arithmetic:**
  - 115 + 115 + 17 + 15 = 262.
  - $24.6 at $0.094 ($12.164 / 130) and $55.0 at $0.21.
  - 2.6–9.5 h at 36–130 s.
- **aircargo's ceiling:**
  - Stage 2's context judge gives 108 full and 114 with an answer of 115: p2-aircargo 99 full and 1 partial; aircargo-gr 9 full, 5 partial and 1 none.
  - So 7 contexts are not full and 1 is none (spec:31–34, spec:179–180).
  - p(0, 6) = 0.031, p(1, 7) = 0.070 and p(0, 7) = 0.016, so spec:122–123's smallest detectable loss holds.
- **P at aircargo «full»:** by V3's verdicts P cannot reach a detected gain there. Six of the seven are aircargo-gr's, where P1b keeps five on all 15 and P is H (tool:336–337). At «full or partial» P can only be stopped.
- **P1b's counts from the export's `ranked_scores`:**
  - All 415 rows hold five scores in [0, 1] with `rerank_status` ok.
  - Fewer than five are kept on 23 p2-aircargo, 0 aircargo-gr, 40 ConditionalQA, 11 WixQA and 15 MultiHop-RAG questions.
  - Each count is at or above spec:120–122's sent-document counts of 17, 0, 39, 11 and 13.
- **s_fix.diff leaves H's path alone:**
  - It changes `_expand_graph_sections`, and fills `_graph_chunk_positions` only where the graph projection is set up.
  - `get_relevant_documents_with_path` is untouched, and the graph lane is off by default (vectordb/manager.py:1040).
- **s_fix.diff does what spec:45–50 says:**
  - One header comes first, and each seam's overlap appears once, through `parent_join`.
  - A side ends at another section's chunk, at a chunk already in the context, at an empty chunk, or at the budget.
  - Adjacency follows the retriever's chunk order, which the product restores by `chunk_index` (vectordb/manager.py:864–865).
  - Three new tests pin this.
- **S's check:** it matches the graph path's dictionary (H's candidates plus entity 0, `rerank_status` ok), and S's seeds must be a subset of H's five (tool:806–816).
- **The parity gate implements spec:80–86:**
  - The stand-ins are asked once each.
  - It checks `PATH_KEYS`, the five, the scores and the expansion.
  - It checks V3's prompt text, its hash and the export's hash, and V3's sent documents.
  - The points are recounted.
  - V4's saved prompts are compared byte for byte, with CR refused (tool:563–573).
  - A break writes `parity.jsonl` alone and exits 3 (tool:1143–1147).
- **The control text:**
  - spec:14–17, spec:57 and spec:150–152 agree with the tool's constants: K 20, the five, 4,096 and 2,636 (test:939).
  - They agree with PLAN item 5a too: INT8's five differs on 307 of 400 (179 by set, 128 by order), the gold goes from 141 to 144 of 250, INT8 is not accepted, and its live series was registered at `3136fb8`.
- **Inputs:**
  - The export holds 415 rows (15 + 4 × 100), with gold on 100 WixQA, 80 ConditionalQA and 70 MultiHop-RAG questions.
  - V4's three cases files hold 100 rows each, with case ids in the export's format.
- **`without_text`:** it refuses a document name by exact match and a question by substring (reports/stage2/tools/stage2_common.py:125–154). It is applied to the parity rows, the record, the rows and `judged`'s output.
- **Running time:** ≈ 10 minutes, stopped at 30, follows §4.4's 3× rule (spec:137).
- **The laptop commands:** `context_judge run --out …/judge` and `judged --plan …/judge` read and write the same plan.json and verdicts.jsonl, and `judged` finds the runs beside the plan's folder (tool:1261).

## Disposition, 2026-10-30

Each finding was checked against the sources it cites; none is refuted. Line numbers below are in the edited files, not in the frozen copy: `spec` is `docs/specs/stage7-step1-arms-m3.md`, `tool` `reports/stage7/tools/arms_replay.py`, `test` `tests/test_stage7_arms_replay.py`.

- **1 and 2. applied, as one rule:** an arm qualifies at one reading only, `pooled_deciding` (`QUALIFIES_AT`, tool:102–103), on a detected gain whose c − b exceeds 2.8·√(b + c) (`MDE_Z = 14/5`, tool:104–105; `above_mde`, tool:956–960, exact in fractions). The MDE now has §4.4's one meaning, the K curve's effect detected four times in five, and a gain the sample only just detects (six to none, p = 0.031) no longer qualifies. Checked outside the repository for every b + c up to 1,000: at the margin's edge the exact p is at most 0.0078 (eight to none), and under no effect an arm passes with a chance of at most 0.0039, the two arms at most 0.0078 — the family spec:127–128 states. `qualifies` and `candidates` (tool:963–978) admit an open arm only so; every stop reading — ConditionalQA, WixQA, the pool and aircargo's two — still stops an arm on a detected loss, and aircargo qualifies none. Two qualifiers go by c − b at the pool, P on a tie (`decision`, tool:981–1000; spec:128–130). spec:33–42, 121–135 and 142–144 and the docstring at tool:40–48 say the same. Tests: test:578–596 (six, seven and twelve to two fail; eight, eleven to one and fourteen to two pass, each at p ≤ 0.008), test:631–679 and test:682–739 (the finding's example — WixQA six to none beside ConditionalQA ten to three and a pool of ten to nine — and a WixQA gain over a pool of six to nine read «H stays»).
- **3. applied:** spec:3 and tool:3 read «registered before the run». The SHA list (spec:197–202) names the SHA-256 of the tool and of this test, which test:1159–1216 checks against the files, and says the record's and the plan's are written in with the evidence commit. The pins are phrases that survive registration and the fill-in: «**registered before the run**», «SHA list of the run:».
- **4. applied:** the registration commit carries GR-1b's three files beside S's fix. `scripts/gr1b_stage_replay.py` gains `legacy_expand_graph_sections` (:30), the old rule copied, which its replay (:108, :113), `scripts/gr1b_seed_expansion.py` (:24, :70) and `tests/test_gr1b_stage_replay.py` (:46) use. spec:56–60 says so, and that `scripts/ab_remote_contextual.py` (:482) calls the product's function and so expands by the new rule.
- **5. applied:** `CONTROL` (tool:110–113) is the path stage 4 accepts. `control()` (tool:591–604) builds the checkout's `Settings` with its deployed settings, as `get_settings()` does without its directories, and stops the replay unless `retrieval_top_k`, `ollama_context_window` and `reranker_runtime` are 20, 4,096 and `torch`; the replay calls it first (tool:1155) and writes the three into the record (tool:1248). Beyond the finding: `get_settings()` also applies an experiment's overrides when `EXPERIMENT_ID` is set, so a set `EXPERIMENT_ID` stops the replay too (tool:597–598). spec:15–23 states the stop and the INT8 amendment — INT8's scores for all 415 questions, aircargo-gr's 15 scored anew, since item 5a's comparison scored stage 2's 400 — and spec:174–175 lists the stop. Tests: test:978–994 (K 10, a window of 8,192, `onnx`, an `EXPERIMENT_ID`: the replay stops and writes nothing), test:878 (the record's control); `_fake_runs` clears the four variables (test:810–822).
- **6. applied:** spec:163–168: at most 268 requests — 115 of H, at most 115 of S, at most 23 of P (P1b keeps fewer than five on 23 p2-aircargo questions and on none of aircargo-gr), 15 retests; by V3's sent documents P's are about 17; $25.2 at $0.094 a request, $56.3 at $0.21, 2.7–9.7 h.
- **7. applied:** spec:110–113 plans each arm that qualifies on the external bases — no detected loss, no `NOT_EVIDENCE` stop reading, the pooled gain above the MDE — as `candidates` reads it.
- **8. applied:** spec:114–116 names aircargo's stop readings: «full» and «full or partial», both runs pooled; each run beside is printed.
- **9. applied, as text:** the stop stays (tool:840–847). spec:177–179 says the tool stops and neither arm is read: S's path is then not the product's, a defect to fix before any reading.
- **10. applied:** `build_graph` (tool:296–310) builds S's retriever inside the same `try`, so a graph the retriever cannot take leaves S unread on the base as a graph that cannot be built does. A qualifying arm without an S row on aircargo gets both aircargo readings `NOT_EVIDENCE` and is not planned (tool:1215–1222; spec:118–119). Test: test:948–975 (S gains at the pool and has no graph of aircargo: no plan, no PRIVATE, the decision `NOT_EVIDENCE`).
- **11. applied:** each run's V4 questions must be among its records (tool:1163–1164), and after the gate passes the questions read with a saved V4 prompt must number `V4_SAVED`, 300 (tool:114, 1211–1212); spec:93–94 and 175–176. Test: test:997–1006; `_fake_runs` sets `V4_SAVED` to the fixture's count.
- **12. applied:** spec:132–135: a `NOT_EVIDENCE` decision repeats on a re-run, opens no answers, closes stage 7 as «H stays» does and names the arm unread; that arm comes back only by a registered amendment that removes the cause.
- **13. applied:** `MEASURE_CODE` holds `vectordb/manager.py` (tool:157).
- **14. applied:** `judge_plan` (tool:1085–1124) builds the runs and the plan in a staging folder and leaves nothing under PRIVATE; the replay checks the record and the rows with `without_text` first and only then puts the trees (tool:1272–1275); `put_trees` (tool:1038–1057) checks every tree already there before it writes any. A replay after an amendment takes a new PRIVATE — its judge runs' `launch.json` name another HEAD — and the old plan stays with the old record (spec:21–23); spec:113 and 179–181. Tests: test:776–783, test:1009–1017 (a record refused after the plan is built leaves no plan).
- **15. applied:** `stops_of` (test:618–628) builds the states the flow reaches: each arm's three external stop readings, and aircargo's two only for an arm the judge read. The G1 cases (test:631–739) use them: the finding's per-base gain beside a flat or falling pool, a gain within the MDE, a planned arm's aircargo loss or `NOT_EVIDENCE`. A real gain now runs end to end: in the fixture's kind «three» (test:73–80) S's section run of chunk 2 reaches chunk 5, ConditionalQA's gold, where H's expansion stops at chunk 4, and i.md stands second, so S's coherence keeps it (at fourth its section's strength would be 0.25 and S would drop it). With «three» on ConditionalQA and WixQA (`GAINS`, test:889–891) S reads eight to none at the pool, the replay plans the judge for S alone, and `judged` opens answers to S when every context is «full» and stops S when its contexts hold none (test:904–945).

None of these tests has run yet: the Mac gate of the nine files waits for the end of item 5a's live series.

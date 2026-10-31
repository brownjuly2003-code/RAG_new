# Cold read: stage 7, step 1, Amendment 1 (the stage-4 package): spec, tool and test before registration

Frozen copy read: the git repository `D:/RAG_new_cx/s1` at commit
`43b0cd144db075f9d9639d37cbfb254f62d6712d`, with a clean working tree. The amendment is
`git diff 0cf0fc4..43b0cd1` of the three files below. The product slice it builds on is
`e92c4af..0cf0fc4`. SHA-256 of the three files at `43b0cd1`:

- `docs/specs/stage7-step1-arms-m3.md` `1a98d7ce957c3740c66eca4c22bbbc115e005f66fd6dcc264e458fd503e8fcba`
- `reports/stage7/tools/arms_replay.py` `d1f5537c52e9a838e4b8d21062ddf03b7407d9907dd858d3ec0e072200328513`
- `tests/test_stage7_arms_replay.py` `03271f6b38bd0f7ba58c9467afd22c64e9d2c828c026519bae161ff6b12105dc`

This was a static reading. Neither the tool nor any test was executed. Only read-only commands
were run: grep, sed, git show, git diff, git status, git rev-parse, sha256sum, and one Python
read of the spec to check the pinned phrases. `spec:N`, `tool:N` and `test:N` are line numbers
at `43b0cd1`, where `tool` is `arms_replay.py`. Other files are cited as path:line in the same
snapshot.

Findings: 1 blocking, 2 should fix, 4 minor.

## Findings

### 1. Blocking: score's interpreter and tokenizer are neither named nor recorded, and the registered command runs score in the gate's environment, which has no model

- **Where:**
  - spec:54–56, spec:214–230
  - tool:1231–1254 (`score_header`), tool:1342–1345
  - vectordb/onnx_reranker.py:39–46
  - deploy/macos/start.py:37–39, :202–225
  - docs/specs/stage4-step5a-int8-reranker.md:35–41, :110–116, :170, :186–189
  - docs/operations/session-handoff-2026-10-30-stage4-step5a-block1.md:419–420
  - docs/evidence/gr2-entity-graph-lane.md:200–205
  - requirements.txt:28
- **What is wrong:**
  - **The command runs in an environment without the model.**
    - spec:220 runs `remote.py --site … score`.
    - `--site` is the gr4 venv plus the gate's site folder. The step-5a handoff (:419–420) and the step-5a spec (:186–189) both describe it as "the product's retrieval code, no model".
    - The gr4 venv is the one in which an earlier run failed with `ModuleNotFoundError: sentence_transformers` (gr2-entity-graph-lane.md:200–205).
    - spec:227–229 names only `RAG_RERANKER_RUNTIME` and `RAG_RERANKER_ONNX`.
  - **INT8 was measured in another interpreter, and the chat service runs in it too.**
    - The interpreter is `/Users/julia/RAG_Support_Assistant/.venv` (start.py:37–39).
    - Its versions: transformers 4.44.2, ONNX Runtime 1.23.2, numpy 1.26.4.
    - Step 5a also pinned the tokenizer snapshot `953dc6f6…`, ran offline (`HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`) at 4 threads, and refused a block whose versions differed (step-5a spec:35–41, :110–116, :170).
  - **The tokenizer is whatever the interpreter finds.**
    - `OnnxCrossEncoder` calls `AutoTokenizer.from_pretrained(model_name)` with no revision (onnx_reranker.py:45). The transformers version and the cached or online revision both come from the interpreter that runs it.
    - requirements.txt:28 asks for transformers ≥ 5.10.0, not the stand's 4.44.2.
  - **The header records almost none of this.**
    - It records the export digest and ORT's version. The version written is the tool's constant, set after an equality check.
    - It does not record the interpreter, the transformers, tokenizers or numpy versions, the tokenizer snapshot, the offline flags or the thread count.
    - replay loads no model, so nothing after score can tell which stack produced the scores that set H_new's five.
  - **Either way the result has no provenance.**
    - As written, score either cannot start: `import onnxruntime` or `import transformers` fails in the gate environment (tool:1342 raises an ImportError, not a stop). The operator then picks an interpreter that the spec does not name.
    - Or score runs on a tokenizer stack that is neither the chat's nor recorded.
    - H_new is the baseline of every G1 pair and of the advisory. Its five would then have no provenance for the part of the path that chooses it.
- **Fix:**
  - **spec:214–230:** run score the way start.py builds the service process, from inside the checkout:
    `env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin HOME="$HOME" LC_ALL=C PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH=<checkout>:/Users/julia/RAG_new_mf_gate_site RAG_RERANKER_ONNX=… /Users/julia/RAG_Support_Assistant/.venv/bin/python -m reports.stage7.tools.arms_replay score`.
    replay, which loads no model, may stay in the gate environment.
  - **tool:1231–1254:** add an `environment` block to the header holding:
    - `sys.executable`;
    - `onnxruntime.__version__` as imported;
    - the transformers, tokenizers and numpy versions;
    - the tokenizer's resolved snapshot (the commit of the cached `BAAI/bge-reranker-v2-m3` it loaded);
    - the two offline flags;
    - the session's intra-op thread count.
  - **Refuse other values:** score stops unless transformers is 4.44.2 and the snapshot is `953dc6f6…`, step 5a's stand. Otherwise, register the values to be used here.
  - **Header comparison:** score compares the whole header on resume. replay, which runs in another interpreter, compares the header without `environment` and copies that block into record.json.
  - **Test:** a journal whose header names another transformers version or snapshot refuses a resume.

### 2. Should fix: the batch comes from the shell running score, not from the chat, and any batch is accepted

- **Where:**
  - spec:46–48
  - tool:1218–1224, tool:1243–1244, tool:1349, tool:1396
  - deploy/macos/start.py:52–66, :202–225
  - reports/stage4-step5a/tools/int8_reranker.py:56
  - docs/evidence/gr3-graph-lane-ab.md:272; scripts/ab_context_precision.py:51
  - test:1003–1006
- **What is wrong:**
  - **The chat always uses batch 32.**
    - The service builds its environment from the deployment keys alone (start.py:202–225). `RAG_RERANK_BATCH` is not one of them (start.py:54–66).
    - So the chat always calls `predict(pairs)`, which batches at 32. Step 5a measured the same ("the product sets none", int8_reranker.py:56).
  - **score takes the batch from its own environment.**
    - `package_batch()` reads the environment of the score process (tool:1218–1224).
    - score accepts any value and only records it (tool:1243–1244, :1396).
    - test:1003–1006 asserts that a run at `RAG_RERANK_BATCH=7` succeeds.
  - **A batch of 8 is a standing recipe on this Mac.**
    - `RAG_RERANK_BATCH=8` appears in gr3-graph-lane-ab.md:272 and scripts/ab_context_precision.py:51.
    - If the invoking shell sets it, the K-14 pool of up to 28 is scored in calls of 8.
    - `quantize_dynamic` quantizes per call (spec:50–52), so the scores and fives are not the chat's. The header, the replay and the record all accept them.
  - **The spec names a setting the chat never gets.** spec:46–47 calls it "the chat's `RAG_RERANK_BATCH`".
- **Fix:**
  - **Tool:** score and replay stop unless `_effective_rerank_batch` returns None, the service's value. The header then always holds `rerank_batch: null` and `batch_size: 32`.
  - **spec:46–48:** "The service passes no `RAG_RERANK_BATCH` (deploy/macos/start.py), so the product calls `predict` once per question at its default of 32. A set `RAG_RERANK_BATCH` stops score."
  - **Test:** test:1003–1006 asserts the refusal at `RAG_RERANK_BATCH=7`. The K-14 cut test stays, without that variable.

### 3. Should fix: nothing stops a second score process from writing the same journal, and the registered run is a 90-minute foreground ssh call

- **Where:**
  - spec:59–60, spec:216–222
  - tool:1377–1388, tool:1266–1298
  - docs/specs/stage4-step5a-int8-reranker.md:161, :176–178
- **What is wrong:**
  - **The registered run is a long foreground call.**
    - score runs in the foreground through `remote.py` (spec:220) for about 90 minutes plus model loading.
    - Step 5a ran its INT8 series detached (`nohup … &`, joined with `;`, never `&&`) after an idle-Mac wait (step-5a spec:176–178).
  - **A dropped session can leave two writers.**
    - If the ssh session drops, the remote process can keep running. It writes to stdout only at the tenth question and at the end, so a closed pipe does not stop it soon.
    - A resume launched then opens the same journal with `r+b`, truncates it at its own `end` and appends (tool:1378–1385). Meanwhile the first process keeps appending at its own offset.
  - **The journal is then lost.**
    - Rows differ in length because of `seconds`, so the two processes' lines overwrite and interleave.
    - The journal then holds an invalid or out-of-order complete line. Every later resume and the replay refuse it (tool:1266–1298), and the scoring is lost.
  - **Memory.** Two INT8 sessions, at about 3.1–3.2 GB each (step-5a spec:161), also push the 8 GB Mac into swap.
- **Fix:**
  - **tool:1378:** take `fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)` on the journal before truncating it, and hold the lock to the end. If the lock is taken, stop with "another score holds the journal".
  - **spec:216–222:** run score detached, as step 5a did (`nohup … >> <OUT>/score.out 2>&1 </dev/null &`), after the idle-Mac check, and read its log. replay may stay in the foreground.

### 4. Minor: score spends its 90 minutes before the parity gate, which takes minutes, has passed

- **Where:**
  - spec:29–32, spec:54, spec:216–222
  - tool:385, tool:1260–1263, tool:1426–1486
- **What is wrong:**
  - **A broken checkout is scored to the end.**
    - Only replay runs the parity gate.
    - score's `Recorder` is exempt from the pool check (tool:385).
    - So a checkout whose fusion, rerank cut or expansion no longer reproduces stage 2 is scored in full. The break shows only at the replay afterwards.
  - **replay already works as a gate check when run first.**
    - Run before score, it completes the gate, then stops at "INT8 scores are absent: run score first" (tool:1486, :1263) without writing anything.
    - If the gate breaks, it writes `parity.jsonl` alone and exits 3.
- **Fix:**
  - **spec:216–222:** run `replay` first. Require it to stop on the absent journal, which shows the gate passed. Then run score, then replay again.
  - **Alternative:** score runs the same parity loop before its first question.

### 5. Minor: once the budget is exceeded, every resume is refused, and the spec does not say what comes next

- **Where:**
  - spec:61–64, spec:216, spec:257–258
  - tool:1357–1361, tool:1413–1414
  - docs/evidence/stage4-step5a-record.md:146
- **What is wrong:**
  - **The stop is permanent.**
    - The 3× check runs over the saved durations before every resume. Once it has fired, no resume can proceed.
    - spec:257–258 says "inspect why before another run". But another run is possible only by removing the journal, which can hold up to about 4.3 h of scoring (3 × about 85 min). The spec gives no rule for that.
  - **The clock is a shared Mac's wall time.**
    - The seconds are wall time per question on a Mac that other projects share.
    - spec:216 asks for an idle Mac, but the tool does not check for one.
    - So contention is enough to trip the stop.
  - **The forecast leans high.** The first question includes ONNX Runtime's first call, 13–15 s in step 5a (record:146). The first question of each base includes building its retriever. Both make the stop conservative, not wrong.
- **Fix:**
  - **spec:63–64, :257–258:** after inspection, the journal is moved aside, kept and named `NOT_EVIDENCE`, and score starts afresh.
  - **Optional:** wait for an idle Mac before the first question, as step 5a's series did.

### 6. Minor: the HEAD in the header and record is the gate checkout's overlay commit, and the tree is not checked clean

- **Where:**
  - tool:1237, tool:1442, tool:1534, tool:1544
  - spec:79–80
  - docs/operations/audit_fable_18_10_26.md:59, :215, :348
  - docs/evidence/k-curve-record.md:31
- **What is wrong:**
  - **The SHA exists only on the Mac.**
    - In `/Users/julia/RAG_new_mf_gate`, HEAD is a Mac-local overlay commit of the synced working tree (audit_fable_18_10_26.md:59, :348).
    - `nr.git_head()` returns that SHA, and no other copy holds it.
    - Earlier records named both SHAs by hand: "at the overlay of `97fc31e` (`4e239a84`)" (k-curve-record.md:31). spec:79–80 says only "the new HEAD".
  - **A local edit goes unseen.**
    - score binds its code by that HEAD alone; the header holds no measure-code hashes.
    - A file edited in the checkout after the sync keeps the same HEAD and is scored under it.
    - replay takes `measure_code_sha256` (tool:1544) only after the scoring.
- **Fix:**
  - **Header and record:** also carry `git rev-parse HEAD^`, the laptop commit under the overlay, and the measure-code SHA-256 map.
  - **Tool:** refuse a non-empty `git status --porcelain`.
  - **spec:79–80:** "the overlay of the registering commit, both SHAs named".

### 7. Minor: several of score's refusals have no test

- **Where:**
  - tool:1273–1298, tool:1364–1375, tool:1396–1397
  - test:939–955
- **What is wrong:**
  - **These refusals are untested:**
    - "extra questions";
    - "invalid complete line";
    - each per-row check of tool:1280–1297: a NaN score, a five outside the pool, a wrong length, another `batch_size`, negative seconds;
    - the cached-settings and factory checks (tool:1364–1375);
    - score's own stop on a pool that was not clean, a status other than ok, or another batch (tool:1396–1397).
  - Deleting any of them leaves the test file green.
  - **The header test covers six fields.** `tool_sha256`, `inputs`, `questions` and `rerank_batch` are not exercised. Today the comparison is of the whole dictionary, so this matters only if it is ever narrowed.
- **Fix:**
  - **Journal corruption:** a parametrized test with a NaN score, a five outside the pool, an extra row, or a complete line that is not JSON. Resume and replay must refuse, and the file must stay unchanged.
  - **Factory:** a test with a factory whose `runtime` is `torch`, whose `path` is another file, or with another `RAG_RERANKER_MODEL`. score must stop before it opens the journal.

## Checked and found consistent

- **The frozen copy:**
  - The three SHA-256 values above are those of the files at `43b0cd1`. The tool's and the test's equal spec:281–282.
  - All thirteen phrases pinned by `test_the_tool_reads_what_the_spec_registers` (test:1407–1422) stand in the spec, each on one line.
  - The SHA-list regex finds exactly the two files.
- **H_new is the product's chat path at the package, apart from what the spec states:**
  - **The vector lane.** `Store` returns `lane[:k]` (tool:196–198) for the product's `similarity_search(query, k=retrieval_k)`. `clean()` requires that k is 14 (tool:381).
  - **The BM25 lane.** The stand-in's scores rank the recorded lane, and the product takes its top 14 with a score above 0.
  - **Fusion and rerank.** Fusion happens only when BM25 returns results, and the merged pool is reranked whole.
  - **The same method as the K curve.** All of this matches the K curve's `Selection` (reports/k-curve/tools/k_curve.py:73), which slices both lanes before `_rrf_merge`. A record without lanes takes the vector lane from its pool in both. test:977–1016 shows 14, 14 and 28 candidates and the pool sets.
  - **The reranker.**
    - Rerank is the product's cached ONNX reranker (tool:1371–1375), called from `HybridRetriever`'s own `_rerank_scored_with_status` (vectordb/_base_manager.py:1049).
    - With no batch set, it is one `predict(pairs)`, and `OnnxCrossEncoder` chunks at 32. A K-14 pool holds at most 28, so it is one call, as in the chat.
    - That holds with or without a request deadline: the deadline splits calls only when a batch is set.
  - **The chat's side.** The chat's stream takes `get_relevant_documents` and `docs[:5]` (api/routers/conversation.py:2380). `_fit_stream_prompt` (conversation.py:669) fits by `prompt_input_limit(owner, "generate")`. That limit is 2,176 at a window of 3,584, which `Builder` checks (tool:442).
  - **The other settings.** The other retrieval settings come from stage 2's snapshot and equal the code defaults (config/settings.py:537–551, :649–651, :827–833): the rerank keeps 5, RRF k is 60, the expansion window is 2 with 3,600 characters, and the chunk overlap is 200.
  - **The stated differences.** The spec states the remaining ones: the approximate index (spec:286–287), and S reading the archive's metadata (spec:289–291).
- **S and P are read on H_new, pairwise and fairly:**
  - replay stages `Recorded` with the scored pool and its INT8 scores (tool:1309–1316).
  - H_new must reproduce score's pool by positions and order (tool:385) and score's five (tool:1324).
  - S runs on the same amended record at K 14 and must report H's candidate counts (tool:899–909).
  - P cuts H_new's five by H_new's INT8 `rerank_scores` (tool:923).
  - All three fit V4 at 3,584. The pairs are per question, on one pool.
  - The advisory's H_old comes from the gate's own K-20 PyTorch replay (tool:1462, :1497–1506). It enters no gate: the decision is built from `stops` alone (tool:1510–1570, :1593–1618).
- **The parity gate is still a real precondition:**
  - replay runs `control()`, then the whole parity loop at K 20 with PyTorch's scores and 4,096/2,636 (tool:1426–1481). This comes before the journal is read or any K-14 machine is built (tool:1483–1489).
  - test:1378–1391 forbids `new_machine` before the gate. On a break, replay writes `parity.jsonl` alone and exits 3.
- **score:**
  - **Resume.**
    - It reads only through the last newline (tool:1265).
    - It requires the whole header to be equal and every complete row valid.
    - It truncates a torn tail before appending (tool:1379) and never repeats a scored question (test:903–936).
    - A complete journal returns without loading the model (tool:1362–1363).
  - **No text.** The header and each row pass `without_text` before they are written (tool:1353, :1407).
  - **Forecast and stop.** The forecast is the mean of the first ten questions times 415 (tool:1330–1333). It is printed at the tenth question. The 3× check runs before a resume and after each question (test:1051–1063).
  - **A kill mid-question.**
    - It leaves no row. That question is redone, and its partial time is not counted (spec:258).
    - fsync is not F_FULLFSYNC on macOS. A killed process does not need it, so this matters only on a power loss.
  - **The seconds.** They feed only the budget. record.json publishes none of them, and spec:85–86 calls the timings planning estimates.
  - **Reproducibility.** Float scores round-trip exactly through JSON, so replay's five is reproducible.
- **Provenance beyond findings 1 and 6:**
  - **What the header binds:**
    - each run's provenance and a hash of its records;
    - the spec and tool hashes;
    - the export digest, checked in chunks before ORT is imported (test:866–884);
    - ORT;
    - the batch;
    - K.
  - replay recomputes the header and requires equality. A changed spec, tool, input or HEAD between score and replay therefore refuses the journal.
  - The record carries the journal's SHA-256 and its header (tool:1546).
- **The spec's numbers and text:**
  - **The score forecast.** 415 × 12 s ≈ 83 min, against the spec's "≈ 85–90 minutes" (spec:84).
  - **INT8's time.** "≈ 16 s" is 28.206 − 12.047 (stage4-step5a-record.md:153).
  - **The smaller pool.** "≈ 30 %" fewer candidates matches the K-curve record (:133–134).
  - **The plan's cost (spec:238–241).**
    - 360 requests = 3 × 115 + 15.
    - $33.84 at $0.094 and $75.60 at $0.21.
    - 3.6–13 h at 36–130 s a request.
  - **The Stops.** The stops in spec:243–258 match the tool's exits.
  - **PLAN.** PLAN.md:757–759 makes the stage-4 package the arms' control, as Amendment 1 does. PLAN.md:760–761 still describes the original registration's control. That is status text outside the three files, to update when the amendment is registered.
- **The tests:**
  - **Each new test fails if its behaviour is removed:**
    - export digest and ORT version: `get_reranker` is forbidden;
    - frozen inputs before loading;
    - resume: the predict calls start at entry 3 with batch 32, the prefix is unchanged, and a complete journal is not reloaded;
    - header mismatch: the file is unchanged;
    - replay's refusals: a swapped pool order gives a refused pool, a changed score gives another five, and a missing row gives "incomplete";
    - the K-14 cut: the asked k, the candidate counts and the pool sets;
    - fresh factory scores: the rows equal the factory's, and replay runs with ORT absent;
    - the forecast and the 3× stop, including on resume.
  - **None vacuous.** No assertion was found that cannot fail.
  - **Limits of the fixture.** The synthetic lanes (7 and 5) are shorter than 14. Only test:977 exercises the cut, and it does so directly.

## Disposition, 2026-10-31

Each finding was checked against the sources it cites; none is refuted. The interpreters'
versions behind finding 1 were read on the Mac on 2026-10-31: the service's
`/Users/julia/RAG_Support_Assistant/.venv` has transformers 4.44.2, tokenizers 0.19.1, numpy
1.26.4 and ONNX Runtime 1.23.2; the gate's (`remote.py --site`) has transformers 4.41.2; the HF
cache holds one snapshot of `BAAI/bge-reranker-v2-m3`, `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`.
Names below are of the edited files: `spec` `docs/specs/stage7-step1-arms-m3.md`, `tool`
`reports/stage7/tools/arms_replay.py`, `test` `tests/test_stage7_arms_replay.py`.

- **1. applied:** score and replay run by one recipe, the service's — its interpreter,
  `deploy/macos/start.py`'s `PYTHONPATH` (the checkout, then the gate's site folder), a clean
  `env -i` environment with `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` — written out in the
  spec's «Running it on the Mac»; `remote.py --site` stays for the tests alone. The tool's
  `environment()` reads, before any model loads, the interpreter, the libraries' versions, the
  two flags, the snapshot the cache's `refs/main` names and ONNX Runtime's version and path, and
  refuses unless transformers is 4.44.2 (`TRANSFORMERS_VERSION`), the snapshot `953dc6f6…`
  (`TOKENIZER_SNAPSHOT`), ORT 1.23.2 and both flags set; `loaded_environment()` checks, after
  loading, that the tokenizer came from that snapshot and that the session keeps the product's
  thread setting (0, ONNX Runtime's own choice). The block is in the score journal's header,
  which replay compares whole and copies into `record.json`. Tests cover each refusal.
- **2. applied:** a set `RAG_RERANK_BATCH`, empty or 32 included, stops score and replay: the
  service never passes it, so the chat scores a pool in one call of up to 32. The header holds
  `rerank_batch` null and `batch_size` 32; the spec says why; the test that scored at 7 now
  asserts the refusal, and the K-14 test counts one call per pool.
- **3. applied:** score takes an exclusive non-blocking `flock` on the journal before it
  truncates anything and holds it to the end; a held lock stops it with «another score holds the
  journal» and the file unchanged (test). The spec runs score detached (`nohup … >>
  out-a1/score.out 2>&1 </dev/null &`) after the idle-Mac check, replay in the foreground.
- **4. applied, as the alternative:** the parity gate is one function, `parity_gate`, that score
  runs after its preconditions and before the factory or the journal, and replay runs again; a
  break writes `parity.jsonl` alone and exits 3 in both (test: one broken byte stops score before
  `get_reranker` is called and before the journal exists). A broken checkout is no longer scored.
- **5. applied, in the spec:** once the 3× stop fires the journal is kept, renamed with its stop
  time and recorded `NOT_EVIDENCE`; score starts afresh at a new OUT only after the cause is
  read. The tool's cumulative stop is unchanged.
- **6. applied:** score and replay refuse a checkout whose `git status --porcelain` is not empty
  (ignored files excluded); the header and the record carry HEAD, its parent and its subject, so
  the gate's overlay names the laptop commit under it, and the measuring code's SHA-256 map. The
  spec names both SHAs.
- **7. applied:** journal corruption (a NaN score, a five outside the pool, a wrong length or
  batch, negative seconds, an extra row, a complete line that is not JSON) refuses resume and
  replay with the file byte-identical; a factory with runtime `torch`, another path or another
  model stops score before a journal is created; score's own stop on an unclean pool, a fallback
  status or another batch stops before its first row.

Beside the findings, the same commit fixes the package's INT8 test
(`tests/test_stage4_package_default_e2e.py`): with the vector lane empty BM25 hands five of the
six pages, as in `tests/test_reranker_onnx_e2e.py`, and the test now expects five; its two order
assertions stand. The registration is the commit that carries this disposition; the run follows
on an idle Mac.

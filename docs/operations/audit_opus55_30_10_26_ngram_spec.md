# Cold read: stage 4, item 5a, n-gram decoding — spec, tool and test before registration

Frozen copy read: `D:/RAG_new/.tmp/coldread-ngram/`, matching its `MANIFEST.sha256`:

- `stage4-step5a-ngram-decoding.md` `f187cd8adaaabcd22dd34a79db2fa01abe721b0d4db97a15f8d85db54ccd2375`
- `ngram_decode.py` `b28bf03a7db93c3f52b3d25b912d6184c4951c9248963b62b0a5aba0f6dc55bf`
- `test_stage4_step5a_ngram_tools.py` `960a7e4d47dd01f68ffccea1f1b109d0662ba1b49749733797d4e544fc7a06bc`

This was a static reading; nothing was run. `spec:N`, `tool:N` and `test:N` are line numbers in the frozen copy. The Ollama 0.33.2 and llama.cpp `d222767c7` files cited below are the copies downloaded to `.tmp/ngram/src/`, read as text only. `window_timing.py` is `reports/stage4-step4b/tools/window_timing.py` in the live tree.

Findings: 1 blocking, 1 should fix, 10 minor.

## Findings

### 1. Blocking: block 0's gate can never pass, because each Ollama runner gets a new random `LLAMA_MEDIA_MARKER` and `runner_same` compares the whole environment

- **Where:** tool:83, tool:313, tool:590–594, tool:636–637; test:55, test:132, test:751–756.
- **What:**
  - Each time Ollama creates a runner, it generates a new crypto-random `<__ollama_media_%x__>` (`llama_server.go:234–241`, called at :922).
  - It puts that value into the runner's environment as `LLAMA_MEDIA_MARKER` (:928). The variable reaches the process through `cmd.Env` (:431, :445–475). The comment at :1599–1600 calls it "the per-process llama-server media marker", and :138–141 says the value must match what the runner was given.
  - `ENV` fullmatches that name. `inputs` therefore stores the marker of the runner it read, then unloads the model (tool:497–498).
  - Block 0's first call starts a new runner with a different marker. So `run["env"] == facts["runner"]["env"]` is false on every attempt, and `check` fails block 0 with "Ollama's runner not the one the inputs read".
- **Why it matters:**
  - The series exits 8, then 8 on the second attempt, then 9 (tool:783–786, 796–803).
  - Block 1 never runs, and Running-it step 3 cannot end with `blocks to 1 done`, so there is no reading at all.
  - The test cannot catch this:
    - The runner stub returns the same dict both times (test:132).
    - The fixture environment holds only `DYLD_LIBRARY_PATH` (test:55).
    - The block-0 test varies only the arguments (test:753–756).
  - The end line keeps only the boolean, so the cause of the 8 cannot be read from the block's files. Spec:178 asks for exactly that: "once the cause is read".
- **Suggested change:**
  - Compare `binary` and `args` as now, but compare the environment without per-start keys (at least `LLAMA_MEDIA_MARKER`). Alternatively, leave that key out of `ENV`; for text-only prompts the direct server does not need it.
  - Write into the end line what block 0 read: the runner, or the keys that differ.
  - Add two tests: one where block 0's runner has a different marker and the gate passes, and one where `DYLD_LIBRARY_PATH` differs and it fails.
  - Name the excluded variables in spec:39–42 and spec:88–89.
  - Not checked from these sources: whether any argument is sized per load (`-c`/`-np` at `llama_server.go:375–376`, or `-b/-ub` at :590–592 when `num_batch` is automatic). Writing the differing keys into the end line would show this on the first attempt.

### 2. Should fix: an Ollama or `ps` error ends a block or the whole series instead of marking a disturbance, and the Stops do not name these exits

- **Where:** tool:370–388, tool:687–704, tool:418–438 with tool:566 and tool:722, tool:796–803; test:911–917.
- **What:**
  - `sample` calls `wt.foreign`, `wt.models` and `wt.llama_servers` without any error handling.
    - `wt.ollama` raises on a refused connection or on its 30 s timeout (window_timing.py:351–357).
    - `wt.llama_servers` runs `ps` with `check=True` and a 20 s timeout (window_timing.py:360–362).
  - Inside a block:
    - A raise before or after a call ends the block with exit 1.
    - The series reports that as 8, which spec:174 defines as "a block's gate failed". A second such raise gives 9.
  - Inside `idle`, the same raise ends the series itself with a traceback and exit 1, which no Stop names.
  - A server that is not ready within 300 s also raises inside the block, after the head line has been written. That is an 8. Spec:169 ties the 300 s limit to the head line, so a reader would expect a 5.
  - Step 4b's `busy` caught Ollama's errors in `models()` (`OSError`, `ValueError`), named them and waited (window_timing.py:963–967).
  - The test pins exit 1 → 8 → 9 (test:911–917).
- **Why it matters:** spec:96–99 says a question with something running beside it is "kept and named, not read for speed". The tool instead uses up the block's attempts. Two Ollama hiccups on the shared Mac, such as a restart or another project loading a model, end the series with 9 and no reading, under a rule the spec does not contain.
- **Suggested change:**
  - In `sample`, catch `OSError`, `ValueError` and `subprocess.SubprocessError` and return a sample that `disturbed` reads as disturbed (for example `models: None`).
  - In `idle`, treat the same errors as "not idle".
  - In the Stops, say that 8 also covers a block that ended on an error: server not ready within 300 s, a stream error, or a socket timeout. Also say that the traceback is in `$O/blocks.out`.

### 3. Minor: the gate's two prompt checks for a direct call cannot catch a wrong prompt

- **Where:** tool:588 and 597 with tool:644 and 650; tool:656–659; spec:86.
- **What:**
  - `sent_sha256` is not computed from what was sent. The tool copies the inputs' own `rendered_sha256` (`flat_sha256` for block 0) into the line, and `check` compares it with the same value.
  - The rule "cached and read tokens add up to the prompt" compares llama-server's counts with each other:
    - `cache_n` is `n_past`, and `prompt_n` counts the rest (server-context.cpp:3293–3294, 3955–3968).
    - `tokens_evaluated` is the prompt's token count (server-task.cpp:349).
    - So the sum always holds unless the prompt was truncated, and truncation is checked separately.
- **Why it matters:** the only real check that a direct block reads the same prompt Ollama would is the fidelity, which covers the warm-up and three questions of block 1. For the other ten questions, and for blocks 2–4, the two gate conditions check nothing, although spec:86 presents them as checks.
- **Suggested change:**
  - Hash `body["prompt"]` at the moment of the call.
  - Compare `tokens_evaluated` with step 4b's `w4096_answer_prompt_tokens` for the same case. That value is Ollama's `prompt_eval_count` for the same prompt, model and Ollama version. It is in `STEP4B_RECORD`, which tool:46 defines and nothing uses.

### 4. Minor: the outcome list leaves one case to the tool, and spec:94 says "nothing is read"

- **Where:** spec:111–118, spec:94–95; tool:937–939, tool:972–981; test:1088.
- **What:**
  - If ngram reads faster but base does not repeat itself, the bytes reading is `NOT_EVIDENCE` (spec:108–109). The outcome list has no line for this case. The tool returns `NOT_EVIDENCE`, and the test pins that.
  - Separately, spec:94 says "nothing is read" after a failed fidelity. In fact `read` writes a record of blocks 0 and 1 with the fidelity's calls and outcome `NOT_EVIDENCE`, as spec:112 implies.
- **Why it matters:** the rule that decides this outcome exists only in the tool, not in the registered text.
- **Suggested change:** add "faster, base not repeating itself: `NOT_EVIDENCE`" to the outcome list, and change spec:94 to "only the fidelity is read".

### 5. Minor: the model's renderer and parser are neither recorded nor checked, though they decide whether the direct body is the one Ollama sends

- **Where:** tool:480, tool:513–517, tool:181–199; spec:49–51.
- **What:**
  - `inputs` keeps `/api/show`'s parameters, the template's SHA-256 and `details`, but not `renderer` or `parser`.
  - If the model has a parser:
    - Ollama rewrites the response through it (routes.go:440–446, 685–696).
    - Ollama sends the parser's `preserved_tokens` to the runner (routes.go:668, 2314–2319; llama_server.go:1576).
    - The direct body never carries `preserved_tokens`.
  - `.tmp/ngram/NOTES.md:53` still lists "renderer/parser" as a fact needed from the Mac.
- **Why it matters:** if a parser is set, spec:49–51 ("the `/completion` body Ollama's runner sends") is false. Block 0's text can then differ from block 1's because of the parser alone, which ends in a 7 and a full restart in a new `$O`.
- **Suggested change:** record `renderer` and `parser` in `inputs.json` and have `inputs` refuse when either is set. Alternatively, send `preserved_tokens` in the body and say so in the spec.

### 6. Minor: `runner()` silently accepts an empty environment

- **Where:** tool:299–305, tool:313, tool:503, tool:534; test:620, test:668–674.
- **What:**
  - If `ps -E` shows no environment (another user's process, or a `ps` that withholds it), then `shown == command`, `env` is `{}`, and nothing complains. The inputs test pins `"env": {}` as accepted (test:673).
  - The arguments and environment are split on spaces (tool:304–305), so a value containing a space would be cut without notice.
  - `inputs` prints the arguments but not the environment.
  - `--version` (tool:503) runs without the runner's environment, so the recorded version may be a loader error. Nothing checks it.
- **Why it matters:** the direct servers would then start without the runner's `DYLD_LIBRARY_PATH`. They would either fail to start (an 8) or run on libraries other than the ones Ollama's runner uses, which the fidelity catches only as a 7.
- **Suggested change:** have `inputs` refuse when `DYLD_LIBRARY_PATH` is missing; on macOS Ollama always sets it (`llama_server.go:453–455`). Print the environment's keys at Running-it step 2.

### 7. Minor: the forecast's numbers do not agree with each other, and the cost of rejected drafts is not counted

- **Where:** spec:129–133, spec:14–15.
- **What:**
  - (a) "≈ 3 s saved a question of ≈ 18 s written" is a ratio of 18/15 = 1.2, but the same sentence gives ≈ 1.15. At 1.15 the saving is 18 − 18/1.15 ≈ 2.3 s.
  - (b) "Kept over drafted ≈ 0.2" means about 1,325 drafted tokens for 265 kept, so about 1,060 tokens are verified and thrown away. The arithmetic, at the spec's own ≈ 40 tokens a second (spec:20):

    | Item | Over the twelve | A question (mean) |
    |---|---|---|
    | Gross gain: 265 × (223 − 25) ms | ≈ 52 s | ≈ 4.4 s |
    | Cost of thrown-away tokens: ≈ 1,060 × 25 ms | ≈ 26 s | ≈ 2.2 s |
    | Net | ≈ 26 s | ≈ 2.2 s |

    The net is slightly higher once the token each verification batch adds is counted. The forecast does not say whether ≈ 3 s is before or after this cost.
  - (c) Neither ≈ 0.2 nor ≈ 3 s comes from the count the spec cites: `.tmp/ngram/copy_spans.py` computes only the accepted share (copy_spans.py:46, 56).
  - (d) Spec:14 splits "a median 74.5 s a call" into "of it 57.7 s … and 17.8 s", but those add up to 75.5 s. All three are medians over the twelve readable pairs, and medians do not add.
- **Why it matters:** the forecast is frozen and will be compared with the reading. As written, it cannot be checked against its own cost model.
- **Suggested change:** state the gross gain, the cost of thrown-away drafts and the net, then keep only the figures that follow from them. Give the step 4b medians as separate medians, not as parts of 74.5 s.

### 8. Minor: the forecast's count cannot be reproduced, and it was made on copies that step 4b's spec keeps on the Mac

- **Where:** spec:127–131.
- **What:**
  - The figure "265 of 1,246, counted by characters in step 4b's answer files" was computed by `.tmp/ngram/copy_spans.py`.
  - That script is outside the repository (`.gitignore:31` excludes `.tmp/`).
  - It ran on laptop copies of step 4b's `inputs.json` and its 26 answer files, in `.tmp/ngram/s4p4b/`. Step 4b's spec says "The inputs, the blocks and the answers stay on the Mac" (`docs/specs/stage4-step4b-window-timing.md:220`).
- **Why it matters:** a number presented as a count has no provenance in the repository, and the data it was computed from contradicts a registered rule.
- **Suggested change:** either run the count on the Mac and commit the script (it prints numbers only), or mark the figure as an off-record estimate. Remove the laptop copies.

### 9. Minor: the tool never checks that the worktree is clean

- **Where:** tool:459–537, tool:737–756; spec:145–147.
- **What:**
  - Step 4b's series refused a worktree that was not clean (window_timing.py:1008–1010). This tool only checks its own SHA-256, in the heads, against itself.
  - The tool imports `window_timing.py` (tool:39–41) and `prompt_budget.py` (tool:465–466). Their SHA-256s are recorded nowhere.
  - The only guard is the manual `git status --porcelain` in Running-it step 1, before `inputs`.
  - `measured_at_head` is `HEAD` at the time `inputs` ran, whatever the tree contained.
- **Why it matters:** the series runs for hours across several starts. An edit in `$W` between step 1 and a block would be measured and would leave no trace in the record.
- **Suggested change:** have `inputs` and `series` refuse a non-empty `git status --porcelain --untracked-files=normal`, as step 4b's series did.

### 10. Minor: the "peak" resident size is only the largest of the samples taken after calls

- **Where:** tool:583, 598, 607; spec:78.
- **What:** RSS is sampled once after the load and once after each call, and `rss_peak_mib` is the largest of those samples, not a peak.
- **Why it matters:** the value is printed only and decides nothing. But a rise during a call is not seen, and the name suggests it is.
- **Suggested change:** call it "largest after a call" in the spec and the record, or sample during calls.

### 11. Minor: the test leaves two boundaries that decide the speed reading unchecked

- **Where:** test:1034–1053; tool:863–866; spec:105.
- **What:**
  - `MIN_READABLE` is tested only with 9 readable questions (test:1050–1053). An off-by-one (`<=` at tool:866) would still pass.
  - No test row has a tie (`g == b`), so "a tie counts on neither side" is untested.
- **Why it matters:** both rules decide the speed reading.
- **Suggested change:** add a set of exactly 10 readable rows that reads "faster", and a set with ties that shows `faster + slower < readable` and a p computed on the untied questions only.

### 12. Minor: the spec names neither the log that step 3 reads nor the file that holds a failed block's cause

- **Where:** spec:152, spec:158–159, spec:177–178; tool:712, tool:750–752, tool:808.
- **What:**
  - Step 3's command writes `$O/series.out`.
  - The lines `block 1 read` and `blocks to 1 done` go to `$O/series.log`.
  - A block's traceback goes to `$O/blocks.out`.
  - Spec:158 says only "its log". The int8 sibling spec names `$O/series.log`.
- **Why it matters:** an operator checking step 3, or reading "the cause" after a 5 or an 8, faces three files and no rule saying which one to read.
- **Suggested change:** name `$O/series.log` for the series' lines and `$O/blocks.out` for a block's errors.

## Checked and found consistent

- The three files match `MANIFEST.sha256`. The test checks both SHA-256s in the spec's list but does not hash the spec, so filling in `<c>` keeps it passing.
- The schedule is 0 ollama, 1 base, 2 ngram, 3 ngram, 4 base. `REPEATS` and `PAIRS` match spec:66–69 and 108–110. The arms differ only by `--spec-type ngram-simple`, appended after the runner's arguments and the port (tool:55–58, 409).
- The request is num_ctx 4,096, the role's num_predict 1,024 and temperature 0.2, plus seed 1030 (tool:53). The render call in `inputs` carries the same options, so the runner `inputs` reads and block 0's runner are loaded with the same `-c`.
- `DEFAULTS` equal Ollama 0.33.2's `DefaultOptions` (types.go:1106–1133), and the merge order is defaults ← model parameters ← request (routes.go:125–159). `completion_body`'s fields, its omitempty handling and its `n_predict` bound (10 × num_ctx) match the runner's request (llama_server.go:1394–1415, 1560–1576).
- The prompt reaches the runner as the rendered string: Ollama tokenizes and cuts it only past num_ctx − 1 tokens (llama_server.go:279–293), and the thirteen are 2,105–2,380 tokens at 4,096. It strips a leading BOS only when the GGUF's tokenizer adds one (llama_server.go:243–276), which the fidelity's prompt tokens would show.
- Spec:26–30 is accurate. Ollama passes `--spec-type` only for its own MTP or external draft models, and it passes `ollama serve`'s environment to the runner (os.Environ in `SetupLlamaServerCommandEnv`). The n-gram size flags have no environment variable.
- Spec:17–19 is accurate. ngram-simple matches the last 11 tokens plus the sampled one and takes the most recent earlier match. It drafts up to size_m = 48 tokens and needs at least 12 to follow the match (ngram-map.cpp:49–110). The server bounds a draft only by the context left and the n_predict left (server-context.cpp:437–455).
- The timing is `predicted_ms / predicted_n`, which excludes the load and the prompt. `draft_n` and `draft_n_accepted` are absent when 0 and are read as 0.
- Fidelity mapping: Ollama's `prompt_eval_count` = `cache_n + prompt_n`, and `eval_count` = `predicted_n`. Blocks 0 and 1 send the same calls in the same order to a freshly started runner or server, so their caches line up. The final stream event's content is empty.
- Speed reading, as spec:100–107 freezes it:
  - per question, the mean of each arm's two blocks;
  - a question is readable when undisturbed in all four blocks;
  - ties count on neither side;
  - exact two-sided sign test, p < 0.05;
  - `NOT_EVIDENCE` below 10 readable;
  - the medians named in spec:106–107.
- Bytes reading: base must repeat itself on all thirteen, then the four pairs are compared. The outcome mapping matches spec:111–118 for the four cases listed there.
- Disturbance check, as spec:96–99 says:
  - samples are taken before and after each call;
  - step 0's process pattern, which matches none of the tool's, the series' or the server's command lines;
  - other processes' CPU over 100 %, leaving out the block, its parent and its server (for block 0, Ollama and its runner);
  - Ollama's loaded models and the llama-server count.
- Exit codes 3–9 and the limits (`START_LIMIT` 300, `QUESTION_LIMIT` 900, `IDLE_LIMIT` 3,600, `BUSY` 100, and `LOAD_LIMIT` 2.0 on the 5-minute load before the first block only) match spec:153–175 and the test's pins.
- Running it: the CLI forms match (`inputs I O`, `series O [LAST]`, `read O TARGET`). `series $O 1` logs `block 1 read` and, once the fidelity holds, `blocks to 1 done`. Without `1`, the series re-reads the kept blocks and ends with `SERIES_DONE`.
- Step 4b's figures, over its twelve readable pairs in `record.json`:
  - medians: 74.48 s a call, 57.67 s for the prompt, 17.79 s for the writing, 81.5 tokens, 222.9 ms a token, 135.87 s for the whole answer;
  - 1,246 answer tokens in total;
  - rates of 39.61 and 4.486 tokens a second;
  - slowest answer call 137.05 s (position 1).
- Arithmetic:
  - p is 0.0225 and 0.0034 for 11 and 12 of 13;
  - 900/137 ≈ 6.5;
  - 48/40 = 1.2 s, and 48 × 0.223 ≈ 11 s;
  - 265/1,246 ≈ 21 %, and 3/74.5 ≈ 4 %;
  - the 1.5-hour time forecast: 2 + 5 + 4 × ≈ 17.5 + 10 min.
- `STEP4B_INPUTS_SHA256` equals step 4b's record (`6dc8f49e…`). The `d7a81d5e…` in `.tmp/ngram/NOTES.md:41` is stale, and nothing uses it.
- The stand checks (no `config.ini`, the binary's SHA-256, the GGUF's size, Ollama's version, the tag's digest, a free port) match spec:34–42. `record.json` and `rows.jsonl` carry the fields spec:190–200 lists and no question, prompt or answer text.
- Spec:5–7 quotes PLAN 5a's lever word for word (PLAN.md:630–632), and spec:114 matches PLAN §8.3 item 2. PLAN.md:632–633 gives "≈ 19 из ≈ 77 с", which is not the twelve-pair median the spec uses from the record (17.8 of 74.5).

## Disposition, 2026-10-30

Each finding was checked against the sources it cites; none is refuted. Line numbers below are in the edited files, not in the frozen copy.

- **1. applied:** `PER_START = ("LLAMA_MEDIA_MARKER",)` (tool:85–88), and `runner_differs` (tool:343–349) compares the binary, the arguments and the environment without it. Block 0's end line keeps the runner it read and the keys that differ (tool:666–671); the gate fails on any of them and names them, or "not read" (tool:718–720). The marker stays in `ENV`: llama-server reads it only with a projector (server-common.cpp:117–127, server-context.cpp:999–1009). No other key in llama_server.go is drawn per start: the library path and `GGML_BACKEND_PATH` follow the binary's and the GPU libraries' places (:444–520), and `LLAMA_ARG_FIT_TARGET` is set only with a projector (:693–718). `ml.GetDevicesEnv` (:923) is not in the downloaded sources; a key it varied would now be named in the end line. Tests: the fixtures' runner carries a marker and comes back with a new one (test:51–68, 145); test:840–861; new test:864–884 (another marker passes, another `DYLD_LIBRARY_PATH` fails). Spec:39–48, 72–76 and 102–104 name the marker.
- **2. applied:** `sample` (tool:405–427) catches `SAMPLE_ERRORS` (tool:89–90: `OSError`, `ValueError`, `subprocess.SubprocessError`, and `http.client.HTTPException`, since an `IncompleteRead` in `wt.ollama`'s reply is no `OSError`) and names the error in the sample; its own `ps` now has `check=True` and a 20 s timeout. `disturbed` reads such a sample as disturbed (tool:430–441), `idle` as not idle (tool:775–794), and each block's summary counts `sample_errors` (tool:1057). Other errors in a block — the server exited or not ready within 300 s, a stream error, a socket timeout — still give 8, then 9; the Stops now say so and point at `$O/blocks.out` (spec:202–217), and spec:111–115 adds the sample rule. Tests: new test:514–536 and test:1091–1112 (one question disturbed, the block passes); test:553 (idle); test:1066–1088, renamed from `test_a_failed_block_is_tried_again_once_and_then_ends_the_series`, now fails on a stream error inside the block.
- **3. applied:** `sent_sha256` is the digest of what is sent, taken at the call (tool:663–665, 673–675). `inputs` stores step 4b's `w4096_answer_prompt_tokens` for each case from `STEP4B_RECORD` (tool:533–537, 555–556), and the gate holds a direct call's `tokens_evaluated` to it (tool:735–739); the add-up check stays. Block 0's prompt tokens stay held by the fidelity. Tests: test:71–87, 120, 727–731, the new case at test:919–925, and new test:938–954 (a swapped prompt fails both checks). Spec:66–71, 72–76, 98–101.
- **4. applied:** spec:130 adds «faster, base not repeating itself: `NOT_EVIDENCE`»; spec:109–110 now reads «only the fidelity is read». No code change.
- **5. applied:** `handlers_of` (tool:182–191) reads `renderer` and `parser` from `/api/show`'s fields or the Modelfile's `RENDERER`/`PARSER` lines; `inputs` refuses either (tool:541–543) and records both under `show` (tool:587–592). Refusal rather than `preserved_tokens`: without a parser Ollama sends none and leaves the text as written (routes.go:440–446, 685–696, 2314–2319), so the direct body stays the runner's. Tests: test:673–678, 733, 759–769. Spec:57–60, 233–234.
- **6. applied:** `inputs` refuses a runner without `DYLD_LIBRARY_PATH` (tool:563–564; Ollama sets it on darwin, llama_server.go:454–455, 477–486), runs `--version` in the runner's environment (`server_env`, tool:444–452, 569–577), refuses a non-zero exit, and prints the environment's names (tool:610). `runner` refuses a kept variable whose value holds a space (tool:323–330). Tests: test:403–434, 741–747, 770–780. Spec:43–45, 183–184.
- **7. applied:** spec:12–17 gives step 4b's figures as separate medians, with the twelve's sums the forecast uses (972 s of calls, 281 s of writing), and spec:20–23 the cost a token (≈ 25 ms checked, ≈ 223 ms written). Spec:141–163 restates the forecast: gross ≈ 52 s (≈ 4.4 s a question), the ≈ 1,060 thrown-away tokens ≈ 26 s (≈ 2.2 s), net ≈ 26 s (≈ 2.2 s) — ≈ 9 % of the writing, a ratio ≈ 1.1, ≈ 2.7 % of the calls — and names what the net leaves out. ≈ 1.15, ≈ 3 s, ≈ 4 % and «≈ 1 s slower» are gone.
- **8. applied:** spec:145–153 marks 265 of 1,246 as an off-record estimate, counted outside the repository on laptop copies of step 4b's answer files and not repeatable from the repository, and ≈ 0.2 as a guess. The laptop copies in `.tmp/ngram/s4p4b/` were removed on 2026-10-30, after the originals were found on the Mac (`inputs.json` by its SHA-256, the 26 answer files).
- **9. applied:** `clean()` (tool:506–508) reads `git status --porcelain --untracked-files=normal`; `inputs` refuses a worktree that is not clean before anything else (tool:516–517), and the series exits 6 at its start (tool:845–847) and before each block (tool:884–886) — not only at the start, as step 4b's did, since a series spans several starts. Tests: new test:798–803 and test:1158–1169; the stands stub a clean tree (test:701, 1009). Spec:175–180, 208–209.
- **10. applied:** `rss_peak_mib` is now `rss_max_after_calls_mib`, the largest of the samples after the calls, without the one after the load (tool:685–689, 1063–1067; test:834); spec:89–91 and 136–139 say «the largest after a call».
- **11. applied:** new test:1265–1276: exactly 10 readable, all faster, read «faster»; with four ties, faster + slower < readable, and p is the nine untied questions' (0.003906).
- **12. applied:** spec:192–195 names `$O/series.log` for the series' lines and says what `$O/series.out` and `$O/blocks.out` hold; the Stops say where each cause is read (spec:202, 213, 216–217, 219–220).

The Mac gate of these four files failed one test: in test:539–561 the error case of finding 2, last in its list, left the stand-in sample failing for the checks after the loop. test:557 now gives the loop's free sample back first; the test's lines from 558 on are one later than above, and the spec lists the test's new SHA-256.

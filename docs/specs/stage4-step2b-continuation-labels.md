# Stage 4, step 2b: the continuation read cold, beside step 2's warm one and on stage 3's 80 labelled answers

Status 2026-10-29: **registered before the first request**, with its tools and their test
([Records](#records)); **read 2026-10-29**, both gates passed, the signal not held, on the
catches: the default stays `classic` ([the record](../evidence/stage4-step2b-record.md)).
It runs only because step 2's candidate is the continuation
([step 2](stage4-step2-self-eval-continuation.md), «The candidate»: its rerun `s2-both-r2` passed
its gate, faster on 13 of 13, a median saving of 54 s). [`PLAN.md`](../../PLAN.md) stage 4,
item 2. Its stand is step 2's ([The stand](#the-stand)); the one value filled in at launch is
`<g>`, the commit that registers this spec.
[Amendment 1](#amendment-1-2026-10-29-v4s-registry-by-the-path-v4-gave-it), 2026-10-29, after the
check stopped at V4's settings and before the first request: each replay reads V4's registry
file by the path V4's settings give it.

## Why

- **What step 2 does not read:** step 2 paired the continuation with the classic on thirteen
  unlabelled answers — their seconds, their routes, whether the continuation scores at all. A badge
  that is faster but blind to a bad answer is a loss step 2 cannot see.
- **The labels:** stage 3's 80 aircargo answers of V4 (`4f48fed`) are graded by the judge
  (`reports/answer-prompt-v4/4f48fed/v4-aircargo-judge.cases.jsonl`), and
  [the handover signals' record](../evidence/handover-signal-v4-aircargo.md) read the classic's
  saved score against those grades. S1, a score under 80, caught 2 of the 17 targets and marked 0 of
  the 63 goods; S1′, a score under 100, caught 3 and marked 4.
- **Cold, and the bridge:** the chat asks its continuation warm, in the slot that has just streamed
  the answer. The 80 streamed in stage 3, so their continuations can only be asked cold:
  llama-server reads each from its start, and a batch read and a token-by-token stream need not
  give the same numbers, at temperature 0 too. So step 2b first asks cold the answers step 2 asked
  warm, and reads their routes side by side: **the bridge**. The 80 are asked only if it holds.
- **The question:** does the continuation, scoring the same 80 answers, lose any of what the
  classic catches? The default `STREAMING_SELF_EVAL_MODE` becomes `continuation` only if it does
  not, and only if the bridge holds.

## The stand

- **Code:** step 2's stand, `S=/Users/julia/RAG_new_chat_57420db`, `CODE_SHA`
  `57420db746e0510465bb5a08b7610e092b32e650` (in `$S/CODE_SHA`, which the replay reads): the
  continuation as step 2 ran it (`api/routers/conversation.py`, `agent/prompts.py`'s
  `SELF_EVAL_CONTINUATION_V1`, `OllamaProvider.generate_chat`). The tools sit in `T=$S/step2b`,
  which is also step 2b's folder: `bridge/` and `labels/`, each a phase's launch and lines, and
  `environment.jsonl`.
- **Step 2's answers:** its runs `s2-both` and `s2-both-r2`, `R2=$S/step2/runs`, read only: each
  answer's saved stream prompt, its case file (the answer as it streamed and the result event, with
  both self-evaluations) and `stages.jsonl`. Step 2's records of them as committed,
  `reports/stage4-step2/57420db/step2.json` and `step2.s2-both-r2.json`, copied to `D2=$T/step2`:
  each ask its reader read, its case file's SHA-256 and the continuation's warm score, seconds and
  counters. The reader holds both to their SHA-256.
- **The bridge's 25:** the asks step 2's reader read — delivered, both self-evaluations in the
  result — 12 of `s2-both` (its thirteenth unread) and 13 of `s2-both-r2`, each run's in its order.
  Warm, the continuation scored 100 on 23 of them and 95 and 90 on the two others: all 25 went to
  the answer as it stands.
- **V4's answers:** V4's runs `v4-aircargo-b01` … `v4-aircargo-b10` of stand `4f48fed`,
  `R=/Users/julia/RAG_new_chat_4f48fed/chatlive/runs`, read only: each answer's saved stream
  prompt, its case file and `stages.jsonl`.
- **The inputs of the 80:** `PLAN=$S/reports/handover-signal/d260d95/plan.json`, the handover
  signals' plan (each answer's files, the SHA-256 of its prompt and of its answer, the classic's
  saved score), and `LABELS=$S/reports/answer-prompt-v4/4f48fed/v4-aircargo-judge.cases.jsonl`, the
  judge's grades. The reader holds both to their SHA-256 as committed.
- **The 80:** `signal_record.py`'s classes — the 17 targets (graded bad, or declined) and the 63
  goods (graded good, not declined) — the targets first, each class in the plan's order. The 20
  partial answers are not asked.
- **The continuation, as the chat sends it** (`step2b_replay.py`):
  - the bridge's first turn is the run's own saved stream prompt, the one that holds the case's
    question: its text after the provider's `USER:` head, given back to the chat's helper, makes
    that file byte for byte;
  - the 80's prompt is rebuilt by V5's replay (`reports/answer-prompt-v5/tools/replay.py`, loaded
    from its file and used as it is) from the saved prompt's question and documents, with the
    chat's own fitting; flattened as the provider's stream sent it, it is the saved file byte for
    byte;
  - then the chat's own helpers in `_stream_continuation_self_eval`'s order: the first turn as the
    provider's stream sent it, the answer as it streamed, unstripped, and
    `SELF_EVAL_CONTINUATION_V1`; the window check (3,443 tokens at `num_ctx` 4,096); one
    `/api/chat` call to the stream model's own provider with the evaluate role's kwargs
    (temperature 0.0, 128 tokens); the strict parse and the entry;
  - the test holds this request to the live function's, byte for byte, on both stream paths.
- **Cold:** each continuation is read from its start, ≈ 2,370–3,130 tokens, at the classic's pace,
  ≈ 28 ms a token.
- **The host prompt cache:** a cold continuation leaves its state in llama-server's host cache, as
  step 0's answers and self-evaluations left 330–380 MiB each, up to 8,192 MiB on a Mac of 8 GB.
  In step 0 eleven such states took llama-server from 3,174 to 6,162 MiB and the swap from 1,837 to
  4,654 MiB ([its record](../evidence/stage4-step0-record.md#what-it-says)). So before each of
  answers n = 6, 11, …, 76 of a phase that a segment does not start with, the replay unloads the
  model, reads `/api/ps` and `ps` every 0.5 s until Ollama holds no model and `ps` lists no
  llama-server — any on the host — within one deadline of 120 s for the request and the reads, and
  loads it again: the cache goes with its process. A segment loads the model before its first
  answer and ends with the same verified unload. Julia's configuration is not touched; item 5's cap
  stays her word.
- **Interpreter and environment:** V5's, as `reports/answer-prompt-v5/tools/v5_chain.sh` ran it:
  `PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python`,
  `SITE=/Users/julia/RAG_new_mf_gate_site`, and the environment written out in
  [Running it](#running-it). The replay holds the settings to V4's first run's, and the
  continuation's provider, window, kwargs and instruction to the spec's; the model is
  `qwen3:4b-instruct-2507-q4_K_M`, held to its digest `0edcdef34593…` (exit 6 for any of these).
  V4's `stand_env.py` writes a line before the bridge, one between the phases and one after the
  80; each phase must lie between two of them, all naming Ollama 0.33.2 and one and the same start
  of its server, or that phase is `NOT_EVIDENCE`.

## What is read

**Per answer,** the replay's line in `$T/bridge/continuations.jsonl` or
`$T/labels/continuations.jsonl`:
- its ids — of the bridge: n, run, case, the case file and its SHA-256, the prompt's file and
  SHA-256, the answer's SHA-256 and its warm continuation as step 2's result keeps it (score,
  seconds, counters); of the 80: n, class, the plan's item, run, case, file names and the SHA-256
  of its prompt and of its answer; of both, the SHA-256 and length of the answer as sent,
  unstripped;
- its checks — the bridge's four: one prompt holds the question, the turn sent is that prompt, the
  answer is the result's from the stream, the stream's row holds it; the 80's seven: the files, the
  prompt's SHA-256, the rebuild's parity, the turn sent, the answer, the answer's SHA-256, the
  stream;
- the stream path; the outcome — `scored`, `not one integer`, `window` or `error` — and the score
  (−1 for none); the seconds; Ollama's counters; the window's numbers; the reply's length and done
  reason; the reload before it, where there was one; the segment that wrote it.

**Per segment,** in `launch.json`: its start and end, its status, the models Ollama held and the
llama-servers `ps` listed before it, the model's load seconds, the final unload's seconds and polls,
a load's or an unload's error type. Beside them what the first segment froze: the stand, the model
and its digest, the instruction, the window, the kwargs, the answer stop, the reload's cadence, the
tools' and the inputs' SHA-256 and the answers planned. A failed call's type, seconds and time also
go to `failures.jsonl`.

Never a question, document, prompt, answer or reply, and of an error its type only.

## How it is read — frozen before the first request

By `step2b_reader.py`: `bridge_reading` over the pairs `bridge_pair` forms, and `readings` over
those `pair_of` forms.

- **A route** is the stream's for a continuation's score: −1 (none) to the classic, which then
  decides; under 80 to a person; 80 and over to the answer as it stands.
- **A bridge pair** is one of the 25 and its cold line, readable when the bridge's gate passed and
  the line holds: its ids and its warm continuation are step 2's, its checks passed, its stream path
  and window are the spec's, and its outcome agrees with its score, its estimate and its error. Its
  two routes are the warm score's and the cold one's.
- **The bridge** is **held**
  with at least 10 of them readable and the cold route the warm one on all but at most 1,
  **not held** otherwise, and `NOT_EVIDENCE` with fewer than 10 readable. A cold continuation
  without a score goes to the classic, so it differs from a warm one that scored.
- **An answer pair** is one of the 80 and its line, readable when the 80's gate passed and the line
  holds, as a bridge pair's does.
- **An answer is flagged when its score is under 80**, the stream's route to a person. Its effective
  score is the continuation's where it scored 1–100, and the classic's saved one where it did not:
  the chat then calls the classic afresh, and its saved score is that call's draw on that answer at
  temperature 0. Such answers are counted apart, by outcome, and bounded by the next rule.
- **Scores held** with at most 6 of the 80 without a score — 7.5 %, step 2's allowance of one of
  thirteen — and **not held** otherwise.
- **Catches held** with at least the classic's 2 of the 17 flagged by the effective score — no net
  loss — and **not held** otherwise.
- **Over-marks held** with at most one of the 63 more than the classic's 0 flagged — 1.59 points
  of the goods — and **not held** otherwise.
- **The signal** is **held** when the bridge and the three hold, **not held** when any of them is
  not held, and `NOT_EVIDENCE` otherwise. The three are `NOT_EVIDENCE` without the 80's passing gate
  and all 80 pairs readable; the bridge without its own gate.
- **What 25, 17 and 63 can show:** the rules take margins, and the exact McNemar test of the 80's
  flags is printed beside them, deciding nothing. It can show a large gain, not a loss of the
  classic's two catches.
  - A lost catch is never significant: two lost and none gained give p = 0.5.
  - A gain in catches needs six gained and none lost (p = 0.031); five give 0.0625.
  - More over-marks need six added and none removed (p = 0.031).
  - Each rule's chance to pass, under a binomial model of independent answers — a rule's
    acceptance, not the protocol's power: the bridge 0.97 at a true rate of route differences of
    1 %, 0.91 at 2 %, 0.64 at 5 % and 0.27 at 10 %; the over-mark rule 0.87 at a true over-mark rate
    of 1 %, 0.43 at 3 % and 0.17 at 5 %; the no-score rule 0.89 at a no-score rate of 5 % and 0.30
    at 10 %; the catch rule 0.61, for a continuation that catches independently at the classic's
    11.8 %. How the two sides' flags correlate is not modelled.
- **Printed, deciding nothing:**
  - the bridge: the equal scores, the routes' pairs, the warm 100s, cold minus warm (higher, same,
    lower, the median), the outcomes, the pairs per run, each side's scores, median seconds and
    median counters;
  - the 80: the McNemar tests; the flags under 100 beside S1′; the continuation's own flags where it
    scored; Wilson intervals; each class's scores and medians; the scores' differences (higher,
    same, lower); the seconds, the counters, the estimates, the done reasons, the replies' lengths
    and the reloads' seconds.

**Each phase's gate,** in the reader's read:
- the launch: schema, spec, its phase, the stand's `CODE_SHA`, key, model and digest, stream path,
  instruction, window, kwargs, the answer stop, the reload's cadence, the answers planned (of the
  bridge 12 and 13 by run, of the 80 17 and 63 by class), status `complete` and as many answers;
- the tools' SHA-256 as listed below; the inputs' SHA-256 — none for the bridge, the plan's and the
  labels' for the 80;
- the lines: every line a JSON object, one an answer in order, each holding; the failures: the
  lines' errors, one for one, and the launch's count;
- the segments: each started on an idle Mac — no model in Ollama, no llama-server in `ps` — and
  loaded the model before its first answer; the first answer's may stand first; a failed call or an
  answer past the stop ends its own segment, as its status says; a reload stands before each of
  answers n = 6, 11, … its segment does not start with; at most 6 segments; the last, and it alone,
  completed the plan;
- the environment: a line taken before the phase's first segment and one after its last, every
  line naming Ollama 0.33.2 and one server, its start, binary and app unchanged;
- the bridge's own: step 2's two records as committed, by SHA-256, and the first answer not
  stopped;
- the 80's own: the input files as committed, the 80 as `signal_record.py`'s classes and the
  classic's saved counts (S1 and S1′).

**Forecast, written before the first request:** the bridge **held**: a cold continuation reads the
same tokens the warm one held in its slot, and the 25 warm scores, 90–100, are far from 80. Scores
held: warm, the continuation scored every one of the 25. Over-marks held: it scored none of them
under 90. Catches are the least certain of the three: two catches of 17 leave no room for a lost
one, and warm, the continuation scored no answer of the 25 lower than the classic did —
`aircargo-probation-extend`, which the classic sent to a person at 60 in both runs, it kept at 95
and 90. The forecast signal: **not held**, on the catches, with low confidence.

**What follows the reading:**
- **held:** the default becomes `continuation`, in a commit of its own with an E2E test of
  `/api/ask` (rule (a));
- **not held** or `NOT_EVIDENCE`: the default stays `classic`.

## Running it

On the laptop, for each `<f>` of `step2b_replay.py` and `step2b_reader.py` and each `<r>` of
`step2.json` and `step2.s2-both-r2.json`, with `<g>` the commit that registers this spec:

    git -C D:/RAG_new show <g>:reports/stage4-step2b/tools/<f> | ssh deproject-mac "mkdir -p /Users/julia/RAG_new_chat_57420db/step2b && cat > /Users/julia/RAG_new_chat_57420db/step2b/<f>"
    git -C D:/RAG_new show <g>:reports/stage4-step2/57420db/<r> | ssh deproject-mac "mkdir -p /Users/julia/RAG_new_chat_57420db/step2b/step2 && cat > /Users/julia/RAG_new_chat_57420db/step2b/step2/<r>"

On the Mac, in bash, with `S`, `T`, `R`, `R2`, `D2`, `PLAN`, `LABELS`, `PY` and `SITE` above. Each
replay runs in V5's environment, written out in full, since zsh does not split a variable into
words:

    env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin HOME="$HOME" LC_ALL=C PYTHONPATH="$S:$SITE" PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 REQUEST_TIMEOUT_SEC=3600 OLLAMA_REQUEST_TIMEOUT_SEC=3600 STREAMING_TIMEOUT_SEC=3600 RAG_DEVICE=cpu PROVIDER_REGISTRY_PATH=/Users/julia/RAG_new_chat_4f48fed/config/providers.yml "$PY" $T/step2b_replay.py …

`ENV` below stands for that prefix up to `"$PY"`, and `READ` for `"$PY" -I $T/step2b_reader.py`.

1. **Tools:** `shasum -a 256 $T/*.py $D2/*.json` must print the replay's and the reader's SHA-256
   as listed below and step 2's records' as the reader holds them; `cat $S/CODE_SHA` the stand's.
2. **Idle, before each launch,** step 0's rule, its four points
   ([step 0](stage4-step0-diagnostics.md), «Running it», 2); else wait, nothing is stopped. The
   replay itself refuses a segment while Ollama holds a model or a llama-server runs (exit 9).
3. **Environment, before the bridge:**
   `$PY $S/reports/answer-prompt-v4/tools/stand_env.py >> $T/environment.jsonl`.
4. **Check:** `ENV "$PY" $T/step2b_replay.py check $R $PLAN $LABELS $R2 > $T/check.jsonl 2> $T/check.log`.
   The last two lines of `check.log` must be `CHECK bridge 25 failed 0 past_the_window 0` and
   `CHECK answers 80 failed 0 past_the_window N`; else nothing is asked.
5. **The bridge's first answer:** `ENV "$PY" $T/step2b_replay.py bridge $R $R2 $T/bridge --first > $T/bridge.first.log 2>&1`,
   then `READ $T/step2b.first.json $T $PLAN $LABELS $D2`. Its `first_answer.stop` must be false.
6. **The bridge's rest,** detached, with `;` before `nohup`, never `&&`:
   `nohup ENV "$PY" $T/step2b_replay.py bridge $R $R2 $T/bridge > $T/bridge.log 2>&1 </dev/null &`.
   The two logs keep the first answer's `REPLAY exit 0` from being read as the rest's.
7. **After `REPLAY exit 0`** in `$T/bridge.log`: the environment's second line, as in 3, then
   `READ $T/step2b.bridge.json $T $PLAN $LABELS $D2`. The bridge's gate must pass and
   `readings.bridge.answer` be `held`; else step 2b ends here, the 80 not asked.
8. **The 80,** once the idle rule holds, detached:
   `nohup ENV "$PY" $T/step2b_replay.py run $R $PLAN $LABELS $T/labels > $T/labels.log 2>&1 </dev/null &`.
9. **After `REPLAY exit 0`** in `$T/labels.log`: the environment's third line, then
   `READ $T/step2b.json $T $PLAN $LABELS $D2`. Both gates must pass. The records are copied to the
   laptop as bytes.

### Stops

- **Exit 3 or 6** comes before any request, nothing written: an answer's check failed; or the
  settings, the model and its digest, the window or the instruction are not the spec's; or a resume
  would change what its launch froze, or its kept lines are not the plan's first. A settings
  mismatch stops the replay before its `REPLAY exit` line, its log ending `not the spec's: …`. A
  marked error fix or an amendment, registered before the first request, comes first.
- **Exit 9,** the Mac not idle at a segment's start, nothing written: the same command once the
  idle rule holds.
- **The first answer's stop:** a first line that does not hold, gives no score or takes longer than
  the answer stop — 255 s, 3× the forecast's longest answer, 85 s — ends step 2b as
  `NOT_EVIDENCE`, and the default stays `classic`.
- **Exit 4,** an answer past the answer stop, its line kept; **exit 7,** an answer's call failed,
  kept as the outcome `error` and in `failures.jsonl`, never asked again; **exit 8,** the model's
  load or unload failed, or the model or a llama-server outlasted an unload's 120 s, no line: each
  is resumed with the same command once the idle rule holds, going on with the next answer. The
  reader reads a phase of at most six segments, the first answer's among them: a phase that would
  need a seventh is `NOT_EVIDENCE`.
- **The bridge not held** ends step 2b: its signal is `not held`, the 80 is not asked, and the
  default stays `classic`.
- **The whole cap,** 3× each phase's forecast from its first launch — 2 h for the bridge,
  5 h 30 min for the 80: `touch $T/<phase>/step2b.stop` stops the replay before its next answer
  (exit 5), or `pkill -f "[R]AG_new_chat_57420db/step2b/step2b_replay.py"`, the model then unloaded
  by hand with `keep_alive` 0. The phase is not resumed and is `NOT_EVIDENCE`.

**Forecast,** the Mac's time once it is idle:
- a cold continuation reads ≈ 2,370–3,130 tokens (median ≈ 2,665): 64–85 s an answer at ≈ 28 ms a
  token, 92–124 s at 41 ms;
- the bridge: its 25 answers ≈ 31 min, its two loads and four reloads ≈ 5 min — ≈ 40 min, ≈ 50 min
  at the slower pace;
- the 80: ≈ 1 h 36 min, ≈ 2 h 19 min at the slower pace, its load and fifteen reloads ≈ 12 min
  at step 2's loads of 31–55 s — ≈ 1 h 48 min, ≈ 2 h 31 min at the slower pace;
- the check, the environment lines, the copies and the reads ≈ 15 min.

≈ 2 h 45 min in all, ≈ 3 h 35 min at the slower pace. The chat's estimates of the 80 run
2,734–3,525 tokens against the window's 3,443, so 0–1 of them are refused by the window check; the
bridge's are the ones step 2's chat made of the same turns, none refused.

## Records

`reports/stage4-step2b/57420db/` holds `step2b.json` (both phases' lines, the pairs and the
readings), `step2b.first.json` (the first answer's read), `step2b.bridge.json` (the bridge's read)
and `environment.jsonl`. They hold numbers, enums, ids, file names, model names, the paths named
here and SHA-256 strings: never a question, answer, prompt, document or reply, and of an error only
its type. The replay's folders stay on the Mac; the record names their files by SHA-256.

The record gets a row in [`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md) and a test that reads it
again. The tools and their test are committed with this spec, and the test checks each SHA-256
below; a later change is a marked error fix that updates this list:

- `reports/answer-prompt-v5/tools/qa_prompt_v5.txt` `835b0f2cf1ac7bc86ad30605367d81457b02e7436a5a5071642a5b881471c276`
- `reports/answer-prompt-v5/tools/replay.py` `ca954c59710e93925cc923f5b2a7f175ce86f7e1fa7b96a46d3b3bbeec4d6eed`
- `reports/stage4-step2b/tools/step2b_reader.py` `93432fd43c843e787583c82e205a5451fcbb6458a3be6d2d74c6ed635313de10`
- `reports/stage4-step2b/tools/step2b_replay.py` `7d0b46bb26943c5c2209bdfc7b827a720fcdb67365902d70d3eb49d21b21ff19`
- `tests/test_stage4_step2b_tools.py` `4ce01360c1ce07a029bb30a9367f90107a69eb83dccaf7c4ef38ee2229a01b04`

Marked error fix, 2026-10-31: the test provider and runtime fixture explicitly use the stand's
4,096 window (`OLLAMA_CONTEXT_WINDOW=4096` for the runtime). Code defaults moved to the stage-4
package (3,584); step-2b replayed the 4,096 stand. Only the test's stand setup and its hash
change; the reading does not change.

## A second opinion

Codex (profile cw, 2026-10-29) read the first draft, its tools and their test, with step 2's spec,
the chat's code at the stand and V5's replay ([`PLAN.md`](../../PLAN.md) §8.1). Its verdict: fix
first.
- **Taken:** the bridge, a prerequisite of the default; a failed call kept as its answer's outcome,
  never asked again; a resume refused before it loads if it would change what the first segment
  froze or its kept lines are not the plan's first, each line naming its segment; the gate reading
  the segments, the reloads, the answer stop, the environment's lines, the first answer, the
  failures against the lines and every line's parse; the final unload verified before the launch
  closes, its error kept beside the segment's own; the reload's cadence written as global answer
  numbers, its one deadline and `ps` counting every llama-server on the host; the margins named
  and the statistics' wording corrected; the tests of each such path and of the replay's folders
  read by the reader; `check.log` named.
- **Not taken:** a fresh classic call for an answer without a score: the saved score is that call's
  draw at temperature 0, and at most 6 answers lean on it, counted apart.
- **Not taken:** newly streamed answers, bad and borderline among them, scored warm and then cold:
  step 2's 25 warm scores exist, and a new stream would be step 2 again; the limit is in
  [Not said](#not-said).
- **Not taken:** the token events joined against the answer: the result's answer equal to the
  case's and the stream row's chunk and character counts hold it, and the answer's unstripped
  SHA-256 is kept in each line.

## Not said

- **Cold for warm:** the bridge's 25 all went to the answer as it stands, warm. It reads whether a
  cold continuation keeps a well-scored answer there, not whether a cold one flags what a warm one
  would flag; its printed differences show the direction, deciding nothing.
- The classic's scores are V4's saved ones, single draws of the classic as V4's stand ran it; the
  continuation's are this replay's single draws, at temperature 0, on another day.
- The labels are the judge's, a model's grades from stage 3, not people's.
- 80 answers of one corpus, one model and V4's prompt: what the continuation loses on another
  corpus or prompt is not read.
- Four answers of five follow another in the slot and keep its ≈ 165 tokens of head; the fifth
  reads them again after the reload. None should be restored from the host cache, which restores a
  state only for a prompt keeping a quarter of it; the serve log's slot lines are not read, and a
  restore would change where the read begins.
- The seconds say nothing of the chat's: a cold continuation reads its whole prompt, the chat's
  warm one its instruction and the turn markers.
- The window check is the chat's estimate, with its margin: an answer it refuses gives no score
  and keeps the classic's, as the chat would.

## Amendment 1, 2026-10-29: V4's registry by the path V4 gave it

Registered before the first request, after the check stopped. The answers, their order, the
tools, their SHA-256, the forecasts, the caps, the stops and the readings stay as above; the
environment of [Running it](#running-it) gains one variable.

**What the check gave.** Run as registered, after the first environment line, it stopped with
exit 6 before any request, `not V4's: provider_registry_path`. V5's check holds the settings to
V4's first run's, and V4's settings name the provider registry by V4's stand,
`/Users/julia/RAG_new_chat_4f48fed/config/providers.yml`, while this stand's default is its own
`config/providers.yml`. The two files are one: SHA-256
`a71571492dff2e96abe41b7391286f5e602aae9d1edf51d79b73730667fae349` on the Mac in both stands, and
unchanged in git from `4f48fed` to `57420db`. Every other setting V5's check reads, and the
stream model, were V4's.

**The change.** Each replay runs with
`PROVIDER_REGISTRY_PATH=/Users/julia/RAG_new_chat_4f48fed/config/providers.yml`: the settings
are V4's by V5's own check, unchanged, and the registry the stand reads is byte for byte its
own. With it, before any request, the check's last two lines were
`CHECK bridge 25 failed 0 past_the_window 0` and `CHECK answers 80 failed 0 past_the_window 0`:
the chat's estimates run 2,866–3,113 tokens for the bridge and 2,736–3,363 for the 80, under the
window's 3,443. The first environment line, taken before the check, stands as the bridge's
first.

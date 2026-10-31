# Stage 4, item 6: the final package's aircargo answers

Status: **registered before the run**, 2026-10-31, before the first request, with its tools
and tests in one commit; the stand is that commit. This is preparation, not a quality result. Item 7 uses the same stand after these answers finish.

A cold read (docs/operations/audit_opus55_31_10_26_stage4_items6_7.md) found 2 blocking, 5 should fix and 6 minor; each is applied (its Disposition says how).

## What is measured

PLAN stage 4 item 6, M1 and M3 (§4.3): 100 new aircargo answers through the customer's
`POST /api/ask/stream`, paired by question with published answers/contexts. The package is
K 14 in each hybrid lane, the V4 prompt, a 3,584 context window (input limit 2,176), and
`BAAI/bge-reranker-v2-m3`'s INT8 export through ONNX Runtime; five kept, parent expansion,
classic self-evaluation and suggested questions remain in the chat. The fourth lever,
llama.cpp's `cache-ram = 1024`, is already permanent on the Mac. This run checks its file,
never writes it. Lever gains measured separately are not added together.

M1 compares bad and good shares with V4's aircargo answers on `4f48fed`, runs
`v4-aircargo-bNN`, plan `v4-aircargo-judge`. M3 reads **the same new M1 plan's
context_has_answer** against that field in V4's M1 plan: the same sent-context instrument,
instructions, salt and route. There is no separate context-judge plan. Both V4 and stage 2
part 1's old side were 100/100; the paired baseline here is V4. The record prints that
**100/100 ceiling**. Only “M3 falls, detected” is harm; there is no “M3 rises” outcome.
V4 kept stage 2's retrieval; shorter fitting can still change what is sent.

## The stand

`reports/stage4-final/tools/raise_stand.py` archives the clean registering HEAD into a new
`/Users/julia/RAG_new_chat_<seven>` and writes `CODE_SHA` and `STAND_FILES.json` (SHA-256 of
archive bytes, independent of Windows checkout line endings). It links the existing
`.ask100-runtime` from `/Users/julia/RAG_new_ask100_20261012_7cad79f`. It refuses an existing
stand or modified/staged tracked files. Untracked files are ignored (`--untracked-files=no`):
`git archive` cannot include them. `run.py` checks every manifest entry before and after each batch.

The old runtime's `env.json` pins qwen2.5:7b. The old chatlive supervisor drops its model
selection keys in mode `prod`; this new driver admits **only** `start.py`'s deployment keys
from it. Model, provider registry, K, window, device, runtime, batch and timeout overrides
are discarded, not copied into the API. The index and ONNX path are explicit deployment
facts. Secrets never enter exported records or command arguments.

The service interpreter is `/Users/julia/RAG_Support_Assistant/.venv/bin/python`, with
`PYTHONPATH=<stand>:/Users/julia/RAG_new_mf_gate_site`. Both HF offline flags are 1.
`stand.py` imports stage 7's frozen `environment()` and `package_batch()` checks: transformers
4.44.2, ORT 1.23.2, tokenizer snapshot `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` from cached
refs/main, and unset `RAG_RERANK_BATCH` (null, effective 32). It also requires tokenizers
0.19.1, the service executable, and product session threads 0 (ORT chooses the threads).
The actual loaded ONNX tokenizer/session are checked by frozen `loaded_environment()`.
Neither a tokenizer nor a model is fetched.

The exact code-default tag is `qwen3:4b-instruct-2507-q4_K_M`, digest
`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`; Ollama is 0.33.2, one
server, its pid/start/binary unchanged across each batch and the base. Effective settings
must be K 14 / 3,584 / onnx / five / CPU / local-first / routing off / classic self-evaluation,
the default 4B and all three 3,600-second limits. The prompt id is `QA_PROMPT_V4` and the
product's `prompt_input_limit` must give 2,176. A missing setting is a refusal too.

`RAG_RERANKER_ONNX=/Users/julia/RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx` must hash to
`57335a9f061fe31378c160ddd0861711a0fbdfa20f70aa2640d473dfc4bc1343` (restored
`reports/stage4-step5a/onnx/manifest.json`). The read-only cache config at
`~/.config/llama.cpp/config.ini` must hash to
`c75f44912ea2c7f54ea0cf0e9ffea8f05466ae447961d99c8f12d716589b4e6c`. Both are hashed in chunks
before API startup and after the batch, outside timed questions. No fallback to PyTorch.

The corpus is stage 2's aircargo generation: the archived chunks match stage 7's frozen
`ARCHIVES`; its three generation files match live item 5a's `CORPUS_SHA256`. The driver
copies the existing index byte for byte for each batch and records both maps. Copies stay
private for inspection; removal after review is an operator action, not a tool's deletion.
The reader rechecks the registered corpus/question digests and binds the API's actual
index path to that copy; a missing index receipt refuses.

## Questions, run, forecast and stops

`stage2_cases.registered` supplies the same 100 ids, order and question-file digest as stage 2
part 1, from `evaluation/curated_cases_aircargo.jsonl`. Ten batches of ten,
`final-answers-aircargo-b01` through `b10`: each a fresh API, no model resident before it,
the model loaded separately and unloaded afterwards. Preload reads `ollama_context_window`
from the API's actual effective settings, sends `options.num_ctx`, then requires `/api/ps`
to show just the chosen model with `context_length` 3,584 before question 1. The launch
records the payload, response, load seconds and llama-server pid. Every in-question memory
reading and the check after the last question must have that same pid; a reload refuses.
After unloading, poll both `/api/ps` and the process list for up to 60 s, logging each
reading, until both are empty, then take idle-after. An unfinished unload is a cleanup
failure, not foreign interference. PostgreSQL and API use the existing
isolated ports 55433/8002; taken ports refuse. Only owned children are stopped.

The frozen stage 2 observation API records the actual lanes, pool, scores and sent prompts;
the frozen HTTP reader sends each question and drains before the next. Its original timed
rerank and selection are unchanged. After **every** question, including 1 and 5, the path
gate requires HTTP success, an answer/result, no stream/drain error, one retrieval, both
lanes nonempty and at most 14 each, successful rerank, five documents, and one V4 labelled
prompt. Failure stops immediately. Ten complete batches are needed to freeze a judge plan;
missing, duplicate or reordered cases, drifted settings or provenance cannot count.

Forecast from V4's measured aircargo **total_sec median 296 s, p90 390 s, max 581.6 s**
(first of batch up to 559 s): first question 360 s, other nine 300 s, startup/preload
120 s per batch. This is **31,800 s = 8.83 Mac hours**; 3,180 s a batch. PLAN's earlier
150–200 s estimate is advisory against that tail. The disturbed item 5a medians (321.9 s
INT8, 542.1 s torch) warn about contention; they are not idle speed evidence or additive savings.

There is **no per-question stop below the product's 3,600-s ceiling**. The HTTP reader
also respects the remaining batch/series deadline. The stops are 3× a batch (**9,540 s =
2.65 h**) and 3× the series (**95,400 s = 26.5 h**), not a fast-answer selection rule.
API startup has 360 s, model preload 300 s. `OUT/STOP` stops before the next question/batch;
SIGTERM cleans up owned children. The primary “whole answer” is `result_sec`; the record
and progress log also name `total_sec`, stream close including suggestions.

Before **each** batch, poll/log the idle checks every 60 s for at most **30 minutes**:
5-minute load below 2, no resident model/CI lock/foreign test, replay, supervisor, large
Python or VM job. This follows step 4b's bounded `IDLE_WAIT_SEC` pattern with this item's
explicit 1,800-s bound. The waits are outside question and batch clocks, inside the series
stop; ten waits could add up to 5 h to the 8.83-h forecast. If still busy, quality proceeds
and the launch says `busy: true`. Taken ports, a resident model or a changed stand still
refuse because they change the path. Incidental quality times decide no speed claim.
The sibling `*-idle-wait.json` logs every reading; the launch also keeps the final check.

On a path break, ceiling, cleanup failure or incomplete batch the base is **NOT_EVIDENCE**,
never a pass. Keep every file, read the cause, then use a new OUT; a product fix requires
a new stand and all 100 again. No automatic quality retry hides a failed question.

## The judge

Only after batch ten: `judge.py plan --base aircargo` builds one M1 plan with
`scripts/chat_answer_judge.py`, including its `context_has_answer` for M3. It adds the
unchanged committed handover `Reading` section as V4's aircargo plan did. Instructions,
salt `chat-answer-judge-2026-10-18` and isolated route stay unchanged:
`claude-opus-5-5`, effort `max`. The explicit later `grade` command alone calls the judge.

The same receipt freezes a **judge bridge**: import V4's `bridge_plan.py` unchanged,
cut V4's aircargo plan to its 15 retested originals and their copies, retain V4's original
reply lines byte for byte, and grade only the copies in this item's window. Before this,
check the source plan/replies against their hashes in V4's published export. The receipt
pins both plans and the bridge's original-reply prefix. The bridge export reuses frozen
admission and stability functions directly, so it needs no private V4 run folders.
It records old/new `admitted_cli`, pair ids and the stability result; no request/reply text.

Commit the text-free `plans.json` receipt **before either first grade**. Grade/export
require it in HEAD and byte-identical plans; bridge originals must remain unchanged.
The new plan has 100 requests and 15 retests, the bridge adds 15 requests. Frozen stage 2
stability stays: at least 12 pairs, and quadratic κ ≥ 0.6 OR at least 13/15 agreement with
no two-step disagreement. Failed within-plan stability, a missing verdict, or a failed
bridge makes the paired M1 **and M3 NOT_EVIDENCE**. The answers remain available for a
later frozen plan; the package does not receive a pass. Six-reply admission stays unchanged.

Budget: **130 requests: 100 + 15 retests + 15 bridge copies**. Measured cost per request
ranges from stage 2's $122.45/690 = **$0.1775** to V5's $175.71/620 = **$0.2834**:
**$23.07–36.84**, before adapter retries. At 120–130 s each, **4.33–4.69 laptop hours**.
Forecasts: M1 14,950 s and bridge 1,950 s; 3× stops 44,850 s and 5,850 s, respectively.
The clock persists the **sum of request durations**, not wall time: sleep and usage-window
pauses do not count. The stop acts before the next request; a returned reply is always
journalled. A stop marker prevents further grading but never export of replies already
received. An incomplete/unstable export cannot support a reading. Keep stopped plans;
read the cause before freezing a new one. Actual usage includes retries.

**Order:** these 100 answers first; finish **all** Mac-touching laptop work (ssh/scp,
including private corpus and answer copies) next. Then the laptop judges M1 and bridge
serially **in parallel with item 7 on the Mac**. No copy, sync, test or other owned task
runs on the Mac during item 7; any remaining copies wait until it finishes.

## Reading and outcomes

`record.py quality --base aircargo` requires all 100 paired ids, counted/stable M1
exports, the registered route/instructions/salt/reading, V4 at 4f48fed, the new stand,
each new verdict's sent-prompt SHA, and the bridge bound to V4's original plan/replies.
It hashes both exports and cases files plus the bridge; admitted CLI versions stay visible.

For M1 bad, M1 good and M3 it imports **unchanged** `v4_record.paired`: new minus old,
Newcombe method 10 (Wilson) and the deterministic cluster-bootstrap 95% intervals; aircargo
has one question per cluster. It reports both, with `read95` spanning them. **Detected**
means both exclude zero on the same side, with V4's four-decimal rounding; touching zero
does not count. This is V4's rule, not McNemar or a new significance rule.

| Outcome | Rule, in this order | Consequence |
|---|---|---|
| harm detected | M1 bad rises, M1 good falls, or M3 falls, detected | Name the affected metric and pairs. If **M1 bad rises**, stage 5 waits for Julia's one yes/no on the package; the package stays in code meanwhile. Otherwise stage 5 follows. |
| gain detected | No harm above; M1 bad falls, M1 good rises, detected | Name the metric; stage 5 follows. |
| holds | No detected harm or gain | No detected change, not proof of equality; stage 5 follows. |

Any missing admission condition gives NOT_EVIDENCE instead of these outcomes and supplies
no release decision. MDE ≈ `2.8 sqrt(d/100)`: 9, 13, 15 percentage points for discordance
0.1, 0.2, 0.3. Smaller changes remain unresolved. Forecast: **holds**, not a promised
non-inferiority bound. K-curve gold 141 → 136 at K 14, p 0.125, and INT8 gold 141 → 144
pull in different directions; the 3,584 window's shorter input limit can lose sent context.
Neither component reading predicts the final paired M1 by addition.

This does not measure new independent questions, external-base quality, an idle latency
distribution, or answer determinism. One unseeded answer per question, the existing set,
residual judge drift despite the bridge and the M3 ceiling constrain the reading. Stage 5 is not run here.
The shared run/answer-record/M1-plan tools take `--base`; external M3 is deterministic and
the aircargo paired-M3 reader refuses an external base rather than misusing its judge.

## Running it on the Mac

Before the answer run, prepare private inputs on the laptop. The four aircargo files can
be copied from the Mac with the following **preparation-only** commands; do this before
item 7, never during it. V4's private plan directory is an operator-supplied existing
location (the copy does not establish that location). Restore the published V4 export
and cases file if absent; do not reconstruct them from prose.

```powershell
$Sha = (git rev-parse HEAD).Trim()
$Short = $Sha.Substring(0, 7)
$Private = Join-Path (Get-Location) ".tmp/stage4-final/$Short"
$Data = Join-Path $Private "data"
$V4 = Read-Host "Existing private V4 aircargo plan directory (plan.json and verdicts.jsonl)"
$Old = "reports/answer-prompt-v4/4f48fed/v4-aircargo-judge.json"
New-Item -ItemType Directory -Force "$Data/aircargo/index"
scp "deproject-mac:/Users/julia/RAG_new_external_s1/aircargo/chunks.json.gz" "$Data/aircargo/chunks.json.gz"
scp "deproject-mac:/Users/julia/RAG_new_external_s1/aircargo/corpus.manifest.json" "$Data/aircargo/corpus.manifest.json"
scp "deproject-mac:/Users/julia/RAG_new_external_s1/aircargo/chunks-report.json" "$Data/aircargo/chunks-report.json"
scp "deproject-mac:/Users/julia/RAG_new_external_s1/aircargo/index/index-receipt.json" "$Data/aircargo/index/index-receipt.json"
```

The **first laptop measurement command**, before raising the stand or making a plan,
checks presence and hashes of all these inputs; do not proceed if it refuses:

```powershell
python reports/stage4-final/tools/judge.py inputs --base aircargo --data "$Data" --v4-source "$V4" --old-m1 $Old --out "$Private/inputs.json"
if ($LASTEXITCODE -ne 0) { throw "Private inputs refused" }
python reports/stage4-final/tools/raise_stand.py $Sha
```

On the Mac in zsh, enter the registering SHA. Use the service recipe, never
`remote.py --site`'s transformers 4.41.2 environment. The driver performs the bounded idle
wait itself; an immediate `run.py idle` refusal is not a prerequisite for the wait.

```sh
read -r SHA
S=/Users/julia/RAG_new_chat_${SHA:0:7}
PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python
T=$S/reports/stage4-final/tools
DATA=/Users/julia/RAG_new_external_s1
cd "$S"
CLEAN=(/usr/bin/env -i HOME="$HOME" PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH="$S:/Users/julia/RAG_new_mf_gate_site" PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 RAG_RERANKER_ONNX=/Users/julia/RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx "$PY")
"${CLEAN[@]}" "$T/stand.py"
nohup "${CLEAN[@]}" -u "$T/run.py" answers --base aircargo --data "$DATA" --out "$S/final-answers" >> "$S/final-answers.out" 2>&1 </dev/null &
echo $! > "$S/final-answers.pid"
```

Read `final-answers.out`, per-batch progress and wait logs. Ten `FINAL_DONE ... complete`
lines and the record gate are required. `touch "$S/final-answers/STOP"` stops before the
next request; SIGTERM only the recorded owned pid for an immediate stop. After completion:

```sh
"${CLEAN[@]}" "$T/record.py" answers --base aircargo --runs "$S/final-answers" --data "$DATA" --out "$S/final-answers.json"
tar --exclude='*/chroma' -czf "$S/final-answers-private.tar.gz" -C "$S/final-answers" .
```

On the laptop, the first command rechecks private inputs before plan/grade steps. Finish
both scp commands and extraction **before item 7 starts**. The b01 admission already checks
its preloaded llama-server pid across every question, so a context-triggered reload cannot
hide until the speed run. Reuse the variables above:

```powershell
python reports/stage4-final/tools/judge.py inputs --base aircargo --data "$Data" --v4-source "$V4" --old-m1 $Old --out "$Private/inputs.json"
if ($LASTEXITCODE -ne 0) { throw "Private inputs refused" }
New-Item -ItemType Directory -Force "$Private/runs", "reports/stage4-final/$Short"
scp "deproject-mac:/Users/julia/RAG_new_chat_$Short/final-answers-private.tar.gz" "$Private/answers.tar.gz"
scp "deproject-mac:/Users/julia/RAG_new_chat_$Short/final-answers.json" "reports/stage4-final/$Short/final-answers.json"
tar -xf "$Private/answers.tar.gz" -C "$Private/runs"
$Receipt = "reports/stage4-final/$Short/plans.json"
python reports/stage4-final/tools/judge.py plan --base aircargo --runs "$Private/runs" --data "$Data" --private "$Private/judge" --receipt $Receipt --v4-source "$V4" --old-m1 $Old
if ($LASTEXITCODE -ne 0) { throw "Plans refused" }
git add -- $Receipt
git commit -m "stage 4 final aircargo: freeze M1 and V4 bridge before grading"
```

All transfers are now finished. Item 7 may start with its exclusive-work declaration.
The following laptop commands are local; grade serially, export even if the request clock
has stopped a plan, and retain any NOT_EVIDENCE result:

```powershell
python reports/stage4-final/tools/judge.py grade --base aircargo --metric m1 --private "$Private/judge" --receipt $Receipt
python reports/stage4-final/tools/judge.py export --base aircargo --metric m1 --private "$Private/judge" --receipt $Receipt --runs "$Private/runs" --out "reports/stage4-final/$Short"
python reports/stage4-final/tools/judge.py grade --base aircargo --metric bridge --private "$Private/judge" --receipt $Receipt
python reports/stage4-final/tools/judge.py export --base aircargo --metric bridge --private "$Private/judge" --receipt $Receipt --out "reports/stage4-final/$Short"
python reports/stage4-final/tools/record.py quality --base aircargo --runs "$Private/runs" --data "$Data" --old-m1 $Old --new-m1 "reports/stage4-final/$Short/final-aircargo-m1.json" --bridge "reports/stage4-final/$Short/final-aircargo-bridge.json" --out "reports/stage4-final/$Short/quality.json"
```

## Records

Public: `reports/stage4-final/<stand-seven>/plans.json`, the M1 export with cases and the bridge stability export,
`quality.json`, and the text-free `final-answers.json` copied from the Mac. Raw prompts,
answers, V4 bridge inputs, replies, logs, runtime env and indices stay private. Failed runs
and stopped plans stay named NOT_EVIDENCE in the evidence record, never overwritten.
The orchestrator writes the evidence/status documents after the reading, not this tool.

The following SHA-256 list is checked by `test_forecasts_caps_and_fixed_pin_lists`.
- `reports/stage4-final/tools/api.py` `19bf92e667f46f7cb00e5f9b44242ece80f80a2ef976b9d58343ce9721aa781b`
- `reports/stage4-final/tools/baseline.py` `ca2f48009acb2da4c10bcf03f8f9c5aac273fe74e8e57246840eaa66f087b8f5`
- `reports/stage4-final/tools/common.py` `0bcf149b359b7db5e20c550a6c7107cd89d3b400453fb808f58ae70a2e1890ed`
- `reports/stage4-final/tools/judge.py` `8b96d7d3413cf7a5d978713046ff3620351647a058e00e2040beca31485cf336`
- `reports/stage4-final/tools/raise_stand.py` `caa1feec88202e6a1bc72af02fd1997a493ff9487a1eda9b844350acd7fff984`
- `reports/stage4-final/tools/record.py` `455f164a41bccb7a50d455c527de12e19d8224fc0cf51f8ff170b56afa4591ac`
- `reports/stage4-final/tools/run.py` `10d577f61df10b5cbc20edbcfb809301228f90a8c9eaab7801c0974fa479efb4`
- `reports/stage4-final/tools/runner.py` `ace524da530742672a9b03d6638cdc79032a6188fde1be40ba41160336a8bd62`
- `reports/stage4-final/tools/stand.py` `2887646363fe9be5b148d0abc378492d53f51c1f9ebef874dc76516955bea29d`
- `tests/test_stage4_final_tools.py` `5e13fac3b9f4162ffd4c409dacd0a830e0865ecf2a948750485d013e6fdbf246`

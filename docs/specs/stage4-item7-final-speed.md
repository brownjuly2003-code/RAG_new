# Stage 4, item 7: final-path speed on the idle Mac

Status: **registered before the run**, 2026-10-31, before the first request, with
[item 6](stage4-item6-final-aircargo.md) and the shared tools/tests, on the same stand commit.

A cold read (docs/operations/audit_opus55_31_10_26_stage4_items6_7.md) found 2 blocking, 5 should fix and 6 minor; each is applied (its Disposition says how).

## What is measured, stand and questions

PLAN §4.3 M5 and stage 4 item 7: the package's time to first word and whole answer, stage
timings, swap and llama-server memory on the production Mac (i5-7500, four cores, 8 GB).
This is a **separate idle run**. Item 6's incidental times cannot decide speed.

The stand, interpreter, offline snapshot, library checks, ONNX and cache digests, model
digest, effective defaults, corpus, index copy, observation API and refusal gates are
exactly item 6's. The model is the code-default `qwen3:4b-instruct-2507-q4_K_M`, Ollama 0.33.2;
V4, K 14 / window 3,584 / input 2,176 / ONNX INT8 / five / CPU / classic self-evaluation.
The fourth lever `cache-ram = 1024` is checked, never edited. No quality override comes
from the old runtime's `env.json`, including its qwen2.5:7b. The effective batch is 32 with
`RAG_RERANK_BATCH` unset. The loaded tokenizer and ONNX thread setting must match the receipt.

The **first 30** of aircargo's stage 2 order, `aircargo-probation-data` through
`aircargo-road-seal`, are the 30 of `19beeb1`'s idle rerun and item 5's `s5-30`. They run
consecutively on one fresh API, with no model resident before the run. After question 30,
only questions disturbed by foreign work may be re-asked once as specified below.
Preload is timed separately at the product's actual window: `options.num_ctx` comes from
the API settings, `/api/ps` must show 3,584, and the recorded llama-server pid must stay
the same in every memory reading and after the last question. A reload refuses. Question 1 is included in the distribution; no warm-up is discarded.
The run is `final-speed-aircargo-b01`. The same cases' histories are paired by id.

**Order:** finish item 6's answers first. Finish all laptop↔Mac copies/ssh first; then its M1 plus bridge judge runs on the laptop **in
parallel with this run on the Mac**. The stand remains the registering commit, even when
the laptop commits the frozen judge receipt. No tests, sync, retrieval replay or another
project's work may run on the Mac during this series. The launch records
`exclusive_owned_work: true`, backed by the required `--exclusive-owned-work` operator
declaration and process observations. This is not proof against an invisible short job.

## Idle protocol, run and readable floor

Before starting, the supervisor reads the Mac as item 5/5a did: 5-minute load below 2,
no model in `/api/ps`, no CI lock, no pytest, llama-server, replay, supervisor, ngram or VM
job. It reads command lines locally to find jobs; only pids go into the receipt. It never
prints environments/secrets or stops another project's job. If occupied, poll every 60 s,
logging each reading, for at most **30 min** (step 4b's bounded wait pattern). Still busy:
**do not start**, write only the sibling idle-wait log, read the cause and try later.
Taken ports refuse. At cleanup, request unload once and poll `/api/ps` and llama processes
until both are empty, bounded at 60 s and logged, then read idle-after. Our own asynchronous
unload never counts as foreign disturbance; an unload timeout is a cleanup failure.

Every roughly five seconds the frozen supervisor and step 0 sampler record monotonic/UTC
clocks, paging/swap, load, process RSS and llama-server footprint (top MEM). Commands may
take longer under load. The observer records all trace stage spans and the sent prompts.
The private raw files are kept. Sampling covers the first question through the last.

A question is **disturbed** only when its resource samples see a foreign job (the same
job detector as the idle check), a Python other than owned API/runner/supervisor at ≥512 MiB,
or qemu/limactl/virtualization. Process command lines stay private; only pids/reasons are
kept. Sampling uses flushed byte checkpoints before classifying an attempt. A changed or
absent preloaded llama-server pid, failed sampler/cleanup, a >30-s observation gap, reversed
clock order, or missing swap/footprint/RSS is **unreadable**, never a retry opportunity.
Thirty seconds admits a delayed five-second sample, not a blind minute. A foreign job in
the final idle-after check also makes the series NOT_EVIDENCE. Detectors cannot exclude
every short/small job; the operator prohibition on other work remains necessary.

The **readable floor remains 30/30**. After the first 30, re-ask each foreign-job-disturbed
question **once**, on the same API, in its original relative order. Replace its timing and
memory reading with the re-ask, retain both attempts (including their trace/prompt hashes)
and list replacements. **More than six** disturbed first-pass questions, **any question
disturbed twice**, a missing/out-of-order repeat or a broken path means **NOT_EVIDENCE**.
No slow clean question is repeated or dropped. This bounded repair suits the shared Mac:
foreign work disturbed two series three times in two hours on 2026-10-30. Selection is by
an **external criterion, never the timing outcome**, so it does not trim the observed tail.
A miss produces no SLO proposal; retain the series and read the cause before a new OUT.

## Forecast and stops

Use item 6's V4 measured tail (total median **296 s**, p90 **390 s**, max **581.6 s**):
first question 360 s, remaining 29 at 300 s, startup/preload 120 s = **9,180 s = 2.55 h**.
Reserve another six × 300 s for externally selected re-asks: the printed forecast is
**10,980 s = 3.05 Mac hours**, with stop **32,940 s = 9.15 h** at 3×, including idle wait.
Together with item 6: **42,780 s = 11.88 Mac hours** forecast, excluding copying, up to
5.5 h of bounded idle waiting, and failed reruns. The reserve is not a target retry count.
19beeb1's idle median was 320 s whole, 223 s first token, 102 s rerank; item 5's cap series
took 2.93 h. Disturbed item 5a times are not an idle baseline and component savings are
not added. PLAN's 150–200 s estimate is advisory against the measured tail.

Forecast: lower medians than 19beeb1, possibly detected, without a promise about p90 or SLO.
With 30 non-tied pairs the sign test first detects at **21 vs 9**, not 20 vs 10.
There is **no per-question stop below 3,600 s**; only that product ceiling and the remaining
series budget bound the request. Slow answers stay in the distribution. Startup cap 360 s,
preload 300 s. Path break stops before the next ask; `OUT/STOP` and owned-pid SIGTERM remain.
Ceiling/path/readability failures are NOT_EVIDENCE. A question's time never selects a retry.

## Reading and the proposal rule

The same frozen HTTP reader supplies `first_token_sec` (first SSE token, called “first
word”, as in 19beeb1) and `result_sec` (the complete answer/result with its quality result).
This does not claim a linguistic word boundary; a first token can be whitespace. Keep
`total_sec` through stream close too, printing its own median and p90 beside the primary times: suggestions can arrive after the result. Historical
printed “whole” medians used stream-close time; the **new paired comparison reads each
side's result_sec**, never compares it with a published total_sec median.

For both primary times, report the median and nearest-rank p90, each with a **95% exact
order-statistic interval**, Binomial(n,p), equal tails ≤0.025, no normal approximation.
Report ranks and actual coverage. Rank 0 / n+1 is unbounded and encoded null, not an
absent observation; ties make coverage conservative. At n=30 the p90 interval's upper
rank is 31, hence **no finite upper 95% limit**. The median point averages the middle two;
p90 is observation 27. Do not replace the unbounded limit with the sample maximum.

The comparison is **descriptive: the whole final path against 19beeb1's path**, including
V3→V4, the package, cache cap and intervening code (including suggestions after result).
It attributes nothing to one lever and decides nothing. Pair both times by question against `19beeb1`, label `qwen3-4b-instruct-q30-r2` only:
two-sided exact sign test, ties removed, `2 * BinomialCDF(min(faster,slower); n, 0.5)`
capped at 1, p < 0.05. Print faster/slower/ties/p and faster / slower / not detected,
separately for each metric; no pooled win claim or correction invented after seeing them.
Item 5's `s5-30` is a **descriptive** comparison of first/result medians on the same order,
not another gate. `baseline.py` extracts actual timestamps from the historic export or
private raw run and hashes its inputs; missing times refuse. `step5.json`'s totals cannot
be substituted for absent first/result timestamps.
The reader also requires both baseline extracts' question-file digests to match the run,
nonempty input receipts, and the registered corpus and copied-index provenance.

Per question keep the trace-stage seconds/timeline, stream/generate call timings, and the
median swap in use, llama-server RSS and footprint. They explain a timing; they do not
qualify an otherwise disturbed series. All 30 first/result times and these memory readings
stay in the public numeric record with provenance; raw texts, source names and logs do not.

**Proposal rule, written now:** independently for first word and complete answer, take the
observed p90 point and round **up to the next multiple of 30 seconds**, leaving exact
multiples unchanged (`ceil(p90 / 30) * 30`). Print these two second values as this session's
SLO proposal, beside the median/p90 intervals and sampling limits. This is an empirical
proposal, not a confidence guarantee or a production percentile promise. **Julia names the
SLO**. A proposal is never adopted automatically, and quality harm remains item 6's decision.

## Running it on the Mac

Start only after every item 6 transfer is complete, with no owned Mac job except this run.
Reuse item 6's stand; do not raise another or alter it. In zsh enter the same registering SHA:

```sh
read -r SHA
S=/Users/julia/RAG_new_chat_${SHA:0:7}
PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python
T=$S/reports/stage4-final/tools
DATA=/Users/julia/RAG_new_external_s1
cd "$S"
CLEAN=(/usr/bin/env -i HOME="$HOME" PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH="$S:/Users/julia/RAG_new_mf_gate_site" PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 RAG_RERANKER_ONNX=/Users/julia/RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx "$PY")
"${CLEAN[@]}" "$T/stand.py"
nohup "${CLEAN[@]}" -u "$T/run.py" speed --exclusive-owned-work --base aircargo --data "$DATA" --out "$S/final-speed" >> "$S/final-speed.out" 2>&1 </dev/null &
echo $! > "$S/final-speed.pid"
```

Read `final-speed.out`, `progress.log`, samples and `FINAL_DONE`; do not start a second
series while it lives. `touch "$S/final-speed/STOP"` stops before the next question.
After completion, on the Mac (restore the published 19beeb1 export if absent; do not guess):

```sh
"${CLEAN[@]}" "$T/baseline.py" 19beeb1 "$S/reports/chat-live-4b/19beeb1/runs.json" "$S/baseline-19beeb1.json"
"${CLEAN[@]}" "$T/baseline.py" item5 /Users/julia/RAG_new_chat_4f48fed/chatlive/runs/s5-30 "$S/baseline-item5.json"
"${CLEAN[@]}" "$T/record.py" speed --base aircargo --runs "$S/final-speed/final-speed-aircargo-b01" --data "$DATA" --baseline "$S/baseline-19beeb1.json" --item5 "$S/baseline-item5.json" --out "$S/final-speed.json"
```

The item 5 comparison may be omitted only if its private cases are unavailable: record the
gap explicitly and omit `--item5`, never fabricate its first/result medians. 19beeb1's
30 valid pairs are mandatory. Only **after item 7 exits**, on the laptop (same `$Sha` and `$Short` as item 6):

```powershell
scp "deproject-mac:/Users/julia/RAG_new_chat_$Short/final-speed.json" "reports/stage4-final/$Short/speed.json"
scp "deproject-mac:/Users/julia/RAG_new_chat_$Short/baseline-19beeb1.json" "reports/stage4-final/$Short/baseline-19beeb1.json"
scp "deproject-mac:/Users/julia/RAG_new_chat_$Short/baseline-item5.json" "reports/stage4-final/$Short/baseline-item5.json"
```

## Records

`reports/stage4-final/<stand-seven>/speed.json` holds the stand receipt, corpus/case/code
hashes, the exclusive-work declaration, baseline/sample/resource hashes, both attempts of
each re-ask and the selected 30, exact intervals/descriptive sign tests and
both SLO proposals. Keep the two numeric baseline extracts beside it; omit and explain
the optional item 5 one if unavailable. The raw run, before/after checks, stage log, samples,
memory, launch, prompts and answers stay on the Mac. The orchestrator records disturbed
and failed attempts as NOT_EVIDENCE and writes the evidence/status documents after review.

These tools are shared with item 6; this SHA list is checked by the same synthetic test.
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

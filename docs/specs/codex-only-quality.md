# Stage 6, item 0: quality under codex-only

Status: **registered before the first request**

## Why

Stage 5в ([spec](generator-ceiling.md), [record](../evidence/generator-ceiling-record.md))
measured GPT-6-Astra/xhigh on contexts selected by the 4B: 220/224 good in a fixed subset
(67 WixQA + 58 ConditionalQA sent gold + 99 aircargo package flags), 284/300 overall
(92 WixQA, 92 ConditionalQA, 100 aircargo). Both arms shared contexts; here contexts change.
M1 counts a faithful decline without the answer in context as good: a failed/malformed low
grade batch can leave zero documents and hide that loss. The primary below counts answered
good instead. The laptop uses Codex/low for query transformation and batched document grading.
Since task 18 (`6656251`), a Codex answer with context and no knowledge gap routes `auto`
under the handover line, with `quality_score=null`. This product path has not been measured.

## What is compared

One product answer versus stage 5в's Codex answer for each of its exact 300 questions:
100/key, identical ids, questions and input order. Apply stage 5в, §What is compared,
to package loaders; bind the old Codex side to
`reports/generator-ceiling/attempt-02/ceiling-<key>-judge-m1.{json,cases.jsonl}`.
Refuse any other set/order. Run the same pilot first, then traverse original order skipping
retained pilot cases. Pair by `(key, case_id)`; record both prompt hashes, which may differ.

## The arm

Use the owner's Windows laptop, real Codex CLI and signed-in profile `cw`. Pin one full
release commit containing task 18 and the Windows launcher. Each key gets a plain clone
at `<private>/stands/<key>/app`, detached at that commit, using the release's locked venv
and assets as [Windows service](../operations/windows-service.md). No measurement-specific
product changes; the tested deployment-helper extensions below must be in the pinned release.
`deploy/windows/start.py` requires `app` and fixes tracing at its parent: separate roots
give separate `traces.db` files without an unsupported env override.

Write each external UTF-8/LF, user-only-ACL env with `deploy/windows/write_env.py
--env-file <stand env> --tenant <index tenant> --chroma-dir <copied index>
--database codex_quality_<series>_<key> --codex-exe <CAPTURE_SHIM_EXE> --codex-home <cw home>`
(the helper accepts `[a-z0-9_]` only, so a series' `-` is written `_`: `attempt_01`).
The later task adds/tests `--tenant`, `--chroma-dir`, `--database`, preserving defaults;
`--codex-exe` already exists. Everything else is exactly what the writer supplies, validated
by `start.py`'s checks: profile, reranker, HF cache, JWT/session/encryption secrets and admin
credentials included. `--tenant` sets `ADMIN_DEFAULT_TENANT` to `ext_wixqa`,
`ext_conditionalqa` or `aircargo`; the authenticated admin JWT supplies that tenant.
Extend/test `deploy/windows/prepare_postgres.py --database NAME` (default `rag_new`
unchanged) to provision these distinct databases in the laptop's PostgreSQL 16 cluster.
Never use `rag_new`; refuse nonempty stores for a new series. Product `AUTO_MIGRATE` creates
their schema at first start. Credentials stay private.

Copy the complete, quiescent aircargo base, including `index/chroma` and sidecars, from
`D:/RAG_new_prod/data/aircargo/` to `<PRIVATE_DATA_ROOT>/aircargo/`. Copy complete, quiescent
WixQA/ConditionalQA folders from `/Users/julia/RAG_new_external_s1/<key>/` to
`<PRIVATE_DATA_ROOT>/<key>/`, including indexes.
Before any request verify corpus files against `corpus.manifest.json`, chunks/cases,
tenant, generation, embedding manifest and collection contents/counts against
`index/index-receipt.json` and stage 5 pins. Match a source-snapshot file/hash inventory
against the whole destination, including Chroma files, before opening the index. Later
admission checks logical content, allowing recorded runtime bookkeeping. Missing evidence/
mismatch refuses; never rebuild or substitute. Record pre/post inventories.
Apply the same verification to all three copies; no stand opens the product's writable
index. Base data stays outside the repository.

Stop the product launcher/API while a stand runs, retaining PostgreSQL; it may run between
sittings. One stand at a time owns `127.0.0.1:8002`. The driver launches
`<release venv python> -I <stand>/app/deploy/windows/start.py <ENV_FILE>`, cwd `<stand>/app`,
with `_support.detach`'s flags (no window, new process group, breakaway with its fallback),
and records launcher/child PIDs and creation times. Do not use `run_detached.py`, which
derives the venv from its root. Keep one stand per key up across that key's chunks within
a sitting; each chunk checks recorded PIDs and readiness first. Stop verified stand PIDs
before switching keys or returning the port to the product. Grading needs no stand.
Serial questions and the drain keep one live Codex call at a time; the shim journal proves
it (fast, strong and answer have separate semaphores). No warm-up request: flag the first
question after each stand start `cold`. No Ollama. Keep real defaults: answer
`gpt-6-astra/xhigh`, V4/3,584 window and identical stage 5в wrapper; auxiliaries `low`,
60 s timeout. Online judge, claim checks, suggestions and self-evaluation stay off.
Preserve routing/safety veto,
timeouts and outage cache; never force `auto`.

At offline registration read the release's effective settings and refuse unless every
`reports/stage4-final/tools/common.py` `SETTINGS` entry matches except the sole changed
key `llm_provider_profile=codex-only`. The profile's fast/strong provider/model/effort/timeout
and answer provider/model are resolved from `config/providers.yml`; record them and answer
effort/timeout from settings separately. Inactive `ollama_model_name` and
`streaming_self_eval_mode` still match; disabled online operations are profile behavior,
not extra setting exceptions. Record the graph's reachable call bound, including any loop.

Serially POST `{question: ...}` to `/api/ask/stream` as the chat does. Omit `session_id`
for a fresh session/question; tenant comes from authenticated identity. Privately retain
full SSE and final `result`: answer, route, sources/citations, session/trace ids,
provider/model and null quality score. Ticket ids/counts and delivery state come only from
each stand's database; `result` has no ticket_id or delivery_state. Do not click handover
or call `/api/escalate`; count actual tickets, including zero.

Capture at the process boundary. A native `.exe` shim forwards stdin bytes, argv, cwd,
environment, stdout and exit status unchanged to real Codex, staying inside the provider's
Windows Job Object. Adjacent private configuration names the real executable and capture
root: custom env variables do not survive the provider's allow-list. Read stdin to EOF,
persist it, durably write a start record, then spawn the real executable: the provider has
assigned the Job Object before sending stdin, so the child inherits it. A failed start-record
write exits 1 without calling Codex. Capture stdout durably as it arrives; write an end
record on exit. Journal calls, efforts/models, configured timeouts, PIDs/creation times,
timestamps, output/status and hashes. A durable active-case file and serial execution bind
calls to questions (the probe has its own id). An unbound/ambiguous call is a rule stop.
Identify the answer call by xhigh plus parsed V4; verify the wrapper,
unwrap only its fixed prefix/suffix. Count low calls too; retain the product acceptance gate.

## Pilot and stops

First, the data-free `Reply with exactly OK.` probe calls `CodexProvider` directly with
the stand's env (`CODEX_BINARY` is the shim); the API has no data-free route. Same CLI;
accept `OK` or `OK.` as stage 5в, §Pilot and stops, outside the 300. Use its exact 7/7/6
pilot ids/salt, cumulative steps **1, 5, 20**. Acceptance means an auditable API result;
`human` alone is not failure. Keep accepted pilot answers.

Fix forecast **60 s/question** from the two post-task-18 runs on 2026-11-03, 49.9 s and
55.0 s; 51.7 s predates task 18. All three ran one aircargo question; no pilot refitting.
At registration compute the per-question ceiling from the maximum reachable Codex calls
in `agent/graph.py` under the effective settings, summing each call's configured timeout
(transform, grade batch, answer, any loop), plus **120 s** for retrieval, rerank and stream.
Today: no classification/HyDE call or retry loop, at most two low calls and one answer,
so expect **60 + 60 + 180 + 120 = 420 s**, from POST dispatch. Never drop an unfinished
stream before that ceiling: disconnecting does not cancel the executor graph. Exceeding it
is a hung stand: infrastructure, stop its recorded PIDs and return code 5 immediately.

Print **180 s** (3x forecast) as the slow-answer threshold, with counts per key, not a stop.
The 3x request-clock stops stay **3,600 s pilot**, **50,400 s remaining** (54,000 s total).
Persist request time including failed attempts; startup, drain, pauses and grading are
separate. Admit only if the full ceiling also fits the remaining request clock; otherwise
fire the request-clock rule stop (code 2), never shorten the ceiling to fit. Product latency
runs from POST dispatch to final result.

Drain before the next question: every start has an end and no recorded shim/real-Codex
process for the stand is alive. Wait at most **60 s**; otherwise stop the recorded stand
PIDs, infrastructure/code 5. A killed shim cannot write its end: after classifying the
missing shim end below, the driver appends a separately labelled end proving verified
process exit, preserving the missing-end flag and never inventing stdout or exit status.
Two open call records at once mean overlapping Codex calls: attribution broken, rule/code 2.
Foreground default/max `--budget 1080`: admit only if
`elapsed + registered ceiling + 60 s drain <= budget`; stand startup is inside this budget.

Bind records before classification. A captured stdout usage-limit marker is infrastructure,
even behind HTTP 200 (the API's fixed failure text/null provider cannot identify it).
Otherwise a start without a shim end is the product's own timeout when the shim's last
1-s heartbeat (or start-record time if none) minus its process start reaches the configured
timeout minus 5 s, allowing for the provider's clock starting before slot wait/spawn and
the 1-s heartbeat period: terminal, bad without a judge request, printed as a product failure.
Any other missing end/record, nonzero exit, capture failure, non-200 or broken SSE is
infrastructure: leave the question pending, retain all attempts, report failures separately.
Three consecutive infrastructure failures across questions stop with code 5; the hung-stand
and drain stops above are immediate. After diagnosis, `run --resume-infrastructure` retries
pending questions; never replay terminal replies. A key with pending questions is not whole.
Persist the driver's own `retry_at=outage reply time + 300 s`, honoring it after restart;
the product's in-memory outage cache dies with its process.

Hold a Windows sleep-inhibition handle during each chunk; failure/suspend stops it. Keep
the laptop on mains with the lid open: the handle cannot prevent lid-close sleep. Detect
suspend by a wall-clock versus monotonic-clock gap.

Language test, all-20 pilot gate, counted-out limits (>15 overall or >5/key), >5 language
mismatches, preservation and amendment/new-series recovery are as stage 5в, §Pilot and
stops; exclude empty/counted-out answers from language mismatch counts. No measurement-side
answer redo. Poll the process list about every 2 s, with an initial snapshot per chunk;
no elevated WMI start trace. Record pre-existing `codex.exe` processes (other projects'
app-servers) without stopping them. Any new `codex.exe` outside the recorded stand tree is
a rule stop, as are wrong profile/effort, overlapping service or Ollama. Record Ollama
observations without killing by name. Restart cannot clear a stop; infrastructure recovery
requires the explicit resume above and fresh admission checks.

## Run folders and the judge

Freeze only a whole key. Adapt captures/API results to unchanged
`scripts/chat_answer_judge.py` run folders with the displayed answer and new documents.
An audited absence of an answer call (early handover or terminal product failure) has empty
sent context: its judge-only V4 frame contains the original question and `[]`, marked
derived, never captured.
A missing capture is not this case. Empty/counted-out answers and product timeouts are bad
without a judge request; infrastructure-pending cases cannot be frozen.

M1 on all 300, references withheld: salt `chat-answer-judge-2026-10-18`, instructions
SHA-256 `fd015e742c835a17b17704ad629df90a34a61ac600762e8c74e52aababdcc9c2`,
isolated `claude-opus-5-5`, effort `max`. Retest 15/key using the unchanged plan builder.
Bridge 15/key with stage 5в's **Codex M1 retested originals**, old contexts/answers and
vouched original verdicts, using `reports/answer-prompt-v4/tools/bridge_plan.py`.
Do not reuse its package-answer bridge or generate answers again.

Before the first M1 request, probe the judge route with the installed Claude CLI and record
its version (stage 5в used 2.1.312). Refusal of every reply is infrastructure: diagnose the
route before grading, not an answer-quality verdict.

Freeze/receipts, commit-before-grade, route admission, six-reply cap, stability, judge
clocks/backoff and `--budget 600` are as stage 5в, §Run folders and the judge. Stability:
at least 12 usable pairs and quadratic kappa >=0.6, or agreement >=13/15 without two-step
disagreement. Any unstable/stopped plan or bridge blocks further requests.
**M2 is not measured: cost.**

| Work | New calls/requests | Forecast USD | Forecast seconds |
| --- | ---: | ---: | ---: |
| Product, 300 questions | up to 300 xhigh + observed low calls (nominal 600) | subscription; no per-request price | 18,000 |
| M1, 3 x (100 + 15 retests) | 345 | 61.24–97.77 | 32,085–44,850 |
| Bridges, 3 x 15 | 45 | 7.99–12.75 | 4,185–5,850 |
| Total judge | **390** | **69.23–110.53** | **36,270–50,700** |

V6's $0.1775–0.2834 and 93–130 s/request, reused by stage 5в, give totals before rounding. Combined:
**54,270–68,700 s (15.08–19.08 h), $69.23–110.53 judge spend plus the subscription**.
Probe/setup/retries/pauses are extra; frozen eligible counts exclude empties. Record actuals.

## The reading

**R, second deciding reading**, no judge: apply
`reports/stage4-final/tools/external/sent_gold.py`, `SentGold.saved_point`, on both sides:
product captured contexts and stage 5's saved package prompts. At offline registration,
before any request, it must reproduce `record.json`'s `corpora.<key>.sent_cases` case for
case (gold/hit/fraction and ids), including **67/100 WixQA**, **58/80 answerable ConditionalQA**;
otherwise refuse (code 1). Save the instrument gate receipt and both input hashes.
Stage 5 used `SentGold.run/one` replay; matching totals alone does not pass this gate.
WixQA credits gold articles; ConditionalQA uses `evaluation/external_gold.py` range
coverage, not string hits. Empty context means hit=0 for gold-bearing cases; no-gold stays
null. Unresolved placements fail the instrument
gate; never silently drop them. Pool **180 gold-bearing questions (100 + 80)**, paired by
`(key, case_id)`, product minus stage 5 package contexts; print both sides, hit transitions,
differences/read95, pooled and per key. ConditionalQA's other 20 are outside R's denominator.
For aircargo print exact equality of document source-id sets against saved package
prompts, out of 100 (ignore order/duplicates; hash names publicly). This measures document
identity, not passage equality/gold coverage. Missing evidence is never empty context.

**Q primary, answered good:** M1 `good` **and** `context_has_answer=true`, pooled over
**all 300**, product minus stage 5в's Codex arm, paired by `(key, case_id)`. Compute the old
side by the same rule from its own `ceiling-<key>-judge-m1.cases.jsonl` verdicts and write
per-case flags and per-key/pooled counts into the registration receipt before the first
request; never hard-code the baseline or reuse stage 5в's fixed 224-case subset. Print both
Q counts/shares, pooled and per key, and the pooled difference/read95. Terminal bad/count-outs
contribute zero; pending questions invalidate the reading, never shrink the denominator.
For both Q and pooled R, as stage 5в, §The reading: paired Newcombe method-10 and
cluster-bootstrap 95% intervals, **10,000** resamples, seed **20261001**; frozen
`evaluation/external_parts.py` clusters prefixed by key, singleton aircargo cases for Q;
R retains the external clusters
on its gold-bearing cases. A fall in either reading is detected only when both of its
upper endpoints are below zero; read95 is their envelope. First applicable row decides:

| Row | Outcome | Condition / next step |
| --- | --- | --- |
| 1 | NOT_EVIDENCE | Key not whole; rule/time stop fired or infrastructure stop unresolved; required plan/bridge missing, unstable or stopped; input hash/receipt refused; R instrument gate failed. Diagnose; rule changes require amendment before new requests; infrastructure recovery follows the explicit resume rule. |
| 2 | below stage 5в's Codex reading | Detected fall in Q or R. If R fell, re-measure context selection (query transform and document grade at low) at higher effort or off in a new registration. Otherwise diagnose the answer path (release code, exec flags, Windows numerics) before any new registration. |
| 3 | holds (no detected fall) | Evidence counts; neither Q nor R fell. Publish these numbers as product quality under codex-only. |

Printed, deciding nothing: per-key/pooled M1 good of any kind (declines included)/partial_ok/bad
on both sides; route counts (auto/human, others separately); M1 bad / all auto per key
and pooled (zero denominator undefined; acceptance share belongs to the owner, PLAN stage 6);
actual tickets; aircargo
document identity; laptop latency median/p90 (nearest rank) with and without cold questions,
per-key counts over 180 s; infrastructure attempts/pending cases and product failures
separately; calls/question by effort; language mismatches; Ollama observations (required
zero); retests/bridges and stop reasons.

Limits: in-sample; one unseeded generation per side; one judge, no human grades (D11).
Context selection and run-to-run generation both change; so do release code since the
stage 5 stands (`2057ad0`, `138f3b3`), Windows ONNX Runtime/embedding numerics versus the
pinned Mac stand (`common.SETTINGS`, `stand.py`), and `codex exec --ignore-user-config
--ignore-rules` with `flatten_messages`' `USER:` framing versus stage 5в's companion `task`.
Neither deciding reading isolates the auxiliaries' causal effect. Overall M1 can reward a
supported decline; answered good and R expose different losses. M2 is absent.
The owner's laptop runs under her load. This is product latency, unlike stage 5в task time.
“No detected fall” does not establish equivalence.

## Records, tools and data

Public `reports/codex-only-quality/<series>/`: registration/copy receipts, arm summaries,
`plans-<key>.json`, M1 JSON/cases JSONL, bridges and `reading.json`. No-prose guard, private
path hashing, schema and partial-freeze rules are as stage 5в, §Records and data. Raw data,
credentials and journals stay under the argument-supplied private root. Publish session/
ticket ids as hashes; keep question case ids. Implement the four measurement tools later
under `reports/codex-only-quality/tools/`, plus the deployment-helper changes at their paths:

| Tool | Arguments and contract |
| --- | --- |
| `copy_verify.py` | `--config FILE --out FILE`: offline copy/index admission, hash-only receipt; no rebuild. |
| `capture_shim.exe` | `--configure --real-exe ABS --capture-root ABS`: adjacent config. Normal mode accepts unmodified provider `exec ... -` argv/stdin. |
| `quality_driver.py` | `register\|probe\|pilot\|run\|freeze\|grade\|export`; common `--config FILE --private DIR --series ID --records DIR`; `pilot --step 1\|5\|20`; `run\|freeze\|grade\|export --key KEY`; `run --resume-infrastructure`; request modes `--budget SECONDS` (product default/max 1080, grade 600). Offline settings/call-bound/Q-baseline/R-gate registration; durable state/backoff, stand lifecycle, capture correlation, freeze/grade/export. |
| `quality_read.py` | Same four common arguments; offline R/Q and reading, including stopped/incomplete runs. |
| `deploy/windows/write_env.py` | Extend with `--tenant`, `--chroma-dir`, `--database`; existing `--env-file` and `--codex-exe` select stand env/shim. Tests; unchanged defaults, full env validation and user-only ACL. |
| `deploy/windows/prepare_postgres.py` | Add/test `--database NAME`, default `rag_new` unchanged; provision the named isolated database without changing the shared cluster's default. |

Private config binds release SHA, per-key clone/env/index/database/tenant/auth-file paths,
venv/assets, CLI/shim/cw home, source inventories, stage 5/item 6 packages, stage 5в
attempt-02 runs/judge journals, R gate's saved prompts/sent_cases/gold-placement inputs,
public inputs and copy receipt. No baked-in private paths.
Imports/offline modes issue no requests. Codes as stage 5в: 0 complete, 1 refusal,
2 rule stop, 3 budget/backoff, 5 infrastructure stop. Driver code 1 is reserved for
preconditions before requests; runtime capture failure is infrastructure. Shim setup uses
0/1; normal mode forwards the real exit (local capture failure: 1). Reader: 2 for a blocking
stop in row 1, otherwise 0; explicitly NOT_EVIDENCE for refused/incomplete evidence,
as stage 5в. Retained, resolved infrastructure stops do not disqualify a completed key.

## Running it

Future orchestrator commands only. Prepare private copies, pinned releases/envs and
isolated databases; stop the product API, keep its cluster, verify the free port.
Populate the private config with the paths above. The repository's Codex executor shares
profile cw's `CODEX_HOME`: during chunks run no executor, second-opinion or other Codex task
of this repository. Existing other-project app-servers are only recorded; newly started
outside-tree `codex.exe` processes stop the chunk. Keep mains connected and the lid open.

```powershell
$py = '<RELEASE_VENV_PYTHON>'
$tools = 'reports/codex-only-quality/tools'
$config = '<PRIVATE_CONFIG_JSON>'
$private = '<PRIVATE_ROOT>'
$a = @('--config', $config, '--private', $private, '--series', 'attempt-02', '--records', 'reports/codex-only-quality')
& $py "$tools/copy_verify.py" --config $config --out '<PRIVATE_COPY_RECEIPT_JSON>'
& '<CAPTURE_SHIM_EXE>' --configure --real-exe '<REAL_CODEX_EXE>' --capture-root '<PRIVATE_CAPTURE_ROOT>'
& $py "$tools/quality_driver.py" register @a
```

Fill hashes, set status to **registered before the first request**, review and commit
spec/tools/tests and hash-only registration before the probe, as stage 5в, §Running it.
Rerun offline registration after finalizing the spec, so its receipt binds the final bytes.

```powershell
& $py "$tools/quality_driver.py" probe @a --budget 1080
& $py "$tools/quality_driver.py" pilot @a --step 1 --budget 1080
& $py "$tools/quality_driver.py" pilot @a --step 5 --budget 1080
& $py "$tools/quality_driver.py" pilot @a --step 20 --budget 1080
```

Read each gate before advancing. For `wixqa`, then `conditionalqa`, then `aircargo`:

```powershell
$key = 'wixqa'
& $py "$tools/quality_driver.py" run @a --key $key --budget 1080
& $py "$tools/quality_driver.py" freeze @a --key $key
```

Repeat chunks only on code 3, honoring backoff. Review/commit `plans-<key>.json` before
grading; codes 1/2/5 require diagnosis, never blind retry. After infrastructure diagnosis,
use `run @a --key $key --resume-infrastructure --budget 1080` to retry pending questions,
including pending pilot cases; the all-20 gate still precedes non-pilot requests. Retain
the stop/diagnosis/resume history; an authorized resume resolves only infrastructure stops.
Product service may run between sittings; stop stands before returning its port.

```powershell
& $py "$tools/quality_driver.py" grade @a --key $key --budget 600
& $py "$tools/quality_driver.py" export @a --key $key
```

After all keys, or a stop:

```powershell
& $py "$tools/quality_read.py" @a
```

## SHA-256 registration

Registered offline on 2026-11-04 as series `attempt-02`: every entry below is expanded to
individual files and their SHA-256 in
[`registration.json`](../../reports/codex-only-quality/attempt-02/registration.json)
(149 public files; release `19ecbbb7489f83121dbc3c817ee948a6115bed7d`, tree
`841d85483016b8348c64f96b7405df3f97b1ebfd`, 2,373 files; private config, copy receipt,
environment, shim, CLIs and stand env files by hash only). Missing files refuse. Recheck
committed bytes before every request, as stage 5в; amendments precede requests. The
receipt binds the final spec without a self-hash. The measurement tools at registration:

- `reports/codex-only-quality/tools/copy_verify.py` `82c78014658226b3acf607c593546ee54f6e89ea4026909fdaeea6b1a84cd1fd`
- `reports/codex-only-quality/tools/quality_driver.py` `7e153606f075d64936d4eb5006dbabcb24e958fcfdc13dd273d7c83c9eb5e66a`
- `reports/codex-only-quality/tools/quality_freeze.py` `c155cfebe0f7571f9070587be3838b3fc396862a14ce4206e10ac14f24d4d9a2`
- `reports/codex-only-quality/tools/quality_read.py` `f6aa36fd05c5a4626b0edbfbc093285e66f6b4ad9a15f6d901e0162092d46185`
- `reports/codex-only-quality/tools/stand_runtime.py` `640127cad83b72d302dda20d14f0b6765849696361b3a402b35e87b12088fccf`
- `reports/codex-only-quality/tools/capture_journal.py` `f0e79e4a9038e27eae1d02cf2bf301f6ce48a958918dd6fdfc3453624ae7a4bc`
- `reports/codex-only-quality/tools/shim/CaptureShim.cs` `70d7353fc8df48a431a984946bcfc316578e2fcc353d8a51e68e01ab64943646`
- `deploy/windows/write_env.py` `2ee6503f77f6a44ded23fdd5dcb8fb488032bf4bde9d764e6866bc54836e13e7`
- `deploy/windows/prepare_postgres.py` `cd11345be50bc72a97fa3800976ec4eb0b3229c2a5457aca3fde59d3fbf49e64`

The receipt's Q baseline, stage 5в's Codex arm by the rule above: answered good **268/300**
(WixQA 87, ConditionalQA 81, aircargo 100). The R instrument gate reproduced `sent_cases`
case for case: passed, **125/180** gold-bearing hits pooled.

Amendment, 2026-11-04, before any `attempt-02` request. Series
[`attempt-01`](../../reports/codex-only-quality/attempt-01/) is retained and stopped (code 5,
unresolved). Its probe and 11 of 20 pilot questions were accepted. Its process watch then refused
twice with `python_command_unreadable`: a concurrent session's short-lived python exited between
`OpenProcess` and the command-line read. The first refusal came during stand startup; the second
came mid-question and stopped the stand. `stand_runtime.py` now skips a python that has really
exited and still refuses a live unreadable one (`559a54c`). Its Windows stress test gave 708
refusals in 4,679 snapshots before the fix and 0 in 5,003 after. A changed registered file needs a
new series, so `attempt-02` has its own databases, stand env files, config and copy receipt. Its
base copies' `chroma.sqlite3` were restored to the admitted source bytes first, because each Chroma
open rewrites bookkeeping. The registration differs from `attempt-01`'s only in that tool, its test,
the three env files and those private bindings. Between chunks, the operator stops a kept stand
with the driver's own `Runtime.stop`, under the series lock. A live stand left the laptop short of
memory, and the next admission took 23 minutes instead of about 5. The next chunk starts a fresh
stand and records its first question `cold`.

- This spec; stage 5в spec/record; every public input/instrument in stage 5в,
  §SHA-256 registration (historical pins still checked).
- `reports/codex-only-quality/tools/copy_verify.py`, `quality_driver.py`, `quality_read.py`,
  shim source/build recipe/executable and tests (exact source/test paths at implementation).
- Extended `deploy/windows/write_env.py`, `deploy/windows/prepare_postgres.py`, their tests,
  `deploy/windows/_support.py`; helper verification receipts and unchanged-default checks.
- `reports/generator-ceiling/attempt-02/reading.json`, `plans-<key>.json`,
  `ceiling-<key>-judge-m1.json` and `.cases.jsonl`, all keys; private source runs,
  plans/verdict journals and bridge seeds by hash.
- R gate: `reports/stage4-final/stage5/2057ad0/record.json` (`corpora.<key>.sent_cases`),
  `stage5-<key>-m1.cases.jsonl`, both external keys' saved package prompt/launch files and
  hashes, cases/gold references, `chunks.json.gz`, source/corpus manifests and placement
  inputs. Record casewise reproduced readings and gate result, not just 67/58 totals.
- `reports/stage4-final/tools/external/sent_gold.py`; `evaluation/external_gold.py`,
  `external_parts.py`, `external_parts.json`, `power.py`; loaded dependencies, including
  `scripts/external_base.py`, `scripts/external_pilot.py` and corpus manifests;
  `reports/stage4-final/tools/common.py`, `stand.py`, `external/reading.py`.
- Full release tree/commit; `config/providers.yml`, `config/settings.py`,
  `llm/providers/codex.py`, `llm/providers/runtime.py`, `llm/codex_wrapper.txt`,
  `agent/graph.py`, `agent/doc_grade.py`,
  `agent/graph_stream.py`, `agent/prompts.py`, `api/routers/conversation.py`, `static/chat.inline.js`,
  `api/routers/session_auth.py`, `deploy/windows/start.py`, `deploy/macos/start.py`, Windows
  lock and operations runbook. Receipt: effective settings/diff against `common.SETTINGS`,
  resolved calls/timeouts and graph-bound derivation/ceiling, per-case Q baseline and totals.
- Private config/env/copy inventories, corpus/index/embedding receipts, real CLI
  executable/version, shim config and installed environment/assets; installed Claude CLI
  executable/version. Judge-route admission is a later receipt, required before the first
  M1 request, not an input to offline registration. Record profile cw's
  AGENTS hash per chunk as stage 5в; never publish credentials or standalone secret hashes.

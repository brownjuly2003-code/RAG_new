# Stage 5v: the generator's ceiling

Status: **registered before the first request**

## Why

How many good answers does the production generator lose on the context it actually received?
PLAN.md, “Этап 5в. Потолок генератора”, and its 2026-11-02 §8.1 decision fix this diagnosis.
`reports/stage4-final/stage5/2057ad0/record.json`, `corpora.<key>.sent_cases`, records gold
in the sent context for 67/100 WixQA and 58/80 answerable ConditionalQA questions. Item 6's
`reports/stage4-final/138f3b3/final-aircargo-m1.cases.jsonl` records an answer in 99/100
contexts. The package M1 exports (stage 5's `stage5-<key>-m1.cases.jsonl` for the external
keys and item 6's export for aircargo) have only 30, 38 and 73 good answers of 100. This measures
the generator's share of the losses, separately from retrieval. It is not a product candidate.

## What is compared

The package's Qwen3-4B, prompt V4, versus one GPT-6-Astra answer to each of the **same 300
saved prompts**, byte for byte inside the wrapper. WixQA and ConditionalQA come from stage
5 (`2057ad0`); aircargo from item 6 (`138f3b3`). Each key has ten complete batches of ten,
`runs/final-answers-<key>-b01..b10/`. The loaders check stand prefix, model/digest, batch
completeness, case order against launch.json, QA_PROMPT_V4, UTF-8/LF, prompt SHA-256 and the
package M1's exact 100 ids and hashes. Paths are arguments, never private path constants.

## The arm

One fresh companion task per question, serially: `node <companion> task --model gpt-6-astra
--effort xhigh --cwd <empty-dir> --prompt-file <sibling-file>`. No write or resume flag.
The runner supplies profile cw's CODEX_HOME, unsets CODEX_COMPANION_APP_SERVER_ENDPOINT,
and sets CLAUDE_PLUGIN_DATA to the supplied private state directory. Every attempt gets a
new empty cwd; its request is in a sibling directory. The wrapper is
`reports/generator-ceiling/tools/wrapper.txt`; its SHA-256 is **583b49ac747123ce24e17d200f3deb70c82117f9f0e295c1dc6db3df311086af**, completed
with the registration list below. Only its literal `{prompt}` is replaced, with saved bytes.
The registered wrapper explicitly makes the question's language override the profile's Russian
reply instruction. Each chunk records CODEX_HOME/AGENTS.md's hash; a change is printed, not a stop.

The rollout found by the job's threadId must have exactly one turn_context (gpt-6-astra,
xhigh, read-only, the attempt's cwd), matching session_meta, a token_count with total_token_usage,
and exactly one nonempty final_answer assistant message containing output_text. That message
is the answer. Record rawOutput's hash and mismatch count; a mismatch is not a gate.

`ceiling_route.ALLOW` is the single registered, closed allow-list: top-level session_meta,
turn_context, world_state, token_usage_record, response_item and event_msg; response kinds
message (developer/user/assistant), reasoning, additional_tools; event kinds task_started,
task_complete, token_count, thread_settings_applied, item_completed; completed item types
UserMessage, AgentMessage, Reasoning. Everything else fails, including calls/outputs,
CommandExecution, SubAgentActivity and inter_agent_communication_metadata. An extension is
an amendment. Gate failure allows one fresh-cwd redo; a second failure counts the question
out. It stays in the denominator as bad, with no judge request. Terminal cases are never
regenerated, including after restart.

Nonzero companion exit, absent job/rollout, usage-limit/network failure or task timeout is
infrastructure, not a route redo. Three consecutive infrastructure failures across questions
stop the driver with code 5 for diagnosis; a later explicitly resumed attempt may retry.
All attempts remain: cwd, job/thread ids, rollout filename/hash/private copy, gate, elapsed
time, task_complete duration_ms/time_to_first_token_ms, and the last non-null total_token_usage.
Read an unfinished rollout up to five times over ten seconds; a truncated last line or missing
task_complete that persists is infrastructure, never a route redo. Transport message patterns
are consulted only after structured completion/exit status has failed. Recovery without a
durable transport.json is infrastructure with no inferred task timeout or measured task time.
After each task, stop only roots whose command line contains that unique cwd and descendants
created no earlier than their parent. Verify process creation time again before terminating
its handle at the common precision derived from CIM's DMTF fraction and native FILETIME.
Record the number stopped; never use taskkill /T. A second snapshot must contain neither
a process naming cwd nor a creation-matching member of the built tree. Survivors set
cleanup_failed and retain the tree for cleanup_pending; unresolved cleanup blocks launches.

Count Latin/Cyrillic letters by Unicode name in the saved prompt's parsed question and the
answer. Majority scripts must match; a tie or no letters fails. Keep and grade a language
mismatch without redo. More than five among 300 stops the arm as NOT_EVIDENCE.

## Pilot and stops

Before corpus requests, run the data-free probe `Reply with exactly OK.` through the same
client and gate. The route gate must pass and the answer, stripped of surrounding whitespace
and with one trailing period removed, must equal `OK` (`OK` and `OK.` pass). Report it
separately from the 300.
The pilot selects 7 WixQA, 7 ConditionalQA, 6 aircargo ids by ascending SHA-256 of
`generator-ceiling-2026-11-02:pilot:<key>:<case_id>` (id breaks a tie), in that key order.
Run cumulative steps **1, 5, 20**, reading gates after each: one, four more, fifteen more.
Forecast **180 s/task**, stop **540 s/task**; each attempt's launch.json durably names its
forecast before launch. All 20 must be accepted, match language, and have no time stop.

After a pass, keep the pilot's answers. Forecast for the remaining 280 is the pilot task-time
p90 (nearest rank, all attempts included), rounded upward to 30 s, at least 60 s. Per-task stop
is three times this forecast; the remaining series' request clock stops at `3 × 280 × forecast`.
The task timeout is also bounded by that clock's remaining allowance. Continue WixQA,
ConditionalQA, aircargo. Stop at more than 15 counted out overall or more than five in a key,
or more than five language mismatches. A failed pilot stops everything: diagnose, commit an
amendment before further corpus requests, and repeat the same 20 in a new private series and
new public records subdirectory. Preserve earlier attempts; none count in the amended series.

Foreground chunks default to `--budget 840`: no new task after the budget, and reserve enough
time for its full ceiling and cleanup within a call under 1,200 s. Codes: 0 completed step/key,
3 budget/backoff reached, 2 rule stop, 5 infrastructure stop, 1 refusal. One status line, no
request/reply text. If the pilot's p90 exceeds 360 s, the driver refuses further launches:
continuing needs a registered amendment permitting a single-task call outside the foreground
cap, with its full per-task ceiling and cleanup allowance. Nothing else changes.

## Run folders and the judge

Privately copy launch.json, stream prompt files and cases/*.json from each package batch.
Change only the case's answer and its result event's answer. Counted-out answers are empty.
Routing, sources and citations remain the package's; the reading never interprets the arm's
route. The unchanged run_answers must return identical prompt filenames and hashes.

Use unchanged scripts/chat_answer_judge.py, salt `chat-answer-judge-2026-10-18`, instructions
SHA-256 `fd015e742c835a17b17704ad629df90a34a61ac600762e8c74e52aababdcc9c2`, isolated
claude-opus-5-5, effort max, CLI admission and six-reply form cap. Freeze a key only after its
100 answers are terminal. Build in `<key>.partial`, publish the hash-only receipt, rename last.
Commit `plans-<key>.json` before that key's first grade. Grading requires the receipt, spec and
registered tools unchanged in HEAD, and rechecks private/input hashes. No pilot-only grading.

| Plans | Originals + retests | New requests | Forecast USD | Forecast seconds |
| --- | ---: | ---: | ---: | ---: |
| ceiling-wixqa-judge-m1 | 100 + 15 | 115 | 20.41–32.59 | 10,695–14,950 |
| ceiling-conditionalqa-judge-m1 | 100 + 15 | 115 | 20.41–32.59 | 10,695–14,950 |
| ceiling-aircargo-judge-m1 | 100 + 15 | 115 | 20.41–32.59 | 10,695–14,950 |
| ceiling-wixqa-judge-m2 | 100 + 15 | 115 | 20.41–32.59 | 10,695–14,950 |
| ceiling-conditionalqa-judge-m2 | 100 + 15 | 115 | 20.41–32.59 | 10,695–14,950 |
| ceiling-bridge-<key>, each of three keys | 15 saved + 15 new | 15 | 2.66–4.25 | 1,395–1,950 |
| Total, no empty answers | | **620** | **110.05–175.71** | **57,660–80,600** |

M1 withholds references; M2 uses stage 5's references/<key>.jsonl, including ConditionalQA's
20 unanswerable questions. Bridges use bridge_plan.py to cut the package M1's 15 retested
originals and re-grade them now. Forecasts derive from V6's $0.1775–0.2834 and 93–130 s/request;
620 = 5 × 115 + 3 × 15, or 16.02–22.39 hours. Actual frozen eligible counts exclude empties;
each plan's request-clock stop is `3 × frozen eligible requests × 130 s`
(44,850 s for 115, retests included; 5,850 s for a 15-request bridge).
Stability is unchanged stage 2: at least 12 usable pairs and quadratic kappa ≥0.6, or
agreement ≥13/15 with no two-step disagreement. Any required unstable/stopped plan or bridge
is NOT_EVIDENCE and blocks subsequent requests. Grading resumes from verdicts in foreground
chunks with default and maximum `--budget 600`: no new request starts at or after 600 s.
Each request has timeout `min(route timeout, 1140 - elapsed)`; with the unchanged 1,200 s
route timeout, even a request started just before the budget has at least 540 s, leaving
60 s for return within the 1,200 s foreground cap. Unavailable attempts are separated by a
persisted 300 s retry_at; seven consecutive
failures return code 5. Restart never bypasses the remaining backoff.

## The reading

Pair exact case ids and prompt hashes with the committed package exports pinned below.
Strata are fixed before Codex: `reports/stage4-final/stage5/2057ad0/record.json`,
`corpora.<key>.sent_cases`, uses gold=true/hit=1
for “answer in context”, gold=true/hit=0 for “not in context”, gold=false for “no gold”.
Air cargo uses the package M1 context_has_answer flag (item 6's registered M3 instrument).

| Key | Answer in context | Not in context | No gold | Package good within answer-in-context |
| --- | ---: | ---: | ---: | ---: |
| WixQA | 67 | 33 | 0 | 19 |
| ConditionalQA | 58 | 22 | 20 | 28 |
| aircargo | 99 | 1 | 0 | 73 |
| Total | **224** | **56** | **20** | **120** |

These counts come from that stage 5 record and the package M1 exports:
`reports/stage4-final/stage5/2057ad0/stage5-<key>-m1.cases.jsonl` for WixQA/ConditionalQA and
`reports/stage4-final/138f3b3/final-aircargo-m1.cases.jsonl` for aircargo. The tool derives them
and refuses different strata or primary n. Primary: pooled M1 **good** share within
“answer in context”, n=67+58+99=224.
Differences are Codex minus package. Reuse V5/V6's paired Newcombe method-10 95% interval and
cluster-bootstrap 95% interval, seed 20261001, 10,000 resamples. External clusters are the
evaluation/external_parts.py-derived clusters pinned in references/exports, prefixed by base;
every aircargo question has its own cluster. Detected means both intervals exclude zero on
the same side; read95 is their envelope. The first applicable row decides:

| Row | Outcome | Condition | Next step (from PLAN 5v item 4) |
| --- | --- | --- | --- |
| 1 | NOT_EVIDENCE | a key not answered whole; an arm stop (D4-D6) fired; a required plan or bridge missing, unstable or stopped; a receipt or input hash refused | the session reports it; an amendment before any new request; only what it names is redone |
| 2 | the generator is the bottleneck | the primary share rises with Codex, detected | a strong model for the product; the host (GPU or an API instead of the Mac, decision D5) is the owner's; production stays the 4B on the Mac until her word |
| 3 | the generator is not shown to be the bottleneck - retrieval next | all evidence counts and the rise is not detected | the next quality step is retrieval |

Printed, deciding nothing: per-key/per-stratum M1 good/bad on both sides, differences/read95/
detection; M2 agrees on 180=100+80 reference-bearing questions, pooled, by key and by stratum;
ConditionalQA's right declines on its 20 unanswerable questions; answers_question, supported/
total claims, defects, listed/unlisted citation marks. For each package not-good answer, count
exactly one: generator loss (in context, Codex good), retrieval loss (not in context/no gold,
Codex not good), neither (in context, Codex not good), Codex good without gold in context
(printed without explanation). Also print retained package good answers and package good
answers Codex lost; all bridges/retests; attempts, redos, counted out, infrastructure/language/
rawOutput failures, AGENTS hashes, task median/p90 and input/cached/output/reasoning tokens.
No arm price: the ChatGPT plan has no per-request price. reading.json contains counts and ids,
with hashes and provenance metadata, never corpus prose. Exit 2 for row 1 when a stop fired,
otherwise 0; incomplete/refused evidence still explicitly says NOT_EVIDENCE.

Limits: in-sample; one unseeded generation per side; one judge, claude-opus-5-5, no human
grades (owner D11). Judge and arm have different vendors, but the judge's family is the
orchestrator's (D12). Codex time/tokens are not product latency/cost. Training knowledge of
products such as Wix may help: M1 penalizes unsupported claims, M2 agreement may not, so
unsupported-claim defects accompany M2. Aircargo's stratum is a judge flag; external strata
are gold labels. V6's approximate detectable difference is `2.8 × sqrt(d / 224)`, where d is
the discordant fraction: about 5.9, 8.4, 10.2 percentage points at d=0.1, 0.2, 0.3. Clustering
can widen the interval. “Not detected” is not “no difference”.

## Records and data

Private root is an argument: requests, attempts, rollout copies, arm runs, judge folders,
raw diagnostics and immutable per-key measurements. Public reports/generator-ceiling holds
arm summaries (ids, status, attempts/gates, language, time/tokens, hashes), receipts, metric
JSON/cases JSONL exports, bridges and reading.json. Public writers recursively refuse string
values named question, answer, text, content, prompt or document, and non-enum reference
values. Frozen exports' aggregate reference maps become reference_counts; historical reading
prose and private path values become hashes. Metric case rows retain stage 5's schema.
The receipt binds spec/tools/wrapper, every plan, private files by hash, package exports,
references and bridge seed. Incomplete partial freezes are retained for diagnosis.
Only the orchestrator runs private-data commands and network calls; imports/tests do neither.

## Running it

PowerShell, from the reviewed repository. Replace placeholders; CODEX_HOME must be profile cw's.
The commands are instructions for the orchestrator, not actions performed while writing this task.

First copy item 6's git-ignored `runs/` and `judge/` folders byte for byte to a fresh directory
outside the repository, for example `D:/RAG_new_stage4_private/138f3b3`. `<I6>` means this
outside copy. Keep V6's outside-repository gate. The package loader checks prompt hashes
against the committed M1 cases export; freeze's source_gate checks plan and verdict hashes
against the committed M1 export. A changed copy refuses admission.

```powershell
$item6Source = '<ITEM6_GIT_IGNORED_SOURCE>'
$item6Copy = '<I6_OUTSIDE_REPOSITORY>'
if (Test-Path -LiteralPath $item6Copy) { throw 'Fresh item-6 copy required' }
New-Item -ItemType Directory -Path $item6Copy -ErrorAction Stop
Copy-Item -LiteralPath "$item6Source/runs" -Destination $item6Copy -Recurse -ErrorAction Stop
Copy-Item -LiteralPath "$item6Source/judge" -Destination $item6Copy -Recurse -ErrorAction Stop
```

```powershell
$py = '<PYTHON>'
$tools = 'reports/generator-ceiling/tools'
$private = '<PRIVATE_ROOT>'
$s5 = '<S5>'
$i6 = $item6Copy # <I6>, the outside copy above
$records = 'reports/generator-ceiling'
$series = 'attempt-01'
$armArgs = @('--private', $private, '--series', $series, '--records', $records, '--companion', '<COMPANION>', '--codex-home', '<CW_CODEX_HOME>', '--state-root', "$private/companion-state")
$judgeArgs = @('--private', $private, '--series', $series, '--records', $records)
& $py "$tools/ceiling_common.py" hashes
```

Fill the wrapper hash and registration placeholders; set the exact status to
`Status: **registered before the first request**`. Review and commit spec, tools and tests.
Stage only the listed spec, tools and tests. Before each new request the registered bytes
must be unchanged in HEAD.

```powershell
git status --short
git diff --check
git add -- docs/specs/generator-ceiling.md reports/generator-ceiling/tools/ceiling_common.py reports/generator-ceiling/tools/ceiling_route.py reports/generator-ceiling/tools/ceiling_answer.py reports/generator-ceiling/tools/ceiling_judge.py reports/generator-ceiling/tools/ceiling_record.py reports/generator-ceiling/tools/wrapper.txt tests/test_generator_ceiling.py
git commit -m "Register stage 5v generator ceiling protocol"
```

Then the data-free probe:

```powershell
& $py "$tools/ceiling_answer.py" probe @armArgs --budget 840
```

Read each step's status and arm summaries before the next step. Code 3 repeats the same command;
code 5 requires diagnosis before the same command with --resume-infrastructure.

```powershell
& $py "$tools/ceiling_answer.py" pilot @armArgs --s5 $s5 --i6 $i6 --step 1 --budget 840
```

```powershell
& $py "$tools/ceiling_answer.py" pilot @armArgs --s5 $s5 --i6 $i6 --step 5 --budget 840
```

```powershell
& $py "$tools/ceiling_answer.py" pilot @armArgs --s5 $s5 --i6 $i6 --step 20 --budget 840
```

Perform the following key sequence for wixqa, then conditionalqa, then aircargo; do not advance
after a rule stop. Repeat run chunks until key complete. A key's pilot answers are reused.

```powershell
$key = 'wixqa' # Next iterations: conditionalqa, aircargo
& $py "$tools/ceiling_answer.py" run @armArgs --s5 $s5 --i6 $i6 --key $key --budget 840
```

Freeze once, review the receipt and printed eligible request/cost/time forecast:

```powershell
& $py "$tools/ceiling_judge.py" freeze $key @judgeArgs --s5 $s5 --i6 $i6
```

Commit that receipt before any grade (the orchestrator performs this after review):

```powershell
git status --short
git diff --check
git add -- "$records/plans-$key.json"
git commit -m "Register generator ceiling $key judge plans"
```

Grade foreground chunks until code 0; on code 3 respect persisted retry_at. After code 5,
diagnose before rerunning with --resume-unavailable. Codes 1/2 require investigation.

```powershell
& $py "$tools/ceiling_judge.py" grade $key @judgeArgs --budget 600
```

Export the key; the reader can report incomplete/stopped evidence at any time:

```powershell
& $py "$tools/ceiling_judge.py" export $key @judgeArgs
```

After all three keys (or a stop), read:

```powershell
& $py "$tools/ceiling_record.py" @judgeArgs
```

## SHA-256 registration

Public input hashes are the SHA-256 of the listed repository files at registration; runtime
checks require those same committed bytes. Tool/wrapper placeholders below are filled from `ceiling_common.py
hashes` after review; an allow-list or other registered-byte change requires an amendment
commit before another corpus request.

- `reports/stage4-final/stage5/2057ad0/record.json` `6ae0d6e1a48b468ceb6fc5cade58bd961a41ea5e8e1c379467ce9dde354f3c1b`
- `reports/stage4-final/stage5/2057ad0/stage5-wixqa-m1.json` `4b7a0cd04ca057f442e7416c5dc8f377cc8e54a8b471e115e99741df20a629a8`
- `reports/stage4-final/stage5/2057ad0/stage5-wixqa-m1.cases.jsonl` `40888f0500e1be401bbf28ce1d3776bb06bb1ba066d5a98ea36e304336d9f71e`
- `reports/stage4-final/stage5/2057ad0/stage5-wixqa-m2.json` `b5f0611281d4a3cf486ab17d51d2bfa5c1c397f8a3119d1868cd8d4fd968028d`
- `reports/stage4-final/stage5/2057ad0/stage5-wixqa-m2.cases.jsonl` `d30f87c84d53c662cbbe18b338891df13a8d1de4358e7787448d7e5d3168ac2f`
- `reports/stage4-final/stage5/2057ad0/stage5-conditionalqa-m1.json` `2d4d19f0a98adddc55942a024161acf49ada34407fde0e511887b33f3906191a`
- `reports/stage4-final/stage5/2057ad0/stage5-conditionalqa-m1.cases.jsonl` `c51985283b4b1d4cc4a5acec55b4821d679432c0f40e3baaed4b8d28b80550d2`
- `reports/stage4-final/stage5/2057ad0/stage5-conditionalqa-m2.json` `093df6572eb6a1046b83f2fbab5216b852f00d60038127bf9a1daa787fcf2890`
- `reports/stage4-final/stage5/2057ad0/stage5-conditionalqa-m2.cases.jsonl` `c32ad3b9a1d515aba2c11dc8fa714d9d810856860cc180b9acc0adc1f31ddcd9`
- `reports/stage4-final/138f3b3/final-aircargo-m1.json` `b652921bd3a988e0bb9cc3bef4ec52f07043f543194a8c52f6694f2471628c83`
- `reports/stage4-final/138f3b3/final-aircargo-m1.cases.jsonl` `232d605eee10b65320f3a6a52a5dd3ecd3fb297d4c442b639329d1b8383e779a`

- `agent/prompts.py` `eb33d17e5891fa792e1576569a8fbd06084669de2ec0dcc8bbba17dffbd4444b`
- `evaluation/blinded_judge.py` `73650a061fdfc4639282a833d13fc496b9c3949de5964eabd85b2d787a0bfe6e`
- `evaluation/blinded_judge_clients.py` `3922706f6401a613708801f42dd1537045f61587dc75b93fb317ef8a12ef807a`
- `evaluation/external_parts.py` `10e101f5e880a8448ff3fc45e27207d672a82bf7e9e478d2f0bbe53b662104de`
- `evaluation/isolated_request.py` `8d488f4feb303fe4ad73d96b4174f2ffa1d10133a11ac3f8c5974e2fff2db244`
- `evaluation/semantic_ruler.py` `78477ebdb660af3a27d9210a318fae802bfa5230a7462954357e8be9f51d9a91`
- `reports/answer-prompt-v4/tools/bridge_plan.py` `41c72f480de3b093a74215d3ea89f00453c838cfaa27857e9c6f6c0d0701d244`
- `reports/answer-prompt-v4/tools/v4_record.py` `b518daf26ea36d2ecb753e22029c4ab780a56b39d1e174d01650b4050659bd6d`
- `reports/answer-prompt-v5/tools/replay.py` `ca954c59710e93925cc923f5b2a7f175ce86f7e1fa7b96a46d3b3bbeec4d6eed`
- `reports/answer-prompt-v5/tools/v5_core.py` `9df9af4f8be470198c1c7a6a3eef12abe0907a613fd1ff43a3933002587f0b4d`
- `reports/answer-prompt-v5/tools/v5_record.py` `1e77dd35f011d274a165e7fda606d54fafbfd27a45c66154e791a645a23f7620`
- `reports/answer-prompt-v6/tools/shown_text.py` `eb571e5ca935fb3729595b95dc785dae7097ae8ac135a78587ebf64cc370aedc`
- `reports/answer-prompt-v6/tools/v6_common.py` `9d851a6aa6c6c021d3a5c98667e56bfb9d57a125413b83d37873857ab1ebf19e`
- `reports/answer-prompt-v6/tools/v6_judge.py` `609477a00f14e1b660a57c43b9ebaa9246c2c2f23d8c9170c05c2a2d5a09c6c3`
- `reports/answer-prompt-v6/tools/v6_key.py` `817a42c0bddae5968a4de5cb6702e0547b920f981b702e322ac64663e8f4c1c0`
- `reports/answer-prompt-v6/tools/v6_record.py` `059d4ce93a265b56ca992a2be9b64abd763e07564de2e67b5cacc59249c759ab`
- `reports/answer-prompt-v6/tools/v6_replay.py` `2a346517fa2c084c797e341758c73f2c5b2f2085df27367c276b391b1ce75c38`
- `reports/generator-ceiling/tools/ceiling_answer.py` `248c7b5dcd2c28144b535615fabea0dd20559bdc9697a107dce7f55da437b71c`
- `reports/generator-ceiling/tools/ceiling_common.py` `1f75e3cbd0e64145dd425d32bd710dc20a14921c8b19dd75ba50f28c63169014`
- `reports/generator-ceiling/tools/ceiling_judge.py` `83c823d20f02447030d21ff96e0d06144952ad0b5366e8ce16c4c6f22052cdf2`
- `reports/generator-ceiling/tools/ceiling_record.py` `ad65e000798c0ed676df9b4a3601b058c50f54e61c2942027eada3512e28e1a6`
- `reports/generator-ceiling/tools/ceiling_route.py` `7ab7e14735db113b2c45d9e653ee252c850fdaf4a15d362f316b20fb2ed871c1`
- `reports/generator-ceiling/tools/wrapper.txt` `583b49ac747123ce24e17d200f3deb70c82117f9f0e295c1dc6db3df311086af`
- `reports/stage2/tools/judge_export.py` `d2a69975de960791c2b1aca8d93d58f75ef01c92c16686e12646473aea069193`
- `reports/stage2/tools/stage2_cases.py` `17550c826764349a9ea654a18cfb107948dfcaa3474675a269695c78b572fb9d`
- `reports/stage2/tools/stage2_common.py` `4d5241560ab5425faa0a1fe6c5b856454b3f8ee47e59187f0da6644b1bad48da`
- `reports/stage4-final/tools/common.py` `0bcf149b359b7db5e20c550a6c7107cd89d3b400453fb808f58ae70a2e1890ed`
- `reports/stage4-final/tools/external/protocol.py` `9ff4ef2692cf9676e347f8b21e36738f29a58aba67db562c5dd54692e4bb7d4b`
- `reports/stage4-final/tools/judge.py` `8b96d7d3413cf7a5d978713046ff3620351647a058e00e2040beca31485cf336`
- `reports/stage4-final/tools/run.py` `d75cc1195a0258cbd78b049d434e15ab79439f2e96cef71838dba6a804481ff1`
- `reports/stage4-final/tools/stand.py` `2887646363fe9be5b148d0abc378492d53f51c1f9ebef874dc76516955bea29d`
- `scripts/chat_answer_judge.py` `cdb2be82d3341afe0b1aba4e560f56eac4e2dec9cce69d0e038a18da4f2c7788`
- `scripts/chat_signals.py` `5a193a801147427a725f3ac32580118ac98ecfdfcacb7b02587fb9fe56afeab7`
- `scripts/context_judge.py` `c93744c25148313ec50e1a6120aebcb702a177cf8def88e49d128260c1e93cd6`
- `scripts/p2_astra_reference.py` `51bab02664db50adde7bd25b89cf9d279b3c7e0d4f66ea46e18f5bd033ce65b6`
- `tests/test_generator_ceiling.py` `ebc10677dc992f94edc733f8d8c9b466e3241e702583e10affa74fd8ddb1818a`

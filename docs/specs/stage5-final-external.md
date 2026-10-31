# Stage 5: the final package's external answers

Status: **registered before the run** on 2026-10-31, at STAGE5_SHA: the commit that added
`reports/stage4-final/stage5/baseline.json`.
A cold read (docs/operations/audit_opus55_31_10_26_stage5.md) found 1 blocking, 4 should fix and 5 minor; each is applied (its Disposition says how).
This registers preparation, not a quality result. Nothing in stage 5 runs before
item 6 has been read; detected harm on item 6's M1 bad first needs Julia's yes/no.
Finish item 7 before stage-5 answers; copy preparation inputs before item 7 or after it.
Stage 7's package advisory is a forecast cross-check only. Its parity-checked
H_old is also the independent old-side M3 gate below; no arm reading decides here.

## What is measured

The final path answers stage 2 part 4's same 300 open-selection questions, 100 each,
in this base order: **WixQA, ConditionalQA, MultiHop-RAG**. Within each base use
`stage2_cases.registered`'s order, ten batches of ten, one answer per question.
No selection by an answer, its time, or its grade. With item 6 this supplies the
published quality base on four corpora, side by side (PLAN rule (c), after the run,
record, test and index row). These reused questions are not an independent test set.

M1 is answer quality without the reference, M2 agreement with the reference (or a
right decline without one), M3 deterministic external gold in the **sent context**.
The judge's `context_has_answer` is printed beside M3, not substituted for it.
This quality run makes no M5 or SLO decision; incidental times are descriptive.

| Base | Old answers and M1/M2 plans | Role |
|---|---|---|
| WixQA | V4, 4f48fed, `v4-wixqa`, `v4-wixqa-judge-m1`, `v4-wixqa-judge-m2` | Paired, primary pool |
| ConditionalQA | V4, 4f48fed, `v4-conditionalqa`, `v4-conditionalqa-judge-m1`, `v4-conditionalqa-judge-m2` | Paired, primary pool |
| MultiHop-RAG | V3, 5e308fe, `p4-multihoprag`, `p4-multihoprag-judge-m1` | Advisory pairing, includes V3→V4 prompt change |

MultiHop-RAG is advisory and decides nothing. V4 never answered it. Its old M2,
`p4-multihoprag-judge-m2`, exists but was **NOT_EVIDENCE**: 13/15 retests agreed,
two two-step disagreements, quadratic κ 0.59 (stage 2's published record and
`docs/evidence/stage2-record.md`). Its new M2 is unpaired and printed only.

Published M1 at `reports/answer-prompt-v4/4f48fed/v4-<base>-judge-m1.json` and
`.cases.jsonl`: WixQA bad/partial_ok/good 51/9/40; ConditionalQA 57/8/35.
The pooled bad share is 108/200 = 0.54 (`v4-record.json`, `primary`). Published
MultiHop-RAG M1 at `reports/stage2/5e308fe/p4-multihoprag-judge-m1.json` and cases:
34/1/65, counted with stable retests. Published `context_has_answer` true counts
are 92, 94 and 73, respectively. These are prose, not decision constants: tools
read the committed old exports and their rows and hash those files in the receipt.

## Stand and unchanged item-6 protocol

Items 6 and 7 have their own registration, **ITEM6_SHA = `138f3b3f6ac223540965cc831838ff4f671a2200`**. This is
the corrected item-6/7 registering commit, not ecc79dd. The private config
and driver require that full SHA. Stage 5 registers separately at **STAGE5_SHA**,
with this spec, its tools/tests and checked `stage5/baseline.json` in that commit.
Only after item 7 ends, raise a new complete stand with the unchanged
`reports/stage4-final/tools/raise_stand.py STAGE5_SHA`.

Before the first batch, and again in the reader, compare the two commits with
`git diff --name-only ITEM6_SHA STAGE5_SHA`. Only `docs/**`, root `*.md`,
`reports/**`, and `tests/**` may differ, with one further restriction: changed
`*.py` under `reports/` must be inside `reports/stage4-final/tools/external/`.
The item-6 harness and its frozen imports therefore cannot change. Reports data,
records and documents remain allowed. Every other path (including product code,
settings and dependencies) refuses. Both full SHAs and every changed path are
printed in the record. Rename detection is disabled so a move cannot conceal a
removed product path. The stand is a Git archive without `.git`; its explicit
`--source` is a bare source repository transported in a Git bundle of the registering
commit. The laptop reader repeats the comparison in its source checkout. The
stand manifest binds the archive to STAGE5_SHA; no copying tools into an old stand.

`external/execute.py` delegates every batch to the unchanged item-6 `run.batch`.
The stand uses the service interpreter
`/Users/julia/RAG_Support_Assistant/.venv/bin/python`, with
`PYTHONPATH=<stand>:/Users/julia/RAG_new_mf_gate_site`, both HF offline flags 1,
transformers 4.44.2, tokenizers 0.19.1, onnxruntime 1.23.2 and tokenizer snapshot
`953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`. Stage 7's frozen environment and
loaded-tokenizer checks are reused; ORT intra-op threads 0 and effective batch 32
are recorded; a set `RAG_RERANK_BATCH` refuses. The runtime symlink's old env.json
does not choose the model: the runner sets the measured model from the code defaults.

Effective K 14, window 3,584, input limit 2,176, onnx, five, CPU, parent expansion,
hybrid search, local-first, routing off, classic self-evaluation, and three
3,600-s limits are required. The prompt id is `QA_PROMPT_V4`. The exact default
model is `qwen3:4b-instruct-2507-q4_K_M`, digest
`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`; Ollama 0.33.2.
The export at `/Users/julia/RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx`
must hash to `57335a9f061fe31378c160ddd0861711a0fbdfa20f70aa2640d473dfc4bc1343`
(item 5a's manifest). The read-only `~/.config/llama.cpp/config.ini` must hash to
`c75f44912ea2c7f54ea0cf0e9ffea8f05466ae447961d99c8f12d716589b4e6c`, including
`cache-ram = 1024`. No fetch, fallback, index rebuild or cache edit.

Before each batch: bounded idle wait, 60-s polls logged for at most 30 minutes;
if still busy, quality proceeds with `busy: true`. Taken ports, a resident model,
or a changed stand still refuse. Each batch has a fresh API and starts unloaded.
Preload reads the product window from its effective settings, sends `options.num_ctx`,
requires `/api/ps` context_length 3,584, and records the llama-server pid; every memory
sample and the after-last-question check must show that pid. The measured load is
at the product window. After unloading, the same bounded 60-s `/api/ps` and process
check as item 6 precedes idle-after. An unfinished unload is a path/cleanup failure.

Each of the thirty `final-answers-<base>-bNN` batches uses its registered tenant and
archive, with the existing index copied byte for byte. Archive hashes are stage 7's
registered `ARCHIVES`; generation, question, index and stand hashes are recorded
and checked again by the reader. Each question must have a successful answer/result,
no stream/drain error, one retrieval with both lanes nonempty and at most 14 each,
successful rerank, five documents and one labelled V4 prompt. Wrong settings,
missing/duplicate/reordered cases or a path break make that **base NOT_EVIDENCE**.
After ten batches pass the answer gate, the driver atomically writes
`OUT/<base>.complete` with that base's ten batch hash maps, baseline hash, both
registration SHAs and changed paths, then starts the next base without waiting for
the laptop. Failed bases get no completion marker or plan receipt; later bases
still run. Stand drift, operator stop and the overall series deadline stop owned
work, but earlier completed bases remain readable. Retain failures, read the cause,
use a new OUT; no automatic quality retry.

## Forecast and stops

Published times, seconds, 100 questions per row, median / p90 / max, with summed
hours (computed by the orchestrator from the committed records at f2b878c):

| Published source | Median | p90 | Max | Sum h |
|---|---:|---:|---:|---:|
| `reports/answer-prompt-v4/4f48fed/v4-wixqa.cases.jsonl` | 301.1 | 470.6 | 796.0 | 8.88 |
| `reports/answer-prompt-v4/4f48fed/v4-conditionalqa.cases.jsonl` | 249.3 | 339.3 | 397.6 | 6.93 |
| `reports/stage2/external-answers-20261023/p4-multihoprag.cases.jsonl` | 275.0 | 341.3 | 418.4 | 7.69 |
| `reports/stage2/external-answers-20261023/p4-wixqa.cases.jsonl` | 256.4 | 394.8 | 719.3 | 7.82 |
| `reports/stage2/external-answers-20261023/p4-conditionalqa.cases.jsonl` | 253.1 | 340.8 | 508.9 | 7.07 |

`result_sec` and `total_sec` agree within 0.1 s in these published records. The new
record keeps both: **whole answer = result_sec**, **stream close including suggestions
= total_sec**, alongside first-token time and stage timings. The forecast uses
total_sec. All old paths had K 20, a 4,096 window and PyTorch: the package should
be faster, so this is conservative, not a speed claim from a quality series.

Compute from each paired old side's actual committed rows: subsequent questions =
median rounded up to 30 s; first = max(360 s, p90 rounded up to 30 s); startup/preload
allowance 120 s. A batch forecast = startup + first + 9 subsequent, a base = ten
batches. Print the measured max too; it is not a censoring threshold. Refuse missing,
nonfinite, misordered times or an old maximum at/above the product ceiling.

| Base | Subsequent / first s | Batch s | Base h | 3× batch / base stop s |
|---|---:|---:|---:|---:|
| WixQA | 330 / 480 | 3,570 | 9.92 | 10,710 / 107,100 |
| ConditionalQA | 270 / 360 | 2,910 | 8.08 | 8,730 / 87,300 |
| MultiHop-RAG | 300 / 360 | 3,180 | 8.83 | 9,540 / 95,400 |

Total **26.83 Mac hours**, versus 23.50 published hours on those old sides, before
the bounded idle waits (at most 15 further hours). Waits are outside batch/question
clocks but inside base and series clocks. Series stop = 3× forecast, **80.50 h**;
also 3× each base and batch as above. There is **no per-question stop below 3,600 s**
except the remaining batch/base/series deadline. Startup has 360 s, preload 300 s,
as item 6. `OUT/STOP` or SIGTERM stops owned work. A forecast stop or ceiling is
NOT_EVIDENCE, never a pass; retain it and read the cause before any new OUT.

## Judge, bridges and per-base receipts

As each base's ten batches pass the answer gate, copy only that base's runs and
completion marker. Freeze that base's M1, M2 and bridge while the Mac answers the
next base. This overlaps a quality series, which does not require an idle Mac;
it never overlaps item 7. Across the three bases there are six main plans, using unchanged `scripts/chat_answer_judge.py`: stage 2/V4 English
instructions, salt `chat-answer-judge-2026-10-18`, isolated `claude-opus-5-5`,
effort `max`. M1 withholds references; M2 gives them. No aircargo handover reading
is added to an external plan. Validate the existing read-only references against
unchanged `judge_export.reference_rows` and the old export's hash; copy them only
into the new private plan directory. Clusters/strata stay the registered ones.

Each main plan holds all 100 answers. Empty or whitespace-only answers have no
message and the frozen export counts them as bad; they do not invalidate the base.
Requests are (100 minus empty) + 15 retests drawn only from message-bearing answers
(or all eligible answers if fewer than 15; the unchanged stability gate still applies).
The receipt and record print each base's empty count. No context verdict is invented
for an empty answer: same/lost/gained counts include only actual Boolean pairs.
With no empties each plan has 100 requests + 15 retests. Also import V4's `bridge_plan.py` unchanged
on the old **M1** plan of each base: V4 WixQA/ConditionalQA, V3 MultiHop-RAG. Cut to
its 15 retested originals and copies, retain the old reply lines byte for byte and
grade only the 15 copies in this window. Validate original plan/reply hashes against
the published export and admitted originals before freezing. The bridge does not
change the original instruction, reference exposure, salt or prompt version.

Each base has its own text-free `stage5/<seven>/plans-<base>.json`, holding its
three plans, its own batch hashes and completion marker, the checked baseline,
references, source plans/replies and bridge original prefix. **Commit each base's
receipt before that base's first grade**, including its bridge. Grade/export
refuse an uncommitted or changed receipt, a receipt for another base, missing plan,
changed bytes/references or changed bridge originals. A later base never changes
an earlier receipt. Exports also bind verdicts to sent-prompt hashes and stand.
No grading is performed by plan or record commands. The reader reads all receipts
present, names absent bases, and retains earlier valid readings after a later
failure; the pooled decision requires both WixQA and ConditionalQA.

Use frozen admission (at most six counted replies/request) and stability: at least
12 retest pairs, quadratic κ ≥ 0.6 OR at least 13/15 agreement with no two-step
disagreement. Missing verdicts or failed M1/bridge stability make that base's paired
M1, M2 and M3 reading NOT_EVIDENCE; retain the answers for a later frozen plan.
An unstable new M2 makes its M2 reading NOT_EVIDENCE, without changing the M1 decision.
MultiHop's new unpaired M2 can still be printed if its own plan is stable.

**735 requests** is the zero-empty forecast = 6 × (100 + 15) + 3 × 15. At the measured range
**$0.1775–0.2834/request** (stage 2 $122.45/690; V5 $175.71/620), **$130.46–208.30**,
before adapter retries. There are 245 requests/base, $43.49–69.43/base, and
8.17–8.85 laptop hours/base at 120–130 s/request; total **24.50–26.54 laptop hours**.
PLAN's ≈330 estimate did not include separate M2 plans and these three bridges.
Serial Mac-then-laptop wall time is **51.33–53.38 h**. With one Mac and one laptop,
start each base's judge after its answers and the prior base's judge finish:
Mac completion at 9.92, 18.00, 26.83 h gives **35.00–36.46 h pipelined**.
These wall forecasts exclude bounded idle waits, copies, plan commits and retries;
the full idle-wait allowance is up to 15 h more, within the same series stop.
With no empties each main plan forecasts 14,950 s, stop 44,850 s; each bridge
1,950 s, stop 5,850 s. Actual plan budgets use their message count times 130 s
and stop at three times that forecast.
Reuse item 6's persistent **sum of request durations**, not elapsed wall time.
A reply that arrives is always kept; stop before the next request. Export even a
stopped plan, preserving NOT_EVIDENCE; a stop never authorizes resumed grading.

## Deterministic M3 and the paired reading

`stage2_record.py` read sent M3 from **p2** external retrieval runs, not p4 answer
rows or the M1 judge. Published V3 values in
`reports/stage2/5e308fe/stage2-record.json`, `corpora/<base>/m3/points/sent`:
WixQA gold_article 68/100, ConditionalQA all_evidence_coverage 60/80 (20 without
gold), MultiHop-RAG all_evidence_coverage 10/70 (30 without gold).

Before reading V4 or the new answers, reproduce the MultiHop-RAG old side from
private `p2-multihoprag/retrieval/*.json`, its registered corpus, and committed
`reports/stage2/external-answers-20261023/p2-multihoprag.json` and `.cases.jsonl`.
Check provenance, the raw sent text/question against its prompt, raw-prompt bytes
against p2's hash and p4's answer prompt hash, gold membership, every sent coverage
point and the combined record's n/hits. It must reproduce that record's 10/70;
the code reads n/hits from the record, not this literal. A mismatch refuses before
any final-path request. Confirm the combined record holds MultiHop's M2 NOT_EVIDENCE.

V4's sent M3 is not in V4's own record, but stage 7's parity-checked H_old
publishes it: WixQA 68/100 and ConditionalQA 60/80. V4 kept retrieval on 100/100
in each primary base, but sent context on only 81 WixQA and 89 ConditionalQA
questions. Recompute from V4's saved prompts, pinned by published answer hashes,
and require per-question equality with `reports/stage7/5e308fe/rows.jsonl`,
labels `p2-wixqa` and `p2-conditionalqa`: H_old prompt SHA-256, gold flag, hit and
fraction rounded to six decimals. Missing, extra or duplicate ids refuse.
The baseline pins that file to SHA-256
`2d87859ecfd5e2442eefadcc5dafb471e5a80d13d8227907d59e568010109627`, and
`reports/stage7/5e308fe/record.json` to SHA-256
`b9db1434a6091536540112591e29cb3f02f373660dd06469e6abebc3780b55e4`.
MultiHop keeps the V3 p2/p4 gate, not this V4 comparator.

The historical archive has only `cases/`, `prompts/` and `launch.json`; no missing
stage trace is required. `chat_answer_judge.run_answers` reads labelled sent text.
WixQA credits the named article when visible text remains. ConditionalQA locates
visible pieces with `external_gold.Source`, stripping contextual headers. If a
body has no placement, also try it with `table_header.prefix(body, seed_metadata)`
stripped for every seed, on whole pieces and on the paragraph fallback, using the
same prefix rule as `external_gold.locate_chunks`.
Noncontiguous parent joins credit only visible paragraphs, never their gaps.
Enumerate every alternative placement, at most 256 combinations; above that cap
refuse before enumeration. Accept repeated text only when read_gold's (hit, fraction)
is identical for every combination; "ambiguous" means ambiguous in its reading.
Unplaceable text or a changed reading refuses. `retrieval_summary.Excerpted` and
the frozen range-coverage rule read the union of coordinates. New answers retain their full stage traces: replay
their observed expansion and use stage 7's `sent_point` as before. No model runs.
Hash every measurement file and recheck it at plan freeze and final reading.

Print old/new M3 numerators, denominators, gold-free count, fractional coverage,
pairs and intervals. Expected gold denominators are 100/80/70. **None of the old
sides is at a ceiling**; the baseline refuses a ceiling rather than silently changing
this registration. M3 reads both directions. The input limit 2,176 versus V4's
2,636 can shorten sent context: a fall is the expected direction of that lever,
but it is harm only if detected. It is a secondary metric, not the package decision.
Print `context_has_answer` same/lost/gained beside it, as V4 did; it decides nothing.

For M1 bad/good and M3, reuse `v4_record.paired` unchanged: new minus old, Newcombe
method 10 and cluster-bootstrap 95% intervals; **detected = both intervals exclude
zero on the same side**, after V4's four-decimal rounding. Touching zero does not
count. Corpus-prefix clusters in the pooled reading so they cannot merge across bases.
The frozen result keys `v3`/`v4` mean old/new in this adapter, including a V4 old side.
M2 reuses V4's reference/decline reader: paired agreement on reference-bearing cases,
right-decline counts beside it. Per-base readings and good shares are printed.

Only pooled **WixQA + ConditionalQA M1 bad**, 200 pairs, decides:

| Outcome | Condition | Consequence |
|---|---|---|
| harm detected | Pooled bad rises, detected | Name it and the pairs; Julia gets one yes/no on the package. The code keeps it meanwhile. |
| gain detected | Pooled bad falls, detected | The published base is the package's numbers. |
| holds | Neither direction detected | Publish the package's numbers; no detected difference is not equivalence. |
| NOT_EVIDENCE | Either primary base lacks admitted paired evidence | No package decision; keep files, read the failure. |

Resolution before the first request (PLAN §4.4), as in item 6: approximate
MDE ≈ 2.8·√(d/n), with discordance d = 0.1 / 0.2 / 0.3:

| Reading | n | MDE, percentage points |
|---|---:|---|
| Pooled deciding M1 bad | 200 | 6.3 / 8.9 / 10.8 |
| Per primary base | 100 | 9 / 13 / 15 |
| ConditionalQA M3 | 80 | 9.9 / 14.0 / 17.1 |
| MultiHop-RAG M3 | 70 | 10.6 / 15.0 / 18.3 |

Smaller changes remain unresolved; holds is not equivalence.

Forecast: **holds**, without a non-inferiority promise. K-curve gold 141→136 at K 14,
p 0.125, and INT8 gold 141→144 pull in different directions. Those component runs
do not add up to a prediction of answer grades; the shorter input limit can lose
sent evidence. The completed Amendment 1 cross-check is published at
`reports/stage7/5e308fe/record.json`, `package_advisory`: deciding bases at sent
128→125 of 180, p 0.375 (not detected); MultiHop-RAG sent 9→4 of 70, p 0.0625
(not detected); all three sent 137→129 of 250, p 0.021 (detected loss); all three
expanded 141→137 of 250, p 0.289 (not detected). The replay's old control used V4's
2,636-token input limit; stage 5's MultiHop old side is V3's p2/p4, 10 of 70.
Thus M1 **holds** remains the forecast; M3 sent is expected to fall on MultiHop-RAG
and possibly overall. These retrieval/context pairs contain no answer grades.
These advisory comparisons are a cross-check, not a decision input; the separate
H_old per-question gate above verifies the baseline. MultiHop-RAG's
answer comparison also includes V3→V4 and cannot isolate the speed package's effect.

## Running it on the Mac

All commands below are for the orchestrator in the real checkout, after item 6's
reading and item 7's end. No operator prompts or historical Mac tar/copies are
needed. Historical laptop inputs are read-only, in the literal paths below.
`D:/RAG_new_stage5_private/data/<base>/` already contains only `corpus/`,
`corpus.manifest.json`, `chunks-report.json`, `chunks.json.gz`, `cases.jsonl` and
`index/index-receipt.json`; it needs no index or embeddings. The corpus files must
be exactly those listed by corpus.manifest.json. Preflight refuses every other
file, including macOS AppleDouble `._*`; tools never remove these read-only files. The p2 retrieval
archive is already at `D:/RAG_new_stage5_private/p2-multihoprag/`.

Each laptop block starts independently in the real checkout. PowerShell uses the
explicit Windows bsdtar: it rejects GNU tar's `--force-local`, so omit that flag. The
first measurement command is `prepare.py`: presence and hashes are its first
operation, before M3 or any request. It validates the historical plans/replies
against their committed exports, actual prompts against answer hashes, references
against the original writer, corpus files against the manifest, and the p2 gate.
Do not create a receipt if preflight refuses.

```powershell
$Private = "D:/RAG_new_stage5_private"
$Old = "D:/RAG_new_stage2_private"
$Tools = "reports/stage4-final/tools/external"
$Baseline = "reports/stage4-final/stage5/baseline.json"
$Config = "$Private/inputs.json"
$Item6Sha = "138f3b3f6ac223540965cc831838ff4f671a2200"
if ([string]::IsNullOrWhiteSpace($Private)) { throw "Private root is empty" }
function Checked { & $args[0] $args[1..($args.Count-1)]; if ($LASTEXITCODE -ne 0) { throw "Command refused" } }
$Bases = @{}
foreach ($Base in @("wixqa", "conditionalqa", "multihoprag")) {
    $Series = if ($Base -eq "multihoprag") { "p4" } else { "v4" }
    $Pub = if ($Series -eq "v4") { "reports/answer-prompt-v4/4f48fed" } else { "reports/stage2/5e308fe" }
    $Answers = if ($Series -eq "v4") { "$Pub/v4-$Base.json" } else { "reports/stage2/external-answers-20261023/p4-$Base.json" }
    $Plans = @{m1="$Old/$Series/judge/$Base-m1"; m2="$Old/$Series/judge/$Base-m2"}
    $Entry = @{answers=$Answers; m1="$Pub/$Series-$Base-judge-m1.json"; m2="$Pub/$Series-$Base-judge-m2.json"; runs="$Old/$Series/runs"; source=$Plans.m1; plans=$Plans; references="$Old/references/$Base.jsonl"}
    if ($Series -eq "v4") { $Plans.bridge="$Old/v4/judge/bridge-$Base"; $Entry.bridge="$Pub/v4-bridge-$Base.json" }
    $Bases[$Base] = $Entry
}
$Inputs = @{item6_sha=$Item6Sha; data="$Private/data"; bases=$Bases; stage2=@{run="$Private/p2-multihoprag"; export="reports/stage2/external-answers-20261023/p2-multihoprag.json"; combined="reports/stage2/5e308fe/stage2-record.json"}}
[IO.File]::WriteAllText($Config, (($Inputs | ConvertTo-Json -Depth 10) -replace "`r`n", "`n") + "`n", [Text.UTF8Encoding]::new($false))
Checked python "$Tools/prepare.py" --config $Config --private $Private --out $Baseline
```

Cold-read the real adapters and run the synthetic gate on the Mac. The orchestrator
then commits the stage-5 registration and checked baseline. Only after item 7 ends,
raise the separate stand. A detached worktree gives the unchanged stand tool the
clean registering HEAD it requires after the main checkout has advanced.
STAGE5_SHA is the commit that added baseline.json, found with --diff-filter=A,
not the moving HEAD; verify it is an ancestor of HEAD. Keep it after receipt commits. The bundle transports HEAD history, including the registering commit and ITEM6_SHA;
verify its ancestry before transport (the normal later-registration history).

```powershell
$Private = "D:/RAG_new_stage5_private"
$Old = "D:/RAG_new_stage2_private"
$Tools = "reports/stage4-final/tools/external"
$Baseline = "reports/stage4-final/stage5/baseline.json"
$Config = "$Private/inputs.json"
$Item6Sha = "138f3b3f6ac223540965cc831838ff4f671a2200"
if ([string]::IsNullOrWhiteSpace($Private)) { throw "Private root is empty" }
function Checked { & $args[0] $args[1..($args.Count-1)]; if ($LASTEXITCODE -ne 0) { throw "Command refused" } }
$Stage5Sha = (git log -1 --format=%H --diff-filter=A -- reports/stage4-final/stage5/baseline.json).Trim()
if ($Stage5Sha -notmatch '^[0-9a-f]{40}$') { throw "Missing registration SHA" }
Checked git merge-base --is-ancestor $Stage5Sha HEAD
$Short = $Stage5Sha.Substring(0, 7)
$RunPrivate = "$Private/$Short"
$Record = "reports/stage4-final/stage5/$Short"
$Remote = "/Users/julia/RAG_new_stage5/$Short"
Checked git merge-base --is-ancestor $Item6Sha $Stage5Sha
New-Item -ItemType Directory -Force "$RunPrivate/runs", $Record
$Src = "D:/RAG_new/.tmp/stage5-stand-src-$Short"
if (Test-Path -LiteralPath $Src) { throw "Stand source already exists" }
Checked git worktree add --detach $Src $Stage5Sha
Checked python "$Src/reports/stage4-final/tools/raise_stand.py" $Stage5Sha
Checked git worktree remove $Src
Checked git bundle create "$RunPrivate/source.bundle" HEAD
[IO.File]::WriteAllText("$Private/STAGE5_SHA", "$Stage5Sha`n", [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText("$Private/ITEM6_SHA", "$Item6Sha`n", [Text.UTF8Encoding]::new($false))
Checked ssh deproject-mac "mkdir -p $Remote"
Checked scp "$Private/STAGE5_SHA" "$Private/ITEM6_SHA" "deproject-mac:/Users/julia/RAG_new_stage5/"
Checked scp "$RunPrivate/source.bundle" "deproject-mac:$Remote/source.bundle"
```

On the Mac (zsh), the service recipe, not `remote.py --site`:

```sh
set -e
SHA=$(cat /Users/julia/RAG_new_stage5/STAGE5_SHA)
ITEM6_SHA=$(cat /Users/julia/RAG_new_stage5/ITEM6_SHA)
S=/Users/julia/RAG_new_chat_${SHA:0:7}
P=/Users/julia/RAG_new_stage5/${SHA:0:7}
PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python
T=$S/reports/stage4-final/tools
DATA=/Users/julia/RAG_new_external_s1
RUN_LABEL=runs # Set runs-r2 for a rerun.
OUT=$P/$RUN_LABEL
test -d "$P/source.git" || git clone --bare "$P/source.bundle" "$P/source.git"
cd "$S"
CLEAN=(/usr/bin/env -i HOME="$HOME" PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH="$S:/Users/julia/RAG_new_mf_gate_site" PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 RAG_RERANKER_ONNX=/Users/julia/RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx "$PY")
"${CLEAN[@]}" "$T/stand.py"
nohup "${CLEAN[@]}" -u "$T/external/execute.py" --data "$DATA" --out "$OUT" --baseline "$S/reports/stage4-final/stage5/baseline.json" --source "$P/source.git" --item6-sha "$ITEM6_SHA" >> "$P/$RUN_LABEL-answers.out" 2>&1 </dev/null &
echo $! > "$P/$RUN_LABEL-answers.pid"
```

For a rerun after reading the cause, retain the old OUT and logs, set RUN_LABEL
to `runs-r2` (then `runs-r3`, etc.) and rerun the Mac block without raising the stand
again. Set the same $RunLabel in laptop blocks 4 and 5. They put new private files
and receipts under that label, preserving prior plans and evidence; no receipt is
reused. The source clone is reused only when already present.

The driver continues WixQA → ConditionalQA → MultiHop-RAG without waiting for the
laptop. Read its log; `touch "$OUT/STOP"` stops before the next question/batch;
SIGTERM only the owned pid for immediate cleanup. A base with no completion marker
is not ready or failed; do not copy/freeze it. After each marker appears, execute
this laptop block for that base (`$Base` in the registered order). It tars only that
base, excluding both Chroma forms. These copies and laptop judging overlap the
quality run, never item 7. If a later base fails, still read earlier receipts.
Mac tar uses `COPYFILE_DISABLE=1` to prevent AppleDouble `._*` entries from extended
attributes, which Windows would extract as ordinary files. Before reading an
extracted runs folder, stage-5 tools refuse any `._*` file with its first offending
path; they never delete these files.

```powershell
$Private = "D:/RAG_new_stage5_private"
$Old = "D:/RAG_new_stage2_private"
$Tools = "reports/stage4-final/tools/external"
$Baseline = "reports/stage4-final/stage5/baseline.json"
$Config = "$Private/inputs.json"
$Item6Sha = "138f3b3f6ac223540965cc831838ff4f671a2200"
if ([string]::IsNullOrWhiteSpace($Private)) { throw "Private root is empty" }
function Checked { & $args[0] $args[1..($args.Count-1)]; if ($LASTEXITCODE -ne 0) { throw "Command refused" } }
$Stage5Sha = (Get-Content -LiteralPath "$Private/STAGE5_SHA" -Raw).Trim()
if ($Stage5Sha -notmatch '^[0-9a-f]{40}$') { throw "Missing registration SHA" }
Checked git merge-base --is-ancestor $Stage5Sha HEAD
$Short = $Stage5Sha.Substring(0, 7)
$RunPrivate = "$Private/$Short"
$Record = "reports/stage4-final/stage5/$Short"
$Remote = "/Users/julia/RAG_new_stage5/$Short"
$RunLabel = "runs" # Set runs-r2 for a rerun, matching the Mac.
if ($RunLabel -notmatch '^runs(-r[0-9]+)?$') { throw "Invalid run label" }
if ($RunLabel -ne "runs") { $RunPrivate += "/$RunLabel"; $Record += "/$RunLabel" }
New-Item -ItemType Directory -Force "$RunPrivate/runs", $Record
$Base = "wixqa" # Repeat for conditionalqa, then multihoprag, after its marker appears.
$BatchNames = (1..10 | ForEach-Object { "final-answers-$Base-b{0:00}" -f $_ }) -join " "
Checked ssh deproject-mac "test -f $Remote/$RunLabel/$Base.complete && COPYFILE_DISABLE=1 tar --exclude='*.chroma' --exclude='*/chroma' -czf $Remote/$RunLabel-$Base.tar.gz -C $Remote/$RunLabel $Base.complete $BatchNames"
Checked scp "deproject-mac:$Remote/$RunLabel-$Base.tar.gz" "$RunPrivate/$Base.tar.gz"
& "$env:SystemRoot/System32/tar.exe" -xf "$RunPrivate/$Base.tar.gz" -C "$RunPrivate/runs"
if ($LASTEXITCODE -ne 0) { throw "Extract refused" }
$Receipt = "$Record/plans-$Base.json"
Checked python "$Tools/grading.py" plan --base $Base --config $Config --private $RunPrivate --runs "$RunPrivate/runs" --baseline $Baseline --receipt $Receipt
Checked git add -- $Receipt
Checked git commit -m "stage 5: freeze $Base M1, M2 and bridge before grading"
foreach ($Metric in @("m1", "m2", "bridge")) {
    python "$Tools/grading.py" grade --base $Base --metric $Metric --private $RunPrivate --baseline $Baseline --receipt $Receipt
    $GradeExit = $LASTEXITCODE
    Checked python "$Tools/grading.py" export --base $Base --metric $Metric --private $RunPrivate --baseline $Baseline --receipt $Receipt --runs "$RunPrivate/runs" --out $Record
    if ($GradeExit -ne 0) { throw "Keep exports; read the stopped plan before further grading" }
}
```

After all available base exports, read all receipts present. An absent primary
base yields NOT_EVIDENCE for the pooled decision; a missing MultiHop base leaves
the primary reading intact. The command never creates a receipt for a failed base.

```powershell
$Private = "D:/RAG_new_stage5_private"
$Old = "D:/RAG_new_stage2_private"
$Tools = "reports/stage4-final/tools/external"
$Baseline = "reports/stage4-final/stage5/baseline.json"
$Config = "$Private/inputs.json"
$Item6Sha = "138f3b3f6ac223540965cc831838ff4f671a2200"
if ([string]::IsNullOrWhiteSpace($Private)) { throw "Private root is empty" }
function Checked { & $args[0] $args[1..($args.Count-1)]; if ($LASTEXITCODE -ne 0) { throw "Command refused" } }
$Stage5Sha = (Get-Content -LiteralPath "$Private/STAGE5_SHA" -Raw).Trim()
if ($Stage5Sha -notmatch '^[0-9a-f]{40}$') { throw "Missing registration SHA" }
Checked git merge-base --is-ancestor $Stage5Sha HEAD
$Short = $Stage5Sha.Substring(0, 7)
$RunPrivate = "$Private/$Short"
$Record = "reports/stage4-final/stage5/$Short"
$Remote = "/Users/julia/RAG_new_stage5/$Short"
$RunLabel = "runs" # Set runs-r2 for a rerun, matching the Mac.
if ($RunLabel -notmatch '^runs(-r[0-9]+)?$') { throw "Invalid run label" }
if ($RunLabel -ne "runs") { $RunPrivate += "/$RunLabel"; $Record += "/$RunLabel" }
Checked python "$Tools/reading.py" --config $Config --private $RunPrivate --runs "$RunPrivate/runs" --baseline $Baseline --receipts $Record --exports $Record --source . --stage5-sha $Stage5Sha --out "$Record/record.json"
```

## Records

Public: checked `reports/stage4-final/stage5/baseline.json`; under `<stage5-seven>/`,
up to three `plans-<base>.json` receipts, six judge exports plus cases, three bridge
exports and `record.json`. The record prints both registration SHAs and changed
paths, receipts present/absent, each available answer/M3 reading and the pooled
M1 decision. A later base's failure does not invalidate an earlier complete base.
The baseline includes computed V4 M3, reproduced stage-2 MultiHop M3, old timing
spreads, computed forecasts, and private-input hashes without private paths.
The record never takes a number from this spec. Status/evidence rows belong to
the orchestrator after reading.

Private inputs stay in `D:/RAG_new_stage2_private/` and the already copied
`D:/RAG_new_stage5_private/data/` and `p2-multihoprag/`. Tools never write there.
New answers/plans stay in `/Users/julia/RAG_new_stage5/<seven>/` and
`D:/RAG_new_stage5_private/<seven>/`, outside the checkout. Only that base's finished
runs and marker cross from Mac to laptop. Do not copy the growing `series.json`.
All public baseline/plan/final records pass `stage2_common.without_text` against
all corpora and queries; judge exports use the frozen guard. Only ids, flags,
numbers and provenance hashes/identifiers leave these folders. No external-base
text enters a committed record. Keep stopped artifacts; later regrading needs a
new private output and committed receipt, retaining the old receipt and exports.

The SHA-256 list below is checked by `test_stage5_spec_pins_new_and_reused_tools_without_editing_item6_or_item7`.

- `evaluation/external_gold.py` `fa15dc1ef84c58b524ee276382794dacfcf9cf4a7c7a459698e1152ccb741e61`
- `reports/answer-prompt-v4/tools/bridge_plan.py` `41c72f480de3b093a74215d3ea89f00453c838cfaa27857e9c6f6c0d0701d244`
- `reports/answer-prompt-v4/tools/v4_record.py` `b518daf26ea36d2ecb753e22029c4ab780a56b39d1e174d01650b4050659bd6d`
- `reports/stage2/tools/answers_summary.py` `b5b51f9cc913d59034e4d9cd8464410c544fe0876561eff31525e6ef7950c39d`
- `reports/stage2/tools/judge_export.py` `d2a69975de960791c2b1aca8d93d58f75ef01c92c16686e12646473aea069193`
- `reports/stage2/tools/retrieval_summary.py` `c5848ae81d9ed2ab1bcade119793d544fd2b0e2991e043e4c87a319b69c9219c`
- `reports/stage2/tools/stage2_cases.py` `17550c826764349a9ea654a18cfb107948dfcaa3474675a269695c78b572fb9d`
- `reports/stage2/tools/stage2_common.py` `4d5241560ab5425faa0a1fe6c5b856454b3f8ee47e59187f0da6644b1bad48da`
- `reports/stage4-final/tools/api.py` `19bf92e667f46f7cb00e5f9b44242ece80f80a2ef976b9d58343ce9721aa781b`
- `reports/stage4-final/tools/baseline.py` `ca2f48009acb2da4c10bcf03f8f9c5aac273fe74e8e57246840eaa66f087b8f5`
- `reports/stage4-final/tools/common.py` `0bcf149b359b7db5e20c550a6c7107cd89d3b400453fb808f58ae70a2e1890ed`
- `reports/stage4-final/tools/external/execute.py` `439cd80969d3911058fd74c39c09a5aa7107120907c1473d7be2777dd91e90a4`
- `reports/stage4-final/tools/external/grading.py` `f6e3e66eb0a731549e4b29c5887028e85f8c5748b9207a4ae6eff300762c7f7d`
- `reports/stage4-final/tools/external/prepare.py` `a18841cc4dd61bb511625281d4b5ef78c25b9e535c39bde963d0d12e7a961ce4`
- `reports/stage4-final/tools/external/protocol.py` `9ff4ef2692cf9676e347f8b21e36738f29a58aba67db562c5dd54692e4bb7d4b`
- `reports/stage4-final/tools/external/reading.py` `1842f9b72b69c22054dc134b04e5bd5427a95cc7133b3c0bf08245c1bf1207a7`
- `reports/stage4-final/tools/external/sent_gold.py` `aa65c31eb9cfbfacc3f233c6f264844d5a2d799d14efc60cc25ef68b0a2500f4`
- `reports/stage4-final/tools/judge.py` `8b96d7d3413cf7a5d978713046ff3620351647a058e00e2040beca31485cf336`
- `reports/stage4-final/tools/raise_stand.py` `caa1feec88202e6a1bc72af02fd1997a493ff9487a1eda9b844350acd7fff984`
- `reports/stage4-final/tools/record.py` `455f164a41bccb7a50d455c527de12e19d8224fc0cf51f8ff170b56afa4591ac`
- `reports/stage4-final/tools/run.py` `d75cc1195a0258cbd78b049d434e15ab79439f2e96cef71838dba6a804481ff1`
- `reports/stage4-final/tools/runner.py` `ace524da530742672a9b03d6638cdc79032a6188fde1be40ba41160336a8bd62`
- `reports/stage4-final/tools/stand.py` `2887646363fe9be5b148d0abc378492d53f51c1f9ebef874dc76516955bea29d`
- `reports/stage7/tools/arms_replay.py` `6ca8b723841d08dfd6f5d084bdc0883264c889eb495dc4d3728ac0a2ea623689`
- `scripts/chat_answer_judge.py` `cdb2be82d3341afe0b1aba4e560f56eac4e2dec9cce69d0e038a18da4f2c7788`
- `tests/test_stage4_final_tools.py` `06485545bb64c614f9b133257991aa5eb922a1cfb89c1d74135859678c593644`
- `tests/test_stage5_final_tools.py` `36f131c48772272062018de5f8f2ab0ffdab6dc41be18413b0b57939d3fe838d`

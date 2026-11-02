# Stage 5b — answer V6

Status: **registered before V6's first request**

Owner decision: Julia's «да», 2026-11-01, PLAN stage 5b. This is a prospective
specification, not an experiment result or approval to adopt. Cold-read it, resolve
any amendment, register these bytes and the tools/tests together, and only then
make the first V6 request. The replay and grading tools refuse the draft status.
Registration changes the status to `registered before V6's first request`.

## Why and what changes (V1–V3)

[V5's record](../evidence/answer-prompt-v5-record.md) found the principal loss:
claims unsupported by any supplied document. Its visible scaffold itself became a
defect in 75, 63 and 65 answers; aircargo also had 11 wrong-language answers and
10 repetitions. With the scaffold's two defects set aside, external-base bad
counts fell 51 → 39 and 57 → 46. Those adjusted counts motivate this experiment;
they are not V6 results or the baseline used for its decision.

V6 keeps written evidence and hides it. `qa_prompt_v6.txt` is the owner's V1 text
verbatim, including its English, final newline, V5 frame and citation sentence.
No prompt correction was made. There is no domain/language vocabulary and no V5
status line. The frozen judge recognises this frame as `QA_PROMPT_V5`; the receipt
and replay identify V6 by the **template SHA-256**, separately from each fitted
prompt SHA. The reference comparison is the **package's actual shown answers**,
not V5 or a recalculation that excuses scaffold defects.

`shown_text.py:shown_text(raw, question, finished=True, details=False)` is the one pure, self-contained function
that returns `{"text": ..., "flags": [...]}`. On adoption move this function
byte for byte. No provider, files, state, language model or language word list is
used. It depends on Python Unicode normalization and `regex` Unicode properties.
The registered versions are **regex 2026.5.9 and unicodedata 14.0.0**, held together
in `v6_common.REGISTERED_VERSIONS`. Replay records both; chain/check and the laptop
plan refuse either mismatch with registration before any request, and the plan
also compares both with replay. The receipt records both laptop and replay versions.

| Order | Registered rule | Edge and rationale |
|---|---|---|
| 1 | First `<answer>`, case-insensitive, exact names without attributes; strip outer whitespace | End at `</answer>` or, if unclosed, the next prompt-defined tag (`answer` or `evidence`, opening or closing, case-insensitive), otherwise the end. Trim a trailing proper prefix of any own tag, case-insensitively, even at a finished stream without a closing tag. Arbitrary `<...>` spans remain literal text. No opening tag or empty first answer gives `parse` at stream end. |
| 2 | Cut before the first repeated sentence of **at least 4 words**, or the third occurrence of an **8-word** n-gram | ASCII `. ! ?` end a sentence only before whitespace or actual end; `。！？` end anywhere; CR/LF also end units. Words are Unicode letters/marks/numbers, normalized NFKC then casefold; numeric citations ignored. Overlapping n-grams count across units. Preserve a preceding citation. Only the answer part is checked. |
| 3 | Compare dominant Unicode scripts | Both need **12 letters**, and a script needs **≥60%** of remaining letters. Ignore citations, quoted passages and identifier-shaped tokens: containing `_` or a digit, lowercase-to-uppercase transitions, or at least two letters all uppercase. Apply identically to question and answer. Unknown/Common/Inherited letters cannot win but remain in the denominator. The release threshold is separately 40 letters. |

The cold read found 23/300 package answers cut (6 graded good), median 20% removed;
seven lost 43–69%. All six sentence triggers were punctuation, and all 17 n-gram
triggers ordinary reuse 6–49 words apart. Measured variants, in W/C/A order:

| Variant | Package cuts | V5 judge-marked repetition caught on whole outputs |
|---|---|---|
| 11b rule | 11/10/2 | 3/2/4 |
| Sentence ≥4 + 4-gram | 7/10/0 | 3/2/4 |
| Sentence ≥4 + 8-gram (chosen) | 1/0/0 | 3/2/4 |
| Sentence ≥4 + 4-gram three times within 12 words | 0/0/0 | 2/1/4 |

With identifier filtering but the old 60% early stop, 4/100 package aircargo
answers fall back, including 2 graded good: their first eligible units are
0.61/0.65 Latin because of non-identifier field names, but their whole answers
are 0.43/0.53 Latin. With the chosen **90% early stop**, measured fallbacks are
**2, both graded bad**, decided at the end by R5's whole-answer rule, not by the
early stop; WixQA/ConditionalQA have 0 in every variant. V5's eligible
wrong-language answer parts are caught **10/10 early**, at the same unit as under
60%; whole outputs are **9/10 early**, one stopping at a different unit. Other
flagged V5 outputs are **3 answer parts / 5 whole outputs**, equal to the
whole-answer rule alone. Of 100 aircargo questions, 96 were Cyrillic-dominant
and 29 contained Latin codes. The Task 11e figures were measured by the reader
with the registered policy, Python 3.11.13, Unicode 14.0.0 and regex 2026.5.9;
they are supplied measurements, not recomputed here or new V6 results.
Release and the whole-answer share remain 60%.

The numeric citation grammar is `[N]` or a numeric list/range separated by comma,
semicolon, hyphen or en dash. The language check ignores paired straight double
quotes, curly double/single quotes, guillemets, Japanese corner/double-corner
quotes and standalone straight single quotes, across line breaks. Apostrophes
inside words are not quotation delimiters. Unclosed quotation marks do not hide
the rest. Common/Inherited/unknown-script letters count in the denominator but
cannot win. Script property identifiers are not language words.

These are deliberately mechanical guards: Latin does not distinguish English
from French; Cyrillic does not distinguish Russian from Ukrainian; mixed-script,
short or quoted-only answers can abstain. Periods are not a linguistic sentence
parser; no-space writing has no dictionary-based word segmentation. The prompt
also asks verbatim quotations to be in the question's language; that tension when
context language differs is retained from V1, not silently rewritten.

`parse` or `language` causes **one fresh package generation**, with the same
question and the original package documents/prompt rebuilt byte for byte. Its
output is shown as generated, without V6 parsing, cutting, language filtering or
another fallback. A repeated answer without another guard keeps its cut prefix.
Record ordered flags, fallback boolean, V6 stream seconds, fallback seconds,
total seconds, character lengths and hashes per case. A fallback can be empty or
wrong-language; it remains part of the measured policy, including the judge's
ordinary empty-answer bad class.

### Display policy R0–R5: measured, graded, and shipped on adoption

- R0: show nothing before `<answer>`; never show the prompt's tags.
- R1: a completed unit ends at a sentence boundary above or a line break. Hold the
  open unit. A trailing ASCII mark in an unfinished chunk waits for its lookahead.
- R2: before release, once completed units contain ≥40 counted letters, release
  all completed units if the question's script has ≥60%; stop generation and use
  the package fallback only if another script has **≥90%**. Another script at
  60% to below 90%, or no dominant script: keep holding until R5 decides.
  If the question abstains, release the first completed unit without a language
  check. If the answer ends without release, the whole-answer 12-letter/60% rule
  decides; abstention then permits release.
- R3: after release, at every unit check all completed units so far. A different
  decided script stops the stream, keeps only already released text and flags
  `language_after_release`; it never starts a fallback or retracts text.
- R4: run the repeat rule on completed units. Stop at a cut; never retract already
  released text. If the cut is inside that text, retain its released end and record
  `cut_at`, the would-be answer-relative character offset.
- R5: closing tag, stream exhaustion, 1,024-token cap or 3,600-s ceiling completes
  the open unit and runs the checks once more before release. After an R2–R4 stop
  drop the open unit. The ceiling also bounds a stalled provider wait.

One pure function reconstructs these decisions in unit order on every chunk that
can complete a unit, a tag or a numeric citation, and always on the finished stream. One shared helper
gates calls in collect and stream_reading (and thus shown_gate): match the new
chunk preceded by the previous character against `regex` pattern
`[\r\n。！？>\]]|[.!?]\s`; otherwise carry the prior result unchanged. Units end only
at these boundaries, tags only at `>`, and `]` can complete a numeric citation
across a line break and change a completed unit's repeat key (0 of 599 real texts
affected). Every chunk's seconds and cumulative characters are still recorded.
Deterministic median policy calls per answer, ungated → gated, in W/C/A order,
with `]` in the gate: package **146 → 10, 165.5 → 10, 79.5 → 6**; V5-shaped
**259 → 18, 304 → 17, 180 → 12**.
Across 599 real texts the gate preserved identical first shown time, `<answer>`
time, unit times, stop chunk, final text and flags. These are supplied measurements;
synthetic equivalence is checked here.
The reader recomputes shown text, flags and times from
private raw output, cumulative chunk characters/seconds and end state, refusing
any difference. Private timelines include both streams, `<answer>` time, each
completed-unit time, release and end. Public outputs contain only derived times,
flags and offsets. First shown includes any fallback delay and is null for empty
output; it is an adapter clock, not browser/network paint time. Full-buffer time
is the observed answer-part end for a non-fallback row; for a fallback it is the
fallback's first shown time on the same request clock, including V6 time and the
fallback's first-chunk delay. The reading uses this value. The measured aircargo
V5 median is 96.5 s without that delay versus **103.0 s with it**. This comparison
is descriptive only; text beyond a policy stop was
never generated and no counterfactual full continuation is inferred.

V5-based estimated first-character medians W/C/A were package 52.5/52.4/52.8 s,
tags hidden only 79.2/74.7/80.3, validated prefix 87.8/83.1/94.3, and full buffering
98.7/98.3/100.6 (p90 153–189 s); the aircargo fallback correction above supersedes
that full-buffer estimate. At a **60% early stop**, measured prefix/whole agreement
is **298/300** package answers. At the registered **90% early stop**, measured
agreement is **300/300**: WixQA **100/100**, ConditionalQA **100/100**, aircargo
**100/100**, under the registered policy and interpreter versions stated above.
This motivates R; these are not V6 observed times. Unspaced
scripts form few “words”: unit release works at CJK marks, but word-based repeat
detection has limited sensitivity without dictionary segmentation.

## Replay, environment and stops (V4–V5)

Use the original stand for each key. This holds code, fitting, provider runtime
and environment constant against that key's package run. Do not move aircargo to
the later external stand merely for convenience. Tools live in a separate archive
of the V6 registration checkout; **do not copy them into either historic stand**.

| Key, in order | Product stand | Saved package runs |
|---|---|---|
| WixQA | `/Users/julia/RAG_new_chat_2057ad0` | `/Users/julia/RAG_new_stage5/2057ad0/runs/final-answers-wixqa-bNN` |
| ConditionalQA | `/Users/julia/RAG_new_chat_2057ad0` | `/Users/julia/RAG_new_stage5/2057ad0/runs/final-answers-conditionalqa-bNN` |
| aircargo | `/Users/julia/RAG_new_chat_138f3b3` | `/Users/julia/RAG_new_chat_138f3b3/final-answers/final-answers-aircargo-bNN` |

`NN` is 01–10, ten saved questions per batch, 100 per key, in the saved case order.
The aircargo path above was checked on the Mac after the interrupted preparation.
`138f3b3f6ac223540965cc831838ff4f671a2200` is item 6's registration. The exact
external stand SHA is read from its `CODE_SHA`/`STAND_FILES.json` and must equal
every batch's full launch SHA; a short prefix alone does not admit a run.

Replay has **no retrieval**, self-evaluation, route selection or follow-up. Import
V5's saved-context parser, document conversion and builder, overriding only its
template. For all 100 keys before any preload/generation, use the actual chat's
`_fit_stream_prompt`, actual context formatting and provider flattening to rebuild
the package prompt. Require exact UTF-8 bytes, without CR/newline translation;
any mismatch refuses the entire key before a model call. Build V6 the same way.
Count unchanged ordered `(source, passage)` pairs per case, as well as document
counts. A V6 shortening is measured, not a parity failure. A missing, duplicate,
reordered, incomplete or different-model case/batch, missing timing, AppleDouble
file, or overridden prompt refuses admission.

Load the stand's `get_settings()`, `build_provider_runtime(settings).strong`, and
`generation_kwargs_for_role("generate")`; call its `generate_stream`, not an HTTP
substitute. Check the union of V5's effective-generation settings and the package's
settings against **each** batch's `effective_settings.json["all"]`, including
`llm_role_params_json` and provider registry selection. Package settings are K14,
window 3584, prompt input 2176, ONNX reranker top5/CPU, local-first, no routing,
hybrid and parent expansion enabled, classic self-evaluation setting, and all
three timeouts 3600 s. Generate temperature is 0.2, max_tokens 1024. No provider
fallback is permitted. Package and V6 use the same generation kwargs.

Model: `qwen3:4b-instruct-2507-q4_K_M`, digest
`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`;
Ollama **0.33.2**. Reuse stage 5/item 6's unchanged `stand.check`, `code_check`,
preload/unload and sampler: service Python
`/Users/julia/RAG_Support_Assistant/.venv/bin/python`, site
`/Users/julia/RAG_new_mf_gate_site`, offline caches and int8 ONNX at
`/Users/julia/RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx`. The frozen check
verifies cache/model hashes, interpreter/libraries/tokenizer, settings, digest and
server. Compare every source batch's `stand.json` and the post-key receipt after
removing only Ollama servers' `pid` and `started`. Binary, binary-change time,
version, digest, settings and caches remain checked. Recheck stand files/tools at end.

Before **each batch**, use stage 5's unchanged quality-only idle reading
(`wait_idle(..., speed=False)`, external/execute.py:77–79). Retain every reading;
after its bounded wait a busy reading can proceed, but a resident model still
refuses. Report timings over all batches and separately over clean readings.
`--check` executes every gate except generation, reports one idle reading without
waiting, checks the stand and generation kwargs, compares both registered Unicode
versions before any request, and prints `regex.__version__` and
`unicodedata.unidata_version`.
Reuse the matching Ollama service; start no additional server. Preload/unload once per batch. Runs from the next key may
overlap the laptop judge, never another Mac generation or a speed measurement.

Each stream, including a fallback, has a **3600-s ceiling**, including a stalled
token wait. The pair also has the remaining key budget. The chain's outer wall
clock covers preflight/stalls: **3× the forecast per key = 37,800 s**. On exception,
timeout or nonzero child exit, stop the chain, preserve partial files, unload the
owned model and retain a STOP/FAILED marker, preserving an existing reason.
`--keys` selects remaining keys in W/C/A order. Every attempt requires a fresh
output folder; completed keys are retained and never regenerated for a later-key
refusal. The laptop driver accepts each completed key's actual run folder.

After b01, **more than 5 of its 10 answers with `parse`** stops the whole chain.
Five is permitted; six is not. This is a registered form stop, not a tuning loop:
amend and cold-read/register the spec before any remaining requests. Never discard
that batch or silently reuse its label. A judge harm reading creates STOP as soon
as available; the replay observes it before the next case/batch/key. The in-flight
bounded call may finish; its answer is retained. The operator must also stop any
further laptop grading after detected harm.

### Forecast registered before requests

Public V5 median streams were 103.4, 100.5, 104.0 s on V4's stand; V4's were
85.3, 76.5, 85.7 s (WixQA, ConditionalQA, aircargo). The package prompt is shorter;
give it no speculative speed credit. Use V5 as the V6 stream proxy and V4 as the
fresh fallback proxy. A planning allowance of **10 fallbacks/100** is an assumption,
not a target or stopping threshold. Allow **120 s ×10** for batch preload overhead.

| Key | 100 V5 proxy streams | 10 fallback proxy calls | With 1200 s overhead | Forecast, rounded up to 900 s | Stop |
|---|---:|---:|---:|---:|---:|
| WixQA | 10,340 s | 853 s | 12,393 s | 12,600 s / 3.5 h | 37,800 s |
| ConditionalQA | 10,050 s | 765 s | 12,015 s | 12,600 s / 3.5 h | 37,800 s |
| aircargo | 10,400 s | 857 s | 12,457 s | 12,600 s / 3.5 h | 37,800 s |

Total registered Mac forecast **10.5 h**. Unrounded sensitivity including the same
overhead: 0% fallbacks 9.55 h; 10% 10.24 h; 25% 11.27 h; 100% 16.43 h. Medians are
not means; these are scheduling proxies, not predicted latency distributions.
Idle waits, transfer, cold-read/receipt commits and failed requests are additional.

## Judge, plans and bridges (V6)

Keep stage 5's request and route unchanged: `scripts/chat_answer_judge.py`, salt
`chat-answer-judge-2026-10-18`, instructions SHA
`fd015e742c835a17b17704ad629df90a34a61ac600762e8c74e52aababdcc9c2`, isolated
`claude-opus-5-5`, effort **max**, same CLI admission and at most six replies per
request. No external model is called during this preparation or by plan/record
commands. Only grading (`v6_judge.py grade` or `v6_key.py`'s grade step) sends
requests during the later registered run.

| Public plan name | Cases / references | New requests if no empty answers |
|---|---|---:|
| `v6-wixqa-judge-m1` | 100; references withheld | 115 |
| `v6-conditionalqa-judge-m1` | 100; references withheld | 115 |
| `v6-aircargo-judge-m1` | 100; original package handover reading retained | 115 |
| `v6-wixqa-judge-m2` | Same 100; reference answers included | 115 |
| `v6-conditionalqa-judge-m2` | Same 100; 80 reference-bearing and 20 without | 115 |
| `v6-bridge-wixqa`, `v6-bridge-conditionalqa`, `v6-bridge-aircargo` | Package M1's 15 retested originals, their admitted old replies, and 15 copies in this window | 15 each |

Bridge sources are stage 5's package M1 for the two bases, item 6's package M1 for
aircargo, **not V4's older answers**. Use V4's unchanged `bridge_plan.py` only as the
cutting tool. Check source plan/reply hashes against committed package exports,
15 admitted originals and immutable original-reply prefix. M2 has within-plan
retests, not an additional historical bridge.

The private V6 runs have the judge's ordinary `launch.json`, `cases/*.json` and
**one V6 stream prompt per case**. `answer`/result.answer is the shown text.
Raw evidence and raw fallback streams stay in `raw/`, outside the repository.
A fallback is judged against the documents in the V6 fitted prompt, although it
was generated with the package's possibly longer context: **this leans against
V6**. Do not substitute the package prompt in that case or select a second grade.

Freeze all plans for a completed key and a public `plans-<key>.json` receipt.
Build in the sibling `<name>.partial` folder and rename to the final name as the
last step, after plans, bridge and receipt. A leftover partial folder is removed
at the next freeze: no request was ever sent from it. If interrupted after receipt
publication but before rename, recover only the receipt matching the staged copy;
a different receipt refuses recovery. A final frozen folder is never rebuilt.
Preflight compares local regex/unicodedata with registration and the Mac summary.
The receipt pins both sides' versions, spec/tools/template, each plan, request counts, source hashes, bridge
prefix, references, old exports and every private measurement file/completion
marker. Recompute shown text/flags from raw bytes before freeze. **Commit the
receipt before that key's first grade**, including its bridge, and require it and
the registered spec unchanged in HEAD. A changed plan, receipt, prefix, references
or historical export refuses grading. Reader/export also recheck measured files;
the reader recomputes admitted grades and stability from the private replies.

Grade a completed key while the Mac answers the next. Within each key use M1,
bridge, read M1 harm immediately, then M2 (external only), export and read again.
An absent M2 must not prevent the first harm reading. Build the after-bridge
reading only if `reading-<key>-after-bridge.json` is absent; retain the after-M2
build. Every key invocation checks harm readings across both stand folders.
Retest count is 15 on eligible nonempty answers. Empty answers stay in the 100 and
are bad without a request; retests are `min(15, eligible)`. Do not resample them
away. Stability is the unchanged stage-2 rule: **≥12 usable pairs** and either
quadratic κ≥0.6, or agreement ≥13/15 of the available pairs with no two-step
disagreement. A missing main verdict still prevents a counted reading even if
the retests alone pass. Failed bridge/within-plan stability, request-clock stop or
missing replies are NOT_EVIDENCE, never a package/V6 pass.

Maximum planned requests without empties/retries: **5×115 +3×15 =620**.
At $0.1775–0.2834 each: **$110.05–175.71**. At 93–130 s each: **16.02–22.39
laptop hours**; this dominates the overlapped schedule. Each 115-request main
plan forecasts 14,950 s and stops at 44,850 s; each 15-request bridge forecasts
1950 s and stops at 5850 s. Actual budgets use the frozen eligible request count
times 130 s, then ×3, with unchanged `timed_sender`. Retries consume this budget
and increase cost; 620 is planned distinct requests, not a six-reply cost cap.

`v6_key.py` runs foreground chunks with a default 840-s budget. It derives state
from committed receipts, frozen journals, NOT_EVIDENCE markers, exports/readings
and a small retry file; it invokes the unchanged `judge.run_plan(..., limit=1)`.
The budget returns after the first completed grading unit past the deadline;
the frozen unit may include its own form retries. `v6_judge.py grade --limit N`
also supports bounded units. A failed grade without that metric's
`NOT_EVIDENCE.json` counts as unavailability only if its journal gained an
`unavailable` row during that attempt; any other exception is a refusal (exit 1).
Retry the same frozen plan, at most seven
consecutive failed attempts, 300 s apart; reset on success. Persist retry timing
and reconcile journal writes after a kill. Return 3 when elapsed time plus the next
backoff reaches the invocation budget; the next invocation honours `retry_at` and
continues the count. Backoff is not judge request time. After exit 5 and diagnosis,
rerun with `--resume-unavailable`: only when the persisted consecutive count is
at least seven, reset the count and retry_at at the current journal length,
preserving all verdicts. Below seven the flag has no effect.
Only a frozen 3x judge stop or detected harm touches the specified Mac STOP;
receipt refusal, budget return or exhausted unavailability does not.

Exit/status: 0 key complete; 3 budget reached, rerun; 4 receipt awaits commit
(path printed); 5 seven consecutive unavailable attempts (after diagnosis, rerun
with `--resume-unavailable`); 2 stopped (3x/harm, Mac STOP touched); 6 stop detected,
Mac STOP not written: the status names the target to touch by hand; 1 refusal.
SSH touch uses BatchMode=yes, ConnectTimeout=20 and a 60-s subprocess timeout.
Output is one status line, never request/reply text. An own `require` gate prints
its message truncated to 200 characters; other exceptions print only the class.
With a validated private path, both name `<private>/<key>/driver.log`, which
appends a UTC timestamp and the full traceback. If the private path is invalid,
print the refusal reason without writing a log or naming a log file.
Frozen judge stdout/stderr remain suppressed.
A kill after a verdict resumes from that verdict; no background laptop job is used.

## Reading fixed before the first request (V7)

Import V5's `corpus`, `pair`, `m2` and `decision`; rename historical side labels
to `package`/`v6`. Pair by case id, require the same 100 cases per key, original
prompt hashes and registered reference clusters/strata. M1 is the frozen
good/partial_ok/bad classification. Primary is **pooled WixQA+ConditionalQA M1
bad share** (200 pairs). Beside it print that same estimate on only pairs whose
ordered document passages V6 read unchanged; it does not replace the primary.

Differences are V6 minus package. Print the paired Newcombe method-10 95% interval
and the cluster-bootstrap 95% interval, seed **20261001**, **10,000 resamples**,
using `evaluation/external_parts.py`'s clusters. Prefix cluster ids by base when
pooling, so unrelated bases cannot merge. Each aircargo question is its own
cluster. A fall/rise is **detected only if both intervals exclude zero on the
same side**; the displayed `read95` is their envelope. Zero on either boundary,
conflicting signs or unavailable intervals mean not detected.

Read this exact V5 table **in order; the first row that holds decides**:

| Row | Outcome | Condition |
|---|---|---|
| 1 | not adopted — harm | Any readable key's bad share rises; or its good share falls while bad does not fall; or ConditionalQA's declines among its 20 unanswerable questions fall; or pooled external bad rises with both bases readable; or pooled M2 `agrees` among 180 reference-bearing questions falls with both bases' M2 plans counted on both sides. |
| 2 | NOT_EVIDENCE | No admitted harm, but a required old/new plan or bridge is missing/uncounted, any key is not answered whole, or either primary base is not available. |
| 3 | adopted | All required evidence counts and pooled external M1 bad falls. |
| 4 | not adopted — no gain | All required evidence counts but that fall is not detected. |

A key's M1 harm is readable only when its old/new M1 plans and bridge count.
M2 harm needs both bases' old/new M2 plans counted. Check after each key, before
waiting for the rest: detected harm wins even if later keys/M2 are absent. Never
use an unstable plan to declare either gain or harm. The reader exits 2 for
detected harm; partial evidence otherwise remains NOT_EVIDENCE until complete.

Printed, deciding nothing else: class transitions, wrong declines, context-answer
lost/gained/same, supported claims, defects by kind, all three guard counts per
key (plus `language_after_release`), fallback count, shown lengths, V6 stream seconds versus
package streams, fallback/total seconds, first shown versus package first token,
chunks/token-cap proxies, copied-passage indicator, same-context counts/primary,
M2 right declines where no reference exists, and all retests/bridges/admission.
Chunk counts are a token-cap proxy, not tokenizer measurements. Fallback-inclusive
total and first-shown times must accompany any comparison of V6-only stream time.
Per key, medians and p90 cover R's `first_shown_sec`, full buffering's observed
answer-part end, or fallback first shown on the same clock (`full_buffer_sec`),
whole answer including fallback (`total_sec`),
V6-only duration, and the package first character/whole answer from `stages.jsonl`.
Print these over all batches and clean batches. Count prefix-versus-whole
disagreements (released but whole fails; early fallback but whole passes) on the
stored raw answer and count `language_after_release`; an ungenerated continuation
cannot be included. Retain each batch's idle readings beside timing.

Detectable paired changes are approximately `2.8*sqrt(d/n)`, where `d` is the
discordant-pair fraction: at 200 pairs about 6/9/11 percentage points for
d=0.1/0.2/0.3; at 100 about 9/13/15. Clustering can increase these requirements;
the unchanged-context subset and 20 unanswerable questions have less power.
The supplied fit comparison changed 54/51/64 of 100 contexts W/C/A: last document
shortened in 48/47/54 and one dropped in 6/4/10. Thus unchanged subsets are about
46/49/36, about **95 pooled primary pairs**. The same formula at n=95 yields
approximately **9.1/12.8/15.7 percentage points** at d=0.1/0.2/0.3, before clustering.
Nine one-sided harm reads give a union-bound false-harm probability up to 22.5%
at 2.5% each; this conservative selection rule is not multiplicity-adjusted
confirmatory inference. Absence of detected harm is not equivalence/no harm.

Do not claim an independent test set, a full retrieval-path gain, a latency SLO,
widget quality, self-evaluation, routing, follow-up quality, exact language
identification, or an improvement on unmeasured bases. This is in-sample, one
unseeded generation per side (plus policy fallbacks), with the fixed judge;
author and judge share the session-model family (D12). No altered-defect
reclassification decides adoption. Context changes and fallback bias stay visible.

## Adoption, not implementation now (V8)

Only after row 3 and the subsequent adoption decision: change `agent/prompts.py`'s
`qa` to these V6 template bytes, move the pure shown-text function byte for byte,
and use it for both chat and widget `/api/ask`. Chat holds evidence until the
answer region, ends at the closing tag, stops/cuts a repeat, and uses the fresh
package fallback for parse/language. Ship exactly R0–R5, including completed-unit
holding, the 40-letter prefix check, irreversible release and late-language flag.
`/api/ask` uses the same function on finished text. Add `regex` to `requirements.txt`
at adoption, using the registered Unicode version. Add an E2E test for rule (a), verifying
that evidence, tags and text after the answer never reach the user, including
split streaming chunks. Replace published measured WixQA, ConditionalQA and
aircargo numbers with V6's actual results, keeping timing/fallback/context caveats.
Name the SLO after its measured outcome (shown-answer quality on paired package
contexts), not a model/prompt version. Its target comes from the registered
reading, not this draft's forecast. Otherwise the package stays; the next quality
step is the generator pilot. No product/adoption code is part of this change.

## Records and data-free verification (V9–V10)

Public: `reports/answer-prompt-v6/2057ad0/` for WixQA/ConditionalQA and
`reports/answer-prompt-v6/138f3b3/` for aircargo: replay summaries, per-key receipts,
judge exports plus `.cases.jsonl`, bridges, and partial/final reading records.
Only ids, hashes, fixed protocol labels/flags and numbers, checked with
`stage2_common.without_text`; explanatory limitations belong in this spec.
Never commit questions, document names/passages, answers, references, raw replies,
CLI journals, private config, or archives. Case exports use the frozen exporter's
text stripping as well. Preserve all failed runs, with NOT_EVIDENCE and reason.

Private Mac: `/Users/julia/RAG_new_stage5/v6/<registration-seven>/<attempt>/<key>/`.
Private laptop: `D:/RAG_new_stage5_private/v6/transfers/<attempt>/<key>/` for runs,
and `D:/RAG_new_stage5_private/v6/<key>/judge/` for plans/journals; input config
and transfer archives under `D:/RAG_new_stage5_private/v6/`.
Bridge sources are read-only byte copies; source_gate checks their plan/reply
hashes against the committed export (exact source paths below). References remain
read-only and hash-pinned. Output must
be outside the repository/tool library/stands and disjoint from every source.

`tests/test_answer_prompt_v6.py` uses invented documents/questions only: parse,
quotes/citations, Latin/Cyrillic/Greek threshold edges, normalization, repeat
cutting, partial-token safety, fresh fallback, stalled stream ceiling, saved-run
refusals/parity, registration pins, request counts, bridge prefix, receipt
commit/hash gates, raw/shown binding, export tampering, clusters/M2, every table
row and early-harm precedence. It calls the real frozen judge planner/exporter
with synthetic isolated replies, never a live sender. The Git boundary alone
is replaced in receipt unit fixtures; live commands require actual HEAD bytes.
Use the isolated test command below so unrelated product autouse fixtures do not
load ML runtimes under the laptop's 1 GiB PythonMemoryGuard.

## Running it

These are **future operator commands after cold-read/registration**, not commands
executed in Task 11d. This delivery remains a draft and uncommitted. The one laptop
interpreter is `$V6Py = 'C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe'`:
Python 3.11.13, unicodedata 14.0.0, regex 2026.5.9 installed 2026-11-01; ruff and
pytest are present. Plan compares both Unicode versions with registration and
replay before grading. Operational pytest runs on the Mac; Task 11d separately
runs the requested local synthetic check.
Every block defines its own variables. No session-held Completed list is used.

### Public-input prerequisite and registration

The genuine stage-5 M1/M2 JSON and cases exports for WixQA/ConditionalQA must be
committed, **UTF-8/LF in both HEAD and the working tree**, with identical bytes.
Existing working copies may be CRLF: normalize them before committing and prevent
Git's CRLF conversion from recreating a difference. A clean Git status alone is
insufficient. These input exports are outside Task 11d's edit scope; never replace
their data. Check each required pair of files with this independent block:

```powershell
Set-Location D:/RAG_new
$V6Py = 'C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$Code = @'
from pathlib import Path
import subprocess
for base in ('wixqa', 'conditionalqa'):
    for metric in ('m1', 'm2'):
        for suffix in ('.json', '.cases.jsonl'):
            p = Path(f'reports/stage4-final/stage5/2057ad0/stage5-{base}-{metric}{suffix}')
            raw = p.read_bytes()
            assert not raw.startswith(b'\xef\xbb\xbf') and b'\r' not in raw, str(p)
            assert subprocess.check_output(['git', 'show', 'HEAD:' + p.as_posix()]) == raw
'@
& $V6Py -c $Code
if ($LASTEXITCODE -ne 0) { throw 'Package export prerequisite refused' }
```

After cold-read approval, change only the status line to the registered status.
Register explicit paths, including the driver; exclude CX_REPORT.

```powershell
Set-Location D:/RAG_new
$V6Py = 'C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
function Checked { & $args[0] $args[1..($args.Count-1)]; if ($LASTEXITCODE -ne 0) { throw 'Command refused' } }
$Tools = 'reports/answer-prompt-v6/tools'
$Spec = 'docs/specs/answer-prompt-v6.md'
$Test = 'tests/test_answer_prompt_v6.py'
$Private = 'D:/RAG_new_stage5_private/v6'
Checked $V6Py -c 'import sys, regex, unicodedata; print(regex.__version__, unicodedata.unidata_version); sys.exit((regex.__version__, unicodedata.unidata_version) != (''2026.5.9'', ''14.0.0''))'
Checked $V6Py -m ruff format --check $Tools $Test
Checked $V6Py -m ruff check $Tools $Test
Checked $V6Py -m py_compile "$Tools/shown_text.py" "$Tools/v6_common.py" "$Tools/v6_replay.py" "$Tools/v6_chain.py" "$Tools/v6_judge.py" "$Tools/v6_record.py" "$Tools/v6_key.py" $Test
Checked git diff --check
Checked git status --short
Checked git add -- $Spec "$Tools/qa_prompt_v6.txt" "$Tools/shown_text.py" "$Tools/v6_common.py" "$Tools/v6_replay.py" "$Tools/v6_chain.py" "$Tools/v6_judge.py" "$Tools/v6_record.py" "$Tools/v6_key.py" $Test
Checked git commit -m 'stage 5b: register answer V6 before requests'
$V6Sha = (git rev-parse HEAD).Trim()
New-Item -ItemType Directory -Force $Private
[IO.File]::WriteAllText("$Private/REGISTRATION_SHA", "$V6Sha`n", [Text.UTF8Encoding]::new($false))
Checked git archive --format=tar "--output=$Private/library.tar" $V6Sha
Checked scp "$Private/library.tar" "$Private/REGISTRATION_SHA" 'deproject-mac:/Users/julia/RAG_new_stage5/'
```

### Mac: script file, synthetic gate, complete preflight and detached attempt

Use native zsh. The interactive shell writes the file; nohup starts `zsh -e`
detached with stdin closed and output retained, so a shell hangup leaves the
attempt running. Do not install a SIGHUP handler: retain nohup's ignored SIGHUP.
Pass remaining keys and a unique attempt label. Never reuse a run output folder.
Measured on the Mac 2026-11-01: the ML interpreter is Python 3.11.15, regex
2026.5.9, unicodedata 14.0.0, with no pytest; the test-gate interpreter is Python
3.11.15, regex 2026.7.19, pytest 9.0.3, unicodedata 14.0.0 with the gate PYTHONPATH.
Use V6_TEST_PY for the synthetic suite because V6_PY has no pytest; retain V6_PY
for --check and the chain so their actual Unicode versions must match registration.

```zsh
cat > /Users/julia/RAG_new_stage5/run-v6.zsh <<'ZSH'
set -o pipefail
V6_SHA=$(cat /Users/julia/RAG_new_stage5/REGISTRATION_SHA)
V6_ROOT=/Users/julia/RAG_new_stage5/v6/${V6_SHA:0:7}
V6_PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python
V6_TEST_PY=/Users/julia/RAG_new_gr4_venv/bin/python
V6_KEYS=$1
V6_ATTEMPT=$2
mkdir -p "$V6_ROOT"
if [[ ! -d "$V6_ROOT/library" ]]; then
  mkdir "$V6_ROOT/library"
  tar -xf /Users/julia/RAG_new_stage5/library.tar -C "$V6_ROOT/library"
fi
V6_TOOLS=$V6_ROOT/library/reports/answer-prompt-v6/tools
V6_SPEC=$V6_ROOT/library/docs/specs/answer-prompt-v6.md
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1
cd "$V6_ROOT/library"
PYTHONPATH=/Users/julia/RAG_new_mf_gate_site "$V6_TEST_PY" -m pytest --noconftest -q -p no:cacheprovider tests/test_answer_prompt_v6.py
"$V6_PY" -u "$V6_TOOLS/v6_chain.py" --check --keys "$V6_KEYS" --out "$V6_ROOT/check-$V6_ATTEMPT" --spec "$V6_SPEC" 2>&1 | tee -a "$V6_ROOT/check.log"
"$V6_PY" -u "$V6_TOOLS/v6_chain.py" --keys "$V6_KEYS" --out "$V6_ROOT/$V6_ATTEMPT" --spec "$V6_SPEC"
test -f "$V6_ROOT/$V6_ATTEMPT/CHAIN_COMPLETE"
ZSH
nohup zsh -e /Users/julia/RAG_new_stage5/run-v6.zsh wixqa,conditionalqa,aircargo attempt-01 > /Users/julia/RAG_new_stage5/v6-attempt-01.out 2>&1 < /dev/null &
```

One laptop poll, no loop (replace `attempt-01` consistently for another attempt):

```powershell
Set-Location D:/RAG_new
ssh -o BatchMode=yes -o ConnectTimeout=20 deproject-mac 'r=$(cut -c1-7 /Users/julia/RAG_new_stage5/REGISTRATION_SHA); d=/Users/julia/RAG_new_stage5/v6/$r/attempt-01; find "$d" -type f \( -name CHAIN_COMPLETE -o -name STOP -o -name FAILED.json \) -print; tail -n 3 /Users/julia/RAG_new_stage5/v6-attempt-01.out'
```

Terminal states: **CHAIN_COMPLETE** means transfer completed keys; **STOP** means
read its reason before any further work; **FAILED.json** means read that key's
failure record. STOP and FAILED.json may coexist; read both. No marker means the
attempt has not reached a recorded terminal state; the last three log lines show
progress or an early preflight refusal.

### Laptop: exact private inputs

These sources are read-only byte copies. `source_gate` compares their plan/reply
hashes with the committed exports. The aircargo folder was copied by the operator
on 2026-11-01; its `plan.json` SHA is
`84805c90506941a9880790b2b424cdbbcdb54b511bc3946c4522ba3160c1dcc1`,
`verdicts.jsonl` SHA is
`a88dc88ec8e7bed98b78f7e3b7fe3552519a804caa53eba2abc519abbe567724`,
matching committed `final-aircargo-m1.json`; it also contains `grade-clock.json`.

```powershell
Set-Location D:/RAG_new
$Private = 'D:/RAG_new_stage5_private/v6'
$Package5 = 'D:/RAG_new_stage5_private/2057ad0'
$Inputs = @{}
foreach ($Base in @('wixqa', 'conditionalqa')) {
    $Inputs[$Base] = @{
        old_m1="reports/stage4-final/stage5/2057ad0/stage5-$Base-m1.json"
        old_m2="reports/stage4-final/stage5/2057ad0/stage5-$Base-m2.json"
        source="$Package5/judge/$Base-m1"
        references="$Package5/references/$Base.jsonl"
    }
}
$Inputs.aircargo = @{
    old_m1='reports/stage4-final/138f3b3/final-aircargo-m1.json'
    source='D:/RAG_new_stage5_private/v6/sources/aircargo-m1'
}
[IO.File]::WriteAllText("$Private/inputs.json", (($Inputs | ConvertTo-Json -Depth 6) -replace "`r`n", "`n") + "`n", [Text.UTF8Encoding]::new($false))
```

### Laptop: transfer one completed key from its explicit attempt

Edit Key/Attempt only. Transfer once; never copy a live key or overwrite retained runs.

```powershell
Set-Location D:/RAG_new
function Checked { & $args[0] $args[1..($args.Count-1)]; if ($LASTEXITCODE -ne 0) { throw 'Command refused' } }
$Private = 'D:/RAG_new_stage5_private/v6'
$Key = 'wixqa'
$Attempt = 'attempt-01'
$V6Sha = (Get-Content -LiteralPath "$Private/REGISTRATION_SHA" -Encoding UTF8 -Raw).Trim()
$Remote = '/Users/julia/RAG_new_stage5/v6/' + $V6Sha.Substring(0, 7)
$Runs = "$Private/transfers/$Attempt/$Key"
if (Test-Path -LiteralPath $Runs) { throw 'Fresh transfer folder required' }
New-Item -ItemType Directory -Force "$Private/transfers/$Attempt"
Checked ssh deproject-mac "test -f $Remote/$Attempt/$Key/COMPLETE && COPYFILE_DISABLE=1 tar -czf $Remote/$Attempt-$Key.tar.gz -C $Remote/$Attempt $Key"
Checked scp "deproject-mac:$Remote/$Attempt-$Key.tar.gz" "$Private/$Attempt-$Key.tar.gz"
Checked "$env:SystemRoot/System32/tar.exe" -xf "$Private/$Attempt-$Key.tar.gz" -C "$Private/transfers/$Attempt"
```

### Laptop: one foreground chunk, resumable across sessions

The first call freezes and returns 4: commit its receipt/public replay and rerun.
Exit 3 means rerun the same call. The Mac STOP target names the **active attempt**,
even when the key came from an earlier one. Code 1 requires diagnosis; after code 5
and diagnosis, rerun with `--resume-unavailable`. Neither touches the Mac STOP.
Code 2 means the stop was propagated; code 6 means touch the named Mac STOP by hand.

```powershell
Set-Location D:/RAG_new
$V6Py = 'C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$Private = 'D:/RAG_new_stage5_private/v6'
$Key = 'wixqa'
$SourceAttempt = 'attempt-01'
$ActiveAttempt = 'attempt-01'
$V6Sha = (Get-Content -LiteralPath "$Private/REGISTRATION_SHA" -Encoding UTF8 -Raw).Trim()
$Remote = '/Users/julia/RAG_new_stage5/v6/' + $V6Sha.Substring(0, 7)
& $V6Py reports/answer-prompt-v6/tools/v6_key.py $Key --budget 840 --spec docs/specs/answer-prompt-v6.md --private $Private --records reports/answer-prompt-v6 --runs "$Private/transfers/$SourceAttempt/$Key" --config "$Private/inputs.json" --mac-stop "deproject-mac:$Remote/$ActiveAttempt/STOP"
Write-Output "Driver exit: $LASTEXITCODE"
```

The receipt commit is a separate explicit step:

```powershell
Set-Location D:/RAG_new
function Checked { & $args[0] $args[1..($args.Count-1)]; if ($LASTEXITCODE -ne 0) { throw 'Command refused' } }
$Key = 'wixqa'
$Stand = if ($Key -eq 'aircargo') { '138f3b3' } else { '2057ad0' }
$Public = "reports/answer-prompt-v6/$Stand"
Checked git status --short
Checked git diff --check
Checked git add -- "$Public/plans-$Key.json" "$Public/v6-$Key.json"
Checked git commit -m "stage 5b: freeze V6 $Key plans before grading"
```

Final reading derives keys from committed receipts, independent of shell state:

```powershell
Set-Location D:/RAG_new
$V6Py = 'C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$Records = 'reports/answer-prompt-v6'
$Private = 'D:/RAG_new_stage5_private/v6'
$Keys = @(git ls-tree -r --name-only HEAD -- $Records | Where-Object { $_ -match '/plans-(wixqa|conditionalqa|aircargo)\.json$' } | ForEach-Object { [IO.Path]::GetFileNameWithoutExtension($_).Substring(6) })
if ($LASTEXITCODE -ne 0 -or $Keys.Count -eq 0) { throw 'Committed receipts required' }
& $V6Py reports/answer-prompt-v6/tools/v6_record.py --private $Private --records $Records --spec docs/specs/answer-prompt-v6.md --keys ($Keys -join ',') --out "$Records/reading-final.json"
if ($LASTEXITCODE -notin @(0, 2)) { throw 'Reading refused' }
```

The driver stores run locations privately, so different keys can come from
different attempts. Review/commit only explicit public JSON/cases paths;
publication/adoption are separate. Never freeze an incomplete key or fill missing
verdicts. A 3x judge stop or harm stops the active Mac attempt. Unavailability
retains the frozen plan and journal; after exit 5 and diagnosis, rerun with
`--resume-unavailable`.


## SHA-256 registration list

The following pins cover every new tool, the test, and every explicitly imported
registered instrument. The test checks file bytes and LF; production registration
checks tool/frozen hashes before requests. Historic stand manifests separately
pin all product/transitive runtime files. Recalculate these entries only for an
explicit pre-request amendment; never silently accept different registered bytes.

<!-- SHA-PINS -->

- `evaluation/external_parts.py` `10e101f5e880a8448ff3fc45e27207d672a82bf7e9e478d2f0bbe53b662104de`
- `evaluation/semantic_ruler.py` `78477ebdb660af3a27d9210a318fae802bfa5230a7462954357e8be9f51d9a91`
- `reports/answer-prompt-v4/tools/bridge_plan.py` `41c72f480de3b093a74215d3ea89f00453c838cfaa27857e9c6f6c0d0701d244`
- `reports/answer-prompt-v4/tools/v4_record.py` `b518daf26ea36d2ecb753e22029c4ab780a56b39d1e174d01650b4050659bd6d`
- `reports/answer-prompt-v5/tools/replay.py` `ca954c59710e93925cc923f5b2a7f175ce86f7e1fa7b96a46d3b3bbeec4d6eed`
- `reports/answer-prompt-v5/tools/v5_record.py` `1e77dd35f011d274a165e7fda606d54fafbfd27a45c66154e791a645a23f7620`
- `reports/answer-prompt-v6/tools/qa_prompt_v6.txt` `a5eced6ee2a8ab4ad93a4db94462d40f8f5f8c5f0290917803eac9d91a56da62`
- `reports/answer-prompt-v6/tools/shown_text.py` `eb571e5ca935fb3729595b95dc785dae7097ae8ac135a78587ebf64cc370aedc`
- `reports/answer-prompt-v6/tools/v6_chain.py` `51f7b6352ab9a21b5d1fd4a82223d7d148e23f5e151b67f499ac54ccbc09f140`
- `reports/answer-prompt-v6/tools/v6_common.py` `a677fc27bbd873523524fecd4df2dbae8b4d6ba45b6b587d07376ec3f3d32e2c`
- `reports/answer-prompt-v6/tools/v6_judge.py` `609477a00f14e1b660a57c43b9ebaa9246c2c2f23d8c9170c05c2a2d5a09c6c3`
- `reports/answer-prompt-v6/tools/v6_key.py` `817a42c0bddae5968a4de5cb6702e0547b920f981b702e322ac64663e8f4c1c0`
- `reports/answer-prompt-v6/tools/v6_record.py` `059d4ce93a265b56ca992a2be9b64abd763e07564de2e67b5cacc59249c759ab`
- `reports/answer-prompt-v6/tools/v6_replay.py` `2a346517fa2c084c797e341758c73f2c5b2f2085df27367c276b391b1ce75c38`
- `reports/stage2/tools/judge_export.py` `d2a69975de960791c2b1aca8d93d58f75ef01c92c16686e12646473aea069193`
- `reports/stage2/tools/stage2_common.py` `4d5241560ab5425faa0a1fe6c5b856454b3f8ee47e59187f0da6644b1bad48da`
- `reports/stage4-final/tools/common.py` `0bcf149b359b7db5e20c550a6c7107cd89d3b400453fb808f58ae70a2e1890ed`
- `reports/stage4-final/tools/external/protocol.py` `9ff4ef2692cf9676e347f8b21e36738f29a58aba67db562c5dd54692e4bb7d4b`
- `reports/stage4-final/tools/judge.py` `8b96d7d3413cf7a5d978713046ff3620351647a058e00e2040beca31485cf336`
- `reports/stage4-final/tools/run.py` `d75cc1195a0258cbd78b049d434e15ab79439f2e96cef71838dba6a804481ff1`
- `reports/stage4-final/tools/stand.py` `2887646363fe9be5b148d0abc378492d53f51c1f9ebef874dc76516955bea29d`
- `scripts/chat_answer_judge.py` `cdb2be82d3341afe0b1aba4e560f56eac4e2dec9cce69d0e038a18da4f2c7788`
- `tests/test_answer_prompt_v6.py` `37b10e19840cc86d002a7fbc100a9a0155bbbf58c36e1a709d777120e4ab39b0`

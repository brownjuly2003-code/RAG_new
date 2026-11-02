# Stage 5: final external answers

The registered outcome is **holds**: **publish the package's numbers**.
The registered decision reads only the pooled WixQA + ConditionalQA M1 bad share. MultiHop-RAG is advisory.
The [registered spec](../specs/stage5-final-external.md) defines this decision.
Public files are in [the record directory](../../reports/stage4-final/stage5/2057ad0/).

WixQA's M1 good share falls, detected: 40.00% to 30.00% (n = 100).
This fall does not enter the registered decision. It is the main caveat of this record and a reason to examine WixQA's good answers in the next stage.

| Metric | Old hits / n (share) | Package hits / n (share) | Change, pp | read95, pp | Clusters | Detected | Direction |
|---|---:|---:|---:|---|---:|---|---|
| Pooled M1 bad | 108/200 (54.00%) | 112/200 (56.00%) | +2.00 | [-4.53, +8.51] | 137 | false | not detected |

## What was compared

The package at `2057ad0` answered the same question ids as stage 2.
The old side is V4 at `4f48fed` for WixQA and ConditionalQA, and V3 at `5e308fe` for MultiHop-RAG.
For WixQA and ConditionalQA, the difference is the package's retrieval and window change under the same prompt.
For MultiHop-RAG the comparison also includes the V3 to V4 prompt change.
This reads the whole package, without attributing the result to an individual change.

The reader's legacy v3/v4 fields mean old/new here. Shares use their paired n; changes and read95 are in percentage points.
read95 spans the cluster and Newcombe intervals. A change is detected only when both intervals exclude zero in the same direction.

## What ran

The Mac answered 100 questions per base on the package's own stand from 2026-10-31 14:21 UTC.
Three receipts froze the judge plans before grading: `da0988a` (WixQA), `bd18bce` (ConditionalQA) and `42dcd1a` (MultiHop-RAG).
The laptop judge graded every plan in foreground chunks from 2026-11-01 to 2026-11-02 UTC; no plan stopped, and every export exited 0.
The laptop wrote the exports with CRLF line ends; they were normalized to LF, each parsing the same, before the read.
The registered read ran on 2026-11-02 and gave the same bytes as a dry read to a scratch path before it.

## Paired M1, M2 and M3 reading

M1 grades answers without references. M2 measures agreement with references, or a right decline without one.
M3 measures deterministic gold coverage in sent context. The judge's context_has_answer is a separate reading.

| Metric | Old hits / n (share) | Package hits / n (share) | Change, pp | read95, pp | Clusters | Detected | Direction |
|---|---:|---:|---:|---|---:|---|---|
| WixQA M1 bad | 51/100 (51.00%) | 59/100 (59.00%) | +8.00 | [-1.24, +16.97] | 77 | false | not detected |
| WixQA M1 good | 40/100 (40.00%) | 30/100 (30.00%) | -10.00 | [-18.56, -1.21] | 77 | true | falls |
| ConditionalQA M1 bad | 57/100 (57.00%) | 53/100 (53.00%) | -4.00 | [-13.13, +5.27] | 60 | false | not detected |
| ConditionalQA M1 good | 35/100 (35.00%) | 38/100 (38.00%) | +3.00 | [-5.23, +11.17] | 60 | false | not detected |
| WixQA M2 agrees | 34/100 (34.00%) | 34/100 (34.00%) | +0.00 | [-7.95, +7.69] | 77 | false | not detected |
| ConditionalQA M2 agrees | 48/80 (60.00%) | 47/80 (58.75%) | -1.25 | [-7.16, +4.68] | 40 | false | not detected |
| WixQA M3 sent | 68/100 (68.00%) | 67/100 (67.00%) | -1.00 | [-5.07, +3.04] | 77 | false | not detected |
| ConditionalQA M3 sent | 60/80 (75.00%) | 58/80 (72.50%) | -2.50 | [-7.25, +2.05] | 40 | false | not detected |

| Base | Context pairs, n | Same | Lost | Gained | Empty package answers / n |
|---|---:|---:|---:|---:|---:|
| WixQA | 100 | 98 | 1 | 1 | 0/100 |
| ConditionalQA | 100 | 97 | 3 | 0 | 0/100 |

WixQA M2: with reference 100/100 paired, 0 unpaired; without reference 0/0 paired, 0 unpaired, right declines old/new 0/0 and 0/0.
WixQA M3: holds; without gold 0/100. Mean covered fraction old/new 0.631667/0.631667 (n = 100).
ConditionalQA M2: with reference 80/80 paired, 0 unpaired; without reference 20/20 paired, 0 unpaired, right declines old/new 4/20 and 5/20.
ConditionalQA M3: holds; without gold 20/100. Mean covered fraction old/new 0.833676/0.806369 (n = 80).

## MultiHop-RAG

**NOT_EVIDENCE**: `NOT_EVIDENCE: bridge stability failed`.
The bridge checks judge drift by re-grading kept stage 2 replies to the old requests.
The following figures come from the committed bridge exports, whose hashes the final record names.

| Bridge | Planned pairs | Agree / n | Two steps apart / n | Quadratic kappa | ci95 | Pass by kappa | Pass by agreement | Passed |
|---|---:|---:|---:|---:|---|---|---|---|
| WixQA | 15 | 15/15 | 0/15 | 1.0000 | [1.0000, 1.0000] | true | true | true |
| ConditionalQA | 15 | 13/15 | 1/15 | 0.8260 | [0.4878, 1.0000] | true | false | true |
| MultiHop-RAG | 15 | 12/15 | 3/15 | 0.3284 | [0.0000, 1.0000] | false | false | false |

MultiHop-RAG has enough pairs: true (n = 15). Its scale is bad / partial_ok / good.
All 3/15 two-step changes are bad to good (first grade, retest grade). There were 90 undefined bootstrap resamples.
MultiHop-RAG field agreement: answers_question 15/15; context_has_answer 15/15; defect 14/15; reference 0/0.
The record retains a new, unpaired advisory M2 reading for MultiHop-RAG. It supplies no admitted old-versus-new result here.

## Stand and provenance

STAGE5_SHA is `2057ad0e5733fbf18d6f199a0cfd94927aec85d8`; item 6 is `138f3b3f6ac223540965cc831838ff4f671a2200`.
K 14, window 3,584, input limit 2,176, rerank top 5; prompt `QA_PROMPT_V4`.
The INT8 reranker runs in `onnx` from `/Users/julia/RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx`.
The answer model is `qwen3:4b-instruct-2507-q4_K_M`; ONNX Runtime 1.23.2, transformers 4.44.2.
Both offline flags are `1`. The checked cache configuration has `cache-ram = 1024`.
One judge model graded both sides: `claude-opus-5-5` at effort `max`. The bridge is a stability check, not a second judge.
The operator reports that the laptop read used Python 3.11.13.

The [artifact test](../../tests/test_stage5_final_artifact.py) pins every public file's SHA-256 and LF bytes, binds the baseline and receipts, and rebuilds the reading.
The corpus and cases hashes below come from baseline.json and match each answer record's provenance.

| Base | Corpus manifest SHA-256 | Chunks report SHA-256 | Index receipt SHA-256 | Cases SHA-256 |
|---|---|---|---|---|
| WixQA | `aeabd28fd61d4dfe9d95aa093a2efd1c383e8cef7f26dedac8153f9e97d24e24` | `d167bb78a119c6932340e60be9592191d1200c2ce4d9d14c2b6328af85a921a9` | `8dc009a68900a07502d59d199e8da476abb19de65f5dceb4692d25d4f9bb35f8` | `d18255995e045c791849db44fb940182f9573056ff3eb11578acb8bf69c20412` |
| ConditionalQA | `25c4b33f5cd5ee385317183ae56e2c101019c2c81907599988a379fe2e99115b` | `cf5ed1be7d8b99922395f7bc765a19a6279887af61fd7c9f2b125bd6838cf2d1` | `3fce93e02bbedb03058587b850b2ae73ede66dc89536d2e75763430de4d7abbf` | `8467991cdb095fe1e2204d8eca90679da56f0bac53e3c81686d488cca59eb6b7` |
| MultiHop-RAG | `3d8de600c4082bc876919b61594ead37e51a6d70d25edcb1694e3b0eb60f26fc` | `cefcfbd1c812e7faa6acaf872b0582dc9ccdaa89125d693f5ead794dbe929259` | `d1662e2ff7b587bc4484cf4405ac561a931da838c273aeb686ee7da55ab6a37a` | `cf5f6462b30cac0d6f1b59cff722106001140baee01f003567fb34001c109fac` |

The test reuses saved M3 measurements. Repeating the context measurement itself needs private corpora and prompts.
Raw questions, answers, source text and judge requests remain private. Public ids are allowed by the registered spec.
The reference field may contain only the frozen judge schema's labels, not reference answer text.

## What it does not say

Each base has 100 questions; intervals account for clusters.
These reused questions are not an independent test set. The bridge bounds judge drift; it does not supply human validation.
No person graded anything (owner's decision D11).
"Not detected" does not mean "no difference".

# Stage 7, step 1: S' after the coherence fix — a context defect remains

**S' has a detected loss at ConditionalQA and at the deciding bases pooled.** Under
[Amendment 2](../specs/stage7-step1-arms-m3.md#amendment-2-2026-11-06-s--the-structural-lane-after-the-coherence-fix),
this is a defect of the lane to find and fix before answers. The owner's word turns the graph on;
this reading is not a reason to keep it off. As
[Amendment 3](../specs/stage7-step1-arms-m3.md#amendment-3-2026-11-06-s--the-structural-lane-with-the-products-parent-expansion)
explains, S' joined only its seed's section run and skipped the parent expansion H uses.
The chunk medians below expose that missing context. Amendment 3 registers the product fix,
S'', and its new score/replay run; that run will have its own capsule.

Her word of 2026-11-06 was «графовый поиск нужно включить». The coherence fix of `98e5bf0`
keeps H_new's five in H_new's order before section expansion. Amendment 2 was registered in
`98e5bf0` before this Mac run of score and replay on 2026-11-06. The replay tool was unchanged.
The [record](../../reports/stage7/98e5bf0-a2/record.json) measures S'; the
[earlier record](../../reports/stage7/5e308fe/record.json) measures S of 2026-10-31.
The [artifact test](../../tests/test_stage7_sprime_record_artifact.py) binds the files and
provenance, parses every table, rebuilds its values from these records and applies the existing
text guard. It needs no model, private archive or retrieval run.

## Provenance and parity

Stage-2 source stand `5e308fe48cca0955c3007057a574a425f71e2a6a`; V4 source stand `4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1`.
Measured HEAD `22822a278b521b6f46bbbf9c45f8ae19514bfa46`, parent `be13ac2a105487fc84ddbe48240fd6058fe423e1`.
Subject: `mf-gate overlay of be13ac2a105487fc84ddbe48240fd6058fe423e1`.
This is the overlay of the post-`98e5bf0` parent, not a claim that the measured HEAD equals
the registering commit. The recorded parent `be13ac2` descends from `98e5bf0`, the commit
that registered Amendment 2. The test reads the spec, the tool, the replay test and every
measuring-code file at that parent and checks them against the header and Amendment 2's list.

Header spec SHA-256: `ed4e5c0139dff6f537cc9e6ffd5f7a593530bf34f7a8e702c9da3f7a1b07c26e`.
Header tool SHA-256: `6ca8b723841d08dfd6f5d084bdc0883264c889eb495dc4d3728ac0a2ea623689`.
Amendment 2's test SHA-256: `4deb3db4e3f258af9c8851d824dc126df5399be1face1dcbe0dbed4267627e03`.
The tool digest equals Amendment 2's SHA list. The header's `measure_code_sha256` map
contains neither the replay tool nor its test: the tool has its own field, and the test
digest is absent. The test digest above is verified against the registered list and the
recorded parent's history, not represented as a hash recorded in the header. The spec hash
binds the run's version, before Amendment 3; the current spec has later amendments.

H is H_new: K 14, 5 kept, window 3,584, input limit 2,176, runtime `onnx`.
INT8 export `57335a9f061fe31378c160ddd0861711a0fbdfa20f70aa2640d473dfc4bc1343`; effective batch 32, no RAG_RERANK_BATCH override.
The run uses Amendment 1's service environment and offline recipe, as published in the
[earlier capsule](stage7-step1-arms-record.md#provenance-and-method).
The old-control parity gate uses K 20, recorded PyTorch scores, window 4,096 and input limit 2,636.
It checks recorded pools, fives, expansions, V3 sent documents and prompt bytes against the
export, then the saved V4 prompt bytes, before either arm is read.
Parity passed 415 of 415; V4 prompts byte-equal 300 of 300; breaks 0.

## H against S' and P

The primary hit is WixQA's `gold_article`, otherwise `all_evidence_coverage`; secondary
means are `gold_articles` and `evidence_recall`, respectively. Here b is H-only, c arm-only.
P's rule is rel 0.2; each primary pair reads loss or gain only at p < 0.05.
The exact two-sided McNemar p is printed to the record's precision; a rounded zero is
shown as <0.000001. No pooled secondary mean is defined. Counts use available gold;
no pair with available gold was unread. ConditionalQA, WixQA and their pool at sent are
the stop readings. Expanded, MultiHop-RAG and all three pooled stand beside, advisory.

| Arm and base | Point | n | H → arm hits | b / c | p | Reading | Secondary mean H / arm |
|---|---|---|---|---|---|---|---|
| S': WixQA | sent | 100 | 67 → 68 | 0 / 1 | 1 | no detected difference | 0.6317 / 0.6417 |
| S': WixQA | expanded | 100 | 68 → 68 | 0 / 0 | 1 | no detected difference | 0.6417 / 0.6417 |
| S': ConditionalQA | sent | 80 | 58 → 45 | 13 / 0 | 0.000244 | loss | 0.8064 / 0.7178 |
| S': ConditionalQA | expanded | 80 | 58 → 45 | 13 / 0 | 0.000244 | loss | 0.8064 / 0.7178 |
| S': MultiHop-RAG | sent | 70 | 4 → 2 | 2 / 0 | 0.5 | no detected difference | 0.4321 / 0.3845 |
| S': MultiHop-RAG | expanded | 70 | 11 → 12 | 0 / 1 | 1 | no detected difference | 0.5179 / 0.5226 |
| S': Deciding bases | sent | 180 | 125 → 113 | 13 / 1 | 0.001831 | loss | — |
| S': Deciding bases | expanded | 180 | 126 → 113 | 13 / 0 | 0.000244 | loss | — |
| S': All three | sent | 250 | 129 → 115 | 15 / 1 | 0.000519 | loss | — |
| S': All three | expanded | 250 | 137 → 125 | 13 / 1 | 0.001831 | loss | — |
| P: WixQA | sent | 100 | 67 → 66 | 1 / 0 | 1 | no detected difference | 0.6317 / 0.6217 |
| P: WixQA | expanded | 100 | 68 → 67 | 1 / 0 | 1 | no detected difference | 0.6417 / 0.6317 |
| P: ConditionalQA | sent | 80 | 58 → 55 | 3 / 0 | 0.25 | no detected difference | 0.8064 / 0.7945 |
| P: ConditionalQA | expanded | 80 | 58 → 55 | 3 / 0 | 0.25 | no detected difference | 0.8064 / 0.7945 |
| P: MultiHop-RAG | sent | 70 | 4 → 4 | 0 / 0 | 1 | no detected difference | 0.4321 / 0.4321 |
| P: MultiHop-RAG | expanded | 70 | 11 → 11 | 0 / 0 | 1 | no detected difference | 0.5179 / 0.5131 |
| P: Deciding bases | sent | 180 | 125 → 121 | 4 / 0 | 0.125 | no detected difference | — |
| P: Deciding bases | expanded | 180 | 126 → 122 | 4 / 0 | 0.125 | no detected difference | — |
| P: All three | sent | 250 | 129 → 125 | 4 / 0 | 0.125 | no detected difference | — |
| P: All three | expanded | 250 | 137 → 133 | 4 / 0 | 0.125 | no detected difference | — |

## S' beside S of 2026-10-31

H's primary counts and n are equal in the two records. The old b, c and p below compare
H with old S; the corresponding H/S' pairs are above. This is a comparison of recorded
readings, not a newly computed paired significance test between S and S'.

| Base | Point | n | H hits (both runs) | S (2026-10-31) hits | S' hits | H vs S b / c | H vs S p |
|---|---|---|---|---|---|---|---|
| WixQA | sent | 100 | 67 | 60 | 68 | 7 / 0 | 0.015625 |
| WixQA | expanded | 100 | 68 | 60 | 68 | 8 / 0 | 0.007812 |
| ConditionalQA | sent | 80 | 58 | 39 | 45 | 19 / 0 | 0.000004 |
| ConditionalQA | expanded | 80 | 58 | 39 | 45 | 19 / 0 | 0.000004 |
| MultiHop-RAG | sent | 70 | 4 | 1 | 2 | 3 / 0 | 0.25 |
| MultiHop-RAG | expanded | 70 | 11 | 4 | 12 | 7 / 0 | 0.015625 |
| Deciding bases | sent | 180 | 125 | 99 | 113 | 26 / 0 | <0.000001 |
| Deciding bases | expanded | 180 | 126 | 99 | 113 | 27 / 0 | <0.000001 |
| All three | sent | 250 | 129 | 100 | 115 | 29 / 0 | <0.000001 |
| All three | expanded | 250 | 137 | 103 | 125 | 34 / 0 | <0.000001 |

The coherence fix recovers context hits, but ConditionalQA and the deciding pool still
show a loss. S' kept all 5 seeds on all 415 questions, with no drops or reordering.
Keeping the same seeds did not assemble the same documents: S' stopped at section
boundaries, while H's parent expansion also joined neighbouring chunks across them.
Amendment 3 corrects Amendment 2's reading of the same-five rule and registers S''.

## Context sent, with expansion beside

These are medians from `record.json`'s `labels`, over each complete label, not only its
gold-bearing questions. Sent columns use `sent_documents`, `sent_chunks` and
`sent_est_tokens`; expanded chunks use `chunks`, before the input-window cut. Estimated
tokens describe the sent context, not the full prompt or a tokenizer's exact token count.
The aircargo labels stay separate; their medians are not pooled or averaged.

| Base / label | Questions | Sent documents H / S' | Sent chunks H / S' | Sent estimated tokens H / S' | Expanded chunks H / S' | S' changed prompts |
|---|---|---|---|---|---|---|
| WixQA | 100 | 5 / 5 | 16 / 6 | 1729.5 / 801.5 | 17 / 6 | 100 |
| ConditionalQA | 100 | 5 / 5 | 16 / 5 | 1673.5 / 677 | 17 / 5 | 100 |
| MultiHop-RAG | 100 | 3 / 3 | 13 / 14 | 1711 / 1733 | 18 / 25 | 94 |
| aircargo | 100 | 3 / 5 | 13 / 6 | 1783.5 / 1323 | 21 / 6 | 100 |
| aircargo-gr | 15 | 2 / 5 | 10 / 7 | 1786 / 1651 | 25 / 7 | 15 |

Of the 300 questions with saved V4 prompts, S' changes 300 prompts and P changes 61 against H_new.
These are comparisons with H_new, not with the saved V4 bytes. Shorter contexts do not
establish better retrieval: the chunk medians support the missing-expansion diagnosis.

## G1 as printed — advisory for S'

The tool retains the key `S` for S'. Its decision field is:

```json
{"standings": {"S": "stopped", "P": "open"}, "gains": {"S": [], "P": []}, "arm": null, "reading": "H stays"}
```

Under Amendment 2 this field is advisory for S': readings publish the lane's effect on
context under rule (c). A detected loss at a stop reading must be fixed before answers;
the field does not decide whether the graph is turned on. P retains Amendment 1's meaning:
it is open but has no qualifying gain. The recorded judge field is null. Amendment 2
provides no aircargo context-judge plan for S'; changed prompts do not open a judge run.

## What it does not say

No answer quality was measured. This is a structural lane replay over archived metadata,
with no links, entities or categories; it does not establish the live chat route's quality.
No fresh index search was made: recorded lane prefixes need not equal a fresh approximate search.
M3 is bounded by available external gold; missing gold is not a miss. Aircargo has no
context gold here, so its changed prompts and context sizes are descriptive only.
No detected difference is not equivalence. A smaller loss than old S is still a defect.
The diagnosis is Amendment 3's code finding, not a causal inference from medians alone;
this capsule does not report S'' results or prove parent expansion across sections correct.

## Files

Under `reports/stage7/98e5bf0-a2/`. These SHA-256 digests bind the six copied files.
They contain ids, flags, counts, hashes, chunk positions, scores and durations, never
question, answer, document or filled-prompt text. No new environment paths are published.

| File | SHA-256 |
|---|---|
| `int8_scores.jsonl` | `9d1c77c53d88cbf09bf09e4244d25006b79fe336987a44fd86c82e49d77f1fd0` |
| `parity.jsonl` | `073cf545aec63c66965a7b999d1a8d01d43b1ab70eb6616eed0400234c71bb26` |
| `record.json` | `0c360ded3ecfcedc1c5c2e97d0765729ca16fd42e8d0c6d22c624edc055443aa` |
| `replay.out` | `d5dbe60eb2cd857eb24fcc31940ebaf2f8de745597d11c6cee01335f6b703b75` |
| `rows.jsonl` | `c4dc3b375bf1747edd867b61ee7db8f2d772ea0af816fa0caeb0988534553b43` |
| `score.out` | `9de140f943a62720543b907a57498e545573051806ad72208a26cc6be508122d` |

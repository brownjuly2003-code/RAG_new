# Stage 7, step 1: Amendment 1's arms at M3 — H stays

**H stays.** S is stopped by a detected loss; P remains open but has no detected gain.
No arm qualifies: no judge plan, no PRIVATE folder and no judged step; no laptop judging step or arm answer run follows.
This closes stage 7 by its registered gate. It does not establish that the arms can never help.

The [spec](../specs/stage7-step1-arms-m3.md), Amendment 1, was registered in `6c52b06` before
the run. Its control is the stage-4 package. The old control remains the byte-parity gate.
The [record](../../reports/stage7/5e308fe/record.json) is the replay's final decision.
The [artifact test](../../tests/test_stage7_arms_record_artifact.py) checks the six files by
hash, provenance, logs, privacy, all external pairs, the advisory comparison and label spreads.
It rebuilds the tables and numeric prose below. It does not rerun retrieval or load a model.

## Provenance and method

Stage-2 source stand `5e308fe48cca0955c3007057a574a425f71e2a6a`; V4 source stand `4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1`.
Measured HEAD `f59169310a026f8962cfdfed01b573be28b9becc`, parent `f2b878ca594779fa03b2561bc271c4cbe88970cb`.
Subject: `mf-gate overlay of f2b878ca594779fa03b2561bc271c4cbe88970cb`.
The operator reports a clean checkout and the spec's service `env -i` recipe.

H is H_new: K 14, 5 kept, window 3,584, input limit 2,176, runtime `onnx`.
INT8 export `57335a9f061fe31378c160ddd0861711a0fbdfa20f70aa2640d473dfc4bc1343`; effective batch 32, no RAG_RERANK_BATCH override.
Service Python `/Users/julia/RAG_Support_Assistant/.venv/bin/python`; transformers 4.44.2, tokenizers 0.19.1, ONNX Runtime 1.23.2.
HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1; tokenizer snapshot `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`.
ORT module `/Users/julia/RAG_new_mf_gate_site/onnxruntime/__init__.py`; intra-op thread setting 0 (automatic).

The old-control parity gate uses K 20, recorded PyTorch scores, window 4,096 and input limit 2,636.
It checks the recorded pools, fives, expansions and V3 sent documents and prompts against
the export, then the saved V4 prompts byte for byte, before the arms are read.
Parity passed 415 of 415; V4 prompts byte-equal 300 of 300; breaks 0.

H_new uses the recorded lane prefixes, fresh INT8 scores, parent expansion and V4's fitted
prompt. S uses H_new's pool and five, section coherence and section expansion; P uses P1b.
P's rule is rel 0.2; each primary pair reads loss or gain only at p < 0.05.
Of the 300 questions with saved V4 prompts, S changes 300 prompts and P changes 61 against H_new.
These counts are not comparisons of H_new with the saved V4 bytes.

## The arms' reading

The primary hit is WixQA's `gold_article`, otherwise `all_evidence_coverage`. The secondary
mean is WixQA's `gold_articles`, otherwise `evidence_recall`; every mean uses the row's n.
Here b is H-only and c arm-only. The exact two-sided McNemar p is printed to the record's
precision; a rounded zero is shown as <0.000001. No pooled secondary mean is defined.
The deciding bases are ConditionalQA and WixQA. Their sent readings, individually and pooled,
can stop an arm; only a qualifying pooled gain opens answers. Expanded and MultiHop-RAG
stand beside. All three pooled is advisory. No pair with available gold was unread.

| Arm and base | Point | n | H → arm hits | b / c | p | Reading | Secondary mean H / arm |
|---|---|---|---|---|---|---|---|
| S: WixQA | sent | 100 | 67 → 60 | 7 / 0 | 0.015625 | loss | 0.6317 / 0.5517 |
| S: WixQA | expanded | 100 | 68 → 60 | 8 / 0 | 0.007812 | loss | 0.6417 / 0.5517 |
| S: ConditionalQA | sent | 80 | 58 → 39 | 19 / 0 | 0.000004 | loss | 0.8064 / 0.6373 |
| S: ConditionalQA | expanded | 80 | 58 → 39 | 19 / 0 | 0.000004 | loss | 0.8064 / 0.6373 |
| S: MultiHop-RAG | sent | 70 | 4 → 1 | 3 / 0 | 0.25 | no detected difference | 0.4321 / 0.3310 |
| S: MultiHop-RAG | expanded | 70 | 11 → 4 | 7 / 0 | 0.015625 | loss | 0.5179 / 0.4298 |
| S: Deciding bases | sent | 180 | 125 → 99 | 26 / 0 | <0.000001 | loss | — |
| S: Deciding bases | expanded | 180 | 126 → 99 | 27 / 0 | <0.000001 | loss | — |
| S: All three | sent | 250 | 129 → 100 | 29 / 0 | <0.000001 | loss | — |
| S: All three | expanded | 250 | 137 → 103 | 34 / 0 | <0.000001 | loss | — |
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

S loses on both deciding bases and their pool. P has no detected difference anywhere;
remaining open is insufficient, because the gate requires a detected gain above the MDE.

## The package beside the arms — advisory

This compares H_old with H_new, with b old-only and c new-only.
The advisory comparison decides nothing; it does not isolate a lever's effect.

| Base | Point | n | H_old → H_new hits | b / c | p | Reading | Secondary mean old / new |
|---|---|---|---|---|---|---|---|
| WixQA | sent | 100 | 68 → 67 | 2 / 1 | 1 | no detected difference | 0.6317 / 0.6317 |
| WixQA | expanded | 100 | 68 → 68 | 1 / 1 | 1 | no detected difference | 0.6317 / 0.6417 |
| ConditionalQA | sent | 80 | 60 → 58 | 2 / 0 | 0.5 | no detected difference | 0.8337 / 0.8064 |
| ConditionalQA | expanded | 80 | 60 → 58 | 2 / 0 | 0.5 | no detected difference | 0.8337 / 0.8064 |
| MultiHop-RAG | sent | 70 | 9 → 4 | 5 / 0 | 0.0625 | no detected difference | 0.4810 / 0.4321 |
| MultiHop-RAG | expanded | 70 | 13 → 11 | 3 / 1 | 0.625 | no detected difference | 0.5262 / 0.5179 |
| Deciding bases | sent | 180 | 128 → 125 | 4 / 1 | 0.375 | no detected difference | — |
| Deciding bases | expanded | 180 | 128 → 126 | 3 / 1 | 0.625 | no detected difference | — |
| All three | sent | 250 | 137 → 129 | 9 / 1 | 0.021484 | loss | — |
| All three | expanded | 250 | 141 → 137 | 6 / 2 | 0.289062 | no detected difference | — |

All-three sent: 137 → 129 of 250, p 0.021, a detected loss.
MultiHop-RAG carries most of that net loss: 9 → 4 of 70 sent; deciding bases 128 → 125 of 180, p 0.375, no detected difference.
All-three expanded: 141 → 137 of 250, p 0.289, no detected difference; MultiHop-RAG 13 → 11 of 70.
Most of MultiHop-RAG's net drop appears between expanded and sent, where the 2,176-token input limit cuts.
The two points do not establish a cause. Stage 5 measures what the package does to answers.

## Duration

The score journal has 415 question rows plus its header; the log ends complete at 415 questions.
Its first-ten forecast was 5,848.08 s; the stop was 17,544.23 s.
The 415 journal durations sum to 7,325 s; median 17.28 s, maximum 34.0 s.
The operator reports about 2 h 03 min wall time for score, including load, and 57 s for replay (exit 0) on 2026-10-31.
The wall times are operator observations outside the artifacts, whose logs carry no timestamps.
These are the run's durations only, not a speed claim under PLAN §4.3 M5.

## What it does not say

No answer quality was measured. One stand and one day do not establish general performance.
M3 is bounded by external_gold's available gold; missing gold is not a miss.
Aircargo has no context gold here and is read only by the parity gate; its arm spreads decide nothing.
No fresh index search was made: recorded lane prefixes need not equal a fresh approximate search.
No detected difference is not equivalence. The record measures context gold, not what an answer
model can use, nor the correctness of parent expansion across sections and gaps.

## Files

Under `reports/stage7/5e308fe/`. The Mac hashes matched the copied files. Rows contain ids,
flags, counts and hashes, never question, answer, document or filled-prompt text. The journal
also contains chunk positions, scores and durations. No PRIVATE contents were produced.

| File | SHA-256 |
|---|---|
| `int8_scores.jsonl` | `5c4d2bbcc42fe17afb516c877fdeacf7bc3bd05beb8557870b7d1f7bedb156a6` |
| `parity.jsonl` | `073cf545aec63c66965a7b999d1a8d01d43b1ab70eb6616eed0400234c71bb26` |
| `record.json` | `b9db1434a6091536540112591e29cb3f02f373660dd06469e6abebc3780b55e4` |
| `replay.out` | `893998a9b03e93794b3aae0458cb16b35dcff3dbc16340048d58bfdb25cb7b60` |
| `rows.jsonl` | `2d87859ecfd5e2442eefadcc5dafb471e5a80d13d8227907d59e568010109627` |
| `score.out` | `bc744b59934fc06309a8c4da15de02cc13c3373e788c70dafcdc669827537e3e` |

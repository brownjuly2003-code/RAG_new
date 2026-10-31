# Stage 4, item 6: final-path aircargo answers — 2026-10-31

The outcome is **gain detected**; stage 5 follows.
M1 good increased with both intervals above zero. Neither M1 bad nor M3 changed detectably;
no yes/no from Julia is needed under the registered rule. This reads the whole package against
V4's aircargo answers, not the contribution of any one lever.

Registered by [item 6's spec](../specs/stage4-item6-final-aircargo.md) in `ecc79dd`, corrected
in `138f3b3`, before the run. Public records are in
[`reports/stage4-final/138f3b3/`](../../reports/stage4-final/138f3b3/).
The [artifact test](../../tests/test_stage4_item6_final_artifact.py) pins their bytes, binds the
receipt and inputs, and rebuilds the reading with the committed reader and V4's paired rule.

## Stand and judge

Stand `138f3b3f6ac223540965cc831838ff4f671a2200` ran 100 aircargo questions in 10 batches of 10.
Each batch used a fresh API and started with the model unloaded, under the registered protocol.
K 14, window 3,584, input limit 2,176, and the INT8 reranker kept 5 chunks with the V4 prompt (`QA_PROMPT_V4`).
The answer model was `qwen3:4b-instruct-2507-q4_K_M`; Ollama was 0.33.2.
The service environment records transformers 4.44.2, tokenizers 0.19.1, and ONNX Runtime 1.23.2.
Both offline flags were `1`; the tokenizer snapshot was `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`.
The export SHA-256 was `57335a9f061fe31378c160ddd0861711a0fbdfa20f70aa2640d473dfc4bc1343`; the checked `cache-ram = 1024` file had SHA-256 `c75f44912ea2c7f54ea0cf0e9ffea8f05466ae447961d99c8f12d716589b4e6c`.

The judge had 100 first grades and 15 retests (115 requests), plus a 15-request V4 bridge.
The route was `claude-opus-5-5` at effort `max`; instructions and salt matched V4.
The public handover reading was unchanged. M3 is this same plan's `context_has_answer`,
not a separate context-judge plan. The bridge regraded V4's retested requests and replies.
The bridge agreed on 15 of 15 pairs; quadratic κ was 1.0, with interval [1.0, 1.0].
Admitted CLI versions: V4 2.1.310 (115 requests), package 2.1.312 (115 requests); the bridge used those respective versions.

## Paired reading

Old means V4 at `4f48fed`; new means the package. The intervals are paired cluster bootstrap
and Newcombe intervals. A difference counts only when both exclude zero on the same side.
The reader's legacy `v3`/`v4` field names mean old/new here, not prompt versions.

| Metric | V4 hits / n | Package hits / n | Change, pp | Cluster 95%, pp | Newcombe 95%, pp | Reading |
|---|---:|---:|---:|---|---|---|
| M1 good | 63/100 | 73/100 | +10.00 | [+2.00, +18.00] | [+1.66, +18.19] | gain detected |
| M1 bad | 17/100 | 13/100 | -4.00 | [-11.00, +3.00] | [-11.48, +3.24] | not detected |
| M3 context has answer | 100/100 | 99/100 | -1.00 | [-3.00, +0.00] | [-5.45, +2.79] | not detected |

M3's old side is at its ceiling, 100/100; only a detected fall could count as harm.
MDE ≈ 2.8 sqrt(d/100): 9, 13, 15 pp at discordance 0.1, 0.2, 0.3; smaller changes remain unresolved.
Not detected does not establish equality.

## Run duration and deviations

The registered answer forecast was 31,800 s; its series stop was 95,400 s.
The orchestrator reports from private logs and journals: answers ran on 2026-10-31 from
04:04:08Z to 11:27:58Z, for 26,630 s wall time, with 10 complete `FINAL_DONE` lines and a
passed answer gate. This quality run supplies a duration, not a speed claim.
The receipt was committed as `fcb4b5a` before grading. All 130 replies were valid on their
first attempt. Total spend was $20.02 (M1 $17.40, bridge $2.62). Persistent request clocks
held M1 6,728 s against a 14,950-s forecast and bridge 1,110 s against 1,950 s.

The orchestrator records two deviations before reading. macOS tar added 42 AppleDouble
`._*` entries to the private archive; the plan builder refused one as non-UTF-8. Rebuilding
under `COPYFILE_DISABLE=1` yielded 589 entries with no sidecars. Windows tar extracted it
into an empty private folder before the plan was built.
The frozen M1 JSON and JSONL exports were then normalized from CRLF to LF for repository
storage, and the quality reader was rerun. Only those input hashes changed, from
`caa0cdba…` / `92301f3c…` to `b652921b…` / `232d605e…`; the reading did not change.
These private counts and chronology are not reconstructed by the artifact test.

## Files

| File | SHA-256 |
|---|---|
| `plans.json` | `a6e25687506ec4cf5b87a81964c9225673ba07155e06fcc9fd699dbe42af7da1` |
| `final-answers.json` | `1e75d640d462dc908ef92ea61c2d570df1d5c89416da63b75d43d4c530b79a27` |
| `final-aircargo-m1.json` | `b652921bd3a988e0bb9cc3bef4ec52f07043f543194a8c52f6694f2471628c83` |
| `final-aircargo-m1.cases.jsonl` | `232d605eee10b65320f3a6a52a5dd3ecd3fb297d4c442b639329d1b8383e779a` |
| `final-aircargo-bridge.json` | `f7f09bd3e272e685e4c3df67351d191113c18c87504aa462daa746f7a482b53a` |
| `quality.json` | `e49e8560a766d58fdeda7c587be9cdfeb6138b24695107a113c16ac2b26f907c` |

Raw answers, prompts, source documents, replies and launches remain private. The judge export
includes the public handover instructions and reference enums; these are not corpus text.
Receipt hashes bind private files but do not make their contents available to this test.

## What it does not say

This is the whole package against V4, with no attribution to one lever. There was one unseeded
answer per question, on one stand, on one day. The existing questions were written by an
agent. Judge drift is bounded by the bridge only. Aircargo does not establish quality on
the external bases; stage 5 measures those.

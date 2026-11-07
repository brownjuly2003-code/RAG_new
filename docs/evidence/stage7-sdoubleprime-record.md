# Stage 7, step 1: S'' with parent expansion — identical prompts, unread decomposition

**The tool reads S'' as NOT_EVIDENCE: its section-run reader cannot decompose some parent-expanded documents.**
**S'' sent H_new's exact prompt bytes on 415 of 415 questions; Amendment 3's b = c = 0 holds by byte identity, not by a McNemar reading the tool could make.**
**Amendment 3's «any difference is a defect» found no difference from H, only an unread decomposition; this is not a pass of the tool's reading.**

P has no detected difference on either deciding base or their pool; its readings stand below.
The tool retains the key `S` for S''. In `members_of`, S still uses `run_members`, the
section-run decomposition written for S and S'; H and P use `external_gold.expansion_members`.
A document that cannot be reconstructed as that run raises `ValueError`; `arm_entry` returns
`unresolved: "members"` before counting chunks or reading points. Since `b080c64`, the lane
uses `_expand_parents`, including neighbours across sections. Amendment 3 says «The replay
tool is unchanged»: its reader was not adapted. This is a gap of the replay tool, not a
difference between S'' and H. The row-level checks below find none; unread rows are not misses.

## What ran, and why

[Amendment 2](../specs/stage7-step1-arms-m3.md#amendment-2-2026-11-06-s--the-structural-lane-after-the-coherence-fix)
measured S' after the coherence fix: keeping H_new's five and their order still left a
detected loss on ConditionalQA and the deciding pool. The historical pairs are below and
in the [S' capsule](stage7-sprime-record.md). `get_graph_documents_with_path` called only
`_expand_graph_sections`, stopping at section boundaries and omitting the neighbouring
parent context that H assembled. Under Amendment 2 this was a defect to fix before answers.

[Amendment 3](../specs/stage7-step1-arms-m3.md#amendment-3-2026-11-06-s--the-structural-lane-with-the-products-parent-expansion),
registered in `b080c64` before the run, fixes that assembly: `_expand_parents(coherent)`
when parent expansion is on, `_expand_graph_sections` only when it is off. It preserves
selection and order. Score, then replay, ran on the Mac on 2026-11-06 and 07 UTC, from the dedicated
clean clone `/Users/julia/RAG_new_a3_gate`, with Amendment 3's recipe and new output folders.
The [record](../../reports/stage7/b080c64-a3/record.json) measures S''; no answers were read.
The [artifact test](../../tests/test_stage7_sdoubleprime_record_artifact.py) binds the copied
bytes, parses every table and rebuilds its values from the records, including row identity.
It needs no model, private archive or retrieval run.

## Provenance and parity

Stage-2 source stand `5e308fe48cca0955c3007057a574a425f71e2a6a`; V4 source stand `4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1`.
Measured HEAD `efd2c3d747a890b317475093dc2a4df1aaa942b1`, parent `b080c6453bdd9fb75576c6b8b49ac9cfdb1f3a30`.
Subject: `mf-gate overlay of b080c6453bdd9fb75576c6b8b49ac9cfdb1f3a30`.
The parent is the registering commit. The measured HEAD is a Mac-only overlay: the test
never resolves it. It reads the spec, tool, replay test and every `measure_code_sha256`
file with `git show` at the recorded parent. That history is required, without a fallback
to any commit of this package; CI uses full history (`fetch-depth: 0`). The parent is absent
from this package, so the historical check cannot succeed here; it was not run locally.

Header spec SHA-256: `9759d79b5413065e405ca39be109dedb9910d1130679771909e7bfb4f89f8d3b`.
Header tool SHA-256: `6ca8b723841d08dfd6f5d084bdc0883264c889eb495dc4d3728ac0a2ea623689`.
Amendment 3's test SHA-256: `84eb8de05ae553f220e8a006ada19d3eb9a65060c5912516b4d73ad9aa40def3`.
The parent spec's bytes must match the header; its Amendment 3 SHA list and the current
registered list must agree. The tool digest is checked against both the header and that
list. The replay test's digest is absent from the header, so its check uses the list and
the parent's bytes. Neither tool nor replay test is in `measure_code_sha256`; every file
in that map is checked at the parent against the header and the record.

H is H_new: K 14, 5 kept, window 3,584, input limit 2,176, runtime `onnx`.
INT8 export `57335a9f061fe31378c160ddd0861711a0fbdfa20f70aa2640d473dfc4bc1343`; effective batch 32, no RAG_RERANK_BATCH override.
The service environment, offline flags and tokenizer snapshot are Amendment 1's recipe,
as in the [S' capsule](stage7-sprime-record.md#provenance-and-parity). The header binds the
frozen runs' provenance and record hashes; replay copies it in full. The input hashes below
come from the record and are checked against the spec; both aircargo labels share an archive.

| Frozen input | SHA-256 |
|---|---|
| Stage-2 export manifest | `f8dbfb9edbdd9af830017c2c583aedcbfc8f8fbedde6c806abb5de94288985e9` |
| V4 record | `81162268ad1c3af7cbe8f5cc885c7137c29864ed3a9acf5b778f17d28821749e` |
| WixQA archive | `2cc24c6f56a394ff189366f70b6ed11b919ba8f545fa592e019c9b193814ba5a` |
| ConditionalQA archive | `e25960d5e4263a0d7f7ea9b02ac217d29be912b078d65bbb4ac0480c677d8755` |
| MultiHop-RAG archive | `db25b882fc9fe6cd6e76101330ffc816a9081813268706a016a263171cf80300` |
| aircargo archive | `b3e4d3727f3456b66ee398698b6a610f60c0c269de5c81bd814ae4e2c0ebba15` |

The old-control parity gate uses K 20, recorded PyTorch scores, window 4,096 and input limit 2,636.
It checks recorded pools, fives, expansions, V3 sent documents and prompt bytes against
the export, then saved V4 prompt bytes, before reading the arms.
Parity passed 415 of 415; V4 prompts byte-equal 300 of 300; breaks 0.
The score completion and replay decision logs are read again by the artifact test.

## S'' as read by the tool, and identity with H

MAX_UNREAD is 5; the rule counts unread questions with gold, not all unresolved rows.
More than that on a base makes it and every pool containing it `NOT_EVIDENCE` at both
points. The table distinguishes the complete row population from gold-bearing pairs.
Aircargo has no context gold here and no external pair or standing of its own. All
questions pooled is descriptive; the tool defines only the deciding and all-three pools.

| Base / pool | Questions | S unresolved members | With gold | Unread with gold | Tool sent | Tool expanded |
|---|---|---|---|---|---|---|
| WixQA | 100 | 28 | 100 | 28 | NOT_EVIDENCE | NOT_EVIDENCE |
| ConditionalQA | 100 | 50 | 80 | 43 | NOT_EVIDENCE | NOT_EVIDENCE |
| MultiHop-RAG | 100 | 49 | 70 | 33 | NOT_EVIDENCE | NOT_EVIDENCE |
| aircargo | 115 | 44 | 0 | 0 | — | — |
| Deciding bases | 200 | 78 | 180 | 71 | NOT_EVIDENCE | NOT_EVIDENCE |
| All three | 300 | 127 | 250 | 104 | NOT_EVIDENCE | NOT_EVIDENCE |
| All questions | 415 | 171 | 250 | 104 | — | — |

Every row has equal prompt SHA-256, `documents`, `chars`, `sent_documents` and `sent_chars`.
The tool also records `changed` from a direct comparison of the complete prompts, not their
hashes alone. S'' has `changed = false`, `dropped = 0` and `order_changed = false` everywhere.
Where both arms have `points`, the entire points objects agree at sent and expanded.
The last column counts equal rows out of rows with points in both arms; it does not impute
points for unread rows. `chunks` and `sent_chunks` differ only on unresolved S rows, where
they are null: they count decomposed members and are not evidence of different text.

| Base / pool | Questions | S unresolved members | Prompt SHA-256 equal | Documents / chars / sent equal | Both points equal / available |
|---|---|---|---|---|---|
| WixQA | 100 | 28 | 100 | 100 | 72 / 72 |
| ConditionalQA | 100 | 50 | 100 | 100 | 37 / 37 |
| MultiHop-RAG | 100 | 49 | 100 | 100 | 37 / 37 |
| aircargo | 115 | 44 | 115 | 115 | 0 / 0 |
| Deciding bases | 200 | 78 | 200 | 200 | 109 / 109 |
| All three | 300 | 127 | 300 | 300 | 146 / 146 |
| All questions | 415 | 171 | 415 | 415 | 146 / 146 |

## H against P

The primary hit is WixQA's `gold_article`, otherwise `all_evidence_coverage`; secondary
means are `gold_articles` and `evidence_recall`. Here b is H-only, c arm-only.
P's rule is rel 0.2; each primary pair reads loss or gain only at p < 0.05.
The exact two-sided McNemar p uses the record's precision; rounded zero is <0.000001.
P has no unread gold-bearing pairs. ConditionalQA, WixQA and their pool at sent are the
stop readings; expanded, MultiHop-RAG and all three pooled stand beside, advisory.
No pooled secondary mean is defined.

| Base | Point | n | H → P hits | b / c | p | Reading | Secondary mean H / P |
|---|---|---|---|---|---|---|---|
| WixQA | sent | 100 | 67 → 66 | 1 / 0 | 1 | no detected difference | 0.6317 / 0.6217 |
| WixQA | expanded | 100 | 68 → 67 | 1 / 0 | 1 | no detected difference | 0.6417 / 0.6317 |
| ConditionalQA | sent | 80 | 58 → 55 | 3 / 0 | 0.25 | no detected difference | 0.8064 / 0.7945 |
| ConditionalQA | expanded | 80 | 58 → 55 | 3 / 0 | 0.25 | no detected difference | 0.8064 / 0.7945 |
| MultiHop-RAG | sent | 70 | 4 → 4 | 0 / 0 | 1 | no detected difference | 0.4321 / 0.4321 |
| MultiHop-RAG | expanded | 70 | 11 → 11 | 0 / 0 | 1 | no detected difference | 0.5179 / 0.5131 |
| Deciding bases | sent | 180 | 125 → 121 | 4 / 0 | 0.125 | no detected difference | — |
| Deciding bases | expanded | 180 | 126 → 122 | 4 / 0 | 0.125 | no detected difference | — |
| All three | sent | 250 | 129 → 125 | 4 / 0 | 0.125 | no detected difference | — |
| All three | expanded | 250 | 137 → 133 | 4 / 0 | 0.125 | no detected difference | — |

## S of 2026-10-31 and S' beside S''

The [original record](../../reports/stage7/5e308fe/record.json) and
[Amendment 2 record](../../reports/stage7/98e5bf0-a2/record.json) supply these historical
columns. Their n and H hits also match this run's readable H/P pairs. Each historical
b / c and p compares that arm with its own H, not S with S'. S'' has no tool-computed
McNemar pair to add: its identity evidence is above, and its standing remains `NOT_EVIDENCE`.

| Base | Point | n | H hits (three runs) | S (2026-10-31) hits | S' hits | H vs S b / c | H vs S p | H vs S' b / c | H vs S' p |
|---|---|---|---|---|---|---|---|---|---|
| WixQA | sent | 100 | 67 | 60 | 68 | 7 / 0 | 0.015625 | 0 / 1 | 1 |
| WixQA | expanded | 100 | 68 | 60 | 68 | 8 / 0 | 0.007812 | 0 / 0 | 1 |
| ConditionalQA | sent | 80 | 58 | 39 | 45 | 19 / 0 | 0.000004 | 13 / 0 | 0.000244 |
| ConditionalQA | expanded | 80 | 58 | 39 | 45 | 19 / 0 | 0.000004 | 13 / 0 | 0.000244 |
| MultiHop-RAG | sent | 70 | 4 | 1 | 2 | 3 / 0 | 0.25 | 2 / 0 | 0.5 |
| MultiHop-RAG | expanded | 70 | 11 | 4 | 12 | 7 / 0 | 0.015625 | 0 / 1 | 1 |
| Deciding bases | sent | 180 | 125 | 99 | 113 | 26 / 0 | <0.000001 | 13 / 1 | 0.001831 |
| Deciding bases | expanded | 180 | 126 | 99 | 113 | 27 / 0 | <0.000001 | 13 / 0 | 0.000244 |
| All three | sent | 250 | 129 | 100 | 115 | 29 / 0 | <0.000001 | 15 / 1 | 0.000519 |
| All three | expanded | 250 | 137 | 103 | 125 | 34 / 0 | <0.000001 | 13 / 1 | 0.001831 |

## Context sent, with expansion beside

Medians are from `record.json`'s `labels`, with H / S'' / P in that order. Documents and
estimated tokens cover the complete label, not just questions with gold. The tool's chunk
medians omit null values: H and P use every row, S'' only rows with a readable decomposition.
Their differing chunk medians therefore compare different populations; the row checks above
show equal chunk counts wherever both are read. They do not show different assembled context.
Estimated tokens describe sent context, not the full prompt or exact tokenizer counts.
The aircargo labels remain separate, without pooling or averaging their medians.

| Base / label | Questions | S readable members | Sent documents H / S'' / P | Sent chunks H / S'' / P | Sent estimated tokens H / S'' / P | Expanded chunks H / S'' / P | S'' / P changed prompts |
|---|---|---|---|---|---|---|---|
| WixQA | 100 | 72 | 5 / 5 / 5 | 16 / 16 / 16 | 1729.5 / 1729.5 / 1713 | 17 / 18 / 16 | 0 / 9 |
| ConditionalQA | 100 | 50 | 5 / 5 / 4 | 16 / 17 / 13 | 1673.5 / 1673.5 / 1376 | 17 / 19 / 13 | 0 / 38 |
| MultiHop-RAG | 100 | 51 | 3 / 3 / 3 | 13 / 14 / 13 | 1711 / 1711 / 1706 | 18 / 21 / 17.5 | 0 / 10 |
| aircargo | 100 | 60 | 3 / 3 / 3 | 13 / 14 / 13 | 1783.5 / 1783.5 / 1769 | 21 / 23 / 18 | 0 / 14 |
| aircargo-gr | 15 | 11 | 2 / 2 / 2 | 10 / 10 / 10 | 1786 / 1786 / 1786 | 25 / 25 / 25 | 0 / 0 |

Of the 300 questions with saved V4 prompts, S'' changes 0 prompts and P changes 61 against H_new.
Those changes compare the arms with H_new; the old-control V4 parity check is separate.

## G1 as printed — advisory for S''

Both `replay.out` and `record.json` print:

```json
{"standings": {"S": "NOT_EVIDENCE", "P": "open"}, "gains": {"S": [], "P": []}, "arm": null, "reading": "NOT_EVIDENCE"}
```

Amendments 2 and 3 publish the graph lane's effect on context under rule (c); the owner's
word turns the graph on, not this reading. P retains Amendment 1's meaning: open, with no
qualifying gain. The recorded judge is null. Amendment 3 provides no aircargo context-judge
plan for S''; changed prompts do not open a judge run. No unread S'' pair is called a pass.

## What it does not say

This is context gold only, with no answer read, on one stand on one day. Missing gold is
not a miss; aircargo has no context gold here. The replay uses archived structural metadata,
without links, entities or categories, and does not measure the live chat route's quality.
Recorded lane prefixes are not a fresh index search and need not equal a fresh approximate
search. No detected difference for P is not equivalence. S'' prompt identity is specific
to these recorded rows and this package; it neither repairs the tool's decomposition nor
proves parent expansion across sections correct. The graph is turned on by the owner's
word, not by this reading.

## Files

Under `reports/stage7/b080c64-a3/`. These SHA-256 digests bind the six copied files.
They contain ids, flags, counts, hashes, chunk positions, scores and durations, never
question, answer, document or filled-prompt text. No new environment paths are published.

| File | SHA-256 |
|---|---|
| `int8_scores.jsonl` | `0e8d3847d1054bd2aee30d45d95aa5dadd1a73e5c1a5704e8dded226b24d7f1a` |
| `parity.jsonl` | `073cf545aec63c66965a7b999d1a8d01d43b1ab70eb6616eed0400234c71bb26` |
| `record.json` | `1a984d335f5426c1e4bfb0095796daa35ce15d491aadc5f0fa184d60d01d10d2` |
| `replay.out` | `139a84a6f047f101c38810c7348ef24802cae325d352da22dbdf81b10c24d33a` |
| `rows.jsonl` | `61032a76e338b0fda595fd5fbed2d5a86fbc44ee792c03d2dc383c248abbbd79` |
| `score.out` | `422ea7a647707831f574eaa8df570aebb832f3546686eb54d3e4699387d0c21c` |

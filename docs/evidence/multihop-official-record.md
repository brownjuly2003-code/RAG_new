# MultiHop-RAG's retrieval by the official rule, beside stage 2's, on stage 2's lists — 2026-10-28

The question: stage 2 reads MultiHop-RAG's gold as every evidence group covered — 10 of the 70
questions with gold at «sent», 7 at the reranked five — while the benchmark publishes Hits@4 of
0.62–0.67. The two are not one measure: the benchmark's script counts a question when any one
gold fact stands in one of the first K chunks. That script's rule read stage 2's saved lists of
stand `5e308fe` by
[`multihop-official-retrieval.md`](../specs/multihop-official-retrieval.md), registered with
the tool in `6ce7a77` before the count; ours was printed beside it. No model call, no new
retrieval; 6.7 s on the Mac.

Record: [`reports/multihop-official/5e308fe/record.json`](../../reports/multihop-official/5e308fe/record.json)
and its [rows](../../reports/multihop-official/5e308fe/rows.jsonl), written by
[`reports/multihop-official/tools/multihop_official.py`](../../reports/multihop-official/tools/multihop_official.py).
Checked by [`tests/test_multihop_official_artifact.py`](../../tests/test_multihop_official_artifact.py):
- every number of the record, its intervals and readings too, is read again from the rows, with
  stage 2's clusters as its committed judge export numbers them;
- stage 2's own points are read again from the committed export;
- every table row below is built from the record.

The rows hold identifiers, flags and numbers, never the text of a question, a fact or a
document.

## Provenance and method

- **The rule:** `calculate_metrics` and `main_eval`'s skip of the null queries, from
  `retrieval_evaluate.py` of `yixuantt/MultiHop-RAG` at `c1c1287a…` (SHA-256 `6734516f…`),
  copied line for line. The file was fetched again and compared before the registration; so
  were the published tables, from arXiv.
- **Inputs:** the no-reranker point's run `p2-multihoprag` on stand
  `5e308fe48cca0955c3007057a574a425f71e2a6a`, its chunk archive and cases, the same files by
  SHA-256 ([record](no-rerank-point-record.md)). The facts' text: the raw `MultiHopRAG.json` of
  revision `71ac0d0b…`, 5,171,312 bytes, SHA-256 `03cfb492…`, as registered. Measured in the
  Mac's gate checkout at the overlay of `6ce7a77` (`d488d58d`); the record names the tool and
  the measuring code by SHA-256.
- **The lists:**
  - primary — the reranker's first ten chunks: the pool of 27–40 candidates by its recorded
    scores, ties in fused order. Ranks 1–5 are the five the product kept; 6–10 were scored and
    dropped.
  - secondary — the recorded expansion of the five.
- **The questions:** the run's 100. The script skips the 30 null queries and leaves stage 2's
  70 with gold, all `inference_query`, in 15 clusters, the largest of 49. They carry 235 facts
  (four facts 34 questions, three 27, two 9), none repeated, none empty.
- **The reading, frozen:** a share reads the wider of Wilson's and the clusters' 95 % interval,
  a mean the clusters'. A number is «above the band» when its interval's low end is above the
  band's top. The band is the published rows with the reranker: the paper's Table 5 (its four
  embedders above 0.6 at Hits@4) and Multi-Meta-RAG's two runs of the script. MAP@10's band is
  the script's alone: the paper's MAP@10 is not what the script computes.
- **Checks before any number, all passed:**
  - the run, the archive and the cases are the export's and the index's;
  - every recorded pool is the export's;
  - each case's row of the raw file holds its question, its type and its evidence;
  - the questions the script keeps are stage 2's 70;
  - each pool's reranker order starts with the five the run kept;
  - stage 2's rule at those five gives the export's points;
  - every chunk of the ten has a place in its document;
  - no record carries text of the base.

## The official numbers

| Metric | Primary: the reranker's first ten | Read interval | Published band | Reading | Secondary: the expanded five | Its interval |
|---|---|---|---|---|---|---|
| Hits@4 | 0.8714 (61 of 70) | 0.8000–1.0000 | 0.6169–0.6661 | above the band | 0.9143 (64 of 70) | 0.8253–0.9601 |
| Hits@10 | 0.9429 (66 of 70) | 0.8824–1.0000 | 0.7059–0.7490 | above the band | 0.9429 (66 of 70) | 0.8824–1.0000 |
| MRR@10 | 0.7811 | 0.7040–0.8819 | 0.5477–0.6029 | above the band | 0.8188 | 0.7333–0.8939 |
| MAP@10 | 0.3233 | 0.2929–0.4169 | 0.2619–0.2687 | above the band | 0.3434 | 0.3089–0.4326 |

The secondary list is printed, not read against the band: its Hits@10 is a hit among five.

## Ours beside — the definition parts them, not the matching

Questions with a fact in the first K by the official substring and by stage 2's ranges, any
fact and every fact, with the read interval:

| K | Substring, any fact (= Hits@K) | Ranges, any group | Substring, every fact | Ranges, every group | `evidence_recall` |
|---|---|---|---|---|---|
| 4 | 61 of 70 (0.8000–1.0000) | 61 of 70 (0.8000–1.0000) | 5 of 70 (0.0000–0.2105) | 5 of 70 (0.0000–0.2105) | 0.4250 (0.3782–0.5357) |
| 10 | 66 of 70 (0.8824–1.0000) | 66 of 70 (0.8824–1.0000) | 13 of 70 (0.0769–0.3333) | 13 of 70 (0.0769–0.3333) | 0.5405 (0.4896–0.6402) |

Discordant at four: 0 by the substring alone, 0 by the ranges alone.

Stage 2's own points of the same 70, from the committed export:

| Point | Every group | Any group | `evidence_recall` |
|---|---|---|---|
| the reranked five | 7 of 70 | 62 of 70 | 0.4595 |
| the expanded five | 13 of 70 | 66 of 70 | 0.5262 |
| «sent» | 10 of 70 | 64 of 70 | 0.4857 |

## What it says

- **By the benchmark's own rule our lists score above every published row.** The first four
  chunks hold a gold fact for 61 of the 70 questions, Hits@4 0.8714. Its read interval,
  0.80–1.00, lies wholly above the band's top of 0.6661. Hits@10, MRR@10 and MAP@10 read «above
  the band» too.
- **The low «10 of 70» is the definition, not the retrieval.** At four and at ten the
  official substring and stage 2's ranges pick the same questions — for any fact and for every
  fact, with 0 discordant. Only «any» against «every» parts 61 from 5 of 70. Each question
  carries two to four facts, and the first four chunks seldom hold all of them.
- **The expansion adds a little on the same five.** Hits@4 on the expanded documents is 64 of
  70 against 61; MRR@10 0.8188 against 0.7811.
- **The forecast held**, all seven items, each written before the count:

  | Item | Forecast | Count |
  |---|---|---|
  | Hits@4 | 0.75–0.90, above the band | 0.8714, above |
  | Hits@10 | 0.84–0.97, above the band | 0.9429, above |
  | MRR@10 | 0.66–0.82, above the band | 0.7811, above |
  | MAP@10 | 0.29–0.37, above the band — the nearest call | 0.3233, above (low end 0.2929) |
  | Ranges, any group, against Hits@4 | within 0.10, at most 7 discordant either way | equal, 0 discordant |
  | Every fact in the first four | at most 7 of 70 | 5 by either matching |
  | The secondary's Hits@4 | not below the primary's | 0.9143 against 0.8714 |

## What it does not say

It decides nothing: MultiHop-RAG is advisory, its labels were written by a model, and no stage
waits on this count. Stage 2's metric and record stay as they are: «all evidence 10 of 70» is
still every group covered at «sent».

Limits:
- not the benchmark's retrieval: our chunks (800 characters), BM25 with BGE-M3 and
  bge-reranker-v2-m3, a pool of 27–40 against their 20;
- 70 inference questions in 15 clusters, against the benchmark's 2,255 of three types;
- «above the band» says the script scores our lists above the published rows for theirs, not
  that our retriever beats theirs;
- ranks 6–10 were scored and dropped by the product: Hits@10, MRR@10 and MAP@10 read the
  reranker's order, not what the model reads;
- gold in the retrieved chunks, not answer quality.

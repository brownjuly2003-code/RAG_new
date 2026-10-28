# MultiHop-RAG's retrieval by the official rule, beside stage 2's, on stage 2's lists

Status 2026-10-28: **registered before the count**, with the tool that reads it and its test
([Records](#records)), in `6ce7a77`; read the same day — **all four official numbers above the
band**, Hits@4 0.8714 ([record](../evidence/multihop-official-record.md)).
[`PLAN.md`](../../PLAN.md), «Параллельно, без Mac», the
recount by the published rules (the amendment of 2026-10-26): «Лёгким скриптом на Mac между
замерами, без модели (тексты остаются на Mac), — Hits@K и MAP@10 MultiHop-RAG по официальному
`retrieval_evaluate.py` … Свои и официальные числа печатаются рядом, и те и другие названы до
счёта. Правило (c) при публикации»; the [research
analysis](../operations/research-2026-10-25/analysis.md), item 1, which needs no word. No model
call, no new retrieval: stage 2's saved lists, read on the Mac, where the texts stay.

## Why

Stage 2 reads MultiHop-RAG's gold by its own rule (`external-gold/range-coverage-v1`). Its
primary metric, `all_evidence_coverage`, is 1 when every evidence group of a question is
covered: at «sent» for 10 of the 70 questions with gold, at the reranked five for 7
([stage 2's record](../../reports/stage2/5e308fe/stage2-record.json), `m3`). The benchmark
publishes Hits@4 of 0.6169–0.6625 for its four best embedders with a reranker (the paper,
arXiv 2401.15391v1, Table 5). The two are not one measure. The official script counts a
question as a hit when any one of its gold facts stands, as a substring, in one of the first K
retrieved chunk texts; ours asks for every fact. The paper's prose calls Hit@K «the fraction
of evidence that appears in the top-K retrieved set»; the script, which others ran to report
their numbers (Multi-Meta-RAG, below), counts any one fact. This spec follows the script: it
is what can be run again. So «10 of 70» cannot be set against 0.62–0.66 until the official
rule runs on our lists. The analysis expects that number «likely much higher»; the risk it
names is choosing the flattering metric after seeing it. Against it, ours and the official
numbers are named here, before the count, and printed side by side.

## The official rule

`retrieval_evaluate.py` of [`yixuantt/MultiHop-RAG`](https://github.com/yixuantt/MultiHop-RAG)
at `c1c1287aa60a94acf9c4d20c891c9cd611a0f6e8` — a merge of 2026-09-16, the head of `main` when
read on 2026-10-28 (the file's blob `a65720ff0d95…`, 4,179 bytes, SHA-256
`6734516f0d5f9385076f76bf4e08d54968541fdb05f519f1cf687c0b65ae0f90`), fetched with `curl` and
never run. Its `calculate_metrics` has not changed since the file was added as `evaluate.py`
in `2d0ecc3` (2024-03-15); `5fc3983` (2024-08-02) renamed it, and `33d3ad0` (2026-07-16)
touched only `main_eval` and the command line (UTF-8 reading, `--limit`, a guard for an empty
input). What it does:

- **Input**, per question: `question_type`; `retrieval_list`, the retrieved texts in rank
  order; `gold_list`, whose `fact` fields are the facts — the official retrieval
  (`simple_retrieval.py`) copies the question's `evidence_list` there.
- **Null queries:** `main_eval` skips every question of type `null_query` before it reads its
  lists. The paper: «NULL queries are excluded in this experiment».
- **Normalisation:** every space and every newline is removed from facts and texts, nothing
  else — case, tabs, `\r`, no-break spaces and punctuation stay.
- **Match:** a fact is found in a text when it is a substring of it, case-sensitive. A fact
  split between two texts is found in neither; an empty fact is found in every text.
- **Ranks:** of the first ten (the loop reads eleven and scores ten) a rank is relevant when
  any fact is found in its text. **Hits@10** — a relevant rank among the ten; **Hits@4** —
  among the first four; **MRR@10** — one over the first relevant rank, 0 without one.
- **MAP@10:** at each relevant rank, the facts first found there over the rank, summed, then
  divided by the number of facts, at most 10. A fact listed twice is found once and divides
  twice; a text that holds an already found fact adds nothing. It is a recall discounted by
  rank, not the textbook average precision.
- **Over questions:** each number is the plain mean, printed at four decimals; an empty gold
  list stops it with a division by zero.

The tool copies `calculate_metrics` line for line — three spellings apart, as ruff writes them
(`zip(..., strict=False)`, `x not in y`, double quotes) — and `main_eval`'s skip
(`official_eval`); nothing of the download is imported or run. Its test holds each case above
on synthetic texts.

## Inputs

Stage 2's retrieval run `p2-multihoprag` on stand `5e308fe`
(`5e308fe48cca0955c3007057a574a425f71e2a6a`), on the Mac:
`/Users/julia/RAG_new_chat_5e308fe/chatlive/runs/p2-multihoprag/` — `launch.json`,
`effective_settings.json` and one `retrieval/NNN-<case>.json` per question, written by
`reports/stage2/tools/live_retrieval.py`: the pool with each candidate's reranker score, kept
whole, the five kept and their expansion. Its settings (the export's provenance): a vector lane
on `BAAI/bge-m3` and a BM25 lane, 20 candidates each, fused by RRF (k = 60, the
[no-reranker record](../evidence/no-rerank-point-record.md)); `BAAI/bge-reranker-v2-m3` keeps
five; parent expansion with window 2 and at most 3,600 characters.

The base, second generation: `/Users/julia/RAG_new_external_s1/multihoprag/` — the chunk
archive `chunks.json.gz` (11,231 chunks, the export's BM25 restore log; SHA-256
`db25b882…0300`, the one the index receipt and the export name), the converted documents of
the 609 articles and `cases.jsonl` (SHA-256 `cf5f6462…c109fac`, as
`evaluation/external_bases.json` registers it). The cases hold the facts' places, not their
text. The text comes from the raw `MultiHopRAG.json` the cases were converted from, the
dataset's revision `71ac0d0bd1f951d2d6b70311f7d2ae404e1ffa82`: 5,171,312 bytes, SHA-256
`03cfb4926461f868684903aadc8024447bdda5bb3f6804741424cce338515bff`, as registered — the copy
`python -m scripts.external_base fetch --base multihoprag --raw DIR` writes to
`DIR/multihoprag/`. The committed export of the same run, `reports/stage2/retrieval-20261021/`,
is named by its manifest's SHA-256 (`f8dbfb9e…85e9`).

## The lists

- **Primary — the reranker's first ten, as chunks.** Stage 2 recorded the reranker's score of
  every candidate of the pool, not only of the five it kept. The pool sorted by those scores,
  highest first, ties in fused order — the product's stable sort
  (`_rerank_scored_with_status`), the order `retrieval_summary.k_curve` replays — is the
  reranker's order of the whole pool; its first five are the five the run kept (check 6). The
  official list is ten long: the official retrieval keeps the reranker's `top_n` = `--topk`, 10
  by default, of 20 retrieved. Each entry is its chunk's text in the archive (`page_content`,
  the contextual header line included) — the text the index holds and the reranker read.
  Hits@4 reads the first four, all among the five the product kept; Hits@10, MRR@10 and MAP@10
  read the ten, ranks 6–10 scored and dropped by the product.
- **Secondary — the expansion of the five.** The recorded `expanded` documents, in order: each
  kept chunk with its neighbours, the text the model's context is cut from. The official
  function on them is printed, not read; its Hits@10 is a hit among the five (five for each
  of the 70, the export's `expanded_documents`).

The chunk before expansion is primary because it is the official unit: the script matches facts
against the retrieved chunks, the texts the reranker ranked. An expanded document holds up to
3,600 characters around its chunk and would credit the ranking with text it never scored.
«Sent», the fitted documents, is not read here: stage 2's own points give it.

## The unit: our chunks are not the paper's

- **Theirs:** LlamaIndex's `SentenceSplitter`, 256 tokens a chunk (the paper: «each consisting
  of 256 tokens»), over each article of `corpus.json`, each text with its title, source and
  date in front (LlamaIndex's LLM metadata mode); the overlap is the splitter's default of 200
  tokens in `simple_retrieval.py` until `8475a31` (2026-09-15) set 25, and 32 in Multi-Meta-RAG;
  20 by vector search, `bge-reranker-large` keeping 10.
- **Ours:** 800 characters with 200 of overlap, structural chunking and a contextual header
  line (the registration's `chunking`), over the converted Markdown; the hybrid pool above.

So the official number here is the official rule applied to our lists, not a reproduction of
the benchmark's retrieval. The two matchings differ too, and the record counts where they part:

- The official one needs a whole fact — spaces and newlines aside — inside one text, of any
  document. Ours (`evaluation/external_gold.py`) compares visible characters only and credits a
  group whose place, in its own document, the present chunks cover together.
- A fact across a boundary of two of our chunks, both present, is found by ours and missed by
  the official one; a fact repeated in another article is found by the official one only.
- Every fact of the 70 stands in its document by its visible characters (the export:
  `unresolved_evidence` 0 for each). So the official match can also fail where the fact and our
  text differ only in what ours ignores — whitespace other than a space or a newline (a tab,
  `\r`, a no-break space) or an invisible character: in the dataset itself, or because the
  conversion (it strips each line, `evaluation/external_convert.py`) or the chunker (it
  re-joins and strips lines and drops invisible characters) removed one from our text.

`discordant_at_4` counts, each way, the questions to which one matching gives a fact in the
first four and the other none.

## The questions

The run's 100: the selection `stage2`, the first 100 advisory questions
([stage 2's spec](stage2-four-corpora.md)). `main_eval`'s skip, read on the pinned file's
`question_type`, leaves 70. They must be stage 2's 70 with gold (check 5), all
`inference_query` (the export); the 30 skipped are its `null_query` ones. They are fed in the
pinned file's order, the order the official retrieval writes. The 70 form 15 clusters, the
largest of 49 (stage 2's spec). The published numbers are over the benchmark's 2,255 non-null
queries of three types — inference 816, comparison 856, temporal 583 (the paper, Table 3).

## Ours beside

On the same first four and first ten, per question, stage 2's two metrics by its own rule
(`scripts/external_pilot.read_gold`): `all_evidence_coverage`, every group covered, and
`evidence_recall`, the share covered, whose «above 0» is the any-fact reading of ours. With the
substring matching's own «every fact» — each distinct fact whole in one of the K texts — they
make four shares at each K:

| | any fact | every fact |
|---|---|---|
| the official substring | `substring_any` (= Hits@K) | `substring_all` |
| stage 2's ranges | `range_any` | `range_all` |

Across a row the definition changes, down a column the matching. Beside them, the export's own
points for the same 70 (`stage2_committed`): `all_evidence_coverage` 7, 13 and 10 of 70 and
`evidence_recall` 0.4595, 0.5262 and 0.4857 at the reranked five, the expanded five and «sent»;
a group is covered there for 62, 66 and 64. «All evidence 10 of 70» is the «sent» point.

## Checks before any number

1. **The run.** `launch.json` complete and of `5e308fe`; `rerank_top_k` 5 and parent expansion
   on; the export's manifest of the same stand, its `p2-multihoprag.cases.jsonl` the file the
   manifest names.
2. **The corpus.** The chunk archive is the one the index receipt and the export name; the
   cases file is the registered one.
3. **The records.** The run's question ids are the export's; every recorded pool, as
   [vector rank, BM25 rank, score], is the export's `pool`.
4. **The pinned file.** Its size and SHA-256 are the registration's. A case's row
   (`multihoprag-NNNN` is row NNNN) holds the case's question and type, and its distinct
   (url, fact) pairs are as many as the case's evidence groups and unresolved facts.
5. **The questions.** Those `main_eval` keeps are exactly stage 2's 70 with gold.
6. **The order.** Each kept question's pool is scored whole by a reranker that ran, and its
   reranker order starts with the five the run kept, in their order.
7. **The recount.** `read_gold` at those five equals the export's `points.ranked`; every chunk
   of the first ten has a place in its document (the export counts no chunk without one,
   `chunks_without_a_place` 0).
8. **No text.** `stage2_common.without_text` refuses a record that names a document of the base
   or holds a question or a gold fact.

Any failure stops the tool before a number is written. A pool shorter than ten gives a shorter
list — the official function reads what is there — counted (`short_of_ten`), not stopped; each
of the 70 pools holds 27 candidates or more (the export).

## How it is read — frozen before the count

Each number over the 70 is printed with its interval, as stage 2 reads its own
([stage 2's spec](stage2-four-corpora.md), «How the numbers are read»): a share — Hits@4,
Hits@10 and the four of «Ours beside» — with its n, its Wilson 95 % interval and the
cluster-bootstrap 95 % interval over stage 2's clusters (`judge_export.clusters`,
`judge_export.share`), the wider of the two read (`stage2_record.read95`); a mean — MRR@10,
MAP@10, `evidence_recall` — with the cluster-bootstrap interval
(`evaluation.semantic_ruler.cluster_summary`).

The published band of a metric runs from the lowest to the highest of the published rows with
the reranker: the paper's Table 5, its four embedders whose Hits@4 is above 0.6
(`text-embedding-ada-002`, `text-search-ada-query-001`, `bge-large-en-v1.5`, `voyage-02`), and
the two baseline rows of Multi-Meta-RAG (arXiv 2406.13213v2, Table 2), «evaluated» with «an
evaluation script provided in the MultiHop-RAG repository»:

| | Table 5 | Multi-Meta-RAG | the band |
|---|---|---|---|
| Hits@4 | 0.6169–0.6625 | 0.6630–0.6661 | 0.6169–0.6661 |
| Hits@10 | 0.7059–0.7467 | 0.7419–0.7490 | 0.7059–0.7490 |
| MRR@10 | 0.5477–0.5860 | 0.6016–0.6029 | 0.5477–0.6029 |
| MAP@10 | 0.4625–0.4795, not read | 0.2619–0.2687 | 0.2619–0.2687 |

MAP@10's band is the script's alone. With the paper's two best embedders, `bge-large-en-v1.5`
and `voyage-02`, the script gives Hits@4 of 0.6661 and 0.6630, by the paper's 0.6364 and
0.6625, but MAP@10 of 0.2687 and 0.2619 against its 0.4759 and 0.4795; and the file was added
on 2024-03-15, after the paper (v1 of 2024-01-27). The paper's MAP@10 is not what the script
computes, and ours is the script's.

Each official number of the primary list, by its read interval:

- «above the band» — the interval's low end above the band's top;
- «below the band» — its high end below the band's bottom;
- «not detected apart from the band» — otherwise; an end on the band's edge touches it.

The secondary list and «Ours beside» are printed with their intervals, not read against the
band.

What it decides: nothing. MultiHop-RAG is advisory — its labels were written by a model, its
open part has 42 clusters — «совещательно — в общий итог не входит» ([`PLAN.md`](../../PLAN.md),
the bases). No stage of the plan waits on this count or changes with it.

What it does not say. It is not the benchmark's retrieval: other chunks, embedder, reranker and
pool, and 70 inference questions against 2,255 of three types. «Above the band» says that the
script scores our lists higher than the published rows report for theirs — not that our
retriever beats theirs. It changes neither stage 2's metric nor its record: «all
evidence 10 of 70» stays every group covered at «sent». It says nothing of answers.

**Forecast, written before the count.** Its bases. The committed export: at the reranked five
a group is covered for 62 of the 70 (read 0.80–1.00 by `judge_export.share` over stage 2's
clusters), every group for 7; in the whole pool a group for 68. The published rows (the tool's
`PAPER` and `SCRIPT`, the record's `published`): in all six, MRR@10 is 0.88–0.91 of Hits@4 and
Hits@10 1.12–1.14 of it; in the script's two, MAP@10 is 0.44–0.45 of MRR@10. An interval as
wide as stage 2's own over the 15 clusters ends low at about 0.89 of its point
(`evidence_recall` at the five, 0.4077 of 0.4595; a group covered, 0.80 of 0.8857). So:

- Hits@4 0.75–0.90 and Hits@10 0.84–0.97 (the pool's 68 of 70), both «above the band»;
- MRR@10 0.66–0.82, «above the band»;
- MAP@10 0.29–0.37, «above the band» — the nearest call: a point below about 0.30 would read
  «not detected apart from the band»;
- `range_any` at four within 0.10 of Hits@4, with at most 7 questions discordant either way;
- every fact in the first four, by either matching, for at most 7 of the 70;
- the secondary list's Hits@4 not below the primary's.

## Records

- Tool: [`reports/multihop-official/tools/multihop_official.py`](../../reports/multihop-official/tools/multihop_official.py),
  run on the Mac in the gate checkout with the run's folder, the data root and the pinned raw
  file; it writes `record.json` and `rows.jsonl` — ids, flags, counts and numbers, never a text
  of a question, a fact or a document.
- Tests: `tests/test_multihop_official_tool.py` (the official rule's edge cases, the lists and
  the reading on synthetic rows); after the count, an artifact test that reads the record again
  from its rows.
- The record: `reports/multihop-official/5e308fe/`, its capsule in `docs/evidence/`, one row in
  [`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md). Rule (c) at publication: the corpus by the
  archive's, the cases' and the pinned file's SHA-256; the code by the stand's SHA, the
  measuring HEAD and the tool's SHA-256; the config by the run's settings — all in the record.

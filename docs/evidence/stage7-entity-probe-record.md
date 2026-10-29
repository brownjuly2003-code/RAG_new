# Stage 7: the entity extraction's cost — G2 failed at the first look, E stops

Does a full extraction of MultiHop-RAG's 11,231 chunks fit in 24 h on the Mac, with the
product's 4B, the cache's schema and an English prompt? The
[spec](../specs/stage7-entity-probe.md) was registered in `52dd160` before the first request,
with the probe and its test; `27e21fd` wrote that hash in for its placeholder. It follows
[`PLAN.md`](../../PLAN.md) stage 7 and Julia's word of 2026-10-28: both arms stay, the graph and
P1b, and the entity extraction's cost is measured first.
The run `e1` went from 22:07:56 to 22:09:54 UTC on 2026-10-29 on the idle Mac and stopped at
the first look, after ten chunks: G2 failed, by the lower bound.

## Record

`reports/stage7/entity-probe/52dd160/`: `launch.json` (the frozen values, the stand and the idle
check at the start), `chunks.jsonl` (the warm-up and ten chunks, a row each), `end.json` (the
status and the stop, the load, the unload), `e1.log` (a line for the load, each chunk, the look
and the end) and `e1.probe.json` (the probe's `read` of the first three, run on the Mac).
[The test](../../tests/test_stage7_entity_probe_artifact.py) reads them again with the committed
probe and checks:

- the files are the bytes copied from the Mac;
- the probe's `read` of the three files, run again, is `e1.probe.json` byte for byte, by the
  tool the spec lists;
- the gate's four points passed with no note, and the stop again from the rows' seconds: no rule
  before chunk 10, the lower bound at it;
- the frozen values, the idle check, the runner and the unload are the spec's;
- every line of the log is built from the rows and the end;
- the records hold numbers, ids, enums, the model's name and digest, the spec's paths and SHA-256
  strings only.

The record holds no chunk's text, output's text, source name, host name, command line or filled prompt.

## Provenance and method

- **Stand:** the probe at `52dd160`, SHA-256 `68f7e828…` as the spec's Records list it, run by
  the Mac's Python 3.11 with `-I`; Ollama 0.33.2 at `http://127.0.0.1:11434` on the CPU;
  `qwen3:4b-instruct-2507-q4_K_M`, digest `0edcdef34593…`, loaded in 8.435 s with `size_vram` 0,
  `context_length` 4096 and one runner of one slot (`-np 1`, `-c 4096`).
- **Chunks:** `/Users/julia/RAG_new_external_s1/multihoprag/chunks.json.gz`, SHA-256
  `db25b882…`, MultiHop-RAG's second index generation, the one stage 2's retrieval read: 11,231
  chunks. Pick i is index i × 11,231 // 100; the run took picks 0, 10, …, 90 first, after the
  last chunk as its warm-up.
- **The request:** the product's extraction call, one `/api/chat` a chunk with the schema as
  `format`, `temperature` 0, `seed` 42, `num_ctx` 4096, and the digest read again under the same
  timer. No retry.
- **Idle:** the probe's check at the start read a 5-minute load of 1.11, no job by the spec's
  pattern, no CI lock and no model in Ollama (`launch.json`); the launcher found the product's
  service down. After each chunk: no other job, no lock, this model alone.
- **The stop:** the spec's rule 3, at the look after chunk 10: 11,231 × the lower bound above
  86,400 s. The unload took 0.169 s and left Ollama with no model.

## The reading

| Point | Read |
|---|---|
| The gate: launch, rows, end, clean | passed, passed, passed, passed; no note |
| G2 | **failed**, by the lower bound at the look after chunk 10 |
| The look after 10 chunks: the mean, the lower bound, the upper bound | 9.724 s, 8.049 s, 11.400 s |
| The line, 86,400 / 11,231 | 7.693 s |
| 11,231 × the lower bound | 90,396 s, 25.1 h: over 24 h |
| Valid | 10 of 10, 0 empty |

## The chunks

In the run's order. The seconds are the client's, the request and its digest check; the tokens
are Ollama's counters.

| Position | Pick | Index | Characters | Seconds | Prompt tokens | Generated | Entities | Valid |
|---|---|---|---|---|---|---|---|---|
| 0, the warm-up | — | 11,230 | 962 | 11.223 | 300 | 34 | 8 | yes |
| 1 | 0 | 0 | 900 | 8.735 | 320 | 29 | 6 | yes |
| 2 | 10 | 1,123 | 816 | 9.864 | 301 | 42 | 8 | yes |
| 3 | 20 | 2,246 | 517 | 7.061 | 219 | 35 | 8 | yes |
| 4 | 30 | 3,369 | 758 | 12.351 | 313 | 62 | 12 | yes |
| 5 | 40 | 4,492 | 844 | 14.317 | 379 | 66 | 12 | yes |
| 6 | 50 | 5,615 | 888 | 9.850 | 295 | 44 | 9 | yes |
| 7 | 60 | 6,738 | 900 | 10.759 | 304 | 49 | 9 | yes |
| 8 | 70 | 7,861 | 948 | 9.676 | 323 | 37 | 8 | yes |
| 9 | 80 | 8,984 | 385 | 6.771 | 176 | 41 | 8 | yes |
| 10 | 90 | 10,107 | 848 | 7.859 | 272 | 31 | 6 | yes |

## Printed, deciding nothing

| Measure | Value |
|---|---|
| Seconds a chunk: the median, the 90th percentile, the longest | 9.763, 12.351, 14.317 |
| The halves' means: chunks 1–5, chunks 6–10 | 10.466 s, 8.983 s |
| Projected hours, MultiHop-RAG's 11,231 chunks: at the mean, at the upper bound | 30.3, 35.6 |
| Projected hours, ConditionalQA's and WixQA's 51,349: at the mean, at the upper bound | 138.7, 162.6 |
| Prompt tokens, generated tokens: medians a chunk, Ollama's counts | 302.5, 41.5 |
| Prompt tokens a second, generated tokens a second, Ollama's | 60.12, 9.0 |
| The client's seconds over Ollama's own, median | 0.002 |
| Entities, distinct keys, their pairs: medians a chunk | 8, 8, 28 |
| A chunk's characters, median | 846 |
| Reloads; done reasons | 0; `stop` 10 |
| The warm-up | 11.223 s, `ok` |
| The load: seconds; size and size_vram, bytes; context_length; runners, -np, -c | 8.435; 3,184,001,022 and 0; 4096; 1, 1, 4096 |
| The run's seconds; its wall time | 117.301; 117.493 |
| Load average over 1, 5 and 15 min: at launch; at the end | 1.15, 1.11, 1.24; 5.79, 2.80, 1.88 |
| Swap used, MiB: at launch; at the end | 2,190.5; 2,532.2 |
| The unload's seconds; Ollama's models after it | 0.169; none |

## Forecast and outcome

| Forecast, written before the first request | Measured |
|---|---|
| So **G2 fails at the first look**, the mean 2–7 × the line, with 10 of 10 valid | failed at the first look, by the lower bound; the mean 1.26 × the line; 10 of 10 valid |
| Low 210/42 + 40/4.0 = 15.0 s; mid 210/33 + 65/3.0 = 28.0 s; high, nothing reused, 295/24 + 90/2.1 = 55.2 s; idle, at the known 4.3–4.7 tokens a second, 210/42 + 65/4.5 = 19.4 s | 9.724 s at the mean, under the low case |
| At 24–42 prompt tokens a second and 2.1–4.0 generated | 60.12 prompt tokens a second and 9.0 generated, Ollama's |
| ≈ 210 new a chunk (a median 850 characters in `reports/external/36f1167/connection.json`); 40–90 generated | Ollama's prompt count a median 302.5, the text a median 846 characters; generated a median 41.5, 29–66 |
| At ≈ 20 s, ≈ 62 h for MultiHop-RAG and ≈ 285 h for ConditionalQA and WixQA | at the mean, 9.724 s: 30.3 h and 138.7 h |
| GR-2's 11.4 s for a 7B is faster than these rates allow the 4B; the probe settles it | the 4B 9.724 s a chunk at the mean, under the 7B's 11.4 s |
| The Mac ≈ 5 min (the load 31–51 s in step 1, the warm-up ≈ 25 s, ten chunks), 3–11 min across the cases | 117.493 s in all: the load 8.435 s, the warm-up 11.223 s, ten chunks |

## What it says

- **G2 failed, so E stops**, by the spec: «Past G2 the full extraction of MultiHop-RAG runs;
  else E stops. The numbers are published either way.» Even
  the lower bound of the mean, 8.049 s, puts MultiHop-RAG's 11,231 chunks at 25.1 h
  over the 24 h; at the mean they take 30.3 h, at the upper bound 35.6 h. Stage 7 goes on with H,
  S and P — the hybrid, the structural graph and P1b — in step 1's arms replay at M3 on stage
  2's lists, without E.
- **The extraction works; its price stops it.** With 10 of 10 outputs valid under the cache's
  acceptance rule and none empty, a chunk gave a median 8 entities, each a distinct key, and 28
  pairs: the English prompt and the schema hold on English news.
- **The survey priced E too high, and the line still holds.** The Mac
  read 60.12 prompt tokens a second and wrote 9.0, against the 24–42 and 2.1–4.0 the survey took
  from step 0's 15 chat requests, on a Mac other projects kept busy. A chunk took 9.724 s at the
  mean, under the forecast's low case of 15.0 s, and the run stopped at
  1.26 × the line at the mean, not the forecast's 2–7 ×.
- The probe is no slice by the acceptance rule (the spec's
  [Records](../specs/stage7-entity-probe.md#records)): it changes no behaviour, case or quality
  number; it prices E, and the price stops it.

## What it does not say

- **Ten chunks, by design.** The spec's sequential stop reads the lower bound after chunks 10,
  20, 40 and 70; after 10 it was over the line. The interval is no nominal 95 % interval for the
  mean of all 11,231 chunks: the picks are fixed and systematic, and llama-server's caches change
  as a run goes. The halves' means, 10.466 s and 8.983 s, decide nothing.
- **The entities' quality is not read.** Counts only; whether E helps would have been its replay
  at M3, past G2.
- **No other way to extract was tried.** One prompt, one schema, one model, one chunk a request.
  A shorter output, several chunks a request or another machine might cost less; each would be a
  spec of its own, and none is planned.
- One corpus, English news, one stand and one day, on a Mac other projects share; the other two
  bases' hours, 138.7 at the mean, decide nothing.
- **Why the rates were faster is not read:** a prompt of ≈ 300 tokens against the chat's
  ≈ 2,300, an idle Mac against a busy one, or both. `prompt_eval_count` may count only the tokens
  not reused: the rates printed are Ollama's, of its counters.
- The load average at the end, 5.79 over one minute, is the probe's own generation on the Mac's
  four cores. The idle rule held at the start, and after each chunk for what it reads: no other
  job by pgrep's pattern, no CI lock, this model alone. A job of another name, or another client
  of this model that did not reload it, passes unseen.

## Files

| File | Bytes | SHA-256 |
|---|---|---|
| `launch.json` | 2,734 | `2f14772b476ae64274fd8f906e835e61a9a93c66cba3d54c8c2038b2661c32ec` |
| `chunks.jsonl` | 7,338 | `2e6234bda0a124ccf40d76ed3ce878ad2f18b5ef07dc4a6820820254021324d0` |
| `end.json` | 627 | `c7a634a219dff511296f76f502fec8d9508bec4aa39ca228b0e6162927781d2d` |
| `e1.log` | 1,073 | `376d85c6e1b467b6038b8eacd2ae8a45830145938619a55a9a8d78183ef6ff50` |
| `e1.probe.json` | 1,995 | `82a973b60896fb09625b32f3365cf30656603dddbe949c01bdb028ff3efa5d37` |

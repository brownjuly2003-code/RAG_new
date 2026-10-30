# Stage 4, item 5: thirty questions under a 1,024-MiB prompt cache — the swap holds — 2026-10-30

The question: does the swap stop climbing when llama-server's host prompt cache is capped at
1,024 MiB? [`PLAN.md`](../../PLAN.md) stage 4, item 5: «Проверка — серия из 30 вопросов, своп не
растёт (≈ 2,5 ч)». Step 0 ([its record](stage4-step0-record.md)) named the cache as llama-server's
growth. `19beeb1`'s rerun of these thirty questions, without a limit, rose from 0.9–1.3 GB of swap
at question 1 to 9.3–10.9 GB at question 13, and was at 9.3–11.0 GB at question 30. Under Julia's
«да» of 29.10, the line `cache-ram = 1024` stood in `~/.config/llama.cpp/config.ini` for this
series only, by [`stage4-step5-cache-cap-series.md`](../specs/stage4-step5-cache-cap-series.md).
The spec was registered with its reader and the reader's test in `f214459` before the first
request (`2b44bb6` wrote the commit into it); nothing changed after it. The series ran on
2026-10-30 between 03:35 and 06:33 UTC, the sampler's first and last rows.

Record: [`reports/stage4-step5/4f48fed/`](../../reports/stage4-step5/4f48fed/):
- `step5.json`: the series — step 0's read of the log and the run, the questions, the cache, the
  gate, the disturbance, the reading and what is printed beside it;
- `s5-30.samples.jsonl`: step 0's sampler, a row every 10 s;
- `environment.jsonl`: V4's `stand_env.py`, a line before the series and one after it.

Every number below is the record's unless named otherwise. `19beeb1`'s are its record's
([`runs.json`](../../reports/chat-live-4b/19beeb1/runs.json), run `qwen3-4b-instruct-q30-r2`):
each question's lowest and highest swap in use, in MB as it prints them, and their midpoints.

The reader is
[`reports/stage4-step5/tools/step5_reader.py`](../../reports/stage4-step5/tools/step5_reader.py),
with step 0's reader and sampler. Checked by
[`tests/test_stage4_step5_artifact.py`](../../tests/test_stage4_step5_artifact.py):
- the files are the bytes copied from the Mac, read by the tools the two specs list, by SHA-256;
- each request's windows and each question's row are read again from the committed samples with
  the committed tools — all but the API's RSS, whose `resources.jsonl` stays on the Mac;
- the cache, the gate, the reading and the printed numbers follow from the record by the reader's
  own functions;
- the gate passed, the limit stood on every cache-state line, nothing disturbed the series;
- the stand is step 0's: V4's code, drivers, model and digest, the questions in their order, one
  Ollama 0.33.2 server before and after;
- the files hold numbers, times, ids, enums, a model name, versions, package names, the paths the
  spec names and SHA-256 strings only;
- every table row below is built from the record, and so is every number of the prose that comes
  from this record or `19beeb1`'s; the others are the spec's or marked mine.

The record holds no question, document, answer, prompt, log line or command line.

## Provenance and method

- **Stand:** step 0's, `S=/Users/julia/RAG_new_chat_4f48fed` at `4f48fed`, V4's four `chatlive/`
  drivers by SHA-256, the supervisor's model `qwen3:4b-instruct-2507-q4_K_M` (`0edcdef34593…`) on
  the CPU, mode `prod`, tenant `aircargo`, a byte-identical copy of the index made before the run
  and removed after it.
- **One process for the thirty:** a fresh API, database and llama-server; the model loaded in
  16.724 s before the first question, and the supervisor unloaded it at its end (`/api/ps` empty
  after it, mine).
- **The limit:** the line went in after the spec's idle check passed, its SHA-256 the spec's
  `c75f4491…`, before the sampler's first row (mine, from the launch's output). llama-server
  named `/Users/julia/.config/llama.cpp/config.ini` as it started, and each of the 89 cache-state
  lines printed the limit 1,024.0 MiB. The guard removed the line at 06:33:01 UTC, after the
  supervisor's exit, and the folder was gone (mine, from the guard's log on the Mac and `ls`).
- **Questions:** aircargo's first thirty, `aircargo-probation-data` to `aircargo-road-seal`, in
  `19beeb1`'s order; routes as V4's, `aircargo-probation-extend` `human` and the others `auto`;
  89 requests, each one model call (calls = matched = requests = 89).
- **The reading,** frozen in the spec: a question's swap is the median of the samples inside its
  window; the growth is the median over questions 26–30 less the median over 6–10; it **holds**
  below 512 MiB.

## The reading

| | This series, MiB | `19beeb1`'s rerun, midpoints, MB |
| --- | ---: | ---: |
| Questions 6–10 | 3,437.5 | 5,691.5 |
| Questions 26–30 | 3,257.25 | 10,143.625 |
| Growth | −180.25 | +4,452.125 |
| «Своп не растёт»: growth below 512 MiB | **holds** | grows |

The gate passed with no reason, and the series was not disturbed: one llama-server pid, no Python
other than the API at 512 MiB or more, no virtual machine among the five largest.

## Per question

This series' memory in MiB; `19beeb1`'s swap in MB, as its record prints it. The cache is
llama-server's as the question's last request arrived.

| n | Question | Route | Seconds | Swap, median | Swap, highest | `19beeb1`'s swap | Footprint, median | API RSS, median | Load, 5 min | Cache | Removed |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `aircargo-probation-data` | auto | 366 | 2,505.5 | 2,696.2 | 914.8–1,339.0 | 3,179 | 1,628 | 3.00 | 694.9 | 0 |
| 2 | `aircargo-probation-extend` | human | 371 | 2,811.0 | 3,143.0 | 983.8–1,708.5 | 3,937 | 1,062 | 4.49 | 775.2 | 1 |
| 3 | `aircargo-probation-dismissal` | auto | 332 | 3,025.0 | 3,143.0 | 1,635.8–2,298.0 | 3,956 | 1,206 | 4.52 | 690.4 | 4 |
| 4 | `aircargo-dismissal-check` | auto | 333 | 3,276.8 | 3,340.8 | 2,177.2–3,545.2 | 3,931 | 1,334 | 4.88 | 751.3 | 2 |
| 5 | `aircargo-dismissal-lawyer` | auto | 441 | 3,367.8 | 3,471.8 | 3,422.8–3,963.0 | 3,932 | 1,286 | 4.70 | 730.9 | 3 |
| 6 | `aircargo-dismissal-order` | auto | 350 | 3,389.5 | 3,613.5 | 3,899.0–4,728.2 | 3,916 | 1,396 | 4.66 | 748.0 | 3 |
| 7 | `aircargo-leave-sources` | auto | 359 | 3,393.5 | 3,552.2 | 4,646.0–5,345.2 | 3,929 | 1,342 | 4.29 | 733.8 | 3 |
| 8 | `aircargo-leave-compensation` | auto | 388 | 3,437.5 | 3,548.0 | 5,246.2–6,136.8 | 3,914 | 1,369 | 4.14 | 705.6 | 3 |
| 9 | `aircargo-leave-risk` | auto | 331 | 3,455.2 | 3,561.8 | 6,029.2–7,406.0 | 3,886 | 1,364 | 3.93 | 1,022.7 | 2 |
| 10 | `aircargo-matliab-check` | auto | 329 | 3,519.2 | 3,807.0 | 7,323.5–8,201.5 | 4,203 | 1,448 | 4.18 | 705.9 | 4 |
| 11 | `aircargo-matliab-disputed` | auto | 331 | 2,630.2 | 2,728.0 | 7,759.0–9,559.8 | 3,887 | 1,455 | 4.34 | 712.2 | 3 |
| 12 | `aircargo-templates-choose` | auto | 323 | 2,615.8 | 2,943.5 | 8,535.2–10,141.2 | 3,893 | 1,329 | 4.53 | 1,022.7 | 2 |
| 13 | `aircargo-templates-checklist` | auto | 373 | 2,944.8 | 3,198.0 | 9,329.5–10,918.8 | 4,204 | 1,391 | 4.62 | 719.8 | 4 |
| 14 | `aircargo-templates-insufficient` | auto | 284 | 3,051.0 | 3,211.0 | 8,703.5–10,255.5 | 3,901 | 1,344 | 4.46 | 689.4 | 3 |
| 15 | `aircargo-secret-check` | auto | 295 | 3,221.1 | 3,306.2 | 9,457.2–11,010.8 | 3,890 | 1,195 | 5.20 | 730.6 | 3 |
| 16 | `aircargo-secret-not-auto` | auto | 252 | 3,277.5 | 3,359.2 | 9,361.2–11,767.2 | 3,911 | 1,408 | 5.77 | 707.7 | 3 |
| 17 | `aircargo-secret-disclosure` | auto | 252 | 3,355.5 | 3,437.5 | 9,348.2–10,935.5 | 3,897 | 1,498 | 5.81 | 733.6 | 3 |
| 18 | `aircargo-pdp-scope` | auto | 238 | 3,289.0 | 3,423.8 | 9,465.2–11,654.2 | 3,914 | 1,248 | 5.67 | 694.9 | 3 |
| 19 | `aircargo-pdp-data` | auto | 307 | 3,312.0 | 3,593.5 | 9,436.2–10,311.8 | 3,903 | 1,161 | 5.83 | 751.8 | 3 |
| 20 | `aircargo-pdp-uncertain` | auto | 281 | 3,482.5 | 3,674.5 | 9,374.0–11,524.0 | 3,933 | 1,232 | 5.58 | 711.1 | 3 |
| 21 | `aircargo-claims-delay` | auto | 265 | 2,711.2 | 3,000.5 | 8,257.5–9,900.2 | 3,942 | 1,295 | 5.49 | 701.2 | 3 |
| 22 | `aircargo-claims-damage` | auto | 516 | 2,932.0 | 3,368.2 | 9,209.5–10,778.2 | 3,882 | 898 | 4.87 | 762.0 | 3 |
| 23 | `aircargo-claims-lawyer` | auto | 503 | 3,215.0 | 3,621.8 | 8,626.0–10,184.0 | 3,943 | 727 | 6.75 | 771.4 | 3 |
| 24 | `aircargo-claims-forbidden` | auto | 511 | 2,716.9 | 3,283.2 | 9,407.2–10,825.2 | 3,952 | 864 | 6.99 | 770.8 | 3 |
| 25 | `aircargo-expedition-vs-carrier` | auto | 336 | 3,627.0 | 3,742.5 | 9,129.0–11,766.5 | 3,952 | 1,209 | 6.74 | 748.5 | 3 |
| 26 | `aircargo-expedition-mawb-hawb` | auto | 499 | 3,257.2 | 3,681.0 | 9,265.0–10,782.8 | 3,929 | 1,035 | 5.67 | 781.5 | 3 |
| 27 | `aircargo-expedition-risks` | auto | 499 | 3,485.8 | 3,915.8 | 9,766.2–11,506.5 | 3,962 | 873 | 7.29 | 755.5 | 3 |
| 28 | `aircargo-road-cutoff` | auto | 292 | 2,852.0 | 3,111.5 | 8,728.5–12,273.8 | 3,958 | 1,226 | 7.45 | 782.4 | 3 |
| 29 | `aircargo-road-penalty` | auto | 290 | 3,219.5 | 3,314.2 | 8,531.5–10,105.0 | 3,963 | 1,317 | 6.31 | 727.7 | 3 |
| 30 | `aircargo-road-seal` | auto | 298 | 3,298.6 | 3,425.0 | 9,309.0–10,978.2 | 3,945 | 1,413 | 5.33 | 796.1 | 3 |

## Printed, deciding nothing

| Printed | Value |
| --- | --- |
| llama-server's footprint, 26–30 less 6–10 | +42.0 MiB |
| The API's RSS, 26–30 less 6–10 | −142.744 MiB |
| The swap's slope from question 6 | −2.604 MiB a question |
| The swap at the first and the last sample | 2,543.0 and 2,219.5 MiB |
| The swap's highest inside the questions | 3,915.75 MiB |
| The cache's highest | 1,023.274 MiB |
| Entries removed, and their size | 85, 21,186.672 MiB |
| Saves skipped | 0 |
| The questions' seconds, median and sum | 331.706 and 10,545.79 |
| The 5-minute load, median | 5.037 |
| The config file llama-server named | `/Users/julia/.config/llama.cpp/config.ini` |

- **The swap's medians** stayed within 2,505.5–3,627.0 MiB question by question; their slope from
  question 6 is the −2.604 MiB above.
- **llama-server's footprint** was 3,179 MiB in question 1, then 3,882–4,204 MiB: the model and a
  cache held at its limit.
- **The seconds:** the thirty took 2.93 h. `19beeb1`'s rerun took 9,482.248 s, a median
  319.629 s, on other code. Five questions — 22, 23, 24, 26 and 27 — took 499–516 s; the other
  twenty-five took a mean 320.7 s. In those five the API's RSS medians were 727–1,035 MiB,
  against 1,062–1,628 MiB in the others; their swap medians stayed inside the others' range.
- **Mine,** from the supervisor's `resources.jsonl` on the Mac (its SHA-256 is in the record): in
  each of those five a Google Chrome renderer was the busiest process after llama-server and the
  API, at a mean 5–15 % CPU; so it was in question 25 too, at 7 %, and question 25 took 336 s.
  Nothing here says what slowed the five. The spec's disturbance names only another model, a
  large Python process and a virtual machine, not a browser.

## Forecast and outcome

| Forecast, the spec's | Outcome | Held |
| --- | --- | --- |
| The gate passes, the series is not disturbed | passed, not disturbed | yes |
| The swap holds, its growth within ± 256 MiB | holds, −180.25 MiB | yes |
| The cache at most 1,024 MiB from question 2, removing entries from then | at most 1,023.274 MiB, the first removal in question 2 | yes |
| llama-server's footprint within ≈ 3,174–4,198 MiB | the questions' medians 3,179–4,204 MiB | 6 MiB over the ≈ |
| The swap at questions 26–30 below 5,000 MiB | at most 3,915.75 MiB | yes |
| The thirty in ≈ 2.3–2.7 h | 2.93 h | no |

The time missed on five questions: the other twenty-five's mean gives 2.67 h for thirty, inside
the forecast.

## What it says

- **Under the limit the swap does not grow:** −180.25 MiB from questions 6–10 to 26–30, where the
  same thirty questions without it grew +4,452.125 MB by the same rule. Item 5's check,
  «своп не растёт», is met by the limit, the first of PLAN's two candidates.
- **Step 0's cause fits:** capped, the cache stayed at or under 1,024 MiB on all 89 requests, and
  llama-server's footprint at 3,882–4,204 MiB from question 2 on, where `19beeb1`'s reached 11 GB
  (the spec's). The cache removed 85 entries, 21,186.672 MiB in all; step 0 saw no state restored,
  so the removals take away no reuse step 0 saw.
- **The line reached llama-server and left with the series:** the config file named at its start,
  the limit on every cache-state line, the line removed by the guard after the supervisor's exit.

## What follows

- The limit enters the product only by Julia's word ([`PLAN.md`](../../PLAN.md) §8.3), by one of
  item 5's two routes: the config line, which every llama.cpp program of the user reads, or
  `LLAMA_ARG_CACHE_RAM` in `ollama serve`'s environment, which needs `ollama serve` restarted. The
  line is gone; it comes back only by her word (§8.1).
- PLAN's other candidate, unloading every N requests or at a swap threshold, is not needed for
  this check.

## What it does not say

- **One series, one corpus, one draw,** in one process on a shared Mac, a browser among its
  busiest processes in questions 22–27 (mine). Not another corpus, model or number of questions.
- **Not the limit's cost in seconds:** they are printed, not tested; `19beeb1`'s code differs from
  this stand's, and the five slowest fell in questions 22–27.
- **The swap is the whole Mac's:** macOS gives swap back slowly, so its level carries what ran
  before — 2,543.0 MiB at the first sample. The reading reads its growth, not its level.
- **Not quality:** no answer is graded here. Not the other route, and not an unload every N
  requests.

## Files

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `step5.json` | 279,819 | `4d3175763ffb7d997a6d49ea5775f96703c88e2b5f3ddce6c74691dc93460f5f` |
| `s5-30.samples.jsonl` | 685,939 | `74dc38327655fe98e63f9f975dd3feb1028f5c4b2279a379514197b5686dddd9` |
| `environment.jsonl` | 1,964 | `487ec1a275a583c770e04dd4c6cde3b790da3467f7ccee11df9d20990156382b` |

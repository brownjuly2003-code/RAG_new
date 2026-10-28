# Stage 6, item 4: the service's questions an hour, and what a second client sees

Status 2026-10-28: **a draft, not registered.** It is registered before the first request: the
runner, the reader and their test are committed with it, and their SHA-256 are listed under
[Records](#records). That happens once the service is installed
([`macos-service.md`](../operations/macos-service.md)) on Julia's word.

This is [`PLAN.md`](../../PLAN.md) stage 6, item 4 («≈ 1 ч»). Its number and its behaviour go
into the interface's text (item 6). Two values are filled in at launch:
- `<c>`, the commit that registers this spec;
- `<s>`, the service's `CODE_SHA`.

## Why

Before the interface promises anything, item 4 asks two things:
- how many questions an hour the installed service answers on this Mac (PLAN.md: ≈ 10–12);
- what a second visitor sees while a first is being answered: a queue or a refusal.

**What the code says about the second visitor:**

- **Up to 8 at once.** The API admits up to `MAX_CONCURRENT_PIPELINES` = 8 questions at once
  (an asyncio semaphore, `api/app.py` `_get_pipeline_semaphore`).
- **A ninth is refused.** It waits `PIPELINE_ACQUIRE_TIMEOUT_SEC` = 0.5 s for a slot, then
  gets the busy reply (`api/routers/conversation.py`):
  - `/api/ask/stream` answers HTTP 200 with one event, `{"type": "error", "detail": "Server is
    busy processing other requests - retry in a moment"}`, and closes;
  - `/api/ask` answers 503 with the same detail;
  - both count `rag_pipeline_rejections_total{reason="busy"}`.
- **A second is admitted.** Its retrieval runs in its own thread beside the first's: the
  request executor has as many workers as the semaphore has slots
  (`utils/request_executor.py`).
- **Its model calls wait at Ollama.** Ollama 0.33.2 starts llama-server with one slot
  ([stage 4, step 0](stage4-step0-diagnostics.md)). A question makes up to three model calls:
  the answer, the self-evaluation and the suggestions, which the `human` route skips.

So by the code, two clients form a queue, and each waits longer. This measurement checks that
and gives the numbers. Eight clients do not fit the 8 GB, so the ninth client's refusal stays
the code's word, not a measured one.

## The service, as installed

- **The service:** the one of [`macos-service.md`](../operations/macos-service.md) at `<s>`, with
  the memory policy stage 4 named and the code defaults. start.py's start lines name the policy
  and the settings off the default, and the record keeps both by name.
- **The Mac:** no other measurement runs on it. The idle checks of stage 4, step 0 apply:
  - the 5-minute load is below 2;
  - no pytest, supervisor, replay or CI VM process, and no `ci_local` lock;
  - the service healthy (`healthcheck.py` exits 0) with nothing in flight.
- **A restart before part A,** with the model unloaded first (`keep_alive: 0`). Part A's first
  question then includes the model's load, as a visitor's does after an idle spell.
- **The tenant and the questions:** tenant `aircargo`. The questions are
  `evaluation/curated_cases_aircargo.jsonl` at `<s>`, and the record keeps the file's SHA-256.

## The questions

The first eleven of aircargo's registered order: V4's batch 1 and the first question of batch 2,
each timed alone in V4 ([`v4-aircargo.cases.jsonl`](../../reports/answer-prompt-v4/4f48fed/v4-aircargo.cases.jsonl)).

**Part A, one client, seven questions in order:**
- `aircargo-probation-data`
- `aircargo-probation-extend`
- `aircargo-probation-dismissal`
- `aircargo-dismissal-check`
- `aircargo-dismissal-lawyer`
- `aircargo-dismissal-order`
- `aircargo-leave-sources`

**Part B, two clients, two questions each:**
- client 1: `aircargo-leave-compensation`, then `aircargo-leave-risk`;
- client 2: `aircargo-matliab-check`, then `aircargo-matliab-disputed`.

Client 2 sends its first question 60 s after client 1, during client 1's retrieval (V4's median
retrieval is 122 s).

**How each question is asked:**
- **As a visitor's first:** `POST /api/ask/stream` with no session id, as
  `reports/stage1/tools/live_runner.py`'s `ask` sends it.
- **Each client is a closed loop.**
  - In part A, the next question goes when the stream has closed and `/metrics` reads 0 for
    both `rag_inflight_pipelines` and `rag_orphan_work_inflight`, so no question's work overlaps
    the next.
  - In part B, each client sends its next question as soon as its own stream closes.
- **Between the parts:** both gauges at 0.
- **The token:** `create_access_token("stage6-throughput", role="admin", tenant="aircargo")`
  (`auth/jwt_handler.py`), signed with the service's `JWT_SECRET`. The runner reads that one key
  from the service's env file into its own process with start.py's reader. It never prints or
  writes the key or the token.

## What is read

**Per question:**
- the case id, the part and the client;
- the send time (UTC and `time.monotonic()`) and the HTTP status;
- the seconds to the first token, to the result event and to the end, and the token count;
- the result's route;
- whether an error event came and its kind: `busy` when its detail is the busy text above,
  else `other`; the detail itself is not kept;
- a client error, by its type.

**Every 5 s,** by a sampler thread of the runner:
- `/metrics`' `rag_inflight_pipelines`, `rag_orphan_work_inflight` and
  `rag_pipeline_rejections_total` by reason;
- the number of models in Ollama's `/api/ps`;
- `vm.swapusage`'s used swap and `vm.loadavg`.

**At each part's start and end:** healthcheck.py's JSON, which holds states, names and numbers
only.

## How it is read — frozen before the first request

Each reading below is computed by the reader from the record.

**Answered**, as in live_runner's `answered`: the question streamed tokens and got a result event
whose route is not `timeout`, with no error event and no client error.

- **R1, questions an hour with one client:** 7 ÷ (part A's first send → its last result event)
  × 3,600.
- **R1s, the warm service's pace:** the same for A's six later questions: 6 ÷ (A's second send →
  its last result event) × 3,600.
- R1 and R1s are `NOT_EVIDENCE` unless all seven questions of A are answered.
- **R2, questions an hour with two clients:** 4 ÷ (part B's first send → its last result event)
  × 3,600.
- **R3, what the second client sees:**
  - **queue** when all four questions of B are answered, the `busy` counter did not change, and
    some 5-s sample read `rag_inflight_pipelines` ≥ 2 (both questions in the API at once);
  - **refusal** when a question of B got a `busy` error event;
  - else `NOT_EVIDENCE`.
- **R4, what sharing costs a question:** the median total of B's four ÷ the median total of A's
  six later questions.
- **R4f:** the same ratio for the first token.

**What item 6 gets:** R1s rounded down (questions an hour), R3, and B's median total, the wait of
a visitor answered beside another. The wording is item 6's.

## Forecast, written before the first request

The forecast is built from V4 (`4f48fed`, 100 questions in 10 batches):
- a question's median is 296.3 s, and 295.2 s for the later questions of a batch;
- the model's load is 51.0 s;
- batch 1's questions run 374.9, 306.7, 262.6, 350.1, 226.2, 230.4 and 215.9 s in part A's
  order.

**Part A** takes 51.0 + 374.9 + 1,591.9 (the six later) = 2,017.8 s, ≈ 33.6 min:
- R1 ≈ 12.5 an hour;
- R1s ≈ 13.6 an hour, or ≈ 12.2 at V4's later median.

**Part B.** The Mac does one question's work at a time, so B's four take about the sum of their
times alone, 214.5 + 237.3 + 295.1 + 281.0 = 1,027.9 s, ≈ 17.1 min:
- R2 ≈ 14.0 an hour: no gain over one client;
- R3 is a queue;
- each question shares the Mac with the other client's for nearly its whole run, so it takes
  ≈ twice its time alone: 429, 475, 590 and 562 s;
- R4 ≈ 518.3 ÷ 246.5 ≈ 2.1, and R4f ≈ 2 (mine).

**The policy's cost:** under an unload policy, each unload adds the 51-s load to the next question.

**In all:** ≈ 51 min plus ≈ 10 min of checks and copies, PLAN's ≈ 1 h.

## Running it

These steps run on the Mac with `PY`, `S=/Users/julia/RAG_new_service` and
`T=/Users/julia/stage6-throughput/<s>`, which is outside the checkout. Each part starts detached,
so ssh returns at once.

1. **Tools:** `mkdir -p $T`. From the laptop, for each tool `<f>`, run `git -C D:/RAG_new show
   <c>:reports/stage6-throughput/tools/<f> | ssh deproject-mac "cat > /Users/julia/stage6-throughput/<s>/<f>"`. Then
   `shasum -a 256 $T/*.py` prints the list under Records.
2. **Idle:** the checks under "The service, as installed". Otherwise wait; nothing is stopped.
3. **Restart:**
   - unload the model (macos-service.md, "Before a measurement", step 3);
   - run `launchctl kickstart -k gui/$(id -u)/com.rag-new.chat`;
   - wait until healthcheck.py exits 0, then write its JSON to `$T/health.jsonl`.
4. **Part A:** `nohup $PY -I $T/throughput_runner.py A $T > $T/A.err 2>&1 </dev/null &`. Its
   end is the line `THROUGHPUT_DONE A` in `$T/A.err`.
5. **Part B:** `nohup $PY -I $T/throughput_runner.py B $T > $T/B.err 2>&1 </dev/null &`. It
   ends the same way.
6. **The readings:** `$PY -I $T/throughput_reader.py $T` writes `$T/throughput.json`. The
   record's files are then copied to the laptop as bytes.

## Stops

Each cap is 3× its forecast. Julia's rule: 3× each question's forecast.

**A question past its cap:**
- part A's first question: 1,280 s (3 × 425.9);
- A's later questions: 900 s (3 × 295.2, rounded up);
- part B's questions: 1,800 s (3 × 590, twice V4's later median).

At that cap the runner closes the question's stream (the service's own limits stay 3,600 s) and
stops the part. The part's unread questions are `NOT_EVIDENCE`.

**A part past 3× its forecast:** part A at 101 min, part B at 52 min. The runner stops itself.

**A refusal does not stop the run.** It is R3's reading.

**After any stop:**
- the runner waits up to 10 min for both gauges to read 0, then writes healthcheck.py's JSON;
- the measurement ends, and Julia gets the measured pace.

## Records

The record is `reports/stage6-throughput/<s>/`. It holds four files:
- `questions.jsonl`: one line per question, with the fields above;
- `samples.jsonl`: the 5-s samples;
- `health.jsonl`: healthcheck.py's JSON at each part's start and end;
- `throughput.json`: the readings with the forecast beside them. It also names `<c>`, `<s>`,
  the policy, the questions file's SHA-256 and, by name, the settings off the code default.

**What it holds:** numbers, enums, ids and SHA-256 strings. **What it never holds:** a question's
or an answer's text, an error's detail, a log line, a command line, the environment or a token.
The eleven sessions the measurement opens stay in the service's database under the user
`stage6-throughput`, and the record does not read them.

**Not a slice by itself.** Item 4 is no slice by the acceptance rule; its numbers become one
through item 6's text and item 7's E2E test (rule (a)). Its record gets a row in
[`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md) and a test that reads it again.

**The tools and their test,** committed with this spec. Each SHA-256 is checked by the test, and
a later change is a marked error fix that updates the list:
- `reports/stage6-throughput/tools/throughput_runner.py` `<sha256>`. It is built from
  live_runner's `ask` and `answered` and adds the sampler, the second client and the caps.
- `reports/stage6-throughput/tools/throughput_reader.py` `<sha256>`
- `tests/test_stage6_throughput_tools.py` `<sha256>`

## Not said

- **One draw:** eleven questions of one corpus and at most two clients. It is no capacity curve,
  and the ninth client's refusal is read from the code, not measured.
- **No SLO.** Stage 4, item 7 proposes one, and Julia names it. These numbers are a pace under
  one memory policy on this Mac.
- **No idle time.** Part B's clients read nothing between questions. A visitor who reads leaves
  the Mac idle, so R2 is the pace with no idle time, not a visitor's.
- Nothing is said about the answers' quality.

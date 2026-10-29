# Stage 7: the entity extraction's cost — an English prompt on 100 MultiHop-RAG chunks

Status 2026-10-29: **registered before the first request**, with the probe and its test, whose
SHA-256 are listed under [Records](#records); revised before that after
[a second opinion and its second pass](#a-second-opinion). It
follows [`PLAN.md`](../../PLAN.md) stage 7 and Julia's word of 2026-10-28 («P1b и граф»: both
arms stay, the entity extraction's cost measured first). `52dd160` is the commit that registers
it; the next one wrote its hash where the registered text had a placeholder.

## Why

- **E needs a full extraction first.** The entity lane (`ingestion/entity_graph.py`,
  `ingestion/entity_retrieval.py`) reads a cache of entities a chunk. GR-3's graph does not fit
  the chunks stage 1 rewrote (PLAN stage 2, item 3), none exists for the external bases, and the
  one prompt, `EXTRACT_PROMPT`, is Russian and written for corporate regulations.
- **The survey's arithmetic** priced E out of a default. At 24–42 prompt tokens a second and
  2.1–4.0 generated (the 4B on the shared Mac; [step 0](../evidence/stage4-step0-record.md) saw
  27–29 ms a prompt token and 2.1–4.0), prompts of 300–460 tokens (aircargo's) and 40–90 out
  (assumed), a chunk takes 17.1–62.0 s: 53.3–193.4 h for MultiHop-RAG's 11,231 chunks,
  243.9–884.3 h for ConditionalQA's and WixQA's 51,349. Its one measured anchor, GR-2's
  qwen2.5:7b with the schema, 11.4 s a chunk on eight aircargo chunks
  ([GR-2](../operations/gr2-entity-builder-preparation.md)), scaled by size to ≈ 6 s, falls
  under the line below. They disagree, so it is measured.
- **Gate G2:** stop E if 11,231 × the upper bound of the mean's 95 % interval exceeds 24 h — a
  bound above 86,400 / 11,231 = 7.693 s a chunk — or if fewer than 95 of the 100 outputs are
  valid. The 24 h are the survey's: PLAN priced the whole live entity lane at ≈ 25–30 h. Past
  G2 the full extraction of MultiHop-RAG runs; else E stops. The numbers are published either way.
- **100 chunks,** where PLAN says «100 документах»: the price is a chunk's; 100 documents would
  be ≈ 1,844 chunks (11,231 × 100 / 609) for the same reading.

## The stand

- **Code:** `reports/stage7/tools/entity_probe.py` at `52dd160`, the standard library only, run by
  `PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python` (3.11) with `-I`. It imports nothing
  of the product and sends what the product's extraction sends
  (`scripts/extract_graph_entities.py` through `llm/providers/pinned_ollama.py`).
- **Model:** `qwen3:4b-instruct-2507-q4_K_M`, digest
  `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`, in Ollama 0.33.2 at
  `http://127.0.0.1:11434` on the Mac's CPU (step 0); the probe loads it with the request's
  options and unloads it after.
- **The stand at the start and in the gate:** Ollama's version from `/api/version`, the
  endpoint, `platform.system()` and `platform.machine()` must be 0.33.2, that endpoint, `Darwin`
  and `x86_64`. The probe refuses at the start when one differs (exit 3, nothing written);
  `launch.json` records them, and the gate requires them again; no host name is recorded. After
  the load `/api/ps` must show the model with `size_vram` 0, every buffer on the CPU
  (`MemorySize()` and `isGPUBuffer()` in `llm/llama_server.go` of Ollama v0.33.2), and
  `context_length` 4096, the runner's `NumCtx` (`ContextLength()` there), which does not show
  the slots. So `pgrep -f '[l]lama-server'` must find one runner, started with `-np 1` and
  `-c 4096`: Ollama starts it with `-c` `NumCtx` × the slots and `-np` the slots,
  `OLLAMA_NUM_PARALLEL`, 1 by default (`envconfig/config.go`), and a second slot would let
  another client's request run beside the probe's. The Mac's runner had both on 2026-10-29,
  read during step 2b's run. Its arguments are read by `ps` and dropped: the count of runners
  and the two integers are kept, never a command line. Else the run is broken, `stand`, before
  the warm-up.
- **The request:** `POST` to `/api/chat` with one user message, the prompt below filled with the
  chunk's `page_content` (its contextual header included), `stream` false, `keep_alive` `30m`,
  `temperature` 0, `seed` 42, `num_ctx` 4096 and the schema as `format`:
  `PinnedOllamaChat.chat`'s call, which waits up to 900 s, the client's own timeout. Then the
  digest is read again in `/api/tags` under the same timer, as `chat()` confirms it; a changed
  digest breaks the run. No retry, which would hide the cost. A reply the pinned client raises
  on breaks the run and is never an extraction's outcome: a body not JSON or not an object, or
  one with an `error` key (Ollama's error body, which has no message); a message not an object;
  content not a string, or empty; an HTTP 4xx; an HTTP 5xx or another transport error, which
  the product retries. Only content the client would return meets the acceptance rule.
- **The chunks:** `/Users/julia/RAG_new_external_s1/multihoprag/chunks.json.gz`, SHA-256
  `db25b882fc9fe6cd6e76101330ffc816a9081813268706a016a263171cf80300`, the second index
  generation's (built at `e5e135a`), which stage 2's retrieval read: tenant `ext_multihoprag`,
  609 articles, 11,231 chunks, documents by name and chunks in document order.

## The prompt and the schema

    Extract the key entities from the passage below: named people, organisations, places, products and events, and the specific terms the passage is about. Skip dates, numbers and generic words that would fit any passage. Write each entity in its base form, in the language of the passage; do not translate. Reply only with a JSON array of 3 to 12 strings.

    Passage:
    {chunk}

    JSON:

SHA-256 `b39de28359c8ea65ea416551121ba51cfc385d90c1a6a5561d6f5175aa8ccf57` (UTF-8, unfilled),
filled by `str.format`. English instructions with no domain word; names stay in the passage's
language. Its «3 to 12» is the product prompt's own count («3-12 сущностей», `EXTRACT_PROMPT`);
the schema and the acceptance rule take 0 to 12. It lives in the probe, which runs alone on the
standard library; past G2 it moves into `ingestion/entity_extraction.py` byte for byte, by this
SHA-256. **The schema** is the cache's `EXTRACT_SCHEMA`, unchanged (format SHA-256
`cd1768c67bdd9ceb5267c4d4632959a654baacb570d17532360234ca4afc7eca`): an array of at most 12
strings of 1–128 characters. It is the smallest the loader takes: `add_entity_graph` reads a list
of strings a chunk, keeps the entities of two documents or more and derives both edge kinds
itself, `mentions` and `co_occurs` (the entity pairs of a chunk); `EntityIndex` reads only those
two. No loader reads a type or an extracted relation, and generated tokens are the costly part.

## What is read

Per chunk, a row of `chunks.jsonl`: position (0 the warm-up, then 1–100), pick and index, the
SHA-256 and length of its text; `ok`, or `cap` for a cut chunk; the seconds of the request and
its digest check, and of the request alone, unrounded; Ollama's `total_duration`,
`load_duration`, `prompt_eval_count`, `prompt_eval_duration`, `eval_count`, `eval_duration` and
`done_reason` (a counter Ollama leaves out, as it omits empty ones, is null and reads as 0);
valid or the reason not; the output's SHA-256 and length; of a valid output its entities, their
distinct keys (the loader's normaliser without its two dictionaries) and the pairs of those
keys, the relations: `co_occurs` before the two-document floor. Then, outside the timer, what
else ran: the processes
`pgrep -f '[p]ytest|[_]supervisor|[r]eplay\.py|[s]tep[0-3]_|[l]imactl'` finds, as a count (never
a command line; null when pgrep fails), whether the CI lock is held, and whether `/api/ps` holds
this model alone, by digest; each check times out at 30 s. `launch.json` holds the frozen
values, the stand and the idle check; `end.json` the status, the reason or the stop, the load
with its seconds, `load_duration`, `size_vram` and `context_length`, the count of runners and
their `-np` and `-c`, the run's seconds, Ollama's models before and after the unload, and the
seconds from `keep_alive` 0 to the reply that showed the model gone (`unload_sec`).

## How it is read — frozen before the first request

- **The 100:** pick i is index i × 11,231 // 100 (0, 112, …, 11,118), evenly spaced from the
  first chunk, as GR-2's eight were. They run every tenth first (picks 0, 10, …, 90, then 1,
  11, …), so the chunks before each look span the list. The warm-up, the last chunk (11,230),
  pays the cold start and decides nothing.
- **Valid** is the cache's acceptance rule (`_entities`): the stripped output, a code fence
  allowed, is a JSON list of at most 12 strings of 1–128 characters once stripped; `[]` is
  valid; a cut chunk is not. A chunk's seconds are the client's wall time of its request and
  digest check, the product's call; the stops and G2 read them unrounded, their sum by
  `math.fsum`, and the interval is mean ± t(0.975, n − 1) · s / √n.
- **The sequential stop, as G2 failed;** a run passes only after all 100:
  1. after any chunk, more than 5 invalid: 95 valid is out of reach;
  2. after any chunk, the seconds so far above 100 × 86,400 / 11,231 = 769.3 s: the mean of the
     100 is over the line whatever follows — the whole-run cap;
  3. at the looks after chunks 10, 20, 40 and 70, 11,231 × the lower bound above 86,400 s.

  At one chunk 1 is named before 2, and 2 before 3. **G2 on the 100:** failed if 11,231 × the
  upper bound exceeds 86,400 s or fewer than 95 are valid; a bound exactly on the line passes.
- **Why these looks:** 1 and 2 are certain, so they cost no false stop. The test runs a seeded
  simulation, lognormal seconds unrounded, seed 20261028. At 0.9 × the line, CV 0.6, the lower
  bound stops at most 4 of 400 runs, and on the line at most 20 of 400 (0 and 12 when written);
  every run stopped in those two cases fails G2 on its 100 anyway. At 2.6 × the line, CV 0.3,
  all 200 runs stop at the first look. At 1.3 × the line, CV 0.6, the four looks end a run after
  fewer than 50 chunks on average (41.8), the look at 10 alone after more than 60 (70.4). False
  stops stay rare as the looks are few, the first at 10 (t = 2.262), and right-skewed seconds
  widen the interval just when a high draw lifts the mean.
- **`NOT_EVIDENCE`:** a broken run, or files that fail the gate: the launch's frozen values
  (model, digest, archive, options, prompt and format SHA-256, picks, order, caps), the stand
  (Ollama's version, the endpoint, the system and the machine) and the idle check; no model in
  Ollama before the run, this one alone at its end and none after the unload, shown gone by a
  reply within the unload's bound; every row field well formed, a row's request within its
  seconds and cut exactly when it reached 900 s, and each digest confirmed; an end with no
  reason that agrees with the rows by the rule, the stand (the runner's included), the caps and
  the seconds: the load and the rows are spans of the run, one after another on one clock, so
  their `math.fsum` is at most the run's seconds, which are below 3,000 s and at most its wall
  time; and no contended row, the warm-up's included, as a job seen after it may have run into
  the first chunk: a job's process counted or pgrep failed, the CI lock held, `/api/ps` failed
  or not this model alone, or a reload (`load_duration` over 1 s). A malformed field anywhere is
  a note, never an exception; the reading carries only fields it checked.
- **Printed, deciding nothing:** the hours a full extraction projects for MultiHop-RAG (11,231)
  and for ConditionalQA plus WixQA (51,349), at the mean and the upper bound; the seconds'
  spread and halves, tokens and rates, entity medians, the load, swap and load average.

**Forecast, written before the first request,** from the survey's rates with this prompt's
tokens: ≈ 80 that every request shares (the template and the instructions), which llama-server's
slot keeps from the request before (step 0: a request reuses the prefix it shares with the
slot's last state), and ≈ 210 new a chunk (a median 850 characters in
`reports/external/36f1167/connection.json`); 40–90 generated. Low 210/42 + 40/4.0 = 15.0 s; mid
210/33 + 65/3.0 = 28.0 s; high, nothing reused, 295/24 + 90/2.1 = 55.2 s; idle, at the known
4.3–4.7 tokens a second, 210/42 + 65/4.5 = 19.4 s. So **G2 fails at the first look**, the mean
2–7 × the line, with 10 of 10 valid (GR-2: 8 of 8 with the schema). At ≈ 20 s, ≈ 62 h for
MultiHop-RAG and ≈ 285 h for ConditionalQA and WixQA (high for those two: median chunks of 503
and 543 characters). GR-2's 11.4 s for a 7B is faster than these rates allow the 4B; the probe
settles it. The Mac ≈ 5 min (the load 31–51 s in step 1, the warm-up ≈ 25 s, ten chunks), 3–11
min across the cases; if ≈ 6 s holds, all 100 run (≈ 11 min) and G2 passes.

## Running it

On the Mac, `T=/Users/julia/RAG_new_stage7/entity-probe` and `PY` above. The run starts detached,
so ssh returns at once (`;`, never `&&`, before `nohup`).

1. **Tools:** `mkdir -p $T/runs`; from the laptop, `git -C D:/RAG_new show
   52dd160:reports/stage7/tools/entity_probe.py | ssh deproject-mac "cat >
   /Users/julia/RAG_new_stage7/entity-probe/entity_probe.py"`; on the Mac, `shasum -a 256
   $T/entity_probe.py /Users/julia/RAG_new_external_s1/multihoprag/chunks.json.gz` prints the
   probe's SHA-256 below and the archive's above.
2. **Idle,** step 0's rule: the 5-minute load below 2; `pgrep -f
   "[p]ytest|[l]lama-server|[_]supervisor|[r]eplay\.py|[s]tep[0-3]_|[l]imactl|[e]ntity_probe"`
   finds nothing; `/api/ps` is `{"models":[]}`; no `$HOME/ci_local/.lock_ci-local`; the product's
   service down, if one runs (PLAN stops it for stage 7: 8 GB, one measurement at a time). Else
   wait; nothing of others' is stopped. The probe applies the rule itself, all but the service,
   after the stand's own checks (the endpoint, the system, the machine, Ollama's version), and
   leaves its own process and its parent out of pgrep's count. It records what it read in
   `launch.json`, or refuses: exit 3, nothing written.
3. **The run:** `nohup $PY -I -u $T/entity_probe.py run $T/runs/e1 >> $T/runs/e1.log 2>&1
   </dev/null &`: a log line a chunk and a look, the last `PROBE_DONE <status>`; exit 0 complete
   or stopped, 3 refused (nothing written), 5 broken.
4. **The read:** `$PY -I $T/entity_probe.py read $T/e1.probe.json $T/runs/e1`.
5. **The record:** `$T/runs/e1/`'s three files, `$T/runs/e1.log` and `$T/e1.probe.json`, copied
   to the laptop as bytes into `reports/stage7/entity-probe/52dd160/`.

### Stops

- **A chunk that reaches 900 s** on the clock, `PinnedOllamaChat`'s timeout, is cut whatever
  came, by the socket's timeout or a reply read after it: invalid, its status `cap`, its
  measured seconds kept and no output or counters (the product would try it up to five times).
  Those seconds alone pass 769.3 s, so rule 2 stops the run as G2 failed, and the reading names
  the rule that fired, with two exceptions: a cut that is the sixth invalid is named by rule 1,
  and after the hundredth no rule runs, so the run is complete and G2 fails it on its seconds.
  A cut is unlikely. The
  schema's grammar allows one or two newlines and at most 20 spaces or tabs between tokens
  (`common/json-schema-to-grammar.cpp` in llama.cpp b10630, `d222767`, which Ollama pins), so
  12 strings of at most 128 plain characters stay near 1,600 characters, ≈ 400–800 tokens:
  ≈ 90–190 s at the idle 4.3–4.7 tokens a second, ≈ 380 s at 2.1, and the prompt. Nothing ends
  a runaway sooner: Ollama bounds `num_predict` −1 at ten contexts, 40,960 tokens
  (`boundedNumPredict()`, tested by `TestBoundedNumPredict` in `llm/llama_server_test.go`), and
  context shift is on for this model (`resolveContextShift` in `server/sched.go`).
- **Broken,** its reason in `end.json`: the load failed or reached 300 s (`load_failed`,
  `load_cap`); `/api/ps` failed after it, the model not loaded or the stand not the registered
  one (`ps_failed`, `not_loaded`, `stand`); the warm-up cut (`warmup_cap`); a reply the client
  raises on (`chat_transport`, `chat_http_4xx`, `chat_not_json`, `chat_not_object`,
  `chat_error`, `chat_no_message`, `chat_no_content`); a counter of the load's or a chunk's
  reply there but not an integer from 0 to 2⁶³ − 1, which could hide a reload (`counters`);
  `/api/tags` failed or the digest changed (`tags_failed`, `digest`); the run at 3,000 s from
  its start to the end of its last request (`run_cap`); an interrupt (`interrupted`). Every
  request is timed on the clock against its cap, as urllib's timeout bounds each socket
  operation, not the request: one that reaches its cap is a timeout whatever came, and a cap is
  reached at its value. The run's cap is read after the load and after every chunk, the last
  too. The worst honest run is the load 300 s, the warm-up 900 s, 769.3 s of chunks and one cut
  chunk of 900 s: 2,869.3 s, with the checks ≈ 2,870 s, under the run's cap. Any other request
  or check times out at 30 s.
- **The unload:** `keep_alive` 0, then `/api/ps` once a second until the model is gone, for at
  most 60 s, or 1,200 s after a cut chunk; the seconds from `keep_alive` 0 to the reply that
  shows it gone are `unload_sec`, and that reply must come within the bound. A closed
  connection cancels the generation: Go's
  request context ends Ollama's request to llama-server, whose `is_connection_closed` is the
  `should_stop` that `wait_for_all` polls about once a second (`tools/server/server-http.cpp`,
  `server-context.cpp` and `server-queue.cpp` at `d222767`), a cooperative stop with no hard
  bound; `keep_alive` 0 unloads once no request holds the runner (`expireRunner` and
  `processCompleted` in Ollama's `server/sched.go`). So after a cut the model normally goes
  within seconds; one still loaded at the bound, or shown gone only by a reply after it, makes
  the run `NOT_EVIDENCE`.
- **Run once more,** as `e1-r2` after the idle check: a broken run, a contended one, or one
  whose end found other models in Ollama or a model after the unload (the reader's notes). A
  second such run makes G2 `NOT_EVIDENCE`, published with the rows it has.
- **Any other failed gate** is a defect: a marked error fix (the change, its test, the new
  SHA-256, one commit), then a new run, as the run and its reader are one file.

## Records

`reports/stage7/entity-probe/52dd160/`: `launch.json`, `chunks.jsonl`, `end.json`, the log and
`e1.probe.json`: numbers, enums, ids, the model's name and digest, the paths named here and
SHA-256 strings, never a chunk's text, an output's text, a source name, a host name, a command
line or the filled prompt. The probe is no slice by the acceptance rule: it changes no
behaviour, case or quality number, and prices one. Its record gets a row in
[`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md) and a test that reads it again. The probe and its
test are committed with this spec, and the test checks each SHA-256 below; a later change is a
marked error fix that updates this list:

- `reports/stage7/tools/entity_probe.py` `68f7e828277cd459a338633801026d36355cce85d0769f5161207c1df01d0c7f`
- `tests/test_stage7_entity_probe.py` `bf3bfc3502cdb20a5ef7ee4ffb39dd5c189fded67d7cf9e87c7de0ffbc911e4b`

## A second opinion

Codex (profile cw, 2026-10-29) read this draft, the probe, its test and the product files they
follow, before registration ([`PLAN.md`](../../PLAN.md) §8.1). Its verdict: no-go until four of
its twelve findings were fixed.
- **Taken:** the product's 900-s cap, a cut that ends the run and an unload that waits for the
  model to go, as the draft's cut at 180 s could leave a generation running into the next chunk
  (finding 1); a reply the client raises on breaks the run, where it read as an empty output
  (2); the stand refused at the start and required by the gate, and contention read after each
  chunk (3); every row and end field checked, a complete end with no reason, no model after the
  unload (5); every cap read on the clock after its request, as urllib's timeout is a socket's
  and the run's cap was read before each chunk only (6); unrounded seconds, as rounded ones
  stopped a run exactly on the line at look 10 (7); the digest check under the request's timer,
  as in the product's `elapsed_s` (9); the header's estimate with its arithmetic, the simulation
  as the test runs it and the interval's coverage in [Not said](#not-said) (8, 10); «3 to 12»
  named as the product prompt's own count (11); a reading that carries only fields it checked
  (12).
- **Not taken:** finding 4, that the listed SHA-256 did not match the files. The package's copies
  had their home paths scrubbed, which changed their bytes; the repository's files matched the
  SHA-256 listed then.

Its second pass (2026-10-29) read the revised draft, probe and test: no-go until the first four
of its eight findings were fixed. All eight are taken: the slots read from the runner's `-np`
and `-c`, as `context_length` does not show them (1); the warm-up's row read for contention
too (2); every request timed on the clock against its cap, the 30-s checks included (3); the
seconds reconciled, a row's request within the row and the load and the rows within the run,
as the gate took seconds no run could have produced (4); the reply that shows the model gone
within the unload's bound (5); a counter there but malformed breaks the run, where it read as
no reload (6); a chunk cut at 900 s itself, and the cut's two exceptions to rule 2 named (7); a
test for each (8).

## Not said

- One corpus, English news, one stand and one day, on a Mac other projects share; the other two
  bases' hours decide nothing. The idle rule holds at the start, and after each chunk for what it
  reads: the processes pgrep's pattern names, the CI lock and Ollama's models. A job of another
  name, or another client of this model that does not reload it, passes unseen.
- The entities' quality: counts only. Whether E helps is its replay past G2, on M3.
- An ingestion in order also shares a document's header between its chunks (≈ 20–30 tokens),
  which spaced picks do not: the probe errs high, by an estimate of 20/42 to 30/24 s,
  ≈ 0.5–1.3 s a chunk at the survey's 24–42 prompt tokens a second.
- The interval is no nominal 95 % interval for the mean of all 11,231 chunks: the 100 are fixed
  systematic picks, and llama-server's caches change as the run goes.
- The runner's flags are read once, after the load; a runner started again later shows only as a
  reload in a row's `load_duration`.
- `size_vram` falls back to the model file's size when Ollama cannot account the buffers
  (`llm/llama_server.go`): a CPU stand may then read non-zero and break as `stand`, at the cost
  of the load alone.
- llama-server keeps each request's state in its host prompt cache, ≈ 50 MiB here (step 0: an
  answer's ≈ 2,300 tokens left 330–380 MiB): ≈ 5 GiB over all 100 on an 8-GB Mac, and its
  8,192-MiB limit in a full extraction, so later chunks may meet swap. The halves' means and the
  swap are printed, deciding nothing.
- `prompt_eval_count` may count only the tokens not reused; the rates printed are Ollama's.

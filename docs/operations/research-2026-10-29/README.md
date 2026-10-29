# Web research of 2026-10-29: five facts about Ollama 0.33.2 and its llama-server

This is a reading of the sources, not a measurement. Nothing here changes a published number of
this repository. One run by Codex (profile cw) answered [the brief](brief-ollama-facts.md); its
answer is [verbatim](codex-ollama-facts.md). Three decisions waited on it:

- the stage 7 cost probe's cap and stand checks
  (spec draft `docs/specs/stage7-entity-probe.md`, uncommitted);
- the host-cache cap of `PLAN.md` stage 4, item 5;
- the continuation of stage 4, step 2
  ([spec](../../specs/stage4-step2-self-eval-continuation.md)).

## In short

Ollama v0.33.2 serves GGML models through upstream llama-server. It pins llama.cpp b10630,
commit `d222767`.

1. **`/api/ps`.**
   - `context_length` is the runner's `NumCtx`, 4096 here. `OLLAMA_NUM_PARALLEL` defaults to 1.
   - `size_vram` is 0 when every buffer is on the CPU. When buffer sizes are not in the log, a
     fallback sets it to the model file's size, a false non-zero.
2. **A closed connection stops the generation.**
   - The path runs from Go's request context to llama-server's `is_connection_closed` check in a
     non-streaming wait. It is polled about once a second, and the stop is cooperative.
   - An abandoned request does not run on to its end.
3. **`keep_alive: 0` unloads once the model's requests have finished.** Its reply comes before
   the unload. `/api/ps` drops the model after the process exits.
4. **`LLAMA_ARG_CACHE_RAM=0` disables only the saved-state host cache.**
   - The setting is in MiB; −1 means no byte limit.
   - The slot's own prefix reuse stays: Ollama sends `cache_prompt: true` on both of its request
     paths.
   - A next turn that extends the previous prompt and answer reuses the matching token prefix.
     Re-tokenized answer text may diverge from the generated tokens (llama.cpp #16632), and the
     reuse stops where it does.
5. **The extraction schema bounds the output.**
   - The schema's grammar bounds whitespace.
   - Ollama clamps an open `num_predict` to 10 × the context, here 40,960 tokens.
   - Context shift is on by default for this model.
   - With 12 items of at most 128 characters, a reply stays near 1,600 characters.

**What the facts imply:**
- **The probe:** the 900-s cut is sound, and the `context_length` check is valid. A strict
  `size_vram` check can break a run falsely, at the cost of the load only.
- **The cache cap:** the cap at 0 keeps the continuation's reuse. It caps no other memory.
- **Step 2:** its saving depends on the matching token prefix, as its spec says.

## Checked by the session

These were checked against the raw sources at v0.33.2 and `d222767`, on the same day:

- `ContextLength()` returns `s.options.NumCtx`.
- `MemorySize()` falls back to `vram = total`, the file size, with the log line "llama-server
  buffer sizes not available, falling back to file size estimate".
- Both request paths set `cache_prompt` to true.
- `boundedNumPredict` returns `10 × numCtx` for a negative or larger value.
- `--cache-ram` reads "set the maximum cache size in MiB (… -1 - no limit, 0 - disable)", with
  the variable `LLAMA_ARG_CACHE_RAM`.

Not checked by the session: the cancellation path's details, the scheduler's unload order, the
grammar's whitespace rule and the template's tokenization.

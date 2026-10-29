# Research: five facts about Ollama 0.33.2 and its llama-server, from the sources

Answer in English. You may search the web and read source code online. Write no code for us and
no patches; give findings with primary sources. Keep the answer under ~1,800 words.

## Why

A small RAG system serves its answers from Ollama 0.33.2 on one Intel Mac (x86_64, macOS 13.7.8,
8 GB, CPU only), model Qwen3-4B-Instruct-2507 q4_K_M, `num_ctx` 4096, one request at a time.
Our reading of Ollama's sources on 2026-10-28 found that 0.33.2 runs upstream llama-server as its
runner and passes it its own environment (`os.Environ()`). Measured here: prompt evaluation
≈ 30–40 tokens/s, generation 4.3–4.7 tokens/s; llama-server's host prompt cache grew by
≈ 280 MiB a request (prompts ≈ 2,300 tokens) and restored no state over 15 requests (it restores
a state only if the new prompt keeps at least a quarter of it).

Three decisions wait on the answers:

- **A cost probe** times entity extraction (`/api/chat`, `stream: false`, a JSON-schema `format`,
  no `num_predict`) with a client-side per-request cap of 900 s. When the cap fires, the client
  closes the connection. If the generation keeps running, a later request is slowed. The probe
  also checks `/api/ps` after loading: `size_vram == 0` and `context_length == 4096`. If these
  fields mean something else, a clean run is rejected.
- **A memory policy** would cap the host prompt cache with `LLAMA_ARG_CACHE_RAM` in
  `ollama serve`'s environment, possibly at 0. This must not break slot-level prompt reuse.
- **A speed lever** asks for the self-evaluation as the next turn of the answer's chat, one
  `/api/chat` call with [user prompt, assistant answer verbatim, user evaluation request]. It
  saves time only if llama-server reuses the slot's KV for the shared prefix.

## Questions

Cite the Ollama sources at tag v0.33.2 (or the nearest tag that exists, and say which). Cite
the llama.cpp commit that this Ollama version builds or pins, by file and line or function. If
0.33.2 does not exist or does not run llama-server, say so first and answer for what it does
run.

1. **`/api/ps` fields.** What exactly is `context_length` for a model loaded with
   `options.num_ctx = 4096`? Is it the requested `num_ctx`, the per-slot context, or the total
   context (`num_ctx × parallel`)? What is Ollama's default `OLLAMA_NUM_PARALLEL` here, and does
   it change the reported value? Is `size_vram` 0 on an Intel Mac with no GPU offload, or can it
   be non-zero, e.g. Metal on an Intel Mac with an AMD GPU?
2. **Cancellation.** Suppose a client of `/api/chat` with `stream: false` closes the connection
   mid-generation. Does Ollama cancel the request's context and stop llama-server's generation
   for that slot? Trace the path: the Gin handler → the scheduler or runner client → llama-server's
   detection of a closed connection for a non-streaming completion. How soon does it stop, and
   is there a version where it does not stop?
3. **Unload while busy.** Suppose `/api/generate` with `{"model": M, "keep_alive": 0}` arrives
   while a request on M is still running (or was abandoned, as in 2). Does the scheduler wait for
   the reference count to reach zero and then unload? How long until `/api/ps` no longer lists M?
4. **`--cache-ram` / `LLAMA_ARG_CACHE_RAM`.**
   - What are its units and default, and what do 0 and −1 mean?
   - Does it limit only the host-memory prompt cache (saved slot states) or also the slot's own
     KV reuse (`cache_prompt`, `n_past` matching against the slot's current tokens)?
   - Does Ollama 0.33.2 send `cache_prompt: true` (or the equivalent) to llama-server?
   - Will a follow-up `/api/chat` whose rendered prompt extends the previous request's prompt
     and answer reuse the slot's KV for that prefix when nothing else ran between them?
   - Does the chat template's rendering of an assistant turn (for Qwen3-Instruct-2507: no
     `<think>` block) re-tokenize the answer identically to the generated tokens? Name a known
     cause of divergence.
5. **Unbounded output under a JSON-schema `format`.** With a grammar from a schema like
   `{"type":"array","items":{"type":"string","minLength":1,"maxLength":128},"maxItems":12}`, can
   llama-server's sampling run on without end, e.g. through whitespace, which JSON grammars often
   allow between tokens? Does Ollama 0.33.2 set a default `num_predict` (or another cap) when the
   client sets none? What happens when the context fills: context shift, stop, or error?

## Answer format

A numbered answer per question:

- the answer in one or two sentences;
- the evidence, with source links (file and line or function, tag or commit) and a short quote;
- confidence: high, medium or low;
- what you could not determine.

End with one line per decision above: what the facts imply for it.

# Codex (gpt-6-astra, xhigh, profile cw) — five facts about Ollama 0.33.2 and its llama-server

Its answer of 2026-10-29 to [the brief](brief-ollama-facts.md), verbatim; read-only, the brief alone in its package.

**Ollama v0.33.2 exists and does run upstream llama-server for GGML models.** Its [`LLAMA_CPP_VERSION`](https://github.com/ollama/ollama/blob/v0.33.2/LLAMA_CPP_VERSION) pins **b10630, commit [`d222767`](https://github.com/ggml-org/llama.cpp/releases/tag/b10630)**, fetched with Ollama compatibility patches by [`llama/server/CMakeLists.txt`](https://github.com/ollama/ollama/blob/v0.33.2/llama/server/CMakeLists.txt). [`NewLlamaServer`](https://github.com/ollama/ollama/blob/v0.33.2/llm/server.go) explicitly says: “All GGML models are served via the upstream llama-server subprocess.” All findings below concern those versions.

1. **`/api/ps` fields**

   **`context_length` is the runner’s configured per-request context: 4096 here. Default `OLLAMA_NUM_PARALLEL` is 1; increasing parallelism multiplies the context passed to llama-server but does not multiply this reported field.**

   Evidence: [`ContextLength()` and `startLlamaServer()`](https://github.com/ollama/ollama/blob/v0.33.2/llm/llama_server.go) respectively return `s.options.NumCtx` and launch with `-c NumCtx*numParallel`, `-np numParallel`. [`envconfig/config.go`, `NumParallel`](https://github.com/ollama/ollama/blob/v0.33.2/envconfig/config.go) specifies `Uint("OLLAMA_NUM_PARALLEL", 1)`. [`loadedModels()`](https://github.com/ollama/ollama/blob/v0.33.2/server/sched.go) obtains the runner’s context value for status reporting. This is configuration, not occupied-token count; Ollama can clamp a request exceeding the model’s training context.

   **`size_vram` normally is zero for genuinely CPU-only buffers, but Intel architecture does not guarantee zero.** [`MemorySize()` and `isGPUBuffer()`](https://github.com/ollama/ollama/blob/v0.33.2/llm/llama_server.go) derive it from runner buffer logs: CPU/BLAS/host buffers are excluded; Metal device buffers count. If buffer accounting is unavailable, the fallback sets VRAM to the **model file size**, potentially producing a false nonzero.

   Metal offload on a compatible Intel Mac with an AMD GPU can therefore produce nonzero VRAM. The [Darwin preset](https://github.com/ollama/ollama/blob/v0.33.2/llama/server/CMakePresets.json) enables Metal; pinned [`ggml_metal_device_init()`](https://github.com/ggml-org/llama.cpp/blob/d222767/ggml/src/ggml-metal/ggml-metal-device.m) selects the system Metal device and includes discrete-GPU support.

   **Confidence: high** for field semantics. **Undetermined:** compatibility and allocation behavior of your particular executable/GPU/driver; no local measurement was performed.

2. **Cancellation after disconnect**

   **Yes: an actual client disconnect propagates cancellation through Ollama to llama-server, including when `/api/chat` uses `stream:false`. Stopping is cooperative, without a hard latency guarantee.**

   The source path is:

   - Go’s [`Request.Context()` contract](https://pkg.go.dev/net/http#Request.Context) cancels incoming requests when the client connection closes. Ollama’s Gin [`ChatHandler` and `handleNativeChat`](https://github.com/ollama/ollama/blob/v0.33.2/server/routes.go) pass that context into scheduling and inference; the rendered path derives a child with `context.WithCancel(c.Request.Context())`.
   - [`Completion()` and `Chat()`](https://github.com/ollama/ollama/blob/v0.33.2/llm/llama_server.go) make context-bound HTTP requests to llama-server. **Both request internal streaming**; external `stream:false` merely makes Ollama accumulate the response.
   - llama-server’s [`server_http_context::post()`](https://github.com/ggml-org/llama.cpp/blob/d222767/tools/server/server-http.cpp) supplies `req.is_connection_closed` as `should_stop`. Even a **direct non-streaming** completion calls `rd.wait_for_all(req.should_stop)` in [`handle_completions_impl()`](https://github.com/ggml-org/llama.cpp/blob/d222767/tools/server/server-context.cpp).
   - [`server_response_reader`](https://github.com/ggml-org/llama.cpp/blob/d222767/tools/server/server-queue.h) calls `stop()` on destruction. [`stop()`](https://github.com/ggml-org/llama.cpp/blob/d222767/tools/server/server-queue.cpp) queues cancellation at the front; `process_single_task()` handles it by releasing the matching slot.

   Waiting HTTP readers check connection status on a **one-second polling interval**; streaming also detects closure through response handling. Queue scheduling and an ongoing CPU decode operation can add delay: one second is not a maximum time until computation stops.

   **Historical exception:** upstream commit **`c6d4cb46559b359d2682cf2a002e7fe01bb7a767`** had blocking non-streaming completion waits, documented in [issue #9273](https://github.com/ggml-org/llama.cpp/issues/9273). [PR #11285](https://github.com/ggml-org/llama.cpp/pull/11285), merged January 18, 2025, introduced periodic disconnect checks. That old direct-server behavior does not describe this pin.

   **Confidence: high** for cancellation wiring; **medium** for expected responsiveness. **Undetermined:** measured stop latency on your Mac and whether any intervening client/proxy actually closes its upstream connection.

3. **Unload while busy**

   **Yes: the empty-prompt `keep_alive:0` request schedules unloading after references reach zero. Its successful response does not mean unloading has already completed.**

   [`GenerateHandler`](https://github.com/ollama/ollama/blob/v0.33.2/server/routes.go) invokes `expireRunner()` and immediately returns `done_reason:"unload"`. In [`expireRunner()`, `useLoadedRunner()` and `processCompleted()`](https://github.com/ollama/ollama/blob/v0.33.2/server/sched.go), expiry sets `sessionDuration=0`; completion decrements the reference count and triggers expiry at zero. The code explicitly says: “We can't unload yet … as soon as the current request completes.”

   References follow **request-context lifetime**. Consequently, an abandoned request can lose its reference before llama-server has processed its cancellation. Unloading then calls [`stopProcess()`](https://github.com/ollama/ollama/blob/v0.33.2/llm/llama_server.go), which kills the subprocess and waits for exit.

   The scheduler removes the model from its loaded map **after process teardown**, before finishing its separate VRAM-recovery wait. A subsequent `/api/ps` snapshot should omit it. There is **no fixed disappearance deadline**: a still-connected active request can postpone unloading, and process/scheduler latency remains.

   **Confidence: high. Undetermined:** elapsed unload time on your machine. This assumes no subsequent request reloads the model or changes its retention policy.

4. **Host prompt cache versus live-slot reuse**

   **`LLAMA_ARG_CACHE_RAM=0` disables the saved-state host cache while preserving live-slot KV prefix reuse. A consecutive evaluation turn can reuse the retained matching token prefix, but reproducing the answer text does not guarantee identical answer-token IDs.**

   Evidence:

   - [`common/arg.cpp`, `--cache-ram`](https://github.com/ggml-org/llama.cpp/blob/d222767/common/arg.cpp) defines **MiB**, with “-1 - no limit, 0 - disable”; [`common_params::cache_ram_mib`](https://github.com/ggml-org/llama.cpp/blob/d222767/common/common.h) defaults to **8192 MiB**.
   - **Qualification for −1:** it removes the **byte limit**, not every eviction limit. [`server_prompt_cache`’s constructor](https://github.com/ggml-org/llama.cpp/blob/d222767/tools/server/server-task.h) retains a token limit, initialized from total context; [`server_prompt_cache::update()`](https://github.com/ggml-org/llama.cpp/blob/d222767/tools/server/server-task.cpp) still enforces it.
   - [`load_model()`, `init()` and `pre_decode()`](https://github.com/ggml-org/llama.cpp/blob/d222767/tools/server/server-context.cpp) separate the mechanisms: zero prevents creating the saved-state pool and disables idle-slot saving, while live reuse independently calculates `n_past` using `slot.prompt.tokens.get_common_prefix(input_tokens)` when `cache_prompt` is enabled. This setting does **not** cap model weights, live KV, or total RSS.
   - Ollama’s [`SetupLlamaServerCommandEnv()`, `Completion()` and `llamaServerChatRequest()`](https://github.com/ollama/ollama/blob/v0.33.2/llm/llama_server.go) inherit the environment and explicitly enable `cache_prompt` in both request paths.

   With one slot, no intervening request or unload, and no context truncation/shift that destroyed the prefix, an extending **token sequence** reuses retained KV. The host cache’s **25% retention threshold** belongs to [`server_prompt_cache::load()`](https://github.com/ggml-org/llama.cpp/blob/d222767/tools/server/server-task.cpp); it does not impose that threshold on ordinary live-slot prefix matching.

   The official [Qwen3-4B-Instruct-2507 template, revision `f50518e`](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/blob/f50518eb58dfc750271b273fc113bdfc16ec2280/tokenizer_config.json), inserts assistant content directly between ChatML delimiters, without a `<think>` block or content trimming. Nevertheless, generated tokens may use a different segmentation from deterministic re-tokenization of their concatenated text—a known cause of cache divergence acknowledged by llama.cpp’s maintainer in [#16632](https://github.com/ggml-org/llama.cpp/issues/16632). Reuse proceeds only through the matching prefix.

   **Confidence: high** for cache separation; **medium** for your expected reuse. **Undetermined:** your GGUF/Modelfile’s actual template and the resulting token-by-token match.

5. **Output bounds under the JSON schema**

   **For the exact bounded schema shown, the pinned converter does not permit endless whitespace. Moreover, Ollama v0.33.2 converts its otherwise open-ended default into a finite output budget: 40,960 generated tokens at context 4096.**

   [`common_schema_converter::visit()` and `SPACE_RULE`](https://github.com/ggml-org/llama.cpp/blob/d222767/common/json-schema-to-grammar.cpp) enforce `maxItems` and string-length bounds. Whitespace is bounded to empty, one space, or one/two newlines followed by at most twenty spaces/tabs: `"\n"{1,2} [ \t]{0,20}`. Thus this schema cannot sustain an infinite whitespace continuation. This conclusion concerns **schema-generated grammar**, not every JSON grammar or unbounded schema.

   [`DefaultOptions()`](https://github.com/ollama/ollama/blob/v0.33.2/api/types.go) starts with `NumPredict:-1`, but the runner’s `boundedNumPredict()` clamps negative or excessive values to **10 × context**. [`TestBoundedNumPredict`](https://github.com/ollama/ollama/blob/v0.33.2/llm/llama_server_test.go) explicitly tests “open ended gets finite budget.” A model-level configured limit may supply a smaller value.

   For this Qwen model, Ollama’s [`resolveContextShift()` / `supportsContextShift()`](https://github.com/ollama/ollama/blob/v0.33.2/server/sched.go) enable shifting by default. llama-server’s [`pre_decode()` and `process_token()`](https://github.com/ggml-org/llama.cpp/blob/d222767/tools/server/server-context.cpp) discard older context while preserving the kept prefix and continue generation. With shifting disabled, generation stops at capacity with a limit condition; oversized input is a separate validation/truncation case.

   **Confidence: high. Undetermined:** wall-clock completion time. Finite grammar and token budgets do not guarantee completion within 900 seconds.

**Cost probe:** Keep the 900-second disconnect cap; cancellation is supported but allow release latency. Checking context 4096 is valid; strict zero-VRAM rejection needs the accounting-fallback caveat.

**Memory policy:** `LLAMA_ARG_CACHE_RAM=0` is suitable for removing unused saved states while retaining same-slot prefix reuse; it is not a total-memory cap.

**Speed lever:** Consecutive evaluation can save prompt evaluation time; the saving depends on the retained matching token prefix and fitting the continuation within context.

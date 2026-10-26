# Evidence index

One row per slice. The capsule is the *record*; the *evidence* is the test or
the number it points at. A slice with no test and no published number is not
on this list.

**Evidence class** says what the claim rests on:

- `synthetic` — fixtures the project wrote for itself. Proves the mechanism
  works; proves nothing about the domain.
- `agent_labelled` — cases the agent labelled and no human has approved
  (ADR 0008's fallback for phase B). It is a proposal, not evidence.
- `real_labelled` — cases with labels over real air-cargo documents
  approved by a human; 100 carry this class since 2026-09-25 (T-54).
- `measured` — a number produced by a run that actually happened, with
  provenance (corpus SHA + code SHA + config).

## Rule for adding a row

New evidence is a test plus one row here. Not a new capsule file in the repo
root — that habit is what produced 29 of them and is now closed.

## Stage 2 retrieval baseline

| Slice | Evidence class | Record and verification |
|---|---|---|
| Stage 2, part 2: 415 retrieval questions complete; aircargo answer/context parity 100/100; sent-context gold coverage ConditionalQA 60/80, WixQA 68/100 (any gold article), MultiHop-RAG 10/70 | measured | [Capsule](docs/evidence/stage2-retrieval-baseline.md), [immutable record](reports/stage2/retrieval-20261021/), [derivation and provenance test](tests/test_stage2_retrieval_artifact.py). Stage 2 remains open; these are retrieval metrics, not external answer grades. |
| Stage 2, part 4: 300 external answers complete in 30 counted batches, no path break; all 300 in the question's language; answer/retrieval prompt parity 100/100 per base; routed to a person ConditionalQA 27, WixQA 24, MultiHop-RAG 33; median 266.9 s | measured | [Capsule](docs/evidence/stage2-external-answers.md), [immutable record](reports/stage2/external-answers-20261023/), [derivation and provenance test](tests/test_stage2_external_answers_artifact.py). Collection only: the registered judge is unavailable, so no answer-quality grade exists yet. |
| Stage 2, part 5: the four corpora judged on the chat path (100 answers each; judge `claude-opus-5-5`, M1 read without the reference; 7 of 8 plans stable on their retests). M1 good aircargo 69/100, ConditionalQA 31/100, WixQA 27/100, MultiHop-RAG 65/100; bad 14, 64, 63, 34. aircargo's good above ConditionalQA's and WixQA's (+38.0 and +42.0 pp, detected), not detected against MultiHop-RAG's. M2 with a reference: agrees ConditionalQA 43/80, WixQA 29/100. MultiHop-RAG's M2 is `NOT_EVIDENCE`: its plan failed the stability rule (13/15, κ 0.59) | measured | [Capsule](docs/evidence/stage2-record.md), [record](reports/stage2/5e308fe/stage2-record.json) built from the eight judge records beside it, [derivation and provenance test](tests/test_stage2_record_artifact.py). One model judges, no person (D11); one of MultiHop-RAG's 45 clusters holds 49 of its questions. |
| Stage 2b: the answer prompt V4 against V3, paired on stage 2's questions (300 answers on stand `4f48fed`, no path break; stage 2's judge, all 8 plans and bridges counted). **Adopted**: the bad share of WixQA and ConditionalQA pooled 127 → 108 of 200 (−9.5 pp, −15.7 to −3.1, falls), −10.6 pp on the 170 pairs of unchanged context. WixQA bad 63 → 51, good 27 → 40 (both detected); ConditionalQA bad 64 → 57, good 31 → 35, aircargo bad 14 → 17, good 69 → 63 (not detected). «[N]» and the referral to a specialist gone from the external bases' answers (42 → 0, 28 → 0) | measured | [Capsule](docs/evidence/answer-prompt-v4-record.md), [record](reports/answer-prompt-v4/4f48fed/v4-record.json) built by the tool registered in `4f48fed`, [derivation and provenance test](tests/test_answer_prompt_v4_record_artifact.py). In sample; one model judges and wrote V4, no person (D11, D12). Close to the line, not harm by the table: ConditionalQA declines 4 of its 20 not answerable questions against V3's 8. |
| Coverage beside quality: stage 2's V3 and stage 2b's V4 M1 records read again by published rules (the decline matrix, CRAG's score, coverage and quality among the answered), no model call, unpaired. Answered of 100: WixQA 67 → 73, ConditionalQA 81 → 91, aircargo 98 → 100, MultiHop-RAG 66 (V3). Good among the answered: 25/67 → 35/73, 27/81 → 32/91, 69/98 → 63/100. CRAG score −0.020 → 0.105, −0.195 → −0.150, 0.655 → 0.560, MultiHop-RAG 0.195. With an unsupported claim among the answered, V4: WixQA 29/73, ConditionalQA 50/91, aircargo 14/100. Declines where the documents held the answer, V4: WixQA 22 of 27, ConditionalQA 6 of 9 | measured | [Capsule](docs/evidence/coverage-metrics-record.md), [record](reports/coverage/coverage-record.json) built by the tool registered in `6310a44`, [derivation and provenance test](tests/test_coverage_record_artifact.py). One model judges, no person (D11); the base's gold from the M2 exports, amended before publication ([spec](docs/specs/coverage-metrics.md)). |

## Publication gate checks

- CI on `45a417a` (2026-10-03), run 37157492007: 11 of 11 jobs passed. `test-unit` on 3.11 and on 3.13: **4650 passed, 41 skipped**, coverage on 3.13 **78.89%** (gate 72%); `test-integration` on both legs: **93 passed, 1 skipped**. Pages run 37157492017 on the same commit: the `build` job passed (its steps include `Audit npm dependencies`, `Type-check docs site` and `Build`); the `deploy` job was skipped because the repository is private, so nothing is published. This is publication preparation, not a quality number.
- E.5 local checks, `c81de77`, rerun on `b0386e9` (2026-09-30 late: 3,722 unit + 36 e2e passed on the Mac, history scan 0 findings): [verification and secret-scan record](docs/evidence/e5-secret-scan.md).
  Mac unit suite: **3,763 passed, 16 skipped**, coverage **77.78%** (gate 72%);
  PostgreSQL integrations: **93 passed, 1 skipped**; admin browser regression:
  **1 passed**. Corpus SHA, exact test-tree hashes, commands and skip reasons
  are recorded there. The all-ref scan found no unallowlisted secrets.
  Follow-up on `813398c` plus the pinned planner fix: **9 Windows tests passed**
  after removing child-profile startup from the timeout, and **5 Mac tests passed**
  with `age` and the byte-identical pinned pool restored. Exact source/input
  hashes and commands are in the record. Docker follow-up on `536cd59` plus the
  pinned restore fixture correction: **11 Mac tests passed, 0 skipped**,
  including both previously unrun Docker scenarios. This is publication preparation.
  CI is the bullet above; public/deploy verification remains open.

## Slices

| Slice | Capsule | Evidence class |
|---|---|---|
| Stage 1 of [`PLAN.md`](PLAN.md) closed: the chat path made ready for any corpus and checked live on the four corpora, before and after the fixes (2026-10-18; one question per tenant — aircargo's first curated question and the first open one of ConditionalQA, WixQA and MultiHop-RAG — through `/api/ask/stream`, each tenant on a fresh API of a stand, Qwen3-4B-Instruct-2507 on the CPU of `deproject-mac` at the code defaults; the criteria registered in the spec before each run). Before the fixes (stand `99cd15f`, the first-generation indexes): WixQA's tenant ran on vectors alone after a restart — 20 vector and 0 BM25 candidates, the restore of its chunks refused by SQLite («too many SQL variables»); the English questions of ConditionalQA and MultiHop-RAG got Russian answers (494 and 331 Cyrillic letters against 1 and 49 Latin); every answer prompt labelled its documents «[Документ N» and opened them with «[Контекст:» headers. After the fixes, on the second generation of the four indexes (built at `e5e135a`): the first check (stand `0892441`, the V2 prompts) failed one criterion — MultiHop-RAG still answered in Russian, 347 Cyrillic letters against 65 Latin, under V2's instructions, themselves Russian; its rerun on V3 (stand `4ca5ddd`, the instructions in English) passed every criterion on every tenant: the hybrid path with 20 vector and 20 BM25 candidates, the rerank ok, 5 documents, the chunks restored after the restart (5,589 / 13,778 / 37,571 / 11,231); each answer in its question's script (aircargo 461 Cyrillic letters against 6 Latin, the three English answers without one Cyrillic letter); the labels `[N \| source=…]` and the header line `[document › section]` in every prompt, no «[Документ» or «[Контекст:», and no Cyrillic letter in the three external prompts. The four answers took 285–399 s. One question per tenant reads the path, not quality (stage 2): between the two checks after the fixes the model's self-score of the same questions moved — ConditionalQA 40 → 80, MultiHop-RAG 100 → 20 (routed `human`) | [records](reports/stage1/); [spec](docs/specs/stage1-fixes.md); `tests/test_stage1_live_artifact.py`; `tests/test_chat_chunk_context_e2e.py` (rule (a)); no capsule | measured |
| Julia's production model, Qwen3-4B-Instruct-2507, in the web chat on the production Mac, measured (2026-10-16 21:27 – 2026-10-17 01:48 UTC; code `19beeb1`, where the 4B is the code default and the suggested questions come from the answer's model, at the code defaults of `468224b` — the 3,600-s ceiling, the reranker on the CPU — with the stand environment's model choice dropped; Ollama 0.33.2 on the CPU of `deproject-mac`; the 5,589-chunk index; questions sent through `/api/ask/stream` as the web chat sends a conversation's first question, a fresh API per step, every question and its forecast named before the first launch in `cf25593`): one question, then five, then thirty. First token / result of the one question: 198 s / 281 s. Five: first token median 212 s (183–321 s), result median 322 s (267–413 s). The thirty stopped at question 16 on HTTP 401 — the test client's one access token had expired after 3,600 s; the 15 answers before the stop: first token median 117 s (103–290 s), result median 227 s (185–387 s). Rerun with a token per question, named before it in `25ed888` — the rerun, all 30: first token median 223 s (110–381 s), result median 320 s (196–476 s); its first 15 took median 291 s against 227 s in the stopped run, cause not established. All 51 answers routed `auto`, the model scoring 49 of them 100 and two 95, so the chat offered no handover; no ticket opened; the rerank succeeded on the CPU in 51 of 51, five documents each; after every run Ollama held the 4B alone. Per answer: retrieval median 134 s (39–304 s), the rerank median 102 s (25–209 s), reading the 2,270-token prompt 67 s, writing 4.2 tokens/s, self-eval 68 s, then the suggested questions, 13 s, before the result event. The forecast came close for the first question of a fresh API (281, 267, 200 and 284 s against 340 s) and held for the others (2 of 47 past 400 s, median 302 s). Memory bounds a long series: swap use grew 600–700 MB a question, to 10,971 MB in the stopped thirty and 12,274 MB in the rerun (about 0.9 GB at each start), and one audit write timed out; the model runner, llama-server, reached an 11-GB footprint while Ollama sized the model at 3.2 GB, and alone, with no API, it grew about 312 MB a request over eight of the rerun's prompts — why is not established. Retrieval was hybrid: every run's tenant `aircargo` restored BM25 at its first question; the run's BM25 warning names the startup tenant `default` | [record](reports/chat-live-4b/19beeb1/); `tests/test_chat_live_4b_artifact.py`; no capsule | measured |
| The chat's suggested questions come from the answer's model (2026-10-16; `19beeb1`): the stream wrote the answer and the self-evaluation with the provider profile's model but asked `OLLAMA_MODEL_NAME` for the suggested questions, so a deployment pinning another model loaded it beside the answer's after every answer — the first live series of the 4B, on a stand whose environment pins `qwen2.5:7b`, loaded the 7B (about 4.7 GB) after each 4B answer on the 8-GB Mac, and is not published. They follow the answer's model now, as the self-evaluation does. The test pins `OLLAMA_MODEL_NAME=qwen2.5:7b` on a real `Settings()` and reads the requests a fake Ollama receives: the stream's three calls ask the 4B. Red on `da134d4` (the third call asked `qwen2.5:7b`), green after; the 114 tests that touch the stream's suggestions pass on the Mac. | `tests/test_production_model_default_e2e.py`; no capsule | synthetic |
| How often the web chat would hand Julia's production model's answers to a person, measured (2026-10-16, 19:12–20:12 UTC; code `7a99c45`, where Qwen3-4B-Instruct-2507 is the code default; plan, forecast, stop rule and reading named before the first request in `da134d4`): the chat routes an answer `auto` when the model's own score of it is 80 or more and `human` below. That self-evaluation — the repository's `build_self_eval_prompt` over contexts fitted by `fit_context_docs` for the role `evaluate`, through the provider runtime a clean `Settings()` builds, `_parse_int_score` — was sent for each of the 100 answers the 4B wrote in the generator screening (seed 42, the phase-C contexts `91ce1745…`, dataset `3737d694…`), which the judge had graded 67 good, 21 partial_ok, 12 bad. Result: `human` 2 of 100 (95 % Wilson 0.6–7.0 %); the model scored its own answer 100 in 89 cases, 95 in 7, 90 in 2, 60 and 20 once each; every reply a number, 0 errors, a median 35 s a case (max 68 s, no stop). The two sent to a person are both declines where the context held the answer; 10 of the judge's 12 bad answers and all 21 partial ones go `auto`, and no good answer is sent to a person. So on this model the chat's own rule is precise but nearly blind: an operator would see about one answer in fifty, while the judge finds one in eight bad. An estimate of the rule, not a chat run: the answers come from the screening's prompt and the contexts from the phase-C harness, not from the chat's retrieval; the test set, not customer traffic; not the widget's rule — `/api/ask` routes by the graph's node (relevance, grounding, retries) and opens a ticket on `human` itself, unmeasured on the 4B. No threshold or rule changed. | [record](reports/chat-route-replay/7a99c45/); `tests/test_chat_route_replay_artifact.py`; no capsule | measured |
| Julia's production model is the code default (2026-10-16; `7a99c45`): she took Qwen3-4B-Instruct-2507 that day («Согласна с тобой»), and every default named `qwen2.5:7b` — `OLLAMA_MODEL_NAME` in `config/settings.py`, the Ollama provider's default models, the `local-first` profile and the GraceKelly profile's local fallback in `config/providers.yml`, `.env.example`, docker-compose's pull, the Helm values and the quickstarts. They name `qwen3:4b-instruct-2507-q4_K_M` now, listed in `providers.yml` (the runtime refuses an unlisted model); `qwen2.5:7b` stays listed with its benchmark aliases, and the scripts that pin it with its digest for the quality thread are unchanged. The test drives the real path on a real `Settings()` with no model, profile or registry in the environment, to a fake Ollama that records each request: the chat's stream (the answer, the self-evaluation, the suggested questions) and `/api/ask` (every graph node through the provider runtime) ask for the 4B and no other. Red on `26fcb4a` (3 failed: `qwen2.5:7b`), green after; the whole unit suite on the Mac 5,809 passed, 123 skipped. | `tests/test_production_model_default_e2e.py`; no capsule | synthetic |
| qwen3:1.7b in the web chat on the production Mac, measured (2026-10-16, 00:26–01:28 UTC; code `9e1fc9e`, thinking off since `c2739af`, at the code defaults of `468224b` — the 3,600-s ceiling, the reranker on the CPU — with no other setting changed but the model; Ollama 0.33.2 on the CPU of `deproject-mac`; the 5,589-chunk index; questions sent through `/api/ask/stream` as the web chat sends them, a fresh API per step, every question and its forecast named before the first launch): one question, then five, then thirty. First token / result of the one question: 142 s / 185 s. Five: first token median 166 s (134–254 s), result median 211 s (177–301 s). Thirty: Julia's stop rule ended them at question 9 with no first token at 360 s, 3× its forecast — its vector search alone took 147 s, as swap use had grown to 4,117 MB (764 MB at the run's start) and the API and the model were paged out; the eight answers before it: first token median 164 s (89–306 s), result median 200 s (139–352 s). All 14 answers routed `auto`, no ticket opened; the rerank succeeded on the CPU in 14 of 14, five documents each. Per answer: retrieval median 129 s (61–276 s), the rerank median 120 s (61–271 s), reading the 2,264-token prompt 28 s, writing 9.2 tokens/s, self-eval 29 s. The forecast, taken from qwen2.5:1.5b's times on 2026-10-14, came close for the first question of a fresh API (185, 177 and 163 s against 180 s) and missed every other (11 of 11 past 120 s, median 215 s). Every run's API logged a retriever built without the BM25 index — the tenant `default`'s, built at startup, which no question uses: the questions' tenant, `aircargo`, restored its 5,589 chunks with BM25 and parent expansion at the first question, in this record and both earlier ones (their API logs on the Mac), so retrieval was hybrid; corrected 2026-10-16, when this row said vector-only | [record](reports/chat-live-qwen3/9e1fc9e/); `tests/test_chat_live_qwen3_artifact.py`; no capsule | measured |
| The embeddable widget says that an answer did not come and offers the operator (2026-10-15; `4977582`): on `/api/ask`'s wall-time limit (HTTP 504) the widget said «Не удалось подключиться к сервису…», which was untrue, and on the graph's own deadline it showed the apology routed `timeout` with nothing to do — and `/api/ask` opens no ticket on a timeout. Now both say the answer did not come in time with «Повторить» and «Передать оператору», and any other failure says it did not come; the button sends `/api/escalate` the question with the reason `route=timeout` / `route=error` and the widget's session, and fetches a new widget token once when the old one expired. The test drives Chromium on `/static/widget.html` against a live server whose `/api/ask` runs its real path to a fake Ollama: under an 8-s request limit and a model silent for 60 s the 504 comes with both buttons and no ticket; under an 8-s ask budget the apology routed `timeout` does; an injected 500 offers both, the retry gets the answer, and the operator's call survives an injected 401. Red on `30e97bd` (3 failed: no button), green 3/3 with `-rs`, no skip | `tests/test_widget_operator_offer_playwright.py` (rule (a), 3); no capsule | synthetic |
| Thinking off on every model call of the chat (2026-10-15; `c2739af`): the provider's bindings (`OllamaLLM`, `ChatOllama`) get `reasoning=False` wherever the class declares the field, so the answer, the self-evaluation, the suggested questions (the graph's own model) and the tool calls send `think: false`, and the raw stream fallback puts it into its payload; a binding without the field gets nothing new. The test drives `/api/ask/stream` on a real `Settings()` through the real path to a fake Ollama and reads the three payloads it receives — the answer, the self-evaluation, the suggestions: `think` is `false` in each (`null` in each on `8464732`, where the raw fallback and both bindings also sent nothing). Why: on this path qwen3:1.7b thought for 130–155 tokens before a one-sentence answer (`think_probe.out`). Ollama 0.33.2 on the Mac, probed the same day (behaviour only, the Mac shared): `think: false` to qwen2.5:7b, which cannot think, gives HTTP 200 and the same 20-token answer as no field; `think: true` gives 400 «does not support thinking»; qwen3:1.7b with `think: false` returns no thinking and 21 tokens, through the raw API, `OllamaLLM` and `ChatOllama` of langchain-ollama 1.1.0 alike | `tests/test_ask_stream_thinking_off_e2e.py` (rule (a), 3); `reports/think-probe/2026-10-15/think_false_probe.{py,out}`; no capsule | synthetic |
| The web chat offers the operator on a timeout and on `human` (2026-10-15; `056844d`): the answer routed `timeout` — the server's apology — and a stream `error` event routed `timeout` or `error` show «Повторить» and «Передать оператору» without hover; an answer routed `human` shows «Передать оператору» and opens no ticket by itself; the button opens the chat's operator dialog and sends `/api/escalate` the question with the reason `route=timeout`, `route=human` or `route=error`, as `/api/ask` names its tickets. Chromium on the Mac drives `/static/chat.html` against a live uvicorn whose stream runs its real path — a real `ConversationSession`, the provider runtime, langchain-ollama and the ollama client — to a fake Ollama: under an 8-s `REQUEST_TIMEOUT_SEC` the test sets and a model silent for 60 s, the apology routed `timeout` comes in 10–11 s with both buttons and the ticket goes out only on the click; an answer the model scores 40 comes routed `human` with the button; the `error` events are put into the stream as the server writes them, which it does only on the graph-parity path or before retrieval. On `147db65` no message had the button (4 failed). Python Playwright 1.63.0 from a separate folder on the Mac, run with `-rs`, no skip; CI has no Playwright and skips it, as the widget's browser test. The widget calls `/api/ask` and has no operator: on that route's 504 it says «Не удалось подключиться к сервису…» — left for Julia | `tests/test_chat_operator_offer_playwright.py` (rule (a), 2); `tests/_fake_ollama.py`; no capsule | synthetic |
| Time limits lifted to a ceiling, the reranker on the CPU by default (2026-10-15; `468224b`): with none of them in the environment, `REQUEST_TIMEOUT_SEC`, `OLLAMA_REQUEST_TIMEOUT_SEC` and `STREAMING_TIMEOUT_SEC` are 3,600 s — Julia's ceiling, not an SLO — and so are the fallbacks for a settings object without them and the raw Ollama stream's limit, before a hard-coded 120 s; `RAG_DEVICE` is `cpu`. The test drives `/api/ask/stream` on a real `Settings()` through the real provider runtime, langchain-ollama and the ollama client to a fake Ollama server that is silent for 65 s, then streams 17 tokens until 129 s: the whole answer arrives with route `auto`, the self-evaluation's 85 and the suggested questions, from one answer request, in 129.3 s on the Mac; on `f4818eb` it ended after 30.2 s on an `httpx.ReadTimeout` with route `timeout` and the apology, as the web chat did on 2026-10-14. The device check: MPS reported available and `RAG_DEVICE` unset, the embedder and the reranker load on `cpu` (`mps` on `f4818eb`). Real time, no fake clock, in the regular suite | `tests/test_ask_stream_time_limits_e2e.py` (rule (a), 1); `tests/test_base_manager.py::test_default_device_is_cpu_where_mps_is_available`; no capsule | synthetic |
| Session refusals on the stream routes come before the first byte (2026-10-15; `54ffdb2`): `/api/ask/stream` and `/api/chat/stream` resolve the session before the response starts, so a 404 (a session of another tenant) or a 503 (the session store in cooldown, the caller's id unverified) reaches the client as the plain JSON error `/api/ask` returns, which the web chat already handles — before, the route sent its `status` event first, the refusal found the response started, and the client got a 200 stream that ended after `status` with neither `error` nor `result` (on the Mac on 2026-10-14, the row of the web chat with generators below 7B). The test was red on `928c124`, 4 of 4 — a 200 stream of one `status` event — and green with the fix; no status semantics added, the direct-stream path kept (ROADMAP, Frozen) | `tests/test_ask_stream_session_refusal.py` (rule (a), 4); no capsule | synthetic |
| Generators below 7B against C.1a and C.1b, the judge on all 100 cases, measured (2026-10-15; registered before its first request at `30b1469`, which gives `scripts/generator_answer_judge.py` its sample size and its reuse step, amended at `5861ffb`; the seed-42 answers of the screening's reports and of C.1a / C.1b, the same files; dataset `3737d694…`, contexts `91ce1745…`; the one judge, claude-opus-5-5 at effort max, blind to the generator): good/partial_ok/bad and the 95 % Wilson interval of the good share — `qwen3-1.7b` 50/27/23 (0.40–0.60), `qwen3-4b-instruct` 67/21/12 (0.57–0.75) against `qwen2.5-7b` 56/29/15 (0.46–0.65, C.1a) and `qwen3-8b` 66/29/5 (0.56–0.75, C.1b); supported claims 0.92 / 0.95 against 0.96 / 0.98, an unsupported claim in 17 / 11 against 12 / 3 answers. Pairs, the cases where only the first / only the second is good and the exact sign test on them: `qwen3-1.7b`–`qwen3-4b-instruct` 4/21, p 0.001; `qwen3-1.7b`–`qwen2.5-7b` 13/19, p 0.377; `qwen3-1.7b`–`qwen3-8b` 3/19, p 0.001; `qwen3-4b-instruct`–`qwen2.5-7b` 17/6, p 0.035; `qwen3-4b-instruct`–`qwen3-8b` 7/6, p 1.000; `qwen2.5-7b`–`qwen3-8b` 5/15, p 0.041 — apart below 0.05 / 6 only the first and the third: `qwen3-1.7b` is behind `qwen3-4b-instruct` and `qwen3-8b` and not told apart from `qwen2.5-7b`, and `qwen3-4b-instruct` and `qwen3-8b` are not told apart; the judge gave the same class on 14 of 15 retests, the same `context_has_answer` for all four answers in 100 of 100 cases. 292 requests sent ($30.95, 218 min of requests, median 33 s, longest 244 s), 123 verdicts reused from the 30-case record (the 120 answers on its cases and 3 retests both plans drew). The route refused the 70th request twice when a plugin of the CLI's user configuration loaded into its `--safe-mode` session; from then on each request disabled the two plugins that configuration held (the amendment). Descriptive, no ship decision; the production model is Julia's and stays suspended | [record](reports/generator-screen/86df582/judge-100/); [plan](docs/specs/small-generator-screening.md#extension-to-100-cases-registered-2026-10-15); `tests/test_generator_screen_artifact.py`; no capsule | measured |
| Generators below 7B screened for the production Mac (2026-10-14, the judge finished 2026-10-15; code `86df582`, amendment `cfb78ee`; Ollama 0.33.2 on the CPU of `deproject-mac`; the C.1 contract — the benchmark's prompt over cached arm-C retrieval, not the chat path — one run at seed 42 without self-grading, 100 answers each, none failed): the one judge (claude-opus-5-5, effort max, blind to the generator) on 30 shared cases, good/partial_ok/bad `qwen2.5-1.5b` 16/5/9, `qwen3-1.7b` 20/5/5, `qwen3-4b-instruct` 23/5/2 against `qwen2.5-7b` 20/6/4 (C.1a) and `qwen3-8b` 21/8/1 (C.1b); supported claims 0.86 / 0.92 / 0.99 against 0.95 / 0.99; the same class on 15 of 15 retests, the same `context_has_answer` for all five answers in 30 of 30 cases. Thirty cases leave gaps of five good answers or fewer unresolved, and the only wider one, `qwen2.5-1.5b` against `qwen3-4b-instruct` (16 vs 23), is not settled either: 1 against 8 discordant cases, exact p ≈ 0.04 before correcting for ten pairs; the leading small generator is within five of C.1a and C.1b, so the plan's reading extends the judge to all 100 cases of the generators concerned under a new plan, measured on 2026-10-15 (the row above). The deterministic checks of all 100 answers: keyword recall of the answers 0.645 / 0.575 / 0.730 for `qwen2.5-1.5b` / `qwen3-1.7b` / `qwen3-4b-instruct` against 0.705 / 0.705 for C.1a / C.1b (the contexts hold 0.905); NLI faithfulness, not ranked on, 0.870 / 0.907 / 0.919 against 0.892 / 0.991; generation median 13.9 / 15.8 / 36.7 s a case (reading 126 / 109 / 45 tokens/s, writing 20.4 / 14.0 / 6.7). The tag `qwen3:4b` proved to be Qwen3-4B-Thinking-2507: it wrote its reasoning as the answer, 6 of 6 at the 384-token cap, and was replaced before its 100-case step. Descriptive, no ship decision; the production model is Julia's and stays suspended | [record](reports/generator-screen/86df582/); [plan](docs/specs/small-generator-screening.md); `tests/test_generator_screen_artifact.py`; no capsule | measured |
| Web chat on the production Mac with generators below 7B, measured (2026-10-14; the stand of the qwen2.5:7b record at code `33d4b42` serving qwen2.5:1.5b, then Qwen3-4B-Instruct-2507, on Ollama 0.33.2 on the CPU of `deproject-mac`; the 5,589-chunk index; questions sent through `/api/ask/stream` as the web chat sends them): under the code-default limits neither model answers — qwen2.5:1.5b: warm-up timeout after 58 s, then route `timeout` without a token; Qwen3-4B: warm-up timeout after 231 s, the reranker blocking on the GPU for 3 min 33 s until MPS out of memory, then the question's stream closed after its `status` event with neither result nor error: the API raised 503 «Session store temporarily unavailable» inside the started stream. With the limits raised to 1800 s only to measure, and `RAG_DEVICE=cpu`, on five questions: qwen2.5:1.5b first token median 77 s (64–143 s), result median 100 s (92–168 s) — retrieval 53 s (the rerank 49 s), reading the 2,258-token prompt 22 s, writing 17.7 tokens/s, self-eval 24 s; 4 of its five answers routed `human`, and one is the bare reference «[4]», routed `auto`. Qwen3-4B first token median 198 s (175–224 s), result median 297 s (258–322 s) — retrieval 137 s (the rerank 129 s), reading the 2,258-token prompt 63 s, writing 4.3 tokens/s, self-eval 68 s; all five routed `auto`, each with a reference. The first token / result of the one question right after the start: qwen2.5:1.5b 147 s / 170 s, Qwen3-4B 258 s / 343 s. The rerank slows as the model takes memory: 27.3 s with no model loaded, 142 s beside the 7B (first token 325 s, result 486 s). qwen3:1.7b is not timed: the API sends Ollama `think: null`, and through the provider's class it wrote 411 characters of reasoning, 130 output tokens for a one-sentence answer | [record](reports/chat-live-small/33d4b42/); `tests/test_chat_live_small_artifact.py`; no capsule | measured |
| Web chat on the production Mac, measured (2026-10-14; code `33d4b42`, qwen2.5:7b on Ollama 0.33.2 on the CPU of `deproject-mac` — i5-7500, 4 cores, 8 GB; the 5,589-chunk index; questions sent through `/api/ask/stream` as the web chat sends them): under the code-default limits the chat gives no answer — route `timeout`, not one token — because retrieval alone took 25.4 s of the 30 s, its reranker failing on the 4 GB GPU with MPS out of memory. With the limits raised to 1800 s only to measure, and `RAG_DEVICE=cpu`, five questions were answered: first token median 325 s (285–423 s), result median 486 s (429–614 s); per question retrieval 214 s, reading the 2,258-token prompt 115 s, writing 4.0 tokens/s, self-eval 122 s. The model, the embedder and the reranker do not fit 8 GB together: retrieval alone, with no model loaded, median 27.6 s (22–38 s) on the CPU, the rerank 27.3 s of it and the vector search 0.2 s, so in the chat it was slowed 8× by swapping; on the GPU the reranker fails with MPS out of memory at its default batch even alone; at batch 4 it works, but retrieval takes median 57.1 s (48–64 s), 2.1× the CPU, at batch 1 median 92.6 s (85–101 s), and with the embedder also on the GPU at batch 4 median 55.8 s (48–71 s). Under the code-default `RAG_DEVICE=auto` both models go to the GPU and every rerank fails, so the chat answers from the unreranked order | [Record](reports/chat-live/33d4b42/runs.json) and [the tools that made it](reports/chat-live/33d4b42/tools/); [session log](archive/docs/operations/session-handoff-2026-10-14-chat-on-mac.md); `tests/test_chat_live_artifact.py`; no capsule | measured |
| Chat and graph prompts fit the local model's window, counted in tokens (2026-10-14; `2758be5`, `33d4b42`, with `cefd7c3`, `0dfd159`, `f355c31`): the web chat's stream prompt and the graph's grade, generate, verify and evaluate prompts are fitted to the Ollama window by token estimates, each context document keeping its share, and the provider refuses a prompt above the window before any client is made — before, such a prompt reached Ollama, which truncates it silently (a 2026-10-13 run sent 4,369 tokens into a 4,096-token window); the Ollama transport and the reranker's batches stop at the request deadline; graph escalations are written on the API's event loop. Each fix was red on its parent — on `2758be5` the end-to-end test saw `/api/ask` prompts of 5,021–5,453 tokens against window limits of 2,636–3,443 — and green on the Mac: on `33d4b42` 943 passed, 2 skipped in 78 files; the live record in the row above keeps every prompt inside the window | `tests/test_ask_window_e2e.py` (rule (a): `/api/ask` through the real graph and Ollama provider over a recording client), `tests/test_graph_window_fit.py`, `tests/test_window_tokens.py`, `tests/test_chat_stream_window.py`, `tests/test_context_window_fit.py`, `tests/test_ollama_request_deadline.py`, `tests/test_ollama_transport_timeout.py`, `tests/test_reranker_deadline.py`, `tests/test_escalation_loop_bridge.py`; no capsule | synthetic |
| Q 1.6 external variance pilot: 50 ConditionalQA / 40 WixQA pairs, none lost; primary variances 0.020 / 0.025, registered floor 0.10 unchanged; step 1 fits 165 or 145 ConditionalQA pages plus 200 WixQA questions in 37.33 / 33.29 hours, MDE 0.069 / 0.074 / 0.091; preparation, no mechanism verdict; revision eleven still pending | [Capsule](docs/evidence/external-bases-pilot.md); [aggregates and sizes](reports/external/64a72e5/pilot/); [Sol 6.1 xhigh review](archive/docs/audits/audit_sol_07_10_26_external_pilot.md); `tests/test_external_pilot_artifact.py`, `tests/test_external_pilot.py` | measured, preparation; no verdict |
| Q 1.5 / 1.5c / 1.5d external bases connected: ConditionalQA, WixQA and MultiHop-RAG, 7,482 documents / 62,580 chunks in separate collections at `36f1167`; all visible text and evidence preserved, 6 MultiHop-RAG groups split across two chunks; corpus, T-65 index and embedding checkpoint unchanged; 9.8 Mac-hours with foreign load, not speed evidence; preparation, no retrieval-quality number | [Capsule](docs/evidence/external-bases-connection.md); [artifact](reports/external/36f1167/connection.json); `tests/test_external_connection_artifact.py`, `tests/test_external_bases.py` | measured |
| Q 0.1b request-context isolation (T-71): the shared request executor runs every callable in a context of its own, so a stream request no longer leaves its deadline and LLM budget on a pooled worker thread; a sync `/api/ask` served by that thread answers and its Evidence is readable, where it used to return an HTTP 200 timeout apology with no trace; this was the cause of the flaky `trace not found` failures on the Python 3.13 CI leg (runs 37093493571 to 37137697604) | `tests/test_request_context_isolation.py`; [requirements](docs/specs/request-context-isolation.md); rule (a), no capsule | synthetic |
| Q 2.4 harness/API parity (T-62): H 100 + Hm 15 in hybrid/graph lanes; pinned chunks, shared exact-cosine store, fake models; pool/reranked order, graded generation context hash and query transform; HTTP contracts through production harness; archived phase-C/GR/P1/P1b require `--legacy-harness`; real Chroma/exact 30-case comparison: next row | `tests/test_harness_api_parity.py`; preparation only, no quality measurement or capsule | synthetic |
| Q 2.4 real-model production parity: 30 H cases at c729b23; 60 session replay matches; Chroma/exact vector and pool divergences in 8 cases, reranked list and sent context in 1; no latency or quality verdict | [capsule](docs/evidence/production-parity-30-cases.md); [report](reports/parity/c729b23/report.json); `tests/test_production_parity_artifact.py` | measured |
| Q 2.3 embedder manifest (T-61): collection metadata binds model/revision/dimension/prompts/normalization; `/api/ask` exposes match in trace and Evidence, refuses mismatch with traced 503, isolates tenants and preserves startup refusal; unverified revisions are NOT_EVIDENCE; KB publish refuses mismatch with traced 409 | `tests/test_ask_embedder_manifest.py`, `tests/test_embedder_manifest.py`; rule (a), no capsule | synthetic |
| Q 1.3a pilot dev drafts (T-64): 30 cases, quotas 10/10/4/6, styles 15/15, derived RU→EN 10, 38 source spans; specificity-filtered frame 982 sections; 84 draft topic families (57 singletons), 19 pilot case–family components; H/Hm use 42 families, pilot adds 7; reserve 35 families / 36 documents, skewed toward HR/legal templates, no claims/customs/dangerous goods; 105 cross_ref links, 25 linked reserve families, 10 unlinked HR families / 10 documents; F-T-64-2/3/4 repaired: numeric self-coverage, atomic claim + source_quote, 30 minimal reference answers; 0 approved, preparation only | [Drafts and limits](docs/evidence/devset-pilot-drafts.md); [cases](evaluation/devset_pilot.jsonl); [manifest](evaluation/devset_pilot.manifest.json); [families](evaluation/document_families.json); `tests/test_devset_pilot.py` | agent_labelled, unapproved |
| Q 1.3b label verification of the pilot drafts (T-78): one verifier, Claude Opus 5.5 in stateless requests — new sessions that also carried the owner's instruction file and hook output (correction of 2026-10-05, by a probe of the route) — rubric `label-verification/v2` (plan D12: no model of another vendor, D11: no person); first check 25 confirmed and 5 rejected of 30 — single-doc 4 of 10, multi-doc 1 of 10, every rejection on severity (5c) or critical facts (5d), whose definitions postdate the drafts; five repairs by the session agent change severity and critical facts only and were all confirmed in round 2 by the same model — a consistency check, counted apart; 30 verified, 0 dropped, 0 `authority_unverified`, 8 severity differences published; status single_model_verified, origin stays agent_labelled; a one-model check leaves that model's systematic errors unseen; preparation only, rule (b) not met | [Check, repairs and limits](docs/evidence/devset-pilot-label-verification.md); [verified set](evaluation/devset_pilot_verified.jsonl); [register](evaluation/devset_pilot_label_checks.json); [repairs](reports/devset/label-verification/repairs.jsonl); `tests/test_devset_label_checks_artifact.py` | agent_labelled, single_model_verified |
| Q 1.3c variance pilot of the gold metrics on the production path: three arms — the registered control, `pool30` and `sent3` — over the 24 verified pilot cases with gold evidence at `768a195`, 24 of 24 in each, graph off, nothing generated or judged; no verdict — the perturbations are not mechanism candidates; each moved 2 of 24 pairs on a metric of the sent context; variances 0.0000–0.0870, all below the grid 0.10, so all 22 rows of the registered MDE stay at the grid: 0.171–0.303 in development (60 cases, 37 clusters), 0.224–0.287 in the holdout (64, 18); no non-inferiority check reaches power 0.8 at a true zero (0.02–0.05); bound of the index: 37 of 38 gold spans held whole by one chunk, one by none; the production filter gave another verdict on the same question and document in 9 of 168 shared documents, its batch request gave no grade a document in 187 of 187 contexts (the 115 of slice 2.5 included) and took 52.2 % of the control's grading seconds, requests with a schema carry no temperature — recorded, not changed; 10.8 Mac-hours, one run on one host, not speed evidence; budget of the campaign recounted (627 s a case through grading, 46 cases a night); labels `single_model_verified`, checked by no model of another vendor and by no person | [Capsule](docs/evidence/variance-pilot-gold-metrics.md); [measure](reports/variance-pilot/768a195/measure.json); arms [control](reports/variance-pilot/768a195/control), [pool30](reports/variance-pilot/768a195/pool30), [sent3](reports/variance-pilot/768a195/sent3), each with its `model-requests.json`; [requests of the 2.5 baseline](reports/baseline/68c5f8d/model-requests.json); `scripts/model_requests.py`; `tests/test_variance_pilot_artifact.py`, `tests/test_model_requests.py`; [development ledger](evaluation/dev_ledger.jsonl), entries 3–5; rule (c) | measured, no verdict; labels single_model_verified |
| Q 2.5 production baseline on H and Hm with its evidence-loss map (T-65): hybrid retrieval with parent expansion, graph off, 115 cases from `68c5f8d`, none excluded by the collection (H n 99 / 99 / 98 for the judged metrics); one judge, Claude Opus 5.5 (`single_judge`), stability retest passed — quadratic κ 0.9281, CI95 [0.8592, 0.9756] over 192 units of 20 cases; H `precision_at_5` 0.5354, `sent_precision` 0.6247, `ndcg_at_5` 0.7638, lexical `context_precision` 0.5436; Hm 0.6800 / 0.7556 / 0.7990 / 0.3077; H is 4 family clusters and Hm 1, so the points are read as points; nothing generated, not speed evidence, no contamination control; neither a model of another vendor nor a person checked a grade; `ndcg_at_5` is low by construction (its ideal counts expanded texts; over the seeds alone the same grades give 0.9622 and 0.9298); loss map on keyword terms, a proxy with a looser rule for H than for Hm: H 91 of 100 cases without a loss (rerank cut 6, before the pool 3), Hm 2 of 15 (before the pool 11, rerank cut 2), no index loss, cause before the pool unknown; the judge and the map do not rank the cases alike; first campaign: the plan's default stands — H1 in the graph branch with the budget of 40 as its setting, not chosen by the map (the run is graph off) — second slot not taken; cold-read by an isolated session of the same model | [Capsule](docs/evidence/production-baseline-h-hm.md); [report](reports/baseline/68c5f8d/report.json); [loss map](reports/baseline/68c5f8d/loss-map.json); `tests/test_production_baseline_artifact.py`; [development ledger](evaluation/dev_ledger.jsonl), entry 2; rule (c) | measured, single_judge |
| Q 2.5 preliminary evidence-loss map (T-63): 100 historical H cases, 200 required-term occurrences; hybrid first losses in 4 cases by the post-caps pool and 9 more between pool and sent context, stage unknown; index proxy has no missing terms; G2/G3 and archive limits explicit, no gold or current baseline | [Capsule](docs/evidence/evidence-loss-map-prelim.md); [artifact](evaluation/evidence-loss-map-prelim.json); `tests/test_evidence_loss_map.py`; [development ledger](evaluation/dev_ledger.jsonl), entry 1; rule (c) | measured archive term proxy |
| Q 1.4 semantic development ruler (T-58): P2 unexpanded H/Hm top-five consensus baseline, published as provisional until slice 1.1; that check of the consensus against model references passed on 2026-10-04 within its scope ([capsule](docs/evidence/p2-model-reference-kappa.md)), the dated artifact keeps `provisional_ruler` (no human calibration: plan D11, 2026-10-03); precision, sent precision and nDCG with component-bootstrap intervals, gold metrics N/A; explicit provisional family mapping | [Baseline and provenance](docs/evidence/semantic-ruler-p2-baseline.md); [artifact](evaluation/semantic-ruler-p2-baseline.json); `tests/test_semantic_ruler.py`, `tests/test_semantic_ruler_p2_artifact.py`; rule (c) | measured, provisional_ruler |
| P2 ruler check without people (plan slice 1.1, T-57): quadratic κ of the registered GLM + Sonnet lower-median consensus on the blind ten-case sample (50 documents) is 0.9333 to Astra (CI95 [0.8511, 0.9859]) and 0.9604 to Opus (CI95 [0.9087, 1.0000]); bootstrap clustered by case, 10 000 resamples, seed 20260925; both intervals entirely above 0.7 → branch 3 of the registered rule, ruler `model-cross-checked` (never `human-validated`) for the sample's question classes and unexpanded top-5 contexts; a check by models — an error they share stays undetected; no gate or default changed | [Check, rule and caveats](docs/evidence/p2-model-reference-kappa.md); [artifact](reports/p2/p2-model-reference-kappa.json); `tests/test_p2_reference_kappa_artifact.py`; rule (c) | measured |
| P2 GPT-6-Astra xhigh model reference grades on the blind ten-case sample built for human grading: 10/10 cases and 50/50 documents graded, 30 relevant; quadratic κ 0.8930 to Sonnet 5, 0.8824 to GLM 5.3, 0.9727 to Opus 5.5; no human grades will follow (plan D11, 2026-10-03); no P2 verdict or gate changed | [Ratings and limits](docs/evidence/p2-astra-reference-sample.md); [raw replies](reports/p2/astra-reference/replies.jsonl); `tests/test_p2_astra_reference_artifact.py` | measured |
| Q 2.1/2.2 route observability (T-59): `/api/ask` logs a `retrieval_route` trace step (configured, selected and effective strategy with a bounded reason, classifier fields, query transform fingerprint, documents, generation context tokens); the hybrid lane reports its path; fallbacks `graph_projection_missing`, `retriever_without_graph_lane`, `retriever_error` and the route reach the Evidence endpoint and tab; `RAG_RERANK_BATCH` validated and reported as `rerank_batch_effective` | `tests/test_ask_contract_route.py` (HTTP ask → trace → Evidence, 16), `tests/test_route_trace_units.py`, `tests/test_route_trace_nodes.py`, `tests/test_graph_route_observability.py`; rule (a), no capsule | synthetic |
| P2 Opus 5.5 max model reference grades on the blind ten-case sample built for human grading: 10/10 cases and 50/50 documents graded, 28 relevant; no human grades will follow (plan D11, 2026-10-03); no P2 verdict or gate changed | [Ratings and limits](docs/evidence/p2-opus-reference-sample.md); [raw replies](reports/p2/opus-reference/replies.jsonl); `tests/test_p2_opus_reference_artifact.py` | measured |
| P2 blinded relevance judgment on H: GLM + Sonnet each graded all 500 units; ordinal α 0.8566, primary per-case τ_b 0.1561 (CI95 [0.0197, 0.2880]); registered `RULER_DOES_NOT_TRACK`; no human grades will follow (plan D11, 2026-10-03); no gate or default changed | [Measurement and limits](docs/evidence/p2-blinded-relevance-judgment.md); [current report](reports/p2/p2-blinded-judge-glm+sonnet.json); `tests/test_p2_blinded_judge_artifact.py` | measured |
| Chroma restart stability after the persistence fix (`534612e`), one build process and seven new-process trials on one Mac: 0 of 5589 records left to the write-ahead log; all seven trials answered all 115 cases as the build did, on both paths; no runtime default changed | [Measurement and limits](docs/evidence/chroma-restart-stability-after-fix.md); [raw report](evaluation/chroma-restart-stability-after-fix.json); `tests/test_chroma_restart_stability_after_fix_artifact.py` | measured |
| Chroma restart stability on production's write path, one build process and seven new-process trials on one Mac: 128 of 5589 records left to the write-ahead log; trials 0–4 and 6 answered all 115 cases as the build did; trial 5 changed case 93's last vector result and its candidate set; no default changed, the fix is a separate slice | [Measurement and limits](docs/evidence/chroma-restart-stability.md); [raw report](evaluation/chroma-restart-stability.json); `tests/test_chroma_restart_stability_artifact.py` | measured |
| D.5 cold start and memory, seven new-process trials per arm on one Mac: median time to first result 85.7 ms PostgreSQL against 1494.7 ms Chroma/BM25; client resident set 68,644,864 against 310,738,944 bytes, with the backend's 98,246,656 bytes counted apart; PostgreSQL answers identical across trials, Chroma's changed in 13 of 115 cases; current backend retained | [Measurement and limits](docs/evidence/d5-pgvector-cold-start.md); [raw report](evaluation/d5-pgvector-cold-start.json); `tests/test_pgvector_cold_start_artifact.py` | measured |
| D.4 graph and evidence parity on the production schema: 10300 nodes and 17327 edges reload with an identical persisted contract; 5589 chunk nodes join 5589 evidence rows; RLS forced on 4 tables with 0 cross-tenant rows; probes `42501`/`55000`/`55000`; 5877 unresolved cross-references not persisted; no migration decision, Phase D open | [Measurement and limits](docs/evidence/d4-pgvector-graph-evidence.md); [raw report](evaluation/d4-pgvector-graph-evidence.json); `tests/test_pgvector_graph_evidence_artifact.py` | measured |
| D.3 offline rerank: final PostgreSQL/Chroma precision 0.460985/0.472891 over 115 cases; no migration decision; Phase D open; describes code `1e64ee3` (`vectordb/_base_manager.py` changed in T-59, not re-measured) | [Integrity, metrics and limits](docs/evidence/d3-pgvector-rerank.md) | measured |
| D.2 pgvector ANN: recall@20 0.965217 over 115 cases; HNSW warm p95 3.45–3.64 ms; 0.20 outlier closed by focused replay (retained original index non-monotonic: ef 100 0.20, ef 40 and ef 200 both 1.0; fresh rebuild 1.0 across the measured grid; localized to the retained index state, no root cause claimed); no migration decision; Phase D open | [Measurement and full replay](docs/evidence/d2-pgvector-ann.md) | measured |
| D.1 pgvector pre-reranker comparison: 115 cases, 3 runs; sequential scans, non-owner RLS; Phase D open; describes code `fa0146c` (`vectordb/_base_manager.py` changed in T-59, not re-measured) | [Measurement and replay](docs/evidence/d1-pgvector-prererank.md) | measured |
| C.3 manual copilot: validated shipment skeleton in `ai_draft`, agent API readback, off parity and fallback | [Copilot verification](docs/evidence/c3-copilot-contract-draft.md) | synthetic |
| C.3 HTTP: pinned response shape → verified fixture answer; evidence binding and legacy-off parity | [HTTP verification](docs/evidence/c3-contract-shaped-response.md) | synthetic |
| Admin Traces can open a known trace ID or direct link and show its Evidence, even when the trace is absent from the recent list | [Browser check and limits](docs/evidence/admin-trace-lookup.md); `scripts/qa/test_admin_trace_lookup_ui.py` | synthetic |
| Evidence UI shows the escalation handoff case, contract, reasons and evidence summary beside the trace outcome | [Browser regression](scripts/qa/test_escalation_evidence_ui.py); [ask → trace → admin HTTP regression](tests/integration/test_shipment_status_e2e.py) | synthetic |
| Evidence UI shows the actual structural/entity path kind, matched entities and entity hops; removes a false no-traversal claim | [Mac Chromium browser regression](scripts/qa/test_graph_evidence_ui.py); [GR-2 HTTP path](docs/evidence/gr2-entity-retrieval-wiring.md) | synthetic |
| GR-2 entity retrieval: bounded traversal → third RRF list → `/api/ask` → Evidence; stale graph rejection and off/auto fallback | [HTTP and retrieval verification](docs/evidence/gr2-entity-retrieval-wiring.md) | synthetic |
| GR-4 structural path: opt-in `/api/ask` → SQLite → Evidence; off/auto fallback, browser rendering and export | [HTTP and browser verification](docs/evidence/gr4-structural-product-wiring.md) | synthetic |
| GR-1b seed reservation: coherent 0.5472 / 0.9200; seed text preserved, no metric gain, NO-SHIP | [report and tests](docs/evidence/gr1b-seed-expansion.md) | measured |
| GR-1b structural replay: 100/100 exact; expansion alone 0.5125 / 0.9300, no G1 keyword losses, NO-SHIP | [stage report and tests](docs/evidence/gr1b-stage-replay.md) | measured |
| GR-1b query-only control: 0.6268 / 0.7250; 22 FULL regressions, NO-SHIP; missing-hit diagnosis | [report and reproduction test](docs/evidence/gr1b-query-control.md) | measured |
| GR-1b bounded safe-subset oracle: 0.6780 / 0.9250 with G1 fallback; label-dependent diagnostic only | [GR-1b oracle](docs/evidence/gr1b-safe-subset-oracle.md) | measured |
| Postgres append immutability | [c4](docs/evidence/c4-postgres-append-immutability.md) | synthetic |
| Postgres temporal evidence | [c5](docs/evidence/c5-postgres-temporal-evidence.md) | synthetic |
| Protected evidence encryption + redaction | [c6](docs/evidence/c6-protected-evidence-encryption-redaction.md) | synthetic |
| Resolution restore smoke | [c7](docs/evidence/c7-resolution-restore-smoke.md) | synthetic |
| Mac Postgres deployment | [c8](docs/evidence/c8-mac-postgres-deployment.md) | synthetic |
| Postgres temporal knowledge authority | [e2](docs/evidence/e2-postgres-temporal-knowledge.md) | synthetic |
| Governed ticket action | [f](docs/evidence/f-governed-ticket-action.md) | synthetic |
| Deterministic resolution grader | [g1](docs/evidence/g1-deterministic-resolution-grader.md) | synthetic |
| Replay manifest impact report | [g2](docs/evidence/g2-replay-manifest-impact-report.md) | synthetic |
| Manifest-bound replay trials | [g3](docs/evidence/g3-manifest-bound-replay-trials.md) | synthetic |
| Versioned resolution corpus coverage | [g4](docs/evidence/g4-versioned-resolution-corpus-coverage.md) | synthetic |
| Versioned synthetic outcome ledger | [g5](docs/evidence/g5-versioned-synthetic-outcome-ledger.md) | synthetic |
| Synthetic outcome comparison | [g6](docs/evidence/g6-synthetic-outcome-comparison.md) | synthetic |
| Synthetic release evidence manifest | [g7](docs/evidence/g7-synthetic-release-evidence-manifest.md) | synthetic |
| Synthetic release safety gate | [g8](docs/evidence/g8-synthetic-release-safety-gate.md) | synthetic |
| Durable session admission contract | [capsule](docs/evidence/durable-session-admission-contract.md) | synthetic |
| Durable session terminal commit | [capsule](docs/evidence/durable-session-terminal-commit.md) | synthetic |
| Multi-replica session consistency SLA | [capsule](docs/evidence/multi-replica-session-consistency-sla.md) | synthetic |
| Escalation delivery telemetry | [capsule](docs/evidence/escalation-delivery-telemetry.md) | synthetic |
| Index dimension rebuild | [capsule](docs/evidence/index-dim-rebuild.md) | synthetic |
| Index dimension Windows activation | [capsule](docs/evidence/index-dim-windows-activation.md) | synthetic |
| Index lifecycle failure telemetry | [capsule](docs/evidence/index-lifecycle-failure-telemetry.md) | synthetic |
| Index manifest rollback | [capsule](docs/evidence/index-manifest-rollback.md) | synthetic |
| Orphan work telemetry | [capsule](docs/evidence/orphan-work-telemetry.md) | synthetic |
| Retention audit tenant contract | [capsule](docs/evidence/retention-audit-tenant-contract.md) | synthetic |
| Safety block telemetry | [capsule](docs/evidence/safety-block-telemetry.md) | synthetic |
| Tenant denied telemetry | [capsule](docs/evidence/tenant-denied-telemetry.md) | synthetic |
| Trace service lifecycle owner | [capsule](docs/evidence/trace-service-lifecycle-owner.md) | synthetic |
| Validated index rollback | [capsule](docs/evidence/validated-index-rollback.md) | synthetic |

29 slices, 29 `synthetic`, 0 `real_labelled`. Verified-resolution yield across
the 17 scenarios these gates cover: **1/17**. Both numbers are here rather
than in a summary elsewhere, because they are the argument for phase B.

## Phase A (2026-08-24) — the kernel gets a production caller

| Slice | Evidence class | Evidence |
|---|---|---|
| A.1 shipment-status shadow behind `/api/ask` | `fixture` | `tests/test_resolution_shadow_wiring.py` (15 tests) |
| A.5 the same shadow, proved through the endpoint | `fixture` | `tests/integration/test_shipment_status_e2e.py` (7 tests) |
| A.4 legacy body byte-identical, shadow off vs on | `fixture` | same file, `test_the_response_body_is_byte_identical_with_the_shadow_off_and_on` |
| A.1b evidence into the resolution tables | `fixture` | `tests/test_resolution_shadow_persistence.py` (24) + `tests/integration/test_resolution_shadow_postgres.py` (4) |
| A.2 durable session turn around sync `/api/ask` | `synthetic` | `tests/integration/test_session_turns_e2e.py` (8, real Postgres) + `tests/test_session_turn_wiring.py` (32) |
| A.2 database cooldown per tenant, and bounded | `synthetic` | `tests/test_db_cooldown_per_tenant.py` (15) |
| A.3 evidence view endpoint + Evidence tab + JSON export | `fixture` | `tests/test_evidence_view.py` (22) + `tests/test_admin_trace_evidence.py` (9) + `tests/integration/test_shipment_status_e2e.py` (3) |

**A.1 + A.5 together are a slice under rule (a)** (2026-08-25, `4a5bdf1`).
A.1 alone was not: the behaviour change was real — a `resolution_shadow` step
appears in the trace — but it was held by unit tests calling
`_run_resolution_shadows` directly. A.5 posts a shipment-status question to
`/api/ask` over HTTP and reads the evidence bundle back **out of the trace
store**, which is what the phase A.3 Evidence tab will have to do: the bundle
has to survive `_state_to_dict`, `json.dumps`, PII redaction and SQLite, not
just reach the sink.

A.4 is closed at the HTTP level in the same file. A.1 held "the answer does not
change" by object identity inside the process; the byte comparison of two real
response bodies, one with the shadow off and one on, is the claim that was
actually being made. That test also asserts the shadow ran, since otherwise it
would pass equally well with the shadow silently disabled.

**A.1b** (2026-08-25, `ae52cf7`) moves the same bundle from visible to
answerable: a `support_cases` row with the events for the states the run
actually walked, the `evidence_snapshots` it read, and the
`case_evidence_links` that tie them to the case version the answer came from.
The case path is asserted against `ALLOWED_CASE_TRANSITIONS` itself rather
than restated, and the round trip runs against real Postgres with the
append-only triggers and both evidence constraints live.

**A.2** (2026-08-25, `3586b0a` and `8548a1c`) is the second slice under rule
(a), and the first one that does not involve the resolution kernel at all.
`services/session.py` had a durable turn lifecycle with no caller — the other
half of FIN-01. Behind `SESSION_DURABLE_TURNS`, `/api/ask` now admits a turn
before it answers and ends it when it is done: a second request on a session
that is still answering gets a 503 instead of racing the first one, and the
message pair is written by the transaction that marks the turn terminal
rather than by a best-effort write that could drop it. The endpoint is driven
over HTTP against a disposable PostgreSQL and the rows are read back — turn
status, committed version, the pair through
`GET /api/sessions/{id}/history` after the in-memory session map is cleared.

Its second half fixes a defect the audit named: one process-wide
`_db_retry_after` deadline meant a single tenant's database failure stopped
session lookups and message writes for every tenant for a minute. The
cooldown is now per tenant and bounded, with a test that fails against the
old code — tenant B's pair is written while tenant A is in cooldown.

Deliberately absent: replay of a committed response body, `Idempotency-Key`,
`ETag`/`If-Match`. That is REL-03D and the durable-HTTP work, frozen in
`ROADMAP.md`; a turn stores the digest of its pair and no payload.

The A.2 rows are `synthetic`, not `fixture`: no fixture TMS is involved.
They prove the mechanism and say nothing about the domain.

**A.3** (2026-08-25) is the third slice under rule (a) and the first phase-A
item a person can look at. `GET /api/admin/traces/{trace_id}/evidence` joins a
shadow step into what a reviewer needs — contract and version, the policy
decision with its own `recorded_at`, every claim beside the evidence under it
and how old that evidence was when it was read, postconditions, and a replay
receipt of the digests the run was pinned to — and the admin UI renders it
beside Raw JSON with a JSON export. It reads the **trace**, not the resolution
tables: those are the queryable copy and their write is best-effort and
bounded, so a run whose database write timed out still has a complete trace
step. The view carries `case_id` and `case_version` so the queryable copy stays
one lookup away.

The row is `fixture`, not `synthetic`: the journey it renders runs against the
fixture TMS, so what it displays is fixture-sourced.

Building it found the defect in the corrections table below — until then every
bundle behind `/api/ask` was empty, so the tab would have rendered a permanent
blank. That is the argument for the rule: the tab is what made the emptiness
visible, and no amount of local test coverage had.

No row in this phase-A table is `measured`. The first `measured` number
from this journey is A.6 below: over the 100
agent-authored-over-real-documents cases, still `agent_labelled` and 0
approved, admission recall is 0.0000, not a resolution score.

`fixture` is a fourth evidence class, weaker than `synthetic`: the journey
runs against a fixture transport management system
(`resolution/adapters/fixtures/shipment-status-v0.1.json`), so it demonstrates
the wiring and proves nothing about air cargo. Phase B replaces it.

## Phase B (2026-08-25) — the labels, and what they found

| Slice | Evidence class | Evidence |
|---|---|---|
| B.1 journey/outcome/root-cause labels on all 100 air-cargo cases | `agent_labelled` | [capsule](docs/evidence/b1-aircargo-journey-labels.md) · `tests/test_aircargo_labels.py` (13) · `evaluation/curated_cases_aircargo.manifest.json` |

**B.1 is not yet a slice under rule (b).** Rule (b) counts *real* labelled
cases, and `real_labelled` is still 0: every label is the agent's proposal
until the domain-owner proxy approves a batch of 20 (Q2). ADR 0008 decided
that fallback in advance, and the code enforces it — `evidence_class` is
derived from `approved_by`, so a file cannot claim the stronger class by
writing it.

What the labelling produced instead is a finding that changes the rest of
phase B. **All 100 cases name no shipment**: 66 belong to no kernel journey at
all, and the 34 that do are blocked before they start by
`no_shipment_binding`. Nothing in the corpus can reach an observation, a
policy decision or a claim, so B.3 — "the first real numbers on the 100
labelled cases" — cannot be run against it, however good the kernel gets. The
brief's own NO-GO check (§15, "100 cases не отражают реальные обращения") is
what fired. `expected_terminal` is `verified` for 100 out of 100 for the same
reason: these are questions *about* air-cargo work, not requests *inside* it,
so the corpus exercises no escalation, disclosure or refusal path either.

The provenance is narrower than the audit's shorthand as well: the 201 source
documents are real, the 100 questions over them were written by an agent
(`325d63c`, `6b7417d`, `32e841f`). An approval makes the **labelling** real,
not the cases — the manifest says so in `case_source`.

## B.1 approval (2026-09-25) — the labels become real

| Slice | Evidence class | Evidence |
|---|---|---|
| T-54 label approvals in a sidecar pinned to the dataset; Julia approved batches 1–5 | `real_labelled` (100 labels; cases agent-authored) | [spec](archive/docs/specs/aircargo-label-approval.md) · `tests/test_aircargo_label_approvals.py` · `evaluation/curated_cases_aircargo.approvals.json` · `evaluation/curated_cases_aircargo.manifest.json` |

Rule (b): `real_labelled` goes from 0 to 100 at `73b13b9`. The dataset stays
byte-identical, so every published measurement that pins it still replays. The
labelling is real. The cases are still agent-authored over real documents, and
none names a shipment, so B.2, B.3 and B.5 stay blocked on data. Reports published
before `73b13b9` describe their labels as `agent_labelled` (0 approved). That was
true when they ran.

## A.6 (2026-08-27) — admission scored, and what the score says

| Slice | Evidence class | Evidence |
|---|---|---|
| A.6 journey admission scored on the 100 labelled cases | `measured` over `agent_labelled` | [a6](docs/evidence/a6-journey-admission-and-clarification.md) · `python scripts/journey_admission_report.py` |

**A.6 is a slice under rule (c):** a published number with provenance
(corpus sha256 + HEAD sha + code digest + `Reproducible from HEAD`).
`/api/ask` did not change in A.6. T-03 later closed that endpoint gap as
A.7 below.

On these 100 agent-authored-over-real-documents cases, still
`agent_labelled` and 0 approved, admission recall is **0.0000**. That is
the published number, and it is the point. The corpus cannot measure
resolution for three independent reasons: no case names a shipment (B.1);
the corpus is Russian and the gate's vocabulary was English
(`contains_both_domain_noun_and_status_cue: 0` at `36d4269`); and with
the language removed (`bd82297`), over the 100
agent-authored-over-real-documents cases, still `agent_labelled` and 0
approved, admission recall is still 0.0000 — reachability moved from
`both 0` to `both 1`, and the one admission is a false positive on a
case labelled `exception_escalation`. The third reason was only findable
because the Russian half is a translation of the English one, not a list
fitted to this corpus.

The before/after table and the report as it prints are in the capsule,
which also records that T-02 fixed four earlier provenance defects.
T-07 closes the remaining provenance gap in report schema v1.3: corpus and
manifest are each read once, their exact snapshots join the code inputs in
`reproducible_from_head`, and every comparison uses the same resolved commit
SHA rather than symbolic `HEAD:path`. Inputs outside the repository fail
closed. Two regressions were RED before the repair; the isolated Mac gate is
11 passed plus strict Mypy and Ruff. Commits: `6651964` (T-01, the gate),
`36d4269` (T-02, the scorer), `bd82297` (T-08, the Russian half), and `491860d`
(T-07). All are local, not pushed, and have not been through remote CI.
T-09 then closes the validator gap: the exact double-space stem was RED before
the one-line source fix; 174 adjacent tests, strict Mypy and Ruff are green.
T-09 is local in its own commit, not pushed, and has not been through remote CI.

## A.7 (2026-08-27) — clarification owns the opt-in endpoint answer

| Slice | Evidence class | Evidence |
|---|---|---|
| A.7 `/api/ask` projects `CLARIFICATION_REQUIRED` for an admitted no-id request | `synthetic` | `tests/integration/test_shipment_status_e2e.py::test_clarification_flag_returns_the_contract_ask_and_updates_session_history` · `tests/test_resolution_shadow_wiring.py` |

**A.7 is a slice under rule (a).** The independent
`RESOLUTION_CLARIFICATION_JOURNEYS` allowlist defaults off and rejects unknown
journeys. With `shipment-status` named in both allowlists, a Russian status
question without an id returns the contract-derived disclosure and asks for
`shipment_id`; the response carries no claims, citations or measured quality.
The same E2E holds the response schema, trace/session identity and in-memory
session answer. Flag off, a declined request, every other terminal and a
shadow/projection failure keep the legacy response unchanged.

## A.8 (2026-08-27) — an empty Evidence view has an explicit cause

| Slice | Evidence class | Evidence |
|---|---|---|
| A.8 Evidence distinguishes disabled, declined and failed shadow production | `synthetic` | `tests/integration/test_shipment_status_e2e.py::test_clarification_flag_leaves_a_declined_request_on_the_legacy_path` · `tests/integration/test_shipment_status_e2e.py::test_a_shadow_that_raises_still_returns_the_legacy_answer` · `tests/test_evidence_view.py` · `tests/test_admin_trace_evidence.py` |

**A.8 is a slice under rule (a).** A request through `/api/ask` now leaves a
minimal trace outcome when `shipment-status` declines it or its producer
fails; `GET /api/admin/traces/{trace_id}/evidence` and the admin tab distinguish
those outcomes from a disabled shadow. The decline still returns the exact
legacy answer, calls neither source nor policy, and is not offered to the
resolution-table persistence path. Producer failures expose no exception
detail to the API.

## Phase C (2026-08-30…2026-09-11) — generator benchmarks

| Slice | Evidence class | Evidence |
|---|---|---|
| C.1a Qwen 2.5 7B baseline over 3 × 100 cases | `measured` over `agent_labelled` | [raw report](evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json) · [SHA-256](evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json.sha256) · `tests/test_phase_c_baseline_artifact.py` |
| C.1b Qwen3 8B over 3 × 100 cases | `measured` over `agent_labelled` | [c1b-qwen3-generator-benchmark](docs/evidence/c1b-qwen3-generator-benchmark.md) · [raw report](evaluation/c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json) · [SHA-256](evaluation/c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json.sha256) · `tests/test_phase_c_qwen3_artifact.py` |

**C.4 decision (2026-09-21):** [NO-SHIP of Qwen3 as default](docs/evidence/c4-generator-model-decision.md), based on the two reports above; no new measurement. Faithfulness 0.8986 misses 0.90; NLI does not replace that gate, and total-host peak RAM is unknown. Existing artifact tests reproduce both reports.

**C.1a is a slice under rule (c):** a Mac run that actually happened, with
exact source, corpus, cached-context, model and config provenance. All 300
rows have valid generation, LLM-judge and NLI output; none has an error. The
run-level means are LLM faithfulness **0.8295** (95% CI
[0.8295, 0.8295]), NLI faithfulness **0.8919** ([0.8916, 0.8923]), context
precision **0.5067** ([0.5067, 0.5067]) and mean latency **197.50 seconds per
case** ([192.10, 202.90]).

This is generator-quality evidence over 100 agent-authored questions and
hash-pinned cached contexts from real documents; it is not a shipment-resolution
number. The baseline misses the phase-C faithfulness and precision thresholds.
C.1a alone was neither a default-model change nor the phase's final NO-SHIP
decision.

**C.1b is a second slice under rule (c):** Qwen3 8B completed the same 3 × 100
contract with zero failed cases. LLM faithfulness is **0.8986**, NLI
faithfulness **0.9908**, answer relevancy **0.8095**, and mean latency **176.81
seconds per case** (run-level 95% CI [105.34, 248.29]). Context precision stays
**0.506657** and recall **0.9050** because the cached-context digest is exactly
the C.1a digest. The result is now an input to C.4, not a model flip: the LLM
faithfulness mean remains 0.0014 below the 0.90 gate, and the report does not
contain a total-host peak-RAM measurement.

## Stream GR (2026-09-09) — the retrieval ruler

| Slice | Evidence class | Evidence |
|---|---|---|
| GR-0.3 phase C retrieval baseline split by question class, over the question-class sidecar `evaluation/curated_cases_question_class.jsonl` + its manifest (`tests/test_question_class_labels.py`) | `measured` over `agent_labelled` | [gr0-bucket-baseline](docs/evidence/gr0-bucket-baseline.md) · [report](reports/gr/gr0-bucket-baseline.json) · `tests/test_gr_bucket_baseline.py` · `python scripts/ab_context_precision.py --buckets` |
| GR-1a section coherence measured as a narrowing arm over the same pinned pool, against GR-0.3 and against fixed top-k truncation | `measured` over `agent_labelled` | [gr1a-section-coherence](docs/evidence/gr1a-section-coherence.md) · [report](reports/gr/gr1a-section-coherence.json) · `tests/test_section_coherence_arm.py` · `python scripts/ab_context_precision.py --section-coherence` |
| GR-1b recovered Mac structural pool: precision 0.5475, recall 0.9200; NO-SHIP at 0.63, prefilter 0/100; producer revision is handoff-attributed | `measured` over `agent_labelled` | [gr1b-structure-graph](docs/evidence/gr1b-structure-graph.md) · [report](reports/gr/gr1b-structure-graph.json) · `tests/test_gr1b_artifact.py` reproduces archived input |
| GR-1b same-pool controls: top-1 reaches 0.6403 but loses 23 FULL; no ordinary top-k meets precision and coverage together | `measured` over `agent_labelled` | [gr1b-same-pool-controls](docs/evidence/gr1b-same-pool-controls.md) · [report](reports/gr/gr1b-controls.json) · `tests/test_gr1b_controls.py` |
| GR-2 entity lane against GR-1 on the same cases: phase C 0.5475 → 0.5487 (single-hop 0.5487 → 0.5499, lane on 6/100), multi-document bucket unchanged on all 15 cases although the lane fired on 11; NO-SHIP at 0.63, default unchanged | `measured` over `agent_labelled` | [gr2-entity-graph-lane](docs/evidence/gr2-entity-graph-lane.md) · [report](reports/gr/gr2-entity-graph.json) · `tests/test_gr2_artifact.py` rebuilds from the archived pools |
| GR-3 three-arm A/B on the same cases: phase C `G2` 0.5487 vs hybrid 0.5067 (FULL 87 → 89); multi-doc bucket recall 0.5000 → 0.4000, FULL 4 → 1; retrieve p95 +8765.2 ms on `deproject-mac`; generation half `not_evidence` (297/300 valid, 99 paired cases); **NO-SHIP-to-default**, default unchanged | `measured` over `agent_labelled`; generation half `not_evidence` | [gr3-graph-lane-ab](docs/evidence/gr3-graph-lane-ab.md) · [report](reports/gr/gr3-graph-lane-ab.json) · [raw generation](evaluation/gr3-g2-qwen25-7b-32de532-phase-c-generator-benchmark.json) · [sha256](evaluation/gr3-g2-qwen25-7b-32de532-phase-c-generator-benchmark.json.sha256) · [reproduction test](tests/test_gr3_artifact.py) rebuilds from the archived pools |
| P1 adaptive-k cut of the fresh reranked top-5: held-out precision 0.5372 vs 0.5067 control; recall 0.8900 vs 0.9050, FULL/PART/MISS 86/6/8 vs 87/7/6; fact-preserving oracle 0.6505; **NO_SHIP**, default unchanged | `measured` over `agent_labelled` | [p1-adaptive-k](docs/evidence/p1-adaptive-k.md) · [report](reports/p1/p1-adaptive-k.json) · `tests/test_p1_adaptive_k_artifact.py` |
| P1b frozen P1 cut under production expansion: `rel_0.2+exp` precision 0.5975 vs 0.5768 expanded control (+0.0207, CI95 [0.0104, 0.0327]); recall 0.9700 vs 0.9800, FULL/PART/MISS 96/2/2 vs 97/2/1, one fact loss; held-out `p1_cv+exp` 0.6062; control equals Q1's expanded top-5; **NO_SHIP**, default unchanged | `measured` over `agent_labelled` | [p1b-expanded-cut](docs/evidence/p1b-expanded-cut.md) · [report](reports/p1b/p1b-expanded-cut.json) · `tests/test_p1b_expanded_cut_artifact.py` |

**GR-0.3 is a slice under rule (c)** and the first published number of stream
GR: context precision **0.5067** and recall **0.9050** at top-5 over the pinned
arm-C pool (`91ce1745…`), reconciling exactly with the C.1a baseline, split as
`single_hop` 0.5063 / 0.9091 over **99** cases, `multi_hop` 0.5401 / 0.5000 over
**1**, `aggregation` and `global` over **0** each. All of it is over 100
questions agent-authored from real documents, still `agent_labelled` with 0
approved, whose question classes are agent-assigned and likewise unapproved.

The row is also where the T-11 question-class labels stop being an unmeasured
artefact: this is the first number computed over them. With 99 of the 100 cases
in one bucket the table cannot discriminate between classes, which is the
finding rather than a defect — GR-0.2's ≥ 15 new multi-hop questions are the
precondition for any bucketed comparison, and they need a new candidate pool
built on the Mac. No retrieval behaviour changed in this slice.

**GR-1a is a slice under rule (c)** and the first *arm* measured against that
ruler: section coherence over the same pool, off by default, reported as a whole
threshold grid rather than one cell. Twelve of the twenty cells cost no keyword
coverage; at the best of them it reaches context precision **0.5216** against
the baseline's **0.5067**, with recall **0.9050** and 87 / 7 / 6 unchanged —
but plain top-4
truncation of the same pool reaches **0.5214** with the same coverage, so on
this corpus the headline gain is a smaller *k*, not section structure. The arm
beats fixed truncation only where it drops harder: 82 FULL at 2.13 documents per
case against top-2's 79, and 71 FULL at 1.24 documents against top-1's 65. The
GR-1 target of 0.63 is reached only at the threshold that turns 16 FULL cases
into PART or MISS, all named in the capsule. No production retrieval behaviour
changed in this slice either.

## Corrections

Not slices — these fix claims that were false, so they do not go in the table
above.

### 2026-10-03

| Fix | Commit | Test |
|---|---|---|
| Eleven artifact tests read git history by commit SHA while the CI `test-unit` job fetched one commit: the job now checks out full history. The multi-hop corpus proof failed without the gitignored corpus: it now skips. The whitespace and end-of-file hooks rewrote a byte-pinned report: `reports/` is excluded from both (T-72) | `f197481` | `tests/test_github_workflows.py`, `tests/test_precommit_config.py`, `tests/test_gr_multihop_cases.py` |
| Six Python packages carried advisories with fixed releases (`anyio`, `oauthlib`, `pyjwt`, `pypdf`, `sentence-transformers`, `urllib3`): floors raised, both locks rebuilt, `sentence-transformers` capped below 6 (T-73) | `ebc343b` | `tests/test_pip_audit_floors.py` |
| Three npm advisories: floors raised for the two with a fix (`dompurify`, `fast-uri`); one dated exception by advisory id for GHSA-ch52-4w7c-c8xp in `http-cache-semantics`, which has no fixed release ([ADR 0009](docs/adr/0009-npm-advisory-without-fix.md)); the Pages audit step is now `npm run audit:deps` (T-74) | `45a417a` | `tests/test_docs_site_npm_audit_gate.py`, `tests/test_docs_site_npm_audit.py`, `tests/test_npm_audit_floors.py` |

These repaired a red CI (runs 37093493571 on `70d272c` to 37137697604 on `df1bf47`); they are not
slices. The fourth cause, the request-context leak, was a product defect and is a slice: T-71,
in the table above. Green afterwards: run 37157492007 on `45a417a`. Not checked:
`sentence-transformers` from the lock with real models — the Mac environment is not built from
the lock.

### 2026-08-29

| Fix | Commit | Test |
|---|---|---|
| Human-calibration readiness now requires at least 40 unique cases with 40 valid double labels; the binding floors cannot be lowered | `56b6dcc` | `tests/test_calibration_artifact.py` |

This is a fail-closed correction, not B.4 completion. The checked-in calibration
set remains 10 synthetic routes; no human-labelled route was added or claimed.

### 2026-08-27

| Fix | Commit | Test |
|---|---|---|
| Multi-word admission nouns cannot be assembled across message boundaries; a complete noun and its status cue may still occur in different messages | with T-06 | `tests/test_shipment_status_admission.py` |

T-06 is a correction, not A.9. Public `/api/ask` currently supplies one
message to the shipment-status journey, so no endpoint or UI behaviour changed
and rule (a) is not satisfied. The internal tuple contract is still protected
because direct callers may supply more than one message.

### 2026-08-25

| Fix | Commit | Test |
|---|---|---|
| Governed-action ledger counts scoped to their tenant (CI-RED-1: the ledger was right, the assertion read another test's rows) | `0fdb29c` | `tests/integration/test_governed_actions_postgres.py` |
| Shipment-id extractor could not match any id the fixture TMS holds | with A.3 | `tests/integration/test_shipment_status_e2e.py` |

The extractor matched only `SHP-…`. The fixture TMS
(`resolution/adapters/fixtures/shipment-status-v0.1.json`) holds `AC-…`, and
every wiring and end-to-end test asks about `AC-100001`. So no question about a
shipment the fixture actually contains could reach an observation: the journey
answered `CLARIFICATION_REQUIRED` / `SHIPMENT_ID_REQUIRED` every time, and the
evidence bundle behind `/api/ask` never carried a source, a policy or a single
claim. Everything A.1, A.1b, A.4 and A.5 asserted was true — the shadow ran,
reached the trace, reached the tables — and none of it needed a bundle with
anything in it. The end-to-end test now drives a `verified` journey with its
claims resolved to their evidence.

The claim that was false was in [ADR 0008](docs/adr/0008-inherited-ci-red-disposition.md)
and `BACKLOG.md`, not in the code: both stated that the governed-action
reconcile path recorded a second run row for one logical action. It never did.
The ADR carries a postscript saying so.

### Phase 0 (2026-08-24)

| Fix | Commit | Test |
|---|---|---|
| Mistral prices pinned to a dated snapshot | `c4b2d0c` | `tests/test_provider_pricing_snapshot.py` |
| Resolved model recorded behind `*-latest` | `c4b2d0c` | `tests/test_mistral_provider.py`, `tests/test_graph_helpers.py` |
| Skipped eval run is `NOT_EVIDENCE`, not a pass | `f57ade8` | `tests/test_eval_gate_skip_is_not_evidence.py` |
| Copied reference answers tagged and refused | `f57ade8` | `tests/test_ragas_eval.py` |
| Cookie-auth `Origin` fail-closed | see phase 0 commit | `tests/test_session_auth_cookie.py` |
| Kernel packages inside mypy + coverage | see phase 0 commit | `tests/test_precommit_config.py` |

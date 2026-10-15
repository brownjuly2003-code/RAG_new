# Generators below 7B on the production Mac: pre-registration and plan

Status 2026-10-15: **measured.** The three generators ran their 100 cases, and the one
judge graded the 30 shared cases of all five generators (record
`reports/generator-screen/86df582/`, EVIDENCE_INDEX). Its stream was stopped once, when the
laptop ran low on memory after 99 of the 165 verdicts, and finished on 2026-10-15; the
request in flight at the stop left no verdict and was sent again. The leading small
generator came within five good answers of C.1a and C.1b, so the [reading](#reading) asks
for the judge's extension to all 100 cases under a new plan; the owner approved its run, and
it was [registered](#extension-to-100-cases-registered-2026-10-15),
[amended](#amendment-of-the-extension-2026-10-15) mid-run and measured on 2026-10-15
(`judge-100/` in the record, EVIDENCE_INDEX); an [erratum](#erratum-of-the-extension-2026-10-15)
written after the run corrects three of its sentences. One row
was replaced before its first answer ([amendment](#amendment-2026-10-14)). This plan fixes
the generators, the contract, the judge, the sample and the order of the runs before any
answer of a generator below 7B was produced or graded.

## Why

On 2026-10-14 the owner named the production host — the iMac `deproject-mac`
(i5-7500, 4 cores, 8 GB, Ollama on the CPU) — and then suspended the choice of the
production model: «Модель для прода. Давай подвесим вопрос. И посмотрим, как на
тестах результаты на модели < 7B.» The live record of the web chat on that host
(`reports/chat-live/33d4b42/`, EVIDENCE_INDEX) gave qwen2.5:7b a first token after a
median 325 s and the whole answer after 486 s, the model, the embedder and the
reranker not fitting 8 GB together. A smaller generator is the lever this host leaves
inside the stack. The screening measures only: it changes no default, and a model
swap stays on the ROADMAP stop-list until the owner decides.

## Question

How do the Qwen generators below 7B that carry the Apache 2.0 licence compare with
C.1a (qwen2.5:7b) and C.1b (qwen3:8b) on the C.1 contract — support of their claims
by the context, completeness, defects — and how fast do they write on this Mac?

## Generators

| Name | Ollama tag | Model digest | Thinking |
|---|---|---|---|
| `qwen2.5-1.5b` | `qwen2.5:1.5b` | `65ec06548149…` | none |
| `qwen3-1.7b` | `qwen3:1.7b` | `8f68893c685c…` | off (`--no-think`) |
| `qwen3-4b-instruct` | `qwen3:4b-instruct-2507-q4_K_M` | `0edcdef34593…` | off (`--no-think`) |
| `qwen2.5-7b` (C.1a) | `qwen2.5:7b` | `845dbda0ea48…` | none |
| `qwen3-8b` (C.1b) | `qwen3:8b` | `500a1f067a9f…` | off |

The three new generators are Apache 2.0. `qwen2.5:3b` is left out: it carries the
Qwen Research License, which bars commercial use. C.1a and C.1b are not rerun; their
published reports (`evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json`,
SHA-256 `ac8d9cc2…`; `evaluation/c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json`,
`1663ea59…`) give their seed-42 answers. They ran on an earlier Ollama build than
0.33.2; the model digests are the ones installed now.

### Amendment, 2026-10-14

The row registered as `qwen3-4b` named the tag `qwen3:4b`, digest `359d7dd4bcda…`. In
the Ollama registry that tag is the same manifest as `qwen3:4b-thinking-2507-q4_K_M`:
Qwen3-4B-Thinking-2507, a model with no mode without thinking (`/api/show`: finetune
`Thinking`, version `2507`). Sent `think: false`, it wrote its reasoning as the answer —
«Хорошо, мне нужно ответить на вопрос пользователя…» — and stopped at the 384-token cap
in all six cases of its 1- and 5-case steps, 69–125 s a case. A row that cannot answer
under the contract measures nothing, so the runner was stopped before that row's
100-case step, and the row was replaced, before the replacement produced any answer, by
Qwen3-4B-Instruct-2507 (`qwen3:4b-instruct-2507-q4_K_M`, manifest `0edcdef34593…`,
Apache 2.0) — the sibling of the same release trained to answer without thinking, which
is what the row was registered to measure: a 4B Qwen3 answering with thinking off.
Ollama reports a thinking capability for it, so it runs with `--no-think` like the other
Qwen3 row; the model itself does not think. The replacement and its runner
(`run_screen2.sh`) were fixed before its download; the progress log times every step.
Added after the runs: the amendment's commit `cfb78ee` is dated 17:31:22 UTC, about eight
seconds after the replacement's first answer had come back and before it was read; the
runner, which names the replacement, started its download at 17:25:14 and its 1-case step
at 17:30:31, which took 42.5 s.
The two steps of the thinking tag are published with the screening as a finding and are
not graded; nothing else in this plan changes.

## Contract

`scripts/generator_benchmark.py`, unchanged in what a generator sees: the 100 cases of
`evaluation/curated_cases_aircargo.jsonl` (`3737d694…`, `agent_labelled`), the cached
contexts of arm C `.tmp/ab_candidates_phase2_C.json` (`91ce1745…`) cut to each case's
`rerank_k` and to 6,000 characters, the prompt `aircargo-context-only-ru-v1`,
temperature 0, seed 42, `num_ctx` 4096, `num_predict` 384, 600 s per request. The
prompt, the context loader and the context cut are byte-identical at these options to
those of C.1a (`c06bdf5`) and C.1b (`b8ecc8e`). This is the benchmark's prompt over
cached retrieval, not the production chat path. Every run starts in a clean git clone
of the commit that registers this plan; the runner refuses a dirty tree.

Three departures from C.1a and C.1b, fixed here:

1. **One run, seed 42** (`--runs 1 --required-runs 1`). At temperature 0 the seeds
   42–44 gave identical answers on 99 of 100 cases for qwen2.5:7b and on 100 of 100
   for qwen3:8b; two more runs would repeat the first.
2. **No self-grading** (`--no-llm-judge`). The LLM metrics of C.1 came from the
   generator grading its own answers. Under plan decision D12 the session's model is
   the one judge, and a generator grading itself is no judge at all. The latency of a
   case is then the generation alone; the C.1 latencies include two grading requests
   and are not comparable — the speed comparison uses Ollama's own timings.
3. **Ollama timings per case** (`ollama_timing`: total, load, prompt and output token
   counts and durations).

## Measures

**Without a judge, all 100 answers** (`answer_checks` in
`scripts/generator_answer_judge.py`): failed generations, empty answers, answers with
no Cyrillic letter (descriptive — C.1b has 8 that list English field names, a right
answer to a field question), answers that are only reference marks, the share of the
case's expected keywords found in the answer (the benchmark's `context_recall` applied
to the answer; the contexts hold 0.905 of them, which bounds it), median answer length,
median latency, median prompt and output tokens per second.

**NLI** as the benchmark computes it (`MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` at
`8adb042d…`): reported, not ranked on. Its validity on these answers is not established
(slice 2.8 was not run), and it may reward short or evasive answers.

**The judge** (`scripts/generator_answer_judge.py`): `claude-opus-5-5` at effort `max`,
one stateless request per answer through the registered route
`evaluation.isolated_request`; system prompt SHA-256 `3969f275…`, request rules
`1bb264c1…`. The sample is 30 cases, the first 30 by
SHA-256 of `small-generator-screening-2026-10-14:<case_id>`, the same 30 for every
generator; each request carries the rules, the question, the context the generator saw
and its seed-42 answer, never the generator's name, in an order shuffled by a salted
hash. Fifteen of the requests are sent a second time as a retest. The judge returns
`claims_total`, `claims_supported`, `context_has_answer`, `answers_question`
(`full`, `partial`, `declined`, `no`) and `defect`. Classes: **good** — a full answer
with every claim supported and no defect, or a decline where the context holds no
answer; **partial_ok** — a partial answer, every claim supported, no defect; **bad** —
everything else, an empty answer included, which is graded without a request. A reply
of a wrong form is asked again, three attempts in all. A verdict counts only with the
record of a clean session and the hash of its planned request. The judge's agreement
with itself is reported twice: the same class on retest, and the same
`context_has_answer` across the five answers of a case, whose context is one.

## Order

1. Commit this plan, the runner changes and the judge with their tests; the tests are
   red on the parent and green on the commit on the Mac.
2. Per new generator, smallest first: 1 case, then 5 (`--max-cases`, own run ids),
   then all 100. The 1-case step names the expected time of the 100-case run before
   it starts; a failure stops the sequence until its cause is found. Expected
   generation per case: well under a minute for the 1.5B and 1.7B models, one to two
   minutes for the 4B model.
3. The judge: `plan` over the five reports, then `run --limit 1`, `--limit 4`, then the
   rest, after one probe of the subscription windows.
4. Publication under `reports/generator-screen/<code sha>/`: the three 100-case reports,
   the two steps of the thinking tag, the judge's `plan.json`, `verdicts.jsonl` and
   `summary.json`, pinned by a test, with one row in EVIDENCE_INDEX.

## Reading

Descriptive: no gate, no threshold, no ship decision. Thirty judged cases separate only
large gaps — at 25 good of 30 the 95 % Wilson interval is about 0.66–0.93 — so two
generators within five good answers of each other are not told apart. If the leading
small generator comes that close to C.1a or C.1b, the judge is extended to all 100 cases
of the generators concerned under a new plan with the same rules. The choice of the
production model belongs to the owner and stays suspended; this screening informs it.

## Extension to 100 cases, registered 2026-10-15

Registered before the extension's first request; nothing above changes.

**Why.** The leading small generator, `qwen3-4b-instruct` (23 good of 30), came within five
good answers of C.1a (20) and C.1b (21), so the [reading](#reading) calls for the judge on
all 100 cases. The owner approved the run on 2026-10-15 — «2. Да» to «Запускать расширение
судьи до 100 кейсов? Минимальный набор — Qwen3-4B-Instruct, 7B, 8B; можно добавить
qwen3-1.7b…».

**Generators.** The reading does not define "the generators concerned"; they are read as the
leading small generator and each reference within five of it — `qwen3-4b-instruct`,
`qwen2.5-7b` (C.1a), `qwen3-8b` (C.1b) — and `qwen3-1.7b` (20 good, within five of all four)
is added: the smallest generator not told apart from the references, and the one whose time
in the live chat is still unmeasured (EVIDENCE_INDEX, the chat row of the generators below
7B); whether its answers hold on 100 cases decides whether that measurement is worth the
provider change it needs. `qwen2.5-1.5b` is left out: the most bad answers of the five, 9 of
30, and four of its five questions in the live chat routed `human`. Each generator's report
is the one the 30-case plan named, with the same SHA-256.

**Sample and requests.** All 100 cases (`plan --sample-size 100`) in the same salted order,
so the first 30 are the registered 30 and their requests are byte-identical. A new retest of
15 is drawn by the same salted hash among the 400 requests: 415 in all, no answer empty.

**Reuse.** Before the first request, `reuse --from reports/generator-screen/86df582/judge`
copies the published verdicts of the requests both plans hold — the same item id and message
hash, the same route and rules, every verdict of that record vouched for: the 120 answers of
the four generators on the registered 30 cases and the 3 retests the first plan also sent.
Each copy names that plan's SHA-256 (`051aa629…`) in `reused_from`; the summary counts the
copies apart from the requests sent, and its cost covers only the latter. 292 requests are
sent; at the first run's mean, $0.106 and 42.6 s a request, that is about $31 and 3.5 hours,
in chunks of ten in the foreground.

**Unchanged:** the judge, its route and system prompt, the request rules, the verdict form,
the classes, three attempts for a reply of a wrong form, and the vouching of every verdict.

**Reading.** Descriptive: no gate, no ship decision. Per generator, the classes on 100
cases and the 95 % Wilson interval of its share of good answers — at 70 of 100 about
0.60–0.78. Per pair of the four, six pairs, the cases where only one of the two is good and
the exact two-sided sign test on them; a pair is called apart only below 0.05 / 6, and
otherwise not told apart. The judge's agreement with itself is reported as before, on the 15
retests and across the four answers of a case.

**Publication:** `.tmp/genscreen-judge-100/` while it runs, then
`reports/generator-screen/86df582/judge-100/` — `plan.json`, `verdicts.jsonl`,
`summary.json` — pinned by the record's test, with one row in EVIDENCE_INDEX.

### Amendment of the extension, 2026-10-15

At 12:05:00 UTC, after 69 of the 292 requests had been sent, a plugin was installed and
enabled in the user configuration of the Claude CLI (`figma@claude-plugins-official`), and
the `--safe-mode` session loaded it: the route refused the reply to the 70th request twice —
"the session loaded more than the request: plugins" — and the run stopped with no verdict
for it. The configuration is the owner's and is left as it is. From that request on, each
request also carries `--settings` with a file that disables the two plugins of that
configuration (`judge-100/tools/no-user-plugins.json`), added by the run's wrapper
(`judge-100/tools/run100_logged.py`), which calls the judge's `run_plan` unchanged and keeps
the message of any refused reply in `refusals.log`. A probe with and without the file showed
the session it restores: the three registered built-ins and no plugin, tool, MCP server or
skill — the session of every earlier verdict, which each verdict's record shows and
`summarize` checks. Nothing else changes.

### Erratum of the extension, 2026-10-15

Written after the run, from a cold read of its record; the registered text above stays as it
was, and no number of the plan or of the record changes.

1. **"The smallest generator not told apart from the references"** ([Extension to 100
   cases](#extension-to-100-cases-registered-2026-10-15), Generators) is wrong. `qwen2.5-1.5b`
   is smaller and had 16 good answers of 30, within five of C.1a (20) and C.1b (21), so by
   the [reading](#reading) it is not told apart from them either. It was left out for the
   reasons the same paragraph gives — the most bad answers of the five, 9 of 30, and four of
   its five questions in the live chat routed `human` — which are the session's choice, not
   the reading's.
2. **"The three registered built-ins"** ([amendment of the
   extension](#amendment-of-the-extension-2026-10-15)) are the three built-in plugins the route
   registers — `cc-plugin-agents-md`, `cc-plugin-plugin-authoring` and `cc-plugin-telemetry`
   (`BUILTIN` in `evaluation/isolated_request.py`, beside four built-in agent types) — and "no
   plugin" there means no other plugin. The settings file disables the two plugins the user
   configuration held at 12:05, not every plugin a user may add.
3. **"Whether its answers hold on 100 cases"** (Generators) was not made precise before the
   run: the reading registers which pairs are apart, not what "hold" means. qwen3-1.7b is not
   told apart from C.1a on 100 cases, with 6 fewer good answers and 8 more bad ones; that this
   still makes its timing in the chat worth the provider change is the session's opinion, not
   a result of this plan.

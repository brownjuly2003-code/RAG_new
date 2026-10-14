# Generators below 7B on the production Mac: pre-registration and plan

Status 2026-10-14: **registered, running; one row replaced before its first answer**
([amendment](#amendment-2026-10-14)). This plan fixes the generators, the contract,
the judge, the sample and the order of the runs before any answer of a generator below
7B was produced or graded.

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

# Web research of 2026-11-06: a small model on Julia's laptop

This is a reading of the sources, not a measurement. Nothing here changes a published number of
this repository.

- **Who ran it.** One subagent of the session answered [the brief](brief-8-laptop-small-model.md), on
  the session's model (Claude Opus 5.5, D12) and from the web only.
- **The report.** Its answer is the [report](report-8-laptop-small-model.md), in Russian. The subagent
  could not write files here, so the session saved its returned text verbatim from the heading on. A
  23-line preamble about the blocked write was left out.
- **The figures.** The session did not check them one by one. Each carries its source and date. The
  report marks which are vendor claims, which are its own estimates and which are unchecked.

## Why

On 2026-11-06 Julia asked whether the local model has a future: «мы дельше будем использовать
qwen? кодекса не хватит, и мы делалали небольшой эксперимент». The answer depended on the role.

- **As the answer's author, Qwen3-4B is not an option.** On the same 300 prompts of stage 5в it had
  59, 53 and 13 bad answers of 100, against Codex's 2, 0 and 0.
- **As a helper, its quality came close.** In this role it transforms the query and grades the
  documents. The baseline of the [`codex-only` record](../../evidence/codex-only-quality-record.md)
  had the Mac's 4B (Ollama `q4_K_M`) choose the contexts and Codex write the answer: 268 of 300
  good. With Codex in every role the score was 279, a detected rise. Contexts, code and framing
  changed together, so the record isolates no cause.
- **On her laptop, the helper froze the machine.** It ran on the CPU through Ollama on 2026-11-03.
  One question took 1,090 s.

Her reply: «нет, ничего не заводим. И с чего такой вопрос? Мы не оставляем историю про qwen.
Может, стоит поискать маленькую, более эффективную модель? Вероятно позже стоит запустить на этой
машине маленькую модель?»

[Research 5 of 2026-10-25](../research-2026-10-25/README.md) looked for a model for the old Mac's
CPU. This brief retargets the search to her laptop:
- Core Ultra 5 125H;
- an Arc iGPU;
- an Intel AI Boost NPU;
- 15.5 GB of memory, shared with the graphics, about 6 GB free while she works.

## In short — the report's reading

The roles are those of the product's path for one question:
1. query transformation;
2. batched document grading;
3. the answer.

The points:

1. **The device decides more than the model.** On the Arc iGPU, OpenVINO runs a 4B-class model at
   about 23 tokens/s of generation and about 600 tokens/s of prompt processing. These are Intel's
   numbers for the 155H. The CPU path of 2026-11-03 is not needed.
2. **Meteor Lake's NPU fits short prompts only**, that is, role 1. Its default prompt window is 1,024
   tokens. Above about 2,000 tokens it silently returns garbage: openvino.genai issue #3255, open
   since 2026-01-30.
3. **Qwen3.5 does not run on that NPU in any runtime.** On the iGPU it runs: Intel publishes an
   official IR, `OpenVINO/Qwen3.5-2B-int4-ov`.
4. **Roles 1–2 come first, with our own Qwen3-4B-Instruct-2507** in INT4, on OpenVINO GenAI and the
   iGPU. Its quality as a helper is roughly known, so a first test checks speed and load.
   - The known number came from Ollama's `q4_K_M`, a different quantization.
   - The record isolates no cause.
   - A swap still needs a quality run on the same 300 questions (`PLAN.md` §9).
5. **Role 2 may need no model at all.** The path already computes a bge-reranker score for each
   document. A threshold or adaptive-k on that score can be checked offline on saved pools.
6. **Role 3, the answer, stays with Codex.** No source shows a model of 4B or less closing the gap. Our
   4B answered 30, 38 and 73 good of 100, Codex 92, 92 and 100.
7. **Dead ends:**
   - IPEX-LLM was archived on 2026-01-28;
   - Ollama's use of the iGPU on Windows is uncertain;
   - any silent fallback to the CPU repeats 2026-11-03.

## The report's order for a first test

| # | What | Roles | Expected, the report's estimate | Memory | Main risk |
|---|---|---|---|---|---|
| 0 | No model: a threshold or adaptive-k on the reranker score, on saved pools | 2 | no model calls | none | the threshold depends on the corpus |
| A | Qwen3-4B-Instruct-2507 INT4, OpenVINO GenAI 2026.4, iGPU | 1, 2 | role 1 ≈ 2.5–4 s, role 2 ≈ 9–15 s | ≈ 3.5–4.5 GB | memory, with ≈ 6 GB free |
| B | Qwen3.5-2B INT4 (official IR), iGPU | 1, 2 | role 1 ≈ 1.5–2.5 s, role 2 ≈ 4–7 s | ≈ 2–2.5 GB | quality unmeasured |
| C | Qwen3-1.7B INT4, NPU, prompt ≤ 1,024 tokens | 1 | ≈ 9–15 tokens/s | ≈ 1.5–2 GB | NPU compile takes minutes; no role 2 |

The report's safe procedure for a first test:

1. **Step 0, without a model.** Note free memory, the NPU driver's version, and that the graphics
   reports as Arc, which means dual-channel memory.
2. **A separate venv.**
3. **The device set explicitly**, never `AUTO`, never Ollama.
4. **A watchdog.** It starts the test at BELOW_NORMAL priority and kills only its own process when
   any of these happens:
   - free memory drops below 2 GB;
   - a call runs over 60 s;
   - the test runs over 10 min;
   - a STOP file appears.
5. **The run.** 10 saved role-1 prompts, then 10 saved role-2 batches.
6. **The log.** Time to first token, tokens/s, peak memory, CPU and GPU load, and agreement with
   Codex.

## What it changes

Nothing yet, and two rules stand:
- no local model starts on her laptop without her word for that run;
- a model swap needs her decision with numbers (`PLAN.md` §9).

Placing this in `PLAN.md` (§8.3 item 15, stage 6) is the next session's work; see the
[handoff](../session-handoff-2026-11-06-push-local-model.md).

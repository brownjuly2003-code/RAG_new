# Web research of 2026-10-25 — our bases against the literature, how to treat our failures, the state of RAG, a checker that reads Russian, a local generator

Literature, not measurement: nothing here changes a published number of this repository, and
no number below is ours unless it says so. Session `5ec44b60`; its
[handoff](../session-handoff-2026-10-25-stage3-signals-running.md) holds the context.

## In short

- **«Низкий» is not shown to be low.** Results on all three bases are published, mostly with
  API generators, graded judge scores or a word-overlap scorer. None uses a ≤ 4B model on a CPU
  with whole-corpus retrieval and our classes. The two closest numbers measure something else.
  WixQA's Context Recall is a judge's score, our 0.63 is article identity. MultiHop-RAG's Hits@K
  counts *any one* gold fact, our 10/70 counts *all* of them.
- **Our loss is mainly generation.** Our judge's rows show unsupported claims and, on WixQA,
  wrong declines. Claude's research 3 guessed retrieval without those rows; Codex's agrees
  with them.
- **First, measure by the published rules.** That costs no Mac time and few or no judge calls.
  Then test an evidence-first answer, with an explicit answered / partly / declined status.
  It is the one prompt-only method with a measured effect: more supported claims, a little
  less recall. The router waits for stage 3. Most treatments touch the frozen
  prompt or retrieval, so each needs a `PLAN.md` amendment — Julia's decision.
- **No fast checker has a measured grounding quality in Russian.** Three multilingual encoders
  of 0.1–0.3B are candidates, and RusHallu-RAG gives a Russian human-labelled test for them
  (research 4).
- **No local model is shown to beat ours.** Qwen3.5-4B and Gemma 4 E2B are worth a pilot of
  80 paired answers (≈ 20 h of Mac), and Qwen3.5-4B is likely slower on our CPU. No
  candidate has a Russian number on answering from documents (research 5).

## Why

On 2026-10-25 Julia saw the metrics: aircargo good 63 of 100, WixQA 40, ConditionalQA 35,
MultiHop-RAG 65 on the earlier prompt. She also saw the handover problem: no cheap signal finds
the answers that need a person. At 18:41 UTC she asked: «текущие проблемы нужно же как-то
лечить… И по трем базам результат очень низкий… Вероятно стоит запустить 2 рисеча — как лечить
текущие проблемы и какие метрики по RAG актуальны». At 18:48 she added a third, on the general
state of RAG in October 2026: «решение о 3-ем рисерче стоит принять перед его запуском». At
19:06 she asked for all three in this session, each repeated by Codex («gpt astra 6 xhigh»),
one run at a time. After reading them she asked for a narrow round at 21:07 («Давай узкий
раунд»: research 4, a fast checker that reads Russian) and at 21:28 for the best local model
for the task (research 5). At 21:46 she gave Codex's budget to more runs, chosen by me
(research 6 and 7; Claude's budget is kept).

## How it was made, and what was checked

- **Briefs** (`brief-*.md` here) state our system, our subsets, our numbers and the questions.
  They hold counts only: no question, document or answer of a base, and no personal data.
- **Claude** ran each brief as a `deep-researcher` subagent on the session's model (Claude
  Opus 5.5). It had read-only web search and the brief as its only input, and wrote the
  report itself.
- **Codex** got the same brief, wrapped by `.tmp/research/build_cx_brief.py`. The wrapper adds
  an output contract and citation rules and changes nothing else.
  - The run went through the Codex companion: profile cw, `gpt-6-astra`, effort `xhigh`,
    read-only sandbox.
  - It ran in a package folder outside the repository that holds only the brief. The report is
    its final message.
  - Its rollout in `~/.codex-work/sessions/` names the model, the effort and the sandbox.
  - This is the second-opinion role of `PLAN.md` §8.1: it writes no code and grades nothing.
- **What I checked:**
  - Every number below appears in the report it is credited to; the check was
    `.tmp/research/_audit/verify.py`.
  - Nineteen claims were checked against their primary source, chosen where the reports
    disagree or where a proposal leans on them. The results are in
    [How good the two reports are](#how-good-the-two-reports-are).
  - Every link was opened by `.tmp/research/_audit/links.py`.
  - The rest is the reports' word; their links are in the reports.

| Run | Brief | Claude's report | Codex's report |
|---|---|---|---|
| 1 — results on our three bases, current metrics | [brief](brief-1-bases-and-metrics.md) | [report](claude-1-bases-and-metrics.md): 24.6k characters, 33 sources, 18:51–19:02 UTC | [report](codex-1-bases-and-metrics.md): 35.3k characters, 33 sources, 19:10–19:28 UTC, thread `01a17478-b668-7293-8418-91c299d212db` |
| 2 — how to treat claims, declines, retrieval, routing | [brief](brief-2-treatment.md) | [report](claude-2-treatment.md): 23.9k characters, 56 sources, 19:10–19:24 UTC | [report](codex-2-treatment.md): 33.8k characters, 32 sources, 19:29–19:49 UTC, thread `01a17489-8e72-7221-b9b6-c62c53d49ddb` |
| 3 — the state of RAG, October 2026 | [brief](brief-3-state-of-rag.md) | [report](claude-3-state-of-rag.md): 27.2k characters, 46 sources, 19:30–19:36 UTC | [report](codex-3-state-of-rag.md): 34.6k characters, 47 sources, 19:50–20:14 UTC, thread `01a1749c-834a-7772-b74d-9e5d0dd258d3` |
| 4 — a fast checker that reads Russian | [brief](brief-4-russian-checker.md) | [report](claude-4-russian-checker.md): 24.4k characters, 46 sources, 21:08–21:23 UTC | [report](codex-4-russian-checker.md): 29.0k characters, 34 sources, 21:08–21:30 UTC, thread `01a174e4-fbf1-7e83-b6f2-6839965950fd` |
| 5 — the best local generator for this machine | [brief](brief-5-local-model.md) | [report](claude-5-local-model.md): 25.0k characters, 40 sources, 21:29–21:46 UTC | [report](codex-5-local-model.md): 29.7k characters, 52 sources, 21:31–21:54 UTC, thread `01a174f9-7ab6-7253-b056-44f7c02ba2f7` |

## Research 1 — are our numbers low against others?

**Published results exist on every base, in other setups:**

- **WixQA.** The dataset paper (2505.08643) reports Factuality of 0.63–0.77 on Simulated, a
  *graded* GPT-4o score (1–5 → 0–1), with frontier API generators.
  - Codex alone found five later works with whole-corpus retrieval:
    - AgenticRAG: agentic search, Factuality .94 on Simulated and .96 on ExpertWritten (GPT-5-mini);
    - LivingRAG: 66–70 % LLM accuracy, Simulated and ExpertWritten pooled;
    - CorpusMap: a 79-question subset;
    - Corpus2Skill and Knowledge-as-Skill: ExpertWritten.
  - All of them use API generators; none uses a ≤ 8B model.
- **ConditionalQA.** Results are published only with the document given: FiD EM/F1
  44.4/50.8; Mistral-7B with oracle passages 55.5/63.8. None is found with whole-corpus
  retrieval, and none for the not answerable questions alone.
- **MultiHop-RAG.**
  - Codex found an 8B generator over the whole corpus (Llama-3.1-8B, 2502.11371): inference
    accuracy 92.16 %.
  - The official answer scorers count an answer right if it shares one word with the
    reference, so these accuracies are lax.
  - In the same work, graph-RAG variants score 41.2–70.3 on all types against plain RAG's
    67.0: at most +3.3, under the lax scorer.

**Both reports propose the same three metrics:**

1. **Claim faithfulness.** Our «claims supported» is already printed. The RAGChecker split
   into hallucination and self-knowledge costs ~100 judge calls a base.
2. **Nugget recall.** This is the recall of the reference's key claims, in the answer and in
   the context. It separates a retrieval miss from a generation miss.
3. **Decline quality.** Codex proposes a matrix: answerable or unanswerable, against answered
   or declined. Claude proposes a CRAG-style score: +1 right, 0 decline, −1 wrong, with
   decline precision and recall; it costs no calls, from M1/M2.

Claude adds a route to one comparable number: WixQA's own Context Recall and Factuality prompts
are in the paper's appendix. One judge call per answer and one per context make our Simulated
rows comparable with theirs. Codex's further advice, blind human labelling of our judge, is
excluded by D11: no person in the quality process.

**Where they differ:**

- **Hits@K.** Claude's report called MultiHop-RAG's Hits@K «the share of evidence in the top
  K». By that reading our 0.49 was lower than the published 0.62–0.64.
  - The official `retrieval_evaluate.py` (read 2026-10-25) settles it for Codex. A query is a
    Hits@K hit when *any one* gold fact is a substring of a top-K chunk. Spaces and newlines
    are removed and null queries excluded. MAP@10 counts the share, by a non-standard formula.
  - Our «all evidence 10/70» and mean evidence recall 0.49 are stricter measures. They are
    not comparable until recomputed by that rule.
- **The original MAP@10.** Codex alone found that a later work (Multi-Meta-RAG) recomputed
  the original voyage-02 MAP@10 with the repository's script. Its table 2 gives 0.2619,
  against the published 0.4795, at the same Hits@4 (0.6630 against 0.6625). Codex's report
  says .2718; the paper's table does not.

## Research 2 — how to treat it

Claude's ranking, each with its cost on this Mac:

| # | Option | Aimed at | Cost |
|---|---|---|---|
| 0 | Recompute MultiHop-RAG's retrieval by the official rule; check each fact in the joined context (an 800-character boundary can cut one) | measurement | no model call |
| 1 | An answer flag (answered / partly / declined) and a second «partial answer» pass for declines only | WixQA's 22 wrong declines | +2–4 min, declines only |
| 2 | A claim check in the chat as the router: the 4B's own (81–235 s) or an encoder checker | handover | minutes, or seconds (English only) |
| 3 | Repair by deleting unsupported sentences, only behind a calibrated signal (one 2026 preprint: 64.3 % of the text kept, 83.5 % of clean answers edited) | unsupported claims | one pass |
| 4 | Query decomposition plus rerank (Hits@4 0.611 → 0.763 on MultiHop-RAG, with a 32B decomposer) | multi-hop retrieval | +0.5–1 min |
| last | Fine-tuning, or an 8B generator | claims, declines | large |

**A correction to option 1.** The report says false declines are set mainly by the prompt: an
8B answers 1.5 % of ASQA under an in-context prompt and 99 % under FRONT. The Trust-Align
paper (2409.11242, read 2026-10-25) shows FRONT is a *trained* model. The paper argues the
opposite: a prompt is unreliable, and training fixes the balance. Option 1 remains a cheap
experiment, but no measured effect elsewhere backs it.

**Fast checkers and routing signals:**

- **English only.** These are the checkers that take seconds on a CPU:
  - HHEM-2.1-open: 0.1B, RAGTruth-QA balanced accuracy 74.3;
  - FactCG-DeBERTa-L: 82.3;
  - MiniCheck-FT5: 78.0;
  - LettuceDetect-large: F1 79.2.
- **Russian.** The FLAN-T5 tokenizer of HHEM and MiniCheck turns Cyrillic into `<unk>`. What
  remains for Russian is an XNLI model never measured on grounding, and the 4B's own check.
- **Routing signals.** Token log-probabilities give AUC ≈ 0.51 on RAGTruth. Semantic entropy
  needs ~10 generations, which is out of reach.

**Codex's report agrees on four points:**

- MultiHop-RAG must be recomputed before retrieval is changed.
- Repair needs a working independent trigger first.
- Training or another generator is Julia's decision.
- No checker has a measured CPU time on our load; HHEM's figure is from an unnamed processor.

**Codex differs on three:**

- **Its first content experiment is an evidence-first answer in the same call.** The answer
  first quotes the evidence for each part of the question, then states only supported claims.
  - The training-free ReClaim prompt (Llama3-8B, ASQA, checked in the paper) raised the share
    of correctly attributed sentences (CAS) from 54.7 to 77.7. EM recall fell from 55.2 to
    50.7.
  - Our prompt already allows a partial answer, so Codex would change how it is carried out,
    not add «answer partly» again. That is a direct objection to Claude's second pass.
- **False declines need their own answerability check.** A decline has no claim for a claim
  check to test, so the answer needs an explicit answered / partial / declined status.
  - With an oracle context, declines were 24 % of Qwen2.5-7B's errors (one 2026 preprint).
- **Deleting sentences.** Codex found no comparable result for it; Claude's one 2026 preprint
  is the only number.

Codex's order of measurement:

1. Finish scoring the widget's check on the saved answers. This is stage 3's run.
2. Compare independent checkers on the same answers, Russian and English apart. Thresholds
   are chosen on one part and reported on another.
3. Run a paired test of the evidence-first prompt on a fixed context. It measures claim
   faithfulness, nugget recall and declines together, so that fewer bad answers do not come
   from poorer ones.
4. Recompute MultiHop-RAG, then measure each candidate's full cost: cold and warm, peak memory,
   inside the 3,600-s ceiling.

## Research 3 — the frame

**The scope, decided ≈19:28 UTC.** Research 1 had covered the metrics and research 2 the
methods. So research 3 asked what they did not:

- the levels reached on the reference benchmarks, by system size;
- the method families behind the best results, and which transfer to a 4B on a CPU;
- how production support assistants measure quality and the handover to a person.

Nobody had covered the last one, and it is her handover question.

**Levels:**

| Benchmark | Best | Small or plain |
|---|---|---|
| CRAG | truthfulness 51 % (best industrial system) | accuracy 32.1 % (plain RAG on Llama-3-8B) |
| FRAMES | 0.66 (multi-step retrieval on Gemini-Pro-1.5) | — |
| BRIGHT, nDCG@10 | 66.9 | 52.4 (a ~4B model); BM25 14.5 |
| TREC RAG 2025 | vital nugget score 0.55 | — |

- **Russian RAG on a CPU** comes from Little Brains (2606.30062, 06.2026). The context is
  given and the machine has 16 GB; their Qwen3-4B is Q5_K_M, ours Q4_K_M on 8 GB.
  - Qwen3-4B-Instruct-2507: correctness 0.71, faithfulness 0.80.
  - GPT-5-mini: 0.73 and 0.89.
- **Hallucination when summarising** (Vectara): Qwen3-4B 5.7 %, GPT-5-mini 12.9 %.

**What transfers to a 4B on 4 cores:**

- **Yes:** cheap grounding detectors, context pruning or compression, late interaction.
- **Partly:** one LLM query rewrite or one extra retrieval step. Prompted agents on a 3B do
  worse than plain RAG: EM 0.181–0.255 against 0.270.
- **No:** graph RAG, 32B reasoning rerankers, long context instead of retrieval, RL training.

**Support in production** (vendor claims):

- Intercom's resolution without a person is 51–56 % (2024–2025) and 76 % (2026). It counts a
  customer who just left.
- Zendesk's «verified» resolution has been checked by an LLM over the transcript since
  2026-05-18.
- No company publishes the precision and recall of its escalations on live traffic.
- Computable from our records without people:
  - the CRAG-style truthfulness;
  - the share routed to a person, with its precision and recall against the judge's labels;
  - the share passing a grounding check;
  - a risk–coverage curve.

**Claude's report places us (its interpretation).** Our 35–63 good of 100 with open retrieval sit
near CRAG's plain RAG (32–44 % accuracy, Llama-3-8B to GPT-4T). They sit below Little Brains'
0.71, where the context is given. These are different metrics.

**Where Claude's report disagrees with our data:**

- **It reads the gap to 0.71 as a retrieval loss**, and calls faithfulness not the small
  models' main weakness. Our judge's rows say otherwise:
  - The context held the answer in 94–100 % of the bad answers: aircargo 17 of 17, WixQA 48
    of 51, ConditionalQA 54 of 57.
  - Most bad answers carry an unsupported claim: 14 of 17, 32 of 51, 50 of 57.
  - Sources: [research 2's brief](brief-2-treatment.md), counted from
    `reports/answer-prompt-v4/4f48fed/*-judge.cases.jsonl`. Research 3's brief did not carry
    these counts.
- **Its own table** shows the faithfulness gap (0.80 against 0.89) larger than the
  correctness gap.
- **Its first recommended family**, a cheap grounding detector, meets research 2's finding:
  those detectors read no Russian.

**Codex's report agrees on four points:**

- There is no single quality number.
- Production resolution and containment rest on what the customer did, not on a fact check.
- Nobody publishes the precision and recall of the handover decision.
- Graph RAG with a large extraction model, RL training and long context do not fit our
  hardware; one extra retrieval step does, in part.

**Codex differs on four:**

- **It will not place our numbers** on anyone's leaderboard without the same questions,
  retrieval and rubric. Our «good» is not a resolution rate either.
- **It reads our failures as our data do.** If the documents do not hold a claim, better
  reasoning will not remove it. So its priorities are:
  - structural, extractive selection of the evidence before the answer;
  - a reader trained for grounding and refusal, compared at the same retrieval and coverage;
  - a bounded extra retrieval step when the evidence has a gap;
  - late interaction only after its index size and memory are measured.
- **Russian: it found no 2026 leader for grounded answering.** Its only Russian figures are
  MIRAGE-Bench's preference scores (2025, Qwen2). It missed Little Brains, which Claude found
  and I checked.
- **It adds production detail:**
  - Fin's denominator was revised in 2026, so resolution can rise with no more solved cases.
  - Airbnb's A/B (2609.05758, checked) cut hard-escalation responses from 5.60 % to 3.08 %,
    while real handoffs moved only from 8.56 % to 8.20 %. The wording changed more than the
    routing did.
  - Its report for us is three numbers: coverage (questions answered), quality among the
    answered, and the share of answers given out with an unsupported claim.

**Small models close the gap mainly by training.** LongPAS (2601.12465, checked), an RL method,
lifts Qwen3-4B on FRAMES from 46.81 to 64.90, against GPT-5-Nano's 73.54. That is out of reach
for us without a GPU.

## Research 4 — a fast checker that reads Russian

Julia asked for it at 21:07 UTC («Давай узкий раунд»). It is the one gap where the literature
could still change a decision: the router for aircargo under either stage 3 outcome.

**Both agree:**

- No open checker has both a measured grounding quality in Russian and a measured time on a
  CPU like ours.
- The realistic class beside the generator is a 0.1–0.3B encoder on mmBERT, which reads
  Russian. LettuceDetect v2 on mmBERT-base is in both top lists: 0.3B, Apache-2.0, RAGTruth
  example F1 74.3, a 4k-token window (its model card, checked).
- The Russian 1.5B detector AtesiT was tested only on synthetic edits of SberQuAD (98 % on its
  own 485 examples), so that evidence is weak.
- PsiloQA has no Russian. It covers 14 languages (the paper, checked).
- A threshold fitted on our judge's labels measures agreement with the judge, not truth.
  Declines are not caught by a grounding check and are counted apart.

**They differ:**

- **Codex found Horizon Hallucination Guard and ranks it first.** It comes in two sizes,
  small (141M) and base (308M), on mmBERT, under Apache-2.0. It claims 30 languages and has an
  8k window.
  - On translated HaluEval in non-English languages, HHEM-2.1-open's balanced accuracy averages
    59.1 % (Codex, from the card). The card gives Horizon-small 0.714 there; that number is
    mine from the card and is not in the report (checked).
  - Russian is not among the tested languages. Claude missed the model.
- **Codex found RusHallu-RAG** (Dialogue 2026), a Russian test with human labels.
  - It has 1,000 Russian question–answer pairs from SberQuAD and ruSciBench, with human
    labels, spans and six error types (the repository, checked; the data's licence is not
    stated).
  - Claude said no Russian RAG set with such labels exists besides mFAVA — wrong.
  - It gives any candidate a Russian test against human labels without our own people.
- **Claude measured the judge gap.** mFAVA's Russian F1 is 89.1 against GPT-4 labels and 65.5
  against human labels (the paper, checked). So agreement with our judge may overstate a
  checker by about 20 points.
- **Claude adds two more candidates.** One is mDeBERTa-xnli on each sentence, estimated at
  3–8 s. The other is the 4B answering one «yes / no» token with log-probabilities, estimated
  at 30–90 s against today's 81–235 s. Its times come from parameter counts; nothing is
  measured.

**What it gives the plan (mine):**

- If stage 3 ends in C, or in a B that costs minutes, there is now a concrete offline test.
- Three encoders would be scored on saved answers, with no new generation:
  - Horizon-small;
  - LettuceDetect v2 mmBERT-base;
  - mDeBERTa-xnli.
- Each would be scored three ways:
  - against RusHallu-RAG's human labels;
  - against our judge's claim labels on the 100 aircargo answers;
  - on the English bases.
- Their CPU time would be measured on the Mac after the signal run.
- A new signal outside the frozen signal plan needs her word.

## Research 5 — the best local generator for this machine

Julia asked for it at 21:28 UTC. It prepares her model decision (`PLAN.md` §9: «Смена модели —
явное решение Юли с числами»); it decides nothing.

**Both agree:**

- **No candidate is shown to beat Qwen3-4B-Instruct-2507.** None that fits in 8 GB has a
  same-protocol comparison with it that it wins by a margin. None has a Russian number on
  answering from given documents. Neither report sees grounds to swap now and measure
  everything again.
- **Pilot first Qwen3.5-4B and Gemma 4 E2B**, the same two in both lists.
- **The pilot:**
  - 20 saved questions per dataset, 80 in all;
  - each candidate paired with the baseline on the same saved context;
  - judged by our judge.
  - Codex's time is 16.7–20 h of Mac for the baseline and two candidates; Claude's is
    20–30 h.
  - Codex adds a feasibility check first: the GGUF loads, thinking is off, `[N]` citations
    come out, and the memory beside the retrieval models.
- The loss of Q4_K_M against Q5 / Q8 on grounded tasks is not measured anywhere («не
  найдено» in both).
- Trust-Align's readers improve English citations and declines. Russian and Q4 are not known.

**They differ:**

- **Qwen3.5-4B's speed: Claude's reading holds.**
  - Claude says it is slower than ours on a CPU: prompt reading ×0.91, generation ×0.79. The
    source is a comment in llama.cpp issue #22001 on a 20-thread CPU (checked).
  - Codex sets a conditional ≈155 s beside our whole answer of 250–300 s. That 155 s leaves
    out the rerank and the scoring call, and it takes 2.85 tokens/s from a slower laptop.
  - The same formula with our own 4.3 tokens/s gives the baseline ≈125 s (67 + 250 / 4.3).
    So the arithmetic says slower too.
  - The brief did not give our 4.3 tokens/s. That omission is mine.
- **Gemma 4: Claude found a quality number.** It is from an ESG RAG study (arXiv 2609.15242,
  table III, checked).
  - Faithfulness: E2B 0.784 and E4B 0.796, against qwen3:4b-instruct's 0.719.
  - Factual correctness: 0.423 and 0.405, against 0.449.
  - It used 100 synthetic English questions with top-1 retrieval. The judge was
    qwen3:4b-instruct, and the paper itself flags the risk of self-preference.
  - Codex had no quality number for Gemma 4.
  - Claude adds a risk: Gemma-3-4B answers 67 % of requests on Vectara's board, and we
    already over-decline on one dataset (not checked).
- **Gemma 4 E2B's speed: Codex found a measurement.**
  - On an i7-10700 with 8 threads it reads prompts at 96.2 tokens/s and generates 18.2
    tokens/s (Q4_K_M). Qwen3.5-4B there gets 44.0 and 10.3 (checked).
  - That machine has no Qwen3-4B row. Its file is 3.1–3.4 GB against our 2.5 GB.
- **Third place differs.**
  - Claude: RuadaptQwen3-4B, our model with a Russian tokenizer. Its authors claim up to 2×
    on Russian text and publish no quality numbers.
  - Claude: OCC-RAG-1.7B (MIT, tagged English and Russian; the card, checked).
    - It beats Qwen3-4B with thinking on context conflicts (ConFiQA 81.4 against 74.1) and on
      declines (MuSiQue-Un 87.2 against 84.0).
    - It loses on HotpotQA (60.9 against 67.1).
    - It writes its own five-section format, so our `[N]` prompt does not fit it.
  - Codex: LFM2.5-2.6B, a 1.67 GB file with Russian claimed. Its LFM Open License 1.0 asks
    for an agreement above $10M of yearly revenue. Then Qwen3.5-2B and Granite-4.2-3B.
- **Claude's calculation: generation runs slower than the hardware allows.** By memory
  bandwidth an answer should take about 100 s, not 250–300 s. If that holds, a faster runtime
  helps any model more than a swap; research 6 asks exactly this.
- **The pilot's pass rule.** Codex proposes at least 8 net extra good answers of 80. Claude
  proposes a sign test written in advance. Mine: 8 net is a screen, not proof. A sign test
  gives p ≈ 0.008 at 8 against 0, but p ≈ 0.12 at 14 against 6.

**What it gives the plan (mine):**

- No model swap is proposed now. The pilot is ready if Julia wants one. It runs in three
  steps:
  - a feasibility check of Qwen3.5-4B and Gemma 4 E2B in Ollama 0.33.2;
  - 80 paired answers each on saved contexts after stage 3, ≈20 h of Mac;
  - the judge.
- The speed question comes first, and it is research 6's. The answer helps the present model
  and any later one.

## How good the two reports are

Checked on 2026-10-25 against the primary sources. The nineteen claims were chosen where the
reports disagree or where a proposal leans on them, so the sample is small and not random.

| Claim | Report | Source says | Verdict |
|---|---|---|---|
| MultiHop-RAG's Hits@K counts any one gold fact | Codex 1: any one; Claude 1: the share | `retrieval_evaluate.py`: any one | Codex right; Claude wrong, and its «we lag» rested on it |
| Trust-Align's 1.5 % → 99 % answer rate | Claude 2: a prompt effect | ICL against FRONT, a trained model | Claude wrong; its declines option rested on it |
| ReClaim's training-free prompt: CAS 54.7 → 77.7, EM recall 55.2 → 50.7, best-of-4 79.1 / 55.3 | Codex 2 | table 2, the same | exact |
| Llama-3.1-8B on MultiHop-RAG: 92.16 / 96.01 / 67.02, HippoRAG2 70.27 | Codex 1 | 2502.11371 table 2, the same | exact |
| AgenticRAG on WixQA: .94 Simulated, .96 ExpertWritten, GPT-5-mini | Codex 1 | the same numbers; the generator is named for ExpertWritten only | exact numbers, one attribution stretched |
| Multi-Meta-RAG's Hits@4 0.77–0.79 | Codex 1 | 0.7672 and 0.792 | exact |
| The recomputed voyage-02 MAP@10 | Codex 1: .2718 | 0.2619 (v2, table 2) | conclusion right, number wrong |
| LettuceDetect v2 mmBERT-base: 0.3B, Apache-2.0, RAGTruth 74.3; «trained on PsiloQA» | Claude 4 | the card: the same numbers; trained on KRLabs' own sets, PsiloQA only for evaluation | numbers exact, one attribution stretched |
| PsiloQA: 14 languages, no Russian | Claude 4, Codex 4 | the paper, the same | exact |
| mFAVA, Russian F1 89.1 (GPT-4 labels) against 65.5 (human) | Claude 4 | table 3, the same | exact |
| Horizon Hallucination Guard: 141M, mmBERT, Apache-2.0; HHEM-2.1-open 59.1 % on non-English HaluEval; «RU in the metadata» | Codex 4 | the card: the same numbers (Horizon-small 0.714 there); Russian not among the tested languages | numbers exact; Claude 4 missed it |
| RusHallu-RAG: 1,000 Russian pairs, human span labels | Codex 4 | the repository, the same | exact; Claude 4 said no such set exists |
| Qwen3.5-4B against Qwen3-4B on a CPU: prompt ×0.91, generation ×0.79 | Claude 5 | llama.cpp #22001, a 20-thread CPU comment: 192.59 / 212.71 and 21.10 / 26.64 (the issue's own table is an iGPU) | exact |
| i7-10700, 8 threads: Qwen3.5-4B 44.0 / 10.3, Gemma 4 E2B 96.2 / 18.2, its QAT Q4_0 93.2 / 19.2 tokens/s | Codex 5 | `local-llm-lab` `reports/cpu.md`, June 2026, the same; no Qwen3-4B row | exact; the ≈155 s set beside our whole answer misleads |
| ESG RAG: faithfulness 0.719 / 0.796 / 0.784, correctness 0.449 / 0.405 / 0.423 (qwen3-4b-instruct, gemma4 e4b, e2b) | Claude 5 | 2609.15242 table III, the same; judge qwen3:4b-instruct | exact; Codex 5 missed it |
| OCC-RAG-1.7B: MIT, en and ru, ConFiQA 81.4, MuSiQue-Un 87.2 | Claude 5 | the card, the same; Qwen3-4B with thinking 74.1 / 84.0, HotpotQA 60.9 against 67.1 | exact where checked |
| Little Brains: Qwen3-4B Q5_K_M 0.71 / 0.80, Qwen3-8B 0.72 / 0.83, GPT-5-mini 0.73 / 0.89; CPU, 16 GB, context given | Claude 3 | 2606.30062 table 3, the same | exact; Codex 3 missed the paper |
| Airbnb's A/B: hard escalation 5.60 → 3.08 %, handoff 8.56 → 8.20 % | Codex 3 | 2609.05758 §6.3, the same | exact |
| LongPAS: Qwen3-4B FRAMES 46.81 → 64.90, GPT-5-Nano 73.54; an RL method | Codex 3 | 2601.12465 table 1, the same | exact |

**Links:**

- Codex: all 198 links open (research 1–5).
- Claude: 214 of 221 open (research 1–5). One is a 404 (an ACL Anthology preview path), one
  site refuses scripts (406), and four are blocked (403 or 429), which does not make them
  dead. One more is cut by the checker at a bracket in the address; the page opens.

**Reading (mine):**

- **Codex (`gpt-6-astra`, `xhigh`) is the more reliable one on the facts a decision turns on.**
  Both errors that drove a wrong conclusion were Claude's, and Codex had both right. Codex's
  own slips were in secondary details.
- **Codex is the more careful one.**
  - It marks every interpretation and every number from our brief.
  - It says «не найдено» and what it searched, rather than give an estimate.
  - Its research 2 ranks for both stage 3 outcomes and orders the measurements much as
    `PLAN.md` does.
- **Codex's weak side is use.**
  - It breaks the size contract: 35k, 34k, 35k, 29k and 30k characters against ≤ ~25k.
  - It is dense, with many English terms.
  - It often finds no CPU cost.
  - It took 18–24 minutes a run against Claude's 6–15.
  - Its research 1 suggests blind human labelling of our judge. The brief asked about
    agreement with people and did not state D11, so this is not a breach, but it does not
    apply to us.
- **Claude's side is breadth and concreteness.**
  - It gave more sources in research 2: 56 against 32.
  - It estimated costs on our hardware.
  - Its research 3 found the one Russian CPU benchmark of a model like ours, which Codex
    missed; its research 4 found the 20-point gap between judge and human labels.
- **Codex's research 3 read our failures right; Claude's did not.** Claude's put the loss in
  retrieval, against our judge's rows.
- **Research 5 turns it round.** Claude found the one quality number for Gemma 4 and read
  Qwen3.5-4B's speed right, and Codex's time estimate misleads. The fault is partly the
  brief's, which left out our generation speed.
- **Research 4 repeats the pattern.** Codex found the two items a decision turns on — the
  multilingual checker with numbers and the Russian human-labelled test — and Claude missed
  both, saying the test does not exist.
- **Where they conflict, the source decides.** Codex was right the first three times a fact
  conflicted, Claude the fourth (Qwen3.5-4B's speed); one check per conflict costs a minute.

## What it means — a proposal for Julia's decision, not a plan

Every item is universal — no dictionaries; any corpus and language.

| # | Step | Place in `PLAN.md` | Counts as | Needs her word |
|---|---|---|---|---|
| 1 | **Measure by the published rules, no model call:** MultiHop-RAG's Hits@K and MAP@10 by the official script; the decline matrix and the CRAG-style score from M1/M2; Codex's three numbers (coverage, quality among the answered, unsupported answers given out). MultiHop-RAG needs the top-K texts in the stage 2 retrieval records, or a retrieval-only rerun on the Mac. | «Параллельно, без Mac»: processing of records | rule (c) once published | no |
| 2 | **Judge metrics that make us comparable:** WixQA's own Context Recall and Factuality prompts (~200 calls); nugget recall: ~100 calls a base to split the references, then ~2 an answer — ≈ 1,200 calls for four bases, ≈ 0.12 of a weekly window at §4.4's rate | judge, from the laptop | rule (c) | the judge budget beyond §4.4 |
| 3 | **Generation:** an evidence-first answer in the same call, with an answered / partial / declined status (Codex; ReClaim's measured gain), or Claude's second pass for declines only. Measured paired on a fixed context on WixQA's and ConditionalQA's open parts (§4.2: not the locked parts), by claim faithfulness, nugget recall and declines together | a prompt change — §9 allows only stage 1's fixes, V4 and stage 4's levers | rule (c); (a) if adopted | yes: an amendment |
| 4 | **The router:** stage 3's outcome on the Mac decides. Outcome B: how to fit a check of minutes into the chat is hers. Outcome C, or a B too slow: research 4's offline test of three encoder checkers on the saved answers, against RusHallu-RAG's human labels and our judge's, with their time on the Mac | stage 3, step 3; a new signal is outside the frozen signal plan | (c) for the test, (a) when wired | yes for B, for the test and for any new model |
| 5 | **Shorter context:** research 3's context pruning supports stage 4's «Промпт короче» lever | stage 4, step 4 | (a), (c) | no: already planned |
| 6 | **Retrieval:** one query rewrite or decomposition, after item 1 shows the real gap. BGE-M3's multi-vector mode would change the vector store (ADR 0007) and the embedder | a new mechanism — stage 7 takes only code that exists; the vector store and the embedder are frozen | (c), then (a) | yes |
| 6a | **Another generator** (research 5): no candidate is shown to beat the 4B. If she wants a pilot: Qwen3.5-4B and Gemma 4 E2B, 80 paired answers each on saved contexts (≈ 20 h of Mac), after a feasibility check; then a reader trained for grounding and refusal (Trust-Align, OCC-RAG; English-tested). Coverage beside quality | a model swap — §9: «явное решение Юли с числами» | (c) | yes |
| 7 | **Not worth our hardware:** graph-RAG frameworks (also ADR 0001), long context, RL training, large reasoning rerankers (a reranker swap is hers anyway), semantic entropy | stop-list §9 | — | — |

Research 6 (speed levers that keep the models, for stage 4) and research 7 (faster retrieval
models that read Russian) run on Codex alone, one after the other, at Julia's word of
21:46 UTC («ресурс кодекс можно потратить - разрешаю, реши сам»). Their reports are added
here when they end.

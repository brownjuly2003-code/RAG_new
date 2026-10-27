# Session handoff 2026-10-26 — four items under Julia's «да», the widget running on the Mac

Session `d00d6821`, 2026-10-26 02:04 UTC – ≈ 17:15 UTC. The laptop's clock and the commit dates
are EDT (UTC−4); the Mac's clock is UTC+3; the logs write UTC. Previous handoff:
[stage 2b closed, stage 3's signals running](session-handoff-2026-10-25-stage3-signals-running.md).

## Read this first

- **A measurement is running on the Mac with no session watching it.** It is stage 3's step 4,
  the widget on the 4B ([spec](../specs/widget-4b.md)). `widget.sh` started at 15:13:16 UTC
  under `nohup`; it runs one production request, then ten development requests.
  - The production request ended at 15:25:54: HTTP 200, route `human`, a ticket,
    quality_score 50, 682.7 s. Its `api.log` line `[evaluate] boundary=start …
    independent=False require=True` says R1 is likely confirmed. The record decides, not this
    line.
  - The ten development requests started at 15:26:20. #1 took 1,464 s and routed `human` with a
    ticket. #2 took 2,356 s and routed `error_escalation` with a ticket (see
    [the finding](#a-finding-on-the-way-the-widgets-call-budget)). #3 began at about 16:30.
  - At 16:51 UTC other projects held the Mac's load at 15–18, so a request takes 25–40 min and
    the chain should end at about **20:30–22:00 UTC**. The log line `CHAIN_DONE` or
    `CHAIN_STOPPED` marks the end ([Next actions](#next-actions), step 1).
  - The stop rule (spec, «Order and stop»): a request with no delivered response — an HTTP
    error, a `timeout` route, the client cap of 4,200 s — stops the series. A delivered
    `error_escalation` does not.
- **While it measures:** no `sync.py`, no `remote.py`, no tests and no downloads on the Mac.
  Never stop it, and never stop another project's process.
- **Uncommitted work, on the laptop only** (and in the local branch `wip/encoder-amend-1`, see
  [State now](#state-now)): Amendment 1 of the encoder test — the spec's text, the tool
  `reports/encoder-checkers/tools/encoder_checkers_amend.py` and its test
  `tests/test_encoder_checkers_amend.py` — plus `tests/test_widget_4b_artifact.py`, which waits
  for the widget's record. **The amendment's tests have not run yet**: the Mac was measuring.
- **One yes/no for Julia is still open, and she has not been asked yet.** Stage 3b's judge
  needs 620 requests, ≈ $116–130 and ≈ 8–10 h ([V5 spec](../specs/answer-prompt-v5.md),
  «The judge»). PLAN.md says ≈ 460 because it counted only the four plans of the external
  bases. Ask her after the V5 chain has launched and before the judge's first request.
- **Nothing was pushed in this session.** `3ef8b54`…`47e2d71` (10 commits) are local. A push
  needs her word. Before it: the whole Mac suite, mypy, bandit, pip-audit, DEP-01 and the site
  build, as the memory note on CI parity lists them.

## Why this session's work exists

On 2026-10-26 the stage-3 signal record came out as outcome C: no cheap signal tells a bad
answer from a good one on V4's 100 aircargo answers well enough to route it. I listed five
decisions for her word. She answered with fear: the task looks impossible. I answered that the
task is doable, and that only a fast and accurate *automatic* bad-answer detector is ruled out
on this hardware. Then I proposed four items, and she said «да»:

1. A line under every answer, «Ответ составлен автоматически и может ошибаться», beside
   «Передать оператору», in the chat and the widget, with an E2E test. **Done:** `60dfd90`.
2. Two free checks. The no-reranker point is **done** (`f7492d5`, `eb4cc17`): the reranker
   stays, because without it the expanded five hold gold in 121 of 250 questions, not 141.
   Stage 3's step 4, R1 on ten widget answers, is **running**. I had called step 4 «минуты
   работы Mac»; that was wrong. It takes hours, and the spec's forecast says 2.5–3 h. Tell her
   this correction in the next message.
3. Stage 3b, the evidence-first prompt V5: **registered** (`47e2d71`), not launched. It needs
   ≈ 10.5 h of the Mac for the answers, then the judge.
4. The test of three encoder checkers that read Russian: **done** (`fa73683`, `4bd2399`). All
   three read *in between* and none is *worth wiring*
   ([record](../evidence/encoder-checkers-record.md)). H came closest: 10 of 17 caught while
   marking 8 of 63.

Not doing for now (deferred, not cancelled): stage 2 for S3 (the third signal of the handover plan), the generator pilot, query
decomposition, the judge budget.

## Julia's words in this session (UTC)

- 02:04 «продолжи доработку» — by the previous handoff: analyse the research, amend PLAN.md,
  then the signal run's record. Done: `3ef8b54`, coverage `6310a44`/`f78857c`, then the record
  `8a69273`.
- 08:21 «про мое слово. у ощущение ужаса((( задаче не выполнима(((» — her answer to my five
  decisions. I answered as above and asked «Делаю так?».
- 08:25 «да».
- 08:51 «продолжи работу»; 09:02, 09:26 and 09:40 «продолжи».
- 15:01, mid-turn: «погоди, энкодеры некачественные??? вероятно стоит искать качественные?».
  I answered that they are not poor: they are small, and they fall short of a strict bar
  registered in advance. Then I committed to Amendment 1: B, the larger sibling of H, and a
  second read of all four on V5's fresh answers.
- 16:43 «напиши астре - нужно использовать хром, а не яндекс браузер», then «не туда написала,
  не реагируй на фразу выше». It was meant for another session; nothing was done.
- 16:50 «сколько времени нужно на остаток прогона? можно закрыть эту сессию?» — I answered
  ≈ 4–5 h, and yes, after this handoff.

## My choices, not hers

- **Amendment 1** is my reading of her 15:01 question; she has not seen its text. It adds two
  parts:
  - Part 1: B = `Horizon-Labs/hallucination-guard-base` at `f0aaaac7`, the larger sibling, as
    the encoder research's next pick.
  - Part 2: the four frozen thresholds read once on V5's 100 aircargo answers. That read
    decides, because the record's weak link is how the threshold transfers: H's AUROC was
    0.805 on aircargo but 0.646 and 0.571 on the calibration answers its threshold was chosen
    on.
  - Rejected: LFM2.5-Encoder-350M (no Russian, its own licence) and LettuceDetect v2 on Qwen
    2B (no Russian, tens of seconds an answer).
- **The rules of the amendment:**
  - An empty V5 answer is a target, as the judge export grades it bad. A missing verdict
    leaves the answer unclassed: scored, counted apart.
  - A fresh *worth wiring* over a V4 read that is useless or `NOT_EVIDENCE` is *held back* and
    counts as in between.
  - Part 2 is `NOT_EVIDENCE` with nothing scored when V5's aircargo answers are not whole or
    its judge plan is not counted.
- **The order on the Mac:** the widget, then B's download, then the V5 chain (≈ 10.5 h). B's
  Part 1 runs on the Mac while V5's judge runs on the laptop. Part 2 comes after the aircargo
  judge record.
- **When to ask about the judge's money:** after the V5 chain launches, before the judge
  starts.

## What happened

| UTC | What |
|---|---|
| 02:48 | `3ef8b54` — the seven research runs analysed; PLAN.md amended before the record |
| 02:53, 03:06 | `6310a44`, `f78857c` — coverage beside quality: spec, then the record |
| 05:58 | `8a69273` — stage 3's signals on V4's 100 aircargo answers: outcome C |
| 09:56 | `60dfd90` — the handover line under every answer (item 1), E2E |
| 10:27, 10:33 | `f7492d5`, `eb4cc17` — the no-reranker point: the reranker earns its place |
| 11:20 | `fa73683` — the three encoder checkers registered before the first call |
| 15:01 | her encoder question; Amendment 1 drafted, then read cold by a subagent (11 findings, no blocker), all fixed |
| 15:12 | `4bd2399` — the encoder record: H, L and N all in between |
| 15:12 | `47e2d71` — V5's replay (3b) and the widget (step 4) registered before the first request |
| 15:13 | the widget chain launched on the Mac |
| 15:25 | the production request done (R1 likely) |
| 16:30 | dev #2 ends in `error_escalation` |

Before `47e2d71`, all V4 parity checks passed on the stand: V4's 300 prompts were rebuilt byte
for byte. V5 keeps the context unchanged on 81 WixQA, 83 ConditionalQA and 36 aircargo
questions, as the spec records.

## A finding on the way: the widget's call budget

The widget's per-request budget of model calls (`llm/request_budget.py`, `max_calls`) runs out
on the 4B whenever a retry is needed. In dev #1 it ran out at the claim check:
`[verify_facts] verifier LLM error: LLMBudgetExceeded`. In dev #2 it ran out at the generation of
the retried pass: `Необработанное исключение в узле 'generate': LLM request budget exceeded
(max_calls)`, then `Pipeline error escalation: node='generate'`. The customer still gets a
delivered response with a ticket. Still, a retry that cannot finish is a product defect. The
record's `model_calls` and `passes` per request show its cost; `api.log` shows how often. Name it in the
capsule; any fix is a slice of its own.

## State now

- **The Mac** (`deproject-mac`, shared). The stand is `/Users/julia/RAG_new_chat_4f48fed`
  (`$S`), CODE_SHA `4f48fed`.
  - Widget tools: `$S/chatlive/`, their SHA-256 matching the commit.
  - Widget runs: `$S/chatlive/runs/` — `widget.log`, `widget-production/`,
    `widget-development/` (with `progress.log`), and the supervisor logs.
  - V5: `$S/v5/`, holding `replay.py`, `qa_prompt_v5.txt`, `v5_chain.sh`, `stand_env.py` and
    the precheck files.
  - Encoders: models in `/Users/julia/RAG_new_encoder_models` (HF cache), the work folder
    `/Users/julia/RAG_new_encoder_work` (with `download_b.py`, not yet run), output in
    `/Users/julia/RAG_new_encoder_out`, a separate `transformers` in
    `/Users/julia/RAG_new_encoder_site`.
  - The ML venv: `/Users/julia/RAG_Support_Assistant/.venv/bin/python`.
  - The gate checkout: `/Users/julia/RAG_new_mf_gate`, last synced at `fa73683`. It lacks
    `47e2d71`'s widget and V5 tools until the next `sync.py`.
- **The laptop.** `master` is at `47e2d71`, ten commits ahead of `origin/master`.
  - Uncommitted: `docs/specs/encoder-checkers.md`, `encoder_checkers_amend.py`,
    `tests/test_encoder_checkers_amend.py`, `tests/test_widget_4b_artifact.py`, this file, its
    pointer lines in `CURRENT_STATE.md` and `docs/README.md`, and `.tmp/v4/docs_check.py`'s
    file list (git-ignored).
  - Never commit `demo/phase-e-raw.webm` or `reports/ask100/`.
  - Backup: the local branch `wip/encoder-amend-1`, built through a temporary index; it is not
    pushed. Restore with `git diff --name-only wip/encoder-amend-1^ wip/encoder-amend-1 | xargs git
    restore --source=wip/encoder-amend-1 --worktree --`. Delete the branch once both commits below
    have landed.
- **The amendment's spec holds two placeholders:** `TOOL_SHA` and `TEST_SHA`, in Amendment 1's
  «Records» bullet. Fill them before the commit.

## Next actions

`$PY` below is the laptop's `C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe`; `$MPY`
the Mac's ML venv `/Users/julia/RAG_Support_Assistant/.venv/bin/python`, written out in full
inside an `ssh` command. A *key* is one of V5's three bases: `wixqa`, `conditionalqa`,
`aircargo`. `remote.py` tests what the last `sync.py` shipped, so every Mac step that reads a
file changed on the laptop starts with `sync.py`.

1. **The widget chain.**
   ```
   ssh deproject-mac 'grep "^20" /Users/julia/RAG_new_chat_4f48fed/chatlive/runs/widget.log; grep "^CASE" /Users/julia/RAG_new_chat_4f48fed/chatlive/runs/widget-development/progress.log'
   ```
   If `CHAIN_DONE` or `CHAIN_STOPPED` is there, go on. If not, wait with a Monitor until-loop
   on that log.
2. **Sync:** `$PY -I D:/RAG_new/.tmp/mf-mac/sync.py`.
3. **The widget's rows, then its record:**
   ```
   ssh deproject-mac 'cd /Users/julia/RAG_new_mf_gate && /Users/julia/RAG_Support_Assistant/.venv/bin/python -I reports/widget-4b/tools/widget_record.py rows /Users/julia/RAG_new_chat_4f48fed/chatlive/runs /Users/julia/RAG_new_widget_out'
   ```
   Create `reports/widget-4b/4f48fed/` on the laptop, `scp` the Mac's
   `/Users/julia/RAG_new_widget_out/rows.jsonl` into it, then run
   `$PY -I reports/widget-4b/tools/widget_record.py record reports/widget-4b/4f48fed`.
   The rows hold no budget flag. Count the call-budget finding from each run's `api.log` with
   the two strings quoted [above](#a-finding-on-the-way-the-widgets-call-budget).
4. **The capsule** `docs/evidence/widget-4b-record.md`. `tests/test_widget_4b_artifact.py` pins
   three things in it:
   - the question table's lines, with the seven columns `question_rows()` writes;
   - `**R1: <reading>.**` and `**R2: <reading>.**`;
   - «X of Y passes», the grader's defects out of all passes.

   Then add one row to `EVIDENCE_INDEX.md`, and the lines in `CURRENT_STATE.md` (150-line cap;
   edit in place), `ROADMAP.md` and `PLAN.md` stage 3. Name the call-budget finding. Add the
   capsule to `CHANGED` in `.tmp/v4/docs_check.py`.
5. **The amendment.**
   - Run `ruff format` and `ruff check` on the tool and its test first.
   - Then put the tool's SHA-256 in place of `TOOL_SHA`, and the test's SHA-256, computed last,
     in place of `TEST_SHA`. The test checks that the tool's SHA is in the spec. No test checks
     `TEST_SHA`.
   - Any later edit of either file, a fix after step 6 included, means computing both again.
   - Then run `$PY -I -X utf8 .tmp/v4/docs_check.py`.
6. **The Mac gate.** Run `$PY -I D:/RAG_new/.tmp/mf-mac/sync.py` first, then:
   ```
   $PY -I .tmp/mf-mac/remote.py --site pytest tests/test_widget_4b_artifact.py tests/test_widget_4b.py tests/test_encoder_checkers_amend.py tests/test_encoder_checkers.py tests/test_encoder_checkers_artifact.py tests/test_docs_hygiene.py tests/test_docs_quality.py tests/test_docs_publication.py -q -p no:schemathesis -p no:cacheprovider --basetemp=.tmp/pytest-widget --tb=short
   ```
   Sync again after any fix, before the next run.
7. **Two commits.**
   - First the widget evidence: rows, record, capsule, index, status files and
     `test_widget_4b_artifact.py`. It also takes this handoff file and its pointer lines in
     `CURRENT_STATE.md` and `docs/README.md`.
   - Then Amendment 1: the spec, the tool and the test.
   - The amendment must be committed **before B's first call and before step 9**. The spec says
     «before V5's first aircargo answer».
8. **B's download:**
   ```
   ssh deproject-mac '/Users/julia/RAG_Support_Assistant/.venv/bin/python /Users/julia/RAG_new_encoder_work/download_b.py > /Users/julia/RAG_new_encoder_work/download_b.log 2>&1'
   ```
   If `huggingface_hub` is missing, put `PYTHONPATH=/Users/julia/RAG_new_encoder_site` in
   front, as the three checkers' download did. Then check the files against the card:
   `model.safetensors` is 1,230,141,424 B with SHA `f8ac683b…`; `onnx/model.onnx` is
   1,230,730,152 B with SHA `b9847954…`.
9. **The V5 chain, launched once:**
   ```
   ssh deproject-mac "nohup sh /Users/julia/RAG_new_chat_4f48fed/v5/v5_chain.sh >> /Users/julia/RAG_new_chat_4f48fed/v5/v5-chain.out 2>&1 </dev/null &"
   ```
   Use `>>`: `replay run` appends its own output to `v5-chain.out`.
   - Its log is `$S/v5/v5-chain.log`, ending with `CHAIN_DONE` or `CHAIN_STOP …`.
   - Before each key it waits up to 6 h (`IDLE_WAIT=21600`) for an idle Mac: the 5-minute load
     below 2; no pytest, llama-server, supervisor or replay; Ollama holding no model.
   - **Running it again resumes a key only after «not idle» or a model error (exit 7).** After
     exit 3 (a V4 prompt not rebuilt), exit 4 (an answer past 1,200 s: the spec stops that key)
     or exit 6, do not run it again; read the spec first.
   - A key past 3 × its forecast, ≈ 11 h, is stopped by the session:
     `touch /Users/julia/RAG_new_chat_4f48fed/v5/runs/v5-<key>.stop`. The file
     `$S/v5/v5-chain.stop` stops the chain before its next key.
10. **Message Julia, in Russian:** the reranker stays; the encoders came out in between, and
    Amendment 1 explains why B and a fresh read; the widget's R1 and the call-budget finding;
    the correction «hours, not minutes»; 3b launched. Then the one yes/no: the judge's 620
    requests, ≈ $116–130.
11. **After the V5 chain, follow the V5 spec's order.**
    - For each key: `replay.py summary KEY V4_RUNS OUT RECORDS`, then copy the runs to
      `D:/RAG_new_stage2_private/v5/`. Write the judge plans and commit their SHA-256 before the
      first grade.
    - Then the judge (after her yes), the bridges and the export. V4's judge driver and its
      limits are described in [the V4 handoff](session-handoff-2026-10-24-v4-running.md).
    - After each key's judge, run the harm check: `v5_record.py STAND_DIR OUT --keys <judged>`
      (spec, «Harm stops early»). Then `v5_record.py`, the capsule and the index.
    - **During the judge, B's Part 1 on the Mac.** Use the gate checkout, synced to the
      amendment's commit. No `sync.py` or `remote.py` while B scores, because it runs in that
      checkout. Each command runs in the background, one at a time:
      ```
      ssh deproject-mac "cd /Users/julia/RAG_new_mf_gate && nohup /Users/julia/RAG_Support_Assistant/.venv/bin/python -I reports/encoder-checkers/tools/encoder_checkers_amend.py parity /Users/julia/RAG_new_encoder_out/base >> /Users/julia/RAG_new_encoder_work/base.log 2>&1 </dev/null &"
      ```
      Then the same with `score` in place of `parity` (≈ 200 min, stopped at 600). Copy
      `parity-B.json` and `scores-B.jsonl` to `reports/encoder-checkers/4f48fed-base/`. Then on
      the laptop run `encoder_checkers_amend.py base reports/encoder-checkers/4f48fed-base`, and
      commit Part 1.
    - **After Part 1's record and the aircargo judge's record are committed,** run `sync.py`
      first. Unsynced, `fresh` finds no V5 records and stops with a false «Part 2 is
      NOT_EVIDENCE». Then run `fresh H`, `fresh L`, `fresh N` and `fresh B` with
      `/Users/julia/RAG_new_encoder_out/fresh`, in that order, each its own background process
      like the one above. Copy the four `fresh-<checker>.jsonl` to
      `reports/encoder-checkers/4f48fed-fresh/`. Then on the laptop run
      `encoder_checkers_amend.py confirm reports/encoder-checkers/4f48fed-fresh <V5's aircargo judge plan.json in D:/RAG_new_stage2_private/v5/>`
      and commit. `confirm` refuses when a checker's file is missing.

## Do not

- Stop the widget run or anything of another project; run tests, syncs or downloads on the
  Mac while it measures.
- Call B before Amendment 1 is committed, or change the registered `encoder_checkers.py`: the
  amendment checks its SHA-256, `fa226d38…`.
- Push, start MyFlow, or bring in any other model than Codex (profile cw) as a second opinion.
- Print `env.json` or the production secrets of the widget run. The record holds their names
  only.
- Put a question, document or answer text of an external base into a committed row.

## Lessons

- **A forecast in a proposal is checked against the spec's numbers before it is said.** I
  called step 4 «минуты» before writing its spec; the spec's own sum came to 2.5–3 h.
- **A cold read before the first call pays.** It found 11 issues in Amendment 1, none a blocker.
  Without the fixes, an orphan row after a crash would have locked Part 1 forever, an empty
  answer would have crashed Part 2, and nothing would have proved that the scored answer was
  the judged one.
- **The shared Mac's load is not ours to plan around.** It was 15–18 at 16:51 UTC; it stretched
  the widget's requests and can time out V5's idle wait.

## Glossary

- **R1:** in production the judge must be independent of the answering model; the 4B has no
  independent judge; so the evaluation fails closed and the widget routes `human`.
- **R2:** the extractor finds nothing, so the widget reports a knowledge gap.
- **H, L, N, B:**
  - H — `Horizon-Labs/hallucination-guard-small`;
  - L — `KRLabsOrg/lettucedect-v2-mmbert-base`;
  - N — `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`;
  - B — `Horizon-Labs/hallucination-guard-base`.
- ***Worth wiring / in between / useless*:** the handover plan's frozen reading of a signal.
  `NOT_EVIDENCE` means too few classed answers, or a run that is not whole.
- ***Held back*:** a fresh *worth wiring* whose V4 read does not count.
- **V4, V5:** the adopted answer prompt (`4f48fed`) and the evidence-first candidate of
  stage 3b.
- **Outcome C:** stage 3 ended with no automatic router, so a person decides.

## Verification

- `ruff format` and `ruff check` pass on the amendment's tool and test. The docs check (`.tmp/v4/docs_check.py`, its
  file list extended to this session's documents) printed `PROBLEMS: none`. The tests have **not** run: their first run is step 6.
- The widget's state was read from `widget.log`, `progress.log` and `api.log` at 16:51 UTC.
- The commit times are from `git log --date=iso`. Julia's times are from the session
  transcript; the 15:01 message from its queue row.

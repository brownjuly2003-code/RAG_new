# Session handoff — 2026-10-18 — stage 1 closed, stage 2 next

Session `0417abf7`, 2026-10-18 11:57 UTC to about 16:00 UTC, Claude Opus 5.5 alone (D12), across
two context compactions (14:02, 15:02). **Times are UTC**, as the Mac's records are; the laptop's
clock is UTC−4 (this session's commits read 08:34–10:55). The session before:
[stage 1 — fixes committed, the new index generation building](session-handoff-2026-10-18-stage1.md).
Its stand, stop and rerun procedures («Next actions» 1–2), «How to test on the Mac», lessons and
glossary still hold; this file adds what changed and what comes next.

**Pushed:** 27 commits `99cd15f..b0bd87c` at 14:58, at Julia's «пуш»; the commit of this file at
about 15:45, at her «да». Nothing is left unpushed.

## Julia's messages

| UTC | Her words | What followed |
|---|---|---|
| 11:59–12:06 | four questions about «Your login expires in 2 days» after her upgrade to Max 20x | not the project: Claude Code's login on this laptop, not the subscription; `/login` renews it, the server applies the limits. My first answer wrongly tied `/login` to the new limits; the next corrected it |
| 12:06 | «вернемся к важному. К проекту. по нему шел долгий процесс по четырем базам, насколько я понимаю, - проверь, что получилось» | the second index generation was complete: built 01:05–11:06 at `e5e135a`, `guarded_unchanged` true, all 68,169 chunks open with the new header and none with «[Контекст:», chunk counts equal to the first generation's. I asked whether to launch the check after the fixes |
| 12:09 | «продолжай» | the check, stand `0892441`, prompts V2, 12:09–12:32: one criterion failed (below) |
| 12:39 | «как оптимальнее?» — to my question: fix the prompts now, or close stage 1 as is and count the share in stage 2 | my answer at 12:41: fix now — about an hour of work and 25 min of the Mac, against stage 2's 41–49 h measuring a prompt that pulls the model toward Russian, and up to 30 h of external answers measured again after a later fix. V3 (`4ca5ddd`), rerun 13:27–13:56: every criterion passed |
| 13:39 | «docs/operations/audit_fable_18_10_26.md - изучи» | an audit of the project written by another session on another model (Fable 5.1); I checked its ten findings F-1…F-10 against the repository (outcomes below) |
| 13:42 | «реши сам» — to my question whether to commit the audit | committed as written, in a commit of its own that names its author (`26e24fb`), linked from `docs/README.md` |
| 14:57 | «пуш. давай продолжим в след сессии. в след сессии все будет понятно?» | pushed at 14:58; this file answers the second half |
| ≈ 15:43 | «да» — to my «Коммит хэндоффа `7dd0e99` пока только локальный. Запушить его?» | this file's commit pushed; its push lines were amended first, so its SHA is no longer `7dd0e99` |

## What matters to understand

**Where the project is.** [`PLAN.md`](../../PLAN.md) stage 1 is closed. The chat path no longer
depends on markdown files, on Russian or on aircargo, and this is proven live on one question
per corpus. The product still has **no quality number on the customer's path**
(`/api/ask/stream`): each number in CURRENT_STATE's table comes from another path, model or
ruler. Stage 2 gives the first, on all four corpora side by side, from one code.

**How the chat works now.** Product code is `4ca5ddd`'s: only documents, records and tests
changed up to `b0bd87c`.

- Retrieval: BM25 and BGE-M3, 20 candidates each, merged by RRF (32–37 candidates in the stage-1
  records). The bge-reranker-v2-m3 on the CPU scores every merged candidate and keeps 5; parent
  expansion adds neighbouring chunks.
- Answer: Qwen3-4B-Instruct-2507 on Ollama, then self-evaluation, then suggested questions.
- Prompts are **V3** (`agent/prompts.py`): English instructions that ask for the answer in the
  language of the question. Each chunk opens with `[document › section]`, and documents are
  labelled `[N | source=…]`.
- Indexes: all four bases, aircargo too, read the **second generation** at
  `/Users/julia/RAG_new_external_s1/<base>/index/chroma`. The first generation stays untouched
  beside it.

**What the three live checks showed.** Each check put one question to each tenant, each tenant
on a fresh API. The criteria were registered in [the spec](../specs/stage1-fixes.md) before each
run: 20 + 20 candidates, rerank `ok`, 5 documents; the tenant's BM25 restore line; the answer in
the question's script; no Russian label in the prompt. The records are in
[`reports/stage1/`](../../reports/stage1/), and `tests/test_stage1_live_artifact.py` derives
every published number from them.

| Check | Stand, prompts, indexes | Result |
|---|---|---|
| before the fixes, 00:12–00:42 (previous session) | `99cd15f`, the old Russian prompts, first generation | WixQA 20 vector and 0 BM25 candidates (the restore failed: «too many SQL variables»); ConditionalQA and MultiHop-RAG answered in Russian; every prompt carried «[Документ» and «[Контекст:» |
| after, 12:09–12:32 | `0892441`, V2 (Russian instructions asking for the question's language), second generation | **failed one criterion**: MultiHop-RAG answered in Russian (347 Cyrillic letters against 65 Latin); the rest passed |
| rerun, 13:27–13:56 | `4ca5ddd`, V3, second generation | **every criterion passed** on all four tenants: BM25 restored 5,589 / 13,778 / 37,571 / 11,231 chunks; each answer in its question's script; 0 Cyrillic letters in the three external prompts (a criterion added before the rerun) |

**Why V2 failed: the lesson for stage 2.** V2 claimed «the chat answers in the question's
language». Its criteria counted the answer's letters and four prompt labels. They did not
count the prompt's own instructions, which were Russian: 608 Cyrillic letters around the
documents. V2 therefore passed on three tenants, and the MultiHop-RAG failure first read as «the
model did not obey». The audit's F-1 named the cause: on an English question the model got a
Russian instruction. V3 removed the cause, and the rerun registered one more criterion. **A
criterion must measure what the change claims, not what is easy to count**: check each criterion
of stage 2's spec against that.

**The self-score does not see the language** (F-2). The records hold three answers in the other
script; the chat's rule sent two of them `auto` (no operator offered), each self-scored 100.
S8 was therefore added to [the handover plan](../specs/handover-signal.md) as a candidate
signal: it marks an answer when fewer than half of its letters are in the question's script,
counted by Unicode ranges — no model call, no word list; it tells scripts apart, not languages.
`scripts/chat_signals.py` does not compute S8 yet; it is due before the handover plan's 1.3
(stage 3), not before stage 2.

**What a passed check proves.** One question per tenant checks the path, not quality: the hybrid
path, the restore, the labels and the language work on every corpus. Nothing about how good the
answers are.

**What else moved on V3** (observations, not criteria): self-scores ConditionalQA 40 → 80 (route
`human` → `auto`), MultiHop-RAG 100 → 20 (`auto` → `human`; its V2 answer was the Russian one);
aircargo's answer grew from 48 to 172 tokens and its time from 263 to 399 s.

**Stage 2** ([`PLAN.md`](../../PLAN.md) §5, «Этап 2»; the judge per part in «Next actions» 1):

1. aircargo, 100 answers on the customer's path: 10 batches of 10, each on a fresh API with the
   model unloaded; forecast 340 s for a batch's first question and 400 s for the others, stop
   at 3×, ≈ 11 h.
2. Retrieval without the answer model on 400 questions (100 aircargo and ≈ 100 per external
   base), ≈ 3.5 h, the rerank scores kept for stage 4.
3. The graph lane on aircargo, ≈ 1–1.5 h.
4. 300 answers on the external bases' `stage2` selections, in batches of 10, ≈ 25–33 h.
5. The record, a test that derives each number from it, and one EVIDENCE_INDEX row — **rule
   (c)**. Parts 1–4 are preparation until then.

In all about 41–49 h of the Mac and about 660 judge requests at effort `max`. **The spec comes
first**: it registers everything that must not be chosen after seeing answers — the stand, the
cases and their order, the forecasts and stop rules, what is `NOT_EVIDENCE`, the judge (id,
effort, prompt, retests, the kappa it must reach) and what each record holds.

**How to read stage 2's outcomes, and what to tell Julia:**

- **A question stops at its cap, or a batch fails.** The supervisor ends the batch at the first
  question past its cap; it and the batch's unsent questions are `NOT_EVIDENCE`. Read the batch's
  `supervisor.log` and `api.log`, then rerun the whole batch under a new label on an idle Mac;
  the record keeps both runs, and the numbers use the rerun's answers. A second stop (the rerun
  or the next batch) means the pace changed — V3's longer answers, swap: stop the part and tell
  Julia the measured times before going on.
- **The path breaks**, as stage 1 defined it: no BM25 candidates or restore line, rerank not
  `ok`, a 5xx, an empty answer. Stop: every number must come from one code, so a fix means a new
  stand and everything run before it runs again. Tell Julia first; it costs Mac hours. A
  wrong-script answer or a low self-score is measured, not a stop.
- **The Mac is busy at a batch start** (ports or Ollama not free). Find what holds it, never stop
  another project's process, and tell Julia if it is hers.
- **A part passes its whole-part cap.** Stop it; its unanswered questions are `NOT_EVIDENCE`; tell
  Julia the measured pace and a new forecast before going on.
- **The judge's retests fall below the registered kappa.** That part's judge numbers are not
  evidence; say so in the report to Julia. Do not tune the judge's prompt on the same answers: a
  changed prompt is a new registration with its own retests.
- **The judge's route fails** (a CLI update or a plugin refuses it — memory
  `safe-mode-loads-official-plugins`) or a usage window runs out: pause the judge; Mac parts go on.
- **Numbers far from phase C's** (4B 67 good / 21 partial / 12 bad) are a finding, not a stop:
  phase C judged fixed contexts, not the chat's retrieval.
- **At the end, tell her:** the first quality numbers on the customer's path, four corpora side
  by side, each with its limits and provenance; ask for the push; stage 3 (the handover signal)
  comes next, on the same 100 aircargo answers.

## Julia's decisions in force

No new decision on the project this session: only «реши сам» on the audit and «пуш». In force:
D11 (2026-10-03) — no person grades or approves anything; D12 (2026-10-04) — the session does
all the work, no other model in any role; production on the Mac (2026-10-14); Qwen3-4B
(2026-10-16); all 2026-10-17 — the one plan, fixes first, answers in the question's language,
the indexes as a new generation, external answers in stage 2 («Вариант B»). A push is hers,
asked each time.

## My choices, not hers

- **V3 before closing**, not closing on V2 and counting the share in stage 2. She asked «как
  оптимальнее?»; the reasons are in the table of her messages.
- **All four tenants rerun on V3**, not MultiHop-RAG alone: one record, one stand.
- **The rerun's added criterion**, 0 Cyrillic letters in an external prompt, registered in the
  spec by `4ca5ddd`, before the rerun.
- **The audit committed as written.** Under D12 its own checks (pip-audit, DEP-01, mypy) are not
  counted; I ran them myself before the push. Taken: F-1 (V3), F-2 (S8), F-4 (the push, on her
  word), F-5 (the judge named by id in four places of `PLAN.md`), F-6 (one writing session per
  repository, `AGENT_STATE.md`), F-7 (the dangling link in `BACKLOG.md`). Deferred: F-3 — a file
  mapping each key `scripts/universality_audit.py` prints to its outcome, with a test that fails
  on a key without one (a small preparation slice); F-10, formatting and tool details. Hers: F-8,
  F-9.
- **S8's threshold 0.5** is the audit's proposal, untuned, checked only against the 12 answers of
  the three records.

## Once Julia decides

- **F-8.** `demo/phase-e-raw.webm` (43 MB) and `reports/ask100/` (563 MB) are untracked and not
  ignored, so `sync.py` ships them to the Mac's gate checkout with every sync. Her options, as
  given: an archive outside the repository, `.gitignore`, or the Mac only. Before acting, check
  what reads them:
  `grep -rln --exclude-dir={archive,.tmp,ask100,node_modules,.git} "phase-e-raw\|reports/ask100" D:/RAG_new`.
  Then do her option, and run one `sync.py` to see the bundle shrink.
- **F-9.** `README.md` «Measured results» shows numbers of the old path (`/api/ask`, 7B/8B);
  `PLAN.md` replaces them in stage 8. My proposal: one line above the table that says so. A root
  `.md` edit, so the three docs tests follow.
- **Mac hours a day** (open since 2026-10-17, CURRENT_STATE «Open for Julia»). Until she names
  them, my proposal: tell her each part's forecast and its end in her time (UTC−4) at the
  launch, start long parts in her evening, and stop at one word from her. The accepted plan
  covers the runs (my reading).
- **GitHub billing.** Once settled, the next push starts CI; its first green run also checks what
  neither machine can — the docs-site build and the suite on the lock's exact pins. Then update
  CURRENT_STATE «CI and pushes».

## Log

| UTC | Commit or run | What |
|---|---|---|
| 12:09–12:32 | run, stand `0892441` | the check after the fixes, V2 |
| 12:34 | `cd78fbd` | its record `reports/stage1/0892441/after.json`; the spec: one criterion failed |
| 13:26 | `4ca5ddd` | V3, `agent/prompts.py` in English; a new E2E case, red on V2 at its Cyrillic assert: an English question over an English page gets a prompt without one Cyrillic letter (`tests/test_chat_chunk_context_e2e.py`); tests, the judge's prompt parser, `audit_summary.py` and the rerun's criteria follow. Whole suite 5,874 passed, 124 skipped; the browser tests 7 passed |
| 13:27–13:56 | run, stand `4ca5ddd` | the rerun |
| 13:56 | `0636ea3` | its record `reports/stage1/4ca5ddd/after.json` |
| 13:57 | `26e24fb` | the audit, as written, linked from `docs/README.md` |
| 14:35 | `96ee4e6` | stage 1 closed: `tests/test_stage1_live_artifact.py`; the spec (status, the rerun's paragraph, the forecast table's actuals); S8 in the handover plan; the evidence row; ROADMAP, CURRENT_STATE, BACKLOG, AGENT_STATE; the judge by id in PLAN |
| 14:55 | `b0bd87c` | CURRENT_STATE: whole suite 5,885 passed, 124 skipped (8 min 33 s, on `96ee4e6`); CI's gates run by hand |
| 14:58 | push | `99cd15f..b0bd87c`; the CI and Pages runs failed in 3–4 s (billing) |
| ≈ 15:45 | this file's commit, pushed | this handoff, read cold by a fresh agent and corrected; in CURRENT_STATE the push lines, «Next», the «Last session» link and the reranker's candidate count; the previous handoff's pointer here |
## State at the end

- **Git:** `origin/master` is this file's commit, pushed at her «да». Untracked
  `demo/phase-e-raw.webm` and `reports/ask100/` (F-8): leave them.
- **The Mac is idle**, checked about 15:05: no `llama-server`, supervisor or pytest; load
  1.06 / 1.55 / 1.90; Ollama holds no model; 420 GB free.
- **Stands on the Mac**, each with its runs under `chatlive/runs/`: `RAG_new_chat_99cd15f` (the
  check before), `RAG_new_chat_0892441` (after, V2), `RAG_new_chat_4ca5ddd` (the rerun),
  `RAG_new_s1_e5e135a` (the build's code). Keep them: the runs hold the answer texts the records
  only count. `RAG_new_chat_{19beeb1,33d4b42,7a99c45,9e1fc9e}` belong to earlier records.
- **Indexes:** the first generation in `/Users/julia/RAG_new_external/` and the ask100 runtime's
  aircargo index; the second in `/Users/julia/RAG_new_external_s1/<base>/` — `index/chroma`,
  `index/index-receipt.json`, `chunks-report.json`, and `cases.jsonl` for the external bases.
- **No background job** of this session runs. CI starts no job (billing, since `e81f0c5`).

## Next actions

### 1. Stage 2's spec and tools, committed before the first request

A proposed name: `docs/specs/stage2-four-corpora.md`, from `PLAN.md` §5 «Этап 2», §4.3 (M1–M4)
and [the handover plan](../specs/handover-signal.md) 1.1–1.2. **Stage 2's tools are written,
tested on the Mac and committed with the spec or before it**: a stand is the archive of one
commit, so a tool committed later is not on it. The spec names:

- **The stand.** PLAN: «стенд — коммит, которым закрыт этап 1»; product code is `4ca5ddd`'s.
  The spec's commit or a later one serves if the check in 2 passes. Every answer of the stage
  comes from that one stand.
- **The cases, in order.** aircargo: all 100 of `evaluation/curated_cases_aircargo.jsonl` in file
  order; the graph lane adds the 15 of `evaluation/curated_cases_aircargo_gr_multihop.jsonl`.
  External: the `case_ids` of the `stage2` selections in `evaluation/external_parts.json`
  (ConditionalQA `stage2` plus `stage2_not_answerable`). `<base>/cases.jsonl` of the second
  generation holds every question of its base (2,623 / 400 / 2,556 lines), so batches name
  selection ids only.
- **Forecasts and stop rules.** PLAN's 340 / 400 s a question, caps 3×: 1,020 / 1,200 s. V3's
  one aircargo answer was a batch-first question: 399 s, 17 % over its 340 s, the answer 3.6×
  longer than V2's. My recommendation: keep PLAN's forecasts (one observation; the caps leave
  room) and read batch 1 against them. Retrieval ≈ 30 s a question; the graph lane ≈ 1–1.5 h.
  Plus a cap for each part as a whole (stage 1's check had 2 h for a 40-min forecast).
- **The runners.**
  - Answers: the stand's `live_supervisor.py LABEL prod CASES 1020/1200 TENANT=…,CHROMA=…,CASES_FILE=…`
    (its docstring). `CASES` is a comma list of ids, so one batch is one supervisor run; the
    fourth argument is the client's caps — pass `1020/1200`, never the forecasts. `audit.sh` is
    the frame for a driver: wait for free ports and an empty Ollama, copy the index (a fresh copy
    per batch: the API writes into the database it opens), run, log START and the end.
  - Retrieval without the model (part 2): `MODE retrieval` runs `live_retrieval.py`, which sits
    only in `reports/chat-live/33d4b42/tools/` and hard-codes aircargo's tenant and cases. Part 2
    needs a runner taking `TENANT`, `CHROMA` and `CASES_FILE` that keeps the score of every merged
    candidate (PLAN writes «всех 20»; the reranker sees 32–37); `live_api.py` already logs them.
  - The graph lane (part 3) has no runner on the chat path: GR-3's `scripts/gr3_graph_lane_ab.py`
    and `scripts/extract_graph_entities.py` worked on phase-C contexts and first-generation
    chunks. Whether its graph is rebuilt on the second generation is the spec's call; part 3 may
    be a preparation slice of its own.
  - New tools go to a new folder, e.g. `reports/stage2/tools/`; a changed stage-1 tool is copied
    there under its own name. Never edit `reports/stage1/tools/`: the stage-1 artefact test pins
    its bytes.
- **The judge.** `claude-opus-5-5` at effort `max` (`evaluation/isolated_request.py`, `MODEL` and
  `EFFORT`, lines 41–42), on the laptop; it needs no Mac time. Per part:
  - 1: M1 by `scripts/chat_answer_judge.py` (one English prompt for every corpus, the answer due
    in the question's language) and M3, 15 retests, ≈ 115 requests;
  - 2: M3 on aircargo by the judge (≈ 100), on the external bases by `evaluation/external_gold.py`
    (deterministic);
  - 3: M3 by the judge, ≈ 115;
  - 4: M1 and M2, ≈ 330.

  M2 on aircargo is keywords, deterministic (PLAN §4.3). No adapter judges a retrieval-only or
  graph context yet (M3); the spec names one. `chat_answer_judge.py` computes a quadratic kappa
  but no threshold: the spec registers one (the repository's precedent is `PASS_KAPPA = 0.6` in
  `evaluation/nli_validation.py`). It also forecasts the judge's hours and usage from its first
  requests (memory `usage-windows-probe`).
- **What leaves the hosts.** The external bases' rule (2026-10-05/07,
  [connection record](../evidence/external-bases-connection.md)): «Outside the hosts go
  aggregates, attribution and provenance only: no question, evidence string, document, chunk or
  embedding of an external base is committed or published.» The hosts are the Mac and the
  laptop. The judge, the session's model, reads answers, prompts and references from the Mac's
  run folders: copy them to a laptop folder outside `D:/RAG_new` (`sync.py` ships untracked
  files, and they risk a commit), never commit them; records hold verdicts, counts, ids, SHAs.
  The same record says generation on the external bases «is frozen» (D7); «Вариант B»
  (2026-10-17) superseded that.
- **The records**, one per part, under `reports/stage2/<stand commit>/`, with corpus SHA, code
  SHA and config; the test and the evidence row of part 5.

Then read the spec cold — one fresh agent on the session's model, the findings as its reply —
fix the gaps, and commit before the first request.

### 2. The stand; one question, five, then the rest

The product-code check and the stand, in one Git Bash call; write the 7 characters of
`git -C D:/RAG_new rev-parse --short=7 HEAD` for `<c>`:

```sh
C=<c>; S=/Users/julia/RAG_new_chat_$C
D=$(git -C D:/RAG_new diff --stat 4ca5ddd $C -- . ':!docs' ':!docs-site' ':!reports' ':!tests' ':!archive' ':!*.md')
if [ -n "$D" ]; then echo "LOOK FIRST: $D"; else git -C D:/RAG_new archive --format=tar $C | ssh -o BatchMode=yes deproject-mac "mkdir $S && tar -x -C $S && echo $(git -C D:/RAG_new rev-parse $C) > $S/CODE_SHA && ln -s /Users/julia/RAG_new_ask100_20261012_7cad79f/.ask100-runtime $S/.ask100-runtime && mkdir $S/chatlive && cp $S/reports/stage1/tools/*.py $S/reports/stage1/tools/audit.sh $S/chatlive/ && cp $S/reports/stage2/tools/* $S/chatlive/ && cat $S/CODE_SHA && ls $S/chatlive"; fi
```

`LOOK FIRST` lists what changed since `4ca5ddd` outside docs, reports and tests. New measurement
tools in `scripts/` or `evaluation/` are allowed. Product code imports some modules there
(`evaluation.experiment_schema`, `scripts.generate_recommendations`, …): grep the product
directories for each printed module before raising the stand without the gate. Stage 2's tools
are copied after stage 1's; use the folder the spec names.

**Idle Mac first:**
`ssh deproject-mac 'ps -axo pid,command | grep -E "[l]lama-server|[s]1_supervisor|[p]ytest|[l]ive_supervisor"; sysctl -n vm.loadavg; curl -s http://127.0.0.1:11434/api/ps'`.
No process may be listed, the second load number must be below 2, and Ollama must report
`"models":[]`.

**One question, then five, then the rest.** This is Julia's rule (memory
`chat-test-expectations`). Run aircargo's batch 1 alone. Read its first answer when it lands,
and its first five — time against the forecast, route, script, prompt labels — before batches
2–10 start.

**Every part runs detached on the Mac.** An 8-hour run died at 39/100 when its session closed
(2026-10-13).
- Launch it with `nohup … </dev/null &` inside ssh, the ssh itself a background Bash job, as the
  build was launched (previous handoff, «Next actions» 1).
- Write the running part's label, log path and stop command into CURRENT_STATE, in place, so a
  session that ends mid-part leaves the next one able to watch or stop it.
- Watch it with a Monitor until-loop that greps the Mac's log over ssh (literal absolute paths).

### 3. The parts in PLAN's order

aircargo's 100, retrieval on 400, the graph lane, the 300 external answers, then the record. Two
small preparation slices fit between parts: F-3, and S8 in `scripts/chat_signals.py` (due
before stage 3).

## Do not

- Push without her word, or name MyFlow, Codex, GLM or any other model (D12).
- Read, print or copy `.ask100-runtime/env.json`.
- Commit or publish any question, document, chunk or embedding of an external base.
- Run tests or models on the laptop. It keeps `ruff`, `mypy` and light scripts.
- Change product code or prompts during stage 2's runs, or rebuild an index in place.
- Edit `reports/stage1/`, whose records and tools are pinned by bytes, or reword a sentence the
  artefact test asserts: grep `tests/test_stage1_live_artifact.py` first.
- Hold a long part on the laptop's ssh; run two measurements on the Mac at once; run
  `sync.py`/`remote.py` during a measured run (keep gate runs short and few).
- Reuse a run folder: `live_supervisor.py` refuses an existing one.

## Lessons

1. **A criterion must measure the change's claim**, not what is easy to count (V2, above). The
   criterion that caught the failure read the answer, and none read the prompt that caused it.
2. **The self-score is blind to some failures.** Two wrong-script answers scored 100; a number
   from the self-score alone would hide them. Stage 2's judge is the instrument.
3. **Heredocs mangle Cyrillic and backslashes** in Git Bash: write such scripts with the Write
   tool. Once, the Edit tool wrote `"[\u0400-\u04ff]"` as literal characters; write
   `"[а-яА-ЯёЁ]"`, or read the bytes back.
4. **A red proof must fail at the assertion that names the defect.** The first one failed for
   another reason; read the failure, not the exit code.
5. **`sync.py`'s `tree=` is never a commit's tree** while untracked files lie in the working tree.
   To name the commit a suite ran on, use the recipe in the memory `mac-gate-infra`
   (`git ls-files --others --exclude-standard --directory`; without `--directory`, WinError 206).
6. **Before a push**, CI's gates by hand, as the previous handoff's «Next actions» 3.4 lists them:
   the whole suite on the Mac, both mypy commands, bandit, pip-audit with CI's flags, DEP-01. CI
   runs none of them while billing blocks it.
7. **Check a claim against the record before writing it.** The spec first said the test «derives
   every claim of this spec about them»; V2's 608 letters come from the Mac, not the record, and
   the sentence was narrowed. This file's cold read found the same kind of error in the next
   step's tools: «all 20 candidates», a retrieval tool assumed universal, an incomplete
   product-code check.

## Glossary

The previous handoff's [glossary](session-handoff-2026-10-18-stage1.md#glossary) holds
generation, stand, tenant, hybrid path, BM25 restore, header line, open and locked parts,
S1–S7, rule (a)/(b)/(c), `NOT_EVIDENCE` and idle Mac. New here:

- **V2 / V3 prompts.** V2 (`ffae1c2`): Russian instructions asking for the question's language.
  V3 (`4ca5ddd`): the same request, in English instructions.
- **Check before / after / rerun.** The three live checks of stage 1:
  `reports/stage1/{99cd15f/before,0892441/after,4ca5ddd/after}.json`.
- **Script.** Cyrillic or Latin, by counting letters in Unicode ranges as `audit_summary.py`
  does; not a language (English and German are both Latin).
- **Self-score.** The model's own 0–100 rating of its answer, the «Качество: N» badge. Below 80
  (`QUALITY_THRESHOLD`) the chat's rule sends the answer `human` (operator offered); otherwise
  `auto`. The rule is S1 of the handover plan. **S8** — the answer-script candidate, above.
- **F-1…F-10.** The findings of the audit of 2026-10-18,
  [`audit_fable_18_10_26.md`](audit_fable_18_10_26.md).
- **M1–M3.** PLAN §4.3: M1 the judge's verdict on the answer against its context; M2 correctness
  against the reference answer (aircargo: keywords); M3 retrieval — the judge's «the context
  holds the answer» on aircargo, gold-evidence coverage on the external bases.
- **`stage2` selections.** External questions registered at `e5e135a`, before any request:
  ConditionalQA 40 documents × 2 plus the first 20 not-answerable, WixQA the first 100 tuning
  questions, MultiHop-RAG the first 100 advisory ones.
- **Kappa.** Quadratic-weighted agreement of the judge with its own retests.

## Verification

- `git -C D:/RAG_new log --oneline 99cd15f..b0bd87c` gives 27 lines, this session's six from
  `cd78fbd`; `git -C D:/RAG_new -c credential.helper='!gh auth git-credential' ls-remote origin master`
  (read-only) gives the SHA of `git -C D:/RAG_new rev-parse HEAD` while nothing new is committed.
- On the Mac: `python D:/RAG_new/.tmp/mf-mac/sync.py`, then
  `python D:/RAG_new/.tmp/mf-mac/remote.py --site pytest tests/test_stage1_live_artifact.py -q -p no:cacheprovider -p no:schemathesis --basetemp=.tmp/pytest-stage1 --tb=short`
  should report 11 passed.
- Whole unit suite on `96ee4e6`'s tree: 5,885 passed, 124 skipped. Both mypy commands: no issues.
  bandit 1.9.4: exit 0. pip-audit: «No known vulnerabilities found, 5 ignored». DEP-01: PASS,
  the dated exception GHSA-ch52-4w7c-c8xp until 2026-11-03. The three docs tests with
  `test_transformers_cve_floor.py`, `test_precommit_config.py` and the records' test: 51 passed
  on `b0bd87c`.

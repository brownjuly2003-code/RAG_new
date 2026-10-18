# Session handoff — 2026-10-18 — stage 1: fixes committed, the new index generation building

Session `99ac58b5`, 2026-10-17 22:59 UTC – 2026-10-18 about 02:30 UTC, Claude Opus 5.5 alone
(D12), continued across several context compactions. **Times are UTC**, as the Mac's records
are; the laptop's clock is UTC−4 (commit dates read 2026-10-17 evening; 12:00 UTC is 08:00 on
the laptop). The session before: [one plan, fixes first](session-handoff-2026-10-17-one-plan.md).
The session after: [stage 1 closed, stage 2 next](session-handoff-2026-10-18-stage1-closed.md) —
this file's «Next actions» are done; their launch, stand, stop and rerun procedures (1–2) still hold.

Julia's request: «продолжи по CURRENT_STATE.md, этап 1» — carry out [`PLAN.md`](../../PLAN.md)
§5, stage 1. Mid-session (about 00:20) she asked «что грузит мак?»; the answer: nothing heavy —
the tail of my own live runs; a background job then waited for the 5-minute load to fall below
2 before the live check of the external tenants resumed (00:26). No other message, no new
decision.

**Not pushed:** 21 commits, `8f94d84`…the commit of this file, on top of `99cd15f`
(`origin/master`). A push waits for her word; the checks it needs are in «Next actions», 3.4.

## What matters to understand

**What stage 1 is for.** The product is the web chat (`/api/ask/stream`). Reading the code on
2026-10-17 found defects that tie the answer path to markdown files, to Russian and to aircargo.
Julia put fixing them first («поставить в приоритет»): measuring before the fixes would measure
a path about to be thrown away. Stage 1 audits the code repeatably, fixes or records each
finding, proves the change live on one question per corpus (rule (a)), rebuilds the four
indexes as a new generation, and writes the tools stage 2 measures with. Stage 2 then gives the
product its first quality number on the customer's path.

**Where it stands.** Everything except the live check after the fixes is done:

| Part of stage 1 (PLAN.md §5) | State |
|---|---|
| 1. The audit, repeatable | done: `python -m scripts.universality_audit` plus the reading of the path; 25 findings, each with an outcome in [`docs/specs/stage1-fixes.md`](../specs/stage1-fixes.md) |
| 2–3. The fixes, a commit and a unit test each | done: loaders (rows 1–3), header (5–7), table header (8), seams (9), language (10), BM25 restore (23); the rest are limits or later stages, each with its reason |
| Live check before the fixes | done: stand `99cd15f`, record [`reports/stage1/99cd15f/before.json`](../../reports/stage1/99cd15f/before.json) |
| 4. The new index generation | **building** on the Mac since 01:05, about 11 h |
| 4. The API's index path cuts the same chunks | done: `tests/test_publication_chunk_parity.py` |
| 5. The tools of stage 2 | done: runner, judge's adapter with M2, sample, signal tool |
| Live check after the fixes (rule (a)) | **next**, when the build ends; pass criteria registered in the spec before the run |

**What the check before the fixes showed** (one question per tenant, each on a fresh API, the
first-generation indexes; 00:12–00:42, a first try of two tenants at a wrong index path stopped
at 00:20 — spec row 25): aircargo, ConditionalQA and MultiHop-RAG took the hybrid path — 20
vector and 20 BM25 candidates, rerank `ok`, 5 documents. **WixQA ran on vectors alone**: a
restarted API rebuilds the BM25 corpus by reading the whole Chroma collection in one call, and
SQLite refuses a call binding more than 32,766 variables (37,571 chunks). Fixed in `0872db4`:
the restore reads pages of 5,000. **The English questions of ConditionalQA and MultiHop-RAG were
answered in Russian** (WixQA's in English), and every answer prompt carried the Russian labels
«[Документ N» and «[Контекст:». Fixed in code (`ffae1c2`, `dec3167`); the check after proves it.

**Why the check after the fixes decides the stage.** It is the E2E test of rule (a) for every
change to the chat path: the same four questions, a stand whose product code is `e5e135a`'s (the
code that cut the new chunks), the indexes of the new generation. The spec's registered
criteria, each read off a field of the record `audit_summary.py` writes — for every tenant:

- `paths`: 20 vector and 20 BM25 candidates, `rerank_status` `ok`, `retained_contexts` 5 —
  `kind` alone does not tell: WixQA's vector-only run before also says `hybrid`;
- `bm25_restore_log`: the tenant's `Restored N chunks` line, no `Chunk restore failed` or
  `WITHOUT BM25`;
- `answer_letters`: more letters of the question's script than of the other — Latin for the
  three external bases, Cyrillic for aircargo;
- `prompts`: `labels_dokument` and `header_kontekst` 0, `labels_source` and `header_first_line`
  at least 1 (window fitting may drop documents or cut one to an excerpt without its header
  line, so not every one);
- a question stopped by the client's cap (1,020 s, named in `client_error`) or a failed run
  (`launch.status`) is `NOT_EVIDENCE` for its tenant.

**How to read each outcome and what to tell Julia:**

- **All four pass** → stage 1 closes (3 below). Tell her: the chat runs the same hybrid path on
  all four corpora, answers in the question's language, its prompts carry no Russian words; the
  first quality number comes in stage 2. Ask whether to push.
- **A defect in product code** (BM25 0, a restore failure, `header_first_line` 0 with the index
  holding headers) → fix it with a unit test in a new commit. Then: if the fix changes how chunks
  are cut or headed (`ingestion/`, the chunking and header code of `vectordb/`), the new
  generation is stale — tell Julia before rebuilding (hours of Mac time). Otherwise bring up a
  new stand at the fix commit, check that `git diff --stat e5e135a <fix>` over the product
  directories shows only the fix, rerun **all four** tenants there, and record under
  `reports/stage1/<fix commit>/after.json`: one record, one stand.
- **`header_first_line` 0 or a «[Контекст:» header, and the index lacks the new header** → a
  build defect: read `/Users/julia/RAG_new_external_s1/<base>/chunks-report.json` and the
  collection's `contextual_header` metadata.
- **An answer in the wrong script** → the 4B did not follow the V2 instruction on that question.
  No word list (universality). Record it as observed, tell Julia, and let stage 2 measure the
  share on ≈ 100 questions per base before any change.
- **aircargo answers that the context lacks it, the log warns «unstamped index»** → the stand
  opened an empty database (spec row 25): wrong directory or collection name.
- **`NOT_EVIDENCE` (cap or failure)** → read `runs/after-<base>.supervisor.log` and the run's
  `api.log`; rerun that tenant alone on an idle Mac (2, «One tenant again»).

## Julia's decisions in force (none new this session)

D11 (2026-10-03): no person grades or approves anything. D12 (2026-10-04): the session does all
the work, no other model in any role. Production on the Mac (2026-10-14), Qwen3-4B (2026-10-16).
All 2026-10-17: the one plan accepted; fixes first; answers in the question's language; the
indexes rebuilt as a new generation beside the old (aircargo too). A push is hers, asked each
time.

## My choices, not hers

- **ConditionalQA's sample adds the first 20 not-answerable questions** to 40 documents × 2
  primary ones: PLAN names refusals among what this base tests (`e5e135a`).
- **S7 of the handover plan is read from the stand's live record** of the reranked retrieval
  (`live_api.py` records every rerank score), not from a rerun of retrieval.
- **The criteria of the check after the fixes** are mine, registered in the spec before the run.
- **Each live run reads a copy of its index** (`audit.sh`): the API writes into the database it
  opens, and a generation must stay as its receipt describes it.
- **The whole unit suite ran on the Mac during the build** (twice): the build has no time number
  to protect. During the live check before, no test ran (the process lists `audit.sh` logs at
  each start show none).

## Log

Grouped by topic; `git log` order differs slightly.

| Commit | What |
|---|---|
| `8f94d84` | the universality audit (`scripts/universality_audit.py`) and the stage-1 spec |
| `dec3167` | the chunk header `[document › section]`, the nearest section kept (rows 5–7) |
| `f11da3d` | parent expansion reads each seam once, the header first (row 9) |
| `e32789e` | a continued table piece starts with its column header (row 8) |
| `305dcab` | DOCX, HTML and PDF load as markdown with their structure (rows 1–3) |
| `ffae1c2` | the chat answers in the question's language; prompts V2 (row 10) |
| `46376e7` | the live check before the fixes and its record; the stand tools |
| `0872db4` | the BM25 corpus restored in pages (row 23) |
| `e76fc54` | `scripts/corpus_chunks.py` and the build supervisor `s1_supervisor.py` |
| `144865e`, `875f274`, `324dbce` | WixQA's 6,221 source HTML pages through the product loader: nothing lost ([record](../../reports/stage1/875f274/wixqa-loader-check.json)) |
| `88a58c2` | the judge of chat answers (`scripts/chat_answer_judge.py`) and the signal tool (`scripts/chat_signals.py`) |
| `e5e135a` | the stage-2 questions registered (`evaluation/external_parts.json`, selections `stage2`) — **the build's code** |
| `047d379` | the restart E2E reads the BM25 corpus back in pages |
| `627e0e6` | three stand-ins of a Chroma collection page as Chroma does (the suite had failed 9 tests through them; the message says eight) |
| `8852fe1` | the pilot's registration stays provable after `e5e135a` (the suite had failed 2 tests) |
| `81009fb` | the upload path indexes the chunks the measurements cut (parity test) |
| `8d97c1b` | the check after the fixes registered; `header_first_line`; S7 from the live record |
| the commit before this file's | the record also says how a run ended and its config (`client_error`, `overrides`, …); `before.json` rebuilt from the same runs with them; the criteria worded by the record's fields; the spec's caps 1,020 s |
| this file's commit | CURRENT_STATE, ROADMAP, this handoff |

Product code (`agent api config ingestion llm services vectordb utils tasks`) has not changed
since `e5e135a`.

## State at the end

- **The build** runs on the Mac: supervisor pid 6360, started 01:05:01, base `aircargo`, step
  `embed` at the last look. Expected: aircargo ≈ 1 h (5,589 chunks × ≈ 0.6 s); the three
  external bases ≈ 10 h (9.8 h at their connection; by chunks ConditionalQA ≈ 2.2 h,
  MultiHop-RAG ≈ 1.8 h, WixQA ≈ 5.9 h) — the end near 12:00–13:00 UTC, later if the pace stays
  as at 01:45 (aircargo 40 min in, checkpoint 10.8 MB, the unit suite running beside it for
  part of that time). **Stop rule** (spec):
  aircargo 3 h, the three external bases 30 h; the supervisor does not enforce it — the session
  that watches compares each base's `embed.started` in the state file with the clock.
- **The unit suite** on the Mac: see «Verification».
- **Stands on the Mac:** `/Users/julia/RAG_new_chat_99cd15f` (the check before; its runs under
  `chatlive/runs/`), `/Users/julia/RAG_new_s1_e5e135a` (the build's code snapshot). Keep both
  until stage 1 closes.
- **Untracked, not mine:** `demo/phase-e-raw.webm`, `reports/ask100/` — leave them.

## Next actions

### 1. Watch the build (no Mac load added)

```sh
ssh deproject-mac 'python3 -c "import json; s=json.load(open(\"/Users/julia/RAG_new_external_s1/s1-state.json\")); print(s[\"status\"], s.get(\"base\"), s.get(\"step\"), s.get(\"reason\"), s.get(\"guarded_unchanged\")); print({b: sorted(v) for b, v in s[\"bases\"].items()})"; tail -1 /Users/julia/RAG_new_external_s1/s1-host.jsonl'
```

- `status`: `running`, then `complete`, `failed` (with `reason` and `log_tail`) or `stopped`.
  A step's own log: `/Users/julia/RAG_new_external_s1/<base>/<step>.log`.
- The host sample every 60 s: the step's process memory and CPU, swap, load, foreign CPU.
- **To stop:** `ssh deproject-mac 'touch /Users/julia/RAG_new_external_s1/s1-stop'`. **To go
  on after a stop or a failure:** remove `s1-stop`, then start it again exactly as it was
  started — a base with an index receipt is skipped, an interrupted embedding resumes:

```sh
ssh -o BatchMode=yes deproject-mac 'cd /Users/julia/RAG_new_s1_e5e135a && nohup /Users/julia/RAG_new_gr4_venv/bin/python reports/stage1/tools/s1_supervisor.py /Users/julia/RAG_new_s1_e5e135a e5e135acb4df7fee25499bc7277232733c622e63 > /Users/julia/RAG_new_s1_e5e135a/s1-supervisor.out 2>&1 < /dev/null & echo launched $!'
```

  Run that ssh as a background Bash job: `nohup … &` inside ssh keeps the local ssh open.
  A base whose `index/` directory exists without a receipt stops the supervisor on purpose;
  look at it before removing anything.
- **Complete means:** `status` `complete`, `guarded_unchanged` `true`, and for each of the four
  bases `/Users/julia/RAG_new_external_s1/<base>/index/index-receipt.json` and
  `<base>/index/chroma/chroma.sqlite3`; external bases also `<base>/cases.jsonl`.
- **`guarded_unchanged` false** → a path the build must not touch changed: compare
  `guarded_before` with `guarded_after` in the state file, use nothing of the new generation,
  and tell Julia.

### 2. The check after the fixes (forecast 40 min; stop at 1,020 s a question, 2 h in all)

**The stand's commit** is HEAD when the check starts — this file's commit or a later one whose
product code still equals `e5e135a`'s. Bash keeps no variables between calls: take
`git -C D:/RAG_new rev-parse --short=7 HEAD` once and write those 7 characters for `<c>` in
every command below. On the laptop, Git Bash:

```sh
C=<c>; S=/Users/julia/RAG_new_chat_$C
git -C D:/RAG_new diff --stat e5e135a $C -- agent api config ingestion llm services vectordb utils tasks   # must print nothing
git -C D:/RAG_new archive --format=tar $C | ssh -o BatchMode=yes deproject-mac "mkdir $S && tar -x -C $S && echo $(git -C D:/RAG_new rev-parse $C) > $S/CODE_SHA && ln -s /Users/julia/RAG_new_ask100_20261012_7cad79f/.ask100-runtime $S/.ask100-runtime && mkdir $S/chatlive && cp $S/reports/stage1/tools/live_supervisor.py $S/reports/stage1/tools/live_runner.py $S/reports/stage1/tools/live_api.py $S/reports/stage1/tools/launch.py $S/reports/stage1/tools/audit.sh $S/reports/stage1/tools/audit_summary.py $S/chatlive/ && chmod +x $S/chatlive/audit.sh && cat $S/CODE_SHA && ls $S/chatlive"
```

The tools come from the archive of that commit, so the stand's `CODE_SHA` names them too. If
the diff prints anything, product code changed after the build — see «A defect in product
code» above, or stop and tell Julia. The runtime link (the ask100 runtime) gives the stand its
`env.json` — never print it — and Postgres on port 55433; the API listens on 8002.

**Idle Mac first:**
`ssh deproject-mac 'ps -axo pid,command | grep -E "[l]lama-server|[s]1_supervisor|[p]ytest|[l]ive_supervisor"; sysctl -n vm.loadavg; curl -s http://127.0.0.1:11434/api/ps'`
(the brackets keep the search from finding itself) — no process listed, the second number of
`vm.loadavg` (the 5-minute load) below 2, Ollama holding no model (`"models":[]`). Then, as a
background Bash job:

```sh
C=<c>; S=/Users/julia/RAG_new_chat_$C
ssh -o BatchMode=yes -o ServerAliveInterval=60 deproject-mac "cd $S/chatlive && sh audit.sh after /Users/julia/RAG_new_external_s1 /Users/julia/RAG_new_external_s1/aircargo/index/chroma > runs-after-audit.out 2>&1; grep -E 'START|STOP|LIVE_DONE|AUDIT' runs/after-audit.log"
```

`audit.sh` (usage in its header): one fresh supervisor per tenant — API, database, the model
loaded and timed apart — each on a copy of its index; the questions are `aircargo-probation-data`,
`conditionalqa-train-1484`, `wixqa-simulated-074`, `multihoprag-0448`; its fourth argument
(`ONLY`) lists the bases to run.

**To stop it** (the 2-h rule, or a problem): `ssh deproject-mac 'pkill -f "^sh audit.sh after"; pkill -f live_runner.py'`
— the first ends the loop, the second ends the running question; its supervisor then stops the
API and Postgres and unloads the model. Check with the idle command above.

**One tenant again:** a run folder is never reused (`live_supervisor.py` refuses an existing
one). Move the old run aside first, e.g. for WixQA:
`ssh deproject-mac "cd $S/chatlive/runs && mv after-wixqa after-wixqa.try1 && mv after-wixqa.supervisor.log after-wixqa.try1.supervisor.log"`,
then `sh audit.sh after /Users/julia/RAG_new_external_s1 "" "wixqa"` in `$S/chatlive`. The
record reads `runs/after-<base>` only — the newest run; say in the spec that a tenant was rerun
and why.

**The record** (counts, ids and config only — no text of an external base leaves the Mac):

```sh
C=<c>; S=/Users/julia/RAG_new_chat_$C
ssh deproject-mac "cd $S/chatlive && /usr/bin/python3 audit_summary.py after runs runs/after-summary.json /Users/julia/RAG_new_external_s1"
mkdir -p D:/RAG_new/reports/stage1/$C && scp -q deproject-mac:$S/chatlive/runs/after-summary.json D:/RAG_new/reports/stage1/$C/after.json
python -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8'))
for t,v in d['runs'].items():
    p=(v['paths'] or [{}])[0]; c=(v['cases'] or [{}])[0]; q=(v['prompts'] or [{}])[0]
    print(t, v['launch'].get('status'), p.get('candidates'), p.get('rerank_status'), p.get('retained_contexts'), c.get('question_letters'), c.get('answer_letters'), c.get('client_error'), q, v['bm25_restore_log'])" D:/RAG_new/reports/stage1/$C/after.json
```

Read it against the criteria above; compare with `before.json`. Provenance in the record: the
code (`launch.code_sha`), the model and its digest, the config — the code defaults at that SHA
plus `launch.overrides` (the limits and the device) — and the SHA-256 of each base's manifest,
chunk report and index receipt (`source_sha256`). Commit `after.json` alone; the spec's text
comes with the close.

### 3. Close stage 1

1. **An artefact test** `tests/test_stage1_live_artifact.py`, on the pattern of
   `tests/test_chat_live_4b_artifact.py`: pin the bytes (SHA-256 and size) of `before.json`,
   `after.json`, `reports/stage1/875f274/wixqa-loader-check.json` and every tracked file of
   `reports/stage1/tools/` (not `__pycache__/`); derive from the records the claims the spec
   makes — per tenant before and after: candidates 20/20 or WixQA's 20/0, rerank `ok`, 5
   documents, the restore line, the letters by script, the four prompt counts; the stand's
   commits and the generation each record names.
2. **The spec:** status closed; a paragraph for the check after (what passed, any rerun and
   why); the forecast table's actuals — check before 30 min of runs (00:12–00:42), the build's
   per-base times from the state file, the check after.
3. **[`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md)** one row; **ROADMAP** stage 1 done;
   **CURRENT_STATE** — the stage-1 section shortened, «Next» stage 2. A root `.md` touched →
   `tests/test_docs_hygiene.py`, `test_docs_quality.py`, `test_docs_publication.py` on the Mac.
4. **Before asking for a push** (CI starts no job: GitHub billing since `e81f0c5`), as CI runs
   them: the whole unit suite on the Mac; both mypy commands of `.github/workflows/ci.yml`
   (lines 136–137) on the laptop; bandit on the Mac with CI's line 278
   (`/Users/julia/agentflow-fc5-venv-7113966/bin/bandit -r . -ll -c pyproject.toml -x ./tests,./.venv,./reports,./data,./archive,./.tmp`
   in the gate checkout); pip-audit with CI's flags (lines 302–310) through `uvx` on the laptop;
   `node docs-site/scripts/check-npm-audit.mjs` on the laptop. Not reachable here: the
   docs-site build and the suite on the lock's exact pins — say so when asking Julia.

Then stage 2 ([`PLAN.md`](../../PLAN.md) §5): 100 aircargo answers on the chat path, retrieval
without generation, 300 judged external answers on the `stage2` selections, the graph lane.

## How to test on the Mac

- `python D:/RAG_new/.tmp/mf-mac/sync.py` (ships the working tree, uncommitted edits too),
  then `python D:/RAG_new/.tmp/mf-mac/remote.py --site pytest -q -p no:cacheprovider -p no:schemathesis --basetemp=.tmp/<name> <tests>`.
- Whole suite: `… pytest tests/ -q --ignore=tests/integration …`, about 11 min; run it as a
  background job.
- **Before committing, grep the tests for what a change touches** — a data file's name, a
  changed call (`grep -rln "external_parts\|\.get(include" tests/`): the focused runs of this
  session missed 11 failures the whole suite then found.
- The laptop runs `ruff` and `mypy` only (`C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe`,
  `PYTHONPATH=D:/RAG_new`). Format only your own code: some files at HEAD are not formatted.

## Lessons

1. **A data file pinned by SHA elsewhere.** `e5e135a` added selections to
   `external_parts.json`; its own test passed, two pilot tests pinned the file's SHA. The fix
   keeps the published records and proves the old bytes: the file without the later selections
   is byte for byte the one the pilot read (`sha_before_later_selections`).
2. **A call changed, the stand-ins not.** The paged restore passes `limit` and `offset`; three
   old stand-ins (test fakes) of a Chroma collection took neither, and the restore swallowed the
   TypeError.
3. **Small fixtures hide size limits.** SQLite's 32,766-variable limit showed only live, at
   37,571 chunks. A test of a whole-collection read needs a size past the limit, or paging.
4. **Chroma opens an empty database silently** at a wrong directory (`<base>/index` instead of
   `<base>/index/chroma`). The stand refuses a directory without `chroma.sqlite3`.
5. **Heredocs mangle backslashes.** Python with `\n` or `\[` written through a Bash heredoc
   changed twice this session; write such scripts with the Write tool.
6. **`nohup … &` inside ssh** holds the local ssh to its timeout; run the ssh as a background job.
7. **Check a claim before writing it.** The spec said every stage-2 tool had a unit test; the
   stand tools have none (they get pinned with their records at the close). A handoff said
   `scp` misreads `D:/…`; a test showed it does not.
8. **Re-read the plan's stage text item by item** before calling the work done: «что он даёт
   те же фрагменты, проверяет аудит» (item 4) was nearly missed; the parity test closes it.
9. **A record must carry what its criteria read.** The first version of the after criteria
   named a stop at 1,020 s and the config, which `audit_summary.py` did not record; the cold
   read found it, the fields were added and `before.json` rebuilt from the same runs.

## Glossary

- **Generation** — one set of indexes built together: the first in `/Users/julia/RAG_new_external`
  and the ask100 runtime, the second (stage 1) in `/Users/julia/RAG_new_external_s1`.
- **The ask100 runtime** — `/Users/julia/RAG_new_ask100_20261012_7cad79f/.ask100-runtime`: the
  deployment a stand links to — `env.json` (secrets; never printed), its Postgres, aircargo's
  first-generation index.
- **Receipt** — `<base>/index/index-receipt.json`, written by `scripts/production_index.py`:
  what was indexed, from which archive and code. **`chunks-report.json`** — `<base>/`, written
  by the chunks step: chunking settings, counts, archive SHA.
- **Guarded paths** — directories the build must not change (first generation, aircargo's
  upload folder, the T-65 index); hashed before and after (`guarded_unchanged`).
- **T-65 index** — the aircargo index of an earlier task (T-65) whose embedder manifest the new
  indexes pin, so the API accepts them as built by the same embedder.
- **Stand** — `git archive` of one commit on the Mac plus `CODE_SHA`, `chatlive/` (the stage-1
  tools) and the `.ask100-runtime` link; serves one tenant per fresh API.
- **Tenant** — the API's corpus key: `aircargo`, `ext_conditionalqa`, `ext_wixqa`,
  `ext_multihoprag`.
- **Hybrid path** — BM25 and BGE-M3 candidates (20 each) merged by RRF (reciprocal rank fusion),
  then the bge-reranker-v2-m3 keeps 5; parent expansion adds neighbours.
- **BM25 restore** — a restarted API rebuilds its BM25 corpus from the Chroma collection.
- **Window fitting** — `_fit_stream_prompt`: documents dropped or cut to an excerpt so the
  prompt fits the model's context window.
- **Seam** — the 200-character overlap between two pieces of one long section.
- **Header line** — a chunk's first line, `[document › section › …]`; before stage 1,
  «[Контекст: Из документа …, раздел: …]».
- **The 4B** — Qwen3-4B-Instruct-2507, the production model. **V2 prompts** — the chat prompts of
  `ffae1c2`: no answer language named, answer in the question's.
- **Open / locked parts** — the external bases' questions split before any run; only open parts
  are read (ConditionalQA's and WixQA's open part is `tuning`, MultiHop-RAG's `advisory`).
  **Pilot**, **`stage2`** — selections of the open parts. **Connection** — the 2026-10-05/07 work
  that converted the external bases and built their first indexes.
- **Stand-in** — a test fake standing for a real object.
- **S1–S7** — candidate signals of [the handover plan](../specs/handover-signal.md); **M2** —
  agreement with reference answers; **M3** — gold-evidence coverage.
- **Rule (a)/(b)/(c)** — the slice acceptance rule of [`CLAUDE.md`](../../CLAUDE.md).
- **`NOT_EVIDENCE`** — a run that did not happen or was stopped; never a pass.
- **Idle Mac** — no `llama-server`, 5-minute load below 2, Ollama holding no model.

## Verification

- `git -C D:/RAG_new log --oneline 99cd15f..HEAD` — the 21 commits above.
- Unit suite on the Mac at `8d97c1b`: 5,874 passed, 124 skipped, none failed (619 s). The run at `047d379`, before `627e0e6` and
  `8852fe1`: 5,862 passed, 11 failed — 9 through the restore stand-ins (2 + 6 + 1 in three
  files) and the 2 pilot pins; all 11 then passed in a focused run (298 passed with the docs
  tests).
- Both mypy commands of CI: no issues (laptop, 2026-10-18).
- The parity test fails with the upload path's headers switched off (mutation run, reverted).
- The build: the command of «Next actions», 1.

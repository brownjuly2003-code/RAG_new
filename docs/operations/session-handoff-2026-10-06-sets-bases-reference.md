# Session handoff — 2026-10-06, sets drafted, bases indexed, reference registered

Written 2026-10-06 at about 11:00Z, when Julia asked whether she could close
the session. The session ran from 2026-10-05T21:53Z (transcript
`f833a800-…`, 20 compactions). Read `CLAUDE.md`, `CURRENT_STATE.md`, then this
file; the [log of 2026-10-05](session-handoff-2026-10-05-one-model-and-sizes.md)
explains what one model can and cannot claim and is not repeated here.

Nothing is lost by the close: every result is in a local commit, and the two
runs on the Mac go on by themselves. What stops is the session's own
continuation — nobody collects the Mac's results or sends the next requests
until a new session starts from this file.

## What matters to understand

**How the system works now.** The product is unchanged: no default moved,
`RAG_GRAPH_RETRIEVAL` stays `off`. Everything below is the measuring side of
the quality plan [`plan_03_10_26.md`](../specs/plan_03_10_26.md): sets,
baselines, judges, registrations.

**The question.** The plan's first campaign asks whether a retrieval mechanism
(H1 first) can be shown to gain under a rule registered in advance. The ten
slices of this session build what that campaign measures with. None of them
changes the product, so each counts only by rule (b) — more verified cases —
or (c) — a published number with provenance; the rest is preparation and is
called so.

**Where each of the ten stands.** The list is my reading of her «10 следующих
слайсов» (the plan's order of dependencies after 3.0).

| Slice | What it is | State at the close | What closes it |
|---|---|---|---|
| 2.5 | production baseline on H and Hm, loss map (T-65) | **closed**, rule (c), `ba8285d`, [capsule](../evidence/production-baseline-h-hm.md) | — |
| 1.3c | variance pilot, sizes of the sets | **closed**, rule (c), `c5817d0`, [capsule](../evidence/variance-pilot-gold-metrics.md); no verdict by design | one open decision, below |
| 1.3d | verified development and holdout sets, then a screening tier | preparation: both sets drafted, scanned, first check planned; **no check request sent** | checks, repairs, replacements, minimums, capsule |
| 1.3e | lock of the holdout | not started; design noted below | after 1.3d |
| 1.5, 1.5c, 1.5d | connect ConditionalQA, WixQA, MultiHop-RAG | preparation: two bases embedded and indexed, WixQA embedding on the Mac | one capsule for the three, when the Mac finishes |
| 1.6 | parts, lock and pilot of the external bases | registered, `64a72e5`; the pilot is queued on the Mac | pilot → capsule → eleventh revision of the spec |
| 1.7 | control baseline on the external bases | not started | after the eleventh revision; about three Mac nights |
| 2.8 | validation of the NLI judge | reference registered, `7dd2ed0`; **no request sent, no judge run** | cold read → labelling → judges on the Mac → criteria → capsule |

**What is established.** The baseline: `precision_at_5` 0.5354 on H (n 99) and
0.6800 on Hm, one judge with a retest. The sizes: development 60 cases in 37
clusters, holdout 64 in 18; the registered MDE of the deciding metrics is
0.17–0.30, so the campaign can show effects of that size and no smaller ones.
The drafts: development 30 of 30, holdout 62 of 64 positions — positions 5 and
19 were declined by the generator and stay empty. Where a brief asked for a
quantity, the draft carries it as asked in 0 of 7 positions of development and
1 of 14 of holdout; the generator prompt was not changed after the first
count, and both counts go into the capsule.

**Two long poles.** The Mac: WixQA embedding (to about 13:30Z on 2026-10-06),
then the pilot of 1.6 by itself (16–19 h, to about 06:00–09:00Z on
2026-10-07), then one night of NLI judges for 2.8, then three nights of 1.7.
The request stream: every draft, check and reference label is one isolated
request of `claude-opus-5-5`, one stream at a time; what is left is about 60
hours of stream. Neither pole waits for the other, and the session's own
writing fits beside both.

**The subscription is the scarce resource.** The isolated requests spend
Julia's subscription, as the session does. Measured on 2026-10-06: 0.01 of
the weekly window is about $10 API-equivalent; a draft costs $0.61 (median), a
check $0.32; a stream of drafts takes about 0.008 of the week an hour. At
10:28Z the weekly window stood at 0.95 (reset 2026-10-06T22:00Z), the
five-hour one at 0.31 (reset 12:50Z). I stopped the streams there and kept
the session quiet: 0.96 was my line, so that her own day keeps some room. The
rest of the campaign's streams is about $450–500, near half of a weekly
window; the screening tier of 1.3d alone is about $345 (360 drafts and one
check each). These are estimates from the medians.

**Three things a session must not read.**
- *Holdout texts.* No text of a holdout draft entered this session; tools were
  read through their counts (`.tmp/devset13d/safe_view.py` masks an output).
  Keep it so until the lock of 1.3e and after it.
- *External bases.* ConditionalQA is for research use only; the registered
  rule (`evaluation/external_bases.json`) lets out aggregates, attribution and
  provenance — no question, evidence string, document, chunk or embedding of
  any of the three is committed or published. Their data lives under
  `D:/RAG_new/.tmp/external/bases/` and `/Users/julia/RAG_new_external/`.
- *Verdicts of 2.8 before `derive`.* The stores `pass*.jsonl` and
  `control-pass*.jsonl` are not opened, and a script prints ids and counts
  only.

**How to read what comes next, and what to tell Julia.**
- *Connection capsule (1.5, 1.5c, 1.5d)*: preparation, not a quality number.
  It says whether each base was converted, chunked, embedded and indexed with
  nothing lost, how long it took, and that our own corpus and index did not
  change. Tell her the sizes and the hours.
- *Pilot of 1.6*: variances and seconds, from which the sizes of the parts and
  the nights of 1.7 are read. It is measured once: a failed or aborted pilot
  is published by stage and error type and is not run again.
- *Checks of 1.3d*: every draft ends verified, repaired once or dropped. A
  minimum of the flags may not be met — the spec expects that for the
  safety-critical count; what follows is registered in «Drafts of plan step
  1.3d» (plan G32 for the tier). Do not improvise a remedy.
- *2.8*: first the stability bound of the reference. If it fails, the rubric
  is clarified once and the whole sample labelled again; a second failure
  makes the judge `provisional_judge`. If it holds, a judge that meets the
  criteria is `single_model_referenced` «on N of M units» — never
  human-validated.

## Julia's requests and decisions this session

| # | Her words | What it became |
|---|---|---|
| 1 | 2026-10-05T21:53Z: «НЕ ГРУЗИ СКИЛЛ MYFLOW_NEW. Не разворачивай на этой машине wsl, docker и подобное. Для этого используй мак. Тесты также прогоняй на маке. Работай сам - все делай сам, работай НЕ ПО MYFLOW_NEW (то есть не привлекай к работе другие модели) - тебе все нужно делать самому. Возьми в работу 10 следующих слайсов.» | no MyFlow command, no other model; pytest on the Mac only; the ten slices above |
| 2 | 2026-10-06T10:40Z: «могу закрыть сессию?» | answered yes; the local wait job stopped; this file |

She decided nothing else in this session. Still binding from earlier ones:
«сам» grants no push and no lifted guard; D11 — no people in the quality
process; D12 — one model does every job and check.

## What is the agent's choice, not Julia's

None of it was audited by another vendor; under D12 none can be.

1. **The ten slices**: 2.5, 1.3c, 1.3d, 1.3e, 1.5, 1.5c, 1.5d, 1.6, 1.7, and
   2.8 as the tenth.
2. **The usage line**: batches with a probe between them, a stop at 0.96 of
   the weekly window, the heavy writing put off until the reset.
3. **2.8**, where the research left a choice (spec, «How the reference of 2.8
   is drawn and asked»): a walk that looks ahead, since a plain capped walk
   ends stratum a1 at 38 of 40; the cap of four counted a question over both
   sources; a top-up kept under the cap, so 24 units and not 50; a pair of
   both sources labelled once; the rubric put into English without examples
   from the corpus; flags asked for and counted in nothing; the order of the
   second pass; a κ that cannot be computed fails the bound.
4. **1.6** (spec, «External bases: parts and pilot of plan slice 1.6»): one
   question a page under a ceiling of nights, which narrows plan row 1.6; one
   pilot, measured once; `reserve` and `excluded` read by no run of this
   campaign; opaque case ids committed as provenance; one capsule for the
   three connection slices.
5. **The Mac's order**: short test runs are allowed beside a measured run, a
   wide scan and the NLI judges are not; the judges go after the pilot.
6. **No change of the generator prompt** after the count of quantities.
7. **Every cold read is by the same model**: twice for the 1.6 section, twice
   for the 1.3d section. The 2.8 block has been read by its author only.
8. **Carried over and not yet told to her**: the decisions of the 3.0 spec
   (plan row 3.0); the rewrite of `CLAUDE.md` and of the memory index on
   2026-10-05; T-65's choices — where artifacts are committed, the tool
   `scripts/model_requests.py`, the ledger's wording for a run without a
   verdict (its [handoff](t65-baseline-handoff.md)).

## Once Julia decides

A bullet with no answer in it has none.

- **Push.** `master` is 27 commits ahead of `origin/master` (`f7416ca`); the
  work exists on this laptop only. On her word: the full suite on the Mac,
  then `git -C "D:/RAG_new" -c credential.helper='!gh auth git-credential' push origin master`,
  then the CI run.
- **The product's filter** (plan §3, «06.10, открытое решение из пилота
  1.3c»). The grading filter is in part a draw: another verdict on the same
  question and document in 9 of 168 shared documents; its batch request gave
  no grade in 187 of 187 contexts and took half of the grading seconds. A
  change of the filter changes the control, and the 2.5 baseline is then
  taken again. Default without her word: the filter stays, and the campaign
  measures the product as it is.
- **The budget of the streams.** About half of a weekly window for what is
  left, the screening tier about $345 of it. If she wants it smaller, the
  tier is the place: G32 is its registered outcome without the tier.
- **The line at 0.96.** Mine and reversible: she may let the streams run to
  the limit, or stop them lower.
- Still open from the log of 2026-10-05: the sensitivity of the campaign, the
  deciding role of the external bases (my reading of her words, in force only
  with the eleventh revision), another vendor's voice.

## Log

Commits of the session, oldest first (git dates against the transcript's
first timestamp):

| Commit | What |
|---|---|
| `5d86213` | 1.3d: registered prompts, sets of rubric v3, drafting, repair and minimums tools |
| `ba8285d` | 2.5 closed: baseline on H and Hm with its loss map (T-65) |
| `c5817d0` | 1.3c closed: variance pilot of the gold metrics |
| `c43f0a0` | 1.3d: register `pilot-v3` (30 verified, 0 dropped) and the development drafts |
| `64a72e5` | 1.6 registered: parts, lock, pilot of the external bases |
| `7dd2ed0` | 2.8 registered: pool, draw, request and plan of the reference |
| `e1521ba` | 1.3d: holdout drafts; development wide scan and round-1 plan |
| `b0db14d` | 1.3d: holdout wide scan and round-1 plan |

The supervisor of the external bases was started on the Mac before this
session (its state file says 2026-10-05T16:45Z) and began to work at
2026-10-06T03:34Z, after the 1.3c pilot. This session launched the pilot
runner of 1.6, which waits behind it.

## State at the end

- **Git**: `master`, 27 commits ahead of `origin/master`, nothing pushed.
  Untracked: `demo/phase-e-raw.webm` (not ours, never staged) and
  `tests/test_external_connection_artifact.py` — it fails until the
  connection capsule exists, so it stays out of gates and commits until then.
- **Laptop**: no stream, no monitor, no background job. Scratch tools are on
  disk under `D:/RAG_new/.tmp/` (git-ignored) and in the local branch
  `wip/plan-1.6-1.3d` (see «Verification»; not pushed).
- **Mac, supervisor of the bases**: pid 64907, snapshot
  `/Users/julia/RAG_new_ext_a0d438c0c25c`, state
  `/Users/julia/RAG_new_external/ext-state.json`. ConditionalQA: 13,778
  chunks, embedded in 6,977 s. MultiHop-RAG: 11,231 chunks, 8,227 s. WixQA:
  37,571 chunks, embedding since 07:48Z, about half done at 10:28Z.
- **Mac, pilot runner of 1.6**: pid 99859, directory
  `/Users/julia/RAG_new_extpilot_f6c2bfa7a915` (code `64a72e5`), state
  `.tmp/extpilot-state.json` there, status `waiting`. It starts when the
  supervisor's processes end: WixQA `retrieve`, then ConditionalQA `grade`,
  arms `control` and `pool30`. The rows of a question stay on the host; what
  may leave is `<base>.aggregates.json`.
- **Requests**: none in flight. 2.8 — none ever sent, no store exists.
  Development and holdout — no check request sent.
- **One look at the Mac**: `python D:/RAG_new/.tmp/external/ext_status.py`.

## Next actions, in order

Laptop tools run as
`PYTHONPATH=D:/RAG_new PYTHONIOENCODING=utf-8 AIRCARGO_CORPUS_DIR=D:/RAG_Support_Assistant/data/uploads/aircargo C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe <script>`;
tests run on the Mac only: `python D:/RAG_new/.tmp/mf-mac/sync.py`, then
`python D:/RAG_new/.tmp/mf-mac/remote.py --site pytest <files> -q -p no:schemathesis -p no:cacheprovider --basetemp=.tmp/pytest-<name> --tb=short`.

0. **Before any stream, measure the windows**:
   `… python.exe D:/RAG_new/.tmp/devset13d/cli_probe.py` (one trivial request;
   prints both windows and their resets). Give every stream its `--limit`.
1. **Connection capsule**, once `ext_status.py` shows the supervisor
   `complete`: `python D:/RAG_new/.tmp/external/collect_connection.py` (writes
   `reports/external/36f1167/connection.json`), then
   `python D:/RAG_new/.tmp/external/render_connection.py` (writes
   `docs/evidence/external-bases-connection.md` and runs the five checks of
   the untracked test). Then one row in `EVIDENCE_INDEX.md` (class `measured`,
   the text says preparation), the plan row of 1.5/1.5c/1.5d, a line of
   `CURRENT_STATE.md` in place, the Mac gate
   (`tests/test_external_connection_artifact.py`,
   `tests/test_external_bases.py`, the three docs tests), a local commit.
2. **1.3d, the checks** — one stream:
   `scripts/devset_label_verify.py verify --set development --round 1 --verifier claude-opus-5-5 --limit N`
   (30 requests, about $11 and 75 minutes), `decide --set development --round 1`,
   then `scripts/devset_label_repair.py plan|repair|build --set development`,
   round 2 with `--repairs`, `apply`, `check`. The same for `holdout` (62
   requests, about $22). Replacements once a set
   (`--set development-replacements`), `python -m evaluation.devset_minimums`,
   clusters and the MDE again, the capsule with its index row and artifact
   test. Commit `c43f0a0` shows the files each step wrote for `pilot-v3`.
   Then the screening tier, or its G32 outcome.
3. **2.8.** First the cold read: the frozen tree and the brief are ready in
   `D:/RAG_new/.tmp/nli28/coldread-7dd2ed090095/` (`BRIEF.md`,
   `MANIFEST.json`) — one fresh-context reader on the session's model, each
   finding applied or refuted in writing, the entry in the spec's header log
   completed. If a text of the prompt changes: new SHA constants in
   `evaluation/nli_validation.py`, the two lines of the spec, and
   `python -m scripts.nli_reference plan` again. Then `send --limit N` (436
   requests of stage 1), `next`, `send`, `derive`, `check`. Still to write:
   the judges' runner for the Mac (cells M0–M2 × two hypotheses × two
   premises, and M3, over the sample and its top-up reserve; raw logits a
   pair; it runs after the pilot) and the criteria module (out-of-fold κ,
   recall of «not supported», the system difference), then the capsule.
4. **1.6, after the pilot**: `D:/RAG_new/.tmp/external/extpilot_ctl.py`
   (its docstring gives the commands) fetches the two `*.aggregates.json`;
   `python -m scripts.external_pilot sizes …`;
   the capsule (aggregates only), its index row and test; then the eleventh
   revision of the spec with a cold read of its own.
5. **1.7** after that revision. **1.3e** after 1.3d: a lock file with the
   path, SHA-256, count and ids of the holdout and `opened: []`; a module
   that mirrors `evaluation/external_parts.py`; a refusal in
   `scripts/production_baseline.py`; a test.
6. **The report to Julia**, first the filter decision, then the list of «What
   is the agent's choice».

## Lessons

- **A stream is sized at its launch.** I started the holdout drafts without
  the limit, against my own rule. `TaskStop` reported success and left the
  processes alive; the auto-mode classifier refused a script that stops them,
  and a usage probe beside the living stream. The stream ended by itself two
  requests later. Pass `--limit`; read the launch line once more.
- **The windows can be measured**; do it before a stream, not after a refusal.
  The session costs as much as a stream: at a short window, silence helps.
- **`cli_exit` happens** — twice in 66 holdout requests. The position stays
  pending; run the stream again.
- **Edits of code go through the Edit tool.** A heredoc script lost the
  backslashes of a regex and stopped half-way.
- **A summary after compaction misplaces things.** Borders of the session come
  from the transcript and `git log`, as in «Log» above.
- **An output that may hold holdout text is masked first**, then looked at.

## Glossary

- **H, Hm** — the 100 historical cases and the 15 multi-document ones.
- **Development, holdout** — the two new sets of 1.3d (60 and 64 positions by
  the split of 1.3c); the holdout is locked in 1.3e and opened once, in 4.1.
- **Cluster** — the cases joined by a document family; the unit of every
  interval. **MDE** — the smallest effect a comparison can detect.
- **Rule (a), (b), (c)** — the three ways a slice counts (`CLAUDE.md`);
  **preparation** is work that meets none yet.
- **Capsule** — a file in `docs/evidence/` with a number's provenance, its row
  in `EVIDENCE_INDEX.md` and an artifact test.
- **D7, D11, D12** — the owner's decisions: three external bases; no people in
  the quality process; one model. **G32, G38, G39** — gaps of the plan.
- **Isolated request** — one stateless request through
  `evaluation/isolated_request.py`: nothing loaded but the registered prompt,
  a record of the session kept. **Stream** — such requests one after another.
- **Draft, check, repair, drop, replacement** — a case written by the
  generator; its verification; one correction by the same model; its removal;
  a new draft for the freed position. **Wide scan** — a search of the corpus
  for evidence a draft missed, run on the Mac before the check.
- **Screening tier** — 360 further positions with one check and no repair.
- **Supervisor** — the Mac process that embeds and indexes the bases one by
  one. **Pilot runner** — the one that measures 1.6 after it.
- **Parts** — tuning, locked, reserve, excluded: the registered division of a
  base. **Arms** — `control` (production defaults), `pool30`.
- **NLI judge** — a small entailment model that scores whether a line of an
  answer is supported by its contexts. **Reference** — the labels it is
  compared with; **unit** — one line of an answer; **stable** — both passes
  gave it the same reduced label; **control** — a unit shown beside foreign
  contexts; **top-up** — more units when too few are «not supported»;
  **strata a1–a4, b1–b3** — by source (C.1a, C.1b), NLI score and overlap.
- **Probe** — the request that reads the usage windows. **Wip branch** — a
  local backup commit built through a temporary index.
- **Cold read** — a read by a fresh-context session of the same model, on a
  frozen copy.

## Verification

- `git -C "D:/RAG_new" status --short` and `log` at the close: as in «State».
- Mac tests of this session's last commits: 44 passed (2.8 with the docs
  tests), 156 passed (drafting, wide scan, label checks, minimums), 58 passed
  (wide scan, label verification v3). The full suite was not run.
- Mac state: `ext_status.py` at 10:28Z, as in «State».
- This file was not read cold when first committed; the record of its read,
  if one was made, is in the line below.

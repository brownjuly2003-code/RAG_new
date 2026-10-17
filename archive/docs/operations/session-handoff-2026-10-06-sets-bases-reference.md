# Session handoff — 2026-10-06, sets drafted, two bases indexed, reference registered

Written 2026-10-06 at about 10:45Z, when Julia asked whether she could close
the session, and corrected the same day after a cold read (see
«Verification»). The session ran from 2026-10-05T21:53Z (transcript
`f833a800-…`). Read `CLAUDE.md`, `CURRENT_STATE.md`, `ROADMAP.md`, then this
file; the commands are in the [runbook](runbook-2026-10-06-next-actions.md).
The [log of 2026-10-05](session-handoff-2026-10-05-one-model-and-sizes.md)
explains what one model can and cannot claim and is not repeated here.

Nothing is lost by the close: every result is in a local commit, and the two
runs on the Mac go on by themselves. What stops is the session's own
continuation — nobody collects the Mac's results or sends the next requests
until a new session starts from this file.

## What matters to understand

**How the system works now.** The product is unchanged: no default moved,
`RAG_GRAPH_RETRIEVAL` stays `off`. Everything below is the measuring side of
the quality plan [`plan_03_10_26.md`](../specs/plan_03_10_26.md): sets,
baselines, judges, registrations. «The spec» is
`docs/specs/semantic-precision-metrics.md`; the runbook names its headings.

**The question.** The plan's first campaign asks whether a retrieval mechanism
(H1 first) can be shown to gain under a rule registered in advance. The ten
slices of this session build what that campaign measures with. None changes
the product, so none counts by rule (a).

**Where each of the ten stands.** The list is my reading of her «10 следующих
слайсов»: the plan's order of dependencies after 3.0.

| Slice | What it is | State at the close | Counts as | What closes it |
|---|---|---|---|---|
| 2.5 | production baseline on H and Hm with its loss map (task T-65) | **closed**, `ba8285d`, [capsule](../../../docs/evidence/production-baseline-h-hm.md) | (c) | — |
| 1.3c | variance pilot, sizes of the sets | **closed**, `c5817d0`, [capsule](../../../docs/evidence/variance-pilot-gold-metrics.md); no verdict by design | (c) by its status row, preparation by its rule column — open, below | — |
| 1.3d | verified development and holdout sets, then a screening tier | both sets drafted, scanned, first check planned; **no check request sent** | preparation: a set verified by a model is not rule (b) | checks, repairs, replacements, minimums, tier, capsule |
| 1.3e | lock of the holdout | not started; design under «Next actions» | preparation | the holdout register |
| 1.5, 1.5c, 1.5d | connect ConditionalQA, WixQA, MultiHop-RAG | two bases embedded and indexed, WixQA embedding on the Mac | preparation | one capsule for the three |
| 1.6 | parts, lock and pilot of the external bases | registered, `64a72e5`; the pilot is queued on the Mac | preparation | pilot → capsule → eleventh revision of the spec |
| 1.7 | control baseline on the external bases | not started, its runner not written | (c) once published | after the eleventh revision; about three Mac nights |
| 2.8 | validation of the NLI judge | reference registered, `7dd2ed0`; **no request sent, no judge run** | (c) once published | cold read → labelling → judges on the Mac → criteria → capsule |

**What is established.** The baseline: `precision_at_5` 0.5354 on H (n 99) and
0.6800 on Hm, one judge with a retest. The sizes: development 60 cases in 37
clusters, holdout 64 in 18; the registered MDE of the deciding metrics is
0.17–0.30 against the rule's +0.05, so the campaign can show effects of that
size and no smaller ones. Development is the 30 pilot cases checked again
under rubric v3 (`pilot-v3`: 30 verified, 0 dropped) and 30 new positions, all
30 drafted. Holdout: 62 of 64 positions drafted; the generator declined
positions 5 and 19. Where a brief asked for a quantity, the draft carries it
as asked in 0 of 7 positions of development and 1 of 14 of holdout; the
generator prompt was not changed after the first count, and both counts go
into the capsule.

**Two holdout minimums are already short, before any check.** At 64 positions
the minimums are RU→EN 13, numeric 13, traps 13 in all five types and
safety-critical 7 (`evaluation/devset_minimums.py`). The 62 drafts hold RU→EN
36; numeric 10; traps 20 in four types — `outdated_rule` was asked in three
positions and written in none; the safety-critical flag 10, but the count
that decides is narrower (the flag, not `authority_unverified`, a span that
quotes the rule). A check can only lower a count. An unmet minimum is
published as unmet and narrows the conclusion; nothing is added to fill one.
Julia has not been told yet.

**Two long poles.** The Mac: WixQA embedding (to about 13:30Z on 2026-10-06),
then the pilot of 1.6 by itself (16–19 h, to about 06:00–09:00Z on
2026-10-07), then one night of NLI judges for 2.8, then three nights of 1.7.
The request stream: every draft, check and reference label is one isolated
request of `claude-opus-5-5`, one stream at a time; about 55–60 hours of
stream are left. Neither pole waits for the other.

**The subscription is the scarce resource.** The isolated requests spend
Julia's subscription, as the session does. Measured on 2026-10-06: 0.01 of
the weekly window is about $10 API-equivalent. A draft costs $0.61 (mean and
median; the 66 holdout requests cost $39.14); a check $0.36 mean and $0.32
median (the 30 checks of `pilot-v3`: $10.72, median 113 s). What is left, by
those means: development checks $11, holdout checks $22, repairs, second
rounds and replacements about $15, the screening tier 360 × $0.97 ≈ $350 —
about twice that if its first pass is rejected — and 2.8, 436–482 requests
whose cost nobody has measured. Together $450–500 if the tier passes at once:
near half of a weekly window. At 11:43Z the weekly window stood at 0.97
(reset 2026-10-06T22:00Z), the five-hour one at 0.44 (reset 12:50Z). My line
was 0.96: the streams stopped at 0.95, and the cold read of this file with
the session's own turns took the rest. Until 22:00Z there is room for no
stream.

**Three things a session must not read.**
- *Holdout texts.* My own rule, not a registered one: under D12 the model
  that will choose mechanisms and settings is the model in the session, and a
  holdout it has read holds nothing out. No text of a holdout draft entered
  this session — I read counts, masked outputs and the numeric fields of the
  manifest. The files are tracked and no guard stands before them: the paths
  and the procedure are in the runbook, section 2. Keep it so until 4.1.
- *External bases.* ConditionalQA is for research use only; the registered
  rule (`evaluation/external_bases.json`) lets out aggregates, attribution and
  provenance — no question, evidence string, document, chunk or embedding of
  any of the three is committed or published. Their data lives under
  `D:/RAG_new/.tmp/external/bases/` and `…/raw/`, and on the Mac under
  `/Users/julia/RAG_new_external/`; the pilot's `<base>.json` holds a row a
  question and stays on the Mac.
- *Verdicts of 2.8 before `derive`.* The stores `pass*.jsonl` and
  `control-pass*.jsonl` are not opened; a script prints ids and counts only.

**How to read what comes next.**
- *Connection capsule (1.5, 1.5c, 1.5d)*: preparation, not a quality number.
  It says whether each base was converted, chunked, embedded and indexed with
  nothing lost, and that our own corpus and index did not change. Its hours
  carry foreign load — the Mac did other work beside — and are no evidence of
  speed.
- *Pilot of 1.6*: variances and seconds, from which the sizes of the parts and
  the nights of 1.7 are read. Until the measure document of a base is written
  nothing is final: a stopped run is resumed; one that cannot be resumed, or
  that the measure refuses, has measured nothing — the fault is fixed by a
  commit, the run made again, and what stopped is published by stage and
  error type. Once the document exists, that base is not run or measured
  again. So a runner that shows `failed` or `stopped` has a fault to fix, not
  a result to publish. (The first version of this file said the opposite.)
- *Checks of 1.3d*: every draft ends verified, repaired once or dropped; a
  freed position gets one replacement. The step closes only with the tier
  built or given up by its own rule.
- *2.8*: first the stability bound of the reference. If it fails, the rubric
  is clarified once and the whole sample labelled again; a second failure
  makes the judge `provisional_judge`. If it holds, the criteria are
  out-of-fold κ ≥ 0.6 with a CI95 lower bound ≥ 0.4, recall of «not
  supported» ≥ 0.7 and a system |Δ| ≤ 0.05 on each source; a judge that meets
  them is `single_model_referenced` «on N of M units» — never human-validated.

## Julia's requests and decisions this session

| # | Her words | What it became |
|---|---|---|
| 1 | 2026-10-05T21:53Z: «НЕ ГРУЗИ СКИЛЛ MYFLOW_NEW. Не разворачивай на этой машине wsl, docker и подобное. Для этого используй мак. Тесты также прогоняй на маке. Работай сам - все делай сам, работай НЕ ПО MYFLOW_NEW (то есть не привлекай к работе другие модели) - тебе все нужно делать самому. Возьми в работу 10 следующих слайсов.» | no MyFlow command, no other model; pytest on the Mac only; the ten slices above |
| 2 | 2026-10-06T10:40Z: «могу закрыть сессию?» | answered yes; the local wait job stopped; this file and its runbook |

She decided nothing else in this session. Still binding from earlier ones:
D11 — no people in the quality process; D12 — one model does every job and
check.

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
   for the 1.3d section, once for this file. The 2.8 block has been read by
   its author only.
8. **The holdout is not read by the session.** It collides with a registered
   sentence: the holdout drops on `repair_not_possible` are published «with
   their reasons word for word» (spec, «Drafts of plan step 1.3d»), and a
   capsule is a file the session writes. My proposal, before the first holdout
   repair request: amend the spec so that a script puts those reasons into a
   committed file of their own and the capsule gives its path, SHA-256 and
   the counts.
9. **No push.** `CURRENT_STATE.md` (§1) and `AGENT_STATE.md` call commits and
   pushes delegated; my note of her words is that «сам» grants no push, and
   her global rule asks before one. I held it.
10. **Carried over and not yet told to her**: the decisions of the 3.0 spec
    (plan row 3.0); the rewrite of `CLAUDE.md` and of the memory index on
    2026-10-05; T-65's choices — where artifacts are committed, the ledger's
    wording for a run without a verdict (its
    [handoff](t65-baseline-handoff.md)); from 1.3c the tool
    `scripts/model_requests.py`.

## Once Julia decides

A bullet with no answer in it has none.

- **Two decisions are cheap only until the pilot of 1.6 is measured** — the
  first measure document (WixQA) can exist an hour after the pilot starts,
  near 14:30Z on 2026-10-06.
  - *The product's filter* (plan §3, «06.10, открытое решение из пилота
    1.3c»). The grading filter is in part a draw: another verdict on the same
    question and document in 9 of 168 shared documents; its batch request
    gave no grade a document in 187 of 187 contexts and took half of the
    grading seconds. A change before the campaign buys about 331 s a case
    through grading instead of 627 — 87 passes a night instead of 46 — and
    takes the draw out of the paired differences. It costs a change of the
    product outside the campaign's mechanisms and the 2.5 baseline taken
    again (19 Mac hours); once the pilot is measured, the pilot too describes
    the old filter and is not measured twice. Default: the filter stays.
  - *The ceiling of acceptance step 1*: eight nights of eight hours for two
    arms on both bases; above it the pages of ConditionalQA are cut (164 of
    165 fit at the means of 1.3c). It is hers to move, in the plan: moved
    before a pilot is measured it is the registered ceiling, moved after it
    is a deviation the eleventh revision must show. Default: eight nights.
- **Push.** `master` is 28 commits ahead of `origin/master` (`f7416ca`); the
  work exists on this laptop only. On her word: runbook, section 8.
- **The screening tier.** The plan requires it for 1.3d; its code does not
  exist; it costs about $350, or twice that. Nothing registered lets it be
  skipped for cost: G32 gives it up only when more than 10 % of it is
  rejected twice. Default: the checks, repairs, replacements and 2.8 run
  first and the tier's code is written; the first screening request is the
  last cheap point to stop, and a new session looks for her answer before it.
  Without one the work goes on as registered.
- **The line at 0.96.** Mine and reversible: she may let the streams run to
  the limit, or stop them lower.
- **The holdout reasons** (choice 8) and **the label of 1.3c**: its status
  row and `CURRENT_STATE.md` say rule (c), its rule column says preparation.
  My reading: (c) for the measured variances, a registration for the sizes;
  the plan should say one thing.
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
| `40a2fee` | this file, first version |
| the next | this file corrected after its cold read; the runbook |

The supervisor of the external bases was started on the Mac before this
session (its state file says 2026-10-05T16:45Z) and began to work at
2026-10-06T03:34Z, after the 1.3c pilot. This session launched the pilot
runner of 1.6, which waits behind it.

## State at the end

- **Git**: `master`, 28 commits ahead of `origin/master` with the one that
  carries this text — 18 of earlier sessions, 10 of this one; nothing pushed.
  Untracked: `demo/phase-e-raw.webm` (not ours, never staged) and
  `tests/test_external_connection_artifact.py` — it fails until the
  connection capsule exists, so it stays out of gates and commits until then.
- **Laptop**: no stream, no monitor, no background job. Scratch tools are on
  disk under `D:/RAG_new/.tmp/` (git-ignored) and in the local branch
  `wip/plan-1.6-1.3d` (see «Verification»; not pushed).
  `.tmp/external/rehearsal/` is a dry run of the capsule step, not a result;
  `.tmp/devset13d/STOP_NOTE.md` is overtaken by this file.
- **Mac, supervisor of the bases**: pid 64907, snapshot
  `/Users/julia/RAG_new_ext_a0d438c0c25c` (code `36f1167`), state
  `/Users/julia/RAG_new_external/ext-state.json`. ConditionalQA: 13,778
  chunks, embedded in 6,977 s. MultiHop-RAG: 11,231 chunks, 8,227 s. WixQA:
  37,571 chunks, embedding since 07:48Z, about 26.7 thousand done at 11:43Z.
- **Mac, pilot runner of 1.6**: pid 99859, directory
  `/Users/julia/RAG_new_extpilot_f6c2bfa7a915` (code `64a72e5`), state
  `.tmp/extpilot-state.json` there, status `waiting`. It starts by itself
  when the supervisor's processes end: WixQA through `retrieve`, then
  ConditionalQA through `grade`, arms `control` and `pool30`.
- **Requests**: none in flight. 2.8 — none ever sent, no store exists.
  Development and holdout — no check request sent.

## Do not

- Push without her word in the session.
- Start a stream before a probe, without `--limit`, beside another stream, or
  before 22:00Z on 2026-10-06; probe beside a living stream.
- Open a holdout path (runbook, section 2), or a store of 2.8 before `derive`.
- Commit, print or send a file of an external base; copy the pilot's
  `<base>.json` off the Mac.
- Run or measure again a base whose measure document exists; publish a
  `failed` runner as the pilot's result.
- Run tests on the Mac in the minutes after the supervisor ends; run a wide
  scan or the judges beside a measured run.
- Start a MyFlow command, another model, or a heavy run on the laptop.
- Stop processes by a pattern: the classifier refused it, and that refusal
  stands for the outcome, not for one command.

## Next actions, in order

0. **The report to Julia, in Russian, before any work.** In this order: the
   two decisions that are cheap only until the pilot is measured, with their
   defaults; what closed (2.5 and 1.3c, with their numbers), what is
   registered (1.6, 2.8), what is drafted; the holdout minimums already
   short; what runs on the Mac and when it ends — its hours with the
   foreign-load caveat; the subscription — the windows, the cost left, the
   tier; nothing pushed, 28 local commits; then «What is the agent's choice».
1. **Probe** (runbook 1), not before 22:00Z on 2026-10-06.
2. **Connection capsule** (runbook 4), once the supervisor is `complete` with
   `guarded_unchanged` true — expected near 13:30Z on 2026-10-06.
3. **Checks of 1.3d** (runbook 5): development (30 cases), then holdout (62)
   with every output to a file; repairs, round 2, replacements, minimums,
   capsule. Before the first holdout repair, the amendment of choice 8.
   `run_scan_remote.py` takes no replacement set yet. Then the tier's code.
4. **2.8** (runbook 6): the cold read, the labelling from `--limit 10`, the
   judges' runner and the criteria module — both unwritten — and the capsule.
5. **1.6 after the pilot** (runbook 7), about 06:00–09:00Z on 2026-10-07:
   aggregates, sizes, capsule, the eleventh revision with its cold read.
6. **1.7** after that revision; its runner is unwritten. **1.3e** as soon as
   the holdout register is complete — my reading of plan row 1.3e, which does
   not wait for the tier: a lock file with the path, SHA-256, count and ids
   of the holdout and `opened: []`; a module that mirrors
   `evaluation/external_parts.py`; a refusal in
   `scripts/production_baseline.py` and a check in the verify script; a
   capsule with the ids and the SHA-256; a row of the ledger; a test.
7. **Push**, on her word (runbook 8).

## Lessons

- **A stream is sized at its launch.** I started the holdout drafts without
  the limit, against my own rule. `TaskStop` reported success and left the
  processes alive; the auto-mode classifier refused a script that stops them
  by pattern, and a probe beside the living stream. I took neither by another
  route and deleted the script. The stream ended by itself two requests
  later. Pass `--limit`; read the launch line once more.
- **The windows can be measured**; do it before a stream, not after a refusal.
  The session spends them too: at a short window, silence helps.
- **A cold read costs as a stream does.** The read of this file took 53
  minutes — I had told Julia ten — and with the session's turns 0.02 of the
  week. Narrow the brief; a subagent returns its findings as text and cannot
  write the report file.
- **`cli_exit` happens** — twice in 66 holdout requests. The position stays
  pending; run the stream again. `unavailable: cli_response` about the
  session record is another thing: the CLI changed (the route registers
  version 2.1.289) — stop and register the new version before a request.
- **A registered rule is quoted, not remembered.** The first version of this
  file gave the pilot's rule backwards.
- **Edits of code go through the Edit tool.** A heredoc script lost the
  backslashes of a regex and stopped half-way.
- **A summary after compaction misplaces things.** Borders of the session come
  from the transcript and `git log`, as in «Log» above.

## Glossary

- **H, Hm** — the 100 historical cases and the 15 multi-document ones.
  **H1** — the first mechanism of the campaign, the graph branch with a
  budget of 40. **3.0** — the policy of enabling the graph, registered before
  this session (`0874953`). **T-65** — the task of slice 2.5. **4.1** — the
  acceptance step, where the holdout is opened once.
- **Development, holdout** — the two new sets of 1.3d (60 and 64 positions by
  the split of 1.3c). **Cluster** — the cases joined by a document family;
  the unit of every interval. **MDE** — the smallest effect a comparison can
  detect. **Deciding metrics** — the closed table of the spec: the primary
  (`sent_precision` or `all_evidence_coverage`) must gain 0.05 with a CI95
  above zero, the others must not fall by more than 0.02.
- **Loss map** — the stage at which a case first loses its evidence: index,
  pool, rerank cut, sent context.
- **Rule (a), (b), (c)** — the three ways a slice counts (`CLAUDE.md`);
  **preparation** is work that meets none yet. **Capsule** — a file in
  `docs/evidence/` with a number's provenance, its row in `EVIDENCE_INDEX.md`
  and an artifact test. **Ledger** — the plan's list of the campaign's runs.
- **D7, D11, D12** — the owner's decisions: three external bases; no people in
  the quality process; one model. **G32** — the plan's rule that gives the
  tier up when more than 10 % of it is rejected twice.
- **Isolated request** — one stateless request through
  `evaluation/isolated_request.py`: nothing loaded but the registered prompt,
  a record of the session kept. **Stream** — such requests one after another.
  **Probe** — the request that reads the usage windows.
- **Generator, verifier** — the same model in separate isolated requests.
  **Brief** — what a position asks of the generator: class, trap, flags,
  document families. **Flags** — `ru_to_en`, numeric, `safety_critical`,
  `adversarial_unanswerable`. **Rubric v3** — the checks a draft must pass.
- **Draft, check, repair, drop, replacement** — a case written by the
  generator; its verification; one correction by the same model; its removal;
  a new draft for the freed position. **Wide scan** — a search of the corpus
  for evidence a draft missed, run on the Mac before the check.
- **Screening tier** — 360 further positions with one check and no repair.
- **Supervisor** — the Mac process that embeds and indexes the bases one by
  one. **Pilot runner** — the one that measures 1.6 after it. **Measure
  document** — the runner's `<base>.json`; `<base>.aggregates.json` is the
  part that may leave the Mac. **Foreign load** — other work on the Mac
  during a timed step.
- **Parts** — tuning, locked, reserve, excluded: the registered division of a
  base. **Arms** — `control` (production defaults) and `pool30`
  (`retrieval_top_k` 30). **Eleventh revision** — the next one of the spec:
  it registers the sizes and nights read from the pilot.
- **NLI judge** — a small entailment model that scores whether a line of an
  answer is supported by its contexts. **Reference** — the labels it is
  compared with; **unit** — one line of an answer; **stable** — both passes
  gave it the same reduced label; **control** — a unit shown beside foreign
  contexts; **top-up** — more units when too few are «not supported»;
  **C.1a, C.1b** — the two archived answer runs the units come from;
  **strata a1–a4, b1–b3** — by source, NLI score and overlap. **M0–M3** —
  the judge models compared, each with two forms of the hypothesis (H0, H1 —
  not the mechanism) and of the premise (P0, P1). **Out-of-fold κ** —
  agreement with the reference on units the threshold was not fitted on.
  **System |Δ|** — the gap between the judge's and the reference's score of
  a whole source.
- **`TaskStop`** — the harness tool that stops a background job.
  **Auto-mode classifier** — the harness check that may refuse a command.
  **Lifted guard** — the hooks under `.myflow/guard/` switched off; never
  done. **Wip branch** — a local backup commit built through a temporary
  index.
- **Cold read** — a read by a fresh-context session of the same model, on a
  frozen copy.

## Verification

- `git -C "D:/RAG_new" status --short` and `log` at the close: as in «State».
- Mac tests of this session's last commits: 44 passed (2.8 with the docs
  tests), 156 passed (drafting, wide scan, label checks, minimums), 58 passed
  (wide scan, label verification v3; read from the terminal, no log kept);
  the three docs tests before the commit that carries this text. The full
  suite was not run.
- Mac state: `ext_status.py` at 11:43Z, as in «State».
- Cold read: one fresh-context reader on the session's model read the first
  version (frozen copy, SHA-256 `f3aa5fec…`) against the repository and
  returned 28 findings — 2 blockers, 12 major, 14 minor. Each is applied here
  or in the runbook; of one, the two tar archives of the Mac snapshots stay
  out of the backup (`git archive` rebuilds them). The reader could not write
  its report file: the findings are in the session's transcript. This version
  and the runbook were not read cold again.
- Wip branch: `wip/plan-1.6-1.3d` is rebuilt on the commit that carries this
  text. `git -C "D:/RAG_new" log -1 --format=%P wip/plan-1.6-1.3d` must name
  that commit; a tip on an older parent is the backup of 03:08Z, which lacks
  the tools of the next actions.

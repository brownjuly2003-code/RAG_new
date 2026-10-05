# Session handoff — 2026-10-05, one model does everything; sizes registered

Written for the next session because Julia asked for a stop point: «поставь
точку, где логично и обнови доку». The session ran from 2026-10-04 23:28 UTC
into 2026-10-05 on her request to take the next ten slices of the quality plan
([`plan_03_10_26.md`](../specs/plan_03_10_26.md)) and to do all of it itself.
**Of the ten, one is finished (1.3b), two are in work (2.5, 1.3c) and seven are
not started. Under the project's acceptance rule none counts yet, and no
quality number was published:** 1.3b and 1.3c are preparation in the plan's own
table — a model's check is not an approval, so the count of real labelled cases
did not rise (rule (b)) — and 2.5 counts under rule (c) only once its capsule
is published. Twelve commits are local and not pushed: ten code commits of
this session, one of the session before it (`693828c`) and the commit that
adds this file. `git -C "D:/RAG_new" status -sb` must show
`master...origin/master [ahead 12]`. The engineering detail of slice 2.5 is in
[`t65-baseline-handoff.md`](t65-baseline-handoff.md), section «T-65 judging
part done — 2026-10-05».

## What matters to understand

**The thread.** The official gate is lexical `context_precision` ≥ 0.63 on H,
and no arm reaches it. The quality plan builds a second, semantic ruler for
development, a development set and a locked holdout, picks at most two
mechanisms from an evidence-loss map, and ends in one research acceptance
(slice 4.1). The full story is in the
[2026-10-03 log](session-handoff-2026-10-03-plan-revision.md); this file adds
what the two days after it changed.

**Change 1 — one model (decision D12).** On 2026-10-03 Julia took people out of
the plan (D11), and I put "models of two vendors" in their place. On 2026-10-04
the session sent one verification request to GLM 5.3, as the registered rule
said, and she interrupted it: «А причем тут glm??? ты должен все делать
сам!!!». Since then the session's model, Claude Opus 5.5, does every job and
every check, and no other model is called in any role — executor, reviewer,
verifier, judge, reference, repair author — even where a registered rule names
one. Sonnet shares the vendor and left the judge all the same: in the session
before this one she had written «не нужно использовать другие модели». A
subagent, where one helps, runs on the same model, as the cold reader of this
file did (my reading). The rule stands over the line «Executor: GLM 5.3» of the
project `CLAUDE.md` and its Codex fallback until Julia edits that line herself.
What stands where two vendors stood is weaker, and the documents say so:

| Job | Under D11 | Under D12 | Status word | Not claimed |
|---|---|---|---|---|
| Check the 30 pilot drafts (1.3b) | two verifiers, two vendors | one verifier, rubric `label-verification/v2` | `single_model_verified` | `model_verified` |
| Check the drafts of 1.3d | the same | the model that drafts also checks, rubric v3 | `single_model_self_checked` | any outside view |
| Grade new texts (2.5 on) | consensus of GLM and Sonnet | one judge, a stability retest, contamination controls | `single_judge` | `model-cross-checked`; a delta to a consensus number |
| Reference for the NLI judge (2.8) | majority of three vendors | agreement of two passes of one model | `single_model_referenced` | a majority |
| Check holdout answers (4.1) | two models, two vendors | four kinds of request in two passes, a third on a disagreement | a capsule line | a second voice |

Three devices replace a second voice. *Isolation*: each check is a new process
with nothing but the registered prompt. *Repetition*: the same request again,
in another order. *Contamination controls*: a text whose evidence was cut out,
so the right direction of the grade is known without a second grader. None of
them sees an error Opus makes every time (plan gap G37, sharper now). Passes
of one model are not votes.

**Change 2 — the clean route.** `evaluation/isolated_request.py` runs
`claude -p --safe-mode --model claude-opus-5-5 --tools ""` from an empty
directory, the request on stdin, and keeps a record of the session beside the
reply; a reply without the record is not read. A probe showed that the earlier
route also carried Julia's global instruction file and the output of two
hooks. The 35 requests of T-78 and the Opus reference sample of P2 went by that
earlier route; their capsules say it, and the verdicts stay published. The 30
pilot cases are checked again under rubric v3 in step 1.3d (next action 5),
the two sets of verdicts side by side; a case rejected there is repaired or
dropped like any other. The variance pilot does not wait for that: its case
file is fixed by SHA-256 in the spec, and it decides nothing about a case.

**What is established.** Each row gives its criterion.

| Item | State | Criterion or limit |
|---|---|---|
| 1.3b, pilot drafts | **done**: 30 verified, 0 dropped — 25 at the first check, 5 after a repair by the same model ([capsule](../evidence/devset-pilot-label-verification.md)) | a script finds every span verbatim in its source (check 1); the model confirms that the facts follow from the spans (2), the question is answerable from them (3), class, flags and expected action fit (4) and the critical facts are the right ones (5d); it does not reject the authority documents (5a in force, 5b the controlled source); its severity (5c) is within one step of the registered one, on the same side of `critical`. Preparation: rule (b) is not met |
| 2.5, collection (T-65) | **complete**: H 100 + Hm 15 from `68c5f8d`, no case excluded, one sent document without a chunk address (listed as unjudged). An earlier session started it on 2026-10-04; it ended on 2026-10-05 05:16 UTC | complete = the supervisor's status after all five stages, 115 of 115 cases; `NOT_EVIDENCE` until the capsule exists |
| 2.5, judging | **part done, stopped at the stop point**: 48 of 115 requests hold a valid reply; no judge process is running | 115 requests, one a case, each needs a valid reply; then the retest, 20 requests more by a second command. No contamination controls in this slice |
| 1.3c, sizes | **registered** at `323ce00`: the split, both sizes, the MDE of every deciding metric. The variance pilot has **not run** | a pilot may raise an MDE, never lower it; the sizes do not depend on it |
| Plan gap G38 | all eight questions closed in the [spec](../specs/semantic-precision-metrics.md), the last five for one model | closed = each question has a registered rule; read cold by sessions of the same model only |

**Change 3 — what the campaign can show.** This is the finding to carry to
Julia. Development is to be 60 cases in 37 clusters — the 30 verified pilot
cases and 30 that step 1.3d drafts; the holdout 64 in 18, all still to be
drafted. A cluster is a group of cases that share a document family, and the
interval of the decision rule resamples clusters, not cases. The acceptance
rule wants a gain of +0.05 on the primary metric with a CI95 lower bound above
zero, and non-inferiority at −0.02 on the others. The registered MDE — the
smallest true effect seen with power 0.8, taken at the cautious end — is:

| Split | Population | n | Clusters | Registered MDE |
|---|---|---|---|---|
| development | all cases | 60 | 37 | 0.171 |
| development | cases with gold evidence | 48 | 32 | 0.184 |
| development | unresolvable cases | 12 | 11 | 0.303 |
| holdout | all cases | 64 | 18 | 0.224 |
| holdout | cases with gold evidence | 51 | 18 | 0.229 |
| holdout | unresolvable cases | 13 | 12 | 0.287 |

The table is computed, not measured: it assumes a variance of 0.10 for the
paired differences and cases of a cluster that move as one — the cautious end,
my choice. The rows "cases with gold evidence" carry the primary metric —
`sent_precision` or `all_evidence_coverage`, one named for a mechanism before
its run — and `evidence_recall_pool`, `fact_coverage`, `answer_fact_coverage`,
`citation_correctness`; "all cases" carry `precision_at_5`, `action_correct`,
`faithfulness`, `citation_presence`; "unresolvable cases" carry
`abstention_correct`. Read it this way:

- **A true gain of +0.05 will most likely not be shown.** On the registered
  rows the power of the whole primary rule at +0.05 is 0.04–0.12: 0.10 in
  development and 0.07 in the holdout for the primary metric, where only a
  true gain near 0.23 is detected four times out of five. At the favourable
  end of the grid — variance 0.05, every case independent — it is 0.34 and
  0.36, and the MDE is still 0.09 (`evaluation/power.py`; the capsule of 1.3c
  prints the whole grid).
- **A neutral mechanism is expected to end `INCONCLUSIVE`,** not `SHIP_RESEARCH`:
  a non-inferiority check at a true zero has power 0.02–0.11. It passes with
  power 0.8 only at a true gain of 0.15–0.28, or where the metric is registered
  before the run as structurally unchanged by the mechanism.
- **`abstention_correct` is expected to have no valid interval** (11 and 12
  clusters; the rule needs ten of them to carry a difference).
- **The sizes cannot grow on this corpus.** A gain of +0.05 needs about 314
  independent clusters in each split at variance 0.10, and 157 at 0.05; there
  are 37 and 18. A cluster needs a family of its own, and the corpus has 49
  development and 35 reserve families. Seeing +0.05 would take several hundred
  new source documents on unrelated topics, which only Julia can add.
- The margin −0.02 is not widened (decision D9).

**And the plan's budget looks too low — a provisional reading.** The plan
counts 350 retrieval passes a night of eight hours and 17–22 nights for the
campaign. The collection of slice 2.5 took 19 hours for 115 cases, where the
plan gave it half a night; the collector's `grade` stage alone — the local
model reading each retrieved document, not the judge — has a median of 507 s a
case, about 50 passes a night, a seventh of the plan's count. That is one run
on one host, part of it under another project's load: not speed evidence. The
variance pilot on an idle Mac gives the first clean timing, and the capsule of
step 1.3c is to recompute the budget from it; this session did not.

**How to read the next results, and what to tell Julia.**

| Result | Criterion (registered in the spec) | What it means |
|---|---|---|
| Stability retest of the judge (T-65) passes | CI95 of quadratic-weighted κ between the two passes, over the whole sub-sample of 20 cases, entirely ≥ 0.7 | the grades are a `single_judge` ruler; the baseline numbers stand as those of the control arm — production defaults — which mechanisms are compared with. Say also: 0.7 is a low bar for one model against itself, and no other vendor and no person checked a grade |
| Retest fails | the interval reaches below 0.7 | `provisional_ruler`, no semantic gain claimed; the judge prompt is re-registered once and everything is graded again. A second failure closes the campaign without 4.1 |
| Retest is `NOT_EVIDENCE` | a pass misses more than 5 % of the units (a unit is a document graded in both passes), or κ has no interval | nothing closes; the ruler stays `provisional_ruler`; the holdout is not opened on that run. Next: send the unanswered requests again and read the retest then; a κ without an interval is final for the run |
| Contamination controls | none in slice 2.5: H and Hm carry no gold spans to cut or swap. They start with the first judged run on the verified set | say that no control stands behind the grades of 2.5 |
| Baseline numbers | — | not comparable as a delta with the published consensus numbers of P2 (H 0.6080, Hm 0.8400): another judge, and contexts widened by the production's parent expansion |
| Variance pilot at or under 0.10 | — | the table above stands |
| Variance pilot above 0.10 on a gold metric | usable only if (1) all 24 cases are measured in the control arm and in the perturbed one, (2) some chunk of the index holds a gold span whole, (3) the control arm's pool holds a gold span in at least one case | that row's MDE rises; nothing else moves |
| Variance pilot unusable | one of the three fails. (2) was checked before any arm and holds: 37 of 38 gold spans, `T64-16-E2` in no chunk (`.tmp/pilot/handoff_numbers.py`); (1) and (3) show only in the runs | published as description; the table stands; the capsule names the condition |

## Julia's requests and decisions this session

| # | Her words | What it became |
|---|---|---|
| 1 | 2026-10-04: «НЕ ГРУЗИ СКИЛЛ MYFLOW_NEW. Не разворачивай на этой машине wsl, docker и подобное. Для этого используй мак. Тесты также прогоняй на маке. Работай сам - все делай сам, работай НЕ ПО MYFLOW_NEW - тебе все нужно делать самому. Возьми в работу 10 следующих слайсов.» | no MyFlow command was run; pytest ran only on `deproject-mac`; the ten slices below |
| 2 | 2026-10-04: «А причем тут glm??? ты должен все делать сам!!!», then «зачем тебе нужен glm?» | decision D12 (plan §2): one request to GLM under rubric v1 had gone out and is not counted |
| 3 | 2026-10-05: «продолжи» | the work went on under D12 |
| 4 | 2026-10-05: «поставь точку, где логично и обнови доку» | the 1.3c registration committed, the pilot not started, this file |

The ten slices, in the plan's order of dependencies: 1.3b, 2.5 (T-65), 1.3c,
1.3d, 1.3e, 3.0, the graph lifecycle of 2.3 (conditional), 2.8, 2.6
(conditional), 3.1. The list is my reading of her «10 следующих слайсов».

From the session before this one, the same day, and still binding: «делай
далее в этой сессии все сам», then «я не про меня. я про работу по
myflow_new» and «не нужно использовать другие модели». She wrote the last two
after I had read «сам» as leave to do her own manual steps. So «сам» names a
way of working and grants nothing else: no push, no lifted guard.

## What is the agent's choice, not Julia's

D12 is one sentence and one stopped request. The rest is mine, and no other
vendor audited any of it — under D12 none can.

1. **What replaces two vendors**: isolation, repetition and controls, and the
   four status words of the table above.
2. **Rubrics v2 and v3**: a rejected case is repaired once by the same model
   and counted apart; under v3 the repair is a separate stateless request.
3. **One judge with a retest at κ 0.7**, a threshold registered for two
   graders and kept because no other number was registered.
4. **The designs of 2.8 and 4.1 for one model** (spec section «Checks by one
   model in slices 2.8 and 4.1»), including the rule that a model withdrawn by
   its provider stops the work until Julia decides.
5. **The sizes**: 60 and 64, a cap of four cases a holdout block, and the
   refusal to seat 98 cases — a cap of eight — in the same 18 blocks.
6. **The pilot's design**: three arms — `control`, `pool30`
   (`retrieval_top_k` 30), `sent3` (`rerank_top_k` 3) — over the 24 verified
   pilot cases with gold evidence. A pool of 40 is not an arm: 40 is the
   budget that hypothesis H5 registers.
7. **The registered MDE** at correlation 1, Student quantile, grid variance
   0.10: the cautious end, so that no later number makes the campaign look
   more sensitive than registered.
8. **Gold metrics by text containment** (`verified-gold/text-containment-v1`):
   the chunks of the index carry no offsets, so a span is found by its text.
9. **Review by the same model.** Each registered text was read cold by an
   isolated session of Opus 5.5. The 1.3c section got 12 findings (2 blockers,
   9 majors, 1 minor), all applied; nothing has read it since.
10. **The stop point**: no push (see «Once Julia decides»), the eleven-hour
    pilot not started, the judging stopped between two replies.

## Once Julia decides

Her answers, if she gives any before this session ends, are written into this
section; a bullet with no answer in it has none. Otherwise look in her first
message of the next session.

- **Push.** The project's standing delegation covers pushes
  (`CURRENT_STATE.md`, «Authorized push»). I held these commits back all the
  same: «сам» grants no push (my reading of her words above), and the twelve
  commits passed
  focused gates only, while a push runs the whole CI on `master`, which the
  order she fixed on 2026-10-03 — my recommendation, her «Зафиксируй» — wants
  green. The closing message of this session asks her. On her word: the full
  suite on the Mac first, then
  `git -C "D:/RAG_new" -c credential.helper='!gh auth git-credential' push origin master`,
  then the CI run. No backup branch was pushed either: it would upload the
  same commits. Until then the work exists on the laptop only.
- **The line «Executor: GLM 5.3» in the project `CLAUDE.md`** contradicts D12.
  The file is hers; I did not edit it. If she agrees, the line becomes "the
  session's model does the work; no other vendor's model is called (plan D12)".
- **The sensitivity of the campaign.** The plan budgets 17–22 nights of the Mac
  — more at the measured speed — for a campaign that, as registered, detects
  effects of 0.17–0.30 and no smaller ones. This is the one thing of the
  session she should hear in full, and the closing message tells her. Actions
  1–4 hold under any answer of hers, bar «do not run the pilot» below. The
  first draft of 1.3d (action 5) is the point of no cheap return: look for her
  answer before it. No answer means the work goes on as registered — her
  decisions are not awaited (plan D11). If she can add source documents, the
  family map and the split are rebuilt and registered again. If she wants
  another design — a larger margin, a development-only campaign, no holdout
  acceptance — that changes decisions D6–D9 and is a plan revision.
- **She brings back another vendor's voice.** The row of D12 in the plan says
  that is her decision. Rubric v1 (two verifiers) is registered and audited;
  the judge tool has not held the GLM and Sonnet routes since `d5c9ebb`, and
  its history before that commit has them.
- **She does not want the pilot run.** Then step 1.3c closes on the grid alone,
  and the capsule says the pilot was not run and why.

## Log

Commits, oldest first; all local.

1. `693828c` — T-77, the label-verification tool
   (`scripts/devset_label_verify.py`): the session before this one, unpushed.
2. `907313d` — rubric `label-verification/v2`: one verifier (D12).
3. `d5c9ebb` — one judge with a stability retest (`scripts/baseline_judge.py`).
4. `6fcf961`, `022d15e`, `f1cc525` — the baseline report
   (`scripts/baseline_report.py`), its rules registered before the first grade.
5. `0d3fe2b` — T-78: the run and the capsule of slice 1.3b.
6. `4bdead8` — `evaluation/power.py`. `d1fedd8` — the collector takes a case
   file and one moved setting.
7. `f3a350c` — the clean route, the judge on it, the spec's tenth revision
   (contamination controls; rubric v3 as text).
8. `323ce00` — step 1.3c registered: `evaluation/devset_split.py` with
   `devset_split.json`, `evaluation/gold_metrics.py`,
   `scripts/variance_pilot.py`, the spec section.

Outside the commits: the export of the T-65 collection was fetched to
`reports/baseline/68c5f8d/`, and the judging began at 06:55 UTC.

## State at the end

- **Git.** `master`, twelve commits ahead of `origin/master`, tree clean but for
  two untracked paths: `demo/phase-e-raw.webm` (not mine, never staged) and
  `reports/baseline/` (the T-65 export and the judge store, about 5 MB: data
  in progress, untracked until the run has its capsule).
- **Judging.** Stopped by the session between two replies, so that no
  background job outlives the stop point: 48 of 115 requests answered, 67 to
  go, about two hours of requests. It ran as a background job of this session
  and was stopped with it: no pass is alive. Store on the laptop:
  `D:/RAG_new/reports/baseline/68c5f8d/judge/opus.jsonl`. The same `judge`
  command resumes: it sends only the requests that hold no valid reply, a
  request that timed out among them (this happened once, and the second
  sending was answered). The command, the check for a live pass and the count
  of valid replies are in the T-65 handoff, «The chain from here».
- **Mac.** Idle since the collection ended. The run stays in
  `/Users/julia/RAG_new_t65_baseline_7d2535f8876f/.tmp/baseline-68c5f8d` (the
  suffix is the SHA-256 prefix of the shipped archive, not the commit).
- **Scratch, outside git** (`D:/RAG_new/.tmp/` is ignored): `t65/` — the
  launcher, supervisor, watcher and pause scripts of the collection, its state
  and host samples in `t65/run/`; `pilot/` — `handoff_numbers.py` and the cold
  read of the 1.3c section. The pilot's launcher is not written.
- **MyFlow.** No command was run. Whatever `.myflow/` says about T-65, T-77 and
  T-78 predates this session; the guard markers in `.myflow/guard/`, hers to
  remove, were not touched.
- **Gate.** The tree of `323ce00` passed on `deproject-mac` before the commit:
  73 tests of the step's four modules, 424 of the baseline and
  label-verification tools, `ruff check .`, mypy on 66 files. The closing
  commit of documentation passed the docs tests there; its message has the
  line. The full suite was run on none of the twelve commits.

## Next actions, in order

Standing rules: one model (Change 1); no MyFlow unless Julia names it — its
stale state blocks no commit; pytest only on the Mac; no WSL, Docker or VM on
the laptop; no push without her word. Actions 1–4 do not wait for her; action
5 looks for her answer first («Once Julia decides»). Commands with hosts,
paths and interpreters are in the T-65 handoff, section «T-65 judging part
done — 2026-10-05».

1. **Start the variance pilot on the Mac** — bullet «Launching the variance
   pilot» of that section has the arguments of the three arms, the route of an
   unpushed commit to the Mac, what to adapt in the supervisor and the rule
   for tests meanwhile. About eleven hours, detached; read its state file
   between steps and do not poll it. The one local background job is the
   judging.
2. **Finish T-65** on the laptop meanwhile: judging to 115 valid replies → the
   retest → `consensus`, which with one judge only writes that judge's grades
   as the ruler input → `pack` → the report from a clean committed tree → the
   loss map → at most two mechanisms → capsule, evidence row, artifact test.
3. **Close 1.3c**: `variance_pilot export` for each arm, `measure`, the capsule
   with sizes, MDE, powers, the index bound, the hours spent and the campaign
   budget recomputed; ledger rows for the three development runs.
4. **Rubric v3 in code**: a registry of rubric versions, the verifier on the
   clean route, the self-check status, the repair as an isolated request.
5. **1.3d** — the 30 new development cases and the 64 of the holdout, drafted
   and checked, and the 30 pilot cases checked again under v3. First the
   replacement function that applies `rules.replacement` of the split, tested
   before the first draft is verified. Give the generator the severity scale
   and the definition of a critical fact before it labels.
6. Then, by the plan's table of slices (§1): **1.3e** locks the holdout, which
   is opened once, in 4.1; **3.0** is the graph enablement policy, registered
   before any graph experiment; **2.3, second part** is the graph's life cycle
   through add, update and delete of a document, only if the map picks a graph
   mechanism; **2.8** validates the NLI judge — the entailment model that
   checks an answer's claims against its context — on 200 claims; **2.6**
   audits the routing verdicts, only if the map picks H4 (the question's
   category as a soft prior) or the policy of 3.0 leans on the class `simple`;
   **3.1** is H1, coherence as a soft preference, the default mechanism. The
   loss map picks at most two mechanisms "by removable losses and cost" (plan
   §1, row 2.5); H1 stands unless the map points elsewhere (row 3.1).

## Lessons

- **«Сам» covers every role.** A rule I had registered named another vendor's
  model as verifier, and I called it. A registered rule is not leave: change the
  rule first, in the open.
- **Compute what a size can show before designing around it.** The plan carried
  "60 + 100" for a week; one module of arithmetic showed that neither aim of
  the spec's section «Power» is reachable on this corpus.
- **A rule registered before a pilot must be monotone in the pilot.** The first
  draft let a small pilot variance lower the MDE; the cold read caught it.
- **A whole-file cold read at maximum effort returns nothing**: 200k
  characters spent the output window on reasoning; a narrowed prompt at effort
  `high` (93k) gave 12 findings in 393 s.
- **Artifact tests pin sentences of the spec**: grep
  `tests/test_variance_pilot.py` before rewording the 1.3c section.
- **Decide what stops before writing the state**: the first draft described a
  judging pass still running, and the cold reader had the old tense. A process
  check that names its own pattern finds itself: hence `baseline_[j]udge`.

## Glossary

- **D-numbers** — rows of the plan's table of decisions (§2). D11 (2026-10-03,
  no people in the plan's work) and D12 (2026-10-04, one model) rest on Julia's
  words; what each means in practice is the agent's text. The earlier ones,
  D6–D9 among them, the agent took on 2026-09-30 under her delegation («прими
  решения сам, нужен очень качественный результат»). **G-numbers** — the
  plan's open gaps (§7); G38 is eight questions about checks by models.
  **H1–H11** — the hypotheses of track 3; a **mechanism** is one of them built
  as a change of retrieval; H5 is a pool of 40 candidates. **T-numbers** —
  task names kept from MyFlow: T-65 is slice 2.5; T-76, T-77 and T-78 are
  slice 1.3b.
- **Registered** — written into the spec or the plan and committed before the
  run it governs; changed only in the open, with a date.
- **Ruler** — a set of metrics with the judge behind them: the lexical one of
  the official gate, the semantic one for development. **`provisional_ruler`**
  — a ruler whose judge has not passed its check: its numbers are description
  and no gain is claimed. **P2** — the published blinded judgment of H and Hm
  by GLM and Sonnet; `model-cross-checked` and `model_verified` are status
  words of checks by two vendors.
- **Arm** — one configuration run over the same cases; the **control** arm is
  production defaults. **Ledger** — the plan's list of every development run
  with its config hash, failed ones included.
- **The four sets.** H and Hm: the 100 single-hop cases of the official gate
  and 15 multi-hop ones, labelled long ago, part of neither split. Pilot: 30
  verified cases, 24 with gold evidence, the first half of development.
  Development: 60 — those 30 and 30 that step 1.3d drafts. Holdout: 64, none
  drafted yet; 1.3d writes them, 1.3e locks them. **Unresolvable cases** — the
  class "refusal or clarification": the right action is to refuse or to ask.
- **Clean route** — the isolated request of `evaluation/isolated_request.py`.
- **Family** — documents of one topic; the unit of independence. **Block** — what
  a new case may draw its documents from: a family of several documents, or two
  one-document families paired by similarity. **Cluster** — cases linked through
  shared families; what the bootstrap resamples. **Reserve** — the 35 families
  no development case touches; the holdout comes from them. **Cap** — at most
  four holdout cases a block.
- **MUE** — the minimally useful effect, +0.05. **NI** — non-inferiority, a CI95
  lower bound of at least −0.02. **MDE** — the smallest true effect detected
  with power 0.8. **Registered MDE** — the MDE at correlation 1 inside a
  cluster, Student quantile, variance the larger of 0.10 and the pilot's.
  **Grid** — the assumed variances 0.05 / 0.10 / 0.20 for metrics the pilot
  cannot measure.
- **Perturbation** — a pilot arm that moves one setting to produce paired
  differences; not a mechanism candidate. **Pool** — the chunks the reranker
  receives. **Sent context** — the documents left after grading.
- **Gold span** — a labelled piece of source text a case's answer rests on.
- **Collector** — `scripts/production_baseline.py`: retrieval through the
  production path, no generator. **Judge store** — the JSONL of raw judge
  replies.
- **Stability retest** — a second grading of 10 cases a subset in another blind
  order. **Contamination control** — a request whose evidence was cut out or
  swapped.
- **Index bound** — the gold spans that some chunk of the index holds whole:
  the most a pool can reach.
- **Capsule** — an evidence file in `docs/evidence/` with provenance.
- **`NOT_EVIDENCE`** — a run that did not happen, cannot be read, or has no
  capsule yet. **`INCONCLUSIVE`** — neither proven nor refuted at the achieved
  power. **`SHIP_RESEARCH`** — every condition of acceptance 4.1 passed.

## Verification

On the laptop, in Git Bash:

    git -C "D:/RAG_new" status -sb
    git -C "D:/RAG_new" log --oneline origin/master..HEAD
    python D:/RAG_new/.tmp/mf-mac/sync.py
    python D:/RAG_new/.tmp/mf-mac/remote.py --site pytest tests/test_power.py tests/test_devset_split.py tests/test_gold_metrics.py tests/test_variance_pilot.py tests/test_docs_hygiene.py tests/test_docs_quality.py -q -p no:schemathesis -p no:cacheprovider --basetemp=.tmp/pytest-focus

The split is rebuilt byte for byte by `tests/test_devset_split.py`; the MDE
table of this file is the one `tests/test_variance_pilot.py` rebuilds from
`registered_mde`.

This file was read cold once before the commit by a fresh session of the same
model that opened this file alone (not the clean route: it carried the
project's instruction files): 25 findings — 2 blockers, 15 majors, 8 minors —
all answered here or in the T-65 handoff. Still not done: the pilot's launcher
is not written, and the check for a live judge pass is a command, not a guard
in the tool. Nothing has read the file since.

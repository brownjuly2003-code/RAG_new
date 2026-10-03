# Session handoff — 2026-10-03, quality plan revised; no people in the process

Written for the next session (autocompact is on) because Julia asked for it:
«запиши лог сессии». It was a plan session: **no code changed, no model graded
anything, no quality number was published.** Three commits rewrote the quality
plan, [`plan_03_10_26.md`](../specs/plan_03_10_26.md); the third adds this file
and takes every human task out of the plan. To confirm it is the pushed HEAD,
run `git -C "D:/RAG_new" status -sb`: it must show `master...origin/master` with
nothing ahead. The engineering resume order is in
[`t65-baseline-handoff.md`](t65-baseline-handoff.md).

## What matters to understand

**The thread this plan serves.** The official quality gate is lexical
`context_precision` ≥ 0.63 on H, the 100 labelled air-cargo cases. No measured
arm reaches it: 0.5067 at the phase-C baseline, about 0.60 for the best
adaptive-k arms, every mechanism so far `NO_SHIP`. P2 then showed that this
lexical ruler does not follow blinded relevance grades (`RULER_DOES_NOT_TRACK`,
τ_b 0.1561). So the quality plan, adopted 2026-09-30, builds a second ruler for
development — relevance judged by a consensus of two LLM judges — plus a dev set
and a locked holdout, makes the retrieval route observable, tests at most two
mechanisms, and ends in one research acceptance (slice 4.1) through the real
`/api/ask`. The 0.63 gate stays on its own ruler, untouched.

**The question the session ended on: who does the human work?** Until today the
plan needed 29–48 hours of Julia, or 21–35 of hers plus 13–20 of a second
trained person (`plan_final_30_09_26.md` §3, «Часы Юли»): grade 50 documents
blind (decision D2), approve every dev and holdout case and the family map (D3),
label 200 assertions for the NLI judge (slice 2.8), check the holdout answers
blind (4.1). Her answer is decision **D11**: «люди участвовать в процессе не
будут». That is one sentence. Reading it as "no human labour at all", and
everything built on that reading, is mine and not hers — see "What is the
agent's choice". Under it the quality thread, up to and including the research
acceptance 4.1, holds zero human hours and waits on no person. Three things stay
behind her gates, and the plan does not schedule them: product acceptance
(slices 4.2 and 4.3 need her deployment target and SLO), making the repository
public, and Pages.

**The model to keep in mind: a model never becomes a person.** The 2026-09-30
plan already said a model grade is not a human grade. D11 did not repeal that,
so the revision does not rename model checks as human ones. It changes what the
plan may claim:

| The human job (2026-09-30) | What does it now | The result is called | No longer claimed |
|---|---|---|---|
| Julia grades the blind sample; κ human ↔ consensus decides (1.1, D2) | κ of the consensus to two models that already graded that sample: Astra (OpenAI, a vendor outside the judges') and Opus (Anthropic, like the Sonnet judge). Both must clear the threshold; only Astra is outside-vendor evidence | `model-cross-checked` | `human-validated` |
| A person approves dev and holdout cases and the family map (1.3b, 1.3d, D3) | two verifier models from two vendors, neither the draft generator's (the pilot's generator is `gpt-6.1-sol`, OpenAI, so the verifiers come from z.ai and Anthropic); one repair, then the case is dropped. The agent registers the family map; only a verify script checks it | `label_check: model_verified`; origin stays `agent_labelled` | `real_labelled` and slice rule (b) |
| Julia labels 200 assertions for the NLI judge (2.8) | the majority label of three models from three vendors | the NLI judge is accepted relative to a model majority, or stays `provisional_judge` | validation on human labels |
| Julia checks holdout answers blind (4.1) | two models from two vendors, neither the answer generator's, blind to the arm; a fact or a citation counts only when both confirm it. They are not chosen yet: registered before the holdout opens | capsule line: no person checked anything | a human answer check |
| A second trained person (G15) | nobody; the agreement between the models is printed | — | inter-annotator reproducibility |

In this file "the references" means only the Astra and Opus grades of slice 1.1.
The checkers of the other slices are named by their job: verifiers (1.3b, 1.3d),
the three-model majority (2.8), the answer checkers (4.1). The plan and the spec
call the last two "reference models" as well.

Independence between people is replaced by independence between **vendors**:
z.ai (GLM), Anthropic (Sonnet, Opus), OpenAI (Astra, Sol); local models are a
group of their own. The honest limit is gap G37 of the plan: models trained on
similar data can share an error, and their agreement will not show it. The human
anchors that remain are the 100 H labels Julia approved on 2026-09-25 (T-54) and
the third-party gold of the external control (ConditionalQA, WixQA).

**How to read slice 1.1, the first slice in the new form** (task T-57; no model
request and no Mac). The inputs are published:
`reports/p2/astra-reference/replies.jsonl`,
`reports/p2/opus-reference/replies.jsonl` and
`reports/p2/p2-blinded-judge-glm+sonnet.json`. The κ of the consensus to each
reference is not computed yet; what is published is each judge's κ to them,
0.88–0.91. The interval is a bootstrap over cases: 10,000 resamples, percentile,
seed 20260925 (the constants of `evaluation/blinded_judge.py`). Read the
branches top to bottom:

| Order | Outcome | Criterion (registered in the metrics spec) | What to tell Julia |
|---|---|---|---|
| 1 | fails | CI95 of quadratic-weighted κ entirely below 0.7 for either reference | the consensus is not a usable ruler; a new judge set is named before its grades meet a reference and is checked once, on a fresh sample; nothing counts as a semantic gain |
| 2 | indeterminate | otherwise, the CI straddles 0.7 for either reference | slice 1.1b: both references grade 20 more cases (≈ 40 requests — one per case and reference; the judges graded all of H in P2). The same three branches apply once to the 30-case κ. Engineering goes on under `provisional_ruler` |
| 3 | passes | otherwise: both CIs entirely ≥ 0.7 | the development ruler is `model-cross-checked`: the two judges agree with two other models on 10 cases / 50 documents; no person checked it; it covers the sample's question classes and unexpanded top-5 contexts only |

A second indeterminate result, after 1.1b, leaves `provisional_ruler`. The
holdout is not opened on it; the judge set is re-registered once; if that fails
too, the campaign closes without 4.1 and what follows is her decision.

With any outcome, say this too: the rule was written after each judge's κ to the
references had been published, so the check is not blind to its likely result;
the 0.7 threshold is the one registered on 2026-09-30 for human grades and was
not tuned; the ten-case sample carries no contamination controls.

## Julia's requests and decisions this session

| # | Her words, 2026-10-03 | What it became |
|---|---|---|
| 1 | «Тщательно изучи проект, нужно обновить план доработки (последний от 30.09) по файлу D:\Rag_research\2026-10-03_PLAN_INPUT.md» | the plan revision from the lexical-lane research input |
| 2 | «Новый план должен быть с датой сегодня» | a new file, `plan_03_10_26.md`; the 2026-09-30 plan stays as history under a "superseded" banner — commit `028f874` |
| 3 | «От меня 1. Зафиксируй по тврей рекомендации 2. Убери, плиз 3. Удали, уже октябрь 4. Как лучше тут?» | (1) order: phase E first — a green CI on HEAD — then the 2.5 chain; (2) the research note I had added is removed, and the input's item П4 with it; (3) the "Actions unavailable until October" rule leaves `CLAUDE.md`; (4) I recommended how to spread her grading hours — commit `69e46c5` |
| 4 | «запиши все в план. люди участвовать в процессе не будут» | decision D11, her answer to my recommendation under item 4 |
| 5 | «запиши лог сессии» | this file |

Her earlier words that support the reading of D11, from the 2026-09-30 session:
«сделай работу за меня. и прими все решения за меня»; «про за мной - я просила
все сделать за меня».

## What is the agent's choice, not Julia's

D11 is one sentence. Everything under it is my implementation, and no second
voice audited it. She was told these points in the final report of this session;
none of the next actions waits for her answer.

1. **The reading.** No human labour at all — not only "no second person". I told
   her this reading before editing; her next message asked for this log and did
   not object.
2. **Vendor independence** as the stand-in for independent people, with the rule
   "counted only when both models confirm".
3. **The status words** `model-cross-checked` and `label_check: model_verified`.
4. **Slices 1.3b and 1.3d are "preparation" by the slice rule**: without a human
   approval the count of real labelled cases cannot rise, so rule (b) is out of
   reach. They are still required work: 1.3c–1.3e and 4.1 depend on them.
5. **The pause rule (G30) is gone**, and its deadline of 2026-10-28 with it: it
   guarded against waiting for human hours.
6. **More text leaves the machine (G31).** Judges already received chunk texts
   and questions. Now z.ai, Anthropic and OpenAI also receive system answers and
   assertions taken from them (2.8, 4.1), and whole draft cases: question, spans,
   facts, reference answer, class, expected action, and for refusal cases the
   control's pool texts (1.3b, 1.3d). Holdout gold therefore leaves the machine
   before the holdout is locked. Sources go out under a pseudonym; tenant
   metadata, paths and file names still do not go out.
7. **The holdout reserve.** The pilot found the reserve skewed toward HR/legal
   templates and linked to development families by 105 `cross_ref` links. The
   question "add independent sources or accept topic independence" was hers; the
   default is now the second, because only the owner can add documents. The
   leakage and skew are published, and the 4.1 capsule lists the strata with no
   holdout cases (by the pilot: claims, customs, dangerous goods) and draws no
   conclusion on them.
8. **Queue position.** Her order of 2026-10-03 named the CI and the 2.5 chain.
   Slices 1.1 and 1.3b used to wait for her hours and had no place in it; I put
   them after the chain. Slice 1.1 is cheap and could go first.
9. **Not done on purpose** (plan G37): unfreezing judge calibration on public
   human-labelled sets (frozen by D8), and making the external control a SHIP
   condition (D7). Either would bring back a human anchor without local people,
   but both change the campaign or the acceptance rule — her decisions.
10. **Scope: the quality thread only.** Phase B is untouched: B.2/B.3/B.5 are
    blocked on shipment-bound data, and B.4 still names 40 double-annotated
    human routes (`BACKLOG.md`, `CURRENT_STATE.md` Q2b).
11. **Her decisions inside the work that became my defaults** (plan §2, «Решения
    владельца, ставшие умолчаниями агента»): what follows a second indeterminate
    κ; a larger stated effect size when the needed sample is out of reach; the
    family map and the loss map checked by nobody but their author; authority
    and applicability of the rules in cases confirmed by nobody; the
    safety-case quota only where the corpus states the correct behaviour
    verbatim; every screening draft checked by one model instead of her blind
    5 % sample.
12. **Eight design questions are open** — plan gap G38 and the table under the
    gap table. The cold read found them; I did not decide them tonight. Each
    names the slice before whose registration it must be closed in the spec.
    Questions «а» and «б» come first, before the first check of slice 1.3b.

What stays hers, and the plan does not wait for it: the deployment target and
SLO (D5), repository publicity and Pages, the stop-list, the list of documents
never sent to external models, new source documents, and the right to revise
any decision before the first track-3 experiment.

## Once Julia decides

- **She confirms, or says nothing.** Go on with "Next actions".
- **She meant only "no second person".** `git revert` the third commit: every
  file returns to the second publication. Then add this log back, put T-57 back
  to importing her grades (its old text is row 1.1 of the 2026-09-30 plan; a
  copy may survive in `.tmp/plan0310/t57_before_d11.txt`) and delete the memory
  `no-humans-in-quality-process`.
- **She objects to one replacement** — a status word, "preparation", the pause
  rule, the reserve default, a default from point 11. Each is one row of the
  replacement table in plan §2 plus the slice rows it names. Change them, list
  the change in plan §6 and re-run the docs tests. No code uses any of it yet.
- **She wants a human anchor without local people.** Offer the two options of
  G37; each needs a new registration and a budget.
- **She does not want answers or draft cases sent to external vendors.** Raise
  it before slice 1.3b registers its verifiers: with local models only, the
  "another vendor" rule cannot hold, and 1.3b, 2.8 and 4.1 need a new design.
- **She wants 1.1 sooner.** `$MF unpark T-57`, then `$MF next --task T-57`.

## Log

1. Onboarding, then the 2026-09-30 plan, the metrics spec and the research input
   `D:/Rag_research/2026-10-03_PLAN_INPUT.md` were read in full and the input's
   premises checked against HEAD `70d272c`. The input is a generated file: do
   not edit it by hand.
2. CI was probed once. GitHub Actions execute jobs again and CI is red; the
   causes went into `CURRENT_STATE.md` and plan §1.
3. **First publication, `028f874`.** New plan file: §0–§5 and §7 of the old plan
   carried over verbatim, §6 lists every changed place. From the input: BM25
   token normalisation is the frozen candidate H11 (gap G36); one cross-reference
   in the spec's «Screening tier»; an appendix to the detail of MyFlow task T-70.
   A slice status table dated 2026-10-03 replaced the "readiness front". A
   separate Claude session read this publication cold.
4. **Second publication, `69e46c5`.** Her three answers recorded; the research
   note and П4 removed; the Actions rule removed from `CLAUDE.md`.
   `D:/Rag_research/HANDOFF.md`, outside this repository, now says the input is
   applied.
5. **Third publication, the commit that adds this file.** D11 in the plan (§2
   record with the replacement table; §1 rows, graph, status table and order; §3
   "Человеческие часы — 0"; §4 boundaries; §6 list; §7 statuses and the new
   G37); the fifth revision of
   [`semantic-precision-metrics.md`](../specs/semantic-precision-metrics.md),
   including the new «Label verification» paragraph; `CURRENT_STATE.md`,
   `ROADMAP.md`, `BACKLOG.md`, four rows of `EVIDENCE_INDEX.md`, one line of
   `README.md`, the T-65 handoff and the old plan's banner. Plan §3 estimates
   about 1,760–1,960 requests to the checking models of the three vendors in
   place of the hours; it is my estimate from the set sizes, not a measurement.
   MyFlow task T-57 was rewritten to the model form and parked again. Two
   memories were saved: `no-humans-in-quality-process`, `session-log-request`.
6. **Cold read, before that commit.** A fresh Claude session (Opus) read this
   file cold and compared the plan, the spec and the state files: 25 findings.
   Fixed in the same commit: the plan still waited on Julia through "closing
   phase E" (track 3 now starts after slice 1.3e and a green CI; publicity and
   Pages do not hold it); the order of the 1.1 branches, the CI method and the
   1.1b outcome; no holdout on a provisional ruler; who the draft author is and
   what happens when a vendor is unavailable; the 2.8 judge sharing a vendor
   with a voice; what leaves the machine during draft verification; the status
   word, renamed from a draft that said "validated"; stale wording. Left open:
   the eight questions of G38.

## State at the end

- **Git.** After the push `master` equals `origin/master` at the commit that
  adds this file; before it `69e46c5`, `028f874`. Untracked and not mine:
  `demo/phase-e-raw.webm`.
- **CI: red, not repaired.** Observed on `70d272c` (run 37093493571) and
  `028f874` (run 37127142442): 7 of 11 jobs pass. `test-unit` on 3.11 and 3.13
  fails 12 tests — 11 artifact tests call `git show <sha>:<path>` on a shallow
  checkout, 1 reads the gitignored `data/uploads`; `pre-commit` and `security`
  fail on new `pip-audit` advisories; the Pages workflow fails `npm audit`.
  The later commits changed documents only and were not checked on CI.
- **MyFlow** (`$MF status`). No open slice; 65 of 70 tasks passed, 4 open, T-57
  parked with the new text. T-69 is prepared and backed up on the branch
  `wip/T-69-prep` (`e5525fa`). There is no task for slice 1.3b yet. Editing the
  spec raises drift advisories on tasks that reference it; they are expected.
  `.myflow/blocked.md` is an append-only log: its 2026-09-30 entry for T-57
  ("waits for Julia's grades") is superseded by the entry below it, and T-14
  is listed there though it is no longer parked. A defect is filed for it
  (`$MF issues` wrote `D:/Runbook/issues/issues37.md`).
- **Not in code yet:** the κ-to-references computation, the fields `label_check`
  and `draft_author`, and the draft-verification tool. Slices 1.1 and 1.3b
  bring them.
- **Mac.** This session started nothing there.
- **Scratch, local and gitignored:** `.tmp/plan0310/` holds the patch scripts
  (`apply_d11_plan.py`, `apply_d11_rest.py`, `apply_d11_fix2.py`, `d11_doc.py`)
  and the checks (`post_checks.py`, `check_links.py`). They are applied; do not
  re-run the patch scripts.

## Next actions, in order

1. **A green CI on HEAD** (plan slice 0.1b; Julia's order). Workflows:
   `.github/workflows/ci.yml` and `docs-site.yml`. Causes: above and plan §1,
   «CI на 03.10»; test names: `gh run view 37093493571 --log-failed`. Expected
   fixes: full git history (`fetch-depth: 0`) in the `test-unit` jobs, a source
   for the corpus file one test reads, upgrades of six Python packages and of
   npm packages. Do not weaken a check, and do not report CI as green without a
   run. A green CI is where the quality thread stops depending on phase E:
   making the repository public and deploying Pages stay Julia's gates and hold
   nothing below.
2. **The 2.5 chain**: T-69 (v2 re-judging) → T-67 (parity publication) → T-70
   (full loss map) → T-65 (the baseline on the Mac). The resume steps, with the
   commands that restore `wip/T-69-prep`, are in the T-65 handoff, "Stop point —
   2026-10-03 (after T-68)"; re-read T-70's detail before its `next`.
3. **Slice 1.1, T-57**: `$MF unpark T-57`, `$MF next --task T-57`. The task
   detail names the inputs, the rule and four mandatory caveats. Compute κ of the
   consensus to both references, publish a new capsule with an evidence row and
   an artifact test — slice rule (c) — and read the outcome with the table above.
   Dated capsules are not rewritten: artifact tests pin their sentences.
4. **Slice 1.3b**: add the task (`$MF task-add --id T-71 --title … --detail-file
   … --spec-refs semantic-precision-metrics`). First close G38 «а» and «б» in the
   spec's «Label verification» and register there the verifier models, versions,
   prompt and rubric. Then add `label_check`, `draft_author` and the tool, verify
   the 30 drafts, and register the family map and the holdout reserve. Files:
   `evaluation/devset_pilot.jsonl`, `evaluation/devset_pilot.manifest.json`,
   `evaluation/document_families.json`, the verifier `evaluation/devset.py`,
   `tests/test_devset_pilot.py`; limits in the
   [pilot capsule](../evidence/devset-pilot-drafts.md).

Commands, from any directory:

    MF='env -C D:/RAG_new python C:/Users/uedom/.claude/skills/myflow_new/scripts/myflow_new.py'
    env -C "D:/RAG_new" "C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe" -m pytest tests/test_docs_hygiene.py tests/test_docs_quality.py tests/test_docs_publication.py tests/test_backlog_docs.py -p no:schemathesis -q
    git -C "D:/RAG_new" -c credential.helper='!gh auth git-credential' push origin master

## Lessons

1. **I proposed human hours to an owner who had delegated the work.** On
   2026-09-30 she had already said «я просила все сделать за меня». Before
   planning a step that needs a person, check her earlier decisions. Saved to
   memory.
2. **I pre-empted an owner's choice.** The research input listed the form of
   publication under the owner's decisions; I added the note on its
   recommendation and she removed it. A recommendation in an input is not a
   decision.
3. **Dated rules expire.** "Actions unavailable until early October" was stale on
   October 3. Check such a rule once when its date passes.
4. **When people leave a process, change the claim, not the label.** Calling a
   model check `human-validated` would have kept the plan's numbers looking the
   same and made them mean less. My first status word still said "validated";
   the cold read caught it.
5. **Removing a person also removes the decisions that person made on the way.**
   I replaced her labour and did not notice that six of her decisions inside the
   work had silently become my defaults, or that the plan still waited for her
   through "closing phase E". My own checks searched for words ("ждёт Юлю"),
   not for rules; a cold reader found both.
6. **Figures do not survive autocompaction.** The summary dropped the hour
   estimates; I checked the ones I had written from memory against
   `git show HEAD:docs/specs/plan_03_10_26.md` before the commit.
7. **Mechanics.** About 190 replacements in files with 2 kB table rows went
   through patch scripts that refuse to write unless every fragment matches
   exactly once. `CURRENT_STATE.md` (150 lines) and `BACKLOG.md` (60) sit at
   their caps: edit them in place.

## Glossary

- **H / Hm** — the 100 labelled air-cargo cases / the 15-case multi-hop and
  aggregation bucket.
- **P1, P1b, P2** — adaptive-k experiments (both `NO_SHIP`) and the blinded
  relevance judgment that found `RULER_DOES_NOT_TRACK`.
- **Phases B, C, E** — of the main plan `plan_06_09_26.md`. B: real labelled
  cases, blocked on shipment-bound data; its open owner question is Q2b. C: the
  quality-leverage phase that set the 0.63 gate. E: the public artefact; its
  slice 0.1b is a green CI, then publicity and Pages.
- **Tracks 0–4** — of the quality plan: 0 closes E; 1 measurement (ruler, dev
  set, holdout); 2 observability and the baseline; 3 mechanism experiments;
  4 acceptance — 4.1 research on the Mac, 4.2 product on a deployment target
  with an SLO, 4.3 the per-tenant flag.
- **Lexical ruler / 0.63 gate** — phase C's `context_precision` over cached
  contexts; the official gate.
- **Development ruler** — judged relevance, pre-registered in
  `semantic-precision-metrics.md`; it selects mechanisms and is not a product
  gate.
- **Consensus** — the lower-median grade of the two judges, GLM 5.3 and Sonnet 5.
- **References** — Opus 5.5 and GPT-6-Astra grades of the blind ten-case sample;
  they check the consensus and never replace it.
- **κ, α, τ_b** — quadratic-weighted Cohen's kappa (agreement of two graders),
  Krippendorff's alpha (agreement between the judges), Kendall's tau-b (rank
  correlation of the lexical ruler with the grades).
- **`provisional_ruler`** — the mark a capsule carries until slice 1.1 passes.
- **`model-cross-checked` / `human-validated`** — a ruler checked by models of
  other vendors / by a person. Only the first is reachable under D11.
- **`agent_labelled` / `real_labelled`** — a label's origin: written by an agent
  / approved by a person. **`label_check: model_verified`** is a separate field:
  two models confirmed the case.
- **Vendor** — the company behind a model; the unit of independence under D11.
- **Family, family map, `cross_ref`, holdout reserve** — a family is a group of
  source documents treated as one cluster; dev and holdout never split one. The
  map is `evaluation/document_families.json` (84 draft topic families).
  `cross_ref` is a link between corpus documents. The reserve is the 35 families
  kept out of development for the holdout.
- **The pilot** — the 30 draft cases of slice 1.3a (T-64).
- **NLI judge** — the entailment model that scores whether a claim of an answer
  is supported by the context; slice 2.8 validates it on 200 claims.
- **D1–D11, G1–G38, H1–H11** — the plan's decisions (§2), gaps (§7) and
  mechanism candidates. D5: deployment target and SLO. D7: the external
  benchmark as a transferability control. D8: the first campaign and its
  freezes. D10: the 2026-09-30 leftovers (pause, external judges, screening
  drafts, second person).
- **П1–П5** — the items of the research input; П4, priors for the second wave,
  was dropped with the note.
- **Slices** — 1.1 ruler check; 1.3a–e dev set and holdout; 2.5 baseline and loss
  map; 2.8 NLI-judge validation; 4.1 research acceptance on the locked holdout.
- **The 2.5 chain** — T-69 (re-grade the contexts under judge contract v2) →
  T-67 (publish the harness-to-API parity run) → T-70 → T-65.
- **Slice rule (a)/(b)/(c)** — a slice counts only as an E2E-proven `/api/ask`
  change, more real labelled cases, or a published number with provenance.
- **SHIP verdicts** — `SHIP_TO_HOLDOUT` / `SHIP_RESEARCH`, `NO_SHIP`,
  `INCONCLUSIVE`; none changes a runtime default.
- **Stop-list** — vector DB, model and reranker swaps, re-embedding: Julia only.
- **MyFlow, `$MF`, T-numbers** — the task controller, its command, its tasks;
  `next` opens the next task as a slice, `unpark` returns a parked one.
- **Astra, Sol, GLM** — `gpt-6-astra` and `gpt-6.1-sol` (OpenAI, through Codex)
  and GLM 5.3 (z.ai).

## Verification

- **Patch scripts**: every replacement matched exactly the stated number of
  times, or nothing was written — 67 and 47 in the first pass, 74 in the
  cold-read pass.
- **Checks on the final tree** (scratch, may be gone:
  `python D:/RAG_new/.tmp/plan0310/post_checks.py`, `…/check_links.py`):
  `CURRENT_STATE.md` 150 lines and `BACKLOG.md` 60, at their caps; no CR bytes;
  no broken relative link or anchor in the 11 files touched or linked;
  `git diff --check` clean; the old status word appears nowhere.
- **Docs and artifact tests**: the 22 test files that read a changed document —
  473 tests — passed on the Windows focused venv (Python 3.11).
- **MyFlow**: `plan-validate` OK after the T-57 edit.
- **Cold read**: one fresh Claude session (Opus), as in Log item 6. Its findings
  are a model's output, not Julia's review; the fixes made after it were read by
  nobody but the author.
- **Not done**: no second-voice audit (GLM or Astra — only on Julia's command),
  no Mac gate, no CI run for the three documentation commits.

# Runbook — next actions after the stop point of 2026-10-06

The commands for the [session log of 2026-10-06](session-handoff-2026-10-06-sets-bases-reference.md).
Read that file first: it says why, and what must not be done. The lines below
come from the tools' `--help`, their docstrings and this session's use; a
chain that was not yet run for a set is marked so.

## Conventions

- `PY` stands for
  `PYTHONPATH=D:/RAG_new PYTHONIOENCODING=utf-8 AIRCARGO_CORPUS_DIR=D:/RAG_Support_Assistant/data/uploads/aircargo C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe`.
  A tool of the repository runs as `PY -m scripts.<tool> …`. The scratch tools
  under `D:/RAG_new/.tmp/` run with plain `python` (any Python 3 on the
  path); `cli_probe.py` alone needs `PY`.
- Absolute paths, no `cd`: the working directory does not persist.
- Tests run on the Mac only: `python D:/RAG_new/.tmp/mf-mac/sync.py` (ships
  the working tree, untracked files too), then
  `python D:/RAG_new/.tmp/mf-mac/remote.py --site pytest <files> -q -p no:schemathesis -p no:cacheprovider --basetemp=.tmp/pytest-<name> --tb=short`.
  The two scripts borrow MyFlow's exclude rules as a library and carry its
  name in their docstrings; they start no MyFlow command, writer or reviewer,
  and they are the only test path.
- «The spec» is `docs/specs/semantic-precision-metrics.md` (the plan's «спека
  1.2», over 3,400 lines — search a heading, never read it whole): «Variance
  pilot and sizes of plan step 1.3c», «Drafts of plan step 1.3d» with «The
  screening tier», «External bases: parts and pilot of plan slice 1.6» with
  «One pilot, measured once», «Checks by one model in slices 2.8 and 4.1»
  with «How the reference of 2.8 is drawn and asked». Its header log holds one
  entry an amendment.

## 1. The usage windows, before any stream

`PY D:/RAG_new/.tmp/devset13d/cli_probe.py` — one trivial request, between
streams and never beside one (the auto-mode classifier refused a probe beside
a living stream). The line `rate limit: {…}` is the CLI's `rate_limit_info`:
`unifiedWindows.five_hour` and `.seven_day`, each with `utilization` (0–1)
and `resetsAt` (epoch seconds). No such line means no rate-limit event came:
do not start a stream on a guess.

Sizing. 0.01 of the weekly window is about $10 API-equivalent. A draft costs
$0.61; a check $0.36 (mean; median $0.32); a turn of the session spends the
same windows and was not measured apart; a reference request of 2.8 was never
sent — start with `--limit 10` and probe again. N = (line − weekly utilization) × 1000 ÷ dollars a request, less what
the session spends meanwhile. The line is 0.96 of the week until Julia moves
it. A five-hour window is about $60–70: keep a stream below 0.9 of it, or the
session stops with it. `draft`, `verify`, `repair` and `send` all take
`--limit N`; exit 1 after a batch that left positions pending is expected —
read `pending`, `invalid`, `unavailable` in the last line and run again. One
stream at a time, as one background job.

`python D:/RAG_new/.tmp/devset13d/store_usage.py <store.jsonl>` gives counts,
seconds, tokens and cost of a store, no text. Drafts are launched by
`sh D:/RAG_new/.tmp/devset13d/run_draft.sh <development|holdout> <log file> <limit>`.

## 2. Holdout: what is never opened

The files are tracked and no guard stands before them; the rule is kept by
hand.

- **Never open, print or search**: `evaluation/devset_holdout_*.jsonl`,
  `evaluation/devset_holdout_*label_checks.json`,
  `reports/devset/drafts/holdout*/`,
  `reports/devset/label-verification/v3/holdout*/` (drafts, plans, the wide
  scan, stores, `decisions.json`, `repairs.jsonl`, `drops.json`); on the Mac
  `/Users/julia/RAG_new_13d_scan_*_holdout`. The manifest
  `evaluation/devset_holdout_drafts.manifest.json` was read by its numeric
  fields only. Of `.tmp/devset13d/`, the logs `draft_holdout_*.log` and the
  outputs `build_holdout.out`, `check_holdout.out`, `plan_holdout_r1.out`,
  `scan_holdout.out` hold status lines and counts; `run-scan-holdout.log` was
  not opened.
- **A content search** names files or directories that hold none of these —
  never `evaluation/` or `reports/devset/` as a whole. `git show`, `git log`
  and `git diff` on `e1521ba` and later only with `--stat` or `--name-only`,
  or on other paths.
- **Every command with `--set holdout`, `--set holdout-replacements` or
  `--split holdout` writes to a file**: `… > D:/RAG_new/.tmp/devset13d/<name>.out 2>&1`.
  Of `verify` and `decide` only the last line is read (`tail -n 1`): the JSON
  of counts. The other lines of `decide` are the verifier's reasons, and the
  session does not need them: `devset_label_repair` builds the repair request
  from the stored reply by itself. `python D:/RAG_new/.tmp/devset13d/safe_view.py <file>`
  masks Cyrillic and long strings but lets short Latin strings through: enough
  for `build`, `check` and `plan`, not for `decide`.
- **Tests over these files** run with `--tb=no`.
- **A frozen tree for a cold reader** is cut without these paths, or its brief
  forbids them by name.

## 3. The Mac (`deproject-mac`)

- One look: `python D:/RAG_new/.tmp/external/ext_status.py` — a line `EXT
  <status>`, a line a base, `guarded_unchanged`, a line `EXTPILOT <status>`.
- To wait, one background job and no polling:
  `python D:/RAG_new/.tmp/external/wait_state.py ext complete,failed,stopped 120`
  (`extpilot` for the runner).
- Supervisor: `starting`, `waiting`, `running`, `failed`, `stopped`,
  `complete`. `EXT complete` with `guarded_unchanged` true → section 4.
  `guarded_unchanged` false → stop and report: our own corpus, the T-65 index
  or its checkpoint changed under the run. `failed` or `stopped` → read
  `reason`; start it again with
  `python D:/RAG_new/.tmp/external/launch_ext.py 36f1167b9629e3ebcc367bff59c15b7365e0b1b6`
  (a base with an index receipt is skipped, an embedding goes on from its
  checkpoint; it needs `.tmp/external/ext-36f1167.tar`, on disk, or
  `git archive` of that commit again).
- Runner of the pilot: `waiting` → `running` (WixQA through the stage
  `retrieve`, then ConditionalQA through `grade`, each with the arm
  `control`, then `pool30`) → `measuring` → `complete`; also `paused`,
  `failed`, `stopped`. It waits while the supervisor's processes live, while a
  test run is alive on the Mac, and while Ollama holds a model or does not
  answer (`waiting_for` says which) — so no gate run in the minutes after the
  supervisor ends, and a stopped Ollama keeps it waiting for ever.
  `python D:/RAG_new/.tmp/external/extpilot_ctl.py status|boundary|now|resume|stop`.
- **`EXTPILOT failed` or `stopped` is not a result of the pilot.** Until the
  measure document of a base is written nothing is final (spec, «One pilot,
  measured once»): a run that stopped is resumed; a run that cannot be
  resumed, or that the measure refuses, has measured no pair — the fault is
  fixed by a commit, the run is made again, and what stopped is published by
  stage and error type. A reason `<base>: missing input …index-receipt.json`
  means the supervisor ended before the indexes stood: start the supervisor
  again, then the runner. One commit starts the runner once: a second start is
  `python D:/RAG_new/.tmp/external/launch_extpilot.py <full sha of a later commit>`,
  and the capsule then names that commit as the pilot's code and shows that
  the pilot's files did not change since `64a72e5`. Once a measure document
  exists, that base is not run or measured again — not for lost pairs, not
  for a condition of use that failed.
- Short test runs beside a run are foreign load on its seconds: few, short,
  none of them a wide scan or the judges of 2.8.

## 4. Connection capsule (slices 1.5, 1.5c, 1.5d)

`python D:/RAG_new/.tmp/external/collect_connection.py` (refuses unless the
state is `complete` and `guarded_unchanged` is true; writes
`reports/external/36f1167/connection.json`), then
`python D:/RAG_new/.tmp/external/render_connection.py` (writes
`docs/evidence/external-bases-connection.md` from
`.tmp/external/capsule-connection.template.md` and runs the five checks of
`tests/test_external_connection_artifact.py`). `.tmp/external/rehearsal/` is a
dry run of this step, not a result. Then: one row in `EVIDENCE_INDEX.md`
(class `measured`; the text says preparation), the plan row of 1.5/1.5c/1.5d,
a line of `CURRENT_STATE.md` in place, the Mac gate
(`tests/test_external_connection_artifact.py`, `tests/test_external_bases.py`,
`tests/test_docs_hygiene.py`, `tests/test_docs_quality.py`,
`tests/test_docs_publication.py`), a local commit. The hours of the capsule
carry foreign load (`foreign=<n>/<n>` a step in the status): they are not
evidence of speed.

## 5. Checks of 1.3d

Not yet run for these sets; `c43f0a0` shows the files each step wrote for
`pilot-v3`. `B` is `D:/RAG_new/reports/devset/label-verification/v3/<set>`.
For `development`:

a. `PY -m scripts.devset_label_verify verify --set development --round 1 --verifier claude-opus-5-5 --limit N`
   — 30 cases, at least 30 requests (up to three attempts a case), about $11
   and 75 minutes. Run again until `pending` is 0.
b. `PY -m scripts.devset_label_verify decide --set development --round 1`.
   With nothing rejected, go to e without `--repairs`.
c. `PY -m scripts.devset_label_repair plan --set development`, then
   `repair --set development --limit N`, `build --set development` (writes
   `B/repairs.jsonl` and `B/drops.json`), `check --set development`.
d. `PY -m scripts.devset_label_verify plan --set development --round 2 --repairs B/repairs.jsonl --drops B/drops.json`;
   `verify` with `--round 2` and the same two flags;
   `decide --round 2 --repairs B/repairs.jsonl`.
e. `apply --set development --repairs B/repairs.jsonl`;
   `check --set development --repairs B/repairs.jsonl --rebuild --drops B/drops.json`.
f. Replacements of the dropped drafts, once:
   `PY -m scripts.devset_draft plan|draft --limit N|build|check --split development --replacements`,
   a commit, their wide scan on the Mac, then a–e with
   `--set development-replacements`.

The same for `holdout` (62 cases, about $22 and 155 minutes) and
`holdout-replacements`, every output to a file (section 2). A wide scan is
`python D:/RAG_new/.tmp/devset13d/run_scan_remote.py <full commit sha> <development|holdout>`:
it scans `git archive` of a commit, refuses beside a measured run, and does
not take a replacement set yet — extend it before the first replacement is
drafted. Then `PY -m evaluation.devset_minimums`; the clusters and the MDE of
the verified sets have no command (`evaluation/power.py` holds the functions,
the capsule of 1.3c the numbers they gave for the registered split); the
capsule with its index row and artifact test.

The screening tier comes last: its code and tests first (set `screening` —
nothing of it exists; the rule is spec, «The screening tier»), seated after
the development replacements, each draft scanned on the Mac and checked once.

## 6. Slice 2.8

1. The cold read: one Agent call on the session's model with the prompt «read
   `D:/RAG_new/.tmp/nli28/coldread-7dd2ed090095/BRIEF.md` and follow it». It
   costs as a stream does (the read of this log took 53 minutes). Apply or
   refute each finding in writing and complete the entry of 2.8 in the
   spec's header log.
2. If a text of the prompt changes: `PROMPT_SHA256` and
   `SYSTEM_PROMPT_SHA256` in `evaluation/nli_validation.py`, the two lines
   `Prompt SHA-256` and `System prompt SHA-256 (rubric nli-reference/v1)` of
   the spec, and `PY -m scripts.nli_reference plan` again.
3. `PY -m scripts.nli_reference send --limit N` (436 requests of stage 1;
   exit 1 while requests wait), `next`, `send`, `derive`, `check`. The stores
   in `reports/nli-validation/v1/` are not opened before `derive`.
4. To write: the judges' runner for the Mac — cells M0–M2 × H0, H1 × P0, P1,
   and M3; A3 and B2 are optional (`archive/docs/specs/research-nli-judges.md`, 3.4)
   — over the sample and its top-up reserve, raw logits a pair, run after the
   pilot; and the criteria module. Then the capsule.

## 7. After the pilot (slice 1.6)

When `extpilot_ctl.py status` shows `complete` for both bases, copy the two
documents that may leave the host and nothing else of that directory
(`<base>.json` beside them holds a row a question and stays):
`scp deproject-mac:/Users/julia/RAG_new_extpilot_f6c2bfa7a915/.tmp/extpilot-measure/wixqa.aggregates.json D:/RAG_new/reports/external/64a72e5/pilot/wixqa.aggregates.json`,
the same for `conditionalqa` (the path is my proposal: the spec registers what
leaves the host, not where it is committed); hold each copy against the
SHA-256 in the state's `measure` block. Then
`PY -m scripts.external_pilot sizes --pilot wixqa=<file> --pilot conditionalqa=<file> --out <file>`,
the capsule (aggregates only) with its index row and test, and the eleventh
revision of the spec with a cold read of its own. The runner of 1.7 is not
written; `.tmp/external/extpilot_runner.py` is the model for it.

## 8. Push — only on Julia's word

After the connection capsule exists (its untracked test fails until then, and
`sync.py` ships untracked files): the whole suite on the Mac — the test line
above with `tests` in place of the files — then
`git -C "D:/RAG_new" -c credential.helper='!gh auth git-credential' push origin master`,
then the CI run on `master` (`gh run list --branch master --limit 3`).

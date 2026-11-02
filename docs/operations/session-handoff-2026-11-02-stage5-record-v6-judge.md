# Session handoff — 2026-11-01 22:37 → 2026-11-02 ≈ 07:55 UTC: stage 5 read, her «Да» to publish, V6 running

Previous: [session-handoff-2026-11-01-stage5-judge-v6-fixes.md](session-handoff-2026-11-01-stage5-judge-v6-fixes.md).
Plan: [`PLAN.md`](../../PLAN.md) stages 5, 5б, 8. State: [`CURRENT_STATE.md`](../../CURRENT_STATE.md).

## Read this first

**Where things stand.** Three streams are at different points:

1. **Stage 5 is read but not committed.** Stage 5 asked: does the package (K 14, window
   3,584, INT8 reranker in ONNX, cache cap 1,024) keep answer quality on the external bases,
   compared with stage 2's answers on the same question ids? Registered decision: the pooled
   WixQA + ConditionalQA M1 bad share, "detected" = both 95 % intervals (cluster bootstrap and
   Newcombe) exclude zero. Result — **holds, publish the package's numbers**: bad 0.54 → 0.56 of
   200, not detected. Outside the decision, **WixQA's M1 good share fell 0.40 → 0.30, detected**
   (read95 [−0.1856, −0.0121]); it is the record's main caveat, not noise. ConditionalQA moved
   nowhere detectably. MultiHop-RAG (advisory) is `NOT_EVIDENCE`: its judge bridge agreed on
   12 of 15 kept replies, three moved two steps (all bad → good), kappa 0.3284. The record,
   capsule, test and status-doc edits sit **in the working tree, uncommitted**, because the
   Mac gate cannot run while the V6 chain uses the Mac (see "State at the end").
2. **Stage 8 — publication — is decided.** Her decision to publish RAG_new with its whole
   history is her word of 2026-11-01 20:26 UTC (the runbook's header); the open point was the
   aircargo corpus, and she answered «Да» (2026-11-02 02:58 UTC) after the scan report. What
   is left is mechanical and ordered by the [runbook](stage8-publication-runbook.md) §5: gates
   and commits, a scan of the new commits, a full `ci_local` PASS, then branch deletion, the
   switch, Pages, the push. The README and the site's links are already rewritten (uncommitted).
3. **Stage 5б — answer V6 — is running.** V6 = the owner's V1 answer prompt (V5's frame: the
   model writes its evidence, then the answer), with that evidence kept but hidden from the
   user by one registered shown-text function (`shown_text.py`: first `<answer>`, a repeat
   cut, a script/language guard), on a context fitted to the window. It is compared with the
   package's own shown answers on the same 100 questions per key (wixqa, conditionalqa,
   aircargo). Registered in `9f968bb`; its first chain stopped in preflight before any request;
   amendment 1 in `4a5c36e`; the chain `attempt-02` has answered on the Mac since 02:22 UTC:
   wixqa done, conditionalqa in progress, aircargo next; expected end ≈ 12:30–14:00 UTC
   2026-11-02. The laptop judge grades each completed key in foreground chunks; wixqa's receipt
   is committed (`d15fa87`); its M1 (115 requests) and bridge (15 requests, 30 verdict lines)
   are graded, M2 is at 40 of 115. The early read after wixqa's bridge
   (`reports/answer-prompt-v6/2057ad0/reading-wixqa-after-bridge.json`): `harm: []`, decision
   `NOT_EVIDENCE` only because M2 and the other keys are not in yet.

**What to tell Julia next.** After the commits and the push: "RAG_new is public; the README
shows the package's numbers on three corpora (aircargo, WixQA, ConditionalQA; MultiHop-RAG
marked NOT_EVIDENCE), with WixQA's fall in good answers stated." After V6's read: its outcome
by the spec's table "Reading fixed before the first request (V7)", first row that holds:
(1) not adopted — harm: any readable key's bad share rises, or its good share falls while bad
does not, or ConditionalQA's declines fall, or pooled bad or pooled M2 `agrees` worsens;
(2) NOT_EVIDENCE: a required plan or bridge missing or uncounted; (3) adopted: pooled
WixQA + ConditionalQA M1 bad share falls, detected; (4) not adopted — no gain.

## Julia's words in this session (UTC)

- 2026-11-01 22:37 — «продолжи доработку». My reading: the previous handoff's "Next actions".
- 2026-11-02 02:58 — «Да», to my question «корпус aircargo можно делать публичным — да/нет?»
  after the stage 8 scan report; my question said yes = publish RAG_new with its history. With
  her 2026-11-01 20:26 word it covers the publication push, deleting the three `wip/*` branches
  on GitHub, disabling `weekly-report.yml`, the visibility switch and Pages, in the runbook's
  order, after a full `ci_local` PASS. It does not name later pushes (runbook §6: "Each push
  still needs her word unless her «да» covers it"): ask her one yes/no before the first push
  after publication, and run both scans before every push anyway.
- ≈ 07:50 — «сессия тяжелая, поставь точку, где логично и обнови доку». This file is the
  answer.

## Stage 8: what the scan found (reported to her before her «Да»)

- gitleaks over `master --remotes=origin --tags` (1,383 commits): 1,554 findings, all
  `generic-api-key` false positives (1,551 hex hashes, 3 prose). No live key. `gh secret list`:
  none.
- Shingle scan (8-word shingles of casefolded letter runs, against the external bases' and the
  aircargo corpus's texts) over 7,141 public text blobs: **no external-base text**. The aircargo
  corpus is readable in history (41.5 % of its shingles; 59 blobs never public before) — hence
  her yes/no, now «Да».
- Personal data that becomes public with the history: commit author addresses, one address in
  `docs-site/astro.config.mjs` (`email:`), the Mac user path and her name in many files. She saw
  the list before «Да». Phone numbers at HEAD are fake fixtures.
- GitHub refs: master `7caaf21`, `baseline/freeze-2026-08-23`, tag `freeze-2026-08-23`,
  `wip/T-61-writer`, `wip/T-69-prep`, `wip/T-77-prep` (the three `wip/*` get deleted).
- This session's new commits `b74c715..master` were scanned again: gitleaks 0; shingle hits only
  paths, run settings, the judge route and V6's own prompt template (stored inside private
  request files) — no base text. **Repeat both over the final range right before the push**,
  after any fix commits (runbook §6): `D:/RAG_new/.tmp/e5-scan/bin/gitleaks.exe git
  --log-opts="origin/master..master" --redact --no-banner D:/RAG_new` and
  `PYTHONHASHSEED=0 C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe -X utf8 D:/RAG_new/.tmp/stage8-scan/shingle_range.py origin/master..master`
  (absolute paths inside, any cwd; it loads `.tmp/stage8-scan/cache/s<i>.npy`;
  `span_view.py <kind> <path>` shows which words of a hit match — classification aid).

## Stage 5 at the stop point

- Answers 2026-10-31 14:21 UTC on stand `2057ad0`; receipts `da0988a`, `bd18bce`, `42dcd1a`;
  every plan graded (735 requests) and exported with exit 0; exports normalized CRLF → LF.
- Committed: twelve exports in `26c175c`. **Uncommitted**: `reports/stage4-final/stage5/2057ad0/`
  `record.json` (the registered read; byte-equal to the dry read `.tmp/stage5-dry/record-final-dry.json`),
  `stage5-multihoprag-m2.json`, `stage5-multihoprag-m2.cases.jsonl`,
  `stage5-multihoprag-bridge.json`; the capsule
  [`docs/evidence/stage5-final-external-record.md`](../evidence/stage5-final-external-record.md);
  the test `tests/test_stage5_final_artifact.py` (6 tests; it pins 20 files' SHA-256, rebuilds
  the read from the exports, checks privacy and binds every capsule line holding a digit).
- Codex wrote the capsule and test (task 10, s1 `9aa867f`); I added the "What ran" section and
  its pins. A light binding check passed on the laptop (`.tmp/cx-exec/check_s10_capsule.py`);
  **the test itself has not run** — Mac only.

## Stage 5б, V6, at the stop point

- Spec [`docs/specs/answer-prompt-v6.md`](../specs/answer-prompt-v6.md). Registration
  `9f968bb` (01:35 UTC). Its `attempt-01` stopped in `--check` before any request:
  `reports/stage4-final/tools/external/protocol.py` puts the stage-4 tools first on `sys.path`,
  and their `api.py` shadowed the product package. Codex task 11f fixed it (product root first,
  plus a test); the Mac gate passed (189 + docs 23); amendment 1 registered in `4a5c36e`
  (02:21 UTC). `attempt-01` is not evidence; its log is kept.
- Chain `attempt-02`, Mac folder `/Users/julia/RAG_new_stage5/v6/4a5c36e/attempt-02`, log
  `/Users/julia/RAG_new_stage5/v6-attempt-02.out`. Each answer prints one `ANSWER <key> <id> [flags]
  <sec>` line; one `RuntimeError: aclose(): asynchronous generator is already running` per
  answer is cosmetic (Ollama's own request durations equal the answer times). At 07:50 UTC:
  wixqa 100 (COMPLETE), conditionalqa 60, aircargo 0.
- wixqa transferred to `D:/RAG_new_stage5_private/v6/transfers/attempt-02/wixqa`; first judge
  call froze its plans (exit 4); receipt committed `d15fa87`; then 8 chunks: M1 115/115, bridge
  15/15 requests (30 verdict lines), M2 40/115.
- `v6_key.py` writes each key's public exports and readings, untracked, into
  `reports/answer-prompt-v6/<stand>/` as it goes: now `v6-wixqa-judge-m1.json`,
  `v6-wixqa-judge-m1.cases.jsonl`, `v6-bridge-wixqa.json`, `reading-wixqa-after-bridge.json`;
  wixqa's exit 0 adds `v6-wixqa-judge-m2.json`, its `.cases.jsonl` and
  `reading-wixqa-after-m2.json`. They are not stage 5's files; they go into V6's record commit
  (step 8) by explicit path, never into commit (a).
- Judge work left: wixqa M2 75, conditionalqa ≈ 245, aircargo ≈ 130 requests — ≈ 450, at
  93–130 s each ≈ 12–16 h, ≈ 50–70 chunks of 840 s.
- **The chain was left running on purpose**: it needs no session, a stop would lose
  conditionalqa's answers, and the spec lets the next key's answers overlap the laptop judge.

## What this session did

- Stage 8 checks and the report → her «Да».
- Stage 5's judge to the end (ConditionalQA bridge, MultiHop-RAG's three plans), the LF commit
  `26c175c`, the registered read.
- V6: Codex 11d/11e fixes, a cold read, my recomputation, registration, the shadowing defect,
  amendment 1, the chain; the wixqa receipt and judge chunks.
- Codex task 10 (capsule, test) and task 12r (README, docs-site links), each reviewed and
  committed in the copy `D:/RAG_new_cx/s1` (`9aa867f`, `57bc424`), then copied into RAG_new.
- Status docs: CURRENT_STATE, ROADMAP rows 5/5б/8, PLAN (status, stage 5 read, 5б
  registration, stage 8 «Да», §8.1, §8.3 item 5), EVIDENCE_INDEX row, BACKLOG, docs/README.

## My choices, not hers

- README rewritten after the stage 5 read, so the public page carries stage 5's numbers (the
  push waited for the Mac anyway).
- The capsule states WixQA's good-share fall in its opening, as the main caveat.
- The README's "Measured results" keeps only the final path (items 6–7, stage 5); the old table
  (graph lane, Qwen3 8B, Qwen2.5 7B) left the front page and is reachable via EVIDENCE_INDEX.
- In review I restored the README's `demo/` and `archive/` lines that Codex had dropped
  because its copy lacked those folders.
- No Mac gate and no master commit at this stop point; a local backup branch instead.

## Next actions (in order)

Paths are absolute; the cwd does not persist. Interpreters: laptop
`C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe`; Mac gate through
`.tmp/mf-mac/sync.py` + `remote.py`.

1. **Check the tree.** `git -C D:/RAG_new status --short` must list the uncommitted files named
   above. If they are gone, restore them from the local backup branch
   `wip/stage5-record-v6-judge-stop` (its `git log -1` shows the SHA):
   `git -C D:/RAG_new diff --name-only wip/stage5-record-v6-judge-stop~1 wip/stage5-record-v6-judge-stop -- . ':!.tmp' | xargs git -C D:/RAG_new restore --source=wip/stage5-record-v6-judge-stop --worktree --`.
   Never push that branch.
2. **Look at the chain** (one call): `bash D:/RAG_new/.tmp/cx-exec/v6-macpoll.sh` prints the
   terminal markers and answers per key. `CHAIN_COMPLETE` = all keys done; `STOP` or
   `FAILED.json` = read them before anything else (spec, "Terminal states"). The Mac is free
   when a terminal marker exists **and** no `v6_chain.py` process remains
   (`ssh -o BatchMode=yes deproject-mac pgrep -fl v6_chain.py` prints nothing); the poll
   script does not check the process.
3. **Finish wixqa's judge**: repeat
   `powershell -NoProfile -File D:/RAG_new/.tmp/cx-exec/v6-chunk.ps1 -Key wixqa` (foreground,
   840-s budget, Bash timeout 1,200,000 ms) until it exits 0. Exit codes (spec, judge block):
   0 key complete; 3 budget reached, rerun; 4 receipt awaits commit (path printed);
   5 seven consecutive unavailable attempts — diagnose, then rerun with `-ResumeUnavailable`
   (below seven the flag does nothing); 2 stopped by a 3x judge stop or harm, Mac STOP
   touched; 6 the same stop detected but the Mac STOP not written — touch it by hand:
   `ssh -o BatchMode=yes deproject-mac touch /Users/julia/RAG_new_stage5/v6/4a5c36e/attempt-02/STOP`;
   1 refusal — diagnose. For 1 and 6 the status line names
   `D:/RAG_new_stage5_private/v6/<key>/driver.log` (traceback). After 2 or 6: no restart
   without her word; read `reports/answer-prompt-v6/*/reading-*.json`, go to step 8 and tell
   her the outcome ("not adopted — harm" or NOT_EVIDENCE). Progress:
   `bash D:/RAG_new/.tmp/cx-exec/v6-progress.sh wixqa` (verdict lines per plan). Keep
   `powershell` and `$(…)` out of one Bash command — a hook refuses it.
4. **conditionalqa, then aircargo**, each once its `COMPLETE` exists:
   `powershell -NoProfile -File D:/RAG_new/.tmp/cx-exec/v6-transfer.ps1 -Key <key>`, then the chunk
   script with `-Key <key>`; the first call returns 4 → commit
   `reports/answer-prompt-v6/<stand>/plans-<key>.json` and `v6-<key>.json` (`<stand>` =
   `2057ad0`, aircargo `138f3b3`) with the message `stage 5b: freeze V6 <key> plans before
   grading`, then rerun to exit 0. One judge stream at a time.
5. **Once the Mac is free (step 2), the Mac gate** — between judge chunks, without waiting
   for the judge to finish: `python D:/RAG_new/.tmp/mf-mac/sync.py`, then
   `python D:/RAG_new/.tmp/mf-mac/remote.py --site pytest -q tests/test_stage5_final_artifact.py tests/test_docs_hygiene.py tests/test_docs_quality.py tests/test_docs_publication.py tests/test_quickstart_docs.py tests/test_docker_compose_hardening.py tests/test_autopilot_runner.py tests/test_answer_prompt_v6.py`
   plus every test that names a changed root file:
   `grep -l -E 'PLAN\.md|EVIDENCE_INDEX|ROADMAP|CURRENT_STATE|README' D:/RAG_new/tests/*.py`
   (PLAN.md changed by 35 lines; pinned phrases are a known trap). A red test: fix (or brief
   Codex in `D:/RAG_new_cx/s1`), never weaken a pin.
6. **Two commits** with explicit paths (never `demo/phase-e-raw.webm`, `reports/ask100/`,
   never a `reports/answer-prompt-v6/` export): (a) the stage 5 record —
   `reports/stage4-final/stage5/2057ad0/{record.json,stage5-multihoprag-m2.json,stage5-multihoprag-m2.cases.jsonl,stage5-multihoprag-bridge.json}`,
   `docs/evidence/stage5-final-external-record.md`, `tests/test_stage5_final_artifact.py`,
   `CURRENT_STATE.md PLAN.md ROADMAP.md EVIDENCE_INDEX.md BACKLOG.md docs/README.md` and this
   handoff; rule (c); (b) `README.md` and the nine `docs-site/src` files.
7. **Publication** (runbook §5), between judge chunks: commit any pending V6 receipt first;
   a full `python C:/Users/uedom/.claude/scripts/ci_local.py --repo D:/RAG_new` in the
   background with PASS (Mac free, no Codex task running); **no commit other than `*.md`
   between that PASS and the push** (the pre-push hook needs the stamp) — if a key's
   `COMPLETE` arrives meanwhile, transfer and freeze it after the push; the two scans over
   `origin/master..master`; delete the three `wip/*` on GitHub;
   `gh workflow disable weekly-report.yml -R brownjuly2003-code/RAG_new`; switch to public;
   Pages; push master; a line in PLAN, ROADMAP and CURRENT_STATE (`*.md` only; it waits for
   the next push, which needs her word, section "Julia's words").
8. **V6's read** once all three keys are graded: the spec's "Final reading" block
   (`v6_record.py`), then a capsule and test (a fresh Codex task in `D:/RAG_new_cx/s1`
   without external data — not `--resume-last`, see Lessons; runner:
   `~/.claude/skills_cold/codex-cw-runner/SKILL.md`), the record commit with the V6 exports
   and readings by explicit path. The SLO (item 7's 270 s / 360 s) is hers to name after
   V6's outcome.
9. Cleanup: the Mac's `/Users/julia/RAG_new_stage5/v6-diag` (a patched diagnostic copy, not
   evidence). Keep `D:/RAG_new/.tmp/stage8-scan/cache` (346 MB) until the last planned push —
   `shingle_range.py` needs it; without it only a full `shingle_scan.py` run works.

## Do not

- Run anything heavy on the Mac while the chain runs: no `sync.py`/`remote.py` gate, no
  `ci_local`. The poll, a key's transfer and a STOP touch are allowed. Never touch other
  projects' processes there.
- Restart a stopped job without her word; clear the stale Codex companion job (below) without
  her word.
- Put external-base ids or texts into a Codex package (`D:/RAG_new_cx/s1` holds none; its
  `.cx_inputs/` is never committed).
- Push before step 7's PASS, or push any `wip/*` branch.

## State at the end

- RAG_new `master` = `d15fa87`, 76 local commits after `origin/master` `7caaf21`, unpushed.
- Working tree: the uncommitted stage 5 / README / site / status files above; wixqa's four
  untracked V6 exports and readings (V6 section); untracked and never to commit:
  `demo/phase-e-raw.webm`, `reports/ask100/`.
- Local backup branch `wip/stage5-record-v6-judge-stop` (built after this file; not pushed).
- Mac: V6 chain `attempt-02` running. Laptop: no background job, no monitor, no Codex task.
- s1 copy at `57bc424` (plus untracked `.cx_inputs/`, modified `CX_REPORT.md`).

## Lessons

- **A filtered working copy misleads its executor.** s1 lacked `docs-site/`, `demo/` and
  `archive/`; Codex first stopped, then "corrected" README lines about folders it could not
  see. Before a task on the front page, give the copy every path the task touches, and say
  which folders exist only in the main tree.
- **The companion refuses `--resume-last` while any old job is stuck "running".**
  `task-mvxxv35t-nh4i5m` (task 11, pid gone) blocks every resume in s1. A fresh task with the
  brief plus the answers worked (`D:/RAG_new_cx/briefs/s10-fresh.md`,
  `D:/RAG_new_cx/briefs/s12r-fresh.md`). Clearing the stuck job needs her word.
- **A frozen tool can shadow the product.** The stage-4 tools' `api.py` beat the product
  package on `sys.path`; `--check` before any request caught it — keep a preflight that imports
  the real product path.
- **The capsule test binds every line with a digit.** Adding a dated sentence means adding the
  same line to `capsule_numeric_prose` in the test.
- The laptop left EDT on 2026-11-01: local time is now UTC − 5.

## Glossary

- **Package** — stage 4's adopted settings: K = 14 candidates per lane, num_ctx 3,584, INT8
  reranker in ONNX Runtime, llama cache cap 1,024 MiB; the code's defaults since `6c52b06`.
- **M1 / M2 / M3** — judge grade without reference (good / partial_ok / bad); agreement with a
  reference answer or a right decline; deterministic gold coverage in the sent context.
- **Bridge** — the judge re-grades kept stage 2 replies; agreement and quadratic kappa test
  whether today's judge grades as it did then.
- **read95** — the span of the cluster-bootstrap and Newcombe 95 % intervals.
- **Receipt** — a committed `plans-<key>.json` that freezes the judge plans before grading.
- **V6** — stage 5б's answer variant: the owner's V1 prompt with written evidence, shown to the
  user only through `shown_text.py` (section "Read this first", item 3).
- **attempt-NN** — one launch of the V6 chain; a failed attempt keeps its folder and log.
- **s1** — `D:/RAG_new_cx/s1`, the data-free copy where Codex (cw, `gpt-6-astra`, xhigh) works.
- **NOT_EVIDENCE** — a plan whose gate failed; it yields no number.

## Verification

- `git -C D:/RAG_new log --oneline -6` shows `d15fa87`, `4a5c36e`, `9f968bb`, `26c175c`.
- `sha256sum D:/RAG_new/reports/stage4-final/stage5/2057ad0/record.json` starts `6ae0d6e1`.
- `bash D:/RAG_new/.tmp/cx-exec/v6-progress.sh wixqa` → m1 115, bridge 30, m2 ≥ 40.

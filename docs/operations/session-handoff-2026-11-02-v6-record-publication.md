# Session handoff — 2026-11-02 11:28 → ≈ 20:00 UTC: stage 5 and V6 recorded, RAG_new published

Previous: [session-handoff-2026-11-02-stage5-record-v6-judge.md](session-handoff-2026-11-02-stage5-record-v6-judge.md).
Plan: [`PLAN.md`](../../PLAN.md) stages 5, 5б, 8. State: [`CURRENT_STATE.md`](../../CURRENT_STATE.md).

## Read this first

**Where things stand.** All three streams of the previous handoff are closed:

1. **Stage 5 is committed** (`21d6c64`): the package holds on WixQA + ConditionalQA (pooled M1
   bad share 0.54 → 0.56 of 200, not detected); WixQA's M1 good share 0.40 → 0.30 is a detected
   fall outside the registered decision and the record's main caveat; MultiHop-RAG is
   `NOT_EVIDENCE` (bridge 12 of 15, kappa 0.3284). README and site carry these numbers (`8c4a1a4`).
2. **Stage 5б — answer V6 — is decided: not adopted, harm** (`d60913d`,
   [record](../evidence/answer-prompt-v6-record.md)). The spec's table is read top-down and
   row 1 holds: pooled M2 agreement with the reference falls 0.45 → 0.356 of 180, read95
   [−16.48, −2.38] pp, 117 clusters, detected. By the registered order that harm decides over
   V6's own detected gain (pooled M1 bad share 0.56 → 0.425 of 200). aircargo is
   `NOT_EVIDENCE`: never answered whole (see "V6's aircargo"). **The package stays.**
3. **Stage 8 — publication — is done** (her «Да» of 2026-11-02, confirmed again at
   ≈ 20:00 UTC when the guard refused the first GitHub step): the three `wip/*` branches
   deleted on GitHub, `weekly-report` disabled, RAG_new **public**, Pages on (build by
   workflow, `https://brownjuly2003-code.github.io/RAG_new/`), master pushed with this file.

**What to tell Julia next.** The quality stream's next step is the generator pilot
(PLAN §8.3, item 15). The SLO is hers to name (PLAN §8.3, item 2): item 7's proposal is
first word 270 s, whole answer 360 s (p90, rounded up to 30 s); V6 would have lengthened the
answer, and V6 is not adopted, so the proposal stands as measured.

## Julia's words in this session (UTC)

- 11:28 — «продолжи доработку проекта». My reading: the previous handoff's "Next actions".
- 12:26 — «что на маке тебе мешает?»; 12:41 — «тебе мак нужен?». Answered: memory for the
  ci_local VM while the V6 chain answered; yes, the Mac is needed for gates and CI.
- Answer to my question on restarting aircargo: «обрыв был вынужденный, перезапусти все».
  She had stopped the Mac herself. Read as: restart what was cut; the spec never regenerates
  completed keys, so only aircargo got a new attempt (attempt-04).
- 13:47 and 15:59 — «процесс живой?» (the second with «насколько сейчас загружен мак?»).
  Answered with the chain's progress and the Mac's CPU, memory and swap.
- 17:23 — «я не понимаю, что происходит((( мы ходим по кругу и гробим ресурс?(((». Answered
  plainly: what is done, V6's outcome, where the time went, what is left. My decision then:
  commit V6's record **before** the full ci_local, so one CI run and one push cover both.

## V6's aircargo

- attempt-02 (from 02:22) completed wixqa and conditionalqa; it ended in aircargo's first batch
  on her external stop at 10:22:58. That stop also took down `ollama serve`.
- attempt-03 refused in preflight (`--check`, URLError connection refused) before any request:
  Ollama was down. No attempt folder; its log `/Users/julia/RAG_new_stage5/v6-attempt-03.out`.
- Ollama restarted at 14:16:50 with default env (same binary 0.33.2, same model digest), pid
  74468, log `/Users/julia/RAG_new_stage5/ollama-serve-20261102.log`. Default env matches the
  runner args of the n-gram record `5558ca8` (`--flash-attn auto`, `-np 1`). It is production's
  server; leave it running.
- attempt-04 began at 14:17 (preflight clean). At 17:18 the conditionalqa judge's M2 made
  pooled M2 harm detected; the judge driver exited 2 and touched the Mac STOP; the chain exited
  17:27 at 70 of 100 aircargo answers (`FAILED.json`: `NOT_EVIDENCE`, operator/harm stop). No
  aircargo receipt, grade or public file exists; the spec lets detected harm decide without
  later keys.

## CI before the push

- `985577f` fixed three CI failures found by single ci_local jobs: item 7's speed test now keeps
  Python 3.11's float sum on 3.12+ (`sum_python311`); bandit B615 is accepted with its reason
  (`# nosec B615`, `vectordb/onnx_reranker.py`, a pinned revision); joserfc 1.7.7 and pypdf
  6.21.4 clear nine pip-audit advisories (floors in requirements, locks, and
  `tests/test_pip_audit_floors.py`).
- ci_local defects found (Julia's tool, not the project): `--job helm` alone does not start
  docker — add `--docker`; ci_local runs no kind-action post step, so the kind container
  `chart-testing-control-plane` stays in the `ci-local` VM after each helm run and the next
  helm run fails ("node(s) already exist"). Remove only that container:
  `ssh deproject-mac 'zsh -lc "colima start ci-local; DOCKER_HOST=unix://$HOME/.colima/ci-local/docker.sock docker rm -f chart-testing-control-plane; colima stop ci-local"'`.
  The VM's other containers (demo, b2b-spark-*, work-redis-1) belong to other projects.
- The first full run on `d60913d` failed in helm/kind-action: `curl: (6) Could not resolve
  host: github.com` inside the VM (a passing DNS blip; the docs-site job had one earlier the
  same day). The run was doomed to FAIL, so I stopped it at minute 15 (its trap stopped the VM)
  and started it again.
- The second run failed at once: `[Errno 28] No space left on device`. The killed run had left
  13 GB of venvs in the VM's `/var/tmp/ci_local/RAG_new_20261102-131038` (root disk 19 GB);
  its trap stops the VM but does not clean the job folder. I removed only that folder (and the
  second run's), stopped the VM and started the third run.
- The third run (`20261102-133704`) ended **INCOMPLETE: 30 steps passed, 0 failed, 4 uncovered**
  — `ci/regression-eval`'s four steps behind `hashFiles()` at run time, the same gap as every
  earlier full run; helm with its kind cluster passed. The laptop's memory guard killed the
  local ci_local process near its end (the Mac run is detached and went on), so the verdict and
  the stamp came from `.tmp/cx-exec/ci_local_attach.py <run id>`: ci_local's own `plan_jobs`,
  `report` and `write_stamp` on the remote state, refusing when the tree differs from HEAD
  beyond `*.md`. Stamped tree `a56022976b` (HEAD `d60913d` plus this handoff's draft). The
  mypy step took 845 s (131 s in the first run): the Mac swapped until Julia closed her apps.

## Scans of the new commits (`origin/master..master`, at `d60913d`)

- gitleaks: 124 `generic-api-key` findings, all hex hashes (108 of 64 digits, 16 of 40) keyed
  by names like `api.log`, `live_api.py`, `v6_key.py`, `tokenizer_snapshot` — false positives,
  the class of the earlier full scan's 1,551. No `.gitleaksignore`: a non-`*.md` file would
  void the ci_local stamp. Output `.tmp/stage8-scan/gitleaks-d60.json`.
- shingle range scan: 172 hits (stage2-private 89, stage5-runs 78, multihoprag-p2 5); every
  `span_view.py` check shows paths, ids, run settings, idle readings, the judge route or prompt
  templates (`agent/prompts.py`, `qa_prompt_v6.txt`); no external-base text — the classes of
  the earlier approved scan. Output `.tmp/stage8-scan/shingle-d60.txt`.

## What this session did

- Stage 5's record (`a7202e4` conditionalqa receipt, `21d6c64` record, `8c4a1a4` README/site)
  after a Mac gate.
- V6's judge to the decision (conditionalqa M1, bridge, M2), the final reading
  (`reports/answer-prompt-v6/reading-final.json`, exit 2, byte-identical to
  `2057ad0/reading-conditionalqa-after-m2.json`).
- Codex tasks 13 (CI fixes, reviewed, `985577f`) and 14 (V6 capsule and artifact test,
  reviewed, in `d60913d`), both in `D:/RAG_new_cx/s1` without external data.
- Status docs for V6: CURRENT_STATE, PLAN, ROADMAP row 5б, EVIDENCE_INDEX row, docs/README.
- Mac focused gate before `d60913d`: 367 passed.
- Publication by the runbook's §5 after the stamp; the status lines in CURRENT_STATE,
  ROADMAP row 8, PLAN (status, stage 8, §8.3 item 5) and docs/README went into the pushed
  md commit, so no later push is owed.

## My choices, not hers

- aircargo restarted as one new attempt only; the completed keys were not regenerated (spec).
- V6's record committed before the full ci_local: one CI run, one push.
- The doomed first full run stopped at minute 15 instead of running on for ≈ 45 minutes.
- No `.gitleaksignore` (it would break the stamp); the triage is in this file instead.

## Next actions (in order)

1. **Check the first public runs**: `gh run list -R brownjuly2003-code/RAG_new -L 5` — CI
   and the docs-site deploy should have started on the push. If the deploy did not:
   `gh workflow run docs-site.yml -R brownjuly2003-code/RAG_new --ref master`; CI has no
   dispatch — `gh run rerun <id>`. A red GitHub run: read it, fix, ci_local, then ask her.
2. **Ask her one yes/no before any later push** (runbook §6; her «Да» covered the publication
   push only); run both scans before each.
3. **SLO**: hers to name (CURRENT_STATE, "Open for Julia").
4. **Generator pilot** (PLAN §8.3, item 15) — the next quality step; read PLAN first.
5. Cleanup: the Mac's `/Users/julia/RAG_new_stage5/v6-diag` (a diagnostic copy, not evidence).
   `D:/RAG_new/.tmp/stage8-scan/cache` (346 MB) is needed only for `shingle_range.py` before
   later pushes; delete it when no push is planned.

## Do not

- Push without her word after the publication push; push any `wip/*` branch.
- Restart a stopped job without her word.
- Put external-base ids or texts into a Codex package (`.cx_inputs/` is never committed).
- Commit `demo/phase-e-raw.webm` or `reports/ask100/`.
- Touch other projects' containers in the `ci-local` VM or their processes on the Mac.

## State at the end

- RAG_new public; `origin/master` = local `master` (the md commit after `d60913d`).
- GitHub refs: `master`, `baseline/freeze-2026-08-23`, tag `freeze-2026-08-23`. Local
  `wip/*` branches stay local (never push them).
- Laptop: no background job, no monitor, no Codex task; the Codex broker of
  `D:/RAG_new_cx/s1` may still idle. Mac: Ollama 0.33.2 serving (pid 74468), the `ci-local`
  VM stopped and clean, no RAG_new job; atv2's `main.py` is another project's.
- `.git/info/exclude` temp lines removed after the push; `demo/phase-e-raw.webm` and
  `reports/ask100/` stay untracked.

## Lessons

- **A doomed CI run is cheaper to stop.** One step's FAIL means no stamp; read the summary
  (`~/ci_local/<run>/state/summary.tsv` on the Mac) early and restart instead of waiting.
  Killing the remote `linux.sh` stops the VM through its trap; the local ci_local and the
  runner container must be stopped too (`docker rm -f ci_local_<run>`), and the run's folder
  in the VM removed by hand —
  `colima ssh -p ci-local -- sudo rm -rf /var/tmp/ci_local/<run>` — or the next run fills
  the VM's 19 GB root disk.
- **The Mac's `ci-local` VM resolves github.com unreliably** (two `Could not resolve host`
  failures on 2026-11-02, both gone on retry).
- **Commit records before the full CI.** A non-`*.md` commit after the PASS needs another
  full run; order the commits so one run covers them.
- **The laptop's memory guard can kill a long ci_local.** Claude Code stops a background
  job when the laptop runs low on memory; the Mac run is detached and finishes, but the
  verdict and stamp are the laptop's. `.tmp/cx-exec/ci_local_attach.py <run id>` reads the
  remote state with ci_local's own functions and stamps (or refuses a non-`*.md` drift).
- **Her stop of the Mac takes Ollama down.** After any external stop, check `ollama serve`
  before a restart; the preflight refuses cleanly without it.

## Glossary

- **Package** — stage 4's adopted settings: K = 14, num_ctx 3,584, INT8 reranker in ONNX
  Runtime, llama cache cap 1,024 MiB; the code's defaults since `6c52b06`.
- **M1 / M2** — judge grade without reference (good / partial_ok / bad); agreement with a
  reference answer or a right decline.
- **Bridge** — the judge re-grades kept replies to test whether it grades as before.
- **read95** — the span of the cluster-bootstrap and Newcombe 95 % intervals; "detected" when
  both exclude zero in the same direction.
- **V6** — stage 5б's answer variant: the owner's V1 prompt with written evidence, shown to the
  user only through `shown_text.py`.
- **Stamp** — ci_local's record of a fully tested tree in `.git/ci_local/`; the pre-push hook
  accepts a commit whose tree is stamped or differs from it in `*.md` only.
- **s1** — `D:/RAG_new_cx/s1`, the data-free copy where Codex (cw, `gpt-6-astra`, xhigh) works.

## Verification

- `git -C D:/RAG_new log --oneline -7` shows `d60913d`, `985577f`, `8c4a1a4`, `21d6c64`,
  `a7202e4`.
- `sha256sum D:/RAG_new/reports/answer-prompt-v6/reading-final.json` equals
  `sha256sum D:/RAG_new/reports/answer-prompt-v6/2057ad0/reading-conditionalqa-after-m2.json`.
- `gh repo view brownjuly2003-code/RAG_new --json visibility` → `PUBLIC`;
  `gh api repos/brownjuly2003-code/RAG_new/pages --jq .build_type` → `workflow`.
- `git -C D:/RAG_new status -sb` shows `master...origin/master` with nothing ahead.

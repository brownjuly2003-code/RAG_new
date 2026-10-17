# Session handoff — 2026-09-25, late (T-54 open: label approvals; Codex down at OpenAI)

## Where to resume

`origin/master` = `a40a483`. MyFlow: 53/54 passed. **T-54 is open**, in phase EXECUTING_SLICE,
attempt 2. Its last fast gate is RED on one mypy error.

Julia's decisions of 2026-09-25, quoted:

> 1. glm пока недоступен. давай выберем sonnet 5 через API Grace Kelly с thinking, GLM 5.3
> xhigh, mistral (ключи тут - D:\TXT\Mistral_API.txt. То есть 3 варианта, берез что доступно,
> добираем. 2.Одоюряю. 3. Под раг ассистент. 4. Ничего не удаляй, ненужное - в архив

1. P2 judges: Sonnet 5 via GraceKelly with thinking, GLM 5.3 xhigh, and Mistral. Run what is
   available and add the rest later.
2. Q2a: label batches 1–5 approved.
3. Q4: publish under the RAG assistant name. Confirm the target at phase E, because
   publishing is outward-facing.
4. Mac leftovers: archived, nothing deleted (see below).

### T-54 working tree (uncommitted)

Files:
- M `evaluation/aircargo_labels.py`
- M `scripts/aircargo_labels.py`
- M `tests/test_aircargo_labels.py`
- M `evaluation/curated_cases_aircargo.manifest.json` (v1.1: 100 real_labelled, approvals
  pinned by sha256)
- ?? `evaluation/curated_cases_aircargo.approvals.json` (batches 1–5, approver julia,
  2026-09-25)
- ?? `tests/test_aircargo_label_approvals.py`
- ?? `archive/docs/specs/aircargo-label-approval.md`

How the approvals were recorded: with the tool, through `.tmp/b-approve/record_julia_approval.py`.
The dataset bytes are unchanged, and 60 tests pass on the Mac.

**The one remaining fix:** `evaluation/aircargo_labels.py:516`. In `case = by_id.get(case_id)`,
`case` is already bound as a LabelledCase, so the lookup result needs a new name. The prompt is
`.tmp/cx-exec/T-54-fix1.md`.

After the fix:
1. Mac tests.
2. `done T-54 --detach`.
3. `review-run --detach --use codex --reason-file .tmp/cx-exec/T-54-review-reason.txt`.
4. `gate --full --detach`.
5. A scoped commit of the seven files above. Rule (b): real_labelled 0 → 100.
6. `attach-commit`, clean-clone verify, push.

### Codex (writer and reviewer) is down at OpenAI

Every Codex call since 22:51Z has ended in `401 Unauthorized: Incorrect API key provided:
sk-svcac…` at `chatgpt.com/backend-api/codex/responses`. Five "Reconnecting" attempts come
before it, on fresh sessions and resumed ones alike.

This is not our side:
- status.openai.com has shown **"Issues with Codex"** since 2026-09-25 22:58:48Z, with Codex API
  and Codex Web in full outage.
- The cw profile's ChatGPT login is valid: `auth.json` has auth_mode chatgpt and no API key, and
  the token was refreshed at 23:11Z and expires on 2026-10-05.
- Unsetting the `OPENAI_API_KEY`/`CODEX_API_KEY` env vars changed nothing.
- The TLS issuers are genuine (Google Trust Services, Let's Encrypt), and the hosts file is
  clean.

When the status page shows the Codex components as operational, rerun the fix. Use `--fresh`,
because the fix prompt is self-contained.

**Start of the next session:**
1. Check the Codex status first:
   `curl -s https://status.openai.com/api/v2/summary.json`, and look at the components whose
   name contains "Codex".
2. If Codex is back, rerun the fix.

The T-54 commit message is drafted in `.tmp/cx-exec/T-54-commit.txt`. Replace its
`GATE_LINE` with the full gate's result before committing.

### T-55 (not yet added): state docs

The detail is ready: `.tmp/cx-exec/T-55-detail.md`.
- Before `task-add`, replace `SHA_T54`/`SHORT_T54` with T-54's commit.
- Files: CURRENT_STATE, AGENT_STATE, ROADMAP, BACKLOG and EVIDENCE_INDEX, plus two new specs.
  Move them into `docs/specs/` only after T-54 is committed; before that the move trips T-54's
  scope check:
  - `.tmp/p2/p2-blinded-judge-plan.md`
  - `.tmp/p2/blinded-relevance-judge.md`
- verify_cmd: T-53's docs template, plus `tests/test_aircargo_labels.py`
  and `tests/test_aircargo_label_approvals.py`.

## P2 judges: availability on 2026-09-25

The plan is pre-registered but not committed. It can still be amended before the first corpus
judgment.

- **sonnet** (GraceKelly `POST /api/v1/orchestrate`, `claude-sonnet-5`, reasoning, browser):
  HTTP 503 `model_auth_required`. The profile `D:/GraceKelly/chrome-profile` is not signed in
  to Perplexity Pro. Julia signs in (`python scripts/bootstrap_chrome_profile.py` in
  D:\GraceKelly). `claude-sonnet-4-6-api` is a different model, not a substitute.
- **mistral:** all three keys get 429 with `x-ratelimit-limit-req-minute: 0`. That happened
  from RU and again from a Canadian exit: Windows is under Julia's VPN, and
  `api.mistral.ai/cdn-cgi/trace` gave `loc=CA`. So it is probably an account or workspace
  limit, not the IP. Julia was asked to check console.mistral.ai. Her route for Mistral is the
  Mac under AdGuard VPN, which only she can switch. atv2 (`/Users/julia/atv2`, HH) runs there
  and needs the VPN off.
- **glm:** weekly cap 1310 until **2026-09-28 05:56 UTC+8**. After that, use direct GLM 5.3
  xhigh per `archive/docs/operations/direct-glm-5.3.md`.

The P2 runner itself is a code task for the writer and does not exist yet. It uses fake-judge
tests, and needs no judge to build.
- Its detail is drafted in `.tmp/cx-exec/T-56-detail.md`.
- It comes after T-55, which commits the two specs.
- Use `spec_refs blinded-relevance-judge`.
- Use `false_reject_risk true`, because it contains a parser.
- Files:
  - `evaluation/blinded_judge.py`
  - `evaluation/blinded_judge_clients.py`
  - `scripts/p2_blinded_judge.py`
  - `tests/test_blinded_judge.py`

## Executor and reviewer

- From 2026-09-28 05:56 UTC+8 the project rule applies again: direct GLM 5.3 xhigh writes, and
  `glm-5.3` reviews. Direct GLM request numbers went up to 032; never resend an old prompt.
- Until then (Julia: "only Codex is available"), GPT-6-Sol on the `cw` profile writes, with no
  `--effort`:

  ```bash
  env -u CODEX_COMPANION_APP_SERVER_ENDPOINT CODEX_HOME='C:\Users\uedom\.codex-work' \
    CLAUDE_PLUGIN_DATA='D:\RAG_new\.tmp\cx-work-state' \
    node "C:/Users/uedom/.claude/plugins/cache/openai-codex/codex/1.0.4/scripts/codex-companion.mjs" \
    task --background --write --fresh --model gpt-6-sol --cwd "D:/RAG_new" \
    --prompt-file "<abs path>"
  ```

  A repair resumes with `--resume-last`. The reviewer runs
  `review-run --detach --use codex --reason-file <file>` (gpt-6-astra).
- The job files are in `.tmp/cx-work-state/state/RAG_new-7b12fe53d2d59a38/jobs/<task>.json|.log`.

## Slice loop, per task

1. `task-add` → `plan-validate` → `next --new-turn --task T`; write the preamble; run the
   writer with `--fresh`.
2. Read the diff yourself before `done`. Mac verify: `python .tmp/mf-mac/sync.py`, then
   `python .tmp/mf-mac/remote.py --site pytest …`.
3. `done T --detach`. A red fast gate prints RETRY_SAME_CONTEXT: give the exact error to the
   writer.
4. `review-run --detach …` as above. Exit 7 means repair.
5. `gate --full --detach`.
6. A scoped commit, with the message file in `.tmp/cx-exec/`.
7. `attach-commit T --summary-file .myflow/summary-T.md`.
8. `bash .tmp/p1-run/p1_verify_mac.sh "$(git -C D:/RAG_new rev-parse master)" [extra tests]`.
9. Push with `git -c credential.helper='!gh auth git-credential' push origin master`.

Wait on MyFlow jobs with a Monitor until-loop on `job status <id> --field status`, then
`job wait <id>`.

Pitfalls:
- The guard blocks the orchestrator's own writes under `tests/`.
- It denies the executor's name right after `;` or `(` in a Bash command.
- Doc caps:
  - root `.md` ≤ 9; this untracked file fails two docs-hygiene tests locally, as expected;
  - CURRENT_STATE ≤ 150 lines, and it is at 150;
  - AGENT_STATE ≤ 120;
  - BACKLOG ≤ 60.

**Mac DB tests** go only through
`ssh -o BatchMode=yes deproject-mac /usr/bin/python3 - <tests> < .tmp/mf-mac/mac_db_test.py`.
**Never touch `ragnew_prod`.**

Limits removed by Julia on 2026-09-24; the anti-loop rails stay.

GitHub Actions is unavailable until early October:
- no retries and no billing probes;
- never claim CI passed.

No WSL, Docker or VM on Windows.

## Mac archive (done 2026-09-25)

Nothing was deleted. 28 items (801M) of finished-run leftovers were moved to
`/Users/julia/RAG_new_archive/2026-09-25/`, each listed with its origin in `INDEX.md`:
- P1/P1b, D.4, D.5 and the Chroma-restart clones;
- the diagnostics;
- the `p1_bench` files.

The seven old `rag_spike_*` databases on the Mac PostgreSQL (55432) stay where they are, since
moving a database would mean dropping it.

## History

- This session's earlier commits, all pushed:
  - T-44…T-47 (Phase D closed);
  - T-48…T-53: the Chroma restart runner, its report, the fix `534612e`, the rerun `4e4273d`,
    and the docs `a40a483`.
- The D.4 GLM results stay in `.tmp/glm-d4-result-0*.txt`.

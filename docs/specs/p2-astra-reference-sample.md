# P2 Astra reference grades for the blind human sample

Registered 2026-09-30 (late) before GPT-6-Astra saw any corpus case. The only
earlier Astra request from the work profile in this context was the synthetic
`Reply with exactly OK.` route probe (thread `01a0f471-8824-76c2-96bc-f6bd3046692d`,
empty directory, `xhigh`, read-only sandbox). Requested by the owner the same
night («про разметку — проверь на кодекс astra xhigh») as a third model family
next to the [Opus reference](p2-opus-reference-sample.md); it does not replace
step 1.1 of the [quality plan](plan_final_30_09_26.md).

## Scope

- Grade the same ten H cases selected by
  `evaluation.blinded_judge.draw_human_sample`: two cases from each of five
  ruler strata, the exact sample in `reports/p2/human-sample.html`
  (10 cases, 50 documents). Hm and the other 90 H cases are outside this run.
- Use `build_request` from the registered [P2 plan](p2-blinded-judge-plan.md)
  unchanged: each request holds only its question and five shuffled D1–D5
  document texts. No case id, rank, arm, keyword, ruler score, prior judge
  grade or the Opus grades is supplied. One independent request per case.
- Use the unchanged P2 scale: 3 fully answers, 2 partly answers, 1 on topic
  but unhelpful, 0 unrelated. Require one JSON object with all five grades
  and short reasons. Existing P2 parsing and two parse retries apply.

## Route and record

- Model `gpt-6-astra`, reasoning effort `xhigh`, through the Codex companion
  `task` command on the owner's ChatGPT work profile (`CODEX_HOME`
  `.codex-work`, direct runtime, not the shared broker). Read-only sandbox,
  no `--write`, one fresh thread per case, no resume. The working directory
  of every task is a fresh empty temporary directory outside the repository,
  so the model has nothing to read except the request. The request text is
  passed as the task prompt; the fixed P2 instruction is its first paragraph.
- Verify every reply against the Codex rollout of its thread
  (`<CODEX_HOME>/sessions/…/rollout-*-<thread id>.jsonl`): the `turn_context`
  must report model `gpt-6-astra`, effort `xhigh` and a `read-only` sandbox,
  and the rollout `cwd` must equal the empty directory. A mismatch, a missing
  rollout, a failed job or an empty final message is unavailable, not a grade.
  Token usage is taken from the rollout's last `token_count` event; the plan
  has no per-request cost, so no cost is reported.
- Save raw replies, thread and job ids, rollout file names, usage, request
  hashes, timings and parsed grades under `reports/p2/astra-reference/`. The
  runner resumes from saved valid grades. Local summaries mark partial runs
  incomplete; publish complete ratings only after checking all ten cases. In
  `ratings.json`, `grades` follows the original top-five order, while
  `presented_grades` follows the human page's blind D1–D5 order.
- Publish quadratic-weighted κ of Astra against Sonnet 5, GLM 5.3 and the
  Opus reference on the same 50 units, descriptively, in an evidence capsule
  with the artefact SHA-256 values, pinned by an artifact test.

These are **model reference grades**. They do not replace Julia's blind human
grades, join the pre-registered three-judge P2 consensus, change the P2 ruler
verdict, change the calibration protocol of
[`semantic-precision-metrics.md`](semantic-precision-metrics.md), or change
any product gate. Agreement between model families is not human validation.

# P2 Opus reference grades for the blind human sample

Registered 2026-09-29 before Opus saw any corpus case. The only earlier Opus
request was the synthetic `Reply with exactly OK.` model and effort probe.

## Scope

- Grade the ten H cases selected by
  `evaluation.blinded_judge.draw_human_sample`: two cases from each of five
  ruler strata. This is the exact sample in `reports/p2/human-sample.html`:
  10 cases, 50 documents. Hm and the other 90 H cases are outside this run.
- Use `build_request` from the registered [P2 plan](p2-blinded-judge-plan.md).
  Each request contains only its question and five shuffled D1–D5 document
  texts. No case id, rank, arm, keyword, ruler score, or prior judge grade is
  supplied. Send one independent request per case.
- Use the unchanged P2 scale: 3 fully answers, 2 partly answers, 1 on topic
  but unhelpful, 0 unrelated. Require one JSON object with all five grades
  and short reasons. Existing P2 parsing and two parse retries apply.

## Route and record

- `claude-opus-5-5`, `--effort max`, first-party Claude Code CLI on the user's
  Claude Max account. Disable tools and slash commands, load no MCP servers,
  use a fresh non-persistent session per case, and allow no model fallback.
  The runner's fixed system prompt asks for independent text-only relevance
  grading and JSON output. Its CLI arguments are recorded in the summary.
- Verify every successful CLI envelope reports only the canonical
  `claude-opus-5-5` model from `firstParty`. A mismatch or CLI failure is
  unavailable, not a grade.
- Save raw replies, model ids, usage, request hashes, timings, and parsed grades
  under `reports/p2/opus-reference/`. The runner resumes from saved valid
  grades. Local summaries mark partial runs incomplete; publish complete
  ratings only after checking all ten cases.

These are **model reference grades**. They do not replace Julia's blind human
grades, join the pre-registered three-judge P2 consensus, change the P2 ruler
verdict, or change any product gate.

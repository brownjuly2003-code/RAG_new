# P2 — blinded relevance judgment of the retrieval ruler

Measured under the [pre-registered plan](../specs/p2-blinded-judge-plan.md) of
2026-09-25. GLM 5.3 and Sonnet 5 with thinking each graded all 115 cases: 100 H
cases (500 documents) and 15 separate Hm cases (75 documents). Both judges saw
the same shuffled, blinded documents. Mistral returned `zero_limit` and supplied
no grades. The [earlier Sonnet-only report](../../reports/p2/p2-blinded-judge-sonnet.json)
remains a separate, provisional version.

## Result

On H, the two-judge consensus has ordinal Krippendorff α **0.8566** over 500
shared units (the plan requires ≥0.667); pairwise quadratic κ is **0.8448**.
The primary per-case Kendall τ_b between the official ruler and the
ruler-shaped judged score is **0.1561**, with case-bootstrap CI95
**[0.0197, 0.2880]**. Its upper bound is below the pre-registered 0.40 cutoff.
The plan therefore yields **`RULER_DOES_NOT_TRACK`** for H. The per-unit τ_b
is 0.4204 and the 37-cell per-arm τ_b is 0.9390; both are descriptive, not
inputs to this verdict.

| H arm | Official ruler | Judged precision | Judged FULL/PART/MISS |
|---|---:|---:|---:|
| Top five control | 0.5067 | 0.6080 | 93/6/1 |
| P1 `rel_0.2` | 0.5278 | 0.6767 | 92/7/1 |
| P1 held-out cut | 0.5372 | 0.6900 | 90/9/1 |
| Label-using best-prefix oracle | 0.6505 | 0.9118 | 86/11/3 |

Judged precision counts grades ≥2 among kept documents, then averages over
cases. With two judges, the registered lower-median consensus takes the lower
grade per document. The Hm control is reported separately: official ruler
0.2527, judged precision 0.8400 on 15 cases. Hm does not enter the verdict.
The blind [human sample](../../reports/p2/human-sample.html) contains 10 H cases
and 50 documents; Julia's grades and the resulting human κ are still pending.

## Provenance and replay

- [Current report](../../reports/p2/p2-blinded-judge-glm+sonnet.json) SHA-256:
  `4c1e60cdad361799a291fa88d0d0c3a35675ad772630a0147615ab30d3a31e7d`.
  The earlier Sonnet-only report SHA-256 is
  `019131aa1952258771f47eff8c379fc3135e6a339bffa31967a3a37aa87baed0`.
- Reply-store SHA-256: GLM
  `aac5c00993737194b0b5beaa9ee0cebc28d0434b647997056ffc1f69606f3da9`,
  Sonnet `c66101caa83c11e3b6cfee1e3fe10743c5cc684211265daf241da8654037f4ee`,
  Mistral `12efbbc7b81bea561cafdcc88b737ecc0239248e5db398d750a8f4fce12a7ea1`.
  The stores contain 115 graded cases for each available judge; the Mistral
  store contains only the unavailable result.
- H pool SHA-256 `91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10`;
  Hm pool SHA-256 `3a3020799e8310fcaf3532783cae9d83f8f03b3b0a741488b425ac7edec0aeee`.
  H dataset SHA-256 `3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720`;
  [P1 input report](../../reports/p1/p1-adaptive-k.json) SHA-256
  `30e55459e1787c134215597d5672293ec4b32ef051c8bc96e8d289dfa50cb65d`.
  The H label approvals and manifest are separately pinned in the report.
- Measurement code commit `fa9e598e5bc6446c2c50d7fb9db038f036426c6a`;
  the report's four code-file digests match its git blobs. `tree_clean: false`
  records the untracked report/reply output at generation time, not a code
  difference. Instruction SHA-256
  `7877c3845a742013e3c189e260ef506ba07dc65749fa3df8455a181a4dcedc33`.
  Bootstrap: 10,000 paired case resamples, seed 20260925.
- Sonnet used GraceKelly `/api/v1/orchestrate`, `claude-sonnet-5`, browser
  adapter, `reasoning: true`. The saved GLM replies used the route recorded in
  the then-current P2 runner: z.ai `/api/anthropic/v1/messages` SSE,
  `glm-5.3`, `xhigh`, thinking budget 8000. Current global rules disallow new
  calls through that Anthropic-compatible route; this publication replays
  existing replies only.
- `tests/test_p2_blinded_judge_artifact.py` pins the reports, replies and
  sample, checks the code commit and source digests, parses saved raw replies,
  reconstructs both pools' grades and selected arms, and recalculates the
  primary interval and verdict.

## Limits

The H questions were agent-authored over real documents. Their journey labels
were approved on 2026-09-25, but no human has approved these relevance grades.
The two judges can share errors; Julia's blind adjudication may change the
reliability result when it arrives. The bootstrap is conditional on this case
set and does not make documents from the same source independent. P2 uses the
cached top-five pool, not fresh retrieval. The official 0.63 gate is defined
on its existing ruler: this study changes no threshold, search setting,
runtime default or product behaviour.

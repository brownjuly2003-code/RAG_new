# P2 Sonnet handoff — 2026-09-27

Start the next session at [CURRENT_STATE.md](../../CURRENT_STATE.md), then use this
handoff for P2. The [pre-registered plan](../specs/p2-blinded-judge-plan.md) is the
decision rule; this note records the local run and work still open. The former
2026-09-25 root handoff is preserved in
[archive](../../archive/docs/sessions/session-handoff-2026-09-25-late.md). Its
T-54 blocker, Codex outage, and claim that the P2 runner does not exist are stale.

## State observed on 2026-09-27

| Item | Observed state |
|---|---|
| `D:\RAG_new` | `master` ahead of `origin/master` by 2; latest commit `b4e2ee2`. The two P2 commits are `039954a` (300-second Sonnet browser timeout) and `b4e2ee2` (bounded retry of transient `unknown_error`). |
| `D:\GraceKelly` | `main` ahead of `origin/main` by 2; latest commit `ed6e05a` verifies the browser's `Sonnet 5` selection label. The untracked `issues.md` belongs to the user; preserve it. |
| GraceKelly server | `127.0.0.1:8011` had a listener, PID 10224. Recheck the endpoint at the start of the next session; this is a dated observation, not a service guarantee. |
| Sonnet worker | PID 2500 is gone because the run finished. Its journal reported `JUDGE_EXIT 0`, `COMPLETED 115`, and `REPORT_EXIT 0`. |
| Local artifacts | [report](../../reports/p2/p2-blinded-judge-sonnet.json) and [reply store](../../reports/p2/replies/sonnet.jsonl) exist under untracked `reports/p2/`. They have not been committed or pushed. |

The owner selected Sonnet 5 with thinking via GraceKelly, GLM 5.3 xhigh, and
Mistral; run each available judge and add the others later. The owner signed in
to Perplexity through the **Google account chooser micro-window**, not through
GraceKelly's menu. Sonnet then worked through GraceKelly's browser route. The
login may expire. The earlier synthetic probe had returned `model_auth_required`;
it does not describe the state during the successful corpus run.

The report records `model: claude-sonnet-5`, `reasoning: true`, browser adapter,
and returned model id `claude-sonnet-5`. Its code commit is `b4e2ee2`; it records
`tree_clean: false` because the working tree contained local files. The report's
control check is valid at the official H top-5 value **0.5067**. The run used
10,000 paired case bootstrap samples, seed 20260925.

## What the run established

The reply store has 118 records for 115 unique cases: **115 graded**, two
earlier `parse_failure` attempts, and one earlier `unavailable` attempt. The
runner resumed and graded every case. H has 100 cases / 500 document units;
Hm has 15 multi-document cases / 75 units. Both pools have zero missing units
and zero currently unavailable units. Hm is reported separately from H.

| Pool and arm | Judged precision | Ruler-shaped judged precision | FULL / PART / MISS |
|---|---:|---:|---:|
| H `top_k_5` control | 0.6660 | 0.7373 | 96 / 3 / 1 |
| H `top_k_1` | 0.9400 | 0.9000 | 76 / 18 / 6 |
| H P1 held-out cut | 0.7338 | 0.7715 | 93 / 6 / 1 |
| Hm `top_k_5` | 0.8400 | 0.6972 | 10 / 5 / 0 |

Here *judged precision* is the mean share of kept documents graded at least 2
out of 3. *FULL* means at least one kept document was graded 3. These are
Sonnet's judgments, not the official 0.63 ruler gate. H top-1 gains judged
precision while reducing FULL from 96 to 76; that trade-off matters before
selecting a cut.

The primary H ruler–judge agreement is per-case Kendall τ_b **0.1537**, 95% CI
**[0.0155, 0.2869]**. Its upper bound is below the plan's 0.40 threshold.
Per-document τ_b is 0.4032 and per-arm τ_b is 0.9291; both are descriptive,
not the decision statistic. The report's exact verdict is
`PROVISIONAL_RULER_DOES_NOT_TRACK`. It is **provisional** because there is one
judge and no imported human grades: Krippendorff α and human κ are unavailable.
It cannot justify changing the 0.63 gate, retrieval defaults, or product
behaviour. P1 and P1b remain `NO_SHIP`.

The H labels were approved, but these questions are still agent-authored and
none names a real shipment. Phase B's need for shipment-bound support requests
and 40 double-annotated calibration routes remains open.

Artifact SHA-256 values, useful for checking that the same local files survive
the next session:

```text
report  019131aa1952258771f47eff8c379fc3135e6a339bffa31967a3a37aa87baed0
replies c66101caa83c11e3b6cfee1e3fe10743c5cc684211265daf241da8654037f4ee
```

## Next actions

1. Refresh `git status` in both repositories and confirm the two artifact
   hashes. Preserve the untracked GraceKelly `issues.md`. Keep the frozen P2
   plan unchanged; after the first corpus judgment, a changed method needs a
   new plan. Do not treat the archived September 25 handoff as current.
2. Generate the plan's **blind human sample**: 10 H cases, two from each ruler
   quintile, 50 units. Ask Julia to grade the local page without seeing ruler
   scores or Sonnet grades. Import only her actual exported grades, then build
   a new report. Do not replace this pre-registered sample with cases chosen
   because Sonnet disagreed with the ruler.
3. When routes become available, grade both pools with GLM 5.3 xhigh and
   Mistral, then rebuild the report from all stored replies. The September 25
   GLM weekly-cap and Mistral zero-limit observations need one fresh check;
   do not assume they still apply. The runner reuses the 115 stored Sonnet
   grades, so a new Sonnet corpus pass is unnecessary.
4. Once judge reliability can be checked, inspect the largest per-case ruler
   disagreements and classify the cause. Decide on ruler or retrieval changes
   only against confirmed errors, answerability, and the unchanged release
   gate. Publish the report with provenance and an artifact verification test
   before adding a `measured` row to [EVIDENCE_INDEX.md](../../EVIDENCE_INDEX.md).

Run from `D:\RAG_new` in native PowerShell; the page is local and makes no
network requests:

```powershell
python scripts/p2_blinded_judge.py human-sample --out reports/p2/human-sample.html
python scripts/p2_blinded_judge.py human-import --grades <Julia-export.json> --grader Julia --date YYYY-MM-DD
python scripts/p2_blinded_judge.py report
```

For a newly available judge, use `judge --judge glm --glm-settings <file>` or
`judge --judge mistral --mistral-key-file <file>`, then `report`. Do not put
credentials or account tokens in this handoff. The [runner](../../scripts/p2_blinded_judge.py)
and [capability spec](../specs/blinded-relevance-judge.md) define the exact
arguments and reply-store behaviour.

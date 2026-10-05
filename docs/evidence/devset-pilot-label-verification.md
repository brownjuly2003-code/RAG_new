# 1.3b — label verification of the pilot drafts (T-78)

The 30 [pilot drafts](devset-pilot-drafts.md) were checked by one model under
the registered protocol
[«Label verification»](../specs/semantic-precision-metrics.md), rubric
`label-verification/v2`. Result: **30 verified, 0 dropped, 0 awaiting repair,
0 unverified**. 25 cases were confirmed at the first check; 5 of the 30
verified cases were confirmed only after a repair. Every verified case
carries `label_check: single_model_verified`, and `label_origin` stays
`agent_labelled`.

This is preparation: rule (b) is not met. A model check is not an approval,
no case became `real_labelled`, and the count of real labelled cases did not
rise. The result does not unblock B.2/B.3/B.5 and measures nothing about
`/api/ask`. Step 1.3b is closed — every draft is confirmed or dropped — and
the next step is 1.3c.

Files: the [verified set](../../evaluation/devset_pilot_verified.jsonl), its
[register](../../evaluation/devset_pilot_label_checks.json), the
[repairs](../../reports/devset/label-verification/repairs.jsonl), and per
round the plan, the raw replies and the decisions
([round 1](../../reports/devset/label-verification/round-1/decisions.json),
[round 2](../../reports/devset/label-verification/round-2/decisions.json)).

## Who checked, and under what rule

- **Draft author:** `gpt-6.1-sol` (OpenAI) wrote the questions, spans, facts,
  reference answers and every label of the drafts.
- **Verifier:** `claude-opus-5-5` (Anthropic) through the Claude Code CLI,
  effort `max`, no tools, one case per request, each request in a new session
  with no conversation state. It is the model of the agent that ran the plan;
  the new session is what keeps the agent's own knowledge out of the verdict.
  Prompt SHA-256
  `3f7c114428028f6518aca3f21a03f5352d0497d99d0356f2c804b9389df756ad`.
- **Repair author:** the agent of the session, the same `claude-opus-5-5`.
- **Why one model.** Plan decision D12 (owner, 2026-10-04) leaves the quality
  thread one model. Under this rubric no model of another vendor was called,
  and no person approved a case (decision D11). The word for such a check is
  `single_model_verified`; `model_verified`, the word of a check by verifiers
  of two vendors, is given to no case.

The checks. (1) Every span is verbatim in its source — a script, not a model.
(2) The facts and the reference answer follow from the spans alone. (3) The
question is answerable from the spans and the reference answer answers it;
for refusal, clarification and trap cases the registered reason holds against
the wide scan of the index. (4) The class, the `safety_critical` flag, the
trap type and `expected_action` agree with that. (5a) Every authority
document is in force on `as_of`. (5b) It is the organisation's controlled
source of the rule. (5c) The severity of the most harmful wrong answer, on
the scale `low` < `moderate` < `high` < `critical`. (5d) The critical facts
are those whose omission or misstatement leads to an unsafe, unlawful or
materially costly action. A case is confirmed when 2, 3, 4 and 5d are
confirmed, 5a and 5b are not rejected, and the level named on 5c is neither
two steps from the registered one nor across the `critical` boundary.

**Order of events.** Rubric v2, its prompt and its verifier were registered
in commit `907313d` before the first request of v2. That commit was local —
not pushed — while the requests were sent, so the order rests on the
repository's own history, not on a third-party timestamp. Earlier, under
rubric v1, one request on T64-01 had gone to each of v1's two verifiers
(GLM 5.3 and Opus 5.5) as a trial of the routes. Neither reply is counted or
kept in the stores. Both rejected check 4 on the wording of the `ru_to_en`
flag, which v1 described more loosely than its registered rule; v2 no longer
sends the three flags the verify script computes. Rubric v2 was therefore
written with those two replies on one case in view.

## Result of the first check

| Drafted class | Drafted | Decided | Rejected | Share rejected |
|---|---|---|---|---|
| `aggregation` | 4 | 4 | 0 | 0.0000 |
| `multi-doc` | 10 | 10 | 1 | 0.1000 |
| `needs-refusal/clarification` | 6 | 6 | 0 | 0.0000 |
| `single-doc` | 10 | 10 | 4 | 0.4000 |

Over the set: 5 of 30 rejected, 25 confirmed. No interval is given: nothing
is decided by these shares, and with 4 to 10 cases per class one case is 10
to 25 points of a class share.

Verified by class: `aggregation` 4, `multi-doc` 10,
`needs-refusal/clarification` 6, `single-doc` 10 — the drafted quotas. No
repair changed a class, so there is no class transition to list.

## The five rejections and what the repairs changed

| Case | Drafted class | Rejecting checks | Severity | Critical facts | Round 2 | State |
|---|---|---|---|---|---|---|
| T64-04 | `single-doc` | 5c, 5d | moderate → critical | 0 → 2 of 2 | confirmed | verified |
| T64-05 | `single-doc` | 5d | moderate → high | 0 → 1 of 1 | confirmed | verified |
| T64-06 | `single-doc` | 5d | high → high | 0 → 1 of 1 | confirmed | verified |
| T64-08 | `single-doc` | 5d | moderate → high | 0 → 2 of 3 | confirmed | verified |
| T64-13 | `multi-doc` | 5c, 5d | moderate → critical | 1 → 4 of 4 | confirmed | verified |

"Critical facts" counts the facts marked critical before and after the
repair, of the required facts of the case. Every rejection is on 5c or 5d; no
case was rejected on check 2, 3, 4, 5a or 5b in either round.

What the verifier said:

- **T64-04** (false premise: the employee NDA is said to cover tariffs only).
  Agreeing with the premise invites disclosure of customer personal data and
  access records, which the scale puts at `critical`; both facts state the
  scope of a confidentiality duty and neither was marked critical.
- **T64-05** (events that return an insurance contract draft to Legal). The
  one fact is the trigger list of a mandatory legal and financial-control
  escalation, and it was not marked critical.
- **T64-06** (sick pay after a work injury, against an outdated 60 % memo).
  The one fact is the guaranteed rate, 100 % regardless of seniority; a wrong
  rate is an unlawful, materially costly underpayment, and it was not marked
  critical.
- **T64-08** (the additional-agreement template and Article 74 of the Labour
  Code). The prohibition on using the template and the legal step that
  applies instead were not marked critical.
- **T64-13** (the cookie policy and the personal-data policy). A wrong answer
  invites unauthorised transfer or disclosure of personal data, `critical`
  on the scale; the data-minimisation limit and its masking and logging
  controls were not marked critical.

The repair author agreed with all five rejections and declared no drop. Each
repair changes `wrong_answer_severity`, `critical_facts` or both, and nothing
else: questions, spans, facts, reference answers, classes, flags, trap types,
actions and documents are as drafted. Where the severity changed, the repair
took the level the verifier had named in round 1.

The documents did not change, so the recomputed families of the repaired
cases are the drafted ones: T64-04 — `family-c3346b4cbd17`; T64-05 —
`family-1335dc50d706`; T64-06 — `family-0287c6d94d73`; T64-08 —
`family-2b2b0aee7e47`; T64-13 — `family-74d57abc1479`.

**Round 2.** The verifier then checked each repaired case in full, in a new
session with no trace of round 1, and confirmed all 5. This is a consistency
check by the model that wrote the repair, not a check by another party. The
two groups are counted apart: 25 cases whose label was written by one
vendor's model and checked by another's, and 5 cases whose repaired fields
were written and checked by the same model. The 5 carry `repair_author` in
their `label_check`.

**Flags and quotas.** The `safety_critical` flag is not the severity: it says
that a wrong answer is a safety risk. T64-04 and T64-13 are now `critical`
for disclosure of personal data and keep the flag false, and check 4
confirmed that in round 2. Count of safety-critical verified: 3 (T64-14,
T64-25, T64-29), and 3 without `authority_unverified`. Cases flagged
`authority_unverified`: 0 — the verifier answered `unverifiable` on 5a or 5b
for no case. Dropped cases: none, so question в of plan G38, the replacement
of a dropped case, has nothing to replace in the pilot.

## Severity differences

| Case | Round | Registered | Named by the verifier | Steps | Across `critical` |
|---|---|---|---|---|---|
| T64-03 | 1 | moderate | low | 1 | no |
| T64-04 | 1 | moderate | critical | 2 | yes |
| T64-05 | 1 | moderate | high | 1 | no |
| T64-07 | 1 | moderate | high | 1 | no |
| T64-08 | 1 | moderate | high | 1 | no |
| T64-12 | 1 | moderate | high | 1 | no |
| T64-13 | 1 | moderate | critical | 2 | yes |
| T64-18 | 1 | moderate | high | 1 | no |

The first check named another level for 8 of 30 cases. All eight were
drafted `moderate`, and seven of the eight were named higher. Two differences
are rejections (T64-04, T64-13). Six are one step and do not cross
`critical`: by the rule they are published, not rejected. Of those six,
T64-05 and T64-08 were rejected on 5d and their repair took the named level.
T64-03, T64-07, T64-12 and T64-18 stay verified with the severity as drafted:
for these four the set holds a level the verifier did not name.

Round 2 shows no difference, which follows from the repairs taking the named
level and is not a second opinion on the severity. Severities of the set:
the drafts hold 19 `moderate`, 7 `high` and 4 `critical`; the verified set
holds 15 `moderate`, 9 `high` and 6 `critical`; neither holds a `low`.

## What was sent

35 requests in 36 attempts — 30 cases in round 1, 5 in round 2 — carried
691 842 characters and 566 corpus texts to the one registered verifier, with
every source named by a pseudonym. Wide-scan passages went with 10 requests
of round 1 and 2 of round 2, 28 to 40 passages each: the six cases without
spans and the four trap cases with spans.

One attempt on T64-18 met an unavailable verifier: the CLI exited when the
account's usage limit was reached. The store keeps that row as `unavailable`;
its text may have left the machine, so it is counted; the request was sent
again after the limit reset and answered. No reply failed the form: the
stores hold 35 valid rows and that one row.

The CLI reported a notional cost of $13.27 — a subscription route, not a
bill — and 2.0 hours of request time. Claude Code CLI 2.1.289, run on
2026-10-04 by the laptop's clock (UTC−4). The version and the date are
recorded in this capsule only: the stores carry neither.

## Provenance

| What | SHA-256 |
|---|---|
| Drafts, `evaluation/devset_pilot.jsonl` | `c8688f470271ec49c4d1f2c5415396c067431e9a7f715297d53abc9a18ef5bdb` |
| Family map, `evaluation/document_families.json` | `54bdb736180e00325bff20f49e2b9d985dd62278fe9f9cdb6161a0da719e3584` |
| Corpus, 201 files | `c8562a64f88f72172f29e30865091be79f08d00ce65fbf675f34de64dcebe343` |
| Wide scan, `wide-scan.json` | `8faf58d4ef3091875b0b263aa05e99cab30b8c0c7948ab06a0fca33436d8466b` |
| Chunk archive, `evaluation/gr1b-4436d61-graph-chunks.json.gz` | `2a9da515a4c69b46453a59ed6d0bb772b0aad6fed23c87ee465851b43dbdef12` |
| Plan of round 1 | `3a820b90eb961d5f7e9f5bb396e40249d68381aa64bc6bb8786b0f63413e1d74` |
| Replies of round 1 | `9d521fbfeb47c3f5f64646bca106efb318e8e07d614ab7e10afd550065d0aa5e` |
| Repairs, `repairs.jsonl` | `e4413cf7260acc4785de0da4c17578882b4689c1995f5a106437bb762e75b3a5` |
| Plan of round 2 | `7fe048c20af2caf684b7124bd86c0b9b32a13302f63be23ddf2c1e5c83c05af4` |
| Replies of round 2 | `cc74c98bf5c0a39a57acfbd4ef3bea5dbc742cc750cce700b8a53ad103777fd3` |
| Verified set | `05ebf00743e2ae3b6a8117f735a3d9a34b451f8bf066a4dd1dfcaadf8e708df4` |
| Register | `c756baae3641853bfbf47022b7743836a9ad1aef86bc2234368c43a3aba6ec43` |

Plans, replies, repairs and the wide scan lie in
`reports/devset/label-verification/`. A plan holds no request text: the tool
rebuilds each request from the drafts, the corpus, the scan and the repairs
and compares its SHA-256 with the plan's.

## How to recompute

`python -m scripts.devset_label_verify check --repairs
reports/devset/label-verification/repairs.jsonl` recomputes every decision
from the stored replies and refuses a verified set or a register that
differs. With `--rebuild` it also rebuilds both plans from the corpus, the
wide scan and the repairs. `tests/test_devset_label_checks_artifact.py` runs
both — the rebuild only where the corpus is present — and holds this capsule
to the register. What the tool must do is in its
[requirement](../specs/label-verification.md).

## What this check does not show

- **It is a check by one model.** Errors this model makes systematically
  pass unseen — in reading a rule, in judging a severity — and there is no
  second verifier whose disagreement would point at them. The check bounds
  label errors; it does not prove their absence.
- **The repaired cases have one author and one checker.** On the 25
  unrepaired cases the label and its check come from models of two vendors.
  On the 5 repaired cases the repaired fields were written and checked by the
  same model, which can catch a repair its own spans do not support and
  little else.
- **The rejections are about two late definitions.** The severity scale and
  the definition of a critical fact were written after the drafts were
  labelled, and all five rejections are on 5c and 5d. The shares above say
  mostly that the drafts were labelled without those definitions; they are
  not an error rate of the draft author's reading of the sources.
- **Nothing was rejected on checks 2, 3, 4, 5a and 5b.** Either the drafts
  are right there, or this verifier does not see what is wrong. One model
  cannot tell the two apart.
- **The wide scan is a budget, not a measured recall.** At most 40 of the
  5589 chunks of the index reach the verifier for one question. A passage
  outside the scan can leave an answerable question registered as
  unanswerable (plan G37); at acceptance such a case falls under the
  `gold_error` rule.
- **Authority is checked on the documents as supplied.** Whether an external
  norm a document cites says the same was not checked.
- **Thirty cases.** The set is a pilot; its quotas, families and reserve are
  those of the [drafts](devset-pilot-drafts.md), with their limits.

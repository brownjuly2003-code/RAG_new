# P2 plan: a blinded relevance judgment beside the official ruler

Pre-registered 2026-09-25, before any judge saw a corpus document. Capability:
[blinded-relevance-judge](blinded-relevance-judge.md). Predecessors:
[P1 plan](p1-adaptive-k-plan.md) (§ Next, item 3), [P1 capsule](../evidence/p1-adaptive-k.md).

## Question

Does the official context-precision ruler (`evaluation/ragas_eval.py::context_precision`)
track an independent, blinded judgment of whether each retrieved document helps answer
the question? And under that judgment, how precise are the published top-5 control and
the P1 cuts?

The ruler scores a document by the share of question words and expected keywords it
contains. The P1 diagnostics found that question words alone give 0.3931 of the control's
0.5067. Phase C's 0.63 precision gate is measured with this ruler. If the ruler does not
track judged relevance, then passing or failing the gate says little about retrieval
quality. The owner decides what follows. P2 changes no gate, no default and no product
behaviour.

## Inputs

- **H:** `evaluation/c1a-c06bdf5-phase-c-C-candidates.json.gz`, pool `91ce1745…`,
  100 cases. The units are each case's top five documents as the ruler scored them:
  `cands[:5]` under the ruler's 6000-character cap. That gives 500 (case, document) units.
  On 2026-09-25, a probe that read only the pool found that the cap cuts none of them.
  The P1 fresh reranker order reproduces this order for all 100 cases, so every P1 cut is
  a prefix of these five.
- **Hm:** `evaluation/gr3-32de532-bucket-Hm-candidates.json.gz`, pool `3a302079…`,
  15 multi-document cases and 75 units. Hm is judged and reported separately and never
  pooled with H.
- **Ruler inputs:** the question and the expected keywords of each case's dataset, as P1
  used them. Keywords go to the ruler only, never to a judge.
- **Arms:** the published [P1 report](../../reports/p1/p1-adaptive-k.json):
  - the kept counts of all 37 grid cells, on H and on Hm;
  - the 5-fold held-out headline;
  - the label-using best-prefix oracle `oracle_k`.

  Every arm keeps a prefix of the five judged documents, so re-scoring an arm needs no
  new judgment.
- **Labels:** the journey labels of the H cases, as the label manifest and its approvals
  sidecar record them at run time. They are recorded as provenance. They do not enter
  any metric.

## Judges (owner's data-governance decision, 2026-09-25)

Julia's words: «давай выберем sonnet 5 через API Grace Kelly с thinking, GLM 5.3 xhigh,
mistral … То есть 3 варианта, бер[ём] что доступно, добираем». So: three judges; run
whichever is available, and add the others when they become available.

| Judge | Route | Status on 2026-09-25 |
|---|---|---|
| `sonnet` | Claude Sonnet 5 with thinking, through the local GraceKelly V2 API (`POST /api/v1/orchestrate`, `model: "claude-sonnet-5"`, `reasoning: true`, `adapter_hint: "browser"`, `decompose: false`). GraceKelly drives the Perplexity Pro web UI. | Blocked: the GraceKelly browser profile is not signed in to Perplexity (HTTP 503 `model_auth_required` on a synthetic probe) |
| `glm` | GLM 5.3 through the direct z.ai API, per the [direct runbook](../operations/direct-glm-5.3.md): `glm-5.3`, `output_config.effort: "xhigh"`, thinking budget 8000, `max_tokens` 48000 | Blocked: weekly cap (code 1310) until 2026-09-28 05:56 UTC+8 |
| `mistral` | `mistral-medium-2604` through `https://api.mistral.ai/v1/chat/completions`, `temperature: 0`, `random_seed: 20260925`, `response_format: {"type": "json_object"}`, `max_tokens: 4000` | Blocked: synthetic probes on all three keys got HTTP 429 with `x-ratelimit-limit-req-minute: 0`, while the model list answered 200. That happened from a Russian exit address and again from a Canadian one (Cloudflare `loc=CA`), so the exit address alone does not explain it. The owner checks the account's limits. The owner's route for Mistral is `deproject-mac` with its VPN on; the Mac also runs an HH job that needs the VPN off, so the owner decides when the VPN is on |

The judges run where their route works: `sonnet` on the Windows machine that holds the
GraceKelly profile, `mistral` wherever its keys get a non-zero limit (the owner's route is
the Mac under the VPN), and `glm` from either. Replies are stored per judge and merged by
the runner.

Every available judge grades every unit of both pools. No request carries a key,
a label, a keyword, a rank, a score or an arm name. Corpus text leaves the machine: to
Perplexity and Anthropic through GraceKelly, to z.ai, and to Mistral. The owner's
decision covers this.

## Blinding and the prompt

- One request per case, 115 per judge.
- The request holds the question and the case's five documents in a per-case random
  order: `random.Random(f"20260925:{case_id}").shuffle` over positions 0–4. The documents
  are labelled D1–D5 by position in that order. Every judge gets the same bytes for the
  same case.
- Each document's text is sent exactly as the ruler scored it, including its contextual
  header line.
- The instruction is fixed in the runner. Its SHA-256 goes into the report. It asks the
  judge to grade each document on its own, not against the others, using only the given
  text:
  - **3**: answers the question fully on its own;
  - **2**: contains part of the answer, but is not enough on its own;
  - **1**: on the question's topic, but does not help answer it;
  - **0**: unrelated.
- The reply is one JSON object: `{"grades": [{"doc": "D1", "grade": 0-3, "reason":
  "…"}, …]}`, with exactly one entry per presented document.
- **Parsing:**
  - The parser takes the first balanced JSON object in the reply text; a web-UI route
    can wrap it in prose or a code fence.
  - A reply that misses, repeats or adds a label, or gives a grade outside the integers
    0–3, is a parse failure. It is retried with a new request, at most twice. After that,
    the case is `missing` for that judge.
- **Failures:**
  - Transport errors are retried with backoff.
  - A rate limit that names a reset time is waited out.
  - An authentication, quota or zero-limit reply marks the judge `unavailable` for the
    run. It never counts as a grade.
- Replies are stored as they arrive: raw text, reported model id, timing and usage. No
  credentials are stored. A rerun skips the cases a judge has already graded.

## Consensus

- Per unit, the consensus is the lower median of the judges that graded it: one judge
  gives its grade, two give the lower of the two, three give the middle one.
- A judge missing more than 5% of a pool's units is left out of that pool's consensus.
  It is still reported on its own.
- A unit is **relevant** when its consensus is 2 or more, and **sufficient** when it is 3.

## Metrics

Per pool; H is the headline. Every metric is also reported per judge.

1. **Judged precision** of an arm: per case, the share of kept documents that are
   relevant, averaged over cases. This is the headline number.
2. **Ruler-shaped judged precision:** the official formula, with its 1/rank weights over
   the reranker ranks, where each document's relevance is its grade divided by 3.
3. **Answerability:** the share of cases whose kept documents include a sufficient one.
   A case with at most a relevant one is partial; any other case is unanswered. These
   are the judgment's analogue of FULL, PART and MISS.
4. **Arms:**
   - the control `top_k_5`;
   - all 37 P1 grid cells;
   - the P1 held-out headline;
   - the best-prefix oracle.

   Each arm gets metrics 1–3, with a paired case bootstrap against the control.
5. **Ruler–judge agreement on H.** Kendall τ_b between the ruler and the consensus at
   three levels:
   - **per case** (primary): the ruler's per-case precision of `top_k_5` against metric
     2 on the same cases. The two share the same weighting, so they differ only in how a
     document's relevance is scored.
   - **per unit:** the ruler's per-document relevance, the formula applied to one
     document, against the consensus grade, over the 500 units.
   - **per arm:** the ruler's aggregate precision against the judged precision, over
     the 37 grid cells.

   Also reported, and descriptive only:
   - the same per-unit τ_b for the ruler's question-word part alone and for its keyword
     part alone;
   - a cross-table of ruler relevance quintiles against grades.
6. **Judge reliability:**
   - pairwise quadratic-weighted Cohen's κ and Krippendorff's α (ordinal) over the units
     all judges graded;
   - per judge, the grade distribution and the missing count.
7. **Human adjudication.** Julia grades a stratified sample with the same scale in
   Russian, blind to every score.
   - **Sample.** Sort the H cases by the ruler's per-case precision of `top_k_5`
     (four decimals, ties by case id), and split them into five consecutive groups of
     20. From each group, `random.Random(20260925).sample(group, 2)` draws two cases,
     taking the groups in order. That gives 10 cases and 50 units.
   - **Presentation.** Each case shows its documents in the judges' order. The runner
     writes the sample as a local, self-contained page with no network access. The page
     exports her grades to a JSON file, which the runner imports.
   - **Measures.** The consensus and each judge against her grades: quadratic-weighted κ.

Every confidence interval is a percentile interval over 10000 case-bootstrap resamples,
seed 20260925.

## Decision rule (on H; Hm is reported, never decided)

1. **Reliability.**
   - With two or more judges in the consensus, Krippendorff's α must be at least 0.667.
   - With the human sample graded, the consensus-to-human quadratic-weighted κ must be
     at least 0.60.
   - A failed check gives `JUDGE_UNRELIABLE`, and no ruler verdict.
   - When neither check is possible (one judge, no human grades), the verdict carries
     the prefix `PROVISIONAL_` and cannot support a gate change.
2. **Ruler verdict,** from the per-case τ_b's CI95:
   - `RULER_TRACKS`: the lower bound is at least 0.40;
   - `RULER_DOES_NOT_TRACK`: the upper bound is below 0.40;
   - `INCONCLUSIVE`: otherwise.
3. **Descriptive only.** The per-unit and per-arm τ_b, the judged precision of
   every arm, and its position against the 0.63 gate are reported without a verdict.
   The gate is defined on the ruler.

## Versions

A judge that becomes available later is added in a new run over the stored replies of
the earlier judges, so earlier judges are not called again. Each run publishes a new
report named by its judge set, `reports/p2/p2-blinded-judge-<judges>.json`. Earlier
reports stay in the tree. The capsule's headline follows the newest report and lists
every version. A run with no available judge publishes nothing: `NOT_EVIDENCE`.

## Integrity record

- Before this plan was committed, no judge saw a corpus document. The judge calls made
  before it were synthetic probes with no corpus text:
  - GraceKelly with Sonnet 5, HTTP 503, and a read-only check of its browser profile:
    no Perplexity login;
  - Mistral on all three keys, from a Russian and then from a Canadian exit address,
    HTTP 429 with a zero limit each time.
- The probe that counted the units read only the two pools.
- Amendments are allowed until the first corpus judgment and are recorded here. After
  it, a change needs a new plan.

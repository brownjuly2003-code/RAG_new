# P2 — the GLM + Sonnet consensus checked against two model references (plan slice 1.1)

Computed 2026-10-04 from grades already in the repository; no model was
called. The development ruler takes its relevance grades from the registered
P2 lower-median consensus of GLM 5.3 and Sonnet 5
([P2](p2-blinded-relevance-judgment.md)). No person grades the blind sample
(plan decision D11, 2026-10-03), so the consensus is checked against two
reference models that graded the same ten H cases and 50 documents blind, from
the same requests: [GPT-6-Astra](p2-astra-reference-sample.md) (OpenAI — a
vendor outside the judge set) and [Opus 5.5](p2-opus-reference-sample.md)
(Anthropic, the vendor of the Sonnet judge — a control, not an independent
voice).

## Result

Quadratic-weighted κ over the 50 documents, with a bootstrap CI95 clustered
by case: 10 000 resamples of cases, each case entering with its five
documents, percentile interval, seed 20260925 (`BOOTSTRAP_SAMPLES` and `SEED`
of `evaluation/blinded_judge.py`). κ was defined in all 10 000 resamples of
every comparison.

| Comparison | κ | CI95 | Exact agreement | CI95 against 0.7 |
|---|---:|---|---:|---|
| consensus ↔ Astra | 0.9333 | [0.8511, 0.9859] | 45/50 | entirely above |
| consensus ↔ Opus | 0.9604 | [0.9087, 1.0000] | 47/50 | entirely above |

**Verdict: branch 3 of the registered rule — the ruler is
`model-cross-checked`.** It is never `human-validated`: no human grade was
used, and none exists.

The rule was registered before this calculation
([metrics spec](../specs/semantic-precision-metrics.md), «Relevance grades»,
revision of 2026-10-03; plan decision D2 as changed by D11). Both references
must clear the threshold, and the branches are read in this order:

1. a CI95 entirely below 0.7 for either reference — the consensus is not used
   as the ruler; a new judge set is named before any of its grades is
   compared with a reference and is checked by this rule once, on a fresh
   reference sample;
2. otherwise, a CI95 straddling 0.7 for either reference — slice 1.1b: the
   reference sample grows to 30 cases before any semantic-gain claim and
   before acceptance 4.1, and the capsules of engineering runs carry
   `provisional_ruler`;
3. otherwise — both CI95 entirely at or above 0.7 — the ruler is
   `model-cross-checked`.

Neither interval reaches below 0.7 (lower bounds 0.8511 and 0.9087), so
branches 1 and 2 do not apply and slice 1.1b is not needed.

## Where the consensus and the references differ

The consensus differs from at least one reference on five documents, each
time by one grade and with the consensus as the lower grade — with two judges
the lower median is the lower of the two grades. Positions are those of the
original top-five order.

| Case | Position | GLM | Sonnet | Consensus | Astra | Opus |
|---|---:|---:|---:|---:|---:|---:|
| aircargo-employment-contract-essential-terms | 3 | 1 | 1 | 1 | 2 | 2 |
| aircargo-driver-job-documents | 2 | 2 | 3 | 2 | 3 | 3 |
| aircargo-driver-job-documents | 3 | 1 | 2 | 1 | 2 | 1 |
| aircargo-contract-termination-fields | 5 | 1 | 0 | 0 | 1 | 1 |
| aircargo-sick-leave-required-fields | 1 | 1 | 1 | 1 | 2 | 1 |

On the relevant / not relevant split fixed in advance (grade ≥ 2) the
consensus agrees on 47/50 with Astra and on 49/50 with Opus; at grade ≥ 3,
the sensitivity view, on 49/50 with each. These counts are descriptive and
decide nothing. The full 4 × 4 tables of every comparison are in the
[artifact](../../reports/p2/p2-model-reference-kappa.json).

## Orientation — does not enter the rule

Agreement between the references and of each single judge with each
reference, computed the same way. The five κ values were published in the
two reference capsules before this slice and replay here; the intervals are
new.

| Comparison | κ | CI95 | Exact agreement |
|---|---:|---|---:|
| Astra ↔ Opus | 0.9727 | [0.9257, 1.0000] | 48/50 |
| GLM ↔ Astra | 0.8824 | [0.8076, 0.9433] | 42/50 |
| GLM ↔ Opus | 0.9133 | [0.8580, 0.9672] | 44/50 |
| Sonnet ↔ Astra | 0.8930 | [0.7967, 0.9638] | 42/50 |
| Sonnet ↔ Opus | 0.8950 | [0.8267, 0.9485] | 42/50 |

The disagreement matrix of the two references is empty except for two
documents graded 2 by Astra and 1 by Opus (rows 3 and 5 of the table above).
Their agreement is a reference for agreement, not a mathematical ceiling: the
consensus κ is not divided by it and no threshold is lowered by it.

## Caveats

1. **A model check, not a human one.** The check is agreement between models.
   It cannot detect an error the models share (plan G37). Here the reference
   labels are model labels, inter-annotator reproducibility is not
   established, and a retest measures one model's stability only.
2. **Not blind to its likely outcome.** The references' grades and each
   judge's κ to them (0.88–0.91) were published before the rule was written,
   so the check is not blind to its likely outcome. The 0.7 threshold is the
   one registered on 2026-09-30 for human grades; it was not adjusted.
3. **Scope of the status.** `model-cross-checked` covers the question classes
   of the sample and the unexpanded top-5 contexts of P2. The sample is ten H
   cases; it holds no Hm case. New question classes and expanded contexts
   need a reference sub-sample of at least 10 cases per class before any
   semantic gain is claimed on them; that sub-sample has no slice row yet
   (plan G38, г).
4. **No contamination controls.** The sample carries no contamination
   controls of the G8 calibration protocol: its grades were published before
   the protocol was written (plan G38, д).

Two further limits of the numbers. Ten clusters are few for a percentile
bootstrap; the intervals are the registered ones and carry no small-sample
correction. An upper bound of 1.0000 means that at least 2.5 % of the
resamples drew no case with a disagreement.

## What the status changes and what it does not

- Within the scope of caveat 3, a result of a track-3 experiment or of
  acceptance 4.1 on this ruler may be reported as a gain on a
  `model-cross-checked` ruler; every such capsule says that the check was
  done by models.
- The baseline of slice 2.5 (T-65) stays `provisional_ruler` whatever this
  verdict: its contexts are expanded (caveat 3).
- P2's `RULER_DOES_NOT_TRACK` verdict on the lexical ruler, the official
  phase-C gate and every retrieval default are unchanged. The dated P2
  capsules are not rewritten.

## Provenance and checks

- Corpus: H pool SHA-256
  `91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10`; grading
  instruction SHA-256
  `7877c3845a742013e3c189e260ef506ba07dc65749fa3df8455a181a4dcedc33`. For
  every case the four graders hold one request SHA-256, listed in the
  artifact.
- Inputs, each checked before the calculation:
  - P2 report `reports/p2/p2-blinded-judge-glm+sonnet.json`, SHA-256
    `4c1e60cdad361799a291fa88d0d0c3a35675ad772630a0147615ab30d3a31e7d`; it
    names the sample (`human.sample_case_ids`) and the two judge stores;
  - judge stores `reports/p2/replies/glm.jsonl`
    `aac5c00993737194b0b5beaa9ee0cebc28d0434b647997056ffc1f69606f3da9` and
    `reports/p2/replies/sonnet.jsonl`
    `c66101caa83c11e3b6cfee1e3fe10743c5cc684211265daf241da8654037f4ee`, equal
    to the SHA-256 the P2 report records;
  - reference stores `reports/p2/astra-reference/replies.jsonl`
    `6411f772c57629cb04118ba3e9892d1956b8c31db448229628fdf874458e5164` and
    `reports/p2/opus-reference/replies.jsonl`
    `f17b1b973249365ba51a5e0c476024e7933de698ffeb2cf29b32ea1ff1aa3a8f`, equal
    to `reply_store_sha256` of the summaries beside them (summary SHA-256
    `95f6351ab27f84a89465ef2192ab00a29a55f0c12d4cbe004c192270fef4364d` and
    `d785df2672b7cb24398b15a3be6695f9d498003ed773ce22b564544d606ac04d`). The
    grades are the `grades` field, in the original top-five order.
- Code: `scripts/p2_reference_kappa.py`, SHA-256
  `3f68a2853c9bddffc3ee98929eecd22defe9ef1aefad96c69cad63b7cf5ed6a4`, committed
  together with this capsule; it takes `quadratic_kappa`, `consensus_grades`,
  `read_store`, `_percentile`, `SEED` and `BOOTSTRAP_SAMPLES` from
  `evaluation/blinded_judge.py`, SHA-256
  `73650a061fdfc4639282a833d13fc496b9c3949de5964eabd85b2d787a0bfe6e` — the
  bytes the P2 report pins at commit `fa9e598`.
- Config: threshold 0.7; 10 000 resamples; seed 20260925, a new generator for
  each comparison; cases in the order of `human.sample_case_ids`, ten indices
  per resample; bounds by linear interpolation at 0.025 and 0.975; a resample
  with an undefined κ is dropped and counted (none was).
- Artifact `reports/p2/p2-model-reference-kappa.json`, SHA-256
  `2b2236b8da48b8b8437170cab6256785f0fa27834d6171146304c447096275ef`.
  `python -m scripts.p2_reference_kappa` rewrites it from the inputs.
- The calculation refuses, and writes nothing, when a store differs from its
  recorded SHA-256, when a reference's cases differ from the P2 sample, when
  a judge lacks a graded row for a sample case, when the graders of a case
  did not see one request, or when a published κ does not replay.
- `tests/test_p2_reference_kappa_artifact.py` rebuilds the artifact, replays
  every κ and interval with its own loop (reference grades taken from the
  `ratings.json` files), re-reads the rule from the intervals, and checks the
  tables, hashes and caveats of this capsule and three of the refusals.
- Executor: Opus through the MyFlow writer, by the owner's order of
  2026-10-04 — GLM 5.3 was on its weekly cap (`1310`).

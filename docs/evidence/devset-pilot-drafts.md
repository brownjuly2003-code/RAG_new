# 1.3a — pilot development-set drafts (T-64)

The [30 JSONL cases](../../evaluation/devset_pilot.jsonl) follow the
[1.2 case schema](../specs/semantic-precision-metrics.md). Their status,
`label_origin` and `evidence_class` are `agent_labelled`;
`approved_by: null`, **0 approved**. This is preparation: slice rule
**(b) applies only after Julia approves the batches in 1.3b**. The set does
**not unblock B.2/B.3/B.5** or measure `/api/ask` quality.

Quotas are **10 single-doc, 10 multi-doc, 4 aggregation and 6
needs-refusal/clarification**. Adversarial/unanswerable cases are **10/30
(33.3%)**, including all six unresolvable cases. Trap counts: false premise 3,
out of corpus 1, outdated rule 2, conflicting documents 1, dangerous goods 1.
Overlapping flags: RU→EN 10, numeric 9, safety-critical 3. RU→EN is a
registered proxy (`cyrillic-query-missing-latin-fact-token-v1`): the question
contains a Cyrillic letter and at least one required fact contains a Latin
token of three or more letters (`[A-Za-z]{3,}`) absent from the question
as a case-insensitive substring. The flag is derived, including Latin tokens
in field names and template placeholders; it does not request an English
answer. No question requests an answer language.

There is **one registered generator, gpt-6.1-sol, with two question styles**:
`agent_style_A`, formal operator questions, and `agent_style_B`, colloquial
support-ticket phrasing, **15/15**. Questions and labels are agent-authored,
unapproved and have no independent generator control. `as_of: 2026-10-01`
sets the scenario date; it does not establish that an internal rule is
current. The owner must confirm authority and applicability: a template
does not establish shipment details or the law in force.

The [pilot manifest](../../evaluation/devset_pilot.manifest.json) pins the
JSONL and family-register SHA-256, seed **6413030**, algorithm, quotas and
the 30 drawn sections. The corpus is **201 files**, SHA-256
`c8562a64f88f72172f29e30865091be79f08d00ce65fbf675f34de64dcebe343`, from the
[corpus manifest](../../evaluation/aircargo_corpus.manifest.json).
Every source file is checked against its manifest SHA-256 before decoding.
Sections are markdown heading bodies with their heading chain; offsets are
**Unicode code-point indices into the UTF-8-decoded source file**, with
line endings preserved. The registered `document-specific-heading-bodies-v2`
frame has **982 sections** with at least 180 stripped characters, sorted by
`(source_id, char_start)`. It excludes the pure meta-headings `История изменений`,
`Связанные документы` and `Порядок пересмотра и актуализации`, and sections
where more than one third of counted lines occur in at least three corpus
documents. Lines are normalized by collapsing whitespace and lower-casing;
only lines of at least eight normalized characters count. The line rule alone
retains **1059** sections; excluding those meta-headings removes another **77**.
`random.Random(6413030).sample(..., 30)` selects without replacement, with no
family restriction. The first draw over the unfiltered 4007-section frame was
discarded before review because 16 of 24 answerable cases rested on template
text; its original family restriction was vacuous. Partner sections satisfy
the same eligibility rule and have recorded selection reasons. JSONL SHA-256:
`c8688f470271ec49c4d1f2c5415396c067431e9a7f715297d53abc9a18ef5bdb`.

The 24 answerable cases carry **38 source spans**, each with a filename,
file revision SHA-256, corpus version, heading path, offsets, SHA-256 of the
exact UTF-8 span bytes and normalized text. Required evidence groups list
explicit alternatives by `span_id`. Required and critical facts construct
`evaluation.semantic_ruler.Fact`, including polarity, unit, condition and
tolerance. Under `pilot-claim-quote-v2`, `text` is an atomic answer claim
(at most 160 characters); `source_quote` is a contiguous verbatim excerpt
of an own gold span (at most 300 characters). Context presence matches the
quote, answer presence matches the claim: specificity belongs to evidence,
so a short department name need not repeat its table-row duties. All non-derived
claims, including numeric claims, are grounded by normalized containment in
their quote, optionally prefixed with a generic governing cue; normalization is casefold plus whitespace
collapse, with punctuation retained. Numeric subjects and conditions are short source phrases within
the published matcher's claim window. The KPI/OKR range claims use their
upper bounds, next to the printed units; the full source range stays in
`text`. The unitless performance-review score uses textual containment.
Aggregations register their operation, bounded scope and operands; their
numeric results carry `derived: true`, are not printed in a source and are
excluded only from quote and source-span checks. Every case has a minimal
Russian `reference_answer` (at most 700 characters), answering exactly its
question; required and critical claims must score 1.0 on it or be explicitly
referred to blind judgment. Unrequested list items, duties and table rows
remain in the spans. T64-23's claims are the two department names and their
derived count; T64-21 requires only the evidence intersection and its count.
Prohibitions and obligations carry generic governing cues in the claim,
because the textual matcher ignores polarity; list headings and their
supporting items remain in the quote, rather than becoming whole-list claims.
The six unresolvable cases have no gold spans or facts
for the missing answer, but carry an action, reason, source addresses and a
reference answer stating that action and reason.
Escalation does not authorize an operation.

The [family register](../../evaluation/document_families.json) is
**draft — owner confirms with the first approved batch (spec: document
family)**. The primary map is topic only, `devset_sources.topic()`:
**84 families over 201 documents, 57 singleton families**. Each membership
records its topic and cross-reference partner IDs; **560 cross-document
`cross_ref` links** from `ingestion/structure_graph.py` are stored once,
with no LLM calls. The eight-folder grouping and the cross-reference closure
are sensitivity views, neither a cluster unit. The latter merges topic
families into **24 families**, the largest containing **171 documents**.

**Deviation from the specification's folder/topic/`cross_ref` family rule:**
the primary map does not merge topics by `cross_ref`. Transitive merging collapsed 61 topics into one 171-document
family and left only three pilot components. Topic families preserve the
declared subject grouping; cross-reference dependence remains visible in
the closure sensitivity view. The literal G22 closure of folder ∪ topic ∪
`cross_ref` collapses all 201 documents into **one family**. This deviation
is retained under the orchestrator's accepted risk F-T-64-1; the specification
and plan are unchanged. Julia must confirm this draft map with the first
approved batch.

The pilot touches **34 documents / 23 topic families** and has **19
case–family components**, with sizes **fourteen singletons, 2, 2, 3, 4 and 5**.
These are registered components, not proof of sufficient statistical power.

The development footprint uses documents actually used by cases. For H,
all **500/500** P2 graded texts loaded through `blinded_judge._load_pool`
match the phase-C first five `cands` exactly and map unambiguously to
`cand_sources`: **117 documents / 41 families**. Hm uses the curated cases'
`source_documents`: **13 documents / 7 families**. Their union is **118
documents / 42 families**, also registered for P1b/P2 and the loss map;
P1b expansion stays inside the seed documents. The pilot adds **7** families,
so the combined footprint is **49 families**. Input artifact SHA-256 values,
including the P2 report and its provenance inputs, are pinned in the register.

Candidate/pre-rerank pools cover **200/201 documents and all 84 families**.
This is a sensitivity number, not the footprint definition: retrieval scans
the corpus on every query, so pool membership cannot mark a family as used.

The registered `holdout_reserve_families` lists **35 families / 36
documents**, outside the development footprint. The reserve is skewed
toward HR/legal templates; **no claims, customs or dangerous-goods families
remain**. Holdout representativeness is an owner decision in **1.3b/1.3e**:
add independent sources or accept the skew. This slice creates no holdout.
`excluded_from_judges: []` (D10).

The register's `cross_ref_dependence` records **105 direct links** between
documents in development topic families and reserve documents. **25 of 35
reserve families** directly link to a development family. Removing those
leaves **10 families / 10 documents**: nine HR policies and one accountant
job-description template (all in the HR folders). The 105-link definition
includes every member of a development family, rather than only documents
actually used by cases. The owner's options are to add independent sources
or accept topic-level independence with this stated cross-reference leakage.

The [verifier](../../evaluation/devset.py) checks schema, enums, quotas,
styles, traps, `Fact` construction, topic memberships, both sensitivity
views, historical footprint provenance, reserve separation and pilot
components, the derived RU→EN flag and its registered count, and the absence
of answer-language requests. Source verification regenerates the structural graph, repeats
the filtered draw and recomputes file/span hashes, offsets and supporting text.
Each span's normalized text must occur in at most **two corpus documents**;
each required or critical fact's source quote with at least **12 normalized characters**
must occur in at most **three**. Document-specific controls remain accepted;
template-anchored spans and facts are rejected. These checks constrain exact
text repetition; they do not establish question quality or independent labels.
The manifest registers the generic governing-cue list, claim atomicity and
grounding, quote specificity, reference-answer coverage and numeric self-coverage
rules. Each non-derived numeric fact must score 1.0 on its own exact source
spans or appear explicitly in `needs_blind_judgment`. Correct numeric-answer
and all 30 reference answers are checked; derived totals have answer controls;
T64-18's opposite permission statement scores 0.0. The registered
`semantic-ruler/claim-window-v3` matcher is unchanged. A limitation for the
owner: any negation cue in a numeric candidate window, including Russian
`не более` / `не менее`, requires blind judgment; a candidate is not a
confirmed fact. Critical facts still require blind human confirmation.

Negative controls reject editorial claims, whole-list claims, quotes absent
from an own span, and claims missing from the minimal reference answer.
Valid composed claims, common names with specific quotes and derived facts
without quotes remain accepted. These are deterministic labelling controls,
not measurements of paraphrase recognition: textual answer presence still
depends on registered claim containment. The claim/quote split does not make
the published matcher semantic or validate agent labels.

The corpus resolves through `AIRCARGO_CORPUS_DIR`, then the repository's
sibling `RAG_Support_Assistant`. With no corpus, metadata and footprint
checks still run; source-dependent tests skip with a reason, which does not
validate spans. D3 now has drafts to review at `evaluation/devset_pilot.jsonl`
and a family map to confirm; Julia reviews traps, critical and complex cases.

# Graph enablement policy — the pre-registered rule for the graph retrieval branch

Registered 2026-10-05 under [`plan_03_10_26.md`](../../archive/docs/specs/plan_03_10_26.md) step 3.0
(the owner's request of 2026-09-30), by the agent of the session on the plan's
delegation, **before any graph experiment of track 3**. It is a rule, not a
hypothesis. It says when the graph branch may answer a question, what the
branch must pass on its own account, by which stages it reaches users, and how
it is taken back. The mechanisms inside the branch — H1 coherence, H3 entity
ranking, H2 cross-references — are judged by the development ruler
([`semantic-precision-metrics.md`](semantic-precision-metrics.md)); no verdict
of that ruler replaces a condition of this file, and this file repeats none of
its rules.

Why it exists. The one measurement of the branch,
[GR-3](../evidence/gr3-graph-lane-ab.md), ended `NO_SHIP_TO_DEFAULT`. On the
15 multi-document cases — the questions the branch is meant for — recall fell
from 0.5000 to 0.4000 and keyword FULL from 4 to 1; with the entity lane the
retrieve p95 on phase C grew by 8 765.2 ms against a limit of 200 ms. On phase
C itself precision rose by 0.0408–0.0420 and FULL by 1–2, with two keyword
losses. Track 3 improves mechanisms of a branch that has no condition of use:
without one, a better mechanism has nowhere to go.

Nothing here is implemented by this registration. «State of the code» lists,
for every rule, what the code does today and the step before which the rule
must hold. The rule of [`graph-lane-ab.md`](graph-lane-ab.md) decided GR-3 and
stays as its record; decisions taken after this registration follow this file.

## Terms

| term | meaning |
|---|---|
| control | hybrid retrieval with production expansion, graph off, model routing off: the configuration of the slice 2.5 baseline |
| graph branch | `HybridRetriever.get_graph_documents_with_path`: vector and BM25 candidates, an entity lane as a third RRF list, reranking, section coherence, section expansion |
| structural lane | the branch without the entity lane; it is all that runs when the query carries no entities |
| entity lane | at most 50 chunks reached from the query's entities over at most two co-occurrence hops; it runs only for a routed class `multi_hop`, `aggregation` or `global`, on the entities the classifier returned |
| scope | which questions of a tenant the branch answers: `all` — every question, no classifier read; `routed` — the questions the classifier routes to it |
| stage | where a tenant stands: `off`, `shadow`, `tenant`, `default` |
| regression set | a tenant's labelled cases with keyword gold; for `aircargo`: H (100 cases) and the multi-document bucket Hm (15 cases) |
| route record | the `retrieval_route` trace record of a request (plan 2.1) |

## State of the code at registration (`36f1167`)

| rule of this file | what the code does today | must hold before |
|---|---|---|
| class and reason code select the branch together | `_select_retrieval_strategy` (`agent/graph.py`) reads `question_class` and `complexity`; `reason_code` is only traced; `complexity == "global"` selects the branch by itself | model routing is on in a measured arm or for a tenant |
| `simple` changes the generator only | a `simple` verdict selects the vector lane — no BM25, no reranker — skips document grading and fact verification and uses the fast generator | the same |
| scope `all` | absent: with model routing off the selector returns hybrid for every question, even with `RAG_RETRIEVAL_STRATEGY=graph` | the first graph experiment (3.1) |
| confidence | `confidence: None` in the route record | any rule reads it |
| the branch's own gate | the GR-3 rule decided the default of `RAG_GRAPH_RETRIEVAL` | the capsule of 3.1 |
| stages per tenant | one setting for all tenants; the projection is built only at `on` (`vectordb/manager.py`) | the stage `shadow` |
| shadow mode | absent | the loss map names a graph mechanism |
| `auto` retired | evaluated and logged at ingestion (`ingestion/graph_activation.py`); it never builds a projection | the stage implementation |
| entity graph status decides the lane | the status is recorded in the path; the structural projection answers under every status, and also when its own digest could not be computed | the stage `tenant` |
| a failing branch degrades to the control | an exception in the branch leaves an empty context; `fallback_reason: retriever_error`, the effective strategy still reads `graph` | the stage `tenant` |

## Requirement: with a classifier, the branch is selected by question class and reason code together

A scope is read only where the tenant's stage lets the branch serve (`tenant`,
`default`) or compute (`shadow`); at `off` the selector never chooses the
branch. Under scope `routed` the selector SHALL choose the graph branch only
for the three pairs marked `graph` below, and hybrid for everything else.

| `question_class` | `reason_code` | selected | `selected_reason` |
|---|---|---|---|
| `multi_hop` | `MULTI_SOURCE_CHAIN` | graph | `graph_eligible_class` |
| `aggregation` | `MULTI_SOURCE_AGGREGATION` | graph | `graph_eligible_class` |
| `global` | `CORPUS_GLOBAL` | graph | `graph_eligible_class` |
| one of the three classes above | any other code | hybrid | `class_reason_mismatch` |
| `single_hop` | any | hybrid | `graph_ineligible_class` |
| `unknown` | any — `ROUTING_DISABLED`, `NOT_CLASSIFIED`, `LEGACY_COMPLEXITY_ONLY`, `SCHEMA_FIELDS_INVALID` or a classifier code | hybrid | `graph_ineligible_class` |

`complexity` and `needs_multi_hop` SHALL NOT select the branch. Hybrid is the
safe side: a question kept in hybrid loses nothing against today, a question
sent to the branch by mistake meets the losses GR-3 measured. A verdict whose
class and reason code contradict each other is the only sign of doubt the
classifier gives without calibration, and it is read as doubt.

Under scope `all` the selector SHALL choose the branch for every question of
such a tenant, whatever the class, the reason code and the complexity, and the
route record SHALL say `selected_reason: graph_scope_all`. The scope is
configuration (`RAG_GRAPH_SCOPE`: `routed`, the default, or `all`), recorded in
the route record as `graph_scope`. `RAG_RETRIEVAL_STRATEGY=graph` keeps its
meaning — the branch is considered at all.

### Scenario: the classifier contradicts itself
- **GIVEN** scope `routed` and a verdict `multi_hop` with `SINGLE_SOURCE`
- **WHEN** the retrieve node selects a strategy
- **THEN** hybrid runs and the route record says `class_reason_mismatch`

### Scenario: complexity alone does not open the branch
- **GIVEN** scope `routed` and a verdict `single_hop` with complexity `global`
- **WHEN** the retrieve node selects a strategy
- **THEN** hybrid runs

### Scenario: scope `all` needs no classifier
- **GIVEN** model routing off, `RAG_RETRIEVAL_STRATEGY=graph`, scope `all`, a
  tenant whose stage lets the branch serve
- **WHEN** any question is asked
- **THEN** the graph branch runs, the route record says `graph_scope_all`, and
  the class in the record is `unknown`

## Requirement: `unknown` never opens the branch, and `simple` changes the generator only

Under scope `routed` a question of class `unknown` SHALL be served by hybrid.
With model routing off every question is `unknown`, so scope `routed` then
serves nothing by the branch; that is today's behaviour and it stays.

Until the routing audit of plan step 2.6 publishes how often `simple` is
right, a `simple` verdict SHALL NOT change which documents reach the
generator: the lane, the reranking and the document grading are those of a
question that is not `simple`. It may change the generator model. The
retrieval shortcut for `simple` — vector lane only, no grading — is a separate
hypothesis with a registration of its own, and the 2.6 audit is its input.
Whether fact verification runs after a `simple` answer is outside this file.

### Scenario: a simple verdict keeps the retrieval
- **GIVEN** model routing on and a verdict `simple`
- **WHEN** the request is served
- **THEN** the route record shows the lane a non-simple question would get,
  the reranker status is `ok`, the documents are graded, and only the
  generator model differs

## Requirement: classifier confidence stays absent until it is calibrated

The route record's `confidence` SHALL be `null` until a calibrated value
exists, and no rule of this file reads it before that. A value is calibrated
when all three hold:

1. its source is registered: the procedure that gives every routed verdict a
   number in [0, 1], with the digests of what produces it — model, prompt and
   schema, or a trained artifact. A number the classifier states about its own
   answer may be such a source; without the next two items it is not
   confidence and is not written into the record;
2. its reliability is published on labelled questions that were not used to
   build the procedure and do not share a document family with those that
   were: accuracy per confidence bin with intervals, in the capsule of the
   routing audit (2.6);
3. a revision of this file registers, before the first run that reads the
   value, the threshold and the precision of graph-eligible verdicts the
   threshold has to deliver, with the labelled set the two were chosen on.

From then on a verdict below the threshold SHALL be read as `unknown` — hybrid
— with `selected_reason: low_confidence`.

### Scenario: an uncalibrated number is not recorded
- **GIVEN** a classifier that returns a self-reported certainty and no
  published reliability
- **WHEN** a request is routed
- **THEN** the route record carries `confidence: null`

## Requirement: the first campaign runs a static policy

In the first campaign of track 3:

- model routing SHALL be off and `confidence` `null`. Trainable routing and
  the research item R4 are outside the campaign (plan G9, D8);
- the experiment arm SHALL be the branch under scope `all`, switched on by
  explicit configuration and run through the production retrieve node. A
  labelled class or a gold class SHALL NOT decide whether the branch runs:
  labels only group the reported numbers;
- with routing off the classifier returns no entities, so the entity lane does
  not run: the arm is the structural lane. A mechanism that needs the entity
  lane (H3) SHALL register, before its run, how the query entities are
  produced; scope `routed` and the rules above then apply to it;
- the branch SHALL be considered only for the case group the baseline loss map
  of slice 2.5 establishes, named in that slice's capsule before the first
  graph run: the cases whose gold lies in at least two source documents and
  for which, on the control, at least one of those documents has all its gold
  absent from the documents of the retrieve stage — a first loss before
  `grading` in the map's order — while at least one other is represented
  there. A document the grader alone removed is the grader's loss and puts no
  case into the group: the branch replaces retrieval, not grading. Cases that
  lose every gold document are listed beside the group and are not in it:
  nothing shows that a second source, and not the first, is what the control
  fails to find. On an external base the group is read the same way over
  evidence groups — two or more sections of a document, or two or more
  documents, with at least one and not all of them unsatisfied by the control.
  The literature does not replace the map (plan G11);
- if the map names no graph mechanism, no graph experiment SHALL run in the
  first campaign, shadow mode is not built, and every tenant stays at `off`.

An experiment arm is a measured run of the collector, not a deployment: its
process sets the stage and the scope for that run alone, and nothing it sets
reaches a serving tenant.

### Scenario: the gold class is not a switch
- **GIVEN** a case labelled `multi_hop` and model routing off
- **WHEN** the control arm and the experiment arm are run
- **THEN** the control serves it by hybrid and the experiment arm by the
  branch under scope `all`; in both the routed class is `unknown`

## Requirement: the branch has a gate of its own

The branch SHALL be enabled for no tenant beyond `shadow` unless its gate
holds. The gate is read on one registered comparison: the branch in the
configuration proposed for enablement — scope, mechanism, candidate budget —
against the control, on the same corpus snapshot, cases and budgets, both
through the production retrieve node. On the tenant's regression set all three
SHALL hold:

1. **multi-document recall is not lower.** On the multi-document cases (for
   `aircargo`: Hm) the keyword recall of the branch is not below the
   control's. Keyword recall of a case is the share of its gold found in the
   documents the retrieve stage hands on, matched as the evidence-loss map
   matches it — for Hm a gold term counts only in its own document;
2. **no FULL is lost.** No case of the regression set (for `aircargo`: H and
   Hm) that holds all its gold under the control holds less under the branch.
   The ids of every such case are published;
3. **retrieve p95 grows by at most 200 ms at a candidate budget of 40**, by
   the ruler's protocol: warm-up requests excluded, arms interleaved, at least
   3 repeats per case, a bootstrap interval over cases, 200 ms compared with
   the upper bound of the 95 % interval of the delta, absolute p50 and p95
   published, the host named.

Conditions 1 and 2 are read on the documents of the retrieve stage — the
branch's own output — because the document grader that follows is one model
shared by both arms, with a run-to-run variance of its own (plan 1.3c). The
same counts on the graded documents are printed beside them; what they decide
is the ruler's matter. A candidate budget of 40 means that the pool the
reranker receives, after fusion and deduplication, holds at most 40 candidates
in both arms: the control merges 20 vector and 20 BM25 candidates, and the
entity lane, when it runs, adds up to 50 more unless the pool is cut (plan
3.2).

The gate is necessary, not sufficient: the mechanism's verdict under the ruler
is required beside it. A gate result belongs to its tenant, corpus snapshot,
graph version, scope, configuration, code and host, and is quoted with them.

### Scenario: precision does not buy back a lost FULL
- **GIVEN** a branch arm whose precision is higher than the control's and one
  H case that goes from FULL to PART
- **WHEN** the gate is read
- **THEN** it does not hold, and the case id is in the report

### Scenario: a latency delta is not read as a point
- **GIVEN** a p95 delta of 150 ms whose 95 % interval reaches 260 ms
- **WHEN** condition 3 is read
- **THEN** it does not hold

## Requirement: the branch reaches users by stages, each with its criteria

A tenant's stage is configuration: `RAG_GRAPH_RETRIEVAL` (`off`, `shadow` or
`on`) is the stage of every tenant without an entry of its own, and a
per-tenant entry (`RAG_GRAPH_TENANT_STAGES`) overrides it. `on` in a tenant's
entry is the stage `tenant`; `on` as the common value is the stage `default`.
The route record SHALL carry the stage as `graph_stage`. A stage is changed by
the owner or on her delegation; this file says when a change is permitted, and
no verdict makes one by itself.

| transition | permitted when all of these hold |
|---|---|
| `off` → `shadow` | a registered campaign names a graph mechanism (in the first one: the capsule of slice 2.5); the graph lifecycle of plan 2.3 covers the tenant (version stamp in the trace; add, update and delete of a document); shadow mode passes its E2E tests on the build; the tenant's projection is built and its digest computed. No quality evidence is asked: shadow changes no answer |
| `shadow` → `tenant` | the gate holds for this tenant, scope and configuration; the configuration is the one acceptance 4.1 returned `SHIP_RESEARCH` for; shadow evidence of this tenant: at least 300 shadowed requests at one code and graph version, shadow failures and fallbacks on at most 1 % of them, each with a named reason, and on the deployment host the branch's retrieve p95 above the serving branch's by at most 200 ms at the upper bound of the 95 % interval; with the entity lane in the configuration, `entity_graph_status` was `matched` on every shadowed request; the rollback of this tenant passes its E2E test |
| `tenant` → `default` | product acceptance 4.2 on the named deployment target with its absolute SLO; the gate held on at least two corpora of different origin — ours and an external base on which the graph was built (plan 1.5) — with no convincing contradiction on a second base (plan D7 as revised 2026-10-05); a base without a graph is `not_applicable` and is not one of the two; no rollback of a tenant is unresolved |

The counts 300 and 1 % are operating values chosen here, not measured
properties: 300 requests leave 15 above the 95th percentile.

Rollback. One configuration change SHALL take a tenant back — to `shadow` or
to `off` — without re-ingestion, and the next request of that tenant SHALL be
served by the control. A tenant SHALL be taken back when any of these holds:

- the gate, run again, does not hold. It SHALL be run again before the tenant
  goes on at `tenant` or `default` after a change of the chunking parameters,
  of the embedder or the reranker, of the branch's own parameters (candidate
  budget, coherence rule, expansion budget), or of the model or prompt that
  extracts the entity graph;
- fallbacks to the control exceed 1 % of the tenant's last 300 requests in the
  branch's scope;
- on the deployment host the branch's retrieve p95 breaks the tenant's SLO;
- one critical error, in the ruler's sense, is traced to the branch;
- the owner says so.

A tenant taken back returns only by the criteria of the table, with evidence
at the new versions.

### Scenario: a rollback needs no ingestion
- **GIVEN** a tenant at `tenant` whose stage is set to `off`
- **WHEN** the next question of that tenant is asked after the restart
- **THEN** the route record shows `graph_stage: off` and hybrid, no projection
  is built for the tenant, and its index is untouched

## Requirement: in shadow the branch computes and the answer does not change

For a tenant at `shadow` the answer SHALL be what it is at `off`: the same
documents in the same order, the same response body. For a sampled share of
the tenant's requests in its scope — the share is part of the tenant's entry,
with no implied value; under scope `routed` only the questions the rule table
sends to the branch are in scope — the graph branch SHALL be computed for the
same effective query away from the answer path:

- the answer does not wait for the shadow, and a shadow that fails, is slow or
  is skipped changes nothing in the response;
- shadow documents never enter the context, a cache of the serving path, or
  the reranking of the serving branch;
- the shadow reads the tenant's own store and graph only;
- a `retrieval_shadow` trace record is written with: the stage, the scope, the
  shadow status (`ok`, `failed`, `deadline`, `skipped_sampling`,
  `skipped_unhealthy`), for both branches the ordered identities of their
  documents (source, chunk index, text SHA-256 — no text), the documents only
  one branch has, the counts of documents and characters, the branch's path
  (lane kinds, candidates per source, coherence drops, stage timings,
  `graph_version`, `entity_graph_status`) and the shadow's duration.

### Scenario: shadow leaves the answer alone
- **GIVEN** deterministic models and one tenant asked the same question at
  `off` and at `shadow`
- **WHEN** both responses are compared
- **THEN** they are identical, and only the `shadow` request has a
  `retrieval_shadow` record, which names the documents the branches disagree on

### Scenario: a broken shadow is invisible to the user
- **GIVEN** a tenant at `shadow` whose graph branch raises
- **WHEN** a question is asked
- **THEN** the response equals the one at `off` and the record says `failed`

### Scenario: another tenant's graph is not read
- **GIVEN** two tenants, one at `shadow`
- **WHEN** the other one asks a question
- **THEN** no `retrieval_shadow` record is written for it, and the first
  tenant's record holds no document of the second

## Requirement: `auto` no longer enables anything

`auto` SHALL NOT enable the branch, and its two thresholds — 20 000 chunks and
a cross-document entity share of 0.15 — are retired as a condition of
activation:

- no measurement links either number to a gain from the branch, and the one
  measurement of the branch is negative on the multi-document bucket;
- the chunk threshold is tied to one chunk size and is out of reach of the
  corpus the product is measured on (5 589 chunks at GR-3); the share is a
  number someone has to measure and put into `RAG_GRAPH_CROSSDOC_SHARE`;
- `auto` enables nothing today: the decision is logged at ingestion and the
  retriever builds a projection only at `on`.

Evidence per tenant — the stages above — stands in the place of thresholds on
the corpus. The value `auto` SHALL stay accepted, resolve to `off` and log one
line that names this file; `DEPRECATIONS.md` gets its row with the stage
implementation. Chunk count and cross-document share may be printed at
ingestion as a description of the corpus; no rule reads them.

### Scenario: a large connected corpus under `auto`
- **GIVEN** `RAG_GRAPH_RETRIEVAL=auto`, 50 000 chunks and a share of 0.4
- **WHEN** a question is asked
- **THEN** the route record shows `graph_stage: off` and hybrid

## Requirement: an entity graph that is not `matched` takes the entity lane out, visibly

`entity_graph_status` is one of `matched`, `no_database`, `unavailable`,
`absent`, `mismatch`, `invalid`. The structural lane does not need the entity
graph; the entity lane does.

- When the status is not `matched`, the entity lane SHALL NOT run, and the
  request SHALL be served by the configuration that holds enablement evidence
  for the tenant: the structural lane if the gate held for it, the control
  otherwise. The route record SHALL say `fallback_reason:
  entity_graph_not_matched` and carry the status. The fallback is never
  silent, and never to a configuration nobody measured.
- A graph whose digest cannot be computed cannot be named: `graph_version` is
  null, and today the code reports this case as `invalid` too. Such a request
  SHALL be served by the control, with `fallback_reason: graph_unidentified`.
- A measured run whose registered mechanism uses the entity lane is
  `NOT_EVIDENCE` for that mechanism if any of its requests ran under a status
  other than `matched`. Arms that ran under different statuses or graph
  versions are not compared.
- In shadow the status is recorded and the structural lane goes on.

### Scenario: the entity graph went stale
- **GIVEN** a tenant at `tenant` with the entity lane, enabled on the evidence
  of an arm that used it, and a corpus update that leaves the status `mismatch`
- **WHEN** a multi-hop question is asked
- **THEN** it is served by the structural lane if the gate held for that lane
  on this tenant and by the control if not, and the route record names the
  status and the fallback

## Requirement: a failing branch degrades to the control

An error inside the graph branch, a missing projection or a retriever without
the branch SHALL end in the control's result for that request — one attempt —
with `effective: hybrid` and a bounded `fallback_reason` in the route record.
An empty context because the branch failed is not an accepted outcome. The
request deadline stays what it is: a request out of time is not retried.

### Scenario: the branch raises
- **GIVEN** a tenant at `tenant` whose graph branch raises on one request
- **WHEN** that request is served
- **THEN** the hybrid documents are handed on and the route record says
  `effective: hybrid`, `fallback_reason: retriever_error`

## What does not depend on the corpus, and what does

The selection rule, the stages, shadow, rollback and the form of the gate are
the same for any corpus. The gate's evidence is per tenant by construction: a
tenant without a regression set cannot pass `shadow` before the stage
`default` exists, and at `default` it is protected by the fallbacks and the
rollback triggers alone — the capsule of that transition has to say so.

Three parts of the branch as it stands are not corpus-independent, and no gate
result on one corpus covers them on another:

- the entity extraction prompt is written in Russian for a fragment of a
  corporate regulation and names cargo and operation types among the kinds of
  entity. On a corpus in another language or of another kind the entity graph
  has no evidence at all; the graph timing of plan 1.5 on 100 documents of
  ConditionalQA is its first run on an English corpus;
- section coherence and section expansion read the heading structure of the
  documents. What they do on a corpus without headings has not been measured;
- the category prefilter is inactive: nothing produces the categories of a
  query.

## What this file does not decide

- Which mechanism the campaign takes — the loss map and the capsule of 2.5.
- Whether a mechanism ships — the ruler and acceptance 4.1.
- The deployment target and its SLO — plan 4.2, the owner names them.
- The retrieval shortcut for `simple` and trainable routing — registrations of
  their own.
- The syntax of the per-tenant entry — the slice that implements the stages
  fixes it and documents it; the meanings above do not change with it.

A change to this file after the first graph experiment is a new registration
with its date and reason below, not an edit.

## Revision record

- 2026-10-05 — first registration. Decisions taken here that the plan left
  open: `auto` is retired and not redefined per tenant; the branch is
  forced in an experiment arm by an explicit scope `all`, a setting of the
  product, and not by a harness-only switch; conditions 1 and 2 of the gate
  are read at the retrieve stage; the shadow window is 300 requests with at
  most 1 % failures; an unidentifiable graph is served by the control. The
  owner may reverse any of them before the first experiment of track 3.

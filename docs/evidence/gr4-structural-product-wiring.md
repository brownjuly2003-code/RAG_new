# GR-4: structural retrieval through ask and Evidence

2026-09-12 · evidence class: `synthetic` · plan §GR-4, structural part.

The production tenant retriever now builds a structural projection from its
restored chunks when `RAG_GRAPH_RETRIEVAL=on`. With
`RAG_RETRIEVAL_STRATEGY=graph` and `MODEL_ROUTING_ENABLED=true`, a question
classified as `global` reaches that projection through the real `/api/ask`
session and graph. Simple questions retain vector routing; other classes
retain hybrid routing. `off` and `auto` do not construct the projection.
Restart the process after changing flags because tenant retrievers are cached.
An explicit projection takes precedence over the parent-child retriever.

Each retrieval returns its documents and path together. No request path is
stored on the shared retriever. The retrieve trace records the effective
strategy, structural section IDs, category-prefilter status, retained and
expanded context counts, and explicitly empty entities / zero entity hops.
A missing projection reports hybrid fallback and carries no structural path.
The default hybrid state keeps its previous shape.

Evidence adds the paths alongside existing resolution journeys. A graph-only
trace can export evidence JSON. Legacy traces retain their previous Evidence
JSON shape. Section text is rendered as text, including HTML-looking input.

## Fresh verification

On Mac, in the isolated `/Users/julia/RAG_new_gr4_20260912` checkout:

```text
python -m pytest tests/integration/test_graph_lane_e2e.py tests/test_graph_retrieval_path.py tests/test_graph_retriever.py tests/test_parent_expansion.py tests/test_sgr_classifier.py tests/test_graph_helpers.py tests/test_provider_graph_integration.py tests/test_graph_node_sse.py tests/test_retriever_tool_deadline.py tests/test_evidence_view.py tests/test_admin_trace_evidence.py tests/test_gr1b_stage_replay.py -q -p no:schemathesis --tb=short --show-capture=no
100 passed (16.87 s), exit 0
```

The HTTP test runs the real ConversationSession, compiled graph, retrieval,
SQLite trace lifecycle and admin Evidence endpoint. It asserts the completed
answer and recorded path for `on`, and hybrid/no-path for `off` and `auto`.
Model output, vector search and Postgres side effects are fixtures; it does
not prove live-model quality or durable Postgres session persistence.
The GR-1b replay regression remains green without rerunning embeddings.

Both CI strict mypy commands passed on Mac: 131 main modules and 31 API /
vectordb modules. The full Linux lock cannot install on Intel macOS because
it includes `cuda-bindings==13.2.0`. The isolated test venv uses Mac-compatible
dependencies plus existing benchmark libraries; this is not a full CI run.

On Windows, the focused backend regression set passed 60 tests. Ruff and
`git diff --check` passed. Browser verification is independently runnable:

```text
python -m pytest scripts/qa/test_graph_evidence_ui.py -q -p no:schemathesis
```

It runs real Chromium against the checked-in admin page and script with
fixture HTTP responses: visible path without a resolution journey, safe
HTML-looking section text, exact downloaded JSON, and clearing the path when
switching to a legacy trace. It requires installed Python Playwright and
Chromium; it is an explicit browser gate outside the unit-test collection.
The test first failed on the missing path heading, then passed after UI wiring.
Retriever trace and factory tests likewise followed red-green implementation.

## Boundary and next work

The structural part of GR-4 satisfies rule (a). Entity traversal remains
GR-2 work; automatic activation remains gated by GR-3. This changes no
benchmark number, default model or quality threshold. GR-1b remains NO-SHIP.
Nothing was pushed or deployed. Continue with GR-2, reusing existing embeddings.

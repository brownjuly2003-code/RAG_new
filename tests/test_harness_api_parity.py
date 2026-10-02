"""Production harness parity; fake models do not measure retrieval quality.

The shared exact-cosine store tests pipeline logic. Chroma ANN versus exact
cosine with real models on 30 H cases is a separate Mac acceptance check.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import ab_remote_contextual as remote

ROOT = Path(__file__).resolve().parents[1]
CHUNKS_SHA256 = "2a9da515a4c69b46453a59ed6d0bb772b0aad6fed23c87ee465851b43dbdef12"


def _cases():
    cases = []
    for stem, count in (
        ("curated_cases_aircargo", 100),
        ("curated_cases_aircargo_gr_multihop", 15),
    ):
        path = ROOT / "evaluation" / (stem + ".jsonl")
        manifest = json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf-8"))
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["dataset_sha256"]
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        assert len(rows) == count
        cases.extend(rows)
    return cases


CASES = _cases()


@pytest.fixture(scope="module")
def parity_retriever():
    from ingestion.structure_graph import build_structural_graph
    from ingestion.structure_graph_projection import project_structure_graph
    from tests.test_ab_remote_contextual_entity_arm import FakeStore
    from tests.test_rerank_score_capture import FakeReranker
    from vectordb._base_manager import Document, HybridRetriever

    archive = ROOT / "evaluation/gr1b-4436d61-graph-chunks.json.gz"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == CHUNKS_SHA256
    payload = json.loads(gzip.decompress(archive.read_bytes()))
    chunks = [Document(**item) for item in payload["chunks"]]
    projection = project_structure_graph(build_structural_graph(chunks, tenant_id="aircargo"))
    scores = {
        doc.page_content: int(hashlib.sha256(doc.page_content.encode()).hexdigest()[:8], 16) / 2**32
        for doc in chunks
    }
    retriever = HybridRetriever(
        FakeStore(chunks),
        chunks,
        reranker=FakeReranker(scores),
        retrieval_k=20,
        rerank_k=5,
        rerank_batch=8,
        parent_expansion=True,
        parent_expansion_window=2,
        parent_expansion_max_chars=2400,
        graph_projection=projection,
    )
    assert retriever._bm25 is not None
    return retriever


def _identities(docs):
    return [(doc.metadata.get("source"), doc.metadata.get("chunk_index")) for doc in docs]


def _same(case_id, level, actual, expected):
    for position in range(max(len(actual), len(expected))):
        left = actual[position] if position < len(actual) else "<missing>"
        right = expected[position] if position < len(expected) else "<missing>"
        assert left == right, (
            f"{case_id}: level {level}, first differing position {position}: {left!r} != {right!r}"
        )


@pytest.mark.parametrize("lane", ["hybrid", "graph"])
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["case_id"])
def test_parity_all_cases(case, lane, parity_retriever, monkeypatch):
    import config.settings
    from agent import graph
    from agent.state import create_initial_state
    from config.settings import Settings
    from tests.test_ask_contract_route import _GRAPH_CLASSIFICATION, _fixture_model

    settings = Settings()
    settings.retrieval_strategy = lane
    settings.model_routing_enabled = lane == "graph"
    settings.fact_verification_enabled = False
    settings.agentic_mode = False
    settings.online_evaluators_enabled = False
    settings.ask_budget_sec = 0
    mode = CASES.index(case) % 3
    settings.hyde = mode == 2
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "get_settings", lambda: settings)
    retriever = parity_retriever
    probe = {}
    original_rank = retriever._rerank_scored_with_status
    original_hybrid = retriever.get_relevant_documents_with_path
    original_graph = retriever.get_graph_documents_with_path
    original_prompt = graph.build_qa_prompt

    def ranked(query, docs):
        probe["pool"] = _identities(docs)
        result = original_rank(query, docs)
        probe["ranked"] = _identities([doc for doc, _ in result[0]])
        return result

    def observed(method):
        def retrieve(*args, **kwargs):
            result = method(*args, **kwargs)
            probe["docs"], probe["path"] = result
            return result

        return retrieve

    def prompt(**kwargs):
        probe["sent"] = "\n\n".join(doc["page_content"] for doc in kwargs["context_docs"])
        return original_prompt(**kwargs)

    def record(trace_id, node, state):
        if node == "retrieval_route":
            probe["route"] = state

    monkeypatch.setattr(retriever, "_rerank_scored_with_status", ranked)
    monkeypatch.setattr(retriever, "get_relevant_documents_with_path", observed(original_hybrid))
    monkeypatch.setattr(retriever, "get_graph_documents_with_path", observed(original_graph))
    monkeypatch.setattr(graph, "build_qa_prompt", prompt)
    monkeypatch.setattr(graph, "log_step", record)

    def model():
        def answers():
            yield case["query"] if mode == 0 else "rewritten " + case["query"]
            if settings.hyde:
                yield "Hypothetical passage: " + case["query"]
            n = len(probe["docs"])
            if n > 1:
                yield json.dumps(
                    {"grades": [{"index": i, "relevant": i != n} for i in range(1, n + 1)]}
                )
            else:
                yield "YES"
            yield "Fixture answer [1]."
            yield '{"score": 90, "reason": "fixture"}'
            yield "[]"

        return _fixture_model(answers(), _GRAPH_CLASSIFICATION if lane == "graph" else None)

    llm = model()
    state = create_initial_state(question=case["query"], tenant_id="aircargo")
    for node in (
        graph.make_classify_complexity_node(llm),
        graph.make_transform_query_node(llm),
        graph.make_retrieve_node(retriever),
        graph.make_grade_docs_node(llm),
        graph.make_generate_node(llm, llm),
    ):
        state = node(state)
    assert not state.get("error"), state.get("error")
    expected = dict(probe)
    assert expected["path"]["rerank_batch_effective"] == 8
    assert expected["route"]["effective"] == lane
    probe.clear()
    session = graph.ConversationSession(retriever, model(), max_iterations=0)
    result = remote.production_case(case, session, tenant_id="aircargo")
    assert not result["state"].get("error"), result["state"].get("error")
    for name in ("pool", "ranked"):
        _same(case["case_id"], "1/" + name, probe[name], expected[name])
    _same(case["case_id"], "2/text", probe["sent"], expected["sent"])
    assert result["sent_context_sha256"] == hashlib.sha256(expected["sent"].encode()).hexdigest(), (
        f"{case['case_id']}: level 2/hash"
    )
    for name in ("query_effective", "query_transform", "query_transform_hash"):
        _same(case["case_id"], "3/" + name, [result[name]], [expected["route"][name]])
    assert probe["path"]["rerank_batch_effective"] == 8
    assert result["state"]["generation_context_tokens"] == state["generation_context_tokens"]


def test_parity_production_case_preserves_rejected_context():
    state = {
        "question": "original question",
        "search_query": "rewritten question",
        "context_docs": [{"page_content": "rejected text", "metadata": {}}],
        "graded_docs": [],
        "doc_grade_reason": "all_docs_rejected",
        "answer": "No evidence",
    }
    session = SimpleNamespace(ask=lambda question, **kwargs: state)
    result = remote.production_case({"case_id": "rejected", "query": state["question"]}, session)
    assert result["cands"] == []
    assert result["query_effective"] == "rewritten question"
    assert result["query_transform"] == "rewrite"
    assert result["state"] is state


def test_parity_legacy_rerank_requires_explicit_switch(tmp_path):
    with pytest.raises(SystemExit, match="2"):
        remote.main(["--stage", "rerank", "--arm", "C", "--out-dir", str(tmp_path)])


@pytest.mark.parametrize(
    "contract",
    [
        "sources_and_citations",
        "orphan_citation_ignored",
        "numeric_fields",
        "verified_single_doc_answer_still_routes_to_human",
        "low_score_routes_to_human",
        "empty_retrieval",
        "route_record_defaults",
        "hybrid_lane_path_reaches_evidence",
        "with_a_float_rerank_score_keeps_the_trace_readable",
        "configured_graph_with_unknown_class_stays_hybrid",
        "simple_complexity_selects_vector_lane",
        "graph_retriever_error_falls_back_with_reason",
        "graph_projection_missing_falls_back_to_hybrid",
        "retriever_without_graph_lane_reports_reason",
        "legacy_graph_lane_without_path",
        "evidence_is_tenant_scoped",
        "stream_final_event_matches_synchronous_contract",
    ],
)
def test_parity_http_contracts_through_harness(contract, monkeypatch, client, tmp_path):
    from tests import test_ask_contract_route as contracts

    original = contracts._pipeline
    calls = []

    def pipeline(*args, **kwargs):
        session, settings = original(*args, **kwargs)
        entry = SimpleNamespace(ask=session.ask)
        if contract == "stream_final_event_matches_synchronous_contract":
            from agent.graph import ConversationSession

            companion = ConversationSession(
                session._retriever,
                contracts._fixture_model(kwargs["answers"], kwargs.get("classification")),
                max_iterations=0,
            )
            result = remote.production_case(
                {"case_id": contract, "query": "Summarize the policy"}, companion
            )
            assert result["state"]["answer"] == "Seed policy [1]."
            assert result["state"]["citations"] == [contracts._CITATION]
            calls.append(result)

        def ask(question, **ask_kwargs):
            result = remote.production_case(
                {"case_id": contract, "query": question}, entry, **ask_kwargs
            )
            calls.append(result)
            return result["state"]

        monkeypatch.setattr(session, "ask", ask)
        return session, settings

    monkeypatch.setattr(contracts, "_pipeline", pipeline)
    test = getattr(contracts, "test_ask_" + contract, None)
    if test is None:
        test = getattr(contracts, "test_ask_contract_" + contract)
    test(monkeypatch, client, tmp_path)
    assert calls, "the HTTP contract must traverse the production harness"


def test_parity_cli_defaults_to_production(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        remote, "stage_production", lambda cases, out: calls.append((cases, out)) or 0
    )
    assert remote.main(["--cases", "cases.jsonl", "--out-dir", str(tmp_path)]) == 0
    assert calls == [(Path("cases.jsonl"), tmp_path)]


def test_parity_production_stage_uses_fresh_sessions(monkeypatch, tmp_path):
    from agent import graph
    from config.settings import get_settings
    from vectordb import manager

    monkeypatch.setattr(get_settings(), "self_rag_max_iterations", 3)
    cases = tmp_path / "cases.jsonl"
    cases.write_text(
        "\n".join(
            json.dumps({"case_id": str(i), "query": "question", "tenant_id": "tenant"})
            for i in range(2)
        ),
        encoding="utf-8",
    )
    sessions = []
    retrievers = []

    class Session:
        def __init__(self, retriever, max_iterations):
            assert max_iterations == 3
            self.calls = 0
            sessions.append(self)

        def ask(self, question, **kwargs):
            self.calls += 1
            assert kwargs == {"tenant_id": "tenant"}
            return {"question": question, "context_docs": [], "graded_docs": []}

    monkeypatch.setattr(graph, "ConversationSession", Session)
    monkeypatch.setattr(manager, "get_retriever", lambda **kwargs: retrievers.append(kwargs))
    output = tmp_path / "output"
    assert remote.stage_production(cases, output) == 0
    assert len(sessions) == 2 and all(session.calls == 1 for session in sessions)
    assert retrievers == [{"tenant_id": "tenant"}] * 2
    result_path = output / "production_contexts.json"
    assert [row["case_id"] for row in json.loads(result_path.read_text(encoding="utf-8"))] == [
        "0",
        "1",
    ]
    before = result_path.read_bytes()
    assert remote.stage_production(cases, output) == 2
    assert result_path.read_bytes() == before
    assert len(sessions) == 2


def test_parity_archive_pool_explicitly_selects_legacy(monkeypatch, tmp_path):
    from scripts import ab_context_precision

    calls = []
    artifact = tmp_path / "ab_candidates_phase2_C.json"
    artifact.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(
        ab_context_precision.subprocess,
        "run",
        lambda cmd, **kwargs: calls.append(cmd) or SimpleNamespace(returncode=0),
    )
    assert ab_context_precision.build_pool(tmp_path) == artifact
    assert len(calls) == 2
    assert all("--legacy-harness" in cmd for cmd in calls)

"""Prove the restart contract in docs/specs/chroma-index-persistence.md.

The test uses real Chroma and langchain-chroma; only the embedding and language
models are deterministic stand-ins. The ingesting process builds and publishes
600 records through production ingestion. The vector segment must be persisted
through the log's highest sequence id.

A second Python process runs test_restarted_process_child with pytest and reopens
the published collection through manager.get_retriever, which reads the BM25 corpus
back from it in pages of 64 records. Its get_relevant_documents
lists for 100 queries cover the whole RRF-fused pool that production's reranker
receives. Those lists, the /api/ask answer, sources, and retrieved context must
equal the ingesting process's. The child test skips unless the parent starts it.

The control drops collection_configuration from the build call and must find
records above the persisted sequence id. The test named
test_candidate_pool_sees_a_change_beyond_the_rerank_depth shows the whole-pool
comparison detects a change hidden by production's rerank depth.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("chromadb")
pytest.importorskip("langchain_chroma")

import numpy as np
from langchain_core.documents import Document

from agent import graph
from config.settings import Settings
from scripts.pgvector_cold_start import read_log_positions
from vectordb import manager

_CHILD_FLAG = "RAG_T51_RESTART_CHILD"
_CHROMA_DIR = "RAG_T51_CHROMA_DIR"
_OUTPUT_PATH = "RAG_T51_OUTPUT_PATH"
_RECORD = re.compile(r"\brecord (\d{4})\b")
_QUESTION = re.compile(r"\bquestion (\d{4})\b")


class FakeEmbeddings:
    def __init__(self) -> None:
        self._records = np.random.default_rng(7).standard_normal((600, 64))
        self._questions = np.random.default_rng(11).standard_normal((100, 64))

    def _vector(self, text: str) -> list[float]:
        record = _RECORD.search(text)
        if record is not None:
            return self._records[int(record.group(1))].tolist()
        question = _QUESTION.search(text)
        if question is not None:
            return self._questions[int(question.group(1))].tolist()
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        return np.random.default_rng(seed).standard_normal(64).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class FixtureModel:
    supports_structured_output = False
    generate_with_schema = None

    def __init__(self) -> None:
        self.answers = iter(
            [
                "GLOBAL",
                "question 0007",
                '{"grades":[{"index":1,"relevant":true},{"index":2,"relevant":true},'
                '{"index":3,"relevant":true},{"index":4,"relevant":true},'
                '{"index":5,"relevant":true}]}',
                "Cargo item answer [1].",
                '{"score": 90, "reason": "Fixture answer"}',
                "[]",
            ]
        )

    def invoke(self, prompt: str) -> str:
        return next(self.answers, "[]")


def _configure(monkeypatch, tmp_path: Path, chroma_directory: Path) -> Settings:
    import config.settings

    monkeypatch.setenv("ANONYMIZED_TELEMETRY", "False")
    settings = Settings()
    settings.vectordb_chroma_dir = chroma_directory
    settings.tracing_db_path = tmp_path / "traces.db"
    settings.vector_backend = "chroma"
    settings.graph_retrieval = "off"
    settings.reranker_model = ""
    settings.model_routing_enabled = True
    settings.fact_verification_enabled = False
    settings.hyde = False
    settings.agentic_mode = False
    settings.online_evaluators_enabled = False
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "get_settings", lambda: settings)
    monkeypatch.setattr(manager, "get_settings", lambda: settings)
    fake = FakeEmbeddings()
    monkeypatch.setattr(manager, "get_embeddings", lambda *args, **kwargs: fake)
    from tracing import _base_trace

    _base_trace._init_db()
    for name in ("_retriever_cache", "_chunks_cache", "_store_cache", "_index_cache_keys"):
        monkeypatch.setattr(manager, name, {})
    return settings


def _docs() -> list[Document]:
    return [
        Document(
            page_content=f"record {i:04d} covers cargo item {i}",
            metadata={"source": f"r{i}.md"},
        )
        for i in range(600)
    ]


def _candidate_pool(monkeypatch, retriever, settings, queries):
    vectors = []
    candidates = []
    with monkeypatch.context() as scoped:
        # The reranker is off here; lifted depth exposes its whole RRF-fused input,
        # as scripts/chroma_restart_stability.py does with rerank_k=1000000.
        scoped.setattr(retriever, "_rerank_k", 1_000_000)
        for query in queries:
            vector = [doc.metadata["chunk_index"] for doc in retriever.get_vector_documents(query)]
            assert len(vector) == settings.retrieval_top_k
            assert all(type(value) is int for value in vector)
            assert len(set(vector)) == len(vector)
            candidate = [
                doc.metadata["chunk_index"] for doc in retriever.get_relevant_documents(query)
            ]
            assert candidate
            assert all(type(value) is int for value in candidate)
            assert len(set(candidate)) == len(candidate)
            assert set(vector).issubset(candidate)
            vectors.append(vector)
            candidates.append(candidate)
    assert retriever._rerank_k == settings.rerank_top_k
    return vectors, candidates


def _record_answers(monkeypatch, client, settings: Settings) -> dict:
    import api.app as api_app
    from api.routers import conversation
    from tracing.sqlite_trace import get_trace_detail

    fake = manager.get_embeddings()
    retriever = manager.get_retriever(tenant_id="default", embeddings=fake)
    queries = [f"question {q:04d}" for q in range(100)]
    vectors, candidates = _candidate_pool(monkeypatch, retriever, settings, queries)

    session = graph.ConversationSession(retriever, FixtureModel(), max_iterations=0)

    async def session_factory(*args, **kwargs):
        return "11111111-2222-4333-8444-555555555555", session

    async def no_postgres(**kwargs):
        return None

    monkeypatch.setattr(api_app, "_get_or_create_session", session_factory)
    monkeypatch.setattr(api_app, "log_audit", no_postgres)
    monkeypatch.setattr(conversation, "_persist_ask_messages", no_postgres)
    monkeypatch.setattr("services.escalation.create_escalation", no_postgres)
    response = client.post("/api/ask", json={"question": "question 0007"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["route"] != "error", body
    assert body["answer"] == "Cargo item answer [1].", body
    assert body["sources"], body
    trace = get_trace_detail(body["trace_id"], tenant_id="default")
    assert trace is not None
    retrieved = [step["state"] for step in trace["steps"] if step["node"] == "retrieve"]
    assert len(retrieved) == 1, trace
    context_chunks = [doc["metadata"]["chunk_index"] for doc in retrieved[0]["context_docs"]]
    assert context_chunks
    # Source identity uses source and page_content; trace identity uses chunk_index.
    return {
        "vectors": vectors,
        "candidates": candidates,
        "ask": {
            "answer": body["answer"],
            "sources": [
                {"source": item["source"], "page_content": item["page_content"]}
                for item in body["sources"]
            ],
            "trace_context_chunks": context_chunks,
        },
    }


def test_restarted_process_answers_as_the_ingesting_process(monkeypatch, client, tmp_path):
    chroma_directory = tmp_path / "chroma"
    settings = _configure(monkeypatch, tmp_path, chroma_directory)
    fake = manager.get_embeddings()
    result = manager.build_vector_store_with_publication(
        _docs(),
        {"chunk_size": settings.chunk_size, "chunk_overlap": settings.chunk_overlap},
        embeddings=fake,
        tenant_id="default",
    )
    assert len(result.chunks) == 600
    assert result.publication is not None
    positions = read_log_positions(chroma_directory)
    assert positions["chroma_log_max_seq_id"] >= 600
    assert positions["chroma_vector_persisted_seq_id"] == positions["chroma_log_max_seq_id"]
    record = _record_answers(monkeypatch, client, settings)

    output_path = tmp_path / "child-result.json"
    env = os.environ.copy()
    env.update(
        {
            _CHILD_FLAG: "1",
            _CHROMA_DIR: str(chroma_directory),
            _OUTPUT_PATH: str(output_path),
            "ANONYMIZED_TELEMETRY": "False",
        }
    )
    command = [
        sys.executable,
        "-m",
        "pytest",
        f"{Path(__file__).resolve()}::test_restarted_process_child",
        "-q",
        "-p",
        "no:cacheprovider",
        f"--basetemp={tmp_path / 'child-basetemp'}",
    ]
    child = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert child.returncode == 0, (child.stdout + child.stderr)[-4000:]
    child_record = json.loads(output_path.read_text(encoding="utf-8"))
    assert child_record.pop("reopened_from_disk") is True
    assert child_record == record


def test_restarted_process_child(monkeypatch, client, tmp_path):
    if os.environ.get(_CHILD_FLAG) != "1":
        pytest.skip("only run in the restarted Python process")
    assert not manager._store_cache
    settings = _configure(monkeypatch, tmp_path, Path(os.environ[_CHROMA_DIR]))
    # The restart reads the BM25 corpus back a page at a time (a whole-collection read fails
    # past SQLite's variable limit, live check 2026-10-18): 600 records over ten pages must
    # give the ingesting process's pools and answer.
    monkeypatch.setattr(manager, "RESTORE_PAGE", 64)
    record = _record_answers(monkeypatch, client, settings)
    record["reopened_from_disk"] = True
    Path(os.environ[_OUTPUT_PATH]).write_text(json.dumps(record), encoding="utf-8")


def test_candidate_pool_sees_a_change_beyond_the_rerank_depth(monkeypatch):
    from vectordb._base_manager import HybridRetriever

    settings = Settings()
    assert settings.retrieval_top_k > settings.rerank_top_k
    chunks = [
        Document(page_content=f"cargo item {index}", metadata={"chunk_index": index})
        for index in range(settings.retrieval_top_k + 1)
    ]

    class FixedVectorStore:
        def __init__(self, ranked):
            self.ranked = ranked

        def similarity_search(self, query, k):
            return self.ranked[:k]

    def retriever_for(ranked):
        return HybridRetriever(
            vector_store=FixedVectorStore(ranked),
            chunks=chunks,
            retrieval_k=settings.retrieval_top_k,
            rerank_k=settings.rerank_top_k,
            rrf_k=settings.rrf_k,
            doc_key_chars=settings.rrf_doc_key_chars,
            reranker=None,
            use_bm25=True,
        )

    first = retriever_for(chunks[: settings.retrieval_top_k])
    second = retriever_for(
        [*chunks[: settings.retrieval_top_k - 1], chunks[settings.retrieval_top_k]]
    )
    # No chunk shares a query token, so BM25 adds nothing to the vector list.
    query = "unmatchedquery"
    first_short = [doc.metadata["chunk_index"] for doc in first.get_relevant_documents(query)]
    second_short = [doc.metadata["chunk_index"] for doc in second.get_relevant_documents(query)]
    assert len(first_short) == settings.rerank_top_k
    assert first_short == second_short

    first_pool = _candidate_pool(monkeypatch, first, settings, [query])
    second_pool = _candidate_pool(monkeypatch, second, settings, [query])
    assert first_pool != second_pool
    assert first_pool[1] != second_pool[1]


def test_dropped_configuration_leaves_unpersisted_records(monkeypatch, tmp_path):
    from langchain_chroma import Chroma

    chroma_directory = tmp_path / "control-chroma"
    settings = _configure(monkeypatch, tmp_path, chroma_directory)
    fake = manager.get_embeddings()

    class DefaultThresholdChroma(Chroma):
        @classmethod
        def from_documents(cls, *args, **kwargs):
            assert kwargs.pop("collection_configuration") == {"hnsw": {"sync_threshold": 1}}
            return super().from_documents(*args, **kwargs)

    monkeypatch.setattr(manager, "_get_chroma", lambda: DefaultThresholdChroma)
    result = manager.build_vector_store_with_publication(
        _docs(),
        {"chunk_size": settings.chunk_size, "chunk_overlap": settings.chunk_overlap},
        embeddings=fake,
        tenant_id="default",
    )
    assert len(result.chunks) == 600
    assert result.publication is not None
    positions = read_log_positions(chroma_directory)
    assert positions["chroma_vector_persisted_seq_id"] < positions["chroma_log_max_seq_id"]

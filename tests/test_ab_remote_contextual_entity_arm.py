"""Unit wiring for the GR-2 offline entity arm in the two-phase A/B harness."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from evaluation.query_classification import _current_code_provenance, _query_sha256
from ingestion.entity_extraction import extract_entities, load_extraction_cache
from ingestion.entity_graph import add_entity_graph
from ingestion.structure_graph import build_structural_graph
from ingestion.structure_graph_projection import project_structure_graph
from scripts import ab_remote_contextual as remote
from vectordb._base_manager import Document, HybridRetriever

TENANT = "aircargo"
EMBED_MODEL = "fake-embed"
QUERY = "How does the air waybill connect to customs clearance?"
FUSION_QUERY = "zzzxq nonce token"
ENTITY_ONLY_TEXT = "Omega pallet bay unused entirely."
HR_OUTSIDE_TEXT = "HR probation rules sit apart."
_ARM_ENV_KEYS = (
    "RAG_SEMANTIC_CHUNKING",
    "RAG_STRUCTURAL_CHUNKING",
    "RAG_RERANKER_MODEL",
)


def _register_arm_env(monkeypatch: Any) -> None:
    for key in _ARM_ENV_KEYS:
        value = os.environ.get(key)
        if value is None:
            monkeypatch.setenv(key, "")
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)


@pytest.fixture(autouse=True)
def restore_arm_env(monkeypatch: Any) -> Iterator[None]:
    _register_arm_env(monkeypatch)
    yield


def _doc(
    text: str,
    source: str,
    chunk_index: int,
    section: str,
    category: str = "shipping",
) -> Document:
    return Document(
        page_content=text,
        metadata={
            "source": source,
            "chunk_index": chunk_index,
            "categories": [category],
            "h1": "Policy",
            "h2": section,
        },
    )


def synthetic_chunks() -> list[Document]:
    return [
        _doc("AWB booking rules cover the air waybill.", "booking.md", 0, "Booking"),
        _doc("Confirm the booking after the AWB is issued.", "booking.md", 1, "Booking"),
        _doc("AWB customs clearance uses the same air waybill.", "customs.md", 0, "Customs"),
        _doc("Customs cargo holds at the warehouse.", "cargo.md", 0, "Cargo"),
    ]


def fusion_chunks() -> list[Document]:
    return [
        *synthetic_chunks(),
        _doc("General apron notes without the tracked tokens.", "proc.md", 0, "Step1"),
        _doc("Another apron note without the tracked tokens.", "proc.md", 1, "Step2"),
        _doc("Third apron note without the tracked tokens.", "proc.md", 2, "Step3"),
        _doc(ENTITY_ONLY_TEXT, "warehouse.md", 0, "Warehouse"),
        _doc(HR_OUTSIDE_TEXT, "hr.md", 0, "HR", category="hr"),
    ]


def _embed_text(text: str) -> list[float]:
    dim = 8
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    vec = np.array([(digest[i] - 128) / 128.0 for i in range(dim)], dtype=np.float32)
    vec += 0.05 * float(len(text) % 7)
    norm = float(np.linalg.norm(vec)) or 1.0
    return (vec / norm).tolist()


class FakeEmbeddings:
    def __init__(self) -> None:
        self.embed_document_calls = 0
        self.embed_query_calls = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.embed_document_calls += 1
        return [_embed_text(text) for text in texts]

    def embed_query(self, query: str) -> list[float]:
        self.embed_query_calls += 1
        return _embed_text(query)


class FakeStore:
    def __init__(self, chunks: list[Document]) -> None:
        self._chunks = chunks
        self._mat = np.asarray(
            [_embed_text(chunk.page_content) for chunk in chunks], dtype=np.float32
        )

    def similarity_search(self, query: str, k: int = 20, filter: Any = None) -> list[Document]:
        vector = np.asarray(_embed_text(query), dtype=np.float32)
        order = np.argsort(-(self._mat @ vector))
        if filter is not None:
            allowed = set(filter["source"]["$in"])
            order = [
                index
                for index in order
                if (self._chunks[index].metadata or {}).get("source") in allowed
            ]
        return [self._chunks[int(index)] for index in order[:k]]


class FakeReranker:
    def predict(self, pairs: list[tuple[str, str]], batch_size: int | None = None) -> list[float]:
        _ = batch_size
        return [-float(index) for index, _pair in enumerate(pairs)]


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        structural_chunking=True,
        contextual_headers=False,
        chunk_size=800,
        chunk_overlap=200,
        retrieval_top_k=20,
        rerank_top_k=5,
        embedding_model=EMBED_MODEL,
        reranker_model="fake-rerank",
        parent_expansion_max_chars=2400,
    )


def _case(
    *,
    case_id: str = "case-1",
    query: str = QUERY,
    label: str = "single_hop",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "case_id": case_id,
        "query": query,
        "tenant_id": TENANT,
        "question_class": label,
        "expected": {"answer_contains": ["air waybill"]},
    }
    if tags is not None:
        row["tags"] = tags
    return row


def _write_cases(path: Path, cases: list[dict[str, Any]]) -> str:
    path.write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases),
        encoding="utf-8",
        newline="\n",
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _entity_answer(prompt: str) -> str:
    mapping = {
        "AWB booking rules cover the air waybill.": '["AWB", "booking"]',
        "Confirm the booking after the AWB is issued.": '["AWB", "booking"]',
        "AWB customs clearance uses the same air waybill.": '["AWB", "customs"]',
        "Customs cargo holds at the warehouse.": '["customs", "cargo"]',
        "HR probation rules.": '["HR"]',
        "General apron notes without the tracked tokens.": "[]",
        "Another apron note without the tracked tokens.": "[]",
        "Third apron note without the tracked tokens.": "[]",
        ENTITY_ONLY_TEXT: '["AWB"]',
        HR_OUTSIDE_TEXT: '["AWB"]',
    }
    for text, answer in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
        if text in prompt:
            return answer
    raise AssertionError(prompt)


def _fusion_entity_answer(prompt: str) -> str:
    mapping = {
        "AWB booking rules cover the air waybill.": '["booking"]',
        "Confirm the booking after the AWB is issued.": '["booking"]',
        "AWB customs clearance uses the same air waybill.": '["customs"]',
        "Customs cargo holds at the warehouse.": '["customs"]',
        "General apron notes without the tracked tokens.": "[]",
        "Another apron note without the tracked tokens.": "[]",
        "Third apron note without the tracked tokens.": "[]",
        ENTITY_ONLY_TEXT: '["AWB"]',
        HR_OUTSIDE_TEXT: '["AWB"]',
    }
    for text, answer in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
        if text in prompt:
            return answer
    raise AssertionError(prompt)


def _write_extraction_cache(
    cache_dir: Path,
    chunks: list[Document],
    invoke: Any,
    **kwargs: Any,
) -> dict[str, list[str]]:
    return extract_entities(
        chunks,
        tenant_id=TENANT,
        corpus_sha256="a" * 64,
        model="mistral-small-2506",
        cache_dir=cache_dir,
        invoke=invoke,
        **kwargs,
    )


def _write_classifications(
    cache_dir: Path,
    cases: list[dict[str, Any]],
    dataset_sha256: str,
    routed: dict[str, dict[str, Any]],
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        **_current_code_provenance(),
        "dataset_sha256": dataset_sha256,
        "case_count": len(cases),
        "provider": "test",
        "model": "test",
        "model_digest": None,
        "options": {"temperature": 0},
    }
    (cache_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with (cache_dir / "classifications.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for case in cases:
            payload = {
                "case_id": case["case_id"],
                "query_sha256": _query_sha256(str(case["query"])),
                **routed[str(case["case_id"])],
            }
            stream.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _multi_hop_route() -> dict[str, Any]:
    return {
        "complexity": "complex",
        "question_class": "multi_hop",
        "entities": ["air waybill", "customs"],
        "needs_multi_hop": True,
        "reason_code": "MULTI_SOURCE_CHAIN",
    }


def _fusion_route() -> dict[str, Any]:
    return {
        "complexity": "complex",
        "question_class": "multi_hop",
        "entities": ["air waybill"],
        "needs_multi_hop": True,
        "reason_code": "MULTI_SOURCE_CHAIN",
    }


def _single_hop_route() -> dict[str, Any]:
    return {
        "complexity": "simple",
        "question_class": "single_hop",
        "entities": ["air waybill"],
        "needs_multi_hop": False,
        "reason_code": "SINGLE_SOURCE",
    }


def _install_pool_fakes(
    monkeypatch: Any,
    *,
    chunks: list[Document],
    embeddings: FakeEmbeddings,
    reranker: Any | None = None,
) -> None:
    class FakeLoader:
        def __init__(self, recursive: bool = False) -> None:
            _ = recursive

        def load_documents(self, path: str) -> list[Document]:
            _ = path
            return list(chunks)

    monkeypatch.setattr("ingestion.loader.DocumentLoader", FakeLoader)
    monkeypatch.setattr(
        "vectordb._base_manager.select_chunks",
        lambda *args, **kwargs: list(chunks),
    )
    monkeypatch.setattr(
        "vectordb.manager.add_contextual_headers",
        lambda selected, docs, chunk_size=None: selected,
    )
    monkeypatch.setattr("config.settings.get_settings", _settings)
    monkeypatch.setattr("vectordb._base_manager.get_embeddings", lambda: embeddings)
    monkeypatch.setattr(
        "vectordb._base_manager.get_reranker",
        lambda: (
            reranker
            if reranker is not None
            else (_ for _ in ()).throw(AssertionError("reranker loaded during pools"))
        ),
    )


def _retriever(
    chunks: list[Document], extracted: dict[str, list[str]], reranker: Any
) -> HybridRetriever:
    graph = add_entity_graph(build_structural_graph(chunks, tenant_id=TENANT), extracted)
    return HybridRetriever(
        vector_store=FakeStore(chunks),
        chunks=chunks,
        retrieval_k=20,
        rerank_k=5,
        reranker=reranker,
        graph_projection=project_structure_graph(graph),
    )


def _contexts(docs: list[Document]) -> list[str]:
    return [doc.page_content for doc in docs]


def _fusion_setup(
    tmp_path: Path, reranker: Any | None
) -> tuple[list[Document], dict[str, list[str]], HybridRetriever]:
    chunks = fusion_chunks()
    extracted = _write_extraction_cache(tmp_path / "entities", chunks, _fusion_entity_answer)
    return chunks, extracted, _retriever(chunks, extracted, reranker)


def _rank_of(docs: list[Document], text: str) -> int | None:
    return next((index for index, doc in enumerate(docs) if doc.page_content == text), None)


def _contains_text(docs: list[Document], text: str) -> bool:
    return any(text in doc.page_content for doc in docs)


def test_g2_helpers_match_product_lane_multi_hop(tmp_path: Path) -> None:
    chunks, extracted, retriever = _fusion_setup(tmp_path, FakeReranker())
    case = _case(query=FUSION_QUERY, label="single_hop")
    entities = ["air waybill"]
    assert len(chunks) > retriever._rerank_k

    vector_results = retriever._vector_search(FUSION_QUERY)
    bm25_results = retriever._graph_bm25_documents(FUSION_QUERY, None)
    assert bm25_results == []
    assert _rank_of(vector_results, ENTITY_ONLY_TEXT) is not None
    assert _rank_of(vector_results, ENTITY_ONLY_TEXT) >= retriever._rerank_k
    assert _rank_of(bm25_results, ENTITY_ONLY_TEXT) is None

    assembled = remote._assemble_graph_candidates(
        retriever,
        FUSION_QUERY,
        case,
        question_class="multi_hop",
        entities=entities,
    )
    assert assembled.entity_candidates > 0
    assert assembled.matched_entities
    assert _rank_of(assembled.documents[: retriever._rerank_k], ENTITY_ONLY_TEXT) is not None
    without_entity = (
        retriever._rrf_merge(vector_results, bm25_results) if bm25_results else vector_results
    )
    assert _rank_of(without_entity[: retriever._rerank_k], ENTITY_ONLY_TEXT) is None

    ranked = retriever._rerank(FUSION_QUERY, assembled.documents)
    g2_docs = remote._apply_graph_post_rerank(retriever, ranked, retriever._rerank_k)
    product_docs, path = retriever.get_graph_documents_with_path(
        FUSION_QUERY, question_class="multi_hop", entities=entities
    )
    assert path is not None
    assert path["kind"] == "structural_entity"
    assert _contexts(g2_docs) == _contexts(product_docs)
    assert _contains_text(g2_docs, ENTITY_ONLY_TEXT)

    single_pool = remote._assemble_graph_candidates(
        retriever,
        FUSION_QUERY,
        case,
        question_class="single_hop",
        entities=entities,
    )
    single_docs = remote._apply_graph_post_rerank(
        retriever,
        retriever._rerank(FUSION_QUERY, single_pool.documents),
        retriever._rerank_k,
    )
    assert _contexts(g2_docs) != _contexts(single_docs)
    assert not _contains_text(single_docs, ENTITY_ONLY_TEXT)

    bare = _retriever(chunks, extracted, None)
    product_none, _ = bare.get_graph_documents_with_path(
        FUSION_QUERY, question_class="multi_hop", entities=entities
    )
    g2_none = remote._apply_graph_post_rerank(bare, assembled.documents, bare._rerank_k)
    assert _contexts(g2_none) == _contexts(product_none)


def test_g2_single_hop_matches_g1_without_entity_candidates(tmp_path: Path) -> None:
    chunks, _, g2_retriever = _fusion_setup(tmp_path, FakeReranker())
    reranker = g2_retriever._reranker
    g1_retriever = HybridRetriever(
        vector_store=FakeStore(chunks),
        chunks=chunks,
        retrieval_k=20,
        rerank_k=5,
        reranker=reranker,
        graph_projection=project_structure_graph(build_structural_graph(chunks, tenant_id=TENANT)),
    )
    case = _case(query=FUSION_QUERY, label="multi_hop")

    g2_pool = remote._assemble_graph_candidates(
        g2_retriever,
        FUSION_QUERY,
        case,
        question_class="single_hop",
        entities=["air waybill", "customs"],
    )
    g1_pool = remote._assemble_graph_candidates(g1_retriever, FUSION_QUERY, case)
    assert g2_pool.entity_candidates == 0
    assert g2_pool.matched_entities == []
    assert g2_pool.entity_hops == 0
    assert _contexts(g2_pool.documents) == _contexts(g1_pool.documents)
    assert _rank_of(g2_pool.documents[: g2_retriever._rerank_k], ENTITY_ONLY_TEXT) is None

    g2_final = remote._apply_graph_post_rerank(
        g2_retriever,
        g2_retriever._rerank(FUSION_QUERY, g2_pool.documents),
        g2_retriever._rerank_k,
    )
    g1_final = remote._apply_graph_post_rerank(
        g1_retriever,
        g1_retriever._rerank(FUSION_QUERY, g1_pool.documents),
        g1_retriever._rerank_k,
    )
    assert _contexts(g2_final) == _contexts(g1_final)
    assert not _contains_text(g2_final, ENTITY_ONLY_TEXT)
    product_docs, path = g2_retriever.get_graph_documents_with_path(
        FUSION_QUERY, question_class="single_hop", entities=["air waybill"]
    )
    assert path is not None
    assert path["kind"] == "structural"
    assert _contexts(g2_final) == _contexts(product_docs)


def test_g2_pools_routes_by_classification_not_label(monkeypatch: Any, tmp_path: Path) -> None:
    chunks = synthetic_chunks()
    cases = [_case(label="single_hop")]
    cases_path = tmp_path / "cases.jsonl"
    digest = _write_cases(cases_path, cases)
    entities_dir = tmp_path / "entities"
    _write_extraction_cache(entities_dir, chunks, _entity_answer)
    class_dir = tmp_path / "classifications"
    _write_classifications(class_dir, cases, digest, {"case-1": _multi_hop_route()})
    embeddings = FakeEmbeddings()
    _install_pool_fakes(monkeypatch, chunks=chunks, embeddings=embeddings)

    out_dir = tmp_path / "out"
    assert (
        remote.stage_pools(
            "G2",
            tmp_path / "corpus",
            cases_path,
            out_dir,
            entities_cache=entities_dir,
            classifications=class_dir,
        )
        == 0
    )
    rows = json.loads((out_dir / "ab_phase2_G2_pool.json").read_text(encoding="utf-8"))
    assert rows[0]["routed_question_class"] == "multi_hop"
    assert rows[0]["query_entities"] == ["air waybill", "customs"]
    assert rows[0]["entity_candidates"] > 0
    assert rows[0]["matched_entities"]


def test_incomplete_extraction_cache_exits_2_without_pool(
    monkeypatch: Any, tmp_path: Path, capsys: Any
) -> None:
    chunks = synthetic_chunks()
    cases = [_case()]
    cases_path = tmp_path / "cases.jsonl"
    digest = _write_cases(cases_path, cases)
    entities_dir = tmp_path / "entities"
    _write_extraction_cache(entities_dir, chunks, _entity_answer, max_calls=1)
    class_dir = tmp_path / "classifications"
    _write_classifications(class_dir, cases, digest, {"case-1": _multi_hop_route()})
    _install_pool_fakes(monkeypatch, chunks=chunks, embeddings=FakeEmbeddings())
    out_dir = tmp_path / "out"

    assert (
        remote.stage_pools(
            "G2",
            tmp_path / "corpus",
            cases_path,
            out_dir,
            entities_cache=entities_dir,
            classifications=class_dir,
        )
        == 2
    )
    captured = capsys.readouterr().out
    assert "cached=" in captured and "rejected=" in captured and "total=" in captured
    assert not (out_dir / "ab_phase2_G2_pool.json").exists()
    assert not (out_dir / "ab_phase2_G2_pool_meta.json").exists()


def test_rejection_only_coverage_builds_pool(monkeypatch: Any, tmp_path: Path) -> None:
    chunks = synthetic_chunks()
    answers = {
        "AWB booking rules cover the air waybill.": "nonsense",
        "Confirm the booking after the AWB is issued.": "nonsense",
        "AWB customs clearance uses the same air waybill.": "nonsense",
        "Customs cargo holds at the warehouse.": "nonsense",
    }

    def invoke(prompt: str) -> str:
        for text, answer in answers.items():
            if text in prompt:
                return answer
        raise AssertionError(prompt)

    cases = [_case()]
    cases_path = tmp_path / "cases.jsonl"
    digest = _write_cases(cases_path, cases)
    entities_dir = tmp_path / "entities"
    _write_extraction_cache(entities_dir, chunks, invoke, on_invalid="record")
    cache = load_extraction_cache(entities_dir, chunks, tenant_id=TENANT)
    assert cache.entities == {}
    assert len(cache.rejected) == len(chunks)
    class_dir = tmp_path / "classifications"
    _write_classifications(class_dir, cases, digest, {"case-1": _single_hop_route()})
    _install_pool_fakes(monkeypatch, chunks=chunks, embeddings=FakeEmbeddings())
    out_dir = tmp_path / "out"

    assert (
        remote.stage_pools(
            "G2",
            tmp_path / "corpus",
            cases_path,
            out_dir,
            entities_cache=entities_dir,
            classifications=class_dir,
        )
        == 0
    )
    meta = json.loads((out_dir / "ab_phase2_G2_pool_meta.json").read_text(encoding="utf-8"))
    assert sorted(meta["rejected_chunk_ids"]) == sorted(cache.rejected)
    assert meta["rejected_count"] == len(cache.rejected)
    assert "peak_rss" not in meta
    assert "peak_rss_bytes" in meta
    assert (out_dir / "ab_phase2_G2_pool.json").exists()


def test_classification_digest_mismatch_exits_2(
    monkeypatch: Any, tmp_path: Path, capsys: Any
) -> None:
    chunks = synthetic_chunks()
    cases = [_case()]
    cases_path = tmp_path / "cases.jsonl"
    _write_cases(cases_path, cases)
    other = "b" * 64
    entities_dir = tmp_path / "entities"
    _write_extraction_cache(entities_dir, chunks, _entity_answer)
    class_dir = tmp_path / "classifications"
    _write_classifications(class_dir, cases, other, {"case-1": _multi_hop_route()})
    _install_pool_fakes(monkeypatch, chunks=chunks, embeddings=FakeEmbeddings())
    out_dir = tmp_path / "out"

    assert (
        remote.stage_pools(
            "G2",
            tmp_path / "corpus",
            cases_path,
            out_dir,
            entities_cache=entities_dir,
            classifications=class_dir,
        )
        == 2
    )
    captured = capsys.readouterr().out
    run_digest = hashlib.sha256(cases_path.read_bytes()).hexdigest()
    assert "dataset_sha256" in captured
    assert other in captured
    assert run_digest in captured
    assert not (out_dir / "ab_phase2_G2_pool.json").exists()


def test_cli_dispatches_g2_pools_and_rerank(monkeypatch: Any, tmp_path: Path) -> None:
    calls: list[tuple[object, ...]] = []

    def _pools(
        arm: str,
        corpus: Path,
        cases: Path,
        out_dir: Path,
        expansions: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> int:
        _ = corpus, cases, out_dir, expansions
        calls.append(("pools", arm, kwargs))
        return 0

    def _rerank(arm: str, out_dir: Path) -> int:
        _ = out_dir
        calls.append(("rerank", arm))
        return 0

    monkeypatch.setattr(remote, "stage_pools", _pools)
    monkeypatch.setattr(remote, "stage_rerank", _rerank)
    entities = tmp_path / "entities"
    classifications = tmp_path / "classifications"
    assert (
        remote.main(
            [
                "--stage",
                "pools",
                "--arm",
                "G2",
                "--entities-cache",
                str(entities),
                "--classifications",
                str(classifications),
                "--out-dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert remote.main(["--stage", "rerank", "--arm", "G2", "--out-dir", str(tmp_path)]) == 0
    assert calls[0][0] == "pools" and calls[0][1] == "G2"
    assert calls[0][2]["entities_cache"] == entities
    assert calls[0][2]["classifications"] == classifications
    assert calls[1] == ("rerank", "G2")


@pytest.mark.parametrize(
    "argv",
    [
        ["--stage", "pools", "--arm", "G2"],
        ["--stage", "pools", "--arm", "G2", "--entities-cache", "e"],
        ["--stage", "pools", "--arm", "G2", "--classifications", "c"],
    ],
)
def test_g2_pools_without_both_caches_is_usage_error(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        remote.main([*argv, "--out-dir", "."])
    assert excinfo.value.code == 2


def test_embeddings_cache_second_run_skips_encoder(monkeypatch: Any, tmp_path: Path) -> None:
    chunks = synthetic_chunks()
    cases = [_case()]
    cases_path = tmp_path / "cases.jsonl"
    digest = _write_cases(cases_path, cases)
    entities_dir = tmp_path / "entities"
    _write_extraction_cache(entities_dir, chunks, _entity_answer)
    class_dir = tmp_path / "classifications"
    _write_classifications(class_dir, cases, digest, {"case-1": _single_hop_route()})
    embeddings = FakeEmbeddings()
    _install_pool_fakes(monkeypatch, chunks=chunks, embeddings=embeddings)
    out_dir = tmp_path / "out"
    cache_path = tmp_path / "emb.npz"

    kwargs = {
        "entities_cache": entities_dir,
        "classifications": class_dir,
        "embeddings_cache": cache_path,
    }
    assert remote.stage_pools("G2", tmp_path / "corpus", cases_path, out_dir, **kwargs) == 0
    assert embeddings.embed_document_calls == 1
    assert cache_path.exists()
    assert remote.stage_pools("G2", tmp_path / "corpus", cases_path, out_dir, **kwargs) == 0
    assert embeddings.embed_document_calls == 1
    assert embeddings.embed_query_calls == 2


@pytest.mark.parametrize("kind", ["digest", "model"])
def test_embeddings_cache_mismatch_exits_2(
    monkeypatch: Any, tmp_path: Path, capsys: Any, kind: str
) -> None:
    chunks = synthetic_chunks()
    cases = [_case()]
    cases_path = tmp_path / "cases.jsonl"
    digest = _write_cases(cases_path, cases)
    entities_dir = tmp_path / "entities"
    _write_extraction_cache(entities_dir, chunks, _entity_answer)
    class_dir = tmp_path / "classifications"
    _write_classifications(class_dir, cases, digest, {"case-1": _single_hop_route()})
    embeddings = FakeEmbeddings()
    _install_pool_fakes(monkeypatch, chunks=chunks, embeddings=embeddings)
    out_dir = tmp_path / "out"
    cache_path = tmp_path / "emb.npz"
    assert (
        remote.stage_pools(
            "G2",
            tmp_path / "corpus",
            cases_path,
            out_dir,
            entities_cache=entities_dir,
            classifications=class_dir,
            embeddings_cache=cache_path,
        )
        == 0
    )
    loaded = np.load(cache_path, allow_pickle=False)
    matrix = np.array(loaded["embeddings"])
    chunk_digest = bytes(np.asarray(loaded["chunk_text_digest"]).item()).decode("ascii")
    model_name = bytes(np.asarray(loaded["embedding_model"]).item()).decode("utf-8")
    loaded.close()
    if kind == "digest":
        chunk_digest = "0" * 64
    else:
        model_name = "other-model"
    np.savez(
        cache_path,
        embeddings=matrix,
        chunk_text_digest=np.bytes_(chunk_digest.encode("ascii")),
        embedding_model=np.bytes_(model_name.encode("utf-8")),
        row_count=np.int64(matrix.shape[0]),
    )
    (out_dir / "ab_phase2_G2_pool.json").unlink()
    assert (
        remote.stage_pools(
            "G2",
            tmp_path / "corpus",
            cases_path,
            out_dir,
            entities_cache=entities_dir,
            classifications=class_dir,
            embeddings_cache=cache_path,
        )
        == 2
    )
    captured = capsys.readouterr().out
    assert "embeddings cache mismatch" in captured
    assert not (out_dir / "ab_phase2_G2_pool.json").exists()
    assert embeddings.embed_document_calls == 1


def test_g2_rerank_keeps_pool_fields_and_g1_gains_only_rerank_s(
    monkeypatch: Any, tmp_path: Path
) -> None:
    chunks = synthetic_chunks()
    cases = [_case(label="single_hop")]
    cases_path = tmp_path / "cases.jsonl"
    digest = _write_cases(cases_path, cases)
    entities_dir = tmp_path / "entities"
    _write_extraction_cache(entities_dir, chunks, _entity_answer)
    class_dir = tmp_path / "classifications"
    _write_classifications(class_dir, cases, digest, {"case-1": _multi_hop_route()})
    embeddings = FakeEmbeddings()
    reranker = FakeReranker()
    _install_pool_fakes(monkeypatch, chunks=chunks, embeddings=embeddings, reranker=reranker)
    out_dir = tmp_path / "out"
    assert (
        remote.stage_pools(
            "G2",
            tmp_path / "corpus",
            cases_path,
            out_dir,
            entities_cache=entities_dir,
            classifications=class_dir,
        )
        == 0
    )
    pool = json.loads((out_dir / "ab_phase2_G2_pool.json").read_text(encoding="utf-8"))[0]
    g2_fields = (
        "routed_question_class",
        "query_entities",
        "matched_entities",
        "entity_hops",
        "entity_candidates",
        "timing_ms",
    )
    assert remote.stage_rerank("G2", out_dir) == 0
    g2 = json.loads((out_dir / "ab_candidates_phase2_G2.json").read_text(encoding="utf-8"))[0]
    for field in g2_fields:
        assert g2[field] == pool[field]
    assert g2["graph_postprocessed"] is True
    assert g2["graph_prefiltered"] is pool["graph_prefiltered"]
    assert isinstance(g2["rerank_s"], float)

    g1_out = tmp_path / "g1"
    assert remote.stage_pools("G1", tmp_path / "corpus", cases_path, g1_out) == 0
    g1_pool = json.loads((g1_out / "ab_phase2_G1_pool.json").read_text(encoding="utf-8"))[0]
    for field in g2_fields:
        assert field not in g1_pool
    assert remote.stage_rerank("G1", g1_out) == 0
    g1 = json.loads((g1_out / "ab_candidates_phase2_G1.json").read_text(encoding="utf-8"))[0]
    for field in g2_fields:
        assert field not in g1
    assert isinstance(g1["rerank_s"], float)
    assert g1["graph_postprocessed"] is True


def test_g2_stages_match_product_lane(monkeypatch: Any, tmp_path: Path) -> None:
    chunks = fusion_chunks()
    cases = [_case(query=FUSION_QUERY, label="single_hop")]
    cases_path = tmp_path / "cases.jsonl"
    digest = _write_cases(cases_path, cases)
    entities_dir = tmp_path / "entities"
    extracted = _write_extraction_cache(entities_dir, chunks, _fusion_entity_answer)
    class_dir = tmp_path / "classifications"
    route = _fusion_route()
    _write_classifications(class_dir, cases, digest, {"case-1": route})
    embeddings = FakeEmbeddings()
    reranker = FakeReranker()
    _install_pool_fakes(monkeypatch, chunks=chunks, embeddings=embeddings, reranker=reranker)
    out_dir = tmp_path / "out"
    assert (
        remote.stage_pools(
            "G2",
            tmp_path / "corpus",
            cases_path,
            out_dir,
            entities_cache=entities_dir,
            classifications=class_dir,
        )
        == 0
    )
    assert remote.stage_rerank("G2", out_dir) == 0
    g2 = json.loads((out_dir / "ab_candidates_phase2_G2.json").read_text(encoding="utf-8"))[0]
    retriever = _retriever(chunks, extracted, FakeReranker())
    product_docs, _ = retriever.get_graph_documents_with_path(
        FUSION_QUERY, question_class="multi_hop", entities=list(route["entities"])
    )
    assert g2["cands"] == _contexts(product_docs)
    assert any(ENTITY_ONLY_TEXT in text for text in g2["cands"])
    single_docs, _ = retriever.get_graph_documents_with_path(
        FUSION_QUERY, question_class="single_hop", entities=list(route["entities"])
    )
    assert g2["cands"] != _contexts(single_docs)
    assert all(ENTITY_ONLY_TEXT not in text for text in _contexts(single_docs))


def test_g2_set_arm_env_is_structural() -> None:
    remote._set_arm_env("G2")
    assert remote.os.environ["RAG_STRUCTURAL_CHUNKING"] == "true"


def test_g2_helpers_match_product_lane_with_matching_category(tmp_path: Path) -> None:
    chunks, _extracted, retriever = _fusion_setup(tmp_path, FakeReranker())
    case = _case(query=FUSION_QUERY, label="single_hop", tags=["shipping"])
    entities = ["air waybill"]
    shipping = [
        chunk for chunk in chunks if "shipping" in ((chunk.metadata or {}).get("categories") or [])
    ]
    assert len(shipping) > retriever._rerank_k

    assembled = remote._assemble_graph_candidates(
        retriever,
        FUSION_QUERY,
        case,
        question_class="multi_hop",
        entities=entities,
    )
    assert assembled.graph_sources is not None
    vector_results = retriever._vector_search_for_sources(FUSION_QUERY, assembled.graph_sources)
    bm25_results = retriever._graph_bm25_documents(FUSION_QUERY, assembled.graph_sources)
    assert bm25_results == []
    assert _rank_of(vector_results, ENTITY_ONLY_TEXT) is not None
    assert _rank_of(vector_results, ENTITY_ONLY_TEXT) >= retriever._rerank_k
    unfiltered_entities, _, _ = retriever._entity_index.search(entities, sources=None)
    filtered_entities, _, _ = retriever._entity_index.search(
        entities, sources=assembled.graph_sources
    )
    assert any(doc.page_content == HR_OUTSIDE_TEXT for doc in unfiltered_entities)
    assert all(doc.page_content != HR_OUTSIDE_TEXT for doc in filtered_entities)
    assert _rank_of(assembled.documents[: retriever._rerank_k], ENTITY_ONLY_TEXT) is not None

    ranked = retriever._rerank(FUSION_QUERY, assembled.documents)
    g2_docs = remote._apply_graph_post_rerank(retriever, ranked, retriever._rerank_k)
    product_docs, path = retriever.get_graph_documents_with_path(
        FUSION_QUERY,
        categories=["shipping"],
        question_class="multi_hop",
        entities=entities,
    )
    assert path is not None
    assert path["prefilter_applied"] is True
    assert _contexts(g2_docs) == _contexts(product_docs)
    assert _contains_text(g2_docs, ENTITY_ONLY_TEXT)
    assert not _contains_text(g2_docs, HR_OUTSIDE_TEXT)

    single_docs, _ = retriever.get_graph_documents_with_path(
        FUSION_QUERY,
        categories=["shipping"],
        question_class="single_hop",
        entities=entities,
    )
    assert _contexts(g2_docs) != _contexts(single_docs)
    assert not _contains_text(single_docs, ENTITY_ONLY_TEXT)


def test_g2_pool_row_keeps_graph_prefiltered_for_matching_tag(
    monkeypatch: Any, tmp_path: Path
) -> None:
    chunks = fusion_chunks()
    cases = [_case(query=FUSION_QUERY, label="single_hop", tags=["shipping"])]
    cases_path = tmp_path / "cases.jsonl"
    digest = _write_cases(cases_path, cases)
    entities_dir = tmp_path / "entities"
    extracted = _write_extraction_cache(entities_dir, chunks, _fusion_entity_answer)
    class_dir = tmp_path / "classifications"
    route = _fusion_route()
    _write_classifications(class_dir, cases, digest, {"case-1": route})
    embeddings = FakeEmbeddings()
    reranker = FakeReranker()
    _install_pool_fakes(monkeypatch, chunks=chunks, embeddings=embeddings, reranker=reranker)
    out_dir = tmp_path / "out"
    assert (
        remote.stage_pools(
            "G2",
            tmp_path / "corpus",
            cases_path,
            out_dir,
            entities_cache=entities_dir,
            classifications=class_dir,
        )
        == 0
    )
    pool = json.loads((out_dir / "ab_phase2_G2_pool.json").read_text(encoding="utf-8"))[0]
    assert pool["graph_prefiltered"] is True
    assert pool["graph_categories"] == ["shipping"]
    assert ENTITY_ONLY_TEXT in pool["cands"][: pool["rerank_k"]]
    assert remote.stage_rerank("G2", out_dir) == 0
    g2 = json.loads((out_dir / "ab_candidates_phase2_G2.json").read_text(encoding="utf-8"))[0]
    assert g2["graph_prefiltered"] is True
    retriever = _retriever(chunks, extracted, FakeReranker())
    product_docs, path = retriever.get_graph_documents_with_path(
        FUSION_QUERY,
        categories=["shipping"],
        question_class="multi_hop",
        entities=list(route["entities"]),
    )
    assert path is not None
    assert path["prefilter_applied"] is True
    assert g2["cands"] == _contexts(product_docs)
    assert any(ENTITY_ONLY_TEXT in text for text in g2["cands"])
    assert all(HR_OUTSIDE_TEXT not in text for text in g2["cands"])


def test_peak_rss_bytes_darwin(monkeypatch: Any) -> None:
    fake_resource = SimpleNamespace(
        RUSAGE_SELF=0,
        getrusage=lambda _who: SimpleNamespace(ru_maxrss=4096),
    )
    monkeypatch.setitem(sys.modules, "resource", fake_resource)
    monkeypatch.setattr(remote.sys, "platform", "darwin")
    assert remote._peak_rss() == 4096


def test_peak_rss_bytes_linux_kib(monkeypatch: Any) -> None:
    fake_resource = SimpleNamespace(
        RUSAGE_SELF=0,
        getrusage=lambda _who: SimpleNamespace(ru_maxrss=4096),
    )
    monkeypatch.setitem(sys.modules, "resource", fake_resource)
    monkeypatch.setattr(remote.sys, "platform", "linux")
    assert remote._peak_rss() == 4096 * 1024


def test_peak_rss_bytes_unavailable(monkeypatch: Any) -> None:
    real_import = __import__

    def blocked(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "resource":
            raise ImportError("no resource")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocked)
    assert remote._peak_rss() is None


@pytest.mark.parametrize("name", ["emb.bin", "emb"])
def test_embeddings_cache_non_npz_is_usage_error(tmp_path: Path, name: str) -> None:
    with pytest.raises(SystemExit) as excinfo:
        remote.main(
            [
                "--stage",
                "pools",
                "--arm",
                "G1",
                "--embeddings-cache",
                str(tmp_path / name),
                "--out-dir",
                str(tmp_path),
            ]
        )
    assert excinfo.value.code == 2


def test_embeddings_cache_non_npz_skips_encoder(monkeypatch: Any, tmp_path: Path) -> None:
    chunks = synthetic_chunks()
    cases = [_case()]
    cases_path = tmp_path / "cases.jsonl"
    digest = _write_cases(cases_path, cases)
    entities_dir = tmp_path / "entities"
    _write_extraction_cache(entities_dir, chunks, _entity_answer)
    class_dir = tmp_path / "classifications"
    _write_classifications(class_dir, cases, digest, {"case-1": _single_hop_route()})
    embeddings = FakeEmbeddings()
    _install_pool_fakes(monkeypatch, chunks=chunks, embeddings=embeddings)
    assert (
        remote.stage_pools(
            "G2",
            tmp_path / "corpus",
            cases_path,
            tmp_path / "out",
            entities_cache=entities_dir,
            classifications=class_dir,
            embeddings_cache=tmp_path / "emb.bin",
        )
        == 2
    )
    assert embeddings.embed_document_calls == 0


def test_arm_env_restored_after_own_monkeypatch_undo() -> None:
    patch = pytest.MonkeyPatch()
    try:
        recorded = {key: os.environ.get(key) for key in _ARM_ENV_KEYS}
        _register_arm_env(patch)
        remote._set_arm_env("G2")
        assert os.environ["RAG_STRUCTURAL_CHUNKING"] == "true"
        assert os.environ["RAG_SEMANTIC_CHUNKING"] == "false"
        assert os.environ["RAG_RERANKER_MODEL"] == ""
        assert any(os.environ.get(key) != recorded[key] for key in _ARM_ENV_KEYS)
        patch.undo()
        for key, value in recorded.items():
            assert os.environ.get(key) == value
    finally:
        patch.undo()


def test_truncated_embeddings_cache_exits_2(monkeypatch: Any, tmp_path: Path, capsys: Any) -> None:
    chunks = synthetic_chunks()
    cases = [_case()]
    cases_path = tmp_path / "cases.jsonl"
    digest = _write_cases(cases_path, cases)
    entities_dir = tmp_path / "entities"
    _write_extraction_cache(entities_dir, chunks, _entity_answer)
    class_dir = tmp_path / "classifications"
    _write_classifications(class_dir, cases, digest, {"case-1": _single_hop_route()})
    embeddings = FakeEmbeddings()
    _install_pool_fakes(monkeypatch, chunks=chunks, embeddings=embeddings)
    cache_path = tmp_path / "emb.npz"
    kwargs = {
        "entities_cache": entities_dir,
        "classifications": class_dir,
        "embeddings_cache": cache_path,
    }
    assert (
        remote.stage_pools("G2", tmp_path / "corpus", cases_path, tmp_path / "out", **kwargs) == 0
    )
    cache_path.write_bytes(cache_path.read_bytes()[:24])
    assert (
        remote.stage_pools("G2", tmp_path / "corpus", cases_path, tmp_path / "out", **kwargs) == 2
    )
    captured = capsys.readouterr().out
    assert "embeddings cache is unreadable" in captured
    assert embeddings.embed_document_calls == 1
    assert not (tmp_path / "out" / "ab_phase2_G2_pool.json").exists()


def test_embeddings_cache_save_leaves_no_temp(monkeypatch: Any, tmp_path: Path) -> None:
    chunks = synthetic_chunks()
    cases = [_case()]
    cases_path = tmp_path / "cases.jsonl"
    digest = _write_cases(cases_path, cases)
    entities_dir = tmp_path / "entities"
    _write_extraction_cache(entities_dir, chunks, _entity_answer)
    class_dir = tmp_path / "classifications"
    _write_classifications(class_dir, cases, digest, {"case-1": _single_hop_route()})
    _install_pool_fakes(monkeypatch, chunks=chunks, embeddings=FakeEmbeddings())
    cache_path = tmp_path / "emb.npz"
    assert (
        remote.stage_pools(
            "G2",
            tmp_path / "corpus",
            cases_path,
            tmp_path / "out",
            entities_cache=entities_dir,
            classifications=class_dir,
            embeddings_cache=cache_path,
        )
        == 0
    )
    leftovers = [
        path for path in cache_path.parent.iterdir() if path.suffix == ".npz" and path != cache_path
    ]
    assert leftovers == []
    assert cache_path.exists()
    out_temps = [
        path
        for path in (tmp_path / "out").iterdir()
        if path.name.startswith(".") and path.suffix == ".tmp"
    ]
    assert out_temps == []


def test_failed_g2_pools_removes_stale_outputs(
    monkeypatch: Any, tmp_path: Path, capsys: Any
) -> None:
    chunks = synthetic_chunks()
    cases = [_case()]
    cases_path = tmp_path / "cases.jsonl"
    digest = _write_cases(cases_path, cases)
    entities_dir = tmp_path / "entities"
    _write_extraction_cache(entities_dir, chunks, _entity_answer, max_calls=1)
    class_dir = tmp_path / "classifications"
    _write_classifications(class_dir, cases, digest, {"case-1": _multi_hop_route()})
    _install_pool_fakes(monkeypatch, chunks=chunks, embeddings=FakeEmbeddings())
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "ab_phase2_G2_pool.json").write_text("stale-pool", encoding="utf-8")
    (out_dir / "ab_phase2_G2_graph_chunks.json").write_text("stale-side", encoding="utf-8")
    (out_dir / "ab_phase2_G2_pool_meta.json").write_text("stale-meta", encoding="utf-8")
    (out_dir / "ab_candidates_phase2_G2.json").write_text("stale-cands", encoding="utf-8")
    assert (
        remote.stage_pools(
            "G2",
            tmp_path / "corpus",
            cases_path,
            out_dir,
            entities_cache=entities_dir,
            classifications=class_dir,
        )
        == 2
    )
    captured = capsys.readouterr().out
    assert "cached=" in captured and "rejected=" in captured and "total=" in captured
    assert not (out_dir / "ab_phase2_G2_pool.json").exists()
    assert not (out_dir / "ab_phase2_G2_graph_chunks.json").exists()
    assert not (out_dir / "ab_phase2_G2_pool_meta.json").exists()
    assert not (out_dir / "ab_candidates_phase2_G2.json").exists()


def test_empty_vector_search_unfiltered_exits_2(
    monkeypatch: Any, tmp_path: Path, capsys: Any
) -> None:
    chunks = synthetic_chunks()
    cases = [_case()]
    cases_path = tmp_path / "cases.jsonl"
    digest = _write_cases(cases_path, cases)
    entities_dir = tmp_path / "entities"
    _write_extraction_cache(entities_dir, chunks, _entity_answer)
    class_dir = tmp_path / "classifications"
    _write_classifications(class_dir, cases, digest, {"case-1": _single_hop_route()})
    embeddings = FakeEmbeddings()
    _install_pool_fakes(monkeypatch, chunks=chunks, embeddings=embeddings)

    from vectordb._base_manager import HybridRetriever

    real_init = HybridRetriever.__init__

    def init_raising(self: Any, *args: Any, **kwargs: Any) -> None:
        real_init(self, *args, **kwargs)

        class RaisingStore:
            def similarity_search(self, *search_args: Any, **search_kwargs: Any) -> list[Document]:
                raise RuntimeError("vector backend down")

        self._vector_store = RaisingStore()

    monkeypatch.setattr(HybridRetriever, "__init__", init_raising)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "ab_phase2_G2_pool.json").write_text("stale-pool", encoding="utf-8")
    assert (
        remote.stage_pools(
            "G2",
            tmp_path / "corpus",
            cases_path,
            out_dir,
            entities_cache=entities_dir,
            classifications=class_dir,
        )
        == 2
    )
    captured = capsys.readouterr().out
    assert "vector search returned no documents for case-1" in captured
    assert not (out_dir / "ab_phase2_G2_pool.json").exists()
    assert embeddings.embed_document_calls == 1


def test_rerank_exit_2_leaves_no_candidates_file(tmp_path: Path, capsys: Any) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    stale = out_dir / "ab_candidates_phase2_G2.json"
    stale.write_text("stale-cands", encoding="utf-8")
    assert remote.stage_rerank("G2", out_dir) == 2
    captured = capsys.readouterr().out
    assert "missing" in captured
    assert not stale.exists()


def test_rerank_missing_graph_sidecar_leaves_no_candidates(
    monkeypatch: Any, tmp_path: Path
) -> None:
    chunks = synthetic_chunks()
    cases = [_case()]
    cases_path = tmp_path / "cases.jsonl"
    digest = _write_cases(cases_path, cases)
    entities_dir = tmp_path / "entities"
    _write_extraction_cache(entities_dir, chunks, _entity_answer)
    class_dir = tmp_path / "classifications"
    _write_classifications(class_dir, cases, digest, {"case-1": _single_hop_route()})
    _install_pool_fakes(monkeypatch, chunks=chunks, embeddings=FakeEmbeddings())
    out_dir = tmp_path / "out"
    assert (
        remote.stage_pools(
            "G2",
            tmp_path / "corpus",
            cases_path,
            out_dir,
            entities_cache=entities_dir,
            classifications=class_dir,
        )
        == 0
    )
    (out_dir / "ab_phase2_G2_graph_chunks.json").unlink()
    stale = out_dir / "ab_candidates_phase2_G2.json"
    stale.write_text("stale-cands", encoding="utf-8")
    assert remote.stage_rerank("G2", out_dir) == 2
    assert not stale.exists()


def test_pools_run_removes_stale_candidates(monkeypatch: Any, tmp_path: Path) -> None:
    chunks = synthetic_chunks()
    cases = [_case()]
    cases_path = tmp_path / "cases.jsonl"
    digest = _write_cases(cases_path, cases)
    entities_dir = tmp_path / "entities"
    _write_extraction_cache(entities_dir, chunks, _entity_answer)
    class_dir = tmp_path / "classifications"
    _write_classifications(class_dir, cases, digest, {"case-1": _single_hop_route()})
    _install_pool_fakes(monkeypatch, chunks=chunks, embeddings=FakeEmbeddings())
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    stale = out_dir / "ab_candidates_phase2_G2.json"
    stale.write_text("stale-cands", encoding="utf-8")
    assert (
        remote.stage_pools(
            "G2",
            tmp_path / "corpus",
            cases_path,
            out_dir,
            entities_cache=entities_dir,
            classifications=class_dir,
        )
        == 0
    )
    assert not stale.exists()
    assert (out_dir / "ab_phase2_G2_pool.json").exists()

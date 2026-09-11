"""Tenant-scoped structural-graph wiring in the ingestion pipeline."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import ingestion.pipeline as pipeline_module
import vectordb.manager as tenant_manager
from ingestion.pipeline import IngestPipeline
from ingestion.structure_graph import StructuralGraph


class _RecordingRepository:
    def __init__(self) -> None:
        self.graphs: list[StructuralGraph] = []

    def replace(self, graph: StructuralGraph) -> None:
        self.graphs.append(graph)


def _source_document(source: str) -> Any:
    return tenant_manager.Document(
        page_content="Source content",
        metadata={"source": source},
    )


def _chunk(source: str) -> Any:
    return tenant_manager.Document(
        page_content="Chunk content",
        metadata={
            "source": source,
            "chunk_index": 0,
            "categories": ["shipping"],
            "h1": "Guide",
        },
    )


def _configure_pipeline(monkeypatch, tmp_path, repository):
    pipeline = IngestPipeline(
        log_path=tmp_path / "ingestion_log.json",
        structural_graph_repository=repository,
    )
    pipeline.loader = MagicMock()
    monkeypatch.setattr(
        pipeline_module,
        "annotate_documents_with_categories",
        lambda docs, tenant_id="default": {},
    )
    monkeypatch.setattr(pipeline_module, "log_graph_activation", lambda count: None)
    return pipeline


def test_ingest_replaces_tenant_structural_graph_after_vector_build(
    monkeypatch,
    tmp_path,
) -> None:
    repository = _RecordingRepository()
    pipeline = _configure_pipeline(monkeypatch, tmp_path, repository)
    pipeline.loader.load_documents.return_value = [_source_document("guide.md")]
    chunks = [_chunk("guide.md")]

    def _build_vector_store(docs, chunk_config, **kwargs):
        assert kwargs["tenant_id"] == "acme"
        assert repository.graphs == []
        return object(), chunks

    monkeypatch.setattr(tenant_manager, "build_vector_store", _build_vector_store)

    pipeline.ingest(tmp_path, tenant_id="acme")

    assert len(repository.graphs) == 1
    graph = repository.graphs[0]
    assert graph.tenant_id == "acme"
    assert {node.kind for node in graph.nodes} == {
        "category",
        "chunk",
        "document",
        "section",
    }


def test_add_document_replaces_graph_from_all_accumulated_chunks(
    monkeypatch,
    tmp_path,
) -> None:
    repository = _RecordingRepository()
    pipeline = _configure_pipeline(monkeypatch, tmp_path, repository)
    pipeline.loader.load_single_file.return_value = [_source_document("new.md")]
    chunks = [_chunk("existing.md"), _chunk("new.md")]

    def _build_vector_store(docs, chunk_config, **kwargs):
        assert kwargs["tenant_id"] == "beta"
        return object(), chunks

    monkeypatch.setattr(tenant_manager, "build_vector_store", _build_vector_store)

    pipeline.add_document(tmp_path / "new.md", tenant_id="beta")

    assert len(repository.graphs) == 1
    graph = repository.graphs[0]
    assert graph.tenant_id == "beta"
    assert {
        node.attributes["source"]
        for node in graph.nodes
        if node.kind == "document"
    } == {"existing.md", "new.md"}

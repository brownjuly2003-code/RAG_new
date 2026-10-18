"""The API's own index path cuts the chunks the measurements index (PLAN.md stage 1, item 4).

The new generation is built by the measurement path: ``scripts/corpus_chunks.py`` (the step
``chunks`` of ``scripts/external_base.py`` runs the same lines), then the embedding and index
scripts. Production updates an index through the upload path instead:
``api.app._rebuild_vector_store_from_docs`` → ``build_vector_store_with_publication``. The
numbers measured on the new generation hold for production only if both cut one corpus into
the same chunks. Here one corpus goes through both, with real Chroma and only the embedding
model a stand-in: each chunk's text and every metadata key the measurement writes must match,
and so must what a restarted API reads back from the published collection. The corpus holds a
section longer than a chunk (seams), a table longer than a chunk (column header repeated), a
heading path past the header's limit and a Russian document.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

pytest.importorskip("chromadb")
pytest.importorskip("langchain_chroma")

import numpy as np

from api import app as api_app
from config.settings import Settings
from ingestion.loader import DocumentLoader
from scripts import corpus_chunks, corpus_manifest
from vectordb import manager

TENANT = "parity"
# Pinned by the measurement path to keep the archive's SHA the same on any host.
HOST_FACTS = ("file_path", "mtime")


class FakeEmbeddings:
    def _vector(self, text: str) -> list[float]:
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        return np.random.default_rng(seed).standard_normal(32).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def _corpus(root: Path) -> None:
    root.mkdir()
    fees = " ".join(
        f"Storage fee clause {i} applies from the third day of storage." for i in range(40)
    )
    rows = "\n".join(f"| Zone {i} | {i * 7} kg | {i * 3} days |" for i in range(60))
    guide = (
        "# Guide\n\n## Fees\n\n" + fees + "\n\n## Rates\n\n"
        "| Zone | Weight | Transit |\n|---|---|---|\n" + rows + "\n"
    )
    deep = (
        "# Handling of dangerous goods carried as cargo on passenger and freighter aircraft\n\n"
        "## Packing instructions for lithium batteries shipped separately from equipment\n\n"
        "### Labels, marks and the documents that travel with each package to its destination\n\n"
        "#### The shipper's declaration\n\nThe shipper signs the declaration before acceptance.\n"
    )
    notes = "# Заметки\n\n## Сроки\n\nГруз принимают за сутки до вылета.\n"
    for name, text in (("guide.md", guide), ("deep.md", deep), ("notes.md", notes)):
        (root / name).write_bytes(text.encode("utf-8"))


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    import config.settings

    monkeypatch.setenv("ANONYMIZED_TELEMETRY", "False")
    settings = Settings()
    settings.vectordb_chroma_dir = tmp_path / "chroma"
    settings.vector_backend = "chroma"
    settings.graph_retrieval = "off"
    settings.reranker_model = ""
    settings.semantic_chunking = False
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(manager, "get_settings", lambda: settings)
    monkeypatch.setattr(api_app, "get_settings", lambda: settings)
    fake = FakeEmbeddings()
    monkeypatch.setattr(manager, "get_embeddings", lambda *args, **kwargs: fake)
    for name in ("_retriever_cache", "_chunks_cache", "_store_cache", "_index_cache_keys"):
        monkeypatch.setattr(manager, name, {})
    for name in ("_vector_store", "_retriever", "_chunks"):
        monkeypatch.setattr(api_app, name, getattr(api_app, name))
    return settings


def test_the_upload_path_indexes_the_chunks_the_measurement_path_cuts(
    configured: Settings, tmp_path: Path
) -> None:
    assert (configured.structural_chunking, configured.contextual_headers) == (True, True)
    root = tmp_path / "corpus"
    _corpus(root)
    manifest = tmp_path / "corpus.manifest.json"
    corpus_manifest.write_manifest(manifest, corpus_manifest.build_manifest(root, name="toy"))
    out = tmp_path / "out"
    corpus_chunks.build(root, manifest, TENANT, f"rag_docs_{TENANT}", "2026-10-18", out)
    measured = json.loads(gzip.decompress((out / "chunks.json.gz").read_bytes()))["chunks"]

    documents = DocumentLoader(recursive=False).load_documents(str(root))
    result = api_app._rebuild_vector_store_from_docs(documents, tenant_id=TENANT)

    assert result is not None and result.publication is not None
    published = result.chunks
    assert [chunk.page_content for chunk in published] == [c["page_content"] for c in measured]
    for index, (chunk, expected) in enumerate(zip(published, measured, strict=True)):
        # scripts/production_index.py stamps the position as the upload path does
        assert chunk.metadata["chunk_index"] == index
        for key, value in expected["metadata"].items():
            if key not in HOST_FACTS:
                assert chunk.metadata[key] == value, (index, key)

    # the corpus reaches what it is here for
    metadata = [c["metadata"] for c in measured]
    assert any(m.get("seam_overlap") for m in metadata)
    assert any(m.get("table_header_prefix") for m in metadata)
    assert any("…" in str(m.get("contextual_header")) for m in metadata)
    notes = [c["page_content"] for c in measured if c["metadata"]["source"] == "notes.md"]
    assert notes and notes[0].splitlines()[0].endswith("Заметки › Сроки]")

    # what a restarted API reads back from the published collection
    restored = manager._restore_chunks_from_store(result.store, TENANT)
    assert restored is not None
    assert [chunk.page_content for chunk in restored] == [c["page_content"] for c in measured]

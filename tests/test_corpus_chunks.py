"""scripts/corpus_chunks.py: any corpus directory chunked as the external bases' step does."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import corpus_chunks, corpus_manifest

FEES = "# Fees\n\n## Storage\n\nStorage costs ten a day after the third day.\n"
LEAVE = "# Leave\n\nLeave is booked a week ahead.\n"


@pytest.fixture
def corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    from config import settings as settings_module

    settings = SimpleNamespace(
        chunk_size=800,
        chunk_overlap=200,
        structural_chunking=True,
        semantic_chunking=False,
        contextual_headers=True,
    )
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)
    root = tmp_path / "corpus"
    root.mkdir()
    (root / "fees.md").write_bytes(FEES.encode("utf-8"))
    (root / "leave.md").write_bytes(LEAVE.encode("utf-8"))
    manifest = tmp_path / "corpus.manifest.json"
    corpus_manifest.write_manifest(manifest, corpus_manifest.build_manifest(root, name="toy"))
    return SimpleNamespace(root=root, manifest=manifest, out=tmp_path / "out")


def test_the_corpus_is_cut_headed_and_archived_the_same_on_any_host(
    corpus: SimpleNamespace,
) -> None:
    report = corpus_chunks.build(
        corpus.root, corpus.manifest, "toy", "rag_docs_toy", "2026-10-17", corpus.out
    )

    archive = (corpus.out / "chunks.json.gz").read_bytes()
    payload = json.loads(gzip.decompress(archive))
    assert report["archive_sha256"] == hashlib.sha256(archive).hexdigest()
    assert payload["tenant_id"] == "toy" == report["tenant"]
    assert report["collection"] == "rag_docs_toy"
    assert report["documents"] == 2 and report["chunks"] == len(payload["chunks"])
    assert report["chunking"]["chunk_size"] == 800
    fees = [c for c in payload["chunks"] if c["metadata"]["source"] == "fees.md"]
    assert fees[-1]["page_content"].startswith("[Fees › Storage]\n")
    assert all(c["metadata"]["mtime"] == "2026-10-17T00:00:00" for c in payload["chunks"])
    assert all(c["metadata"]["file_path"] == c["metadata"]["source"] for c in payload["chunks"])
    again = corpus_chunks.build(
        corpus.root, corpus.manifest, "toy", "rag_docs_toy", "2026-10-17", corpus.out
    )
    assert {**again, "seconds": None} == {**report, "seconds": None}
    written = json.loads((corpus.out / "chunks-report.json").read_text(encoding="utf-8"))
    assert written == again


def test_a_corpus_that_differs_from_its_manifest_is_refused(corpus: SimpleNamespace) -> None:
    (corpus.root / "leave.md").write_bytes(LEAVE.replace("week", "month").encode("utf-8"))

    with pytest.raises(ValueError, match="differs from its manifest"):
        corpus_chunks.build(
            corpus.root, corpus.manifest, "toy", "rag_docs_toy", "2026-10-17", corpus.out
        )
    assert not corpus.out.exists()

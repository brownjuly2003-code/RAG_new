"""A scratch baseline index requires a complete, pinned embedding checkpoint."""

import gzip
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
import pytest

from scripts.production_embeddings import prepare_embeddings
from vectordb.embedder_manifest import EmbedderManifest


@pytest.fixture
def inputs(tmp_path):
    class Embedder:
        manifest = EmbedderManifest(
            backend="local", model_id="fixture", revision="a" * 40,
            revision_source="hf_snapshot", dimension=2, query_prompt="",
            document_prompt="", normalize=True,
        )

        def embed_documents(self, texts):
            return [[1.0, 0.0], [0.0, 1.0]][:len(texts)]

    chunks = [
        {"page_content": "cargo one", "metadata": {"source": "one.md", "section": "A"}},
        {"page_content": "cargo two", "metadata": {"source": "two.md", "section": "B"}},
    ]
    archive = tmp_path / "chunks.json.gz"
    archive.write_bytes(gzip.compress(json.dumps({"chunks": chunks}).encode()))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checkpoint = tmp_path / "vectors.npz"
    prepare_embeddings(
        [chunk["page_content"] for chunk in chunks], Embedder(), checkpoint,
        corpus_sha256=digest,
    )
    return dict(
        archive=archive, checkpoint=checkpoint, output=tmp_path / "index",
        archive_sha256=digest, expected_manifest=Embedder.manifest, code_sha="b" * 40,
    )


@pytest.mark.parametrize("damage", [
    "partial", "corpus", "texts", "revision", "schema", "unverified", "nan", "norm", "width",
])
def test_invalid_checkpoint_cannot_create_index(inputs, damage):
    from scripts.production_index import build_index

    checkpoint = inputs["checkpoint"]
    with np.load(checkpoint, allow_pickle=False) as saved:
        payload = dict(saved)
    if damage == "partial":
        payload["embeddings"] = payload["embeddings"][:1]
    elif damage in {"corpus", "texts"}:
        payload[damage + "_sha256"] = "0" * 64
    elif damage == "schema":
        payload["schema_version"] = 2
    elif damage in {"revision", "unverified"}:
        manifest = json.loads(str(payload["embedder_manifest"]))
        manifest["revision" if damage == "revision" else "revision_source"] = (
            "c" * 40 if damage == "revision" else "unresolved"
        )
        payload["embedder_manifest"] = json.dumps(manifest)
    elif damage == "width":
        payload["embeddings"] = np.ones((2, 3))
    else:
        payload["embeddings"][0, 0] = float("nan") if damage == "nan" else 2.0
    np.savez(checkpoint, **payload)
    before = checkpoint.read_bytes()
    with pytest.raises(ValueError):
        build_index(**inputs)
    assert not inputs["output"].exists()
    assert checkpoint.read_bytes() == before


def test_wrong_archive_is_refused_before_creating_output(inputs):
    from scripts.production_index import build_index

    inputs["archive_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="archive"):
        build_index(**inputs)
    assert not inputs["output"].exists()


def test_existing_directory_is_never_reused(inputs):
    from scripts.production_index import build_index

    inputs["output"].mkdir()
    sentinel = inputs["output"] / "keep"
    sentinel.write_text("existing index", encoding="utf-8")
    with pytest.raises(FileExistsError):
        build_index(**inputs)
    assert list(inputs["output"].iterdir()) == [sentinel]
    assert sentinel.read_text(encoding="utf-8") == "existing index"


def test_real_chroma_reopens_with_exact_vectors_metadata_and_manifest(inputs):
    from scripts.production_index import build_index

    report = build_index(**inputs)
    assert report["chunk_count"] == 2
    assert report["checkpoint_sha256"] == hashlib.sha256(inputs["checkpoint"].read_bytes()).hexdigest()
    assert report["corpus_sha256"] == inputs["archive_sha256"]
    assert report["code_sha"] == inputs["code_sha"]
    assert report["embedder_manifest"] == inputs["expected_manifest"].as_dict()
    assert json.loads((inputs["output"] / "index-receipt.json").read_text()) == report
    script = """
import json, sys
import chromadb
client = chromadb.PersistentClient(path=sys.argv[1])
collection = client.get_collection('rag_docs_aircargo', embedding_function=None)
assert collection.count() == 2
rows = collection.get(include=['documents', 'metadatas', 'embeddings'])
ordered = sorted(zip(rows['documents'], rows['metadatas'], rows['embeddings']), key=lambda r: r[1]['chunk_index'])
assert [r[0] for r in ordered] == ['cargo one', 'cargo two']
assert [r[1]['source'] for r in ordered] == ['one.md', 'two.md']
assert [r[1]['section'] for r in ordered] == ['A', 'B']
assert [r[2].tolist() for r in ordered] == [[1.0, 0.0], [0.0, 1.0]]
assert json.loads(collection.metadata['embedder_manifest']) == json.loads(sys.argv[2])
assert collection.query(query_embeddings=[[0.0, 1.0]], n_results=1)['documents'] == [['cargo two']]
print('REOPEN_OK')
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(inputs["output"] / "chroma"),
         inputs["expected_manifest"].canonical_json],
        capture_output=True, text=True, timeout=60,
        env=dict(os.environ, ANONYMIZED_TELEMETRY="False"),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "REOPEN_OK" in result.stdout

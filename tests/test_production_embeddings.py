"""A resumable real-model cache must never inherit an unverified identity."""

import hashlib
from dataclasses import replace

import numpy as np
import pytest

from vectordb.embedder_manifest import EmbedderManifest

CORPUS = "c" * 64
TEXTS = ["one", "two", "three", "four", "five"]


class Embedder:
    manifest = EmbedderManifest(
        backend="local", model_id="fixture", revision="a" * 40,
        revision_source="hf_snapshot", dimension=2, query_prompt="",
        document_prompt="", normalize=True,
    )

    def __init__(self):
        self.calls = []

    def embed_documents(self, texts):
        self.calls.append(list(texts))
        return [[1.0, 0.0] for _ in texts]


def test_bounded_checkpoint_resumes_without_reencoding(tmp_path):
    from scripts.production_embeddings import prepare_embeddings

    model = Embedder()
    output = tmp_path / "vectors.npz"
    first = prepare_embeddings(
        TEXTS, model, output, corpus_sha256=CORPUS, batch_size=2, max_batches=1,
    )
    assert first["completed_rows"] == 2
    assert first["complete"] is False
    second = prepare_embeddings(
        TEXTS, model, output, corpus_sha256=CORPUS, batch_size=2, resume=True,
    )
    assert second["complete"] is True
    assert second["completed_rows"] == second["total_rows"] == 5
    assert model.calls == [TEXTS[:2], TEXTS[2:4], TEXTS[4:]]
    assert second["checkpoint_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert second["embedder_manifest"] == model.manifest.as_dict()
    assert prepare_embeddings(
        TEXTS, model, output, corpus_sha256=CORPUS, resume=True,
    ) == second
    assert len(model.calls) == 3


@pytest.mark.parametrize("change", ["corpus", "texts", "revision", "prompt", "normalize"])
def test_resume_refuses_changed_identity_without_touching_checkpoint(tmp_path, change):
    from scripts.production_embeddings import prepare_embeddings

    model = Embedder()
    output = tmp_path / "vectors.npz"
    prepare_embeddings(TEXTS, model, output, corpus_sha256=CORPUS, max_batches=1, batch_size=2)
    original = output.read_bytes()
    corpus, texts = CORPUS, TEXTS
    if change == "corpus":
        corpus = "d" * 64
    elif change == "texts":
        texts = list(reversed(TEXTS))
    elif change == "revision":
        model.manifest = replace(model.manifest, revision="b" * 40)
    elif change == "prompt":
        model.manifest = replace(model.manifest, document_prompt="passage: ")
    else:
        model.manifest = replace(model.manifest, normalize=False)
    with pytest.raises(ValueError):
        prepare_embeddings(texts, model, output, corpus_sha256=corpus, resume=True)
    assert model.calls == [TEXTS[:2]]
    assert output.read_bytes() == original


def test_existing_output_needs_explicit_resume(tmp_path):
    from scripts.production_embeddings import prepare_embeddings

    output = tmp_path / "legacy.npz"
    output.write_bytes(b"legacy cache must be preserved")
    model = Embedder()
    with pytest.raises((ValueError, FileExistsError)):
        prepare_embeddings(TEXTS, model, output, corpus_sha256=CORPUS)
    with pytest.raises(ValueError):
        prepare_embeddings(TEXTS, model, output, corpus_sha256=CORPUS, resume=True)
    assert not model.calls
    assert output.read_bytes() == b"legacy cache must be preserved"


@pytest.mark.parametrize("bad", [[[float("nan"), 0.0]], [[2.0, 0.0]], [[1.0]], []])
def test_bad_model_batch_preserves_last_valid_checkpoint(tmp_path, bad):
    from scripts.production_embeddings import prepare_embeddings

    class FailingEmbedder(Embedder):
        def embed_documents(self, texts):
            if self.calls:
                return bad
            return super().embed_documents(texts)

    model = FailingEmbedder()
    output = tmp_path / "vectors.npz"
    prepare_embeddings(TEXTS, model, output, corpus_sha256=CORPUS, batch_size=1, max_batches=1)
    before = output.read_bytes()
    with pytest.raises(ValueError):
        prepare_embeddings(TEXTS, model, output, corpus_sha256=CORPUS, batch_size=1, resume=True)
    assert output.read_bytes() == before


@pytest.mark.parametrize("field,value", [
    ("revision", None), ("revision_source", "unresolved"), ("backend", "remote"),
])
def test_unverified_model_cannot_start_cache(tmp_path, field, value):
    from scripts.production_embeddings import prepare_embeddings

    model = Embedder()
    model.manifest = replace(model.manifest, **{field: value})
    output = tmp_path / "vectors.npz"
    with pytest.raises(ValueError):
        prepare_embeddings(TEXTS, model, output, corpus_sha256=CORPUS)
    assert not model.calls
    assert not output.exists()


def test_corrupt_checkpoint_matrix_is_not_used(tmp_path):
    from scripts.production_embeddings import prepare_embeddings

    model = Embedder()
    output = tmp_path / "vectors.npz"
    prepare_embeddings(TEXTS, model, output, corpus_sha256=CORPUS, batch_size=1, max_batches=1)
    with np.load(output, allow_pickle=False) as data:
        payload = dict(data)
    payload["embeddings"] = np.array([[float("inf"), 0]])
    np.savez(output, **payload)
    before = output.read_bytes()
    with pytest.raises(ValueError):
        prepare_embeddings(TEXTS, model, output, corpus_sha256=CORPUS, resume=True)
    assert len(model.calls) == 1
    assert output.read_bytes() == before


def test_cli_rejects_wrong_archive_before_model_load(tmp_path):
    from scripts.production_embeddings import main

    archive = tmp_path / "chunks.json.gz"
    archive.write_bytes(b"not the pinned corpus")
    with pytest.raises((ValueError, SystemExit)):
        main([
            "--archive", str(archive), "--archive-sha256", CORPUS,
            "--output", str(tmp_path / "vectors.npz"), "--revision", "a" * 40,
        ])
    assert not (tmp_path / "vectors.npz").exists()

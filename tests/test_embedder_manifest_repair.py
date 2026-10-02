"""T-61 repair regressions using real retrievers and Chroma metadata semantics."""

from types import SimpleNamespace

import pytest

from tests.test_embedder_manifest import _manifest, _store
from tests.test_embedder_manifest import _stop_chroma_systems as _stop_chroma_systems


def test_embedder_manifest_plain_vector_retriever_registry(monkeypatch, tmp_path):
    pytest.importorskip("langchain_core")
    from langchain_core.vectorstores import VectorStore, VectorStoreRetriever

    import config.settings
    from vectordb import manager

    class Store(VectorStore):
        def __init__(self):
            self._collection = _store(_manifest())._collection

        @classmethod
        def from_texts(cls, texts, embedding, metadatas=None, **kwargs):
            return cls()

        def similarity_search(self, query, k=4, **kwargs):
            return []

    settings = SimpleNamespace(
        vector_backend="chroma",
        vectordb_chroma_dir=tmp_path,
        graph_retrieval="off",
        retrieval_strategy="vector",
        retrieval_top_k=20,
        rerank_top_k=5,
        hybrid_search=False,
        reranker_model=None,
        parent_expansion=False,
    )
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(manager, "get_settings", lambda: settings)
    for name in ("_retriever_cache", "_store_cache", "_chunks_cache", "_index_cache_keys"):
        monkeypatch.setattr(manager, name, {})
    embedder = SimpleNamespace(manifest=_manifest(), embedding_dimension=1024)
    retriever = manager.get_retriever(Store(), chunks=[], embeddings=embedder, tenant_id="tenant-a")
    assert isinstance(retriever, VectorStoreRetriever)
    assert manager.get_index_manifest_status("tenant-a")["status"] == "match"
    assert manager.get_index_manifest_status("tenant-b") is None
    manager.get_retriever(Store(), chunks=[], embeddings=embedder, tenant_id="tenant-b")
    # The cached path recomputes the registry entry without touching the retriever.
    manager._index_manifest_status.pop("tenant-a")
    assert manager.get_retriever(embeddings=embedder, tenant_id="tenant-a") is retriever
    assert manager.get_index_manifest_status("tenant-a")["status"] == "match"
    manager.reset_retriever_cache("tenant-a")
    assert manager.get_index_manifest_status("tenant-a") is None
    assert manager.get_index_manifest_status("tenant-b")["status"] == "match"
    manager.reset_retriever_cache()
    assert manager.get_index_manifest_status("tenant-b") is None


@pytest.mark.parametrize(
    "changes,status,reason",
    [
        ({"revision": None, "revision_source": "unresolved"}, "unverified", "revision_unresolved"),
        (
            {
                "backend": "remote",
                "model_id": "mistral-embed",
                "revision": None,
                "revision_source": "remote_unversioned",
            },
            "unverified",
            "remote_unversioned",
        ),
        (
            {"revision": "short", "revision_source": "hf_snapshot"},
            "unverified",
            "revision_unresolved",
        ),
        ({}, "match", None),
    ],
)
def test_embedder_manifest_evidence_requires_resolved_revision(changes, status, reason):
    from vectordb.embedder_manifest import check_collection_manifest

    manifest = _manifest(**changes)
    result = check_collection_manifest(_store(manifest), SimpleNamespace(manifest=manifest))
    assert result["status"] == status
    assert result.get("reason") == reason
    assert result["evidence_status"] == ("eligible" if status == "match" else "NOT_EVIDENCE")


@pytest.mark.parametrize("reverse", [False, True])
def test_embedder_manifest_resolved_against_null_refuses(reverse):
    from vectordb.embedder_manifest import EmbedderManifestMismatch, check_collection_manifest

    manifests = [_manifest(), _manifest(revision=None, revision_source="unresolved")]
    if reverse:
        manifests.reverse()
    with pytest.raises(EmbedderManifestMismatch):
        check_collection_manifest(_store(manifests[0]), SimpleNamespace(manifest=manifests[1]))


def _real_chroma_store(tmp_path):
    chromadb = pytest.importorskip("chromadb")
    client = chromadb.PersistentClient(path=str(tmp_path))

    class Store:
        def __init__(self, **kwargs):
            self._collection = client.get_or_create_collection(
                name=kwargs["collection_name"],
                metadata=kwargs.get("collection_metadata"),
                configuration=kwargs.get("collection_configuration"),
                embedding_function=None,
            )

        @classmethod
        def from_documents(cls, **kwargs):
            store = cls(**kwargs)
            store.add_documents(kwargs["documents"])
            return store

        def add_documents(self, documents):
            start = self._collection.count()
            self._collection.add(
                ids=[f"record-{start + i}" for i in range(len(documents))],
                documents=[doc.page_content for doc in documents],
                embeddings=[[1.0] + [0.0] * 1023 for _ in documents],
            )

        def similarity_search(self, query, **kwargs):
            return [SimpleNamespace(page_content="Seed policy.")]

        def delete_collection(self):
            client.delete_collection(self._collection.name)

    return Store


@pytest.mark.parametrize("entrypoint", ["legacy", "factcards", "staged"])
@pytest.mark.parametrize("initial", ["new", "legacy", "empty", "match", "mismatch"])
def test_embedder_manifest_every_write_checks_before_add(
    monkeypatch, tmp_path, entrypoint, initial
):
    import config.settings
    from tests.test_index_staging import _held_tenant_lock
    from vectordb import manager
    from vectordb.embedder_manifest import MANIFEST_METADATA_KEY, EmbedderManifestMismatch
    from vectordb.index_staging import build_staged_collection, staged_collection_name

    chroma = _real_chroma_store(tmp_path / "real-chroma")
    settings = SimpleNamespace(
        vector_backend="chroma",
        vectordb_chroma_dir=tmp_path,
        vectordb_collection_prefix="rag_docs",
    )
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(manager, "get_settings", lambda: settings)
    monkeypatch.setattr(manager, "_get_chroma", lambda: chroma)
    monkeypatch.setattr(manager._base_manager, "_load_chroma", lambda: chroma)
    monkeypatch.setattr(manager._base_manager, "_data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        manager, "tenant_index_lock", lambda tenant: _held_tenant_lock(monkeypatch, tenant)
    )
    candidate_id = "1" * 16
    name = {
        "legacy": "documents",
        "factcards": manager._factcard_collection_name("default"),
        "staged": staged_collection_name("default", candidate_id=candidate_id),
    }[entrypoint]
    doc = SimpleNamespace(page_content="Seed policy.", metadata={"source": "policy.md"})
    embedder = SimpleNamespace(manifest=_manifest(), embed_query=lambda text: [1.0] + [0.0] * 1023)
    if initial != "new":
        stored_manifest = (
            _manifest(model_id="other-model") if initial == "mismatch" else _manifest()
        )
        seed = chroma(
            collection_name=name,
            collection_metadata={MANIFEST_METADATA_KEY: stored_manifest.canonical_json}
            if initial in ("match", "mismatch")
            else None,
        )
        if initial != "empty":
            seed.add_documents([doc])
    before = 0 if initial in ("new", "empty") else 1

    def build():
        if entrypoint == "legacy":
            return manager._base_manager._build_chroma([doc], embedder)
        if entrypoint == "factcards":
            return manager.build_factcard_store([doc], embeddings=embedder)
        with _held_tenant_lock(monkeypatch, "default") as token:
            return build_staged_collection(
                [doc],
                embedder,
                tenant_id="default",
                lock_token=token,
                chroma_cls=chroma,
                chroma_directory=tmp_path,
                candidate_id=candidate_id,
            ).store

    if initial == "mismatch" and entrypoint != "factcards":
        with pytest.raises(EmbedderManifestMismatch):
            build()
        assert seed._collection.count() == before
        assert seed._collection.metadata[MANIFEST_METADATA_KEY] == stored_manifest.canonical_json
        return
    result = build()
    assert result._collection.count() == (1 if entrypoint == "factcards" else before + 1)
    metadata = result._collection.metadata or {}
    if initial == "legacy" and entrypoint != "factcards":
        assert MANIFEST_METADATA_KEY not in metadata
    else:
        assert metadata[MANIFEST_METADATA_KEY] == _manifest().canonical_json


@pytest.mark.parametrize("real", [False, True])
def test_embedder_manifest_staged_creation_persists_config_and_stamp(monkeypatch, tmp_path, real):
    from tests.test_embedder_manifest import _creating_chroma
    from tests.test_index_staging import _held_tenant_lock
    from vectordb.embedder_manifest import MANIFEST_METADATA_KEY
    from vectordb.index_staging import build_staged_collection

    base = _real_chroma_store(tmp_path) if real else _creating_chroma({})
    creations = []

    class Chroma(base):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            if self._collection.count() == 0:
                creations.append(kwargs)

    embedder = SimpleNamespace(manifest=_manifest(), embed_query=lambda text: [1.0] * 1024)
    with _held_tenant_lock(monkeypatch, "default") as token:
        candidate = build_staged_collection(
            [SimpleNamespace(page_content="Seed policy.")],
            embedder,
            tenant_id="default",
            lock_token=token,
            chroma_cls=Chroma,
            chroma_directory=tmp_path,
            candidate_id="2" * 16,
        )
    # from_documents reopens the collection: only the first constructor creates it.
    assert creations[0]["collection_configuration"] == {"hnsw": {"sync_threshold": 1}}
    assert creations[0]["collection_metadata"] == {
        MANIFEST_METADATA_KEY: _manifest().canonical_json
    }
    assert sum("collection_metadata" in call for call in creations) == 1
    collection = candidate.store._collection
    assert collection.metadata[MANIFEST_METADATA_KEY] == _manifest().canonical_json
    if real:
        assert collection.configuration["hnsw"]["sync_threshold"] == 1


def test_embedder_manifest_staged_creation_failure_cleans_and_wraps(monkeypatch, tmp_path):
    from tests.test_index_staging import _held_tenant_lock
    from vectordb import index_staging

    failure = RuntimeError("creation failed")
    cleanups = []

    class Chroma:
        def __init__(self, **kwargs):
            raise failure

    monkeypatch.setattr(
        index_staging, "_cleanup_candidate", lambda **kwargs: cleanups.append(kwargs)
    )
    with _held_tenant_lock(monkeypatch, "default") as token:
        with pytest.raises(index_staging.IndexStagingBuildError) as raised:
            index_staging.build_staged_collection(
                [SimpleNamespace(page_content="Seed policy.")],
                SimpleNamespace(manifest=_manifest()),
                tenant_id="default",
                lock_token=token,
                chroma_cls=Chroma,
                chroma_directory=tmp_path,
                candidate_id="3" * 16,
            )
    assert raised.value.__cause__ is failure
    assert len(cleanups) == 1
    assert cleanups[0]["collection_name"].endswith("3" * 16)


def test_embedder_manifest_staged_existing_mismatch_never_cleans(monkeypatch, tmp_path):
    from tests.test_index_staging import _held_tenant_lock
    from vectordb import index_staging
    from vectordb.embedder_manifest import EmbedderManifestMismatch

    cleanups = []
    collection = _store(_manifest(model_id="other-model"))._collection

    class Chroma:
        def __init__(self, **kwargs):
            self._collection = collection

    monkeypatch.setattr(
        index_staging, "_cleanup_candidate", lambda **kwargs: cleanups.append(kwargs)
    )
    with _held_tenant_lock(monkeypatch, "default") as token:
        with pytest.raises(EmbedderManifestMismatch):
            index_staging.build_staged_collection(
                [SimpleNamespace(page_content="Seed policy.")],
                SimpleNamespace(manifest=_manifest()),
                tenant_id="default",
                lock_token=token,
                chroma_cls=Chroma,
                chroma_directory=tmp_path,
                candidate_id="4" * 16,
            )
    assert cleanups == []
    assert collection.count() == 1


def test_embedder_manifest_unidentified_leaves_creation_to_from_documents():
    from vectordb.embedder_manifest import open_chroma_for_write

    def constructor(**kwargs):
        pytest.fail("Unidentified embedder must not precreate the collection")

    assert open_chroma_for_write(constructor, object(), collection_name="candidate") is None


def test_embedder_manifest_staged_partial_creation_is_deleted(monkeypatch, tmp_path):
    chromadb = pytest.importorskip("chromadb")
    from tests.test_index_staging import _held_tenant_lock
    from vectordb.index_staging import (
        IndexStagingBuildError,
        build_staged_collection,
        staged_collection_name,
    )

    base = _real_chroma_store(tmp_path)
    failure = RuntimeError("failed after collection creation")

    class Chroma(base):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            if "collection_metadata" in kwargs:
                raise failure

    candidate_id = "5" * 16
    with _held_tenant_lock(monkeypatch, "default") as token:
        with pytest.raises(IndexStagingBuildError) as raised:
            build_staged_collection(
                [SimpleNamespace(page_content="Seed policy.")],
                SimpleNamespace(manifest=_manifest()),
                tenant_id="default",
                lock_token=token,
                chroma_cls=Chroma,
                chroma_directory=tmp_path,
                candidate_id=candidate_id,
            )
    assert raised.value.__cause__ is failure
    client = chromadb.PersistentClient(path=str(tmp_path))
    with pytest.raises(chromadb.errors.NotFoundError):
        client.get_collection(staged_collection_name("default", candidate_id=candidate_id))

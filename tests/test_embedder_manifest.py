"""Embedder identity regression tests for T-61."""

from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def _stop_chroma_systems():
    yield
    import sys

    if "chromadb" in sys.modules:
        from chromadb.api.shared_system_client import SharedSystemClient

        for system in list(SharedSystemClient._identifier_to_system.values()):
            system.stop()
        SharedSystemClient.clear_system_cache()


def _manifest(**changes):
    from dataclasses import replace

    from vectordb.embedder_manifest import EmbedderManifest

    return replace(
        EmbedderManifest(
            backend="local",
            model_id="BAAI/bge-m3",
            revision="a" * 40,
            revision_source="hf_snapshot",
            dimension=1024,
            query_prompt="",
            document_prompt="",
            normalize=True,
        ),
        **changes,
    )


def _store(manifest):
    from vectordb.embedder_manifest import MANIFEST_METADATA_KEY

    class Collection:
        def __init__(self):
            self.metadata = {"existing": "preserved"}

        def modify(self, *, metadata):
            self.metadata = metadata

        def get(self, **kwargs):
            assert kwargs == {"limit": 1, "include": ["embeddings"]}
            return {"embeddings": [[0.0] * 1024]}

        def count(self):
            return 1

    collection = Collection()
    if manifest is not None:
        collection.metadata = {MANIFEST_METADATA_KEY: manifest.canonical_json}
    return SimpleNamespace(_collection=collection)


@pytest.mark.parametrize(
    "changes,fields",
    [
        ({"revision": "b" * 40}, ["revision"]),
        ({"query_prompt": "query: "}, ["query_prompt"]),
        ({"document_prompt": "passage: "}, ["document_prompt"]),
        ({"normalize": False}, ["normalize"]),
        ({"revision": None}, ["revision"]),
        (
            {
                "backend": "remote",
                "model_id": "mistral-embed",
                "revision": None,
                "revision_source": "remote_unversioned",
            },
            ["backend", "model_id", "revision", "revision_source"],
        ),
    ],
)
def test_embedder_manifest_refuses_before_restore_and_only_evicts_its_tenant(
    monkeypatch, tmp_path, changes, fields
):
    from vectordb import manager
    from vectordb.embedder_manifest import EmbedderManifestMismatch

    configured = _manifest(**changes)
    store = _store(_manifest())
    monkeypatch.setattr(
        manager,
        "get_settings",
        lambda: SimpleNamespace(
            vector_backend="chroma", vectordb_chroma_dir=tmp_path, graph_retrieval="off"
        ),
    )
    for name in ("_retriever_cache", "_chunks_cache", "_store_cache", "_index_cache_keys"):
        monkeypatch.setattr(manager, name, {"tenant-a": object()})
    monkeypatch.setattr(manager, "_restore_chunks_from_store", lambda *args: pytest.fail("restore"))
    with pytest.raises(EmbedderManifestMismatch) as caught:
        manager.get_retriever(
            vector_store=store,
            tenant_id="tenant-b",
            embeddings=SimpleNamespace(manifest=configured, embedding_dimension=1024),
        )
    assert caught.value.mismatched_fields == fields
    assert caught.value.stored == _manifest().as_dict()
    assert caught.value.configured == configured.as_dict()
    for name in ("_retriever_cache", "_chunks_cache", "_store_cache", "_index_cache_keys"):
        assert set(getattr(manager, name)) == {"tenant-a"}


@pytest.mark.parametrize("stamped,status", [(True, "match"), (False, "unstamped")])
def test_embedder_manifest_matching_or_legacy_loads(monkeypatch, tmp_path, stamped, status, caplog):
    from vectordb import manager

    store = _store(_manifest() if stamped else None)
    before = dict(store._collection.metadata)
    monkeypatch.setattr(
        manager,
        "get_settings",
        lambda: SimpleNamespace(
            vector_backend="chroma", vectordb_chroma_dir=tmp_path, graph_retrieval="off"
        ),
    )
    for name in ("_retriever_cache", "_chunks_cache", "_store_cache", "_index_cache_keys"):
        monkeypatch.setattr(manager, name, {})
    monkeypatch.setattr(
        manager._base_manager, "get_retriever", lambda *args, **kwargs: SimpleNamespace()
    )
    embedder = SimpleNamespace(manifest=_manifest(), embedding_dimension=1024)
    manager.get_retriever(vector_store=store, chunks=[], embeddings=embedder)
    assert manager.get_index_manifest_status("default")["status"] == status
    assert store._collection.metadata == before
    if not stamped:
        assert manager.get_index_manifest_status("default")["evidence_status"] == "NOT_EVIDENCE"
        manager.get_retriever(embeddings=embedder)
        assert sum("unstamped" in record.message for record in caplog.records) == 1


def test_embedder_manifest_stamp_canonical_and_preserves_metadata():
    import hashlib
    import json

    from vectordb.embedder_manifest import MANIFEST_METADATA_KEY, stamp_collection

    manifest = _manifest()
    store = _store(None)
    store._collection.count = lambda: 0
    stamp_collection(store, SimpleNamespace(manifest=manifest))
    encoded = store._collection.metadata[MANIFEST_METADATA_KEY]
    assert encoded == json.dumps(manifest.as_dict(), sort_keys=True, separators=(",", ":"))
    assert manifest.sha256 == hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    assert store._collection.metadata["existing"] == "preserved"


def test_embedder_manifest_remote_has_no_credentials():
    from vectordb._base_manager import _RemoteEmbeddings

    embedder = _RemoteEmbeddings(
        url="https://secret.invalid/?key=secret",
        model="mistral-embed",
        api_key="secret",
        batch_size=2,
        timeout_sec=1,
    )
    assert embedder.manifest == _manifest(
        backend="remote",
        model_id="mistral-embed",
        revision=None,
        revision_source="remote_unversioned",
    )
    assert "secret" not in embedder.manifest.canonical_json


def test_embedder_manifest_unidentified_and_unsupported():
    from vectordb.embedder_manifest import check_collection_manifest

    assert check_collection_manifest(_store(_manifest()), object())["status"] == "unidentified"
    assert (
        check_collection_manifest(None, object(), backend="qdrant")["status"]
        == "unsupported_backend"
    )


def test_embedder_manifest_staging_publish_and_rollback_keep_stamp(monkeypatch, tmp_path):
    from tests.test_index_staging import _held_tenant_lock
    from vectordb.embedder_manifest import MANIFEST_METADATA_KEY
    from vectordb.index_manifest import publish_active_collection, rollback_active_collection
    from vectordb.index_staging import build_staged_collection

    stores = {}

    class Chroma(_creating_chroma(stores)):
        @classmethod
        def from_documents(cls, **kwargs):
            assert set(kwargs) == {
                "documents",
                "embedding",
                "persist_directory",
                "collection_name",
                "collection_configuration",
            }
            assert kwargs["collection_configuration"] == {"hnsw": {"sync_threshold": 1}}
            return super().from_documents(**kwargs)

    doc = SimpleNamespace(page_content="Seed policy.")
    embeddings = SimpleNamespace(manifest=_manifest(), embed_query=lambda text: [0.0] * 1024)
    with _held_tenant_lock(monkeypatch, "default") as token:
        candidates = [
            build_staged_collection(
                [doc],
                embeddings,
                tenant_id="default",
                lock_token=token,
                chroma_cls=Chroma,
                chroma_directory=tmp_path,
                candidate_id=f"{i:016x}",
            )
            for i in (1, 2)
        ]
        for candidate in candidates:
            publish_active_collection(
                "default", candidate.collection_name, lock_token=token, chroma_directory=tmp_path
            )
        result = rollback_active_collection("default", lock_token=token, chroma_directory=tmp_path)
    assert result.active_collection == candidates[0].collection_name
    for store in stores.values():
        assert store._collection.metadata[MANIFEST_METADATA_KEY] == _manifest().canonical_json


@pytest.mark.parametrize("revision", [None, "main"])
def test_embedder_manifest_local_loaded_snapshot_and_default_prompt(
    monkeypatch, tmp_path, revision
):
    import sys

    import config.settings
    from vectordb import _base_manager

    snapshot = tmp_path / "models--BAAI--bge-m3" / "snapshots" / ("b" * 40)
    snapshot.mkdir(parents=True)
    calls = []
    model = SimpleNamespace(
        default_prompt_name="query",
        prompts={"query": "query: "},
        get_sentence_embedding_dimension=lambda: 1024,
        _modules={"0": SimpleNamespace(tokenizer=SimpleNamespace(name_or_path=str(snapshot)))},
    )

    def constructor(name, **kwargs):
        calls.append((name, kwargs))
        return model

    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=constructor)
    )
    monkeypatch.setattr(_base_manager, "_cached_embeddings", None)
    monkeypatch.setattr(_base_manager, "_resolve_device", lambda: "cpu")
    monkeypatch.setattr(
        config.settings,
        "get_settings",
        lambda: SimpleNamespace(
            embedding_backend="local",
            embedding_model="BAAI/bge-m3",
            embedding_model_revision=revision,
        ),
    )
    embeddings = _base_manager.get_embeddings()
    assert calls == [
        ("BAAI/bge-m3", {"device": "cpu", **({"revision": revision} if revision else {})})
    ]
    assert embeddings.manifest == _manifest(
        revision="b" * 40, query_prompt="query: ", document_prompt="query: "
    )


def test_embedder_manifest_unresolved_revision_is_not_guessed(monkeypatch):
    import sys

    import config.settings
    from vectordb import _base_manager

    model = SimpleNamespace(get_sentence_embedding_dimension=lambda: 1024, _modules={})
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=lambda name, **kwargs: model),
    )
    monkeypatch.setattr(_base_manager, "_cached_embeddings", None)
    monkeypatch.setattr(_base_manager, "_resolve_device", lambda: "cpu")
    monkeypatch.setattr(
        config.settings,
        "get_settings",
        lambda: SimpleNamespace(
            embedding_backend="local",
            embedding_model="BAAI/bge-m3",
            embedding_model_revision="a" * 40,
        ),
    )
    assert _base_manager.get_embeddings().manifest.revision is None


def test_embedder_manifest_empty_default_prompt_name_records_applied_prompt():
    from vectordb.embedder_manifest import local_manifest

    model = SimpleNamespace(default_prompt_name="", prompts={"": "query: "}, _modules={})
    manifest = local_manifest(model, "BAAI/bge-m3", 1024)
    assert manifest.query_prompt == manifest.document_prompt == "query: "


def test_embedder_manifest_same_dimension_substitution_refused():
    from vectordb.embedder_manifest import (
        MANIFEST_METADATA_KEY,
        EmbedderManifest,
        EmbedderManifestMismatch,
        check_collection_manifest,
    )

    stored = EmbedderManifest(
        backend="local",
        model_id="BAAI/bge-m3",
        revision="a" * 40,
        revision_source="hf_snapshot",
        dimension=1024,
        query_prompt="",
        document_prompt="",
        normalize=True,
    )
    configured = EmbedderManifest(
        backend="remote",
        model_id="mistral-embed",
        revision=None,
        revision_source="remote_unversioned",
        dimension=1024,
        query_prompt="",
        document_prompt="",
        normalize=True,
    )
    store = SimpleNamespace(
        _collection=SimpleNamespace(metadata={MANIFEST_METADATA_KEY: stored.canonical_json})
    )
    with pytest.raises(EmbedderManifestMismatch) as caught:
        check_collection_manifest(store, SimpleNamespace(manifest=configured))
    assert "model_id" in caught.value.mismatched_fields
    assert "dimension" not in caught.value.mismatched_fields


def test_embedder_manifest_cached_retriever_rejects_explicit_substitute(monkeypatch):
    from vectordb import manager
    from vectordb.embedder_manifest import EmbedderManifestMismatch

    store = _store(_manifest())
    monkeypatch.setattr(manager, "_resolve_active_index", lambda *args: ("documents", None, False))
    monkeypatch.setattr(
        manager,
        "get_settings",
        lambda: SimpleNamespace(vector_backend="chroma", vectordb_chroma_dir="unused"),
    )
    monkeypatch.setattr(manager, "_retriever_cache", {"default": SimpleNamespace()})
    monkeypatch.setattr(manager, "_store_cache", {"default": store})
    monkeypatch.setattr(manager, "_chunks_cache", {"default": []})
    monkeypatch.setattr(manager, "_index_cache_keys", {})
    with pytest.raises(EmbedderManifestMismatch):
        manager.get_retriever(
            embeddings=SimpleNamespace(
                manifest=_manifest(model_id="other-model"), embedding_dimension=1024
            )
        )
    assert "default" not in manager._retriever_cache


def _creating_chroma(stores):
    class Chroma:
        def __init__(self, **kwargs):
            name = kwargs["collection_name"]
            if name in stores:
                self.__dict__.update(stores[name].__dict__)
                return
            self._collection = _store(None)._collection
            self._collection.metadata = kwargs.get("collection_metadata") or {}
            self._documents = []
            self._collection.count = lambda: len(self._documents)
            self._collection.query = lambda **kwargs: {"ids": [["doc"]]}
            self.similarity_search = lambda *args, **kwargs: self._documents
            stores[name] = self

        @classmethod
        def from_documents(cls, **kwargs):
            store = cls(**kwargs)
            store._documents.extend(kwargs["documents"])
            stores[kwargs["collection_name"]] = store
            return store

    return Chroma


@pytest.mark.parametrize("entrypoint", ["legacy", "factcards", "build", "publication"])
def test_embedder_manifest_every_collection_creator_stamps(monkeypatch, tmp_path, entrypoint):
    import config.settings
    from tests.test_index_staging import _held_tenant_lock
    from vectordb import manager
    from vectordb.embedder_manifest import MANIFEST_METADATA_KEY
    from vectordb.index_manifest import resolve_active_collection

    stores = {}
    chroma = _creating_chroma(stores)
    settings = SimpleNamespace(
        vector_backend="chroma",
        vectordb_chroma_dir=tmp_path,
        vectordb_retention_max_versions=2,
        vectordb_collection_prefix="rag_docs",
        contextual_headers=False,
    )
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(manager, "get_settings", lambda: settings)
    monkeypatch.setattr(manager, "_get_chroma", lambda: chroma)
    monkeypatch.setattr(manager._base_manager, "_load_chroma", lambda: chroma)
    monkeypatch.setattr(manager._base_manager, "_data_dir", lambda: tmp_path)
    monkeypatch.setattr(manager._base_manager, "select_chunks", lambda docs, *args, **kwargs: docs)
    monkeypatch.setattr(
        manager, "tenant_index_lock", lambda tenant: _held_tenant_lock(monkeypatch, tenant)
    )
    monkeypatch.setattr(manager, "execute_chroma_retention", lambda *args, **kwargs: None)
    for name in ("_retriever_cache", "_chunks_cache", "_store_cache", "_index_cache_keys"):
        monkeypatch.setattr(manager, name, {})
    embeddings = SimpleNamespace(manifest=_manifest(), embed_query=lambda text: [0.0] * 1024)
    docs = [SimpleNamespace(page_content="Seed policy.", metadata={"source": "policy.md"})]
    if entrypoint == "legacy":
        store = manager._base_manager._build_chroma(docs, embeddings)
    elif entrypoint == "factcards":
        store = manager.build_factcard_store(docs, embeddings=embeddings)
    else:
        builder = (
            manager.build_vector_store
            if entrypoint == "build"
            else manager.build_vector_store_with_publication
        )
        result = builder(docs, {"chunk_size": 800, "chunk_overlap": 200}, embeddings=embeddings)
        store = result[0] if entrypoint == "build" else result.store
        active = resolve_active_collection("default", chroma_directory=tmp_path)
        assert stores[active] is store
    assert store._collection.metadata[MANIFEST_METADATA_KEY] == embeddings.manifest.canonical_json

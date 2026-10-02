"""HTTP embedder manifest contract, deterministic models and stores only."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from agent import graph
from tests.test_ask_contract_route import (
    _DEFAULT_ANSWERS,
    _auth,
    _fixture_model,
    _pipeline,
    _policy_seed,
    api_app,
)
from tests.test_embedder_manifest import _creating_chroma, _manifest, _store
from tests.test_embedder_manifest import _stop_chroma_systems as _stop_chroma_systems
from tracing.sqlite_trace import get_trace_detail
from vectordb import manager

_SESSION_FACTORY = api_app._get_or_create_session
_INITIALIZE = api_app.initialize_vector_store


def _setup(monkeypatch, client, tmp_path, *, mismatch=False):
    seed = _policy_seed()
    _, settings = _pipeline(monkeypatch, client, tmp_path, answers=list(_DEFAULT_ANSWERS))
    settings.vector_backend = "chroma"
    settings.vectordb_chroma_dir = tmp_path / "chroma"
    settings.vectordb_chroma_dir.mkdir()
    settings.self_rag_max_iterations = 0
    monkeypatch.setattr(api_app, "get_settings", lambda: settings)
    monkeypatch.setattr(api_app, "_get_or_create_session", _SESSION_FACTORY)
    monkeypatch.setattr(api_app, "_ConversationSession", graph.ConversationSession)
    monkeypatch.setattr(api_app, "_llm", _fixture_model(list(_DEFAULT_ANSWERS) * 3))
    monkeypatch.setattr(api_app, "_startup_manifest_refused", False)
    monkeypatch.setattr(type(api_app._db_cooldown), "blocked", lambda self, tenant: True)
    monkeypatch.setattr(manager, "_retriever_cache", {})
    monkeypatch.setattr(manager, "_index_manifest_status", {})
    stores = {
        tenant: _store(
            _manifest(model_id="other") if mismatch and tenant == "tenant-b" else _manifest()
        )
        for tenant in ("tenant-a", "tenant-b", "default")
    }
    for store in stores.values():
        store.similarity_search = lambda query, k: [seed]
    embedder = SimpleNamespace(manifest=_manifest(), embedding_dimension=1024)
    monkeypatch.setattr(api_app, "_vector_store", stores["default"])
    monkeypatch.setattr(api_app, "_retriever", None)
    monkeypatch.setattr(
        api_app,
        "_get_retriever",
        lambda *args, tenant_id="default", **kwargs: manager.get_retriever(
            vector_store=stores[tenant_id], chunks=[seed], embeddings=embedder, tenant_id=tenant_id
        ),
    )
    return settings, stores, embedder


def test_ask_embedder_manifest_match_in_trace_and_evidence(monkeypatch, client, tmp_path):
    _setup(monkeypatch, client, tmp_path)
    response = client.post("/api/ask", json={"question": "Summarize the policy"})
    assert response.status_code == 200, response.text
    trace_id = response.json()["trace_id"]
    trace = get_trace_detail(trace_id, tenant_id="default")
    nodes = [step["node"] for step in trace["steps"]]
    position = nodes.index("index_manifest")
    assert nodes[position : position + 3] == ["index_manifest", "retrieval_route", "retrieve"]
    record = trace["steps"][position]["state"]
    assert record["status"] == "match"
    assert record["stored"] == record["configured"] == _manifest().as_dict()
    evidence = client.get(f"/api/admin/traces/{trace_id}/evidence")
    assert evidence.status_code == 200, evidence.text
    assert evidence.json()["embedder_manifest"] == {
        key: record[key]
        for key in ("status", "stored", "configured", "mismatched_fields", "evidence_status")
    }


@pytest.mark.parametrize("backend", ["local", "remote"])
def test_ask_embedder_manifest_unverified_revision_in_trace_and_evidence(
    monkeypatch, client, tmp_path, backend
):
    _, stores, embedder = _setup(monkeypatch, client, tmp_path)
    reason = "remote_unversioned" if backend == "remote" else "revision_unresolved"
    embedder.manifest = _manifest(
        backend=backend,
        model_id="mistral-embed" if backend == "remote" else "BAAI/bge-m3",
        revision=None,
        revision_source="remote_unversioned" if backend == "remote" else "unresolved",
    )
    stores["default"]._collection.metadata["embedder_manifest"] = embedder.manifest.canonical_json
    response = client.post("/api/ask", json={"question": "Summarize the policy"})
    assert response.status_code == 200, response.text
    trace_id = response.json()["trace_id"]
    trace = get_trace_detail(trace_id, tenant_id="default")
    record = next(step["state"] for step in trace["steps"] if step["node"] == "index_manifest")
    assert record["status"] == "unverified"
    assert record["evidence_status"] == "NOT_EVIDENCE"
    assert record["reason"] == reason
    evidence = client.get(f"/api/admin/traces/{trace_id}/evidence")
    assert evidence.status_code == 200, evidence.text
    assert evidence.json()["embedder_manifest"] == record


def test_ask_embedder_manifest_refusal_is_tenant_scoped(monkeypatch, client, tmp_path):
    _setup(monkeypatch, client, tmp_path, mismatch=True)
    for tenant, expected in (("tenant-a", 200), ("tenant-b", 503), ("tenant-a", 200)):
        response = client.post(
            "/api/ask", headers=_auth(tenant), json={"question": "Summarize the policy"}
        )
        assert response.status_code == expected, response.text
        if tenant == "tenant-b":
            detail = response.json()["detail"]
    assert detail["reason"] == "embedder_manifest_mismatch"
    trace_id = detail["trace_id"]
    trace = get_trace_detail(trace_id, tenant_id="tenant-b")
    assert len(trace["steps"]) == 1
    record = trace["steps"][0]["state"]
    assert record["status"] == "refused"
    assert record["reason"] == detail["reason"]
    assert record["mismatched_fields"] == ["model_id"]
    assert record["evidence_status"] == "NOT_EVIDENCE"
    own = client.get(f"/api/admin/traces/{trace_id}/evidence", headers=_auth("tenant-b"))
    assert own.status_code == 200, own.text
    assert own.json()["embedder_manifest"]["status"] == "refused"
    for suffix in ("", "/evidence"):
        foreign = client.get(f"/api/admin/traces/{trace_id}{suffix}", headers=_auth("tenant-a"))
        assert foreign.status_code == 404, foreign.text
    assert "tenant-a" in manager._retriever_cache
    assert "tenant-b" not in manager._retriever_cache


def test_ask_embedder_manifest_startup_refusal_cannot_answer(monkeypatch, client, tmp_path):
    settings, stores, embedder = _setup(monkeypatch, client, tmp_path)
    stores["default"]._collection.metadata["embedder_manifest"] = replace(
        _manifest(), model_id="other"
    ).canonical_json
    (settings.vectordb_chroma_dir / "fixture").touch()
    monkeypatch.setattr(api_app, "_vector_store", None)
    monkeypatch.setattr(api_app, "_Chroma", lambda **kwargs: stores["default"])
    monkeypatch.setattr(api_app, "_get_embeddings", lambda: embedder)
    _INITIALIZE()
    response = client.post("/api/ask", json={"question": "Summarize the policy"})
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["reason"] == "embedder_manifest_mismatch"
    trace = get_trace_detail(detail["trace_id"], tenant_id="default")
    assert trace["steps"][0]["state"]["status"] == "refused"


def test_embedder_manifest_upload_build_publishes_stamp_and_clears_startup_refusal(
    monkeypatch, client, tmp_path
):
    from tests.test_index_staging import _held_tenant_lock
    from vectordb.embedder_manifest import MANIFEST_METADATA_KEY
    from vectordb.index_manifest import resolve_active_collection

    settings, _, embedder = _setup(monkeypatch, client, tmp_path)
    embedder.embed_query = lambda text: [0.0] * 1024
    stores = {}
    monkeypatch.setattr(manager, "get_embeddings", lambda: embedder)
    monkeypatch.setattr(manager, "_get_chroma", lambda: _creating_chroma(stores))
    monkeypatch.setattr(manager._base_manager, "select_chunks", lambda docs, *args, **kwargs: docs)
    monkeypatch.setattr(
        manager, "tenant_index_lock", lambda tenant: _held_tenant_lock(monkeypatch, tenant)
    )
    monkeypatch.setattr(manager, "execute_chroma_retention", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        api_app, "_build_vector_store_with_publication", manager.build_vector_store_with_publication
    )
    monkeypatch.setattr(api_app, "_get_retriever", manager.get_retriever)
    monkeypatch.setattr(api_app, "_startup_manifest_refused", True)
    result = api_app._rebuild_vector_store_from_docs([_policy_seed()])
    assert result is not None
    active = resolve_active_collection("default", chroma_directory=settings.vectordb_chroma_dir)
    assert stores[active]._collection.metadata[MANIFEST_METADATA_KEY] == _manifest().canonical_json
    assert manager.get_index_manifest_status("default")["status"] == "match"
    assert api_app._startup_manifest_refused is False
    response = client.post("/api/ask", json={"question": "Summarize the policy"})
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("initial", ["new", "empty", "match", "legacy", "mismatch"])
def test_embedder_manifest_kb_publish_stamps_only_new_collection(
    monkeypatch, client, tmp_path, initial
):
    import uuid

    from api.routers import admin_kb
    from tests.test_embedder_manifest_repair import _real_chroma_store
    from tests.test_index_staging import _held_tenant_lock
    from vectordb.embedder_manifest import MANIFEST_METADATA_KEY
    from vectordb.index_manifest import resolve_active_collection

    settings, _, embedder = _setup(monkeypatch, client, tmp_path)
    draft_id = uuid.uuid4()
    draft = SimpleNamespace(
        id=draft_id,
        tenant_id="default",
        topic="Policy",
        draft_content="Seed policy.",
        source_ticket_ids=[],
        status="pending",
        reviewed_at=None,
    )
    chroma = _real_chroma_store(tmp_path / "kb-chroma")
    name = resolve_active_collection("default", chroma_directory=settings.vectordb_chroma_dir)
    if initial != "new":
        stored = _manifest(model_id="other-model") if initial == "mismatch" else _manifest()
        seed = chroma(
            collection_name=name,
            collection_metadata={MANIFEST_METADATA_KEY: stored.canonical_json}
            if initial in ("match", "mismatch")
            else None,
        )
        if initial != "empty":
            seed.add_documents([SimpleNamespace(page_content="Original policy.")])
    before = 0 if initial in ("new", "empty") else 1
    commits = []

    class Db:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, model, value):
            assert value == draft_id
            return draft

        async def commit(self):
            commits.append(True)

    monkeypatch.setattr(admin_kb, "_async_session", Db)
    monkeypatch.setattr(manager, "Chroma", chroma)
    monkeypatch.setattr(manager, "get_embeddings", lambda: embedder)
    monkeypatch.setattr(
        manager, "tenant_index_lock", lambda tenant: _held_tenant_lock(monkeypatch, tenant)
    )
    response = client.post(f"/api/admin/kb-drafts/{draft_id}/publish")
    collection = chroma(collection_name=name)._collection
    if initial == "mismatch":
        assert response.status_code == 409, response.text
        body = response.json()
        assert body["reason"] == "embedder_manifest_mismatch"
        trace = get_trace_detail(body["trace_id"], tenant_id="default")
        assert trace["steps"][0]["node"] == "index_manifest"
        record = trace["steps"][0]["state"]
        assert record["status"] == "refused"
        assert record["reason"] == body["reason"]
        assert record["mismatched_fields"] == ["model_id"]
        assert collection.count() == before
        assert collection.metadata[MANIFEST_METADATA_KEY] == stored.canonical_json
        assert draft.status == "pending"
        assert draft.reviewed_at is None
        assert commits == []
        foreign = client.get(
            f"/api/admin/traces/{body['trace_id']}/evidence", headers=_auth("tenant-b")
        )
        assert foreign.status_code == 404, foreign.text
        return
    assert response.status_code == 200, response.text
    assert collection.count() == before + 1
    assert draft.status == "published"
    assert commits == [True]
    if initial == "legacy":
        assert MANIFEST_METADATA_KEY not in (collection.metadata or {})
    else:
        assert collection.metadata.get(MANIFEST_METADATA_KEY) == _manifest().canonical_json

"""The Mac service accepts only the measured INT8 export before starting the API."""

from __future__ import annotations

import hashlib

import pytest

from deploy.macos import start


@pytest.fixture
def deployment(tmp_path, monkeypatch):
    index = tmp_path / "index"
    index.mkdir()
    (index / "chroma.sqlite3").touch()
    model = tmp_path / "model.onnx"
    model.write_bytes(b"small test export")
    monkeypatch.setattr(
        start, "RERANKER_ONNX_SHA256", hashlib.sha256(model.read_bytes()).hexdigest()
    )
    return {
        "DATABASE_URL": "postgresql://test:test@localhost/test",
        "VECTORDB_CHROMA_DIR": str(index),
        "RAG_RERANKER_ONNX": str(model),
        "JWT_SECRET": "j" * 48,
        "DB_ENCRYPTION_KEY": "e" * 32,
        "ADMIN_PASSWORD_HASH": "$2b$12$" + "a" * 53,
        "ADMIN_DEFAULT_TENANT": "test",
    }


def test_service_accepts_onnx_path_as_a_deployment_key(tmp_path, monkeypatch):
    path = tmp_path / "service.env"
    path.write_text("RAG_RERANKER_ONNX=/models/int8/model.onnx\n", encoding="utf-8", newline="\n")
    # Windows cannot express POSIX 0600; permissions are not this test's subject.
    monkeypatch.setattr(start.stat, "S_IMODE", lambda mode: 0o600)
    deployment, own = start.read_service_env(path)
    assert deployment == {"RAG_RERANKER_ONNX": "/models/int8/model.onnx"}
    assert own == {}
    assert start.api_environment(deployment)["RAG_RERANKER_ONNX"] == "/models/int8/model.onnx"


@pytest.mark.parametrize("kind", ["unset", "missing", "directory"])
def test_service_refuses_a_missing_onnx_file(deployment, tmp_path, kind):
    if kind == "unset":
        del deployment["RAG_RERANKER_ONNX"]
    else:
        deployment["RAG_RERANKER_ONNX"] = str(
            tmp_path if kind == "directory" else tmp_path / "none"
        )
    with pytest.raises(start.Stop, match="RAG_RERANKER_ONNX") as refused:
        start.check_values(deployment)
    assert refused.value.code == start.REFUSE


def test_service_refuses_the_wrong_onnx_digest(deployment, monkeypatch):
    monkeypatch.setattr(start, "RERANKER_ONNX_SHA256", "0" * 64)
    with pytest.raises(start.Stop, match="RAG_RERANKER_ONNX.*SHA-256") as refused:
        start.check_values(deployment)
    assert refused.value.code == start.REFUSE
    assert all(value not in str(refused.value) for value in deployment.values())


def test_service_accepts_the_measured_onnx_digest(deployment):
    start.check_values(deployment)

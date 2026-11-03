"""The Mac service accepts only the measured INT8 export before starting the API."""

from __future__ import annotations

import hashlib

import pytest

from deploy.macos import start


def test_service_forces_the_measured_offline_environment(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
    env = start.api_environment({})
    assert env["HF_HUB_OFFLINE"] == "1"
    assert env["TRANSFORMERS_OFFLINE"] == "1"


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


@pytest.mark.parametrize("profile", ["local-first", "codex-answer"])
def test_service_accepts_codex_deployment_keys(deployment, tmp_path, monkeypatch, profile):
    binary = tmp_path / "codex"
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
    binary.chmod(0o700)
    home = tmp_path / "codex-home"
    home.mkdir()
    additions = {
        "LLM_PROVIDER_PROFILE": profile,
        "CODEX_BINARY": str(binary),
        "CODEX_HOME": str(home),
    }
    env_file = tmp_path / "service.env"
    env_file.write_text(
        "".join(f"{k}={v}\n" for k, v in additions.items()), encoding="utf-8", newline="\n"
    )
    monkeypatch.setattr(start.stat, "S_IMODE", lambda mode: 0o600)
    parsed, own = start.read_service_env(env_file)
    assert parsed == additions and own == {}
    env = start.api_environment({**deployment, **parsed})
    start.check_values(env)
    assert all(env[k] == v for k, v in additions.items())


@pytest.mark.parametrize(
    "key,value",
    [
        ("LLM_PROVIDER_PROFILE", "mistral"),
        ("LLM_PROVIDER_PROFILE", ""),
        ("CODEX_BINARY", "codex"),
        ("CODEX_BINARY", ""),
        ("CODEX_HOME", "~/codex"),
        ("CODEX_HOME", "relative/home"),
        ("CODEX_HOME", ""),
    ],
)
def test_service_refuses_invalid_codex_values(deployment, key, value):
    with pytest.raises(start.Stop, match=key) as refused:
        start.check_values({**deployment, key: value})
    assert refused.value.code == start.REFUSE


def test_codex_profile_requires_service_paths(deployment):
    with pytest.raises(start.Stop, match="CODEX_BINARY"):
        start.check_values({**deployment, "LLM_PROVIDER_PROFILE": "codex-answer"})


@pytest.mark.parametrize("kind", ["missing", "directory", "not-executable"])
def test_service_refuses_unusable_codex_binary(deployment, tmp_path, kind):
    binary = tmp_path / "codex"
    if kind == "directory":
        binary.mkdir()
    elif kind == "not-executable":
        binary.write_text("not executable", encoding="utf-8")
        binary.chmod(0o600)
    with pytest.raises(start.Stop, match="CODEX_BINARY"):
        start.check_values({**deployment, "CODEX_BINARY": str(binary)})


def test_service_refuses_non_directory_codex_home(deployment, tmp_path):
    with pytest.raises(start.Stop, match="CODEX_HOME"):
        start.check_values({**deployment, "CODEX_HOME": str(tmp_path / "missing")})


def test_service_still_refuses_unlisted_tuning_keys(tmp_path, monkeypatch):
    path = tmp_path / "service.env"
    path.write_text("CODEX_MODEL=another-model\n", encoding="utf-8", newline="\n")
    monkeypatch.setattr(start.stat, "S_IMODE", lambda mode: 0o600)
    with pytest.raises(start.Stop, match="no deployment key"):
        start.read_service_env(path)

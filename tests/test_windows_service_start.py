"""The Windows launcher contract is testable without Windows or live services."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from deploy.macos import start as macos
from deploy.windows import start


@pytest.fixture
def deployment(tmp_path, monkeypatch):
    index = tmp_path / "index"
    index.mkdir()
    (index / "chroma.sqlite3").touch()
    model = tmp_path / "model.onnx"
    model.write_bytes(b"small test export")
    monkeypatch.setattr(
        macos, "RERANKER_ONNX_SHA256", hashlib.sha256(model.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(start.os.path, "isfile", lambda path: path == "C:/native/codex.exe")
    monkeypatch.setattr(start.os.path, "isdir", lambda path: path in {"C:/profile", "D:/hf-cache"})
    return {
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:55432/test",
        "VECTORDB_CHROMA_DIR": str(index),
        "RAG_RERANKER_ONNX": str(model),
        "JWT_SECRET": "j" * 48,
        "DB_ENCRYPTION_KEY": "e" * 32,
        "ADMIN_PASSWORD_HASH": "$2b$12$" + "a" * 53,
        "ADMIN_DEFAULT_TENANT": "test",
        "HF_HOME": "D:/hf-cache",
    }


def test_key_allowlist_matches_deployment_contract():
    assert start.DEPLOYMENT_KEYS == macos.DEPLOYMENT_KEYS | {"HF_HOME"}
    assert macos.OWN_KEYS.isdisjoint(start.DEPLOYMENT_KEYS)


def test_parser_accepts_new_keys_without_posix_permissions(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "ROOT", tmp_path / "checkout")
    path = tmp_path / "service.env"
    content = (
        "# Windows deployment\nLLM_PROVIDER_PROFILE=codex-answer\n"
        "CODEX_BINARY=C:/native/codex.exe\nCODEX_HOME=C:/profile\nHF_HOME=D:/hf-cache\n"
    )
    path.write_text(content, encoding="utf-8", newline="\n")
    path.chmod(0o644)
    assert start.read_service_env(path) == {
        "LLM_PROVIDER_PROFILE": "codex-answer",
        "CODEX_BINARY": "C:/native/codex.exe",
        "CODEX_HOME": "C:/profile",
        "HF_HOME": "D:/hf-cache",
    }


@pytest.mark.parametrize(
    "content",
    [
        b"HF_HOME=D:/cache\r\n",
        b"HF_HOME=\xff\n",
        b"\xef\xbb\xbfHF_HOME=D:/cache\n",
        b"HF_HOME=D:/cache\nHF_HOME=D:/other\n",
        b'CODEX_HOME="C:/profile"\n',
        b"CODEX_BINARY= C:/native/codex.exe\n",
        b"export HF_HOME=D:/cache\n",
        b"HF_HOME =D:/cache\n",
        b"HF_HOME=D:/cache \n",
        b"CODEX_MODEL=other\n",
        b"RAG_SERVICE_MEMORY_POLICY=none\n",
        b"RAG_SERVICE_OLLAMA_LOG=D:/log\n",
        b"HF_HUB_OFFLINE=0\n",
        b"OLLAMA_MODEL_NAME=other\n",
        b"HF_HOME=D:/<cache>\n",
    ],
)
def test_parser_refuses_invalid_format_and_keys(tmp_path, monkeypatch, content):
    monkeypatch.setattr(start, "ROOT", tmp_path / "checkout")
    path = tmp_path / "service.env"
    path.write_bytes(content)
    with pytest.raises(start.Stop):
        start.read_service_env(path)


def test_env_file_must_be_absolute_and_outside_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "ROOT", tmp_path)
    path = tmp_path / "service.env"
    path.touch()
    for candidate in (path, Path("relative.env")):
        with pytest.raises(start.Stop):
            start.read_service_env(candidate)


def test_default_env_location_and_single_override(monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", "C:/Users/owner/AppData/Local")
    assert start.service_env_path([]) == Path(
        "C:/Users/owner/AppData/Local/rag-new/chat-service.env"
    )
    assert start.service_env_path(["D:/RAG_new_prod/chat-service.env"]) == Path(
        "D:/RAG_new_prod/chat-service.env"
    )
    with pytest.raises(start.Stop):
        start.service_env_path(["one", "two"])
    monkeypatch.delenv("LOCALAPPDATA")
    with pytest.raises(start.Stop):
        start.service_env_path([])


@pytest.mark.parametrize("profile", [None, "local-first", "codex-answer", "codex-only"])
def test_valid_deployment_reuses_index_digest_and_secret_rules(deployment, profile):
    if profile is not None:
        deployment["LLM_PROVIDER_PROFILE"] = profile
    if profile in {"codex-answer", "codex-only"}:
        deployment.update(CODEX_BINARY="C:/native/codex.exe", CODEX_HOME="C:/profile")
    start.check_values(deployment)


@pytest.mark.parametrize(
    "key,value",
    [
        ("LLM_PROVIDER_PROFILE", "other"),
        ("LLM_PROVIDER_PROFILE", ""),
        ("CODEX_BINARY", "codex.exe"),
        ("CODEX_BINARY", "C:codex.exe"),
        ("CODEX_BINARY", "/codex.exe"),
        ("CODEX_BINARY", "C:/native/codex.cmd"),
        ("CODEX_BINARY", "C:/missing.exe"),
        ("CODEX_BINARY", "C:/directory.exe"),
        ("CODEX_BINARY", ""),
        ("CODEX_HOME", "relative"),
        ("CODEX_HOME", "C:profile"),
        ("CODEX_HOME", "C:/missing"),
        ("CODEX_HOME", "C:/native/codex.exe"),
        ("CODEX_HOME", ""),
        ("HF_HOME", "relative"),
        ("HF_HOME", "D:cache"),
        ("HF_HOME", "D:/missing"),
        ("HF_HOME", "C:/native/codex.exe"),
        ("HF_HOME", ""),
        ("HF_HOME", "D:/<cache>"),
        ("CODEX_HOME", "C:/<profile>"),
        ("CODEX_BINARY", "C:/<codex>.exe"),
        ("LLM_PROVIDER_PROFILE", "<profile>"),
    ],
)
def test_new_key_refusals(deployment, key, value):
    with pytest.raises(start.Stop, match=key):
        start.check_values({**deployment, key: value})


@pytest.mark.parametrize("profile", ["codex-answer", "codex-only"])
def test_required_windows_paths(deployment, profile):
    no_cache = {key: value for key, value in deployment.items() if key != "HF_HOME"}
    with pytest.raises(start.Stop, match="HF_HOME"):
        start.check_values(no_cache)
    with pytest.raises(start.Stop, match="CODEX_BINARY"):
        start.check_values({**deployment, "LLM_PROVIDER_PROFILE": profile})
    with pytest.raises(start.Stop, match="CODEX_HOME"):
        start.check_values(
            {
                **deployment,
                "LLM_PROVIDER_PROFILE": profile,
                "CODEX_BINARY": "C:/native/codex.exe",
            }
        )


@pytest.mark.parametrize(
    "key,minimum", [("JWT_SECRET", 32), ("SESSION_SECRET_KEY", 32), ("DB_ENCRYPTION_KEY", 16)]
)
def test_shared_secret_lengths(deployment, key, minimum):
    with pytest.raises(start.Stop, match=key):
        start.check_values({**deployment, key: "z" * (minimum - 1)})
    start.check_values({**deployment, key: "z" * minimum})


@pytest.mark.parametrize("kind", ["index", "digest", "hash", "placeholder"])
def test_shared_checks_are_not_bypassed(deployment, monkeypatch, kind):
    if kind == "index":
        (Path(deployment["VECTORDB_CHROMA_DIR"]) / "chroma.sqlite3").unlink()
    elif kind == "digest":
        monkeypatch.setattr(macos, "RERANKER_ONNX_SHA256", "0" * 64)
    elif kind == "hash":
        deployment["ADMIN_PASSWORD_HASH"] = "bad-hash"
    else:
        deployment["ADMIN_USERNAME"] = "<login>"
    with pytest.raises(start.Stop):
        start.check_values(deployment)


def test_api_environment_drops_inherited_tuning_and_forces_offline(deployment, monkeypatch):
    monkeypatch.setenv("USERPROFILE", "C:/Users/owner")
    monkeypatch.setenv("OLLAMA_MODEL_NAME", "wrong-model")
    monkeypatch.setenv("CODEX_MODEL", "wrong-model")
    monkeypatch.setenv("LLM_PROVIDER_PROFILE", "wrong-profile")
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "private")
    env = start.api_environment(deployment)
    assert env["HF_HUB_OFFLINE"] == env["TRANSFORMERS_OFFLINE"] == "1"
    assert env["HF_HOME"] == deployment["HF_HOME"]
    assert env["PYTHONPATH"] == str(start.ROOT)
    assert env["PYTHONUTF8"] == "1" and env["PYTHONIOENCODING"] == "utf-8"
    assert env["USERPROFILE"] == "C:/Users/owner"
    for key in ("OLLAMA_MODEL_NAME", "CODEX_MODEL", "LLM_PROVIDER_PROFILE", "OPENAI_API_KEY"):
        assert key not in env


@pytest.fixture
def ready(monkeypatch, tmp_path, deployment):
    from config import settings

    calls = []
    monkeypatch.setattr(start, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(start, "DATA", tmp_path / "data")
    monkeypatch.setattr(start.os, "environ", {})
    monkeypatch.setattr(start, "read_service_env", lambda _: deployment)
    monkeypatch.setattr(macos, "port_taken", lambda *_: False)
    monkeypatch.setattr(start, "wait_for_postgres", lambda _: calls.append("postgres"))
    monkeypatch.setattr(macos, "check_ollama", lambda *_: calls.append("ollama"))
    monkeypatch.setattr(macos, "validate", lambda _: calls.append("validate"))
    monkeypatch.setattr(
        settings,
        "Settings",
        lambda: SimpleNamespace(
            ollama_base_url="http://localhost:11434", ollama_model_name="test-model"
        ),
    )
    monkeypatch.setattr(
        start.subprocess,
        "run",
        lambda argv, **kwargs: calls.append((argv, kwargs)) or SimpleNamespace(returncode=23),
    )
    return calls


def test_main_preflights_and_forwards_child_exit(ready, capsys, deployment):
    assert start.main(["D:/RAG_new_prod/chat-service.env"]) == 23
    assert ready[:3] == ["postgres", "ollama", "validate"]
    argv, kwargs = ready[3]
    assert argv == [
        start.PY,
        "-m",
        "uvicorn",
        "api.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8002",
        "--workers",
        "1",
    ]
    assert kwargs["cwd"] == start.ROOT
    assert kwargs["shell"] is False
    assert kwargs["check"] is False
    output = capsys.readouterr()
    assert all(value not in output.out + output.err for value in deployment.values())


def test_codex_only_preflight_skips_ollama(ready, deployment, monkeypatch):
    deployment.update(
        LLM_PROVIDER_PROFILE="codex-only",
        CODEX_BINARY="C:/native/codex.exe",
        CODEX_HOME="C:/profile",
    )

    def forbidden(*args):
        pytest.fail("Codex-only must not probe Ollama")

    monkeypatch.setattr(macos, "check_ollama", forbidden)
    assert start.main(["D:/RAG_new_prod/chat-service.env"]) == 23
    assert ready[:2] == ["postgres", "validate"]
    assert ready[2][1]["env"]["LLM_PROVIDER_PROFILE"] == "codex-only"


@pytest.mark.parametrize("failure", ["values", "postgres", "ollama", "settings"])
def test_failed_preflight_never_starts_or_prints_values(ready, monkeypatch, capsys, failure):
    def fail(*_):
        raise start.Stop(macos.NOT_YET, "sensitive-file-value")

    target, name = {
        "values": (start, "check_values"),
        "postgres": (start, "wait_for_postgres"),
        "ollama": (macos, "check_ollama"),
        "settings": (macos, "validate"),
    }[failure]
    monkeypatch.setattr(target, name, fail)
    assert start.main(["D:/RAG_new_prod/chat-service.env"]) == 1
    assert all(isinstance(call, str) for call in ready)
    output = capsys.readouterr()
    assert "sensitive-file-value" not in output.out + output.err


@pytest.mark.parametrize("fails", [False, True])
def test_postgres_preflight_awaits_select_one_and_redacts_failure(monkeypatch, fails):
    calls = []

    async def select_one(url):
        calls.append(url)
        if fails:
            raise OSError("sensitive-connection-detail")

    monkeypatch.setattr(macos, "_select_one", select_one)
    if fails:
        with pytest.raises(start.Stop, match="^PostgreSQL did not accept the service login$"):
            start.wait_for_postgres("private-database-url")
    else:
        start.wait_for_postgres("private-database-url")
    assert calls == ["private-database-url"]

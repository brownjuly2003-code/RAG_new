"""Deployment contracts; Windows processes and ACLs are faked on POSIX."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

from deploy.windows import _support, prepare_postgres, run_detached, smoke_ask, start, write_env


@pytest.fixture
def paths(tmp_path):
    return _support.Paths(tmp_path / "product")


@pytest.mark.parametrize("module", [prepare_postgres, write_env, run_detached, smoke_ask])
def test_root_argument_and_default(module, tmp_path):
    trailing = ["A question"] if module is smoke_ask else []
    assert module.parser().parse_args(trailing).root == Path("D:/RAG_new_prod")
    args = module.parser().parse_args(["--root", str(tmp_path), *trailing])
    assert args.root == tmp_path


def test_all_product_paths_derive_from_root(paths):
    expected = {
        "app": "app",
        "python": "venv/Scripts/python.exe",
        "launcher": "app/deploy/windows/start.py",
        "index": "data/aircargo/index/chroma",
        "onnx": "ort/bge-reranker-v2-m3/int8/model.onnx",
        "hf": "hf",
        "pgdata": "pgdata",
        "pglog": "pg.log",
        "secrets": "secrets",
        "pg_store": "secrets/pg.json",
        "service_store": "secrets/service.json",
        "service_log": "service.log",
    }
    for name, relative in expected.items():
        assert getattr(paths, name) == paths.root / relative


@pytest.fixture
def values(paths):
    return write_env.deployment_values(
        paths,
        {"app_role": "rag_app", "app_password": "p@ss:/word", "port": 55432, "database": "rag_new"},
        {
            "jwt_secret": "j" * 48,
            "session_secret_key": "s" * 48,
            "db_encryption_key": "d" * 32,
            "admin_username": "owner",
        },
        Path("C:/native/codex.exe"),
        Path("C:/Users/owner/.codex-work"),
        "$2b$12$" + "a" * 53,
    )


def test_env_body_round_trips_through_launcher(paths, values, tmp_path, monkeypatch):
    monkeypatch.setattr(start, "ROOT", paths.app)
    monkeypatch.setattr(_support, "restrict", lambda _: None)
    env_file = tmp_path / "localappdata" / "chat-service.env"
    write_env.write_env_file(env_file, values)
    raw = env_file.read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf") and raw.endswith(b"\n")
    assert start.read_service_env(env_file) == values
    assert set(values) == start.DEPLOYMENT_KEYS - {"AUTO_MIGRATE"}
    assert all(value and value[0] not in "\"'" for value in values.values())
    assert not start.common.PLACEHOLDER.search(raw.decode("utf-8"))
    assert (
        values["DATABASE_URL"]
        == "postgresql+asyncpg://rag_app:p%40ss%3A%2Fword@127.0.0.1:55432/rag_new"
    )
    assert values["VECTORDB_CHROMA_DIR"] == paths.index.as_posix()
    assert values["RAG_RERANKER_ONNX"] == paths.onnx.as_posix()
    assert values["HF_HOME"] == paths.hf.as_posix()
    assert values["LLM_PROVIDER_PROFILE"] == "codex-only"


@pytest.mark.parametrize("admin_username", [None, "replacement-owner"])
def test_env_command_reuses_password_validates_and_prints_only_keys(
    paths, tmp_path, monkeypatch, capsys, admin_username
):
    monkeypatch.setattr(_support, "require_windows", lambda: None)
    monkeypatch.setattr(_support, "restrict", lambda _: None)
    monkeypatch.setattr(start, "ROOT", paths.app)
    prepare_postgres.load_secrets(paths)
    service = write_env.load_secrets(paths, "original-owner")
    binary = tmp_path / "codex.exe"
    binary.touch()
    env_file = tmp_path / "service.env"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "write_env.py",
            "--root",
            str(paths.root),
            "--env-file",
            str(env_file),
            "--codex-exe",
            str(binary),
            "--codex-home",
            str(tmp_path),
            *(["--admin-username", admin_username] if admin_username is not None else []),
        ],
    )
    hashed = []
    validated = []

    def hashpw(password, salt):
        hashed.append(password)
        return ("$2b$12$" + "a" * 53).encode("ascii")

    monkeypatch.setitem(
        sys.modules, "bcrypt", SimpleNamespace(hashpw=hashpw, gensalt=lambda rounds: b"salt")
    )

    def check_values(values):
        assert not env_file.exists()
        validated.append(values)

    monkeypatch.setattr(start, "check_values", check_values)
    assert write_env.main() == 0
    parsed = start.read_service_env(env_file)
    assert validated == [parsed]
    assert parsed["ADMIN_USERNAME"] == "original-owner"
    assert hashed == [service["admin_password"].encode("utf-8")]
    output = capsys.readouterr()
    assert output.out == "wrote env keys: " + ", ".join(parsed) + "\n"
    assert all(str(value) not in output.out + output.err for value in service.values())


@pytest.mark.parametrize(
    "value", ['"quoted"', "<placeholder>", "owner\nAUTO_MIGRATE=false", " padded"]
)
def test_invalid_generated_env_never_replaces_existing_file(values, value, tmp_path, monkeypatch):
    monkeypatch.setattr(start, "ROOT", tmp_path / "checkout")
    env_file = tmp_path / "service.env"
    env_file.write_bytes(b"old contents\n")
    with pytest.raises(start.Stop):
        write_env.write_env_file(env_file, {**values, "ADMIN_USERNAME": value})
    assert env_file.read_bytes() == b"old contents\n"


def test_writer_reuses_checkout_refusal_before_creating_file(paths, values, monkeypatch):
    monkeypatch.setattr(start, "ROOT", paths.app)
    candidate = paths.app / "service.env"
    with pytest.raises(start.Stop, match="outside the checkout"):
        write_env.write_env_file(candidate, values)
    assert not candidate.exists()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX symlink contract; Windows may require a privilege",
)
def test_writer_refuses_symlink_into_checkout(paths, values, tmp_path, monkeypatch):
    paths.app.mkdir(parents=True)
    monkeypatch.setattr(start, "ROOT", paths.app)
    link = tmp_path / "linked-checkout"
    link.symlink_to(paths.app, target_is_directory=True)
    with pytest.raises(start.Stop, match="outside the checkout"):
        write_env.write_env_file(link / "service.env", values)
    assert not (paths.app / "service.env").exists()


@pytest.mark.parametrize("count", [0, 1, 2])
def test_codex_discovery_requires_exactly_one_file(tmp_path, monkeypatch, count):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    matches = []
    for number in range(count):
        binary = tmp_path / "npm/node_modules/@openai/codex" / str(number) / "bin/codex.exe"
        binary.parent.mkdir(parents=True)
        binary.touch()
        matches.append(binary)
    if count == 1:
        assert write_env.codex_executable(None) == matches[0]
    else:
        with pytest.raises(_support.DeploymentError, match="exactly one"):
            write_env.codex_executable(None)


def test_explicit_codex_binary_and_default_home(tmp_path, monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    binary = tmp_path / "codex.exe"
    binary.touch()
    assert write_env.codex_executable(binary) == binary
    assert write_env.codex_home(None) == tmp_path / ".codex-work"
    assert write_env.codex_home(tmp_path / "signed-in") == tmp_path / "signed-in"
    with pytest.raises(_support.DeploymentError):
        write_env.codex_executable(tmp_path / "codex.cmd")


def test_admin_username_has_no_default():
    assert write_env.parser().parse_args([]).admin_username is None


@pytest.mark.parametrize("admin_username", [None, ""])
def test_missing_admin_username_refuses_before_creating_secrets(paths, monkeypatch, admin_username):
    monkeypatch.setattr(
        _support, "restrict", lambda _: pytest.fail("must refuse before ACL changes")
    )
    with pytest.raises(_support.DeploymentError, match="--admin-username.*required.*service.json"):
        write_env.load_secrets(paths, admin_username)
    assert not paths.root.exists()


def test_secrets_generated_once_and_existing_admin_kept(paths, monkeypatch):
    restricted = []
    monkeypatch.setattr(_support, "restrict", restricted.append)
    first_pg = prepare_postgres.load_secrets(paths)
    first_service = write_env.load_secrets(paths, "original-owner")
    monkeypatch.setattr(_support.secrets, "token_urlsafe", lambda _: pytest.fail("secret rotated"))
    assert prepare_postgres.load_secrets(paths) == first_pg
    assert write_env.load_secrets(paths, None) == first_service
    assert write_env.load_secrets(paths, "replacement-owner") == first_service
    assert first_service["admin_username"] == "original-owner"
    assert (
        paths.secrets in restricted
        and paths.pg_store in restricted
        and paths.service_store in restricted
    )
    assert b"\r" not in paths.service_store.read_bytes()


def test_existing_cluster_without_secrets_is_not_rekeyed(paths):
    paths.pgdata.mkdir(parents=True)
    (paths.pgdata / "PG_VERSION").write_text("16\n", encoding="utf-8")
    with pytest.raises(_support.DeploymentError, match="secrets"):
        prepare_postgres.load_secrets(paths)
    assert not paths.pg_store.exists()


def test_detached_launcher_uses_release_venv_isolation_cwd_and_log(paths, monkeypatch):
    paths.python.parent.mkdir(parents=True)
    paths.python.touch()
    paths.launcher.parent.mkdir(parents=True)
    paths.launcher.touch()
    calls = []

    def detach(argv, **kwargs):
        calls.append((argv, kwargs))
        assert kwargs["stdout"].name == str(paths.service_log)
        return SimpleNamespace(pid=4321)

    monkeypatch.setattr(_support, "detach", detach)
    assert run_detached.launch(paths, None) == 4321
    assert calls[0][0] == [str(paths.python), "-I", str(paths.launcher)]
    assert calls[0][1]["cwd"] == paths.app
    env_file = paths.root / "service.env"
    run_detached.launch(paths, env_file)
    assert calls[1][0][-1] == str(env_file)


@pytest.mark.parametrize("refuse_breakaway", [False, True])
def test_detach_uses_no_window_and_retries_without_breakaway(monkeypatch, refuse_breakaway):
    calls = []
    monkeypatch.setattr(_support, "require_windows", lambda: None)
    for name, value in {
        "CREATE_NO_WINDOW": 0x08000000,
        "CREATE_NEW_PROCESS_GROUP": 0x00000200,
        "CREATE_BREAKAWAY_FROM_JOB": 0x01000000,
        "STARTUPINFO": lambda: pytest.fail("detach must not construct STARTUPINFO"),
    }.items():
        monkeypatch.setattr(_support.subprocess, name, value, raising=False)

    def popen(argv, **kwargs):
        calls.append(kwargs)
        if refuse_breakaway and len(calls) == 1:
            raise OSError("job breakaway unavailable")
        return SimpleNamespace(pid=42)

    monkeypatch.setattr(_support.subprocess, "Popen", popen)
    assert _support.detach(["program.exe"]).pid == 42
    expected_flags = [0x09000200, 0x08000200] if refuse_breakaway else [0x09000200]
    assert [call["creationflags"] for call in calls] == expected_flags
    assert all("startupinfo" not in call for call in calls)
    assert all(call["close_fds"] and call["shell"] is False for call in calls)


def test_acl_removes_inheritance_and_grants_current_user_only(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(_support, "require_windows", lambda: None)
    monkeypatch.setenv("USERNAME", "owner")
    monkeypatch.setattr(_support, "run", lambda argv, **kwargs: calls.append(argv))
    _support.restrict(tmp_path)
    assert calls == [["icacls", tmp_path, "/inheritance:r", "/grant:r", "owner:(OI)(CI)F"]]


@pytest.mark.parametrize("existing", [False, True])
def test_postgres_create_or_reuse_cluster_role_and_database(paths, monkeypatch, existing):
    monkeypatch.setattr(_support, "restrict", lambda _: None)
    paths.pgdata.mkdir(parents=True)
    if existing:
        prepare_postgres.load_secrets(paths)
        (paths.pgdata / "PG_VERSION").write_text("16\n", encoding="utf-8")
    calls, detached = [], []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if argv[-1] == "status":
            return SimpleNamespace(returncode=0 if existing else 3, stdout="")
        sql = kwargs.get("input", "")
        exists = "FROM pg_roles" in sql or "FROM pg_database" in sql
        return SimpleNamespace(returncode=0, stdout="1\n" if existing or not exists else "")

    monkeypatch.setattr(_support, "run", run)
    monkeypatch.setattr(_support, "detach", lambda argv, **kwargs: detached.append(argv))
    prepare_postgres.prepare(paths, Path("C:/PostgreSQL/16/bin"))
    sqls = [kwargs.get("input", "") for _, kwargs in calls]
    assert any("CREATE ROLE" in sql for sql in sqls) is not existing
    assert any("CREATE DATABASE" in sql for sql in sqls) is not existing
    assert any(Path(argv[0]).name == "initdb.exe" for argv, _ in calls) is not existing
    assert bool(detached) is not existing
    if detached:
        assert detached[0] == [
            str(Path("C:/PostgreSQL/16/bin/pg_ctl.exe")),
            "-D",
            str(paths.pgdata),
            "-l",
            str(paths.pglog),
            "start",
        ]
    stored = json.loads(paths.pg_store.read_text(encoding="utf-8"))
    assert all(stored["app_password"] not in str(argv) for argv, _ in calls)


def test_command_failures_do_not_disclose_passwords(monkeypatch, capsys):
    monkeypatch.setattr(
        _support.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, "private", "private"),
    )
    assert _support.cli(lambda: _support.run(["psql.exe"], input="private")) == 2
    assert "private" not in capsys.readouterr().err


def test_http_error_body_is_not_returned_or_printed(monkeypatch, capsys):
    def urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 401, "denied", {}, io.BytesIO(b"private-password")
        )

    monkeypatch.setattr(smoke_ask.urllib.request, "urlopen", urlopen)
    assert smoke_ask.post("/api/auth/login", {"password": "private-password"}) == (401, {})
    output = capsys.readouterr()
    assert not output.out and not output.err


@pytest.mark.parametrize("login_status,ask_status", [(200, 200), (401, 200), (200, 503)])
def test_smoke_reads_stored_credentials_reports_metadata_and_fails_http(
    paths, monkeypatch, capsys, login_status, ask_status
):
    paths.secrets.mkdir(parents=True)
    paths.service_store.write_text(
        json.dumps({"admin_username": "stored-owner", "admin_password": "private-password"}),
        encoding="utf-8",
    )
    calls = []

    def post(path, body, token=None, timeout=60):
        calls.append((path, body, token))
        if path.endswith("login"):
            return login_status, {"access_token": "private-token"}
        return ask_status, {
            "answer_provider": "codex",
            "answer_model": "gpt-6-astra",
            "route": "human",
            "ticket_id": "ticket-1",
            "delivery_state": "persisted",
            "quality_score": None,
        }

    monkeypatch.setattr(smoke_ask, "post", post)
    question = "В какой срок нужно сдать авансовый отчёт после возвращения из командировки?"
    result = smoke_ask.ask(paths, question, "aircargo")
    assert result == (0 if login_status == ask_status == 200 else 1)
    assert calls[0][1] == {"username": "stored-owner", "password": "private-password"}
    if login_status == 200:
        assert calls[1] == (
            "/api/ask",
            {"question": question, "tenant_id": "aircargo"},
            "private-token",
        )
    output = capsys.readouterr()
    assert "private-password" not in output.out + output.err
    assert "private-token" not in output.out + output.err
    if login_status == ask_status == 200:
        for key in (
            "seconds",
            "answer_provider",
            "answer_model",
            "route",
            "ticket_id",
            "delivery_state",
            "quality_score",
        ):
            assert f"{key}:" in output.out
        assert "quality_score: None\n" in output.out

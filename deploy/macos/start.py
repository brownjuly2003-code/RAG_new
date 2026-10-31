"""Start the RAG_new chat as the Mac's launchd service (PLAN.md stage 6, items 1-3).

launchd runs this file (deploy/macos/com.rag-new.chat.plist) with the API's interpreter and
``-I``. A draft: nothing runs it until Julia installs the service on her word
(docs/operations/macos-service.md).

The API starts with the code defaults: the model, the limits and every quality setting come
from config/settings.py, never from .ask100-runtime/env.json, which pins qwen2.5:7b (item 2).
Its environment is built from nothing but the paths below and the deployment keys of one file
outside the repository, SERVICE_ENV. No other variable reaches the API, and no value of that
file is printed or put on a command line.

Exit 0 is a refusal: launchd leaves the service stopped until the cause is fixed and the
service is kickstarted. Exit 1: PostgreSQL or Ollama is not up yet, and launchd runs this again
after its ThrottleInterval. When every check passes, uvicorn replaces this process.
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
# The interpreter the plist names: the stands' (/Users/julia/RAG_Support_Assistant/.venv).
PY = sys.executable
SITE = "/Users/julia/RAG_new_mf_gate_site"
HOME = Path.home()
SERVICE_ENV = HOME / ".config" / "rag-new" / "chat-service.env"
DATA = HOME / ".local" / "share" / "rag-new" / "chat-service"
HOST = "127.0.0.1"
# The measurement stands' port, on purpose: a stand refuses to start while the service holds
# it, and the service refuses while a stand does. One measurement at a time on 8 GB.
PORT = 8002
POSTGRES_WAIT_SEC = 120.0
# Measured INT8 export: reports/stage4-step5a/onnx/manifest.json, files["int8/model.onnx"].
RERANKER_ONNX_SHA256 = "57335a9f061fe31378c160ddd0861711a0fbdfa20f70aa2640d473dfc4bc1343"

# What the service takes from SERVICE_ENV (deploy/macos/service.env.example explains each):
# where its data lives, its secrets and its login. Everything else keeps the code default.
DEPLOYMENT_KEYS = frozenset(
    {
        "DATABASE_URL",
        "VECTORDB_CHROMA_DIR",
        "RAG_RERANKER_ONNX",
        "JWT_SECRET",
        "SESSION_SECRET_KEY",
        "DB_ENCRYPTION_KEY",
        "ADMIN_USERNAME",
        "ADMIN_PASSWORD_HASH",
        "ADMIN_DEFAULT_TENANT",
        "CORS_ORIGINS",
        "AUTO_MIGRATE",
    }
)
REQUIRED_KEYS = (
    "DATABASE_URL",
    "VECTORDB_CHROMA_DIR",
    "RAG_RERANKER_ONNX",
    "JWT_SECRET",
    "DB_ENCRYPTION_KEY",
    "ADMIN_PASSWORD_HASH",
    "ADMIN_DEFAULT_TENANT",
)
# This script's own keys; they never reach the API.
POLICY_KEY = "RAG_SERVICE_MEMORY_POLICY"
OWN_KEYS = frozenset({POLICY_KEY, "RAG_SERVICE_OLLAMA_LOG"})
# The memory policy stage 4 names (PLAN.md stage 4, item 5), "undecided" until it does.
POLICY_SHAPE = re.compile(
    r"(undecided|none|cache-ram:(\d+)|unload-every:(\d+)|unload-at-swap:(\d+))"
)
PLACEHOLDER = re.compile(r"[<>]")
BCRYPT = re.compile(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}")
# Printed at each start beside the settings off the code default: what makes an answer's time.
PUBLIC_SETTINGS = (
    "rag_env",
    "ollama_model_name",
    "llm_provider_profile",
    "rag_device",
    "request_timeout_sec",
    "streaming_timeout_sec",
    "ollama_request_timeout_sec",
    "max_concurrent_pipelines",
    "pipeline_acquire_timeout_sec",
    "db_persist_timeout_sec",
    "db_cooldown_sec",
    "db_cooldown_failure_threshold",
)

REFUSE = 0
NOT_YET = 1


class Stop(Exception):
    """End the start with launchd's exit code and one line that says why."""

    def __init__(self, code: int, reason: str) -> None:
        super().__init__(reason)
        self.code = code


def say(message: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"{stamp} chat-service: {message}", file=sys.stderr, flush=True)


def read_service_env(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """The deployment keys and this script's own, read as text: never sourced, never printed."""
    if not path.is_file():
        raise Stop(REFUSE, f"no {path}; deploy/macos/service.env.example lists its keys")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode != 0o600:
        raise Stop(REFUSE, f"{path} is mode {mode:o}; chmod 600 it")
    raw = path.read_bytes()
    if b"\r" in raw:
        raise Stop(REFUSE, f"{path} has CR line ends; save it with LF")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise Stop(REFUSE, f"{path} is not UTF-8") from None
    deployment: dict[str, str] = {}
    own: dict[str, str] = {}
    for number, line in enumerate(text.split("\n"), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition("=")
        where = f"{path.name} line {number}"
        if not sep or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise Stop(REFUSE, f"{where} is not KEY=VALUE")
        if key in deployment or key in own:
            raise Stop(REFUSE, f"{where}: {key} is set twice")
        if value != value.strip() or value[:1] in {'"', "'"}:
            raise Stop(REFUSE, f"{where}: the value of {key} is quoted or padded with spaces")
        if key in OWN_KEYS:
            own[key] = value
        elif key in DEPLOYMENT_KEYS:
            deployment[key] = value
        else:
            raise Stop(REFUSE, f"{where}: {key} is no deployment key; the code defaults stay")
    return deployment, own


def memory_policy(own: dict[str, str]) -> str:
    """The policy stage 4 names; the service does not start without one it can hold to.

    On 8 GB the 4B's host prompt cache grows with each request until swap (stage 4, step 0).
    `cache-ram:<MiB>` is set outside the service, by one of PLAN's two paths, each on Julia's
    word; the two unloads are named but not built, so they refuse. The cap is proved by the
    limit llama-server reports in Ollama's log, which healthcheck.py reads (PLAN.md: so
    `ps eww` is not needed); the environment of `ollama serve` is not read here.
    """
    policy = own.get(POLICY_KEY, "undecided")
    shape = POLICY_SHAPE.fullmatch(policy)
    if shape is None:
        raise Stop(
            REFUSE,
            f"{POLICY_KEY}={policy} is none of undecided, none, cache-ram:<MiB>, "
            "unload-every:<N>, unload-at-swap:<MB>",
        )
    if policy == "undecided":
        raise Stop(REFUSE, f"{POLICY_KEY} is undecided: stage 4 names it (PLAN.md stage 4, item 5)")
    if policy.startswith("unload-"):
        raise Stop(
            REFUSE,
            f"policy {policy} is named but not built: the unload is stage 4's to wire "
            "(docs/operations/macos-service.md, the memory policy)",
        )
    if policy.startswith("cache-ram:"):
        where = "config.ini" if cache_ram_in_ini(shape.group(2)) else "not config.ini"
        say(f"policy {policy}, {where}; healthcheck.py reads the limit llama-server reports")
    return policy


def cache_ram_in_ini(mib: str) -> bool:
    """llama.cpp's config.ini sets the cap, the first of PLAN's two paths (stage 4, item 5)."""
    ini = HOME / ".config" / "llama.cpp" / "config.ini"
    line = re.compile(rf"^\s*cache-ram\s*=\s*{mib}\s*$", re.MULTILINE)
    return ini.is_file() and bool(line.search(ini.read_text(encoding="utf-8", errors="replace")))


def port_taken(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def api_environment(deployment: dict[str, str]) -> dict[str, str]:
    """The API's whole environment: the user, the interpreter's paths and the deployment keys."""
    env = {
        name: os.environ[name]
        for name in ("HOME", "USER", "LOGNAME", "TMPDIR")
        if os.environ.get(name)
    }
    env.update(
        {
            "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "LANG": "en_US.UTF-8",
            # The stands' paths: the checkout first, then the gate's site directory.
            "PYTHONPATH": f"{ROOT}:{SITE}",
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            # chromadb sends no telemetry from the service.
            "ANONYMIZED_TELEMETRY": "False",
            # Traces outside the checkout, so a new release keeps them.
            "TRACING_DB_PATH": str(DATA / "traces.db"),
        }
    )
    env.update(deployment)
    return env


def check_values(env: dict[str, str]) -> None:
    """The keys are there, filled in and strong; the index is there.

    The secrets meet production's rules (config/settings.py, SEC-02) without RAG_ENV=production:
    that switch also moves the answer path (judge independence and the calibration artifact
    become required), and the measured stands ran the code default.
    """
    from config.settings import production_secret_rejection_reason

    missing = [key for key in REQUIRED_KEYS if not env.get(key)]
    if missing:
        raise Stop(REFUSE, f"{SERVICE_ENV.name} lacks " + ", ".join(missing))
    unfilled = sorted(key for key in DEPLOYMENT_KEYS if PLACEHOLDER.search(env.get(key, "")))
    if unfilled:
        raise Stop(REFUSE, "placeholders left in " + ", ".join(unfilled))
    secrets_rules = (("JWT_SECRET", 32), ("SESSION_SECRET_KEY", 32), ("DB_ENCRYPTION_KEY", 16))
    for key, minimum in secrets_rules:
        value = env.get(key) or (env["JWT_SECRET"] if key == "SESSION_SECRET_KEY" else "")
        reason = production_secret_rejection_reason(value, min_length=minimum, label=key)
        if reason is not None:
            raise Stop(REFUSE, reason)
    if not BCRYPT.fullmatch(env["ADMIN_PASSWORD_HASH"]):
        raise Stop(REFUSE, "ADMIN_PASSWORD_HASH is no bcrypt hash; without one admin/admin logs in")
    index = Path(env["VECTORDB_CHROMA_DIR"])
    if not (index / "chroma.sqlite3").is_file():
        raise Stop(
            REFUSE,
            f"no chroma.sqlite3 in VECTORDB_CHROMA_DIR {index}: the API would make an empty index",
        )
    model = Path(env["RAG_RERANKER_ONNX"])
    if not model.is_file():
        raise Stop(REFUSE, "RAG_RERANKER_ONNX must name the measured INT8 file")
    digest = hashlib.sha256()
    try:
        with model.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        raise Stop(REFUSE, "RAG_RERANKER_ONNX could not be read") from None
    if digest.hexdigest() != RERANKER_ONNX_SHA256:
        raise Stop(REFUSE, "RAG_RERANKER_ONNX SHA-256 differs from the measured INT8 export")


def wait_for_postgres(url_text: str) -> None:
    """The session store's database accepts the service's login (PLAN.md stage 6, item 3)."""
    from sqlalchemy.engine import make_url

    try:
        url = make_url(url_text)
    except Exception:
        # The parser's message quotes the URL, password included.
        raise Stop(REFUSE, "DATABASE_URL is not a URL SQLAlchemy reads") from None
    host, port = url.host or "localhost", int(url.port or 5432)
    deadline = time.monotonic() + POSTGRES_WAIT_SEC
    while True:
        try:
            with socket.create_connection((host, port), timeout=2.0):
                break
        except OSError:
            if time.monotonic() >= deadline:
                raise Stop(NOT_YET, f"PostgreSQL at {host}:{port} accepts no connection") from None
            time.sleep(2.0)
    try:
        asyncio.run(asyncio.wait_for(_select_one(url_text), timeout=60.0))
    except (asyncio.TimeoutError, TimeoutError):
        raise Stop(NOT_YET, f"PostgreSQL at {host}:{port} did not answer in 60 s") from None
    except Exception as exc:
        state = sqlstate(exc)
        if state == "57P03":  # the database system is starting up
            raise Stop(NOT_YET, f"PostgreSQL at {host}:{port} is starting up") from None
        raise Stop(
            REFUSE,
            f"PostgreSQL at {host}:{port} refused the service's login: "
            f"{type(exc).__name__}, SQLSTATE {state or 'none'}",
        ) from None
    say(f"PostgreSQL at {host}:{port} takes the service's login")


async def _select_one(url_text: str) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(url_text, pool_size=1, max_overflow=0)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    finally:
        await engine.dispose()


def sqlstate(exc: BaseException) -> str | None:
    """The SQLSTATE anywhere in the chain SQLAlchemy and asyncpg wrap an error in."""
    seen: set[int] = set()
    todo: list[Any] = [exc]
    while todo:
        item = todo.pop()
        if not isinstance(item, BaseException) or id(item) in seen:
            continue
        seen.add(id(item))
        state = getattr(item, "sqlstate", None)
        if isinstance(state, str) and state:
            return state
        todo += [getattr(item, "orig", None), item.__cause__, item.__context__]
    return None


def get_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=10.0) as response:
        return json.loads(response.read())


def check_ollama(base_url: str, model: str) -> str:
    """Ollama answers and holds the code default's model; nothing is loaded here."""
    try:
        version = str(get_json(f"{base_url}/api/version").get("version", "unknown"))
        tags = get_json(f"{base_url}/api/tags")
    except (OSError, ValueError) as exc:
        raise Stop(
            NOT_YET, f"Ollama at {base_url} does not answer ({type(exc).__name__})"
        ) from None
    names = {item.get("name") for item in tags.get("models", [])}
    if model not in names:
        raise Stop(REFUSE, f"Ollama has no {model}, the code default's model; pull it first")
    return version


def validate(settings: Any) -> None:
    try:
        settings.validate()
    except RuntimeError as exc:
        lines = str(exc).strip().splitlines()
        raise Stop(
            REFUSE, "Settings.validate: " + (lines[0] if lines else "RuntimeError")
        ) from None


def settings_off_default(settings_cls: Any, keys: set[str]) -> list[str]:
    """The Settings fields the service's keys move off the code default, by name."""
    run = settings_cls()
    saved = {key: os.environ.pop(key) for key in keys if key in os.environ}
    try:
        default = settings_cls()
    finally:
        os.environ.update(saved)
    names = []
    for item in dataclasses.fields(run):
        try:
            same = bool(getattr(run, item.name) == getattr(default, item.name))
        except Exception:
            same = False
        if not same:
            names.append(item.name)
    return names


def code_sha() -> str:
    marker = ROOT / "CODE_SHA"
    if marker.is_file():
        return marker.read_text(encoding="utf-8").strip()
    git = shutil.which("git")
    if git is None:
        return "unknown"
    done = subprocess.run(
        [git, "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return done.stdout.strip() or "unknown"


def main() -> int:
    try:
        deployment, own = read_service_env(SERVICE_ENV)
        policy = memory_policy(own)
        if port_taken(HOST, PORT):
            raise Stop(REFUSE, f"port {PORT} is taken: a measurement stand or another API holds it")
        DATA.mkdir(parents=True, exist_ok=True)
        env = api_environment(deployment)
        os.environ.clear()
        os.environ.update(env)
        sys.path[:0] = [str(ROOT), SITE]
        check_values(env)
        wait_for_postgres(env["DATABASE_URL"])
        from config.settings import Settings

        settings = Settings()
        base_url = str(settings.ollama_base_url).rstrip("/")
        version = check_ollama(base_url, settings.ollama_model_name)
        validate(settings)
        off = settings_off_default(Settings, set(env) - {"HOME", "USER", "LOGNAME", "TMPDIR"})
        public = {name: getattr(settings, name, None) for name in PUBLIC_SETTINGS}
        say(f"code {code_sha()}, Ollama {version}, policy {policy}")
        say("settings off the code default: " + (", ".join(off) or "none"))
        say("settings: " + json.dumps(public, default=str))
    except Stop as stop:
        say(("refused: " if stop.code == REFUSE else "not up yet: ") + str(stop))
        return stop.code
    except Exception as exc:
        frame = exc.__traceback__
        while frame is not None and frame.tb_next is not None:
            frame = frame.tb_next
        where = (
            f"{Path(frame.tb_frame.f_code.co_filename).name}:{frame.tb_lineno}" if frame else "?"
        )
        # The message is not printed: it may quote a value of the service's env file.
        say(f"refused: {type(exc).__name__} at {where} in the start checks")
        return REFUSE
    argv = [PY, "-m", "uvicorn", "api.app:app", "--host", HOST, "--port", str(PORT)]
    say(f"uvicorn api.app:app on {HOST}:{PORT}, one worker")
    os.chdir(ROOT)
    os.execve(PY, [*argv, "--workers", "1"], env)
    return REFUSE  # not reached: execve replaces the process


if __name__ == "__main__":
    os.umask(0o077)
    sys.exit(main())

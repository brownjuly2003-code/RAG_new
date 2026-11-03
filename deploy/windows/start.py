"""Start the laptop's chat from one external env file, with code-default quality settings."""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parents[2]
# Support direct invocation with the venv's Python -I, without inherited PYTHONPATH.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy.macos import start as common  # noqa: E402

Stop = common.Stop
PY = sys.executable
DATA = Path("D:/RAG_new_prod")
DEPLOYMENT_KEYS = common.DEPLOYMENT_KEYS | frozenset({"HF_HOME"})
WINDOWS_KEYS = frozenset({"LLM_PROVIDER_PROFILE", "CODEX_BINARY", "CODEX_HOME", "HF_HOME"})
REFUSE = 2


def service_env_path(args: list[str]) -> Path:
    if len(args) > 1:
        raise Stop(REFUSE, "expected at most one env-file argument")
    if args:
        return Path(args[0])
    local = os.environ.get("LOCALAPPDATA", "")
    if not PureWindowsPath(local).is_absolute():
        raise Stop(REFUSE, "LOCALAPPDATA must be absolute, or supply an env-file argument")
    return Path(local) / "rag-new" / "chat-service.env"


def read_service_env(path: Path) -> dict[str, str]:
    """Strict UTF-8/LF data, never shell syntax; Windows access is controlled by ACLs."""
    if not path.is_absolute() or path.resolve().is_relative_to(ROOT.resolve()):
        raise Stop(REFUSE, "env file must be absolute and outside the checkout")
    if not path.is_file():
        raise Stop(REFUSE, "env file is missing")
    raw = path.read_bytes()
    if b"\r" in raw:
        raise Stop(REFUSE, "env file must use LF line endings")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise Stop(REFUSE, "env file must use UTF-8") from None
    deployment: dict[str, str] = {}
    for number, line in enumerate(text.split("\n"), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition("=")
        where = f"env line {number}"
        if not sep or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise Stop(REFUSE, f"{where} is not KEY=VALUE")
        if key not in DEPLOYMENT_KEYS:
            raise Stop(REFUSE, f"{where} has an unknown deployment key")
        if key in deployment:
            raise Stop(REFUSE, f"{where}: {key} is set twice")
        if value != value.strip() or value[:1] in {'"', "'"}:
            raise Stop(REFUSE, f"{where}: {key} is quoted or padded with spaces")
        if common.PLACEHOLDER.search(value):
            raise Stop(REFUSE, f"{where}: {key} contains a placeholder")
        deployment[key] = value
    return deployment


def check_values(deployment: dict[str, str]) -> None:
    for key in DEPLOYMENT_KEYS:
        if common.PLACEHOLDER.search(deployment.get(key, "")):
            raise Stop(REFUSE, f"{key} contains a placeholder")
    profile = deployment.get("LLM_PROVIDER_PROFILE", "local-first")
    if profile not in {"local-first", "codex-answer", "codex-only"}:
        raise Stop(REFUSE, "LLM_PROVIDER_PROFILE must be local-first, codex-answer or codex-only")
    for key in ("CODEX_BINARY", "CODEX_HOME", "HF_HOME"):
        if key not in deployment and key != "HF_HOME" and profile == "local-first":
            continue
        value = deployment.get(key, "")
        path = PureWindowsPath(value)
        if not path.is_absolute():
            raise Stop(REFUSE, f"{key} must be an absolute Windows path")
        if key == "CODEX_BINARY":
            if path.suffix.lower() != ".exe" or not os.path.isfile(value):
                raise Stop(REFUSE, "CODEX_BINARY must name an existing .exe file")
        elif not os.path.isdir(value):
            raise Stop(REFUSE, f"{key} must name an existing directory")
    # Reuse the Mac's secret rules, bcrypt, index and pinned streaming SHA-256 checks.
    # Its POSIX Codex path checks are replaced by the Windows checks above.
    common.check_values(
        {key: value for key, value in deployment.items() if key not in WINDOWS_KEYS}
    )


def api_environment(deployment: dict[str, str]) -> dict[str, str]:
    env = {
        key: os.environ[key]
        for key in ("PATH", "SystemRoot", "TEMP", "TMP", "USERPROFILE")
        if key in os.environ
    }
    env.update(
        {
            "PYTHONPATH": str(ROOT),
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "ANONYMIZED_TELEMETRY": "False",
            "TRACING_DB_PATH": str(DATA / "traces.db"),
        }
    )
    env.update(deployment)
    return env


def wait_for_postgres(url_text: str) -> None:
    # Unlike the Mac helper, do not log host/port extracted from the env file.
    try:
        asyncio.run(asyncio.wait_for(common._select_one(url_text), timeout=60.0))
    except Exception:
        raise Stop(common.NOT_YET, "PostgreSQL did not accept the service login") from None


def main(args: list[str] | None = None) -> int:
    stage = "env file"
    try:
        if sys.platform != "win32":
            raise Stop(REFUSE, "this launcher requires Windows")
        deployment = read_service_env(service_env_path(sys.argv[1:] if args is None else args))
        env = api_environment(deployment)
        # Settings and pre-flight clients see exactly the child's environment.
        os.environ.clear()
        os.environ.update(env)
        stage = "deployment values (secrets, paths, index and reranker SHA-256)"
        check_values(deployment)
        stage = "API port"
        if common.port_taken(common.HOST, common.PORT):
            raise Stop(REFUSE, "API port is occupied")
        stage = "PostgreSQL login"
        wait_for_postgres(env["DATABASE_URL"])
        from config.settings import Settings

        settings = Settings()
        if deployment.get("LLM_PROVIDER_PROFILE") != "codex-only":
            stage = "Ollama availability and default model"
            common.check_ollama(
                str(settings.ollama_base_url).rstrip("/"), settings.ollama_model_name
            )
        stage = "settings validation"
        common.validate(settings)
        stage = "runtime data directory"
        DATA.mkdir(parents=True, exist_ok=True)
        argv = [
            PY,
            "-m",
            "uvicorn",
            "api.app:app",
            "--host",
            common.HOST,
            "--port",
            str(common.PORT),
            "--workers",
            "1",
        ]
        stage = "uvicorn child"
        common.say("starting uvicorn api.app:app on 127.0.0.1:8002, one worker")
        return subprocess.run(argv, cwd=ROOT, env=env, shell=False, check=False).returncode
    except Stop as stop:
        # Shared checks can include a path/host in their exception. Never print that text.
        common.say(f"start check failed: {stage}")
        return common.NOT_YET if stop.code == common.NOT_YET else REFUSE
    except Exception:
        common.say(f"start failed: {stage}")
        return REFUSE


if __name__ == "__main__":
    sys.exit(main())

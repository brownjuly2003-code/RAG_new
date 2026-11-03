"""Write the launcher's external UTF-8/LF env file; print key names, never values."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy.windows import _support as support  # noqa: E402
from deploy.windows import start  # noqa: E402

CODEX_GLOB = "**/codex.exe"


def parser() -> argparse.ArgumentParser:
    result = support.parser(__doc__ or "")
    result.add_argument(
        "--env-file", type=Path, help="Default: %%LOCALAPPDATA%%/rag-new/chat-service.env"
    )
    result.add_argument(
        "--codex-exe",
        type=Path,
        help="Native .exe, or discover exactly one under the npm Codex package",
    )
    result.add_argument("--codex-home", type=Path, help="Default: %%USERPROFILE%%/.codex-work")
    result.add_argument(
        "--admin-username",
        help="Required when creating secrets/service.json; ignored if the store exists",
    )
    return result


def codex_executable(explicit: Path | None) -> Path:
    if explicit is not None:
        if (
            not explicit.is_absolute()
            or explicit.suffix.lower() != ".exe"
            or not explicit.is_file()
        ):
            raise support.DeploymentError("--codex-exe must name an existing absolute native .exe")
        return explicit
    appdata = os.environ.get("APPDATA", "")
    if not appdata or not Path(appdata).is_absolute():
        raise support.DeploymentError("Supply --codex-exe or an absolute APPDATA for discovery")
    package = Path(appdata) / "npm/node_modules/@openai/codex"
    matches = [path for path in package.glob(CODEX_GLOB) if path.is_file()]
    if len(matches) != 1:
        raise support.DeploymentError(
            "Codex discovery requires exactly one match; supply --codex-exe"
        )
    return matches[0]


def codex_home(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    profile = os.environ.get("USERPROFILE", "")
    if not profile:
        raise support.DeploymentError("Supply --codex-home or USERPROFILE")
    return Path(profile) / ".codex-work"


def load_secrets(paths: support.Paths, admin_username: str | None) -> dict[str, Any]:
    if not paths.service_store.exists() and not admin_username:
        raise support.DeploymentError(
            "--admin-username is required when secrets/service.json does not exist"
        )
    return support.secret_store(
        paths.service_store,
        lambda: {
            "jwt_secret": support.random_secret(48),
            "session_secret_key": support.random_secret(48),
            "db_encryption_key": support.random_secret(32),
            "admin_username": admin_username,
            "admin_password": support.random_secret(18),
        },
    )


def deployment_values(
    paths: support.Paths,
    pg: dict[str, Any],
    service: dict[str, Any],
    binary: Path,
    home: Path,
    admin_hash: str,
) -> dict[str, str]:
    return {
        "LLM_PROVIDER_PROFILE": "codex-only",
        "CODEX_BINARY": binary.as_posix(),
        "CODEX_HOME": home.as_posix(),
        "HF_HOME": paths.hf.as_posix(),
        "DATABASE_URL": f"postgresql+asyncpg://{quote(pg['app_role'], safe='')}:{quote(pg['app_password'], safe='')}@127.0.0.1:{int(pg['port'])}/{quote(pg['database'], safe='')}",
        "VECTORDB_CHROMA_DIR": paths.index.as_posix(),
        "RAG_RERANKER_ONNX": paths.onnx.as_posix(),
        "JWT_SECRET": service["jwt_secret"],
        "SESSION_SECRET_KEY": service["session_secret_key"],
        "DB_ENCRYPTION_KEY": service["db_encryption_key"],
        "ADMIN_USERNAME": service["admin_username"],
        "ADMIN_PASSWORD_HASH": admin_hash,
        "ADMIN_DEFAULT_TENANT": "aircargo",
        "CORS_ORIGINS": "http://127.0.0.1:8002",
    }


def write_env_file(path: Path, values: dict[str, str]) -> None:
    start.check_env_path(path)
    body = "".join(f"{key}={value}\n" for key, value in values.items()).encode("utf-8")
    if start.parse_service_env(body) != values:
        raise start.Stop(start.REFUSE, "env values must occupy exactly one line each")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Secure an empty new file before putting secrets in it; preserve existing contents
    # until both the format and ACL checks have succeeded.
    path.touch(exist_ok=True)
    support.restrict(path)
    path.write_bytes(body)


def main() -> int:
    args = parser().parse_args()
    support.require_windows()
    paths = support.Paths(args.root)
    env_file = start.service_env_path([str(args.env_file)] if args.env_file else [])
    start.check_env_path(env_file)
    binary, home = codex_executable(args.codex_exe), codex_home(args.codex_home)
    pg = json.loads(paths.pg_store.read_text(encoding="utf-8"))
    service = load_secrets(paths, args.admin_username)
    import bcrypt

    admin_hash = bcrypt.hashpw(
        service["admin_password"].encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("ascii")
    values = deployment_values(paths, pg, service, binary, home, admin_hash)
    start.check_values(values)
    write_env_file(env_file, values)
    print("wrote env keys:", ", ".join(values))
    return 0


if __name__ == "__main__":
    sys.exit(support.cli(main))

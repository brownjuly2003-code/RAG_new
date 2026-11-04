"""Create or start the product's own PostgreSQL 16 cluster; reuse stored secrets."""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy.windows import _support as support  # noqa: E402


def parser() -> argparse.ArgumentParser:
    result = support.parser(__doc__ or "")
    result.add_argument("--pg-bin", type=Path, default=Path("C:/Program Files/PostgreSQL/16/bin"))
    result.add_argument(
        "--database",
        type=database_name,
        help="Database to provision (default: stored product database, rag_new)",
    )
    return result


def database_name(value: str) -> str:
    if re.fullmatch(r"[a-z][a-z0-9_]{0,62}", value) is None:
        raise ValueError("database must match ^[a-z][a-z0-9_]{0,62}$")
    return value


def load_secrets(paths: support.Paths) -> dict[str, Any]:
    if (paths.pgdata / "PG_VERSION").exists() and not paths.pg_store.exists():
        raise support.DeploymentError(
            "Existing cluster has no secrets store; restore it before proceeding"
        )
    return support.secret_store(
        paths.pg_store,
        lambda: {
            "superuser": "postgres",
            "superuser_password": support.random_secret(32),
            "app_role": "rag_app",
            "app_password": support.random_secret(32),
            "database": "rag_new",
            "port": 55432,
        },
    )


def prepare(paths: support.Paths, pg_bin: Path, *, database: str | None = None) -> None:
    if database is not None:
        database_name(database)
    stored = load_secrets(paths)
    version = paths.pgdata / "PG_VERSION"
    if version.exists() and version.read_text(encoding="utf-8").strip() != "16":
        raise support.DeploymentError("Existing cluster must be PostgreSQL 16")
    if not version.exists():
        # The password file inherits the user-only secrets directory ACL.
        with tempfile.TemporaryDirectory(dir=paths.secrets) as temp:
            password_file = Path(temp) / "password"
            password_file.write_bytes(stored["superuser_password"].encode("utf-8"))
            support.run(
                [
                    pg_bin / "initdb.exe",
                    "-D",
                    paths.pgdata,
                    "-U",
                    stored["superuser"],
                    "--auth=scram-sha-256",
                    f"--pwfile={password_file}",
                    "-E",
                    "UTF8",
                    "--no-locale",
                ]
            )
        with (paths.pgdata / "postgresql.conf").open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                f"\n# RAG_new product cluster\nport = {int(stored['port'])}\nlisten_addresses = '127.0.0.1'\n"
            )
        print("initdb done")
    status = support.run([pg_bin / "pg_ctl.exe", "-D", paths.pgdata, "status"], check=False)
    if status.returncode:
        # A transient inherited console causes new backends to fail with 0xC0000142.
        support.detach(
            [str(pg_bin / "pg_ctl.exe"), "-D", str(paths.pgdata), "-l", str(paths.pglog), "start"]
        )

    env = dict(os.environ, PGPASSWORD=stored["superuser_password"])
    psql = [
        pg_bin / "psql.exe",
        "-h",
        "127.0.0.1",
        "-p",
        str(stored["port"]),
        "-U",
        stored["superuser"],
        "-d",
        "postgres",
        "-X",
        "-v",
        "ON_ERROR_STOP=1",
        "-tA",
    ]
    for _ in range(30):
        if support.run(psql, env=env, input="SELECT 1;\n", check=False).returncode == 0:
            break
        time.sleep(1)
    else:
        raise support.DeploymentError(
            "PostgreSQL did not accept the stored login within 30 seconds"
        )

    # SQL goes over stdin, never password-bearing argv. Escape identifiers and literals.
    def literal(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    def identifier(value: str) -> str:
        return '"' + value.replace('"', '""') + '"'

    role, database = stored["app_role"], stored["database"] if database is None else database
    if (
        support.run(
            psql, env=env, input=f"SELECT 1 FROM pg_roles WHERE rolname={literal(role)};\n"
        ).stdout.strip()
        != "1"
    ):
        support.run(
            psql,
            env=env,
            input=f"CREATE ROLE {identifier(role)} LOGIN PASSWORD {literal(stored['app_password'])};\n",
        )
        print("role created")
    if (
        support.run(
            psql, env=env, input=f"SELECT 1 FROM pg_database WHERE datname={literal(database)};\n"
        ).stdout.strip()
        != "1"
    ):
        support.run(
            psql,
            env=env,
            input=f"CREATE DATABASE {identifier(database)} OWNER {identifier(role)} ENCODING 'UTF8';\n",
        )
        print("database created")
    support.run(
        [
            pg_bin / "psql.exe",
            "-h",
            "127.0.0.1",
            "-p",
            str(stored["port"]),
            "-U",
            role,
            "-d",
            database,
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-tAc",
            "SELECT 1",
        ],
        env=dict(os.environ, PGPASSWORD=stored["app_password"]),
    )
    print("app login ok")


def main() -> int:
    args = parser().parse_args()
    support.require_windows()
    prepare(support.Paths(args.root), args.pg_bin, database=args.database)
    return 0


if __name__ == "__main__":
    sys.exit(support.cli(main))

"""Mac-only Phase D.5 cold-start and memory runner; not production code."""

from __future__ import annotations

import gzip
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import numpy as np

from scripts.pgvector_cold_start import (
    _ArgumentParser,
    build_report,
    compare_d1,
    text_digest,
    trial_order,
    validate_trial_record,
)
from scripts.pgvector_spike_db import TENANT, setup

ROOT = Path(__file__).resolve().parents[1]
TRIALS = 7
EXPECTED_CHUNKS = 5589
EXPECTED_CASES = 115
DIM = 1024
COLLECTION = "d5_aircargo"
BATCH = 500
TOP_K = 20
EF_SEARCH = 100
CHILD_TIMEOUT_S = 900
DROP_RETRY_S = 30
SCHEMA_VERSION = "d5-pgvector-cold-start-v1"
ARCHIVE = ROOT / "evaluation/gr1b-4436d61-graph-chunks.json.gz"
CASE_FILES = (
    ROOT / "evaluation/curated_cases_aircargo.jsonl",
    ROOT / "evaluation/curated_cases_aircargo_gr_multihop.jsonl",
)
D1_REPORT = ROOT / "evaluation/d1-pgvector-prererank.json"
SOURCE_FILES = (
    "scripts/pgvector_cold_start_run.py",
    "scripts/pgvector_cold_start.py",
    "scripts/pgvector_spike.py",
    "scripts/pgvector_spike_db.py",
    "scripts/pgvector_ann.py",
    "vectordb/manager.py",
    "vectordb/_base_manager.py",
)


class RunnerError(RuntimeError):
    def __init__(
        self,
        stage: str,
        *,
        arm: str | None = None,
        trial: int | None = None,
        detail: str,
    ) -> None:
        self.stage = stage
        self.arm = arm
        self.trial = trial
        self.detail = detail
        parts = [stage]
        if arm is not None:
            parts.append(arm)
        if trial is not None:
            parts.append(f"trial {trial}")
        parts.append(detail)
        super().__init__(": ".join(parts))


class _ChildFailure(RuntimeError):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_code_base() -> str:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    if status.stdout.strip():
        raise RuntimeError("tracked git worktree must be clean")
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise RuntimeError("unexpected git revision")
    return revision


def _normalize_admin_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        if not re.fullmatch(r"postgresql(?:\+[A-Za-z0-9_]+)?", parts.scheme):
            raise ValueError
        if parts.hostname not in ("localhost", "127.0.0.1") or parts.port != 55432:
            raise ValueError
        if not parts.netloc or parts.fragment:
            raise ValueError
        normalized = urlunsplit(("postgresql", parts.netloc, parts.path, parts.query, ""))
        import psycopg2

        parsed = psycopg2.extensions.parse_dsn(normalized)
        allowed = {
            "user",
            "password",
            "host",
            "port",
            "dbname",
            "sslmode",
            "connect_timeout",
            "application_name",
        }
        if not set(parsed) <= allowed:
            raise ValueError
        if parsed.get("host") not in ("localhost", "127.0.0.1"):
            raise ValueError
        if parsed.get("port") != "55432":
            raise ValueError
        return normalized
    except Exception:
        raise ValueError("administrative URL must use local PostgreSQL port 55432") from None


def _check_libpq_environment() -> None:
    for name in ("PGHOST", "PGHOSTADDR", "PGPORT", "PGSERVICE", "PGSERVICEFILE", "PGSYSCONFDIR"):
        if name in os.environ:
            raise ValueError(f"libpq environment variable is set: {name}")


def _scratch_name(token_hex=secrets.token_hex) -> str:
    token = token_hex(8)
    if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{16}", token):
        raise ValueError("invalid scratch name token")
    return "rag_spike_d5_" + token


def _decode_scalar(value) -> str:
    item = value.item()
    return item.decode("utf-8") if isinstance(item, bytes) else str(item)


def _load_inputs(
    archive,
    vectors_path,
    queries_path,
    case_files,
    d1_report,
    expected_chunks=EXPECTED_CHUNKS,
    expected_cases=EXPECTED_CASES,
) -> dict:
    archive = Path(archive)
    vectors_path = Path(vectors_path)
    queries_path = Path(queries_path)
    case_files = tuple(Path(path) for path in case_files)
    d1_report = Path(d1_report)
    if len(case_files) != 2 or len({path.name for path in case_files}) != 2:
        raise ValueError("two distinct case files are required")
    with gzip.open(archive, "rb") as stream:
        decompressed = stream.read()
    chunks = json.loads(decompressed)["chunks"]
    texts = [chunk["page_content"] for chunk in chunks]
    digest = text_digest(texts)
    cases = [
        json.loads(line)
        for path in case_files
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(texts) != expected_chunks:
        raise ValueError(f"chunk count {len(texts)} differs from {expected_chunks}")
    if len(cases) != expected_cases:
        raise ValueError(f"case count {len(cases)} differs from {expected_cases}")
    if any("case_id" not in case or "query" not in case for case in cases):
        raise ValueError("case_id or query missing")
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("case_id values must be unique")
    with np.load(vectors_path, allow_pickle=False) as cache:
        if _decode_scalar(cache["chunk_text_digest"]) != digest:
            raise ValueError("chunk text digest mismatch")
        if _decode_scalar(cache["embedding_model"]) != "BAAI/bge-m3":
            raise ValueError("unexpected embedding model")
        vectors = cache["embeddings"]
    queries = np.load(queries_path, allow_pickle=False)
    if vectors.shape != (expected_chunks, DIM) or queries.shape != (expected_cases, DIM):
        raise ValueError("unexpected embedding shapes")
    if not np.isfinite(vectors).all() or not np.isfinite(queries).all():
        raise ValueError("embeddings must be finite")
    d1 = json.loads(d1_report.read_text(encoding="utf-8"))
    input_sha256 = {
        path.name: _sha256(path) for path in (archive, vectors_path, queries_path, *case_files)
    }
    input_sha256["ab_phase2_G2_graph_chunks.json"] = hashlib.sha256(decompressed).hexdigest()
    input_sha256[d1_report.name] = _sha256(d1_report)
    for path in (vectors_path, queries_path, *case_files):
        if input_sha256[path.name] != d1["input_sha256"].get(path.name):
            raise ValueError(f"input D.1 did not use: {path.name}")
    if input_sha256["ab_phase2_G2_graph_chunks.json"] != d1["input_sha256"].get(
        "ab_phase2_G2_graph_chunks.json"
    ):
        raise ValueError(f"input D.1 did not use: {archive.name}")
    return {
        "texts": texts,
        "vectors": vectors,
        "cases": cases,
        "text_digest": digest,
        "input_sha256": input_sha256,
        "d1": d1,
    }


def _connect_admin(dsn: str, dbname: str):
    import psycopg2

    try:
        parsed = psycopg2.extensions.parse_dsn(dsn)
        parsed.pop("dbname", None)
        return psycopg2.connect(**parsed, dbname=dbname)
    except Exception as exc:
        raise RuntimeError(f"admin connection: {type(exc).__name__}") from None


class _ScratchExists(ValueError):
    pass


def _check_absent(dsn: str, name: str, connection_factory=_connect_admin) -> None:
    connection = connection_factory(dsn, "postgres")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=%s)", (name,))
            database_exists = bool(cursor.fetchone()[0])
            cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=%s)", (name,))
            role_exists = bool(cursor.fetchone()[0])
        if database_exists or role_exists:
            raise _ScratchExists("scratch database or role already exists")
    finally:
        connection.close()


def _directory_size(directory: Path) -> int:
    total = 0
    for current, dirs, files in os.walk(directory, followlinks=False):
        dirs[:] = [name for name in dirs if not Path(current, name).is_symlink()]
        for name in files:
            info = Path(current, name).stat(follow_symlinks=False)
            if stat.S_ISREG(info.st_mode):
                total += info.st_size
    return total


def _collect_database_facts(connection) -> tuple[str, str, dict, dict]:
    settings = {}
    with connection.cursor() as cursor:
        cursor.execute("SELECT version()")
        postgres = str(cursor.fetchone()[0])
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
        pgvector = str(cursor.fetchone()[0])
        for name in ("shared_buffers", "work_mem", "maintenance_work_mem", "effective_cache_size"):
            cursor.execute("SELECT current_setting(%s)", (name,))
            settings[name] = str(cursor.fetchone()[0])
        cursor.execute("SELECT pg_database_size(current_database())")
        database_bytes = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT c.oid::regclass::text, pg_relation_size(c.oid) "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relkind IN ('r','i','p','I') "
            "ORDER BY c.oid::regclass::text"
        )
        relations = {str(name): int(size) for name, size in cursor.fetchall()}
        cursor.execute(
            "SELECT pg_total_relation_size(reltoastrelid) "
            "FROM pg_class WHERE oid='public.spike_chunks'::regclass"
        )
        toast_bytes = int(cursor.fetchone()[0])
    connection.commit()
    return (
        postgres,
        pgvector,
        settings,
        {
            "database_bytes": database_bytes,
            "relations_bytes": relations,
            "spike_chunks_toast_bytes": toast_bytes,
        },
    )


def _sysctl(name: str) -> str:
    return subprocess.run(
        ["sysctl", "-n", name],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()


def _versions() -> dict[str, str]:
    return {
        name: importlib.metadata.version(name)
        for name in ("numpy", "chromadb", "rank-bm25", "psycopg2-binary")
    }


def _child_env(dsn: str | None = None) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("RESOLUTION_", "DATABASE_")) and key != "SPIKE_ADMIN_DSN"
    }
    env["ANONYMIZED_TELEMETRY"] = "False"
    if dsn is not None:
        env["SPIKE_ADMIN_DSN"] = dsn
    return env


def _run_child(args: list[str], label: str, spawner, clock, dsn=None) -> tuple[dict, float]:
    started = clock()
    try:
        result = spawner(
            args,
            capture_output=True,
            text=True,
            timeout=CHILD_TIMEOUT_S,
            cwd=ROOT,
            env=_child_env(dsn),
        )
    except Exception as exc:
        raise _ChildFailure(type(exc).__name__) from None
    wall_ms = 1000 * (clock() - started)
    last_line = result.stdout.splitlines()[-1] if result.stdout.splitlines() else ""
    try:
        payload = json.loads(last_line)
    except (ValueError, TypeError):
        payload = None
    if result.returncode != 0:
        error = payload.get("error") if isinstance(payload, dict) else None
        if (
            isinstance(error, str)
            and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_ ]*: [A-Za-z_][A-Za-z0-9_]*", error)
            and _safe_exception_message(RuntimeError(error)) is not None
        ):
            raise _ChildFailure(error)
        exit_detail = (
            f"exit code {result.returncode}"
            if type(result.returncode) is int
            else "invalid exit code"
        )
        raise _ChildFailure(exit_detail)
    if not isinstance(payload, dict) or "error" in payload:
        raise ValueError(f"{label}: invalid child JSON")
    return payload, wall_ms


def _cleanup(
    dsn: str,
    name: str,
    directory: Path,
    created: bool,
    *,
    connection_factory=_connect_admin,
    remove_dir=shutil.rmtree,
    clock=time.monotonic,
    sleep=time.sleep,
) -> dict[str, bool]:
    flags = {"database_dropped": False, "role_dropped": False, "chroma_dir_removed": not created}
    connection = None
    try:
        connection = connection_factory(dsn, "postgres")
        connection.autocommit = True
        started = clock()
        while True:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
                flags["database_dropped"] = True
                break
            except Exception as exc:
                if getattr(exc, "pgcode", None) != "55006" or clock() - started >= DROP_RETRY_S:
                    break
                sleep(1)
        try:
            with connection.cursor() as cursor:
                cursor.execute(f'DROP ROLE IF EXISTS "{name}"')
            flags["role_dropped"] = True
        except Exception:
            pass
    except Exception:
        pass
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
        if created:
            try:
                remove_dir(directory)
                flags["chroma_dir_removed"] = True
            except Exception:
                pass
    return flags


def _mkdir(path: Path) -> None:
    path.mkdir(exist_ok=False)


def _load_average() -> str:
    return ", ".join(str(value) for value in os.getloadavg())


def run_measurement(
    output,
    *,
    vectors_path,
    queries_path,
    archive=ARCHIVE,
    case_files=CASE_FILES,
    d1_report=D1_REPORT,
    expected_chunks=EXPECTED_CHUNKS,
    expected_cases=EXPECTED_CASES,
    trials=TRIALS,
    temp_dir=None,
    code_base_provider=_git_code_base,
    spawner=subprocess.run,
    connection_factory=_connect_admin,
    setup_fn=setup,
    directory_creator=_mkdir,
    remove_dir=shutil.rmtree,
    host_reader=_sysctl,
    token_hex=secrets.token_hex,
    clock=time.perf_counter,
    sleep=time.sleep,
    versions_provider=_versions,
    load_reader=_load_average,
    cleanup_clock=time.monotonic,
    cleanup_fn=_cleanup,
) -> dict:
    output = Path(output)
    if output.exists():
        raise FileExistsError("output path already exists")
    _check_libpq_environment()
    code_base = code_base_provider()
    dsn = _normalize_admin_url(os.environ.get("RESOLUTION_ADMIN_DATABASE_URL", ""))
    inputs = _load_inputs(
        archive, vectors_path, queries_path, case_files, d1_report, expected_chunks, expected_cases
    )
    name = _scratch_name(token_hex)
    directory = Path(temp_dir if temp_dir is not None else tempfile.gettempdir()) / name
    source_sha256 = {path: _sha256(ROOT / path) for path in SOURCE_FILES}
    versions = versions_provider()
    try:
        _check_absent(dsn, name, connection_factory)
    except _ScratchExists:
        raise
    except Exception as exc:
        raise RuntimeError(f"existence check: {type(exc).__name__}") from None

    created = False
    records = []
    stage = "directory"
    current_arm = None
    current_trial = None
    unstable_path = None
    failure = None
    try:
        directory_creator(directory)
        created = True
        stage = "build"
        command = [
            sys.executable,
            "-m",
            "scripts.pgvector_cold_start",
            "--build-collection",
            "--chroma-dir",
            str(directory),
            "--collection",
            COLLECTION,
            "--archive",
            str(archive),
            "--vectors",
            str(vectors_path),
            "--text-digest",
            inputs["text_digest"],
        ]
        built, _ = _run_child(command, stage, spawner, clock)
        if (
            set(built) != {"build_ms"}
            or isinstance(built["build_ms"], bool)
            or not isinstance(built["build_ms"], (int, float))
            or not math.isfinite(built["build_ms"])
            or built["build_ms"] < 0
        ):
            raise ValueError("invalid build result")
        chroma_dir_bytes = _directory_size(directory)
        stage = "setup"
        setup_start = clock()
        connection = setup_fn(dsn, name, inputs["texts"], inputs["vectors"])
        postgres_setup_ms = 1000 * (clock() - setup_start)
        try:
            postgres, pgvector, server_settings, sizes = _collect_database_facts(connection)
        finally:
            connection.close()
        stage = "host facts"
        host = {
            "physical_memory_bytes": int(host_reader("hw.memsize")),
            "cpu_count": os.cpu_count(),
        }
        host_load = {
            "before": {"load_average": load_reader(), "swap_usage": host_reader("vm.swapusage")}
        }
        for trial, arm, position in trial_order(trials):
            stage = "trial"
            current_arm = arm
            current_trial = trial
            if arm == "chroma_bm25":
                command = [
                    sys.executable,
                    "-m",
                    "scripts.pgvector_cold_start",
                    "--trial",
                    arm,
                    "--chroma-dir",
                    str(directory),
                    "--collection",
                    COLLECTION,
                    "--queries",
                    str(queries_path),
                ]
                for case_file in case_files:
                    command.extend(("--cases", str(case_file)))
                command.extend(("--text-digest", inputs["text_digest"]))
                trial_dsn = None
            else:
                command = [
                    sys.executable,
                    "-m",
                    "scripts.pgvector_cold_start",
                    "--trial",
                    arm,
                    "--database",
                    name,
                    "--queries",
                    str(queries_path),
                ]
                for case_file in case_files:
                    command.extend(("--cases", str(case_file)))
                trial_dsn = dsn
            payload, wall_ms = _run_child(command, stage, spawner, clock, trial_dsn)
            record = {**payload, "trial": trial, "position": position, "process_wall_ms": wall_ms}
            validate_trial_record(record, arm, expected_cases)
            records.append(record)
        stage = "host facts"
        current_arm = None
        current_trial = None
        host_load["after"] = {
            "load_average": load_reader(),
            "swap_usage": host_reader("vm.swapusage"),
        }
        stage = "stability"
        first = {
            path: rows
            for record in records
            if record["trial"] == 0
            for path, rows in record["rankings"].items()
        }
        for record in records:
            for path, rows in record["rankings"].items():
                if rows != first[path]:
                    unstable_path = path
                    raise ValueError("ranking changed")
        stage = "D.1 cross-check"
        d1_run = inputs["d1"]["runs"][0]
        cross_check = {
            "chroma_bm25": compare_d1(first["chroma_fused"], d1_run["chroma_bm25"]["rankings"]),
            "postgres": compare_d1(first["postgres_fused"], d1_run["postgres"]["rankings"]),
        }
    except Exception as exc:
        if isinstance(exc, _ChildFailure):
            detail = exc.detail
        elif stage == "stability" and unstable_path is not None:
            detail = f"ranking path {unstable_path}: {type(exc).__name__}"
        else:
            detail = type(exc).__name__
        if _safe_exception_message(RuntimeError(detail)) is None:
            detail = "Exception"
        failure = RunnerError(
            stage,
            arm=current_arm if stage == "trial" else None,
            trial=current_trial if stage == "trial" else None,
            detail=detail,
        )
        traceback.clear_frames(exc.__traceback__)
    finally:
        cleanup = cleanup_fn(
            dsn,
            name,
            directory,
            created,
            connection_factory=connection_factory,
            remove_dir=remove_dir,
            clock=cleanup_clock,
            sleep=sleep,
        )
    if failure is not None:
        raise failure from None
    context = {
        "code_base": code_base,
        "database": name,
        "input_sha256": inputs["input_sha256"],
        "source_sha256": source_sha256,
        "versions": versions,
        "python": platform.python_version(),
        "platform": sys.platform,
        "host": host,
        "postgres": postgres,
        "pgvector": pgvector,
        "server_settings": server_settings,
        "setup": {
            "chroma_build_ms": built["build_ms"],
            "chroma_dir_bytes": chroma_dir_bytes,
            "postgres_setup_ms": postgres_setup_ms,
            **sizes,
        },
        "host_load": host_load,
        "d1_cross_check": cross_check,
        "chunks": expected_chunks,
        "cases": expected_cases,
        "trials": trials,
        "collection": COLLECTION,
        "tenant": TENANT,
    }
    report = build_report(context, records, cleanup)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return report


def _safe_exception_message(exc: Exception) -> str | None:
    message = str(exc)
    raw_url = os.environ.get("RESOLUTION_ADMIN_DATABASE_URL", "")
    sensitive = {raw_url} if raw_url else set()
    try:
        parts = urlsplit(raw_url)
        if parts.scheme.startswith("postgresql+"):
            sensitive.add(urlunsplit(("postgresql", parts.netloc, parts.path, parts.query, "")))
        for value in (parts.username, parts.password):
            if value:
                sensitive.update((value, unquote(value)))
    except Exception:
        pass
    try:
        normalized = _normalize_admin_url(raw_url)
        import psycopg2

        parsed = psycopg2.extensions.parse_dsn(normalized)
        for value in (parsed.get("user"), parsed.get("password")):
            if value:
                sensitive.update((value, quote(value, safe="")))
    except Exception:
        pass
    return None if any(value and value in message for value in sensitive) else message


def main(argv=None, *, measurement_fn=run_measurement) -> int:
    parser = _ArgumentParser(description=__doc__)
    for option in ("vectors", "queries", "output"):
        parser.add_argument("--" + option, required=True)
    try:
        args = parser.parse_args(argv)
        report = measurement_fn(args.output, vectors_path=args.vectors, queries_path=args.queries)
        print(json.dumps({"status": report["status"], "database": report["database"]}))
        return 0
    except RunnerError as exc:
        print(
            json.dumps(
                {
                    "error": "runner",
                    "stage": exc.stage,
                    "arm": exc.arm,
                    "trial": exc.trial,
                    "detail": exc.detail,
                }
            )
        )
        return 2
    except Exception as exc:
        payload = {"error": f"runner: {type(exc).__name__}"}
        message = _safe_exception_message(exc)
        if message is not None:
            payload["message"] = message
        print(json.dumps(payload))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

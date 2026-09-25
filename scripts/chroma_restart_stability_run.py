"""Run the pre-registered Chroma restart measurement on macOS."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from scripts.chroma_restart_stability import (
    TRIALS,
    build_report,
    validate_build_record,
    validate_trial_record,
)
from scripts.pgvector_cold_start import _ArgumentParser
from scripts.pgvector_cold_start_run import _git_code_base, _load_inputs, _sysctl

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "evaluation/gr1b-4436d61-graph-chunks.json.gz"
CASE_FILES = (
    ROOT / "evaluation/curated_cases_aircargo.jsonl",
    ROOT / "evaluation/curated_cases_aircargo_gr_multihop.jsonl",
)
D1_REPORT = ROOT / "evaluation/d1-pgvector-prererank.json"
SOURCE_FILES = (
    "scripts/chroma_restart_stability.py",
    "scripts/chroma_restart_stability_run.py",
    "scripts/pgvector_cold_start.py",
    "scripts/pgvector_cold_start_run.py",
    "vectordb/manager.py",
    "vectordb/_base_manager.py",
    "vectordb/index_staging.py",
    "config/settings.py",
)
CHILD_TIMEOUT_S = 900


def _versions():
    return {
        name: importlib.metadata.version(name)
        for name in ("numpy", "chromadb", "langchain-chroma", "langchain-core", "rank-bm25")
    }


def _source_sha256(commit, *, git_runner=subprocess.run):
    return {
        path: hashlib.sha256(
            git_runner(
                ["git", "show", f"{commit}:{path}"],
                cwd=ROOT,
                capture_output=True,
                check=True,
                timeout=30,
            ).stdout
        ).hexdigest()
        for path in SOURCE_FILES
    }


def _utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_average():
    return os.getloadavg()


def _mkdir(path):
    path.mkdir()


def _run_child(args, label, spawner, environ, clock):
    child_env = dict(environ)
    child_env["ANONYMIZED_TELEMETRY"] = "False"
    started = clock()
    try:
        result = spawner(
            args,
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=child_env,
            timeout=CHILD_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{label}: child timed out after {CHILD_TIMEOUT_S} seconds") from exc
    elapsed_ms = 1000 * (clock() - started)
    lines = result.stdout.splitlines() if isinstance(result.stdout, str) else []
    try:
        payload = json.loads(lines[-1]) if lines else None
    except ValueError:
        payload = None
    stderr = getattr(result, "stderr", "")
    stderr_tail = (
        " | " + stderr[-2000:].replace("\r\n", " | ").replace("\r", " | ").replace("\n", " | ")
        if stderr
        else ""
    )
    if result.returncode != 0:
        detail = payload.get("error") if isinstance(payload, dict) else None
        raise RuntimeError(
            f"{label}: {detail or f'child exit code {result.returncode}'}{stderr_tail}"
        )
    if not isinstance(payload, dict) or "error" in payload:
        raise ValueError(f"{label}: invalid child JSON object{stderr_tail}")
    return payload, elapsed_ms


def _child_args(mode, directory, vectors_path, queries_path, digest, *, trial=None):
    args = [sys.executable, "-m", "scripts.chroma_restart_stability", mode]
    if trial is not None:
        args.extend(("--trial-index", str(trial)))
    args.extend(
        (
            "--directory",
            str(directory),
            "--archive",
            str(ARCHIVE),
            "--vectors",
            str(vectors_path),
            "--queries",
            str(queries_path),
        )
    )
    for case_file in CASE_FILES:
        args.extend(("--cases", str(case_file)))
    args.extend(("--text-digest", digest))
    return args


def run_measurement(
    output,
    *,
    vectors_path,
    queries_path,
    platform_name=None,
    environ=None,
    input_loader=_load_inputs,
    code_base_provider=_git_code_base,
    temp_dir=None,
    directory_creator=_mkdir,
    remove_dir=shutil.rmtree,
    spawner=subprocess.run,
    token_hex=secrets.token_hex,
    source_sha_provider=_source_sha256,
    versions_provider=_versions,
    host_reader=_sysctl,
    load_reader=_load_average,
    utc_now=_utc_now,
    clock=time.perf_counter,
):
    active_platform = sys.platform if platform_name is None else platform_name
    active_env = os.environ if environ is None else environ
    if active_platform != "darwin" or active_env.get("ANONYMIZED_TELEMETRY") != "False":
        raise ValueError("macOS and ANONYMIZED_TELEMETRY=False are required")
    output = Path(output)
    if output.exists():
        raise FileExistsError("output path already exists")
    vectors_path = Path(vectors_path).resolve()
    queries_path = Path(queries_path).resolve()
    inputs = input_loader(ARCHIVE, vectors_path, queries_path, CASE_FILES, D1_REPORT)
    commit = code_base_provider()

    token = token_hex(8)
    if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{16}", token):
        raise ValueError("invalid temporary directory token")
    directory = Path(tempfile.gettempdir() if temp_dir is None else temp_dir) / (
        f"chroma_restart_{token}"
    )
    if directory.exists():
        raise FileExistsError("temporary directory already exists")

    start_utc = utc_now()
    load_average_start = list(load_reader())
    source_sha256 = source_sha_provider(commit)
    versions = versions_provider()
    host = {
        "cpu_count": os.cpu_count(),
        "hw.model": host_reader("hw.model"),
        "hw.memsize": host_reader("hw.memsize"),
    }
    created = False
    directory_removed = False
    build = None
    records = []
    try:
        directory_creator(directory)
        created = True
        build, build_wall_ms = _run_child(
            _child_args("build", directory, vectors_path, queries_path, inputs["text_digest"]),
            "build",
            spawner,
            active_env,
            clock,
        )
        validate_build_record(build, len(inputs["texts"]), len(inputs["cases"]))
        build["process_wall_ms"] = build_wall_ms
        for trial in range(TRIALS):
            record, wall_ms = _run_child(
                _child_args(
                    "trial",
                    directory,
                    vectors_path,
                    queries_path,
                    inputs["text_digest"],
                    trial=trial,
                ),
                f"trial {trial}",
                spawner,
                active_env,
                clock,
            )
            validate_trial_record(
                record, len(inputs["texts"]), len(inputs["cases"]), build["settings"]
            )
            records.append({**record, "trial": trial, "process_wall_ms": wall_ms})
    finally:
        if created:
            try:
                remove_dir(directory)
            except OSError:
                pass
            directory_removed = not directory.exists()

    context = {
        "code_commit": commit,
        "input_sha256": inputs["input_sha256"],
        "source_sha256": source_sha256,
        "versions": versions,
        "python": platform.python_version(),
        "platform": active_platform,
        "host": host,
        "load_average_start": load_average_start,
        "start_utc": start_utc,
        "end_utc": utc_now(),
    }
    report = build_report(context, build, records, directory_removed=directory_removed)
    serialized = json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    output_created = False
    try:
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            output_created = True
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        if output_created:
            output.unlink(missing_ok=True)
        raise
    return report


def main(argv=None, *, measurement_fn=run_measurement):
    parser = _ArgumentParser(description=__doc__)
    for option in ("vectors", "queries", "output"):
        parser.add_argument("--" + option, required=True)
    try:
        args = parser.parse_args(argv)
        report = measurement_fn(args.output, vectors_path=args.vectors, queries_path=args.queries)
        print(json.dumps({"status": report["status"], "output": args.output}))
        return 0
    except Exception as exc:
        print(str(exc).replace("\r", " ").replace("\n", " "))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

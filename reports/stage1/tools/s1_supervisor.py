"""Mac-side supervisor: the stage-1 index generation of the four corpora (PLAN.md stage 1, item 4).

Usage (detached, inside a clean `git archive` of the code): python s1_supervisor.py <snapshot> <sha>

Adapted from the supervisor that built the first generation of the external bases
(/Users/julia/RAG_new_external/ext_supervisor.py, code 36f1167): the same embedding and index
steps, a new data root beside the old one, aircargo added, and the chunks cut here by the
snapshot's code. For each base in turn — aircargo, conditionalqa, multihoprag, wixqa:

  prepare  copy the corpus and its manifest (and an external base's cases) from the first
           generation, or aircargo's corpus from its upload folder; the copy must equal the
           manifest
  chunks   scripts.external_base chunks (aircargo: scripts.corpus_chunks): the product's
           loader, select_chunks and contextual headers at the code defaults
  preserve scripts.external_base preserve (external bases): how the chunks hold the documents
           and every gold place; a chunk without a place or a lost gold alternative stops the run
  embed    scripts.production_embeddings: BGE-M3 at the pinned revision, on CPU; a checkpoint
           every 64 texts, an interrupted run goes on with --resume
  index    scripts.production_index into <data>/<base>/index, the collection the API names for
           the tenant, with the embedder manifest pinned for the T-65 index

A base whose index receipt exists is skipped, so the supervisor may be started again after a
stop. Before the first step and after the last, every guarded path is hashed: the first
generation, aircargo's upload folder, the T-65 index and checkpoint must stay as they were.

State: <data>/s1-state.json. Host samples every 60 s: <data>/s1-host.jsonl.
Stop: create <data>/s1-stop — the running step is ended at once and the supervisor exits with
status "stopped".
"""

import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

root = Path(sys.argv[1])
code_sha = sys.argv[2]
os.chdir(root)
data = Path("/Users/julia/RAG_new_external_s1")
first = Path("/Users/julia/RAG_new_external")
uploads = Path("/Users/julia/RAG_Support_Assistant/data/uploads/aircargo")
state_path = data / "s1-state.json"
monitor_path = data / "s1-host.jsonl"
stop_path = data / "s1-stop"
t65 = Path("/Users/julia/RAG_new_t65_embeddings_2851e3811508")
MANIFEST = t65 / ".tmp/t65-index-expected-manifest.json"
GUARDED = [
    uploads,
    t65 / ".tmp/t65-index-72fbd72",
    t65 / ".tmp/t65-verified-embeddings.npz",
    *(first / base for base in ("conditionalqa", "multihoprag", "wixqa")),
]
stage_py = "/Users/julia/RAG_Support_Assistant/.venv/bin/python"
tools_py = "/Users/julia/RAG_new_gr4_venv/bin/python"
SITE = "/Users/julia/RAG_new_mf_gate_site"
REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
BASES = ["aircargo", "conditionalqa", "multihoprag", "wixqa"]
AIRCARGO = {"tenant": "aircargo", "collection": "rag_docs_aircargo", "dated": "2026-10-18"}
WRITERS = (
    "scripts.production_parity|scripts.production_baseline|parity_supervisor"
    "|baseline_supervisor|pilot_supervisor|ext_supervisor|live_supervisor|pytest"
)
SAMPLE_SEC = 60
registration = json.loads((root / "evaluation/external_bases.json").read_text(encoding="utf-8"))


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


data.mkdir(exist_ok=True)
record = {
    "status": "starting",
    "code_sha": code_sha,
    "snapshot": str(root),
    "supervisor_pid": os.getpid(),
    "started": now(),
    "monitor_errors": 0,
    "bases": {},
}
if state_path.exists():
    earlier = json.loads(state_path.read_text())
    record["earlier_runs"] = earlier.get("earlier_runs", []) + [
        {k: v for k, v in earlier.items() if k != "earlier_runs"}
    ]


def save() -> None:
    record["updated"] = now()
    temporary = state_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n")
    os.replace(temporary, state_path)


def out(args: list[str]) -> str:
    return subprocess.run(args, capture_output=True, text=True, timeout=30).stdout


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def guarded() -> dict:
    """One digest per guarded path: the SHA-256 of its files' names and SHA-256, in order."""
    result = {}
    for path in GUARDED:
        files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
        lines = "".join(f"{p.relative_to(path.parent)} {file_sha(p)}\n" for p in files)
        result[str(path)] = {
            "files": len(files),
            "sha256": hashlib.sha256(lines.encode()).hexdigest(),
        }
    return result


def sample(base: str, step: str, pid: int | None, checkpoint: Path | None) -> None:
    """One host sample. A monitoring failure must never end the run."""
    try:
        child_rss, child_cpu, foreign = 0, 0.0, []
        for line in out(["ps", "-axo", "pid=,rss=,pcpu=,comm="]).splitlines():
            parts = line.split(None, 3)
            if len(parts) < 4:
                continue
            number, rss, cpu, name = int(parts[0]), int(parts[1]), float(parts[2]), parts[3]
            if number == pid:
                child_rss, child_cpu = rss, cpu
            elif cpu >= 25.0 and number != os.getpid():
                foreign.append([name.rsplit("/", 1)[-1][:40], cpu, rss])
        swap = re.search(r"used = ([\d.]+)M", out(["sysctl", "-n", "vm.swapusage"]))
        row = {
            "t": now(),
            "base": base,
            "step": step,
            "child_rss_kb": child_rss,
            "child_cpu": child_cpu,
            "swap_used_mb": float(swap.group(1)) if swap else None,
            "load1": round(os.getloadavg()[0], 2),
            "foreign_cpu": foreign,
        }
        if checkpoint is not None and checkpoint.exists():
            row["checkpoint_bytes"] = checkpoint.stat().st_size
            record["bases"][base]["checkpoint_bytes"] = row["checkpoint_bytes"]
        with monitor_path.open("a") as handle:
            handle.write(json.dumps(row) + "\n")
        entry = record["bases"].get(base, {}).get(step)
        if entry is not None:
            entry["samples"] = entry.get("samples", 0) + 1
            entry["foreign_cpu_samples"] = entry.get("foreign_cpu_samples", 0) + bool(foreign)
            entry["peak_rss_kb"] = max(entry.get("peak_rss_kb", 0), child_rss)
            entry["peak_load1"] = max(entry.get("peak_load1", 0), row["load1"])
    except Exception as exc:
        record["monitor_errors"] += 1
        record["last_monitor_error"] = f"{type(exc).__name__}: {exc}"


def finish(status: str, **extra) -> None:
    record.update(status=status, finished=now(), **extra)
    try:
        record["guarded_after"] = guarded()
        record["guarded_unchanged"] = record["guarded_after"] == record.get("guarded_before")
    except Exception as exc:
        record["guarded_error"] = f"{type(exc).__name__}: {exc}"
    save()
    raise SystemExit(0 if status == "complete" else 1)


def run(base: str, step: str, command: list[str], env: dict, checkpoint: Path | None) -> dict:
    """Run one step to its end; the supervisor exits here on a stop or a failure."""
    entry = record["bases"][base].setdefault(step, {"attempts": 0, "seconds": 0})
    entry["attempts"] += 1
    entry["started"] = now()
    log = data / base / f"{step}.log"
    started = time.time()
    with log.open("a") as handle:
        handle.write(f"=== attempt {entry['attempts']} {now()} {' '.join(command[1:])}\n")
        handle.flush()
        proc = subprocess.Popen(
            command, cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=handle,
            stderr=subprocess.STDOUT,
        )
        entry["pid"] = proc.pid
        record.update(status="running", base=base, step=step)
        save()
        while True:
            try:
                code = proc.wait(timeout=SAMPLE_SEC)
                break
            except subprocess.TimeoutExpired:
                sample(base, step, proc.pid, checkpoint)
                save()
                if stop_path.exists():
                    proc.terminate()
                    try:
                        proc.wait(timeout=60)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                    entry["seconds"] += round(time.time() - started)
                    finish("stopped", reason=f"stop file during {base} {step}")
    entry["seconds"] += round(time.time() - started)
    entry["exit_code"] = code
    entry["finished"] = now()
    if code != 0:
        tail = log.read_text(errors="replace")[-1500:]
        finish("failed", reason=f"{base} {step} exited {code}", log_tail=tail)
    for line in reversed(log.read_text(errors="replace").strip().splitlines()[-40:]):
        if line.startswith("{"):
            try:
                entry["report"] = json.loads(line)
                break
            except ValueError:
                continue
    else:
        finish("failed", reason=f"{base} {step}: no report line in the log")
    save()
    return entry["report"]


def prepare(base: str, folder: Path) -> None:
    """The corpus (and cases) of the base in its new folder, equal to its manifest."""
    folder.mkdir(exist_ok=True)
    if base == "aircargo":
        sources = {"corpus": uploads,
                   "corpus.manifest.json": root / "evaluation/aircargo_corpus.manifest.json"}
    else:
        sources = {name: first / base / name
                   for name in ("corpus", "corpus.manifest.json", "cases.jsonl")}
    for name, source in sources.items():
        target = folder / name
        if target.exists():
            continue
        if source.is_dir():
            shutil.copytree(source, target, copy_function=shutil.copy2)
        else:
            shutil.copy2(source, target)
    check = subprocess.run(
        [stage_py, "-m", "scripts.corpus_manifest", "verify", "--manifest",
         str(folder / "corpus.manifest.json"), "--root", str(folder / "corpus")],
        cwd=root, capture_output=True, text=True, timeout=600,
    )
    record["bases"][base]["corpus_verify"] = {"exit_code": check.returncode,
                                              "tail": check.stdout[-300:] + check.stderr[-300:]}
    save()
    if check.returncode != 0:
        finish("failed", reason=f"{base}: the copied corpus differs from its manifest")


def crashed(kind, value, trace) -> None:
    """An error of the supervisor itself is a terminal state too, not a silent death."""
    if not issubclass(kind, SystemExit):
        record.update(status="failed", finished=now(), reason=f"supervisor: {kind.__name__}: {value}")
        save()
    sys.__excepthook__(kind, value, trace)


sys.excepthook = crashed
save()
while True:
    probe = subprocess.run(["pgrep", "-fl", WRITERS], capture_output=True, text=True)
    if probe.returncode == 1:
        break
    if stop_path.exists():
        finish("stopped", reason="stop file while waiting")
    record.update(status="waiting", waiting_for=probe.stdout.strip().splitlines()[:3])
    save()
    time.sleep(SAMPLE_SEC)
record.pop("waiting_for", None)
record["work_started"] = now()
record["guarded_before"] = guarded()
save()

light_env = dict(
    os.environ, PYTHONDONTWRITEBYTECODE="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
    TOKENIZERS_PARALLELISM="false", ANONYMIZED_TELEMETRY="False",
)
embed_env = dict(light_env, OMP_NUM_THREADS="4", RAG_DEVICE="cpu")
index_env = dict(
    os.environ, PYTHONDONTWRITEBYTECODE="1", ANONYMIZED_TELEMETRY="False", PYTHONPATH=SITE,
)
for base in BASES:
    folder = data / base
    entry = record["bases"].setdefault(base, {})
    receipt = folder / "index" / "index-receipt.json"
    if receipt.exists():
        entry["index_receipt"] = json.loads(receipt.read_text())
        entry["skipped"] = "index receipt exists"
        save()
        continue
    prepare(base, folder)
    archive = folder / "chunks.json.gz"
    if base == "aircargo":
        command = [
            stage_py, "-m", "scripts.corpus_chunks", "--corpus", str(folder / "corpus"),
            "--manifest", str(folder / "corpus.manifest.json"), "--tenant", AIRCARGO["tenant"],
            "--collection", AIRCARGO["collection"], "--dated", AIRCARGO["dated"],
            "--out", str(folder),
        ]
        collection = AIRCARGO["collection"]
    else:
        command = [stage_py, "-m", "scripts.external_base", "chunks", "--base", base,
                   "--out", str(folder)]
        collection = registration["bases"][base]["collection"]
    chunks = run(base, "chunks", command, light_env, None)
    if file_sha(archive) != chunks["archive_sha256"] or chunks["collection"] != collection:
        finish("failed", reason=f"{base}: the archive differs from its report")
    entry.update(archive_sha256=chunks["archive_sha256"], chunks=chunks["chunks"])
    if base != "aircargo":
        kept = run(base, "preserve", [stage_py, "-m", "scripts.external_base", "preserve",
                                      "--base", base, "--out", str(folder)], light_env, None)
        lost = (kept.get("chunks_without_a_place"), kept.get("alternatives", {}).get("lost"))
        if lost != (0, 0):
            finish("failed", reason=f"{base}: chunks without a place or lost gold: {lost}")
    checkpoint = folder / "embeddings.npz"
    command = [
        stage_py, "-m", "scripts.production_embeddings", "--archive", str(archive),
        "--archive-sha256", chunks["archive_sha256"], "--output", str(checkpoint),
        "--revision", REVISION, "--batch-size", "64",
    ]
    if checkpoint.exists():
        command.append("--resume")
    report = run(base, "embed", command, embed_env, checkpoint)
    if not report["complete"] or report["total_rows"] != chunks["chunks"]:
        finish("failed", reason=f"{base}: the embeddings are not complete")
    if (folder / "index").exists():
        finish("failed", reason=f"{base}: an index directory without a receipt exists")
    command = [
        tools_py, "-m", "scripts.production_index", "--archive", str(archive),
        "--archive-sha256", chunks["archive_sha256"], "--checkpoint", str(checkpoint),
        "--manifest", str(MANIFEST), "--code-sha", code_sha, "--output", str(folder / "index"),
        "--collection-name", collection,
    ]
    entry["index_receipt"] = run(base, "index", command, index_env, None)
finish("complete")

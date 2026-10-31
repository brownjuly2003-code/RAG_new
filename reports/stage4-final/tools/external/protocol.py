"""Stage 5 contracts; the item 6/7 modules remain byte-identical."""

import hashlib
import math
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import ROOT, frozen, positive, questions, require, rows, sha, write  # noqa: E402
from common import read as read  # noqa: E402

BASES = ("wixqa", "conditionalqa", "multihoprag")
PRIMARY = BASES[:2]
SPEC = "docs/specs/stage5-final-external.md"
OLD = {"wixqa": "4f48fed", "conditionalqa": "4f48fed", "multihoprag": "5e308fe"}
GOLD_N = {"wixqa": 100, "conditionalqa": 80, "multihoprag": 70}
REQUESTS = {"m1": 115, "m2": 115, "bridge": 15}  # Forecast with no empty answers.


def outside(path):
    path = Path(path).resolve()
    require(not path.is_relative_to(ROOT.resolve()), "private data must be outside the repository")
    return path


def committed(path):
    path = Path(path).resolve()
    require(path.is_relative_to(ROOT.resolve()), "public input must be in the repository")
    relative = path.relative_to(ROOT.resolve()).as_posix()
    try:
        held = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=ROOT)
    except subprocess.CalledProcessError:
        require(False, "public input is not committed unchanged")
    require(held == path.read_bytes(), "public input is not committed unchanged")
    return sha(path)


def product_diff(source, item6_sha, stage5_sha):
    """The archive stand has no .git; compare its commits in the explicit source repository."""
    for value in (item6_sha, stage5_sha):
        require(
            isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value),
            "full registration SHAs required",
        )
        resolved = subprocess.check_output(
            ["git", "rev-parse", value + "^{commit}"], cwd=source, text=True
        ).strip()
        require(resolved == value, "registration commit differs")
    changed = (
        subprocess.check_output(
            ["git", "diff", "--name-only", "--no-renames", "-z", item6_sha, stage5_sha, "--"],
            cwd=source,
        )
        .decode("utf-8")
        .split("\0")
    )
    changed = sorted(p for p in changed if p)
    require(
        all(
            p.startswith(("docs/", "reports/", "tests/")) or ("/" not in p and p.endswith(".md"))
            for p in changed
        ),
        "product path differs from item 6",
    )
    require(
        not any(
            p.startswith("reports/")
            and p.endswith(".py")
            and not p.startswith("reports/stage4-final/tools/external/")
            for p in changed
        ),
        "product path differs from item 6: frozen harness changed",
    )
    return {"item6_sha": item6_sha, "stage5_sha": stage5_sha, "changed_paths": changed}


def table(data, ids):
    require(len(data) == len(ids) and {r["case_id"] for r in data} == set(ids), "case set differs")
    return {r["case_id"]: r for r in data}


def pin_public(path):
    return {Path(path).resolve().relative_to(ROOT.resolve()).as_posix(): committed(path)}


def runs_gate(root):
    """Refuse macOS archive sidecars before a reader tries to decode them as answers."""
    for path in sorted(Path(root).rglob("._*")):
        if path.is_file():
            require(False, f"AppleDouble file in runs archive: {path.as_posix()}")


def private_hashes(root):
    """Measurement files only; no index copy, runtime environment or document names."""
    root = outside(root)
    runs_gate(root)
    folders = (
        [root]
        if (root / "launch.json").exists()
        else [p for p in root.iterdir() if p.is_dir() and (p / "launch.json").exists()]
    )
    paths = [root / "series.json"] if (root / "series.json").is_file() else []
    for folder in folders:
        paths.extend(
            p
            for p in folder.iterdir()
            if p.is_file() and (p.suffix in (".json", ".jsonl") or p.name == "api.log")
        )
        for name in ("prompts", "cases", "retrieval"):
            paths.extend(p for p in (folder / name).glob("*") if p.is_file())
    require(bool(paths), "private run archive empty")
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(paths)}


def batch_hashes(root, base):
    """Bind just one base: the next base and the live series journal may still be growing."""
    require(base in BASES, "unknown base")
    runs_gate(root)
    return {
        f"final-answers-{base}-b{n:02d}": private_hashes(
            Path(root) / f"final-answers-{base}-b{n:02d}"
        )
        for n in range(1, 11)
    }


def forecast(times):
    require(
        times.get("n") == 100
        and all(positive(times.get(k)) for k in ("median", "p90", "max"))
        and times["median"] <= times["p90"] <= times["max"] < 3600,
        "historical tail missing or invalid",
    )
    # Whole stream (including suggestions), rounded up; the max remains visible, not a cap.
    rest = 30 * math.ceil(times["median"] / 30)
    first = max(360, 30 * math.ceil(times["p90"] / 30))
    batch = 120 + first + 9 * rest
    return {"first": first, "rest": rest, "startup": 120, "batch": batch, "series": 10 * batch}


def public_write(path, value, data):
    frozen("cases")  # Adds the frozen common module's directory, without loading models.
    from stage2_common import source_names, without_text

    for base in BASES:
        _, names = source_names(data, base)
        cases, ids = questions(base, data)
        queries = [r["query"] for r in rows(cases) if r["case_id"] in set(ids)]
        without_text(value, names, queries)
    write(path, value)


def prefix(path):
    data = Path(path).read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def seed_gate(path, held):
    with Path(path).open("rb") as stream:
        require(
            hashlib.sha256(stream.read(held["bytes"])).hexdigest() == held["sha256"],
            "historical bridge replies changed",
        )


def judge_record(path, base, metric, ids, references, code, prompts=None):
    from record import judge_rows

    record, cases = judge_rows(path, base, "answers")
    table(list(cases.values()), ids)
    p = record["provenance"]
    require(not record.get("missing"), "judge verdict missing")
    require(
        p["references_sha256"] == references
        and p["references_withheld"] is (metric == "m1")
        and ("m2" in record) is (metric == "m2"),
        "references or judge instrument differ",
    )
    require(
        p["prompt_id"] == ("QA_PROMPT_V3" if code == "5e308fe" else "QA_PROMPT_V4")
        and bool(p["runs"])
        and all(
            r["code_sha"].startswith(code) and r["tenant"] == "ext_" + base
            for r in p["runs"].values()
        ),
        "judge stand or prompt differs",
    )
    require(
        all(r.get("grade") in ("good", "partial_ok", "bad") for r in cases.values()),
        "invalid grade",
    )
    if metric == "m2":
        require(
            all(
                r.get("m2")
                in (
                    ("agrees", "partial", "disagrees", "declined", "empty_answer")
                    if r.get("has_reference")
                    else ("right", "wrong")
                )
                for r in cases.values()
            ),
            "M2 verdict missing or invalid",
        )
    if prompts is not None:
        require(
            all(cases[i]["prompt_sha256"] == prompts[i] for i in ids), "judge sent prompt differs"
        )
    return record, cases

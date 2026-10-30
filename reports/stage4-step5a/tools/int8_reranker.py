"""Stage 4, item 5a: INT8 of the same reranker, on stage 2's saved candidate lists.

docs/specs/stage4-step5a-int8-reranker.md, registered with this tool before any question of
stage 2 was scored in ONNX. PLAN.md stage 4, item 5a: first ONNX FP32 against PyTorch, then
INT8, on stage 2's saved candidate lists — the fives' overlap, the gold by base, the seconds,
the RSS. The pools stage 2 recorded (runs p2-* of stand 5e308fe, with the bases' chunk archives)
are scored by the product's reranker in PyTorch and by export_onnx.py's files in ONNX Runtime,
and read against the scores and the gold stage 2 recorded:

  block N RUNS DATA_ROOT MODELS OUT       the schedule's block N, in a process of its own
  series RUNS DATA_ROOT MODELS OUT LAST   the blocks up to LAST, each on the idle Mac
  read RUNS DATA_ROOT MODELS OUT RECORD   the record, from the blocks' files
  e.g. ... /Users/julia/RAG_new_chat_5e308fe/chatlive/runs /Users/julia/RAG_new_external_s1
           /Users/julia/RAG_new_ort/bge-reranker-v2-m3 /Users/julia/RAG_new_s4p5a_runs

A block scores its questions' pools as the product does: the question with each candidate's
archive text, in the pool's recorded order, 32 pairs a call. Its first question warms the model
and is not read. Blocks 1-6 read the INT8 variant; 7-11 read its fallback and run only when
block 6's gold reads a loss. `read` takes each question's five through the product's own fusion,
rerank cut and parent expansion (reports/k-curve/tools/k_curve.py's Selection and the no-reranker
point's loading, checks and exact McNemar) and writes RECORD/record.json and RECORD/rows.jsonl:
ids, flags and numbers; stage2_common.without_text refuses either when a string of it names a
document of a base or holds a question.
"""

import functools
import gzip
import hashlib
import json
import math
import os
import re
import resource
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
sys.path.insert(0, str(WS / "reports" / "k-curve" / "tools"))
import k_curve as kc  # noqa: E402

nr = kc.nr
from stage2_common import spread, swap_used_mb, without_text  # noqa: E402

SPEC = "docs/specs/stage4-step5a-int8-reranker.md"
MODEL = "BAAI/bge-reranker-v2-m3"
SNAPSHOT = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
# export_onnx.py's manifest: the files by SHA-256, the versions it ran on.
MANIFEST_SHA256 = "9888d92b97600dad487bf29de64483a4afe15d2e0e06e21497b8595dcf7c5408"
RUNTIME = ("torch", "transformers", "tokenizers", "sentence-transformers", "onnxruntime", "numpy")
THREADS = 4
BATCH = 32  # CrossEncoder.predict's default; the product sets none (RAG_RERANK_BATCH unset)
THIRTY = 30
SCHEDULE = {
    1: ("fp32", "thirty"),
    2: ("pytorch", "thirty"),
    3: ("int8", "thirty"),
    4: ("int8", "thirty"),
    5: ("pytorch", "thirty"),
    6: ("int8", "all"),
    7: ("pytorch", "thirty"),
    8: ("int8_u8u8", "thirty"),
    9: ("int8_u8u8", "thirty"),
    10: ("pytorch", "thirty"),
    11: ("int8_u8u8", "all"),
}
VARIANTS = {
    "int8": {"timing": (2, 3, 4, 5), "quality": 6},
    "int8_u8u8": {"timing": (7, 8, 9, 10), "quality": 11},
}
FIDELITY = 1
# A block's largest score difference from the record that stops the series: PyTorch must be
# stage 2's reranker, the FP32 export the same function.
TOLERANCE = {"pytorch": 1e-6, "fp32": 1e-3}
# Seconds a block may go without a new line: before its head line (the stand's hashes and the
# model's load), then between two questions.
START_LIMIT = 900
QUESTION_LIMIT = 300
POLL = 5
IDLE_LIMIT = 3600
IDLE_POLL = 15
LOAD_LIMIT = 2.0
BUSY = 100.0
PATTERN = re.compile(r"pytest|_supervisor|replay\.py|step[0-3]_|limactl|llama-server")
OLLAMA = "http://127.0.0.1:11434/api/ps"
CI_LOCK = Path.home() / "ci_local" / ".lock_ci-local"
MIN_READABLE = 25
MAX_UNREAD = 5
NET_LOSS = 2
NOT_EVIDENCE = nr.NOT_EVIDENCE
EXIT = {"stop": 3, "idle": 4, "slow": 5, "stand": 6, "fidelity": 7, "gate": 8, "twice": 9}
MEASURE_CODE = (
    *kc.MEASURE_CODE,
    "reports/k-curve/tools/k_curve.py",
    "reports/stage4-step5a/tools/export_onnx.py",
)
RENAMED = {"b_reranker_only": "b_pytorch_only", "c_fused_only": "c_variant_only"}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finite(value):
    return isinstance(value, float) and math.isfinite(value)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def peak_mib():
    """The process's peak resident size: ru_maxrss is bytes on macOS, KiB elsewhere."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(peak / 2**20 if sys.platform == "darwin" else peak / 2**10, 1)


def median(values):
    values = list(values)
    return round(statistics.median(values), 4) if values else None


def files_of(runs, base):
    return sorted((runs / nr.LABELS[base] / "retrieval").glob("*.json"))


def questions_of(kind, runs):
    """A block's questions in order, (base, record file): aircargo's thirty-first warms the
    model, then aircargo's first thirty or every base's every question."""
    aircargo = files_of(runs, "aircargo")
    warm = [("aircargo", aircargo[THIRTY])]
    if kind == "thirty":
        return warm + [("aircargo", p) for p in aircargo[:THIRTY]]
    return warm + [(base, p) for base in nr.LABELS for p in files_of(runs, base)]


def archive(root, base):
    with gzip.open(root / base / "chunks.json.gz", "rt", encoding="utf-8") as handle:
        return json.load(handle)["chunks"]


def pairs_of(record, chunks):
    """The product's rerank input: the question with each pool candidate's archive text, in
    the pool's recorded order (HybridRetriever._rerank_scored_with_status)."""
    pairs = []
    for candidate in record["pool"] or []:
        source, index = candidate[0], candidate[1]
        if (
            type(index) is not int
            or not 0 <= index < len(chunks)
            or chunks[index]["metadata"].get("source") != source
        ):
            raise SystemExit(f"{record['case_id']}: a candidate names no chunk of the archive")
        pairs.append((record["question"], chunks[index]["page_content"]))
    return pairs


class Torch:
    """The product's reranker: sentence-transformers' CrossEncoder on the CPU, predict's calls."""

    def __init__(self):
        import torch
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(MODEL, device="cpu")
        self.threads = torch.get_num_threads()

    def __call__(self, pairs):
        return [float(s) for s in self.model.predict(pairs)]


class Onnx:
    """The same calls in ONNX Runtime: the CrossEncoder's tokenization (each text stripped, the
    pairs padded to the longest, truncated longest first at the tokenizer's limit), logit 0's
    sigmoid."""

    def __init__(self, path):
        import onnxruntime as ort
        from transformers import AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(MODEL)
        options = ort.SessionOptions()
        options.intra_op_num_threads = THREADS
        self.session = ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])
        self.threads = options.intra_op_num_threads

    def __call__(self, pairs):
        import numpy as np

        scores = []
        for start in range(0, len(pairs), BATCH):
            batch = pairs[start : start + BATCH]
            features = self.tokenizer(
                [q.strip() for q, _ in batch],
                [d.strip() for _, d in batch],
                padding=True,
                truncation="longest_first",
                return_tensors="np",
                max_length=None,
            )
            feed = {k: features[k].astype(np.int64) for k in ("input_ids", "attention_mask")}
            logits = self.session.run(["logits"], feed)[0][:, 0].astype(np.float32)
            scores += [float(s) for s in 1.0 / (1.0 + np.exp(-logits))]
        return scores


def stand(arm, models):
    """The block's facts, held to the export's manifest; None and the reasons when one differs."""
    import importlib.metadata

    from huggingface_hub import try_to_load_from_cache

    reasons = []
    path = models / "manifest.json"
    if sha256(path) != MANIFEST_SHA256:
        return None, ["the export's manifest is not the registered one"]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest["max_length"] is not None:
        reasons.append("the export did not read at the tokenizer's own limit")
    packages = {n: importlib.metadata.version(n) for n in RUNTIME}
    reasons += [f"{n} {v}" for n, v in packages.items() if manifest["packages"].get(n) != v]
    config = try_to_load_from_cache(MODEL, "config.json")
    snapshot = Path(config).parent.name if isinstance(config, str) else None
    if snapshot != SNAPSHOT:
        reasons.append("the cached snapshot is not stage 2's")
    files = {}
    if arm != "pytorch":
        for name, want in manifest["files"].items():
            if name.startswith(f"{arm}/"):
                files[name] = sha256(models / name)
                if files[name] != want["sha256"]:
                    reasons.append(f"{name} is not the export's")
        if not files:
            reasons.append(f"the export holds no {arm}")
    facts = {
        "packages": packages,
        "snapshot": snapshot,
        "files": files,
        "python": sys.version.split()[0],
    }
    return (None if reasons else facts), reasons


def ollama_models():
    import urllib.request

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(OLLAMA, timeout=5) as response:
            return sorted(m.get("name", "?") for m in json.load(response).get("models", []))
    except (OSError, ValueError):
        return []


def sample(own):
    """What runs beside the block: the pattern's processes, the CPU of every other process,
    Ollama's models, the one-minute load and the swap."""
    listing = subprocess.run(
        ["ps", "-Ao", "pid=,pcpu=,command="], capture_output=True, text=True, check=False
    ).stdout
    matched, busy = set(), 0.0
    for line in listing.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 2 or not parts[0].isdigit() or int(parts[0]) in own:
            continue
        busy += float(parts[1])
        found = PATTERN.search(parts[2] if len(parts) > 2 else "")
        if found:
            matched.add(found.group(0))
    swap = subprocess.run(
        ["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True, check=False
    ).stdout
    return {
        "matched": sorted(matched),
        "others_cpu": round(busy, 1),
        "ollama": ollama_models(),
        "load1": round(os.getloadavg()[0], 2),
        "swap_mb": swap_used_mb(swap),
    }


def disturbed(line):
    return bool(line["matched"] or line["ollama"] or line["others_cpu"] > BUSY)


def block(number, runs, root, models, out, scorer=None):
    """One block of the schedule into OUT/blocks/NN.jsonl: a head line, a line a question, an
    end line. Exit 6 when the stand is not the registered one."""
    arm, kind = SCHEDULE[number]
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    own = {os.getpid(), os.getppid()}
    facts, reasons = stand(arm, models)
    if facts is None:
        print(f"block {number}: {'; '.join(reasons)}", flush=True)
        return EXIT["stand"]
    questions = questions_of(kind, runs)
    started = time.perf_counter()
    if scorer is None:
        scorer = Torch() if arm == "pytorch" else Onnx(models / arm / "model.onnx")
    load_sec = round(time.perf_counter() - started, 3)
    if scorer.threads != THREADS:
        print(f"block {number}: {scorer.threads} threads", flush=True)
        return EXIT["stand"]
    blocks = out / "blocks"
    blocks.mkdir(parents=True, exist_ok=True)
    partial = blocks / f"{number:02d}.partial.jsonl"
    with partial.open("w", encoding="utf-8") as handle:

        def put(line):
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
            handle.flush()

        put(
            {
                "block": number,
                "arm": arm,
                "kind": kind,
                "tool_sha256": sha256(Path(__file__)),
                "started_at": now(),
                "load_sec": load_sec,
                "rss_after_load_mib": peak_mib(),
                "threads": scorer.threads,
                **facts,
                "beside": sample(own),
            }
        )
        held, chunks = None, None
        for position, (base, path) in enumerate(questions):
            if base != held:
                held, chunks = base, None
                chunks = archive(root, base)
            record = json.loads(path.read_text(encoding="utf-8"))
            pairs = pairs_of(record, chunks)
            clock = time.perf_counter()
            scores = scorer(pairs) if pairs else []
            seconds = time.perf_counter() - clock
            put(
                {
                    "position": position,
                    "warm_up": position == 0,
                    "base": base,
                    "case_id": record["case_id"],
                    "index": record["index"],
                    "record_sha256": sha256(path),
                    "pairs": len(pairs),
                    "seconds": round(seconds, 3),
                    "scores": scores,
                    **sample(own),
                }
            )
        put(
            {
                "done": True,
                "ended_at": now(),
                "rss_peak_mib": peak_mib(),
                "torch_imported": "torch" in sys.modules,
            }
        )
    partial.rename(blocks / f"{number:02d}.jsonl")
    return 0


def lines_of(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def check(number, path, runs):
    """A block's file against the schedule and the records: the reasons it fails its gate, and
    its largest score difference from the scores stage 2 recorded."""
    arm, kind = SCHEDULE[number]
    lines = lines_of(path)
    reasons = []
    if len(lines) < 3:
        return ["no head, question and end"], None
    head, body, end = lines[0], lines[1:-1], lines[-1]
    if (head.get("block"), head.get("arm"), head.get("kind")) != (number, arm, kind):
        reasons.append("not the schedule's block")
    if head.get("tool_sha256") != sha256(Path(__file__)):
        reasons.append("another tool")
    if end.get("done") is not True:
        reasons.append("no end line")
    expected = questions_of(kind, runs)
    if [(q.get("base"), q.get("record_sha256")) for q in body] != [
        (base, sha256(p)) for base, p in expected
    ]:
        return [*reasons, "not the schedule's questions"], None
    worst = 0.0
    for line, (_, record_path) in zip(body, expected, strict=True):
        record = json.loads(record_path.read_text(encoding="utf-8"))
        recorded = [c[2] for c in record["pool"] or []]
        scores = line.get("scores")
        if (
            not isinstance(scores, list)
            or len(scores) != len(recorded)
            or not all(finite(s) and 0.0 <= s <= 1.0 for s in scores)
        ):
            reasons.append(f"position {line.get('position')}: not a score a candidate")
            continue
        worst = max([worst, *(abs(a - b) for a, b in zip(scores, recorded, strict=True))])
    return reasons, worst


def idle(first, own):
    """Wait for the idle Mac: no pattern process, no model in Ollama, no ci-local lock, the other
    processes under a core; before the series' first block the five-minute load below 2."""
    deadline = time.monotonic() + IDLE_LIMIT
    while True:
        got = sample(own)
        if (
            not got["matched"]
            and not got["ollama"]
            and not CI_LOCK.exists()
            and got["others_cpu"] <= BUSY
            and (not first or os.getloadavg()[1] < LOAD_LIMIT)
        ):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(IDLE_POLL)


def launch(number, runs, root, models, out):
    """The block in a process of its own; killed when its head line or its next question does
    not come within the limit."""
    partial = out / "blocks" / f"{number:02d}.partial.jsonl"
    command = [
        sys.executable,
        "-u",
        str(Path(__file__).resolve()),
        "block",
        str(number),
        *(str(p) for p in (runs, root, models, out)),
    ]
    with (out / "blocks.out").open("a", encoding="utf-8") as sink:
        process = subprocess.Popen(
            command, stdout=sink, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL
        )
        seen, since = 0, time.monotonic()
        while process.poll() is None:
            time.sleep(POLL)
            count = len(partial.read_bytes().splitlines()) if partial.exists() else 0
            if count != seen:
                seen, since = count, time.monotonic()
            elif time.monotonic() - since > (QUESTION_LIMIT if seen else START_LIMIT):
                process.kill()
                process.wait()
                return EXIT["slow"]
    return process.returncode


def series(runs, root, models, out, last):
    """The schedule's blocks up to LAST, from the first without a file; see the spec's Stops."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "blocks").mkdir(exist_ok=True)
    (out / "rejected").mkdir(exist_ok=True)
    tool = sha256(Path(__file__))
    state_path = out / "series.json"
    state = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.exists()
        else {"tool_sha256": tool, "attempts": {}}
    )

    def say(text):
        with (out / "series.log").open("a", encoding="utf-8") as log:
            log.write(f"{now()} {text}\n")

    if state["tool_sha256"] != tool:
        say("another tool started this series")
        return EXIT["stand"]

    def fidelity(number, worst):
        arm = SCHEDULE[number][0]
        if arm in TOLERANCE and worst > TOLERANCE[arm]:
            say(f"block {number} fidelity: {worst:.3e} above {TOLERANCE[arm]:.0e}")
            return False
        return True

    own, first = {os.getpid()}, True
    for number in range(1, last + 1):
        arm, kind = SCHEDULE[number]
        final = out / "blocks" / f"{number:02d}.jsonl"
        if final.exists():
            # A block kept from an earlier start is read again: its stop holds on every start.
            reasons, worst = check(number, final, runs)
            if reasons:
                say(f"block {number} kept but failing: {'; '.join(reasons)}")
                return EXIT["gate"]
            if not fidelity(number, worst):
                return EXIT["fidelity"]
            continue
        if (out / "stop").exists():
            say("stop file")
            return EXIT["stop"]
        tried = state["attempts"].get(str(number), 0)
        if tried >= 2:
            say(f"block {number} failed twice")
            return EXIT["twice"]
        if not idle(first, own):
            say("the Mac not idle within an hour")
            return EXIT["idle"]
        first = False
        state["attempts"][str(number)] = tried + 1
        state_path.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
        say(f"block {number} {arm} {kind}, attempt {tried + 1}")
        code = launch(number, runs, root, models, out)
        if code == 0 and final.exists():
            reasons, worst = check(number, final, runs)
        else:
            reasons, worst = [f"exit {code}"], None
        if reasons:
            for path in (final, out / "blocks" / f"{number:02d}.partial.jsonl"):
                if path.exists():
                    path.rename(out / "rejected" / f"{number:02d}-{tried + 1}-{path.name}")
            say(f"block {number} failed: {'; '.join(reasons)}")
            return {EXIT["slow"]: EXIT["slow"], EXIT["stand"]: EXIT["stand"]}.get(
                code, EXIT["gate"]
            )
        if not fidelity(number, worst):
            return EXIT["fidelity"]
        say(f"block {number} read: largest difference from the record {worst:.3e}")
    say("SERIES_DONE")
    return 0


def parsed(path):
    lines = lines_of(path)
    return {
        "head": lines[0],
        "warm_up": lines[1],
        "questions": [q for q in lines[1:-1] if not q["warm_up"]],
        "end": lines[-1],
    }


def speed(blocks, variant):
    """Per question, the two PyTorch blocks' mean seconds against the variant's two blocks'."""
    a1, b1, b2, a2 = VARIANTS[variant]["timing"]
    if any(n not in blocks for n in (a1, b1, b2, a2)):
        return None
    by = {n: {q["case_id"]: q for q in blocks[n]["questions"]} for n in (a1, b1, b2, a2)}
    cases = [q["case_id"] for q in blocks[a1]["questions"]]
    readable = [c for c in cases if not any(disturbed(by[n][c]) for n in by)]
    torch_sec = {c: (by[a1][c]["seconds"] + by[a2][c]["seconds"]) / 2 for c in readable}
    ours = {c: (by[b1][c]["seconds"] + by[b2][c]["seconds"]) / 2 for c in readable}
    faster = sum(1 for c in readable if ours[c] < torch_sec[c])
    slower = sum(1 for c in readable if ours[c] > torch_sec[c])
    p = nr.mcnemar(faster, slower)  # the exact two-sided sign test
    if len(readable) < MIN_READABLE:
        reading = NOT_EVIDENCE
    elif p < nr.ALPHA and faster > slower:
        reading = "faster"
    elif p < nr.ALPHA and slower > faster:
        reading = "slower"
    else:
        reading = "no detected difference"

    def seconds(n):
        return median(q["seconds"] for q in blocks[n]["questions"])

    timed = all(ours[c] > 0 for c in readable)
    return {
        "questions": len(cases),
        "readable": len(readable),
        "disturbed": [c for c in cases if c not in readable],
        "faster": faster,
        "slower": slower,
        "p": round(p, 6),
        "reading": reading,
        "ratio_median": median(torch_sec[c] / ours[c] for c in readable) if timed else None,
        "saved_sec_median": median(torch_sec[c] - ours[c] for c in readable),
        "pytorch_sec_median": median(torch_sec.values()),
        "variant_sec_median": median(ours.values()),
        "block_sec_median": {str(n): seconds(n) for n in (a1, b1, b2, a2)},
    }


def against_pytorch(blocks, number):
    """Per question, the first PyTorch pair's mean seconds over a block's own: beside, not read,
    for the block ran before them, not between."""
    a1, _, _, a2 = VARIANTS["int8"]["timing"]
    if any(n not in blocks for n in (number, a1, a2)):
        return None
    by = {n: {q["case_id"]: q["seconds"] for q in blocks[n]["questions"]} for n in (number, a1, a2)}
    mine = by[number]
    return median((by[a1][c] + by[a2][c]) / 2 / mine[c] for c in mine if mine[c] > 0)


def question(base, case, record, chunks, places, expand, select, scored):
    """One question's row: of each block that scored it, the largest difference from the
    recorded scores and the five the product keeps by its scores; with gold, the recorded five's
    points and, of each quality block, its five's before and after the expansion."""
    from retrieval_summary import position

    from scripts.external_pilot import read_gold

    case_id = record["case_id"]
    if not record["pool"]:
        raise SystemExit(f"{case_id}: the record holds no pool: NOT_EVIDENCE")
    lanes = record["lanes"] or {"vector": [p[:2] for p in record["pool"]], "bm25": []}
    recorded = [p[2] for p in record["pool"]]
    try:
        vector = [position(x, chunks) for x in lanes["vector"]]
        bm25 = [position(x, chunks) for x in lanes["bm25"]]
        pool = [position(p, chunks) for p in record["pool"]]
        ranked = [position(r, chunks) for r in record["ranked"]][: nr.TOP]
        top = select(chunks, vector, bm25, dict(zip(pool, recorded, strict=True)), kc.KMAX)
        picks = {}
        for number, scores in sorted(scored.get(case_id, {}).items()):
            if len(scores) != len(pool):
                raise ValueError(f"block {number} scored another pool")
            picks[number] = select(
                chunks, vector, bm25, dict(zip(pool, scores, strict=True)), kc.KMAX
            )
    except ValueError as error:
        raise SystemExit(f"{case_id}: {error}: NOT_EVIDENCE") from error
    if (top["pool"], top["five"], top["scores"]) != (
        pool,
        ranked,
        [r[2] for r in record["ranked"]][: nr.TOP],
    ):
        raise SystemExit(f"{case_id}: the recorded scores are not the recorded five: NOT_EVIDENCE")
    row = {
        "case_id": case_id,
        "base": base,
        "index": record["index"],
        "pool_size": len(pool),
        "reranker_ok": record["reranker_ok"],
        "blocks": {
            str(n): {
                "max_abs_diff": max(
                    abs(a - b) for a, b in zip(scored[case_id][n], recorded, strict=True)
                ),
                "shared_of_five": len(set(pick["five"]) & set(ranked)),
                "same_five": set(pick["five"]) == set(ranked),
                "same_order": pick["five"] == ranked,
            }
            for n, pick in picks.items()
        },
    }
    if case is None:
        return row
    expanded = [
        {"metadata": {"chunk_index": e["chunk_index"]}, "text": e["text"]}
        for e in record["expanded"]
    ]
    if expand(ranked) != expanded:
        raise SystemExit(f"{case_id}: the product's expansion is not the recorded one")
    try:
        points = {
            "ranked": read_gold(base, case, ranked, places),
            "expanded_ranked": read_gold(base, case, places.members(expanded), places),
        }
    except ValueError as error:
        raise SystemExit(f"{case_id}: {error}, where the export read it") from error
    row.update(stratum=case.get("stratum"), points=points, unresolved=[])
    for variant, plan in VARIANTS.items():
        if plan["quality"] not in picks:
            continue
        five = picks[plan["quality"]]["five"]
        try:
            points[variant] = read_gold(base, case, five, places)
            points[f"expanded_{variant}"] = read_gold(
                base, case, places.members(expand(five)), places
            )
        except ValueError:
            points.pop(variant, None)
            row["unresolved"].append(variant)
    return row


def base_rows(base, runs, root, manifest, scored):
    """The no-reranker point's loading and checks of one base, with this tool's rows."""
    label = nr.LABELS[base]
    settings = json.loads((runs / label / "effective_settings.json").read_text("utf-8"))["all"]
    if settings["retrieval_top_k"] != kc.KMAX:
        raise SystemExit(f"{label}: the lanes are not of {kc.KMAX} candidates")
    original = nr.question
    nr.question = functools.partial(question, select=kc.Selection(settings), scored=scored)
    try:
        rows, provenance, names, questions = nr.base_rows(base, runs, root, manifest)
    finally:
        nr.question = original
    return rows, provenance, names, questions


def gold_pair(rows, variant, point):
    """The variant's five against PyTorch's recorded five, by each question's primary metric:
    b - gold with PyTorch's only, c - with the variant's only."""
    left = "expanded_ranked" if point == "expanded" else "ranked"
    right = f"expanded_{variant}" if point == "expanded" else variant
    view = [
        {"base": r["base"], "points": {"pytorch": r["points"][left], variant: r["points"][right]}}
        for r in rows
        if right in r["points"]
    ]
    return {RENAMED.get(k, k): v for k, v in nr.pair(view, "pytorch", variant).items()}


def beside(rows, number):
    """Of one block, over a base's rows it scored: the fives shared, the scores' differences."""
    entries = [r["blocks"][str(number)] for r in rows if str(number) in r["blocks"]]
    if not entries:
        return None
    return {
        "questions": len(entries),
        "shared_of_five_mean": nr.mean(e["shared_of_five"] for e in entries),
        "same_five": sum(1 for e in entries if e["same_five"]),
        "same_order": sum(1 for e in entries if e["same_order"]),
        "max_abs_diff": spread([e["max_abs_diff"] for e in entries]),
    }


def quality(rows, variant):
    """Per base with gold and pooled, the variant's gold after the expansion against PyTorch's;
    the reading the spec froze."""
    number = VARIANTS[variant]["quality"]
    gold = [r for r in rows if "points" in r and str(number) in r["blocks"]]
    if not gold:
        return None
    per_base, pooled_rows, not_evidence = {}, [], False
    for base in nr.METRICS:
        mine = [r for r in gold if r["base"] == base]
        unread = sum(1 for r in mine if variant in r["unresolved"])
        not_evidence |= unread > MAX_UNREAD
        per_base[base] = {
            "with_gold": len(mine),
            "unresolved": unread,
            "ranked": gold_pair(mine, variant, "ranked"),
            "expanded": NOT_EVIDENCE
            if unread > MAX_UNREAD
            else gold_pair(mine, variant, "expanded"),
        }
        pooled_rows += mine
    pooled = {
        "ranked": gold_pair(pooled_rows, variant, "ranked"),
        "expanded": NOT_EVIDENCE if not_evidence else gold_pair(pooled_rows, variant, "expanded"),
    }
    if not_evidence:
        reading = NOT_EVIDENCE
    else:
        expanded = [p["expanded"] for p in per_base.values()] + [pooled["expanded"]]
        net = pooled["expanded"]["b_pytorch_only"] - pooled["expanded"]["c_variant_only"]
        lost = any(e["reading"] == "loss" for e in expanded) or net > NET_LOSS
        reading = "loss" if lost else "holds"
    return {"bases": per_base, "pooled": pooled, "reading": reading}


def outcome(fidelity, readings):
    """The spec's outcome: the FP32 export first, then INT8, its fallback only on a loss."""
    if fidelity is None:
        return "pending"
    if fidelity["reading"] != "holds":
        return NOT_EVIDENCE
    for variant in VARIANTS:
        got = readings.get(variant) or {}
        gold, pace = got.get("quality"), got.get("speed")
        if gold is None:
            return "pending"
        if gold["reading"] == NOT_EVIDENCE:
            return NOT_EVIDENCE
        if gold["reading"] == "loss":
            continue
        if pace is None:
            return "pending"
        if pace["reading"] == NOT_EVIDENCE:
            return NOT_EVIDENCE
        return {
            "variant": variant,
            "passes": pace["reading"] == "faster",
            "speed": pace["reading"],
            "ratio_median": pace["ratio_median"],
        }
    return {"variant": None, "passes": False}


def read(runs, root, models, out, target):
    manifest = json.loads((nr.EXPORT / "manifest.json").read_text(encoding="utf-8"))
    if manifest["code_sha"] != nr.CODE_SHA:
        raise SystemExit("the export is not of the stand the records are")
    blocks = {}
    for number in SCHEDULE:
        path = out / "blocks" / f"{number:02d}.jsonl"
        if path.exists():
            reasons, _ = check(number, path, runs)
            if reasons:
                raise SystemExit(f"block {number}: {'; '.join(reasons)}")
            blocks[number] = parsed(path)
    scored = {}
    for number, got in blocks.items():
        for q in got["questions"]:
            scored.setdefault(q["case_id"], {})[number] = q["scores"]
    all_rows, provenance, names, questions = [], {}, set(), []
    for base in nr.LABELS:
        rows, provenance[base], held, asked = base_rows(base, runs, root, manifest, scored)
        all_rows += rows
        names |= held
        questions += asked
    fidelity = None
    if FIDELITY in blocks:
        got = beside(all_rows, FIDELITY)
        fidelity = {
            **got,
            "tolerance": TOLERANCE["fp32"],
            "reading": "holds" if got["max_abs_diff"]["max"] <= TOLERANCE["fp32"] else "fails",
            "pytorch_over_fp32_sec_median": against_pytorch(blocks, FIDELITY),
        }
    readings = {
        variant: {"speed": speed(blocks, variant), "quality": quality(all_rows, variant)}
        for variant in VARIANTS
    }
    by_base = {}
    for base in nr.LABELS:
        mine = [r for r in all_rows if r["base"] == base]
        got = {str(n): beside(mine, n) for n in blocks}
        by_base[base] = {n: v for n, v in got.items() if v}
    record = {
        "spec": SPEC,
        "stand_code_sha": nr.CODE_SHA,
        "measured_at_head": nr.git_head(),
        "inputs": {
            "runs": str(runs),
            "data_root": str(root),
            "models": str(models),
            "export_onnx_manifest_sha256": sha256(models / "manifest.json"),
            "export": str(nr.EXPORT.relative_to(WS)),
            "export_manifest_sha256": sha256(nr.EXPORT / "manifest.json"),
        },
        "tool_sha256": sha256(Path(__file__)),
        "measure_code_sha256": {n: sha256(WS / n) for n in MEASURE_CODE},
        "provenance": provenance,
        "blocks": {
            str(n): {
                "arm": got["head"]["arm"],
                "kind": got["head"]["kind"],
                "file_sha256": sha256(out / "blocks" / f"{n:02d}.jsonl"),
                "started_at": got["head"]["started_at"],
                "ended_at": got["end"]["ended_at"],
                "load_sec": got["head"]["load_sec"],
                "warm_up_sec": got["warm_up"]["seconds"],
                "seconds": spread([q["seconds"] for q in got["questions"]]),
                "seconds_sum": round(math.fsum(q["seconds"] for q in got["questions"]), 3),
                "rss_after_load_mib": got["head"]["rss_after_load_mib"],
                "rss_peak_mib": got["end"]["rss_peak_mib"],
                "torch_imported": got["end"]["torch_imported"],
                "disturbed": sum(1 for q in got["questions"] if disturbed(q)),
                "others_cpu_max": max(q["others_cpu"] for q in got["questions"]),
                "swap_mb": spread([q["swap_mb"] for q in got["questions"]]),
            }
            for n, got in blocks.items()
        },
        "attempts": json.loads((out / "series.json").read_text(encoding="utf-8"))["attempts"],
        "rejected": sorted(p.name for p in (out / "rejected").glob("*")),
        "fidelity": fidelity,
        "by_base": by_base,
        "variants": readings,
        "outcome": outcome(fidelity, readings),
    }
    without_text(record, names, questions)
    without_text(all_rows, names, questions)
    for got in blocks.values():
        without_text(got, names, questions)
    target.mkdir(parents=True, exist_ok=True)
    (target / "record.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    (target / "rows.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in all_rows), encoding="utf-8"
    )
    print(json.dumps({"fidelity": fidelity, "outcome": record["outcome"]}, indent=1))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    command, rest = argv[0], argv[1:]
    if command == "block":
        return block(int(rest[0]), *(Path(p) for p in rest[1:5]))
    if command == "series":
        return series(*(Path(p) for p in rest[:4]), int(rest[4]))
    if command == "read":
        return read(*(Path(p) for p in rest[:5]))
    raise SystemExit(f"unknown command {command}")


if __name__ == "__main__":
    raise SystemExit(main())

"""What the stage-2 summaries share: reading a run, spreads, memory, the rule of what leaves.

answers_summary.py and retrieval_summary.py import it from the stand's chatlive folder.
"""

import gzip
import hashlib
import json
import re
import statistics
from pathlib import Path

# The bases of the generation and the keys of their runs.
BASES = {
    "aircargo": "aircargo",
    "aircargo-gr": "aircargo",
    "conditionalqa": "conditionalqa",
    "wixqa": "wixqa",
    "multihoprag": "multihoprag",
}
# The generation's files whose SHA-256 a record carries.
SOURCE_FILES = ("corpus.manifest.json", "chunks-report.json", "index/index-receipt.json")
# The lines vectordb.manager logs when it restores a tenant's chunks for BM25, or cannot.
RESTORE = re.compile(r"Restored \d+ chunks|Chunk restore failed|WITHOUT BM25")


def load_jsonl(path):
    if not Path(path).exists():
        return []
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value, digits=3):
    return round(value, digits) if isinstance(value, float) else value


def spread(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    p90 = (
        statistics.quantiles(values, n=10, method="inclusive")[8] if len(values) > 1 else values[0]
    )
    return {
        "n": len(values),
        "min": values[0],
        "median": round(statistics.median(values), 3),
        "p90": round(p90, 3),
        "max": values[-1],
    }


def swap_used_mb(text):
    match = re.search(r"used = ([0-9.]+)M", text or "")
    return float(match.group(1)) if match else None


def memory(samples):
    """Swap used, the least free memory and the largest resident size by process kind."""
    swap = [v for v in (swap_used_mb(s.get("swap")) for s in samples) if v is not None]
    free = [s["free_pages"] * 4096 / 2**20 for s in samples if s.get("free_pages")]
    rss = {}
    for sample in samples:
        for _pid, _cpu, size, comm in sample.get("procs", []):
            kind = "ollama" if "llama" in comm else "postgres" if "postgres" in comm else "python"
            rss[kind] = max(rss.get(kind, 0), size)
    return {
        "samples": len(samples),
        "swap_used_mb": [min(swap), max(swap)] if swap else None,
        "free_mb_min": round(min(free)) if free else None,
        "max_rss_mb": {k: round(v / 2**20) for k, v in sorted(rss.items())},
    }


def restore_breaks(lines, tenant):
    """Stage 1's restore test of a run («The path breaks» of the spec), for its tenant only.

    A Restored line and no failure line; the API's start also loads the tenant default, whose
    lines are not the measured path.
    """
    mine = [line for line in lines if re.search(rf"[Tt]enant {re.escape(tenant)}(?![\w-])", line)]
    reasons = [] if any("Restored " in line for line in mine) else ["no restore line"]
    return reasons + [
        kind for kind in ("Chunk restore failed", "WITHOUT BM25") if any(kind in m for m in mine)
    ]


def path_breaks(candidates, rerank_status, documents):
    """Stage 1's path test of one retrieval: both lanes found some, the rerank ran, five back."""
    candidates = candidates or {}
    reasons = [f"empty {lane} lane" for lane in ("vector", "bm25") if not candidates.get(lane)]
    if rerank_status != "ok":
        reasons.append(f"rerank {rerank_status}")
    if (documents or 0) < 5:
        reasons.append(f"{documents} documents")
    return reasons


def ranks(lane):
    """Each candidate of a lane by its identity (source, chunk_index): its rank, from 1."""
    out = {}
    for rank, ident in enumerate(lane, start=1):
        out.setdefault(tuple(ident), rank)
    return out


def pool_ranks(lanes, pool):
    """Every fused candidate as [vector rank, BM25 rank, cross-encoder score]: no identity.

    No lanes row: BM25 found nothing, no fusion ran, and the pool is the vector lane.
    """
    lanes = lanes or {"vector": [p[:2] for p in pool], "bm25": []}
    by_vector, by_bm25 = ranks(lanes["vector"]), ranks(lanes["bm25"])
    return [[by_vector.get((s, c)), by_bm25.get((s, c)), score] for s, c, score in pool]


def source_names(root, base):
    """The documents of a base by the names its chunk archive gives them."""
    archive = json.loads(gzip.decompress((Path(root) / base / "chunks.json.gz").read_bytes()))
    return archive, {str(c["metadata"].get("source")) for c in archive["chunks"]}


def strings(value):
    """Every string of a record, the keys of its mappings too."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from strings(item)


def without_text(record, names, questions):
    """The record, refused when a string of it names a document or holds a question.

    The rule of scripts/external_pilot.without_text (evaluation/external_bases.json,
    "redistribution"): the summaries copy numbers, ids and statuses; this holds a later change
    of them to what may leave the host.
    """
    held = set(strings(record))
    if held.intersection(names) or any(q in text for q in questions for text in held):
        raise SystemExit("the record would carry text of the base: refused")
    return record


def write(out, name, record, rows):
    """NAME.json and NAME.cases.jsonl, one question a line."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    (out / f"{name}.cases.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )

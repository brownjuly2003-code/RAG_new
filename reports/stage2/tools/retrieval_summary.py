"""Summarise one stage-2 retrieval run: provenance, times and, on an external base, M3.

Usage (on the Mac, in the stand's chatlive folder):
    python retrieval_summary.py RUN DATA_ROOT OUT_DIR [ANSWERS_CASES]
    e.g. retrieval_summary.py p2-wixqa /Users/julia/RAG_new_external_s1 /Users/julia/s2-out
    python retrieval_summary.py check RUN
    - stage2.sh after the run: the path test; exit 6 on a break or no question.
A run that did not complete is refused: its questions are NOT_EVIDENCE.

PLAN.md stage 2, item 2; docs/specs/stage2-four-corpora.md. RUN is a run of stage2.sh in mode
retrieval, labelled PART-KEY[SUFFIX]: runs/RUN/retrieval/NNN-<case>.json, written by
live_retrieval.py. ANSWERS_CASES, when given, is the PART-KEY.cases.jsonl answers_summary.py
wrote for the same questions: each question's prompt SHA-256 here is compared with the one the
chat sent (the parity check).

M3 on an external base is read by external-gold/range-coverage-v1 (evaluation/external_gold.py)
with the pilot's Places and read_gold (scripts/external_pilot.py), at the points
  vector, bm25 - the candidates of each lane;
  pool         - the fused candidates the reranker scored;
  ranked       - the five it kept, the seeds;
  expanded     - the documents parent expansion returned, resolved into the chunks they were
                 joined from (external_gold.expansion_members);
  sent         - the documents of the fitted prompt, what the chat's model reads. A document
                 the fitting cut to an excerpt (agent/context_window._excerpt: paragraphs of it
                 joined by EXCERPT_GAP) holds the places of the excerpt's paragraphs only, each
                 found, in order, among the places of the chunks the whole document joined;
                 on WixQA it holds its article when the excerpt has a visible character.
ConditionalQA and MultiHop-RAG: all_evidence_coverage and evidence_recall; WixQA: gold_article
and gold_articles. A question without gold (ConditionalQA's stratum not_answerable) has no
coverage and is counted apart.

The K curve (PLAN.md stage 4, item 3): for K = 1..20 candidates a lane, the pool is the
candidates within the first K of either lane and the five kept are those of the highest
cross-encoder score among them, ties in the fused order (the product's stable sort). A
candidate's score does not depend on the others, so the curve needs no new run; K = 20 must
give the five the run kept (as a set: k20_is_ranked; their order apart, k20_order_differs),
and a question where it does not is counted and left out of the curve. The curve is read at
ranked. The first K of a lane stand for a search of K: exact for BM25, approximate for the
vector index, whose search depth depends on k.

Each point's mean is printed with its n, the questions read up to it; a comparison of two
points reads the questions read at both.

Writes OUT_DIR/RUN.json (provenance, aggregates) and OUT_DIR/RUN.cases.jsonl (one question a
line: numbers and ids). path_breaks is what stage 1's path test finds wrong: in a question an
empty lane, the rerank's status or fewer than five documents, in the run its BM25 restore for
its tenant (the lines live_retrieval.py logs into progress.log). stage2_common.without_text
refuses either file when a string of it names a document of the base or holds a question.
"""

import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parent
RUNS = HERE / "runs"
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(WS))
from stage2_cases import registered  # noqa: E402
from stage2_common import (  # noqa: E402
    BASES,
    RESTORE,
    SOURCE_FILES,
    load_jsonl,
    memory,
    path_breaks,
    pool_ranks,
    restore_breaks,
    sha256,
    source_names,
    spread,
    without_text,
    write,
)

TOP = 5
POINTS = ("vector", "bm25", "pool", "ranked", "expanded", "sent")
METRICS = {
    "wixqa": ("gold_article", "gold_articles"),
    "conditionalqa": ("all_evidence_coverage", "evidence_recall"),
    "multihoprag": ("all_evidence_coverage", "evidence_recall"),
}
TOOLS = (
    "live_api.py",
    "live_retrieval.py",
    "live_supervisor.py",
    "stage2.sh",
    "stage2_cases.py",
    "stage2_common.py",
    "retrieval_summary.py",
)
MEASURE_CODE = (
    "evaluation/external_gold.py",
    "scripts/external_pilot.py",
    "evaluation/external_parts.py",
    "evaluation/external_bases.py",
    "agent/context_window.py",
)


def position(ident, chunks):
    """The archive position of a candidate (source, chunk_index): the index stamps it."""
    source, index = ident[0], ident[1]
    if (
        type(index) is not int
        or not 0 <= index < len(chunks)
        or chunks[index]["metadata"].get("source") != source
    ):
        raise ValueError("a candidate names no chunk of the archive")
    return index


class Excerpted:
    """The places of a set of chunks, with the places of excerpts added."""

    def __init__(self, places, extra):
        self.source, self.places, self.extra = places.source, places, extra

    def by_document(self, members):
        held = self.places.by_document(members) if members else {}
        for name, place in self.extra:
            held.setdefault(name, []).append(place)
        return held


def excerpt_places(text, whole, seed, places, sources, chunks):
    """The places of an excerpt's paragraphs and how many of them were not found."""
    from agent.context_window import EXCERPT_GAP
    from evaluation import external_gold as gold

    name = places.source[seed]
    spans = [
        places.places[m] for m in whole if places.source[m] == name and places.places[m] is not None
    ]
    low, high = min(s[0] for s in spans), max(s[1] for s in spans)
    found, missed, at = [], 0, low
    for piece in text.split(EXCERPT_GAP):
        needle = gold.visible(gold.strip_header(piece, chunks[seed]["metadata"]))[0]
        if not needle:
            continue
        start = sources[name].text.find(needle, at, high)
        if start == -1:
            missed += 1
            continue
        found.append((name, (start, start + len(needle))))
        at = start + len(needle)
    return found, missed


def k_curve(record):
    """The five kept for every K, as identities; None without a score for every candidate."""
    pool = record["pool"]
    if not pool or any(p[2] is None for p in pool):
        return None, 0
    lanes = record["lanes"] or {"vector": [p[:2] for p in pool], "bm25": []}
    score = {tuple(p[:2]): p[2] for p in pool}
    order = {tuple(p[:2]): i for i, p in enumerate(pool)}
    outside = len({tuple(x) for x in lanes["vector"] + lanes["bm25"]} - set(score))
    curve = []
    for k in range(1, max(len(lanes["vector"]), len(lanes["bm25"])) + 1):
        within = {tuple(x) for x in lanes["vector"][:k]} | {tuple(x) for x in lanes["bm25"][:k]}
        curve.append(
            sorted((i for i in within if i in score), key=lambda i: (-score[i], order[i]))[:TOP]
        )
    return curve, outside


def in_index(base, case, places):
    """Whether the chunks of the index can give the question the first metric 1 (the pilot's
    reachable, for every base)."""
    from scripts.external_pilot import gold_documents, read_gold

    members = [m for name in gold_documents(base, case) for m in places.of_source.get(name, [])]
    try:
        return read_gold(base, case, members, places)[METRICS[base][0]] == 1.0
    except ValueError:
        return None


def coverage(base, case, record, places, sources, chunks):
    """M3 of one question at every point; the excerpt paragraphs not found; the K curve.

    A point that cannot be read - a candidate or a joined chunk without a place in its
    document, a document that is no expansion of its seed - ends the reading of the question
    there: unresolved names the point and the record counts it.
    """
    from evaluation import external_gold as gold
    from scripts.external_pilot import read_gold

    pool = record["pool"] or []
    lanes = record["lanes"] or {"vector": [p[:2] for p in pool], "bm25": []}
    out = {"points": {}, "excerpt_pieces_missed": 0, "unresolved": None}
    expanded = [
        {"metadata": {"chunk_index": e["chunk_index"]}, "text": e["text"]}
        for e in record["expanded"]
    ]
    point = "vector"
    try:
        present = {
            "vector": [position(x, chunks) for x in lanes["vector"]],
            "bm25": [position(x, chunks) for x in lanes["bm25"]],
            "pool": [position(p, chunks) for p in pool],
            "ranked": [position(r, chunks) for r in record["ranked"]][:TOP],
        }
        for point in ("vector", "bm25", "pool", "ranked"):
            out["points"][point] = read_gold(base, case, present[point], places)
        point = "expanded"
        out["points"][point] = read_gold(base, case, places.members(expanded), places)
        point = "sent"
        members, extra = [], []
        # The fitting keeps leading documents: what it sent is a prefix of the expanded ones.
        for doc, whole in zip(record["sent"], expanded, strict=False):
            joined = places.members([whole])
            if not doc["cut"]:
                members += joined
            elif sources is None:
                if gold.visible(doc["text"])[0]:
                    members.append(doc["chunk_index"])
            else:
                found, missed = excerpt_places(
                    doc["text"], joined, doc["chunk_index"], places, sources, chunks
                )
                extra += found
                out["excerpt_pieces_missed"] += missed
        out["points"][point] = read_gold(base, case, members, Excerpted(places, extra))
    except ValueError:
        out["unresolved"] = point
    curve, outside = k_curve(record)
    out["lane_not_in_pool"] = outside
    kept = [tuple(r[:2]) for r in record["ranked"][:TOP]]
    out["k20_is_ranked"] = None if curve is None else set(curve[-1]) == set(kept)
    out["k20_order_differs"] = None if curve is None else list(curve[-1]) != kept
    try:
        out["k_curve"] = (
            None
            if curve is None
            else [
                read_gold(base, case, [position(i, chunks) for i in kept], places) for kept in curve
            ]
        )
    except ValueError:
        out["k_curve"] = None
        out["unresolved"] = out["unresolved"] or "k_curve"
    return out


def mean(values):
    values = list(values)
    return round(math.fsum(values) / len(values), 4) if values else None


def external_aggregate(base, rows):
    gold_rows = [r for r in rows if r.get("gold")]
    metrics = METRICS[base]

    def points(group):
        return {
            point: {
                "n": sum(1 for r in group if point in r["points"]),
                **{
                    m: mean(r["points"][point][m] for r in group if point in r["points"])
                    for m in metrics
                },
            }
            for point in POINTS
        }

    curves = [r["k_curve"] for r in gold_rows if r.get("k_curve") and r.get("k20_is_ranked")]
    depth = min((len(c) for c in curves), default=0)
    strata = sorted({str(r.get("stratum")) for r in gold_rows})
    return {
        "with_gold": len(gold_rows),
        "without_gold": len(rows) - len(gold_rows),
        "gold_in_index": dict(Counter(str(r["gold_in_index"]) for r in gold_rows)),
        "with_unresolved_evidence": sum(1 for r in gold_rows if r["unresolved_evidence"]),
        "unresolved": dict(Counter(str(r["unresolved"]) for r in gold_rows)),
        "excerpt_pieces_missed": sum(r["excerpt_pieces_missed"] for r in gold_rows),
        "points": points(gold_rows),
        "points_by_stratum": {
            s: points([r for r in gold_rows if str(r.get("stratum")) == s]) for s in strata
        },
        "k_curve_questions": len(curves),
        "k20_is_ranked": sum(1 for r in gold_rows if r.get("k20_is_ranked")),
        "k20_not_ranked": sum(1 for r in gold_rows if r.get("k20_is_ranked") is False),
        "k20_order_differs": sum(1 for r in gold_rows if r.get("k20_order_differs")),
        "lane_not_in_pool": sum(r["lane_not_in_pool"] for r in gold_rows),
        "k_curve": [{m: mean(c[k][m] for c in curves) for m in metrics} for k in range(depth)],
    }


def restore_lines(run):
    """The retriever's restore lines, which live_retrieval.py logs into the run's progress.log."""
    text = (run / "progress.log").read_text(encoding="utf-8", errors="replace")
    return [line.strip() for line in text.splitlines() if RESTORE.search(line)]


def check(label):
    """The path test of a finished retrieval run, read by stage2.sh after it."""
    run = RUNS / label
    launch = json.loads((run / "launch.json").read_text(encoding="utf-8"))
    breaks = {}
    records = sorted((run / "retrieval").glob("*.json"))
    for path in records:
        record = json.loads(path.read_text(encoding="utf-8"))
        found = path_breaks(
            (record["path"] or {}).get("candidates"),
            (record["path"] or {}).get("rerank_status"),
            len(record["expanded"]),
        )
        if found:
            breaks[record["case_id"]] = found
    run_breaks = restore_breaks(restore_lines(run), launch.get("tenant") or "")
    print(
        "CHECK",
        label,
        "questions",
        len(records),
        "run",
        run_breaks,
        "path_breaks",
        json.dumps(breaks, ensure_ascii=False),
        flush=True,
    )
    return 6 if breaks or run_breaks or not records else 0


def main():
    if sys.argv[1] == "check":
        return check(sys.argv[2])
    label, root, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    answers = sys.argv[4] if len(sys.argv) > 4 else None
    run = RUNS / label
    launch = json.loads((run / "launch.json").read_text(encoding="utf-8"))
    if launch.get("status") != "complete":
        raise SystemExit(f"{label} did not complete ({launch.get('status')}): NOT_EVIDENCE")
    effective = json.loads((run / "effective_settings.json").read_text(encoding="utf-8"))
    header = json.loads((run / "retrieval-cpu.json").read_text(encoding="utf-8"))
    key = next(
        k for k in sorted(BASES, key=len, reverse=True) if label.split("-", 1)[1].startswith(k)
    )
    base, cases_file = BASES[key], Path(launch["cases_file"])
    if launch.get("tenant") != ("aircargo" if base == "aircargo" else f"ext_{base}"):
        raise SystemExit(f"{label} is not on the tenant of {base}")
    missing_sources = [n for n in SOURCE_FILES if not (root / base / n).is_file()]
    if missing_sources:
        raise SystemExit(f"the generation lacks {missing_sources}")
    archive, names = source_names(root, base)
    chunks = archive["chunks"]
    receipt = json.loads((root / base / "index" / "index-receipt.json").read_text("utf-8"))
    archive_sha = sha256(root / base / "chunks.json.gz")
    if receipt.get("corpus_sha256") != archive_sha:
        raise SystemExit("the chunk archive is not the one the index receipt names")
    rows_file = load_jsonl(cases_file)
    asked = list(launch["cases"])
    order = registered(key, cases_file)
    window = effective["all"]["parent_expansion_window"]
    restore = restore_lines(run)
    run_breaks = restore_breaks(restore, launch.get("tenant") or "")
    provenance = {
        **{
            k: launch.get(k)
            for k in (
                "label",
                "code_sha",
                "tenant",
                "chroma_dir",
                "cases_file",
                "started",
                "finished",
                "status",
                "variants",
                "mode",
                "overrides",
                "client_cap_sec",
                "error",
            )
        },
        "settings": effective["settings"],
        "settings_sha256": hashlib.sha256(
            json.dumps(effective["settings"], sort_keys=True).encode()
        ).hexdigest(),
        "parent_expansion_window": window,
        "retriever_build_sec": header.get("retriever_build_sec"),
        "bm25_restore_log": restore,
        "path_breaks": run_breaks,
        "window": header.get("window"),
        "caps": header.get("caps"),
        "data_root": str(root),
        "source_sha256": {n: sha256(root / base / n) for n in SOURCE_FILES},
        "archive_sha256": archive_sha,
        "receipt_corpus_sha256": receipt.get("corpus_sha256"),
        "cases_file_sha256": sha256(cases_file),
        "tools_sha256": {n: sha256(HERE / n) for n in TOOLS if (HERE / n).is_file()},
    }
    gold_cases = places = sources = None
    if base in METRICS:
        from evaluation import external_bases as bases
        from evaluation import external_gold as gold
        from evaluation import external_parts as parts
        from scripts import external_base
        from scripts.external_pilot import Places

        converted = bases.registration()
        gold_cases = {c["case_id"]: c for c in parts.load_cases(root / base, base, converted)}
        if base != "wixqa":
            _, sources = external_base._corpus(root / base)
        places = Places(chunks, sources, converted["chunking"]["chunk_overlap"], window)
        provenance.update(
            match_rule=gold.MATCH_RULE,
            chunking=converted["chunking"],
            chunks_without_a_place=places.without_place,
            registrations={p.name: sha256(p) for p in (bases.REGISTRATION, parts.REGISTRATION)},
            measure_code={n: sha256(WS / n) for n in MEASURE_CODE},
        )
    same = {}
    if answers:
        same = {
            r["case_id"]: r["prompts"][0]["sha256"]
            for r in load_jsonl(Path(answers))
            if r.get("prompts")
        }
    rows = []
    for path in sorted((run / "retrieval").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        row = {
            "case_id": record["case_id"],
            "index": record["index"],
            "walls": record["walls"],
            "reranker_ok": record["reranker_ok"],
            "rerank_status": (record["path"] or {}).get("rerank_status"),
            "candidates": (record["path"] or {}).get("candidates"),
            "pool": pool_ranks(record["lanes"], record["pool"] or []),
            "ranked_scores": [r[2] for r in record["ranked"]],
            "expanded_documents": len(record["expanded"]),
            "expanded_chars": sum(len(e["text"]) for e in record["expanded"]),
            "sent_documents": len(record["sent"]),
            "sent_chars": sum(len(d["text"]) for d in record["sent"]),
            "cut": any(d["cut"] for d in record["sent"]),
            "prompt": {k: record["prompt"][k] for k in ("sha256", "chars", "est_tokens")},
            "answer_prompt_same": (
                None
                if record["case_id"] not in same
                else same[record["case_id"]] == record["prompt"]["sha256"]
            ),
        }
        row["path_breaks"] = (
            path_breaks(row["candidates"], row["rerank_status"], row["expanded_documents"])
            + run_breaks
        )
        if gold_cases is not None:
            from scripts.external_pilot import gold_documents

            case = gold_cases[record["case_id"]]
            row.update(
                stratum=case.get("stratum"),
                gold=bool(gold_documents(base, case)),
                unresolved_evidence=len(case.get("unresolved_evidence") or []),
            )
            if row["gold"]:
                row["gold_in_index"] = in_index(base, case, places)
                row.update(coverage(base, case, record, places, sources, chunks))
        rows.append(row)
    measured = [r["case_id"] for r in rows]
    first = [r for r in rows if r["index"] == 1]
    rest = [r for r in rows if r["index"] > 1]
    aggregate = {
        "registered": len(order),
        "asked": len(asked),
        "measured": len(measured),
        "missing": [i for i in order if i not in measured],
        "in_registered_order": measured == [i for i in order if i in measured],
        # Stage 1's definition, «The path breaks» of the spec: any entry stops the work.
        "path_breaks": {r["case_id"]: r["path_breaks"] for r in rows if r["path_breaks"]},
        "walls": {
            name: {
                w: spread([r["walls"].get(w) for r in group])
                for w in ("retrieval", "vector", "rerank")
            }
            for name, group in (("first", first), ("rest", rest))
        },
        "reranker_ok": sum(1 for r in rows if r["reranker_ok"]),
        "rerank_status": dict(Counter(str(r["rerank_status"]) for r in rows)),
        "pool_size": spread([len(r["pool"]) for r in rows]),
        "sent_documents": dict(Counter(r["sent_documents"] for r in rows)),
        "cut": sum(1 for r in rows if r["cut"]),
        "prompt_est_tokens": spread([r["prompt"]["est_tokens"] for r in rows]),
        "memory": memory(load_jsonl(run / "resources.jsonl")),
    }
    if answers:
        aggregate["parity"] = dict(Counter(str(r["answer_prompt_same"]) for r in rows))
    if gold_cases is not None:
        aggregate["m3"] = external_aggregate(base, rows)
    record = {
        "run": label,
        "key": key,
        "base": base,
        "provenance": provenance,
        "aggregate": aggregate,
    }
    questions = [r["query"] for r in rows_file]
    without_text(record, names, questions)
    without_text(rows, names, questions)
    write(out, label, record, rows)
    print(json.dumps(aggregate, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""The no-reranker point: the fused order's first five against the reranker's, on stage 2's lists.

docs/specs/no-rerank-point.md, registered with this tool before the count; PLAN.md stage 4,
step 3. Reads stage 2's retrieval records of stand 5e308fe and the bases' chunk archives on the
Mac, and the committed export of the same runs, and no model:

  python reports/no-rerank/tools/no_rerank_point.py RUNS DATA_ROOT [OUT]
  e.g. ... /Users/julia/RAG_new_chat_5e308fe/chatlive/runs /Users/julia/RAG_new_external_s1

Per question with gold, stage 2's metrics (scripts/external_pilot.read_gold) at four points:
  ranked          - the reranker's five, as recorded;
  fused           - the pool's first five in its recorded fused order: what
                    HybridRetriever.get_relevant_documents_with_path keeps with no reranker;
  expanded_ranked - the recorded expansion of the ranked five;
  expanded_fused  - the product's HybridRetriever._expand_parents on the fused five over the
                    chunk archive, with the run's window, character budget and chunk overlap.
Before any number: ranked and expanded_ranked must equal the committed export's points (else the
tool stops), and _expand_parents on the ranked five must give the recorded texts - a question
where it does not is left out of the expanded pair, more than MAX_UNREPRODUCED on a base make
the base's expanded pair NOT_EVIDENCE. aircargo, without gold documents, gives only how many of
the five the two orders share.

Writes OUT/record.json (provenance, the pairs, the reading) and OUT/rows.jsonl (one question a
line: ids, flags, numbers); stage2_common.without_text refuses either when a string of it names
a document of the base or holds a question.
"""

import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
sys.path.insert(0, str(WS / "reports" / "stage2" / "tools"))
sys.path.insert(1, str(WS))
from retrieval_summary import position  # noqa: E402
from stage2_common import load_jsonl, sha256, source_names, spread, without_text  # noqa: E402

SPEC = "docs/specs/no-rerank-point.md"
CODE_SHA = "5e308fe48cca0955c3007057a574a425f71e2a6a"
EXPORT = WS / "reports" / "stage2" / "retrieval-20261021"
LABELS = {
    "wixqa": "p2-wixqa",
    "conditionalqa": "p2-conditionalqa",
    "multihoprag": "p2-multihoprag",
    "aircargo": "p2-aircargo",
}
METRICS = {
    "wixqa": ("gold_article", "gold_articles"),
    "conditionalqa": ("all_evidence_coverage", "evidence_recall"),
    "multihoprag": ("all_evidence_coverage", "evidence_recall"),
}
PAIRS = {"ranked": ("ranked", "fused"), "expanded": ("expanded_ranked", "expanded_fused")}
TOP = 5
ALPHA = 0.05
MAX_UNREPRODUCED = 5
NOT_EVIDENCE = "NOT_EVIDENCE"
KEEP = "the fused five keep the gold"
EARNS = "the reranker earns its place"
MEASURE_CODE = (
    "vectordb/_base_manager.py",
    "vectordb/parent_join.py",
    "vectordb/contextual_header.py",
    "scripts/external_pilot.py",
    "scripts/external_base.py",
    "evaluation/external_gold.py",
    "evaluation/external_parts.py",
    "evaluation/external_bases.py",
    "reports/stage2/tools/retrieval_summary.py",
    "reports/stage2/tools/stage2_common.py",
)


def mcnemar(b, c):
    """The exact two-sided McNemar p: the binomial on the b + c discordant pairs at one half."""
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n)


def reading(b, c, p):
    """The spec's frozen reading of one pair; b - gold only with the reranker, c - only without."""
    if p < ALPHA and b > c:
        return "loss"
    if p < ALPHA and c > b:
        return "gain"
    return "no detected difference"


def mean(values):
    values = list(values)
    return round(math.fsum(values) / len(values), 4) if values else None


def pair(rows, left, right):
    """One pair on the questions read at both points, by each question's primary metric."""
    both = [r for r in rows if left in r["points"] and right in r["points"]]

    def hit(row, side):
        return row["points"][side][METRICS[row["base"]][0]] == 1.0

    b = sum(1 for r in both if hit(r, left) and not hit(r, right))
    c = sum(1 for r in both if hit(r, right) and not hit(r, left))
    p = mcnemar(b, c)
    out = {
        "n": len(both),
        "hits": {side: sum(1 for r in both if hit(r, side)) for side in (left, right)},
        "b_reranker_only": b,
        "c_fused_only": c,
        "p": round(p, 6),
        "reading": reading(b, c, p),
    }
    bases = {r["base"] for r in both}
    if len(bases) == 1:
        second = METRICS[bases.pop()][1]
        out[second] = {
            side: mean(r["points"][side][second] for r in both) for side in (left, right)
        }
    return out


def pairs(rows, not_evidence):
    """The ranked pair and the expanded pair; the latter on the reproduced questions only."""
    reproduced = [r for r in rows if r.get("expansion_reproduced")]
    return {
        "ranked": pair(rows, *PAIRS["ranked"]),
        "expanded": NOT_EVIDENCE if not_evidence else pair(reproduced, *PAIRS["expanded"]),
    }


def verdict(per_base, pooled):
    """The spec's decision, read at the expanded pair."""
    expanded = [v["expanded"] for v in per_base.values()] + [pooled["expanded"]]
    if NOT_EVIDENCE in expanded:
        return NOT_EVIDENCE
    return EARNS if any(e["reading"] == "loss" for e in expanded) else KEEP


def described(documents):
    """The seeds and texts of a retriever's documents, the way the records hold them."""
    return [
        {"metadata": {"chunk_index": d.metadata.get("chunk_index")}, "text": d.page_content}
        for d in documents
    ]


class Expansion:
    """The product's parent expansion over a base's chunk archive, at the run's settings."""

    def __init__(self, chunks, settings):
        from vectordb._base_manager import Document, HybridRetriever

        # The index stamps each chunk's archive position as its chunk_index.
        self.docs = [
            Document(page_content=c["page_content"], metadata={**c["metadata"], "chunk_index": i})
            for i, c in enumerate(chunks)
        ]
        self.overlap = settings["chunk_overlap"]
        self.retriever = HybridRetriever(
            vector_store=None,
            chunks=self.docs,
            rerank_k=TOP,
            use_bm25=False,
            parent_expansion=True,
            parent_expansion_window=settings["parent_expansion_window"],
            parent_expansion_max_chars=settings["parent_expansion_max_chars"],
        )

    def __call__(self, members):
        import config.settings as config

        # _expand_parents reads the chunk overlap from get_settings() when it is called.
        real = config.get_settings
        config.get_settings = lambda: SimpleNamespace(chunk_overlap=self.overlap)
        try:
            return described(self.retriever._expand_parents([self.docs[m] for m in members]))
        finally:
            config.get_settings = real


def question(base, case, record, chunks, places, expand):
    """One question's row: the four points, the checks' flags, the shared count, the seconds."""
    from scripts.external_pilot import read_gold

    pool = record["pool"] or []
    ranked = [position(r, chunks) for r in record["ranked"]][:TOP]
    fused = [position(p, chunks) for p in pool[:TOP]]
    row = {
        "case_id": record["case_id"],
        "base": base,
        "index": record["index"],
        "pool_size": len(pool),
        "shared_of_five": len(set(ranked) & set(fused)),
        "rerank_sec": record["walls"].get("rerank"),
        "reranker_ok": record["reranker_ok"],
    }
    if case is None:
        return row
    recorded = [
        {"metadata": {"chunk_index": e["chunk_index"]}, "text": e["text"]}
        for e in record["expanded"]
    ]
    row.update(stratum=case.get("stratum"), points={}, unresolved=None)
    row["points"]["ranked"] = read_gold(base, case, ranked, places)
    row["points"]["expanded_ranked"] = read_gold(base, case, places.members(recorded), places)
    row["expansion_reproduced"] = expand(ranked) == recorded
    row["short_pool"] = len(pool) < TOP
    if row["short_pool"]:
        return row
    point = "fused"
    try:
        row["points"]["fused"] = read_gold(base, case, fused, places)
        point = "expanded_fused"
        members = places.members(expand(fused))
        row["points"]["expanded_fused"] = read_gold(base, case, members, places)
    except ValueError:
        row["unresolved"] = point
    return row


def export_rows(label, manifest):
    """The committed export's rows of a run, held to its manifest."""
    name = f"{label}.cases.jsonl"
    if sha256(EXPORT / name) != manifest["files"][name]:
        raise SystemExit(f"{name} is not the file the export's manifest names")
    return {r["case_id"]: r for r in load_jsonl(EXPORT / name)}


def recount(rows, committed):
    """Check 1: the recorded points read again equal the committed ones, question by question."""
    for row in rows:
        if "points" not in row:
            continue
        points = committed[row["case_id"]]["points"]
        if (row["points"]["ranked"], row["points"]["expanded_ranked"]) != (
            points["ranked"],
            points["expanded"],
        ):
            raise SystemExit(f"{row['case_id']}: the recount differs from the committed export")


def base_rows(base, runs, root, manifest):
    """The rows of one base and its run's provenance."""
    label = LABELS[base]
    run = runs / label
    launch = json.loads((run / "launch.json").read_text(encoding="utf-8"))
    if launch.get("status") != "complete" or launch.get("code_sha") != CODE_SHA:
        raise SystemExit(f"{label}: not a complete run of {CODE_SHA}: NOT_EVIDENCE")
    settings = json.loads((run / "effective_settings.json").read_text(encoding="utf-8"))["all"]
    if settings["rerank_top_k"] != TOP or not settings["parent_expansion"]:
        raise SystemExit(f"{label}: not the five-and-expansion path")
    archive, names = source_names(root, base)
    chunks = archive["chunks"]
    receipt = json.loads((root / base / "index" / "index-receipt.json").read_text("utf-8"))
    archive_sha = sha256(root / base / "chunks.json.gz")
    if receipt.get("corpus_sha256") != archive_sha:
        raise SystemExit(f"{base}: the chunk archive is not the one the index receipt names")
    committed = json.loads((EXPORT / f"{label}.json").read_text(encoding="utf-8"))
    if committed["provenance"]["archive_sha256"] != archive_sha:
        raise SystemExit(f"{base}: the chunk archive is not the one the export read")
    cases, places = {}, None
    if base in METRICS:
        from evaluation import external_bases as bases
        from evaluation import external_parts as parts
        from scripts import external_base
        from scripts.external_pilot import Places, gold_documents

        converted = bases.registration()
        cases = {
            c["case_id"]: c
            for c in parts.load_cases(root / base, base, converted)
            if gold_documents(base, c)
        }
        sources = None if base == "wixqa" else external_base._corpus(root / base)[1]
        places = Places(
            chunks,
            sources,
            converted["chunking"]["chunk_overlap"],
            settings["parent_expansion_window"],
        )
    expand = Expansion(chunks, settings) if cases else None
    rows = [
        question(base, cases.get(record["case_id"]), record, chunks, places, expand)
        for record in (
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((run / "retrieval").glob("*.json"))
        )
    ]
    recount(rows, export_rows(label, manifest))
    provenance = {
        "label": label,
        "code_sha": launch["code_sha"],
        "tenant": launch.get("tenant"),
        "settings": {
            k: settings[k]
            for k in (
                "rerank_top_k",
                "rrf_k",
                "chunk_overlap",
                "parent_expansion_window",
                "parent_expansion_max_chars",
            )
        },
        "archive_sha256": archive_sha,
        "cases_file_sha256": sha256(Path(launch["cases_file"])),
        "launch_sha256": sha256(run / "launch.json"),
    }
    questions = [r["query"] for r in load_jsonl(Path(launch["cases_file"]))]
    return rows, provenance, names, questions


def summary(base, rows):
    """A base's counts, its pairs and what stands beside them."""
    out = {
        "questions": len(rows),
        "shared_of_five": dict(sorted(Counter(r["shared_of_five"] for r in rows).items())),
        "shared_of_five_mean": mean(r["shared_of_five"] for r in rows),
        "rerank_sec": spread([r["rerank_sec"] for r in rows]),
        "reranker_ok": sum(1 for r in rows if r["reranker_ok"]),
    }
    if base not in METRICS:
        return out
    gold = [r for r in rows if "points" in r]
    unreproduced = sum(1 for r in gold if not r["expansion_reproduced"])
    out.update(
        with_gold=len(gold),
        short_pool=sum(1 for r in gold if r["short_pool"]),
        unresolved=dict(Counter(str(r["unresolved"]) for r in gold)),
        unreproduced=unreproduced,
        **pairs(gold, unreproduced > MAX_UNREPRODUCED),
    )
    return out


def git_head():
    done = subprocess.run(
        ["git", "-C", str(WS), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return done.stdout.strip() or None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    runs, root = Path(argv[0]), Path(argv[1])
    out = Path(argv[2]) if len(argv) > 2 else WS / "reports" / "no-rerank" / "5e308fe"
    manifest = json.loads((EXPORT / "manifest.json").read_text(encoding="utf-8"))
    if manifest["code_sha"] != CODE_SHA:
        raise SystemExit("the export is not of the stand the records are")
    all_rows, provenance, bases, names, questions = [], {}, {}, set(), []
    for base in LABELS:
        rows, provenance[base], held, asked = base_rows(base, runs, root, manifest)
        bases[base] = summary(base, rows)
        all_rows += rows
        names |= held
        questions += asked
    gold = [r for r in all_rows if "points" in r]
    per_base = {b: bases[b] for b in METRICS}
    pooled = pairs(gold, any(v["expanded"] == NOT_EVIDENCE for v in per_base.values()))
    record = {
        "spec": SPEC,
        "stand_code_sha": CODE_SHA,
        "measured_at_head": git_head(),
        "inputs": {
            "runs": str(runs),
            "data_root": str(root),
            "export": str(EXPORT.relative_to(WS)),
            "export_manifest_sha256": sha256(EXPORT / "manifest.json"),
        },
        "tool_sha256": sha256(Path(__file__)),
        "measure_code_sha256": {n: sha256(WS / n) for n in MEASURE_CODE},
        "provenance": provenance,
        "bases": bases,
        "pooled": pooled,
        "decision": verdict(per_base, pooled),
    }
    without_text(record, names, questions)
    without_text(all_rows, names, questions)
    out.mkdir(parents=True, exist_ok=True)
    (out / "record.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    (out / "rows.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in all_rows), encoding="utf-8"
    )
    print(json.dumps({"bases": bases, "pooled": pooled, "decision": record["decision"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

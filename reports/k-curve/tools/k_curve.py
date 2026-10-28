"""The K curve after expansion: the five the reranker keeps from each lane's first K, expanded.

docs/specs/k-curve-expanded.md, registered with this tool before the count; PLAN.md stage 4,
step 3. Reads what the no-reranker point reads, through its tool
(reports/no-rerank/tools/no_rerank_point.py, whose loading, checks, expansion and exact McNemar
this one imports): stage 2's retrieval records of stand 5e308fe and the bases' chunk archives
on the Mac, and the committed export of the same runs; no model:

  python reports/k-curve/tools/k_curve.py RUNS DATA_ROOT [OUT]
  e.g. ... /Users/julia/RAG_new_chat_5e308fe/chatlive/runs /Users/julia/RAG_new_external_s1

For K = 5 ... 20 and every question, the product's own selection on the recorded lists:
HybridRetriever._rrf_merge over the first K of each recorded lane, then
HybridRetriever._rerank_scored_with_status with a stand-in cross-encoder that returns each
candidate's recorded whole score - one stable sort, ties in the K pool's fused order, cut at
five - then the product's HybridRetriever._expand_parents over the chunk archive. Per question
with gold, stage 2's metrics (scripts/external_pilot.read_gold) before and after the expansion;
each K below 20 against K = 20 at the expanded point, per base and pooled.

The tool stops and writes nothing when K = 20 is not the recorded path (its pool, its five with
their scores, their expansion), when K = 20's points are not the committed export's, when a K's
point before the expansion is not the export's K curve, or when a candidate has no recorded
finite score. A question whose expanded point cannot be read at some K is left out of every K;
more than MAX_UNREAD such questions make the base's comparison NOT_EVIDENCE.

Writes OUT/record.json (provenance, the pairs, the reading) and OUT/rows.jsonl (one question a
line: ids, flags, numbers); stage2_common.without_text refuses either when a string of it names
a document of the base or holds a question.
"""

import functools
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
sys.path.insert(0, str(WS / "reports" / "no-rerank" / "tools"))
import no_rerank_point as nr  # noqa: E402
from retrieval_summary import position  # noqa: E402
from stage2_common import sha256, spread, without_text  # noqa: E402

SPEC = "docs/specs/k-curve-expanded.md"
KS = tuple(range(5, 21))
KMAX = KS[-1]
MAX_UNREAD = 5
NOT_EVIDENCE = nr.NOT_EVIDENCE
OUT = WS / "reports" / "k-curve" / "5e308fe"
MEASURE_CODE = (
    *nr.MEASURE_CODE,
    "reports/no-rerank/tools/no_rerank_point.py",
    "utils/request_deadline.py",
)
# The no-reranker point's pair names its sides by its two points; here they are K = 20 and K.
RENAMED = {"b_reranker_only": "b_k20_only", "c_fused_only": "c_k_only"}


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class Recorded:
    """A stand-in for the cross-encoder: the whole score stage 2 recorded for each candidate."""

    def __init__(self):
        self.scores = {}

    def predict(self, pairs, batch_size=None):
        return [self.scores[text] for _, text in pairs]


class Selection:
    """The product's fusion and rerank cut on one base's recorded lanes, at any K.

    Candidates are archive positions. Each stands in as a Document with its chunk's metadata and
    its position as chunk_index, as the index stamps it, so the fusion keys it as the product
    did; its text is the position, which the stand-in reranker reads back.
    """

    def __init__(self, settings):
        self.settings = settings
        self.reranker = Recorded()
        self.retriever = None
        self.docs = {}

    def doc(self, chunks, member):
        if member not in self.docs:
            from vectordb._base_manager import Document

            self.docs[member] = Document(
                page_content=str(member),
                metadata={**chunks[member]["metadata"], "chunk_index": member},
            )
        return self.docs[member]

    def __call__(self, chunks, vector, bm25, scores, k):
        """The pool at K in its fused order, the five kept and their scores."""
        if self.retriever is None:
            from vectordb._base_manager import HybridRetriever

            self.retriever = HybridRetriever(
                vector_store=None,
                chunks=[],
                rerank_k=nr.TOP,
                rrf_k=self.settings["rrf_k"],
                doc_key_chars=self.settings["rrf_doc_key_chars"],
                reranker=self.reranker,
                use_bm25=False,
            )
        lanes = [[self.doc(chunks, m) for m in lane[:k]] for lane in (vector, bm25)]
        # get_relevant_documents_with_path fuses only when the BM25 lane holds something.
        pool = self.retriever._rrf_merge(*lanes) if lanes[1] else lanes[0]
        members = [d.metadata["chunk_index"] for d in pool]
        if not all(finite(scores.get(m)) for m in members):
            raise ValueError(f"a candidate at K = {k} has no recorded finite score")
        self.reranker.scores = {str(m): scores[m] for m in members}
        scored, ok = self.retriever._rerank_scored_with_status("", pool)
        if not ok:
            raise ValueError(f"the recorded scores did not rerank at K = {k}")
        return {
            "pool": members,
            "five": [d.metadata["chunk_index"] for d, _ in scored],
            "scores": [s for _, s in scored],
        }


def question(base, case, record, chunks, places, expand, select):
    """One question's row: at every K the candidates scored and how many of the five are
    K = 20's; with gold, the points before and after the expansion. K = 20 is held to the
    record first."""
    from scripts.external_pilot import read_gold

    case_id = record["case_id"]
    if not record["pool"]:
        raise SystemExit(f"{case_id}: the record holds no pool: NOT_EVIDENCE")
    # Without a BM25 candidate the product does not fuse, and the pool is the vector lane;
    # stage 2's K curve reads such a record so too.
    lanes = record["lanes"] or {"vector": [p[:2] for p in record["pool"]], "bm25": []}
    try:
        vector = [position(x, chunks) for x in lanes["vector"]]
        bm25 = [position(x, chunks) for x in lanes["bm25"]]
        pool = [position(p, chunks) for p in record["pool"]]
        ranked = [position(r, chunks) for r in record["ranked"]][: nr.TOP]
        scores = dict(zip(pool, (p[2] for p in record["pool"]), strict=True))
        picks = {k: select(chunks, vector, bm25, scores, k) for k in KS}
    except ValueError as error:
        raise SystemExit(f"{case_id}: {error}: NOT_EVIDENCE") from error
    top = picks[KMAX]
    if (top["pool"], top["five"], top["scores"]) != (
        pool,
        ranked,
        [r[2] for r in record["ranked"]][: nr.TOP],
    ):
        raise SystemExit(f"{case_id}: K = {KMAX} is not the recorded pool and five: NOT_EVIDENCE")
    row = {
        "case_id": case_id,
        "base": base,
        "index": record["index"],
        "reranker_ok": record["reranker_ok"],
        "curve": [
            {
                "k": k,
                "candidates": len(picks[k]["pool"]),
                "same_five": len(set(picks[k]["five"]) & set(ranked)),
            }
            for k in KS
        ],
    }
    if case is None:
        return row
    recorded = [
        {"metadata": {"chunk_index": e["chunk_index"]}, "text": e["text"]}
        for e in record["expanded"]
    ]
    if expand(ranked) != recorded:
        raise SystemExit(f"{case_id}: the product's expansion is not the recorded one")
    try:
        before = {k: read_gold(base, case, picks[k]["five"], places) for k in KS}
        after = {tuple(ranked): read_gold(base, case, places.members(recorded), places)}
    except ValueError as error:
        raise SystemExit(f"{case_id}: {error}, where the export read it") from error
    row.update(stratum=case.get("stratum"), unresolved=None)
    # K = 20's points, which the export holds; no_rerank_point.recount reads them.
    row["points"] = {"ranked": before[KMAX], "expanded_ranked": after[tuple(ranked)]}
    for k in KS:
        five = tuple(picks[k]["five"])
        if five in after:
            continue
        try:
            after[five] = read_gold(base, case, places.members(expand(list(five))), places)
        except ValueError:
            row["unresolved"] = k
            break
    for entry in row["curve"]:
        entry["ranked"] = before[entry["k"]]
        if row["unresolved"] is None:
            entry["expanded"] = after[tuple(picks[entry["k"]]["five"])]
    return row


def against_export(rows, committed):
    """Check 4: before the expansion, every K's point is the export's K curve at that K."""
    for row in rows:
        if "points" not in row:
            continue
        exported = committed[row["case_id"]]
        curve = exported.get("k_curve") or []
        if exported.get("k20_is_ranked") is not True or any(
            len(curve) < entry["k"] or entry["ranked"] != curve[entry["k"] - 1]
            for entry in row["curve"]
        ):
            raise SystemExit(f"{row['case_id']}: the curve before expansion is not stage 2's")


def base_rows(base, runs, root, manifest):
    """The no-reranker point's loading and checks of one base, with this point's rows."""
    label = nr.LABELS[base]
    path = runs / label / "effective_settings.json"
    settings = json.loads(path.read_text(encoding="utf-8"))["all"]
    if settings["retrieval_top_k"] != KMAX:
        raise SystemExit(f"{label}: the lanes are not of {KMAX} candidates")
    # no_rerank_point.base_rows builds a row a question through its module's question(); this
    # point's row takes its place for the one call, and the loading and checks stay its own.
    original = nr.question
    nr.question = functools.partial(question, select=Selection(settings))
    try:
        rows, provenance, names, questions = nr.base_rows(base, runs, root, manifest)
    finally:
        nr.question = original
    against_export(rows, nr.export_rows(label, manifest))
    provenance["settings"].update(
        retrieval_top_k=settings["retrieval_top_k"],
        rrf_doc_key_chars=settings["rrf_doc_key_chars"],
    )
    return rows, provenance, names, questions


def at(row, k):
    """A row's entry at K; the curve runs over KS in order."""
    return row["curve"][KS.index(k)]


def pair(rows, k, point):
    """K against 20 at one point, by each question's primary metric: the no-reranker point's
    pair, with b - gold at 20 only - and c - gold at K only."""
    view = [
        {"base": r["base"], "points": {"k20": at(r, KMAX)[point], "k": at(r, k)[point]}}
        for r in rows
    ]
    return {RENAMED.get(key, key): value for key, value in nr.pair(view, "k20", "k").items()}


def pairs(rows, k, not_evidence):
    """The pair before the expansion, which stands beside, and after it, which is read."""
    return {
        "ranked": pair(rows, k, "ranked"),
        "expanded": NOT_EVIDENCE if not_evidence else pair(rows, k, "expanded"),
    }


def summary(base, rows):
    """A base's counts, each K's pairs against 20 and what stands beside them."""
    out = {"questions": len(rows), "reranker_ok": sum(1 for r in rows if r["reranker_ok"])}
    read, not_evidence = [], False
    if base in nr.METRICS:
        gold = [r for r in rows if "points" in r]
        read = [r for r in gold if r["unresolved"] is None]
        not_evidence = len(gold) - len(read) > MAX_UNREAD
        out.update(with_gold=len(gold), unresolved=len(gold) - len(read))
    out["curve"] = []
    for k in KS:
        point = {
            "k": k,
            "candidates": spread([at(r, k)["candidates"] for r in rows]),
            "same_five_mean": nr.mean(at(r, k)["same_five"] for r in rows),
        }
        if base in nr.METRICS and k < KMAX:
            point.update(pairs(read, k, not_evidence))
        out["curve"].append(point)
    return out


def pooled_curve(rows, not_evidence):
    """Each K's pairs over the three bases' questions read at every K."""
    read = [r for r in rows if "points" in r and r["unresolved"] is None]
    return [{"k": k, **pairs(read, k, not_evidence)} for k in KS[:-1]]


def decision(per_base, pooled):
    """The smallest K from which no K below 20 reads a loss, on any base or pooled."""
    curves = {**{base: got["curve"] for base, got in per_base.items()}, "pooled": pooled}
    expanded = {
        where: {p["k"]: p["expanded"] for p in curve if "expanded" in p}
        for where, curve in curves.items()
    }
    if any(got == NOT_EVIDENCE for by_k in expanded.values() for got in by_k.values()):
        return NOT_EVIDENCE
    losses = {
        where: [k for k in sorted(by_k) if by_k[k]["reading"] == "loss"]
        for where, by_k in expanded.items()
    }
    lost = {k for found in losses.values() for k in found}
    smallest = KMAX
    for k in reversed(KS[:-1]):
        if k in lost:
            break
        smallest = k
    return {"smallest_k_without_a_detected_loss": smallest, "losses": losses}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    runs, root = Path(argv[0]), Path(argv[1])
    out = Path(argv[2]) if len(argv) > 2 else OUT
    manifest = json.loads((nr.EXPORT / "manifest.json").read_text(encoding="utf-8"))
    if manifest["code_sha"] != nr.CODE_SHA:
        raise SystemExit("the export is not of the stand the records are")
    all_rows, provenance, bases, names, questions = [], {}, {}, set(), []
    for base in nr.LABELS:
        rows, provenance[base], held, asked = base_rows(base, runs, root, manifest)
        bases[base] = summary(base, rows)
        all_rows += rows
        names |= held
        questions += asked
    per_base = {b: bases[b] for b in nr.METRICS}
    pooled = pooled_curve(
        [r for r in all_rows if r["base"] in nr.METRICS],
        any(got["unresolved"] > MAX_UNREAD for got in per_base.values()),
    )
    record = {
        "spec": SPEC,
        "stand_code_sha": nr.CODE_SHA,
        "measured_at_head": nr.git_head(),
        "inputs": {
            "runs": str(runs),
            "data_root": str(root),
            "export": str(nr.EXPORT.relative_to(WS)),
            "export_manifest_sha256": sha256(nr.EXPORT / "manifest.json"),
        },
        "tool_sha256": sha256(Path(__file__)),
        "measure_code_sha256": {n: sha256(WS / n) for n in MEASURE_CODE},
        "ks": list(KS),
        "provenance": provenance,
        "bases": bases,
        "pooled": pooled,
        "decision": decision(per_base, pooled),
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
    for where, curve in [*((b, got["curve"]) for b, got in per_base.items()), ("pooled", pooled)]:
        for point in curve:
            got = point.get("expanded")
            if isinstance(got, dict):
                print(
                    f"{where} K={point['k']}: {got['hits']['k20']} at 20, {got['hits']['k']} "
                    f"at K, b {got['b_k20_only']}, c {got['c_k_only']}, p {got['p']}, "
                    f"{got['reading']}"
                )
    print(json.dumps({"decision": record["decision"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

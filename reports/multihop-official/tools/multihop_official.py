"""MultiHop-RAG's retrieval by the benchmark's own rule, beside stage 2's, on stage 2's lists.

docs/specs/multihop-official-retrieval.md, registered with this tool before the count; PLAN.md,
the recount by the published rules (the research analysis of 2026-10-25, item 1). Reads stage
2's retrieval records of stand 5e308fe for p2-multihoprag, the base's chunk archive, documents
and cases on the Mac, the pinned MultiHopRAG.json the cases were converted from, and the
committed export of the same run, and no model:

  python reports/multihop-official/tools/multihop_official.py RUNS DATA_ROOT RAW_JSON [OUT]
  e.g. ... /Users/julia/RAG_new_chat_5e308fe/chatlive/runs /Users/julia/RAG_new_external_s1 \
      RAW/multihoprag/MultiHopRAG.json   (RAW: the --raw of `scripts.external_base fetch`)

The rule: calculate_metrics of retrieval_evaluate.py in yixuantt/MultiHop-RAG at OFFICIAL's
commit - unchanged there since 2d0ecc3 of 2024-03-15 - and main_eval's skip of the null queries
(official_eval); both are copied below, nothing of the download is imported or run. The input,
per question: question_type and gold_list - the pinned row's type and its evidence facts as
they stand; retrieval_list - the primary list: the texts of the reranker's first ten, the pool
by its recorded scores with ties in fused order (the product's stable sort), each its chunk's
text as the archive holds it, the contextual header included; the secondary list: the recorded
expansion of the kept five. Beside them, stage 2's metrics (scripts/external_pilot.read_gold,
external-gold/range-coverage-v1) at the same first four and first ten, and the export's own
points.

Before any number the tool stops unless: the run is complete and of the stand; the archive is
the index's and the export's; every recorded pool is the export's; each case's row of the
pinned file is its question with its evidence; the questions main_eval keeps are stage 2's 70
with gold, each pool scored whole, its reranker order starting with the five the product kept,
read_gold at those five giving the export's points.ranked, and every chunk of the first ten
placed in its document.

Writes OUT/record.json (provenance, the numbers, their intervals, the readings) and
OUT/rows.jsonl (one question a line: ids, flags, numbers); stage2_common.without_text refuses
either when a string of it names a document of the base, or holds a question or a gold fact.
"""

import hashlib
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
from stage2_common import load_jsonl, pool_ranks, sha256, source_names, without_text  # noqa: E402

SPEC = "docs/specs/multihop-official-retrieval.md"
CODE_SHA = "5e308fe48cca0955c3007057a574a425f71e2a6a"
EXPORT = WS / "reports" / "stage2" / "retrieval-20261021"
OUT = WS / "reports" / "multihop-official" / "5e308fe"
BASE = "multihoprag"
LABEL = "p2-multihoprag"
RAW_FILE = "MultiHopRAG.json"
# Where the rule was read (curl, never run); calculate_metrics is unchanged since "since".
OFFICIAL = {
    "repository": "https://github.com/yixuantt/MultiHop-RAG",
    "path": "retrieval_evaluate.py",
    "commit": "c1c1287aa60a94acf9c4d20c891c9cd611a0f6e8",
    "blob": "a65720ff0d9551cd9f97084174845f14ee8831f5",
    "sha256": "6734516f0d5f9385076f76bf4e08d54968541fdb05f519f1cf687c0b65ae0f90",
    "since": "2d0ecc32da99dc32bc60d76ba991a72af5a09d4b",
}
NULL_QUERY = "null_query"
METRICS = ("Hits@10", "Hits@4", "MAP@10", "MRR@10")
SHARES = ("Hits@10", "Hits@4")
DEPTH = 10  # simple_retrieval.py keeps the reranker's top_n = --topk, 10 by default
KS = (4, 10)
TOP = 5
WITH_GOLD = 70
POINTS = ("ranked", "expanded", "sent")
# The published numbers, each with bge-reranker-large over 20 retrieved chunks. The paper,
# arXiv 2401.15391v1, Table 5: its four embedders whose Hits@4 is above 0.6, of eight.
PAPER = {
    "text-embedding-ada-002": {
        "MRR@10": 0.5477,
        "MAP@10": 0.4625,
        "Hits@10": 0.7059,
        "Hits@4": 0.6169,
    },
    "text-search-ada-query-001": {
        "MRR@10": 0.5483,
        "MAP@10": 0.4625,
        "Hits@10": 0.7064,
        "Hits@4": 0.6174,
    },
    "bge-large-en-v1.5": {"MRR@10": 0.563, "MAP@10": 0.4759, "Hits@10": 0.7183, "Hits@4": 0.6364},
    "voyage-02": {"MRR@10": 0.586, "MAP@10": 0.4795, "Hits@10": 0.7467, "Hits@4": 0.6625},
}
# Multi-Meta-RAG, arXiv 2406.13213v2, Table 2: its baseline run by this script, "(evaluated)".
SCRIPT = {
    "bge-large-en-v1.5": {"MRR@10": 0.6029, "MAP@10": 0.2687, "Hits@10": 0.749, "Hits@4": 0.6661},
    "voyage-02": {"MRR@10": 0.6016, "MAP@10": 0.2619, "Hits@10": 0.7419, "Hits@4": 0.663},
}
ABOVE = "above the band"
BELOW = "below the band"
APART = "not detected apart from the band"
MEASURE_CODE = (
    "scripts/external_pilot.py",
    "scripts/external_base.py",
    "scripts/chat_signals.py",
    "evaluation/external_gold.py",
    "evaluation/external_parts.py",
    "evaluation/external_bases.py",
    "evaluation/external_bases.json",
    "evaluation/semantic_ruler.py",
    "reports/stage2/tools/retrieval_summary.py",
    "reports/stage2/tools/stage2_common.py",
    "reports/stage2/tools/judge_export.py",
    "reports/stage2/tools/stage2_record.py",
)


# calculate_metrics of retrieval_evaluate.py at OFFICIAL["commit"], line for line: its names,
# its order and its arithmetic, so its floats are the script's. Three spellings differ, as ruff
# writes them, with the same operations: zip(..., strict=False) for zip(...), x not in y for
# not x in y, double quotes for single.
def calculate_metrics(retrieved_lists, gold_lists):
    hits_at_10_count = 0
    hits_at_4_count = 0
    map_at_10_list = []
    mrr_list = []

    for retrieved, gold in zip(retrieved_lists, gold_lists, strict=False):
        hits_at_10_flag = False
        hits_at_4_flag = False
        average_precision_sum = 0
        first_relevant_rank = None
        find_gold = []

        gold = [item.replace(" ", "").replace("\n", "") for item in gold]
        retrieved = [item.replace(" ", "").replace("\n", "") for item in retrieved]

        for rank, retrieved_item in enumerate(retrieved[:11], start=1):
            if any(gold_item in retrieved_item for gold_item in gold):
                if rank <= 10:
                    hits_at_10_flag = True
                    if first_relevant_rank is None:
                        first_relevant_rank = rank
                    if rank <= 4:
                        hits_at_4_flag = True
                    # Compute precision at this rank for this query
                    count = 0
                    for gold_item in gold:
                        if gold_item in retrieved_item and gold_item not in find_gold:
                            count = count + 1
                            find_gold.append(gold_item)
                    precision_at_rank = count / rank
                    average_precision_sum += precision_at_rank

        # Calculate metrics for this query
        hits_at_10_count += int(hits_at_10_flag)
        hits_at_4_count += int(hits_at_4_flag)
        map_at_10_list.append(average_precision_sum / min(len(gold), 10))
        mrr_list.append(1 / first_relevant_rank if first_relevant_rank else 0)

    # Calculate average metrics over all queries
    hits_at_10 = hits_at_10_count / len(gold_lists)
    hits_at_4 = hits_at_4_count / len(gold_lists)
    map_at_10 = sum(map_at_10_list) / len(gold_lists)
    mrr_at_10 = sum(mrr_list) / len(gold_lists)

    return {
        "Hits@10": hits_at_10,
        "Hits@4": hits_at_4,
        "MAP@10": map_at_10,
        "MRR@10": mrr_at_10,
    }


def official_eval(data):
    """main_eval of the same file on its parsed input, without the file and the prints: a
    question of type null_query is skipped, every other one read; None when none is left (the
    script prints so and returns)."""
    retrieved_lists = []
    gold_lists = []

    for d in data:
        if d["question_type"] == NULL_QUERY:
            continue
        retrieved_lists.append([m["text"] for m in d["retrieval_list"]])
        gold_lists.append([m["fact"] for m in d["gold_list"]])

    if not retrieved_lists:
        return None

    return calculate_metrics(retrieved_lists, gold_lists)


def printed(metrics):
    """The numbers as main_eval prints them, at four decimals."""
    return {metric: f"{value:.4f}" for metric, value in metrics.items()}


def normalise(text):
    """The official normalisation: every space and every newline removed, nothing else."""
    return text.replace(" ", "").replace("\n", "")


def distinct_facts(gold):
    """The gold facts once each after the official normalisation, in order: what find_gold can
    come to hold."""
    return list(dict.fromkeys(normalise(fact) for fact in gold))


def substring_found(retrieved, gold, k):
    """How many distinct gold facts stand whole in one of the first k texts by the official
    matching: a diagnostic, not a published metric."""
    texts = [normalise(text) for text in retrieved[:k]]
    return sum(1 for fact in distinct_facts(gold) if any(fact in text for text in texts))


def reranker_order(pool):
    """The pool's candidates, [source, chunk_index], in the reranker's order.

    vectordb._base_manager._rerank_scored_with_status sorts every scored candidate by this key
    with reverse=True, a stable sort: equal scores keep their fused order, the order
    retrieval_summary.k_curve replays; a candidate without a score goes last."""
    ordered = sorted(pool, key=lambda p: (p[2] is not None, p[2] or 0.0), reverse=True)
    return [list(p[:2]) for p in ordered]


def first_ten(record):
    """The reranker's first ten of a question; stops when the record cannot give the order or
    the order does not start with the five the product kept."""
    pool = record["pool"] or []
    if not record["reranker_ok"] or not pool or any(p[2] is None for p in pool):
        raise SystemExit(f"{record['case_id']}: the pool's scores are not all recorded")
    order = reranker_order(pool)
    if order[:TOP] != [list(r[:2]) for r in record["ranked"][:TOP]]:
        raise SystemExit(f"{record['case_id']}: the reranker's order does not give its five")
    return order[:DEPTH]


def pinned_rows(path, registered):
    """The rows of the pinned MultiHopRAG.json, held to the size and SHA-256 the registration
    of the base (evaluation/external_bases.json) gives it."""
    entry = next(f for f in registered["bases"][BASE]["files"] if f["path"] == RAW_FILE)
    data = Path(path).read_bytes()
    if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise SystemExit(f"{path}: not the registered {RAW_FILE}: NOT_EVIDENCE")
    return json.loads(data.decode("utf-8")), entry


def gold_facts(case, rows):
    """A case's row of the pinned file - multihoprag-NNNN is row NNNN - its question type and
    its official gold_list: the evidence facts as they stand, a repeated one repeated. Stops
    when the row is not the case's question or its facts are not the case's evidence."""
    index = int(case["case_id"].rsplit("-", 1)[1])
    row = rows[index]
    if row["query"] != case["query"] or row["question_type"] != case["stratum"]:
        raise SystemExit(f"{case['case_id']}: row {index} of {RAW_FILE} is not its question")
    # The conversion keeps a fact once per (url, fact) and counts the ones it cannot place.
    distinct = dict.fromkeys((item["url"], item["fact"]) for item in row["evidence_list"])
    if len(distinct) != len(case["evidence_groups"]) + case["unresolved_evidence"]:
        raise SystemExit(f"{case['case_id']}: row {index}'s facts are not its evidence")
    return index, row["question_type"], [item["fact"] for item in row["evidence_list"]]


def entries(records, cases, chunks, rows, exported):
    """The official input, one entry a question of the run, in the pinned file's order - the
    order the official retrieval writes. A null query carries no lists: main_eval skips it
    before reading them. Stops when a record's pool is not the export's."""
    out = []
    for record in records:
        case_id = record["case_id"]
        if pool_ranks(record["lanes"], record["pool"] or []) != exported[case_id]["pool"]:
            raise SystemExit(f"{case_id}: the recorded pool is not the export's")
        index, kind, facts = gold_facts(cases[case_id], rows)
        members, texts, expanded = [], [], []
        if kind != NULL_QUERY:
            members = [position(ident, chunks) for ident in first_ten(record)]
            texts = [chunks[member]["page_content"] for member in members]
            expanded = [document["text"] for document in record["expanded"]]
        out.append(
            {
                "case_id": case_id,
                "raw_index": index,
                "question_type": kind,
                "members": members,
                "retrieval_list": [{"text": text} for text in texts],
                "expanded_list": [{"text": text} for text in expanded],
                "gold_list": [{"fact": fact} for fact in facts],
            }
        )
    return sorted(out, key=lambda entry: entry["raw_index"])


def question(entry, case, places, exported):
    """One question main_eval keeps: the official numbers of both lists on it alone (a mean
    over one question is its own value), the substring diagnostic and stage 2's metrics at the
    official K. Stops when read_gold at the five is not the export's points.ranked."""
    from scripts.external_pilot import read_gold

    texts = [m["text"] for m in entry["retrieval_list"]]
    facts = [m["fact"] for m in entry["gold_list"]]
    members = entry["members"]
    if read_gold(BASE, case, members[:TOP], places) != exported["points"]["ranked"]:
        raise SystemExit(f"{entry['case_id']}: the recount differs from the committed export")
    row = {
        "case_id": entry["case_id"],
        "raw_index": entry["raw_index"],
        "stratum": entry["question_type"],
        "evaluated": True,
        "facts": len(facts),
        "distinct": len(distinct_facts(facts)),
        "facts_empty": sum(1 for fact in facts if not normalise(fact)),
        "groups": len(case["evidence_groups"]),
        "listed": len(texts),
        "official": calculate_metrics([texts], [facts]),
        "official_expanded": calculate_metrics(
            [[m["text"] for m in entry["expanded_list"]]], [facts]
        ),
        "substring_found": {},
        "range": {},
    }
    for k in KS:
        row["substring_found"][f"@{k}"] = substring_found(texts, facts, k)
        try:
            row["range"][f"@{k}"] = read_gold(BASE, case, members[:k], places)
        except ValueError as error:
            raise SystemExit(
                f"{entry['case_id']}: a chunk of the first ten has no place"
            ) from error
    return row


def band(metric):
    """The published band of a metric: the lowest and the highest of the paper's four rows and
    of the script's two; MAP@10 of the script's alone - the script does not give the paper's."""
    values = [row[metric] for row in SCRIPT.values()]
    if metric != "MAP@10":
        values += [row[metric] for row in PAPER.values()]
    return min(values), max(values)


def reading(read95, published):
    """The spec's frozen reading of one number against its band, by the interval it reads."""
    low, high = published
    if read95[0] > high:
        return ABOVE
    if read95[1] < low:
        return BELOW
    return APART


def mean(values):
    values = list(values)
    return round(math.fsum(values) / len(values), 4) if values else None


def families_of(cases):
    """Stage 2's clusters of the questions with gold, those joined by a shared gold document
    (judge_export.clusters), each cluster a family."""
    from judge_export import clusters

    return {case: [f"cluster:{number}"] for case, number in clusters(BASE, cases).items()}


def interval(values, families, share):
    """A number over the questions as stage 2 reads it: a share with its n, hits, Wilson's and
    the clusters' 95 % (judge_export.share); a mean with the clusters' 95 %
    (evaluation.semantic_ruler.cluster_summary). read95, the wider, is the one read
    (stage2_record.read95)."""
    from judge_export import share as shared
    from stage2_record import read95

    if share:
        entry = shared(values, families)
    else:
        from evaluation.semantic_ruler import cluster_summary

        summary = cluster_summary(values, {case: families[case] for case in values})
        entry = {
            "n": summary["n"],
            "mean": round(summary["point"], 4),
            "clusters": summary["clusters"],
            "cluster95": [round(value, 4) for value in summary["ci95"]],
        }
    return {**entry, "read95": read95(entry)}


def official_numbers(metrics, rows, key, families, read):
    """One list's official numbers, as printed, with their intervals; read - with the readings
    against the published bands."""
    out = {"metrics": metrics, "printed": printed(metrics), "intervals": {}}
    for metric in METRICS:
        values = {r["case_id"]: r[key][metric] for r in rows}
        if metric in SHARES:
            values = {case: int(value) for case, value in values.items()}
        out["intervals"][metric] = interval(values, families, metric in SHARES)
    if read:
        out["readings"] = {m: reading(out["intervals"][m]["read95"], band(m)) for m in METRICS}
    return out


def beside(rows, families):
    """At each official K, any and all by the substring matching and by stage 2's ranges, and
    stage 2's evidence_recall: the definition and the matching apart."""
    out = {}
    for k in KS:
        at = f"@{k}"
        hits = {
            "substring_any": {r["case_id"]: int(r["official"][f"Hits@{k}"]) for r in rows},
            "substring_all": {
                r["case_id"]: int(r["substring_found"][at] == r["distinct"]) for r in rows
            },
            "range_any": {r["case_id"]: int(r["range"][at]["evidence_recall"] > 0) for r in rows},
            "range_all": {
                r["case_id"]: int(r["range"][at]["all_evidence_coverage"] == 1.0) for r in rows
            },
        }
        out[at] = {name: interval(values, families, True) for name, values in hits.items()}
        recall = {r["case_id"]: r["range"][at]["evidence_recall"] for r in rows}
        out[at]["evidence_recall"] = interval(recall, families, False)
    return out


def discordant(rows):
    """Where the two matchings part at Hits@4: a fact's string in one of the four without a
    group's range covered, and the reverse."""
    official = {r["case_id"]: r["official"]["Hits@4"] == 1.0 for r in rows}
    ranged = {r["case_id"]: r["range"]["@4"]["evidence_recall"] > 0 for r in rows}
    return {
        "substring_only": sum(1 for c in official if official[c] and not ranged[c]),
        "range_only": sum(1 for c in official if ranged[c] and not official[c]),
    }


def committed_points(exported, ids):
    """Stage 2's own points of the same questions, as the committed export holds them."""
    out = {}
    for point in POINTS:
        read = [exported[case]["points"][point] for case in ids]
        out[point] = {
            "n": len(read),
            "all_evidence": sum(1 for p in read if p["all_evidence_coverage"] == 1.0),
            "any_evidence": sum(1 for p in read if p["evidence_recall"] > 0),
            "evidence_recall": mean(p["evidence_recall"] for p in read),
        }
    return out


def export_rows(manifest):
    """The committed export's rows of the run, held to its manifest."""
    name = f"{LABEL}.cases.jsonl"
    if sha256(EXPORT / name) != manifest["files"][name]:
        raise SystemExit(f"{name} is not the file the export's manifest names")
    return {r["case_id"]: r for r in load_jsonl(EXPORT / name)}


def run_inputs(runs, root, manifest):
    """The run's records, the archive, the cases and the places, held to the export and the
    index; the run's provenance, the documents' names and the questions."""
    from evaluation import external_bases as bases
    from evaluation import external_parts as parts
    from scripts import external_base
    from scripts.external_pilot import Places

    run = runs / LABEL
    launch = json.loads((run / "launch.json").read_text(encoding="utf-8"))
    if launch.get("status") != "complete" or launch.get("code_sha") != CODE_SHA:
        raise SystemExit(f"{LABEL}: not a complete run of {CODE_SHA}: NOT_EVIDENCE")
    settings = json.loads((run / "effective_settings.json").read_text(encoding="utf-8"))["all"]
    if settings["rerank_top_k"] != TOP or not settings["parent_expansion"]:
        raise SystemExit(f"{LABEL}: not the five-and-expansion path")
    archive, names = source_names(root, BASE)
    chunks = archive["chunks"]
    receipt = json.loads((root / BASE / "index" / "index-receipt.json").read_text("utf-8"))
    archive_sha = sha256(root / BASE / "chunks.json.gz")
    if receipt.get("corpus_sha256") != archive_sha:
        raise SystemExit(f"{BASE}: the chunk archive is not the one the index receipt names")
    committed = json.loads((EXPORT / f"{LABEL}.json").read_text(encoding="utf-8"))
    if committed["provenance"]["archive_sha256"] != archive_sha:
        raise SystemExit(f"{BASE}: the chunk archive is not the one the export read")
    registered = bases.registration()
    cases = {c["case_id"]: c for c in parts.load_cases(root / BASE, BASE, registered)}
    places = Places(
        chunks,
        external_base._corpus(root / BASE)[1],
        registered["chunking"]["chunk_overlap"],
        settings["parent_expansion_window"],
    )
    records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((run / "retrieval").glob("*.json"))
    ]
    exported = export_rows(manifest)
    if sorted(r["case_id"] for r in records) != sorted(exported):
        raise SystemExit(f"{LABEL}: the records are not the export's questions")
    provenance = {
        "label": LABEL,
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
    return SimpleNamespace(
        records=records,
        chunks=chunks,
        cases=cases,
        places=places,
        exported=exported,
        registered=registered,
        provenance=provenance,
        names=names,
        questions=[r["query"] for r in load_jsonl(Path(launch["cases_file"]))],
    )


def git_head():
    done = subprocess.run(
        ["git", "-C", str(WS), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return done.stdout.strip() or None


def main(argv=None):
    from scripts.external_pilot import gold_documents

    argv = sys.argv[1:] if argv is None else argv
    runs, root, raw = Path(argv[0]), Path(argv[1]), Path(argv[2])
    out = Path(argv[3]) if len(argv) > 3 else OUT
    manifest = json.loads((EXPORT / "manifest.json").read_text(encoding="utf-8"))
    if manifest["code_sha"] != CODE_SHA:
        raise SystemExit("the export is not of the stand the records are")
    got = run_inputs(runs, root, manifest)
    cases, exported = got.cases, got.exported
    pinned, raw_entry = pinned_rows(raw, got.registered)
    data = entries(got.records, cases, got.chunks, pinned, exported)
    kept = [e for e in data if e["question_type"] != NULL_QUERY]
    with_gold = sorted(e["case_id"] for e in data if gold_documents(BASE, cases[e["case_id"]]))
    if sorted(e["case_id"] for e in kept) != with_gold or len(with_gold) != WITH_GOLD:
        raise SystemExit("the questions main_eval keeps are not stage 2's 70 with gold")
    rows = [question(e, cases[e["case_id"]], got.places, exported[e["case_id"]]) for e in kept]
    families = families_of([cases[case] for case in with_gold])
    sizes = Counter(family[0] for family in families.values())
    primary = official_eval(data)
    secondary = official_eval([{**e, "retrieval_list": e["expanded_list"]} for e in data])
    record = {
        "spec": SPEC,
        "stand_code_sha": CODE_SHA,
        "measured_at_head": git_head(),
        "inputs": {
            "runs": str(runs),
            "data_root": str(root),
            "raw": str(raw),
            "export": str(EXPORT.relative_to(WS)),
            "export_manifest_sha256": sha256(EXPORT / "manifest.json"),
        },
        "tool_sha256": sha256(Path(__file__)),
        "measure_code_sha256": {n: sha256(WS / n) for n in MEASURE_CODE},
        "official": OFFICIAL,
        "raw": {**raw_entry, "revision": got.registered["bases"][BASE]["revision"]},
        "provenance": got.provenance,
        "questions": {
            "run": len(data),
            "skipped_null_query": len(data) - len(kept),
            "evaluated": len(rows),
            "strata": dict(Counter(r["stratum"] for r in rows)),
            "clusters": len(sizes),
            "largest_cluster": max(sizes.values()),
            "short_of_ten": sum(1 for r in rows if r["listed"] < DEPTH),
            "facts": sum(r["facts"] for r in rows),
            "facts_repeated": sum(r["facts"] - r["distinct"] for r in rows),
            "facts_empty": sum(r["facts_empty"] for r in rows),
        },
        "official_primary": official_numbers(primary, rows, "official", families, True),
        "official_expanded": official_numbers(
            secondary, rows, "official_expanded", families, False
        ),
        "beside": beside(rows, families),
        "discordant_at_4": discordant(rows),
        "stage2_committed": committed_points(exported, with_gold),
        "published": {
            "paper_table5": PAPER,
            "script_multi_meta_rag_table2": SCRIPT,
            "bands": {m: list(band(m)) for m in METRICS},
        },
    }
    skipped = [
        {
            "case_id": e["case_id"],
            "raw_index": e["raw_index"],
            "stratum": e["question_type"],
            "evaluated": False,
        }
        for e in data
        if e["question_type"] == NULL_QUERY
    ]
    all_rows = sorted(rows + skipped, key=lambda r: r["raw_index"])
    facts = [m["fact"] for e in kept for m in e["gold_list"] if normalise(m["fact"])]
    without_text(record, got.names, got.questions + facts)
    without_text(all_rows, got.names, got.questions + facts)
    out.mkdir(parents=True, exist_ok=True)
    (out / "record.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    (out / "rows.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in all_rows), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "official": record["official_primary"]["printed"],
                "readings": record["official_primary"]["readings"],
                "official_expanded": record["official_expanded"]["printed"],
                "beside_at_4": {
                    k: v.get("hits", v.get("mean")) for k, v in record["beside"]["@4"].items()
                },
                "stage2_committed": record["stage2_committed"],
                "questions": record["questions"],
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Coverage beside quality: the committed M1 judge records read by published rules.

docs/specs/coverage-metrics.md, registered with this tool before the count. Reads the committed
judge exports its «Inputs» name - V3's of stage 2 (reports/stage2/5e308fe/), V4's of stage 2b
(reports/answer-prompt-v4/4f48fed/) - and no model:

  python reports/coverage/tools/coverage_record.py [OUT]

Writes OUT, by default reports/coverage/coverage-record.json: the SHA-256 of each input and of
this tool, the stands' commits, and per key and side the spec's numbers - coverage, good and good
or partial_ok among the answered, unsupported among the answered, the CRAG score, the decline
matrices by the judge's `context_has_answer` and, on an external base, by the base's gold (the
same side's M2 export's `has_reference`; M1 withholds it), with decline precision and recall
from each. A share carries Wilson's 95 % interval and, on an external base, the cluster
bootstrap over stage 2's clusters; the CRAG mean the bootstrap only, each aircargo question its
own cluster.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
sys.path.insert(0, str(WS / "reports" / "stage2" / "tools"))
sys.path.insert(1, str(WS))
from stage2_common import load_jsonl, sha256  # noqa: E402

from evaluation.semantic_ruler import cluster_summary  # noqa: E402
from scripts.chat_signals import wilson  # noqa: E402

SPEC = "docs/specs/coverage-metrics.md"
STANDS = {
    "V3": "5e308fe48cca0955c3007057a574a425f71e2a6a",
    "V4": "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1",
}
INPUTS = {
    "aircargo": {
        "V3": "reports/stage2/5e308fe/p1-aircargo-judge.cases.jsonl",
        "V4": "reports/answer-prompt-v4/4f48fed/v4-aircargo-judge.cases.jsonl",
    },
    "wixqa": {
        "V3": "reports/stage2/5e308fe/p4-wixqa-judge-m1.cases.jsonl",
        "V4": "reports/answer-prompt-v4/4f48fed/v4-wixqa-judge-m1.cases.jsonl",
    },
    "conditionalqa": {
        "V3": "reports/stage2/5e308fe/p4-conditionalqa-judge-m1.cases.jsonl",
        "V4": "reports/answer-prompt-v4/4f48fed/v4-conditionalqa-judge-m1.cases.jsonl",
    },
    "multihoprag": {"V3": "reports/stage2/5e308fe/p4-multihoprag-judge-m1.cases.jsonl"},
}
EXTERNAL = ("wixqa", "conditionalqa", "multihoprag")
# M1 withholds the reference, so its rows' has_reference is false throughout; the base's own
# gold is the same side's M2 export's has_reference, from the references file its plan was
# frozen with. Only that field is read from it, never a verdict.
GOLD = {
    key: {name: path.replace("-judge-m1.", "-judge-m2.") for name, path in sides.items()}
    for key, sides in INPUTS.items()
    if key in EXTERNAL
}
GRADES = ("good", "partial_ok", "bad")


def kind(row):
    """declined, empty or answered: the spec's three; a row must be graded."""
    if row.get("empty_answer"):
        return "empty"
    return "declined" if row["answers_question"] == "declined" else "answered"


def crag(row):
    """CRAG's level, mapped once: good 1, partial_ok 0.5, declined or empty 0, other -1."""
    if kind(row) != "answered":
        return 0.0
    return {"good": 1.0, "partial_ok": 0.5}.get(row["grade"], -1.0)


def share(values, families):
    """values: case -> 0 or 1. Its n, hits, share and Wilson's interval; with families the
    cluster bootstrap."""
    n, hits = len(values), sum(values.values())
    out = {"n": n, "hits": hits, "share": round(hits / n, 4) if n else None}
    out["wilson95"] = wilson(hits, n)
    if families is not None and n:
        out["cluster95"] = [round(v, 4) for v in cluster_summary(values, families)["ci95"]]
    return out


def matrix(rows, truth):
    """Counts of truth (true, false) against declined, answered, empty; decline precision and
    recall: of the declines, those where truth is false; of the falses, those declined."""
    table = {
        str(value).lower(): {name: 0 for name in ("declined", "answered", "empty")}
        for value in (True, False)
    }
    for row in rows:
        table[str(truth(row)).lower()][kind(row)] += 1
    declines = sum(cell["declined"] for cell in table.values())
    falses = sum(table["false"].values())
    return {
        "counts": table,
        "decline_precision": round(table["false"]["declined"] / declines, 4) if declines else None,
        "decline_recall": round(table["false"]["declined"] / falses, 4) if falses else None,
    }


def side(key, rows, gold=None):
    """The spec's numbers for one key and side; gold: case -> the base's has_reference."""
    unknown = sorted({row["grade"] for row in rows} - set(GRADES) - {None})
    if unknown:
        raise SystemExit(f"{key}: grades the spec does not name: {unknown}")
    if len({row["case_id"] for row in rows}) != len(rows):
        raise SystemExit(f"{key}: a question stands twice")
    graded = [row for row in rows if row["grade"] is not None]
    families = None
    if key in EXTERNAL:
        families = {row["case_id"]: [f"cluster:{row['cluster']}"] for row in graded}
    answered = [row for row in graded if kind(row) == "answered"]

    def sub(family_rows):
        return (
            None
            if families is None
            else {r["case_id"]: families[r["case_id"]] for r in family_rows}
        )

    def among(subset, test):
        return share({row["case_id"]: int(test(row)) for row in subset}, sub(subset))

    scores = {row["case_id"]: crag(row) for row in graded}
    own = {case: [case] for case in scores}
    summary = cluster_summary(scores, families if families is not None else own)
    levels = {str(level): sum(v == level for v in scores.values()) for level in (1, 0.5, 0, -1)}
    out = {
        "rows": len(rows),
        "missing": sorted(row["case_id"] for row in rows if row["grade"] is None),
        "graded": len(graded),
        "kinds": {
            name: sum(kind(row) == name for row in graded)
            for name in ("answered", "declined", "empty")
        },
        "coverage": among(graded, lambda row: kind(row) == "answered"),
        "good_among_answered": among(answered, lambda row: row["grade"] == "good"),
        "good_or_partial_among_answered": among(
            answered, lambda row: row["grade"] in ("good", "partial_ok")
        ),
        "unsupported_among_answered": among(
            answered, lambda row: row["claims_supported"] < row["claims_total"]
        ),
        "crag": {
            "mean": round(summary["point"], 4),
            "cluster95": [round(v, 4) for v in summary["ci95"]],
            "clusters": summary["clusters"],
            "levels": levels,
        },
        "by_context": matrix(
            [row for row in graded if kind(row) != "empty"], lambda row: row["context_has_answer"]
        ),
    }
    if key in EXTERNAL:
        if gold is None or set(gold) != {row["case_id"] for row in rows}:
            raise SystemExit(f"{key}: the gold does not hold the same questions")
        out["by_reference"] = matrix(graded, lambda row: gold[row["case_id"]])
    return out


def build():
    record = {"spec": SPEC, "tool_sha256": sha256(Path(__file__)), "stands": STANDS}
    paths = [path for table in (INPUTS, GOLD) for s in table.values() for path in s.values()]
    record["inputs"] = {path: sha256(WS / path) for path in paths}
    record["keys"] = {}
    for key, sides in INPUTS.items():
        record["keys"][key] = {}
        for name, path in sides.items():
            gold = None
            if key in GOLD:
                gold = {r["case_id"]: r["has_reference"] for r in load_jsonl(WS / GOLD[key][name])}
            record["keys"][key][name] = side(key, load_jsonl(WS / path), gold)
    return record


def main(argv):
    out = Path(argv[1]) if len(argv) > 1 else WS / "reports/coverage/coverage-record.json"
    text = json.dumps(build(), ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    out.write_bytes(text.encode("utf-8"))
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv)

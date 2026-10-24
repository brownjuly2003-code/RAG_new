"""Stage 2's combined record, part 5: the four corpora's numbers from the committed records.

docs/specs/stage2-four-corpora.md, «How the numbers are read» and «The judge» (part 5's
reading, settled 2026-10-23). Reads committed records only:

  reports/stage2/5e308fe/                    p1-aircargo-judge, p2-aircargo-context-judge,
                                             p4-<base>-judge-m1, p4-<base>-judge-m2
  reports/stage2/retrieval-20261021/         p1-aircargo, p2-aircargo
  reports/stage2/external-answers-20261023/  p4-<base>, p2-<base>

  python reports/stage2/tools/stage2_record.py [OUT]

writes OUT, by default reports/stage2/5e308fe/stage2-record.json: each input's SHA-256, and
per corpus
  - M1: the judge's classes, the plan's status and retest; the supported marks and claims,
    each a share of marks or claims whose cluster is the answer (aircargo) or the question's
    cluster (an external base); the marks naming no listed document; the defects;
    answer_without_context; on a base of two strata, the classes by stratum;
  - M2: aircargo's keywords; an external base's reference and declines as its m2 record
    holds them, and the reference's sway - the m1 and m2 plans' classes on the same answers;
  - M3: aircargo's context judge by run and against part 1's context_has_answer; an external
    base's gold coverage at each point of the path;
  - M4 the routes, M5 the times, the prompt parity and the path breaks;
and aircargo against each external base per class of M1: the difference with Newcombe's
hybrid score interval on each share's read interval, «detected» when it excludes zero.
Shares carry judge_export.share's n, Wilson interval and, on an external base, clusters and
cluster-bootstrap interval; `read95` is the wider of the two, the interval the spec reads.
"""

import json
import math
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(WS))
from judge_export import share, shares  # noqa: E402
from stage2_common import load_jsonl, sha256, spread  # noqa: E402

CODE = "5e308fe48cca0955c3007057a574a425f71e2a6a"
JUDGE = WS / "reports/stage2/5e308fe"
RETRIEVAL = WS / "reports/stage2/retrieval-20261021"
EXTERNAL = WS / "reports/stage2/external-answers-20261023"
OUT = JUDGE / "stage2-record.json"
BASES = ("conditionalqa", "wixqa", "multihoprag")
CLASSES = ("good", "partial_ok", "bad")
LEVELS = ("full", "partial", "none")
POINTS = ("vector", "bm25", "pool", "ranked", "expanded", "sent")
# Primary, then the mean beside it (the spec, «What each number is», M3).
COVERAGE = {
    "conditionalqa": ("all_evidence_coverage", "evidence_recall"),
    "wixqa": ("gold_article", "gold_articles"),
    "multihoprag": ("all_evidence_coverage", "evidence_recall"),
}
TIMES = ("total_sec", "first_token_sec", "retrieval_sec", "rerank_sec")
RETEST = ("planned", "pairs", "agree", "two_steps_apart", "quadratic_kappa", "ci95", "passed")


def read95(entry):
    """The wider of the Wilson and the cluster-bootstrap interval: the one the spec reads."""
    spans = [span for span in (entry.get("wilson95"), entry.get("cluster95")) if span]
    return max(spans, key=lambda span: span[1] - span[0]) if spans else None


def with_read(entry):
    return {**entry, "read95": read95(entry)}


def read_all(entries):
    return {name: with_read(entry) for name, entry in entries.items()}


def ratio(parts, families):
    """parts: case -> (hits, total). A share of the units, each in its case's cluster."""
    values, units = {}, {}
    for case, (hits, total) in parts.items():
        if not 0 <= hits <= total:
            raise SystemExit(f"{case}: {hits} of {total}")
        for index in range(total):
            key = f"{case}#{index}"
            values[key] = int(index < hits)
            units[key] = families[case] if families else [f"answer:{case}"]
    return {**with_read(share(values, units)), "answers": len(parts)}


def m1(record, rows, families):
    """M1 of one answers plan: its classes and their stability, then M1's other parts."""
    judged = [row for row in rows if "defect" in row]
    grades = {row["case_id"]: row["grade"] for row in rows}
    out = {
        "plan": record["plan"],
        "status": record["status"],
        "questions": record["questions"],
        "graded": sum(grade is not None for grade in grades.values()),
        "missing": record["missing"],
        "classes": read_all(shares(grades, CLASSES, families)),
        "retest": {key: record["retest"][key] for key in RETEST},
        "marks_supported": ratio(
            {
                row["case_id"]: (row["citations_supported"], row["marks_listed"])
                for row in judged
                if row["marks_listed"]
            },
            families,
        ),
        "claims_supported": ratio(
            {
                row["case_id"]: (row["claims_supported"], row["claims_total"])
                for row in judged
                if row["claims_total"]
            },
            families,
        ),
        "marks_unlisted": {
            "marks": sum(row["marks_unlisted"] for row in rows),
            "answers": sum(row["marks_unlisted"] > 0 for row in rows),
        },
        "with_defect": with_read(
            share({row["case_id"]: int(row["defect"] != "none") for row in judged}, families)
        ),
        "defects": dict(sorted(Counter(row["defect"] for row in judged).items())),
        "answer_without_context": sum(
            row["answers_question"] in ("full", "partial") and not row["context_has_answer"]
            for row in judged
        ),
        "empty_answers": sum(bool(row.get("empty_answer")) for row in rows),
    }
    strata = sorted({row["stratum"] for row in rows if "stratum" in row})
    if len(strata) > 1:
        out["by_stratum"] = {
            stratum: read_all(
                shares(
                    {row["case_id"]: row["grade"] for row in rows if row["stratum"] == stratum},
                    CLASSES,
                    families,
                )
            )
            for stratum in strata
        }
    return out


def sway(m1_rows, m2_rows):
    """The m1 plan's class against the m2 plan's on the answers both graded: printed only."""
    from scripts.chat_answer_judge import quadratic_kappa

    level = {name: index for index, name in enumerate(reversed(CLASSES))}
    second = {row["case_id"]: row for row in m2_rows}
    if set(second) != {row["case_id"] for row in m1_rows}:
        raise SystemExit("the m1 and m2 plans hold other questions")
    table = {name: dict.fromkeys(CLASSES, 0) for name in CLASSES}
    pairs = []
    for row in m1_rows:
        other = second[row["case_id"]]
        if row.get("empty_answer") or row["grade"] is None or other["grade"] is None:
            continue
        table[row["grade"]][other["grade"]] += 1
        pairs.append((level[row["grade"]], level[other["grade"]]))
    kappa = quadratic_kappa(pairs, len(CLASSES))
    return {
        "answers": len(pairs),
        "m1_by_m2": table,
        "agree": sum(a == b for a, b in pairs),
        "two_steps_apart": sum(abs(a - b) >= 2 for a, b in pairs),
        "quadratic_kappa": None if kappa is None else round(kappa, 4),
    }


def routes(rows, families, strata=None):
    """M4: the route of each answer and the share sent to a person."""
    out = {
        "routes": dict(sorted(Counter(row["route"] for row in rows).items())),
        "human": with_read(
            share({row["case_id"]: int(row["route"] == "human") for row in rows}, families)
        ),
        "self_score_below_80": sum(
            row["quality_score"] is not None and row["quality_score"] < 80 for row in rows
        ),
    }
    if strata:
        out["human_by_stratum"] = {
            stratum: {
                "questions": sum(strata[row["case_id"]] == stratum for row in rows),
                "human": sum(
                    strata[row["case_id"]] == stratum and row["route"] == "human" for row in rows
                ),
            }
            for stratum in sorted(set(strata.values()))
        }
    return out


def times(rows):
    """M5 as the answers' records hold it: all answers, a batch's first, the rest."""
    groups = {
        "all": rows,
        "first_of_batch": [row for row in rows if row["index"] == 1],
        "rest": [row for row in rows if row["index"] > 1],
    }
    return {
        name: {key: spread([row.get(key) for row in group]) for key in TIMES}
        for name, group in groups.items()
    }


def collection(answers, answer_rows, retrieval_rows):
    """Parity and the path: every counted question once, none with a path break."""
    if answers["aggregate"]["path_breaks"] or any(row["path_breaks"] for row in answer_rows):
        raise SystemExit(f"{answers['key']}: a counted answer has a path break")
    if any(row["path_breaks"] for row in retrieval_rows):
        raise SystemExit(f"{answers['key']}: a counted retrieval has a path break")
    if answers["provenance"]["code_sha"] != [CODE]:
        raise SystemExit(f"{answers['key']}: not the stand {CODE}")
    same = Counter(bool(row.get("answer_prompt_same")) for row in retrieval_rows)
    return {
        "answers": len(answer_rows),
        "path_breaks": 0,
        "parity": {"same": same[True], "of": len(retrieval_rows)},
    }


def coverage(rows, metrics, families):
    """M3 of an external base: the gold's coverage at each point, the questions with gold."""
    from evaluation.semantic_ruler import cluster_summary

    primary, mean = metrics
    gold = [row for row in rows if row["gold"]]
    out = {
        "with_gold": len(gold),
        "without_gold": len(rows) - len(gold),
        "gold_in_index": sum(bool(row["gold_in_index"]) for row in gold),
        "unresolved": sum(row["unresolved"] is not None for row in gold),
        "points": {},
    }
    for point in POINTS:
        read = [row for row in gold if point in row["points"]]
        hits = {row["case_id"]: row["points"][point][primary] for row in read}
        if any(value not in (0, 1) for value in hits.values()):
            raise SystemExit(f"{primary} at {point} is not a yes or no")
        values = {row["case_id"]: row["points"][point][mean] for row in read}
        summary = cluster_summary(values, {case: families[case] for case in values})
        out["points"][point] = {
            primary: with_read(share({case: int(v) for case, v in hits.items()}, families)),
            mean: {
                "n": summary["n"],
                "mean": round(summary["point"], 4),
                "clusters": summary["clusters"],
                "cluster95": [round(value, 4) for value in summary["ci95"]],
            },
        }
    return out


def newcombe(a, b):
    """a's share minus b's with Newcombe's hybrid score interval on their read intervals."""
    (pa, (la, ua)), (pb, (lb, ub)) = (a["share"], a["read95"]), (b["share"], b["read95"])
    difference = pa - pb
    low = difference - math.sqrt((pa - la) ** 2 + (ub - pb) ** 2)
    high = difference + math.sqrt((ua - pa) ** 2 + (pb - lb) ** 2)
    return {
        "difference": round(difference, 4),
        "ci95": [round(low, 4), round(high, 4)],
        "detected": low > 0 or high < 0,
    }


def build():
    inputs = {}

    def load(folder, name):
        record_path, rows_path = folder / f"{name}.json", folder / f"{name}.cases.jsonl"
        for path in (record_path, rows_path):
            inputs[path.relative_to(WS).as_posix()] = sha256(path)
        return json.loads(record_path.read_text(encoding="utf-8")), load_jsonl(rows_path)

    judge, judge_rows = load(JUDGE, "p1-aircargo-judge")
    context, context_rows = load(JUDGE, "p2-aircargo-context-judge")
    answers, answer_rows = load(RETRIEVAL, "p1-aircargo")
    _, retrieval_rows = load(RETRIEVAL, "p2-aircargo")
    if sorted(row["case_id"] for row in judge_rows) != sorted(r["case_id"] for r in answer_rows):
        raise SystemExit("aircargo: the judge's questions are not the answers'")
    m3 = {"status": context["status"], "retest": {k: context["retest"][k] for k in RETEST}}
    for run in ("p2-aircargo", "p2-aircargo-gr"):
        mine = {row["case_id"]: row["grade"] for row in context_rows if row["run"] == run}
        held = {case: int(v in ("full", "partial")) for case, v in mine.items() if v is not None}
        m3[run.removeprefix("p2-")] = {
            "questions": len(mine),
            "levels": read_all(shares(mine, LEVELS, None)),
            "holds_the_answer": with_read(share(held, None)),
        }
    held = {
        row["case_id"]: row["grade"] in ("full", "partial")
        for row in context_rows
        if row["run"] == "p2-aircargo" and row["grade"] is not None
    }
    seen = {row["case_id"]: row["context_has_answer"] for row in judge_rows if "defect" in row}
    both = sorted(set(held) & set(seen))
    m3["against_part_1"] = {
        "questions": len(both),
        "agree": sum(held[case] == seen[case] for case in both),
        "context_judge_holds": sum(held[case] for case in both),
        "answer_judge_holds": sum(seen[case] for case in both),
    }
    corpora = {
        "aircargo": {
            **collection(answers, answer_rows, retrieval_rows),
            "m1": m1(judge, judge_rows, None),
            "m2_keywords": read_all(
                shares(
                    {row["case_id"]: row["keywords"] for row in answer_rows},
                    ("FULL", "PART", "MISS"),
                    None,
                )
            ),
            "m3": m3,
            "m4": routes(answer_rows, None),
            "m5": times(answer_rows),
        }
    }
    for base in BASES:
        first, first_rows = load(JUDGE, f"p4-{base}-judge-m1")
        second, second_rows = load(JUDGE, f"p4-{base}-judge-m2")
        answers, answer_rows = load(EXTERNAL, f"p4-{base}")
        _, retrieval_rows = load(EXTERNAL, f"p2-{base}")
        if first["provenance"]["references_withheld"] is not True or "m2" not in second:
            raise SystemExit(f"{base}: the m1 plan withholds the references, the m2 plan reads M2")
        families = {row["case_id"]: [f"cluster:{row['cluster']}"] for row in first_rows}
        if sorted(families) != sorted(row["case_id"] for row in answer_rows):
            raise SystemExit(f"{base}: the judge's questions are not the answers'")
        strata = {row["case_id"]: row["stratum"] for row in first_rows}
        m2 = {"plan": second["plan"], "status": second["status"]}
        m2.update({group: read_all(value) for group, value in second["m2"].items()})
        for group in ("conditional", "not_conditional"):
            if group in second:
                m2[group] = {
                    "questions": second[group]["questions"],
                    "m2": read_all(second[group]["m2"]),
                }
        corpora[base] = {
            **collection(answers, answer_rows, retrieval_rows),
            "m1": m1(first, first_rows, families),
            "m2": m2,
            "sway": {
                **sway(first_rows, second_rows),
                "status": "counted"
                if first["status"] == second["status"] == "counted"
                else "NOT_EVIDENCE",
            },
            "m3": coverage(retrieval_rows, COVERAGE[base], families),
            "m4": routes(answer_rows, families, strata),
            "m5": times(answer_rows),
        }
    against = {
        base: {
            name: {
                **newcombe(
                    corpora["aircargo"]["m1"]["classes"][name],
                    corpora[base]["m1"]["classes"][name],
                ),
                "status": "counted"
                if corpora["aircargo"]["m1"]["status"] == corpora[base]["m1"]["status"] == "counted"
                else "NOT_EVIDENCE",
            }
            for name in CLASSES
        }
        for base in BASES
    }
    return {
        "stand": CODE,
        "inputs": dict(sorted(inputs.items())),
        "corpora": corpora,
        "aircargo_against": against,
    }


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    out = Path(argv[0]) if argv else OUT
    out.write_bytes((json.dumps(build(), ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

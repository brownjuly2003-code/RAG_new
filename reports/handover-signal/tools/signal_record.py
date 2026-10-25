"""The handover signals on V4's 100 aircargo answers: the record of the handover plan's 1.4.

docs/specs/handover-signal.md, «Reading» (frozen 2026-10-17), «1.4» and S7's threshold rule
(f520cde); PLAN.md stage 3, steps 1-3. Reads committed records only:

  RECORD_DIR/plan.json      the signal plan, scripts/chat_signals.py plan (b7ad62a)
  RECORD_DIR/signals.jsonl  its rows, scripts/chat_signals.py run on deproject-mac
  JUDGE_CASES               the judge's class of each answer, stage 2b's export
                            (reports/answer-prompt-v4/4f48fed/v4-aircargo-judge.cases.jsonl)

  python reports/handover-signal/tools/signal_record.py RECORD_DIR [OUT]

Writes OUT, by default RECORD_DIR/record.json: the SHA-256 of each input; the run (its rows,
resumes, stops, node errors, seconds); the judge's classes and the target - every bad answer
and every decline; per signal, scripts.chat_signals.summarize's counts with S7 at the
threshold its rule chooses, the median seconds it adds and the reading; R2 and R3 counted on
the claim check's rows; the grader's outcomes; the plan's outcome A, B or C. The counts are
chat_signals.summarize's; the reading compares unrounded Wilson limits.
"""

import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
sys.path.insert(0, str(WS / "reports" / "stage2" / "tools"))
sys.path.insert(1, str(WS))
from stage2_common import load_jsonl, sha256  # noqa: E402

from scripts import chat_signals  # noqa: E402

JUDGE_CASES = WS / "reports/answer-prompt-v4/4f48fed/v4-aircargo-judge.cases.jsonl"
MIN_TARGETS = 15
CHEAP = ("S1", "S1p", "S5", "S7", "S8")
CHECKS = ("S2", "S3", "S4", "S6")
# The seconds each signal adds to an answer: none without a model call; the claim check's,
# the grader's, or both for the widget's first pass.
SECONDS = {"S2": "verify", "S3": "verify", "S4": "grade", "S6": "total"}
USAGE = "usage: signal_record.py RECORD_DIR [OUT]"


def wilson(hits, n, z=1.96):
    """Wilson's 95 % limits, unrounded: chat_signals.wilson's before its rounding."""
    if n == 0:
        return None
    share = hits / n
    denominator = 1 + z * z / n
    centre = (share + z * z / (2 * n)) / denominator
    half = z * math.sqrt(share * (1 - share) / n + z * z / (4 * n * n)) / denominator
    return [max(0.0, centre - half), min(1.0, centre + half)]


def judged(plan, rows):
    """(run, case) -> (class, declined) for each plan answer, its prompt the judge's."""
    by_case = {(row["run"], row["case_id"]): row for row in rows}
    out = {}
    for item in plan["items"]:
        row = by_case[(item["run"], item["case_id"])]
        if row["prompt_sha256"] != item["prompt_sha256"] or row["missing"]:
            raise SystemExit(f"{item['case_id']}: the judge graded another answer, or none")
        out[(item["run"], item["case_id"])] = (row["grade"], row["answers_question"] == "declined")
    if len(by_case) != len(out):
        raise SystemExit("the judge holds answers the plan does not")
    return out


def target(classes, key):
    return classes[key][0] == "bad" or classes[key][1]


def good(classes, key):
    return classes[key][0] == "good" and not classes[key][1]


def s7_threshold(plan, classes):
    """The spec's rule: the candidate over-marking at most 1 of 3 that catches the most."""
    scored = [
        (float(item["S7"]["top_score"]), (item["run"], item["case_id"]))
        for item in plan["items"]
        if item["S7"]["status"] == "ok"
    ]
    goods = sum(1 for _, key in scored if good(classes, key))
    best = None
    for threshold in sorted({score for score, _ in scored}):
        marked = [key for score, key in scored if score < threshold]
        caught = sum(1 for key in marked if target(classes, key))
        over = sum(1 for key in marked if good(classes, key))
        if 3 * over <= goods and (best is None or caught > best["caught"]):
            best = {"threshold": threshold, "caught": caught, "over_marked": over}
    chosen = best if best is not None and best["caught"] > 0 else None
    return {
        "candidates": len({score for score, _ in scored}),
        "scored": len(scored),
        "threshold": None if chosen is None else chosen["threshold"],
        "chosen_on_these_answers": True,
    }


def read(entry):
    """The frozen reading of one signal: worth wiring, useless or in between."""
    caught, n = entry["caught"], entry["target"]
    if n == 0:
        return "no reading"
    over, goods = entry["over_marked"], entry["good_not_declining"]
    low, high = wilson(caught, n)
    if 3 * caught >= 2 * n and 3 * low >= 1 and 3 * over <= goods:
        return "worth wiring"
    if 2 * high < 1 or 2 * over > goods:
        return "useless"
    return "in between"


def added_seconds(name, answers):
    if name not in SECONDS:
        return 0.0
    return statistics.median(row["seconds"][SECONDS[name]] for row in answers)


def run_summary(rows):
    answers = [row for row in rows if row["kind"] == "answer"]
    totals = [row["seconds"]["total"] for row in answers]
    return {
        "rows": dict(Counter(row["kind"] for row in rows)),
        "code_sha": sorted({row["code_sha"] for row in rows if row["kind"] == "start"}),
        "served": sorted({row["served"] for row in rows if row["kind"] == "start"}),
        "rag_env": sorted({str(row["rag_env"]) for row in rows if row["kind"] == "start"}),
        "min_relevance": sorted({row["min_relevance"] for row in rows if row["kind"] == "start"}),
        "first": rows[0]["at"],
        "last": rows[-1]["at"],
        "answers": len(answers),
        "stops": [row for row in rows if row["kind"] == "stop"],
        "node_errors": sum(1 for row in answers if row["node_errors"]),
        "seconds_total": {
            "first_five_median": statistics.median(totals[:5]),
            "median": statistics.median(totals),
            "min": min(totals),
            "max": max(totals),
            "sum_hours": round(sum(totals) / 3600, 2),
        },
        "seconds_grade_median": statistics.median(row["seconds"]["grade"] for row in answers),
        "seconds_verify_median": statistics.median(row["seconds"]["verify"] for row in answers),
    }


def findings(answers):
    """R2 and R3 on the claim check's rows; the grader's outcomes."""
    no_claims = [row for row in answers if not row["S3"]["claims"]]
    vacuous = [
        row
        for row in no_claims
        if row["S2"]["grounding_status"] == "verified" and row["S2"]["factuality"] == 0
    ]
    claims = [claim for row in answers for claim in row["S3"]["claims"]]
    for_citation = [
        row
        for row in answers
        if row["S2"]["marked"]
        and row["S3"]["claims"]
        and all(claim["supported"] for claim in row["S3"]["claims"])
        and not all(claim["cited"] for claim in row["S3"]["claims"])
    ]
    return {
        "R2": {
            "no_claims": len(no_claims),
            "verified_with_factuality_0": len(vacuous),
            "made_a_gap": sum(1 for row in vacuous if row["S6"]["knowledge_gap"]),
            "routed_not_auto": sum(1 for row in vacuous if row["S6"]["marked"]),
        },
        "R3": {
            "claims": len(claims),
            "supported": sum(1 for claim in claims if claim["supported"]),
            "cited": sum(1 for claim in claims if claim["cited"]),
            "answers_marked_for_want_of_a_citation": len(for_citation),
        },
        "S2_status": dict(Counter(str(row["S2"]["grounding_status"]) for row in answers)),
        "S4_outcome": dict(Counter(str(row["S4"]["outcome"]) for row in answers)),
        "S4_relevance_none": sum(1 for row in answers if row["S4"]["relevance"] is None),
        "S4_kept_none": sum(1 for row in answers if row["S4"]["kept"] == 0),
        "S6_route": dict(Counter(str(row["S6"]["route"]) for row in answers)),
    }


def outcome(signals, targets):
    """The plan's outcome: A a cheap signal, B only a check of minutes, C none."""
    if targets < MIN_TARGETS:
        return {
            "outcome": "no reading",
            "worth_wiring": [],
            "candidates_for_stage_2": [],
            "in_between": [],
        }
    worth = [name for name, entry in signals.items() if entry["reading"] == "worth wiring"]
    between = [name for name, entry in signals.items() if entry["reading"] == "in between"]
    # A threshold chosen on these answers is a candidate, never a wired signal (the plan).
    candidates = [name for name in worth if signals[name].get("chosen_on_these_answers")]
    wired = [name for name in worth if name not in candidates]
    if any(name in CHEAP for name in wired):
        letter = "A"
    elif wired:
        letter = "B"
    else:
        letter = "C"
    return {
        "outcome": letter,
        "worth_wiring": wired,
        "candidates_for_stage_2": candidates + between,
        "in_between": between,
    }


def build(record_dir, *, judge_cases=JUDGE_CASES):
    record_dir = Path(record_dir)
    plan_path, rows_path = record_dir / "plan.json", record_dir / "signals.jsonl"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    rows = load_jsonl(rows_path)
    classes = judged(plan, load_jsonl(judge_cases))
    answers = [row for row in rows if row["kind"] == "answer"]
    if sorted(row["item"] for row in answers) != [item["item"] for item in plan["items"]]:
        raise SystemExit("the run did not give every planned answer exactly once")
    s7 = s7_threshold(plan, classes)
    summary = chat_signals.summarize(plan, rows, judged=classes, s7_threshold=s7["threshold"])
    signals = {}
    for name in chat_signals.SIGNALS:
        entry = dict(summary["signals"][name])
        if entry["computed"] == 0:
            entry["reading"] = "no threshold"
        else:
            entry["reading"] = read(entry)
        entry["added_seconds_median"] = added_seconds(name, answers)
        if name == "S7":
            entry.update(s7)
        signals[name] = entry
    targets = sum(1 for key in classes if target(classes, key))
    return {
        "what": (
            "the handover signals on V4's 100 aircargo answers "
            "(docs/specs/handover-signal.md 1.4; PLAN.md stage 3)"
        ),
        "inputs": {
            str(path.relative_to(WS)).replace("\\", "/"): sha256(path)
            for path in (plan_path, rows_path, Path(judge_cases))
        },
        "plan": {
            "code_sha": plan["code_sha"],
            "model": plan["model"],
            "answers_code_sha": sorted({run["code_sha"] for run in plan["runs"].values()}),
            "runs": len(plan["runs"]),
            "items": len(plan["items"]),
            "forecast_sec": plan["forecast_sec"],
        },
        "run": run_summary(rows),
        "judged": {
            "classes": dict(sorted(Counter(grade for grade, _ in classes.values()).items())),
            "declined": sum(1 for _, declined in classes.values() if declined),
            "target": targets,
            "good_not_declining": sum(1 for key in classes if good(classes, key)),
            "min_target": MIN_TARGETS,
        },
        "signals": signals,
        "s7_status": summary["s7_status"],
        "heuristic_scores": summary["heuristic_scores"],
        "findings": findings(answers),
        "outcome": outcome(signals, targets),
    }


def write(out, record):
    Path(out).write_bytes((json.dumps(record, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) not in (1, 2):
        raise SystemExit(USAGE)
    record_dir = Path(argv[0])
    out = Path(argv[1]) if len(argv) == 2 else record_dir / "record.json"
    record = build(record_dir)
    write(out, record)
    print(out)
    print(json.dumps(record["outcome"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

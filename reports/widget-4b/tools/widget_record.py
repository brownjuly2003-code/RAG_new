"""Stage 3, step 4 (docs/specs/widget-4b.md): the widget's rows and its record.

  python reports/widget-4b/tools/widget_record.py rows RUNS OUT   (the Mac: the run folders)
  python reports/widget-4b/tools/widget_record.py record OUT      (anywhere: the rows)

`rows` reads each run's launch.json, cases/, traces.db, api.log, stages.jsonl and
resources.jsonl and writes OUT/rows.jsonl: a start row a run and an answer row a request —
ids, labels, counts and seconds, never a text of a question, a document or an answer.
`record` reads the rows and the committed plan and judge records and writes OUT/record.json by
the spec's frozen reading.
"""

from __future__ import annotations

import json
import re
import sqlite3
import statistics
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
sys.path.insert(0, str(WS / "reports" / "stage2" / "tools"))
from stage2_common import load_jsonl, sha256  # noqa: E402

SPEC = "docs/specs/widget-4b.md"
STAND = "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
PLAN = WS / "reports/handover-signal/d260d95/plan.json"
JUDGE = WS / "reports/answer-prompt-v4/4f48fed/v4-aircargo-judge.cases.jsonl"
RUNS = {
    "widget-production": ("production", ["aircargo-matliab-disputed"]),
    "widget-development": (
        "development",
        [
            "aircargo-probation-data",
            "aircargo-probation-extend",
            "aircargo-probation-dismissal",
            "aircargo-dismissal-check",
            "aircargo-dismissal-lawyer",
            "aircargo-dismissal-order",
            "aircargo-leave-sources",
            "aircargo-leave-compensation",
            "aircargo-leave-risk",
            "aircargo-matliab-check",
        ],
    ),
}
TOOLS = ("widget_supervisor.py", "widget_runner.py", "widget.sh", "widget_record.py", "live_api.py")
GRADER_DEFECTS = ("grader_error", "partial_grader_error")
NO_JUDGE = "no_independent_judge"
EVALUATE = re.compile(r"\[evaluate\] boundary=start .*independent=(\w+) require=(\w+)")


# ---- pure: the passes, the lines, the reading -------------------------------------------


def seconds_between(start: str, end: str) -> float:
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


def no_claim(verify: dict) -> bool:
    """The extractor said NONE: no claim, vacuously verified at factuality 0 (R2's shape)."""
    return (
        verify.get("claims") == []
        and verify.get("grounding_status") == "verified"
        and verify.get("factuality_score") == 0
        and not verify.get("fact_verification_skipped")
    )


def _pass(steps: list[dict]) -> dict:
    last = {}
    for step in steps:
        last[step["node"]] = step["state"]
    grade, verify = last.get("grade_docs"), last.get("verify_facts")
    evaluate, routed = last.get("evaluate"), last.get("route_or_retry")
    claims = (verify or {}).get("claims") or []
    return {
        "grade": None
        if grade is None
        else {
            "outcome": grade.get("doc_grade_outcome"),
            "kept": len(grade.get("graded_docs") or []),
            "documents": len(grade.get("context_docs") or []),
        },
        "verify": None
        if verify is None
        else {
            "claims": len(claims),
            "supported": sum(1 for claim in claims if claim.get("supported")),
            "no_claim": no_claim(verify),
            "factuality": verify.get("factuality_score"),
            "grounding": verify.get("grounding_status"),
            "skipped": bool(verify.get("fact_verification_skipped")),
        },
        "evaluate": None
        if evaluate is None
        else {
            "status": evaluate.get("judge_status"),
            "reason": evaluate.get("judge_reason"),
            "quality": evaluate.get("quality_score"),
            "source": evaluate.get("quality_source"),
        },
        "route": None if routed is None else routed.get("route"),
        "knowledge_gap": None if routed is None else routed.get("knowledge_gap"),
    }


def passes(steps: list[dict]) -> list[dict]:
    """The trace cut after each route_or_retry; a tail with no route is a pass if it graded,
    verified or evaluated."""
    out, current = [], []
    for step in steps:
        current.append(step)
        if step["node"] == "route_or_retry":
            out.append(_pass(current))
            current = []
    if any(step["node"] in ("grade_docs", "verify_facts", "evaluate") for step in current):
        out.append(_pass(current))
    return out


def node_seconds(started: str, steps: list[dict]) -> dict[str, float]:
    """Seconds from the previous logged step (the first from the trace's start), per node."""
    out: dict[str, float] = {}
    previous = started
    for step in steps:
        out[step["node"]] = round(
            out.get(step["node"], 0.0) + seconds_between(previous, step["ts"]), 3
        )
        previous = step["ts"]
    return out


def evaluate_lines(lines: list[str]) -> list[dict]:
    out = []
    for line in lines:
        try:
            message = json.loads(line).get("msg", "")
        except (json.JSONDecodeError, AttributeError):
            message = line
        found = EVALUATE.search(str(message))
        if found:
            out.append({"independent": found[1] == "True", "require": found[2] == "True"})
    return out


def model_calls(stages: list[dict], start: float, seconds: float) -> dict:
    ends = [
        row
        for row in stages
        if row.get("stage", "").startswith("ollama.generate")
        and row.get("event") == "end"
        and start <= row.get("monotonic", -1) <= start + seconds
    ]
    return {"calls": len(ends), "seconds": round(sum(row.get("wall_sec", 0) for row in ends), 3)}


def judge_class(row: dict) -> str | None:
    if row["grade"] == "bad" or row.get("answers_question") == "declined":
        return "target"
    if row["grade"] == "good":
        return "good"
    return None


def r1(production: list[dict], development: list[dict], lines: dict[str, list[dict]]) -> dict:
    """R1 by the spec: the production request fails closed on no independent judge."""
    evaluated = [p["evaluate"] for row in production for p in row["passes"] if p["evaluate"]]
    seen = {
        "production_route": production[0]["route"] if production else None,
        "production_evaluations": evaluated,
        "production_lines": lines.get("production", []),
        "development_no_judge": sum(
            1
            for row in development
            for p in row["passes"]
            if p["evaluate"] and p["evaluate"]["reason"] == NO_JUDGE
        ),
    }
    if any(item["status"] == "ok" for item in evaluated):
        reading = "refuted"
    elif (
        evaluated
        and all(
            item["status"] == "unavailable" and item["reason"] == NO_JUDGE for item in evaluated
        )
        and seen["production_lines"]
        and all(line["require"] for line in seen["production_lines"])
        and seen["production_route"] == "human"
        and seen["development_no_judge"] == 0
    ):
        reading = "confirmed"
    else:
        reading = "not settled"
    return {"reading": reading, "seen": seen}


def r2(development: list[dict]) -> dict:
    hits = [
        row["case_id"]
        for row in development
        if row["route"] == "human"
        and row["passes"]
        and row["passes"][-1]["knowledge_gap"]
        and any(p["verify"] and p["verify"]["no_claim"] for p in row["passes"])
    ]
    return {"reading": "seen" if hits else "not seen on these ten", "cases": hits}


def grader(rows: list[dict]) -> dict:
    graded = [p["grade"] for row in rows for p in row["passes"] if p["grade"]]
    outcomes: dict[str, int] = {}
    for grade in graded:
        outcomes[str(grade["outcome"])] = outcomes.get(str(grade["outcome"]), 0) + 1
    return {
        "passes": len(graded),
        "defects": sum(1 for grade in graded if grade["outcome"] in GRADER_DEFECTS),
        "outcomes": dict(sorted(outcomes.items())),
    }


def ten(development: list[dict], classes: dict[str, dict]) -> dict:
    routes: dict[str, int] = {}
    for row in development:
        routes[str(row["route"])] = routes.get(str(row["route"]), 0) + 1
    seconds = [row["seconds"] for row in development]
    return {
        "reached": len(development),
        "routes": dict(sorted(routes.items())),
        "tickets": sum(1 for row in development if row["ticket"]),
        "retries": sum(1 for row in development for p in row["passes"] if p["route"] == "retry"),
        "seconds": {
            "median": round(statistics.median(seconds), 1) if seconds else None,
            "max": round(max(seconds), 1) if seconds else None,
        },
        "questions": [
            {
                "case_id": row["case_id"],
                "route": row["route"],
                "ticket": row["ticket"],
                "seconds": row["seconds"],
                "passes": len(row["passes"]),
                "model_calls": row["model_calls"]["calls"],
                **classes.get(row["case_id"], {"chat_grade": None, "chat_class": None}),
            }
            for row in development
        ],
    }


def build(rows: list[dict], classes: dict[str, dict]) -> dict:
    starts = {row["run"]: row for row in rows if row["kind"] == "start"}
    answers = [row for row in rows if row["kind"] == "answer"]
    production = [row for row in answers if row["run"] == "widget-production"]
    development = [row for row in answers if row["run"] == "widget-development"]
    lines = {RUNS[run][0]: start["evaluate_lines"] for run, start in starts.items()}
    runs = {
        run: {
            "env": start["env"],
            "status": start["status"],
            "planned": len(start["planned"]),
            "reached": sum(1 for row in answers if row["run"] == run),
            "delivered": sum(1 for row in answers if row["run"] == run and row["delivered"]),
            "tickets_made": None
            if start["tickets_before"] is None or start["tickets_after"] is None
            else int(start["tickets_after"]) - int(start["tickets_before"]),
            "load": start["load"],
        }
        for run, start in starts.items()
    }
    return {
        "runs": runs,
        "r1": r1(production, development, lines),
        "r2": r2(development),
        "grader": grader(answers),
        "ten": ten(development, classes),
    }


# ---- the Mac: the run folders into rows ----------------------------------------------------


def _steps(db: Path, trace_id: str) -> tuple[str | None, list[dict]]:
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as con:
        started = con.execute(
            "SELECT started_at FROM traces WHERE trace_id = ?", (trace_id,)
        ).fetchone()
        found = con.execute(
            "SELECT node_name, ts, state_json FROM trace_steps WHERE trace_id = ? ORDER BY step_order",
            (trace_id,),
        ).fetchall()
    return (started[0] if started else None), [
        {"node": node, "ts": ts, "state": json.loads(state)} for node, ts, state in found
    ]


def _load(run: Path) -> dict:
    values = []
    for row in load_jsonl(run / "resources.jsonl"):
        if "loadavg" in row:
            values.append(float(row["loadavg"].strip("{} ").split()[0]))
    if not values:
        return {"median": None, "max": None}
    return {"median": round(statistics.median(values), 2), "max": round(max(values), 2)}


def run_rows(run: Path) -> list[dict]:
    env, planned = RUNS[run.name]
    launch = json.loads((run / "launch.json").read_text(encoding="utf-8"))
    api_log = (run / "api.log").read_text(encoding="utf-8", errors="replace").splitlines()
    stages = load_jsonl(run / "stages.jsonl")
    start = {
        "kind": "start",
        "run": run.name,
        "env": env,
        "rag_env": launch.get("rag_env"),
        "production_names_set": launch.get("production_names_set"),
        "code_sha": launch.get("code_sha"),
        "tools_sha256": launch.get("tools_sha256"),
        "model": launch.get("model"),
        "model_digest": launch.get("model_digest"),
        "status": launch.get("status"),
        "runner_exit": launch.get("runner_exit"),
        "error": launch.get("error"),
        "planned": launch.get("cases"),
        "tickets_before": launch.get("db_tickets_before"),
        "tickets_after": launch.get("db_tickets_after"),
        "ollama_load_sec": launch.get("ollama_load_sec"),
        "evaluate_lines": evaluate_lines(api_log),
        "load": _load(run),
    }
    if launch.get("cases") != planned:
        raise SystemExit(f"{run.name}: the cases are not the spec's")
    out = [start]
    for path in sorted((run / "cases").glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        reply = case.get("reply") or {}
        trace_id = reply.get("trace_id") or ""
        started, steps = _steps(run / "traces.db", trace_id) if trace_id else (None, [])
        out.append(
            {
                "kind": "answer",
                "run": run.name,
                "env": env,
                "case_id": case["case_id"],
                "http_status": case.get("http_status"),
                "client_error": bool(case.get("client_error")),
                "delivered": case.get("http_status") == 200
                and not case.get("client_error")
                and reply.get("route") not in (None, "timeout", "error"),
                "route": reply.get("route"),
                "ticket": bool(reply.get("ticket_id")),
                "delivery_state": reply.get("delivery_state"),
                "quality_score": reply.get("quality_score"),
                "cached": reply.get("cached"),
                "citations": len(reply.get("citations") or []),
                "sources": len(reply.get("sources") or []),
                "seconds": case.get("total_sec"),
                "trace_found": bool(steps),
                "passes": passes(steps),
                "nodes": node_seconds(started, steps) if started and steps else {},
                "model_calls": model_calls(stages, case["t0_monotonic"], case["total_sec"]),
            }
        )
    return out


def write_rows(runs: Path, out: Path) -> None:
    rows = []
    for name in RUNS:
        if (runs / name).is_dir():
            rows += run_rows(runs / name)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "rows.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"rows": len(rows), "out": str(out / "rows.jsonl")}))


def chat_classes() -> dict[str, dict]:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    run_of = {item["case_id"]: item["run"] for item in plan["items"]}
    judged = {(row["run"], row["case_id"]): row for row in load_jsonl(JUDGE)}
    out = {}
    for case_id, run in run_of.items():
        row = judged.get((run, case_id))
        if row is not None:
            out[case_id] = {"chat_grade": row["grade"], "chat_class": judge_class(row)}
    return out


def write_record(out: Path) -> None:
    rows = load_jsonl(out / "rows.jsonl")
    record = {
        "spec": SPEC,
        "stand": STAND,
        "model": MODEL,
        "rows_sha256": sha256(out / "rows.jsonl"),
        "plan_sha256": sha256(PLAN),
        "judge_sha256": sha256(JUDGE),
        **build(rows, chat_classes()),
    }
    (out / "record.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps({key: record[key] for key in ("r1", "r2", "grader")}, ensure_ascii=False)[:2000]
    )


def main(argv: list[str]) -> int:
    if argv[:1] == ["rows"] and len(argv) == 3:
        write_rows(Path(argv[1]), Path(argv[2]))
    elif argv[:1] == ["record"] and len(argv) == 2:
        write_record(Path(argv[1]))
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

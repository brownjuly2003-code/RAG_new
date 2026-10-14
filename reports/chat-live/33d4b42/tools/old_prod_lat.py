"""Latency summary of a traces.db (read-only): totals, retrieve, and model-call steps.

Usage (Mac): python3 - TRACES_DB < old_prod_lat.py
A step's time is the gap since the previous step (or the trace start), as in db_lat.py.
"""

import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime


def ts(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def span(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return {"n": len(values), "min": round(values[0], 1),
            "median": round(statistics.median(values), 1), "max": round(values[-1], 1)}


con = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
traces = con.execute("select trace_id, started_at, finished_at from traces").fetchall()
steps = defaultdict(list)
models = Counter()
for tid, node, model, prov, step_ts in con.execute(
    "select trace_id, node_name, model_name, provider_name, ts from trace_steps "
    "order by trace_id, step_order"
):
    steps[tid].append((node, ts(step_ts), model))
    if model:
        models[f"{prov}/{model}"] += 1
totals, by_node, model_steps = [], defaultdict(list), []
first = last = None
for tid, started, finished in traces:
    a, b = ts(started), ts(finished)
    if a and b:
        totals.append(b - a)
        first = min(first or started, started)
        last = max(last or started, started)
    prev = a
    for node, t, model in steps.get(tid, []):
        if t is not None and prev is not None:
            by_node[node].append(t - prev)
            if model:
                model_steps.append(t - prev)
        prev = t or prev
print({"traces": len(traces), "from": str(first)[:19], "to": str(last)[:19]})
print("total", span(totals))
print("model steps", span(model_steps))
for node in ("retrieve", "transform_query", "grade_docs", "generate", "evaluate"):
    print(node, span(by_node.get(node, [])))
print("models", dict(models))

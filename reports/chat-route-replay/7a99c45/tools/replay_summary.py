"""Summarize the chat-route replay against the judge's classes (laptop, read-only)."""

import json
import math
import sys
from collections import Counter
from pathlib import Path

REPO = Path("D:/RAG_new")
sys.path.insert(0, str(REPO / "scripts"))
from generator_answer_judge import classify  # noqa: E402

GENERATOR = "qwen3-4b-instruct"
replay = Path(sys.argv[1])
out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


plan = json.loads((REPO / "reports/generator-screen/86df582/judge-100/plan.json").read_text("utf-8"))
items = {i["item_id"]: i for i in plan["items"]}
classes = {}
for line in (REPO / "reports/generator-screen/86df582/judge-100/verdicts.jsonl").read_text(
    "utf-8"
).splitlines():
    row = json.loads(line)
    item = items.get(row["item_id"])
    if not item or "retest_of" in item or item["generator"] != GENERATOR:
        continue
    if row.get("status") != "valid":
        continue
    classes[item["case_id"]] = classify(row["verdict"])
assert len(classes) == 100, len(classes)

rows = [json.loads(x) for x in replay.read_text("utf-8").splitlines()]
cases = {r["case_id"]: r for r in rows if r["kind"] == "case"}
n = len(cases)
routes = Counter(r["route"] for r in cases.values())
human = routes.get("human", 0)
cross = Counter((classes[c], r["route"]) for c, r in cases.items())
by_class = Counter(classes[c] for c in cases)
scores = Counter(r["quality"] for r in cases.values() if r["quality_source"] == "llm")
summary = {
    "cases": n,
    "routes": dict(routes),
    "human_share": round(human / n, 4) if n else None,
    "human_wilson95": wilson(human, n) if n else None,
    "quality_source": dict(Counter(r["quality_source"] for r in cases.values())),
    "errors": sum(1 for r in cases.values() if r.get("error")),
    "judge_classes": dict(by_class),
    "class_by_route": {f"{k[0]}->{k[1]}": v for k, v in sorted(cross.items())},
    "bad_caught": cross.get(("bad", "human"), 0),
    "bad_passed_auto": cross.get(("bad", "auto"), 0),
    "good_sent_human": cross.get(("good", "human"), 0),
    "score_counts": dict(sorted(scores.items())),
    "elapsed_sec_median": sorted(r["elapsed_sec"] for r in cases.values())[n // 2] if n else None,
    "elapsed_sec_max": max(r["elapsed_sec"] for r in cases.values()) if n else None,
    "stopped": [r for r in rows if r["kind"] == "stop"],
}
text = json.dumps(summary, indent=2, ensure_ascii=False)
print(text)
if out_path:
    out_path.write_text(text + "\n", encoding="utf-8", newline="\n")

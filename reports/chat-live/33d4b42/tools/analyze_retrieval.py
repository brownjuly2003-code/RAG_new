"""Summarise one retrieval-only run (live_supervisor.py mode retrieval) into analysis.json.

Usage (Mac): analyze_retrieval.py LABEL
Per placement: model devices and load messages, and per question the walls of retrieval,
vector search and rerank and whether the reranker succeeded; plus memory and the load of
the machine (load average, the busiest processes that were not ours).
"""

import json
import re
import statistics
import sys
from pathlib import Path

RUNS = Path(__file__).resolve().parent / "runs"
OURS = ("live_", "RAG_Support_Assistant/.venv", "llama", "ollama", "postgres")


def load_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    run = RUNS / sys.argv[1]
    launch = json.loads((run / "launch.json").read_text(encoding="utf-8"))
    variants = {}
    for path in sorted(run.glob("retrieval-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        variants[data["variant"]] = data
    resources = load_jsonl(run / "resources.jsonl")
    swaps = [float(m.group(1)) for r in resources
             if (m := re.search(r"used = ([0-9.]+)M", r.get("swap") or ""))]
    free = [r["free_pages"] * 4096 / 2**20 for r in resources if r.get("free_pages")]
    loads = [float(r["loadavg"].strip("{} ").split()[0]) for r in resources if r.get("loadavg")]
    foreign = {}
    for r in resources:
        for pid, cpu, size, comm in r.get("busiest", []):
            if any(mark in comm for mark in OURS):
                continue
            name = comm.rsplit("/", 1)[-1]
            foreign[name] = max(foreign.get(name, 0.0), cpu)
    report = {"label": run.name, "mode": launch.get("mode"), "status": launch.get("status"),
              "error": launch.get("error"), "code_sha": launch.get("code_sha"),
              "variant_exits": launch.get("variants"),
              "ollama_models_before": launch.get("ollama_models_before"),
              "ollama_models_after": launch.get("ollama_models_after"),
              "variants": variants,
              "memory": {"samples": len(resources),
                         "swap_used_mb": [min(swaps), max(swaps)] if swaps else None,
                         "free_mb_min": round(min(free)) if free else None},
              "load": {"loadavg_1min_max": max(loads) if loads else None,
                       "loadavg_1min_median": statistics.median(loads) if loads else None,
                       "foreign_max_cpu": dict(sorted(foreign.items(), key=lambda kv: -kv[1])[:8])}}
    (run / "analysis.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
    for name, data in variants.items():
        print(name, data["placement"], "batch", data.get("rerank_batch_env"), "build",
              data["retriever_build_sec"], data.get("loads"))
        for q in data["questions"]:
            print("  ", q["case"], q["retrieval_sec"], "vector", q.get("vector"), "rerank",
                  q.get("rerank"), "ok", q.get("reranker_ok"),
                  (q.get("reranker_errors") or [""])[0][:200])
        real = [q for q in data["questions"] if not q["case"].startswith("warmup")]
        if real:
            print("   median of", len(real), "cases: retrieval",
                  statistics.median(q["retrieval_sec"] for q in real), "rerank",
                  statistics.median(q.get("rerank", 0) for q in real))
    print(json.dumps({k: report[k] for k in ("status", "variant_exits", "memory", "load")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()

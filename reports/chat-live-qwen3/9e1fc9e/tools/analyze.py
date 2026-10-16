"""Summarise one live chat run: per-question timeline, stage times, exact prompt tokens, memory.

Usage (Mac, model venv): analyze.py LABEL   -> prints a compact report, writes analysis.json
Prompt texts are counted, never printed.
"""

import json
import re
import sys
from pathlib import Path

RUNS = Path(__file__).resolve().parent / "runs"
TOKENIZER = (
    "/Users/julia/.cache/huggingface/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/"
    "a09a35458c702b33eeacc393d103063234e8bc28/tokenizer.json"
)


def load_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def swap_used_mb(text):
    match = re.search(r"used = ([0-9.]+)M", text or "")
    return float(match.group(1)) if match else None


def main():
    run = RUNS / sys.argv[1]
    launch = json.loads((run / "launch.json").read_text(encoding="utf-8"))
    settings = {}
    if (run / "effective_settings.json").exists():
        settings = json.loads((run / "effective_settings.json").read_text(encoding="utf-8"))
    from tokenizers import Tokenizer

    tok = Tokenizer.from_file(TOKENIZER)
    stages = load_jsonl(run / "stages.jsonl")
    for row in stages:
        name = row.get("prompt_file")
        if name and row.get("event") == "start":
            text = (run / "prompts" / name).read_text(encoding="utf-8")
            row["prompt_exact_tokens"] = len(tok.encode(text).ids)
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((run / "cases").glob("*.json"))]
    report = {"label": run.name, "mode": launch.get("mode"), "status": launch.get("status"),
              "error": launch.get("error"), "code_sha": launch.get("code_sha"),
              "ollama_load_sec": launch.get("ollama_load_sec"),
              "tickets": [launch.get("db_tickets_before"), launch.get("db_tickets_after")],
              "models_after": launch.get("ollama_models_after"),
              "unloaded": launch.get("unloaded_models"),
              "settings": settings.get("settings"), "code": settings.get("code"), "cases": []}
    for case in cases:
        t0 = case.get("t0_monotonic")
        t1 = t0 + case.get("total_sec", 0) + case.get("drain_sec", 0) + 1 if t0 else None
        timeline = []
        for row in stages:
            if t0 is None or not (t0 - 1 <= row["monotonic"] <= t1):
                continue
            if row["event"] != "end":
                continue
            item = {"stage": row["stage"], "end_at": round(row["monotonic"] - t0, 2),
                    "wall": round(row.get("wall_sec", 0), 2)}
            for key in ("first_chunk_sec", "chunks", "output_chars", "error", "detail",
                        "prompt_est_tokens", "max_tokens", "prompt_file", "reranker_ok",
                        "docs"):
                if row.get(key) is not None:
                    item[key] = round(row[key], 2) if isinstance(row[key], float) else row[key]
            start = next((s for s in stages if s.get("prompt_file") == row.get("prompt_file")
                          and s["event"] == "start" and row.get("prompt_file")), None)
            if start:
                item["prompt_exact_tokens"] = start["prompt_exact_tokens"]
            timeline.append(item)
        events = [{k: (v if not isinstance(v, str) else v[:160]) for k, v in e.items()
                   if k in ("at", "type", "route", "quality", "quality_source", "detail", "status")}
                  for e in case.get("events", [])]
        result = next((e for e in case.get("events", []) if e.get("type") == "result"), {})
        report["cases"].append({
            "case": case["case_id"], "question": case["question"],
            "http": case.get("http_status"), "first_token_sec": case.get("first_token_sec"),
            "last_token_sec": case.get("last_token_sec"), "tokens": case.get("tokens", 0),
            "answer_chars": len(case.get("answer", "")),
            "answer_tokens": len(tok.encode(case.get("answer", "")).ids),
            "result_sec": case.get("result_sec"), "error_sec": case.get("error_sec"),
            "total_sec": case.get("total_sec"), "drain_sec": case.get("drain_sec"),
            "client_error": case.get("client_error"), "route": result.get("route"),
            "quality": result.get("quality"), "sources": len(result.get("sources") or []),
            "suggested": len(result.get("suggested_questions") or []),
            "events": events, "timeline": timeline})
    resources = load_jsonl(run / "resources.jsonl")
    swaps = [swap_used_mb(r.get("swap")) for r in resources if r.get("swap")]
    free = [r["free_pages"] * 4096 / 2**20 for r in resources if r.get("free_pages")]
    rss = {}
    for r in resources:
        for pid, cpu, size, comm in r.get("procs", []):
            key = "ollama" if "ollama" in comm else ("postgres" if "postgres" in comm else "python")
            rss[key] = max(rss.get(key, 0), size)
    report["memory"] = {"samples": len(resources),
                        "swap_used_mb": [min(swaps), max(swaps)] if swaps else None,
                        "free_mb_min": round(min(free)) if free else None,
                        "max_rss_mb": {k: round(v / 2**20) for k, v in rss.items()}}
    (run / "analysis.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()

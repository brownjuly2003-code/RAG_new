"""One publishable record of live chat runs: timings, prompt sizes, settings, provenance.

Usage (Mac, model venv, clean environment, CHAT_RUN_DIR set to any scratch directory,
after analyze.py of every label): export.py OUT_JSON LABEL...
Each run names the model it served (MODEL of live_supervisor.py) and its digest.
Prompt texts are not exported; answers are, as the client received them. Settings come
as the run's public subset plus every field that differs from a clean Settings() of the
same code (secret-like fields only as <set>/<empty>, see live_api.settings_snapshot).
"""

import hashlib
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parent
RUNTIME = (WS / ".ask100-runtime").resolve()
sys.path.insert(0, str(HERE))
from live_api import settings_snapshot  # noqa: E402

from config.settings import Settings  # noqa: E402

PY = "/Users/julia/RAG_Support_Assistant/.venv/bin/python"
DATASET = "evaluation/curated_cases_aircargo.jsonl"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
CASE_FIELDS = ("case", "question", "http", "first_token_sec", "last_token_sec", "tokens",
               "answer_tokens", "result_sec", "error_sec", "total_sec", "drain_sec",
               "client_error", "route", "quality", "quality_source", "sources", "suggested",
               "memory", "events")


def sh(*args):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, check=True,
                          timeout=120).stdout.strip()


def ollama(path):
    with urllib.request.urlopen("http://127.0.0.1:11434" + path, timeout=10) as response:
        return json.load(response)


def relative(value):
    if not isinstance(value, str):
        return value
    return value.replace(str(RUNTIME), "<runtime>").replace(str(WS), "<workspace>")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def mask(text):
    text = re.sub(r"://[^/@\s]+@", "://<redacted>@", text)
    return re.sub(r"(?i)(passw\w*|secret\w*|token\w*|api[_-]?key\w*)=\S+", r"\1=<redacted>", text)


def warnings(path):
    """WARNING and worse lines of the API log, counted by message with numbers folded."""
    found = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        start = line.find('{"ts"')
        if start < 0:
            continue
        try:
            row = json.loads(line[start:])
        except ValueError:
            continue
        if row.get("level") not in ("WARNING", "ERROR", "CRITICAL"):
            continue
        message = mask(str(row.get("msg", "")))
        key = f'{row["level"]} {row.get("module")}: ' + re.sub(r"[0-9a-f]{8,}|\d+(\.\d+)?", "#",
                                                               message)[:160]
        entry = found.setdefault(key, {"count": 0, "first": message[:300]})
        entry["count"] += 1
    return found


def main():
    out_path, labels = Path(sys.argv[1]), sys.argv[2:]
    defaults = settings_snapshot(Settings())
    digests = {m["name"]: m["digest"] for m in ollama("/api/tags")["models"]}
    record = {
        "schema": "chat-live/v1",
        "code_sha": (WS / "CODE_SHA").read_text(encoding="utf-8").strip(),
        "dataset": {"path": DATASET,
                    "sha256": hashlib.sha256((WS / DATASET).read_bytes()).hexdigest()},
        "host": {"model": sh("/usr/sbin/sysctl", "-n", "hw.model"),
                 "cpu": sh("/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"),
                 "physical_cores": int(sh("/usr/sbin/sysctl", "-n", "hw.physicalcpu")),
                 "memory_bytes": int(sh("/usr/sbin/sysctl", "-n", "hw.memsize")),
                 "macos": sh("/usr/bin/sw_vers", "-productVersion")},
        "ollama": {"version": ollama("/api/version")["version"]},
        "runs": [],
    }
    chroma_dirs = set()
    record["retrieval_runs"] = []
    for label in labels:
        run = HERE / "runs" / label
        launch = load(run / "launch.json")
        analysis = load(run / "analysis.json")
        effective = load(run / "effective_settings.json")
        chroma_dirs.add(effective["settings"]["vectordb_chroma_dir"])
        off_default = {
            name: {"default": relative(defaults.get(name)),
                   "run": relative(effective["all"].get(name))}
            for name in sorted(set(defaults) | set(effective["all"]))
            if defaults.get(name) != effective["all"].get(name)
        }
        notes = load(run / "notes.json") if (run / "notes.json").exists() else []
        if launch["mode"] == "retrieval":
            record["retrieval_runs"].append({
                "label": label, "mode": "retrieval", "overrides": launch.get("overrides"),
                "started": launch["started"], "finished": launch.get("finished"),
                "status": launch["status"], "variant_order": launch.get("variant_order"),
                "variant_exits": launch.get("variants"),
                "ollama_models_before": launch.get("ollama_models_before"),
                "ollama_models_after": launch.get("ollama_models_after"),
                "settings": {k: relative(v) for k, v in effective["settings"].items()},
                "settings_off_default": off_default, "memory": analysis["memory"],
                "load": analysis["load"], "notes": notes,
                "variants": [{k: v for k, v in data.items() if k != "loads"}
                             | {"devices": {k: v for k, v in data.get("loads", {}).items()
                                            if k != "messages"},
                                "load_messages": data.get("loads", {}).get("messages", [])}
                             for data in analysis["variants"].values()],
            })
            continue
        answers = {}
        for path in sorted((run / "cases").glob("*.json")):
            case = load(path)
            answers[case["case_id"]] = case.get("answer", "")
        cases = []
        for case in analysis["cases"]:
            timeline = [{k: v for k, v in step.items() if k != "prompt_file"}
                        for step in case["timeline"]]
            cases.append({**{k: case.get(k) for k in CASE_FIELDS},
                          "answer": answers.get(case["case"], ""), "timeline": timeline})
        record["runs"].append({
            "label": label, "mode": launch["mode"], "overrides": launch.get("overrides"),
            "started": launch["started"], "finished": launch.get("finished"),
            "status": launch["status"], "runner_exit": launch.get("runner_exit"),
            "model": launch.get("model", MODEL),
            "model_digest": launch.get("model_digest") or digests[launch.get("model", MODEL)],
            "ollama_models_before": launch.get("ollama_models_before"),
            "ollama_models_after": launch.get("ollama_models_after"),
            "ollama_load_sec": launch.get("ollama_load_sec"),
            "settings": {k: relative(v) for k, v in effective["settings"].items()},
            "settings_off_default": off_default, "tickets": analysis["tickets"],
            "memory": analysis["memory"], "api_warnings": warnings(run / "api.log"),
            "notes": notes, "cases": cases,
        })
    assert len(chroma_dirs) == 1, chroma_dirs
    record["index"] = load_index(chroma_dirs.pop())
    out_path.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"written": str(out_path), "runs": labels, "index": record["index"],
                      "bytes": out_path.stat().st_size}))


def load_index(chroma_dir):
    return json.loads(sh(PY, HERE / "index_digest.py", chroma_dir))


if __name__ == "__main__":
    main()

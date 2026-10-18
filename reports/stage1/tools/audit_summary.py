"""Aggregate one stage-1 live audit into a committable record (counts and ids, no text).

Usage (on the Mac, in the stand's chatlive folder):
    python audit_summary.py PREFIX RUNS_DIR OUT.json DATA_ROOT

DATA_ROOT holds each external base's generation (``<base>/corpus.manifest.json``,
``<base>/index/index-receipt.json``); a run reads a copy of its index, which the API writes
into at startup, so the provenance is the source generation's manifest and receipt.

For each run ``RUNS_DIR/PREFIX-<tenant>``: the launch record (code, model, tenant, index,
cases), the hybrid path the trace recorded, the BM25 restore lines of the API log, the letters
of the question and the answer by script (the language check of finding 10), the prompt's
document labels and header form (findings 5 and 10), the self-score, route and timings. The
external bases' texts stay on the host (evaluation/external_bases.json, "redistribution"):
the record holds case ids, counts and the API's own log messages only.
"""

import glob
import hashlib
import json
import re
import sys
from pathlib import Path

PREFIX, RUNS, OUT, ROOT = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
TENANTS = ("aircargo", "conditionalqa", "wixqa", "multihoprag")


def letters(text):
    return {
        "cyrillic": len(re.findall("[а-яА-ЯёЁ]", text)),
        "latin": len(re.findall("[a-zA-Z]", text)),
    }


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


record = {"prefix": PREFIX, "runs": {}}
for tenant in TENANTS:
    run = RUNS / f"{PREFIX}-{tenant}"
    if not run.is_dir():
        continue
    launch = json.loads((run / "launch.json").read_text(encoding="utf-8"))
    cases = []
    for path in sorted(glob.glob(str(run / "cases" / "*.json"))):
        case = json.loads(Path(path).read_text(encoding="utf-8"))
        if str(case["case_id"]).startswith("warmup-"):
            continue
        result = next((e for e in case["events"] if e.get("type") == "result"), {})
        cases.append(
            {
                "case_id": case["case_id"],
                "question_letters": letters(case["question"]),
                "answer_letters": letters(str(result.get("answer") or "")),
                "quality_score": result.get("quality_score"),
                "quality_source": result.get("quality_source"),
                "route": result.get("route"),
                "first_token_sec": case.get("first_token_sec"),
                "result_sec": case.get("result_sec"),
                "tokens": case.get("tokens"),
            }
        )
    paths = []
    for line in (run / "stages.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if (
            row.get("stage") == "hybrid.get_relevant_documents_with_path"
            and row.get("event") == "end"
        ):
            path = row["path"]
            paths.append(path if isinstance(path, dict) else str(path))
    prompts = []
    for path in sorted(glob.glob(str(run / "prompts" / "*-stream.txt"))):
        text = Path(path).read_text(encoding="utf-8")
        prompts.append(
            {
                "file": Path(path).name,
                "sha256": sha256(path),
                "labels_dokument": len(re.findall(r"^\[Документ \d+", text, re.M)),
                "labels_source": len(re.findall(r"^\[\d+ \| source=", text, re.M)),
                "header_kontekst": text.count("[Контекст:"),
            }
        )
    restore = [
        json.loads(line)["msg"]
        for line in (run / "api.log").read_text(encoding="utf-8", errors="replace").splitlines()
        if line.startswith("{")
        and re.search(r"Restored \d+ chunks|Chunk restore failed|WITHOUT BM25", line)
        and "Tenant default" not in line
    ]
    base = ROOT / tenant
    source = {
        name: sha256(base / name)
        for name in ("corpus.manifest.json", "chunks-report.json", "index/index-receipt.json")
        if (base / name).is_file()
    }
    record["runs"][tenant] = {
        "launch": {
            key: launch.get(key)
            for key in (
                "label",
                "code_sha",
                "model",
                "model_digest",
                "tenant",
                "chroma_dir",
                "cases_file",
                "started",
                "finished",
                "status",
                "client_cap_sec",
            )
        },
        "data_root": str(ROOT),
        "source_sha256": source,
        "cases": cases,
        "paths": paths,
        "prompts": prompts,
        "bm25_restore_log": restore,
    }
OUT.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps({t: [c["case_id"] for c in r["cases"]] for t, r in record["runs"].items()}))

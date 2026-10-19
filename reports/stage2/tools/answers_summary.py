"""Summarise one stage-2 answers part into a committable record: numbers and ids, no text.

Usage (on the Mac, in the stand's chatlive folder):
    python answers_summary.py PART-KEY DATA_ROOT OUT_DIR
    e.g. answers_summary.py p1-aircargo /Users/julia/RAG_new_external_s1 /Users/julia/s2-out
    python answers_summary.py check LABEL
    - stage2.sh after each batch: the path test of run LABEL; exit 6 on a break or no case.

PLAN.md stage 2, items 1 and 4; docs/specs/stage2-four-corpora.md. stage2.sh runs a part as
batches of ten, each batch one live_supervisor.py run labelled PART-KEY-bNN, its rerun
PART-KEY-bNN-rK. A batch counts by the last of its runs that completed (status complete,
runner exit 0); a batch without one leaves its questions unmeasured. Every run is listed.

Writes OUT_DIR/PART-KEY.json - provenance (code, model, settings, the generation's files, the
questions file, the tools), the runs, the aggregates - and OUT_DIR/PART-KEY.cases.jsonl, one
counted question a line: the times, route and self-score, the letters of the question and the
answer by script, the answer's reference marks, the stream prompt's labels and SHA-256, the
retrieval's path, every fused candidate as [vector rank, BM25 rank, cross-encoder score], the
model calls with their times, the memory it ran in, and path_breaks - what stage 1's path test
finds wrong (HTTP status, no answer, an empty lane, the rerank's status, fewer than five
documents, the run's BM25 restore for its tenant); on aircargo also M2, the keywords of the
case (expected.answer_contains) in the answer by the repository's rule
(scripts/ab_remote_contextual._kw_status: FULL, PART or MISS). The texts stay on the host
(evaluation/external_bases.json, "redistribution"): stage2_common.without_text refuses the
record when a string of it is the name of a document of the base or holds a question.
"""

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(HERE.parent))
from stage2_cases import registered  # noqa: E402
from stage2_common import (  # noqa: E402
    BASES,
    RESTORE,
    SOURCE_FILES,
    load_jsonl,
    memory,
    number,
    path_breaks,
    pool_ranks,
    restore_breaks,
    sha256,
    source_names,
    spread,
    without_text,
    write,
)

from scripts.ab_remote_contextual import _kw_status  # noqa: E402

TOOLS = (
    "live_api.py",
    "live_runner.py",
    "live_supervisor.py",
    "stage2.sh",
    "stage2_cases.py",
    "stage2_common.py",
    "answers_summary.py",
)
LAUNCH = (
    "label",
    "code_sha",
    "model",
    "model_digest",
    "tenant",
    "chroma_dir",
    "cases_file",
    "started",
    "api_ready",
    "finished",
    "status",
    "client_cap_sec",
    "mode",
    "overrides",
    "runner_exit",
    "error",
    "api_killed",
    "ollama_load_sec",
    "db_tickets_before",
    "db_tickets_after",
    "ollama_models_before",
    "ollama_models_after",
    "unloaded_models",
    "pg_stop_error",
    "unload_error",
)
STAGES = (
    "vectordb.manager.get_retriever",
    "vectordb.manager.get_embeddings",
    "vectordb._base_manager.get_embeddings",
    "vectordb._base_manager.get_reranker",
    "hybrid.get_relevant_documents_with_path",
    "hybrid._vector_search",
    "hybrid._rerank_scored_with_status",
    "hybrid._expand_parents",
    "ollama.generate_stream",
    "ollama.generate",
)
MARK = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def letters(text):
    return {
        "cyrillic": len(re.findall("[а-яА-ЯёЁ]", text)),
        "latin": len(re.findall("[a-zA-Z]", text)),
    }


def script(counts):
    """The script most letters are in, or None for a text without letters."""
    if not counts["cyrillic"] and not counts["latin"]:
        return None
    return "cyrillic" if counts["cyrillic"] >= counts["latin"] else "latin"


def prompt_check(path):
    """What the answer prompt held, counted: the V3 labels, the header lines, the letters."""
    text = path.read_text(encoding="utf-8")
    return {
        "file": path.name,
        "sha256": sha256(path),
        "chars": len(text),
        "labels_source": len(re.findall(r"^\[\d+ \| source=", text, re.M)),
        "header_first_line": len(
            re.findall(r"^\[\d+ \| source=[^\n]*\n\[(?!Контекст:)[^\n]*\]$", text, re.M)
        ),
        "letters": letters(text),
    }


def marks(answer):
    """The answer's reference marks: how many, and the document numbers they name."""
    named = [int(n) for group in MARK.findall(answer) for n in group.split(",")]
    return {"marks": len(named), "named": sorted(set(named))}


def call(row):
    """A model call's numbers; an error by its type only (its message may quote a prompt)."""
    error = row.get("error")
    return {
        "wall_sec": number(row.get("wall_sec")),
        "first_chunk_sec": number(row.get("first_chunk_sec")),
        "chunks": row.get("chunks"),
        "output_chars": row.get("output_chars"),
        "prompt_chars": row.get("prompt_chars"),
        "prompt_est_tokens": row.get("prompt_est_tokens"),
        "max_tokens": row.get("max_tokens"),
        "error": str(error).split(":", 1)[0] if error else None,
    }


def case_rows(case, rows, run):
    """The stage rows of one question: its retrieval, its pool, its model calls."""
    t0 = case["t0_monotonic"]
    ends = [r for r in rows if r.get("event") == "end"]

    def of(stage):
        return [r for r in ends if r["stage"] == stage]

    timeline = [
        [
            r["stage"],
            round(r["monotonic"] - r.get("wall_sec", 0) - t0, 2),
            round(r["monotonic"] - t0, 2),
        ]
        for r in ends
        if r["stage"] in STAGES
    ]
    paths, lanes, pools = (
        of("hybrid.get_relevant_documents_with_path"),
        of("hybrid.lanes"),
        of("hybrid.rerank_pool"),
    )
    ranked, vector, expand = (
        of("hybrid._rerank_scored_with_status"),
        of("hybrid._vector_search"),
        of("hybrid._expand_parents"),
    )
    out = {"retrievals": len(paths), "timeline": timeline}
    if paths:
        out.update(
            retrieval_sec=number(paths[0]["wall_sec"]),
            path=paths[0].get("path"),
            docs=paths[0].get("docs"),
        )
    if vector:
        out["vector_sec"] = number(vector[0]["wall_sec"])
    if ranked:
        out.update(
            rerank_sec=number(ranked[0]["wall_sec"]),
            reranker_ok=ranked[0].get("reranker_ok"),
            ranked_scores=ranked[0].get("scores"),
        )
    if expand:
        out.update(expanded_docs=expand[0].get("docs"), expanded_chars=expand[0].get("chars"))
    if pools:
        out["fusion"] = bool(lanes)
        out["pool"] = pool_ranks(lanes[0] if lanes else None, pools[0]["pool"])
    streams = of("ollama.generate_stream")
    out["stream"] = [call(r) for r in streams]
    out["generate"] = [call(r) for r in of("ollama.generate")]
    out["prompts"] = [
        prompt_check(run / "prompts" / r["prompt_file"]) for r in streams if r.get("prompt_file")
    ]
    return out


def answered(case, result):
    """live_runner.py's own test: streamed tokens and a result that is not a timeout."""
    return (
        case.get("tokens", 0) > 0
        and "result_sec" in case
        and result.get("route") != "timeout"
        and "client_error" not in case
        and "error_sec" not in case
    )


def api_log(run):
    """The BM25 restore lines of the API's log and its warnings counted by logger."""
    path = run / "api.log"
    restore, levels = [], Counter()
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    for line in text.splitlines():
        # A progress bar written to the same stream can precede an entry on its line.
        start = line.find("{")
        if start < 0:
            continue
        try:
            entry = json.loads(line[start:])
        except ValueError:
            continue
        message = str(entry.get("msg", ""))
        level = entry.get("level") or entry.get("levelname")
        if level in ("WARNING", "ERROR", "CRITICAL"):
            name = entry.get("logger") or entry.get("name") or entry.get("module")
            levels[f"{level} {name}"] += 1
        if RESTORE.search(message) and "Tenant default" not in message:
            restore.append(message)
    return restore, dict(sorted(levels.items()))


def summarise_run(run, batch, counted, expected):
    launch = json.loads((run / "launch.json").read_text(encoding="utf-8"))
    settings_path = run / "effective_settings.json"
    settings = (
        json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    )
    stages = load_jsonl(run / "stages.jsonl")
    resources = load_jsonl(run / "resources.jsonl")
    restore, levels = api_log(run)
    run_breaks = restore_breaks(restore, launch.get("tenant") or "")
    cases = []
    for path in sorted((run / "cases").glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        result = next((e for e in case.get("events", []) if e.get("type") == "result"), {})
        answer = str(result.get("answer") or case.get("answer") or "")
        keywords = expected.get(case["case_id"])
        row = {
            "case_id": case["case_id"],
            "batch": batch,
            "run": run.name,
            "index": int(path.name.split("-", 1)[0]),
            "http_status": case.get("http_status"),
            "answered": answered(case, result),
            "question_letters": letters(case["question"]),
            "answer_letters": letters(answer),
            "answer_chars": len(answer),
            "tokens": case.get("tokens", 0),
            **{
                key: case.get(key)
                for key in (
                    "first_token_sec",
                    "last_token_sec",
                    "result_sec",
                    "error_sec",
                    "total_sec",
                    "drain_sec",
                )
            },
            "client_error": (
                str(case["client_error"]).split(":", 1)[0] if case.get("client_error") else None
            ),
            "drain_error": (
                str(case["drain_error"]).split(":", 1)[0] if case.get("drain_error") else None
            ),
            "route": result.get("route"),
            "quality_score": result.get("quality_score"),
            "quality_source": result.get("quality_source"),
            "answer_source": result.get("answer_source"),
            "generation_source": result.get("generation_source"),
            "sources": len(result.get("sources") or []),
            "citations": sorted(int(c.get("index") or 0) for c in result.get("citations") or []),
            "suggested": len(result.get("suggested_questions") or []),
            "events": [[e.get("type"), e.get("at")] for e in case.get("events", [])],
            "keywords": _kw_status(keywords, [answer]) if keywords else None,
            **marks(answer),
        }
        t0 = case.get("t0_monotonic")
        if t0 is not None:
            end = t0 + case.get("total_sec", 0) + (case.get("drain_sec") or 0)
            row.update(
                case_rows(
                    case, [r for r in stages if t0 - 1 <= r.get("monotonic", -1) <= end + 1], run
                )
            )
            row["memory"] = memory(
                [
                    s
                    for s in resources
                    if s.get("monotonic") is not None
                    and t0 <= s["monotonic"] <= t0 + case.get("total_sec", 0)
                ]
            )
        path = row.get("path") or {}
        row["path_breaks"] = (
            ([] if row["http_status"] == 200 else [f"http {row['http_status']}"])
            + ([] if row["answered"] else ["no answer"])
            + path_breaks(path.get("candidates"), path.get("rerank_status"), row.get("docs"))
            + run_breaks
        )
        cases.append(row)
    return {
        "label": run.name,
        "batch": batch,
        "counted": counted,
        "launch": {key: launch.get(key) for key in LAUNCH},
        "settings": settings.get("settings"),
        "code": settings.get("code"),
        "settings_sha256": hashlib.sha256(
            json.dumps(settings.get("settings"), sort_keys=True).encode()
        ).hexdigest(),
        "cases": [c["case_id"] for c in cases],
        "bm25_restore_log": restore,
        "path_breaks": run_breaks,
        "log_levels": levels,
        "memory": memory(resources),
    }, cases


def aggregate(cases, ids):
    first = [c for c in cases if c["index"] == 1]
    rest = [c for c in cases if c["index"] > 1]
    measured = [c["case_id"] for c in cases]
    times = {}
    for name, group in (("first_of_batch", first), ("rest", rest)):
        times[name] = {
            key: spread([c.get(key) for c in group])
            for key in ("total_sec", "first_token_sec", "result_sec", "retrieval_sec", "rerank_sec")
        }
        times[name]["stream_sec"] = spread(
            [c["stream"][0]["wall_sec"] for c in group if c.get("stream")]
        )
    same = Counter(
        f"{script(c['question_letters'])}->{script(c['answer_letters'])}"
        for c in cases
        if c["answered"]
    )
    labels = [c["prompts"][0]["labels_source"] for c in cases if c.get("prompts")]
    # Batch b holds the registered questions 10b - 9 ... 10b, asked in that order.
    place = {case_id: number for number, case_id in enumerate(ids)}
    return {
        "registered": len(ids),
        "measured": len(measured),
        "missing": [i for i in ids if i not in measured],
        "out_of_place": [
            c["case_id"]
            for c in cases
            if place.get(c["case_id"]) != (c["batch"] - 1) * 10 + c["index"] - 1
        ],
        # Stage 1's definition, «The path breaks» of the spec: any entry stops the work.
        "path_breaks": {c["case_id"]: c["path_breaks"] for c in cases if c["path_breaks"]},
        "answered": sum(c["answered"] for c in cases),
        "routes": dict(Counter(str(c["route"]) for c in cases)),
        "quality_below_80": sum(1 for c in cases if (c["quality_score"] or 0) < 80),
        "quality_sources": dict(Counter(str(c["quality_source"]) for c in cases)),
        "keywords": dict(Counter(str(c["keywords"]) for c in cases)),
        "retrievals_per_case": dict(Counter(c.get("retrievals", 0) for c in cases)),
        "rerank_status": dict(
            Counter(str((c.get("path") or {}).get("rerank_status")) for c in cases)
        ),
        "pool_size": spread([len(c["pool"]) for c in cases if c.get("pool")]),
        "prompt_labels": dict(Counter(labels)),
        "with_marks": sum(1 for c in cases if c["marks"]),
        "marks_past_labels": sum(
            1
            for c in cases
            if c.get("prompts")
            and c["named"]
            and max(c["named"]) > c["prompts"][0]["labels_source"]
        ),
        "answer_script_vs_question": dict(sorted(same.items())),
        "times": times,
        "swap_used_mb_max": max(
            (
                c["memory"]["swap_used_mb"][1]
                for c in cases
                if (c.get("memory") or {}).get("swap_used_mb")
            ),
            default=None,
        ),
    }


def check(label):
    """The path test of one finished batch run, read by stage2.sh before the next batch."""
    _, cases = summarise_run(RUNS / label, 0, True, {})
    breaks = {c["case_id"]: c["path_breaks"] for c in cases if c["path_breaks"]}
    labels = [c["prompts"][0]["labels_source"] if c.get("prompts") else 0 for c in cases]
    print(
        "CHECK",
        label,
        "cases",
        len(cases),
        "labels",
        labels,
        "path_breaks",
        json.dumps(breaks, ensure_ascii=False),
        flush=True,
    )
    return 6 if breaks or not cases else 0


def main():
    if sys.argv[1] == "check":
        return check(sys.argv[2])
    prefix, root, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    key = prefix.split("-", 1)[1]
    base = BASES[key]
    tenant = "aircargo" if base == "aircargo" else f"ext_{base}"
    missing_sources = [n for n in SOURCE_FILES if not (root / base / n).is_file()]
    if missing_sources:
        raise SystemExit(f"the generation lacks {missing_sources}")
    pattern = re.compile(re.escape(prefix) + r"-b(\d{2})(-r\d+)?")
    runs = sorted(
        (
            p
            for p in RUNS.iterdir()
            if p.is_dir() and pattern.fullmatch(p.name) and (p / "launch.json").exists()
        ),
        key=lambda p: p.name,
    )
    if not runs:
        raise SystemExit(f"no runs of {prefix} in {RUNS}")
    launches = {p: json.loads((p / "launch.json").read_text(encoding="utf-8")) for p in runs}
    if any(launch.get("tenant") != tenant for launch in launches.values()):
        raise SystemExit(f"a run of {prefix} is not on the tenant {tenant}")
    cases_file = Path(launches[runs[0]]["cases_file"])
    rows = load_jsonl(cases_file)
    expected = {
        r["case_id"]: list((r.get("expected") or {}).get("answer_contains") or []) for r in rows
    }
    _, names = source_names(root, base)
    chosen = {}
    for path in sorted(runs, key=lambda p: launches[p]["started"]):
        if launches[path].get("status") == "complete" and launches[path].get("runner_exit") == 0:
            chosen[int(pattern.fullmatch(path.name).group(1))] = path
    records, cases = [], []
    for path in runs:
        batch = int(pattern.fullmatch(path.name).group(1))
        record, measured = summarise_run(path, batch, chosen.get(batch) == path, expected)
        records.append(record)
        if record["counted"]:
            cases.extend(measured)
    ids = registered(key, cases_file)
    order = {case_id: i for i, case_id in enumerate(ids)}
    cases.sort(key=lambda c: order.get(c["case_id"], len(order)))
    counted = [r for r in records if r["counted"]]
    log = RUNS / f"{prefix}.log"
    record = {
        "part": prefix,
        "key": key,
        "base": base,
        "provenance": {
            "code_sha": sorted({r["launch"]["code_sha"] for r in counted}),
            "model": sorted({r["launch"]["model"] for r in counted}),
            "model_digest": sorted({r["launch"]["model_digest"] for r in counted}),
            "settings_sha256": sorted({r["settings_sha256"] for r in counted}),
            "settings": counted[0]["settings"] if counted else None,
            "code": counted[0]["code"] if counted else None,
            "overrides": counted[0]["launch"]["overrides"] if counted else None,
            "data_root": str(root),
            "source_sha256": {name: sha256(root / base / name) for name in SOURCE_FILES},
            "cases_file": str(cases_file),
            "cases_file_sha256": sha256(cases_file),
            "tools_sha256": {
                name: sha256(HERE / name) for name in TOOLS if (HERE / name).is_file()
            },
        },
        "driver_log": [
            line
            for line in log.read_text(encoding="utf-8").splitlines()
            if re.match(r"\d{4}-\d\d-\d\dT", line)
        ]
        if log.exists()
        else [],
        "runs": records,
        "aggregate": aggregate(cases, ids),
    }
    questions = [r["query"] for r in rows]
    without_text(record, names, questions)
    without_text(cases, names, questions)
    write(out, prefix, record, cases)
    print(json.dumps(record["aggregate"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

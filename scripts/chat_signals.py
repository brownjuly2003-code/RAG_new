#!/usr/bin/env python3
"""The handover signals S1-S8 on the chat's answers (docs/specs/handover-signal.md, stage 1.0).

Each signal says yes or no — "mark this answer for a person" — and each is computed by the
repository's code, none re-implemented:

- S1, S1' — the chat's own self-score recorded live with the answer (the stream's result
  event): marked below ``QUALITY_THRESHOLD`` (80), and below 100; the length heuristic, which
  the chat routes at 70, never marks and is counted;
- S2, S3 — the widget's claim check, ``make_verify_facts_node`` on the answer and the documents
  the chat's model saw: S2 marked unless ``verified``, S3 when any claim is unsupported
  (citation binding ignored);
- S4 — the widget's relevance, ``make_grade_docs_node`` on those documents and
  ``measure_retrieval_relevance``: marked below the route's ``min_relevance``;
- S5 — a decline: ``_is_knowledge_gap``'s phrases (asked with two documents and no
  factuality, so only its phrases decide) or the answer prompt's own wording; no model call;
- S6 — the widget's first pass, ``make_route_or_retry_node`` with the graph's thresholds on
  the state S1, S2 and S4 build: marked unless ``auto``;
- S7 — retrieval's confidence: the reranker's top score, recorded live by the stand
  (``reports/stage1/tools/live_api.py``) for the very retrieval whose documents the answer
  prompt holds — counted only when the prompt's sources are the reranked ones in order; its
  threshold is chosen on stage 1 (``summary --s7-threshold``);
- S8 — the answer's script: marked when fewer than half of the answer's letters are in the
  question's script, counted by Unicode ranges as ``reports/stage1/tools/audit_summary.py``
  counts them; no model call, no word list.

``plan`` reads run records and freezes, before the first model call, the answers in order, the
digests of their prompts and answers, the signals that need no model (S1, S1', S5, S7, S8), the
forecast and the stop rule; it holds no question, document or answer text, so it can be
committed for any corpus. ``run`` computes S2, S3, S4 and S6 with the 4B the code defaults
serve, appending one row per answer; it stops at 3x the forecast (Julia's rule) and unloads the
model after every five answers (Ollama's runner grows until an unload). ``summary`` counts the
marks per signal and, given the judge's verdicts (``scripts/chat_answer_judge.py``), what each
signal catches among the answers that need a person.

Usage:
  python -m scripts.chat_signals plan --run LABEL=DIR ... --code-sha SHA --out PLAN.json
  python -m scripts.chat_signals run PLAN.json OUT.jsonl            (Mac, a git archive)
  python -m scripts.chat_signals summary PLAN.json OUT.jsonl [--judge DIR] [--s7-threshold X]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.request
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import chat_answer_judge as judge  # noqa: E402

MODEL = "qwen3:4b-instruct-2507-q4_K_M"
# The decline wording of the V2 answer prompt. V3 (2026-10-18, agent/prompts.py) asks for the
# decline in the question's language and fixes no words, so this catches only an answer that
# still uses V2's; S5's wording is stage 3's to settle (docs/specs/handover-signal.md).
PROMPT_DECLINE = "ответить нельзя"
UNLOAD_EVERY = 5
# Per answer: the grader and the first claim about 65 s each, other claims 10-65 s.
FORECAST_SEC = (180, 600)
FIRST_CAP_SEC = 1800
FIRST_ANSWERS = 5
CHOICE_ENV = (
    "OLLAMA_MODEL_NAME",
    "OLLAMA_FAST_MODEL_NAME",
    "MODEL_ROUTING_ENABLED",
    "LLM_PROVIDER_PROFILE",
    "PROVIDER_REGISTRY_PATH",
    "QUALITY_THRESHOLD",
    "OLLAMA_CONTEXT_WINDOW",
    "FACT_VERIFICATION_ENABLED",
    "MIN_RELEVANCE_FOR_AUTO",
    "MIN_FACTUALITY_FOR_AUTO",
)
SIGNALS = ("S1", "S1p", "S2", "S3", "S4", "S5", "S6", "S7", "S8")
# A node of the widget's graph: a state in, the state with its fields out.
Node = Callable[[Any], Any]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_decline(answer: str) -> bool:
    """S5: the widget's gap phrases, alone, or the answer prompt's decline wording."""
    from agent.graph import _is_knowledge_gap

    lone: Any = {"context_docs": [{}, {}], "factuality_score": None, "answer": answer}
    return _is_knowledge_gap(lone) or PROMPT_DECLINE in answer.lower()


def letters(text: str) -> dict[str, int]:
    """Cyrillic and Latin letters, by audit_summary.py's ranges."""
    return {
        "cyrillic": len(re.findall("[а-яА-ЯёЁ]", text)),
        "latin": len(re.findall("[a-zA-Z]", text)),
    }


def other_script(question: str, answer: str) -> bool:
    """S8: fewer than half of the answer's letters in the script most of the question's are."""
    asked = letters(question)
    script = "cyrillic" if asked["cyrillic"] > asked["latin"] else "latin"
    answered = letters(answer)
    return answered[script] < sum(answered.values()) / 2


def retrievals(stages: Path) -> dict[str, dict[str, Any]]:
    """The rerank the stand recorded before each streamed answer prompt, by prompt file."""
    bound: dict[str, dict[str, Any]] = {}
    last: dict[str, Any] | None = None
    for line in stages.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("event") == "end" and row.get("stage") == "hybrid._rerank_scored_with_status":
            last = row
        elif row.get("event") == "start" and row.get("stage") == "ollama.generate_stream":
            if last is not None:
                bound[str(row.get("prompt_file"))] = last
            last = None
    return bound


def s7_reading(rerank: Mapping[str, Any] | None, sources: Sequence[str]) -> dict[str, Any]:
    """The top rerank score, kept only when the prompt holds the reranked documents in order."""
    if rerank is None or "scores" not in rerank:
        return {"status": "no_record", "top_score": None}
    if not rerank.get("reranker_ok"):
        return {"status": "reranker_failed", "top_score": None}
    ranked = list(rerank.get("sources") or [])
    if not sources or list(sources) != ranked[: len(sources)]:
        return {"status": "order_differs", "top_score": None}
    top = rerank["scores"][0] if rerank["scores"] else None
    return {"status": "ok" if top is not None else "no_score", "top_score": top}


def build_plan(runs: Mapping[str, Path], code_sha: str) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    records: dict[str, Any] = {}
    for label, run in runs.items():
        launch_path = run / "launch.json"
        launch = json.loads(launch_path.read_text(encoding="utf-8")) if launch_path.exists() else {}
        records[label] = {
            "path": str(run),
            "code_sha": launch.get("code_sha"),
            "tenant": launch.get("tenant"),
            "model": launch.get("model"),
            "model_digest": launch.get("model_digest"),
        }
        bound = retrievals(run / "stages.jsonl")
        live = {}
        for path in sorted((run / "cases").glob("*.json")):
            case = json.loads(path.read_text(encoding="utf-8"))
            result: dict[str, Any] = next(
                (e for e in case.get("events", []) if e.get("type") == "result"), {}
            )
            live[case["case_id"]] = (path.name, result)
        for answer in judge.run_answers(run):
            case_file, result = live[answer["case_id"]]
            quality = result.get("quality_score")
            source = result.get("quality_source")
            text = answer["answer"]
            sources = [source_name for source_name, _ in answer["documents"]]
            s7 = s7_reading(bound.get(answer["prompt_file"]), sources)
            items.append(
                {
                    "item": len(items) + 1,
                    "run": label,
                    "case_id": answer["case_id"],
                    "case_file": case_file,
                    "prompt_file": answer["prompt_file"],
                    "prompt_sha256": answer["prompt_sha256"],
                    "answer_sha256": _digest(text),
                    "documents": len(answer["documents"]),
                    "live_route": answer["route"],
                    "quality_score": quality,
                    "quality_source": source,
                    "S1": source == "llm" and quality is not None and quality < 80,
                    "S1p": source == "llm" and quality is not None and quality < 100,
                    "S5": is_decline(text),
                    "S7": s7,
                    "S8": other_script(answer["question"], text),
                    "empty_answer": not text,
                }
            )
    return {
        "named": _now(),
        "what": "handover signals S1-S8 on chat answers (docs/specs/handover-signal.md)",
        "code_sha": code_sha,
        "model": MODEL,
        "runs": records,
        "forecast_sec": list(FORECAST_SEC),
        "stop_rule": (
            f"each of the first {FIRST_ANSWERS} answers stops at {FIRST_CAP_SEC} s "
            "(3 x the 600-s forecast), every later one at 3 x the median of the first five"
        ),
        "unload_every": UNLOAD_EVERY,
        "items": items,
    }


def _documents(text: str) -> list[Any]:
    """The prompt's documents in the form the widget's retrieve node gives its graph."""
    from langchain_core.documents import Document

    from agent.graph import _docs_to_plain_dicts

    _, documents = judge.read_prompt(text)
    return _docs_to_plain_dicts(
        [Document(page_content=body, metadata={"source": src}) for src, body in documents]
    )


def _route_node(settings: Any) -> tuple[Node, float]:
    """route_or_retry with the thresholds build_graph gives it (agent/graph.py)."""
    from agent.calibration import resolve_routing_thresholds
    from agent.graph import make_route_or_retry_node

    try:
        thresholds = resolve_routing_thresholds(settings)
    except Exception:
        thresholds = None
    if thresholds is not None:
        min_quality = int(thresholds.min_quality)
        min_relevance = float(thresholds.min_relevance)
        min_factuality = int(thresholds.min_factuality)
    else:
        min_quality = int(getattr(settings, "quality_threshold", 80))
        min_relevance = float(getattr(settings, "min_relevance_for_auto", 0.8) or 0.8)
        min_factuality = int(getattr(settings, "min_factuality_for_auto", 80) or 80)
    node = make_route_or_retry_node(
        min_quality=min_quality, min_relevance=min_relevance, min_factuality=min_factuality
    )
    return node, min_relevance


def model_signals(
    item: Mapping[str, Any],
    question: str,
    answer: str,
    documents: list[Any],
    grade: Node,
    verify: Node,
    route: Node,
    min_relevance: float,
) -> dict[str, Any]:
    """S2, S3, S4 and S6 for one answer, each node on the documents the model saw."""
    from agent.graph import _is_knowledge_gap
    from agent.relevance import measure_retrieval_relevance

    base = {
        "trace_id": f"signal-{item['run']}-{item['case_id']}",
        "question": question,
        "answer": answer,
        "context_docs": documents,
        "iteration": 0,
        "max_iterations": 2,
    }
    started = time.monotonic()
    graded = grade(dict(base))
    grade_sec = time.monotonic() - started
    kept = list(graded.get("graded_docs") or [])
    relevance, relevance_source = measure_retrieval_relevance(
        context_docs=documents, graded_docs=kept
    )
    started = time.monotonic()
    verified = verify({**base, "generation_context_docs": documents})
    verify_sec = time.monotonic() - started
    claims = [
        {"supported": bool(claim.get("supported")), "cited": claim.get("citation_bound")}
        for claim in verified.get("claims") or []
    ]
    llm_score = item["quality_source"] == "llm"
    state: Any = {
        **graded,
        **{key: verified.get(key) for key in GROUNDING_KEYS if key in verified},
        "quality_score": item["quality_score"],
        "quality_source": item["quality_source"],
        "relevance_score": relevance,
        "judge_status": "ok" if llm_score else "parse_failure",
    }
    state["knowledge_gap"] = _is_knowledge_gap(state)
    routed = route(state)
    errors = [row.get("error") for row in (graded, verified, routed) if row.get("error")]
    return {
        "S2": {
            "grounding_status": verified.get("grounding_status"),
            "factuality": verified.get("factuality_score"),
            "skipped": verified.get("fact_verification_skipped"),
            "error": verified.get("fact_verification_error"),
            "marked": verified.get("grounding_status") != "verified",
        },
        "S3": {"claims": claims, "marked": any(not claim["supported"] for claim in claims)},
        "S4": {
            "kept": len(kept),
            "documents": len(documents),
            "relevance": relevance,
            "source": relevance_source,
            "outcome": graded.get("doc_grade_outcome"),
            "marked": relevance is None or relevance < min_relevance,
        },
        "S6": {
            "route": routed.get("route"),
            "knowledge_gap": state["knowledge_gap"],
            "marked": routed.get("route") != "auto",
        },
        "node_errors": [str(error)[:300] for error in errors],
        "seconds": {"grade": round(grade_sec, 3), "verify": round(verify_sec, 3)},
    }


GROUNDING_KEYS = (
    "claims",
    "factuality_score",
    "grounding_status",
    "fact_verification_skipped",
    "fact_verification_error",
)


def _unload(base_url: str, model: str) -> None:
    body = json.dumps({"model": model, "keep_alive": 0}).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - local Ollama
        response.read()


def run_plan(plan: Mapping[str, Any], out: Path) -> int:
    leaked = [name for name in CHOICE_ENV if os.environ.get(name)]
    if leaked:
        raise SystemExit(f"the environment chooses the model or a threshold: {leaked}")
    code_sha = (Path.cwd() / "CODE_SHA").read_text(encoding="utf-8").strip()
    if code_sha != plan["code_sha"]:
        raise SystemExit(f"workspace {code_sha} != plan {plan['code_sha']}")

    from agent.graph import make_grade_docs_node, make_verify_facts_node
    from config.settings import Settings
    from llm.providers import build_provider_runtime

    settings = Settings()
    runtime = build_provider_runtime(settings)
    llm = runtime.fast
    served = getattr(llm, "model_name", None)
    if served != plan["model"]:
        raise SystemExit(f"served {served} != plan {plan['model']}")
    grade, verify = make_grade_docs_node(llm), make_verify_facts_node(llm)
    route, min_relevance = _route_node(settings)

    rows = judge._read_jsonl(out)
    done = {row["item"] for row in rows if row.get("kind") == "answer"}
    elapsed = [row["seconds"]["total"] for row in rows if row.get("kind") == "answer"]
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    judge._append(
        out,
        {
            "kind": "start",
            "at": _now(),
            "code_sha": code_sha,
            "served": served,
            "rag_env": os.environ.get("RAG_ENV"),
            "min_relevance": min_relevance,
            "resumed_after": len(done),
        },
    )
    since_unload = 0
    for item in plan["items"]:
        if item["item"] in done or item["empty_answer"]:
            continue
        run = Path(plan["runs"][item["run"]]["path"])
        prompt = (run / "prompts" / item["prompt_file"]).read_text(encoding="utf-8")
        case = json.loads((run / "cases" / item["case_file"]).read_text(encoding="utf-8"))
        result: dict[str, Any] = next(
            (e for e in case.get("events", []) if e.get("type") == "result"), {}
        )
        answer = str(result.get("answer") or case.get("answer") or "").strip()
        if _digest(prompt) != item["prompt_sha256"] or _digest(answer) != item["answer_sha256"]:
            raise SystemExit(f"item {item['item']}: the run record changed after the plan")
        question, _ = judge.read_prompt(prompt)
        documents = _documents(prompt)
        cap = (
            FIRST_CAP_SEC
            if len(elapsed) < FIRST_ANSWERS
            else 3 * statistics.median(elapsed[:FIRST_ANSWERS])
        )
        started = time.monotonic()
        future = pool.submit(
            model_signals, item, question, answer, documents, grade, verify, route, min_relevance
        )
        try:
            signals = future.result(timeout=cap)
        except concurrent.futures.TimeoutError:
            judge._append(
                out,
                {
                    "kind": "stop",
                    "at": _now(),
                    "item": item["item"],
                    "elapsed_sec": round(time.monotonic() - started, 3),
                    "cap_sec": cap,
                },
            )
            os._exit(3)
        total = round(time.monotonic() - started, 3)
        elapsed.append(total)
        signals["seconds"]["total"] = total
        judge._append(out, {"kind": "answer", "at": _now(), "item": item["item"], **signals})
        since_unload += 1
        if since_unload == UNLOAD_EVERY:
            _unload(settings.ollama_base_url, served)
            since_unload = 0
    _unload(settings.ollama_base_url, served)
    judge._append(out, {"kind": "end", "at": _now()})
    pool.shutdown(wait=False)
    return 0


def wilson(hits: int, total: int, z: float = 1.96) -> list[float] | None:
    if total == 0:
        return None
    share = hits / total
    denominator = 1 + z * z / total
    centre = (share + z * z / (2 * total)) / denominator
    half = z * math.sqrt(share * (1 - share) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def marks(
    item: Mapping[str, Any], row: Mapping[str, Any] | None, threshold: float | None
) -> dict[str, bool | None]:
    """Each signal's yes or no for one answer; None when it was not computed."""
    s7 = item["S7"]
    out: dict[str, bool | None] = {
        "S1": item["S1"],
        "S1p": item["S1p"],
        "S5": item["S5"],
        "S8": item["S8"],
        "S7": (
            None
            if threshold is None or s7["status"] != "ok"
            else float(s7["top_score"]) < threshold
        ),
    }
    for name in ("S2", "S3", "S4", "S6"):
        out[name] = None if row is None else bool(row[name]["marked"])
    return out


def summarize(
    plan: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    *,
    judged: Mapping[tuple[str, str], tuple[str, bool]] | None = None,
    s7_threshold: float | None = None,
) -> dict[str, Any]:
    """Marks per signal; with the judge's classes, caught and over-marked (Wilson 95 %)."""
    answered = {row["item"]: row for row in rows if row.get("kind") == "answer"}
    per_item = [
        (item, marks(item, answered.get(item["item"]), s7_threshold)) for item in plan["items"]
    ]
    summary: dict[str, Any] = {
        "answers": len(per_item),
        "with_model_signals": len(answered),
        "heuristic_scores": sum(1 for item, _ in per_item if item["quality_source"] != "llm"),
        "s7_status": dict(Counter(item["S7"]["status"] for item, _ in per_item)),
        "s7_threshold": s7_threshold,
        "added_seconds_median": (
            statistics.median(row["seconds"]["total"] for row in answered.values())
            if answered
            else None
        ),
        "signals": {},
    }
    for name in SIGNALS:
        known = [(item, bool(mark[name])) for item, mark in per_item if mark[name] is not None]
        entry: dict[str, Any] = {
            "computed": len(known),
            "marked": sum(1 for _, mark in known if mark),
        }
        if judged is not None:
            target = [
                mark
                for item, mark in known
                if (key := (item["run"], item["case_id"])) in judged
                and (judged[key][0] == "bad" or judged[key][1])
            ]
            good = [
                mark
                for item, mark in known
                if (key := (item["run"], item["case_id"])) in judged
                and judged[key][0] == "good"
                and not judged[key][1]
            ]
            entry.update(
                {
                    "target": len(target),
                    "caught": sum(target),
                    "caught_wilson95": wilson(sum(target), len(target)),
                    "good_not_declining": len(good),
                    "over_marked": sum(good),
                    "over_marked_wilson95": wilson(sum(good), len(good)),
                }
            )
        summary["signals"][name] = entry
    return summary


def judged_classes(judge_dir: Path) -> dict[tuple[str, str], tuple[str, bool]]:
    """(run, case) -> (the judge's class, whether the answer declines) from its verdicts."""
    plan = json.loads((judge_dir / "plan.json").read_text(encoding="utf-8"))
    valid = judge._vouched(plan, judge._read_jsonl(judge_dir / "verdicts.jsonl"))
    out: dict[tuple[str, str], tuple[str, bool]] = {}
    for item in plan["items"]:
        if "retest_of" in item:
            continue
        key = (item["run"], item["case_id"])
        if item.get("empty_answer"):
            out[key] = ("bad", False)
        elif item["item_id"] in valid:
            verdict = valid[item["item_id"]]
            out[key] = (judge.classify(verdict), verdict["answers_question"] == "declined")
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan")
    plan_parser.add_argument("--run", action="append", required=True, metavar="LABEL=DIR")
    plan_parser.add_argument("--code-sha", required=True)
    plan_parser.add_argument("--out", type=Path, required=True)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("plan", type=Path)
    run_parser.add_argument("out", type=Path)
    summary_parser = commands.add_parser("summary")
    summary_parser.add_argument("plan", type=Path)
    summary_parser.add_argument("out", type=Path)
    summary_parser.add_argument("--judge", type=Path)
    summary_parser.add_argument("--s7-threshold", type=float)
    args = parser.parse_args(argv)

    if args.command == "plan":
        if args.out.exists():
            raise SystemExit(f"{args.out} exists: a plan is frozen once written")
        runs: dict[str, Path] = {}
        for spec in args.run:
            label, _, path = spec.partition("=")
            if not label or not path or label in runs:
                raise SystemExit(f"--run {spec}: give each run once as LABEL=DIR")
            runs[label] = Path(path)
        plan = build_plan(runs, args.code_sha)
        args.out.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", "utf-8")
        print(json.dumps({"items": len(plan["items"]), "out": str(args.out)}))
        return 0
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    if args.command == "run":
        return run_plan(plan, args.out)
    judged = judged_classes(args.judge) if args.judge else None
    summary = summarize(
        plan, judge._read_jsonl(args.out), judged=judged, s7_threshold=args.s7_threshold
    )
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

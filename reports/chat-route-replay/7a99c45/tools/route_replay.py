"""The web chat's routing rule replayed on the judged answers of one generator.

The chat's stream routes an answer ``auto`` when the generator's own score of
it is at least ``QUALITY_THRESHOLD`` (80) and ``human`` otherwise
(``api/routers/conversation.py``, the self-evaluation after the stream). This
tool sends that same self-evaluation — ``build_self_eval_prompt`` over the
contexts fitted by ``fit_context_docs`` for the role ``evaluate``, through the
provider runtime the chat builds from ``Settings()`` — for each of the 100
answers the generator screening wrote and the judge graded, and records the
score and the route. It writes no answer of its own and runs no retrieval: the
answers and contexts are the screening's (``reports/generator-screen/86df582``).

Run in a ``git archive`` of one commit, with no model, profile or registry in
the environment, so the served model is the code default:

    python route_replay.py <plan.json> <out.jsonl>

Each case is cut off at 3x its forecast (Julia's stop rule): the tool records
the stop and exits 3.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WS = Path.cwd()
sys.path.insert(0, str(WS))
sys.path.insert(0, str(WS / "scripts"))

CHOICE_ENV = (
    "OLLAMA_MODEL_NAME",
    "OLLAMA_FAST_MODEL_NAME",
    "MODEL_ROUTING_ENABLED",
    "LLM_PROVIDER_PROFILE",
    "PROVIDER_REGISTRY_PATH",
    "QUALITY_THRESHOLD",
    "OLLAMA_CONTEXT_WINDOW",
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    plan_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    leaked = [name for name in CHOICE_ENV if os.environ.get(name)]
    if leaked:
        raise SystemExit(f"environment chooses the model or the rule: {leaked}")

    from generator_benchmark import load_benchmark_cases

    from agent.context_window import fit_context_docs
    from agent.graph import _invoke_llm, _parse_int_score
    from agent.prompts import build_self_eval_prompt
    from config.settings import Settings
    from llm.providers import build_provider_runtime

    dataset = WS / plan["dataset"]["path"]
    contexts = Path(plan["contexts"]["path"])
    report = WS / plan["answers"]["path"]
    for name, path in (("dataset", dataset), ("contexts", contexts), ("answers", report)):
        digest = sha256(path)
        if digest != plan[name]["sha256"]:
            raise SystemExit(f"{name} digest {digest} != plan {plan[name]['sha256']}")

    cases = {
        c["case_id"]: c
        for c in load_benchmark_cases(
            dataset_path=dataset,
            contexts_path=contexts,
            expected_cases=100,
            context_chars=int(plan["contexts"]["context_chars"]),
        )
    }
    answers = {
        c["case_id"]: c["answer"]
        for c in json.loads(report.read_text(encoding="utf-8"))["runs"][0]["cases"]
    }

    settings = Settings()
    threshold = int(settings.quality_threshold)
    runtime = build_provider_runtime(settings)
    # The chat's session has no model of its own: the stream takes the runtime's
    # strong model and evaluates with the same one.
    eval_llm = runtime.strong
    served = {
        "ollama_model_name": settings.ollama_model_name,
        "runtime_profile": runtime.profile_name,
        "eval_model": getattr(eval_llm, "model_name", None),
        "eval_provider": getattr(eval_llm, "provider_id", None),
        "quality_threshold": threshold,
        "ollama_context_window": settings.ollama_context_window,
        "provider_registry_path": str(settings.provider_registry_path),
    }
    if served["eval_model"] != plan["model"]:
        raise SystemExit(f"served {served['eval_model']} != plan {plan['model']}")

    done = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("kind") == "case":
                done.add(row["case_id"])

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    with out_path.open("a", encoding="utf-8") as out:

        def write(row: dict) -> None:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()

        write({"kind": "start", "at": now(), "served": served, "resumed_after": len(done)})
        for position, case_id in enumerate(plan["case_order"]):
            if case_id in done:
                continue
            case = cases[case_id]
            question = case["query"]
            answer = re.sub(r"\s*\[\d+\]", "", answers[case_id])
            answer = re.sub(r"\s{2,}", " ", answer).strip()
            docs = [
                {"page_content": text, "metadata": {}} for text in case["contexts"]
            ]

            def prompt_for(selected, question=question, answer=answer):
                return build_self_eval_prompt(
                    question=question, answer=answer, context_docs=selected
                )

            prompt = prompt_for(
                fit_context_docs(
                    eval_llm, question + " " + answer, docs, prompt_for, role="evaluate"
                )
            )
            forecast = float(
                plan["forecast_first_sec"] if position == 0 else plan["forecast_sec"]
            )
            cap = 3 * forecast
            started = time.monotonic()
            future = pool.submit(_invoke_llm, eval_llm, prompt, role="evaluate")
            try:
                raw = future.result(timeout=cap)
                error = None
            except concurrent.futures.TimeoutError:
                write({"kind": "stop", "at": now(), "case_id": case_id,
                       "elapsed_sec": round(time.monotonic() - started, 3),
                       "forecast_sec": forecast, "cap_sec": cap})
                os._exit(3)
            except Exception as exc:  # recorded, the rule's fallback applies
                raw, error = "", f"{type(exc).__name__}: {exc}"[:300]
            elapsed = time.monotonic() - started
            parsed = _parse_int_score(str(raw or ""), default=-1)
            if parsed != -1:
                quality, source = parsed, "llm"
                route = "auto" if quality >= threshold else "human"
            else:
                # The stream keeps its length heuristic and routes it at 70.
                quality = 70 if len(answers[case_id].strip()) > 20 else 40
                source = "heuristic"
                route = "auto" if quality >= 70 else "human"
            write({
                "kind": "case", "at": now(), "case_id": case_id,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "prompt_chars": len(prompt), "docs_sent": prompt.count("[Документ "),
                "raw": str(raw or "")[:200], "error": error, "quality": quality,
                "quality_source": source, "route": route,
                "elapsed_sec": round(elapsed, 3), "forecast_sec": forecast,
            })
        write({"kind": "end", "at": now()})
    pool.shutdown(wait=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

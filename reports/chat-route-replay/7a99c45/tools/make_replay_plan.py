"""Name the chat-route replay before its run: inputs, forecast, stop rule and reading."""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("D:/RAG_new")
OUT = Path(sys.argv[1])
CODE_SHA = sys.argv[2]
DATASET = "evaluation/curated_cases_aircargo.jsonl"
ANSWERS = (
    "reports/generator-screen/86df582/reports/"
    "gs-qwen3-4b-instruct-n100-phase-c-generator-benchmark.json"
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


order = [
    json.loads(line)["case_id"]
    for line in (REPO / DATASET).read_text(encoding="utf-8").splitlines()
    if line.strip()
]
assert len(order) == 100
plan = {
    "named": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "what": (
        "The web chat's routing rule — the generator's own score of its answer, auto at "
        "QUALITY_THRESHOLD 80 or above, human below, the length heuristic at 70 when no number "
        "comes back — replayed through the repository's code (build_self_eval_prompt, "
        "fit_context_docs for the role evaluate, the provider runtime the chat builds from "
        "Settings(), _invoke_llm, _parse_int_score) on the 100 answers Qwen3-4B-Instruct wrote "
        "in the generator screening and the judge graded"
    ),
    "code_sha": CODE_SHA,
    "model": "qwen3:4b-instruct-2507-q4_K_M",
    "model_digest": "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0",
    "dataset": {"path": DATASET, "sha256": sha(REPO / DATASET)},
    "contexts": {
        "path": "/Users/julia/genscreen_86df582/.tmp/ab_candidates_phase2_C.json",
        "sha256": "91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10",
        "context_chars": 6000,
    },
    "answers": {"path": ANSWERS, "sha256": sha(REPO / ANSWERS), "generator_seed": 42},
    "judge": {
        "verdicts": "reports/generator-screen/86df582/judge-100/verdicts.jsonl",
        "plan": "reports/generator-screen/86df582/judge-100/plan.json",
        "classes": "scripts/generator_answer_judge.py classify(): good, partial_ok, bad",
    },
    "case_order": order,
    "forecast_first_sec": 60,
    "forecast_sec": 40,
    "forecast_basis": (
        "the screening's 4B read prompts at a median 45.3 tokens/s on this Mac with no API "
        "loaded, and its answer prompt for the first case took 1,340 tokens; the evaluation "
        "prompt carries the same contexts plus the answer and asks for one number — about "
        "35 s; 40 s a case, 60 s for the first (the model's load); about 70 minutes for 100"
    ),
    "stop_rule": (
        "Julia, 2026-10-15: a case that runs past 3x its forecast stops the run "
        "(120 s, the first 180 s); the session investigates at once"
    ),
    "reading": [
        "human share: cases routed human of 100, with the 95% Wilson interval",
        "against the judge: of the bad answers, how many go human (caught) and how many auto "
        "(passed to the client unmarked); of the good, how many go human (sent needlessly); "
        "partial_ok apart",
        "the score distribution and the parse failures, counted apart",
        "an estimate of the chat's rule on this model's answers on the test set: the answers "
        "come from the screening's prompt, the contexts from the phase-C harness, not from "
        "the chat's retrieval; not customer traffic; not the widget's rule (/api/ask routes "
        "by the graph's node: relevance, grounding, retries)",
        "no threshold or rule changes on this run; a change of the rule is Julia's decision",
    ],
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("named", plan["named"], OUT)

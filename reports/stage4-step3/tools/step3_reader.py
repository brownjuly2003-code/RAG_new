"""Stage 4, step 3's reader: K = 14 against 20, the rerank's seconds with the retrieval alone.

docs/specs/stage4-step3-k-timing.md, registered with this tool before the first request.
On the Mac after the runs, any Python 3.11, the standard library only:

  python -I step3_reader.py OUT RUN_DIR [RUN_DIR ...]

A run is the directory step 1's live_supervisor.py (unchanged) writes in mode retrieval, its
drivers two levels up: launch.json, effective_settings.json, retrieval-cpu.json (written at the
run's end) and a file a question, retrieval/NNN-<case>.json, which stage 2's live_retrieval.py
writes. Of a question (an ask) the reader keeps its walls (the retrieval, its vector search and
its rerank), the rerank's status and success, the lanes' lengths, the merged candidates, the
pool's count and the SHA-256 of its [source, chunk_index] set, the documents back and sent and
the prompt's estimated tokens. The four asks of one question, two at each K, make its pair; the
readings are functions of the readable pairs alone.

OUT holds numbers, enums, ids, the paths named here and SHA-256 strings: no question, document,
source name or prompt. Prints the spec's readings; refuses an existing OUT.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA = "stage4-step3/v1"
SPEC = "docs/specs/stage4-step3-k-timing.md"
HERE = Path(__file__).resolve().parent
NOT_EVIDENCE = "NOT_EVIDENCE"
CODE_SHA = "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1"
# aircargo's registered order, its first thirteen: the first pays the encoders' load in every
# run and pairs with nothing; the other twelve make the pairs.
CASES = (
    "aircargo-probation-data",
    "aircargo-probation-extend",
    "aircargo-probation-dismissal",
    "aircargo-dismissal-check",
    "aircargo-dismissal-lawyer",
    "aircargo-dismissal-order",
    "aircargo-leave-sources",
    "aircargo-leave-compensation",
    "aircargo-leave-risk",
    "aircargo-matliab-check",
    "aircargo-matliab-disputed",
    "aircargo-templates-choose",
    "aircargo-templates-checklist",
)
PAIRED = CASES[1:]
# The registered runs in their order, ABBA, and each one's K.
RUNS = {"s3-k20-1": 20, "s3-k14-1": 14, "s3-k14-2": 14, "s3-k20-2": 20}
# What a run must have run, two levels above its directory: step 1's supervisor, V4's
# live_api.py and stage 2's retrieval driver with its helpers.
DRIVERS_SHA256 = {
    "live_api.py": "43ff96f06af18538a2571d68a86e898ecfcdd5fcab47039f0d58bd245361a7b5",
    "live_retrieval.py": "9e41910d371630ec7b215c8649d5c1a124da16ff5c0977d89c291f5de371e916",
    "live_supervisor.py": "915ffa9e22e3165f56cd54194fe20e89c8e4146f5a10170f32094a03138fe536",
    "stage2_common.py": "4d5241560ab5425faa0a1fe6c5b856454b3f8ee47e59187f0da6644b1bad48da",
}
# The settings both K keep (the code defaults: five kept, the CPU); K is the run's.
SETTINGS = {"rerank_top_k": 5, "rag_device": "cpu"}
# The K curve's candidates for each question at K = 14 and at 20 (reports/k-curve/5e308fe/
# rows.jsonl, aircargo): printed beside the live pools, deciding nothing.
K_CURVE_CANDIDATES = {
    "aircargo-probation-data": (23, 32),
    "aircargo-probation-extend": (24, 36),
    "aircargo-probation-dismissal": (25, 37),
    "aircargo-dismissal-check": (24, 35),
    "aircargo-dismissal-lawyer": (23, 35),
    "aircargo-dismissal-order": (22, 30),
    "aircargo-leave-sources": (27, 39),
    "aircargo-leave-compensation": (25, 37),
    "aircargo-leave-risk": (27, 39),
    "aircargo-matliab-check": (20, 28),
    "aircargo-matliab-disputed": (21, 29),
    "aircargo-templates-choose": (25, 37),
    "aircargo-templates-checklist": (27, 39),
}
LAUNCH_KEYS = (
    "label",
    "mode",
    "cases",
    "client_cap_sec",
    "started",
    "code_sha",
    "model",
    "tenant",
    "status",
    "variants",
    "variant_order",
    "ollama_models_before",
    "ollama_models_after",
)
WALLS = ("retrieval", "vector", "rerank")
# The spec's readings, frozen with it.
MIN_QUESTIONS = 10
ALPHA = 0.05


def sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def num(value: Any) -> int | float | None:
    """A number as it is; anything else (a bool included) is None."""
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def an_id(value: Any) -> str | None:
    """A case id or a label as it is; anything else masked."""
    if value is None:
        return None
    return str(value) if re.fullmatch(r"[\w.-]+", str(value)) else "<not an id>"


def a_name(value: Any) -> str | None:
    """A model name or an enum as it is (a tag holds ":"); anything else masked."""
    if value is None:
        return None
    return str(value) if re.fullmatch(r"[\w.:/-]+", str(value)) else "<not a name>"


def rounded(value: float | None, places: int = 3) -> float | None:
    return None if value is None else round(value, places)


def median(values: Sequence[float]) -> float | None:
    return round(statistics.median(values), 3) if values else None


def load(path: Path, notes: list[str], what: str) -> dict[str, Any]:
    """A file's JSON object; a file not found, not JSON or not an object is noted and empty."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    if not isinstance(data, dict):
        notes.append(f"run: no readable {what}")
        return {}
    return data


def field(data: dict[str, Any], key: str, kind: type) -> Any:
    """data[key] when it is a kind; else an empty kind, a shape not found."""
    value = data.get(key)
    return value if isinstance(value, kind) else kind()


def idents(items: Any) -> list[str]:
    """Each [source, chunk_index, ...] item as the JSON of its first two: an identity."""
    if not isinstance(items, list):
        return []
    return [json.dumps(item[:2], ensure_ascii=False) for item in items if isinstance(item, list)]


def read_ask(path: Path, k: int | None) -> dict[str, Any]:
    """One question's file: its numbers and the reasons it is not read; never a text."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("not a JSON object")
    walls = field(data, "walls", dict)
    route = field(data, "path", dict)
    lanes = {name: idents(field(data, "lanes", dict).get(name)) for name in ("vector", "bm25")}
    pool = idents(data.get("pool"))
    candidates = field(route, "candidates", dict)
    prompt = field(data, "prompt", dict)
    ask: dict[str, Any] = {"case_id": an_id(data.get("case_id")), "index": num(data.get("index"))}
    ask.update({name: rounded(num(walls.get(name))) for name in WALLS})
    ask["reranker_ok"] = data.get("reranker_ok") is True
    ask["rerank_status"] = a_name(route.get("rerank_status"))
    ask["lanes"] = {name: len(found) for name, found in lanes.items()}
    ask["merged"] = num(candidates.get("merged"))
    ask["pool"] = len(pool)
    text = json.dumps(sorted(pool), ensure_ascii=False)
    ask["pool_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest() if pool else None
    ranked = field(data, "ranked", list)
    ask["ranked"] = len(ranked)
    ask["ranked_sha256"] = (
        hashlib.sha256(json.dumps(idents(ranked), ensure_ascii=False).encode()).hexdigest()
        if ranked
        else None
    )
    ask["sent"] = len(data["sent"]) if isinstance(data.get("sent"), list) else None
    ask["prompt_est_tokens"] = num(prompt.get("est_tokens"))
    why = []
    for name in WALLS:
        if ask[name] is None:
            why.append(f"no {name} seconds")
    if not ask["reranker_ok"] or ask["rerank_status"] != "ok":
        why.append("the rerank did not succeed")
    if k is None or ask["lanes"]["vector"] != k or not 0 < ask["lanes"]["bm25"] <= k:
        why.append("a lane not K long")
    if not ask["pool"] or ask["ranked"] != 5:
        why.append("no pool, or not five kept")
    ask["unread"] = why
    ask["read"] = not why
    ask["sha256"] = sha256(path)
    return ask


def read_run(run_dir: Path) -> dict[str, Any]:
    """One run: its launch, settings, drivers, asks and its gate."""
    notes: list[str] = []
    label = run_dir.name
    k = RUNS.get(label.removesuffix("-r2"))
    launch = load(run_dir / "launch.json", notes, "launch.json")
    kept = {key: launch[key] for key in LAUNCH_KEYS if key in launch}
    kept = json.loads(json.dumps(kept, ensure_ascii=False))
    kept["cases"] = [an_id(case) for case in field(launch, "cases", list)]
    for key in ("ollama_models_before", "ollama_models_after"):
        if isinstance(launch.get(key), list):
            kept[key] = [a_name(name) for name in launch[key]]
    overrides = field(launch, "overrides", dict)
    kept["k_override"] = a_name(overrides.get("RAG_RETRIEVAL_TOP_K"))
    data = load(run_dir / "effective_settings.json", notes, "effective_settings.json")
    found = field(data, "settings", dict)
    settings: dict[str, Any] = {"retrieval_top_k": num(found.get("retrieval_top_k"))}
    settings.update(
        {
            key: a_name(found.get(key)) if isinstance(value, str) else num(found.get(key))
            for key, value in SETTINGS.items()
        }
    )
    drivers = {name: sha256(run_dir.parent.parent / name) for name in DRIVERS_SHA256}
    summary = load(run_dir / "retrieval-cpu.json", notes, "retrieval-cpu.json")
    asks = []
    for path in sorted((run_dir / "retrieval").glob("*.json")):
        try:
            asks.append(read_ask(path, k))
        except (OSError, ValueError, KeyError, TypeError):
            notes.append(f"run: question file {path.name} unreadable")
    by_index = [ask["case_id"] for ask in asks]
    rows = field(summary, "questions", list)
    agrees = [
        isinstance(row, dict)
        and row.get("case") == ask["case_id"]
        and all(rounded(num(row.get(name))) == ask[name] for name in WALLS)
        for row, ask in zip(rows, asks, strict=False)
    ]
    k14 = kept["k_override"] == "14"
    gate = {
        "launch": kept.get("code_sha") == CODE_SHA
        and kept.get("mode") == "retrieval"
        and kept.get("status") == "complete"
        and kept.get("variants") == {"cpu": 0}
        and kept.get("cases") == list(CASES)
        and kept.get("ollama_models_before") == []
        and kept.get("ollama_models_after") == []
        and k is not None
        and (k14 if k == 14 else kept["k_override"] in (None, "20")),
        "settings": k is not None and settings == {"retrieval_top_k": k, **SETTINGS},
        "drivers": drivers == DRIVERS_SHA256,
        "asks": by_index == list(CASES)
        and [ask["index"] for ask in asks] == list(range(1, len(CASES) + 1))
        and all(ask["read"] for ask in asks),
        "summary": len(rows) == len(asks) == len(CASES) and all(agrees),
    }
    gate["passed"] = all(gate.values())
    return {
        "label": an_id(label),
        "k": k,
        "launch": kept,
        "settings": settings,
        "drivers_sha256": drivers,
        "sha256": {
            name: sha256(run_dir / name)
            for name in ("launch.json", "effective_settings.json", "retrieval-cpu.json")
        },
        "retriever_build_sec": rounded(num(summary.get("retriever_build_sec"))),
        "asks": asks,
        "gate": gate,
        "notes": notes,
    }


def sign_p(wins: int, losses: int) -> float:
    """The exact two-sided sign test at one half."""
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(wins, losses) + 1)) / 2**n
    return min(1.0, 2 * tail)


def pair_up(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each paired question's asks at each K, from runs whose gates passed."""
    pairs = []
    for position, case_id in enumerate(CASES, start=1):
        if case_id not in PAIRED:
            continue
        sides: dict[int, list[dict[str, Any]]] = {14: [], 20: []}
        why = []
        for run in runs:
            ask = next((a for a in run["asks"] if a["case_id"] == case_id), None)
            if ask is None or run["k"] not in sides:
                continue
            if not run["gate"]["passed"]:
                why.append(f"{run['label']}: its gate failed")
            elif ask["index"] != position:
                why.append(f"{run['label']}: at position {ask['index']}, not {position}")
            else:
                sides[run["k"]].append(ask)
        for k, asks in sides.items():
            if len(asks) != 2:
                why.append(f"{len(asks)} read asks at K = {k}, not two")
        pair: dict[str, Any] = {"case_id": case_id, "position": position}
        for k, asks in sides.items():
            for name in WALLS:
                pair[f"k{k}_{name}"] = [ask[name] for ask in asks]
            pair[f"k{k}_pool"] = sorted({ask["pool"] for ask in asks})
            pair[f"k{k}_same_pool"] = len({ask["pool_sha256"] for ask in asks}) == 1
            pair[f"k{k}_same_five"] = len({ask["ranked_sha256"] for ask in asks}) == 1
        pair["k_curve_candidates"] = list(K_CURVE_CANDIDATES[case_id])
        pair["readable"] = not why
        pair["why"] = why
        if not why:
            for name in WALLS:
                k20 = statistics.fmean(pair[f"k20_{name}"])
                k14 = statistics.fmean(pair[f"k14_{name}"])
                pair[f"{name}_saving_sec"] = rounded(k20 - k14)
                pair[f"{name}_ratio"] = rounded(k14 / k20 if k20 else None)
        pairs.append(pair)
    return pairs


def spread(pairs: list[dict[str, Any]], k: int) -> float | None:
    """The same K's two asks, apart: the median of |a - b| over their mean, rerank seconds."""
    values = []
    for pair in pairs:
        a, b = pair[f"k{k}_rerank"]
        if a + b:
            values.append(abs(a - b) / ((a + b) / 2))
    return median(values)


def readings(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    """The spec's answer and what stands beside it, from the readable pairs alone."""
    readable = [pair for pair in pairs if pair["readable"]]
    savings = [pair["rerank_saving_sec"] for pair in readable]
    wins = sum(1 for value in savings if value > 0)
    losses = sum(1 for value in savings if value < 0)
    p = sign_p(wins, losses)
    if len(readable) < MIN_QUESTIONS:
        answer = NOT_EVIDENCE
    elif wins > losses and p < ALPHA:
        answer = "faster"
    elif losses > wins and p < ALPHA:
        answer = "slower"
    else:
        answer = "no detected difference"
    return {
        "answer": answer,
        "readable_questions": len(readable),
        "k14_faster": wins,
        "k14_slower": losses,
        "sign_p": round(p, 6),
        "median_rerank_saving_sec": median(savings),
        "median_rerank_ratio": median([pair["rerank_ratio"] for pair in readable]),
        "printed_deciding_nothing": {
            "median_retrieval_saving_sec": median(
                [pair["retrieval_saving_sec"] for pair in readable]
            ),
            "median_vector_saving_sec": median([pair["vector_saving_sec"] for pair in readable]),
            "median_rerank_sec": {
                f"k{k}": median([v for pair in readable for v in pair[f"k{k}_rerank"]])
                for k in (20, 14)
            },
            "same_k_spread": {f"k{k}": spread(readable, k) for k in (20, 14)},
            "same_pool_both_asks": {
                f"k{k}": sum(1 for pair in readable if pair[f"k{k}_same_pool"]) for k in (20, 14)
            },
            "same_five_both_asks": {
                f"k{k}": sum(1 for pair in readable if pair[f"k{k}_same_five"]) for k in (20, 14)
            },
            "pools_as_k_curve": {
                f"k{k}": sum(
                    1
                    for pair in readable
                    if pair[f"k{k}_pool"] == [pair["k_curve_candidates"][0 if k == 14 else 1]]
                )
                for k in (20, 14)
            },
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("runs", type=Path, nargs="+")
    args = parser.parse_args(argv)
    if args.out.exists():
        print(f"refused: {args.out} exists", file=sys.stderr)
        return 2
    # A rerun stands in its run's place, never beside it.
    names = [run.name.removesuffix("-r2") for run in args.runs]
    if len(set(names)) != len(names):
        print("refused: a run named twice, or beside its rerun", file=sys.stderr)
        return 2
    runs = [read_run(run) for run in args.runs]
    pairs = pair_up(runs)
    record = {
        "schema": SCHEMA,
        "spec": SPEC,
        "tools_sha256": {"step3_reader.py": sha256(HERE / "step3_reader.py")},
        "runs": runs,
        "pairs": pairs,
        "readings": readings(pairs),
    }
    text = json.dumps(record, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    args.out.write_bytes(text.encode("utf-8"))
    print(json.dumps(record["readings"], sort_keys=True))
    print(json.dumps({"gates": {run["label"]: run["gate"] for run in runs}}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

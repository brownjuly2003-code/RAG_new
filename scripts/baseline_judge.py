"""Regrade production-baseline contexts with two blind judges.

    python -m scripts.baseline_judge plan --run <baseline run> --out <judge dir>
    python -m scripts.baseline_judge judge --out <judge dir> --judge glm|sonnet [--limit N]
    python -m scripts.baseline_judge consensus --out <judge dir>

plan reads a finished production-baseline run and writes plan.json. For each
case it takes the union of the top five reranked seeds and the sent documents,
deduplicated by text_sha256. A text without a chunk address is not sent and is
unjudged with its address reason. Cases excluded in collection are listed and
not judged.

The split rule, stated exactly as SPLIT_RULE: "addressed texts sorted by
text_sha256, cut into ceil(n / 10) consecutive parts whose sizes differ by at
most one, larger parts first; a single part keeps the case id, parts of a split
case are <case_id>#<k> with k from 1".

judge sends the planned requests through run_judge_v2 with the store
<judge dir>/<judge>.jsonl. Endpoint and credentials come from the environment:
RAG_JUDGE_GK_BASE, required for Sonnet; RAG_JUDGE_GLM_SETTINGS, optional for
GLM. Neither is printed. Only the prompt leaves the machine.

consensus applies evaluation.judge_consensus and writes ruler-input.json. No
quality number is computed here.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from evaluation.blinded_judge import read_store
from evaluation.blinded_judge_clients import GlmClient, SonnetClient
from evaluation.judge_consensus import consensus_v2, ruler_cases, store_grades
from evaluation.judge_contract import build_request_v2
from scripts import production_baseline as baseline
from scripts import production_parity as parity
from scripts.relevance_judge_v2 import judge_version, run_judge_v2

JUDGES = ("glm", "sonnet")
MAX_DOCUMENTS = 10
PLAN_VERSION = 1
PLAN_JUDGE_VERSION = "plan"
SPLIT_RULE = (
    "addressed texts sorted by text_sha256, cut into ceil(n / 10) consecutive parts whose "
    "sizes differ by at most one, larger parts first; a single part keeps the case id, "
    "parts of a split case are <case_id>#<k> with k from 1"
)


def load_baseline(run: Path) -> tuple[str, list[tuple[dict, dict]]]:
    """Verify the run is finished and return its identity with each case and grade row."""
    manifest = baseline.load_manifest(run)
    identity = parity.digest(manifest)
    baseline.require_no_aborts(run, baseline.STAGES)
    parity.load_stage(run / "report.json", identity)
    return identity, [
        (case, baseline.load_case(run / "grade" / f"{case['case_id']}.json", identity, run))
        for case in manifest["cases"]
    ]


def split_documents(
    case_id: str, documents: Sequence[Mapping[str, Any]]
) -> list[tuple[str, list[dict]]]:
    """Apply SPLIT_RULE, so the parts and their order never depend on the input order."""
    ordered = sorted(
        (dict(document) for document in documents), key=lambda document: document["text_sha256"]
    )
    hashes = [document["text_sha256"] for document in ordered]
    if len(set(hashes)) != len(hashes):
        raise ValueError("documents must have unique text_sha256")
    if not ordered:
        return []
    parts = (len(ordered) + MAX_DOCUMENTS - 1) // MAX_DOCUMENTS
    base, extra = divmod(len(ordered), parts)
    pairs: list[tuple[str, list[dict]]] = []
    start = 0
    for index in range(parts):
        size = base + 1 if index < extra else base
        request_id = case_id if parts == 1 else f"{case_id}#{index + 1}"
        pairs.append((request_id, ordered[start : start + size]))
        start += size
    return pairs


def case_plan(case: Mapping[str, Any], row: Mapping[str, Any]) -> tuple[dict, list[dict]]:
    """Plan one case: the addressed union of top seeds and sent texts, split by SPLIT_RULE."""
    walked = list(row["seed_documents"][:5]) + list(row["documents"])
    seeds = [document["text_sha256"] for document in row["seed_documents"][:5]]
    sent = [document["text_sha256"] for document in row["documents"]]
    addressed: dict[str, dict[str, Any]] = {}
    first_reason: dict[str, str] = {}
    for document in walked:
        text_sha256 = document["text_sha256"]
        if text_sha256 not in first_reason:
            first_reason[text_sha256] = document.get("address_reason") or "address_unresolved"
        address = document.get("chunk_address")
        if address is not None and text_sha256 not in addressed:
            addressed[text_sha256] = {
                "text": document["text"],
                "text_sha256": text_sha256,
                "address": dict(address),
            }
    unaddressed = {
        text_sha256: first_reason[text_sha256]
        for text_sha256 in dict.fromkeys(seeds + sent)
        if text_sha256 not in addressed
    }
    requests: list[dict[str, Any]] = []
    for request_id, documents in split_documents(case["case_id"], list(addressed.values())):
        built = build_request_v2(
            case_id=request_id,
            question=case["query"],
            documents=documents,
            judge_version=PLAN_JUDGE_VERSION,
        )
        requests.append(
            {
                "case_id": request_id,
                "baseline_case_id": case["case_id"],
                "question": case["query"],
                "documents": documents,
                "request_sha256": built.request_sha256,
                "prompt_characters": len(built.text),
            }
        )
    entry = {
        "case_id": case["case_id"],
        "subset": case["subset"],
        "seeds": seeds,
        "sent": sent,
        "unaddressed": unaddressed,
        "requests": [request["case_id"] for request in requests],
    }
    return entry, requests


def build_plan(run: Path) -> dict:
    """Read one finished baseline run and derive the whole judge plan from its grade rows."""
    identity, pairs = load_baseline(run)
    collection_excluded: list[str] = []
    cases: list[dict[str, Any]] = []
    requests: list[dict[str, Any]] = []
    for case, row in pairs:
        if row.get("status") != "ok":
            collection_excluded.append(case["case_id"])
            continue
        entry, case_requests = case_plan(case, row)
        cases.append(entry)
        requests.extend(case_requests)
    return {
        "plan_version": PLAN_VERSION,
        "run_sha256": identity,
        "baseline_report_sha256": parity.file_sha(run / "report.json"),
        "split_rule": SPLIT_RULE,
        "collection_excluded": collection_excluded,
        "cases": cases,
        "requests": requests,
    }


def write_plan(out: Path, plan: dict) -> None:
    """Write plan.json once; an equal plan already present is accepted, a different one is not."""
    path = out / "plan.json"
    if path.exists():
        try:
            same = parity.read(path) == plan
        except (OSError, ValueError):
            same = False
        if same:
            return
        raise FileExistsError("A different plan exists in this directory")
    parity.write_new(path, plan)


def load_plan(out: Path) -> dict:
    """Read plan.json and refuse any plan whose shape or recorded hashes no longer rebuild."""
    plan = parity.read(out / "plan.json")
    if plan.get("plan_version") != PLAN_VERSION:
        raise ValueError("plan_version is not supported")
    planned_cases = {case["case_id"] for case in plan["cases"]}
    request_ids: set[str] = set()
    for request in plan["requests"]:
        request_id = request["case_id"]
        if request_id in request_ids:
            raise ValueError(f"duplicate request id: {request_id}")
        request_ids.add(request_id)
        if request["baseline_case_id"] not in planned_cases:
            raise ValueError(f"request {request_id} is outside the planned cases")
        built = build_request_v2(
            case_id=request_id,
            question=request["question"],
            documents=request["documents"],
            judge_version=PLAN_JUDGE_VERSION,
        )
        if built.request_sha256 != request["request_sha256"]:
            raise ValueError(f"request_sha256 does not rebuild: {request_id}")
        if len(built.text) != request["prompt_characters"]:
            raise ValueError(f"prompt_characters does not rebuild: {request_id}")
    listed = sorted(request_id for case in plan["cases"] for request_id in case["requests"])
    if listed != sorted(request_ids):
        raise ValueError("case request lists disagree with the request rows")
    return plan


def outbound(rows: Iterable[Mapping[str, Any]], plan: Mapping[str, Any]) -> dict[str, int]:
    """Upper-bound what left the machine: every non-rebind v2 attempt is one prompt."""
    by_request = {
        (request["case_id"], request["request_sha256"]): request for request in plan["requests"]
    }
    calls = texts = characters = 0
    for row in rows:
        if row.get("request_version") != 2 or row.get("reused"):
            continue
        request = by_request.get((row.get("case_id"), row.get("request_sha256")))
        if request is None:
            raise ValueError("reply store holds an attempt outside the plan")
        calls += 1
        texts += len(request["documents"])
        characters += request["prompt_characters"]
    return {"calls": calls, "texts": texts, "characters": characters}


def make_client(judge: str) -> Any:
    """Build the named judge client from the environment without echoing any secret."""
    if judge == "sonnet":
        base = os.environ.get("RAG_JUDGE_GK_BASE", "").strip()
        if not base:
            raise ValueError("RAG_JUDGE_GK_BASE is required for the Sonnet judge")
        return SonnetClient(base)
    if judge == "glm":
        settings = os.environ.get("RAG_JUDGE_GLM_SETTINGS", "").strip()
        return GlmClient(Path(settings) if settings else None)
    raise ValueError(f"unknown judge: {judge}")


def judge(out: Path, name: str, *, limit: int | None = None, client: Any = None) -> dict:
    """Send the planned requests through one judge and report outcomes and outbound totals."""
    if name not in JUDGES:
        raise ValueError(f"unknown judge: {name}")
    plan = load_plan(out)
    if client is None:
        client = make_client(name)
    endpoint = None
    if name == "sonnet":
        endpoint = os.environ.get("RAG_JUDGE_GK_BASE", "").strip() or None
    version = judge_version(name, client, endpoint)
    store = out / f"{name}.jsonl"
    for row in read_store(store):
        if row.get("request_version") == 2 and row.get("judge_version") != version:
            raise ValueError(
                "the store holds attempts of another judge version; use a new judge directory"
            )
    result = run_judge_v2(client, plan["requests"], store, judge_version=version, limit=limit)
    return {"judge": name, **result, "outbound": outbound(read_store(store), plan)}


def consensus(out: Path, judges: Sequence[str] = JUDGES) -> dict:
    """Compute the judges' consensus and write ruler-input.json when evidence exists."""
    plan = load_plan(out)
    planned = {request["case_id"]: request["request_sha256"] for request in plan["requests"]}
    owner: dict[tuple[str, str], tuple[str, str]] = {}
    for request in plan["requests"]:
        for document in request["documents"]:
            owner[(request["case_id"], document["text_sha256"])] = (
                request["baseline_case_id"],
                document["text_sha256"],
            )
    units = list(owner.values())
    grades_by_judge: dict[str, dict[tuple[str, str], int]] = {}
    stores: dict[str, str | None] = {}
    judge_versions: dict[str, str | None] = {}
    outbound_totals: dict[str, dict[str, int]] = {}
    for name in judges:
        store_path = out / f"{name}.jsonl"
        rows = read_store(store_path)
        grades, version = store_grades(rows, planned)
        mapped: dict[tuple[str, str], int] = {}
        for key, grade in grades.items():
            if key not in owner:
                raise ValueError("grade for a text outside its request")
            mapped[owner[key]] = grade
        grades_by_judge[name] = mapped
        judge_versions[name] = version
        stores[name] = parity.file_sha(store_path) if store_path.is_file() else None
        outbound_totals[name] = outbound(rows, plan)
    result = consensus_v2(units, grades_by_judge)
    unjudged = dict(result.unjudged)
    for case in plan["cases"]:
        for text_sha256, reason in case["unaddressed"].items():
            unjudged[(case["case_id"], text_sha256)] = reason
    unjudged_counts: dict[str, int] = {}
    for reason in unjudged.values():
        unjudged_counts[reason] = unjudged_counts.get(reason, 0) + 1
    grade_counts: dict[str, int] = {}
    for included in result.graded_by.values():
        count = str(len(included))
        grade_counts[count] = grade_counts.get(count, 0) + 1
    summary: dict[str, Any] = {
        "status": "ok" if result.grades else "NOT_EVIDENCE",
        "run_sha256": plan["run_sha256"],
        "plan_sha256": parity.file_sha(out / "plan.json"),
        "stores": stores,
        "judge_versions": judge_versions,
        "included_judges": list(result.included),
        "excluded_judges": result.excluded,
        "missing": result.missing,
        "units": len(units),
        "unjudged_units": {reason: unjudged_counts[reason] for reason in sorted(unjudged_counts)},
        "units_by_grade_count": grade_counts,
        "collection_excluded": plan["collection_excluded"],
        "outbound": outbound_totals,
        "quality_metrics": "N/A: not computed here; ruler-input.json is their input",
    }
    ruler = ruler_cases(plan["cases"], result.grades, unjudged)
    summary["judged_precision_cases"] = len(ruler["cases"])
    summary["judged_precision_excluded"] = ruler["excluded_count"]
    summary["excluded_by_subset"] = ruler["excluded_by_subset"]
    summary["kept_by_subset"] = ruler["kept_by_subset"]
    summary["repeated_sent_texts"] = ruler["repeated_sent_texts"]
    if summary["status"] != "ok":
        return summary
    payload = json.dumps({**summary, "ruler": ruler}, ensure_ascii=False, indent=2)
    (out / "ruler-input.json").write_text(payload + "\n", encoding="utf-8", newline="\n")
    return summary


def main(argv: list[str] | None = None) -> int:
    """Run plan, judge or consensus and return the process exit status."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    plan_command = commands.add_parser("plan")
    plan_command.add_argument("--run", type=Path, required=True)
    plan_command.add_argument("--out", type=Path, required=True)
    judge_command = commands.add_parser("judge")
    judge_command.add_argument("--out", type=Path, required=True)
    judge_command.add_argument("--judge", choices=JUDGES, required=True)
    judge_command.add_argument("--limit", type=int)
    consensus_command = commands.add_parser("consensus")
    consensus_command.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args(argv)
    if arguments.command == "plan":
        plan = build_plan(arguments.run)
        write_plan(arguments.out, plan)
        print(
            json.dumps(
                {
                    "cases": len(plan["cases"]),
                    "requests": len(plan["requests"]),
                    "collection_excluded": len(plan["collection_excluded"]),
                    "unaddressed": sum(len(case["unaddressed"]) for case in plan["cases"]),
                },
                ensure_ascii=False,
            )
        )
        return 0
    if arguments.command == "judge":
        base = os.environ.get("RAG_JUDGE_GK_BASE", "").strip()
        if arguments.judge == "sonnet" and not base:
            parser.error("RAG_JUDGE_GK_BASE is required for the Sonnet judge")
        result = judge(arguments.out, arguments.judge, limit=arguments.limit)
        print(json.dumps(result, ensure_ascii=False))
        return 1 if result["invalid"] or result["absent"] or result["pending"] else 0
    summary = consensus(arguments.out)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

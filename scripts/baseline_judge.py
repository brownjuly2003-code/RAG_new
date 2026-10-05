"""Regrade production-baseline contexts with the registered blind judge.

    python -m scripts.baseline_judge plan --run <baseline run> --out <judge dir>
    python -m scripts.baseline_judge judge --out <judge dir> --judge opus [--limit N] [--retest]
    python -m scripts.baseline_judge consensus --out <judge dir>
    python -m scripts.baseline_judge retest --out <judge dir> --judge opus

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
<judge dir>/<judge>.jsonl. The registered judge of new texts is one model,
claude-opus-5-5 through the Claude Code CLI, with the arguments of the P2 Opus
reference collection (metrics spec, «Judge of new texts»; plan decision D12);
the tool holds no route to any other model. The CLI may be named in
RAG_JUDGE_CLAUDE_CLI; it is not printed or stored. Only the prompt leaves the
machine.

judge --retest sends the stability sub-sample a second time, into
<judge dir>/<judge>-retest.jsonl. The sub-sample, stated exactly as
RETEST_RULE: "per subset, the planned cases that have a request, sorted by the
SHA-256 of '20260925:retest:<case_id>', the first 10; every request of a drawn
case is sent again as <request id>~retest into a store of its own".

Every judge invocation appends one line to <judge dir>/runs.jsonl: the store it
wrote to, when it started and finished, its counts and the version the CLI
reported.

consensus applies evaluation.judge_consensus and writes ruler-input.json; with
one judge the grade is that judge's and the summary says single_judge. retest
compares the two passes of the sub-sample and writes <judge>-retest.json. No
retrieval-quality number is computed here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from evaluation.blinded_judge import BOOTSTRAP_SAMPLES, SEED, read_store
from evaluation.blinded_judge_clients import JudgeUnavailable, Reply
from evaluation.judge_consensus import (
    MISSING_SHARE_LIMIT,
    consensus_v2,
    retest_stability,
    ruler_cases,
    store_grades,
)
from evaluation.judge_contract import build_request_v2
from scripts import p2_opus_reference as reference
from scripts import production_baseline as baseline
from scripts import production_parity as parity
from scripts.relevance_judge_v2 import judge_version, run_judge_v2

JUDGES = ("opus",)
MAX_DOCUMENTS = 10
PLAN_VERSION = 1
PLAN_JUDGE_VERSION = "plan"
SPLIT_RULE = (
    "addressed texts sorted by text_sha256, cut into ceil(n / 10) consecutive parts whose "
    "sizes differ by at most one, larger parts first; a single part keeps the case id, "
    "parts of a split case are <case_id>#<k> with k from 1"
)
RETEST_SUFFIX = "~retest"
RETEST_CASES = 10
RETEST_THRESHOLD = 0.7
RETEST_RULE = (
    "per subset, the planned cases that have a request, sorted by the SHA-256 of "
    f"'{SEED}:retest:<case_id>', the first {RETEST_CASES}; every request of a drawn case is "
    f"sent again as <request id>{RETEST_SUFFIX} into a store of its own"
)
CLI_TIMEOUT_S = 1200.0
RUN_LOG = "runs.jsonl"
USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "total_cost_usd",
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


class OpusCliClient:
    """The judge of new texts: one `claude -p` process per request, no tools, no stored session.

    The arguments are those of the P2 Opus reference collection, so the judge is the grader
    whose agreement with the registered consensus was measured on the P2 sample.
    """

    model = reference.MODEL
    route = "Claude Code CLI, first-party provider"
    arguments = reference.CLI_ARGS
    parameters: ClassVar[dict[str, Any]] = {
        "model": reference.MODEL,
        "effort": "max",
        "tools": "none",
        "system_prompt_sha256": hashlib.sha256(reference.SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
    }

    def __init__(self, executable: str | None = None, timeout_s: float = CLI_TIMEOUT_S) -> None:
        self.executable = executable
        self.timeout_s = timeout_s

    def grade(self, request_text: str) -> Reply:
        executable = self.executable or shutil.which("claude.cmd") or shutil.which("claude")
        if executable is None:
            raise JudgeUnavailable("cli_missing", "Claude CLI is not installed")
        start = time.monotonic()
        try:
            process = subprocess.run(
                [executable, *self.arguments],
                input=request_text,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=tempfile.gettempdir(),
                timeout=self.timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise JudgeUnavailable("cli_timeout", "Claude CLI request timed out") from None
        except OSError:
            raise JudgeUnavailable("cli_missing", "Claude CLI did not start") from None
        if process.returncode != 0:
            raise JudgeUnavailable("cli_exit", f"Claude CLI exited with {process.returncode}")
        try:
            envelope = reference.parse_cli_envelope(process.stdout)
        except ValueError as exc:
            raise JudgeUnavailable("cli_response", str(exc)) from None
        usage = {
            field: envelope["usage"][field]
            for field in USAGE_FIELDS
            if type(envelope["usage"].get(field)) in (int, float)
        }
        return Reply(envelope["result"], envelope["model"], usage, time.monotonic() - start)

    def describe(self) -> dict[str, str]:
        """Name the CLI build that serves the requests; the path of the executable stays out."""
        executable = self.executable or shutil.which("claude.cmd") or shutil.which("claude")
        if executable is None:
            return {"cli_version": "N/A: Claude CLI is not installed"}
        try:
            process = subprocess.run(
                [executable, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=tempfile.gettempdir(),
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return {"cli_version": "N/A: Claude CLI did not report a version"}
        lines = process.stdout.strip().splitlines()
        if process.returncode != 0 or not lines:
            return {"cli_version": "N/A: Claude CLI did not report a version"}
        return {"cli_version": lines[0].strip()}


def make_client(judge: str) -> Any:
    """Build the client of a registered judge; a route exists for no other model."""
    if judge == "opus" and judge in JUDGES:
        return OpusCliClient(os.environ.get("RAG_JUDGE_CLAUDE_CLI", "").strip() or None)
    raise ValueError(f"no route is registered for the judge {judge}")


def retest_cases(plan: Mapping[str, Any]) -> list[str]:
    """Draw the stability sub-sample by RETEST_RULE: from the plan alone, so no grade moves it."""
    by_subset: dict[str, list[str]] = {}
    for case in plan["cases"]:
        if case["requests"]:
            by_subset.setdefault(case["subset"], []).append(case["case_id"])
    drawn: list[str] = []
    for subset in sorted(by_subset):
        ordered = sorted(
            by_subset[subset],
            key=lambda case_id: hashlib.sha256(
                f"{SEED}:retest:{case_id}".encode("utf-8")
            ).hexdigest(),
        )
        drawn.extend(ordered[:RETEST_CASES])
    return drawn


def retest_requests(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Give every request of a drawn case its retest id, which also gives it another blind order."""
    drawn = set(retest_cases(plan))
    requests: list[dict[str, Any]] = []
    for request in plan["requests"]:
        if request["baseline_case_id"] not in drawn:
            continue
        request_id = request["case_id"] + RETEST_SUFFIX
        built = build_request_v2(
            case_id=request_id,
            question=request["question"],
            documents=request["documents"],
            judge_version=PLAN_JUDGE_VERSION,
        )
        requests.append(
            {
                **request,
                "case_id": request_id,
                "request_sha256": built.request_sha256,
                "prompt_characters": len(built.text),
            }
        )
    return requests


def judge(
    out: Path,
    name: str,
    *,
    limit: int | None = None,
    client: Any = None,
    retest: bool = False,
) -> dict:
    """Send one pass of the planned requests through one judge; report outcomes and outbound."""
    if name not in JUDGES:
        raise ValueError(f"unknown judge: {name}")
    plan = load_plan(out)
    if client is None:
        client = make_client(name)
    version = judge_version(name, client)
    requests = retest_requests(plan) if retest else plan["requests"]
    store = out / (f"{name}-retest.jsonl" if retest else f"{name}.jsonl")
    for row in read_store(store):
        if row.get("request_version") == 2 and row.get("judge_version") != version:
            raise ValueError(
                "the store holds attempts of another judge version; use a new judge directory"
            )
    describe = getattr(client, "describe", None)
    environment = describe() if callable(describe) else {}
    started = datetime.now(UTC).isoformat(timespec="seconds")
    result = run_judge_v2(client, requests, store, judge_version=version, limit=limit)
    with (out / RUN_LOG).open("a", encoding="utf-8", newline="\n") as handle:
        row = {
            "judge": name,
            "store": store.name,
            "started": started,
            "finished": datetime.now(UTC).isoformat(timespec="seconds"),
            "environment": environment,
            **result,
        }
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    summary = {
        "judge": name,
        **result,
        "outbound": outbound(read_store(store), {"requests": requests}),
    }
    if retest:
        summary["retest"] = True
    return summary


def retest(out: Path, name: str) -> dict:
    """Compare the two passes of the stability sub-sample and write <judge>-retest.json."""
    if name not in JUDGES:
        raise ValueError(f"unknown judge: {name}")
    plan = load_plan(out)
    subsets = {case["case_id"]: case["subset"] for case in plan["cases"]}
    second_requests = retest_requests(plan)
    first_path, second_path = out / f"{name}.jsonl", out / f"{name}-retest.jsonl"
    first_rows, second_rows = read_store(first_path), read_store(second_path)
    first, first_version = store_grades(
        first_rows, {request["case_id"]: request["request_sha256"] for request in plan["requests"]}
    )
    second, second_version = store_grades(
        second_rows, {request["case_id"]: request["request_sha256"] for request in second_requests}
    )
    if first_version and second_version and first_version != second_version:
        raise ValueError("the two passes were graded under different judge versions")
    pairs: dict[str, list[tuple[int, int]]] = {}
    units = 0
    missing = {"first": 0, "second": 0}
    for request in second_requests:
        original = request["case_id"][: -len(RETEST_SUFFIX)]
        for document in request["documents"]:
            units += 1
            before = first.get((original, document["text_sha256"]))
            after = second.get((request["case_id"], document["text_sha256"]))
            missing["first"] += before is None
            missing["second"] += after is None
            if before is not None and after is not None:
                pairs.setdefault(request["baseline_case_id"], []).append((before, after))
    overall = retest_stability(pairs)
    complete = bool(units) and max(missing.values()) / units <= MISSING_SHARE_LIMIT
    interval = overall["ci95"]
    if not complete or interval is None:
        verdict = "NOT_EVIDENCE"
    elif interval[0] >= RETEST_THRESHOLD:
        verdict = "single_judge"
    else:
        verdict = "provisional_ruler"
    report: dict[str, Any] = {
        "status": "NOT_EVIDENCE" if verdict == "NOT_EVIDENCE" else "ok",
        "verdict": verdict,
        "judge": name,
        "judge_version": first_version or second_version,
        "run_sha256": plan["run_sha256"],
        "plan_sha256": parity.file_sha(out / "plan.json"),
        "rule": RETEST_RULE,
        "threshold": RETEST_THRESHOLD,
        "missing_share_limit": MISSING_SHARE_LIMIT,
        "bootstrap": {"seed": SEED, "resamples": BOOTSTRAP_SAMPLES, "cluster": "case"},
        "cases": retest_cases(plan),
        "requests": len(second_requests),
        "units": units,
        "missing": missing,
        "stores": {
            "first": parity.file_sha(first_path) if first_path.is_file() else None,
            "second": parity.file_sha(second_path) if second_path.is_file() else None,
        },
        "all": overall,
        "by_subset": {
            subset: retest_stability(
                {case_id: rows for case_id, rows in pairs.items() if subsets[case_id] == subset}
            )
            for subset in sorted({subsets[case_id] for case_id in retest_cases(plan)})
        },
        "outbound": outbound(second_rows, {"requests": second_requests}),
        "quality_metrics": "N/A: agreement of one judge with itself, not a retrieval metric",
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    (out / f"{name}-retest.json").write_text(payload + "\n", encoding="utf-8", newline="\n")
    return report


def consensus(out: Path, judges: Sequence[str] | None = None) -> dict:
    """Compute the judges' consensus and write ruler-input.json when evidence exists."""
    judges = JUDGES if judges is None else judges
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
        "grade_source": {0: None, 1: "single_judge"}.get(len(result.included), "consensus"),
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
    """Run plan, judge, consensus or retest and return the process exit status."""
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
    judge_command.add_argument("--retest", action="store_true")
    consensus_command = commands.add_parser("consensus")
    consensus_command.add_argument("--out", type=Path, required=True)
    retest_command = commands.add_parser("retest")
    retest_command.add_argument("--out", type=Path, required=True)
    retest_command.add_argument("--judge", choices=JUDGES, required=True)
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
                    "retest_cases": len(retest_cases(plan)),
                    "retest_requests": len(retest_requests(plan)),
                },
                ensure_ascii=False,
            )
        )
        return 0
    if arguments.command == "judge":
        result = judge(
            arguments.out, arguments.judge, limit=arguments.limit, retest=arguments.retest
        )
        print(json.dumps(result, ensure_ascii=False))
        return 1 if result["invalid"] or result["absent"] or result["pending"] else 0
    if arguments.command == "retest":
        report = retest(arguments.out, arguments.judge)
        print(
            json.dumps(
                {field: report[field] for field in ("status", "verdict", "units", "missing")}
                | {field: report["all"][field] for field in ("quadratic_kappa", "ci95")},
                ensure_ascii=False,
            )
        )
        return 0 if report["status"] == "ok" else 1
    summary = consensus(arguments.out)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

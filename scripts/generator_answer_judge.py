#!/usr/bin/env python3
"""Grade C.1 generator answers with the one judge, blind to the generator.

Plan decision D12 leaves one judge, the session's model, asked in stateless requests by the
registered route (`evaluation.isolated_request`). The generator benchmark's own LLM judge is the
generator grading itself, so the screening of generators below 7B
(`docs/specs/small-generator-screening.md`) grades answers here instead:

- `plan` takes the seed-42 run of each benchmark report, checks that every report sent the same
  prompt over the same dataset and cached contexts, counts the deterministic defects of all its
  answers, and writes one request per answer of the 30 registered cases (`--sample-size 100`
  for the extension to all of them), plus a retest of 15 of them, in a fixed shuffled order; a
  request never names the generator, and an empty answer is graded bad without one;
- `reuse` copies, before the first request, the verdicts an earlier plan of the same route and
  rules got for byte-identical requests, each marked with that plan's SHA-256;
- `run` sends the requests one at a time and appends every reply to `verdicts.jsonl`, so a
  stopped run resumes where it stopped; it stops at the first reply the route refuses;
- `summary` counts the verdicts per generator; a verdict counts only with the record of a clean
  session and the hash of its planned request.

Usage:
  python scripts/generator_answer_judge.py plan --report NAME=PATH ... --out DIR [--sample-size N]
  python scripts/generator_answer_judge.py reuse --from EARLIER_DIR --out DIR
  python scripts/generator_answer_judge.py run --out DIR [--limit N]
  python scripts/generator_answer_judge.py summary --out DIR
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation import isolated_request as isolated  # noqa: E402
from evaluation.blinded_judge_clients import JudgeUnavailable  # noqa: E402
from evaluation.ragas_eval import context_recall  # noqa: E402
from scripts.generator_benchmark import (  # noqa: E402
    DEFAULT_CONTEXTS,
    DEFAULT_DATASET,
    PROMPT_VERSION,
    load_benchmark_cases,
)

PROTOCOL = "docs/specs/small-generator-screening.md"
SALT = "small-generator-screening-2026-10-14"
SAMPLE_SIZE = 30
RETEST_SIZE = 15
SEED = 42
EXPECTED_CASES = 100
CONTEXT_CHARS = 6000
FORM_ATTEMPTS = 3
CLI_TIMEOUT_S = 1200.0
ANSWERS = ("full", "partial", "declined", "no")
DEFECTS = (
    "none",
    "empty",
    "citation_only",
    "wrong_language",
    "copied_context",
    "cut_off",
    "repetition",
    "other",
)
KEYS = (
    "claims_total",
    "claims_supported",
    "context_has_answer",
    "answers_question",
    "defect",
    "note",
)
CLASSES = ("good", "partial_ok", "bad")
USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "total_cost_usd",
)
CYRILLIC = re.compile(r"[А-Яа-яЁё]")
CITATION = re.compile(r"\[\d+(?:\s*,\s*\d+)*\]")
WORD = re.compile(r"\w")

# One line: the route refuses a system prompt with a newline, a quote or a shell character.
SYSTEM_PROMPT = (
    "You grade one answer of a retrieval-augmented support assistant against the context it "
    "was given. Follow the grading rules of the request and reply with one JSON object only."
)
INSTRUCTIONS = """You grade one answer written by a support assistant of an air-cargo company. \
The assistant was told to answer the user's question strictly from the context below, briefly \
and in Russian, and to say that the information is insufficient when the context does not \
contain the answer. You see the same context the assistant saw.

Grade the answer against this context only. Do not use outside knowledge to decide whether a \
claim is true.

1. claims_total: the number of material claims in the answer - statements of a fact, rule, \
number, deadline, condition, procedure step or recommendation. Restating the question, a \
greeting, a reference mark such as [1] or a statement that the information is insufficient is \
not a claim.
2. claims_supported: how many of those claims the context states or directly implies. A claim \
that adds a detail the context does not give (a number, a deadline, a condition, a name) is not \
supported.
3. context_has_answer: true if the context contains what is needed to answer the question, at \
least in part; otherwise false.
4. answers_question: "full" if the answer gives everything the context offers that the question \
asks for; "partial" if it gives some of it and misses a part the question asks for; "declined" \
if it says the information is insufficient and gives no answer; "no" if it does not address the \
question (off topic, or only copies or cites the context).
5. defect: "none", or the first of these that applies: "empty" (no text), "citation_only" (only \
reference marks such as [1]), "wrong_language" (not in Russian), "copied_context" (mostly copies \
the context instead of answering), "cut_off" (ends in the middle of a sentence), "repetition" \
(repeats the same text), "other".

Reply with one JSON object and nothing else:
{"claims_total": <integer>, "claims_supported": <integer>, "context_has_answer": <true or \
false>, "answers_question": "<full|partial|declined|no>", "defect": \
"<none|empty|citation_only|wrong_language|copied_context|cut_off|repetition|other>", \
"note": "<one short sentence>"}"""


class VerdictError(ValueError):
    """A reply that is not one verdict object of the registered form."""


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sample_case_ids(case_ids: Sequence[str], size: int = SAMPLE_SIZE) -> list[str]:
    """The registered cases: the first `size` by a salted hash, whatever the order given.

    A larger sample starts with the smaller one, so the extension to all 100 cases plans the
    registered 30 cases' requests unchanged.
    """
    return sorted(set(case_ids), key=lambda case_id: _digest(f"{SALT}:{case_id}"))[:size]


def build_message(question: str, contexts: Sequence[str], answer: str) -> str:
    """One request: the rules, then the question, the context and the answer; no generator."""
    context = "\n\n---\n\n".join(contexts)
    return f"{INSTRUCTIONS}\n\nQUESTION:\n{question}\n\nCONTEXT:\n{context}\n\nANSWER:\n{answer}\n"


def parse_verdict(text: str) -> dict[str, Any]:
    """Accept one JSON object of the registered form, optionally in one code fence."""
    body = text.strip()
    if body.startswith("```"):
        lines = body.splitlines()
        if len(lines) < 3 or lines[-1].strip() != "```":
            raise VerdictError("unclosed code fence")
        body = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise VerdictError(f"not one JSON object: {exc.msg}") from None
    if not isinstance(value, dict) or set(value) != set(KEYS):
        raise VerdictError("the object does not hold exactly the registered keys")
    for name in ("claims_total", "claims_supported"):
        number = value[name]
        if not isinstance(number, int) or isinstance(number, bool) or number < 0:
            raise VerdictError(f"{name} is not a non-negative integer")
    if value["claims_supported"] > value["claims_total"]:
        raise VerdictError("claims_supported exceeds claims_total")
    if not isinstance(value["context_has_answer"], bool):
        raise VerdictError("context_has_answer is not a boolean")
    if value["answers_question"] not in ANSWERS:
        raise VerdictError("answers_question is not a registered value")
    if value["defect"] not in DEFECTS:
        raise VerdictError("defect is not a registered value")
    if not isinstance(value["note"], str):
        raise VerdictError("note is not a string")
    return value


def classify(verdict: Mapping[str, Any]) -> str:
    """good: complete and fully supported, or a right decline; partial_ok: faithful but partial."""
    faithful = verdict["defect"] == "none" and (
        verdict["claims_supported"] == verdict["claims_total"]
    )
    answered = verdict["claims_total"] >= 1
    if faithful and verdict["answers_question"] == "full" and answered:
        return "good"
    if faithful and verdict["answers_question"] == "declined" and not verdict["context_has_answer"]:
        return "good"
    if faithful and verdict["answers_question"] == "partial" and answered:
        return "partial_ok"
    return "bad"


def _median(values: Sequence[float], digits: int) -> float | None:
    return round(statistics.median(values), digits) if values else None


def answer_checks(
    run: Mapping[str, Any], cases: Mapping[str, Mapping[str, Any]], config: Mapping[str, Any]
) -> dict[str, Any]:
    """What needs no judge, over every answer of the run: defects, keywords, speed."""
    rows = run["cases"]
    answers = [str(row.get("answer") or "").strip() for row in rows]
    recalls = [
        context_recall([answer], list(cases[str(row["case_id"])]["expected_keywords"]))
        for row, answer in zip(rows, answers, strict=True)
        if cases[str(row["case_id"])]["expected_keywords"]
    ]
    timings = [row.get("ollama_timing") or {} for row in rows]

    def rate(count: str, duration: str) -> float | None:
        values = [t[count] / t[duration] * 1e9 for t in timings if t.get(count) and t.get(duration)]
        return _median(values, 2)

    aggregate = run.get("aggregate") or {}
    return {
        "cases": len(rows),
        "generation_failed": sum(not row.get("generation_valid") for row in rows),
        "empty": sum(not answer for answer in answers),
        "no_cyrillic": sum(bool(answer) and not CYRILLIC.search(answer) for answer in answers),
        "citation_only": sum(
            bool(answer) and not WORD.search(CITATION.sub("", answer)) for answer in answers
        ),
        "answer_keyword_recall": round(statistics.fmean(recalls), 4) if recalls else None,
        "median_answer_chars": _median([len(answer) for answer in answers], 1),
        "nli_faithfulness": aggregate.get("nli_faithfulness"),
        "nli_supported_claim_rate": aggregate.get("nli_supported_claim_rate"),
        "median_latency_s": _median([float(row.get("latency_ms") or 0) / 1000 for row in rows], 1),
        "latency_includes_self_judging": bool(config.get("llm_judge", True)),
        "median_prompt_tokens_per_s": rate("prompt_eval_count", "prompt_eval_duration"),
        "median_output_tokens_per_s": rate("eval_count", "eval_duration"),
        "median_output_tokens": _median(
            [t["eval_count"] for t in timings if t.get("eval_count")], 1
        ),
    }


def _seed_run(
    report: Mapping[str, Any],
    name: str,
    cases: Mapping[str, Mapping[str, Any]],
    input_sha256: tuple[str, str],
) -> Mapping[str, Any]:
    """The seed-42 run of a report that sent the registered prompt over the same input."""
    provenance = report.get("provenance") or {}
    config = provenance.get("config") or {}
    if (provenance.get("dataset_sha256"), provenance.get("contexts_sha256")) != input_sha256:
        raise ValueError(f"{name}: the report used another dataset or cached contexts")
    if (
        (config.get("prompt_version"), config.get("context_chars"))
        != (PROMPT_VERSION, CONTEXT_CHARS)
        or config.get("top_k_override")
        or config.get("allow_short_contexts")
    ):
        raise ValueError(f"{name}: the report sent another prompt or context")
    runs = [run for run in report.get("runs") or [] if run.get("seed") == SEED]
    if len(runs) != 1:
        raise ValueError(f"{name}: the report holds no single run of seed {SEED}")
    rows = runs[0].get("cases") or []
    if sorted(str(row.get("case_id")) for row in rows) != sorted(cases):
        raise ValueError(f"{name}: the seed-{SEED} run does not hold every case once")
    # C.1a and C.1b predate the count; their code built the same contexts at these options.
    for row in rows:
        count = len(cases[str(row["case_id"])]["contexts"])
        if row.get("context_count", count) != count:
            raise ValueError(f"{name}: case {row['case_id']} was sent another context")
    return runs[0]


def build_plan(
    reports: Mapping[str, Mapping[str, Any]],
    *,
    dataset_path: Path,
    contexts_path: Path,
    report_sha256: Mapping[str, str] | None = None,
    sample_size: int = SAMPLE_SIZE,
) -> dict[str, Any]:
    """Freeze every request and every deterministic count before the first grade."""
    input_sha256 = (_sha256_path(dataset_path), _sha256_path(contexts_path))
    cases = {
        case["case_id"]: case
        for case in load_benchmark_cases(
            dataset_path=dataset_path,
            contexts_path=contexts_path,
            expected_cases=EXPECTED_CASES,
            context_chars=CONTEXT_CHARS,
        )
    }
    sample = sample_case_ids(list(cases), sample_size)
    items: list[dict[str, Any]] = []
    generators: dict[str, Any] = {}
    checks: dict[str, Any] = {}
    for name, report in reports.items():
        run = _seed_run(report, name, cases, input_sha256)
        provenance = report["provenance"]
        generators[name] = {
            "report_sha256": (report_sha256 or {}).get(name),
            "ollama_model": provenance.get("ollama_model"),
            "ollama_model_digest": provenance.get("ollama_model_digest"),
            "think": provenance.get("ollama_think"),
            "code_sha": provenance.get("code_sha"),
        }
        checks[name] = answer_checks(run, cases, provenance.get("config") or {})
        answers = {
            str(row["case_id"]): str(row.get("answer") or "").strip() for row in run["cases"]
        }
        for case_id in sample:
            item: dict[str, Any] = {
                "item_id": _digest(f"{name}:{case_id}")[:16],
                "generator": name,
                "case_id": case_id,
            }
            if answers[case_id]:
                message = build_message(
                    cases[case_id]["query"], cases[case_id]["contexts"], answers[case_id]
                )
                item.update(message=message, message_sha256=_digest(message))
            else:
                item["empty_answer"] = True
            items.append(item)
    items.sort(key=lambda item: _digest(f"{SALT}:order:{item['item_id']}"))
    asked = [item for item in items if "message" in item]
    retest = sorted(asked, key=lambda item: _digest(f"{SALT}:retest:{item['item_id']}"))
    items.extend(
        {**item, "item_id": f"{item['item_id']}-retest", "retest_of": item["item_id"]}
        for item in retest[:RETEST_SIZE]
    )
    return {
        "protocol": PROTOCOL,
        "salt": SALT,
        "seed": SEED,
        "dataset_sha256": input_sha256[0],
        "contexts_sha256": input_sha256[1],
        "prompt_version": PROMPT_VERSION,
        "sample": sample,
        "context_keyword_recall": round(
            statistics.fmean(
                context_recall(list(case["contexts"]), list(case["expected_keywords"]))
                for case in cases.values()
                if case["expected_keywords"]
            ),
            4,
        ),
        "generators": generators,
        "checks": checks,
        "route": isolated.settings(SYSTEM_PROMPT),
        "instructions_sha256": _digest(INSTRUCTIONS),
        "items": items,
    }


Sender = Callable[[str, str], Any]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _append(path: Path, row: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_plan(plan: Mapping[str, Any], out: Path, send: Sender, *, limit: int = 0) -> int:
    """Send each request that has no valid verdict yet; return how many requests were graded."""
    path = out / "verdicts.jsonl"
    done = {row["item_id"] for row in _read_jsonl(path) if row["status"] == "valid"}
    graded = 0
    for item in plan["items"]:
        if "message" not in item or item["item_id"] in done:
            continue
        if limit and graded >= limit:
            break
        for attempt in range(1, FORM_ATTEMPTS + 1):
            row: dict[str, Any] = {
                "item_id": item["item_id"],
                "message_sha256": item["message_sha256"],
                "attempt": attempt,
            }
            try:
                reply = send(SYSTEM_PROMPT, item["message"])
            except JudgeUnavailable as exc:
                row.update(status="unavailable", reason=exc.code)
                _append(path, row)
                raise
            row.update(
                raw_text=reply.text,
                model=reply.model,
                usage={key: reply.usage[key] for key in USAGE_FIELDS if key in reply.usage},
                elapsed_s=round(reply.elapsed_s, 1),
                session=reply.session,
            )
            try:
                row.update(status="valid", verdict=parse_verdict(reply.text))
            except VerdictError as exc:
                row.update(status="invalid", reason=str(exc))
            _append(path, row)
            print(f"{item['item_id']} attempt {attempt}: {row['status']}", flush=True)
            if row["status"] == "valid":
                break
        graded += 1
    return graded


def reuse_verdicts(plan: Mapping[str, Any], out: Path, source: Path) -> int:
    """Copy the verdicts an earlier plan got for this plan's requests; return how many.

    Only before the first request, only from a plan of the same route and rules, and only for
    a request with the same item id and message hash: the first valid verdict, the one
    `summarize` reads, from a record whose every verdict is vouched for. Each copy names the
    earlier plan's SHA-256 in `reused_from`.
    """
    path = out / "verdicts.jsonl"
    if path.exists():
        raise ValueError(f"{path} exists: verdicts are reused before the first request")
    earlier = json.loads((source / "plan.json").read_text(encoding="utf-8"))
    for key in ("route", "instructions_sha256"):
        if earlier.get(key) != plan.get(key):
            raise ValueError(f"the earlier plan was asked by another {key}")
    rows = _read_jsonl(source / "verdicts.jsonl")
    _vouched(earlier, rows)
    wanted = {
        item["item_id"]: item["message_sha256"] for item in plan["items"] if "message" in item
    }
    origin = _sha256_path(source / "plan.json")
    copied: set[str] = set()
    for row in rows:
        item_id = str(row.get("item_id"))
        if row.get("status") != "valid" or item_id in copied:
            continue
        if wanted.get(item_id) == row.get("message_sha256"):
            _append(path, {**row, "reused_from": origin})
            copied.add(item_id)
    return len(copied)


def _vouched(
    plan: Mapping[str, Any], verdicts: Sequence[Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    """The first valid verdict of each request, re-read from its raw reply."""
    items = {item["item_id"]: item for item in plan["items"]}
    valid: dict[str, dict[str, Any]] = {}
    for row in verdicts:
        if row.get("status") != "valid":
            continue
        item = items.get(str(row.get("item_id")))
        if item is None or row.get("message_sha256") != item.get("message_sha256"):
            raise ValueError(f"the verdict of {row.get('item_id')} answers no planned request")
        try:
            isolated.check_record(row.get("session"))
        except ValueError as exc:
            raise ValueError(f"the verdict of {row['item_id']} is not vouched for: {exc}") from None
        valid.setdefault(item["item_id"], parse_verdict(str(row.get("raw_text"))))
    return valid


def summarize(plan: Mapping[str, Any], verdicts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Classes, supported claims and defects per generator; agreement of the judge with itself."""
    valid = _vouched(plan, verdicts)
    items = {item["item_id"]: item for item in plan["items"]}
    generators: dict[str, Any] = {}
    for name in plan["generators"]:
        own = [
            item for item in plan["items"] if item["generator"] == name and "retest_of" not in item
        ]
        empty = sum(bool(item.get("empty_answer")) for item in own)
        graded = [valid[item["item_id"]] for item in own if item["item_id"] in valid]
        classes = Counter(classify(verdict) for verdict in graded)
        classes["bad"] += empty
        defects = Counter(verdict["defect"] for verdict in graded)
        defects["empty"] += empty
        rates = [
            verdict["claims_supported"] / verdict["claims_total"]
            for verdict in graded
            if verdict["claims_total"]
        ]
        generators[name] = {
            "items": len(own),
            "graded": len(graded) + empty,
            "empty_answers": empty,
            "classes": {label: classes[label] for label in CLASSES},
            "supported_claim_rate": round(statistics.fmean(rates), 4) if rates else None,
            "with_unsupported_claim": sum(
                verdict["claims_supported"] < verdict["claims_total"] for verdict in graded
            ),
            "answers": {
                label: sum(verdict["answers_question"] == label for verdict in graded)
                for label in ANSWERS
            },
            "defects": {label: defects[label] for label in DEFECTS if label != "none"},
        }
    seen: dict[str, set[bool]] = {}
    for item_id, verdict in valid.items():
        if "retest_of" not in items[item_id]:
            seen.setdefault(items[item_id]["case_id"], set()).add(verdict["context_has_answer"])
    pairs = [
        (valid[item["retest_of"]], valid[item_id])
        for item_id, item in items.items()
        if "retest_of" in item and item_id in valid and item["retest_of"] in valid
    ]
    sent = [row for row in verdicts if "usage" in row and "reused_from" not in row]
    requests: dict[str, Any] = {
        "sent": len(sent),
        "valid": len(valid),
        "cost_usd": round(sum(float(row["usage"].get("total_cost_usd") or 0) for row in sent), 2),
        "elapsed_s": round(sum(float(row.get("elapsed_s") or 0) for row in sent), 1),
    }
    # The 30-case record reused nothing, and its published summary has no such count.
    if reused := sum("reused_from" in row for row in verdicts):
        requests["reused"] = reused
    return {
        "missing": sum(
            "message" in item and item_id not in valid for item_id, item in items.items()
        ),
        "generators": generators,
        "context_has_answer": {
            "cases": len(seen),
            "same_for_every_answer": sum(len(values) == 1 for values in seen.values()),
        },
        "retest": {
            "pairs": len(pairs),
            "same_class": sum(classify(a) == classify(b) for a, b in pairs),
            "same_answers_question": sum(
                a["answers_question"] == b["answers_question"] for a, b in pairs
            ),
            "same_claims": sum(
                (a["claims_total"], a["claims_supported"])
                == (b["claims_total"], b["claims_supported"])
                for a, b in pairs
            ),
        },
        "checks": plan["checks"],
        "context_keyword_recall": plan["context_keyword_recall"],
        "requests": requests,
    }


def _isolated_sender(timeout_s: float) -> Sender:
    executable = os.environ.get("RAG_JUDGE_CLAUDE_CLI", "").strip() or isolated.find_cli()
    if executable is None:
        raise SystemExit("Claude CLI is not installed")

    def send(system_prompt: str, message: str) -> Any:
        return isolated.send(executable, system_prompt, message, timeout_s=timeout_s)

    return send


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan")
    plan_parser.add_argument("--report", action="append", required=True, metavar="NAME=PATH")
    plan_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    plan_parser.add_argument("--contexts", type=Path, default=DEFAULT_CONTEXTS)
    plan_parser.add_argument("--out", type=Path, required=True)
    plan_parser.add_argument("--sample-size", type=int, default=SAMPLE_SIZE)
    reuse_parser = commands.add_parser("reuse")
    reuse_parser.add_argument("--from", dest="source", type=Path, required=True)
    reuse_parser.add_argument("--out", type=Path, required=True)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--out", type=Path, required=True)
    run_parser.add_argument("--limit", type=int, default=0)
    run_parser.add_argument("--timeout", type=float, default=CLI_TIMEOUT_S)
    summary_parser = commands.add_parser("summary")
    summary_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    plan_path = args.out / "plan.json"
    if args.command == "plan":
        if plan_path.exists():
            raise SystemExit(f"{plan_path} exists: a plan is frozen once written")
        if not 0 < args.sample_size <= EXPECTED_CASES:
            raise SystemExit(f"--sample-size {args.sample_size}: give 1 to {EXPECTED_CASES} cases")
        reports: dict[str, Any] = {}
        digests: dict[str, str] = {}
        for spec in args.report:
            name, _, path = spec.partition("=")
            if not name or not path or name in reports:
                raise SystemExit(f"--report {spec}: give each report once as NAME=PATH")
            reports[name] = json.loads(Path(path).read_text(encoding="utf-8"))
            digests[name] = _sha256_path(Path(path))
        plan = build_plan(
            reports,
            dataset_path=args.dataset,
            contexts_path=args.contexts,
            report_sha256=digests,
            sample_size=args.sample_size,
        )
        args.out.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", "utf-8")
        asked = sum("message" in item for item in plan["items"])
        print(f"{asked} requests planned in {plan_path}")
        return 0
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if args.command == "reuse":
        try:
            reused = reuse_verdicts(plan, args.out, args.source)
        except ValueError as exc:
            raise SystemExit(str(exc)) from None
        print(f"{reused} verdicts reused from {args.source}")
        return 0
    if args.command == "run":
        try:
            graded = run_plan(plan, args.out, _isolated_sender(args.timeout), limit=args.limit)
        except JudgeUnavailable as exc:
            print(f"stopped: the route refused a reply ({exc.code})")
            return 2
        print(f"{graded} requests graded")
        return 0
    summary = summarize(plan, _read_jsonl(args.out / "verdicts.jsonl"))
    (args.out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1) + "\n", "utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

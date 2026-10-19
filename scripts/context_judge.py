#!/usr/bin/env python3
"""Grade whether the context a search sent holds the answer (M3 on aircargo, PLAN.md §4.3).

PLAN.md stage 2, items 2 and 3: on aircargo M3 is whether the context the chat's model reads
holds the answer to the question, by the one judge (decision D12) asked in stateless requests
by the registered route (``evaluation.isolated_request``), as ``scripts/chat_answer_judge.py``
asks it. The answer judge reads the context beside an answer (its ``context_has_answer``);
this judge reads it alone, for runs without an answer: ``reports/stage2/tools/live_retrieval.py``
saves the prompt the chat would send. The documents are read from that prompt by
``chat_answer_judge.read_prompt``, so both judges see one context the same way.

Per context the judge gives ``context_answer`` - "full" when the documents hold everything the
question asks for, "partial" when they hold a part of it, "none" when they hold nothing that
answers it - and ``documents_with_answer``, the numbers of the documents that hold a part.
``context_has_answer``, the answer judge's field, is "full" or "partial".

- ``plan`` reads retrieval records (``retrieval/*.json`` of each run) and freezes one request
  per context in a fixed shuffled order, plus a retest of ``--retest`` of them (the stability
  check), before the first grade; a context without documents is "none" without a request;
- ``run`` sends the requests one at a time and appends every reply to ``verdicts.jsonl``, so a
  stopped run resumes; it stops at the first reply the route refuses;
- ``summary`` counts the levels per run, the retest's quadratic kappa over the three levels and
  each context's level by case id; a verdict counts only with the record of a clean session
  and the hash of its planned request.

Usage:
  python scripts/context_judge.py plan --run LABEL=DIR ... --out DIR [--retest N]
  python scripts/context_judge.py run --out DIR [--limit N]
  python scripts/context_judge.py summary --out DIR
"""

from __future__ import annotations

import argparse
import json
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
from scripts import chat_answer_judge as answer_judge  # noqa: E402

SALT = "context-judge-2026-10-19"
RETEST_SIZE = 15
LEVELS = ("none", "partial", "full")
KEYS = ("context_answer", "documents_with_answer", "note")

# One line: the route refuses a system prompt with a newline, a quote or a shell character.
SYSTEM_PROMPT = (
    "You judge whether the documents a search found hold the answer to a question. Follow the "
    "rules of the request and reply with one JSON object only."
)
INSTRUCTIONS = """You judge whether the documents a support assistant's search found hold the \
answer to the user's question. The assistant's answer model reads exactly these numbered \
documents and nothing else.

Judge against these documents only. Do not use outside knowledge to decide what the answer is.

1. context_answer: "full" if the documents hold everything needed to answer what the question \
asks; "partial" if they hold some of it and miss a part the question asks for; "none" if they \
hold nothing that answers the question.
2. documents_with_answer: the numbers of the documents that hold a part of the answer, smallest \
first; an empty list when context_answer is "none".
3. note: one short sentence.

Reply with one JSON object and nothing else:
{"context_answer": "<full|partial|none>", "documents_with_answer": [<integers>], "note": \
"<one short sentence>"}"""


class VerdictError(ValueError):
    """A reply that is not one verdict object of the registered form."""


def build_message(question: str, documents: Sequence[tuple[str, str]]) -> str:
    """One request: the rules, then the question and the documents as the answer judge shows them."""
    shown = "\n\n".join(
        f"[{index}] source={source}\n{text}" for index, (source, text) in enumerate(documents, 1)
    )
    return f"{INSTRUCTIONS}\n\nQUESTION:\n{question}\n\nDOCUMENTS:\n{shown or '(none)'}\n"


def parse_verdict(text: str, documents: int) -> dict[str, Any]:
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
    if value["context_answer"] not in LEVELS:
        raise VerdictError("context_answer is not a registered value")
    numbers = value["documents_with_answer"]
    if not isinstance(numbers, list) or any(
        not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= documents for n in numbers
    ):
        raise VerdictError("documents_with_answer names no listed document")
    if len(set(numbers)) != len(numbers) or (not numbers) != (value["context_answer"] == "none"):
        raise VerdictError("documents_with_answer does not fit context_answer")
    if not isinstance(value["note"], str):
        raise VerdictError("note is not a string")
    return value


def run_contexts(run: Path) -> list[dict[str, Any]]:
    """Each retrieval record of a run with the documents its prompt holds."""
    contexts = []
    for path in sorted((run / "retrieval").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        text = record["prompt"]["text"]
        if answer_judge._digest(text) != record["prompt"]["sha256"]:
            raise ValueError(f"{run.name}/{path.name}: the prompt is not the one its hash names")
        question, documents = answer_judge.read_prompt(text)
        if question != record["question"]:
            raise ValueError(f"{run.name}/{path.name}: the prompt holds another question")
        contexts.append(
            {
                "case_id": record["case_id"],
                "question": question,
                "documents": documents,
                "prompt_sha256": record["prompt"]["sha256"],
            }
        )
    return contexts


def build_plan(runs: Mapping[str, Path], *, retest: int = RETEST_SIZE) -> dict[str, Any]:
    """Freeze every request before the first grade."""
    items: list[dict[str, Any]] = []
    records: dict[str, Any] = {}
    for label, run in runs.items():
        launch_path = run / "launch.json"
        launch = json.loads(launch_path.read_text(encoding="utf-8")) if launch_path.exists() else {}
        records[label] = {
            key: launch.get(key) for key in ("code_sha", "tenant", "chroma_dir", "cases_file")
        }
        for context in run_contexts(run):
            item: dict[str, Any] = {
                "item_id": answer_judge._digest(f"{label}:{context['case_id']}")[:16],
                "run": label,
                "case_id": context["case_id"],
                "prompt_sha256": context["prompt_sha256"],
                "documents": len(context["documents"]),
            }
            if context["documents"]:
                message = build_message(context["question"], context["documents"])
                item.update(message=message, message_sha256=answer_judge._digest(message))
            else:
                item["empty_context"] = True
            items.append(item)
    items.sort(key=lambda item: answer_judge._digest(f"{SALT}:order:{item['item_id']}"))
    asked = [item for item in items if "message" in item]
    again = sorted(asked, key=lambda item: answer_judge._digest(f"{SALT}:retest:{item['item_id']}"))
    items.extend(
        {**item, "item_id": f"{item['item_id']}-retest", "retest_of": item["item_id"]}
        for item in again[:retest]
    )
    return {
        "salt": SALT,
        "prompt_id": answer_judge.PROMPT_ID,
        "runs": records,
        "route": isolated.settings(SYSTEM_PROMPT),
        "instructions_sha256": answer_judge._digest(INSTRUCTIONS),
        "items": items,
    }


Sender = Callable[[str, str], Any]


def run_plan(plan: Mapping[str, Any], out: Path, send: Sender, *, limit: int = 0) -> int:
    """Send each request that has no valid verdict yet; return how many requests were graded."""
    path = out / "verdicts.jsonl"
    done = {row["item_id"] for row in answer_judge._read_jsonl(path) if row["status"] == "valid"}
    graded = 0
    for item in plan["items"]:
        if "message" not in item or item["item_id"] in done:
            continue
        if limit and graded >= limit:
            break
        for attempt in range(1, answer_judge.FORM_ATTEMPTS + 1):
            row: dict[str, Any] = {
                "item_id": item["item_id"],
                "message_sha256": item["message_sha256"],
                "attempt": attempt,
            }
            try:
                reply = send(SYSTEM_PROMPT, item["message"])
            except JudgeUnavailable as exc:
                row.update(status="unavailable", reason=exc.code)
                answer_judge._append(path, row)
                raise
            row.update(
                raw_text=reply.text,
                model=reply.model,
                usage={
                    key: reply.usage[key] for key in answer_judge.USAGE_FIELDS if key in reply.usage
                },
                elapsed_s=round(reply.elapsed_s, 1),
                session=reply.session,
            )
            try:
                row.update(status="valid", verdict=parse_verdict(reply.text, item["documents"]))
            except VerdictError as exc:
                row.update(status="invalid", reason=str(exc))
            answer_judge._append(path, row)
            print(f"{item['item_id']} attempt {attempt}: {row['status']}", flush=True)
            if row["status"] == "valid":
                break
        graded += 1
    return graded


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
        valid.setdefault(
            item["item_id"], parse_verdict(str(row.get("raw_text")), item["documents"])
        )
    return valid


def summarize(plan: Mapping[str, Any], verdicts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    valid = _vouched(plan, verdicts)
    first = [item for item in plan["items"] if "retest_of" not in item]

    def level(item: Mapping[str, Any]) -> str | None:
        if item.get("empty_context"):
            return "none"
        verdict = valid.get(item["item_id"])
        return None if verdict is None else str(verdict["context_answer"])

    per_run: dict[str, Any] = {}
    for label in plan["runs"]:
        mine = [item for item in first if item["run"] == label]
        levels = Counter(level(item) for item in mine)
        per_run[label] = {
            "contexts": len(mine),
            "graded": sum(levels[name] for name in LEVELS),
            "missing": levels[None],
            "levels": {name: levels[name] for name in LEVELS},
            "context_has_answer": levels["full"] + levels["partial"],
            "empty_contexts": sum(1 for item in mine if item.get("empty_context")),
        }
    index = {name: number for number, name in enumerate(LEVELS)}
    by_id = {item["item_id"]: item for item in first}
    pairs = []
    for item in plan["items"]:
        if "retest_of" not in item:
            continue
        before, after = level(by_id[item["retest_of"]]), level(item)
        if before is not None and after is not None:
            pairs.append((index[before], index[after]))
    return {
        "runs": plan["runs"],
        "per_run": per_run,
        "retest": {
            "pairs": len(pairs),
            "same_level": sum(a == b for a, b in pairs),
            "quadratic_kappa": answer_judge.quadratic_kappa(pairs, len(LEVELS)),
        },
        "per_case": [
            {
                "run": item["run"],
                "case_id": item["case_id"],
                "level": level(item),
                "documents": item["documents"],
                "documents_with_answer": (
                    valid[item["item_id"]]["documents_with_answer"]
                    if item["item_id"] in valid
                    else []
                ),
            }
            for item in sorted(first, key=lambda item: (item["run"], item["case_id"]))
        ],
        "requests_valid": len(valid),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan")
    plan_parser.add_argument("--run", action="append", required=True, metavar="LABEL=DIR")
    plan_parser.add_argument("--retest", type=int, default=RETEST_SIZE)
    plan_parser.add_argument("--out", type=Path, required=True)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--out", type=Path, required=True)
    run_parser.add_argument("--limit", type=int, default=0)
    run_parser.add_argument("--timeout", type=float, default=answer_judge.CLI_TIMEOUT_S)
    summary_parser = commands.add_parser("summary")
    summary_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    plan_path = args.out / "plan.json"
    if args.command == "plan":
        if plan_path.exists():
            raise SystemExit(f"{plan_path} exists: a plan is frozen once written")
        runs: dict[str, Path] = {}
        for spec in args.run:
            label, _, path = spec.partition("=")
            if not label or not path or label in runs:
                raise SystemExit(f"--run {spec}: give each run once as LABEL=DIR")
            runs[label] = Path(path)
        plan = build_plan(runs, retest=args.retest)
        args.out.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", "utf-8")
        asked = sum("message" in item for item in plan["items"])
        print(f"{asked} requests planned in {plan_path}")
        return 0
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if args.command == "run":
        try:
            graded = run_plan(
                plan, args.out, answer_judge._isolated_sender(args.timeout), limit=args.limit
            )
        except JudgeUnavailable as exc:
            print(f"stopped: the route refused a reply ({exc.code})")
            return 2
        print(f"{graded} requests graded")
        return 0
    summary = summarize(plan, answer_judge._read_jsonl(args.out / "verdicts.jsonl"))
    (args.out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1) + "\n", "utf-8"
    )
    print(json.dumps({key: summary[key] for key in ("per_run", "retest")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

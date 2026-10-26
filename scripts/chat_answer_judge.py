#!/usr/bin/env python3
"""Grade the web chat's answers of live runs with the one judge (PLAN.md stage 1, item 5).

The chat's path chooses each answer's documents itself, so a judge of chat answers reads, per
answer, the documents the chat's model read: the stand saves every prompt it sends
(``reports/stage1/tools/live_api.py``), and the answer prompt (``QA_PROMPT_V3``, ``V4``, ``V5``) holds
the question and the numbered documents. Decision D12 leaves one judge, the session's model, asked
in stateless requests by the registered route (``evaluation.isolated_request``), as
``scripts/generator_answer_judge.py`` asks it; the rules here name no domain and no language —
the answer is due in the question's language — so one prompt serves every corpus.

Per answer the judge gives M1 (PLAN.md §4.3): the material claims and how many of them the
documents support, whether the documents hold the answer, whether the answer gives it, the
reference marks ``[N]`` whose statement document N supports, and a defect. Given a reference
answer (the external bases' cases), it also gives M2: whether the answer agrees with it. A
mark that names no listed document is counted here, without the judge. With
``--withhold-references`` the plan names the references file by its SHA-256 but no request
carries a reference: M1 read where no reference can sway it, as part 1's aircargo requests are.

- ``plan`` reads run records (``cases/*.json`` and ``prompts/`` of each), freezes one request
  per answer in a fixed shuffled order, plus a retest of ``--retest`` of them (the stability
  check), before the first grade; an empty answer is graded bad without a request;
- ``run`` sends the requests one at a time and appends every reply to ``verdicts.jsonl``, so a
  stopped run resumes; it stops at the first reply the route refuses; a request gets at most
  six replies over all runs (``REPLIES``);
- ``summary`` counts the verdicts per run; a verdict counts only from a request's first six
  replies, from the plan's model, with the record of a clean session and the hash of its
  planned request. Both refuse a plan this code did not freeze: another salt, rules or route,
  a request that is not the text its hash names, a second retest of a request or a retest that
  is not its request's copy.

Usage:
  python scripts/chat_answer_judge.py plan --run LABEL=DIR ...
      [--references FILE [--withhold-references]] --out DIR
  python scripts/chat_answer_judge.py run --out DIR [--limit N]
  python scripts/chat_answer_judge.py summary --out DIR
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation import isolated_request as isolated  # noqa: E402
from evaluation.blinded_judge_clients import JudgeUnavailable  # noqa: E402

SALT = "chat-answer-judge-2026-10-18"
RETEST_SIZE = 15
FORM_ATTEMPTS = 3
# A request's replies that count: the attempts of one run of the plan and of one more run.
REPLIES = 2 * FORM_ATTEMPTS
CLI_TIMEOUT_S = 1200.0
# The answer prompts of agent/prompts.py this adapter reads, told apart by their citation
# sentence; a plan's answers come from one of them.
PROMPT_IDS = {
    "QA_PROMPT_V3": "add [N] right after it,",
    "QA_PROMPT_V4": "[1] for the first document in the context list,",
    # Stage 3b's evidence-first prompt (docs/specs/answer-prompt-v5.md), replayed on V4's contexts.
    "QA_PROMPT_V5": "[1] for the context's first document,",
}
# Their common frame: the stand saves the prompt after "USER:".
CONTEXT_START = "CONTEXT:\n"
CONTEXT_END = "\n--------------------\n\nQUESTION:\n"
QUESTION_END = "\n\nWhen you rely on"
LABEL = re.compile(r"(?m)^\[(\d+) \| source=([^\]\n]*)\]\n")
MARK = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
ANSWERS = ("full", "partial", "declined", "no")
REFERENCE = ("agrees", "partial", "disagrees", "declined", "none")
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
    "citations_supported",
    "reference",
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

# One line: the route refuses a system prompt with a newline, a quote or a shell character.
SYSTEM_PROMPT = (
    "You grade one answer of a retrieval-augmented support assistant against the documents it "
    "was given. Follow the grading rules of the request and reply with one JSON object only."
)
INSTRUCTIONS = """You grade one answer written by a support assistant. The assistant was told \
to answer the user's question strictly from the numbered documents below, briefly and in the \
language of the question, to mark a fact it takes from a document with [N], N being the \
document's number, and to say that the information is insufficient when the documents do not \
contain the answer. You see the same documents the assistant saw.

Grade the answer against these documents only. Do not use outside knowledge to decide whether \
a claim is true.

1. claims_total: the number of material claims in the answer - statements of a fact, rule, \
number, deadline, condition, procedure step or recommendation. Restating the question, a \
greeting, a reference mark such as [1] or a statement that the information is insufficient is \
not a claim.
2. claims_supported: how many of those claims the documents state or directly imply. A claim \
that adds a detail the documents do not give (a number, a deadline, a condition, a name) is \
not supported.
3. context_has_answer: true if the documents contain what is needed to answer the question, at \
least in part; otherwise false.
4. answers_question: "full" if the answer gives everything the documents offer that the \
question asks for; "partial" if it gives some of it and misses a part the question asks for; \
"declined" if it says the information is insufficient and gives no answer; "no" if it does not \
address the question (off topic, or only copies or cites the documents).
5. citations_supported: the answer holds MARKS reference marks that name a listed document (a \
mark [1, 2] counts as two). Of those, how many follow a statement that the named document \
states or directly implies. 0 when MARKS is 0.
6. reference: a reference answer is given below, or "none" is written there. If one is given: \
"agrees" if the answer's substance matches it; "partial" if the answer matches a part of it and \
contradicts none of it; "disagrees" if the answer contradicts it or gives another answer; \
"declined" if the answer says the information is insufficient. If none is given: "none".
7. defect: "none", or the first of these that applies: "empty" (no text), "citation_only" (only \
reference marks such as [1]), "wrong_language" (not in the language of the question), \
"copied_context" (mostly copies the documents instead of answering), "cut_off" (ends in the \
middle of a sentence), "repetition" (repeats the same text), "other".

Reply with one JSON object and nothing else:
{"claims_total": <integer>, "claims_supported": <integer>, "context_has_answer": <true or \
false>, "answers_question": "<full|partial|declined|no>", "citations_supported": <integer>, \
"reference": "<agrees|partial|disagrees|declined|none>", "defect": \
"<none|empty|citation_only|wrong_language|copied_context|cut_off|repetition|other>", \
"note": "<one short sentence>"}"""


class VerdictError(ValueError):
    """A reply that is not one verdict object of the registered form."""


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def prompt_id(text: str) -> str:
    """Which answer prompt a saved prompt is."""
    found = [name for name, marker in PROMPT_IDS.items() if marker in text]
    framed = CONTEXT_START in text and CONTEXT_END in text and QUESTION_END in text
    if not framed or len(found) != 1:
        raise ValueError(f"not an answer prompt of {' or '.join(PROMPT_IDS)}")
    return found[0]


def one_prompt(names: Iterable[str]) -> str | None:
    """The answer prompt all of a plan's requests were written with."""
    found = sorted(set(names))
    if len(found) > 1:
        raise ValueError(f"the runs hold answers of {' and '.join(found)}: a plan reads one prompt")
    return found[0] if found else None


def read_prompt(text: str) -> tuple[str, list[tuple[str, str]]]:
    """The question and the numbered documents (source, text) of a saved answer prompt."""
    prompt_id(text)
    context = text.split(CONTEXT_START, 1)[1].split(CONTEXT_END, 1)[0]
    question = text.split(CONTEXT_END, 1)[1].split(QUESTION_END, 1)[0]
    if context == "[]":
        return question, []
    labels = list(LABEL.finditer(context))
    if not labels or labels[0].start() != 0:
        raise ValueError("the context does not start with a document label")
    documents = []
    for index, label in enumerate(labels, start=1):
        if int(label[1]) != index:
            raise ValueError(f"document label {label[1]} stands where {index} is due")
        end = labels[index].start() if index < len(labels) else len(context)
        documents.append((label[2], context[label.end() : end].rstrip("\n")))
    return question, documents


def marks(answer: str, documents: int) -> tuple[int, int]:
    """The reference marks of an answer: those naming a listed document, and the others."""
    numbers = [int(n) for group in MARK.findall(answer) for n in group.split(",")]
    listed = sum(1 for n in numbers if 1 <= n <= documents)
    return listed, len(numbers) - listed


def build_message(
    question: str, documents: Sequence[tuple[str, str]], answer: str, reference: str | None
) -> str:
    """One request: the rules, then the question, the documents, the answer, the reference."""
    listed, _ = marks(answer, len(documents))
    shown = "\n\n".join(
        f"[{index}] source={source}\n{text}" for index, (source, text) in enumerate(documents, 1)
    )
    return (
        f"{INSTRUCTIONS.replace('MARKS', str(listed))}\n\nQUESTION:\n{question}\n\n"
        f"DOCUMENTS:\n{shown or '(none)'}\n\nANSWER:\n{answer}\n\n"
        f"REFERENCE ANSWER:\n{reference if reference else 'none'}\n"
    )


def parse_verdict(text: str, listed: int, has_reference: bool) -> dict[str, Any]:
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
    for name in ("claims_total", "claims_supported", "citations_supported"):
        number = value[name]
        if not isinstance(number, int) or isinstance(number, bool) or number < 0:
            raise VerdictError(f"{name} is not a non-negative integer")
    if value["claims_supported"] > value["claims_total"]:
        raise VerdictError("claims_supported exceeds claims_total")
    if value["citations_supported"] > listed:
        raise VerdictError("citations_supported exceeds the marks that name a document")
    if not isinstance(value["context_has_answer"], bool):
        raise VerdictError("context_has_answer is not a boolean")
    if value["answers_question"] not in ANSWERS:
        raise VerdictError("answers_question is not a registered value")
    if value["reference"] not in REFERENCE or (value["reference"] == "none") == has_reference:
        raise VerdictError("reference does not fit the request")
    if value["defect"] not in DEFECTS:
        raise VerdictError("defect is not a registered value")
    if not isinstance(value["note"], str):
        raise VerdictError("note is not a string")
    return value


def classify(verdict: Mapping[str, Any]) -> str:
    """good: complete and fully supported, or a right decline; partial_ok: faithful but partial.

    "full" and "partial" weigh the answer against what the documents offer, so they count only
    where the documents hold the answer: without it the right answer is a decline.
    """
    faithful = verdict["defect"] == "none" and (
        verdict["claims_supported"] == verdict["claims_total"]
    )
    answered = verdict["claims_total"] >= 1
    held = verdict["context_has_answer"]
    if faithful and verdict["answers_question"] == "full" and answered and held:
        return "good"
    if faithful and verdict["answers_question"] == "declined" and not held:
        return "good"
    if faithful and verdict["answers_question"] == "partial" and answered and held:
        return "partial_ok"
    return "bad"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _append(path: Path, row: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_answers(run: Path) -> list[dict[str, Any]]:
    """Each answered case of a run record with the documents its answer prompt held."""
    prompts: dict[str, list[tuple[str, list[tuple[str, str]], str, str]]] = {}
    for path in sorted((run / "prompts").glob("*-stream.txt")):
        text = path.read_text(encoding="utf-8")
        try:
            question, documents = read_prompt(text)
        except ValueError:
            continue
        prompts.setdefault(question, []).append(
            (path.name, documents, _digest(text), prompt_id(text))
        )
    answers = []
    for path in sorted((run / "cases").glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        if str(case["case_id"]).startswith("warmup-"):
            continue
        found = prompts.get(case["question"], [])
        if len(found) != 1:
            raise ValueError(
                f"{run.name}/{path.name}: {len(found)} answer prompts hold its question"
            )
        name, documents, digest, prompt = found[0]
        result = next((e for e in case.get("events", []) if e.get("type") == "result"), {})
        answers.append(
            {
                "case_id": case["case_id"],
                "question": case["question"],
                "answer": str(result.get("answer") or case.get("answer") or "").strip(),
                "route": result.get("route"),
                "documents": documents,
                "prompt_file": name,
                "prompt_sha256": digest,
                "prompt_id": prompt,
            }
        )
    return answers


def build_plan(
    runs: Mapping[str, Path],
    references: Mapping[str, Sequence[str]],
    *,
    retest: int = RETEST_SIZE,
    references_sha256: str | None = None,
    withheld: bool = False,
) -> dict[str, Any]:
    """Freeze every request and every deterministic count before the first grade.

    ``withheld``: the references file is named by ``references_sha256``, and ``references``
    is empty, so no request carries a reference.
    """
    if withheld and (references or references_sha256 is None):
        raise ValueError("a plan withholds the references of a named file: none in its requests")
    items: list[dict[str, Any]] = []
    records: dict[str, Any] = {}
    prompts: list[str] = []
    for label, run in runs.items():
        launch_path = run / "launch.json"
        launch = json.loads(launch_path.read_text(encoding="utf-8")) if launch_path.exists() else {}
        records[label] = {
            key: launch.get(key)
            for key in ("code_sha", "model", "model_digest", "tenant", "chroma_dir", "cases_file")
        }
        for answer in run_answers(run):
            prompts.append(answer["prompt_id"])
            reference = "\n\n".join(references.get(answer["case_id"], [])) or None
            listed, unlisted = marks(answer["answer"], len(answer["documents"]))
            item: dict[str, Any] = {
                "item_id": _digest(f"{label}:{answer['case_id']}")[:16],
                "run": label,
                "case_id": answer["case_id"],
                "route": answer["route"],
                "prompt_file": answer["prompt_file"],
                "prompt_sha256": answer["prompt_sha256"],
                "documents": len(answer["documents"]),
                "marks_listed": listed,
                "marks_unlisted": unlisted,
                "has_reference": reference is not None,
            }
            if answer["answer"]:
                message = build_message(
                    answer["question"], answer["documents"], answer["answer"], reference
                )
                item.update(message=message, message_sha256=_digest(message))
            else:
                item["empty_answer"] = True
            items.append(item)
    items.sort(key=lambda item: _digest(f"{SALT}:order:{item['item_id']}"))
    asked = [item for item in items if "message" in item]
    again = sorted(asked, key=lambda item: _digest(f"{SALT}:retest:{item['item_id']}"))
    items.extend(
        {**item, "item_id": f"{item['item_id']}-retest", "retest_of": item["item_id"]}
        for item in again[:retest]
    )
    return {
        "salt": SALT,
        "prompt_id": one_prompt(prompts),
        "runs": records,
        "route": isolated.settings(SYSTEM_PROMPT),
        "instructions_sha256": _digest(INSTRUCTIONS),
        "references_sha256": references_sha256,
        "references_withheld": withheld,
        "items": items,
    }


Sender = Callable[[str, str], Any]
Reader = Callable[[Mapping[str, Any], str], dict[str, Any]]


def check_plan(
    plan: Mapping[str, Any],
    *,
    salt: str = SALT,
    instructions: str = INSTRUCTIONS,
    system_prompt: str = SYSTEM_PROMPT,
) -> dict[str, dict[str, Any]]:
    """The plan's requests by id; refused unless it is this judge's and whole.

    Its salt, rules and route are this code's; each request is the text its hash names; each id
    stands once; a request has at most one retest, and that one is its copy. The hashes inside
    a plan cannot show an edit of the whole: the plan's own SHA-256 is committed before its
    first grade.
    """
    if (
        plan.get("salt") != salt
        or plan.get("instructions_sha256") != _digest(instructions)
        or plan.get("route") != isolated.settings(system_prompt)
    ):
        raise ValueError("the plan was not frozen by this judge: its salt, rules or route differ")
    items: dict[str, dict[str, Any]] = {}
    for item in plan["items"]:
        if item["item_id"] in items:
            raise ValueError(f"{item['item_id']} stands twice in the plan")
        if "message" in item and _digest(item["message"]) != item.get("message_sha256"):
            raise ValueError(f"the request of {item['item_id']} is not the text its hash names")
        items[item["item_id"]] = item
    retested: set[str] = set()
    for item in items.values():
        if "retest_of" not in item:
            continue
        first = items.get(item["retest_of"])
        copy = {key: value for key, value in item.items() if key not in ("item_id", "retest_of")}
        if (
            first is None
            or "retest_of" in first
            or "message" not in item
            or item["retest_of"] in retested
            or copy != {key: value for key, value in first.items() if key != "item_id"}
        ):
            raise ValueError(f"the retest {item['item_id']} does not repeat its request")
        retested.add(item["retest_of"])
    return items


def _replies(
    items: Mapping[str, Mapping[str, Any]], rows: Sequence[Mapping[str, Any]]
) -> Counter[str]:
    """Each request's replies so far; refused when a row answers no request of the plan."""
    replies: Counter[str] = Counter()
    for row in rows:
        item = items.get(str(row.get("item_id")))
        if (
            item is None
            or "message" not in item
            or row.get("message_sha256") != item["message_sha256"]
        ):
            raise ValueError(f"a row of {row.get('item_id')} answers no planned request")
        if row.get("status") in ("valid", "invalid"):
            replies[item["item_id"]] += 1
    return replies


def vouch(
    plan: Mapping[str, Any],
    items: Mapping[str, Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    read: Reader,
) -> dict[str, dict[str, Any]]:
    """The first valid verdict of each request among its first REPLIES replies.

    A verdict counts only from the plan's model, with the record of a clean session of one
    turn, re-read from its raw reply.
    """
    _replies(items, rows)
    model = plan["route"]["model"]
    seen: Counter[str] = Counter()
    valid: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("status") not in ("valid", "invalid"):
            continue
        item_id = str(row["item_id"])
        seen[item_id] += 1
        if row["status"] != "valid" or seen[item_id] > REPLIES or item_id in valid:
            continue
        session = row.get("session")
        if (
            row.get("model") != model
            or not isinstance(session, Mapping)
            or session.get("model") != model
        ):
            raise ValueError(f"the verdict of {item_id} is not the plan's model's")
        try:
            isolated.check_record(session)
        except ValueError as exc:
            raise ValueError(f"the verdict of {item_id} is not vouched for: {exc}") from None
        valid[item_id] = read(items[item_id], str(row.get("raw_text")))
    return valid


def send_plan(
    plan: Mapping[str, Any],
    items: Mapping[str, Mapping[str, Any]],
    out: Path,
    send: Sender,
    system_prompt: str,
    read: Reader,
    *,
    limit: int = 0,
) -> int:
    """Send each request without a counted verdict, at most REPLIES times over all runs."""
    path = out / "verdicts.jsonl"
    rows = _read_jsonl(path)
    replies = _replies(items, rows)
    done = vouch(plan, items, rows, read)
    graded = 0
    for item in plan["items"]:
        left = REPLIES - replies[item["item_id"]]
        if "message" not in item or item["item_id"] in done or left <= 0:
            continue
        if limit and graded >= limit:
            break
        for attempt in range(1, min(FORM_ATTEMPTS, left) + 1):
            row: dict[str, Any] = {
                "item_id": item["item_id"],
                "message_sha256": item["message_sha256"],
                "attempt": attempt,
            }
            try:
                reply = send(system_prompt, item["message"])
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
                row.update(status="valid", verdict=read(item, reply.text))
            except VerdictError as exc:
                row.update(status="invalid", reason=str(exc))
            _append(path, row)
            print(f"{item['item_id']} attempt {attempt}: {row['status']}", flush=True)
            if row["status"] == "valid":
                break
        graded += 1
    return graded


def _read(item: Mapping[str, Any], text: str) -> dict[str, Any]:
    return parse_verdict(text, item["marks_listed"], item["has_reference"])


def run_plan(plan: Mapping[str, Any], out: Path, send: Sender, *, limit: int = 0) -> int:
    """Send each request that has no counted verdict yet; return how many requests were graded."""
    return send_plan(plan, check_plan(plan), out, send, SYSTEM_PROMPT, _read, limit=limit)


def _vouched(
    plan: Mapping[str, Any], verdicts: Sequence[Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    """The counted verdict of each request (``vouch``), re-read from its raw reply."""
    return vouch(plan, check_plan(plan), verdicts, _read)


def quadratic_kappa(pairs: Sequence[tuple[int, int]], levels: int) -> float | None:
    """Cohen's kappa with quadratic weights over ordinal levels 0..levels-1.

    None when it cannot be computed: no pairs, or no disagreement to expect - every rating on
    one level (stage 2's spec, «Stability»: the agreement then decides).
    """
    if not pairs:
        return None
    count = len(pairs)
    first = Counter(a for a, _ in pairs)
    second = Counter(b for _, b in pairs)
    span = (levels - 1) ** 2
    observed = sum((a - b) ** 2 / span for a, b in pairs) / count
    expected = sum(
        first[a] * second[b] * (a - b) ** 2 / span for a in range(levels) for b in range(levels)
    ) / (count * count)
    if expected == 0:
        return None
    return round(1 - observed / expected, 4)


def summarize(plan: Mapping[str, Any], verdicts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    valid = _vouched(plan, verdicts)
    first = [item for item in plan["items"] if "retest_of" not in item]
    per_run: dict[str, Any] = {}
    for label in plan["runs"]:
        mine = [item for item in first if item["run"] == label]
        graded = [valid[item["item_id"]] for item in mine if item["item_id"] in valid]
        classes = Counter(classify(verdict) for verdict in graded)
        classes["bad"] += sum(1 for item in mine if item.get("empty_answer"))
        listed = sum(item["marks_listed"] for item in mine if item["item_id"] in valid)
        per_run[label] = {
            "answers": len(mine),
            "graded": len(graded) + sum(1 for item in mine if item.get("empty_answer")),
            "missing": sum(
                1 for item in mine if "message" in item and item["item_id"] not in valid
            ),
            "classes": {name: classes[name] for name in CLASSES},
            "routes": dict(Counter(str(item["route"]) for item in mine)),
            "defects": dict(Counter(verdict["defect"] for verdict in graded)),
            "reference": dict(Counter(verdict["reference"] for verdict in graded)),
            "marks_listed": listed,
            "marks_supported": sum(verdict["citations_supported"] for verdict in graded),
            "marks_unlisted": sum(item["marks_unlisted"] for item in mine),
            "context_has_answer": sum(verdict["context_has_answer"] for verdict in graded),
            # "full" or "partial" where the documents hold no answer: bad by ``classify``.
            "answer_without_context": sum(
                verdict["answers_question"] in ("full", "partial")
                and not verdict["context_has_answer"]
                for verdict in graded
            ),
        }
    level = {name: index for index, name in enumerate(reversed(CLASSES))}
    pairs = [
        (level[classify(valid[item["retest_of"]])], level[classify(valid[item["item_id"]])])
        for item in plan["items"]
        if "retest_of" in item and item["item_id"] in valid and item["retest_of"] in valid
    ]
    return {
        "runs": plan["runs"],
        "per_run": per_run,
        "retest": {
            "pairs": len(pairs),
            "same_class": sum(a == b for a, b in pairs),
            "quadratic_kappa": quadratic_kappa(pairs, len(CLASSES)),
        },
        "requests_valid": len(valid),
    }


def _isolated_sender(timeout_s: float) -> Sender:
    executable = os.environ.get("RAG_JUDGE_CLAUDE_CLI", "").strip() or isolated.find_cli()
    if executable is None:
        raise SystemExit("Claude CLI is not installed")

    def send(system_prompt: str, message: str) -> Any:
        return isolated.send(executable, system_prompt, message, timeout_s=timeout_s)

    return send


def _references(path: Path | None) -> dict[str, list[str]]:
    if path is None:
        return {}
    references: dict[str, list[str]] = {}
    for row in _read_jsonl(path):
        if row["case_id"] in references:
            raise ValueError(f"{path.name}: {row['case_id']} stands twice")
        references[row["case_id"]] = [str(answer) for answer in row.get("reference_answers") or []]
    return references


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan")
    plan_parser.add_argument("--run", action="append", required=True, metavar="LABEL=DIR")
    plan_parser.add_argument("--references", type=Path)
    plan_parser.add_argument("--withhold-references", action="store_true")
    plan_parser.add_argument("--retest", type=int, default=RETEST_SIZE)
    plan_parser.add_argument("--out", type=Path, required=True)
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
        runs: dict[str, Path] = {}
        for spec in args.run:
            label, _, path = spec.partition("=")
            if not label or not path or label in runs:
                raise SystemExit(f"--run {spec}: give each run once as LABEL=DIR")
            runs[label] = Path(path)
        if args.withhold_references and args.references is None:
            raise SystemExit("--withhold-references names the file it withholds: give --references")
        references = _references(args.references)
        plan = build_plan(
            runs,
            {} if args.withhold_references else references,
            retest=args.retest,
            references_sha256=(
                hashlib.sha256(args.references.read_bytes()).hexdigest()
                if args.references
                else None
            ),
            withheld=args.withhold_references,
        )
        args.out.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", "utf-8")
        asked = sum("message" in item for item in plan["items"])
        print(f"{asked} requests planned in {plan_path}")
        return 0
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
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

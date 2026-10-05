"""Repair the cases a first verification rejected, one stateless request a case.

    python -m scripts.devset_label_repair plan --set development
    python -m scripts.devset_label_repair repair --set development [--limit N]
    python -m scripts.devset_label_repair build --set development
    python -m scripts.devset_label_repair check --set development

The protocol is change 4 of rubric label-verification/v3 in
docs/specs/semantic-precision-metrics.md; evaluation/devset_repair.py holds the repair prompt
and the rules a reply must pass. The sets are those of scripts/devset_label_verify.py that are
verified under v3.

plan reads round 1 of the set and writes <set dir>/repair/plan.json: per rejected case the
SHA-256 of its request and the supplement the request adds - the bounds of the repair and the
two labels the verifier's request does not show. The request text is not written anywhere:
repair rebuilds it from the same inputs - the verifier's request, the verifier's stored reply
and the supplement - and refuses inputs that no longer give the plan. A rejected case without
spans whose rejection includes check 5a or 5b gets no request: no repair answers it, and the
plan lists it apart.

repair sends the planned requests by the isolated route and appends every reply, with the
record of its session, to <set dir>/repair/claude-opus-5-5.jsonl; a rerun resumes by case. A
reply the script refuses is asked for again with the refusal, three attempts in all. The Claude
CLI may be named in RAG_VERIFY_CLAUDE_CLI; it is not printed or stored.

build writes <set dir>/repairs.jsonl and <set dir>/drops.json, the inputs of round 2: the
repaired cases, the drops the model declared, and a drop on the ground repair_not_possible for
every case that got no request and for every case that three replies left without a valid
repair. check recomputes both from the plan and the store, refuses files that differ, and
refuses a round 2 planned on other files.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, TextIO

from evaluation import devset
from evaluation import devset_drafting as drafting
from evaluation import devset_repair as repair
from evaluation import isolated_request as isolated
from evaluation import label_verification as lv
from evaluation.blinded_judge_clients import JudgeUnavailable
from evaluation.devset_sources import corpus_directory, read_sources
from scripts import devset_label_verify as v

PLAN_VERSION = 1
STORE = f"{repair.AUTHOR['model']}.jsonl"
# What a row of the store says of its reply: it gives a repair or a declared drop; the script
# refused it; the route did not answer.
STATUSES = ("valid", "invalid", "unavailable")
OUTCOMES = ("repaired", "dropped")


@dataclass(frozen=True)
class Inputs:
    """What the repairs of one set are written from; nothing here is rewritten."""

    drafts: v.Drafts
    rounds: v.RoundInputs
    round_1: Path


@dataclass(frozen=True)
class Held:
    """What every reply of a pass is held against, computed once.

    `cases` are the revisions round 1 checked; `pseudonyms`, per case, is the map of the
    verifier's request, pseudonym to document, `supplied` the documents a text of which that
    request supplies, and `scanned` the places of the scan passages it shows.
    """

    texts: dict[str, str]
    frame: devset.SourceFrame
    family_map: dict[str, str]
    masker: lv.Masker
    cases: dict[str, dict[str, Any]]
    pseudonyms: dict[str, dict[str, str]]
    supplied: dict[str, list[str]]
    scanned: dict[str, list[dict[str, Any]]]


def build_plan(inputs: Inputs) -> tuple[dict[str, Any], dict[str, str], Held]:
    """Check round 1 of a set; return the plan of its repairs and the request texts by case."""
    drafts = inputs.drafts
    if drafts.rubric != lv.RUBRIC_V3:
        raise ValueError("a repair by request is of rubric label-verification/v3")
    if repair.prompt_sha256() != repair.PROMPT_SHA256:
        raise ValueError("the repair prompt is not the registered one")
    first = v.load_round(inputs.round_1, drafts)
    rebuilt, sent = v.build_round(drafts, replace(inputs.rounds, round=1))
    if first.plan["round"] != 1 or rebuilt != first.plan:
        raise ValueError("the inputs no longer rebuild the plan of round 1")
    undecided = sum(decision["outcome"] == "none" for decision in first.decisions.values())
    if undecided:
        raise ValueError(f"round 1 is not complete: {undecided} cases have no valid verdict")
    (name,) = first.plan["verifiers"]
    replies = {
        row["case_id"]: row["raw_reply"] for row in first.stores[name] if row["status"] == "valid"
    }
    source_texts = read_sources(drafts.corpus, inputs.rounds.corpus_dir)
    _, scan, chunks = v.read_scan(inputs.rounds)
    requests = []
    without_request = []
    texts = {}
    pseudonyms = {}
    supplied = {}
    scanned = {}
    for request in first.plan["requests"]:
        case_id = request["case_id"]
        decision = first.decisions[case_id]
        if decision["outcome"] != "rejected":
            continue
        case = first.revisions[case_id]
        if lv.no_repair_request(case, decision):
            # No repair answers the rejection: the case is dropped here, and nothing is asked.
            without_request.append(
                {
                    "case_id": case_id,
                    "rejecting_checks": [row["check"] for row in decision["rejecting_checks"]],
                }
            )
            continue
        pseudonyms[case_id] = dict(request["pseudonyms"])
        supplied[case_id] = repair.supplied_documents(sent[case_id])
        # The passages the verifier's request shows, at their places: a new span is held to them.
        passages = lv.scan_passages(case, scan, chunks) if lv.needs_scan(case) else []
        scanned[case_id] = repair.passage_regions(passages, source_texts)
        added = repair.supplement(
            case,
            pseudonyms[case_id],
            supplied[case_id],
            drafts.barred,
            not drafts.holdout,
        )
        # The verifier saw no file name; should its reply still write one, it does not go back.
        texts[case_id] = repair.build_request(
            sent[case_id], drafting.unnamed(replies[case_id], source_texts), added
        )
        requests.append(
            {
                "case_id": case_id,
                "request_sha256": lv.sha256_text(texts[case_id]),
                "characters": len(texts[case_id]),
                "verifier_request_sha256": request["request_sha256"],
                "verifier_reply_sha256": lv.sha256_text(replies[case_id]),
                "supplement": added,
            }
        )
    plan = {
        "plan_version": PLAN_VERSION,
        "repair_version": repair.REPAIR_VERSION,
        "prompt_sha256": repair.PROMPT_SHA256,
        "rubric_version": drafts.rubric,
        "author": repair.AUTHOR,
        "route": isolated.ROUTE,
        "settings": isolated.settings(repair.SYSTEM_PROMPT),
        "inputs": {
            **{key: first.plan["inputs"][key] for key in v.BOUND_INPUTS},
            "round_1_plan_sha256": first.plan_sha256,
            "round_1_stores_sha256": first.store_sha256,
        },
        "requests": requests,
        "without_request": without_request,
    }
    held = Held(
        source_texts,
        devset.source_frame(source_texts),
        devset.document_families(drafts.register),
        lv.Masker(source_texts),
        {request["case_id"]: first.revisions[request["case_id"]] for request in requests},
        pseudonyms,
        supplied,
        scanned,
    )
    # The plan is compared with the one read back from plan.json: keep it what JSON gives.
    return json.loads(json.dumps(plan, ensure_ascii=False, allow_nan=False)), texts, held


def load_plan(out: Path) -> dict[str, Any]:
    """Read plan.json; refuse a plan of another version, repair version or prompt."""
    plan: dict[str, Any] = v.read_json(out / "plan.json")
    if not isinstance(plan, dict) or plan.get("plan_version") != PLAN_VERSION:
        raise ValueError("plan_version is not supported")
    if plan.get("repair_version") != repair.REPAIR_VERSION:
        raise ValueError("the plan is of another repair version")
    if plan.get("prompt_sha256") != repair.PROMPT_SHA256:
        raise ValueError("the plan is of another prompt")
    try:
        planned = [request["case_id"] for request in plan["requests"]]
        planned += [row["case_id"] for row in plan["without_request"]]
    except (KeyError, TypeError):
        raise ValueError("plan.json does not hold a plan") from None
    if len(set(planned)) != len(planned):
        raise ValueError("a case is planned twice")
    return plan


def read_store(out: Path, plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Read the replies; refuse a row that `repair` does not write for this plan.

    The attempt of a row is one more than the refused replies before it, three in all, and
    nothing follows a valid reply. A reply that counts or was refused carries the record of a
    session that loaded nothing.
    """
    path = out / STORE
    if not path.exists():
        return []
    planned = {request["case_id"]: request for request in plan["requests"]}
    rows = v.read_jsonl(path)
    invalid: Counter[str] = Counter()
    closed: set[str] = set()
    for row in rows:
        identity = row.get("case_id")
        request = planned.get(identity) if isinstance(identity, str) else None
        if (
            not isinstance(identity, str)
            or request is None
            or row.get("base_request_sha256") != request["request_sha256"]
            or row.get("prompt_sha256") != plan["prompt_sha256"]
            or row.get("repair_version") != plan["repair_version"]
            or row.get("status") not in STATUSES
        ):
            raise ValueError(f"the store holds a row that is not of this plan ({identity})")
        if (
            identity in closed
            or invalid[identity] >= repair.ATTEMPTS
            or type(row.get("attempt")) is not int
            or row["attempt"] != invalid[identity] + 1
        ):
            raise ValueError(f"the store holds attempts that repair does not write: {identity}")
        if row["status"] == "unavailable":
            continue
        if row.get("model") != plan["author"]["model"]:
            raise ValueError(f"a stored reply is not of the registered model: {identity}")
        try:
            isolated.check_record(row.get("session"))
        except ValueError as exc:
            raise ValueError(f"a stored reply the route does not vouch for: {exc}") from None
        if row["status"] == "valid":
            closed.add(identity)
        else:
            invalid[identity] += 1
    return rows


def request_text(base: str, earlier: Sequence[Mapping[str, Any]], masker: lv.Masker) -> str:
    """The text of the next attempt of one case, given its refused replies so far.

    The refusal is the one part of a later attempt the script writes knowing the file names:
    one that still reads as naming a file is not sent, and the fixed sentence of
    `drafting.UNQUOTABLE` goes in its place. The refused reply goes back as given; its author
    was shown no file name.
    """
    refused = [row for row in earlier if row["status"] == "invalid"]
    if not refused:
        return base
    refusal = drafting.quoted_refusal(refused[-1]["error"], masker)
    return repair.retry_text(base, refusal, refused[-1]["raw_reply"])


def check_chain(
    rows: Sequence[Mapping[str, Any]], texts: Mapping[str, str], masker: lv.Masker
) -> None:
    """Refuse a store one of whose replies answers a text other than the one its row names."""
    seen: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        earlier = seen.setdefault(row["case_id"], [])
        expected = lv.sha256_text(request_text(texts[row["case_id"]], earlier, masker))
        if row.get("request_sha256") != expected:
            raise ValueError(f"a stored reply is not to the request of its row: {row['case_id']}")
        earlier.append(row)


def outcome_of(
    reply: str, request: Mapping[str, Any], drafts: v.Drafts, held: Held
) -> tuple[str, dict[str, Any]]:
    """What one reply gives: ("repaired", the case) or ("dropped", the declared drop).

    ReplyFormatError or DraftRefused says what the reply must change; the words are those that
    go back to the model, so nothing in them names a file.
    """
    case_id = request["case_id"]
    case = held.cases[case_id]
    pseudonyms = held.pseudonyms[case_id]
    kind, value = repair.parse_reply(reply)
    try:
        if kind == "drop":
            drop = repair.drop_of(value, case_id, pseudonyms, request["supplement"])
            problem = drafts.drop_problem(drop)
            if problem:
                raise drafting.DraftRefused(problem)
            return "dropped", drop
        version = drafts.corpus["corpus_sha256"]
        built = repair.build_case(
            value,
            case,
            pseudonyms,
            held.supplied[case_id],
            held.texts,
            drafts.revisions,
            version,
            held.frame,
            held.scanned[case_id],
        )
        repair.check_case(
            built,
            case,
            pseudonyms,
            drafts.author,
            drafts.barred,
            held.texts,
            held.frame,
            drafts.revisions,
            version,
            held.family_map,
            held.masker,
        )
        # What `plan --round 2` asks of a repair, asked here, while the model can still answer.
        problem = v.repair_problem(drafts, built)
        if problem:
            raise drafting.DraftRefused(problem)
    except drafting.DraftRefused as exc:
        raise drafting.DraftRefused(drafting.unnamed(str(exc), held.texts, held.masker)) from None
    return "repaired", built


def attempt(
    client: Any,
    text: str,
    row: dict[str, Any],
    request: Mapping[str, Any],
    drafts: v.Drafts,
    held: Held,
) -> dict[str, Any]:
    """Send one request once; the row holds the reply as given, or the code of the failure."""
    start = time.monotonic()
    blank: dict[str, Any] = {
        "outcome": None,
        "model": None,
        "raw_reply": None,
        "usage": {},
        "session": None,
    }
    try:
        reply = client.grade(text)
    except JudgeUnavailable as exc:
        elapsed = round(time.monotonic() - start, 3)
        return {**row, "status": "unavailable", **blank, "elapsed_s": elapsed, "error": exc.code}
    answered = {
        "outcome": None,
        "model": reply.model,
        "raw_reply": reply.text,
        "usage": v.usage_counts(reply.usage),
        "session": getattr(reply, "session", None),
        "elapsed_s": round(reply.elapsed_s, 3),
    }
    failure = None
    if reply.model != repair.AUTHOR["model"]:
        failure = "model_mismatch"
    else:
        try:
            isolated.check_record(answered["session"])
        except ValueError:
            failure = "session_record"
    if failure is not None:
        # Not a reply of the route: it is no repair and is not kept.
        return {
            **row,
            "status": "unavailable",
            **blank,
            "model": reply.model,
            "elapsed_s": answered["elapsed_s"],
            "error": failure,
        }
    try:
        kind, _ = outcome_of(reply.text, request, drafts, held)
    except (lv.ReplyFormatError, drafting.DraftRefused) as exc:
        return {**row, "status": "invalid", **answered, "error": str(exc)}
    return {**row, "status": "valid", **answered, "outcome": kind, "error": None}


def run_repairs(
    out: Path, inputs: Inputs, *, client: Any = None, limit: int | None = None
) -> dict[str, Any]:
    """Send the planned requests; resume by case; stop when the route is unavailable."""
    plan = load_plan(out)
    rebuilt, texts, held = build_plan(inputs)
    if rebuilt != plan:
        raise ValueError("the inputs no longer rebuild the plan of these repairs")
    rows = read_store(out, plan)
    check_chain(rows, texts, held.masker)
    if client is None:
        client = v.isolated_client(repair.AUTHOR["model"], repair.SYSTEM_PROMPT)
    store = out / STORE
    taken = sent = 0
    unavailable: str | None = None
    with ExitStack() as opened:
        handle: TextIO | None = None
        for request in plan["requests"]:
            identity = request["case_id"]
            mine = [row for row in rows if row["case_id"] == identity]
            refused = sum(row["status"] == "invalid" for row in mine)
            if any(row["status"] == "valid" for row in mine) or refused >= repair.ATTEMPTS:
                continue
            if unavailable is not None or (limit is not None and taken >= limit):
                break
            taken += 1
            if handle is None:
                # Opened before the first request: no reply is asked for that cannot be kept.
                handle = opened.enter_context(store.open("a", encoding="utf-8", newline="\n"))
            while refused < repair.ATTEMPTS:
                text = request_text(texts[identity], mine, held.masker)
                row = attempt(
                    client,
                    text,
                    {
                        "case_id": identity,
                        "attempt": refused + 1,
                        "request_sha256": lv.sha256_text(text),
                        "base_request_sha256": request["request_sha256"],
                        "prompt_sha256": plan["prompt_sha256"],
                        "repair_version": plan["repair_version"],
                    },
                    request,
                    inputs.drafts,
                    held,
                )
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                rows.append(row)
                mine.append(row)
                sent += 1
                v.emit(f"{identity} attempt {row['attempt']}: {row['error'] or row['outcome']}")
                if row["status"] == "valid":
                    break
                if row["status"] == "unavailable":
                    unavailable = row["error"]
                    break
                refused += 1
    return {**progress(plan, rows), "sent": sent, "unavailable": unavailable}


def progress(plan: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Where the repairs stand: a case is closed by a valid reply or by three refused ones.

    A case the plan gives no request is dropped from the start and is counted apart.
    """
    outcomes = {row["case_id"]: row["outcome"] for row in rows if row["status"] == "valid"}
    refused = Counter(row["case_id"] for row in rows if row["status"] == "invalid")
    exhausted = [
        request["case_id"]
        for request in plan["requests"]
        if request["case_id"] not in outcomes and refused[request["case_id"]] >= repair.ATTEMPTS
    ]
    counts = Counter(outcomes.values())
    return {
        "requests": len(plan["requests"]),
        "repaired": counts["repaired"],
        "dropped_by_declaration": counts["dropped"],
        "dropped_without_valid_repair": len(exhausted),
        "dropped_without_request": len(plan["without_request"]),
        "pending": len(plan["requests"]) - len(outcomes) - len(exhausted),
    }


def outputs(out: Path, inputs: Inputs) -> tuple[bytes, bytes, dict[str, Any]]:
    """The repaired cases and the declared drops, as the plan, the store and the corpus give them."""
    plan = load_plan(out)
    rebuilt, texts, held = build_plan(inputs)
    if rebuilt != plan:
        raise ValueError("the inputs no longer rebuild the plan of these repairs")
    rows = read_store(out, plan)
    check_chain(rows, texts, held.masker)
    state = progress(plan, rows)
    if state["pending"]:
        raise ValueError(f"{state['pending']} rejected cases have no reply yet")
    repairs: list[dict[str, Any]] = []
    # The drops the script writes itself come first, then those of the requests in their order.
    drops: list[dict[str, Any]] = [
        {"case_id": row["case_id"], "ground": lv.NO_REPAIR_DROP, "reason": lv.NO_SPAN_AUTHORITY}
        for row in plan["without_request"]
    ]
    for request in plan["requests"]:
        identity = request["case_id"]
        valid = [row for row in rows if row["case_id"] == identity and row["status"] == "valid"]
        if not valid:
            drops.append(
                {"case_id": identity, "ground": lv.NO_REPAIR_DROP, "reason": repair.NO_VALID_REPAIR}
            )
            continue
        try:
            kind, value = outcome_of(valid[0]["raw_reply"], request, inputs.drafts, held)
        except (lv.ReplyFormatError, drafting.DraftRefused) as exc:
            raise ValueError(
                f"a stored reply no longer passes the script: {identity} ({exc})"
            ) from None
        if kind != valid[0]["outcome"]:
            raise ValueError(f"a stored reply is not what its row says: {identity}")
        (repairs if kind == "repaired" else drops).append(value)
    return v.jsonl(repairs), v.dump(drops), state


def build(out: Path, inputs: Inputs, repairs: Path, drops: Path) -> dict[str, Any]:
    repairs_bytes, drops_bytes, state = outputs(out, inputs)
    for path, data in ((repairs, repairs_bytes), (drops, drops_bytes)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return state


def check(
    out: Path, inputs: Inputs, repairs: Path, drops: Path, round_2: Path | None = None
) -> dict[str, Any]:
    """Recompute the repairs and the drops and refuse files, or a round 2, that differ."""
    repairs_bytes, drops_bytes, state = outputs(out, inputs)
    if repairs.read_bytes() != repairs_bytes:
        raise ValueError("the repairs are not what the plan and the store give")
    if drops.read_bytes() != drops_bytes:
        raise ValueError("the declared drops are not what the plan and the store give")
    if round_2 is not None and (round_2 / "plan.json").exists():
        planned = v.load_plan(round_2)["inputs"]
        if planned.get("repairs_sha256") != v.sha256_bytes(repairs_bytes) or planned.get(
            "drops_sha256"
        ) != v.sha256_bytes(drops_bytes):
            raise ValueError("round 2 is not planned on these repairs and declared drops")
    return {"status": "ok", **state}


def main(argv: list[str] | None = None) -> int:
    """Run one command and return the process exit status; a refusal is exit 2."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=("plan", "repair", "build", "check"))
    parser.add_argument("--set", choices=sorted(set(v.SETS) - {"pilot"}), required=True)
    parser.add_argument("--corpus-dir", type=Path)
    parser.add_argument("--scan", type=Path)
    parser.add_argument("--archive", type=Path, default=v.ARCHIVE)
    parser.add_argument("--limit", type=int)
    arguments = parser.parse_args(argv)
    try:
        return run(arguments)
    except OSError as exc:
        named = f": {Path(exc.filename).name}" if exc.filename else ""
        v.emit(f"refused: a file cannot be read or written{named}")
    except ValueError as exc:
        v.emit(f"refused: {exc}")
    return 2


def run(arguments: argparse.Namespace) -> int:
    base = v.SETS[arguments.set].base
    out = base / "repair"
    inputs = Inputs(
        v.load_set(arguments.set),
        v.RoundInputs(
            round=1,
            corpus_dir=arguments.corpus_dir or corpus_directory(),
            scan=arguments.scan or base / "wide-scan.json",
            archive=arguments.archive,
        ),
        base / "round-1",
    )
    repairs, drops = base / "repairs.jsonl", base / "drops.json"
    if arguments.command == "plan":
        plan, _, _ = build_plan(inputs)
        v.write_plan(out, plan)
        v.emit(
            json.dumps(
                {
                    "set": arguments.set,
                    "requests": len(plan["requests"]),
                    "without_request": len(plan["without_request"]),
                    "characters": sum(request["characters"] for request in plan["requests"]),
                },
                ensure_ascii=False,
            )
        )
        return 0
    if arguments.command == "repair":
        result = run_repairs(out, inputs, limit=arguments.limit)
        v.emit(json.dumps(result, ensure_ascii=False))
        return 0 if not result["pending"] else 1
    if arguments.command == "build":
        result = build(out, inputs, repairs, drops)
    else:
        result = check(out, inputs, repairs, drops, base / "round-2")
    v.emit(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

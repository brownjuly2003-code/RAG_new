"""Write the drafts of plan step 1.3d, one stateless request a position.

    python -m scripts.devset_draft plan --split development
    python -m scripts.devset_draft draft --split development [--limit N]
    python -m scripts.devset_draft build --split development
    python -m scripts.devset_draft check --split development

The protocol is rubric label-verification/v3 of docs/specs/semantic-precision-metrics.md
(change 3) and the section «Drafts of plan step 1.3d» there; evaluation/devset_drafting.py
holds the generator prompt, the brief rule and the rules a reply must pass.

plan writes <dir>/plan.json: per position its brief, the sections and the SHA-256 of the
request. The request text is not written anywhere: draft rebuilds it from the corpus and the
registered split and refuses inputs that no longer give the plan.

draft sends the planned requests by the isolated route and appends every reply, with the
record of its session, to <dir>/claude-opus-5-5.jsonl; a rerun resumes by position. A reply the
script refuses is asked for again with the refusal, which names no file, three attempts in all;
a position left without a valid reply stays empty, and so does one whose reply declares that
its sections give no case (NO CASE). The Claude CLI may be named in RAG_VERIFY_CLAUDE_CLI; it is
not printed or stored.

build writes the drafts and their manifest from the plan and the store; check recomputes both
and refuses files that differ. A draft is `agent_labelled` and unchecked.

With --replacements every command works on the replacements of the split: one draft for each
draft that the first verification of the split dropped, seated by the rule `replacement` of
the registered split and asked for what the dropped draft was. They are read from the drafts
and from the register of that verification, which must be complete, and are kept apart:
evaluation/devset_<split>_replacements.jsonl, with the plan in <dir>-replacements. A place the
rule seats nowhere is listed in the plan and the manifest as unseated. The replacements of
development wait for the register of `pilot-v3` as well: a dropped case of that set is replaced
with them, and its seating is registered and not written here, so they are refused while it
holds one.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from evaluation import devset, devset_split
from evaluation import devset_drafting as drafting
from evaluation import isolated_request as isolated
from evaluation import label_verification as lv
from evaluation.blinded_judge_clients import JudgeUnavailable
from evaluation.devset_sources import corpus_directory, read_sources
from scripts.devset_label_verify import (
    CLI_TIMEOUT_S,
    dump,
    emit,
    jsonl,
    read_json,
    read_jsonl,
    sha256_bytes,
    usage_counts,
    write_plan,
)

ROOT = Path(__file__).resolve().parent.parent
EVALUATION = ROOT / "evaluation"
BASE = ROOT / "reports" / "devset" / "drafts"
PLAN_VERSION = 1
MANIFEST_VERSION = "devset-drafts/v1"
STORE = f"{drafting.AUTHOR['model']}.jsonl"
# What a row of the store says of its reply: it gives a case; the script refused it; the model
# declared that the sections give no case; the route did not answer.
STATUSES = ("valid", "invalid", "declined", "unavailable")
# After these nothing more is asked of a position.
CLOSING = ("valid", "declined")


def _kind(replacement: bool) -> str:
    return "replacements" if replacement else "drafts"


def drafts_path(split: str, replacement: bool = False) -> Path:
    return EVALUATION / f"devset_{split}_{_kind(replacement)}.jsonl"


def manifest_path(split: str, replacement: bool = False) -> Path:
    return EVALUATION / f"devset_{split}_{_kind(replacement)}.manifest.json"


def checks_path(split: str) -> Path:
    """The register of the first verification of a split: what its replacements start from."""
    return EVALUATION / f"devset_{split}_label_checks.json"


def pilot_register() -> bytes:
    """The register of `pilot-v3`, read for the replacements of development; refuse to go on.

    A dropped case of `pilot-v3` is replaced with the dropped drafts of development and is
    seated after them. So nothing of development is replaced before that register is complete,
    and nothing while it holds a dropped case: this tool does not seat one yet.
    """
    try:
        data = checks_path("pilot_v3").read_bytes()
    except OSError:
        raise ValueError("the verification of pilot-v3 is not complete: no register") from None
    checks = json.loads(data)
    if not checks.get("complete"):
        raise ValueError("the verification of pilot-v3 is not complete")
    dropped = sorted(entry["case_id"] for entry in checks["cases"] if entry["state"] == "dropped")
    if dropped:
        raise ValueError(
            "pilot-v3 holds dropped cases, and their seating is registered and not written: "
            + ", ".join(dropped)
        )
    return data


def out_dir(split: str, replacement: bool = False) -> Path:
    return BASE / (f"{split}-replacements" if replacement else split)


@dataclass(frozen=True)
class Inputs:
    """What the drafts of one split are written from; nothing here is rewritten."""

    split: str
    texts: dict[str, str]
    corpus: dict[str, Any]
    register: dict[str, Any]
    places: list[dict[str, Any]]
    briefs: list[dict[str, Any]]
    bound: dict[str, str]
    replacement: bool = False

    @property
    def revisions(self) -> dict[str, str]:
        return {entry["name"]: entry["sha256"] for entry in self.corpus["files"]}


def outcomes(
    split: str,
    places: Sequence[Mapping[str, Any]],
    drafts: Mapping[str, Mapping[str, Any]],
    checks: Mapping[str, Any],
) -> tuple[dict[int, str], dict[int, Mapping[str, Any]]]:
    """What the first verification left of every seated position, and the dropped drafts.

    A position whose draft the register calls verified is confirmed, one whose draft it calls
    dropped is dropped, and one that has no draft is empty. Replacements are made only when
    every draft is one or the other.
    """
    if not checks.get("complete"):
        raise ValueError("the first verification of the split is not complete")
    states = {entry["case_id"]: entry["state"] for entry in checks["cases"]}
    if set(states) != set(drafts):
        raise ValueError("the register of the first verification is not of these drafts")
    left: dict[int, str] = {}
    dropped: dict[int, Mapping[str, Any]] = {}
    for place in places:
        if place["seed"] is None:
            continue
        identity = drafting.case_id(split, place["position"])
        if identity not in drafts:
            left[place["position"]] = "empty"
        elif states[identity] == "dropped":
            left[place["position"]] = "dropped"
            dropped[place["position"]] = drafts[identity]
        else:
            left[place["position"]] = "confirmed"
    return left, dropped


def load_inputs(split: str, corpus_dir: Path | None = None, *, replacement: bool = False) -> Inputs:
    """Read the corpus, the family map and the registered positions of one split.

    With `replacement` the positions are those of the dropped drafts, seated again by the
    rule `replacement` of the registered split on what the first verification left; each is
    asked for the class, the style, the trap and the action of the draft it replaces. Those of
    development are bound to the register of `pilot-v3` as well.
    """
    corpus = read_json(EVALUATION / "aircargo_corpus.manifest.json")
    try:
        texts = read_sources(corpus, corpus_dir or corpus_directory())
    except OSError:
        raise ValueError("the corpus is not the registered version: a file is missing") from None
    families = (EVALUATION / "document_families.json").read_bytes()
    registered_bytes = (EVALUATION / "devset_split.json").read_bytes()
    registered = json.loads(registered_bytes)
    bound = {
        "split_sha256": sha256_bytes(registered_bytes),
        "corpus_sha256": corpus["corpus_sha256"],
        "families_sha256": sha256_bytes(families),
    }
    if any(registered["inputs"][key] != bound[key] for key in ("corpus_sha256", "families_sha256")):
        raise ValueError("the registered split is not of this corpus and family map")
    places = registered["splits"][split]["positions"]
    if not replacement:
        briefs = drafting.briefs(split, places)
    else:
        pilot = pilot_register() if split == "development" else None
        drafts_bytes = drafts_path(split).read_bytes()
        checks_bytes = checks_path(split).read_bytes()
        checks = json.loads(checks_bytes)
        if checks["sha256"]["drafts"] != sha256_bytes(drafts_bytes):
            raise ValueError("the register of the first verification is not of these drafts")
        drafts = {case["case_id"]: case for case in read_jsonl(drafts_path(split))}
        left, dropped = outcomes(split, places, drafts, checks)
        places = devset_split.replacements(split, registered, texts, left)
        briefs = drafting.replacement_briefs(split, places, dropped)
        bound = {
            **bound,
            "drafts_sha256": sha256_bytes(drafts_bytes),
            "label_checks_sha256": sha256_bytes(checks_bytes),
        }
        if pilot is not None:
            bound["pilot_v3_label_checks_sha256"] = sha256_bytes(pilot)
    return Inputs(
        split=split,
        texts=texts,
        corpus=corpus,
        register=json.loads(families),
        places=places,
        briefs=briefs,
        bound=bound,
        replacement=replacement,
    )


@dataclass(frozen=True)
class Rules:
    """What every reply of a pass is held against, computed once."""

    frame: devset.SourceFrame
    family_map: dict[str, str]
    masker: lv.Masker


def rules(inputs: Inputs) -> Rules:
    return Rules(
        devset.source_frame(inputs.texts),
        devset.document_families(inputs.register),
        lv.Masker(inputs.texts),
    )


def build_plan(inputs: Inputs) -> tuple[dict[str, Any], dict[str, str]]:
    """Check the inputs of one split; return its plan and the request texts by case id.

    A place without a section - the order of the split had none left for it - gets no request
    and is listed as unseated.
    """
    if drafting.prompt_sha256() != drafting.PROMPT_SHA256:
        raise ValueError("the generator prompt is not the registered one")
    masker = lv.Masker(inputs.texts)
    requests = []
    unseated = []
    texts = {}
    for brief, place in zip(inputs.briefs, inputs.places, strict=True):
        if place["seed"] is None:
            unseated.append(place["position"])
            continue
        request = drafting.build_request(brief, place, inputs.texts, masker)
        texts[brief["case_id"]] = request.text
        requests.append(
            {
                **brief,
                "block_id": place["block_id"],
                "seed": place["seed"],
                "partner": place["partner"],
                "request_sha256": request.sha256,
                "pseudonyms": request.pseudonyms,
                "characters": request.characters,
            }
        )
    plan = {
        "plan_version": PLAN_VERSION,
        "generator_version": drafting.GENERATOR_VERSION,
        "prompt_sha256": drafting.PROMPT_SHA256,
        "author": drafting.AUTHOR,
        "route": isolated.ROUTE,
        "settings": isolated.settings(drafting.SYSTEM_PROMPT),
        "split": inputs.split,
        "replacement": inputs.replacement,
        "as_of": drafting.AS_OF,
        "brief_rule": drafting.BRIEF_RULE,
        "inputs": inputs.bound,
        "unseated_positions": unseated,
        "requests": requests,
    }
    # The plan is compared with the one read back from plan.json: keep it what JSON gives.
    return json.loads(json.dumps(plan, ensure_ascii=False, allow_nan=False)), texts


def load_plan(out: Path) -> dict[str, Any]:
    """Read plan.json; refuse a plan of another version, generator or prompt."""
    plan: dict[str, Any] = read_json(out / "plan.json")
    if not isinstance(plan, dict) or plan.get("plan_version") != PLAN_VERSION:
        raise ValueError("plan_version is not supported")
    if plan.get("generator_version") != drafting.GENERATOR_VERSION:
        raise ValueError("the plan is of another generator version")
    if plan.get("prompt_sha256") != drafting.PROMPT_SHA256:
        raise ValueError("the plan is of another prompt")
    try:
        planned = [request["case_id"] for request in plan["requests"]]
    except (KeyError, TypeError):
        raise ValueError("plan.json does not hold a plan") from None
    if len(set(planned)) != len(planned):
        raise ValueError("a position is planned twice")
    return plan


def read_store(out: Path, plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Read the replies; refuse a row that `draft` does not write for this plan.

    The attempt of a row is one more than the refused replies before it, three in all, and
    nothing follows a valid reply or one that declares no case. A reply that counts, was
    refused or declares no case carries the record of a session that loaded nothing.
    """
    path = out / STORE
    if not path.exists():
        return []
    planned = {request["case_id"]: request for request in plan["requests"]}
    rows = read_jsonl(path)
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
            or row.get("generator_version") != plan["generator_version"]
            or row.get("status") not in STATUSES
        ):
            raise ValueError(f"the store holds a row that is not of this plan ({identity})")
        if (
            identity in closed
            or invalid[identity] >= drafting.ATTEMPTS
            or row.get("attempt") != invalid[identity] + 1
        ):
            raise ValueError(f"the store holds attempts that draft does not write: {identity}")
        if row["status"] == "unavailable":
            continue
        if row.get("model") != plan["author"]["model"]:
            raise ValueError(f"a stored reply is not of the registered model: {identity}")
        try:
            isolated.check_record(row.get("session"))
        except ValueError as exc:
            raise ValueError(f"a stored reply the route does not vouch for: {exc}") from None
        if row["status"] == "declined" and drafting.declined(row.get("raw_reply") or "") is None:
            raise ValueError(f"a stored reply declares no case and does not say so: {identity}")
        if row["status"] in CLOSING:
            closed.add(identity)
        else:
            invalid[identity] += 1
    return rows


def request_text(base: str, earlier: Sequence[Mapping[str, Any]], masker: lv.Masker) -> str:
    """The text of the next attempt of one position, given its refused replies so far.

    The refusal is the one part of a later attempt the script writes knowing the file names:
    one that still reads as naming a file is not sent, and the fixed sentence of
    `drafting.UNQUOTABLE` goes in its place. The refused reply goes back as given; its author
    was shown no file name.
    """
    refused = [row for row in earlier if row["status"] == "invalid"]
    if not refused:
        return base
    refusal = drafting.quoted_refusal(refused[-1]["error"], masker)
    return drafting.retry_text(base, refusal, refused[-1]["raw_reply"])


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


def case_of(reply: str, request: Mapping[str, Any], inputs: Inputs, held: Rules) -> dict[str, Any]:
    """The case one reply gives, or ReplyFormatError / DraftRefused with what must change.

    The words of a refusal are those that go back to the generator, so nothing in them names
    a file.
    """
    label = drafting.parse_reply(reply)
    revisions = inputs.revisions
    version = inputs.corpus["corpus_sha256"]
    try:
        case = drafting.build_case(label, request, request, inputs.texts, revisions, version)
        drafting.check_case(
            case,
            request,
            inputs.texts,
            held.frame,
            revisions,
            version,
            held.family_map,
            held.masker,
        )
    except drafting.DraftRefused as exc:
        raise drafting.DraftRefused(drafting.unnamed(str(exc), inputs.texts, held.masker)) from None
    return case


class GeneratorClient:
    """The route of a draft: one request is one new session that loads nothing."""

    def __init__(self, executable: str | None = None, timeout_s: float = CLI_TIMEOUT_S) -> None:
        self.executable = executable
        self.timeout_s = timeout_s

    def send(self, text: str) -> isolated.IsolatedReply:
        executable = self.executable or isolated.find_cli()
        if executable is None:
            raise JudgeUnavailable("cli_missing", "Claude CLI is not installed")
        return isolated.send(executable, drafting.SYSTEM_PROMPT, text, timeout_s=self.timeout_s)


def attempt(
    client: Any,
    text: str,
    row: dict[str, Any],
    request: Mapping[str, Any],
    inputs: Inputs,
    held: Rules,
) -> dict[str, Any]:
    """Send one request once; the row holds the reply as given, or the code of the failure."""
    start = time.monotonic()
    blank: dict[str, Any] = {"model": None, "raw_reply": None, "usage": {}, "session": None}
    try:
        reply = client.send(text)
    except JudgeUnavailable as exc:
        elapsed = round(time.monotonic() - start, 3)
        return {**row, "status": "unavailable", **blank, "elapsed_s": elapsed, "error": exc.code}
    answered = {
        "model": reply.model,
        "raw_reply": reply.text,
        "usage": usage_counts(reply.usage),
        "session": reply.session,
        "elapsed_s": round(reply.elapsed_s, 3),
    }
    failure = None
    if reply.model != drafting.AUTHOR["model"]:
        failure = "model_mismatch"
    else:
        try:
            isolated.check_record(reply.session)
        except ValueError:
            failure = "session_record"
    if failure is not None:
        # Not a reply of the route: it is no draft and is not kept.
        return {
            **row,
            "status": "unavailable",
            **blank,
            "elapsed_s": answered["elapsed_s"],
            "error": failure,
        }
    if drafting.declined(reply.text) is not None:
        return {**row, "status": "declined", **answered, "error": None}
    try:
        case_of(reply.text, request, inputs, held)
    except (lv.ReplyFormatError, drafting.DraftRefused) as exc:
        return {**row, "status": "invalid", **answered, "error": str(exc)}
    return {**row, "status": "valid", **answered, "error": None}


def draft(
    out: Path, inputs: Inputs, *, client: Any = None, limit: int | None = None
) -> dict[str, Any]:
    """Send the planned requests; resume by position; stop when the route is unavailable."""
    plan = load_plan(out)
    rebuilt, texts = build_plan(inputs)
    if rebuilt != plan:
        raise ValueError("the inputs no longer rebuild the plan of these drafts")
    rows = read_store(out, plan)
    held = rules(inputs)
    check_chain(rows, texts, held.masker)
    if client is None:
        client = GeneratorClient(os.environ.get("RAG_VERIFY_CLAUDE_CLI", "").strip() or None)
    store = out / STORE
    taken = sent = 0
    unavailable: str | None = None
    with ExitStack() as opened:
        handle: TextIO | None = None
        for request in plan["requests"]:
            identity = request["case_id"]
            mine = [row for row in rows if row["case_id"] == identity]
            refused = sum(row["status"] == "invalid" for row in mine)
            if any(row["status"] in CLOSING for row in mine) or refused >= drafting.ATTEMPTS:
                continue
            if unavailable is not None or (limit is not None and taken >= limit):
                break
            taken += 1
            if handle is None:
                # Opened before the first request: no reply is asked for that cannot be kept.
                handle = opened.enter_context(store.open("a", encoding="utf-8", newline="\n"))
            while refused < drafting.ATTEMPTS:
                text = request_text(texts[identity], mine, held.masker)
                row = attempt(
                    client,
                    text,
                    {
                        "case_id": identity,
                        "position": request["position"],
                        "attempt": refused + 1,
                        "request_sha256": lv.sha256_text(text),
                        "base_request_sha256": request["request_sha256"],
                        "prompt_sha256": plan["prompt_sha256"],
                        "generator_version": plan["generator_version"],
                    },
                    request,
                    inputs,
                    held,
                )
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                rows.append(row)
                mine.append(row)
                sent += 1
                emit(f"{identity} attempt {row['attempt']}: {row['error'] or row['status']}")
                if row["status"] in CLOSING:
                    break
                if row["status"] == "unavailable":
                    unavailable = row["error"]
                    break
                refused += 1
    return {**progress(plan, rows), "sent": sent, "unavailable": unavailable}


def progress(plan: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Where a split stands: a position is empty after three refused replies or a NO CASE."""
    valid = {row["case_id"] for row in rows if row["status"] == "valid"}
    declined = {row["case_id"] for row in rows if row["status"] == "declined"}
    refused = Counter(row["case_id"] for row in rows if row["status"] == "invalid")
    empty = [
        request["case_id"]
        for request in plan["requests"]
        if request["case_id"] in declined
        or (request["case_id"] not in valid and refused[request["case_id"]] >= drafting.ATTEMPTS)
    ]
    return {
        "split": plan["split"],
        "requests": len(plan["requests"]),
        "valid": len(valid),
        "empty": len(empty),
        "pending": len(plan["requests"]) - len(valid) - len(empty),
    }


def outputs(out: Path, inputs: Inputs) -> tuple[bytes, bytes]:
    """The drafts and their manifest, as they follow from the plan, the store and the corpus."""
    plan = load_plan(out)
    rebuilt, texts = build_plan(inputs)
    if rebuilt != plan:
        raise ValueError("the inputs no longer rebuild the plan of these drafts")
    rows = read_store(out, plan)
    held = rules(inputs)
    check_chain(rows, texts, held.masker)
    state = progress(plan, rows)
    if state["pending"]:
        raise ValueError(f"{state['pending']} positions have no reply yet")
    cases = []
    empty = []
    # By the attempt of the declaration: after a refused reply NO CASE is a way out of it.
    declined: dict[str, list[int]] = {str(number): [] for number in range(1, drafting.ATTEMPTS + 1)}
    for request in plan["requests"]:
        mine = [row for row in rows if row["case_id"] == request["case_id"]]
        valid = [row for row in mine if row["status"] == "valid"]
        if not valid:
            empty.append(request["position"])
            for row in mine:
                if row["status"] == "declined":
                    declined[str(row["attempt"])].append(request["position"])
            continue
        try:
            cases.append(case_of(valid[0]["raw_reply"], request, inputs, held))
        except (lv.ReplyFormatError, drafting.DraftRefused) as exc:
            raise ValueError(
                f"a stored reply no longer passes the script: {request['case_id']} ({exc})"
            ) from None
    drafts = jsonl(cases)
    attempts = Counter(row["case_id"] for row in rows if row["status"] != "unavailable")
    manifest = {
        "schema_version": MANIFEST_VERSION,
        "split": plan["split"],
        "replacement": plan["replacement"],
        "generator": plan["author"]["model"],
        "generator_version": plan["generator_version"],
        "prompt_sha256": plan["prompt_sha256"],
        "route": plan["route"],
        "settings": plan["settings"],
        "as_of": plan["as_of"],
        "brief_rule": plan["brief_rule"],
        "label_origin": "agent_labelled",
        "label_check": "none",
        "jsonl_sha256": sha256_bytes(drafts),
        **plan["inputs"],
        "plan_sha256": sha256_bytes((out / "plan.json").read_bytes()),
        "store_sha256": sha256_bytes((out / STORE).read_bytes()),
        "replies": {
            "sent": len(rows),
            "refused_by_script": sum(row["status"] == "invalid" for row in rows),
            "no_case": sum(row["status"] == "declined" for row in rows),
            "unavailable": sum(row["status"] == "unavailable" for row in rows),
            "cases_by_attempts": dict(
                sorted(Counter(str(attempts[case["case_id"]]) for case in cases).items())
            ),
        },
        **drafting.summary(plan, cases, empty),
        "no_case_positions": declined,
        "unseated_positions": plan["unseated_positions"],
    }
    return drafts, dump(manifest)


def build(out: Path, inputs: Inputs, drafts: Path, manifest: Path) -> dict[str, Any]:
    drafts_bytes, manifest_bytes = outputs(out, inputs)
    for path, data in ((drafts, drafts_bytes), (manifest, manifest_bytes)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return report(json.loads(manifest_bytes))


def check(out: Path, inputs: Inputs, drafts: Path, manifest: Path) -> dict[str, Any]:
    """Recompute the drafts from the plan and the store and refuse files that differ."""
    drafts_bytes, manifest_bytes = outputs(out, inputs)
    if drafts.read_bytes() != drafts_bytes:
        raise ValueError("the drafts are not what the plan and the store give")
    if manifest.read_bytes() != manifest_bytes:
        raise ValueError("the manifest is not what the plan and the store give")
    return {"status": "ok", **report(json.loads(manifest_bytes))}


def report(manifest: Mapping[str, Any]) -> dict[str, Any]:
    names = ("split", "positions", "drafted", "empty_positions", "unseated_positions")
    return {name: manifest[name] for name in (*names, "class_counts", "trap_counts", "flags")}


def main(argv: list[str] | None = None) -> int:
    """Run one command and return the process exit status; a refusal is exit 2."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=("plan", "draft", "build", "check"))
    parser.add_argument("--split", choices=sorted(drafting.ID_PREFIX), required=True)
    parser.add_argument("--replacements", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--corpus-dir", type=Path)
    parser.add_argument("--limit", type=int)
    arguments = parser.parse_args(argv)
    try:
        return run(arguments)
    except OSError as exc:
        named = f": {Path(exc.filename).name}" if exc.filename else ""
        emit(f"refused: a file cannot be read or written{named}")
    except ValueError as exc:
        emit(f"refused: {exc}")
    return 2


def run(arguments: argparse.Namespace) -> int:
    split = arguments.split
    again = arguments.replacements
    out = arguments.out or out_dir(split, again)
    inputs = load_inputs(split, arguments.corpus_dir, replacement=again)
    if arguments.command == "plan":
        plan, _ = build_plan(inputs)
        write_plan(out, plan)
        classes = Counter(request["primary_class"] for request in plan["requests"])
        emit(
            json.dumps(
                {
                    "split": split,
                    "requests": len(plan["requests"]),
                    "classes": dict(sorted(classes.items())),
                    "characters": sum(request["characters"] for request in plan["requests"]),
                },
                ensure_ascii=False,
            )
        )
        return 0
    if arguments.command == "draft":
        result = draft(out, inputs, limit=arguments.limit)
        emit(json.dumps(result, ensure_ascii=False))
        return 0 if not result["pending"] else 1
    if arguments.command == "build":
        result = build(out, inputs, drafts_path(split, again), manifest_path(split, again))
    else:
        result = check(out, inputs, drafts_path(split, again), manifest_path(split, again))
    emit(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

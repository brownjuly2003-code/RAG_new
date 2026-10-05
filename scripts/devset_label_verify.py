"""Check the labels of development-set drafts with the registered verifier model.

    python -m scripts.devset_label_verify plan --round 1
    python -m scripts.devset_label_verify verify --round 1 --verifier claude-opus-5-5 [--limit N]
    python -m scripts.devset_label_verify decide --round 1
    python -m scripts.devset_label_verify plan --round 2 --repairs <jsonl> [--drops <json>]
    python -m scripts.devset_label_verify decide --round 2 --repairs <jsonl>
    python -m scripts.devset_label_verify apply [--repairs <jsonl>]
    python -m scripts.devset_label_verify check [--repairs <jsonl>] [--rebuild [--drops <json>]]

The protocol is the section «Label verification» of docs/specs/semantic-precision-metrics.md;
docs/specs/label-verification.md says what these commands must do.

Every command takes --set. `pilot`, the default, is the pilot set under rubric
label-verification/v2; its rounds are complete. The sets of plan step 1.3d are verified under
rubric v3: `pilot-v3` (the verified pilot set, checked again), `development`, `holdout`, and
`development-replacements` and `holdout-replacements`. A set of v3 keeps its rounds in
reports/devset/label-verification/v3/<set>/ and is checked by the isolated route: every reply
is stored with the record of its session, and a reply without the record of a session that
loaded nothing is no verdict. Its repairs and declared drops are written by
scripts/devset_label_repair.py.

plan checks every input of one round and writes <round dir>/plan.json: per request its
SHA-256, the pseudonym map and the counts. The request text is not written anywhere: verify
rebuilds it from the same inputs (drafts, corpus, scan, chunk archive and, in round 2, the
repairs and the declared drops) and refuses inputs that no longer give the plan.

verify sends the planned requests of one verifier and appends every reply to
<round dir>/<verifier>.jsonl; a rerun resumes by request. --limit N takes up at most N
requests in one run. The Claude CLI may be named in RAG_VERIFY_CLAUDE_CLI; it is not printed or
stored. Only the request text leaves the machine, and only to a registered verifier: the tool
holds no route to any other model (plan decision D12).

decide recomputes the outcome of every planned case from the stores, writes
<round dir>/decisions.json and prints, for each rejected case, the reasons of every verifier:
the input of the repair.

apply writes the verified set and its register; check recomputes both from the plans and the
stores and refuses a set that differs. A model check is not a human approval: label_origin
stays agent_labelled.

decide, apply and check read no severity, class or document on a plan's word: every row of a
plan is held against the case revision it names - the draft in round 1, the repairs file in
round 2 - and a row that differs is refused. What binds a row to its request text is the
rebuild: verify makes it before it sends, and check --rebuild makes it again from the corpus,
the scan, the repairs and the declared drops.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, TextIO

from evaluation import devset
from evaluation import isolated_request as isolated
from evaluation import label_verification as lv
from evaluation.blinded_judge_clients import (
    JudgeUnavailable,
    RateLimited,
    Reply,
    TransportError,
)
from evaluation.devset_sources import corpus_directory, read_sources
from scripts import devset_wide_scan as wide

ROOT = Path(__file__).resolve().parent.parent
EVALUATION = ROOT / "evaluation"
BASE = ROOT / "reports" / "devset" / "label-verification"
ARCHIVE = ROOT / "evaluation" / "gr1b-4436d61-graph-chunks.json.gz"
VERIFIED = ROOT / "evaluation" / "devset_pilot_verified.jsonl"
REGISTER = ROOT / "evaluation" / "devset_pilot_label_checks.json"
# The drafts, their manifest and the family register are never written here.
PROTECTED = tuple(
    ROOT / "evaluation" / name
    for name in ("devset_pilot.jsonl", "devset_pilot.manifest.json", "document_families.json")
)
PLAN_VERSION = 1
REGISTER_VERSION = "devset-label-checks/v1"
BOUND_INPUTS = (
    "drafts_sha256",
    "families_sha256",
    "corpus_sha256",
    "scan_sha256",
    "archive_sha256",
)
CLI_TIMEOUT_S = 1800.0
# What a store keeps of a route's usage: these counters, as numbers, and nothing else.
USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "total_cost_usd",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    # Not splitlines(): it also breaks on separators JSON leaves unescaped inside a string.
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line.strip()
    ]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"a line of {path.name} is not a JSON object")
    return rows


def dump(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def jsonl(rows: list[dict[str, Any]]) -> bytes:
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8")


def usage_counts(usage: object) -> dict[str, int | float]:
    """The registered counters of a route's usage. A route may report more: it is not kept."""
    if not isinstance(usage, Mapping):
        return {}
    return {
        name: usage[name]
        for name in USAGE_FIELDS
        if type(usage.get(name)) in (int, float) and math.isfinite(usage[name])
    }


@dataclass(frozen=True)
class Drafts:
    """The registered drafts with what binds them. Nothing here is rewritten.

    `rubric` is the rubric the set is verified under. `label_authors` names, per case, the
    author of the label as the set holds it where that is not the draft author: a label that
    was repaired before it came into this set. `holdout` marks a set drafted from the holdout
    reserve, whose repairs are bound the other way round. `gate` refuses round 1 of a set that
    waits for something; a set that waits for nothing has none.
    """

    cases: list[dict[str, Any]]
    manifest: dict[str, Any]
    register: dict[str, Any]
    corpus: dict[str, Any]
    verify: Callable[[Path], object]
    rubric: str = lv.RUBRIC_VERSION
    label_authors: Mapping[str, Mapping[str, str]] | None = None
    holdout: bool = False
    gate: Callable[[], object] | None = None

    @property
    def author(self) -> dict[str, str]:
        return lv.draft_author(self.manifest["generator"])

    @property
    def revisions(self) -> dict[str, str]:
        return {entry["name"]: entry["sha256"] for entry in self.corpus["files"]}

    @property
    def reserve(self) -> frozenset[str]:
        return frozenset(self.register["holdout_reserve_documents"])

    @property
    def barred(self) -> frozenset[str]:
        """The documents a repair of this set may not cite.

        A development case cites no document of the holdout reserve. A case of the holdout is
        drafted from the reserve, and its repair cites no document outside it: the families of
        the two splits stay apart either way.
        """
        return frozenset(self.revisions) - self.reserve if self.holdout else self.reserve

    @property
    def barred_name(self) -> str:
        return "a document outside the holdout reserve" if self.holdout else "the holdout reserve"

    def label_author(self, case_id: str) -> dict[str, str]:
        """Who wrote the label of a case as this set holds it."""
        return dict((self.label_authors or {}).get(case_id) or self.author)

    def verifiers(self) -> dict[str, lv.Verifier]:
        """The registered verifiers of the set, by its rubric.

        Under v3 the verifier of every label is the model of the session, asked by the isolated
        route; under v2 it follows from the vendor of the draft author.
        """
        if self.rubric != lv.RUBRIC_V3:
            return lv.registered_verifiers(self.author)
        return {
            isolated.MODEL: {
                "model": isolated.MODEL,
                "vendor": lv.REPAIR_AUTHOR["vendor"],
                "route": isolated.ROUTE,
                "settings": isolated.settings(lv.CLI_SYSTEM_PROMPT),
            }
        }

    def drop_problem(self, drop: Mapping[str, Any]) -> str | None:
        """What is wrong with a declared drop of a case of this set; None for a valid one."""
        if self.holdout and drop.get("ground") == lv.RESERVE_DROP:
            return f"a case of the holdout has no ground {lv.RESERVE_DROP}"
        problems = lv.drop_violations(drop, self.reserve)
        return problems[0] if problems else None

    def by_id(self) -> dict[str, dict[str, Any]]:
        return {case["case_id"]: case for case in self.cases}

    def case_rules(self, case: dict[str, Any], draft: Mapping[str, Any]) -> list[str]:
        """Apply the per-case rules of the verify script to one revision; return its families."""
        return devset.validate_case(
            case,
            draft["seed_selected_source_section"],
            self.revisions,
            self.corpus["corpus_sha256"],
            devset.document_families(self.register),
        )


def pilot_drafts() -> Drafts:
    cases, manifest, register, corpus = devset.load_artifacts()
    return Drafts(
        cases, manifest, register, corpus, lambda directory: devset.verify(directory=directory)
    )


def pilot_v3_drafts() -> Drafts:
    """The verified pilot set as rubric v3 checks it again in plan step 1.3d.

    A case confirmed as drafted is the draft of its author; a case confirmed after a repair
    is a label of the model that repaired it, which is the model that now checks it.
    """
    pilot = pilot_drafts()
    data = VERIFIED.read_bytes()
    checks = read_json(REGISTER)
    if not checks.get("complete") or checks["sha256"].get("verified_set") != sha256_bytes(data):
        raise ValueError("the verified pilot set is not the one its register gives")
    rows = read_jsonl(VERIFIED)
    cases = [
        {key: value for key, value in row.items() if key not in lv.ADDED_FIELDS} for row in rows
    ]
    manifest = {
        "generator": pilot.manifest["generator"],
        "jsonl_sha256": sha256_bytes(data),
        "families_sha256": pilot.manifest["families_sha256"],
    }
    drafted = pilot.by_id()
    families = devset.document_families(pilot.register)

    def script(directory: Path) -> None:
        texts = read_sources(pilot.corpus, directory)
        frame = devset.source_frame(texts)
        for case in cases:
            seed = drafted[case["case_id"]]["seed_selected_source_section"]
            devset.validate_case(
                case, seed, pilot.revisions, pilot.corpus["corpus_sha256"], families
            )
            devset.validate_case_sources(case, texts, frame)

    return Drafts(
        cases,
        manifest,
        pilot.register,
        pilot.corpus,
        script,
        rubric=lv.RUBRIC_V3,
        label_authors={
            row["case_id"]: row["label_check"]["repair_author"]
            for row in rows
            if "repair_author" in row["label_check"]
        },
    )


def pilot_closed() -> None:
    """The gate of the set `development`: its round 1 waits for the register of `pilot-v3`.

    A case `pilot-v3` drops is replaced with the dropped drafts of development, and the code
    that seats a replacement is tested before a draft of the step is verified. So no draft of
    development is checked while that register is open, nor while it holds a dropped case
    that the draft tool cannot seat yet.
    """
    from scripts import devset_draft as draft_tool

    try:
        draft_tool.pilot_register()
    except ValueError as exc:
        raise ValueError(f"round 1 of development waits for pilot-v3: {exc}") from None


def split_drafts(split: str, replacement: bool = False) -> Drafts:
    """The drafts of plan step 1.3d of one split, or the replacements of its dropped drafts."""
    # The draft tool takes its file helpers from this module.
    from scripts import devset_draft as draft_tool

    path = draft_tool.drafts_path(split, replacement)
    manifest = read_json(draft_tool.manifest_path(split, replacement))

    def script(directory: Path) -> None:
        draft_tool.check(
            draft_tool.out_dir(split, replacement),
            draft_tool.load_inputs(split, directory, replacement=replacement),
            path,
            draft_tool.manifest_path(split, replacement),
        )

    return Drafts(
        read_jsonl(path),
        manifest,
        read_json(EVALUATION / "document_families.json"),
        read_json(EVALUATION / "aircargo_corpus.manifest.json"),
        script,
        rubric=lv.RUBRIC_V3,
        holdout=split == "holdout",
        gate=pilot_closed if split == "development" and not replacement else None,
    )


@dataclass(frozen=True)
class DraftSet:
    """Where one draft set keeps its rounds and what `apply` writes for it."""

    base: Path
    verified: Path
    register: Path


def _v3(name: str) -> DraftSet:
    stem = "devset_" + name.replace("-", "_")
    return DraftSet(
        BASE / "v3" / name,
        EVALUATION / f"{stem}_verified.jsonl",
        EVALUATION / f"{stem}_label_checks.json",
    )


# The pilot was verified under v2; every set of plan step 1.3d is verified under v3.
SETS = {
    "pilot": DraftSet(BASE, VERIFIED, REGISTER),
    **{
        name: _v3(name)
        for name in (
            "pilot-v3",
            "development",
            "holdout",
            "development-replacements",
            "holdout-replacements",
        )
    },
}


def load_set(name: str) -> Drafts:
    if name == "pilot":
        return pilot_drafts()
    if name == "pilot-v3":
        return pilot_v3_drafts()
    split, _, rest = name.partition("-")
    return split_drafts(split, rest == "replacements")


def protected(name: str) -> tuple[Path, ...]:
    """What `apply` never writes for a set: every file of drafts, and the outputs of the others."""
    from scripts import devset_draft as draft_tool

    drafts = [
        path
        for split in ("development", "holdout")
        for replacement in (False, True)
        for path in (
            draft_tool.drafts_path(split, replacement),
            draft_tool.manifest_path(split, replacement),
        )
    ]
    others = [
        path
        for other, files in SETS.items()
        if other != name
        for path in (files.verified, files.register)
    ]
    return (*PROTECTED, *drafts, *others)


@dataclass(frozen=True)
class RoundInputs:
    """What one round is built from; verify rebuilds the plan from the same inputs."""

    round: int
    corpus_dir: Path
    scan: Path
    archive: Path
    previous: Path | None = None
    repairs: Path | None = None
    drops: Path | None = None


@dataclass(frozen=True)
class Round:
    """One round as its directory holds it: the plan, the stores and the recomputed outcomes.

    `revisions` are the case revisions the plan was built from, each checked against its row.
    """

    plan: dict[str, Any]
    plan_sha256: str
    revisions: dict[str, dict[str, Any]]
    stores: dict[str, list[dict[str, Any]]]
    store_sha256: dict[str, str | None]
    decisions: dict[str, dict[str, Any]]

    @property
    def requests(self) -> dict[str, dict[str, Any]]:
        return {request["case_id"]: request for request in self.plan["requests"]}

    @property
    def drops(self) -> dict[str, dict[str, Any]]:
        return {drop["case_id"]: drop for drop in self.plan["declared_drops"]}


def load_plan(out: Path) -> dict[str, Any]:
    """Read plan.json; refuse a plan of another version, rubric or prompt."""
    plan: dict[str, Any] = read_json(out / "plan.json")
    if not isinstance(plan, dict) or plan.get("plan_version") != PLAN_VERSION:
        raise ValueError("plan_version is not supported")
    if plan.get("rubric_version") not in lv.RUBRICS:
        raise ValueError("the plan is of another rubric version")
    if plan.get("prompt_sha256") != lv.PROMPT_SHA256:
        raise ValueError("the plan is of another prompt")
    planned: list[Any] = []
    try:
        planned += [request["case_id"] for request in plan["requests"]]
        planned += [drop["case_id"] for drop in plan["declared_drops"]]
        whole = plan["round"] in (1, 2) and all(
            isinstance(plan[key], dict) for key in ("draft_author", "verifiers", "inputs")
        )
    except (KeyError, TypeError):
        whole = False
    if not whole or not all(isinstance(case_id, str) for case_id in planned):
        raise ValueError("plan.json does not hold a plan")
    if len(set(planned)) != len(planned):
        raise ValueError("a case is planned twice")
    return plan


def write_plan(out: Path, plan: dict[str, Any]) -> None:
    """Write plan.json once; an equal plan already present is accepted, a different one is not."""
    path = out / "plan.json"
    if path.exists():
        try:
            same = read_json(path) == plan
        except (OSError, ValueError):
            same = False
        if same:
            return
        raise ValueError("a different plan exists in this directory")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(dump(plan))


def read_store(out: Path, plan: Mapping[str, Any], name: str) -> list[dict[str, Any]]:
    """Read one verifier's replies; refuse a row of another request, prompt or rubric.

    A store is what `verify` writes: the attempt of a row is one more than the invalid replies
    before it, three attempts in all, and nothing follows a valid reply. Any other history is
    refused: a verdict on a fourth attempt or a second verdict is not counted. Under v3 a
    reply counts only with the record of a session that loaded nothing.
    """
    path = out / f"{name}.jsonl"
    if not path.exists():
        return []
    planned = {request["case_id"]: request for request in plan["requests"]}
    rows = read_jsonl(path)
    invalid: dict[str, int] = {}
    closed: set[str] = set()
    for row in rows:
        case_id = row.get("case_id")
        request = planned.get(case_id) if isinstance(case_id, str) else None
        if (
            not isinstance(case_id, str)
            or request is None
            or row.get("verifier") != name
            or row.get("round") != plan["round"]
            or row.get("request_sha256") != request["request_sha256"]
            or row.get("prompt_sha256") != plan["prompt_sha256"]
            or row.get("rubric_version") != plan["rubric_version"]
            or row.get("status") not in ("valid", "invalid", "unavailable")
        ):
            raise ValueError(
                f"the store of {name} holds a row that is not of this plan: its request, "
                f"prompt or rubric version differs ({row.get('case_id')})"
            )
        before = invalid.get(case_id, 0)
        number = row.get("attempt")
        if case_id in closed or before >= lv.ATTEMPTS or type(number) is not int:
            written = False
        else:
            written = number == before + 1
        if not written:
            raise ValueError(
                f"the store of {name} holds attempts that verify does not write: {case_id}"
            )
        if plan["rubric_version"] == lv.RUBRIC_V3 and row["status"] != "unavailable":
            try:
                isolated.check_record(row.get("session"))
            except ValueError as exc:
                raise ValueError(f"a stored reply the route does not vouch for: {exc}") from None
        if row["status"] == "valid":
            closed.add(case_id)
        elif row["status"] == "invalid":
            invalid[case_id] = before + 1
    return rows


def valid_verdict(
    rows: list[dict[str, Any]], case_id: str, model: str
) -> dict[str, dict[str, Any]] | None:
    """The verdict of the first valid reply to one request, parsed again from the raw reply."""
    for row in rows:
        if row["case_id"] != case_id or row["status"] != "valid":
            continue
        if row.get("model") != model:
            raise ValueError(f"a stored verdict is not of the registered model: {case_id}")
        try:
            return lv.parse_reply(row["raw_reply"])
        except (lv.ReplyFormatError, TypeError):
            raise ValueError(f"a stored verdict does not follow the form: {case_id}") from None
    return None


def planned_fields(case: Mapping[str, Any], families: Mapping[str, str]) -> dict[str, Any]:
    """What a row of a plan copies from the case revision it was built from."""
    return {
        "case_sha256": lv.case_sha256(case),
        "registered_severity": case["wrong_answer_severity"],
        "primary_class": case["primary_class"],
        "safety_critical": case["flags"]["safety_critical"],
        "documents": case["documents"],
        "families": sorted({families[name] for name in case["documents"]}),
        # A plan is written only when the drafts, and in round 2 the repairs, pass the verify
        # script, and check 1 - every span verbatim in its source - is part of it.
        "check_1": "passed",
    }


def repair_problem(drafts: Drafts, case: dict[str, Any]) -> str | None:
    """Why a revision is no repair of its draft: a kept field, the reserve or a per-case rule."""
    case_id = case.get("case_id")
    draft = drafts.by_id().get(case_id) if isinstance(case_id, str) else None
    if draft is None:
        return "a repair is of no drafted case"
    try:
        problems = lv.repair_violations(
            draft, case, drafts.author, drafts.barred, barred=drafts.barred_name
        )
        if not problems:
            drafts.case_rules(case, draft)
    except (ValueError, KeyError, TypeError) as exc:
        problems = [f"a repair fails the rules of the verify script ({exc})"]
    return problems[0] if problems else None


def planned_revisions(
    plan: Mapping[str, Any], drafts: Drafts, repairs: Path | None
) -> dict[str, dict[str, Any]]:
    """The case revision behind every row of a plan; refuse a row that is not what it gives.

    A decision reads the severity from the row and the register its class and documents: none
    is taken on the plan's word. Round 1 is held against the drafts, round 2 against the
    repairs file it was planned on.
    """
    if plan["rubric_version"] != drafts.rubric:
        raise ValueError("the plan is not of the rubric these drafts are verified under")
    if plan["draft_author"] != drafts.author or plan["verifiers"] != drafts.verifiers():
        raise ValueError("the plan is not of the registered draft author and verifiers")
    if plan["round"] == 1:
        cases = drafts.by_id()
        source = "these drafts"
    else:
        source = "the repairs it was planned on"
        if not plan["requests"]:
            cases = {}
        elif repairs is None:
            raise ValueError("round 2 checked repaired cases: name their file with --repairs")
        elif sha256_bytes(repairs.read_bytes()) != plan["inputs"].get("repairs_sha256"):
            raise ValueError("the repairs file is not the one round 2 was planned on")
        else:
            cases = {
                case["case_id"]: case
                for case in read_jsonl(repairs)
                if isinstance(case.get("case_id"), str)
            }
    families = devset.document_families(drafts.register)
    revisions: dict[str, dict[str, Any]] = {}
    for request in plan["requests"]:
        case_id = request["case_id"]
        try:
            case = cases[case_id]
            copied = planned_fields(case, families)
            same = all(request.get(key) == value for key, value in copied.items())
        except (KeyError, TypeError):
            same = False
        if not same:
            raise ValueError(f"the plan of round {plan['round']} is not of {source}: {case_id}")
        # A repairs file and a plan rewritten together still do not make a repair of anything.
        problem = repair_problem(drafts, case) if plan["round"] == 2 else None
        if problem:
            raise ValueError(f"{problem}: {case_id}")
        revisions[case_id] = case
    return revisions


def load_round(out: Path, drafts: Drafts, repairs: Path | None = None) -> Round:
    """Read one round and recompute every planned case's outcome from its stores."""
    plan = load_plan(out)
    revisions = planned_revisions(plan, drafts, repairs)
    names = sorted(plan["verifiers"])
    stores = {name: read_store(out, plan, name) for name in names}
    decisions = {}
    for request in plan["requests"]:
        case_id = request["case_id"]
        verdicts = {
            name: valid_verdict(stores[name], case_id, plan["verifiers"][name]["model"])
            for name in names
        }
        decisions[case_id] = {
            **lv.decide(revisions[case_id]["wrong_answer_severity"], verdicts, check_1=True),
            "verdicts": verdicts,
        }
    return Round(
        plan=plan,
        plan_sha256=sha256_bytes((out / "plan.json").read_bytes()),
        revisions=revisions,
        stores=stores,
        store_sha256={
            name: sha256_bytes((out / f"{name}.jsonl").read_bytes())
            if (out / f"{name}.jsonl").exists()
            else None
            for name in names
        },
        decisions=decisions,
    )


def refuse_unrepairable(first: Round, drafts: Drafts, repaired: Sequence[str]) -> None:
    """Refuse the repair of a case rubric v3 drops without one, whoever wrote the repair.

    A case without spans that round 1 rejected on check 5a or 5b: its repair would be a
    second draw of the same check. `repaired` are cases round 1 rejected.
    """
    if drafts.rubric != lv.RUBRIC_V3:
        return
    for case_id in repaired:
        if lv.no_repair_request(first.revisions[case_id], first.decisions[case_id]):
            raise ValueError(f"a case without spans rejected on 5a or 5b has no repair: {case_id}")


def check_drops(first: Round, second: Round, drafts: Drafts) -> None:
    """Refuse a round 2 that plans what round 1 did not reject, or an invalid declared drop."""
    planned = [*second.requests, *second.drops]
    for case_id in planned:
        if first.decisions.get(case_id, {}).get("outcome") != "rejected":
            raise ValueError(f"a case was not rejected in round 1: {case_id}")
    refuse_unrepairable(first, drafts, list(second.requests))
    for case_id, drop in second.drops.items():
        problem = drafts.drop_problem(drop)
        if problem:
            raise ValueError(f"{problem}: {case_id}")


def second_round(
    drafts: Drafts,
    inputs: RoundInputs,
    texts: dict[str, str],
    bound: Mapping[str, str],
    verifiers: Mapping[str, lv.Verifier],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str | None]]:
    """Check the repairs and the declared drops of round 2 against round 1 and the rules."""
    if inputs.previous is None:
        raise ValueError("round 2 needs the directory of round 1")
    first = load_round(inputs.previous, drafts)
    if (
        first.plan["round"] != 1
        or any(first.plan["inputs"][key] != value for key, value in bound.items())
        or first.plan["verifiers"] != verifiers
        or first.plan["draft_author"] != drafts.author
    ):
        raise ValueError("round 2 is not planned on the inputs of round 1")
    repairs = read_jsonl(inputs.repairs) if inputs.repairs is not None else []
    declared = read_json(inputs.drops) if inputs.drops is not None else []
    if not isinstance(declared, list) or not all(isinstance(drop, dict) for drop in declared):
        raise ValueError("the declared drops are not a list of objects")
    given = [row.get("case_id") for row in [*repairs, *declared]]
    if not all(isinstance(case_id, str) for case_id in given):
        raise ValueError("a repair or a declared drop names no case")
    for case_id in given:
        if given.count(case_id) > 1:
            both = any(row.get("case_id") == case_id for row in repairs) and any(
                drop.get("case_id") == case_id for drop in declared
            )
            raise ValueError(
                f"a case is given both as a repair and as a declared drop: {case_id}"
                if both
                else f"a case is given twice: {case_id}"
            )
        if first.decisions.get(case_id, {}).get("outcome") != "rejected":
            raise ValueError(f"a case was not rejected in round 1: {case_id}")
    for drop in declared:
        problem = drafts.drop_problem(drop)
        if problem:
            raise ValueError(f"{problem}: {drop['case_id']}")
    refuse_unrepairable(first, drafts, [case["case_id"] for case in repairs])
    frame = devset.source_frame(texts) if repairs else None
    for case in repairs:
        problem = repair_problem(drafts, case)
        if problem is None and frame is not None:
            try:
                devset.validate_case_sources(case, texts, frame)
            except (ValueError, KeyError, TypeError) as exc:
                problem = f"a repair fails the rules of the verify script ({exc})"
        if problem:
            raise ValueError(f"{problem}: {case['case_id']}")
    order = {case["case_id"]: index for index, case in enumerate(drafts.cases)}
    repairs.sort(key=lambda case: order[case["case_id"]])
    drops = sorted(
        ({"case_id": drop["case_id"], **lv.drop_record(drop)} for drop in declared),
        key=lambda drop: order[drop["case_id"]],
    )
    return (
        repairs,
        drops,
        {
            "previous_plan_sha256": first.plan_sha256,
            "repairs_sha256": sha256_bytes(inputs.repairs.read_bytes())
            if inputs.repairs is not None
            else None,
            "drops_sha256": sha256_bytes(inputs.drops.read_bytes())
            if inputs.drops is not None
            else None,
        },
    )


def read_scan(inputs: RoundInputs) -> tuple[bytes, dict[str, Any], list[dict[str, Any]]]:
    """The wide scan of a round, as bytes and as read, and the chunks of its archive.

    ValueError when a file is missing, the scan is not of the registered schema or one of its
    texts is not the archive's.
    """
    try:
        scan_bytes = inputs.scan.read_bytes()
        archive = inputs.archive.read_bytes()
    except OSError:
        raise ValueError("no wide scan: the scan file or the chunk archive is missing") from None
    try:
        scan = json.loads(scan_bytes)
    except ValueError:
        scan = None
    if not isinstance(scan, dict) or scan.get("schema_version") != wide.SCHEMA_VERSION:
        raise ValueError("the scan file is not a wide scan of the registered schema")
    chunks = wide.load_chunks(archive, scan.get("archive_sha256", ""))
    try:
        lv.check_scan(scan, chunks)
    except (KeyError, TypeError):
        raise ValueError("the scan file is not a wide scan of the registered schema") from None
    return scan_bytes, scan, chunks


def build_round(
    drafts: Drafts, inputs: RoundInputs, verifiers: Mapping[str, lv.Verifier] | None = None
) -> tuple[dict[str, Any], dict[str, str]]:
    """Check every input of one round; return its plan and the request texts by case id.

    Nothing is written. Every refusal of `plan` is raised here as ValueError.
    """
    if lv.prompt_sha256() != lv.PROMPT_SHA256:
        raise ValueError("the prompt is not the registered one")
    if lv.sha256_text(lv.CLI_SYSTEM_PROMPT) != lv.CLI_SYSTEM_PROMPT_SHA256:
        raise ValueError("the system prompt is not the registered one")
    if inputs.round not in (1, 2):
        raise ValueError("a round is 1 or 2")
    if inputs.round == 1 and drafts.gate is not None:
        drafts.gate()
    author = drafts.author
    chosen = dict(verifiers) if verifiers is not None else drafts.verifiers()
    if drafts.rubric != lv.RUBRIC_V3:
        # v3 has the author of a label check it: the vendor rule of v2 cannot be met there.
        lv.check_vendors(author, chosen)
    try:
        texts = read_sources(drafts.corpus, inputs.corpus_dir)
    except OSError:
        raise ValueError("the corpus is not the registered version: a file is missing") from None
    except ValueError as exc:
        raise ValueError(f"the corpus is not the registered version: {exc}") from None
    try:
        drafts.verify(inputs.corpus_dir)
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"the drafts fail the verify script: {exc}") from None
    scan_bytes, scan, chunks = read_scan(inputs)
    bound = {
        "drafts_sha256": drafts.manifest["jsonl_sha256"],
        "families_sha256": drafts.manifest["families_sha256"],
        "corpus_sha256": drafts.corpus["corpus_sha256"],
        "scan_sha256": sha256_bytes(scan_bytes),
        "archive_sha256": scan["archive_sha256"],
    }
    drops: list[dict[str, Any]] = []
    earlier: dict[str, str | None] = {
        "previous_plan_sha256": None,
        "repairs_sha256": None,
        "drops_sha256": None,
    }
    if inputs.round == 1:
        cases = list(drafts.cases)
    else:
        cases, drops, earlier = second_round(drafts, inputs, texts, bound, chosen)
    masker = lv.Masker(texts)
    families = devset.document_families(drafts.register)
    requests = []
    request_texts = {}
    for case in cases:
        passages = lv.scan_passages(case, scan, chunks) if lv.needs_scan(case) else None
        request = lv.build_request(case, texts, masker, passages)
        request_texts[case["case_id"]] = request.text
        requests.append(
            {
                "case_id": case["case_id"],
                "round": inputs.round,
                "request_sha256": request.sha256,
                "pseudonyms": request.pseudonyms,
                "characters": request.characters,
                "corpus_texts": sum(request.corpus_texts.values()),
                "corpus_text_counts": request.corpus_texts,
                **planned_fields(case, families),
            }
        )
    plan = {
        "plan_version": PLAN_VERSION,
        "rubric_version": drafts.rubric,
        "prompt_sha256": lv.PROMPT_SHA256,
        "round": inputs.round,
        "draft_author": author,
        "verifiers": chosen,
        "inputs": {**bound, **earlier},
        "requests": requests,
        "declared_drops": drops,
    }
    # The plan is compared with the one read back from plan.json: keep it what JSON gives.
    return json.loads(json.dumps(plan, ensure_ascii=False, allow_nan=False)), request_texts


def plan_round(out: Path, drafts: Drafts, inputs: RoundInputs) -> dict[str, Any]:
    plan, _ = build_round(drafts, inputs)
    write_plan(out, plan)
    return {
        "round": plan["round"],
        "requests": len(plan["requests"]),
        "declared_drops": len(plan["declared_drops"]),
        "characters": sum(request["characters"] for request in plan["requests"]),
        "corpus_texts": sum(request["corpus_texts"] for request in plan["requests"]),
    }


def parse_cli_envelope(raw_json: str, model: str) -> dict[str, Any]:
    """Read the JSON envelope of `claude -p`; refuse any reply the registered model did not give."""
    try:
        data = json.loads(raw_json)
    except ValueError as exc:
        raise ValueError("Claude CLI did not return JSON") from exc
    if not isinstance(data, dict) or data.get("is_error") is not False:
        raise ValueError("Claude CLI returned an error")
    if data.get("terminal_reason") != "completed":
        raise ValueError("Claude CLI did not complete")
    model_usage = data.get("modelUsage")
    if not isinstance(model_usage, dict) or set(model_usage) != {model}:
        raise ValueError("Claude CLI used a different model")
    reported = model_usage[model]
    if not isinstance(reported, dict) or reported.get("canonicalModel") != model:
        raise ValueError("Claude CLI did not confirm the requested model")
    if reported.get("provider") != "firstParty":
        raise ValueError("Claude CLI did not use the first-party provider")
    result = data.get("result")
    if not isinstance(result, str) or not result.strip():
        raise ValueError("Claude CLI returned no reply")
    usage = data.get("usage")
    counted = {
        **(usage if isinstance(usage, dict) else {}),
        "total_cost_usd": data.get("total_cost_usd"),
    }
    return {"result": result, "model": model, "usage": usage_counts(counted)}


class ClaudeCliClient:
    """The Claude route: one request is one new `claude -p` process, no tools, no stored session."""

    model = "claude-opus-5-5"
    route = lv.VERIFIERS[model]["route"]
    arguments = (
        "-p",
        "--model",
        model,
        "--effort",
        "max",
        "--tools",
        "",
        "--permission-mode",
        "dontAsk",
        "--disable-slash-commands",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--output-format",
        "json",
        "--system-prompt",
        lv.CLI_SYSTEM_PROMPT,
    )

    def __init__(self, executable: str | None = None, timeout_s: float = CLI_TIMEOUT_S) -> None:
        self.executable = executable
        self.timeout_s = timeout_s

    def grade(self, request_text: str) -> Reply:
        executable = self.executable or shutil.which("claude")
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
            envelope = parse_cli_envelope(process.stdout, self.model)
        except ValueError as exc:
            raise JudgeUnavailable("cli_response", str(exc)) from None
        return Reply(
            envelope["result"], envelope["model"], envelope["usage"], time.monotonic() - start
        )


class IsolatedClient:
    """The route of rubric v3: one request is one new session that loads nothing.

    The reply comes back with the record of its session, and a verdict counts only with it.
    """

    model = isolated.MODEL
    route = isolated.ROUTE

    def __init__(
        self,
        executable: str | None = None,
        timeout_s: float = CLI_TIMEOUT_S,
        system_prompt: str = lv.CLI_SYSTEM_PROMPT,
    ) -> None:
        self.executable = executable
        self.timeout_s = timeout_s
        self.system_prompt = system_prompt

    def grade(self, request_text: str) -> isolated.IsolatedReply:
        executable = self.executable or isolated.find_cli()
        if executable is None:
            raise JudgeUnavailable("cli_missing", "Claude CLI is not installed")
        return isolated.send(executable, self.system_prompt, request_text, timeout_s=self.timeout_s)


def make_client(name: str) -> Any:
    """Build the client of a registered verifier from the environment; nothing is echoed.

    A route exists for a registered verifier and for no other model. This is the route the
    pilot was verified by under v2; a plan of v3 is sent by `isolated_client`.
    """
    if name == ClaudeCliClient.model and name in lv.VERIFIERS:
        return ClaudeCliClient(os.environ.get("RAG_VERIFY_CLAUDE_CLI", "").strip() or None)
    raise ValueError(f"no route is registered for the verifier {name}")


def isolated_client(name: str, system_prompt: str = lv.CLI_SYSTEM_PROMPT) -> Any:
    """The client of rubric v3 from the environment; nothing is echoed."""
    if name != IsolatedClient.model:
        raise ValueError(f"no route is registered for the verifier {name}")
    return IsolatedClient(
        os.environ.get("RAG_VERIFY_CLAUDE_CLI", "").strip() or None, system_prompt=system_prompt
    )


def emit(line: str) -> None:
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        print(line.encode("ascii", "backslashreplace").decode("ascii"), flush=True)


def attempt(
    client: Any, text: str, model: str, row: dict[str, Any], *, recorded: bool = False
) -> dict[str, Any]:
    """Send one request once; the row holds the reply as given, or the code of the failure.

    With `recorded` (rubric v3) the row keeps the record of the reply's session, and a reply
    without the record of a session that loaded nothing is no verdict.
    """
    start = time.monotonic()
    blank: dict[str, Any] = {"model": None, "raw_reply": None, "usage": {}}
    if recorded:
        blank["session"] = None
    try:
        reply = client.grade(text)
    except JudgeUnavailable as exc:
        failure = exc.code
    except RateLimited:
        failure = "rate_limited"
    except TransportError:
        failure = "transport"
    else:
        answered = {
            "model": reply.model,
            "raw_reply": reply.text,
            "usage": usage_counts(reply.usage),
            "elapsed_s": round(reply.elapsed_s, 3),
        }
        if reply.model != model:
            # Another model answered: its reply is no verdict and is not kept.
            return {
                **row,
                "status": "unavailable",
                **blank,
                "model": reply.model,
                "elapsed_s": answered["elapsed_s"],
                "error": "model_mismatch",
            }
        if recorded:
            answered["session"] = getattr(reply, "session", None)
            try:
                isolated.check_record(answered["session"])
            except ValueError:
                # Not a reply of the route: it is no verdict and is not kept.
                return {
                    **row,
                    "status": "unavailable",
                    **blank,
                    "elapsed_s": answered["elapsed_s"],
                    "error": "session_record",
                }
        try:
            lv.parse_reply(reply.text)
        except lv.ReplyFormatError as exc:
            return {**row, "status": "invalid", **answered, "error": str(exc)}
        return {**row, "status": "valid", **answered, "error": None}
    return {
        **row,
        "status": "unavailable",
        **blank,
        "elapsed_s": round(time.monotonic() - start, 3),
        "error": failure,
    }


def verify(
    out: Path,
    name: str,
    drafts: Drafts,
    inputs: RoundInputs,
    *,
    client: Any = None,
    limit: int | None = None,
    verifiers: Mapping[str, lv.Verifier] | None = None,
) -> dict[str, Any]:
    """Send one verifier's planned requests; resume by request; stop when it is unavailable."""
    plan = load_plan(out)
    if name not in plan["verifiers"]:
        raise ValueError(f"not a verifier of this plan: {name}")
    rebuilt, texts = build_round(drafts, replace(inputs, round=plan["round"]), verifiers)
    if rebuilt != plan:
        raise ValueError("the inputs no longer rebuild the plan of this round")
    rows = read_store(out, plan, name)
    recorded = plan["rubric_version"] == lv.RUBRIC_V3
    if client is None:
        client = isolated_client(name) if recorded else make_client(name)
    model = plan["verifiers"][name]["model"]
    store = out / f"{name}.jsonl"
    taken = sent = 0
    unavailable: str | None = None
    with ExitStack() as opened:
        handle: TextIO | None = None
        for request in plan["requests"]:
            case_id = request["case_id"]
            mine = [row for row in rows if row["case_id"] == case_id]
            invalid = sum(row["status"] == "invalid" for row in mine)
            if any(row["status"] == "valid" for row in mine) or invalid >= lv.ATTEMPTS:
                continue
            if unavailable is not None or (limit is not None and taken >= limit):
                break
            taken += 1
            if lv.sha256_text(texts[case_id]) != request["request_sha256"]:
                raise ValueError(f"the request text is not the plan's: {case_id}")
            if handle is None:
                # Opened before the first request: no reply is asked for that cannot be kept.
                handle = opened.enter_context(store.open("a", encoding="utf-8", newline="\n"))
            while invalid < lv.ATTEMPTS:
                row = attempt(
                    client,
                    texts[case_id],
                    model,
                    {
                        "case_id": case_id,
                        "round": plan["round"],
                        "verifier": name,
                        "attempt": invalid + 1,
                        "request_sha256": request["request_sha256"],
                        "prompt_sha256": plan["prompt_sha256"],
                        "rubric_version": plan["rubric_version"],
                    },
                    recorded=recorded,
                )
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                rows.append(row)
                sent += 1
                emit(f"{name} {case_id} attempt {row['attempt']}: {row['error'] or row['status']}")
                if row["status"] == "valid":
                    break
                if row["status"] == "unavailable":
                    unavailable = row["error"]
                    break
                invalid += 1
    valid = {row["case_id"] for row in rows if row["status"] == "valid"}
    exhausted = {
        request["case_id"]
        for request in plan["requests"]
        if request["case_id"] not in valid
        and sum(row["case_id"] == request["case_id"] and row["status"] == "invalid" for row in rows)
        >= lv.ATTEMPTS
    }
    return {
        "verifier": name,
        "round": plan["round"],
        "requests": len(plan["requests"]),
        "valid": len(valid),
        "invalid": len(exhausted),
        "pending": len(plan["requests"]) - len(valid) - len(exhausted),
        "sent": sent,
        "unavailable": unavailable,
    }


def rejection_lines(decisions: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """For each rejected case, the rejecting checks with the answer and reason of every verifier."""
    lines = []
    for case_id, decision in decisions.items():
        if decision["outcome"] != "rejected":
            continue
        lines.append(f"{case_id}: rejected")
        for rejecting in decision["rejecting_checks"]:
            lines.append(f"  check {rejecting['check']}")
            for name, verdict in rejecting["verdicts"].items():
                answer = verdict.get("verdict") or verdict.get("level")
                element = f" [{verdict['element']}]" if verdict.get("element") else ""
                reason = verdict.get("reason") or "no reason given"
                lines.append(f"    {name}: {answer}{element} - {reason}")
    return lines


def decide(
    out: Path, drafts: Drafts, repairs: Path | None = None
) -> tuple[dict[str, Any], list[str]]:
    """Recompute the outcomes of one round from its stores and write decisions.json."""
    decided = load_round(out, drafts, repairs)
    outcomes = [decision["outcome"] for decision in decided.decisions.values()]
    summary = {
        "round": decided.plan["round"],
        "confirmed": outcomes.count("confirmed"),
        "rejected": outcomes.count("rejected"),
        "none": outcomes.count("none"),
        "declared_drops": len(decided.plan["declared_drops"]),
    }
    (out / "decisions.json").write_bytes(
        dump(
            {
                "rubric_version": decided.plan["rubric_version"],
                "prompt_sha256": decided.plan["prompt_sha256"],
                "round": decided.plan["round"],
                "plan_sha256": decided.plan_sha256,
                "stores_sha256": decided.store_sha256,
                "summary": summary,
                "cases": [
                    {"case_id": case_id, **decision}
                    for case_id, decision in decided.decisions.items()
                ],
                "declared_drops": decided.plan["declared_drops"],
            }
        )
    )
    return summary, rejection_lines(decided.decisions)


def load_rounds(
    drafts: Drafts, round_1: Path, round_2: Path | None, repairs: Path | None = None
) -> tuple[Round, Round | None]:
    """Read the rounds and refuse plans that are not of these drafts or of each other."""
    first = load_round(round_1, drafts)
    if (
        first.plan["round"] != 1
        or first.plan["inputs"].get("drafts_sha256") != drafts.manifest["jsonl_sha256"]
        or first.plan["inputs"].get("families_sha256") != drafts.manifest["families_sha256"]
        or first.plan["inputs"].get("corpus_sha256") != drafts.corpus["corpus_sha256"]
        or set(first.requests) != set(drafts.by_id())
    ):
        raise ValueError("the plan of round 1 is not of these drafts")
    if round_2 is None or not (round_2 / "plan.json").exists():
        return first, None
    second = load_round(round_2, drafts, repairs)
    if (
        second.plan["round"] != 2
        or second.plan["inputs"].get("previous_plan_sha256") != first.plan_sha256
        or any(second.plan["inputs"].get(key) != first.plan["inputs"][key] for key in BOUND_INPUTS)
    ):
        raise ValueError("the plan of round 2 is not planned on round 1")
    check_drops(first, second, drafts)
    return first, second


def round_entry(decided: Round, case_id: str) -> dict[str, Any]:
    request = decided.requests[case_id]
    return {
        "case_sha256": request["case_sha256"],
        "request_sha256": request["request_sha256"],
        **decided.decisions[case_id],
    }


def sent_counts(rounds: list[Round]) -> dict[str, dict[str, int]]:
    """Per verifier, what was sent. An attempt that met an unavailable verifier is counted too:
    its text may have left the machine."""
    counts: dict[str, dict[str, int]] = {}
    for decided in rounds:
        for name, rows in decided.stores.items():
            total = counts.setdefault(
                name, {"requests": 0, "attempts": 0, "characters": 0, "corpus_texts": 0}
            )
            total["requests"] += len({row["case_id"] for row in rows})
            for row in rows:
                request = decided.requests[row["case_id"]]
                total["attempts"] += 1
                total["characters"] += request["characters"]
                total["corpus_texts"] += request["corpus_texts"]
    return counts


def label_word(drafts: Drafts, plan: Mapping[str, Any], case_id: str, number: object) -> str:
    """The word of a case confirmed in round `number`: by the rubric and the label's author.

    The label checked in round 1 is the one the set holds; the label checked in round 2 was
    written by the repair author.
    """
    written_by = drafts.label_author(case_id) if number == 1 else lv.REPAIR_AUTHOR
    return lv.label_status(plan["rubric_version"], written_by, plan["verifiers"])


def build_outputs(drafts: Drafts, first: Round, second: Round | None) -> tuple[bytes, bytes]:
    """The verified set and its register, as they follow from the drafts, plans and stores."""
    author = drafts.author
    rubric = first.plan["rubric_version"]
    verifier_ids = sorted(first.plan["verifiers"])
    drops = second.drops if second is not None else {}
    rows = []
    entries = []
    for draft in drafts.cases:
        case_id = draft["case_id"]
        one = first.decisions[case_id]
        two = second.decisions.get(case_id) if second is not None else None
        state = lv.case_state(
            one["outcome"], two["outcome"] if two else None, declared_drop=case_id in drops
        )
        rounds = {"1": round_entry(first, case_id)}
        request = first.requests[case_id]
        repair = None
        if second is not None and two is not None:
            rounds["2"] = round_entry(second, case_id)
            request = second.requests[case_id]
            repair = {key: request[key] for key in ("case_sha256", "documents", "families")}
        label: dict[str, Any] = {"status": "none"}
        authority_unverified = False
        kept: Mapping[str, Any] | None = draft
        drop = None
        if state == "verified":
            number = 1 if one["outcome"] == "confirmed" else 2
            if number == 2 and second is not None:
                # The revision the verdicts were given on: the row of the plan is bound to it.
                kept = second.revisions[case_id]
            label = {
                "status": label_word(drafts, first.plan, case_id, number),
                "verifiers": verifier_ids,
                "rubric_version": rubric,
                "round": number,
            }
            if number == 2:
                # The verdicts of round 2 were given on a label its verifier's model wrote.
                label["repair_author"] = dict(lv.REPAIR_AUTHOR)
            elif drafts.label_author(case_id) != author:
                # The set held a label that had been repaired before: its author is named.
                label["repair_author"] = drafts.label_author(case_id)
            authority_unverified = (one if number == 1 else two or {})["authority_unverified"]
        elif state == "dropped":
            kept = None
            drop = (
                lv.drop_record(drops[case_id])
                if case_id in drops
                else {
                    "ground": lv.SECOND_REJECTION,
                    "rejecting_checks": [
                        rejecting["check"] for rejecting in (two or {})["rejecting_checks"]
                    ],
                }
            )
        if kept is not None:
            rows.append(
                {
                    **{key: value for key, value in kept.items() if key not in lv.ADDED_FIELDS},
                    "draft_author": author,
                    "label_check": label,
                    "authority_unverified": authority_unverified,
                }
            )
        verified_revision = request if state == "verified" else first.requests[case_id]
        entries.append(
            {
                "case_id": case_id,
                "state": state,
                "label_check": label if kept is not None else None,
                "authority_unverified": authority_unverified,
                "drafted_class": draft["primary_class"],
                "class": request["primary_class"],
                "safety_critical": verified_revision["safety_critical"],
                "draft_sha256": first.requests[case_id]["case_sha256"],
                "repair": repair,
                "drop": drop,
                "rounds": rounds,
            }
        )
    verified = jsonl(rows)
    summary = lv.summarise(entries)
    rounds_read = [first] if second is None else [first, second]
    register = {
        "schema_version": REGISTER_VERSION,
        "rubric_version": rubric,
        "prompt_sha256": lv.PROMPT_SHA256,
        "label_origin": "agent_labelled",
        "draft_author": author,
        "verifiers": first.plan["verifiers"],
        "repair_author": lv.REPAIR_AUTHOR,
        "sha256": {
            **{key.removesuffix("_sha256"): first.plan["inputs"][key] for key in BOUND_INPUTS},
            "repairs": second.plan["inputs"]["repairs_sha256"] if second is not None else None,
            "drops": second.plan["inputs"]["drops_sha256"] if second is not None else None,
            "plans": {str(decided.plan["round"]): decided.plan_sha256 for decided in rounds_read},
            "stores": {str(decided.plan["round"]): decided.store_sha256 for decided in rounds_read},
            "verified_set": sha256_bytes(verified),
        },
        "sent": sent_counts(rounds_read),
        "complete": summary["complete"],
        "summary": summary,
        "cases": entries,
    }
    return verified, dump(register)


def apply(
    drafts: Drafts,
    round_1: Path,
    round_2: Path | None,
    *,
    repairs: Path | None,
    verified: Path,
    register: Path,
    protected: Sequence[Path] = PROTECTED,
) -> dict[str, Any]:
    """Write the verified set and its register; the drafts and their register are not touched."""
    targets = {verified.resolve(), register.resolve()}
    if len(targets) != 2 or targets & {path.resolve() for path in protected}:
        raise ValueError("the verified set and its register do not replace the drafts")
    first, second = load_rounds(drafts, round_1, round_2, repairs)
    set_bytes, register_bytes = build_outputs(drafts, first, second)
    for path, data in ((verified, set_bytes), (register, register_bytes)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return report(json.loads(register_bytes))


def report(register: Mapping[str, Any]) -> dict[str, Any]:
    """The counts of a verified set: they are reported, the set-level rules do not bind it."""
    summary = register["summary"]
    return {
        "cases": len(register["cases"]),
        "states": summary["states"],
        "verified_by_class": summary["verified_by_class"],
        "authority_unverified": len(summary["authority_unverified"]),
        "safety_critical": summary["safety_critical"],
        "complete": register["complete"],
    }


def check(
    drafts: Drafts,
    round_1: Path,
    round_2: Path | None,
    *,
    repairs: Path | None = None,
    verified: Path,
    register: Path,
    inputs: RoundInputs | None = None,
) -> dict[str, Any]:
    """Recompute the decisions from the stores and refuse a verified set that differs.

    With `inputs` every plan is also built again from the corpus, the scan and, in round 2, the
    repairs and the declared drops: a plan they do not give is refused, and with it a request
    that was not built from the revision its row names.
    """
    first, second = load_rounds(drafts, round_1, round_2, repairs)
    if inputs is not None:
        for read in (first, second):
            if read is None:
                continue
            given = replace(inputs, round=read.plan["round"], previous=round_1, repairs=repairs)
            if build_round(drafts, given)[0] != read.plan:
                raise ValueError(
                    f"the inputs no longer rebuild the plan of round {read.plan['round']}"
                )
    by_id = drafts.by_id()
    drops = second.drops if second is not None else {}
    seen: set[str] = set()
    for row in read_jsonl(verified):
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or case_id not in by_id or case_id in seen:
            raise ValueError(f"the verified set holds an unknown or repeated case: {case_id}")
        seen.add(case_id)
        draft = by_id[case_id]
        one = first.decisions[case_id]["outcome"]
        two = second.decisions.get(case_id, {}).get("outcome") if second is not None else None
        if lv.case_state(one, two, declared_drop=case_id in drops) == "dropped":
            raise ValueError(f"a dropped case is still present: {case_id}")
        content = {key: value for key, value in row.items() if key not in lv.ADDED_FIELDS}
        label = row.get("label_check")
        if not isinstance(label, dict) or label.get("status") != label_word(
            drafts, first.plan, case_id, label.get("round")
        ):
            if content != draft:
                raise ValueError(f"an unrepaired case differs from its draft: {case_id}")
            continue
        number = label.get("round")
        decided = first if number == 1 else second if number == 2 else None
        if decided is None or decided.decisions.get(case_id, {}).get("outcome") != "confirmed":
            raise ValueError(
                f"a verified case is not confirmed by a valid verdict of every verifier: {case_id}"
            )
        if lv.case_sha256(row) != decided.requests[case_id]["case_sha256"]:
            raise ValueError(
                f"a verified case is not the revision its verdicts were given on: {case_id}"
            )
        # A case verified in round 2 is the revision of the repairs file, and that one was held
        # to the bounds of a repair when the round was read.
        if decided is first and content != draft:
            raise ValueError(f"an unrepaired case differs from its draft: {case_id}")
    set_bytes, register_bytes = build_outputs(drafts, first, second)
    if verified.read_bytes() != set_bytes:
        raise ValueError("the verified set is not what the decisions give")
    if register.read_bytes() != register_bytes:
        raise ValueError("the register is not what the decisions give")
    return {"status": "ok", **report(json.loads(register_bytes))}


def main(argv: list[str] | None = None) -> int:
    """Run one command and return the process exit status; a refusal is exit 2."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)

    def rounds(command: argparse.ArgumentParser) -> None:
        # The directories, the scan and the outputs default to those of the set.
        command.add_argument("--set", choices=sorted(SETS), default="pilot")
        command.add_argument("--round-1", type=Path)
        command.add_argument("--round-2", type=Path)

    def sources(command: argparse.ArgumentParser) -> None:
        command.add_argument("--corpus-dir", type=Path)
        command.add_argument("--scan", type=Path)
        command.add_argument("--archive", type=Path, default=ARCHIVE)
        command.add_argument("--repairs", type=Path)
        command.add_argument("--drops", type=Path)

    def built(command: argparse.ArgumentParser) -> None:
        rounds(command)
        command.add_argument("--round", type=int, choices=(1, 2), required=True)
        sources(command)

    built(commands.add_parser("plan"))
    verify_command = commands.add_parser("verify")
    built(verify_command)
    verify_command.add_argument("--verifier", choices=sorted(lv.VERIFIERS), required=True)
    verify_command.add_argument("--limit", type=int)
    decide_command = commands.add_parser("decide")
    rounds(decide_command)
    decide_command.add_argument("--round", type=int, choices=(1, 2), required=True)
    decide_command.add_argument("--repairs", type=Path)
    for name in ("apply", "check"):
        command = commands.add_parser(name)
        rounds(command)
        command.add_argument("--verified", type=Path)
        command.add_argument("--register", type=Path)
        if name == "apply":
            command.add_argument("--repairs", type=Path)
        else:
            sources(command)
            command.add_argument("--rebuild", action="store_true")
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
    chosen = SETS[arguments.set]
    round_1 = arguments.round_1 or chosen.base / "round-1"
    round_2 = arguments.round_2 or chosen.base / "round-2"
    drafts = load_set(arguments.set)
    if arguments.command in ("plan", "verify"):
        out = round_1 if arguments.round == 1 else round_2
        inputs = RoundInputs(
            round=arguments.round,
            corpus_dir=arguments.corpus_dir or corpus_directory(),
            scan=arguments.scan or chosen.base / "wide-scan.json",
            archive=arguments.archive,
            previous=round_1 if arguments.round == 2 else None,
            repairs=arguments.repairs,
            drops=arguments.drops,
        )
        if arguments.command == "plan":
            emit(json.dumps(plan_round(out, drafts, inputs), ensure_ascii=False))
            return 0
        result = verify(out, arguments.verifier, drafts, inputs, limit=arguments.limit)
        emit(json.dumps(result, ensure_ascii=False))
        return 0 if result["valid"] == result["requests"] else 1
    if arguments.command == "decide":
        summary, lines = decide(
            round_1 if arguments.round == 1 else round_2, drafts, arguments.repairs
        )
        for line in lines:
            emit(line)
        emit(json.dumps(summary, ensure_ascii=False))
        return 1 if summary["none"] else 0
    verified = arguments.verified or chosen.verified
    register = arguments.register or chosen.register
    if arguments.command == "apply":
        result = apply(
            drafts,
            round_1,
            round_2,
            repairs=arguments.repairs,
            verified=verified,
            register=register,
            protected=protected(arguments.set),
        )
    else:
        rebuilt: RoundInputs | None = None
        if arguments.rebuild:
            rebuilt = RoundInputs(
                round=1,
                corpus_dir=arguments.corpus_dir or corpus_directory(),
                scan=arguments.scan or chosen.base / "wide-scan.json",
                archive=arguments.archive,
                previous=round_1,
                repairs=arguments.repairs,
                drops=arguments.drops,
            )
        result = check(
            drafts,
            round_1,
            round_2,
            repairs=arguments.repairs,
            verified=verified,
            register=register,
            inputs=rebuilt,
        )
    emit(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

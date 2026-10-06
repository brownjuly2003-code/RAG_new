"""Reference labels of the NLI judge validation - plan slice 2.8.

One model labels the sample of `evaluation/nli_validation.py` in two passes, and the labeller's
control beside them. The rules are in docs/specs/semantic-precision-metrics.md, «Checks by one
model in slices 2.8 and 4.1»; this script is how they run. The check moves in stages, and a
command takes it from one to the next. Before `derive` no command prints or returns a label:
`send` prints request ids with the status of the reply, `next` prints counts of what is sent
next.

    python -m scripts.nli_reference plan     # the sample, the control and the requests of stage 1
    python -m scripts.nli_reference send     # send what waits, in the hashed order; resumable
    python -m scripts.nli_reference next     # stage 2: the top-up and the added control units
    python -m scripts.nli_reference send     # ... and send those
    python -m scripts.nli_reference derive   # stage 4: the labels and the stability bound
    python -m scripts.nli_reference check    # every file against the rules

`send` exits 1 while requests wait: a usage limit or an outage leaves the request in its store
as unavailable, and the same command sends it again.

The files, under `reports/nli-validation/v1/`:

- `plan.json` - the sample by claim id, the control order and the requests of stage 1 with the
  SHA-256 of their texts. It holds no text: every command rebuilds the pool from the
  registered inputs and refuses a plan the inputs no longer rebuild.
- `pass1.jsonl`, `pass2.jsonl`, `control-pass1.jsonl`, `control-pass2.jsonl` - the replies as
  given, each pass in a store of its own and the control apart, with the session record of
  every reply.
- `stage2.json` - what `next` lists: the top-up units and the control units drawn beyond the
  first twenty, with their requests.
- `labels.json` - what `derive` writes: the labels of both passes for every unit of the
  sample, the reference label, the control and the stability bound.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from pathlib import Path
from typing import Any, TextIO

from evaluation import isolated_request as isolated
from evaluation import nli_validation as nv
from scripts.devset_label_verify import IsolatedClient, attempt, emit

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "nli-validation" / "v1"
PLAN = "plan.json"
STAGE_2 = "stage2.json"
LABELS = "labels.json"
STORES = {
    ("unit", 1): "pass1.jsonl",
    ("unit", 2): "pass2.jsonl",
    ("control", 1): "control-pass1.jsonl",
    ("control", 2): "control-pass2.jsonl",
}
STATUSES = ("valid", "invalid", "unavailable")
SUPPORTED: nv.Reference = {"state": "stable", "label": "supported"}
NOT_SUPPORTED: nv.Reference = {"state": "stable", "label": "not_supported"}


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump(value), encoding="utf-8", newline="\n")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request(
    by_id: Mapping[str, Mapping[str, Any]],
    *,
    kind: str,
    number: int,
    stage: int,
    shows: str,
    contexts_of: str,
    serves: Sequence[str],
) -> dict[str, Any]:
    request = nv.request_id(shows, number, control=kind == "control")
    text = nv.request_text(by_id[shows], by_id[contexts_of]["contexts"], request)
    return {
        "request_id": request,
        "kind": kind,
        "pass": number,
        "stage": stage,
        "shows": shows,
        "contexts_of": contexts_of,
        "serves": list(serves),
        "request_sha256": nv.sha256_text(text),
    }


def unit_requests(
    by_id: Mapping[str, Mapping[str, Any]], units: Sequence[Mapping[str, Any]], stage: int
) -> list[dict[str, Any]]:
    """Both passes of every labelling unit that no earlier request labels."""
    return [
        _request(
            by_id,
            kind="unit",
            number=number,
            stage=stage,
            shows=unit["request_id"],
            contexts_of=unit["request_id"],
            serves=unit["serves"],
        )
        for unit in units
        if unit["new"]
        for number in nv.PASSES
    ]


def control_requests(
    by_id: Mapping[str, Mapping[str, Any]], order: Sequence[str], start: int, drawn: int, stage: int
) -> tuple[list[dict[str, Any]], list[str]]:
    """Both passes of the control units `start`..`drawn` of the order; and those left alone.

    The partner of a unit is looked for among the first `drawn` units of the order.
    """
    units = [by_id[key] for key in order]
    requests: list[dict[str, Any]] = []
    alone: list[str] = []
    for index in range(start, drawn):
        partner = nv.control_partner(units, index, drawn)
        if partner is None:
            alone.append(order[index])
            continue
        requests += [
            _request(
                by_id,
                kind="control",
                number=number,
                stage=stage,
                shows=order[index],
                contexts_of=order[partner],
                serves=(),
            )
            for number in nv.PASSES
        ]
    return requests, alone


def in_order(requests: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(requests, key=lambda request: nv.sending_order(request["request_id"]))


def build_plan(root: Path = ROOT) -> dict[str, Any]:
    """The sample, the control and the requests of stage 1, from the registered inputs alone."""
    if (
        nv.prompt_sha256() != nv.PROMPT_SHA256
        or nv.sha256_text(nv.SYSTEM_PROMPT) != nv.SYSTEM_PROMPT_SHA256
    ):
        raise ValueError("the prompt is not the registered one")
    pool = nv.build_pool(root)
    by_id = {unit["claim_id"]: unit for unit in pool}
    drawn = nv.draw(pool)
    sample = drawn["sample"]
    order = nv.control_order(pool, sample)
    first = min(nv.CONTROL_FIRST, len(order))
    controls, alone = control_requests(by_id, order, 0, first, 1)
    requests = unit_requests(by_id, nv.labelling_units(pool, sample), 1) + controls
    return {
        "version": nv.RUBRIC_VERSION,
        "seed": nv.SEED,
        "inputs": {
            **{name: {"path": row[0], "sha256": row[1]} for name, row in nv.REPORTS.items()},
            "candidates": {"path": nv.CANDIDATES[0], "sha256": nv.CANDIDATES[1]},
            "families": {"path": nv.FAMILIES[0], "sha256": nv.FAMILIES[1]},
        },
        "route": {"name": isolated.ROUTE, **isolated.settings(nv.SYSTEM_PROMPT)},
        "prompt_sha256": nv.PROMPT_SHA256,
        "attempts": nv.ATTEMPTS,
        "sample": [
            {
                "claim_id": key,
                "source": by_id[key]["source"],
                "case_id": by_id[key]["case_id"],
                "stratum": by_id[key]["stratum"],
            }
            for key in sample
        ],
        "replacements": drawn["replacements"],
        "summary": nv.summary(pool, sample),
        "top_up_available": len(nv.top_up(pool, sample)),
        "control": {
            "tag": nv.CONTROL_TAG,
            "order": order,
            "first": first,
            "without_partner": alone,
        },
        "requests": in_order(requests),
    }


def load_plan(out: Path, root: Path = ROOT) -> dict[str, Any]:
    path = out / PLAN
    if not path.exists():
        raise ValueError("no plan: run plan")
    plan = _load(path)
    if plan != json.loads(_dump(build_plan(root))):
        raise ValueError("the inputs no longer rebuild the plan")
    return plan


def read_stores(
    out: Path, requests: Sequence[Mapping[str, Any]], plan: Mapping[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    """The stored rows of every request; refuse a row or a history `send` does not write.

    The attempt of a row is one more than the invalid replies before it, three attempts in
    all, and nothing follows a valid reply: the first valid reply is final. A reply counts only
    with the record of a session that loaded nothing, of the registered model.
    """
    planned = {request["request_id"]: request for request in requests}
    rows: dict[str, list[dict[str, Any]]] = {}
    for (kind, number), name in STORES.items():
        path = out / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            request = planned.get(row.get("request_id"))
            if (
                request is None
                or (request["kind"], request["pass"]) != (kind, number)
                or row.get("request_sha256") != request["request_sha256"]
                or row.get("prompt_sha256") != plan["prompt_sha256"]
                or row.get("rubric_version") != plan["version"]
                or row.get("status") not in STATUSES
            ):
                raise ValueError(f"{name} holds a row that is not of this plan")
            mine = rows.setdefault(request["request_id"], [])
            invalid = sum(earlier["status"] == "invalid" for earlier in mine)
            if (
                any(earlier["status"] == "valid" for earlier in mine)
                or invalid >= nv.ATTEMPTS
                or row.get("attempt") != invalid + 1
            ):
                raise ValueError(f"{name} holds attempts that send does not write")
            if row["status"] != "unavailable":
                try:
                    isolated.check_record(row.get("session"))
                except ValueError as exc:
                    raise ValueError(
                        f"a stored reply the route does not vouch for: {exc}"
                    ) from None
                if row.get("model") != isolated.MODEL:
                    raise ValueError(f"{name} holds a reply of another model")
            if row["status"] == "valid":
                try:
                    nv.parse_reply(row["raw_reply"])
                except nv.ReplyFormatError:
                    raise ValueError(f"{name} counts a reply that is not in the form") from None
            mine.append(row)
    return rows


def state(rows: Sequence[Mapping[str, Any]]) -> str:
    """`valid`, `invalid` (three replies out of form) or `pending`."""
    if any(row["status"] == "valid" for row in rows):
        return "valid"
    if sum(row["status"] == "invalid" for row in rows) >= nv.ATTEMPTS:
        return "invalid"
    return "pending"


def reply_of(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    for row in rows:
        if row["status"] == "valid":
            return nv.parse_reply(row["raw_reply"])
    return None


def _passes(
    requests: Sequence[Mapping[str, Any]],
    rows: Mapping[str, Sequence[Mapping[str, Any]]],
    kind: str,
) -> dict[str, dict[int, dict[str, Any] | None]]:
    """For every shown unit of a kind: the reply of each pass, None where there is none."""
    passes: dict[str, dict[int, dict[str, Any] | None]] = {}
    for request in requests:
        if request["kind"] == kind:
            passes.setdefault(request["shows"], {})[request["pass"]] = reply_of(
                rows.get(request["request_id"], [])
            )
    return passes


def _reference(replies: Mapping[int, Mapping[str, Any] | None]) -> nv.Reference:
    first, second = (replies.get(number) for number in nv.PASSES)
    return nv.reference(first and first["label"], second and second["label"])


def build_stage_2(
    plan: Mapping[str, Any],
    pool: Sequence[Mapping[str, Any]],
    rows: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    """What the registered rules send after stage 1: the top-up and the added control units.

    Fields are compared and none is shown: the document names units and requests, no label.
    """
    if any(state(rows.get(request["request_id"], [])) == "pending" for request in plan["requests"]):
        raise ValueError("stage 1 is not complete: run send")
    by_id = {unit["claim_id"]: unit for unit in pool}
    passes = _passes(plan["requests"], rows, "unit")
    own = {
        key: _reference(passes[request["shows"]])
        for request in plan["requests"]
        if request["kind"] == "unit"
        for key in request["serves"]
    }
    sample = [row["claim_id"] for row in plan["sample"]]
    lacking = sum(own[key] == NOT_SUPPORTED for key in sample) < nv.TOP_UP_BELOW
    added = nv.top_up(pool, sample) if lacking else []
    units = nv.labelling_units(pool, added, sorted(passes))
    order = plan["control"]["order"]
    drawn = nv.control_drawn([own[key] == SUPPORTED for key in order])
    controls, alone = control_requests(by_id, order, plan["control"]["first"], drawn, 2)
    return {
        "version": plan["version"],
        "top_up": added,
        "served_by_stage_1": {
            key: unit["request_id"] for unit in units if not unit["new"] for key in unit["serves"]
        },
        "control_drawn": drawn,
        "control_without_partner": alone,
        "requests": in_order(unit_requests(by_id, units, 2) + controls),
    }


def load_stage_2(
    out: Path, plan: Mapping[str, Any], pool: Sequence[Mapping[str, Any]]
) -> dict[str, Any] | None:
    path = out / STAGE_2
    if not path.exists():
        return None
    stage = _load(path)
    rows = read_stores(out, [*plan["requests"], *stage["requests"]], plan)
    if stage != json.loads(_dump(build_stage_2(plan, pool, rows))):
        raise ValueError("the stores of stage 1 no longer rebuild stage 2")
    return stage


def _counts(requests: Sequence[Mapping[str, Any]], rows: Mapping[str, Any]) -> dict[str, int]:
    states = Counter(state(rows.get(request["request_id"], [])) for request in requests)
    return {
        "requests": len(requests),
        "valid": states["valid"],
        "invalid": states["invalid"],
        "pending": states["pending"],
    }


def send(
    out: Path, *, client: Any = None, limit: int | None = None, root: Path = ROOT
) -> dict[str, Any]:
    """Send the requests that wait, in the hashed order; stop when the model is unavailable."""
    plan = load_plan(out, root)
    pool = nv.build_pool(root)
    by_id = {unit["claim_id"]: unit for unit in pool}
    stage = load_stage_2(out, plan, pool)
    requests = in_order([*plan["requests"], *(stage["requests"] if stage else [])])
    rows = read_stores(out, requests, plan)
    if client is None:
        client = IsolatedClient(
            os.environ.get("RAG_VERIFY_CLAUDE_CLI", "").strip() or None,
            system_prompt=nv.SYSTEM_PROMPT,
        )
    taken = sent = 0
    unavailable: str | None = None
    with ExitStack() as opened:
        handles: dict[str, TextIO] = {}
        for request in requests:
            mine = rows.setdefault(request["request_id"], [])
            if state(mine) != "pending":
                continue
            if unavailable is not None or (limit is not None and taken >= limit):
                break
            taken += 1
            text = nv.request_text(
                by_id[request["shows"]],
                by_id[request["contexts_of"]]["contexts"],
                request["request_id"],
            )
            if nv.sha256_text(text) != request["request_sha256"]:
                raise ValueError(f"the request text is not the plan's: {request['request_id']}")
            name = STORES[(request["kind"], request["pass"])]
            if name not in handles:
                # Opened before the first request: no reply is asked for that cannot be kept.
                handles[name] = opened.enter_context(
                    (out / name).open("a", encoding="utf-8", newline="\n")
                )
            invalid = sum(row["status"] == "invalid" for row in mine)
            while invalid < nv.ATTEMPTS:
                row = attempt(
                    client,
                    text,
                    isolated.MODEL,
                    {
                        "request_id": request["request_id"],
                        "kind": request["kind"],
                        "pass": request["pass"],
                        "attempt": invalid + 1,
                        "request_sha256": request["request_sha256"],
                        "prompt_sha256": plan["prompt_sha256"],
                        "rubric_version": plan["version"],
                    },
                    recorded=True,
                    parse=nv.parse_reply,
                )
                handles[name].write(json.dumps(row, ensure_ascii=False) + "\n")
                handles[name].flush()
                os.fsync(handles[name].fileno())
                mine.append(row)
                sent += 1
                emit(
                    f"{request['request_id']} attempt {row['attempt']}: "
                    f"{row['error'] or row['status']}"
                )
                if row["status"] == "valid":
                    break
                if row["status"] == "unavailable":
                    unavailable = row["error"]
                    break
                invalid += 1
    return {**_counts(requests, rows), "sent": sent, "unavailable": unavailable}


def next_stage(out: Path, root: Path = ROOT) -> dict[str, Any]:
    """List stage 2 once stage 1 is stored; print what is sent next, never a label."""
    plan = load_plan(out, root)
    pool = nv.build_pool(root)
    stage = load_stage_2(out, plan, pool)
    if stage is None:
        stage = json.loads(
            _dump(build_stage_2(plan, pool, read_stores(out, plan["requests"], plan)))
        )
        _write(out / STAGE_2, stage)
    return {
        "top_up_units": len(stage["top_up"]),
        "top_up_units_labelled_in_stage_1": len(stage["served_by_stage_1"]),
        "control_units_added": stage["control_drawn"] - plan["control"]["first"],
        "control_units_without_partner": len(stage["control_without_partner"]),
        "requests": len(stage["requests"]),
    }


def build_labels(out: Path, root: Path = ROOT) -> dict[str, Any]:
    """Stage 4: the labels of every unit of the sample, the control and the stability bound."""
    plan = load_plan(out, root)
    pool = nv.build_pool(root)
    by_id = {unit["claim_id"]: unit for unit in pool}
    stage = load_stage_2(out, plan, pool)
    if stage is None:
        raise ValueError("stage 2 is not listed: run next")
    requests = [*plan["requests"], *stage["requests"]]
    rows = read_stores(out, requests, plan)
    if _counts(requests, rows)["pending"]:
        raise ValueError("requests wait: run send")
    passes = _passes(requests, rows, "unit")
    served = {
        key: request["shows"]
        for request in requests
        if request["kind"] == "unit"
        for key in request["serves"]
    }
    served.update(stage["served_by_stage_1"])
    added = set(stage["top_up"])
    sample = [row["claim_id"] for row in plan["sample"]] + stage["top_up"]
    units = []
    for key in sample:
        replies = passes[served[key]]
        verdict = _reference(replies)
        units.append(
            {
                "claim_id": key,
                "source": by_id[key]["source"],
                "case_id": by_id[key]["case_id"],
                "stratum": by_id[key]["stratum"],
                "top_up": key in added,
                "request_id": served[key],
                "passes": [
                    None
                    if (reply := replies.get(number)) is None
                    else {
                        "label": reply["label"],
                        "flags": reply["flags"],
                        "contexts": nv.cited_contexts(reply, nv.request_id(served[key], number)),
                    }
                    for number in nv.PASSES
                ],
                "state": verdict["state"],
                "label": verdict["label"],
            }
        )
    own = {unit["claim_id"]: unit for unit in units}
    serving = Counter(served[key] for key in sample)
    labelled = [
        {
            "case_id": by_id[shown]["case_id"],
            "serves": serving[shown],
            "first": (replies.get(1) or {}).get("label"),
            "second": (replies.get(2) or {}).get("label"),
        }
        for shown, replies in sorted(passes.items())
    ]
    controls = _passes(requests, rows, "control")
    partners = {
        request["shows"]: request["contexts_of"]
        for request in requests
        if request["kind"] == "control"
    }
    control = [
        {
            "claim_id": key,
            "partner": partners.get(key),
            "own": {"state": own[key]["state"], "label": own[key]["label"]},
            "first": ((controls.get(key) or {}).get(1) or {}).get("label"),
            "second": ((controls.get(key) or {}).get(2) or {}).get("label"),
        }
        for key in plan["control"]["order"][: stage["control_drawn"]]
    ]
    strata: dict[str, Counter[str]] = {name: Counter() for name in nv.STRATA}
    for unit in units:
        strata[unit["stratum"]][unit["label"] or unit["state"]] += 1
    return {
        "version": plan["version"],
        "prompt_sha256": plan["prompt_sha256"],
        "files": {
            name: _sha256(out / name)
            for name in (PLAN, STAGE_2, *STORES.values())
            if (out / name).exists()
        },
        "units": units,
        "control": control,
        "stability": nv.stability(
            labelled, [{**row, "partner": row["partner"] is not None} for row in control]
        ),
        "counts": {
            "sample": len(plan["sample"]),
            "top_up": len(stage["top_up"]),
            "labelling_units": len(passes),
            "stable_not_supported": sum(
                (unit["state"], unit["label"]) == ("stable", "not_supported") for unit in units
            ),
            "strata": {
                name: {
                    key: counted[key]
                    for key in ("supported", "not_supported", "not_claim", "unstable", "invalid")
                }
                for name, counted in strata.items()
            },
        },
    }


def derive(out: Path, root: Path = ROOT) -> dict[str, Any]:
    labels = json.loads(_dump(build_labels(out, root)))
    _write(out / LABELS, labels)
    return {"stability": labels["stability"], "counts": labels["counts"]}


def check(out: Path, root: Path = ROOT) -> dict[str, Any]:
    """Every file against the rules; the states of the requests, and no label."""
    plan = load_plan(out, root)
    pool = nv.build_pool(root)
    stage = load_stage_2(out, plan, pool)
    requests = [*plan["requests"], *(stage["requests"] if stage else [])]
    rows = read_stores(out, requests, plan)
    derived = (out / LABELS).exists()
    if derived and _load(out / LABELS) != json.loads(_dump(build_labels(out, root))):
        raise ValueError("the stores no longer derive the stored labels")
    return {
        "stage_1": _counts(plan["requests"], rows),
        "stage_2": _counts(stage["requests"], rows) if stage else None,
        "labels_derived": derived,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("plan", "send", "next", "derive", "check"))
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--limit", type=int)
    arguments = parser.parse_args(argv)
    out: Path = arguments.out
    try:
        if arguments.command == "plan":
            plan = json.loads(_dump(build_plan()))
            if (out / PLAN).exists() and _load(out / PLAN) != plan:
                raise ValueError(
                    "another plan is stored: a new rubric version takes a new directory"
                )
            _write(out / PLAN, plan)
            result: dict[str, Any] = {
                "requests": len(plan["requests"]),
                "summary": plan["summary"],
                "replacements": len(plan["replacements"]),
                "top_up_available": plan["top_up_available"],
                "plan_sha256": _sha256(out / PLAN),
            }
        elif arguments.command == "send":
            result = send(out, limit=arguments.limit)
        elif arguments.command == "next":
            result = next_stage(out)
        elif arguments.command == "derive":
            result = derive(out)
        else:
            result = check(out)
    except ValueError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 1 if arguments.command == "send" and result["pending"] else 0


if __name__ == "__main__":
    sys.exit(main())

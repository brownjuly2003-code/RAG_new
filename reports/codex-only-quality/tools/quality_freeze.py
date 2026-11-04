"""Offline capture adaptation and the registered ceiling judge orchestration.

Private layout: <private>/<series>/{state,stand,judge-route}.json; attempts/<id>/;
<key>.partial is retained on failure, renamed last to <key>, containing runs/,
measurement.json, locations.json, receipt.json, references.jsonl and m1/bridge.
Only grade can send requests. Historical instruments load from repository paths.
"""

from __future__ import annotations

import contextlib
import copy
import io
import os
import re
import shutil
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import quality_driver as d

cv = d.cv
METRICS = ("m1", "bridge")
INSTRUCTIONS_SHA256 = "fd015e742c835a17b17704ad629df90a34a61ac600762e8c74e52aababdcc9c2"
SALT = "chat-answer-judge-2026-10-18"


def modules(repo: Path) -> tuple[Any, Any]:
    c = d.canonical_import(repo, "ceiling_common", "reports/generator-ceiling/tools")
    grading = d.canonical_import(repo, "ceiling_judge", "reports/generator-ceiling/tools")
    return c, grading


def active_stops(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in state["stops"] if s["code"] == 2 or not s.get("resolved")]


def whole(key, state, package, series, *, alive=None):
    cv.require(not active_stops(state), "arm has a rule or unresolved infrastructure stop")
    cv.require(state["pilot_passed"] and state["pilot_step"] == 20, "all-20 pilot not passed")
    measured = {r["case_id"]: r for r in state["cases"].values() if r["key"] == key}
    cv.require(
        len(measured) == len(package) == 100
        and set(measured) == {r["case_id"] for r in package}
        and all(r["status"] in d.TERMINAL for r in measured.values()),
        "key not whole; missing or pending case",
    )
    stand_path = series / "stand.json"
    if stand_path.exists():
        stand = cv.read(stand_path)
        if stand and stand["key"] == key:
            live = alive or d.sr.WindowsSystem().alive
            cv.require(
                not any(live(d.sr.Process(**p)) for p in stand["processes"]),
                "recorded stand is alive",
            )
    return measured


def sse_result(path: Path) -> dict[str, Any] | None:
    data: list[str] = []
    results: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            if data:
                event = cv.decode("\n".join(data).encode())
                cv.require(isinstance(event, dict), "invalid SSE object")
                if event.get("type") == "result":
                    results.append(event)
                data = []
        elif line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
        else:
            cv.require(line.startswith((":", "event:", "id:", "retry:")), "invalid SSE line")
    cv.require(not data and len(results) <= 1, "incomplete or repeated SSE result")
    return results[0] if results else None


def capture_bindings(capture, state, series_name):
    owners = {}
    for row in state["cases"].values():
        for attempt in row["attempts"]:
            for call in attempt["calls"]:
                cv.require(call["folder"] not in owners, "ambiguous capture ownership")
                owners[call["folder"]] = attempt
    bound = {}
    for folder in (capture / "calls").iterdir():
        cv.no_links(folder)
        owner = owners.get(folder.name)
        try:
            start = cv.read(folder / "start.json")
            active = cv.decode(start["active_case"].encode())
            cv.require(isinstance(active, dict), "invalid capture binding")
        except (OSError, ValueError, KeyError, AttributeError, TypeError):
            # A diagnosed infrastructure attempt can retain an incomplete capture.
            # This exception never supplies a prompt for a terminal attempt.
            cv.require(
                owner is not None and owner["classification"] == "infrastructure",
                "unbound or missing terminal capture",
            )
            bound.setdefault(owner["id"], set()).add(folder.name)
            continue
        if active.get("series") == series_name:
            cv.require(
                owner is not None and active.get("attempt_id") == owner["id"],
                "unrecorded or ambiguous capture",
            )
            bound.setdefault(owner["id"], set()).add(folder.name)
        else:
            cv.require(owner is None, "capture belongs to another series")
    return bound


def audit(key, series, config, registration, package, measured, repo, state):
    """Replay the existing classification from durable captures, never from package answers."""
    _, route, _, journal = d.instruments(repo)
    inspector = object.__new__(d.Chunk)
    inspector.config, inspector.registration = config, registration
    inspector.capture, inspector.journal, inspector.route = (
        Path(config["capture_root"]),
        journal,
        route,
    )
    files, capture_files, selected = {}, {}, {}
    # Read every call's binding once: an omitted answer cannot masquerade as absence.
    bound = capture_bindings(inspector.capture, state, series.name)
    for case in package:
        row = measured[case["case_id"]]
        cv.require(bool(row["attempts"]), "terminal case has no attempts")
        rebuilt = d.initial_state(registration)
        for attempt in row["attempts"]:
            folder = series / "attempts" / cv.relative(attempt["id"])
            launch, outcome = cv.read(folder / "launch.json"), cv.read(folder / "outcome.json")
            cv.require(outcome == attempt, "attempt journal differs from state")
            cv.require(
                launch["question"] == case["question"]
                and launch["case_id"] == case["case_id"]
                and launch["key"] == key
                and launch["series"] == series.name
                and launch["id"] == launch["attempt_id"] == attempt["id"],
                "attempt identity differs",
            )
            names = {c["folder"] for c in attempt["calls"]}
            cv.require(names == bound.get(attempt["id"], set()), "unrecorded or missing capture")
            if attempt["classification"] in d.TERMINAL:
                response = cv.read(folder / "response.json")
                result = sse_result(folder / "stream.sse")
                cv.require(result == response.get("result"), "SSE and response differ")
                current = inspector.inspect(launch, response, names)
                current["tickets"] = attempt["tickets"]
                cv.require(current == attempt, "capture classification differs")
                selected[case["case_id"]] = attempt
            d.reduce_request(rebuilt, attempt)
            files.update(
                {
                    "attempts/" + attempt["id"] + "/" + f["path"]: f["sha256"]
                    for f in cv.tree_files(folder)
                }
            )
            for name in names:
                capture_files.update(
                    {
                        "calls/" + name + "/" + f["path"]: f["sha256"]
                        for f in cv.tree_files(inspector.capture / "calls" / name)
                    }
                )
        cv.require(rebuilt["cases"][key + ":" + case["case_id"]] == row, "case reduction differs")
    return selected, files, capture_files


def prompt_bytes(attempt, question, capture, repo):
    journal = d.canonical_import(repo, "capture_journal", "reports/codex-only-quality/tools")
    judge = modules(repo)[0].judge()
    calls = [c for c in attempt["calls"] if c["effort"] == "xhigh"]
    cv.require(len(calls) <= 1, "ambiguous answer call")
    derived = not calls
    if calls:
        call = calls[0]
        raw = (capture / "calls" / cv.relative(call["folder"]) / "stdin.bin").read_bytes()
        cv.require(cv.digest(raw) == call["stdin_sha256"], "answer capture changed")
        text = journal.unwrap(raw)
        cv.require(cv.digest(text) == attempt["answer_prompt_sha256"], "answer prompt changed")
    else:
        cv.require(
            (
                attempt["classification"] == "accepted"
                and attempt.get("audited_absence") is True
                and attempt.get("early_handover")
                and attempt["result"].get("route") == "human"
            )
            or (
                attempt["classification"] == "product_failure"
                and any(c["classification"] == "product_timeout" for c in attempt["calls"])
            ),
            "absence of answer call not audited",
        )
        prompts = d.canonical_import(repo, "agent.prompts", "")
        experiment = SimpleNamespace(prompt_overrides={"qa": prompts.PROMPT_REGISTRY["qa"]["text"]})
        text = prompts.build_qa_prompt(question, [], experiment=experiment)
    parsed_question, docs = judge.read_prompt(text)
    cv.require(
        judge.prompt_id(text) == "QA_PROMPT_V4" and parsed_question == question,
        "V4 question differs",
    )
    cv.require(not derived or not docs, "derived frame has documents")
    raw = text.encode("utf-8")
    cv.require(b"\r" not in raw, "prompt is not LF")
    return raw, derived


def case_value(ident, question, attempt):
    result = copy.deepcopy(attempt["result"])
    answer = result.get("answer") if attempt["classification"] == "accepted" else ""
    cv.require(isinstance(answer, str), "displayed answer absent")
    result.update(type="result", answer=answer)
    return {"case_id": ident, "question": question, "events": [result], "answer": answer}


def copy_runs(key, source, target, attempts, config, repo):
    cv.require(not target.exists(), "arm runs already exist")
    judge = modules(repo)[0].judge()
    measurement, paths = {}, {}
    for batch in range(1, 11):
        label = f"final-answers-{key}-b{batch:02d}"
        before, after = source / label, target / label
        paths[label] = after
        (after / "prompts").mkdir(parents=True)
        (after / "cases").mkdir()
        shutil.copyfile(before / "launch.json", after / "launch.json")
        package = d.table(judge.run_answers(before))
        cv.require(len(package) == 10, "package batch count differs")
        for file in sorted((before / "cases").glob("*.json")):
            original = cv.read(file)
            ident = original["case_id"]
            case, attempt = package[ident], attempts[ident]
            raw, derived = prompt_bytes(
                attempt, case["question"], Path(config["capture_root"]), repo
            )
            (after / "prompts" / cv.relative(case["prompt_file"])).write_bytes(raw)
            cv.write(after / "cases" / file.name, case_value(ident, case["question"], attempt))
            measurement[ident] = {
                "case_id": ident,
                "class": attempt["classification"],
                "derived": derived,
                "prompt_sha256": cv.digest(raw),
                "captured_prompt_sha256": None if derived else cv.digest(raw),
                "package_prompt_sha256": case["prompt_sha256"],
                "attempt_id": attempt["id"],
            }
        parsed = d.table(judge.run_answers(after), list(package))
        for ident, case in package.items():
            prompt = (after / "prompts" / case["prompt_file"]).read_bytes()
            row = parsed[ident]
            cv.require(
                row["question"] == case["question"]
                and row["documents"] == judge.read_prompt(prompt.decode())[1]
                and row["route"] == attempts[ident]["result"].get("route")
                and row["prompt_sha256"] == cv.digest(prompt),
                "adapted run differs",
            )
    cv.require(
        set(measurement) == set(attempts) and len(measurement) == 100, "arm case set differs"
    )
    return paths, measurement


def check_instructions(judge):
    cv.require(
        cv.digest(judge.INSTRUCTIONS) == INSTRUCTIONS_SHA256 and judge.SALT == SALT,
        "judge instructions/salt mismatch",
    )
    cv.require(
        judge.isolated.MODEL == "claude-opus-5-5" and judge.isolated.EFFORT == "max",
        "judge model/effort mismatch",
    )


def validate_frozen(key, work, pin, series, registration, repo):
    c, _ = modules(repo)
    cv.require(
        pin["key"] == key
        and pin["registration_sha256"] == cv.digest(cv.encoded(registration))
        and pin["tools"] == registration["files"]
        and set(pin["plans"]) == set(METRICS),
        "receipt registration differs",
    )
    for metric in METRICS:
        plan = cv.read(work / metric / "plan.json")
        cv.require(
            cv.sha(work / metric / "plan.json") == pin["plans"][metric]
            and c.instruments().judge.counts(plan, metric) == pin["requests"][metric],
            "frozen plan changed",
        )
        c.judge().check_plan(plan)
    cv.require(c.tree_hashes(work / "runs") == pin["answer_files"], "frozen runs changed")
    for name in ("locations", "measurement"):
        cv.require(
            cv.sha(work / (name + ".json")) == pin[name + "_sha256"], "private binding changed"
        )
    measurement = cv.read(work / "measurement.json")
    cv.require(measurement == pin["cases"], "public/private measurement differs")
    bind_state(key, cv.read(series / "state.json"), measurement)
    locations = cv.read(work / "locations.json")
    for root, names in (
        (series, pin["attempt_files"]),
        (Path(locations["capture"]), pin["capture_files"]),
        (Path(locations["source"]), pin["source_inputs"]),
    ):
        for name, expected in names.items():
            cv.require(cv.sha(root / cv.relative(name)) == expected, "frozen input changed")
    old = repo / d.ATTEMPT / f"ceiling-{key}-judge-m1.json"
    cv.require(
        cv.sha(old) == pin["old"]["m1"]["record_sha256"]
        and cv.sha(old.with_suffix(".cases.jsonl")) == pin["old"]["m1"]["cases_sha256"],
        "old side changed",
    )
    cv.require(
        c.instruments().judge.source_gate(locations["source_judge"], cv.read(old)) == pin["source"],
        "bridge source changed",
    )
    c.instruments().common.protocol.seed_gate(work / "bridge/verdicts.jsonl", pin["bridge_seed"])
    if key in cv.KEYS[:2]:
        cv.require(
            cv.sha(work / "references.jsonl")
            == pin["references_sha256"]
            == cv.sha(Path(locations["references"])),
            "references changed",
        )


def bind_state(key, state, measurement):
    """Frozen terminal attempts remain the arm even if other keys progress later."""
    cv.require(state["pilot_passed"] and state["pilot_step"] == 20, "all-20 pilot not passed")
    rows = {r["case_id"]: r for r in state["cases"].values() if r["key"] == key}
    cv.require(
        len(rows) == len(measurement) == 100 and set(rows) == set(measurement),
        "frozen case set differs",
    )
    cv.require(
        all(
            r["status"] in d.TERMINAL
            and r["status"] == measurement[cid]["class"]
            and r["attempts"]
            and r["attempts"][-1]["id"] == measurement[cid]["attempt_id"]
            and cv.digest(cv.encoded(r)) == measurement[cid]["state_sha256"]
            for cid, r in rows.items()
        ),
        "frozen case status or attempt differs",
    )


def recover_partial(work, receipt, validate):
    cv.require(not work.exists(), "key already frozen")
    partial = work.with_name(work.name + ".partial")
    if partial.exists():
        cv.require(
            receipt.exists()
            and (partial / "receipt.json").exists()
            and cv.sha(receipt) == cv.sha(partial / "receipt.json"),
            "incomplete partial freeze retained",
        )
        pin = cv.read(receipt)
        validate(partial, pin)
        partial.rename(work)
        return pin
    cv.require(not receipt.exists(), "receipt already exists")
    return None


def freeze(args, repo=d.ROOT, *, alive=None):
    config, registration = d.admit_chunk(
        SimpleNamespace(**{**vars(args), "budget": 600}), repo, offline=True
    )
    c, _ = modules(repo)
    check_instructions(c.judge())
    series, records = args.private / args.series, args.records / args.series
    state = cv.read(series / "state.json")
    cv.require(
        state["registration_sha256"] == cv.digest(cv.encoded(registration)),
        "state registration differs",
    )
    cv.require(not c.judge_stops(series), "judge stopped")
    packages, _ = d.load_packages(repo, config)
    d.bind_attempt02(repo, config, packages)
    measured = whole(args.key, state, packages[args.key], series, alive=alive)
    work, receipt = series / args.key, records / f"plans-{args.key}.json"
    recovered = recover_partial(
        work,
        receipt,
        lambda folder, pin: validate_frozen(args.key, folder, pin, series, registration, repo),
    )
    if recovered is not None:
        return recovered
    attempts, files, captures = audit(
        args.key, series, config, registration, packages[args.key], measured, repo, state
    )
    inputs = config["private_inputs"]
    source = Path(
        inputs["stage5_aircargo_runs" if args.key == "aircargo" else "stage5_runs"]["root"]
    )
    source_judge = Path(inputs["attempt02_journals"]["root"]) / args.key / "m1"
    old_path = repo / d.ATTEMPT / f"ceiling-{args.key}-judge-m1.json"
    old, old_rows = cv.read(old_path), d.table(cv.rows(old_path.with_suffix(".cases.jsonl")))
    source_pin = c.instruments().judge.source_gate(source_judge, old)
    refs = (
        Path(inputs["stage5_references"]["root"]) / (args.key + ".jsonl")
        if args.key != "aircargo"
        else None
    )
    if refs:
        reference_rows = d.table(cv.rows(refs), list(measured))
        cv.require(cv.sha(refs) == old["provenance"]["references_sha256"], "reference hash differs")
        cv.require(
            all(
                reference_rows[cid][name] == old_rows[cid][name]
                for cid in measured
                for name in ("cluster", "stratum")
            ),
            "reference strata/clusters differ",
        )
    partial = work.with_name(work.name + ".partial")
    c.disjoint(partial, [source, source_judge, *([refs] if refs else [])])
    paths, measurement = copy_runs(args.key, source, partial / "runs", attempts, config, repo)
    for cid, entry in measurement.items():
        entry["state_sha256"] = cv.digest(cv.encoded(measured[cid]))
    cv.write(partial / "measurement.json", measurement)
    cv.write(
        partial / "locations.json",
        {
            "source": str(source),
            "source_judge": str(source_judge),
            "references": str(refs) if refs else None,
            "capture": config["capture_root"],
        },
    )
    if refs:
        shutil.copyfile(refs, partial / "references.jsonl")
    plan = c.judge().build_plan(
        paths,
        {},
        retest=15,
        references_sha256=cv.sha(refs) if refs else None,
        withheld=refs is not None,
    )
    if args.key == "aircargo":
        # Ceiling public_export hashes the reading text: take the original pinned
        # stage-5 package provenance, not that sanitized attempt-02 export.
        plan["reading"] = cv.read(repo / cv.old_export(args.key))["provenance"]["reading"]
    cv.require(sum("retest_of" in i for i in plan["items"]) == 15, "M1 needs 15 eligible retests")
    cv.write(partial / "m1/plan.json", plan)
    (partial / "m1/verdicts.jsonl").touch()
    bridge = d.canonical_import(repo, "bridge_plan", "reports/answer-prompt-v4/tools")
    bridge.main([str(source_judge), str(partial / "bridge")])
    pin = {
        "key": args.key,
        "spec_sha256": registration["files"][d.SPEC],
        "registration_sha256": cv.digest(cv.encoded(registration)),
        "tools": registration["files"],
        "wrapper_sha256": cv.sha(repo / "llm/codex_wrapper.txt"),
        "public_inputs": dict(c.INPUT_PINS),
        "plans": {m: cv.sha(partial / m / "plan.json") for m in METRICS},
        "requests": {
            m: c.instruments().judge.counts(cv.read(partial / m / "plan.json"), m) for m in METRICS
        },
        "bridge_seed": c.instruments().common.protocol.prefix(partial / "bridge/verdicts.jsonl"),
        "source": source_pin,
        "old": {
            "m1": {
                "record_sha256": cv.sha(old_path),
                "cases_sha256": cv.sha(old_path.with_suffix(".cases.jsonl")),
            }
        },
        "references_sha256": cv.sha(refs) if refs else None,
        "answer_files": c.tree_hashes(partial / "runs"),
        "attempt_files": files,
        "capture_files": captures,
        "measurement_sha256": cv.sha(partial / "measurement.json"),
        "locations_sha256": cv.sha(partial / "locations.json"),
        "source_inputs": {
            f"{label}/{f['path']}": f["sha256"]
            for label in paths
            for f in cv.tree_files(source / label)
        },
        "cases": measurement,
    }
    c.public(partial / "receipt.json", pin)
    c.public(receipt, pin)
    validate_frozen(args.key, partial, pin, series, registration, repo)
    partial.rename(work)
    return pin


def admitted(args, repo=d.ROOT):
    config, registration = d.admit_chunk(
        SimpleNamespace(**{**vars(args), "budget": 600}), repo, offline=True
    )
    series, records = args.private / args.series, args.records / args.series
    receipt = records / f"plans-{args.key}.json"
    pin = cv.decode(d.committed_bytes(repo, receipt))
    work = series / args.key
    cv.require(cv.sha(work / "receipt.json") == cv.sha(receipt), "private/public receipt differs")
    validate_frozen(args.key, work, pin, series, registration, repo)
    return config, registration, pin


def exports(key, series, pin, metric, repo=d.ROOT):
    c, historical = modules(repo)
    work, name = series / key, f"codex-only-{key}-judge-{metric}"
    target = work / "export-cache"
    target.mkdir(exist_ok=True)
    v6 = c.instruments()
    if metric == "bridge":
        result = v6.legacy.bridge_export(
            work / metric, {"inputs": {"v4": pin["source"]}}, target / (name + ".json")
        )
        data = None
    else:
        plan = cv.read(work / metric / "plan.json")
        result = v6.common.final.frozen("export").export(
            work / metric,
            name,
            target,
            {label: work / "runs" / label for label in plan["runs"]},
            work / "references.jsonl" if key in cv.KEYS[:2] else None,
        )
        data = cv.rows(target / (name + ".cases.jsonl"))
    if (work / metric / "NOT_EVIDENCE.json").exists():
        result.update(status="NOT_EVIDENCE", request_duration_stop=True)
    result = historical.public_export(result)
    if data is not None:
        c.public_guard(data)
    return result, data


def export(args, repo=d.ROOT):
    _, _, pin = admitted(args, repo)
    c, _ = modules(repo)
    for metric in METRICS:
        result, data = exports(args.key, args.private / args.series, pin, metric, repo)
        path = args.records / args.series / f"codex-only-{args.key}-judge-{metric}.json"
        c.public(path, result)
        if data is not None:
            c.public_rows(path.with_suffix(".cases.jsonl"), data)


def judge_route(config, series, records, repo, *, sender=None):
    c, _ = modules(repo)
    judge = c.judge()
    check_instructions(judge)
    executable = os.environ.get("RAG_JUDGE_CLAUDE_CLI", "").strip() or judge.isolated.find_cli()
    cv.require(executable is not None, "judge CLI missing")
    path = Path(str(executable)).resolve()
    cv.require(
        path == Path(config["artifacts"]["claude_executable"]).resolve(), "judge executable differs"
    )
    digest = cv.sha(path)
    private, public = series / "judge-route.json", records / "judge-route.json"
    if private.exists():
        return saved_route(series, records, digest, judge)["passed"] is True
    held = {
        "passed": False,
        "executable_sha256": digest,
        "executable": str(path),
        "route": judge.isolated.settings(judge.SYSTEM_PROMPT),
    }
    try:
        # The supplied historical tools expose their route validator, but no
        # separate probe entry point. Exercise the exact sender and verdict parser
        # on synthetic data; an OK reply would violate this route's JSON-only system.
        message = judge.build_message(
            "What colour is the synthetic marker?",
            [("synthetic", "The synthetic marker is blue.")],
            "The synthetic marker is blue [1].",
            None,
        )
        held["message_sha256"] = cv.digest(message)
        reply = (sender or judge._isolated_sender(judge.CLI_TIMEOUT_S))(
            judge.SYSTEM_PROMPT, message
        )
        held.update(session=reply.session)
        if isinstance(reply.session, dict):
            held["version"] = reply.session.get("cli_version")
        judge.isolated.check_record(reply.session)
        cv.require(
            reply.model == judge.isolated.MODEL and reply.session["model"] == judge.isolated.MODEL,
            "judge probe refused",
        )
        judge._read({"marks_listed": 1, "has_reference": False}, reply.text)
        held["passed"] = True
    except (Exception, SystemExit) as error:
        held.update(reason=type(error).__name__)
    cv.write(private, held)
    c.public(public, route_public(held, private))
    return held["passed"] is True


def saved_route(series, records, digest, judge):
    """Offline route receipt admission; cannot send a probe when the receipt is absent."""
    private = series / "judge-route.json"
    held = cv.read(private)
    cv.require(held["executable_sha256"] == digest, "judge executable changed after probe")
    cv.require(
        held["route"] == judge.isolated.settings(judge.SYSTEM_PROMPT)
        and cv.read(records / "judge-route.json") == route_public(held, private),
        "judge route receipt differs",
    )
    if held["passed"] is True:
        judge.isolated.check_record(held["session"])
        cv.require(
            held["version"] == held["session"]["cli_version"]
            and held["session"]["model"] == judge.isolated.MODEL,
            "judge route session differs",
        )
    return held


def route_public(held, private):
    return {
        "passed": held["passed"],
        "executable_sha256": held["executable_sha256"],
        "version_sha256": cv.digest(held["version"]) if held.get("version") else None,
        "receipt_sha256": cv.sha(private),
    }


class Proxy:
    def __init__(self, original, **overrides):
        self.original, self.overrides = original, overrides

    def __getattr__(self, name):
        return self.overrides[name] if name in self.overrides else getattr(self.original, name)


@contextlib.contextmanager
def ceiling_adapter(historical, common, pin, series, repo):
    """Serial scoped bindings reuse the historical grade loop without copying it.

    Only this module's reference to common/admission/export is rebound; imported
    instruments are untouched. Always restore, including exception/budget exits.
    """
    original = historical.c, historical.admitted, historical.exports
    instruments = common.instruments()

    def retry(folder):
        held = instruments.key.retry_state(folder)
        cv.write(folder / "retry.json", held)  # Persist journal/crash reconciliation too.
        return held

    facade = Proxy(instruments, key=Proxy(instruments.key, retry_state=retry))

    def read(path):
        value = cv.read(Path(path))
        if Path(path) == series / "state.json":
            value["stops"] = active_stops(value)
        return value

    historical.c = Proxy(common, metrics=lambda key: METRICS, read=read, instruments=lambda: facade)
    historical.admitted = lambda *args: pin
    historical.exports = lambda key, series, pin, metric: exports(key, series, pin, metric, repo)
    try:
        yield
    finally:
        historical.c, historical.admitted, historical.exports = original


def grade(
    args, repo=d.ROOT, *, sender=None, probe_sender=None, clock=time.monotonic, now=time.time
):
    cv.require(type(args.budget) is int and 0 < args.budget <= 600, "grade budget must be 1..600")
    started = clock()
    config, registration, pin = admitted(args, repo)
    c, historical = modules(repo)
    judge = c.judge()
    check_instructions(judge)
    series, records = args.private / args.series, args.records / args.series
    state = cv.read(series / "state.json")
    cv.require(
        state["registration_sha256"] == cv.digest(cv.encoded(registration)),
        "state registration differs",
    )
    if active_stops(state) or c.judge_stops(series):
        return (
            2 if c.judge_stops(series) or any(s["code"] == 2 for s in active_stops(state)) else 5
        ), "arm or judge stopped"
    bind_state(args.key, state, cv.read(series / args.key / "measurement.json"))
    for metric in METRICS:
        check_instructions(judge)
        judge.check_plan(cv.read(series / args.key / metric / "plan.json"))
    if clock() - started >= args.budget:
        return 3, "foreground budget reached"
    try:
        if not judge_route(config, series, records, repo, sender=probe_sender):
            return 5, "judge route refused; no grades requested"
    except (Exception, SystemExit):
        return 5, "judge route admission unavailable"
    remaining = args.budget - (clock() - started)
    if remaining <= 0:
        return 3, "foreground budget reached"
    with ceiling_adapter(historical, c, pin, series, repo):
        return historical.grade(
            args.key, series, records, repo / d.SPEC, remaining, sender=sender, clock=clock, now=now
        )


def execute(args, repo=d.ROOT):
    c, _ = modules(repo)
    # As the request modes: path checks first, then the same per-series lock,
    # so a freeze/grade/export never runs beside a request chunk of its series.
    cv.require(re.fullmatch(r"[A-Za-z0-9_-]+", args.series), "invalid series")
    cv.require(
        args.private.is_absolute()
        and not args.private.resolve().is_relative_to(repo.resolve())
        and not repo.resolve().is_relative_to(args.private.resolve()),
        "private root overlaps repository",
    )
    with (
        c.serial_lock(args.private / args.series),
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        if args.command == "freeze":
            pin = freeze(args, repo)
            code, message = (
                0,
                f"frozen; commit plans-{args.key}.json; requests={sum(pin['requests'].values())}",
            )
        elif args.command == "grade":
            code, message = grade(args, repo)
        else:
            export(args, repo)
            code, message = 0, "public exports written"
    print(f"{code} {message}")
    return code

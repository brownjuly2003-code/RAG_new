"""Amendment 1 of docs/specs/encoder-checkers.md, registered before B's first call and before
V5's first aircargo answer: Horizon guard base as a fourth checker B (Part 1), then the four
checkers' frozen thresholds read once on V5's fresh aircargo answers (Part 2).

  python reports/encoder-checkers/tools/encoder_checkers_amend.py parity OUT
  python reports/encoder-checkers/tools/encoder_checkers_amend.py score OUT
  python reports/encoder-checkers/tools/encoder_checkers_amend.py base OUT
  python reports/encoder-checkers/tools/encoder_checkers_amend.py fresh CHECKER OUT
  python reports/encoder-checkers/tools/encoder_checkers_amend.py confirm OUT PLAN_JSON

The registered tool, encoder_checkers.py, is loaded unchanged (its SHA-256 is checked) and keeps
its rules, inputs, scorers and score loop; this one adds B, scored by H's scorer, and Part 2.
``parity``, ``score`` and ``fresh`` run on the Mac in the gate checkout, as the registered tool's
do: ``parity`` checks B's PyTorch path against its authors' ONNX export (OUT/parity-B.json),
``score`` runs the registered score loop for B (OUT/scores-B.jsonl), ``fresh`` scores V5's
aircargo answers with one checker (OUT/fresh-CHECKER.jsonl). ``base`` writes Part 1's record
(OUT/record.json: B's numbers and the outcome over the four, H's, L's and N's from their committed
rows); ``confirm`` writes Part 2's (OUT/record.json), the thresholds read from the two committed
records, each scored answer tied to its judged request through V5's aircargo judge plan
(PLAN_JSON, in the laptop's private folder; the judge record names it by SHA-256). Rows hold ids,
labels, scores, counts, seconds and SHA-256s, never a text.
"""

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
REGISTERED = HERE / "encoder_checkers.py"
# The registered tool of fa73683, the one the record of 4f48fed names.
REGISTERED_SHA256 = "fa226d384f7dc0e997be0e69ba3cd1de5c9312770fae64d155fcd32380a2a49e"


def _registered():
    """The registered tool, under a name of its own: B is added to this copy only."""
    spec = importlib.util.spec_from_file_location("encoder_checkers_registered", REGISTERED)
    module = importlib.util.module_from_spec(spec)
    sys.modules["encoder_checkers_registered"] = module
    spec.loader.exec_module(module)
    return module


ec = _registered()
B = {
    "repo": "Horizon-Labs/hallucination-guard-base",
    "revision": "f0aaaac7c39073b4528191261e874d9664f14254",
    "forecast_min": 200,
}
ec.CHECKERS["B"] = B
ec.SCORERS["B"] = ec.score_h
FOUR = ("H", "L", "N", "B")
FIRST = WS / "reports/encoder-checkers/4f48fed"
BASE = WS / "reports/encoder-checkers/4f48fed-base"
V5_RUNS = Path("/Users/julia/RAG_new_chat_4f48fed/v5/runs")
V5_DIR = WS / "reports/answer-prompt-v5/4f48fed"
V5_JUDGE = V5_DIR / "v5-aircargo-judge"
V5_SUMMARY = V5_DIR / "v5-aircargo"
FRESH_FORECAST_MIN = {"H": 25, "L": 15, "N": 50, "B": 80}
FRESH_PLANNED = 100
FRESH_MIN_TARGET, FRESH_MIN_GOOD = 10, 30
# What H's start rows of 4f48fed hold and B's must repeat: the same answers in the same order.
SAME_ANSWERS = ("inputs", "inputs_sha256", "planned", "rushallu_commit")


def check_registered():
    if ec.sha256(REGISTERED) != REGISTERED_SHA256:
        raise SystemExit(f"{REGISTERED.name}: not the registered tool")


def tools():
    return {
        "registered_sha256": ec.sha256(REGISTERED),
        "amendment_sha256": ec.sha256(Path(__file__)),
    }


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


# --- Part 1: B -------------------------------------------------------------------------------


def weights_b():
    return ec.snapshot("B") / "model.safetensors"


def parity(out):
    """B's PyTorch path against its authors' ONNX export on the registered tool's 12 pairs."""
    import numpy
    import onnxruntime

    check_registered()
    out.mkdir(parents=True, exist_ok=True)
    stored = json.loads((ec.snapshot("B") / "config.json").read_text(encoding="utf-8"))
    if stored["model_type"] != "modernbert":
        raise SystemExit("B: not a ModernBERT config, whose rope bases the registered load checks")
    tokenizer, model = ec.load("B")  # raises when the loaded config is not the file's
    onnx = ec.snapshot("B") / "onnx" / "model.onnx"
    session = onnxruntime.InferenceSession(str(onnx), providers=["CPUExecutionProvider"])
    names = {node.name for node in session.get_inputs()}
    worst, same, lengths = 0.0, True, []
    for source, claim in ec.parity_pairs():
        enc = tokenizer(source, claim, truncation=True, max_length=ec.H_MAX, return_tensors="pt")
        lengths.append(int(enc["input_ids"].shape[1]))
        torch_probs = ec._probs(model, enc["input_ids"], enc["attention_mask"])[0].numpy()
        feed = {key: enc[key].numpy().astype(numpy.int64) for key in enc if key in names}
        logits = session.run(None, feed)[0][0].astype(numpy.float64)
        onnx_probs = numpy.exp(logits - logits.max())
        onnx_probs /= onnx_probs.sum()
        worst = max(worst, float(numpy.abs(torch_probs - onnx_probs).max()))
        same = same and int(torch_probs.argmax()) == int(onnx_probs.argmax())
    passed = worst <= ec.PARITY_TOLERANCE and same
    found = {
        "pairs": len(lengths),
        "onnxruntime": onnxruntime.__version__,
        "B": {
            "weights_sha256": ec.sha256(weights_b()),
            "onnx_sha256": ec.sha256(onnx),
            "max_abs_difference": worst,
            "same_top_label": same,
            "tokens": [min(lengths), max(lengths)],
            "config_matches_file": True,
            "passed": passed,
        },
        "passed": passed,
        **tools(),
        "measured_at_head": ec.git_head(),
    }
    (out / "parity-B.json").write_text(json.dumps(found, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(found, indent=1))
    if not passed:
        raise SystemExit("B's loading check failed: the PyTorch path is not the authors' export")


def score(out):
    """The registered score loop for B; each segment after a row naming this amendment."""
    check_registered()
    path = out / "scores-B.jsonl"
    if any(row["kind"] == "end" and row["stopped"] for row in ec.load_jsonl(path)):
        raise SystemExit(f"{path} stopped by the rule; it is not resumed")
    if not (out / "parity-B.json").is_file():
        raise SystemExit("B's loading check has not run")
    checked = json.loads((out / "parity-B.json").read_text(encoding="utf-8"))
    if not checked["passed"]:
        raise SystemExit("B's loading check has not passed")
    if not weights_b().is_file() or ec.sha256(weights_b()) != checked["B"]["weights_sha256"]:
        raise SystemExit("B's weights are not the ones its loading check read")
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({"kind": "amendment", **tools(), "at": ec.now()}) + "\n")
    ec.score("B", out)


def segments(rows):
    """B's segments: each start right after a row naming the amendment; amendment rows a broken
    launch left before any start are counted apart."""
    amendments, orphans = [], 0
    for index, row in enumerate(rows):
        if row["kind"] == "start":
            if index == 0 or rows[index - 1]["kind"] != "amendment":
                raise SystemExit("scores-B.jsonl: a segment not run by this amendment")
            amendments.append(rows[index - 1]["amendment_sha256"])
        elif row["kind"] == "amendment" and (
            index + 1 == len(rows) or rows[index + 1]["kind"] != "start"
        ):
            orphans += 1
    return amendments, orphans


def base(out):
    """Part 1's record: B's numbers by the registered rules, and the outcome over the four."""
    check_registered()
    rows = ec.load_jsonl(out / "scores-B.jsonl")
    amendments, orphans = segments(rows)
    starts = [row for row in rows if row["kind"] == "start"]
    if not starts:
        raise SystemExit("scores-B.jsonl: no segment")
    if any(row["tool_sha256"] != REGISTERED_SHA256 for row in starts):
        raise SystemExit("scores-B.jsonl: scored by another tool than the registered")
    held = next(row for row in ec.load_jsonl(FIRST / "scores-H.jsonl") if row["kind"] == "start")
    for key in SAME_ANSWERS:
        if any(row[key] != held[key] for row in starts):
            raise SystemExit(f"scores-B.jsonl: not H's answers, its {key} differs")
    first = json.loads((FIRST / "record.json").read_text(encoding="utf-8"))
    per_checker = {}
    for name in ("H", "L", "N"):
        per_checker[name] = ec.checker_record(ec.load_jsonl(FIRST / f"scores-{name}.jsonl"))
        if json.loads(json.dumps(per_checker[name])) != first["checkers"][name]:
            raise SystemExit(f"{name}: its committed rows are not its record's")
    per_checker["B"] = ec.checker_record(rows)
    result = {
        "spec": ec.SPEC,
        "amendment": 1,
        "part": 1,
        **tools(),
        "amendments": amendments,
        "orphan_amendment_rows": orphans,
        "parity": json.loads((out / "parity-B.json").read_text(encoding="utf-8")),
        "checkers": {"B": per_checker["B"]},
        **ec.outcome(per_checker),
        # Part 1 proposes nothing alone: a checker goes to Julia only through Part 2.
        "proposes": False,
    }
    write(out / "record.json", result)
    print(result["decision"])
    return result


# --- Part 2: fresh answers --------------------------------------------------------------------


def v5_answers(runs=V5_RUNS):
    """Every answer of V5's aircargo runs, by (run, case), with its documents and digests."""
    found = {}
    for run in sorted(Path(runs).glob("v5-aircargo-b??")):
        if not run.is_dir():
            continue
        for answer in ec.judge.run_answers(run):
            key = (run.name, answer["case_id"])
            if key in found:
                raise SystemExit(f"{key}: two answers")
            found[key] = answer
    return found


def readable():
    """Why Part 2 cannot read V5's aircargo answers, or None: none whole, or a plan not counted."""
    summary, judged = Path(f"{V5_SUMMARY}.json"), Path(f"{V5_JUDGE}.json")
    if not summary.is_file():
        return "no V5 aircargo answers"
    if not json.loads(summary.read_text(encoding="utf-8"))["whole"]:
        return "V5's aircargo answers are not whole"
    if not judged.is_file():
        return "no V5 aircargo judge record"
    if json.loads(judged.read_text(encoding="utf-8"))["status"] != "counted":
        return "V5's aircargo judge plan is not counted"
    return None


def fresh_class(row):
    """The rule above on V5's judge rows: an empty answer is bad, a missing verdict unclassed."""
    if row.get("empty_answer"):
        return "target"
    if row["missing"]:
        return None
    return ec.judge_class(row)


def fresh_inputs(found=None):
    """V5's aircargo answers in the replay summary's order, each with V5's judge's class and the
    SHA-256 of the request the judge was sent for it."""
    summary = ec.load_jsonl(Path(f"{V5_SUMMARY}.cases.jsonl"))
    rows = ec.load_jsonl(Path(f"{V5_JUDGE}.cases.jsonl"))
    judged = {row["case_id"]: row for row in rows}
    found = v5_answers() if found is None else found
    if (
        len(summary) != FRESH_PLANNED
        or len(judged) != len(rows)
        or len(judged) != len(summary)
        or len(found) != len(summary)
    ):
        raise SystemExit("V5's aircargo answers, its judge and the replay summary differ in size")
    out = []
    for entry in summary:
        key = (entry["run"], entry["case_id"])
        answer, row = found.get(key), judged.get(entry["case_id"])
        if answer is None or row is None:
            raise SystemExit(f"{key}: no answer, or no judge row")
        if not answer["prompt_sha256"] == row["prompt_sha256"] == entry["v5_prompt_sha256"]:
            raise SystemExit(f"{key}: the judge graded another prompt than the replay's")
        if bool(row.get("empty_answer")) != (not answer["answer"]):
            raise SystemExit(f"{key}: the judge's empty answer is not the run's")
        texts = [body for _, body in answer["documents"]]
        item = ec.item("fresh", "aircargo", key, fresh_class(row), answer["answer"], texts)
        item["item_id"] = row["item_id"]
        item["verdict_missing"] = bool(row["missing"])
        item["answer_sha256"] = ec.digest(answer["answer"])
        item["message_sha256"] = (
            ec.digest(
                ec.judge.build_message(
                    answer["question"], answer["documents"], answer["answer"], None
                )
            )
            if answer["answer"]
            else None
        )
        out.append(item)
    return out


def fresh_hashes():
    return {
        "judge": ec.sha256(Path(f"{V5_JUDGE}.cases.jsonl")),
        "judge record": ec.sha256(Path(f"{V5_JUDGE}.json")),
        "summary": ec.sha256(Path(f"{V5_SUMMARY}.cases.jsonl")),
        "summary record": ec.sha256(Path(f"{V5_SUMMARY}.json")),
        "first record": ec.sha256(FIRST / "record.json"),
        "base record": ec.sha256(BASE / "record.json"),
    }


def versions():
    import torch
    import transformers

    return {"torch": torch.__version__, "transformers": transformers.__version__}


def fresh(name, out):
    """Score V5's aircargo answers with one checker; stop at three times its forecast; resume."""
    check_registered()
    why = readable()
    if why:
        raise SystemExit(f"Part 2 is {ec.NOT_EVIDENCE}: {why}; nothing to score")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"fresh-{name}.jsonl"
    rows = ec.load_jsonl(path)
    done = {row["id"] for row in rows if row["kind"] == "answer"}
    spent = sum(row["seconds"] for row in rows if row["kind"] == "answer")
    if any(row["kind"] == "end" and row["stopped"] for row in rows):
        raise SystemExit(f"{path} stopped by the rule; it is not resumed")
    todo = fresh_inputs()
    spec = ec.CHECKERS[name]
    start = {
        "kind": "start",
        "checker": name,
        "repo": spec["repo"],
        "revision": spec["revision"],
        "forecast_min": FRESH_FORECAST_MIN[name],
        "weights_sha256": ec.sha256(ec.snapshot(name) / "model.safetensors"),
        "spec": ec.SPEC,
        **tools(),
        "measured_at_head": ec.git_head(),
        "inputs": fresh_hashes(),
        "inputs_sha256": ec.digest(json.dumps(todo, ensure_ascii=False, sort_keys=True)),
        "planned": len(todo),
        "resumed_after": len(done),
        **versions(),
        "threads": ec.THREADS,
        "load": list(os.getloadavg()),
        "at": ec.now(),
    }
    tokenizer, model = ec.load(name)
    scorer = ec.SCORERS[name]
    stopped = False
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(start, ensure_ascii=False) + "\n")
        for entry in todo:
            if entry["id"] in done:
                continue
            if spent > ec.STOP_FACTOR * 60 * FRESH_FORECAST_MIN[name]:
                stopped = True
                break
            began = time.perf_counter()
            if entry["documents"]:
                value, units, tokens, cut = scorer(
                    tokenizer, model, entry["documents"], entry["answer"]
                )
            else:
                value, units, tokens, cut = None, 0, 0, 0
            seconds = time.perf_counter() - began
            spent += seconds
            row = {
                "kind": "answer",
                "set": entry["set"],
                "base": entry["base"],
                "id": entry["id"],
                "class": entry["class"],
                "item_id": entry["item_id"],
                "verdict_missing": entry["verdict_missing"],
                "answer_sha256": entry["answer_sha256"],
                "message_sha256": entry["message_sha256"],
                "score": value,
                "sentences": len(ec.sentences(entry["answer"])),
                "units": units,
                "tokens": tokens,
                "truncated": cut,
                "seconds": round(seconds, 3),
            }
            handle.write(json.dumps(row) + "\n")
            handle.flush()
        handle.write(
            json.dumps(
                {
                    "kind": "end",
                    "stopped": stopped,
                    "seconds_spent": round(spent, 1),
                    "peak_rss_bytes": ec.peak_rss(),
                    "load": list(os.getloadavg()),
                    "at": ec.now(),
                }
            )
            + "\n"
        )
    print(path, "stopped" if stopped else "whole", round(spent / 60, 1), "min")


def frozen():
    """Each checker's threshold and its read on V4's 80, as the two committed records hold them."""
    first = json.loads((FIRST / "record.json").read_text(encoding="utf-8"))
    second = json.loads((BASE / "record.json").read_text(encoding="utf-8"))
    entries = {**first["checkers"], **second["checkers"]}
    return {
        name: {"threshold": entries[name]["threshold"]["threshold"], "v4": entries[name]["reading"]}
        for name in FOUR
    }


def fresh_record(rows, cut):
    """One checker's fresh read: the frozen reading on V5's classed answers, and beside it."""
    starts = [row for row in rows if row["kind"] == "start"]
    answers = [row for row in rows if row["kind"] == "answer"]
    ends = [row for row in rows if row["kind"] == "end"]
    for key in ("amendment_sha256", "weights_sha256", "inputs_sha256", "planned", "revision"):
        if any(row[key] != starts[0][key] for row in starts):
            raise SystemExit(f"{starts[0]['checker']}: a resumed segment differs in {key}")
    entry = ec.counts(answers, cut)
    short = []
    if len(answers) != starts[0]["planned"]:
        short.append("the checker did not reach every answer")
    if entry["target"] < FRESH_MIN_TARGET or entry["good_not_declining"] < FRESH_MIN_GOOD:
        short.append(f"fewer than {FRESH_MIN_TARGET} targets or {FRESH_MIN_GOOD} good")
    return {
        "threshold": cut,
        "reached": len(answers),
        "segments": len(starts),
        "stopped": any(row["stopped"] for row in ends),
        "reading": ec.NOT_EVIDENCE if short else ec.reading(answers, cut),
        "counts": entry,
        "not_evidence_because": short,
        "unclassed": sum(1 for row in answers if row["class"] is None),
        "verdict_missing": sum(1 for row in answers if row["verdict_missing"]),
        "auroc": ec.auroc(answers),
        "seconds": ec.spread([row["seconds"] for row in answers]),
        "seconds_total": sum(row["seconds"] for row in answers),
        "truncated": sum(row["truncated"] for row in answers),
        "unscored": sum(1 for row in answers if row["score"] is None),
        "peak_rss_bytes": max((row["peak_rss_bytes"] for row in ends), default=None),
        "load": [row["load"] for row in rows if row["kind"] in ("start", "end")],
    }


def v4_counts(before):
    """A V4 read lets a fresh *worth wiring* stand when it is neither useless nor NOT_EVIDENCE."""
    return before != ec.NOT_EVIDENCE and before["reading"] != "useless"


def confirm_outcome(per_checker, v4):
    """Worth wiring on the fresh read and a V4 read that counts - the best; else the fresh rule,
    a fresh *worth wiring* over a V4 read that does not count held back as in between."""
    worth = [
        name
        for name, entry in per_checker.items()
        if entry["reading"] != ec.NOT_EVIDENCE and entry["reading"]["reading"] == "worth wiring"
    ]
    eligible = [name for name in worth if v4_counts(v4[name])]
    held = {"held_back": [name for name in worth if name not in eligible]}
    if eligible:
        best = min(
            eligible,
            key=lambda name: (
                -per_checker[name]["reading"]["caught"],
                per_checker[name]["reading"]["over_marked"],
                per_checker[name]["seconds"]["median"],
            ),
        )
        return {"decision": f"worth wiring: {best}", "worth_wiring": best, **held}
    missing = [name for name, entry in per_checker.items() if entry["reading"] == ec.NOT_EVIDENCE]
    if missing:
        decision = f"{ec.NOT_EVIDENCE}: {', '.join(missing)}"
        return {"decision": decision, "worth_wiring": None, **held}
    between = [
        name
        for name, entry in per_checker.items()
        if entry["reading"]["reading"] in ("in between", "worth wiring")
    ]
    if between:
        return {"decision": f"in between: {', '.join(between)}", "worth_wiring": None, **held}
    return {"decision": "none worth wiring", "worth_wiring": None, **held}


def linked(rows_by_name, plan_path):
    """Each scored answer is the request the judge was sent: its message SHA-256 the plan's, the
    plan the one V5's aircargo judge record names."""
    record = json.loads(Path(f"{V5_JUDGE}.json").read_text(encoding="utf-8"))
    if ec.sha256(plan_path) != record["provenance"]["plan_sha256"]:
        raise SystemExit(f"{plan_path}: not the plan V5's aircargo judge record names")
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    sent = {item["item_id"]: item for item in plan["items"] if "retest_of" not in item}
    for name, rows in rows_by_name.items():
        for row in rows:
            if row["kind"] != "answer":
                continue
            item = sent.get(row["item_id"])
            if item is None or f"{item['run']}/{item['case_id']}" != row["id"]:
                raise SystemExit(f"{name}: {row['id']} is not a request of the plan")
            if item.get("message_sha256") != row["message_sha256"] or bool(
                item.get("empty_answer")
            ) != (row["message_sha256"] is None):
                raise SystemExit(f"{name}: {row['id']} scored another answer than the judged")
    return True


def confirm(out, plan_path):
    """Part 2's record from the four fresh files and the two committed records."""
    check_registered()
    base_part = {"spec": ec.SPEC, "amendment": 1, "part": 2, **tools()}
    why = readable()
    if why:
        result = {
            **base_part,
            "not_evidence_because": [why],
            "decision": f"{ec.NOT_EVIDENCE}: {why}",
            "worth_wiring": None,
        }
        write(out / "record.json", result)
        print(result["decision"])
        return result
    held, inputs = frozen(), fresh_hashes()
    rows_by_name, per_checker = {}, {}
    for name in FOUR:
        rows = ec.load_jsonl(out / f"fresh-{name}.jsonl")
        starts = [row for row in rows if row["kind"] == "start"]
        if not starts:
            raise SystemExit(f"no fresh scores of {name}")
        for row in starts:
            if row["checker"] != name or row["registered_sha256"] != REGISTERED_SHA256:
                raise SystemExit(f"fresh-{name}.jsonl: another checker or tool")
            if row["inputs"] != inputs:
                raise SystemExit(f"fresh-{name}.jsonl: scored on other inputs than the records")
        rows_by_name[name] = rows
        per_checker[name] = fresh_record(rows, held[name]["threshold"])
    if len({rows[0]["inputs_sha256"] for rows in rows_by_name.values()}) != 1:
        raise SystemExit("the four checkers scored different answers")
    result = {
        **base_part,
        "inputs": inputs,
        "plan_linked": linked(rows_by_name, plan_path),
        "v4_reading": {name: held[name]["v4"] for name in FOUR},
        "checkers": per_checker,
        **confirm_outcome(per_checker, {name: held[name]["v4"] for name in FOUR}),
    }
    write(out / "record.json", result)
    print(result["decision"])
    return result


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    command, rest = (argv[0], argv[1:]) if argv else (None, [])
    if command in ("parity", "score") and len(rest) == 1:
        sys.path.insert(0, ec.SITE)
        (parity if command == "parity" else score)(Path(rest[0]))
    elif command == "fresh" and len(rest) == 2 and rest[0] in FOUR:
        sys.path.insert(0, ec.SITE)
        fresh(rest[0], Path(rest[1]))
    elif command == "base" and len(rest) == 1:
        base(Path(rest[0]))
    elif command == "confirm" and len(rest) == 2:
        confirm(Path(rest[0]), Path(rest[1]))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()

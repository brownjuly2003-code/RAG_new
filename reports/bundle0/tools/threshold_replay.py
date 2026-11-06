"""Bundle 0: registered offline filtering of stage 7's H_new; no model calls."""

import argparse
import importlib.util
import json
import math
import statistics
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[3]
SPEC = "docs/specs/bundle0-reranker-threshold.md"
STAGE7 = WS / "reports/stage7/5e308fe"
FROZEN = {
    "reports/stage7/tools/arms_replay.py": "6ca8b723841d08dfd6f5d084bdc0883264c889eb495dc4d3728ac0a2ea623689",
    "reports/stage7/5e308fe/record.json": "b9db1434a6091536540112591e29cb3f02f373660dd06469e6abebc3780b55e4",
    "reports/stage7/5e308fe/int8_scores.jsonl": "5c4d2bbcc42fe17afb516c877fdeacf7bc3bd05beb8557870b7d1f7bedb156a6",
    "reports/stage7/5e308fe/rows.jsonl": "2d87859ecfd5e2442eefadcc5dafb471e5a80d13d8227907d59e568010109627",
}
THRESHOLDS = {f"T{i:02d}": i / 20 for i in range(21)}
ARMS = (*THRESHOLDS, "A", "G")
TEXT_FIELDS = {
    "text",
    "page_content",
    "content",
    "question",
    "query",
    "source",
    "sources",
    "answer",
    "response",
    "reason",
    "prompt_text",
    "raw_response",
    "raw_verdict",
}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ar = load_module("bundle0_arms_replay", WS / "reports/stage7/tools/arms_replay.py")
from stage2_common import without_text  # noqa: E402


class ParityError(ValueError):
    """H changed: no arm's result may be published."""


def validate_scores(scores):
    if any(type(s) not in (float, int) or not math.isfinite(s) or not 0 <= s <= 1 for s in scores):
        raise ValueError("scores must be finite sigmoid values in [0, 1]")


def threshold_keep(scores, threshold):
    validate_scores(scores)
    validate_scores([threshold])
    return [i for i, score in enumerate(scores) if score >= threshold]


def shape_keep(scores):
    """Largest adjacent gap, longest prefix on a tie; a flat vector keeps everything."""
    validate_scores(scores)
    if len(scores) < 2:
        return list(range(len(scores)))
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    gap, cut = max((scores[order[i - 1]] - scores[order[i]], i) for i in range(1, len(order)))
    chosen = set(order[:cut] if gap > 0 else order)
    return [i for i in range(len(scores)) if i in chosen]


def parity_gate(actual, expected):
    for field in ("label", "base", "case_id", "index", "gold", "H"):
        if actual.get(field) != expected.get(field):
            raise ParityError("H parity failed: " + field)


def prepare_control(inputs, record, scored, machine, builder):
    try:
        _, h = ar.new_h(inputs, record, scored, machine, builder)
    except SystemExit as error:
        raise ParityError("H did not reproduce the scored pool/five") from error
    case = inputs["cases"].get(record["case_id"])
    row = {
        "label": inputs["label"],
        "base": inputs["base"],
        "case_id": record["case_id"],
        "index": record["index"],
        "gold": case is not None,
        "H": ar.arm_entry("H", h["docs"], h["flat"], h["sent"], inputs, builder, case),
    }
    return row, h


def control_row(inputs, record, scored, machine, builder):
    return prepare_control(inputs, record, scored, machine, builder)[0]


def grade_keep(response, count):
    from agent.graph import _parse_doc_grade_batch_text

    grades = _parse_doc_grade_batch_text(response, count)
    return [] if grades is None else [i for i, (keep, _) in enumerate(grades) if keep]


def read_capture(root):
    """Read-only Codex capture. Missing default capture is explicitly unavailable."""
    if not root.exists():
        return [], None
    journal = load_module(
        "bundle0_capture_journal", WS / "reports/codex-only-quality/tools/capture_journal.py"
    )
    calls = journal.read_journal(root)
    fingerprints = []
    for call in calls:
        # Bind via the capture's own validator before any use of the output.
        try:
            active = json.loads(call.start["active_case"])
        except (KeyError, TypeError, ValueError) as error:
            raise SystemExit("unbound grader capture") from error
        if journal.bind_calls([call], active) or call.errors or call.driver_errors:
            raise SystemExit("invalid grader capture")
        fingerprints.append(
            {
                "id": call.folder.name,
                "files": {
                    p.name: ar.sha256(p) for p in sorted(call.folder.iterdir()) if p.is_file()
                },
            }
        )
    return calls, ar.digest(json.dumps(fingerprints, sort_keys=True))


def recorded_grade(calls, base, case_id, question, docs):
    """Only a complete, uniquely matched batch over exactly these documents is comparable."""
    from agent.prompts import build_doc_grade_batch_prompt

    prompt = build_doc_grade_batch_prompt(
        question, [{"page_content": d.page_content, "metadata": d.metadata} for d in docs]
    ).strip()
    matched = []
    for call in calls:
        active = json.loads(call.start["active_case"])
        if (active["key"], active["case_id"]) == (base, case_id) and call.prompt == prompt:
            matched.append(call)
    if not matched:
        return None, "unmatched"
    if len(matched) != 1:
        return None, "ambiguous"
    call = matched[0]
    if (
        call.errors
        or call.stop_reasons
        or call.driver_errors
        or call.spawned is None
        or call.end is None
        or call.end.get("exit_code") != 0
        or call.end.get("capture_ok") is not True
        or not call.output.accepted
    ):
        return None, "incomplete"
    return grade_keep(call.output.text, len(docs)), "matched"


def evaluate_question(inputs, record, scored, machine, builder, expected, calls):
    row, h = prepare_control(inputs, record, scored, machine, builder)
    parity_gate(row, expected)
    five = [d.metadata["chunk_index"] for d in h["docs"]]
    by_seed = dict(zip(scored["pool"], scored["scores"], strict=True))
    scores = [by_seed[seed] for seed in five]
    selections = {name: threshold_keep(scores, t) for name, t in THRESHOLDS.items()}
    selections["A"] = shape_keep(scores)
    selections["G"], row["grader_status"] = recorded_grade(
        calls, inputs["base"], record["case_id"], record["question"], h["docs"]
    )
    row["five"], row["scores"] = five, scores
    for arm, kept in selections.items():
        if kept is None:
            row[arm] = None
            continue
        # Filter the already expanded H documents, as grade_docs does; never expand anew.
        docs = [h["docs"][i] for i in kept]
        flat, sent = builder("v4", record["question"], docs)
        row[arm] = {
            **ar.arm_entry(
                arm, docs, flat, sent, inputs, builder, inputs["cases"].get(record["case_id"])
            ),
            "kept_indices": kept,
            "changed": flat != h["flat"],
        }
        if row[arm]["unresolved"] is not None or row[arm].get("excerpt_pieces_missed", 0):
            raise SystemExit("unresolved arm: NOT_EVIDENCE")
    return row


def usage(rows, arm):
    entries = [row[arm] for row in rows if row.get(arm) is not None]
    out = {
        "questions": len(rows),
        "observed": len(entries),
        "zero_kept": sum(e["documents"] == 0 for e in entries),
        "zero_sent": sum(e["sent_documents"] == 0 for e in entries),
    }
    for field in ("documents", "sent_documents", "sent_est_tokens"):
        values = [e[field] for e in entries]
        out[field] = {
            "mean": statistics.mean(values) if values else None,
            "median": statistics.median(values) if values else None,
        }
    return out


def comparison(rows, arm):
    with_gold = sum(r["gold"] for r in rows)
    unread = ar.unread(rows, arm)
    out = {
        "with_gold": with_gold,
        "unread": unread,
        "missing": sum(r.get(arm) is None for r in rows),
        "usage": usage(rows, arm),
    }
    for point in ("sent", "expanded"):
        if not with_gold or unread:
            out[point] = ar.NOT_EVIDENCE
        else:
            out[point] = ar.pair(rows, arm, point)
            # The existing helper rounds p for display. Selection uses the exact value.
            out[point]["p"] = ar.nr.mcnemar(out[point]["b_h_only"], out[point]["c_arm_only"])
    return out


def summaries(rows):
    out = {}
    for arm in ARMS:
        out[arm] = {
            "per_base": {
                base: comparison([r for r in rows if r["base"] == base], arm)
                for base in (*ar.EXTERNAL, "aircargo")
            },
            "pooled_deciding": comparison([r for r in rows if r["base"] in ar.DECIDING], arm),
        }
        if arm == "G":
            # Available-case pairs beside the full-cohort NOT_EVIDENCE reading, never selection.
            out[arm]["matched_per_base"] = {
                base: comparison([r for r in rows if r["base"] == base and r["G"] is not None], arm)
                for base in (*ar.EXTERNAL, "aircargo")
            }
            out[arm]["matched_pooled_deciding"] = comparison(
                [r for r in rows if r["base"] in ar.DECIDING and r["G"] is not None], arm
            )
    return out


def eligible(reading):
    for base in ar.DECIDING:
        got = reading["per_base"][base]
        sent, counts = got["sent"], got["usage"]
        if (
            not isinstance(sent, dict)
            or sent["n"] == 0
            or (sent["p"] < 0.05 and sent["b_h_only"] > sent["c_arm_only"])
            or got["unread"]
            or got["missing"]
            or counts["questions"] == 0
            or 20 * counts["zero_kept"] > counts["questions"]
        ):
            return False
    return True


def select(readings):
    accepted = [name for name in THRESHOLDS if eligible(readings[name])]
    name = accepted[-1] if accepted else None
    return {
        "arm": name,
        "threshold": THRESHOLDS[name] if name else None,
        "A_eligible": eligible(readings["A"]),
        "in_sample": True,
    }


def reject_text_fields(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in TEXT_FIELDS or (key == "prompt" and not isinstance(item, dict)):
                raise SystemExit("text field refused")
            reject_text_fields(item)
    elif isinstance(value, list):
        for item in value:
            reject_text_fields(item)


def write_results(out, record, rows, names, questions):
    for value in (record, rows):
        reject_text_fields(value)
        without_text(value, names, questions)
    encoded = {
        "record.json": json.dumps(record, ensure_ascii=False, allow_nan=False, indent=1) + "\n",
        "rows.jsonl": "".join(
            json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in rows
        ),
    }
    if any((out / name).exists() for name in encoded):
        raise SystemExit("output already exists; preserve it")
    out.mkdir(parents=True, exist_ok=True)
    for name, text in encoded.items():
        with (out / name).open("xb") as stream:
            stream.write(text.encode("utf-8"))


def require_hash(path, expected):
    if not path.is_file() or ar.sha256(path) != expected:
        raise SystemExit("frozen input absent or SHA-256 mismatch: " + path.name)


def indexed(rows):
    out = {}
    for row in rows:
        key = row["label"], row["case_id"]
        if key in out:
            raise SystemExit("duplicate question id")
        out[key] = row
    return out


def replay(args):
    budget = ar.replay_budget()
    for path, digest in FROZEN.items():
        require_hash(WS / path, digest)
    source_record = json.loads((STAGE7 / "record.json").read_text(encoding="utf-8"))
    expected = indexed(ar.load_jsonl(STAGE7 / "rows.jsonl"))
    code, batch, control, environment = (
        ar.checkout(),
        ar.package_batch(),
        ar.control(),
        ar.environment(),
    )
    # A new registration has a different HEAD/spec. Bind the journal to its original header,
    # then independently compare the private input provenance and serialized records.
    header = source_record["int8_scores"]["header"]
    if environment != header["environment"] or control != source_record["control"]:
        raise SystemExit("service environment or control differs from stage 7")
    manifest = ar.export_manifest()
    runs = {label: ar.run_inputs(label, args, manifest) for label in ar.LABELS}
    for label, inputs in runs.items():
        actual = {
            "provenance": inputs["provenance"],
            "records_sha256": ar.digest(json.dumps(inputs["records"], sort_keys=True)),
        }
        if actual != header["inputs"][label]:
            raise SystemExit("private input differs from scored journal")
    scored, _ = ar.score_rows(STAGE7 / "int8_scores.jsonl", header, runs)
    scores = indexed(scored)
    if len(expected) != 415 or set(expected) != set(scores):
        raise SystemExit("stage 7 question coverage differs")
    for item in scored:
        validate_scores(item["scores"])
    capture = args.private / "capture"
    calls, capture_digest = read_capture(capture)
    builder, rows = ar.Builder(), []
    for label, inputs in runs.items():
        machine = ar.new_machine(inputs, batch)
        for record in inputs["records"]:
            budget()
            key = label, record["case_id"]
            rows.append(
                evaluate_question(
                    inputs, record, scores[key], machine, builder, expected[key], calls
                )
            )
            builder.cache.clear()
    readings = summaries(rows)
    result = {
        "schema": "bundle0/1",
        "head": code["head"],
        "head_parent": code["head_parent"],
        "spec_sha256": ar.sha256(WS / SPEC),
        "tool_sha256": ar.sha256(Path(__file__)),
        "test_sha256": ar.sha256(WS / "tests/test_bundle0_threshold_replay.py"),
        "inputs_sha256": FROZEN,
        "measure_code_sha256": code["measure_code_sha256"],
        "grader_code_sha256": {
            name: ar.sha256(WS / name)
            for name in (
                "agent/graph.py",
                "agent/prompts.py",
                "reports/codex-only-quality/tools/capture_journal.py",
                "llm/providers/codex.py",
            )
        },
        "environment": environment,
        "control": control,
        "score_head": header["head"],
        "capture_sha256": capture_digest,
        "grader_counts": {
            s: sum(r["grader_status"] == s for r in rows)
            for s in ("matched", "unmatched", "ambiguous", "incomplete")
        },
        "frozen": {
            "thresholds": THRESHOLDS,
            "shape": "largest_gap_longest_tie",
            "alpha": 0.05,
            "zero_fraction": 0.05,
            "input_limit": ar.LIMIT,
        },
        "parity": {"checked": len(rows), "passed": len(rows)},
        "H_usage": {
            base: usage([r for r in rows if r["base"] == base], "H")
            for base in (*ar.EXTERNAL, "aircargo")
        },
        "H_usage_pooled_deciding": usage([r for r in rows if r["base"] in ar.DECIDING], "H"),
        "readings": readings,
        "selection": select(readings),
    }
    names = set().union(*(r["names"] for r in runs.values()))
    questions = [q for r in runs.values() for q in r["questions"]]
    budget()
    write_results(args.out, result, rows, names, questions)
    print(json.dumps({"parity": result["parity"], "selection": result["selection"]}))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=ar.RUNS)
    parser.add_argument("--data-root", type=Path, default=ar.DATA_ROOT)
    parser.add_argument("--v4-runs", type=Path, default=ar.V4_RUNS)
    parser.add_argument("--out", type=Path, default=Path("/Users/julia/RAG_new_bundle0/out"))
    parser.add_argument(
        "--private", type=Path, default=Path("/Users/julia/RAG_new_bundle0/private")
    )
    args = parser.parse_args(argv)
    try:
        return replay(args)
    except ParityError:
        print("H parity failed: NOT_EVIDENCE", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

"""Bundle 0's copied evidence: hashes, registered history, privacy and parsed tables.

No model, Mac environment or PRIVATE input is needed. The measured overlay exists only
on the Mac; Git reads the registered parent, never the overlay or a package fallback.
The target repository must have full history (CI uses fetch-depth: 0). A package without
that parent must fail the historical check, not skip it.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / "reports/bundle0/9672502"
SPEC = "docs/specs/bundle0-reranker-threshold.md"
TOOL = "reports/bundle0/tools/threshold_replay.py"
REPLAY_TEST = "tests/test_bundle0_threshold_replay.py"
CAPSULE = ROOT / "docs/evidence/bundle0-record.md"
FILES = ("record.json", "rows.jsonl", "run.out")
HEAD = "41d5f45192a08b79e9d4d462691c6c7b1b2f1912"
PARENT = "9672502480afa34898c5fe4eb8ba02ef0a0c969d"
BASE_NAMES = {
    "wixqa": "WixQA",
    "conditionalqa": "ConditionalQA",
    "pooled_deciding": "Deciding bases pooled",
    "multihoprag": "MultiHop-RAG",
    "aircargo": "aircargo",
}
DECIDING = ("wixqa", "conditionalqa", "pooled_deciding")
FORBIDDEN = {"question", "answer", "text", "reference", "content"}


def load_tool() -> Any:
    spec = importlib.util.spec_from_file_location("bundle0_record_replay", ROOT / TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tr = load_tool()
record = json.loads((RECORDS / "record.json").read_text("utf-8"))
rows = [json.loads(line) for line in (RECORDS / "rows.jsonl").read_text("utf-8").splitlines()]
log = [json.loads(line) for line in (RECORDS / "run.out").read_text("utf-8").splitlines()]
capsule = CAPSULE.read_text("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def listed_hashes(text: str) -> dict[str, str]:
    pairs = re.findall(r"`((?:reports|tests)/[\w./-]+)` `([0-9a-f]{64})`", text)
    assert len(dict(pairs)) == len(pairs)
    return dict(pairs)


def tables() -> dict[tuple[str, ...], list[list[str]]]:
    """Parse every table; extra rows, tables and malformed separators cannot escape."""
    result = {}
    blocks = re.findall(r"(?m)(?:^\|.*\|\n)+", capsule)
    assert sum(len(block.splitlines()) for block in blocks) == sum(
        line.lstrip().startswith("|") for line in capsule.splitlines()
    )
    for block in blocks:
        parsed = [
            [cell.strip() for cell in line.strip("|").split("|")] for line in block.splitlines()
        ]
        heading, separator, *body = parsed
        assert all(re.fullmatch(r":?-{3,}:?", cell) for cell in separator)
        assert all(len(row) == len(heading) for row in (separator, *body))
        assert tuple(heading) not in result
        result[tuple(heading)] = body
    return result


def comparison(arm: str, base: str, matched: bool = False) -> dict[str, Any]:
    reading = record["readings"][arm]
    prefix = "matched_" if matched else ""
    if base == "pooled_deciding":
        return reading[prefix + base]
    return reading[prefix + "per_base"][base]


def number(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def pair_cells(got: Any, arm: str) -> list[str]:
    if not isinstance(got, dict):
        return ["—"] * 4 + [got]
    return [
        str(got["n"]),
        f"{got['hits']['H']} → {got['hits'][arm]}",
        f"{got['b_h_only']} / {got['c_arm_only']}",
        str(got["p"]),
        got["reading"],
    ]


def secondary(got: dict[str, Any], arm: str, base: str) -> str:
    if base == "pooled_deciding":
        return "—"
    key = tr.ar.nr.METRICS[base][1]
    return f"{got[key]['H']:.4f} / {got[key][arm]:.4f}"


def test_the_three_files_match_the_capsule_and_use_utf8_lf() -> None:
    assert tables()[("File", "SHA-256")] == [
        [f"`{name}`", f"`{sha((RECORDS / name).read_bytes())}`"] for name in FILES
    ]
    for path in (*(RECORDS / name for name in FILES), CAPSULE, Path(__file__)):
        data = path.read_bytes()
        data.decode("utf-8")
        assert not data.startswith(b"\xef\xbb\xbf"), path.name
        assert data.endswith(b"\n") and b"\r" not in data, path.name


def test_record_hashes_match_the_registered_parent_and_committed_files() -> None:
    assert (record["head"], record["head_parent"]) == (HEAD, PARENT)
    # Do not resolve HEAD: the Mac-only overlay is not in the target repository.
    historical = {
        path: subprocess.check_output(["git", "show", f"{PARENT}:{path}"], cwd=ROOT)
        for path in (SPEC, TOOL, REPLAY_TEST)
    }
    listed = listed_hashes(historical[SPEC].decode("utf-8"))
    assert listed == listed_hashes((ROOT / SPEC).read_text("utf-8"))
    # The spec cannot list its own hash; record.spec_sha256 binds its registered bytes.
    for path, field in ((SPEC, "spec_sha256"), (TOOL, "tool_sha256"), (REPLAY_TEST, "test_sha256")):
        assert sha(historical[path]) == record[field] == sha((ROOT / path).read_bytes()), path
        if path != SPEC:
            assert record[field] == listed[path], path
    assert set(listed) == {*record["inputs_sha256"], TOOL, REPLAY_TEST}
    assert {path: listed[path] for path in record["inputs_sha256"]} == record["inputs_sha256"]


def test_frozen_inputs_and_original_score_header_match() -> None:
    listed = listed_hashes((ROOT / SPEC).read_text("utf-8"))
    assert record["inputs_sha256"] == tr.FROZEN
    assert len(record["inputs_sha256"]) == 4
    for path, digest in record["inputs_sha256"].items():
        assert sha((ROOT / path).read_bytes()) == digest == listed[path], path
    previous = json.loads((tr.STAGE7 / "record.json").read_text("utf-8"))
    with (tr.STAGE7 / "int8_scores.jsonl").open(encoding="utf-8") as stream:
        header = json.loads(next(stream))
    assert previous["int8_scores"] == {
        "sha256": record["inputs_sha256"]["reports/stage7/5e308fe/int8_scores.jsonl"],
        "header": header,
    }
    assert record["score_head"] == header["head"]
    assert record["environment"] == header["environment"]
    assert record["control"] == previous["control"]
    assert re.fullmatch(r"[0-9a-f]{64}", record["capture_sha256"])


def test_parity_readings_and_selection_are_rebuilt_without_replay() -> None:
    assert record["schema"] == "bundle0/1"
    assert record["parity"] == {"checked": len(rows), "passed": len(rows)}
    assert len(rows) == 415
    previous = tr.indexed(tr.ar.load_jsonl(tr.STAGE7 / "rows.jsonl"))
    assert set(tr.indexed(rows)) == set(previous)
    for row in rows:
        tr.parity_gate(row, previous[row["label"], row["case_id"]])
        assert row["T00"]["kept_indices"] == list(range(row["H"]["documents"]))
        assert all(row["T00"][key] == value for key, value in row["H"].items())
    assert log[-1] == {key: record[key] for key in ("parity", "selection")}
    assert log == [log[-1]]  # No unguarded plain-text prefix or extra log payload.
    assert tr.summaries(rows) == record["readings"]
    for base, expected in record["H_usage"].items():
        assert tr.usage([row for row in rows if row["base"] == base], "H") == expected
    assert (
        tr.usage([row for row in rows if row["base"] in tr.ar.DECIDING], "H")
        == record["H_usage_pooled_deciding"]
    )
    statuses = Counter(row["grader_status"] for row in rows)
    assert set(statuses) <= set(record["grader_counts"])
    assert record["grader_counts"] == {key: statuses[key] for key in record["grader_counts"]}
    assert sum(record["grader_counts"].values()) == len(rows)
    assert record["frozen"]["thresholds"] == tr.THRESHOLDS
    assert set(record["readings"]) == set(tr.ARMS)
    assert (
        tr.select(record["readings"])
        == record["selection"]
        == {
            "arm": "T00",
            "threshold": 0.0,
            "A_eligible": False,
            "in_sample": True,
        }
    )
    assert [arm for arm in tr.THRESHOLDS if tr.eligible(record["readings"][arm])] == ["T00"]
    assert not tr.eligible(record["readings"]["A"])


def keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from keys(item)


def test_no_artifact_carries_text_fields() -> None:
    for value in (record, *rows, *log):
        assert tr.without_text(value, FORBIDDEN, ()) == value
        tr.reject_text_fields(value)
        for key in keys(value):
            if re.fullmatch(r"[A-Za-z_]+", key):
                assert not FORBIDDEN.intersection(key.lower().split("_")), key
    for row in rows:
        assert isinstance(row["case_id"], str) and not re.search(r"\s", row["case_id"])
        for key, value in row.items():
            if isinstance(value, str):
                assert key in {"label", "base", "case_id", "grader_status"}, key
        for arm in ("H", *tr.ARMS):
            entry = row[arm]
            if entry is None:
                assert arm == "G" and row["grader_status"] != "matched"
                continue
            if arm == "G":
                assert row["grader_status"] == "matched"
            assert entry["unresolved"] is None
            assert set(entry["prompt"]) == {"sha256", "chars", "est_tokens"}
            assert re.fullmatch(r"[0-9a-f]{64}", entry["prompt"]["sha256"])
            assert all(
                not isinstance(value, str) for key, value in entry.items() if key != "prompt"
            )


def test_every_capsule_table_is_rebuilt_from_record() -> None:
    sent, expanded, cohorts, baseline, grader = [], [], [], [], []
    for arm in (*record["frozen"]["thresholds"], "A"):
        for base in DECIDING:
            part = comparison(arm, base)
            usage = part["usage"]
            sent.append(
                [
                    f"{arm}: {BASE_NAMES[base]}",
                    *pair_cells(part["sent"], arm),
                    f"{usage['zero_kept']} / {usage['zero_sent']}",
                    number(usage["sent_documents"]["mean"]),
                    number(usage["sent_est_tokens"]["mean"]),
                    secondary(part["sent"], arm, base),
                ]
            )
            expanded.append(
                [
                    f"{arm}: {BASE_NAMES[base]}",
                    *pair_cells(part["expanded"], arm),
                    secondary(part["expanded"], arm, base),
                ]
            )
    for base, name in BASE_NAMES.items():
        part = comparison("T00", base)
        cohorts.append(
            [
                name,
                str(part["usage"]["questions"]),
                str(part["with_gold"]),
                str(part["unread"]),
                str(part["missing"]),
                *(
                    str(part[p]["n"]) if isinstance(part[p], dict) else "—"
                    for p in ("sent", "expanded")
                ),
            ]
        )
        usage = (
            record["H_usage_pooled_deciding"]
            if base == "pooled_deciding"
            else record["H_usage"][base]
        )
        baseline.append(
            [
                name,
                str(usage["questions"]),
                f"{usage['zero_kept']} / {usage['zero_sent']}",
                *(
                    f"{number(usage[key]['mean'])} / {number(usage[key]['median'])}"
                    for key in ("documents", "sent_documents", "sent_est_tokens")
                ),
            ]
        )
        for matched, scope in ((False, "Full"), (True, "Matched only")):
            part = comparison("G", base, matched)
            assert part["sent"] == part["expanded"]
            grader.append(
                [
                    f"{scope}: {name}",
                    str(part["usage"]["questions"]),
                    str(part["with_gold"]),
                    str(part["usage"]["observed"]),
                    str(part["unread"]),
                    str(part["missing"]),
                    *pair_cells(part["sent"], "G"),
                ]
            )
    assert tables() == {
        ("Run item", "Value"): [
            [key, f"`{record[key]}`"]
            for key in (
                "head",
                "head_parent",
                "spec_sha256",
                "tool_sha256",
                "test_sha256",
                "score_head",
                "capture_sha256",
            )
        ],
        ("Frozen input", "SHA-256"): [
            [f"`{path}`", f"`{digest}`"] for path, digest in record["inputs_sha256"].items()
        ],
        ("Base", "Total", "Gold", "Unread", "Missing", "Paired sent", "Paired expanded"): cohorts,
        (
            "H base",
            "Questions",
            "Zero kept / sent",
            "Kept mean / median",
            "Sent documents mean / median",
            "Sent estimated tokens mean / median",
        ): baseline,
        (
            "Arm and base at sent",
            "n",
            "H → arm hits",
            "b / c",
            "p",
            "Reading",
            "Zero kept / sent",
            "Mean sent documents",
            "Mean sent estimated tokens",
            "Secondary mean H / arm",
        ): sent,
        (
            "Arm and base at expanded",
            "n",
            "H → arm hits",
            "b / c",
            "p",
            "Reading",
            "Secondary mean H / arm",
        ): expanded,
        (
            "G scope and base (sent = expanded)",
            "Total",
            "Gold",
            "Matched",
            "Unread",
            "Missing",
            "n",
            "H → G hits",
            "b / c",
            "p",
            "Reading",
        ): grader,
        ("File", "SHA-256"): [
            [f"`{name}`", f"`{sha((RECORDS / name).read_bytes())}`"] for name in FILES
        ],
    }


def test_opening_reading_provenance_and_limits_are_bound() -> None:
    selection, gate, counts = record["selection"], record["parity"], record["grader_counts"]
    assert (
        f"**{selection['arm']} is selected: threshold {selection['threshold']}, every H document kept.**"
        in capsule
    )
    assert f"Parity passed {gate['passed']} of {gate['checked']}." in capsule
    assert (
        f"G matched {counts['matched']} of {gate['checked']}; unmatched {counts['unmatched']}, "
        f"ambiguous {counts['ambiguous']}, incomplete {counts['incomplete']}."
    ) in capsule
    for arm in ("T01", "T02"):
        part = comparison(arm, "conditionalqa")
        assert (
            f"{arm} ({record['frozen']['thresholds'][arm]:.2f}): ConditionalQA zero kept "
            f"{part['usage']['zero_kept']}/{part['usage']['questions']}; "
            f"sent H {part['sent']['hits']['H']} → {part['sent']['hits'][arm]}, "
            f"b/c {part['sent']['b_h_only']}/{part['sent']['c_arm_only']}, "
            f"p {part['sent']['p']}."
        ) in capsule
    part = comparison("T02", "wixqa")
    assert (
        f"T02 also exceeds the zero limit on WixQA: {part['usage']['zero_kept']}/{part['usage']['questions']}."
        in capsule
    )
    got = comparison("A", "pooled_deciding")["sent"]
    assert (
        f"A pooled sent: H {got['hits']['H']} → {got['hits']['A']} of {got['n']}, "
        f"b/c {got['b_h_only']}/{got['c_arm_only']}, p {got['p']}, {got['reading']}."
    ) in capsule
    for phrase in (
        "T01 fails the per-base zero-kept condition, despite no detected per-base loss.",
        "T02 fails both the ConditionalQA loss condition and the zero-kept condition.",
        "A fails the loss condition on both deciding bases, with no zero-kept questions there.",
        "No filtering threshold in the registered grid, and not the gap rule A, can replace",
        "the batched document grader: each loses gold or empties contexts beyond the registered",
        "The test reads the spec, tool and synthetic test with `git show` at the recorded parent.",
        "There is no fallback and no lookup of the measured overlay, which exists only on the Mac.",
        "The spec's SHA list covers the tool and synthetic test, not the spec itself.",
        "T00..T20 and A have no unread or missing cases on any base.",
        "Full-cohort G is `NOT_EVIDENCE` at both points on every base and pooled deciding.",
        "The grader's own effect on gold is unmeasured for the full cohort.",
        "The choice is in-sample across the registered grid, not a held-out result.",
        "No answers or answer quality were measured.",
        "No detected difference is not equivalence or proof of no loss.",
    ):
        assert phrase in capsule, phrase

"""Amendment 2's S' evidence: copied bytes, provenance, privacy and parsed tables.

No model, private archive or replay is needed. Historical Git bytes bind the registered
test: its digest is absent from the score header, unlike the tool's separate digest.
The recorded parent's Git history is required; nothing is skipped.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / "reports/stage7/98e5bf0-a2"
SPEC = ROOT / "docs/specs/stage7-step1-arms-m3.md"
CAPSULE = ROOT / "docs/evidence/stage7-sprime-record.md"
TOOL = "reports/stage7/tools/arms_replay.py"
REPLAY_TEST = "tests/test_stage7_arms_replay.py"
FILES = (
    "int8_scores.jsonl",
    "parity.jsonl",
    "record.json",
    "replay.out",
    "rows.jsonl",
    "score.out",
)
HEAD = "22822a278b521b6f46bbbf9c45f8ae19514bfa46"
PARENT = "be13ac2a105487fc84ddbe48240fd6058fe423e1"
BASE_NAMES = {
    "wixqa": "WixQA",
    "conditionalqa": "ConditionalQA",
    "multihoprag": "MultiHop-RAG",
    "deciding": "Deciding bases",
    "all_three": "All three",
    "aircargo": "aircargo",
    "aircargo-gr": "aircargo-gr",
}
FORBIDDEN = {"question", "answer", "text", "reference", "content"}


def lines(name: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (RECORDS / name).read_text("utf-8").splitlines()]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


record = json.loads((RECORDS / "record.json").read_text("utf-8"))
previous = json.loads((ROOT / "reports/stage7/5e308fe/record.json").read_text("utf-8"))
header, *scores = lines("int8_scores.jsonl")
rows = lines("rows.jsonl")
parity = lines("parity.jsonl")
score_log = lines("score.out")
capsule = CAPSULE.read_text("utf-8")


def tables() -> dict[tuple[str, ...], list[list[str]]]:
    """Parse all tables, rejecting duplicate headings and malformed separators."""
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


def amendment_hashes() -> dict[str, str]:
    section = SPEC.read_text("utf-8").split("Amendment 2's run:\n", 1)[1]
    section = section.split("Amendment 3's run:", 1)[0]
    listed = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", section))
    assert set(listed) == {TOOL, REPLAY_TEST}
    return listed


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def test_the_files_match_the_capsule_and_use_utf8_lf() -> None:
    listed = tables()[("File", "SHA-256")]
    assert listed == [[f"`{name}`", f"`{sha((RECORDS / name).read_bytes())}`"] for name in FILES]
    for path in (*(RECORDS / name for name in FILES), CAPSULE, Path(__file__)):
        data = path.read_bytes()
        data.decode("utf-8")
        assert not data.startswith(b"\xef\xbb\xbf"), path.name
        assert data.endswith(b"\n") and b"\r" not in data, path.name


def test_the_header_overlay_and_historical_measure_code_are_registered() -> None:
    assert (header["head"], header["head_parent"], header["head_subject"]) == (
        HEAD,
        PARENT,
        f"mf-gate overlay of {PARENT}",
    )
    assert (record["measured_at_head"], record["head_parent"], record["head_subject"]) == (
        header["head"],
        header["head_parent"],
        header["head_subject"],
    )
    assert record["int8_scores"] == {
        "sha256": sha((RECORDS / "int8_scores.jsonl").read_bytes()),
        "header": header,
    }
    for key in ("spec", "tool_sha256", "measure_code_sha256", "environment"):
        assert header[key] == record[key], key
    assert header["spec"] == SPEC.relative_to(ROOT).as_posix()
    assert header["type"] == "header" and header["schema"] == 2

    git("merge-base", "--is-ancestor", "98e5bf0", PARENT)
    assert git("rev-parse", "98e5bf0").decode().strip() != PARENT
    assert sha(git("show", f"{PARENT}:{header['spec']}")) == header["spec_sha256"]
    listed = amendment_hashes()
    assert sha(git("show", f"{PARENT}:{TOOL}")) == header["tool_sha256"] == listed[TOOL]
    assert sha(git("show", f"{PARENT}:{REPLAY_TEST}")) == listed[REPLAY_TEST]
    measured = header["measure_code_sha256"]
    assert TOOL not in measured and REPLAY_TEST not in measured
    assert measured
    for name, digest in measured.items():
        assert sha(git("show", f"{PARENT}:{name}")) == digest, name


def test_parity_logs_and_the_unchanged_five_are_read_again() -> None:
    identities = [(row["label"], row["case_id"]) for row in rows]
    assert len(set(identities)) == len(rows) == header["questions"]
    for entries in (scores, parity):
        assert [(row["label"], row["case_id"]) for row in entries] == identities
    gate = {
        "questions": len(parity),
        "passed": sum(not row["breaks"] for row in parity),
        "v4_saved": sum(bool(row["v4_saved"]) for row in parity),
        "v4_byte_equal": sum(
            bool(row["v4_saved"]) and not {"v4_saved", "v4_prompt"}.intersection(row["breaks"])
            for row in parity
        ),
        "breaks": dict(Counter(item for row in parity for item in row["breaks"])),
    }
    assert gate == record["parity"]
    assert gate["passed"] == gate["questions"]
    assert gate["v4_byte_equal"] == gate["v4_saved"] == record["frozen"]["v4_saved"]
    assert not gate["breaks"]
    assert score_log[-1] == {"score": "complete", "questions": len(scores)}
    forecast = sum(row["seconds"] for row in scores[:10]) / 10 * len(scores)
    assert score_log == [
        {"forecast_seconds": forecast, "stop_seconds": 3 * forecast},
        {"score": "complete", "questions": len(scores)},
    ]
    prefix, block = (RECORDS / "replay.out").read_text("utf-8").split("{", 1)
    assert json.loads("{" + block) == {key: record[key] for key in ("parity", "judge", "decision")}
    assert prefix.splitlines() == [
        f"{arm} {where}: H {got['hits']['H']}, {arm} {got['hits'][arm]} of {got['n']},"
        f" b {got['b_h_only']}, c {got['c_arm_only']}, p {got['p']}, {got['reading']}"
        for arm, stops in record["stops"].items()
        for where, got in stops.items()
    ]
    assert record["judge"] is None
    assert not (RECORDS / "judged.json").exists()
    assert all(
        row["S"]["seeds"] == record["frozen"]["five"]
        and row["S"]["dropped"] == 0
        and not row["S"]["order_changed"]
        for row in rows
    )


def keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from keys(item)


def test_no_artifact_carries_text_fields() -> None:
    spec = importlib.util.spec_from_file_location(
        "stage2_common_sprime_record", ROOT / "reports/stage2/tools/stage2_common.py"
    )
    assert spec and spec.loader
    common = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(common)
    replay_json = json.loads("{" + (RECORDS / "replay.out").read_text("utf-8").split("{", 1)[1])
    for value in (record, previous, header, *rows, *parity, *scores, *score_log, replay_json):
        assert common.without_text(value, FORBIDDEN, ()) == value
        for key in keys(value):
            if re.fullmatch(r"[A-Za-z_]+", key):
                assert not FORBIDDEN.intersection(key.lower().split("_")), key
    for row in (*rows, *parity, *scores):
        assert isinstance(row["case_id"], str) and not re.search(r"\s", row["case_id"])
        for key, value in row.items():
            if isinstance(value, str):
                assert key in {"label", "base", "case_id", "stratum"}, key
        for arm in ("H", "S", "P", "H_old"):
            if arm not in row:
                continue
            entry = row[arm]
            assert entry["unresolved"] is None
            assert set(entry["prompt"]) == {"sha256", "chars", "est_tokens"}
            assert re.fullmatch(r"[0-9a-f]{64}", entry["prompt"]["sha256"])
            assert all(
                not isinstance(value, str) for key, value in entry.items() if key != "prompt"
            )
    # The log test constrains both logs in full, including replay's non-JSON prefix.


def p_text(value: float) -> str:
    return "<0.000001" if value == 0 else f"{value:.6f}".rstrip("0").rstrip(".")


def readings(part: dict[str, Any]) -> Iterator[tuple[str, str, str, dict[str, Any]]]:
    for group in ("per_base", "pooled"):
        for base, points in part[group].items():
            for point in ("sent", "expanded"):
                yield group, base, point, points[point]


def test_every_capsule_table_is_rebuilt_from_the_records() -> None:
    pairs = []
    for arm, display in (("S", "S'"), ("P", "P")):
        for group, base, point, got in readings(record["external"][arm]):
            metric = "gold_articles" if base == "wixqa" else "evidence_recall"
            means = (
                f"{got[metric]['H']:.4f} / {got[metric][arm]:.4f}" if group == "per_base" else "—"
            )
            pairs.append(
                [
                    f"{display}: {BASE_NAMES[base]}",
                    point,
                    str(got["n"]),
                    f"{got['hits']['H']} → {got['hits'][arm]}",
                    f"{got['b_h_only']} / {got['c_arm_only']}",
                    p_text(got["p"]),
                    got["reading"],
                    means,
                ]
            )
    comparison = []
    for group, base, point, got in readings(record["external"]["S"]):
        old = previous["external"]["S"][group][base][point]
        assert (got["n"], got["hits"]["H"]) == (old["n"], old["hits"]["H"])
        comparison.append(
            [
                BASE_NAMES[base],
                point,
                str(got["n"]),
                str(got["hits"]["H"]),
                str(old["hits"]["S"]),
                str(got["hits"]["S"]),
                f"{old['b_h_only']} / {old['c_arm_only']}",
                p_text(old["p"]),
            ]
        )
    context = []
    for label, part in record["labels"].items():
        medians = [
            f"{part['H'][key]['median']:g} / {part['S'][key]['median']:g}"
            for key in ("sent_documents", "sent_chunks", "sent_est_tokens", "chunks")
        ]
        context.append(
            [
                BASE_NAMES[label.removeprefix("p2-")],
                str(part["questions"]),
                *medians,
                str(part["S"]["prompt_changed"]),
            ]
        )
    assert tables() == {
        (
            "Arm and base",
            "Point",
            "n",
            "H → arm hits",
            "b / c",
            "p",
            "Reading",
            "Secondary mean H / arm",
        ): pairs,
        (
            "Base",
            "Point",
            "n",
            "H hits (both runs)",
            "S (2026-10-31) hits",
            "S' hits",
            "H vs S b / c",
            "H vs S p",
        ): comparison,
        (
            "Base / label",
            "Questions",
            "Sent documents H / S'",
            "Sent chunks H / S'",
            "Sent estimated tokens H / S'",
            "Expanded chunks H / S'",
            "S' changed prompts",
        ): context,
        ("File", "SHA-256"): [
            [f"`{name}`", f"`{sha((RECORDS / name).read_bytes())}`"] for name in FILES
        ],
    }


def test_numeric_prose_g1_and_the_amended_reading_are_bound() -> None:
    frozen, gate = record["frozen"], record["parity"]
    old = frozen["old_control"]
    phrases = (
        f"Stage-2 source stand `{record['stand_code_sha']}`; V4 source stand `{record['v4_stand_code_sha']}`.",
        f"Measured HEAD `{header['head']}`, parent `{header['head_parent']}`.",
        f"Subject: `{header['head_subject']}`.",
        f"Header spec SHA-256: `{header['spec_sha256']}`.",
        f"Header tool SHA-256: `{header['tool_sha256']}`.",
        f"Amendment 2's test SHA-256: `{amendment_hashes()[REPLAY_TEST]}`.",
        f"H is H_new: K {frozen['k']}, {frozen['five']} kept, window {frozen['window']:,}, input limit {frozen['input_limit']:,}, runtime `{record['control']['reranker_runtime']}`.",
        f"INT8 export `{header['export_sha256']}`; effective batch {header['batch_size']}, no RAG_RERANK_BATCH override.",
        f"The old-control parity gate uses K {old['k']}, recorded PyTorch scores, window {old['window']:,} and input limit {old['input_limit']:,}.",
        f"Parity passed {gate['passed']} of {gate['questions']}; V4 prompts byte-equal {gate['v4_byte_equal']} of {gate['v4_saved']}; breaks {sum(gate['breaks'].values())}.",
        f"P's rule is {frozen['p_rule'][0]} {frozen['p_rule'][1]}; each primary pair reads loss or gain only at p < {frozen['alpha']}.",
        f"S' kept all {frozen['five']} seeds on all {gate['questions']} questions, with no drops or reordering.",
        f"Of the {gate['v4_saved']} questions with saved V4 prompts, S' changes {record['changed_on_v4']['S']} prompts and P changes {record['changed_on_v4']['P']} against H_new.",
    )
    for phrase in phrases:
        assert phrase in capsule, phrase
    decisions = re.findall(r"```json\n(.*?)\n```", capsule, re.DOTALL)
    assert len(decisions) == 1 and json.loads(decisions[0]) == record["decision"]
    assert record["decision"]["reading"] == "H stays"
    assert record["decision"]["standings"] == {"S": "stopped", "P": "open"}
    assert record["stops"]["S"]["conditionalqa"]["reading"] == "loss"
    assert record["stops"]["S"]["pooled_deciding"]["reading"] == "loss"
    for phrase in (
        "**S' has a detected loss at ConditionalQA and at the deciding bases pooled.**",
        "this is a defect of the lane to find and fix before answers.",
        "S' joined only its seed's section run and skipped the parent expansion H uses.",
        "G1 as printed — advisory for S'",
        "context under rule (c).",
        "P retains Amendment 1's meaning:",
        "provides no aircargo context-judge plan for S'; changed prompts do not open a judge run.",
        "digest is absent.",
        "this capsule does not report S'' results",
    ):
        assert phrase in capsule, phrase
    assert "#amendment-2-" in capsule and "#amendment-3-" in capsule

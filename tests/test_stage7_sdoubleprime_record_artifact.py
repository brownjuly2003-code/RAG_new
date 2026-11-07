"""Amendment 3's S'' capsule: copied bytes, unread reader and row identity.

No model, private archive or replay is needed. The Mac-only measured HEAD is never
resolved. Historical bytes MUST come from the recorded registering parent: no package
commit fallback, skip or replacement is allowed. CI requires full Git history.
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
from statistics import median
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / "reports/stage7/b080c64-a3"
SPEC = ROOT / "docs/specs/stage7-step1-arms-m3.md"
CAPSULE = ROOT / "docs/evidence/stage7-sdoubleprime-record.md"
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
HEAD = "efd2c3d747a890b317475093dc2a4df1aaa942b1"
PARENT = "b080c6453bdd9fb75576c6b8b49ac9cfdb1f3a30"
BASE_NAMES = {
    "wixqa": "WixQA",
    "conditionalqa": "ConditionalQA",
    "multihoprag": "MultiHop-RAG",
    "aircargo": "aircargo",
    "aircargo-gr": "aircargo-gr",
    "deciding": "Deciding bases",
    "all_three": "All three",
    "all": "All questions",
}
FORBIDDEN = {"question", "answer", "text", "reference", "content"}
SIZE_KEYS = ("documents", "chars", "sent_documents", "sent_chars")
CONTEXT_KEYS = ("sent_documents", "sent_chunks", "sent_est_tokens", "chunks")


def lines(name: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (RECORDS / name).read_text("utf-8").splitlines()]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


record = json.loads((RECORDS / "record.json").read_text("utf-8"))
previous = json.loads((ROOT / "reports/stage7/5e308fe/record.json").read_text("utf-8"))
sprime = json.loads((ROOT / "reports/stage7/98e5bf0-a2/record.json").read_text("utf-8"))
header, *scores = lines("int8_scores.jsonl")
rows = lines("rows.jsonl")
parity = lines("parity.jsonl")
score_log = lines("score.out")
capsule = CAPSULE.read_text("utf-8")


def tables() -> dict[tuple[str, ...], list[list[str]]]:
    """Parse every table; no duplicate headings, malformed rows or hidden tables."""
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


def amendment_hashes(text: str) -> dict[str, str]:
    section = text.split("Amendment 3's run:\n", 1)[1].split("\n## ", 1)[0]
    listed = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", section))
    assert set(listed) == {TOOL, REPLAY_TEST}
    return listed


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def test_the_files_match_the_capsule_and_use_utf8_lf() -> None:
    assert tables()[("File", "SHA-256")] == [
        [f"`{name}`", f"`{sha((RECORDS / name).read_bytes())}`"] for name in FILES
    ]
    for path in (*(RECORDS / name for name in FILES), CAPSULE, Path(__file__)):
        data = path.read_bytes()
        data.decode("utf-8")
        assert not data.startswith(b"\xef\xbb\xbf"), path.name
        assert data.endswith(b"\n") and b"\r" not in data, path.name


def test_the_header_and_record_name_the_registered_overlay() -> None:
    assert PARENT.startswith("b080c645")
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
    assert header["rerank_batch"] is None
    assert header["k"] == record["frozen"]["k"] == record["control"]["retrieval_top_k"]
    assert header["export_sha256"] == record["control"]["reranker_onnx_sha256"]
    assert header["ort_version"] == header["environment"]["ort_version"]


def test_every_historical_byte_is_read_at_the_parent_without_fallback() -> None:
    # Do not resolve HEAD: the overlay exists only on the measuring Mac. Missing parent
    # history here is an expected failure, not grounds to use this package's own commits.
    parent_spec = git("show", f"{PARENT}:{header['spec']}")
    assert sha(parent_spec) == header["spec_sha256"]
    listed = amendment_hashes(parent_spec.decode("utf-8"))
    assert listed == amendment_hashes(SPEC.read_text("utf-8"))
    parent_tool = git("show", f"{PARENT}:{TOOL}")
    assert sha(parent_tool) == header["tool_sha256"] == listed[TOOL]
    assert sha(git("show", f"{PARENT}:{REPLAY_TEST}")) == listed[REPLAY_TEST]
    measured = header["measure_code_sha256"]
    assert TOOL not in measured and REPLAY_TEST not in measured
    assert measured == record["measure_code_sha256"] and measured
    for name, digest in measured.items():
        assert sha(git("show", f"{PARENT}:{name}")) == digest, name
    limit = re.search(rb"(?m)^MAX_UNREAD = (\d+)$", parent_tool)
    assert limit and int(limit[1]) == record["frozen"]["max_unread"]


def frozen_inputs() -> list[list[str]]:
    result = [
        ["Stage-2 export manifest", f"`{record['inputs']['export_manifest_sha256']}`"],
        ["V4 record", f"`{record['inputs']['v4_record_sha256']}`"],
    ]
    for base in ("wixqa", "conditionalqa", "multihoprag", "aircargo"):
        digest = record["provenance"][f"p2-{base}"]["archive_sha256"]
        result.append([f"{BASE_NAMES[base]} archive", f"`{digest}`"])
    return result


def test_frozen_inputs_and_environment_are_bound() -> None:
    spec = SPEC.read_text("utf-8")
    for _, digest in frozen_inputs():
        assert digest in spec
    assert header["export_sha256"] in spec
    assert record["stand_code_sha"] in spec and record["v4_stand_code_sha"] in spec
    assert record["inputs"] == sprime["inputs"] == previous["inputs"]
    assert set(header["inputs"]) == set(record["provenance"]) == set(record["labels"])
    for label, got in header["inputs"].items():
        assert got["provenance"] == record["provenance"][label]
        assert got == sprime["int8_scores"]["header"]["inputs"][label]
        assert got == previous["int8_scores"]["header"]["inputs"][label]
        assert got["provenance"]["code_sha"] == record["stand_code_sha"]
        assert got["provenance"]["records"] == record["labels"][label]["questions"]
        assert re.fullmatch(r"[0-9a-f]{64}", got["records_sha256"])
    assert (
        record["provenance"]["p2-aircargo"]["archive_sha256"]
        == record["provenance"]["p2-aircargo-gr"]["archive_sha256"]
    )
    env = header["environment"]
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        assert env["offline"][name] == "1"
    assert env["versions"]["transformers"] in spec
    assert env["versions"]["onnxruntime"] == env["ort_version"]
    assert env["ort_version"] in spec and env["tokenizer_snapshot"] in spec
    assert header["batch_size"] == sprime["int8_scores"]["header"]["batch_size"]


def test_parity_and_both_logs_are_read_again() -> None:
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
    forecast = sum(row["seconds"] for row in scores[:10]) / 10 * len(scores)
    assert score_log == [
        {"forecast_seconds": forecast, "stop_seconds": 3 * forecast},
        {"score": "complete", "questions": len(scores)},
    ]
    prefix, block = (RECORDS / "replay.out").read_text("utf-8").split("{", 1)
    assert json.loads("{" + block) == {key: record[key] for key in ("parity", "judge", "decision")}
    printed = []
    for arm, stops in record["stops"].items():
        for where, got in stops.items():
            value = (
                f"H {got['hits']['H']}, {arm} {got['hits'][arm]} of {got['n']},"
                f" b {got['b_h_only']}, c {got['c_arm_only']}, p {got['p']}, {got['reading']}"
                if isinstance(got, dict)
                else got
            )
            printed.append(f"{arm} {where}: {value}")
    assert prefix.splitlines() == printed
    assert record["judge"] is None
    assert not (RECORDS / "judged.json").exists()


def keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from keys(item)


def test_no_artifact_carries_text_fields() -> None:
    # Reuse the S' test's existing stage-2 guard, including its tokenized-key check.
    spec = importlib.util.spec_from_file_location(
        "stage2_common_sdoubleprime_record", ROOT / "reports/stage2/tools/stage2_common.py"
    )
    assert spec and spec.loader
    common = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(common)
    replay_json = json.loads("{" + (RECORDS / "replay.out").read_text("utf-8").split("{", 1)[1])
    for value in (
        record,
        previous,
        sprime,
        header,
        *rows,
        *parity,
        *scores,
        *score_log,
        replay_json,
    ):
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
            assert entry["unresolved"] in ((None, "members") if arm == "S" else (None,))
            assert set(entry["prompt"]) == {"sha256", "chars", "est_tokens"}
            assert re.fullmatch(r"[0-9a-f]{64}", entry["prompt"]["sha256"])
            assert all(
                not isinstance(value, str)
                for key, value in entry.items()
                if key not in {"prompt", "unresolved"}
            )
    # The log test constrains both logs in full, including replay's non-JSON prefix.


def groups() -> dict[str, tuple[str, ...]]:
    external = tuple(record["external"]["S"]["per_base"])
    bases = (*external, "aircargo")
    return {
        **{base: (base,) for base in bases},
        "deciding": tuple(record["frozen"]["deciding"]),
        "all_three": external,
        "all": bases,
    }


def identity(mine: list[dict[str, Any]]) -> dict[str, int]:
    both = [row for row in mine if "points" in row["H"] and "points" in row["S"]]
    return {
        "questions": len(mine),
        "unresolved": sum(row["S"]["unresolved"] == "members" for row in mine),
        "prompt_equal": sum(
            row["H"]["prompt"]["sha256"] == row["S"]["prompt"]["sha256"] for row in mine
        ),
        "sizes_equal": sum(
            all(row["H"][key] == row["S"][key] for key in SIZE_KEYS) for row in mine
        ),
        "points_equal": sum(
            all(
                row["H"]["points"][point] == row["S"]["points"][point]
                for point in ("sent", "expanded")
            )
            for row in both
        ),
        "both_points": len(both),
    }


def test_identity_and_member_counts_are_rebuilt_without_imputing_points() -> None:
    counts = {
        base: identity([row for row in rows if row["base"] in bases])
        for base, bases in groups().items()
    }
    # On any mismatch report per-base counts; never turn a partial identity into a pass.
    assert all(
        got["prompt_equal"] == got["sizes_equal"] == got["questions"]
        and got["points_equal"] == got["both_points"]
        for got in counts.values()
    ), counts
    for row in rows:
        h, s = row["H"], row["S"]
        assert s["changed"] is False and s["dropped"] == 0 and s["order_changed"] is False, row[
            "base"
        ]
        assert s["seeds"] == record["frozen"]["five"], row["base"]
        assert h["prompt"] == s["prompt"], row["base"]
        assert h["sent_est_tokens"] == s["sent_est_tokens"] and h["cut"] == s["cut"], row["base"]
        if s["unresolved"] == "members":
            assert s["chunks"] is None and s["sent_chunks"] is None and "points" not in s
        else:
            assert s["unresolved"] is None
            assert h["chunks"] == s["chunks"] and h["sent_chunks"] == s["sent_chunks"], row["base"]
            assert ("points" in h) == ("points" in s) == row["gold"]


def test_standing_and_unread_counts_distinguish_gold_from_all_rows() -> None:
    external = record["external"]["S"]
    for base, got in external["per_base"].items():
        mine = [row for row in rows if row["base"] == base]
        unread = sum(row["gold"] and row["S"]["unresolved"] is not None for row in mine)
        assert got["with_gold"] == sum(row["gold"] for row in mine)
        assert got["unread"] == unread > record["frozen"]["max_unread"]
        assert got["sent"] == got["expanded"] == "NOT_EVIDENCE"
        assert record["external"]["P"]["per_base"][base]["unread"] == 0
    for base in external["pooled"]:
        assert any(
            external["per_base"][held]["unread"] > record["frozen"]["max_unread"]
            for held in groups()[base]
        )
        assert external["pooled"][base] == {"sent": "NOT_EVIDENCE", "expanded": "NOT_EVIDENCE"}
    for arm in ("S", "P"):
        expected = {
            base: record["external"][arm]["per_base"][base]["sent"]
            for base in record["frozen"]["deciding"]
        }
        expected["pooled_deciding"] = record["external"][arm]["pooled"]["deciding"]["sent"]
        assert record["stops"][arm] == expected
    assert record["decision"] == {
        "standings": {"S": "NOT_EVIDENCE", "P": "open"},
        "gains": {"S": [], "P": []},
        "arm": None,
        "reading": "NOT_EVIDENCE",
    }


def test_label_medians_and_changed_counts_use_the_recorded_populations() -> None:
    for label, part in record["labels"].items():
        mine = [row for row in rows if row["label"] == label]
        assert part["questions"] == len(mine)
        assert part["graph"] and not part["graph"].get("error")
        for arm in ("H", "S", "P"):
            assert part[arm]["unresolved"] == dict(
                Counter(str(row[arm]["unresolved"]) for row in mine)
            )
            for key in CONTEXT_KEYS:
                available = [row[arm][key] for row in mine if row[arm][key] is not None]
                assert part[arm][key]["median"] == median(available), (label, arm, key)
            if arm != "H":
                assert part[arm]["prompt_changed"] == sum(row[arm]["changed"] for row in mine)
                assert part[arm]["prompt_changed_on_v4"] == sum(
                    row[arm]["changed"] and row["v4_saved"] for row in mine
                )
    for arm in ("S", "P"):
        assert record["changed_on_v4"][arm] == sum(
            row[arm]["changed"] and row["v4_saved"] for row in rows
        )


def p_text(value: float) -> str:
    return "<0.000001" if value == 0 else f"{value:.6f}".rstrip("0").rstrip(".")


def readings(part: dict[str, Any]) -> Iterator[tuple[str, str, str, dict[str, Any]]]:
    for group in ("per_base", "pooled"):
        for base, points in part[group].items():
            for point in ("sent", "expanded"):
                yield group, base, point, points[point]


def test_every_capsule_table_is_rebuilt_from_the_records() -> None:
    standings, identities = [], []
    for base, bases in groups().items():
        mine = [row for row in rows if row["base"] in bases]
        got = identity(mine)
        external = record["external"]["S"]
        reading = external["per_base"].get(base, external["pooled"].get(base, {}))
        # Pools have no separate unread field: sum their recorded per-base counts.
        recorded_bases = [
            external["per_base"][held] for held in bases if held in external["per_base"]
        ]
        standings.append(
            [
                BASE_NAMES[base],
                str(got["questions"]),
                str(got["unresolved"]),
                str(sum(item["with_gold"] for item in recorded_bases)),
                str(sum(item["unread"] for item in recorded_bases)),
                reading.get("sent", "—"),
                reading.get("expanded", "—"),
            ]
        )
        identities.append(
            [
                BASE_NAMES[base],
                str(got["questions"]),
                str(got["unresolved"]),
                str(got["prompt_equal"]),
                str(got["sizes_equal"]),
                f"{got['points_equal']} / {got['both_points']}",
            ]
        )
    pairs, history = [], []
    for group, base, point, got in readings(record["external"]["P"]):
        metric = "gold_articles" if base == "wixqa" else "evidence_recall"
        means = f"{got[metric]['H']:.4f} / {got[metric]['P']:.4f}" if group == "per_base" else "—"
        pairs.append(
            [
                BASE_NAMES[base],
                point,
                str(got["n"]),
                f"{got['hits']['H']} → {got['hits']['P']}",
                f"{got['b_h_only']} / {got['c_arm_only']}",
                p_text(got["p"]),
                got["reading"],
                means,
            ]
        )
        old = previous["external"]["S"][group][base][point]
        prime = sprime["external"]["S"][group][base][point]
        assert (
            (got["n"], got["hits"]["H"])
            == (old["n"], old["hits"]["H"])
            == (prime["n"], prime["hits"]["H"])
        )
        history.append(
            [
                BASE_NAMES[base],
                point,
                str(got["n"]),
                str(got["hits"]["H"]),
                str(old["hits"]["S"]),
                str(prime["hits"]["S"]),
                f"{old['b_h_only']} / {old['c_arm_only']}",
                p_text(old["p"]),
                f"{prime['b_h_only']} / {prime['c_arm_only']}",
                p_text(prime["p"]),
            ]
        )
    context = []
    for label, part in record["labels"].items():
        medians = [
            " / ".join(f"{part[arm][key]['median']:g}" for arm in ("H", "S", "P"))
            for key in CONTEXT_KEYS
        ]
        context.append(
            [
                BASE_NAMES[label.removeprefix("p2-")],
                str(part["questions"]),
                str(part["S"]["unresolved"].get("None", 0)),
                *medians,
                f"{part['S']['prompt_changed']} / {part['P']['prompt_changed']}",
            ]
        )
    assert tables() == {
        ("Frozen input", "SHA-256"): frozen_inputs(),
        (
            "Base / pool",
            "Questions",
            "S unresolved members",
            "With gold",
            "Unread with gold",
            "Tool sent",
            "Tool expanded",
        ): standings,
        (
            "Base / pool",
            "Questions",
            "S unresolved members",
            "Prompt SHA-256 equal",
            "Documents / chars / sent equal",
            "Both points equal / available",
        ): identities,
        (
            "Base",
            "Point",
            "n",
            "H → P hits",
            "b / c",
            "p",
            "Reading",
            "Secondary mean H / P",
        ): pairs,
        (
            "Base",
            "Point",
            "n",
            "H hits (three runs)",
            "S (2026-10-31) hits",
            "S' hits",
            "H vs S b / c",
            "H vs S p",
            "H vs S' b / c",
            "H vs S' p",
        ): history,
        (
            "Base / label",
            "Questions",
            "S readable members",
            "Sent documents H / S'' / P",
            "Sent chunks H / S'' / P",
            "Sent estimated tokens H / S'' / P",
            "Expanded chunks H / S'' / P",
            "S'' / P changed prompts",
        ): context,
        ("File", "SHA-256"): [
            [f"`{name}`", f"`{sha((RECORDS / name).read_bytes())}`"] for name in FILES
        ],
    }


def test_opening_lines_numeric_prose_and_advisory_meaning_are_pinned() -> None:
    assert capsule.splitlines()[2:5] == [
        "**The tool reads S'' as NOT_EVIDENCE: its section-run reader cannot decompose some parent-expanded documents.**",
        f"**S'' sent H_new's exact prompt bytes on {len(rows)} of {len(rows)} questions; Amendment 3's b = c = 0 holds by byte identity, not by a McNemar reading the tool could make.**",
        "**Amendment 3's «any difference is a defect» found no difference from H, only an unread decomposition; this is not a pass of the tool's reading.**",
    ]
    frozen, gate = record["frozen"], record["parity"]
    old = frozen["old_control"]
    phrases = (
        f"Stage-2 source stand `{record['stand_code_sha']}`; V4 source stand `{record['v4_stand_code_sha']}`.",
        f"Measured HEAD `{header['head']}`, parent `{header['head_parent']}`.",
        f"Subject: `{header['head_subject']}`.",
        f"Header spec SHA-256: `{header['spec_sha256']}`.",
        f"Header tool SHA-256: `{header['tool_sha256']}`.",
        f"Amendment 3's test SHA-256: `{amendment_hashes(SPEC.read_text('utf-8'))[REPLAY_TEST]}`.",
        f"H is H_new: K {frozen['k']}, {frozen['five']} kept, window {frozen['window']:,}, input limit {frozen['input_limit']:,}, runtime `{record['control']['reranker_runtime']}`.",
        f"INT8 export `{header['export_sha256']}`; effective batch {header['batch_size']}, no RAG_RERANK_BATCH override.",
        f"The old-control parity gate uses K {old['k']}, recorded PyTorch scores, window {old['window']:,} and input limit {old['input_limit']:,}.",
        f"Parity passed {gate['passed']} of {gate['questions']}; V4 prompts byte-equal {gate['v4_byte_equal']} of {gate['v4_saved']}; breaks {sum(gate['breaks'].values())}.",
        f"MAX_UNREAD is {frozen['max_unread']}; the rule counts unread questions with gold, not all unresolved rows.",
        f"P's rule is {frozen['p_rule'][0]} {frozen['p_rule'][1]}; each primary pair reads loss or gain only at p < {frozen['alpha']}.",
        f"Of the {gate['v4_saved']} questions with saved V4 prompts, S'' changes {record['changed_on_v4']['S']} prompts and P changes {record['changed_on_v4']['P']} against H_new.",
    )
    for phrase in phrases:
        assert phrase in capsule.splitlines(), phrase
    decisions = re.findall(r"```json\n(.*?)\n```", capsule, re.DOTALL)
    assert len(decisions) == 1 and json.loads(decisions[0]) == record["decision"]
    for phrase in (
        "H and P use `external_gold.expansion_members`.",
        "This is a gap of the replay tool, not a",
        "G1 as printed — advisory for S''",
        "context under rule (c);",
        "P retains Amendment 1's meaning:",
        "word turns the graph on, not this reading.",
        "context gold only, with no answer read, on one stand on one day.",
        "medians omit null values:",
        "without a fallback",
        "digest is absent from the header",
    ):
        assert phrase in capsule, phrase
    assert "#amendment-2-" in capsule and "#amendment-3-" in capsule

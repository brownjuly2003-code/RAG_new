"""Amendment 1's completed arms replay: provenance and a read-again of its committed rows.

No model, archive or live replay is needed. The six real artifacts must be present; missing
JSONL files in a reduced checkout are not a reason to skip. The capsule's tables and numeric
prose are built from the artifacts, except the explicitly attributed operator wall times.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
import statistics
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/stage7/tools/arms_replay.py"
RECORDS = ROOT / "reports/stage7/5e308fe"
SPEC = ROOT / "docs/specs/stage7-step1-arms-m3.md"
CAPSULE = ROOT / "docs/evidence/stage7-step1-arms-record.md"
# The six copies matched these SHA-256s on the Mac before transfer.
FILES = {
    "int8_scores.jsonl": "5c4d2bbcc42fe17afb516c877fdeacf7bc3bd05beb8557870b7d1f7bedb156a6",
    "parity.jsonl": "073cf545aec63c66965a7b999d1a8d01d43b1ab70eb6616eed0400234c71bb26",
    "record.json": "b9db1434a6091536540112591e29cb3f02f373660dd06469e6abebc3780b55e4",
    "replay.out": "893998a9b03e93794b3aae0458cb16b35dcff3dbc16340048d58bfdb25cb7b60",
    "rows.jsonl": "2d87859ecfd5e2442eefadcc5dafb471e5a80d13d8227907d59e568010109627",
    "score.out": "bc744b59934fc06309a8c4da15de02cc13c3373e788c70dafcdc669827537e3e",
}
HEAD = "f59169310a026f8962cfdfed01b573be28b9becc"
PARENT = "f2b878ca594779fa03b2561bc271c4cbe88970cb"
SUBJECT = f"mf-gate overlay of {PARENT}"
STAND = "5e308fe48cca0955c3007057a574a425f71e2a6a"
V4_STAND = "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1"
EXPORT = "57335a9f061fe31378c160ddd0861711a0fbdfa20f70aa2640d473dfc4bc1343"
SNAPSHOT = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
COUNTS = {
    "p2-wixqa": 100,
    "p2-conditionalqa": 100,
    "p2-multihoprag": 100,
    "p2-aircargo": 100,
    "p2-aircargo-gr": 15,
}
BASE_NAMES = {
    "wixqa": "WixQA",
    "conditionalqa": "ConditionalQA",
    "multihoprag": "MultiHop-RAG",
    "deciding": "Deciding bases",
    "all_three": "All three",
}


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("arms_replay_record", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(name: str) -> list[dict[str, Any]]:
    # Unlike the tool's optional-input loader, a missing artifact must fail here.
    return [json.loads(line) for line in (RECORDS / name).read_text("utf-8").splitlines()]


ar = _load()
record = json.loads((RECORDS / "record.json").read_text("utf-8"))
rows = lines("rows.jsonl")
parity = lines("parity.jsonl")
header, *scores = lines("int8_scores.jsonl")
score_log = lines("score.out")


def test_the_six_files_are_the_bytes_copied_from_the_mac() -> None:
    for name, digest in FILES.items():
        data = (RECORDS / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, name
        assert data.endswith(b"\n") and b"\r" not in data, name
    assert (len(rows), len(parity), len(scores)) == (415, 415, 415)


def test_the_tool_stands_overlay_and_journal_are_the_registered_run() -> None:
    spec = SPEC.read_text("utf-8")
    listed = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", spec))
    assert record["tool_sha256"] == listed[TOOL.relative_to(ROOT).as_posix()] == sha(TOOL)
    assert (record["spec"], record["stand_code_sha"], record["v4_stand_code_sha"]) == (
        ar.SPEC,
        STAND,
        V4_STAND,
    )
    assert ar.SPEC == SPEC.relative_to(ROOT).as_posix()
    assert (ar.CODE_SHA, ar.V4_STAND) == (STAND, V4_STAND)
    assert (record["measured_at_head"], record["head_parent"], record["head_subject"]) == (
        HEAD,
        PARENT,
        SUBJECT,
    )
    assert "registered before the run" in spec and "`6c52b06`" in spec
    assert record["int8_scores"] == {"sha256": sha(RECORDS / "int8_scores.jsonl"), "header": header}
    assert (
        header["type"],
        header["schema"],
        header["head"],
        header["head_parent"],
        header["head_subject"],
    ) == ("header", 2, HEAD, PARENT, SUBJECT)
    for key in ("spec", "tool_sha256", "environment", "measure_code_sha256"):
        assert header[key] == record[key], key
    # The spec may acquire evidence links later: pin the run's version, not future prose bytes.
    assert (
        header["spec_sha256"] == "33348bb1510a070b86bf4d967ca5097898ca97ae642fbefd87d1775301463664"
    )
    assert set(record["measure_code_sha256"]) == set(ar.MEASURE_CODE)
    assert all(
        re.fullmatch(r"[0-9a-f]{64}", value) for value in record["measure_code_sha256"].values()
    )
    assert record["inputs"]["export_manifest_sha256"] == ar.EXPORT_MANIFEST_SHA256
    assert record["inputs"]["v4_record_sha256"] == ar.V4_RECORD_SHA256
    assert {label: p["records"] for label, p in record["provenance"].items()} == COUNTS
    assert set(header["inputs"]) == set(COUNTS)
    for label, provenance in record["provenance"].items():
        assert header["inputs"][label]["provenance"] == provenance
        assert provenance["code_sha"] == STAND
        assert provenance["base"] == ar.LABELS[label]
        assert provenance["archive_sha256"] == ar.ARCHIVES[provenance["base"]]


def test_the_package_old_control_and_service_environment_are_frozen() -> None:
    assert record["control"] == {
        "retrieval_top_k": 14,
        "ollama_context_window": 3584,
        "reranker_runtime": "onnx",
        "reranker_onnx_sha256": EXPORT,
    }
    assert ar.CONTROL == {
        "retrieval_top_k": 14,
        "ollama_context_window": 3584,
        "reranker_runtime": "onnx",
    }
    assert record["frozen"] == {
        "k": 14,
        "five": 5,
        "window": 3584,
        "input_limit": 2176,
        "p_rule": ["rel", 0.2],
        "alpha": 0.05,
        "max_unread": 5,
        "max_missing": 5,
        "deciding": ["conditionalqa", "wixqa"],
        "qualifies_at": "pooled_deciding",
        "mde_z": 2.8,
        "v4_saved": 300,
        "old_control": {"k": 20, "window": 4096, "input_limit": 2636},
    }
    assert (ar.KMAX, ar.TOP, ar.WINDOW, ar.LIMIT, ar.K_RECORDED, ar.WINDOW_V4, ar.LIMIT_V4) == (
        14,
        5,
        3584,
        2176,
        20,
        4096,
        2636,
    )
    assert (
        header["export_sha256"],
        header["ort_version"],
        header["rerank_batch"],
        header["batch_size"],
        header["k"],
        header["questions"],
    ) == (EXPORT, "1.23.2", None, 32, 14, 415)
    assert record["environment"] == {
        "executable": "/Users/julia/RAG_Support_Assistant/.venv/bin/python",
        "versions": {
            "transformers": "4.44.2",
            "tokenizers": "0.19.1",
            "numpy": "1.26.4",
            "chromadb": "1.5.9",
            "sentence-transformers": "2.7.0",
            "langchain-ollama": "1.1.0",
            "langchain-community": "0.4.1",
            "onnxruntime": "1.23.2",
        },
        "offline": {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"},
        "tokenizer_snapshot": SNAPSHOT,
        "ort_version": "1.23.2",
        "ort_module": "/Users/julia/RAG_new_mf_gate_site/onnxruntime/__init__.py",
        "ort_intra_op_num_threads": 0,
    }
    assert (ar.INT8_SHA256, ar.ORT_VERSION, ar.TRANSFORMERS_VERSION, ar.TOKENIZER_SNAPSHOT) == (
        EXPORT,
        "1.23.2",
        "4.44.2",
        SNAPSHOT,
    )


def test_the_journal_questions_and_forecast_end_in_completion() -> None:
    identities = [(row["label"], row["case_id"]) for row in rows]
    assert len(set(identities)) == 415
    assert [(row["label"], row["case_id"]) for row in scores] == identities
    assert dict(Counter(row["label"] for row in rows)) == COUNTS
    for row in scores:
        assert set(row) == {"label", "case_id", "five", "pool", "scores", "seconds", "batch_size"}
        assert row["batch_size"] == 32
        assert 0 < len(row["pool"]) <= 28
        assert len(row["pool"]) == len(row["scores"]) == len(set(row["pool"]))
        assert all(type(position) is int and position >= 0 for position in row["pool"])
        assert all(ar.finite(value) for value in row["scores"])
        assert ar.finite(row["seconds"]) and row["seconds"] >= 0
        ranked = sorted(
            zip(row["pool"], row["scores"], strict=True), key=lambda p: p[1], reverse=True
        )
        assert row["five"] == [position for position, _ in ranked[:5]]
    forecast = ar.forecast(scores, len(scores))
    assert score_log == [
        {"forecast_seconds": forecast, "stop_seconds": 3 * forecast},
        {"score": "complete", "questions": 415},
    ]
    assert (RECORDS / "score.out").read_text("utf-8").splitlines()[
        -1
    ] == '{"score": "complete", "questions": 415}'
    assert (round(forecast, 2), round(3 * forecast, 2)) == (5848.08, 17544.23)
    seconds = [row["seconds"] for row in scores]
    assert math.fsum(seconds) < 3 * forecast
    assert (
        round(math.fsum(seconds)),
        round(statistics.median(seconds), 2),
        round(max(seconds), 1),
    ) == (7325, 17.28, 34.0)


def test_parity_counts_and_the_replay_log_are_read_again() -> None:
    assert [(r["label"], r["case_id"], r["index"], r["v4_saved"]) for r in parity] == [
        (r["label"], r["case_id"], r["index"], r["v4_saved"]) for r in rows
    ]
    gate = {
        "questions": len(parity),
        "passed": sum(not r["breaks"] for r in parity),
        "v4_saved": sum(bool(r["v4_saved"]) for r in parity),
        "v4_byte_equal": sum(
            bool(r["v4_saved"]) and not {"v4_saved", "v4_prompt"}.intersection(r["breaks"])
            for r in parity
        ),
        "breaks": dict(Counter(b for r in parity for b in r["breaks"])),
    }
    assert (
        gate
        == record["parity"]
        == {"questions": 415, "passed": 415, "v4_saved": 300, "v4_byte_equal": 300, "breaks": {}}
    )
    text = (RECORDS / "replay.out").read_text("utf-8")
    prefix, block = text.split("{", 1)
    assert json.loads("{" + block) == {key: record[key] for key in ("parity", "judge", "decision")}
    expected = []
    for arm in ar.ARMS:
        for where, got in record["stops"][arm].items():
            expected.append(
                f"{arm} {where}: H {got['hits']['H']}, {arm} {got['hits'][arm]} of {got['n']},"
                f" b {got['b_h_only']}, c {got['c_arm_only']}, p {got['p']}, {got['reading']}"
            )
    assert prefix.splitlines() == expected


def test_every_external_pair_advisory_and_decision_is_read_again() -> None:
    # Graph construction needs the private chunk archives; rows suffice for every M3 pair.
    # The graph descriptors themselves are bound by record.json's hash, not recomputed here.
    graphs = {ar.LABELS[label]: part["graph"] for label, part in record["labels"].items()}
    assert all("error" not in graph for graph in graphs.values())
    external = ar.external(rows, graphs)
    assert external == record["external"]
    assert all(
        part["unread"] == 0
        for reading in external.values()
        for part in reading["per_base"].values()
    )
    assert ar.package_advisory(rows) == record["package_advisory"]
    advisory = record["package_advisory"]
    hop = advisory["per_base"]["multihoprag"]
    sent_loss = hop["sent"]["hits"]["H"] - hop["sent"]["hits"]["H_new"]
    expanded_loss = hop["expanded"]["hits"]["H"] - hop["expanded"]["hits"]["H_new"]
    all_sent = advisory["pooled"]["all_three"]["sent"]["hits"]
    # The capsule's two uses of "most": most of the pooled net loss is MultiHop-RAG's;
    # most of MultiHop-RAG's net loss emerges between these two points, not all of it.
    assert 2 * sent_loss > all_sent["H"] - all_sent["H_new"]
    assert 0 < expanded_loss < sent_loss - expanded_loss
    stops = {arm: ar.external_stops(external[arm]) for arm in ar.ARMS}
    assert stops == record["stops"]
    assert ar.candidates(stops) == []
    assert (
        ar.decision(stops)
        == record["decision"]
        == {
            "standings": {"S": "stopped", "P": "open"},
            "gains": {"S": [], "P": []},
            "arm": None,
            "reading": "H stays",
        }
    )
    assert record["judge"] is None
    assert not (RECORDS / "judged.json").exists()


def test_every_label_spread_and_changed_prompt_count_is_read_again() -> None:
    assert set(record["labels"]) == set(COUNTS)
    for label, part in record["labels"].items():
        mine = [r for r in rows if r["label"] == label]
        again = ar.label_summary(mine, None)
        # JSON turns the integer keys of the kept/seeds histograms into strings.
        again = json.loads(json.dumps(again))
        assert {k: v for k, v in again.items() if k != "graph"} == {
            k: v for k, v in part.items() if k != "graph"
        }, label
        for row in mine:
            assert row["base"] == ar.LABELS[label]
            assert row["v4_saved"] == (label in ar.V4_KEYS)
            for arm in ar.ARMS:
                assert row[arm]["changed"] == (
                    row[arm]["prompt"]["sha256"] != row["H"]["prompt"]["sha256"]
                )
    changed = {arm: sum(bool(r["v4_saved"]) and r[arm]["changed"] for r in rows) for arm in ar.ARMS}
    assert changed == record["changed_on_v4"] == {"S": 300, "P": 61}
    assert all(not r["gold"] for r in rows if r["base"] == "aircargo")


FORBIDDEN = {"question", "answer", "text", "reference", "content"}


def keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from keys(item)


def test_no_artifact_carries_text_fields() -> None:
    # The source texts are deliberately not required on the machine reading this evidence.
    # without_text scans keys too; supplement it with field-shape and row-value checks.
    values = [record, header, *rows, *parity, *scores, *score_log]
    replay_json = json.loads("{" + (RECORDS / "replay.out").read_text("utf-8").split("{", 1)[1])
    values.append(replay_json)
    for value in values:
        assert ar.without_text(value, FORBIDDEN, ()) == value
        for key in keys(value):
            # A measuring-code path (e.g. scripts/chat_answer_judge.py) is not a field name.
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
            assert all(not isinstance(v, str) for k, v in entry.items() if k != "prompt")
    # Both logs' complete content is constrained by the log tests, including the plain prefix.


def p_text(value: float) -> str:
    # The reader rounds p to six decimals. Do not print its rounded zero as an exact zero.
    return "<0.000001" if value == 0 else f"{value:.6f}".rstrip("0").rstrip(".")


def pair_rows(part: dict[str, Any], arm: str, prefix: str = "") -> list[str]:
    built = []
    for group in ("per_base", "pooled"):
        for base, readings in part[group].items():
            for point in ("sent", "expanded"):
                got = readings[point]
                secondary = ar.nr.METRICS[base][1] if group == "per_base" else None
                means = (
                    f"{got[secondary]['H']:.4f} / {got[secondary][arm]:.4f}" if secondary else "—"
                )
                built.append(
                    f"| {prefix}{BASE_NAMES[base]} | {point} | {got['n']} |"
                    f" {got['hits']['H']} → {got['hits'][arm]} |"
                    f" {got['b_h_only']} / {got['c_arm_only']} | {p_text(got['p'])} |"
                    f" {got['reading']} | {means} |"
                )
    return built


def provenance_phrases() -> list[str]:
    control, frozen, env = record["control"], record["frozen"], record["environment"]
    old = frozen["old_control"]
    return [
        f"Stage-2 source stand `{record['stand_code_sha']}`; V4 source stand `{record['v4_stand_code_sha']}`.",
        f"Measured HEAD `{record['measured_at_head']}`, parent `{record['head_parent']}`.",
        f"Subject: `{record['head_subject']}`.",
        f"H is H_new: K {control['retrieval_top_k']}, {frozen['five']} kept, window {control['ollama_context_window']:,}, input limit {frozen['input_limit']:,}, runtime `{control['reranker_runtime']}`.",
        f"INT8 export `{control['reranker_onnx_sha256']}`; effective batch {header['batch_size']}, no RAG_RERANK_BATCH override.",
        f"The old-control parity gate uses K {old['k']}, recorded PyTorch scores, window {old['window']:,} and input limit {old['input_limit']:,}.",
        f"P's rule is {frozen['p_rule'][0]} {frozen['p_rule'][1]}; each primary pair reads loss or gain only at p < {frozen['alpha']}.",
        f"Service Python `{env['executable']}`; transformers {env['versions']['transformers']}, tokenizers {env['versions']['tokenizers']}, ONNX Runtime {env['ort_version']}.",
        f"HF_HUB_OFFLINE={env['offline']['HF_HUB_OFFLINE']}, TRANSFORMERS_OFFLINE={env['offline']['TRANSFORMERS_OFFLINE']}; tokenizer snapshot `{env['tokenizer_snapshot']}`.",
        f"ORT module `{env['ort_module']}`; intra-op thread setting {env['ort_intra_op_num_threads']} (automatic).",
        f"Parity passed {record['parity']['passed']} of {record['parity']['questions']}; V4 prompts byte-equal {record['parity']['v4_byte_equal']} of {record['parity']['v4_saved']}; breaks {sum(record['parity']['breaks'].values())}.",
        f"Of the {record['parity']['v4_saved']} questions with saved V4 prompts, S changes {record['changed_on_v4']['S']} prompts and P changes {record['changed_on_v4']['P']} against H_new.",
    ]


def reading_phrases() -> list[str]:
    advisory = record["package_advisory"]
    sent, expanded = (advisory["pooled"]["all_three"][point] for point in ("sent", "expanded"))
    deciding = advisory["pooled"]["deciding"]["sent"]
    hop_sent, hop_expanded = (
        advisory["per_base"]["multihoprag"][point] for point in ("sent", "expanded")
    )
    seconds = [row["seconds"] for row in scores]
    return [
        f"All-three sent: {sent['hits']['H']} → {sent['hits']['H_new']} of {sent['n']}, p {sent['p']:.3f}, a detected loss.",
        f"MultiHop-RAG carries most of that net loss: {hop_sent['hits']['H']} → {hop_sent['hits']['H_new']} of {hop_sent['n']} sent; deciding bases {deciding['hits']['H']} → {deciding['hits']['H_new']} of {deciding['n']}, p {deciding['p']:.3f}, no detected difference.",
        f"All-three expanded: {expanded['hits']['H']} → {expanded['hits']['H_new']} of {expanded['n']}, p {expanded['p']:.3f}, no detected difference; MultiHop-RAG {hop_expanded['hits']['H']} → {hop_expanded['hits']['H_new']} of {hop_expanded['n']}.",
        f"Most of MultiHop-RAG's net drop appears between expanded and sent, where the {record['frozen']['input_limit']:,}-token input limit cuts.",
        f"The score journal has {len(scores)} question rows plus its header; the log ends complete at {score_log[-1]['questions']} questions.",
        f"Its first-ten forecast was {score_log[0]['forecast_seconds']:,.2f} s; the stop was {score_log[0]['stop_seconds']:,.2f} s.",
        f"The {len(seconds)} journal durations sum to {math.fsum(seconds):,.0f} s; median {statistics.median(seconds):.2f} s, maximum {max(seconds):.1f} s.",
    ]


# Supplied by the operator, not timestamps inside the six artifacts. This pins the attribution,
# not a measurement inferred from the logs (which contain no wall-clock timestamps).
OPERATOR = "The operator reports about 2 h 03 min wall time for score, including load, and 57 s for replay (exit 0) on 2026-10-31."
LIMITS = (
    "**H stays.** S is stopped by a detected loss; P remains open but has no detected gain.",
    "No arm qualifies: no judge plan, no PRIVATE folder and no judged step; no laptop judging step or arm answer run follows.",
    "The advisory comparison decides nothing; it does not isolate a lever's effect.",
    "The two points do not establish a cause. Stage 5 measures what the package does to answers.",
    "These are the run's durations only, not a speed claim under PLAN §4.3 M5.",
    "The wall times are operator observations outside the artifacts, whose logs carry no timestamps.",
    "No answer quality was measured. One stand and one day do not establish general performance.",
    "M3 is bounded by external_gold's available gold; missing gold is not a miss.",
    "Aircargo has no context gold here and is read only by the parity gate; its arm spreads decide nothing.",
)


def test_every_capsule_table_row_is_built_from_the_record() -> None:
    lines = CAPSULE.read_text("utf-8").splitlines()
    built = [
        *(row for arm in ar.ARMS for row in pair_rows(record["external"][arm], arm, f"{arm}: ")),
        *pair_rows(record["package_advisory"], "H_new"),
        *(f"| `{name}` | `{sha(RECORDS / name)}` |" for name in FILES),
    ]
    assert len(built) == 36
    # Exact table contents: an extra numeric row cannot silently escape the test.
    actual = [line for line in lines if line.startswith("| ")]
    headings = {
        "| Arm and base | Point | n | H → arm hits | b / c | p | Reading | Secondary mean H / arm |",
        "| Base | Point | n | H_old → H_new hits | b / c | p | Reading | Secondary mean old / new |",
        "| File | SHA-256 |",
    }
    assert [line for line in actual if line not in headings] == built


def test_the_capsules_numeric_prose_and_limits_are_pinned() -> None:
    lines = CAPSULE.read_text("utf-8").splitlines()
    for phrase in (*provenance_phrases(), *reading_phrases(), OPERATOR, *LIMITS):
        assert phrase in lines, phrase

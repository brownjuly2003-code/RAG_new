"""Read the committed stage-5 record again, without a model or private inputs.

Run in the full repository: missing artifacts fail, never skip. The sent-context
M3 measurement needs private corpora and saved prompts, so this test reuses the
record's sent_cases and baseline.old_m3, then rebuilds their paired reading.
It cannot remeasure that private replay, answer runs, or private judge requests.
The operator reports Python 3.11.13 for the read; the Mac gate uses 3.11.15.
Only fraction means use a 1e-12 tolerance (3.12 changed float summation).
"""

import copy
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports/stage4-final/tools"
EXTERNAL = TOOLS / "external"
BASELINE = ROOT / "reports/stage4-final/stage5/baseline.json"
RECORDS = BASELINE.parent / "2057ad0"
CAPSULE = ROOT / "docs/evidence/stage5-final-external-record.md"
SPEC = ROOT / "docs/specs/stage5-final-external.md"
STAGE5_SHA = "2057ad0e5733fbf18d6f199a0cfd94927aec85d8"
ITEM6_SHA = "138f3b3f6ac223540965cc831838ff4f671a2200"
BASES = ("wixqa", "conditionalqa", "multihoprag")
LABELS = dict(zip(BASES, ("WixQA", "ConditionalQA", "MultiHop-RAG"), strict=True))
BASELINE_SHA256 = "a723a94a346ca6faba2bfb8ff8fa920577eac2b613a663e10f1959e67f2a140e"
FILES = {
    "plans-conditionalqa.json": "dd3c77445b95cb0de396ed957c3a4f1149ab8cd1a59d45975bcdb121934d0ac3",
    "plans-multihoprag.json": "f4ac1bfdd9b18903ae98b6b55add46b5572cdf78b3fbb6f1e38eaf7aef47f8fe",
    "plans-wixqa.json": "0230a953670f272d509a590b20a68c03c933a579fc1e3c8224a0a54b0dbb92fc",
    "record.json": "6ae0d6e1a48b468ceb6fc5cade58bd961a41ea5e8e1c379467ce9dde354f3c1b",
    "stage5-conditionalqa-bridge.json": "3b5ed1a6a39e2601dcfb2177fb0060b2d943df3c70436807c1cd9e93dfd83255",
    "stage5-conditionalqa-m1.cases.jsonl": "c51985283b4b1d4cc4a5acec55b4821d679432c0f40e3baaed4b8d28b80550d2",
    "stage5-conditionalqa-m1.json": "2d4d19f0a98adddc55942a024161acf49ada34407fde0e511887b33f3906191a",
    "stage5-conditionalqa-m2.cases.jsonl": "c32ad3b9a1d515aba2c11dc8fa714d9d810856860cc180b9acc0adc1f31ddcd9",
    "stage5-conditionalqa-m2.json": "093df6572eb6a1046b83f2fbab5216b852f00d60038127bf9a1daa787fcf2890",
    "stage5-multihoprag-bridge.json": "25c7983f6d1b7a01870c5038007233bc0d240f8907e1547da9b44e0234acebcd",
    "stage5-multihoprag-m1.cases.jsonl": "7d960011f4e5ba7e4404a003dccdaf8ab46c2237184009ba8155836085543a99",
    "stage5-multihoprag-m1.json": "11f6ebc3b6c73679193e286c6a7206609d2eca90437fb939430bde45ae78f760",
    "stage5-multihoprag-m2.cases.jsonl": "bda6155c65824fd9f00388b47ce4d0b9c1ca41782e779df77f25e429731e5649",
    "stage5-multihoprag-m2.json": "86f1077f3f9d0fa874b0abc939b6acb419f2b0210d4864dfee3df1338e8584a8",
    "stage5-wixqa-bridge.json": "9106d9b9944b3adb45a81e313c6ec00b3ec2c9780592226c9ddad98484d5bd26",
    "stage5-wixqa-m1.cases.jsonl": "40888f0500e1be401bbf28ce1d3776bb06bb1ba066d5a98ea36e304336d9f71e",
    "stage5-wixqa-m1.json": "4b7a0cd04ca057f442e7416c5dc8f377cc8e54a8b471e115e99741df20a629a8",
    "stage5-wixqa-m2.cases.jsonl": "d30f87c84d53c662cbbe18b338891df13a8d1de4358e7787448d7e5d3168ac2f",
    "stage5-wixqa-m2.json": "b5f0611281d4a3cf486ab17d51d2bfa5c1c397f8a3119d1868cd8d4fd968028d",
}


def read(path):
    return json.loads(path.read_text("utf-8"))


def rows(path):
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recorded_path(value):
    # Accept the laptop's separators on the Mac without changing hashed bytes.
    path = PureWindowsPath(value)
    assert not path.drive and not path.root and ".." not in path.parts
    assert path.parts[0] == "reports"
    return ROOT.joinpath(*path.parts)


def old_path(baseline, base, metric):
    code = baseline["bases"][base]["old_code"]
    prefix = "p4" if base == "multihoprag" else "v4"
    found = [
        recorded_path(value)
        for value in baseline["inputs"]
        if recorded_path(value).name == f"{prefix}-{base}-judge-{metric}.json"
    ]
    assert len(found) == 1 and code in found[0].parts
    assert found[0].with_suffix(".cases.jsonl") in {
        recorded_path(value) for value in baseline["inputs"]
    }
    return found[0]


@pytest.fixture
def artifacts():
    return SimpleNamespace(
        baseline=read(BASELINE),
        record=read(RECORDS / "record.json"),
        receipts={base: read(RECORDS / f"plans-{base}.json") for base in BASES},
        exports={
            (base, metric): read(RECORDS / f"stage5-{base}-{metric}.json")
            for base in BASES
            for metric in ("m1", "m2", "bridge")
        },
    )


@pytest.fixture
def tools(monkeypatch):
    # CLI modules import siblings by name; restore those bindings and sys.path.
    monkeypatch.syspath_prepend(str(TOOLS))
    monkeypatch.syspath_prepend(str(EXTERNAL))
    modules = {}
    for folder, names in (
        (TOOLS, ("common", "stand", "record", "run", "judge")),
        (EXTERNAL, ("protocol", "sent_gold", "prepare", "execute", "grading", "reading")),
    ):
        for name in names:
            spec = importlib.util.spec_from_file_location(name, folder / f"{name}.py")
            module = importlib.util.module_from_spec(spec)
            monkeypatch.setitem(sys.modules, name, module)
            spec.loader.exec_module(module)
            modules[name] = module
    return SimpleNamespace(**modules)


def test_public_bytes_lf_and_all_recorded_input_hashes(artifacts):
    expected_names = {"record.json"} | {f"plans-{base}.json" for base in BASES}
    expected_names |= {
        f"stage5-{base}-{suffix}"
        for base in BASES
        for suffix in ("m1.json", "m1.cases.jsonl", "m2.json", "m2.cases.jsonl", "bridge.json")
    }
    assert set(FILES) == expected_names
    for path, digest in [(BASELINE, BASELINE_SHA256)] + [
        (RECORDS / name, digest) for name, digest in FILES.items()
    ]:
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, path
        assert data.endswith(b"\n") and b"\r" not in data and not data.startswith(b"\xef\xbb\xbf")
        data.decode("utf-8")
    record = artifacts.record
    assert record["baseline_sha256"] == sha(BASELINE)
    assert record["receipts_sha256"] == {
        base: sha(RECORDS / f"plans-{base}.json") for base in BASES
    }
    assert record["exports_sha256"] == {
        name: sha(RECORDS / name) for name in FILES if name.startswith("stage5-")
    }
    paths = {recorded_path(key): digest for key, digest in artifacts.baseline["inputs"].items()}
    assert len(paths) == len(artifacts.baseline["inputs"])
    for path, digest in paths.items():
        assert sha(path) == digest, path


def test_registration_stand_receipts_and_judge_provenance(artifacts, tools):
    baseline, record = artifacts.baseline, artifacts.record
    assert baseline["spec"] == record["spec"] == SPEC.relative_to(ROOT).as_posix()
    assert baseline["status"] == record["status"] == "counted"
    assert baseline["order"] == list(BASES) and set(record["corpora"]) == set(BASES)
    assert record["absent_bases"] == []
    assert baseline["item6_sha"] == record["product_diff"]["item6_sha"] == ITEM6_SHA
    assert record["product_diff"]["stage5_sha"] == STAGE5_SHA
    assert record["product_diff"] == tools.protocol.product_diff(ROOT, ITEM6_SHA, STAGE5_SHA)
    pins = dict(re.findall(r"`([\w./-]+\.py)` `([0-9a-f]{64})`", SPEC.read_text("utf-8")))
    assert pins
    for path, digest in pins.items():
        assert sha(ROOT / path) == digest, path
    for base in BASES:
        old = baseline["bases"][base]
        answers = record["corpora"][base]["answers"]
        provenance, held = answers["provenance"], answers["stand"]
        assert answers["status"] == "counted" and answers["base"] == base
        assert provenance["code_sha"] == STAGE5_SHA
        assert provenance["corpus_sha256"] == old["corpus"]
        assert provenance["cases_sha256"] == old["cases_sha256"]
        assert old["old_code"] == tools.protocol.OLD[base]
        assert len(old["ids"]) == len(set(old["ids"])) == len(answers["cases"]) == 100
        assert [case["case_id"] for case in answers["cases"]] == old["ids"]
        tools.record.stand_gate(held)
        assert held["settings"] == {
            **tools.common.SETTINGS,
            "reranker_onnx_path": tools.common.ONNX,
        }
        assert held["settings"]["retrieval_top_k"] == 14
        assert held["settings"]["ollama_context_window"] == 3584
        assert held["settings"]["reranker_runtime"] == "onnx"
        assert held["settings"]["rerank_top_k"] == 5
        assert held["settings"]["ollama_model_name"] == "qwen3:4b-instruct-2507-q4_K_M"
        assert held["input_limit"] == 2176 and held["prompt_id"] == "QA_PROMPT_V4"
        env = held["environment"]
        assert env["offline"] == {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
        assert env["ort_version"] == env["versions"]["onnxruntime"] == "1.23.2"
        assert env["versions"]["transformers"] == "4.44.2"
        assert provenance["model_digest"] == held["model_digest"] == tools.common.MODEL_DIGEST
        for case in answers["cases"]:
            tools.record.case_gate(case)
        pin = artifacts.receipts[base]
        assert pin["spec"] == record["spec"] and pin["base"] == base
        assert pin["completion"]["status"] == "complete"
        assert pin["completion"]["base"] == base
        assert pin["completion"]["code_sha"] == STAGE5_SHA
        assert pin["baseline_sha256"] == pin["completion"]["baseline_sha256"] == sha(BASELINE)
        assert pin["completion"]["product_diff"] == record["product_diff"]
        assert pin["answer_files"] == pin["completion"]["batch_sha256"]
        assert set(pin["answer_files"]) == set(answers["runs"])
        assert pin["inputs"][base]["source"] == old["bridge_source"]
        assert pin["inputs"][base]["references_sha256"] == old["references_sha256"]
        assert pin["empty_answers"] == record["corpora"][base]["empty_answers"]
        assert set(pin["plans"]) == {f"{base}-{metric}" for metric in ("m1", "m2", "bridge")}
        for metric, historical in old["old_judges"].items():
            exported = read(old_path(baseline, base, metric))["provenance"]
            assert historical == {key: exported[key] for key in historical}
        for metric in ("m1", "m2"):
            exported = artifacts.exports[base, metric]
            p = exported["provenance"]
            assert p["plan_sha256"] == pin["plans"][f"{base}-{metric}"]
            assert exported["requests_valid"] == pin["requests"][f"{base}-{metric}"]
            assert set(p["runs"]) == set(answers["runs"])
            assert {run["code_sha"] for run in p["runs"].values()} == {STAGE5_SHA}
            assert p["route"]["model"] == "claude-opus-5-5" and p["route"]["effort"] == "max"
            # MultiHop has no admitted old M2: compare its instrument with old M1.
            historical = old["old_judges"].get(metric, old["old_judges"]["m1"])
            for key in ("route", "salt", "instructions_sha256"):
                assert p[key] == historical[key], (base, metric, key)
        bridge = artifacts.exports[base, "bridge"]
        # The bridge schema puts these hashes at the top level, not in provenance.
        assert bridge["plan_sha256"] == pin["plans"][f"{base}-bridge"]
        assert bridge["source_plan_sha256"] == old["bridge_source"]["plan"]
        assert bridge["source_verdicts_sha256"] == old["bridge_source"]["verdicts"]


def assert_reading(actual, expected):
    actual, expected = copy.deepcopy(actual), copy.deepcopy(expected)
    if "m3" in actual:
        means = actual["m3"].pop("fraction_mean")
        held = expected["m3"].pop("fraction_mean")
        assert set(means) == set(held) == {"old", "new"}
        for side in means:
            assert means[side] == pytest.approx(held[side], rel=0, abs=1e-12)
    assert actual == expected


def test_read_again_rebuilds_every_corpus_the_pool_and_the_decision(artifacts, tools):
    baseline, record = artifacts.baseline, artifacts.record
    tables = {}
    for base in BASES:
        old, stored = baseline["bases"][base], record["corpora"][base]
        ids = old["ids"]
        prompts = {
            case["case_id"]: case["prompts"][0]["sha256"] for case in stored["answers"]["cases"]
        }
        gold = tools.protocol.table(stored["sent_cases"], ids)
        assert all(gold[ident]["prompt_sha256"] == prompts[ident] for ident in ids)
        old_record, a = tools.protocol.judge_record(
            old_path(baseline, base, "m1"),
            base,
            "m1",
            ids,
            old["references_sha256"],
            old["old_code"],
        )
        pin = artifacts.receipts[base]
        new, b = tools.protocol.judge_record(
            RECORDS / f"stage5-{base}-m1.json",
            base,
            "m1",
            ids,
            old["references_sha256"],
            STAGE5_SHA,
            prompts,
        )
        assert new["provenance"]["plan_sha256"] == pin["plans"][f"{base}-m1"]
        assert sum(row.get("empty_answer") is True for row in b.values()) == pin["empty_answers"]
        try:
            tools.reading.bridge_gate(
                artifacts.exports[base, "bridge"], old_record, pin["plans"][f"{base}-bridge"]
            )
        except SystemExit as error:
            assert base == "multihoprag" and str(error) == "NOT_EVIDENCE: bridge stability failed"
            rebuilt = {"status": "NOT_EVIDENCE", "reason": str(error), "advisory": True}
        else:
            rebuilt = tools.reading.compare(
                base, a, b, tools.protocol.table(old["old_m3"], ids), gold
            )
            tables[base] = (a, b)
        rec, b2 = tools.protocol.judge_record(
            RECORDS / f"stage5-{base}-m2.json",
            base,
            "m2",
            ids,
            old["references_sha256"],
            STAGE5_SHA,
            prompts,
        )
        assert rec["provenance"]["plan_sha256"] == pin["plans"][f"{base}-m2"]
        assert sum(row.get("empty_answer") is True for row in b2.values()) == pin["empty_answers"]
        a2 = None
        if base in tools.protocol.PRIMARY and rebuilt["status"] == "counted":
            _, a2 = tools.protocol.judge_record(
                old_path(baseline, base, "m2"),
                base,
                "m2",
                ids,
                old["references_sha256"],
                old["old_code"],
            )
        rebuilt["m2"] = tools.reading.m2_read(base, rec, b2, a2, rebuilt["status"] == "counted")
        rebuilt["empty_answers"] = pin["empty_answers"]
        assert_reading(
            rebuilt,
            {key: value for key, value in stored.items() if key not in ("answers", "sent_cases")},
        )
    primary = tools.reading.pooled(tables)
    assert primary == record["primary"]
    assert tools.reading.outcome(primary) == record["decision"]


def test_bridges_rebuild_stability_from_saved_pairs(artifacts, tools):
    from scripts.chat_answer_judge import quadratic_kappa

    export = tools.common.frozen("export")
    for base in BASES:
        bridge = artifacts.exports[base, "bridge"]
        held = bridge["retest"]
        pairs = held["pairs_list"]
        assert held["scale"] == ["bad", "partial_ok", "good"]
        assert all(
            len(pair) == 2 and all(value in range(len(held["scale"])) for value in pair)
            for pair in pairs
        )
        assert held["planned"] == artifacts.receipts[base]["requests"][f"{base}-bridge"]
        assert held["planned"] == held["pairs"] == len(pairs) == len(bridge["pairs"])
        assert held["pairs_ids"] == [pair["first"] for pair in bridge["pairs"]]
        assert len(set(held["pairs_ids"])) == len(pairs)
        assert held["agree"] == sum(a == b for a, b in pairs)
        assert held["two_steps_apart"] == sum(abs(a - b) >= 2 for a, b in pairs)
        kappa = quadratic_kappa(pairs, len(held["scale"]))
        assert held["quadratic_kappa"] == kappa
        interval = export.kappa_interval(pairs, len(held["scale"]))
        assert {key: held[key] for key in interval} == interval
        assert held["passes_by_kappa"] == (kappa is not None and kappa >= export.KAPPA)
        assert held["passes_by_agreement"] == (
            held["agree"] * export.OF >= export.AGREE * len(pairs) and held["two_steps_apart"] == 0
        )
        assert held["enough_pairs"] == (len(pairs) >= export.MIN_PAIRS)
        assert held["passed"] == (
            held["enough_pairs"] and (held["passes_by_kappa"] or held["passes_by_agreement"])
        )
        assert held["passed"] is (base != "multihoprag")
        assert bridge["status"] == ("counted" if held["passed"] else "NOT_EVIDENCE")
        for pair in bridge["pairs"]:
            assert pair["copy"] == pair["first"] + "-retest"
            assert pair["old_cli"] in bridge["admitted_cli"]["old"]
            assert pair["new_cli"] in bridge["admitted_cli"]["new"]
    # stability() stores (before, after): all extreme changes here are bad -> good.
    held = artifacts.exports["multihoprag", "bridge"]["retest"]
    assert [pair for pair in held["pairs_list"] if abs(pair[0] - pair[1]) >= 2] == [
        [held["scale"].index("bad"), held["scale"].index("good")]
    ] * held["two_steps_apart"]


def assert_no_raw_strings(value, reference_values, trail=()):
    if isinstance(value, dict):
        for key, item in value.items():
            path = (*trail, key)
            if key.lower() in {"question", "answer", "text", "content"}:
                assert not isinstance(item, str), path
            if key.lower() == "reference" and isinstance(item, str):
                assert item in reference_values, path
            assert_no_raw_strings(item, reference_values, path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            assert_no_raw_strings(item, reference_values, (*trail, index))


def test_record_and_exports_have_no_strings_under_raw_text_keys():
    from scripts.chat_answer_judge import REFERENCE

    for name in FILES:
        if name != "record.json" and not name.startswith("stage5-"):
            continue
        path = RECORDS / name
        values = rows(path) if path.suffix == ".jsonl" else [read(path)]
        for index, value in enumerate(values):
            assert_no_raw_strings(value, REFERENCE, (name, index))
            if name.endswith("-m1.cases.jsonl"):
                assert value["reference"] == "none"


# Only the displayed numbers are pinned here. All unprinted fields are rebuilt above.
# n, old/new shares, difference, read95, clusters, detected, direction
PAIRED_PRINT = {
    "Pooled M1 bad": (200, 0.54, 0.56, 0.02, [-0.0453, 0.0851], 137, False, "not detected"),
    "WixQA M1 bad": (100, 0.51, 0.59, 0.08, [-0.0124, 0.1697], 77, False, "not detected"),
    "WixQA M1 good": (100, 0.4, 0.3, -0.1, [-0.1856, -0.0121], 77, True, "falls"),
    "ConditionalQA M1 bad": (100, 0.57, 0.53, -0.04, [-0.1313, 0.0527], 60, False, "not detected"),
    "ConditionalQA M1 good": (100, 0.35, 0.38, 0.03, [-0.0523, 0.1117], 60, False, "not detected"),
    "WixQA M2 agrees": (100, 0.34, 0.34, 0.0, [-0.0795, 0.0769], 77, False, "not detected"),
    "ConditionalQA M2 agrees": (
        80,
        0.6,
        0.5875,
        -0.0125,
        [-0.0716, 0.0468],
        40,
        False,
        "not detected",
    ),
    "WixQA M3 sent": (100, 0.68, 0.67, -0.01, [-0.0507, 0.0304], 77, False, "not detected"),
    "ConditionalQA M3 sent": (
        80,
        0.75,
        0.725,
        -0.025,
        [-0.0725, 0.0205],
        40,
        False,
        "not detected",
    ),
}
PAIRED_HEADER = [
    "| Metric | Old hits / n (share) | Package hits / n (share) | Change, pp | read95, pp | Clusters | Detected | Direction |",
    "|---|---:|---:|---:|---|---:|---|---|",
]
# planned, pairs, agree, two_steps_apart, kappa, ci95, kappa pass, agreement pass, passed
BRIDGE_PRINT = {
    "wixqa": (15, 15, 15, 0, 1.0, [1.0, 1.0], True, True, True),
    "conditionalqa": (15, 15, 13, 1, 0.826, [0.4878, 1.0], True, False, True),
    "multihoprag": (15, 15, 12, 3, 0.3284, [0.0, 1.0], False, False, False),
}


def paired_rows(record):
    result = {"Pooled M1 bad": record["primary"]["bad"]}
    for base in BASES[:2]:
        for metric in ("bad", "good"):
            result[f"{LABELS[base]} M1 {metric}"] = record["corpora"][base][metric]
    for base in BASES[:2]:
        result[f"{LABELS[base]} M2 agrees"] = record["corpora"][base]["m2"]["with_reference"][
            "agrees"
        ]
    for base in BASES[:2]:
        result[f"{LABELS[base]} M3 sent"] = record["corpora"][base]["m3"]["sent"]
    return result


def paired_line(label, row):
    a, b, c = (row["table"][key] for key in ("a", "b", "c"))
    interval = ", ".join(f"{100 * value:+.2f}" for value in row["read95"])
    return (
        f"| {label} | {a + b}/{row['n']} ({100 * row['v3']:.2f}%) | "
        f"{a + c}/{row['n']} ({100 * row['v4']:.2f}%) | {100 * row['difference']:+.2f} | "
        f"[{interval}] | {row['clusters']} | {str(row['detected']).lower()} | {row['direction']} |"
    )


def capsule_tables(record, baseline, exports):
    paired = paired_rows(record)
    lines = PAIRED_HEADER + [paired_line("Pooled M1 bad", paired["Pooled M1 bad"])]
    lines += PAIRED_HEADER + [
        paired_line(label, row) for label, row in paired.items() if label != "Pooled M1 bad"
    ]
    lines += [
        "| Base | Context pairs, n | Same | Lost | Gained | Empty package answers / n |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for base in BASES[:2]:
        corpus = record["corpora"][base]
        context, n = corpus["context_has_answer"], corpus["bad"]["n"]
        lines.append(
            f"| {LABELS[base]} | {n} | {context['same']} | {context['lost']} | {context['gained']} | {corpus['empty_answers']}/{n} |"
        )
    lines += [
        "| Bridge | Planned pairs | Agree / n | Two steps apart / n | Quadratic kappa | ci95 | Pass by kappa | Pass by agreement | Passed |",
        "|---|---:|---:|---:|---:|---|---|---|---|",
    ]
    for base in BASES:
        held = exports[base, "bridge"]["retest"]
        interval = ", ".join(f"{value:.4f}" for value in held["ci95"])
        flags = " | ".join(
            str(held[key]).lower() for key in ("passes_by_kappa", "passes_by_agreement", "passed")
        )
        lines.append(
            f"| {LABELS[base]} | {held['planned']} | {held['agree']}/{held['pairs']} | {held['two_steps_apart']}/{held['pairs']} | {held['quadratic_kappa']:.4f} | [{interval}] | {flags} |"
        )
    lines += [
        "| Base | Corpus manifest SHA-256 | Chunks report SHA-256 | Index receipt SHA-256 | Cases SHA-256 |",
        "|---|---|---|---|---|",
    ]
    for base in BASES:
        old = baseline["bases"][base]
        digests = [
            old["corpus"][key]
            for key in ("corpus.manifest.json", "chunks-report.json", "index/index-receipt.json")
        ]
        lines.append(
            f"| {LABELS[base]} | "
            + " | ".join(f"`{value}`" for value in [*digests, old["cases_sha256"]])
            + " |"
        )
    return lines


def capsule_numeric_prose(record, baseline, exports):
    corpora = record["corpora"]
    good = corpora["wixqa"]["good"]
    held = corpora["wixqa"]["answers"]["stand"]
    settings, env = held["settings"], held["environment"]
    route = baseline["bases"]["wixqa"]["old_judges"]["m1"]["route"]
    bridge = exports["multihoprag", "bridge"]["retest"]
    lines = [
        "# Stage 5: final external answers",
        "The registered decision reads only the pooled WixQA + ConditionalQA M1 bad share. MultiHop-RAG is advisory.",
        "The [registered spec](../specs/stage5-final-external.md) defines this decision.",
        f"Public files are in [the record directory](../../reports/stage4-final/stage5/{record['product_diff']['stage5_sha'][:7]}/).",
        f"WixQA's M1 good share falls, detected: {100 * good['v3']:.2f}% to {100 * good['v4']:.2f}% (n = {good['n']}).",
        f"The package at `{record['product_diff']['stage5_sha'][:7]}` answered the same question ids as stage 2.",
        f"The old side is V4 at `{baseline['bases']['wixqa']['old_code']}` for WixQA and ConditionalQA, and V3 at `{baseline['bases']['multihoprag']['old_code']}` for MultiHop-RAG.",
        "For MultiHop-RAG the comparison also includes the V3 to V4 prompt change.",
        "The reader's legacy v3/v4 fields mean old/new here. Shares use their paired n; changes and read95 are in percentage points.",
        "read95 spans the cluster and Newcombe intervals. A change is detected only when both intervals exclude zero in the same direction.",
        "## Paired M1, M2 and M3 reading",
        "M1 grades answers without references. M2 measures agreement with references, or a right decline without one.",
        "M3 measures deterministic gold coverage in sent context. The judge's context_has_answer is a separate reading.",
        # The run's dates and receipt commits are operator-supplied, not fields in record.json.
        "The Mac answered 100 questions per base on the package's own stand from 2026-10-31 14:21 UTC.",
        "Three receipts froze the judge plans before grading: `da0988a` (WixQA), `bd18bce` (ConditionalQA) and `42dcd1a` (MultiHop-RAG).",
        "The laptop judge graded every plan in foreground chunks from 2026-11-01 to 2026-11-02 UTC; no plan stopped, and every export exited 0.",
        "The registered read ran on 2026-11-02 and gave the same bytes as a dry read to a scratch path before it.",
    ]
    for base in BASES[:2]:
        m2, m3 = corpora[base]["m2"], corpora[base]["m3"]
        with_ref, without_ref = m2["with_reference"], m2["without_reference"]
        lines += [
            f"{LABELS[base]} M2: with reference {with_ref['pairs']}/{with_ref['questions']} paired, {with_ref['unpaired']['count']} unpaired; without reference {without_ref['pairs']}/{without_ref['questions']} paired, {without_ref['unpaired']['count']} unpaired, right declines old/new {without_ref['right']['v3']}/{without_ref['pairs']} and {without_ref['right']['v4']}/{without_ref['pairs']}.",
            f"{LABELS[base]} M3: {m3['reading']}; without gold {m3['without_gold']}/{len(corpora[base]['sent_cases'])}. Mean covered fraction old/new {m3['fraction_mean']['old']:.6f}/{m3['fraction_mean']['new']:.6f} (n = {m3['old_n']}).",
        ]
    lines += [
        "The bridge checks judge drift by re-grading kept stage 2 replies to the old requests.",
        f"MultiHop-RAG has enough pairs: {str(bridge['enough_pairs']).lower()} (n = {bridge['pairs']}). Its scale is {' / '.join(bridge['scale'])}.",
        f"All {bridge['two_steps_apart']}/{bridge['pairs']} two-step changes are bad to good (first grade, retest grade). There were {bridge['resamples_undefined']} undefined bootstrap resamples.",
        "MultiHop-RAG field agreement: "
        + "; ".join(
            f"{key} {bridge['field_agreement'][key]['agree']}/{bridge['field_agreement'][key]['of']}"
            for key in ("answers_question", "context_has_answer", "defect", "reference")
        )
        + ".",
        "The record retains a new, unpaired advisory M2 reading for MultiHop-RAG. It supplies no admitted old-versus-new result here.",
        f"One judge model graded both sides: `{route['model']}` at effort `{route['effort']}`. The bridge is a stability check, not a second judge.",
        f"STAGE5_SHA is `{record['product_diff']['stage5_sha']}`; item 6 is `{record['product_diff']['item6_sha']}`.",
        f"K {settings['retrieval_top_k']}, window {settings['ollama_context_window']:,}, input limit {held['input_limit']:,}, rerank top {settings['rerank_top_k']}; prompt `{held['prompt_id']}`.",
        f"The INT8 reranker runs in `{settings['reranker_runtime']}` from `{settings['reranker_onnx_path']}`.",
        f"The answer model is `{settings['ollama_model_name']}`; ONNX Runtime {env['ort_version']}, transformers {env['versions']['transformers']}.",
        f"Both offline flags are `{env['offline']['HF_HUB_OFFLINE']}`. The checked cache configuration has `cache-ram = 1024`.",
        # The read's interpreter is operator-supplied, not a field in record.json.
        "The operator reports that the laptop read used Python 3.11.13.",
        "The [artifact test](../../tests/test_stage5_final_artifact.py) pins every public file's SHA-256 and LF bytes, binds the baseline and receipts, and rebuilds the reading.",
        "The corpus and cases hashes below come from baseline.json and match each answer record's provenance.",
        "The test reuses saved M3 measurements. Repeating the context measurement itself needs private corpora and prompts.",
        f"Each base has {len(baseline['bases']['wixqa']['ids'])} questions; intervals account for clusters.",
        "No person graded anything (owner's decision D11).",
    ]
    return lines


def test_capsule_numbers_are_pinned_to_the_record(artifacts, tools):
    record, baseline = artifacts.record, artifacts.baseline
    for label, row in paired_rows(record).items():
        assert (
            tuple(
                row[key]
                for key in (
                    "n",
                    "v3",
                    "v4",
                    "difference",
                    "read95",
                    "clusters",
                    "detected",
                    "direction",
                )
            )
            == PAIRED_PRINT[label]
        )
        assert row["table"]["a"] + row["table"]["b"] == round(row["v3"] * row["n"])
        assert row["table"]["a"] + row["table"]["c"] == round(row["v4"] * row["n"])
    for base, context, without_ref, gold, means in (
        ("wixqa", (98, 1, 1, 0), (0, 0, 0), 0, ("0.631667", "0.631667")),
        ("conditionalqa", (97, 3, 0, 0), (20, 4, 5), 20, ("0.833676", "0.806369")),
    ):
        corpus = record["corpora"][base]
        assert (
            *(corpus["context_has_answer"][key] for key in ("same", "lost", "gained")),
            corpus["empty_answers"],
        ) == context
        m2, m3 = corpus["m2"], corpus["m3"]
        no_ref = m2["without_reference"]
        assert (no_ref["questions"], no_ref["right"]["v3"], no_ref["right"]["v4"]) == without_ref
        for group in ("with_reference", "without_reference"):
            assert m2[group]["pairs"] == m2[group]["questions"]
            assert m2[group]["unpaired"] == {"count": 0, "case_ids": []}
        assert m3["without_gold"] == gold
        assert tuple(f"{m3['fraction_mean'][side]:.6f}" for side in ("old", "new")) == means
    assert record["decision"] == {"outcome": "holds", "action": "publish the package's numbers"}
    assert record["corpora"]["multihoprag"]["reason"] == "NOT_EVIDENCE: bridge stability failed"
    assert all(
        len(baseline["bases"][base]["ids"]) == len(record["corpora"][base]["sent_cases"]) == 100
        for base in BASES
    )
    assert "cache-ram = 1024" in SPEC.read_text("utf-8")
    assert record["corpora"]["wixqa"]["answers"]["stand"]["cache_sha256"] == tools.common.CACHE
    for base in BASES:
        held = artifacts.exports[base, "bridge"]["retest"]
        assert (
            tuple(
                held[key]
                for key in (
                    "planned",
                    "pairs",
                    "agree",
                    "two_steps_apart",
                    "quadratic_kappa",
                    "ci95",
                    "passes_by_kappa",
                    "passes_by_agreement",
                    "passed",
                )
            )
            == BRIDGE_PRINT[base]
        )
    held = artifacts.exports["multihoprag", "bridge"]["retest"]
    assert held["enough_pairs"] is True and held["resamples_undefined"] == 90
    assert held["field_agreement"] == {
        "answers_question": {"agree": 15, "of": 15},
        "context_has_answer": {"agree": 15, "of": 15},
        "defect": {"agree": 14, "of": 15},
        "reference": {"agree": 0, "of": 0},
    }
    text = CAPSULE.read_text("utf-8")
    tables = capsule_tables(record, baseline, artifacts.exports)
    assert [line for line in text.splitlines() if line.startswith("|")] == tables
    expected = capsule_numeric_prose(record, baseline, artifacts.exports) + tables
    assert Counter(line for line in text.splitlines() if re.search(r"\d", line)) == Counter(
        line for line in expected if re.search(r"\d", line)
    )
    assert (
        f"The registered outcome is **{record['decision']['outcome']}**: **{record['decision']['action']}**."
        in text
    )
    assert (
        "This fall does not enter the registered decision. It is the main caveat of this record and a reason to examine WixQA's good answers in the next stage."
        in text
    )
    assert text.index("WixQA's M1 good share falls, detected") < text.index("## What was compared")
    assert (
        f"**{record['corpora']['multihoprag']['status']}**: `{record['corpora']['multihoprag']['reason']}`."
        in text
    )
    route = artifacts.exports["wixqa", "m1"]["provenance"]["route"]
    assert (
        f"One judge model graded both sides: `{route['model']}` at effort `{route['effort']}`. The bridge is a stability check, not a second judge."
        in text
    )
    assert '"Not detected" does not mean "no difference".' in text

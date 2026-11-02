"""Read the committed V6 public record again; missing files fail, never skip.

The Mac has public exports, not the private replay/judge directories. Therefore
build() itself cannot run: run_hashes() needs every batch file and COMPLETE;
shown_gate() needs raw answers, questions, saved shown replies and chunk timelines
to rederive guards, fallback selection, release/cut times and shown-text hashes.
admitted() additionally needs private plans for their hashes/request counts,
bridge seed verdict bytes, and reference bytes. export_gate() needs those plans,
verdict journals, _vouched admission and NOT_EVIDENCE markers to rederive status,
planned fields, grades, retest field agreement and private provenance hashes.

Repeat their public checks below, including registration, committed bytes,
receipt/export bindings, summary_gate(), old_export(), public classifications,
retest stability, compare(), plan_summary(), pooled reads, counted(), decision().
Replay measurements, private admission and retest field agreement remain saved
observations pinned by file hashes, not independently remeasured facts. No corpus
aggregate is copied from reading-final to make the reconstruction pass.
Stored Unicode versions are checked against registration, not the Mac's current
runtime: this read neither generates nor applies the shown-text function.

The reading used Python 3.11.13; Python 3.12+ compensates float sums. Only kappa
(which sums floating weights) allows pytest.approx(rel=0, abs=1e-12). Corpus,
timing, paired intervals, counts, plan summaries and decisions compare exactly.
"""

import hashlib
import importlib.util
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "reports/answer-prompt-v6"
TOOLS = PUBLIC / "tools"
RECORDS = PUBLIC / "2057ad0"
FINAL = PUBLIC / "reading-final.json"
SPEC = ROOT / "docs/specs/answer-prompt-v6.md"
CAPSULE = ROOT / "docs/evidence/answer-prompt-v6-record.md"
SPEC_SHA = "2ea4da508c4812e0fe38ffac2a6d0fc04ee6ecbafa877fbc75a7d14f52983fce"
BASES = ("wixqa", "conditionalqa")
LABELS = {"wixqa": "WixQA", "conditionalqa": "ConditionalQA"}
FILES = {
    "2057ad0/plans-conditionalqa.json": "a6a954048f5f009aa78dbbdc690aab56379a51304534db49863ea81303051d47",
    "2057ad0/plans-wixqa.json": "4c7223e61cdec45468f6fde85f52748f44cd4dbc14673a742070c554f5dd96dc",
    "2057ad0/reading-conditionalqa-after-bridge.json": "a2289db16714ba725d386cf79b8bfc2a09fb8659bf5ba0d676ec507851944832",
    "2057ad0/reading-conditionalqa-after-m2.json": "1de6177bb507e97d5790e16ea58646aa15502a5099ebb04b2c2dbc630a05f504",
    "2057ad0/reading-wixqa-after-bridge.json": "80317b762fcad5719385f279f8c27c8a6b283b2613cb573eb18bdbb48ad543b3",
    "2057ad0/reading-wixqa-after-m2.json": "e4b6520c68c283ef8681eda4f0ddae47cd55ddb6d541720636142abdc716a962",
    "2057ad0/v6-bridge-conditionalqa.json": "991b5342bf71ac824018eb6152083efd77a21e186da94f9afd8a2527e5e01ce0",
    "2057ad0/v6-bridge-wixqa.json": "57126b79c3fdcdf407fc8fdb93f32b8e3d6913282a81dc5cae7ec9ca02e327a3",
    "2057ad0/v6-conditionalqa-judge-m1.cases.jsonl": "e4a381eef4f67b7a4013c42f12f3c8d5d16b4b501ac4efa371ba251ef1678eb3",
    "2057ad0/v6-conditionalqa-judge-m1.json": "b30fec2ac67b3f4630a8a5653dfe15762bf3023907e5a10801dc94fe907d725f",
    "2057ad0/v6-conditionalqa-judge-m2.cases.jsonl": "faa41078487b474bf802b7b76ea2d1a3b3e2593507e4e6bd7bbc1b2798c29e8b",
    "2057ad0/v6-conditionalqa-judge-m2.json": "38873e3c9fb01e2a14b81e4ad2aad1d9c607f6e7caf1ca83dddf56653fca6e51",
    "2057ad0/v6-conditionalqa.json": "18c4651fd698c8d606daa47a8671c665825f4be556466e1f719898599fdec0f1",
    "2057ad0/v6-wixqa-judge-m1.cases.jsonl": "86efbe4cf67e0cb50a2fa968da10481568bcf960d7ddf772bb04e31bf0be368e",
    "2057ad0/v6-wixqa-judge-m1.json": "269d2177d87bee8c762b24bca18277f5575e04869e1a7e6e80c289bf8259a68f",
    "2057ad0/v6-wixqa-judge-m2.cases.jsonl": "7f963b34114d294ca9a8e29e2ed651ad638acf06f17e34039cfdd1380a7ba4ab",
    "2057ad0/v6-wixqa-judge-m2.json": "fffb043804d668ba66b640771e2114f5c090f25401c852897b9ee6a889f3eaac",
    "2057ad0/v6-wixqa.json": "e7dea3aa50383a26aefeb3515df38bb50e4d8db78883c321d0af33e3e8552a95",
    "reading-final.json": "1de6177bb507e97d5790e16ea58646aa15502a5099ebb04b2c2dbc630a05f504",
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recorded_path(value):
    path = PureWindowsPath(value)
    assert not path.drive and not path.root and ".." not in path.parts
    assert path.parts[0] == "reports"
    return ROOT.joinpath(*path.parts)


@pytest.fixture(scope="module")
def record():
    return read(FINAL)


@pytest.fixture(scope="module")
def tools():
    # Frozen imports bind generic names (including common); restore all report
    # modules they replace/add, as well as sys.path and the product-root override.
    before_path, before_modules = sys.path[:], sys.modules.copy()
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("V6_PRODUCT_ROOT", str(ROOT))
        sys.path.insert(0, str(TOOLS))
        modules = {}
        try:
            for name in ("shown_text", "v6_common", "v6_replay", "v6_judge", "v6_record"):
                spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
                assert spec and spec.loader
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
                modules[name] = module
            yield SimpleNamespace(**modules)
        finally:
            sys.path[:] = before_path
            for name, module in tuple(sys.modules.items()):
                source = getattr(module, "__file__", None)
                if source and Path(source).resolve().is_relative_to(ROOT / "reports"):
                    if name in before_modules:
                        sys.modules[name] = before_modules[name]
                    else:
                        del sys.modules[name]


def test_public_bytes_registration_and_provenance(record, tools):
    common = tools.v6_common
    expected = {"reading-final.json"}
    for key in BASES:
        expected |= {
            f"2057ad0/{name}"
            for name in (
                f"plans-{key}.json",
                f"v6-{key}.json",
                f"v6-bridge-{key}.json",
                f"reading-{key}-after-bridge.json",
                f"reading-{key}-after-m2.json",
                f"v6-{key}-judge-m1.json",
                f"v6-{key}-judge-m1.cases.jsonl",
                f"v6-{key}-judge-m2.json",
                f"v6-{key}-judge-m2.cases.jsonl",
            )
        }
    assert set(FILES) == expected
    for name, digest in FILES.items():
        path = PUBLIC / name
        data = path.read_bytes()
        assert sha(path) == digest, name
        assert data.endswith(b"\n") and b"\r" not in data and not data.startswith(b"\xef\xbb\xbf")
        data.decode("utf-8")
        common.protocol.committed(path)
    assert FINAL.read_bytes() == (RECORDS / "reading-conditionalqa-after-m2.json").read_bytes()
    assert record["spec_sha256"] == sha(SPEC) == SPEC_SHA
    assert common.registration(SPEC) == SPEC_SHA
    common.protocol.committed(SPEC)
    registered = common.pins(SPEC)
    assert record["tools"] == common.tool_hashes()
    for name, digest in record["tools"].items():
        assert digest == sha(TOOLS / name) == registered[f"reports/answer-prompt-v6/tools/{name}"]
    assert record["keys"] == list(BASES)
    assert record["stands"] == {key: common.STANDS[key] for key in record["keys"]}
    assert record["stands"] == dict.fromkeys(BASES, RECORDS.name)
    for value, digest in record["inputs"].items():
        path = recorded_path(value)
        assert sha(path) == digest, value
        common.protocol.committed(path)


def check_stability(exported, exporter):
    from scripts.chat_answer_judge import quadratic_kappa

    held = exported["retest"]
    pairs, scale = held["pairs_list"], held["scale"]
    assert scale == ["bad", "partial_ok", "good"]
    assert held["planned"] == held["pairs"] == len(pairs) == len(set(held["pairs_ids"]))
    assert all(len(pair) == 2 and all(v in range(len(scale)) for v in pair) for pair in pairs)
    assert held["agree"] == sum(a == b for a, b in pairs)
    assert held["two_steps_apart"] == sum(abs(a - b) >= 2 for a, b in pairs)
    kappa = quadratic_kappa(pairs, len(scale))
    if kappa is None:
        assert held["quadratic_kappa"] is None
    else:
        assert held["quadratic_kappa"] == pytest.approx(kappa, rel=0, abs=1e-12)
    assert {k: held[k] for k in ("ci95", "resamples_undefined")} == exporter.kappa_interval(
        pairs, len(scale)
    )
    assert held["passes_by_kappa"] == (kappa is not None and kappa >= exporter.KAPPA)
    assert held["passes_by_agreement"] == (
        len(pairs) > 0
        and held["agree"] * exporter.OF >= exporter.AGREE * len(pairs)
        and held["two_steps_apart"] == 0
    )
    assert held["enough_pairs"] == (len(pairs) >= exporter.MIN_PAIRS)
    assert held["passed"] == (
        held["enough_pairs"] and (held["passes_by_kappa"] or held["passes_by_agreement"])
    )
    assert held["passed"] is True and exported["status"] == "counted"
    assert not exported.get("request_duration_stop", False)


def public_receipt(key, pin, summary, common):
    assert pin["key"] == key and pin["spec"] == SPEC.relative_to(ROOT).as_posix()
    assert pin["spec_sha256"] == summary["spec_sha256"] == sha(SPEC)
    assert pin["tools"] == summary["tools"] == common.tool_hashes()
    assert pin["stand"] == summary["code_sha"]
    assert pin["stand"].startswith(common.STANDS[key])
    assert pin["prompt_template_sha256"] == sha(TOOLS / "qa_prompt_v6.txt")
    for versions in (pin, pin["replay_versions"], summary):
        assert {
            field: versions[field] for field in common.REGISTERED_VERSIONS
        } == common.REGISTERED_VERSIONS
    assert set(pin["plans"]) == set(pin["requests"]) == {"m1", "m2", "bridge"}
    assert set(pin["old"]) == {"m1", "m2"}
    assert pin["answer_files"][f"v6-{key}.json"] == sha(RECORDS / f"v6-{key}.json")
    assert "COMPLETE" in pin["answer_files"]


def public_export(key, metric, pin, exported, data, old_record, measured, common):
    from scripts import chat_answer_judge as judge

    exporter = common.final.frozen("export")
    p, old = exported["provenance"], old_record["provenance"]
    assert exported["base"] == key and exported["judge"] == "answers"
    assert exported["plan"] == common.plan_name(key, metric)
    assert p["plan_sha256"] == pin["plans"][metric]
    assert p["adapter_sha256"] == common.JUDGE_SHA
    assert p["tool_sha256"] == sha(Path(exporter.__file__))
    assert p["prompt_id"] == "QA_PROMPT_V5"
    for field in ("salt", "instructions_sha256", "route", "references_sha256", "reading"):
        assert p.get(field) == old.get(field), (key, metric, field)
    assert p["references_sha256"] == pin["references_sha256"]
    assert p["references_withheld"] is (metric == "m1")
    assert exported["questions"] == len(data) == len(measured)
    assert exported["missing"] == sorted(c for c, row in data.items() if row["missing"]) == []
    assert exported["requests_valid"] == pin["requests"][metric]
    assert (
        exported["requests_valid"]
        == sum(not row.get("empty_answer") for row in data.values()) + exported["retest"]["planned"]
    )
    assert exported["replies"]["models"] == {p["route"]["model"]: exported["requests_valid"]}
    assert set(p["runs"]) == {row["run"] for row in data.values()}
    for run in p["runs"].values():
        assert run["code_sha"] == pin["stand"]
        assert run["model_digest"] == common.final.MODEL_DIGEST
        assert run["tenant"] == "ext_" + key
    for case, row in data.items():
        assert row["prompt_sha256"] == measured[case]["v6_prompt_sha256"]
        assert row["documents"] == measured[case]["documents_v6"]
        assert row["grade"] == ("bad" if row.get("empty_answer") else judge.classify(row))
        if metric == "m1":
            assert row["has_reference"] is False and row["reference"] == "none"
        else:
            assert row["m2"] == exporter.m2(row, row)
    check_stability(exported, exporter)


def check_public_measurements(measured):
    # Numeric/flag consistency from shown_gate is public; raw-text binding is not.
    for row in measured.values():
        fallback = bool(set(row["flags"]) & {"parse", "language"})
        assert row["fallback"] is fallback
        for field in ("v6_stream_sec", "total_sec", "package_stream_sec"):
            assert (
                isinstance(row[field], (int, float))
                and math.isfinite(row[field])
                and row[field] >= 0
            )
        assert row["v6_stream_sec"] <= 3600
        assert (row["fallback_stream_sec"] is not None) is fallback
        if fallback:
            assert (
                math.isfinite(row["fallback_stream_sec"])
                and 0 <= row["fallback_stream_sec"] <= 3600
            )
        # Preserve the registered gate's arithmetic bound, not a record tolerance.
        assert (
            abs(row["total_sec"] - row["v6_stream_sec"] - (row["fallback_stream_sec"] or 0)) < 1e-6
        )


def test_read_again_from_committed_public_files(record, tools):
    common, reader = tools.v6_common, tools.v6_record
    v4, v5 = reader.v4, common.v5_record
    inputs, corpora, plans, not_counted, readable = {}, {}, {}, {}, []
    pooled, same, recall = ({}, {}, {}), ({}, {}, {}), ({}, {}, {})
    m2_counted = True

    def remember(path):
        common.protocol.committed(path)
        inputs[path.relative_to(ROOT).as_posix()] = sha(path)
        return path

    for key in record["keys"]:
        pin = read(remember(RECORDS / f"plans-{key}.json"))
        summary = read(remember(RECORDS / f"v6-{key}.json"))
        public_receipt(key, pin, summary, common)
        measured = reader.summary_gate(summary, key)
        check_public_measurements(measured)
        loaded = {"package": {}, "v6": {}}
        exporter = common.final.frozen("export")
        for metric, held in pin["old"].items():
            old_path = remember(recorded_path(held["path"]))
            old_cases = remember(old_path.with_suffix(".cases.jsonl"))
            assert sha(old_path) == held["record_sha256"] and sha(old_cases) == held["cases_sha256"]
            old_record, old_data = reader.old_export(old_path, key, metric)
            path = remember(RECORDS / (common.plan_name(key, metric) + ".json"))
            new_record = read(path)
            new_data = common.unique(rows(remember(path.with_suffix(".cases.jsonl"))))
            assert set(old_data) == set(new_data) == set(measured)
            assert all(
                old_data[c]["prompt_sha256"] == measured[c]["package_prompt_sha256"]
                for c in old_data
            )
            public_export(key, metric, pin, new_record, new_data, old_record, measured, common)
            check_stability(old_record, exporter)
            for side, exported, data in (
                ("package", old_record, old_data),
                ("v6", new_record, new_data),
            ):
                loaded[side][metric] = exported, data
                name = f"{side}-{key}-{metric}"
                plans[name] = v4.plan_summary(exported)
                if not reader.counted(exported, data):
                    not_counted.setdefault(key, []).append(name)
        name = common.plan_name(key, "bridge")
        bridge = read(remember(RECORDS / (name + ".json")))
        check_stability(bridge, exporter)
        assert bridge["plan_sha256"] == pin["plans"]["bridge"]
        old_m1 = loaded["package"]["m1"][0]
        for field in ("plan", "verdicts"):
            assert (
                bridge[f"source_{field}_sha256"]
                == pin["source"][field]
                == old_m1["provenance"][f"{field}_sha256"]
            )
        assert bridge["retest"]["planned"] == pin["requests"]["bridge"]
        assert bridge["retest"]["pairs_ids"] == [pair["first"] for pair in bridge["pairs"]]
        assert bridge["retest"]["pairs_ids"] == old_m1["retest"]["pairs_ids"]
        old_items = {row["item_id"]: row for row in loaded["package"]["m1"][1].values()}
        for pair, classes in zip(bridge["pairs"], bridge["retest"]["pairs_list"], strict=True):
            assert pair["copy"] == pair["first"] + "-retest"
            assert pair["old_cli"] in bridge["admitted_cli"]["old"]
            assert pair["new_cli"] in bridge["admitted_cli"]["new"]
            assert old_items[pair["first"]]["case_id"] == pair["case_id"]
            assert bridge["retest"]["scale"][classes[0]] == old_items[pair["first"]]["grade"]
        plans[name] = bridge
        if not reader.counted(bridge):
            not_counted.setdefault(key, []).append(name)
        if reader.counted(bridge) and all(reader.counted(*loaded[s]["m1"]) for s in loaded):
            readable.append(key)
        a, b = loaded["package"]["m1"][1], loaded["v6"]["m1"][1]
        numbers, pairs, context, families = reader.compare(key, a, b, measured)
        corpora[key] = numbers
        numbers["idle"] = summary["idle"]
        for into, cases in ((pooled, pairs), (same, context)):
            into[0].update(v4.indicator(key, cases, a, v4.is_bad))
            into[1].update(v4.indicator(key, cases, b, v4.is_bad))
            into[2].update({f"{key}:{c}": families[c] for c in cases})
        first, second = loaded["package"]["m2"][1], loaded["v6"]["m2"][1]
        assert all(
            first[c][f] == second[c][f] == a[c][f] for c in first for f in ("cluster", "stratum")
        )
        numbers["m2"], held = v5.m2(key, first, second, families)
        m2_counted = m2_counted and all(reader.counted(*loaded[s]["m2"]) for s in loaded)
        recall[0].update(v4.indicator(key, held, first, v5.agrees))
        recall[1].update(v4.indicator(key, held, second, v5.agrees))
        recall[2].update({f"{key}:{c}": families[c] for c in held})
    bases = [key for key in common.BASES if key in corpora]
    primary = {"keys": bases, **v5.pair(*pooled)}
    agreement = {"keys": bases, **v5.pair(*recall)}
    rebuilt = {
        "keys": [key for key in common.KEYS if key in corpora],
        "stands": {key: common.STANDS[key] for key in corpora},
        "inputs": inputs,
        "spec_sha256": sha(SPEC),
        "tools": common.tool_hashes(),
        "corpora": corpora,
        "plans": plans,
        "primary": primary,
        "same_context": {"keys": bases, **v5.pair(*same)},
        "recall": agreement,
        "decision": reader.decision(
            primary,
            agreement if bases == list(common.BASES) and m2_counted else None,
            corpora,
            list(corpora),
            readable,
            not_counted,
        ),
    }
    assert reader.renamed(rebuilt) == record


def test_registered_harm_decides_before_gain(record):
    assert record["decision"] == {
        "decision": "not adopted",
        "reasons": ["pooled: M2's agreement with the reference falls"],
        "harm": ["pooled: M2's agreement with the reference falls"],
        "not_counted": {},
        "not_run": ["aircargo"],
        "v6_replaces_package": False,
    }
    for name, n in (("recall", 180), ("primary", 200)):
        assert record[name]["n"] == n
        assert record[name]["detected"] is True and record[name]["direction"] == "falls"
    assert "aircargo" not in record["corpora"]


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


def test_every_public_v6_file_has_no_raw_text():
    from scripts.chat_answer_judge import REFERENCE

    paths = {PUBLIC / name for name in FILES}
    paths |= {
        p for p in PUBLIC.rglob("*") if p.suffix in {".json", ".jsonl"} and TOOLS not in p.parents
    }
    for path in sorted(paths):
        values = rows(path) if path.suffix == ".jsonl" else [read(path)]
        for index, value in enumerate(values):
            assert_no_raw_strings(value, REFERENCE, (path.relative_to(ROOT).as_posix(), index))


PAIRED_HEADER = [
    "| Metric | Package hits / n (share) | V6 hits / n (share) | Change, pp | read95, pp | Clusters | Detected | Direction |",
    "|---|---:|---:|---:|---|---:|---|---|",
]
TIMING_FIELDS = (
    "package_first_sec",
    "first_shown_sec",
    "full_buffer_sec",
    "package_stream_sec",
    "v6_stream_sec",
    "total_sec",
)


def paired_line(label, row):
    a, b, c = (row["table"][key] for key in ("a", "b", "c"))
    interval = ", ".join(f"{100 * value:+.2f}" for value in row["read95"])
    return (
        f"| {label} | {a + b}/{row['n']} ({100 * row['package']:.2f}%) | "
        f"{a + c}/{row['n']} ({100 * row['v6']:.2f}%) | {100 * row['difference']:+.2f} | "
        f"[{interval}] | {row['clusters']} | {str(row['detected']).lower()} | {row['direction']} |"
    )


def capsule_tables(record):
    corpora = record["corpora"]
    lines = PAIRED_HEADER + [paired_line("Pooled M2 agrees", record["recall"])]
    lines += PAIRED_HEADER + [paired_line("Pooled M1 bad", record["primary"])]
    for key in BASES:
        for metric in ("bad", "good"):
            lines.append(paired_line(f"{LABELS[key]} M1 {metric}", corpora[key][metric]))
    lines += [
        paired_line("Same-context pooled M1 bad", record["same_context"]),
        paired_line(
            "ConditionalQA unanswerable declines",
            corpora["conditionalqa"]["declines_without_answer"],
        ),
        "| Base | Wrong declines, package / n to V6 / n | Supported claims, package | Supported claims, V6 | Same contexts / n |",
        "|---|---|---|---|---:|",
    ]
    for key in BASES:
        c = corpora[key]
        claims = [
            f"{c['claims_supported'][s]['supported']}/{c['claims_supported'][s]['total']} ({100 * c['claims_supported'][s]['share']:.2f}%)"
            for s in ("package", "v6")
        ]
        lines.append(
            f"| {LABELS[key]} | {c['wrong_declines']['package']}/{c['pairs']} to {c['wrong_declines']['v6']}/{c['pairs']} | {' | '.join(claims)} | {c['same_context']}/{c['answers']} |"
        )
    lines += [
        f"| Defect | WixQA package to V6 (n = {corpora['wixqa']['pairs']}) | ConditionalQA package to V6 (n = {corpora['conditionalqa']['pairs']}) |",
        "|---|---:|---:|",
    ]
    for defect in corpora["wixqa"]["defects"]["package"]:
        values = [
            f"{corpora[k]['defects']['package'][defect]} to {corpora[k]['defects']['v6'][defect]}"
            for k in BASES
        ]
        lines.append(f"| {defect} | {' | '.join(values)} |")
    lines += [
        "| Base | n | Parse | Repeat | Language | Language after release | Fallbacks | Prefix/whole disagreements |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in BASES:
        c = corpora[key]
        values = [
            c["answers"],
            *(c["guards"][k] for k in ("parse", "repeat", "language", "language_after_release")),
            c["fallbacks"],
            c["prefix_whole_disagreements"],
        ]
        lines.append(f"| {LABELS[key]} | " + " | ".join(map(str, values)) + " |")
    lines += [
        "| Base / batches | n | Package first | V6 first shown | Full buffer | Package whole | V6-only stream | Total with fallback |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in BASES:
        for group, label in (("all_batches", "all"), ("clean_batches", "clean")):
            timing = corpora[key]["timing"][group]
            n = timing["first_shown_sec"]["n"]
            assert all(timing[field]["n"] == n for field in TIMING_FIELDS)
            values = [f"{timing[f]['median']:.3f} / {timing[f]['p90']:.3f}" for f in TIMING_FIELDS]
            lines.append(f"| {LABELS[key]} / {label} | {n} | {' | '.join(values)} |")
    lines += ["| Bridge | Agree / n | Quadratic kappa | Status |", "|---|---:|---:|---|"]
    for key in BASES:
        bridge = record["plans"][f"v6-bridge-{key}"]
        held = bridge["retest"]
        lines.append(
            f"| {LABELS[key]} | {held['agree']}/{held['pairs']} | {held['quadratic_kappa']:.4f} | {bridge['status']} |"
        )
    return lines


def capsule_numeric_prose(record, route):
    # Dates, attempts, commit ids and interpreter are operator-supplied history;
    # row numbers, prompt versions and multiplicity limits come from the spec.
    # These are not invented reading-final fields; CX_REPORT maps the exceptions.
    corpora = record["corpora"]
    requests = {
        key: {
            m: sum(record["plans"][f"v6-{key}-{m}"]["admitted_cli"].values()) for m in ("m1", "m2")
        }
        for key in BASES
    }
    assert requests["wixqa"] == requests["conditionalqa"]
    assert corpora["wixqa"]["answers"] == corpora["conditionalqa"]["answers"]
    assert (
        record["plans"]["v6-bridge-wixqa"]["retest"]["planned"]
        == record["plans"]["v6-bridge-conditionalqa"]["retest"]["planned"]
    )
    assert all(corpora[key]["fallback_stream_sec"] is None for key in BASES)
    return [
        "# Stage 5b: answer V6 record",
        f"The registered outcome is row 1: **{record['decision']['decision']} — harm**.",
        "The [registered spec](../specs/answer-prompt-v6.md) reads harm first. The package stays.",
        "The deciding read is pooled M2 agreement with the reference. Detected harm wins over the pooled M1 gain by the registered order.",
        "V6 uses the owner's V1 answer prompt in V5's frame: evidence first, then the answer. The registered shown-text function hides the evidence from the user.",
        f"It was compared with the package's own shown answers on the same {corpora['wixqa']['answers']} question ids per key, WixQA and ConditionalQA. Retrieval was held; the package's contexts were fitted to the window.",
        "The [final reading](../../reports/answer-prompt-v6/reading-final.json) holds the public record. Differences are V6 minus package, in percentage points; read95 is the envelope of the paired Newcombe and cluster-bootstrap intervals.",
        "## The gain and the counts beside it",
        "M1 grades without references. The pooled bad-share fall is detected. WixQA's bad-share fall is detected; ConditionalQA's is not.",
        "ConditionalQA's declines on unanswerable questions rise. These are right declines; row 1 guards against their fall. This rise is not harm.",
        "The same-context subset does not replace the primary reading. Wrong declines are declines where the judge finds an answer in the context. These counts do not establish a cause for the M2 fall.",
        "## Timing",
        "Each timing cell is median / p90 seconds, with its n. All batches and clean batches are shown separately.",
        "V6-only stream time is not a latency claim. First-shown time and fallback-inclusive totals sit beside it. Full buffer is the observed answer-part end, or fallback first shown on the same clock.",
        f"Fallback stream spreads are absent: WixQA {corpora['wixqa']['fallbacks']}/{corpora['wixqa']['answers']}, ConditionalQA {corpora['conditionalqa']['fallbacks']}/{corpora['conditionalqa']['answers']} fallbacks. Batch idle readings remain in the public record.",
        "## Bridges and execution",
        f"The laptop judge used `{route['model']}`, effort `{route['effort']}`, tools `{route['tools']}`, on the frozen stage 5 isolated route. A bridge re-grades kept package replies to check judge drift; it is not another judge.",
        f"For each key the order was M1 ({requests['wixqa']['m1']} requests), bridge ({record['plans']['v6-bridge-wixqa']['retest']['planned']} new re-grades), then M2 ({requests['wixqa']['m2']} requests), in foreground chunks. No plan stopped. Every plan and bridge counts.",
        "Operator history, 2026-11-02 UTC: attempt-02 began at 02:22; WixQA and ConditionalQA completed. Receipts froze their plans before grading: `d15fa87` (WixQA), `a7202e4` (ConditionalQA).",
        "aircargo is **NOT_EVIDENCE**, not answered whole; it is `not_run`, with no receipt, grade or public file.",
        "aircargo attempt-02 ended in its first batch on the owner's external stop at 10:22:58. attempt-03 refused in preflight before any request because the model server was down.",
        "aircargo attempt-04 began at 14:17 after restarting the same Ollama 0.33.2 with the same model digest. The judge's harm STOP ended it at 17:18. The spec requires detected harm to decide without later keys.",
        "## Provenance and limits",
        f"Both recorded stands are `{record['stands']['wixqa']}`. Registration: `9f968bb`; amendment 1: `4a5c36e`.",
        f"Spec SHA-256: `{record['spec_sha256']}`.",
        "The operator reports the final reader ran on the laptop in the focused venv with Python 3.11.13 and exited 2 for detected harm.",
        "The final reading is byte-identical to `2057ad0/reading-conditionalqa-after-m2.json`. The other per-key readings are earlier partial readings, each with its own hash.",
        "The [artifact test](../../tests/test_answer_prompt_v6_record_artifact.py) pins public file hashes and LF bytes, verifies the registered tool hashes, and rebuilds the public reading. Its docstring names the private replay and admission checks it cannot repeat.",
        "The spec has nine one-sided harm reads: the union-bound false-harm probability is up to 22.5%. This is a conservative selection rule, not multiplicity-adjusted confirmatory inference.",
        "No person graded anything (owner's decision D11). Author and judge share one model family (D12).",
    ]


def test_every_capsule_number_is_pinned(record):
    tables = capsule_tables(record)
    assert tables == PRINTED_TABLES
    route = read(RECORDS / "v6-wixqa-judge-m1.json")["provenance"]["route"]
    assert (route["model"], route["effort"], route["tools"]) == ("claude-opus-5-5", "max", "none")
    text = CAPSULE.read_text(encoding="utf-8")
    assert [line for line in text.splitlines() if line.startswith("|")] == tables
    expected = capsule_numeric_prose(record, route) + tables
    # Count complete lines, including headings/links: any added numeric claim fails.
    assert Counter(line for line in text.splitlines() if re.search(r"\d", line)) == Counter(
        line for line in expected if re.search(r"\d", line)
    )
    for line in capsule_numeric_prose(record, route):
        assert line in text
    for line in (
        "One unseeded generation per side, in-sample, one judge; policy fallbacks were allowed.",
        '"Not detected" does not mean "no difference".',
        "The package stays. The next quality step is the generator pilot.",
    ):
        assert line in text
    assert text.index("Pooled M2 agrees") < text.index("## What was compared")


# Only the capsule's printed numbers are pinned; all other values are rebuilt.
PRINTED_TABLES = """\
| Metric | Package hits / n (share) | V6 hits / n (share) | Change, pp | read95, pp | Clusters | Detected | Direction |
|---|---:|---:|---:|---|---:|---|---|
| Pooled M2 agrees | 81/180 (45.00%) | 64/180 (35.56%) | -9.44 | [-16.48, -2.38] | 117 | true | falls |
| Metric | Package hits / n (share) | V6 hits / n (share) | Change, pp | read95, pp | Clusters | Detected | Direction |
|---|---:|---:|---:|---|---:|---|---|
| Pooled M1 bad | 112/200 (56.00%) | 85/200 (42.50%) | -13.50 | [-22.68, -4.57] | 137 | true | falls |
| WixQA M1 bad | 59/100 (59.00%) | 42/100 (42.00%) | -17.00 | [-31.36, -2.22] | 77 | true | falls |
| WixQA M1 good | 30/100 (30.00%) | 32/100 (32.00%) | +2.00 | [-10.78, +14.42] | 77 | false | not detected |
| ConditionalQA M1 bad | 53/100 (53.00%) | 43/100 (43.00%) | -10.00 | [-20.83, +0.96] | 60 | false | not detected |
| ConditionalQA M1 good | 38/100 (38.00%) | 41/100 (41.00%) | +3.00 | [-6.49, +12.50] | 60 | false | not detected |
| Same-context pooled M1 bad | 49/95 (51.58%) | 40/95 (42.11%) | -9.47 | [-20.56, +2.04] | 79 | false | not detected |
| ConditionalQA unanswerable declines | 5/20 (25.00%) | 10/20 (50.00%) | +25.00 | [+3.19, +45.00] | 20 | true | rises |
| Base | Wrong declines, package / n to V6 / n | Supported claims, package | Supported claims, V6 | Same contexts / n |
|---|---|---|---|---:|
| WixQA | 18/100 to 36/100 | 453/512 (88.48%) | 228/240 (95.00%) | 46/100 |
| ConditionalQA | 7/100 to 16/100 | 314/384 (81.77%) | 195/225 (86.67%) | 49/100 |
| Defect | WixQA package to V6 (n = 100) | ConditionalQA package to V6 (n = 100) |
|---|---:|---:|
| empty | 0 to 0 | 0 to 0 |
| citation_only | 0 to 0 | 0 to 0 |
| wrong_language | 0 to 0 | 0 to 0 |
| copied_context | 0 to 0 | 0 to 0 |
| cut_off | 0 to 0 | 0 to 0 |
| repetition | 0 to 0 | 2 to 1 |
| other | 0 to 0 | 4 to 6 |
| Base | n | Parse | Repeat | Language | Language after release | Fallbacks | Prefix/whole disagreements |
|---|---:|---:|---:|---:|---:|---:|---:|
| WixQA | 100 | 0 | 0 | 0 | 0 | 0 | 0 |
| ConditionalQA | 100 | 0 | 0 | 0 | 0 | 0 | 0 |
| Base / batches | n | Package first | V6 first shown | Full buffer | Package whole | V6-only stream | Total with fallback |
|---|---:|---:|---:|---:|---:|---:|---:|
| WixQA / all | 100 | 52.547 / 74.115 | 54.563 / 71.880 | 59.462 / 80.349 | 79.735 / 149.661 | 59.466 / 80.355 | 59.466 / 80.355 |
| WixQA / clean | 100 | 52.547 / 74.115 | 54.563 / 71.880 | 59.462 / 80.349 | 79.735 / 149.661 | 59.466 / 80.355 | 59.466 / 80.355 |
| ConditionalQA / all | 100 | 52.365 / 68.419 | 58.314 / 102.237 | 65.864 / 105.409 | 83.276 / 149.335 | 65.870 / 105.413 | 65.870 / 105.413 |
| ConditionalQA / clean | 90 | 52.164 / 70.334 | 57.208 / 74.463 | 63.265 / 83.911 | 82.724 / 148.416 | 63.270 / 83.918 | 63.270 / 83.918 |
| Bridge | Agree / n | Quadratic kappa | Status |
|---|---:|---:|---|
| WixQA | 14/15 | 0.9589 | counted |
| ConditionalQA | 13/15 | 0.8148 | counted |
""".splitlines()

"""Read the real final-aircargo artifacts again, without a model or private archive.

The full repository must supply V4's two published exports; their absence is a failure,
not a skip. Private launch/plan/reply bytes and operator clocks cannot be re-read here.
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
TOOLS = ROOT / "reports/stage4-final/tools"
RECORDS = ROOT / "reports/stage4-final/138f3b3"
SPEC = ROOT / "docs/specs/stage4-item6-final-aircargo.md"
CAPSULE = ROOT / "docs/evidence/stage4-item6-final-aircargo-record.md"
OLD = ROOT / "reports/answer-prompt-v4/4f48fed/v4-aircargo-judge.json"
QUESTIONS = ROOT / "evaluation/curated_cases_aircargo.jsonl"
CODE = "138f3b3f6ac223540965cc831838ff4f671a2200"
V4_CODE = "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1"
FILES = {
    "plans.json": "a6e25687506ec4cf5b87a81964c9225673ba07155e06fcc9fd699dbe42af7da1",
    "final-answers.json": "1e75d640d462dc908ef92ea61c2d570df1d5c89416da63b75d43d4c530b79a27",
    "final-aircargo-m1.json": "b652921bd3a988e0bb9cc3bef4ec52f07043f543194a8c52f6694f2471628c83",
    "final-aircargo-m1.cases.jsonl": "232d605eee10b65320f3a6a52a5dd3ecd3fb297d4c442b639329d1b8383e779a",
    "final-aircargo-bridge.json": "f7f09bd3e272e685e4c3df67351d191113c18c87504aa462daa746f7a482b53a",
    "quality.json": "e49e8560a766d58fdeda7c587be9cdfeb6138b24695107a113c16ac2b26f907c",
}


def read(path):
    return json.loads(path.read_text("utf-8"))


def rows(path):
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def tools(monkeypatch):
    # These CLI modules use sibling imports; restore the namespace after each test.
    monkeypatch.syspath_prepend(str(TOOLS))
    modules = {}
    for name in ("common", "stand", "record", "run"):
        spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        modules[name] = module
    return SimpleNamespace(**modules)


def recorded_path(value):
    # The laptop wrote Windows-relative keys. Path(value) alone is wrong on the Mac.
    path = PureWindowsPath(value)
    assert not path.drive and not path.root and ".." not in path.parts
    assert path.parts[0] == "reports"
    return ROOT.joinpath(*path.parts)


def test_the_six_public_files_and_quality_inputs_are_the_committed_bytes():
    for name, digest in FILES.items():
        data = (RECORDS / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, name
        assert data.endswith(b"\n") and b"\r" not in data, name
    quality = read(RECORDS / "quality.json")
    inputs = {recorded_path(key): value for key, value in quality["input_sha256"].items()}
    assert set(inputs) == {
        OLD,
        OLD.with_suffix(".cases.jsonl"),
        RECORDS / "final-aircargo-m1.json",
        RECORDS / "final-aircargo-m1.cases.jsonl",
        RECORDS / "final-aircargo-bridge.json",
    }
    assert len(inputs) == len(quality["input_sha256"])
    for path, digest in inputs.items():
        assert sha(path) == digest, path


def test_the_package_corpus_questions_and_tools_are_the_registered_stand(tools):
    answers = read(RECORDS / "final-answers.json")
    quality = read(RECORDS / "quality.json")
    held, provenance = answers["stand"], answers["provenance"]
    assert answers["status"] == quality["status"] == "counted"
    assert answers["base"] == quality["base"] == "aircargo"
    assert quality["stand"] == held and quality["provenance"] == provenance
    assert provenance["code_sha"] == CODE
    tools.record.stand_gate(held)
    assert held["settings"] == {**tools.common.SETTINGS, "reranker_onnx_path": tools.common.ONNX}
    assert (held["settings"]["retrieval_top_k"], held["settings"]["ollama_context_window"]) == (
        14,
        3584,
    )
    assert (held["settings"]["reranker_runtime"], held["settings"]["rerank_top_k"]) == ("onnx", 5)
    assert held["settings"]["ollama_model_name"] == "qwen3:4b-instruct-2507-q4_K_M"
    assert held["prompt_id"] == "QA_PROMPT_V4" and held["input_limit"] == 2176
    assert (
        held["export_sha256"] == "57335a9f061fe31378c160ddd0861711a0fbdfa20f70aa2640d473dfc4bc1343"
    )
    assert held["cache_sha256"] == tools.common.CACHE
    assert provenance["model_digest"] == held["model_digest"] == tools.common.MODEL_DIGEST
    env = held["environment"]
    assert env["executable"] == tools.common.PY
    assert env["offline"] == {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
    assert env["ort_version"] == env["versions"]["onnxruntime"] == "1.23.2"
    assert env["versions"]["transformers"] == "4.44.2"
    assert env["versions"]["tokenizers"] == "0.19.1"
    assert env["tokenizer_snapshot"] == "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
    assert env["ort_intra_op_num_threads"] == 0
    assert provenance["corpus_sha256"] == tools.run.aircargo_hashes()
    assert provenance["cases_sha256"] == sha(QUESTIONS)
    assert answers["runs"] == [f"final-answers-aircargo-b{n:02d}" for n in range(1, 11)]
    ids = [row["case_id"] for row in rows(QUESTIONS)]
    assert len(ids) == len(set(ids)) == len(answers["cases"]) == 100
    assert [row["case_id"] for row in answers["cases"]] == quality["pair_ids"] == ids
    assert Counter(row["run"] for row in answers["cases"]) == dict.fromkeys(answers["runs"], 10)
    for row in answers["cases"]:
        tools.record.case_gate(row)
    spec = SPEC.read_text("utf-8")
    assert "registered before the run" in spec
    assert "Registered in `ecc79dd`" in spec
    assert "cache-ram = 1024" in spec
    pins = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", spec))
    for name in ("common", "stand", "record", "run", "judge"):
        path = TOOLS / f"{name}.py"
        assert sha(path) == pins[path.relative_to(ROOT).as_posix()]


def test_the_receipt_binds_answers_plans_and_the_v4_bridge(tools):
    plans = read(RECORDS / "plans.json")
    answers = read(RECORDS / "final-answers.json")
    new = read(RECORDS / "final-aircargo-m1.json")
    bridge = read(RECORDS / "final-aircargo-bridge.json")
    old = read(OLD)
    assert plans["base"] == "aircargo"
    assert plans["inputs"]["corpus"] == answers["provenance"]["corpus_sha256"]
    assert plans["inputs"]["old_m1_sha256"] == sha(OLD)
    assert plans["plans"] == {
        "m1": new["provenance"]["plan_sha256"],
        "bridge": bridge["plan_sha256"],
    }
    assert plans["inputs"]["v4"] == {
        "plan": old["provenance"]["plan_sha256"],
        "verdicts": old["provenance"]["verdicts_sha256"],
    }
    assert bridge["source_plan_sha256"] == plans["inputs"]["v4"]["plan"]
    assert bridge["source_verdicts_sha256"] == plans["inputs"]["v4"]["verdicts"]
    # answers_sha256 holds private launch.json digests, not the public answer summary.
    assert list(plans["answers_sha256"]) == answers["runs"]
    assert all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in plans["answers_sha256"].values())
    assert plans["bridge_seed"] == {
        "bytes": 23263,
        "sha256": "d1e18bd157bf758837c1288f363d446228bab6fbef07fa8907d93bb6f7f1cf2a",
    }
    assert plans["requests"] == {"m1": new["requests_valid"], "bridge": bridge["retest"]["planned"]}
    assert plans["requests"] == {"m1": 115, "bridge": 15}
    assert new["questions"] == 100 and new["missing"] == []
    assert new["replies"]["statuses"] == {"valid": 115}
    assert new["replies"]["past_the_limit"] == 0
    for key in ("salt", "instructions_sha256", "route", "prompt_id"):
        assert new["provenance"][key] == old["provenance"][key], key
    for export, code in ((new, CODE), (old, V4_CODE)):
        assert {run["code_sha"] for run in export["provenance"]["runs"].values()} == {code}
    assert new["provenance"]["reading"]["commit"] == CODE
    assert new["provenance"]["reading"]["text"] == old["provenance"]["reading"]["text"]
    assert set(new["provenance"]["runs"]) == set(answers["runs"])
    # This gate also checks the current frozen request's salt, instructions and route.
    tools.record.judge_rows(RECORDS / "final-aircargo-m1.json", "aircargo", "answers")


def test_the_full_paired_reading_and_outcome_rebuild_with_the_committed_reader(tools):
    quality = read(RECORDS / "quality.json")
    rebuilt = tools.record.quality(
        "aircargo",
        read(RECORDS / "final-answers.json"),
        OLD,
        RECORDS / "final-aircargo-m1.json",
        RECORDS / "final-aircargo-bridge.json",
    )
    # The reader uses str(Path): normalize the laptop's keys, not the hashed file bytes.
    inputs = rebuilt.pop("input_sha256")
    expected = dict(quality)
    recorded = expected.pop("input_sha256")
    assert {Path(key): value for key, value in inputs.items()} == {
        recorded_path(key): value for key, value in recorded.items()
    }
    assert rebuilt == expected  # tables, v3/v4, both intervals, read95, direction and admission
    assert (
        quality["outcome"]
        == tools.record.outcome(quality["m1_bad"], quality["m1_good"], quality["m3"])
        == "gain detected"
    )
    assert quality["stage5"] == "follows"
    assert quality["m3_old_ceiling"]["hits"] == quality["m3_old_ceiling"]["n"] == 100


def test_bridge_stability_rebuilds_from_its_saved_pairs(tools):
    from scripts.chat_answer_judge import quadratic_kappa

    bridge = read(RECORDS / "final-aircargo-bridge.json")
    held = bridge["retest"]
    pairs = held["pairs_list"]
    export = tools.common.frozen("export")
    assert held["scale"] == ["bad", "partial_ok", "good"]
    assert held["pairs_ids"] == [pair["first"] for pair in bridge["pairs"]]
    assert held["planned"] == held["pairs"] == len(pairs) == len(bridge["pairs"]) == 15
    assert len(set(held["pairs_ids"])) == len(pairs)
    assert held["agree"] == sum(a == b for a, b in pairs) == 15
    assert held["two_steps_apart"] == sum(abs(a - b) >= 2 for a, b in pairs) == 0
    kappa = quadratic_kappa(pairs, len(held["scale"]))
    assert held["quadratic_kappa"] == kappa == 1.0
    interval = export.kappa_interval(pairs, len(held["scale"]))
    assert {key: held[key] for key in interval} == interval
    assert held["passes_by_kappa"] == (kappa is not None and kappa >= export.KAPPA)
    assert held["passes_by_agreement"] == (
        held["agree"] * export.OF >= export.AGREE * len(pairs) and held["two_steps_apart"] == 0
    )
    assert held["enough_pairs"] == (len(pairs) >= export.MIN_PAIRS)
    assert (
        held["passed"]
        == (held["enough_pairs"] and (held["passes_by_kappa"] or held["passes_by_agreement"]))
        is True
    )
    assert bridge["status"] == "counted"
    assert bridge == read(RECORDS / "quality.json")["bridge"]
    for pair in bridge["pairs"]:
        assert pair["copy"] == pair["first"] + "-retest"
        assert pair["old_cli"] in bridge["admitted_cli"]["old"]
        assert pair["new_cli"] in bridge["admitted_cli"]["new"]


def assert_no_raw_keys(value, allowed, trail=()):
    if isinstance(value, dict):
        for key, item in value.items():
            path = (*trail, key)
            if key.lower() in {
                "question",
                "answer",
                "text",
                "reference",
                "content",
                "query",
                "page_content",
            }:
                assert path in allowed and item == allowed[path], path
            assert_no_raw_keys(item, allowed, path)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            assert_no_raw_keys(item, allowed, (*trail, i))


def test_public_records_keep_only_schema_metadata_and_no_question_or_answer_text(tools):
    export = tools.common.frozen("export")
    from stage2_common import without_text

    queries = [row["query"] for row in rows(QUESTIONS)]
    handover = export.reading_text((ROOT / export.HANDOVER).read_text("utf-8"))
    for name in FILES:
        values = rows(RECORDS / name) if name.endswith(".jsonl") else [read(RECORDS / name)]
        for value in values:
            allowed = {}
            if name == "final-aircargo-m1.json":
                # Public instructions and the enum 'none' are not private corpus text.
                allowed[("provenance", "reading", "text")] = handover
                for run in read(RECORDS / "final-answers.json")["runs"]:
                    allowed[("per_run", run, "reference")] = {"none": 10}
            if name == "final-aircargo-m1.cases.jsonl":
                allowed[("reference",)] = "none"
            if name in ("final-aircargo-m1.json", "final-aircargo-bridge.json", "quality.json"):
                prefix = ("bridge",) if name == "quality.json" else ()
                allowed[(*prefix, "retest", "field_agreement", "reference")] = {"agree": 0, "of": 0}
            assert_no_raw_keys(value, allowed)
            # No source corpus is distributed here; actual public questions can be checked.
            assert without_text(value, set(), queries) == value


def test_the_capsule_tables_and_numeric_reading_are_the_records(tools):
    text = CAPSULE.read_text("utf-8")
    quality = read(RECORDS / "quality.json")
    answers = read(RECORDS / "final-answers.json")
    plans = read(RECORDS / "plans.json")
    judge = read(RECORDS / "final-aircargo-m1.json")
    expected = [
        "| Metric | V4 hits / n | Package hits / n | Change, pp | Cluster 95%, pp | Newcombe 95%, pp | Reading |",
        "|---|---:|---:|---:|---|---|---|",
    ]
    for key, label in (
        ("m1_good", "M1 good"),
        ("m1_bad", "M1 bad"),
        ("m3", "M3 context has answer"),
    ):
        row = quality[key]
        a, b, c = (row["table"][k] for k in ("a", "b", "c"))
        cluster = ", ".join(f"{100 * v:+.2f}" for v in row["cluster95"])
        newcombe = ", ".join(f"{100 * v:+.2f}" for v in row["newcombe95"])
        reading = (
            "gain detected"
            if key == "m1_good" and row["direction"] == "rises"
            else row["direction"]
        )
        expected.append(
            f"| {label} | {a + b}/{row['n']} | {a + c}/{row['n']} | {100 * row['difference']:+.2f} | "
            f"[{cluster}] | [{newcombe}] | {reading} |"
        )
    expected += ["| File | SHA-256 |", "|---|---|"]
    expected += [f"| `{name}` | `{digest}` |" for name, digest in FILES.items()]
    assert [line for line in text.splitlines() if line.startswith("|")] == expected
    held, env = answers["stand"], answers["stand"]["environment"]
    retest = quality["bridge"]["retest"]
    sentences = [
        f"The outcome is **{quality['outcome']}**; stage 5 {quality['stage5']}.",
        f"Stand `{answers['provenance']['code_sha']}` ran {len(answers['cases'])} aircargo questions in {len(answers['runs'])} batches of 10.",
        f"K {held['settings']['retrieval_top_k']}, window {held['settings']['ollama_context_window']:,}, input limit {held['input_limit']:,}, and the INT8 reranker kept {held['settings']['rerank_top_k']} chunks with the V4 prompt (`{held['prompt_id']}`).",
        f"The answer model was `{held['settings']['ollama_model_name']}`; Ollama was {held['ollama']}.",
        f"The service environment records transformers {env['versions']['transformers']}, tokenizers {env['versions']['tokenizers']}, and ONNX Runtime {env['ort_version']}.",
        f"Both offline flags were `{env['offline']['HF_HUB_OFFLINE']}`; the tokenizer snapshot was `{env['tokenizer_snapshot']}`.",
        f"The export SHA-256 was `{held['export_sha256']}`; the checked `cache-ram = 1024` file had SHA-256 `{held['cache_sha256']}`.",
        f"The judge had {judge['questions']} first grades and {judge['retest']['planned']} retests ({plans['requests']['m1']} requests), plus a {plans['requests']['bridge']}-request V4 bridge.",
        f"The route was `{judge['provenance']['route']['model']}` at effort `{judge['provenance']['route']['effort']}`; instructions and salt matched V4.",
        f"The bridge agreed on {retest['agree']} of {retest['pairs']} pairs; quadratic κ was {retest['quadratic_kappa']:.1f}, with interval [{retest['ci95'][0]:.1f}, {retest['ci95'][1]:.1f}].",
        f"Admitted CLI versions: V4 {next(iter(quality['admitted_cli']['old']))} ({sum(quality['admitted_cli']['old'].values())} requests), package {next(iter(quality['admitted_cli']['new']))} ({sum(quality['admitted_cli']['new'].values())} requests); the bridge used those respective versions.",
        f"M3's old side is at its ceiling, {quality['m3_old_ceiling']['hits']}/{quality['m3_old_ceiling']['n']}; only a detected fall could count as harm.",
    ]
    for sentence in sentences:
        assert sentence in text, sentence
    assert "../specs/stage4-item6-final-aircargo.md" in text
    assert "in `ecc79dd`, corrected\nin `138f3b3`" in text
    assert f"All {sum(plans['requests'].values())} replies were valid" in text
    assert (
        f"`{FILES['final-aircargo-m1.json'][:8]}…` / `{FILES['final-aircargo-m1.cases.jsonl'][:8]}…`"
        in text
    )
    spec = SPEC.read_text("utf-8")
    forecast = tools.common.forecast(100, 10)
    assert (
        f"The registered answer forecast was {forecast:,} s; its series stop was {3 * forecast:,} s."
        in text
    )
    assert f"{forecast:,} s" in spec and f"{3 * forecast:,} s" in spec
    mde = [round(100 * 2.8 * math.sqrt(d / len(answers["cases"]))) for d in (0.1, 0.2, 0.3)]
    assert mde == [9, 13, 15]
    assert (
        "MDE ≈ 2.8 sqrt(d/100): 9, 13, 15 pp at discordance 0.1, 0.2, 0.3; smaller changes remain unresolved."
        in text
    )
    assert "2.8 sqrt(d/100)" in spec and "9, 13, 15 percentage points" in spec
    # Timings, costs, transfer counts and chronology below are explicitly operator reports.
    assert "The orchestrator reports from private logs and journals" in text
    assert "These private counts and chronology are not reconstructed by the artifact test." in text
    assert "COPYFILE_DISABLE=1" in text and "CRLF to LF" in text
    assert "no yes/no from Julia is needed under the registered rule" in text

"""Re-read the committed idle-Mac speed cases, exact intervals and descriptive pairs.

Private observer logs and historical corpora are not distributed with these extracts.
Their receipt hashes are preserved; no model, Mac process or remote run is invoked.
"""

import hashlib
import importlib.util
import json
import math
import re
import statistics
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports/stage4-final/tools"
RECORDS = ROOT / "reports/stage4-final/138f3b3"
SPEC = ROOT / "docs/specs/stage4-item7-final-speed.md"
CAPSULE = ROOT / "docs/evidence/stage4-item7-final-speed-record.md"
QUESTIONS = ROOT / "evaluation/curated_cases_aircargo.jsonl"
CODE = "138f3b3f6ac223540965cc831838ff4f671a2200"
FILES = {
    "speed.json": "41cd1a602e08cf5a3a69d4bed35269b11164bf14b7caf9cdab7596e360c403ba",
    "baseline-19beeb1.json": "967f11c896d618594b34cefcae4b1c1644ee8490b02be0535bd2b2a4f53455d5",
    "baseline-item5.json": "41cc0df7762de7393187c50229983b80a880c29c8856ed5141d843fc03eca9a3",
}
TIME_NAMES = {
    "first_token_sec": "First word",
    "result_sec": "Whole answer",
    "total_sec": "Stream close including suggestions",
}


def read(path):
    return json.loads(path.read_text("utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sum_python311(values):
    # Python 3.12+ compensates float sums; the record was written on Python 3.11.
    total = 0
    for value in values:
        total += value
    return total


@pytest.fixture
def tools(monkeypatch):
    monkeypatch.syspath_prepend(str(TOOLS))
    modules = {}
    for name in ("common", "stand", "record", "run"):
        spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        modules[name] = module
    monkeypatch.setattr(modules["record"], "sum", sum_python311, raising=False)
    return SimpleNamespace(**modules)


def test_the_speed_and_baseline_files_are_the_copies_from_the_mac():
    for name, digest in FILES.items():
        data = (RECORDS / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, name
        assert data.endswith(b"\n") and b"\r" not in data, name


def test_the_stand_question_order_corpus_and_exclusive_run_are_bound(tools):
    speed = read(RECORDS / "speed.json")
    provenance = speed["provenance"]
    assert speed["status"] == "counted"
    assert provenance["exclusive_owned_work"] is True
    assert provenance["code_sha"] == CODE
    answers = read(RECORDS / "final-answers.json")
    assert provenance["stand"] == answers["stand"]
    tools.record.stand_gate(provenance["stand"])
    assert (
        provenance["corpus_sha256"]
        == answers["provenance"]["corpus_sha256"]
        == tools.run.aircargo_hashes()
    )
    assert provenance["cases_sha256"] == answers["provenance"]["cases_sha256"] == sha(QUESTIONS)
    ids = [json.loads(line)["case_id"] for line in QUESTIONS.read_text("utf-8").splitlines()][:30]
    assert [row["case_id"] for row in speed["cases"]] == ids
    assert len(ids) == len(set(ids)) == 30
    assert speed["attempts"] == speed["cases"]
    assert speed["reasked"] == tools.record.reask_ids(speed["attempts"]) == []
    assert tools.record.select_attempts(speed["attempts"], ids) == speed["cases"]
    for case in speed["cases"]:
        tools.record.case_gate(case)
        assert case["run"] == "final-speed-aircargo-b01" and case["disturbed"] == []
        memory = case["mac_memory"]
        assert memory["samples"] > 0
        assert all(
            memory[key] is not None and memory[key] >= 0
            for key in ("swap_mib", "llama_mem_mib", "llama_rss_mib")
        )
    for source, digest_key in (("19beeb1", "baseline_sha256"), ("item5", "item5_sha256")):
        path = RECORDS / f"baseline-{source}.json"
        old = read(path)
        assert provenance[digest_key] == sha(path)
        tools.record.baseline_gate(old, source, provenance["cases_sha256"])
        assert [row["case_id"] for row in old["cases"]] == ids
        assert all(re.fullmatch(r"[0-9a-f]{64}", value) for value in old["input_sha256"].values())
        # baseline.py does not export historical corpus hashes. Do not invent that binding.
        assert set(old) == {"source", "status", "cases_sha256", "input_sha256", "cases"}
    for key in ("launch_sha256", "samples_sha256", "resources_sha256"):
        assert re.fullmatch(r"[0-9a-f]{64}", provenance[key])
    spec = SPEC.read_text("utf-8")
    pins = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", spec))
    for name in ("common", "stand", "record", "run", "baseline"):
        path = TOOLS / f"{name}.py"
        assert sha(path) == pins[path.relative_to(ROOT).as_posix()]


def test_the_reader_rebuilds_all_speed_results_and_the_slo_proposals(tools):
    speed = read(RECORDS / "speed.json")
    old = read(RECORDS / "baseline-19beeb1.json")
    item5 = read(RECORDS / "baseline-item5.json")
    rebuilt = tools.record.speed_read(speed["cases"], old["cases"], item5["cases"])
    assert rebuilt == {
        key: value
        for key, value in speed.items()
        if key not in {"provenance", "attempts", "reasked"}
    }
    for key in TIME_NAMES:
        values = sorted(case[key] for case in speed["cases"])
        for name, p in (("median", 0.5), ("p90", 0.9)):
            held = speed["times"][key][name]
            assert held == tools.record.quantile(values, p)
            assert held["n"] == 30
            lower, upper = held["ranks"]
            assert held["ci95"] == [
                values[lower - 1],
                values[upper - 1] if upper <= len(values) else None,
            ]
            masses = [
                math.comb(len(values), k) * p**k * (1 - p) ** (len(values) - k)
                for k in range(len(values) + 1)
            ]
            assert held["coverage"] == sum_python311(masses[lower:upper])
            assert sum(masses[:lower]) <= 0.025 < sum(masses[: lower + 1])
            assert sum(masses[upper:]) <= 0.025 < sum(masses[upper - 1 :])
        assert speed["times"][key]["median"]["point"] == statistics.median(values)
        assert speed["times"][key]["median"]["ranks"] == [10, 21]
        assert speed["times"][key]["p90"]["point"] == values[math.ceil(0.9 * len(values)) - 1]
        assert speed["times"][key]["p90"]["ranks"] == [23, 31]
        assert speed["times"][key]["p90"]["ci95"][1] is None
    for key in ("first_token_sec", "result_sec"):
        assert speed["paired_19beeb1"][key] == tools.record.sign(
            {case["case_id"]: case[key] for case in old["cases"]},
            {case["case_id"]: case[key] for case in speed["cases"]},
        )
        assert speed["item5_descriptive"][key] == statistics.median(
            case[key] for case in item5["cases"]
        )
        assert (
            speed["slo_proposal_seconds"][key]
            == tools.record.slo(speed["times"][key]["p90"]["point"])
            == math.ceil(speed["times"][key]["p90"]["point"] / 30) * 30
        )
    assert speed["slo_proposal_seconds"] == {"first_token_sec": 270, "result_sec": 360}


def test_the_speed_extracts_hold_no_raw_question_answer_or_document_text(tools):
    tools.common.frozen("export")  # makes the frozen stage2_common available
    from stage2_common import without_text

    queries = [json.loads(line)["query"] for line in QUESTIONS.read_text("utf-8").splitlines()]

    def check(value):
        if isinstance(value, dict):
            for key, item in value.items():
                assert key.lower() not in {
                    "question",
                    "answer",
                    "text",
                    "reference",
                    "content",
                    "query",
                    "page_content",
                }
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)

    for name in FILES:
        value = read(RECORDS / name)
        check(value)
        assert without_text(value, set(), queries) == value


def test_every_capsule_table_and_numeric_result_is_the_saved_reading(tools):
    speed = read(RECORDS / "speed.json")
    old = read(RECORDS / "baseline-19beeb1.json")
    text = CAPSULE.read_text("utf-8")
    expected = [
        "| Time, seconds (n = 30) | Median | Exact 95% interval | Nearest-rank p90 | Exact 95% interval |",
        "|---|---:|---|---:|---|",
    ]
    for key, label in TIME_NAMES.items():
        median, p90 = (speed["times"][key][name] for name in ("median", "p90"))
        expected.append(
            f"| {label} | {median['point']:.4f} | [{median['ci95'][0]:.3f}, {median['ci95'][1]:.3f}] | "
            f"{p90['point']:.4f} | [{p90['ci95'][0]:.3f}, unbounded] |"
        )
    expected += [
        "| Time (n = 30 pairs) | Faster | Slower | Ties | Exact sign-test p | 19beeb1 median, s | Item 5 median, s |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key in ("first_token_sec", "result_sec"):
        pair = speed["paired_19beeb1"][key]
        before = statistics.median(case[key] for case in old["cases"])
        expected.append(
            f"| {TIME_NAMES[key]} | {pair['faster']} | {pair['slower']} | {pair['ties']} | "
            f"{pair['p_exact']:.12f} | {before:.4f} | {speed['item5_descriptive'][key]:.4f} |"
        )
    expected += ["| File | SHA-256 |", "|---|---|"]
    expected += [f"| `{name}` | `{digest}` |" for name, digest in FILES.items()]
    assert [line for line in text.splitlines() if line.startswith("|")] == expected
    median, p90 = (speed["times"]["result_sec"][name] for name in ("median", "p90"))
    sentences = [
        f"The record is **{speed['status']}**: {len(speed['cases'])} readable questions, {len(speed['reasked'])} re-asks, and no marked disturbance.",
        f"Stand `{speed['provenance']['code_sha']}` is the same stand as item 6.",
        f"The SLO proposals are **{speed['slo_proposal_seconds']['first_token_sec']} s to first word** and **{speed['slo_proposal_seconds']['result_sec']} s for the whole answer**.",
        f"Median interval ranks are {median['ranks'][0]} and {median['ranks'][1]}, with coverage {100 * median['coverage']:.6f}%.",
        f"The p90 point is order statistic {math.ceil(p90['n'] * p90['p'])}; interval ranks are {p90['ranks'][0]} and {p90['ranks'][1]}, with coverage {100 * p90['coverage']:.6f}%.",
        f"At n = {p90['n']}, rank {p90['ranks'][1]} is unbounded (`null` in the record); it is not the observed maximum.",
        f"Rule: ceil(p90 / 30) × 30 seconds. {speed['slo_owner']}.",
        "The comparison is " + speed["comparison"] + ".",
    ]
    for sentence in sentences:
        assert sentence in text, sentence
    assert "../specs/stage4-item7-final-speed.md" in text
    assert f"One Mac, one day, {len(speed['cases'])} questions." in text
    forecast = tools.common.forecast(30, 1, reasks=tools.common.MAX_REASK)
    assert (
        f"The registered forecast was {forecast:,} s; the series stop was {3 * forecast:,} s."
        in text
    )
    spec = SPEC.read_text("utf-8")
    assert f"{forecast:,} s" in spec and f"{3 * forecast:,} s" in spec
    assert "exclusive_owned_work=true" in text
    assert "The orchestrator reports from the private run log" in text
    assert (
        "These timestamps and wall duration are not reconstructed from the public extracts." in text
    )
    assert "Historical corpus digests are absent from both baseline extracts" in text

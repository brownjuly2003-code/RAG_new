"""Stage 2's 300 external answers, exported without corpus text on 2026-10-23."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import median

import pytest

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "reports/stage2/external-answers-20261023"
RETRIEVAL = ROOT / "reports/stage2/retrieval-20261021"
CODE = "5e308fe48cca0955c3007057a574a425f71e2a6a"
BASES = ("conditionalqa", "wixqa", "multihoprag")
ROUTES = {
    "conditionalqa": {"auto": 73, "human": 27},
    "wixqa": {"auto": 76, "human": 24},
    "multihoprag": {"auto": 67, "human": 33},
}
# Route by the registered stratum of part 2's rows: (stratum, has gold, route) -> questions.
STRATA = {
    "conditionalqa": {
        ("answerable", True, "auto"): 62,
        ("answerable", True, "human"): 18,
        ("not_answerable", False, "auto"): 11,
        ("not_answerable", False, "human"): 9,
    },
    "wixqa": {("simulated", True, "auto"): 76, ("simulated", True, "human"): 24},
    "multihoprag": {
        ("inference_query", True, "auto"): 57,
        ("inference_query", True, "human"): 13,
        ("null_query", False, "auto"): 10,
        ("null_query", False, "human"): 20,
    },
}
TOOLS = {
    "answers_summary.py": "reports/stage2/tools",
    "live_api.py": "reports/stage2/tools",
    "stage2.sh": "reports/stage2/tools",
    "stage2_cases.py": "reports/stage2/tools",
    "stage2_common.py": "reports/stage2/tools",
    "live_runner.py": "reports/stage1/tools",
    "live_supervisor.py": "reports/stage1/tools",
}


def load(folder, name):
    record = json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (folder / f"{name}.cases.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return record, rows


def test_export_bytes_are_pinned():
    manifest = json.loads((RECORD / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["code_sha"] == CODE
    assert set(manifest["files"]) == {
        f"{part}-{base}{suffix}"
        for part in ("p2", "p4")
        for base in BASES
        for suffix in (".json", ".cases.jsonl")
    }
    assert {path.name for path in RECORD.iterdir()} == {"manifest.json", *manifest["files"]}
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((RECORD / name).read_bytes()).hexdigest() == digest
    raw = manifest["private_raw"]
    assert raw["members"] == 1356
    assert len(raw["archive_sha256"]) == len(raw["raw_manifest_sha256"]) == 64


@pytest.mark.parametrize("base", BASES)
def test_every_registered_question_answered_once_in_ten_counted_batches(base):
    record, rows = load(RECORD, f"p4-{base}")
    _, retrieval = load(RECORD, f"p2-{base}")
    registered = [row["case_id"] for row in retrieval]
    aggregate, provenance = record["aggregate"], record["provenance"]
    assert len(set(registered)) == 100
    assert [row["case_id"] for row in rows] == registered
    assert [(row["batch"], row["index"]) for row in rows] == [
        (batch, index) for batch in range(1, 11) for index in range(1, 11)
    ]
    assert aggregate["registered"] == aggregate["measured"] == aggregate["answered"] == 100
    assert aggregate["missing"] == aggregate["out_of_place"] == []
    assert not aggregate["path_breaks"]
    labels = [f"p4-{base}-b{batch:02d}" for batch in range(1, 11)]
    assert [run["label"] for run in record["runs"]] == labels
    for batch, run in enumerate(record["runs"], start=1):
        launch = run["launch"]
        assert run["counted"] and not run["path_breaks"]
        assert launch["status"] == "complete" and launch["runner_exit"] == 0
        assert launch["error"] is None and launch["code_sha"] == CODE
        # A fresh API on an empty Ollama, the model unloaded after the batch.
        assert launch["ollama_models_before"] == [] and launch["api_killed"] is None
        assert launch["unloaded_models"] == ["qwen3:4b-instruct-2507-q4_K_M"]
        assert launch["client_cap_sec"] == "1020/1200"
        assert run["cases"] == registered[10 * (batch - 1) : 10 * batch]
        done = f"LIVE_DONE {run['label']} complete exit 0"
        assert sum(line.endswith(done) for line in record["driver_log"]) == 1
    assert provenance["code_sha"] == [CODE]
    assert provenance["model"] == ["qwen3:4b-instruct-2507-q4_K_M"]
    assert provenance["settings"] == record["runs"][0]["settings"]
    assert provenance["settings_sha256"] == sorted(
        hashlib.sha256(json.dumps(run["settings"], sort_keys=True).encode()).hexdigest()
        for run in record["runs"]
    )
    assert set(provenance["tools_sha256"]) == set(TOOLS)
    for name, folder in TOOLS.items():
        assert (
            hashlib.sha256((ROOT / folder / name).read_bytes()).hexdigest()
            == provenance["tools_sha256"][name]
        )
    for row in rows:
        assert row["http_status"] == 200 and row["answered"] and not row["path_breaks"]
        assert row["path"]["kind"] == "hybrid" and row["path"]["rerank_status"] == "ok"
        assert row["retrievals"] == 1 and row["reranker_ok"]


def test_all_30_batches_ran_one_configuration():
    """Settings differ between batches only by each run's own trace and index-copy paths."""
    per_run = ("tracing_db_path", "vectordb_chroma_dir")
    configurations = set()
    for base in BASES:
        record, _ = load(RECORD, f"p4-{base}")
        for run in record["runs"]:
            assert all(run["label"] in run["settings"][key] for key in per_run)
            shared = {key: value for key, value in run["settings"].items() if key not in per_run}
            configurations.add(json.dumps(shared, sort_keys=True))
        assert record["provenance"]["overrides"] == {
            "REQUEST_TIMEOUT_SEC": "3600",
            "OLLAMA_REQUEST_TIMEOUT_SEC": "3600",
            "STREAMING_TIMEOUT_SEC": "3600",
            "RAG_DEVICE": "cpu",
        }
    assert len(configurations) == 1


@pytest.mark.parametrize("base", BASES)
def test_aggregates_are_derived_from_the_rows(base):
    record, rows = load(RECORD, f"p4-{base}")
    aggregate = record["aggregate"]
    routes = Counter(row["route"] for row in rows)
    assert routes == aggregate["routes"] == ROUTES[base]
    # The chat routes to a person exactly when its self-score is below 80.
    assert all((row["route"] == "human") == (row["quality_score"] < 80) for row in rows)
    assert aggregate["quality_below_80"] == routes["human"]
    assert aggregate["quality_sources"] == {"llm": 100}
    assert aggregate["answer_script_vs_question"] == {"latin->latin": 100}
    assert all(row["answer_letters"]["cyrillic"] == 0 for row in rows)
    assert Counter(str(row["prompts"][0]["labels_source"]) for row in rows) == Counter(
        aggregate["prompt_labels"]
    )
    assert aggregate["marks_past_labels"] == 0
    for name, group in (
        ("first_of_batch", [row for row in rows if row["index"] == 1]),
        ("rest", [row for row in rows if row["index"] > 1]),
    ):
        for key in ("total_sec", "first_token_sec"):
            spread = aggregate["times"][name][key]
            values = [row[key] for row in group]
            assert spread["n"] == len(values) == (10 if name == "first_of_batch" else 90)
            assert spread["median"] == round(median(values), 3)
            assert spread["max"] == max(values)
    assert aggregate["swap_used_mb_max"] == max(row["memory"]["swap_used_mb"][1] for row in rows)


@pytest.mark.parametrize("base", BASES)
def test_answer_prompts_are_the_retrieval_prompts_of_part_2(base):
    retrieval, rows = load(RECORD, f"p2-{base}")
    _, answers = load(RECORD, f"p4-{base}")
    by_id = {row["case_id"]: row for row in answers}
    assert retrieval["aggregate"]["parity"] == {"True": 100}
    for row in rows:
        assert row["answer_prompt_same"] is True
        assert row["prompt"]["sha256"] == by_id[row["case_id"]]["prompts"][0]["sha256"]


@pytest.mark.parametrize("base", BASES)
def test_part_2_numbers_are_unchanged_by_the_rewrite_after_the_answers(base):
    before, before_rows = load(RETRIEVAL, f"p2-{base}")
    after, after_rows = load(RECORD, f"p2-{base}")
    assert "parity" not in before["aggregate"]
    assert after["aggregate"].pop("parity") == {"True": 100}
    assert before == after
    for old, new in zip(before_rows, after_rows, strict=True):
        assert old.pop("answer_prompt_same") is None
        assert new.pop("answer_prompt_same") is True
        assert old == new


@pytest.mark.parametrize("base", BASES)
def test_route_by_registered_stratum(base):
    _, retrieval = load(RECORD, f"p2-{base}")
    _, answers = load(RECORD, f"p4-{base}")
    route = {row["case_id"]: row["route"] for row in answers}
    assert (
        Counter((row["stratum"], bool(row["gold"]), route[row["case_id"]]) for row in retrieval)
        == STRATA[base]
    )


def test_all_300_answers_in_the_questions_language_and_their_times():
    # Median total and first-token seconds per base, as the capsule's table gives them.
    medians = {
        "conditionalqa": (253.1, 168.8),
        "wixqa": (256.4, 165.1),
        "multihoprag": (275.0, 180.2),
    }
    for base, (total, first) in medians.items():
        rows = load(RECORD, f"p4-{base}")[1]
        assert round(median(row["total_sec"] for row in rows), 1) == total
        assert round(median(row["first_token_sec"] for row in rows), 1) == first
    rows = [row for base in BASES for row in load(RECORD, f"p4-{base}")[1]]
    assert len(rows) == len({row["case_id"] for row in rows}) == 300
    assert sum(row["route"] == "human" for row in rows) == 84
    assert all(row["question_letters"]["latin"] > 0 for row in rows)
    assert all(row["answer_letters"]["cyrillic"] == 0 for row in rows)
    totals = [row["total_sec"] for row in rows]
    assert round(median(totals), 1) == 266.9
    assert max(totals) == 719.301 < 1020
    assert round(median(row["first_token_sec"] for row in rows), 1) == 173.1

"""reports/stage4-step3/tools/step3_reader.py: the runs' gates, the pairs and the readings.

docs/specs/stage4-step3-k-timing.md. Synthetic fixtures only: every number, path and text in
them is made up. The run files copy the shapes the drivers write (launch.json by step 1's
live_supervisor.py in mode retrieval; effective_settings.json, retrieval-cpu.json and the
question files by stage 2's live_retrieval.py). No network, Ollama, API, database or model: the
supervisor is imported with its requests and processes replaced by fakes.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import statistics
import subprocess
import sys
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports" / "stage4-step3" / "tools"
STAGE2 = ROOT / "reports" / "stage2" / "tools"
SUPERVISOR = ROOT / "reports" / "stage4-step1" / "tools" / "live_supervisor.py"
DRIVERS = {
    "live_api.py": STAGE2 / "live_api.py",
    "live_retrieval.py": STAGE2 / "live_retrieval.py",
    "live_supervisor.py": SUPERVISOR,
    "stage2_common.py": STAGE2 / "stage2_common.py",
}
CURATED = ROOT / "evaluation" / "curated_cases_aircargo.jsonl"
K_CURVE = ROOT / "reports" / "k-curve" / "5e308fe" / "rows.jsonl"
SPEC = ROOT / "docs" / "specs" / "stage4-step3-k-timing.md"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
PLANTED = "PLANTED-текст"


def load(path: Path, name: str) -> Any:
    """A tool as a module of its own name; the sys.path a tool extends is given back."""
    saved = list(sys.path)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = saved
    return module


reader = load(TOOLS / "step3_reader.py", "stage4_step3_reader")
supervisor = load(SUPERVISOR, "stage4_step3_live_supervisor")


# --- synthetic runs ---------------------------------------------------------------------------


def put(path: Path, value: Any) -> None:
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def ident(n: int) -> list[Any]:
    return [f"{PLANTED}-{n:02d}.md", n % 4]


def question(case_id: str, index: int, k: int, rerank: float, *, vector: float) -> dict[str, Any]:
    """One question's file as live_retrieval.py writes it; the pool has the K curve's count."""
    pool_n = reader.K_CURVE_CANDIDATES[case_id][0 if k == 14 else 1]
    vec = [ident(n) for n in range(k)]
    bm25 = [ident(n) for n in range(k, pool_n)] + vec[: 2 * k - pool_n]
    pool = [[*ident(n), round(1.0 / (n + 1), 6)] for n in range(pool_n)]
    ranked = [list(item) for item in pool[:5]]
    walls = {"vector": vector, "rerank": rerank, "retrieval": round(vector + rerank + 0.1, 3)}
    return {
        "case_id": case_id,
        "index": index,
        "question": f"{PLANTED} вопрос {index}",
        "walls": walls,
        "path": {
            "kind": "hybrid",
            "candidates": {"vector": k, "bm25": len(bm25), "merged": pool_n},
            "rerank_status": "ok",
            "rerank_scores": [item[2] for item in ranked],
            "retrieved_contexts": pool_n,
            "retained_contexts": 5,
        },
        "lanes": {"vector": vec, "bm25": bm25},
        "pool": pool,
        "reranker_ok": True,
        "ranked": ranked,
        "expanded": [{"source": s, "chunk_index": c, "text": PLANTED} for s, c, _ in ranked],
        "sent": [
            {"source": s, "chunk_index": c, "text": PLANTED, "cut": i == 2}
            for i, (s, c, _) in enumerate(ranked[:3])
        ],
        "prompt": {
            "sha256": hashlib.sha256(PLANTED.encode()).hexdigest(),
            "chars": 6966,
            "est_tokens": 2589,
            "text": PLANTED,
        },
    }


def write_driver(
    run: Path,
    k: int,
    reranks: dict[str, float],
    *,
    settings: dict[str, Any] | None = None,
    change: Callable[[int, dict[str, Any]], None] | None = None,
    upto: int | None = None,
    summary: bool = True,
) -> None:
    """What live_retrieval.py writes into the run: its settings, a file a question and, at the
    end, retrieval-cpu.json."""
    (run / "retrieval").mkdir(parents=True, exist_ok=True)
    found = {"retrieval_top_k": k, "rerank_top_k": 5, "rag_device": "cpu"}
    found.update(vectordb_chroma_dir=f"/Users/julia/{PLANTED}/chroma", **(settings or {}))
    put(run / "effective_settings.json", {"settings": found, "all": {"note": PLANTED}})
    rows = []
    for index, case_id in enumerate(reader.CASES[:upto], start=1):
        first = index == 1
        record = question(
            case_id, index, k, 40.0 if first else reranks[case_id], vector=60.0 if first else 0.2
        )
        if change:
            change(index, record)
        put(run / "retrieval" / f"{index:03d}-{case_id}.json", record)
        rows.append(
            {
                "case": case_id,
                **record["walls"],
                "reranker_ok": record["reranker_ok"],
                "pool": len(record["pool"] or []),
                "sent": len(record["sent"]),
                "cap": 360.0 if first else 120.0,
            }
        )
    if summary:
        put(
            run / "retrieval-cpu.json",
            {
                "variant": "cpu",
                "tenant": "aircargo",
                "cases_file": f"/Users/julia/{PLANTED}.jsonl",
                "retriever_build_sec": 12.345,
                "window": {"owner": "provider", "context_window": 4096},
                "caps": [360.0, 120.0],
                "questions": rows,
            },
        )


def write_launch(run: Path, label: str, k: int, launch: dict[str, Any] | None = None) -> None:
    """launch.json as step 1's supervisor leaves it after a retrieval run."""
    run.mkdir(parents=True, exist_ok=True)
    overrides = {**supervisor.STANDARD, **({"RAG_RETRIEVAL_TOP_K": "14"} if k == 14 else {})}
    put(
        run / "launch.json",
        {
            "label": label,
            "mode": "retrieval",
            "cases": list(reader.CASES),
            "client_cap_sec": "1400",
            "started": "2026-10-29T08:00:00+00:00",
            "supervisor_pid": 4242,
            "workspace": f"/Users/julia/{PLANTED}",
            "code_sha": reader.CODE_SHA,
            "overrides": overrides,
            "model": MODEL,
            "tenant": "aircargo",
            "chroma_dir": f"/Users/julia/{PLANTED}.chroma",
            "cases_file": f"/Users/julia/{PLANTED}.jsonl",
            "ollama_models_before": [],
            "model_digest": "d" * 64,
            "status": "complete",
            "variants": {"cpu": 0},
            "variant_order": ["cpu"],
            "ollama_models_after": [],
            "unloaded_models": [],
            "finished": "2026-10-29T08:08:00+00:00",
            **(launch or {}),
        },
    )


def write_run(
    folder: Path,
    label: str,
    k: int,
    reranks: dict[str, float],
    *,
    launch: dict[str, Any] | None = None,
    **driver: Any,
) -> str:
    run = folder / "runs" / label
    write_launch(run, label, k, launch)
    write_driver(run, k, reranks, **driver)
    return str(run)


def reader_stand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """$T on the Mac: the reader beside the four drivers."""
    folder = tmp_path / "step3"
    (folder / "runs").mkdir(parents=True)
    for name, source in DRIVERS.items():
        (folder / name).write_bytes(source.read_bytes())
    (folder / "step3_reader.py").write_bytes((TOOLS / "step3_reader.py").read_bytes())
    monkeypatch.setattr(reader, "HERE", folder)
    return folder


# K = 20's mean rerank seconds a question; each K's two asks lie a second and half a second
# around their mean, so the same K's spread is known.
R20 = dict(
    zip(
        reader.PAIRED,
        (27.0, 25.5, 30.1, 22.0, 26.7, 28.0, 31.0, 24.0, 19.5, 21.0, 29.0, 33.0),
        strict=True,
    )
)
FASTER = {case_id: round(0.7 * r, 3) for case_id, r in R20.items()}


def four_runs(
    folder: Path,
    k14: dict[str, float],
    changes: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """The four registered runs in their order, ABBA."""
    args = []
    for label, k in reader.RUNS.items():
        sign = 1 if label.endswith("-1") else -1
        step = 1.0 if k == 20 else 0.5
        means = R20 if k == 20 else k14
        reranks = {case_id: round(mean + sign * step, 3) for case_id, mean in means.items()}
        args.append(write_run(folder, label, k, reranks, **(changes or {}).get(label, {})))
    return args


def read(tmp_path: Path, args: list[str], name: str = "step3.json") -> dict[str, Any]:
    out = tmp_path / name
    assert reader.main([str(out), *args]) == 0
    text = out.read_text("utf-8")
    assert "PLANTED" not in text
    assert b"\r" not in out.read_bytes()
    return json.loads(text)


PASSED = {
    "launch": True,
    "settings": True,
    "drivers": True,
    "asks": True,
    "summary": True,
    "passed": True,
}


# --- the readings -----------------------------------------------------------------------------


def test_the_readings_faster_on_twelve_and_the_numbers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    record = read(tmp_path, four_runs(folder, FASTER))
    assert record["schema"] == reader.SCHEMA and record["spec"] == reader.SPEC
    assert [(run["label"], run["k"]) for run in record["runs"]] == list(reader.RUNS.items())
    for run in record["runs"]:
        assert run["gate"] == PASSED, run["gate"]
        assert run["drivers_sha256"] == reader.DRIVERS_SHA256
        assert run["retriever_build_sec"] == 12.345
        assert [ask["case_id"] for ask in run["asks"]] == list(reader.CASES)
        ask = run["asks"][1]
        assert ask["lanes"] == {"vector": run["k"], "bm25": run["k"]}
        assert ask["ranked"] == 5 and ask["sent"] == 3 and ask["prompt_est_tokens"] == 2589
        assert (
            ask["pool"]
            == ask["merged"]
            == reader.K_CURVE_CANDIDATES[ask["case_id"]][0 if run["k"] == 14 else 1]
        )
    assert [pair["case_id"] for pair in record["pairs"]] == list(reader.PAIRED)
    assert all(pair["readable"] for pair in record["pairs"])
    readings = record["readings"]
    assert readings["answer"] == "faster"
    assert (readings["readable_questions"], readings["k14_faster"], readings["k14_slower"]) == (
        12,
        12,
        0,
    )
    assert readings["sign_p"] == round(2 / 4096, 6)
    assert readings["median_rerank_saving_sec"] == pytest.approx(
        0.3 * statistics.median(R20.values()), abs=1e-3
    )
    assert readings["median_rerank_ratio"] == pytest.approx(0.7, abs=1e-3)
    beside = readings["printed_deciding_nothing"]
    assert beside["median_retrieval_saving_sec"] == readings["median_rerank_saving_sec"]
    assert beside["median_vector_saving_sec"] == 0.0
    assert beside["median_rerank_sec"]["k14"] < beside["median_rerank_sec"]["k20"]
    assert beside["same_k_spread"]["k20"] == pytest.approx(
        statistics.median(2 / r for r in R20.values()), abs=1e-3
    )
    assert beside["same_k_spread"]["k14"] == pytest.approx(
        statistics.median(1 / r for r in FASTER.values()), abs=1e-3
    )
    for name in ("same_pool_both_asks", "same_five_both_asks", "pools_as_k_curve"):
        assert beside[name] == {"k20": 12, "k14": 12}, name


@pytest.mark.parametrize(
    ("wins", "losses", "ties", "answer", "p"),
    [
        (10, 2, 0, "faster", 158 / 4096),
        (9, 3, 0, "no detected difference", 598 / 4096),
        (2, 10, 0, "slower", 158 / 4096),
        (6, 6, 0, "no detected difference", 1.0),
        (9, 0, 3, "faster", 2 / 512),
        (0, 0, 12, "no detected difference", 1.0),
    ],
)
def test_the_sign_rule_at_its_edges_and_ties_count_neither_way(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    wins: int,
    losses: int,
    ties: int,
    answer: str,
    p: float,
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    factors = [0.7] * wins + [1.3] * losses + [1.0] * ties
    k14 = {case_id: round(f * R20[case_id], 3) for case_id, f in zip(R20, factors, strict=True)}
    readings = read(tmp_path, four_runs(folder, k14))["readings"]
    assert (readings["k14_faster"], readings["k14_slower"]) == (wins, losses)
    assert readings["sign_p"] == pytest.approx(p, abs=1e-6)
    assert readings["answer"] == answer


def test_a_pool_unlike_the_k_curves_is_printed_and_decides_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)

    def wider(index: int, record: dict[str, Any]) -> None:
        if index == 4:
            record["pool"].append([*ident(90), 0.001])

    record = read(tmp_path, four_runs(folder, FASTER, {"s3-k14-2": {"change": wider}}))
    readings = record["readings"]
    assert readings["answer"] == "faster" and readings["readable_questions"] == 12
    beside = readings["printed_deciding_nothing"]
    assert beside["same_pool_both_asks"] == {"k20": 12, "k14": 11}
    assert beside["pools_as_k_curve"] == {"k20": 12, "k14": 11}
    assert beside["same_five_both_asks"] == {"k20": 12, "k14": 12}


# --- what an ask and a run need -------------------------------------------------------------


def drop_rerank(record: dict[str, Any]) -> None:
    del record["walls"]["rerank"]


def rerank_failed(record: dict[str, Any]) -> None:
    record["reranker_ok"] = False


def status_failed(record: dict[str, Any]) -> None:
    record["path"]["rerank_status"] = "failed"


def short_vector(record: dict[str, Any]) -> None:
    record["lanes"]["vector"] = record["lanes"]["vector"][:-1]


def empty_bm25(record: dict[str, Any]) -> None:
    record["lanes"]["bm25"] = []


def long_bm25(record: dict[str, Any]) -> None:
    record["lanes"]["bm25"].append(ident(91))


def four_kept(record: dict[str, Any]) -> None:
    record["ranked"] = record["ranked"][:4]


def no_pool(record: dict[str, Any]) -> None:
    record["pool"] = None


@pytest.mark.parametrize(
    ("defect", "why"),
    [
        (drop_rerank, "no rerank seconds"),
        (rerank_failed, "the rerank did not succeed"),
        (status_failed, "the rerank did not succeed"),
        (short_vector, "a lane not K long"),
        (empty_bm25, "a lane not K long"),
        (long_bm25, "a lane not K long"),
        (four_kept, "no pool, or not five kept"),
        (no_pool, "no pool, or not five kept"),
    ],
)
def test_an_unread_ask_fails_its_runs_gate_and_leaves_no_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    defect: Callable[[dict[str, Any]], None],
    why: str,
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)

    def change(index: int, record: dict[str, Any]) -> None:
        if index == 5:
            defect(record)

    record = read(tmp_path, four_runs(folder, FASTER, {"s3-k14-1": {"change": change}}))
    run = record["runs"][1]
    ask = run["asks"][4]
    assert (ask["read"], ask["unread"]) == (False, [why])
    assert sum(not ask["read"] for ask in run["asks"]) == 1
    assert run["gate"]["asks"] is False and run["gate"]["passed"] is False
    assert all(r["gate"]["passed"] for r in record["runs"] if r["label"] != "s3-k14-1")
    for pair in record["pairs"]:
        assert not pair["readable"]
        assert "s3-k14-1: its gate failed" in pair["why"]
        assert "1 read asks at K = 14, not two" in pair["why"]
    assert record["readings"]["answer"] == reader.NOT_EVIDENCE
    assert record["readings"]["readable_questions"] == 0


@pytest.mark.parametrize(
    ("label", "launch"),
    [
        ("s3-k14-1", {"code_sha": "0" * 40}),
        ("s3-k14-1", {"mode": "prod"}),
        ("s3-k14-1", {"status": "failed"}),
        ("s3-k14-1", {"variants": {"cpu": 6}}),
        ("s3-k14-1", {"variants": {"cpu": 0, "auto": 0}}),
        ("s3-k14-1", {"cases": list(reversed(reader.CASES))}),
        ("s3-k14-1", {"ollama_models_before": [MODEL]}),
        ("s3-k14-1", {"ollama_models_after": [MODEL]}),
        ("s3-k14-1", {"overrides": dict(supervisor.STANDARD)}),
        ("s3-k20-2", {"overrides": {**supervisor.STANDARD, "RAG_RETRIEVAL_TOP_K": "14"}}),
    ],
)
def test_the_gate_reads_the_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, label: str, launch: dict[str, Any]
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    record = read(tmp_path, four_runs(folder, FASTER, {label: {"launch": launch}}))
    run = next(run for run in record["runs"] if run["label"] == label)
    assert run["gate"] == {**PASSED, "launch": False, "passed": False}
    assert record["readings"]["answer"] == reader.NOT_EVIDENCE


def test_a_k20_run_may_name_its_k_and_the_launch_keeps_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    named = {"overrides": {**supervisor.STANDARD, "RAG_RETRIEVAL_TOP_K": "20"}}
    record = read(tmp_path, four_runs(folder, FASTER, {"s3-k20-2": {"launch": named}}))
    assert [run["launch"]["k_override"] for run in record["runs"]] == [None, "14", "14", "20"]
    assert all(run["gate"]["passed"] for run in record["runs"])
    assert record["readings"]["answer"] == "faster"


@pytest.mark.parametrize(
    ("label", "driver", "failed"),
    [
        ("s3-k14-2", {"settings": {"retrieval_top_k": 20}}, "settings"),
        ("s3-k20-1", {"settings": {"rerank_top_k": 6}}, "settings"),
        ("s3-k20-1", {"settings": {"rag_device": "mps"}}, "settings"),
        ("s3-k20-1", {"summary": False}, "summary"),
        ("s3-k14-1", {"upto": 12}, "asks"),
    ],
)
def test_the_gate_reads_the_settings_the_questions_and_the_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    label: str,
    driver: dict[str, Any],
    failed: str,
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    record = read(tmp_path, four_runs(folder, FASTER, {label: driver}))
    run = next(run for run in record["runs"] if run["label"] == label)
    expected = {**PASSED, failed: False, "passed": False}
    if failed == "asks":  # twelve questions: retrieval-cpu.json lists twelve too
        expected["summary"] = False
    assert run["gate"] == expected
    assert record["readings"]["answer"] == reader.NOT_EVIDENCE


def test_the_summary_must_hold_each_questions_walls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    args = four_runs(folder, FASTER)
    path = Path(args[3]) / "retrieval-cpu.json"
    summary = json.loads(path.read_text("utf-8"))
    summary["questions"][6]["rerank"] += 1.0
    put(path, summary)
    record = read(tmp_path, args)
    assert record["runs"][3]["gate"] == {**PASSED, "summary": False, "passed": False}


def test_a_question_at_another_position_fails_the_asks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)

    def moved(index: int, record: dict[str, Any]) -> None:
        if index == 3:
            record["index"] = 4

    record = read(tmp_path, four_runs(folder, FASTER, {"s3-k20-2": {"change": moved}}))
    assert record["runs"][3]["gate"]["asks"] is False
    assert record["readings"]["answer"] == reader.NOT_EVIDENCE


def test_a_changed_driver_fails_every_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    args = four_runs(folder, FASTER)
    (folder / "live_retrieval.py").write_bytes(DRIVERS["live_retrieval.py"].read_bytes() + b"#\n")
    record = read(tmp_path, args)
    for run in record["runs"]:
        assert run["gate"] == {**PASSED, "drivers": False, "passed": False}
    assert record["readings"]["answer"] == reader.NOT_EVIDENCE


def test_three_runs_are_not_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    record = read(tmp_path, four_runs(folder, FASTER)[:3])
    assert {tuple(pair["why"]) for pair in record["pairs"]} == {("1 read asks at K = 20, not two",)}
    assert record["readings"]["answer"] == reader.NOT_EVIDENCE


def test_an_unregistered_label_has_no_k_and_no_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    reranks = {case_id: r + 1.0 for case_id, r in FASTER.items()}
    args = [*four_runs(folder, FASTER), write_run(folder, "s3-k16-1", 14, reranks)]
    record = read(tmp_path, args)
    run = record["runs"][4]
    assert run["k"] is None
    assert run["gate"]["launch"] is False and run["gate"]["settings"] is False
    assert record["readings"]["answer"] == "faster"
    assert record["readings"]["readable_questions"] == 12


def test_a_rerun_stands_in_its_runs_place_and_never_beside_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    args = four_runs(folder, FASTER, {"s3-k14-1": {"launch": {"status": "failed"}}})
    reranks = {case_id: round(r + 0.5, 3) for case_id, r in FASTER.items()}
    rerun = write_run(folder, "s3-k14-1-r2", 14, reranks)
    record = read(tmp_path, [args[0], rerun, *args[2:]])
    assert record["runs"][1]["label"] == "s3-k14-1-r2" and record["runs"][1]["k"] == 14
    assert all(run["gate"]["passed"] for run in record["runs"])
    assert record["readings"]["answer"] == "faster"
    for refused in ([*args, rerun], [*args, args[1]]):
        out = tmp_path / "refused.json"
        assert reader.main([str(out), *refused]) == 2
        assert not out.exists()


def test_one_question_first_reads_the_first_ask_while_the_run_goes_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    running = {"status": "running", "variants": {}}
    run = folder / "runs" / "s3-k20-1"
    write_launch(run, "s3-k20-1", 20, running)
    write_driver(run, 20, {}, upto=1, summary=False)
    record = read(tmp_path, [str(run)], "s3-k20-1.q1.step3.json")
    (read_run,) = record["runs"]
    assert len(read_run["asks"]) == 1 and read_run["asks"][0]["read"]
    assert read_run["asks"][0]["rerank"] == 40.0 and read_run["asks"][0]["vector"] == 60.0
    assert read_run["gate"]["passed"] is False
    assert "run: no readable retrieval-cpu.json" in read_run["notes"]


def test_an_existing_out_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    args = four_runs(folder, FASTER)
    out = tmp_path / "step3.json"
    out.write_bytes(b"kept\n")
    assert reader.main([str(out), *args]) == 2
    assert out.read_bytes() == b"kept\n"


# --- the supervisor writes what the reader reads -------------------------------------------


def test_the_supervisor_runs_the_driver_with_k_and_leaves_the_launch_the_reader_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Step 1's supervisor, mode retrieval, with the spec's arguments: Ollama, the processes
    and the sampling are fakes; the driver's fake writes its files into the run."""
    folder = reader_stand(tmp_path, monkeypatch)
    (tmp_path / "CODE_SHA").write_text(reader.CODE_SHA + "\n", "utf-8")
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    put(runtime / "env.json", {"OLLAMA_MODEL_NAME": "qwen2.5:7b", "NOTE": PLANTED})
    monkeypatch.setattr(supervisor, "HERE", folder)
    monkeypatch.setattr(supervisor, "WS", tmp_path)
    monkeypatch.setattr(supervisor, "RUNTIME", runtime)
    monkeypatch.setattr(supervisor, "PY", "/no/python")
    monkeypatch.setattr(supervisor, "port_free", lambda port: True)
    monkeypatch.setattr(supervisor, "sample", lambda: {"sample": 1})

    def fake_ollama(path: str, payload: Any = None, timeout: float = 10) -> Any:
        assert payload is None, "nothing is loaded or unloaded in mode retrieval"
        if path == "/api/tags":
            return {"models": [{"name": MODEL, "digest": "d" * 64}]}
        assert path == "/api/ps"
        return {"models": []}

    seen: dict[str, Any] = {}
    reranks = {case_id: r + 0.5 for case_id, r in FASTER.items()}

    def fake_run(args: list[str], **kwargs: Any) -> Any:
        seen.update(args=args, **kwargs)
        write_driver(Path(kwargs["env"]["CHAT_RUN_DIR"]), 14, reranks)
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(supervisor, "ollama", fake_ollama)
    fakes = types.SimpleNamespace(
        run=fake_run,
        DEVNULL=subprocess.DEVNULL,
        STDOUT=subprocess.STDOUT,
        TimeoutExpired=subprocess.TimeoutExpired,
    )
    monkeypatch.setattr(supervisor, "subprocess", fakes)
    monkeypatch.setenv("LIVE_VARIANTS", "cpu")
    cases = ",".join(reader.CASES)
    argv = ["live_supervisor.py", "s3-k14-1", "retrieval", cases, "1400"]
    monkeypatch.setattr(sys, "argv", [*argv, "TENANT=aircargo,RAG_RETRIEVAL_TOP_K=14"])
    assert supervisor.main() == 0
    assert "LIVE_DONE s3-k14-1 complete exit 0" in capsys.readouterr().out
    assert seen["args"] == ["/no/python", "-u", str(folder / "live_retrieval.py"), "cpu", cases]
    assert seen["timeout"] == 1400.0
    env = seen["env"]
    assert (env["RAG_RETRIEVAL_TOP_K"], env["RAG_DEVICE"], env["CHAT_TENANT"]) == (
        "14",
        "cpu",
        "aircargo",
    )
    assert "OLLAMA_MODEL_NAME" not in env
    record = read(tmp_path, [str(folder / "runs" / "s3-k14-1")])
    (run,) = record["runs"]
    assert run["gate"] == PASSED
    assert run["launch"]["k_override"] == "14" and run["launch"]["client_cap_sec"] == "1400"


# --- the registration ------------------------------------------------------------------------


def test_the_registered_questions_and_the_k_curves_candidates() -> None:
    ids = [json.loads(line)["case_id"] for line in CURATED.read_text("utf-8").splitlines() if line]
    assert tuple(ids[:13]) == reader.CASES
    assert reader.PAIRED == reader.CASES[1:]
    assert reader.RUNS == {"s3-k20-1": 20, "s3-k14-1": 14, "s3-k14-2": 14, "s3-k20-2": 20}
    rows = [json.loads(line) for line in K_CURVE.read_text("utf-8").splitlines() if line]
    aircargo = [row for row in rows if row["base"] == "aircargo"][:13]
    assert [row["case_id"] for row in aircargo] == list(reader.CASES)
    for row in aircargo:
        candidates = {point["k"]: point["candidates"] for point in row["curve"]}
        assert (candidates[14], candidates[20]) == reader.K_CURVE_CANDIDATES[row["case_id"]]


def test_the_spec_names_the_tools_and_the_readings_as_they_stand() -> None:
    """Registered before the first request: the spec names the SHA-256 of each tool and of this
    test, and a later change shows here (a marked error fix updates it)."""
    spec = SPEC.read_text("utf-8")
    assert "registered before the first request" in spec
    named = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", spec))
    assert sorted(named) == [
        "reports/stage2/tools/live_api.py",
        "reports/stage2/tools/live_retrieval.py",
        "reports/stage2/tools/stage2_common.py",
        "reports/stage4-step1/tools/live_supervisor.py",
        "reports/stage4-step3/tools/step3_reader.py",
        "tests/test_stage4_step3_tools.py",
    ]
    for path, digest in named.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    for name, digest in reader.DRIVERS_SHA256.items():
        assert hashlib.sha256(DRIVERS[name].read_bytes()).hexdigest() == digest, name
    assert (reader.MIN_QUESTIONS, reader.ALPHA) == (10, 0.05)
    assert reader.SETTINGS == {"rerank_top_k": 5, "rag_device": "cpu"}
    phrases = (
        "below 0.05",
        "fewer than ten readable questions",
        "at least 10 of 12",
        "ABBA",
        "`RAG_RETRIEVAL_TOP_K=14`",
        "1,400 s",
        "360 s",
        "120 s",
    )
    for phrase in phrases:
        assert phrase in spec, phrase

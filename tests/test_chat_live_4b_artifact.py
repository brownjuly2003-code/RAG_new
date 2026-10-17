"""Check the published live measurement of Julia's production model in the web chat.

ROADMAP, thread M, step 4. From 2026-10-16 21:27 to 2026-10-17 01:48 UTC the stand
`/Users/julia/RAG_new_chat_19beeb1` - `git archive 19beeb1`, where Qwen3-4B-Instruct-2507 is the
code default and the stream's suggested questions follow the answer's model, the 5,589-chunk
index - served the chat at the code defaults (the 3,600-s ceiling, the reranker on the CPU),
questions sent through `/api/ask/stream` as the web chat sends a conversation's first question,
a fresh API per step: one question, five, thirty. `tools/series_plan.json` named every question
and its forecast before the first launch (`cf25593`). The thirty stopped at question 16 on an
expired token of the test client; `tools/rerun_plan.json` named its rerun, with a token per
question, before it (`25ed888`). `tools/runner_memory.py` made the rerun's last note: the model
runner's memory with no API around it. Nothing here needs a model, the network or the Mac: the test
pins the bytes, then derives every published number from the record and finds it in the
evidence row.
"""

import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "reports/chat-live-4b/19beeb1"
# sha256, size and path of every published file, LF line endings (.gitattributes).
PINS = """
89b3a0885d7e301af49466cb5c4d28a0890bfe4f9861cde92f962f7fc8def6f5 174344 runs.json
e6351a975c0752182ca024efb4b2ca8b8d4cb1450926c29da9c6be15c95b9d1c 6806 tools/analyze.py
75be67d42a84b7c31c0f2226487c8992a1977498785028af2caff3d537fd461e 2061 tools/check_export.py
fda8373fc16433aa9c0e5f1af81e016aa4e02bc7a2103e27098c242f12a8ceec 831 tools/defaults_diff.py
38c4694eae40acbd4dad28cb62b121e30fa0847a34a5e8c2a3567eba7737f6db 7731 tools/export.py
b24ce3d52f9aa76bb9b0d9ae794a0a66b0df58720630069f9dc834dab5460e0e 892 tools/export.sh
ad4c5a522956284681756076265db3d59f268ec857f8ca2a4155dcdd41b7a4ea 990 tools/index_digest.py
3098a60df73f86d349a2c9619666340503f13d1f3113fb0b23a1eb1475da7531 701 tools/launch.py
c94273d08c2fe8110de884c90609f15f6b6fd1c9ad59d816d7bea538e4d07f83 544 tools/launch_series.py
aa2bb918d968f2192c8b336d56f5ecc6d69c80f4d0a624abe7ef372a7b596dc6 7706 tools/live_api.py
71dd84ce3724d007564caf2fcad7286ee613a5d9c8e6112a1044cab4a0b20f04 7199 tools/live_runner.py
56c8afd885b63d3185d81b00d4a93ab4098473d49982d7af64d141c279a28986 16859 tools/live_supervisor.py
62f7d3a500c9c737ae12fd29415099693dccb11fe8da8e0a2f16879fb9b8ea88 6274 tools/make_stand.py
492bdc47919698aad61dd99850f758b3e503fa2cc2a7156e0d180123c95ab84f 2311 tools/rerun_plan.json
a7531046d056395d236d6952fd1506f9fdf49432dede3acb9b0b89d02dabe552 2636 tools/runner_memory.py
e859e7e5b85b588ea857cec913cbaaf49ed1963d80cfe3b0a159c5317a82b8cf 2636 tools/series.sh
b4a0c8ac54252a906c750187128a07e444a37edd8f0767a29efbabf8a169f009 3162 tools/series_plan.json
ba09478c70b24b0a6c86b8062f0ce62b9d8499ad2a354cdbb163586e04c40afd 669 tools/watch.sh
"""
FILES = {
    name: (sha256, int(size)) for sha256, size, name in map(str.split, PINS.strip().splitlines())
}
CODE_SHA = "19beeb1e1e49188ac8ddb5188003e10562506ad8"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
MODEL_DIGEST = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
INDEX_DIGEST = "b7cdcac13df472600c9cb4933325260dc3914da09f72ffcb98b2c8e3cfbe4b57"
# The code defaults since 468224b, which the supervisor's `prod` mode puts back.
DEFAULTS = {
    "REQUEST_TIMEOUT_SEC": "3600",
    "OLLAMA_REQUEST_TIMEOUT_SEC": "3600",
    "STREAMING_TIMEOUT_SEC": "3600",
    "RAG_DEVICE": "cpu",
}
SERIES = ["qwen3-4b-instruct-q1", "qwen3-4b-instruct-q5", "qwen3-4b-instruct-q30"]
RERUN = "qwen3-4b-instruct-q30-r2"
LABELS = [*SERIES, RERUN]
# Settings a run may hold off the code defaults: where the deployment keeps its data and
# secrets. Not the model: the supervisor drops the model choice of env.json.
ALLOWED_OFF_DEFAULT = {"tracing_db_path", "vectordb_chroma_dir", "db_encryption_key"}
RERANK = "hybrid._rerank_scored_with_status"


def record() -> dict:
    return json.loads((RECORD / "runs.json").read_text(encoding="utf-8"))


def plan(name: str) -> dict:
    return json.loads((RECORD / "tools" / name).read_text(encoding="utf-8"))


def run(label: str) -> dict:
    return next(item for item in record()["runs"] if item["label"] == label)


def answered(label: str) -> list[dict]:
    return [case for case in run(label)["cases"] if case["result_sec"] is not None]


def delivered() -> list[dict]:
    return [case for label in LABELS for case in answered(label)]


def steps(case: dict, stage: str) -> list[dict]:
    return [step for step in case["timeline"] if step["stage"] == stage]


def seconds(value: float) -> str:
    return f"{round(value)} s"


def median_range(values: list[float]) -> str:
    return (
        f"median {seconds(statistics.median(values))} ({round(min(values))}–{round(max(values))} s)"
    )


def times(cases: list[dict]) -> str:
    return (
        f"first token {median_range([c['first_token_sec'] for c in cases])}, "
        f"result {median_range([c['result_sec'] for c in cases])}"
    )


def evidence_row() -> str:
    index = (ROOT / "EVIDENCE_INDEX.md").read_text(encoding="utf-8")
    (row,) = [line for line in index.splitlines() if "reports/chat-live-4b/19beeb1" in line]
    return row


def test_published_files_are_pinned() -> None:
    published = {
        path.relative_to(RECORD).as_posix() for path in RECORD.rglob("*") if path.is_file()
    }
    assert published == set(FILES), "every published file is pinned, and only those"
    for name, (sha256, size) in FILES.items():
        data = (RECORD / name).read_bytes()
        assert (hashlib.sha256(data).hexdigest(), len(data)) == (sha256, size), name


def test_the_series_and_the_rerun_ran_as_named_before_their_launches() -> None:
    named, rerun, data = plan("series_plan.json"), plan("rerun_plan.json"), record()
    assert (named["model"], named["code_sha"], named["mode"]) == (MODEL, CODE_SHA, "prod")
    assert named["forecast_sec"] == {"first_question_of_a_fresh_api": 340, "other_questions": 400}
    assert named["client_cap_sec"] == rerun["client_cap_sec"] == "1020/1200", "3x the forecast"
    assert "no session_id" in named["client"]
    assert named["named"] < run(SERIES[0])["started"]
    assert [step["label"] for step in named["steps"]] == SERIES
    assert [item["label"] for item in data["runs"]] == LABELS
    for step in named["steps"]:
        asked = [case["case"] for case in run(step["label"])["cases"]]
        assert asked == step["cases"][: len(asked)], step["label"]
    assert [len(step["cases"]) for step in named["steps"]] == [1, 5, 30]
    # The rerun: named after the thirty stopped and before it began, the same thirty questions.
    assert run(SERIES[2])["finished"] < rerun["named"] < run(RERUN)["started"]
    assert (rerun["label"], rerun["code_sha"], rerun["forecast_sec"]) == (
        RERUN,
        CODE_SHA,
        named["forecast_sec"],
    )
    assert rerun["cases"] == named["steps"][2]["cases"]
    assert [case["case"] for case in run(RERUN)["cases"]] == rerun["cases"]


def test_each_run_served_the_4b_alone_at_the_code_defaults() -> None:
    data = record()
    assert data["code_sha"] == CODE_SHA and data["ollama"]["version"] == "0.33.2"
    assert data["host"]["physical_cores"] == 4 and data["host"]["memory_bytes"] == 8 * 2**30
    assert data["index"] == {
        "rag_docs_aircargo": {"chunks": 5589, "sha256_sorted_texts": INDEX_DIGEST}
    }
    for item in data["runs"]:
        assert item["mode"] == "prod" and item["overrides"] == DEFAULTS, item["label"]
        assert (item["model"], item["model_digest"]) == (MODEL, MODEL_DIGEST)
        settings = item["settings"]
        assert settings["ollama_model_name"] == MODEL, "env.json's model choice was dropped"
        assert settings["request_timeout_sec"] == 3600.0 and settings["rag_device"] == "cpu"
        assert set(item["settings_off_default"]) <= ALLOWED_OFF_DEFAULT, item["label"]
        # One model in Ollama at the end: the suggestions no longer load a second one.
        assert item["ollama_models_before"] == [] and item["ollama_models_after"] == [MODEL]
        assert item["tickets"][0] == item["tickets"][1], "a run escalated into the test database"


def test_the_thirty_stopped_on_the_clients_expired_token_and_the_rerun_finished() -> None:
    row = evidence_row()
    assert [(run(label)["status"], run(label)["runner_exit"]) for label in LABELS] == [
        ("complete", 0),
        ("complete", 0),
        ("failed", 4),
        ("complete", 0),
    ]
    *before, stopped = run(SERIES[2])["cases"]
    assert len(before) == 15 and all(case["client_error"] is None for case in before)
    assert stopped["case"] == "aircargo-secret-not-auto" and stopped["tokens"] == 0
    assert "401" in stopped["client_error"] and stopped["total_sec"] < 1
    assert "stopped at question 16 on HTTP 401" in row
    notes = " ".join(note["observed"] for note in run(SERIES[2])["notes"])
    assert "JWT_ACCESS_TTL = 3,600 s" in notes and "63 min" in notes
    rerun = run(RERUN)["cases"]
    assert len(rerun) == 30 and all(case["client_error"] is None for case in rerun)


def test_the_row_publishes_the_times() -> None:
    row = evidence_row()
    (one,) = run(SERIES[0])["cases"]
    first, result = seconds(one["first_token_sec"]), seconds(one["result_sec"])
    assert f"First token / result of the one question: {first} / {result}" in row
    assert f"Five: {times(answered(SERIES[1]))}" in row
    assert f"the 15 answers before the stop: {times(answered(SERIES[2]))}" in row
    assert f"the rerun, all 30: {times(answered(RERUN))}" in row
    every = delivered()
    retrieval = median_range(
        [steps(c, "hybrid.get_relevant_documents_with_path")[0]["wall"] for c in every]
    )
    rerank = median_range([steps(c, RERANK)[0]["wall"] for c in every])
    streams = [steps(case, "ollama.generate_stream")[0] for case in every]
    reading = statistics.median(step["first_chunk_sec"] for step in streams)
    prompt = statistics.median(step["prompt_exact_tokens"] for step in streams)
    writing = statistics.median(
        (c["tokens"] - 1) / (c["last_token_sec"] - c["first_token_sec"]) for c in every
    )
    evaluate = statistics.median(
        step["wall"]
        for case in every
        for step in steps(case, "ollama.generate")
        if step.get("max_tokens") == 128
    )
    assert (
        f"retrieval {retrieval}, the rerank {rerank}, reading the {round(prompt):,}-token prompt "
        f"{seconds(reading)}, writing {writing:.1f} tokens/s, self-eval {seconds(evaluate)}"
    ) in row
    for case in every:
        for step in steps(case, "ollama.generate_stream"):
            # The answer's prompt and its output budget fit the 4,096-token window.
            assert step["prompt_exact_tokens"] + step["max_tokens"] <= 4096


def test_routes_the_rerank_the_forecast_and_memory_are_published() -> None:
    row = evidence_row()
    every = delivered()
    assert {case["route"] for case in every} == {"auto"}
    assert {case["quality_source"] for case in every} == {"llm"}
    scores = [case["quality"] for case in every]
    assert (len(every), scores.count(100), scores.count(95)) == (51, 49, 2)
    assert "All 51 answers routed `auto`, the model scoring 49 of them 100 and two 95" in row
    reranks = [steps(case, RERANK)[0] for case in every]
    assert all(step["reranker_ok"] and step["docs"] == 5 for step in reranks)
    assert "the rerank succeeded on the CPU in 51 of 51" in row
    firsts = [run(label)["cases"][0]["result_sec"] for label in LABELS]
    assert (
        "(" + ", ".join(f"{round(v)}" for v in firsts[:-1]) + f" and {round(firsts[-1])} s "
        "against 340 s)"
    ) in row
    others = [c["result_sec"] for label in LABELS for c in answered(label)[1:]]
    past = sum(value > 400 for value in others)
    assert (
        f"({past} of {len(others)} past 400 s, median {seconds(statistics.median(others))})" in row
    )
    swaps = [round(run(label)["memory"]["swap_used_mb"][1]) for label in (SERIES[2], RERUN)]
    assert f"to {swaps[0]:,} MB in the stopped thirty and {swaps[1]:,} MB in the rerun" in row
    notes = " ".join(note["observed"] for note in run(RERUN)["notes"])
    assert "about 312 MB a request" in notes and "3,184,001,022" in notes
    assert "about 312 MB a request" in row
    # Retrieval was hybrid: every run's tenant restored BM25 at its first question; the
    # BM25 warning each API logged names the startup tenant `default`.
    for label in LABELS:
        notes = " ".join(note["observed"] for note in run(label)["notes"])
        assert "BM25 + parent-expansion re-enabled" in notes, label
        warnings = [w["first"] for w in run(label)["api_warnings"].values()]
        bm25 = [w for w in warnings if "WITHOUT BM25" in w]
        assert len(bm25) == 1 and bm25[0].startswith("Tenant default:"), label
    assert "restored BM25 at its first question" in row

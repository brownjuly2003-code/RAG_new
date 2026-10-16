"""Check the published live measurement of qwen3:1.7b in the web chat (ROADMAP, thread M, step 3).

On 2026-10-16 (00:26-01:28 UTC) the stand `/Users/julia/RAG_new_chat_9e1fc9e` - `git archive
9e1fc9e`, the 5,589-chunk index - served qwen3:1.7b with thinking off (`c2739af`) at the code
defaults of `468224b` (the 3,600-s ceiling, the reranker on the CPU), questions sent through
`/api/ask/stream` as the web chat sends them, a fresh API per step: one question, five, thirty.
`tools/make_stand.py` made the tools from the qwen2.5:7b record's; `tools/series_plan.json`
named every question and its forecast before the first launch, and Julia's stop rule (3x the
forecast, 2026-10-15) ended the thirty at question 9. Nothing here needs a model, the network
or the Mac: the test pins the bytes, then derives every published number from the record and
finds it in the evidence row.
"""

import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "reports/chat-live-qwen3/9e1fc9e"
# sha256, size and path of every published file, LF line endings (.gitattributes).
PINS = """
31045ef9ea03aeb2062fb13549e365b433a62ea1f16f3f1a4b8f33641df3c8a8 48815 runs.json
076a5be30c6d79c11ccbdaaf2a4c4c1ca404fe4578a9d899b5e7009eb8463647 5511 tools/analyze.py
75be67d42a84b7c31c0f2226487c8992a1977498785028af2caff3d537fd461e 2061 tools/check_export.py
fda8373fc16433aa9c0e5f1af81e016aa4e02bc7a2103e27098c242f12a8ceec 831 tools/defaults_diff.py
c04295a4338a496b5aef97e3da11b8dfe382b9a73e0ab43c6c308c4d12e832ac 7669 tools/export.py
25ceaf88a72708eba500e166f72effac32dbbbe6915010941cd976b587b15676 892 tools/export.sh
ad4c5a522956284681756076265db3d59f268ec857f8ca2a4155dcdd41b7a4ea 990 tools/index_digest.py
3098a60df73f86d349a2c9619666340503f13d1f3113fb0b23a1eb1475da7531 701 tools/launch.py
c94273d08c2fe8110de884c90609f15f6b6fd1c9ad59d816d7bea538e4d07f83 544 tools/launch_series.py
aa2bb918d968f2192c8b336d56f5ecc6d69c80f4d0a624abe7ef372a7b596dc6 7706 tools/live_api.py
471f07243f00cba285de6c5e21cd67725db1fb6ae8a00fcc80dbe6d21902eaa4 6999 tools/live_runner.py
55eac4478cd1b19c2014dc8ce630dc225d3fab5db2dc1d454a96e89f98bb6e5c 16239 tools/live_supervisor.py
0ded2ccf557052ae25472cc80d720d620fae1856e3c84b72322935587a7508c2 10669 tools/make_stand.py
90615bd5a09ee8e6452f4ce3e7d649144610ba64ec90fadcd79062253d1d6296 2592 tools/series.sh
3beee5d5e98314a19fd77aec4e8a23c98c1123336038ee7f7e9acc88d3a13887 2497 tools/series_plan.json
8e37d1ba586aa2d6a8ea75e47fc899fc3f352d6f9edca150527f580335736a46 669 tools/watch.sh
"""
FILES = {
    name: (sha256, int(size)) for sha256, size, name in map(str.split, PINS.strip().splitlines())
}
CODE_SHA = "9e1fc9eaa411e6e3aec89a8667bfa19bf7932e46"
MODEL = "qwen3:1.7b"
MODEL_DIGEST = "8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7"
INDEX_DIGEST = "b7cdcac13df472600c9cb4933325260dc3914da09f72ffcb98b2c8e3cfbe4b57"
# The code defaults since 468224b, which the supervisor's `prod` mode puts back.
DEFAULTS = {
    "REQUEST_TIMEOUT_SEC": "3600",
    "OLLAMA_REQUEST_TIMEOUT_SEC": "3600",
    "STREAMING_TIMEOUT_SEC": "3600",
    "RAG_DEVICE": "cpu",
}
LABELS = ["qwen3-1p7b-q1", "qwen3-1p7b-q5", "qwen3-1p7b-q30"]
# Settings a run may hold off the code defaults: where the deployment keeps its data and
# secrets, and the model it served.
ALLOWED_OFF_DEFAULT = {
    "tracing_db_path",
    "vectordb_chroma_dir",
    "db_encryption_key",
    "ollama_model_name",
    "provider_registry_path",
}
RERANK = "hybrid._rerank_scored_with_status"


def record() -> dict:
    return json.loads((RECORD / "runs.json").read_text(encoding="utf-8"))


def plan() -> dict:
    return json.loads((RECORD / "tools/series_plan.json").read_text(encoding="utf-8"))


def run(label: str) -> dict:
    return next(item for item in record()["runs"] if item["label"] == label)


def delivered() -> list[dict]:
    return [
        case
        for item in record()["runs"]
        for case in item["cases"]
        if case["result_sec"] is not None
    ]


def steps(case: dict, stage: str) -> list[dict]:
    return [step for step in case["timeline"] if step["stage"] == stage]


def seconds(value: float) -> str:
    return f"{round(value)} s"


def median_range(values: list[float]) -> str:
    return (
        f"median {seconds(statistics.median(values))} ({round(min(values))}–{round(max(values))} s)"
    )


def evidence_row() -> str:
    index = (ROOT / "EVIDENCE_INDEX.md").read_text(encoding="utf-8")
    (row,) = [line for line in index.splitlines() if "reports/chat-live-qwen3/9e1fc9e" in line]
    return row


def test_published_files_are_pinned() -> None:
    published = {
        path.relative_to(RECORD).as_posix() for path in RECORD.rglob("*") if path.is_file()
    }
    assert published == set(FILES), "every published file is pinned, and only those"
    for name, (sha256, size) in FILES.items():
        data = (RECORD / name).read_bytes()
        assert (hashlib.sha256(data).hexdigest(), len(data)) == (sha256, size), name


def test_the_series_ran_as_named_before_its_first_launch() -> None:
    named = plan()
    data = record()
    assert (named["model"], named["code_sha"], named["mode"]) == (MODEL, CODE_SHA, "prod")
    assert named["forecast_sec"] == {"first_question_of_a_fresh_api": 180, "other_questions": 120}
    assert named["client_cap_sec"] == "540/360", "3x each question's forecast"
    assert named["named"] < data["runs"][0]["started"]
    assert [step["label"] for step in named["steps"]] == LABELS
    assert [item["label"] for item in data["runs"]] == LABELS
    for step in named["steps"]:
        asked = [case["case"] for case in run(step["label"])["cases"]]
        assert asked == step["cases"][: len(asked)], step["label"]
    assert [len(step["cases"]) for step in named["steps"]] == [1, 5, 30]


def test_each_run_served_qwen3_at_the_code_defaults_and_no_other_setting() -> None:
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
        assert settings["ollama_model_name"] == MODEL
        assert settings["request_timeout_sec"] == 3600.0 and settings["rag_device"] == "cpu"
        assert set(item["settings_off_default"]) <= ALLOWED_OFF_DEFAULT, item["label"]
        assert item["ollama_models_before"] == [] and item["ollama_models_after"] == [MODEL]
        assert item["tickets"][0] == item["tickets"][1], "a run escalated into the test database"


def test_the_stop_rule_ended_the_thirty_at_question_nine() -> None:
    row = evidence_row()
    assert [(run(label)["status"], run(label)["runner_exit"]) for label in LABELS] == [
        ("complete", 0),
        ("complete", 0),
        ("failed", 5),
    ]
    thirty = run("qwen3-1p7b-q30")
    *answered, stopped = thirty["cases"]
    assert len(answered) == 8 and all(case["client_error"] is None for case in answered)
    assert stopped["case"] == "aircargo-leave-risk" and stopped["tokens"] == 0
    assert stopped["client_error"] == "TimeoutError: timed out" and stopped["total_sec"] >= 359
    (search,) = steps(stopped, "hybrid._vector_search")
    assert f"its vector search alone took {seconds(search['wall'])}" in row
    swap = thirty["memory"]["swap_used_mb"]
    assert f"swap use had grown to {round(swap[1]):,} MB ({round(swap[0]):,} MB" in row
    notes = " ".join(note["observed"] for note in thirty["notes"])
    assert "both paged out" in notes and "what else held memory" in notes


def test_the_row_publishes_the_times() -> None:
    row = evidence_row()
    (one,) = run("qwen3-1p7b-q1")["cases"]
    first, result = seconds(one["first_token_sec"]), seconds(one["result_sec"])
    assert f"First token / result of the one question: {first} / {result}" in row
    for label, name in (
        ("qwen3-1p7b-q5", "Five"),
        ("qwen3-1p7b-q30", "the eight answers before it"),
    ):
        cases = [case for case in run(label)["cases"] if case["result_sec"] is not None]
        assert (
            f"{name}: first token {median_range([c['first_token_sec'] for c in cases])}, "
            f"result {median_range([c['result_sec'] for c in cases])}"
        ) in row
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
        if step["max_tokens"] == 128
    )
    assert (
        f"retrieval {retrieval}, the rerank {rerank}, reading the {round(prompt):,}-token prompt "
        f"{seconds(reading)}, writing {writing:.1f} tokens/s, self-eval {seconds(evaluate)}"
    ) in row
    for case in every:
        for step in steps(case, "ollama.generate_stream") + steps(case, "ollama.generate"):
            # Every prompt and its output budget fit the 4,096-token window (2758be5).
            assert step["prompt_exact_tokens"] + step["max_tokens"] <= 4096


def test_routes_the_rerank_and_the_forecast_are_published() -> None:
    row = evidence_row()
    every = delivered()
    assert {case["route"] for case in every} == {"auto"}
    reranks = [steps(case, RERANK)[0] for case in every]
    assert all(step["reranker_ok"] and step["docs"] == 5 for step in reranks)
    count = len(every)
    assert f"All {count} answers routed `auto`, no ticket opened" in row
    assert f"the rerank succeeded on the CPU in {count} of {count}" in row
    firsts = [run(label)["cases"][0]["result_sec"] for label in LABELS]
    assert (
        "the first question of a fresh API ("
        + ", ".join(f"{round(value)}" for value in firsts[:-1])
        + f" and {round(firsts[-1])} s against 180 s)"
        in row
    )
    others = [
        c["result_sec"] for label in LABELS for c in run(label)["cases"][1:] if c["result_sec"]
    ]
    past = sum(value > 120 for value in others)
    assert (
        f"missed every other ({past} of {len(others)} past 120 s, "
        f"median {seconds(statistics.median(others))})"
    ) in row
    warnings = [
        warning["first"] for label in LABELS for warning in run(label)["api_warnings"].values()
    ]
    assert sum("WITHOUT BM25 index" in warning for warning in warnings) == len(LABELS)
    assert "retriever built without the BM25 index" in row

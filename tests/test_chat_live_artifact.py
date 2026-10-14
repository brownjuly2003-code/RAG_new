"""Check the published live measurement of the web chat on the production Mac.

The record was produced on deproject-mac on 2026-10-14 by the tools kept beside it
(`reports/chat-live/33d4b42/tools/`): the real API at code `33d4b42`, the ready index,
qwen2.5:7b served by Ollama on the CPU, questions sent through `/api/ask/stream` as the
web chat sends them. No model, network or Mac is needed here: the test pins the bytes,
then derives every published number from the record and finds it in the evidence row.
"""

import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "reports/chat-live/33d4b42"
# sha256, size and path of every published file, LF line endings (.gitattributes).
PINS = """
827f67e12c04336216f9321abd12497bdf99231c53ce7382d686b141df37578e 5704 bench/bench_ollama.py
dd1b570567201e0fecb05ba5c17dfa7431c9652365cef2c4be0020e62b0fe33f 19025 bench/prompts.py
5fef4d1111d9a8ee3c863a9f2dcdef684d0acd9bff57f5a61f24a4ad3b1de8e6 4847 bench/results.json
70014dee0cc191ba9c1b2f9330b8022b1639eaf0a52b181012cbdaac4f628874 71214 runs.json
1e569e905cd1e31e1c16f39fc4d2367faa85c798aa9a2780343f086c939ab9b8 5464 tools/analyze.py
14b52d6080d0e2609aef071673863e8669bb2565d87a8f74b9955162704e5933 3673 tools/analyze_retrieval.py
75be67d42a84b7c31c0f2226487c8992a1977498785028af2caff3d537fd461e 2061 tools/check_export.py
fda8373fc16433aa9c0e5f1af81e016aa4e02bc7a2103e27098c242f12a8ceec 831 tools/defaults_diff.py
5f7b3fa12b8b5ea419577b9841c5ba0ef0a39cbc990d2c81c3c4652bf24ffc41 7367 tools/export.py
a0290f89844611665cdf9ed95920b47ff14ac2ccdabc0bf648b3236bbaa36618 931 tools/export.sh
ad4c5a522956284681756076265db3d59f268ec857f8ca2a4155dcdd41b7a4ea 990 tools/index_digest.py
3098a60df73f86d349a2c9619666340503f13d1f3113fb0b23a1eb1475da7531 701 tools/launch.py
b056b670d1a16a3ae7159e1d6eb6f88909209fb7ac4daaa8673523bb5ef22f32 7386 tools/live_api.py
96de0bb5d974df55faa21f9511e953b8aa008117f9d91c4a4c915f474b24a89a 5607 tools/live_retrieval.py
6e5d3f3427055b5874734c279674f7751d21113998ca1e953c89323f9f9d9658 6394 tools/live_runner.py
55d0e6dfc30502aea5fbcc778f411a0e066da40c8714f588b4b77a6f958cdbeb 13898 tools/live_supervisor.py
707835f7ef865e78ab37beef13f0784932d216830b00a1f2f041be2a0bce9bed 2185 tools/old_prod_lat.py
b238a69d69b4397fac3b6d195bd1120af7235d4dd60acd950af05cf97641f614 716 tools/r2.sh
54c4d118b8f9e014c03d493c8b09a43dcb0903a137e81843f1d7459ee420ac2e 814 tools/summary.py
94b56c30e924a004e521a8695cd66310234c8c7c24533069b621086f12dc6067 669 tools/watch.sh
"""
FILES = {
    name: (sha256, int(size)) for sha256, size, name in map(str.split, PINS.strip().splitlines())
}
CODE_SHA = "33d4b4236e74121c6e23412d40656cbdc8c5e2c9"
STANDARD = "live-b1-prod"
FLOOR = "live-b2-floor"
RETRIEVAL = "live-r1-retrieval"
GPU = "live-r2-rerank-gpu"
# Settings a run may hold off the code defaults: where the deployment keeps its data
# and secrets, plus what the run itself overrode (its `overrides`).
DEPLOYMENT_FIELDS = {"tracing_db_path", "vectordb_chroma_dir", "db_encryption_key"}


def record() -> dict:
    return json.loads((REPORT / "runs.json").read_text(encoding="utf-8"))


def run(label: str) -> dict:
    return next(item for item in record()["runs"] if item["label"] == label)


def steps(case: dict, stage: str) -> list[dict]:
    return [step for step in case["timeline"] if step["stage"] == stage]


def retrieval_sec(case: dict) -> float:
    (step,) = steps(case, "hybrid.get_relevant_documents_with_path")
    return step["wall"]


def seconds(value: float) -> str:
    return f"{round(value)} s"


def evidence_row() -> str:
    index = (ROOT / "EVIDENCE_INDEX.md").read_text(encoding="utf-8")
    (row,) = [line for line in index.splitlines() if "reports/chat-live/33d4b42" in line]
    return row


def test_published_files_are_pinned() -> None:
    published = {
        path.relative_to(REPORT).as_posix() for path in REPORT.rglob("*") if path.is_file()
    }
    assert published == set(FILES), "every published file is pinned, and only those"
    for name, (sha256, size) in FILES.items():
        data = (REPORT / name).read_bytes()
        assert (hashlib.sha256(data).hexdigest(), len(data)) == (sha256, size), name


def test_provenance_names_code_index_model_and_every_setting_off_default() -> None:
    data = record()
    assert data["code_sha"] == CODE_SHA
    (collection,) = data["index"].values()
    assert collection["chunks"] == 5589
    assert data["ollama"]["model"] == "qwen2.5:7b" and data["ollama"]["version"] == "0.33.2"
    assert data["host"]["physical_cores"] == 4 and data["host"]["memory_bytes"] == 8 * 2**30
    for item in data["runs"]:
        overridden = {name.lower() for name in item["overrides"]}
        assert set(item["settings_off_default"]) <= DEPLOYMENT_FIELDS | overridden, item["label"]
        assert item["settings"]["ollama_model_name"] == "qwen2.5:7b"
        assert item["settings"]["ollama_context_window"] == 4096
        assert item["tickets"][0] == item["tickets"][1], "a run escalated into the test database"


def test_code_default_limits_deliver_no_answer() -> None:
    standard = run(STANDARD)
    assert standard["settings"]["request_timeout_sec"] == 30.0
    assert standard["settings"]["rag_device"] == "auto"
    assert standard["settings_off_default"].keys() <= DEPLOYMENT_FIELDS
    assert all(case["tokens"] == 0 and case["route"] == "timeout" for case in standard["cases"])
    # The first question warms the process up; the last one is the question of the set.
    question = standard["cases"][-1]
    row = evidence_row()
    assert f"retrieval alone took {retrieval_sec(question):.1f} s of the 30 s" in row
    reranker = [w for w in standard["api_warnings"].values() if "Reranker error" in w["first"]]
    assert reranker and all("MPS backend out of memory" in w["first"] for w in reranker)


def median_range(values: list[float]) -> str:
    return (
        f"median {seconds(statistics.median(values))} ({round(min(values))}–{round(max(values))} s)"
    )


def test_floor_limits_measure_a_complete_answer_and_the_row_publishes_its_time() -> None:
    floor = run(FLOOR)
    assert floor["overrides"] == {
        "REQUEST_TIMEOUT_SEC": "1800",
        "OLLAMA_REQUEST_TIMEOUT_SEC": "1800",
        "STREAMING_TIMEOUT_SEC": "1800",
        "RAG_DEVICE": "cpu",
    }
    assert floor["status"] == "complete" and len(floor["cases"]) == 5
    for case in floor["cases"]:
        assert case["tokens"] > 0 and case["route"] == "auto" and case["client_error"] is None
        assert case["first_token_sec"] < case["last_token_sec"] < case["result_sec"]
        for step in steps(case, "ollama.generate_stream") + steps(case, "ollama.generate"):
            # Every prompt and its output budget fit the 4,096-token window (2758be5).
            assert step["prompt_exact_tokens"] + step["max_tokens"] <= 4096
    # Later questions are no faster than the first: the 7B model, the embedder and the
    # reranker do not fit 8 GB together, so the medians are over all five.
    every = floor["cases"]
    row = evidence_row()
    assert f"first token {median_range([c['first_token_sec'] for c in every])}" in row
    assert f"result {median_range([c['result_sec'] for c in every])}" in row
    retrieval = statistics.median(retrieval_sec(case) for case in every)
    streams = [steps(case, "ollama.generate_stream")[0] for case in every]
    reading = statistics.median(step["first_chunk_sec"] for step in streams)
    prompt = statistics.median(step["prompt_exact_tokens"] for step in streams)
    writing = statistics.median(
        (case["tokens"] - 1) / (case["last_token_sec"] - case["first_token_sec"]) for case in every
    )
    evaluate = statistics.median(
        step["wall"]
        for case in every
        for step in steps(case, "ollama.generate")
        if step["max_tokens"] == 128
    )
    assert (
        f"retrieval {seconds(retrieval)}, reading the {round(prompt):,}-token prompt "
        f"{seconds(reading)}, writing {writing:.1f} tokens/s, self-eval {seconds(evaluate)}"
    ) in row


def retrieval_run(label: str) -> dict:
    return next(item for item in record()["retrieval_runs"] if item["label"] == label)


def placement(label: str, variant: str) -> dict:
    return next(item for item in retrieval_run(label)["variants"] if item["variant"] == variant)


def questions(variant: dict) -> list[dict]:
    """The questions of the set; the warm-up question before them loads the models."""
    return [question for question in variant["questions"] if question["case"] != "warmup-1"]


def tenths(values: list[float]) -> str:
    return f"median {statistics.median(values):.1f} s ({min(values):.0f}–{max(values):.0f} s)"


def test_retrieval_alone_runs_the_floor_questions_with_no_model_loaded() -> None:
    names = [case["case"] for case in run(FLOOR)["cases"]]
    for label in (RETRIEVAL, GPU):
        item = retrieval_run(label)
        assert item["status"] == "complete", label
        assert item["ollama_models_before"] == [] and item["ollama_models_after"] == [], label
        overridden = {name.lower() for name in item["overrides"]}
        assert set(item["settings_off_default"]) <= DEPLOYMENT_FIELDS | overridden, label
        assert (
            item["settings"]["rag_device"] == "auto" and item["settings"]["retrieval_top_k"] == 20
        )
        for variant in item["variants"]:
            assert variant["questions"][0]["case"] == "warmup-1"
            assert [q["case"] for q in questions(variant)] == names, variant["variant"]


def test_on_the_cpu_retrieval_is_the_rerank_and_swapping_made_it_eight_times_slower() -> None:
    cpu = placement(RETRIEVAL, "cpu")
    assert cpu["devices"] == {"get_embeddings": "cpu", "get_reranker": "cpu"}
    assert all(question["reranker_ok"] for question in cpu["questions"])
    alone = questions(cpu)
    row = evidence_row()
    assert (
        f"retrieval alone, with no model loaded, {tenths([q['retrieval_sec'] for q in alone])}"
        f" on the CPU, the rerank {statistics.median(q['rerank'] for q in alone):.1f} s of it"
    ) in row
    assert f"the vector search {statistics.median(q['vector'] for q in alone):.1f} s" in row
    floor = statistics.median(retrieval_sec(case) for case in run(FLOOR)["cases"])
    ratio = floor / statistics.median(q["retrieval_sec"] for q in alone)
    assert f"slowed {ratio:.0f}× by swapping" in row


def test_the_gpu_fails_the_reranker_at_its_batch_and_is_slower_at_a_small_one() -> None:
    alone = placement(GPU, "rerank-mps")
    assert alone["devices"] == {"get_embeddings": "cpu", "get_reranker": "mps"}
    for question in alone["questions"]:
        assert not question["reranker_ok"] and question["rerank_batch_effective"] is None
        (error,) = question["reranker_errors"]
        assert "MPS backend out of memory" in error
    small = placement(GPU, "rerank-mps-b4")
    assert small["devices"] == {"get_embeddings": "cpu", "get_reranker": "mps"}
    assert all(q["reranker_ok"] and q["rerank_batch_effective"] == 4 for q in small["questions"])
    gpu = [question["retrieval_sec"] for question in questions(small)]
    cpu = [question["retrieval_sec"] for question in questions(placement(RETRIEVAL, "cpu"))]
    ratio = statistics.median(gpu) / statistics.median(cpu)
    row = evidence_row()
    assert (
        "on the GPU the reranker fails with MPS out of memory at its default batch even alone; "
        f"at batch 4 it works, but retrieval takes {tenths(gpu)}, {ratio:.1f}× the CPU"
    ) in row
    single = placement(GPU, "rerank-mps-b1")
    assert all(q["reranker_ok"] and q["rerank_batch_effective"] == 1 for q in single["questions"])
    assert f"at batch 1 {tenths([q['retrieval_sec'] for q in questions(single)])}" in row
    both = placement(GPU, "auto-b4")
    assert both["devices"] == {"get_embeddings": "mps", "get_reranker": "mps"}
    assert all(q["reranker_ok"] and q["rerank_batch_effective"] == 4 for q in both["questions"])
    together = [question["retrieval_sec"] for question in questions(both)]
    assert f"with the embedder also on the GPU at batch 4 {tenths(together)}" in row


def test_the_code_default_placement_loses_the_rerank_without_failing_the_request() -> None:
    for label in (RETRIEVAL, GPU):
        default = placement(label, "auto")
        assert default["devices"] == {"get_embeddings": "mps", "get_reranker": "mps"}
        assert not any(question["reranker_ok"] for question in default["questions"])
    # R2 kept the error each rerank logged: the reranker never ran under the default.
    errors = [q["reranker_errors"] for q in placement(GPU, "auto")["questions"]]
    assert all(len(e) == 1 and "MPS backend out of memory" in e[0] for e in errors)

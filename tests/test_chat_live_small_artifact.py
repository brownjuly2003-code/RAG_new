"""Check the published live measurement of the web chat with generators below 7B.

On 2026-10-14 the stand of the qwen2.5:7b record (`reports/chat-live/33d4b42/`) served
qwen2.5:1.5b and then Qwen3-4B-Instruct-2507 through `MODEL=` of its supervisor, kept in
`tools/` with the rest of what changed (`tools/make_small_stand.py` makes the stand from the
7B record's tools; `tools/live_small.sh` ran it): the real API at code `33d4b42`, the
5,589-chunk index, questions sent through `/api/ask/stream` as the web chat sends them. Per
model: the code-default limits on the 7B record's B1 questions, then the floor limits on the
CPU for one question and for the five B2 questions. qwen3:1.7b was not timed: the API sends
Ollama no `think` value, and it thinks (`tools/think_probe.out`). Nothing here needs a model,
the network or the Mac: the test pins the bytes, then derives every published number from
the record and finds it in the evidence row.
"""

import hashlib
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "reports/chat-live-small/33d4b42"
# sha256, size and path of every published file, LF line endings (.gitattributes).
PINS = """
fccacd5d0f02c22a0a8f3854a73201f2712c0d67a6bdc97f4404912a82a40f71 66719 runs.json
c04295a4338a496b5aef97e3da11b8dfe382b9a73e0ab43c6c308c4d12e832ac 7669 tools/export.py
805d29a61c7d41535604f98b860c2bd586b4f58ae4e1770133b24cf82a867119 904 tools/export.sh
c61bfdbbf17807c726ebd6cd89f8674b5436c6ac46b68dec42c94bd77a1717d2 2833 tools/live_small.sh
748740d60dfe6523095fb5160d51cad75469540b6885377421a4d36aa6bf6886 15773 tools/live_supervisor.py
0f32de8c105c88e21cbbf1d332e27a36039c29a656bb271d24be4c375084e773 7331 tools/make_small_stand.py
bc54de63b62024a9f36ca4a2437e11d25ed003c9da0557be61398c749713b04d 612 tools/think_probe.out
09d570c4db48a8b8667f00512ebbb434c11046f1bd64557e65a4d69e78432aed 2767 tools/think_probe.py
06d2f00b6020a9d10c6adcd52349c574d403cb4a63c064e0214921d4f4e1b568 706 tools/watch_live.sh
"""
FILES = {
    name: (sha256, int(size)) for sha256, size, name in map(str.split, PINS.strip().splitlines())
}
CODE_SHA = "33d4b4236e74121c6e23412d40656cbdc8c5e2c9"
# Label stem: the Ollama tag served, its digest, and its name in the evidence row.
MODELS = {
    "qwen25-1p5b": (
        "qwen2.5:1.5b",
        "65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b",
        "qwen2.5:1.5b",
    ),
    "qwen3-4b-instruct": (
        "qwen3:4b-instruct-2507-q4_K_M",
        "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0",
        "Qwen3-4B",
    ),
}
FLOOR_LIMITS = {
    "REQUEST_TIMEOUT_SEC": "1800",
    "OLLAMA_REQUEST_TIMEOUT_SEC": "1800",
    "STREAMING_TIMEOUT_SEC": "1800",
    "RAG_DEVICE": "cpu",
}
B2 = [
    "aircargo-probation-data",
    "aircargo-probation-extend",
    "aircargo-probation-dismissal",
    "aircargo-dismissal-check",
    "aircargo-dismissal-lawyer",
]
# Settings a run may hold off the code defaults: where the deployment keeps its data and
# secrets, the model it served, plus what the run itself overrode (its `overrides`).
DEPLOYMENT_FIELDS = {"tracing_db_path", "vectordb_chroma_dir", "db_encryption_key"}
MODEL_FIELDS = {"ollama_model_name", "provider_registry_path"}


def record() -> dict:
    return json.loads((RECORD / "runs.json").read_text(encoding="utf-8"))


def run(label: str) -> dict:
    return next(item for item in record()["runs"] if item["label"] == label)


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
    (row,) = [line for line in index.splitlines() if "reports/chat-live-small/33d4b42" in line]
    return row


def test_published_files_are_pinned() -> None:
    published = {
        path.relative_to(RECORD).as_posix() for path in RECORD.rglob("*") if path.is_file()
    }
    assert published == set(FILES), "every published file is pinned, and only those"
    for name, (sha256, size) in FILES.items():
        data = (RECORD / name).read_bytes()
        assert (hashlib.sha256(data).hexdigest(), len(data)) == (sha256, size), name


def test_each_run_served_its_small_model_and_no_other() -> None:
    data = record()
    assert data["code_sha"] == CODE_SHA and data["ollama"]["version"] == "0.33.2"
    assert data["host"]["physical_cores"] == 4 and data["host"]["memory_bytes"] == 8 * 2**30
    (collection,) = data["index"].values()
    assert collection["chunks"] == 5589
    labels = [item["label"] for item in data["runs"]]
    assert labels == [
        f"live-{step}-{stem}-{mode}"
        for stem in MODELS
        for step, mode in (("s1", "prod"), ("s2", "floor1"), ("s3", "floor"))
    ]
    for item in data["runs"]:
        tag, digest, _ = MODELS[item["label"].split("-", 2)[2].rsplit("-", 1)[0]]
        assert (item["model"], item["model_digest"]) == (tag, digest), item["label"]
        assert item["settings"]["ollama_model_name"] == tag
        assert item["settings"]["ollama_context_window"] == 4096
        assert item["ollama_models_before"] == [] and item["ollama_models_after"] == [tag]
        overridden = {name.lower() for name in item["overrides"]}
        allowed = DEPLOYMENT_FIELDS | MODEL_FIELDS | overridden
        assert set(item["settings_off_default"]) <= allowed, item["label"]
        assert item["tickets"][0] == item["tickets"][1], "a run escalated into the test database"


def test_code_default_limits_deliver_no_answer_with_a_small_model_either() -> None:
    row = evidence_row()
    for stem, (_, _, name) in MODELS.items():
        standard = run(f"live-s1-{stem}-prod")
        assert standard["settings"]["request_timeout_sec"] == 30.0
        assert standard["settings"]["rag_device"] == "auto"
        # The runner stops a run at the first question that delivers no answer (exit 4).
        assert (standard["status"], standard["runner_exit"]) == ("failed", 4)
        assert [case["case"] for case in standard["cases"]] == ["warmup-1", B2[0]]
        assert all(case["tokens"] == 0 for case in standard["cases"])
        warmup = standard["cases"][0]
        assert warmup["route"] == "timeout"
        assert f"{name}: warm-up timeout after {seconds(warmup['result_sec'])}" in row
        reranker = [w for w in standard["api_warnings"].values() if "Reranker error" in w["first"]]
        assert reranker and all("MPS backend out of memory" in w["first"] for w in reranker)
    small = run("live-s1-qwen25-1p5b-prod")
    assert all(case["route"] == "timeout" for case in small["cases"])
    # Qwen3-4B: after the warm-up the question's stream closed on its `status` event, with
    # neither a result nor an error: the API raised 503 inside the started stream (notes).
    instruct = run("live-s1-qwen3-4b-instruct-prod")
    _, question = instruct["cases"]
    assert [event["type"] for event in question["events"]] == ["status"]
    assert question["result_sec"] is None
    notes = " ".join(note["observed"] for note in instruct["notes"])
    assert "503 'Session store temporarily unavailable'" in notes
    assert "Session store temporarily unavailable" in row


def test_floor_limits_measure_a_complete_answer_and_the_row_publishes_its_time() -> None:
    row = evidence_row()
    assert "first token / result of the one question right after the start:" in row
    for stem, (_, _, name) in MODELS.items():
        (one,) = run(f"live-s2-{stem}-floor1")["cases"]
        assert f"{name} {seconds(one['first_token_sec'])} / {seconds(one['result_sec'])}" in row
        for label, cases in ((f"live-s2-{stem}-floor1", B2[:1]), (f"live-s3-{stem}-floor", B2)):
            floor = run(label)
            assert floor["overrides"] == FLOOR_LIMITS and floor["status"] == "complete"
            assert [case["case"] for case in floor["cases"]] == cases
            for case in floor["cases"]:
                assert case["tokens"] > 0 and case["client_error"] is None
                assert case["first_token_sec"] <= case["last_token_sec"] < case["result_sec"]
                for step in steps(case, "ollama.generate_stream") + steps(case, "ollama.generate"):
                    # Every prompt and its output budget fit the 4,096-token window (2758be5).
                    assert step["prompt_exact_tokens"] + step["max_tokens"] <= 4096
        every = run(f"live-s3-{stem}-floor")["cases"]
        first = median_range([c["first_token_sec"] for c in every])
        result = median_range([c["result_sec"] for c in every])
        assert f"{name} first token {first}, result {result}" in row
        retrieval = statistics.median(
            steps(c, "hybrid.get_relevant_documents_with_path")[0]["wall"] for c in every
        )
        rerank = statistics.median(
            steps(c, "hybrid._rerank_scored_with_status")[0]["wall"] for c in every
        )
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
            f"retrieval {seconds(retrieval)} (the rerank {seconds(rerank)}), reading the "
            f"{round(prompt):,}-token prompt {seconds(reading)}, writing {writing:.1f} tokens/s, "
            f"self-eval {seconds(evaluate)}"
        ) in row


def test_the_routes_and_the_bare_reference_are_published() -> None:
    row = evidence_row()
    small = run("live-s3-qwen25-1p5b-floor")["cases"]
    humans = sum(case["route"] == "human" for case in small)
    assert humans == 4 and f"{humans} of its five answers routed `human`" in row
    (bare,) = [case for case in small if re.fullmatch(r"\[\d+\]", case["answer"].strip())]
    assert bare["route"] == "auto" and f"the bare reference «{bare['answer'].strip()}»" in row
    instruct = run("live-s3-qwen3-4b-instruct-floor")["cases"]
    assert all(case["route"] == "auto" for case in instruct)
    assert all(re.search(r"\[\d+\]", case["answer"]) for case in instruct)
    assert "all five routed `auto`, each with a reference" in row


def test_qwen3_1_7b_thinks_on_the_chat_path() -> None:
    probe = (RECORD / "tools/think_probe.out").read_text(encoding="utf-8")
    assert "OllamaLLM.reasoning default: None" in probe
    assert "payload carries think from reasoning: True" in probe
    provider = probe.split("provider class OllamaLLM.generate", 1)[1]
    thinking = int(re.search(r"thinking chars: (\d+)", provider).group(1))
    tokens = int(re.search(r"output tokens: (\d+)", provider).group(1))
    assert thinking > 0
    row = evidence_row()
    assert f"{thinking} characters of reasoning, {tokens} output tokens" in row

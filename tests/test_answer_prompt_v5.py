"""reports/answer-prompt-v5/tools: the replay of V4's saved contexts under V5, its summary, and
the record of V5 against V4, paired.

docs/specs/answer-prompt-v5.md. A fake stream model and toy V4 runs - the chat's own prompts of
short documents - stand in for the stand's model and the private runs; toy plans and records of
the stage-2 schemas - ids, classes and counts only - for the judge's records.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import string
import sys
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agent import prompts
from agent.prompts import build_qa_prompt
from llm.providers.base import flatten_messages
from llm.role_params import generation_kwargs_for_role
from scripts import chat_answer_judge as judge

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports" / "answer-prompt-v5" / "tools"
STAND = "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
DIGEST = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
# QA_PROMPT_V4's text as V4's spec registered it, and V5's as this spec registers it.
V4_SHA256 = "9276aff5a3a44bc9ff1adb7a52b7b11a06e8f4b0f7fe79a5dc6b20262db3a515"
# The judge V5's plans are read by, as committed with the tools.
JUDGE_SHA256 = hashlib.sha256((ROOT / "scripts/chat_answer_judge.py").read_bytes()).hexdigest()
DOCS = [
    {
        "page_content": "Storage costs ten euros a day from the fourth day after arrival.",
        "metadata": {"source": "fees.md"},
    },
    {
        "page_content": "Claims are filed within 14 days.\n\nA late claim needs the manager's word.",
        "metadata": {"source": "claims.md"},
    },
]
QUESTIONS = {
    "w0": "What does storage cost?",
    "w1": "When are claims filed?",
    "w2": "Can a claim be late?",
}
V4_ANSWER = "Storage is charged daily [1]."
V5_TOKENS = (
    '1. Evidence: "Storage costs ten euros ',
    'a day from the fourth day after arrival." [1]',
)
KEYS = ("wixqa", "conditionalqa", "aircargo")


@pytest.fixture(scope="module")
def tools() -> Iterator[dict[str, Any]]:
    """The tools, loaded from their files; the sys.path entries they add are taken back."""
    saved = list(sys.path)
    loaded = {}
    for name in ("replay", "v5_record"):
        spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
        assert spec and spec.loader
        loaded[name] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded[name])
    yield loaded
    sys.path[:] = saved


@pytest.fixture()
def replay(tools: dict[str, Any]) -> Any:
    return tools["replay"]


@pytest.fixture()
def record(tools: dict[str, Any]) -> Any:
    return tools["v5_record"]


def _v4_prompt(question: str, docs: list[dict] = DOCS) -> str:
    """V4's stream prompt as the stand saved it: the chat's prompt, flattened."""
    return flatten_messages([{"role": "user", "content": build_qa_prompt(question, docs)}])


class FakeModel:
    """The chat's stream model as the replay calls it: the window, the name, generate_stream."""

    context_window = 4096
    model_name = MODEL

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[list[dict], dict]] = []

    async def generate_stream(self, messages: list[dict], **kwargs: Any) -> AsyncIterator[str]:
        self.calls.append((messages, kwargs))
        if self.fail:
            raise RuntimeError("the model is down")
        for token in V5_TOKENS:
            yield token


def _v4_runs(root: Path, key: str = "wixqa", *, header: str | None = None) -> Path:
    """V4's run v4-KEY-b01 of three answered cases and a warm-up, as the stand saved it."""
    run = root / "runs" / f"v4-{key}-b01"
    (run / "prompts").mkdir(parents=True)
    (run / "cases").mkdir()
    (run / "prompts" / "000-stream.txt").write_text(_v4_prompt("warm up"), "utf-8")
    stages = []
    for index, (case, question) in enumerate(QUESTIONS.items(), start=1):
        text = _v4_prompt(question)
        if header is not None and index == 2:
            text = text.replace("You are a support assistant.", header)
        name = f"{2 * index - 1:03d}-stream.txt"
        (run / "prompts" / name).write_bytes(text.encode("utf-8"))
        (run / "prompts" / f"{2 * index:03d}-generate.txt").write_text("self-eval", "utf-8")
        row = {
            "case_id": case,
            "question": question,
            "answer": V4_ANSWER,
            "events": [{"type": "result", "answer": V4_ANSWER, "route": "auto"}],
        }
        (run / "cases" / f"{index:02d}-{case}.json").write_text(json.dumps(row), "utf-8")
        stages.append(
            {
                "stage": "ollama.generate_stream",
                "event": "end",
                "prompt_file": name,
                "prompt_est_tokens": 300 + index,
                "chunks": 80 + index,
                "wall_sec": 85.12345,
                "first_chunk_sec": 61.5,
            }
        )
    warm = {"case_id": "warmup-1", "question": "warm up", "answer": "x", "events": []}
    (run / "cases" / "00-warmup-1.json").write_text(json.dumps(warm), "utf-8")
    (run / "stages.jsonl").write_text("".join(json.dumps(r) + "\n" for r in stages), "utf-8")
    launch = {"tenant": f"ext_{key}", "chroma_dir": "/toy/chroma", "cases_file": "/toy/cases"}
    (run / "launch.json").write_text(json.dumps(launch), "utf-8")
    return run.parent


def test_the_v5_template_keeps_the_frame_the_judge_reads(replay: Any) -> None:
    text = replay.V5.read_text("utf-8")
    assert "\r" not in text and text.endswith("\n")
    fields = {field for _, field, _, _ in string.Formatter().parse(text) if field}
    assert fields == {"context_block", "question"}
    filled = text.format(context_block="[1 | source=a.md]\nA.", question="Q?")
    assert judge.prompt_id(filled) == "QA_PROMPT_V5"
    assert judge.read_prompt(filled) == ("Q?", [("a.md", "A.")])
    assert judge.PROMPT_IDS["QA_PROMPT_V5"] == replay.V5_MARK
    assert judge.PROMPT_IDS["QA_PROMPT_V4"] == replay.V4_MARK
    v4 = prompts.PROMPT_REGISTRY["qa"]["text"]
    assert hashlib.sha256(v4.encode("utf-8")).hexdigest() == V4_SHA256
    assert prompts.PROMPT_REGISTRY["qa"]["prompt_id"] == replay.V4_ID


def test_a_saved_prompt_gives_back_the_question_and_documents_the_chat_joined(
    replay: Any,
) -> None:
    question, documents = replay.read_saved(_v4_prompt("What does storage cost?"))
    assert question == "What does storage cost?"
    assert documents == [(d["metadata"]["source"], d["page_content"]) for d in DOCS]
    assert judge.read_prompt(_v4_prompt("What does storage cost?")) == (question, documents)
    assert replay.read_saved(_v4_prompt("Nothing?", [])) == ("Nothing?", [])
    joined = _v4_prompt("Q?").replace("day after arrival.\n\n[2 |", "day after arrival.\n[2 |")
    with pytest.raises(ValueError, match="not joined as the chat joins them"):
        replay.read_saved(joined)


def test_the_builder_rebuilds_v4_byte_for_byte_and_v5_on_the_same_documents(
    replay: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    builder = replay.Builder(FakeModel())
    saved = _v4_prompt("What does storage cost?")
    question, documents = replay.read_saved(saved)
    _, rebuilt, fitted = builder.build(builder.v4, question, documents)
    assert rebuilt == saved and replay.same_context(documents, fitted)
    prompt, flat, fitted = builder.build(builder.v5, question, documents)
    assert replay.V5_MARK in prompt and replay.V4_MARK not in prompt
    assert flat == flatten_messages([{"role": "user", "content": prompt}])
    assert judge.read_prompt(flat) == (question, documents) and replay.same_context(
        documents, fitted
    )
    # The registry's text is put back, whatever the build.
    assert prompts.PROMPT_REGISTRY["qa"]["text"] == builder.v4
    # An override of "qa" would stand before the registry's text: the build refuses.
    monkeypatch.setitem(prompts.DEPLOYED_PROMPT_OVERRIDES, "qa", builder.v4)
    with pytest.raises(SystemExit, match="from another text than the one given"):
        builder.build(builder.v5, question, documents)


def test_an_answer_quotes_its_context_by_a_passage_of_forty_characters(replay: Any) -> None:
    documents = [("fees.md", DOCS[0]["page_content"])]
    assert replay.quoted("".join(V5_TOKENS), documents)
    assert replay.quoted('"Storage   costs ten euros a day\nfrom the fourth day" [1]', documents)
    assert not replay.quoted(V4_ANSWER, documents)
    assert not replay.quoted("Storage costs ten euros a day.", documents)  # under forty
    assert not replay.quoted("".join(V5_TOKENS), [])


def _patch_run(
    replay: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, model: FakeModel, digest: str
) -> None:
    monkeypatch.setattr(replay, "BATCHES", 1)
    monkeypatch.setattr(
        replay,
        "provider_and_settings",
        lambda runs, key: (model, SimpleNamespace(streaming_timeout_sec=3600.0)),
    )
    stand = tmp_path / "stand"
    stand.mkdir(exist_ok=True)
    (stand / "CODE_SHA").write_text(STAND + "\n", "utf-8")
    monkeypatch.setattr(replay, "WS", stand)
    calls: list[tuple[str, Any]] = []

    def ollama(path: str, payload: Any = None, timeout: float = 30) -> dict:
        calls.append((path, payload))
        if path == "/api/tags":
            return {"models": [{"name": MODEL, "digest": digest}]}
        return {}

    monkeypatch.setattr(replay, "ollama", ollama)
    monkeypatch.setattr(replay, "_ollama_calls", calls, raising=False)


def test_the_replay_answers_each_v4_case_under_v5_in_v4s_run_layout(
    replay: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runs, out = _v4_runs(tmp_path), tmp_path / "out"
    model = FakeModel()
    _patch_run(replay, monkeypatch, tmp_path, model, DIGEST)

    assert replay.run("wixqa", runs, out) == 0

    folder = out / "v5-wixqa-b01"
    launch = json.loads((folder / "launch.json").read_text("utf-8"))
    assert launch["status"] == "complete" and launch["cases"] == 3
    assert (launch["label"], launch["replay_of"], launch["code_sha"]) == (
        "v5-wixqa-b01",
        "v4-wixqa-b01",
        STAND,
    )
    assert (launch["model"], launch["model_digest"], launch["prompt_id"]) == (
        MODEL,
        DIGEST,
        "QA_PROMPT_V5",
    )
    assert launch["tenant"] == "ext_wixqa" and launch["budget_sec"] == 3600.0
    assert launch["tools_sha256"] == {
        name: hashlib.sha256((TOOLS / name).read_bytes()).hexdigest() for name in replay.TOOLS
    }
    assert launch["params"] == generation_kwargs_for_role("generate")
    # Each call is the chat's own: one user message, the "generate" role's kwargs.
    assert [kwargs for _, kwargs in model.calls] == [generation_kwargs_for_role("generate")] * 3
    loads = [payload for path, payload in replay._ollama_calls if path == "/api/generate"]
    assert loads == [{"model": MODEL, "keep_alive": "30m"}, {"model": MODEL, "keep_alive": 0}]
    for index, (case, question) in enumerate(QUESTIONS.items(), start=1):
        row = json.loads((folder / "cases" / f"{index:02d}-{case}.json").read_text("utf-8"))
        assert (row["case_id"], row["question"], row["index"]) == (case, question, index)
        assert row["answer"] == "".join(V5_TOKENS) and row["tokens"] == 2
        assert row["same_context"] and (row["documents_v4"], row["documents_v5"]) == (2, 2)
        v4 = (runs / "v4-wixqa-b01" / "prompts" / row["v4_prompt_file"]).read_text("utf-8")
        assert row["v4_prompt_sha256"] == hashlib.sha256(v4.encode("utf-8")).hexdigest()
        saved = (folder / "prompts" / row["prompt_file"]).read_text("utf-8")
        assert row["prompt_file"] == f"{index:03d}-stream.txt"
        assert judge.prompt_id(saved) == "QA_PROMPT_V5"
        assert judge.read_prompt(saved) == judge.read_prompt(v4)
        messages = model.calls[index - 1][0]
        assert flatten_messages(messages) == saved and len(messages) == 1
    stages = [
        json.loads(line) for line in (folder / "stages.jsonl").read_text("utf-8").splitlines()
    ]
    assert [(s["event"], s["prompt_file"]) for s in stages] == [
        (event, f"{n:03d}-stream.txt") for n in (1, 2, 3) for event in ("start", "end")
    ]
    # The judge's adapter reads the run as it read V4's.
    answers = judge.run_answers(folder)
    assert [a["case_id"] for a in answers] == list(QUESTIONS)
    assert {a["prompt_id"] for a in answers} == {"QA_PROMPT_V5"}

    # A whole batch is kept: running again asks nothing.
    assert replay.run("wixqa", runs, out) == 0 and len(model.calls) == 3


def test_the_replay_stops_and_resumes_where_it_stopped(
    replay: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runs, out = _v4_runs(tmp_path), tmp_path / "out"
    model = FakeModel()
    _patch_run(replay, monkeypatch, tmp_path, model, DIGEST)
    folder = out / "v5-wixqa-b01"
    out.mkdir()

    (out / "v5-wixqa.stop").touch()
    assert replay.run("wixqa", runs, out) == 5 and not model.calls
    assert json.loads((folder / "launch.json").read_text("utf-8"))["status"] == "stopped"
    (out / "v5-wixqa.stop").unlink()

    monkeypatch.setattr(replay, "ANSWER_STOP", -1.0)
    assert replay.run("wixqa", runs, out) == 4 and len(model.calls) == 1
    assert json.loads((folder / "launch.json").read_text("utf-8"))["status"] == "answer_stop"
    assert [p.name for p in (folder / "cases").iterdir()] == ["01-w0.json"]
    monkeypatch.setattr(replay, "ANSWER_STOP", 1200.0)

    model.fail = True
    assert replay.run("wixqa", runs, out) == 7 and len(model.calls) == 2
    assert json.loads((folder / "launch.json").read_text("utf-8"))["status"] == "model_error"
    assert sorted(p.name for p in (folder / "prompts").iterdir()) == ["001-stream.txt"]
    ended = json.loads((folder / "stages.jsonl").read_text("utf-8").splitlines()[-1])
    assert ended["event"] == "end" and ended["error"] == "RuntimeError"

    # A process killed between a prompt and its case leaves the prompt alone: removed, counted.
    (folder / "prompts" / "002-stream.txt").write_bytes(_v4_prompt(QUESTIONS["w1"]).encode())
    model.fail = False
    assert replay.run("wixqa", runs, out) == 0 and len(model.calls) == 4
    assert sorted(p.name for p in (folder / "prompts").iterdir()) == [
        "001-stream.txt",
        "002-stream.txt",
        "003-stream.txt",
    ]
    launch = json.loads((folder / "launch.json").read_text("utf-8"))
    assert launch["status"] == "complete"
    assert (launch["orphan_prompts"], launch["model_errors"]) == (1, 1)
    assert [a["case_id"] for a in judge.run_answers(folder)] == list(QUESTIONS)


def test_the_replay_refuses_another_model_and_a_prompt_it_cannot_rebuild(
    replay: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model = FakeModel()
    _patch_run(replay, monkeypatch, tmp_path, model, "another digest")
    assert replay.run("wixqa", _v4_runs(tmp_path), tmp_path / "out") == 6 and not model.calls

    other = tmp_path / "other"
    runs = _v4_runs(other, header="You are an assistant.")
    builder = replay.Builder(model)
    rows, failed = replay.check(builder, replay.v4_cases(runs, "wixqa"))
    assert [row["parity"] for row in rows] == [True, False, True]
    assert failed == ["v4-wixqa-b01/02-w1.json"]
    _patch_run(replay, monkeypatch, other, model, DIGEST)
    assert replay.run("wixqa", runs, other / "out") == 3 and not model.calls

    # The judge reads a carriage return as a line feed: such a prompt is refused, not replayed.
    returned = _v4_runs(tmp_path / "returned")
    path = returned / "v4-wixqa-b01" / "prompts" / "003-stream.txt"
    path.write_bytes(path.read_bytes().replace(b"14 days.", b"14 days.\r"))
    with pytest.raises(SystemExit, match="003-stream.txt: a carriage return"):
        replay.v4_cases(returned, "wixqa")


def test_the_stream_model_is_the_runtimes_ollama_provider_inside_its_wrapper(
    replay: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import config.settings as config
    import llm.providers.runtime as runtime
    from llm.providers.base import ProviderBackedLLM

    for name in (
        "LLM_PROVIDER_PROFILE",
        "OLLAMA_MODEL_NAME",
        "PROVIDER_REGISTRY_PATH",
        "MODEL_ROUTING_ENABLED",
        "OLLAMA_CONTEXT_WINDOW",
        "LLM_ROLE_PARAMS_JSON",
        "EXPERIMENT_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = config.Settings()
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    strong = runtime.build_provider_runtime(settings).strong
    assert isinstance(strong, ProviderBackedLLM)
    assert type(strong._provider).__name__ == "OllamaProvider"
    run = tmp_path / "v4-wixqa-b01"
    run.mkdir()
    recorded = {name: getattr(settings, name, None) for name in replay.SETTINGS}

    def write(values: dict) -> None:
        (run / "effective_settings.json").write_text(
            json.dumps({"all": values}, default=str), "utf-8"
        )

    write(recorded)
    llm, got = replay.provider_and_settings(tmp_path, "wixqa")
    assert got is settings and llm.model_name == replay.MODEL
    assert replay.Builder(llm).owner is llm  # its window is V4's 2,636 tokens

    write({**recorded, "streaming_timeout_sec": 1})
    with pytest.raises(SystemExit) as stopped:
        replay.provider_and_settings(tmp_path, "wixqa")
    assert stopped.value.code == 6

    write(recorded)
    fallback = ProviderBackedLLM(strong._provider, fallback_provider=strong._provider)
    monkeypatch.setattr(
        runtime, "build_provider_runtime", lambda _: SimpleNamespace(strong=fallback)
    )
    with pytest.raises(SystemExit) as stopped:
        replay.provider_and_settings(tmp_path, "wixqa")
    assert stopped.value.code == 6


def test_near_the_window_v4s_excerpt_is_rebuilt_and_v5_reads_less_of_it(replay: Any) -> None:
    builder = replay.Builder(FakeModel())
    question = "What does storage cost at terminal 7?"
    first = " ".join(f"Rule {i} of the warehouse applies to every pallet." for i in range(60))
    second = "\n\n".join(
        f"Line {i}: storage of cargo at terminal {i} costs {i} euros a day." for i in range(240)
    )
    documents = [("rules.md", first), ("fees.md", second)]
    # V4's prompt as the chat fitted it: the first document whole, the second an excerpt.
    _, saved, _ = builder.build(builder.v4, question, documents)
    held = replay.read_saved(saved)[1]
    assert held[0] == documents[0] and held[1][0] == "fees.md"
    assert len(held[1][1]) < len(second)

    rows, failed = replay.check(
        builder, [("v4-wixqa-b01", "01-w0.json", {"case_id": "w0"}, ("001-stream.txt", saved))]
    )

    row = rows[0]
    assert row["parity"] and not failed
    assert row["v5_prompt_est_tokens"] <= replay.LIMIT
    assert not row["same_context"] and row["documents_v5"] <= row["documents_v4"] == 2
    _, _, fitted = builder.build(builder.v5, question, held)
    assert fitted[0]["page_content"] == first
    assert sum(len(d["page_content"]) for d in fitted[1:]) < len(held[1][1])


def test_the_summary_holds_ids_flags_and_numbers_only(
    replay: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runs, out, records = _v4_runs(tmp_path), tmp_path / "out", tmp_path / "records"
    _patch_run(replay, monkeypatch, tmp_path, FakeModel(), DIGEST)
    assert replay.run("wixqa", runs, out) == 0

    summary = replay.summary("wixqa", runs, out, records)

    assert (summary["key"], summary["answers"], summary["whole"]) == ("wixqa", 3, True)
    assert summary["launches"][0]["status"] == "complete"
    assert summary["launches"][0]["tools_sha256"] == {
        name: hashlib.sha256((TOOLS / name).read_bytes()).hexdigest() for name in replay.TOOLS
    }
    rows = [
        json.loads(line)
        for line in (records / "v5-wixqa.cases.jsonl").read_text("utf-8").split("\n")
        if line
    ]
    assert [row["case_id"] for row in rows] == list(QUESTIONS)
    first = rows[0]
    assert first["quoted"] == {"v4": False, "v5": True} and first["same_context"]
    assert first["chunks"]["v4"] == 81 and first["stream_sec"]["v4"] == 85.123
    assert first["answer_chars"] == {"v4": len(V4_ANSWER), "v5": len("".join(V5_TOKENS))}
    assert first["truncated"] is False
    assert first["at_token_cap"] == {"v4": False, "v5": False}
    # The hashes v5_record.py holds against the judges' are the judge's adapter's own.
    assert [row["v5_prompt_sha256"] for row in rows] == [
        a["prompt_sha256"] for a in judge.run_answers(out / "v5-wixqa-b01")
    ]
    checked, _ = replay.check(replay.Builder(FakeModel()), replay.v4_cases(runs, "wixqa"))
    assert [row["v4_prompt_sha256"] for row in checked] == [
        a["prompt_sha256"] for a in judge.run_answers(runs / "v4-wixqa-b01")
    ]
    written = (records / "v5-wixqa.cases.jsonl").read_text("utf-8") + (
        records / "v5-wixqa.json"
    ).read_text("utf-8")
    for text in [*QUESTIONS.values(), V4_ANSWER, *V5_TOKENS, "Storage", "fees.md"]:
        assert text not in written


# The record: each key's ten questions, V4's class and V5's; None where V5's verdict is missing.
V4_CLASSES = {
    "wixqa": ["bad"] * 8 + ["good", "good"],
    "conditionalqa": ["bad"] * 7 + ["good", "partial_ok", "good"],
    "aircargo": ["good"] * 8 + ["bad", "partial_ok"],
}
V5_CLASSES = {
    "wixqa": ["good"] * 6 + ["partial_ok", "partial_ok", "good", "good"],
    "conditionalqa": ["good"] * 8 + ["partial_ok", None],
    "aircargo": ["good"] * 8 + ["bad", "good"],
}
CLUSTERS = {
    "wixqa": [0, 0, 1, 2, 2, 2, 3, 4, 5, 6],
    "conditionalqa": [0, 0, 1, 1, 2, 3, 4, 5, 6, 7],
}
NOT_ANSWERABLE = {"c8", "c9"}
M2 = {
    "wixqa": (["disagrees"] * 10, ["agrees"] * 8 + ["disagrees", "partial"]),
    "conditionalqa": (
        ["disagrees"] * 8 + ["right", "right"],
        ["agrees"] * 7 + ["partial", "right", "wrong"],
    ),
}
TAKEN = ("2026-10-27T00:00:00+00:00", "2026-10-27T12:00:00+00:00")
LAUNCH = ("2026-10-27T01:00:00+00:00", "2026-10-27T11:00:00+00:00")


def _write(folder: Path, name: str, data: dict, rows: list[dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(json.dumps(data), "utf-8")
    (folder / f"{name}.cases.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), "utf-8"
    )


def _prompt_sha(side: str, case: str) -> str:
    return hashlib.sha256(f"{side} prompt of {case}".encode()).hexdigest()


def _judge_rows(key: str, side: str, part: str) -> list[dict]:
    rows = []
    for index, grade in enumerate((V4_CLASSES if side == "v4" else V5_CLASSES)[key]):
        case = f"{key[0]}{index}"
        reference = part == "m2" and case not in NOT_ANSWERABLE
        row: dict[str, Any] = {
            "run": f"{side}-{key}-b01",
            "case_id": case,
            "item_id": f"{side}-{part}-{case}",
            "prompt_sha256": _prompt_sha(side, case),
            "has_reference": reference,
            "grade": grade,
            "missing": grade is None,
        }
        if grade is not None:
            declined = case == "c8"
            total = 0 if declined else 2
            row.update(
                claims_total=total,
                claims_supported=total - (grade == "bad"),
                context_has_answer=not (side == "v5" and case == "w7"),
                answers_question="declined" if declined else "full",
                defect="cut_off" if grade == "bad" and side == "v4" and index == 0 else "none",
            )
        if key in CLUSTERS:
            stratum = "not_answerable" if case in NOT_ANSWERABLE else "answerable"
            row.update(stratum="simulated" if key == "wixqa" else stratum)
            row.update(cluster=CLUSTERS[key][index])
        if part == "m2":
            row["m2"] = M2[key][side == "v5"][index]
        rows.append(row)
    return rows


def _judge_record(key: str, side: str, part: str, name: str, rows: list[dict]) -> dict:
    provenance: dict[str, Any] = {
        "references_sha256": None if key == "aircargo" else f"{key}-references",
        "references_withheld": part == "m1" and key != "aircargo",
        "salt": judge.SALT,
        "prompt_id": "QA_PROMPT_V4" if side == "v4" else "QA_PROMPT_V5",
        "instructions_sha256": hashlib.sha256(judge.INSTRUCTIONS.encode()).hexdigest(),
        "route": {"model": "claude-opus-5-5", "effort": "max"},
        "adapter_sha256": "v4-judge" if side == "v4" else JUDGE_SHA256,
        "tool_sha256": "v4-export",
        "runs": {
            f"{side}-{key}-b01": {
                "code_sha": STAND,
                "model": MODEL,
                "model_digest": DIGEST,
                "tenant": key if key == "aircargo" else f"ext_{key}",
            }
        },
    }
    data: dict[str, Any] = {
        "plan": name,
        "status": "counted",
        "provenance": provenance,
        "replies": {"admitted_cli": {"2.1.309": len(rows)}},
        "retest": {"passed": True},
    }
    if part == "m2":
        data["m2"] = {"with_reference": {}, "without_reference": {}}
    return data


def _snapshot(v4r: Any, taken: str) -> dict:
    return {
        "taken": taken,
        "ollama": {
            "server_version": v4r.OLLAMA,
            "servers": [
                {"pid": 7, "started": "2026-09-13T16:37:06+00:00", "binary": "/toy/ollama"}
            ],
        },
        "distributions": {
            "freeze_sha256": v4r.FREEZE,
            "newest": {"name": "toy", "changed": "2026-05-30T14:51:39+00:00"},
            "versions": {"langchain": "1.3.2"},
        },
    }


def _world(record: Any, root: Path) -> tuple[Path, dict]:
    """V4's committed judge records and V5's records under root, as the tools write them."""
    v4_dir = root / "reports/answer-prompt-v4/4f48fed"
    stand = root / "reports/answer-prompt-v5/4f48fed"
    tools = {
        name: hashlib.sha256((TOOLS / name).read_bytes()).hexdigest() for name in record.REPLAY
    }
    for key in KEYS:
        for side, folder in (("v4", v4_dir), ("v5", stand)):
            for part, name in record.names(key)[side].items():
                rows = _judge_rows(key, side, part)
                _write(folder, name, _judge_record(key, side, part, name, rows), rows)
        rows = _judge_rows(key, "v4", "m1")[:3]
        bridge = _judge_record(key, "v4", "m1", f"v5-bridge-{key}", rows)
        bridge["provenance"]["plan_sha256"] = record.BRIDGES[key]
        bridge["provenance"]["adapter_sha256"] = JUDGE_SHA256
        _write(stand, f"v5-bridge-{key}", bridge, rows)
        launch = {
            "label": f"v5-{key}-b01",
            "replay_of": f"v4-{key}-b01",
            "code_sha": STAND,
            "model": MODEL,
            "model_digest": DIGEST,
            "prompt_id": "QA_PROMPT_V5",
            "tools_sha256": tools,
            "started": LAUNCH[0],
            "finished": LAUNCH[1],
            "status": "complete",
        }
        answers = [
            {
                "run": f"v5-{key}-b01",
                "case_id": f"{key[0]}{index}",
                "same_context": index % 2 == 0,
                "quoted": {"v4": index == 0, "v5": index < 7},
                "truncated": False,
                "at_token_cap": {"v4": False, "v5": index == 9},
                "stream_sec": {"v4": 85.0 + index, "v5": 120.0 + index},
                "chunks": {"v4": 100, "v5": 1024 if index == 9 else 150 + index},
                "v5_prompt_sha256": _prompt_sha("v5", f"{key[0]}{index}"),
            }
            for index in range(10)
        ]
        summary = {"key": key, "launches": [launch], "answers": 10, "whole": True}
        _write(stand, f"v5-{key}", summary, answers)
        parity = [
            {
                "case_id": row["case_id"],
                "parity": True,
                "v4_prompt_sha256": _prompt_sha("v4", row["case_id"]),
            }
            for row in answers
        ]
        (stand / f"v5-{key}.check.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in parity), "utf-8"
        )
    (stand / "v5-environment.jsonl").write_text(
        "".join(json.dumps(_snapshot(record.v4r, taken)) + "\n" for taken in TAKEN), "utf-8"
    )
    return stand, {"v4_dir": v4_dir, "root": root}


def test_the_record_pairs_v5_with_v4_question_by_question(record: Any, tmp_path: Path) -> None:
    stand, folders = _world(record, tmp_path)

    got = record.build(stand, **folders)

    primary = got["primary"]
    assert primary["keys"] == ["wixqa", "conditionalqa"] and primary["n"] == 19
    assert primary["table"] == {"a": 0, "b": 15, "c": 0, "d": 4}
    assert (primary["v4"], primary["v5"], primary["difference"]) == (0.7895, 0.0, -0.7895)
    assert primary["direction"] == "falls" and "v3" not in primary
    same = got["same_context"]
    assert same["table"] == {"a": 0, "b": 8, "c": 0, "d": 2}
    wixqa, conditional, aircargo = (got["corpora"][key] for key in KEYS)
    assert wixqa["transitions"]["bad"] == {"good": 6, "partial_ok": 2, "bad": 0}
    assert wixqa["context_has_answer"] == {"same": 9, "lost": 1, "gained": 0}
    assert wixqa["defects"]["v4"]["cut_off"] == 1 and wixqa["defects"]["v5"]["cut_off"] == 0
    assert wixqa["claims_supported"]["v4"] == {"supported": 12, "total": 20, "share": 0.6}
    assert wixqa["quoted"] == {"v4": 1, "v5": 7} and wixqa["same_context"] == 5
    assert wixqa["at_token_cap"] == {"v4": 0, "v5": 1}
    assert wixqa["stream_sec"]["v5"]["median"] == 124.5
    assert conditional["pairs"] == 9
    assert conditional["unpaired"] == {"count": 1, "case_ids": ["c9"]}
    assert conditional["declines_without_answer"]["table"] == {"a": 1, "b": 0, "c": 0, "d": 0}
    assert "declines_without_answer" not in wixqa  # its gold has no question without an answer
    assert aircargo["bad"]["table"] == {"a": 1, "b": 0, "c": 0, "d": 9}
    assert "m2" not in aircargo
    # M2: `agrees` among the questions with a reference, pooled; the right declines beside it.
    assert got["recall"]["n"] == 18 and got["recall"]["table"]["c"] == 15
    assert got["recall"]["direction"] == "rises"
    assert conditional["m2"]["without_reference"]["right"] == {"v4": 2, "v5": 1}
    assert got["decision"]["decision"] == "adopted" and got["decision"]["v5_replaces_v4"]
    assert got["decision"]["reasons"] == ["fewer bad answers"]
    assert got["environment"]["snapshots"] == 2
    assert got["prompts"]["v4_sha256"] == V4_SHA256
    assert (
        got["prompts"]["v5_sha256"]
        == hashlib.sha256((TOOLS / "qa_prompt_v5.txt").read_bytes()).hexdigest()
    )
    assert set(got["tools"]) == set(record.TOOLS)
    assert "reports/answer-prompt-v5/4f48fed/v5-wixqa.check.jsonl" in got["inputs"]
    assert "reports/answer-prompt-v4/4f48fed/v4-wixqa-judge-m2.json" in got["inputs"]
    assert set(got["plans"]) >= {"v5-bridge-wixqa", "v4-aircargo-judge", "v5-wixqa-judge-m2"}

    out = tmp_path / "record.json"
    assert record.main([str(stand), str(out)], **folders) == 0
    assert b"\r" not in out.read_bytes() and json.loads(out.read_text("utf-8")) == got


def _edit(path: Path, change: Callable[[Any], Any]) -> None:
    if path.suffix == ".jsonl":
        rows = [json.loads(line) for line in path.read_text("utf-8").splitlines() if line]
        rows = change(rows)
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    else:
        path.write_text(json.dumps(change(json.loads(path.read_text("utf-8")))), "utf-8")


def _provenance(**changes: Any) -> Callable[[dict], dict]:
    return lambda data: {**data, "provenance": {**data["provenance"], **changes}}


def _launch(**changes: Any) -> Callable[[dict], dict]:
    return lambda data: {**data, "launches": [{**data["launches"][0], **changes}]}


def _tenant(data: dict) -> dict:
    runs = {label: {**run, "tenant": "other"} for label, run in data["provenance"]["runs"].items()}
    return _provenance(runs=runs)(data)


def _restarted(ollama: dict) -> dict:
    server = {"pid": 8, "started": "2026-10-27T05:00:00+00:00", "binary": "/toy/ollama"}
    return {**ollama, "servers": [server]}


V5_DIR = "reports/answer-prompt-v5/4f48fed"


@pytest.mark.parametrize(
    ("path", "change", "match"),
    [
        (
            "v5-wixqa-judge-m1.json",
            _provenance(prompt_id="QA_PROMPT_V4"),
            "v5-wixqa-judge-m1: its plan reads QA_PROMPT_V4",
        ),
        (
            "v5-wixqa-judge-m1.json",
            _provenance(references_withheld=False),
            "the m1 plan withholds the references",
        ),
        (
            "v5-conditionalqa-judge-m2.json",
            _provenance(salt="other"),
            "not V4's judge, its salt differs",
        ),
        ("v5-aircargo-judge.json", _tenant, "answers of another model or tenant than V4's"),
        (
            "v5-bridge-wixqa.json",
            _provenance(plan_sha256="0" * 64),
            "v5-bridge-wixqa: not the bridge the spec registered",
        ),
        (
            "v5-bridge-aircargo.json",
            _provenance(prompt_id="QA_PROMPT_V5"),
            "not V4's plan, its prompt_id differs",
        ),
        (
            "v5-bridge-conditionalqa.cases.jsonl",
            lambda rows: [{**rows[0], "grade": "partial_ok"}, *rows[1:]],
            "its first verdicts are not V4's",
        ),
        ("v5-wixqa.json", lambda data: {**data, "whole": False}, "v5-wixqa: not answered whole"),
        (
            "v5-wixqa.json",
            _launch(code_sha="1" * 40),
            "v5-wixqa-b01 is not a whole batch of the stand",
        ),
        (
            "v5-aircargo.json",
            _launch(tools_sha256={"replay.py": "0" * 64}),
            "ran other tools than the registered",
        ),
        (
            "v5-conditionalqa.check.jsonl",
            lambda rows: [{**rows[0], "parity": False}, *rows[1:]],
            "a V4 prompt was not rebuilt byte for byte",
        ),
        (
            "v5-conditionalqa.check.jsonl",
            lambda rows: rows[1:] + [{"case_id": "other", "parity": True}],
            "its parity check read other questions",
        ),
        (
            "v5-wixqa-judge-m2.cases.jsonl",
            lambda rows: [{**rows[0], "case_id": "other"}, *rows[1:]],
            "wixqa: v5-wixqa-judge-m2 holds other questions than v5-wixqa",
        ),
        (
            "v5-environment.jsonl",
            lambda rows: [rows[0], {**rows[1], "taken": "2026-10-27T10:00:00+00:00"}],
            "not read before V4's first answer and after its last",
        ),
        (
            "v5-environment.jsonl",
            lambda rows: [rows[0], {**rows[1], "ollama": _restarted(rows[1]["ollama"])}],
            "v5-environment.jsonl: not stage 2's one Ollama server",
        ),
        (
            "v5-wixqa-judge-m1.json",
            _provenance(adapter_sha256="0" * 64),
            "v5-wixqa-judge-m1: read by another judge than the registered",
        ),
        (
            "v5-bridge-wixqa.json",
            _provenance(tool_sha256="another export"),
            "v5-bridge-wixqa: exported by another tool than V4's",
        ),
        (
            "v5-wixqa.check.jsonl",
            lambda rows: [{**rows[0], "v4_prompt_sha256": "0" * 64}, *rows[1:]],
            "v4-wixqa-judge-m1: graded other prompts than the replay's",
        ),
        (
            "v5-aircargo.cases.jsonl",
            lambda rows: [{**rows[0], "v5_prompt_sha256": "0" * 64}, *rows[1:]],
            "v5-aircargo-judge: graded other prompts than the replay's",
        ),
    ],
)
def test_the_record_refuses_inputs_it_cannot_pair(
    record: Any, tmp_path: Path, path: str, change: Callable[[Any], Any], match: str
) -> None:
    stand, folders = _world(record, tmp_path)
    _edit(tmp_path / V5_DIR / path, change)

    with pytest.raises(SystemExit, match=re.escape(match)):
        record.build(stand, **folders)


def test_a_plan_not_counted_leaves_no_decision_and_its_part_unread(
    record: Any, tmp_path: Path
) -> None:
    stand, folders = _world(record, tmp_path)
    _edit(stand / "v5-conditionalqa-judge-m2.json", lambda data: {**data, "status": "NOT_EVIDENCE"})
    got = record.build(stand, **folders)["decision"]
    assert got["decision"] == "NOT_EVIDENCE" and got["harm"] == []
    assert got["not_counted"] == {"conditionalqa": ["v5-conditionalqa-judge-m2"]}

    _edit(stand / "v5-bridge-wixqa.json", lambda data: {**data, "status": "NOT_EVIDENCE"})
    got = record.build(stand, **folders)["decision"]
    assert got["reasons"] == ["a plan not counted: v5-bridge-wixqa, v5-conditionalqa-judge-m2"]
    for name in ("v5-environment.jsonl", "v5-aircargo.check.jsonl", "v5-bridge-wixqa.json"):
        (stand / name).unlink()
        with pytest.raises(SystemExit, match=f"{re.escape(name)}: no such record"):
            record.build(stand, **folders)


def test_a_key_not_answered_whole_is_left_out_and_named(record: Any, tmp_path: Path) -> None:
    stand, folders = _world(record, tmp_path)
    got = record.build(stand, ("wixqa", "conditionalqa"), **folders)
    assert got["keys"] == ["wixqa", "conditionalqa"] and "aircargo" not in got["corpora"]
    assert got["decision"]["decision"] == "NOT_EVIDENCE"
    assert got["decision"]["reasons"] == ["not answered whole, no harm read: aircargo"]
    with pytest.raises(SystemExit, match="--keys names some of"):
        record.build(stand, ("wixqa", "wixqa"), **folders)
    with pytest.raises(SystemExit, match="usage"):
        record.main([str(stand), "a", "b"], **folders)


def test_the_decision_is_read_in_the_specs_table_in_its_order(record: Any) -> None:
    def read(
        pooled: str = "not detected",
        bad: dict[str, str] | None = None,
        good: dict[str, str] | None = None,
        guard: str = "not detected",
        recall: str | None = "not detected",
        keys: tuple[str, ...] = KEYS,
        readable: tuple[str, ...] | None = None,
        not_counted: dict[str, list[str]] | None = None,
    ) -> dict:
        corpora: dict[str, dict] = {
            key: {
                "bad": {"direction": (bad or {}).get(key, "not detected")},
                "good": {"direction": (good or {}).get(key, "not detected")},
            }
            for key in keys
        }
        if "conditionalqa" in keys:
            corpora["conditionalqa"]["declines_without_answer"] = {"direction": guard}
        primary = {
            "keys": [k for k in ("wixqa", "conditionalqa") if k in keys],
            "direction": pooled,
        }
        read_recall = None if recall is None else {"direction": recall}
        return record.decision(
            primary,
            read_recall,
            corpora,
            list(keys),
            list(keys if readable is None else readable),
            not_counted or {},
        )

    # 3: fewer bad answers, pooled: V5 replaces V4.
    assert read("falls") == {
        "decision": "adopted",
        "v5_replaces_v4": True,
        "reasons": ["fewer bad answers"],
        "harm": [],
        "not_counted": {},
        "not_run": [],
    }
    # 4: no gain, a key's own fall included.
    assert read(bad={"wixqa": "falls"})["reasons"] == ["no gain"]
    assert not read()["v5_replaces_v4"]
    # 1: harm decides before all else, each of its five kinds; the good share falling with the
    # bad share is no harm.
    harmed = read(
        "rises",
        bad={"aircargo": "rises", "conditionalqa": "falls"},
        good={"wixqa": "falls", "conditionalqa": "falls"},
        guard="falls",
        recall="falls",
    )
    assert (harmed["decision"], harmed["v5_replaces_v4"]) == ("not adopted", False)
    assert (
        harmed["reasons"]
        == harmed["harm"]
        == [
            "wixqa: the good share falls, the bad share does not",
            "conditionalqa: fewer declines where the gold says not answerable",
            "aircargo: the bad share rises",
            "pooled: the bad share rises",
            "pooled: M2's agreement with the reference falls",
        ]
    )
    assert read("falls", recall="falls")["decision"] == "not adopted"
    assert read("falls", recall=None)["decision"] == "adopted"
    # 2: an M1 plan or a bridge not counted takes its key's harm, and the pooled one's, with it.
    unstable = read(
        "rises",
        bad={"wixqa": "rises"},
        readable=("conditionalqa", "aircargo"),
        not_counted={"wixqa": ["v5-bridge-wixqa"]},
    )
    assert (unstable["decision"], unstable["harm"]) == ("NOT_EVIDENCE", [])
    assert unstable["reasons"] == ["a plan not counted: v5-bridge-wixqa"]
    # An M2 plan not counted leaves the key's M1 harm read.
    m2_only = read(
        bad={"conditionalqa": "rises"},
        recall=None,
        not_counted={"conditionalqa": ["v5-conditionalqa-judge-m2"]},
    )
    assert m2_only["harm"] == ["conditionalqa: the bad share rises"]
    # Harm on the first key stops the others; without harm, a key not answered leaves none.
    early = read("rises", bad={"wixqa": "rises"}, keys=("wixqa",), recall=None)
    assert (early["decision"], early["harm"]) == ("not adopted", ["wixqa: the bad share rises"])
    assert early["not_run"] == ["conditionalqa", "aircargo"]


def test_the_chain_runs_the_keys_in_the_specs_order_checking_before_answering(
    replay: Any, record: Any
) -> None:
    chain = (TOOLS / "v5_chain.sh").read_text("utf-8")
    assert "\r" not in chain
    assert re.search(r'^KEYS="(.+)"$', chain, re.M)[1].split() == list(record.KEYS)
    marks = dict(re.findall(r'^(V[45])_MARK="(.+)"$', chain, re.M))
    assert marks["V5"].replace("\\", "") == replay.V5_MARK
    assert marks["V4"].replace("\\", "") == replay.V4_MARK
    loop = chain[chain.index("for key in $KEYS; do") :]
    assert loop.index("replay check") < loop.index("replay run") < loop.index("v5prompts")
    # The parity rows are written under the name the record reads them by.
    assert '> "$V/v5-$key.check.jsonl"' in loop
    assert 'f"v5-{key}.check.jsonl"' in (TOOLS / "v5_record.py").read_text("utf-8")
    assert "S=/Users/julia/RAG_new_chat_4f48fed" in chain
    assert replay.KEYS == record.KEYS and replay.TOOLS == record.REPLAY
    assert record.STAND.startswith(Path(record.V4_DIR).name)


def test_the_spec_names_the_reading_as_it_stands(record: Any) -> None:
    """The reading is frozen at registration: the spec names the SHA-256 of each tool and of
    this test, and the bridges' plans; a later change shows here (a marked error fix updates the
    spec)."""
    spec = (ROOT / "docs/specs/answer-prompt-v5.md").read_text("utf-8")
    named = dict(
        re.findall(r"`((?:reports|scripts|tests)/[\w./-]+\.(?:py|sh|txt))` `([0-9a-f]{64})`", spec)
    )
    assert sorted(named) == [
        "reports/answer-prompt-v4/tools/stand_env.py",
        "reports/answer-prompt-v5/tools/qa_prompt_v5.txt",
        "reports/answer-prompt-v5/tools/replay.py",
        "reports/answer-prompt-v5/tools/v5_chain.sh",
        "reports/answer-prompt-v5/tools/v5_record.py",
        "scripts/chat_answer_judge.py",
        "tests/test_answer_prompt_v5.py",
    ]
    for path, digest in named.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    assert named["scripts/chat_answer_judge.py"] == record.JUDGE_SHA256 == JUDGE_SHA256
    for digest in record.BRIDGES.values():
        assert f"`{digest}`" in spec

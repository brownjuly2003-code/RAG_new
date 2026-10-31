"""reports/stage4-step2b/tools: the replay's cold continuations and the reader's read.

docs/specs/stage4-step2b-continuation-labels.md. The replay's request is held against the
chat's own (api.routers.conversation._stream_continuation_self_eval), byte for byte, on both
stream paths, with only the /api/chat transport a recording fake. Its two phases read toy runs -
a V4 run of the 80's kind and step 2's runs s2-both and s2-both-r2, the chat's own prompts of
short documents, as tests/test_answer_prompt_v5.py writes them - with the stream model's provider,
Ollama's endpoints and the host's ps faked. The reader reads synthetic phase folders beside the
committed plan, judge labels and step 2's records, which hold ids, SHA-256 strings, grades and
scores only, and once the replay's own folders of the toy runs. No network, Ollama, API or model.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from agent import prompts
from agent.prompts import PROMPT_REGISTRY, build_qa_prompt, build_self_eval_continuation_prompt
from api.routers import conversation
from llm import role_params
from llm.providers import ollama as ollama_module
from llm.providers.base import ProviderBackedLLM, estimate_window_tokens, flatten_messages
from llm.providers.ollama import OllamaProvider

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports" / "stage4-step2b" / "tools"
SIGNAL_RECORD = ROOT / "reports" / "handover-signal" / "tools" / "signal_record.py"
PLAN = ROOT / "reports" / "handover-signal" / "d260d95" / "plan.json"
LABELS = ROOT / "reports" / "answer-prompt-v4" / "4f48fed" / "v4-aircargo-judge.cases.jsonl"
STEP2_DIR = ROOT / "reports" / "stage4-step2" / "57420db"
SPEC = ROOT / "docs" / "specs" / "stage4-step2b-continuation-labels.md"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
DIGEST = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
# The commit the fixtures' launches name; the reader's CODE_SHA is set to it by `named` alone.
STAND = "57420db746e0510465bb5a08b7610e092b32e650"
PLACEHOLDER = "<the stand's commit>"
PLANTED = "PLANTED-текст"
# Ollama's counters of a continuation as /api/chat reports them (nanoseconds).
OLLAMA_COUNTERS = {
    "prompt_eval_count": 2650,
    "prompt_eval_duration": 74_000_000_000,
    "eval_count": 2,
    "eval_duration": 310_000_000,
}


def load(path: Path, name: str) -> Any:
    """A tool as a module of its own name; the sys.path entries it adds are taken back."""
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


def _v5() -> Any:
    """V5's replay as step2b_replay.py loads it, once; its sys.path entry taken back."""
    saved = list(sys.path)
    try:
        return step2b.v5()
    finally:
        sys.path[:] = saved


step2b = load(TOOLS / "step2b_replay.py", "stage4_step2b_replay")
reader = load(TOOLS / "step2b_reader.py", "stage4_step2b_reader")
v5 = _v5()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write(path: Path, text: str) -> None:
    """Bytes, not write_text: no newline translation on any machine."""
    path.write_bytes(text.encode("utf-8"))


def _jsonl(rows: Sequence[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


# --- the request: the chat's own continuation, on both stream paths --------------------------

PROMPT = "  Контекст:\n[1 | source=warranty.md]\nЗаявку подают письменно.\n\nQuestion: how?\n"
ANSWER = " Письменно [1].\n"


def _transport(calls: list[dict[str, Any]], replies: Sequence[Any] = ()) -> Callable[..., Any]:
    """A recording stand-in for llm.providers.ollama._post_chat: each call takes the next of
    `replies` - a reply's text, or an error it raises - and "91" once they run out."""
    queue = list(replies)

    def _post_chat(url: str, payload: dict[str, Any], *, timeout_sec: float) -> dict[str, Any]:
        calls.append({"url": url, "payload": payload, "timeout_sec": timeout_sec})
        reply = queue.pop(0) if queue else "91"
        if isinstance(reply, BaseException):
            raise reply
        message = {"role": "assistant", "content": reply}
        body = {"model": payload["model"], "message": message, "done": True}
        return {**body, "done_reason": "stop", **OLLAMA_COUNTERS}

    return _post_chat


def _provider(**overrides: Any) -> Any:
    """The chat's OllamaProvider of the stand's model. Typed Any: statically it is no LLMProvider,
    lacking generate_batch, as in the wrappers of tests/test_stream_self_eval_continuation.py."""
    values: dict[str, Any] = {
        "model_name": MODEL,
        "base_url": "http://ollama.test",
        "timeout_sec": 60,
        "input_price_per_1m_tokens": 0,
        "output_price_per_1m_tokens": 0,
        # The stand ran at 4,096; the code default is 3,584 since the stage-4 package.
        "context_window": 4096,
    }
    values.update(overrides)
    return OllamaProvider(**values)


def _stream(stream_path: str, num_ctx: int) -> tuple[Any, Any]:
    """The stream model and the settings the chat hands its continuation, by the answer's path:
    the provider's stream, or the raw one posted to settings' server."""
    if stream_path == "provider":
        return ProviderBackedLLM(_provider(context_window=num_ctx)), SimpleNamespace()
    settings = SimpleNamespace(
        ollama_model_name=MODEL,
        ollama_base_url="http://ollama.test",
        ollama_request_timeout_sec=45.0,
    )
    return None, settings


def _both(
    monkeypatch: pytest.MonkeyPatch,
    stream_path: str,
    *,
    num_ctx: int = 4096,
    answer: str = ANSWER,
    replies: Sequence[Any] = (),
) -> SimpleNamespace:
    """One answer's continuation by the chat and by the replay: the chat's entry and requests,
    the replay's line and requests, each side with a transport of its own."""
    model, settings = _stream(stream_path, num_ctx)
    given = {"stream_path": stream_path, "settings": settings, "context_window": num_ctx}
    live: list[dict[str, Any]] = []
    monkeypatch.setattr(ollama_module, "_post_chat", _transport(live, replies))
    entry = asyncio.run(
        conversation._stream_continuation_self_eval(
            model, prompt=PROMPT, answer=answer, mode="continuation", **given
        )
    )
    mine: list[dict[str, Any]] = []
    monkeypatch.setattr(ollama_module, "_post_chat", _transport(mine, replies))
    got = step2b.request(model, prompt=PROMPT, answer=answer, **given)
    return SimpleNamespace(entry=entry, live=live, got=got, mine=mine)


def _wire(call: dict[str, Any]) -> tuple[str, float, bytes]:
    """A request as it leaves: the URL, the timeout and the JSON body's bytes."""
    body = json.dumps(call["payload"], ensure_ascii=False).encode("utf-8")
    return call["url"], call["timeout_sec"], body


def _but_seconds(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entry.items() if key != "sec"}


@pytest.mark.parametrize(("stream_path", "num_ctx"), [("provider", 4096), ("raw", 8192)])
@pytest.mark.parametrize(
    ("reply", "score", "outcome"),
    [("91", 91, "scored"), (" 91. ", 91, "scored"), ("80/100", -1, "not one integer")],
)
def test_the_replay_sends_the_chats_own_continuation_byte_for_byte(
    monkeypatch: pytest.MonkeyPatch,
    stream_path: str,
    num_ctx: int,
    reply: str,
    score: int,
    outcome: str,
) -> None:
    both = _both(monkeypatch, stream_path, num_ctx=num_ctx, replies=[reply])

    assert len(both.live) == len(both.mine) == 1
    assert _wire(both.mine[0]) == _wire(both.live[0])
    messages = both.mine[0]["payload"]["messages"]
    assert messages == step2b.continuation(PROMPT, ANSWER, stream_path=stream_path)
    # The first turn as the answer's path sent it, the answer as it streamed, the instruction.
    first = {"provider": "USER:\n" + PROMPT.strip(), "raw": PROMPT}[stream_path]
    assert [message["content"].encode("utf-8") for message in messages] == [
        first.encode("utf-8"),
        ANSWER.encode("utf-8"),
        build_self_eval_continuation_prompt().encode("utf-8"),
    ]
    assert [message["role"] for message in messages] == ["user", "assistant", "user"]
    options = both.mine[0]["payload"]["options"]
    assert options == {"num_ctx": num_ctx, "num_predict": 128, "temperature": 0.0}
    # The chat's entry but its seconds; the line keeps what the chat folds into -1.
    assert _but_seconds({key: both.got[key] for key in both.entry}) == _but_seconds(both.entry)
    assert (both.got["score"], both.got["outcome"], both.got["error"]) == (score, outcome, None)
    limit = conversation._continuation_input_limit(num_ctx, 128)
    assert (both.got["num_ctx"], both.got["input_limit"]) == (num_ctx, limit)
    assert (both.got["reply_chars"], both.got["done_reason"]) == (len(reply), "stop")
    assert both.got["prompt_tokens"] == OLLAMA_COUNTERS["prompt_eval_count"]


def _tokens(answer: str) -> int:
    turns = step2b.continuation(PROMPT, answer, stream_path="provider")
    return estimate_window_tokens(flatten_messages(turns))


def test_the_replay_refuses_the_window_the_chat_refuses_and_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    num_ctx = 1024
    limit = conversation._continuation_input_limit(num_ctx, 128)
    # Digits weigh one token each: the shortest answer of sevens past the limit.
    over = next(n for n in range(1, num_ctx) if _tokens("7" * n) > limit)

    both = _both(monkeypatch, "provider", num_ctx=num_ctx, answer="7" * over)
    assert (both.entry["score"], both.live, both.mine) == (-1, [], [])
    assert {key: both.got[key] for key in both.entry} == both.entry
    assert (both.got["outcome"], both.got["input_limit"]) == ("window", limit)
    assert both.got["est_input_tokens"] == _tokens("7" * over)

    both = _both(monkeypatch, "provider", num_ctx=num_ctx, answer="7" * (over - 1))
    assert (both.entry["score"], both.got["score"], both.got["outcome"]) == (91, 91, "scored")
    assert _wire(both.mine[0]) == _wire(both.live[0])


@pytest.mark.parametrize("error", [httpx.ConnectError(PLANTED), httpx.ReadTimeout(PLANTED)])
def test_a_failed_call_is_the_chats_no_score_and_the_line_keeps_its_type_alone(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    both = _both(monkeypatch, "provider", replies=[error])

    assert len(both.live) == len(both.mine) == 1 and both.entry["score"] == -1
    assert _wire(both.mine[0]) == _wire(both.live[0])
    assert (both.got["outcome"], both.got["score"]) == ("error", -1)
    assert both.got["error"] == type(error).__name__
    assert (both.got["reply_chars"], both.got["done_reason"], both.got["prompt_tokens"]) == (
        None,
        None,
        None,
    )
    assert "PLANTED" not in json.dumps(both.got)


@pytest.mark.parametrize("stream_path", [None, "graph"])
def test_an_answer_from_no_ollama_path_stops_the_replay_rather_than_scoring_it(
    stream_path: str | None,
) -> None:
    with pytest.raises(SystemExit, match="names no Ollama provider"):
        step2b.request(
            ProviderBackedLLM(_provider()),
            stream_path=stream_path,
            settings=SimpleNamespace(),
            context_window=4096,
            prompt=PROMPT,
            answer=ANSWER,
        )


# --- the phases: toy runs, the stream model's provider, Ollama and the host's ps faked ---------

DOCS = [
    {
        "page_content": f"{PLANTED}: storage costs ten euros a day.",
        "metadata": {"source": "fees.md"},
    },
    {
        "page_content": "Claims are filed within 14 days.\n\nA late claim needs the manager's word.",
        "metadata": {"source": "claims.md"},
    },
]
RUN = "v4-aircargo-b01"
# The plan's five answers in its order, each with the judge's grade and answers_question.
JUDGED = {
    "aircargo-g1": ("good", "full"),
    "aircargo-t1": ("bad", "full"),
    "aircargo-p1": ("partial_ok", "partial"),
    "aircargo-g2": ("good", "full"),
    "aircargo-t2": ("partial_ok", "declined"),
}
# The 80's order: the targets (bad, or declined), then the goods, each in the plan's order.
ORDER = [
    (1, "target", "aircargo-t1"),
    (2, "target", "aircargo-t2"),
    (3, "good", "aircargo-g1"),
    (4, "good", "aircargo-g2"),
]
# Step 2's runs: each case's id and its result's warm continuation and classic scores - None:
# the classic's side missing, so step 2's reader did not read the ask.
STEP2_CASES: dict[str, tuple[tuple[str, int, int | None], ...]] = {
    "s2-both": (("aircargo-b1", 100, 85), ("aircargo-b2", 100, 85), ("aircargo-b3", 95, 60)),
    "s2-both-r2": (("aircargo-b1", 100, 85), ("aircargo-b3", 90, None), ("aircargo-b4", 70, -1)),
}
# A case whose stream timed out: not delivered.
UNDELIVERED = {("s2-both", "aircargo-b2")}
# The bridge's order: the asks step 2 read, its runs in their order.
BRIDGE = [
    (1, "s2-both", "aircargo-b1"),
    (2, "s2-both", "aircargo-b3"),
    (3, "s2-both-r2", "aircargo-b1"),
    (4, "s2-both-r2", "aircargo-b4"),
]
# What a line holds beside its answer's ids: checks, enums, numbers and SHA-256 strings.
ANSWER_KEYS = {
    "phase",
    "n",
    "segment",
    "checks",
    "stream_path",
    "sent_answer_sha256",
    "answer_chars",
    "started",
    "finished",
    "num_ctx",
    "est_input_tokens",
    "input_limit",
    "error",
    "reply_chars",
    "done_reason",
    "outcome",
    "score",
    "sec",
    "prompt_tokens",
    "prompt_sec",
    "eval_tokens",
    "eval_sec",
    "reload",
}
LABEL_KEYS = ANSWER_KEYS | set(reader.IDS["labels"])
BRIDGE_KEYS = (
    ANSWER_KEYS
    | set(reader.IDS["bridge"])
    | {"prompt_file", "prompt_sha256", "answer_sha256", "warm"}
)


def _v4_prompt(question: str) -> str:
    """V4's stream prompt as the stand saved it: the chat's prompt, flattened."""
    return flatten_messages([{"role": "user", "content": build_qa_prompt(question, DOCS)}])


def _question(case_id: str) -> str:
    return f"{PLANTED}: what does {case_id} ask?"


def _answer(case_id: str) -> str:
    """The answer as it streamed: a leading space and a final newline, which nothing strips."""
    return f" {PLANTED} answers {case_id} [1].\n"


def _side(score: int) -> dict[str, Any]:
    """A self-evaluation as step 2's result keeps it: the score, the seconds, Ollama's counters."""
    counters = {"prompt_tokens": 2590, "prompt_sec": 7.663, "eval_tokens": 4, "eval_sec": 0.74}
    return {"score": score, "sec": 8.635, **counters}


def _streamed(case_id: str, question: str, answer: str, result: dict[str, Any]) -> dict[str, Any]:
    """A case as live_runner.py keeps it: three token events, then the result."""
    tokens = [answer[:4], answer[4:9], answer[9:]]
    events: list[dict[str, Any]] = [{"type": "token", "token": t} for t in tokens]
    events.append({"type": "result", "answer": answer, "answer_source": "stream", **result})
    case: dict[str, Any] = {"case_id": case_id, "question": question, "answer": answer}
    case.update(tokens=len(tokens), events=events, result_sec=90.0)
    return case


def _stages(prompt_file: str, answer: str) -> list[dict[str, Any]]:
    """The stand's stream rows of a prompt: its start and its end."""
    stream: dict[str, Any] = {"stage": "ollama.generate_stream", "prompt_file": prompt_file}
    end = {**stream, "event": "end", "chunks": 3, "output_chars": len(answer), "error": None}
    return [{**stream, "event": "start"}, {**end, "wall_sec": 80.0, "first_chunk_sec": 61.5}]


def _run_folder(run: Path) -> None:
    """A run's folders and its warm-up, which the replay skips."""
    (run / "prompts").mkdir(parents=True)
    (run / "cases").mkdir()
    _write(run / "prompts" / "000-stream.txt", _v4_prompt("warm up"))
    warm = {"case_id": "warmup-1", "question": "warm up", "answer": "x", "events": []}
    _write(run / "cases" / "00-warmup-1.json", json.dumps(warm))


def _world(root: Path) -> tuple[Path, Path, Path]:
    """V4's run v4-aircargo-b01 as the stand saved it - a warm-up and five answered cases - and
    the plan of the five and the judge's labels: (V4_RUNS, PLAN, LABELS)."""
    run = root / "runs" / RUN
    _run_folder(run)
    stages: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    for index, (case_id, (grade, answers)) in enumerate(JUDGED.items(), start=1):
        prompt_file, case_file = f"{2 * index - 1:03d}-stream.txt", f"{index:02d}-{case_id}.json"
        saved, answer = _v4_prompt(_question(case_id)), _answer(case_id)
        _write(run / "prompts" / prompt_file, saved)
        _write(run / "prompts" / f"{2 * index:03d}-generate.txt", f"{PLANTED} self-eval")
        case = _streamed(case_id, _question(case_id), answer, {})
        _write(run / "cases" / case_file, json.dumps(case, ensure_ascii=False))
        stages += _stages(prompt_file, answer)
        sha = _digest(saved)
        item: dict[str, Any] = {"item": index, "run": RUN, "case_id": case_id}
        item.update(case_file=case_file)
        item.update(
            prompt_file=prompt_file, prompt_sha256=sha, answer_sha256=_digest(answer.strip())
        )
        items.append({**item, "quality_score": 85, "quality_source": "llm"})
        labels.append({"run": RUN, "case_id": case_id, "prompt_sha256": sha, "missing": False})
        labels[-1].update(grade=grade, answers_question=answers)
    _write(run / "stages.jsonl", _jsonl(stages))
    plan, labels_path = root / "plan.json", root / "labels.jsonl"
    _write(plan, json.dumps({"items": items}))
    _write(labels_path, _jsonl(labels))
    return run.parent, plan, labels_path


def _sides(warm: int, classic: int | None) -> dict[str, Any]:
    both = {"continuation": _side(warm)}
    if classic is not None:
        both["classic"] = _side(classic)
    return both


def _step2_world(root: Path) -> Path:
    """Step 2's runs as the stand saved them, laid out as V4's - each a warm-up and three cases,
    each result with the self-evaluations STEP2_CASES gives it: STEP2_RUNS."""
    step2 = root / "step2"
    for label, cases in STEP2_CASES.items():
        run = step2 / label
        _run_folder(run)
        stages: list[dict[str, Any]] = []
        for index, (case_id, warm, classic) in enumerate(cases, start=1):
            prompt_file = f"{2 * index - 1:03d}-stream.txt"
            question, answer = _question(case_id), _answer(case_id)
            _write(run / "prompts" / prompt_file, _v4_prompt(question))
            _write(run / "prompts" / f"{2 * index:03d}-generate.txt", f"{PLANTED} self-eval")
            route = "timeout" if (label, case_id) in UNDELIVERED else "auto"
            result = {"route": route, "self_eval_both": _sides(warm, classic)}
            case = _streamed(case_id, question, answer, result)
            path = run / "cases" / f"{index:02d}-{case_id}.json"
            _write(path, json.dumps(case, ensure_ascii=False))
            stages += _stages(prompt_file, answer)
        _write(run / "stages.jsonl", _jsonl(stages))
    return step2


def _step2_records(step2: Path, folder: Path) -> Path:
    """Step 2's records of the toy runs, as far as the reader reads them: each ask's index and
    case, its case file's SHA-256, whether step 2 read it and its two self-evaluations."""
    folder.mkdir()
    for label, name in reader.STEP2_RECORDS.items():
        asks = []
        for index, (case_id, warm, classic) in enumerate(STEP2_CASES[label], start=1):
            path = step2 / label / "cases" / f"{index:02d}-{case_id}.json"
            read = (label, case_id) not in UNDELIVERED and classic is not None
            ask = {"index": index, "case_id": case_id, "sha256": _sha(path), "read": read}
            asks.append({**ask, "self_eval": _sides(warm, classic)})
        _write(folder / name, json.dumps({"run": {"label": label, "asks": asks}}))
    return folder


@pytest.fixture
def toy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """The toy runs, the stand's CODE_SHA, the classes' sizes 2 and 2, and the fakes: V5's stream
    model; Ollama's endpoints, whose /api/ps holds the model from its load to its unload; the
    host's ps, which lists no llama-server; and the /api/chat transport."""
    runs, plan, labels = _world(tmp_path)
    step2 = _step2_world(tmp_path)
    stand = tmp_path / "stand"
    stand.mkdir()
    _write(stand / "CODE_SHA", STAND + "\n")
    monkeypatch.setattr(step2b, "WS", stand)
    monkeypatch.setattr(step2b, "TARGETS", 2)
    monkeypatch.setattr(step2b, "GOODS", 2)
    monkeypatch.setattr(step2b, "POLL_SEC", 0.0)
    model = ProviderBackedLLM(_provider())
    monkeypatch.setattr(v5, "BATCHES", 1)
    monkeypatch.setattr(v5, "provider_and_settings", lambda runs, key: (model, SimpleNamespace()))
    endpoints: list[tuple[str, Any]] = []
    held: list[str] = []

    def ollama(path: str, payload: Any = None, timeout: float = 30) -> dict[str, Any]:
        endpoints.append((path, payload))
        if path == "/api/tags":
            return {"models": [{"name": MODEL, "digest": DIGEST}]}
        if path == "/api/ps":
            return {"models": [{"name": name} for name in held]}
        if path == "/api/generate":
            if payload["keep_alive"] == 0:
                held[:] = [name for name in held if name != payload["model"]]
            elif payload["model"] not in held:
                held.append(payload["model"])
        return {}

    monkeypatch.setattr(v5, "ollama", ollama)
    monkeypatch.setattr(step2b, "llama_servers", lambda *args: 0)
    chat: list[dict[str, Any]] = []
    monkeypatch.setattr(ollama_module, "_post_chat", _transport(chat))
    run_dir = tmp_path / "step2b"
    return SimpleNamespace(
        runs=runs,
        plan=plan,
        labels=labels,
        step2=step2,
        run_dir=run_dir,
        bridge_out=run_dir / "bridge",
        labels_out=run_dir / "labels",
        chat=chat,
        endpoints=endpoints,
        held=held,
    )


def _run(toy: SimpleNamespace, **kwargs: Any) -> int:
    return int(step2b.run(toy.runs, toy.plan, toy.labels, toy.labels_out, **kwargs))


def _bridge(toy: SimpleNamespace, **kwargs: Any) -> int:
    return int(step2b.bridge(toy.runs, toy.step2, toy.bridge_out, **kwargs))


def _launch(folder: Path) -> dict[str, Any]:
    return dict(json.loads((folder / "launch.json").read_text("utf-8")))


def _lines(folder: Path) -> list[dict[str, Any]]:
    return _rows(folder / "continuations.jsonl")


def _paths(toy: SimpleNamespace) -> list[str]:
    return [path for path, _ in toy.endpoints]


def _keep_alive(toy: SimpleNamespace) -> list[Any]:
    return [payload["keep_alive"] for path, payload in toy.endpoints if path == "/api/generate"]


def _no_text(folder: Path) -> None:
    for path in folder.iterdir():
        data = path.read_bytes()
        assert b"PLANTED" not in data and b"\r" not in data, path.name


def test_the_replay_asks_each_labelled_answer_in_its_order_and_writes_no_text(
    toy: SimpleNamespace,
) -> None:
    assert _run(toy) == 0

    out = toy.labels_out
    lines = _lines(out)
    # The targets first, then the goods; the partial answer is not asked.
    assert [(line["n"], line["class"], line["case_id"]) for line in lines] == ORDER
    run = toy.runs / RUN
    for line, call in zip(lines, toy.chat, strict=True):
        saved = (run / "prompts" / line["prompt_file"]).read_bytes().decode("utf-8")
        case = json.loads((run / "cases" / line["case_file"]).read_text("utf-8"))
        assert call["payload"]["messages"] == [
            {"role": "user", "content": saved},
            {"role": "assistant", "content": case["answer"]},
            {"role": "user", "content": build_self_eval_continuation_prompt()},
        ]
        assert call["url"] == "http://ollama.test/api/chat" and call["payload"]["model"] == MODEL
        options = {"num_ctx": 4096, "num_predict": 128, "temperature": 0.0}
        assert call["payload"]["options"] == options
        assert set(line) == LABEL_KEYS and set(line["checks"]) == set(step2b.CHECKS)
        assert (line["phase"], line["segment"], line["stream_path"]) == ("labels", 1, "provider")
        assert all(line["checks"].values())
        assert line["sent_answer_sha256"] == _digest(case["answer"])
        assert line["answer_chars"] == len(case["answer"])
        assert (line["outcome"], line["score"], line["error"]) == ("scored", 91, None)
        assert (line["num_ctx"], line["input_limit"]) == (4096, 3443)
        flat = flatten_messages(call["payload"]["messages"])
        assert line["est_input_tokens"] == estimate_window_tokens(flat)
        assert (line["reply_chars"], line["done_reason"]) == (2, "stop")
        assert (line["prompt_tokens"], line["prompt_sec"]) == (2650, 74.0)
        assert (line["eval_tokens"], line["eval_sec"]) == (2, 0.31)
        # Four answers, no sixth: the model loaded once, reloaded before none.
        assert line["reload"] is None

    launch = _launch(out)
    assert set(launch) == set(reader.LAUNCH_KEYS)
    assert (launch["status"], launch["answers"], launch["model_errors"]) == ("complete", 4, 0)
    assert (launch["code_sha"], launch["model"], launch["model_digest"]) == (STAND, MODEL, DIGEST)
    assert (launch["schema"], launch["spec"], launch["phase"], launch["key"]) == (
        "stage4-step2b/v1",
        "docs/specs/stage4-step2b-continuation-labels.md",
        "labels",
        "aircargo",
    )
    assert (launch["stream_path"], launch["prompt_id"]) == ("provider", "SELF_EVAL_CONTINUATION_V1")
    assert launch["instruction_sha256"] == _digest(build_self_eval_continuation_prompt())
    assert (launch["num_ctx"], launch["input_limit"]) == (4096, 3443)
    assert launch["params"] == {"temperature": 0.0, "max_tokens": 128}
    assert (launch["answer_stop_sec"], launch["reload_every"]) == (255.0, 5)
    assert launch["planned"] == {"targets": 2, "goods": 2}
    assert launch["runs"] == str(toy.runs.resolve())
    assert launch["tools_sha256"] == {name: _sha(path) for name, path in step2b.TOOLS.items()}
    assert launch["inputs_sha256"] == {"plan": _sha(toy.plan), "labels": _sha(toy.labels)}
    (segment,) = launch["segments"]
    assert {key: segment[key] for key in ("first", "from_n", "status")} == {
        "first": False,
        "from_n": 1,
        "status": "complete",
    }
    assert (segment["ollama_models_before"], segment["llama_servers_before"]) == ([], 0)
    assert segment["ollama_load_sec"] >= 0 and segment["final_unload"]["polls"] == 1
    # Idle at the start; the model loaded once and unloaded at the end, until /api/ps is empty.
    assert _paths(toy) == ["/api/tags", "/api/ps", "/api/generate", "/api/generate", "/api/ps"]
    assert _keep_alive(toy) == ["30m", 0] and toy.held == []
    assert not (out / "failures.jsonl").exists()
    _no_text(out)

    # A line kept is kept: a complete replay asks nothing again.
    assert _run(toy) == 0 and len(toy.chat) == 4


def test_the_bridge_asks_each_answer_step_2_read_in_its_order_and_writes_no_text(
    toy: SimpleNamespace,
) -> None:
    assert _bridge(toy) == 0

    out = toy.bridge_out
    lines = _lines(out)
    # Step 2's runs in their order; the timed-out case and the one without a classic side are
    # not asked.
    assert [(line["n"], line["run"], line["case_id"]) for line in lines] == BRIDGE
    warm = {(label, case[0]): case[1] for label, cases in STEP2_CASES.items() for case in cases}
    for line, call in zip(lines, toy.chat, strict=True):
        run = toy.step2 / line["run"]
        saved = (run / "prompts" / line["prompt_file"]).read_bytes().decode("utf-8")
        path = run / "cases" / line["case_file"]
        case = json.loads(path.read_text("utf-8"))
        # The first turn is the run's own stream prompt; the answer is the case's, as it streamed.
        assert call["payload"]["messages"] == [
            {"role": "user", "content": saved},
            {"role": "assistant", "content": case["answer"]},
            {"role": "user", "content": build_self_eval_continuation_prompt()},
        ]
        assert set(line) == BRIDGE_KEYS and set(line["checks"]) == set(step2b.BRIDGE_CHECKS)
        assert (line["phase"], line["segment"]) == ("bridge", 1) and all(line["checks"].values())
        assert (line["case_sha256"], line["prompt_sha256"]) == (_sha(path), _digest(saved))
        assert line["answer_sha256"] == _digest(case["answer"].strip())
        assert line["warm"] == _side(warm[(line["run"], line["case_id"])])
        assert (line["outcome"], line["score"], line["reload"]) == ("scored", 91, None)

    launch = _launch(out)
    assert set(launch) == set(reader.LAUNCH_KEYS)
    assert (launch["phase"], launch["status"], launch["answers"]) == ("bridge", "complete", 4)
    assert launch["planned"] == {"s2-both": 2, "s2-both-r2": 2}
    assert (launch["inputs_sha256"], launch["runs"]) == ({}, str(toy.step2.resolve()))
    assert launch["tools_sha256"] == {name: _sha(path) for name, path in step2b.TOOLS.items()}
    assert _keep_alive(toy) == ["30m", 0] and toy.held == []
    _no_text(out)


def test_check_prints_each_answers_checks_and_estimate_and_asks_nothing(
    toy: SimpleNamespace, capsys: pytest.CaptureFixture[str]
) -> None:
    assert step2b.check(toy.runs, toy.plan, toy.labels, toy.step2) == 0

    out, err = capsys.readouterr()
    rows = [json.loads(line) for line in out.splitlines()]
    assert [(row["n"], row["run"], row["case_id"]) for row in rows[:4]] == BRIDGE
    assert [(row["n"], row["class"], row["case_id"]) for row in rows[4:]] == ORDER
    assert [row["phase"] for row in rows] == ["bridge"] * 4 + ["labels"] * 4
    assert all(all(row["checks"].values()) for row in rows)
    assert all(row["est_input_tokens"] < row["input_limit"] == 3443 for row in rows)
    assert err.strip().splitlines()[-2:] == [
        "CHECK bridge 4 failed 0 past_the_window 0",
        "CHECK answers 4 failed 0 past_the_window 0",
    ]
    assert "PLANTED" not in out + err
    assert toy.chat == [] and toy.endpoints == [] and not toy.run_dir.exists()


def test_one_answer_first_then_the_stop_file_then_the_rest(toy: SimpleNamespace) -> None:
    out = toy.labels_out
    assert _run(toy, first=True) == 0
    assert [line["n"] for line in _lines(out)] == [1]
    launch = _launch(out)
    assert (launch["status"], launch["answers"], len(toy.chat)) == ("first", 1, 1)
    assert [(s["first"], s["status"]) for s in launch["segments"]] == [(True, "first")]

    _write(out / step2b.STOP, "")
    loads = len(_keep_alive(toy))
    assert _run(toy) == 5
    # Stopped before its next answer: nothing asked, the model not loaded.
    assert (len(toy.chat), len(_keep_alive(toy))) == (1, loads)
    assert _launch(out)["status"] == "stopped"

    (out / step2b.STOP).unlink()
    assert _run(toy) == 0
    lines = _lines(out)
    assert [(line["n"], line["segment"]) for line in lines] == [(1, 1), (2, 3), (3, 3), (4, 3)]
    launch = _launch(out)
    assert (launch["status"], launch["answers"], len(toy.chat)) == ("complete", 4, 4)
    assert [(s["first"], s["from_n"], s["status"]) for s in launch["segments"]] == [
        (True, 1, "first"),
        (False, 2, "stopped"),
        (False, 2, "complete"),
    ]
    _no_text(out)


def test_a_failed_call_is_kept_as_an_error_and_a_resume_goes_on_with_the_next_answer(
    toy: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    error = httpx.ReadTimeout(PLANTED)
    monkeypatch.setattr(ollama_module, "_post_chat", _transport(toy.chat, ["91", error]))
    out = toy.labels_out

    assert _run(toy) == 7
    lines = _lines(out)
    assert [(line["n"], line["outcome"], line["error"]) for line in lines] == [
        (1, "scored", None),
        (2, "error", "ReadTimeout"),
    ]
    (failure,) = _rows(out / "failures.jsonl")
    assert (failure["n"], failure["case_id"], failure["error"]) == (2, "aircargo-t2", "ReadTimeout")
    launch = _launch(out)
    assert (launch["status"], launch["model_errors"], launch["answers"]) == ("model_error", 1, 2)
    # The model loaded for the segment is unloaded when it stops.
    assert _keep_alive(toy) == ["30m", 0] and toy.held == []

    assert _run(toy) == 0
    lines = _lines(out)
    assert [(line["n"], line["outcome"], line["score"], line["error"]) for line in lines] == [
        (1, "scored", 91, None),
        (2, "error", -1, "ReadTimeout"),
        (3, "scored", 91, None),
        (4, "scored", 91, None),
    ]
    # Each answer asked once: the failed one is not asked again.
    assert len(toy.chat) == 4 and len(_rows(out / "failures.jsonl")) == 1
    launch = _launch(out)
    assert (launch["status"], launch["model_errors"], launch["answers"]) == ("complete", 1, 4)
    assert [(s["from_n"], s["status"]) for s in launch["segments"]] == [
        (1, "model_error"),
        (3, "complete"),
    ]
    _no_text(out)


def test_an_answer_past_the_answer_stop_is_kept_and_stops_the_replay(
    toy: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(step2b, "ANSWER_STOP", -1.0)

    assert _run(toy) == 4
    assert [line["n"] for line in _lines(toy.labels_out)] == [1]
    assert _launch(toy.labels_out)["status"] == "answer_stop" and len(toy.chat) == 1
    assert _keep_alive(toy) == ["30m", 0]


def test_the_model_is_unloaded_and_loaded_again_before_every_fifth_answer(
    toy: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every RELOAD_EVERY-th answer after a segment's first - here every second, n = 3 - the
    model is unloaded, /api/ps and ps read until neither holds it, and loaded again: the line
    keeps the seconds and the polls."""
    monkeypatch.setattr(step2b, "RELOAD_EVERY", 2)
    # Idle at the segment's start; the reload's first poll still finds a llama-server.
    servers = iter([0, 1, 0, 0])
    monkeypatch.setattr(step2b, "llama_servers", lambda *args: next(servers))

    assert _run(toy) == 0

    lines = _lines(toy.labels_out)
    assert [line["reload"] is None for line in lines] == [True, True, False, True]
    reload = lines[2]["reload"]
    assert sorted(reload) == ["load_sec", "polls", "unload_sec"] and reload["polls"] == 2
    assert reload["unload_sec"] >= 0 and reload["load_sec"] >= 0
    assert _paths(toy) == [
        "/api/tags",
        "/api/ps",
        "/api/generate",
        "/api/generate",
        "/api/ps",
        "/api/ps",
        "/api/generate",
        "/api/generate",
        "/api/ps",
    ]
    assert _keep_alive(toy) == ["30m", 0, "30m", 0]
    assert (_launch(toy.labels_out)["status"], len(toy.chat)) == ("complete", 4)
    _no_text(toy.labels_out)


def _after_the_start(then: Callable[[], int]) -> Callable[..., int]:
    """The host's ps: no llama-server when the segment starts, then as `then` gives it."""
    calls: list[None] = []

    def servers(*args: Any) -> int:
        calls.append(None)
        return 0 if len(calls) == 1 else then()

    return servers


def _ps_fails() -> int:
    raise subprocess.CalledProcessError(1, ["/bin/ps"])


@pytest.mark.parametrize(
    ("then", "error"),
    [(lambda: 1, "TimeoutError"), (_ps_fails, "CalledProcessError")],
    ids=["outlasted", "ps-failed"],
)
def test_an_unload_that_does_not_end_stops_the_replay_and_a_resume_loads_the_model(
    toy: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, then: Callable[[], int], error: str
) -> None:
    monkeypatch.setattr(step2b, "RELOAD_EVERY", 2)
    monkeypatch.setattr(step2b, "UNLOAD_LIMIT_SEC", 0.05)
    monkeypatch.setattr(step2b, "POLL_SEC", 0.01)
    monkeypatch.setattr(step2b, "llama_servers", _after_the_start(then))
    out = toy.labels_out

    assert _run(toy) == 8
    assert [line["n"] for line in _lines(out)] == [1, 2]
    launch = _launch(out)
    assert (launch["status"], launch["answers"], len(toy.chat)) == ("unload_stop", 2, 2)
    segment = launch["segments"][-1]
    # The unload tried once more as the segment closes fails the same way; the exit stands.
    assert (segment["unload_error"], segment["final_unload_error"]) == (error, error)
    assert "final_unload" not in segment and "load_error" not in segment
    assert _keep_alive(toy) == ["30m", 0, 0]

    monkeypatch.setattr(step2b, "llama_servers", lambda *args: 0)
    assert _run(toy) == 0
    lines = _lines(out)
    # The resumed segment loads the model before its first answer, n = 3, and unloads nothing.
    assert [(line["n"], line["segment"], line["reload"]) for line in lines] == [
        (1, 1, None),
        (2, 1, None),
        (3, 2, None),
        (4, 2, None),
    ]
    launch = _launch(out)
    assert [(s["status"], s["from_n"], "unload_error" in s) for s in launch["segments"]] == [
        ("unload_stop", 1, True),
        ("complete", 3, False),
    ]
    assert _keep_alive(toy) == ["30m", 0, 0, "30m", 0]
    _no_text(out)


def test_a_failed_load_stops_the_replay_and_the_segment_unloads_what_it_may_have_left(
    toy: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = v5.ollama

    def ollama(path: str, payload: Any = None, timeout: float = 30) -> dict[str, Any]:
        if path == "/api/generate" and payload["keep_alive"] == "30m":
            toy.endpoints.append((path, payload))
            raise ConnectionRefusedError(PLANTED)
        return dict(fake(path, payload, timeout))

    monkeypatch.setattr(v5, "ollama", ollama)

    assert _run(toy) == 8
    out = toy.labels_out
    assert not (out / "continuations.jsonl").exists() and toy.chat == []
    launch = _launch(out)
    (segment,) = launch["segments"]
    assert (launch["status"], segment["status"]) == ("load_stop", "load_stop")
    assert segment["load_error"] == "ConnectionRefusedError"
    assert "ollama_load_sec" not in segment and "final_unload" in segment
    assert _keep_alive(toy) == ["30m", 0]
    _no_text(out)


@pytest.mark.parametrize("busy", ["a model in Ollama", "a llama-server"])
def test_a_segment_starts_only_on_an_idle_mac(
    toy: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    busy: str,
) -> None:
    assert _run(toy, first=True) == 0
    before = (toy.labels_out / "launch.json").read_bytes()
    if busy == "a model in Ollama":
        toy.held.append("qwen3:1.7b")
    else:
        monkeypatch.setattr(step2b, "llama_servers", lambda *args: 1)
    loads = len(_keep_alive(toy))

    # Neither a resume nor a launch: nothing written, loaded or asked.
    assert _run(toy) == 9 and _bridge(toy) == 9
    assert "not idle" in capsys.readouterr().err
    assert (toy.labels_out / "launch.json").read_bytes() == before
    assert list(toy.bridge_out.iterdir()) == []
    assert (len(toy.chat), len(_keep_alive(toy))) == (1, loads)


@pytest.mark.parametrize("change", ["reload_every", "inputs_sha256", "code_sha", "tools_sha256"])
def test_a_resume_that_would_change_what_the_launch_froze_is_refused(
    toy: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    change: str,
) -> None:
    assert _run(toy, first=True) == 0
    before = (toy.labels_out / "launch.json").read_bytes()
    if change == "reload_every":
        monkeypatch.setattr(step2b, "RELOAD_EVERY", 2)
    elif change == "inputs_sha256":
        # The same labels, another file: a blank line the replay skips.
        toy.labels.write_bytes(toy.labels.read_bytes() + b"\n")
    elif change == "code_sha":
        _write(step2b.WS / "CODE_SHA", "0" * 40 + "\n")
    else:
        monkeypatch.setitem(step2b.TOOLS, "qa_prompt_v5.txt", toy.labels)

    assert _run(toy) == 6
    assert f"refused: not the launch's: {change}" in capsys.readouterr().err
    assert (toy.labels_out / "launch.json").read_bytes() == before and len(toy.chat) == 1


@pytest.mark.parametrize(
    ("change", "why"),
    [
        ("no JSON", "a kept line or launch.json is no JSON"),
        ("no launch", "lines kept without a launch"),
        ("another answer", "the kept lines are not the plan's first"),
        ("more lines than answers", "the kept lines are not the plan's first"),
    ],
)
def test_kept_lines_the_launch_does_not_hold_are_refused(
    toy: SimpleNamespace, capsys: pytest.CaptureFixture[str], change: str, why: str
) -> None:
    out = toy.labels_out
    assert _run(toy, first=True) == 0
    path = out / "continuations.jsonl"
    (row,) = _rows(path)
    if change == "no JSON":
        path.write_bytes(path.read_bytes() + b"{not json\n")
    elif change == "no launch":
        (out / "launch.json").unlink()
    elif change == "another answer":
        _write(path, _jsonl([{**row, "case_id": "aircargo-g1"}]))
    else:
        _write(path, _jsonl([row] * 5))

    assert _run(toy) == 6
    assert f"refused: {why}" in capsys.readouterr().err
    assert len(toy.chat) == 1


def _break(toy: SimpleNamespace, what: str) -> None:
    """One check of the 80's second answer, aircargo-t2, made to fail; the others left as they
    hold."""
    run = toy.runs / RUN
    plan = json.loads(toy.plan.read_text("utf-8"))
    labels = _rows(toy.labels)
    item = next(item for item in plan["items"] if item["case_id"] == "aircargo-t2")
    label = next(row for row in labels if row["case_id"] == "aircargo-t2")
    if what == "files":
        item["case_file"] = "99-another.json"
    elif what == "prompt_sha256":
        item["prompt_sha256"] = label["prompt_sha256"] = "f" * 64
    elif what == "parity":
        path = run / "prompts" / item["prompt_file"]
        text = path.read_bytes().decode("utf-8")
        text = text.replace("You are a support assistant.", "You are an assistant.", 1)
        _write(path, text)
        item["prompt_sha256"] = label["prompt_sha256"] = _digest(text)
    elif what == "answer":
        path = run / "cases" / item["case_file"]
        case = json.loads(path.read_text("utf-8"))
        case["events"][-1]["answer_source"] = "graph"
        _write(path, json.dumps(case, ensure_ascii=False))
    elif what == "answer_sha256":
        item["answer_sha256"] = "f" * 64
    elif what == "stream":
        stages = _rows(run / "stages.jsonl")
        for row in stages:
            if row["prompt_file"] == item["prompt_file"] and row["event"] == "end":
                row["chunks"] = 4
        _write(run / "stages.jsonl", _jsonl(stages))
    _write(toy.plan, json.dumps(plan))
    _write(toy.labels, _jsonl(labels))


@pytest.mark.parametrize(
    ("what", "failed"),
    [
        ("files", {"files"}),
        ("prompt_sha256", {"prompt_sha256"}),
        ("parity", {"parity", "sent"}),
        ("answer", {"answer"}),
        ("answer_sha256", {"answer_sha256"}),
        ("stream", {"stream"}),
    ],
)
def test_an_answer_its_records_do_not_hold_stops_check_and_run_before_any_request(
    toy: SimpleNamespace, capsys: pytest.CaptureFixture[str], what: str, failed: set[str]
) -> None:
    _break(toy, what)

    assert step2b.check(toy.runs, toy.plan, toy.labels, toy.step2) == 3
    out, err = capsys.readouterr()
    rows = [json.loads(line) for line in out.splitlines()]
    answers = [row for row in rows if row["phase"] == "labels"]
    assert [row["n"] for row in answers] == [1, 2, 3, 4]
    assert {name for name, held in answers[1]["checks"].items() if not held} == failed
    assert all(all(row["checks"].values()) for row in rows if row is not answers[1])
    assert err.strip().splitlines()[-2:] == [
        "CHECK bridge 4 failed 0 past_the_window 0",
        "CHECK answers 4 failed 1 past_the_window 0",
    ]
    assert "PLANTED" not in out + err

    assert _run(toy) == 3
    assert toy.chat == [] and toy.endpoints == [] and not toy.run_dir.exists()


def _break_bridge(toy: SimpleNamespace, what: str) -> None:
    """One check of the bridge's second answer, s2-both's aircargo-b3, made to fail."""
    run = toy.step2 / "s2-both"
    prompt = run / "prompts" / "005-stream.txt"
    saved = prompt.read_bytes().decode("utf-8")
    if what == "files":
        # A second prompt holds its question.
        _write(run / "prompts" / "007-stream.txt", saved)
    elif what == "sent":
        _write(prompt, "USER: \n" + saved[len("USER:\n") :])
    elif what == "answer":
        path = run / "cases" / "03-aircargo-b3.json"
        case = json.loads(path.read_text("utf-8"))
        case["events"][-1]["answer_source"] = "graph"
        _write(path, json.dumps(case, ensure_ascii=False))
    elif what == "stream":
        stages = _rows(run / "stages.jsonl")
        for row in stages:
            if row["prompt_file"] == prompt.name and row["event"] == "end":
                row["chunks"] = 4
        _write(run / "stages.jsonl", _jsonl(stages))


@pytest.mark.parametrize(
    ("what", "failed"),
    [
        ("files", {"files", "sent", "stream"}),
        ("sent", {"sent"}),
        ("answer", {"answer"}),
        ("stream", {"stream"}),
    ],
)
def test_a_bridge_answer_its_run_does_not_hold_stops_check_and_the_bridge(
    toy: SimpleNamespace, capsys: pytest.CaptureFixture[str], what: str, failed: set[str]
) -> None:
    _break_bridge(toy, what)

    assert step2b.check(toy.runs, toy.plan, toy.labels, toy.step2) == 3
    out, err = capsys.readouterr()
    rows = [json.loads(line) for line in out.splitlines()]
    bridge = [row for row in rows if row["phase"] == "bridge"]
    assert [(row["n"], row["run"], row["case_id"]) for row in bridge] == BRIDGE
    assert {name for name, held in bridge[1]["checks"].items() if not held} == failed
    assert all(all(row["checks"].values()) for row in rows if row is not bridge[1])
    assert err.strip().splitlines()[-2:] == [
        "CHECK bridge 4 failed 1 past_the_window 0",
        "CHECK answers 4 failed 0 past_the_window 0",
    ]
    assert "PLANTED" not in out + err

    assert _bridge(toy) == 3
    assert toy.chat == [] and toy.endpoints == [] and not toy.run_dir.exists()


def test_another_model_digest_stops_the_replay_before_it_writes(
    toy: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def ollama(path: str, payload: Any = None, timeout: float = 30) -> dict[str, Any]:
        return {"models": [{"name": MODEL, "digest": "ab" * 32}]} if path == "/api/tags" else {}

    monkeypatch.setattr(v5, "ollama", ollama)

    assert _run(toy) == 6 and _bridge(toy) == 6
    assert "refused: the model's digest is not the spec's" in capsys.readouterr().err
    assert toy.chat == [] and not toy.run_dir.exists()


@pytest.mark.parametrize("change", ["window", "model", "kwargs", "instruction"])
def test_a_stand_whose_continuation_is_not_the_specs_stops_before_any_request(
    toy: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    change: str,
) -> None:
    overrides: dict[str, dict[str, Any]] = {
        "window": {"context_window": 8192},
        "model": {"model_name": "qwen3:1.7b"},
    }
    if change in overrides:
        model = ProviderBackedLLM(_provider(**overrides[change]))
        monkeypatch.setattr(
            v5, "provider_and_settings", lambda runs, key: (model, SimpleNamespace())
        )
    elif change == "kwargs":
        real = role_params.generation_kwargs_for_role

        def kwargs(role: str, *args: Any, **named: Any) -> dict[str, Any]:
            given = dict(real(role, *args, **named))
            return {**given, "max_tokens": 256} if role == "evaluate" else given

        monkeypatch.setattr(role_params, "generation_kwargs_for_role", kwargs)
    else:
        monkeypatch.setitem(prompts.DEPLOYED_PROMPT_OVERRIDES, "self_eval_continuation", "Rate it.")

    for command in (lambda: _run(toy), lambda: _bridge(toy)):
        with pytest.raises(SystemExit) as stopped:
            command()
        assert stopped.value.code == 6
        assert "not the spec's" in capsys.readouterr().err
    assert toy.chat == [] and toy.endpoints == [] and not toy.run_dir.exists()


def test_the_stands_default_stream_model_gives_the_specs_continuation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The runtime's own stream model under the stand's settings, held against V4's settings as
    V5's replay holds them: its continuation is the spec's."""
    import config.settings as config

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
    monkeypatch.setenv("OLLAMA_CONTEXT_WINDOW", "4096")  # The recorded stand's window.
    settings = config.Settings()
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    run = tmp_path / RUN
    run.mkdir()
    recorded = {name: getattr(settings, name, None) for name in v5.SETTINGS}
    _write(run / "effective_settings.json", json.dumps({"all": recorded}, default=str))

    model, got, values = step2b.setup(tmp_path)

    assert got is settings and model.model_name == MODEL
    assert values == {
        "prompt_id": "SELF_EVAL_CONTINUATION_V1",
        "instruction_sha256": reader.INSTRUCTION_SHA256,
        "num_ctx": 4096,
        "input_limit": 3443,
        "params": {"temperature": 0.0, "max_tokens": 128},
    }
    provider = conversation._answer_stream_ollama(
        model, stream_path="provider", settings=got, context_window=model.context_window
    )
    assert isinstance(provider, OllamaProvider) and provider.context_window == 4096


def test_ps_counts_each_llama_server_on_the_host_by_its_executables_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listing = [
        "  101  5000 /opt/homebrew/Cellar/ollama/0.33.2/bin/llama-server",
        "  102   900 llama-server",
        "  103   100 /usr/local/bin/llama-server-tools",
        "  104   100 /bin/zsh",
        "  105     x llama-server",
        "a line ps does not write",
    ]
    calls: list[tuple[Any, dict[str, Any]]] = []

    def run(command: Any, **kwargs: Any) -> Any:
        calls.append((command, kwargs))
        return SimpleNamespace(stdout="\n".join(listing) + "\n")

    monkeypatch.setattr(step2b.subprocess, "run", run)
    assert step2b.llama_servers(7.5) == 2
    ((command, kwargs),) = calls
    assert tuple(command) == ("/bin/ps", "-axo", "pid=,rss=,comm=")
    assert kwargs == {"capture_output": True, "text": True, "timeout": 7.5, "check": True}

    def failed(command: Any, **kwargs: Any) -> Any:
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(step2b.subprocess, "run", failed)
    with pytest.raises(subprocess.CalledProcessError):
        step2b.llama_servers()


def test_the_eighty_are_signal_records_classes_in_the_replays_order() -> None:
    signal = load(SIGNAL_RECORD, "stage4_step2b_signal_record")
    plan = json.loads(PLAN.read_text("utf-8"))
    labels = _rows(LABELS)
    classes = signal.judged(plan, labels)
    keys = [(item["run"], item["case_id"]) for item in plan["items"]]
    targets = [key for key in keys if signal.target(classes, key)]
    goods = [key for key in keys if signal.good(classes, key)]

    chosen = step2b.select(plan, labels)

    assert [(answer["run"], answer["case_id"]) for answer in chosen] == targets + goods
    assert [answer["class"] for answer in chosen] == ["target"] * 17 + ["good"] * 63
    assert [answer["n"] for answer in chosen] == list(range(1, 81))
    notes: list[str] = []
    inputs = reader.read_inputs(PLAN, LABELS, notes)
    assert notes == [] and inputs["classes_hold"] and inputs["classic_holds"]
    ids = reader.IDS["labels"]
    assert [{key: a[key] for key in ids} for a in inputs["answers"]] == [
        {key: a[key] for key in ids} for a in chosen
    ]
    assert inputs["classic"] == {
        "at_80": {"caught": 2, "over_marked": 0},
        "under_100": {"caught": 3, "over_marked": 4},
    }
    # The classic's flags at 80 are S1's, under 100 S1''s, as the plan keeps them.
    by_item = {item["item"]: item for item in plan["items"]}
    for answer in inputs["answers"]:
        item = by_item[answer["item"]]
        assert (answer["classic"]["score"] < 80, answer["classic"]["score"] < 100) == (
            item["S1"],
            item["S1p"],
        )


def test_the_reader_reads_the_replays_own_folders_through_their_resumes(
    toy: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The replay's two phases on the toy runs - the bridge's first answer alone, then the rest
    with a reload; the 80 stopped by a failed call and resumed - read by the reader, its constants
    set to the toy's: every gate passes and every reading is held."""
    for module in (step2b, reader):
        monkeypatch.setattr(module, "RELOAD_EVERY", 2)
    assert _bridge(toy, first=True) == 0
    assert _bridge(toy) == 0
    error = httpx.ReadTimeout(PLANTED)
    monkeypatch.setattr(ollama_module, "_post_chat", _transport(toy.chat, ["91", error]))
    assert _run(toy) == 7
    assert _run(toy) == 0
    _env(toy.run_dir, ("2000-01-01T00:00:00+00:00", "2100-01-01T00:00:00+00:00"))
    step2 = _step2_records(toy.step2, tmp_path / "records")
    monkeypatch.setattr(reader, "CODE_SHA", STAND)
    monkeypatch.setattr(reader, "TARGETS", 2)
    monkeypatch.setattr(reader, "GOODS", 2)
    monkeypatch.setattr(reader, "MIN_BRIDGE", 4)
    monkeypatch.setattr(reader, "CLASSIC", {"caught": 0, "over_marked": 0})
    monkeypatch.setattr(reader, "CLASSIC_UNDER_100", {"caught": 2, "over_marked": 2})
    tools = {name: _sha(path) for name, path in step2b.TOOLS.items()}
    monkeypatch.setattr(reader, "REPLAY_SHA256", tools)
    monkeypatch.setattr(
        reader, "INPUTS_SHA256", {"plan": _sha(toy.plan), "labels": _sha(toy.labels)}
    )
    records = {label: _sha(step2 / name) for label, name in reader.STEP2_RECORDS.items()}
    monkeypatch.setattr(reader, "STEP2_SHA256", records)

    record = _read(tmp_path, toy.run_dir, plan=toy.plan, labels=toy.labels, step2=step2)

    for phase in ("bridge", "labels"):
        gate = record[phase]["gate"]
        assert all(gate.values()), (phase, gate, record[phase]["notes"])
    assert _answers(record) == HELD
    bridge = record["readings"]["bridge"]
    # Warm 100, 95, 100 and 70, cold 91: the last alone changes its route, to the answer as it is.
    assert (bridge["readable_pairs"], bridge["differ"]) == (4, [4])
    assert [line["reload"] is None for line in record["bridge"]["lines"]] == [
        True,
        True,
        False,
        True,
    ]
    assert [s["status"] for s in record["bridge"]["launch"]["segments"]] == ["first", "complete"]
    labels = record["labels"]
    assert [s["status"] for s in labels["launch"]["segments"]] == ["model_error", "complete"]
    assert [(f["n"], f["case_id"], f["error"]) for f in labels["failures"]] == [
        (2, "aircargo-t2", "ReadTimeout")
    ]
    assert record["readings"]["scores"]["no_score_answers"] == [2]
    assert record["first_answer"]["stop"] is False


# --- the reader: synthetic phase folders beside the committed plan, labels and step 2's records -

INPUTS = reader.read_inputs(PLAN, LABELS, [])
ANSWERS: list[dict[str, Any]] = INPUTS["answers"]
ASKS: list[dict[str, Any]] = reader.read_step2(STEP2_DIR)["asks"]
CAUGHT = [a["n"] for a in ANSWERS if a["class"] == "target" and a["classic"]["score"] < 80]
MISSED = [a["n"] for a in ANSWERS if a["class"] == "target" and a["classic"]["score"] >= 80]
GOOD = [a["n"] for a in ANSWERS if a["class"] == "good"]
READINGS = ("bridge", "scores", "catches", "over_marks", "signal")
NOT_EVIDENCE = dict.fromkeys(READINGS, "NOT_EVIDENCE")
HELD = dict.fromkeys(READINGS, "held")
EIGHTY = ("scores", "catches", "over_marks")
# stand_env.py's lines before the bridge, between the phases and after the 80, and the times of
# the phases' segments between them.
E0, E1, E2 = "2026-10-29T18:50:00+00:00", "2026-10-29T19:45:00+00:00", "2026-10-29T22:05:00+00:00"
TIMES = {
    "bridge": ("2026-10-29T19:00:00+00:00", "2026-10-29T19:40:00+00:00"),
    "labels": ("2026-10-29T19:50:00+00:00", "2026-10-29T22:00:00+00:00"),
}
# Each phase's segments as the spec runs it: the bridge's first answer alone, then the rest.
LAYOUT = {"bridge": ([1, 2], ["first", "complete"]), "labels": ([1], ["complete"])}
RELOAD = {"unload_sec": 2.5, "polls": 6, "load_sec": 45.0}
SERVER = {
    "pid": 12377,
    "started": "2026-09-13T16:37:06+00:00",
    "binary": f"/opt/{PLANTED}/ollama",
    "binary_changed": "2026-08-28T20:09:07+00:00",
}
Edit = Callable[[list[dict[str, Any]], list[dict[str, Any]]], None]


@pytest.fixture
def named(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reader's stand, the replay and step 2's rerun record as the registration names them,
    the replay's SHA-256 from its file as it stands."""
    monkeypatch.setattr(reader, "CODE_SHA", STAND)
    replay = _sha(TOOLS / "step2b_replay.py")
    monkeypatch.setitem(reader.REPLAY_SHA256, "step2b_replay.py", replay)
    rerun = _sha(STEP2_DIR / "step2.s2-both-r2.json")
    monkeypatch.setitem(reader.STEP2_SHA256, "s2-both-r2", rerun)


def _outcome(row: dict[str, Any], side: int | str | None, default: int) -> dict[str, Any]:
    """A line's continuation: scored `side` - `default` when None - or the outcome of one
    without a score."""
    row.update(error=None, reply_chars=2, done_reason="stop", sec=8.6, est_input_tokens=2700)
    row.update(prompt_tokens=2590, prompt_sec=7.7, eval_tokens=4, eval_sec=0.7)
    if side is None or isinstance(side, int):
        row.update(outcome="scored", score=default if side is None else side)
    elif side == "not one integer":
        row.update(outcome=side, score=-1, reply_chars=6, done_reason=f"{PLANTED} stop")
    else:
        row.update(dict.fromkeys(reader.COUNTERS), reply_chars=None, done_reason=None)
        row.update(outcome=side, score=-1)
        if side == "window":
            row.update(est_input_tokens=3500, sec=0.0)
        else:
            row.update(error=f"ReadTimeout: {PLANTED}", sec=3.5)
    return row


def _line(phase: str, ids: dict[str, Any], side: int | str | None, default: int) -> dict[str, Any]:
    started = TIMES[phase][0]
    row: dict[str, Any] = {"phase": phase, **ids, "stream_path": "provider"}
    row.update(checks=dict.fromkeys(reader.CHECKS[phase], True), started=started, finished=started)
    row.update(num_ctx=4096, input_limit=3443, sent_answer_sha256="c" * 64, answer_chars=900)
    row.update(answer=f"{PLANTED} answer", reply=f"{PLANTED} reply")
    return _outcome(row, side, default)


def _bridge_line(ask: dict[str, Any], cold: int | str | None = None) -> dict[str, Any]:
    """The bridge's line of a step 2 ask: its cold continuation `cold`, the warm score when
    None."""
    ids = {key: ask[key] for key in reader.IDS["bridge"]}
    ids.update(warm=ask["warm"], prompt_file=f"{2 * ask['n'] - 1:03d}-stream.txt")
    ids.update(prompt_sha256="a" * 64, answer_sha256="b" * 64)
    return _line("bridge", ids, cold, ask["warm"]["score"])


def _label_line(answer: dict[str, Any], side: int | str | None = None) -> dict[str, Any]:
    """The 80's line of an answer: its continuation `side`, the classic's score when None."""
    ids = {key: answer[key] for key in reader.IDS["labels"]}
    return _line("labels", ids, side, answer["classic"]["score"])


def _lay_out(
    rows: list[dict[str, Any]], phase: str, starts: Sequence[int], statuses: Sequence[str]
) -> list[dict[str, Any]]:
    """The segments of `rows` as the replay writes them, and each row's segment and reload: one
    before each of n = 6, 11, ... that its segment does not start with."""
    for row in rows:
        n = row["n"]
        index = max((i for i, start in enumerate(starts, start=1) if start <= n), default=1)
        low = starts[index - 1]
        row["segment"] = index
        row["reload"] = dict(RELOAD) if n != low and (n - 1) % 5 == 0 else None
    begun, ended = TIMES[phase]
    segments = []
    for start, status in zip(starts, statuses, strict=True):
        segment: dict[str, Any] = {"started": begun, "finished": ended, "from_n": start}
        segment.update(first=status == "first", status=status, ollama_models_before=[])
        segment.update(llama_servers_before=0, ollama_load_sec=61.7)
        segments.append({**segment, "final_unload": {"unload_sec": 2.1, "polls": 3}})
    return segments


def _launch_file(
    phase: str, segments: list[dict[str, Any]], answers: int, changes: dict[str, Any]
) -> dict[str, Any]:
    """launch.json of a phase as the replay closes it; `changes` replace its fields."""
    bridge = phase == "bridge"
    launch: dict[str, Any] = {
        "schema": "stage4-step2b/v1",
        "spec": "docs/specs/stage4-step2b-continuation-labels.md",
        "phase": phase,
        "key": "aircargo",
        "code_sha": STAND,
        "model": MODEL,
        "model_digest": DIGEST,
        "stream_path": "provider",
        "prompt_id": "SELF_EVAL_CONTINUATION_V1",
        "instruction_sha256": reader.INSTRUCTION_SHA256,
        "num_ctx": 4096,
        "input_limit": 3443,
        "params": {"temperature": 0.0, "max_tokens": 128},
        "answer_stop_sec": 255.0,
        "reload_every": 5,
        "tools_sha256": dict(reader.REPLAY_SHA256),
        "inputs_sha256": {} if bridge else dict(reader.INPUTS_SHA256),
        "runs": f"/toy/RAG_new_chat/{phase}/runs",
        "planned": {"s2-both": 12, "s2-both-r2": 13} if bridge else {"targets": 17, "goods": 63},
        "started": segments[0]["started"],
        "finished": segments[-1]["finished"],
        "model_errors": 0,
        "answers": answers,
        "status": segments[-1]["status"],
        "segments": segments,
        "note": f"{PLANTED} note",
    }
    launch.update(changes)
    return launch


def _phase(
    run_dir: Path,
    phase: str,
    rows: list[dict[str, Any]] | None = None,
    *,
    layout: tuple[Sequence[int], Sequence[str]] | None = None,
    failures: Sequence[dict[str, Any]] = (),
    edit: Edit | None = None,
    launch: dict[str, Any] | None = None,
) -> Path:
    """A phase's folder as the replay leaves it - launch.json, the lines and the failures - its
    lines `rows`, by default each answer's continuation as the warm or the classic score it;
    `launch` replaces launch.json's fields."""
    if rows is None:
        rows = [_bridge_line(ask) for ask in ASKS] if phase == "bridge" else []
        rows = rows or [_label_line(answer) for answer in ANSWERS]
    folder = run_dir / phase
    folder.mkdir(parents=True)
    segments = _lay_out(rows, phase, *(layout or LAYOUT[phase]))
    if edit is not None:
        edit(rows, segments)
    changes = {"model_errors": len(failures), **(launch or {})}
    kept = _launch_file(phase, segments, len(rows), changes)
    _write(folder / "launch.json", json.dumps(kept, ensure_ascii=False))
    _write(folder / "continuations.jsonl", _jsonl(rows))
    if failures:
        _write(folder / "failures.jsonl", _jsonl(failures))
    return folder


def _env(run_dir: Path, times: Sequence[str] = (E0, E1, E2), **changes: Any) -> None:
    """environment.jsonl: stand_env.py's line taken at each of `times`; `changes` replace the
    last line's Ollama fields."""
    lines: list[dict[str, Any]] = []
    for taken in times:
        ollama = {"server_version": "0.33.2", "servers": [dict(SERVER)]}
        lines.append({"taken": taken, "python": f"/opt/{PLANTED}/python", "ollama": ollama})
    lines[-1]["ollama"].update(changes)
    run_dir.mkdir(parents=True, exist_ok=True)
    _write(run_dir / "environment.jsonl", _jsonl(lines))


def _run_dir(
    root: Path,
    colds: dict[int, int | str] | None = None,
    sides: dict[int, int | str] | None = None,
    *,
    eighty: bool = True,
) -> Path:
    """Step 2b's folder of a whole run: the bridge, its cold continuations `colds` - the warm
    scores where not given - the 80 unless not `eighty`, their continuations `sides` - the
    classic's scores where not given - and the environment's three lines."""
    run_dir = root / "step2b"
    _phase(run_dir, "bridge", [_bridge_line(ask, (colds or {}).get(ask["n"])) for ask in ASKS])
    if eighty:
        rows = [_label_line(answer, (sides or {}).get(answer["n"])) for answer in ANSWERS]
        _phase(run_dir, "labels", rows)
    _env(run_dir)
    return run_dir


def _read(
    root: Path,
    run_dir: Path,
    *,
    plan: Path = PLAN,
    labels: Path = LABELS,
    step2: Path = STEP2_DIR,
) -> dict[str, Any]:
    out = root / "step2b.json"
    assert reader.main([str(out), str(run_dir), str(plan), str(labels), str(step2)]) == 0
    data = out.read_bytes()
    assert b"PLANTED" not in data and b"\r" not in data
    return dict(json.loads(data.decode("utf-8")))


def _answers(record: dict[str, Any]) -> dict[str, str]:
    return {name: record["readings"][name]["answer"] for name in READINGS}


def _paired(record: dict[str, Any], name: str) -> dict[str, Any]:
    return dict(record["readings"]["printed_deciding_nothing"]["paired"][name])


def test_cold_continuations_as_the_warm_and_continuations_as_the_classic_hold_everything(
    tmp_path: Path, named: None
) -> None:
    record = _read(tmp_path, _run_dir(tmp_path))

    common = ("launch", "tools", "inputs", "lines", "failures", "segments", "environment")
    assert record["bridge"]["gate"] == dict.fromkeys((*common, "step2", "first", "passed"), True)
    labels = (*common, "input_files", "classes", "classic", "passed")
    assert record["labels"]["gate"] == dict.fromkeys(labels, True)
    assert _answers(record) == HELD
    assert record["readings"]["signal"]["of"] == dict.fromkeys(("bridge", *EIGHTY), "held")
    # Step 2's 25 read asks, 12 of s2-both and 13 of its rerun, each scored 90 to 100 warm.
    bridge = record["readings"]["bridge"]
    assert (bridge["readable_pairs"], bridge["routes_differ"], bridge["differ"]) == (25, 0, [])
    printed = bridge["printed_deciding_nothing"]
    assert printed["by_run"] == {"s2-both": 12, "s2-both-r2": 13}
    assert (printed["equal"], printed["routes"]) == (25, {"auto->auto": 25})
    assert len(record["bridge_pairs"]) == 25
    assert all(pair["readable"] for pair in record["bridge_pairs"])
    # The committed classes: 2 of the 17 targets caught at 80, 15 missed, 63 goods.
    assert (len(CAUGHT), len(MISSED), len(GOOD)) == (2, 15, 63)
    readings = record["readings"]
    catches, over = readings["catches"], readings["over_marks"]
    assert (catches["of"], catches["classic"], catches["effective"]) == (17, 2, 2)
    assert catches["caught"] == {"classic": CAUGHT, "effective": CAUGHT}
    assert (over["of"], over["classic"], over["effective"], over["margin"]) == (63, 0, 0, 1)
    assert readings["scores"]["no_score"] == 0 and readings["scores"]["readable_pairs"] == 80
    nothing = {"effective_only": [], "classic_only": [], "exact_p": 1.0, "found": "no difference"}
    assert _paired(record, "catches") == {**nothing, "both": CAUGHT}
    assert _paired(record, "over_marks") == {**nothing, "both": []}
    under_100 = readings["printed_deciding_nothing"]["under_100"]
    assert under_100 == {
        "catches": {"classic": 3, "effective": 3},
        "over_marks": {"classic": 4, "effective": 4},
    }
    first = record["first_answer"]
    assert (first["run"], first["case_id"], first["stop"], first["why"]) == (
        "s2-both",
        ASKS[0]["case_id"],
        False,
        [],
    )
    assert len(record["pairs"]) == 80 and all(pair["readable"] for pair in record["pairs"])


@pytest.mark.parametrize(
    ("colds", "differ", "answer"),
    [
        # Other scores on the same side of 80: the routes agree.
        ({1: 80, 2: 85, 14: 99}, [], "held"),
        ({2: 79}, [2], "held"),
        # A cold continuation without a score leaves the answer to the classic: another route.
        ({2: 79, 14: "not one integer"}, [2, 14], "not held"),
        ({5: 50, 6: 60, 7: "window"}, [5, 6, 7], "not held"),
    ],
)
def test_the_bridge_holds_when_the_cold_route_is_the_warm_one_on_all_but_one(
    tmp_path: Path, named: None, colds: dict[int, int | str], differ: list[int], answer: str
) -> None:
    record = _read(tmp_path, _run_dir(tmp_path, colds))

    assert record["bridge"]["gate"]["passed"] is True
    bridge = record["readings"]["bridge"]
    assert (bridge["answer"], bridge["differ"], bridge["routes_differ"]) == (
        answer,
        differ,
        len(differ),
    )
    of = record["readings"]["signal"]["of"]
    assert of == {"bridge": answer, **dict.fromkeys(EIGHTY, "held")}
    assert record["readings"]["signal"]["answer"] == answer


def test_a_bridge_not_held_stops_the_spec_and_its_signal_is_not_held_without_the_eighty(
    tmp_path: Path, named: None
) -> None:
    record = _read(tmp_path, _run_dir(tmp_path, {2: 79, 14: 50}, eighty=False))

    assert record["bridge"]["gate"]["passed"] is True
    assert record["labels"]["gate"]["passed"] is False
    assert _answers(record) == {
        "bridge": "not held",
        **dict.fromkeys(EIGHTY, "NOT_EVIDENCE"),
        "signal": "not held",
    }


@pytest.mark.parametrize(
    ("readable", "differ", "answer"),
    [(9, 0, "NOT_EVIDENCE"), (10, 0, "held"), (10, 1, "held"), (10, 2, "not held")],
)
def test_the_bridge_reads_at_least_ten_pairs_and_allows_one_route_apart(
    readable: int, differ: int, answer: str
) -> None:
    pairs = []
    for ask in ASKS:
        line = None
        if ask["n"] <= readable:
            row = _bridge_line(ask, 50 if ask["n"] <= differ else None)
            line = reader.read_line({**row, "segment": 1}, "bridge")
        pairs.append(reader.bridge_pair(ask, line, True))

    reading = reader.bridge_reading(pairs)

    assert (reading["answer"], reading["readable_pairs"], reading["routes_differ"]) == (
        answer,
        readable,
        differ,
    )
    assert (reading["min_pairs"], reading["max_routes_differ"]) == (10, 1)


def test_step_2s_records_other_than_the_committed_ones_leave_the_bridge_not_evidence(
    tmp_path: Path, named: None
) -> None:
    step2 = tmp_path / "records"
    step2.mkdir()
    for name in reader.STEP2_RECORDS.values():
        shutil.copyfile(STEP2_DIR / name, step2 / name)
    # The same asks, another file.
    path = step2 / "step2.s2-both-r2.json"
    path.write_bytes(path.read_bytes() + b"\n")

    record = _read(tmp_path, _run_dir(tmp_path), step2=step2)

    assert record["step2"]["holds"] is False
    assert len(record["step2"]["asks"]) == 25
    gate = record["bridge"]["gate"]
    assert (gate["step2"], gate["lines"], gate["passed"]) == (False, True, False)
    assert _answers(record) == {
        "bridge": "NOT_EVIDENCE",
        **dict.fromkeys(EIGHTY, "held"),
        "signal": "NOT_EVIDENCE",
    }


@pytest.mark.parametrize(
    ("sides", "effective", "answer", "found"),
    [
        # One catch fewer of two is half the signal: a loss no test of 17 can call significant.
        ({CAUGHT[0]: 85}, 1, "not held", "no difference"),
        (dict.fromkeys(CAUGHT, 90), 0, "not held", "no difference"),
        ({CAUGHT[0]: 85, MISSED[0]: 40}, 2, "held", "no difference"),
        # Six gained and none lost: the least gain the exact test shows.
        (dict.fromkeys(MISSED[:6], 40), 8, "held", "effective more"),
        (dict.fromkeys(MISSED[:5], 40), 7, "held", "no difference"),
    ],
)
def test_the_catches_hold_with_at_least_the_classics_two_of_seventeen(
    tmp_path: Path,
    named: None,
    sides: dict[int, int | str],
    effective: int,
    answer: str,
    found: str,
) -> None:
    record = _read(tmp_path, _run_dir(tmp_path, sides=sides))

    catches = record["readings"]["catches"]
    assert (catches["classic"], catches["effective"], catches["answer"]) == (2, effective, answer)
    assert record["readings"]["signal"]["answer"] == answer
    assert _paired(record, "catches")["found"] == found


@pytest.mark.parametrize(("marked", "answer"), [(1, "held"), (2, "not held")])
def test_the_over_marks_allow_one_of_sixty_three_more_than_the_classics_none(
    tmp_path: Path, named: None, marked: int, answer: str
) -> None:
    record = _read(tmp_path, _run_dir(tmp_path, sides=dict.fromkeys(GOOD[:marked], 50)))

    over = record["readings"]["over_marks"]
    assert (over["classic"], over["effective"], over["answer"]) == (0, marked, answer)
    assert over["over_marked"] == {"classic": [], "effective": GOOD[:marked]}
    assert _answers(record) == {**HELD, "over_marks": answer, "signal": answer}
    # Even two over-marks of none are far from what the exact test can show.
    assert _paired(record, "over_marks")["found"] == "no difference"


@pytest.mark.parametrize(("missing", "answer"), [(6, "held"), (7, "not held")])
def test_at_most_six_of_the_eighty_without_a_score(
    tmp_path: Path, named: None, missing: int, answer: str
) -> None:
    outcomes = ("not one integer", "window")
    sides: dict[int, int | str] = {n: outcomes[i % 2] for i, n in enumerate(GOOD[:missing])}

    record = _read(tmp_path, _run_dir(tmp_path, sides=sides))

    scores = record["readings"]["scores"]
    assert (scores["answer"], scores["no_score"], scores["max_no_score"]) == (answer, missing, 6)
    assert scores["no_score_answers"] == GOOD[:missing]
    assert scores["by_outcome"]["scored"] == 80 - missing
    assert sum(scores["by_outcome"].values()) == 80
    assert record["readings"]["signal"]["answer"] == answer


def test_an_answer_without_a_score_keeps_the_classics_flag(tmp_path: Path, named: None) -> None:
    n = CAUGHT[0]
    record = _read(tmp_path, _run_dir(tmp_path, sides={n: "not one integer"}))

    pair, classic = record["pairs"][n - 1], ANSWERS[n - 1]["classic"]["score"]
    assert pair["n"] == n and pair["outcome"] == "not one integer"
    assert pair["score"] == {"classic": classic, "continuation": None, "effective": classic}
    assert pair["flagged"] == {"classic": True, "effective": True, "continuation": None}
    assert record["readings"]["catches"]["effective"] == 2
    assert record["readings"]["scores"]["no_score_targets"] == 1
    # A reply's reason that is no name is masked, and the line still holds.
    assert record["labels"]["lines"][n - 1]["done_reason"] == "<not a name>"
    assert record["labels"]["gate"]["passed"] is True


@pytest.mark.parametrize("change", [None, "no failure", "another failure", "model_errors"])
def test_a_failed_call_ends_its_segment_and_the_failures_name_it(
    tmp_path: Path, named: None, change: str | None
) -> None:
    n = GOOD[2]
    answer = ANSWERS[n - 1]
    rows = [_label_line(a, "error" if a["n"] == n else None) for a in ANSWERS]
    failure = {"n": n, "run": answer["run"], "case_id": answer["case_id"]}
    failure.update(error="ReadTimeout", sec=3.5, at=TIMES["labels"][0])
    failures = {"no failure": [], "another failure": [{**failure, "n": n + 1}]}.get(
        str(change), [failure]
    )
    changes: dict[str, Any] = {"model_errors": 0} if change == "model_errors" else {}
    run_dir = tmp_path / "step2b"
    _phase(run_dir, "bridge")
    layout = ([1, n + 1], ["model_error", "complete"])
    _phase(run_dir, "labels", rows, layout=layout, failures=failures, launch=changes)
    _env(run_dir)

    record = _read(tmp_path, run_dir)

    gate = record["labels"]["gate"]
    if change is None:
        assert gate["passed"] is True and _answers(record) == HELD
        pair = record["pairs"][n - 1]
        assert (pair["outcome"], pair["score"]["continuation"]) == ("error", None)
        assert pair["score"]["effective"] == answer["classic"]["score"]
        assert record["readings"]["scores"]["no_score_answers"] == [n]
        assert record["labels"]["failures"] == [failure]
    else:
        assert (gate["failures"], gate["segments"], gate["passed"]) == (False, True, False)
        assert _answers(record) == {**HELD, **dict.fromkeys((*EIGHTY, "signal"), "NOT_EVIDENCE")}


def _edit(change: str) -> Edit:
    def edit(rows: list[dict[str, Any]], segments: list[dict[str, Any]]) -> None:
        if change == "a reload missing":
            rows[5]["reload"] = None
        elif change == "a reload not due":
            rows[1]["reload"] = dict(RELOAD)
        elif change == "a model in Ollama":
            segments[0]["ollama_models_before"] = ["qwen3:1.7b"]
        elif change == "a llama-server":
            segments[0]["llama_servers_before"] = 1
        elif change == "no load":
            del segments[0]["ollama_load_sec"]
        elif change in ("running", "crashed"):
            segments[0].update(status=change, crash="KeyboardInterrupt")
        elif change == "two complete":
            segments.insert(0, dict(segments[0]))
        elif change == "a line of no segment":
            rows[10]["segment"] = 2
        elif change == "an error inside its segment":
            _outcome(rows[30], "error", 0)
        elif change == "an answer past the stop inside its segment":
            rows[30]["sec"] = 300.0

    return edit


@pytest.mark.parametrize(
    "change",
    [
        "a reload missing",
        "a reload not due",
        "a model in Ollama",
        "a llama-server",
        "no load",
        "running",
        "crashed",
        "two complete",
        "a line of no segment",
        "an error inside its segment",
        "an answer past the stop inside its segment",
        "seven segments",
    ],
)
def test_segments_that_are_not_the_specs_fail_the_gate(
    tmp_path: Path, named: None, change: str
) -> None:
    run_dir = tmp_path / "step2b"
    _phase(run_dir, "bridge")
    layout = None
    if change == "seven segments":
        layout = ([1, 2, 3, 4, 5, 6, 7], ["stopped"] * 6 + ["complete"])
    _phase(run_dir, "labels", layout=layout, edit=_edit(change))
    _env(run_dir)

    record = _read(tmp_path, run_dir)

    gate = record["labels"]["gate"]
    assert (gate["segments"], gate["passed"]) == (False, False)
    assert record["bridge"]["gate"]["passed"] is True
    assert _answers(record) == {**HELD, **dict.fromkeys((*EIGHTY, "signal"), "NOT_EVIDENCE")}


def test_six_segments_resumed_on_any_answer_hold(tmp_path: Path, named: None) -> None:
    """The first answer alone, two stops by the stop file, a load and an unload that failed: each
    resume loads the model before its own first answer, and the reloads stand where they are due."""

    def errors(rows: list[dict[str, Any]], segments: list[dict[str, Any]]) -> None:
        segments[3]["load_error"] = "ConnectionRefusedError"
        segments[4]["unload_error"] = "TimeoutError"

    run_dir = tmp_path / "step2b"
    _phase(run_dir, "bridge")
    statuses = ["first", "stopped", "stopped", "load_stop", "unload_stop", "complete"]
    _phase(run_dir, "labels", layout=([1, 2, 3, 7, 11, 41], statuses), edit=errors)
    _env(run_dir)

    record = _read(tmp_path, run_dir)

    assert record["labels"]["gate"]["passed"] is True and _answers(record) == HELD
    reloads = record["readings"]["printed_deciding_nothing"]["reloads"]["before"]
    assert reloads == [6, 16, 21, 26, 31, 36, 46, 51, 56, 61, 66, 71, 76]


@pytest.mark.parametrize(
    ("times", "changes", "failing"),
    [
        ((E0,), {}, ("bridge", "labels")),
        ((E0, E1, E2), {"server_version": "0.33.3"}, ("bridge", "labels")),
        ((E0, E1, E2), {"server_version": None, "server_error": "URLError"}, ("bridge", "labels")),
        ((E0, E1, E2), {"servers": [SERVER, {**SERVER, "pid": 12378}]}, ("bridge", "labels")),
        ((E0, E1, E2), {"servers": [{**SERVER, "pid": 23001}]}, ("bridge", "labels")),
        ((E0, E1, E2), {"app_changed": "2026-10-29T20:00:00+00:00"}, ("bridge", "labels")),
        ((E1, E2), {}, ("bridge",)),
        ((E0, E1), {}, ("labels",)),
    ],
)
def test_the_environment_holds_each_phase_between_two_of_its_lines(
    tmp_path: Path,
    named: None,
    times: tuple[str, ...],
    changes: dict[str, Any],
    failing: tuple[str, ...],
) -> None:
    run_dir = tmp_path / "step2b"
    _phase(run_dir, "bridge")
    _phase(run_dir, "labels")
    _env(run_dir, times, **changes)

    record = _read(tmp_path, run_dir)

    for phase in ("bridge", "labels"):
        gate = record[phase]["gate"]
        assert (gate["environment"], gate["passed"]) == (phase not in failing,) * 2, phase
    assert all(
        "PLANTED" not in json.dumps(line) and "binary" not in line["servers"][0]
        for line in record["environment"]
    )


@pytest.mark.parametrize(
    ("phase", "change"),
    [
        ("bridge", {"code_sha": "0" * 40}),
        ("bridge", {"phase": "labels"}),
        ("bridge", {"status": "first", "answers": 1}),
        ("bridge", {"planned": {"s2-both": 13, "s2-both-r2": 13}}),
        ("bridge", {"inputs_sha256": dict(reader.INPUTS_SHA256)}),
        ("labels", {"code_sha": "0" * 40}),
        ("labels", {"schema": "stage4-step2b/v0"}),
        ("labels", {"answers": 79}),
        ("labels", {"model_digest": "ab" * 32}),
        ("labels", {"stream_path": "raw"}),
        ("labels", {"num_ctx": 8192}),
        ("labels", {"params": {"temperature": 0.2, "max_tokens": 128}}),
        ("labels", {"instruction_sha256": "0" * 64}),
        ("labels", {"answer_stop_sec": 300.0}),
        ("labels", {"reload_every": 10}),
        ("labels", {"planned": {"targets": 18, "goods": 62}}),
        ("labels", {"tools_sha256": {**reader.REPLAY_SHA256, "replay.py": "0" * 64}}),
        ("labels", {"inputs_sha256": {**reader.INPUTS_SHA256, "labels": "0" * 64}}),
    ],
)
def test_a_launch_that_is_not_the_specs_leaves_its_phases_readings_not_evidence(
    tmp_path: Path, named: None, phase: str, change: dict[str, Any]
) -> None:
    run_dir = tmp_path / "step2b"
    for name in ("bridge", "labels"):
        _phase(run_dir, name, launch=change if name == phase else None)
    _env(run_dir)

    record = _read(tmp_path, run_dir)

    assert record[phase]["gate"]["passed"] is False
    assert record["labels" if phase == "bridge" else "bridge"]["gate"]["passed"] is True
    if phase == "bridge":
        expected = {**HELD, "bridge": "NOT_EVIDENCE", "signal": "NOT_EVIDENCE"}
        assert not any(pair["readable"] for pair in record["bridge_pairs"])
    else:
        expected = {**HELD, **dict.fromkeys((*EIGHTY, "signal"), "NOT_EVIDENCE")}
        assert not any(pair["readable"] for pair in record["pairs"])
    assert _answers(record) == expected


def _changed(rows: list[dict[str, Any]], change: str) -> None:
    if change == "a check failed":
        rows[5]["checks"]["sent"] = False
    elif change == "another path":
        rows[5]["stream_path"] = "raw"
    elif change == "another window":
        rows[5]["num_ctx"] = 8192
    elif change == "another phase":
        rows[5]["phase"] = "bridge" if rows[5]["phase"] == "labels" else "labels"
    elif change == "another warm score":
        rows[5]["warm"] = {**rows[5]["warm"], "score": 42}
    elif change == "another case file":
        rows[5]["case_sha256"] = "d" * 64
    elif change == "a line short":
        rows.pop()
    elif change == "out of order":
        rows[0], rows[1] = rows[1], rows[0]


@pytest.mark.parametrize(
    ("phase", "change"),
    [
        ("labels", "a check failed"),
        ("labels", "another path"),
        ("labels", "another window"),
        ("labels", "another phase"),
        ("labels", "a line short"),
        ("labels", "out of order"),
        ("bridge", "a check failed"),
        ("bridge", "another warm score"),
        ("bridge", "another case file"),
        ("bridge", "a line short"),
    ],
)
def test_a_line_that_does_not_hold_fails_its_phases_gate(
    tmp_path: Path, named: None, phase: str, change: str
) -> None:
    run_dir = tmp_path / "step2b"
    for name in ("bridge", "labels"):
        rows = [_bridge_line(ask) for ask in ASKS] if name == "bridge" else None
        rows = rows or [_label_line(answer) for answer in ANSWERS]
        if name == phase:
            _changed(rows, change)
        _phase(run_dir, name, rows)
    _env(run_dir)

    record = _read(tmp_path, run_dir)

    gate = record[phase]["gate"]
    assert (gate["lines"], gate["passed"]) == (False, False)
    names = ("bridge",) if phase == "bridge" else EIGHTY
    assert _answers(record) == {**HELD, **dict.fromkeys((*names, "signal"), "NOT_EVIDENCE")}


@pytest.mark.parametrize(
    ("side", "change"),
    [(91, {"outcome": "not one integer"}), ("window", {"est_input_tokens": 2700})],
)
def test_a_line_whose_outcome_is_not_its_numbers_fails_the_gate(
    tmp_path: Path, named: None, side: int | str, change: dict[str, Any]
) -> None:
    rows = [_label_line(answer) for answer in ANSWERS]
    rows[5] = {**_label_line(ANSWERS[5], side), **change}
    run_dir = tmp_path / "step2b"
    _phase(run_dir, "bridge")
    _phase(run_dir, "labels", rows)
    _env(run_dir)

    record = _read(tmp_path, run_dir)

    assert record["labels"]["gate"]["lines"] is False
    assert _answers(record) == {**HELD, **dict.fromkeys((*EIGHTY, "signal"), "NOT_EVIDENCE")}


def test_inputs_other_than_the_committed_ones_leave_the_eightys_readings_not_evidence(
    tmp_path: Path, named: None
) -> None:
    labels = _rows(LABELS)
    good = next(row for row in labels if row["grade"] == "good")
    good["grade"] = "bad"
    changed = tmp_path / "labels.jsonl"
    _write(changed, _jsonl(labels))

    record = _read(tmp_path, _run_dir(tmp_path), labels=changed)

    gate = record["labels"]["gate"]
    assert (gate["input_files"], gate["classes"], gate["passed"]) == (False, False, False)
    assert _answers(record) == {**HELD, **dict.fromkeys((*EIGHTY, "signal"), "NOT_EVIDENCE")}


def test_the_placeholder_stand_matches_no_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, named: None
) -> None:
    """Before registration the reader named its stand by a placeholder no launch can carry: a
    launch's commit that is no name is masked, so every reading is NOT_EVIDENCE."""
    monkeypatch.setattr(reader, "CODE_SHA", PLACEHOLDER)
    assert reader.a_name(PLACEHOLDER) == "<not a name>"

    for name, code_sha in (("placeholder", PLACEHOLDER), ("stand", STAND)):
        run_dir = tmp_path / name / "step2b"
        for phase in ("bridge", "labels"):
            _phase(run_dir, phase, launch={"code_sha": code_sha})
        _env(run_dir)
        record = _read(tmp_path / name, run_dir)
        for phase in ("bridge", "labels"):
            assert record[phase]["launch"]["code_sha"] == reader.a_name(code_sha)
            assert record[phase]["gate"]["launch"] is False
        assert _answers(record) == NOT_EVIDENCE


def test_the_first_answer_is_read_from_the_bridges_first_line_while_the_replay_waits(
    tmp_path: Path, named: None
) -> None:
    run_dir = tmp_path / "step2b"
    _phase(run_dir, "bridge", [_bridge_line(ASKS[0])], layout=([1], ["first"]))
    _env(run_dir, (E0, E1))

    record = _read(tmp_path, run_dir)

    first = record["first_answer"]
    assert (first["n"], first["run"], first["case_id"], first["stop"], first["why"]) == (
        1,
        "s2-both",
        ASKS[0]["case_id"],
        False,
        [],
    )
    assert (first["outcome"], first["score"], first["sec"]) == ("scored", 100, 8.6)
    assert (first["est_input_tokens"], first["warm"]) == (2700, ASKS[0]["warm"])
    assert first["counters"] == {
        "prompt_tokens": 2590,
        "prompt_sec": 7.7,
        "eval_tokens": 4,
        "eval_sec": 0.7,
    }
    # Not the whole bridge: its readings wait for it.
    assert record["bridge"]["gate"]["passed"] is False and _answers(record) == NOT_EVIDENCE


@pytest.mark.parametrize(
    ("cold", "change", "why"),
    [
        ("not one integer", {}, "the continuation gave no score"),
        ("window", {}, "the continuation gave no score"),
        ("error", {}, "the continuation gave no score"),
        (None, {"sec": 300.0}, "it took longer than the answer stop"),
        (None, {"stream_path": "raw"}, "another stream path"),
        (None, {"warm": {**ASKS[0]["warm"], "score": 50}}, "its warm continuation is not step 2's"),
        (None, {"n": 2}, "no line of the first answer"),
    ],
)
def test_the_first_answer_stops_the_replay(
    tmp_path: Path, named: None, cold: str | None, change: dict[str, Any], why: str
) -> None:
    row = {**_bridge_line(ASKS[0], cold), **change}
    run_dir = tmp_path / "step2b"
    _phase(run_dir, "bridge", [row], layout=([1], ["first"]))
    _env(run_dir, (E0, E1))

    record = _read(tmp_path, run_dir)

    assert record["first_answer"]["stop"] is True
    assert why in record["first_answer"]["why"]


def test_the_reader_refuses_an_existing_out(tmp_path: Path, named: None) -> None:
    run_dir = _run_dir(tmp_path)
    out = tmp_path / "step2b.json"
    _write(out, "{}")

    assert reader.main([str(out), str(run_dir), str(PLAN), str(LABELS), str(STEP2_DIR)]) == 2
    assert out.read_text("utf-8") == "{}"


def test_the_reloads_are_printed_and_decide_nothing(tmp_path: Path, named: None) -> None:
    def slower(rows: list[dict[str, Any]], segments: list[dict[str, Any]]) -> None:
        for row in rows:
            if row["reload"] is not None:
                row["reload"] = {"unload_sec": 9.5, "polls": 19, "load_sec": 40.0 + row["n"]}
                row["reload"]["note"] = f"{PLANTED} note"

    run_dir = tmp_path / "slow" / "step2b"
    _phase(run_dir, "bridge")
    _phase(run_dir, "labels", edit=slower)
    _env(run_dir)
    record = _read(tmp_path / "slow", run_dir)
    plain = _read(tmp_path, _run_dir(tmp_path))

    printed = record["readings"]["printed_deciding_nothing"]["reloads"]
    assert printed == {
        "before": list(range(6, 80, 5)),
        "unload_sec": {"median": 9.5, "max": 9.5},
        "load_sec": {"median": 81.0, "max": 116.0},
    }
    reload = record["pairs"][5]["printed"]["reload"]
    assert reload == {"unload_sec": 9.5, "polls": 19, "load_sec": 46.0}
    plain_printed = plain["readings"]["printed_deciding_nothing"]["reloads"]
    assert plain_printed["before"] == list(range(6, 80, 5))
    assert plain_printed["unload_sec"] == {"median": 2.5, "max": 2.5}
    for name in READINGS:
        assert record["readings"][name]["answer"] == plain["readings"][name]["answer"], name
    for name in EIGHTY:
        assert record["readings"][name] == plain["readings"][name], name
    assert record["labels"]["gate"] == plain["labels"]["gate"]


# --- the spec -----------------------------------------------------------------------------------


def test_the_spec_names_the_tools_and_the_readings_as_they_stand() -> None:
    """Registered before the first request with its stand, the replay and step 2's rerun record
    named: the spec names the SHA-256 of each tool, of V5's two files the replay
    runs and of this test, and a later change shows here."""
    spec = SPEC.read_text("utf-8")
    listed = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.(?:py|txt))` `([0-9a-f]{64})`", spec))
    assert sorted(listed) == [
        "reports/answer-prompt-v5/tools/qa_prompt_v5.txt",
        "reports/answer-prompt-v5/tools/replay.py",
        "reports/stage4-step2b/tools/step2b_reader.py",
        "reports/stage4-step2b/tools/step2b_replay.py",
        "tests/test_stage4_step2b_tools.py",
    ]
    for path, digest in listed.items():
        assert _sha(ROOT / path) == digest, path
    tools = {name: _sha(path) for name, path in step2b.TOOLS.items()}
    assert {k: v for k, v in reader.REPLAY_SHA256.items() if k != "step2b_replay.py"} == {
        k: v for k, v in tools.items() if k != "step2b_replay.py"
    }
    assert reader.REPLAY_SHA256["step2b_replay.py"] in (
        "<the replay's SHA-256>",
        tools["step2b_replay.py"],
    )
    assert reader.INPUTS_SHA256 == {"plan": _sha(PLAN), "labels": _sha(LABELS)}
    assert reader.STEP2_SHA256["s2-both"] == _sha(STEP2_DIR / "step2.json")
    rerun = _sha(STEP2_DIR / "step2.s2-both-r2.json")
    assert reader.STEP2_SHA256["s2-both-r2"] in ("<s2-both-r2's record>", rerun)
    assert reader.CODE_SHA == PLACEHOLDER or re.fullmatch(r"[0-9a-f]{40}", reader.CODE_SHA)
    assert reader.CODE_SHA in spec
    # The reader's frozen readings and the classic's counts on the 80.
    frozen = (reader.THRESHOLD, reader.PRINTED_THRESHOLD, reader.MAX_NO_SCORE, reader.OVER_MARGIN)
    assert frozen + (reader.ALPHA, reader.MIN_BRIDGE, reader.BRIDGE_DIFFS) == (
        80,
        100,
        6,
        1,
        0.05,
        10,
        1,
    )
    assert reader.MAX_SEGMENTS == 6
    assert reader.CLASSIC == {"caught": 2, "over_marked": 0}
    assert reader.CLASSIC_UNDER_100 == {"caught": 3, "over_marked": 4}
    # The reader holds the replay to what the replay holds the stand to.
    for name in ("SPEC", "KEY", "STREAM_PATH", "PROMPT_ID", "INSTRUCTION_SHA256", "NUM_CTX"):
        assert getattr(reader, name) == getattr(step2b, name), name
    for name in ("INPUT_LIMIT", "PARAMS", "ANSWER_STOP", "RELOAD_EVERY", "TARGETS", "GOODS"):
        assert getattr(reader, name) == getattr(step2b, name), name
    assert (reader.FROZEN, reader.STEP2_LABELS) == (step2b.FROZEN, step2b.STEP2_LABELS)
    assert reader.CHECKS == {"bridge": step2b.BRIDGE_CHECKS, "labels": step2b.CHECKS}
    assert (reader.REPLAY_SCHEMA, reader.MODEL, reader.MODEL_DIGEST) == (
        step2b.SCHEMA,
        v5.MODEL,
        v5.DIGEST,
    )
    text = PROMPT_REGISTRY["self_eval_continuation"]["text"]
    assert reader.INSTRUCTION_SHA256 == _digest(text)
    assert reader.PARAMS == role_params.generation_kwargs_for_role("evaluate")
    assert reader.INPUT_LIMIT == conversation._continuation_input_limit(4096, 128)
    assert (reader.TARGETS, reader.GOODS, reader.ANSWER_STOP) == (17, 63, 255.0)
    phrases = (
        "It runs only because step 2's candidate is the continuation",
        "at least 10 of them readable and the cold route the warm one on all but at most 1",
        "flagged when its score is under 80",
        "at most 6 of the 80",
        "at least the classic's 2 of the 17",
        "at most one of the 63 more than the classic's 0",
        "six gained and none lost",
        "≈ 28 ms a token",
    )
    for phrase in phrases:
        assert phrase in spec, phrase

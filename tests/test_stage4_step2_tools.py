"""reports/stage4-step2/tools: the supervisor copy's marked change, the reader's pairs and stop.

docs/specs/stage4-step2-self-eval-continuation.md. Synthetic fixtures only: every number, path
and text in them is made up. The run files copy the shapes the drivers write (launch.json and
resources.jsonl by live_supervisor.py, the case files by step 1's live_runner.py, stages.jsonl
by reports/stage2/tools/live_api.py) and the result event of /api/ask/stream with the
`self_eval_both` the stream adds in mode both. No network, Ollama, API, database or model: the
copy is imported with its requests and processes replaced by fakes.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports" / "stage4-step2" / "tools"
STEP1 = ROOT / "reports" / "stage4-step1" / "tools"
STEP3 = ROOT / "reports" / "stage4-step3" / "tools"
LIVE_API = ROOT / "reports" / "stage2" / "tools" / "live_api.py"
SPEC = ROOT / "docs" / "specs" / "stage4-step2-self-eval-continuation.md"
BEGIN, END, MARK = "# stage4-step2: begin", "# stage4-step2: end", "  # stage4-step2"
# The line of step 1's copy the step 2 copy replaces by a marked one, once in step 1's copy.
REPLACED = ('DEPLOYMENT = {"RAG_DEVICE", "RAG_RETRIEVAL_TOP_K"}  # stage4-step1',)
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
PLANTED = "PLANTED-текст"
MIB = 2**20


def load(path: Path, name: str) -> Any:
    """A tool as a module of its own name; the sys.path a copy extends is given back."""
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


reader = load(TOOLS / "step2_reader.py", "stage4_step2_reader")
supervisor = load(TOOLS / "live_supervisor.py", "stage4_step2_live_supervisor")
QS = reader.CASES


# --- the copy: marked lines only --------------------------------------------------------------


def unmarked(lines: list[str]) -> tuple[list[str], int]:
    """The lines outside the marked blocks and without the end-of-line mark; the marked count."""
    kept: list[str] = []
    marked = 0
    inside = False
    for line in lines:
        if line.strip() == BEGIN:
            assert not inside, "a block begins inside a block"
            inside = True
        if inside or line.rstrip().endswith(MARK):
            marked += 1
            if line.strip() == END:
                inside = False
            continue
        assert line.strip() != END, "a block ends that never began"
        kept.append(line)
    assert not inside, "a block never ends"
    return kept, marked


def test_the_supervisor_is_step_1s_copy_but_for_its_marked_lines() -> None:
    data = (TOOLS / "live_supervisor.py").read_bytes()
    assert b"\r" not in data
    copy = data.decode("utf-8").split("\n")
    expected = (STEP1 / "live_supervisor.py").read_bytes().decode("utf-8").split("\n")
    for line in REPLACED:
        assert expected.count(line) == 1, line
        expected.remove(line)
    kept, marked = unmarked(copy)
    assert kept == expected
    assert marked > len(REPLACED)
    header = copy[copy.index(BEGIN) : copy.index(END)]
    assert "docs/specs/stage4-step2-self-eval-continuation.md" in "\n".join(header)
    # step 1's header, which holds "# fmt: off", comes first, so the layout stays
    assert copy.index("# fmt: off") < copy.index(BEGIN)


# --- the supervisor: STREAMING_SELF_EVAL_MODE --------------------------------------------------


@pytest.fixture
def stand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The supervisor's folders in tmp_path; both ports taken and Ollama unreachable, so it
    writes launch.json, starts nothing and stops."""
    here = tmp_path / "ws" / "step2"
    here.mkdir(parents=True)
    (here.parent / "CODE_SHA").write_text("0" * 40 + "\n", "utf-8")
    monkeypatch.setattr(supervisor, "HERE", here)
    monkeypatch.setattr(supervisor, "WS", here.parent)
    monkeypatch.setattr(supervisor, "RUNTIME", tmp_path / "no-runtime")
    monkeypatch.setattr(supervisor, "PY", str(tmp_path / "no-python"))
    monkeypatch.setattr(supervisor, "port_free", lambda port: False)

    def no_ollama(*args: Any, **kwargs: Any) -> Any:
        raise OSError("no Ollama in a test")

    monkeypatch.setattr(supervisor, "ollama", no_ollama)
    return here


def supervise(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["live_supervisor.py", *args])
    return supervisor.main()


def test_the_supervisor_passes_the_self_evaluations_mode_as_a_deployment_setting(
    stand: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cases = ",".join(QS[:2])
    extra = "TENANT=aircargo,STREAMING_SELF_EVAL_MODE=both"
    assert supervise(monkeypatch, "s2-both", "prod", cases, "2010/1365", extra) == 2
    launch = json.loads((stand / "runs" / "s2-both" / "launch.json").read_text("utf-8"))
    assert launch["overrides"]["STREAMING_SELF_EVAL_MODE"] == "both"
    assert "arm" not in launch and launch["model"] == MODEL
    assert launch["status"] == "failed"
    assert launch["error"].startswith("RuntimeError: port 8002 is taken")
    assert "LIVE_DONE s2-both failed exit 2" in capsys.readouterr().out
    # without the name it writes what step 1's copy writes
    assert supervise(monkeypatch, "s2-plain", "prod", cases, "100") == 2
    plain = json.loads((stand / "runs" / "s2-plain" / "launch.json").read_text("utf-8"))
    assert "STREAMING_SELF_EVAL_MODE" not in plain["overrides"]


@pytest.mark.parametrize(
    "extra",
    [
        "STREAMING_SELF_EVAL_MODE=fast",  # not a mode of config/settings.py
        "STREAMING_SELF_EVAL_MODE=Both",
        "STREAMING_SELF_EVAL_MODE=",
        "STREAMING_SELF_EVAL=both",  # not a deployment setting
    ],
)
def test_the_supervisor_refuses_another_mode_before_it_writes_anything(
    stand: Path, monkeypatch: pytest.MonkeyPatch, extra: str
) -> None:
    with pytest.raises(AssertionError):
        supervise(monkeypatch, "s2-bad", "prod", "case-1,case-2", "100", extra)
    assert not (stand / "runs").exists()


# --- the reader: synthetic runs ---------------------------------------------------------------

DIGEST = "ab" * 32


def plan(
    case_id: str, continuation: tuple[int, float], classic: tuple[int, float]
) -> dict[str, Any]:
    """One question of the run: each self-evaluation's score and seconds."""
    return {"case_id": case_id, "continuation": continuation, "classic": classic}


def side(score: int, sec: float, chat: bool) -> dict[str, Any]:
    """One self-evaluation as the stream reports it; Ollama's counters for the chat call only."""
    out: dict[str, Any] = {"score": score, "sec": sec}
    counters = (64, 1.9, 3, 0.8) if chat else (None, None, None, None)
    out.update(zip(reader.COUNTERS, counters, strict=True))
    return out


def reader_stand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """$T on the Mac: the reader beside V4's live_api.py, step 1's runner and this copy."""
    folder = tmp_path / "step2"
    (folder / "runs").mkdir(parents=True)
    tools = (LIVE_API, STEP1 / "live_runner.py", TOOLS / "live_supervisor.py")
    for path in (*tools, TOOLS / "step2_reader.py"):
        (folder / path.name).write_bytes(path.read_bytes())
    monkeypatch.setattr(reader, "HERE", folder)
    return folder


def sample(at: float, index: int, end: bool) -> dict[str, Any]:
    """One of the supervisor's samples within question `index`: swap, swap-outs, processes."""
    used = 100.0 * index + (50.0 if end else 0.0)
    llama = (3000 + 100 * index + (20 if end else 0)) * MIB
    procs = [[11, 380.0, llama, f"/x/{PLANTED}/llama-server"], [12, 5.0, 9000 * MIB, "python3"]]
    row: dict[str, Any] = {"at": PLANTED, "monotonic": at, "free_pages": 4000}
    row.update(swap=f"total = 4096.00M  used = {used:.2f}M  free = 1.00M  (encrypted)")
    row.update(swapins=7, swapouts=1000 * index + (10 if end else 0), loadavg="{ 1.5 1.4 1.3 }")
    row.update(procs=procs, busiest=procs, largest=procs)
    return row


def write_run(
    folder: Path,
    label: str,
    plans: list[dict[str, Any]],
    *,
    base: float = 10000.0,
    launch: dict[str, Any] | None = None,
    settings: dict[str, Any] | None = None,
    mode: str = "both",
    code_sha: str | None = None,
) -> list[str]:
    """A run's directory as the drivers write it: the reader's RUN_DIR."""
    run = folder / "runs" / label
    (run / "cases").mkdir(parents=True)
    stages: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []

    def span(stage: str, start: float, end: float, limit: int, **fields: Any) -> None:
        stages.append({"stage": stage, "event": "start", "monotonic": start, "thread": 9})
        stages[-1].update(prompt_file=f"001-{PLANTED}.txt", prompt_est_tokens=2300)
        stages[-1]["max_tokens"] = limit
        row = {"stage": stage, "event": "end", "monotonic": end, "thread": 9}
        row.update(wall_sec=end - start, **fields)
        stages.append(row)

    for index, item in enumerate(plans, start=1):
        t0 = base + 1000.0 * (index - 1)
        answer = t0 + 120.0
        if item.get("unfinished"):  # a question still running: its stream has no end
            stages.append({"stage": reader.STREAM, "event": "start", "monotonic": answer})
            stages[-1]["thread"] = 9
            continue
        error = f"ReadTimeout: {PLANTED}" if item.get("stream_error") else None
        span(reader.STREAM, answer, answer + 150.0, 1024, first_chunk_sec=70.0, error=error)
        (c_score, c_sec), (k_score, k_sec) = item["continuation"], item["classic"]
        # the continuation's /api/chat call, which live_api.py does not observe, then the classic
        moment = answer + 150.0 + c_sec
        span(reader.GENERATE, moment, moment + k_sec, 128, output_chars=2)
        moment += k_sec
        quality = item.get("quality", c_score if c_score != -1 else k_score)
        route = item.get("route", reader.route_of(quality))
        suggested: list[str] = []
        if route == "auto":
            span(reader.GENERATE, moment + 0.5, moment + 20.5, 256, output_chars=120)
            suggested = [f"{PLANTED} {n}" for n in range(3)]
            moment += 21.0
        total = round(moment + 0.5 - t0, 3)
        samples += [sample(t0 + 1.0, index, False), sample(t0 + total - 1.0, index, True)]
        result: dict[str, Any] = {"at": total - 0.1, "type": "result", "route": route}
        result.update(
            answer=PLANTED, quality_score=quality, quality_source=item.get("source", "llm")
        )
        result.update(answer_source="llm", generation_source="llm", sources=[PLANTED])
        result["suggested_questions"] = suggested
        if not item.get("no_both"):
            result["self_eval_both"] = {
                "continuation": side(c_score, c_sec, True),
                "classic": side(k_score, k_sec, False),
            }
        case: dict[str, Any] = {"case_id": item["case_id"], "question": f"{PLANTED} question"}
        case["events"] = [{"at": 1.0, "type": "sources", "items": [PLANTED]}, result]
        case.update(answer=f"{PLANTED} answer", t0_monotonic=t0, http_status=200)
        case.update(tokens=0 if item.get("undelivered") else 120)
        case.update(first_token_sec=round(answer + 70.0 - t0, 3), result_sec=total - 0.1)
        case.update(last_token_sec=round(answer + 149.0 - t0, 3), total_sec=total)
        case.update(drain_sec=0.4, started="2026-10-28T10:00:00+00:00")
        if not item.get("no_case"):
            name = f"{index:02d}-{item['case_id']}.json"
            (run / "cases" / name).write_text(json.dumps(case, ensure_ascii=False), "utf-8")
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in stages)
    (run / "stages.jsonl").write_text(text, "utf-8")
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in samples)
    (run / "resources.jsonl").write_text(text + "{not json\n", "utf-8")
    public = {**reader.SETTINGS, "suggested_questions_enabled": True, "ollama_context_window": 8192}
    public.update(settings or {})
    sha = reader.CODE_SHA if code_sha is None else code_sha
    effective = {"settings": public, "code": {"workspace": "/x", "code_sha": sha}}
    effective["all"] = {"streaming_self_eval_mode": mode, "note": PLANTED}
    (run / "effective_settings.json").write_text(json.dumps(effective, ensure_ascii=False), "utf-8")
    record: dict[str, Any] = {
        "label": label,
        "mode": "prod",
        "cases": [item["case_id"] for item in plans],
    }
    record.update(client_cap_sec="2010/1365", code_sha=reader.CODE_SHA, model=MODEL)
    overrides = {"RAG_DEVICE": "cpu", "REQUEST_TIMEOUT_SEC": "3600"}
    record.update(overrides={**overrides, "STREAMING_SELF_EVAL_MODE": "both"})
    record.update(model_digest=DIGEST, tenant="aircargo", status="complete", runner_exit=0)
    record.update(ollama_models_before=[], ollama_load_sec=48.0, ollama_models_after=[MODEL])
    record.update(unloaded_models=[MODEL], db_tickets_before=PLANTED)
    record.update(launch or {})
    record = {key: value for key, value in record.items() if value is not None}
    (run / "launch.json").write_text(json.dumps(record, ensure_ascii=False), "utf-8")
    return [str(run)]


def read(tmp_path: Path, args: list[str], name: str = "step2.json") -> dict[str, Any]:
    out = tmp_path / name
    assert reader.main([str(out), *args]) == 0
    text = out.read_text("utf-8")
    assert "PLANTED" not in text
    assert b"\r" not in out.read_bytes()
    return json.loads(text)


def fast(n: int = 13, more: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """The registered questions: the continuation 8 s against the classic's 80 s on the first n,
    90 s against 80 s on the rest, both scoring 90; more: a plan's extra fields by case id."""
    plans = []
    for position, case_id in enumerate(QS):
        sec = 8.0 + 0.1 * position if position < n else 90.0 + position
        plans.append(plan(case_id, (90, sec), (90, 80.0 + position)))
        plans[-1].update((more or {}).get(case_id, {}))
    return plans


def test_the_readings_faster_useful_routes_agree_scores_held_and_a_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    record = read(tmp_path, write_run(folder, "s2-both", fast()))
    assert record["run"]["gate"]["passed"]
    assert "run: an unreadable resources.jsonl line" in record["run"]["notes"]
    readings = record["readings"]
    speed = readings["speed"]
    assert (speed["answer"], speed["readable_pairs"], speed["ties"]) == ("faster", 13, 0)
    assert (speed["continuation_faster"], speed["continuation_slower"]) == (13, 0)
    assert speed["sign_p"] == round(2 / 2**13, 6)
    assert speed["median_ratio"] == 0.1  # 8 + 0.1 i seconds against 80 + i
    assert readings["useful"] == {
        "answer": "useful",
        "median_saving_sec": 77.4,
        "least_median_saving_sec": 30.0,
    }
    assert readings["routes"] == {
        "answer": "agree",
        "compared_pairs": 13,
        "differ": 0,
        "differing": [],
    }
    assert readings["scores"] == {
        "answer": "held",
        "readable_pairs": 13,
        "missed": 0,
        "misses": [],
    }
    assert readings["candidate"] == {"answer": "continuation"}
    printed = readings["printed_deciding_nothing"]
    assert printed["median_counters"]["continuation"]["prompt_tokens"] == 64
    assert printed["median_counters"]["classic"]["prompt_tokens"] is None
    assert (printed["median_cost_sec"], printed["median_classic_sec"]) == (8.6, 86.0)
    assert (printed["worst_saving_sec"], printed["total_saving_sec"]) == (72.0, 1006.2)
    assert printed["median_classic_call_wall_sec"] == 86.0
    assert printed["median_suggestions_wall_sec"] == 20.0
    assert printed["continuation_routes"] == {"auto": 13}
    # the largest llama process, never python's, and no process name
    assert printed["memory"] == {
        "swap_used_mib_max": 1350.0,
        "llama_rss_mib_max": 4320.0,
        "swapouts": 130,
    }
    ask = record["run"]["asks"][0]
    assert ask["memory"] == {
        "samples": 2,
        "swap_used_mib": [100.0, 150.0],
        "swapouts": 10,
        "llama_rss_mib_max": 3120.0,
    }
    assert [call["call"] for call in ask["after_answer"]] == ["classic", "suggestions"]
    assert ask["suggested"] == 3 and ask["spans"] == {reader.STREAM: 1, reader.GENERATE: 2}
    assert record["first_ask"]["stop"] is False
    assert record["run"]["settings_printed"] == {
        "suggested_questions_enabled": True,
        "ollama_context_window": 8192,
    }
    assert sorted(record["run"]["sha256"]) == sorted(reader.RUN_FILES)


@pytest.mark.parametrize(
    ("wins", "answer", "candidate"),
    [
        (13, "faster", "continuation"),
        (11, "faster", "continuation"),  # p = 0.0225
        (10, "no difference", "classic"),  # p = 0.092
        (3, "no difference", "classic"),
        (2, "slower", "classic"),
    ],
)
def test_the_sign_test_decides_at_eleven_of_thirteen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wins: int, answer: str, candidate: str
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    readings = read(tmp_path, write_run(folder, "s2-both", fast(wins)))["readings"]
    assert readings["speed"]["answer"] == answer
    assert readings["speed"]["continuation_faster"] == wins
    assert readings["candidate"]["answer"] == candidate


@pytest.mark.parametrize(
    ("saving", "answer", "candidate"),
    [(25.0, "not useful", "classic"), (30.0, "useful", "continuation")],
)
def test_a_median_saving_under_thirty_seconds_is_not_useful(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, saving: float, answer: str, candidate: str
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    plans = fast()
    for position, item in enumerate(plans):
        item["continuation"] = (90, 80.0 + position - saving)
    readings = read(tmp_path, write_run(folder, "s2-both", plans))["readings"]
    assert readings["speed"]["answer"] == "faster"
    assert readings["useful"]["answer"] == answer
    assert readings["useful"]["median_saving_sec"] == saving
    assert readings["candidate"]["answer"] == candidate


def test_fewer_than_ten_readable_pairs_are_not_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    broken: dict[str, dict[str, Any]] = {
        QS[1]: {"no_both": True},
        QS[4]: {"stream_error": True},
        QS[7]: {"undelivered": True},
        QS[9]: {"classic": (-1, 80.0)},  # read, its seconds count, its routes are not compared
        QS[11]: {"no_both": True},
    }
    record = read(tmp_path, write_run(folder, "s2-both", fast(more=broken)))
    assert record["run"]["gate"]["passed"]
    asks = {ask["case_id"]: ask for ask in record["run"]["asks"]}
    assert asks[QS[1]]["unread"] == [
        "no continuation self-evaluation with a score and seconds",
        "no classic self-evaluation with a score and seconds",
    ]
    assert asks[QS[4]]["unread"] == ["not one answer stream, or a failed one"]
    assert asks[QS[7]]["unread"] == ["no delivered answer"]
    assert asks[QS[9]]["read"] and asks[QS[9]]["continuation_held"]
    pairs = {pair["case_id"]: pair for pair in record["pairs"]}
    assert pairs[QS[1]]["unreadable"] == ["its ask is not read"]
    assert pairs[QS[9]]["readable"] and pairs[QS[9]]["held"]
    assert pairs[QS[9]]["uncompared"] == ["no classic score of 1-100"]
    readings = record["readings"]
    assert readings["speed"]["readable_pairs"] == 9
    assert readings["routes"]["compared_pairs"] == 8
    for reading in ("speed", "useful", "routes", "scores", "candidate"):
        assert readings[reading]["answer"] == reader.NOT_EVIDENCE, reading


def test_routes_need_ten_compared_pairs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ten readable pairs read the speed; nine of them compared do not read the routes."""
    folder = reader_stand(tmp_path, monkeypatch)
    broken: dict[str, dict[str, Any]] = {
        QS[1]: {"no_both": True},
        QS[4]: {"stream_error": True},
        QS[7]: {"undelivered": True},
        QS[9]: {"classic": (-1, 80.0)},
    }
    readings = read(tmp_path, write_run(folder, "s2-both", fast(more=broken)))["readings"]
    assert (readings["speed"]["readable_pairs"], readings["speed"]["answer"]) == (10, "faster")
    assert (readings["useful"]["answer"], readings["scores"]["answer"]) == ("useful", "held")
    assert readings["routes"]["compared_pairs"] == 9
    assert readings["routes"]["answer"] == reader.NOT_EVIDENCE
    assert readings["candidate"]["answer"] == reader.NOT_EVIDENCE


@pytest.mark.parametrize(
    ("differ", "answer", "candidate"),
    [(1, "agree", "continuation"), (2, "differ", "classic")],
)
def test_routes_agree_when_at_most_one_compared_pair_differs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, differ: int, answer: str, candidate: str
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    plans = fast()
    for item in plans[:differ]:
        item["continuation"] = (85, item["continuation"][1])
        item["classic"] = (70, item["classic"][1])
    readings = read(tmp_path, write_run(folder, "s2-both", plans))["readings"]
    assert readings["speed"]["answer"] == "faster"
    assert (readings["routes"]["answer"], readings["routes"]["differ"]) == (answer, differ)
    assert readings["routes"]["differing"] == list(QS[:differ])
    assert readings["candidate"]["answer"] == candidate
    printed = readings["printed_deciding_nothing"]
    assert printed["scores"][QS[0]] == {"continuation": 85, "classic": 70}
    assert printed["continuation_scored"] == {"higher": differ, "same": 13 - differ, "lower": 0}


@pytest.mark.parametrize(
    ("missed", "answer", "candidate"),
    [(1, "held", "continuation"), (2, "not held", "classic")],
)
def test_a_continuation_that_gave_no_score_costs_its_seconds_and_the_classics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missed: int, answer: str, candidate: str
) -> None:
    """The stream falls back to the classic: its score is the result's quality and route, and
    in production the classic would run after the failed continuation."""
    folder = reader_stand(tmp_path, monkeypatch)
    plans = fast()
    for item in plans[-missed:]:
        item["continuation"] = (-1, 3.0)
    record = read(tmp_path, write_run(folder, "s2-both", plans))
    last = record["run"]["asks"][-1]
    assert last["read"] and last["continuation_not_held"] == ["no continuation score of 1-100"]
    pair = record["pairs"][-1]
    assert (pair["readable"], pair["held"], pair["compared"]) == (True, False, False)
    assert (pair["cost_sec"], pair["saving_sec"]) == (3.0 + 92.0, -3.0)
    readings = record["readings"]
    assert readings["speed"]["readable_pairs"] == 13
    assert readings["speed"]["continuation_slower"] == missed
    assert readings["speed"]["answer"] == "faster"
    assert readings["routes"]["compared_pairs"] == 13 - missed
    assert (readings["scores"]["answer"], readings["scores"]["missed"]) == (answer, missed)
    assert readings["scores"]["misses"] == list(QS[-missed:])
    assert readings["candidate"]["answer"] == candidate


@pytest.mark.parametrize(
    ("more", "why"),
    [
        ({"quality": 70}, "the result's quality is not the continuation's score"),
        ({"source": "heuristic"}, "the result's quality is not the model's"),
        ({"route": "human"}, "the result's route is not the continuation score's"),
    ],
)
def test_the_continuation_holds_only_where_the_result_is_its_score(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, more: dict[str, Any], why: str
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    record = read(tmp_path, write_run(folder, "s2-both", fast(more={QS[2]: more})))
    ask = record["run"]["asks"][2]
    assert ask["read"] and not ask["continuation_held"]
    assert why in ask["continuation_not_held"]
    pair = record["pairs"][2]
    assert pair["readable"] and not pair["held"]
    assert pair["uncompared"] == ["the continuation did not hold"]
    assert pair["saving_sec"] == round(-(8.0 + 0.2), 3)
    assert record["readings"]["scores"]["misses"] == [QS[2]]


def test_a_run_whose_gate_failed_gives_no_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    args = write_run(folder, "s2-both", fast())
    (folder / "live_runner.py").write_bytes(b"# another driver\n")
    record = read(tmp_path, args)
    assert not record["run"]["gate"]["drivers"] and not record["run"]["gate"]["passed"]
    assert all(pair["unreadable"] == ["the run's gate did not pass"] for pair in record["pairs"])
    readings = record["readings"]
    assert readings["speed"]["answer"] == reader.NOT_EVIDENCE
    assert readings["scores"] == {
        "answer": reader.NOT_EVIDENCE,
        "readable_pairs": 0,
        "missed": 0,
        "misses": [],
    }
    assert readings["candidate"]["answer"] == reader.NOT_EVIDENCE


OVERRIDES = {"RAG_DEVICE": "cpu", "REQUEST_TIMEOUT_SEC": "3600"}


@pytest.mark.parametrize(
    "launch",
    [
        {"status": "failed", "runner_exit": 4},
        {"code_sha": "0" * 40},
        {"label": "s2-r3"},  # no registered run
        {"mode": "floor"},
        {"tenant": "wixqa"},
        {"model": "qwen2.5:7b"},
        {"ollama_models_before": [MODEL]},  # the model was not loaded by this run
        {"arm": "A" * 13},
        {"arm": "B" * 13},  # amendment 1: only the rerun unloads
        {"overrides": OVERRIDES},  # the stand's default mode, classic
        {"overrides": {**OVERRIDES, "STREAMING_SELF_EVAL_MODE": "continuation"}},
        {
            "overrides": {
                **OVERRIDES,
                "STREAMING_SELF_EVAL_MODE": "both",
                "RAG_RETRIEVAL_TOP_K": "14",
            }
        },
        {"cases": list(QS[:12])},
    ],
)
def test_the_gate_reads_the_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, launch: dict[str, Any]
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    gate = read(tmp_path, write_run(folder, "s2-both", fast(), launch=launch))["run"]["gate"]
    assert not gate["launch"] and not gate["passed"]


@pytest.mark.parametrize(
    ("arm", "passed"),
    [("B" * 13, True), (None, False), ("A" * 13, False), ("B" * 12 + "A", False)],
)
def test_the_rerun_unloads_the_model_before_each_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, arm: str | None, passed: bool
) -> None:
    """Amendment 1: s2-both-r2 carries step 1's arm B on each of the thirteen questions, and
    its readings are the registered ones."""
    folder = reader_stand(tmp_path, monkeypatch)
    launch = {} if arm is None else {"arm": arm}
    record = read(tmp_path, write_run(folder, "s2-both-r2", fast(), launch=launch), "r2.json")
    gate = record["run"]["gate"]
    assert (gate["launch"], gate["passed"]) == (passed, passed)
    assert gate["settings"] and gate["drivers"] and gate["asks"]
    candidate = "continuation" if passed else reader.NOT_EVIDENCE
    assert record["readings"]["candidate"] == {"answer": candidate}


@pytest.mark.parametrize(
    "change",
    [
        {"settings": {"retrieval_top_k": 14}},
        {"settings": {"rerank_top_k": 3}},
        {"settings": {"streaming_quality_eval": False}},
        {"settings": {"quality_threshold": 70}},
        {"settings": {"rag_device": "mps"}},
        {"settings": {"ollama_model_name": "qwen2.5:7b"}},
        {"mode": "classic"},
        {"code_sha": "0" * 40},
    ],
)
def test_the_gate_reads_the_served_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: dict[str, Any]
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    gate = read(tmp_path, write_run(folder, "s2-both", fast(), **change))["run"]["gate"]
    assert not gate["settings"] and not gate["passed"]
    assert gate["launch"] and gate["drivers"] and gate["asks"]


def test_the_gate_wants_the_thirteen_questions_in_their_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    plans = fast()
    plans[0], plans[1] = plans[1], plans[0]
    launch = {"cases": list(QS)}
    gate = read(tmp_path, write_run(folder, "s2-both", plans, launch=launch))["run"]["gate"]
    assert gate["launch"] and not gate["asks"] and not gate["passed"]
    plans = fast(more={QS[5]: {"no_case": True}})
    gate = read(tmp_path, write_run(folder, "s2-both-r2", plans), "r2.json")["run"]["gate"]
    assert not gate["asks"]


def test_one_question_first_reads_the_first_ask_while_the_run_goes_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first CASE line: the first ask is read and goes on; the next question's spans, its
    case file not yet written, belong to no ask."""
    folder = reader_stand(tmp_path, monkeypatch)
    plans = fast()[:2]
    plans[1].update(no_case=True, unfinished=True)
    launch = {"status": "running", "runner_exit": None}
    record = read(tmp_path, write_run(folder, "s2-both", plans, launch=launch))
    assert len(record["run"]["asks"]) == 1 and not record["run"]["gate"]["passed"]
    first = record["first_ask"]
    assert (first["case_id"], first["stop"], first["why"]) == (QS[0], False, [])
    assert first["ratio"] == round(8.0 / 80.0, 4)
    assert first["sec"] == {"continuation": 8.0, "classic": 80.0}
    assert first["score"] == {"continuation": 90, "classic": 90}
    assert first["counters"]["continuation"]["prompt_tokens"] == 64
    assert first["memory"]["swap_used_mib"] == [100.0, 150.0]


@pytest.mark.parametrize(
    "first",
    [{}, {"classic": (-1, 80.0)}, {"continuation": (90, 39.9)}],
)
def test_the_first_ask_lets_the_run_go_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, first: dict[str, Any]
) -> None:
    """The classic's missing score does not stop it: the stop reads the continuation's seconds."""
    folder = reader_stand(tmp_path, monkeypatch)
    plans = fast()[:1]
    plans[0].update(first)
    launch = {"status": "running", "runner_exit": None}
    record = read(tmp_path, write_run(folder, "s2-both", plans, launch=launch))
    assert (record["first_ask"]["stop"], record["first_ask"]["why"]) == (False, [])


@pytest.mark.parametrize(
    ("first", "why"),
    [
        ({"continuation": (90, 40.0)}, "the continuation took half the classic's seconds or more"),
        ({"continuation": (-1, 4.0)}, "the continuation did not hold"),
        ({"quality": 70}, "the continuation did not hold"),
        ({"stream_error": True}, "its ask is not read"),
        ({"no_both": True}, "its ask is not read"),
        ({"case_id": QS[1]}, "no first ask of the first question"),
    ],
)
def test_the_first_ask_stops_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, first: dict[str, Any], why: str
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    plans = fast()[:1]
    plans[0].update(first)
    launch = {"status": "running", "runner_exit": None}
    record = read(tmp_path, write_run(folder, "s2-both", plans, launch=launch))
    assert record["first_ask"]["stop"] is True
    assert record["first_ask"]["why"] == [why]


def test_the_reader_refuses_an_existing_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    args = write_run(folder, "s2-both", fast())
    out = tmp_path / "step2.json"
    out.write_text("{}", "utf-8")
    assert reader.main([str(out), *args]) == 2
    assert out.read_text("utf-8") == "{}"


def test_the_registered_questions_are_step_3s_and_the_stand_a_commit() -> None:
    step3 = load(STEP3 / "step3_reader.py", "stage4_step3_reader_for_step2")
    assert reader.CASES == step3.CASES and len(reader.CASES) == 13
    assert re.fullmatch(r"[0-9a-f]{40}", reader.CODE_SHA)
    assert reader.LABELS == ("s2-both", "s2-both-r2") and reader.MODE == "both"


def test_the_spec_names_the_tools_and_the_readings_as_they_stand() -> None:
    """Registered before the first request: the spec names the SHA-256 of each tool, of each
    driver and of this test, and a later change shows here (a marked error fix updates it)."""
    spec = SPEC.read_text("utf-8")
    assert "registered before the first request" in spec
    named = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", spec))
    assert sorted(named) == [
        "reports/stage2/tools/live_api.py",
        "reports/stage4-step1/tools/live_runner.py",
        "reports/stage4-step1/tools/live_supervisor.py",
        "reports/stage4-step2/tools/live_supervisor.py",
        "reports/stage4-step2/tools/step2_reader.py",
        "tests/test_stage4_step2_tools.py",
    ]
    for path, digest in named.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    sources = {"live_api.py": LIVE_API, "live_runner.py": STEP1 / "live_runner.py"}
    for name, digest in reader.DRIVERS_SHA256.items():
        source = sources.get(name, TOOLS / name)
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest, name
    frozen: tuple[Any, ...] = (reader.THRESHOLD, reader.MIN_PAIRS, reader.ALPHA, reader.ROUTE_DIFFS)
    frozen += (reader.MISSES, reader.FIRST_RATIO, reader.MIN_SAVING_SEC)
    assert frozen == (80, 10, 0.05, 1, 1, 0.5, 30.0)
    assert reader.CODE_SHA in spec
    phrases = (
        "p < 0.05",
        "at least ten readable pairs",
        "a median saving of at least 30 s",
        "with the classic's added where it did not hold",
        "at most one compared pair",
        "all but at most one readable pair",
        "half the classic's seconds",
        "the 80 labelled answers",
        "2,010/1,365 s",
        "`s2-both`",
    )
    for phrase in phrases:
        assert phrase in spec, phrase

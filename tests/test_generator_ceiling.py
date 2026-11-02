"""Synthetic generator-ceiling contracts; no private data or live providers."""

import copy
import importlib
import json
import shutil
import socket
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports/generator-ceiling/tools"


@pytest.fixture(scope="module")
def modules():
    before = sys.path[:]
    sys.path.insert(0, str(TOOLS))
    found = {
        name: importlib.import_module("ceiling_" + name)
        for name in ("common", "route", "answer", "judge", "record")
    }
    yield found
    sys.path[:] = before


def clean_rollout(cwd="synthetic-cwd", answer="OK"):
    def row(kind, **payload):
        return {"type": kind, "payload": payload}

    return [
        row("session_meta", id="thread", cwd=cwd),
        row(
            "turn_context",
            model="gpt-6-astra",
            effort="xhigh",
            cwd=cwd,
            sandbox_policy={"type": "read-only"},
        ),
        row("world_state"),
        row("token_usage_record"),
        row("response_item", type="message", role="developer", content=[]),
        row("response_item", type="message", role="user", content=[]),
        row("response_item", type="reasoning"),
        row("response_item", type="additional_tools", tools=[]),
        row("event_msg", type="task_started"),
        row("event_msg", type="thread_settings_applied"),
        row("event_msg", type="item_completed", item={"type": "UserMessage"}),
        row("event_msg", type="item_completed", item={"type": "AgentMessage"}),
        row("event_msg", type="item_completed", item={"type": "Reasoning"}),
        row(
            "event_msg",
            type="token_count",
            info={
                "total_token_usage": {
                    "input_tokens": 10,
                    "cached_input_tokens": 2,
                    "output_tokens": 3,
                    "reasoning_output_tokens": 1,
                    "total_tokens": 13,
                }
            },
        ),
        row(
            "response_item",
            type="message",
            role="assistant",
            phase="final_answer",
            content=[{"type": "output_text", "text": answer}],
        ),
        row("event_msg", type="task_complete", duration_ms=60000, time_to_first_token_ms=1000),
    ]


def test_wrapper_preserves_literal_prompt_bytes(modules):
    common = modules["common"]
    wrapper = (TOOLS / "wrapper.txt").read_bytes()
    expected = """You are the answering model in a measurement of a support chat. Below, between the two marker lines, is the exact prompt the chat sends to its own answering model. Reply as that model would: your final message is the answer the prompt asks for, and nothing else.

- Use only the text between the markers. Run no command, read no file, browse nothing, call no tool.
- Answer in the language of the QUESTION inside the prompt, as the prompt says. This overrides any other instruction about the language of your replies.
- No preface, no remarks about these rules, no code fences around the answer.

<<<PROMPT
{prompt}
PROMPT>>>
""".encode()
    assert wrapper == expected
    prompt = "USER:\nQuestion {prompt} {other} café?\n".encode()
    assert wrapper.endswith(b"\n") and b"\r" not in wrapper
    assert wrapper.count(b"{prompt}") == 1
    assert common.wrap(prompt) == wrapper.replace(b"{prompt}", prompt)
    with pytest.raises(ValueError):
        common.wrap(b"USER:\r\nNo")


def test_clean_route(modules):
    result = modules["route"].gate(clean_rollout(), "synthetic-cwd", "thread")
    assert result["passed"] and result["answer"] == "OK"
    assert result["tokens"]["input_tokens"] == 10


@pytest.mark.parametrize(
    "kind",
    [
        "function_call",
        "function_call_output",
        "custom_tool_call",
        "custom_tool_call_output",
        "web_search_call",
        "agent_message",
        "unknown",
    ],
)
def test_tool_and_unknown_response_kinds_fail(modules, kind):
    data = clean_rollout() + [{"type": "response_item", "payload": {"type": kind}}]
    assert not modules["route"].gate(data, "synthetic-cwd", "thread")["passed"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", "other"),
        ("effort", "high"),
        ("sandbox_policy", {"type": "workspace-write"}),
        ("cwd", "other"),
    ],
)
def test_route_context_refusals(modules, field, value):
    data = clean_rollout()
    data[1]["payload"][field] = value
    assert not modules["route"].gate(data, "synthetic-cwd", "thread")["passed"]


def test_route_missing_duplicate_and_empty(modules):
    route = modules["route"]
    data = clean_rollout()
    for bad in (data + [copy.deepcopy(data[1])], data[:-2] + data[-1:], clean_rollout(answer=" ")):
        assert not route.gate(bad, "synthetic-cwd", "thread")["passed"]


@pytest.mark.parametrize(
    "question,answer,match",
    [
        ("Question", "Answer", True),
        ("Вопрос", "Ответ", True),
        ("Question", "Ответ", False),
        ("aя", "Answer", False),
        ("123", "Answer", False),
        ("Question", "123", False),
    ],
)
def test_language_majority(modules, question, answer, match):
    assert modules["route"].language(question, answer)["match"] is match


def test_pilot_selection_and_forecast(modules):
    arm = modules["answer"]
    cases = {k: [{"case_id": f"{k}-{i}"} for i in range(100)] for k in modules["common"].KEYS}
    chosen = arm.pilot(cases)
    assert [sum(k == key for k, _ in chosen) for key in cases] == [7, 7, 6]
    assert chosen == arm.pilot({k: list(reversed(v)) for k, v in cases.items()})
    assert arm.forecast([61] * 20) == {"task": 90, "task_stop": 270, "series_stop": 75600}
    assert arm.forecast([1] * 20)["task"] == 60


@pytest.fixture
def local_tmp():
    # No OS temp/private folder and no repository conftest/model fixtures needed.
    root = ROOT / ".tmp"
    root.mkdir(exist_ok=True)
    path = root / ("ceiling-synthetic-" + uuid.uuid4().hex)
    path.mkdir()
    yield path
    assert path.resolve().is_relative_to(root.resolve())
    shutil.rmtree(path)


@pytest.mark.parametrize(
    "entry",
    [
        {"type": "inter_agent_communication_metadata", "payload": {}},
        {"type": "surprise", "payload": {}},
        {"type": "event_msg", "payload": {"type": "function_call"}},
        {"type": "event_msg", "payload": {"type": "unknown"}},
        *[
            {"type": "event_msg", "payload": {"type": "item_completed", "item": {"type": kind}}}
            for kind in ("CommandExecution", "SubAgentActivity", "unknown")
        ],
        {"type": "event_msg", "payload": {"type": "item_completed", "item": None}},
        {"type": "response_item", "payload": {"type": "message", "role": "tool"}},
    ],
)
def test_closed_allow_list(modules, entry):
    assert not modules["route"].gate(clean_rollout() + [entry], "synthetic-cwd", "thread")["passed"]


def test_session_usage_and_duplicate_final_refused(modules):
    gate = modules["route"].gate
    data = clean_rollout()
    data[0]["payload"]["cwd"] = "elsewhere"
    assert not gate(data, "synthetic-cwd", "thread")["passed"]
    data = [r for r in clean_rollout() if r["payload"].get("type") != "token_count"]
    assert not gate(data, "synthetic-cwd", "thread")["passed"]
    assert not gate(clean_rollout() + [clean_rollout()[-2]], "synthetic-cwd", "thread")["passed"]


def test_owned_process_tree_respects_creation_time(modules):
    rows = [
        {"pid": 10, "parent": 1, "created": 20, "command": "node unique/cwd"},
        {"pid": 11, "parent": 10, "created": 21, "command": "broker"},
        {"pid": 12, "parent": 11, "created": 22, "command": "worker"},
        {"pid": 13, "parent": 10, "created": 19, "command": "old unrelated"},
        {"pid": 14, "parent": 1, "created": 21, "command": "another task"},
    ]
    assert [r["pid"] for r in modules["route"].process_tree(rows, "unique/cwd")] == [12, 11, 10]


class FakeClient:
    def __init__(self, modules, kinds=("accepted",), answer="Synthetic answer [1].", elapsed=60):
        self.m, self.kinds, self.answer, self.elapsed, self.calls = (
            modules,
            list(kinds),
            answer,
            elapsed,
            0,
        )

    def run(self, folder, timeout):
        self.calls += 1
        kind = self.kinds.pop(0) if len(self.kinds) > 1 else self.kinds[0]
        c = self.m["common"]
        assert not list((folder / "cwd").iterdir())
        assert (folder / "request/prompt.txt").is_file()
        result = {
            "kind": kind,
            "elapsed_s": self.elapsed,
            "timeout": self.elapsed > timeout,
            "processes_stopped": 0,
        }
        if kind != "infrastructure":
            data = clean_rollout(str(folder / "cwd"), self.answer)
            if kind == "route_failure":
                data.append({"type": "response_item", "payload": {"type": "function_call"}})
            path = folder / "rollout.jsonl"
            path.write_bytes("".join(json.dumps(r) + "\n" for r in data).encode())
            c.write(folder / "job.json", {"write": False})
            result.update(
                gate=self.m["route"].gate(data, folder / "cwd", "thread"),
                thread_id="thread",
                job_id="job",
                rollout_file="synthetic.jsonl",
                rollout_sha256=c.sha(path),
                raw_output_sha256=c.digest(self.answer),
                raw_output_mismatch=False,
            )
        return result

    def recover(self, folder):
        raise AssertionError("completed synthetic attempts must not call a provider on restart")


def synthetic_case(cid="case"):
    return {"case_id": cid, "question": "Question?", "saved": "Exact synthetic prompt"}


def test_redo_counted_out_infrastructure_and_restart(modules, local_tmp):
    c, a = modules["common"], modules["answer"]
    state = a.initial("spec")
    client = FakeClient(
        modules, ("infrastructure", "route_failure", "infrastructure", "route_failure")
    )
    for _ in range(4):
        a.one_attempt(state, local_tmp, "wixqa", synthetic_case(), client, 180, 540, "agents")
    row = state["cases"]["wixqa:case"]
    assert row["status"] == "counted_out" and row["route_failures"] == 2
    assert a.route_numbers(state)["redos"] == 1
    assert a.route_numbers(state)["infrastructure_failures"] == 2
    assert not a.one_attempt(
        state, local_tmp, "wixqa", synthetic_case(), client, 180, 540, "agents"
    )
    assert client.calls == 4
    c.write(local_tmp / "state.json", state)
    restarted = c.read(local_tmp / "state.json")
    a.recover(restarted, local_tmp, {"wixqa": {"case": synthetic_case()}}, client)
    assert restarted == state
    accepted = FakeClient(modules)
    a.one_attempt(
        restarted, local_tmp, "wixqa", synthetic_case("accepted"), accepted, 180, 540, "agents"
    )
    c.write(local_tmp / "state.json", restarted)
    again = c.read(local_tmp / "state.json")
    assert not a.one_attempt(
        again, local_tmp, "wixqa", synthetic_case("accepted"), accepted, 180, 540, "agents"
    )
    assert accepted.calls == 1
    # Simulate a crash after outcome.json but before the state checkpoint.
    a.recover(
        state,
        local_tmp,
        {"wixqa": {"case": synthetic_case(), "accepted": synthetic_case("accepted")}},
        accepted,
    )
    assert state == restarted


def test_forecast_stops_and_probe_exclusion(modules, local_tmp):
    a = modules["answer"]
    state = a.initial("spec")
    a.one_attempt(
        state, local_tmp, "probe", synthetic_case(), FakeClient(modules), 180, 540, "agents"
    )
    assert a.route_numbers(state)["attempts"] == 0
    a.one_attempt(
        state,
        local_tmp,
        "wixqa",
        synthetic_case(),
        FakeClient(modules, elapsed=541),
        180,
        540,
        "agents",
    )
    assert state["stops"] == ["task_forecast"]
    state = a.initial("spec")
    state["forecast"] = a.forecast([61] * 20)
    state["postpilot_seconds"] = 75599
    a.one_attempt(
        state,
        local_tmp,
        "wixqa",
        synthetic_case(),
        FakeClient(modules, elapsed=1),
        90,
        270,
        "agents",
        postpilot=True,
    )
    assert state["stops"] == ["series_forecast"]


def test_pilot_steps_language_and_counted_out_limits(modules):
    a = modules["answer"]
    selected = [
        (key, str(i))
        for key, n in zip(modules["common"].KEYS, (7, 7, 6), strict=True)
        for i in range(n)
    ]
    state = a.initial("spec")
    for index, (key, cid) in enumerate(selected, 1):
        attempt = {
            "id": str(index),
            "kind": "accepted",
            "elapsed_s": 61,
            "task_stop": 540,
            "gate": modules["route"].gate(clean_rollout(), "synthetic-cwd", "thread"),
        }
        a.reduce_attempt(state, key, cid, attempt, "Question?")
        if index in (1, 5, 20):
            assert a.pilot_gate(state, selected, index)
            assert state["pilot_step"] == index
    assert state["pilot_passed"] and state["forecast"]["task"] == 90
    state["cases"]["wixqa:0"]["language"]["match"] = False
    assert not a.pilot_gate(state, selected, 20)
    assert "pilot_failed" in state["stops"]
    state = a.initial("spec")
    for i in range(6):
        for retry in range(2):
            a.reduce_attempt(
                state,
                "wixqa",
                str(i),
                {"id": f"{i}-{retry}", "kind": "route_failure", "elapsed_s": 1, "task_stop": 540},
                "Question",
            )
    assert state["stops"] == ["counted_out_limit"]
    state = a.initial("spec")
    for i in range(6):
        a.reduce_attempt(
            state,
            "wixqa",
            str(i),
            {
                "id": str(i),
                "kind": "accepted",
                "elapsed_s": 1,
                "task_stop": 540,
                "gate": modules["route"].gate(
                    clean_rollout(answer="Ответ"), "synthetic-cwd", "thread"
                ),
            },
            "Question",
        )
    assert state["stops"] == ["language_limit"]


def run_args(local_tmp, command="pilot", **updates):
    values = dict(
        command=command,
        private=local_tmp / "private",
        series="series",
        records=local_tmp / "records",
        spec=local_tmp / "spec",
        codex_home=local_tmp / "home",
        companion=local_tmp / "companion",
        state_root=local_tmp / "private/state",
        node="node",
        s5=local_tmp / "s5",
        i6=local_tmp / "i6",
        step=1,
        key="wixqa",
        budget=840,
        resume_infrastructure=False,
    )
    values.update(updates)
    return SimpleNamespace(**values)


def synthetic_boundaries(monkeypatch, c, records):
    monkeypatch.setattr(c, "registration", lambda *_: "spec")
    monkeypatch.setattr(c, "public_inputs", lambda: {})
    monkeypatch.setattr(c, "outside", lambda p: Path(p).resolve())
    monkeypatch.setattr(c, "output_path", lambda p: Path(p).resolve())
    monkeypatch.setattr(c, "committed", c.sha)
    monkeypatch.setattr(c.instruments().common.protocol, "committed", c.sha)


def test_driver_three_infrastructure_failures_then_no_launch(modules, local_tmp, monkeypatch):
    c, a = modules["common"], modules["answer"]
    args = run_args(local_tmp, command="probe")
    synthetic_boundaries(monkeypatch, c, args.records)
    args.codex_home.mkdir()
    (args.codex_home / "AGENTS.md").write_bytes(b"Synthetic rules\n")
    client = FakeClient(modules, ("infrastructure",))
    code, _ = a.run(args, client=client)
    assert code == 5 and client.calls == 3
    state = c.read(args.private / args.series / "state.json")
    assert state["infrastructure_streak"] == 3
    assert state["cases"]["probe:probe"]["route_failures"] == 0
    assert a.run(args, client=client)[0] == 5 and client.calls == 3
    assert (
        a.run(
            run_args(local_tmp, command="probe", budget=1),
            client=client,
            clock=iter((0, 2)).__next__,
        )[0]
        == 5
    )


def test_budget_and_global_judge_stop_prevent_launch(modules, local_tmp, monkeypatch):
    c, a = modules["common"], modules["answer"]
    args = run_args(local_tmp, command="probe")
    synthetic_boundaries(monkeypatch, c, args.records)
    args.codex_home.mkdir()
    (args.codex_home / "AGENTS.md").write_bytes(b"Synthetic rules\n")
    client = FakeClient(modules)
    assert a.run(args, client=client, clock=iter((0, 841)).__next__)[0] == 3
    assert client.calls == 0
    c.write(args.private / args.series / "wixqa/m1/NOT_EVIDENCE.json", {"reason": "synthetic"})
    assert a.run(args, client=client)[0] == 2
    assert client.calls == 0


def test_judge_seven_unavailable_attempts_and_backoff(modules, local_tmp, monkeypatch):
    c, grading = modules["common"], modules["judge"]
    judge = c.judge()
    folder = local_tmp / "series/wixqa/m1"
    plan = {
        "salt": judge.SALT,
        "instructions_sha256": c.digest(judge.INSTRUCTIONS),
        "route": judge.isolated.settings(judge.SYSTEM_PROMPT),
        "runs": {},
        "items": [
            {"item_id": "item", "message": "synthetic", "message_sha256": c.digest("synthetic")}
        ],
    }
    c.write(folder / "plan.json", plan)
    c.write(local_tmp / "series/state.json", {"stops": []})
    monkeypatch.setattr(grading, "admitted", lambda *_: {"requests": {"m1": 1}})
    count, wall = [0], [0]

    def unavailable(*_):
        count[0] += 1
        raise judge.JudgeUnavailable("synthetic", "not a network request")

    for i in range(7):
        wall[0] = i * 300
        code, _ = grading.grade(
            "wixqa",
            local_tmp / "series",
            local_tmp / "records",
            None,
            sender=unavailable,
            clock=lambda: 0,
            now=lambda: wall[0],
        )
        assert code == (5 if i == 6 else 3)
        assert count[0] == i + 1
        # A restart at the same time cannot shorten the 300-second backoff.
        grading.grade(
            "wixqa",
            local_tmp / "series",
            local_tmp / "records",
            None,
            sender=unavailable,
            clock=lambda: 0,
            now=lambda: wall[0],
        )
        assert count[0] == i + 1
    assert c.read(folder / "retry.json")["consecutive_failures"] == 7


@pytest.mark.parametrize(
    "field", ["question", "answer", "text", "content", "prompt", "document", "reference"]
)
def test_all_public_writers_refuse_text(modules, local_tmp, field):
    c = modules["common"]
    bad = {"nested": [{field: "private prose"}]}
    for writer, value in ((c.public, bad), (c.public_rows, [bad])):
        with pytest.raises(ValueError):
            writer(local_tmp / "refused", value)
        assert not (local_tmp / "refused").exists()
    with pytest.raises(ValueError):
        modules["judge"].public_export(bad)
    c.public(local_tmp / "allowed", {"reference": "none", "question": 1, "answer_sha256": "0" * 64})


def fake_sender(c):
    judge = c.judge()

    def send(_system, message):
        value = dict(
            claims_total=1,
            claims_supported=1,
            context_has_answer=True,
            answers_question="full",
            citations_supported=1,
            defect="none",
            note="synthetic",
            reference="none" if message.endswith("REFERENCE ANSWER:\nnone\n") else "agrees",
        )
        session = {
            "cli_version": "9.9.9",
            "model": judge.isolated.MODEL,
            "loaded": {k: [] for k in judge.isolated.LOADED},
            "builtin": {"plugins": [], "agents": []},
            "turns": 1,
            "context_tokens": 100,
        }
        return judge.isolated.IsolatedReply(
            json.dumps(value), judge.isolated.MODEL, {}, 1.0, session
        )

    return send


def make_package(modules, root):
    c, a = modules["common"], modules["answer"]
    prompts = c.load("agent/prompts.py", "ceiling_test_prompts")
    s5, i6, series = root / "s5", root / "i6", root / "private/series"
    package, old, old_m2 = {}, {}, {}
    stage5 = {"corpora": {}}
    state = a.initial("spec")
    state.update(probe=True, pilot_passed=True, pilot_step=20, forecast=a.forecast([60] * 20))
    client = FakeClient(modules)
    for key in c.KEYS:
        source = s5 if key in c.BASES else i6
        runs, refs, sent = {}, [], []
        old[key], old_m2[key] = {}, {}
        for batch in range(1, 11):
            label = f"final-answers-{key}-b{batch:02d}"
            folder = source / "runs" / label
            runs[label] = folder
            (folder / "prompts").mkdir(parents=True)
            stages, ids = [], []
            for i in range((batch - 1) * 10, batch * 10):
                cid, question = f"{key}-{i:03d}", f"Synthetic question {key} {i}?"
                ids.append(cid)
                raw = (
                    "USER:\n"
                    + prompts.PROMPT_REGISTRY["qa"]["text"].format(
                        context_block="[1 | source=synthetic-source]\nSynthetic context.",
                        question=question,
                    )
                ).encode()
                name = f"{i:03d}-stream.txt"
                (folder / "prompts" / name).write_bytes(raw)
                value = {
                    "case_id": cid,
                    "question": question,
                    "answer": "Package answer [1].",
                    "sources": ["synthetic-source"],
                    "events": [
                        {
                            "type": "result",
                            "answer": "Package answer [1].",
                            "route": "auto",
                            "citations": [1],
                        },
                        {"type": "meta", "other": 7},
                    ],
                }
                c.write(folder / "cases" / f"{i:03d}.json", value)
                stages.append(
                    {
                        "stage": c.instruments().common.v5.STAGE,
                        "event": "end",
                        "prompt_file": name,
                        "wall_sec": 1,
                        "first_chunk_sec": 0.5,
                        "chunks": 1,
                    }
                )
                inside, outside, _ = c.EXPECTED[key]
                gold = i < inside + outside
                row = {
                    "case_id": cid,
                    "prompt_sha256": c.digest(raw),
                    "grade": "good" if i % 2 else "bad",
                    "missing": False,
                    "context_has_answer": i < inside,
                    "claims_total": 1,
                    "claims_supported": 1,
                    "answers_question": "full",
                    "defect": "none",
                    "marks_listed": 1,
                    "marks_unlisted": 0,
                }
                if key in c.BASES:
                    row.update(
                        cluster=i // 2,
                        stratum="simulated"
                        if key == "wixqa"
                        else "answerable"
                        if gold
                        else "not_answerable",
                    )
                    refs.append(
                        {
                            "case_id": cid,
                            "cluster": row["cluster"],
                            "stratum": row["stratum"],
                            "reference_answers": ["Synthetic reference."] if gold else [],
                        }
                    )
                    sent.append(
                        {
                            "case_id": cid,
                            "prompt_sha256": c.digest(raw),
                            "gold": gold,
                            "hit": int(i < inside) if gold else None,
                        }
                    )
                old[key][cid] = row
                old_m2[key][cid] = {
                    **row,
                    "has_reference": gold,
                    "m2": "agrees" if gold else "wrong",
                }
                a.one_attempt(
                    state,
                    series,
                    key,
                    {"case_id": cid, "question": question, "saved": raw.decode()},
                    client,
                    180,
                    540,
                    "agents",
                )
            c.write(
                folder / "launch.json",
                {
                    "status": "complete",
                    "code_sha": c.STANDS[key],
                    "model": c.instruments().common.MODEL,
                    "model_digest": c.instruments().common.DIGEST,
                    "cases": ids,
                    "tenant": key if key == "aircargo" else "ext_" + key,
                },
            )
            (folder / "stages.jsonl").write_bytes(
                "".join(json.dumps(r) + "\n" for r in stages).encode()
            )
        refs_file = source / "references" / (key + ".jsonl")
        if refs:
            refs_file.parent.mkdir(exist_ok=True)
            refs_file.write_bytes("".join(json.dumps(r) + "\n" for r in refs).encode())
            stage5["corpora"][key] = {"sent_cases": sent}
        plan = c.judge().build_plan(
            runs, {}, references_sha256=c.sha(refs_file) if refs else None, withheld=bool(refs)
        )
        source_judge = source / "judge" / (key + "-m1" if refs else "m1")
        c.write(source_judge / "plan.json", plan)
        c.judge().run_plan(plan, source_judge, fake_sender(c))
        provenance = {
            "references_sha256": c.sha(refs_file) if refs else None,
            "plan_sha256": c.sha(source_judge / "plan.json"),
            "verdicts_sha256": c.sha(source_judge / "verdicts.jsonl"),
            "reading": {"text": "synthetic historical reading"},
        }
        for metric in ("m1", "m2") if refs else ("m1",):
            target = root / "old" / f"{key}-{metric}.json"
            c.write(target, {"provenance": provenance})
            c.public_rows(
                target.with_suffix(".cases.jsonl"),
                list((old[key] if metric == "m1" else old_m2[key]).values()),
            )
        package[key] = (
            c.instruments().replay.cases(source / "runs", key)
            if refs
            else c.aircargo_cases(source / "runs")
        )
    state["input_hashes"] = a.input_hashes(s5, i6)
    c.write(series / "state.json", state)
    return SimpleNamespace(
        s5=s5,
        i6=i6,
        series=series,
        package=package,
        old=old,
        old_m2=old_m2,
        stage5=stage5,
        state=state,
    )


def test_freeze_real_plans_copy_and_changed_input(modules, local_tmp, monkeypatch):
    c, grading = modules["common"], modules["judge"]
    records = local_tmp / "records"
    synthetic_boundaries(monkeypatch, c, records)
    # This synthetic-only integration must stay inside the allowed workspace.
    # Replace V6's path boundary here only; production source_gate still refuses
    # repository inputs and verifies the outside copy's plan/verdict hashes.
    monkeypatch.setattr(c.instruments().judge, "outside", lambda p: Path(p).resolve())
    data = make_package(modules, local_tmp)
    monkeypatch.setattr(
        c, "old_path", lambda key, metric: local_tmp / "old" / f"{key}-{metric}.json"
    )
    monkeypatch.setattr(
        c.instruments().judge,
        "old_export",
        lambda path, *_: (c.read(path), c.unique(c.rows(path.with_suffix(".cases.jsonl")))),
    )
    total = 0
    for key in c.KEYS:
        pin = grading.freeze(key, data.s5, data.i6, data.series, records)
        assert pin["requests"] == (
            {"m1": 115, "m2": 115, "bridge": 15} if key in c.BASES else {"m1": 115, "bridge": 15}
        )
        total += sum(pin["requests"].values())
        grading.validate_frozen(key, data.series / key, pin, data.series)
        grading.admitted(key, data.series, records)
        for batch in range(1, 11):
            label = f"final-answers-{key}-b{batch:02d}"
            source = (data.s5 if key in c.BASES else data.i6) / "runs" / label
            target = data.series / key / "runs" / label
            assert c.sha(source / "launch.json") == c.sha(target / "launch.json")
            for path in (source / "cases").glob("*.json"):
                before, after = c.read(path), c.read(target / "cases" / path.name)
                assert before["answer"] != after["answer"]
                before["answer"] = before["events"][0]["answer"] = "Synthetic answer [1]."
                assert before == after
            old_answers, new_answers = c.judge().run_answers(source), c.judge().run_answers(target)
            assert [r["prompt_sha256"] for r in old_answers] == [
                r["prompt_sha256"] for r in new_answers
            ]
        plan = c.read(data.series / key / "m1/plan.json")
        assert all(i["has_reference"] is False for i in plan["items"])
        assert sum("retest_of" in i for i in plan["items"]) == 15
    assert total == 620
    path = data.s5 / "runs/final-answers-wixqa-b01/prompts/000-stream.txt"
    original = path.read_bytes()
    path.write_bytes(original + b"changed")
    with pytest.raises(ValueError, match="source input changed"):
        grading.validate_frozen(
            "wixqa", data.series / "wixqa", c.read(records / "plans-wixqa.json"), data.series
        )
    path.write_bytes(original)
    # Exercise successful chunks, resumability, export_one and build on the same
    # three-key store, retaining real admission/export/stability/statistics.
    calls = []
    send = fake_sender(c)

    def sender(system, message):
        calls.append(message)
        return send(system, message)

    for key in c.KEYS:
        pin = c.read(records / f"plans-{key}.json")
        # Seed a realistic resumed chunk with one pending request per metric.
        # Bulk run_plan uses the same sender/verdict admission and keeps this
        # integration under two minutes without 620 journal rescans in grade.
        for metric in c.metrics(key):
            folder = data.series / key / metric
            c.judge().run_plan(
                c.read(folder / "plan.json"), folder, sender, limit=pin["requests"][metric] - 1
            )
        before = len(calls)
        assert (
            grading.grade(key, data.series, records, None, sender=sender, clock=lambda: 0)[0] == 0
        )
        assert len(calls) - before == len(c.metrics(key))
        before = len(calls)
        assert (
            grading.grade(key, data.series, records, None, sender=sender, clock=lambda: 0)[0] == 0
        )
        assert len(calls) == before
        for metric in c.metrics(key):
            duration = c.read(data.series / key / metric / "grade-clock.json")
            assert duration["forecast"] == pin["requests"][metric] * 130
            assert 3 * duration["forecast"] == (5850 if metric == "bridge" else 44850)
            result = grading.export_one(key, data.series, records, None, metric)
            path = records / (c.plan_name(key, metric) + ".json")
            assert c.read(path) == result
            assert result["status"] == "counted" and result["retest"]["pairs"] == 15
            if metric != "bridge":
                assert len(c.rows(path.with_suffix(".cases.jsonl"))) == 100
            c.public_guard(result)
    assert len(calls) == 620
    # Redirect only the repository M3 record to its synthetic counterpart.
    stage5_path = c.ROOT / "reports/stage4-final/stage5/2057ad0/record.json"
    original_read = c.read
    monkeypatch.setattr(
        c, "read", lambda path: data.stage5 if Path(path) == stage5_path else original_read(path)
    )
    reading, code = modules["record"].build(data.series, records)
    assert code == 0 and reading == c.read(records / "reading.json")
    assert reading["decision"]["row"] == 2
    assert reading["primary"]["n"] == 224 and reading["m2"]["n"] == 180
    assert modules["record"].decision(reading["primary"], [], False)["row"] == 2
    assert reading["corpora"]["conditionalqa"]["right_declines"]["n"] == 20
    for key in c.KEYS:
        loss = reading["corpora"][key]["losses"]
        assert (
            loss["package_not_good"]
            == sum(
                loss[n]["n"]
                for n in (
                    "generator_losses",
                    "retrieval_losses",
                    "neither",
                    "codex_good_without_gold_in_context",
                )
            )
            == 50
        )
    c.public_guard(reading)
    wrong = copy.deepcopy(data.stage5)
    wrong["corpora"]["wixqa"]["sent_cases"][0]["hit"] = 0
    with pytest.raises(ValueError, match="stratum counts"):
        modules["record"].strata(data.old, wrong)
    # The real reader records a rule stop and returns 2 even with a missing plan.
    stopped_state = c.read(data.series / "state.json")
    stopped_state["stops"] = ["task_forecast"]
    c.write(data.series / "state.json", stopped_state)
    (data.series / "wixqa/m1/plan.json").unlink()
    stopped, code = modules["record"].build(data.series, records)
    assert code == 2 and stopped["decision"]["row"] == 1
    assert stopped == c.read(records / "reading.json")
    stopped_state["stops"] = []
    c.write(data.series / "state.json", stopped_state)
    refused, code = modules["record"].build(data.series, records)
    assert code == 0 and refused["decision"]["row"] == 1
    assert refused == c.read(records / "reading.json")


def test_decision_and_interval_agreement(modules, monkeypatch):
    record = modules["record"]
    primary = {"n": 224, "detected": True, "direction": "rises"}
    assert record.decision(primary, ["missing_plan"], False)["row"] == 1
    assert record.decision(primary, [], True)["row"] == 1
    assert record.decision(primary, [], False)["row"] == 2
    assert (
        record.decision({**primary, "detected": False, "direction": "not detected"}, [], False)[
            "row"
        ]
        == 3
    )
    assert record.decision({**primary, "direction": "falls"}, [], False)["row"] == 3
    from evaluation import semantic_ruler

    monkeypatch.setattr(
        semantic_ruler, "cluster_summary", lambda *_: {"ci95": [-0.01, 1], "clusters": 20}
    )
    first, second = dict.fromkeys(range(20), 0), dict.fromkeys(range(20), 1)
    value = record.pair(first, second, {i: [str(i)] for i in first})
    assert value["newcombe95"][0] > 0 and not value["detected"]
    assert value["read95"][0] == -0.01
    with pytest.raises(ValueError, match="primary n"):
        record.primary(
            {k: {} for k in modules["common"].KEYS},
            {k: {} for k in modules["common"].KEYS},
            {k: {} for k in modules["common"].KEYS},
        )


def test_counted_out_bad_and_loss_partition(modules):
    record = modules["record"]
    new = {"x": {"grade": "bad", "empty_answer": True}}
    assert (
        record.normalize_counted_out(new, {"x": {"status": "counted_out"}})["x"]["grade"] == "bad"
    )
    loss = record.loss_accounting({"x": {"grade": "partial_ok"}}, new, {"x": "answer in context"})
    assert loss["neither"] == {"n": 1, "ids": ["x"]}
    with pytest.raises(ValueError):
        record.normalize_counted_out({"x": {"grade": "good"}}, {"x": {"status": "counted_out"}})


def test_imports_have_no_process_network_or_private_io(modules, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("side effect during tool import")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    for module in modules.values():
        importlib.reload(module)


def test_malformed_rollout_is_reproducible_route_failure(modules):
    result = modules["route"].rollout_gate(b"not-json\n", "cwd", "thread", {"write": False})
    assert not result["passed"] and result["reasons"] == ["malformed_rollout"]


def test_companion_retains_parent_until_owned_cleanup(modules, local_tmp, monkeypatch):
    c, route = modules["common"], modules["route"]
    folder = local_tmp / "attempt"
    (folder / "cwd").mkdir(parents=True)
    (folder / "request").mkdir()
    (folder / "request/prompt.txt").write_bytes(b"OK")
    c.write(folder / "launch.json", {"started": "2026-11-02T00:00:00+00:00"})
    client = route.CompanionClient.__new__(route.CompanionClient)
    client.node, client.companion = "node", local_tmp / "companion"
    client.codex_home, client.state_root = local_tmp / "home", local_tmp / "state"
    calls = []

    def popen(command, **kwargs):
        calls.append((command, kwargs))

        class Process:
            def wait(self, timeout):
                raise subprocess.TimeoutExpired(command, timeout)

        return Process()

    monkeypatch.setattr(route.subprocess, "Popen", popen)
    monkeypatch.setattr(
        route.subprocess,
        "run",
        lambda *_a, **_k: pytest.fail("run kills the parent before the owned tree can be built"),
    )
    monkeypatch.setattr(client, "collect", lambda _folder, _started, **transport: transport)
    result = client.run(folder, 1)
    assert result["timed_out"] and result["returncode"] == -1
    command, kwargs = calls[0]
    assert command == [
        "node",
        str(client.companion),
        "task",
        "--model",
        "gpt-6-astra",
        "--effort",
        "xhigh",
        "--cwd",
        str(folder / "cwd"),
        "--prompt-file",
        str(folder / "request/prompt.txt"),
    ]
    assert "CODEX_COMPANION_APP_SERVER_ENDPOINT" not in kwargs["env"]
    assert kwargs["env"]["CLAUDE_PLUGIN_DATA"] == str(client.state_root)
    assert kwargs["env"]["CODEX_HOME"] == str(client.codex_home)


def test_registration_requires_status_line_not_quoted_instructions(modules, local_tmp, monkeypatch):
    c = modules["common"]
    spec = local_tmp / "draft.md"
    spec.write_bytes(
        b"Status: **draft**\n\nSet `Status: **registered before the first request**` later.\n"
    )
    monkeypatch.setattr(c, "tool_hashes", lambda: {})
    monkeypatch.setattr(c, "INPUT_PINS", {})
    monkeypatch.setattr(c, "committed", c.sha)
    with pytest.raises(ValueError, match="spec is a draft"):
        c.registration(spec)
    spec.write_bytes(b"Status: **registered before the first request**\n")
    assert c.registration(spec) == c.sha(spec)


def rollout_bytes(entries):
    return b"".join((json.dumps(row, ensure_ascii=False) + "\n").encode() for row in entries)


@pytest.mark.parametrize("separator", ["\u2028", "\u2029", "\u0085"])
def test_rollout_splits_only_lf(modules, separator):
    answer = "First" + separator + "last"
    result = modules["route"].rollout_gate(
        rollout_bytes(clean_rollout(answer=answer)), "synthetic-cwd", "thread", {"write": False}
    )
    assert result["passed"] and result["answer"] == answer


@pytest.mark.parametrize("info", [None, {}, {"total_token_usage": None}])
def test_last_non_null_usage_survives(modules, info):
    entries = clean_rollout() + [
        {"type": "event_msg", "payload": {"type": "token_count", "info": info}}
    ]
    result = modules["route"].gate(entries, "synthetic-cwd", "thread")
    assert result["passed"] and result["tokens"]["total_tokens"] == 13


def collection_fixture(modules, root, *, answer="OK"):
    c, route = modules["common"], modules["route"]
    folder = root / "attempt"
    (folder / "cwd").mkdir(parents=True)
    started = "2026-11-02T00:00:00+00:00"
    c.write(folder / "launch.json", {"started": started, "task_stop": 540})
    client = route.CompanionClient(root / "companion", root / "home", root / "state")
    record = {
        "id": "job",
        "threadId": "thread",
        "workspaceRoot": str(folder / "cwd"),
        "createdAt": started,
        "write": False,
        "status": "completed",
        "result": {"status": 0, "rawOutput": answer},
    }
    job = client.state_root / "state/synthetic/jobs/job.json"
    c.write(job, record)
    rollout = client.codex_home / "sessions/rollout-synthetic-thread.jsonl"
    rollout.parent.mkdir(parents=True)
    rollout.write_bytes(rollout_bytes(clean_rollout(str(folder / "cwd"), answer)))
    return SimpleNamespace(
        client=client, folder=folder, started=started, job=job, record=record, rollout=rollout
    )


@pytest.mark.parametrize("failure", [None, "exit", "job", "result", "missing"])
def test_collect_transport_messages_require_failed_status(modules, local_tmp, monkeypatch, failure):
    c, route = modules["common"], modules["route"]
    data = collection_fixture(modules, local_tmp, answer="The network connection timed out.")
    data.record["message"] = "The network connection timed out."
    data.record["result"]["stderr"] = "network"
    if failure == "job":
        data.record["status"] = "failed"
    if failure == "result":
        data.record["result"]["status"] = 1
    c.write(data.job, data.record)
    if failure == "missing":
        data.job.unlink()
    (data.folder / "stderr.bin").write_bytes(b"connection timed out")
    monkeypatch.setattr(
        route, "cleanup", lambda *_: {"processes_stopped": 2, "processes_exited": 0}
    )
    result = data.client.collect(data.folder, data.started, returncode=int(failure == "exit"))
    assert result["kind"] == ("accepted" if failure is None else "infrastructure")
    assert result["processes_stopped"] == 2 and c.read(data.folder / "outcome.json") == result
    if failure is None:
        assert result["gate"]["answer"] == data.record["result"]["rawOutput"]
        assert result["rollout_sha256"] == c.sha(data.folder / "rollout.jsonl")
        assert not result["raw_output_mismatch"]


@pytest.mark.parametrize("incomplete", ["tail", "completion"])
@pytest.mark.parametrize("finishes", [False, True])
def test_collect_waits_for_complete_rollout(modules, local_tmp, monkeypatch, incomplete, finishes):
    route = modules["route"]
    data = collection_fixture(modules, local_tmp)
    full = data.rollout.read_bytes()
    partial = (
        full[:-8]
        if incomplete == "tail"
        else rollout_bytes(clean_rollout(str(data.folder / "cwd"))[:-1])
    )
    data.rollout.write_bytes(partial)
    waits = []

    def sleep(seconds):
        waits.append(seconds)
        if finishes:
            data.rollout.write_bytes(full)

    monkeypatch.setattr(route.time, "sleep", sleep)
    monkeypatch.setattr(
        route, "cleanup", lambda *_: {"processes_stopped": 0, "processes_exited": 0}
    )
    result = data.client.collect(data.folder, data.started)
    assert result["kind"] == ("accepted" if finishes else "infrastructure")
    assert waits and (sum(waits) <= 10 if finishes else sum(waits) == 10)
    assert (data.folder / "rollout.jsonl").read_bytes() == (full if finishes else partial)
    if not finishes:
        assert result["reason"] == "incomplete_rollout"


def test_collect_complete_route_failure_and_raw_mismatch(modules, local_tmp, monkeypatch):
    route = modules["route"]
    data = collection_fixture(modules, local_tmp)
    entries = clean_rollout(str(data.folder / "cwd"), "Different answer")
    entries.insert(-1, {"type": "response_item", "payload": {"type": "function_call"}})
    data.rollout.write_bytes(rollout_bytes(entries))
    monkeypatch.setattr(
        route, "cleanup", lambda *_: {"processes_stopped": 0, "processes_exited": 0}
    )
    monkeypatch.setattr(
        route.time, "sleep", lambda *_: pytest.fail("complete rollout must not wait")
    )
    result = data.client.collect(data.folder, data.started)
    assert result["kind"] == "route_failure" and result["raw_output_mismatch"]


class FakeKernel:
    def __init__(
        self, created, *, termination_fails=(), exit_on_failure=(), exited=(), gone=(), live=()
    ):
        self.created, self.stopped, self.closed = created, [], []
        self.termination_fails = set(termination_fails)
        self.exit_on_failure, self.exited = set(exit_on_failure), set(exited)
        self.gone, self.live = set(gone), set(live)
        self.opened, self.waits, self.terminated = [], [], []
        self.error = 0

    def OpenProcess(self, access, _inherit, pid):
        self.opened.append((access, pid))
        if pid in self.gone:
            self.error = 87
            return 0
        return pid

    def GetProcessTimes(self, handle, created, *_times):
        created._obj.value = self.created[handle]
        return 1

    def WaitForSingleObject(self, handle, timeout):
        self.waits.append((handle, timeout))
        if timeout == 0 and handle in self.live:
            return 258
        return 0 if handle in self.stopped or handle in self.exited else 258

    def TerminateProcess(self, handle, _code):
        self.terminated.append(handle)
        if handle in self.termination_fails:
            self.error = 5
            if handle in self.exit_on_failure:
                self.exited.add(handle)
            return 0
        self.stopped.append(handle)
        return 1

    def CloseHandle(self, handle):
        self.closed.append(handle)


def process_snapshot(cwd):
    return [
        {
            "pid": pid,
            "parent": parent,
            "created": created,
            "command": command,
            "created_dmtf": "20261102000000.123456+000",
        }
        for pid, parent, created, command in (
            (10, 1, 1000, "node " + str(cwd)),
            (11, 10, 1020, "broker"),
            (12, 11, 1040, "app-server"),
            (13, 10, 990, "unrelated older"),
            (14, 1, 1050, "unrelated"),
            (15, 10, 1060, "reused pid"),
        )
    ]


def test_cleanup_termination_race_counts_exit_and_stops_rest(modules, monkeypatch):
    route = modules["route"]
    rows = process_snapshot("unique/cwd")[:3]
    kernel = FakeKernel(
        {10: 1007, 11: 1029, 12: 1041}, termination_fails=(12,), exit_on_failure=(12,)
    )
    snapshots = iter((rows, []))
    ticks = iter((100, 102, 104, 106))
    monkeypatch.setattr(route.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(route.ctypes, "get_last_error", lambda: kernel.error, raising=False)
    result = route.cleanup("unique/cwd", snapshot=lambda: next(snapshots), kernel=kernel)
    assert result == {"processes_stopped": 2, "processes_exited": 1}
    assert kernel.error == 5 and kernel.terminated == [12, 11, 10]
    assert kernel.stopped == [11, 10] and kernel.closed == [12, 11, 10]
    assert kernel.waits == [(12, 0), (12, 18000), (11, 0), (11, 16000), (10, 0), (10, 14000)]


def test_cleanup_termination_failure_times_out(modules, monkeypatch):
    route = modules["route"]
    kernel = FakeKernel({10: 1007}, termination_fails=(10,))
    ticks = iter((100, 119.5))
    monkeypatch.setattr(route.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(route.ctypes, "get_last_error", lambda: kernel.error, raising=False)
    with pytest.raises(TimeoutError, match="owned process stop timed out") as caught:
        route.cleanup(
            "unique/cwd", snapshot=lambda: process_snapshot("unique/cwd")[:1], kernel=kernel
        )
    outcome = {}
    route.cleanup_failure(outcome, caught.value)
    assert outcome["reason"] == "cleanup_timeout" and outcome["cleanup_failed"]
    assert kernel.error == 5 and kernel.waits == [(10, 0), (10, 500)]
    assert kernel.closed == [10] and not kernel.stopped


@pytest.mark.parametrize("member", ["cwd", "tree"])
@pytest.mark.parametrize("state", ["signalled", "gone", "reused", "live"])
def test_cleanup_second_snapshot_checks_handle(modules, monkeypatch, member, state):
    route = modules["route"]
    rows = process_snapshot("unique/cwd")[:3]
    proc = {**rows[0], "pid": 99} if member == "cwd" else rows[2]
    kernel = FakeKernel(
        {10: 1007, 11: 1029, 12: 1041, 99: 1007},
        exited=(proc["pid"],) if member == "cwd" and state == "signalled" else (),
        live=(proc["pid"],) if state == "live" else (),
    )
    monkeypatch.setattr(route.ctypes, "get_last_error", lambda: kernel.error, raising=False)
    snapshots = iter((rows, [proc]))

    def snapshot():
        current = next(snapshots)
        if current is not rows:
            if state == "gone":
                kernel.gone.add(proc["pid"])
            elif state == "reused":
                kernel.created[proc["pid"]] += 10
        return current

    if state == "live":
        with pytest.raises(route.CleanupFailed) as caught:
            route.cleanup("unique/cwd", snapshot=snapshot, kernel=kernel)
        assert caught.value.tree == route.process_tree(rows, "unique/cwd")
        assert caught.value.stopped == 3
    else:
        assert route.cleanup("unique/cwd", snapshot=snapshot, kernel=kernel) == {
            "processes_stopped": 3,
            "processes_exited": 0,
        }
    # The final snapshot is checked without requesting termination rights.
    assert kernel.opened[-1] == (0x100000 | 0x1000, proc["pid"])
    assert kernel.terminated == [12, 11, 10]
    assert len(kernel.closed) == (3 if state == "gone" else 4)


@pytest.mark.parametrize("recover", [False, True])
def test_cleanup_exit_counter_is_journaled(modules, local_tmp, monkeypatch, recover):
    c, route, arm = modules["common"], modules["route"], modules["answer"]
    data = collection_fixture(modules, local_tmp)
    c.write(data.folder / "transport.json", {"returncode": 0, "timed_out": False, "elapsed": 1})
    rows = process_snapshot(data.folder / "cwd")[:3]
    kernel = FakeKernel(
        {10: 1007, 11: 1029, 12: 1041}, termination_fails=(12,), exit_on_failure=(12,)
    )
    snapshots = iter((rows, [], [], []))
    cleanup = route.cleanup
    monkeypatch.setattr(
        route, "cleanup", lambda cwd: cleanup(cwd, snapshot=lambda: next(snapshots), kernel=kernel)
    )
    result = (
        data.client.recover(data.folder)
        if recover
        else data.client.collect(data.folder, data.started)
    )
    assert result["kind"] == "accepted"
    assert result["processes_stopped"] == 2 and result["processes_exited"] == 1
    assert c.read(data.folder / "outcome.json") == result
    state = arm.initial("spec")
    arm.reduce_attempt(
        state, "wixqa", "case", {"id": "attempt", "task_stop": 540, **result}, "Question"
    )
    assert arm.attempt_public(result)["processes_exited"] == 1
    assert arm.route_numbers(state)["processes_exited"] == 1
    assert arm.route_numbers(state)["processes_stopped"] == 2


def test_cleanup_common_precision_and_pid_reuse(modules):
    route = modules["route"]
    first = process_snapshot("unique/cwd")
    # Native FILETIME retains sub-microsecond ticks; pid 15 has been reused.
    kernel = FakeKernel({10: 1007, 11: 1029, 12: 1041, 15: 1071})
    snapshots = iter((first, [{**first[-1], "created": 1070}, *first[3:5]]))
    assert route.cleanup("unique/cwd", snapshot=lambda: next(snapshots), kernel=kernel) == {
        "processes_stopped": 3,
        "processes_exited": 0,
    }
    assert kernel.stopped == [12, 11, 10]
    assert set(kernel.closed) == {10, 11, 12, 15}


@pytest.mark.parametrize("fraction,native,stopped", [("1234567", 1001, 0), ("123", 9999, 1)])
def test_cleanup_derives_snapshot_precision(modules, fraction, native, stopped):
    proc = {
        "pid": 10,
        "parent": 1,
        "created": 0 if len(fraction) == 3 else 1000,
        "command": "node unique/cwd",
        "created_dmtf": f"20261102000000.{fraction}+000",
    }
    kernel = FakeKernel({10: native})
    snapshots = iter(([proc], []))
    assert modules["route"].cleanup(
        "unique/cwd", snapshot=lambda: next(snapshots), kernel=kernel
    ) == {"processes_stopped": stopped, "processes_exited": 0}


@pytest.mark.parametrize("survivor", ["root", "child", "new_root"])
def test_cleanup_survivor_records_failure_and_blocks_launch(
    modules, local_tmp, monkeypatch, survivor
):
    c, route, arm = modules["common"], modules["route"], modules["answer"]
    data = collection_fixture(modules, local_tmp)
    rows = process_snapshot(data.folder / "cwd")[:3]
    alive = [rows[0 if survivor == "root" else 2]]
    if survivor == "new_root":
        alive = [{**rows[0], "pid": 99, "created": 1080}]
    # Deliberately report a live handle in the final check despite the successful
    # termination wait, so this test still exercises the survivor failure path.
    kernel = FakeKernel({10: 1007, 11: 1029, 12: 1041, 99: 1089}, live=(alive[0]["pid"],))
    cleanup = route.cleanup
    snapshots = iter((rows, alive))
    monkeypatch.setattr(
        route, "cleanup", lambda cwd: cleanup(cwd, snapshot=lambda: next(snapshots), kernel=kernel)
    )
    result = data.client.collect(data.folder, data.started)
    assert result["kind"] == "infrastructure" and result["cleanup_failed"]
    assert result["processes_stopped"] == 3
    assert c.read(data.folder / "outcome.json")["cleanup_failed"]
    state = arm.initial("spec")
    arm.reduce_attempt(
        state, "wixqa", "case", {"id": "attempt", "task_stop": 540, **result}, "Question"
    )
    assert state["cleanup_pending"] == "attempt"
    args = run_args(local_tmp, command="probe")
    synthetic_boundaries(monkeypatch, c, args.records)
    args.codex_home.mkdir(exist_ok=True)
    (args.codex_home / "AGENTS.md").write_bytes(b"Synthetic rules\n")
    c.write(args.private / args.series / "state.json", state)
    c.write(args.private / args.series / "attempts/attempt/outcome.json", result)
    pending_cwd = args.private / args.series / "attempts/attempt/cwd"
    alive = [
        {**p, "command": p["command"].replace(str(data.folder / "cwd"), str(pending_cwd))}
        for p in alive
    ]
    monkeypatch.setattr(
        route,
        "cleanup",
        lambda cwd, **kw: cleanup(cwd, snapshot=lambda: alive, kernel=kernel, **kw),
    )
    client = FakeClient(modules)
    with pytest.raises(ValueError, match="surviv"):
        arm.run(args, client=client)
    assert client.calls == 0
    assert c.read(args.private / args.series / "state.json")["cleanup_pending"] == "attempt"
    assert c.read(args.private / args.series / "attempts/attempt/outcome.json")[
        "cleanup_tree"
    ] == route.process_tree(alive, pending_cwd, result["cleanup_tree"])


@pytest.mark.parametrize(
    "transport",
    [
        None,
        {"returncode": 0, "timed_out": False, "elapsed": 60},
        {"returncode": -1, "timed_out": True, "elapsed": 540},
    ],
)
def test_companion_recover_uses_only_durable_timeout(modules, local_tmp, monkeypatch, transport):
    c, route, arm = modules["common"], modules["route"], modules["answer"]
    data = collection_fixture(modules, local_tmp)
    # An ancient wall-clock start models a crash or laptop sleep, not a timed task.
    c.write(data.folder / "launch.json", {"started": "2000-01-01T00:00:00+00:00", "task_stop": 540})
    if transport:
        c.write(data.folder / "transport.json", transport)
    stopped = iter(
        (
            {"processes_stopped": 2, "processes_exited": 0},
            {"processes_stopped": 0, "processes_exited": 0},
        )
    )
    monkeypatch.setattr(route, "cleanup", lambda *_: next(stopped))
    result = data.client.recover(data.folder)
    assert result["kind"] == (
        "accepted" if transport and transport["returncode"] == 0 else "infrastructure"
    )
    assert result["timeout"] is bool(transport and transport["timed_out"])
    assert result["processes_stopped"] == 2 and c.read(data.folder / "outcome.json") == result
    state = arm.initial("spec")
    arm.reduce_attempt(
        state, "wixqa", "case", {"id": "attempt", "task_stop": 540, **result}, "Question"
    )
    assert state["stops"] == (["task_forecast"] if transport and transport["timed_out"] else [])


def test_registration_refusal_leaves_no_phantom_launch(modules, local_tmp):
    arm = modules["answer"]
    client, state = FakeClient(modules), arm.initial("spec")

    def refuse():
        raise ValueError("registration changed")

    with pytest.raises(ValueError, match="registration changed"):
        arm.one_attempt(
            state,
            local_tmp,
            "wixqa",
            synthetic_case(),
            client,
            180,
            540,
            "agents",
            before_launch=refuse,
        )
    assert not list(local_tmp.rglob("launch.json")) and client.calls == 0
    arm.recover(state, local_tmp, {"wixqa": {"case": synthetic_case()}}, client)
    assert not state["cases"]


@pytest.mark.parametrize(
    "answer,passed", [("OK", True), (" OK.\n", True), ("OK..", False), ("OK!", False)]
)
def test_probe_normalizes_one_period(modules, local_tmp, monkeypatch, answer, passed):
    c, arm = modules["common"], modules["answer"]
    args = run_args(local_tmp, command="probe")
    synthetic_boundaries(monkeypatch, c, args.records)
    args.codex_home.mkdir()
    (args.codex_home / "AGENTS.md").write_bytes(b"Synthetic rules\n")
    client = FakeClient(modules, answer=answer)
    assert arm.run(args, client=client)[0] == (0 if passed else 2)
    assert c.read(args.private / args.series / "state.json")["probe"] is passed
    assert client.calls == 1


@pytest.mark.parametrize(
    "elapsed,route_timeout,expected",
    [(0, 1200, 1140), (599.5, 1200, 540.5), (599.5, 500, 500), (600, 1200, None)],
)
def test_grade_request_headroom(modules, local_tmp, monkeypatch, elapsed, route_timeout, expected):
    c, grading = modules["common"], modules["judge"]
    judge = c.judge()
    folder = local_tmp / "series/wixqa/m1"
    c.write(
        folder / "plan.json",
        {
            "salt": judge.SALT,
            "instructions_sha256": c.digest(judge.INSTRUCTIONS),
            "route": judge.isolated.settings(judge.SYSTEM_PROMPT),
            "runs": {},
            "items": [
                {
                    "item_id": "item",
                    "message": "synthetic",
                    "message_sha256": c.digest("synthetic"),
                    "marks_listed": 1,
                    "marks_unlisted": 0,
                    "has_reference": True,
                }
            ],
        },
    )
    c.write(local_tmp / "series/state.json", {"stops": []})
    monkeypatch.setattr(grading, "admitted", lambda *_: {"requests": {"m1": 1}})
    monkeypatch.setattr(c, "metrics", lambda _: ("m1",))
    monkeypatch.setattr(grading, "exports", lambda *_: ({"status": "counted"}, None))
    monkeypatch.setattr(judge, "CLI_TIMEOUT_S", route_timeout)
    timeouts = []

    def sender(timeout):
        timeouts.append(timeout)
        return fake_sender(c)

    monkeypatch.setattr(judge, "_isolated_sender", sender)
    ticks = iter((0,))
    code, _ = grading.grade(
        "wixqa",
        local_tmp / "series",
        local_tmp / "records",
        None,
        clock=lambda: next(ticks, elapsed),
    )
    assert timeouts == ([] if expected is None else [expected])
    assert code == (3 if expected is None else 0)
    if expected is not None:
        assert elapsed + expected <= 1140
    with pytest.raises(ValueError, match="budget"):
        grading.grade("wixqa", local_tmp / "series", local_tmp / "records", None, budget=601)


def test_source_gate_keeps_repository_boundary(modules, local_tmp):
    with pytest.raises(SystemExit, match="outside repository"):
        modules["common"].instruments().judge.source_gate(local_tmp / "i6/judge/m1", {})


@pytest.mark.parametrize("elapsed", [61, 361])
def test_driver_pilot_steps_then_key_and_restart(modules, local_tmp, monkeypatch, elapsed):
    c, arm = modules["common"], modules["answer"]
    args = run_args(local_tmp, command="probe")
    synthetic_boundaries(monkeypatch, c, args.records)
    args.codex_home.mkdir()
    (args.codex_home / "AGENTS.md").write_bytes(b"Synthetic rules\n")
    package = {key: [synthetic_case(f"{key}-{i:03d}") for i in range(100)] for key in c.KEYS}
    monkeypatch.setattr(c, "package_cases", lambda *_: package)
    monkeypatch.setattr(arm, "input_hashes", lambda *_: {"synthetic": "fixed"})
    client = FakeClient(modules, answer="OK.", elapsed=elapsed)
    assert arm.run(args, client=client, clock=lambda: 0)[0] == 0
    client.answer = "Synthetic answer"
    args.command = "pilot"
    for step in (1, 5, 20):
        args.step = step
        assert arm.run(args, client=client, clock=lambda: 0)[0] == 0
        state = c.read(args.private / args.series / "state.json")
        assert state["pilot_step"] == step and client.calls == step + 1
        selected = set(arm.pilot(package)[:step])
        assert {
            (r["key"], r["case_id"]) for r in state["cases"].values() if r["key"] != "probe"
        } == selected
    assert state["pilot_passed"]
    assert state["forecast"]["task"] == (90 if elapsed == 61 else 390)
    args.command = "run"
    if elapsed == 361:
        with pytest.raises(ValueError, match="amendment"):
            arm.run(args, client=client, clock=lambda: 0)
        assert client.calls == 21
        return
    assert arm.run(args, client=client, clock=lambda: 0)[0] == 0
    assert client.calls == 114  # probe + 20 pilot + 93 remaining WixQA
    state = c.read(args.private / args.series / "state.json")
    assert arm.summary(state, "wixqa")["whole"]
    assert c.read(args.records / "arm-wixqa.json")["whole"]
    assert state["postpilot_seconds"] == 93 * elapsed
    assert arm.run(args, client=client, clock=lambda: 0)[0] == 0
    assert client.calls == 114


def test_recover_cleanup_survivor_is_journaled(modules, local_tmp, monkeypatch):
    c, route = modules["common"], modules["route"]
    data = collection_fixture(modules, local_tmp)
    tree = process_snapshot(data.folder / "cwd")[:3]

    def fail(*_):
        raise route.CleanupFailed(tree, stopped=2, exited=1)

    monkeypatch.setattr(route, "cleanup", fail)
    result = data.client.recover(data.folder)
    assert result["kind"] == "infrastructure" and result["cleanup_failed"]
    assert result["cleanup_tree"] == tree and result["timeout"] is False
    assert result["processes_stopped"] == 2 and result["processes_exited"] == 1
    assert c.read(data.folder / "outcome.json") == result


def test_cleanup_tracks_orphan_and_new_descendants(modules):
    route = modules["route"]
    tracked = process_snapshot("unique/cwd")[:3]
    orphan = {**tracked[2], "parent": 1}
    child = {**orphan, "pid": 20, "parent": 12, "created": 1050, "command": "new worker"}
    kernel = FakeKernel({12: 1041, 20: 1058})
    snapshots = iter(([orphan, child], []))
    assert route.cleanup(
        "unique/cwd", snapshot=lambda: next(snapshots), kernel=kernel, tracked=tracked
    ) == {"processes_stopped": 2, "processes_exited": 0}
    assert kernel.stopped == [20, 12]

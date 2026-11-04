"""Synthetic contracts; execute on the session's Mac, never the measurement host."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reports/codex-only-quality/tools"))
import quality_driver as driver  # noqa: E402
import quality_freeze as frozen  # noqa: E402

cv = driver.cv


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else cv.encoded(value))
    return path


def inputs(tmp_path):
    return {
        "schema_version": 1,
        "private_data_root": str(tmp_path / "data"),
        "bases": {k: {"inventory": str(tmp_path / (k + ".json"))} for k in cv.KEYS},
        "private_inputs": {
            k: {"root": str(tmp_path / k), "inventory": str(tmp_path / (k + ".json"))}
            for k in cv.PRIVATE_INPUTS
        },
    }


def test_identical_tree_inventory_alias_only(tmp_path):
    config = inputs(tmp_path)
    trees = config["private_inputs"]
    trees["attempt02_journals"] = dict(trees["attempt02_runs"])
    assert cv.input_trees(config)["attempt02_runs"] == cv.input_trees(config)["attempt02_journals"]
    trees["attempt02_journals"]["inventory"] = str(tmp_path / "different.json")
    with pytest.raises(cv.Refusal, match="overlap"):
        cv.input_trees(config)
    trees["attempt02_journals"]["root"] += "/nested"
    with pytest.raises(cv.Refusal, match="overlap"):
        cv.input_trees(config)


def test_references_are_required_and_inventoried(tmp_path):
    config = inputs(tmp_path)
    assert "stage5_references" in cv.input_trees(config)
    del config["private_inputs"]["stage5_references"]
    with pytest.raises(cv.Refusal, match="inventories missing"):
        cv.input_trees(config)


def test_missing_start_of_retained_infrastructure_does_not_mask_terminal_capture(tmp_path):
    put(tmp_path / "calls/failed/stdin.bin", b"synthetic incomplete capture")
    state = {
        "cases": {
            "wixqa:synthetic": {
                "attempts": [
                    {
                        "id": "old",
                        "classification": "infrastructure",
                        "calls": [{"folder": "failed"}],
                    }
                ]
            }
        }
    }
    assert frozen.capture_bindings(tmp_path, state, "s") == {"old": {"failed"}}
    state["cases"]["wixqa:synthetic"]["attempts"][0]["classification"] = "accepted"
    with pytest.raises(cv.Refusal, match="capture"):
        frozen.capture_bindings(tmp_path, state, "s")
    state["cases"] = {}
    with pytest.raises(cv.Refusal, match="capture"):
        frozen.capture_bindings(tmp_path, state, "s")


@pytest.mark.parametrize("change", ["pending", "rule", "infra", "pilot", "live"])
def test_whole_gate_refuses(change, tmp_path):
    package = [{"case_id": str(i)} for i in range(100)]
    state = {
        "pilot_passed": True,
        "pilot_step": 20,
        "stops": [],
        "cases": {
            "wixqa:" + r["case_id"]: {"key": "wixqa", **r, "status": "accepted"} for r in package
        },
    }
    if change == "pending":
        state["cases"]["wixqa:0"]["status"] = "pending"
    if change in {"rule", "infra"}:
        state["stops"] = [{"code": 2 if change == "rule" else 5}]
    if change == "pilot":
        state["pilot_step"] = 5
    put(
        tmp_path / "stand.json",
        {
            "key": "wixqa",
            "processes": [{"pid": 1, "created": 2, "parent": 0, "image": "python", "command": ""}],
        },
    )
    with pytest.raises(cv.Refusal):
        frozen.whole("wixqa", state, package, tmp_path, alive=lambda p: change == "live")


def prompt(question="Synthetic question?", documents=True):
    from agent.prompts import build_qa_prompt

    return (
        build_qa_prompt(
            question,
            [{"page_content": "Synthetic fact.", "metadata": {"source": "synthetic"}}]
            if documents
            else [],
        )
        .strip()
        .encode()
    )


@pytest.mark.parametrize("status", ["accepted", "product_failure", "counted_out"])
def test_captured_bytes_and_timeout_answer(tmp_path, status):
    raw = prompt()
    stdin = (ROOT / "llm/codex_wrapper.txt").read_bytes().replace(b"{prompt}", b"USER:\n" + raw)
    put(tmp_path / "calls/one/stdin.bin", stdin)
    attempt = {
        "classification": status,
        "calls": [{"effort": "xhigh", "folder": "one", "stdin_sha256": cv.digest(stdin)}],
        "answer_prompt_sha256": cv.digest(raw),
        "result": {"answer": "Synthetic reply.", "route": "human"},
    }
    actual, derived = frozen.prompt_bytes(attempt, "Synthetic question?", tmp_path, ROOT)
    assert actual == raw and derived is False
    target = tmp_path / "run"
    put(target / "launch.json", {})
    put(target / "prompts/one-stream.txt", actual)
    put(target / "cases/one.json", frozen.case_value("one", "Synthetic question?", attempt))
    judge = frozen.modules(ROOT)[0].judge()
    row = judge.run_answers(target)[0]
    assert row["case_id"] == "one" and row["question"] == "Synthetic question?"
    assert row["documents"] == judge.read_prompt(raw.decode())[1]
    assert row["route"] == "human"
    assert row["answer"] == ("Synthetic reply." if status == "accepted" else "")
    (tmp_path / "calls/one/stdin.bin").unlink()
    with pytest.raises((cv.Refusal, OSError)):
        frozen.prompt_bytes(attempt, "Synthetic question?", tmp_path, ROOT)


def test_audited_absence_is_derived_empty_frame(tmp_path):
    attempt = {
        "classification": "accepted",
        "calls": [],
        "audited_absence": True,
        "early_handover": "synthetic",
        "result": {"route": "human"},
    }
    raw, derived = frozen.prompt_bytes(attempt, "Synthetic question?", tmp_path, ROOT)
    assert derived
    assert frozen.modules(ROOT)[0].judge().read_prompt(raw.decode()) == ("Synthetic question?", [])
    attempt["audited_absence"] = False
    with pytest.raises(cv.Refusal):
        frozen.prompt_bytes(attempt, "Synthetic question?", tmp_path, ROOT)


def test_all_package_filenames_and_product_answers_survive_adaptation(tmp_path):
    source, capture, target = tmp_path / "package", tmp_path / "capture", tmp_path / "arm"
    attempts = {}
    wrapper = (ROOT / "llm/codex_wrapper.txt").read_bytes()
    for number in range(100):
        cid, question = f"synthetic-{number:03}", f"Synthetic question {number}?"
        run = source / f"final-answers-wixqa-b{number // 10 + 1:02}"
        put(run / "launch.json", {"tenant": "ext_wixqa"})
        put(run / "prompts" / (cid + "-stream.txt"), prompt(question))
        put(
            run / "cases" / (cid + ".json"),
            {
                "case_id": cid,
                "question": question,
                "answer": "PACKAGE ONLY",
                "events": [{"type": "result", "answer": "PACKAGE ONLY", "route": "auto"}],
            },
        )
        raw = prompt(question, documents=number != 2)
        stdin = wrapper.replace(b"{prompt}", b"USER:\n" + raw)
        if number != 1:
            put(capture / "calls" / cid / "stdin.bin", stdin)
        attempts[cid] = {
            "id": cid,
            "classification": "product_failure" if number == 0 else "accepted",
            "calls": [{"effort": "xhigh", "folder": cid, "stdin_sha256": cv.digest(stdin)}],
            "answer_prompt_sha256": cv.digest(raw),
            "result": {"answer": "PRODUCT ONLY", "route": "human"},
        }
    attempts["synthetic-001"].update(calls=[], audited_absence=True, early_handover="synthetic")
    paths, measurement = frozen.copy_runs(
        "wixqa", source, target, attempts, {"capture_root": str(capture)}, ROOT
    )
    assert len(paths) == 10 and len(measurement) == 100
    judge = frozen.modules(ROOT)[0].judge()
    for label, run in paths.items():
        assert (run / "launch.json").read_bytes() == (source / label / "launch.json").read_bytes()
        assert sorted(p.name for p in (run / "cases").iterdir()) == sorted(
            p.name for p in (source / label / "cases").iterdir()
        )
        for row in judge.run_answers(run):
            cid = row["case_id"]
            assert row["route"] == "human" and row["question"].startswith("Synthetic question ")
            assert row["answer"] == ("" if cid == "synthetic-000" else "PRODUCT ONLY")
            if cid == "synthetic-001":
                assert measurement[cid]["derived"] and row["documents"] == []
                assert measurement[cid]["captured_prompt_sha256"] is None
            else:
                stdin = (capture / "calls" / cid / "stdin.bin").read_bytes()
                journal = driver.canonical_import(
                    ROOT, "capture_journal", "reports/codex-only-quality/tools"
                )
                assert (run / "prompts" / row["prompt_file"]).read_bytes() == journal.unwrap(
                    stdin
                ).encode()
                assert measurement[cid]["derived"] is False
    assert measurement["synthetic-000"]["class"] == "product_failure"


def test_frozen_state_cannot_become_pending_or_change_attempt():
    measured = {str(i): {"class": "accepted", "attempt_id": str(i)} for i in range(100)}
    rows = {
        "wixqa:" + cid: {
            "key": "wixqa",
            "case_id": cid,
            "status": "accepted",
            "attempts": [{"id": cid}],
        }
        for cid in measured
    }
    state = {"pilot_passed": True, "pilot_step": 20, "cases": rows}
    for cid, entry in measured.items():
        entry["state_sha256"] = cv.digest(cv.encoded(rows["wixqa:" + cid]))
    frozen.bind_state("wixqa", state, measured)
    rows["wixqa:0"]["status"] = "pending"
    with pytest.raises(cv.Refusal, match="frozen case"):
        frozen.bind_state("wixqa", state, measured)
    rows["wixqa:0"]["status"] = "accepted"
    rows["wixqa:0"]["attempts"][-1]["tickets"] = {"count": 999}
    with pytest.raises(cv.Refusal, match="frozen case"):
        frozen.bind_state("wixqa", state, measured)
    del rows["wixqa:0"]["attempts"][-1]["tickets"]
    rows["wixqa:0"]["attempts"][-1]["id"] = "different"
    with pytest.raises(cv.Refusal, match="frozen case"):
        frozen.bind_state("wixqa", state, measured)


def test_partial_recovers_only_published_matching_receipt(tmp_path):
    work, receipt = tmp_path / "wixqa", tmp_path / "public/plans-wixqa.json"
    partial = work.with_name("wixqa.partial")
    put(partial / "receipt.json", {"key": "wixqa"})
    with pytest.raises(cv.Refusal, match="partial"):
        frozen.recover_partial(work, receipt, lambda folder, pin: None)
    put(receipt, {"key": "wixqa"})
    seen = []
    assert frozen.recover_partial(work, receipt, lambda folder, pin: seen.append(folder))
    assert seen == [partial] and work.exists() and not partial.exists()


def test_partial_validation_failure_preserves_staging(tmp_path):
    work, receipt = tmp_path / "wixqa", tmp_path / "public/plans-wixqa.json"
    put(tmp_path / "wixqa.partial/receipt.json", {})
    put(receipt, {})

    def refuse(folder, pin):
        raise cv.Refusal("changed frozen bytes")

    with pytest.raises(cv.Refusal, match="changed"):
        frozen.recover_partial(work, receipt, refuse)
    assert (tmp_path / "wixqa.partial").exists() and not work.exists()


@pytest.fixture
def grading(tmp_path, monkeypatch):
    c, historical = frozen.modules(ROOT)
    args = SimpleNamespace(
        private=tmp_path / "private",
        records=tmp_path / "public",
        series="synthetic",
        key="wixqa",
        budget=600,
    )
    series = args.private / args.series
    registration = {"files": {}}
    measured = {str(i): {"class": "accepted", "attempt_id": str(i)} for i in range(100)}
    put(
        series / "state.json",
        {
            "stops": [],
            "registration_sha256": cv.digest(cv.encoded(registration)),
            "pilot_passed": True,
            "pilot_step": 20,
            "cases": {
                "wixqa:" + cid: {
                    "key": "wixqa",
                    "case_id": cid,
                    "status": "accepted",
                    "attempts": [{"id": cid}],
                }
                for cid in measured
            },
        },
    )
    state = cv.read(series / "state.json")
    for cid, entry in measured.items():
        entry["state_sha256"] = cv.digest(cv.encoded(state["cases"]["wixqa:" + cid]))
    put(series / args.key / "measurement.json", measured)
    run = tmp_path / "run"
    put(run / "launch.json", {"tenant": "ext_wixqa"})
    for number in range(15):
        question = f"Synthetic question {number}?"
        put(run / "prompts" / f"{number:02}-stream.txt", prompt(question))
        put(
            run / "cases" / f"{number:02}.json",
            {
                "case_id": str(number),
                "question": question,
                "answer": "Synthetic reply [1].",
                "events": [{"type": "result", "answer": "Synthetic reply [1].", "route": "auto"}],
            },
        )
    plan = c.judge().build_plan({"synthetic": run}, {}, retest=15)
    for metric in frozen.METRICS:
        put(series / args.key / metric / "plan.json", plan)
        put(series / args.key / metric / "verdicts.jsonl", b"")
    pin = {"requests": {m: 30 for m in frozen.METRICS}}
    monkeypatch.setattr(frozen, "admitted", lambda *a: ({}, registration, pin))
    monkeypatch.setattr(frozen, "judge_route", lambda *a, **kw: True)
    monkeypatch.setattr(frozen, "exports", lambda *a: ({"status": "counted", "missing": []}, []))
    return SimpleNamespace(
        args=args,
        c=c,
        series=series,
        folder=series / args.key / "m1",
        pin=pin,
        historical=historical,
    )


def reply(c, text=None):
    judge = c.judge()
    session = {
        "cli_version": "9.9.9",
        "model": judge.isolated.MODEL,
        "loaded": {k: [] for k in judge.isolated.LOADED},
        "builtin": {"plugins": [], "agents": []},
        "turns": 1,
        "context_tokens": 100,
    }
    value = {
        "claims_total": 1,
        "claims_supported": 1,
        "context_has_answer": True,
        "answers_question": "full",
        "citations_supported": 1,
        "reference": "none",
        "defect": "none",
        "note": "synthetic",
    }
    return judge.isolated.IsolatedReply(
        text or json.dumps(value), judge.isolated.MODEL, {}, 1.0, session
    )


def test_grade_retry_persists_and_seven_unavailable_stop(grading):
    calls = []

    def unavailable(*args):
        calls.append(args)
        raise grading.c.judge().JudgeUnavailable("synthetic", "synthetic outage")

    for index in range(7):
        wall = 1000 + index * 301
        code, _ = frozen.grade(grading.args, sender=unavailable, clock=lambda: 0, now=lambda: wall)
        assert code == (5 if index == 6 else 3)
        assert cv.read(grading.folder / "retry.json")["retry_at"] == wall + 300
        assert len(calls) == index + 1
        frozen.grade(grading.args, sender=unavailable, clock=lambda: 0, now=lambda: wall)
        assert len(calls) == index + 1


def test_grade_budget_no_request(grading):
    ticks = iter([0, 600])
    code, _ = frozen.grade(
        grading.args,
        sender=lambda *a: pytest.fail("request after budget"),
        clock=lambda: next(ticks),
    )
    assert code == 3


def test_unstable_m1_stops_before_bridge(grading, monkeypatch):
    monkeypatch.setattr(
        frozen, "exports", lambda *a: ({"status": "NOT_EVIDENCE", "missing": []}, [])
    )
    code, _ = frozen.grade(grading.args, sender=lambda *a: reply(grading.c), clock=lambda: 0)
    assert code == 2
    assert cv.read(grading.folder / "NOT_EVIDENCE.json")["status"] == "NOT_EVIDENCE"
    assert (grading.series / grading.args.key / "bridge/verdicts.jsonl").read_bytes() == b""


def test_grade_request_clock_stop(grading):
    put(
        grading.folder / "grade-clock.json", {"forecast": 30 * 130, "request_seconds": 3 * 30 * 130}
    )
    code, _ = frozen.grade(
        grading.args, sender=lambda *a: pytest.fail("request after clock stop"), clock=lambda: 0
    )
    assert code == 2 and (grading.folder / "NOT_EVIDENCE.json").exists()


def test_route_refusal_grades_nothing(grading, monkeypatch):
    monkeypatch.setattr(frozen, "judge_route", lambda *a, **kw: False)
    code, _ = frozen.grade(
        grading.args, sender=lambda *a: pytest.fail("request after route refusal"), clock=lambda: 0
    )
    assert code == 5
    assert (grading.folder / "verdicts.jsonl").read_bytes() == b""


def test_instructions_mismatch_before_probe_or_grade(grading, monkeypatch):
    monkeypatch.setattr(grading.c.judge(), "INSTRUCTIONS", "changed")
    monkeypatch.setattr(
        frozen, "judge_route", lambda *a, **kw: pytest.fail("probe after bad instructions")
    )
    with pytest.raises(cv.Refusal, match="instructions"):
        frozen.grade(grading.args, sender=lambda *a: pytest.fail("request"))


def test_real_route_validator_records_executable_and_version(tmp_path, monkeypatch):
    c, _ = frozen.modules(ROOT)
    executable = put(tmp_path / "claude", b"synthetic executable; never executed")
    config = {"artifacts": {"claude_executable": str(executable)}}
    monkeypatch.setenv("RAG_JUDGE_CLAUDE_CLI", str(executable))
    assert frozen.judge_route(
        config, tmp_path / "series", tmp_path / "public", ROOT, sender=lambda *a: reply(c)
    )
    held = cv.read(tmp_path / "series/judge-route.json")
    assert held["version"] == "9.9.9" and held["executable_sha256"] == cv.sha(executable)
    public = (tmp_path / "public/judge-route.json").read_text()
    assert str(executable) not in public and "9.9.9" not in public


def test_refused_route_is_retained_without_reprobing(tmp_path, monkeypatch):
    c, _ = frozen.modules(ROOT)
    executable = put(tmp_path / "claude", b"synthetic; never executed")
    config = {"artifacts": {"claude_executable": str(executable)}}
    monkeypatch.setenv("RAG_JUDGE_CLAUDE_CLI", str(executable))
    assert not frozen.judge_route(
        config,
        tmp_path / "series",
        tmp_path / "public",
        ROOT,
        sender=lambda *a: reply(c, "not a verdict"),
    )
    held = cv.read(tmp_path / "series/judge-route.json")
    assert held["version"] == "9.9.9" and held["passed"] is False
    assert not frozen.judge_route(
        config,
        tmp_path / "series",
        tmp_path / "public",
        ROOT,
        sender=lambda *a: pytest.fail("refused route must not silently retry"),
    )


def test_public_export_hashes_private_paths_and_refuses_prose():
    _, historical = frozen.modules(ROOT)
    record = {
        "provenance": {
            "reading": {"text": "synthetic private reading"},
            "runs": {"a": {"chroma_dir": "/private/index", "cases_file": "/private/cases"}},
        }
    }
    exported = historical.public_export(record)
    text = json.dumps(exported)
    assert "synthetic private reading" not in text and "/private" not in text
    with pytest.raises(ValueError):
        historical.public_export({"answer": "private answer"})


def test_export_names_and_guard(tmp_path, monkeypatch):
    args = SimpleNamespace(
        private=tmp_path / "private", records=tmp_path / "public", series="s", key="wixqa"
    )
    monkeypatch.setattr(frozen, "admitted", lambda *a: ({}, {}, {}))
    monkeypatch.setattr(
        frozen,
        "exports",
        lambda key, series, pin, metric, repo: (
            {"status": "counted"},
            [{"case_id": "synthetic", "grade": "good"}] if metric == "m1" else None,
        ),
    )
    frozen.export(args)
    assert sorted(p.name for p in (args.records / args.series).iterdir()) == [
        "codex-only-wixqa-judge-bridge.json",
        "codex-only-wixqa-judge-m1.cases.jsonl",
        "codex-only-wixqa-judge-m1.json",
    ]
    monkeypatch.setattr(frozen, "exports", lambda *a: ({"answer": "private prose"}, None))
    with pytest.raises(ValueError):
        frozen.export(args)

"""Stage 5 registration: synthetic archives only; no server, model or judge requests."""

import copy
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports/stage4-final/tools"
EXTERNAL = TOOLS / "external"


def load(path, name, monkeypatch):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tools(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(TOOLS))
    monkeypatch.syspath_prepend(str(EXTERNAL))
    modules = {}
    for name in ("common", "stand", "record", "run", "judge"):
        modules[name] = load(TOOLS / f"{name}.py", name, monkeypatch)
    for name in ("protocol", "sent_gold", "prepare", "execute", "grading", "reading"):
        modules[name] = load(EXTERNAL / f"{name}.py", name, monkeypatch)
    modules["helpers"] = load(
        ROOT / "tests/test_stage4_final_tools.py", "s5_fixture_helpers", monkeypatch
    )
    # The Mac's pytest basetemp is inside its checkout. Give the privacy guard a synthetic
    # checkout beside this fixture's private folders; the boundary itself is tested below.
    monkeypatch.setattr(modules["protocol"], "ROOT", tmp_path / "checkout")
    return SimpleNamespace(**modules)


def journal(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(v) + "\n" for v in values), "utf-8", newline="\n")


def answers_table(grade="good"):
    return {
        f"q{i:03}": {
            "case_id": f"q{i:03}",
            "grade": grade,
            "cluster": i // 2,
            "stratum": "answerable",
            "context_has_answer": True,
        }
        for i in range(100)
    }


def gold_table(n=100, hits=40):
    return {
        f"q{i:03}": {
            "case_id": f"q{i:03}",
            "gold": i < n,
            "hit": int(i < hits) if i < n else None,
            "fraction": float(i < hits) if i < n else None,
        }
        for i in range(100)
    }


@pytest.mark.parametrize(
    "tail,expected",
    [
        ((301.1, 470.6, 796.0), (330, 480, 3570, 35700)),
        ((249.3, 339.3, 397.6), (270, 360, 2910, 29100)),
        ((275.0, 341.3, 418.4), (300, 360, 3180, 31800)),
        ((60, 90, 2000), (60, 360, 1020, 10200)),
    ],
)
def test_forecast_is_computed_from_the_records_not_published_literals(tools, tail, expected):
    value = tools.protocol.forecast(dict(zip(("median", "p90", "max"), tail, strict=True), n=100))
    assert tuple(value[k] for k in ("rest", "first", "batch", "series")) == expected
    assert value["startup"] == 120
    # The observed maximum is printed, not used to censor a later answer at that time.
    assert "question_cap" not in value


@pytest.mark.parametrize(
    "change", [{"n": 99}, {"median": 0}, {"p90": float("nan")}, {"max": 3600}, {"median": 201}]
)
def test_invalid_historical_tail_refuses(tools, change):
    with pytest.raises(SystemExit, match="historical tail"):
        tools.protocol.forecast({"n": 100, "median": 100, "p90": 200, "max": 300, **change})


@pytest.mark.parametrize(
    "nc,cluster,direction",
    [
        ((0.01, 0.2), (0.02, 0.3), "rises"),
        ((-0.3, -0.02), (-0.2, -0.01), "falls"),
        ((0, 0.2), (0.02, 0.3), "not detected"),
        ((0.01, 0.2), (0, 0.3), "not detected"),
        ((-0.3, -0.02), (0.01, 0.2), "not detected"),
        ((0.00001, 0.2), (0.01, 0.3), "not detected"),
    ],
)
def test_pooled_rule_keeps_v4s_both_intervals_and_rounding(
    tools, monkeypatch, nc, cluster, direction
):
    from evaluation import semantic_ruler

    v4 = tools.common.frozen("v4")
    monkeypatch.setattr(v4, "newcombe", lambda *a: nc)
    seen = []

    def summary(values, families):
        seen.append((values, families))
        return {"ci95": cluster, "clusters": len(set(tuple(f) for f in families.values()))}

    monkeypatch.setattr(semantic_ruler, "cluster_summary", summary)
    monkeypatch.setattr(tools.reading, "paired", v4.paired)
    tables = {b: (answers_table(), answers_table("bad")) for b in tools.protocol.BASES}
    result = tools.reading.pooled(tables)
    assert result["bad"]["n"] == 200
    assert result["bad"]["direction"] == direction
    assert result["bad"]["detected"] is (direction != "not detected")
    assert result["bad"]["v3"] == 0 and result["bad"]["v4"] == 1
    assert set(result["keys"]) == {"wixqa", "conditionalqa"}
    assert set(seen[0][1]) == {
        f"{base}:q{i:03}" for base in tools.protocol.PRIMARY for i in range(100)
    }
    assert len({tuple(f) for f in seen[0][1].values()}) == 100  # clusters cannot cross corpora
    decision = tools.reading.outcome(result)
    assert (
        decision["outcome"]
        == {"rises": "harm detected", "falls": "gain detected", "not detected": "holds"}[direction]
    )
    del tables["multihoprag"]
    assert tools.reading.pooled(tables) == result
    del tables["wixqa"]
    assert tools.reading.outcome(tools.reading.pooled(tables))["outcome"] == "NOT_EVIDENCE"


@pytest.mark.parametrize("base,n", [("wixqa", 100), ("conditionalqa", 80), ("multihoprag", 70)])
@pytest.mark.parametrize(
    "direction,expected",
    [("rises", "gain detected"), ("falls", "harm detected"), ("not detected", "holds")],
)
def test_sent_m3_has_no_ceiling_and_reads_both_directions(
    tools, monkeypatch, base, n, direction, expected
):
    calls = []

    def paired(a, b, families):
        calls.append((a, b, families))
        return {"direction": direction}

    monkeypatch.setattr(tools.reading, "paired", paired)
    old, new = gold_table(n), gold_table(n, 30)
    result = tools.reading.m3_read(base, old, new, {i: [i] for i in old})
    assert result["reading"] == expected and result["old_n"] == n
    assert result["old_hits"] == 40 and result["without_gold"] == 100 - n
    assert len(calls[0][0]) == n and result["old_ceiling"] is False
    with pytest.raises(SystemExit, match="ceiling"):
        tools.reading.m3_read(base, gold_table(n, n), new, {i: [i] for i in old})
    new["q000"]["gold"] = False
    with pytest.raises(SystemExit, match="membership"):
        tools.reading.m3_read(base, old, new, {i: [i] for i in old})


def test_multihop_and_judge_context_cannot_change_the_primary_decision(tools, monkeypatch):
    monkeypatch.setattr(tools.reading, "paired", lambda *a: {"direction": "not detected"})
    a, b = answers_table("good"), answers_table("bad")
    b["q000"]["context_has_answer"] = False
    result = tools.reading.compare("multihoprag", a, b, gold_table(70), gold_table(70, 10))
    assert result["advisory"] is True
    assert result["context_has_answer"] == {"same": 99, "lost": 1, "gained": 0}
    assert (
        tools.reading.outcome(tools.reading.pooled({"multihoprag": (a, b)}))["outcome"]
        == "NOT_EVIDENCE"
    )


def test_multihop_m2_is_new_unpaired_even_if_its_bridge_fails(tools, monkeypatch):
    monkeypatch.setattr(
        tools.reading, "frozen", lambda *a: pytest.fail("no comparator for MultiHop M2")
    )
    result = tools.reading.m2_read(
        "multihoprag", {"m2": {"with_reference": {"agrees": 5}}}, {}, None, False
    )
    assert result == {
        "status": "counted",
        "paired": False,
        "advisory": True,
        "new": {"with_reference": {"agrees": 5}},
    }
    with pytest.raises(SystemExit, match="no admitted old side"):
        tools.reading.m2_read("multihoprag", {"m2": {}}, {}, {}, True)
    assert tools.reading.m2_read("wixqa", {"m2": {}}, {}, None, False)["status"] == "NOT_EVIDENCE"


def test_m2_pairs_reference_answers_and_counts_declines_by_the_frozen_reader(tools, monkeypatch):
    calls = []

    def reference(base, a, b, families):
        calls.append((base, a, b, families))
        return {"with_reference": {"pairs": 1}, "without_reference": {"pairs": 1}}

    monkeypatch.setattr(tools.reading, "frozen", lambda *a: SimpleNamespace(reference=reference))
    a = {
        "q": {"cluster": 0, "has_reference": True, "m2": "agrees"},
        "r": {"cluster": 1, "has_reference": False, "m2": "right"},
    }
    b = copy.deepcopy(a)
    result = tools.reading.m2_read("conditionalqa", {"m2": {}}, b, a, True)
    assert result["paired"] is True and len(calls) == 1
    assert calls[0] == ("conditionalqa", a, b, {"q": ["conditionalqa:0"], "r": ["conditionalqa:1"]})
    b["q"]["cluster"] = 2
    with pytest.raises(SystemExit, match="clusters"):
        tools.reading.m2_read("conditionalqa", {"m2": {}}, b, a, True)


@pytest.mark.parametrize("change", ["plan", "source_plan", "source_replies", "status", "stability"])
def test_bridge_failure_invalidates_the_paired_reading(tools, change):
    old = {"provenance": {"plan_sha256": "old-plan", "verdicts_sha256": "old-replies"}}
    bridge = {
        "plan_sha256": "new-plan",
        "source_plan_sha256": "old-plan",
        "source_verdicts_sha256": "old-replies",
        "status": "counted",
        "retest": {"passed": True},
    }
    tools.reading.bridge_gate(bridge, old, "new-plan")
    key = {
        "plan": "plan_sha256",
        "source_plan": "source_plan_sha256",
        "source_replies": "source_verdicts_sha256",
        "status": "status",
        "stability": "retest",
    }[change]
    bridge[key] = {"passed": False} if change == "stability" else "different"
    with pytest.raises(SystemExit, match="bridge"):
        tools.reading.bridge_gate(bridge, old, "new-plan")


@pytest.fixture
def published_judge(tools, tmp_path):
    from evaluation import isolated_request
    from scripts import chat_answer_judge as answer

    path = tmp_path / "v4-wixqa-judge-m1.json"
    ids = list(answers_table())
    provenance = {
        "references_sha256": "refs",
        "references_withheld": True,
        "prompt_id": "QA_PROMPT_V4",
        "plan_sha256": "plan",
        "verdicts_sha256": "replies",
        "route": isolated_request.settings(answer.SYSTEM_PROMPT),
        "salt": answer.SALT,
        "instructions_sha256": answer._digest(answer.INSTRUCTIONS),
        "runs": {"v4-wixqa-b01": {"code_sha": "4f48fed" + "0" * 33, "tenant": "ext_wixqa"}},
    }
    record = {
        "plan": path.stem,
        "status": "counted",
        "judge": "answers",
        "base": "wixqa",
        "provenance": provenance,
        "replies": {},
        "questions": 100,
        "requests_valid": 115,
        "missing": [],
        "per_run": {},
        "shares": {},
        "retest": {"passed": True},
    }
    cases = [
        {**r, "prompt_sha256": "prompt", "has_reference": False} for r in answers_table().values()
    ]
    tools.common.write(path, record)
    journal(path.with_suffix(".cases.jsonl"), cases)
    return path, record, cases, ids


@pytest.mark.parametrize(
    "broken",
    [
        None,
        "status",
        "retest",
        "route",
        "salt",
        "instructions",
        "references",
        "withheld",
        "code",
        "prompt_id",
        "prompt",
        "duplicate",
        "missing",
        "grade",
    ],
)
def test_real_published_judge_schema_and_refusals(tools, published_judge, broken):
    path, record, cases, ids = published_judge
    p = record["provenance"]
    if broken == "status":
        record["status"] = "NOT_EVIDENCE"
    elif broken == "retest":
        record["retest"]["passed"] = False
    elif broken in ("route", "salt", "prompt_id"):
        p[broken] = "changed"
    elif broken == "instructions":
        p["instructions_sha256"] = "changed"
    elif broken == "references":
        p["references_sha256"] = "changed"
    elif broken == "withheld":
        p["references_withheld"] = False
    elif broken == "code":
        p["runs"]["v4-wixqa-b01"]["code_sha"] = "5e308fe"
    elif broken == "prompt":
        cases[0]["prompt_sha256"] = "changed"
    elif broken == "duplicate":
        cases[1] = cases[0]
    elif broken == "missing":
        record["missing"] = [ids[0]]
    elif broken == "grade":
        cases[0]["grade"] = None
    tools.common.write(path, record)
    journal(path.with_suffix(".cases.jsonl"), cases)
    args = (path, "wixqa", "m1", ids, "refs", "4f48fed", {i: "prompt" for i in ids})
    if broken is None:
        got, table = tools.protocol.judge_record(*args)
        assert got == record and len(table) == 100
    else:
        with pytest.raises(SystemExit, match="NOT_EVIDENCE|duplicate"):
            tools.protocol.judge_record(*args)


def test_committed_input_and_private_boundary(tools, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(tools.protocol, "ROOT", repo)
    path = repo / "old.json"
    path.write_bytes(b"{}\n")
    calls = []
    monkeypatch.setattr(
        tools.protocol.subprocess, "check_output", lambda args, **kw: calls.append(args) or b"{}\n"
    )
    assert tools.protocol.committed(path) == tools.common.sha(path)
    assert calls == [["git", "show", "HEAD:old.json"]]
    path.write_bytes(b"{ }\n")
    with pytest.raises(SystemExit, match="committed unchanged"):
        tools.protocol.committed(path)
    with pytest.raises(SystemExit, match="outside"):
        tools.protocol.outside(repo / "private")
    assert tools.protocol.outside(tmp_path / "private") == tmp_path / "private"


@pytest.fixture
def series(tools, tmp_path, monkeypatch):
    data, out, repo = tmp_path / "data", tmp_path / "runs", tmp_path / "stand"
    repo.mkdir()
    baseline = repo / "baseline.json"
    held = {
        "spec": tools.protocol.SPEC,
        "status": "counted",
        "order": list(tools.protocol.BASES),
        "item6_sha": "e" * 40,
        "bases": {},
    }
    ids = list(answers_table())
    for base in tools.protocol.BASES:
        file = data / base / "cases.jsonl"
        journal(file, [{"case_id": i, "query": f"Synthetic {i}?"} for i in ids])
        times = {"n": 100, "median": 101, "p90": 220, "max": 300}
        held["bases"][base] = {
            "ids": ids,
            "cases_sha256": tools.common.sha(file),
            "corpus": {"receipt": "digest"},
            "times": {"total_sec": times},
            "forecast": tools.protocol.forecast(times),
        }
    tools.common.write(baseline, held)
    tools.common.write(
        repo / "STAND_FILES.json", {"files": {"baseline.json": tools.common.sha(baseline)}}
    )
    monkeypatch.setattr(tools.execute, "ROOT", repo)
    monkeypatch.setattr(tools.execute, "code_check", lambda: "f" * 40)
    monkeypatch.setattr(tools.execute, "corpus", lambda *a: {"receipt": "digest"})
    monkeypatch.setattr(tools.execute, "questions", lambda b, d: (d / b / "cases.jsonl", ids))
    monkeypatch.setattr(tools.execute.time, "monotonic", lambda: 0)
    monkeypatch.setattr(
        tools.execute,
        "product_diff",
        lambda source, a, b: {
            "item6_sha": a,
            "stage5_sha": b,
            "changed_paths": ["docs/specs/stage5-final-external.md"],
        },
    )
    monkeypatch.setattr(tools.execute, "answers", lambda *a: {"provenance": {"code_sha": "f" * 40}})
    return data, out, baseline, held, ids


def test_thirty_batches_delegate_to_item6_in_registered_order_and_keep_busy(
    tools, series, monkeypatch
):
    data, out, baseline, held, ids = series
    calls = []
    monkeypatch.setattr(
        tools.execute, "wait_idle", lambda *a: {"busy": True, "reasons": ["foreign"]}
    )

    def batch(path, base, cases, selected, data_arg, deadline, speed, before):
        calls.append((base, selected, deadline))
        assert data_arg == data and cases == data / base / "cases.jsonl"
        assert before["busy"] and speed is False
        assert deadline == 3 * held["bases"][base]["forecast"]["batch"]
        tools.common.write(path / "launch.json", {"base": base})

    monkeypatch.setattr(tools.execute, "batch", batch)
    tools.execute.run_series(data, out, baseline, baseline.parent, "e" * 40)
    assert calls == [
        (b, ids[n * 10 : (n + 1) * 10], 3 * held["bases"][b]["forecast"]["batch"])
        for b in tools.protocol.BASES
        for n in range(10)
    ]
    result = tools.common.read(out / "series.json")
    assert result["status"] == "complete" and len(result["completed"]) == 30
    assert tools.execute.batch is batch
    for base in tools.protocol.BASES:
        marker = tools.common.read(out / f"{base}.complete")
        assert marker["base"] == base and len(marker["batch_sha256"]) == 10
        assert marker["product_diff"]["item6_sha"] == "e" * 40
        assert marker["batch_sha256"] == tools.protocol.batch_hashes(out, base)
    with pytest.raises(SystemExit, match="new OUT"):
        tools.execute.run_series(data, out, baseline, baseline.parent, "e" * 40)


@pytest.mark.parametrize(
    "broken", ["manifest", "ids", "corpus", "forecast", "deadline", "operator"]
)
def test_series_refuses_changed_inputs_and_never_counts_a_failed_batch(
    tools, series, monkeypatch, broken
):
    data, out, baseline, held, _ = series
    calls = []
    if broken in ("ids", "corpus", "forecast"):
        key = broken
        held["bases"]["wixqa"][key] = [] if key == "ids" else {}
        tools.common.write(baseline, held)
        tools.common.write(
            baseline.parent / "STAND_FILES.json",
            {"files": {"baseline.json": tools.common.sha(baseline)}},
        )
    elif broken == "manifest":
        tools.common.write(baseline, {**held, "extra": True})

    def wait(*args):
        if broken == "operator":
            (out / "STOP").touch()
        return {"busy": False}

    def batch(*args, **kwargs):
        calls.append(args)

    monkeypatch.setattr(tools.execute, "batch", batch)
    monkeypatch.setattr(tools.execute, "wait_idle", wait)
    if broken == "deadline":
        ticks = iter([0, 0])
        monkeypatch.setattr(tools.execute.time, "monotonic", lambda: next(ticks, 10**9))
    with pytest.raises(SystemExit):
        tools.execute.run_series(data, out, baseline, baseline.parent, "e" * 40)
    if broken in ("deadline", "operator"):
        assert tools.common.read(out / "series.json")["status"] == "NOT_EVIDENCE"
        assert calls == []
    else:
        assert not out.exists() and calls == []


def test_private_hashes_bind_measurements_but_never_visit_the_index(tools, tmp_path):
    run = tmp_path / "runs" / "b01"
    tools.common.write(run / "launch.json", {})
    tools.common.write(run / "cases" / "q.json", {"answer": "private"})
    tools.common.write(run / "chroma" / "index.json", {"text": "must not be visited"})
    first = tools.protocol.private_hashes(run.parent)
    assert set(first) == {"b01/launch.json", "b01/cases/q.json"}
    tools.common.write(run / "cases" / "q.json", {"answer": "changed"})
    assert tools.protocol.private_hashes(run.parent) != first
    tools.common.write(run.parent / "series.json", {"status": "complete"})
    assert tools.protocol.private_hashes(run.parent)["series.json"] == tools.common.sha(
        run.parent / "series.json"
    )


@pytest.fixture(params=["._launch.json", "b01/prompts/._001-stream.txt", "unexpected/deep/._x"])
def appledouble_runs(tmp_path, request):
    runs = tmp_path / "runs"
    first = runs / request.param
    for path in (first, runs / "zz-last/._second"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x00\xffAppleDouble")
    (runs / "ordinary.txt").write_bytes(b"ordinary UTF-8 file\n")
    return runs, first


@pytest.mark.parametrize(
    "entry", ["plan", "export", "reading", "hashes", "batch_hashes", "m3", "historical_m3", "p2_m3"]
)
def test_extracted_runs_refuse_the_first_appledouble_path_without_changes(
    tools, tmp_path, monkeypatch, appledouble_runs, entry
):
    runs, first = appledouble_runs
    before = {p.relative_to(runs): p.read_bytes() for p in runs.rglob("*") if p.is_file()}
    private, data = tmp_path / "private", tmp_path / "data"
    baseline, receipt = tmp_path / "baseline.json", tmp_path / "receipt.json"
    config = {"data": str(data), "stage2": {"run": str(tmp_path / "old-p2")}, "bases": {}}
    for module in (tools.grading, tools.reading):
        monkeypatch.setattr(
            module,
            "check_receipt",
            lambda *a: pytest.fail("archive must be checked before baseline"),
        )
    with pytest.raises(SystemExit) as error:
        if entry == "plan":
            tools.grading.freeze(config, private, runs, baseline, receipt, "wixqa")
        elif entry == "export":
            tools.grading.export_one(
                "wixqa", "m1", private, runs, {"base": "wixqa"}, tmp_path / "out"
            )
        elif entry == "reading":
            tools.reading.build(
                config, private, runs, baseline, tmp_path, tmp_path, tmp_path, "f" * 40
            )
        elif entry == "hashes":
            tools.protocol.private_hashes(runs)
        elif entry == "batch_hashes":
            tools.protocol.batch_hashes(runs, "wixqa")
        elif entry == "p2_m3":
            tools.sent_gold.stage2_gate(data, runs, tmp_path / "p2.json", baseline, [])
        else:
            tools.sent_gold.measure("wixqa", data, runs, [], historical=entry == "historical_m3")
    assert str(error.value) == f"NOT_EVIDENCE: AppleDouble file in runs archive: {first.as_posix()}"
    assert {p.relative_to(runs): p.read_bytes() for p in runs.rglob("*") if p.is_file()} == before
    assert not private.exists() and not receipt.exists() and not (tmp_path / "out").exists()


def test_public_record_refuses_questions_and_document_names(tools, tmp_path, monkeypatch):
    tools.common.frozen("cases")
    import stage2_common

    monkeypatch.setattr(stage2_common, "source_names", lambda *a: ({}, {"private-source.md"}))
    file = tmp_path / "cases.jsonl"
    journal(file, [{"case_id": "q", "query": "Private question?"}])
    monkeypatch.setattr(tools.protocol, "questions", lambda *a: (file, ["q"]))
    out = tmp_path / "public.json"
    for value in ("private-source.md", "prefix Private question? suffix"):
        with pytest.raises(SystemExit, match="text of the base"):
            tools.protocol.public_write(out, {"forbidden": value}, tmp_path)
        assert not out.exists()
    tools.protocol.public_write(out, {"case_id": "q", "hit": 1}, tmp_path)
    assert tools.common.read(out) == {"case_id": "q", "hit": 1}


@pytest.mark.parametrize("empty_text", [None, "", " \n\t"])
def test_each_base_freezes_its_three_plans_before_its_own_first_grade(
    tools, tmp_path, monkeypatch, empty_text
):
    from scripts import chat_answer_judge as answer

    private, runs = tmp_path / "private", tmp_path / "runs"
    baseline = tmp_path / "baseline.json"
    tools.common.write(baseline, {"status": "counted"})
    ids = list(answers_table())
    measured, config, old = (
        {},
        {"data": str(tmp_path / "data"), "stage2": {"run": str(tmp_path / "p2")}, "bases": {}},
        {"bases": {}, "item6_sha": "e" * 40},
    )
    for base in tools.protocol.BASES:
        paths = {}
        for n in range(10):
            path = runs / f"final-answers-{base}-b{n + 1:02d}"
            tools.helpers.make_run(tools, path, ids[n * 10 : (n + 1) * 10])
            launch = tools.common.read(path / "launch.json")
            launch["tenant"] = "ext_" + base
            tools.common.write(path / "launch.json", launch)
            paths[path.name] = path
        refs = tmp_path / "history" / "references" / f"{base}.jsonl"
        journal(
            refs,
            [
                {
                    "case_id": i,
                    "reference_answers": ["Synthetic reference."],
                    "cluster": j,
                    "stratum": "answerable",
                }
                for j, i in enumerate(ids)
            ],
        )
        plan = answer.build_plan(
            paths, {}, retest=15, references_sha256=tools.common.sha(refs), withheld=True
        )
        plan["prompt_id"] = "QA_PROMPT_V3" if base == "multihoprag" else "QA_PROMPT_V4"
        for r in plan["runs"].values():
            r["code_sha"] = tools.protocol.OLD[base] + "0" * 33
        source = tmp_path / "history" / "judge" / base
        tools.common.write(source / "plan.json", plan)
        journal(source / "verdicts.jsonl", [tools.helpers.verdict_reply(i) for i in plan["items"]])
        config["bases"][base] = {
            "source": str(source),
            "references": str(refs),
            "runs": str(tmp_path / "history/runs"),
            "plans": {"m1": str(source)},
        }
        old["bases"][base] = {
            "bridge_source": {
                "plan": tools.common.sha(source / "plan.json"),
                "verdicts": tools.common.sha(source / "verdicts.jsonl"),
            },
            "references_sha256": tools.common.sha(refs),
        }
        measured[base] = {
            "runs": list(paths),
            "provenance": {"code_sha": "f" * 40},
            "stand": {"same": True},
        }
    for base in tools.protocol.BASES:
        tools.common.write(
            runs / f"{base}.complete",
            {
                "status": "complete",
                "base": base,
                "code_sha": "f" * 40,
                "baseline_sha256": tools.common.sha(baseline),
                "product_diff": {
                    "item6_sha": "e" * 40,
                    "stage5_sha": "f" * 40,
                    "changed_paths": [],
                },
                "batch_sha256": tools.protocol.batch_hashes(runs, base),
            },
        )
    if empty_text is not None:
        # Historical bridge replies remain unchanged; only the new WixQA answer is empty.
        folder = runs / "final-answers-wixqa-b01"
        path = next((folder / "cases").glob("*.json"))
        raw = tools.common.read(path)
        raw["answer"] = empty_text
        for event in raw.get("events", []):
            if event.get("type") == "result":
                event["answer"] = empty_text
        tools.common.write(path, raw)
        complete = tools.common.read(runs / "wixqa.complete")
        complete["batch_sha256"] = tools.protocol.batch_hashes(runs, "wixqa")
        tools.common.write(runs / "wixqa.complete", complete)
    monkeypatch.setattr(tools.grading, "check_receipt", lambda *a: old)
    monkeypatch.setattr(tools.grading, "answers", lambda r, b, d: measured[b])
    monkeypatch.setattr(tools.grading, "public_write", lambda p, v, d: tools.common.write(p, v))
    monkeypatch.setattr(
        answer, "_isolated_sender", lambda *a: pytest.fail("freeze cannot send requests")
    )
    history = tmp_path / "history"
    before = {p.relative_to(history): p.read_bytes() for p in history.rglob("*") if p.is_file()}
    pins = {}
    for base in tools.protocol.BASES:
        receipt = tmp_path / f"plans-{base}.json"
        pins[base] = tools.grading.freeze(config, private, runs, baseline, receipt, base)
        empty = int(base == "wixqa" and empty_text is not None)
        assert pins[base]["empty_answers"] == empty
        assert sum(pins[base]["requests"].values()) == 245 - 2 * empty
        assert len(pins[base]["plans"]) == 3
        assert set(pins[base]["answer_files"]) == {
            f"final-answers-{base}-b{n:02d}" for n in range(1, 11)
        }
        # No later base plan is needed for admission of the one just frozen.
        monkeypatch.setattr(tools.grading, "committed", lambda p: tools.common.sha(p))
        assert tools.grading.admitted(receipt, private, baseline, base) == pins[base]
    assert sum(sum(pin["requests"].values()) for pin in pins.values()) == (
        735 if empty_text is None else 733
    )
    assert {
        p.relative_to(history): p.read_bytes() for p in history.rglob("*") if p.is_file()
    } == before
    source = history / "judge/wixqa"
    old_record = {
        "provenance": {k + "_sha256": v for k, v in old["bases"]["wixqa"]["bridge_source"].items()}
    }
    assert tools.prepare.source_gate(source, old_record) == old["bases"]["wixqa"]["bridge_source"]
    wrong = copy.deepcopy(old_record)
    wrong["provenance"]["verdicts_sha256"] = "changed"
    with pytest.raises(SystemExit, match="historical bridge inputs"):
        tools.prepare.source_gate(source, wrong)
    replies = source / "verdicts.jsonl"
    original = replies.read_bytes()
    replies.write_bytes(b"")
    wrong["provenance"]["verdicts_sha256"] = tools.common.sha(replies)
    with pytest.raises(SystemExit, match="15 admitted bridge originals"):
        tools.prepare.source_gate(source, wrong)
    replies.write_bytes(original)
    for base in tools.protocol.BASES:
        empty = int(base == "wixqa" and empty_text is not None)
        for metric, expected in (("m1", 115 - empty), ("m2", 115 - empty), ("bridge", 15)):
            folder = private / "judge" / f"{base}-{metric}"
            plan = tools.common.read(folder / "plan.json")
            assert plan["salt"] == answer.SALT
            assert plan["instructions_sha256"] == answer._digest(answer.INSTRUCTIONS)
            assert pins[base]["requests"][f"{base}-{metric}"] == expected
            assert sum("retest_of" in i for i in plan["items"]) == 15
            if metric != "bridge":
                assert len(plan["items"]) == 115
                assert all(i["has_reference"] is (metric == "m2") for i in plan["items"])
                blanks = [i for i in plan["items"] if i.get("empty_answer")]
                assert len(blanks) == empty
                assert all("message" not in i for i in blanks)
                assert all(
                    i["retest_of"] not in {b["item_id"] for b in blanks}
                    for i in plan["items"]
                    if "retest_of" in i
                )
                if empty:
                    # The real frozen export keeps all 100 questions and grades the empty one bad.
                    replies = [
                        tools.helpers.verdict_reply(i) for i in plan["items"] if "message" in i
                    ]
                    if metric == "m2":
                        for reply in replies:
                            verdict = json.loads(reply["raw_text"])
                            verdict["reference"] = "agrees"
                            reply["raw_text"] = json.dumps(verdict)
                    journal(folder / "verdicts.jsonl", replies)
                    out = tmp_path / "exported"
                    result = tools.grading.export_one(base, metric, private, runs, pins[base], out)
                    exported = tools.common.rows(out / f"stage5-{base}-{metric}.cases.jsonl")
                    assert result["status"] == "counted" and len(exported) == 100
                    blank = next(r for r in exported if r.get("empty_answer"))
                    assert blank["grade"] == "bad" and blank["missing"] is False
                    if metric == "m2":
                        assert blank["m2"] == "empty_answer"
            else:
                assert len(plan["items"]) == 30
                source_lines = (
                    (history / "judge" / base / "verdicts.jsonl")
                    .read_bytes()
                    .splitlines(keepends=True)
                )
                first = {i["item_id"] for i in plan["items"] if "retest_of" not in i}
                assert (folder / "verdicts.jsonl").read_bytes() == b"".join(
                    line for line in source_lines if json.loads(line)["item_id"] in first
                )
    receipt, pin = tmp_path / "plans-wixqa.json", pins["wixqa"]
    commits = []
    monkeypatch.setattr(tools.grading, "committed", lambda p: commits.append(p))
    assert tools.grading.admitted(receipt, private, baseline, "wixqa") == pin
    assert commits == [receipt, baseline]
    for victim, message in (
        (private / "references/wixqa.jsonl", "references differ"),
        (private / "judge/wixqa-bridge/verdicts.jsonl", "historical bridge replies"),
    ):
        original = victim.read_bytes()
        victim.write_bytes(b"changed\n")
        with pytest.raises(SystemExit, match=message):
            tools.grading.admitted(receipt, private, baseline, "wixqa")
        victim.write_bytes(original)
    incomplete = copy.deepcopy(pin)
    del incomplete["plans"]["wixqa-bridge"]
    tools.common.write(receipt, incomplete)
    with pytest.raises(SystemExit, match="receipt lacks plans"):
        tools.grading.admitted(receipt, private, baseline, "wixqa")
    tools.common.write(receipt, pin)
    victim = private / "judge/wixqa-m1/plan.json"
    victim.write_bytes(victim.read_bytes() + b" \n")
    with pytest.raises(SystemExit, match="plan differs"):
        tools.grading.admitted(receipt, private, baseline, "wixqa")
    with pytest.raises(SystemExit, match="new judge"):
        tools.grading.freeze(config, private, runs, baseline, receipt, "wixqa")


def test_receipt_recheck_rejects_any_old_input_mutation(tools, tmp_path, monkeypatch):
    path = tmp_path / "baseline.json"
    tools.common.write(path, {"inputs": {"old": "digest"}})
    called = []
    monkeypatch.setattr(tools.prepare, "committed", lambda p: called.append(p))
    monkeypatch.setattr(tools.prepare, "inputs", lambda *a: {"inputs": {"old": "digest"}})
    assert tools.prepare.check_receipt(path, {}, tmp_path)["inputs"] == {"old": "digest"}
    assert called == [path]
    monkeypatch.setattr(tools.prepare, "inputs", lambda *a: {"inputs": {"old": "changed"}})
    with pytest.raises(SystemExit, match="baseline receipt differs"):
        tools.prepare.check_receipt(path, {}, tmp_path)


@pytest.mark.parametrize("metric", ["m1", "m2", "bridge"])
def test_a_judge_duration_stop_survives_export_even_with_stable_verdicts(
    tools, tmp_path, monkeypatch, metric
):
    private, out = tmp_path / "private", tmp_path / "exports"
    folder = private / "judge" / f"wixqa-{metric}"
    tools.common.write(folder / "plan.json", {"runs": []})
    tools.common.write(folder / "NOT_EVIDENCE.json", {"status": "NOT_EVIDENCE"})
    monkeypatch.setattr(tools.grading, "batch_hashes", lambda *a: {})
    monkeypatch.setattr(
        tools.grading,
        "frozen",
        lambda *a: SimpleNamespace(export=lambda *a: {"status": "counted", "retained": 114}),
    )
    monkeypatch.setattr(
        tools.judge, "bridge_export", lambda *a: {"status": "counted", "retained": 29}
    )
    pin = {"base": "wixqa", "answer_files": {}, "inputs": {"wixqa": {"source": {}}}}
    result = tools.grading.export_one("wixqa", metric, private, tmp_path / "runs", pin, out)
    assert result["status"] == "NOT_EVIDENCE" and result["request_duration_stop"] is True
    assert result["retained"] == (29 if metric == "bridge" else 114)
    assert tools.common.read(out / f"stage5-wixqa-{metric}.json") == result


@pytest.mark.parametrize(
    "failed_bridge,expected", [(None, "holds"), ("multihoprag", "holds"), ("wixqa", "NOT_EVIDENCE")]
)
def test_final_record_requires_both_primary_bridges_but_multihop_is_advisory(
    tools, tmp_path, monkeypatch, failed_bridge, expected
):
    data, private, runs, exports = (tmp_path / n for n in ("data", "private", "runs", "exports"))
    baseline, receipts = tmp_path / "baseline.json", tmp_path / "receipts"
    tools.common.write(baseline, {})
    ids = list(answers_table())
    config = {"data": str(data), "bases": {}, "item6_sha": "e" * 40}
    held, measured, pin = (
        {"bases": {}, "item6_sha": "e" * 40},
        {},
        {"answer_files": {}, "plans": {}, "empty_answers": 0},
    )
    change = {"item6_sha": "e" * 40, "stage5_sha": "f" * 40, "changed_paths": []}
    complete = {"code_sha": "f" * 40, "product_diff": change}
    pin["completion"] = complete
    for base in tools.protocol.BASES:
        tools.common.write(receipts / f"plans-{base}.json", {})
        config["bases"][base] = {"m1": f"old-{base}-m1.json", "m2": f"old-{base}-m2.json"}
        held["bases"][base] = {
            "ids": ids,
            "references_sha256": "refs",
            "old_m3": list(gold_table(tools.protocol.GOLD_N[base]).values()),
        }
        measured[base] = {
            "provenance": {"code_sha": "f" * 40},
            "stand": {},
            "cases": [{"case_id": i, "prompts": [{"sha256": "prompt"}]} for i in ids],
        }
        for metric in tools.protocol.REQUESTS:
            name = f"stage5-{base}-{metric}"
            pin["plans"][f"{base}-{metric}"] = name
            tools.common.write(
                exports / f"{name}.json",
                {
                    "plan_sha256": name,
                    "source_plan_sha256": "old-plan",
                    "source_verdicts_sha256": "old-replies",
                    "status": "counted",
                    "retest": {"passed": base != failed_bridge},
                },
            )
    tools.common.write(
        runs / "series.json",
        {
            "status": "complete",
            "baseline_sha256": tools.common.sha(baseline),
            "order": list(tools.protocol.BASES),
            "completed": [[b, n] for b in tools.protocol.BASES for n in range(1, 11)],
            "code_sha": "f" * 40,
        },
    )
    monkeypatch.setattr(tools.reading, "check_receipt", lambda *a: held)
    monkeypatch.setattr(tools.reading, "admitted", lambda *a: pin)
    monkeypatch.setattr(tools.reading, "batch_hashes", lambda *a: {})
    monkeypatch.setattr(tools.reading, "product_diff", lambda *a: change)
    monkeypatch.setattr(tools.reading, "series_gate", lambda *a: complete)
    monkeypatch.setattr(tools.reading, "answers", lambda r, b, d: measured[b])
    monkeypatch.setattr(
        tools.reading, "measure", lambda b, *a: list(gold_table(tools.protocol.GOLD_N[b]).values())
    )
    monkeypatch.setattr(tools.reading, "paired", lambda *a: {"direction": "not detected"})
    monkeypatch.setattr(
        tools.reading, "frozen", lambda *a: SimpleNamespace(reference=lambda *a: {})
    )

    def judge(path, base, metric, *args):
        assert path.name != "old-multihoprag-m2.json"  # never load the NOT_EVIDENCE comparator
        return {
            "provenance": {
                "plan_sha256": path.stem if path.name.startswith("stage5") else "old-plan",
                "verdicts_sha256": "old-replies",
            },
            "m2": {"new": 100},
        }, answers_table()

    monkeypatch.setattr(tools.reading, "judge_record", judge)
    result = tools.reading.build(
        config, private, runs, baseline, receipts, exports, tmp_path, "f" * 40
    )
    assert result["decision"]["outcome"] == expected
    assert result["corpora"]["multihoprag"]["m2"]["paired"] is False
    if failed_bridge:
        failed = result["corpora"][failed_bridge]
        assert failed["status"] == "NOT_EVIDENCE" and "m3" not in failed
        assert len(failed["sent_cases"]) == 100  # the new deterministic observations remain


@pytest.fixture
def gold_archive(tools, monkeypatch):
    # Reuse the registered synthetic chunk archive, never an external-base document.
    fixture = load(ROOT / "tests/test_stage7_arms_replay.py", "s5_gold_fixture", monkeypatch)
    reader = tools.sent_gold.SentGold.__new__(tools.sent_gold.SentGold)
    reader.base, reader.chunks, reader.arms = "wixqa", fixture.CHUNKS, fixture.ar
    reader.sources, reader.places = None, fixture.Spans(fixture.CHUNKS)
    reader.cases = {"q": {**fixture.gold_case("wixqa", "q"), "query": "Synthetic question?"}}
    return fixture, reader


def test_actual_prompt_reader_and_product_expansion_read_sent_not_ranked(
    tools, gold_archive, tmp_path
):
    from agent.prompts import build_qa_prompt
    from llm.providers.base import flatten_messages

    fixture, reader = gold_archive
    replay = fixture.machine()
    ranked = [2, 7, 4, 0, 8]
    with fixture.ar.overlap_of(fixture.SETTINGS["chunk_overlap"]):
        expanded = replay.hybrid._expand_parents([replay.docs[i] for i in ranked])
    folder = tmp_path / "v4-wixqa-b01"
    tools.common.write(folder / "effective_settings.json", {"all": fixture.SETTINGS})
    question = reader.cases["q"]["query"]
    tools.common.write(
        folder / "cases/q.json",
        {
            "case_id": "q",
            "question": question,
            "answer": "Synthetic reply [1].",
            "events": [],
            "t0_monotonic": 10,
            "total_sec": 30,
        },
    )
    journal(
        folder / "stages.jsonl",
        [
            {
                "event": "end",
                "stage": "hybrid._rerank_scored_with_status",
                "monotonic": 11,
                "reranker_ok": True,
                "chunk_index": ranked,
            },
            {
                "event": "end",
                "stage": "hybrid._expand_parents",
                "monotonic": 12,
                "chunk_index": ranked,
                "chars": sum(len(d.page_content) for d in expanded),
            },
        ],
    )
    prompt = folder / "prompts/001-stream.txt"
    prompt.parent.mkdir()

    def read_sent(kept):
        documents = [{"page_content": d.page_content, "metadata": d.metadata} for d in kept]
        text = flatten_messages([{"role": "user", "content": build_qa_prompt(question, documents)}])
        prompt.write_text(text, "utf-8", newline="\n")
        published = {"q": {"prompts": [{"file": prompt.name, "sha256": tools.common.sha(prompt)}]}}
        return reader.run(folder, published)[0]

    assert read_sent(expanded)["hit"] == 1
    # The gold article is ranked fourth: trimming the sent tail loses it, despite rank parity.
    assert read_sent(expanded[:3])["hit"] == 0
    with pytest.raises(SystemExit, match="saved prompt differs"):
        reader.run(folder, {"q": {"prompts": [{"file": prompt.name, "sha256": "wrong"}]}})
    stages = tools.common.rows(folder / "stages.jsonl")
    stages[1]["chars"] += 1
    journal(folder / "stages.jsonl", stages)
    with pytest.raises(SystemExit, match="expansion replay differs"):
        read_sent(expanded)


def test_an_unplaceable_excerpt_or_wrong_source_refuses(tools, gold_archive, monkeypatch):
    fixture, reader = gold_archive
    replay = fixture.machine()
    doc = replay.docs[0]
    case = reader.cases["q"]
    with pytest.raises(SystemExit, match="source order"):
        reader.one(case, [("another.md", doc.page_content)], [doc], fixture.SETTINGS)
    monkeypatch.setattr(reader.arms, "sent_point", lambda *a: ({}, 1))
    with pytest.raises(SystemExit, match="excerpt could not be placed"):
        reader.one(case, [(doc.metadata["source"], "cut")], [doc], fixture.SETTINGS)


@pytest.mark.parametrize(
    "broken",
    [None, "prompt", "sent", "cut", "question", "gold", "point", "total", "m2", "provenance"],
)
def test_stage2_gate_reproduces_p2_sent_and_p4_parity_before_reading_v4(
    tools, gold_archive, tmp_path, monkeypatch, broken
):
    fixture, reader = gold_archive
    from retrieval_summary import coverage

    from evaluation import external_gold

    reader.base, reader.sources = "multihoprag", {}
    reader.cases = {"q": {**fixture.gold_case("multihoprag", "q"), "query": "Synthetic question?"}}
    reader.places.members = lambda docs: [
        i
        for doc in docs
        for i in external_gold.expansion_members(
            doc["text"],
            doc["metadata"]["chunk_index"],
            reader.chunks,
            fixture.SETTINGS["parent_expansion_window"],
            fixture.SETTINGS["chunk_overlap"],
        )
    ]
    raw = fixture.recorded(fixture.machine(), "q", 1, "Synthetic question?", "one")
    got = coverage("multihoprag", reader.cases["q"], raw, reader.places, {}, reader.chunks)
    assert got["unresolved"] is None and got["excerpt_pieces_missed"] == 0
    point = got["points"]["sent"]
    assert point["all_evidence_coverage"] == 1
    data, run = tmp_path / "data", tmp_path / "p2-multihoprag"
    file = data / "multihoprag/cases.jsonl"
    journal(file, [reader.cases["q"]])
    (data / "multihoprag/chunks.json.gz").write_bytes(b"synthetic hashed archive")
    exported, combined = tmp_path / "p2-multihoprag.json", tmp_path / "stage2-record.json"
    p = {
        "code_sha": "5e308fe",
        "settings": {},
        "parent_expansion_window": 2,
        "archive_sha256": tools.common.sha(data / "multihoprag/chunks.json.gz"),
        "source_sha256": {"receipt": "digest"},
        "cases_file_sha256": tools.common.sha(file),
    }
    row = {
        "case_id": "q",
        "gold": True,
        "points": {"sent": point},
        "path_breaks": [],
        "answer_prompt_same": True,
        "prompt": {"sha256": raw["prompt"]["sha256"]},
    }
    published = {
        "corpora": {
            "multihoprag": {
                "m3": {"points": {"sent": {"all_evidence_coverage": {"n": 1, "hits": 1}}}},
                "m2": {"status": "NOT_EVIDENCE"},
            }
        }
    }
    answers = [{"case_id": "q", "prompts": [{"sha256": raw["prompt"]["sha256"]}]}]
    if broken == "prompt":
        raw["prompt"]["text"] += "changed"
    elif broken == "sent":
        raw["sent"][0]["text"] += "changed"
    elif broken == "cut":
        raw["sent"][0]["cut"] = not raw["sent"][0]["cut"]
    elif broken == "question":
        raw["question"] = "changed"
    elif broken == "gold":
        row["gold"] = False
    elif broken == "point":
        row["points"]["sent"] = {**point, "all_evidence_coverage": 0}
    elif broken == "total":
        published["corpora"]["multihoprag"]["m3"]["points"]["sent"]["all_evidence_coverage"][
            "hits"
        ] = 0
    elif broken == "m2":
        published["corpora"]["multihoprag"]["m2"]["status"] = "counted"
    elif broken == "provenance":
        p["archive_sha256"] = "changed"
    tools.common.write(exported, {"provenance": p})
    journal(exported.with_suffix(".cases.jsonl"), [row])
    tools.common.write(combined, published)
    tools.common.write(
        run / "launch.json",
        {"status": "complete", "code_sha": "5e308fe", "tenant": "ext_multihoprag", "cases": ["q"]},
    )
    tools.common.write(run / "effective_settings.json", {"all": fixture.SETTINGS, "settings": {}})
    tools.common.write(run / "retrieval/q.json", raw)
    monkeypatch.setattr(tools.sent_gold, "SentGold", lambda *a: reader)
    monkeypatch.setattr(tools.sent_gold, "questions", lambda *a: (file, ["q"]))
    monkeypatch.setattr(tools.protocol, "committed", lambda *a: "committed")
    monkeypatch.setattr(tools.run, "corpus", lambda *a: {"receipt": "digest"})
    if broken is None:
        result = tools.sent_gold.stage2_gate(data, run, exported, combined, answers)
        assert result == [
            {
                "case_id": "q",
                "prompt_sha256": raw["prompt"]["sha256"],
                "gold": True,
                "hit": 1,
                "fraction": 1,
            }
        ]
        # It compares the input's 1/1, not a literal 10/70 from the published prose.
    else:
        with pytest.raises(SystemExit, match="stage2"):
            tools.sent_gold.stage2_gate(data, run, exported, combined, answers)


@pytest.mark.parametrize("broken", [None, "order", "generation", "stand", "path", "timing"])
def test_historical_answer_schema_binds_questions_generation_and_counted_retries(
    tools, tmp_path, monkeypatch, broken
):
    file = tmp_path / "questions.jsonl"
    ids = list(answers_table())
    journal(file, [{"case_id": i} for i in ids])
    path = tmp_path / "v4-wixqa.json"
    rec = {
        "base": "wixqa",
        "provenance": {
            "cases_file_sha256": tools.common.sha(file),
            "source_sha256": {"receipt": "digest"},
        },
        "runs": [
            {"counted": True, "launch": {"status": "complete", "code_sha": "4f48fed"}}
            for _ in range(10)
        ],
    }
    rec["runs"].append({"counted": False, "launch": {"status": "aborted", "code_sha": "4f48fed"}})
    cases = [
        {
            "case_id": i,
            "answered": True,
            "path_breaks": [],
            "result_sec": 80,
            "total_sec": 100,
            "first_token_sec": 40,
        }
        for i in ids
    ]
    if broken == "order":
        cases.reverse()
    elif broken == "generation":
        rec["provenance"]["cases_file_sha256"] = "changed"
    elif broken == "stand":
        rec["runs"][0]["launch"]["code_sha"] = "different"
    elif broken == "path":
        cases[0]["path_breaks"] = ["rerank"]
    elif broken == "timing":
        cases[0]["result_sec"] = 101
    tools.common.write(path, rec)
    journal(path.with_suffix(".cases.jsonl"), cases)
    monkeypatch.setattr(tools.prepare, "pin_public", lambda p: {p.name: tools.common.sha(p)})
    monkeypatch.setattr(tools.prepare, "questions", lambda *a: (file, ids))
    monkeypatch.setattr(tools.run, "corpus", lambda *a: {"receipt": "digest"})
    if broken is None:
        got, pins, times = tools.prepare.historical({"answers": str(path)}, "wixqa", ids, tmp_path)
        assert got == cases and len(pins) == 2
        assert times["total_sec"]["median"] == 100 and times["result_sec"]["median"] == 80
    else:
        with pytest.raises(SystemExit, match="historical"):
            tools.prepare.historical({"answers": str(path)}, "wixqa", ids, tmp_path)


@pytest.mark.parametrize(
    "path,allowed",
    [
        ("docs/specs/new.md", True),
        ("STATUS.md", True),
        ("reports/tool.py", False),
        ("reports/stage4-final/tools/run.py", False),
        ("reports/stage2/tools/live_api.py", False),
        ("reports/stage4-final/tools/external/new.py", True),
        ("reports/result.json", True),
        ("reports/data.cases.jsonl", True),
        ("reports/notes.md", True),
        ("tests/test_new.py", True),
        ("agent/x.py", False),
        ("config/settings.py", False),
        ("nested/notes.md", False),
        ("README.py", False),
    ],
)
def test_product_diff_checks_both_commits_and_only_registered_paths(
    tools, tmp_path, monkeypatch, path, allowed
):
    calls = []

    def git(args, **kw):
        calls.append((args, kw["cwd"]))
        if args[1] == "rev-parse":
            return args[2].removesuffix("^{commit}") + "\n"
        return path.encode() + b"\0"

    monkeypatch.setattr(tools.protocol.subprocess, "check_output", git)
    if allowed:
        assert tools.protocol.product_diff(tmp_path, "e" * 40, "f" * 40) == {
            "item6_sha": "e" * 40,
            "stage5_sha": "f" * 40,
            "changed_paths": [path],
        }
    else:
        with pytest.raises(SystemExit, match="product path differs"):
            tools.protocol.product_diff(tmp_path, "e" * 40, "f" * 40)
    assert calls[-1] == (
        ["git", "diff", "--name-only", "--no-renames", "-z", "e" * 40, "f" * 40, "--"],
        tmp_path,
    )
    # --no-renames exposes both an old product path and its allowed destination.
    with pytest.raises(SystemExit, match="full registration"):
        tools.protocol.product_diff(tmp_path, "not-a-sha", "f" * 40)


def test_driver_refuses_a_product_change_before_creating_out(tools, series, monkeypatch):
    data, out, baseline, _, _ = series
    monkeypatch.setattr(
        tools.execute,
        "product_diff",
        lambda *a: tools.common.require(False, "product path differs"),
    )
    monkeypatch.setattr(
        tools.execute, "batch", lambda *a, **kw: pytest.fail("must refuse before first batch")
    )
    with pytest.raises(SystemExit, match="product path differs"):
        tools.execute.run_series(data, out, baseline, baseline.parent, "e" * 40)
    assert not out.exists()


@pytest.mark.parametrize("failure", ["batch", "answer_gate"])
def test_later_base_failure_keeps_earlier_completion_and_runs_next_base(
    tools, series, monkeypatch, failure
):
    data, out, baseline, _, _ = series
    seen, first = [], {}

    def batch(path, base, *a, **kw):
        seen.append(base)
        if base != "wixqa":
            first.setdefault("bytes", (out / "wixqa.complete").read_bytes())
        if base == "conditionalqa" and failure == "batch":
            raise SystemExit("NOT_EVIDENCE: chat path broke")
        tools.common.write(path / "launch.json", {"base": base})

    def gate(runs, base, data):
        if base == "conditionalqa" and failure == "answer_gate":
            raise SystemExit("NOT_EVIDENCE: bad answer gate")
        return {"provenance": {"code_sha": "f" * 40}}

    monkeypatch.setattr(tools.execute, "batch", batch)
    monkeypatch.setattr(tools.execute, "answers", gate)
    monkeypatch.setattr(tools.execute, "wait_idle", lambda *a: {"busy": True})
    tools.execute.run_series(data, out, baseline, baseline.parent, "e" * 40)
    assert (out / "wixqa.complete").read_bytes() == first["bytes"]
    assert not (out / "conditionalqa.complete").exists()
    assert (out / "multihoprag.complete").is_file() and seen[-10:] == ["multihoprag"] * 10
    marker = tools.execute.series_gate(out, baseline, gate(out, "wixqa", data), "wixqa")
    assert marker["base"] == "wixqa"
    assert tools.common.read(out / "series.json")["status"] == "NOT_EVIDENCE"
    with pytest.raises(SystemExit, match="completion marker missing"):
        tools.execute.series_gate(out, baseline, gate(out, "wixqa", data), "conditionalqa")
    tools.common.write(out / "final-answers-wixqa-b01/launch.json", {"changed": True})
    with pytest.raises(SystemExit, match="changed batch hashes"):
        tools.execute.series_gate(out, baseline, gate(out, "wixqa", data), "wixqa")


@pytest.mark.parametrize("base", ["wixqa", "conditionalqa", "multihoprag"])
@pytest.mark.parametrize("state", ["committed", "uncommitted", "changed", "wrong_base"])
def test_each_receipt_must_be_committed_unchanged_for_its_own_base(
    tools, tmp_path, monkeypatch, base, state
):
    repo, private = tmp_path / "repo", tmp_path / "private"
    monkeypatch.setattr(tools.protocol, "ROOT", repo)
    baseline, receipt = repo / "baseline.json", repo / f"plans-{base}.json"
    tools.common.write(baseline, {})
    refs = private / "references" / f"{base}.jsonl"
    journal(refs, [{"case_id": "q", "reference_answers": []}])
    plans = {}
    for metric in tools.protocol.REQUESTS:
        path = private / "judge" / f"{base}-{metric}" / "plan.json"
        first = [
            {"item_id": f"i{n}", "case_id": f"q{n}", "message": "synthetic"}
            for n in range(15 if metric == "bridge" else 100)
        ]
        copies = [
            {**i, "item_id": i["item_id"] + "-retest", "retest_of": i["item_id"]}
            for i in first[:15]
        ]
        tools.common.write(path, {"items": first + copies})
        plans[f"{base}-{metric}"] = tools.common.sha(path)
    seed = private / "judge" / f"{base}-bridge" / "verdicts.jsonl"
    journal(seed, [{"synthetic": "original"}])
    pin = {
        "spec": tools.protocol.SPEC,
        "base": base,
        "baseline_sha256": tools.common.sha(baseline),
        "plans": plans,
        "empty_answers": 0,
        "requests": {f"{base}-{m}": n for m, n in tools.protocol.REQUESTS.items()},
        "inputs": {base: {"references_sha256": tools.common.sha(refs)}},
        "bridge_seeds": {base: tools.protocol.prefix(seed)},
    }
    tools.common.write(receipt, pin)
    committed = {p.name: p.read_bytes() for p in (baseline, receipt)}

    def git(args, **kw):
        name = args[-1].removeprefix("HEAD:")
        if state == "uncommitted" and name == receipt.name:
            raise subprocess.CalledProcessError(128, args)
        return committed[name]

    monkeypatch.setattr(tools.protocol.subprocess, "check_output", git)
    if state == "changed":
        receipt.write_bytes(receipt.read_bytes() + b" \n")
    if state == "committed":
        assert tools.grading.admitted(receipt, private, baseline, base) == pin
    else:
        with pytest.raises(SystemExit, match="committed unchanged|another base"):
            tools.grading.admitted(
                receipt, private, baseline, "wrong" if state == "wrong_base" else base
            )


@pytest.mark.parametrize("missing", ["multihoprag", "conditionalqa"])
@pytest.mark.parametrize("failed", [False, True])
def test_reading_keeps_completed_bases_and_names_missing_receipts(
    tools, tmp_path, monkeypatch, missing, failed
):
    config = {"item6_sha": "e" * 40}
    baseline = tmp_path / "baseline.json"
    tools.common.write(baseline, {})
    change = {"item6_sha": "e" * 40, "stage5_sha": "f" * 40, "changed_paths": []}
    monkeypatch.setattr(tools.reading, "check_receipt", lambda *a: {"item6_sha": "e" * 40})
    checks = []
    monkeypatch.setattr(tools.reading, "product_diff", lambda *a: checks.append(a) or change)
    for base in tools.protocol.BASES:
        if failed or base != missing:
            tools.common.write(tmp_path / f"plans-{base}.json", {})

    def one(config, base, *args):
        if base == missing:
            raise SystemExit("NOT_EVIDENCE: incomplete batch")
        return {"status": "counted", "m3": {"old_hits": 40}}, (answers_table(), answers_table()), {}

    monkeypatch.setattr(tools.reading, "read_base", one)
    monkeypatch.setattr(tools.reading, "paired", lambda *a: {"direction": "not detected"})
    result = tools.reading.build(
        config,
        tmp_path / "private",
        tmp_path / "runs",
        baseline,
        tmp_path,
        tmp_path,
        tmp_path,
        "f" * 40,
    )
    assert checks == [(tmp_path, "e" * 40, "f" * 40)]
    assert result["corpora"]["wixqa"] == {"status": "counted", "m3": {"old_hits": 40}}
    assert result["corpora"][missing]["status"] == "NOT_EVIDENCE"
    assert result["absent_bases"] == ([] if failed else [missing])
    assert result["decision"]["outcome"] == (
        "holds" if missing == "multihoprag" else "NOT_EVIDENCE"
    )
    monkeypatch.setattr(
        tools.reading,
        "product_diff",
        lambda *a: tools.common.require(False, "product path differs"),
    )
    with pytest.raises(SystemExit, match="product path differs"):
        tools.reading.build(
            config,
            tmp_path / "private",
            tmp_path / "runs",
            baseline,
            tmp_path,
            tmp_path,
            tmp_path,
            "f" * 40,
        )


def test_reference_validation_is_read_only_and_refuses_missing_or_changed(
    tools, tmp_path, monkeypatch
):
    cases, ref = tmp_path / "cases.jsonl", tmp_path / "history/references/wixqa.jsonl"
    journal(cases, [{"case_id": "q"}])
    made = [{"case_id": "q", "reference_answers": ["Synthetic reference"]}]
    monkeypatch.setattr(tools.prepare, "questions", lambda *a: (cases, ["q"]))
    monkeypatch.setattr(
        tools.prepare, "frozen", lambda *a: SimpleNamespace(reference_rows=lambda *a: made)
    )
    with pytest.raises(SystemExit, match="references missing"):
        tools.prepare.references("wixqa", tmp_path, ref, ["q"])
    assert not ref.exists()
    journal(ref, made)
    before = ref.read_bytes()
    assert tools.prepare.references("wixqa", tmp_path, ref, ["q"]) == tools.common.sha(ref)
    assert ref.read_bytes() == before
    ref.write_bytes(b"changed\n")
    with pytest.raises(SystemExit, match="references missing or changed"):
        tools.prepare.references("wixqa", tmp_path, ref, ["q"])
    assert ref.read_bytes() == b"changed\n"


def test_output_gate_protects_every_historical_root_and_data(tools, tmp_path):
    config = {
        "data": str(tmp_path / "data"),
        "stage2": {"run": str(tmp_path / "p2")},
        "bases": {
            "wixqa": {
                "runs": str(tmp_path / "v4/runs"),
                "references": str(tmp_path / "references/wixqa.jsonl"),
                "plans": {"m1": str(tmp_path / "v4/judge/wixqa-m1")},
            }
        },
    }
    for protected in [
        tmp_path,
        tmp_path / "data",
        tmp_path / "p2/new",
        tmp_path / "v4/runs/new",
        tmp_path / "references",
        tmp_path / "v4/judge/wixqa-m1/new",
    ]:
        with pytest.raises(SystemExit, match="overlaps read-only"):
            tools.grading.output_gate(protected, config)
    assert tools.grading.output_gate(tmp_path / "new", config) == tmp_path / "new"


@pytest.mark.parametrize(
    "broken",
    [
        None,
        "missing_plan",
        "private_hash",
        "prompt_hash",
        "batch_layout",
        "item6",
        "appledouble",
        "run_appledouble",
        "p2_appledouble",
    ],
)
def test_prepare_reads_the_exact_minimal_private_layout_before_any_m3(
    tools, tmp_path, monkeypatch, broken, stage7_archive
):
    from agent.prompts import build_qa_prompt
    from llm.providers.base import flatten_messages
    from scripts import external_base

    data, history = tmp_path / "data", tmp_path / "history"
    config = {"item6_sha": "e" * 40, "data": str(data), "bases": {}, "stage2": {}}
    ids = list(answers_table())
    for base in tools.protocol.BASES:
        series = "p4" if base == "multihoprag" else "v4"
        c = {"runs": str(history / series / "runs"), "plans": {}}
        public = tmp_path / "published" / base
        for metric in ("m1", "m2", "bridge") if base != "multihoprag" else ("m1", "m2"):
            name = f"bridge-{base}" if metric == "bridge" else f"{base}-{metric}"
            folder = history / series / "judge" / name
            tools.common.write(folder / "plan.json", {"items": []})
            journal(folder / "verdicts.jsonl", [{"synthetic": metric}])
            c["plans"][metric] = str(folder)
            c[metric] = str(public / f"{metric}.json")
            tools.common.write(
                Path(c[metric]),
                {
                    "provenance": {
                        "plan_sha256": tools.common.sha(folder / "plan.json"),
                        "verdicts_sha256": tools.common.sha(folder / "verdicts.jsonl"),
                        "references_sha256": "refs",
                    }
                },
            )
            journal(Path(c[metric]).with_suffix(".cases.jsonl"), [])
        c["source"] = c["plans"]["m1"]
        c["references"] = str(history / "references" / f"{base}.jsonl")
        journal(Path(c["references"]), [{"case_id": i} for i in ids])
        rows = []
        for n in range(10):
            folder = Path(c["runs"]) / f"{series}-{base}-b{n + 1:02d}"
            selected = ids[n * 10 : (n + 1) * 10]
            tools.common.write(
                folder / "launch.json",
                {
                    "code_sha": tools.protocol.OLD[base],
                    "tenant": "ext_" + base,
                    "status": "complete",
                },
            )
            (folder / "prompts").mkdir()
            for j, ident in enumerate(selected, 1):
                question = f"Synthetic question {ident}?"
                tools.common.write(
                    folder / "cases" / f"{j:02}-{ident}.json",
                    {
                        "case_id": ident,
                        "question": question,
                        "answer": "Synthetic reply.",
                    },
                )
                prompt = build_qa_prompt(
                    question,
                    [{"page_content": "Synthetic fact.", "metadata": {"source": "synthetic.md"}}],
                )
                (folder / "prompts" / f"{j:03}-stream.txt").write_text(
                    flatten_messages([{"role": "user", "content": prompt}]),
                    "utf-8",
                    newline="\n",
                )
            assert {p.name for p in folder.iterdir()} == {"launch.json", "cases", "prompts"}
            rows.extend(
                {
                    "case_id": ident,
                    "run": folder.name,
                    "prompts": [
                        {
                            "file": f"{j:03}-stream.txt",
                            "sha256": tools.common.sha(folder / "prompts" / f"{j:03}-stream.txt"),
                        }
                    ],
                }
                for j, ident in enumerate(selected, 1)
            )
        c["answers"] = str(public / "answers.json")
        tools.common.write(Path(c["answers"]), {"base": base})
        journal(Path(c["answers"]).with_suffix(".cases.jsonl"), rows)
        journal(data / base / "cases.jsonl", [{"case_id": i} for i in ids])
        corpus = data / base / "corpus"
        corpus.mkdir()
        (corpus / "synthetic.md").write_text("Synthetic corpus.", "utf-8")
        manifest = external_base.corpus_manifest.build_manifest(corpus, name="ext_" + base)
        external_base.corpus_manifest.write_manifest(data / base / "corpus.manifest.json", manifest)
        for name in ("chunks-report.json", "index/index-receipt.json"):
            tools.common.write(data / base / name, {})
        (data / base / "chunks.json.gz").write_bytes(b"synthetic archive")
        config["bases"][base] = c
    p2 = tmp_path / "p2-multihoprag"
    tools.common.write(p2 / "launch.json", {})
    tools.common.write(p2 / "effective_settings.json", {})
    tools.common.write(p2 / "retrieval/q.json", {})
    config["stage2"] = {
        "run": str(p2),
        "export": str(tmp_path / "p2.json"),
        "combined": str(tmp_path / "combined.json"),
    }
    for path in (tmp_path / "p2.json", tmp_path / "combined.json"):
        tools.common.write(path, {})
    journal(tmp_path / "p2.cases.jsonl", [])
    monkeypatch.setattr(tools.prepare, "questions", lambda b, d: (d / b / "cases.jsonl", ids))
    monkeypatch.setattr(tools.run, "corpus", lambda *a: {"checked": "digest"})
    monkeypatch.setattr(tools.prepare, "references", lambda *a: "refs")
    monkeypatch.setattr(tools.prepare, "pin_public", lambda p: {p.name: tools.common.sha(p)})
    c = config["bases"]["wixqa"]
    if broken == "missing_plan":
        Path(c["plans"]["m2"]).joinpath("plan.json").unlink()
    elif broken == "private_hash":
        Path(c["plans"]["m1"]).joinpath("verdicts.jsonl").write_bytes(b"changed\n")
    elif broken in ("prompt_hash", "batch_layout"):
        path = Path(c["answers"]).with_suffix(".cases.jsonl")
        rows = tools.common.rows(path)
        if broken == "prompt_hash":
            rows[0]["prompts"][0]["sha256"] = "changed"
        else:
            rows[0]["run"] = "v4-wixqa-b01-r1"
        journal(path, rows)
    elif broken == "item6":
        config["item6_sha"] = "not-a-sha"
    elif broken == "appledouble":
        (data / "wixqa/corpus/._x").write_bytes(b"AppleDouble")
    elif broken in ("run_appledouble", "p2_appledouble"):
        offender = (
            Path(c["runs"]) / "v4-wixqa-b01/prompts/._001-stream.txt"
            if broken == "run_appledouble"
            else p2 / "retrieval/._q.json"
        )
        offender.write_bytes(b"\x00\xffAppleDouble")
    before = {p.relative_to(history): p.read_bytes() for p in history.rglob("*") if p.is_file()}
    if broken is None:
        pins, inventory = tools.prepare.input_files(config)
        assert pins and set(inventory) == {*tools.protocol.BASES, "p2-multihoprag"}
        assert len(inventory["wixqa"]["runs"]) == 10
        assert set(inventory["wixqa"]["plans"]) == {"m1", "m2", "bridge"}
        assert set(inventory["multihoprag"]["plans"]) == {"m1", "m2"}
    else:
        with pytest.raises(
            (SystemExit, FileNotFoundError),
            match="layout differs" if broken == "appledouble" else None,
        ) as error:
            tools.prepare.input_files(config)
        if broken in ("run_appledouble", "p2_appledouble"):
            assert str(error.value) == (
                f"NOT_EVIDENCE: AppleDouble file in runs archive: {offender.as_posix()}"
            )
            assert offender.read_bytes() == b"\x00\xffAppleDouble"
    assert {
        p.relative_to(history): p.read_bytes() for p in history.rglob("*") if p.is_file()
    } == before
    calls = []

    def preflight(*a):
        calls.append("presence/hash")
        raise SystemExit("NOT_EVIDENCE: preflight refuses")

    monkeypatch.setattr(tools.prepare, "input_files", preflight)
    monkeypatch.setattr(tools.prepare, "stage2_gate", lambda *a: pytest.fail("M3 before hashes"))
    with pytest.raises(SystemExit, match="preflight refuses"):
        tools.prepare.inputs(config, tmp_path / "new")
    assert calls == ["presence/hash"]


def test_saved_historical_prompt_needs_no_stage_trace_and_keeps_source_ranges(
    tools, gold_archive, tmp_path
):
    from agent.prompts import build_qa_prompt
    from evaluation import external_gold as gold
    from llm.providers.base import flatten_messages
    from scripts.external_pilot import Places

    fixture, reader = gold_archive
    folder = tmp_path / "v4-wixqa-b01"
    tools.common.write(folder / "launch.json", {"status": "complete"})
    tools.common.write(
        folder / "cases/q.json",
        {"case_id": "q", "question": reader.cases["q"]["query"], "answer": "Synthetic answer."},
    )
    prompt = folder / "prompts/001-stream.txt"
    prompt.parent.mkdir()
    doc = {
        "page_content": reader.chunks[0]["page_content"],
        "metadata": reader.chunks[0]["metadata"],
    }
    prompt.write_text(
        flatten_messages(
            [{"role": "user", "content": build_qa_prompt(reader.cases["q"]["query"], [doc])}]
        ),
        "utf-8",
        newline="\n",
    )
    held = {"q": {"prompts": [{"file": prompt.name, "sha256": tools.common.sha(prompt)}]}}
    got = reader.saved_run(folder, held)
    assert got[0]["hit"] == 1
    assert set(p.name for p in folder.iterdir()) == {"launch.json", "cases", "prompts"}
    held["q"]["prompts"][0]["sha256"] = "wrong"
    with pytest.raises(SystemExit, match="saved prompt differs"):
        reader.saved_run(folder, held)
    # Coordinates, not answer-string containment: repeated snippets must not select a place.
    reader.base = "conditionalqa"
    reader.chunks = [{"page_content": "Alpha beta", "metadata": {"source": "doc.md"}}]
    reader.sources = {"doc.md": gold.Source.read("doc.md", "Alpha beta gamma")}
    reader.places = Places(reader.chunks, reader.sources, 0, 1)
    case = {"evidence_groups": [{"alternatives": [{"source_id": "doc.md", "start": 0, "end": 9}]}]}
    assert reader.saved_point(case, [("doc.md", "Alpha beta")]) == {
        "gold": True,
        "hit": 1,
        "fraction": 1,
    }
    assert reader.saved_point(case, [("doc.md", "beta")])["hit"] == 0
    reader.sources["doc.md"] = gold.Source.read("doc.md", "Alpha beta Alpha beta")
    with pytest.raises(SystemExit, match="unplaceable or ambiguous"):
        reader.saved_point(case, [("doc.md", "Alpha beta")])
    with pytest.raises(SystemExit, match="unplaceable or ambiguous"):
        reader.saved_point(case, [("doc.md", "missing")])
    reader.sources["doc.md"] = gold.Source.read("doc.md", "Alpha beta omitted tail")
    # A join over a skipped body must not credit the range between its visible paragraphs.
    gap_case = {
        "evidence_groups": [{"alternatives": [{"source_id": "doc.md", "start": 9, "end": 16}]}]
    }
    assert reader.saved_point(case, [("doc.md", "Alpha beta\n\ntail")])["hit"] == 1
    assert reader.saved_point(gap_case, [("doc.md", "Alpha beta\n\ntail")])["hit"] == 0


@pytest.mark.parametrize("paragraphs", [False, True])
def test_saved_point_strips_the_chunkers_repeated_table_header(tools, gold_archive, paragraphs):
    from evaluation import external_gold as gold
    from scripts.external_pilot import Places
    from vectordb import table_header

    _, reader = gold_archive
    reader.base = "conditionalqa"
    original = "Lead.\n\n| Name | Value |\n| --- | --- |\n| A | 1 |\n| B | 2 |\n| C | 3 |"
    header = table_header.header_rows(original, original.index("| C |")) + "\n"
    assert header == "| Name | Value |\n| --- | --- |\n"
    continued = header + "| C | 3 |"
    reader.chunks = [
        {"page_content": original[: original.index("| C |")], "metadata": {"source": "doc.md"}},
        {
            "page_content": continued,
            "metadata": {"source": "doc.md", table_header.PREFIX_KEY: len(header)},
        },
    ]
    reader.sources = {"doc.md": gold.Source.read("doc.md", original)}
    reader.places = Places(reader.chunks, reader.sources, 0, 1)
    low, high = reader.sources["doc.md"].occurrences("| C | 3 |")[0]
    case = {
        "evidence_groups": [{"alternatives": [{"source_id": "doc.md", "start": low, "end": high}]}]
    }
    sent = "Lead.\n\n" + continued if paragraphs else continued
    assert not reader.sources["doc.md"].occurrences(sent)
    assert reader.saved_point(case, [("doc.md", sent)]) == {"gold": True, "hit": 1, "fraction": 1}
    # An intact table already has a place; another seed's prefix must not erase its gold header.
    low, high = reader.sources["doc.md"].occurrences(header)[0]
    case["evidence_groups"][0]["alternatives"][0].update(start=low, end=high)
    intact = original[original.index("| Name |") :]
    assert reader.saved_point(case, [("doc.md", intact)])["hit"] == 1


@pytest.mark.parametrize("paragraphs", [False, True])
@pytest.mark.parametrize("reading", ["same", "hit_changes", "fraction_changes"])
def test_saved_point_repeats_are_admitted_only_for_an_invariant_reading(
    gold_archive, paragraphs, reading
):
    from evaluation import external_gold as gold
    from scripts.external_pilot import Places

    _, reader = gold_archive
    reader.base = "conditionalqa"
    original = "Repeat.\n\nGap.\n\nRepeat.\n\nGap.\n\nTail."
    reader.chunks = [{"page_content": original, "metadata": {"source": "doc.md"}}]
    reader.sources = {"doc.md": gold.Source.read("doc.md", original)}
    reader.places = Places(reader.chunks, reader.sources, 0, 1)
    repeats = reader.sources["doc.md"].occurrences("Repeat.")
    assert len(repeats) == 2
    alternatives = [{"source_id": "doc.md", "start": lo, "end": hi} for lo, hi in repeats]
    case = {
        "evidence_groups": [
            {"alternatives": alternatives if reading == "same" else alternatives[:1]}
        ]
    }
    if reading == "fraction_changes":
        lo, hi = reader.sources["doc.md"].occurrences("Gap.")[0]
        case["evidence_groups"].append(
            {"alternatives": [{"source_id": "doc.md", "start": lo, "end": hi}]}
        )
    sent = "Repeat.\n\nTail." if paragraphs else "Repeat."
    if reading == "same":
        assert reader.saved_point(case, [("doc.md", sent)]) == {
            "gold": True,
            "hit": 1,
            "fraction": 1,
        }
    else:
        # The fraction-only variant has hit=0 at both placements; comparing hit alone is wrong.
        with pytest.raises(SystemExit, match="ambiguous in its reading"):
            reader.saved_point(case, [("doc.md", sent)])


@pytest.mark.parametrize("paragraphs", [False, True])
def test_saved_point_checks_all_256_placements_and_refuses_larger_products(
    gold_archive, monkeypatch, paragraphs
):
    from agent.context_window import EXCERPT_GAP
    from evaluation import external_gold as gold
    from scripts import external_pilot

    _, reader = gold_archive
    reader.base = "conditionalqa"
    reader.chunks = [{"page_content": "X Y X", "metadata": {"source": "doc.md"}}]
    reader.sources = {"doc.md": gold.Source.read("doc.md", "X Y X")}
    reader.places = external_pilot.Places(reader.chunks, reader.sources, 0, 1)
    case = {"evidence_groups": [{"alternatives": [{"source_id": "doc.md", "start": 0, "end": 1}]}]}
    calls = []

    def reading(*args):
        calls.append(args)
        return {"all_evidence_coverage": 0, "evidence_recall": 0}

    monkeypatch.setattr(external_pilot, "read_gold", reading)
    gap = "\n\n" if paragraphs else EXCERPT_GAP
    assert reader.saved_point(case, [("doc.md", gap.join(["X"] * 8))])["hit"] == 0
    assert len(calls) == 256  # Enumeration, not a truncated sample of possible readings.
    calls.clear()
    with pytest.raises(SystemExit, match="exceed 256"):
        reader.saved_point(case, [("doc.md", gap.join(["X"] * 9))])
    assert calls == []


@pytest.fixture
def stage7_archive(tools, tmp_path, monkeypatch):
    root = tmp_path / "stage7-checkout"
    monkeypatch.setattr(tools.prepare, "ROOT", root)
    monkeypatch.setattr(
        tools.prepare, "pin_public", lambda p: {p.relative_to(root).as_posix(): tools.common.sha(p)}
    )

    def save(values):
        folder = root / "reports/stage7/5e308fe"
        journal(folder / "rows.jsonl", values)
        tools.common.write(
            folder / "record.json", {"parity": {"passed": 415, "v4_byte_equal": 300}}
        )
        pins = {p.relative_to(root).as_posix(): tools.common.sha(p) for p in folder.iterdir()}
        monkeypatch.setattr(tools.prepare, "STAGE7_FILES", pins)
        return pins

    save([])
    return root, save


def test_stage7_gate_pins_the_published_parity_checked_artifacts(tools):
    assert tools.prepare.STAGE7_FILES == {
        "reports/stage7/5e308fe/rows.jsonl": "2d87859ecfd5e2442eefadcc5dafb471e5a80d13d8227907d59e568010109627",
        "reports/stage7/5e308fe/record.json": "b9db1434a6091536540112591e29cb3f02f373660dd06469e6abebc3780b55e4",
    }


@pytest.mark.parametrize("base", ["wixqa", "conditionalqa"])
@pytest.mark.parametrize(
    "changed",
    [
        None,
        "prompt",
        "gold",
        "hit",
        "fraction",
        "missing",
        "extra",
        "duplicate",
        "label",
        "rows_hash",
        "record_hash",
    ],
)
def test_stage7_old_side_gate_matches_every_question_and_pins_both_files(
    tools, stage7_archive, base, changed
):
    root, save = stage7_archive
    hit, fraction = (
        ("gold_article", "gold_articles")
        if base == "wixqa"
        else ("all_evidence_coverage", "evidence_recall")
    )
    points = [
        {"case_id": "q", "prompt_sha256": "a" * 64, "gold": True, "hit": 1, "fraction": 1.0},
        {
            "case_id": "no-gold",
            "prompt_sha256": "b" * 64,
            "gold": False,
            "hit": None,
            "fraction": None,
        },
    ]
    archived = [
        {
            "label": "p2-" + base,
            "base": base,
            "case_id": p["case_id"],
            "index": n,
            "gold": p["gold"],
            "stratum": "synthetic",
            "v4_saved": True,
            "H_old": {
                "prompt": {"sha256": p["prompt_sha256"]},
                **({"points": {"sent": {hit: 1.0, fraction: 1.0}}} if p["gold"] else {}),
            },
        }
        for n, p in enumerate(points)
    ]
    if changed == "prompt":
        archived[0]["H_old"]["prompt"]["sha256"] = "c" * 64
    elif changed == "gold":
        archived[0]["gold"] = False
    elif changed in ("hit", "fraction"):
        archived[0]["H_old"]["points"]["sent"][hit if changed == "hit" else fraction] = (
            0.5 if changed == "fraction" else 0
        )
    elif changed == "missing":
        archived.pop()
    elif changed in ("extra", "duplicate"):
        archived.append(copy.deepcopy(archived[0]))
        if changed == "extra":
            archived[-1]["case_id"] = "extra"
    elif changed == "label":
        archived[0]["label"] = "p4-" + base
    pins = save(archived)
    if changed in ("rows_hash", "record_hash"):
        path = (
            root
            / "reports/stage7/5e308fe"
            / ("rows.jsonl" if changed == "rows_hash" else "record.json")
        )
        path.write_bytes(path.read_bytes() + b"\n")
    if changed is None:
        # The gate compares fractional readings at the registered six-decimal precision.
        points[0]["fraction"] = 0.9999999
        assert tools.prepare.stage7_gate(base, points) == pins
        assert set(pins) == {
            "reports/stage7/5e308fe/rows.jsonl",
            "reports/stage7/5e308fe/record.json",
        }
    else:
        with pytest.raises(SystemExit, match="stage7 old-side|case set differs"):
            tools.prepare.stage7_gate(base, points)


def test_empty_answer_is_bad_without_inventing_a_context_verdict(tools, monkeypatch):
    a, b = answers_table(), answers_table()
    b["q000"].update(grade="bad", empty_answer=True)
    del b["q000"]["context_has_answer"]
    calls = []

    def paired(old, new, families):
        calls.append((old, new))
        return {"direction": "not detected"}

    monkeypatch.setattr(tools.reading, "paired", paired)
    result = tools.reading.compare("wixqa", a, b, gold_table(), gold_table())
    assert result["status"] == "counted" and result["empty_answers"] == 1
    assert calls[0][1]["q000"] == 1
    assert result["context_has_answer"] == {"same": 99, "lost": 0, "gained": 0}
    del b["q000"]["empty_answer"]
    with pytest.raises(SystemExit, match="judge context field missing"):
        tools.reading.compare("wixqa", a, b, gold_table(), gold_table())


def test_stage5_command_blocks_keep_the_registration_and_work_in_fresh_sessions():
    spec = (ROOT / "docs/specs/stage5-final-external.md").read_text("utf-8")
    blocks = re.findall(r"```powershell\n(.*?)```", spec, re.S)
    assert len(blocks) == 4
    preamble = "\n".join(
        [
            '$Private = "D:/RAG_new_stage5_private"',
            '$Old = "D:/RAG_new_stage2_private"',
            '$Tools = "reports/stage4-final/tools/external"',
            '$Baseline = "reports/stage4-final/stage5/baseline.json"',
            '$Config = "$Private/inputs.json"',
            '$Item6Sha = "138f3b3f6ac223540965cc831838ff4f671a2200"',
            'if ([string]::IsNullOrWhiteSpace($Private)) { throw "Private root is empty" }',
        ]
    )
    for block in blocks:
        assert block.startswith(preamble)
        assert "--force-local" not in block
    assert (
        "git log -1 --format=%H --diff-filter=A -- reports/stage4-final/stage5/baseline.json"
        in blocks[1]
    )
    assert '[IO.File]::WriteAllText("$Private/STAGE5_SHA"' in blocks[1]
    stand_commands = "\n".join(
        [
            '$Src = "D:/RAG_new/.tmp/stage5-stand-src-$Short"',
            'if (Test-Path -LiteralPath $Src) { throw "Stand source already exists" }',
            "Checked git worktree add --detach $Src $Stage5Sha",
            'Checked python "$Src/reports/stage4-final/tools/raise_stand.py" $Stage5Sha',
            "Checked git worktree remove $Src",
        ]
    )
    assert stand_commands in blocks[1]
    assert blocks[1].count("raise_stand.py") == 1
    for block in blocks[1:]:
        assert "Checked git merge-base --is-ancestor $Stage5Sha HEAD" in block
        assert "$Short = $Stage5Sha.Substring(0, 7)" in block
        assert '$RunPrivate = "$Private/$Short"' in block
        assert '$Record = "reports/stage4-final/stage5/$Short"' in block
        assert '$Remote = "/Users/julia/RAG_new_stage5/$Short"' in block
    for block in blocks[2:]:
        assert '(Get-Content -LiteralPath "$Private/STAGE5_SHA" -Raw).Trim()' in block
        assert '$RunLabel = "runs"' in block
    assert (
        '& "$env:SystemRoot/System32/tar.exe" -xf "$RunPrivate/$Base.tar.gz" -C "$RunPrivate/runs"'
        in blocks[2]
    )
    assert "-C $Remote/$RunLabel $Base.complete $BatchNames" in blocks[2]
    mac_tar_lines = [
        line
        for block in re.findall(r"```(?:powershell|sh)\n(.*?)```", spec, re.S)
        for line in block.splitlines()
        if re.search(r"\btar\s", line)
    ]
    assert mac_tar_lines
    for line in mac_tar_lines:
        assert re.findall(r"\btar\s", line) == re.findall(r"(?<=COPYFILE_DISABLE=1 )tar\s", line)
    mac = re.search(r"```sh\n(.*?)```", spec, re.S).group(1)
    assert 'test -d "$P/source.git" || git clone --bare' in mac
    assert "RUN_LABEL=runs" in mac and "OUT=$P/$RUN_LABEL" in mac


def test_stage5_spec_pins_new_and_reused_tools_without_editing_item6_or_item7():
    spec = (ROOT / "docs/specs/stage5-final-external.md").read_text("utf-8")
    pins = dict(re.findall(r"`([^`]+)` `([0-9a-f]{64})`", spec))
    required = {p.relative_to(ROOT).as_posix() for p in TOOLS.glob("*.py")}
    required.update(p.relative_to(ROOT).as_posix() for p in EXTERNAL.glob("*.py"))
    required.update(
        {
            "tests/test_stage5_final_tools.py",
            "tests/test_stage4_final_tools.py",
            "reports/answer-prompt-v4/tools/bridge_plan.py",
            "reports/answer-prompt-v4/tools/v4_record.py",
            "reports/stage2/tools/answers_summary.py",
            "reports/stage2/tools/retrieval_summary.py",
            "reports/stage2/tools/judge_export.py",
            "reports/stage2/tools/stage2_common.py",
            "reports/stage2/tools/stage2_cases.py",
            "reports/stage7/tools/arms_replay.py",
            "evaluation/external_gold.py",
            "scripts/chat_answer_judge.py",
        }
    )
    assert set(pins) == required
    for name, digest in pins.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    for old in ("stage4-item6-final-aircargo.md", "stage4-item7-final-speed.md"):
        for name, digest in re.findall(
            r"`([^`]+)` `([0-9a-f]{64})`", (ROOT / "docs/specs" / old).read_text("utf-8")
        ):
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
            if name in pins:
                assert pins[name] == digest
    assert re.search(
        r"^Status: \*\*(draft — to be cold-read and registered|registered before the run)\*\*",
        spec,
        re.M,
    )
    for phrase in (
        "A cold read (docs/operations/audit_opus55_31_10_26_stage5.md) found 1 blocking, "
        "4 should fix and 5 minor; each is applied (its Disposition says how).",
        "735 requests",
        "MultiHop-RAG is advisory",
        "p2-multihoprag",
        "published",
        "NOT_EVIDENCE",
        "context_has_answer",
    ):
        assert phrase in spec

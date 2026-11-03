"""Read the committed 5v public record again; missing files fail, never skip.

The Mac has public exports, not the private series. Do not call build(): its
state.json registration/pilot/stops and judge_stops() marker scan cannot be
replayed; measurement.json cannot be compared with state['cases']. admitted()
also needs the private receipt, plans/request bodies, runs, attempt files,
measurement/locations, source inputs, bridge source journals/seed prefix and
reference bytes for validate_frozen(). Their receipt hashes are observations,
not substitutes for those bytes. exports() needs the plans, runs, references,
verdict journals, _vouched admission and NOT_EVIDENCE markers; therefore neither
"public export differs from journal" nor "public case export differs" can be
rechecked. Raw route/language/prompt-wrapper/answer-copy checks, judge reply
admission, retry clocks/costs and retest field agreement need those private data.
Saved stage-5 sent_cases gold labels cannot be remeasured without the corpus.

Repeat all public bindings, classifications, aggregates and stability checks.
Each arm-<key>.json has every terminal status: it supplies all that
normalize_counted_out() reads, with no measurement.json fallback. Rebuild the
arm's counts/times/tokens and pilot from public rows; probe execution, historical
stops and chunk boundaries remain hash-pinned observations in arm.json. Compare
reading.plans to the exports' status/retest/missing, use counted(), then strata(),
families(), primary(), loss_accounting(), diagnostics(), analyze() and decision().
Every corpus field and every loss id list is compared, not copied into the read.

The reader ran on Python 3.11.13. Python 3.12+ compensates float sums. Only the
weighted kappa calculation allows pytest.approx(rel=0, abs=1e-12); its rounded
bootstrap interval and all paired reads, integer claim sums, arm medians/p90,
counts and decisions compare exactly. No blanket floating-point tolerance.
"""

import hashlib
import importlib.util
import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "reports/generator-ceiling"
TOOLS = PUBLIC / "tools"
RECORDS = PUBLIC / "attempt-02"
SPEC = ROOT / "docs/specs/generator-ceiling.md"
CAPSULE = ROOT / "docs/evidence/generator-ceiling-record.md"
SPEC_SHA = "95adbbe1bd391b14a7ac6d771d7ec3df7b6f90133e0045877d20d6b7b9d99ebe"
KEYS = ("wixqa", "conditionalqa", "aircargo")
LABELS = dict(zip(KEYS, ("WixQA", "ConditionalQA", "aircargo"), strict=True))
STRATA = ("answer in context", "not in context", "no gold")
SIDES = ("package", "codex")
GRADES = ("good", "partial_ok", "bad")
LOSS_FIELDS = (
    "generator_losses",
    "retrieval_losses",
    "neither",
    "codex_good_without_gold_in_context",
    "retained_good",
    "lost_good",
)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recorded_path(value, *, reading_input=False):
    # public_inputs/tools use root-relative paths; build() adds export basenames.
    # PureWindowsPath accepts the laptop's separators on the Mac.
    path = PureWindowsPath(value)
    assert not path.drive and not path.root and ".." not in path.parts
    if reading_input and len(path.parts) == 1:
        return RECORDS / path.name
    return ROOT.joinpath(*path.parts)


@pytest.fixture(scope="module")
def tools():
    before_path, before_modules = sys.path[:], sys.modules.copy()
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("V6_PRODUCT_ROOT", str(ROOT))
        sys.path.insert(0, str(TOOLS))
        loaded = {}
        try:
            for suffix in ("common", "route", "answer", "judge", "record"):
                name = "ceiling_" + suffix
                spec = importlib.util.spec_from_file_location(name, TOOLS / (name + ".py"))
                assert spec and spec.loader
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
                loaded[suffix] = module
            yield SimpleNamespace(**loaded)
        finally:
            sys.path[:] = before_path
            for name, module in tuple(sys.modules.items()):
                source = getattr(module, "__file__", None)
                if source and Path(source).resolve().is_relative_to(ROOT / "reports"):
                    if name in before_modules:
                        sys.modules[name] = before_modules[name]
                    else:
                        del sys.modules[name]


@pytest.fixture(scope="module")
def artifacts(tools):
    c = tools.common
    old, new = {}, {}
    for key in KEYS:
        for metric in c.metrics(key):
            path = RECORDS / (c.plan_name(key, metric) + ".json")
            new[key, metric] = (
                read(path),
                None if metric == "bridge" else c.unique(rows(path.with_suffix(".cases.jsonl"))),
            )
            if metric != "bridge":
                old[key, metric] = c.instruments().judge.old_export(
                    c.old_path(key, metric), key, metric
                )
    return SimpleNamespace(
        record=read(RECORDS / "reading.json"),
        arm=read(RECORDS / "arm.json"),
        summaries={key: read(RECORDS / f"arm-{key}.json") for key in KEYS},
        receipts={key: read(RECORDS / f"plans-{key}.json") for key in KEYS},
        stage5=read(ROOT / "reports/stage4-final/stage5/2057ad0/record.json"),
        old=old,
        new=new,
    )


def test_public_bytes_registration_and_input_hashes(artifacts, tools):
    c, record = tools.common, artifacts.record
    expected = {
        f"reports/generator-ceiling/{attempt}/arm{suffix}.json"
        for attempt in ("attempt-01", "attempt-02")
        for suffix in ("", *("-" + key for key in KEYS))
    }
    expected.add("reports/generator-ceiling/attempt-02/reading.json")
    for key in KEYS:
        expected.add(f"reports/generator-ceiling/attempt-02/plans-{key}.json")
        for metric in c.metrics(key):
            stem = "reports/generator-ceiling/attempt-02/" + c.plan_name(key, metric)
            expected.add(stem + ".json")
            if metric != "bridge":
                expected.add(stem + ".cases.jsonl")
    assert set(FILES) == expected
    for name, digest in FILES.items():
        path = recorded_path(name)
        data = path.read_bytes()
        assert sha(path) == digest, name
        assert data.endswith(b"\n") and b"\r" not in data and not data.startswith(b"\xef\xbb\xbf")
        data.decode("utf-8")
        c.committed(path)
    assert sha(SPEC) == SPEC_SHA == c.registration(SPEC)
    public_inputs = c.public_inputs()
    rebuilt_inputs = dict(public_inputs)
    for key in KEYS:
        pin = artifacts.receipts[key]
        assert pin["key"] == key
        assert pin["spec_sha256"] == SPEC_SHA
        assert pin["tools"] == c.tool_hashes()
        for name, digest in pin["tools"].items():
            assert sha(recorded_path(name)) == digest, name
        assert pin["wrapper_sha256"] == sha(TOOLS / "wrapper.txt")
        assert pin["public_inputs"] == public_inputs
        for name, digest in pin["public_inputs"].items():
            assert sha(recorded_path(name)) == digest, name
        assert set(pin["plans"]) == set(pin["requests"]) == set(c.metrics(key))
        assert set(pin["old"]) == set(c.metrics(key)) - {"bridge"}
        for metric, held in pin["old"].items():
            path = c.old_path(key, metric)
            assert held == {
                "record_sha256": sha(path),
                "cases_sha256": sha(path.with_suffix(".cases.jsonl")),
            }
        for metric in c.metrics(key):
            path = RECORDS / (c.plan_name(key, metric) + ".json")
            rebuilt_inputs[path.name] = sha(path)
            if metric != "bridge":
                path = path.with_suffix(".cases.jsonl")
                rebuilt_inputs[path.name] = sha(path)
    assert record["input_sha256"] == rebuilt_inputs
    for name, digest in record["input_sha256"].items():
        path = recorded_path(name, reading_input=True)
        assert sha(path) == digest, name
        c.committed(path)


def check_stability(exported, first_rows, exporter, judge):
    held = exported["retest"]
    pairs, scale = held["pairs_list"], held["scale"]
    assert scale == ["bad", "partial_ok", "good"]
    assert held["planned"] == held["pairs"] == len(pairs) == len(set(held["pairs_ids"]))
    assert len(held["pairs_ids"]) == len(pairs)
    assert all(len(pair) == 2 and all(v in range(len(scale)) for v in pair) for pair in pairs)
    originals = {row["item_id"]: row for row in first_rows.values()}
    assert len(originals) == len(first_rows)
    for ident, (before, _) in zip(held["pairs_ids"], pairs, strict=True):
        assert scale[before] == originals[ident]["grade"]
    assert held["agree"] == sum(a == b for a, b in pairs)
    assert held["two_steps_apart"] == sum(abs(a - b) >= 2 for a, b in pairs)
    kappa = judge.quadratic_kappa(pairs, len(scale))
    if kappa is None:
        assert held["quadratic_kappa"] is None
    else:
        assert held["quadratic_kappa"] == pytest.approx(kappa, rel=0, abs=1e-12)
    assert {k: held[k] for k in ("ci95", "resamples_undefined")} == exporter.kappa_interval(
        pairs, len(scale)
    )
    assert held["passes_by_kappa"] == (kappa is not None and kappa >= exporter.KAPPA)
    assert held["passes_by_agreement"] == (
        len(pairs) > 0
        and held["agree"] * exporter.OF >= exporter.AGREE * len(pairs)
        and held["two_steps_apart"] == 0
    )
    assert held["enough_pairs"] == (len(pairs) >= exporter.MIN_PAIRS)
    assert held["passed"] == (
        held["enough_pairs"] and (held["passes_by_kappa"] or held["passes_by_agreement"])
    )
    # Retest verdict fields themselves are private; their public denominators are not.
    for field, counts in held["field_agreement"].items():
        n = (
            sum(originals[i]["has_reference"] for i in held["pairs_ids"])
            if field == "reference_counts"
            else len(pairs)
        )
        assert counts["of"] == n and 0 <= counts["agree"] <= n
    assert held["passed"] is True and exported["status"] == "counted"
    assert not exported.get("request_duration_stop", False)


def check_public_aggregates(exported, data, key, metric, exporter, judge):
    # The admitted original verdict fields are public. Never fabricate a journal
    # or bypass _vouched() to run summarize(); reconstruct its public counters.
    per_run = {}
    for label in exported["provenance"]["runs"]:
        mine = [r for r in data.values() if r["run"] == label]
        graded = [r for r in mine if not r.get("empty_answer") and not r["missing"]]
        per_run[label] = {
            "answers": len(mine),
            "graded": sum(not r["missing"] for r in mine),
            "missing": sum(r["missing"] for r in mine),
            "classes": {g: sum(r["grade"] == g for r in mine) for g in judge.CLASSES},
            "routes": dict(Counter(str(r["route"]) for r in mine)),
            "defects": dict(Counter(r["defect"] for r in graded)),
            "reference_counts": dict(Counter(r["reference"] for r in graded)),
            "marks_listed": sum(r["marks_listed"] for r in graded),
            "marks_supported": sum(r["citations_supported"] for r in graded),
            "marks_unlisted": sum(r["marks_unlisted"] for r in mine),
            "context_has_answer": sum(r["context_has_answer"] for r in graded),
            "answer_without_context": sum(
                r["answers_question"] in ("full", "partial") and not r["context_has_answer"]
                for r in graded
            ),
        }
    assert exported["per_run"] == per_run
    families = (
        {cid: [f"cluster:{r['cluster']}"] for cid, r in data.items()} if key != "aircargo" else None
    )
    grades = {cid: r["grade"] for cid, r in data.items()}
    assert exported["shares"] == exporter.shares(grades, exported["retest"]["scale"], families)
    if metric == "m2":
        m2_names = ("agrees", "partial", "disagrees", "declined", "empty_answer")
        assert exported["m2"] == {
            "with_reference": exporter.shares(
                {cid: r["m2"] for cid, r in data.items() if r["has_reference"]}, m2_names, families
            ),
            "without_reference": exporter.shares(
                {cid: r["m2"] for cid, r in data.items() if not r["has_reference"]},
                ("right", "wrong"),
                families,
            ),
        }
        if any(r.get("conditional") for r in data.values()):
            for group, wanted in (("conditional", True), ("not_conditional", False)):
                apart = {
                    cid: r
                    for cid, r in data.items()
                    if r["has_reference"] and bool(r.get("conditional")) is wanted
                }
                assert exported[group] == {
                    "questions": len(apart),
                    "shares": exporter.shares(
                        {cid: r["grade"] for cid, r in apart.items()},
                        exported["retest"]["scale"],
                        families,
                    ),
                    "m2": exporter.shares(
                        {cid: r["m2"] for cid, r in apart.items()}, m2_names, families
                    ),
                }


def test_receipts_exports_and_all_eight_plans(artifacts, tools):
    c = tools.common
    frozen, judge = c.instruments(), c.judge()
    exporter = frozen.common.final.frozen("export")
    plans = {}
    for key in KEYS:
        pin = artifacts.receipts[key]
        for metric in c.metrics(key):
            exported, data = artifacts.new[key, metric]
            name = c.plan_name(key, metric)
            plans[name] = {k: exported[k] for k in ("status", "retest", "missing") if k in exported}
            assert frozen.record.counted(exported, data)
            if metric == "bridge":
                old_record, old_data = artifacts.old[key, "m1"]
                assert exported["plan_sha256"] == pin["plans"][metric]
                for field in ("plan", "verdicts"):
                    assert (
                        exported[f"source_{field}_sha256"]
                        == pin["source"][field]
                        == old_record["provenance"][f"{field}_sha256"]
                    )
                held = exported["retest"]
                assert pin["requests"][metric] == held["planned"] == len(exported["pairs"])
                assert (
                    held["pairs_ids"]
                    == [p["first"] for p in exported["pairs"]]
                    == old_record["retest"]["pairs_ids"]
                )
                originals = {r["item_id"]: r for r in old_data.values()}
                for pair in exported["pairs"]:
                    assert pair["copy"] == pair["first"] + "-retest"
                    assert pair["case_id"] == originals[pair["first"]]["case_id"]
                    assert pair["old_cli"] in exported["admitted_cli"]["old"]
                    assert pair["new_cli"] in exported["admitted_cli"]["new"]
                check_stability(exported, old_data, exporter, judge)
                continue
            old_record, old_data = artifacts.old[key, metric]
            assert frozen.record.counted(old_record, old_data)
            p = exported["provenance"]
            historical = tools.judge.public_export({"provenance": old_record["provenance"]})[
                "provenance"
            ]
            assert exported["plan"] == name and exported["base"] == key
            assert exported["judge"] == "answers"
            assert p["plan_sha256"] == pin["plans"][metric]
            assert {k: v for k, v in p.items() if k not in ("plan_sha256", "verdicts_sha256")} == {
                k: v for k, v in historical.items() if k not in ("plan_sha256", "verdicts_sha256")
            }
            assert p["adapter_sha256"] == sha(ROOT / "scripts/chat_answer_judge.py")
            assert p["tool_sha256"] == sha(Path(exporter.__file__))
            assert p["references_sha256"] == pin["references_sha256"]
            assert p["references_withheld"] is (key != "aircargo" and metric == "m1")
            assert (p["route"]["model"], p["route"]["effort"], p["route"]["tools"]) == (
                "claude-opus-5-5",
                "max",
                "none",
            )
            assert p["prompt_id"] == "QA_PROMPT_V4"
            assert set(data) == set(old_data)
            assert exported["questions"] == len(data) == 100
            assert (
                exported["missing"] == sorted(cid for cid, r in data.items() if r["missing"]) == []
            )
            assert (
                exported["requests_valid"]
                == pin["requests"][metric]
                == sum(not r.get("empty_answer") for r in data.values())
                + exported["retest"]["planned"]
            )
            replies = exported["replies"]
            assert replies["rows"] == sum(replies["statuses"].values())
            for field in ("admitted_at_reply", "admitted_cli"):
                assert sum(replies[field].values()) == exported["requests_valid"]
            assert set(p["runs"]) == {r["run"] for r in data.values()}
            for cid, row in data.items():
                assert row["prompt_sha256"] == old_data[cid]["prompt_sha256"]
                assert row["documents"] == old_data[cid]["documents"]
                assert row["grade"] == ("bad" if row.get("empty_answer") else judge.classify(row))
                if not row.get("empty_answer"):
                    assert 1 <= row["admitted_reply"] <= p["replies_counted_per_request"]
                    assert row["admitted_cli"] in replies["admitted_cli"]
                if metric == "m1":
                    assert row["has_reference"] is False and row["reference"] == "none"
                else:
                    assert row["m2"] == exporter.m2(row, row)
            check_stability(exported, data, exporter, judge)
            check_public_aggregates(exported, data, key, metric, exporter, judge)
    assert len(plans) == 8 and plans == artifacts.record["plans"]


@pytest.fixture(scope="module")
def measurement(artifacts, tools):
    c, arm = tools.common, tools.answer
    measured = {}
    state = arm.initial(SPEC_SHA)
    for key in KEYS:
        summary = artifacts.summaries[key]
        assert summary["key"] == key and summary["spec_sha256"] == SPEC_SHA
        measured[key] = c.unique(summary["rows"])
        assert summary["whole"] is True and len(measured[key]) == 100
        assert set(measured[key]) == set(artifacts.old[key, "m1"][1])
        for cid, row in measured[key].items():
            assert row["status"] in arm.TERMINAL
            state["cases"][arm.tag(key, cid)] = {**row, "key": key}
            assert row["status"] == "accepted" and row["route_failures"] == 0
            assert len(row["attempts"]) == 1
            for attempt in row["attempts"]:
                assert (
                    attempt["saved_prompt_sha256"]
                    == artifacts.old[key, "m1"][1][cid]["prompt_sha256"]
                )
                assert attempt["kind"] == "accepted" and attempt["gate"]["passed"] is True
                assert attempt["gate"]["reasons"] == [] and attempt["timeout"] is False
                assert (
                    math.isfinite(attempt["elapsed_s"])
                    and 0 <= attempt["elapsed_s"] <= attempt["task_stop"]
                )
                for name, digest in (
                    ("rollout.jsonl", attempt["rollout_sha256"]),
                    ("request/prompt.txt", attempt["request_sha256"]),
                ):
                    assert (
                        artifacts.receipts[key]["attempt_files"][f"attempts/{attempt['id']}/{name}"]
                        == digest
                    )
            language = row["language"]
            for field in ("question_script", "answer_script"):
                counts = language[field]["counts"]
                winner = (
                    None if counts["LATIN"] == counts["CYRILLIC"] else max(counts, key=counts.get)
                )
                assert language[field]["script"] == winner
            assert language["match"] is (
                language["question_script"]["script"] is not None
                and language["question_script"]["script"] == language["answer_script"]["script"]
            )
    selected = arm.pilot({key: list(data.values()) for key, data in measured.items()})
    assert len(selected) == 20
    pilot_times = [a["elapsed_s"] for key, cid in selected for a in measured[key][cid]["attempts"]]
    for step in (1, 5, 20):
        assert arm.pilot_gate(state, selected, step)
    assert state["pilot_passed"] == artifacts.arm["pilot_passed"] is True
    assert state["forecast"] == artifacts.arm["forecast"] == arm.forecast(pilot_times)
    for key, data in measured.items():
        for cid, row in data.items():
            for attempt in row["attempts"]:
                assert attempt["postpilot"] is ((key, cid) not in selected)
                forecast = (
                    {"task": 180, "task_stop": 540} if (key, cid) in selected else state["forecast"]
                )
                assert attempt["task_forecast"] == forecast["task"]
                assert attempt["task_stop"] == forecast["task_stop"]
    state["agents_hashes"] = sorted(
        {a["agents_sha256"] for r in state["cases"].values() for a in r["attempts"]}
    )
    rebuilt = arm.route_numbers(state)
    # These historical observations cannot be reconstructed from terminal rows.
    saved_only = {"probe", "chunks", "stops"}
    assert {k: v for k, v in rebuilt.items() if k not in saved_only} == {
        k: v for k, v in artifacts.arm.items() if k not in saved_only
    }
    assert artifacts.arm == artifacts.record["arm"]
    assert artifacts.arm["stops"] == [] and artifacts.arm["probe"]["passed"] is True
    assert all(
        chunk["agents_sha256"] in state["agents_hashes"] for chunk in artifacts.arm["chunks"]
    )
    assert all(
        a["agents_sha256"] in state["agents_hashes"] for a in artifacts.arm["probe"]["attempts"]
    )
    assert [sum(r["language"]["match"] is False for r in measured[k].values()) for k in KEYS] == [
        0,
        0,
        2,
    ]
    return SimpleNamespace(
        rows=measured, pilot_n=len(selected), pilot_p90=arm.percentile90(pilot_times)
    )


def test_read_again_every_field_and_loss_id(artifacts, tools, measurement):
    c, reader = tools.common, tools.record
    old = {k: artifacts.old[k, "m1"][1] for k in KEYS}
    new = {
        k: reader.normalize_counted_out(artifacts.new[k, "m1"][1], measurement.rows[k])
        for k in KEYS
    }
    old_m2 = {k: artifacts.old[k, "m2"][1] for k in c.BASES}
    new_m2 = {k: artifacts.new[k, "m2"][1] for k in c.BASES}
    labels = reader.strata(old, artifacts.stage5)
    for key in KEYS:
        assert tuple(Counter(labels[key].values())[s] for s in c.STRATA) == c.EXPECTED[key]
        assert reader.families(key, old[key]) == {
            cid: [f"{key}:cluster:{r['cluster']}" if key in c.BASES else f"{key}:case:{cid}"]
            for cid, r in old[key].items()
        }
        held = artifacts.record["corpora"][key]
        assert reader.loss_accounting(old[key], new[key], labels[key]) == held["losses"]
        for side, data in (("package", old[key]), ("codex", new[key])):
            assert reader.diagnostics(data) == held["diagnostics"][side]
        if key in c.BASES:
            for side, data in (("package", old_m2[key]), ("codex", new_m2[key])):
                assert reader.diagnostics(data) == held["m2"]["unsupported_claim_defects"][side]
    assert reader.primary(old, new, labels) == artifacts.record["primary"]
    rebuilt = reader.analyze(old, new, old_m2, new_m2, artifacts.stage5)
    assert rebuilt == {name: artifacts.record[name] for name in ("primary", "corpora", "m2")}
    stopped = bool(
        artifacts.arm["stops"]
        or any(e.get("request_duration_stop", False) for e, _ in artifacts.new.values())
    )
    refusals = [
        tools.common.plan_name(*key)
        for key, (e, data) in artifacts.new.items()
        if not c.instruments().record.counted(e, data)
    ]
    assert reader.decision(rebuilt["primary"], refusals, stopped) == artifacts.record["decision"]


def test_registered_decision_and_arm(artifacts, measurement):
    record = artifacts.record
    assert record["decision"] == {
        "row": 2,
        "outcome": "the generator is the bottleneck",
        "production_change": False,
        "stop_fired": False,
    }
    assert record["primary"]["n"] == 224 and record["primary"]["indicator"] == "good"
    assert record["primary"]["detected"] is True and record["primary"]["direction"] == "rises"
    assert record["m2"]["n"] == 180 and record["m2"]["detected"] is False
    assert record["m2"]["direction"] == "not detected"
    assert tuple(
        record["arm"][k]
        for k in (
            "attempts",
            "redos",
            "counted_out",
            "infrastructure_failures",
            "language_mismatches",
            "raw_output_mismatches",
        )
    ) == (300, 0, 0, 0, 2, 0)
    assert record["arm"]["stops"] == [] and record["arm"]["pilot_passed"] is True
    assert measurement.pilot_n == 20 and f"{measurement.pilot_p90:.1f}" == "30.7"
    probe = read(PUBLIC / "attempt-01/arm.json")
    assert probe["probe"]["passed"] is False
    assert any(
        a["kind"] == "infrastructure" and a["reason"] == "cleanup_failure"
        for a in probe["probe"]["attempts"]
    )
    assert probe["attempts"] == 0
    for key in KEYS:
        summary = read(PUBLIC / f"attempt-01/arm-{key}.json")
        assert summary["key"] == key and summary["rows"] == [] and summary["whole"] is False


def assert_no_raw_strings(value, references, trail=()):
    if isinstance(value, dict):
        for key, item in value.items():
            path = (*trail, key)
            if key.lower() in {"question", "answer", "text", "content", "prompt", "document"}:
                assert not isinstance(item, str), path
            if key.lower() == "reference" and isinstance(item, str):
                assert item in references, path
            assert_no_raw_strings(item, references, path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            assert_no_raw_strings(item, references, (*trail, index))


def test_every_public_file_has_no_raw_text():
    from scripts.chat_answer_judge import REFERENCE

    paths = {recorded_path(name) for name in FILES}
    paths |= {
        p for p in PUBLIC.rglob("*") if p.suffix in {".json", ".jsonl"} and TOOLS not in p.parents
    }
    for path in sorted(paths):
        values = rows(path) if path.suffix == ".jsonl" else [read(path)]
        for index, value in enumerate(values):
            assert_no_raw_strings(value, REFERENCE, (path.relative_to(ROOT).as_posix(), index))


def test_named_public_history():
    def at(revision, path):
        result = subprocess.run(
            ["git", "show", f"{revision}:{path.relative_to(ROOT).as_posix()}"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, (revision, path)
        return result.stdout

    assert hashlib.sha256(at("f93508a", SPEC)).hexdigest() == SPEC_SHA
    assert b"Status: **registered before the first request**" in at("54a46e2", SPEC)
    for key, revision in zip(KEYS, ("e900f87", "adb35a7", "3bb48dc"), strict=True):
        path = RECORDS / f"plans-{key}.json"
        assert at(revision, path) == path.read_bytes()
    for name in FILES:
        path = recorded_path(name)
        assert at("e166109", path) == path.read_bytes()
        if path.parent == RECORDS and (
            path.name.startswith("arm")
            or path.name.startswith(("ceiling-wixqa-", "ceiling-conditionalqa-"))
            or path.name in ("ceiling-bridge-wixqa.json", "ceiling-bridge-conditionalqa.json")
        ):
            assert at("31f29af", path) == path.read_bytes()


PAIRED_HEADER = [
    "| Metric | Package hits / n (share) | Codex hits / n (share) | Change, pp | read95, pp | Clusters | Detected | Direction |",
    "|---|---:|---:|---:|---|---:|---|---|",
]


def paired_line(label, row):
    n, table = row["n"], row["table"]
    if not n:
        return f"| {label} | 0/0 (undefined) | 0/0 (undefined) | undefined | undefined | {row['clusters']} | {str(row['detected']).lower()} | {row['direction']} |"
    interval = ", ".join(f"{100 * value:+.2f}" for value in row["read95"])
    return (
        f"| {label} | {table['a'] + table['b']}/{n} ({100 * row['package']:.2f}%) | "
        f"{table['a'] + table['c']}/{n} ({100 * row['codex']:.2f}%) | "
        f"{100 * row['difference']:+.2f} | [{interval}] | {row['clusters']} | "
        f"{str(row['detected']).lower()} | {row['direction']} |"
    )


def capsule_lines(record, receipts, pilot_n, pilot_p90, route):
    """Bind every displayed number, including prose, to its public source.

    Commits bind public file versions in test_named_public_history(). Runtime,
    cleanup error/exit and resume chronology are explicitly operator-reported;
    the spec supplies route/prompt/limit/owner-decision labels (see CX_REPORT).
    """
    arm, corpora = record["arm"], record["corpora"]
    n = sum(corpora[k]["pairs"] for k in KEYS)
    lines = [
        "# Stage 5v: generator ceiling record",
        "",
        f"The registered outcome is row {record['decision']['row']}: **{record['decision']['outcome']}**.",
        "The [registered spec](../specs/generator-ceiling.md) decides on pooled M1 good share where the answer is in the sent context.",
        "",
        *PAIRED_HEADER,
        paired_line("Pooled M1 good, answer in context", record["primary"]),
        "",
        "The next step is a strong model for the product. The host (a GPU or an API instead of the Mac, decision D5) is the owner's.",
        "Production stays the 4B on the Mac until her word. No production change is authorized by this reading.",
        "",
        "## What was compared",
        "",
        f"The package (Qwen3-4B on the Mac, prompt V4) was compared with one GPT-6-Astra answer to each of the same {n} saved prompts, byte for byte inside the wrapper.",
        "Retrieval and context were held. Each Codex answer used profile `cw`, effort `xhigh`, in an isolated read-only task.",
        "One unseeded generation per side, in-sample, one judge. This diagnoses the generator's share of the losses; it is not a product candidate.",
        "The [reading](../../reports/generator-ceiling/attempt-02/reading.json) holds the public result. Differences are Codex minus package, in percentage points.",
        "read95 is the envelope of the paired Newcombe and cluster-bootstrap intervals. A difference is detected only when both exclude zero on the same side.",
        "",
        "## M1 by key and stratum",
        "",
        "M1 grades without references. Undefined cells have no observations.",
        "",
        *PAIRED_HEADER,
    ]
    for key in KEYS:
        for metric in ("good", "bad"):
            lines.append(paired_line(f"{LABELS[key]} M1 {metric}, all", corpora[key][metric]))
        for stratum in STRATA:
            for metric in ("good", "bad"):
                lines.append(
                    paired_line(
                        f"{LABELS[key]} M1 {metric}, {stratum}",
                        corpora[key]["strata"][stratum][metric],
                    )
                )
    lines += [
        "",
        "Transitions read from the package grade to the Codex grade.",
        "",
        "| Base | Package grade | n | Codex good | Codex partial_ok | Codex bad |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for key in KEYS:
        for grade in GRADES:
            counts = corpora[key]["transitions"][grade]
            lines.append(
                f"| {LABELS[key]} | {grade} | {sum(counts.values())} | "
                + " | ".join(str(counts[g]) for g in GRADES)
                + " |"
            )
    lines += [
        "",
        "## Loss accounting",
        "",
        "The loss categories partition the package's not-good answers. Kept and lost use the package's good answers as their denominator.",
        "",
        "| Base | Package not good / n | Generator losses | Retrieval losses | Neither | Codex good without gold in context | Package good kept | Package good lost |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    losses = {
        k: {
            "n": corpora[k]["pairs"],
            "package_not_good": corpora[k]["losses"]["package_not_good"],
            **{f: corpora[k]["losses"][f]["n"] for f in LOSS_FIELDS},
        }
        for k in KEYS
    }
    losses["pooled"] = {
        f: sum(row[f] for row in losses.values()) for f in ("n", "package_not_good", *LOSS_FIELDS)
    }
    for key, row in losses.items():
        bad, good = row["package_not_good"], row["n"] - row["package_not_good"]
        cells = [f"{row[f]}/{bad if f in LOSS_FIELDS[:4] else good}" for f in LOSS_FIELDS]
        lines.append(
            f"| {LABELS.get(key, 'Pooled')} | {bad}/{row['n']} | " + " | ".join(cells) + " |"
        )
    lines += [
        "",
        "## M2 beside M1",
        "",
        "M2 measures agreement with the reference. The pooled rise is not detected. ConditionalQA's overall rise and its answer-in-context rise are detected; WixQA's are not.",
        "aircargo has no references and no M2. The no-gold strata have no reference-agreement denominator.",
        "",
        *PAIRED_HEADER,
        paired_line("Pooled M2 agrees", record["m2"]),
    ]
    for key in KEYS[:2]:
        m2 = corpora[key]["m2"]
        lines.append(paired_line(f"{LABELS[key]} M2 agrees, all", m2["with_reference"]["agrees"]))
        for stratum in STRATA:
            lines.append(paired_line(f"{LABELS[key]} M2 agrees, {stratum}", m2["strata"][stratum]))
    lines.append(
        paired_line(
            "ConditionalQA M1 right declines, unanswerable",
            corpora["conditionalqa"]["right_declines"],
        )
    )
    no_ref = corpora["conditionalqa"]["m2"]["without_reference"]
    lines += [
        "",
        f"ConditionalQA's M2 right declines are {no_ref['right']['package']}/{no_ref['pairs']} for the package and {no_ref['right']['codex']}/{no_ref['pairs']} for Codex. The M1 right-decline change above is not detected.",
        "Training knowledge of products such as Wix may help. M1 penalizes unsupported claims; M2 agreement may not. These counts do not establish a cause for the gap between the rises.",
        "Both instruments' diagnostics follow. Each diagnostic covers all answers in its key, including those without a reference. Unlisted defect categories have zero counts.",
        "",
        "| Base / instrument | Side | n | Supported / total claims (share) | Unsupported-claim answers / n | Unsupported claims | Defects (answers) |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for key in KEYS:
        for metric in ("M1", "M2") if key != "aircargo" else ("M1",):
            data = (
                corpora[key]["diagnostics"]
                if metric == "M1"
                else corpora[key]["m2"]["unsupported_claim_defects"]
            )
            for side in SIDES:
                row, count = data[side], corpora[key]["pairs"]
                claims = row["claims"]
                defects = "; ".join(
                    f"{name} {value}" for name, value in sorted(row["defects"].items())
                )
                lines.append(
                    f"| {LABELS[key]} / {metric} | {side} | {count} | {claims['supported']}/{claims['total']} ({100 * claims['share']:.2f}%) | {row['unsupported_claim_answers']}/{count} | {row['unsupported_claims']} | {defects} |"
                )
    lines += [
        "",
        "## Retests and bridges",
        "",
        f"The laptop judge used `{route['model']}`, effort `{route['effort']}`, tools `{route['tools']}`, on the frozen stage 5 isolated route.",
        "A bridge re-grades kept package answers to check judge drift. It does not add another judge. Retests repeat the grades of the current answers.",
        "",
        "| Plan | New requests | Pairs / planned | Agree / n | Quadratic kappa | Two steps apart / n | Passed |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for key in KEYS:
        for metric in ("m1", "bridge", "m2") if key != "aircargo" else ("m1", "bridge"):
            name = (
                f"ceiling-bridge-{key}" if metric == "bridge" else f"ceiling-{key}-judge-{metric}"
            )
            retest = record["plans"][name]["retest"]
            kappa = (
                "undefined"
                if retest["quadratic_kappa"] is None
                else f"{retest['quadratic_kappa']:.4f}"
            )
            lines.append(
                f"| {LABELS[key]} {metric.upper() if metric != 'bridge' else metric} | {receipts[key]['requests'][metric]} | {retest['pairs']}/{retest['planned']} | {retest['agree']}/{retest['pairs']} | {kappa} | {retest['two_steps_apart']}/{retest['pairs']} | {str(retest['passed']).lower()} |"
            )
    requests = sum(sum(pin["requests"].values()) for pin in receipts.values())
    retests = record["plans"]["ceiling-wixqa-judge-m1"]["retest"]["planned"]
    bridge_n = record["plans"]["ceiling-bridge-wixqa"]["retest"]["pairs"]
    lines += [
        "",
        f"All {len(record['plans'])} plans count: {requests} new requests. Each metric has {corpora['wixqa']['pairs']} originals plus {retests} retests; each bridge has {bridge_n} kept grades plus {bridge_n} new grades.",
        "ConditionalQA M2 passes by agreement; aircargo M1 has undefined kappa and passes by agreement. No plan stopped.",
        "Operator history: aircargo grading paused after `31f29af` and resumed from kept verdicts. One `unavailable` reply was retried after its persisted `retry_at`.",
        "",
        "## The arm",
        "",
        f"attempt-02 passed the data-free probe. The pilot accepted {pilot_n}/{pilot_n}, with task p90 {pilot_p90:.1f} s. The resulting task forecast was {arm['forecast']['task']} s and task stop {arm['forecast']['task_stop']} s.",
        "",
        "| Attempts | Redos | Counted out / n | Infrastructure failures | Language mismatches / n | Raw-output mismatches | Stops | Pilot passed |",
        "|---:|---:|---:|---:|---:|---:|---:|---|",
        f"| {arm['attempts']} | {arm['redos']} | {arm['counted_out']}/{n} | {arm['infrastructure_failures']} | {arm['language_mismatches']}/{n} | {arm['raw_output_mismatches']} | {len(arm['stops'])} | {str(arm['pilot_passed']).lower()} |",
        "",
        "| Tasks, n | Median, s | p90, s | Input tokens | Cached input tokens | Output tokens | Reasoning output tokens |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        f"| {arm['task_seconds']['n']} | {arm['task_seconds']['median']:.3f} | {arm['task_seconds']['p90']:.3f} | {arm['tokens']['input_tokens']:,} | {arm['tokens']['cached_input_tokens']:,} | {arm['tokens']['output_tokens']:,} | {arm['tokens']['reasoning_output_tokens']:,} |",
        "",
        f"AGENTS SHA-256: `{arm['agents_hashes'][0]}`.",
        f"The {arm['language_mismatches']} language mismatches were aircargo questions in Russian with Latin product terms (operator observation). They were kept and graded. The spec stops the arm at more than five among {n}.",
        "Raw-output mismatches are reported separately; they are not a route gate. The ChatGPT plan has no per-request price. Codex time and tokens are not product latency or cost.",
        "",
        "attempt-01 was the data-free probe. It stopped with code 5 (`cleanup_failure`): TerminateProcess returned error 5 on a codex.exe exiting by itself (operator report).",
        "Amendment `f93508a`, before the first corpus request, counted a signalled process handle as exited by itself and refreshed registration hashes. attempt-01's four arm files remain its record.",
        "",
        "## Provenance and limits",
        "",
        f"Spec SHA-256: `{SPEC_SHA}`. Registration: `54a46e2`; amendment: `f93508a`.",
        "Plans were frozen and committed before each key's first grade: `e900f87` (WixQA), `adb35a7` (ConditionalQA), `3bb48dc` (aircargo).",
        "Receipt `31f29af` holds the arm summaries and WixQA/ConditionalQA exports. Receipt `e166109` adds aircargo's exports and the reading.",
        "Package stands: `2057ad0` for WixQA and ConditionalQA; `138f3b3` for aircargo (item 6).",
        "The operator reports that the laptop reader ran in the focused venv with Python 3.11.13 and exited 0.",
        "The [artifact test](../../tests/test_generator_ceiling_record_artifact.py) pins every public file's SHA-256 and LF bytes, checks registered tool/wrapper hashes and public provenance, and rebuilds the reading.",
        "Its docstring names the private checks it cannot repeat. Public case ids stay in the full repository; raw prompts, answers and verdict journals stay private.",
        "",
        "These reused questions are in-sample. There is one unseeded generation per side and one judge. No person graded anything (owner's decision D11).",
        "Judge and arm are different vendors, but the judge's family is the orchestrator's (D12).",
        "aircargo's stratum is a judge flag; the external strata are gold labels.",
        f"The spec's approximate detectable difference is `2.8 * sqrt(d / {record['primary']['n']})`, where d is the discordant fraction: about 5.9, 8.4 and 10.2 percentage points at d = 0.1, 0.2 and 0.3. Clustering can widen the interval.",
        '"Not detected" does not mean "no difference".',
    ]
    return lines


def test_every_capsule_number_is_bound(artifacts, tools, measurement):
    route = artifacts.new["wixqa", "m1"][0]["provenance"]["route"]
    lines = capsule_lines(
        artifacts.record, artifacts.receipts, measurement.pilot_n, measurement.pilot_p90, route
    )
    assert [line for line in lines if line.startswith("|")] == PRINTED_TABLES
    assert CAPSULE.read_text(encoding="utf-8") == "\n".join(lines) + "\n"
    assert len(artifacts.arm["agents_hashes"]) == 1
    spec = SPEC.read_text(encoding="utf-8")
    for phrase in (
        "Qwen3-4B",
        "prompt V4",
        "GPT-6-Astra",
        "profile cw",
        "xhigh",
        "read-only",
        "one unseeded generation per side",
        "one judge",
        "no human",
        "D11",
        "D12",
        "decision D5",
        "production stays the 4B on the Mac until her word",
        "More than five among 300",
        "2.8 × sqrt(d / 224)",
        "5.9, 8.4, 10.2",
        "d=0.1, 0.2, 0.3",
    ):
        assert phrase in spec, phrase
    assert tools.common.STANDS == {
        "wixqa": "2057ad0",
        "conditionalqa": "2057ad0",
        "aircargo": "138f3b3",
    }


# Public byte pins; no private ids or journals are embedded.
FILES = {
    "reports/generator-ceiling/attempt-01/arm-aircargo.json": "9bdd5a2d6ecc88c10035951fd96563ba0806ed858642186d1ba81fb45bb9a7c8",
    "reports/generator-ceiling/attempt-01/arm-conditionalqa.json": "8cae460244750a3f33b9e922ce5286deda62133d57a38e5e1e7943e0aba4478f",
    "reports/generator-ceiling/attempt-01/arm-wixqa.json": "f9f76cde758b510a1406e9cc58f45f1e02de7f887ba2b0ab3207e9f18987e035",
    "reports/generator-ceiling/attempt-01/arm.json": "56e2a9addb1433239489502901d5afbebe57da107b93ede5c72834b626dc980b",
    "reports/generator-ceiling/attempt-02/arm-aircargo.json": "268d1e688ffef25afc3a9bd6d86b6bec289e9300aa31e7631a98836f9f04f64c",
    "reports/generator-ceiling/attempt-02/arm-conditionalqa.json": "c7c9de75173d2f7ad921520e09eaef6dcbbc0e61efbd913428dd21bc48b50985",
    "reports/generator-ceiling/attempt-02/arm-wixqa.json": "a59bbc9af1bfc625d76ce21b4606c6ee1592e65b4848b469d6b93bbbcd5ca5c1",
    "reports/generator-ceiling/attempt-02/arm.json": "8217950215e6d8aabff2ca405cda60f9314de4ac9d34a809efcf5e3ac1b34be2",
    "reports/generator-ceiling/attempt-02/ceiling-aircargo-judge-m1.cases.jsonl": "376cea51f4e15d190c8d72d5badf7a377a50e75f225fffe0f1352a53c6aa7fd5",
    "reports/generator-ceiling/attempt-02/ceiling-aircargo-judge-m1.json": "dfd65c1ff0dd43e7b116e8b8d05d0aa0a05bdbbf089dd847cc228627d8fb4959",
    "reports/generator-ceiling/attempt-02/ceiling-bridge-aircargo.json": "4f487b7a9774168c9eda51c0f60adeb703543cb5051dba1d40e53c3f8733ad46",
    "reports/generator-ceiling/attempt-02/ceiling-bridge-conditionalqa.json": "1675c76bf4b40fdd2d8c659a4a96666a19ce766425e3d4b8d4bc4b7af6803b45",
    "reports/generator-ceiling/attempt-02/ceiling-bridge-wixqa.json": "a5a9a571596d3f4d431566f8b4be77f968fc729a7f19eb9573b31f7a519aea73",
    "reports/generator-ceiling/attempt-02/ceiling-conditionalqa-judge-m1.cases.jsonl": "f5cffdbb76acdb641b923df593ed2260df42be8a8d92f79b2283dcfe628e72fd",
    "reports/generator-ceiling/attempt-02/ceiling-conditionalqa-judge-m1.json": "9d3c8e53ee4244283bbde70f5845ed21a6361cdb622c64c35fdaa3417bce82f7",
    "reports/generator-ceiling/attempt-02/ceiling-conditionalqa-judge-m2.cases.jsonl": "b049febffa895a0cabedd7fdb4eef93365fd3e7a612f94b9831d9d2189240b60",
    "reports/generator-ceiling/attempt-02/ceiling-conditionalqa-judge-m2.json": "64b27a9e82195d74a17e9de1111c1542e4471f6abf859daf77957b1a0a1ae6de",
    "reports/generator-ceiling/attempt-02/ceiling-wixqa-judge-m1.cases.jsonl": "1a10696e5658284ee6e79638721f0ff6a6774fcbf18e5635e3d9324918eb5370",
    "reports/generator-ceiling/attempt-02/ceiling-wixqa-judge-m1.json": "7601f1aabe24dea7921601a3208da5694236a3f5b58e7c1b1e2b44a1b34745bf",
    "reports/generator-ceiling/attempt-02/ceiling-wixqa-judge-m2.cases.jsonl": "3918c121f6bb3f7fc14fc0c18fbfe19fe3478925d6d43b09ea9e361bfd772dde",
    "reports/generator-ceiling/attempt-02/ceiling-wixqa-judge-m2.json": "3d8f9db1091da1bee83aebde300b62b8beb6a9f3ad2b5c9012e98f5ab6984d6e",
    "reports/generator-ceiling/attempt-02/plans-aircargo.json": "14d300fc59f1889cccf29673e787b04ce94ce9db42d7e3c2c31e1fe4f2f51438",
    "reports/generator-ceiling/attempt-02/plans-conditionalqa.json": "7d55b1cd5438f3af2a0121abf57d503ea6ba4d27a6e6b1c07b30f8daa81f7079",
    "reports/generator-ceiling/attempt-02/plans-wixqa.json": "e61e610051f7d09f46b7d6b74472c3afc303bfe291f2bf16089da3c49245db3b",
    "reports/generator-ceiling/attempt-02/reading.json": "2dc32f4af6e10135081d37cc49b2d98cd46c5979e23de2ae227167f561b73a5d",
}

# Literal displayed cells pin only the capsule numbers, never case lists.
PRINTED_TABLES = """\
| Metric | Package hits / n (share) | Codex hits / n (share) | Change, pp | read95, pp | Clusters | Detected | Direction |
|---|---:|---:|---:|---|---:|---|---|
| Pooled M1 good, answer in context | 120/224 (53.57%) | 220/224 (98.21%) | +44.64 | [+37.33, +51.83] | 191 | true | rises |
| Metric | Package hits / n (share) | Codex hits / n (share) | Change, pp | read95, pp | Clusters | Detected | Direction |
|---|---:|---:|---:|---|---:|---|---|
| WixQA M1 good, all | 30/100 (30.00%) | 92/100 (92.00%) | +62.00 | [+50.13, +71.26] | 77 | true | rises |
| WixQA M1 bad, all | 59/100 (59.00%) | 2/100 (2.00%) | -57.00 | [-66.67, -45.88] | 77 | true | falls |
| WixQA M1 good, answer in context | 19/67 (28.36%) | 64/67 (95.52%) | +67.16 | [+53.40, +79.03] | 56 | true | rises |
| WixQA M1 bad, answer in context | 41/67 (61.19%) | 1/67 (1.49%) | -59.70 | [-72.22, -46.08] | 56 | true | falls |
| WixQA M1 good, not in context | 11/33 (33.33%) | 28/33 (84.85%) | +51.52 | [+27.60, +70.59] | 27 | true | rises |
| WixQA M1 bad, not in context | 18/33 (54.55%) | 1/33 (3.03%) | -51.52 | [-70.97, -29.06] | 27 | true | falls |
| WixQA M1 good, no gold | 0/0 (undefined) | 0/0 (undefined) | undefined | undefined | 0 | false | not detected |
| WixQA M1 bad, no gold | 0/0 (undefined) | 0/0 (undefined) | undefined | undefined | 0 | false | not detected |
| ConditionalQA M1 good, all | 38/100 (38.00%) | 92/100 (92.00%) | +54.00 | [+42.65, +64.89] | 60 | true | rises |
| ConditionalQA M1 bad, all | 53/100 (53.00%) | 0/100 (0.00%) | -53.00 | [-63.27, -42.61] | 60 | true | falls |
| ConditionalQA M1 good, answer in context | 28/58 (48.28%) | 57/58 (98.28%) | +50.00 | [+35.00, +64.91] | 36 | true | rises |
| ConditionalQA M1 bad, answer in context | 27/58 (46.55%) | 0/58 (0.00%) | -46.55 | [-61.40, -31.48] | 36 | true | falls |
| ConditionalQA M1 good, not in context | 4/22 (18.18%) | 19/22 (86.36%) | +68.18 | [+37.74, +91.30] | 18 | true | rises |
| ConditionalQA M1 bad, not in context | 14/22 (63.64%) | 0/22 (0.00%) | -63.64 | [-85.00, -38.16] | 18 | true | falls |
| ConditionalQA M1 good, no gold | 6/20 (30.00%) | 16/20 (80.00%) | +50.00 | [+22.33, +70.00] | 20 | true | rises |
| ConditionalQA M1 bad, no gold | 12/20 (60.00%) | 0/20 (0.00%) | -60.00 | [-80.00, -33.26] | 20 | true | falls |
| aircargo M1 good, all | 73/100 (73.00%) | 100/100 (100.00%) | +27.00 | [+18.43, +36.43] | 100 | true | rises |
| aircargo M1 bad, all | 13/100 (13.00%) | 0/100 (0.00%) | -13.00 | [-20.98, -6.58] | 100 | true | falls |
| aircargo M1 good, answer in context | 73/99 (73.74%) | 99/99 (100.00%) | +26.26 | [+17.74, +35.70] | 99 | true | rises |
| aircargo M1 bad, answer in context | 12/99 (12.12%) | 0/99 (0.00%) | -12.12 | [-20.00, -5.84] | 99 | true | falls |
| aircargo M1 good, not in context | 0/1 (0.00%) | 1/1 (100.00%) | +100.00 | [-12.21, +100.00] | 1 | false | not detected |
| aircargo M1 bad, not in context | 1/1 (100.00%) | 0/1 (0.00%) | -100.00 | [-100.00, +12.21] | 1 | false | not detected |
| aircargo M1 good, no gold | 0/0 (undefined) | 0/0 (undefined) | undefined | undefined | 0 | false | not detected |
| aircargo M1 bad, no gold | 0/0 (undefined) | 0/0 (undefined) | undefined | undefined | 0 | false | not detected |
| Base | Package grade | n | Codex good | Codex partial_ok | Codex bad |
|---|---|---:|---:|---:|---:|
| WixQA | good | 30 | 28 | 1 | 1 |
| WixQA | partial_ok | 11 | 11 | 0 | 0 |
| WixQA | bad | 59 | 53 | 5 | 1 |
| ConditionalQA | good | 38 | 37 | 1 | 0 |
| ConditionalQA | partial_ok | 9 | 8 | 1 | 0 |
| ConditionalQA | bad | 53 | 47 | 6 | 0 |
| aircargo | good | 73 | 73 | 0 | 0 |
| aircargo | partial_ok | 14 | 14 | 0 | 0 |
| aircargo | bad | 13 | 13 | 0 | 0 |
| Base | Package not good / n | Generator losses | Retrieval losses | Neither | Codex good without gold in context | Package good kept | Package good lost |
|---|---:|---:|---:|---:|---:|---:|---:|
| WixQA | 70/100 | 45/70 | 3/70 | 3/70 | 19/70 | 28/30 | 2/30 |
| ConditionalQA | 62/100 | 29/62 | 6/62 | 1/62 | 26/62 | 37/38 | 1/38 |
| aircargo | 27/100 | 26/27 | 0/27 | 0/27 | 1/27 | 73/73 | 0/73 |
| Pooled | 159/300 | 100/159 | 9/159 | 4/159 | 46/159 | 138/141 | 3/141 |
| Metric | Package hits / n (share) | Codex hits / n (share) | Change, pp | read95, pp | Clusters | Detected | Direction |
|---|---:|---:|---:|---|---:|---|---|
| Pooled M2 agrees | 81/180 (45.00%) | 99/180 (55.00%) | +10.00 | [+0.00, +19.44] | 117 | false | not detected |
| WixQA M2 agrees, all | 34/100 (34.00%) | 40/100 (40.00%) | +6.00 | [-7.84, +20.23] | 77 | false | not detected |
| WixQA M2 agrees, answer in context | 25/67 (37.31%) | 31/67 (46.27%) | +8.96 | [-10.26, +26.98] | 56 | false | not detected |
| WixQA M2 agrees, not in context | 9/33 (27.27%) | 9/33 (27.27%) | +0.00 | [-18.18, +19.35] | 27 | false | not detected |
| WixQA M2 agrees, no gold | 0/0 (undefined) | 0/0 (undefined) | undefined | undefined | 0 | false | not detected |
| ConditionalQA M2 agrees, all | 47/80 (58.75%) | 59/80 (73.75%) | +15.00 | [+2.56, +26.79] | 40 | true | rises |
| ConditionalQA M2 agrees, answer in context | 36/58 (62.07%) | 47/58 (81.03%) | +18.97 | [+3.63, +33.33] | 36 | true | rises |
| ConditionalQA M2 agrees, not in context | 11/22 (50.00%) | 12/22 (54.55%) | +4.55 | [-19.06, +27.34] | 18 | false | not detected |
| ConditionalQA M2 agrees, no gold | 0/0 (undefined) | 0/0 (undefined) | undefined | undefined | 0 | false | not detected |
| ConditionalQA M1 right declines, unanswerable | 5/20 (25.00%) | 6/20 (30.00%) | +5.00 | [-18.38, +27.76] | 20 | false | not detected |
| Base / instrument | Side | n | Supported / total claims (share) | Unsupported-claim answers / n | Unsupported claims | Defects (answers) |
|---|---|---:|---:|---:|---:|---|
| WixQA / M1 | package | 100 | 453/512 (88.48%) | 43/100 | 59 | none 100 |
| WixQA / M1 | codex | 100 | 611/612 (99.84%) | 1/100 | 1 | none 100 |
| WixQA / M2 | package | 100 | 469/524 (89.50%) | 41/100 | 55 | none 99; other 1 |
| WixQA / M2 | codex | 100 | 602/603 (99.83%) | 1/100 | 1 | none 100 |
| ConditionalQA / M1 | package | 100 | 314/384 (81.77%) | 47/100 | 70 | none 94; other 4; repetition 2 |
| ConditionalQA / M1 | codex | 100 | 547/547 (100.00%) | 0/100 | 0 | none 100 |
| ConditionalQA / M2 | package | 100 | 324/390 (83.08%) | 43/100 | 66 | none 95; other 4; repetition 1 |
| ConditionalQA / M2 | codex | 100 | 536/540 (99.26%) | 1/100 | 4 | none 100 |
| aircargo / M1 | package | 100 | 468/482 (97.10%) | 10/100 | 14 | copied_context 2; none 97; other 1 |
| aircargo / M1 | codex | 100 | 561/561 (100.00%) | 0/100 | 0 | none 100 |
| Plan | New requests | Pairs / planned | Agree / n | Quadratic kappa | Two steps apart / n | Passed |
|---|---:|---:|---:|---:|---:|---|
| WixQA M1 | 115 | 15/15 | 15/15 | 1.0000 | 0/15 | true |
| WixQA bridge | 15 | 15/15 | 13/15 | 0.9231 | 0/15 | true |
| WixQA M2 | 115 | 15/15 | 15/15 | 1.0000 | 0/15 | true |
| ConditionalQA M1 | 115 | 15/15 | 15/15 | 1.0000 | 0/15 | true |
| ConditionalQA bridge | 15 | 15/15 | 15/15 | 1.0000 | 0/15 | true |
| ConditionalQA M2 | 115 | 15/15 | 13/15 | 0.5946 | 0/15 | true |
| aircargo M1 | 115 | 15/15 | 15/15 | undefined | 0/15 | true |
| aircargo bridge | 15 | 15/15 | 15/15 | 1.0000 | 0/15 | true |
| Attempts | Redos | Counted out / n | Infrastructure failures | Language mismatches / n | Raw-output mismatches | Stops | Pilot passed |
|---:|---:|---:|---:|---:|---:|---:|---|
| 300 | 0 | 0/300 | 0 | 2/300 | 0 | 0 | true |
| Tasks, n | Median, s | p90, s | Input tokens | Cached input tokens | Output tokens | Reasoning output tokens |
|---:|---:|---:|---:|---:|---:|---:|
| 300 | 25.829 | 34.703 | 5,434,591 | 2,814,208 | 125,074 | 85,302 |
""".splitlines()

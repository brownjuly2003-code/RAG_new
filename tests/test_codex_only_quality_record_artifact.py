"""Read the committed codex-only record again; missing files fail, never skip.

This is a public read, not build() on a fabricated private series. build() needs
state.json (registration binding, pilot, case histories, active_stops and the
judge_stops() marker scan), measurement.json (class/attempt/state bindings), and
the verdict journals. admit_chunk() also needs the private config/root, copy
receipt, corpus/index inventories, detached release copies, env/shim/CLI bytes.
Only the registered codex-only tools and spec are pinned in the current checkout;
other registered product files may change in later slices. Public evidence
inputs are still checked against their receipts. No whole-tree admission claim.

admitted()/validate_frozen()/bind_state() need private receipts, plans/request bodies, runs,
measurement/locations, attempts, capture files, source inputs, references and
bridge source journals/seed prefix. saved_route() needs the private route/session
receipt and installed executable. exports() needs plans, verdict journals,
_vouched admission and NOT_EVIDENCE markers; neither "public export differs from
journal" nor "public case export differs from journal" can be replayed. The
input_sha256.<key>.m1_verdicts_sha256 and bridge_verdicts_sha256 entries bind
private journals: cross-check their public digests, but do not claim to hash the
journals. Private plan hashes likewise have public cross-bindings, not rehashes.
Reply admission, raw retest field agreement, cli_exit reason/retry_at chronology,
raw language/route/capture checks and costs remain recorded observations.

Arm attempts carry every case's terminal classification. Rebuild measured from
them and cross-check the plans receipt's public cases; no measurement fallback.
Rebuild Q from both M1 case exports. For R, reuse reading.r.cases, bind its old
side to registration.r_gate and stage 5 sent_cases, and rerun analyze(). Product
R needs captured contexts and the private corpus to be remeasured. External
clusters come from stage 5v's frozen case labels; clusters()'s external_parts
cluster/stratum recomputation and load_packages()'s dispatch-order check need
private packages/corpus. Check the two public exports' labels against each other.

Rebuild M1, accepted routes, bad/auto, latency ranks, attempts/statuses, tickets,
effort counts, language flags, stops and Ollama counts from public rows. Arm
summaries omit result_utc and each attempt's route: M1 proves the accepted route,
but the extra infrastructure route is only the arm's aggregate observation.
Delivery states are not exported by the arm (here no tickets); preserve that
reading observation. Aircargo identity is rebuilt from public source hashes,
whose correspondence to raw document names cannot be independently reproduced.

The reading ran on Python 3.11.13; Python 3.12+ compensates float sums. Only
weighted kappa and the pilot elapsed-seconds sum use pytest.approx(rel=0,
abs=1e-12). Q/R (every field, including hit_transitions), rounded intervals,
latency ranks, integer counts, plans and decisions compare exactly.
Printed costs compare at their published four-decimal precision.
"""

import hashlib
import importlib.util
import json
import math
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "reports/codex-only-quality"
TOOLS = PUBLIC / "tools"
RECORDS = PUBLIC / "attempt-06"
BASELINE = ROOT / "reports/generator-ceiling/attempt-02"
SPEC = ROOT / "docs/specs/codex-only-quality.md"
CAPSULE = ROOT / "docs/evidence/codex-only-quality-record.md"
SPEC_SHA = "0fe4275734b2a87da2ccef5bcc284ba0cbfe4b6eb0f52a17a071a9209c1adebc"
KEYS = ("wixqa", "conditionalqa", "aircargo")
LABELS = dict(zip((*KEYS, "pooled"), ("WixQA", "ConditionalQA", "aircargo", "Pooled"), strict=True))
GRADES = ("good", "partial_ok", "bad")
FILES = {
    "reports/codex-only-quality/attempt-01/arm-aircargo.json": "196831791de2e0d26380e39b2b9d2e6abe5a1e4f465ce9360289fd2bb88d83a6",
    "reports/codex-only-quality/attempt-01/arm-conditionalqa.json": "fe91f52785dc45db2b84526f358ccbc044887c788feef8c327f4f1521cd1e082",
    "reports/codex-only-quality/attempt-01/arm-wixqa.json": "cc306fd8443272e0cebb670ae02fddc0dac9ee0fcdfc6039df93802d3527497f",
    "reports/codex-only-quality/attempt-01/pilot.json": "d942cbd2a99a1ea523299c5862c5c12ad19a64443a83af97178ea06adbdae19d",
    "reports/codex-only-quality/attempt-01/probe.json": "bf47f405d129e4aa04d2f83aad6555416def28f1760f69bd66bf32b41c419914",
    "reports/codex-only-quality/attempt-01/registration.json": "5e02844038f873a49c7d636d5f4f513d791440b7743ca02f5f751b01caec569f",
    "reports/codex-only-quality/attempt-02/arm-aircargo.json": "7eece228bb82e746b65a9f80d3e3ba1fde2c226058c582eb320030ca5ad895b2",
    "reports/codex-only-quality/attempt-02/arm-conditionalqa.json": "445b673181b52f74124ef670cf0ecbe40ec9c99c756c71522e00c2fb4e927e80",
    "reports/codex-only-quality/attempt-02/arm-wixqa.json": "459be0302a42c2d047122622638eca618fc88600d1509cd040e5c3eaaab4acbc",
    "reports/codex-only-quality/attempt-02/pilot.json": "73b51da4c1d91137387b45cb0f365d0daf88ca42c1aafc2754224fa997c65148",
    "reports/codex-only-quality/attempt-02/probe.json": "6280dd17e1111b08f21b306774ad7f3b8e4f5ebba45840c04a4c058f568270ae",
    "reports/codex-only-quality/attempt-02/registration.json": "07ecced6dbf73252a7bce92f5dd673ddd2d3e565f512cdf64f7ef5180b9b23b6",
    "reports/codex-only-quality/attempt-03/arm-aircargo.json": "ef9ea5f62f5c493472ebbaa7ee9744b0beed82b1d35227187f96b7db9bb098f9",
    "reports/codex-only-quality/attempt-03/arm-conditionalqa.json": "c2ccea46e91f90b9701b34b57008e1437664845f86d0cd573e58d265b4bdf20a",
    "reports/codex-only-quality/attempt-03/arm-wixqa.json": "4de478885319ece85cfb6d01834e97ee5a0332111a6e663d1a105b5921894a39",
    "reports/codex-only-quality/attempt-03/pilot.json": "edade3e953cfb0a858adc8f22ab4850f7dae0eeb9fd54f43e78cc063333ab7b0",
    "reports/codex-only-quality/attempt-03/plans-wixqa.json": "f553769adf3bb74525262c73ef7765f8f6d661f49d262b8b958473cfe9d3eacd",
    "reports/codex-only-quality/attempt-03/probe.json": "1abc0b6e24bb06bec31baff8cdb9299849fe811cc7b5645080f6a33a9769094a",
    "reports/codex-only-quality/attempt-03/registration.json": "dceb93d1f92bed77ee80c8592eadd31330ac364e689a75a4742e4bfdba9e3403",
    "reports/codex-only-quality/attempt-04/arm-aircargo.json": "631166a6d055f7066bc11e22cbb87f11d02c1b7a6d58e3f11e71274b223511bd",
    "reports/codex-only-quality/attempt-04/arm-conditionalqa.json": "0d5a20f7897b092034bf16eb7f2f878aa7e30bbc8c548dceb58d3507cce302e7",
    "reports/codex-only-quality/attempt-04/arm-wixqa.json": "1b6bfac8ffb302207485d2a1b659280334eeec446221afbaa7c9ff7c4e37e014",
    "reports/codex-only-quality/attempt-04/pilot.json": "5f3a68e424885ec220b8c974a1f35ce1543cd8e60247372ded6e2087889f54bc",
    "reports/codex-only-quality/attempt-04/probe.json": "86cf4ff3504aeb58370eb994198a362b0e6dbad6edb08e535b965d644de46300",
    "reports/codex-only-quality/attempt-04/registration.json": "b35d38830096861506720f04286d46b645092f73e966a85b6144f972ac20d1a0",
    "reports/codex-only-quality/attempt-05/arm-aircargo.json": "b264856e092b8874eb4c40c91b25a4bbc97077dc20e445ddf95e1ffc0d84fe84",
    "reports/codex-only-quality/attempt-05/arm-conditionalqa.json": "f67f2e1761b34ac1d8271615f546296b69a2bc42e8f8a03daeb66fd13a8d5161",
    "reports/codex-only-quality/attempt-05/arm-wixqa.json": "b84b511b833a5bae6ff23ab28da0cf188622d14556dfeb16142fed170e8762c4",
    "reports/codex-only-quality/attempt-05/pilot.json": "da9a3c3d455a7e15fb5205119f044874ff27c6eac354c680c476dea0c395941e",
    "reports/codex-only-quality/attempt-05/plans-wixqa.json": "0a8b6f9d41fe070f5da956e5cc2310428e846a132f72b2e4237afceae2abf07d",
    "reports/codex-only-quality/attempt-05/probe.json": "919206488f2657e2797fbdb77a37c2b01b826ae00138a620ecb8a8f95b7a2a9e",
    "reports/codex-only-quality/attempt-05/registration.json": "9048b519a969447da8bb7046ddd724cc8eef18488f5749cc7c5c79e0a3b3db13",
    "reports/codex-only-quality/attempt-06/arm-aircargo.json": "2df874a84a0d95c65bfb262be45872cb48b39e86c88b0e2a17570d83f5375396",
    "reports/codex-only-quality/attempt-06/arm-conditionalqa.json": "25c29309cb456d3179f6031a9b59f9a4032ba051e993f066d1fce358552801e9",
    "reports/codex-only-quality/attempt-06/arm-wixqa.json": "02c8b8492bcc276c894ae957f056089974942375beb770879cb439e4447b7fc7",
    "reports/codex-only-quality/attempt-06/codex-only-aircargo-judge-bridge.json": "6d590823f66c42d5bf3621bc27edeaa3b5ae35ec0dded3e9132fc6b5fd5282f9",
    "reports/codex-only-quality/attempt-06/codex-only-aircargo-judge-m1.cases.jsonl": "9c7f42c5de60e27c86337beb03b0017872bf82736c2861b66c66d443aafc93a3",
    "reports/codex-only-quality/attempt-06/codex-only-aircargo-judge-m1.json": "b417d7922c699a27ba5a1c9eae38bfa906629bd2c839de808fad3f0f680c5f69",
    "reports/codex-only-quality/attempt-06/codex-only-conditionalqa-judge-bridge.json": "3d1f066f6ef84503740c390b496899f5e324f797af2df037881e31d675ed8f64",
    "reports/codex-only-quality/attempt-06/codex-only-conditionalqa-judge-m1.cases.jsonl": "8628c8f9aff69526f01710a7e5bea6a5fed45977e03f2c7b6bad161a904210f4",
    "reports/codex-only-quality/attempt-06/codex-only-conditionalqa-judge-m1.json": "d787c8750aba74ad78c6b2396117d1adfc2fc80c381fb441a0bd057bcf9adc28",
    "reports/codex-only-quality/attempt-06/codex-only-wixqa-judge-bridge.json": "3bced69edfdc70296154845fd0a5392e73c91ac47dbf6986c8a2018fc9a118a8",
    "reports/codex-only-quality/attempt-06/codex-only-wixqa-judge-m1.cases.jsonl": "ed0bed6d79c569988be67cce75a900de9e4c18136aecfae2de9478cf63cf6a21",
    "reports/codex-only-quality/attempt-06/codex-only-wixqa-judge-m1.json": "ee781f7fe6cf5c085ab58f58c1c2e140021c1fc2bc3e64a0370ab0a9ad55e2e6",
    "reports/codex-only-quality/attempt-06/judge-route.json": "c3267d2fd526e37d00563c2184c34b243bd974de36a40beabeb349b8b603dd53",
    "reports/codex-only-quality/attempt-06/pilot.json": "6b8a1f9263e373cf9b465259449beec7f3e256b87e21c8d7072df740db986185",
    "reports/codex-only-quality/attempt-06/plans-aircargo.json": "d63c3429baa8bef9156dec0ee83f661d451a584e00e2ac4dcc42c06126563361",
    "reports/codex-only-quality/attempt-06/plans-conditionalqa.json": "6f45efef6f6c64f7bc818815444ba20609b28f790a3409898c51eb8f1c9a69e5",
    "reports/codex-only-quality/attempt-06/plans-wixqa.json": "6a014483c6c9d1185b7bb3dfeb994e40c5de3b1049bcbfaae635240851007ea5",
    "reports/codex-only-quality/attempt-06/probe.json": "bd5194630e0083d516ae7a752150414c13bc5eb5c2b6aa92b2cb5cdb7384776e",
    "reports/codex-only-quality/attempt-06/reading.json": "2f178d708e46135bac9b4dfeefcdd8fffb377cb8d89ac77cef0afb3e7db33089",
    "reports/codex-only-quality/attempt-06/registration.json": "8d9e2d23dd81af885ea68389787866f8d44cdbc3a72215a75b5d8f7966f163c1",
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recorded_path(name):
    path = PureWindowsPath(name)
    assert not path.drive and not path.root and ".." not in path.parts
    return ROOT.joinpath(*path.parts)


def git_bytes(revision, path):
    result = subprocess.run(
        ["git", "show", f"{revision}:{path.relative_to(ROOT).as_posix()}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, (revision, path)
    return result.stdout


@pytest.fixture(scope="module")
def tools():
    # No collection-time instrument import or I/O; restore generic frozen names.
    before_path, before_modules = sys.path[:], sys.modules.copy()
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("V6_PRODUCT_ROOT", str(ROOT))
        sys.path.insert(0, str(TOOLS))
        try:
            loaded = {}
            for name in (
                "copy_verify",
                "stand_runtime",
                "quality_driver",
                "quality_freeze",
                "quality_read",
            ):
                spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
                assert spec and spec.loader
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
                loaded[name] = module
            reader = loaded["quality_read"]
            common, _ = reader.f.modules(ROOT)
            frozen = common.instruments()
            yield SimpleNamespace(
                reader=reader,
                driver=reader.d,
                freeze=reader.f,
                common=common,
                frozen=frozen,
                judge=common.judge(),
                exporter=frozen.common.final.frozen("export"),
            )
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
    old, new, exports, baseline_exports = {}, {}, {}, {}
    for key in KEYS:
        old[key] = tools.driver.table(rows(BASELINE / f"ceiling-{key}-judge-m1.cases.jsonl"))
        new[key] = tools.driver.table(rows(RECORDS / f"codex-only-{key}-judge-m1.cases.jsonl"))
        baseline_exports[key] = read(BASELINE / f"ceiling-{key}-judge-m1.json")
        exports[key] = {
            metric: read(RECORDS / f"codex-only-{key}-judge-{metric}.json")
            for metric in tools.freeze.METRICS
        }
    return SimpleNamespace(
        record=read(RECORDS / "reading.json"),
        registration=read(RECORDS / "registration.json"),
        receipts={key: read(RECORDS / f"plans-{key}.json") for key in KEYS},
        arms={key: read(RECORDS / f"arm-{key}.json") for key in KEYS},
        pilot=read(RECORDS / "pilot.json"),
        probe=read(RECORDS / "probe.json"),
        route=read(RECORDS / "judge-route.json"),
        old=old,
        new=new,
        exports=exports,
        baseline_exports=baseline_exports,
        stage5=read(ROOT / tools.driver.STAGE5),
    )


def test_public_bytes_and_provenance(artifacts, tools):
    a, d = artifacts, tools.driver
    # Inventory is explicit: retired series do not all have the same files.
    for name, digest in FILES.items():
        path = recorded_path(name)
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, name
        assert data.endswith(b"\n") and b"\r" not in data and not data.startswith(b"\xef\xbb\xbf")
        data.decode("utf-8")
        assert git_bytes("HEAD", path) == data
    reg = a.registration
    assert reg["series"] == a.record["series"] == "attempt-06"
    assert reg["request_ready"] is True and reg["pending"] == []
    assert reg["files"][d.SPEC] == sha(SPEC) == SPEC_SHA
    spec_text = SPEC.read_text(encoding="utf-8")
    assert (
        "paired Newcombe method-10" in spec_text and "cluster-bootstrap 95% intervals" in spec_text
    )
    assert "**M2 is not measured: cost.**" in spec_text
    assert "Amendment, 2026-11-05" in spec_text
    assert reg["release"]["commit"] == "19ecbbb7489f83121dbc3c817ee948a6115bed7d"
    pinned_tools = {
        n: h for n, h in reg["files"].items() if n.startswith("reports/codex-only-quality/tools/")
    }
    assert pinned_tools and "reports/codex-only-quality/tools/quality_read.py" in pinned_tools
    for name, digest in {d.SPEC: SPEC_SHA, **pinned_tools}.items():
        path = recorded_path(name)
        assert sha(path) == digest and git_bytes("HEAD", path) == path.read_bytes()
    inputs = a.record["input_sha256"]
    rebuilt = {
        "registration_sha256": sha(RECORDS / "registration.json"),
        "judge_route_sha256": sha(RECORDS / "judge-route.json"),
    }
    assert a.route["passed"] is True
    assert a.route["executable_sha256"] == reg["private_artifacts"]["claude_executable"]["sha256"]
    for key in KEYS:
        pin = a.receipts[key]
        assert pin["key"] == key and pin["spec_sha256"] == SPEC_SHA
        assert pin["registration_sha256"] == rebuilt["registration_sha256"]
        assert pin["tools"] == reg["files"]
        assert pin["wrapper_sha256"] == reg["files"]["llm/codex_wrapper.txt"]
        for role, provider in reg["providers"][key].items():
            assert provider["provider"] == "codex"
            assert provider["model"] == "gpt-6-astra"
            assert provider["effort"] == ("xhigh" if role == "answer" else "low")
        assert reg["settings"][key]["passed"] is True
        assert reg["settings"][key]["effective"]["llm_provider_profile"] == "codex-only"
        assert set(pin["plans"]) == set(pin["requests"]) == {"m1", "bridge"}
        # Evidence files stay fixed; do not re-pin current product code via tools.
        for name, digest in pin["public_inputs"].items():
            path = recorded_path(name)
            assert sha(path) == digest
            assert git_bytes("HEAD", path) == path.read_bytes()
        old_path = BASELINE / f"ceiling-{key}-judge-m1.json"
        assert pin["old"] == {
            "m1": {
                "record_sha256": sha(old_path),
                "cases_sha256": sha(old_path.with_suffix(".cases.jsonl")),
            }
        }
        for path in (
            old_path,
            old_path.with_suffix(".cases.jsonl"),
            BASELINE / f"plans-{key}.json",
        ):
            assert sha(path) == reg["files"][path.relative_to(ROOT).as_posix()]
            assert git_bytes("HEAD", path) == path.read_bytes()
        old_pin = read(BASELINE / f"plans-{key}.json")
        assert old_pin["plans"]["m1"] == a.baseline_exports[key]["provenance"]["plan_sha256"]
        held = {"receipt_sha256": sha(RECORDS / f"plans-{key}.json"), "plans": pin["plans"]}
        for metric in tools.freeze.METRICS:
            export = a.exports[key][metric]
            provenance = export["provenance"] if metric == "m1" else export
            assert provenance["plan_sha256"] == pin["plans"][metric]
            held[metric + "_export_sha256"] = sha(RECORDS / f"codex-only-{key}-judge-{metric}.json")
            # Cross-bind this private digest; its bytes are not public.
            held[metric + "_verdicts_sha256"] = provenance["verdicts_sha256"]
            if metric == "m1":
                held["m1_cases_sha256"] = sha(RECORDS / f"codex-only-{key}-judge-m1.cases.jsonl")
            else:
                for field in ("plan", "verdicts"):
                    assert (
                        export[f"source_{field}_sha256"]
                        == pin["source"][field]
                        == a.baseline_exports[key]["provenance"][f"{field}_sha256"]
                    )
        rebuilt[key] = held
    assert inputs == rebuilt


def check_stability(export, originals, tools):
    held, exporter, judge = export["retest"], tools.exporter, tools.judge
    pairs, scale = held["pairs_list"], held["scale"]
    assert scale == ["bad", "partial_ok", "good"]
    assert held["planned"] == held["pairs"] == len(pairs) == len(set(held["pairs_ids"]))
    assert len(held["pairs_ids"]) == len(pairs)
    by_item = {r["item_id"]: r for r in originals.values()}
    assert len(by_item) == len(originals)
    for ident, pair in zip(held["pairs_ids"], pairs, strict=True):
        assert len(pair) == 2 and all(v in range(len(scale)) for v in pair)
        assert scale[pair[0]] == by_item[ident]["grade"]
    assert held["agree"] == sum(x == y for x, y in pairs)
    assert held["two_steps_apart"] == sum(abs(x - y) >= 2 for x, y in pairs)
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
    for field, counts in held["field_agreement"].items():
        n = (
            sum(by_item[i]["has_reference"] for i in held["pairs_ids"])
            if field == "reference_counts"
            else len(pairs)
        )
        assert counts["of"] == n and 0 <= counts["agree"] <= n
    assert held["passed"] is True and export["status"] == "counted"
    assert not export.get("request_duration_stop", False)


def check_m1_aggregates(export, data, key, tools):
    per_run = {}
    for label in export["provenance"]["runs"]:
        mine = [r for r in data.values() if r["run"] == label]
        graded = [r for r in mine if not r.get("empty_answer") and not r["missing"]]
        per_run[label] = {
            "answers": len(mine),
            "graded": sum(not r["missing"] for r in mine),
            "missing": sum(r["missing"] for r in mine),
            "classes": {g: sum(r["grade"] == g for r in mine) for g in GRADES},
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
    assert export["per_run"] == per_run
    groups = (
        {cid: [f"cluster:{row['cluster']}"] for cid, row in data.items()}
        if key != "aircargo"
        else None
    )
    assert export["shares"] == tools.exporter.shares(
        {cid: r["grade"] for cid, r in data.items()}, export["retest"]["scale"], groups
    )


def test_all_six_plans_and_exports(artifacts, tools):
    a, plans = artifacts, {}
    for key in KEYS:
        plans[key] = {}
        old, new, pin = a.old[key], a.new[key], a.receipts[key]
        assert len(old) == len(new) == 100 and set(old) == set(new)
        assert tools.frozen.record.counted(a.baseline_exports[key], old)
        for metric, export in a.exports[key].items():
            data = new if metric == "m1" else None
            assert tools.frozen.record.counted(export, data)
            plans[key][metric] = {
                "status": export["status"],
                "retest": export["retest"],
                "missing": export.get("missing", []),
                "requests": pin["requests"][metric],
            }
            assert plans[key][metric]["missing"] == []
            check_stability(export, new if metric == "m1" else old, tools)
            if metric == "bridge":
                assert (
                    pin["requests"][metric] == export["retest"]["planned"] == len(export["pairs"])
                )
                assert (
                    export["retest"]["pairs_ids"]
                    == [p["first"] for p in export["pairs"]]
                    == a.baseline_exports[key]["retest"]["pairs_ids"]
                )
                by_item = {r["item_id"]: r for r in old.values()}
                for pair in export["pairs"]:
                    assert pair["case_id"] == by_item[pair["first"]]["case_id"]
                    assert pair["copy"] == pair["first"] + "-retest"
                    assert pair["old_cli"] in export["admitted_cli"]["old"]
                    assert pair["new_cli"] in export["admitted_cli"]["new"]
                continue
            provenance, replies = export["provenance"], export["replies"]
            assert provenance["route"] == a.exports["wixqa"]["m1"]["provenance"]["route"]
            assert export["plan"] == f"codex-only-{key}-judge-m1"
            assert export["judge"] == "answers" and export["base"] == key
            assert export["questions"] == len(new)
            assert export["missing"] == sorted(cid for cid, r in new.items() if r["missing"]) == []
            assert (
                export["requests_valid"]
                == pin["requests"][metric]
                == sum(not r.get("empty_answer") for r in new.values())
                + export["retest"]["planned"]
            )
            assert provenance["references_sha256"] == pin["references_sha256"]
            assert provenance["references_withheld"] is (key != "aircargo")
            assert provenance["instructions_sha256"] == tools.freeze.INSTRUCTIONS_SHA256
            assert (
                provenance["adapter_sha256"]
                == a.registration["files"]["scripts/chat_answer_judge.py"]
            )
            exporter_path = Path(tools.exporter.__file__).resolve().relative_to(ROOT).as_posix()
            assert provenance["tool_sha256"] == a.registration["files"][exporter_path]
            assert provenance["salt"] == tools.freeze.SALT
            assert provenance["prompt_id"] == "QA_PROMPT_V4"
            assert set(provenance["runs"]) == {r["run"] for r in new.values()}
            assert replies["rows"] == sum(replies["statuses"].values())
            assert replies["statuses"]["valid"] == export["requests_valid"]
            for field in ("models", "admitted_at_reply", "admitted_cli"):
                assert sum(replies[field].values()) == export["requests_valid"]
            assert replies["past_the_limit"] == 0
            assert replies["statuses"] == (
                {"valid": 115, "unavailable": 1} if key == "wixqa" else {"valid": 115}
            )
            assert (
                provenance["route"]["model"],
                provenance["route"]["effort"],
                provenance["route"]["tools"],
            ) == ("claude-opus-5-5", "max", "none")
            for cli in replies["admitted_cli"]:
                assert hashlib.sha256(cli.encode()).hexdigest() == a.route["version_sha256"]
            for cid, row in new.items():
                assert row["grade"] == (
                    "bad" if row.get("empty_answer") else tools.judge.classify(row)
                )
                assert row["has_reference"] is False and row["reference"] == "none"
                assert 1 <= row["admitted_reply"] <= provenance["replies_counted_per_request"]
                assert row["admitted_cli"] in replies["admitted_cli"]
                assert row["prompt_sha256"] == pin["cases"][cid]["prompt_sha256"]
                assert pin["cases"][cid]["package_prompt_sha256"] == old[cid]["prompt_sha256"]
                if key != "aircargo":
                    assert all(row[f] == old[cid][f] for f in ("cluster", "stratum"))
            check_m1_aggregates(export, new, key, tools)
    assert plans == a.record["plans"]
    assert sum(len(p) for p in plans.values()) == 6


@pytest.fixture(scope="module")
def measured(artifacts, tools):
    result = {}
    for key in KEYS:
        arm = artifacts.arms[key]
        assert arm["key"] == key and arm["whole"] is True
        by_case = {}
        for attempt in arm["attempts"]:
            by_case.setdefault(attempt["case_id"], []).append(attempt)
        assert set(by_case) == set(artifacts.old[key])
        result[key] = {}
        for cid, attempts in by_case.items():
            terminal = [r for r in attempts if r["classification"] in tools.driver.TERMINAL]
            assert len(terminal) == 1 and attempts[-1] == terminal[0]
            last = terminal[0]
            assert all(row["classification"] == "infrastructure" for row in attempts[:-1])
            result[key][cid] = {"class": last["classification"]}
            case = artifacts.receipts[key]["cases"][cid]
            assert case["case_id"] == cid and case["class"] == last["classification"]
            assert case["attempt_id"] == last["id"]
        counts = Counter(row["class"] for row in result[key].values())
        counts["pending"] = 100 - len(result[key])
        assert dict(counts) == arm["status_counts"] == {"accepted": 100, "pending": 0}
        assert arm["accepted"] == counts["accepted"]
    return result


def test_read_again_every_q_and_r_field(artifacts, tools, measured):
    a, d, reader = artifacts, tools.driver, tools.reader
    ids = {key: [r["case_id"] for r in a.registration["q_baseline"][key]["cases"]] for key in KEYS}
    baseline = d.q_baseline({k: list(a.old[k].values()) for k in KEYS}, ids)
    assert a.registration["q_baseline"] == baseline
    groups = {
        key: {
            cid: [f"{key}:case:{cid}" if key == "aircargo" else f"{key}:cluster:{row['cluster']}"]
            for cid, row in a.old[key].items()
        }
        for key in KEYS
    }
    before, after, gate_keys = {}, {}, {}
    for key in KEYS[:2]:
        pairs = d.table(a.record["r"]["cases"][key], list(a.old[key]))
        before[key] = {cid: row["baseline"] for cid, row in pairs.items()}
        after[key] = {cid: row["product"] for cid, row in pairs.items()}
        gate = a.registration["r_gate"]["keys"][key]
        held = d.table(gate["cases"], list(a.old[key]))
        assert before[key] == {
            cid: {f: row[f] for f in ("gold", "hit", "fraction", "prompt_sha256")}
            for cid, row in held.items()
        }
        for cid, point in after[key].items():
            assert point["prompt_sha256"] == a.new[key][cid]["prompt_sha256"]
            assert point["derived"] == a.receipts[key]["cases"][cid]["derived"]
            if point["gold"]:
                assert type(point["hit"]) is int and 0 <= point["fraction"] <= 1
        rebuilt = d.r_compare(
            key,
            a.stage5["corpora"][key]["sent_cases"],
            [{"case_id": cid, **point} for cid, point in before[key].items()],
        )
        # saved_prompts_sha256 uses private package order; per-case hashes are public.
        gate_keys[key] = {
            **rebuilt,
            "record_sha256": sha(ROOT / d.STAGE5),
            "saved_prompts_sha256": gate["saved_prompts_sha256"],
        }
    gate = {
        "passed": all(v["passed"] for v in gate_keys.values()),
        "keys": gate_keys,
        "pooled": {
            "hits": sum(v["hits"] for v in gate_keys.values()),
            "n": sum(v["n"] for v in gate_keys.values()),
        },
    }
    reader.match_baselines(a.registration, baseline, gate)
    rebuilt = reader.analyze(a.old, a.new, measured, before, after, groups, ROOT)
    assert rebuilt == {name: a.record[name] for name in ("q", "r")}
    refusals = [
        f"{key}:{metric}"
        for key in KEYS
        for metric, export in a.exports[key].items()
        if not tools.frozen.record.counted(export, a.new[key] if metric == "m1" else None)
    ]
    stopped = bool(
        tools.freeze.active_stops(a.pilot)
        or any(
            e.get("request_duration_stop", False)
            for exports in a.exports.values()
            for e in exports.values()
        )
    )
    assert not refusals and not stopped
    assert reader.fallen(rebuilt["q"]["pooled"]) is False
    assert reader.fallen(rebuilt["r"]["pooled"]) is False
    assert (
        reader.decision(rebuilt["q"]["pooled"], rebuilt["r"]["pooled"], refusals, stopped)
        == a.record["decision"]
        == {
            "row": 3,
            "outcome": "holds (no detected fall)",
            "q_fell": False,
            "r_fell": False,
            "next_step": "Publish these numbers as product quality under codex-only.",
        }
    )
    for metric, parts in {
        "q": {
            "pooled": (300, 268, 279, True, "rises"),
            "wixqa": (100, 87, 89, False, "not detected"),
            "conditionalqa": (100, 81, 92, True, "rises"),
            "aircargo": (100, 100, 98, False, "not detected"),
        },
        "r": {
            "pooled": (180, 125, 116, False, "not detected"),
            "wixqa": (100, 67, 60, False, "not detected"),
            "conditionalqa": (80, 58, 56, False, "not detected"),
        },
    }.items():
        for key, expected in parts.items():
            value = (
                rebuilt[metric]["pooled"] if key == "pooled" else rebuilt[metric]["per_key"][key]
            )
            assert (
                tuple(
                    value[f]
                    for f in ("n", "baseline_count", "product_count", "detected", "direction")
                )
                == expected
            )


def rank_times(attempts):
    values = sorted(a["elapsed_s"] for a in attempts)
    return {
        "n": len(values),
        "median": values[math.ceil(len(values) * 0.5) - 1] if values else None,
        "p90": values[math.ceil(len(values) * 0.9) - 1] if values else None,
    }


def test_public_diagnostics(artifacts, tools, measured):
    a, rebuilt = artifacts, {}
    for key in (*KEYS, "pooled"):
        keys = KEYS if key == "pooled" else (key,)
        attempts = [r for k in keys for r in a.arms[k]["attempts"]]
        terminals = [r for r in attempts if r["classification"] in tools.driver.TERMINAL]
        assert all(r["classification"] == "accepted" for r in terminals)
        assert all(a.new[k][cid]["route"] in ("auto", "human") for k in keys for cid in measured[k])
        n = sum(len(measured[k]) for k in keys)
        efforts = Counter()
        for row in attempts:
            efforts.update(row["calls_by_effort"])
        product = [r for k in keys for r in a.new[k].values()]
        baseline = [r for k in keys for r in a.old[k].values()]
        denominator = sum(r["route"] == "auto" for r in product)
        numerator = sum(r["route"] == "auto" and r["grade"] == "bad" for r in product)
        rebuilt[key] = {
            "m1": {
                side: {g: sum(r["grade"] == g for r in data) for g in GRADES}
                for side, data in (("baseline", baseline), ("product", product))
            },
            "baseline_routes": dict(Counter(tools.driver.safe_route(r["route"]) for r in baseline)),
            "routes": dict(Counter(tools.driver.safe_route(r["route"]) for r in product)),
            "bad_per_auto": {
                "numerator": numerator,
                "denominator": denominator,
                "share": numerator / denominator if denominator else None,
            },
            "tickets": sum(r["ticket_count"] for r in attempts),
            "ticket_sha256": sorted({h for r in attempts for h in r["ticket_sha256"]}),
            "delivery_states": a.record["diagnostics"]["per_key"][key]["delivery_states"],
            "latency": {
                "with_cold": rank_times(terminals),
                "without_cold": rank_times([r for r in terminals if not r["cold"]]),
                "over_180": sum(r["elapsed_s"] > 180 for r in terminals),
            },
            "infrastructure_attempts": sum(
                r["classification"] == "infrastructure" for r in attempts
            ),
            "pending": n - len(terminals),
            "product_failures": sum(r["classification"] == "product_failure" for r in terminals),
            "counted_out": sum(r["classification"] == "counted_out" for r in terminals),
            "calls_by_effort": dict(efforts),
            "calls_per_question": {k: v / n for k, v in efforts.items()},
            "language_mismatches": sum(r["language"].get("match") is False for r in terminals),
        }
        assert rebuilt[key]["delivery_states"] == {} and rebuilt[key]["tickets"] == 0
        for row in terminals:
            language = row["language"]
            for field in ("question_script", "answer_script"):
                counts = language[field]["counts"]
                assert language[field]["script"] == (
                    None if counts["LATIN"] == counts["CYRILLIC"] else max(counts, key=counts.get)
                )
            assert language["match"] is (
                language["question_script"]["script"] is not None
                and language["question_script"]["script"] == language["answer_script"]["script"]
            )
    shared = a.pilot
    for arm in (*a.arms.values(), a.probe):
        for field in (
            "stops",
            "resumes",
            "chunks",
            "retry_at",
            "pilot_seconds",
            "remaining_seconds",
            "forecast_s",
            "slow_threshold_s",
        ):
            assert arm[field] == shared[field]
    for key, arm in a.arms.items():
        assert arm["over_180"] == sum(r["elapsed_s"] > 180 for r in arm["attempts"])
        for field in ("infrastructure_attempts", "language_mismatches"):
            assert arm[field] == rebuilt[key][field]
        extra = Counter(arm["route_counts"])
        extra.subtract(rebuilt[key]["routes"])
        assert {k: v for k, v in extra.items() if v} == ({"other": 1} if key == "aircargo" else {})
    stops = [
        {"code": s["code"], "reason": s["reason"], "resolved": bool(s.get("resolved"))}
        for s in shared["stops"]
    ]
    assert {s["id"] for s in shared["stops"]} == {s["stop_id"] for s in shared["resumes"]}
    assert all(s["resolved"] for s in stops)
    assert {
        "per_key": rebuilt,
        "stop_reasons": stops,
        "ollama_observations": sum(c.get("ollama_observations", 0) for c in shared["chunks"]),
    } == a.record["diagnostics"]
    refused = [c for c in shared["chunks"] if c["exit_code"] == 1]
    assert len(refused) == 1 and refused[0]["refusal_reason"] == "ollama_observed"
    assert refused[0]["changed"] is False
    # changed reports AGENTS hash drift, not measurement mutation. The pre-request
    # refusal/no-answer claim remains the named operator observation below.
    assert sum(c["exit_code"] == 5 for c in shared["chunks"]) == 1
    assert sum(c.get("ollama_observations", 0) for c in shared["chunks"] if c not in refused) == 0
    infrastructure = [
        r for r in a.arms["aircargo"]["attempts"] if r["classification"] == "infrastructure"
    ]
    assert len(infrastructure) == 1 and round(infrastructure[0]["elapsed_s"]) == 442
    assert infrastructure[0]["calls_by_effort"] == {"low": 1}
    assert a.probe["accepted"] is True and len(a.probe["attempts"]) == 1
    assert a.pilot["passed"] is True and a.pilot["step"] == len(a.pilot["selected"]) == 20
    terminal_by_key = {
        k: {r["case_id"]: r for r in a.arms[k]["attempts"] if r["classification"] == "accepted"}
        for k in KEYS
    }
    pilot = [terminal_by_key[r["key"]][r["case_id"]] for r in a.pilot["selected"]]
    assert len({(r["key"], r["case_id"]) for r in a.pilot["selected"]}) == len(pilot)
    assert all(a.new[r["key"]][r["case_id"]]["route"] == "auto" for r in a.pilot["selected"])
    assert a.pilot["pilot_seconds"] == pytest.approx(
        sum(r["elapsed_s"] for r in pilot), rel=0, abs=1e-12
    )
    identity = a.record["aircargo_document_identity"]
    cases = tools.driver.table(identity["cases"], list(a.old["aircargo"]))
    for row in cases.values():
        for field in ("baseline_sources_sha256", "product_sources_sha256"):
            assert row[field] == sorted(set(row[field]))
            assert all(re.fullmatch(r"[0-9a-f]{64}", h) for h in row[field])
        assert row["same"] is (row["baseline_sources_sha256"] == row["product_sources_sha256"])
    assert identity["same"] == sum(r["same"] for r in cases.values()) == 50
    assert identity["n"] == len(cases) == 100


def assert_private_text_absent(value, references, trail=()):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in {"question", "answer", "text", "content", "prompt", "document"}:
                assert not isinstance(item, str), (*trail, key)
            if key.lower() == "reference" and isinstance(item, str):
                assert item in references, (*trail, key)
            assert_private_text_absent(key, references, trail)
            assert_private_text_absent(item, references, (*trail, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            assert_private_text_absent(item, references, (*trail, index))
    elif isinstance(value, str):
        assert not re.search(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|/Users/", value), trail


def test_every_public_file_is_private_text_free(tools):
    paths = {recorded_path(name) for name in FILES}
    paths |= {
        p for p in PUBLIC.rglob("*") if p.suffix in {".json", ".jsonl"} and TOOLS not in p.parents
    }
    for path in sorted(paths):
        for value in rows(path) if path.suffix == ".jsonl" else [read(path)]:
            assert_private_text_absent(
                value, tools.judge.REFERENCE, (path.relative_to(ROOT).as_posix(),)
            )


def test_named_public_history(artifacts):
    for name in FILES:
        path = recorded_path(name)
        assert git_bytes("090dcd1", path) == path.read_bytes()
    for revision, name in (("5a2d2fe", "registration.json"), ("e2845c9", "judge-route.json")):
        path = RECORDS / name
        assert git_bytes(revision, path) == path.read_bytes()
    assert hashlib.sha256(git_bytes("5a2d2fe", SPEC)).hexdigest() == SPEC_SHA
    for key, frozen, exported in zip(
        KEYS, ("32ff420", "86a6ab4", "4bf203a"), ("557c2d0", "cd1223d", "8c0014e"), strict=True
    ):
        path = RECORDS / f"plans-{key}.json"
        assert git_bytes(frozen, path) == path.read_bytes()
        for suffix in ("m1.json", "m1.cases.jsonl", "bridge.json"):
            path = RECORDS / f"codex-only-{key}-judge-{suffix}"
            assert git_bytes(exported, path) == path.read_bytes()
    # These records later acquired the series-wide stops/chunks. Bind their gates.
    for name, current, fields in (
        ("probe.json", artifacts.probe, ("attempts", "accepted", "whole", "route_counts")),
        ("pilot.json", artifacts.pilot, ("selected", "step", "passed")),
    ):
        original = json.loads(git_bytes("2f07562", RECORDS / name))
        assert {f: original[f] for f in fields} == {f: current[f] for f in fields}


# Explicit exceptions: these facts are not derivable from the public JSON files.
# Commit/file bindings are separately checked in test_named_public_history().
EXTERNAL_FACTS = {
    "stage_and_design": "Stage 6 item 0; stage 5v; the 4B selected the saved contexts on the Mac; one unseeded generation per side; one judge; owner decision D11. Source: registered spec and task brief. Method-10/95% are checked against that spec; p90 and the 180 s threshold name registered reader conventions, not measured values.",
    "amendment_and_commits": "Amendment 2026-11-05; registration 5a2d2fe; probe/pilot 2f07562; freezes 32ff420, 86a6ab4, 4bf203a; route e2845c9; exports 557c2d0, cd1223d, 8c0014e; reading 090dcd1. Source: task brief and named Git objects.",
    "reader_execution": "Operator report: Python 3.11.13 in the release venv; exit 0; 337 s; stdout equalled reading.json. Source: task brief.",
    "judge_operation": "Operator report: foreground --budget 600; seven temporary Defender exclusions; one-shot route probe; the one unavailable reply was cli_exit and retried after persisted retry_at. Source: task brief; public exports give the unavailable count, not reason or clock.",
    "retired_series": "Source: docs/operations/session-handoff-2026-11-05-codex-only-measurement.md, Series table; stop codes, two watch refusals, pilot 20/20, 691 s, and historical commits below. Fix 6d4e32f: task brief. Public bytes are pinned, but private cause/timing cannot be replayed.",
    "environment_causes": "Windows Update stalled the infrastructure attempt; Ollama's updater caused the refused chunk; it changed nothing and no answer ran beside Ollama. Source: task brief and handoff. Public chunks bind the refusal, not an independent process replay; changed is an AGENTS-hash flag.",
}

HISTORY_LINES = [
    "attempt-01 (`6f272f2`, `5b7e71f`): code 5 twice, then retired. The watch raced with the owner's other session's short-lived pythons.",
    "attempt-02 (`9530861`): code 2 before any request. The shared capture root still held attempt-01's call records.",
    "attempt-03 (`616798d`): pilot 20/20 (`b366a0c`), WixQA frozen (`53a701a`), then code 2 `outside_codex`. The owner's second Claude session started Codex.",
    "attempt-04 (`e31c8c3`): pilot 20/20 (`215d96a`), then closed by the orchestrator without a stop. Full-tree chunk admission took 691 s; a stat cache followed.",
    "attempt-05 (`97062cd`): pilot (`11c99b5`) and WixQA frozen (`42e559e`), then code 2 on ConditionalQA. The drain's check time became a killed call's end, falsely implying overlap; instrument fix `6d4e32f` left the overlap rule unchanged.",
]


def interval(values):
    return "[" + ", ".join(f"{100 * value:+.2f}" for value in values) + "]"


def paired_line(label, row):
    n = row["n"]
    return (
        f"| {label} | {row['baseline_count']}/{n} ({100 * row['baseline_share']:.2f}%) | "
        f"{row['product_count']}/{n} ({100 * row['product_share']:.2f}%) | "
        f"{100 * row['difference']:+.2f} | {interval(row['newcombe95'])} | "
        f"{interval(row['cluster95'])} | {interval(row['read95'])} | {row['clusters']} | "
        f"{str(row['detected']).lower()} | {row['direction']} |"
    )


def capsule_lines(
    record, registration, exports, pilot, probe, attempts_n, infrastructure_s, refused_n
):
    """Render the capsule from public values; EXTERNAL_FACTS names all exceptions."""
    q, r, diagnostics = record["q"], record["r"], record["diagnostics"]
    per_key = diagnostics["per_key"]
    n = q["pooled"]["n"]
    route = exports["wixqa"]["m1"]["provenance"]["route"]
    cli = next(iter(exports["wixqa"]["m1"]["replies"]["admitted_cli"]))
    header = [
        "| Metric | Baseline hits / n (share) | Product hits / n (share) | Change, pp | Newcombe95, pp | Cluster95, pp | read95, pp | Clusters | Detected | Direction |",
        "|---|---:|---:|---:|---|---|---|---:|---|---|",
    ]
    lines = [
        "# Stage 6 item 0: codex-only quality record",
        "",
        f"The registered outcome is row {record['decision']['row']}: **{record['decision']['outcome']}**.",
        record["decision"]["next_step"],
        "The [registered spec](../specs/codex-only-quality.md) reads falls in Q or R. A detected rise in Q decides nothing beyond no fall.",
        "",
        *header,
        paired_line("Pooled Q", q["pooled"]),
        paired_line("Pooled R", r["pooled"]),
        "",
        f"R's fall of {-100 * r['pooled']['difference']:.2f} percentage points is not detected.",
        f"R hit transitions, n = {r['pooled']['n']}: both hit {r['pooled']['hit_transitions']['both_hit']}, lost {r['pooled']['hit_transitions']['lost']}, gained {r['pooled']['hit_transitions']['gained']}, neither hit {r['pooled']['hit_transitions']['neither_hit']}.",
        "",
        "## What was compared",
        "",
        f"The product path itself answered the same {n} questions, with the same ids and order, on the owner's laptop under `codex-only`.",
        f"Every model call used Codex, profile `cw`, `{registration['providers']['wixqa']['answer']['model']}`. Its own retrieval used query transformation and batched document grading at `low`; the answer used `xhigh` in stage 5v's wrapper.",
        "The baseline is stage 5v's Codex arm: the same model at xhigh answered the package's saved contexts, selected on the Mac by the 4B.",
        "One unseeded generation per side, in-sample, one judge.",
        f"Q is primary: M1 good and context_has_answer true, over all {n} questions. R is gold in the sent context, without a judge, over {r['pooled']['n']} gold-bearing WixQA and ConditionalQA questions.",
        "Differences are product minus baseline. read95 is the envelope of paired Newcombe method-10 and cluster-bootstrap intervals.",
        f"Intervals are 95%, with {q['pooled']['resamples']:,} bootstrap resamples and seed {q['pooled']['seed']}. A fall requires both upper endpoints below zero.",
        "External clusters use frozen stage 5v labels; aircargo uses singleton cases. No denominator shrinks for failures.",
        "",
        "## Per key",
        "",
        *header,
    ]
    for metric, value in (("Q", q), ("R", r)):
        lines.extend(
            paired_line(f"{LABELS[key]} {metric}", value["per_key"][key])
            for key in value["per_key"]
        )
    lines += [
        "",
        "## Printed, deciding nothing",
        "",
        "M1 good includes supported declines. Counts below are good / partial_ok / bad. Routes are accepted answers; other routes are shown separately below.",
        "The acceptance share belongs to the owner (PLAN stage 6). Bad per auto uses all auto answers as its denominator.",
        "",
        "| Key | n | Baseline M1 | Product M1 | Baseline auto / human | Product auto / human | Product bad / auto (share) | Tickets |",
        "|---|---:|---|---|---|---|---|---:|",
    ]
    for key in (*KEYS, "pooled"):
        d = per_key[key]
        count = q["pooled"]["n"] if key == "pooled" else q["per_key"][key]["n"]
        grades = [
            " / ".join(str(d["m1"][side][g]) for g in GRADES) for side in ("baseline", "product")
        ]
        routes = [
            " / ".join(str(d[field].get(route, 0)) for route in ("auto", "human"))
            for field in ("baseline_routes", "routes")
        ]
        bad = d["bad_per_auto"]
        lines.append(
            f"| {LABELS[key]} | {count} | {grades[0]} | {grades[1]} | {routes[0]} | {routes[1]} | {bad['numerator']}/{bad['denominator']} ({100 * bad['share']:.2f}%) | {d['tickets']} |"
        )
    lines += [
        "",
        "Latency is dispatch to product result on her laptop under her load. It differs from stage 5v's task time. Both percentiles use nearest rank.",
        "",
        "| Key | With cold, n | Median / p90, s | Without cold, n | Median / p90, s | Over 180 s / accepted n |",
        "|---|---:|---|---:|---|---|",
    ]
    for key in (*KEYS, "pooled"):
        latency = per_key[key]["latency"]
        cold, warm = latency["with_cold"], latency["without_cold"]
        lines.append(
            f"| {LABELS[key]} | {cold['n']} | {cold['median']:.3f} / {cold['p90']:.3f} | {warm['n']} | {warm['median']:.3f} / {warm['p90']:.3f} | {latency['over_180']}/{cold['n']} |"
        )
    lines += [
        "",
        "| Key | Questions, n | Infrastructure attempts | Pending | Product failures | Counted out | Language mismatches / n |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for key in (*KEYS, "pooled"):
        d = per_key[key]
        count = d["latency"]["with_cold"]["n"]
        lines.append(
            f"| {LABELS[key]} | {count} | {d['infrastructure_attempts']} | {d['pending']} | {d['product_failures']} | {d['counted_out']} | {d['language_mismatches']}/{count} |"
        )
    lines += [
        "",
        "Language mismatch is a script-count heuristic, not a human language grade.",
        "",
        "| Key | Questions, n | Low calls | Low / question | Xhigh calls | Xhigh / question |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key in (*KEYS, "pooled"):
        d = per_key[key]
        lines.append(
            f"| {LABELS[key]} | {d['latency']['with_cold']['n']} | {d['calls_by_effort']['low']} | {d['calls_per_question']['low']:.4f} | {d['calls_by_effort']['xhigh']} | {d['calls_per_question']['xhigh']:.4f} |"
        )
    identity = record["aircargo_document_identity"]
    lines += [
        "",
        f"Aircargo document identity: {identity['same']}/{identity['n']} equal source-id sets against the saved package prompts. This is document identity, not passage equality or gold coverage.",
        f"Ollama observations: {diagnostics['ollama_observations']}, in {refused_n} chunk refused with code 1 `ollama_observed` before its request; it changed nothing.",
        "The operator traced this to Ollama's own updater. It was gone at the check; no answer ran beside Ollama.",
        "",
        "## Retests, bridges and execution",
        "",
        f"The laptop judge was `{route['model']}` through Claude Code CLI `{cli}`, effort `{route['effort']}`, tools `{route['tools']}`, on the frozen safe-mode route.",
        "Safe mode has " + route["session"].removeprefix("safe mode: ") + ".",
        "A bridge compares the judge now with the judge then on the same kept stage 5v Codex answers. It checks judge drift. Retests grade current answers again.",
        "",
        "| Plan | New requests | Pairs / planned | Agree / pairs | Quadratic kappa | Two steps apart / pairs | Passed |",
        "|---|---:|---|---|---|---|---|",
    ]
    for key in KEYS:
        for metric, plan in record["plans"][key].items():
            t = plan["retest"]
            kappa = "undefined" if t["quadratic_kappa"] is None else f"{t['quadratic_kappa']:.4f}"
            lines.append(
                f"| {LABELS[key]} {metric.upper() if metric == 'm1' else metric} | {plan['requests']} | {t['pairs']}/{t['planned']} | {t['agree']}/{t['pairs']} | {kappa} | {t['two_steps_apart']}/{t['pairs']} | {str(t['passed']).lower()} |"
            )
    plans = [plan for per in record["plans"].values() for plan in per.values()]
    missing = sum(len(p["missing"]) for p in plans)
    cost = [exports[k]["m1"]["replies"]["cost_usd"] for k in KEYS]
    valid = sum(exports[k]["m1"]["requests_valid"] for k in KEYS)
    reply_rows = sum(exports[k]["m1"]["replies"]["rows"] for k in KEYS)
    unavailable = sum(exports[k]["m1"]["replies"]["statuses"].get("unavailable", 0) for k in KEYS)
    lines += [
        "",
        f"All {len(plans)} plans and bridges count: {sum(p['requests'] for p in plans)} new requests; missing {missing}. Each M1 has {q['per_key']['wixqa']['n']} originals and {record['plans']['wixqa']['m1']['retest']['planned']} retests; each bridge has {record['plans']['wixqa']['bridge']['retest']['planned']} kept grades and {record['plans']['wixqa']['bridge']['requests']} new grades.",
        "ConditionalQA M1 and aircargo bridge have undefined kappa and pass by agreement. M2 is absent by spec.",
        f"The M1 exports report {valid} valid replies among {reply_rows} logged replies. Their replies.cost_usd sum is ${cost[0]:.4f} + ${cost[1]:.4f} + ${cost[2]:.4f} = ${sum(cost):.4f} (WixQA, ConditionalQA, aircargo). This is the M1 export cost, not total bridge or product cost.",
        f"WixQA M1 had {unavailable} unavailable reply. The operator reports `cli_exit` and a retry after persisted `retry_at`.",
        f"The arm made {attempts_n} question attempts for {n} accepted answers. The probe passed in {probe['attempts'][0]['elapsed_s']:.1f} s; the pilot passed {pilot['step']}/{pilot['step']}, all auto.",
        f"Aircargo's {per_key['aircargo']['infrastructure_attempts']} infrastructure attempt lasted {infrastructure_s:.0f} s. It accounts for the arm's extra other route and its over-180 attempt; accepted answers have {per_key['aircargo']['latency']['over_180']}/{q['per_key']['aircargo']['n']} over 180 s.",
        f"There are {len(diagnostics['stop_reasons'])} series-wide stops, both resolved: "
        + "; ".join(f"code {s['code']} `{s['reason']}`" for s in diagnostics["stop_reasons"])
        + ".",
        "The operator diagnosed a Windows Update stall, resumed with `--resume-infrastructure`, and asked the pending question again; it was accepted. Stops, resumes and chunks repeat in every arm file and must not be added across keys.",
        "Judging used foreground `--budget 600` chunks; each first re-hashed the copy for offline admission. The route receipt came from a one-shot probe in WixQA's first grade chunk.",
        "Operator actions, all reverted after the reading: Claude Code updates held with `DISABLE_AUTOUPDATER`; seven temporary Microsoft Defender exclusions for the release venv, model caches and private roots; High QoS (EcoQoS opt-out), ABOVE_NORMAL priority and P-core affinity for the grade driver; AC power overlay at best performance.",
        "The laptop's firmware caps its E-cores. These environment changes changed no series data or rule.",
        "",
        "## Retired series",
        "",
        "The Series table of the [measurement handoff](../operations/session-handoff-2026-11-05-codex-only-measurement.md) records the history below. Each retirement required a new registration; no answer carried over. The artifact test pins every retained public file.",
        "",
    ]
    for line in HISTORY_LINES:
        lines += [line, ""]
    lines += [
        "## Provenance and limits",
        "",
        f"Spec SHA-256: `{SPEC_SHA}`; amendment 2026-11-05. Registration `5a2d2fe` preceded requests; release `{registration['release']['commit']}` (`19ecbbb`).",
        f"Registration config_sha256: `{registration['config_sha256']}`. copy_receipt_sha256: `{registration['copy_receipt_sha256']}`.",
        "Probe and pilot: `2f07562`. Frozen receipts: `32ff420` (WixQA), `86a6ab4` (ConditionalQA), `4bf203a` (aircargo). Judge route: `e2845c9`.",
        "Exports: `557c2d0` (WixQA), `cd1223d` (ConditionalQA), `8c0014e` (aircargo). Reading: `090dcd1`.",
        "The operator reports the laptop reader used Python 3.11.13 in the release venv, exited 0 in 337 s, and wrote stdout identical to reading.json.",
        "The [reading](../../reports/codex-only-quality/attempt-06/reading.json) holds the result. The [artifact test](../../tests/test_codex_only_quality_record_artifact.py) pins public SHA-256 and LF bytes, registered codex-only tool/spec hashes, receipts and public provenance, and reads Q/R again.",
        "The test docstring names the private checks it cannot repeat. Current product files outside the registered codex-only tools and spec may change in later slices. Public record ids stay in the full repository; raw questions, answers and journals stay private.",
        "",
        *record["limits"],
        f"The one judge was `{route['model']}`. Overall M1 can reward a supported decline, so Q and R expose different losses.",
    ]
    return lines


def test_every_capsule_number_is_bound(artifacts):
    a = artifacts
    infrastructure = [
        r for r in a.arms["aircargo"]["attempts"] if r["classification"] == "infrastructure"
    ]
    assert len(infrastructure) == 1
    expected = capsule_lines(
        a.record,
        a.registration,
        a.exports,
        a.pilot,
        a.probe,
        sum(len(arm["attempts"]) for arm in a.arms.values()),
        infrastructure[0]["elapsed_s"],
        sum(c["exit_code"] == 1 for c in a.pilot["chunks"]),
    )
    assert CAPSULE.read_text(encoding="utf-8") == "\n".join(expected) + "\n"
    # Pin only printed numbers, not a second copy of the reading or case lists.
    assert [line for line in expected if re.search(r"\d", line)] == PRINTED_NUMERIC_LINES
    assert EXTERNAL_FACTS.keys() == {
        "stage_and_design",
        "amendment_and_commits",
        "reader_execution",
        "judge_operation",
        "retired_series",
        "environment_causes",
    }


PRINTED_NUMERIC_LINES = [
    "# Stage 6 item 0: codex-only quality record",
    "The registered outcome is row 3: **holds (no detected fall)**.",
    "| Metric | Baseline hits / n (share) | Product hits / n (share) | Change, pp | Newcombe95, pp | "
    "Cluster95, pp | read95, pp | Clusters | Detected | Direction |",
    "| Pooled Q | 268/300 (89.33%) | 279/300 (93.00%) | +3.67 | [+0.08, +7.44] | [+0.34, +7.06] | "
    "[+0.08, +7.44] | 237 | true | rises |",
    "| Pooled R | 125/180 (69.44%) | 116/180 (64.44%) | -5.00 | [-12.42, +2.50] | [-12.57, +2.59] | "
    "[-12.57, +2.59] | 117 | false | not detected |",
    "R's fall of 5.00 percentage points is not detected.",
    "R hit transitions, n = 180: both hit 97, lost 28, gained 19, neither hit 36.",
    "The product path itself answered the same 300 questions, with the same ids and order, on the "
    "owner's laptop under `codex-only`.",
    "Every model call used Codex, profile `cw`, `gpt-6-astra`. Its own retrieval used query "
    "transformation and batched document grading at `low`; the answer used `xhigh` in stage 5v's "
    "wrapper.",
    "The baseline is stage 5v's Codex arm: the same model at xhigh answered the package's saved "
    "contexts, selected on the Mac by the 4B.",
    "Q is primary: M1 good and context_has_answer true, over all 300 questions. R is gold in the sent "
    "context, without a judge, over 180 gold-bearing WixQA and ConditionalQA questions.",
    "Differences are product minus baseline. read95 is the envelope of paired Newcombe method-10 and "
    "cluster-bootstrap intervals.",
    "Intervals are 95%, with 10,000 bootstrap resamples and seed 20261001. A fall requires both upper "
    "endpoints below zero.",
    "External clusters use frozen stage 5v labels; aircargo uses singleton cases. No denominator "
    "shrinks for failures.",
    "| Metric | Baseline hits / n (share) | Product hits / n (share) | Change, pp | Newcombe95, pp | "
    "Cluster95, pp | read95, pp | Clusters | Detected | Direction |",
    "| WixQA Q | 87/100 (87.00%) | 89/100 (89.00%) | +2.00 | [-4.87, +9.05] | [-4.08, +8.25] | "
    "[-4.87, +9.05] | 77 | false | not detected |",
    "| ConditionalQA Q | 81/100 (81.00%) | 92/100 (92.00%) | +11.00 | [+2.90, +19.55] | [+3.96, "
    "+18.28] | [+2.90, +19.55] | 60 | true | rises |",
    "| aircargo Q | 100/100 (100.00%) | 98/100 (98.00%) | -2.00 | [-7.00, +1.97] | [-5.00, +0.00] | "
    "[-7.00, +1.97] | 100 | false | not detected |",
    "| WixQA R | 67/100 (67.00%) | 60/100 (60.00%) | -7.00 | [-17.02, +3.25] | [-18.10, +3.57] | "
    "[-18.10, +3.57] | 77 | false | not detected |",
    "| ConditionalQA R | 58/80 (72.50%) | 56/80 (70.00%) | -2.50 | [-13.59, +8.66] | [-13.75, +8.75] "
    "| [-13.75, +8.75] | 40 | false | not detected |",
    "M1 good includes supported declines. Counts below are good / partial_ok / bad. Routes are "
    "accepted answers; other routes are shown separately below.",
    "The acceptance share belongs to the owner (PLAN stage 6). Bad per auto uses all auto answers as "
    "its denominator.",
    "| Key | n | Baseline M1 | Product M1 | Baseline auto / human | Product auto / human | Product "
    "bad / auto (share) | Tickets |",
    "| WixQA | 100 | 92 / 6 / 2 | 96 / 3 / 1 | 86 / 14 | 96 / 4 | 0/96 (0.00%) | 0 |",
    "| ConditionalQA | 100 | 92 / 8 / 0 | 97 / 3 / 0 | 85 / 15 | 93 / 7 | 0/93 (0.00%) | 0 |",
    "| aircargo | 100 | 100 / 0 / 0 | 98 / 0 / 2 | 98 / 2 | 96 / 4 | 2/96 (2.08%) | 0 |",
    "| Pooled | 300 | 284 / 14 / 2 | 291 / 6 / 3 | 269 / 31 | 285 / 15 | 2/285 (0.70%) | 0 |",
    "Latency is dispatch to product result on her laptop under her load. It differs from stage 5v's "
    "task time. Both percentiles use nearest rank.",
    "| Key | With cold, n | Median / p90, s | Without cold, n | Median / p90, s | Over 180 s / "
    "accepted n |",
    "| WixQA | 100 | 60.797 / 71.796 | 86 | 59.766 / 68.641 | 0/100 |",
    "| ConditionalQA | 100 | 70.844 / 83.469 | 85 | 71.344 / 83.734 | 0/100 |",
    "| aircargo | 100 | 69.469 / 88.078 | 83 | 69.125 / 88.078 | 0/100 |",
    "| Pooled | 300 | 66.016 / 83.281 | 254 | 65.703 / 83.281 | 0/300 |",
    "| WixQA | 100 | 0 | 0 | 0 | 0 | 0/100 |",
    "| ConditionalQA | 100 | 0 | 0 | 0 | 0 | 0/100 |",
    "| aircargo | 100 | 1 | 0 | 0 | 0 | 3/100 |",
    "| Pooled | 300 | 1 | 0 | 0 | 0 | 3/300 |",
    "| WixQA | 100 | 200 | 2.0000 | 100 | 1.0000 |",
    "| ConditionalQA | 100 | 200 | 2.0000 | 100 | 1.0000 |",
    "| aircargo | 100 | 201 | 2.0100 | 100 | 1.0000 |",
    "| Pooled | 300 | 601 | 2.0033 | 300 | 1.0000 |",
    "Aircargo document identity: 50/100 equal source-id sets against the saved package prompts. This "
    "is document identity, not passage equality or gold coverage.",
    "Ollama observations: 2, in 1 chunk refused with code 1 `ollama_observed` before its request; it "
    "changed nothing.",
    "The laptop judge was `claude-opus-5-5` through Claude Code CLI `2.1.312`, effort `max`, tools "
    "`none`, on the frozen safe-mode route.",
    "A bridge compares the judge now with the judge then on the same kept stage 5v Codex answers. It "
    "checks judge drift. Retests grade current answers again.",
    "| WixQA M1 | 115 | 15/15 | 15/15 | 1.0000 | 0/15 | true |",
    "| WixQA bridge | 15 | 15/15 | 15/15 | 1.0000 | 0/15 | true |",
    "| ConditionalQA M1 | 115 | 15/15 | 15/15 | undefined | 0/15 | true |",
    "| ConditionalQA bridge | 15 | 15/15 | 15/15 | 1.0000 | 0/15 | true |",
    "| aircargo M1 | 115 | 15/15 | 15/15 | 1.0000 | 0/15 | true |",
    "| aircargo bridge | 15 | 15/15 | 15/15 | undefined | 0/15 | true |",
    "All 6 plans and bridges count: 390 new requests; missing 0. Each M1 has 100 originals and 15 "
    "retests; each bridge has 15 kept grades and 15 new grades.",
    "ConditionalQA M1 and aircargo bridge have undefined kappa and pass by agreement. M2 is absent by "
    "spec.",
    "The M1 exports report 345 valid replies among 346 logged replies. Their replies.cost_usd sum is "
    "$14.9158 + $13.8187 + $14.1262 = $42.8607 (WixQA, ConditionalQA, aircargo). This is the M1 "
    "export cost, not total bridge or product cost.",
    "WixQA M1 had 1 unavailable reply. The operator reports `cli_exit` and a retry after persisted "
    "`retry_at`.",
    "The arm made 301 question attempts for 300 accepted answers. The probe passed in 19.9 s; the "
    "pilot passed 20/20, all auto.",
    "Aircargo's 1 infrastructure attempt lasted 442 s. It accounts for the arm's extra other route "
    "and its over-180 attempt; accepted answers have 0/100 over 180 s.",
    "There are 2 series-wide stops, both resolved: code 5 `verified_stop_failed`; code 5 "
    "`state_stop`.",
    "Judging used foreground `--budget 600` chunks; each first re-hashed the copy for offline "
    "admission. The route receipt came from a one-shot probe in WixQA's first grade chunk.",
    "The Series table of the [measurement handoff]"
    "(../operations/session-handoff-2026-11-05-codex-only-measurement.md) records the history below. "
    "Each retirement required a new registration; no answer carried over. The artifact test pins "
    "every retained public file.",
    "attempt-01 (`6f272f2`, `5b7e71f`): code 5 twice, then retired. The watch raced with the owner's "
    "other session's short-lived pythons.",
    "attempt-02 (`9530861`): code 2 before any request. The shared capture root still held "
    "attempt-01's call records.",
    "attempt-03 (`616798d`): pilot 20/20 (`b366a0c`), WixQA frozen (`53a701a`), then code 2 "
    "`outside_codex`. The owner's second Claude session started Codex.",
    "attempt-04 (`e31c8c3`): pilot 20/20 (`215d96a`), then closed by the orchestrator without a stop. "
    "Full-tree chunk admission took 691 s; a stat cache followed.",
    "attempt-05 (`97062cd`): pilot (`11c99b5`) and WixQA frozen (`42e559e`), then code 2 on "
    "ConditionalQA. The drain's check time became a killed call's end, falsely implying overlap; "
    "instrument fix `6d4e32f` left the overlap rule unchanged.",
    "Spec SHA-256: `0fe4275734b2a87da2ccef5bcc284ba0cbfe4b6eb0f52a17a071a9209c1adebc`; amendment "
    "2026-11-05. Registration `5a2d2fe` preceded requests; release "
    "`19ecbbb7489f83121dbc3c817ee948a6115bed7d` (`19ecbbb`).",
    "Registration config_sha256: `eb700c2d78f6f986d852b59d4d42b67e3701022109db3209b87a6360447e3dfe`. "
    "copy_receipt_sha256: `6d2798fdaa4e2d75d23246f094f836917eab34a0247c348a3e45bd5abb6c6332`.",
    "Probe and pilot: `2f07562`. Frozen receipts: `32ff420` (WixQA), `86a6ab4` (ConditionalQA), "
    "`4bf203a` (aircargo). Judge route: `e2845c9`.",
    "Exports: `557c2d0` (WixQA), `cd1223d` (ConditionalQA), `8c0014e` (aircargo). Reading: `090dcd1`.",
    "The operator reports the laptop reader used Python 3.11.13 in the release venv, exited 0 in 337 "
    "s, and wrote stdout identical to reading.json.",
    "The [reading](../../reports/codex-only-quality/attempt-06/reading.json) holds the result. The "
    "[artifact test](../../tests/test_codex_only_quality_record_artifact.py) pins public SHA-256 and "
    "LF bytes, registered codex-only tool/spec hashes, receipts and public provenance, and reads Q/R "
    "again.",
    "In-sample; one unseeded generation per side; one judge; no human grades (D11).",
    "M2 absent; laptop under owner load; no detected fall does not establish equivalence.",
    "The one judge was `claude-opus-5-5`. Overall M1 can reward a supported decline, so Q and R expose "
    "different losses.",
]

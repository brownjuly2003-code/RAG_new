"""Check the published screening of the generators below 7B on the production Mac.

On 2026-10-14 a clean clone of `86df582` on deproject-mac ran `scripts/generator_benchmark.py`
on the C.1 contract — one run at seed 42, no self-grading — for qwen2.5:1.5b, qwen3:1.7b and
Qwen3-4B-Instruct-2507, driven by the tools kept beside the record (`tools/`, the progress log
times every step). The tag qwen3:4b, a thinking-only model, ran its 1- and 5-case steps and was
replaced (`docs/specs/small-generator-screening.md`, amendment). The one judge then graded the
answers of these three and of C.1a and C.1b on 30 shared cases (`judge/`; its stream, stopped
once for low memory on the laptop, finished on 2026-10-15), and on 2026-10-15 graded all 100
cases of qwen3:1.7b, Qwen3-4B-Instruct, C.1a and C.1b under a second plan (`judge-100/`,
registered before its first request), reusing the verdicts of the requests both plans hold.
Nothing here needs a model, the network or the Mac: the test pins the bytes, rebuilds both
plans — with the checks of all 100 answers — from the tracked inputs and their summaries from
the verdicts, and finds the published numbers in the evidence rows.
"""

from __future__ import annotations

import gzip
import hashlib
import itertools
import json
import math
import shutil
from pathlib import Path

from scripts import generator_answer_judge as judge

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "reports/generator-screen/86df582"
# sha256, size and path of every published file, LF line endings (.gitattributes).
PINS = """
82c5b45645c5129515b0a4137cbdaba83cdae80db1fb8cfc44bcfd19b81ad2be 3492925 judge-100/plan.json
55ef98a0aab869394ab5d7e00b8fba2ab709198a12bb390c457e6e3e74861a52 143 judge-100/refusals.log
218881044ed31263cc79a2403fe42aef0e59a28ee9858b632e1fa9137ae36aa3 4156 judge-100/summary.json
a3ab8425a701299b40eccc6b732cc90e68aba624f2cf90b45a82200b854a287a 106 judge-100/tools/no-user-plugins.json
1d629940b24e0450de04a95efcbaf7fc3b6d4a64c549fffca5fd15579d0d2c01 2129 judge-100/tools/run100_logged.py
c63b24037d67c01dc281de1dd15ee4d7195b6f00ba7681398ebe63a0d9bf63ab 594649 judge-100/verdicts.jsonl
051aa629af4ca6cab9c2e8df3c2977b0bf6bcd86b0d59946d22d8a838bf95cc8 1366796 judge/plan.json
f3eea3be82a0de4b8aeb9aadf8a8a242016831c1651e170beda752a1d1e1ca88 5058 judge/summary.json
5defc76a4bba8d220c83935d2daa6809c738e73c77f32bbdf3c1d09d306af257 231764 judge/verdicts.jsonl
120a8d430054ae42569abdc2481f1f46b555b5941c45997643b3f5dd68191e4a 2645 progress.log
34ba5ebe50a71f44c3e07a50385ecdb9081f53663623364310f8d583bb227f3a 464023 reports/gs-qwen25-1p5b-n100-phase-c-generator-benchmark.json
d943fb960363b521bfc0194bb54a810a2eabc7acc935cb34d7de74dab89bdfbb 373894 reports/gs-qwen3-1p7b-n100-phase-c-generator-benchmark.json
c7cb4a219ecee7aa4e9d156f5108d7964b7fd28a223a5d577736c003db5d9ba7 458386 reports/gs-qwen3-4b-instruct-n100-phase-c-generator-benchmark.json
c8ecb998406f4cbbf8d1a4d879b9e7da811a267420ce033818122b2641716627 14041 reports/gs-qwen3-4b-n1-phase-c-generator-benchmark.json
13ce5b099285e431529b9c227869a781c6ad605279c605d9f0b44dac697c16b6 54717 reports/gs-qwen3-4b-n5-phase-c-generator-benchmark.json
9332ca664a9fe593c1b37d59ab21328aa3f3ba56ae4bc9ae0c1ea77fd9ada4ba 1857 tools/check_step.py
d7613427fca529e0d3415b1d1730776b31b489b554886a41e0d6f559f3ae6a54 1043 tools/registry_tags.py
14732dceb9cad54b940af85e683030303e89d144f69ab5d15831d2fd205bfa21 1150 tools/run_screen.sh
4e5d7baaaaed1fc67fce55e0bee27287afcc4a3c6648adfb7f41e2ff977c9d48 2238 tools/run_screen2.sh
6d5fde575cca25af0c5865c1c10893aa10d574cad9126e16fa63f1a493f31c81 507 tools/watch.sh
"""
FILES = {
    name: (sha256, int(size)) for sha256, size, name in map(str.split, PINS.strip().splitlines())
}
CODE_SHA = "86df58272ddaf8f89f7b5ed6c5209703564169b0"
DATASET = ROOT / "evaluation/curated_cases_aircargo.jsonl"
DATASET_SHA256 = "3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720"
CONTEXTS_GZ = ROOT / "evaluation/c1a-c06bdf5-phase-c-C-candidates.json.gz"
CONTEXTS_SHA256 = "91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10"
# Judge name: report, Ollama tag, model digest, the think field sent.
SCREENED = {
    "qwen2.5-1.5b": (
        "reports/gs-qwen25-1p5b-n100-phase-c-generator-benchmark.json",
        "qwen2.5:1.5b",
        "65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b",
        None,
    ),
    "qwen3-1.7b": (
        "reports/gs-qwen3-1p7b-n100-phase-c-generator-benchmark.json",
        "qwen3:1.7b",
        "8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7",
        False,
    ),
    "qwen3-4b-instruct": (
        "reports/gs-qwen3-4b-instruct-n100-phase-c-generator-benchmark.json",
        "qwen3:4b-instruct-2507-q4_K_M",
        "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0",
        False,
    ),
}
REFERENCE = {
    "qwen2.5-7b": ROOT / "evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json",
    "qwen3-8b": ROOT / "evaluation/c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json",
}
THINKING_STEPS = {
    "reports/gs-qwen3-4b-n1-phase-c-generator-benchmark.json": 1,
    "reports/gs-qwen3-4b-n5-phase-c-generator-benchmark.json": 5,
}
THINKING_DIGEST = "359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7"
# The extension: its generators, small first, and its sample.
EXTENDED = ("qwen3-1.7b", "qwen3-4b-instruct", "qwen2.5-7b", "qwen3-8b")
EXTENSION_CASES = 100
# Its rows without a verdict, each request sent again: the 70th request sent, refused twice when
# a plugin of the CLI's user configuration loaded into the session (the spec's amendment of the
# extension), and a request in flight when a chunk's time budget ran out.
WITHOUT_VERDICT = [
    ("90cb10c3d563f1da", "cli_response"),
    ("90cb10c3d563f1da", "cli_response"),
    ("5c20ead02f1e39b1", "cli_exit"),
]
Z95 = 1.959963984540054


def load(name: str) -> dict:
    return json.loads((RECORD / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report_paths() -> dict[str, Path]:
    return {**{name: RECORD / spec[0] for name, spec in SCREENED.items()}, **REFERENCE}


def verdicts(directory: str = "judge") -> list[dict]:
    text = (RECORD / directory / "verdicts.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


def evidence_row(record: str = "") -> str:
    index = (ROOT / "EVIDENCE_INDEX.md").read_text(encoding="utf-8")
    link = f"](reports/generator-screen/86df582/{record})"
    (row,) = [line for line in index.splitlines() if link in line]
    return row


def contexts_file(tmp_path: Path) -> Path:
    contexts = tmp_path / "contexts.json"
    with gzip.open(CONTEXTS_GZ, "rb") as source, contexts.open("wb") as target:
        shutil.copyfileobj(source, target)
    assert sha256(contexts) == CONTEXTS_SHA256
    return contexts


def wilson(good: int, n: int) -> tuple[float, float]:
    share = good / n
    centre = (share + Z95**2 / (2 * n)) / (1 + Z95**2 / n)
    half = Z95 * math.sqrt(share * (1 - share) / n + Z95**2 / (4 * n * n)) / (1 + Z95**2 / n)
    return centre - half, centre + half


def sign_test(only_a: int, only_b: int) -> float:
    n = only_a + only_b
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(min(only_a, only_b) + 1)) / 2**n)


def good_answers(plan: dict, rows: list[dict]) -> dict[tuple[str, str], bool]:
    first: dict[str, dict] = {}
    for row in rows:
        if row["status"] == "valid":
            first.setdefault(row["item_id"], judge.parse_verdict(row["raw_text"]))
    return {
        (item["generator"], item["case_id"]): item["item_id"] in first
        and judge.classify(first[item["item_id"]]) == "good"
        for item in plan["items"]
        if "retest_of" not in item
    }


def test_published_files_are_pinned() -> None:
    published = {
        path.relative_to(RECORD).as_posix() for path in RECORD.rglob("*") if path.is_file()
    }
    assert published == set(FILES), "every published file is pinned, and only those"
    for name, (digest, size) in FILES.items():
        data = (RECORD / name).read_bytes()
        assert (hashlib.sha256(data).hexdigest(), len(data)) == (digest, size), name


def test_each_screened_generator_ran_the_registered_contract() -> None:
    for name, (path, tag, digest, think) in SCREENED.items():
        report = load(path)
        provenance = report["provenance"]
        assert provenance["code_sha"] == CODE_SHA and provenance["code_tree_clean"] is True
        assert provenance["dataset_sha256"] == DATASET_SHA256
        assert provenance["contexts_sha256"] == CONTEXTS_SHA256
        assert provenance["ollama_model"] == tag, name
        assert provenance["ollama_model_digest"] == digest, name
        assert provenance["ollama_think"] is think and provenance["config"]["think"] is think
        config = provenance["config"]
        assert config["prompt_version"] == "aircargo-context-only-ru-v1"
        assert (config["temperature"], config["seed_base"], config["num_ctx"]) == (0.0, 42, 4096)
        assert (config["num_predict"], config["context_chars"]) == (384, 6000)
        assert config["llm_judge"] is False and config["runs"] == config["required_runs"] == 1
        assert config["allow_short_contexts"] is False and config["top_k_override"] is None
        (run,) = report["runs"]
        assert (run["seed"], run["num_cases"], run["failed_cases"]) == (42, 100, 0)
        assert report["evidence_class"] == "measured", name
        assert all(case["ollama_timing"]["eval_duration"] for case in run["cases"]), name


def test_the_thinking_tag_wrote_its_reasoning_instead_of_an_answer() -> None:
    for path, cases in THINKING_STEPS.items():
        report = load(path)
        provenance = report["provenance"]
        assert provenance["ollama_model"] == "qwen3:4b"
        assert provenance["ollama_model_digest"] == THINKING_DIGEST
        assert provenance["ollama_think"] is False and provenance["code_sha"] == CODE_SHA
        assert report["evidence_class"] == "not_evidence", "a step is not the 100-case run"
        (run,) = report["runs"]
        assert run["num_cases"] == cases
        for case in run["cases"]:
            assert case["ollama_timing"]["eval_count"] == 384, "stopped at num_predict"
            assert case["answer"].startswith("Хорошо, мне нужно ответить на вопрос пользователя")
    total = sum(THINKING_STEPS.values())
    assert f"{total} of {total} at the 384-token cap" in evidence_row()


def test_the_judge_plan_is_rebuilt_from_the_tracked_inputs(tmp_path: Path) -> None:
    contexts = contexts_file(tmp_path)
    paths = report_paths()
    reports = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in paths.items()}
    plan = judge.build_plan(
        reports,
        dataset_path=DATASET,
        contexts_path=contexts,
        report_sha256={name: sha256(path) for name, path in paths.items()},
    )
    assert plan == load("judge/plan.json")
    assert len(plan["items"]) == len(plan["generators"]) * judge.SAMPLE_SIZE + judge.RETEST_SIZE
    assert not any(item.get("empty_answer") for item in plan["items"])


def test_the_summary_is_derived_from_the_verdicts() -> None:
    plan = load("judge/plan.json")
    rows = verdicts()
    # summarize() takes a verdict only from a clean session's record and for a planned request.
    summary = judge.summarize(plan, rows)
    assert summary == load("judge/summary.json")
    assert summary["missing"] == 0 and summary["checks"] == plan["checks"]
    planned = [item["item_id"] for item in plan["items"] if "message" in item]
    assert sorted(row["item_id"] for row in rows) == sorted(planned), "one verdict per request"
    assert all(row["status"] == "valid" and row["attempt"] == 1 for row in rows)
    assert {row["model"] for row in rows} == {"claude-opus-5-5"}
    assert set(summary["generators"]) == set(SCREENED) | set(REFERENCE)
    for name, generator in summary["generators"].items():
        assert generator["items"] == generator["graded"] == judge.SAMPLE_SIZE, name
    assert summary["retest"]["pairs"] == judge.RETEST_SIZE


def test_the_evidence_row_publishes_the_checks_of_all_answers() -> None:
    row = evidence_row()
    plan = load("judge/plan.json")
    checks = plan["checks"]
    for name in SCREENED:
        assert checks[name]["cases"] == 100 and checks[name]["generation_failed"] == 0, name
        assert checks[name]["latency_includes_self_judging"] is False, name
    small, large = list(SCREENED), list(REFERENCE)

    def joined(names: list[str], key: str, form: str) -> str:
        return " / ".join(format(checks[name][key], form) for name in names)

    assert (
        f"keyword recall of the answers {joined(small, 'answer_keyword_recall', '.3f')} for "
        f"`qwen2.5-1.5b` / `qwen3-1.7b` / `qwen3-4b-instruct` against "
        f"{joined(large, 'answer_keyword_recall', '.3f')} for C.1a / C.1b"
    ) in row
    assert f"the contexts hold {plan['context_keyword_recall']:.3f}" in row
    assert (
        f"NLI faithfulness, not ranked on, {joined(small, 'nli_faithfulness', '.3f')} against "
        f"{joined(large, 'nli_faithfulness', '.3f')}"
    ) in row
    assert f"generation median {joined(small, 'median_latency_s', '.1f')} s a case" in row
    reading = " / ".join(str(round(checks[name]["median_prompt_tokens_per_s"])) for name in small)
    assert (
        f"reading {reading} tokens/s, writing {joined(small, 'median_output_tokens_per_s', '.1f')}"
        in row
    )


def test_the_evidence_row_publishes_the_judge() -> None:
    row = evidence_row()
    summary = load("judge/summary.json")
    generators = summary["generators"]
    for name, generator in generators.items():
        classes = generator["classes"]
        assert f"`{name}` {classes['good']}/{classes['partial_ok']}/{classes['bad']}" in row, name

    def rates(names: list[str]) -> str:
        return " / ".join(f"{generators[name]['supported_claim_rate']:.2f}" for name in names)

    assert f"supported claims {rates(list(SCREENED))} against {rates(list(REFERENCE))}" in row
    retest, context = summary["retest"], summary["context_has_answer"]
    assert f"the same class on {retest['same_class']} of {retest['pairs']} retests" in row
    assert (
        "the same `context_has_answer` for all five answers in "
        f"{context['same_for_every_answer']} of {context['cases']} cases"
    ) in row


def test_the_row_reads_the_judge_as_the_plan_registered() -> None:
    # Thirty cases leave gaps of five good answers or fewer unresolved; if the leading small
    # generator comes within five of C.1a or C.1b, the judge extends to all 100 cases.
    row = evidence_row()
    generators = load("judge/summary.json")["generators"]
    good = {name: generator["classes"]["good"] for name, generator in generators.items()}
    apart = [(a, b) for a, b in itertools.combinations(good, 2) if abs(good[a] - good[b]) > 5]
    assert apart == [("qwen2.5-1.5b", "qwen3-4b-instruct")]
    assert "the only wider one, `qwen2.5-1.5b` against `qwen3-4b-instruct` (16 vs 23)" in row
    # Even that gap is a lead, not a settled order: the cases where only one of the two is good.
    plan = load("judge/plan.json")
    first: dict[str, dict] = {}
    for verdict_row in verdicts():
        first.setdefault(verdict_row["item_id"], judge.parse_verdict(verdict_row["raw_text"]))
    is_good = {
        (item["generator"], item["case_id"]): item["item_id"] in first
        and judge.classify(first[item["item_id"]]) == "good"
        for item in plan["items"]
        if "retest_of" not in item
    }
    cases = {case for _, case in is_good}
    only = [
        sum(is_good[a, case] and not is_good[b, case] for case in cases)
        for a, b in (apart[0], apart[0][::-1])
    ]
    assert only == [1, 8]
    exact_p = 2 * sum(math.comb(9, k) for k in range(2)) / 2**9
    assert round(exact_p, 2) == 0.04
    assert "1 against 8 discordant cases, exact p ≈ 0.04 before correcting for ten pairs" in row
    leader = max(SCREENED, key=lambda name: good[name])
    assert leader == "qwen3-4b-instruct"
    assert any(abs(good[leader] - good[name]) <= 5 for name in REFERENCE)
    assert "extends the judge to all 100 cases of the generators concerned" in row


def test_the_extension_plan_is_rebuilt_from_the_tracked_inputs(tmp_path: Path) -> None:
    paths = {name: report_paths()[name] for name in EXTENDED}
    plan = judge.build_plan(
        {name: json.loads(path.read_text(encoding="utf-8")) for name, path in paths.items()},
        dataset_path=DATASET,
        contexts_path=contexts_file(tmp_path),
        report_sha256={name: sha256(path) for name, path in paths.items()},
        sample_size=EXTENSION_CASES,
    )
    assert plan == load("judge-100/plan.json")
    assert plan["sample"][: judge.SAMPLE_SIZE] == load("judge/plan.json")["sample"]
    assert len(plan["items"]) == len(EXTENDED) * EXTENSION_CASES + judge.RETEST_SIZE
    assert not any(item.get("empty_answer") for item in plan["items"])


def test_the_extension_reused_the_published_verdicts_of_its_identical_requests() -> None:
    planned = {
        item["item_id"]: item["message_sha256"] for item in load("judge-100/plan.json")["items"]
    }
    published = verdicts()
    shared = {
        row["item_id"] for row in published if planned.get(row["item_id"]) == row["message_sha256"]
    }
    rows = verdicts("judge-100")
    reused = [row for row in rows if "reused_from" in row]
    # The four generators' answers on the registered 30 cases, and three retests both plans drew.
    assert len(reused) == len(shared) == len(EXTENDED) * judge.SAMPLE_SIZE + 3
    assert {row["item_id"] for row in reused} == shared
    assert rows[: len(reused)] == reused, "copied before the first request"
    by_id = {row["item_id"]: row for row in published}
    for row in reused:
        assert row["reused_from"] == FILES["judge/plan.json"][0]
        copy = {key: value for key, value in row.items() if key != "reused_from"}
        assert copy == by_id[row["item_id"]]


def test_the_extension_summary_is_derived_from_the_verdicts() -> None:
    plan = load("judge-100/plan.json")
    rows = verdicts("judge-100")
    # summarize() takes a verdict only from a clean session's record and for a planned request.
    summary = judge.summarize(plan, rows)
    assert summary == load("judge-100/summary.json")
    assert summary["missing"] == 0 and summary["checks"] == plan["checks"]
    valid = [row for row in rows if row["status"] == "valid"]
    planned = sorted(item["item_id"] for item in plan["items"] if "message" in item)
    assert sorted(row["item_id"] for row in valid) == planned, "one verdict per request"
    others = [row for row in rows if row["status"] != "valid"]
    assert [(row["item_id"], row["reason"]) for row in others] == WITHOUT_VERDICT
    assert {row["status"] for row in others} == {"unavailable"}
    assert all(row["attempt"] == 1 for row in rows), "no reply of a wrong form"
    assert {row["model"] for row in valid} == {"claude-opus-5-5"}
    # Before the amendment and after it, the same session: three built-ins and nothing loaded.
    assert len({json.dumps(row["session"]["builtin"], sort_keys=True) for row in valid}) == 1
    for name in EXTENDED:
        generator = summary["generators"][name]
        assert generator["items"] == generator["graded"] == EXTENSION_CASES, name
    requests = summary["requests"]
    assert requests["reused"] == len(EXTENDED) * judge.SAMPLE_SIZE + 3
    assert requests["sent"] == len(planned) - requests["reused"]
    assert summary["retest"]["pairs"] == judge.RETEST_SIZE


def test_the_extension_row_reads_the_judge_as_registered() -> None:
    row = evidence_row("judge-100/")
    summary = load("judge-100/summary.json")
    generators = summary["generators"]
    for name in EXTENDED:
        classes = generators[name]["classes"]
        low, high = wilson(classes["good"], EXTENSION_CASES)
        counts = f"{classes['good']}/{classes['partial_ok']}/{classes['bad']}"
        assert f"`{name}` {counts} ({low:.2f}–{high:.2f}" in row, name
    small, large = EXTENDED[:2], EXTENDED[2:]

    def joined(names: tuple[str, ...], key: str, form: str) -> str:
        return " / ".join(format(generators[name][key], form) for name in names)

    rates = "supported_claim_rate"
    assert (
        f"supported claims {joined(small, rates, '.2f')} against {joined(large, rates, '.2f')}"
        in row
    )
    unsupported = "with_unsupported_claim"
    assert (
        f"an unsupported claim in {joined(small, unsupported, 'd')} against "
        f"{joined(large, unsupported, 'd')} answers"
    ) in row
    # Registered: per pair, the cases where only one of the two is good, the exact sign test on
    # them, and a pair apart only below 0.05 / 6.
    good = good_answers(load("judge-100/plan.json"), verdicts("judge-100"))
    cases = {case for _, case in good}
    assert len(cases) == EXTENSION_CASES
    pairs = list(itertools.combinations(EXTENDED, 2))
    apart = []
    for a, b in pairs:
        only_a = sum(good[a, case] and not good[b, case] for case in cases)
        only_b = sum(good[b, case] and not good[a, case] for case in cases)
        p = sign_test(only_a, only_b)
        assert f"`{a}`–`{b}` {only_a}/{only_b}, p {p:.3f}" in row, (a, b)
        if p < 0.05 / len(pairs):
            apart.append((a, b))
    assert apart == [("qwen3-1.7b", "qwen3-4b-instruct"), ("qwen3-1.7b", "qwen3-8b")]
    assert "apart below 0.05 / 6 only the first and the third" in row
    retest, context = summary["retest"], summary["context_has_answer"]
    assert f"the same class on {retest['same_class']} of {retest['pairs']} retests" in row
    assert (
        "the same `context_has_answer` for all four answers in "
        f"{context['same_for_every_answer']} of {context['cases']} cases"
    ) in row
    requests = summary["requests"]
    assert f"{requests['sent']} requests sent (${requests['cost_usd']:.2f}" in row
    assert f"{requests['reused']} verdicts reused from the 30-case record" in row

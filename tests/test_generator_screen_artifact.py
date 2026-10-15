"""Check the published screening of the generators below 7B on the production Mac.

On 2026-10-14 a clean clone of `86df582` on deproject-mac ran `scripts/generator_benchmark.py`
on the C.1 contract — one run at seed 42, no self-grading — for qwen2.5:1.5b, qwen3:1.7b and
Qwen3-4B-Instruct-2507, driven by the tools kept beside the record (`tools/`, the progress log
times every step). The tag qwen3:4b, a thinking-only model, ran its 1- and 5-case steps and was
replaced (`docs/specs/small-generator-screening.md`, amendment). The one judge then graded the
answers of these three and of C.1a and C.1b on 30 shared cases (`judge/`; its stream, stopped
once for low memory on the laptop, finished on 2026-10-15). Nothing here needs a model, the
network or the Mac: the test pins the bytes, rebuilds the judge's plan — with the checks of all
100 answers — from the tracked inputs and its summary from the verdicts, and finds the published
numbers in the evidence row.
"""

from __future__ import annotations

import gzip
import hashlib
import itertools
import json
import shutil
from pathlib import Path

from scripts import generator_answer_judge as judge

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "reports/generator-screen/86df582"
# sha256, size and path of every published file, LF line endings (.gitattributes).
PINS = """
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


def load(name: str) -> dict:
    return json.loads((RECORD / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report_paths() -> dict[str, Path]:
    return {**{name: RECORD / spec[0] for name, spec in SCREENED.items()}, **REFERENCE}


def verdicts() -> list[dict]:
    text = (RECORD / "judge/verdicts.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


def evidence_row() -> str:
    index = (ROOT / "EVIDENCE_INDEX.md").read_text(encoding="utf-8")
    (row,) = [line for line in index.splitlines() if "reports/generator-screen/86df582" in line]
    return row


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
    contexts = tmp_path / "contexts.json"
    with gzip.open(CONTEXTS_GZ, "rb") as source, contexts.open("wb") as target:
        shutil.copyfileobj(source, target)
    assert sha256(contexts) == CONTEXTS_SHA256
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
    # Thirty cases tell apart only gaps of more than five good answers; if the leading small
    # generator comes within five of C.1a or C.1b, the judge extends to all 100 cases.
    row = evidence_row()
    generators = load("judge/summary.json")["generators"]
    good = {name: generator["classes"]["good"] for name, generator in generators.items()}
    apart = [(a, b) for a, b in itertools.combinations(good, 2) if abs(good[a] - good[b]) > 5]
    assert apart == [("qwen2.5-1.5b", "qwen3-4b-instruct")]
    assert "here only `qwen2.5-1.5b` from `qwen3-4b-instruct`" in row
    leader = max(SCREENED, key=lambda name: good[name])
    assert leader == "qwen3-4b-instruct"
    assert any(abs(good[leader] - good[name]) <= 5 for name in REFERENCE)
    assert "extends the judge to all 100 cases of the generators concerned" in row

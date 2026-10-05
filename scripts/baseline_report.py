"""Build the slice 2.5 baseline report: the rulers over a collected and judged run.

    python -m scripts.baseline_report export --run <baseline run> --out <evidence dir>
    python -m scripts.baseline_report build --inputs <evidence dir> --judge-dir <judge dir>
        --out <report.json> [--judge opus] [--state <supervisor state>] [--host-samples <file>]

export reads a finished production-baseline run through the collector's own integrity
checks and writes what the report is computed from, small enough to keep in the
repository: byte copies of manifest.json, registration.json and the collector's
report.json (as collector-report.json), and contexts.json.gz — for every case its first
five reranked seeds and its sent documents as text hashes, with one table of the texts.

build computes from those files, the judge directory and the registered family map: the
lexical ruler and the development ruler for H and Hm, their intervals, the timings of the
collection and the provenance fields the collector left to this step. It refuses when the
files do not describe one run. Every rule is the metrics spec's, «Baseline of plan slice
2.5»; nothing is chosen here, and nothing is sent anywhere.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from evaluation.blinded_judge import read_store
from evaluation.ragas_eval import context_precision
from evaluation.semantic_ruler import (
    FACT_MATCHER_VERSION,
    RESAMPLES,
    SEED,
    family_clusters,
    ndcg_at_5,
    precision_at_5,
    sent_precision,
    single_arm_summary,
)
from scripts import baseline_judge as judge_tool
from scripts import production_baseline as baseline
from scripts import production_parity as parity

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = "production-baseline-report/v1"
CONTEXTS_VERSION = 1
FAMILY_MAP = "evaluation/document_families.json"
FAMILY_MAP_SHA256 = "54bdb736180e00325bff20f49e2b9d985dd62278fe9f9cdb6161a0da719e3584"
OFFICIAL_GATE = 0.63
SUBSETS = ("H", "Hm")
JUDGED = ("precision_at_5", "sent_precision", "ndcg_at_5")
LEXICAL = {"context_precision": "sent", "context_precision_seeds": "seeds"}
NO_GOLD = "H and Hm carry no registered gold spans, evidence groups or facts"
NO_ANSWER = "nothing is generated in this mode"
SINGLE_ARM = "single arm, no paired difference; registered for a comparison in plan step 1.3c"
UNMEASURED = {
    "evidence_recall_pool": NO_GOLD,
    "all_evidence_coverage": NO_GOLD,
    "fact_coverage": NO_GOLD,
    "abstention_correct": NO_ANSWER,
    "faithfulness": NO_ANSWER,
    "answer_fact_coverage": NO_ANSWER,
    "citation_correctness": NO_ANSWER,
    "citation_presence": NO_ANSWER,
    "action_correct": NO_ANSWER,
    "critical_errors": NO_ANSWER,
}
CODE_FILES = (
    "scripts/baseline_report.py",
    "scripts/baseline_judge.py",
    "evaluation/semantic_ruler.py",
    "evaluation/judge_consensus.py",
    "evaluation/ragas_eval.py",
)
POPULATION = (
    "H and Hm through the production path: hybrid retrieval with parent expansion, graph off, "
    "model routing off, single-turn; retrieval, rerank and grading, no generation. Judged "
    "seeds are the first five reranked texts before expansion; the sent context is what "
    "grading left."
)


def _copy_once(source: Path, target: Path) -> None:
    data = source.read_bytes()
    if target.exists():
        if target.read_bytes() != data:
            raise FileExistsError(f"A different {target.name} exists in the evidence directory")
        return
    target.write_bytes(data)


def export(run: Path, out: Path) -> dict[str, Any]:
    """Write the repository-sized inputs of the report from one finished baseline run."""
    identity, pairs = judge_tool.load_baseline(run)
    texts: dict[str, str] = {}
    cases: list[dict[str, Any]] = []
    for case, row in pairs:
        entry: dict[str, Any] = {
            "case_id": case["case_id"],
            "subset": case["subset"],
            "status": row["status"],
            "grade_file_sha256": parity.file_sha(run / "grade" / f"{case['case_id']}.json"),
        }
        if row["status"] != "ok":
            entry["exclusion"] = row.get("exclusion")
            cases.append(entry)
            continue
        for name, documents in (("seeds", row["seed_documents"][:5]), ("sent", row["documents"])):
            entry[name] = [document["text_sha256"] for document in documents]
            for document in documents:
                if baseline.text_sha(document["text"]) != document["text_sha256"]:
                    raise baseline.IntegrityError(f"text hash mismatch in {case['case_id']}")
                texts[document["text_sha256"]] = document["text"]
        entry["sent_context_sha256"] = row.get("sent_context_sha256")
        cases.append(entry)
    out.mkdir(parents=True, exist_ok=True)
    for source, target in (
        ("manifest.json", "manifest.json"),
        ("registration.json", "registration.json"),
        ("report.json", "collector-report.json"),
    ):
        _copy_once(run / source, out / target)
    payload = {
        "contexts_version": CONTEXTS_VERSION,
        "run_sha256": identity,
        "collector_report_sha256": parity.file_sha(run / "report.json"),
        "cases": cases,
        "texts": dict(sorted(texts.items())),
    }
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    packed = out / "contexts.json.gz"
    if packed.exists():
        if gzip.decompress(packed.read_bytes()) != data:
            raise FileExistsError("A different contexts.json.gz exists in the evidence directory")
    else:
        packed.write_bytes(gzip.compress(data, compresslevel=9, mtime=0))
    return {
        "run_sha256": identity,
        "cases": len(cases),
        "collected": sum(entry["status"] == "ok" for entry in cases),
        "texts": len(texts),
        "contexts_sha256": parity.digest(payload),
    }


def load_inputs(inputs: Path) -> dict[str, Any]:
    """Read an evidence directory and refuse files that do not describe one run."""
    manifest = baseline.load_manifest(inputs)
    identity = parity.digest(manifest)
    collector = parity.load_stage(inputs / "collector-report.json", identity)
    contexts = json.loads(gzip.decompress((inputs / "contexts.json.gz").read_bytes()))
    if contexts.get("contexts_version") != CONTEXTS_VERSION:
        raise ValueError("contexts_version is not supported")
    if contexts["run_sha256"] != identity or contexts["collector_report_sha256"] != (
        parity.file_sha(inputs / "collector-report.json")
    ):
        raise ValueError("contexts.json.gz belongs to another run")
    if [entry["case_id"] for entry in contexts["cases"]] != [
        case["case_id"] for case in manifest["cases"]
    ]:
        raise ValueError("contexts.json.gz does not list the cases of the manifest")
    for text_sha256, text in contexts["texts"].items():
        if baseline.text_sha(text) != text_sha256:
            raise ValueError("a text of contexts.json.gz does not match its hash")
    for entry in contexts["cases"]:
        if entry["status"] != "ok":
            continue
        if any(key not in contexts["texts"] for name in ("seeds", "sent") for key in entry[name]):
            raise ValueError(f"contexts.json.gz misses a text of {entry['case_id']}")
    return {
        "identity": identity,
        "manifest": manifest,
        "collector": collector,
        "collector_sha256": parity.file_sha(inputs / "collector-report.json"),
        "contexts": contexts,
        "contexts_sha256": parity.digest(contexts),
    }


def load_family_map(path: Path, expected_sha256: str | None = FAMILY_MAP_SHA256) -> dict[str, Any]:
    """Read the family map; the registered one unless another hash is named explicitly."""
    digest = parity.file_sha(path)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("the family map is not the registered one")
    register = parity.read(path)
    family_of: dict[str, str] = {}
    for family in register["families"]:
        for member in family["members"]:
            if member["source_id"] in family_of:
                raise ValueError(f"document in two families: {member['source_id']}")
            family_of[member["source_id"]] = family["family_id"]
    return {
        "sha256": digest,
        "family_of": family_of,
        "case_documents": {
            subset: usage["case_documents"]
            for subset, usage in register["development_used"].items()
            if "case_documents" in usage
        },
    }


def case_families(
    cases: Sequence[Mapping[str, Any]], family_map: Mapping[str, Any]
) -> dict[str, list[str]]:
    """Give each case the families of the documents the map lists for it."""
    mapping: dict[str, list[str]] = {}
    for case in cases:
        listed = family_map["case_documents"].get(case["subset"], {}).get(case["case_id"])
        if not listed:
            raise ValueError(f"the family map lists no documents for {case['case_id']}")
        unknown = sorted(set(listed) - set(family_map["family_of"]))
        if unknown:
            raise ValueError(f"documents of {case['case_id']} outside the family map: {unknown}")
        mapping[case["case_id"]] = sorted({family_map["family_of"][name] for name in listed})
    return mapping


def load_judged(judge_dir: Path, judge: str, inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Read the plan, the stores, the ruler input and the retest; refuse a stale or foreign one."""
    if judge not in judge_tool.JUDGES:
        raise ValueError(f"unknown judge: {judge}")
    plan = judge_tool.load_plan(judge_dir)
    plan_sha256 = parity.file_sha(judge_dir / "plan.json")
    if (
        plan["run_sha256"] != inputs["identity"]
        or plan["baseline_report_sha256"] != (inputs["collector_sha256"])
    ):
        raise ValueError("the judge plan belongs to another run")
    contexts = {entry["case_id"]: entry for entry in inputs["contexts"]["cases"]}
    collected = [case_id for case_id, entry in contexts.items() if entry["status"] == "ok"]
    if [case["case_id"] for case in plan["cases"]] != collected:
        raise ValueError("the judge plan does not list the collected cases")
    for case in plan["cases"]:
        entry = contexts[case["case_id"]]
        if case["seeds"] != entry["seeds"] or case["sent"] != entry["sent"]:
            raise ValueError(f"the judge plan reads other texts for {case['case_id']}")
    first_path, second_path = judge_dir / f"{judge}.jsonl", judge_dir / f"{judge}-retest.jsonl"
    first_sha256 = parity.file_sha(first_path)
    ruler_input = parity.read(judge_dir / "ruler-input.json")
    if (
        ruler_input.get("run_sha256") != inputs["identity"]
        or ruler_input.get("plan_sha256") != plan_sha256
        or ruler_input.get("stores") != {judge: first_sha256}
    ):
        raise ValueError("ruler-input.json is not computed from this plan and this store")
    if (
        ruler_input.get("status") != "ok"
        or ruler_input.get("included_judges") != [judge]
        or ruler_input.get("grade_source") != "single_judge"
    ):
        raise ValueError("ruler-input.json does not hold the grades of the one registered judge")
    retest_path = judge_dir / f"{judge}-retest.json"
    retest: dict[str, Any] | None = None
    if retest_path.is_file():
        retest = parity.read(retest_path)
        stores = {
            "first": first_sha256,
            "second": parity.file_sha(second_path) if second_path.is_file() else None,
        }
        if (
            retest.get("run_sha256") != inputs["identity"]
            or retest.get("plan_sha256") != plan_sha256
            or retest.get("stores") != stores
        ):
            raise ValueError("the retest report is not computed from this plan and these stores")
    runs_path = judge_dir / "runs.jsonl"
    return {
        "plan": plan,
        "plan_sha256": plan_sha256,
        "ruler_input": ruler_input,
        "ruler_input_sha256": parity.file_sha(judge_dir / "ruler-input.json"),
        "retest": retest,
        "retest_sha256": parity.file_sha(retest_path) if retest is not None else None,
        "first": read_store(first_path),
        "first_sha256": first_sha256,
        "second": read_store(second_path) if second_path.is_file() else [],
        "second_sha256": parity.file_sha(second_path) if second_path.is_file() else None,
        "runs": read_store(runs_path) if runs_path.is_file() else [],
    }


def _spread(values: Sequence[int]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "min": min(values),
        "mean": math.fsum(values) / len(values),
        "max": max(values),
    }


def subset_report(
    subset: str,
    inputs: Mapping[str, Any],
    judged: Mapping[str, Any],
    families: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    """Compute one subset: per-case values, the registered intervals and what was left out."""
    cases = [case for case in inputs["manifest"]["cases"] if case["subset"] == subset]
    contexts = {entry["case_id"]: entry for entry in inputs["contexts"]["cases"]}
    texts = inputs["contexts"]["texts"]
    mapping = {case["case_id"]: list(families[case["case_id"]]) for case in cases}
    collected = [case for case in cases if contexts[case["case_id"]]["status"] == "ok"]
    values: dict[str, dict[str, float]] = {metric: {} for metric in (*JUDGED, *LEXICAL)}
    for case in collected:
        entry = contexts[case["case_id"]]
        keywords = list(case.get("expected", {}).get("answer_contains", []))
        for metric, population in LEXICAL.items():
            documents = [texts[key] for key in entry[population]]
            values[metric][case["case_id"]] = float(
                context_precision(case["query"], documents, keywords)
            )
    ruler = judged["ruler_input"]["ruler"]
    zero_idcg: list[str] = []
    for kept in ruler["cases"]:
        if kept["subset"] != subset:
            continue
        case_id, grades = kept["case_id"], kept["grades"]
        values["precision_at_5"][case_id] = precision_at_5(kept["seeds"], grades)
        values["sent_precision"][case_id] = sent_precision(kept["sent"], grades)
        ndcg = ndcg_at_5(kept["seeds"], grades)
        if ndcg is None:
            zero_idcg.append(case_id)
        else:
            values["ndcg_at_5"][case_id] = ndcg
    metrics: dict[str, Any] = {}
    for metric, per_case in values.items():
        if per_case:
            metrics[metric] = {
                **single_arm_summary(per_case, mapping, seed=SEED, resamples=RESAMPLES),
                "excluded": len(collected) - len(per_case),
            }
        else:
            metrics[metric] = {"point": "N/A", "reason": "no case has a value", "n": 0}
    for metric, reason in UNMEASURED.items():
        metrics[metric] = {"point": "N/A", "reason": reason, "n": 0}
    components = family_clusters(mapping)
    return {
        "case_count": len(cases),
        "collected": len(collected),
        "collection_excluded": [
            {"case_id": case["case_id"], "exclusion": contexts[case["case_id"]].get("exclusion")}
            for case in cases
            if contexts[case["case_id"]]["status"] != "ok"
        ],
        "judged_excluded": [
            {"case_id": row["case_id"], "reason": row["reason"], "unjudged": row["unjudged"]}
            for row in ruler["excluded"]
            if row["subset"] == subset
        ],
        "zero_idcg": zero_idcg,
        "cluster_unit": {
            "basis": f"registered family map, development_used.{subset}.case_documents",
            "count": len(components),
            "sizes": sorted((len(component) for component in components), reverse=True),
            "mapping": mapping,
            "components": [list(component) for component in components],
        },
        "contexts": {
            "seeds": _spread([len(contexts[case["case_id"]]["seeds"]) for case in collected]),
            "sent": _spread([len(contexts[case["case_id"]]["sent"]) for case in collected]),
            "sent_characters": _spread(
                [
                    sum(len(texts[key]) for key in contexts[case["case_id"]]["sent"])
                    for case in collected
                ]
            ),
            "empty_sent": sum(not contexts[case["case_id"]]["sent"] for case in collected),
        },
        "metrics": metrics,
        "per_case": values,
    }


def _store_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    attempts = [row for row in rows if row.get("request_version") == 2 and not row.get("reused")]
    valid = [row for row in attempts if row.get("status") == "valid"]
    return {
        "attempts": len(attempts),
        "valid": len(valid),
        "models": sorted({str(row["model"]) for row in valid if row.get("model")}),
        "rubric_versions": sorted({str(row.get("rubric_version")) for row in attempts}),
        "judge_versions": sorted({str(row.get("judge_version")) for row in attempts}),
        "elapsed_s": math.fsum(float(row.get("elapsed_s") or 0) for row in attempts),
        "total_cost_usd": math.fsum(
            float((row.get("usage") or {}).get("total_cost_usd") or 0) for row in attempts
        ),
    }


def _cli_versions(runs: Sequence[Mapping[str, Any]]) -> list[str] | str:
    if not runs:
        return "N/A: no run log beside the stores"
    versions = sorted(
        {
            str(run["environment"]["cli_version"])
            for run in runs
            if isinstance(run.get("environment"), dict) and run["environment"].get("cli_version")
        }
    )
    return versions or "N/A: the run log names no CLI version"


def collection_block(state: Path | None, host_samples: Path | None, code_sha: str) -> Any:
    """Summarise the supervisor's record of the collection: pauses, attempts and host peaks."""
    if state is None:
        return "N/A: supervisor state not supplied"
    record = parity.read(state)
    if record.get("status") != "complete" or record.get("code_sha") != code_sha:
        raise ValueError("the supervisor state is not that of this finished collection")
    peaks = record.get("host_peaks", {})

    def peak(field: str) -> Any:
        found = [stage[field] for stage in peaks.values() if type(stage.get(field)) in (int, float)]
        return max(found) if found else "N/A: not sampled"

    return {
        "state_sha256": parity.file_sha(state),
        "host_samples_sha256": parity.file_sha(host_samples)
        if host_samples is not None
        else "N/A: host samples not supplied",
        "started": record.get("started"),
        "host": record.get("host"),
        "stage_seconds": record.get("stage_seconds"),
        "attempts": record.get("attempts"),
        "pauses": record.get("pauses"),
        "monitor_errors": record.get("monitor_errors"),
        "host_peaks": peaks,
        "peak_host_rss": {
            "collector_plus_ollama_rss_kb": peak("collector_plus_ollama_rss_kb"),
            "mem_used_mb": peak("mem_used_mb"),
            "swap_used_mb": peak("swap_used_mb"),
            "scope": "supervisor samples of the collector and Ollama processes, one every 30 s",
        },
    }


def _code() -> dict[str, Any]:
    def git(*arguments: str) -> str | None:
        try:
            return subprocess.check_output(
                ["git", *arguments], cwd=ROOT, text=True, timeout=30, stderr=subprocess.DEVNULL
            ).strip()
        except (OSError, subprocess.SubprocessError):
            return None

    status = git("status", "--porcelain", "--untracked-files=no")
    return {
        "commit": git("rev-parse", "HEAD") or "N/A: not a git checkout",
        "tracked_tree_clean": None if status is None else status == "",
        "blobs": {name: git("rev-parse", f"HEAD:{name}") for name in CODE_FILES},
    }


def build(
    inputs_dir: Path,
    judge_dir: Path,
    *,
    judge: str = "opus",
    families: Path | None = None,
    families_sha256: str | None = FAMILY_MAP_SHA256,
    state: Path | None = None,
    host_samples: Path | None = None,
) -> dict[str, Any]:
    """Compute the whole report from an evidence directory and its judge directory."""
    inputs = load_inputs(inputs_dir)
    judged = load_judged(judge_dir, judge, inputs)
    family_map = load_family_map(
        ROOT / FAMILY_MAP if families is None else families, families_sha256
    )
    manifest, collector = inputs["manifest"], inputs["collector"]
    unknown = sorted({case["subset"] for case in manifest["cases"]} - set(SUBSETS))
    if unknown:
        raise ValueError(f"subsets outside the registered population: {unknown}")
    mapping = case_families(manifest["cases"], family_map)
    subsets = {subset: subset_report(subset, inputs, judged, mapping) for subset in SUBSETS}
    retest, first = judged["retest"], _store_summary(judged["first"])
    if retest is None:
        provisional, reason = True, "the stability retest has not been run"
    elif retest["verdict"] == "single_judge":
        provisional, reason = False, "the stability retest passed"
    else:
        provisional, reason = True, f"the stability retest gave {retest['verdict']}"
    collection = collection_block(state, host_samples, manifest["code_sha"])
    timings = collector["timings_ms"]
    deciding: dict[str, Any] = {}
    for name in baseline.DECIDING_METRICS:
        if name in UNMEASURED:
            deciding[name] = {
                field: f"N/A: {UNMEASURED[name]}"
                for field in ("n", "clusters", "MDE", "achieved_power")
            }
        elif name == "retrieve_p95":
            deciding[name] = {
                "n": timings.get("retrieve", {}).get("n", "N/A: no retrieve timing"),
                "clusters": "N/A: one run without repeats; no interval is formed",
                "MDE": f"N/A: {SINGLE_ARM}",
                "achieved_power": f"N/A: {SINGLE_ARM}",
            }
        else:
            deciding[name] = {
                subset: {
                    "n": block["metrics"][name]["n"],
                    "clusters": block["metrics"][name].get("clusters", 0),
                    "MDE": f"N/A: {SINGLE_ARM}",
                    "achieved_power": f"N/A: {SINGLE_ARM}",
                }
                for subset, block in subsets.items()
            }
    provenance = {
        **collector["provenance"],
        "raw_judge_replies": {
            "first_pass": {
                "file": f"{judge}.jsonl",
                "sha256": judged["first_sha256"],
                **_store_summary(judged["first"]),
            },
            "retest_pass": {
                "file": f"{judge}-retest.jsonl",
                "sha256": judged["second_sha256"],
                **_store_summary(judged["second"]),
            }
            if judged["second_sha256"] is not None
            else "N/A: the stability retest has not been run",
            "request_hashes": "every stored attempt carries request_sha256 and request_key",
            "production_llm_replies": "per-case model_calls cache files of the collection run",
        },
        "bootstrap_seed": {"metric_intervals": SEED, "retest_kappa": judge_tool.SEED},
        "fact_matcher_version": f"{FACT_MATCHER_VERSION}; not applied: {NO_GOLD}",
        "judge_model": first["models"],
        "judge_revision": {
            "judge_version": first["judge_versions"],
            "cli_versions": _cli_versions(judged["runs"]),
        },
        "rubric_version": first["rubric_versions"],
        "peak_host_rss": collection["peak_host_rss"]
        if isinstance(collection, dict)
        else collection,
        "metrics": deciding,
        "family_map": {"path": FAMILY_MAP, "sha256": family_map["sha256"]},
        "judge_plan_sha256": judged["plan_sha256"],
        "ruler_input_sha256": judged["ruler_input_sha256"],
        "retest_report_sha256": judged["retest_sha256"]
        or "N/A: the stability retest has not been run",
        "contexts_sha256": inputs["contexts_sha256"],
        "collector_report_sha256": inputs["collector_sha256"],
        "report_code": _code(),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_class": "development-baseline",
        "manifest_sha256": inputs["identity"],
        "grade_source": "single_judge",
        "judge": judge,
        "provisional_ruler": provisional,
        "provisional_reason": reason,
        "population": POPULATION,
        "total_cases": collector["total_cases"],
        "denominators": collector["denominators"],
        "exclusions": collector["exclusions"],
        "config": {
            "resamples": RESAMPLES,
            "seed": SEED,
            "interval": "percentile CI95 of the cluster bootstrap, linear quantiles",
            "small_cluster_rule": "under 10 clusters the cluster-robust t-interval beside it; "
            "one cluster gives the whole range [0, 1]; ci95_conservative is the wider bound",
            "sensitivity_view": "case_bootstrap_ci95: every case its own cluster",
            "weights": "equal case weights",
            "relevant_grade_min": 2,
            "top_k": 5,
            "official_context_precision_gate": OFFICIAL_GATE,
            "gate_applies_to": "neither lexical number here; printed beside (decision D6)",
            "collection": collector["provenance"]["config"],
        },
        "retest": {
            field: retest[field]
            for field in ("status", "verdict", "threshold", "units", "missing", "cases")
        }
        | {"all": retest["all"], "by_subset": retest["by_subset"]}
        if retest is not None
        else "N/A: the stability retest has not been run",
        "subsets": subsets,
        "timings_ms": timings,
        "timing_scope": collector["timing_scope"],
        "latency_evidence": collector["latency_evidence"],
        "collection": collection,
        "provenance": provenance,
    }


def main(argv: list[str] | None = None) -> int:
    """Run export or build and return the process exit status."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    export_command = commands.add_parser("export")
    export_command.add_argument("--run", type=Path, required=True)
    export_command.add_argument("--out", type=Path, required=True)
    build_command = commands.add_parser("build")
    build_command.add_argument("--inputs", type=Path, required=True)
    build_command.add_argument("--judge-dir", type=Path, required=True)
    build_command.add_argument("--out", type=Path, required=True)
    build_command.add_argument("--judge", choices=judge_tool.JUDGES, default=judge_tool.JUDGES[0])
    build_command.add_argument("--state", type=Path)
    build_command.add_argument("--host-samples", type=Path)
    arguments = parser.parse_args(argv)
    if arguments.command == "export":
        print(json.dumps(export(arguments.run, arguments.out), ensure_ascii=False))
        return 0
    report = build(
        arguments.inputs,
        arguments.judge_dir,
        judge=arguments.judge,
        state=arguments.state,
        host_samples=arguments.host_samples,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    arguments.out.write_text(payload, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "provisional_ruler": report["provisional_ruler"],
                **{
                    subset: {
                        metric: block["metrics"][metric]["point"] for metric in (*JUDGED, *LEXICAL)
                    }
                    for subset, block in report["subsets"].items()
                },
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

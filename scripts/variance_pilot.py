"""The variance pilot of plan step 1.3c: how the paired differences of the gold metrics spread.

Three arms of the production retrieval path run over the verified pilot cases that carry gold
evidence: the control and two perturbations of it, each moving one registered candidate count.
The perturbations are not mechanism candidates and nothing is chosen from them. They show how the
paired differences of the gold metrics spread when an arm changes the pool or the sent context —
the quantity the interval of the decision rule is made of — and the tables say what the
registered split can show for such a spread.

    python -m scripts.variance_pilot cases [--write]            the questions the arms run on
    python -m scripts.variance_pilot export --run RUN --out DIR         on the collection host
    python -m scripts.variance_pilot measure --arm control=DIR --arm pool30=DIR \
        --arm sent3=DIR --out FILE

No judge and no generator take part: the judged metrics and the answer metrics get no variance
here and are read on the registered scenario grid. The verified cases, the question file, the
family map and the split are read at their registered SHA-256 and the command line cannot name
others.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from evaluation import devset_split as split
from evaluation import gold_metrics as gold
from evaluation import power
from evaluation import semantic_ruler as ruler
from evaluation.devset import FACT_LABEL_RULE
from scripts import baseline_judge as judge_tool
from scripts import baseline_report as report_tool
from scripts import production_baseline as baseline
from scripts import production_parity as parity

ROOT = Path(__file__).resolve().parents[1]
VERSION = "variance-pilot/v1"
ADDRESSES_VERSION = "variance-pilot-addresses/v1"
VERIFIED = ROOT / "evaluation/devset_pilot_verified.jsonl"
QUESTIONS = ROOT / "evaluation/devset_pilot_gold_questions.jsonl"
FAMILIES = ROOT / "evaluation/document_families.json"
ARCHIVE = ROOT / "evaluation" / (baseline.ARCHIVE + ".json.gz")
SUBSET = "pilot-gold"
TASK = "1.3c variance pilot"
CONTROL = "control"
# Neither count is one a hypothesis of the plan registers: 40 candidates is the budget of H5.
ARMS: dict[str, dict[str, int]] = {
    CONTROL: {},
    "pool30": {"retrieval_top_k": 30},
    "sent3": {"rerank_top_k": 3},
}
# The registered files a pilot is measured on, by SHA-256; `measure` refuses any other.
REGISTERED_SHA256 = {
    "verified": "05ebf00743e2ae3b6a8117f735a3d9a34b451f8bf066a4dd1dfcaadf8e708df4",
    "questions": "c5017d2f81f47b4751183a090d7ff505afded013335bb7f01bf3045c5edffccf",
    "families": "54bdb736180e00325bff20f49e2b9d985dd62278fe9f9cdb6161a0da719e3584",
    "split": "20d69e9bb30043f7012823e3b39ca2692badc58bf9e04a737691abbcab2c44a8",
}
SCENARIO_VARIANCES = (0.05, 0.10, 0.20)
GOLD_EVIDENCE = "cases with gold evidence"
POPULATIONS: dict[str, tuple[str, ...]] = {
    "all cases": split.CLASSES,
    GOLD_EVIDENCE: ("multi-doc", "single-doc", "aggregation"),
    "unresolvable cases": ("needs-refusal/clarification",),
}
# The deciding metrics of the closed table that are read on an interval, each with the largest
# population its denominator can have, so that the registered MDE of a row is a lower bound of
# what the verified, answered and paired cases will give. An unresolvable case may be answered
# in both arms: a row over answered cases counts all cases unless it also needs facts, which
# only a case with gold evidence has.
DECIDING: dict[str, str] = {
    "sent_precision": GOLD_EVIDENCE,
    "all_evidence_coverage": GOLD_EVIDENCE,
    "precision_at_5": "all cases",
    "evidence_recall_pool": GOLD_EVIDENCE,
    "fact_coverage": GOLD_EVIDENCE,
    "abstention_correct": "unresolvable cases",
    "faithfulness": "all cases",
    "answer_fact_coverage": GOLD_EVIDENCE,
    "citation_correctness": GOLD_EVIDENCE,
    "citation_presence": "all cases",
    "action_correct": "all cases",
}
REGISTERED_GRID_VARIANCE = 0.10
# Why a perturbation's numbers are not used, as the document words it.
LOST_PAIR = "a pair was not measured"
NO_SPAN_IN_INDEX = "no chunk of the index holds a gold span whole"
NO_SPAN_IN_CONTROL = "the pool of the control holds no gold span"
SHARED = (
    "code_sha",
    "source_sha256",
    "runtime",
    "cases",
    "index_receipt_sha256",
    "source_manifest_sha256",
    "chunker_version",
    "llm",
    "reranker",
)
CODE_FILES = (
    "scripts/variance_pilot.py",
    "evaluation/gold_metrics.py",
    "evaluation/power.py",
    "evaluation/semantic_ruler.py",
    "evaluation/devset_split.py",
)


def read_lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def gold_questions(cases: Sequence[Mapping[str, Any]]) -> str:
    """What the collector reads: the id and the question of every case with a gold span."""
    return "".join(
        json.dumps(
            {"case_id": case["case_id"], "question": case["question"]},
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
        for case in cases
        if case["evidence_spans"]
    )


def _write_once(path: Path, text: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise FileExistsError(f"A different {path.name} exists")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False) + "\n"


def export(run: Path, out: Path) -> dict[str, Any]:
    """Write the evidence directory of one finished arm: the report's inputs and the addresses.

    The report's export keeps the texts of the seeds and of the sent context by hash. The gold
    metrics also need the pool the reranker received and the document every sent text came from;
    ``addresses.json`` adds them.
    """
    summary = report_tool.export(run, out)
    identity, pairs = judge_tool.load_baseline(run)
    cases: list[dict[str, Any]] = []
    for case, row in pairs:
        entry: dict[str, Any] = {"case_id": case["case_id"], "status": row["status"]}
        if row["status"] == "ok":
            entry["pool"] = row["pool"]
            entry["ranked"] = row["ranked"]
            entry["sent"] = [
                {
                    "text_sha256": document["text_sha256"],
                    "source_id": document["metadata"].get("source"),
                    "chunk_index": document["metadata"].get("chunk_index"),
                    "parent_expanded": bool(document["metadata"].get("parent_expanded")),
                }
                for document in row["documents"]
            ]
        cases.append(entry)
    payload = {"addresses_version": ADDRESSES_VERSION, "run_sha256": identity, "cases": cases}
    _write_once(out / "addresses.json", dump(payload))
    return {**summary, "addresses_sha256": parity.file_sha(out / "addresses.json")}


def load_arm(directory: Path) -> dict[str, Any]:
    """Read one arm's evidence directory and refuse addresses of another run."""
    inputs = report_tool.load_inputs(directory)
    addresses = parity.read(directory / "addresses.json")
    if (
        addresses.get("addresses_version") != ADDRESSES_VERSION
        or addresses["run_sha256"] != inputs["identity"]
    ):
        raise ValueError("addresses.json belongs to another run")
    packed = inputs["contexts"]["cases"]
    if [entry["case_id"] for entry in addresses["cases"]] != [e["case_id"] for e in packed]:
        raise ValueError("addresses.json does not list the cases of the run")
    for entry, listed in zip(addresses["cases"], packed, strict=True):
        if entry["status"] != listed["status"] or (
            entry["status"] == "ok"
            and [document["text_sha256"] for document in entry["sent"]] != listed["sent"]
        ):
            raise ValueError(f"addresses.json disagrees with the contexts of {entry['case_id']}")
    return {
        **inputs,
        "addresses": addresses,
        "addresses_sha256": parity.file_sha(directory / "addresses.json"),
    }


def check_arms(arms: Mapping[str, Mapping[str, Any]]) -> None:
    """The arms differ from the control in the one count each of them registers, in nothing else."""
    if set(arms) != set(ARMS):
        raise ValueError("the pilot is the control and its two registered perturbations")
    control = arms[CONTROL]["manifest"]
    moved = {key for overrides in ARMS.values() for key in overrides}

    def datasets(manifest: Mapping[str, Any]) -> dict[str, tuple[str, int]]:
        return {name: (d["sha256"], d["count"]) for name, d in manifest["datasets"].items()}

    def unmoved(manifest: Mapping[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in manifest["config"].items() if key not in moved}

    for name, arm in arms.items():
        manifest = arm["manifest"]
        if manifest.get("config_overrides", {}) != ARMS[name] or any(
            manifest["config"][key] != value for key, value in ARMS[name].items()
        ):
            raise ValueError(f"{name}: the run does not move what the arm registers")
        if (
            any(manifest[key] != control[key] for key in SHARED)
            or datasets(manifest) != datasets(control)
            or unmoved(manifest) != unmoved(control)
        ):
            raise ValueError(f"{name}: not the control's code, cases, index, models or settings")


def check_labels(cases: Sequence[Mapping[str, Any]], manifest: Mapping[str, Any]) -> str:
    """The labels were verified on the corpus the run retrieved from; its version is returned."""
    corpus = manifest["source_manifest"]["corpus_sha256"]
    revisions = {entry["name"]: entry["sha256"] for entry in manifest["source_manifest"]["files"]}
    for case in cases:
        for span in case["evidence_spans"]:
            if (
                span["corpus_version"] != corpus
                or revisions.get(span["source_id"]) != span["source_revision"]
            ):
                raise ValueError(f"{case['case_id']}: labelled on another corpus than the run's")
    return str(corpus)


def load_chunks(archive: Path, manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    if parity.file_sha(archive) != manifest["index_receipt"]["corpus_sha256"]:
        raise ValueError("the chunk archive is not the one the index was built from")
    chunks: list[dict[str, Any]] = json.loads(gzip.decompress(archive.read_bytes()))["chunks"]
    return chunks


def _chunk_text(chunk: Mapping[str, Any]) -> dict[str, Any]:
    return {"source_id": (chunk.get("metadata") or {}).get("source"), "text": chunk["page_content"]}


def arm_metrics(
    arm: Mapping[str, Any],
    cases: Mapping[str, Mapping[str, Any]],
    chunks: Sequence[Mapping[str, Any]],
    corpus: str,
) -> dict[str, dict[str, Any] | None]:
    """The gold metrics of every case of one arm; None for a case the run excluded."""
    texts = arm["contexts"]["texts"]
    result: dict[str, dict[str, Any] | None] = {}
    for entry in arm["addresses"]["cases"]:
        if entry["status"] != "ok":
            result[entry["case_id"]] = None
            continue
        pool = gold.evidence_texts([_chunk_text(chunks[index]) for index in entry["pool"]], corpus)
        sent = gold.evidence_texts(
            [
                {"source_id": document["source_id"], "text": texts[document["text_sha256"]]}
                for document in entry["sent"]
            ],
            corpus,
        )
        result[entry["case_id"]] = {
            **gold.case_metrics(cases[entry["case_id"]], pool, sent),
            "pool": sorted(entry["pool"]),
            "sent": [document["text_sha256"] for document in entry["sent"]],
        }
    return result


def index_bound(
    cases: Sequence[Mapping[str, Any]], chunks: Sequence[Mapping[str, Any]], corpus: str
) -> dict[str, Any]:
    """Gold spans that some chunk of the index holds whole: what a pool can reach at most.

    A span that several chunks hold whole lies where neighbouring chunks overlap or recurs in
    its document. The rule reads text, so for such a span it cannot tell the labelled place
    from another; the chunks are listed by their place in the index.
    """
    by_source: dict[Any, list[tuple[int, dict[str, Any]]]] = {}
    for index, chunk in enumerate(chunks):
        text = _chunk_text(chunk)
        by_source.setdefault(text["source_id"], []).append((index, text))
    spans = 0
    missing: list[str] = []
    several: dict[str, list[int]] = {}
    for case in cases:
        for span_id, span in gold.gold_spans(case).items():
            holding = [
                index
                for index, text in by_source.get(span.source_id, [])
                if ruler.evidence_recall_pool([span], gold.evidence_texts([text], corpus)) == 1.0
            ]
            spans += 1
            if not holding:
                missing.append(span_id)
            elif len(holding) > 1:
                several[span_id] = holding
    return {
        "spans": spans,
        "held_whole_by_a_chunk": spans - len(missing),
        "held_by_no_chunk": missing,
        "held_by_several_chunks": several,
    }


def compare(
    control: Mapping[str, Mapping[str, Any] | None],
    arm: Mapping[str, Mapping[str, Any] | None],
    families: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    """The paired differences of one perturbation against the control, per gold metric."""
    pairs = {
        case_id: (control[case_id], arm[case_id])
        for case_id in control
        if control[case_id] is not None and arm.get(case_id) is not None
    }
    result: dict[str, Any] = {
        "pairs": len(pairs),
        "lost_pairs": sorted(set(control) - set(pairs)),
        "cases_with_another_pool": sum(a["pool"] != b["pool"] for a, b in pairs.values()),
        "cases_with_another_context": sum(a["sent"] != b["sent"] for a, b in pairs.values()),
        "critical_facts_lost": sum(gold.critical_fact_losses(a, b) for a, b in pairs.values()),
        "cases_with_a_critical_fact_lost": sum(
            gold.critical_fact_losses(a, b) > 0 for a, b in pairs.values()
        ),
        "metrics": {},
    }
    for metric in gold.METRICS:
        measured = {
            case_id: (a[metric], b[metric])
            for case_id, (a, b) in pairs.items()
            if a[metric] is not None and b[metric] is not None
        }
        if not measured:
            result["metrics"][metric] = None
            continue
        differences = {case_id: b - a for case_id, (a, b) in measured.items()}
        result["metrics"][metric] = {
            **power.pair_variance(differences, families),
            "control_mean": sum(a for a, _ in measured.values()) / len(measured),
            "arm_mean": sum(b for _, b in measured.values()) / len(measured),
            "losses": sum(value < 0 for value in differences.values()),
            "gains": sum(value > 0 for value in differences.values()),
        }
    return result


def populations(
    registered: Mapping[str, Any],
    family_of: Mapping[str, str],
    pilot: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, list[str]], dict[str, dict[str, list[int]]]]:
    """The development case–family graph and the cluster sizes of every population of a split.

    Clusters are the components of the whole split, as the decision rule counts them; a
    population keeps of each cluster the cases of its classes.
    """
    sizes: dict[str, dict[str, list[int]]] = {}
    development: dict[str, list[str]] = {}
    for name, summary in registered["splits"].items():
        own = pilot if name == "development" else ()
        graph = split.case_families(summary["positions"], family_of, own)
        if name == "development":
            development = graph
        classes = {
            f"position-{place['position']}": place["primary_class"]
            for place in summary["positions"]
            if place["seed"] is not None
        }
        classes.update({case["case_id"]: case["primary_class"] for case in own})
        clusters = ruler.family_clusters(graph)
        sizes[name] = {
            population: sorted(
                (
                    count
                    for count in (
                        sum(classes[case] in members for case in cluster) for cluster in clusters
                    )
                    if count
                ),
                reverse=True,
            )
            for population, members in POPULATIONS.items()
        }
        if sizes[name]["all cases"] != summary["cluster_sizes"]:
            raise ValueError(f"{name}: the clusters differ from the registered split")
    return development, sizes


def scenario_rows(
    sizes: Mapping[str, Mapping[str, Sequence[int]]], pilot: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """What each split can show: the registered grid for every population, the pilot's spreads
    for the population the gold metrics are measured on.

    The intra-cluster correlation is bracketed by 0 and 1 around the pilot's estimate, which
    rests on a few clusters of two cases or more. A row at correlation 1 takes the Student
    quantile: there the sample is the clusters. Only the perturbations whose numbers the
    registration takes give rows.
    """
    pilot = _used(pilot)
    estimates = _estimates(pilot)

    def correlations(estimate: float | None) -> list[tuple[str, float]]:
        middle = [] if estimate is None else [("pilot estimate", estimate)]
        return [("independent cases", 0.0), *middle, ("a cluster moves as one case", 1.0)]

    def scenario(variance: float, cluster_sizes: Sequence[int], icc: float, share: float) -> Any:
        return power.scenario(
            variance, cluster_sizes, icc, differing_share=share, student=icc == 1.0
        )

    rows: list[dict[str, Any]] = []
    for name, by_population in sizes.items():
        for population, cluster_sizes in by_population.items():
            if len(cluster_sizes) < 2:
                continue
            for variance in SCENARIO_VARIANCES:
                for label, icc in correlations(max(estimates) if estimates else None):
                    rows.append(
                        {
                            "source": "grid",
                            "split": name,
                            "population": population,
                            "correlation": label,
                            **scenario(variance, cluster_sizes, icc, variance),
                        }
                    )
        cluster_sizes = by_population[GOLD_EVIDENCE]
        for arm, comparison in pilot.items():
            for metric, stats in comparison["metrics"].items():
                if stats is None or not stats["variance"]:
                    continue
                for label, icc in correlations(stats["intraclass_correlation"]):
                    rows.append(
                        {
                            "source": f"pilot:{arm}",
                            "metric": metric,
                            "split": name,
                            "population": GOLD_EVIDENCE,
                            "correlation": label,
                            **scenario(
                                stats["variance"], cluster_sizes, icc, stats["differing_share"]
                            ),
                        }
                    )
    return rows


def _used(pilot: Mapping[str, Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    """The perturbations whose numbers the registration takes."""
    return {arm: found for arm, found in pilot.items() if found.get("variance_used", True)}


def _or_one(estimate: float | None) -> float:
    return 1.0 if estimate is None else estimate


def _estimates(pilot: Mapping[str, Mapping[str, Any]]) -> list[float]:
    return [
        stats["intraclass_correlation"]
        for comparison in pilot.values()
        for stats in comparison["metrics"].values()
        if stats is not None and stats["intraclass_correlation"] is not None
    ]


def registered_mde(
    sizes: Mapping[str, Mapping[str, Sequence[int]]], pilot: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """One row a split and deciding metric: the MDE the campaign registers.

    The variance is the larger of the grid value and the variances the pilot's usable
    perturbations give the metric, so a pilot can raise the MDE and cannot lower it. The
    published MDE — the ``mde`` of the row, with its powers — is taken at correlation 1 with
    the Student quantile: the sample is then the clusters. The MDE of independent cases and
    the MDE at the pilot's estimate of the correlation stand beside it as description.
    """
    pilot = _used(pilot)
    estimates = _estimates(pilot)
    rows: list[dict[str, Any]] = []
    for name, by_population in sizes.items():
        for metric, population in DECIDING.items():
            variance = share = REGISTERED_GRID_VARIANCE
            estimate, source = (max(estimates) if estimates else None), "grid"
            # Equal variances: the larger correlation, none read as 1, then the arm's name.
            measured = max(
                (
                    (stats["variance"], _or_one(stats["intraclass_correlation"]), arm)
                    for arm, comparison in pilot.items()
                    for stats in [comparison["metrics"].get(metric)]
                    if stats is not None and stats["variance"] is not None
                ),
                default=None,
            )
            if measured is not None and measured[0] > REGISTERED_GRID_VARIANCE:
                stats = pilot[measured[2]]["metrics"][metric]
                variance, share = stats["variance"], stats["differing_share"]
                estimate, source = stats["intraclass_correlation"], f"pilot:{measured[2]}"
            cluster_sizes = by_population[population]
            row: dict[str, Any] = {
                "split": name,
                "metric": metric,
                "population": population,
                "variance_source": source,
                "n": sum(cluster_sizes),
                "clusters": len(cluster_sizes),
            }
            if len(cluster_sizes) < 2:
                rows.append(row)
                continue
            published = power.scenario(
                variance, cluster_sizes, 1.0, differing_share=share, student=True
            )
            independent = power.scenario(variance, cluster_sizes, 0.0, differing_share=share)
            at_estimate = None
            if estimate is not None:
                at_estimate = power.scenario(
                    variance, cluster_sizes, estimate, student=estimate == 1.0
                )["mde"]
            rows.append(
                {
                    **row,
                    **published,
                    "mde_independent_cases": independent["mde"],
                    "correlation_estimate": estimate,
                    "mde_at_correlation_estimate": at_estimate,
                }
            )
    return rows


def measure(
    directories: Mapping[str, Path],
    *,
    verified: Path | None = None,
    questions: Path | None = None,
    families: Path | None = None,
    registered: Path | None = None,
    archive: Path | None = None,
    sha256: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """The pilot's document: per-case gold metrics, paired differences and the power tables.

    The verified cases, the question file, the family map and the split are read at their
    registered SHA-256. A caller that names other files names their hashes too — the tests do,
    the command line cannot.
    """
    verified, questions = verified or VERIFIED, questions or QUESTIONS
    families, registered = families or FAMILIES, registered or split.REGISTERED
    expected = REGISTERED_SHA256 if sha256 is None else sha256
    named = {"verified": verified, "questions": questions, "families": families}
    for name, path in {**named, "split": registered}.items():
        if parity.file_sha(path) != expected[name]:
            raise ValueError(f"{name}: not the registered file")
    arms = {name: load_arm(directory) for name, directory in directories.items()}
    check_arms(arms)
    manifest = arms[CONTROL]["manifest"]
    pilot = read_lines(verified)
    by_id = {case["case_id"]: case for case in pilot}
    if gold_questions(pilot) != questions.read_text(encoding="utf-8"):
        raise ValueError("the question file is not the verified cases with gold spans")
    if manifest["ledger_entry"]["task"] != TASK or [
        (case["case_id"], case["query"]) for case in manifest["cases"]
    ] != [(row["case_id"], row["question"]) for row in read_lines(questions)]:
        raise ValueError("the runs are not the registered pilot")
    ran = [by_id[case["case_id"]] for case in manifest["cases"]]
    corpus = check_labels(ran, manifest)
    chunks = load_chunks(archive or ARCHIVE, manifest)
    development, sizes = populations(
        parity.read(registered), split.family_index(parity.read(families)), pilot
    )
    metrics = {name: arm_metrics(arm, by_id, chunks, corpus) for name, arm in arms.items()}
    bound = index_bound(ran, chunks, corpus)
    # A match that finds nothing reads like a perturbation that moved nothing: say which it is.
    unreadable = [NO_SPAN_IN_INDEX] if not bound["held_whole_by_a_chunk"] else []
    if not any(found and found["evidence_recall_pool"] for found in metrics[CONTROL].values()):
        unreadable.append(NO_SPAN_IN_CONTROL)
    comparisons = {}
    for name, values in metrics.items():
        if name == CONTROL:
            continue
        comparison = compare(metrics[CONTROL], values, development)
        because = [*unreadable, *([LOST_PAIR] if comparison["lost_pairs"] else [])]
        comparisons[name] = {
            **comparison,
            "variance_used": not because,
            "variance_unused_because": because,
        }
    return {
        "version": VERSION,
        "task": TASK,
        "arms": {
            name: {
                "moved": ARMS[name],
                "run_sha256": arm["identity"],
                "contexts_sha256": arm["contexts_sha256"],
                "addresses_sha256": arm["addresses_sha256"],
                "collected": sum(value is not None for value in metrics[name].values()),
                "excluded": sorted(cid for cid, value in metrics[name].items() if value is None),
            }
            for name, arm in arms.items()
        },
        "provenance": {
            "code_sha": manifest["code_sha"],
            "source_sha256": manifest["source_sha256"],
            "corpus_sha256": corpus,
            "chunker_version": manifest["chunker_version"],
            "index_receipt_sha256": manifest["index_receipt_sha256"],
            "config": manifest["config"],
            "llm": manifest["llm"],
            "reranker": manifest["reranker"],
            "verified_cases_sha256": parity.file_sha(verified),
            "questions_sha256": parity.file_sha(questions),
            "families_sha256": parity.file_sha(families),
            "split_sha256": parity.file_sha(registered),
            "match_rule": gold.MATCH_RULE,
            "fact_label_rule": FACT_LABEL_RULE["version"],
            "fact_matcher": ruler.FACT_MATCHER_VERSION,
            "measure_code_sha256": {name: parity.file_sha(ROOT / name) for name in CODE_FILES},
        },
        "index_bound": bound,
        "cases": {
            case["case_id"]: {name: metrics[name][case["case_id"]] for name in arms}
            for case in manifest["cases"]
        },
        "pilot": comparisons,
        "cluster_sizes": sizes,
        "zero_loss_cases": power.cases_for_zero_loss_bound(),
        "registered_mde": registered_mde(sizes, comparisons),
        "tables": scenario_rows(sizes, comparisons),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    cases = commands.add_parser("cases")
    cases.add_argument("--write", action="store_true")
    exporting = commands.add_parser("export")
    exporting.add_argument("--run", type=Path, required=True)
    exporting.add_argument("--out", type=Path, required=True)
    measuring = commands.add_parser("measure")
    measuring.add_argument("--arm", action="append", required=True, metavar="NAME=DIR")
    measuring.add_argument("--out", type=Path, required=True)
    measuring.add_argument("--archive", type=Path, help="the chunk archive of the index")
    args = parser.parse_args(argv)
    if args.command == "cases":
        text = gold_questions(read_lines(VERIFIED))
        if args.write:
            QUESTIONS.write_text(text, encoding="utf-8", newline="\n")
        elif QUESTIONS.read_text(encoding="utf-8") != text:
            print("the question file differs from the verified cases with gold spans")
            return 1
        print(len(text.splitlines()), "cases")
        return 0
    if args.command == "export":
        print(json.dumps(export(args.run, args.out), sort_keys=True))
        return 0
    directories = {}
    for pair in args.arm:
        name, _, directory = pair.partition("=")
        if name in directories or not directory:
            parser.error(f"--arm needs NAME=DIR once per arm: {pair}")
        directories[name] = Path(directory)
    document = measure(directories, archive=args.archive)
    _write_once(args.out, dump(document))
    for name, comparison in document["pilot"].items():
        if not comparison["variance_used"]:
            print(name, "not used:", "; ".join(comparison["variance_unused_because"]))
        for metric, stats in comparison["metrics"].items():
            if stats is not None:
                print(
                    name,
                    metric,
                    {key: stats[key] for key in ("n", "clusters", "mean", "variance")},
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""The pilot on the external bases (plan slice 1.6): how a base's primary metric spreads.

Two arms of the production retrieval path run over the registered selection ``pilot`` of a base
(``evaluation/external_parts.json``): the control and ``pool30``, the perturbation of the variance
pilot of plan step 1.3c that gives the reranker 30 candidates a lane in place of 20. The
perturbation is not a mechanism candidate and nothing is chosen from it. It is run because the
interval of a comparison is made of paired differences, and the spread of such differences can
only be seen between two arms; the runs also say what a question of the base costs in seconds
at every stage.

    python -m scripts.external_pilot measure --base NAME --base-dir DIR \
        --arm control=RUN --arm pool30=RUN --out FILE [--aggregates FILE]
    python -m scripts.external_pilot sizes [--pilot BASE=FILE ...] --out FILE

``sizes`` reads the registered parts and, when given, the documents ``measure`` wrote, and
prints what a comparison on every part can show; without a pilot it stands on the grid variance.
With the pilots of both bases it also prints what step 1 of acceptance 4.1 reads, by the
criterion the spec registers before the pilot runs (``step_one``): one question a page, and as
many pages as two arms can read under the ceiling.

``measure`` runs on the host that holds the base. It reads the gold of the questions, the
corpus, the chunk archive and the stage records of the two runs, and writes numbers, case ids
and digests: no question, no text, no name of a document and no list of retrieved chunks
(``evaluation/external_bases.json``, "redistribution"). It refuses to write a document in which
a string is the name of a document of the base or holds a question of the selection. The
document it writes holds a row of numbers for every question and stays on the host;
``--aggregates`` writes it once more without those rows and with its SHA-256, and that copy is
what leaves the host. ``sizes`` reads either.

Gold is read by ``external-gold/range-coverage-v1`` (``evaluation/external_gold.py``) at the
points of the path a run records:

    vector    the candidates of the vector lane
    bm25      the candidates of the lexical lane
    pool      the fused pool the reranker received
    ranked    the reranked seeds, the first ``TOP`` of them
    expanded  the context after parent expansion, before grading
    sent      the context left after grading — what a generator would be sent

ConditionalQA is read at all six: an evidence group is satisfied at a point when the places of
the chunks present there cover one of its alternatives, ``evidence_recall`` is the share of
satisfied groups and ``all_evidence_coverage`` is 1 when every group is satisfied. Its primary
metric is ``all_evidence_coverage`` at ``sent``. WixQA is read at the first four, its runs stop
after retrieval: ``gold_article`` is 1 when a chunk of a gold article is present and
``gold_articles`` is the share of gold articles that have one. Its primary metric is
``gold_article`` at ``ranked``.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import statistics
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from evaluation import external_bases as bases
from evaluation import external_gold as gold
from evaluation import external_parts as parts
from evaluation import power
from evaluation.semantic_ruler import family_clusters
from scripts import external_base
from scripts import production_baseline as baseline
from scripts import production_parity as parity

ROOT = Path(__file__).resolve().parents[1]
VERSION = "external-pilot/v1"
SELECTION = "pilot"
CONTROL = "control"
# The control and the perturbation `pool30` of scripts/variance_pilot.py; a test holds them equal.
ARMS: dict[str, dict[str, int]] = {CONTROL: {}, "pool30": {"retrieval_top_k": 30}}
TOP = 5
LANES = ("vector", "bm25", "pool", "ranked")
# What a base's pilot is read by: the last stage its runs reach, the points of the path, the
# metrics of a point, the primary metric with its point, and the unit of a cluster.
BASES: dict[str, dict[str, Any]] = {
    "conditionalqa": {
        "last_stage": "grade",
        "points": (*LANES, "expanded", "sent"),
        "metrics": ("all_evidence_coverage", "evidence_recall"),
        "primary": ("sent", "all_evidence_coverage"),
        "cluster_unit": "document",
    },
    "wixqa": {
        "last_stage": "retrieve",
        "points": LANES,
        "metrics": ("gold_article", "gold_articles"),
        "primary": ("ranked", "gold_article"),
        "cluster_unit": "gold-article set",
    },
}
# What the settings of an arm may not move for the context budgets of the arms to be equal.
BUDGET = (
    "rerank_top_k",
    "parent_expansion",
    "parent_expansion_window",
    "parent_expansion_max_chars",
)
SHARED = (
    "code_sha",
    "source_sha256",
    "runtime",
    "cases",
    "base",
    "index_receipt_sha256",
    "source_manifest_sha256",
    "chunker_version",
    "llm",
    "reranker",
)
BLOCK = (
    "name",
    "tenant",
    "collection",
    "revision",
    "corpus_sha256",
    "selection",
    "part",
    "cases_sha256",
)
CODE_FILES = (
    "scripts/external_pilot.py",
    "evaluation/external_gold.py",
    "evaluation/external_parts.py",
    "evaluation/external_bases.py",
    "evaluation/power.py",
    "evaluation/semantic_ruler.py",
)
# The strata of a base whose primary metric gets a variance of its own, beside all questions.
STRATA: dict[str, tuple[str, ...]] = {"conditionalqa": ("several_sections",), "wixqa": ()}
# What a size is registered for: the strata of a base, each with the counts of the registration
# that give its clusters.
SIZED: dict[str, dict[str, str]] = {
    "conditionalqa": {
        "primary": "primary_by_document",
        "several_sections": "several_sections_by_document",
    },
    "wixqa": {"all": "cluster_sizes"},
}
SIZES_VERSION = "external-sizes/v1"
GRID_VARIANCE = 0.10
# The selections by documents a size is printed for: so many documents, so many questions each,
# and every document that carries a question of the stratum with one question each. The rule
# of a selection gives other counts as well.
DOCUMENTS = (25, 50, 75, 100, 125, 150)
PER_DOCUMENT = (1, 2, 3, 4)
# The ceiling of step 1 of acceptance 4.1: the nights of eight hours the plan gives the step.
STEP_ONE_NIGHTS = 8
NIGHT_SECONDS = 8 * 3600
# The ceiling of the entity graph of a base: the nights of eight hours its build may take.
GRAPH_NIGHTS = 3
# Lost pairs above this share make the numbers of a base NOT_EVIDENCE, as the collection rule
# of the spec does for excluded cases.
MAX_LOST_SHARE = 0.10
# Why a pilot's variance is not used, as the document words it.
LOST_PAIRS = "more than a tenth of the pairs were not measured"
NO_GOLD_IN_INDEX = "no question has all its gold in the chunks of the index"
NO_GOLD_IN_CONTROL = "the control finds the gold of no question"


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False) + "\n"


def load_rows(run: Path, manifest: Mapping[str, Any], base: str) -> dict[str, dict[str, Any]]:
    """The record every case of a run has at the last stage the pilot of the base reaches."""
    identity = parity.digest(manifest)
    last = BASES[base]["last_stage"]
    baseline.require_no_aborts(run, baseline.STAGES[: baseline.STAGES.index(last) + 1])
    rows = {}
    for case in manifest["cases"]:
        target = run / last / f"{case['case_id']}.json"
        if not target.exists():
            raise ValueError(f"the run has not finished the stage {last}: {case['case_id']}")
        rows[case["case_id"]] = baseline.load_case(target, identity, run)
    return rows


def check_arms(manifests: Mapping[str, Mapping[str, Any]], block: Mapping[str, Any]) -> None:
    """The arms are the registered two, on the registered selection, and differ in one count."""
    if set(manifests) != set(ARMS):
        raise ValueError("the pilot is the control and its registered perturbation")
    control = manifests[CONTROL]
    moved = {key for overrides in ARMS.values() for key in overrides}
    if moved.intersection(BUDGET):
        raise ValueError("an arm of the pilot moves the context budget")

    def datasets(manifest: Mapping[str, Any]) -> dict[str, tuple[str, int]]:
        return {name: (d["sha256"], d["count"]) for name, d in manifest["datasets"].items()}

    def unmoved(manifest: Mapping[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in manifest["config"].items() if key not in moved}

    for name, manifest in manifests.items():
        registered = manifest.get("base") or {}
        if any(registered.get(key) != block[key] for key in BLOCK):
            raise ValueError(f"{name}: not a run on the registered selection of the base")
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


def load_chunks(directory: Path, manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The chunk archive of the base, held to the index the run read and to the base's tenant."""
    archive = directory / "chunks.json.gz"
    if parity.file_sha(archive) != manifest["index_receipt"]["corpus_sha256"]:
        raise ValueError("the chunk archive is not the one the index was built from")
    payload = json.loads(gzip.decompress(archive.read_bytes()))
    if payload.get("tenant_id") != manifest["base"]["tenant"]:
        raise ValueError("the chunk archive belongs to another tenant")
    chunks: list[dict[str, Any]] = payload["chunks"]
    return chunks


class Places:
    """Where the chunks of a base stand in their documents, and what a set of chunks covers."""

    def __init__(
        self,
        chunks: Sequence[Mapping[str, Any]],
        sources: Mapping[str, gold.Source] | None,
        overlap: int,
        window: int,
    ) -> None:
        self.chunks = chunks
        self.window = window
        self.source = [str((chunk.get("metadata") or {}).get("source") or "") for chunk in chunks]
        self.of_source: dict[str, list[int]] = {}
        for member, name in enumerate(self.source):
            self.of_source.setdefault(name, []).append(member)
        self.places = gold.locate_chunks(chunks, sources, overlap) if sources is not None else None
        # Chunks whose body has no place in its document; None when the base is read by articles.
        self.without_place = (
            None if self.places is None else sum(place is None for place in self.places)
        )

    def by_document(self, members: Sequence[int]) -> dict[str, list[gold.Range]]:
        """The places of a set of chunks, by document; needs the documents of the base.

        A chunk without a place stops the measure: what it holds would be counted as absent.
        """
        if self.places is None:
            raise ValueError("the documents of the base were not read")
        held: dict[str, list[gold.Range]] = {}
        for member in dict.fromkeys(members):
            place = self.places[member]
            if place is None:
                raise ValueError("a chunk that is read has no place in its document")
            held.setdefault(self.source[member], []).append(place)
        return held

    def members(self, documents: Sequence[Mapping[str, Any]]) -> list[int]:
        """The chunks the documents of a context were joined from."""
        found: list[int] = []
        for document in documents:
            seed = document["metadata"].get("chunk_index")
            if type(seed) is not int or not 0 <= seed < len(self.chunks):
                raise ValueError("a document of a context names no chunk of the archive")
            found.extend(gold.expansion_members(document["text"], seed, self.chunks, self.window))
        return found


def points(base: str, row: Mapping[str, Any], places: Places) -> dict[str, list[int]]:
    """The chunks present at every point of the path a record of the base holds."""
    present = {
        "vector": list(row["vector"]),
        "bm25": list(row["bm25"]),
        "pool": list(row["pool"]),
        "ranked": list(row["ranked"])[:TOP],
    }
    if "expanded" in BASES[base]["points"]:
        present["expanded"] = places.members(row["expanded_documents"])
        present["sent"] = places.members(row["documents"])
    return present


def read_gold(
    base: str, case: Mapping[str, Any], members: Sequence[int], places: Places
) -> dict[str, float]:
    """The metrics of one question over the chunks present at one point."""
    if base == "wixqa":
        wanted = set(case["gold_sources"])
        held = wanted.intersection(places.source[member] for member in members)
        return {"gold_article": float(bool(held)), "gold_articles": len(held) / len(wanted)}
    by_document = places.by_document(members)
    satisfied = sum(
        any(
            gold.covered((a["start"], a["end"]), by_document.get(a["source_id"], ()))
            for a in group["alternatives"]
        )
        for group in case["evidence_groups"]
    )
    groups = len(case["evidence_groups"])
    return {
        "all_evidence_coverage": float(satisfied == groups),
        "evidence_recall": satisfied / groups,
    }


def gold_documents(base: str, case: Mapping[str, Any]) -> list[str]:
    """The documents the gold of a question stands in."""
    if base == "wixqa":
        return sorted(set(case["gold_sources"]))
    return sorted({a["source_id"] for g in case["evidence_groups"] for a in g["alternatives"]})


def reachable(base: str, case: Mapping[str, Any], places: Places) -> bool:
    """Whether the chunks of the index can give a question the primary metric 1.

    Every evidence group of a ConditionalQA question; one gold article of a WixQA question.
    """
    metric = BASES[base]["primary"][1]
    members = [m for name in gold_documents(base, case) for m in places.of_source.get(name, [])]
    return read_gold(base, case, members, places)[metric] == 1.0


def case_record(
    base: str, case: Mapping[str, Any], row: Mapping[str, Any], places: Places
) -> tuple[dict[str, Any], dict[str, list[int]]]:
    """What one arm gave one question, and the chunks it had at every point.

    The record holds the metrics at every point, the sizes and the seconds, and is what is
    written. The chunks are returned beside it for the comparison of the arms and are not.
    """
    if row["status"] != "ok":
        exclusion = row["exclusion"]
        excluded = {
            "status": "excluded",
            "stage": exclusion["stage"],
            "error_type": exclusion["error_type"],
        }
        return excluded, {}
    present = points(base, row, places)
    record: dict[str, Any] = {
        "status": "ok",
        "points": {
            name: read_gold(base, case, members, places) for name, members in present.items()
        },
        "candidates": {name: len(present[name]) for name in LANES},
        "seconds": {key: value / 1000 for key, value in sorted(row["timings_ms"].items())},
    }
    if "sent" in present:
        for name, key in (("expanded", "expanded_documents"), ("sent", "documents")):
            record[f"{name}_documents"] = len(row[key])
            record[f"{name}_characters"] = sum(len(document["text"]) for document in row[key])
    return record, present


def spread(values: Sequence[float]) -> dict[str, float]:
    ordered = sorted(values)

    def quantile(share: float) -> float:
        position = (len(ordered) - 1) * share
        low, high = math.floor(position), math.ceil(position)
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)

    return {
        "n": len(ordered),
        "mean": math.fsum(ordered) / len(ordered),
        "p50": quantile(0.5),
        "p95": quantile(0.95),
        "total": math.fsum(ordered),
    }


def arm_summary(base: str, records: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """The means of one arm over the questions it measured."""
    measured = [record for record in records.values() if record["status"] == "ok"]
    summary: dict[str, Any] = {
        "cases": len(records),
        "measured": len(measured),
        "excluded": {
            case_id: {key: record[key] for key in ("stage", "error_type")}
            for case_id, record in records.items()
            if record["status"] != "ok"
        },
    }
    if not measured:
        return summary
    summary["points"] = {
        point: {
            metric: math.fsum(record["points"][point][metric] for record in measured)
            / len(measured)
            for metric in BASES[base]["metrics"]
        }
        for point in BASES[base]["points"]
    }
    summary["candidates"] = {
        name: spread([record["candidates"][name] for record in measured]) for name in LANES
    }
    keys = sorted({key for record in measured for key in record["seconds"]})
    summary["seconds"] = {
        key: spread([record["seconds"][key] for record in measured if key in record["seconds"]])
        for key in keys
    }
    for name in ("expanded_documents", "expanded_characters", "sent_documents", "sent_characters"):
        if name in measured[0]:
            summary[name] = spread([record[name] for record in measured])
    return summary


def clusters_of(base: str, cases: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    """What joins the questions of a base into clusters: the document, or the gold articles."""
    if base == "conditionalqa":
        return {case["case_id"]: [case["document"]] for case in cases}
    return {case["case_id"]: list(case["gold_sources"]) for case in cases}


def compare(
    base: str,
    arm: Mapping[str, Mapping[str, Any]],
    control: Mapping[str, Mapping[str, Any]],
    families: Mapping[str, Sequence[str]],
    present: Mapping[str, Mapping[str, Sequence[int]]],
    present_control: Mapping[str, Mapping[str, Sequence[int]]],
    strata: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    """The paired differences arm − control of every metric at every point.

    ``chunks_differ`` counts, for every point, the pairs whose arms had different chunks there:
    a metric can move in no other pair. ``primary_by_stratum`` gives the differences of the
    primary metric over the pairs of each stratum, clustered among themselves.
    """
    paired = [
        case_id
        for case_id in control
        if control[case_id]["status"] == "ok" and arm[case_id]["status"] == "ok"
    ]
    result: dict[str, Any] = {
        "pairs": len(paired),
        "lost": [case_id for case_id in control if case_id not in paired],
        "points": {},
    }
    if not paired:
        return result
    for point in BASES[base]["points"]:
        result["points"][point] = {
            metric: power.pair_variance(
                {
                    case_id: arm[case_id]["points"][point][metric]
                    - control[case_id]["points"][point][metric]
                    for case_id in paired
                },
                families,
            )
            for metric in BASES[base]["metrics"]
        }
    result["chunks_differ"] = {
        point: sum(set(present[c][point]) != set(present_control[c][point]) for c in paired)
        for point in BASES[base]["points"]
    }
    if "sent" in BASES[base]["points"]:
        result["sent_characters"] = power.pair_variance(
            {c: float(arm[c]["sent_characters"] - control[c]["sent_characters"]) for c in paired},
            families,
        )
    point, metric = BASES[base]["primary"]
    result["primary_by_stratum"] = {}
    for stratum, members in strata.items():
        chosen = [case_id for case_id in paired if case_id in set(members)]
        if chosen:
            result["primary_by_stratum"][stratum] = power.pair_variance(
                {
                    case_id: arm[case_id]["points"][point][metric]
                    - control[case_id]["points"][point][metric]
                    for case_id in chosen
                },
                families,
            )
    return result


def usable(
    base: str,
    compared: Mapping[str, Any],
    control: Mapping[str, Mapping[str, Any]],
    in_index: int,
) -> str | None:
    """Why the variance of the primary metric is not used; None when it is."""
    point, metric = BASES[base]["primary"]
    if len(compared["lost"]) > MAX_LOST_SHARE * (compared["pairs"] + len(compared["lost"])):
        return LOST_PAIRS
    if not in_index:
        return NO_GOLD_IN_INDEX
    if not any(
        record["points"][point][metric] for record in control.values() if record["status"] == "ok"
    ):
        return NO_GOLD_IN_CONTROL
    return None


def strings(value: Any) -> Iterator[str]:
    """Every string of a document, the keys of its mappings too."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from strings(item)


def without_text(
    document: dict[str, Any], cases: Sequence[Mapping[str, Any]], places: Places
) -> dict[str, Any]:
    """The document, refused when it names a document of the base or holds a question.

    The measure copies numbers, ids, stages and error types and nothing else of a run; this
    holds a later change of it to the rule of what leaves the host.
    """
    held = set(strings(document))
    if held.intersection(places.source) or any(
        case["query"] in text for case in cases for text in held
    ):
        raise ValueError("the document of the measure would carry text of the base")
    return document


def measure(base: str, directory: Path, runs: Mapping[str, Path]) -> dict[str, Any]:
    """The pilot of one base: what each arm found, how the differences spread, what it cost."""
    if base not in BASES:
        raise ValueError(f"the pilot is not registered for the base: {base}")
    converted = bases.registration()
    drawn = parts.registration()
    block, _ = baseline.external_base(base, directory, SELECTION)
    manifests = {name: baseline.load_manifest(run) for name, run in runs.items()}
    check_arms(manifests, block)
    control = manifests[CONTROL]
    rows = {name: load_rows(run, manifests[name], base) for name, run in runs.items()}
    ids = parts.read(drawn, base, selection=SELECTION)
    if [case["case_id"] for case in control["cases"]] != ids:
        raise ValueError("the runs did not read the registered selection")
    questions = directory / "selections" / f"{SELECTION}.questions.jsonl"
    if parity.file_sha(questions) != control["datasets"][SELECTION]["sha256"]:
        raise ValueError("the runs read another question file")
    by_id = {case["case_id"]: case for case in parts.load_cases(directory, base, converted)}
    cases = [by_id[case_id] for case_id in ids]
    if not all(gold_documents(base, case) for case in cases):
        raise ValueError("a question of the selection carries no gold")

    chunks = load_chunks(directory, control)
    sources = None
    if "expanded" in BASES[base]["points"]:
        corpus, sources = external_base._corpus(directory)
        if corpus["corpus_sha256"] != block["corpus_sha256"]:
            raise ValueError("the corpus is not the registered conversion of the base")
    config = control["config"]
    places = Places(
        chunks, sources, converted["chunking"]["chunk_overlap"], config["parent_expansion_window"]
    )
    records: dict[str, dict[str, dict[str, Any]]] = {name: {} for name in ARMS}
    present: dict[str, dict[str, dict[str, list[int]]]] = {name: {} for name in ARMS}
    for name in ARMS:
        for case in cases:
            case_id = case["case_id"]
            records[name][case_id], present[name][case_id] = case_record(
                base, case, rows[name][case_id], places
            )
    families = clusters_of(base, cases)
    clusters = family_clusters(families)
    number = {case_id: index for index, cluster in enumerate(clusters) for case_id in cluster}
    in_index = [reachable(base, case, places) for case in cases]
    strata = {
        stratum: [case["case_id"] for case in cases if parts.in_stratum(base, case, stratum)]
        for stratum in STRATA[base]
    }
    compared = {
        name: compare(
            base,
            records[name],
            records[CONTROL],
            families,
            present[name],
            present[CONTROL],
            strata,
        )
        for name in ARMS
        if name != CONTROL
    }
    point, metric = BASES[base]["primary"]
    for name, result in compared.items():
        reason = usable(base, result, records[CONTROL], sum(in_index))
        result["primary"] = {
            "point": point,
            "metric": metric,
            "used": reason is None,
            "not_used_because": reason,
            **({} if not result["pairs"] else result["points"][point][metric]),
        }
    registrations = {
        path.name: parity.file_sha(path) for path in (bases.REGISTRATION, parts.REGISTRATION)
    }
    document = {
        "version": VERSION,
        "base": base,
        "selection": SELECTION,
        "match_rule": gold.MATCH_RULE,
        "top": TOP,
        "primary": {"point": point, "metric": metric},
        "cases": len(cases),
        "clusters": {
            "unit": BASES[base]["cluster_unit"],
            "count": len(clusters),
            "sizes": sorted((len(cluster) for cluster in clusters), reverse=True),
        },
        "gold_in_index": {"cases": sum(in_index), "of": len(cases)},
        "chunks_without_a_place": places.without_place,
        "strata": {stratum: len(members) for stratum, members in strata.items()},
        "arms": {name: arm_summary(base, records[name]) for name in ARMS},
        "pairs": compared,
        "per_case": [
            {
                "case_id": case["case_id"],
                "cluster": number[case["case_id"]],
                "gold_in_index": held,
                "arms": {name: records[name][case["case_id"]] for name in ARMS},
            }
            for case, held in zip(cases, in_index, strict=True)
        ],
        "provenance": {
            "code_sha": control["code_sha"],
            "source_sha256": control["source_sha256"],
            "runtime": control["runtime"],
            "runs": {
                name: {
                    "run_sha256": parity.digest(manifests[name]),
                    "config_sha256": parity.digest(manifests[name]["config"]),
                    "config_overrides": manifests[name].get("config_overrides", {}),
                    "task": manifests[name]["ledger_entry"]["task"],
                }
                for name in ARMS
            },
            "config": config,
            "context_budget": {key: config[key] for key in BUDGET},
            "base": {key: block[key] for key in BLOCK},
            "archive_sha256": control["index_receipt"]["corpus_sha256"],
            "checkpoint_sha256": control["index_receipt"]["checkpoint_sha256"],
            "index_receipt_sha256": control["index_receipt_sha256"],
            "embedder": control["index_receipt"]["embedder_manifest"],
            "chunking": converted["chunking"],
            "converter_version": converted["converter_version"],
            "llm": control["llm"],
            "reranker": control["reranker"],
            "registrations_of_the_runs": {
                name: entry["sha256"] for name, entry in control["base"]["registrations"].items()
            },
            "registrations_of_the_measure": registrations,
            "measure_code": {
                name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in CODE_FILES
            },
        },
    }
    return without_text(document, cases, places)


def aggregates(report: Mapping[str, Any], text: str) -> dict[str, Any]:
    """What of a measured pilot leaves the host: all of it but the rows of single questions.

    ``text`` is the document as ``measure`` wrote it; it stays beside the runs, and its SHA-256
    goes with the aggregates.
    """
    kept = {key: value for key, value in report.items() if key != "per_case"}
    kept["measure_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return kept


def designs(
    base: str, block: Mapping[str, Any], stratum: str
) -> list[tuple[dict[str, int] | None, list[int]]]:
    """The whole of a part and a grid of its selections by documents, each with its clusters.

    A selection by documents is the registered kind (``external_parts.RULES``, "selection"): the
    first documents that carry at least so many questions of the stratum, and so many of each.
    The grid is ``DOCUMENTS`` by ``PER_DOCUMENT`` and, with one question each, every document
    that carries a question of the stratum. Only ConditionalQA has them; a part of WixQA is
    sized whole.
    """
    counted = block[SIZED[base][stratum]]
    if base != "conditionalqa":
        whole = [int(size) for size, count in counted.items() for _ in range(count)]
        return [(None, sorted(whole, reverse=True))]
    found: list[tuple[dict[str, int] | None, list[int]]] = [
        (None, sorted((size for size in counted if size), reverse=True))
    ]
    for per_document in PER_DOCUMENT:
        carrying = sum(size >= per_document for size in counted)
        offered = [documents for documents in DOCUMENTS if documents <= carrying]
        if per_document == 1 and carrying and carrying not in offered:
            offered.append(carrying)
        found.extend(
            ({"documents": documents, "per_document": per_document}, [per_document] * documents)
            for documents in offered
        )
    return found


def scenario(
    variance: float,
    clusters: Sequence[int],
    correlation: float,
    share: float | None,
    *,
    student: bool = False,
) -> dict[str, Any]:
    """A row of ``evaluation/power.py`` and the true gain the whole primary rule needs.

    The rule passes when the point gain is at least the minimally useful effect and the interval
    lies above zero, so with power 0.8 it passes at a true gain of the larger of the two
    thresholds plus the quantile of the power times the standard error. Where the interval is
    the stricter threshold this is the MDE; where the minimally useful effect is, it is more.
    """
    row = power.scenario(variance, clusters, correlation, differing_share=share, student=student)
    reach = statistics.NormalDist().inv_cdf(power.POWER) * row["standard_error"]
    row["effect_for_rule"] = max(power.MUE, row["critical"] * row["standard_error"]) + reach
    return row


def registered_variance(pilot: Mapping[str, Any] | None, stratum: str) -> dict[str, Any]:
    """The variance a size is registered at: the grid value, which a pilot can only raise.

    A pilot whose variance is not used (``usable``) raises it all the same when its measured
    pairs give more than the grid: set aside whole, such a pilot would be read in the favourable
    direction. Its share of differing pairs and its correlation are not taken. The share and the
    correlation of a usable pilot are those of all its measured pairs, in a stratum's row too.
    """
    found = {"grid": GRID_VARIANCE}
    share = None
    correlation = None
    if pilot is not None:
        for name, result in pilot["pairs"].items():
            primary = result["primary"]
            label = f"pilot {name}" if primary["used"] else f"pilot {name}, not usable"
            given = {label: primary}
            if stratum in result.get("primary_by_stratum", {}):
                given[f"{label}, {stratum}"] = result["primary_by_stratum"][stratum]
            for key, estimate in given.items():
                if estimate.get("variance") is not None:
                    found[key] = estimate["variance"]
            if primary["used"]:
                share = primary["differing_share"]
                correlation = primary["intraclass_correlation"]
    source = max(found, key=lambda label: found[label])
    return {
        "variance": found[source],
        "source": source,
        "candidates": found,
        "differing_share": share,
        "correlation": correlation,
    }


def graph_timing_limit(sample_chunks: int, base_chunks: int) -> float:
    """The seconds the timing of the entity graph may take on its sample if the base is to fit.

    The cost of a base is the mean seconds a chunk times its chunks, and the base gets its
    entity graph when that is at most ``GRAPH_NIGHTS`` nights. A sample that has taken longer
    than the ceiling times its share of the base's chunks has settled it: the base cannot fit.
    """
    if not 0 < sample_chunks <= base_chunks:
        raise ValueError("the sample of the timing is not a part of the base")
    return GRAPH_NIGHTS * NIGHT_SECONDS * sample_chunks / base_chunks


def question_seconds(base: str, pilot: Mapping[str, Any]) -> float:
    """The mean seconds a question took the control of a pilot, summed over its stages.

    A lower estimate of what a question costs: it is taken over the measured questions, and the
    loading of the models is outside it.
    """
    if pilot.get("version") != VERSION or pilot.get("base") != base:
        raise ValueError(f"not the pilot of the base: {base}")
    last = baseline.STAGES.index(BASES[base]["last_stage"])
    taken = pilot["arms"][CONTROL]["seconds"]
    return math.fsum(taken[stage]["mean"] for stage in baseline.STAGES[1 : last + 1])


def step_one(
    registered: Mapping[str, Any], pilots: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any] | None:
    """What step 1 of acceptance 4.1 reads, by the criterion registered before the pilot.

    Of WixQA the whole locked part, up to the reranked list. Of ConditionalQA one question a
    page of its locked part, drawn on a stratum: every page that carries a question of the
    stratum when two arms on both bases fit the ceiling at the seconds a question took the
    control of each pilot, and otherwise the first pages that fit. No variance, no correlation
    and no level of a metric enters the count; the variance gives the count its registered MDE.
    The seconds of a pilot whose variance is not used count as those of any other. None until
    both pilots are given.
    """
    if set(pilots) != set(BASES):
        return None
    seconds = {base: question_seconds(base, pilots[base]) for base in sorted(BASES)}
    locked = {base: registered["bases"][base]["parts"]["locked"] for base in BASES}
    ceiling = STEP_ONE_NIGHTS * NIGHT_SECONDS
    articles = 2 * locked["wixqa"]["cases"] * seconds["wixqa"]
    fit = max(0, math.floor((ceiling - articles) / (2 * seconds["conditionalqa"])))
    pages: dict[str, Any] = {}
    for stratum, counted in SIZED["conditionalqa"].items():
        carrying = sum(size >= 1 for size in locked["conditionalqa"][counted])
        read = min(carrying, fit)
        given = registered_variance(pilots["conditionalqa"], stratum)
        pages[stratum] = {
            "pages_with_a_question": carrying,
            "pages_read": read,
            "seconds_of_two_arms": 2 * read * seconds["conditionalqa"],
            "variance": given["variance"],
            "variance_source": given["source"],
        }
        if read >= 2:
            pages[stratum]["registered"] = scenario(
                given["variance"], [1] * read, 1.0, given["differing_share"], student=True
            )
    return {
        "ceiling_seconds": ceiling,
        "seconds_per_question": seconds,
        "wixqa": {"questions": locked["wixqa"]["cases"], "seconds_of_two_arms": articles},
        "conditionalqa": pages,
    }


def sizes(registered: Mapping[str, Any], pilots: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """What a comparison on a part of an external base can show, by the registered rule.

    For every part of ConditionalQA and WixQA, every stratum and every design — the whole part
    or a selection by documents — the row gives n, the clusters, and the scenario of
    ``evaluation/power.py`` at the registered variance twice: for independent questions, and for
    clusters that move as one, which is the registered reading. A pilot adds, as description,
    the reading at its own estimate of the correlation and the hours two arms take at the
    seconds its control spent on a question, and can only raise the variance. The pilots of
    both bases together give ``step_1``: what step 1 of acceptance reads.
    """
    rows = []
    for base, strata in SIZED.items():
        pilot = pilots.get(base)
        seconds = None if pilot is None else question_seconds(base, pilot)
        for part, block in registered["bases"][base]["parts"].items():
            for stratum in strata:
                given = registered_variance(pilot, stratum)
                variance, share = given["variance"], given["differing_share"]
                for selection, clusters in designs(base, block, stratum):
                    if len(clusters) < 2:
                        continue
                    row: dict[str, Any] = {
                        "base": base,
                        "part": part,
                        "access": block["access"],
                        "stratum": stratum,
                        "selection": selection,
                        "n": sum(clusters),
                        "clusters": len(clusters),
                        "largest_cluster": clusters[0],
                        "variance": variance,
                        "variance_source": given["source"],
                        "independent": scenario(variance, clusters, 0.0, share),
                        "registered": scenario(variance, clusters, 1.0, share, student=True),
                    }
                    if given["correlation"] is not None:
                        row["at_pilot_correlation"] = scenario(
                            variance, clusters, given["correlation"], share
                        )
                    if seconds is not None:
                        row["hours_of_two_arms"] = 2 * sum(clusters) * seconds / 3600
                    rows.append(row)
    return {
        "version": SIZES_VERSION,
        "grid_variance": GRID_VARIANCE,
        "power": power.POWER,
        "minimally_useful_effect": power.MUE,
        "margin": power.MARGIN,
        "registration_sha256": parity.file_sha(parts.REGISTRATION),
        "variances": {
            base: {stratum: registered_variance(pilots.get(base), stratum) for stratum in strata}
            for base, strata in SIZED.items()
        },
        "seconds_per_question": {
            base: pilot["arms"][CONTROL]["seconds"] for base, pilot in sorted(pilots.items())
        },
        "pilot_runs": {
            base: {name: run["run_sha256"] for name, run in pilot["provenance"]["runs"].items()}
            for base, pilot in sorted(pilots.items())
        },
        "step_1": step_one(registered, pilots),
        "rows": rows,
        "code": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in CODE_FILES
        },
    }


def _write_once(path: Path, text: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != text:
        raise FileExistsError(f"A different {path.name} exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("measure", "sizes"))
    parser.add_argument("--base", choices=sorted(BASES))
    parser.add_argument("--base-dir", type=Path, help="the converted base")
    parser.add_argument("--arm", action="append", default=[], metavar="NAME=RUN")
    parser.add_argument("--pilot", action="append", default=[], metavar="BASE=FILE")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--aggregates", type=Path, help="measure: also write the document without its rows"
    )
    args = parser.parse_args(argv)
    if args.command == "sizes":
        if args.base is not None or args.base_dir is not None or args.arm or args.aggregates:
            parser.error("sizes reads the registration and the pilots: --pilot BASE=FILE")
        pilots = {}
        for pair in args.pilot:
            name, _, file = pair.partition("=")
            if name not in BASES or name in pilots or not file:
                parser.error(f"--pilot names a base once, as BASE=FILE: {pair}")
            pilots[name] = json.loads(Path(file).read_text(encoding="utf-8"))
        document = sizes(parts.registration(), pilots)
        _write_once(args.out, dump(document))
        print(json.dumps({"rows": len(document["rows"]), "pilots": sorted(pilots)}), flush=True)
        return 0
    if args.base is None or args.base_dir is None or args.pilot:
        parser.error("measure needs --base, --base-dir and both --arm")
    runs = {}
    for pair in args.arm:
        name, _, run = pair.partition("=")
        if name not in ARMS or name in runs or not run:
            parser.error(f"--arm names a registered arm once, as NAME=RUN: {pair}")
        runs[name] = Path(run)
    if set(runs) != set(ARMS):
        parser.error("the pilot is measured on the control and pool30 together")
    text = dump(measure(args.base, args.base_dir, runs))
    _write_once(args.out, text)
    report = json.loads(text)
    if args.aggregates is not None:
        _write_once(args.aggregates, dump(aggregates(report, text)))
    print(
        json.dumps(
            {
                "base": report["base"],
                "cases": report["cases"],
                "clusters": report["clusters"]["count"],
                "pairs": {name: result["pairs"] for name, result in report["pairs"].items()},
                "primary": {name: result["primary"] for name, result in report["pairs"].items()},
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

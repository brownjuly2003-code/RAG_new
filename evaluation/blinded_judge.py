"""P2 blinded relevance judgments, stores, statistics, and evidence assembly."""

from __future__ import annotations

import hashlib
import html
import json
import math
import random
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Protocol

from evaluation.aircargo_labels import load_labelled_cases, summarise, verify_manifest
from evaluation.blinded_judge_clients import (
    GlmClient,
    JudgeUnavailable,
    MistralClient,
    RateLimited,
    Reply,
    SonnetClient,
    TransportError,
)
from evaluation.ragas_eval import context_precision
from scripts import p1_adaptive_k as p1
from scripts import rerank_score_capture
from scripts.ab_context_precision import _git_commit, sha256_file
from scripts.generator_benchmark import _truncate_contexts, load_benchmark_cases

PROJECT_ROOT = Path(__file__).resolve().parent.parent
P1_REPORT = PROJECT_ROOT / "reports/p1/p1-adaptive-k.json"
SEED = 20260925
BOOTSTRAP_SAMPLES = 10_000
INSTRUCTION = (
    "Read the question and each document. Use only the text shown. Judge each document "
    "independently. Give 3 if it fully answers the question on its own; 2 if it contains "
    "part of the answer but is not enough on its own; 1 if it is on the topic but does "
    "not help answer; 0 if unrelated. Return one JSON object with grades, a list of "
    "five objects with doc (D1 through D5), grade (integer 0-3), and a short reason. "
    "Include each doc exactly once."
)
INSTRUCTION_SHA256 = hashlib.sha256(INSTRUCTION.encode("utf-8")).hexdigest()


class InvalidControl(ValueError):
    pass


class ParseFailure(ValueError):
    pass


class NotEvidence(ValueError):
    pass


@dataclass(frozen=True)
class Case:
    pool: str
    case_id: str
    question: str
    documents: tuple[str, ...]
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class Request:
    pool: str
    case_id: str
    text: str
    sha256: str
    order: tuple[int, ...]


@dataclass
class Pool:
    name: str
    cases: list[Case]
    sha256: str
    shortened_units: int
    ruler_per_case: dict[str, float]
    ruler_units: dict[str, tuple[float, ...]]
    question_units: dict[str, tuple[float, ...]]
    keyword_units: dict[str, tuple[float, ...]]
    provenance: dict[str, Any]


@dataclass
class Inputs:
    pools: dict[str, Pool]
    arms: dict[str, dict[str, dict[str, int]]]
    control_precision: float
    p1_report: dict[str, Any]
    approvals: dict[str, str]
    h_labels: dict[str, Any]


class JudgeClient(Protocol):
    def grade(self, request_text: str) -> Reply: ...


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_request(case: Case) -> Request:
    if len(case.documents) != 5:
        raise ValueError("each case must present five documents")
    order = list(range(5))
    random.Random(f"{SEED}:{case.case_id}").shuffle(order)
    text = (
        INSTRUCTION
        + "\n\nQuestion\n"
        + case.question
        + "\n\n"
        + "\n\n".join(
            f"D{position + 1}\n{case.documents[index]}" for position, index in enumerate(order)
        )
    )
    return Request(case.pool, case.case_id, text, _sha256_text(text), tuple(order))


def _first_object(text: str) -> object:
    start = text.find("{")
    if start < 0:
        raise ParseFailure("no JSON object")
    depth = 0
    quoted = False
    escaped = False
    for position in range(start, len(text)):
        char = text[position]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : position + 1])
                except (ValueError, TypeError):
                    raise ParseFailure("invalid first JSON object") from None
    raise ParseFailure("unbalanced JSON object")


def parse_grades(text: str, labels: Sequence[str]) -> dict[str, int]:
    obj = _first_object(text)
    if not isinstance(obj, dict) or not isinstance(obj.get("grades"), list):
        raise ParseFailure("missing grades list")
    rows = obj["grades"]
    if len(rows) != len(labels):
        raise ParseFailure("wrong number of grades")
    result: dict[str, int] = {}
    expected = set(labels)
    for row in rows:
        if not isinstance(row, dict):
            raise ParseFailure("grade is not an object")
        label = row.get("doc")
        grade = row.get("grade")
        if (
            not isinstance(label, str)
            or label not in expected
            or label in result
            or type(grade) is not int
            or not 0 <= grade <= 3
        ):
            raise ParseFailure("invalid, repeated, or extra grade")
        result[label] = grade
    if set(result) != expected:
        raise ParseFailure("missing document grade")
    return result


def _checked_count(value: object, size: int, source: str) -> int:
    if type(value) is not int or not 1 <= value <= 5:
        raise ValueError(f"{source}: kept count must be an integer from 1 to 5")
    if size < value:
        raise ValueError(f"{source}: kept count exceeds presented documents")
    return value


def _list_arm(counts: object, cases: Sequence[Case], source: str) -> dict[str, int]:
    if not isinstance(counts, list) or len(counts) != len(cases):
        raise ValueError(f"{source}: counts do not line up with pool cases")
    return {
        case.case_id: _checked_count(value, len(case.documents), source)
        for case, value in zip(cases, counts, strict=True)
    }


def _path_from_report(root: Path, name: object) -> Path:
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError("P1 provenance contains an invalid path")
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("P1 provenance path escapes the project")
    return path


def _pinned_file(root: Path, provenance: Mapping[str, Any], name: str) -> Path:
    path = _path_from_report(root, provenance["archive_path" if name == "archive" else name])
    if sha256_file(path) != provenance[name + "_sha256"]:
        raise ValueError(f"P1 {name} digest mismatch")
    return path


def _load_pool(root: Path, name: str, provenance: dict[str, Any]) -> Pool:
    expected_sha = p1.H_POOL_SHA256 if name == "H" else p1.HM_POOL_SHA256
    archive = p1.H_ARCHIVE if name == "H" else p1.HM_ARCHIVE
    if provenance["pool_sha256"] != expected_sha:
        raise ValueError(f"P1 {name} pool digest differs from the pinned constant")
    if archive != _path_from_report(root, provenance["archive_path"]):
        raise ValueError(f"P1 {name} archive path differs from the pinned constant")
    _pinned_file(root, provenance, "archive")
    dataset = _pinned_file(root, provenance, "dataset")
    _pinned_file(root, provenance, "label_sidecar")
    _pinned_file(root, provenance, "label_manifest")
    rows, digest = rerank_score_capture.load_pool_archive(archive, expected_sha)
    with tempfile.TemporaryDirectory(prefix="p2-pool-") as tmp:
        pool_path = Path(tmp) / "pool.json"
        pool_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        benchmark = load_benchmark_cases(
            dataset_path=dataset,
            contexts_path=pool_path,
            expected_cases=len(rows),
            top_k=5,
            context_chars=6000,
        )
    if [row["case_id"] for row in rows] != [case["case_id"] for case in benchmark]:
        raise ValueError(f"P1 {name} pool order differs from dataset order")
    cases: list[Case] = []
    shortened = 0
    ruler_cases: dict[str, float] = {}
    ruler_units: dict[str, tuple[float, ...]] = {}
    question_units: dict[str, tuple[float, ...]] = {}
    keyword_units: dict[str, tuple[float, ...]] = {}
    for row, benchmark_case in zip(rows, benchmark, strict=True):
        originals = row["cands"][:5]
        documents = tuple(_truncate_contexts(originals, 6000))
        shortened += sum(left != right for left, right in zip(originals, documents, strict=False))
        shortened += max(0, len(originals) - len(documents))
        if len(documents) != 5 or documents != tuple(benchmark_case["contexts"]):
            raise ValueError(f"P1 {name} case {row['case_id']} lacks five scored documents")
        case = Case(
            name,
            row["case_id"],
            benchmark_case["query"],
            documents,
            tuple(benchmark_case["expected_keywords"]),
        )
        cases.append(case)
        ruler_cases[case.case_id] = round(
            context_precision(case.question, documents, list(case.keywords)), 4
        )
        ruler_units[case.case_id] = tuple(
            context_precision(case.question, [document], list(case.keywords))
            for document in documents
        )
        question_units[case.case_id] = tuple(
            context_precision(case.question, [document], None) for document in documents
        )
        keyword_units[case.case_id] = tuple(
            context_precision("", [document], list(case.keywords)) for document in documents
        )
    return Pool(
        name,
        cases,
        digest,
        shortened,
        ruler_cases,
        ruler_units,
        question_units,
        keyword_units,
        provenance,
    )


def validate_control(value: float) -> None:
    if round(value, 4) != 0.5067:
        raise InvalidControl(f"INVALID_CONTROL: H top_k_5={value:.4f}, expected 0.5067")


def load_inputs(*, root: Path = PROJECT_ROOT, report_path: Path | None = None) -> Inputs:
    report = json.loads(
        (report_path or root / "reports/p1/p1-adaptive-k.json").read_text(encoding="utf-8")
    )
    provenances = report["provenance"]["pools"]
    pools = {name: _load_pool(root, name, provenances[name]) for name in ("H", "Hm")}
    manifest_name = "evaluation/curated_cases_aircargo.manifest.json"
    approvals_name = "evaluation/curated_cases_aircargo.approvals.json"
    approvals: dict[str, str] = {}
    for name in (manifest_name, approvals_name):
        path = _path_from_report(root, name)
        approvals[name] = sha256_file(path)
    manifest = json.loads(_path_from_report(root, manifest_name).read_text(encoding="utf-8"))
    if (
        manifest["approvals"]["sha256"] != approvals[approvals_name]
        or manifest["dataset_sha256"] != provenances["H"]["dataset_sha256"]
        or manifest["dataset"] != provenances["H"]["dataset"]
    ):
        raise ValueError("H label manifest does not pin the approvals and dataset")
    h_dataset = _path_from_report(root, provenances["H"]["dataset"])
    approvals_path = _path_from_report(root, approvals_name)
    labelled_cases = load_labelled_cases(h_dataset, approvals_path=approvals_path)
    problems = verify_manifest(
        manifest, h_dataset, labelled_cases, approvals_path=approvals_path,
        approvals_name=approvals_name,
    )
    if problems:
        raise ValueError("H label manifest mismatch: " + "; ".join(problems))
    if [case.case_id for case in labelled_cases] != [case.case_id for case in pools["H"].cases]:
        raise ValueError("H journey labels do not line up with the judged cases")
    h_labels = {
        "summary": summarise(labelled_cases).as_dict(),
        "cases": [
            {"case_id": case.case_id, "label": case.label.as_dict()}
            for case in labelled_cases
        ],
    }
    arms: dict[str, dict[str, dict[str, int]]] = {}
    for name, section in (("H", report["h"]), ("Hm", report["hm"])):
        cases = pools[name].cases
        cells = section["cells"]
        if [cell["name"] for cell in cells] != [cell_name for cell_name, *_ in p1.grid_cells()]:
            raise ValueError(f"P1 {name} grid does not match the registered 37 cells")
        arms[name] = {
            cell["name"]: _list_arm(cell["kept"], cases, f"{name}/{cell['name']}") for cell in cells
        }
        if arms[name].get("top_k_5") != {case.case_id: 5 for case in cases}:
            raise ValueError(f"P1 {name} control must keep five documents")
    if list(arms["H"])[0:37] != list(arms["Hm"])[0:37]:
        raise ValueError("P1 H and Hm cells differ")
    h_cases = pools["H"].cases
    held_out = report["h"]["cross_validation"]["per_case"]
    case_ids = {case.case_id for case in h_cases}
    if len(held_out) != len(h_cases) or {row["case_id"] for row in held_out} != case_ids:
        raise ValueError("P1 held-out rows do not line up with H")
    arms["H"]["held_out"] = {
        row["case_id"]: _checked_count(row["kept"], 5, "H/held_out") for row in held_out
    }
    arms["H"]["oracle_best_prefix"] = _list_arm(
        report["h"]["oracle_best_prefix"]["oracle_k"], h_cases, "H/oracle_best_prefix"
    )
    rows, _ = rerank_score_capture.load_pool_archive(p1.H_ARCHIVE, p1.H_POOL_SHA256)
    scored, _ = p1.score_selection(
        rows,
        [{"texts": row["cands"]} for row in rows],
        [5] * len(rows),
        dataset_path=_path_from_report(root, provenances["H"]["dataset"]),
        sidecar_path=_path_from_report(root, provenances["H"]["label_sidecar"]),
        label_manifest_path=_path_from_report(root, provenances["H"]["label_manifest"]),
    )
    control = p1.aggregate(scored)["context_precision"]
    if control is None:
        raise InvalidControl("INVALID_CONTROL: no H cases")
    validate_control(control)
    if {row["case_id"]: row["context_precision"] for row in scored} != pools["H"].ruler_per_case:
        raise InvalidControl("INVALID_CONTROL: H per-case ruler scores differ")
    return Inputs(pools, arms, control, report, approvals, h_labels)


def read_store(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                row = json.loads(line)
            except ValueError:
                raise ValueError(f"invalid reply store line {line_number}") from None
            if not isinstance(row, dict):
                raise ValueError(f"invalid reply store line {line_number}")
            rows.append(row)
    return rows


def _store_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row["pool"]), str(row["case_id"])


def merge_stores(
    paths: Sequence[Path],
    request_sha_by_case: Mapping[tuple[str, str], str] | None = None,
) -> dict[str, dict[tuple[str, str], dict[str, Any]]]:
    result: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    for path in paths:
        for row in read_store(path):
            judge = str(row["judge"])
            key = _store_key(row)
            current = result.setdefault(judge, {}).get(key)
            preferred_sha = (request_sha_by_case or {}).get(key)
            if preferred_sha and current is not None:
                if current.get("request_sha256") == preferred_sha != row.get("request_sha256"):
                    continue
                if row.get("request_sha256") == preferred_sha != current.get("request_sha256"):
                    result[judge][key] = row
                    continue
            if (
                current is None
                or row.get("status") == "graded"
                or current.get("status") != "graded"
            ):
                result[judge][key] = row
    return result


def _append_store(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()


def run_judge(
    judge: str,
    client: JudgeClient,
    cases: Sequence[Case],
    store_path: Path,
    *,
    control_precision: float = 0.5067,
    limit: int | None = None,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    validate_control(control_precision)
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")
    graded_sha = {
        (row["pool"], row["case_id"], row["request_sha256"])
        for row in read_store(store_path)
        if row.get("judge") == judge and row.get("status") == "graded"
    }
    result: dict[str, Any] = {
        "judge": judge,
        "status": "available",
        "graded": 0,
        "missing": 0,
        "reused": 0,
    }
    started = 0
    for case in cases:
        request = build_request(case)
        if (case.pool, case.case_id, request.sha256) in graded_sha:
            result["reused"] += 1
            continue
        if limit is not None and started >= limit:
            break
        started += 1
        parse_failures = 0
        transport_failures = 0
        rate_waits = 0
        while True:
            try:
                reply = client.grade(request.text)
            except JudgeUnavailable as exc:
                unavailable_record = {
                    "judge": judge,
                    "pool": case.pool,
                    "case_id": case.case_id,
                    "request_sha256": request.sha256,
                    "status": "unavailable",
                    "code": exc.code,
                    "message": exc.message,
                }
                _append_store(store_path, unavailable_record)
                result.update(status="unavailable", code=exc.code, message=exc.message)
                return result
            except RateLimited as exc:
                if exc.reset_at is None or rate_waits >= 3:
                    _append_store(
                        store_path,
                        {
                            "judge": judge,
                            "pool": case.pool,
                            "case_id": case.case_id,
                            "request_sha256": request.sha256,
                            "status": "unavailable",
                            "code": "rate_limit",
                            "message": "Rate limit has no usable reset",
                        },
                    )
                    result.update(
                        status="unavailable",
                        code="rate_limit",
                        message="Rate limit has no usable reset",
                    )
                    return result
                sleep(max(0.0, exc.reset_at - clock()))
                rate_waits += 1
                continue
            except TransportError:
                transport_failures += 1
                if transport_failures >= 3:
                    _append_store(
                        store_path,
                        {
                            "judge": judge,
                            "pool": case.pool,
                            "case_id": case.case_id,
                            "request_sha256": request.sha256,
                            "status": "unavailable",
                            "code": "transport",
                            "message": "Judge endpoint is unreachable",
                        },
                    )
                    result.update(
                        status="unavailable",
                        code="transport",
                        message="Judge endpoint is unreachable",
                    )
                    return result
                sleep(float(2 ** (transport_failures - 1)))
                continue
            record: dict[str, Any] = {
                "judge": judge,
                "pool": case.pool,
                "case_id": case.case_id,
                "request_sha256": request.sha256,
                "raw_text": reply.text,
                "model": reply.model,
                "usage": reply.usage,
                "elapsed_s": reply.elapsed_s,
            }
            try:
                parsed = parse_grades(reply.text, tuple(f"D{j}" for j in range(1, 6)))
            except ParseFailure:
                parse_failures += 1
                record["status"] = "missing" if parse_failures >= 3 else "parse_failure"
                _append_store(store_path, record)
                if parse_failures >= 3:
                    result["missing"] += 1
                    break
            else:
                grades = [0] * 5
                for position, original_index in enumerate(request.order):
                    grades[original_index] = parsed[f"D{position + 1}"]
                record.update(status="graded", grades=grades)
                _append_store(store_path, record)
                result["graded"] += 1
                break
    return result


def lower_median(values: Sequence[int]) -> int:
    if not values:
        raise ValueError("median requires at least one grade")
    ordered = sorted(values)
    return ordered[(len(ordered) - 1) // 2]


def consensus_grades(
    case_ids: Sequence[str], grades_by_judge: Mapping[str, Mapping[str, tuple[int, ...]]]
) -> tuple[dict[str, tuple[int, ...]], list[str]]:
    total_units = len(case_ids) * 5
    excluded = sorted(
        judge
        for judge, grades in grades_by_judge.items()
        if total_units
        and sum(5 - len(grades.get(case_id, ())) for case_id in case_ids) / total_units > 0.05
    )
    included = sorted(set(grades_by_judge) - set(excluded))
    consensus: dict[str, tuple[int, ...]] = {}
    for case_id in case_ids:
        per_judge = [grades_by_judge[judge].get(case_id) for judge in included]
        if not any(per_judge):
            continue
        unit_grades: list[int] = []
        for index in range(5):
            values = [
                grades[index] for grades in per_judge if grades is not None and len(grades) > index
            ]
            if not values:
                break
            unit_grades.append(lower_median(values))
        if len(unit_grades) == 5:
            consensus[case_id] = tuple(unit_grades)
    return consensus, excluded


def _weighted(values: Sequence[float]) -> float:
    weights = [1 / (index + 1) for index in range(len(values))]
    return sum(value * weight for value, weight in zip(values, weights, strict=True)) / sum(weights)


def _case_metrics(grades: Sequence[int], kept: int) -> dict[str, float | str]:
    selected = grades[:kept]
    state = "FULL" if 3 in selected else "PART" if any(grade >= 2 for grade in selected) else "MISS"
    return {
        "judged_precision": sum(grade >= 2 for grade in selected) / kept,
        "ruler_shaped_judged_precision": _weighted([grade / 3 for grade in selected]),
        "answerability": float(state == "FULL"),
        "state": state,
    }


def arm_metrics(
    grades_by_case: Mapping[str, tuple[int, ...]], kept_by_case: Mapping[str, int]
) -> dict[str, Any]:
    per_case = {
        case_id: _case_metrics(grades, _checked_count(kept_by_case[case_id], len(grades), case_id))
        for case_id, grades in grades_by_case.items()
        if case_id in kept_by_case
    }
    states = Counter(row["state"] for row in per_case.values())
    count = len(per_case)
    return {
        "graded_cases": count,
        "missing_cases": len(kept_by_case) - count,
        "judged_precision": (
            sum(float(row["judged_precision"]) for row in per_case.values()) / count
            if count
            else None
        ),
        "ruler_shaped_judged_precision": (
            sum(float(row["ruler_shaped_judged_precision"]) for row in per_case.values()) / count
            if count
            else None
        ),
        "answerability": {name: states[name] for name in ("FULL", "PART", "MISS")},
        "answerability_rate": states["FULL"] / count if count else None,
    }


def kendall_tau_b(x: Sequence[float], y: Sequence[float]) -> float | None:
    if len(x) != len(y):
        raise ValueError("Kendall vectors have different lengths")
    concordant = discordant = x_only_ties = y_only_ties = 0
    for first in range(len(x)):
        for second in range(first + 1, len(x)):
            dx = (x[first] > x[second]) - (x[first] < x[second])
            dy = (y[first] > y[second]) - (y[first] < y[second])
            if dx == 0 and dy != 0:
                x_only_ties += 1
            elif dy == 0 and dx != 0:
                y_only_ties += 1
            elif dx == dy and dx != 0:
                concordant += 1
            elif dx != 0 and dy != 0:
                discordant += 1
    denominator = math.sqrt(
        (concordant + discordant + x_only_ties) * (concordant + discordant + y_only_ties)
    )
    return (concordant - discordant) / denominator if denominator else None


def quadratic_kappa(first: Sequence[int], second: Sequence[int]) -> float | None:
    if len(first) != len(second):
        raise ValueError("Kappa vectors have different lengths")
    if not first:
        return None
    left = Counter(first)
    right = Counter(second)
    observed = sum((a - b) ** 2 for a, b in zip(first, second, strict=True)) / len(first)
    expected = (
        sum(left[a] * right[b] * (a - b) ** 2 for a in range(4) for b in range(4)) / len(first) ** 2
    )
    if expected == 0:
        return 1.0 if observed == 0 else None
    return 1 - observed / expected


def krippendorff_alpha_ordinal(units: Sequence[Sequence[int]]) -> float | None:
    complete = [unit for unit in units if len(unit) >= 2]
    if not complete:
        return None
    counts = Counter(grade for unit in complete for grade in unit)
    total = sum(counts.values())
    if total < 2:
        return None

    def distance(a: int, b: int) -> float:
        if a == b:
            return 0.0
        low, high = sorted((a, b))
        center = float(sum(counts[category] for category in range(low, high + 1)))
        center -= (counts[low] + counts[high]) / 2
        return center**2

    observed_sum = 0.0
    observed_units = 0
    for unit in complete:
        pair_count = len(unit) * (len(unit) - 1) / 2
        observed_sum += (
            sum(distance(a, b) for index, a in enumerate(unit) for b in unit[index + 1 :])
            / pair_count
        )
        observed_units += 1
    observed = observed_sum / observed_units
    expected = sum(
        2 * counts[a] * counts[b] * distance(a, b) for a in range(4) for b in range(a + 1, 4)
    ) / (total * (total - 1))
    if expected == 0:
        return 1.0 if observed == 0 else None
    return 1 - observed / expected


def _percentile(ordered: Sequence[float], proportion: float) -> float:
    position = (len(ordered) - 1) * proportion
    below = math.floor(position)
    above = math.ceil(position)
    return ordered[below] + (ordered[above] - ordered[below]) * (position - below)


def bootstrap_mean_ci(
    values: Sequence[float], *, samples: int = BOOTSTRAP_SAMPLES, seed: int = SEED
) -> tuple[float, float] | None:
    if not values or samples < 1:
        return None
    rng = random.Random(seed)
    n = len(values)
    draws = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(samples))
    return _percentile(draws, 0.025), _percentile(draws, 0.975)


def bootstrap_tau_ci(
    x: Sequence[float],
    y: Sequence[float],
    *,
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = SEED,
) -> tuple[float, float] | None:
    if len(x) != len(y) or len(x) < 2:
        return None
    rng = random.Random(seed)
    n = len(x)
    draws: list[float] = []
    for _ in range(samples):
        indices = [rng.randrange(n) for _ in range(n)]
        value = kendall_tau_b([x[index] for index in indices], [y[index] for index in indices])
        if value is not None:
            draws.append(value)
    if not draws:
        return None
    draws.sort()
    return _percentile(draws, 0.025), _percentile(draws, 0.975)


def verdict(
    ci95: tuple[float, float] | None,
    *,
    judge_count: int,
    alpha: float | None,
    human_kappa: float | None,
    human_graded: bool = False,
) -> str:
    if judge_count < 1:
        return "JUDGE_UNRELIABLE"
    if judge_count >= 2 and (alpha is None or alpha < 0.667):
        return "JUDGE_UNRELIABLE"
    if human_graded and (human_kappa is None or human_kappa < 0.60):
        return "JUDGE_UNRELIABLE"
    if human_kappa is not None and human_kappa < 0.60:
        return "JUDGE_UNRELIABLE"
    if ci95 is None:
        decision = "INCONCLUSIVE"
    elif ci95[0] >= 0.40:
        decision = "RULER_TRACKS"
    elif ci95[1] < 0.40:
        decision = "RULER_DOES_NOT_TRACK"
    else:
        decision = "INCONCLUSIVE"
    if judge_count == 1 and not human_graded and human_kappa is None:
        return "PROVISIONAL_" + decision
    return decision


def draw_human_sample(cases: Sequence[Case], ruler: Mapping[str, float]) -> list[Case]:
    ordered = sorted(cases, key=lambda case: (round(ruler[case.case_id], 4), case.case_id))
    if len(ordered) != 100:
        raise ValueError("human sample requires the 100 H cases")
    rng = random.Random(SEED)
    sample: list[Case] = []
    for start in range(0, 100, 20):
        sample.extend(rng.sample(ordered[start : start + 20], 2))
    return sample


def write_human_page(sample: Sequence[Case], path: Path) -> None:
    sections: list[str] = []
    for case in sample:
        request = build_request(case)
        documents = []
        for position, index in enumerate(request.order, 1):
            label = f"D{position}"
            options = '<option value="">Выберите</option>' + "".join(
                f'<option value="{grade}">{grade}</option>' for grade in range(4)
            )
            documents.append(
                f"<article><h3>{label}</h3><pre>{html.escape(case.documents[index])}</pre>"
                f'<label>Оценка <select data-case="{html.escape(case.case_id, quote=True)}" '
                f'data-doc="{label}">{options}</select></label></article>'
            )
        sections.append(
            f"<section><h2>{html.escape(case.case_id)}</h2>"
            f"<p>{html.escape(case.question)}</p>{''.join(documents)}</section>"
        )
    page = (
        '<!doctype html><html lang="ru"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Оценка документов</title><style>body{font:16px/1.5 system-ui;max-width:72ch;"
        "margin:auto;padding:2rem}section{border-top:2px solid #555;margin-top:3rem}"
        "article{border:1px solid #bbb;padding:1rem;margin:1rem 0}pre{white-space:pre-wrap;"
        "overflow-wrap:anywhere}select{font-size:1rem}</style><body>"
        "<h1>Оценка полезности документов</h1><p>3 — полный ответ; 2 — часть ответа; "
        "1 — по теме, но не помогает; 0 — не относится к вопросу.</p>"
        + "".join(sections)
        + '<button id="export" type="button">Сохранить JSON</button><script>'
        'document.getElementById("export").addEventListener("click",()=>{'
        'const fields=[...document.querySelectorAll("select[data-case]")];'
        'if(fields.some(field=>field.value==="")){alert("Заполните все поля");return}'
        "const grades=fields.map(field=>({case_id:field.dataset.case,doc:field.dataset.doc,"
        "grade:Number(field.value)}));"
        'const blob=new Blob([JSON.stringify({grades},null,2)],{type:"application/json"});'
        'const link=document.createElement("a");link.href=URL.createObjectURL(blob);'
        'link.download="human-grades.json";link.click();URL.revokeObjectURL(link.href);});'
        "</script></body></html>\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8", newline="\n")


def import_human_grades(
    grades_path: Path, sample: Sequence[Case], grader: str, graded_date: str
) -> dict[str, Any]:
    if not grader.strip():
        raise ValueError("grader name is required")
    try:
        if date.fromisoformat(graded_date).isoformat() != graded_date:
            raise ValueError("date must be YYYY-MM-DD")
    except ValueError:
        raise ValueError("date must be YYYY-MM-DD") from None
    payload = json.loads(grades_path.read_text(encoding="utf-8"))
    rows = payload.get("grades") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("human grades must be a list")
    expected = {(case.case_id, f"D{position}") for case in sample for position in range(1, 6)}
    found: dict[tuple[str, str], int] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid human grade row")
        case_id = row.get("case_id")
        label = row.get("doc")
        if not isinstance(case_id, str) or not isinstance(label, str):
            raise ValueError("human grades must cover exactly the sampled units")
        key = (case_id, label)
        value = row.get("grade")
        if key not in expected or key in found or type(value) is not int or not 0 <= value <= 3:
            raise ValueError("human grades must cover exactly the sampled units")
        found[key] = value
    if set(found) != expected:
        raise ValueError("human grades must cover exactly the sampled units")
    return {
        "schema_version": "p2-human-grades/v1.0",
        "grader": grader.strip(),
        "date": graded_date,
        "sample_case_ids": [case.case_id for case in sample],
        "grades": [
            {"case_id": case_id, "doc": label, "grade": grade}
            for (case_id, label), grade in sorted(found.items())
        ],
    }


def _current_grades(
    inputs: Inputs, stores: Mapping[str, Mapping[tuple[str, str], dict[str, Any]]]
) -> tuple[dict[str, dict[str, dict[str, tuple[int, ...]]]], dict[str, Any]]:
    by_pool: dict[str, dict[str, dict[str, tuple[int, ...]]]] = {name: {} for name in inputs.pools}
    judge_info: dict[str, Any] = {}
    routes: dict[str, tuple[str, dict[str, Any]]] = {
        "sonnet": (SonnetClient.route, SonnetClient.parameters),
        "glm": (GlmClient.route, GlmClient.parameters),
        "mistral": (MistralClient.route, MistralClient.parameters),
    }
    for judge, records in stores.items():
        if judge not in routes:
            raise ValueError(f"unknown judge in reply store: {judge}")
        global_unavailable: dict[str, str] | None = None
        for pool in inputs.pools.values():
            for case in pool.cases:
                record = records.get((pool.name, case.case_id))
                if (
                    record
                    and record.get("status") == "unavailable"
                    and record.get("request_sha256") == build_request(case).sha256
                ):
                    global_unavailable = {
                        "code": str(record.get("code", "unavailable")),
                        "message": str(record.get("message", "Judge unavailable")),
                    }
        info: dict[str, Any] = {
            "route": routes[judge][0],
            "parameters": routes[judge][1],
            "reported_models": [],
            "pools": {},
        }
        models: set[str] = set()
        for pool_name, pool in inputs.pools.items():
            grades: dict[str, tuple[int, ...]] = {}
            unavailable = global_unavailable
            for case in pool.cases:
                record = records.get((pool_name, case.case_id))
                request = build_request(case)
                if not record or record.get("request_sha256") != request.sha256:
                    continue
                if record.get("status") == "unavailable":
                    unavailable = {
                        "code": str(record.get("code", "unavailable")),
                        "message": str(record.get("message", "Judge unavailable")),
                    }
                if record.get("status") != "graded":
                    continue
                parsed = parse_grades(record["raw_text"], tuple(f"D{j}" for j in range(1, 6)))
                ordered = [0] * 5
                for position, index in enumerate(request.order):
                    ordered[index] = parsed[f"D{position + 1}"]
                if record.get("grades") != ordered:
                    raise ValueError(f"reply store grade mismatch for {case.case_id}")
                grades[case.case_id] = tuple(ordered)
                models.add(str(record["model"]))
            by_pool[pool_name][judge] = grades
            missing = (len(pool.cases) - len(grades)) * 5
            info["pools"][pool_name] = {
                "graded_units": len(grades) * 5,
                "missing_units": 0 if unavailable else missing,
                "unavailable_units": missing if unavailable else 0,
                "unavailable": unavailable,
            }
        info["reported_models"] = sorted(models)
        judge_info[judge] = info
    return by_pool, judge_info


def _ruler_arm_scores(inputs: Inputs, pool_name: str) -> dict[str, dict[str, Any]]:
    pool = inputs.pools[pool_name]
    provenance = pool.provenance
    rows, _ = rerank_score_capture.load_pool_archive(
        p1.H_ARCHIVE if pool_name == "H" else p1.HM_ARCHIVE, pool.sha256
    )
    rankings = [{"texts": row["cands"]} for row in rows]
    cache: dict[tuple[int, ...], dict[str, Any]] = {}
    result: dict[str, dict[str, Any]] = {}
    for arm, kept in inputs.arms[pool_name].items():
        counts = tuple(kept[row["case_id"]] for row in rows)
        if counts not in cache:
            scored, _ = p1.score_selection(
                rows,
                rankings,
                counts,
                dataset_path=_path_from_report(PROJECT_ROOT, provenance["dataset"]),
                sidecar_path=_path_from_report(PROJECT_ROOT, provenance["label_sidecar"]),
                label_manifest_path=_path_from_report(PROJECT_ROOT, provenance["label_manifest"]),
            )
            cache[counts] = {
                "aggregate": p1.aggregate(scored)["context_precision"],
                "per_case": {row["case_id"]: row["context_precision"] for row in scored},
            }
        result[arm] = cache[counts]
    return result


def _paired_comparison(
    grades: Mapping[str, tuple[int, ...]], arm: Mapping[str, int], control: Mapping[str, int]
) -> dict[str, Any]:
    keys = ("judged_precision", "ruler_shaped_judged_precision", "answerability")
    paired: dict[str, list[float]] = {key: [] for key in keys}
    for case_id, case_grades in grades.items():
        if case_id not in arm or case_id not in control:
            continue
        selected = _case_metrics(case_grades, arm[case_id])
        baseline = _case_metrics(case_grades, control[case_id])
        for key in keys:
            paired[key].append(float(selected[key]) - float(baseline[key]))
    return {
        key: {
            "delta": sum(values) / len(values) if values else None,
            "ci95": bootstrap_mean_ci(values),
        }
        for key, values in paired.items()
    }


def _arm_results(
    inputs: Inputs,
    pool_name: str,
    grades: Mapping[str, tuple[int, ...]],
    ruler: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    control = inputs.arms[pool_name]["top_k_5"]
    return {
        arm: {
            "kept": kept,
            "ruler_precision": ruler[arm]["aggregate"],
            "metrics": arm_metrics(grades, kept),
            "paired_vs_control": _paired_comparison(grades, kept, control),
        }
        for arm, kept in inputs.arms[pool_name].items()
    }


def _pairwise_kappas(grades: Mapping[str, Mapping[str, tuple[int, ...]]]) -> dict[str, Any]:
    judges = sorted(grades)
    result: dict[str, Any] = {}
    shared_all = set.intersection(*(set(grades[judge]) for judge in judges)) if judges else set()
    for left_index, left in enumerate(judges):
        for right in judges[left_index + 1 :]:
            shared = sorted(shared_all)
            first = [grade for case_id in shared for grade in grades[left][case_id]]
            second = [grade for case_id in shared for grade in grades[right][case_id]]
            result[f"{left}+{right}"] = {
                "shared_units": len(first),
                "quadratic_kappa": quadratic_kappa(first, second),
            }
    return result


def _alpha_for_consensus(
    grades: Mapping[str, Mapping[str, tuple[int, ...]]],
    included: Sequence[str],
    case_ids: Sequence[str],
) -> tuple[float | None, int]:
    if len(included) < 2:
        return None, 0
    units = [
        [grades[judge][case_id][index] for judge in included]
        for case_id in case_ids
        if all(case_id in grades[judge] for judge in included)
        for index in range(5)
    ]
    return krippendorff_alpha_ordinal(units), len(units)


def _human_comparison(
    sample: Sequence[Case],
    human: Mapping[str, Any],
    consensus: Mapping[str, tuple[int, ...]],
    judges: Mapping[str, Mapping[str, tuple[int, ...]]],
) -> dict[str, Any]:
    presented = {(row["case_id"], row["doc"]): row["grade"] for row in human["grades"]}
    by_case: dict[str, tuple[int, ...]] = {}
    for case in sample:
        values = [0] * 5
        for position, original in enumerate(build_request(case).order, 1):
            values[original] = presented[(case.case_id, f"D{position}")]
        by_case[case.case_id] = tuple(values)

    def compare(grades: Mapping[str, tuple[int, ...]]) -> dict[str, Any]:
        shared = sorted(set(grades) & set(by_case))
        first = [grade for case_id in shared for grade in grades[case_id]]
        second = [grade for case_id in shared for grade in by_case[case_id]]
        return {"shared_units": len(first), "quadratic_kappa": quadratic_kappa(first, second)}

    return {
        "sample_case_ids": [case.case_id for case in sample],
        "grades": human,
        "consensus": compare(consensus),
        "judges": {judge: compare(grades) for judge, grades in judges.items()},
    }


def _cross_table(pool: Pool, consensus: Mapping[str, tuple[int, ...]]) -> dict[str, dict[str, int]]:
    units = sorted(
        (relevance, case_id, index)
        for case_id, values in pool.ruler_units.items()
        for index, relevance in enumerate(values)
    )
    table = {str(quintile + 1): {str(grade): 0 for grade in range(4)} for quintile in range(5)}
    for position, (_relevance, case_id, index) in enumerate(units):
        if case_id in consensus:
            quintile = min(4, 5 * position // len(units))
            table[str(quintile + 1)][str(consensus[case_id][index])] += 1
    return table


def _h_agreement(
    pool: Pool,
    consensus: Mapping[str, tuple[int, ...]],
    arm_results: Mapping[str, Any],
    ruler_arms: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    case_ids = sorted(consensus)
    ruler_case = [pool.ruler_per_case[case_id] for case_id in case_ids]
    judged_case = [
        float(_case_metrics(consensus[case_id], 5)["ruler_shaped_judged_precision"])
        for case_id in case_ids
    ]
    ruler_unit = [value for case_id in case_ids for value in pool.ruler_units[case_id]]
    question_unit = [value for case_id in case_ids for value in pool.question_units[case_id]]
    keyword_unit = [value for case_id in case_ids for value in pool.keyword_units[case_id]]
    judged_unit = [grade for case_id in case_ids for grade in consensus[case_id]]
    cells = [name for name in ruler_arms if name not in ("held_out", "oracle_best_prefix")]
    ruler_arm = [ruler_arms[name]["aggregate"] for name in cells]
    judged_arm = [arm_results[name]["metrics"]["judged_precision"] for name in cells]
    arm_pairs = [
        (float(a), float(b))
        for a, b in zip(ruler_arm, judged_arm, strict=True)
        if a is not None and b is not None
    ]
    return {
        "per_case": {
            "n": len(case_ids),
            "tau_b": kendall_tau_b(ruler_case, judged_case),
            "ci95": bootstrap_tau_ci(ruler_case, judged_case),
        },
        "per_unit": {"n": len(judged_unit), "tau_b": kendall_tau_b(ruler_unit, judged_unit)},
        "per_arm": {
            "n": len(arm_pairs),
            "tau_b": kendall_tau_b([a for a, _ in arm_pairs], [b for _, b in arm_pairs]),
        },
        "question_only_per_unit": kendall_tau_b(question_unit, judged_unit),
        "keyword_only_per_unit": kendall_tau_b(keyword_unit, judged_unit),
        "ruler_quintile_by_grade": _cross_table(pool, consensus),
    }


def build_report(
    inputs: Inputs, store_paths: Sequence[Path], *, out_dir: Path = PROJECT_ROOT / "reports/p2"
) -> tuple[Path, dict[str, Any]]:
    validate_control(inputs.control_precision)
    request_sha_by_case = {
        (case.pool, case.case_id): build_request(case).sha256
        for pool in inputs.pools.values()
        for case in pool.cases
    }
    stores = merge_stores(store_paths, request_sha_by_case)
    grades, judge_info = _current_grades(inputs, stores)
    graded_judges = sorted(
        judge for judge in stores if any(grades[pool][judge] for pool in inputs.pools)
    )
    if not graded_judges:
        raise NotEvidence("NOT_EVIDENCE: no judge graded a unit")
    for judge in stores:
        judge_info[judge]["reply_files"] = [
            {"path": path.as_posix(), "sha256": sha256_file(path)}
            for path in store_paths
            if any(row.get("judge") == judge for row in read_store(path))
        ]
    ruler_arms = {name: _ruler_arm_scores(inputs, name) for name in inputs.pools}
    sample = draw_human_sample(inputs.pools["H"].cases, inputs.pools["H"].ruler_per_case)
    human_path = out_dir / "human-grades.json"
    human = None
    if human_path.is_file():
        original = json.loads(human_path.read_text(encoding="utf-8"))
        human = import_human_grades(human_path, sample, original["grader"], original["date"])
    metrics: dict[str, Any] = {}
    h_consensus: dict[str, tuple[int, ...]] = {}
    h_included: list[str] = []
    h_alpha: float | None = None
    for pool_name, pool in inputs.pools.items():
        case_ids = [case.case_id for case in pool.cases]
        pool_grades = {judge: grades[pool_name][judge] for judge in graded_judges}
        consensus, excluded = consensus_grades(case_ids, pool_grades)
        included = sorted(set(graded_judges) - set(excluded))
        alpha, complete_units = _alpha_for_consensus(pool_grades, included, case_ids)
        per_judge = {
            judge: {
                "arms": _arm_results(inputs, pool_name, pool_grades[judge], ruler_arms[pool_name]),
                "grade_distribution": dict(
                    sorted(
                        Counter(
                            grade for values in pool_grades[judge].values() for grade in values
                        ).items()
                    )
                ),
                "missing_units": (len(case_ids) - len(pool_grades[judge])) * 5,
            }
            for judge in graded_judges
        }
        metrics[pool_name] = {
            "cases": len(case_ids),
            "units": len(case_ids) * 5,
            "shortened_units": pool.shortened_units,
            "excluded_from_consensus": excluded,
            "included_in_consensus": included,
            "consensus": {
                "graded_cases": len(consensus),
                "arms": _arm_results(inputs, pool_name, consensus, ruler_arms[pool_name]),
            },
            "per_judge": per_judge,
            "reliability": {
                "pairwise_quadratic_kappa": _pairwise_kappas(pool_grades),
                "ordinal_krippendorff_alpha": alpha,
                "complete_units": complete_units,
            },
        }
        if pool_name == "H":
            h_consensus, h_included, h_alpha = consensus, included, alpha
    agreement = _h_agreement(
        inputs.pools["H"], h_consensus, metrics["H"]["consensus"]["arms"], ruler_arms["H"]
    )
    adjudication: dict[str, Any] = (
        _human_comparison(
            sample, human, h_consensus, {judge: grades["H"][judge] for judge in graded_judges}
        )
        if human is not None
        else {"sample_case_ids": [case.case_id for case in sample], "grades": None}
    )
    human_kappa = adjudication["consensus"]["quadratic_kappa"] if human is not None else None
    decision = verdict(
        agreement["per_case"]["ci95"],
        judge_count=len(h_included),
        alpha=h_alpha,
        human_kappa=human_kappa,
        human_graded=human is not None,
    )
    code = _git_commit()
    code["files"] = {
        name: sha256_file(PROJECT_ROOT / name)
        for name in (
            "evaluation/blinded_judge.py",
            "evaluation/blinded_judge_clients.py",
            "scripts/p2_blinded_judge.py",
            "tests/test_blinded_judge.py",
        )
    }
    report = {
        "schema_version": "p2-blinded-judge/v1.0",
        "evidence_class": "measured",
        "provenance": {
            "code": code,
            "pools": {
                name: {"pool_sha256": pool.sha256, **pool.provenance}
                for name, pool in inputs.pools.items()
            },
            "label_manifest_and_approvals": inputs.approvals,
            "H_labels": inputs.h_labels,
            "instruction_sha256": INSTRUCTION_SHA256,
            "judge_routes": judge_info,
        },
        "control": {"H_top_k_5": inputs.control_precision, "valid": True},
        "bootstrap": {
            "samples": BOOTSTRAP_SAMPLES,
            "seed": SEED,
            "method": "paired case percentile 95%, linear quantiles",
        },
        "metrics": metrics,
        "h_agreement": agreement,
        "human": adjudication,
        "verdict": {
            "decision": decision,
            "judge_count": len(h_included),
            "ordinal_krippendorff_alpha": h_alpha,
            "human_quadratic_kappa": human_kappa,
            "per_case_tau_b_ci95": agreement["per_case"]["ci95"],
        },
    }
    path = out_dir / f"p2-blinded-judge-{'+'.join(graded_judges)}.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return path, report

"""Version 2 consensus of the blind judges and its adapter to the semantic ruler.

The frozen v1 `lower_median`/`consensus_grades` in `evaluation.blinded_judge` stay
unchanged for the pinned P2 artifacts.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from evaluation.blinded_judge import lower_median
from evaluation.judge_contract import validate_grade_record

MISSING_SHARE_LIMIT = 0.05


@dataclass(frozen=True)
class ConsensusV2:
    """Consensus over one pool of addressed texts."""

    grades: dict[Hashable, int]
    unjudged: dict[Hashable, str]
    graded_by: dict[Hashable, tuple[str, ...]]
    included: tuple[str, ...]
    excluded: dict[str, float]
    missing: dict[str, int]


def store_grades(
    rows: Iterable[Mapping[str, Any]],
    requests: Mapping[str, str],
) -> tuple[dict[tuple[str, str], int], str | None]:
    """Collect one judge's valid v2 grades keyed by `(case_id, text_sha256)`.

    Only rows with `request_version == 2` and `status == "valid"` count, and
    each record of such a row is validated; a record counts only when its
    `case_id` is planned and its `request_sha256` matches that plan, repeated
    keys must repeat the same grade. Every v2 attempt, regardless of status
    or plan membership, must share one nonempty `judge_version`, and all its
    records must carry that version. Return the store's v2 attempt version,
    or `None` when no v2 attempt exists.
    """
    grades: dict[tuple[str, str], int] = {}
    judge_version: str | None = None
    for row in rows:
        if row.get("request_version") != 2:
            continue
        version = row.get("judge_version")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("v2 attempt requires a nonempty judge_version")
        if judge_version is None:
            judge_version = version
        elif version != judge_version:
            raise ValueError("one reply store mixes judge versions")
        for record in row.get("records", ()):
            if record.get("judge_version") != version:
                raise ValueError("grade record judge_version differs from its attempt")
        if row.get("status") != "valid":
            continue
        for record in row.get("records", ()):
            validate_grade_record(record)
            case_id = record["case_id"]
            if case_id not in requests:
                continue
            if record["request_sha256"] != requests[case_id]:
                continue
            key = (case_id, record["text_sha256"])
            if key in grades and grades[key] != record["grade"]:
                raise ValueError("conflicting grades for one addressed text")
            grades[key] = record["grade"]
    return grades, judge_version


def consensus_v2(
    units: Sequence[Hashable],
    grades_by_judge: Mapping[str, Mapping[Hashable, int]],
) -> ConsensusV2:
    """Compute each unit's consensus as the lower median of the included judges.

    A judge missing strictly more than `MISSING_SHARE_LIMIT` of the pool's
    units is left out of that pool's consensus and reported with its missing
    share; a unit graded by no included judge is unjudged with a reason, never
    grade 0, and with every judge included a unit graded by both judges gets
    the lower median of the two grades.
    """
    pool: set[Hashable] = set()
    for unit in units:
        if unit in pool:
            raise ValueError("duplicate unit in the pool")
        pool.add(unit)
    for judge_grades in grades_by_judge.values():
        for unit, grade in judge_grades.items():
            if unit not in pool:
                raise ValueError("grade for a unit outside the pool")
            if type(grade) is not int or not 0 <= grade <= 3:
                raise ValueError("grades must be integers 0-3")
    total = len(units)
    missing = {
        judge: sum(1 for unit in units if unit not in judge_grades)
        for judge, judge_grades in grades_by_judge.items()
    }
    excluded: dict[str, float] = {}
    for judge, count in missing.items():
        share = count / total if total else 0.0
        if share > MISSING_SHARE_LIMIT:
            excluded[judge] = share
    included = tuple(sorted(judge for judge in grades_by_judge if judge not in excluded))
    consensus: dict[Hashable, int] = {}
    unjudged: dict[Hashable, str] = {}
    graded_by: dict[Hashable, tuple[str, ...]] = {}
    for unit in units:
        judged = [
            (grades_by_judge[judge][unit], judge)
            for judge in included
            if unit in grades_by_judge[judge]
        ]
        if judged:
            consensus[unit] = lower_median([grade for grade, _ in judged])
            graded_by[unit] = tuple(sorted(judge for _, judge in judged))
        else:
            unjudged[unit] = "no_valid_grade" if included else "no_included_judge"
    return ConsensusV2(
        grades=consensus,
        unjudged=unjudged,
        graded_by=graded_by,
        included=included,
        excluded=excluded,
        missing=missing,
    )


def ruler_cases(
    cases: Sequence[Mapping[str, Any]],
    grades: Mapping[tuple[str, str], int],
    unjudged: Mapping[tuple[str, str], str],
) -> dict[str, Any]:
    """Split cases into ruler-ready kept cases and excluded cases.

    A case is excluded when its deciding population, `seeds[:5]` followed by
    `sent`, holds a text hash with no grade for its `case_id`; it is
    reported with the unjudged reasons (`"not_graded"` when unknown) in
    first-occurrence order and never a substituted grade. Kept cases carry
    their seeds, sent and every grade of their case, so `precision_at_5`,
    `sent_precision` and `ndcg_at_5` accept them unchanged.
    Sent texts keep only their first occurrence, with repeats counted across
    kept and excluded cases; seeds retain their ranked order and repeats.
    """
    grades_by_case: dict[str, dict[str, int]] = {}
    for (case_id, text_sha256), grade in grades.items():
        grades_by_case.setdefault(case_id, {})[text_sha256] = grade
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    kept_counts: dict[str, int] = {}
    excluded_counts: dict[str, int] = {}
    subsets: set[str] = set()
    repeated_sent_texts = 0
    for case in cases:
        case_id = case["case_id"]
        if case_id in seen:
            raise ValueError("duplicate case id")
        seen.add(case_id)
        subset = case["subset"]
        subsets.add(subset)
        case_grades = grades_by_case.get(case_id, {})
        sent = list(dict.fromkeys(case["sent"]))
        repeated_sent_texts += len(case["sent"]) - len(sent)
        population = list(case["seeds"][:5]) + sent
        reasons: dict[str, str] = {}
        for text_sha256 in population:
            if text_sha256 not in case_grades:
                reason = unjudged.get((case_id, text_sha256), "not_graded")
                reasons.setdefault(text_sha256, reason)
        if reasons:
            excluded.append(
                {
                    "case_id": case_id,
                    "subset": subset,
                    "reason": "unjudged document in deciding population",
                    "unjudged": reasons,
                }
            )
            excluded_counts[subset] = excluded_counts.get(subset, 0) + 1
        else:
            kept.append(
                {
                    "case_id": case_id,
                    "subset": subset,
                    "seeds": list(case["seeds"]),
                    "sent": sent,
                    "grades": dict(case_grades),
                }
            )
            kept_counts[subset] = kept_counts.get(subset, 0) + 1
    return {
        "cases": kept,
        "excluded": excluded,
        "excluded_count": len(excluded),
        "repeated_sent_texts": repeated_sent_texts,
        "excluded_by_subset": {
            subset: excluded_counts.get(subset, 0) for subset in sorted(subsets)
        },
        "kept_by_subset": {subset: kept_counts.get(subset, 0) for subset in sorted(subsets)},
    }

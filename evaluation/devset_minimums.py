"""Minimums of the flags of plan step 1.3d, counted on the verified sets.

    python -m evaluation.devset_minimums

No network and no model. The plan gives a minimum at the reference sizes 60 and 100; the
minimum of a split is that number times the registered size of the split over the reference
size, rounded up (docs/specs/semantic-precision-metrics.md, «Drafts of plan step 1.3d»).
Development is counted over the verified files of pilot-v3, development and
development-replacements together, the holdout over holdout and holdout-replacements; a set
whose verification is not complete is not counted and is named as such.

A trap is a verified case whose `trap_type` is set. `ru_to_en` and `numeric` are the flags the
scripts compute. The safety-critical count that decides follows the plan's condition - the
right behaviour is stated word for word by a rule of the corpus: the flag true, the case not
`authority_unverified`, and at least one span, the quoted rule. Two wider counts are printed
beside it and decide nothing: every case with the flag, and those of them that are not
`authority_unverified`, the count «Label verification» registers.

A minimum that is not met is published as unmet and narrows the conclusion: nothing here
adds a case.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from evaluation import devset

EVALUATION = Path(__file__).resolve().parent
# The plan's minimums at its reference sizes (plan row 1.3d).
REFERENCE_SIZE = {"development": 60, "holdout": 100}
PLAN_MINIMUMS = {
    "development": {"ru_to_en": 12, "numeric": 12, "traps": 12},
    "holdout": {"ru_to_en": 20, "numeric": 20, "traps": 20, "safety_critical": 10},
}
# The verified sets of rubric v3 a split is counted over.
SETS = {
    "development": ("pilot-v3", "development", "development-replacements"),
    "holdout": ("holdout", "holdout-replacements"),
}


def minimums(split: str, size: int) -> dict[str, int]:
    """The minimums of a split of `size` cases: the plan's numbers scaled, rounded up."""
    reference = REFERENCE_SIZE[split]
    return {name: -(-number * size // reference) for name, number in PLAN_MINIMUMS[split].items()}


def counts(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """What the minimums are held against, on the verified cases of one split."""
    traps = Counter(case["trap_type"] for case in cases if case["trap_type"])
    flagged = [case for case in cases if case["flags"]["safety_critical"]]
    confirmed = [case for case in flagged if not case.get("authority_unverified")]
    return {
        "cases": len(cases),
        "ru_to_en": sum(bool(case["flags"]["ru_to_en"]) for case in cases),
        "numeric": sum(bool(case["flags"]["numeric"]) for case in cases),
        "traps": sum(traps.values()),
        "trap_types": {name: traps[name] for name in sorted(devset.TRAPS)},
        # The count the minimum is held against: a quoted rule of the corpus states the case.
        "safety_critical": sum(bool(case["evidence_spans"]) for case in confirmed),
        "safety_critical_flagged": len(flagged),
        "safety_critical_authority_confirmed": len(confirmed),
    }


def unmet(required: Mapping[str, int], counted: Mapping[str, Any]) -> list[str]:
    """The minimums a counted set does not meet, each with its count and its number."""
    missing = [
        f"{name}: {counted[name]} of {number}"
        for name, number in required.items()
        if counted[name] < number
    ]
    absent = [name for name, number in counted["trap_types"].items() if not number]
    if "traps" in required and absent:
        missing.append("trap types without a case: " + ", ".join(absent))
    return missing


def set_paths(name: str, directory: Path) -> tuple[Path, Path]:
    """The verified file and the register of one set of rubric v3."""
    stem = name.replace("-", "_")
    return (
        directory / f"devset_{stem}_verified.jsonl",
        directory / f"devset_{stem}_label_checks.json",
    )


def read_set(name: str, directory: Path) -> tuple[str, list[dict[str, Any]]]:
    """The state of one set and its verified cases.

    `absent` when the set has no register, `incomplete` while its verification is not
    complete - its cases are then not counted - and `complete` otherwise. A verified file
    that is not the one its register names is refused.
    """
    verified, register = set_paths(name, directory)
    if not register.exists():
        return "absent", []
    checks = json.loads(register.read_bytes())
    if not checks.get("complete"):
        return "incomplete", []
    data = verified.read_bytes()
    if hashlib.sha256(data).hexdigest() != checks["sha256"]["verified_set"]:
        raise ValueError(f"the verified file of {name} is not the one its register names")
    return "complete", [json.loads(line) for line in data.decode("utf-8").splitlines() if line]


def report(split: str, directory: Path = EVALUATION) -> dict[str, Any]:
    """The minimums of one split against its verified sets, as a capsule prints them."""
    registered = json.loads((directory / "devset_split.json").read_bytes())
    size = registered["splits"][split]["cases"]
    states: dict[str, str] = {}
    cases: list[dict[str, Any]] = []
    for name in SETS[split]:
        states[name], found = read_set(name, directory)
        cases += found
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError(f"a case stands in two verified sets of {split}")
    required = minimums(split, size)
    counted = counts(cases)
    return {
        "split": split,
        "registered_size": size,
        "reference_size": REFERENCE_SIZE[split],
        "sets": states,
        "minimums": required,
        "counts": counted,
        "unmet": unmet(required, counted),
    }


def main() -> int:
    try:
        result = [report(split) for split in SETS]
    except (OSError, ValueError, KeyError) as exc:
        print(f"refused: {exc}")
        return 2
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False, indent=1).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Plan slice 1.1: kappa of the registered P2 consensus to the two model references.

Offline: every grade is read from a published reply store; no model is called.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation import blinded_judge as p2  # noqa: E402
from scripts.ab_context_precision import sha256_file  # noqa: E402

SCHEMA_VERSION = "p2-model-reference-kappa/v1"
THRESHOLD = 0.7
P2_REPORT = "reports/p2/p2-blinded-judge-glm+sonnet.json"
OUT = "reports/p2/p2-model-reference-kappa.json"
CODE_FILES = ("scripts/p2_reference_kappa.py", "evaluation/blinded_judge.py")
JUDGE_STORES = {
    "glm": "reports/p2/replies/glm.jsonl",
    "sonnet": "reports/p2/replies/sonnet.jsonl",
}
REFERENCES: dict[str, dict[str, str]] = {
    "astra": {
        "directory": "reports/p2/astra-reference",
        "vendor": "OpenAI",
        "role": "vendor outside the judge set",
    },
    "opus": {
        "directory": "reports/p2/opus-reference",
        "vendor": "Anthropic",
        "role": "control: the vendor of the Sonnet judge, not an independent voice",
    },
}
# Published in the two reference capsules before this calculation; each must reproduce.
PUBLISHED_KAPPA = {
    ("astra", "opus"): 0.9727,
    ("glm", "astra"): 0.8824,
    ("sonnet", "astra"): 0.8930,
    ("glm", "opus"): 0.9133,
    ("sonnet", "opus"): 0.8950,
}
RULER_STATUS = {
    1: "consensus_not_used",
    2: "provisional_ruler",
    3: "model-cross-checked",
}

Grades = dict[str, tuple[int, ...]]


def _checked_grades(row: Mapping[str, Any], source: str) -> tuple[int, ...]:
    grades = row.get("grades")
    if (
        not isinstance(grades, list)
        or len(grades) != 5
        or any(isinstance(grade, bool) or not isinstance(grade, int) for grade in grades)
        or any(not 0 <= grade <= 3 for grade in grades)
    ):
        raise p2.NotEvidence(f"{source}: {row.get('case_id')} does not hold five grades 0-3")
    return tuple(grades)


def load_reference(
    root: Path, name: str, sample: Sequence[str]
) -> tuple[Grades, dict[str, str], dict[str, Any]]:
    """Grades of one reference in the original top-five order, bound to its summary."""
    directory = root / REFERENCES[name]["directory"]
    store = directory / "replies.jsonl"
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    digest = sha256_file(store)
    if summary.get("reply_store_sha256") != digest:
        raise p2.NotEvidence(f"{name}: reply store SHA-256 differs from its summary")
    rows = p2.read_store(store)
    if [row.get("case_id") for row in rows] != list(sample):
        raise p2.NotEvidence(f"{name}: reference cases differ from the P2 sample")
    if any(row.get("status") != "graded" or row.get("pool") != "H" for row in rows):
        raise p2.NotEvidence(f"{name}: a reference row is not a graded H case")
    grades = {str(row["case_id"]): _checked_grades(row, name) for row in rows}
    requests = {str(row["case_id"]): str(row["request_sha256"]) for row in rows}
    return grades, requests, {"summary": summary, "store_sha256": digest}


def load_judge(
    root: Path, report: Mapping[str, Any], judge: str, sample: Sequence[str]
) -> tuple[Grades, dict[str, str], str]:
    """Grades of one consensus judge from the reply store the P2 report names."""
    relative = JUDGE_STORES[judge]
    files = report["provenance"]["judge_routes"][judge]["reply_files"]
    if len(files) != 1 or not str(files[0]["path"]).replace("\\", "/").endswith("/" + relative):
        raise p2.NotEvidence(f"{judge}: the P2 report does not name {relative}")
    digest = sha256_file(root / relative)
    if files[0]["sha256"] != digest:
        raise p2.NotEvidence(f"{judge}: reply store SHA-256 differs from the P2 report")
    wanted = set(sample)
    graded: dict[str, list[dict[str, Any]]] = {}
    for row in p2.read_store(root / relative):
        if row.get("pool") == "H" and row.get("status") == "graded" and row["case_id"] in wanted:
            graded.setdefault(str(row["case_id"]), []).append(row)
    grades: Grades = {}
    requests: dict[str, str] = {}
    for case_id in sample:
        rows = graded.get(case_id, [])
        if len(rows) != 1:
            raise p2.NotEvidence(f"{judge}: {case_id} has {len(rows)} graded rows, expected one")
        grades[case_id] = _checked_grades(rows[0], judge)
        requests[case_id] = str(rows[0]["request_sha256"])
    return grades, requests, digest


def _units(grades: Mapping[str, Sequence[int]], case_ids: Sequence[str]) -> list[int]:
    return [grade for case_id in case_ids for grade in grades[case_id]]


def compare(
    first: Mapping[str, Sequence[int]],
    second: Mapping[str, Sequence[int]],
    case_ids: Sequence[str],
) -> dict[str, Any]:
    """Quadratic kappa with the `bootstrap_tau_ci` scheme of P2 moved to case clusters."""
    left = _units(first, case_ids)
    right = _units(second, case_ids)
    kappa = p2.quadratic_kappa(left, right)
    if kappa is None:
        raise p2.NotEvidence("kappa is undefined on the sample")
    rng = random.Random(p2.SEED)
    size = len(case_ids)
    draws: list[float] = []
    for _ in range(p2.BOOTSTRAP_SAMPLES):
        chosen = [case_ids[rng.randrange(size)] for _ in range(size)]
        value = p2.quadratic_kappa(_units(first, chosen), _units(second, chosen))
        if value is not None:
            draws.append(value)
    if not draws:
        raise p2.NotEvidence("kappa is undefined in every resample")
    draws.sort()
    pairs = Counter(zip(left, right, strict=True))
    return {
        "cases": size,
        "units": len(left),
        "quadratic_kappa": kappa,
        "ci95": [p2._percentile(draws, 0.025), p2._percentile(draws, 0.975)],
        "resamples_used": len(draws),
        "resamples_undefined": p2.BOOTSTRAP_SAMPLES - len(draws),
        "exact_agreement": sum(count for (a, b), count in pairs.items() if a == b),
        "agreement_at_grade_ge_2": sum(
            count for (a, b), count in pairs.items() if (a >= 2) == (b >= 2)
        ),
        "agreement_at_grade_ge_3": sum(
            count for (a, b), count in pairs.items() if (a >= 3) == (b >= 3)
        ),
        "cross_table": {str(a): {str(b): pairs[(a, b)] for b in range(4)} for a in range(4)},
    }


def rule_branch(ci95: Sequence[float]) -> str:
    low, high = ci95
    if high < THRESHOLD:
        return "below"
    if low >= THRESHOLD:
        return "clears"
    return "straddles"


def rule_verdict(branches: Mapping[str, str]) -> dict[str, Any]:
    """The three branches of decision D2 as changed by D11, read in their order."""
    if "below" in branches.values():
        number = 1
    elif "straddles" in branches.values():
        number = 2
    else:
        number = 3
    return {"branch": number, "ruler_status": RULER_STATUS[number], "per_reference": dict(branches)}


def build_report(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    report_path = root / P2_REPORT
    report = json.loads(report_path.read_text(encoding="utf-8"))
    sample = [str(case_id) for case_id in report["human"]["sample_case_ids"]]
    if len(sample) != 10 or len(set(sample)) != 10:
        raise p2.NotEvidence("the P2 sample is not ten distinct cases")

    grades: dict[str, Grades] = {}
    requests: dict[str, dict[str, str]] = {}
    inputs: dict[str, str] = {P2_REPORT: sha256_file(report_path)}
    models: dict[str, str] = {}
    for judge, relative in JUDGE_STORES.items():
        grades[judge], requests[judge], inputs[relative] = load_judge(root, report, judge, sample)
    for name, reference in REFERENCES.items():
        grades[name], requests[name], info = load_reference(root, name, sample)
        inputs[f"{reference['directory']}/replies.jsonl"] = info["store_sha256"]
        inputs[f"{reference['directory']}/summary.json"] = sha256_file(
            root / reference["directory"] / "summary.json"
        )
        if info["summary"].get("instruction_sha256") != p2.INSTRUCTION_SHA256:
            raise p2.NotEvidence(f"{name}: graded under another instruction")
        models[name] = str(info["summary"]["model"])
    if report["provenance"]["instruction_sha256"] != p2.INSTRUCTION_SHA256:
        raise p2.NotEvidence("the P2 report was graded under another instruction")
    for case_id in sample:
        if len({requests[source][case_id] for source in requests}) != 1:
            raise p2.NotEvidence(f"{case_id}: the four graders did not see one request")

    consensus, excluded = p2.consensus_grades(
        sample, {judge: grades[judge] for judge in JUDGE_STORES}
    )
    if excluded or list(consensus) != sample:
        raise p2.NotEvidence("the consensus does not cover all 50 documents of the sample")

    references: dict[str, Any] = {}
    for name, reference in REFERENCES.items():
        result = compare(consensus, grades[name], sample)
        references[name] = {
            "model": models[name],
            "vendor": reference["vendor"],
            "role": reference["role"],
            **result,
            "rule_branch": rule_branch(result["ci95"]),
        }
    between_references = compare(grades["astra"], grades["opus"], sample)
    judges = {
        judge: {name: compare(grades[judge], grades[name], sample) for name in REFERENCES}
        for judge in JUDGE_STORES
    }
    reproduced = {
        "astra+opus": between_references["quadratic_kappa"],
        **{
            f"{judge}+{name}": judges[judge][name]["quadratic_kappa"]
            for judge in JUDGE_STORES
            for name in REFERENCES
        },
    }
    for (first, second), published in PUBLISHED_KAPPA.items():
        if round(reproduced[f"{first}+{second}"], 4) != published:
            raise p2.NotEvidence(f"published kappa {first}+{second} {published} does not replay")

    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_class": "measured",
        "boundary": "Model check of the ruler; not human validation.",
        "sample": {
            "pool": "H",
            "case_ids": sample,
            "cases": len(sample),
            "documents": len(sample) * 5,
            "request_sha256": {case_id: requests["astra"][case_id] for case_id in sample},
        },
        "consensus": {
            "method": "lower median per document",
            "judges": sorted(JUDGE_STORES),
            "excluded": excluded,
            "grades": {case_id: list(consensus[case_id]) for case_id in sample},
        },
        "bootstrap": {
            "samples": p2.BOOTSTRAP_SAMPLES,
            "seed": p2.SEED,
            "method": "cases resampled with replacement, each with its five documents; "
            "percentile 95%, linear quantiles; a new generator per comparison",
        },
        "rule": {
            "threshold": THRESHOLD,
            "branches": {
                "1": "CI95 entirely below the threshold for either reference: consensus not used",
                "2": "otherwise CI95 straddles the threshold for either reference: slice 1.1b",
                "3": "otherwise CI95 entirely at or above the threshold for both references",
            },
        },
        "references": references,
        "verdict": rule_verdict({name: row["rule_branch"] for name, row in references.items()}),
        "orientation": {
            "enters_rule": False,
            "astra+opus": between_references,
            "judges": judges,
        },
        "published_kappa_replayed": {
            f"{first}+{second}": value for (first, second), value in PUBLISHED_KAPPA.items()
        },
        "provenance": {
            "inputs_sha256": inputs,
            "code_sha256": {relative: sha256_file(root / relative) for relative in CODE_FILES},
            "h_pool_sha256": report["provenance"]["pools"]["H"]["pool_sha256"],
            "instruction_sha256": p2.INSTRUCTION_SHA256,
            "model_requests": 0,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / OUT)
    args = parser.parse_args(argv)
    try:
        report = build_report()
    except p2.NotEvidence as error:
        print(f"NOT_EVIDENCE: {error}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    for name, row in report["references"].items():
        low, high = row["ci95"]
        print(f"{name}: kappa {row['quadratic_kappa']:.4f}, CI95 [{low:.4f}, {high:.4f}]")
    print(f"branch {report['verdict']['branch']}: {report['verdict']['ruler_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

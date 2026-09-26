"""Review, approve and pin the journey labels on the air-cargo cases.

Phase B labels 100 cases in batches of 20 (plan Q2): the agent proposes, the
domain-owner proxy approves. Approvals live in a sidecar pinned to the dataset;
the dataset is never rewritten. The manifest pins both files and their merged
``real_labelled`` count.

    python scripts/aircargo_labels.py report --batch 1     # what to review
    python scripts/aircargo_labels.py approve --batch 1 --approver julia
    python scripts/aircargo_labels.py verify               # gate

``verify`` is the gate: it fails when a case has no label, when a label
contradicts itself, or when the manifest no longer describes the dataset and
the sidecar.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.aircargo_labels import (  # noqa: E402
    APPROVALS_SCHEMA_VERSION,
    BATCH_SIZE,
    ApprovalSidecar,
    BatchApproval,
    LabelledCase,
    apply_approvals,
    build_manifest,
    dataset_digest,
    load_approval_sidecar,
    load_labelled_cases,
    summarise,
    verify_manifest,
)

DATASET_PATH = PROJECT_ROOT / "evaluation" / "curated_cases_aircargo.jsonl"
MANIFEST_PATH = PROJECT_ROOT / "evaluation" / "curated_cases_aircargo.manifest.json"
APPROVALS_PATH = PROJECT_ROOT / "evaluation" / "curated_cases_aircargo.approvals.json"
DATASET_NAME = "evaluation/curated_cases_aircargo.jsonl"
APPROVALS_NAME = "evaluation/curated_cases_aircargo.approvals.json"

CASE_SOURCE = "agent_authored_over_real_documents"
CASE_SOURCE_NOTE = (
    "The 201 source documents are real (copied from D:/TestRag/corpus into the "
    "aircargo tenant on 2026-05-30). The 100 questions over them were written "
    "by an agent, not sampled from support traffic, so an approved label makes "
    "the labelling real, not the case."
)


def _load() -> tuple[LabelledCase, ...]:
    return load_labelled_cases(DATASET_PATH, approvals_path=APPROVALS_PATH)


def _write_manifest(cases: tuple[LabelledCase, ...]) -> dict[str, object]:
    manifest = build_manifest(
        DATASET_PATH,
        cases,
        dataset=DATASET_NAME,
        case_source=CASE_SOURCE,
        case_source_note=CASE_SOURCE_NOTE,
        approvals_path=APPROVALS_PATH,
        approvals_name=APPROVALS_NAME,
    )
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def command_verify(_: argparse.Namespace) -> int:
    cases = _load()
    if not MANIFEST_PATH.exists():
        print(f"missing manifest: {MANIFEST_PATH}", file=sys.stderr)
        return 1
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    problems = verify_manifest(
        manifest,
        DATASET_PATH,
        cases,
        approvals_path=APPROVALS_PATH,
        approvals_name=APPROVALS_NAME,
    )
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    summary = summarise(cases)
    print(
        f"{summary.case_count} cases labelled, "
        f"{summary.real_labelled_count} real_labelled, "
        f"{summary.agent_labelled_count} agent_labelled"
    )
    return 0


def command_manifest(_: argparse.Namespace) -> int:
    manifest = _write_manifest(_load())
    print(f"wrote {MANIFEST_PATH.name} at {manifest['dataset_sha256']}")
    return 0


def command_report(args: argparse.Namespace) -> int:
    cases = _load()
    selected = [case for case in cases if args.batch is None or case.label.batch == args.batch]
    if not selected:
        print(f"no cases in batch {args.batch}", file=sys.stderr)
        return 1
    print("| Case | Question | Journey | Terminal | Root cause | Conf. | Note |")
    print("|---|---|---|---|---|---|---|")
    for case in selected:
        label = case.label
        print(
            f"| `{case.case_id}` | {case.query} | {label.journey.value} | "
            f"{label.expected_terminal.value} | {label.root_cause.value} | "
            f"{label.confidence.value} | {label.note or '—'} |"
        )
    return 0


def command_approve(args: argparse.Namespace) -> int:
    dataset_before = DATASET_PATH.read_bytes()
    cases = _load()
    batch = [case for case in cases if case.label.batch == args.batch]
    if not batch:
        print(f"no cases in batch {args.batch}", file=sys.stderr)
        return 1
    already = [case for case in batch if case.label.approved_by is not None]
    if already and not args.reapprove:
        print(
            f"batch {args.batch} already carries {len(already)} approvals; "
            "pass --reapprove to overwrite",
            file=sys.stderr,
        )
        return 1
    approval = BatchApproval(
        batch=args.batch,
        approver=args.approver,
        approved_at=args.approved_at,
        case_ids=tuple(case.case_id for case in batch),
        note=args.note,
    )
    if APPROVALS_PATH.exists():
        existing = load_approval_sidecar(APPROVALS_PATH)
        approvals = tuple(item for item in existing.approvals if item.batch != args.batch)
    else:
        approvals = ()
    sidecar = ApprovalSidecar(
        schema_version=APPROVALS_SCHEMA_VERSION,
        dataset=DATASET_NAME,
        dataset_sha256=dataset_digest(DATASET_PATH),
        approvals=(*approvals, approval),
    )
    apply_approvals(load_labelled_cases(DATASET_PATH), sidecar, dataset_path=DATASET_PATH)
    APPROVALS_PATH.write_text(
        json.dumps(sidecar.as_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    refreshed = _load()
    _write_manifest(refreshed)
    if DATASET_PATH.read_bytes() != dataset_before:
        raise RuntimeError("dataset bytes changed while recording the approval")
    summary = summarise(refreshed)
    print(
        f"batch {args.batch}: {len(batch)} cases approved by {args.approver}; "
        f"real_labelled is now {summary.real_labelled_count}/{summary.case_count}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("verify", help="fail if the labels or the manifest are wrong")
    subparsers.add_parser("manifest", help="regenerate the dataset manifest")

    report = subparsers.add_parser("report", help="print a review table")
    report.add_argument("--batch", type=int, default=None, help=f"batch of {BATCH_SIZE} cases")

    approve = subparsers.add_parser("approve", help="record a human approval for one batch")
    approve.add_argument("--batch", type=int, required=True)
    approve.add_argument("--approver", required=True, help="who approved, e.g. julia")
    approve.add_argument("--approved-at", type=date.fromisoformat, default=date.today())
    approve.add_argument("--note", default="", help="review note of at most 512 characters")
    approve.add_argument("--reapprove", action="store_true", help="overwrite existing approvals")

    args = parser.parse_args(argv)
    handlers = {
        "verify": command_verify,
        "manifest": command_manifest,
        "report": command_report,
        "approve": command_approve,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())

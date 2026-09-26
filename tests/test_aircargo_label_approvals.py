"""Approvals join onto the pinned air-cargo dataset without rewriting it."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from evaluation import aircargo_labels as labels
from scripts import aircargo_labels as script

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET = PROJECT_ROOT / "evaluation" / "curated_cases_aircargo.jsonl"
MANIFEST = PROJECT_ROOT / "evaluation" / "curated_cases_aircargo.manifest.json"
DATASET_NAME = "evaluation/curated_cases_aircargo.jsonl"
APPROVALS_NAME = "evaluation/curated_cases_aircargo.approvals.json"


def _dataset_copy(tmp_path: Path) -> Path:
    path = tmp_path / DATASET.name
    path.write_bytes(DATASET.read_bytes())
    return path


def _payload(path: Path, batches: tuple[int, ...] = (1, 2, 3, 4, 5)) -> dict:
    cases = labels.load_labelled_cases(path)
    return {
        "schema_version": "aircargo-label-approvals/v1.0",
        "dataset": DATASET_NAME,
        "dataset_sha256": labels.dataset_digest(path),
        "approvals": [
            {
                "batch": batch,
                "approver": "julia",
                "approved_at": "2026-09-25",
                "case_ids": [case.case_id for case in cases if case.label.batch == batch],
                "note": "Approved in batches of 20",
            }
            for batch in batches
        ],
    }


def _write_sidecar(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "curated_cases_aircargo.approvals.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def _script_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    dataset = _dataset_copy(tmp_path)
    manifest = tmp_path / MANIFEST.name
    manifest.write_bytes(MANIFEST.read_bytes())
    sidecar = tmp_path / "curated_cases_aircargo.approvals.json"
    monkeypatch.setattr(script, "DATASET_PATH", dataset)
    monkeypatch.setattr(script, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(script, "APPROVALS_PATH", sidecar, raising=False)
    return dataset, manifest, sidecar


def test_all_five_real_batches_are_accepted_and_verified(tmp_path: Path) -> None:
    """A valid reference sidecar is the false-reject control."""
    dataset = _dataset_copy(tmp_path)
    sidecar = _write_sidecar(tmp_path, _payload(dataset))

    cases = labels.load_labelled_cases(dataset, approvals_path=sidecar)
    manifest = labels.build_manifest(
        dataset,
        cases,
        dataset=DATASET_NAME,
        case_source="test",
        case_source_note="test",
        approvals_path=sidecar,
        approvals_name=APPROVALS_NAME,
    )

    assert len(cases) == 100
    assert all(case.label.approved_by == "julia" for case in cases)
    assert manifest["summary"]["real_labelled_count"] == 100
    assert manifest["summary"]["agent_labelled_count"] == 0
    assert manifest["summary"]["approved_batches"] == [1, 2, 3, 4, 5]
    assert manifest["evidence_class"] == "real_labelled"
    assert manifest["approvals"] == {
        "file": APPROVALS_NAME,
        "sha256": labels.dataset_digest(sidecar),
    }
    assert (
        labels.verify_manifest(
            manifest,
            dataset,
            cases,
            approvals_path=sidecar,
            approvals_name=APPROVALS_NAME,
        )
        == ()
    )


def test_missing_sidecar_preserves_agent_labels(tmp_path: Path) -> None:
    dataset = _dataset_copy(tmp_path)
    missing = tmp_path / "missing.approvals.json"

    for sidecar in (None, missing):
        cases = labels.load_labelled_cases(dataset, approvals_path=sidecar)
        manifest = labels.build_manifest(
            dataset,
            cases,
            dataset=DATASET_NAME,
            case_source="test",
            case_source_note="test",
            approvals_path=sidecar,
            approvals_name=APPROVALS_NAME,
        )
        assert all(case.label.evidence_class.value == "agent_labelled" for case in cases)
        assert manifest["summary"]["agent_labelled_count"] == 100
        assert manifest["approvals"] is None


def test_dataset_digest_mismatch_names_the_digest(tmp_path: Path) -> None:
    dataset = _dataset_copy(tmp_path)
    sidecar = _write_sidecar(tmp_path, _payload(dataset, (1,)))
    dataset.write_bytes(dataset.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="digest"):
        labels.load_labelled_cases(dataset, approvals_path=sidecar)


@pytest.mark.parametrize("defect", ["partial", "foreign", "unknown"])
def test_partial_or_foreign_batch_is_refused(tmp_path: Path, defect: str) -> None:
    dataset = _dataset_copy(tmp_path)
    payload = _payload(dataset, (2,))
    ids = payload["approvals"][0]["case_ids"]
    if defect == "partial":
        ids.pop()
    elif defect == "foreign":
        ids[-1] = _payload(dataset, (3,))["approvals"][0]["case_ids"][0]
    else:
        ids[-1] = "case-that-is-not-in-the-dataset"
    sidecar = _write_sidecar(tmp_path, payload)

    with pytest.raises(ValueError, match="batch 2"):
        labels.load_labelled_cases(dataset, approvals_path=sidecar)


@pytest.mark.parametrize("defect", ["batch", "case"])
def test_double_approval_is_refused(tmp_path: Path, defect: str) -> None:
    dataset = _dataset_copy(tmp_path)
    payload = _payload(dataset, (1,))
    if defect == "batch":
        payload["approvals"].append(copy.deepcopy(payload["approvals"][0]))
    else:
        ids = payload["approvals"][0]["case_ids"]
        ids[1] = ids[0]
    sidecar = _write_sidecar(tmp_path, payload)

    with pytest.raises(ValueError, match="(batch|case).*(twice|duplicate|repeated)"):
        labels.load_labelled_cases(dataset, approvals_path=sidecar)


def test_dataset_approval_cannot_be_overlaid(tmp_path: Path) -> None:
    dataset = _dataset_copy(tmp_path)
    lines = dataset.read_text(encoding="utf-8").splitlines()
    first = next(index for index, line in enumerate(lines) if line and not line.startswith("#"))
    row = json.loads(lines[first])
    row["label"]["approved_by"] = "prior_reviewer"
    row["label"]["evidence_class"] = "real_labelled"
    lines[first] = json.dumps(row, ensure_ascii=False)
    dataset.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    sidecar = _write_sidecar(tmp_path, _payload(dataset, (row["label"]["batch"],)))

    with pytest.raises(ValueError, match="already carries approved_by"):
        labels.load_labelled_cases(dataset, approvals_path=sidecar)


@pytest.mark.parametrize(
    ("defect", "problem"),
    [
        ("unknown_sidecar_field", "unknown.*sidecar"),
        ("missing_sidecar_field", "missing.*sidecar"),
        ("unknown_approval_field", "unknown.*approval"),
        ("missing_approval_field", "missing.*approval"),
        ("wrong_schema", "schema_version"),
        ("wrong_dataset", "dataset"),
        ("invalid_date", "approved_at"),
        ("long_note", "note"),
        ("agent_approver", "approver"),
        ("invalid_case_ids", "case_ids"),
    ],
)
def test_invalid_sidecar_fields_are_refused(tmp_path: Path, defect: str, problem: str) -> None:
    dataset = _dataset_copy(tmp_path)
    payload = _payload(dataset, (1,))
    approval = payload["approvals"][0]
    if defect == "unknown_sidecar_field":
        payload["reviewer_mood"] = "happy"
    elif defect == "missing_sidecar_field":
        del payload["dataset"]
    elif defect == "unknown_approval_field":
        approval["reviewer_mood"] = "happy"
    elif defect == "missing_approval_field":
        del approval["approved_at"]
    elif defect == "wrong_schema":
        payload["schema_version"] = "aircargo-label-approvals/v9.0"
    elif defect == "wrong_dataset":
        payload["dataset"] = "evaluation/other.jsonl"
    elif defect == "invalid_date":
        approval["approved_at"] = "2026-02-30"
    elif defect == "long_note":
        approval["note"] = "x" * 513
    elif defect == "agent_approver":
        approval["approver"] = "agent_reviewer"
    else:
        approval["case_ids"] = "not a list"
    sidecar = _write_sidecar(tmp_path, payload)

    with pytest.raises(ValueError, match=problem):
        labels.load_labelled_cases(dataset, approvals_path=sidecar)


def test_approve_preserves_raw_dataset_bytes_and_updates_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset, manifest, sidecar = _script_paths(tmp_path, monkeypatch)
    before = hashlib.sha256(dataset.read_bytes()).hexdigest()
    old_manifest = manifest.read_bytes()

    assert script.main(["approve", "--batch", "1", "--approver", "julia"]) == 0

    assert hashlib.sha256(dataset.read_bytes()).hexdigest() == before
    assert sidecar.exists()
    assert manifest.read_bytes() != old_manifest
    stored = json.loads(sidecar.read_text(encoding="utf-8"))
    assert stored["dataset"] == DATASET_NAME
    assert stored["dataset_sha256"] == labels.dataset_digest(dataset)
    assert stored["approvals"][0]["case_ids"] == [
        case.case_id for case in labels.load_labelled_cases(dataset) if case.label.batch == 1
    ]
    assert json.loads(manifest.read_text(encoding="utf-8"))["approvals"] == {
        "file": APPROVALS_NAME,
        "sha256": labels.dataset_digest(sidecar),
    }
    assert script.main(["verify"]) == 0


def test_reapproval_replaces_one_batch_and_keeps_batch_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _dataset, _manifest, sidecar = _script_paths(tmp_path, monkeypatch)
    assert (
        script.main(
            ["approve", "--batch", "2", "--approver", "julia", "--approved-at", "2026-09-25"]
        )
        == 0
    )
    assert script.main(["approve", "--batch", "1", "--approver", "julia"]) == 0
    assert script.main(["approve", "--batch", "2", "--approver", "other"]) == 1
    assert (
        script.main(
            [
                "approve",
                "--batch",
                "2",
                "--approver",
                "other",
                "--approved-at",
                "2026-09-26",
                "--note",
                "Second review",
                "--reapprove",
            ]
        )
        == 0
    )

    stored = json.loads(sidecar.read_text(encoding="utf-8"))
    assert [row["batch"] for row in stored["approvals"]] == [1, 2]
    assert stored["approvals"][1]["approver"] == "other"
    assert stored["approvals"][1]["approved_at"] == "2026-09-26"
    assert stored["approvals"][1]["note"] == "Second review"
    assert sidecar.read_bytes().endswith(b"\n")
    assert b"\r\n" not in sidecar.read_bytes()


def test_verify_names_sidecar_digest_after_hand_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    dataset, _manifest, sidecar = _script_paths(tmp_path, monkeypatch)
    _write_sidecar(tmp_path, _payload(dataset, (1,)))
    assert script.main(["manifest"]) == 0
    assert script.main(["verify"]) == 0
    stored = json.loads(sidecar.read_text(encoding="utf-8"))
    stored["approvals"][0]["approver"] = "another_reviewer"
    _write_sidecar(tmp_path, stored)

    assert script.main(["verify"]) == 1
    error = capsys.readouterr().err
    assert "approvals" in error and "sha256" in error


@pytest.mark.parametrize("command", ["report", "manifest", "verify"])
def test_read_commands_validate_the_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    dataset, _manifest, _sidecar = _script_paths(tmp_path, monkeypatch)
    payload = _payload(dataset, (1,))
    payload["dataset_sha256"] = "0" * 64
    _write_sidecar(tmp_path, payload)

    with pytest.raises(ValueError, match="digest"):
        script.main([command])

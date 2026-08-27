"""Score the shipment-status admission gate against the pinned B.1 labels."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from evaluation.aircargo_labels import (
    Journey,
    LabelledCase,
    dataset_digest_bytes,
    load_labelled_cases_from_bytes,
)
from resolution.application.shipment_status import ShipmentStatusShadowLoop

REPORT_SCHEMA_VERSION: Final[str] = "journey-admission-report/v1.2"
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS_PATH: Final[Path] = PROJECT_ROOT / "evaluation" / "curated_cases_aircargo.jsonl"
DEFAULT_MANIFEST_PATH: Final[Path] = (
    PROJECT_ROOT / "evaluation" / "curated_cases_aircargo.manifest.json"
)
CODE_DIGEST_PATHS: Final[tuple[Path, ...]] = (
    Path("evaluation/aircargo_labels.py"),
    Path("evaluation/journey_admission.py"),
    Path("scripts/journey_admission_report.py"),
    Path("resolution/application/shipment_status.py"),
)
CODE_DIGEST_FRAMING: Final[str] = (
    "for each listed path in order: 8-byte big-endian UTF-8 path length, "
    "path bytes, 8-byte big-endian content length, content bytes"
)
UNKNOWN_HEAD_SHA: Final[str] = "unknown"
KERNEL_FUNCTION: Final[str] = (
    "resolution.application.shipment_status.ShipmentStatusShadowLoop._is_admitted"
)
DECLINE_INTERPRETATION: Final[str] = (
    "shipment_status is the only admitted journey. out_of_scope is declined; "
    "customs_docs and exception_escalation are also declined because no kernel "
    "loop exists for them. Those declines are not routing opinions."
)
_LATIN_ALPHABETIC_CHARACTER: Final[re.Pattern[str]] = re.compile(r"[A-Za-z]")
_DECLINE_REASON_KEYS: Final[tuple[str, ...]] = (
    "no_shipment_reference",
    "no_domain_noun",
    "no_status_cue",
    "neither_domain_noun_nor_status_cue",
)


class CorpusDigestMismatchError(RuntimeError):
    """The report must not turn an unpinned corpus into published evidence."""


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    """One kernel decision paired with the B.1 journey label."""

    journey: Journey
    admitted: bool

    @property
    def expected_admission(self) -> bool:
        """Only the shipment-status loop exists in the kernel today."""
        return self.journey is Journey.SHIPMENT_STATUS


@dataclass(frozen=True, slots=True)
class AdmissionConfusionMatrix:
    """Binary admission-gate outcomes, where shipment-status is the positive class."""

    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int

    @property
    def total(self) -> int:
        return self.true_positive + self.false_positive + self.false_negative + self.true_negative

    @property
    def precision(self) -> float | None:
        admitted = self.true_positive + self.false_positive
        return self.true_positive / admitted if admitted else None

    @property
    def recall(self) -> float | None:
        expected = self.true_positive + self.false_negative
        return self.true_positive / expected if expected else None

    def as_dict(self) -> dict[str, int]:
        return {
            "true_positive": self.true_positive,
            "false_positive": self.false_positive,
            "false_negative": self.false_negative,
            "true_negative": self.true_negative,
            "total": self.total,
        }


@dataclass(frozen=True, slots=True)
class CodeProvenance:
    """Source identity for the exact report and kernel bytes just evaluated."""

    head_sha: str
    code_digest: str
    code_digest_paths: tuple[str, ...]
    reproducible_from_head: bool


@dataclass(frozen=True, slots=True)
class JourneyAdmissionReport:
    """The publishable score and the inputs needed to reproduce it."""

    corpus_path: str
    corpus_sha256: str
    head_sha: str
    code_digest: str
    code_digest_paths: tuple[str, ...]
    reproducible_from_head: bool
    journey_counts: dict[str, int]
    confusion_matrix: AdmissionConfusionMatrix
    decline_reasons: dict[str, int]
    script_composition: dict[str, int]
    vocabulary_reachability: dict[str, int]

    @property
    def case_count(self) -> int:
        return self.confusion_matrix.total

    @property
    def git_sha(self) -> str:
        """Backward-compatible alias for callers of the pre-v1.2 report object."""
        return self.head_sha

    def as_dict(self) -> dict[str, object]:
        return {
            "report_schema_version": REPORT_SCHEMA_VERSION,
            "corpus_path": self.corpus_path,
            "corpus_sha256": self.corpus_sha256,
            "head_sha": self.head_sha,
            "code_digest": self.code_digest,
            "code_digest_paths": list(self.code_digest_paths),
            "code_digest_framing": CODE_DIGEST_FRAMING,
            "reproducible_from_head": self.reproducible_from_head,
            "kernel_function": KERNEL_FUNCTION,
            "case_count": self.case_count,
            "journey_counts": dict(self.journey_counts),
            "confusion_matrix": self.confusion_matrix.as_dict(),
            "decline_reasons": dict(self.decline_reasons),
            "script_composition": dict(self.script_composition),
            "vocabulary_reachability": dict(self.vocabulary_reachability),
            "admission_precision": self.confusion_matrix.precision,
            "admission_recall": self.confusion_matrix.recall,
            "decline_interpretation": DECLINE_INTERPRETATION,
        }


def _verify_corpus_digest_bytes(corpus_bytes: bytes, manifest_path: Path) -> str:
    """Return the digest of one pinned corpus snapshot, or refuse to score it."""
    try:
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusDigestMismatchError(f"cannot read manifest {manifest_path}: {error}") from error
    if not isinstance(manifest_payload, dict):
        raise CorpusDigestMismatchError(f"manifest {manifest_path} must be a JSON object")
    expected_digest = manifest_payload.get("dataset_sha256")
    if not isinstance(expected_digest, str) or not expected_digest:
        raise CorpusDigestMismatchError(f"manifest {manifest_path} has no dataset_sha256")

    actual_digest = dataset_digest_bytes(corpus_bytes)
    if actual_digest != expected_digest:
        raise CorpusDigestMismatchError(
            f"corpus sha256 mismatch: manifest has {expected_digest}, corpus is {actual_digest}"
        )
    return actual_digest


def _read_corpus_bytes(corpus_path: Path) -> bytes:
    try:
        return corpus_path.read_bytes()
    except OSError as error:
        raise CorpusDigestMismatchError(f"cannot read corpus {corpus_path}: {error}") from error


def verify_corpus_digest(corpus_path: Path, manifest_path: Path) -> str:
    """Return the pinned corpus digest, or refuse to score the changed corpus."""
    return _verify_corpus_digest_bytes(_read_corpus_bytes(corpus_path), manifest_path)


def kernel_admits(question: str) -> bool:
    """Delegate to T-01's kernel function; never copy its lexical rule here."""
    return ShipmentStatusShadowLoop._is_admitted((question,))


def _report_source_contents(project_root: Path) -> tuple[bytes, ...]:
    return tuple((project_root / path).read_bytes() for path in CODE_DIGEST_PATHS)


def _source_digest(
    source_contents: Iterable[bytes],
    *,
    source_paths: Iterable[Path] | None = None,
) -> str:
    """Hash each source with its identity and byte length in an unambiguous frame."""
    digest = hashlib.sha256()
    if source_paths is None:
        entries = (
            (str(index).encode("ascii"), contents)
            for index, contents in enumerate(source_contents)
        )
    else:
        entries = (
            (path.as_posix().encode("utf-8"), contents)
            for path, contents in zip(source_paths, source_contents, strict=True)
        )
    for path_bytes, contents in entries:
        digest.update(len(path_bytes).to_bytes(8, "big"))
        digest.update(path_bytes)
        digest.update(len(contents).to_bytes(8, "big"))
        digest.update(contents)
    return digest.hexdigest()


def _run_git(
    arguments: Sequence[str],
    *,
    project_root: Path,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes] | None:
    """Run one best-effort Git query without compromising the report itself."""
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=project_root,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError:
        return None


def head_git_sha(project_root: Path = PROJECT_ROOT) -> str:
    """Return HEAD's revision, or ``unknown`` when Git cannot provide one."""
    result = _run_git(("rev-parse", "HEAD"), project_root=project_root)
    if result is None or result.returncode != 0:
        return UNKNOWN_HEAD_SHA
    head_sha = result.stdout.decode("ascii", errors="replace").strip()
    return head_sha or UNKNOWN_HEAD_SHA


def _head_matches_source_contents(
    *,
    project_root: Path,
    source_contents: Sequence[bytes],
) -> bool:
    """Compare every report input to HEAD in one Git batch query."""
    requests = b"".join(
        b"HEAD:" + path.as_posix().encode("utf-8") + b"\n" for path in CODE_DIGEST_PATHS
    )
    result = _run_git(
        ("cat-file", "--batch"),
        project_root=project_root,
        input_bytes=requests,
    )
    if result is None or result.returncode != 0:
        return False

    offset = 0
    for expected_contents in source_contents:
        header_end = result.stdout.find(b"\n", offset)
        if header_end < 0:
            return False
        header = result.stdout[offset:header_end].split()
        if len(header) != 3 or header[1] != b"blob":
            return False
        try:
            content_size = int(header[2])
        except ValueError:
            return False
        content_start = header_end + 1
        content_end = content_start + content_size
        if (
            content_end >= len(result.stdout)
            or result.stdout[content_end : content_end + 1] != b"\n"
            or result.stdout[content_start:content_end] != expected_contents
        ):
            return False
        offset = content_end + 1
    return offset == len(result.stdout)


def code_provenance(project_root: Path = PROJECT_ROOT) -> CodeProvenance:
    """Hash report inputs and state whether those exact bytes exist at HEAD.

    The digest uses ``CODE_DIGEST_FRAMING`` for paths in ``code_digest_paths``.
    Git provenance is deliberately best effort: an unavailable or failing Git
    executable never suppresses a score.
    """
    source_contents = _report_source_contents(project_root)
    head_sha = head_git_sha(project_root)
    reproducible_from_head = (
        head_sha != UNKNOWN_HEAD_SHA
        and _head_matches_source_contents(
            project_root=project_root,
            source_contents=source_contents,
        )
    )
    return CodeProvenance(
        head_sha=head_sha,
        code_digest=_source_digest(source_contents, source_paths=CODE_DIGEST_PATHS),
        code_digest_paths=tuple(path.as_posix() for path in CODE_DIGEST_PATHS),
        reproducible_from_head=reproducible_from_head,
    )


def admission_confusion_matrix(
    decisions: Iterable[AdmissionDecision],
) -> AdmissionConfusionMatrix:
    """Build the positive/negative admission matrix from labelled decisions."""
    true_positive = 0
    false_positive = 0
    false_negative = 0
    true_negative = 0
    for decision in decisions:
        if decision.admitted and decision.expected_admission:
            true_positive += 1
        elif decision.admitted:
            false_positive += 1
        elif decision.expected_admission:
            false_negative += 1
        else:
            true_negative += 1
    return AdmissionConfusionMatrix(
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        true_negative=true_negative,
    )


def score_labelled_cases(
    cases: Sequence[LabelledCase],
    *,
    corpus_path: Path,
    corpus_sha256: str,
    provenance: CodeProvenance,
) -> JourneyAdmissionReport:
    """Run T-01 over every labelled question and retain its exact decisions."""
    journey_counts = {journey.value: 0 for journey in Journey}
    decisions: list[AdmissionDecision] = []
    decline_reasons = {reason: 0 for reason in _DECLINE_REASON_KEYS}
    script_composition = {"contains_latin": 0, "contains_no_latin": 0}
    vocabulary_reachability = {
        "contains_domain_noun": 0,
        "contains_status_cue": 0,
        "contains_both_domain_noun_and_status_cue": 0,
    }
    for case in cases:
        journey_counts[case.label.journey.value] += 1
        signals = ShipmentStatusShadowLoop.admission_signals((case.query,))
        admitted = kernel_admits(case.query)
        decisions.append(
            AdmissionDecision(
                journey=case.label.journey,
                admitted=admitted,
            )
        )
        if _LATIN_ALPHABETIC_CHARACTER.search(case.query) is None:
            script_composition["contains_no_latin"] += 1
        else:
            script_composition["contains_latin"] += 1
        if signals.has_domain_noun:
            vocabulary_reachability["contains_domain_noun"] += 1
        if signals.has_status_cue:
            vocabulary_reachability["contains_status_cue"] += 1
        if signals.has_domain_noun and signals.has_status_cue:
            vocabulary_reachability["contains_both_domain_noun_and_status_cue"] += 1
        if not admitted:
            if not signals.has_shipment_reference:
                decline_reasons["no_shipment_reference"] += 1
            if not signals.has_domain_noun:
                decline_reasons["no_domain_noun"] += 1
            if not signals.has_status_cue:
                decline_reasons["no_status_cue"] += 1
            if not signals.has_domain_noun and not signals.has_status_cue:
                decline_reasons["neither_domain_noun_nor_status_cue"] += 1
    return JourneyAdmissionReport(
        corpus_path=str(corpus_path),
        corpus_sha256=corpus_sha256,
        head_sha=provenance.head_sha,
        code_digest=provenance.code_digest,
        code_digest_paths=provenance.code_digest_paths,
        reproducible_from_head=provenance.reproducible_from_head,
        journey_counts=journey_counts,
        confusion_matrix=admission_confusion_matrix(decisions),
        decline_reasons=decline_reasons,
        script_composition=script_composition,
        vocabulary_reachability=vocabulary_reachability,
    )


def score_default_corpus(
    *,
    git_sha: str | None = None,
    corpus_path: Path = DEFAULT_CORPUS_PATH,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    project_root: Path = PROJECT_ROOT,
) -> JourneyAdmissionReport:
    """Verify the repository corpus, then publish one reproducible score.

    ``git_sha`` remains accepted for source compatibility with v1.1 callers,
    but cannot override the separately reported HEAD provenance.
    """
    corpus_bytes = _read_corpus_bytes(corpus_path)
    corpus_sha256 = _verify_corpus_digest_bytes(corpus_bytes, manifest_path)
    cases = load_labelled_cases_from_bytes(corpus_bytes, source_name=corpus_path.name)
    provenance = code_provenance(project_root)
    _ = git_sha
    return score_labelled_cases(
        cases,
        corpus_path=corpus_path,
        corpus_sha256=corpus_sha256,
        provenance=provenance,
    )


def format_report(report: JourneyAdmissionReport) -> str:
    """Render the human-readable report with the same facts as :meth:`as_dict`."""
    matrix = report.confusion_matrix
    precision = "undefined" if matrix.precision is None else f"{matrix.precision:.4f}"
    recall = "undefined" if matrix.recall is None else f"{matrix.recall:.4f}"
    journey_lines = "\n".join(
        f"  {journey}: {count}" for journey, count in report.journey_counts.items()
    )
    decline_reason_lines = "\n".join(
        f"  {reason}: {count}" for reason, count in report.decline_reasons.items()
    )
    script_composition_lines = "\n".join(
        f"  {category}: {count}" for category, count in report.script_composition.items()
    )
    vocabulary_reachability_lines = "\n".join(
        f"  {category}: {count}"
        for category, count in report.vocabulary_reachability.items()
    )
    return "\n".join(
        (
            "Journey admission report",
            f"Corpus: {report.corpus_path}",
            f"Corpus sha256: {report.corpus_sha256}",
            f"HEAD sha: {report.head_sha}",
            f"Code digest (sha256): {report.code_digest}",
            f"Code digest framing: {CODE_DIGEST_FRAMING}",
            "Code digest paths (in order):",
            *(f"  {path}" for path in report.code_digest_paths),
            f"Reproducible from HEAD: {str(report.reproducible_from_head).lower()}",
            *(
                (
                    "Reproducibility note: this score uses the listed working-tree "
                    "bytes and cannot be reproduced from HEAD.",
                )
                if not report.reproducible_from_head
                else ()
            ),
            f"Kernel function: {KERNEL_FUNCTION}",
            f"Cases: {report.case_count}",
            "Counts per journey:",
            journey_lines,
            "Confusion matrix (positive = shipment_status admitted):",
            f"  true_positive: {matrix.true_positive}",
            f"  false_positive: {matrix.false_positive}",
            f"  false_negative: {matrix.false_negative}",
            f"  true_negative: {matrix.true_negative}",
            f"  total: {matrix.total}",
            "Decline reasons (declined cases only):",
            decline_reason_lines,
            "Script composition:",
            script_composition_lines,
            "Vocabulary reachability:",
            vocabulary_reachability_lines,
            f"Admission precision: {precision}",
            f"Admission recall: {recall}",
            f"Note: {DECLINE_INTERPRETATION}",
        )
    )


__all__ = [
    "AdmissionConfusionMatrix",
    "AdmissionDecision",
    "CODE_DIGEST_PATHS",
    "CodeProvenance",
    "CorpusDigestMismatchError",
    "DECLINE_INTERPRETATION",
    "DEFAULT_CORPUS_PATH",
    "DEFAULT_MANIFEST_PATH",
    "JourneyAdmissionReport",
    "KERNEL_FUNCTION",
    "REPORT_SCHEMA_VERSION",
    "admission_confusion_matrix",
    "code_provenance",
    "format_report",
    "head_git_sha",
    "kernel_admits",
    "score_default_corpus",
    "score_labelled_cases",
    "verify_corpus_digest",
]

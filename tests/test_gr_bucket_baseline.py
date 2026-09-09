"""GR-0.3: the phase C retrieval baseline, split by question class.

`docs/specs/retrieval-buckets.md` requires a retrieval number reported per
question class, with the case count of every class beside its metrics and the
digest of the candidate pool it was post-processed from. These tests are the
gate for `scripts/ab_context_precision.py`'s bucket report:

* a synthetic pool plus a synthetic sidecar produces the expected per-class
  rows, including a class with zero cases (which must not read as a zero
  measurement);
* the report refuses to run when the sidecar's pinned dataset digest disagrees
  with the dataset it is joined onto;
* two runs over the same inputs produce byte-identical JSON — there is no
  timestamp in the report at all — and the measured body stays identical even
  when the git provenance fields are left unpinned;
* the numbers quoted in `docs/evidence/gr0-bucket-baseline.md` are the numbers
  in the committed `reports/gr/gr0-bucket-baseline.json`, so the prose cannot
  drift from the artifact;
* the committed aggregate still reconciles with the published phase C.1a
  context precision / recall, which is what makes it the same ruler.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

from evaluation.question_class_labels import DatasetDigestMismatchError
from scripts.ab_context_precision import (
    _stored_path,
    build_bucket_report,
    render_bucket_table,
    write_bucket_report,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT = PROJECT_ROOT / "reports" / "gr" / "gr0-bucket-baseline.json"
CAPSULE = PROJECT_ROOT / "docs" / "evidence" / "gr0-bucket-baseline.md"

# Literals from CURRENT_STATE.md / the checked-in C.1a report. Not imported from
# production code, so moving a constant and the report together cannot quiet
# this test.
PUBLISHED_PHASE_C_PRECISION = 0.5067
PUBLISHED_PHASE_C_RECALL = 0.9050
PUBLISHED_PHASE_C_DATASET_SHA256 = (
    "3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720"
)

FAKE_COMMIT = "0" * 40


# ---------------------------------------------------------------------------
# Synthetic fixture: four cases, three classes used, one class empty
# ---------------------------------------------------------------------------

_CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "syn-one",
        "query": "какие поля нужны для допуска груза",
        "kws": ["поля", "допуск"],
        "question_class": "single_hop",
        "cands": [
            "Для допуска груза нужны поля маркировки отправителя.",
            "Общие сведения о складской логистике без конкретики.",
        ],
    },
    {
        "case_id": "syn-two",
        "query": "когда нужен юрист по претензии",
        "kws": ["юрист", "эскалаци"],
        "question_class": "single_hop",
        "cands": [
            "Юрист подключается при крупной претензии клиента.",
            "Порядок первичного ответа на претензию без эскалации.",
        ],
    },
    {
        "case_id": "syn-three",
        "query": "таможенное оформление авиагруза данные",
        "kws": ["таможен", "декларац"],
        "question_class": "multi_hop",
        "cands": [
            "Складские операции и хранение груза на терминале.",
            "Общие правила приёмки груза без оформления.",
        ],
    },
    {
        "case_id": "syn-four",
        "query": "сколько хранится груз на складе",
        "kws": ["хранени"],
        "question_class": "aggregation",
        "cands": [
            "Срок хранения груза на складе — трое суток.",
            "Тарифы на дополнительное хранение публикуются отдельно.",
        ],
    },
)


def _write_fixture(root: Path, *, top_k: int = 2) -> dict[str, Path]:
    """Write a tiny dataset + pool + sidecar + manifests under ``root``."""
    root.mkdir(parents=True, exist_ok=True)
    dataset = root / "cases.jsonl"
    pool = root / "pool.json"
    sidecar = root / "classes.jsonl"
    label_manifest = root / "classes.manifest.json"
    corpus_manifest = root / "corpus.manifest.json"

    dataset.write_text(
        "".join(
            json.dumps(
                {
                    "case_id": case["case_id"],
                    "tenant_id": "aircargo",
                    "query": case["query"],
                    "expected": {"answer_contains": list(case["kws"])},
                },
                ensure_ascii=False,
            )
            + "\n"
            for case in _CASES
        ),
        encoding="utf-8",
        newline="\n",
    )
    pool.write_text(
        json.dumps(
            [
                {
                    "case_id": case["case_id"],
                    "query": case["query"],
                    "kws": list(case["kws"]),
                    "rerank_k": top_k,
                    "cands": list(case["cands"]),
                    "cand_sources": [f"{case['case_id']}.md"] * len(case["cands"]),
                }
                for case in _CASES
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
        newline="\n",
    )
    sidecar.write_text(
        "".join(
            json.dumps(
                {
                    "case_id": case["case_id"],
                    "question_class": case["question_class"],
                    "reason": "synthetic fixture label",
                    "labelled_by": "agent:test",
                    "labelled_at": "2026-09-09",
                    "batch": 1,
                    "approved_by": None,
                },
                ensure_ascii=False,
            )
            + "\n"
            for case in _CASES
        ),
        encoding="utf-8",
        newline="\n",
    )
    label_manifest.write_text(
        json.dumps(
            {
                "schema_version": "aircargo-question-class-manifest/v1.0",
                "dataset": dataset.name,
                "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
                "case_count": len(_CASES),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
        newline="\n",
    )
    corpus_manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "synthetic",
                "root": "tests/fixtures/synthetic",
                "corpus_sha256": "f" * 64,
                "file_count": 3,
                "files": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
        newline="\n",
    )
    return {
        "dataset": dataset,
        "pool": pool,
        "sidecar": sidecar,
        "label_manifest": label_manifest,
        "corpus_manifest": corpus_manifest,
    }


def _report_for(paths: dict[str, Path], **overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "pool_path": paths["pool"],
        "dataset_path": paths["dataset"],
        "sidecar_path": paths["sidecar"],
        "label_manifest_path": paths["label_manifest"],
        "corpus_manifest_path": paths["corpus_manifest"],
        "expected_cases": len(_CASES),
        "top_k": 2,
        "code_commit": FAKE_COMMIT,
    }
    kwargs.update(overrides)
    return build_bucket_report(**kwargs)


def _buckets_by_class(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["question_class"]: row for row in report["buckets"]}


# ---------------------------------------------------------------------------
# The per-class rows
# ---------------------------------------------------------------------------


def test_a_synthetic_pool_produces_the_expected_per_class_rows(tmp_path: Path) -> None:
    report = _report_for(_write_fixture(tmp_path))
    buckets = _buckets_by_class(report)

    assert sorted(buckets) == ["aggregation", "global", "multi_hop", "single_hop"]
    assert buckets["single_hop"]["num_cases"] == 2
    assert buckets["multi_hop"]["num_cases"] == 1
    assert buckets["aggregation"]["num_cases"] == 1
    assert buckets["global"]["num_cases"] == 0

    # syn-one and syn-two carry both keywords in the top-2; syn-three carries
    # neither; syn-four carries its only keyword.
    assert buckets["single_hop"]["FULL"] == 2
    assert buckets["single_hop"]["context_recall"] == pytest.approx(1.0)
    assert buckets["multi_hop"]["MISS"] == 1
    assert buckets["multi_hop"]["context_recall"] == pytest.approx(0.0)
    assert buckets["aggregation"]["FULL"] == 1

    assert report["aggregate"]["num_cases"] == len(_CASES)
    assert report["aggregate"]["FULL"] == 3
    assert report["aggregate"]["MISS"] == 1
    assert report["aggregate"]["context_recall"] == pytest.approx(0.75)


def test_a_class_with_no_cases_is_reported_and_is_not_a_measured_zero(
    tmp_path: Path,
) -> None:
    report = _report_for(_write_fixture(tmp_path))
    empty = _buckets_by_class(report)["global"]

    assert empty["num_cases"] == 0
    # A zero-case class must not claim precision 0.0 — that reads as a measured
    # failure rather than as "nothing was measured here".
    assert empty["context_precision"] is None
    assert empty["context_recall"] is None
    assert (empty["FULL"], empty["PART"], empty["MISS"]) == (0, 0, 0)


def test_every_printed_class_row_carries_its_case_count(tmp_path: Path) -> None:
    report = _report_for(_write_fixture(tmp_path))
    table = render_bucket_table(report)

    for row in report["buckets"]:
        line = next(
            (
                ln
                for ln in table.splitlines()
                if ln.strip().startswith(f"| {row['question_class']} ")
            ),
            None,
        )
        assert line is not None, f"no printed row for class {row['question_class']}"
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        assert cells[1] == str(row["num_cases"])
    assert str(report["aggregate"]["num_cases"]) in table


# ---------------------------------------------------------------------------
# Fail-closed on digest drift
# ---------------------------------------------------------------------------


def test_the_report_refuses_a_sidecar_pinned_to_another_dataset(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path)
    manifest = json.loads(paths["label_manifest"].read_text(encoding="utf-8"))
    manifest["dataset_sha256"] = "a" * 64
    paths["label_manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )

    with pytest.raises(DatasetDigestMismatchError) as excinfo:
        _report_for(paths)

    assert "a" * 64 in str(excinfo.value)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_two_runs_over_the_same_inputs_produce_identical_json(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path)
    first = write_bucket_report(_report_for(paths), tmp_path / "out" / "first.json")
    second = write_bucket_report(_report_for(paths), tmp_path / "out" / "second.json")

    assert first.read_bytes() == second.read_bytes()
    # Nothing time-dependent may be in the compared body at all.
    body = first.read_text(encoding="utf-8")
    assert "created_at" not in body
    assert "timestamp" not in body


def _measured_body(report: dict[str, Any]) -> str:
    """The report without its two git provenance fields, as canonical JSON."""
    stripped = json.loads(json.dumps(report))
    code = stripped["provenance"]["code"]
    code.pop("commit", None)
    code.pop("tree_clean", None)
    return json.dumps(stripped, ensure_ascii=False, indent=2, sort_keys=True)


def test_the_measured_body_is_identical_when_the_git_fields_are_not_pinned(
    tmp_path: Path,
) -> None:
    """Determinism with ``_git_commit()`` inside the tested surface.

    ``_report_for`` pins ``code_commit``, which bypasses ``_git_commit``
    entirely; this pair calls ``build_bucket_report(code_commit=None)`` so the
    real git lookup runs. What is guaranteed — and asserted — is that the
    measured body (per-class rows, aggregate, per-case table, digests, config)
    is identical across the two builds. ``provenance.code.commit`` and
    ``provenance.code.tree_clean`` track HEAD by design and will differ across
    a commit; this test runs inside one process and therefore cannot assert
    anything across a commit boundary, and does not pretend to. It only
    requires that both fields are present and well-formed.
    """
    paths = _write_fixture(tmp_path)
    first = _report_for(paths, code_commit=None)
    second = _report_for(paths, code_commit=None)

    assert _measured_body(first) == _measured_body(second)

    for report in (first, second):
        code = report["provenance"]["code"]
        assert code["commit"] == "unknown" or re.fullmatch(r"[0-9a-f]{40}", code["commit"])
        assert code["tree_clean"] is None or isinstance(code["tree_clean"], bool)
        # The digests that actually pin the code are per file, not the commit.
        assert "scripts/ab_context_precision.py" in code["files"]


def test_the_report_records_the_pool_digest_and_the_configuration(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path)
    report = _report_for(paths)
    provenance = report["provenance"]

    assert provenance["pool_sha256"] == hashlib.sha256(paths["pool"].read_bytes()).hexdigest()
    assert provenance["dataset_sha256"] == hashlib.sha256(paths["dataset"].read_bytes()).hexdigest()
    assert (
        provenance["label_sidecar_sha256"]
        == hashlib.sha256(paths["sidecar"].read_bytes()).hexdigest()
    )
    assert provenance["corpus"]["corpus_sha256"] == "f" * 64
    assert provenance["config"]["top_k"] == 2
    assert provenance["config"]["parent_expansion"] is False
    # No absolute machine path may reach a published artifact.
    for key in ("pool_path", "dataset", "label_sidecar", "label_manifest"):
        assert not Path(provenance[key]).is_absolute(), f"{key} is an absolute path"
        assert ":" not in provenance[key], f"{key} carries a drive letter"


def test_a_path_outside_the_project_is_stored_as_the_stable_placeholder() -> None:
    outside = PROJECT_ROOT.parent / "elsewhere" / "ab_candidates_phase2_C.json"

    assert _stored_path(outside) == "<external>/ab_candidates_phase2_C.json"
    assert _stored_path(PROJECT_ROOT / "reports" / "gr" / "gr0-bucket-baseline.json") == (
        "reports/gr/gr0-bucket-baseline.json"
    )


# ---------------------------------------------------------------------------
# The committed artifact, and the prose over it
# ---------------------------------------------------------------------------


def _committed_report() -> dict[str, Any]:
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_the_committed_aggregate_reconciles_with_the_published_phase_c_numbers() -> None:
    aggregate = _committed_report()["aggregate"]

    assert aggregate["num_cases"] == 100
    assert aggregate["context_precision"] == pytest.approx(PUBLISHED_PHASE_C_PRECISION, abs=5e-5)
    assert aggregate["context_recall"] == pytest.approx(PUBLISHED_PHASE_C_RECALL, abs=5e-5)
    assert _committed_report()["provenance"]["dataset_sha256"] == PUBLISHED_PHASE_C_DATASET_SHA256


def test_the_committed_report_names_every_class_with_its_case_count() -> None:
    report = _committed_report()
    buckets = _buckets_by_class(report)

    assert sorted(buckets) == ["aggregation", "global", "multi_hop", "single_hop"]
    assert sum(row["num_cases"] for row in report["buckets"]) == 100
    for row in report["buckets"]:
        assert isinstance(row["num_cases"], int)
        if row["num_cases"] == 0:
            assert row["context_precision"] is None
    # The labels are agent-assigned and unapproved; the report has to say so.
    assert report["labels"]["evidence_class"] == "agent_labelled"
    assert report["labels"]["approved"] == 0


def _capsule_bucket_rows() -> dict[str, list[str]]:
    """Parse the per-class table out of the capsule."""
    rows: dict[str, list[str]] = {}
    for line in CAPSULE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or set(stripped) <= set("|-: "):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != 7:
            continue
        name = cells[0].strip("*` ")
        if name in {"aggregation", "global", "multi_hop", "single_hop", "all cases"}:
            rows[name] = cells
    return rows


def test_the_capsule_quotes_the_numbers_that_are_in_the_committed_report() -> None:
    report = _committed_report()
    rows = _capsule_bucket_rows()
    buckets = _buckets_by_class(report)

    assert sorted(rows) == ["aggregation", "all cases", "global", "multi_hop", "single_hop"]

    expected = {name: row for name, row in buckets.items()}
    expected["all cases"] = report["aggregate"] | {"question_class": "all cases"}

    for name, cells in rows.items():
        row = expected[name]
        assert cells[1] == str(row["num_cases"]), f"{name}: case count differs"
        for index, key in ((2, "context_precision"), (3, "context_recall")):
            value = row[key]
            if value is None:
                assert cells[index] in {"—", "-", "n/a"}, f"{name}: {key} should be blank"
            else:
                assert cells[index] == f"{value:.4f}", f"{name}: {key} differs"
        for index, key in ((4, "FULL"), (5, "PART"), (6, "MISS")):
            assert cells[index] == str(row[key]), f"{name}: {key} differs"


def _capsule_prose_lines() -> list[str]:
    """Every capsule line that is not a markdown table row, minus code spans.

    The table rows are already pinned cell-by-cell by
    ``_capsule_bucket_rows``; what is left is the narrative, which is where a
    number can drift away from the artifact without any test noticing.

    Inline code spans are stripped because a backticked literal names a token
    rather than quoting a measurement — the capsule says a zero-case class
    reports ``null``, "never ``0.0000``", and that sentence is true precisely
    because ``0.0000`` is not in the report.
    """
    return [
        re.sub(r"`[^`]*`", "", line)
        for line in CAPSULE.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("|")
    ]


def _reported_metric_values(report: dict[str, Any]) -> list[float]:
    """Every per-class and aggregate metric value the report actually carries."""
    values: list[float] = []
    for row in (*report["buckets"], report["aggregate"]):
        for key in ("context_precision", "context_recall"):
            value = row[key]
            if value is not None:
                values.append(float(value))
    return values


# A decimal rendering of a 0-1 metric in running prose: one leading digit, one
# to four decimals. The lookbehind keeps identifiers out — ``GR-0.3`` and
# ``GR-0.2`` are stream names, not measurements — and the lookahead stops the
# pattern from biting a prefix off a longer number such as a version string.
_PROSE_METRIC_RE = re.compile(r"(?<![\w.-])\d\.\d{1,4}(?![\d.])")


def _is_prefix_rounding_of_a_reported_metric(token: str, values: list[float]) -> bool:
    """True when ``token`` is some reported value rendered at its own precision.

    ``0.5401``, ``0.540`` and ``0.54`` are all honest renderings of a metric of
    0.5401; ``0.64`` is not a rendering of anything in the report and must
    fail however few decimals it is written to.
    """
    decimals = len(token.split(".", 1)[1])
    return any(f"{value:.{decimals}f}" == token for value in values)


def _unreported_prose_tokens(lines: list[str], values: list[float]) -> list[str]:
    """Prose decimals that no reported metric renders to, at their precision."""
    return [
        token
        for line in lines
        for token in _PROSE_METRIC_RE.findall(line)
        if not _is_prefix_rounding_of_a_reported_metric(token, values)
    ]


def test_the_capsule_prose_quotes_only_numbers_that_are_in_the_report() -> None:
    """The narrative, not just the table, is pinned to the committed JSON.

    ``_capsule_bucket_rows`` covers the one 7-cell table. The capsule also
    quotes metrics in running text ("single_hop at 0.5063 and the aggregate at
    0.5067", "recall 0.5000", "context precision **0.5067**"), and an edit to
    any of those used to pass the whole suite.

    Every decimal rendering of a metric in the prose — not only the canonical
    four-decimal one — must be a prefix-rounding of a value that is actually in
    ``reports/gr/gr0-bucket-baseline.json``. Pinning only ``\\d\\.\\d{4}``
    left a hole: a prose quote shortened to "0.64 over one" named a value no
    row carries and still passed, because the table cell beside it was left
    intact. Any decimal in the narrative is a claim about a measured value, so
    any decimal is checked.
    """
    report = _committed_report()
    values = _reported_metric_values(report)
    allowed = sorted({f"{value:.4f}" for value in values})

    lines = _capsule_prose_lines()
    unreported = _unreported_prose_tokens(lines, values)
    assert not unreported, (
        f"docs/evidence/gr0-bucket-baseline.md quotes {unreported} in its prose, "
        f"which is not a metric in reports/gr/gr0-bucket-baseline.json "
        f"(the report's values are {allowed}). Do not edit a number "
        f"in the capsule without re-running the report."
    )
    quoted = [token for line in lines for token in _PROSE_METRIC_RE.findall(line)]

    # A capsule rewrite that moved every number into the table or into an image
    # would otherwise disable this check silently.
    assert len(quoted) >= 4, (
        "docs/evidence/gr0-bucket-baseline.md no longer quotes any metric in its "
        f"prose (found {len(quoted)}); the narrative is then unpinned and this "
        "test would pass vacuously."
    )
    # The two numbers the reconciliation paragraph exists to state.
    aggregate = report["aggregate"]
    for key in ("context_precision", "context_recall"):
        rendered = f"{aggregate[key]:.4f}"
        assert rendered in quoted, (
            f"docs/evidence/gr0-bucket-baseline.md prose no longer states the "
            f"aggregate {key} {rendered} from reports/gr/gr0-bucket-baseline.json"
        )


def test_a_wrong_prose_quote_fails_however_few_decimals_it_is_written_to() -> None:
    """The reproduction of the hole the four-decimal-only scan left open.

    The prose says "0.5401 over one". Rewriting that to the wrong value "0.64
    over one" used to pass every check, because "0.64" is not four decimals and
    the table cell beside it stayed correct. The mutation happens on an
    in-memory copy of the capsule; nothing on disk is touched.
    """
    values = _reported_metric_values(_committed_report())
    lines = _capsule_prose_lines()
    assert any("0.5401 over one" in line for line in lines), (
        "this test mutates the multi_hop prose quote; the capsule no longer "
        "carries it, so re-anchor the mutation before trusting the result"
    )

    wrong = [line.replace("0.5401 over one", "0.64 over one") for line in lines]
    assert _unreported_prose_tokens(wrong, values) == ["0.64"]

    # A shortened but honest rendering of the same metric is still accepted:
    # the rule is prefix-rounding, not a fixed number of decimals.
    for shortened in ("0.540 over one", "0.54 over one", "0.5 over one"):
        rounded = [line.replace("0.5401 over one", shortened) for line in lines]
        assert _unreported_prose_tokens(rounded, values) == [], shortened

    # Stream identifiers are not measurements and stay out of scope, so the
    # broadened scan cannot be satisfied by deleting "GR-0.3" from the prose.
    assert _PROSE_METRIC_RE.findall("the finding of GR-0.3 follows GR-0.2's ask") == []


def test_the_capsule_prose_quotes_the_aggregate_keyword_counts() -> None:
    """The FULL / PART / MISS triple in the prose is the aggregate's own."""
    aggregate = _committed_report()["aggregate"]
    prose = "\n".join(_capsule_prose_lines())
    triple = f"{aggregate['FULL']} / {aggregate['PART']} / {aggregate['MISS']}"

    assert triple in prose, (
        f"docs/evidence/gr0-bucket-baseline.md prose must quote the aggregate "
        f"FULL / PART / MISS triple {triple} from "
        f"reports/gr/gr0-bucket-baseline.json"
    )


def test_the_capsule_carries_the_provenance_digests_of_the_report() -> None:
    report = _committed_report()
    capsule = CAPSULE.read_text(encoding="utf-8")
    provenance = report["provenance"]

    for digest in (
        provenance["pool_sha256"],
        provenance["dataset_sha256"],
        provenance["label_sidecar_sha256"],
        provenance["corpus"]["corpus_sha256"],
        provenance["code"]["commit"],
    ):
        assert digest in capsule, f"capsule does not quote {digest}"


def test_the_capsule_says_the_case_set_cannot_discriminate_the_buckets() -> None:
    report = _committed_report()
    capsule = CAPSULE.read_text(encoding="utf-8")
    buckets = _buckets_by_class(report)

    # 99 of 100 in one bucket: the capsule must state that, not imply a
    # comparison the case set cannot support.
    assert buckets["single_hop"]["num_cases"] == 99
    assert "agent_labelled" in capsule
    assert "0 approved" in capsule
    assert re.search(r"99 of (the )?100", capsule), "capsule must name the 99/100 skew"
    assert "cannot" in capsule


def test_the_capsule_claims_no_retrieval_improvement() -> None:
    capsule = CAPSULE.read_text(encoding="utf-8").lower()

    for forbidden in ("improves retrieval", "retrieval improvement", "precision gain"):
        assert forbidden not in capsule

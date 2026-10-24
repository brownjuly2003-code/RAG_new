"""ADR 0009: exercise the real advisory-scoped gate with offline reports."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs-site/scripts/check-npm-audit.mjs"
REGISTER = ROOT / "docs-site/npm-audit-exceptions.json"
TODAY = "2026-10-03"
ADVISORY = "GHSA-ch52-4w7c-c8xp"
SECOND_ADVISORY = "GHSA-aaaa-bbbb-cccc"
PACKAGE = "http-cache-semantics"


def _exception() -> dict[str, str]:
    """Supply a valid exception at the 31-day expiry boundary."""
    return {
        "advisory": ADVISORY,
        "package": PACKAGE,
        "vulnerable_range": "<=4.2.0",
        "max_severity": "high",
        "reason": "No fixed release exists for this advisory.",
        "unfreeze": "Upgrade and remove when a fixed release exists.",
        "owner": "repository owner",
        "added": TODAY,
        "expires": "2026-11-03",
    }


def _advisory(
    advisory: str = ADVISORY, package: str = PACKAGE, severity: str = "high"
) -> dict[str, Any]:
    """Model a root advisory as npm's object-valued via item."""
    return {
        "source": 123456,
        "name": package,
        "url": f"https://github.com/advisories/{advisory}",
        "severity": severity,
        "range": "<=4.2.0",
    }


def _report() -> dict[str, Any]:
    """Model three packages deriving their high severity from one root."""
    return {
        "auditReportVersion": 2,
        "vulnerabilities": {
            PACKAGE: {"severity": "high", "via": [_advisory()]},
            "astro": {"severity": "high", "via": [PACKAGE]},
            "@astrojs/mdx": {"severity": "high", "via": ["astro"]},
            "@astrojs/starlight": {"severity": "high", "via": ["@astrojs/mdx", "astro"]},
        },
    }


def _run(
    tmp_path: Path,
    report: dict[str, Any],
    exceptions: list[dict[str, str]],
    today: str = TODAY,
    register: dict[str, Any] | None = None,
    extra_args: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    """Run Node with local JSON inputs and an explicit deterministic date."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available")
    report_path = tmp_path / "report.json"
    register_path = tmp_path / "register.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    register_path.write_text(
        json.dumps(
            register if register is not None else {"schema_version": 2, "exceptions": exceptions}
        ),
        encoding="utf-8",
    )
    return subprocess.run(
        [
            node,
            str(SCRIPT),
            "--report",
            str(report_path),
            "--exceptions",
            str(register_path),
            "--today",
            today,
            *extra_args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )


def _assert_pass(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    """A valid audit succeeds and reports no uncovered or stale entries."""
    assert result.returncode == 0, result.stderr
    assert result.stderr.startswith("DEP-01 PASS:")
    output = json.loads(result.stdout)
    assert output["summary"]["uncovered_count"] == 0
    assert output["summary"]["stale_count"] == 0
    return output


def _assert_fail(result: subprocess.CompletedProcess[str], reason: str) -> None:
    """Rejections exit one and expose the specific DEP-01 failure reason."""
    assert result.returncode == 1, result.stderr
    assert result.stderr.startswith("DEP-01 FAIL:")
    assert reason in result.stderr


def test_clean_report_with_empty_register_passes(tmp_path: Path) -> None:
    """A clean audit needs no exception and must not be falsely rejected."""
    _assert_pass(_run(tmp_path, {"auditReportVersion": 2, "vulnerabilities": {}}, []))


def test_info_advisory_with_empty_register_passes(tmp_path: Path) -> None:
    """Informational root advisories require no exception."""
    report = {
        "auditReportVersion": 2,
        "vulnerabilities": {PACKAGE: {"severity": "info", "via": [_advisory(severity="info")]}},
    }
    _assert_pass(_run(tmp_path, report, []))


def test_matching_exception_covers_transitive_packages(tmp_path: Path) -> None:
    """One exact advisory exception also covers all three derived packages."""
    exception = _exception()
    result = _run(tmp_path, _report(), [exception])
    output = _assert_pass(result)
    assert f"{ADVISORY} in {PACKAGE} until {exception['expires']}" in result.stderr
    derived = {item["package"] for item in output["covered"] if item["advisory"] is None}
    assert derived == {"astro", "@astrojs/mdx", "@astrojs/starlight"}
    assert output["summary"]["covered_count"] == 4


def test_committed_register_covers_report_on_added_date(tmp_path: Path) -> None:
    """Each committed exception accepts its root and derivations on its added date.

    The register is empty since 2026-10-24, when the lock moved to http-cache-semantics 4.3.0
    (ADR 0009's review log); an entry added later is run here in the synthetic report's shape.
    """
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    for exception in register["exceptions"]:
        report = _report()
        root = report["vulnerabilities"][PACKAGE]["via"][0]
        root.update(
            url=f"https://github.com/advisories/{exception['advisory']}",
            name=exception["package"],
            range=exception["vulnerable_range"],
        )
        _assert_pass(_run(tmp_path, report, [], today=exception["added"], register=register))


def test_unexcepted_advisory_fails(tmp_path: Path) -> None:
    """A high root and its derivations fail without an exception."""
    _assert_fail(_run(tmp_path, _report(), []), f"no exception for advisory {ADVISORY}")


def test_second_advisory_in_same_package_fails(tmp_path: Path) -> None:
    """An exception covers one advisory rather than every advisory of its package."""
    report = _report()
    report["vulnerabilities"][PACKAGE]["via"].append(_advisory(SECOND_ADVISORY))
    _assert_fail(
        _run(tmp_path, report, [_exception()]),
        f"no exception for advisory {SECOND_ADVISORY} in {PACKAGE}",
    )


def test_derived_package_own_advisory_fails(tmp_path: Path) -> None:
    """Astro's own root remains uncovered even when its dependency is excepted."""
    report = _report()
    report["vulnerabilities"]["astro"]["via"].append(_advisory(SECOND_ADVISORY, "astro"))
    _assert_fail(
        _run(tmp_path, report, [_exception()]),
        f"no exception for advisory {SECOND_ADVISORY} in astro",
    )


def test_changed_vulnerable_range_fails(tmp_path: Path) -> None:
    """An advisory range must exactly match the dated exception's range."""
    report = _report()
    report["vulnerabilities"][PACKAGE]["via"][0]["range"] = "<4.2.0"
    _assert_fail(_run(tmp_path, report, [_exception()]), "vulnerable_range mismatch")


def test_expired_exception_fails(tmp_path: Path) -> None:
    """An exception fails on the first day after its expiry."""
    exception = _exception()
    today = (date.fromisoformat(exception["expires"]) + timedelta(days=1)).isoformat()
    _assert_fail(
        _run(tmp_path, _report(), [exception], today=today),
        f"exception expired on {exception['expires']} (today is {today})",
    )


def test_critical_advisory_cannot_be_excepted(tmp_path: Path) -> None:
    """Critical advisories fail even with an otherwise matching exception."""
    report = _report()
    report["vulnerabilities"][PACKAGE]["severity"] = "critical"
    report["vulnerabilities"][PACKAGE]["via"][0]["severity"] = "critical"
    _assert_fail(_run(tmp_path, report, [_exception()]), "critical severity is never excepted")


def test_exception_for_another_package_fails(tmp_path: Path) -> None:
    """An advisory id cannot transfer an exception to a different package."""
    exception = _exception()
    exception["package"] = "another-package"
    _assert_fail(
        _run(tmp_path, _report(), [exception]),
        f'names package "another-package" but the advisory is against "{PACKAGE}"',
    )


def test_severity_above_exception_maximum_fails(tmp_path: Path) -> None:
    """A high advisory fails when the exception allows only moderate severity."""
    exception = _exception()
    exception["max_severity"] = "moderate"
    _assert_fail(
        _run(tmp_path, _report(), [exception]),
        'advisory severity "high" is above exception max_severity "moderate"',
    )


def test_clean_report_with_stale_exception_fails(tmp_path: Path) -> None:
    """A clean audit requires removing exceptions for absent root advisories."""
    _assert_fail(
        _run(tmp_path, {"auditReportVersion": 2, "vulnerabilities": {}}, [_exception()]),
        f"advisory {ADVISORY} is not among this report's root advisories",
    )


def test_missing_via_package_fails(tmp_path: Path) -> None:
    """A missing report entry cannot explain a derived package's vulnerability."""
    report = _report()
    report["vulnerabilities"]["astro"]["via"].append("missing-package")
    _assert_fail(
        _run(tmp_path, report, [_exception()]),
        "via names package(s) with no entry in the report: missing-package",
    )


def test_empty_via_fails(tmp_path: Path) -> None:
    """A flagged entry with no via items fails closed."""
    report = _report()
    report["vulnerabilities"]["astro"]["via"] = []
    _assert_fail(_run(tmp_path, report, [_exception()]), "entry has no via items")


@pytest.mark.parametrize(
    ("defect", "reason"),
    [
        ("old-schema", "unsupported schema_version=1 (expected 2)"),
        ("missing-unfreeze", 'field "unfreeze" must be a non-empty string'),
        ("expiry-too-far", "32 days after 2026-10-03; at most 31 days is allowed"),
        ("duplicate-advisory", f'duplicate advisory "{ADVISORY}"'),
        ("invalid-id", 'field "advisory" must match ^GHSA(-[0-9a-z]{4}){3}$'),
        ("short-reason", 'field "reason" must be at least 20 characters'),
    ],
)
def test_malformed_register_fails(tmp_path: Path, defect: str, reason: str) -> None:
    """Each malformed register is rejected with its own validation reason."""
    exception = _exception()
    register: dict[str, Any] = {"schema_version": 2, "exceptions": [exception]}
    if defect == "old-schema":
        register["schema_version"] = 1
    elif defect == "missing-unfreeze":
        del exception["unfreeze"]
    elif defect == "expiry-too-far":
        exception["expires"] = (date.fromisoformat(TODAY) + timedelta(days=32)).isoformat()
    elif defect == "duplicate-advisory":
        register["exceptions"].append(dict(exception, package="another-package"))
    elif defect == "invalid-id":
        exception["advisory"] = "CVE-2026-1234"
    elif defect == "short-reason":
        exception["reason"] = "x" * 19
    _assert_fail(_run(tmp_path, _report(), [], register=register), reason)


@pytest.mark.parametrize(
    ("report", "reason"),
    [
        ({"auditReportVersion": 3, "vulnerabilities": {}}, "auditReportVersion=3 (expected 2)"),
        (
            {"error": {"code": "ENOAUDIT", "summary": "Audit unavailable"}},
            "auditReportVersion=undefined (expected 2); npm said: Audit unavailable",
        ),
        (
            {"message": "request to https://registry.npmjs.org failed", "method": "POST"},
            "auditReportVersion=undefined (expected 2); npm said: request to",
        ),
    ],
    ids=["unsupported-version", "npm-error", "npm-request-failure"],
)
def test_malformed_report_fails(tmp_path: Path, report: dict[str, Any], reason: str) -> None:
    """An unsupported report or npm error document cannot count as a clean audit."""
    _assert_fail(_run(tmp_path, report, []), reason)


@pytest.mark.parametrize(
    ("extra_args", "reason"),
    [(("--unknown",), "unknown argument: --unknown"), (("--today",), "missing value for --today")],
    ids=["unknown-argument", "missing-today-value"],
)
def test_malformed_cli_fails(tmp_path: Path, extra_args: tuple[str, ...], reason: str) -> None:
    """Unknown arguments and missing option values fail before audit execution."""
    _assert_fail(_run(tmp_path, _report(), [], extra_args=extra_args), reason)


@pytest.mark.parametrize("entry", [None, [], "broken", 42])
def test_invalid_vulnerability_entry_fails(tmp_path: Path, entry: Any) -> None:
    """Every vulnerability entry must be an object before coverage is computed."""
    report = {"auditReportVersion": 2, "vulnerabilities": {"broken": entry}}
    _assert_fail(_run(tmp_path, report, []), 'entry "broken" must be an object')


@pytest.mark.parametrize("item", [None, 42, True, [], "", "   "])
def test_invalid_via_item_fails(tmp_path: Path, item: Any) -> None:
    """Invalid via items identify both the package and the failing index."""
    report = {
        "auditReportVersion": 2,
        "vulnerabilities": {"broken": {"severity": "critical", "via": [item, 42]}},
    }
    _assert_fail(_run(tmp_path, report, []), 'entry "broken" via[0] must be')


@pytest.mark.parametrize("severity", ["severe", "constructor", None])
def test_unknown_advisory_severity_fails(tmp_path: Path, severity: Any) -> None:
    """An advisory severity must belong to the known severity vocabulary."""
    report = _report()
    report["vulnerabilities"][PACKAGE]["via"][0]["severity"] = severity
    _assert_fail(_run(tmp_path, report, []), f'entry "{PACKAGE}" via[0] has unknown severity')


def test_direct_high_entry_with_only_info_advisory_fails(tmp_path: Path) -> None:
    """A direct high entry cannot be explained by informational advisories alone."""
    report = {
        "auditReportVersion": 2,
        "vulnerabilities": {"broken": {"severity": "high", "via": [_advisory(severity="info")]}},
    }
    _assert_fail(
        _run(tmp_path, report, []), "no root advisory above info (the report cannot be explained)"
    )


def test_missing_via_keeps_existing_failure(tmp_path: Path) -> None:
    """Missing via retains the same rejection as an empty via array."""
    report = _report()
    del report["vulnerabilities"]["astro"]["via"]
    _assert_fail(_run(tmp_path, report, [_exception()]), "entry has no via items")


@pytest.mark.parametrize("via", [None, "http-cache-semantics", {"severity": "critical"}, 42])
def test_via_that_is_not_an_array_fails(tmp_path: Path, via: Any) -> None:
    """A via of the wrong type fails even under an info entry, which is otherwise ignored."""
    report = {
        "auditReportVersion": 2,
        "vulnerabilities": {"broken": {"severity": "info", "via": via}},
    }
    _assert_fail(_run(tmp_path, report, []), 'entry "broken" via must be an array')


def test_inherited_package_name_is_not_a_report_entry(tmp_path: Path) -> None:
    """Prototype properties cannot satisfy a via reference to an absent package."""
    report = _report()
    report["vulnerabilities"]["astro"]["via"].append("constructor")
    _assert_fail(
        _run(tmp_path, report, [_exception()]),
        "via names package(s) with no entry in the report: constructor",
    )


def test_inherited_cli_name_is_unknown(tmp_path: Path) -> None:
    """Prototype properties cannot act as command-line flags."""
    _assert_fail(
        _run(tmp_path, _report(), [], extra_args=("constructor",)), "unknown argument: constructor"
    )


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("range", "<4.2.0", "vulnerable_range mismatch"),
        ("severity", "critical", "critical severity is never excepted"),
    ],
)
def test_distinct_same_id_roots_are_checked(
    tmp_path: Path, field: str, value: str, reason: str
) -> None:
    """Range and severity distinguish roots sharing an advisory id and package."""
    report = _report()
    second = _advisory()
    second[field] = value
    report["vulnerabilities"][PACKAGE]["via"].append(second)
    result = _run(tmp_path, report, [_exception()])
    _assert_fail(result, reason)
    output = json.loads(result.stdout)
    assert len([item for item in output["uncovered"] if item["advisory"] == ADVISORY]) == 1


def test_identical_root_objects_collapse(tmp_path: Path) -> None:
    """Identical advisory objects do not increase the number of covered roots."""
    report = _report()
    report["vulnerabilities"][PACKAGE]["via"].append(_advisory())
    output = _assert_pass(_run(tmp_path, report, [_exception()]))
    assert output["summary"]["covered_count"] == 4


@pytest.mark.parametrize("field", ["added", "expires", "--today"])
@pytest.mark.parametrize("value", ["2026-02-31", "2026-13-01"])
def test_nonexistent_calendar_date_fails(tmp_path: Path, field: str, value: str) -> None:
    """All three date inputs must exist in the calendar rather than normalize."""
    exception = _exception()
    today = "2026-02-28"
    if field == "--today":
        today = value
    else:
        exception[field] = value
    result = _run(tmp_path, _report(), [exception], today=today)
    _assert_fail(result, field)
    _assert_fail(result, value)
    _assert_fail(result, "must be an existing calendar date")


def test_added_after_expiry_fails(tmp_path: Path) -> None:
    """The exception's addition date cannot follow its expiry date."""
    exception = _exception()
    exception["added"] = "2026-12-01"
    _assert_fail(
        _run(tmp_path, _report(), [exception]), 'field "added" must not be after "expires"'
    )


def test_added_after_today_before_expiry_passes(tmp_path: Path) -> None:
    """A timezone-ahead addition date remains valid before the expiry date."""
    exception = _exception()
    exception["added"] = "2026-10-04"
    _assert_pass(_run(tmp_path, _report(), [exception]))


@pytest.mark.parametrize(
    "field",
    [
        "advisory",
        "package",
        "vulnerable_range",
        "reason",
        "unfreeze",
        "owner",
        "added",
        "expires",
        "max_severity",
    ],
)
def test_whitespace_only_required_field_fails(tmp_path: Path, field: str) -> None:
    """Each mandatory exception string must contain non-whitespace characters."""
    exception = _exception()
    exception[field] = "   "
    _assert_fail(
        _run(tmp_path, _report(), [exception]), f'field "{field}" must be a non-empty string'
    )

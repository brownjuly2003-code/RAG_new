"""Guard the pip-audit floors (six raised on 2026-10-03, three on 2026-10-15, six on
2026-10-25, one on 2026-10-28, two on 2026-11-02) and the caps below major lines nothing here has run on."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.version import Version

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCK_NAMES = ("requirements.lock", "requirements-dev.lock")

# Advisory ranges retain the shorthand used by requirements.txt.
FIXED_IN = {
    "pypdf": (
        Version("6.21.4"),
        (
            "CVE-2026-119203..119209",
            "113786",
            "113789..113795",
            "115585",
            "PYSEC-2026-4153..4160",
        ),
    ),
    "urllib3": (Version("2.8.0"), ("PYSEC-2026-4175/4176/4177",)),
    "pyjwt": (Version("2.15.0"), ("PYSEC-2026-4140..4152",)),
    "sentence-transformers": (Version("5.6.0"), ("PYSEC-2026-4164",)),
    "anyio": (Version("4.14.2"), ("PYSEC-2026-4024/4025",)),
    "oauthlib": (Version("4.0.0"), ("PYSEC-2026-4114",)),
    "fsspec": (Version("2026.6.0"), ("CVE-2026-104851",)),
    "langgraph-sdk": (Version("0.4.4"), ("CVE-2026-104873",)),
    "multidict": (Version("6.9.1"), ("CVE-2026-104874",)),
    "aiohttp": (
        Version("3.14.4"),
        ("CVE-2026-111063..111066", "CVE-2026-111748..111750", "GHSA-2g87-pp6c-29x5"),
    ),
    "setuptools": (Version("84.1.0"), ("GHSA-xmj3-9gf7-h52w",)),
    "certifi": (Version("2026.10.19"), ("PYSEC-2026-4320",)),
    "filelock": (Version("4.2.1"), ("CVE-2026-112907", "112913", "112940")),
    "opentelemetry-api": (Version("1.45.1"), ("CVE-2026-114603",)),
    "authlib": (Version("1.9.1"), ("CVE-2026-96760", "CVE-2026-114614..114618", "114620")),
    "joserfc": (Version("1.7.6"), ("CVE-2026-119283", "119284")),
}
# Major lines kept out of the locks; requirements.txt says why beside each cap.
CAPS = {"sentence-transformers": Version("6"), "multidict": Version("7")}


def _assert_declared_floor(text: str, name: str) -> Requirement:
    match = re.search(
        rf"^{re.escape(name)}(?=[<>=!~])[^\n#]+", text, flags=re.MULTILINE | re.IGNORECASE
    )
    assert match is not None, f"requirements.txt lost the {name} floor"
    requirement = Requirement(match.group(0).strip())
    floors = [Version(spec.version) for spec in requirement.specifier if spec.operator == ">="]
    assert floors, f"requirements.txt lost the {name} >= floor"
    fixed_in = FIXED_IN[name][0]
    assert max(floors) >= fixed_in, (
        f"requirements.txt declares {name} floor {max(floors)}, below the fix {fixed_in}"
    )
    return requirement


def _assert_locked_floor(text: str, name: str, source: str) -> Version:
    match = re.search(
        rf"^{re.escape(name)}==([^\s]+?)(?:[ \t]+\\)?[ \t]*$",
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    assert match is not None, f"{source} does not pin {name}"
    version = Version(match.group(1))
    fixed_in = FIXED_IN[name][0]
    assert version >= fixed_in, f"{source} pins {name} {version}, below the fix {fixed_in}"
    return version


def _assert_cap(text: str, source: str, name: str) -> None:
    """Keep both the declared range and the resolved pins below the unevaluated line."""
    ceiling = CAPS[name]
    message = f"{source}: keep {name} below {ceiling}; see the comment in requirements.txt"
    if source == "requirements.txt":
        requirement = _assert_declared_floor(text, name)
        assert any(
            (spec.operator == "<" and Version(spec.version) <= ceiling)
            or (spec.operator == "<=" and Version(spec.version) < ceiling)
            for spec in requirement.specifier
        ), message
    else:
        assert _assert_locked_floor(text, name, source) < ceiling, message


@pytest.mark.parametrize("name", FIXED_IN)
def test_requirements_declares_each_fix_and_its_advisories(name: str) -> None:
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")
    _assert_declared_floor(requirements, name)
    for advisory in FIXED_IN[name][1]:
        assert advisory in requirements, f"requirements.txt lost {name} advisory {advisory}"


@pytest.mark.parametrize("source", LOCK_NAMES)
@pytest.mark.parametrize("name", FIXED_IN)
def test_both_locks_pin_each_package_at_or_above_its_fix(name: str, source: str) -> None:
    _assert_locked_floor((PROJECT_ROOT / source).read_text(encoding="utf-8"), name, source)


@pytest.mark.parametrize("source", ("requirements.txt", *LOCK_NAMES))
@pytest.mark.parametrize("name", CAPS)
def test_capped_packages_stay_below_their_unevaluated_line(name: str, source: str) -> None:
    _assert_cap((PROJECT_ROOT / source).read_text(encoding="utf-8"), source, name)


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("pyjwt", "PyJWT>=2.15.0\n"),
        ("pyjwt", "PYJWT>=2.16.0\n"),
        ("sentence-transformers", "sentence-transformers>=5.6.0,<6\n"),
        ("sentence-transformers", "Sentence-Transformers>=5.7.0,<6\n"),
        ("anyio", "anyio>=4.15.1\n"),
    ],
)
def test_declared_floor_accepts_valid_reference_lines(name: str, text: str) -> None:
    _assert_declared_floor(text, name)


@pytest.mark.parametrize("name", FIXED_IN)
@pytest.mark.parametrize("text", ["", "{name}>=0.1.0\n"])
def test_declared_floor_rejects_missing_or_below_fix_lines(name: str, text: str) -> None:
    with pytest.raises(AssertionError, match=rf"{name}.*(?:floor|below)"):
        _assert_declared_floor(text.format(name=name), name)


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("pyjwt", "PyJWT==2.15.0\n"),
        ("pyjwt", "PYJWT==2.16.0 \\\n    --hash=sha256:abc \\\n    --hash=sha256:def\n"),
        ("sentence-transformers", "sentence-transformers==5.7.0 \\\n    --hash=sha256:abc\n"),
        ("anyio", "anyio==4.15.1\n"),
    ],
)
def test_locked_floor_accepts_valid_reference_lines(name: str, text: str) -> None:
    _assert_locked_floor(text, name, "synthetic.lock")


@pytest.mark.parametrize("name", FIXED_IN)
@pytest.mark.parametrize("text", ["", "{name}==0.1.0 \\\n    --hash=sha256:abc\n"])
def test_locked_floor_rejects_missing_or_below_fix_lines(name: str, text: str) -> None:
    with pytest.raises(AssertionError, match=rf"(?:does not pin {name}|{name}.*below)"):
        _assert_locked_floor(text.format(name=name), name, "synthetic.lock")


@pytest.mark.parametrize(
    ("name", "source", "text"),
    [
        ("sentence-transformers", "requirements.txt", "Sentence-Transformers>=5.7.0,<6\n"),
        (
            "sentence-transformers",
            "requirements.lock",
            "Sentence-Transformers==5.7.0 \\\n    --hash=sha256:abc\n",
        ),
        ("sentence-transformers", "requirements-dev.lock", "sentence-transformers==5.8.0\n"),
        ("multidict", "requirements.txt", "multidict>=6.9.1,<7\n"),
        ("multidict", "requirements.lock", "multidict==6.9.1 \\\n    --hash=sha256:abc\n"),
    ],
)
def test_cap_accepts_valid_reference_lines(name: str, source: str, text: str) -> None:
    _assert_cap(text, source, name)


@pytest.mark.parametrize(
    ("name", "source", "text"),
    [
        ("sentence-transformers", "requirements.txt", "sentence-transformers>=5.6.0\n"),
        ("sentence-transformers", "requirements.txt", "sentence-transformers>=5.6.0,<=6\n"),
        ("sentence-transformers", "requirements.txt", "sentence-transformers>=5.6.0,<7\n"),
        ("sentence-transformers", "requirements.lock", "sentence-transformers==6.0.0\n"),
        ("sentence-transformers", "requirements-dev.lock", "sentence-transformers==6.1.0\n"),
        ("multidict", "requirements.txt", "multidict>=6.9.1\n"),
        ("multidict", "requirements.lock", "multidict==7.1.0\n"),
    ],
)
def test_cap_rejects_the_unevaluated_line(name: str, source: str, text: str) -> None:
    with pytest.raises(AssertionError, match=r"comment in requirements\.txt"):
        _assert_cap(text, source, name)

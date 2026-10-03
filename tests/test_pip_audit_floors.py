"""Guard the six pip-audit floors raised on 2026-10-03 and the unevaluated 6.x cap."""

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
    "pypdf": (Version("6.19.0"), ("PYSEC-2026-4153..4160",)),
    "urllib3": (Version("2.8.0"), ("PYSEC-2026-4175/4176/4177",)),
    "pyjwt": (Version("2.15.0"), ("PYSEC-2026-4140..4152",)),
    "sentence-transformers": (Version("5.6.0"), ("PYSEC-2026-4164",)),
    "anyio": (Version("4.14.2"), ("PYSEC-2026-4024/4025",)),
    "oauthlib": (Version("4.0.0"), ("PYSEC-2026-4114",)),
}


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


def _assert_sentence_transformers_cap(text: str, source: str) -> None:
    """Keep both the declared range and the resolved pins below the unevaluated line."""
    name = "sentence-transformers"
    ceiling = Version("6")
    message = f"{source}: keep {name} below 6; see the comment in requirements.txt"
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
def test_sentence_transformers_stays_below_the_unevaluated_6_line(source: str) -> None:
    _assert_sentence_transformers_cap((PROJECT_ROOT / source).read_text(encoding="utf-8"), source)


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
    ("source", "text"),
    [
        ("requirements.txt", "Sentence-Transformers>=5.7.0,<6\n"),
        ("requirements.lock", "Sentence-Transformers==5.7.0 \\\n    --hash=sha256:abc\n"),
        ("requirements-dev.lock", "sentence-transformers==5.8.0\n"),
    ],
)
def test_sentence_transformers_cap_accepts_valid_reference_lines(source: str, text: str) -> None:
    _assert_sentence_transformers_cap(text, source)


@pytest.mark.parametrize(
    ("source", "text"),
    [
        ("requirements.txt", "sentence-transformers>=5.6.0\n"),
        ("requirements.txt", "sentence-transformers>=5.6.0,<=6\n"),
        ("requirements.txt", "sentence-transformers>=5.6.0,<7\n"),
        ("requirements.lock", "sentence-transformers==6.0.0\n"),
        ("requirements-dev.lock", "sentence-transformers==6.1.0\n"),
    ],
)
def test_sentence_transformers_cap_rejects_the_6_line(source: str, text: str) -> None:
    with pytest.raises(AssertionError, match=r"comment in requirements\.txt"):
        _assert_sentence_transformers_cap(text, source)

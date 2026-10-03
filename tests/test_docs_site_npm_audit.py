"""Plan DEP-01 / ADR 0009: advisory-scoped schema-2 exceptions and npm audit posture.

**What this file owns:** the exception register's schema and staleness, the
audit script and npm-script wiring, and the manifest shape the Astro 7 upgrade
requires of packages that carry no advisory (`@astrojs/starlight`,
`@astrojs/markdown-remark`), plus the presence of a committed lock.

Version constraints raised by T-18 and T-74 — `astro`, `dompurify`,
`fast-uri`, `js-yaml`, `sharp`, `svgo` — live in
`tests/test_npm_audit_floors.py` and only there, including their pin format.
This file used to carry private copies (`astro` had to start with `^7.`,
`sharp` with `^0.35`); the `astro` copy went stale the moment the security fix
demanded an exact pin, so those assertions moved to their single owner rather
than being patched here.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_SITE = PROJECT_ROOT / "docs-site"
EXCEPTIONS = DOCS_SITE / "npm-audit-exceptions.json"
CHECK_SCRIPT = DOCS_SITE / "scripts" / "check-npm-audit.mjs"
PACKAGE_JSON = DOCS_SITE / "package.json"

# Reachability notes that only papered over Astro 6 residual moderates/lows.
# After the Astro 7 upgrade these packages must not keep stale exceptions.
# `astro` itself is not listed here: test_npm_audit_floors.py already forbids
# an exception for every package with a fixed release, `astro` included.
ASTRO6_RESIDUAL_EXCEPTION_PACKAGES = frozenset(
    {
        "@astrojs/mdx",
        "@astrojs/starlight",
        "astro-expressive-code",
        "esbuild",
    }
)


def _caret_version(spec: str) -> tuple[int, int, int]:
    """Parse leading major.minor.patch from a caret/range npm version specifier."""
    match = re.match(r"^\^?(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(spec).strip())
    assert match, f"unparseable version spec: {spec!r}"
    major, minor, patch = match.groups()
    return int(major), int(minor or 0), int(patch or 0)


def test_npm_audit_exceptions_register_is_valid() -> None:
    """Schema 2 exceptions are unique by advisory and expire within 31 days."""
    raw = json.loads(EXCEPTIONS.read_text(encoding="utf-8"))
    assert raw["schema_version"] == 2
    assert raw.get("updated")
    assert isinstance(raw.get("notes"), str) and raw["notes"].strip()
    exceptions = raw["exceptions"]
    # Empty list is valid after a clean Astro 7 audit; structure still enforced.
    assert isinstance(exceptions, list)

    today = date.today()
    advisories: set[str] = set()
    for entry in exceptions:
        assert isinstance(entry["advisory"], str)
        assert re.fullmatch(r"GHSA(-[0-9a-z]{4}){3}", entry["advisory"])
        assert entry["advisory"] not in advisories
        advisories.add(entry["advisory"])
        for field in ("package", "vulnerable_range", "unfreeze", "owner"):
            assert isinstance(entry.get(field), str) and entry[field].strip()
        assert entry["max_severity"] in {"low", "moderate", "high"}
        assert isinstance(entry["reason"], str) and len(entry["reason"].strip()) >= 20
        for field in ("added", "expires"):
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry[field])
        added = date.fromisoformat(entry["added"])
        expires = date.fromisoformat(entry["expires"])
        assert added <= expires
        assert expires >= today, f"expired exception for {entry['package']}"
        assert expires <= today + timedelta(days=31)
        assert "advisories" not in entry
        assert entry["package"] not in ASTRO6_RESIDUAL_EXCEPTION_PACKAGES, (
            f"stale Astro-6 residual exception for {entry['package']}"
        )


def test_docs_site_audit_script_and_package_script_exist() -> None:
    assert CHECK_SCRIPT.is_file()
    text = CHECK_SCRIPT.read_text(encoding="utf-8")
    assert "DEP-01" in text
    assert "npm-audit-exceptions.json" in text

    pkg = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    assert pkg["scripts"]["audit:deps"] == "node scripts/check-npm-audit.mjs"
    deps = pkg["dependencies"]

    # `astro` and `sharp` are asserted in tests/test_npm_audit_floors.py.
    starlight_ver = _caret_version(deps["@astrojs/starlight"])
    assert starlight_ver[0] == 0 and starlight_ver[1] >= 41, (
        f"@astrojs/starlight must be ^0.41+, got {deps['@astrojs/starlight']!r}"
    )

    # Astro 7 requires direct ownership of @astrojs/markdown-remark when using
    # markdown.rehypePlugins (unified processor is imported from this package).
    md_spec = deps.get("@astrojs/markdown-remark")
    assert md_spec, (
        "direct @astrojs/markdown-remark dependency required for rehypePlugins on Astro 7"
    )
    md_ver = _caret_version(md_spec)
    assert md_ver[0] == 7 and md_ver[1] >= 2, (
        f"@astrojs/markdown-remark must be ^7.2+, got {md_spec!r}"
    )


def test_docs_site_package_lock_present() -> None:
    lock = DOCS_SITE / "package-lock.json"
    assert lock.is_file()
    assert lock.stat().st_size > 10_000

"""Guard: the docs-site npm floors raised by T-18 cannot drift back down.

Advisories against five packages published upstream between 2026-08-25 and
2026-09-07 turned `Deploy docs site (Astro Starlight) to Pages` red without a
single commit in this repository touching `docs-site/package.json` or
`docs-site/package-lock.json` — the audit's only inputs. Three of those packages
were pinned *inside* the newly vulnerable ranges by pins that were correct when
written (`fast-uri: ^3.1.5`, `js-yaml: ^4.1.1`, `sharp: ^0.35.3`), which is the
failure mode this file guards: the next lock
refresh must not be free to resolve back under the fix, and the gate must not
be quieted with an exception when a fixed release exists.

**What this file owns:** every version constraint on the five advisory
packages in `FIXED_IN` — the declared floor, the pin *format* that keeps that
floor from drifting, the versions the lock resolves, and the exception
register's silence about them. `tests/test_docs_site_npm_audit.py` owns the
DEP-01 audit posture (the exception register's schema and staleness, the audit
script wiring, the non-advisory manifest shape). No assertion is stated in both
files; a constraint on a `FIXED_IN` package belongs here.

The advisory ranges are transcribed from `npm audit` on run 34393111514.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path

import pytest
from packaging.version import Version

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_SITE = PROJECT_ROOT / "docs-site"

# package -> first release that clears every advisory against it.
FIXED_IN = {
    "astro": Version("7.2.8"),  # GHSA-26w7-cxv4-gfx2 (critical), GHSA-376h-93r7-7g6f
    "fast-uri": Version("3.1.6"),  # GHSA-5jgf-p345-68v8 + three more
    "js-yaml": Version("4.3.2"),  # GHSA-2883-xcg3-v3hh
    "sharp": Version("0.35.4"),  # GHSA-rgj7-g3m4-5g8c (libheif)
    "svgo": Version("4.1.0"),  # GHSA-w27v-7q3p-w38r, GHSA-4vpr-x523-8j87
}


def _declared_floor(spec: str) -> Version:
    """The lowest version an npm range accepts, for `^x`, `~x`, `>=x` and `x`."""
    match = re.match(r"^[\^~]?(?:>=)?\s*(\d+\.\d+\.\d+)$", spec.strip())
    assert match is not None, f"unhandled npm range {spec!r}"
    return Version(match.group(1))


def _package_json() -> dict:
    return json.loads((DOCS_SITE / "package.json").read_text(encoding="utf-8"))


def _declared_specs(manifest: dict, name: str) -> list[str]:
    """Every spec the manifest declares for `name`, one per source.

    `dependencies` and `overrides` are separate constraints on the same
    package — `sharp` is declared in both today — so they cannot be merged
    into one dict before checking: the second source would shadow the first
    and leave that floor unchecked.
    """
    return [
        source[name]
        for source in (manifest.get("dependencies", {}), manifest.get("overrides", {}))
        if name in source
    ]


def _assert_floors(manifest: dict, fixed_in: Mapping[str, Version]) -> None:
    """Assert `manifest` floors every package in `fixed_in` at or above its fix.

    This is the consuming loop itself, not a fixture: the shadowing guard below
    calls it on a synthetic manifest so that a rewrite back to a merged
    `dependencies | overrides` dict fails there, and not only in the real test.
    """
    for name, fix in fixed_in.items():
        specs = _declared_specs(manifest, name)
        assert specs, (
            f"{name} has neither a dependency nor an override in "
            f"docs-site/package.json; nothing pins it above {fix}"
        )
        for spec in specs:
            assert _declared_floor(spec) >= fix, (
                f"docs-site/package.json allows {name} {spec}, below the fix {fix}"
            )


def _locked_versions() -> dict[str, list[Version]]:
    lock = json.loads((DOCS_SITE / "package-lock.json").read_text(encoding="utf-8"))
    resolved: dict[str, list[Version]] = {}
    for path, entry in lock["packages"].items():
        if "node_modules/" not in path or "version" not in entry:
            continue
        name = path.rsplit("node_modules/", 1)[1]
        if name in FIXED_IN:
            resolved.setdefault(name, []).append(Version(entry["version"]))
    return resolved


def test_package_json_declares_a_floor_at_or_above_every_fix() -> None:
    """A floor in `package.json` is what survives the next `npm install`."""
    _assert_floors(_package_json(), FIXED_IN)


@pytest.mark.parametrize(
    ("dependency", "override"),
    [("^0.35.3", "^0.35.4"), ("^0.35.4", "^0.35.3")],
    ids=["dependency-below-fix", "override-below-fix"],
)
def test_neither_manifest_source_can_shadow_a_below_fix_spec_in_the_other(
    dependency: str, override: str
) -> None:
    """The floor check reads both sources, so neither can hide the other.

    `sharp` is declared as a dependency *and* as an override. Merging the two
    into one dict lets the winning source shadow the losing one, so a spec below
    the fix in the loser would slip through the floor check above — and which
    source loses depends on the merge order, so proving one order leaves the
    other rewrite free. Both are exercised here: the below-fix spec sits in
    `dependencies` in one case and in `overrides` in the other, against
    `_assert_floors` itself — the same code path the real test runs. A rewrite
    to `{**dependencies, **overrides}` stops raising in the first case and one
    to `{**overrides, **dependencies}` in the second, so either fails this
    guard.
    """
    shadowing = {
        "dependencies": {"sharp": dependency},
        "overrides": {"sharp": override},
    }
    with pytest.raises(AssertionError, match=r"allows sharp \^0\.35\.3"):
        _assert_floors(shadowing, {"sharp": FIXED_IN["sharp"]})


def test_astro_is_pinned_exactly_because_the_caret_leaves_the_7_2_line() -> None:
    """`astro` is the one advisory package whose floor cannot be a caret.

    `^7.2.8` resolves to the newest 7.x, and 7.3.x peer-requires
    `@astrojs/markdown-remark ^7.3.0` — which contradicts the 7.2.4 this site
    depends on directly for the `markdown` rehype plugins (`unified()` imported
    from `@astrojs/markdown-remark`). So the fix is carried by
    an exact pin, and this is the single place in the repository that asserts
    the pin format for `astro`.
    """
    spec = _package_json()["dependencies"]["astro"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", spec), (
        f"astro must stay an exact pin, got {spec!r}: a caret resolves into "
        "7.3.x and breaks the @astrojs/markdown-remark peer contract"
    )
    assert Version(spec) < Version("7.3.0"), (
        f"astro {spec} leaves the 7.2 line; moving to 7.3+ means bumping "
        "@astrojs/markdown-remark with it, which is a dependency refresh, not "
        "a security floor"
    )


def test_the_lock_resolves_every_advisory_package_above_its_fix() -> None:
    """`npm ci` installs the lock, not the manifest, so the lock is the gate."""
    resolved = _locked_versions()

    for name, fixed_in in FIXED_IN.items():
        versions = resolved.get(name)
        assert versions, f"docs-site/package-lock.json no longer resolves {name}"
        for version in versions:
            assert version >= fixed_in, (
                f"package-lock.json pins {name} {version}, below the fix {fixed_in}"
            )


def test_sharp_dependency_and_override_agree() -> None:
    """`sharp` is pinned twice; a floor raised in one place only is not a floor."""
    manifest = _package_json()
    dependency = _declared_floor(manifest["dependencies"]["sharp"])
    override = _declared_floor(manifest["overrides"]["sharp"])
    assert dependency == override, (
        f"docs-site/package.json declares sharp>={dependency} as a dependency "
        f"and sharp>={override} as an override"
    )


def test_the_audit_gate_was_not_quieted_instead_of_fixed() -> None:
    """Every one of the five advisories had a fixed release, so none earns an
    exception. CLAUDE.md forbids fixing a gate by relaxing it."""
    registry = json.loads((DOCS_SITE / "npm-audit-exceptions.json").read_text(encoding="utf-8"))
    excepted = {exception.get("package") for exception in registry["exceptions"]}
    quieted = sorted(excepted & set(FIXED_IN))
    assert not quieted, (
        f"npm-audit-exceptions.json excepts {quieted}, which have fixed releases; "
        "raise the floor instead"
    )

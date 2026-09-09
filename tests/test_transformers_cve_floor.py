"""Guard: the CVE-2026-9856 floor on `transformers` cannot be dropped silently.

`transformers` is transitive (via `sentence-transformers`), so without an
explicit floor in `requirements.txt` the next recompile is free to resolve back
below 5.10.0 and re-introduce the finding that turned the `security` and
`pre-commit` jobs red on run 34069248177.
"""

from __future__ import annotations

import re
from pathlib import Path

from packaging.version import Version

PROJECT_ROOT = Path(__file__).resolve().parents[1]

_FIXED_IN = Version("5.10.0")


def test_requirements_declares_the_cve_2026_9856_floor() -> None:
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")

    match = re.search(r"^transformers>=(\S+)$", requirements, flags=re.MULTILINE)
    assert match is not None, "requirements.txt lost the transformers floor"
    assert Version(match.group(1)) >= _FIXED_IN
    assert "CVE-2026-9856" in requirements


def test_current_state_does_not_call_the_cve_unfixed_while_the_locks_carry_it() -> None:
    """The routing doc must not contradict the locks — nor claim CI is green."""
    state = (PROJECT_ROOT / "CURRENT_STATE.md").read_text(encoding="utf-8")

    bullets = [b for b in state.split("\n- ") if "CVE-2026-9856" in b]
    assert len(bullets) == 1, "CURRENT_STATE.md lost its CVE-2026-9856 bullet"
    bullet = bullets[0]

    assert "unfixed" not in bullet, "the locks pin the fix; the bullet says otherwise"
    assert "transformers>=5.10.0" in bullet, "the bullet does not name the floor"
    assert "green" not in bullet.lower(), "no CI run has executed on these commits"


def test_both_locks_pin_transformers_at_or_above_the_fix() -> None:
    for lock_name in ("requirements.lock", "requirements-dev.lock"):
        lock = (PROJECT_ROOT / lock_name).read_text(encoding="utf-8")
        match = re.search(r"^transformers==(\S+?)(?: \\)?$", lock, flags=re.MULTILINE)
        assert match is not None, f"{lock_name} does not pin transformers"
        assert Version(match.group(1)) >= _FIXED_IN, (
            f"{lock_name} pins transformers {match.group(1)}, "
            f"below the CVE-2026-9856 fix {_FIXED_IN}"
        )

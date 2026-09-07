"""The repository root is a routing surface, not a filing cabinet.

Audit 2026-08-24 (FIN-06): the root held 46 markdown files -- 29 of them
per-slice process capsules -- plus a 678 KB, 12 327-line AGENT_STATE.md. A new
session could not tell which file was current, so agents planned from whatever
they happened to open. The fix was structural (capsules to docs/evidence/,
history to archive/), and this test is what keeps it fixed: without a
guard the capsule habit returns one file at a time.
"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# The routing surface. Adding to this set is a deliberate decision, not a
# side effect of finishing a slice.
ALLOWED_ROOT_DOCS = {
    "README.md",
    "CLAUDE.md",
    "CURRENT_STATE.md",
    "ROADMAP.md",
    "EVIDENCE_INDEX.md",
    "BACKLOG.md",
    "DEPRECATIONS.md",
    "AGENT_STATE.md",
    "plan_06_09_26.md",
}

MAX_ROOT_DOCS = 9


def _root_docs() -> set[str]:
    return {path.name for path in PROJECT_ROOT.glob("*.md")}


def test_root_markdown_is_limited_to_the_routing_surface() -> None:
    unexpected = sorted(_root_docs() - ALLOWED_ROOT_DOCS)
    assert not unexpected, (
        f"new markdown in the repository root: {unexpected}. Slice evidence "
        "belongs in docs/evidence/ with a row in EVIDENCE_INDEX.md; history "
        "belongs in archive/."
    )


def test_root_markdown_count_stays_bounded() -> None:
    docs = _root_docs()
    assert len(docs) <= MAX_ROOT_DOCS, f"{len(docs)} root .md files: {sorted(docs)}"


def test_agent_state_stays_a_digest() -> None:
    """AGENT_STATE.md is read by scripts/autopilot.ps1 as planner context.

    It stays at that path so the autopilot wiring keeps working, but it must
    not grow back into an update log -- that is what archive/ is for.
    """
    lines = (PROJECT_ROOT / "AGENT_STATE.md").read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 120, (
        f"AGENT_STATE.md is {len(lines)} lines; it is a digest. Append history "
        "to archive/docs/state/agent-state-2026-03..08.md instead."
    )


def test_current_state_is_short_enough_to_actually_be_read() -> None:
    lines = (PROJECT_ROOT / "CURRENT_STATE.md").read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 150, f"CURRENT_STATE.md is {len(lines)} lines; cap is 150"


def test_the_archived_update_log_survived_the_move() -> None:
    archive = (
        PROJECT_ROOT
        / "archive"
        / "docs"
        / "state"
        / "agent-state-2026-03..08.md"
    )
    assert archive.exists(), "the AGENT_STATE history must remain in archive/docs/state/"
    assert len(archive.read_text(encoding="utf-8").splitlines()) > 1000


def test_superseded_root_surfaces_stay_in_the_archive() -> None:
    assert not (PROJECT_ROOT / "archive-legacy").exists()
    assert not (PROJECT_ROOT / "codex-tasks").exists()
    assert not (PROJECT_ROOT / "plan_sol_23_07_26").exists()
    assert (PROJECT_ROOT / "archive" / "README.md").exists()
    assert (PROJECT_ROOT / "archive" / "legacy-code").is_dir()
    assert (PROJECT_ROOT / "archive" / "tasks").is_dir()


def test_slice_capsules_live_under_docs_evidence() -> None:
    capsules = list((PROJECT_ROOT / "docs" / "evidence").glob("*.md"))
    assert len(capsules) >= 29, (
        f"expected the 29 moved slice capsules under docs/evidence/, found {len(capsules)}"
    )


def test_every_evidence_capsule_is_listed_in_the_index() -> None:
    index = (PROJECT_ROOT / "EVIDENCE_INDEX.md").read_text(encoding="utf-8")
    missing = [
        path.name
        for path in (PROJECT_ROOT / "docs" / "evidence").glob("*.md")
        if path.name not in index
    ]
    assert not missing, f"capsules with no row in EVIDENCE_INDEX.md: {sorted(missing)}"

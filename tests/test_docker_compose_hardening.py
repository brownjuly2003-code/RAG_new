from __future__ import annotations

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_compose() -> dict:
    return yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def test_default_compose_is_labeled_local_dev_only() -> None:
    content = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "Local development only" in content
    assert "not a production deployment manifest" in content


def test_default_compose_binds_published_ports_to_loopback() -> None:
    compose = _load_compose()

    exposed_ports = {
        service_name: port
        for service_name, service in compose["services"].items()
        for port in service.get("ports", [])
    }

    assert exposed_ports
    assert all(str(port).startswith("127.0.0.1:") for port in exposed_ports.values())


def test_default_compose_forces_development_environment() -> None:
    compose = _load_compose()

    assert "RAG_ENV=development" in compose["services"]["app"]["environment"]


def _readme_section(title: str) -> str:
    """Return one top-level README section, bounded by the next `## ` heading.

    The 2026-09-04 restructure renamed `## Quick Start` to `## Quick start` and
    dropped the `## API` heading this test used as the section's lower bound.
    Splitting on a hardcoded next-heading name is what let a rename read as "the
    whole rest of the file", so the bound is now the next heading, whatever it is
    called: a section that loses its content fails here instead of borrowing a
    phrase from a later one.
    """
    lines = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8").splitlines()
    headings = [index for index, line in enumerate(lines) if line.startswith("## ")]
    for position, index in enumerate(headings):
        if lines[index].removeprefix("## ").strip().casefold() == title.casefold():
            end = headings[position + 1] if position + 1 < len(headings) else len(lines)
            return "\n".join(lines[index + 1 : end])
    raise AssertionError(f"README has no `## {title}` section")


def test_readme_quick_start_covers_local_first_onboarding() -> None:
    """README Quick Start must document env bootstrap, local Compose, and no shipped keys."""
    quick_start = _readme_section("Quick start")
    lowered = quick_start.lower()

    assert "cp .env.example .env" in quick_start
    assert "docker compose" in lowered
    assert "docker-compose.yml" in quick_start
    assert "optional provider keys" in lowered
    assert "no api keys ship in this repository" in lowered

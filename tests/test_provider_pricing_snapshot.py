"""Contract test: runtime provider prices must match the pinned snapshot.

Audit 2026-08-24 (FIN-08) found config/providers.yml carrying Mistral prices
that had drifted from the vendor's published rates -- mistral-large overstated
4x, ministral-3b understated 2.5x -- while a cost-per-resolution claim was
computed from them. Nothing failed, because nothing compared the numbers to
anything. This test is that comparison: config/pricing_snapshot.json is the
dated, sourced contract, providers.yml is the runtime copy, and they must
agree exactly.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from config.provider_schema import load_provider_registry

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = PROJECT_ROOT / "config" / "pricing_snapshot.json"


def _snapshot() -> dict:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_every_paid_provider_declares_a_pricing_snapshot_date() -> None:
    registry = load_provider_registry()
    paid = [p for p in registry.providers if p.kind == "paid"]
    assert paid, "registry has no paid providers -- update this test if that is intentional"
    for provider in paid:
        assert provider.pricing_snapshot_date, (
            f"paid provider '{provider.id}' has no pricing_snapshot_date"
        )


def test_every_paid_provider_is_covered_by_the_snapshot_file() -> None:
    registry = load_provider_registry()
    snapshot = _snapshot()["providers"]
    for provider in registry.providers:
        if provider.kind != "paid":
            continue
        assert provider.id in snapshot, (
            f"paid provider '{provider.id}' is missing from {SNAPSHOT_PATH.name}"
        )


def test_registry_prices_match_the_pinned_snapshot() -> None:
    registry = load_provider_registry()
    snapshot = _snapshot()["providers"]

    for provider_id, pinned in snapshot.items():
        provider = next(
            (p for p in registry.providers if p.id == provider_id), None
        )
        assert provider is not None, f"snapshot pins unknown provider '{provider_id}'"
        assert provider.pricing_snapshot_date == pinned["snapshot_date"], (
            f"{provider_id}: providers.yml snapshot date "
            f"{provider.pricing_snapshot_date!r} != pinned {pinned['snapshot_date']!r}"
        )

        runtime = {m.name: m for m in provider.models}
        assert set(runtime) == set(pinned["models"]), (
            f"{provider_id}: model set drifted -- "
            f"runtime {sorted(runtime)} vs pinned {sorted(pinned['models'])}"
        )

        for name, prices in pinned["models"].items():
            model = runtime[name]
            assert model.input_price_per_1m_tokens == pytest.approx(prices["input"]), (
                f"{provider_id}/{name}: input price "
                f"{model.input_price_per_1m_tokens} != pinned {prices['input']}"
            )
            assert model.output_price_per_1m_tokens == pytest.approx(prices["output"]), (
                f"{provider_id}/{name}: output price "
                f"{model.output_price_per_1m_tokens} != pinned {prices['output']}"
            )


def test_snapshot_entries_carry_provenance() -> None:
    for provider_id, pinned in _snapshot()["providers"].items():
        for field in ("snapshot_date", "source", "verified_by"):
            assert pinned.get(field), f"{provider_id} snapshot is missing '{field}'"

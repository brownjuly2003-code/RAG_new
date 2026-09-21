"""Composition root for the resolution kernel's read-only shadow journeys.

Phase A of plan_23_08_2026. Until this module existed, the kernel had no
caller: `grep -rlE "from (resolution|knowledge|actions)" api/` returned
nothing, so every slice was proven only against its own tests. This is the
seam that changes that, and it is deliberately one-directional -- the kernel
never learns anything about FastAPI, and `api/` never learns how a shadow loop
is built.

A shadow observes and records. It does not own the response, it cannot change
it, and a failure inside it must not reach the caller.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from resolution.adapters.shipment_status import (
    FixtureShipmentSource,
    LegacyRetrievalPolicyAdapter,
    ShipmentFixture,
)
from resolution.application.shipment_status import (
    ShipmentShadowRequest,
    ShipmentShadowResult,
    ShipmentStatusShadowLoop,
)
from resolution.contracts.models import ResolutionContract, TerminalOutcome

logger = logging.getLogger(__name__)

SHIPMENT_STATUS_JOURNEY = "shipment-status"

_PACKAGE_ROOT = Path(__file__).resolve().parent
SHIPMENT_CONTRACT_PATH = _PACKAGE_ROOT / "contracts" / "versions" / "v0.1" / "shipment-status.json"
SHIPMENT_RESPONSE_CONTRACT_PATH = (
    _PACKAGE_ROOT / "contracts" / "versions" / "v0.1" / "shipment-status-response.json"
)
SHIPMENT_FIXTURE_PATH = _PACKAGE_ROOT / "adapters" / "fixtures" / "shipment-status-v0.1.json"


@dataclass(frozen=True, slots=True)
class ShadowProducerOutcome:
    """Minimal trace outcome when a journey produces no persistable evidence."""

    journey: str
    outcome: Literal["journey_declined", "producer_failure"]
    terminal_state: TerminalOutcome | None = None
    reason_codes: tuple[str, ...] = ()


def load_shipment_contract(path: Path | None = None) -> ResolutionContract:
    """Load the pinned shipment-status contract that ships with the package.

    The loop re-checks id, version and digest against its own constants, so a
    contract edited without bumping its version fails loudly at construction
    rather than quietly changing what the shadow measures.
    """
    source = path or SHIPMENT_CONTRACT_PATH
    return ResolutionContract.model_validate_json(source.read_text(encoding="utf-8"))


def load_shipment_response_contract(path: Path | None = None) -> ResolutionContract:
    """Load the pinned shipment-status response contract (0.2.0).

    Kept separate from the 0.1.0 shadow contract, which stays untouched: this
    is the contract a terminal must be bound to before it is allowed to own
    the legacy answer, so it is pinned and loaded by name.
    """
    source = path or SHIPMENT_RESPONSE_CONTRACT_PATH
    return ResolutionContract.model_validate_json(source.read_text(encoding="utf-8"))


def load_shipment_fixtures(path: Path | None = None) -> tuple[ShipmentFixture, ...]:
    """Load the fixture TMS state.

    This is a stand-in, not a transport management system. Anything measured
    through it is fixture-sourced and must say so.
    """
    source = path or SHIPMENT_FIXTURE_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    return tuple(
        ShipmentFixture(
            tenant_id=str(row["tenant_id"]),
            shipment_id=str(row["shipment_id"]),
            status=str(row["status"]),
            location=str(row["location"]),
            estimated_delivery=str(row["estimated_delivery"]),
            observed_at=datetime.fromisoformat(str(row["observed_at"])),
            source_version=str(row["source_version"]),
        )
        for row in payload["shipments"]
    )


def build_shipment_status_observer(
    *,
    retriever: object,
    sink: Callable[[ShipmentShadowResult | ShadowProducerOutcome], None] | None = None,
    contract_path: Path | None = None,
    fixture_path: Path | None = None,
) -> Callable[[ShipmentShadowRequest], ShipmentShadowResult | None]:
    """Build the observer callable `run_legacy_ask_shadow` expects.

    `sink` receives a full result, or a minimal outcome for a decline/failure;
    it is where trace and evidence persistence hang. Both the loop and the
    sink are wrapped: a shadow that raises would otherwise turn an answered
    question into a 500.
    """
    loop = ShipmentStatusShadowLoop(
        contract=load_shipment_contract(contract_path),
        source=FixtureShipmentSource(fixtures=load_shipment_fixtures(fixture_path)),
        policy=LegacyRetrievalPolicyAdapter(retriever),
    )

    def emit(value: ShipmentShadowResult | ShadowProducerOutcome) -> None:
        if sink is None:
            return
        try:
            sink(value)
        except Exception:
            logger.warning("shipment-status shadow sink failed", exc_info=True)

    def observe(request: ShipmentShadowRequest) -> ShipmentShadowResult | None:
        try:
            result = loop.run(request)
        except Exception:
            logger.warning("shipment-status shadow failed", exc_info=True)
            emit(
                ShadowProducerOutcome(
                    journey=SHIPMENT_STATUS_JOURNEY,
                    outcome="producer_failure",
                )
            )
            return None
        if (
            result.terminal_state is TerminalOutcome.CANCELLED
            and result.reason_codes == ("NOT_IN_JOURNEY",)
        ):
            emit(
                ShadowProducerOutcome(
                    journey=SHIPMENT_STATUS_JOURNEY,
                    outcome="journey_declined",
                    terminal_state=result.terminal_state,
                    reason_codes=result.reason_codes,
                )
            )
            return None
        emit(result)
        return result

    return observe


def build_shadow_observers(
    *,
    journeys: Sequence[str],
    retriever: object,
    sink: Callable[[ShipmentShadowResult | ShadowProducerOutcome], None] | None = None,
    response_journeys: Sequence[str] = (),
) -> dict[str, Callable[[ShipmentShadowRequest], Any]]:
    """Build every enabled shadow observer. Empty `journeys` means empty dict.

    `response_journeys` names journeys that run under the pinned response
    contract (0.2.0) so their terminal can own the /api/ask answer; only an
    enabled shipment-status journey gets the new contract path, everything
    else keeps the original (`None`).

    A journey that cannot be constructed is logged and skipped rather than
    taking the process down: the shadow is not allowed to make the inherited
    runtime worse than it was without it.
    """
    observers: dict[str, Callable[[ShipmentShadowRequest], Any]] = {}
    for journey in journeys:
        if journey != SHIPMENT_STATUS_JOURNEY:
            logger.warning("unknown shadow journey %r, skipped", journey)
            continue
        try:
            observers[journey] = build_shipment_status_observer(
                retriever=retriever,
                sink=sink,
                contract_path=(
                    SHIPMENT_RESPONSE_CONTRACT_PATH
                    if journey in response_journeys
                    else None
                ),
            )
        except Exception:
            logger.warning("could not build %r shadow observer", journey, exc_info=True)
    return observers


__all__ = [
    "SHIPMENT_CONTRACT_PATH",
    "SHIPMENT_RESPONSE_CONTRACT_PATH",
    "SHIPMENT_FIXTURE_PATH",
    "SHIPMENT_STATUS_JOURNEY",
    "ShadowProducerOutcome",
    "build_shadow_observers",
    "build_shipment_status_observer",
    "load_shipment_contract",
    "load_shipment_fixtures",
    "load_shipment_response_contract",
]

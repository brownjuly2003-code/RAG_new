from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from itertools import islice
from typing import cast

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ShipmentProviderTimeout(TimeoutError):
    """The fixture source models a bounded source-provider timeout."""


class InvalidPolicyEvidence(ValueError):
    """Retrieved policy evidence did not satisfy the typed adapter contract."""


@dataclass(frozen=True, slots=True)
class ShipmentFixture:
    tenant_id: str
    shipment_id: str
    status: str
    location: str
    estimated_delivery: str
    observed_at: datetime
    source_version: str


@dataclass(frozen=True, slots=True)
class ShipmentObservation:
    tenant_id: str
    shipment_id: str
    status: str
    location: str
    estimated_delivery: str
    observed_at: datetime
    source_id: str
    source_version: str
    content_digest: str


@dataclass(frozen=True, slots=True)
class PolicyEvidence:
    tenant_id: str
    authority: str
    data_revision: str
    recorded_at: datetime
    valid_from: datetime
    valid_to: datetime | None
    status_disclosure_allowed: bool
    content_digest: str


def _aware_datetime(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise InvalidPolicyEvidence(f"invalid {field}") from exc
    else:
        raise InvalidPolicyEvidence(f"invalid {field}")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InvalidPolicyEvidence(f"{field} must be timezone-aware")
    return parsed


def _required_text(metadata: Mapping[str, object], field: str) -> str:
    value = metadata.get(field)
    if not isinstance(value, str) or not value.strip():
        raise InvalidPolicyEvidence(f"invalid {field}")
    return value.strip()


class FixtureShipmentSource:
    """Tenant-scoped, deterministic read-only shipment source."""

    def __init__(
        self,
        *,
        fixtures: tuple[ShipmentFixture, ...],
        timeout_shipment_ids: frozenset[str] = frozenset(),
    ) -> None:
        self._fixtures = fixtures
        self._timeout_shipment_ids = frozenset(item.upper() for item in timeout_shipment_ids)

    def lookup(
        self,
        *,
        tenant_id: str,
        shipment_id: str,
        timeout_seconds: int,
    ) -> ShipmentObservation | None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        normalized = shipment_id.upper()
        if normalized in self._timeout_shipment_ids:
            raise ShipmentProviderTimeout("fixture shipment source timed out")
        fixture = next(
            (
                item
                for item in self._fixtures
                if item.tenant_id == tenant_id and item.shipment_id.upper() == normalized
            ),
            None,
        )
        if fixture is None:
            return None
        if fixture.observed_at.tzinfo is None or fixture.observed_at.utcoffset() is None:
            raise ValueError("fixture observed_at must be timezone-aware")
        canonical = json.dumps(
            {
                "estimated_delivery": fixture.estimated_delivery,
                "location": fixture.location,
                "observed_at": fixture.observed_at.isoformat(),
                "shipment_id": fixture.shipment_id.upper(),
                "source_version": fixture.source_version,
                "status": fixture.status,
                "tenant_id": fixture.tenant_id,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return ShipmentObservation(
            tenant_id=fixture.tenant_id,
            shipment_id=fixture.shipment_id.upper(),
            status=fixture.status,
            location=fixture.location,
            estimated_delivery=fixture.estimated_delivery,
            observed_at=fixture.observed_at,
            source_id="shipment-source-primary",
            source_version=fixture.source_version,
            content_digest=hashlib.sha256(canonical).hexdigest(),
        )


_RetrieveDocuments = Callable[[str], Iterable[object] | None]


class LegacyRetrievalPolicyAdapter:
    """Typed adapter over the inherited ``get_relevant_documents`` boundary."""

    def __init__(self, retriever: object, *, max_candidates: int = 20) -> None:
        if max_candidates < 1:
            raise ValueError("max_candidates must be positive")
        retrieve = getattr(retriever, "get_relevant_documents", None)
        if not callable(retrieve):
            raise TypeError("retriever must expose get_relevant_documents")
        self._retrieve = cast(_RetrieveDocuments, retrieve)
        self._max_candidates = max_candidates

    def gather(
        self,
        *,
        tenant_id: str,
        shipment_id: str,
        effective_at: datetime,
    ) -> tuple[PolicyEvidence, ...]:
        if effective_at.tzinfo is None or effective_at.utcoffset() is None:
            raise ValueError("effective_at must be timezone-aware")
        raw_documents = self._retrieve(f"shipment status disclosure {shipment_id}")
        if raw_documents is None:
            return ()
        evidence: list[PolicyEvidence] = []
        seen: set[tuple[str, str]] = set()
        for document in islice(raw_documents, self._max_candidates):
            if isinstance(document, Mapping):
                metadata_value = document.get("metadata", {})
            else:
                metadata_value = getattr(document, "metadata", {})
            if not isinstance(metadata_value, Mapping):
                raise InvalidPolicyEvidence("policy metadata must be a mapping")
            metadata: Mapping[str, object] = metadata_value
            if metadata.get("tenant_id") != tenant_id:
                continue
            authority = _required_text(metadata, "authority")
            if authority != "logistics-policy-primary":
                continue
            revision = _required_text(metadata, "policy_revision")
            recorded_at = _aware_datetime(metadata.get("recorded_at"), "recorded_at")
            valid_from = _aware_datetime(metadata.get("valid_from"), "valid_from")
            valid_to_value = metadata.get("valid_to")
            valid_to = (
                None if valid_to_value is None else _aware_datetime(valid_to_value, "valid_to")
            )
            if effective_at < valid_from or (valid_to is not None and effective_at >= valid_to):
                continue
            allowed = metadata.get("status_disclosure_allowed")
            if type(allowed) is not bool:
                raise InvalidPolicyEvidence("status_disclosure_allowed must be boolean")
            digest = _required_text(metadata, "content_digest")
            if _SHA256_PATTERN.fullmatch(digest) is None:
                raise InvalidPolicyEvidence("content_digest must be sha256")
            identity = (revision, digest)
            if identity in seen:
                continue
            seen.add(identity)
            evidence.append(
                PolicyEvidence(
                    tenant_id=tenant_id,
                    authority=authority,
                    data_revision=revision,
                    recorded_at=recorded_at,
                    valid_from=valid_from,
                    valid_to=valid_to,
                    status_disclosure_allowed=allowed,
                    content_digest=digest,
                )
            )
        return tuple(evidence)


__all__ = [
    "FixtureShipmentSource",
    "InvalidPolicyEvidence",
    "LegacyRetrievalPolicyAdapter",
    "PolicyEvidence",
    "ShipmentFixture",
    "ShipmentObservation",
    "ShipmentProviderTimeout",
]

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TypeAlias
from uuid import UUID

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SYMBOL = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_SCOPE = re.compile(r"^[a-z][a-z0-9_.:-]{0,127}$")
_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$")

JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class ActionDomainError(ValueError):
    pass


class InvalidActionValue(ActionDomainError):
    pass


class ActionManifestMismatch(ActionDomainError):
    pass


class ActionPolicyMismatch(ActionDomainError):
    pass


class ActionIdempotencyConflict(ActionDomainError):
    pass


class ActionConfirmationRejected(ActionDomainError):
    pass


class ActionWorkUnavailable(ActionDomainError):
    pass


class ActionConnectorIdentityMismatch(ActionDomainError):
    pass


class ActionConnectorRejected(ActionDomainError):
    pass


class ActionCompensationRejected(ActionDomainError):
    pass


class ActionRisk(StrEnum):
    READ = "read"
    REVERSIBLE_WRITE = "reversible_write"
    IRREVERSIBLE_WRITE = "irreversible_write"


class ActionPolicyResult(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"


class ConfirmationDecision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class ActionRunState(StrEnum):
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    READY = "ready"
    DISPATCHED = "dispatched"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"
    RECONCILING = "reconciling"
    POSTCONDITION_PASSED = "postcondition_passed"
    POSTCONDITION_FAILED = "postcondition_failed"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ActionReceiptState(StrEnum):
    DENIED = "denied"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    READY = "ready"
    DISPATCHED = "dispatched"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"
    RECONCILING = "reconciling"
    POSTCONDITION_PASSED = "postcondition_passed"
    POSTCONDITION_FAILED = "postcondition_failed"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ActionOutboxKind(StrEnum):
    DISPATCH = "dispatch"
    RECONCILE = "reconcile"


class ActionOutboxState(StrEnum):
    PENDING = "pending"
    LEASED = "leased"
    DELIVERED = "delivered"


class TransportOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"
    IDENTITY_MISMATCH = "identity_mismatch"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"


class PostconditionStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


def _require_uuid(value: UUID, field: str) -> None:
    if not isinstance(value, UUID) or value.int == 0:
        raise InvalidActionValue(f"{field} must be a non-nil UUID")


def _require_text(value: str, field: str, *, maximum: int = 256) -> None:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum:
        raise InvalidActionValue(f"{field} must be non-empty trimmed text")


def _require_symbol(value: str, field: str) -> None:
    if not isinstance(value, str) or _SYMBOL.fullmatch(value) is None:
        raise InvalidActionValue(f"{field} must be a stable lowercase symbol")


def _require_semver(value: str, field: str) -> None:
    if not isinstance(value, str) or _SEMVER.fullmatch(value) is None:
        raise InvalidActionValue(f"{field} must be a semantic version")


def _require_scope(value: str, field: str) -> None:
    if not isinstance(value, str) or _SCOPE.fullmatch(value) is None:
        raise InvalidActionValue(f"{field} must be a stable lowercase scope")


def _require_digest(value: str, field: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise InvalidActionValue(f"{field} must be a lowercase sha256 digest")


def _require_aware(value: datetime, field: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise InvalidActionValue(f"{field} must be timezone-aware")


def _normalize_json(value: object, *, path: str = "$") -> JsonValue:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise InvalidActionValue(f"{path} contains a non-finite number")
        return value
    if isinstance(value, (list, tuple)):
        return [_normalize_json(item, path=f"{path}[]") for item in value]
    if isinstance(value, dict):
        normalized: dict[str, JsonValue] = {}
        for key in sorted(value):
            if not isinstance(key, str) or not key or key != key.strip():
                raise InvalidActionValue(f"{path} contains an invalid object key")
            normalized[key] = _normalize_json(value[key], path=f"{path}.{key}")
        return normalized
    raise InvalidActionValue(f"{path} contains a non-JSON value")


def canonical_json(value: object) -> str:
    return json.dumps(
        _normalize_json(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ActionManifest:
    tenant_id: UUID
    id: str
    version: str
    connector_id: str
    action_id: str
    schema_digest: str
    risk: ActionRisk
    required_scopes: tuple[str, ...]
    timeout_seconds: int
    confirmation_ttl_seconds: int | None
    postcondition_id: str
    postcondition_version: str
    compensation_manifest_id: str | None
    max_reconciliation_attempts: int
    recorded_at: datetime
    input_fields: tuple[str, ...] = ("session_id", "summary", "priority")

    def __post_init__(self) -> None:
        _require_uuid(self.tenant_id, "manifest tenant_id")
        _require_symbol(self.id, "manifest id")
        _require_semver(self.version, "manifest version")
        _require_symbol(self.connector_id, "connector id")
        _require_symbol(self.action_id, "action id")
        _require_digest(self.schema_digest, "manifest schema_digest")
        if not self.required_scopes or len(self.required_scopes) != len(set(self.required_scopes)):
            raise InvalidActionValue("manifest required_scopes must be non-empty and unique")
        for scope in self.required_scopes:
            _require_scope(scope, "manifest scope")
        if not self.input_fields or len(self.input_fields) != len(set(self.input_fields)):
            raise InvalidActionValue("manifest input_fields must be non-empty and unique")
        for field in self.input_fields:
            _require_symbol(field, "manifest input field")
        if not 1 <= self.timeout_seconds <= 300:
            raise InvalidActionValue("manifest timeout_seconds is outside 1..300")
        if self.risk is ActionRisk.READ:
            if self.confirmation_ttl_seconds is not None:
                raise InvalidActionValue("read actions cannot require confirmation")
        elif (
            self.confirmation_ttl_seconds is None
            or not 1 <= self.confirmation_ttl_seconds <= 86_400
        ):
            raise InvalidActionValue("write actions require a finite confirmation ttl")
        _require_symbol(self.postcondition_id, "postcondition id")
        _require_semver(self.postcondition_version, "postcondition version")
        if self.compensation_manifest_id is not None:
            _require_symbol(self.compensation_manifest_id, "compensation manifest id")
            if self.compensation_manifest_id == self.id:
                raise InvalidActionValue("an action cannot compensate itself")
        if not 1 <= self.max_reconciliation_attempts <= 20:
            raise InvalidActionValue("max_reconciliation_attempts is outside 1..20")
        _require_aware(self.recorded_at, "manifest recorded_at")


@dataclass(frozen=True, slots=True)
class ActionCommand:
    tenant_id: UUID
    case_id: UUID
    contract_id: str
    contract_version: str
    contract_digest: str
    step_id: str
    manifest_id: str
    manifest_version: str
    manifest_schema_digest: str
    actor_id: str
    actor_scopes: tuple[str, ...]
    logical_operation_key: str
    input_payload: dict[str, object]
    evidence_digest: str
    correlation_id: UUID
    requested_at: datetime
    compensation_of_run_id: UUID | None = None

    def __post_init__(self) -> None:
        _require_uuid(self.tenant_id, "command tenant_id")
        _require_uuid(self.case_id, "command case_id")
        _require_symbol(self.contract_id, "contract id")
        _require_semver(self.contract_version, "contract version")
        _require_digest(self.contract_digest, "contract digest")
        _require_symbol(self.step_id, "contract step id")
        _require_symbol(self.manifest_id, "command manifest id")
        _require_semver(self.manifest_version, "command manifest version")
        _require_digest(self.manifest_schema_digest, "command manifest schema digest")
        _require_text(self.actor_id, "actor id", maximum=256)
        if len(self.actor_scopes) != len(set(self.actor_scopes)):
            raise InvalidActionValue("actor scopes must be unique")
        for scope in self.actor_scopes:
            _require_scope(scope, "actor scope")
        _require_text(self.logical_operation_key, "logical operation key", maximum=512)
        normalized = _normalize_json(self.input_payload)
        if not isinstance(normalized, dict):
            raise InvalidActionValue("action input must be a JSON object")
        object.__setattr__(self, "input_payload", normalized)
        _require_digest(self.evidence_digest, "evidence digest")
        _require_uuid(self.correlation_id, "correlation id")
        _require_aware(self.requested_at, "requested_at")
        if self.compensation_of_run_id is not None:
            _require_uuid(self.compensation_of_run_id, "compensation_of_run_id")


@dataclass(frozen=True, slots=True)
class ActionDigests:
    operation_key_digest: str
    input_digest: str
    action_digest: str


def derive_action_digests(manifest: ActionManifest, command: ActionCommand) -> ActionDigests:
    if (
        manifest.tenant_id != command.tenant_id
        or manifest.id != command.manifest_id
        or manifest.version != command.manifest_version
        or manifest.schema_digest != command.manifest_schema_digest
    ):
        raise ActionManifestMismatch("command does not reference the exact persisted manifest")
    input_digest = canonical_sha256(command.input_payload)
    operation_key_digest = canonical_sha256(
        {
            "tenant_id": str(command.tenant_id),
            "case_id": str(command.case_id),
            "contract_id": command.contract_id,
            "contract_version": command.contract_version,
            "step_id": command.step_id,
            "manifest_id": command.manifest_id,
            "manifest_version": command.manifest_version,
            "logical_operation_key": command.logical_operation_key,
        }
    )
    action_digest = canonical_sha256(
        {
            "operation_key_digest": operation_key_digest,
            "input_digest": input_digest,
            "contract_digest": command.contract_digest,
            "manifest_schema_digest": command.manifest_schema_digest,
            "evidence_digest": command.evidence_digest,
            "actor_id": command.actor_id,
            "compensation_of_run_id": (
                None
                if command.compensation_of_run_id is None
                else str(command.compensation_of_run_id)
            ),
        }
    )
    return ActionDigests(operation_key_digest, input_digest, action_digest)


@dataclass(frozen=True, slots=True)
class ActionPolicyRequest:
    tenant_id: UUID
    case_id: UUID
    actor_id: str
    actor_scopes: tuple[str, ...]
    manifest_id: str
    manifest_version: str
    action_digest: str
    input_digest: str
    evidence_digest: str
    risk: ActionRisk
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class ActionPolicyDecision:
    id: UUID
    tenant_id: UUID
    case_id: UUID
    action_digest: str
    input_digest: str
    evidence_digest: str
    result: ActionPolicyResult
    reason_codes: tuple[str, ...]
    policy_adapter: str
    policy_revision: str
    decided_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        _require_uuid(self.id, "policy decision id")
        _require_uuid(self.tenant_id, "policy decision tenant_id")
        _require_uuid(self.case_id, "policy decision case_id")
        _require_digest(self.action_digest, "policy action_digest")
        _require_digest(self.input_digest, "policy input_digest")
        _require_digest(self.evidence_digest, "policy evidence_digest")
        if not self.reason_codes:
            raise InvalidActionValue("policy decision requires reason codes")
        for reason in self.reason_codes:
            _require_symbol(reason.lower(), "policy reason code")
        _require_symbol(self.policy_adapter, "policy adapter")
        _require_text(self.policy_revision, "policy revision", maximum=128)
        _require_aware(self.decided_at, "policy decided_at")
        _require_aware(self.expires_at, "policy expires_at")
        if self.expires_at <= self.decided_at:
            raise InvalidActionValue("policy decision expiry must follow decision time")


@dataclass(frozen=True, slots=True)
class ActionRun:
    id: UUID
    tenant_id: UUID
    case_id: UUID
    manifest_id: str
    manifest_version: str
    manifest_schema_digest: str
    connector_id: str
    action_id: str
    operation_key_digest: str
    input_digest: str
    action_digest: str
    evidence_digest: str
    policy_decision_id: UUID
    downstream_idempotency_key: str
    state: ActionRunState
    safe_input: dict[str, object]
    created_at: datetime
    updated_at: datetime
    attempt_count: int = 0
    confirmation_id: UUID | None = None
    outbox_event_id: UUID | None = None
    lease_token: str | None = None
    lease_expires_at: datetime | None = None
    remote_operation_id: str | None = None
    remote_resource_id: str | None = None
    result_digest: str | None = None
    compensation_of_run_id: UUID | None = None

    def __post_init__(self) -> None:
        _require_uuid(self.id, "action run id")
        _require_uuid(self.tenant_id, "action run tenant_id")
        _require_uuid(self.case_id, "action run case_id")
        _require_symbol(self.manifest_id, "action run manifest id")
        _require_semver(self.manifest_version, "action run manifest version")
        _require_digest(self.manifest_schema_digest, "action run manifest schema digest")
        _require_symbol(self.connector_id, "action run connector id")
        _require_symbol(self.action_id, "action run action id")
        _require_digest(self.operation_key_digest, "operation key digest")
        _require_digest(self.input_digest, "run input digest")
        _require_digest(self.action_digest, "run action digest")
        _require_digest(self.evidence_digest, "run evidence digest")
        _require_uuid(self.policy_decision_id, "run policy decision id")
        _require_text(self.downstream_idempotency_key, "downstream idempotency key")
        normalized = _normalize_json(self.safe_input)
        if not isinstance(normalized, dict):
            raise InvalidActionValue("safe input must be a JSON object")
        object.__setattr__(self, "safe_input", normalized)
        _require_aware(self.created_at, "run created_at")
        _require_aware(self.updated_at, "run updated_at")
        if self.attempt_count < 0:
            raise InvalidActionValue("attempt_count cannot be negative")
        if self.confirmation_id is not None:
            _require_uuid(self.confirmation_id, "run confirmation id")
        if self.outbox_event_id is not None:
            _require_uuid(self.outbox_event_id, "run outbox event id")
        if (self.lease_token is None) != (self.lease_expires_at is None):
            raise InvalidActionValue("run lease token and expiry must be set together")
        if self.lease_token is not None:
            _require_text(self.lease_token, "run lease token", maximum=128)
            _require_aware(self.lease_expires_at, "run lease expiry")  # type: ignore[arg-type]
        if self.result_digest is not None:
            _require_digest(self.result_digest, "run result digest")
        if self.compensation_of_run_id is not None:
            _require_uuid(self.compensation_of_run_id, "run compensation parent")
            if self.compensation_of_run_id == self.id:
                raise InvalidActionValue("an action run cannot compensate itself")


@dataclass(frozen=True, slots=True)
class ActionConfirmation:
    id: UUID
    tenant_id: UUID
    run_id: UUID
    action_digest: str
    actor_id: str | None
    decision: ConfirmationDecision
    expires_at: datetime
    created_at: datetime
    decided_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ActionOutboxEvent:
    id: UUID
    tenant_id: UUID
    run_id: UUID
    sequence: int
    kind: ActionOutboxKind
    state: ActionOutboxState
    payload_digest: str
    available_at: datetime
    attempts: int = 0
    lease_token: str | None = None
    lease_expires_at: datetime | None = None
    delivered_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ActionWorkItem:
    run: ActionRun
    manifest: ActionManifest
    event: ActionOutboxEvent
    attempt_number: int
    lease_token: str
    started_at: datetime


@dataclass(frozen=True, slots=True)
class ConnectorResult:
    connector_id: str
    action_id: str
    downstream_idempotency_key: str
    remote_operation_id: str
    remote_resource_id: str
    response_digest: str
    observed_at: datetime

    def __post_init__(self) -> None:
        _require_symbol(self.connector_id, "connector result connector id")
        _require_symbol(self.action_id, "connector result action id")
        _require_text(self.downstream_idempotency_key, "connector idempotency key")
        _require_text(self.remote_operation_id, "remote operation id")
        _require_text(self.remote_resource_id, "remote resource id")
        _require_digest(self.response_digest, "connector response digest")
        _require_aware(self.observed_at, "connector observed_at")

    def require_identity(self, manifest: ActionManifest, run: ActionRun) -> None:
        if (
            self.connector_id != manifest.connector_id
            or self.action_id != manifest.action_id
            or self.downstream_idempotency_key != run.downstream_idempotency_key
        ):
            raise ActionConnectorIdentityMismatch(
                "connector result identity is not pinned to the run"
            )


@dataclass(frozen=True, slots=True)
class ActionPostconditionResult:
    id: UUID
    tenant_id: UUID
    run_id: UUID
    checker_id: str
    checker_version: str
    observation_digest: str
    status: PostconditionStatus
    reason_codes: tuple[str, ...]
    checked_at: datetime

    def __post_init__(self) -> None:
        _require_uuid(self.id, "postcondition result id")
        _require_uuid(self.tenant_id, "postcondition tenant_id")
        _require_uuid(self.run_id, "postcondition run_id")
        _require_symbol(self.checker_id, "postcondition checker id")
        _require_semver(self.checker_version, "postcondition checker version")
        _require_digest(self.observation_digest, "postcondition observation digest")
        if not self.reason_codes:
            raise InvalidActionValue("postcondition result requires reason codes")
        _require_aware(self.checked_at, "postcondition checked_at")


@dataclass(frozen=True, slots=True)
class ActionReceipt:
    state: ActionReceiptState
    action_digest: str
    reason_codes: tuple[str, ...]
    run_id: UUID | None = None
    confirmation_id: UUID | None = None
    outbox_event_id: UUID | None = None
    remote_resource_id: str | None = None
    replayed: bool = False


__all__ = [
    "ActionCommand",
    "ActionCompensationRejected",
    "ActionConfirmation",
    "ActionConfirmationRejected",
    "ActionConnectorRejected",
    "ActionConnectorIdentityMismatch",
    "ActionDigests",
    "ActionDomainError",
    "ActionIdempotencyConflict",
    "ActionManifest",
    "ActionManifestMismatch",
    "ActionOutboxEvent",
    "ActionOutboxKind",
    "ActionOutboxState",
    "ActionPolicyDecision",
    "ActionPolicyMismatch",
    "ActionPolicyRequest",
    "ActionPolicyResult",
    "ActionPostconditionResult",
    "ActionReceipt",
    "ActionReceiptState",
    "ActionRisk",
    "ActionRun",
    "ActionRunState",
    "ActionWorkItem",
    "ActionWorkUnavailable",
    "ConfirmationDecision",
    "ConnectorResult",
    "InvalidActionValue",
    "PostconditionStatus",
    "TransportOutcome",
    "canonical_json",
    "canonical_sha256",
    "derive_action_digests",
]

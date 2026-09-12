"""Phase A.3 — the evidence bundle, projected into what an operator reads.

A `resolution_shadow` trace step carries the whole export: contract identity,
the source observation, the policy decision, every claim with the evidence
digests behind it, the postconditions and the escalation brief. That is the
right thing to *store* and the wrong thing to *show* — a reviewer asking "why
did it say that, and how stale was what it knew" should not have to join
digests to observations by eye.

This module does that join, and nothing else. It is pure: a trace dict in, a
view dict out, no I/O and no clock. The freshness it reports is measured
against the moment the shadow recorded the step, not against now, so the same
trace projects to the same numbers next week — which is the only way a number
on this screen can be quoted anywhere else.

**Why the trace and not the resolution tables.** A.1b writes the same bundle
to `support_cases` / `case_events` / `evidence_snapshots` /
`case_evidence_links`, and that copy is the queryable one. It is also
best-effort and bounded at two seconds: a run whose database write timed out
still has a complete trace step, and an Evidence tab sourced from Postgres
would show nothing for it. The view therefore reads the trace and carries
`case_id` / `case_version` so the queryable copy is one lookup away.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from resolution.persistence import POLICY_REQUIREMENT_ID, SOURCE_REQUIREMENT_ID

SHADOW_NODE_NAME = "resolution_shadow"

_JOURNEY_RECORDED = "journey_recorded"
_JOURNEY_DECLINED = "journey_declined"
_PRODUCER_FAILURE = "producer_failure"
_SHADOW_DISABLED = "shadow_disabled"

__all__ = ["SHADOW_NODE_NAME", "evidence_view"]


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, str) or isinstance(value, Mapping):
        return ()
    return value if isinstance(value, Sequence) else ()


def _as_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_seconds(observed_at: Any, as_of: datetime | None) -> float | None:
    """How old the evidence was when the shadow recorded it.

    None whenever either end is missing or unparsable, and never negative: a
    source clock running ahead of the trace clock is a clock problem, not
    evidence from the future, and rendering it as one would be worse than
    rendering nothing.
    """
    observed = _parse_time(observed_at)
    if observed is None or as_of is None:
        return None
    if observed.tzinfo is None or as_of.tzinfo is None:
        return None
    return max(0.0, (as_of - observed).total_seconds())


def _source_evidence(observation: Mapping[str, Any], as_of: datetime | None) -> dict[str, Any]:
    shipment_id = _as_text(observation.get("shipment_id"))
    status = _as_text(observation.get("status"))
    location = _as_text(observation.get("location"))
    label = " · ".join(part for part in (shipment_id, status, location) if part)
    return {
        "requirement_id": SOURCE_REQUIREMENT_ID,
        "kind": "observation",
        "label": label,
        "digest": _as_text(observation.get("content_digest")),
        "source_id": _as_text(observation.get("source_id")),
        "source_version": _as_text(observation.get("source_version")),
        "observed_at": _as_text(observation.get("observed_at")),
        "age_seconds": _age_seconds(observation.get("observed_at"), as_of),
        "detail": {
            "shipment_id": shipment_id,
            "status": status,
            "location": location,
            "estimated_delivery": _as_text(observation.get("estimated_delivery")),
        },
    }


def _policy_evidence(policy: Mapping[str, Any], as_of: datetime | None) -> dict[str, Any]:
    return {
        "requirement_id": POLICY_REQUIREMENT_ID,
        "kind": "policy",
        "label": _as_text(policy.get("decision")),
        "digest": _as_text(policy.get("content_digest")),
        "source_id": _as_text(policy.get("authority")),
        "source_version": _as_text(policy.get("data_revision")),
        # A policy's own recorded_at, not the instant the run happened to read
        # it. The distinction is the whole point of storing it bitemporally.
        "observed_at": _as_text(policy.get("recorded_at")),
        "age_seconds": _age_seconds(policy.get("recorded_at"), as_of),
        "detail": {
            "decision": _as_text(policy.get("decision")),
            "implementation_version": _as_text(policy.get("implementation_version")),
            "valid_from": _as_text(policy.get("valid_from")),
            "valid_to": policy.get("valid_to"),
        },
    }


def _claim_view(
    claim: Mapping[str, Any],
    *,
    by_requirement: Mapping[str, dict[str, Any]],
    by_digest: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    """Resolve one claim's evidence references to the evidence themselves.

    Matched by requirement id first and digest second. Requirement id is what
    the contract actually names; the digest is the fallback for a bundle whose
    requirement ids and evidence disagree, which is a defect worth seeing
    rather than hiding — hence `unresolved`, which says plainly that a claim
    cites evidence this bundle does not contain.
    """
    requirement_ids = [
        _as_text(item) for item in _as_sequence(claim.get("evidence_requirement_ids"))
    ]
    digests = [_as_text(item) for item in _as_sequence(claim.get("evidence_digests"))]
    # Paired by position, padded to the longer of the two: a claim that cites
    # digests without naming requirements still resolves, and a mismatch in
    # length shows up as an unresolved reference instead of a dropped one.
    references = [
        (
            requirement_ids[index] if index < len(requirement_ids) else "",
            digests[index] if index < len(digests) else "",
        )
        for index in range(max(len(requirement_ids), len(digests)))
    ]

    sources: list[dict[str, Any]] = []
    unresolved: list[str] = []
    seen: set[str] = set()

    for requirement_id, digest in references:
        evidence = by_requirement.get(requirement_id) or by_digest.get(digest)
        if evidence is None:
            unresolved.append(requirement_id or digest)
            continue
        key = f"{evidence['requirement_id']}:{evidence['digest']}"
        if key in seen:
            continue
        seen.add(key)
        cited = dict(evidence)
        # The digest the claim cites, next to the digest the evidence carries.
        # Equal in every healthy bundle; a difference means the claim was
        # written against evidence that has since been replaced.
        cited["cited_digest"] = digest
        cited["digest_matches"] = bool(digest) and digest == evidence["digest"]
        sources.append(cited)

    return {
        "claim_id": _as_text(claim.get("claim_id")),
        "text": _as_text(claim.get("text")),
        "sources": sources,
        "unresolved": unresolved,
    }


def _replay_receipt(
    evidence: Mapping[str, Any],
    contract: Mapping[str, Any],
    observation: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Everything needed to run this case again and expect the same answer.

    There is no separate receipt object in the kernel; the receipt is the set
    of digests and versions the run was pinned to, which the export already
    carries. Collecting them in one place is what makes the claim "this is
    replayable" checkable instead of decorative.
    """
    return {
        "mode": _as_text(evidence.get("mode")),
        "case_id": _as_text(evidence.get("case_id")),
        "case_version": evidence.get("case_version"),
        "correlation_id": _as_text(evidence.get("correlation_id")),
        "contract_id": _as_text(contract.get("contract_id")),
        "contract_version": _as_text(contract.get("version")),
        "contract_digest": _as_text(contract.get("digest")),
        "source_id": _as_text(observation.get("source_id")),
        "source_version": _as_text(observation.get("source_version")),
        "source_digest": _as_text(observation.get("content_digest")),
        "policy_authority": _as_text(policy.get("authority")),
        "policy_data_revision": _as_text(policy.get("data_revision")),
        "policy_digest": _as_text(policy.get("content_digest")),
    }


def _journey_view(state: Mapping[str, Any], step_ts: Any) -> dict[str, Any]:
    evidence = _as_mapping(state.get("evidence"))
    outcome = _as_text(state.get("outcome"))
    if outcome not in {_JOURNEY_RECORDED, _JOURNEY_DECLINED, _PRODUCER_FAILURE}:
        outcome = _JOURNEY_RECORDED if evidence else _PRODUCER_FAILURE
    contract = _as_mapping(evidence.get("contract"))
    observation = _as_mapping(evidence.get("source_observation"))
    policy = _as_mapping(evidence.get("policy"))
    as_of = _parse_time(step_ts)

    by_requirement: dict[str, dict[str, Any]] = {}
    by_digest: dict[str, dict[str, Any]] = {}
    for item in (
        _source_evidence(observation, as_of) if observation else None,
        _policy_evidence(policy, as_of) if policy else None,
    ):
        if item is None:
            continue
        by_requirement[item["requirement_id"]] = item
        if item["digest"]:
            by_digest[item["digest"]] = item

    claims = [
        _claim_view(_as_mapping(claim), by_requirement=by_requirement, by_digest=by_digest)
        for claim in _as_sequence(evidence.get("claim_links"))
    ]

    postconditions = [
        {
            "postcondition_id": _as_text(_as_mapping(item).get("postcondition_id")),
            "version": _as_text(_as_mapping(item).get("version")),
            "schema_digest": _as_text(_as_mapping(item).get("schema_digest")),
            "result": _as_text(_as_mapping(item).get("result")),
        }
        for item in _as_sequence(evidence.get("postcondition_versions"))
    ]

    return {
        "journey": _as_text(state.get("journey")),
        "outcome": outcome,
        "as_of": _as_text(step_ts),
        "case_id": _as_text(evidence.get("case_id")) or _as_text(state.get("case_id")),
        "case_version": evidence.get("case_version"),
        "terminal_state": (
            _as_text(evidence.get("terminal_state")) or _as_text(state.get("terminal_state"))
        ),
        "reason_codes": [_as_text(code) for code in _as_sequence(state.get("reason_codes"))],
        "contract": {
            "contract_id": _as_text(contract.get("contract_id")),
            "version": _as_text(contract.get("version")),
            "digest": _as_text(contract.get("digest")),
            "schema_identity": _as_text(contract.get("schema_identity")),
        },
        "policy": _policy_evidence(policy, as_of) if policy else None,
        "observation": _source_evidence(observation, as_of) if observation else None,
        "claims": claims,
        "postconditions": postconditions,
        "escalation_brief": (
            dict(_as_mapping(evidence.get("escalation_brief")))
            if evidence.get("escalation_brief")
            else None
        ),
        "replay_receipt": _replay_receipt(evidence, contract, observation, policy),
    }


def evidence_view(trace: Mapping[str, Any]) -> dict[str, Any]:
    """Project every shadow step of one trace into the operator's view.

    An empty `journeys` list is the honest answer for a trace that ran no
    journey — most of them, since the shadow is off by default. It is not an
    error and must not read like one.
    """
    journeys = [
        _journey_view(_as_mapping(step.get("state")), step.get("ts"))
        for step in (_as_mapping(item) for item in _as_sequence(trace.get("steps")))
        if step.get("node") == SHADOW_NODE_NAME
    ]
    outcomes = {journey["outcome"] for journey in journeys}
    if _PRODUCER_FAILURE in outcomes:
        shadow_status = _PRODUCER_FAILURE
    elif _JOURNEY_RECORDED in outcomes:
        shadow_status = _JOURNEY_RECORDED
    elif _JOURNEY_DECLINED in outcomes:
        shadow_status = _JOURNEY_DECLINED
    else:
        shadow_status = _SHADOW_DISABLED
    view = {
        "trace_id": _as_text(trace.get("trace_id")),
        "started_at": _as_text(trace.get("started_at")),
        "shadow_status": shadow_status,
        "journeys": journeys,
    }
    paths = [
        {"strategy": state.get("retrieval_strategy_effective"), "path": dict(path)}
        for step in (_as_mapping(item) for item in _as_sequence(trace.get("steps")))
        if step.get("node") == "retrieve"
        if (state := _as_mapping(step.get("state")))
        if (path := _as_mapping(state.get("retrieval_path")))
    ]
    if paths:
        view["retrieval_paths"] = paths
    return view

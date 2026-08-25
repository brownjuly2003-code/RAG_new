"""Phase A.3 — the join the Evidence tab reads, held without a browser.

`resolution/evidence_view.py` turns a `resolution_shadow` trace step into what
an operator actually needs: which contract ran, what the policy decided, which
evidence each claim rests on and how old that evidence was when it was read.

Three of its decisions are the ones worth pinning, because each has an obvious
wrong version:

- **freshness is measured against the step, not against now.** A number on
  this screen has to mean the same thing next week, or it cannot be quoted
  anywhere;
- **a claim that cites evidence the bundle does not carry says so.** Dropping
  the reference would render a claim as fully supported when it is not;
- **a trace with no journey projects to an empty list, not an error.** The
  shadow is off by default, so that is the common case and it must not read
  like a failure.
"""

from __future__ import annotations

from typing import Any

import pytest

from resolution.evidence_view import SHADOW_NODE_NAME, evidence_view
from resolution.persistence import POLICY_REQUIREMENT_ID, SOURCE_REQUIREMENT_ID

_STEP_TS = "2026-08-25T12:00:00+00:00"
_OBSERVED_AT = "2026-08-25T11:30:00+00:00"
_POLICY_RECORDED_AT = "2026-08-20T09:00:00+00:00"
_SOURCE_DIGEST = "a" * 64
_POLICY_DIGEST = "b" * 64


def _bundle(**overrides: Any) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "mode": "shadow",
        "tenant_id": "acme",
        "case_id": "11111111-2222-3333-4444-555555555555",
        "case_version": 3,
        "correlation_id": "66666666-7777-8888-9999-000000000000",
        "terminal_state": "verified_resolution",
        "reason_codes": ["shipment.status.known"],
        "contract": {
            "schema_identity": "resolution-contract/v0.1",
            "contract_id": "aircargo.shipment-status",
            "version": "0.1.0",
            "digest": "c" * 64,
        },
        "source_observation": {
            "shipment_id": "AC-100001",
            "status": "in_transit",
            "location": "Frankfurt",
            "estimated_delivery": "2026-08-27",
            "observed_at": _OBSERVED_AT,
            "source_id": "fixture-tms",
            "source_version": "0.1.0",
            "content_digest": _SOURCE_DIGEST,
        },
        "policy": {
            "implementation_version": "1.2.0",
            "data_revision": "2026-08-01",
            "authority": "aircargo-policy",
            "content_digest": _POLICY_DIGEST,
            "decision": "disclose_status",
            "recorded_at": _POLICY_RECORDED_AT,
            "valid_from": "2026-08-01T00:00:00+00:00",
            "valid_to": None,
        },
        "claim_links": [
            {
                "claim_id": "status",
                "text": "Shipment AC-100001 is in transit via Frankfurt.",
                "evidence_requirement_ids": [SOURCE_REQUIREMENT_ID, POLICY_REQUIREMENT_ID],
                "evidence_digests": [_SOURCE_DIGEST, _POLICY_DIGEST],
            }
        ],
        "postcondition_versions": [
            {
                "postcondition_id": "status-disclosed",
                "version": "0.1.0",
                "schema_digest": "d" * 64,
                "result": "satisfied",
            }
        ],
        "escalation_brief": None,
    }
    evidence.update(overrides)
    return evidence


def _trace(*, evidence: dict[str, Any] | None = None, steps: list[Any] | None = None) -> dict:
    if steps is None:
        steps = [
            {"order": 1, "node": "generate", "state": {"answer": "..."}, "ts": _STEP_TS},
            {
                "order": 2,
                "node": SHADOW_NODE_NAME,
                "state": {
                    "journey": "shipment-status",
                    "evidence": evidence if evidence is not None else _bundle(),
                    "terminal_state": "verified_resolution",
                    "reason_codes": ["shipment.status.known"],
                    "case_id": "11111111-2222-3333-4444-555555555555",
                    "kernel_correlation_id": "66666666-7777-8888-9999-000000000000",
                    "shadow_response_text": "not the answer anyone got",
                },
                "ts": _STEP_TS,
            },
        ]
    return {
        "trace_id": "trace-abc123",
        "started_at": "2026-08-25T11:59:58+00:00",
        "finished_at": _STEP_TS,
        "steps": steps,
        "feedback": [],
    }


def _journey(**kwargs: Any) -> dict[str, Any]:
    view = evidence_view(_trace(**kwargs))
    assert view["journeys"], "the projection dropped the shadow step"
    return view["journeys"][0]


# --- what the tab shows -----------------------------------------------------


def test_the_contract_and_the_outcome_come_through() -> None:
    journey = _journey()

    assert journey["journey"] == "shipment-status"
    assert journey["contract"]["contract_id"] == "aircargo.shipment-status"
    assert journey["contract"]["version"] == "0.1.0"
    assert journey["terminal_state"] == "verified_resolution"
    assert journey["reason_codes"] == ["shipment.status.known"]


def test_the_policy_decision_carries_its_own_time_not_the_runs() -> None:
    """Bitemporal, and the tab has to keep it that way.

    `recorded_at` is when the policy became true. Showing the moment the run
    read it would claim the policy was written when the question was asked.
    """
    journey = _journey()

    assert journey["policy"]["detail"]["decision"] == "disclose_status"
    assert journey["policy"]["source_id"] == "aircargo-policy"
    assert journey["policy"]["source_version"] == "2026-08-01"
    assert journey["policy"]["observed_at"] == _POLICY_RECORDED_AT
    assert journey["policy"]["detail"]["valid_to"] is None


def test_a_claim_is_joined_to_the_evidence_it_cites() -> None:
    """The join is the point: digests are unreadable, evidence is not."""
    (claim,) = _journey()["claims"]

    assert claim["text"].startswith("Shipment AC-100001")
    kinds = [source["kind"] for source in claim["sources"]]
    assert kinds == ["observation", "policy"]
    observation = claim["sources"][0]
    assert observation["label"] == "AC-100001 · in_transit · Frankfurt"
    assert observation["digest"] == _SOURCE_DIGEST
    assert observation["digest_matches"] is True


def test_freshness_is_measured_at_the_step_not_at_read_time() -> None:
    """30 minutes between the observation and the step, and it stays 30."""
    first = _journey()["claims"][0]["sources"][0]["age_seconds"]
    second = _journey()["claims"][0]["sources"][0]["age_seconds"]

    assert first == 1800.0
    assert second == first


def test_a_source_clock_ahead_of_the_trace_is_not_evidence_from_the_future() -> None:
    bundle = _bundle()
    bundle["source_observation"]["observed_at"] = "2026-08-25T12:05:00+00:00"

    journey = _journey(evidence=bundle)

    assert journey["observation"]["age_seconds"] == 0.0


@pytest.mark.parametrize(
    "observed_at",
    [
        "",
        "not-a-time",
        # Parses, but carries no zone. An instant without one cannot be
        # subtracted from the trace clock, and guessing UTC would invent a
        # freshness figure out of an ambiguity.
        "2026-08-25 12:00:00",
    ],
)
def test_an_unreadable_timestamp_reports_no_age_rather_than_a_wrong_one(
    observed_at: str,
) -> None:
    bundle = _bundle()
    bundle["source_observation"]["observed_at"] = observed_at

    source = _journey(evidence=bundle)["observation"]

    assert source["age_seconds"] is None
    # The timestamp itself is still shown, so the gap is visible rather than
    # merely absent.
    assert source["observed_at"] == observed_at


def test_a_claim_citing_evidence_the_bundle_does_not_carry_says_so() -> None:
    """Silently dropping the reference would render the claim as supported."""
    bundle = _bundle()
    bundle["claim_links"][0]["evidence_requirement_ids"] = [
        SOURCE_REQUIREMENT_ID,
        "shipment-customs-file",
    ]
    bundle["claim_links"][0]["evidence_digests"] = [_SOURCE_DIGEST, "e" * 64]

    (claim,) = _journey(evidence=bundle)["claims"]

    assert [source["kind"] for source in claim["sources"]] == ["observation"]
    assert claim["unresolved"] == ["shipment-customs-file"]


def test_a_claim_that_cites_a_digest_without_naming_a_requirement_still_resolves() -> None:
    bundle = _bundle()
    bundle["claim_links"][0]["evidence_requirement_ids"] = []

    (claim,) = _journey(evidence=bundle)["claims"]

    assert [source["kind"] for source in claim["sources"]] == ["observation", "policy"]
    assert claim["unresolved"] == []


def test_a_claim_whose_digest_moved_under_it_is_flagged_rather_than_hidden() -> None:
    bundle = _bundle()
    bundle["claim_links"][0]["evidence_digests"] = ["f" * 64, _POLICY_DIGEST]

    (claim,) = _journey(evidence=bundle)["claims"]

    observation = claim["sources"][0]
    assert observation["digest_matches"] is False
    assert observation["cited_digest"] == "f" * 64
    assert observation["digest"] == _SOURCE_DIGEST


def test_the_replay_receipt_pins_everything_a_rerun_would_need() -> None:
    """There is no receipt object in the kernel; this is what one would be."""
    receipt = _journey()["replay_receipt"]

    assert receipt == {
        "mode": "shadow",
        "case_id": "11111111-2222-3333-4444-555555555555",
        "case_version": 3,
        "correlation_id": "66666666-7777-8888-9999-000000000000",
        "contract_id": "aircargo.shipment-status",
        "contract_version": "0.1.0",
        "contract_digest": "c" * 64,
        "source_id": "fixture-tms",
        "source_version": "0.1.0",
        "source_digest": _SOURCE_DIGEST,
        "policy_authority": "aircargo-policy",
        "policy_data_revision": "2026-08-01",
        "policy_digest": _POLICY_DIGEST,
    }


def test_postconditions_come_through_with_their_result() -> None:
    (postcondition,) = _journey()["postconditions"]

    assert postcondition["postcondition_id"] == "status-disclosed"
    assert postcondition["result"] == "satisfied"


# --- the shapes that are not the happy one ----------------------------------


def test_a_trace_that_ran_no_journey_is_empty_not_broken() -> None:
    view = evidence_view(
        _trace(steps=[{"order": 1, "node": "generate", "state": {}, "ts": _STEP_TS}])
    )

    assert view["journeys"] == []
    assert view["trace_id"] == "trace-abc123"


def test_a_bundle_without_a_source_or_a_policy_renders_the_rest() -> None:
    """Half a bundle is what an escalation looks like; it still has a contract."""
    bundle = _bundle(source_observation=None, policy=None, claim_links=[])

    journey = _journey(evidence=bundle)

    assert journey["observation"] is None
    assert journey["policy"] is None
    assert journey["claims"] == []
    assert journey["contract"]["contract_id"] == "aircargo.shipment-status"


def test_every_shadow_step_in_a_trace_gets_its_own_journey() -> None:
    step = _trace()["steps"][1]
    view = evidence_view(_trace(steps=[step, step]))

    assert len(view["journeys"]) == 2


@pytest.mark.parametrize(
    "trace",
    [
        {},
        {"steps": None},
        {"steps": "not a list"},
        {"steps": [None, 3, "step"]},
        {"steps": [{"node": SHADOW_NODE_NAME, "state": None, "ts": None}]},
        {"steps": [{"node": SHADOW_NODE_NAME, "state": {"evidence": "not a mapping"}}]},
    ],
)
def test_a_malformed_trace_never_raises(trace: dict[str, Any]) -> None:
    """The tab is a reader. A trace it cannot parse is a blank panel, not a 500."""
    view = evidence_view(trace)

    assert isinstance(view["journeys"], list)

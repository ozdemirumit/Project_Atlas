from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.modules.workflows.domain import (
    WorkflowProtectedResidentContextAccessAuthorizationClaim,
    WorkflowProtectedResidentContextAccessAuthorizationLease,
    WorkflowProtectedResidentContextAccessAuthorizationLeaseEffectiveState,
    WorkflowProtectedResidentContextAccessAuthorizationLeaseState,
    WorkflowProtectedResidentContextAccessAuthorizationPolicy,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResultState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_resident_context_access_authorization_policy,
    code_owned_workflow_protected_resident_context_access_authorization_policy_values,
    code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy,
)

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
DIGEST = "a" * 64
SUCCESS = (
    WorkflowProtectedTransportTargetContextCapsuleOpeningResultState
).OPENED_IN_PROTECTED_CONSUMER_BOUNDARY
OPERATIONAL_AUTHORITY_FIELDS = (
    "endpoint_resolution_authorized",
    "route_selection_authorized",
    "route_binding_authorized",
    "credential_selection_authorized",
    "credential_assignment_binding_authorized",
    "credential_access_authorized",
    "credential_brokerage_authorized",
    "credential_resolution_authorized",
    "protected_artifact_access_authorized",
    "credential_delivery_authorized",
    "network_access_authorized",
    "readiness_probe_authorized",
    "publication_authorized",
    "delivery_authorized",
    "dispatch_authorized",
    "execution_authorized",
    "infrastructure_mutation_authorized",
    "target_context_capsule_handoff_authorized",
    "target_context_capsule_opening_authorized",
)


def _payload(values: dict[str, object]) -> dict[str, object]:
    return {
        name: (
            value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, StrEnum)
            else value.canonical_value()
            if hasattr(value, "canonical_value")
            else value
        )
        for name, value in values.items()
        if name != "canonical_digest"
    }


def _claim_values() -> dict[str, object]:
    policy = code_owned_workflow_protected_resident_context_access_authorization_policy()
    return {
        "claim_id": "claim.resident-context-access.imp-216",
        "opening_id": "opening.imp-215",
        "opening_result_digest": DIGEST,
        "opening_attempt_id": "attempt.opening.imp-215",
        "opening_attempt_digest": "b" * 64,
        "opening_consumption_claim_id": "claim.opening.imp-215",
        "opening_consumption_claim_digest": "c" * 64,
        "opening_authorization_lease_id": "lease.opening.imp-214",
        "opening_authorization_lease_digest": "d" * 64,
        "opening_receipt_digest": "e" * 64,
        "opening_result_state": SUCCESS,
        "opening_completed_at": NOW - timedelta(seconds=1),
        "opening_deadline": NOW,
        "protected_resident_context_id": "resident-context.imp-215",
        "protected_resident_context_digest": "f" * 64,
        "protected_resident_context_created_at": NOW - timedelta(seconds=1),
        "protected_resident_context_usable_until": NOW + timedelta(seconds=10),
        "protected_resident_context_is_bearer_capability": False,
        "capsule_opened_in_protected_boundary": True,
        "target_context_pair_verified": True,
        "opening_outcome_known": True,
        "protected_source_closed": True,
        "source_capsule_zeroized": True,
        "scope": WorkflowScope("organization.test", "environment.test", "site.test"),
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "request_fingerprint": "1" * 64,
        "idempotency_digest": "2" * 64,
        "authorization_audit_digest": "3" * 64,
        "claimed_at": NOW,
        **{name: False for name in OPERATIONAL_AUTHORITY_FIELDS},
        "protected_resident_context_access_authority_granted": False,
    }


def _claim(**overrides: object) -> WorkflowProtectedResidentContextAccessAuthorizationClaim:
    values = {**_claim_values(), **overrides}
    return WorkflowProtectedResidentContextAccessAuthorizationClaim(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def _lease_values() -> dict[str, object]:
    claim = _claim()
    return {
        "authorization_lease_id": "lease.resident-context-access.imp-216",
        "claim_id": claim.claim_id,
        "claim_digest": claim.canonical_digest,
        "opening_id": claim.opening_id,
        "opening_result_digest": claim.opening_result_digest,
        "opening_attempt_id": claim.opening_attempt_id,
        "opening_attempt_digest": claim.opening_attempt_digest,
        "opening_consumption_claim_id": claim.opening_consumption_claim_id,
        "opening_consumption_claim_digest": claim.opening_consumption_claim_digest,
        "opening_authorization_lease_id": claim.opening_authorization_lease_id,
        "opening_authorization_lease_digest": claim.opening_authorization_lease_digest,
        "opening_receipt_digest": claim.opening_receipt_digest,
        "opening_result_state": claim.opening_result_state,
        "opening_completed_at": claim.opening_completed_at,
        "opening_deadline": claim.opening_deadline,
        "protected_resident_context_id": claim.protected_resident_context_id,
        "protected_resident_context_digest": claim.protected_resident_context_digest,
        "protected_resident_context_created_at": claim.protected_resident_context_created_at,
        "protected_resident_context_usable_until": (claim.protected_resident_context_usable_until),
        "protected_resident_context_is_bearer_capability": False,
        "capsule_opened_in_protected_boundary": True,
        "target_context_pair_verified": True,
        "opening_outcome_known": True,
        "protected_source_closed": True,
        "source_capsule_zeroized": True,
        "scope": claim.scope,
        "consumer_subject_id": claim.consumer_subject_id,
        "consumer_audience": claim.consumer_audience,
        "consumer_contract_id": claim.consumer_contract_id,
        "consumer_contract_version": claim.consumer_contract_version,
        "purpose_id": claim.purpose_id,
        "policy_id": claim.policy_id,
        "policy_version": claim.policy_version,
        "policy_digest": claim.policy_digest,
        "lifecycle_attestation_id": "attestation.resident-context.imp-216",
        "lifecycle_attestation_digest": "4" * 64,
        "lifecycle_attestation_valid_until": NOW + timedelta(seconds=2),
        "issued_at": NOW,
        "valid_until": NOW + timedelta(seconds=1),
        "effective_until": NOW + timedelta(seconds=1),
        "single_use": True,
        "renewable": False,
        "transferable": False,
        "lease_is_bearer_capability": False,
        "state": (
            WorkflowProtectedResidentContextAccessAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
        ),
        **{name: False for name in OPERATIONAL_AUTHORITY_FIELDS},
        "protected_resident_context_access_authority_granted": True,
    }


def _lease(**overrides: object) -> WorkflowProtectedResidentContextAccessAuthorizationLease:
    values = {**_lease_values(), **overrides}
    return WorkflowProtectedResidentContextAccessAuthorizationLease(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def test_policy_is_code_owned_and_matches_adr_165_consumer_contract() -> None:
    values = code_owned_workflow_protected_resident_context_access_authorization_policy_values()
    policy = code_owned_workflow_protected_resident_context_access_authorization_policy()
    opening_policy = (
        code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy()
    )

    assert policy.policy_id == "policy.workflow-protected-resident-context-access-authorization"
    assert policy.purpose_id == "purpose.workflow-protected-resident-context-access-evaluation"
    assert policy.maximum_lifetime_seconds == 1
    assert policy.single_use_required is True
    assert policy.renewable_allowed is False
    assert policy.transferable_allowed is False
    assert policy.bearer_capability_allowed is False
    assert (
        policy.consumer_subject_id,
        policy.consumer_audience,
        policy.consumer_contract_id,
        policy.consumer_contract_version,
    ) == (
        opening_policy.consumer_subject_id,
        opening_policy.consumer_audience,
        opening_policy.consumer_contract_id,
        opening_policy.consumer_contract_version,
    )
    assert policy.canonical_digest == canonical_digest(values)

    with pytest.raises(ValueError, match="not code-owned"):
        replace(policy, maximum_lifetime_seconds=2)
    with pytest.raises(ValueError, match="digest mismatch"):
        replace(policy, canonical_digest="9" * 64)
    with pytest.raises(FrozenInstanceError):
        policy.policy_id = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("claim_id", " bad"),
        ("opening_id", ""),
        ("consumer_subject_id", "service.wrong"),
        ("consumer_audience", "audience.wrong"),
        ("opening_result_digest", "A" * 64),
        ("request_fingerprint", "short"),
    ],
)
def test_claim_rejects_invalid_identities_and_digests(
    field_name: str, invalid_value: object
) -> None:
    with pytest.raises(ValueError):
        _claim(**{field_name: invalid_value})


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        (
            "opening_result_state",
            WorkflowProtectedTransportTargetContextCapsuleOpeningResultState.OPENING_FAILED,
        ),
        ("opening_completed_at", NOW),
        ("protected_resident_context_created_at", NOW - timedelta(seconds=2)),
        ("protected_resident_context_is_bearer_capability", True),
        ("capsule_opened_in_protected_boundary", False),
        ("target_context_pair_verified", False),
        ("opening_outcome_known", False),
        ("protected_source_closed", False),
        ("source_capsule_zeroized", False),
    ],
)
def test_claim_accepts_only_successful_adr_165_resident_context_source(
    field_name: str, invalid_value: object
) -> None:
    with pytest.raises(ValueError, match="source is ineligible"):
        _claim(**{field_name: invalid_value})


def test_claim_is_immutable_digest_bound_and_grants_no_authority() -> None:
    claim = _claim()
    authority_fields = [
        field.name
        for field in fields(claim)
        if field.name.endswith("_authorized")
        or field.name == "protected_resident_context_access_authority_granted"
    ]

    assert len(authority_fields) == 20
    assert all(getattr(claim, name) is False for name in authority_fields)
    with pytest.raises(ValueError, match="authority declaration"):
        _claim(protected_resident_context_access_authority_granted=True)
    with pytest.raises(ValueError, match="operational authority"):
        _claim(network_access_authorized=True)
    with pytest.raises(ValueError, match="digest mismatch"):
        replace(claim, canonical_digest="9" * 64)
    with pytest.raises(FrozenInstanceError):
        claim.claim_id = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("claimed_at", datetime(2026, 8, 16, 12, 0)),
        ("opening_completed_at", datetime(2026, 8, 16, 11, 59, 59)),
        ("opening_deadline", datetime(2026, 8, 16, 12, 0)),
        ("protected_resident_context_created_at", datetime(2026, 8, 16, 11, 59, 59)),
        ("protected_resident_context_usable_until", datetime(2026, 8, 16, 12, 0, 10)),
    ],
)
def test_claim_rejects_naive_times(field_name: str, invalid_value: object) -> None:
    with pytest.raises(ValueError):
        _claim(**{field_name: invalid_value})


def test_lease_is_single_use_non_bearer_and_grants_only_access_request_authority() -> None:
    lease = _lease()
    operational_fields = [
        field.name for field in fields(lease) if field.name.endswith("_authorized")
    ]

    assert lease.single_use is True
    assert lease.renewable is False
    assert lease.transferable is False
    assert lease.lease_is_bearer_capability is False
    assert lease.protected_resident_context_access_authority_granted is True
    assert len(operational_fields) == 19
    assert all(getattr(lease, name) is False for name in operational_fields)

    with pytest.raises(ValueError, match="operational authority"):
        _lease(execution_authorized=True)
    with pytest.raises(ValueError, match="authority declaration"):
        _lease(protected_resident_context_access_authority_granted=False)
    with pytest.raises(ValueError, match="lease is invalid"):
        _lease(renewable=True)


def test_lease_derives_at_most_one_second_effective_window_from_all_deadlines() -> None:
    lease = _lease()

    assert lease.effective_until - lease.issued_at == timedelta(seconds=1)
    with pytest.raises(ValueError, match="lease is invalid"):
        _lease(
            valid_until=NOW + timedelta(seconds=1, microseconds=1),
            effective_until=NOW + timedelta(seconds=1, microseconds=1),
        )

    shortened = _lease(
        lifecycle_attestation_valid_until=NOW + timedelta(milliseconds=400),
        valid_until=NOW + timedelta(milliseconds=400),
        effective_until=NOW + timedelta(milliseconds=400),
    )
    assert shortened.effective_until - shortened.issued_at == timedelta(milliseconds=400)


@pytest.mark.parametrize(
    "field_name",
    ["issued_at", "valid_until", "effective_until", "lifecycle_attestation_valid_until"],
)
def test_lease_rejects_naive_times(field_name: str) -> None:
    with pytest.raises(ValueError, match="time must be aware"):
        _lease(**{field_name: datetime(2026, 8, 16, 12, 0)})


def test_lease_effective_state_is_derived_without_mutation() -> None:
    lease = _lease()

    assert lease.effective_state(evaluated_at=NOW - timedelta(microseconds=1)) is (
        WorkflowProtectedResidentContextAccessAuthorizationLeaseEffectiveState.EXPIRED
    )
    assert lease.effective_state(evaluated_at=NOW) is (
        WorkflowProtectedResidentContextAccessAuthorizationLeaseEffectiveState.ACTIVE
    )
    assert lease.effective_state(evaluated_at=lease.valid_until) is (
        WorkflowProtectedResidentContextAccessAuthorizationLeaseEffectiveState.EXPIRED
    )
    assert lease.state is (
        WorkflowProtectedResidentContextAccessAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
    )
    with pytest.raises(ValueError, match="evaluation time must be aware"):
        lease.effective_state(evaluated_at=datetime(2026, 8, 16, 12, 0))
    with pytest.raises(FrozenInstanceError):
        lease.state = (  # type: ignore[misc]
            WorkflowProtectedResidentContextAccessAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
        )


def test_lease_rejects_invalid_identity_digest_and_canonical_digest() -> None:
    with pytest.raises(ValueError):
        _lease(authorization_lease_id=" bad")
    with pytest.raises(ValueError):
        _lease(claim_digest="short")
    with pytest.raises(ValueError, match="source is ineligible"):
        _lease(consumer_subject_id="service.wrong")

    lease = _lease()
    with pytest.raises(ValueError, match="digest mismatch"):
        replace(lease, canonical_digest="9" * 64)


def test_public_policy_type_is_constructible_only_from_code_owned_values() -> None:
    values = code_owned_workflow_protected_resident_context_access_authorization_policy_values()
    policy = WorkflowProtectedResidentContextAccessAuthorizationPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )

    assert policy == code_owned_workflow_protected_resident_context_access_authorization_policy()

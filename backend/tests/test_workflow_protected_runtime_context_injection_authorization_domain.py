from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.modules.workflows.domain import (
    WorkflowProtectedResidentContextAccessConsumptionResultState,
    WorkflowProtectedRuntimeContextInjectionAuthorizationClaim,
    WorkflowProtectedRuntimeContextInjectionAuthorizationLease,
    WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseState,
    WorkflowProtectedRuntimeContextInjectionAuthorizationPolicy,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_resident_context_access_consumption_policy,
    code_owned_workflow_protected_runtime_context_injection_authorization_policy,
    code_owned_workflow_protected_runtime_context_injection_authorization_policy_values,
)

NOW = datetime(2026, 8, 16, 23, 0, tzinfo=UTC)
SUCCESS = (
    WorkflowProtectedResidentContextAccessConsumptionResultState
).HANDLE_ESTABLISHED_IN_PROTECTED_BOUNDARY
PRIOR_AUTHORITY_FIELDS = (
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
    "protected_resident_context_access_authority_granted",
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
    policy = code_owned_workflow_protected_runtime_context_injection_authorization_policy()
    return {
        "claim_id": "claim.runtime-context-injection.imp-218",
        "access_result_id": "resident-context-access.imp-217",
        "access_result_digest": "1" * 64,
        "access_attempt_id": "resident-context-access-attempt.imp-217",
        "access_attempt_digest": "2" * 64,
        "access_consumption_claim_id": "resident-context-access-claim.imp-217",
        "access_consumption_claim_digest": "3" * 64,
        "access_authorization_lease_id": "resident-context-access-lease.imp-216",
        "access_authorization_lease_digest": "4" * 64,
        "accessor_receipt_digest": "5" * 64,
        "access_result_state": SUCCESS,
        "access_completed_at": NOW - timedelta(seconds=1),
        "access_result_recorded_at": NOW - timedelta(milliseconds=900),
        "access_deadline": NOW - timedelta(milliseconds=500),
        "protected_runtime_handle_id": "protected-runtime-context-handle.imp-217",
        "protected_runtime_handle_digest": "6" * 64,
        "protected_runtime_handle_created_at": NOW - timedelta(seconds=1),
        "protected_runtime_handle_usable_until": NOW + timedelta(seconds=5),
        "protected_runtime_handle_is_bearer_capability": False,
        "protected_resident_context_usable_until": NOW + timedelta(seconds=10),
        "protected_resident_context_consumed": True,
        "runtime_handle_established_in_protected_boundary": True,
        "access_outcome_known": True,
        "destination_boundary_id": policy.destination_boundary_id,
        "destination_deployment_id": policy.destination_deployment_id,
        "destination_generation": policy.destination_generation,
        "destination_fencing_token_digest": policy.destination_fencing_token_digest,
        "runtime_handle_profile_id": policy.runtime_handle_profile_id,
        "runtime_handle_profile_version": policy.runtime_handle_profile_version,
        "runtime_handle_profile_digest": policy.runtime_handle_profile_digest,
        "scope": WorkflowScope("organization.test", "environment.test", "site.test"),
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "request_fingerprint": "7" * 64,
        "idempotency_digest": "8" * 64,
        "authorization_audit_digest": "9" * 64,
        "claimed_at": NOW,
        **{name: False for name in PRIOR_AUTHORITY_FIELDS},
        "protected_runtime_context_injection_authority_granted": False,
    }


def _claim(
    **overrides: object,
) -> WorkflowProtectedRuntimeContextInjectionAuthorizationClaim:
    values = {**_claim_values(), **overrides}
    return WorkflowProtectedRuntimeContextInjectionAuthorizationClaim(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def _lease_values() -> dict[str, object]:
    policy = code_owned_workflow_protected_runtime_context_injection_authorization_policy()
    claim = _claim()
    source_fields = {
        field.name: getattr(claim, field.name)
        for field in fields(claim)
        if field.name
        not in {
            "claim_id",
            "request_fingerprint",
            "idempotency_digest",
            "authorization_audit_digest",
            "claimed_at",
            "canonical_digest",
            *PRIOR_AUTHORITY_FIELDS,
            "protected_runtime_context_injection_authority_granted",
        }
    }
    return {
        "authorization_lease_id": "lease.runtime-context-injection.imp-218",
        "claim_id": claim.claim_id,
        "claim_digest": claim.canonical_digest,
        **source_fields,
        "lifecycle_attestation_id": "attestation.runtime-handle.imp-218",
        "lifecycle_attestation_digest": "a" * 64,
        "lifecycle_attestation_valid_until": NOW + timedelta(seconds=2),
        "injector_contract_id": policy.required_injector_contract_id,
        "injector_contract_version": policy.required_injector_contract_version,
        "injector_id": policy.approved_injector_id,
        "injector_version": policy.approved_injector_version,
        "runtime_slot_profile_id": policy.runtime_slot_profile_id,
        "runtime_slot_profile_version": policy.runtime_slot_profile_version,
        "runtime_slot_profile_digest": policy.runtime_slot_profile_digest,
        "issued_at": NOW,
        "valid_until": NOW + timedelta(seconds=1),
        "effective_until": NOW + timedelta(seconds=1),
        "single_use": True,
        "renewable": False,
        "transferable": False,
        "lease_is_bearer_capability": False,
        "state": (
            WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
        ),
        **{name: False for name in PRIOR_AUTHORITY_FIELDS},
        "protected_runtime_context_injection_authority_granted": True,
    }


def _lease(
    **overrides: object,
) -> WorkflowProtectedRuntimeContextInjectionAuthorizationLease:
    values = {**_lease_values(), **overrides}
    return WorkflowProtectedRuntimeContextInjectionAuthorizationLease(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def test_policy_is_code_owned_and_derives_exact_adr_167_boundary() -> None:
    values = code_owned_workflow_protected_runtime_context_injection_authorization_policy_values()
    policy = code_owned_workflow_protected_runtime_context_injection_authorization_policy()
    access_policy = code_owned_workflow_protected_resident_context_access_consumption_policy()

    assert policy.policy_id == ("policy.workflow-protected-runtime-context-injection-authorization")
    assert policy.policy_version == "1.0"
    assert policy.required_access_result_state == SUCCESS.value
    assert policy.maximum_lifetime_seconds == 1
    assert policy.single_use_required is True
    assert policy.renewable_allowed is False
    assert policy.transferable_allowed is False
    assert policy.bearer_capability_allowed is False
    assert policy.consumer_subject_id == (
        "service.workflow-protected-transport-target-context-capsule-consumer"
    )
    assert policy.runtime_handle_profile_digest == access_policy.runtime_handle_profile_digest
    assert policy.canonical_digest == canonical_digest(values)

    with pytest.raises(ValueError, match="not code-owned"):
        replace(policy, maximum_lifetime_seconds=2)
    with pytest.raises(ValueError, match="digest mismatch"):
        replace(policy, canonical_digest="f" * 64)
    with pytest.raises(FrozenInstanceError):
        policy.policy_id = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        (
            "access_result_state",
            WorkflowProtectedResidentContextAccessConsumptionResultState.RESIDENT_CONTEXT_ACCESS_FAILED,
        ),
        ("protected_runtime_handle_created_at", NOW - timedelta(seconds=2)),
        ("protected_runtime_handle_is_bearer_capability", True),
        ("protected_resident_context_consumed", False),
        ("runtime_handle_established_in_protected_boundary", False),
        ("access_outcome_known", False),
        ("destination_generation", 999),
        ("runtime_handle_profile_digest", "b" * 64),
    ],
)
def test_claim_accepts_only_canonical_adr_167_handle_success(
    field_name: str, invalid_value: object
) -> None:
    with pytest.raises(ValueError, match="source is ineligible"):
        _claim(**{field_name: invalid_value})


def test_claim_is_immutable_digest_bound_and_grants_no_authority() -> None:
    claim = _claim()
    authority_fields = [
        field.name
        for field in fields(claim)
        if field.name.endswith("_authorized") or field.name.endswith("_authority_granted")
    ]

    assert len(authority_fields) == 21
    assert all(getattr(claim, name) is False for name in authority_fields)
    with pytest.raises(ValueError, match="prior authority"):
        _claim(protected_resident_context_access_authority_granted=True)
    with pytest.raises(ValueError, match="authority declaration"):
        _claim(protected_runtime_context_injection_authority_granted=True)
    with pytest.raises(ValueError, match="digest mismatch"):
        replace(claim, canonical_digest="f" * 64)


def test_lease_is_bounded_single_use_non_bearer_and_grants_only_injection_request() -> None:
    lease = _lease()

    assert lease.single_use is True
    assert lease.renewable is False
    assert lease.transferable is False
    assert lease.lease_is_bearer_capability is False
    assert lease.valid_until - lease.issued_at == timedelta(seconds=1)
    assert all(getattr(lease, name) is False for name in PRIOR_AUTHORITY_FIELDS)
    assert lease.protected_runtime_context_injection_authority_granted is True
    assert lease.is_active(evaluated_at=NOW) is True
    assert lease.is_active(evaluated_at=NOW, consumed=True) is False
    assert lease.is_active(evaluated_at=lease.valid_until) is False

    with pytest.raises(ValueError, match="lease is invalid"):
        _lease(
            valid_until=NOW + timedelta(seconds=1, microseconds=1),
            effective_until=NOW + timedelta(seconds=1, microseconds=1),
        )
    with pytest.raises(ValueError, match="prior authority"):
        _lease(network_access_authorized=True)
    with pytest.raises(ValueError, match="authority declaration"):
        _lease(protected_runtime_context_injection_authority_granted=False)
    with pytest.raises(ValueError, match="lease is invalid"):
        _lease(runtime_slot_profile_digest="c" * 64)
    with pytest.raises(ValueError, match="evaluation time must be aware"):
        lease.is_active(evaluated_at=datetime(2026, 8, 16, 23, 0))


def test_public_policy_type_accepts_only_code_owned_values() -> None:
    values = code_owned_workflow_protected_runtime_context_injection_authorization_policy_values()
    policy = WorkflowProtectedRuntimeContextInjectionAuthorizationPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )

    assert policy == code_owned_workflow_protected_runtime_context_injection_authorization_policy()

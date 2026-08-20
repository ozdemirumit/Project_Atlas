from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from typing import Any, cast

from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_process_creation_authorization_domain import (
    WorkflowProtectedRuntimeProcessCreationAuthorizationAuthority,
    WorkflowProtectedRuntimeProcessCreationAuthorizationClaim,
    WorkflowProtectedRuntimeProcessCreationAuthorizationLease,
    WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_process_creation_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_process_creation_consumption_domain import (
    WorkflowProtectedRuntimeProcessCreationInstruction,
    code_owned_workflow_protected_runtime_process_creation_consumption_policy,
)
from atlas.modules.workflows.domain.protected_runtime_readiness_consumption_domain import (
    WorkflowProtectedRuntimeReadinessConsumptionResultState,
    code_owned_workflow_protected_runtime_readiness_consumption_policy,
)

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
SCOPE = WorkflowScope(
    organization_id="organization.test",
    environment_id="environment.test",
    site_id="site.test",
)


def digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def canonical_mapping(values: dict[str, object]) -> dict[str, object]:
    return {name: canonical_value(value) for name, value in values.items()}


def canonical_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "canonical_value"):
        return value.canonical_value()
    return value


def authorization_source() -> tuple[
    WorkflowProtectedRuntimeProcessCreationAuthorizationClaim,
    WorkflowProtectedRuntimeProcessCreationAuthorizationLease,
]:
    policy = code_owned_workflow_protected_runtime_process_creation_authorization_policy()
    readiness = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    completed_at = NOW - timedelta(seconds=1)
    source: dict[str, object] = {
        "readiness_result_id": "readiness-result.test",
        "readiness_result_digest": digest("readiness-result"),
        "readiness_consumption_id": "readiness-consumption.test",
        "readiness_attempt_id": "readiness-attempt.test",
        "readiness_attempt_digest": digest("readiness-attempt"),
        "readiness_claim_id": "readiness-claim.test",
        "readiness_claim_digest": digest("readiness-claim"),
        "readiness_authorization_lease_id": "readiness-lease.test",
        "readiness_authorization_lease_digest": digest("readiness-lease"),
        "start_result_id": "start-result.test",
        "start_result_digest": digest("start-result"),
        "assessor_receipt_digest": digest("assessor-receipt"),
        "readiness_result_state": (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READY_IN_PROTECTED_BOUNDARY,
        "readiness_failure_class": None,
        "readiness_outcome_known": True,
        "readiness_assessment_performed": True,
        "runtime_ready": True,
        "readiness_completed_at": completed_at,
        "readiness_result_recorded_at": completed_at + timedelta(milliseconds=25),
        "readiness_profile_id": readiness.readiness_profile_id,
        "readiness_profile_version": readiness.readiness_profile_version,
        "readiness_profile_digest": readiness.readiness_profile_digest,
        "destination_deployment_id": "deployment.test",
        "destination_generation": 2,
        "destination_fencing_token_digest": digest("destination-fence"),
        "protected_slot_commitment": digest("protected-slot"),
        "protected_slot_generation": 3,
        "runtime_envelope_id": "runtime-envelope.test",
        "runtime_envelope_commitment": digest("runtime-envelope"),
        "runtime_envelope_generation": 3,
        "scope": SCOPE,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
    }
    claim_values = {
        "claim_id": "process-creation-authorization-claim.test",
        **source,
        "request_fingerprint": digest("authorization-request"),
        "idempotency_digest": digest("authorization-idempotency"),
        "authorization_audit_digest": digest("authorization-audit"),
        "claimed_at": completed_at + timedelta(milliseconds=50),
        "authority": WorkflowProtectedRuntimeProcessCreationAuthorizationAuthority(),
    }
    claim = WorkflowProtectedRuntimeProcessCreationAuthorizationClaim(
        **cast(Any, claim_values),
        canonical_digest=canonical_digest(canonical_mapping(claim_values)),
    )
    issued_at = NOW - timedelta(milliseconds=50)
    lease_values = {
        "authorization_lease_id": "process-creation-authorization-lease.test",
        "claim_id": claim.claim_id,
        "claim_digest": claim.canonical_digest,
        **source,
        "lifecycle_attestation_id": "lifecycle-attestation.test",
        "lifecycle_attestation_digest": digest("lifecycle-attestation"),
        "lifecycle_attestation_valid_until": NOW + timedelta(milliseconds=900),
        "runtime_envelope_eligible_until": NOW + timedelta(milliseconds=900),
        "attestation_metadata_only": True,
        "runtime_started": True,
        "process_created": False,
        "process_scheduled": False,
        "process_creation_profile_id": policy.process_creation_profile_id,
        "process_creation_profile_version": policy.process_creation_profile_version,
        "process_creation_profile_digest": policy.process_creation_profile_digest,
        "issued_at": issued_at,
        "valid_until": NOW + timedelta(milliseconds=900),
        "effective_until": NOW + timedelta(milliseconds=900),
        "single_use": True,
        "renewable": False,
        "transferable": False,
        "lease_is_bearer_capability": False,
        "state": (
            WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseState
        ).AUTHORIZED_UNCONSUMED,
        "authority": WorkflowProtectedRuntimeProcessCreationAuthorizationAuthority(
            protected_runtime_process_creation_authority_granted=True
        ),
    }
    lease = WorkflowProtectedRuntimeProcessCreationAuthorizationLease(
        **cast(Any, lease_values),
        canonical_digest=canonical_digest(canonical_mapping(lease_values)),
    )
    return claim, lease


def instruction() -> WorkflowProtectedRuntimeProcessCreationInstruction:
    policy = code_owned_workflow_protected_runtime_process_creation_consumption_policy()
    values: dict[str, object] = {
        "consumption_id": "process-creation-consumption.test",
        "attempt_id": "process-creation-attempt.test",
        "attempt_digest": digest("attempt"),
        "claim_id": "process-creation-claim.test",
        "claim_digest": digest("claim"),
        "authorization_lease_id": "process-creation-authorization-lease.test",
        "authorization_lease_digest": digest("authorization-lease"),
        "protected_operation_reference": "protected-operation.test",
        "runtime_envelope_id": "runtime-envelope.test",
        "runtime_envelope_commitment": digest("runtime-envelope"),
        "runtime_envelope_generation": 3,
        "process_creation_profile_id": policy.process_creation_profile_id,
        "process_creation_profile_version": policy.process_creation_profile_version,
        "process_creation_profile_digest": policy.process_creation_profile_digest,
        "primitive_id": policy.primitive_id,
        "primitive_version": policy.primitive_version,
        "primitive_digest": policy.primitive_digest,
        "creator_contract_id": policy.creator_contract_id,
        "creator_contract_version": policy.creator_contract_version,
        "creator_id": policy.approved_creator_id,
        "creator_version": policy.approved_creator_version,
        "request_nonce_digest": digest("nonce"),
        "scope": SCOPE,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "started_at": NOW - timedelta(milliseconds=100),
        "invocation_deadline": NOW + timedelta(milliseconds=800),
    }
    return WorkflowProtectedRuntimeProcessCreationInstruction(
        **cast(Any, values), canonical_digest=canonical_digest(canonical_mapping(values))
    )

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.modules.workflows.application.protected_runtime_context_use_ports import (
    WorkflowProtectedRuntimeContextUseClaimRequest,
    WorkflowProtectedRuntimeContextUseClaimStatus,
    WorkflowProtectedRuntimeContextUseClaimWrite,
    WorkflowProtectedRuntimeContextUseEligibilityAttestation,
    WorkflowProtectedRuntimeContextUseEligibilityAttestationRequest,
    WorkflowProtectedRuntimeContextUseError,
    WorkflowProtectedRuntimeContextUseReplayLookup,
    WorkflowProtectedRuntimeContextUseReplayLookupRequest,
    WorkflowProtectedRuntimeContextUseReplayStatus,
    WorkflowProtectedRuntimeContextUseResultRequest,
    WorkflowProtectedRuntimeContextUseResultWrite,
    WorkflowProtectedRuntimeContextUseResultWriteStatus,
    WorkflowProtectedRuntimeContextUseSource,
    build_workflow_protected_runtime_context_use_instruction,
    validate_workflow_protected_runtime_context_use_claim_request,
)
from atlas.modules.workflows.application.protected_runtime_context_uses import (
    WorkflowProtectedRuntimeContextUsePresentation,
    WorkflowProtectedRuntimeContextUseService,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_context_use_authorization_consumption_domain import (  # noqa: E501
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthority,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaim,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResult,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionState,
    code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy,
)
from atlas.modules.workflows.domain.protected_runtime_context_use_authorization_domain import (
    WorkflowProtectedRuntimeContextUseAuthorizationLeaseState,
)
from atlas.modules.workflows.domain.protected_runtime_context_use_domain import (
    WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNATURE_ALGORITHM,
    WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNING_KEY_ID,
    WorkflowProtectedRuntimeContextUseAttempt,
    WorkflowProtectedRuntimeContextUseAttemptState,
    WorkflowProtectedRuntimeContextUseAuthority,
    WorkflowProtectedRuntimeContextUseClaim,
    WorkflowProtectedRuntimeContextUseReceipt,
    WorkflowProtectedRuntimeContextUseResult,
    WorkflowProtectedRuntimeContextUseResultState,
    code_owned_workflow_protected_runtime_context_use_policy,
)

NOW = datetime(2026, 8, 17, 13, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.test", "environment.test", "site.test")


def _canonical_mapping(values: dict[str, object]) -> dict[str, object]:
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
    }


def _source_claim() -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaim:
    source_policy = (
        code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy()
    )
    use_policy = code_owned_workflow_protected_runtime_context_use_policy()
    values: dict[str, object] = {
        "consumption_claim_id": "use-authorization-consumption-claim.imp-221",
        "consumption_id": "use-authorization-consumption.imp-221",
        "authorization_lease_id": "use-authorization-lease.imp-220",
        "authorization_lease_digest": "1" * 64,
        "authorization_claim_id": "use-authorization-claim.imp-220",
        "authorization_claim_digest": "2" * 64,
        "injection_result_id": "injection-result.imp-219",
        "injection_result_digest": "3" * 64,
        "destination_deployment_id": "deployment.imp-222",
        "destination_generation": 7,
        "destination_fencing_token_digest": "4" * 64,
        "runtime_slot_commitment": "5" * 64,
        "runtime_slot_post_generation": 11,
        "injected_context_usable_until": NOW + timedelta(seconds=2),
        "use_profile_id": use_policy.use_profile_id,
        "use_profile_version": use_policy.use_profile_version,
        "use_profile_digest": use_policy.use_profile_digest,
        "source_lease_state": (
            WorkflowProtectedRuntimeContextUseAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
        ),
        "source_lease_issued_at": NOW - timedelta(milliseconds=200),
        "source_lease_valid_until": NOW + timedelta(seconds=1),
        "source_lease_effective_until": NOW + timedelta(seconds=1),
        "scope": SCOPE,
        "consumer_subject_id": source_policy.consumer_subject_id,
        "consumer_audience": source_policy.consumer_audience,
        "consumer_contract_id": source_policy.consumer_contract_id,
        "consumer_contract_version": source_policy.consumer_contract_version,
        "purpose_id": source_policy.purpose_id,
        "policy_id": source_policy.policy_id,
        "policy_version": source_policy.policy_version,
        "policy_digest": source_policy.canonical_digest,
        "source_policy_id": source_policy.source_policy_id,
        "source_policy_version": source_policy.source_policy_version,
        "source_policy_digest": source_policy.source_policy_digest,
        "idempotency_digest": "6" * 64,
        "request_fingerprint": "7" * 64,
        "irreversible_consumption_acknowledged": True,
        "consumption_audit_digest": "8" * 64,
        "claimed_at": NOW,
        "authority": WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthority(),
    }
    return WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaim(
        **cast(Any, values), canonical_digest=canonical_digest(_canonical_mapping(values))
    )


def _source_result(
    claim: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaim,
) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResult:
    values: dict[str, object] = {
        "result_id": "use-authorization-consumption-result.imp-221",
        "consumption_id": claim.consumption_id,
        "consumption_claim_id": claim.consumption_claim_id,
        "consumption_claim_digest": claim.canonical_digest,
        "authorization_lease_id": claim.authorization_lease_id,
        "authorization_lease_digest": claim.authorization_lease_digest,
        "scope": claim.scope,
        "consumer_subject_id": claim.consumer_subject_id,
        "consumer_audience": claim.consumer_audience,
        "consumer_contract_id": claim.consumer_contract_id,
        "consumer_contract_version": claim.consumer_contract_version,
        "purpose_id": claim.purpose_id,
        "policy_id": claim.policy_id,
        "policy_version": claim.policy_version,
        "policy_digest": claim.policy_digest,
        "source_policy_id": claim.source_policy_id,
        "source_policy_version": claim.source_policy_version,
        "source_policy_digest": claim.source_policy_digest,
        "state": (
            WorkflowProtectedRuntimeContextUseAuthorizationConsumptionState.AUTHORIZATION_CONSUMED_WITHOUT_RUNTIME_USE
        ),
        "consumed_at": claim.claimed_at,
        "recorded_at": claim.claimed_at,
        "authorization_lease_consumed": True,
        "historical_result_only": True,
        "context_accessed": False,
        "context_used": False,
        "runtime_started": False,
        "runtime_resumed": False,
        "network_activity_performed": False,
        "connector_activity_performed": False,
        "readiness_probe_performed": False,
        "publication_performed": False,
        "delivery_performed": False,
        "dispatch_performed": False,
        "execution_performed": False,
        "infrastructure_mutation_performed": False,
        "renewal_created": False,
        "transfer_created": False,
        "replacement_created": False,
        "retry_created": False,
        "authority": WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthority(),
    }
    return WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResult(
        **cast(Any, values), canonical_digest=canonical_digest(_canonical_mapping(values))
    )


def _source() -> WorkflowProtectedRuntimeContextUseSource:
    claim = _source_claim()
    return WorkflowProtectedRuntimeContextUseSource(claim, _source_result(claim))


def _context() -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext:
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
        subject_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        actor_type="service",
        authentication_method="workload_token",
        credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
        scope=SCOPE,
        correlation_id="correlation.imp-222",
        decision_id="decision.imp-222",
        requested_at=NOW,
    )


class _SignatureVerifier:
    def __init__(self, *, valid: bool = True) -> None:
        self.valid = valid

    def verify_context_use_eligibility_attestation(
        self, attestation: WorkflowProtectedRuntimeContextUseEligibilityAttestation
    ) -> bool:
        del attestation
        return self.valid

    def verify_receipt(self, receipt: WorkflowProtectedRuntimeContextUseReceipt) -> bool:
        del receipt
        return self.valid


class _InstructionSigner:
    @property
    def available(self) -> bool:
        return True

    @property
    def signing_key_id(self) -> str:
        return WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNING_KEY_ID

    @property
    def signature_algorithm(self) -> str:
        return WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNATURE_ALGORITHM

    def sign_instruction_envelope_digest(self, payload_digest: str) -> str:
        return canonical_digest({"payload_digest": payload_digest, "test_key": "imp-222"})


class _InstructionSignatureVerifier:
    def __init__(self, *, valid: bool = True) -> None:
        self.valid = valid

    def verify_instruction_envelope(self, envelope: Any) -> bool:
        expected = canonical_digest(
            {
                "payload_digest": canonical_digest(envelope.signature_payload()),
                "test_key": "imp-222",
            }
        )
        return self.valid and envelope.integrity_signature == expected


class _Attestor:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.calls: list[WorkflowProtectedRuntimeContextUseEligibilityAttestationRequest] = []

    @property
    def available(self) -> bool:
        return True

    async def attest_context_use_eligibility(
        self, request: WorkflowProtectedRuntimeContextUseEligibilityAttestationRequest
    ) -> WorkflowProtectedRuntimeContextUseEligibilityAttestation:
        self.events.append("attest")
        self.calls.append(request)
        policy = code_owned_workflow_protected_runtime_context_use_policy()
        values: dict[str, object] = {
            field.name: getattr(request, field.name)
            for field in fields(request)
            if field.name not in {"requested_at"}
        }
        values.update(
            {
                "attestation_id": "use-eligibility-attestation.imp-222",
                "attestor_id": policy.required_attestor_id,
                "attestor_version": policy.required_attestor_version,
                "signing_key_id": policy.attestation_verification_signing_key_id,
                "signature_algorithm": "hmac-sha256",
                "observed_at": request.requested_at,
                "valid_until": request.requested_at + timedelta(milliseconds=800),
                "context_present": True,
                "context_inert": True,
                "context_unexpired": True,
                "context_unrevoked": True,
                "context_uncleared": True,
                "context_unsuperseded": True,
                "context_unused": True,
                "use_count": 0,
                "competing_use_absent": True,
                "destination_generation_current": True,
                "destination_fence_current": True,
                "runtime_slot_generation_current": True,
                "use_profile_eligible": True,
                "executor_profile_eligible": True,
                "atomic_compare_and_swap_supported": True,
                "raw_context_included": False,
                "runtime_handle_included": False,
                "runtime_slot_locator_included": False,
                "endpoint_included": False,
                "credential_included": False,
                "secret_included": False,
                "bearer_token_included": False,
                "runtime_start_authorized": False,
                "runtime_resume_authorized": False,
                "process_creation_authorized": False,
                "prompt_construction_authorized": False,
                "model_inference_authorized": False,
                "connector_activity_authorized": False,
                "network_activity_authorized": False,
                "dispatch_authorized": False,
                "execution_authorized": False,
                "infrastructure_mutation_authorized": False,
                "integrity_signature": "a" * 64,
            }
        )
        return WorkflowProtectedRuntimeContextUseEligibilityAttestation(
            **cast(Any, values), canonical_digest=canonical_digest(_canonical_mapping(values))
        )


class _TrustedUser:
    def __init__(self, events: list[str], *, fail: bool = False) -> None:
        self.events = events
        self.fail = fail
        self.attempt: WorkflowProtectedRuntimeContextUseAttempt | None = None
        self.calls = 0

    @property
    def available(self) -> bool:
        return True

    @property
    def executor_contract_id(self) -> str:
        return (
            code_owned_workflow_protected_runtime_context_use_policy().required_executor_contract_id
        )

    @property
    def executor_contract_version(self) -> str:
        policy = code_owned_workflow_protected_runtime_context_use_policy()
        return policy.required_executor_contract_version

    @property
    def executor_id(self) -> str:
        return code_owned_workflow_protected_runtime_context_use_policy().approved_executor_id

    @property
    def executor_version(self) -> str:
        return code_owned_workflow_protected_runtime_context_use_policy().approved_executor_version

    @property
    def use_profile_id(self) -> str:
        return code_owned_workflow_protected_runtime_context_use_policy().use_profile_id

    @property
    def use_profile_version(self) -> str:
        return code_owned_workflow_protected_runtime_context_use_policy().use_profile_version

    @property
    def use_profile_digest(self) -> str:
        return code_owned_workflow_protected_runtime_context_use_policy().use_profile_digest

    async def use_context(self, invocation: Any) -> WorkflowProtectedRuntimeContextUseReceipt:
        self.events.append("executor")
        self.calls += 1
        if self.fail:
            raise WorkflowProtectedRuntimeContextUseError("simulated_executor_failure")
        assert self.attempt is not None
        instruction = build_workflow_protected_runtime_context_use_instruction(self.attempt)
        assert invocation.instruction_digest == instruction.canonical_digest
        assert invocation.signed_instruction_envelope.instruction == instruction
        assert invocation.signed_instruction_envelope.signing_key_id == (
            WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNING_KEY_ID
        )
        values: dict[str, object] = {
            "instruction_digest": instruction.canonical_digest,
            "protected_operation_reference": instruction.protected_operation_reference,
            "authorization_consumption_result_id": instruction.authorization_consumption_result_id,
            "authorization_consumption_result_digest": (
                instruction.authorization_consumption_result_digest
            ),
            "destination_deployment_id": instruction.destination_deployment_id,
            "destination_generation": instruction.destination_generation,
            "destination_fencing_token_digest": instruction.destination_fencing_token_digest,
            "runtime_slot_commitment": instruction.runtime_slot_commitment,
            "runtime_slot_pre_generation": instruction.runtime_slot_pre_generation,
            "runtime_slot_post_generation": instruction.expected_runtime_slot_post_generation,
            "use_count_pre": 0,
            "use_count_post": 1,
            "use_profile_id": instruction.use_profile_id,
            "use_profile_version": instruction.use_profile_version,
            "use_profile_digest": instruction.use_profile_digest,
            "executor_contract_id": instruction.executor_contract_id,
            "executor_contract_version": instruction.executor_contract_version,
            "executor_id": instruction.executor_id,
            "executor_version": instruction.executor_version,
            "state": (
                WorkflowProtectedRuntimeContextUseResultState
            ).CONTEXT_USED_ONCE_IN_PROTECTED_BOUNDARY,
            "failure_class": None,
            "context_adopted": True,
            "protected_runtime_context_use_performed": True,
            "context_terminal_non_reusable": True,
            "transient_material_zeroized": True,
            "context_disclosed": False,
            "runtime_started": False,
            "runtime_resumed": False,
            "process_created": False,
            "prompt_constructed": False,
            "model_inference_performed": False,
            "model_output_created": False,
            "filesystem_activity_performed": False,
            "provider_activity_performed": False,
            "connector_activity_performed": False,
            "network_activity_performed": False,
            "readiness_probe_performed": False,
            "publication_performed": False,
            "delivery_performed": False,
            "dispatch_performed": False,
            "execution_performed": False,
            "infrastructure_mutation_performed": False,
            "completed_at": instruction.started_at + timedelta(milliseconds=100),
            "use_deadline": instruction.use_deadline,
            "attested_by": instruction.executor_id,
            "signing_key_id": (
                code_owned_workflow_protected_runtime_context_use_policy()
            ).receipt_verification_signing_key_id,
            "signature_algorithm": "hmac-sha256",
            "integrity_signature": "b" * 64,
        }
        return WorkflowProtectedRuntimeContextUseReceipt(
            **cast(Any, values), canonical_digest=canonical_digest(_canonical_mapping(values))
        )


class _Repository:
    def __init__(self, trusted_user: _TrustedUser, events: list[str]) -> None:
        self.durable = True
        self.trusted_user = trusted_user
        self.events = events
        self.source = _source()
        self.attempt: WorkflowProtectedRuntimeContextUseAttempt | None = None
        self.result: WorkflowProtectedRuntimeContextUseResult | None = None
        self.time_calls = 0

    async def get_authoritative_time(self) -> datetime:
        self.events.append("time")
        self.time_calls += 1
        return NOW + timedelta(milliseconds=200 * (self.time_calls - 1))

    async def lookup_protected_runtime_context_use_replay(
        self, request: WorkflowProtectedRuntimeContextUseReplayLookupRequest
    ) -> WorkflowProtectedRuntimeContextUseReplayLookup:
        self.events.append("replay")
        del request
        if self.attempt is not None and self.result is not None:
            return WorkflowProtectedRuntimeContextUseReplayLookup(
                WorkflowProtectedRuntimeContextUseReplayStatus.TERMINAL,
                self.attempt,
                self.result,
            )
        if self.attempt is not None:
            return WorkflowProtectedRuntimeContextUseReplayLookup(
                WorkflowProtectedRuntimeContextUseReplayStatus.CLAIM_ONLY_UNCERTAIN,
                self.attempt,
                None,
            )
        return WorkflowProtectedRuntimeContextUseReplayLookup(
            WorkflowProtectedRuntimeContextUseReplayStatus.NONE
        )

    async def get_protected_runtime_context_use_source(
        self, *, authorization_consumption_result_id: str
    ) -> WorkflowProtectedRuntimeContextUseSource | None:
        self.events.append("source")
        return (
            self.source
            if authorization_consumption_result_id
            == self.source.authorization_consumption_result.result_id
            else None
        )

    async def claim_protected_runtime_context_use(
        self, request: WorkflowProtectedRuntimeContextUseClaimRequest
    ) -> WorkflowProtectedRuntimeContextUseClaimWrite:
        self.events.append("claim")
        validate_workflow_protected_runtime_context_use_claim_request(request)
        policy = code_owned_workflow_protected_runtime_context_use_policy()
        source_claim = request.source.authorization_consumption_claim
        source_result = request.source.authorization_consumption_result
        attestation = request.eligibility_attestation
        claim_values: dict[str, object] = {
            "claim_id": request.claim_id,
            "use_id": request.use_id,
            "attempt_id": request.attempt_id,
            "authorization_consumption_result_id": source_result.result_id,
            "authorization_consumption_result_digest": source_result.canonical_digest,
            "authorization_consumption_claim_id": source_claim.consumption_claim_id,
            "authorization_consumption_claim_digest": source_claim.canonical_digest,
            "authorization_lease_id": source_claim.authorization_lease_id,
            "authorization_lease_digest": source_claim.authorization_lease_digest,
            "injection_result_id": source_claim.injection_result_id,
            "injection_result_digest": source_claim.injection_result_digest,
            "destination_deployment_id": source_claim.destination_deployment_id,
            "destination_generation": source_claim.destination_generation,
            "destination_fencing_token_digest": source_claim.destination_fencing_token_digest,
            "runtime_slot_commitment": source_claim.runtime_slot_commitment,
            "runtime_slot_pre_generation": source_claim.runtime_slot_post_generation,
            "injected_context_usable_until": source_claim.injected_context_usable_until,
            "use_profile_id": request.expected_use_profile_id,
            "use_profile_version": request.expected_use_profile_version,
            "use_profile_digest": request.expected_use_profile_digest,
            "scope": request.scope,
            "consumer_subject_id": request.consumer_subject_id,
            "consumer_audience": request.consumer_audience,
            "consumer_contract_id": policy.consumer_contract_id,
            "consumer_contract_version": policy.consumer_contract_version,
            "purpose_id": policy.purpose_id,
            "policy_id": request.expected_policy_id,
            "policy_version": request.expected_policy_version,
            "policy_digest": request.expected_policy_digest,
            "idempotency_digest": request.idempotency_digest,
            "request_fingerprint": request.request_fingerprint,
            "use_authorization_audit_digest": request.use_authorization_audit_digest,
            "irreversible_use_acknowledged": True,
            "uncertainty_no_retry_acknowledged": True,
            "claimed_at": NOW,
            "authority": WorkflowProtectedRuntimeContextUseAuthority(),
        }
        claim = WorkflowProtectedRuntimeContextUseClaim(
            **cast(Any, claim_values),
            canonical_digest=canonical_digest(_canonical_mapping(claim_values)),
        )
        attempt_values: dict[str, object] = {
            "attempt_id": request.attempt_id,
            "use_id": request.use_id,
            "claim_id": request.claim_id,
            "claim_digest": claim.canonical_digest,
            "authorization_consumption_result_id": source_result.result_id,
            "authorization_consumption_result_digest": source_result.canonical_digest,
            "authorization_consumption_claim_id": source_claim.consumption_claim_id,
            "authorization_consumption_claim_digest": source_claim.canonical_digest,
            "authorization_lease_id": source_claim.authorization_lease_id,
            "authorization_lease_digest": source_claim.authorization_lease_digest,
            "injection_result_id": source_claim.injection_result_id,
            "injection_result_digest": source_claim.injection_result_digest,
            "protected_operation_reference": "protected-operation.imp-222",
            "destination_deployment_id": source_claim.destination_deployment_id,
            "destination_generation": source_claim.destination_generation,
            "destination_fencing_token_digest": source_claim.destination_fencing_token_digest,
            "runtime_slot_commitment": source_claim.runtime_slot_commitment,
            "runtime_slot_pre_generation": source_claim.runtime_slot_post_generation,
            "expected_runtime_slot_post_generation": source_claim.runtime_slot_post_generation + 1,
            "expected_use_count_pre": 0,
            "expected_use_count_post": 1,
            "injected_context_usable_until": source_claim.injected_context_usable_until,
            "use_profile_id": request.expected_use_profile_id,
            "use_profile_version": request.expected_use_profile_version,
            "use_profile_digest": request.expected_use_profile_digest,
            "required_executor_contract_id": request.expected_executor_contract_id,
            "required_executor_contract_version": request.expected_executor_contract_version,
            "approved_executor_id": request.expected_executor_id,
            "approved_executor_version": request.expected_executor_version,
            "receipt_verification_signing_key_id": (
                request.expected_receipt_verification_signing_key_id
            ),
            "eligibility_attestation_id": attestation.attestation_id,
            "eligibility_attestation_digest": attestation.canonical_digest,
            "request_nonce_digest": request.expected_request_nonce_digest,
            "scope": request.scope,
            "consumer_subject_id": request.consumer_subject_id,
            "consumer_audience": request.consumer_audience,
            "consumer_contract_id": policy.consumer_contract_id,
            "consumer_contract_version": policy.consumer_contract_version,
            "purpose_id": policy.purpose_id,
            "policy_id": request.expected_policy_id,
            "policy_version": request.expected_policy_version,
            "policy_digest": request.expected_policy_digest,
            "started_at": NOW,
            "use_deadline": NOW + timedelta(milliseconds=500),
            "attestation_valid_until": attestation.valid_until,
            "state": WorkflowProtectedRuntimeContextUseAttemptState.USE_STARTED,
            "authority": WorkflowProtectedRuntimeContextUseAuthority(),
        }
        attempt = WorkflowProtectedRuntimeContextUseAttempt(
            **cast(Any, attempt_values),
            canonical_digest=canonical_digest(_canonical_mapping(attempt_values)),
        )
        self.attempt = attempt
        self.trusted_user.attempt = attempt
        return WorkflowProtectedRuntimeContextUseClaimWrite(
            WorkflowProtectedRuntimeContextUseClaimStatus.CLAIMED, claim, attempt, None
        )

    async def record_protected_runtime_context_use_result(
        self, request: WorkflowProtectedRuntimeContextUseResultRequest
    ) -> WorkflowProtectedRuntimeContextUseResultWrite:
        self.events.append("result")
        self.result = request.result
        return WorkflowProtectedRuntimeContextUseResultWrite(
            WorkflowProtectedRuntimeContextUseResultWriteStatus.RECORDED, request.result
        )

    async def list_protected_runtime_context_use_attempts(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeContextUseAttempt, ...]:
        del scope, limit
        return (self.attempt,) if self.attempt is not None else ()

    async def get_protected_runtime_context_use_results(
        self, *, scope: WorkflowScope, use_ids: tuple[str, ...]
    ) -> tuple[WorkflowProtectedRuntimeContextUseResult, ...]:
        del scope, use_ids
        return (self.result,) if self.result is not None else ()


def _service(
    *,
    fail_executor: bool = False,
    valid_attestation: bool = True,
    valid_receipt: bool = True,
    valid_instruction_signature: bool = True,
) -> tuple[WorkflowProtectedRuntimeContextUseService, _Repository, _Attestor, _TrustedUser]:
    events: list[str] = []
    trusted_user = _TrustedUser(events, fail=fail_executor)
    repository = _Repository(trusted_user, events)
    attestor = _Attestor(events)
    service = WorkflowProtectedRuntimeContextUseService(
        repository=repository,
        eligibility_attestor=attestor,
        eligibility_signature_verifier=_SignatureVerifier(valid=valid_attestation),
        trusted_user=trusted_user,
        receipt_signature_verifier=_SignatureVerifier(valid=valid_receipt),
        instruction_signer=_InstructionSigner(),
        instruction_signature_verifier=_InstructionSignatureVerifier(
            valid=valid_instruction_signature
        ),
    )
    return service, repository, attestor, trusted_user


async def _use(
    service: WorkflowProtectedRuntimeContextUseService,
) -> WorkflowProtectedRuntimeContextUsePresentation:
    return await service.use(
        authorization_consumption_result_id="use-authorization-consumption-result.imp-221",
        policy_id=service.policy.policy_id,
        policy_version=service.policy.policy_version,
        irreversible_use_acknowledged=True,
        uncertainty_no_retry_acknowledged=True,
        idempotency_key="imp-222-context-use",
        context=_context(),
    )


@pytest.mark.asyncio
async def test_service_is_replay_first_claims_before_io_and_calls_executor_once() -> None:
    service, repository, attestor, trusted_user = _service()

    presentation = await _use(service)

    assert repository.events == [
        "replay",
        "source",
        "time",
        "attest",
        "claim",
        "executor",
        "time",
        "result",
    ]
    assert trusted_user.calls == 1
    assert len(attestor.calls) == 1
    assert presentation.result is not None
    assert presentation.result.protected_runtime_context_use_performed is True
    assert not any(presentation.result.authority.canonical_value().values())

    replayed = await _use(service)
    assert replayed == presentation
    assert trusted_user.calls == 1
    assert len(attestor.calls) == 1
    assert repository.events[-1] == "replay"


@pytest.mark.asyncio
async def test_exact_terminal_replay_performs_no_attestor_or_executor_io() -> None:
    service, repository, attestor, trusted_user = _service()
    original = await _use(service)
    repository.events.clear()

    replayed = await _use(service)

    assert replayed == original
    assert repository.events == ["replay"]
    assert trusted_user.calls == 1
    assert len(attestor.calls) == 1


@pytest.mark.asyncio
async def test_missing_instruction_security_components_fail_before_protected_state_io() -> None:
    events: list[str] = []
    trusted_user = _TrustedUser(events)
    repository = _Repository(trusted_user, events)
    attestor = _Attestor(events)
    service = WorkflowProtectedRuntimeContextUseService(
        repository=repository,
        eligibility_attestor=attestor,
        eligibility_signature_verifier=_SignatureVerifier(),
        trusted_user=trusted_user,
        receipt_signature_verifier=_SignatureVerifier(),
    )

    with pytest.raises(
        WorkflowProtectedRuntimeContextUseError,
        match="protected_runtime_context_use_trusted_component_unavailable",
    ):
        await _use(service)

    assert events == ["replay"]
    assert attestor.calls == []
    assert trusted_user.calls == 0


@pytest.mark.asyncio
async def test_started_attempt_replay_is_never_resumed_or_reinvoked() -> None:
    service, repository, attestor, trusted_user = _service()
    original = await _use(service)
    assert original.result is not None
    repository.result = None
    repository.events.clear()

    replayed = await _use(service)

    assert replayed.attempt == original.attempt
    assert replayed.result is None
    assert repository.events == ["replay"]
    assert trusted_user.calls == 1
    assert len(attestor.calls) == 1


@pytest.mark.asyncio
async def test_invalid_fresh_attestation_fails_before_claim_or_executor() -> None:
    service, repository, _, trusted_user = _service(valid_attestation=False)

    with pytest.raises(WorkflowProtectedRuntimeContextUseError, match="evidence_invalid"):
        await _use(service)

    assert repository.events == ["replay", "source", "time", "attest"]
    assert trusted_user.calls == 0


@pytest.mark.asyncio
async def test_executor_failure_records_permanent_uncertainty_without_retry() -> None:
    service, repository, attestor, trusted_user = _service(fail_executor=True)

    presentation = await _use(service)

    assert presentation.result is not None
    assert presentation.result.state.value == "context_use_outcome_uncertain"
    assert presentation.result.executor_receipt_digest is None
    assert presentation.result.protected_runtime_context_use_performed is False
    assert trusted_user.calls == 1

    replayed = await _use(service)
    assert replayed == presentation
    assert trusted_user.calls == 1
    assert len(attestor.calls) == 1
    assert repository.events[-1] == "replay"


@pytest.mark.asyncio
async def test_invalid_receipt_becomes_uncertain_and_is_never_reinvoked() -> None:
    service, repository, _, trusted_user = _service(valid_receipt=False)

    presentation = await _use(service)

    assert presentation.result is not None
    assert presentation.result.state.value == "context_use_outcome_uncertain"
    assert presentation.result.outcome_known is False
    assert trusted_user.calls == 1

    await _use(service)
    assert trusted_user.calls == 1
    assert repository.events[-1] == "replay"


@pytest.mark.asyncio
async def test_invalid_instruction_envelope_fails_closed_before_executor_io() -> None:
    service, repository, _, trusted_user = _service(valid_instruction_signature=False)

    presentation = await _use(service)

    assert presentation.result is not None
    assert presentation.result.state.value == "context_use_outcome_uncertain"
    assert trusted_user.calls == 0
    assert "executor" not in repository.events


@pytest.mark.asyncio
async def test_request_rejects_human_or_missing_irreversible_acknowledgement() -> None:
    service, _, _, trusted_user = _service()
    human = _context()
    object.__setattr__(human, "actor_type", "human")

    with pytest.raises(WorkflowProtectedRuntimeContextUseError, match="request_invalid"):
        await service.use(
            authorization_consumption_result_id="use-authorization-consumption-result.imp-221",
            policy_id=service.policy.policy_id,
            policy_version=service.policy.policy_version,
            irreversible_use_acknowledged=False,
            uncertainty_no_retry_acknowledged=True,
            idempotency_key="imp-222-context-use",
            context=human,
        )

    assert trusted_user.calls == 0

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas.core.audit import AuditSink
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_ports import (
    WorkflowProtectedTargetContextCapsuleHandoffAttestationSignatureVerifier,
    WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestationRequest,
    WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestor,
    WorkflowProtectedTargetContextCapsuleSealedHandoffAdapter,
    WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestationRequest,
    WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestor,
    WorkflowProtectedTransportTargetContextCapsuleHandoffClaimStatus,
    WorkflowProtectedTransportTargetContextCapsuleHandoffError,
    WorkflowProtectedTransportTargetContextCapsuleHandoffReplayStatus,
    WorkflowProtectedTransportTargetContextCapsuleHandoffResultWriteStatus,
    WorkflowTargetContextCapsuleHandoffClaimRequest,
    WorkflowTargetContextCapsuleHandoffReplayLookup,
    WorkflowTargetContextCapsuleHandoffReplayLookupRequest,
    WorkflowTargetContextCapsuleHandoffRepository,
    WorkflowTargetContextCapsuleHandoffResultRequest,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestation,
    WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestation,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthority,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseState,
    WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionPolicy,
    WorkflowProtectedTransportTargetContextCapsuleHandoffInstruction,
    WorkflowProtectedTransportTargetContextCapsuleHandoffReceipt,
    WorkflowProtectedTransportTargetContextCapsuleHandoffResult,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_transport_target_context_capsule_handoff_consumption_policy,
)


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleHandoffPresentation:
    attempt: WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt
    result: WorkflowProtectedTransportTargetContextCapsuleHandoffResult | None


@dataclass(frozen=True, slots=True)
class _ResolvedHandoffEvidence:
    lease: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease
    binding: WorkflowProtectedTransportTargetContextCapsuleConsumerBinding
    lifecycle: WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestation
    acceptance: WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestation


class WorkflowProtectedTransportTargetContextCapsuleHandoffService:
    """Consumes one lease before one sealed protected-boundary handoff attempt."""

    def __init__(
        self,
        *,
        repository: WorkflowTargetContextCapsuleHandoffRepository,
        lifecycle_attestor: WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestor,
        acceptance_attestor: WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestor,
        attestation_signature_verifier: (
            WorkflowProtectedTargetContextCapsuleHandoffAttestationSignatureVerifier
        ),
        adapter: WorkflowProtectedTargetContextCapsuleSealedHandoffAdapter,
        audit_sink: AuditSink,
        policy: WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionPolicy
        | None = None,
    ) -> None:
        self._repository = repository
        self._lifecycle_attestor = lifecycle_attestor
        self._acceptance_attestor = acceptance_attestor
        self._attestation_signature_verifier = attestation_signature_verifier
        self._adapter = adapter
        self._audit_sink = audit_sink
        self._policy = policy or (
            code_owned_workflow_protected_transport_target_context_capsule_handoff_consumption_policy()
        )

    @property
    def repository(self) -> WorkflowTargetContextCapsuleHandoffRepository:
        return self._repository

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def policy(self) -> WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionPolicy:
        return self._policy

    async def handoff(
        self,
        *,
        authorization_lease_id: str,
        authorization_lease_digest: str,
        policy_id: str,
        policy_version: str,
        irreversible_consumption_acknowledged: bool,
        uncertain_outcome_requires_new_authorization_acknowledged: bool,
        idempotency_key: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffPresentation:
        self._require_request(
            authorization_lease_id=authorization_lease_id,
            authorization_lease_digest=authorization_lease_digest,
            policy_id=policy_id,
            policy_version=policy_version,
            irreversible_consumption_acknowledged=irreversible_consumption_acknowledged,
            uncertain_outcome_requires_new_authorization_acknowledged=(
                uncertain_outcome_requires_new_authorization_acknowledged
            ),
            idempotency_key=idempotency_key,
            context=context,
        )
        if not self._repository.durable:
            self._raise("target_context_capsule_handoff_durable_repository_required")
        idempotency_digest = sha256(
            f"{context.subject_id}\x00{idempotency_key}".encode()
        ).hexdigest()
        request_fingerprint = canonical_digest(
            {
                "authorization_lease_digest": authorization_lease_digest,
                "authorization_lease_id": authorization_lease_id,
                "consumer_audience": context.credential_audience,
                "consumer_subject_id": context.subject_id,
                "idempotency_digest": idempotency_digest,
                "irreversible_consumption_acknowledged": True,
                "policy_digest": self._policy.canonical_digest,
                "policy_id": policy_id,
                "policy_version": policy_version,
                "scope": context.scope.canonical_value(),
                "uncertain_outcome_requires_new_authorization_acknowledged": True,
            }
        )
        seed = canonical_digest(
            {
                "authorization_lease_id": authorization_lease_id,
                "idempotency_digest": idempotency_digest,
                "request_fingerprint": request_fingerprint,
            }
        )
        handoff_id = f"workflow-target-context-capsule-handoff.{seed[:24]}"
        replay = await self._repository.lookup_target_context_capsule_handoff_replay(
            WorkflowTargetContextCapsuleHandoffReplayLookupRequest(
                authorization_lease_id=authorization_lease_id,
                authorization_lease_digest=authorization_lease_digest,
                scope=context.scope,
                consumer_subject_id=context.subject_id,
                consumer_audience=context.credential_audience,
                policy_id=self._policy.policy_id,
                policy_version=self._policy.policy_version,
                policy_digest=self._policy.canonical_digest,
                idempotency_digest=idempotency_digest,
                request_fingerprint=request_fingerprint,
                handoff_id=handoff_id,
            )
        )
        historical = self._resolve_replay(replay)
        if historical is not None:
            return historical
        if (
            not self._adapter.available
            or self._adapter.adapter_contract_id != self._policy.required_adapter_contract_id
            or self._adapter.adapter_contract_version
            != self._policy.required_adapter_contract_version
            or self._adapter.adapter_id != self._policy.approved_adapter_id
            or self._adapter.adapter_version != self._policy.approved_adapter_version
        ):
            self._raise("target_context_capsule_handoff_trusted_adapter_unavailable")

        evidence = await self._load_and_attest(
            authorization_lease_id=authorization_lease_id,
            authorization_lease_digest=authorization_lease_digest,
            context=context,
        )
        claim_id = f"workflow-target-context-capsule-handoff-claim.{seed[:24]}"
        attempt_id = f"workflow-target-context-capsule-handoff-attempt.{seed[:24]}"
        audit_payload: dict[str, object] = {
            "schema_id": (
                "audit.workflow-target-context-capsule-handoff-consumption-authorization"
            ),
            "schema_version": "1.0",
            "event_type": "target_context_capsule_handoff_lease_consumption_authorized",
            "claim_id": claim_id,
            "attempt_id": attempt_id,
            "handoff_id": handoff_id,
            "authorization_lease_id": authorization_lease_id,
            "authorization_lease_digest": authorization_lease_digest,
            "scope": context.scope.canonical_value(),
            "consumer_subject_id": context.subject_id,
            "consumer_audience": context.credential_audience,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "idempotency_digest": idempotency_digest,
            "request_fingerprint": request_fingerprint,
            "irreversible_consumption_acknowledged": True,
            "uncertain_outcome_requires_new_authorization_acknowledged": True,
        }
        claim_request = WorkflowTargetContextCapsuleHandoffClaimRequest(
            claim_id=claim_id,
            attempt_id=attempt_id,
            handoff_id=handoff_id,
            authorization_lease_id=authorization_lease_id,
            authorization_lease_digest=authorization_lease_digest,
            expected_consumer_binding_id=evidence.binding.binding_id,
            expected_consumer_binding_digest=evidence.binding.canonical_digest,
            expected_sealed_capsule_id=evidence.binding.sealed_capsule_id,
            expected_sealed_capsule_digest=evidence.binding.sealed_capsule_digest,
            expected_capsule_schema_id=evidence.binding.capsule_schema_id,
            expected_capsule_schema_version=evidence.binding.capsule_schema_version,
            lifecycle_attestation=evidence.lifecycle,
            acceptance_attestation=evidence.acceptance,
            expected_request_nonce_digest=evidence.lifecycle.request_nonce_digest,
            offline_signature_verifier=self._attestation_signature_verifier,
            expected_policy_id=self._policy.policy_id,
            expected_policy_version=self._policy.policy_version,
            expected_policy_digest=self._policy.canonical_digest,
            expected_adapter_contract_id=self._policy.required_adapter_contract_id,
            expected_adapter_contract_version=self._policy.required_adapter_contract_version,
            expected_approved_adapter_id=self._policy.approved_adapter_id,
            expected_approved_adapter_version=self._policy.approved_adapter_version,
            expected_destination_boundary_id=self._policy.destination_boundary_id,
            expected_destination_deployment_id=self._policy.destination_deployment_id,
            expected_destination_generation=self._policy.destination_generation,
            expected_destination_fencing_token_digest=(
                self._policy.destination_fencing_token_digest
            ),
            expected_custody_contract_id=self._policy.custody_contract_id,
            expected_custody_contract_version=self._policy.custody_contract_version,
            expected_verification_signing_key_id=self._policy.verification_signing_key_id,
            expected_trusted_profile_digest=self._policy.trusted_profile_digest,
            minimum_remaining_budget_milliseconds=(
                self._policy.minimum_remaining_budget_milliseconds
            ),
            scope=context.scope,
            consumer_subject_id=context.subject_id,
            consumer_audience=context.credential_audience,
            consumer_contract_id=evidence.binding.consumer_contract_id,
            consumer_contract_version=evidence.binding.consumer_contract_version,
            purpose_id=evidence.binding.purpose_id,
            idempotency_key=idempotency_key,
            idempotency_digest=idempotency_digest,
            request_fingerprint=request_fingerprint,
            irreversible_consumption_acknowledged=True,
            uncertain_outcome_requires_new_authorization_acknowledged=True,
            consumption_authorization_audit_payload=audit_payload,
            consumption_authorization_audit_digest=canonical_digest(audit_payload),
        )
        claimed = await self._repository.claim_target_context_capsule_handoff(claim_request)
        if (
            claimed.status
            is WorkflowProtectedTransportTargetContextCapsuleHandoffClaimStatus.REPLAY_COMPLETED
        ):
            if claimed.attempt is None:
                self._raise("target_context_capsule_handoff_repository_contract_violation")
            return WorkflowProtectedTransportTargetContextCapsuleHandoffPresentation(
                claimed.attempt, claimed.result
            )
        if (
            claimed.status
            is WorkflowProtectedTransportTargetContextCapsuleHandoffClaimStatus.CLAIM_ONLY_UNCERTAIN
        ):
            if claimed.attempt is None:
                self._raise("target_context_capsule_handoff_repository_contract_violation")
            return WorkflowProtectedTransportTargetContextCapsuleHandoffPresentation(
                claimed.attempt, None
            )
        if (
            claimed.status
            is not WorkflowProtectedTransportTargetContextCapsuleHandoffClaimStatus.CLAIMED
        ):
            self._raise(f"target_context_capsule_handoff_{claimed.status.value}")
        if claimed.claim is None or claimed.attempt is None or claimed.result is not None:
            self._raise("target_context_capsule_handoff_claim_commit_uncertain")

        instruction = self._build_instruction(evidence=evidence, attempt=claimed.attempt)
        try:
            receipt = await self._adapter.handoff_sealed_capsule(instruction)
            self._verify_receipt(receipt, instruction)
            result = self._build_result(
                evidence=evidence,
                claim_digest=claimed.claim.canonical_digest,
                attempt_digest=claimed.attempt.canonical_digest,
                receipt=receipt,
            )
            written = await self._repository.record_target_context_capsule_handoff_result(
                WorkflowTargetContextCapsuleHandoffResultRequest(
                    result=result,
                    receipt=receipt,
                    expected_claim_digest=claimed.claim.canonical_digest,
                    expected_attempt_digest=claimed.attempt.canonical_digest,
                )
            )
        except Exception:
            return WorkflowProtectedTransportTargetContextCapsuleHandoffPresentation(
                claimed.attempt, None
            )
        if (
            written.status
            not in (
                WorkflowProtectedTransportTargetContextCapsuleHandoffResultWriteStatus.RECORDED,
                WorkflowProtectedTransportTargetContextCapsuleHandoffResultWriteStatus.REPLAY,
            )
            or written.result is None
        ):
            return WorkflowProtectedTransportTargetContextCapsuleHandoffPresentation(
                claimed.attempt, None
            )
        return WorkflowProtectedTransportTargetContextCapsuleHandoffPresentation(
            claimed.attempt, written.result
        )

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleHandoffPresentation, ...]:
        if not self._repository.durable:
            self._raise("target_context_capsule_handoff_durable_repository_required")
        attempts = await self._repository.list_target_context_capsule_handoff_attempts(
            scope=scope, limit=limit
        )
        results = await self._repository.get_target_context_capsule_handoff_results_by_handoff_ids(
            scope=scope,
            handoff_ids=tuple(attempt.handoff_id for attempt in attempts),
        )
        by_handoff = {result.handoff_id: result for result in results}
        return tuple(
            WorkflowProtectedTransportTargetContextCapsuleHandoffPresentation(
                attempt, by_handoff.get(attempt.handoff_id)
            )
            for attempt in attempts
        )

    async def _load_and_attest(
        self,
        *,
        authorization_lease_id: str,
        authorization_lease_digest: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> _ResolvedHandoffEvidence:
        lease = await self._repository.get_target_context_capsule_handoff_authorization_lease_by_id(
            authorization_lease_id=authorization_lease_id
        )
        if lease is None:
            self._raise("target_context_capsule_handoff_lease_not_found")
        binding = await self._repository.get_target_context_capsule_consumer_binding_by_id(
            binding_id=lease.consumer_binding_id
        )
        if binding is None:
            self._raise("target_context_capsule_handoff_binding_not_found")
        self._validate_base_evidence(
            lease=lease,
            binding=binding,
            authorization_lease_digest=authorization_lease_digest,
            context=context,
        )
        nonce_digest = canonical_digest(
            {"authorization_lease_digest": authorization_lease_digest, "nonce": uuid4().hex}
        )
        lifecycle_request = WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestationRequest(
            authorization_lease_id=lease.authorization_lease_id,
            authorization_lease_digest=lease.canonical_digest,
            consumer_binding_id=binding.binding_id,
            consumer_binding_digest=binding.canonical_digest,
            sealed_capsule_id=binding.sealed_capsule_id,
            sealed_capsule_digest=binding.sealed_capsule_digest,
            capsule_schema_id=binding.capsule_schema_id,
            capsule_schema_version=binding.capsule_schema_version,
            scope=context.scope,
            consumer_subject_id=context.subject_id,
            request_nonce_digest=nonce_digest,
            requested_at=context.requested_at,
        )
        acceptance_request = (
            WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestationRequest(
                authorization_lease_id=lease.authorization_lease_id,
                authorization_lease_digest=lease.canonical_digest,
                consumer_binding_id=binding.binding_id,
                consumer_binding_digest=binding.canonical_digest,
                consumer_subject_id=binding.consumer_subject_id,
                consumer_audience=binding.consumer_audience,
                consumer_contract_id=binding.consumer_contract_id,
                consumer_contract_version=binding.consumer_contract_version,
                purpose_id=binding.purpose_id,
                capsule_schema_id=binding.capsule_schema_id,
                capsule_schema_version=binding.capsule_schema_version,
                destination_boundary_id=self._policy.destination_boundary_id,
                destination_deployment_id=self._policy.destination_deployment_id,
                destination_generation=self._policy.destination_generation,
                destination_fencing_token_digest=(self._policy.destination_fencing_token_digest),
                custody_contract_id=self._policy.custody_contract_id,
                custody_contract_version=self._policy.custody_contract_version,
                approved_adapter_id=self._policy.approved_adapter_id,
                approved_adapter_version=self._policy.approved_adapter_version,
                verification_signing_key_id=self._policy.verification_signing_key_id,
                trusted_profile_digest=self._policy.trusted_profile_digest,
                scope=context.scope,
                request_nonce_digest=nonce_digest,
                requested_at=context.requested_at,
            )
        )
        lifecycle = await self._lifecycle_attestor.attest_capsule_handoff_lifecycle(
            lifecycle_request
        )
        acceptance = await self._acceptance_attestor.attest_consumer_boundary_acceptance(
            acceptance_request
        )
        now = await self._repository.get_authoritative_time()
        self._validate_attestations(
            lifecycle=lifecycle,
            acceptance=acceptance,
            lifecycle_request=lifecycle_request,
            acceptance_request=acceptance_request,
            evaluated_at=now,
        )
        if not lease.issued_at <= now < lease.valid_until:
            self._raise("target_context_capsule_handoff_evidence_conflict")
        return _ResolvedHandoffEvidence(lease, binding, lifecycle, acceptance)

    def _validate_attestations(
        self,
        *,
        lifecycle: WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestation,
        acceptance: WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestation,
        lifecycle_request: WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestationRequest,
        acceptance_request: (
            WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestationRequest
        ),
        evaluated_at: datetime,
    ) -> None:
        if (
            lifecycle.authorization_lease_id != lifecycle_request.authorization_lease_id
            or lifecycle.authorization_lease_digest != lifecycle_request.authorization_lease_digest
            or lifecycle.consumer_binding_id != lifecycle_request.consumer_binding_id
            or lifecycle.consumer_binding_digest != lifecycle_request.consumer_binding_digest
            or lifecycle.sealed_capsule_id != lifecycle_request.sealed_capsule_id
            or lifecycle.sealed_capsule_digest != lifecycle_request.sealed_capsule_digest
            or lifecycle.request_nonce_digest != lifecycle_request.request_nonce_digest
            or lifecycle.attestor_id != self._policy.required_lifecycle_attestor_id
            or lifecycle.attestor_version != self._policy.required_lifecycle_attestor_version
            or acceptance.authorization_lease_id != acceptance_request.authorization_lease_id
            or acceptance.authorization_lease_digest
            != acceptance_request.authorization_lease_digest
            or acceptance.consumer_binding_id != acceptance_request.consumer_binding_id
            or acceptance.consumer_binding_digest != acceptance_request.consumer_binding_digest
            or acceptance.consumer_subject_id != acceptance_request.consumer_subject_id
            or acceptance.consumer_audience != acceptance_request.consumer_audience
            or acceptance.consumer_contract_id != acceptance_request.consumer_contract_id
            or acceptance.consumer_contract_version != acceptance_request.consumer_contract_version
            or acceptance.purpose_id != acceptance_request.purpose_id
            or acceptance.destination_boundary_id != self._policy.destination_boundary_id
            or acceptance.destination_deployment_id != self._policy.destination_deployment_id
            or acceptance.destination_generation != self._policy.destination_generation
            or acceptance.destination_fencing_token_digest
            != self._policy.destination_fencing_token_digest
            or acceptance.custody_contract_id != self._policy.custody_contract_id
            or acceptance.custody_contract_version != self._policy.custody_contract_version
            or acceptance.approved_adapter_id != self._policy.approved_adapter_id
            or acceptance.approved_adapter_version != self._policy.approved_adapter_version
            or acceptance.verification_signing_key_id != self._policy.verification_signing_key_id
            or acceptance.trusted_profile_digest != self._policy.trusted_profile_digest
            or acceptance.request_nonce_digest != acceptance_request.request_nonce_digest
            or acceptance.attestor_id != self._policy.required_acceptance_attestor_id
            or acceptance.attestor_version != self._policy.required_acceptance_attestor_version
            or lifecycle.observed_at < lifecycle_request.requested_at
            or acceptance.observed_at < acceptance_request.requested_at
            or lifecycle.observed_at > evaluated_at
            or acceptance.observed_at > evaluated_at
            or lifecycle.valid_until <= evaluated_at
            or acceptance.valid_until <= evaluated_at
            or self._attestation_signature_verifier.verify_capsule_handoff_lifecycle_attestation(
                lifecycle
            )
            is not True
            or self._attestation_signature_verifier.verify_consumer_boundary_acceptance_attestation(
                acceptance
            )
            is not True
        ):
            self._raise("target_context_capsule_handoff_evidence_conflict")

    @staticmethod
    def _validate_base_evidence(
        *,
        lease: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
        binding: WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
        authorization_lease_digest: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> None:
        if (
            lease.canonical_digest != authorization_lease_digest
            or lease.scope != context.scope
            or lease.consumer_subject_id != context.subject_id
            or lease.consumer_audience != context.credential_audience
            or lease.state
            is not (
                WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseState
            ).AUTHORIZED_UNCONSUMED
            or lease.authority.target_context_capsule_handoff_authorized is not True
            or any(
                value is not False
                for name, value in lease.authority.canonical_value().items()
                if name != "target_context_capsule_handoff_authorized"
            )
            or binding.binding_id != lease.consumer_binding_id
            or binding.canonical_digest != lease.consumer_binding_digest
            or binding.sealed_capsule_id != lease.sealed_capsule_id
            or binding.sealed_capsule_digest != lease.sealed_capsule_digest
            or binding.scope != lease.scope
            or binding.consumer_subject_id != lease.consumer_subject_id
            or binding.consumer_audience != lease.consumer_audience
            or binding.consumer_contract_id != lease.consumer_contract_id
            or binding.consumer_contract_version != lease.consumer_contract_version
            or binding.purpose_id != lease.purpose_id
            or binding.capsule_is_bearer_capability
            or any(binding.authority.canonical_value().values())
        ):
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffError(
                "target_context_capsule_handoff_evidence_conflict"
            )

    def _build_instruction(
        self,
        *,
        evidence: _ResolvedHandoffEvidence,
        attempt: WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt,
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffInstruction:
        values: dict[str, object] = {
            "handoff_id": attempt.handoff_id,
            "attempt_id": attempt.attempt_id,
            "consumption_claim_id": attempt.consumption_claim_id,
            "authorization_lease_id": evidence.lease.authorization_lease_id,
            "authorization_lease_digest": evidence.lease.canonical_digest,
            "consumer_binding_id": evidence.binding.binding_id,
            "consumer_binding_digest": evidence.binding.canonical_digest,
            "sealed_capsule_id": evidence.binding.sealed_capsule_id,
            "sealed_capsule_digest": evidence.binding.sealed_capsule_digest,
            "capsule_schema_id": evidence.binding.capsule_schema_id,
            "capsule_schema_version": evidence.binding.capsule_schema_version,
            "consumer_subject_id": evidence.binding.consumer_subject_id,
            "consumer_audience": evidence.binding.consumer_audience,
            "consumer_contract_id": evidence.binding.consumer_contract_id,
            "consumer_contract_version": evidence.binding.consumer_contract_version,
            "purpose_id": evidence.binding.purpose_id,
            "adapter_contract_id": self._policy.required_adapter_contract_id,
            "adapter_contract_version": self._policy.required_adapter_contract_version,
            "approved_adapter_id": self._policy.approved_adapter_id,
            "approved_adapter_version": self._policy.approved_adapter_version,
            "destination_boundary_id": self._policy.destination_boundary_id,
            "destination_deployment_id": self._policy.destination_deployment_id,
            "destination_generation": self._policy.destination_generation,
            "destination_fencing_token_digest": (self._policy.destination_fencing_token_digest),
            "custody_contract_id": self._policy.custody_contract_id,
            "custody_contract_version": self._policy.custody_contract_version,
            "verification_signing_key_id": self._policy.verification_signing_key_id,
            "trusted_profile_digest": self._policy.trusted_profile_digest,
            "started_at": attempt.started_at,
            "handoff_deadline": attempt.handoff_deadline,
            "lifecycle_attestation_digest": evidence.lifecycle.canonical_digest,
            "acceptance_attestation_digest": evidence.acceptance.canonical_digest,
        }
        return WorkflowProtectedTransportTargetContextCapsuleHandoffInstruction(
            **cast(Any, values), canonical_digest=canonical_digest(self._payload(values))
        )

    def _verify_receipt(
        self,
        receipt: WorkflowProtectedTransportTargetContextCapsuleHandoffReceipt,
        instruction: WorkflowProtectedTransportTargetContextCapsuleHandoffInstruction,
    ) -> None:
        if (
            receipt.handoff_id != instruction.handoff_id
            or receipt.attempt_id != instruction.attempt_id
            or receipt.consumption_claim_id != instruction.consumption_claim_id
            or receipt.instruction_digest != instruction.canonical_digest
            or receipt.adapter_contract_id != self._policy.required_adapter_contract_id
            or receipt.adapter_contract_version != self._policy.required_adapter_contract_version
            or receipt.adapter_id != self._policy.approved_adapter_id
            or receipt.adapter_version != self._policy.approved_adapter_version
            or receipt.destination_boundary_id != self._policy.destination_boundary_id
            or receipt.destination_deployment_id != self._policy.destination_deployment_id
            or receipt.destination_generation != self._policy.destination_generation
            or receipt.destination_fencing_token_digest
            != self._policy.destination_fencing_token_digest
            or receipt.custody_contract_id != self._policy.custody_contract_id
            or receipt.custody_contract_version != self._policy.custody_contract_version
            or receipt.signing_key_id != self._policy.verification_signing_key_id
            or receipt.trusted_profile_digest != self._policy.trusted_profile_digest
            or receipt.completed_at < instruction.started_at
            or receipt.completed_at >= instruction.handoff_deadline
            or receipt.capsule_remained_sealed is not True
            or receipt.consumer_receipt_is_bearer_capability is not False
            or receipt.runtime_use_performed is not False
            or receipt.network_activity_performed is not False
            or receipt.canonical_digest != canonical_digest(receipt.digest_payload())
            or self._adapter.verify_receipt(receipt) is not True
        ):
            self._raise("target_context_capsule_handoff_receipt_invalid")

    def _build_result(
        self,
        *,
        evidence: _ResolvedHandoffEvidence,
        claim_digest: str,
        attempt_digest: str,
        receipt: WorkflowProtectedTransportTargetContextCapsuleHandoffReceipt,
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffResult:
        values: dict[str, object] = {
            "handoff_id": receipt.handoff_id,
            "attempt_id": receipt.attempt_id,
            "attempt_digest": attempt_digest,
            "consumption_claim_id": receipt.consumption_claim_id,
            "consumption_claim_digest": claim_digest,
            "authorization_lease_id": evidence.lease.authorization_lease_id,
            "authorization_lease_digest": evidence.lease.canonical_digest,
            "consumer_binding_id": evidence.binding.binding_id,
            "consumer_binding_digest": evidence.binding.canonical_digest,
            "scope": evidence.binding.scope,
            "consumer_contract_id": evidence.binding.consumer_contract_id,
            "consumer_contract_version": evidence.binding.consumer_contract_version,
            "purpose_id": evidence.binding.purpose_id,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "adapter_contract_id": self._policy.required_adapter_contract_id,
            "adapter_contract_version": self._policy.required_adapter_contract_version,
            "receipt_digest": receipt.canonical_digest,
            "state": receipt.state,
            "failure_class": receipt.failure_class,
            "consumer_receipt_id": receipt.consumer_receipt_id,
            "consumer_receipt_is_bearer_capability": False,
            "sealed_capsule_handed_off": receipt.sealed_capsule_handed_off,
            "completed_at": receipt.completed_at,
            "usable_until": receipt.usable_until,
            "source_cleanup_confirmed": receipt.source_cleanup_confirmed,
            "authority": WorkflowProtectedTransportTargetContextCapsuleHandoffAuthority(),
        }
        return WorkflowProtectedTransportTargetContextCapsuleHandoffResult(
            **cast(Any, values), canonical_digest=canonical_digest(self._payload(values))
        )

    def _require_request(self, **values: object) -> None:
        context = values["context"]
        assert isinstance(
            context, WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext
        )
        if (
            context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.subject_id != WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT
            or context.credential_audience
            != WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            or values["policy_id"] != self._policy.policy_id
            or values["policy_version"] != self._policy.policy_version
            or values["irreversible_consumption_acknowledged"] is not True
            or values["uncertain_outcome_requires_new_authorization_acknowledged"] is not True
            or not isinstance(values["authorization_lease_digest"], str)
            or len(values["authorization_lease_digest"]) != 64
            or not isinstance(values["idempotency_key"], str)
            or not 8 <= len(values["idempotency_key"]) <= 128
        ):
            self._raise("target_context_capsule_handoff_request_invalid")
        for name in ("authorization_lease_id", "policy_id", "policy_version", "idempotency_key"):
            value = values[name]
            if (
                not isinstance(value, str)
                or not value
                or value != value.strip()
                or len(value) > 240
            ):
                self._raise("target_context_capsule_handoff_request_invalid")

    def _resolve_replay(
        self, replay: WorkflowTargetContextCapsuleHandoffReplayLookup
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffPresentation | None:
        if replay.status is WorkflowProtectedTransportTargetContextCapsuleHandoffReplayStatus.NONE:
            if replay.attempt is not None or replay.result is not None:
                self._raise("target_context_capsule_handoff_repository_contract_violation")
            return None
        if (
            replay.status
            is WorkflowProtectedTransportTargetContextCapsuleHandoffReplayStatus.TERMINAL
        ):
            if replay.attempt is None or replay.result is None:
                self._raise("target_context_capsule_handoff_repository_contract_violation")
            return WorkflowProtectedTransportTargetContextCapsuleHandoffPresentation(
                replay.attempt, replay.result
            )
        replay_statuses = WorkflowProtectedTransportTargetContextCapsuleHandoffReplayStatus
        if replay.status is replay_statuses.CLAIM_ONLY_UNCERTAIN:
            if replay.attempt is None or replay.result is not None:
                self._raise("target_context_capsule_handoff_repository_contract_violation")
            return WorkflowProtectedTransportTargetContextCapsuleHandoffPresentation(
                replay.attempt, None
            )
        self._raise(f"target_context_capsule_handoff_{replay.status.value}")

    @staticmethod
    def _payload(values: dict[str, object]) -> dict[str, object]:
        return {
            name: (
                value.isoformat()
                if isinstance(value, datetime)
                else value.value
                if hasattr(value, "value")
                else value.canonical_value()
                if hasattr(value, "canonical_value")
                else value
            )
            for name, value in values.items()
        }

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowProtectedTransportTargetContextCapsuleHandoffError(code)


__all__ = [
    "WorkflowProtectedTransportTargetContextCapsuleHandoffPresentation",
    "WorkflowProtectedTransportTargetContextCapsuleHandoffService",
]

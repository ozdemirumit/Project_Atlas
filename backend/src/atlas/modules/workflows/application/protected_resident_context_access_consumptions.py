from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.protected_resident_context_access_authorization_ports import (  # noqa: E501
    WorkflowProtectedResidentContextLifecycleAttestation,
    WorkflowProtectedResidentContextLifecycleAttestationRequest,
    WorkflowProtectedResidentContextLifecycleAttestor,
    WorkflowProtectedResidentContextLifecycleSignatureVerifier,
)
from atlas.modules.workflows.application.protected_resident_context_access_consumption_ports import (  # noqa: E501
    WorkflowProtectedResidentContextAccessConsumptionClaimRequest,
    WorkflowProtectedResidentContextAccessConsumptionClaimStatus,
    WorkflowProtectedResidentContextAccessConsumptionError,
    WorkflowProtectedResidentContextAccessConsumptionReplayLookup,
    WorkflowProtectedResidentContextAccessConsumptionReplayLookupRequest,
    WorkflowProtectedResidentContextAccessConsumptionReplayStatus,
    WorkflowProtectedResidentContextAccessConsumptionRepository,
    WorkflowProtectedResidentContextAccessConsumptionResultRequest,
    WorkflowProtectedResidentContextAccessConsumptionResultWriteStatus,
    WorkflowProtectedResidentContextAccessConsumptionSource,
    WorkflowProtectedResidentContextAccessorReadinessAttestation,
    WorkflowProtectedResidentContextAccessorReadinessAttestationRequest,
    WorkflowProtectedResidentContextAccessorReadinessAttestor,
    WorkflowProtectedResidentContextAccessorReadinessSignatureVerifier,
    WorkflowProtectedResidentContextTrustedAccessor,
    build_workflow_protected_resident_context_trusted_accessor_instruction,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedResidentContextAccessAuthorizationLeaseEffectiveState,
    WorkflowProtectedResidentContextAccessAuthorizationLeaseState,
    WorkflowProtectedResidentContextAccessConsumptionAttempt,
    WorkflowProtectedResidentContextAccessConsumptionAuthority,
    WorkflowProtectedResidentContextAccessConsumptionFailureClass,
    WorkflowProtectedResidentContextAccessConsumptionPolicy,
    WorkflowProtectedResidentContextAccessConsumptionResult,
    WorkflowProtectedResidentContextAccessConsumptionResultState,
    WorkflowProtectedResidentContextTrustedAccessorInstruction,
    WorkflowProtectedResidentContextTrustedAccessorReceipt,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_resident_context_access_consumption_policy,
)

WORKFLOW_PROTECTED_RESIDENT_CONTEXT_ACCESS_CONSUMPTION_PRODUCER = (
    "project-atlas-workflow-protected-resident-context-access-consumer"
)


@dataclass(frozen=True, slots=True)
class WorkflowProtectedResidentContextAccessConsumptionPresentation:
    attempt: WorkflowProtectedResidentContextAccessConsumptionAttempt
    result: WorkflowProtectedResidentContextAccessConsumptionResult | None


@dataclass(frozen=True, slots=True)
class _ResolvedAccessEvidence:
    source: WorkflowProtectedResidentContextAccessConsumptionSource
    lifecycle: WorkflowProtectedResidentContextLifecycleAttestation
    readiness: WorkflowProtectedResidentContextAccessorReadinessAttestation


class WorkflowProtectedResidentContextAccessConsumptionService:
    """Consumes one ADR-166 lease before one protected-side CAS operation."""

    def __init__(
        self,
        *,
        repository: WorkflowProtectedResidentContextAccessConsumptionRepository,
        lifecycle_attestor: WorkflowProtectedResidentContextLifecycleAttestor,
        readiness_attestor: WorkflowProtectedResidentContextAccessorReadinessAttestor,
        lifecycle_signature_verifier: WorkflowProtectedResidentContextLifecycleSignatureVerifier,
        readiness_signature_verifier: (
            WorkflowProtectedResidentContextAccessorReadinessSignatureVerifier
        ),
        accessor: WorkflowProtectedResidentContextTrustedAccessor,
        audit_sink: AuditSink,
        policy: WorkflowProtectedResidentContextAccessConsumptionPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._lifecycle_attestor = lifecycle_attestor
        self._readiness_attestor = readiness_attestor
        self._lifecycle_signature_verifier = lifecycle_signature_verifier
        self._readiness_signature_verifier = readiness_signature_verifier
        self._accessor = accessor
        self._audit_sink = audit_sink
        self._policy = (
            policy or code_owned_workflow_protected_resident_context_access_consumption_policy()
        )

    @property
    def repository(self) -> WorkflowProtectedResidentContextAccessConsumptionRepository:
        return self._repository

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def policy(self) -> WorkflowProtectedResidentContextAccessConsumptionPolicy:
        return self._policy

    async def consume(
        self,
        *,
        authorization_lease_id: str,
        policy_id: str,
        policy_version: str,
        irreversible_consumption_acknowledged: bool,
        uncertain_outcome_requires_new_authorization_acknowledged: bool,
        idempotency_key: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> WorkflowProtectedResidentContextAccessConsumptionPresentation:
        self._require_request(
            authorization_lease_id=authorization_lease_id,
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
            self._raise("protected_resident_context_access_consumption_durable_repository_required")

        idempotency_digest = sha256(
            f"{context.subject_id}\x00{idempotency_key}".encode()
        ).hexdigest()
        request_fingerprint = canonical_digest(
            {
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
        consumption_id = f"workflow-protected-resident-context-access.{seed[:24]}"

        # This durable lookup is deliberately the first repository operation and precedes
        # every attestor/accessor call. Historical replay must be external-I/O free.
        replay = await self._repository.lookup_protected_resident_context_access_consumption_replay(
            WorkflowProtectedResidentContextAccessConsumptionReplayLookupRequest(
                authorization_lease_id=authorization_lease_id,
                scope=context.scope,
                consumer_subject_id=context.subject_id,
                consumer_audience=context.credential_audience,
                policy_id=self._policy.policy_id,
                policy_version=self._policy.policy_version,
                policy_digest=self._policy.canonical_digest,
                idempotency_digest=idempotency_digest,
                request_fingerprint=request_fingerprint,
                consumption_id=consumption_id,
            )
        )
        historical = self._resolve_replay(replay)
        if historical is not None:
            return historical

        self._require_trusted_components()
        evidence = await self._load_and_attest(
            authorization_lease_id=authorization_lease_id,
            context=context,
        )
        lease = evidence.source.authorization_lease
        claim_id = f"workflow-protected-resident-context-access-claim.{seed[:24]}"
        attempt_id = f"workflow-protected-resident-context-access-attempt.{seed[:24]}"
        audit_payload: dict[str, object] = {
            "schema_id": (
                "audit.workflow-protected-resident-context-access-consumption-authorization"
            ),
            "schema_version": "1.0",
            "event_type": "protected_resident_context_access_lease_consumption_authorized",
            "claim_id": claim_id,
            "attempt_id": attempt_id,
            "consumption_id": consumption_id,
            "authorization_lease_id": lease.authorization_lease_id,
            "authorization_lease_digest": lease.canonical_digest,
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
        claimed = await self._repository.claim_protected_resident_context_access_consumption(
            WorkflowProtectedResidentContextAccessConsumptionClaimRequest(
                claim_id=claim_id,
                attempt_id=attempt_id,
                consumption_id=consumption_id,
                source=evidence.source,
                lifecycle_attestation=evidence.lifecycle,
                accessor_readiness_attestation=evidence.readiness,
                expected_request_nonce_digest=evidence.lifecycle.request_nonce_digest,
                offline_lifecycle_signature_verifier=self._lifecycle_signature_verifier,
                offline_readiness_signature_verifier=self._readiness_signature_verifier,
                expected_policy_id=self._policy.policy_id,
                expected_policy_version=self._policy.policy_version,
                expected_policy_digest=self._policy.canonical_digest,
                expected_lifecycle_attestor_id=self._policy.required_lifecycle_attestor_id,
                expected_lifecycle_attestor_version=(
                    self._policy.required_lifecycle_attestor_version
                ),
                expected_readiness_attestor_id=self._policy.required_readiness_attestor_id,
                expected_readiness_attestor_version=(
                    self._policy.required_readiness_attestor_version
                ),
                expected_accessor_contract_id=self._policy.required_accessor_contract_id,
                expected_accessor_contract_version=(
                    self._policy.required_accessor_contract_version
                ),
                expected_accessor_id=self._policy.approved_accessor_id,
                expected_accessor_version=self._policy.approved_accessor_version,
                expected_runtime_handle_profile_id=self._policy.runtime_handle_profile_id,
                expected_runtime_handle_profile_version=(
                    self._policy.runtime_handle_profile_version
                ),
                expected_runtime_handle_profile_digest=(self._policy.runtime_handle_profile_digest),
                expected_readiness_verification_signing_key_id=(
                    self._policy.readiness_verification_signing_key_id
                ),
                minimum_remaining_budget_milliseconds=(
                    self._policy.minimum_remaining_budget_milliseconds
                ),
                scope=context.scope,
                consumer_subject_id=context.subject_id,
                consumer_audience=context.credential_audience,
                idempotency_key=idempotency_key,
                idempotency_digest=idempotency_digest,
                request_fingerprint=request_fingerprint,
                irreversible_consumption_acknowledged=True,
                uncertain_outcome_requires_new_authorization_acknowledged=True,
                consumption_authorization_audit_payload=audit_payload,
                consumption_authorization_audit_digest=canonical_digest(audit_payload),
            )
        )
        claim_presentation = self._resolve_claim(claimed.status, claimed.attempt, claimed.result)
        if claim_presentation is not None:
            return claim_presentation
        if claimed.claim is None or claimed.attempt is None or claimed.result is not None:
            self._raise("protected_resident_context_access_consumption_claim_commit_uncertain")

        await self._export_audit_best_effort(
            context=context,
            consumption_id=consumption_id,
            authorization_lease_id=authorization_lease_id,
            outcome="succeeded",
            result_code="protected_resident_context_access_consumption_claim_committed",
        )

        instruction = self._build_instruction(claimed.attempt)
        receipt: WorkflowProtectedResidentContextTrustedAccessorReceipt | None = None
        try:
            receipt = await self._accessor.establish_access(instruction)
            self._verify_receipt(receipt, instruction)
            recorded_at = await self._repository.get_authoritative_time()
            result = self._build_receipted_result(
                claim_digest=claimed.claim.canonical_digest,
                attempt=claimed.attempt,
                receipt=receipt,
                recorded_at=recorded_at,
            )
            write = (
                await self._repository.record_protected_resident_context_access_consumption_result(
                    WorkflowProtectedResidentContextAccessConsumptionResultRequest(
                        result=result,
                        receipt=receipt,
                        expected_claim_digest=claimed.claim.canonical_digest,
                        expected_attempt_digest=claimed.attempt.canonical_digest,
                    )
                )
            )
        except Exception:
            return await self._record_uncertainty_if_due(
                claim_digest=claimed.claim.canonical_digest,
                attempt=claimed.attempt,
            )
        if (
            write.status
            not in (
                WorkflowProtectedResidentContextAccessConsumptionResultWriteStatus.RECORDED,
                WorkflowProtectedResidentContextAccessConsumptionResultWriteStatus.REPLAY,
            )
            or write.result is None
        ):
            return await self._record_uncertainty_if_due(
                claim_digest=claimed.claim.canonical_digest,
                attempt=claimed.attempt,
            )
        return WorkflowProtectedResidentContextAccessConsumptionPresentation(
            claimed.attempt, write.result
        )

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedResidentContextAccessConsumptionPresentation, ...]:
        if not self._repository.durable:
            self._raise("protected_resident_context_access_consumption_durable_repository_required")
        attempts = (
            await self._repository.list_protected_resident_context_access_consumption_attempts(
                scope=scope, limit=limit
            )
        )
        results = await self._repository.get_protected_resident_context_access_consumption_results(
            scope=scope,
            consumption_ids=tuple(attempt.access_id for attempt in attempts),
        )
        by_consumption = {result.access_id: result for result in results}
        return tuple(
            WorkflowProtectedResidentContextAccessConsumptionPresentation(
                attempt, by_consumption.get(attempt.access_id)
            )
            for attempt in attempts
        )

    async def _load_and_attest(
        self,
        *,
        authorization_lease_id: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> _ResolvedAccessEvidence:
        source = await self._repository.get_protected_resident_context_access_consumption_source(
            authorization_lease_id=authorization_lease_id
        )
        if source is None:
            self._raise("protected_resident_context_access_consumption_lease_not_found")
        self._validate_source(source, context=context)
        lease = source.authorization_lease
        lineage = source.authorization_source
        nonce_digest = canonical_digest(
            {"authorization_lease_digest": lease.canonical_digest, "nonce": uuid4().hex}
        )
        lifecycle_request = WorkflowProtectedResidentContextLifecycleAttestationRequest(
            opening_id=lease.opening_id,
            opening_result_digest=lease.opening_result_digest,
            opening_attempt_id=lease.opening_attempt_id,
            opening_attempt_digest=lease.opening_attempt_digest,
            opening_consumption_claim_id=lease.opening_consumption_claim_id,
            opening_consumption_claim_digest=lease.opening_consumption_claim_digest,
            opening_authorization_lease_id=lease.opening_authorization_lease_id,
            opening_authorization_lease_digest=lease.opening_authorization_lease_digest,
            opening_receipt_digest=lease.opening_receipt_digest,
            opening_receipt_signing_key_id=lineage.opening_receipt_signing_key_id,
            protected_resident_context_id=lease.protected_resident_context_id,
            protected_resident_context_digest=lease.protected_resident_context_digest,
            protected_resident_context_created_at=lease.protected_resident_context_created_at,
            protected_resident_context_usable_until=lease.protected_resident_context_usable_until,
            destination_boundary_id=lineage.destination_boundary_id,
            destination_deployment_id=lineage.destination_deployment_id,
            destination_generation=lineage.destination_generation,
            destination_fencing_token_digest=lineage.destination_fencing_token_digest,
            scope=lease.scope,
            consumer_subject_id=lease.consumer_subject_id,
            consumer_audience=lease.consumer_audience,
            consumer_contract_id=lease.consumer_contract_id,
            consumer_contract_version=lease.consumer_contract_version,
            purpose_id=lease.purpose_id,
            request_nonce_digest=nonce_digest,
            requested_at=context.requested_at,
        )
        readiness_request = WorkflowProtectedResidentContextAccessorReadinessAttestationRequest(
            authorization_lease_id=lease.authorization_lease_id,
            authorization_lease_digest=lease.canonical_digest,
            protected_resident_context_id=lease.protected_resident_context_id,
            protected_resident_context_digest=lease.protected_resident_context_digest,
            protected_resident_context_usable_until=lease.protected_resident_context_usable_until,
            destination_boundary_id=lineage.destination_boundary_id,
            destination_deployment_id=lineage.destination_deployment_id,
            destination_generation=lineage.destination_generation,
            destination_fencing_token_digest=lineage.destination_fencing_token_digest,
            scope=lease.scope,
            consumer_subject_id=lease.consumer_subject_id,
            consumer_audience=lease.consumer_audience,
            consumer_contract_id=lease.consumer_contract_id,
            consumer_contract_version=lease.consumer_contract_version,
            accessor_contract_id=self._policy.required_accessor_contract_id,
            accessor_contract_version=self._policy.required_accessor_contract_version,
            accessor_id=self._policy.approved_accessor_id,
            accessor_version=self._policy.approved_accessor_version,
            runtime_handle_profile_id=self._policy.runtime_handle_profile_id,
            runtime_handle_profile_version=self._policy.runtime_handle_profile_version,
            runtime_handle_profile_digest=self._policy.runtime_handle_profile_digest,
            request_nonce_digest=nonce_digest,
            requested_at=context.requested_at,
        )
        lifecycle = await self._lifecycle_attestor.attest_resident_context_lifecycle(
            lifecycle_request
        )
        readiness = await self._readiness_attestor.attest_accessor_readiness(readiness_request)
        self._validate_fresh_evidence(
            source=source,
            lifecycle=lifecycle,
            readiness=readiness,
            nonce_digest=nonce_digest,
            requested_at=context.requested_at,
        )
        return _ResolvedAccessEvidence(source, lifecycle, readiness)

    def _validate_source(
        self,
        source: WorkflowProtectedResidentContextAccessConsumptionSource,
        *,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> None:
        lease = source.authorization_lease
        lineage = source.authorization_source
        if (
            lease.authorization_lease_id == ""
            or lease.state
            is not (
                WorkflowProtectedResidentContextAccessAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
            )
            or lease.effective_state(evaluated_at=context.requested_at)
            is not WorkflowProtectedResidentContextAccessAuthorizationLeaseEffectiveState.ACTIVE
            or lease.single_use is not True
            or lease.renewable is not False
            or lease.transferable is not False
            or lease.lease_is_bearer_capability is not False
            or lease.protected_resident_context_access_authority_granted is not True
            or lease.scope != context.scope
            or lease.consumer_subject_id != context.subject_id
            or lease.consumer_audience != context.credential_audience
            or lease.opening_id != lineage.result.opening_id
            or lease.opening_result_digest != lineage.result.canonical_digest
            or lease.protected_resident_context_id != lineage.protected_resident_context_id
            or lease.protected_resident_context_digest != lineage.protected_resident_context_digest
            or lineage.destination_boundary_id != self._policy.destination_boundary_id
            or lineage.destination_deployment_id != self._policy.destination_deployment_id
            or lineage.destination_generation != self._policy.destination_generation
            or lineage.destination_fencing_token_digest
            != self._policy.destination_fencing_token_digest
        ):
            self._raise("protected_resident_context_access_consumption_source_invalid")

    def _validate_fresh_evidence(
        self,
        *,
        source: WorkflowProtectedResidentContextAccessConsumptionSource,
        lifecycle: WorkflowProtectedResidentContextLifecycleAttestation,
        readiness: WorkflowProtectedResidentContextAccessorReadinessAttestation,
        nonce_digest: str,
        requested_at: datetime,
    ) -> None:
        lease = source.authorization_lease
        if (
            lifecycle.request_nonce_digest != nonce_digest
            or readiness.request_nonce_digest != nonce_digest
            or lifecycle.observed_at < requested_at
            or readiness.observed_at < requested_at
            or lifecycle.observed_at >= lifecycle.valid_until
            or readiness.observed_at >= readiness.valid_until
            or lifecycle.protected_resident_context_id != lease.protected_resident_context_id
            or readiness.protected_resident_context_id != lease.protected_resident_context_id
            or lifecycle.protected_resident_context_digest
            != lease.protected_resident_context_digest
            or readiness.protected_resident_context_digest
            != lease.protected_resident_context_digest
            or lifecycle.valid_until > lease.valid_until
            or readiness.valid_until > lease.valid_until
            or lifecycle.valid_until > lease.protected_resident_context_usable_until
            or readiness.valid_until > lease.protected_resident_context_usable_until
            or lifecycle.resident_context_present is not True
            or lifecycle.resident_context_unexpired is not True
            or lifecycle.resident_context_unrevoked is not True
            or lifecycle.resident_context_undestroyed is not True
            or lifecycle.resident_context_unconsumed is not True
            or lifecycle.resident_context_handle_outstanding is not False
            or readiness.access_eligible is not True
            or readiness.atomic_compare_and_set_supported is not True
            or readiness.resident_context_unconsumed is not True
            or readiness.runtime_handle_outstanding is not False
            or readiness.runtime_handle_profile_confirmed is not True
            or readiness.runtime_handle_is_bearer_capability is not False
            or lifecycle.canonical_digest != canonical_digest(lifecycle.digest_payload())
            or readiness.canonical_digest != canonical_digest(readiness.digest_payload())
            or not self._lifecycle_signature_verifier.verify_lifecycle_attestation(lifecycle)
            or not self._readiness_signature_verifier.verify_accessor_readiness_attestation(
                readiness
            )
        ):
            self._raise("protected_resident_context_access_consumption_evidence_invalid")

    def _build_instruction(
        self, attempt: WorkflowProtectedResidentContextAccessConsumptionAttempt
    ) -> WorkflowProtectedResidentContextTrustedAccessorInstruction:
        return build_workflow_protected_resident_context_trusted_accessor_instruction(attempt)

    def _verify_receipt(
        self,
        receipt: WorkflowProtectedResidentContextTrustedAccessorReceipt,
        instruction: WorkflowProtectedResidentContextTrustedAccessorInstruction,
    ) -> None:
        for name in (
            "access_id",
            "attempt_id",
            "consumption_claim_id",
            "authorization_lease_id",
            "authorization_lease_digest",
            "protected_resident_context_id",
            "protected_resident_context_digest",
            "destination_boundary_id",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "accessor_contract_id",
            "accessor_contract_version",
            "accessor_id",
            "accessor_version",
            "runtime_handle_profile_id",
            "runtime_handle_profile_version",
            "runtime_handle_profile_digest",
        ):
            if getattr(receipt, name) != getattr(instruction, name):
                self._raise("protected_resident_context_access_consumption_receipt_invalid")
        state = receipt.state.value
        success = state == "handle_established_in_protected_boundary"
        known_failure = state == "resident_context_access_failed"
        if (
            receipt.instruction_digest != instruction.canonical_digest
            or receipt.completed_at < instruction.started_at
            or receipt.completed_at >= instruction.access_deadline
            or not (success or known_failure)
            or receipt.protected_resident_context_consumed is not True
            or receipt.runtime_handle_established_in_protected_boundary is not success
            or receipt.protected_runtime_handle_is_bearer_capability is not False
            or receipt.runtime_handle_locator_returned is not False
            or receipt.raw_context_returned is not False
            or receipt.endpoint_returned is not False
            or receipt.credential_returned is not False
            or receipt.secret_returned is not False
            or receipt.bearer_token_returned is not False
            or receipt.provider_payload_returned is not False
            or receipt.filesystem_activity_performed is not False
            or receipt.provider_activity_performed is not False
            or receipt.connector_activity_performed is not False
            or receipt.network_activity_performed is not False
            or receipt.readiness_probe_performed is not False
            or receipt.publication_performed is not False
            or receipt.delivery_performed is not False
            or receipt.dispatch_performed is not False
            or receipt.execution_performed is not False
            or receipt.infrastructure_mutation_performed is not False
            or (known_failure and receipt.runtime_handle_absence_confirmed is not True)
            or receipt.canonical_digest != canonical_digest(receipt.digest_payload())
            or self._accessor.verify_receipt(receipt) is not True
        ):
            self._raise("protected_resident_context_access_consumption_receipt_invalid")

    def _build_receipted_result(
        self,
        *,
        claim_digest: str,
        attempt: WorkflowProtectedResidentContextAccessConsumptionAttempt,
        receipt: WorkflowProtectedResidentContextTrustedAccessorReceipt,
        recorded_at: datetime,
    ) -> WorkflowProtectedResidentContextAccessConsumptionResult:
        return cast(
            WorkflowProtectedResidentContextAccessConsumptionResult,
            _construct_record(
                WorkflowProtectedResidentContextAccessConsumptionResult,
                sources=(receipt, attempt),
                aliases={
                    "attempt_digest": attempt.canonical_digest,
                    "consumption_claim_digest": claim_digest,
                    "accessor_receipt_digest": receipt.canonical_digest,
                    "outcome_known": True,
                    "recorded_at": recorded_at,
                    "authority": WorkflowProtectedResidentContextAccessConsumptionAuthority(),
                },
            ),
        )

    async def _record_uncertainty_if_due(
        self,
        *,
        claim_digest: str,
        attempt: WorkflowProtectedResidentContextAccessConsumptionAttempt,
    ) -> WorkflowProtectedResidentContextAccessConsumptionPresentation:
        try:
            recorded_at = await self._repository.get_authoritative_time()
        except Exception:
            return WorkflowProtectedResidentContextAccessConsumptionPresentation(attempt, None)
        if recorded_at < attempt.access_deadline:
            return WorkflowProtectedResidentContextAccessConsumptionPresentation(attempt, None)
        result = _construct_record(
            WorkflowProtectedResidentContextAccessConsumptionResult,
            sources=(attempt,),
            aliases={
                "attempt_digest": attempt.canonical_digest,
                "consumption_claim_digest": claim_digest,
                "accessor_receipt_digest": None,
                "state": (
                    WorkflowProtectedResidentContextAccessConsumptionResultState.ACCESS_OUTCOME_UNCERTAIN
                ),
                "failure_class": (
                    WorkflowProtectedResidentContextAccessConsumptionFailureClass.ACCESS_OUTCOME_UNCERTAIN
                ),
                "protected_runtime_handle_id": None,
                "protected_runtime_handle_digest": None,
                "protected_runtime_handle_created_at": None,
                "protected_runtime_handle_usable_until": None,
                "protected_resident_context_consumed": None,
                "runtime_handle_established_in_protected_boundary": False,
                "protected_runtime_handle_is_bearer_capability": False,
                "runtime_handle_absence_confirmed": False,
                "outcome_known": False,
                "completed_at": None,
                "recorded_at": recorded_at,
                "authority": WorkflowProtectedResidentContextAccessConsumptionAuthority(),
            },
        )
        try:
            write = (
                await self._repository.record_protected_resident_context_access_consumption_result(
                    WorkflowProtectedResidentContextAccessConsumptionResultRequest(
                        result=result,
                        receipt=None,
                        expected_claim_digest=claim_digest,
                        expected_attempt_digest=attempt.canonical_digest,
                    )
                )
            )
        except Exception:
            return WorkflowProtectedResidentContextAccessConsumptionPresentation(attempt, None)
        return WorkflowProtectedResidentContextAccessConsumptionPresentation(
            attempt,
            write.result
            if write.status
            in (
                WorkflowProtectedResidentContextAccessConsumptionResultWriteStatus.RECORDED,
                WorkflowProtectedResidentContextAccessConsumptionResultWriteStatus.REPLAY,
            )
            else None,
        )

    def _require_trusted_components(self) -> None:
        if (
            not self._lifecycle_attestor.available
            or not self._readiness_attestor.available
            or not self._accessor.available
            or self._accessor.accessor_contract_id != self._policy.required_accessor_contract_id
            or self._accessor.accessor_contract_version
            != self._policy.required_accessor_contract_version
            or self._accessor.accessor_id != self._policy.approved_accessor_id
            or self._accessor.accessor_version != self._policy.approved_accessor_version
            or self._accessor.runtime_handle_profile_id != self._policy.runtime_handle_profile_id
            or self._accessor.runtime_handle_profile_version
            != self._policy.runtime_handle_profile_version
            or self._accessor.runtime_handle_profile_digest
            != self._policy.runtime_handle_profile_digest
        ):
            self._raise(
                "protected_resident_context_access_consumption_trusted_component_unavailable"
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
            or not isinstance(values["idempotency_key"], str)
            or not 8 <= len(values["idempotency_key"]) <= 128
        ):
            self._raise("protected_resident_context_access_consumption_request_invalid")
        for name in ("authorization_lease_id", "policy_id", "policy_version", "idempotency_key"):
            value = values[name]
            if (
                not isinstance(value, str)
                or not value
                or value != value.strip()
                or len(value) > 240
                or any(character.isspace() for character in value)
            ):
                self._raise("protected_resident_context_access_consumption_request_invalid")

    def _resolve_replay(
        self, replay: WorkflowProtectedResidentContextAccessConsumptionReplayLookup
    ) -> WorkflowProtectedResidentContextAccessConsumptionPresentation | None:
        statuses = WorkflowProtectedResidentContextAccessConsumptionReplayStatus
        if replay.status is statuses.NONE:
            if replay.attempt is not None or replay.result is not None:
                self._raise("protected_resident_context_access_consumption_repository_violation")
            return None
        if replay.status is statuses.TERMINAL:
            if replay.attempt is None or replay.result is None:
                self._raise("protected_resident_context_access_consumption_repository_violation")
            return WorkflowProtectedResidentContextAccessConsumptionPresentation(
                replay.attempt, replay.result
            )
        if replay.status in (statuses.CLAIM_ONLY_PENDING, statuses.CLAIM_ONLY_UNCERTAIN):
            if replay.attempt is None or replay.result is not None:
                self._raise("protected_resident_context_access_consumption_repository_violation")
            return WorkflowProtectedResidentContextAccessConsumptionPresentation(
                replay.attempt, None
            )
        self._raise(f"protected_resident_context_access_consumption_{replay.status.value}")

    def _resolve_claim(
        self,
        status: WorkflowProtectedResidentContextAccessConsumptionClaimStatus,
        attempt: WorkflowProtectedResidentContextAccessConsumptionAttempt | None,
        result: WorkflowProtectedResidentContextAccessConsumptionResult | None,
    ) -> WorkflowProtectedResidentContextAccessConsumptionPresentation | None:
        statuses = WorkflowProtectedResidentContextAccessConsumptionClaimStatus
        if status is statuses.CLAIMED:
            return None
        if status is statuses.REPLAY_COMPLETED:
            if attempt is None or result is None:
                self._raise("protected_resident_context_access_consumption_repository_violation")
            return WorkflowProtectedResidentContextAccessConsumptionPresentation(attempt, result)
        if status in (statuses.CLAIM_ONLY_PENDING, statuses.CLAIM_ONLY_UNCERTAIN):
            if attempt is None or result is not None:
                self._raise("protected_resident_context_access_consumption_repository_violation")
            return WorkflowProtectedResidentContextAccessConsumptionPresentation(attempt, None)
        self._raise(f"protected_resident_context_access_consumption_{status.value}")

    async def _audit(
        self,
        *,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
        consumption_id: str,
        authorization_lease_id: str,
        outcome: str,
        result_code: str,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.workflow.protected-resident-context-access-consumption.claim",
                schema_version="1.0",
                producer=WORKFLOW_PROTECTED_RESIDENT_CONTEXT_ACCESS_CONSUMPTION_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.protected-resident-context-access-consumptions.create",
                resource_type="resource.workflow-protected-resident-context-access-consumption",
                scope_reference="/".join(
                    (*context.scope.canonical_value().values(), consumption_id)
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=None,
                target_metadata=(
                    ("consumption_id", consumption_id),
                    ("authorization_lease_id", authorization_lease_id),
                    ("protected_resident_context_access_authority", "false"),
                    ("target_context_capsule_opening_authority", "false"),
                    ("network_access_authority", "false"),
                    ("execution_authority", "false"),
                    ("infrastructure_mutation_authority", "false"),
                ),
            )
        )

    async def _export_audit_best_effort(self, **values: Any) -> None:
        try:
            await self._audit(**values)
        except Exception:
            return

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowProtectedResidentContextAccessConsumptionError(code)


def _construct_record(
    model: type[Any],
    *,
    sources: tuple[object, ...],
    aliases: dict[str, object],
) -> Any:
    values: dict[str, object] = {}
    for field in fields(model):
        if field.name == "canonical_digest":
            continue
        if field.name in aliases:
            values[field.name] = aliases[field.name]
            continue
        for source in sources:
            if hasattr(source, field.name):
                values[field.name] = getattr(source, field.name)
                break
        else:
            raise WorkflowProtectedResidentContextAccessConsumptionError(
                "protected_resident_context_access_consumption_domain_contract_violation"
            )
    return model(**cast(Any, values), canonical_digest=canonical_digest(_payload(values)))


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


__all__ = [
    "WORKFLOW_PROTECTED_RESIDENT_CONTEXT_ACCESS_CONSUMPTION_PRODUCER",
    "WorkflowProtectedResidentContextAccessConsumptionPresentation",
    "WorkflowProtectedResidentContextAccessConsumptionService",
]

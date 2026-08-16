from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.application.target_context_capsule_opening_ports import (
    WorkflowProtectedTargetContextCapsuleOpenabilityAttestation,
    WorkflowProtectedTargetContextCapsuleOpenabilityAttestationRequest,
    WorkflowProtectedTargetContextCapsuleOpenabilityAttestor,
    WorkflowProtectedTargetContextCapsuleOpeningAttestationSignatureVerifier,
    WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestation,
    WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestationRequest,
    WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestor,
    WorkflowProtectedTargetContextCapsuleTrustedOpener,
    WorkflowProtectedTransportTargetContextCapsuleOpeningClaimStatus,
    WorkflowProtectedTransportTargetContextCapsuleOpeningError,
    WorkflowProtectedTransportTargetContextCapsuleOpeningReplayStatus,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResultWriteStatus,
    WorkflowProtectedTransportTargetContextCapsuleOpeningSource,
    WorkflowTargetContextCapsuleOpeningClaimRequest,
    WorkflowTargetContextCapsuleOpeningReplayLookup,
    WorkflowTargetContextCapsuleOpeningReplayLookupRequest,
    WorkflowTargetContextCapsuleOpeningRepository,
    WorkflowTargetContextCapsuleOpeningResultRequest,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthority,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseEffectiveState,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseState,
    WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionPolicy,
    WorkflowProtectedTransportTargetContextCapsuleOpeningFailureClass,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResult,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResultState,
    WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerInstruction,
    WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy,
)

WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_OPENING_PRODUCER = (
    "project-atlas-workflow-protected-target-context-capsule-opener"
)


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation:
    attempt: WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt
    result: WorkflowProtectedTransportTargetContextCapsuleOpeningResult | None


@dataclass(frozen=True, slots=True)
class _ResolvedOpeningEvidence:
    source: WorkflowProtectedTransportTargetContextCapsuleOpeningSource
    custody: WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestation
    openability: WorkflowProtectedTargetContextCapsuleOpenabilityAttestation


class WorkflowProtectedTransportTargetContextCapsuleOpeningService:
    """Irreversibly consumes one opening lease before one trusted opener call."""

    def __init__(
        self,
        *,
        repository: WorkflowTargetContextCapsuleOpeningRepository,
        custody_attestor: WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestor,
        openability_attestor: WorkflowProtectedTargetContextCapsuleOpenabilityAttestor,
        attestation_signature_verifier: (
            WorkflowProtectedTargetContextCapsuleOpeningAttestationSignatureVerifier
        ),
        opener: WorkflowProtectedTargetContextCapsuleTrustedOpener,
        audit_sink: AuditSink,
        policy: WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionPolicy
        | None = None,
    ) -> None:
        self._repository = repository
        self._custody_attestor = custody_attestor
        self._openability_attestor = openability_attestor
        self._attestation_signature_verifier = attestation_signature_verifier
        self._opener = opener
        self._audit_sink = audit_sink
        self._policy = policy or (
            code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy()
        )

    @property
    def repository(self) -> WorkflowTargetContextCapsuleOpeningRepository:
        return self._repository

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def policy(self) -> WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionPolicy:
        return self._policy

    async def open(
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
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation:
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
            self._raise("target_context_capsule_opening_durable_repository_required")
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
        opening_id = f"workflow-target-context-capsule-opening.{seed[:24]}"
        replay = await self._repository.lookup_target_context_capsule_opening_replay(
            WorkflowTargetContextCapsuleOpeningReplayLookupRequest(
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
                opening_id=opening_id,
            )
        )
        historical = self._resolve_replay(replay)
        if historical is not None:
            return historical
        self._require_trusted_components()
        evidence = await self._load_and_attest(
            authorization_lease_id=authorization_lease_id,
            authorization_lease_digest=authorization_lease_digest,
            context=context,
        )
        claim_id = f"workflow-target-context-capsule-opening-claim.{seed[:24]}"
        attempt_id = f"workflow-target-context-capsule-opening-attempt.{seed[:24]}"
        audit_payload: dict[str, object] = {
            "schema_id": "audit.workflow-target-context-capsule-opening-consumption-authorization",
            "schema_version": "1.0",
            "event_type": "target_context_capsule_opening_lease_consumption_authorized",
            "claim_id": claim_id,
            "attempt_id": attempt_id,
            "opening_id": opening_id,
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

        async def required_precommit_audit() -> None:
            await self._audit(
                context=context,
                opening_id=opening_id,
                authorization_lease_id=authorization_lease_id,
                outcome="succeeded",
                result_code="target_context_capsule_opening_claim_ready",
            )

        claimed = await self._repository.claim_target_context_capsule_opening(
            WorkflowTargetContextCapsuleOpeningClaimRequest(
                claim_id=claim_id,
                attempt_id=attempt_id,
                opening_id=opening_id,
                source=evidence.source,
                custody_attestation=evidence.custody,
                openability_attestation=evidence.openability,
                expected_request_nonce_digest=evidence.custody.request_nonce_digest,
                offline_signature_verifier=self._attestation_signature_verifier,
                expected_policy_id=self._policy.policy_id,
                expected_policy_version=self._policy.policy_version,
                expected_policy_digest=self._policy.canonical_digest,
                expected_custody_attestor_id=self._policy.required_custody_attestor_id,
                expected_custody_attestor_version=(self._policy.required_custody_attestor_version),
                expected_openability_attestor_id=(self._policy.required_openability_attestor_id),
                expected_openability_attestor_version=(
                    self._policy.required_openability_attestor_version
                ),
                expected_opener_contract_id=self._policy.required_opener_contract_id,
                expected_opener_contract_version=self._policy.required_opener_contract_version,
                expected_opener_id=self._policy.approved_opener_id,
                expected_opener_version=self._policy.approved_opener_version,
                expected_trusted_opener_profile_digest=(self._policy.trusted_opener_profile_digest),
                expected_verification_signing_key_id=(self._policy.verification_signing_key_id),
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
                required_precommit_audit=required_precommit_audit,
            )
        )
        claim_presentation = self._resolve_claim(claimed.status, claimed.attempt, claimed.result)
        if claim_presentation is not None:
            return claim_presentation
        if claimed.claim is None or claimed.attempt is None or claimed.result is not None:
            self._raise("target_context_capsule_opening_claim_commit_uncertain")

        instruction = self._build_instruction(
            source=evidence.source,
            attempt=claimed.attempt,
        )
        try:
            receipt = await self._opener.open_capsule(instruction)
            self._verify_receipt(receipt, instruction)
            recorded_at = await self._repository.get_authoritative_time()
            result = self._build_receipted_result(
                source=evidence.source,
                claim_digest=claimed.claim.canonical_digest,
                attempt=claimed.attempt,
                receipt=receipt,
                recorded_at=recorded_at,
            )
            write = await self._repository.record_target_context_capsule_opening_result(
                WorkflowTargetContextCapsuleOpeningResultRequest(
                    result=result,
                    receipt=receipt,
                    expected_claim_digest=claimed.claim.canonical_digest,
                    expected_attempt_digest=claimed.attempt.canonical_digest,
                )
            )
        except Exception:
            return await self._record_uncertainty_if_due(
                source=evidence.source,
                claim_digest=claimed.claim.canonical_digest,
                attempt=claimed.attempt,
            )
        if (
            write.status
            not in (
                WorkflowProtectedTransportTargetContextCapsuleOpeningResultWriteStatus.RECORDED,
                WorkflowProtectedTransportTargetContextCapsuleOpeningResultWriteStatus.REPLAY,
            )
            or write.result is None
        ):
            return WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation(
                claimed.attempt, None
            )
        return WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation(
            claimed.attempt, write.result
        )

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation, ...]:
        if not self._repository.durable:
            self._raise("target_context_capsule_opening_durable_repository_required")
        attempts = await self._repository.list_target_context_capsule_opening_attempts(
            scope=scope, limit=limit
        )
        results = await self._repository.get_target_context_capsule_opening_results_by_opening_ids(
            scope=scope,
            opening_ids=tuple(attempt.opening_id for attempt in attempts),
        )
        by_opening = {result.opening_id: result for result in results}
        return tuple(
            WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation(
                attempt, by_opening.get(attempt.opening_id)
            )
            for attempt in attempts
        )

    async def _load_and_attest(
        self,
        *,
        authorization_lease_id: str,
        authorization_lease_digest: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> _ResolvedOpeningEvidence:
        source = await self._repository.get_target_context_capsule_opening_source(
            authorization_lease_id=authorization_lease_id
        )
        if source is None:
            self._raise("target_context_capsule_opening_lease_not_found")
        self._validate_source(
            source,
            authorization_lease_digest=authorization_lease_digest,
            context=context,
        )
        lease = source.lease
        nonce_digest = canonical_digest(
            {"authorization_lease_digest": authorization_lease_digest, "nonce": uuid4().hex}
        )
        custody_request = WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestationRequest(
            authorization_lease_id=lease.authorization_lease_id,
            authorization_lease_digest=lease.canonical_digest,
            handoff_id=lease.handoff_id,
            handoff_result_digest=lease.handoff_result_digest,
            sealed_capsule_id=lease.sealed_capsule_id,
            sealed_capsule_digest=lease.sealed_capsule_digest,
            consumer_receipt_id=lease.consumer_receipt_id,
            consumer_receipt_digest=lease.receipt_digest,
            destination_boundary_id=lease.destination_boundary_id,
            destination_deployment_id=lease.destination_deployment_id,
            destination_generation=lease.destination_generation,
            destination_fencing_token_digest=lease.destination_fencing_token_digest,
            custody_contract_id=lease.custody_contract_id,
            custody_contract_version=lease.custody_contract_version,
            scope=lease.scope,
            consumer_subject_id=lease.consumer_subject_id,
            consumer_audience=lease.consumer_audience,
            consumer_contract_id=lease.consumer_contract_id,
            consumer_contract_version=lease.consumer_contract_version,
            purpose_id=lease.purpose_id,
            request_nonce_digest=nonce_digest,
            requested_at=context.requested_at,
        )
        openability_request = WorkflowProtectedTargetContextCapsuleOpenabilityAttestationRequest(
            authorization_lease_id=lease.authorization_lease_id,
            authorization_lease_digest=lease.canonical_digest,
            sealed_capsule_id=lease.sealed_capsule_id,
            sealed_capsule_digest=lease.sealed_capsule_digest,
            consumer_receipt_id=lease.consumer_receipt_id,
            consumer_receipt_digest=lease.receipt_digest,
            capsule_schema_id=source.capsule_schema_id,
            capsule_schema_version=source.capsule_schema_version,
            consumer_subject_id=lease.consumer_subject_id,
            consumer_audience=lease.consumer_audience,
            consumer_contract_id=lease.consumer_contract_id,
            consumer_contract_version=lease.consumer_contract_version,
            purpose_id=lease.purpose_id,
            destination_boundary_id=lease.destination_boundary_id,
            destination_deployment_id=lease.destination_deployment_id,
            destination_generation=lease.destination_generation,
            destination_fencing_token_digest=lease.destination_fencing_token_digest,
            custody_contract_id=lease.custody_contract_id,
            custody_contract_version=lease.custody_contract_version,
            opener_contract_id=self._policy.required_opener_contract_id,
            opener_contract_version=self._policy.required_opener_contract_version,
            opener_id=self._policy.approved_opener_id,
            opener_version=self._policy.approved_opener_version,
            verification_signing_key_id=self._policy.verification_signing_key_id,
            trusted_opener_profile_digest=self._policy.trusted_opener_profile_digest,
            scope=lease.scope,
            request_nonce_digest=nonce_digest,
            requested_at=context.requested_at,
        )
        try:
            custody = await self._custody_attestor.attest_opening_custody(custody_request)
            openability = await self._openability_attestor.attest_capsule_openability(
                openability_request
            )
            now = await self._repository.get_authoritative_time()
        except WorkflowProtectedTransportTargetContextCapsuleOpeningError:
            raise
        except Exception:
            self._raise("target_context_capsule_opening_evidence_conflict")
        self._validate_attestations(
            custody=custody,
            openability=openability,
            custody_request=custody_request,
            openability_request=openability_request,
            evaluated_at=now,
        )
        if (
            lease.effective_state(evaluated_at=now)
            is not (
                WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseEffectiveState
            ).ACTIVE
        ):
            self._raise("target_context_capsule_opening_evidence_conflict")
        return _ResolvedOpeningEvidence(source, custody, openability)

    def _validate_attestations(
        self,
        *,
        custody: WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestation,
        openability: WorkflowProtectedTargetContextCapsuleOpenabilityAttestation,
        custody_request: WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestationRequest,
        openability_request: WorkflowProtectedTargetContextCapsuleOpenabilityAttestationRequest,
        evaluated_at: datetime,
    ) -> None:
        custody_expected = _request_bound_fields(custody_request)
        openability_expected = _request_bound_fields(openability_request)
        if (
            any(getattr(custody, name) != value for name, value in custody_expected.items())
            or any(
                getattr(openability, name) != value for name, value in openability_expected.items()
            )
            or custody.attestor_id != self._policy.required_custody_attestor_id
            or custody.attestor_version != self._policy.required_custody_attestor_version
            or openability.attestor_id != self._policy.required_openability_attestor_id
            or openability.attestor_version != self._policy.required_openability_attestor_version
            or custody.observed_at < custody_request.requested_at
            or openability.observed_at < openability_request.requested_at
            or custody.observed_at > evaluated_at
            or openability.observed_at > evaluated_at
            or custody.valid_until <= evaluated_at
            or openability.valid_until <= evaluated_at
            or custody.capsule_remains_sealed is not True
            or custody.destination_custody_final is not True
            or custody.source_reuse_authority_terminated is not True
            or custody.sealed_capsule_is_bearer_capability is not False
            or custody.consumer_receipt_is_bearer_capability is not False
            or custody.runtime_authority_granted is not False
            or custody.runtime_authority_count != 0
            or custody.revoked is not False
            or custody.destroyed is not False
            or openability.acceptance_eligible is not True
            or openability.capsule_openable is not True
            or openability.exact_capsule_binding_confirmed is not True
            or openability.protected_destination_confirmed is not True
            or openability.protected_resident_context_profile_confirmed is not True
            or openability.sealed_capsule_is_bearer_capability is not False
            or openability.consumer_receipt_is_bearer_capability is not False
            or openability.raw_material_return_authorized is not False
            or openability.runtime_handle_creation_authorized is not False
            or openability.network_activity_authorized is not False
            or openability.delivery_authorized is not False
            or openability.execution_authorized is not False
            or custody.canonical_digest != canonical_digest(custody.digest_payload())
            or openability.canonical_digest != canonical_digest(openability.digest_payload())
            or self._attestation_signature_verifier.verify_opening_custody_attestation(custody)
            is not True
            or self._attestation_signature_verifier.verify_capsule_openability_attestation(
                openability
            )
            is not True
        ):
            self._raise("target_context_capsule_opening_evidence_conflict")

    @staticmethod
    def _validate_source(
        source: WorkflowProtectedTransportTargetContextCapsuleOpeningSource,
        *,
        authorization_lease_digest: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> None:
        lease = source.lease
        authority = lease.authority.canonical_value()
        if (
            lease.canonical_digest != authorization_lease_digest
            or lease.scope != context.scope
            or lease.consumer_subject_id != context.subject_id
            or lease.consumer_audience != context.credential_audience
            or lease.state
            is not (
                WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseState
            ).AUTHORIZED_UNCONSUMED
            or authority.get("target_context_capsule_opening_authorized") is not True
            or any(
                value is not False
                for name, value in authority.items()
                if name != "target_context_capsule_opening_authorized"
            )
            or not source.capsule_schema_id
            or not source.capsule_schema_version
        ):
            raise WorkflowProtectedTransportTargetContextCapsuleOpeningError(
                "target_context_capsule_opening_evidence_conflict"
            )

    def _build_instruction(
        self,
        *,
        source: WorkflowProtectedTransportTargetContextCapsuleOpeningSource,
        attempt: WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt,
    ) -> WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerInstruction:
        values: dict[str, object] = {
            "opening_id": attempt.opening_id,
            "attempt_id": attempt.attempt_id,
            "consumption_claim_id": attempt.consumption_claim_id,
            "authorization_lease_id": attempt.authorization_lease_id,
            "authorization_lease_digest": attempt.authorization_lease_digest,
            "sealed_capsule_id": attempt.sealed_capsule_id,
            "sealed_capsule_digest": attempt.sealed_capsule_digest,
            "consumer_receipt_id": attempt.consumer_receipt_id,
            "consumer_receipt_digest": attempt.consumer_receipt_digest,
            "sealed_capsule_is_bearer_capability": False,
            "consumer_receipt_is_bearer_capability": False,
            "consumer_subject_id": attempt.consumer_subject_id,
            "consumer_audience": attempt.consumer_audience,
            "consumer_contract_id": attempt.consumer_contract_id,
            "consumer_contract_version": attempt.consumer_contract_version,
            "purpose_id": attempt.purpose_id,
            "policy_id": attempt.policy_id,
            "policy_version": attempt.policy_version,
            "policy_digest": attempt.policy_digest,
            "required_opener_contract_id": attempt.required_opener_contract_id,
            "required_opener_contract_version": attempt.required_opener_contract_version,
            "approved_opener_id": attempt.approved_opener_id,
            "approved_opener_version": attempt.approved_opener_version,
            "destination_boundary_id": attempt.destination_boundary_id,
            "destination_deployment_id": attempt.destination_deployment_id,
            "destination_generation": attempt.destination_generation,
            "destination_fencing_token_digest": attempt.destination_fencing_token_digest,
            "custody_contract_id": attempt.custody_contract_id,
            "custody_contract_version": attempt.custody_contract_version,
            "trusted_opener_profile_digest": attempt.trusted_opener_profile_digest,
            "custody_attestation_digest": attempt.custody_attestation_digest,
            "openability_attestation_digest": attempt.openability_attestation_digest,
            "started_at": attempt.started_at,
            "opening_deadline": attempt.opening_deadline,
        }
        del source
        return WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerInstruction(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    def _verify_receipt(
        self,
        receipt: WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt,
        instruction: WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerInstruction,
    ) -> None:
        if (
            receipt.opening_id != instruction.opening_id
            or receipt.attempt_id != instruction.attempt_id
            or receipt.consumption_claim_id != instruction.consumption_claim_id
            or receipt.instruction_digest != instruction.canonical_digest
            or receipt.authorization_lease_id != instruction.authorization_lease_id
            or receipt.authorization_lease_digest != instruction.authorization_lease_digest
            or receipt.sealed_capsule_id != instruction.sealed_capsule_id
            or receipt.sealed_capsule_digest != instruction.sealed_capsule_digest
            or receipt.consumer_receipt_id != instruction.consumer_receipt_id
            or receipt.consumer_receipt_digest != instruction.consumer_receipt_digest
            or receipt.opener_contract_id != self._policy.required_opener_contract_id
            or receipt.opener_contract_version != self._policy.required_opener_contract_version
            or receipt.opener_id != self._policy.approved_opener_id
            or receipt.opener_version != self._policy.approved_opener_version
            or receipt.completed_at < instruction.started_at
            or receipt.completed_at >= instruction.opening_deadline
            or receipt.raw_target_context_returned is not False
            or receipt.runtime_handle_created is not False
            or receipt.network_activity_performed is not False
            or receipt.delivery_performed is not False
            or receipt.execution_performed is not False
            or receipt.protected_source_closed is not True
            or receipt.source_capsule_zeroized is not True
            or receipt.canonical_digest != canonical_digest(receipt.digest_payload())
            or self._opener.verify_receipt(receipt) is not True
        ):
            self._raise("target_context_capsule_opening_receipt_invalid")

    def _build_receipted_result(
        self,
        *,
        source: WorkflowProtectedTransportTargetContextCapsuleOpeningSource,
        claim_digest: str,
        attempt: WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt,
        receipt: WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt,
        recorded_at: datetime,
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningResult:
        values: dict[str, object] = {
            "opening_id": attempt.opening_id,
            "attempt_id": attempt.attempt_id,
            "attempt_digest": attempt.canonical_digest,
            "consumption_claim_id": attempt.consumption_claim_id,
            "consumption_claim_digest": claim_digest,
            "authorization_lease_id": attempt.authorization_lease_id,
            "authorization_lease_digest": attempt.authorization_lease_digest,
            "consumer_binding_id": attempt.consumer_binding_id,
            "consumer_binding_digest": attempt.consumer_binding_digest,
            "sealed_capsule_id": attempt.sealed_capsule_id,
            "sealed_capsule_digest": attempt.sealed_capsule_digest,
            "consumer_receipt_id": attempt.consumer_receipt_id,
            "consumer_receipt_digest": attempt.consumer_receipt_digest,
            "scope": attempt.scope,
            "consumer_subject_id": attempt.consumer_subject_id,
            "consumer_audience": attempt.consumer_audience,
            "consumer_contract_id": attempt.consumer_contract_id,
            "consumer_contract_version": attempt.consumer_contract_version,
            "purpose_id": attempt.purpose_id,
            "policy_id": attempt.policy_id,
            "policy_version": attempt.policy_version,
            "policy_digest": attempt.policy_digest,
            "opener_id": receipt.opener_id,
            "opener_version": receipt.opener_version,
            "opening_receipt_digest": receipt.canonical_digest,
            "state": receipt.state,
            "failure_class": receipt.failure_class,
            "protected_resident_context_id": receipt.protected_resident_context_id,
            "protected_resident_context_digest": receipt.protected_resident_context_digest,
            "protected_resident_context_is_bearer_capability": False,
            "capsule_opened_in_protected_boundary": (receipt.capsule_opened_in_protected_boundary),
            "target_context_pair_verified": receipt.target_context_pair_verified,
            "outcome_known": True,
            "protected_source_closed": receipt.protected_source_closed,
            "source_capsule_zeroized": receipt.source_capsule_zeroized,
            "completed_at": receipt.completed_at,
            "recorded_at": recorded_at,
            "opening_deadline": attempt.opening_deadline,
            "authority": WorkflowProtectedTransportTargetContextCapsuleOpeningAuthority(),
        }
        del source
        return WorkflowProtectedTransportTargetContextCapsuleOpeningResult(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    async def _record_uncertainty_if_due(
        self,
        *,
        source: WorkflowProtectedTransportTargetContextCapsuleOpeningSource,
        claim_digest: str,
        attempt: WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt,
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation:
        try:
            recorded_at = await self._repository.get_authoritative_time()
        except Exception:
            return WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation(attempt, None)
        if recorded_at < attempt.opening_deadline:
            return WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation(attempt, None)
        values: dict[str, object] = {
            "opening_id": attempt.opening_id,
            "attempt_id": attempt.attempt_id,
            "attempt_digest": attempt.canonical_digest,
            "consumption_claim_id": attempt.consumption_claim_id,
            "consumption_claim_digest": claim_digest,
            "authorization_lease_id": attempt.authorization_lease_id,
            "authorization_lease_digest": attempt.authorization_lease_digest,
            "consumer_binding_id": attempt.consumer_binding_id,
            "consumer_binding_digest": attempt.consumer_binding_digest,
            "sealed_capsule_id": attempt.sealed_capsule_id,
            "sealed_capsule_digest": attempt.sealed_capsule_digest,
            "consumer_receipt_id": attempt.consumer_receipt_id,
            "consumer_receipt_digest": attempt.consumer_receipt_digest,
            "scope": attempt.scope,
            "consumer_subject_id": attempt.consumer_subject_id,
            "consumer_audience": attempt.consumer_audience,
            "consumer_contract_id": attempt.consumer_contract_id,
            "consumer_contract_version": attempt.consumer_contract_version,
            "purpose_id": attempt.purpose_id,
            "policy_id": attempt.policy_id,
            "policy_version": attempt.policy_version,
            "policy_digest": attempt.policy_digest,
            "opener_id": attempt.approved_opener_id,
            "opener_version": attempt.approved_opener_version,
            "opening_receipt_digest": None,
            "state": (
                WorkflowProtectedTransportTargetContextCapsuleOpeningResultState.OPENING_OUTCOME_UNCERTAIN
            ),
            "failure_class": (
                WorkflowProtectedTransportTargetContextCapsuleOpeningFailureClass.OPENING_OUTCOME_UNCERTAIN
            ),
            "protected_resident_context_id": None,
            "protected_resident_context_digest": None,
            "protected_resident_context_is_bearer_capability": False,
            "capsule_opened_in_protected_boundary": False,
            "target_context_pair_verified": False,
            "outcome_known": False,
            "protected_source_closed": False,
            "source_capsule_zeroized": False,
            "completed_at": None,
            "recorded_at": recorded_at,
            "opening_deadline": attempt.opening_deadline,
            "authority": WorkflowProtectedTransportTargetContextCapsuleOpeningAuthority(),
        }
        del source
        result = WorkflowProtectedTransportTargetContextCapsuleOpeningResult(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )
        try:
            write = await self._repository.record_target_context_capsule_opening_result(
                WorkflowTargetContextCapsuleOpeningResultRequest(
                    result=result,
                    receipt=None,
                    expected_claim_digest=claim_digest,
                    expected_attempt_digest=attempt.canonical_digest,
                )
            )
        except Exception:
            return WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation(attempt, None)
        return WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation(
            attempt,
            write.result
            if write.status
            in (
                WorkflowProtectedTransportTargetContextCapsuleOpeningResultWriteStatus.RECORDED,
                WorkflowProtectedTransportTargetContextCapsuleOpeningResultWriteStatus.REPLAY,
            )
            else None,
        )

    def _require_trusted_components(self) -> None:
        if (
            not self._custody_attestor.available
            or not self._openability_attestor.available
            or not self._opener.available
            or self._opener.opener_contract_id != self._policy.required_opener_contract_id
            or self._opener.opener_contract_version != self._policy.required_opener_contract_version
            or self._opener.opener_id != self._policy.approved_opener_id
            or self._opener.opener_version != self._policy.approved_opener_version
        ):
            self._raise("target_context_capsule_opening_trusted_component_unavailable")

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
            self._raise("target_context_capsule_opening_request_invalid")
        for name in ("authorization_lease_id", "policy_id", "policy_version", "idempotency_key"):
            value = values[name]
            if (
                not isinstance(value, str)
                or not value
                or value != value.strip()
                or len(value) > 240
            ):
                self._raise("target_context_capsule_opening_request_invalid")

    def _resolve_replay(
        self, replay: WorkflowTargetContextCapsuleOpeningReplayLookup
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation | None:
        statuses = WorkflowProtectedTransportTargetContextCapsuleOpeningReplayStatus
        if replay.status is statuses.NONE:
            if replay.attempt is not None or replay.result is not None:
                self._raise("target_context_capsule_opening_repository_contract_violation")
            return None
        if replay.status is statuses.TERMINAL:
            if replay.attempt is None or replay.result is None:
                self._raise("target_context_capsule_opening_repository_contract_violation")
            return WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation(
                replay.attempt, replay.result
            )
        if replay.status in (statuses.CLAIM_ONLY_PENDING, statuses.CLAIM_ONLY_UNCERTAIN):
            if replay.attempt is None or replay.result is not None:
                self._raise("target_context_capsule_opening_repository_contract_violation")
            return WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation(
                replay.attempt, None
            )
        self._raise(f"target_context_capsule_opening_{replay.status.value}")

    def _resolve_claim(
        self,
        status: WorkflowProtectedTransportTargetContextCapsuleOpeningClaimStatus,
        attempt: WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt | None,
        result: WorkflowProtectedTransportTargetContextCapsuleOpeningResult | None,
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation | None:
        statuses = WorkflowProtectedTransportTargetContextCapsuleOpeningClaimStatus
        if status is statuses.CLAIMED:
            return None
        if status is statuses.REPLAY_COMPLETED:
            if attempt is None or result is None:
                self._raise("target_context_capsule_opening_repository_contract_violation")
            return WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation(
                attempt, result
            )
        if status in (statuses.CLAIM_ONLY_PENDING, statuses.CLAIM_ONLY_UNCERTAIN):
            if attempt is None or result is not None:
                self._raise("target_context_capsule_opening_repository_contract_violation")
            return WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation(attempt, None)
        self._raise(f"target_context_capsule_opening_{status.value}")

    async def _audit(
        self,
        *,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
        opening_id: str,
        authorization_lease_id: str,
        outcome: str,
        result_code: str,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.workflow.protected-target-context-capsule-opening.claim",
                schema_version="1.0",
                producer=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_OPENING_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.protected-target-context-capsule-openings.create",
                resource_type="resource.workflow-protected-target-context-capsule-opening",
                scope_reference="/".join((*context.scope.canonical_value().values(), opening_id)),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=None,
                target_metadata=(
                    ("opening_id", opening_id),
                    ("authorization_lease_id", authorization_lease_id),
                    ("target_context_capsule_opening_authority", "false"),
                    ("target_context_capsule_handoff_authority", "false"),
                    ("network_access_authority", "false"),
                    ("execution_authority", "false"),
                    ("infrastructure_mutation_authority", "false"),
                ),
            )
        )

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowProtectedTransportTargetContextCapsuleOpeningError(code)


def _request_bound_fields(value: Any) -> dict[str, object]:
    ignored = {"requested_at"}
    return {
        field.name: getattr(value, field.name)
        for field in fields(value)
        if field.name not in ignored
    }


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
    "WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_OPENING_PRODUCER",
    "WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation",
    "WorkflowProtectedTransportTargetContextCapsuleOpeningService",
]

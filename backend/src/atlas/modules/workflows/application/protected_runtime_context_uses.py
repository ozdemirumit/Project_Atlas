from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from hashlib import sha256
from typing import Any, NoReturn, cast

from atlas.modules.workflows.application.protected_runtime_context_use_ports import (
    WorkflowProtectedRuntimeContextTrustedUser,
    WorkflowProtectedRuntimeContextUseClaimRequest,
    WorkflowProtectedRuntimeContextUseClaimStatus,
    WorkflowProtectedRuntimeContextUseEligibilityAttestation,
    WorkflowProtectedRuntimeContextUseEligibilityAttestationRequest,
    WorkflowProtectedRuntimeContextUseEligibilityAttestor,
    WorkflowProtectedRuntimeContextUseEligibilitySignatureVerifier,
    WorkflowProtectedRuntimeContextUseError,
    WorkflowProtectedRuntimeContextUseInstructionSignatureVerifier,
    WorkflowProtectedRuntimeContextUseInstructionSigner,
    WorkflowProtectedRuntimeContextUseReceiptSignatureVerifier,
    WorkflowProtectedRuntimeContextUseReplayLookup,
    WorkflowProtectedRuntimeContextUseReplayLookupRequest,
    WorkflowProtectedRuntimeContextUseReplayStatus,
    WorkflowProtectedRuntimeContextUseRepository,
    WorkflowProtectedRuntimeContextUseResultRequest,
    WorkflowProtectedRuntimeContextUseResultWriteStatus,
    WorkflowProtectedRuntimeContextUseSource,
    build_workflow_protected_runtime_context_use_instruction,
    build_workflow_protected_runtime_context_use_invocation,
    build_workflow_protected_runtime_context_use_signed_instruction_envelope,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_context_use_domain import (
    WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNATURE_ALGORITHM,
    WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNING_KEY_ID,
    WorkflowProtectedRuntimeContextUseAttempt,
    WorkflowProtectedRuntimeContextUseAuthority,
    WorkflowProtectedRuntimeContextUseFailureClass,
    WorkflowProtectedRuntimeContextUseInstruction,
    WorkflowProtectedRuntimeContextUsePolicy,
    WorkflowProtectedRuntimeContextUseReceipt,
    WorkflowProtectedRuntimeContextUseResult,
    WorkflowProtectedRuntimeContextUseResultState,
    WorkflowProtectedRuntimeContextUseSignedInstructionEnvelope,
    code_owned_workflow_protected_runtime_context_use_policy,
)


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUsePresentation:
    attempt: WorkflowProtectedRuntimeContextUseAttempt
    result: WorkflowProtectedRuntimeContextUseResult | None


@dataclass(frozen=True, slots=True)
class _FreshUseEvidence:
    source: WorkflowProtectedRuntimeContextUseSource
    attestation: WorkflowProtectedRuntimeContextUseEligibilityAttestation


class WorkflowProtectedRuntimeContextUseService:
    """Adopts one context once inside the protected boundary without exporting it."""

    def __init__(
        self,
        *,
        repository: WorkflowProtectedRuntimeContextUseRepository,
        eligibility_attestor: WorkflowProtectedRuntimeContextUseEligibilityAttestor,
        eligibility_signature_verifier: (
            WorkflowProtectedRuntimeContextUseEligibilitySignatureVerifier
        ),
        trusted_user: WorkflowProtectedRuntimeContextTrustedUser,
        receipt_signature_verifier: WorkflowProtectedRuntimeContextUseReceiptSignatureVerifier,
        instruction_signer: WorkflowProtectedRuntimeContextUseInstructionSigner | None = None,
        instruction_signature_verifier: (
            WorkflowProtectedRuntimeContextUseInstructionSignatureVerifier | None
        ) = None,
        policy: WorkflowProtectedRuntimeContextUsePolicy | None = None,
    ) -> None:
        self._repository = repository
        self._eligibility_attestor = eligibility_attestor
        self._eligibility_signature_verifier = eligibility_signature_verifier
        self._trusted_user = trusted_user
        self._receipt_signature_verifier = receipt_signature_verifier
        self._instruction_signer = instruction_signer
        self._instruction_signature_verifier = instruction_signature_verifier
        self._policy = policy or code_owned_workflow_protected_runtime_context_use_policy()

    @property
    def repository(self) -> WorkflowProtectedRuntimeContextUseRepository:
        return self._repository

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def policy(self) -> WorkflowProtectedRuntimeContextUsePolicy:
        return self._policy

    async def use(
        self,
        *,
        authorization_consumption_result_id: str,
        authorization_consumption_result_digest: str,
        policy_id: str,
        policy_version: str,
        irreversible_use_acknowledged: bool,
        uncertainty_no_retry_acknowledged: bool,
        idempotency_key: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> WorkflowProtectedRuntimeContextUsePresentation:
        self._require_request(
            authorization_consumption_result_id=authorization_consumption_result_id,
            authorization_consumption_result_digest=authorization_consumption_result_digest,
            policy_id=policy_id,
            policy_version=policy_version,
            irreversible_use_acknowledged=irreversible_use_acknowledged,
            uncertainty_no_retry_acknowledged=uncertainty_no_retry_acknowledged,
            idempotency_key=idempotency_key,
            context=context,
        )
        if not self._repository.durable:
            self._raise("protected_runtime_context_use_durable_repository_required")

        idempotency_digest = canonical_digest(
            {
                "scope": context.scope.canonical_value(),
                "consumer_subject_id": context.subject_id,
                "consumer_audience": context.credential_audience,
                "idempotency_key_sha256": sha256(idempotency_key.encode()).hexdigest(),
            }
        )
        request_fingerprint = canonical_digest(
            {
                "authorization_consumption_result_id": authorization_consumption_result_id,
                "authorization_consumption_result_digest": (
                    authorization_consumption_result_digest
                ),
                "scope": context.scope.canonical_value(),
                "consumer_subject_id": context.subject_id,
                "consumer_audience": context.credential_audience,
                "policy_id": policy_id,
                "policy_version": policy_version,
                "policy_digest": self._policy.canonical_digest,
                "idempotency_digest": idempotency_digest,
                "irreversible_use_acknowledged": True,
                "uncertainty_no_retry_acknowledged": True,
            }
        )
        seed = canonical_digest(
            {
                "authorization_consumption_result_id": authorization_consumption_result_id,
                "authorization_consumption_result_digest": (
                    authorization_consumption_result_digest
                ),
                "idempotency_digest": idempotency_digest,
                "request_fingerprint": request_fingerprint,
            }
        )
        use_id = f"workflow-protected-runtime-context-use.{seed[:24]}"

        # This is deliberately the first repository call and precedes attestor/executor I/O.
        replay = await self._repository.lookup_protected_runtime_context_use_replay(
            WorkflowProtectedRuntimeContextUseReplayLookupRequest(
                authorization_consumption_result_id=authorization_consumption_result_id,
                authorization_consumption_result_digest=(authorization_consumption_result_digest),
                scope=context.scope,
                consumer_subject_id=context.subject_id,
                consumer_audience=context.credential_audience,
                policy_id=self._policy.policy_id,
                policy_version=self._policy.policy_version,
                policy_digest=self._policy.canonical_digest,
                idempotency_digest=idempotency_digest,
                request_fingerprint=request_fingerprint,
                use_id=use_id,
            )
        )
        historical = self._resolve_replay(replay)
        if historical is not None:
            return historical

        self._require_trusted_components()
        evidence = await self._load_and_attest(
            authorization_consumption_result_id=authorization_consumption_result_id,
            authorization_consumption_result_digest=authorization_consumption_result_digest,
            context=context,
        )
        claim_id = f"workflow-protected-runtime-context-use-claim.{seed[:24]}"
        attempt_id = f"workflow-protected-runtime-context-use-attempt.{seed[:24]}"
        audit_payload: dict[str, object] = {
            "schema_id": "audit.workflow-protected-runtime-context-use",
            "schema_version": "1.0",
            "event_type": "protected_runtime_context_use_claimed",
            "use_id": use_id,
            "claim_id": claim_id,
            "attempt_id": attempt_id,
            "authorization_consumption_result_id": authorization_consumption_result_id,
            "authorization_consumption_result_digest": authorization_consumption_result_digest,
            "scope": context.scope.canonical_value(),
            "consumer_subject_id": context.subject_id,
            "consumer_audience": context.credential_audience,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "idempotency_digest": idempotency_digest,
            "request_fingerprint": request_fingerprint,
            "irreversible_use_acknowledged": True,
            "uncertainty_no_retry_acknowledged": True,
            "runtime_started": False,
            "runtime_resumed": False,
            "network_activity_performed": False,
            "connector_activity_performed": False,
            "dispatch_performed": False,
            "execution_performed": False,
            "infrastructure_mutation_performed": False,
        }
        claimed = await self._repository.claim_protected_runtime_context_use(
            WorkflowProtectedRuntimeContextUseClaimRequest(
                claim_id=claim_id,
                attempt_id=attempt_id,
                use_id=use_id,
                source=evidence.source,
                eligibility_attestation=evidence.attestation,
                expected_request_nonce_digest=evidence.attestation.request_nonce_digest,
                offline_attestation_signature_verifier=self._eligibility_signature_verifier,
                expected_policy_id=self._policy.policy_id,
                expected_policy_version=self._policy.policy_version,
                expected_policy_digest=self._policy.canonical_digest,
                expected_attestor_id=self._policy.required_attestor_id,
                expected_attestor_version=self._policy.required_attestor_version,
                expected_executor_contract_id=self._policy.required_executor_contract_id,
                expected_executor_contract_version=(
                    self._policy.required_executor_contract_version
                ),
                expected_executor_id=self._policy.approved_executor_id,
                expected_executor_version=self._policy.approved_executor_version,
                expected_use_profile_id=self._policy.use_profile_id,
                expected_use_profile_version=self._policy.use_profile_version,
                expected_use_profile_digest=self._policy.use_profile_digest,
                expected_attestation_verification_signing_key_id=(
                    self._policy.attestation_verification_signing_key_id
                ),
                expected_receipt_verification_signing_key_id=(
                    self._policy.receipt_verification_signing_key_id
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
                irreversible_use_acknowledged=True,
                uncertainty_no_retry_acknowledged=True,
                use_authorization_audit_payload=audit_payload,
                use_authorization_audit_digest=canonical_digest(audit_payload),
            )
        )
        historical_after_claim = self._resolve_claim(
            claimed.status, claimed.attempt, claimed.result
        )
        if historical_after_claim is not None:
            return historical_after_claim
        if claimed.claim is None or claimed.attempt is None or claimed.result is not None:
            self._raise("protected_runtime_context_use_claim_commit_uncertain")

        instruction = build_workflow_protected_runtime_context_use_instruction(claimed.attempt)
        try:
            signed_instruction_envelope = (
                build_workflow_protected_runtime_context_use_signed_instruction_envelope(
                    instruction,
                    cast(
                        WorkflowProtectedRuntimeContextUseInstructionSigner,
                        self._instruction_signer,
                    ),
                )
            )
            self._verify_instruction_envelope(signed_instruction_envelope, instruction)
            invocation = build_workflow_protected_runtime_context_use_invocation(
                instruction, signed_instruction_envelope
            )
            receipt = await self._trusted_user.use_context(invocation)
            self._verify_receipt(receipt, instruction)
            recorded_at = await self._repository.get_authoritative_time()
            result = self._build_receipted_result(
                claim_digest=claimed.claim.canonical_digest,
                attempt=claimed.attempt,
                receipt=receipt,
                recorded_at=recorded_at,
            )
            write = await self._repository.record_protected_runtime_context_use_result(
                WorkflowProtectedRuntimeContextUseResultRequest(
                    result=result,
                    receipt=receipt,
                    expected_claim_digest=claimed.claim.canonical_digest,
                    expected_attempt_digest=claimed.attempt.canonical_digest,
                )
            )
        except Exception:
            return await self._record_uncertainty(
                claim_digest=claimed.claim.canonical_digest,
                attempt=claimed.attempt,
            )
        if (
            write.status
            not in (
                WorkflowProtectedRuntimeContextUseResultWriteStatus.RECORDED,
                WorkflowProtectedRuntimeContextUseResultWriteStatus.REPLAY,
            )
            or write.result is None
        ):
            return await self._record_uncertainty(
                claim_digest=claimed.claim.canonical_digest,
                attempt=claimed.attempt,
            )
        return WorkflowProtectedRuntimeContextUsePresentation(claimed.attempt, write.result)

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeContextUsePresentation, ...]:
        attempts = await self._repository.list_protected_runtime_context_use_attempts(
            scope=scope, limit=limit
        )
        results = await self._repository.get_protected_runtime_context_use_results(
            scope=scope, use_ids=tuple(attempt.use_id for attempt in attempts)
        )
        by_use_id = {result.use_id: result for result in results}
        return tuple(
            WorkflowProtectedRuntimeContextUsePresentation(attempt, by_use_id.get(attempt.use_id))
            for attempt in attempts
        )

    async def _load_and_attest(
        self,
        *,
        authorization_consumption_result_id: str,
        authorization_consumption_result_digest: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> _FreshUseEvidence:
        source = await self._repository.get_protected_runtime_context_use_source(
            authorization_consumption_result_id=authorization_consumption_result_id,
            authorization_consumption_result_digest=(authorization_consumption_result_digest),
        )
        if source is None:
            self._raise("protected_runtime_context_use_source_not_found")
        if (
            source.authorization_consumption_result.canonical_digest
            != authorization_consumption_result_digest
        ):
            self._raise("protected_runtime_context_use_source_invalid")
        now = await self._repository.get_authoritative_time()
        self._validate_source(source=source, scope=context.scope, evaluated_at=now)
        claim = source.authorization_consumption_claim
        result = source.authorization_consumption_result
        nonce_digest = canonical_digest(
            {
                "authorization_consumption_result_digest": result.canonical_digest,
                "evaluated_at": now.isoformat(),
                "scope": context.scope.canonical_value(),
            }
        )
        request = WorkflowProtectedRuntimeContextUseEligibilityAttestationRequest(
            authorization_consumption_result_id=result.result_id,
            authorization_consumption_result_digest=result.canonical_digest,
            authorization_consumption_claim_id=claim.consumption_claim_id,
            authorization_consumption_claim_digest=claim.canonical_digest,
            injection_result_id=claim.injection_result_id,
            injection_result_digest=claim.injection_result_digest,
            destination_deployment_id=claim.destination_deployment_id,
            destination_generation=claim.destination_generation,
            destination_fencing_token_digest=claim.destination_fencing_token_digest,
            runtime_slot_commitment=claim.runtime_slot_commitment,
            runtime_slot_generation=claim.runtime_slot_post_generation,
            injected_context_usable_until=claim.injected_context_usable_until,
            use_profile_id=claim.use_profile_id,
            use_profile_version=claim.use_profile_version,
            use_profile_digest=claim.use_profile_digest,
            executor_contract_id=self._policy.required_executor_contract_id,
            executor_contract_version=self._policy.required_executor_contract_version,
            executor_id=self._policy.approved_executor_id,
            executor_version=self._policy.approved_executor_version,
            scope=context.scope,
            consumer_subject_id=context.subject_id,
            consumer_audience=context.credential_audience,
            purpose_id=self._policy.purpose_id,
            request_nonce_digest=nonce_digest,
            requested_at=now,
        )
        attestation = await self._eligibility_attestor.attest_context_use_eligibility(request)
        self._validate_fresh_evidence(
            source=source,
            attestation=attestation,
            request=request,
        )
        return _FreshUseEvidence(source, attestation)

    def _validate_source(
        self,
        *,
        source: WorkflowProtectedRuntimeContextUseSource,
        scope: WorkflowScope,
        evaluated_at: datetime,
    ) -> None:
        claim = source.authorization_consumption_claim
        result = source.authorization_consumption_result
        forbidden_result_effects = (
            result.context_accessed,
            result.context_used,
            result.runtime_started,
            result.runtime_resumed,
            result.network_activity_performed,
            result.connector_activity_performed,
            result.readiness_probe_performed,
            result.publication_performed,
            result.delivery_performed,
            result.dispatch_performed,
            result.execution_performed,
            result.infrastructure_mutation_performed,
            result.renewal_created,
            result.transfer_created,
            result.replacement_created,
            result.retry_created,
        )
        if (
            result.state.value != self._policy.required_source_state
            or result.result_id == ""
            or result.consumption_claim_id != claim.consumption_claim_id
            or result.consumption_claim_digest != claim.canonical_digest
            or result.authorization_lease_id != claim.authorization_lease_id
            or result.authorization_lease_digest != claim.authorization_lease_digest
            or result.scope != scope
            or claim.scope != scope
            or result.consumer_subject_id != self._policy.consumer_subject_id
            or result.consumer_audience != self._policy.consumer_audience
            or claim.consumer_subject_id != self._policy.consumer_subject_id
            or claim.consumer_audience != self._policy.consumer_audience
            or result.authorization_lease_consumed is not True
            or result.historical_result_only is not True
            or any(forbidden_result_effects)
            or any(result.authority.canonical_value().values())
            or any(claim.authority.canonical_value().values())
            or claim.use_profile_id != self._policy.use_profile_id
            or claim.use_profile_version != self._policy.use_profile_version
            or claim.use_profile_digest != self._policy.use_profile_digest
            or claim.injected_context_usable_until <= evaluated_at
            or result.canonical_digest != canonical_digest(result.digest_payload())
            or claim.canonical_digest != canonical_digest(claim.digest_payload())
        ):
            self._raise("protected_runtime_context_use_source_invalid")

    def _validate_fresh_evidence(
        self,
        *,
        source: WorkflowProtectedRuntimeContextUseSource,
        attestation: WorkflowProtectedRuntimeContextUseEligibilityAttestation,
        request: WorkflowProtectedRuntimeContextUseEligibilityAttestationRequest,
    ) -> None:
        unsafe = (
            attestation.raw_context_included,
            attestation.runtime_handle_included,
            attestation.runtime_slot_locator_included,
            attestation.endpoint_included,
            attestation.credential_included,
            attestation.secret_included,
            attestation.bearer_token_included,
            attestation.runtime_start_authorized,
            attestation.runtime_resume_authorized,
            attestation.process_creation_authorized,
            attestation.prompt_construction_authorized,
            attestation.model_inference_authorized,
            attestation.connector_activity_authorized,
            attestation.network_activity_authorized,
            attestation.dispatch_authorized,
            attestation.execution_authorized,
            attestation.infrastructure_mutation_authorized,
        )
        bound_fields = (
            "authorization_consumption_result_id",
            "authorization_consumption_result_digest",
            "authorization_consumption_claim_id",
            "authorization_consumption_claim_digest",
            "injection_result_id",
            "injection_result_digest",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "runtime_slot_commitment",
            "runtime_slot_generation",
            "injected_context_usable_until",
            "use_profile_id",
            "use_profile_version",
            "use_profile_digest",
            "executor_contract_id",
            "executor_contract_version",
            "executor_id",
            "executor_version",
            "scope",
            "consumer_subject_id",
            "consumer_audience",
            "purpose_id",
            "request_nonce_digest",
        )
        if (
            any(getattr(attestation, name) != getattr(request, name) for name in bound_fields)
            or attestation.attestor_id != self._policy.required_attestor_id
            or attestation.attestor_version != self._policy.required_attestor_version
            or attestation.signing_key_id != self._policy.attestation_verification_signing_key_id
            or attestation.observed_at < request.requested_at
            or attestation.observed_at >= attestation.valid_until
            or attestation.valid_until
            > source.authorization_consumption_claim.injected_context_usable_until
            or attestation.context_present is not True
            or attestation.context_inert is not True
            or attestation.context_unexpired is not True
            or attestation.context_unrevoked is not True
            or attestation.context_uncleared is not True
            or attestation.context_unsuperseded is not True
            or attestation.context_unused is not True
            or attestation.use_count != 0
            or attestation.competing_use_absent is not True
            or attestation.destination_generation_current is not True
            or attestation.destination_fence_current is not True
            or attestation.runtime_slot_generation_current is not True
            or attestation.use_profile_eligible is not True
            or attestation.executor_profile_eligible is not True
            or attestation.atomic_compare_and_swap_supported is not True
            or any(unsafe)
            or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
            or not self._eligibility_signature_verifier.verify_context_use_eligibility_attestation(
                attestation
            )
        ):
            self._raise("protected_runtime_context_use_evidence_invalid")

    def _verify_receipt(
        self,
        receipt: WorkflowProtectedRuntimeContextUseReceipt,
        instruction: WorkflowProtectedRuntimeContextUseInstruction,
    ) -> None:
        bound_fields = (
            "protected_operation_reference",
            "authorization_consumption_result_id",
            "authorization_consumption_result_digest",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "runtime_slot_commitment",
            "runtime_slot_pre_generation",
            "use_profile_id",
            "use_profile_version",
            "use_profile_digest",
            "executor_contract_id",
            "executor_contract_version",
            "executor_id",
            "executor_version",
            "use_deadline",
        )
        if (
            any(getattr(receipt, name) != getattr(instruction, name) for name in bound_fields)
            or receipt.instruction_digest != instruction.canonical_digest
            or receipt.use_count_pre != instruction.expected_use_count_pre
            or (
                receipt.state
                is (
                    WorkflowProtectedRuntimeContextUseResultState
                ).CONTEXT_USED_ONCE_IN_PROTECTED_BOUNDARY
                and (
                    receipt.runtime_slot_post_generation
                    != instruction.expected_runtime_slot_post_generation
                    or receipt.use_count_post != instruction.expected_use_count_post
                )
            )
            or receipt.completed_at < instruction.started_at
            or receipt.completed_at >= instruction.use_deadline
            or receipt.signing_key_id != self._policy.receipt_verification_signing_key_id
            or receipt.canonical_digest != canonical_digest(receipt.digest_payload())
            or not self._receipt_signature_verifier.verify_receipt(receipt)
        ):
            self._raise("protected_runtime_context_use_receipt_invalid")

    def _verify_instruction_envelope(
        self,
        envelope: WorkflowProtectedRuntimeContextUseSignedInstructionEnvelope,
        instruction: WorkflowProtectedRuntimeContextUseInstruction,
    ) -> None:
        verifier = self._instruction_signature_verifier
        if (
            verifier is None
            or envelope.instruction != instruction
            or envelope.instruction.canonical_digest != instruction.canonical_digest
            or not verifier.verify_instruction_envelope(envelope)
        ):
            self._raise("protected_runtime_context_use_instruction_envelope_invalid")

    def _build_receipted_result(
        self,
        *,
        claim_digest: str,
        attempt: WorkflowProtectedRuntimeContextUseAttempt,
        receipt: WorkflowProtectedRuntimeContextUseReceipt,
        recorded_at: datetime,
    ) -> WorkflowProtectedRuntimeContextUseResult:
        values = _record_values(
            WorkflowProtectedRuntimeContextUseResult,
            sources=(receipt, attempt),
            aliases={
                "result_id": (
                    "workflow-protected-runtime-context-use-result."
                    f"{attempt.attempt_id.rsplit('.', 1)[-1]}"
                ),
                "attempt_digest": attempt.canonical_digest,
                "claim_digest": claim_digest,
                "executor_receipt_digest": receipt.canonical_digest,
                "outcome_known": True,
                "recorded_at": recorded_at,
                "authority": WorkflowProtectedRuntimeContextUseAuthority(),
            },
        )
        return WorkflowProtectedRuntimeContextUseResult(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    async def _record_uncertainty(
        self,
        *,
        claim_digest: str,
        attempt: WorkflowProtectedRuntimeContextUseAttempt,
    ) -> WorkflowProtectedRuntimeContextUsePresentation:
        try:
            recorded_at = await self._repository.get_authoritative_time()
            values = _record_values(
                WorkflowProtectedRuntimeContextUseResult,
                sources=(attempt,),
                aliases={
                    "result_id": (
                        "workflow-protected-runtime-context-use-result."
                        f"{attempt.attempt_id.rsplit('.', 1)[-1]}"
                    ),
                    "attempt_digest": attempt.canonical_digest,
                    "claim_digest": claim_digest,
                    "executor_contract_id": attempt.required_executor_contract_id,
                    "executor_contract_version": attempt.required_executor_contract_version,
                    "executor_id": attempt.approved_executor_id,
                    "executor_version": attempt.approved_executor_version,
                    "executor_receipt_digest": None,
                    "runtime_slot_post_generation": None,
                    "use_count_pre": attempt.expected_use_count_pre,
                    "use_count_post": None,
                    "state": (
                        WorkflowProtectedRuntimeContextUseResultState
                    ).CONTEXT_USE_OUTCOME_UNCERTAIN,
                    "failure_class": (
                        WorkflowProtectedRuntimeContextUseFailureClass
                    ).CONTEXT_USE_OUTCOME_UNCERTAIN,
                    "outcome_known": False,
                    "context_adopted": False,
                    "protected_runtime_context_use_performed": False,
                    "context_terminal_non_reusable": False,
                    "transient_material_zeroized": False,
                    "completed_at": None,
                    "recorded_at": recorded_at,
                    "authority": WorkflowProtectedRuntimeContextUseAuthority(),
                },
            )
            result = WorkflowProtectedRuntimeContextUseResult(
                **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
            )
            write = await self._repository.record_protected_runtime_context_use_result(
                WorkflowProtectedRuntimeContextUseResultRequest(
                    result=result,
                    receipt=None,
                    expected_claim_digest=claim_digest,
                    expected_attempt_digest=attempt.canonical_digest,
                )
            )
        except Exception:
            return WorkflowProtectedRuntimeContextUsePresentation(attempt, None)
        return WorkflowProtectedRuntimeContextUsePresentation(
            attempt,
            write.result
            if write.status
            in (
                WorkflowProtectedRuntimeContextUseResultWriteStatus.RECORDED,
                WorkflowProtectedRuntimeContextUseResultWriteStatus.REPLAY,
            )
            else None,
        )

    def _require_trusted_components(self) -> None:
        if (
            not self._eligibility_attestor.available
            or not self._trusted_user.available
            or self._instruction_signer is None
            or not self._instruction_signer.available
            or self._instruction_signature_verifier is None
            or self._instruction_signer.signing_key_id
            != WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNING_KEY_ID
            or self._instruction_signer.signature_algorithm
            != WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNATURE_ALGORITHM
            or self._trusted_user.executor_contract_id != self._policy.required_executor_contract_id
            or self._trusted_user.executor_contract_version
            != self._policy.required_executor_contract_version
            or self._trusted_user.executor_id != self._policy.approved_executor_id
            or self._trusted_user.executor_version != self._policy.approved_executor_version
            or self._trusted_user.use_profile_id != self._policy.use_profile_id
            or self._trusted_user.use_profile_version != self._policy.use_profile_version
            or self._trusted_user.use_profile_digest != self._policy.use_profile_digest
        ):
            self._raise("protected_runtime_context_use_trusted_component_unavailable")

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
            or values["irreversible_use_acknowledged"] is not True
            or values["uncertainty_no_retry_acknowledged"] is not True
            or not isinstance(values["idempotency_key"], str)
            or not 8 <= len(values["idempotency_key"]) <= 128
        ):
            self._raise("protected_runtime_context_use_request_invalid")
        for name in (
            "authorization_consumption_result_id",
            "authorization_consumption_result_digest",
            "policy_id",
            "policy_version",
            "idempotency_key",
        ):
            value = values[name]
            if (
                not isinstance(value, str)
                or not value
                or value != value.strip()
                or len(value) > 240
                or any(character.isspace() for character in value)
            ):
                self._raise("protected_runtime_context_use_request_invalid")
        digest = values["authorization_consumption_result_digest"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            self._raise("protected_runtime_context_use_request_invalid")

    def _resolve_replay(
        self, replay: WorkflowProtectedRuntimeContextUseReplayLookup
    ) -> WorkflowProtectedRuntimeContextUsePresentation | None:
        statuses = WorkflowProtectedRuntimeContextUseReplayStatus
        if replay.status is statuses.NONE:
            if replay.attempt is not None or replay.result is not None:
                self._raise("protected_runtime_context_use_repository_violation")
            return None
        if replay.status is statuses.TERMINAL:
            if replay.attempt is None or replay.result is None:
                self._raise("protected_runtime_context_use_repository_violation")
            return WorkflowProtectedRuntimeContextUsePresentation(replay.attempt, replay.result)
        if replay.status in (statuses.CLAIM_ONLY_PENDING, statuses.CLAIM_ONLY_UNCERTAIN):
            if replay.attempt is None or replay.result is not None:
                self._raise("protected_runtime_context_use_repository_violation")
            return WorkflowProtectedRuntimeContextUsePresentation(replay.attempt, None)
        self._raise(f"protected_runtime_context_use_{replay.status.value}")

    def _resolve_claim(
        self,
        status: WorkflowProtectedRuntimeContextUseClaimStatus,
        attempt: WorkflowProtectedRuntimeContextUseAttempt | None,
        result: WorkflowProtectedRuntimeContextUseResult | None,
    ) -> WorkflowProtectedRuntimeContextUsePresentation | None:
        statuses = WorkflowProtectedRuntimeContextUseClaimStatus
        if status is statuses.CLAIMED:
            return None
        if status is statuses.REPLAY_COMPLETED:
            if attempt is None or result is None:
                self._raise("protected_runtime_context_use_repository_violation")
            return WorkflowProtectedRuntimeContextUsePresentation(attempt, result)
        if status in (statuses.CLAIM_ONLY_PENDING, statuses.CLAIM_ONLY_UNCERTAIN):
            if attempt is None or result is not None:
                self._raise("protected_runtime_context_use_repository_violation")
            return WorkflowProtectedRuntimeContextUsePresentation(attempt, None)
        self._raise(f"protected_runtime_context_use_{status.value}")

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowProtectedRuntimeContextUseError(code)


def _record_values(
    model: type[Any], *, sources: tuple[object, ...], aliases: dict[str, object]
) -> dict[str, object]:
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
            raise WorkflowProtectedRuntimeContextUseError(
                "protected_runtime_context_use_domain_contract_violation"
            )
    return values


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
    "WorkflowProtectedRuntimeContextUsePresentation",
    "WorkflowProtectedRuntimeContextUseService",
]

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.protected_runtime_context_injection_authorization_ports import (  # noqa: E501
    WorkflowProtectedRuntimeHandleLifecycleAttestation,
    WorkflowProtectedRuntimeHandleLifecycleAttestationRequest,
    WorkflowProtectedRuntimeHandleLifecycleAttestor,
    WorkflowProtectedRuntimeHandleLifecycleSignatureVerifier,
)
from atlas.modules.workflows.application.protected_runtime_context_injection_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeContextInjectionConsumptionClaimRequest,
    WorkflowProtectedRuntimeContextInjectionConsumptionClaimStatus,
    WorkflowProtectedRuntimeContextInjectionConsumptionError,
    WorkflowProtectedRuntimeContextInjectionConsumptionReplayLookup,
    WorkflowProtectedRuntimeContextInjectionConsumptionReplayLookupRequest,
    WorkflowProtectedRuntimeContextInjectionConsumptionReplayStatus,
    WorkflowProtectedRuntimeContextInjectionConsumptionRepository,
    WorkflowProtectedRuntimeContextInjectionConsumptionResultRequest,
    WorkflowProtectedRuntimeContextInjectionConsumptionResultWriteStatus,
    WorkflowProtectedRuntimeContextInjectionConsumptionSource,
    WorkflowProtectedRuntimeContextTrustedInjector,
    WorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier,
    WorkflowProtectedRuntimeSlotReadinessAttestation,
    WorkflowProtectedRuntimeSlotReadinessAttestationRequest,
    WorkflowProtectedRuntimeSlotReadinessAttestor,
    WorkflowProtectedRuntimeSlotReadinessSignatureVerifier,
    build_workflow_protected_runtime_context_trusted_injector_instruction,
    build_workflow_protected_runtime_context_trusted_injector_invocation,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedRuntimeContextInjectionConsumptionAttempt,
    WorkflowProtectedRuntimeContextInjectionConsumptionAuthority,
    WorkflowProtectedRuntimeContextInjectionConsumptionFailureClass,
    WorkflowProtectedRuntimeContextInjectionConsumptionPolicy,
    WorkflowProtectedRuntimeContextInjectionConsumptionResult,
    WorkflowProtectedRuntimeContextInjectionConsumptionResultState,
    WorkflowProtectedRuntimeContextTrustedInjectorInstruction,
    WorkflowProtectedRuntimeContextTrustedInjectorReceipt,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_runtime_context_injection_consumption_policy,
)

WORKFLOW_PROTECTED_RUNTIME_CONTEXT_INJECTION_CONSUMPTION_PRODUCER = (
    "project-atlas-workflow-protected-runtime-context-injection-consumer"
)


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextInjectionConsumptionPresentation:
    attempt: WorkflowProtectedRuntimeContextInjectionConsumptionAttempt
    result: WorkflowProtectedRuntimeContextInjectionConsumptionResult | None


@dataclass(frozen=True, slots=True)
class _FreshInjectionEvidence:
    source: WorkflowProtectedRuntimeContextInjectionConsumptionSource
    lifecycle: WorkflowProtectedRuntimeHandleLifecycleAttestation
    readiness: WorkflowProtectedRuntimeSlotReadinessAttestation


class WorkflowProtectedRuntimeContextInjectionConsumptionService:
    """Consumes one ADR-168 lease before one trusted protected-slot CAS."""

    def __init__(
        self,
        *,
        repository: WorkflowProtectedRuntimeContextInjectionConsumptionRepository,
        lifecycle_attestor: WorkflowProtectedRuntimeHandleLifecycleAttestor,
        slot_readiness_attestor: WorkflowProtectedRuntimeSlotReadinessAttestor,
        lifecycle_signature_verifier: WorkflowProtectedRuntimeHandleLifecycleSignatureVerifier,
        slot_readiness_signature_verifier: (WorkflowProtectedRuntimeSlotReadinessSignatureVerifier),
        injector: WorkflowProtectedRuntimeContextTrustedInjector,
        receipt_signature_verifier: (
            WorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier
        ),
        audit_sink: AuditSink,
        policy: WorkflowProtectedRuntimeContextInjectionConsumptionPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._lifecycle_attestor = lifecycle_attestor
        self._slot_readiness_attestor = slot_readiness_attestor
        self._lifecycle_signature_verifier = lifecycle_signature_verifier
        self._slot_readiness_signature_verifier = slot_readiness_signature_verifier
        self._injector = injector
        self._receipt_signature_verifier = receipt_signature_verifier
        self._audit_sink = audit_sink
        self._policy = (
            policy or code_owned_workflow_protected_runtime_context_injection_consumption_policy()
        )

    @property
    def repository(self) -> WorkflowProtectedRuntimeContextInjectionConsumptionRepository:
        return self._repository

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def policy(self) -> WorkflowProtectedRuntimeContextInjectionConsumptionPolicy:
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
    ) -> WorkflowProtectedRuntimeContextInjectionConsumptionPresentation:
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
            self._raise(
                "protected_runtime_context_injection_consumption_durable_repository_required"
            )

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
        injection_id = f"workflow-protected-runtime-context-injection-consumption.{seed[:24]}"

        # Durable replay is deliberately the first repository operation and precedes every
        # attestor and injector call. Historical replay is entirely offline.
        replay = await (
            self._repository.lookup_protected_runtime_context_injection_consumption_replay(
                WorkflowProtectedRuntimeContextInjectionConsumptionReplayLookupRequest(
                    authorization_lease_id=authorization_lease_id,
                    scope=context.scope,
                    consumer_subject_id=context.subject_id,
                    consumer_audience=context.credential_audience,
                    policy_id=self._policy.policy_id,
                    policy_version=self._policy.policy_version,
                    policy_digest=self._policy.canonical_digest,
                    idempotency_digest=idempotency_digest,
                    request_fingerprint=request_fingerprint,
                    injection_id=injection_id,
                )
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
        claim_id = f"workflow-protected-runtime-context-injection-claim.{seed[:24]}"
        attempt_id = f"workflow-protected-runtime-context-injection-attempt.{seed[:24]}"
        lease = evidence.source.authorization_lease
        audit_payload: dict[str, object] = {
            "schema_id": "audit.workflow-protected-runtime-context-injection-consumption",
            "schema_version": "1.0",
            "event_type": "protected_runtime_context_injection_lease_consumption_authorized",
            "claim_id": claim_id,
            "attempt_id": attempt_id,
            "injection_id": injection_id,
            "authorization_lease_id": lease.authorization_lease_id,
            "authorization_lease_digest": lease.canonical_digest,
            "runtime_slot_commitment": evidence.readiness.runtime_slot_commitment,
            "runtime_slot_pre_generation": evidence.readiness.runtime_slot_pre_generation,
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
        claimed = await self._repository.claim_protected_runtime_context_injection_consumption(
            WorkflowProtectedRuntimeContextInjectionConsumptionClaimRequest(
                claim_id=claim_id,
                attempt_id=attempt_id,
                injection_id=injection_id,
                source=evidence.source,
                lifecycle_attestation=evidence.lifecycle,
                slot_readiness_attestation=evidence.readiness,
                expected_request_nonce_digest=evidence.lifecycle.request_nonce_digest,
                offline_lifecycle_signature_verifier=self._lifecycle_signature_verifier,
                offline_slot_readiness_signature_verifier=(self._slot_readiness_signature_verifier),
                expected_policy_id=self._policy.policy_id,
                expected_policy_version=self._policy.policy_version,
                expected_policy_digest=self._policy.canonical_digest,
                expected_lifecycle_attestor_id=self._policy.required_lifecycle_attestor_id,
                expected_lifecycle_attestor_version=(
                    self._policy.required_lifecycle_attestor_version
                ),
                expected_slot_readiness_attestor_id=(
                    self._policy.required_slot_readiness_attestor_id
                ),
                expected_slot_readiness_attestor_version=(
                    self._policy.required_slot_readiness_attestor_version
                ),
                expected_injector_contract_id=self._policy.required_injector_contract_id,
                expected_injector_contract_version=(
                    self._policy.required_injector_contract_version
                ),
                expected_injector_id=self._policy.approved_injector_id,
                expected_injector_version=self._policy.approved_injector_version,
                expected_runtime_slot_profile_id=self._policy.runtime_slot_profile_id,
                expected_runtime_slot_profile_version=(self._policy.runtime_slot_profile_version),
                expected_runtime_slot_profile_digest=self._policy.runtime_slot_profile_digest,
                expected_slot_readiness_verification_signing_key_id=(
                    self._policy.slot_readiness_verification_signing_key_id
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
                irreversible_consumption_acknowledged=True,
                uncertain_outcome_requires_new_authorization_acknowledged=True,
                consumption_authorization_audit_payload=audit_payload,
                consumption_authorization_audit_digest=canonical_digest(audit_payload),
            )
        )
        replay_after_claim = self._resolve_claim(claimed.status, claimed.attempt, claimed.result)
        if replay_after_claim is not None:
            return replay_after_claim
        if claimed.claim is None or claimed.attempt is None or claimed.result is not None:
            self._raise("protected_runtime_context_injection_consumption_claim_commit_uncertain")

        await self._export_audit_best_effort(
            context=context,
            injection_id=injection_id,
            authorization_lease_id=authorization_lease_id,
            outcome="succeeded",
            result_code="protected_runtime_context_injection_consumption_claim_committed",
        )

        instruction = build_workflow_protected_runtime_context_trusted_injector_instruction(
            claimed.attempt
        )
        invocation = build_workflow_protected_runtime_context_trusted_injector_invocation(
            instruction
        )
        try:
            receipt = await self._injector.inject_context(invocation)
            self._verify_receipt(receipt, instruction)
            recorded_at = await self._repository.get_authoritative_time()
            result = self._build_receipted_result(
                claim_digest=claimed.claim.canonical_digest,
                attempt=claimed.attempt,
                receipt=receipt,
                recorded_at=recorded_at,
            )
            write = await (
                self._repository.record_protected_runtime_context_injection_consumption_result(
                    WorkflowProtectedRuntimeContextInjectionConsumptionResultRequest(
                        result=result,
                        receipt=receipt,
                        expected_claim_digest=claimed.claim.canonical_digest,
                        expected_attempt_digest=claimed.attempt.canonical_digest,
                    )
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
                WorkflowProtectedRuntimeContextInjectionConsumptionResultWriteStatus.RECORDED,
                WorkflowProtectedRuntimeContextInjectionConsumptionResultWriteStatus.REPLAY,
            )
            or write.result is None
        ):
            return await self._record_uncertainty(
                claim_digest=claimed.claim.canonical_digest,
                attempt=claimed.attempt,
            )
        return WorkflowProtectedRuntimeContextInjectionConsumptionPresentation(
            claimed.attempt, write.result
        )

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeContextInjectionConsumptionPresentation, ...]:
        attempts = await (
            self._repository.list_protected_runtime_context_injection_consumption_attempts(
                scope=scope, limit=limit
            )
        )
        results = await (
            self._repository.get_protected_runtime_context_injection_consumption_results(
                scope=scope,
                injection_ids=tuple(attempt.injection_id for attempt in attempts),
            )
        )
        by_injection_id = {result.injection_id: result for result in results}
        return tuple(
            WorkflowProtectedRuntimeContextInjectionConsumptionPresentation(
                attempt, by_injection_id.get(attempt.injection_id)
            )
            for attempt in attempts
        )

    async def _load_and_attest(
        self,
        *,
        authorization_lease_id: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> _FreshInjectionEvidence:
        source = await self._repository.get_protected_runtime_context_injection_consumption_source(
            authorization_lease_id=authorization_lease_id
        )
        if source is None:
            self._raise("protected_runtime_context_injection_consumption_source_not_found")
        lease = source.authorization_lease
        now = await self._repository.get_authoritative_time()
        self._validate_source(source=source, scope=context.scope, evaluated_at=now)
        nonce_digest = canonical_digest(
            {
                "authorization_lease_digest": lease.canonical_digest,
                "evaluated_at": now.isoformat(),
                "scope": context.scope.canonical_value(),
            }
        )
        lifecycle_request = _construct(
            WorkflowProtectedRuntimeHandleLifecycleAttestationRequest,
            sources=(source.authorization_source, lease, self._policy),
            aliases={"request_nonce_digest": nonce_digest, "requested_at": now},
        )
        slot_request = _construct(
            WorkflowProtectedRuntimeSlotReadinessAttestationRequest,
            sources=(source.authorization_source, lease, self._policy),
            aliases={"request_nonce_digest": nonce_digest, "requested_at": now},
        )
        lifecycle = await self._lifecycle_attestor.attest_runtime_handle_lifecycle(
            lifecycle_request
        )
        readiness = await self._slot_readiness_attestor.attest_runtime_slot_readiness(slot_request)
        self._validate_fresh_evidence(
            source=source,
            lifecycle=lifecycle,
            readiness=readiness,
            nonce_digest=nonce_digest,
            requested_at=now,
        )
        return _FreshInjectionEvidence(source, lifecycle, readiness)

    def _validate_source(
        self,
        *,
        source: WorkflowProtectedRuntimeContextInjectionConsumptionSource,
        scope: WorkflowScope,
        evaluated_at: datetime,
    ) -> None:
        lease = source.authorization_lease
        lineage = source.authorization_source
        if (
            not lease.is_active(evaluated_at=evaluated_at)
            or lease.scope != scope
            or lease.consumer_subject_id != self._policy.consumer_subject_id
            or lease.consumer_audience != self._policy.consumer_audience
            or lease.protected_runtime_context_injection_authority_granted is not True
            or lease.lease_is_bearer_capability is not False
            or lease.protected_runtime_handle_digest != lineage.protected_runtime_handle_digest
            or lease.destination_boundary_id != lineage.destination_boundary_id
            or lease.destination_deployment_id != lineage.destination_deployment_id
            or lease.destination_generation != lineage.destination_generation
            or lease.destination_fencing_token_digest != lineage.destination_fencing_token_digest
            or lease.injector_contract_id != self._policy.required_injector_contract_id
            or lease.injector_contract_version != self._policy.required_injector_contract_version
            or lease.injector_id != self._policy.approved_injector_id
            or lease.injector_version != self._policy.approved_injector_version
            or lease.runtime_slot_profile_id != self._policy.runtime_slot_profile_id
            or lease.runtime_slot_profile_version != self._policy.runtime_slot_profile_version
            or lease.runtime_slot_profile_digest != self._policy.runtime_slot_profile_digest
        ):
            self._raise("protected_runtime_context_injection_consumption_source_invalid")

    def _validate_fresh_evidence(
        self,
        *,
        source: WorkflowProtectedRuntimeContextInjectionConsumptionSource,
        lifecycle: WorkflowProtectedRuntimeHandleLifecycleAttestation,
        readiness: WorkflowProtectedRuntimeSlotReadinessAttestation,
        nonce_digest: str,
        requested_at: datetime,
    ) -> None:
        lease = source.authorization_lease
        unsafe_lifecycle = (
            lifecycle.runtime_handle_is_bearer_capability,
            lifecycle.raw_context_included,
            lifecycle.runtime_handle_material_included,
            lifecycle.runtime_payload_included,
            lifecycle.runtime_handle_locator_included,
            lifecycle.endpoint_included,
            lifecycle.credential_included,
            lifecycle.secret_included,
            lifecycle.bearer_token_included,
            lifecycle.provider_payload_included,
            lifecycle.handle_lookup_authorized,
            lifecycle.handle_retrieval_authorized,
            lifecycle.handle_use_authorized,
            lifecycle.runtime_use_authorized,
            lifecycle.injection_consumption_outstanding,
            lifecycle.connector_activity_authorized,
            lifecycle.network_activity_authorized,
            lifecycle.readiness_probe_authorized,
            lifecycle.publication_authorized,
            lifecycle.delivery_authorized,
            lifecycle.dispatch_authorized,
            lifecycle.execution_authorized,
            lifecycle.infrastructure_mutation_authorized,
        )
        unsafe_readiness = (
            readiness.raw_context_included,
            readiness.runtime_handle_material_included,
            readiness.runtime_payload_included,
            readiness.runtime_slot_locator_included,
            readiness.endpoint_included,
            readiness.credential_included,
            readiness.bearer_token_included,
            readiness.connector_activity_authorized,
            readiness.network_activity_authorized,
            readiness.readiness_probe_authorized,
            readiness.execution_authorized,
            readiness.infrastructure_mutation_authorized,
        )
        if (
            lifecycle.request_nonce_digest != nonce_digest
            or readiness.request_nonce_digest != nonce_digest
            or lifecycle.observed_at < requested_at
            or readiness.observed_at < requested_at
            or lifecycle.observed_at >= lifecycle.valid_until
            or readiness.observed_at >= readiness.valid_until
            or lifecycle.valid_until > lease.valid_until
            or readiness.valid_until > lease.valid_until
            or lifecycle.valid_until > lease.protected_runtime_handle_usable_until
            or readiness.valid_until > lease.protected_runtime_handle_usable_until
            or lifecycle.protected_runtime_handle_digest != lease.protected_runtime_handle_digest
            or readiness.protected_runtime_handle_digest != lease.protected_runtime_handle_digest
            or lifecycle.runtime_handle_present is not True
            or lifecycle.runtime_handle_unexpired is not True
            or lifecycle.runtime_handle_unrevoked is not True
            or lifecycle.runtime_handle_undestroyed is not True
            or lifecycle.runtime_handle_uninjected is not True
            or lifecycle.runtime_handle_unused is not True
            or lifecycle.destination_generation_current is not True
            or lifecycle.destination_fence_current is not True
            or lifecycle.injector_profile_eligible is not True
            or lifecycle.runtime_slot_profile_eligible is not True
            or lifecycle.runtime_context_injection_authorized is not True
            or any(unsafe_lifecycle)
            or readiness.exact_runtime_slot_confirmed is not True
            or readiness.runtime_slot_empty is not True
            or readiness.runtime_slot_inert is not True
            or readiness.runtime_slot_eligible is not True
            or readiness.atomic_compare_and_swap_supported is not True
            or readiness.destination_generation_current is not True
            or readiness.destination_fence_current is not True
            or readiness.injector_profile_eligible is not True
            or readiness.runtime_autostart_disabled is not True
            or readiness.runtime_slot_pre_generation < 0
            or len(readiness.runtime_slot_commitment) != 64
            or any(unsafe_readiness)
            or lifecycle.canonical_digest != canonical_digest(lifecycle.digest_payload())
            or readiness.canonical_digest != canonical_digest(readiness.digest_payload())
            or not self._lifecycle_signature_verifier.verify_runtime_handle_lifecycle_attestation(
                lifecycle
            )
            or not self._slot_readiness_signature_verifier.verify_runtime_slot_readiness_attestation(  # noqa: E501
                readiness
            )
        ):
            self._raise("protected_runtime_context_injection_consumption_evidence_invalid")

    def _verify_receipt(
        self,
        receipt: WorkflowProtectedRuntimeContextTrustedInjectorReceipt,
        instruction: WorkflowProtectedRuntimeContextTrustedInjectorInstruction,
    ) -> None:
        for name in (
            "protected_operation_reference",
            "injector_contract_id",
            "injector_contract_version",
            "injector_id",
            "injector_version",
            "injection_deadline",
        ):
            if getattr(receipt, name) != getattr(instruction, name):
                self._raise("protected_runtime_context_injection_consumption_receipt_invalid")
        if (
            receipt.instruction_digest != instruction.canonical_digest
            or receipt.runtime_slot_pre_generation != instruction.runtime_slot_pre_generation
            or (
                receipt.state
                is WorkflowProtectedRuntimeContextInjectionConsumptionResultState.INJECTED_INTO_PROTECTED_RUNTIME_SLOT  # noqa: E501
                and receipt.runtime_slot_post_generation
                != instruction.expected_runtime_slot_post_generation
            )
            or receipt.completed_at < instruction.started_at
            or receipt.completed_at >= instruction.injection_deadline
            or receipt.signing_key_id != self._policy.receipt_verification_signing_key_id
            or receipt.canonical_digest != canonical_digest(receipt.digest_payload())
            or not self._receipt_signature_verifier.verify_receipt(receipt)
        ):
            self._raise("protected_runtime_context_injection_consumption_receipt_invalid")

    def _build_receipted_result(
        self,
        *,
        claim_digest: str,
        attempt: WorkflowProtectedRuntimeContextInjectionConsumptionAttempt,
        receipt: WorkflowProtectedRuntimeContextTrustedInjectorReceipt,
        recorded_at: datetime,
    ) -> WorkflowProtectedRuntimeContextInjectionConsumptionResult:
        values = _record_values(
            WorkflowProtectedRuntimeContextInjectionConsumptionResult,
            sources=(receipt, attempt),
            aliases={
                "result_id": (
                    "workflow-protected-runtime-context-injection-result."
                    f"{attempt.attempt_id.rsplit('.', 1)[-1]}"
                ),
                "attempt_digest": attempt.canonical_digest,
                "consumption_claim_digest": claim_digest,
                "injector_receipt_digest": receipt.canonical_digest,
                "outcome_known": True,
                "recorded_at": recorded_at,
                "authority": WorkflowProtectedRuntimeContextInjectionConsumptionAuthority(),
            },
        )
        return WorkflowProtectedRuntimeContextInjectionConsumptionResult(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    async def _record_uncertainty(
        self,
        *,
        claim_digest: str,
        attempt: WorkflowProtectedRuntimeContextInjectionConsumptionAttempt,
    ) -> WorkflowProtectedRuntimeContextInjectionConsumptionPresentation:
        try:
            recorded_at = await self._repository.get_authoritative_time()
            values = _record_values(
                WorkflowProtectedRuntimeContextInjectionConsumptionResult,
                sources=(attempt,),
                aliases={
                    "result_id": (
                        "workflow-protected-runtime-context-injection-result."
                        f"{attempt.attempt_id.rsplit('.', 1)[-1]}"
                    ),
                    "attempt_digest": attempt.canonical_digest,
                    "consumption_claim_digest": claim_digest,
                    "injector_contract_id": attempt.required_injector_contract_id,
                    "injector_contract_version": attempt.required_injector_contract_version,
                    "injector_id": attempt.approved_injector_id,
                    "injector_version": attempt.approved_injector_version,
                    "injector_receipt_digest": None,
                    "runtime_slot_post_generation": None,
                    "state": (
                        WorkflowProtectedRuntimeContextInjectionConsumptionResultState.INJECTION_OUTCOME_UNCERTAIN
                    ),
                    "failure_class": (
                        WorkflowProtectedRuntimeContextInjectionConsumptionFailureClass.INJECTION_OUTCOME_UNCERTAIN
                    ),
                    "outcome_known": False,
                    "protected_runtime_handle_consumed": None,
                    "inert_context_injected": False,
                    "runtime_slot_mutation_performed": False,
                    "completed_at": None,
                    "recorded_at": recorded_at,
                    "authority": WorkflowProtectedRuntimeContextInjectionConsumptionAuthority(),
                },
            )
            result = WorkflowProtectedRuntimeContextInjectionConsumptionResult(
                **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
            )
            write = await (
                self._repository.record_protected_runtime_context_injection_consumption_result(
                    WorkflowProtectedRuntimeContextInjectionConsumptionResultRequest(
                        result=result,
                        receipt=None,
                        expected_claim_digest=claim_digest,
                        expected_attempt_digest=attempt.canonical_digest,
                    )
                )
            )
        except Exception:
            return WorkflowProtectedRuntimeContextInjectionConsumptionPresentation(attempt, None)
        return WorkflowProtectedRuntimeContextInjectionConsumptionPresentation(
            attempt,
            write.result
            if write.status
            in (
                WorkflowProtectedRuntimeContextInjectionConsumptionResultWriteStatus.RECORDED,
                WorkflowProtectedRuntimeContextInjectionConsumptionResultWriteStatus.REPLAY,
            )
            else None,
        )

    def _require_trusted_components(self) -> None:
        if (
            not self._lifecycle_attestor.available
            or not self._slot_readiness_attestor.available
            or not self._injector.available
            or self._injector.injector_contract_id != self._policy.required_injector_contract_id
            or self._injector.injector_contract_version
            != self._policy.required_injector_contract_version
            or self._injector.injector_id != self._policy.approved_injector_id
            or self._injector.injector_version != self._policy.approved_injector_version
            or self._injector.runtime_slot_profile_id != self._policy.runtime_slot_profile_id
            or self._injector.runtime_slot_profile_version
            != self._policy.runtime_slot_profile_version
            or self._injector.runtime_slot_profile_digest
            != self._policy.runtime_slot_profile_digest
        ):
            self._raise(
                "protected_runtime_context_injection_consumption_trusted_component_unavailable"
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
            self._raise("protected_runtime_context_injection_consumption_request_invalid")
        for name in ("authorization_lease_id", "policy_id", "policy_version", "idempotency_key"):
            value = values[name]
            if (
                not isinstance(value, str)
                or not value
                or value != value.strip()
                or len(value) > 240
                or any(character.isspace() for character in value)
            ):
                self._raise("protected_runtime_context_injection_consumption_request_invalid")

    def _resolve_replay(
        self, replay: WorkflowProtectedRuntimeContextInjectionConsumptionReplayLookup
    ) -> WorkflowProtectedRuntimeContextInjectionConsumptionPresentation | None:
        statuses = WorkflowProtectedRuntimeContextInjectionConsumptionReplayStatus
        if replay.status is statuses.NONE:
            if replay.attempt is not None or replay.result is not None:
                self._raise("protected_runtime_context_injection_consumption_repository_violation")
            return None
        if replay.status is statuses.TERMINAL:
            if replay.attempt is None or replay.result is None:
                self._raise("protected_runtime_context_injection_consumption_repository_violation")
            return WorkflowProtectedRuntimeContextInjectionConsumptionPresentation(
                replay.attempt, replay.result
            )
        if replay.status in (statuses.CLAIM_ONLY_PENDING, statuses.CLAIM_ONLY_UNCERTAIN):
            if replay.attempt is None or replay.result is not None:
                self._raise("protected_runtime_context_injection_consumption_repository_violation")
            return WorkflowProtectedRuntimeContextInjectionConsumptionPresentation(
                replay.attempt, None
            )
        self._raise(f"protected_runtime_context_injection_consumption_{replay.status.value}")

    def _resolve_claim(
        self,
        status: WorkflowProtectedRuntimeContextInjectionConsumptionClaimStatus,
        attempt: WorkflowProtectedRuntimeContextInjectionConsumptionAttempt | None,
        result: WorkflowProtectedRuntimeContextInjectionConsumptionResult | None,
    ) -> WorkflowProtectedRuntimeContextInjectionConsumptionPresentation | None:
        statuses = WorkflowProtectedRuntimeContextInjectionConsumptionClaimStatus
        if status is statuses.CLAIMED:
            return None
        if status is statuses.REPLAY_COMPLETED:
            if attempt is None or result is None:
                self._raise("protected_runtime_context_injection_consumption_repository_violation")
            return WorkflowProtectedRuntimeContextInjectionConsumptionPresentation(attempt, result)
        if status in (statuses.CLAIM_ONLY_PENDING, statuses.CLAIM_ONLY_UNCERTAIN):
            if attempt is None or result is not None:
                self._raise("protected_runtime_context_injection_consumption_repository_violation")
            return WorkflowProtectedRuntimeContextInjectionConsumptionPresentation(attempt, None)
        self._raise(f"protected_runtime_context_injection_consumption_{status.value}")

    async def _audit(
        self,
        *,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
        injection_id: str,
        authorization_lease_id: str,
        outcome: str,
        result_code: str,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.workflow.protected-runtime-context-injection-consumption.claim",
                schema_version="1.0",
                producer=WORKFLOW_PROTECTED_RUNTIME_CONTEXT_INJECTION_CONSUMPTION_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.protected-runtime-context-injection-consumptions.create",
                resource_type="resource.workflow-protected-runtime-context-injection-consumption",
                scope_reference="/".join((*context.scope.canonical_value().values(), injection_id)),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=None,
                target_metadata=(
                    ("injection_id", injection_id),
                    ("authorization_lease_id", authorization_lease_id),
                    ("runtime_started", "false"),
                    ("network_access_authority", "false"),
                    ("connector_activity_authority", "false"),
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
        raise WorkflowProtectedRuntimeContextInjectionConsumptionError(code)


def _construct(model: type[Any], *, sources: tuple[object, ...], aliases: dict[str, object]) -> Any:
    values = _record_values(model, sources=sources, aliases=aliases)
    return model(**cast(Any, values))


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
            raise WorkflowProtectedRuntimeContextInjectionConsumptionError(
                "protected_runtime_context_injection_consumption_domain_contract_violation"
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
    "WORKFLOW_PROTECTED_RUNTIME_CONTEXT_INJECTION_CONSUMPTION_PRODUCER",
    "WorkflowProtectedRuntimeContextInjectionConsumptionPresentation",
    "WorkflowProtectedRuntimeContextInjectionConsumptionService",
]

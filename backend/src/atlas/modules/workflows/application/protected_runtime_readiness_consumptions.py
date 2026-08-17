from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.protected_runtime_readiness_consumption_ports import (
    WorkflowProtectedRuntimeReadinessAssessor,
    WorkflowProtectedRuntimeReadinessConsumptionClaimRequest,
    WorkflowProtectedRuntimeReadinessConsumptionClaimStatus,
    WorkflowProtectedRuntimeReadinessConsumptionError,
    WorkflowProtectedRuntimeReadinessConsumptionReplayLookup,
    WorkflowProtectedRuntimeReadinessConsumptionReplayLookupRequest,
    WorkflowProtectedRuntimeReadinessConsumptionReplayStatus,
    WorkflowProtectedRuntimeReadinessConsumptionRepository,
    WorkflowProtectedRuntimeReadinessConsumptionResultRequest,
    WorkflowProtectedRuntimeReadinessConsumptionResultWriteStatus,
    WorkflowProtectedRuntimeReadinessConsumptionSource,
    WorkflowProtectedRuntimeReadinessInstructionSignatureVerifier,
    WorkflowProtectedRuntimeReadinessInstructionSigner,
    WorkflowProtectedRuntimeReadinessReceiptSignatureVerifier,
    build_workflow_protected_runtime_readiness_instruction,
    build_workflow_protected_runtime_readiness_invocation,
    build_workflow_protected_runtime_readiness_signed_instruction_envelope,
    validate_workflow_protected_runtime_readiness_consumption_claim_request,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_readiness_authorization_domain import (
    WorkflowProtectedRuntimeReadinessAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_readiness_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_readiness_consumption_domain import (
    WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNATURE_ALGORITHM,
    WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNING_KEY_ID,
    WorkflowProtectedRuntimeReadinessAttempt,
    WorkflowProtectedRuntimeReadinessConsumptionAttemptState,
    WorkflowProtectedRuntimeReadinessConsumptionAuthority,
    WorkflowProtectedRuntimeReadinessConsumptionClaim,
    WorkflowProtectedRuntimeReadinessConsumptionFailureClass,
    WorkflowProtectedRuntimeReadinessConsumptionPolicy,
    WorkflowProtectedRuntimeReadinessConsumptionResultState,
    WorkflowProtectedRuntimeReadinessInstruction,
    WorkflowProtectedRuntimeReadinessReceipt,
    WorkflowProtectedRuntimeReadinessResult,
    WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope,
    code_owned_workflow_protected_runtime_readiness_consumption_policy,
)

_RUNTIME_READINESS_OUTCOME_UNCERTAIN_NO_RETRY = (
    "protected_runtime_readiness_outcome_uncertain_no_retry"
)
WORKFLOW_PROTECTED_RUNTIME_READINESS_CONSUMPTION_PRODUCER = (
    "project-atlas-workflow-protected-runtime-readiness-consumer"
)


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessConsumptionPresentation:
    attempt: WorkflowProtectedRuntimeReadinessAttempt
    result: WorkflowProtectedRuntimeReadinessResult | None


class WorkflowProtectedRuntimeReadinessConsumptionService:
    """Consumes one ADR-175 lease and assesses protected readiness at most once."""

    def __init__(
        self,
        *,
        repository: WorkflowProtectedRuntimeReadinessConsumptionRepository,
        assessor: WorkflowProtectedRuntimeReadinessAssessor,
        instruction_signer: WorkflowProtectedRuntimeReadinessInstructionSigner,
        instruction_signature_verifier: (
            WorkflowProtectedRuntimeReadinessInstructionSignatureVerifier
        ),
        receipt_signature_verifier: (WorkflowProtectedRuntimeReadinessReceiptSignatureVerifier),
        audit_sink: AuditSink,
        policy: WorkflowProtectedRuntimeReadinessConsumptionPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._assessor = assessor
        self._instruction_signer = instruction_signer
        self._instruction_signature_verifier = instruction_signature_verifier
        self._receipt_signature_verifier = receipt_signature_verifier
        self._audit_sink = audit_sink
        self._policy = (
            policy or code_owned_workflow_protected_runtime_readiness_consumption_policy()
        )

    @property
    def repository(self) -> WorkflowProtectedRuntimeReadinessConsumptionRepository:
        return self._repository

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def policy(self) -> WorkflowProtectedRuntimeReadinessConsumptionPolicy:
        return self._policy

    async def consume(
        self,
        *,
        authorization_lease_id: str,
        policy_id: str,
        policy_version: str,
        irreversible_consumption_acknowledged: bool,
        uncertainty_no_retry_acknowledged: bool,
        idempotency_key: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> WorkflowProtectedRuntimeReadinessConsumptionPresentation:
        self._require_request(
            authorization_lease_id=authorization_lease_id,
            policy_id=policy_id,
            policy_version=policy_version,
            irreversible_consumption_acknowledged=irreversible_consumption_acknowledged,
            uncertainty_no_retry_acknowledged=uncertainty_no_retry_acknowledged,
            idempotency_key=idempotency_key,
            context=context,
        )
        if not self._repository.durable:
            self._raise("protected_runtime_readiness_consumption_durable_repository_required")

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
                "authorization_lease_id": authorization_lease_id,
                "scope": context.scope.canonical_value(),
                "consumer_subject_id": context.subject_id,
                "consumer_audience": context.credential_audience,
                "policy_id": self._policy.policy_id,
                "policy_version": self._policy.policy_version,
                "policy_digest": self._policy.canonical_digest,
                "idempotency_digest": idempotency_digest,
                "irreversible_consumption_acknowledged": True,
                "uncertainty_no_retry_acknowledged": True,
            }
        )
        seed = canonical_digest(
            {
                "authorization_lease_id": authorization_lease_id,
                "idempotency_digest": idempotency_digest,
                "request_fingerprint": request_fingerprint,
            }
        )
        consumption_id = f"workflow-protected-runtime-readiness-consumption.{seed[:24]}"

        # ADR-176 requires durable replay to be the first repository operation.
        replay_request = WorkflowProtectedRuntimeReadinessConsumptionReplayLookupRequest(
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
        replay = await self._repository.lookup_protected_runtime_readiness_consumption_replay(
            replay_request
        )
        historical = self._resolve_replay(replay)
        if historical is not None:
            await self._postcommit_audit(
                context,
                result_code=self._audit_result_code("replayed", historical.result),
                attempt=historical.attempt,
                result=historical.result,
            )
            return historical

        self._require_trusted_components()
        source = await self._repository.get_protected_runtime_readiness_consumption_source(
            authorization_lease_id=authorization_lease_id
        )
        if source is None:
            self._raise("protected_runtime_readiness_consumption_source_unavailable")
        authoritative_time = await self._repository.get_authoritative_time()
        self._validate_source(source, authoritative_time, context.scope)

        claim = self._build_claim(
            source=source,
            claim_id=f"workflow-protected-runtime-readiness-consumption-claim.{seed[:24]}",
            attempt_id=f"workflow-protected-runtime-readiness-attempt.{seed[:24]}",
            consumption_id=consumption_id,
            scope=context.scope,
            idempotency_digest=idempotency_digest,
            request_fingerprint=request_fingerprint,
            claimed_at=authoritative_time,
        )
        attempt = self._build_attempt(
            source=source,
            claim=claim,
            started_at=authoritative_time,
            seed=seed,
        )
        instruction = build_workflow_protected_runtime_readiness_instruction(attempt)
        envelope = build_workflow_protected_runtime_readiness_signed_instruction_envelope(
            instruction, self._instruction_signer
        )
        self._verify_instruction_envelope(envelope, instruction)
        claim_request = WorkflowProtectedRuntimeReadinessConsumptionClaimRequest(
            source=source,
            candidate_claim=claim,
            candidate_attempt=attempt,
            signed_instruction_envelope=envelope,
            offline_instruction_signature_verifier=self._instruction_signature_verifier,
            expected_policy_id=self._policy.policy_id,
            expected_policy_version=self._policy.policy_version,
            expected_policy_digest=self._policy.canonical_digest,
            minimum_invocation_margin_milliseconds=(
                self._policy.minimum_invocation_margin_milliseconds
            ),
            idempotency_key=idempotency_key,
            idempotency_digest=idempotency_digest,
            request_fingerprint=request_fingerprint,
        )
        validate_workflow_protected_runtime_readiness_consumption_claim_request(claim_request)

        try:
            claimed = await self._repository.claim_protected_runtime_readiness_consumption(
                claim_request
            )
        except Exception as exc:
            raise WorkflowProtectedRuntimeReadinessConsumptionError(
                "protected_runtime_readiness_consumption_claim_commit_uncertain"
            ) from exc
        historical_after_claim = self._resolve_claim(
            claimed.status, claimed.attempt, claimed.result
        )
        if historical_after_claim is not None:
            await self._postcommit_audit(
                context,
                result_code=self._audit_result_code(
                    "claim_replayed", historical_after_claim.result
                ),
                attempt=historical_after_claim.attempt,
                result=historical_after_claim.result,
            )
            return historical_after_claim
        if claimed.claim != claim or claimed.attempt != attempt or claimed.result is not None:
            self._raise("protected_runtime_readiness_consumption_repository_violation")

        await self._postcommit_audit(
            context,
            result_code="protected_runtime_readiness_lease_consumed_attempt_committed",
            attempt=attempt,
        )
        await self._postcommit_audit(
            context,
            result_code="protected_runtime_readiness_assessor_invocation_intent_recorded",
            attempt=attempt,
        )
        try:
            receipt = await self._assessor.assess_runtime_readiness(
                build_workflow_protected_runtime_readiness_invocation(envelope)
            )
        except Exception:
            await self._postcommit_audit(
                context,
                result_code="protected_runtime_readiness_assessor_invocation_failed",
                attempt=attempt,
                occurred_at=datetime.now(UTC),
            )
            return await self._record_uncertainty(claim=claim, attempt=attempt, context=context)
        await self._postcommit_audit(
            context,
            result_code="protected_runtime_readiness_assessor_invocation_returned",
            attempt=attempt,
            occurred_at=datetime.now(UTC),
        )
        result: WorkflowProtectedRuntimeReadinessResult | None = None
        try:
            recorded_at = await self._repository.get_authoritative_time()
            if recorded_at >= attempt.invocation_deadline:
                self._raise("protected_runtime_readiness_receipt_arrived_after_deadline")
            self._verify_receipt(receipt, instruction)
            result = self._build_receipted_result(
                claim=claim,
                attempt=attempt,
                receipt=receipt,
                recorded_at=recorded_at,
            )
            write = await self._repository.record_protected_runtime_readiness_consumption_result(
                WorkflowProtectedRuntimeReadinessConsumptionResultRequest(
                    result=result,
                    receipt=receipt,
                    expected_claim_digest=claim.canonical_digest,
                    expected_attempt_digest=attempt.canonical_digest,
                )
            )
        except Exception:
            if result is not None:
                resolved = await self._resolve_result_write_ambiguity(
                    replay_request=replay_request,
                    attempt=attempt,
                    candidate_result=result,
                )
                if resolved is not None:
                    await self._postcommit_audit(
                        context,
                        result_code=self._audit_result_code(
                            "result_write_resolved", resolved.result
                        ),
                        attempt=resolved.attempt,
                        result=resolved.result,
                    )
                    return resolved
            return await self._record_uncertainty(claim=claim, attempt=attempt, context=context)
        if (
            write.status
            not in (
                WorkflowProtectedRuntimeReadinessConsumptionResultWriteStatus.RECORDED,
                WorkflowProtectedRuntimeReadinessConsumptionResultWriteStatus.REPLAY,
            )
            or write.result is None
        ):
            return await self._record_uncertainty(claim=claim, attempt=attempt, context=context)
        presentation = WorkflowProtectedRuntimeReadinessConsumptionPresentation(
            attempt, write.result
        )
        await self._postcommit_audit(
            context,
            result_code=self._audit_result_code("recorded", write.result),
            attempt=attempt,
            result=write.result,
        )
        return presentation

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeReadinessConsumptionPresentation, ...]:
        if not self._repository.durable:
            self._raise("protected_runtime_readiness_consumption_durable_repository_required")
        attempts = await self._repository.list_protected_runtime_readiness_attempts(
            scope=scope, limit=limit
        )
        results = await self._repository.get_protected_runtime_readiness_results(
            scope=scope,
            consumption_ids=tuple(attempt.consumption_id for attempt in attempts),
        )
        by_consumption_id = {result.consumption_id: result for result in results}
        return tuple(
            WorkflowProtectedRuntimeReadinessConsumptionPresentation(
                attempt, by_consumption_id.get(attempt.consumption_id)
            )
            for attempt in attempts
        )

    def _build_claim(
        self,
        *,
        source: WorkflowProtectedRuntimeReadinessConsumptionSource,
        claim_id: str,
        attempt_id: str,
        consumption_id: str,
        scope: WorkflowScope,
        idempotency_digest: str,
        request_fingerprint: str,
        claimed_at: datetime,
    ) -> WorkflowProtectedRuntimeReadinessConsumptionClaim:
        lease = source.authorization_lease
        values = _record_values(
            WorkflowProtectedRuntimeReadinessConsumptionClaim,
            sources=(lease,),
            aliases={
                "claim_id": claim_id,
                "consumption_id": consumption_id,
                "attempt_id": attempt_id,
                "authorization_lease_digest": lease.canonical_digest,
                "authorization_claim_id": lease.claim_id,
                "authorization_claim_digest": lease.claim_digest,
                "scope": scope,
                "consumer_subject_id": self._policy.consumer_subject_id,
                "consumer_audience": self._policy.consumer_audience,
                "consumer_contract_id": self._policy.consumer_contract_id,
                "consumer_contract_version": self._policy.consumer_contract_version,
                "purpose_id": self._policy.purpose_id,
                "policy_id": self._policy.policy_id,
                "policy_version": self._policy.policy_version,
                "policy_digest": self._policy.canonical_digest,
                "idempotency_digest": idempotency_digest,
                "request_fingerprint": request_fingerprint,
                "irreversible_consumption_acknowledged": True,
                "uncertainty_no_retry_acknowledged": True,
                "claimed_at": claimed_at,
                "authority": WorkflowProtectedRuntimeReadinessConsumptionAuthority(),
            },
        )
        return WorkflowProtectedRuntimeReadinessConsumptionClaim(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    def _build_attempt(
        self,
        *,
        source: WorkflowProtectedRuntimeReadinessConsumptionSource,
        claim: WorkflowProtectedRuntimeReadinessConsumptionClaim,
        started_at: datetime,
        seed: str,
    ) -> WorkflowProtectedRuntimeReadinessAttempt:
        lease = source.authorization_lease
        values = _record_values(
            WorkflowProtectedRuntimeReadinessAttempt,
            sources=(claim, lease),
            aliases={
                "claim_digest": claim.canonical_digest,
                "protected_operation_reference": (f"protected-runtime-readiness.{seed[:32]}"),
                "expected_assessment_count_pre": 0,
                "expected_assessment_count_post": 1,
                "assessor_contract_id": self._policy.required_assessor_contract_id,
                "assessor_contract_version": (self._policy.required_assessor_contract_version),
                "assessor_id": self._policy.approved_assessor_id,
                "assessor_version": self._policy.approved_assessor_version,
                "receipt_verification_signing_key_id": (
                    self._policy.receipt_verification_signing_key_id
                ),
                "request_nonce_digest": canonical_digest(
                    {
                        "attempt_id": claim.attempt_id,
                        "claim_digest": claim.canonical_digest,
                        "seed": seed,
                    }
                ),
                "started_at": started_at,
                "invocation_deadline": lease.effective_until,
                "state": (
                    WorkflowProtectedRuntimeReadinessConsumptionAttemptState
                ).RUNTIME_READINESS_ATTEMPT_STARTED,
                "authority": WorkflowProtectedRuntimeReadinessConsumptionAuthority(),
            },
        )
        return WorkflowProtectedRuntimeReadinessAttempt(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    def _build_receipted_result(
        self,
        *,
        claim: WorkflowProtectedRuntimeReadinessConsumptionClaim,
        attempt: WorkflowProtectedRuntimeReadinessAttempt,
        receipt: WorkflowProtectedRuntimeReadinessReceipt,
        recorded_at: datetime,
    ) -> WorkflowProtectedRuntimeReadinessResult:
        failed = (
            receipt.result_state
            is (
                WorkflowProtectedRuntimeReadinessConsumptionResultState
            ).RUNTIME_READINESS_FAILED_WITHOUT_ASSESSMENT
        )
        values = _record_values(
            WorkflowProtectedRuntimeReadinessResult,
            sources=(attempt,),
            aliases={
                "result_id": (
                    "workflow-protected-runtime-readiness-result."
                    f"{attempt.attempt_id.rsplit('.', 1)[-1]}"
                ),
                "attempt_digest": attempt.canonical_digest,
                "claim_digest": claim.canonical_digest,
                "state": receipt.result_state,
                "failure_class": (
                    (
                        WorkflowProtectedRuntimeReadinessConsumptionFailureClass
                    ).PROTECTED_ASSESSOR_REJECTED_WITHOUT_ASSESSMENT
                    if failed
                    else None
                ),
                "outcome_known": True,
                "assessment_performed": receipt.readiness_assessment_performed,
                "runtime_ready": receipt.runtime_ready,
                "assessor_receipt_digest": receipt.canonical_digest,
                "completed_at": receipt.completed_at,
                "recorded_at": recorded_at,
                "authority": WorkflowProtectedRuntimeReadinessConsumptionAuthority(),
            },
        )
        return WorkflowProtectedRuntimeReadinessResult(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    async def _record_uncertainty(
        self,
        *,
        claim: WorkflowProtectedRuntimeReadinessConsumptionClaim,
        attempt: WorkflowProtectedRuntimeReadinessAttempt,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> WorkflowProtectedRuntimeReadinessConsumptionPresentation:
        try:
            recorded_at = await self._repository.get_authoritative_time()
            values = _record_values(
                WorkflowProtectedRuntimeReadinessResult,
                sources=(attempt,),
                aliases={
                    "result_id": (
                        "workflow-protected-runtime-readiness-result."
                        f"{attempt.attempt_id.rsplit('.', 1)[-1]}"
                    ),
                    "attempt_digest": attempt.canonical_digest,
                    "claim_digest": claim.canonical_digest,
                    "state": (
                        WorkflowProtectedRuntimeReadinessConsumptionResultState
                    ).RUNTIME_READINESS_OUTCOME_UNCERTAIN,
                    "failure_class": (
                        WorkflowProtectedRuntimeReadinessConsumptionFailureClass
                    ).RUNTIME_READINESS_OUTCOME_UNCERTAIN,
                    "outcome_known": False,
                    "assessment_performed": None,
                    "runtime_ready": None,
                    "assessor_receipt_digest": None,
                    "completed_at": None,
                    "recorded_at": recorded_at,
                    "authority": WorkflowProtectedRuntimeReadinessConsumptionAuthority(),
                },
            )
            result = WorkflowProtectedRuntimeReadinessResult(
                **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
            )
            write = await self._repository.record_protected_runtime_readiness_consumption_result(
                WorkflowProtectedRuntimeReadinessConsumptionResultRequest(
                    result=result,
                    receipt=None,
                    expected_claim_digest=claim.canonical_digest,
                    expected_attempt_digest=attempt.canonical_digest,
                )
            )
        except Exception as exc:
            raise WorkflowProtectedRuntimeReadinessConsumptionError(
                _RUNTIME_READINESS_OUTCOME_UNCERTAIN_NO_RETRY
            ) from exc
        if (
            write.status
            not in (
                WorkflowProtectedRuntimeReadinessConsumptionResultWriteStatus.RECORDED,
                WorkflowProtectedRuntimeReadinessConsumptionResultWriteStatus.REPLAY,
            )
            or write.result is None
            or write.result.state
            is not (
                WorkflowProtectedRuntimeReadinessConsumptionResultState
            ).RUNTIME_READINESS_OUTCOME_UNCERTAIN
        ):
            self._raise(_RUNTIME_READINESS_OUTCOME_UNCERTAIN_NO_RETRY)
        presentation = WorkflowProtectedRuntimeReadinessConsumptionPresentation(
            attempt, write.result
        )
        await self._postcommit_audit(
            context,
            result_code="protected_runtime_readiness_outcome_uncertain",
            attempt=attempt,
            result=write.result,
        )
        return presentation

    async def _resolve_result_write_ambiguity(
        self,
        *,
        replay_request: WorkflowProtectedRuntimeReadinessConsumptionReplayLookupRequest,
        attempt: WorkflowProtectedRuntimeReadinessAttempt,
        candidate_result: WorkflowProtectedRuntimeReadinessResult,
    ) -> WorkflowProtectedRuntimeReadinessConsumptionPresentation | None:
        try:
            replay = await self._repository.lookup_protected_runtime_readiness_consumption_replay(
                replay_request
            )
        except Exception:
            return None
        if (
            replay.status is WorkflowProtectedRuntimeReadinessConsumptionReplayStatus.TERMINAL
            and replay.attempt == attempt
            and replay.result is not None
            and replay.result.canonical_digest == candidate_result.canonical_digest
        ):
            return WorkflowProtectedRuntimeReadinessConsumptionPresentation(
                replay.attempt, replay.result
            )
        return None

    async def _postcommit_audit(
        self,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
        *,
        result_code: str,
        attempt: WorkflowProtectedRuntimeReadinessAttempt,
        result: WorkflowProtectedRuntimeReadinessResult | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        metadata = [
            ("attempt_id", attempt.attempt_id),
            ("consumption_id", attempt.consumption_id),
            ("attempt_digest", attempt.canonical_digest),
            ("assessment_authority", "false"),
            ("execution_authority", "false"),
            ("infrastructure_mutation_authority", "false"),
        ]
        if result is not None:
            metadata.extend(
                (
                    ("result_id", result.result_id),
                    ("result_state", result.state.value),
                    ("result_digest", result.canonical_digest),
                )
            )
        try:
            await self._audit_sink.record(
                AuditRecord(
                    event_id=f"evt_{uuid4().hex}",
                    event_type="atlas.workflow.protected-runtime-readiness-consumption.observation",
                    schema_version="1.0",
                    producer=WORKFLOW_PROTECTED_RUNTIME_READINESS_CONSUMPTION_PRODUCER,
                    producer_version=__version__,
                    occurred_at=occurred_at or context.requested_at,
                    correlation_id=context.correlation_id,
                    subject_id=context.subject_id,
                    actor_type=context.actor_type,
                    authentication_method=context.authentication_method,
                    assurance_level="workload",
                    permission_id="workflow.protected-runtime-readiness-consumptions.create",
                    resource_type="resource.workflow-protected-runtime-readiness-consumption",
                    scope_reference="/".join(
                        (*context.scope.canonical_value().values(), "runtime-readiness")
                    ),
                    decision_id=context.decision_id,
                    outcome="succeeded",
                    result_code=result_code,
                    idempotency_key=None,
                    target_metadata=tuple(metadata),
                )
            )
        except Exception:
            return

    @staticmethod
    def _audit_result_code(
        prefix: str, result: WorkflowProtectedRuntimeReadinessResult | None
    ) -> str:
        suffix = "attempt_pending" if result is None else result.state.value
        return f"protected_runtime_readiness_{prefix}_{suffix}"

    def _validate_source(
        self,
        source: WorkflowProtectedRuntimeReadinessConsumptionSource,
        evaluated_at: datetime,
        scope: WorkflowScope,
    ) -> None:
        lease = source.authorization_lease
        authorization_claim = source.authorization_claim
        source_policy = code_owned_workflow_protected_runtime_readiness_authorization_policy()
        authority = lease.authority.canonical_value()
        readiness_request_authority = authority.pop("protected_runtime_readiness_authority_granted")
        remaining = lease.effective_until - evaluated_at
        if (
            lease.claim_id != authorization_claim.claim_id
            or lease.claim_digest != authorization_claim.canonical_digest
            or lease.scope != scope
            or lease.policy_id != source_policy.policy_id
            or lease.policy_version != source_policy.policy_version
            or lease.policy_digest != source_policy.canonical_digest
            or lease.state
            is not (WorkflowProtectedRuntimeReadinessAuthorizationLeaseState).AUTHORIZED_UNCONSUMED
            or not lease.is_active(evaluated_at=evaluated_at)
            or remaining
            < timedelta(milliseconds=self._policy.minimum_invocation_margin_milliseconds)
            or not readiness_request_authority
            or any(authority.values())
            or lease.consumer_subject_id != self._policy.consumer_subject_id
            or lease.consumer_audience != self._policy.consumer_audience
            or lease.consumer_contract_id != self._policy.consumer_contract_id
            or lease.consumer_contract_version != self._policy.consumer_contract_version
            or lease.readiness_profile_id != self._policy.readiness_profile_id
            or lease.readiness_profile_version != self._policy.readiness_profile_version
            or lease.readiness_profile_digest != self._policy.readiness_profile_digest
        ):
            self._raise("protected_runtime_readiness_consumption_source_invalid")

    def _verify_instruction_envelope(
        self,
        envelope: WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope,
        instruction: WorkflowProtectedRuntimeReadinessInstruction,
    ) -> None:
        if (
            envelope.instruction != instruction
            or not self._instruction_signature_verifier.verify_instruction_envelope(envelope)
        ):
            self._raise("protected_runtime_readiness_instruction_envelope_invalid")

    def _verify_receipt(
        self,
        receipt: WorkflowProtectedRuntimeReadinessReceipt,
        instruction: WorkflowProtectedRuntimeReadinessInstruction,
    ) -> None:
        exact = (
            (receipt.consumption_id, instruction.consumption_id),
            (receipt.attempt_id, instruction.attempt_id),
            (receipt.attempt_digest, instruction.attempt_digest),
            (receipt.claim_id, instruction.claim_id),
            (receipt.claim_digest, instruction.claim_digest),
            (receipt.instruction_digest, instruction.canonical_digest),
            (receipt.authorization_lease_id, instruction.authorization_lease_id),
            (receipt.authorization_lease_digest, instruction.authorization_lease_digest),
            (receipt.start_result_id, instruction.start_result_id),
            (receipt.start_result_digest, instruction.start_result_digest),
            (receipt.protected_operation_reference, instruction.protected_operation_reference),
            (receipt.destination_deployment_id, instruction.destination_deployment_id),
            (receipt.destination_generation, instruction.destination_generation),
            (
                receipt.destination_fencing_token_digest,
                instruction.destination_fencing_token_digest,
            ),
            (receipt.protected_slot_commitment, instruction.protected_slot_commitment),
            (receipt.protected_slot_generation, instruction.protected_slot_generation),
            (receipt.runtime_envelope_id, instruction.runtime_envelope_id),
            (receipt.runtime_envelope_commitment, instruction.runtime_envelope_commitment),
            (receipt.runtime_envelope_generation, instruction.runtime_envelope_generation),
            (receipt.readiness_profile_id, instruction.readiness_profile_id),
            (receipt.readiness_profile_version, instruction.readiness_profile_version),
            (receipt.readiness_profile_digest, instruction.readiness_profile_digest),
            (receipt.assessor_contract_id, instruction.assessor_contract_id),
            (receipt.assessor_contract_version, instruction.assessor_contract_version),
            (receipt.assessor_id, instruction.assessor_id),
            (receipt.assessor_version, instruction.assessor_version),
            (receipt.request_nonce_digest, instruction.request_nonce_digest),
            (receipt.started_at, instruction.started_at),
            (receipt.invocation_deadline, instruction.invocation_deadline),
        )
        if (
            any(observed != expected for observed, expected in exact)
            or receipt.completed_at < instruction.started_at
            or receipt.completed_at >= instruction.invocation_deadline
            or receipt.signing_key_id != self._policy.receipt_verification_signing_key_id
            or receipt.signature_algorithm != self._policy.receipt_signature_algorithm
            or not self._receipt_signature_verifier.verify_receipt(receipt)
        ):
            self._raise("protected_runtime_readiness_receipt_invalid")

    def _require_trusted_components(self) -> None:
        if (
            not self._assessor.available
            or not self._instruction_signer.available
            or not self._instruction_signature_verifier.available
            or not self._receipt_signature_verifier.available
            or self._instruction_signer.signing_key_id
            != WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNING_KEY_ID
            or self._instruction_signer.signature_algorithm
            != WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNATURE_ALGORITHM
            or self._policy.instruction_signing_key_id
            == self._policy.receipt_verification_signing_key_id
            or self._assessor.assessor_contract_id != self._policy.required_assessor_contract_id
            or self._assessor.assessor_contract_version
            != self._policy.required_assessor_contract_version
            or self._assessor.assessor_id != self._policy.approved_assessor_id
            or self._assessor.assessor_version != self._policy.approved_assessor_version
            or self._assessor.readiness_profile_id != self._policy.readiness_profile_id
            or self._assessor.readiness_profile_version != self._policy.readiness_profile_version
            or self._assessor.readiness_profile_digest != self._policy.readiness_profile_digest
        ):
            self._raise("protected_runtime_readiness_trusted_component_unavailable")

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
            or values["uncertainty_no_retry_acknowledged"] is not True
            or not isinstance(values["idempotency_key"], str)
            or not 8 <= len(values["idempotency_key"]) <= 128
        ):
            self._raise("protected_runtime_readiness_consumption_request_invalid")
        for name in (
            "authorization_lease_id",
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
                self._raise("protected_runtime_readiness_consumption_request_invalid")

    def _resolve_replay(
        self, replay: WorkflowProtectedRuntimeReadinessConsumptionReplayLookup
    ) -> WorkflowProtectedRuntimeReadinessConsumptionPresentation | None:
        statuses = WorkflowProtectedRuntimeReadinessConsumptionReplayStatus
        if replay.status is statuses.NONE:
            if replay.attempt is not None or replay.result is not None:
                self._raise("protected_runtime_readiness_consumption_repository_violation")
            return None
        if replay.status is statuses.TERMINAL:
            if replay.attempt is None or replay.result is None:
                self._raise("protected_runtime_readiness_consumption_repository_violation")
            return WorkflowProtectedRuntimeReadinessConsumptionPresentation(
                replay.attempt, replay.result
            )
        if replay.status is statuses.ATTEMPT_UNCERTAIN:
            if replay.attempt is None or replay.result is not None:
                self._raise("protected_runtime_readiness_consumption_repository_violation")
            self._raise(_RUNTIME_READINESS_OUTCOME_UNCERTAIN_NO_RETRY)
        if replay.status is statuses.ATTEMPT_PENDING:
            if replay.attempt is None or replay.result is not None:
                self._raise("protected_runtime_readiness_consumption_repository_violation")
            return WorkflowProtectedRuntimeReadinessConsumptionPresentation(replay.attempt, None)
        self._raise(f"protected_runtime_readiness_consumption_{replay.status.value}")

    def _resolve_claim(
        self,
        status: WorkflowProtectedRuntimeReadinessConsumptionClaimStatus,
        attempt: WorkflowProtectedRuntimeReadinessAttempt | None,
        result: WorkflowProtectedRuntimeReadinessResult | None,
    ) -> WorkflowProtectedRuntimeReadinessConsumptionPresentation | None:
        statuses = WorkflowProtectedRuntimeReadinessConsumptionClaimStatus
        if status is statuses.CLAIMED:
            return None
        if status is statuses.REPLAY_TERMINAL:
            if attempt is None or result is None:
                self._raise("protected_runtime_readiness_consumption_repository_violation")
            return WorkflowProtectedRuntimeReadinessConsumptionPresentation(attempt, result)
        if status is statuses.REPLAY_UNCERTAIN:
            if attempt is None or result is not None:
                self._raise("protected_runtime_readiness_consumption_repository_violation")
            self._raise(_RUNTIME_READINESS_OUTCOME_UNCERTAIN_NO_RETRY)
        if status is statuses.REPLAY_PENDING:
            if attempt is None or result is not None:
                self._raise("protected_runtime_readiness_consumption_repository_violation")
            return WorkflowProtectedRuntimeReadinessConsumptionPresentation(attempt, None)
        self._raise(f"protected_runtime_readiness_consumption_{status.value}")

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowProtectedRuntimeReadinessConsumptionError(code)


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
            raise WorkflowProtectedRuntimeReadinessConsumptionError(
                "protected_runtime_readiness_consumption_domain_contract_violation"
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
    "WorkflowProtectedRuntimeReadinessConsumptionPresentation",
    "WorkflowProtectedRuntimeReadinessConsumptionService",
]

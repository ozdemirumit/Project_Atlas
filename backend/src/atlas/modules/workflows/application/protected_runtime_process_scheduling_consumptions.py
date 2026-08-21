from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, NoReturn, cast

from atlas.modules.workflows.application.protected_runtime_process_scheduling_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessScheduler,
    WorkflowProtectedRuntimeProcessSchedulingClaimRequest,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionClaimStatus,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionError,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionReplayStatus,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionRepository,
    WorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier,
    WorkflowProtectedRuntimeProcessSchedulingInstructionSigner,
    WorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier,
    WorkflowProtectedRuntimeProcessSchedulingReplayLookupRequest,
    WorkflowProtectedRuntimeProcessSchedulingResultRequest,
    WorkflowProtectedRuntimeProcessSchedulingResultWriteStatus,
    build_workflow_protected_runtime_process_scheduling_instruction,
    build_workflow_protected_runtime_process_scheduling_invocation,
    build_workflow_protected_runtime_process_scheduling_signed_instruction_envelope,
)
from atlas.modules.workflows.domain.models import canonical_digest
from atlas.modules.workflows.domain.protected_runtime_process_scheduling_authorization_domain import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_process_scheduling_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_process_scheduling_consumption_domain import (
    WorkflowProtectedRuntimeProcessSchedulingAttempt,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionAttemptState,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionAuthority,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionClaim,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionFailureClass,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionPolicy,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState,
    WorkflowProtectedRuntimeProcessSchedulingReceipt,
    WorkflowProtectedRuntimeProcessSchedulingResult,
    code_owned_workflow_protected_runtime_process_scheduling_consumption_policy,
)


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingConsumptionPresentation:
    attempt: WorkflowProtectedRuntimeProcessSchedulingAttempt
    result: WorkflowProtectedRuntimeProcessSchedulingResult | None


class WorkflowProtectedRuntimeProcessSchedulingConsumptionService:
    """Atomically consumes one exact ADR-179 lease before one scheduler call."""

    def __init__(
        self,
        *,
        repository: WorkflowProtectedRuntimeProcessSchedulingConsumptionRepository,
        instruction_signer: WorkflowProtectedRuntimeProcessSchedulingInstructionSigner,
        instruction_signature_verifier: (
            WorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier
        ),
        receipt_signature_verifier: (
            WorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier
        ),
        scheduler: WorkflowProtectedRuntimeProcessScheduler,
        policy: WorkflowProtectedRuntimeProcessSchedulingConsumptionPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._instruction_signer = instruction_signer
        self._instruction_signature_verifier = instruction_signature_verifier
        self._receipt_signature_verifier = receipt_signature_verifier
        self._scheduler = scheduler
        self._policy = (
            policy or code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()
        )

    @property
    def repository(self) -> WorkflowProtectedRuntimeProcessSchedulingConsumptionRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowProtectedRuntimeProcessSchedulingConsumptionPolicy:
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
    ) -> WorkflowProtectedRuntimeProcessSchedulingConsumptionPresentation:
        self._validate_boundary(
            authorization_lease_id=authorization_lease_id,
            policy_id=policy_id,
            policy_version=policy_version,
            irreversible_consumption_acknowledged=irreversible_consumption_acknowledged,
            uncertainty_no_retry_acknowledged=uncertainty_no_retry_acknowledged,
            idempotency_key=idempotency_key,
        )
        if not self._repository.durable:
            self._raise("protected_runtime_process_scheduling_durable_repository_required")

        idempotency_digest = canonical_digest({"idempotency_key": idempotency_key})
        request_fingerprint = canonical_digest(
            {
                "authorization_lease_id": authorization_lease_id,
                "policy_id": policy_id,
                "policy_version": policy_version,
                "policy_digest": self._policy.canonical_digest,
                "primitive_digest": self._policy.primitive_digest,
            }
        )
        consumption_id = f"prps-consumption-{request_fingerprint[:32]}"
        replay = await self._repository.lookup_protected_runtime_process_scheduling_replay(
            WorkflowProtectedRuntimeProcessSchedulingReplayLookupRequest(
                authorization_lease_id=authorization_lease_id,
                policy_id=policy_id,
                policy_version=policy_version,
                policy_digest=self._policy.canonical_digest,
                idempotency_digest=idempotency_digest,
                request_fingerprint=request_fingerprint,
                consumption_id=consumption_id,
            )
        )
        replay_presentation = self._resolve_replay(replay.status, replay.attempt, replay.result)
        if replay_presentation is not None:
            return replay_presentation

        self._require_dependencies()
        source = await self._repository.get_protected_runtime_process_scheduling_consumption_source(
            authorization_lease_id=authorization_lease_id
        )
        if source is None:
            self._raise("protected_runtime_process_scheduling_authorization_not_found")
        now = await self._repository.get_authoritative_time()
        if now.tzinfo is None:
            self._raise("protected_runtime_process_scheduling_authoritative_time_invalid")
        lease = source.authorization_lease
        authorization_claim = source.authorization_claim
        source_policy = (
            code_owned_workflow_protected_runtime_process_scheduling_authorization_policy()
        )
        if (
            lease.authorization_lease_id != authorization_lease_id
            or lease.claim_id != authorization_claim.claim_id
            or lease.claim_digest != authorization_claim.canonical_digest
            or lease.policy_id != source_policy.policy_id
            or lease.policy_version != source_policy.policy_version
            or lease.policy_digest != source_policy.canonical_digest
            or lease.state
            is not (
                WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseState
            ).AUTHORIZED_UNCONSUMED
            or lease.single_use is not True
            or lease.renewable is not False
            or lease.transferable is not False
            or lease.lease_is_bearer_capability is not False
            or lease.authority.protected_runtime_process_scheduling_authority_granted is not True
            or authorization_claim.authority.protected_runtime_process_scheduling_authority_granted
            is not False
            or lease.scheduling_profile_id != self._policy.scheduling_profile_id
            or lease.scheduling_profile_version != self._policy.scheduling_profile_version
            or lease.scheduling_profile_digest != self._policy.scheduling_profile_digest
            or lease.consumer_subject_id != self._policy.consumer_subject_id
            or lease.consumer_audience != self._policy.consumer_audience
            or lease.consumer_contract_id != self._policy.consumer_contract_id
            or lease.consumer_contract_version != self._policy.consumer_contract_version
            or lease.process_created is not True
            or lease.process_sealed is not True
            or lease.process_suspended is not True
            or lease.process_scheduled is not False
            or lease.process_resumed is not False
            or lease.process_dispatched is not False
            or lease.process_executed is not False
            or not lease.is_active(evaluated_at=now)
        ):
            self._raise("protected_runtime_process_scheduling_authorization_invalid_or_expired")
        deadline = lease.valid_until
        if (
            now + timedelta(milliseconds=self._policy.minimum_invocation_margin_milliseconds)
            >= deadline
        ):
            self._raise("protected_runtime_process_scheduling_invocation_margin_insufficient")

        identity_digest = canonical_digest(
            {
                "consumption_id": consumption_id,
                "authorization_lease_digest": lease.canonical_digest,
                "request_fingerprint": request_fingerprint,
            }
        )
        claim_id = f"prps-claim-{identity_digest[:32]}"
        attempt_id = f"prps-attempt-{identity_digest[:32]}"
        authority = WorkflowProtectedRuntimeProcessSchedulingConsumptionAuthority()
        claim_values = {
            "claim_id": claim_id,
            "consumption_id": consumption_id,
            "attempt_id": attempt_id,
            "authorization_lease_id": lease.authorization_lease_id,
            "authorization_lease_digest": lease.canonical_digest,
            "authorization_claim_id": authorization_claim.claim_id,
            "authorization_claim_digest": authorization_claim.canonical_digest,
            "scheduling_profile_id": lease.scheduling_profile_id,
            "scheduling_profile_version": lease.scheduling_profile_version,
            "scheduling_profile_digest": lease.scheduling_profile_digest,
            "scope": lease.scope,
            "consumer_subject_id": lease.consumer_subject_id,
            "consumer_audience": lease.consumer_audience,
            "consumer_contract_id": lease.consumer_contract_id,
            "consumer_contract_version": lease.consumer_contract_version,
            "purpose_id": self._policy.purpose_id,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "idempotency_digest": idempotency_digest,
            "request_fingerprint": request_fingerprint,
            "claimed_at": now,
            "authority": authority,
        }
        claim = WorkflowProtectedRuntimeProcessSchedulingConsumptionClaim(
            **cast(Any, claim_values), canonical_digest=canonical_digest(_payload(claim_values))
        )
        attempt_values = {
            "attempt_id": attempt_id,
            "consumption_id": consumption_id,
            "claim_id": claim_id,
            "claim_digest": claim.canonical_digest,
            "authorization_lease_id": lease.authorization_lease_id,
            "authorization_lease_digest": lease.canonical_digest,
            "protected_operation_reference": f"protected-operation-{identity_digest[:32]}",
            "scheduling_profile_id": self._policy.scheduling_profile_id,
            "scheduling_profile_version": self._policy.scheduling_profile_version,
            "scheduling_profile_digest": self._policy.scheduling_profile_digest,
            "primitive_id": self._policy.primitive_id,
            "primitive_version": self._policy.primitive_version,
            "primitive_digest": self._policy.primitive_digest,
            "scheduler_contract_id": self._policy.scheduler_contract_id,
            "scheduler_contract_version": self._policy.scheduler_contract_version,
            "scheduler_id": self._policy.approved_scheduler_id,
            "scheduler_version": self._policy.approved_scheduler_version,
            "receipt_verification_signing_key_id": (
                self._policy.receipt_verification_signing_key_id
            ),
            "request_nonce_digest": canonical_digest(
                {"attempt_id": attempt_id, "lease_digest": lease.canonical_digest}
            ),
            "scope": lease.scope,
            "consumer_subject_id": lease.consumer_subject_id,
            "consumer_audience": lease.consumer_audience,
            "consumer_contract_id": lease.consumer_contract_id,
            "consumer_contract_version": lease.consumer_contract_version,
            "purpose_id": self._policy.purpose_id,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "started_at": now,
            "invocation_deadline": deadline,
            "state": (
                WorkflowProtectedRuntimeProcessSchedulingConsumptionAttemptState
            ).PROCESS_SCHEDULING_ATTEMPT_STARTED,
            "authority": authority,
        }
        attempt = WorkflowProtectedRuntimeProcessSchedulingAttempt(
            **cast(Any, attempt_values),
            canonical_digest=canonical_digest(_payload(attempt_values)),
        )
        instruction = build_workflow_protected_runtime_process_scheduling_instruction(attempt)
        envelope = build_workflow_protected_runtime_process_scheduling_signed_instruction_envelope(
            instruction, self._instruction_signer
        )
        if not self._instruction_signature_verifier.verify_instruction_envelope(envelope):
            self._raise("protected_runtime_process_scheduling_instruction_signature_invalid")

        write = await self._repository.claim_protected_runtime_process_scheduling(
            WorkflowProtectedRuntimeProcessSchedulingClaimRequest(
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
        )
        if (
            write.status
            is not WorkflowProtectedRuntimeProcessSchedulingConsumptionClaimStatus.CLAIMED
        ):
            replay_presentation = self._resolve_claim_write(
                write.status, write.attempt, write.result
            )
            if replay_presentation is not None:
                return replay_presentation
            self._raise(f"protected_runtime_process_scheduling_{write.status.value}")
        if write.claim != claim or write.attempt != attempt:
            self._raise("protected_runtime_process_scheduling_repository_contract_violation")

        invocation = build_workflow_protected_runtime_process_scheduling_invocation(envelope)
        try:
            receipt = await self._scheduler.schedule_suspended_process(invocation)
        except Exception:
            return await self._record_uncertain(claim=claim, attempt=attempt, completed_at=now)
        if not self._valid_receipt(receipt, attempt, instruction.canonical_digest):
            return await self._record_uncertain(
                claim=claim, attempt=attempt, completed_at=receipt.completed_at
            )
        result = self._result_from_receipt(claim=claim, attempt=attempt, receipt=receipt)
        return await self._record_result(
            claim=claim, attempt=attempt, result=result, receipt=receipt
        )

    async def _record_uncertain(
        self,
        *,
        claim: WorkflowProtectedRuntimeProcessSchedulingConsumptionClaim,
        attempt: WorkflowProtectedRuntimeProcessSchedulingAttempt,
        completed_at: datetime,
    ) -> WorkflowProtectedRuntimeProcessSchedulingConsumptionPresentation:
        values = self._result_values(
            claim=claim,
            attempt=attempt,
            receipt_digest=None,
            result_state=WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState.PROCESS_SCHEDULING_OUTCOME_UNCERTAIN,
            failure_class=WorkflowProtectedRuntimeProcessSchedulingConsumptionFailureClass.PROCESS_SCHEDULING_OUTCOME_UNCERTAIN,
            outcome_known=False,
            process_scheduled=None,
            process_suspended=None,
            process_runnable=None,
            completed_at=completed_at,
        )
        result = WorkflowProtectedRuntimeProcessSchedulingResult(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )
        return await self._record_result(claim=claim, attempt=attempt, result=result, receipt=None)

    def _result_from_receipt(
        self,
        *,
        claim: WorkflowProtectedRuntimeProcessSchedulingConsumptionClaim,
        attempt: WorkflowProtectedRuntimeProcessSchedulingAttempt,
        receipt: WorkflowProtectedRuntimeProcessSchedulingReceipt,
    ) -> WorkflowProtectedRuntimeProcessSchedulingResult:
        states = WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState
        failures = {
            states.PROCESS_SCHEDULING_REJECTED_WITHOUT_SCHEDULING: (
                WorkflowProtectedRuntimeProcessSchedulingConsumptionFailureClass
            ).PROTECTED_SCHEDULER_REJECTED_WITHOUT_SCHEDULING,
            states.PROCESS_SCHEDULING_FAILED_WITHOUT_SCHEDULING: (
                WorkflowProtectedRuntimeProcessSchedulingConsumptionFailureClass
            ).PROTECTED_SCHEDULER_FAILED_WITHOUT_SCHEDULING,
        }
        values = self._result_values(
            claim=claim,
            attempt=attempt,
            receipt_digest=receipt.canonical_digest,
            result_state=receipt.result_state,
            failure_class=failures.get(receipt.result_state),
            outcome_known=True,
            process_scheduled=receipt.process_scheduled,
            process_suspended=receipt.process_suspended,
            process_runnable=receipt.process_runnable,
            completed_at=receipt.completed_at,
        )
        return WorkflowProtectedRuntimeProcessSchedulingResult(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    def _result_values(
        self,
        *,
        claim: WorkflowProtectedRuntimeProcessSchedulingConsumptionClaim,
        attempt: WorkflowProtectedRuntimeProcessSchedulingAttempt,
        receipt_digest: str | None,
        result_state: WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState,
        failure_class: WorkflowProtectedRuntimeProcessSchedulingConsumptionFailureClass | None,
        outcome_known: bool,
        process_scheduled: bool | None,
        process_suspended: bool | None,
        process_runnable: bool | None,
        completed_at: datetime,
    ) -> dict[str, object]:
        return {
            "result_id": f"prps-result-{attempt.canonical_digest[:32]}",
            "consumption_id": attempt.consumption_id,
            "attempt_id": attempt.attempt_id,
            "attempt_digest": attempt.canonical_digest,
            "claim_id": claim.claim_id,
            "claim_digest": claim.canonical_digest,
            "authorization_lease_id": claim.authorization_lease_id,
            "authorization_lease_digest": claim.authorization_lease_digest,
            "receipt_digest": receipt_digest,
            "result_state": result_state,
            "failure_class": failure_class,
            "outcome_known": outcome_known,
            "process_scheduled": process_scheduled,
            "process_suspended": process_suspended,
            "process_runnable": process_runnable,
            "process_resumed": False,
            "process_dispatched": False,
            "process_executed": False,
            "scheduling_profile_id": attempt.scheduling_profile_id,
            "scheduling_profile_version": attempt.scheduling_profile_version,
            "scheduling_profile_digest": attempt.scheduling_profile_digest,
            "primitive_id": attempt.primitive_id,
            "primitive_version": attempt.primitive_version,
            "primitive_digest": attempt.primitive_digest,
            "scope": attempt.scope,
            "consumer_subject_id": attempt.consumer_subject_id,
            "consumer_audience": attempt.consumer_audience,
            "consumer_contract_id": attempt.consumer_contract_id,
            "consumer_contract_version": attempt.consumer_contract_version,
            "purpose_id": attempt.purpose_id,
            "policy_id": attempt.policy_id,
            "policy_version": attempt.policy_version,
            "policy_digest": attempt.policy_digest,
            "completed_at": completed_at,
            "recorded_at": completed_at,
            "authority": WorkflowProtectedRuntimeProcessSchedulingConsumptionAuthority(),
        }

    async def _record_result(
        self,
        *,
        claim: WorkflowProtectedRuntimeProcessSchedulingConsumptionClaim,
        attempt: WorkflowProtectedRuntimeProcessSchedulingAttempt,
        result: WorkflowProtectedRuntimeProcessSchedulingResult,
        receipt: WorkflowProtectedRuntimeProcessSchedulingReceipt | None,
    ) -> WorkflowProtectedRuntimeProcessSchedulingConsumptionPresentation:
        write = await self._repository.record_protected_runtime_process_scheduling_result(
            WorkflowProtectedRuntimeProcessSchedulingResultRequest(
                result=result,
                receipt=receipt,
                expected_claim_digest=claim.canonical_digest,
                expected_attempt_digest=attempt.canonical_digest,
            )
        )
        if write.status not in {
            WorkflowProtectedRuntimeProcessSchedulingResultWriteStatus.RECORDED,
            WorkflowProtectedRuntimeProcessSchedulingResultWriteStatus.REPLAY,
        }:
            self._raise("protected_runtime_process_scheduling_result_write_uncertain")
        return WorkflowProtectedRuntimeProcessSchedulingConsumptionPresentation(
            attempt=attempt, result=write.result
        )

    def _valid_receipt(
        self,
        receipt: object,
        attempt: WorkflowProtectedRuntimeProcessSchedulingAttempt,
        instruction_digest: str,
    ) -> bool:
        if not isinstance(receipt, WorkflowProtectedRuntimeProcessSchedulingReceipt):
            return False
        return (
            self._receipt_signature_verifier.verify_receipt(receipt)
            and receipt.consumption_id == attempt.consumption_id
            and receipt.attempt_id == attempt.attempt_id
            and receipt.instruction_digest == instruction_digest
            and receipt.protected_operation_reference == attempt.protected_operation_reference
            and receipt.authorization_lease_id == attempt.authorization_lease_id
            and receipt.scheduling_profile_digest == attempt.scheduling_profile_digest
            and receipt.primitive_digest == attempt.primitive_digest
            and receipt.request_nonce_digest == attempt.request_nonce_digest
            and receipt.completed_at.tzinfo is not None
            and receipt.completed_at < attempt.invocation_deadline
        )

    def _resolve_replay(
        self,
        status: WorkflowProtectedRuntimeProcessSchedulingConsumptionReplayStatus,
        attempt: WorkflowProtectedRuntimeProcessSchedulingAttempt | None,
        result: WorkflowProtectedRuntimeProcessSchedulingResult | None,
    ) -> WorkflowProtectedRuntimeProcessSchedulingConsumptionPresentation | None:
        if (
            status is WorkflowProtectedRuntimeProcessSchedulingConsumptionReplayStatus.TERMINAL
            and attempt is not None
            and result is not None
        ):
            return WorkflowProtectedRuntimeProcessSchedulingConsumptionPresentation(attempt, result)
        if (
            status
            is WorkflowProtectedRuntimeProcessSchedulingConsumptionReplayStatus.ATTEMPT_PENDING
        ):
            self._raise("protected_runtime_process_scheduling_attempt_committed_no_retry")
        if (
            status
            is WorkflowProtectedRuntimeProcessSchedulingConsumptionReplayStatus.ATTEMPT_UNCERTAIN
        ):
            self._raise("protected_runtime_process_scheduling_outcome_permanently_uncertain")
        if status is not WorkflowProtectedRuntimeProcessSchedulingConsumptionReplayStatus.NONE:
            self._raise(f"protected_runtime_process_scheduling_{status.value}")
        return None

    def _resolve_claim_write(
        self,
        status: WorkflowProtectedRuntimeProcessSchedulingConsumptionClaimStatus,
        attempt: WorkflowProtectedRuntimeProcessSchedulingAttempt | None,
        result: WorkflowProtectedRuntimeProcessSchedulingResult | None,
    ) -> WorkflowProtectedRuntimeProcessSchedulingConsumptionPresentation | None:
        if (
            status
            is WorkflowProtectedRuntimeProcessSchedulingConsumptionClaimStatus.REPLAY_TERMINAL
            and attempt is not None
            and result is not None
        ):
            return WorkflowProtectedRuntimeProcessSchedulingConsumptionPresentation(attempt, result)
        if status is WorkflowProtectedRuntimeProcessSchedulingConsumptionClaimStatus.REPLAY_PENDING:
            self._raise("protected_runtime_process_scheduling_attempt_committed_no_retry")
        if (
            status
            is WorkflowProtectedRuntimeProcessSchedulingConsumptionClaimStatus.REPLAY_UNCERTAIN
        ):
            self._raise("protected_runtime_process_scheduling_outcome_permanently_uncertain")
        return None

    def _require_dependencies(self) -> None:
        if (
            not self._instruction_signer.available
            or not self._instruction_signature_verifier.available
            or not self._receipt_signature_verifier.available
            or not self._scheduler.available
            or self._scheduler.scheduler_contract_id != self._policy.scheduler_contract_id
            or self._scheduler.scheduler_contract_version != self._policy.scheduler_contract_version
            or self._scheduler.scheduler_id != self._policy.approved_scheduler_id
            or self._scheduler.scheduler_version != self._policy.approved_scheduler_version
            or self._scheduler.scheduling_profile_digest != self._policy.scheduling_profile_digest
            or self._scheduler.primitive_digest != self._policy.primitive_digest
        ):
            self._raise("protected_runtime_process_scheduling_trusted_boundary_unavailable")

    def _validate_boundary(self, **values: object) -> None:
        for name in ("authorization_lease_id", "policy_id", "policy_version", "idempotency_key"):
            value = values[name]
            if not isinstance(value, str) or not value or len(value) > 512:
                self._raise(f"protected_runtime_process_scheduling_{name}_invalid")
        if (
            values["policy_id"] != self._policy.policy_id
            or values["policy_version"] != self._policy.policy_version
        ):
            self._raise("protected_runtime_process_scheduling_code_owned_policy_required")
        if (
            values["irreversible_consumption_acknowledged"] is not True
            or values["uncertainty_no_retry_acknowledged"] is not True
        ):
            self._raise("protected_runtime_process_scheduling_acknowledgement_required")

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowProtectedRuntimeProcessSchedulingConsumptionError(code)


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
    "WorkflowProtectedRuntimeProcessSchedulingConsumptionPresentation",
    "WorkflowProtectedRuntimeProcessSchedulingConsumptionService",
]

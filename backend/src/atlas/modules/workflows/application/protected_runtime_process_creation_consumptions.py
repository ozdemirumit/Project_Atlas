from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, NoReturn, cast

from atlas.modules.workflows.application.protected_runtime_process_creation_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessCreationClaimRequest,
    WorkflowProtectedRuntimeProcessCreationConsumptionClaimStatus,
    WorkflowProtectedRuntimeProcessCreationConsumptionError,
    WorkflowProtectedRuntimeProcessCreationConsumptionReplayStatus,
    WorkflowProtectedRuntimeProcessCreationConsumptionRepository,
    WorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier,
    WorkflowProtectedRuntimeProcessCreationInstructionSigner,
    WorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier,
    WorkflowProtectedRuntimeProcessCreationReplayLookupRequest,
    WorkflowProtectedRuntimeProcessCreationResultRequest,
    WorkflowProtectedRuntimeProcessCreationResultWriteStatus,
    WorkflowProtectedRuntimeProcessCreator,
    build_workflow_protected_runtime_process_creation_instruction,
    build_workflow_protected_runtime_process_creation_invocation,
    build_workflow_protected_runtime_process_creation_signed_instruction_envelope,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_process_creation_authorization_domain import (
    WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_process_creation_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_process_creation_consumption_domain import (
    WorkflowProtectedRuntimeProcessCreationAttempt,
    WorkflowProtectedRuntimeProcessCreationConsumptionAttemptState,
    WorkflowProtectedRuntimeProcessCreationConsumptionAuthority,
    WorkflowProtectedRuntimeProcessCreationConsumptionClaim,
    WorkflowProtectedRuntimeProcessCreationConsumptionFailureClass,
    WorkflowProtectedRuntimeProcessCreationConsumptionPolicy,
    WorkflowProtectedRuntimeProcessCreationConsumptionResultState,
    WorkflowProtectedRuntimeProcessCreationReceipt,
    WorkflowProtectedRuntimeProcessCreationResult,
    code_owned_workflow_protected_runtime_process_creation_consumption_policy,
)


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationConsumptionPresentation:
    attempt: WorkflowProtectedRuntimeProcessCreationAttempt
    result: WorkflowProtectedRuntimeProcessCreationResult | None


class WorkflowProtectedRuntimeProcessCreationConsumptionService:
    """Consumes one exact lease before one fixed, protected creator invocation."""

    def __init__(
        self,
        *,
        repository: WorkflowProtectedRuntimeProcessCreationConsumptionRepository,
        instruction_signer: WorkflowProtectedRuntimeProcessCreationInstructionSigner,
        instruction_signature_verifier: (
            WorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier
        ),
        receipt_signature_verifier: (
            WorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier
        ),
        creator: WorkflowProtectedRuntimeProcessCreator,
        policy: WorkflowProtectedRuntimeProcessCreationConsumptionPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._instruction_signer = instruction_signer
        self._instruction_signature_verifier = instruction_signature_verifier
        self._receipt_signature_verifier = receipt_signature_verifier
        self._creator = creator
        self._policy = (
            policy or code_owned_workflow_protected_runtime_process_creation_consumption_policy()
        )

    @property
    def repository(self) -> WorkflowProtectedRuntimeProcessCreationConsumptionRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowProtectedRuntimeProcessCreationConsumptionPolicy:
        return self._policy

    async def consume(
        self,
        *,
        authorization_lease_id: str,
        scope: WorkflowScope,
        consumer_subject_id: str,
        consumer_audience: str,
        consumer_contract_id: str,
        consumer_contract_version: str,
        irreversible_consumption_acknowledged: bool,
        uncertainty_no_retry_acknowledged: bool,
        idempotency_key: str,
    ) -> WorkflowProtectedRuntimeProcessCreationConsumptionPresentation:
        self._validate_boundary(
            authorization_lease_id=authorization_lease_id,
            consumer_subject_id=consumer_subject_id,
            consumer_audience=consumer_audience,
            consumer_contract_id=consumer_contract_id,
            consumer_contract_version=consumer_contract_version,
            irreversible_consumption_acknowledged=irreversible_consumption_acknowledged,
            uncertainty_no_retry_acknowledged=uncertainty_no_retry_acknowledged,
            idempotency_key=idempotency_key,
        )
        if not self._repository.durable:
            self._raise("protected_runtime_process_creation_durable_repository_required")

        idempotency_digest = canonical_digest({"idempotency_key": idempotency_key})
        request_fingerprint = canonical_digest(
            {
                "authorization_lease_id": authorization_lease_id,
                "scope": scope.canonical_value(),
                "consumer_subject_id": consumer_subject_id,
                "consumer_audience": consumer_audience,
                "consumer_contract_id": consumer_contract_id,
                "consumer_contract_version": consumer_contract_version,
                "policy_digest": self._policy.canonical_digest,
                "primitive_digest": self._policy.primitive_digest,
            }
        )
        consumption_id = f"prpc-consumption-{request_fingerprint[:32]}"
        replay = await self._repository.lookup_protected_runtime_process_creation_replay(
            WorkflowProtectedRuntimeProcessCreationReplayLookupRequest(
                authorization_lease_id=authorization_lease_id,
                scope=scope,
                consumer_subject_id=consumer_subject_id,
                consumer_audience=consumer_audience,
                policy_id=self._policy.policy_id,
                policy_version=self._policy.policy_version,
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
        source = await self._repository.get_protected_runtime_process_creation_consumption_source(
            authorization_lease_id=authorization_lease_id
        )
        if source is None:
            self._raise("protected_runtime_process_creation_authorization_not_found")
        now = await self._repository.get_authoritative_time()
        if now.tzinfo is None:
            self._raise("protected_runtime_process_creation_authoritative_time_invalid")
        lease = source.authorization_lease
        authorization_claim = source.authorization_claim
        source_policy = (
            code_owned_workflow_protected_runtime_process_creation_authorization_policy()
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
                WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseState
            ).AUTHORIZED_UNCONSUMED
            or lease.single_use is not True
            or lease.renewable is not False
            or lease.transferable is not False
            or lease.lease_is_bearer_capability is not False
            or lease.authority.protected_runtime_process_creation_authority_granted is not True
            or authorization_claim.authority.protected_runtime_process_creation_authority_granted
            is not False
            or lease.scope != scope
            or authorization_claim.scope != scope
            or lease.runtime_envelope_id != authorization_claim.runtime_envelope_id
            or lease.runtime_envelope_commitment != authorization_claim.runtime_envelope_commitment
            or lease.runtime_envelope_generation != authorization_claim.runtime_envelope_generation
            or not lease.is_active(evaluated_at=now)
        ):
            self._raise("protected_runtime_process_creation_authorization_invalid_or_expired")
        deadline = lease.valid_until
        if (
            now + timedelta(milliseconds=self._policy.minimum_invocation_margin_milliseconds)
            >= deadline
        ):
            self._raise("protected_runtime_process_creation_invocation_margin_insufficient")

        identity_digest = canonical_digest(
            {
                "consumption_id": consumption_id,
                "authorization_lease_digest": lease.canonical_digest,
                "request_fingerprint": request_fingerprint,
            }
        )
        claim_id = f"prpc-claim-{identity_digest[:32]}"
        attempt_id = f"prpc-attempt-{identity_digest[:32]}"
        authority = WorkflowProtectedRuntimeProcessCreationConsumptionAuthority()
        claim_values = {
            "claim_id": claim_id,
            "consumption_id": consumption_id,
            "attempt_id": attempt_id,
            "authorization_lease_id": lease.authorization_lease_id,
            "authorization_lease_digest": lease.canonical_digest,
            "authorization_claim_id": authorization_claim.claim_id,
            "authorization_claim_digest": authorization_claim.canonical_digest,
            "runtime_envelope_id": lease.runtime_envelope_id,
            "runtime_envelope_commitment": lease.runtime_envelope_commitment,
            "runtime_envelope_generation": lease.runtime_envelope_generation,
            "process_creation_profile_id": lease.process_creation_profile_id,
            "process_creation_profile_version": lease.process_creation_profile_version,
            "process_creation_profile_digest": lease.process_creation_profile_digest,
            "scope": scope,
            "consumer_subject_id": consumer_subject_id,
            "consumer_audience": consumer_audience,
            "consumer_contract_id": consumer_contract_id,
            "consumer_contract_version": consumer_contract_version,
            "purpose_id": self._policy.purpose_id,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "idempotency_digest": idempotency_digest,
            "request_fingerprint": request_fingerprint,
            "claimed_at": now,
            "authority": authority,
        }
        claim = WorkflowProtectedRuntimeProcessCreationConsumptionClaim(
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
            "runtime_envelope_id": lease.runtime_envelope_id,
            "runtime_envelope_commitment": lease.runtime_envelope_commitment,
            "runtime_envelope_generation": lease.runtime_envelope_generation,
            "process_creation_profile_id": self._policy.process_creation_profile_id,
            "process_creation_profile_version": self._policy.process_creation_profile_version,
            "process_creation_profile_digest": self._policy.process_creation_profile_digest,
            "primitive_id": self._policy.primitive_id,
            "primitive_version": self._policy.primitive_version,
            "primitive_digest": self._policy.primitive_digest,
            "creator_contract_id": self._policy.creator_contract_id,
            "creator_contract_version": self._policy.creator_contract_version,
            "creator_id": self._policy.approved_creator_id,
            "creator_version": self._policy.approved_creator_version,
            "receipt_verification_signing_key_id": (
                self._policy.receipt_verification_signing_key_id
            ),
            "request_nonce_digest": canonical_digest(
                {"attempt_id": attempt_id, "lease_digest": lease.canonical_digest}
            ),
            "scope": scope,
            "consumer_subject_id": consumer_subject_id,
            "consumer_audience": consumer_audience,
            "consumer_contract_id": consumer_contract_id,
            "consumer_contract_version": consumer_contract_version,
            "purpose_id": self._policy.purpose_id,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "started_at": now,
            "invocation_deadline": deadline,
            "state": (
                WorkflowProtectedRuntimeProcessCreationConsumptionAttemptState
            ).PROCESS_CREATION_ATTEMPT_STARTED,
            "authority": authority,
        }
        attempt = WorkflowProtectedRuntimeProcessCreationAttempt(
            **cast(Any, attempt_values),
            canonical_digest=canonical_digest(_payload(attempt_values)),
        )
        instruction = build_workflow_protected_runtime_process_creation_instruction(attempt)
        envelope = build_workflow_protected_runtime_process_creation_signed_instruction_envelope(
            instruction, self._instruction_signer
        )
        if not self._instruction_signature_verifier.verify_instruction_envelope(envelope):
            self._raise("protected_runtime_process_creation_instruction_signature_invalid")

        write = await self._repository.claim_protected_runtime_process_creation(
            WorkflowProtectedRuntimeProcessCreationClaimRequest(
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
            is not WorkflowProtectedRuntimeProcessCreationConsumptionClaimStatus.CLAIMED
        ):
            replay_presentation = self._resolve_claim_write(
                write.status, write.attempt, write.result
            )
            if replay_presentation is not None:
                return replay_presentation
            self._raise(f"protected_runtime_process_creation_{write.status.value}")
        if write.claim != claim or write.attempt != attempt:
            self._raise("protected_runtime_process_creation_repository_contract_violation")

        invocation = build_workflow_protected_runtime_process_creation_invocation(envelope)
        try:
            receipt = await self._creator.create_sealed_suspended_process(invocation)
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
        claim: WorkflowProtectedRuntimeProcessCreationConsumptionClaim,
        attempt: WorkflowProtectedRuntimeProcessCreationAttempt,
        completed_at: datetime,
    ) -> WorkflowProtectedRuntimeProcessCreationConsumptionPresentation:
        values = self._result_values(
            claim=claim,
            attempt=attempt,
            receipt_digest=None,
            result_state=WorkflowProtectedRuntimeProcessCreationConsumptionResultState.PROCESS_CREATION_OUTCOME_UNCERTAIN,
            failure_class=WorkflowProtectedRuntimeProcessCreationConsumptionFailureClass.PROCESS_CREATION_OUTCOME_UNCERTAIN,
            outcome_known=False,
            process_created=None,
            completed_at=completed_at,
        )
        result = WorkflowProtectedRuntimeProcessCreationResult(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )
        return await self._record_result(claim=claim, attempt=attempt, result=result, receipt=None)

    def _result_from_receipt(
        self,
        *,
        claim: WorkflowProtectedRuntimeProcessCreationConsumptionClaim,
        attempt: WorkflowProtectedRuntimeProcessCreationAttempt,
        receipt: WorkflowProtectedRuntimeProcessCreationReceipt,
    ) -> WorkflowProtectedRuntimeProcessCreationResult:
        failure: WorkflowProtectedRuntimeProcessCreationConsumptionFailureClass | None
        if (
            receipt.result_state
            is (
                WorkflowProtectedRuntimeProcessCreationConsumptionResultState
            ).PROCESS_CREATION_REJECTED_WITHOUT_CREATION
        ):
            failure = (
                WorkflowProtectedRuntimeProcessCreationConsumptionFailureClass
            ).PROTECTED_CREATOR_REJECTED_WITHOUT_CREATION
        elif (
            receipt.result_state
            is (
                WorkflowProtectedRuntimeProcessCreationConsumptionResultState
            ).PROCESS_CREATION_FAILED_WITHOUT_CREATION
        ):
            failure = (
                WorkflowProtectedRuntimeProcessCreationConsumptionFailureClass
            ).PROTECTED_CREATOR_FAILED_WITHOUT_CREATION
        else:
            failure = None
        values = self._result_values(
            claim=claim,
            attempt=attempt,
            receipt_digest=receipt.canonical_digest,
            result_state=receipt.result_state,
            failure_class=failure,
            outcome_known=True,
            process_created=receipt.process_created,
            completed_at=receipt.completed_at,
        )
        return WorkflowProtectedRuntimeProcessCreationResult(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    def _result_values(
        self,
        *,
        claim: WorkflowProtectedRuntimeProcessCreationConsumptionClaim,
        attempt: WorkflowProtectedRuntimeProcessCreationAttempt,
        receipt_digest: str | None,
        result_state: WorkflowProtectedRuntimeProcessCreationConsumptionResultState,
        failure_class: WorkflowProtectedRuntimeProcessCreationConsumptionFailureClass | None,
        outcome_known: bool,
        process_created: bool | None,
        completed_at: datetime,
    ) -> dict[str, object]:
        return {
            "result_id": f"prpc-result-{attempt.attempt_id[-32:]}",
            "consumption_id": attempt.consumption_id,
            "attempt_id": attempt.attempt_id,
            "attempt_digest": attempt.canonical_digest,
            "claim_id": claim.claim_id,
            "claim_digest": claim.canonical_digest,
            "authorization_lease_id": attempt.authorization_lease_id,
            "authorization_lease_digest": attempt.authorization_lease_digest,
            "receipt_digest": receipt_digest,
            "result_state": result_state,
            "failure_class": failure_class,
            "outcome_known": outcome_known,
            "process_created": process_created,
            "process_sealed": process_created,
            "process_suspended": process_created,
            "process_scheduled": False,
            "process_resumed": False,
            "process_dispatched": False,
            "process_executed": False,
            "runtime_envelope_id": attempt.runtime_envelope_id,
            "runtime_envelope_commitment": attempt.runtime_envelope_commitment,
            "runtime_envelope_generation": attempt.runtime_envelope_generation,
            "process_creation_profile_id": attempt.process_creation_profile_id,
            "process_creation_profile_version": attempt.process_creation_profile_version,
            "process_creation_profile_digest": attempt.process_creation_profile_digest,
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
            "authority": WorkflowProtectedRuntimeProcessCreationConsumptionAuthority(),
        }

    async def _record_result(
        self,
        *,
        claim: WorkflowProtectedRuntimeProcessCreationConsumptionClaim,
        attempt: WorkflowProtectedRuntimeProcessCreationAttempt,
        result: WorkflowProtectedRuntimeProcessCreationResult,
        receipt: WorkflowProtectedRuntimeProcessCreationReceipt | None,
    ) -> WorkflowProtectedRuntimeProcessCreationConsumptionPresentation:
        write = await self._repository.record_protected_runtime_process_creation_result(
            WorkflowProtectedRuntimeProcessCreationResultRequest(
                result=result,
                receipt=receipt,
                expected_claim_digest=claim.canonical_digest,
                expected_attempt_digest=attempt.canonical_digest,
            )
        )
        if (
            write.status
            in {
                WorkflowProtectedRuntimeProcessCreationResultWriteStatus.RECORDED,
                WorkflowProtectedRuntimeProcessCreationResultWriteStatus.REPLAY,
            }
            and write.result == result
        ):
            return WorkflowProtectedRuntimeProcessCreationConsumptionPresentation(attempt, result)
        self._raise("protected_runtime_process_creation_result_persistence_uncertain")

    def _valid_receipt(
        self,
        receipt: WorkflowProtectedRuntimeProcessCreationReceipt,
        attempt: WorkflowProtectedRuntimeProcessCreationAttempt,
        instruction_digest: str,
    ) -> bool:
        return (
            self._receipt_signature_verifier.verify_receipt(receipt)
            and receipt.attempt_id == attempt.attempt_id
            and receipt.consumption_id == attempt.consumption_id
            and receipt.instruction_digest == instruction_digest
            and receipt.authorization_lease_id == attempt.authorization_lease_id
            and receipt.runtime_envelope_id == attempt.runtime_envelope_id
            and receipt.runtime_envelope_commitment == attempt.runtime_envelope_commitment
            and receipt.runtime_envelope_generation == attempt.runtime_envelope_generation
            and receipt.primitive_digest == self._policy.primitive_digest
            and receipt.completed_at <= attempt.invocation_deadline
        )

    def _resolve_replay(
        self,
        status: WorkflowProtectedRuntimeProcessCreationConsumptionReplayStatus,
        attempt: WorkflowProtectedRuntimeProcessCreationAttempt | None,
        result: WorkflowProtectedRuntimeProcessCreationResult | None,
    ) -> WorkflowProtectedRuntimeProcessCreationConsumptionPresentation | None:
        if status is WorkflowProtectedRuntimeProcessCreationConsumptionReplayStatus.NONE:
            return None
        if (
            status is WorkflowProtectedRuntimeProcessCreationConsumptionReplayStatus.TERMINAL
            and attempt is not None
            and result is not None
        ):
            return WorkflowProtectedRuntimeProcessCreationConsumptionPresentation(attempt, result)
        if status is WorkflowProtectedRuntimeProcessCreationConsumptionReplayStatus.ATTEMPT_PENDING:
            self._raise("protected_runtime_process_creation_attempt_committed_no_retry")
        if (
            status
            is WorkflowProtectedRuntimeProcessCreationConsumptionReplayStatus.ATTEMPT_UNCERTAIN
        ):
            self._raise("protected_runtime_process_creation_outcome_permanently_uncertain")
        self._raise(f"protected_runtime_process_creation_{status.value}")

    def _resolve_claim_write(
        self,
        status: WorkflowProtectedRuntimeProcessCreationConsumptionClaimStatus,
        attempt: WorkflowProtectedRuntimeProcessCreationAttempt | None,
        result: WorkflowProtectedRuntimeProcessCreationResult | None,
    ) -> WorkflowProtectedRuntimeProcessCreationConsumptionPresentation | None:
        if (
            status is WorkflowProtectedRuntimeProcessCreationConsumptionClaimStatus.REPLAY_TERMINAL
            and attempt is not None
            and result is not None
        ):
            return WorkflowProtectedRuntimeProcessCreationConsumptionPresentation(attempt, result)
        if status is WorkflowProtectedRuntimeProcessCreationConsumptionClaimStatus.REPLAY_PENDING:
            self._raise("protected_runtime_process_creation_attempt_committed_no_retry")
        if status is WorkflowProtectedRuntimeProcessCreationConsumptionClaimStatus.REPLAY_UNCERTAIN:
            self._raise("protected_runtime_process_creation_outcome_permanently_uncertain")
        return None

    def _require_dependencies(self) -> None:
        if (
            not self._instruction_signer.available
            or not self._instruction_signature_verifier.available
            or not self._receipt_signature_verifier.available
            or not self._creator.available
            or self._creator.creator_contract_id != self._policy.creator_contract_id
            or self._creator.creator_contract_version != self._policy.creator_contract_version
            or self._creator.creator_id != self._policy.approved_creator_id
            or self._creator.creator_version != self._policy.approved_creator_version
            or self._creator.process_creation_profile_digest
            != self._policy.process_creation_profile_digest
            or self._creator.primitive_digest != self._policy.primitive_digest
        ):
            self._raise("protected_runtime_process_creation_trusted_boundary_unavailable")

    def _validate_boundary(self, **values: object) -> None:
        for name in (
            "authorization_lease_id",
            "consumer_subject_id",
            "consumer_audience",
            "consumer_contract_id",
            "consumer_contract_version",
            "idempotency_key",
        ):
            value = values[name]
            if not isinstance(value, str) or not value or len(value) > 512:
                self._raise(f"protected_runtime_process_creation_{name}_invalid")
        if (
            values["consumer_subject_id"] != self._policy.consumer_subject_id
            or values["consumer_audience"] != self._policy.consumer_audience
            or values["consumer_contract_id"] != self._policy.consumer_contract_id
            or values["consumer_contract_version"] != self._policy.consumer_contract_version
        ):
            self._raise("protected_runtime_process_creation_exact_workload_required")
        if (
            values["irreversible_consumption_acknowledged"] is not True
            or values["uncertainty_no_retry_acknowledged"] is not True
        ):
            self._raise("protected_runtime_process_creation_acknowledgement_required")

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowProtectedRuntimeProcessCreationConsumptionError(code)


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
    "WorkflowProtectedRuntimeProcessCreationConsumptionPresentation",
    "WorkflowProtectedRuntimeProcessCreationConsumptionService",
]

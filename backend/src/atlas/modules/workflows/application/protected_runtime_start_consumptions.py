from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, NoReturn, cast

from atlas.modules.workflows.application.protected_runtime_start_consumption_ports import (
    WorkflowProtectedRuntimeStartConsumptionClaimRequest,
    WorkflowProtectedRuntimeStartConsumptionClaimStatus,
    WorkflowProtectedRuntimeStartConsumptionError,
    WorkflowProtectedRuntimeStartConsumptionReplayLookup,
    WorkflowProtectedRuntimeStartConsumptionReplayLookupRequest,
    WorkflowProtectedRuntimeStartConsumptionReplayStatus,
    WorkflowProtectedRuntimeStartConsumptionRepository,
    WorkflowProtectedRuntimeStartConsumptionResultRequest,
    WorkflowProtectedRuntimeStartConsumptionResultWriteStatus,
    WorkflowProtectedRuntimeStartConsumptionSource,
    WorkflowProtectedRuntimeStarter,
    WorkflowProtectedRuntimeStartInstructionSignatureVerifier,
    WorkflowProtectedRuntimeStartInstructionSigner,
    WorkflowProtectedRuntimeStartReceiptSignatureVerifier,
    build_workflow_protected_runtime_start_instruction,
    build_workflow_protected_runtime_start_invocation,
    build_workflow_protected_runtime_start_signed_instruction_envelope,
    validate_workflow_protected_runtime_start_consumption_claim_request,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_start_authorization_domain import (
    WorkflowProtectedRuntimeStartAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_start_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_start_consumption_domain import (
    WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNATURE_ALGORITHM,
    WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNING_KEY_ID,
    WorkflowProtectedRuntimeStartConsumptionAttempt,
    WorkflowProtectedRuntimeStartConsumptionAttemptState,
    WorkflowProtectedRuntimeStartConsumptionAuthority,
    WorkflowProtectedRuntimeStartConsumptionClaim,
    WorkflowProtectedRuntimeStartConsumptionFailureClass,
    WorkflowProtectedRuntimeStartConsumptionPolicy,
    WorkflowProtectedRuntimeStartConsumptionResult,
    WorkflowProtectedRuntimeStartConsumptionResultState,
    WorkflowProtectedRuntimeStartInstruction,
    WorkflowProtectedRuntimeStartReceipt,
    WorkflowProtectedRuntimeStartSignedInstructionEnvelope,
    code_owned_workflow_protected_runtime_start_consumption_policy,
)

_RUNTIME_START_OUTCOME_UNCERTAIN_NO_RETRY = "protected_runtime_start_outcome_uncertain_no_retry"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartConsumptionPresentation:
    attempt: WorkflowProtectedRuntimeStartConsumptionAttempt
    result: WorkflowProtectedRuntimeStartConsumptionResult | None


class WorkflowProtectedRuntimeStartConsumptionService:
    """Consumes one ADR-173 lease and invokes the protected starter at most once."""

    def __init__(
        self,
        *,
        repository: WorkflowProtectedRuntimeStartConsumptionRepository,
        starter: WorkflowProtectedRuntimeStarter,
        instruction_signer: WorkflowProtectedRuntimeStartInstructionSigner,
        instruction_signature_verifier: WorkflowProtectedRuntimeStartInstructionSignatureVerifier,
        receipt_signature_verifier: WorkflowProtectedRuntimeStartReceiptSignatureVerifier,
        policy: WorkflowProtectedRuntimeStartConsumptionPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._starter = starter
        self._instruction_signer = instruction_signer
        self._instruction_signature_verifier = instruction_signature_verifier
        self._receipt_signature_verifier = receipt_signature_verifier
        self._policy = policy or code_owned_workflow_protected_runtime_start_consumption_policy()

    @property
    def repository(self) -> WorkflowProtectedRuntimeStartConsumptionRepository:
        return self._repository

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def policy(self) -> WorkflowProtectedRuntimeStartConsumptionPolicy:
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
    ) -> WorkflowProtectedRuntimeStartConsumptionPresentation:
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
            self._raise("protected_runtime_start_consumption_durable_repository_required")

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
        consumption_id = f"workflow-protected-runtime-start-consumption.{seed[:24]}"

        # The durable replay lookup is the first repository operation.
        replay = await self._repository.lookup_protected_runtime_start_consumption_replay(
            WorkflowProtectedRuntimeStartConsumptionReplayLookupRequest(
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
        source = await self._repository.get_protected_runtime_start_consumption_source(
            authorization_lease_id=authorization_lease_id
        )
        if source is None:
            self._raise("protected_runtime_start_consumption_source_unavailable")
        authoritative_time = await self._repository.get_authoritative_time()
        self._validate_source(source, authoritative_time, context.scope)

        claim_id = f"workflow-protected-runtime-start-consumption-claim.{seed[:24]}"
        attempt_id = f"workflow-protected-runtime-start-attempt.{seed[:24]}"
        claim = self._build_claim(
            source=source,
            claim_id=claim_id,
            attempt_id=attempt_id,
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
        instruction = build_workflow_protected_runtime_start_instruction(attempt)
        envelope = build_workflow_protected_runtime_start_signed_instruction_envelope(
            instruction, self._instruction_signer
        )
        self._verify_instruction_envelope(envelope, instruction)
        claim_request = WorkflowProtectedRuntimeStartConsumptionClaimRequest(
            source=source,
            candidate_claim=claim,
            candidate_attempt=attempt,
            signed_instruction_envelope=envelope,
            offline_instruction_signature_verifier=(self._instruction_signature_verifier),
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
        validate_workflow_protected_runtime_start_consumption_claim_request(claim_request)

        try:
            claimed = await self._repository.claim_protected_runtime_start_consumption(
                claim_request
            )
        except Exception as exc:
            raise WorkflowProtectedRuntimeStartConsumptionError(
                "protected_runtime_start_consumption_claim_commit_uncertain"
            ) from exc
        historical_after_claim = self._resolve_claim(
            claimed.status, claimed.attempt, claimed.result
        )
        if historical_after_claim is not None:
            return historical_after_claim
        if claimed.claim != claim or claimed.attempt != attempt or claimed.result is not None:
            self._raise("protected_runtime_start_consumption_repository_violation")

        try:
            invocation = build_workflow_protected_runtime_start_invocation(envelope)
            receipt = await self._starter.start_runtime(invocation)
            self._verify_receipt(receipt, instruction)
            recorded_at = await self._repository.get_authoritative_time()
            result = self._build_receipted_result(
                claim=claim,
                attempt=attempt,
                receipt=receipt,
                recorded_at=recorded_at,
            )
            write = await self._repository.record_protected_runtime_start_consumption_result(
                WorkflowProtectedRuntimeStartConsumptionResultRequest(
                    result=result,
                    receipt=receipt,
                    expected_claim_digest=claim.canonical_digest,
                    expected_attempt_digest=attempt.canonical_digest,
                )
            )
        except Exception:
            return await self._record_uncertainty(claim=claim, attempt=attempt)
        if (
            write.status
            not in (
                WorkflowProtectedRuntimeStartConsumptionResultWriteStatus.RECORDED,
                WorkflowProtectedRuntimeStartConsumptionResultWriteStatus.REPLAY,
            )
            or write.result is None
        ):
            return await self._record_uncertainty(claim=claim, attempt=attempt)
        return WorkflowProtectedRuntimeStartConsumptionPresentation(attempt, write.result)

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeStartConsumptionPresentation, ...]:
        if not self._repository.durable:
            self._raise("protected_runtime_start_consumption_durable_repository_required")
        attempts = await self._repository.list_protected_runtime_start_attempts(
            scope=scope, limit=limit
        )
        results = await self._repository.get_protected_runtime_start_results(
            scope=scope,
            consumption_ids=tuple(attempt.consumption_id for attempt in attempts),
        )
        by_consumption_id = {result.consumption_id: result for result in results}
        return tuple(
            WorkflowProtectedRuntimeStartConsumptionPresentation(
                attempt, by_consumption_id.get(attempt.consumption_id)
            )
            for attempt in attempts
        )

    def _build_claim(
        self,
        *,
        source: WorkflowProtectedRuntimeStartConsumptionSource,
        claim_id: str,
        attempt_id: str,
        consumption_id: str,
        scope: WorkflowScope,
        idempotency_digest: str,
        request_fingerprint: str,
        claimed_at: datetime,
    ) -> WorkflowProtectedRuntimeStartConsumptionClaim:
        lease = source.authorization_lease
        values = _record_values(
            WorkflowProtectedRuntimeStartConsumptionClaim,
            sources=(lease,),
            aliases={
                "claim_id": claim_id,
                "consumption_id": consumption_id,
                "attempt_id": attempt_id,
                "authorization_lease_digest": lease.canonical_digest,
                "authorization_claim_id": lease.claim_id,
                "authorization_claim_digest": lease.claim_digest,
                "runtime_slot_generation": lease.runtime_slot_post_generation,
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
                "authority": WorkflowProtectedRuntimeStartConsumptionAuthority(),
            },
        )
        return WorkflowProtectedRuntimeStartConsumptionClaim(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    def _build_attempt(
        self,
        *,
        source: WorkflowProtectedRuntimeStartConsumptionSource,
        claim: WorkflowProtectedRuntimeStartConsumptionClaim,
        started_at: datetime,
        seed: str,
    ) -> WorkflowProtectedRuntimeStartConsumptionAttempt:
        lease = source.authorization_lease
        deadline = lease.valid_until
        values = _record_values(
            WorkflowProtectedRuntimeStartConsumptionAttempt,
            sources=(claim, lease),
            aliases={
                "claim_digest": claim.canonical_digest,
                "protected_operation_reference": f"protected-runtime-start.{seed[:32]}",
                "runtime_slot_generation": lease.runtime_slot_post_generation,
                "expected_start_count_pre": 0,
                "expected_start_count_post": 1,
                "starter_contract_id": self._policy.required_starter_contract_id,
                "starter_contract_version": self._policy.required_starter_contract_version,
                "starter_id": self._policy.approved_starter_id,
                "starter_version": self._policy.approved_starter_version,
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
                "invocation_deadline": deadline,
                "state": (
                    WorkflowProtectedRuntimeStartConsumptionAttemptState
                ).RUNTIME_START_ATTEMPT_STARTED,
                "authority": WorkflowProtectedRuntimeStartConsumptionAuthority(),
            },
        )
        return WorkflowProtectedRuntimeStartConsumptionAttempt(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    def _build_receipted_result(
        self,
        *,
        claim: WorkflowProtectedRuntimeStartConsumptionClaim,
        attempt: WorkflowProtectedRuntimeStartConsumptionAttempt,
        receipt: WorkflowProtectedRuntimeStartReceipt,
        recorded_at: datetime,
    ) -> WorkflowProtectedRuntimeStartConsumptionResult:
        success = (
            receipt.result_state
            is (
                WorkflowProtectedRuntimeStartConsumptionResultState
            ).RUNTIME_STARTED_IN_PROTECTED_BOUNDARY
        )
        values = _record_values(
            WorkflowProtectedRuntimeStartConsumptionResult,
            sources=(attempt,),
            aliases={
                "result_id": (
                    "workflow-protected-runtime-start-result."
                    f"{attempt.attempt_id.rsplit('.', 1)[-1]}"
                ),
                "attempt_digest": attempt.canonical_digest,
                "claim_digest": claim.canonical_digest,
                "runtime_envelope_commitment": attempt.runtime_envelope_commitment,
                "state": receipt.result_state,
                "failure_class": (
                    None
                    if success
                    else (
                        WorkflowProtectedRuntimeStartConsumptionFailureClass
                    ).PROTECTED_STARTER_REJECTED_WITHOUT_START
                ),
                "outcome_known": True,
                "runtime_started": success,
                "starter_receipt_digest": receipt.canonical_digest,
                "completed_at": receipt.completed_at,
                "recorded_at": recorded_at,
                "authority": WorkflowProtectedRuntimeStartConsumptionAuthority(),
            },
        )
        return WorkflowProtectedRuntimeStartConsumptionResult(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    async def _record_uncertainty(
        self,
        *,
        claim: WorkflowProtectedRuntimeStartConsumptionClaim,
        attempt: WorkflowProtectedRuntimeStartConsumptionAttempt,
    ) -> WorkflowProtectedRuntimeStartConsumptionPresentation:
        try:
            recorded_at = await self._repository.get_authoritative_time()
            values = _record_values(
                WorkflowProtectedRuntimeStartConsumptionResult,
                sources=(attempt,),
                aliases={
                    "result_id": (
                        "workflow-protected-runtime-start-result."
                        f"{attempt.attempt_id.rsplit('.', 1)[-1]}"
                    ),
                    "attempt_digest": attempt.canonical_digest,
                    "claim_digest": claim.canonical_digest,
                    "runtime_envelope_commitment": attempt.runtime_envelope_commitment,
                    "state": (
                        WorkflowProtectedRuntimeStartConsumptionResultState
                    ).RUNTIME_START_OUTCOME_UNCERTAIN,
                    "failure_class": (
                        WorkflowProtectedRuntimeStartConsumptionFailureClass
                    ).RUNTIME_START_OUTCOME_UNCERTAIN,
                    "outcome_known": False,
                    "runtime_started": None,
                    "starter_receipt_digest": None,
                    "completed_at": None,
                    "recorded_at": recorded_at,
                    "authority": WorkflowProtectedRuntimeStartConsumptionAuthority(),
                },
            )
            result = WorkflowProtectedRuntimeStartConsumptionResult(
                **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
            )
            write = await self._repository.record_protected_runtime_start_consumption_result(
                WorkflowProtectedRuntimeStartConsumptionResultRequest(
                    result=result,
                    receipt=None,
                    expected_claim_digest=claim.canonical_digest,
                    expected_attempt_digest=attempt.canonical_digest,
                )
            )
        except Exception as exc:
            raise WorkflowProtectedRuntimeStartConsumptionError(
                _RUNTIME_START_OUTCOME_UNCERTAIN_NO_RETRY
            ) from exc
        if (
            write.status
            not in (
                WorkflowProtectedRuntimeStartConsumptionResultWriteStatus.RECORDED,
                WorkflowProtectedRuntimeStartConsumptionResultWriteStatus.REPLAY,
            )
            or write.result is None
            or write.result.state
            is not (
                WorkflowProtectedRuntimeStartConsumptionResultState
            ).RUNTIME_START_OUTCOME_UNCERTAIN
        ):
            self._raise(_RUNTIME_START_OUTCOME_UNCERTAIN_NO_RETRY)
        return WorkflowProtectedRuntimeStartConsumptionPresentation(attempt, write.result)

    def _validate_source(
        self,
        source: WorkflowProtectedRuntimeStartConsumptionSource,
        evaluated_at: datetime,
        scope: WorkflowScope,
    ) -> None:
        lease = source.authorization_lease
        authorization_claim = source.authorization_claim
        source_policy = code_owned_workflow_protected_runtime_start_authorization_policy()
        authority = lease.authority.canonical_value()
        start_request_authority = authority.pop("protected_runtime_start_authority_granted")
        remaining = lease.valid_until - evaluated_at
        if (
            lease.claim_id != authorization_claim.claim_id
            or lease.claim_digest != authorization_claim.canonical_digest
            or lease.scope != scope
            or lease.policy_id != source_policy.policy_id
            or lease.policy_version != source_policy.policy_version
            or lease.policy_digest != source_policy.canonical_digest
            or lease.state
            is not WorkflowProtectedRuntimeStartAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
            or not lease.is_active(evaluated_at=evaluated_at)
            or remaining
            < timedelta(milliseconds=self._policy.minimum_invocation_margin_milliseconds)
            or not start_request_authority
            or any(authority.values())
            or lease.consumer_subject_id != self._policy.consumer_subject_id
            or lease.consumer_audience != self._policy.consumer_audience
            or lease.consumer_contract_id != self._policy.consumer_contract_id
            or lease.consumer_contract_version != self._policy.consumer_contract_version
            or lease.runtime_start_profile_id != self._policy.runtime_start_profile_id
            or lease.runtime_start_profile_version != self._policy.runtime_start_profile_version
            or lease.runtime_start_profile_digest != self._policy.runtime_start_profile_digest
        ):
            self._raise("protected_runtime_start_consumption_source_invalid")

    def _verify_instruction_envelope(
        self,
        envelope: WorkflowProtectedRuntimeStartSignedInstructionEnvelope,
        instruction: WorkflowProtectedRuntimeStartInstruction,
    ) -> None:
        if (
            envelope.instruction != instruction
            or not self._instruction_signature_verifier.verify_instruction_envelope(envelope)
        ):
            self._raise("protected_runtime_start_instruction_envelope_invalid")

    def _verify_receipt(
        self,
        receipt: WorkflowProtectedRuntimeStartReceipt,
        instruction: WorkflowProtectedRuntimeStartInstruction,
    ) -> None:
        exact = (
            (receipt.consumption_id, instruction.consumption_id),
            (receipt.attempt_id, instruction.attempt_id),
            (receipt.instruction_digest, instruction.canonical_digest),
            (receipt.protected_operation_reference, instruction.protected_operation_reference),
            (receipt.authorization_lease_id, instruction.authorization_lease_id),
            (receipt.destination_deployment_id, instruction.destination_deployment_id),
            (receipt.destination_generation, instruction.destination_generation),
            (
                receipt.destination_fencing_token_digest,
                instruction.destination_fencing_token_digest,
            ),
            (receipt.runtime_slot_commitment, instruction.runtime_slot_commitment),
            (receipt.runtime_slot_generation, instruction.runtime_slot_generation),
            (receipt.runtime_envelope_id, instruction.runtime_envelope_id),
            (receipt.runtime_envelope_commitment, instruction.runtime_envelope_commitment),
            (receipt.runtime_envelope_generation, instruction.runtime_envelope_generation),
            (receipt.request_nonce_digest, instruction.request_nonce_digest),
        )
        if (
            any(observed != expected for observed, expected in exact)
            or receipt.completed_at < instruction.started_at
            or receipt.completed_at >= instruction.invocation_deadline
            or receipt.signing_key_id != self._policy.receipt_verification_signing_key_id
            or receipt.signature_algorithm != self._policy.receipt_signature_algorithm
            or not self._receipt_signature_verifier.verify_receipt(receipt)
        ):
            self._raise("protected_runtime_start_receipt_invalid")

    def _require_trusted_components(self) -> None:
        if (
            not self._starter.available
            or not self._instruction_signer.available
            or not self._instruction_signature_verifier.available
            or not self._receipt_signature_verifier.available
            or self._instruction_signer.signing_key_id
            != WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNING_KEY_ID
            or self._instruction_signer.signature_algorithm
            != WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNATURE_ALGORITHM
            or self._starter.starter_contract_id != self._policy.required_starter_contract_id
            or self._starter.starter_contract_version
            != self._policy.required_starter_contract_version
            or self._starter.starter_id != self._policy.approved_starter_id
            or self._starter.starter_version != self._policy.approved_starter_version
            or self._starter.runtime_start_profile_id != self._policy.runtime_start_profile_id
            or self._starter.runtime_start_profile_version
            != self._policy.runtime_start_profile_version
            or self._starter.runtime_start_profile_digest
            != self._policy.runtime_start_profile_digest
        ):
            self._raise("protected_runtime_start_trusted_component_unavailable")

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
            self._raise("protected_runtime_start_consumption_request_invalid")
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
                self._raise("protected_runtime_start_consumption_request_invalid")

    def _resolve_replay(
        self, replay: WorkflowProtectedRuntimeStartConsumptionReplayLookup
    ) -> WorkflowProtectedRuntimeStartConsumptionPresentation | None:
        statuses = WorkflowProtectedRuntimeStartConsumptionReplayStatus
        if replay.status is statuses.NONE:
            if replay.attempt is not None or replay.result is not None:
                self._raise("protected_runtime_start_consumption_repository_violation")
            return None
        if replay.status is statuses.TERMINAL:
            if replay.attempt is None or replay.result is None:
                self._raise("protected_runtime_start_consumption_repository_violation")
            return WorkflowProtectedRuntimeStartConsumptionPresentation(
                replay.attempt, replay.result
            )
        if replay.status is statuses.ATTEMPT_UNCERTAIN:
            if replay.attempt is None or replay.result is not None:
                self._raise("protected_runtime_start_consumption_repository_violation")
            self._raise(_RUNTIME_START_OUTCOME_UNCERTAIN_NO_RETRY)
        if replay.status is statuses.ATTEMPT_PENDING:
            if replay.attempt is None or replay.result is not None:
                self._raise("protected_runtime_start_consumption_repository_violation")
            return WorkflowProtectedRuntimeStartConsumptionPresentation(replay.attempt, None)
        self._raise(f"protected_runtime_start_consumption_{replay.status.value}")

    def _resolve_claim(
        self,
        status: WorkflowProtectedRuntimeStartConsumptionClaimStatus,
        attempt: WorkflowProtectedRuntimeStartConsumptionAttempt | None,
        result: WorkflowProtectedRuntimeStartConsumptionResult | None,
    ) -> WorkflowProtectedRuntimeStartConsumptionPresentation | None:
        statuses = WorkflowProtectedRuntimeStartConsumptionClaimStatus
        if status is statuses.CLAIMED:
            return None
        if status is statuses.REPLAY_TERMINAL:
            if attempt is None or result is None:
                self._raise("protected_runtime_start_consumption_repository_violation")
            return WorkflowProtectedRuntimeStartConsumptionPresentation(attempt, result)
        if status is statuses.REPLAY_UNCERTAIN:
            if attempt is None or result is not None:
                self._raise("protected_runtime_start_consumption_repository_violation")
            self._raise(_RUNTIME_START_OUTCOME_UNCERTAIN_NO_RETRY)
        if status is statuses.REPLAY_PENDING:
            if attempt is None or result is not None:
                self._raise("protected_runtime_start_consumption_repository_violation")
            return WorkflowProtectedRuntimeStartConsumptionPresentation(attempt, None)
        self._raise(f"protected_runtime_start_consumption_{status.value}")

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowProtectedRuntimeStartConsumptionError(code)


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
            raise WorkflowProtectedRuntimeStartConsumptionError(
                "protected_runtime_start_consumption_domain_contract_violation"
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
    "WorkflowProtectedRuntimeStartConsumptionPresentation",
    "WorkflowProtectedRuntimeStartConsumptionService",
]

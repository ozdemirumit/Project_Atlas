from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.protected_runtime_process_resume_authorization_ports import (  # noqa: E501
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTATION_SIGNING_KEY_ID,
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTOR_ID,
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTOR_VERSION,
    WorkflowProtectedRuntimeProcessResumeAuthorizationError,
    WorkflowProtectedRuntimeProcessResumeAuthorizationInventory,
    WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseRequest,
    WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseStatus,
    WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightRequest,
    WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightStatus,
    WorkflowProtectedRuntimeProcessResumeAuthorizationRepository,
    WorkflowProtectedRuntimeProcessResumeAuthorizationSource,
    WorkflowProtectedRuntimeProcessResumeAuthorizationSourceRequest,
    WorkflowProtectedRuntimeProcessResumeStateAttestation,
    WorkflowProtectedRuntimeProcessResumeStateAttestationRequest,
    WorkflowProtectedRuntimeProcessResumeStateAttestor,
    WorkflowProtectedRuntimeProcessResumeStateSignatureVerifier,
    workflow_protected_runtime_process_resume_receipt_matches_source,
)
from atlas.modules.workflows.application.protected_runtime_process_scheduling_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_process_resume_authorization_domain import (
    WorkflowProtectedRuntimeProcessResumeAuthorizationAuthority,
    WorkflowProtectedRuntimeProcessResumeAuthorizationClaim,
    WorkflowProtectedRuntimeProcessResumeAuthorizationLease,
    WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseState,
    WorkflowProtectedRuntimeProcessResumeAuthorizationPolicy,
    code_owned_workflow_protected_runtime_process_resume_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_process_scheduling_consumption_domain import (
    WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState,
    code_owned_workflow_protected_runtime_process_scheduling_consumption_policy,
)

WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_AUTHORIZATION_PRODUCER = (
    "project-atlas-workflow-protected-runtime-process-resume-authorizer"
)


class WorkflowProtectedRuntimeProcessResumeAuthorizationService:
    """Issue a future process-resume-request lease without scheduling or running a process."""

    def __init__(
        self,
        *,
        authorization_repository: WorkflowProtectedRuntimeProcessResumeAuthorizationRepository,
        process_state_attestor: WorkflowProtectedRuntimeProcessResumeStateAttestor,
        process_state_signature_verifier: (
            WorkflowProtectedRuntimeProcessResumeStateSignatureVerifier
        ),
        process_scheduling_receipt_signature_verifier: (
            WorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier
        ),
        audit_sink: AuditSink,
        policy: WorkflowProtectedRuntimeProcessResumeAuthorizationPolicy | None = None,
    ) -> None:
        self._repository = authorization_repository
        self._process_state_attestor = process_state_attestor
        self._process_state_signature_verifier = process_state_signature_verifier
        self._process_scheduling_receipt_signature_verifier = (
            process_scheduling_receipt_signature_verifier
        )
        self._audit_sink = audit_sink
        self._observed_expiry_audit_ids: set[str] = set()
        self._policy = (
            policy or code_owned_workflow_protected_runtime_process_resume_authorization_policy()
        )

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def repository(self) -> WorkflowProtectedRuntimeProcessResumeAuthorizationRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowProtectedRuntimeProcessResumeAuthorizationPolicy:
        return self._policy

    async def authorize(
        self,
        *,
        process_scheduling_result_id: str,
        policy_id: str,
        policy_version: str,
        single_use_nonrenewable_nontransferable_future_request_acknowledged: bool,
        single_use_future_request_only_acknowledged: bool,
        idempotency_key: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> WorkflowProtectedRuntimeProcessResumeAuthorizationLease:
        try:
            return await self._authorize(
                process_scheduling_result_id=process_scheduling_result_id,
                policy_id=policy_id,
                policy_version=policy_version,
                single_use_nonrenewable_nontransferable_future_request_acknowledged=(
                    single_use_nonrenewable_nontransferable_future_request_acknowledged
                ),
                single_use_future_request_only_acknowledged=(
                    single_use_future_request_only_acknowledged
                ),
                idempotency_key=idempotency_key,
                context=context,
            )
        except WorkflowProtectedRuntimeProcessResumeAuthorizationError as error:
            await self._rejection_audit(
                context,
                result_code=error.code,
                process_scheduling_result_id=process_scheduling_result_id,
            )
            raise

    async def _authorize(
        self,
        *,
        process_scheduling_result_id: str,
        policy_id: str,
        policy_version: str,
        single_use_nonrenewable_nontransferable_future_request_acknowledged: bool,
        single_use_future_request_only_acknowledged: bool,
        idempotency_key: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> WorkflowProtectedRuntimeProcessResumeAuthorizationLease:
        self._require_workload(context)
        if not self._repository.durable:
            self._raise("workflow_protected_runtime_process_resume_durable_repository_required")
        result_id = self._identifier(process_scheduling_result_id, "process_scheduling_result_id")
        normalized_key = self._idempotency_key(idempotency_key)
        if (
            single_use_nonrenewable_nontransferable_future_request_acknowledged is not True
            or single_use_future_request_only_acknowledged is not True
        ):
            self._raise("workflow_protected_runtime_process_resume_acknowledgement_required")
        if policy_id != self._policy.policy_id or policy_version != self._policy.policy_version:
            self._raise("workflow_protected_runtime_process_resume_policy_conflict")
        idempotency_digest = canonical_digest(
            {
                "idempotency_key": normalized_key,
                "scope": context.scope.canonical_value(),
                "subject_id": context.subject_id,
            }
        )
        fingerprint = canonical_digest(
            {
                "policy_digest": self._policy.canonical_digest,
                "scope": context.scope.canonical_value(),
                "process_scheduling_result_id": result_id,
                "subject_id": context.subject_id,
                "single_use_nonrenewable_nontransferable_future_request_acknowledged": True,
                "single_use_future_request_only_acknowledged": True,
            }
        )
        preflight_request = WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightRequest(
            process_scheduling_result_id=result_id,
            scope=context.scope,
            consumer_subject_id=context.subject_id,
            consumer_audience=context.credential_audience,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.policy_version,
            policy_digest=self._policy.canonical_digest,
            idempotency_key=normalized_key,
            idempotency_digest=idempotency_digest,
            request_fingerprint=fingerprint,
            offline_signature_verifier=self._process_state_signature_verifier,
            offline_process_scheduling_receipt_signature_verifier=(
                self._process_scheduling_receipt_signature_verifier
            ),
        )
        try:
            preflight = (
                await self._repository.preflight_protected_runtime_process_resume_authorization(
                    preflight_request
                )
            )
        except WorkflowProtectedRuntimeProcessResumeAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_process_resume_repository_unavailable")
        statuses = WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightStatus
        if preflight.status is statuses.REPLAY:
            if preflight.lease is None or preflight.evaluated_at is None:
                self._raise(
                    "workflow_protected_runtime_process_resume_repository_contract_violation"
                )
            self._validate_historical_lease(preflight.lease, scope=context.scope)
            await self._postcommit_audit(
                context,
                result_code="workflow_protected_runtime_process_resume_authorization_replayed",
                lease=preflight.lease,
            )
            return preflight.lease
        if preflight.status is not statuses.NONE:
            self._raise_preflight_status(preflight.status)
        if preflight.lease is not None or preflight.evaluated_at is None:
            self._raise("workflow_protected_runtime_process_resume_repository_contract_violation")
        if not self._process_state_attestor.available:
            self._raise("workflow_protected_runtime_process_resume_trusted_attestor_unavailable")
        try:
            source = (
                await self._repository.get_protected_runtime_process_resume_authorization_source(
                    WorkflowProtectedRuntimeProcessResumeAuthorizationSourceRequest(
                        process_scheduling_result_id=result_id,
                        scope=context.scope,
                        consumer_subject_id=self._policy.consumer_subject_id,
                        consumer_audience=self._policy.consumer_audience,
                        consumer_contract_id=self._policy.consumer_contract_id,
                        consumer_contract_version=self._policy.consumer_contract_version,
                    )
                )
            )
        except WorkflowProtectedRuntimeProcessResumeAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_process_resume_repository_unavailable")
        if source is None:
            self._raise("workflow_protected_runtime_process_resume_evidence_conflict")
        result_digest = source.result.canonical_digest
        self._validate_source(source, expected_digest=result_digest, scope=context.scope)
        nonce_digest = canonical_digest({"nonce": uuid4().hex, "fingerprint": fingerprint})
        attestation_request = self._attestation_request(
            source,
            nonce_digest=nonce_digest,
            requested_at=preflight.evaluated_at,
        )
        try:
            attestation = await self._process_state_attestor.attest_runtime_process_resume_state(
                attestation_request
            )
        except WorkflowProtectedRuntimeProcessResumeAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_process_resume_evidence_conflict")
        try:
            authoritative_now = await self._repository.get_authoritative_time()
        except Exception:
            self._raise("workflow_protected_runtime_process_resume_repository_unavailable")
        self._validate_attestation(
            attestation,
            request=attestation_request,
            evaluated_at=authoritative_now,
        )
        candidate_claim, candidate = self._build_candidates(
            source=source,
            attestation=attestation,
            issued_at=authoritative_now,
            idempotency_digest=idempotency_digest,
            request_fingerprint=fingerprint,
        )
        request = WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseRequest(
            source=source,
            process_state_attestation=attestation,
            expected_request_nonce_digest=nonce_digest,
            offline_signature_verifier=self._process_state_signature_verifier,
            offline_process_scheduling_receipt_signature_verifier=(
                self._process_scheduling_receipt_signature_verifier
            ),
            expected_policy_digest=self._policy.canonical_digest,
            expected_validity_window_seconds=self._policy.maximum_lifetime_seconds,
            expected_minimum_remaining_safety_margin_milliseconds=(
                self._policy.minimum_remaining_safety_margin_milliseconds
            ),
            scope=context.scope,
            consumer_subject_id=context.subject_id,
            consumer_audience=context.credential_audience,
            pre_attestation_observed_at=preflight.evaluated_at,
            requested_at=authoritative_now,
            candidate_claim=candidate_claim,
            candidate=candidate,
            idempotency_key=normalized_key,
            idempotency_digest=idempotency_digest,
            request_fingerprint=fingerprint,
        )
        try:
            outcome = await self._repository.authorize_protected_runtime_process_resume(request)
        except WorkflowProtectedRuntimeProcessResumeAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_process_resume_repository_unavailable")
        lease_statuses = WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseStatus
        if outcome.status not in (lease_statuses.AUTHORIZED, lease_statuses.REPLAY):
            self._raise_authorization_status(outcome.status)
        if outcome.lease is None or outcome.evaluated_at is None:
            self._raise("workflow_protected_runtime_process_resume_repository_contract_violation")
        self._validate_historical_lease(outcome.lease, scope=context.scope)
        await self._postcommit_audit(
            context,
            result_code=(
                "workflow_protected_runtime_process_resume_authorization_created"
                if outcome.status is lease_statuses.AUTHORIZED
                else "workflow_protected_runtime_process_resume_authorization_replayed"
            ),
            lease=outcome.lease,
        )
        return outcome.lease

    async def list_presentations(
        self,
        *,
        scope: WorkflowScope,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> WorkflowProtectedRuntimeProcessResumeAuthorizationInventory:
        if not self._repository.durable:
            self._raise("workflow_protected_runtime_process_resume_durable_repository_required")
        try:
            server_time = await self._repository.get_authoritative_time()
            presentations = await (
                self._repository
            ).list_protected_runtime_process_resume_authorization_presentations(
                scope=scope,
                evaluated_at=server_time,
                authorization_lease_ids=authorization_lease_ids,
                limit=max(1, min(limit, 256)),
            )
            inventory = WorkflowProtectedRuntimeProcessResumeAuthorizationInventory(
                server_time=server_time,
                presentations=presentations,
            )
        except WorkflowProtectedRuntimeProcessResumeAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_process_resume_repository_unavailable")
        await self._audit_observed_expiries(inventory)
        return inventory

    def _validate_source(
        self,
        source: WorkflowProtectedRuntimeProcessResumeAuthorizationSource,
        *,
        expected_digest: str,
        scope: object,
    ) -> None:
        result = source.result
        attempt = source.attempt
        claim = source.process_scheduling_claim
        receipt = source.process_scheduling_receipt
        lease = source.process_scheduling_authorization_lease
        authorization_claim = source.process_scheduling_authorization_claim
        source_policy = (
            code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()
        )
        receipt_forbidden = (
            receipt.process_locator_returned,
            receipt.process_identifier_returned,
            receipt.queue_or_priority_returned,
            receipt.caller_material_used,
            receipt.model_activity_performed,
            receipt.network_activity_performed,
            receipt.mcp_activity_performed,
            receipt.connector_activity_performed,
            receipt.provider_activity_performed,
            receipt.infrastructure_mutation_performed,
        )
        lease_authority = lease.authority.canonical_value()
        process_scheduling_grant = lease_authority.pop(
            "protected_runtime_process_scheduling_authority_granted"
        )
        if (
            result.canonical_digest != expected_digest
            or result.canonical_digest != canonical_digest(result.digest_payload())
            or attempt.canonical_digest != canonical_digest(attempt.digest_payload())
            or claim.canonical_digest != canonical_digest(claim.digest_payload())
            or receipt.canonical_digest != canonical_digest(receipt.digest_payload())
            or lease.canonical_digest != canonical_digest(lease.digest_payload())
            or authorization_claim.canonical_digest
            != canonical_digest(authorization_claim.digest_payload())
            or result.result_state
            is not (
                WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState
            ).PROCESS_SCHEDULED_SUSPENDED_IN_PROTECTED_BOUNDARY
            or result.failure_class is not None
            or result.outcome_known is not True
            or result.process_suspended is not True
            or result.process_scheduled is not True
            or result.process_runnable is not False
            or result.process_resumed is not False
            or result.process_dispatched is not False
            or result.process_executed is not False
            or result.receipt_digest != receipt.canonical_digest
            or result.attempt_id != attempt.attempt_id
            or result.attempt_digest != attempt.canonical_digest
            or result.claim_id != claim.claim_id
            or result.claim_digest != claim.canonical_digest
            or result.consumption_id != attempt.consumption_id
            or result.consumption_id != claim.consumption_id
            or attempt.claim_id != claim.claim_id
            or attempt.claim_digest != claim.canonical_digest
            or result.authorization_lease_id != lease.authorization_lease_id
            or result.authorization_lease_digest != lease.canonical_digest
            or attempt.authorization_lease_id != lease.authorization_lease_id
            or attempt.authorization_lease_digest != lease.canonical_digest
            or claim.authorization_lease_id != lease.authorization_lease_id
            or claim.authorization_lease_digest != lease.canonical_digest
            or lease.claim_id != authorization_claim.claim_id
            or lease.claim_digest != authorization_claim.canonical_digest
            or result.scheduling_profile_id != attempt.scheduling_profile_id
            or result.scheduling_profile_version != attempt.scheduling_profile_version
            or result.scheduling_profile_digest != attempt.scheduling_profile_digest
            or result.primitive_id != attempt.primitive_id
            or result.primitive_version != attempt.primitive_version
            or result.primitive_digest != attempt.primitive_digest
            or result.scope != scope
            or attempt.scope != scope
            or claim.scope != scope
            or lease.scope != scope
            or lease.process_created is not True
            or lease.process_sealed is not True
            or lease.process_suspended is not True
            or lease.process_scheduled is not False
            or lease.process_resumed is not False
            or lease.process_dispatched is not False
            or lease.process_executed is not False
            or attempt.consumer_subject_id != source_policy.consumer_subject_id
            or attempt.consumer_audience != source_policy.consumer_audience
            or attempt.consumer_contract_id != source_policy.consumer_contract_id
            or attempt.consumer_contract_version != source_policy.consumer_contract_version
            or result.consumer_subject_id != source_policy.consumer_subject_id
            or result.consumer_audience != source_policy.consumer_audience
            or result.consumer_contract_id != source_policy.consumer_contract_id
            or result.consumer_contract_version != source_policy.consumer_contract_version
            or result.purpose_id != source_policy.purpose_id
            or result.policy_id != source_policy.policy_id
            or result.policy_version != source_policy.policy_version
            or result.policy_digest != source_policy.canonical_digest
            or receipt.result_state is not result.result_state
            or receipt.process_suspended is not True
            or receipt.process_scheduled is not True
            or receipt.process_runnable is not False
            or receipt.process_resumed is not False
            or receipt.process_dispatched is not False
            or receipt.process_executed is not False
            or receipt.completed_at != result.completed_at
            or receipt.signing_key_id != source_policy.receipt_verification_signing_key_id
            or any(receipt_forbidden)
            or not workflow_protected_runtime_process_resume_receipt_matches_source(source)
            or process_scheduling_grant is not True
            or any(lease_authority.values())
            or any(result.authority.canonical_value().values())
            or any(attempt.authority.canonical_value().values())
            or any(claim.authority.canonical_value().values())
            or not self._process_scheduling_receipt_signature_verifier.available
            or not self._process_scheduling_receipt_signature_verifier.verify_receipt(receipt)
        ):
            self._raise("workflow_protected_runtime_process_resume_evidence_conflict")

    def _attestation_request(
        self,
        source: WorkflowProtectedRuntimeProcessResumeAuthorizationSource,
        *,
        nonce_digest: str,
        requested_at: datetime,
    ) -> WorkflowProtectedRuntimeProcessResumeStateAttestationRequest:
        result = source.result
        attempt = source.attempt
        source_policy = (
            code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()
        )
        return WorkflowProtectedRuntimeProcessResumeStateAttestationRequest(
            process_scheduling_result_id=result.result_id,
            process_scheduling_result_digest=result.canonical_digest,
            process_scheduling_consumption_id=result.consumption_id,
            process_scheduling_attempt_id=attempt.attempt_id,
            process_scheduling_attempt_digest=attempt.canonical_digest,
            process_scheduling_claim_id=source.process_scheduling_claim.claim_id,
            process_scheduling_claim_digest=source.process_scheduling_claim.canonical_digest,
            process_scheduling_authorization_lease_id=(
                source.process_scheduling_authorization_lease.authorization_lease_id
            ),
            process_scheduling_authorization_lease_digest=(
                source.process_scheduling_authorization_lease.canonical_digest
            ),
            process_scheduling_authorization_claim_id=(
                source.process_scheduling_authorization_claim.claim_id
            ),
            process_scheduling_authorization_claim_digest=(
                source.process_scheduling_authorization_claim.canonical_digest
            ),
            process_scheduling_receipt_digest=source.process_scheduling_receipt.canonical_digest,
            destination_deployment_id=result.scope.site_id,
            destination_generation=source.process_scheduling_authorization_lease.destination_generation,
            destination_fencing_token_digest=(
                source.process_scheduling_authorization_lease.destination_fencing_token_digest
            ),
            protected_slot_commitment=(
                source.process_scheduling_authorization_lease.protected_slot_commitment
            ),
            protected_slot_generation=(
                source.process_scheduling_authorization_lease.protected_slot_generation
            ),
            runtime_envelope_id=(source.process_scheduling_authorization_lease.runtime_envelope_id),
            runtime_envelope_commitment=(
                source.process_scheduling_authorization_lease.runtime_envelope_commitment
            ),
            runtime_envelope_generation=(
                source.process_scheduling_authorization_lease.runtime_envelope_generation
            ),
            process_scheduling_profile_id=source_policy.scheduling_profile_id,
            process_scheduling_profile_version=source_policy.scheduling_profile_version,
            process_scheduling_profile_digest=source_policy.scheduling_profile_digest,
            primitive_id=source_policy.primitive_id,
            primitive_version=source_policy.primitive_version,
            primitive_digest=source_policy.primitive_digest,
            resume_profile_id=self._policy.resume_profile_id,
            resume_profile_version=self._policy.resume_profile_version,
            resume_profile_digest=self._policy.resume_profile_digest,
            scope=result.scope,
            consumer_subject_id=self._policy.consumer_subject_id,
            consumer_audience=self._policy.consumer_audience,
            consumer_contract_id=self._policy.consumer_contract_id,
            consumer_contract_version=self._policy.consumer_contract_version,
            purpose_id=self._policy.purpose_id,
            request_nonce_digest=nonce_digest,
            requested_at=requested_at,
        )

    def _validate_attestation(
        self,
        attestation: WorkflowProtectedRuntimeProcessResumeStateAttestation,
        *,
        request: WorkflowProtectedRuntimeProcessResumeStateAttestationRequest,
        evaluated_at: datetime,
    ) -> None:
        confirmations = (
            attestation.exact_process_scheduling_result_confirmed,
            attestation.terminal_success_confirmed,
            attestation.metadata_only_confirmed,
            attestation.process_created_confirmed,
            attestation.process_sealed_confirmed,
            attestation.process_suspended_confirmed,
            attestation.process_scheduled_confirmed,
            attestation.process_not_runnable_confirmed,
            attestation.process_not_resumed_confirmed,
            attestation.process_not_dispatched_confirmed,
            attestation.process_not_executed_confirmed,
            attestation.runtime_envelope_current,
            attestation.destination_generation_current,
            attestation.destination_fence_current,
            attestation.protected_slot_generation_current,
            attestation.prior_process_resume_claim_absent,
            attestation.prior_process_resume_lease_absent,
            attestation.pending_or_conflicting_resume_absent,
            attestation.pending_or_conflicting_dispatch_absent,
            attestation.pending_or_conflicting_execution_absent,
            attestation.pending_or_conflicting_supervision_absent,
            attestation.pending_or_conflicting_stop_absent,
            attestation.pending_or_conflicting_cleanup_absent,
            attestation.pending_or_conflicting_replacement_absent,
            attestation.pending_or_conflicting_rescheduling_absent,
        )
        forbidden = (
            attestation.scheduling_performed,
            attestation.resume_performed,
            attestation.dispatch_performed,
            attestation.execution_performed,
            attestation.network_activity_performed,
            attestation.connector_activity_performed,
            attestation.mcp_activity_performed,
            attestation.provider_activity_performed,
            attestation.infrastructure_mutation_performed,
            attestation.process_locator_included,
            attestation.process_identifier_included,
            attestation.process_material_included,
            attestation.runtime_material_included,
            attestation.command_material_included,
            attestation.argument_material_included,
            attestation.environment_material_included,
            attestation.prompt_material_included,
            attestation.model_material_included,
            attestation.endpoint_material_included,
            attestation.credential_material_included,
            attestation.secret_material_included,
        )
        request_values = {
            name: getattr(request, name) for name in request.__slots__ if name != "requested_at"
        }
        signature_valid = (
            self._process_state_signature_verifier
        ).verify_runtime_process_resume_state_attestation(attestation)
        if (
            any(getattr(attestation, name) != value for name, value in request_values.items())
            or attestation.attestor_id != WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTOR_ID
            or attestation.attestor_version
            != WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTOR_VERSION
            or attestation.signing_key_id
            != WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTATION_SIGNING_KEY_ID
            or any(
                value.tzinfo is None
                for value in (
                    request.requested_at,
                    attestation.observed_at,
                    attestation.valid_until,
                    attestation.process_state_eligible_until,
                    evaluated_at,
                )
            )
            or attestation.observed_at < request.requested_at
            or not attestation.observed_at <= evaluated_at < attestation.valid_until
            or evaluated_at
            + timedelta(milliseconds=self._policy.minimum_remaining_safety_margin_milliseconds)
            > attestation.valid_until
            or evaluated_at
            + timedelta(milliseconds=self._policy.minimum_remaining_safety_margin_milliseconds)
            > attestation.process_state_eligible_until
            or attestation.valid_until > attestation.process_state_eligible_until
            or attestation.valid_until - attestation.observed_at
            > timedelta(seconds=self._policy.maximum_attestation_freshness_seconds)
            or not all(confirmations)
            or any(forbidden)
            or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
            or not signature_valid
        ):
            self._raise("workflow_protected_runtime_process_resume_attestation_invalid")

    def _build_candidates(
        self,
        *,
        source: WorkflowProtectedRuntimeProcessResumeAuthorizationSource,
        attestation: WorkflowProtectedRuntimeProcessResumeStateAttestation,
        issued_at: datetime,
        idempotency_digest: str,
        request_fingerprint: str,
    ) -> tuple[
        WorkflowProtectedRuntimeProcessResumeAuthorizationClaim,
        WorkflowProtectedRuntimeProcessResumeAuthorizationLease,
    ]:
        result = source.result
        attempt = source.attempt
        if result.receipt_digest is None:
            self._raise("workflow_protected_runtime_process_resume_evidence_conflict")
        suffix = uuid4().hex
        source_values: dict[str, object] = {
            "process_scheduling_result_id": result.result_id,
            "process_scheduling_result_digest": result.canonical_digest,
            "process_scheduling_consumption_id": result.consumption_id,
            "process_scheduling_attempt_id": attempt.attempt_id,
            "process_scheduling_attempt_digest": attempt.canonical_digest,
            "process_scheduling_claim_id": source.process_scheduling_claim.claim_id,
            "process_scheduling_claim_digest": source.process_scheduling_claim.canonical_digest,
            "process_scheduling_authorization_lease_id": (
                source.process_scheduling_authorization_lease.authorization_lease_id
            ),
            "process_scheduling_authorization_lease_digest": (
                source.process_scheduling_authorization_lease.canonical_digest
            ),
            "process_scheduling_authorization_claim_id": (
                source.process_scheduling_authorization_claim.claim_id
            ),
            "process_scheduling_authorization_claim_digest": (
                source.process_scheduling_authorization_claim.canonical_digest
            ),
            "process_scheduling_receipt_digest": result.receipt_digest,
            "process_scheduling_result_state": result.result_state,
            "process_scheduling_failure_class": result.failure_class,
            "process_scheduling_outcome_known": result.outcome_known,
            "process_created": source.process_scheduling_authorization_lease.process_created,
            "process_sealed": source.process_scheduling_authorization_lease.process_sealed,
            "process_suspended": result.process_suspended,
            "process_scheduled": result.process_scheduled,
            "process_runnable": result.process_runnable,
            "process_resumed": result.process_resumed,
            "process_dispatched": result.process_dispatched,
            "process_executed": result.process_executed,
            "process_scheduling_completed_at": result.completed_at,
            "process_scheduling_result_recorded_at": result.recorded_at,
            "destination_deployment_id": result.scope.site_id,
            "destination_generation": (
                source.process_scheduling_authorization_lease.destination_generation
            ),
            "destination_fencing_token_digest": (
                source.process_scheduling_authorization_lease.destination_fencing_token_digest
            ),
            "protected_slot_commitment": (
                source.process_scheduling_authorization_lease.protected_slot_commitment
            ),
            "protected_slot_generation": (
                source.process_scheduling_authorization_lease.protected_slot_generation
            ),
            "runtime_envelope_id": (
                source.process_scheduling_authorization_lease.runtime_envelope_id
            ),
            "runtime_envelope_commitment": (
                source.process_scheduling_authorization_lease.runtime_envelope_commitment
            ),
            "runtime_envelope_generation": (
                source.process_scheduling_authorization_lease.runtime_envelope_generation
            ),
            "process_scheduling_profile_id": result.scheduling_profile_id,
            "process_scheduling_profile_version": result.scheduling_profile_version,
            "process_scheduling_profile_digest": result.scheduling_profile_digest,
            "primitive_id": result.primitive_id,
            "primitive_version": result.primitive_version,
            "primitive_digest": result.primitive_digest,
            "scope": result.scope,
            "consumer_subject_id": self._policy.consumer_subject_id,
            "consumer_audience": self._policy.consumer_audience,
            "consumer_contract_id": self._policy.consumer_contract_id,
            "consumer_contract_version": self._policy.consumer_contract_version,
            "purpose_id": self._policy.purpose_id,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
        }
        claim_values = {
            **source_values,
            "claim_id": f"workflow-protected-runtime-process-resume-claim.{suffix}",
            "request_fingerprint": request_fingerprint,
            "idempotency_digest": idempotency_digest,
            "authorization_audit_digest": canonical_digest(
                {
                    "policy_digest": self._policy.canonical_digest,
                    "request_fingerprint": request_fingerprint,
                    "scope": result.scope.canonical_value(),
                    "process_scheduling_result_id": result.result_id,
                }
            ),
            "claimed_at": issued_at,
            "authority": WorkflowProtectedRuntimeProcessResumeAuthorizationAuthority(),
        }
        claim = WorkflowProtectedRuntimeProcessResumeAuthorizationClaim(
            **cast(Any, claim_values),
            canonical_digest=canonical_digest(_payload(claim_values)),
        )
        effective_until = min(
            issued_at + timedelta(seconds=self._policy.maximum_lifetime_seconds),
            attestation.valid_until,
            attestation.process_state_eligible_until,
        )
        if effective_until - issued_at < timedelta(
            milliseconds=self._policy.minimum_remaining_safety_margin_milliseconds
        ):
            self._raise("workflow_protected_runtime_process_resume_attestation_expired")
        lease_values = {
            **source_values,
            "authorization_lease_id": (
                f"workflow-protected-runtime-process-resume-authorization-lease.{suffix}"
            ),
            "claim_id": claim.claim_id,
            "claim_digest": claim.canonical_digest,
            "process_state_attestation_id": attestation.attestation_id,
            "process_state_attestation_digest": attestation.canonical_digest,
            "process_state_attestation_valid_until": attestation.valid_until,
            "process_state_eligible_until": attestation.process_state_eligible_until,
            "attestation_metadata_only": True,
            "resume_profile_id": self._policy.resume_profile_id,
            "resume_profile_version": self._policy.resume_profile_version,
            "resume_profile_digest": self._policy.resume_profile_digest,
            "issued_at": issued_at,
            "valid_until": effective_until,
            "effective_until": effective_until,
            "single_use": True,
            "renewable": False,
            "transferable": False,
            "lease_is_bearer_capability": False,
            "state": (
                WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
            ),
            "authority": WorkflowProtectedRuntimeProcessResumeAuthorizationAuthority(
                protected_runtime_process_resume_authority_granted=True
            ),
        }
        lease = WorkflowProtectedRuntimeProcessResumeAuthorizationLease(
            **cast(Any, lease_values),
            canonical_digest=canonical_digest(_payload(lease_values)),
        )
        return claim, lease

    def _validate_historical_lease(
        self, lease: WorkflowProtectedRuntimeProcessResumeAuthorizationLease, *, scope: object
    ) -> None:
        authority = lease.authority.canonical_value()
        dedicated = authority.pop("protected_runtime_process_resume_authority_granted")
        if (
            lease.scope != scope
            or lease.policy_digest != self._policy.canonical_digest
            or lease.canonical_digest != canonical_digest(lease.digest_payload())
            or lease.valid_until - lease.issued_at > timedelta(seconds=1)
            or lease.valid_until > lease.process_state_attestation_valid_until
            or lease.single_use is not True
            or lease.renewable is not False
            or lease.transferable is not False
            or lease.lease_is_bearer_capability is not False
            or dedicated is not True
            or any(authority.values())
        ):
            self._raise("workflow_protected_runtime_process_resume_repository_contract_violation")

    async def _postcommit_audit(
        self,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
        *,
        result_code: str,
        lease: WorkflowProtectedRuntimeProcessResumeAuthorizationLease,
    ) -> None:
        try:
            await self._audit_sink.record(
                AuditRecord(
                    event_id=f"evt_{uuid4().hex}",
                    event_type="atlas.workflow.protected-runtime-process-resume-authorization.commit",
                    schema_version="1.0",
                    producer=WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_AUTHORIZATION_PRODUCER,
                    producer_version=__version__,
                    occurred_at=context.requested_at,
                    correlation_id=context.correlation_id,
                    subject_id=context.subject_id,
                    actor_type=context.actor_type,
                    authentication_method=context.authentication_method,
                    assurance_level="workload",
                    permission_id="workflow.protected-runtime-process-resume-authorizations.create",
                    resource_type=(
                        "resource.workflow-protected-runtime-process-resume-authorization-lease"
                    ),
                    scope_reference="/".join(
                        (*context.scope.canonical_value().values(), "runtime-process-resume")
                    ),
                    decision_id=context.decision_id,
                    outcome="succeeded",
                    result_code=result_code,
                    idempotency_key=None,
                    target_metadata=(
                        ("authorization_lease_id", lease.authorization_lease_id),
                        ("protected_runtime_process_resume_request_authority", "true"),
                        ("process_scheduling_performed", "false"),
                        ("scheduling_authority", "false"),
                        ("scheduling_performed", "false"),
                        ("resume_performed", "false"),
                        ("dispatch_performed", "false"),
                        ("network_access_authority", "false"),
                        ("connector_activity_authority", "false"),
                        ("execution_authority", "false"),
                        ("execution_performed", "false"),
                        ("infrastructure_mutation_authority", "false"),
                    ),
                )
            )
        except Exception:
            return

    async def _rejection_audit(
        self,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
        *,
        result_code: str,
        process_scheduling_result_id: str,
    ) -> None:
        evidence_reference = canonical_digest(
            {"process_scheduling_result_id": process_scheduling_result_id.strip()}
        )[:24]
        try:
            await self._audit_sink.record(
                AuditRecord(
                    event_id=f"evt_{uuid4().hex}",
                    event_type=(
                        "atlas.workflow.protected-runtime-process-resume-authorization.rejected"
                    ),
                    schema_version="1.0",
                    producer=WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_AUTHORIZATION_PRODUCER,
                    producer_version=__version__,
                    occurred_at=context.requested_at,
                    correlation_id=context.correlation_id,
                    subject_id=context.subject_id,
                    actor_type=context.actor_type,
                    authentication_method=context.authentication_method,
                    assurance_level="workload",
                    permission_id=(
                        "workflow.protected-runtime-process-resume-authorizations.create"
                    ),
                    resource_type=(
                        "resource.workflow-protected-runtime-process-resume-authorization-lease"
                    ),
                    scope_reference="/".join(
                        (*context.scope.canonical_value().values(), "runtime-process-resume")
                    ),
                    decision_id=context.decision_id,
                    outcome="denied",
                    result_code=result_code,
                    idempotency_key=None,
                    target_metadata=(
                        ("process_scheduling_result_reference", f"integrity.{evidence_reference}"),
                        ("protected_runtime_process_resume_request_authority", "false"),
                        ("process_scheduling_performed", "false"),
                        ("scheduling_performed", "false"),
                        ("execution_performed", "false"),
                        ("infrastructure_mutation_performed", "false"),
                    ),
                )
            )
        except Exception:
            return

    async def _audit_observed_expiries(
        self, inventory: WorkflowProtectedRuntimeProcessResumeAuthorizationInventory
    ) -> None:
        for presentation in inventory.presentations:
            if presentation.effective_state.value != "expired":
                continue
            lease = presentation.lease
            audit_digest = canonical_digest(
                {
                    "authorization_lease_digest": lease.canonical_digest,
                    "effective_until": lease.effective_until.isoformat(),
                    "event": "observed-expiry",
                }
            )
            event_id = f"evt_{audit_digest[:32]}"
            if event_id in self._observed_expiry_audit_ids:
                continue
            self._observed_expiry_audit_ids.add(event_id)
            try:
                await self._audit_sink.record(
                    AuditRecord(
                        event_id=event_id,
                        event_type=(
                            "atlas.workflow.protected-runtime-process-resume-authorization.expired"
                        ),
                        schema_version="1.0",
                        producer=(WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_AUTHORIZATION_PRODUCER),
                        producer_version=__version__,
                        occurred_at=inventory.server_time,
                        correlation_id=f"expiry-observation.{audit_digest[:24]}",
                        subject_id=None,
                        actor_type="service",
                        authentication_method="internal_projection",
                        assurance_level="system",
                        permission_id=(
                            "workflow.protected-runtime-process-resume-authorizations.read"
                        ),
                        resource_type=(
                            "resource.workflow-protected-runtime-process-resume-authorization-lease"
                        ),
                        scope_reference="/".join(
                            (*lease.scope.canonical_value().values(), "runtime-process-resume")
                        ),
                        decision_id=None,
                        outcome="succeeded",
                        result_code=(
                            "workflow_protected_runtime_process_resume_authorization_expired"
                        ),
                        idempotency_key=None,
                        target_metadata=(
                            ("authorization_reference", f"integrity.{audit_digest[:24]}"),
                            ("effective_state", "expired"),
                            ("protected_runtime_process_resume_request_authority", "false"),
                            ("process_scheduling_performed", "false"),
                            ("scheduling_performed", "false"),
                            ("execution_performed", "false"),
                            ("infrastructure_mutation_performed", "false"),
                        ),
                    )
                )
            except Exception:
                self._observed_expiry_audit_ids.discard(event_id)

    @classmethod
    def _raise_preflight_status(
        cls, status: WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightStatus
    ) -> NoReturn:
        statuses = WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightStatus
        cls._raise(
            {
                statuses.IDEMPOTENCY_CONFLICT: (
                    "workflow_protected_runtime_process_resume_idempotency_conflict"
                ),
                statuses.EVIDENCE_CONFLICT: (
                    "workflow_protected_runtime_process_resume_evidence_conflict"
                ),
                statuses.ALREADY_AUTHORIZED: (
                    "workflow_protected_runtime_process_resume_already_authorized"
                ),
            }.get(
                status,
                "workflow_protected_runtime_process_resume_repository_contract_violation",
            )
        )

    @classmethod
    def _raise_authorization_status(
        cls, status: WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseStatus
    ) -> NoReturn:
        statuses = WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseStatus
        cls._raise(
            {
                statuses.IDEMPOTENCY_CONFLICT: (
                    "workflow_protected_runtime_process_resume_idempotency_conflict"
                ),
                statuses.EVIDENCE_CONFLICT: (
                    "workflow_protected_runtime_process_resume_evidence_conflict"
                ),
                statuses.ALREADY_AUTHORIZED: (
                    "workflow_protected_runtime_process_resume_already_authorized"
                ),
            }.get(
                status,
                "workflow_protected_runtime_process_resume_repository_contract_violation",
            )
        )

    @staticmethod
    def _require_workload(
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> None:
        if (
            context.subject_id != WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT
            or context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience
            != WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
        ):
            WorkflowProtectedRuntimeProcessResumeAuthorizationService._raise(
                "workflow_protected_runtime_process_resume_consumer_identity_required"
            )

    @staticmethod
    def _identifier(value: str, name: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 240 or any(c.isspace() for c in normalized):
            WorkflowProtectedRuntimeProcessResumeAuthorizationService._raise(
                f"workflow_protected_runtime_process_resume_{name}_invalid"
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            cls._raise("workflow_protected_runtime_process_resume_idempotency_key_invalid")
        return normalized

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowProtectedRuntimeProcessResumeAuthorizationError(
            code,
            "The protected runtime process-resume authorization request was denied.",
        )


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
    "WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_AUTHORIZATION_PRODUCER",
    "WorkflowProtectedRuntimeProcessResumeAuthorizationService",
]

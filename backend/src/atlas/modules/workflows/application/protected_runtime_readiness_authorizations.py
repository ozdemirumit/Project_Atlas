from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.protected_runtime_readiness_authorization_ports import (
    WorkflowProtectedRuntimeReadinessAuthorizationError,
    WorkflowProtectedRuntimeReadinessAuthorizationLeaseRequest,
    WorkflowProtectedRuntimeReadinessAuthorizationLeaseStatus,
    WorkflowProtectedRuntimeReadinessAuthorizationPreflightRequest,
    WorkflowProtectedRuntimeReadinessAuthorizationPreflightStatus,
    WorkflowProtectedRuntimeReadinessAuthorizationPresentation,
    WorkflowProtectedRuntimeReadinessAuthorizationRepository,
    WorkflowProtectedRuntimeReadinessAuthorizationSource,
    WorkflowProtectedRuntimeReadinessAuthorizationSourceRequest,
    WorkflowProtectedRuntimeReadinessLifecycleAttestation,
    WorkflowProtectedRuntimeReadinessLifecycleAttestationRequest,
    WorkflowProtectedRuntimeReadinessLifecycleAttestor,
    WorkflowProtectedRuntimeReadinessLifecycleSignatureVerifier,
    workflow_protected_runtime_readiness_starter_receipt_matches_source,
)
from atlas.modules.workflows.application.protected_runtime_start_consumption_ports import (
    WorkflowProtectedRuntimeStartReceiptSignatureVerifier,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_readiness_authorization_domain import (
    WorkflowProtectedRuntimeReadinessAuthorizationAuthority,
    WorkflowProtectedRuntimeReadinessAuthorizationClaim,
    WorkflowProtectedRuntimeReadinessAuthorizationLease,
    WorkflowProtectedRuntimeReadinessAuthorizationLeaseState,
    WorkflowProtectedRuntimeReadinessAuthorizationPolicy,
    code_owned_workflow_protected_runtime_readiness_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_start_consumption_domain import (
    WorkflowProtectedRuntimeStartConsumptionResultState,
)

WORKFLOW_PROTECTED_RUNTIME_READINESS_AUTHORIZATION_PRODUCER = (
    "project-atlas-workflow-protected-runtime-readiness-authorizer"
)


class WorkflowProtectedRuntimeReadinessAuthorizationService:
    """Issues one future readiness-request lease without performing a probe."""

    def __init__(
        self,
        *,
        authorization_repository: WorkflowProtectedRuntimeReadinessAuthorizationRepository,
        lifecycle_attestor: WorkflowProtectedRuntimeReadinessLifecycleAttestor,
        lifecycle_signature_verifier: (WorkflowProtectedRuntimeReadinessLifecycleSignatureVerifier),
        start_receipt_signature_verifier: WorkflowProtectedRuntimeStartReceiptSignatureVerifier,
        audit_sink: AuditSink,
        policy: WorkflowProtectedRuntimeReadinessAuthorizationPolicy | None = None,
    ) -> None:
        self._repository = authorization_repository
        self._lifecycle_attestor = lifecycle_attestor
        self._lifecycle_signature_verifier = lifecycle_signature_verifier
        self._start_receipt_signature_verifier = start_receipt_signature_verifier
        self._audit_sink = audit_sink
        self._policy = (
            policy or code_owned_workflow_protected_runtime_readiness_authorization_policy()
        )

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def repository(self) -> WorkflowProtectedRuntimeReadinessAuthorizationRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowProtectedRuntimeReadinessAuthorizationPolicy:
        return self._policy

    async def authorize(
        self,
        *,
        start_result_id: str,
        start_result_digest: str,
        policy_id: str,
        policy_version: str,
        idempotency_key: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> WorkflowProtectedRuntimeReadinessAuthorizationLease:
        self._require_workload(context)
        if not self._repository.durable:
            self._raise("workflow_protected_runtime_readiness_durable_repository_required")
        result_id = self._identifier(start_result_id, "start_result_id")
        result_digest = self._digest(start_result_digest, "start_result_digest")
        normalized_key = self._idempotency_key(idempotency_key)
        if policy_id != self._policy.policy_id or policy_version != self._policy.policy_version:
            self._raise("workflow_protected_runtime_readiness_policy_conflict")
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
                "start_result_digest": result_digest,
                "start_result_id": result_id,
                "subject_id": context.subject_id,
            }
        )
        preflight_request = WorkflowProtectedRuntimeReadinessAuthorizationPreflightRequest(
            start_result_id=result_id,
            start_result_digest=result_digest,
            scope=context.scope,
            consumer_subject_id=context.subject_id,
            consumer_audience=context.credential_audience,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.policy_version,
            policy_digest=self._policy.canonical_digest,
            idempotency_key=normalized_key,
            idempotency_digest=idempotency_digest,
            request_fingerprint=fingerprint,
            offline_signature_verifier=self._lifecycle_signature_verifier,
            offline_start_receipt_signature_verifier=(self._start_receipt_signature_verifier),
        )
        try:
            preflight = await self._repository.preflight_protected_runtime_readiness_authorization(
                preflight_request
            )
        except WorkflowProtectedRuntimeReadinessAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_readiness_repository_unavailable")
        statuses = WorkflowProtectedRuntimeReadinessAuthorizationPreflightStatus
        if preflight.status is statuses.REPLAY:
            if preflight.lease is None or preflight.evaluated_at is None:
                self._raise("workflow_protected_runtime_readiness_repository_contract_violation")
            self._validate_historical_lease(preflight.lease, scope=context.scope)
            await self._postcommit_audit(
                context,
                result_code="workflow_protected_runtime_readiness_authorization_replayed",
                lease=preflight.lease,
            )
            return preflight.lease
        if preflight.status is not statuses.NONE:
            self._raise_preflight_status(preflight.status)
        if preflight.lease is not None or preflight.evaluated_at is None:
            self._raise("workflow_protected_runtime_readiness_repository_contract_violation")
        if not self._lifecycle_attestor.available:
            self._raise("workflow_protected_runtime_readiness_trusted_attestor_unavailable")
        try:
            source = await self._repository.get_protected_runtime_readiness_authorization_source(
                WorkflowProtectedRuntimeReadinessAuthorizationSourceRequest(
                    start_result_id=result_id,
                    start_result_digest=result_digest,
                    scope=context.scope,
                    consumer_subject_id=self._policy.consumer_subject_id,
                    consumer_audience=self._policy.consumer_audience,
                    consumer_contract_id=self._policy.consumer_contract_id,
                    consumer_contract_version=self._policy.consumer_contract_version,
                )
            )
        except WorkflowProtectedRuntimeReadinessAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_readiness_repository_unavailable")
        if source is None:
            self._raise("workflow_protected_runtime_readiness_evidence_conflict")
        self._validate_source(source, expected_digest=result_digest, scope=context.scope)
        nonce_digest = canonical_digest({"nonce": uuid4().hex, "fingerprint": fingerprint})
        attestation_request = self._attestation_request(
            source,
            nonce_digest=nonce_digest,
            requested_at=preflight.evaluated_at,
        )
        try:
            attestation = await self._lifecycle_attestor.attest_runtime_readiness_lifecycle(
                attestation_request
            )
        except WorkflowProtectedRuntimeReadinessAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_readiness_evidence_conflict")
        try:
            authoritative_now = await self._repository.get_authoritative_time()
        except Exception:
            self._raise("workflow_protected_runtime_readiness_repository_unavailable")
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
        request = WorkflowProtectedRuntimeReadinessAuthorizationLeaseRequest(
            source=source,
            lifecycle_attestation=attestation,
            expected_request_nonce_digest=nonce_digest,
            offline_signature_verifier=self._lifecycle_signature_verifier,
            offline_start_receipt_signature_verifier=(self._start_receipt_signature_verifier),
            expected_policy_digest=self._policy.canonical_digest,
            expected_validity_window_seconds=self._policy.maximum_lifetime_seconds,
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
            outcome = await self._repository.authorize_protected_runtime_readiness(request)
        except WorkflowProtectedRuntimeReadinessAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_readiness_repository_unavailable")
        lease_statuses = WorkflowProtectedRuntimeReadinessAuthorizationLeaseStatus
        if outcome.status not in (lease_statuses.AUTHORIZED, lease_statuses.REPLAY):
            self._raise_authorization_status(outcome.status)
        if outcome.lease is None or outcome.evaluated_at is None:
            self._raise("workflow_protected_runtime_readiness_repository_contract_violation")
        self._validate_historical_lease(outcome.lease, scope=context.scope)
        await self._postcommit_audit(
            context,
            result_code=(
                "workflow_protected_runtime_readiness_authorization_created"
                if outcome.status is lease_statuses.AUTHORIZED
                else "workflow_protected_runtime_readiness_authorization_replayed"
            ),
            lease=outcome.lease,
        )
        return outcome.lease

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeReadinessAuthorizationPresentation, ...]:
        if not self._repository.durable:
            self._raise("workflow_protected_runtime_readiness_durable_repository_required")
        try:
            return await (
                self._repository.list_protected_runtime_readiness_authorization_presentations(
                    scope=scope,
                    limit=max(1, min(limit, 256)),
                )
            )
        except WorkflowProtectedRuntimeReadinessAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_readiness_repository_unavailable")

    def _validate_source(
        self,
        source: WorkflowProtectedRuntimeReadinessAuthorizationSource,
        *,
        expected_digest: str,
        scope: object,
    ) -> None:
        result = source.result
        attempt = source.attempt
        claim = source.start_claim
        receipt = source.starter_receipt
        lease = source.start_authorization_lease
        authorization_claim = source.start_authorization_claim
        receipt_forbidden = (
            receipt.scheduling_performed,
            receipt.runtime_resumed,
            receipt.generic_process_created,
            receipt.prompt_constructed,
            receipt.model_inference_performed,
            receipt.network_activity_performed,
            receipt.readiness_probe_performed,
            receipt.publication_performed,
            receipt.delivery_performed,
            receipt.connector_activity_performed,
            receipt.dispatch_performed,
            receipt.execution_performed,
            receipt.infrastructure_mutation_performed,
        )
        lease_authority = lease.authority.canonical_value()
        start_grant = lease_authority.pop("protected_runtime_start_authority_granted")
        if (
            result.canonical_digest != expected_digest
            or result.canonical_digest != canonical_digest(result.digest_payload())
            or attempt.canonical_digest != canonical_digest(attempt.digest_payload())
            or claim.canonical_digest != canonical_digest(claim.digest_payload())
            or receipt.canonical_digest != canonical_digest(receipt.digest_payload())
            or lease.canonical_digest != canonical_digest(lease.digest_payload())
            or authorization_claim.canonical_digest
            != canonical_digest(authorization_claim.digest_payload())
            or result.state
            is not (
                WorkflowProtectedRuntimeStartConsumptionResultState
            ).RUNTIME_STARTED_IN_PROTECTED_BOUNDARY
            or result.failure_class is not None
            or result.outcome_known is not True
            or result.runtime_started is not True
            or result.completed_at is None
            or result.starter_receipt_digest != receipt.canonical_digest
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
            or result.destination_deployment_id != attempt.destination_deployment_id
            or result.destination_generation != attempt.destination_generation
            or result.runtime_envelope_commitment != attempt.runtime_envelope_commitment
            or result.runtime_envelope_generation != attempt.runtime_envelope_generation
            or result.runtime_start_profile_id != attempt.runtime_start_profile_id
            or result.runtime_start_profile_version != attempt.runtime_start_profile_version
            or result.runtime_start_profile_digest != attempt.runtime_start_profile_digest
            or result.scope != scope
            or attempt.scope != scope
            or attempt.consumer_subject_id != self._policy.consumer_subject_id
            or attempt.consumer_audience != self._policy.consumer_audience
            or attempt.consumer_contract_id != self._policy.consumer_contract_id
            or attempt.consumer_contract_version != self._policy.consumer_contract_version
            or receipt.result_state is not result.state
            or receipt.runtime_started is not True
            or receipt.runtime_start_count_pre != 0
            or receipt.runtime_start_count_post != 1
            or receipt.runtime_envelope_current is not True
            or receipt.runtime_envelope_inactive is not False
            or receipt.completed_at != result.completed_at
            or receipt.signing_key_id != self._policy.receipt_verification_signing_key_id
            or any(receipt_forbidden)
            or not workflow_protected_runtime_readiness_starter_receipt_matches_source(source)
            or start_grant is not True
            or any(lease_authority.values())
            or any(result.authority.canonical_value().values())
            or any(attempt.authority.canonical_value().values())
            or any(claim.authority.canonical_value().values())
            or not self._start_receipt_signature_verifier.available
            or not self._start_receipt_signature_verifier.verify_receipt(receipt)
        ):
            self._raise("workflow_protected_runtime_readiness_evidence_conflict")

    def _attestation_request(
        self,
        source: WorkflowProtectedRuntimeReadinessAuthorizationSource,
        *,
        nonce_digest: str,
        requested_at: datetime,
    ) -> WorkflowProtectedRuntimeReadinessLifecycleAttestationRequest:
        result = source.result
        attempt = source.attempt
        return WorkflowProtectedRuntimeReadinessLifecycleAttestationRequest(
            start_result_id=result.result_id,
            start_result_digest=result.canonical_digest,
            start_consumption_id=result.consumption_id,
            start_attempt_id=attempt.attempt_id,
            start_attempt_digest=attempt.canonical_digest,
            start_claim_id=source.start_claim.claim_id,
            start_claim_digest=source.start_claim.canonical_digest,
            start_authorization_lease_id=source.start_authorization_lease.authorization_lease_id,
            start_authorization_lease_digest=source.start_authorization_lease.canonical_digest,
            starter_receipt_digest=source.starter_receipt.canonical_digest,
            destination_deployment_id=result.destination_deployment_id,
            destination_generation=result.destination_generation,
            destination_fencing_token_digest=attempt.destination_fencing_token_digest,
            protected_slot_commitment=attempt.runtime_slot_commitment,
            protected_slot_generation=attempt.runtime_slot_generation,
            runtime_envelope_id=attempt.runtime_envelope_id,
            runtime_envelope_commitment=result.runtime_envelope_commitment,
            runtime_envelope_generation=result.runtime_envelope_generation,
            runtime_start_profile_id=result.runtime_start_profile_id,
            runtime_start_profile_version=result.runtime_start_profile_version,
            runtime_start_profile_digest=result.runtime_start_profile_digest,
            readiness_profile_id=self._policy.readiness_profile_id,
            readiness_profile_version=self._policy.readiness_profile_version,
            readiness_profile_digest=self._policy.readiness_profile_digest,
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
        attestation: WorkflowProtectedRuntimeReadinessLifecycleAttestation,
        *,
        request: WorkflowProtectedRuntimeReadinessLifecycleAttestationRequest,
        evaluated_at: datetime,
    ) -> None:
        confirmations = (
            attestation.exact_start_result_confirmed,
            attestation.runtime_started_confirmed,
            attestation.runtime_envelope_current,
            attestation.runtime_envelope_started,
            attestation.destination_generation_current,
            attestation.destination_fence_current,
            attestation.protected_slot_generation_current,
            attestation.readiness_profile_eligible,
            attestation.prior_readiness_claim_absent,
            attestation.prior_readiness_lease_absent,
            attestation.prior_readiness_attempt_absent,
            attestation.prior_readiness_result_absent,
        )
        forbidden = (
            attestation.runtime_resumed,
            attestation.runtime_stopped,
            attestation.runtime_restarted,
            attestation.generic_process_created,
            attestation.scheduling_performed,
            attestation.readiness_probe_performed,
            attestation.network_activity_performed,
            attestation.connector_activity_performed,
            attestation.publication_performed,
            attestation.delivery_performed,
            attestation.dispatch_performed,
            attestation.execution_performed,
            attestation.infrastructure_mutation_performed,
            attestation.runtime_locator_included,
            attestation.process_identifier_included,
            attestation.context_included,
            attestation.endpoint_included,
            attestation.credential_included,
            attestation.secret_included,
            attestation.command_included,
        )
        request_values = {
            name: getattr(request, name) for name in request.__slots__ if name != "requested_at"
        }
        signature_valid = (
            self._lifecycle_signature_verifier.verify_runtime_readiness_lifecycle_attestation(
                attestation
            )
        )
        if (
            any(getattr(attestation, name) != value for name, value in request_values.items())
            or attestation.attestor_id != self._policy.required_attestor_id
            or attestation.attestor_version != self._policy.required_attestor_version
            or attestation.signing_key_id != self._policy.verification_signing_key_id
            or any(
                value.tzinfo is None
                for value in (
                    request.requested_at,
                    attestation.observed_at,
                    attestation.valid_until,
                    attestation.runtime_envelope_eligible_until,
                    evaluated_at,
                )
            )
            or attestation.observed_at < request.requested_at
            or not attestation.observed_at <= evaluated_at < attestation.valid_until
            or attestation.valid_until > attestation.runtime_envelope_eligible_until
            or attestation.valid_until - attestation.observed_at
            > timedelta(seconds=self._policy.maximum_attestation_freshness_seconds)
            or not all(confirmations)
            or any(forbidden)
            or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
            or not signature_valid
        ):
            self._raise("workflow_protected_runtime_readiness_attestation_invalid")

    def _build_candidates(
        self,
        *,
        source: WorkflowProtectedRuntimeReadinessAuthorizationSource,
        attestation: WorkflowProtectedRuntimeReadinessLifecycleAttestation,
        issued_at: datetime,
        idempotency_digest: str,
        request_fingerprint: str,
    ) -> tuple[
        WorkflowProtectedRuntimeReadinessAuthorizationClaim,
        WorkflowProtectedRuntimeReadinessAuthorizationLease,
    ]:
        result = source.result
        attempt = source.attempt
        if result.completed_at is None or result.starter_receipt_digest is None:
            self._raise("workflow_protected_runtime_readiness_evidence_conflict")
        suffix = uuid4().hex
        source_values: dict[str, object] = {
            "start_result_id": result.result_id,
            "start_result_digest": result.canonical_digest,
            "start_consumption_id": result.consumption_id,
            "start_attempt_id": attempt.attempt_id,
            "start_attempt_digest": attempt.canonical_digest,
            "start_claim_id": source.start_claim.claim_id,
            "start_claim_digest": source.start_claim.canonical_digest,
            "start_authorization_lease_id": (
                source.start_authorization_lease.authorization_lease_id
            ),
            "start_authorization_lease_digest": (source.start_authorization_lease.canonical_digest),
            "starter_receipt_digest": result.starter_receipt_digest,
            "start_result_state": result.state,
            "start_completed_at": result.completed_at,
            "start_result_recorded_at": result.recorded_at,
            "start_outcome_known": result.outcome_known,
            "runtime_started": result.runtime_started,
            "destination_deployment_id": result.destination_deployment_id,
            "destination_generation": result.destination_generation,
            "destination_fencing_token_digest": attempt.destination_fencing_token_digest,
            "protected_slot_commitment": attempt.runtime_slot_commitment,
            "protected_slot_generation": attempt.runtime_slot_generation,
            "runtime_envelope_id": attempt.runtime_envelope_id,
            "runtime_envelope_commitment": result.runtime_envelope_commitment,
            "runtime_envelope_generation": result.runtime_envelope_generation,
            "runtime_start_profile_id": result.runtime_start_profile_id,
            "runtime_start_profile_version": result.runtime_start_profile_version,
            "runtime_start_profile_digest": result.runtime_start_profile_digest,
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
            "claim_id": f"workflow-protected-runtime-readiness-claim.{suffix}",
            "request_fingerprint": request_fingerprint,
            "idempotency_digest": idempotency_digest,
            "authorization_audit_digest": canonical_digest(
                {
                    "policy_digest": self._policy.canonical_digest,
                    "request_fingerprint": request_fingerprint,
                    "scope": result.scope.canonical_value(),
                    "start_result_id": result.result_id,
                }
            ),
            "claimed_at": issued_at,
            "authority": WorkflowProtectedRuntimeReadinessAuthorizationAuthority(),
        }
        claim = WorkflowProtectedRuntimeReadinessAuthorizationClaim(
            **cast(Any, claim_values),
            canonical_digest=canonical_digest(_payload(claim_values)),
        )
        effective_until = min(
            issued_at + timedelta(seconds=self._policy.maximum_lifetime_seconds),
            attestation.valid_until,
            attestation.runtime_envelope_eligible_until,
        )
        if effective_until <= issued_at:
            self._raise("workflow_protected_runtime_readiness_attestation_expired")
        lease_values = {
            **source_values,
            "authorization_lease_id": f"workflow-protected-runtime-readiness-lease.{suffix}",
            "claim_id": claim.claim_id,
            "claim_digest": claim.canonical_digest,
            "lifecycle_attestation_id": attestation.attestation_id,
            "lifecycle_attestation_digest": attestation.canonical_digest,
            "lifecycle_attestation_valid_until": attestation.valid_until,
            "runtime_envelope_eligible_until": attestation.runtime_envelope_eligible_until,
            "readiness_profile_id": self._policy.readiness_profile_id,
            "readiness_profile_version": self._policy.readiness_profile_version,
            "readiness_profile_digest": self._policy.readiness_profile_digest,
            "issued_at": issued_at,
            "valid_until": effective_until,
            "effective_until": effective_until,
            "single_use": True,
            "renewable": False,
            "transferable": False,
            "lease_is_bearer_capability": False,
            "state": (
                WorkflowProtectedRuntimeReadinessAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
            ),
            "authority": WorkflowProtectedRuntimeReadinessAuthorizationAuthority(
                protected_runtime_readiness_authority_granted=True
            ),
        }
        lease = WorkflowProtectedRuntimeReadinessAuthorizationLease(
            **cast(Any, lease_values),
            canonical_digest=canonical_digest(_payload(lease_values)),
        )
        return claim, lease

    def _validate_historical_lease(
        self, lease: WorkflowProtectedRuntimeReadinessAuthorizationLease, *, scope: object
    ) -> None:
        authority = lease.authority.canonical_value()
        dedicated = authority.pop("protected_runtime_readiness_authority_granted")
        if (
            lease.scope != scope
            or lease.policy_digest != self._policy.canonical_digest
            or lease.canonical_digest != canonical_digest(lease.digest_payload())
            or lease.valid_until - lease.issued_at > timedelta(seconds=1)
            or lease.valid_until > lease.lifecycle_attestation_valid_until
            or lease.single_use is not True
            or lease.renewable is not False
            or lease.transferable is not False
            or lease.lease_is_bearer_capability is not False
            or dedicated is not True
            or any(authority.values())
        ):
            self._raise("workflow_protected_runtime_readiness_repository_contract_violation")

    async def _postcommit_audit(
        self,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
        *,
        result_code: str,
        lease: WorkflowProtectedRuntimeReadinessAuthorizationLease,
    ) -> None:
        try:
            await self._audit_sink.record(
                AuditRecord(
                    event_id=f"evt_{uuid4().hex}",
                    event_type="atlas.workflow.protected-runtime-readiness-authorization.commit",
                    schema_version="1.0",
                    producer=WORKFLOW_PROTECTED_RUNTIME_READINESS_AUTHORIZATION_PRODUCER,
                    producer_version=__version__,
                    occurred_at=context.requested_at,
                    correlation_id=context.correlation_id,
                    subject_id=context.subject_id,
                    actor_type=context.actor_type,
                    authentication_method=context.authentication_method,
                    assurance_level="workload",
                    permission_id="workflow.protected-runtime-readiness-authorizations.create",
                    resource_type=(
                        "resource.workflow-protected-runtime-readiness-authorization-lease"
                    ),
                    scope_reference="/".join(
                        (*context.scope.canonical_value().values(), "runtime-readiness")
                    ),
                    decision_id=context.decision_id,
                    outcome="succeeded",
                    result_code=result_code,
                    idempotency_key=None,
                    target_metadata=(
                        ("authorization_lease_id", lease.authorization_lease_id),
                        ("protected_runtime_readiness_request_authority", "true"),
                        ("readiness_probe_authority", "false"),
                        ("network_access_authority", "false"),
                        ("connector_activity_authority", "false"),
                        ("execution_authority", "false"),
                        ("infrastructure_mutation_authority", "false"),
                    ),
                )
            )
        except Exception:
            return

    @classmethod
    def _raise_preflight_status(
        cls, status: WorkflowProtectedRuntimeReadinessAuthorizationPreflightStatus
    ) -> NoReturn:
        statuses = WorkflowProtectedRuntimeReadinessAuthorizationPreflightStatus
        cls._raise(
            {
                statuses.IDEMPOTENCY_CONFLICT: (
                    "workflow_protected_runtime_readiness_idempotency_conflict"
                ),
                statuses.EVIDENCE_CONFLICT: (
                    "workflow_protected_runtime_readiness_evidence_conflict"
                ),
                statuses.ALREADY_AUTHORIZED: (
                    "workflow_protected_runtime_readiness_already_authorized"
                ),
            }.get(
                status,
                "workflow_protected_runtime_readiness_repository_contract_violation",
            )
        )

    @classmethod
    def _raise_authorization_status(
        cls, status: WorkflowProtectedRuntimeReadinessAuthorizationLeaseStatus
    ) -> NoReturn:
        statuses = WorkflowProtectedRuntimeReadinessAuthorizationLeaseStatus
        cls._raise(
            {
                statuses.IDEMPOTENCY_CONFLICT: (
                    "workflow_protected_runtime_readiness_idempotency_conflict"
                ),
                statuses.EVIDENCE_CONFLICT: (
                    "workflow_protected_runtime_readiness_evidence_conflict"
                ),
                statuses.ALREADY_AUTHORIZED: (
                    "workflow_protected_runtime_readiness_already_authorized"
                ),
            }.get(
                status,
                "workflow_protected_runtime_readiness_repository_contract_violation",
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
            WorkflowProtectedRuntimeReadinessAuthorizationService._raise(
                "workflow_protected_runtime_readiness_consumer_identity_required"
            )

    @staticmethod
    def _identifier(value: str, name: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 240 or any(c.isspace() for c in normalized):
            WorkflowProtectedRuntimeReadinessAuthorizationService._raise(
                f"workflow_protected_runtime_readiness_{name}_invalid"
            )
        return normalized

    @classmethod
    def _digest(cls, value: str, name: str) -> str:
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            cls._raise(f"workflow_protected_runtime_readiness_{name}_invalid")
        return value

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            cls._raise("workflow_protected_runtime_readiness_idempotency_key_invalid")
        return normalized

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowProtectedRuntimeReadinessAuthorizationError(
            code,
            "The protected runtime-readiness authorization request was denied.",
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
    "WORKFLOW_PROTECTED_RUNTIME_READINESS_AUTHORIZATION_PRODUCER",
    "WorkflowProtectedRuntimeReadinessAuthorizationService",
]

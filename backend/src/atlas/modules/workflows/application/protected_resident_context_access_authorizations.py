from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.protected_resident_context_access_authorization_ports import (  # noqa: E501
    WorkflowProtectedResidentContextAccessAuthorizationError,
    WorkflowProtectedResidentContextAccessAuthorizationLeaseRequest,
    WorkflowProtectedResidentContextAccessAuthorizationLeaseStatus,
    WorkflowProtectedResidentContextAccessAuthorizationPreflightRequest,
    WorkflowProtectedResidentContextAccessAuthorizationPreflightStatus,
    WorkflowProtectedResidentContextAccessAuthorizationPresentation,
    WorkflowProtectedResidentContextAccessAuthorizationRepository,
    WorkflowProtectedResidentContextAccessAuthorizationSource,
    WorkflowProtectedResidentContextLifecycleAttestation,
    WorkflowProtectedResidentContextLifecycleAttestationRequest,
    WorkflowProtectedResidentContextLifecycleAttestor,
    WorkflowProtectedResidentContextLifecycleSignatureVerifier,
    WorkflowProtectedResidentContextOpeningReceiptSignatureVerifier,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedResidentContextAccessAuthorizationClaim,
    WorkflowProtectedResidentContextAccessAuthorizationLease,
    WorkflowProtectedResidentContextAccessAuthorizationLeaseState,
    WorkflowProtectedResidentContextAccessAuthorizationPolicy,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_resident_context_access_authorization_policy,
)

WORKFLOW_PROTECTED_RESIDENT_CONTEXT_ACCESS_AUTHORIZATION_PRODUCER = (
    "project-atlas-workflow-protected-resident-context-access-authorizer"
)

_OPERATIONAL_AUTHORITY_FIELDS = (
    "endpoint_resolution_authorized",
    "route_selection_authorized",
    "route_binding_authorized",
    "credential_selection_authorized",
    "credential_assignment_binding_authorized",
    "credential_access_authorized",
    "credential_brokerage_authorized",
    "credential_resolution_authorized",
    "protected_artifact_access_authorized",
    "credential_delivery_authorized",
    "network_access_authorized",
    "readiness_probe_authorized",
    "publication_authorized",
    "delivery_authorized",
    "dispatch_authorized",
    "execution_authorized",
    "infrastructure_mutation_authorized",
    "target_context_capsule_handoff_authorized",
    "target_context_capsule_opening_authorized",
)


class WorkflowProtectedResidentContextAccessAuthorizationService:
    """Issues a one-second authorization without exposing or using resident context."""

    def __init__(
        self,
        *,
        authorization_repository: WorkflowProtectedResidentContextAccessAuthorizationRepository,
        lifecycle_attestor: WorkflowProtectedResidentContextLifecycleAttestor,
        lifecycle_signature_verifier: (WorkflowProtectedResidentContextLifecycleSignatureVerifier),
        opening_receipt_signature_verifier: (
            WorkflowProtectedResidentContextOpeningReceiptSignatureVerifier
        ),
        audit_sink: AuditSink,
        policy: WorkflowProtectedResidentContextAccessAuthorizationPolicy | None = None,
    ) -> None:
        self._repository = authorization_repository
        self._lifecycle_attestor = lifecycle_attestor
        self._lifecycle_signature_verifier = lifecycle_signature_verifier
        self._opening_receipt_signature_verifier = opening_receipt_signature_verifier
        self._audit_sink = audit_sink
        self._policy = (
            policy or code_owned_workflow_protected_resident_context_access_authorization_policy()
        )

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def repository(self) -> WorkflowProtectedResidentContextAccessAuthorizationRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowProtectedResidentContextAccessAuthorizationPolicy:
        return self._policy

    async def authorize(
        self,
        *,
        opening_result_id: str,
        opening_result_digest: str,
        policy_id: str,
        policy_version: str,
        idempotency_key: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> WorkflowProtectedResidentContextAccessAuthorizationLease:
        self._require_workload(context)
        if not self._repository.durable:
            self._raise("workflow_protected_resident_context_access_durable_repository_required")
        opening_id = self._identifier(opening_result_id, "opening_result_id")
        result_digest = self._digest(opening_result_digest, "opening_result_digest")
        normalized_key = self._idempotency_key(idempotency_key)
        if policy_id != self._policy.policy_id or policy_version != self._policy.policy_version:
            self._raise("workflow_protected_resident_context_access_policy_conflict")
        idempotency_digest = canonical_digest(
            {
                "idempotency_key": normalized_key,
                "scope": context.scope.canonical_value(),
                "subject_id": context.subject_id,
            }
        )
        fingerprint = canonical_digest(
            {
                "opening_result_digest": result_digest,
                "opening_result_id": opening_id,
                "policy_digest": self._policy.canonical_digest,
                "scope": context.scope.canonical_value(),
                "subject_id": context.subject_id,
            }
        )
        preflight_request = WorkflowProtectedResidentContextAccessAuthorizationPreflightRequest(
            opening_id=opening_id,
            opening_result_digest=result_digest,
            scope=context.scope,
            consumer_subject_id=context.subject_id,
            consumer_audience=context.credential_audience,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.policy_version,
            policy_digest=self._policy.canonical_digest,
            idempotency_key=normalized_key,
            idempotency_digest=idempotency_digest,
            request_fingerprint=fingerprint,
        )
        try:
            preflight = await (
                self._repository.preflight_protected_resident_context_access_authorization(
                    preflight_request
                )
            )
        except WorkflowProtectedResidentContextAccessAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_resident_context_access_repository_unavailable")
        preflight_statuses = WorkflowProtectedResidentContextAccessAuthorizationPreflightStatus
        if preflight.status is preflight_statuses.REPLAY:
            if preflight.lease is None or preflight.evaluated_at is None:
                self._raise(
                    "workflow_protected_resident_context_access_repository_contract_violation"
                )
            self._validate_historical_lease(preflight.lease, scope=context.scope)
            await self._postcommit_audit(
                context,
                result_code="workflow_protected_resident_context_access_authorization_replayed",
                lease=preflight.lease,
            )
            return preflight.lease
        if preflight.status is not preflight_statuses.NONE:
            self._raise_preflight_status(preflight.status)
        if preflight.lease is not None or preflight.evaluated_at is None:
            self._raise("workflow_protected_resident_context_access_repository_contract_violation")
        if not self._lifecycle_attestor.available:
            self._raise("workflow_protected_resident_context_access_trusted_attestor_unavailable")
        try:
            source = await (
                self._repository.get_protected_resident_context_access_authorization_source(
                    opening_id=opening_id
                )
            )
        except WorkflowProtectedResidentContextAccessAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_resident_context_access_repository_unavailable")
        if source is None:
            self._raise("workflow_protected_resident_context_access_evidence_conflict")
        self._validate_source(source, expected_digest=result_digest, scope=context.scope)
        nonce_digest = canonical_digest({"nonce": uuid4().hex, "request_fingerprint": fingerprint})
        attestation_request = self._attestation_request(
            source,
            nonce_digest=nonce_digest,
            requested_at=preflight.evaluated_at,
        )
        try:
            attestation = await self._lifecycle_attestor.attest_resident_context_lifecycle(
                attestation_request
            )
        except WorkflowProtectedResidentContextAccessAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_resident_context_access_evidence_conflict")
        try:
            authoritative_now = await self._repository.get_authoritative_time()
        except Exception:
            self._raise("workflow_protected_resident_context_access_repository_unavailable")
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
        request = WorkflowProtectedResidentContextAccessAuthorizationLeaseRequest(
            source=source,
            lifecycle_attestation=attestation,
            expected_request_nonce_digest=nonce_digest,
            offline_signature_verifier=self._lifecycle_signature_verifier,
            offline_opening_receipt_signature_verifier=(self._opening_receipt_signature_verifier),
            expected_policy_digest=self._policy.canonical_digest,
            expected_validity_window_seconds=1,
            scope=context.scope,
            consumer_subject_id=context.subject_id,
            consumer_audience=context.credential_audience,
            requested_at=authoritative_now,
            candidate_claim=candidate_claim,
            candidate=candidate,
            idempotency_key=normalized_key,
            idempotency_digest=idempotency_digest,
            request_fingerprint=fingerprint,
        )
        try:
            authorization = await self._repository.authorize_protected_resident_context_access(
                request
            )
        except WorkflowProtectedResidentContextAccessAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_resident_context_access_repository_unavailable")
        statuses = WorkflowProtectedResidentContextAccessAuthorizationLeaseStatus
        if authorization.status in (statuses.AUTHORIZED, statuses.REPLAY):
            if authorization.lease is None or authorization.evaluated_at is None:
                self._raise(
                    "workflow_protected_resident_context_access_repository_contract_violation"
                )
            self._validate_lease(
                authorization.lease,
                scope=context.scope,
                evaluated_at=authorization.evaluated_at,
                source=source,
            )
            await self._postcommit_audit(
                context,
                result_code=(
                    "workflow_protected_resident_context_access_authorization_created"
                    if authorization.status is statuses.AUTHORIZED
                    else "workflow_protected_resident_context_access_authorization_replayed"
                ),
                lease=authorization.lease,
            )
            return authorization.lease
        self._raise_authorization_status(authorization.status)

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedResidentContextAccessAuthorizationPresentation, ...]:
        if not self._repository.durable:
            self._raise("workflow_protected_resident_context_access_durable_repository_required")
        if not 1 <= limit <= 256:
            self._raise("workflow_protected_resident_context_access_limit_invalid")
        try:
            presentations = await (
                self._repository.list_protected_resident_context_access_authorization_presentations(
                    scope=scope, limit=limit
                )
            )
        except WorkflowProtectedResidentContextAccessAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_resident_context_access_repository_unavailable")
        for presentation in presentations:
            self._validate_presentation(presentation, scope=scope)
        if (
            len({item.lease.authorization_lease_id for item in presentations}) != len(presentations)
            or len({item.evaluated_at for item in presentations}) > 1
        ):
            self._raise("workflow_protected_resident_context_access_repository_contract_violation")
        return presentations

    async def get_presentation(
        self, *, scope: WorkflowScope, authorization_lease_id: str
    ) -> WorkflowProtectedResidentContextAccessAuthorizationPresentation:
        if not self._repository.durable:
            self._raise("workflow_protected_resident_context_access_durable_repository_required")
        try:
            presentations = await (
                self._repository.list_protected_resident_context_access_authorization_presentations(
                    scope=scope,
                    authorization_lease_ids=(authorization_lease_id,),
                    limit=1,
                )
            )
        except WorkflowProtectedResidentContextAccessAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_resident_context_access_repository_unavailable")
        if len(presentations) != 1:
            self._raise("workflow_protected_resident_context_access_repository_contract_violation")
        presentation = presentations[0]
        self._validate_presentation(presentation, scope=scope)
        if presentation.lease.authorization_lease_id != authorization_lease_id:
            self._raise("workflow_protected_resident_context_access_repository_contract_violation")
        return presentation

    def _validate_presentation(
        self,
        presentation: WorkflowProtectedResidentContextAccessAuthorizationPresentation,
        *,
        scope: WorkflowScope,
    ) -> None:
        if presentation.evaluated_at.tzinfo is None:
            self._raise("workflow_protected_resident_context_access_repository_contract_violation")
        self._validate_historical_lease(presentation.lease, scope=scope)

    def _validate_source(
        self,
        source: WorkflowProtectedResidentContextAccessAuthorizationSource,
        *,
        expected_digest: str,
        scope: WorkflowScope,
    ) -> None:
        result = source.result
        attempt = source.attempt
        claim = source.consumption_claim
        lease = source.authorization_lease
        receipt = source.opening_receipt
        state = getattr(result.state, "value", result.state)
        if (
            result.canonical_digest != expected_digest
            or canonical_digest(result.digest_payload()) != expected_digest
            or state != self._policy.required_opening_result_state
            or result.scope != scope
            or result.failure_class is not None
            or result.opening_receipt_digest != source.opening_receipt_digest
            or result.attempt_id != attempt.attempt_id
            or result.attempt_digest != attempt.canonical_digest
            or result.consumption_claim_id != claim.claim_id
            or result.consumption_claim_digest != claim.canonical_digest
            or result.authorization_lease_id != lease.authorization_lease_id
            or result.authorization_lease_digest != lease.canonical_digest
            or result.protected_resident_context_id != source.protected_resident_context_id
            or result.protected_resident_context_digest != source.protected_resident_context_digest
            or result.protected_resident_context_created_at
            != source.protected_resident_context_created_at
            or result.protected_resident_context_usable_until
            != source.protected_resident_context_usable_until
            or result.completed_at != source.protected_resident_context_created_at
            or result.completed_at is None
            or result.completed_at >= result.opening_deadline
            or source.protected_resident_context_created_at
            >= source.protected_resident_context_usable_until
            or source.protected_resident_context_usable_until
            > source.protected_resident_context_created_at + timedelta(seconds=30)
            or result.protected_resident_context_is_bearer_capability
            or not result.capsule_opened_in_protected_boundary
            or not result.target_context_pair_verified
            or not result.outcome_known
            or not result.protected_source_closed
            or not result.source_capsule_zeroized
            or canonical_digest(attempt.digest_payload()) != attempt.canonical_digest
            or canonical_digest(claim.digest_payload()) != claim.canonical_digest
            or canonical_digest(lease.digest_payload()) != lease.canonical_digest
            or canonical_digest(receipt.digest_payload()) != receipt.canonical_digest
            or receipt.canonical_digest != source.opening_receipt_digest
            or receipt.opening_id != result.opening_id
            or receipt.attempt_id != attempt.attempt_id
            or receipt.consumption_claim_id != claim.claim_id
            or receipt.authorization_lease_id != lease.authorization_lease_id
            or receipt.protected_resident_context_id != source.protected_resident_context_id
            or receipt.protected_resident_context_digest != source.protected_resident_context_digest
            or receipt.protected_resident_context_created_at
            != source.protected_resident_context_created_at
            or receipt.protected_resident_context_usable_until
            != source.protected_resident_context_usable_until
            or receipt.signing_key_id != source.opening_receipt_signing_key_id
            or receipt.signature_algorithm != source.opening_receipt_signature_algorithm
            or receipt.integrity_signature != source.opening_receipt_integrity_signature
            or receipt.destination_boundary_id != source.destination_boundary_id
            or receipt.destination_deployment_id != source.destination_deployment_id
            or receipt.destination_generation != source.destination_generation
            or receipt.destination_fencing_token_digest != source.destination_fencing_token_digest
            or source.destination_boundary_id != self._policy.destination_boundary_id
            or source.destination_deployment_id != self._policy.destination_deployment_id
            or source.destination_generation != self._policy.destination_generation
            or source.destination_fencing_token_digest
            != self._policy.destination_fencing_token_digest
            or result.consumer_subject_id != source.consumer_subject_id
            or result.consumer_audience != source.consumer_audience
            or result.consumer_contract_id != source.consumer_contract_id
            or result.consumer_contract_version != source.consumer_contract_version
            or source.consumer_subject_id != self._policy.consumer_subject_id
            or source.consumer_audience != self._policy.consumer_audience
            or source.consumer_contract_id != self._policy.consumer_contract_id
            or source.consumer_contract_version != self._policy.consumer_contract_version
            or any(result.authority.canonical_value().values())
            or any(attempt.authority.canonical_value().values())
            or any(claim.authority.canonical_value().values())
            or not self._opening_receipt_signature_verifier.verify_opening_receipt(receipt)
        ):
            self._raise("workflow_protected_resident_context_access_evidence_conflict")

    def _attestation_request(
        self,
        source: WorkflowProtectedResidentContextAccessAuthorizationSource,
        *,
        nonce_digest: str,
        requested_at: datetime,
    ) -> WorkflowProtectedResidentContextLifecycleAttestationRequest:
        return WorkflowProtectedResidentContextLifecycleAttestationRequest(
            opening_id=source.result.opening_id,
            opening_result_digest=source.result.canonical_digest,
            opening_attempt_id=source.attempt.attempt_id,
            opening_attempt_digest=source.attempt.canonical_digest,
            opening_consumption_claim_id=source.consumption_claim.claim_id,
            opening_consumption_claim_digest=source.consumption_claim.canonical_digest,
            opening_authorization_lease_id=source.authorization_lease.authorization_lease_id,
            opening_authorization_lease_digest=source.authorization_lease.canonical_digest,
            opening_receipt_digest=source.opening_receipt_digest,
            opening_receipt_signing_key_id=source.opening_receipt_signing_key_id,
            protected_resident_context_id=source.protected_resident_context_id,
            protected_resident_context_digest=source.protected_resident_context_digest,
            protected_resident_context_created_at=source.protected_resident_context_created_at,
            protected_resident_context_usable_until=(
                source.protected_resident_context_usable_until
            ),
            destination_boundary_id=source.destination_boundary_id,
            destination_deployment_id=source.destination_deployment_id,
            destination_generation=source.destination_generation,
            destination_fencing_token_digest=source.destination_fencing_token_digest,
            scope=source.result.scope,
            consumer_subject_id=source.consumer_subject_id,
            consumer_audience=source.consumer_audience,
            consumer_contract_id=source.consumer_contract_id,
            consumer_contract_version=source.consumer_contract_version,
            purpose_id=self._policy.purpose_id,
            request_nonce_digest=nonce_digest,
            requested_at=requested_at,
        )

    def _validate_attestation(
        self,
        attestation: WorkflowProtectedResidentContextLifecycleAttestation,
        *,
        request: WorkflowProtectedResidentContextLifecycleAttestationRequest,
        evaluated_at: datetime,
    ) -> None:
        for name in (
            "opening_id",
            "opening_result_digest",
            "opening_attempt_id",
            "opening_attempt_digest",
            "opening_consumption_claim_id",
            "opening_consumption_claim_digest",
            "opening_authorization_lease_id",
            "opening_authorization_lease_digest",
            "opening_receipt_digest",
            "opening_receipt_signing_key_id",
            "protected_resident_context_id",
            "protected_resident_context_digest",
            "protected_resident_context_created_at",
            "protected_resident_context_usable_until",
            "destination_boundary_id",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "scope",
            "consumer_subject_id",
            "consumer_audience",
            "consumer_contract_id",
            "consumer_contract_version",
            "purpose_id",
            "request_nonce_digest",
        ):
            if getattr(attestation, name) != getattr(request, name):
                self._raise("workflow_protected_resident_context_access_evidence_conflict")
        unsafe_metadata = (
            attestation.resident_context_is_bearer_capability,
            attestation.resident_context_handle_outstanding,
            attestation.raw_context_included,
            attestation.endpoint_included,
            attestation.credential_included,
            attestation.secret_included,
            attestation.bearer_token_included,
            attestation.locator_included,
            attestation.provider_payload_included,
            attestation.runtime_handle_creation_authorized,
            attestation.network_activity_authorized,
            attestation.execution_authorized,
            attestation.infrastructure_mutation_authorized,
        )
        if (
            attestation.attestor_id != self._policy.required_attestor_id
            or attestation.attestor_version != self._policy.required_attestor_version
            or attestation.signing_key_id != self._policy.verification_signing_key_id
            or attestation.observed_at < request.requested_at
            or attestation.observed_at > evaluated_at
            or attestation.valid_until <= evaluated_at + timedelta(seconds=1)
            or attestation.valid_until > attestation.protected_resident_context_usable_until
            or not attestation.resident_context_present
            or not attestation.resident_context_unexpired
            or not attestation.resident_context_unrevoked
            or not attestation.resident_context_undestroyed
            or not attestation.resident_context_unconsumed
            or any(unsafe_metadata)
            or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
            or not self._lifecycle_signature_verifier.verify_lifecycle_attestation(attestation)
        ):
            self._raise("workflow_protected_resident_context_access_evidence_conflict")

    def _build_candidates(
        self,
        *,
        source: WorkflowProtectedResidentContextAccessAuthorizationSource,
        attestation: WorkflowProtectedResidentContextLifecycleAttestation,
        issued_at: datetime,
        idempotency_digest: str,
        request_fingerprint: str,
    ) -> tuple[
        WorkflowProtectedResidentContextAccessAuthorizationClaim,
        WorkflowProtectedResidentContextAccessAuthorizationLease,
    ]:
        effective_until = min(
            source.protected_resident_context_usable_until,
            attestation.valid_until,
        )
        valid_until = min(
            issued_at + timedelta(seconds=self._policy.maximum_lifetime_seconds),
            effective_until,
        )
        if issued_at >= valid_until:
            self._raise("workflow_protected_resident_context_access_evidence_conflict")
        identity_digest = canonical_digest(
            {
                "idempotency_digest": idempotency_digest,
                "opening_id": source.result.opening_id,
                "policy_digest": self._policy.canonical_digest,
            }
        )
        lease_id = f"workflow-protected-resident-context-access-lease.{identity_digest[:24]}"
        claim_id = f"workflow-protected-resident-context-access-claim.{identity_digest[:24]}"
        audit_payload = {
            "schema_id": "audit.workflow-protected-resident-context-access-authorization",
            "schema_version": "1.0",
            "authorization_lease_id": lease_id,
            "opening_id": source.result.opening_id,
            "request_fingerprint": request_fingerprint,
            "scope": source.result.scope.canonical_value(),
            "consumer_subject_id": source.consumer_subject_id,
            "protected_resident_context_access_authority_granted": True,
            "operational_authority_granted": False,
        }
        source_values = self._candidate_source_values(source)
        claim_values: dict[str, object] = {
            "claim_id": claim_id,
            **source_values,
            "request_fingerprint": request_fingerprint,
            "idempotency_digest": idempotency_digest,
            "authorization_audit_digest": canonical_digest(audit_payload),
            "claimed_at": issued_at,
            **{name: False for name in _OPERATIONAL_AUTHORITY_FIELDS},
            "protected_resident_context_access_authority_granted": False,
        }
        claim = WorkflowProtectedResidentContextAccessAuthorizationClaim(
            **cast(Any, claim_values),
            canonical_digest=canonical_digest(self._payload(claim_values)),
        )
        lease_values: dict[str, object] = {
            "authorization_lease_id": lease_id,
            "claim_id": claim.claim_id,
            "claim_digest": claim.canonical_digest,
            **source_values,
            "lifecycle_attestation_id": attestation.attestation_id,
            "lifecycle_attestation_digest": attestation.canonical_digest,
            "lifecycle_attestation_valid_until": attestation.valid_until,
            "issued_at": issued_at,
            "valid_until": valid_until,
            "effective_until": effective_until,
            "single_use": True,
            "renewable": False,
            "transferable": False,
            "lease_is_bearer_capability": False,
            "state": (
                WorkflowProtectedResidentContextAccessAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
            ),
            **{name: False for name in _OPERATIONAL_AUTHORITY_FIELDS},
            "protected_resident_context_access_authority_granted": True,
        }
        lease = WorkflowProtectedResidentContextAccessAuthorizationLease(
            **cast(Any, lease_values),
            canonical_digest=canonical_digest(self._payload(lease_values)),
        )
        return claim, lease

    def _candidate_source_values(
        self, source: WorkflowProtectedResidentContextAccessAuthorizationSource
    ) -> dict[str, object]:
        result = source.result
        assert result.completed_at is not None
        return {
            "opening_id": result.opening_id,
            "opening_result_digest": result.canonical_digest,
            "opening_attempt_id": source.attempt.attempt_id,
            "opening_attempt_digest": source.attempt.canonical_digest,
            "opening_consumption_claim_id": source.consumption_claim.claim_id,
            "opening_consumption_claim_digest": source.consumption_claim.canonical_digest,
            "opening_authorization_lease_id": source.authorization_lease.authorization_lease_id,
            "opening_authorization_lease_digest": source.authorization_lease.canonical_digest,
            "opening_receipt_digest": source.opening_receipt_digest,
            "opening_result_state": result.state,
            "opening_completed_at": result.completed_at,
            "opening_deadline": result.opening_deadline,
            "protected_resident_context_id": source.protected_resident_context_id,
            "protected_resident_context_digest": source.protected_resident_context_digest,
            "protected_resident_context_created_at": (source.protected_resident_context_created_at),
            "protected_resident_context_usable_until": (
                source.protected_resident_context_usable_until
            ),
            "protected_resident_context_is_bearer_capability": False,
            "capsule_opened_in_protected_boundary": True,
            "target_context_pair_verified": True,
            "opening_outcome_known": True,
            "protected_source_closed": True,
            "source_capsule_zeroized": True,
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

    def _validate_lease(
        self,
        lease: WorkflowProtectedResidentContextAccessAuthorizationLease,
        *,
        scope: WorkflowScope,
        evaluated_at: datetime,
        source: WorkflowProtectedResidentContextAccessAuthorizationSource | None = None,
    ) -> None:
        self._validate_historical_lease(lease, scope=scope)
        if getattr(lease.effective_state(evaluated_at=evaluated_at), "value", None) != "active":
            self._raise("workflow_protected_resident_context_access_repository_contract_violation")
        if source is not None and (
            lease.opening_id != source.result.opening_id
            or lease.opening_result_digest != source.result.canonical_digest
            or lease.protected_resident_context_id != source.protected_resident_context_id
            or lease.protected_resident_context_digest != source.protected_resident_context_digest
        ):
            self._raise("workflow_protected_resident_context_access_repository_contract_violation")

    def _validate_historical_lease(
        self,
        lease: WorkflowProtectedResidentContextAccessAuthorizationLease,
        *,
        scope: WorkflowScope,
    ) -> None:
        if (
            lease.scope != scope
            or lease.policy_digest != self._policy.canonical_digest
            or canonical_digest(lease.digest_payload()) != lease.canonical_digest
            or lease.valid_until - lease.issued_at > timedelta(seconds=1)
            or lease.valid_until > lease.effective_until
            or lease.effective_until > lease.protected_resident_context_usable_until
            or lease.effective_until > lease.lifecycle_attestation_valid_until
            or lease.single_use is not True
            or lease.renewable is not False
            or lease.transferable is not False
            or lease.lease_is_bearer_capability is not False
            or lease.protected_resident_context_access_authority_granted is not True
            or any(getattr(lease, name) is not False for name in _OPERATIONAL_AUTHORITY_FIELDS)
        ):
            self._raise("workflow_protected_resident_context_access_repository_contract_violation")

    async def _postcommit_audit(
        self,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
        *,
        result_code: str,
        lease: WorkflowProtectedResidentContextAccessAuthorizationLease,
    ) -> None:
        try:
            await self._audit_sink.record(
                AuditRecord(
                    event_id=f"evt_{uuid4().hex}",
                    event_type=(
                        "atlas.workflow.protected-resident-context-access-authorization.commit"
                    ),
                    schema_version="1.0",
                    producer=WORKFLOW_PROTECTED_RESIDENT_CONTEXT_ACCESS_AUTHORIZATION_PRODUCER,
                    producer_version=__version__,
                    occurred_at=context.requested_at,
                    correlation_id=context.correlation_id,
                    subject_id=context.subject_id,
                    actor_type=context.actor_type,
                    authentication_method=context.authentication_method,
                    assurance_level="workload",
                    permission_id=(
                        "workflow.protected-resident-context-access-authorizations.create"
                    ),
                    resource_type=(
                        "resource.workflow-protected-resident-context-access-authorization-lease"
                    ),
                    scope_reference="/".join(
                        (*context.scope.canonical_value().values(), "resident-context-access")
                    ),
                    decision_id=context.decision_id,
                    outcome="succeeded",
                    result_code=result_code,
                    idempotency_key=None,
                    target_metadata=(
                        ("authorization_lease_id", lease.authorization_lease_id),
                        ("protected_resident_context_access_authority", "true"),
                        ("runtime_handle_creation_authority", "false"),
                        ("network_access_authority", "false"),
                        ("execution_authority", "false"),
                        ("infrastructure_mutation_authority", "false"),
                    ),
                )
            )
        except Exception:
            return

    @classmethod
    def _raise_preflight_status(
        cls, status: WorkflowProtectedResidentContextAccessAuthorizationPreflightStatus
    ) -> NoReturn:
        statuses = WorkflowProtectedResidentContextAccessAuthorizationPreflightStatus
        cls._raise(
            {
                statuses.IDEMPOTENCY_CONFLICT: (
                    "workflow_protected_resident_context_access_idempotency_conflict"
                ),
                statuses.EVIDENCE_CONFLICT: (
                    "workflow_protected_resident_context_access_evidence_conflict"
                ),
                statuses.ALREADY_AUTHORIZED: (
                    "workflow_protected_resident_context_access_already_authorized"
                ),
            }.get(
                status,
                "workflow_protected_resident_context_access_repository_contract_violation",
            )
        )

    @classmethod
    def _raise_authorization_status(
        cls, status: WorkflowProtectedResidentContextAccessAuthorizationLeaseStatus
    ) -> NoReturn:
        statuses = WorkflowProtectedResidentContextAccessAuthorizationLeaseStatus
        cls._raise(
            {
                statuses.IDEMPOTENCY_CONFLICT: (
                    "workflow_protected_resident_context_access_idempotency_conflict"
                ),
                statuses.EVIDENCE_CONFLICT: (
                    "workflow_protected_resident_context_access_evidence_conflict"
                ),
                statuses.ALREADY_AUTHORIZED: (
                    "workflow_protected_resident_context_access_already_authorized"
                ),
            }.get(
                status,
                "workflow_protected_resident_context_access_repository_contract_violation",
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
            WorkflowProtectedResidentContextAccessAuthorizationService._raise(
                "workflow_protected_resident_context_access_consumer_identity_required"
            )

    @staticmethod
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

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowProtectedResidentContextAccessAuthorizationError(
            code, "The protected resident-context access authorization request was denied."
        )

    @classmethod
    def _identifier(cls, value: str, name: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 240 or any(c.isspace() for c in normalized):
            cls._raise(f"workflow_protected_resident_context_access_{name}_invalid")
        return normalized

    @classmethod
    def _digest(cls, value: str, name: str) -> str:
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            cls._raise(f"workflow_protected_resident_context_access_{name}_invalid")
        return value

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            cls._raise("workflow_protected_resident_context_access_idempotency_key_invalid")
        return normalized


__all__ = [
    "WORKFLOW_PROTECTED_RESIDENT_CONTEXT_ACCESS_AUTHORIZATION_PRODUCER",
    "WorkflowProtectedResidentContextAccessAuthorizationService",
]

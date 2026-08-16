from __future__ import annotations

from datetime import datetime, timedelta
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
from atlas.modules.workflows.application.target_context_capsule_opening_authorization_lease_ports import (  # noqa: E501
    WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestationRequest,
    WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestor,
    WorkflowProtectedTargetContextCapsuleDestinationCustodySignatureVerifier,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseError,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseRepository,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseRequest,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseStatus,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationSource,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestation,
    WorkflowProtectedTransportTargetContextCapsuleHandoffResultState,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseEffectiveState,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseState,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationPolicy,
    WorkflowProtectedTransportTargetContextCapsuleOpeningLeaseAuthority,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy,
)

WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_OPENING_AUTHORIZATION_LEASE_PRODUCER = (
    "project-atlas-workflow-protected-target-context-capsule-opening-authorizer"
)


class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseService:
    """Authorizes a future opening request without retrieving or opening a capsule."""

    def __init__(
        self,
        *,
        authorization_repository: (
            WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseRepository
        ),
        custody_attestor: WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestor,
        custody_signature_verifier: (
            WorkflowProtectedTargetContextCapsuleDestinationCustodySignatureVerifier
        ),
        audit_sink: AuditSink,
        policy: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationPolicy
        | None = None,
    ) -> None:
        self._repository = authorization_repository
        self._custody_attestor = custody_attestor
        self._custody_signature_verifier = custody_signature_verifier
        self._audit_sink = audit_sink
        self._policy = (
            policy
            or code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy()  # noqa: E501
        )

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def repository(
        self,
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationPolicy:
        return self._policy

    async def authorize(
        self,
        *,
        handoff_result_id: str,
        handoff_result_digest: str,
        policy_id: str,
        policy_version: str,
        idempotency_key: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease:
        self._require_workload(context)
        if not self._repository.durable:
            self._raise("workflow_target_context_capsule_opening_durable_repository_required")
        if not self._custody_attestor.available:
            self._raise("workflow_target_context_capsule_opening_trusted_attestor_unavailable")
        handoff_id = self._identifier(handoff_result_id, "handoff_result_id")
        handoff_digest = self._digest(handoff_result_digest, "handoff_result_digest")
        normalized_key = self._idempotency_key(idempotency_key)
        if policy_id != self._policy.policy_id or policy_version != self._policy.policy_version:
            self._raise("workflow_target_context_capsule_opening_policy_conflict")
        source = await self._repository.get_target_context_capsule_opening_authorization_source(
            handoff_id=handoff_id
        )
        if source is None:
            self._raise("workflow_target_context_capsule_opening_evidence_conflict")
        self._validate_source(source, expected_digest=handoff_digest, scope=context.scope)
        fingerprint = canonical_digest(
            {
                "handoff_result_digest": handoff_digest,
                "handoff_result_id": handoff_id,
                "policy_digest": self._policy.canonical_digest,
                "scope": context.scope.canonical_value(),
                "subject_id": context.subject_id,
            }
        )
        nonce_digest = canonical_digest({"nonce": uuid4().hex, "request_fingerprint": fingerprint})
        await self._audit(
            context,
            event_kind="intent",
            outcome="requested",
            result_code="workflow_target_context_capsule_opening_authorization_requested",
            idempotency_key=normalized_key,
            handoff_id=handoff_id,
        )
        request = self._attestation_request(source, nonce_digest=nonce_digest, context=context)
        try:
            attestation = await self._custody_attestor.attest_destination_custody(request)
            authoritative_now = await self._repository.get_authoritative_time()
            self._validate_attestation(attestation, request=request, evaluated_at=authoritative_now)
            if (
                self._custody_signature_verifier.verify_destination_custody_attestation(attestation)
                is not True
            ):
                raise ValueError("custody signature invalid")
        except WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseError:
            raise
        except Exception:
            self._raise("workflow_target_context_capsule_opening_evidence_conflict")
        candidate = self._build_lease(
            source=source, attestation=attestation, issued_at=authoritative_now
        )

        async def required_precommit_audit() -> None:
            await self._audit(
                context,
                event_kind="persistence-readiness",
                outcome="succeeded",
                result_code="workflow_target_context_capsule_opening_persistence_audit_ready",
                idempotency_key=normalized_key,
                handoff_id=handoff_id,
                lease=candidate,
            )

        try:
            result = await self._repository.authorize_target_context_capsule_opening(
                WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseRequest(
                    source=source,
                    custody_attestation=attestation,
                    expected_request_nonce_digest=nonce_digest,
                    offline_signature_verifier=self._custody_signature_verifier,
                    expected_policy_digest=self._policy.canonical_digest,
                    expected_validity_window_seconds=1,
                    scope=context.scope,
                    consumer_subject_id=self._policy.consumer_subject_id,
                    consumer_audience=self._policy.consumer_audience,
                    requested_at=authoritative_now,
                    candidate=candidate,
                    idempotency_key=normalized_key,
                    request_fingerprint=fingerprint,
                    required_precommit_audit=required_precommit_audit,
                )
            )
        except Exception:
            self._raise("workflow_target_context_capsule_opening_repository_unavailable")
        statuses = WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseStatus
        if result.status in (statuses.AUTHORIZED, statuses.REPLAY):
            if result.lease is None or result.evaluated_at is None:
                self._raise("workflow_target_context_capsule_opening_repository_contract_violation")
            self._validate_lease(result.lease, source=source, evaluated_at=result.evaluated_at)
            await self._audit(
                context,
                event_kind="completion" if result.status is statuses.AUTHORIZED else "replay",
                outcome="succeeded",
                result_code=(
                    "workflow_target_context_capsule_opening_authorization_lease_created"
                    if result.status is statuses.AUTHORIZED
                    else "workflow_target_context_capsule_opening_authorization_lease_replayed"
                ),
                idempotency_key=normalized_key,
                handoff_id=handoff_id,
                lease=result.lease,
            )
            return result.lease
        self._raise(
            {
                statuses.IDEMPOTENCY_CONFLICT: (
                    "workflow_target_context_capsule_opening_idempotency_conflict"
                ),
                statuses.EVIDENCE_CONFLICT: (
                    "workflow_target_context_capsule_opening_evidence_conflict"
                ),
                statuses.ALREADY_AUTHORIZED: (
                    "workflow_target_context_capsule_opening_already_authorized"
                ),
                statuses.PRECOMMIT_AUDIT_FAILED: (
                    "workflow_target_context_capsule_opening_precommit_audit_failed"
                ),
            }.get(
                result.status,
                "workflow_target_context_capsule_opening_repository_contract_violation",
            )
        )

    async def list_leases(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease, ...]:
        if not self._repository.durable:
            self._raise("workflow_target_context_capsule_opening_durable_repository_required")
        if not 1 <= limit <= 256:
            self._raise("workflow_target_context_capsule_opening_limit_invalid")
        leases = await self._repository.list_target_context_capsule_opening_authorization_leases(
            scope=scope, limit=limit
        )
        for lease in leases:
            self._validate_historical_lease(lease, scope=scope)
        return leases

    def _validate_source(
        self,
        source: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationSource,
        *,
        expected_digest: str,
        scope: WorkflowScope,
    ) -> None:
        result = source.result
        attempt = source.attempt
        claim = source.consumption_claim
        upstream = source.upstream_authorization_lease
        binding = source.consumer_binding
        policy = self._policy
        if (
            result.canonical_digest != expected_digest
            or canonical_digest(result.digest_payload()) != expected_digest
            or result.state
            is not (
                WorkflowProtectedTransportTargetContextCapsuleHandoffResultState.HANDED_OFF_SEALED
            )
            or result.scope != scope
            or result.failure_class is not None
            or result.consumer_receipt_id is None
            or result.consumer_receipt_is_bearer_capability
            or not result.sealed_capsule_handed_off
            or result.usable_until is None
            or result.attempt_id != attempt.attempt_id
            or result.attempt_digest != attempt.canonical_digest
            or result.consumption_claim_id != claim.claim_id
            or result.consumption_claim_digest != claim.canonical_digest
            or result.authorization_lease_id != upstream.authorization_lease_id
            or result.authorization_lease_digest != upstream.canonical_digest
            or result.consumer_binding_id != binding.binding_id
            or result.consumer_binding_digest != binding.canonical_digest
            or attempt.sealed_capsule_id != binding.sealed_capsule_id
            or attempt.sealed_capsule_digest != binding.sealed_capsule_digest
            or attempt.destination_boundary_id != policy.destination_boundary_id
            or attempt.destination_deployment_id != policy.destination_deployment_id
            or attempt.destination_generation != policy.destination_generation
            or attempt.destination_fencing_token_digest != policy.destination_fencing_token_digest
            or attempt.custody_contract_id != policy.custody_contract_id
            or attempt.custody_contract_version != policy.custody_contract_version
            or attempt.approved_adapter_id != policy.approved_adapter_id
            or attempt.approved_adapter_version != policy.approved_adapter_version
            or attempt.verification_signing_key_id != policy.verification_signing_key_id
            or attempt.trusted_profile_digest != policy.trusted_profile_digest
            or any(result.authority.canonical_value().values())
            or any(attempt.authority.canonical_value().values())
            or any(claim.authority.canonical_value().values())
        ):
            self._raise("workflow_target_context_capsule_opening_evidence_conflict")

    def _attestation_request(
        self,
        source: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationSource,
        *,
        nonce_digest: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestationRequest:
        result, attempt = source.result, source.attempt
        assert result.consumer_receipt_id is not None
        return WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestationRequest(
            handoff_id=result.handoff_id,
            handoff_result_digest=result.canonical_digest,
            attempt_id=attempt.attempt_id,
            attempt_digest=attempt.canonical_digest,
            consumption_claim_id=source.consumption_claim.claim_id,
            consumption_claim_digest=source.consumption_claim.canonical_digest,
            consumer_binding_id=source.consumer_binding.binding_id,
            consumer_binding_digest=source.consumer_binding.canonical_digest,
            sealed_capsule_id=attempt.sealed_capsule_id,
            sealed_capsule_digest=attempt.sealed_capsule_digest,
            consumer_receipt_id=result.consumer_receipt_id,
            receipt_digest=result.receipt_digest,
            destination_boundary_id=attempt.destination_boundary_id,
            destination_deployment_id=attempt.destination_deployment_id,
            destination_generation=attempt.destination_generation,
            destination_fencing_token_digest=attempt.destination_fencing_token_digest,
            custody_contract_id=attempt.custody_contract_id,
            custody_contract_version=attempt.custody_contract_version,
            approved_adapter_id=attempt.approved_adapter_id,
            approved_adapter_version=attempt.approved_adapter_version,
            verification_signing_key_id=attempt.verification_signing_key_id,
            trusted_profile_digest=attempt.trusted_profile_digest,
            scope=result.scope,
            consumer_subject_id=context.subject_id,
            request_nonce_digest=nonce_digest,
            requested_at=context.requested_at,
        )

    def _validate_attestation(
        self,
        attestation: WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestation,
        *,
        request: WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestationRequest,
        evaluated_at: datetime,
    ) -> None:
        policy = self._policy
        for name in (
            "handoff_id",
            "handoff_result_digest",
            "attempt_id",
            "attempt_digest",
            "consumption_claim_id",
            "consumption_claim_digest",
            "consumer_binding_id",
            "consumer_binding_digest",
            "sealed_capsule_id",
            "sealed_capsule_digest",
            "consumer_receipt_id",
            "receipt_digest",
            "destination_boundary_id",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "custody_contract_id",
            "custody_contract_version",
            "approved_adapter_id",
            "approved_adapter_version",
            "verification_signing_key_id",
            "trusted_profile_digest",
            "request_nonce_digest",
        ):
            if getattr(attestation, name) != getattr(request, name):
                self._raise("workflow_target_context_capsule_opening_evidence_conflict")
        if (
            attestation.attestor_id != policy.required_attestor_id
            or attestation.attestor_version != policy.required_attestor_version
            or attestation.observed_at < request.requested_at
            or attestation.observed_at > evaluated_at
            or attestation.valid_until <= evaluated_at + timedelta(seconds=1)
            or not attestation.handed_off_sealed
            or not attestation.destination_custody_confirmed
            or not attestation.custody_finality_confirmed
            or not attestation.capsule_remains_sealed
            or attestation.revoked
            or attestation.destroyed
            or canonical_digest(attestation.digest_payload()) != attestation.canonical_digest
        ):
            self._raise("workflow_target_context_capsule_opening_evidence_conflict")

    def _build_lease(
        self,
        *,
        source: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationSource,
        attestation: WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestation,
        issued_at: datetime,
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease:
        result, attempt = source.result, source.attempt
        assert result.consumer_receipt_id is not None and result.usable_until is not None
        values: dict[str, object] = {
            "authorization_lease_id": "workflow-target-context-capsule-opening-authorization-lease."
            + sha256(result.handoff_id.encode()).hexdigest()[:24],
            "handoff_id": result.handoff_id,
            "handoff_result_digest": result.canonical_digest,
            "attempt_id": attempt.attempt_id,
            "attempt_digest": attempt.canonical_digest,
            "consumption_claim_id": source.consumption_claim.claim_id,
            "consumption_claim_digest": source.consumption_claim.canonical_digest,
            "upstream_authorization_lease_id": (
                source.upstream_authorization_lease.authorization_lease_id
            ),
            "upstream_authorization_lease_digest": (
                source.upstream_authorization_lease.canonical_digest
            ),
            "consumer_binding_id": source.consumer_binding.binding_id,
            "consumer_binding_digest": source.consumer_binding.canonical_digest,
            "sealed_capsule_id": attempt.sealed_capsule_id,
            "sealed_capsule_digest": attempt.sealed_capsule_digest,
            "consumer_receipt_id": result.consumer_receipt_id,
            "receipt_digest": result.receipt_digest,
            "destination_boundary_id": attempt.destination_boundary_id,
            "destination_deployment_id": attempt.destination_deployment_id,
            "destination_generation": attempt.destination_generation,
            "destination_fencing_token_digest": attempt.destination_fencing_token_digest,
            "custody_contract_id": attempt.custody_contract_id,
            "custody_contract_version": attempt.custody_contract_version,
            "approved_adapter_id": attempt.approved_adapter_id,
            "approved_adapter_version": attempt.approved_adapter_version,
            "verification_signing_key_id": attempt.verification_signing_key_id,
            "trusted_profile_digest": attempt.trusted_profile_digest,
            "custody_attestation_id": attestation.attestation_id,
            "custody_attestation_digest": attestation.canonical_digest,
            "custody_attestation_valid_until": attestation.valid_until,
            "scope": result.scope,
            "consumer_subject_id": self._policy.consumer_subject_id,
            "consumer_audience": self._policy.consumer_audience,
            "consumer_contract_id": self._policy.consumer_contract_id,
            "consumer_contract_version": self._policy.consumer_contract_version,
            "purpose_id": self._policy.purpose_id,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "issued_at": issued_at,
            "valid_until": issued_at + timedelta(seconds=1),
            "effective_until": min(result.usable_until, attestation.valid_until),
            "single_use": True,
            "renewable": False,
            "transferable": False,
            "lease_is_bearer_capability": False,
            "state": (
                WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
            ),
            "authority": WorkflowProtectedTransportTargetContextCapsuleOpeningLeaseAuthority(),
        }
        return WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease(
            **cast(Any, values),
            canonical_digest=canonical_digest(
                {
                    name: value.isoformat()
                    if isinstance(value, datetime)
                    else value.value
                    if hasattr(value, "value")
                    else value.canonical_value()
                    if hasattr(value, "canonical_value")
                    else value
                    for name, value in values.items()
                }
            ),
        )

    def _validate_lease(
        self,
        lease: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease,
        *,
        source: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationSource,
        evaluated_at: datetime,
    ) -> None:
        self._validate_historical_lease(lease, scope=source.result.scope)
        if (
            lease.handoff_id != source.result.handoff_id
            or lease.handoff_result_digest != source.result.canonical_digest
            or lease.effective_state(evaluated_at=evaluated_at)
            is not (
                WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseEffectiveState.ACTIVE
            )
        ):
            self._raise("workflow_target_context_capsule_opening_repository_contract_violation")

    def _validate_historical_lease(
        self,
        lease: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease,
        *,
        scope: WorkflowScope,
    ) -> None:
        authority = lease.authority.canonical_value()
        if (
            lease.scope != scope
            or lease.policy_digest != self._policy.canonical_digest
            or canonical_digest(lease.digest_payload()) != lease.canonical_digest
            or lease.valid_until - lease.issued_at != timedelta(seconds=1)
            or authority.get("target_context_capsule_opening_authorized") is not True
            or any(
                value is not False
                for name, value in authority.items()
                if name != "target_context_capsule_opening_authorized"
            )
        ):
            self._raise("workflow_target_context_capsule_opening_repository_contract_violation")

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
            WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseService._raise(
                "workflow_target_context_capsule_opening_consumer_identity_required"
            )

    async def _audit(
        self,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
        *,
        event_kind: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        handoff_id: str,
        lease: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease
        | None = None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=f"atlas.workflow.protected-target-context-capsule-opening-authorization.{event_kind}",
                schema_version="1.0",
                producer=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_OPENING_AUTHORIZATION_LEASE_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.protected-target-context-capsule-opening-authorization-leases.create",
                resource_type="resource.workflow-protected-target-context-capsule-opening-authorization-lease",
                scope_reference="/".join(
                    (
                        *context.scope.canonical_value().values(),
                        "capsule-opening-authorization-lease",
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    ("handoff_id", handoff_id),
                    (
                        "authorization_lease_id",
                        "none" if lease is None else lease.authorization_lease_id,
                    ),
                    ("target_context_capsule_opening_authority", "true" if lease else "false"),
                    ("target_context_capsule_handoff_authority", "false"),
                    ("protected_artifact_access_authority", "false"),
                    ("network_access_authority", "false"),
                    ("execution_authority", "false"),
                    ("infrastructure_mutation_authority", "false"),
                ),
            )
        )

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseError(
            code, "The target context capsule opening authorization request was denied."
        )

    @classmethod
    def _identifier(cls, value: str, name: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 240 or any(c.isspace() for c in normalized):
            cls._raise(f"workflow_target_context_capsule_opening_{name}_invalid")
        return normalized

    @classmethod
    def _digest(cls, value: str, name: str) -> str:
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            cls._raise(f"workflow_target_context_capsule_opening_{name}_invalid")
        return value

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            cls._raise("workflow_target_context_capsule_opening_idempotency_key_invalid")
        return normalized


__all__ = [
    "WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_OPENING_AUTHORIZATION_LEASE_PRODUCER",
    "WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseService",
]

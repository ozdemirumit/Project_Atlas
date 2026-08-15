from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.target_context_access_authorization_lease_ports import (
    WorkflowProtectedArtifactStatusAttestationRequest,
    WorkflowProtectedArtifactStatusSignatureVerifier,
    WorkflowProtectedCredentialStatusAttestor,
    WorkflowProtectedEndpointStatusAttestor,
    WorkflowTargetContextAccessAuthorizationLeaseError,
    WorkflowTargetContextAccessAuthorizationLeaseRepository,
    WorkflowTargetContextAccessAuthorizationLeaseRequest,
    WorkflowTargetContextAccessAuthorizationLeaseStatus,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseAuthority,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseEffectiveState,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseState,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationPolicy,
    WorkflowEventPhysicalTransportTargetContextBinding,
    WorkflowEventPhysicalTransportTargetContextBindingState,
    WorkflowProtectedArtifactKind,
    WorkflowProtectedArtifactStatusAttestation,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_target_context_access_authorization_policy,
)

WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE = (
    "audience.workflow-protected-transport-context-accessor"
)
WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_SUBJECT = (
    "service.workflow-protected-transport-context-accessor"
)
WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESS_AUTHORIZATION_LEASE_PRODUCER = (
    "project-atlas-workflow-protected-transport-context-access-authorizer"
)


@dataclass(frozen=True, slots=True)
class WorkflowPhysicalTransportTargetContextAccessorContext:
    subject_id: str
    actor_type: str
    authentication_method: str
    credential_audience: str
    scope: WorkflowScope
    correlation_id: str
    decision_id: str
    requested_at: datetime

    def __post_init__(self) -> None:
        identifiers = (
            self.subject_id,
            self.actor_type,
            self.authentication_method,
            self.credential_audience,
            self.correlation_id,
            self.decision_id,
        )
        if any(not value or value != value.strip() or len(value) > 240 for value in identifiers):
            raise ValueError("target context access context contains invalid evidence")
        if self.requested_at.tzinfo is None:
            raise ValueError("target context access requested_at must be timezone-aware")


class WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseService:
    """Authorizes bounded access without opening endpoint or credential artifacts."""

    def __init__(
        self,
        *,
        authorization_repository: WorkflowTargetContextAccessAuthorizationLeaseRepository,
        endpoint_status_attestor: WorkflowProtectedEndpointStatusAttestor,
        credential_status_attestor: WorkflowProtectedCredentialStatusAttestor,
        status_signature_verifier: WorkflowProtectedArtifactStatusSignatureVerifier,
        audit_sink: AuditSink,
        policy: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationPolicy | None = None,
    ) -> None:
        self._repository = authorization_repository
        self._endpoint_status_attestor = endpoint_status_attestor
        self._credential_status_attestor = credential_status_attestor
        self._status_signature_verifier = status_signature_verifier
        self._audit_sink = audit_sink
        self._policy = policy or (
            code_owned_workflow_event_physical_transport_target_context_access_authorization_policy()
        )

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def repository(self) -> WorkflowTargetContextAccessAuthorizationLeaseRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowEventPhysicalTransportTargetContextAccessAuthorizationPolicy:
        return self._policy

    async def authorize(
        self,
        *,
        target_context_binding_id: str,
        target_context_binding_digest: str,
        policy_id: str,
        policy_version: str,
        idempotency_key: str,
        context: WorkflowPhysicalTransportTargetContextAccessorContext,
    ) -> WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease:
        await self._require_accessor_workload(context)
        if not self._repository.durable:
            await self._deny(
                context,
                result_code="workflow_target_context_access_durable_repository_required",
            )
        try:
            binding_id = self._identifier(target_context_binding_id, "binding_id")
            binding_digest = self._digest(target_context_binding_digest, "binding_digest")
            requested_policy_id = self._identifier(policy_id, "policy_id")
            requested_policy_version = self._identifier(policy_version, "policy_version")
            normalized_key = self._idempotency_key(idempotency_key)
        except WorkflowTargetContextAccessAuthorizationLeaseError as exc:
            await self._deny(context, result_code=exc.code)

        if not self._policy_is_current(
            policy_id=requested_policy_id, policy_version=requested_policy_version
        ):
            await self._deny(
                context,
                result_code="workflow_target_context_access_policy_conflict",
                idempotency_key=normalized_key,
                binding_id=binding_id,
            )

        try:
            binding = await self._repository.get_target_context_binding_by_id(binding_id=binding_id)
        except Exception:
            await self._deny(
                context,
                result_code="workflow_target_context_access_evidence_unavailable",
                idempotency_key=normalized_key,
                binding_id=binding_id,
            )
        if binding is None:
            await self._deny_evidence(context, normalized_key, binding_id=binding_id)
        try:
            self._validate_binding(
                binding,
                expected_digest=binding_digest,
                scope=context.scope,
            )
        except (ValueError, WorkflowTargetContextAccessAuthorizationLeaseError):
            await self._deny_evidence(context, normalized_key, binding_id=binding_id)

        fingerprint = canonical_digest(
            {
                "accessor_subject_id": context.subject_id,
                "policy_digest": self._policy.canonical_digest,
                "policy_id": self._policy.policy_id,
                "policy_version": self._policy.policy_version,
                "scope": context.scope.canonical_value(),
                "target_context_binding_digest": binding_digest,
                "target_context_binding_id": binding_id,
            }
        )
        nonce_digest = canonical_digest({"nonce": uuid4().hex, "request_fingerprint": fingerprint})
        await self._audit_required(
            context,
            event_kind="intent",
            outcome="requested",
            result_code="workflow_target_context_access_authorization_requested",
            idempotency_key=normalized_key,
            binding_id=binding_id,
        )

        endpoint_request = self._attestation_request(
            binding,
            artifact_kind=WorkflowProtectedArtifactKind.ENDPOINT,
            materialization_id=binding.endpoint_materialization_id,
            materialization_digest=binding.endpoint_materialization_digest,
            nonce_digest=nonce_digest,
            context=context,
        )
        credential_request = self._attestation_request(
            binding,
            artifact_kind=WorkflowProtectedArtifactKind.CREDENTIAL,
            materialization_id=binding.credential_materialization_id,
            materialization_digest=binding.credential_materialization_digest,
            nonce_digest=nonce_digest,
            context=context,
        )
        try:
            endpoint_attestation = (
                await self._endpoint_status_attestor.attest_endpoint_artifact_status(
                    endpoint_request
                )
            )
            credential_attestation = (
                await self._credential_status_attestor.attest_credential_artifact_status(
                    credential_request
                )
            )
            authoritative_now = await self._repository.get_authoritative_time()
            if authoritative_now.tzinfo is None:
                raise ValueError("repository time must be timezone-aware")
            self._validate_attestation(
                endpoint_attestation,
                request=endpoint_request,
                evaluated_at=authoritative_now,
                required_attestor_id=self._policy.required_endpoint_status_attestor_id,
                required_attestor_version=(self._policy.required_endpoint_status_attestor_version),
            )
            self._validate_attestation(
                credential_attestation,
                request=credential_request,
                evaluated_at=authoritative_now,
                required_attestor_id=self._policy.required_credential_status_attestor_id,
                required_attestor_version=(
                    self._policy.required_credential_status_attestor_version
                ),
            )
            self._verify_status_signature(endpoint_attestation)
            self._verify_status_signature(credential_attestation)
            self._require_full_window(
                binding,
                endpoint_attestation=endpoint_attestation,
                credential_attestation=credential_attestation,
                evaluated_at=authoritative_now,
            )
        except Exception:
            await self._deny_evidence(context, normalized_key, binding_id=binding_id)

        candidate = self._build_lease(
            binding=binding,
            endpoint_attestation=endpoint_attestation,
            credential_attestation=credential_attestation,
            accessor_subject_id=context.subject_id,
            issued_at=authoritative_now,
        )

        async def required_precommit_audit() -> None:
            await self._audit(
                context,
                event_kind="commit-authorization",
                outcome="authorized",
                result_code="workflow_target_context_access_persistence_authorized",
                idempotency_key=normalized_key,
                binding_id=binding_id,
                lease=candidate,
            )

        try:
            result = await self._repository.authorize_target_context_access(
                WorkflowTargetContextAccessAuthorizationLeaseRequest(
                    expected_target_context_binding_id=binding.binding_id,
                    expected_target_context_binding_digest=binding.canonical_digest,
                    expected_target_context_commitment=binding.target_context_commitment,
                    expected_endpoint_materialization_id=binding.endpoint_materialization_id,
                    expected_endpoint_materialization_digest=(
                        binding.endpoint_materialization_digest
                    ),
                    expected_credential_materialization_id=binding.credential_materialization_id,
                    expected_credential_materialization_digest=(
                        binding.credential_materialization_digest
                    ),
                    endpoint_status_attestation=endpoint_attestation,
                    credential_status_attestation=credential_attestation,
                    expected_request_nonce_digest=nonce_digest,
                    expected_endpoint_status_attestor_id=(
                        self._policy.required_endpoint_status_attestor_id
                    ),
                    expected_endpoint_status_attestor_version=(
                        self._policy.required_endpoint_status_attestor_version
                    ),
                    expected_credential_status_attestor_id=(
                        self._policy.required_credential_status_attestor_id
                    ),
                    expected_credential_status_attestor_version=(
                        self._policy.required_credential_status_attestor_version
                    ),
                    offline_signature_verifier=self._status_signature_verifier,
                    expected_policy_digest=self._policy.canonical_digest,
                    expected_validity_window_seconds=self._policy.validity_window_seconds,
                    scope=context.scope,
                    accessor_subject_id=context.subject_id,
                    requested_at=authoritative_now,
                    candidate=candidate,
                    idempotency_key=normalized_key,
                    request_fingerprint=fingerprint,
                    required_precommit_audit=required_precommit_audit,
                )
            )
        except Exception:
            await self._deny(
                context,
                result_code="workflow_target_context_access_repository_unavailable",
                idempotency_key=normalized_key,
                binding_id=binding_id,
            )

        if result.status in (
            WorkflowTargetContextAccessAuthorizationLeaseStatus.AUTHORIZED,
            WorkflowTargetContextAccessAuthorizationLeaseStatus.REPLAY,
        ):
            if result.lease is None:
                await self._deny_evidence(context, normalized_key, binding_id=binding_id)
            try:
                self._validate_lease(
                    result.lease,
                    binding=binding,
                    scope=context.scope,
                    evaluated_at=authoritative_now,
                )
            except (ValueError, WorkflowTargetContextAccessAuthorizationLeaseError):
                await self._deny_evidence(context, normalized_key, binding_id=binding_id)
            await self._audit_committed_result(
                context,
                event_kind=(
                    "completion"
                    if result.status
                    is WorkflowTargetContextAccessAuthorizationLeaseStatus.AUTHORIZED
                    else "replay"
                ),
                result_code=(
                    "workflow_target_context_access_authorization_lease_created"
                    if result.status
                    is WorkflowTargetContextAccessAuthorizationLeaseStatus.AUTHORIZED
                    else "workflow_target_context_access_authorization_lease_replayed"
                ),
                idempotency_key=normalized_key,
                binding_id=binding_id,
                lease=result.lease,
            )
            return result.lease

        result_code = {
            WorkflowTargetContextAccessAuthorizationLeaseStatus.IDEMPOTENCY_CONFLICT: (
                "workflow_target_context_access_idempotency_conflict"
            ),
            WorkflowTargetContextAccessAuthorizationLeaseStatus.EVIDENCE_CONFLICT: (
                "workflow_target_context_access_evidence_conflict"
            ),
            WorkflowTargetContextAccessAuthorizationLeaseStatus.ALREADY_AUTHORIZED: (
                "workflow_target_context_access_already_authorized"
            ),
            WorkflowTargetContextAccessAuthorizationLeaseStatus.PRECOMMIT_AUDIT_FAILED: (
                "workflow_target_context_access_precommit_audit_failed"
            ),
        }.get(result.status, "workflow_target_context_access_repository_contract_violation")
        await self._deny(
            context,
            result_code=result_code,
            idempotency_key=normalized_key,
            binding_id=binding_id,
            lease=result.lease,
        )

    async def list_leases(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease, ...]:
        if not self._repository.durable:
            raise WorkflowTargetContextAccessAuthorizationLeaseError(
                "workflow_target_context_access_durable_repository_required",
                "Durable target context access authorization storage is required.",
            )
        if not 1 <= limit <= 256:
            raise WorkflowTargetContextAccessAuthorizationLeaseError(
                "workflow_target_context_access_limit_invalid",
                "The target context access authorization lease limit is invalid.",
            )
        leases = await self._repository.list_target_context_access_authorization_leases(
            scope=scope, limit=limit
        )
        for lease in leases:
            self._validate_historical_lease(lease, scope=scope)
        return leases

    def _policy_is_current(self, *, policy_id: str, policy_version: str) -> bool:
        return (
            policy_id == self._policy.policy_id
            and policy_version == self._policy.policy_version
            and canonical_digest(self._policy.digest_payload()) == self._policy.canonical_digest
            and self._policy.validity_window_seconds == 5
            and self._policy.full_window_required is True
            and self._policy.accessor_subject_bound is True
            and self._policy.single_use_required is True
            and self._policy.renewable_allowed is False
            and self._policy.transferable_allowed is False
            and self._policy.endpoint_status_attestation_required is True
            and self._policy.credential_status_attestation_required is True
            and bool(self._policy.required_endpoint_status_attestor_id)
            and bool(self._policy.required_endpoint_status_attestor_version)
            and bool(self._policy.required_credential_status_attestor_id)
            and bool(self._policy.required_credential_status_attestor_version)
        )

    @staticmethod
    def _attestation_request(
        binding: WorkflowEventPhysicalTransportTargetContextBinding,
        *,
        artifact_kind: WorkflowProtectedArtifactKind,
        materialization_id: str,
        materialization_digest: str,
        nonce_digest: str,
        context: WorkflowPhysicalTransportTargetContextAccessorContext,
    ) -> WorkflowProtectedArtifactStatusAttestationRequest:
        return WorkflowProtectedArtifactStatusAttestationRequest(
            artifact_kind=artifact_kind,
            materialization_id=materialization_id,
            materialization_digest=materialization_digest,
            target_context_binding_id=binding.binding_id,
            target_context_binding_digest=binding.canonical_digest,
            target_context_commitment=binding.target_context_commitment,
            scope=context.scope,
            accessor_subject_id=context.subject_id,
            request_nonce_digest=nonce_digest,
            requested_at=context.requested_at,
        )

    def _build_lease(
        self,
        *,
        binding: WorkflowEventPhysicalTransportTargetContextBinding,
        endpoint_attestation: WorkflowProtectedArtifactStatusAttestation,
        credential_attestation: WorkflowProtectedArtifactStatusAttestation,
        accessor_subject_id: str,
        issued_at: datetime,
    ) -> WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease:
        lease_id = (
            "workflow-physical-transport-target-context-access-authorization-lease."
            + sha256(f"{binding.binding_id}:{accessor_subject_id}".encode()).hexdigest()[:24]
        )
        values: dict[str, object] = {
            "authorization_lease_id": lease_id,
            "target_context_binding_id": binding.binding_id,
            "target_context_binding_digest": binding.canonical_digest,
            "target_context_commitment": binding.target_context_commitment,
            "endpoint_status_attestation_id": endpoint_attestation.attestation_id,
            "endpoint_status_attestation_digest": endpoint_attestation.canonical_digest,
            "endpoint_status_attestation_valid_until": endpoint_attestation.valid_until,
            "credential_status_attestation_id": credential_attestation.attestation_id,
            "credential_status_attestation_digest": credential_attestation.canonical_digest,
            "credential_status_attestation_valid_until": credential_attestation.valid_until,
            "scope": binding.scope,
            "accessor_subject_id": accessor_subject_id,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "issued_at": issued_at,
            "valid_until": issued_at + timedelta(seconds=5),
            "joint_usable_until": binding.joint_usable_until,
            "single_use": True,
            "renewable": False,
            "transferable": False,
            "state": (
                WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseState
            ).AUTHORIZED_UNCONSUMED,
            "authority": (
                WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseAuthority()
            ),
        }
        payload = {
            name: value.canonical_value()
            if isinstance(
                value,
                (
                    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseAuthority,
                    WorkflowScope,
                ),
            )
            else value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(
                value,
                WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseState,
            )
            else value
            for name, value in values.items()
        }
        return WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease(
            **cast(Any, values), canonical_digest=canonical_digest(payload)
        )

    @staticmethod
    def _validate_binding(
        binding: WorkflowEventPhysicalTransportTargetContextBinding,
        *,
        expected_digest: str,
        scope: WorkflowScope,
    ) -> None:
        if (
            binding.scope != scope
            or binding.canonical_digest != expected_digest
            or canonical_digest(binding.digest_payload()) != binding.canonical_digest
            or binding.state is not WorkflowEventPhysicalTransportTargetContextBindingState.BOUND
            or any(binding.authority.canonical_value().values())
        ):
            raise WorkflowTargetContextAccessAuthorizationLeaseError(
                "workflow_target_context_access_evidence_conflict",
                "Target context access evidence is invalid.",
            )

    @staticmethod
    def _validate_attestation(
        attestation: WorkflowProtectedArtifactStatusAttestation,
        *,
        request: WorkflowProtectedArtifactStatusAttestationRequest,
        evaluated_at: datetime,
        required_attestor_id: str,
        required_attestor_version: str,
    ) -> None:
        if (
            attestation.artifact_kind is not request.artifact_kind
            or attestation.materialization_id != request.materialization_id
            or attestation.materialization_digest != request.materialization_digest
            or attestation.target_context_binding_id != request.target_context_binding_id
            or attestation.target_context_binding_digest != request.target_context_binding_digest
            or attestation.target_context_commitment != request.target_context_commitment
            or attestation.protected_store_attestor_id != required_attestor_id
            or attestation.protected_store_attestor_version != required_attestor_version
            or attestation.request_nonce_digest != request.request_nonce_digest
            or canonical_digest(attestation.digest_payload()) != attestation.canonical_digest
            or attestation.observed_at > evaluated_at
            or attestation.valid_until <= evaluated_at
            or attestation.usable is not True
            or attestation.revoked is not False
            or attestation.destroyed is not False
        ):
            raise WorkflowTargetContextAccessAuthorizationLeaseError(
                "workflow_target_context_access_evidence_conflict",
                "Target context access evidence is invalid.",
            )

    def _verify_status_signature(
        self, attestation: WorkflowProtectedArtifactStatusAttestation
    ) -> None:
        if self._status_signature_verifier.verify_status_attestation(attestation) is not True:
            raise WorkflowTargetContextAccessAuthorizationLeaseError(
                "workflow_target_context_access_evidence_conflict",
                "Target context access evidence is invalid.",
            )

    @staticmethod
    def _require_full_window(
        binding: WorkflowEventPhysicalTransportTargetContextBinding,
        *,
        endpoint_attestation: WorkflowProtectedArtifactStatusAttestation,
        credential_attestation: WorkflowProtectedArtifactStatusAttestation,
        evaluated_at: datetime,
    ) -> None:
        complete_until = evaluated_at + timedelta(seconds=5)
        if any(
            complete_until > deadline
            for deadline in (
                binding.joint_usable_until,
                endpoint_attestation.valid_until,
                credential_attestation.valid_until,
            )
        ):
            raise WorkflowTargetContextAccessAuthorizationLeaseError(
                "workflow_target_context_access_evidence_conflict",
                "Target context access evidence is invalid.",
            )

    def _validate_lease(
        self,
        lease: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease,
        *,
        binding: WorkflowEventPhysicalTransportTargetContextBinding,
        scope: WorkflowScope,
        evaluated_at: datetime,
    ) -> None:
        self._validate_historical_lease(lease, scope=scope)
        if (
            lease.target_context_binding_id != binding.binding_id
            or lease.target_context_binding_digest != binding.canonical_digest
            or lease.target_context_commitment != binding.target_context_commitment
            or lease.accessor_subject_id
            != WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_SUBJECT
            or lease.effective_state(evaluated_at=evaluated_at)
            is not (
                WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseEffectiveState
            ).ACTIVE
        ):
            raise WorkflowTargetContextAccessAuthorizationLeaseError(
                "workflow_target_context_access_repository_contract_violation",
                "Stored target context access authorization evidence is invalid.",
            )

    def _validate_historical_lease(
        self,
        lease: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease,
        *,
        scope: WorkflowScope,
    ) -> None:
        if (
            lease.scope != scope
            or lease.policy_id != self._policy.policy_id
            or lease.policy_version != self._policy.policy_version
            or lease.policy_digest != self._policy.canonical_digest
            or canonical_digest(lease.digest_payload()) != lease.canonical_digest
            or lease.valid_until - lease.issued_at != timedelta(seconds=5)
            or lease.single_use is not True
            or lease.renewable is not False
            or lease.transferable is not False
            or lease.authority.protected_artifact_access_authorized is not True
            or any(
                value is not False
                for name, value in lease.authority.canonical_value().items()
                if name != "protected_artifact_access_authorized"
            )
        ):
            raise WorkflowTargetContextAccessAuthorizationLeaseError(
                "workflow_target_context_access_repository_contract_violation",
                "Stored target context access authorization evidence is invalid.",
            )

    async def _require_accessor_workload(
        self, context: WorkflowPhysicalTransportTargetContextAccessorContext
    ) -> None:
        if (
            context.subject_id != WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_SUBJECT
            or context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience
            != WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE
        ):
            await self._deny(
                context,
                result_code="workflow_target_context_access_accessor_identity_required",
            )

    async def _audit_committed_result(
        self,
        context: WorkflowPhysicalTransportTargetContextAccessorContext,
        *,
        event_kind: str,
        result_code: str,
        idempotency_key: str,
        binding_id: str,
        lease: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease,
    ) -> None:
        try:
            await self._audit(
                context,
                event_kind=event_kind,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                binding_id=binding_id,
                lease=lease,
            )
        except Exception as exc:
            raise WorkflowTargetContextAccessAuthorizationLeaseError(
                "workflow_target_context_access_completion_audit_outcome_uncertain",
                "The access lease is committed but completion audit is unavailable.",
            ) from exc

    async def _deny_evidence(
        self,
        context: WorkflowPhysicalTransportTargetContextAccessorContext,
        idempotency_key: str,
        *,
        binding_id: str,
    ) -> NoReturn:
        await self._deny(
            context,
            result_code="workflow_target_context_access_evidence_conflict",
            idempotency_key=idempotency_key,
            binding_id=binding_id,
        )

    async def _deny(
        self,
        context: WorkflowPhysicalTransportTargetContextAccessorContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
        binding_id: str = "none",
        lease: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease | None = None,
    ) -> NoReturn:
        try:
            await self._audit(
                context,
                event_kind="denied",
                outcome="denied",
                result_code=result_code,
                idempotency_key=idempotency_key,
                binding_id=binding_id,
                lease=lease,
            )
        except Exception as exc:
            raise WorkflowTargetContextAccessAuthorizationLeaseError(
                "workflow_target_context_access_audit_unavailable",
                "The authorization was denied and required audit is unavailable.",
            ) from exc
        raise WorkflowTargetContextAccessAuthorizationLeaseError(
            result_code,
            "The target context access authorization request was denied.",
        )

    async def _audit_required(
        self,
        context: WorkflowPhysicalTransportTargetContextAccessorContext,
        *,
        event_kind: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        binding_id: str,
    ) -> None:
        try:
            await self._audit(
                context,
                event_kind=event_kind,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                binding_id=binding_id,
            )
        except Exception as exc:
            raise WorkflowTargetContextAccessAuthorizationLeaseError(
                "workflow_target_context_access_audit_unavailable",
                "Required target context access audit evidence is unavailable.",
            ) from exc

    async def _audit(
        self,
        context: WorkflowPhysicalTransportTargetContextAccessorContext,
        *,
        event_kind: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        binding_id: str,
        lease: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease | None = None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=(
                    "atlas.workflow.physical-transport-target-context-access-authorization."
                    f"{event_kind}"
                ),
                schema_version="1.0",
                producer=(
                    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESS_AUTHORIZATION_LEASE_PRODUCER
                ),
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id=(
                    "workflow.physical-transport-target-context-access-authorization-leases.create"
                ),
                resource_type=(
                    "resource.workflow-physical-transport-target-context-access-authorization-lease"
                ),
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "target-context-access-authorization-lease",
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    (
                        "authorization_lease_id",
                        "none" if lease is None else lease.authorization_lease_id,
                    ),
                    ("target_context_binding_id", binding_id),
                    ("protected_artifact_access_authority", "true" if lease else "false"),
                    ("credential_delivery_authority", "false"),
                    ("network_access_authority", "false"),
                    ("publication_authority", "false"),
                    ("dispatch_authority", "false"),
                    ("execution_authority", "false"),
                    ("infrastructure_mutation_authority", "false"),
                ),
            )
        )

    @staticmethod
    def _identifier(value: str, name: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 240 or any(c.isspace() for c in normalized):
            raise WorkflowTargetContextAccessAuthorizationLeaseError(
                f"workflow_target_context_access_{name}_invalid",
                f"{name} is invalid.",
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowTargetContextAccessAuthorizationLeaseError(
                "workflow_target_context_access_idempotency_key_invalid",
                "The idempotency key is invalid.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise WorkflowTargetContextAccessAuthorizationLeaseError(
                f"workflow_target_context_access_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value


__all__ = [
    "WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE",
    "WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_SUBJECT",
    "WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESS_AUTHORIZATION_LEASE_PRODUCER",
    "WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseService",
    "WorkflowPhysicalTransportTargetContextAccessorContext",
]

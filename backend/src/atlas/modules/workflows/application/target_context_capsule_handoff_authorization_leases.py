from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_lease_ports import (  # noqa: E501
    WorkflowProtectedTargetContextCapsuleLifecycleAttestationRequest,
    WorkflowProtectedTargetContextCapsuleLifecycleSignatureVerifier,
    WorkflowProtectedTargetContextCapsuleLifecycleStatusAttestor,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRepository,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRequest,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseStatus,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedTargetContextCapsuleLifecycleAttestation,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingState,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseEffectiveState,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseState,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationPolicy,
    WorkflowProtectedTransportTargetContextCapsuleHandoffLeaseAuthority,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_transport_target_context_capsule_handoff_authorization_policy,
)

WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT = (
    "service.workflow-protected-transport-target-context-capsule-consumer"
)
WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE = (
    "audience.workflow-protected-transport-target-context-capsule-consumer"
)
WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_HANDOFF_AUTHORIZATION_LEASE_PRODUCER = (
    "project-atlas-workflow-protected-target-context-capsule-handoff-authorizer"
)


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext:
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
            raise ValueError("target context capsule handoff context contains invalid evidence")
        if self.requested_at.tzinfo is None:
            raise ValueError("target context capsule handoff requested_at must be timezone-aware")


class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseService:
    """Issues narrow handoff-request authority without retrieving or moving a capsule."""

    def __init__(
        self,
        *,
        authorization_repository: (
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRepository
        ),
        lifecycle_status_attestor: (WorkflowProtectedTargetContextCapsuleLifecycleStatusAttestor),
        lifecycle_signature_verifier: (
            WorkflowProtectedTargetContextCapsuleLifecycleSignatureVerifier
        ),
        audit_sink: AuditSink,
        policy: (
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationPolicy | None
        ) = None,
    ) -> None:
        self._repository = authorization_repository
        self._lifecycle_status_attestor = lifecycle_status_attestor
        self._lifecycle_signature_verifier = lifecycle_signature_verifier
        self._audit_sink = audit_sink
        self._policy = policy or (
            code_owned_workflow_protected_transport_target_context_capsule_handoff_authorization_policy()
        )

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def repository(
        self,
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationPolicy:
        return self._policy

    async def authorize(
        self,
        *,
        consumer_binding_id: str,
        consumer_binding_digest: str,
        policy_id: str,
        policy_version: str,
        idempotency_key: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease:
        await self._require_consumer_workload(context)
        if not self._repository.durable:
            await self._deny(
                context,
                result_code="workflow_target_context_capsule_handoff_durable_repository_required",
            )
        try:
            binding_id = self._identifier(consumer_binding_id, "consumer_binding_id")
            binding_digest = self._digest(consumer_binding_digest, "consumer_binding_digest")
            requested_policy_id = self._identifier(policy_id, "policy_id")
            requested_policy_version = self._identifier(policy_version, "policy_version")
            normalized_key = self._idempotency_key(idempotency_key)
        except WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError as exc:
            await self._deny(context, result_code=exc.code)

        if not self._policy_is_current(
            policy_id=requested_policy_id,
            policy_version=requested_policy_version,
        ):
            await self._deny(
                context,
                result_code="workflow_target_context_capsule_handoff_policy_conflict",
                idempotency_key=normalized_key,
                binding_id=binding_id,
            )

        try:
            binding = await self._repository.get_target_context_capsule_consumer_binding_by_id(
                binding_id=binding_id
            )
        except Exception:
            await self._deny(
                context,
                result_code="workflow_target_context_capsule_handoff_evidence_unavailable",
                idempotency_key=normalized_key,
                binding_id=binding_id,
            )
        if binding is None:
            await self._deny_evidence(context, normalized_key, binding_id=binding_id)
        try:
            self._validate_binding(binding, expected_digest=binding_digest, scope=context.scope)
        except (
            ValueError,
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError,
        ):
            await self._deny_evidence(context, normalized_key, binding_id=binding_id)

        fingerprint = canonical_digest(
            {
                "consumer_binding_digest": binding_digest,
                "consumer_binding_id": binding_id,
                "consumer_subject_id": context.subject_id,
                "policy_digest": self._policy.canonical_digest,
                "policy_id": self._policy.policy_id,
                "policy_version": self._policy.policy_version,
                "scope": context.scope.canonical_value(),
            }
        )
        nonce_digest = canonical_digest({"nonce": uuid4().hex, "request_fingerprint": fingerprint})
        await self._audit_required(
            context,
            event_kind="intent",
            outcome="requested",
            result_code="workflow_target_context_capsule_handoff_authorization_requested",
            idempotency_key=normalized_key,
            binding_id=binding_id,
        )

        attestation_request = self._attestation_request(
            binding,
            nonce_digest=nonce_digest,
            context=context,
        )
        try:
            # This is the only provider I/O and occurs before repository authorization.
            lifecycle_attestation = await self._lifecycle_status_attestor.attest_capsule_lifecycle(
                attestation_request
            )
            authoritative_now = await self._repository.get_authoritative_time()
            if authoritative_now.tzinfo is None:
                raise ValueError("repository time must be timezone-aware")
            self._validate_attestation(
                lifecycle_attestation,
                request=attestation_request,
                evaluated_at=authoritative_now,
            )
            self._verify_lifecycle_signature(lifecycle_attestation)
            self._require_full_window(
                binding,
                lifecycle_attestation=lifecycle_attestation,
                evaluated_at=authoritative_now,
            )
        except Exception:
            await self._deny_evidence(context, normalized_key, binding_id=binding_id)

        candidate = self._build_lease(
            binding=binding,
            lifecycle_attestation=lifecycle_attestation,
            issued_at=authoritative_now,
        )

        async def required_precommit_audit() -> None:
            await self._audit(
                context,
                event_kind="persistence-readiness",
                outcome="succeeded",
                result_code="workflow_target_context_capsule_handoff_persistence_audit_ready",
                idempotency_key=normalized_key,
                binding_id=binding_id,
                lease=candidate,
            )

        try:
            result = await self._repository.authorize_target_context_capsule_handoff(
                WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRequest(
                    expected_consumer_binding_id=binding.binding_id,
                    expected_consumer_binding_digest=binding.canonical_digest,
                    expected_opening_result_id=binding.opening_result_id,
                    expected_opening_result_digest=binding.opening_result_digest,
                    expected_sealed_capsule_id=binding.sealed_capsule_id,
                    expected_sealed_capsule_digest=binding.sealed_capsule_digest,
                    expected_capsule_schema_id=binding.capsule_schema_id,
                    expected_capsule_schema_version=binding.capsule_schema_version,
                    lifecycle_attestation=lifecycle_attestation,
                    expected_request_nonce_digest=nonce_digest,
                    expected_lifecycle_attestor_id=(
                        self._policy.required_capsule_lifecycle_attestor_id
                    ),
                    expected_lifecycle_attestor_version=(
                        self._policy.required_capsule_lifecycle_attestor_version
                    ),
                    offline_signature_verifier=self._lifecycle_signature_verifier,
                    expected_policy_digest=self._policy.canonical_digest,
                    expected_validity_window_seconds=self._policy.validity_window_seconds,
                    scope=context.scope,
                    consumer_subject_id=self._policy.consumer_subject_id,
                    consumer_audience=self._policy.consumer_audience,
                    consumer_contract_id=self._policy.consumer_contract_id,
                    consumer_contract_version=self._policy.consumer_contract_version,
                    purpose_id=self._policy.purpose_id,
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
                result_code="workflow_target_context_capsule_handoff_repository_unavailable",
                idempotency_key=normalized_key,
                binding_id=binding_id,
            )

        status_type = WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseStatus
        if result.status in (status_type.AUTHORIZED, status_type.REPLAY):
            if result.lease is None or result.evaluated_at is None:
                await self._deny_evidence(context, normalized_key, binding_id=binding_id)
            try:
                if result.evaluated_at.tzinfo is None:
                    raise ValueError("repository evaluation time must be timezone-aware")
                self._validate_lease(
                    result.lease,
                    binding=binding,
                    scope=context.scope,
                    evaluated_at=result.evaluated_at,
                )
            except (
                ValueError,
                WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError,
            ):
                await self._deny_evidence(context, normalized_key, binding_id=binding_id)
            authorized = result.status is status_type.AUTHORIZED
            await self._audit_committed_result(
                context,
                event_kind="completion" if authorized else "replay",
                result_code=(
                    "workflow_target_context_capsule_handoff_authorization_lease_created"
                    if authorized
                    else "workflow_target_context_capsule_handoff_authorization_lease_replayed"
                ),
                idempotency_key=normalized_key,
                binding_id=binding_id,
                lease=result.lease,
            )
            return result.lease

        result_code = {
            status_type.IDEMPOTENCY_CONFLICT: (
                "workflow_target_context_capsule_handoff_idempotency_conflict"
            ),
            status_type.EVIDENCE_CONFLICT: (
                "workflow_target_context_capsule_handoff_evidence_conflict"
            ),
            status_type.ALREADY_AUTHORIZED: (
                "workflow_target_context_capsule_handoff_already_authorized"
            ),
            status_type.PRECOMMIT_AUDIT_FAILED: (
                "workflow_target_context_capsule_handoff_precommit_audit_failed"
            ),
        }.get(
            result.status,
            "workflow_target_context_capsule_handoff_repository_contract_violation",
        )
        await self._deny(
            context,
            result_code=result_code,
            idempotency_key=normalized_key,
            binding_id=binding_id,
            lease=result.lease,
        )

    async def list_leases(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease, ...]:
        if not self._repository.durable:
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(
                "workflow_target_context_capsule_handoff_durable_repository_required",
                "Durable target context capsule handoff authorization storage is required.",
            )
        if not 1 <= limit <= 256:
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(
                "workflow_target_context_capsule_handoff_limit_invalid",
                "The target context capsule handoff authorization lease limit is invalid.",
            )
        leases = await self._repository.list_target_context_capsule_handoff_authorization_leases(
            scope=scope,
            limit=limit,
        )
        for lease in leases:
            self._validate_historical_lease(lease, scope=scope)
        return leases

    def _policy_is_current(self, *, policy_id: str, policy_version: str) -> bool:
        return (
            policy_id == self._policy.policy_id
            and policy_version == self._policy.policy_version
            and canonical_digest(self._policy.digest_payload()) == self._policy.canonical_digest
            and self._policy.validity_window_seconds == 1
            and self._policy.full_window_required is True
            and self._policy.consumer_subject_bound is True
            and self._policy.single_use_required is True
            and self._policy.renewable_allowed is False
            and self._policy.transferable_allowed is False
            and self._policy.capsule_lifecycle_attestation_required is True
        )

    @staticmethod
    def _attestation_request(
        binding: WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
        *,
        nonce_digest: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> WorkflowProtectedTargetContextCapsuleLifecycleAttestationRequest:
        return WorkflowProtectedTargetContextCapsuleLifecycleAttestationRequest(
            opening_result_id=binding.opening_result_id,
            opening_result_digest=binding.opening_result_digest,
            consumer_binding_id=binding.binding_id,
            consumer_binding_digest=binding.canonical_digest,
            sealed_capsule_id=binding.sealed_capsule_id,
            sealed_capsule_digest=binding.sealed_capsule_digest,
            capsule_schema_id=binding.capsule_schema_id,
            capsule_schema_version=binding.capsule_schema_version,
            scope=binding.scope,
            consumer_subject_id=context.subject_id,
            request_nonce_digest=nonce_digest,
            requested_at=context.requested_at,
        )

    def _build_lease(
        self,
        *,
        binding: WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
        lifecycle_attestation: WorkflowProtectedTargetContextCapsuleLifecycleAttestation,
        issued_at: datetime,
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease:
        lease_id = (
            "workflow-target-context-capsule-handoff-authorization-lease."
            + sha256(f"{binding.binding_id}:{binding.sealed_capsule_id}".encode()).hexdigest()[:24]
        )
        values: dict[str, object] = {
            "authorization_lease_id": lease_id,
            "consumer_binding_id": binding.binding_id,
            "consumer_binding_digest": binding.canonical_digest,
            "opening_result_id": binding.opening_result_id,
            "opening_result_digest": binding.opening_result_digest,
            "sealed_capsule_id": binding.sealed_capsule_id,
            "sealed_capsule_digest": binding.sealed_capsule_digest,
            "capsule_schema_id": binding.capsule_schema_id,
            "capsule_schema_version": binding.capsule_schema_version,
            "lifecycle_attestation_id": lifecycle_attestation.attestation_id,
            "lifecycle_attestation_digest": lifecycle_attestation.canonical_digest,
            "lifecycle_attestation_valid_until": lifecycle_attestation.valid_until,
            "scope": binding.scope,
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
            "effective_until": binding.effective_until,
            "single_use": True,
            "renewable": False,
            "transferable": False,
            "lease_is_bearer_capability": False,
            "state": (
                WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseState
            ).AUTHORIZED_UNCONSUMED,
            "authority": WorkflowProtectedTransportTargetContextCapsuleHandoffLeaseAuthority(),
        }
        return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease(
            **cast(Any, values),
            canonical_digest=canonical_digest(
                {
                    name: value.canonical_value()
                    if isinstance(
                        value,
                        (
                            WorkflowProtectedTransportTargetContextCapsuleHandoffLeaseAuthority,
                            WorkflowScope,
                        ),
                    )
                    else value.isoformat()
                    if isinstance(value, datetime)
                    else value.value
                    if isinstance(
                        value,
                        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseState,
                    )
                    else value
                    for name, value in values.items()
                }
            ),
        )

    def _validate_binding(
        self,
        binding: WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
        *,
        expected_digest: str,
        scope: WorkflowScope,
    ) -> None:
        if (
            binding.scope != scope
            or binding.canonical_digest != expected_digest
            or canonical_digest(binding.digest_payload()) != binding.canonical_digest
            or binding.state
            is not WorkflowProtectedTransportTargetContextCapsuleConsumerBindingState.BOUND
            or binding.capsule_is_bearer_capability is not False
            or binding.consumer_subject_id != self._policy.consumer_subject_id
            or binding.consumer_audience != self._policy.consumer_audience
            or binding.consumer_contract_id != self._policy.consumer_contract_id
            or binding.consumer_contract_version != self._policy.consumer_contract_version
            or binding.purpose_id != self._policy.purpose_id
            or any(binding.authority.canonical_value().values())
        ):
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(
                "workflow_target_context_capsule_handoff_evidence_conflict",
                "Target context capsule handoff evidence is invalid.",
            )

    def _validate_attestation(
        self,
        attestation: WorkflowProtectedTargetContextCapsuleLifecycleAttestation,
        *,
        request: WorkflowProtectedTargetContextCapsuleLifecycleAttestationRequest,
        evaluated_at: datetime,
    ) -> None:
        if (
            attestation.opening_result_id != request.opening_result_id
            or attestation.opening_result_digest != request.opening_result_digest
            or attestation.consumer_binding_id != request.consumer_binding_id
            or attestation.consumer_binding_digest != request.consumer_binding_digest
            or attestation.sealed_capsule_id != request.sealed_capsule_id
            or attestation.sealed_capsule_digest != request.sealed_capsule_digest
            or attestation.capsule_schema_id != request.capsule_schema_id
            or attestation.capsule_schema_version != request.capsule_schema_version
            or attestation.request_nonce_digest != request.request_nonce_digest
            or attestation.protected_store_attestor_id
            != self._policy.required_capsule_lifecycle_attestor_id
            or attestation.protected_store_attestor_version
            != self._policy.required_capsule_lifecycle_attestor_version
            or canonical_digest(attestation.digest_payload()) != attestation.canonical_digest
            or attestation.observed_at > evaluated_at
            or attestation.valid_until <= evaluated_at
            or attestation.usable is not True
            or attestation.revoked is not False
            or attestation.destroyed is not False
            or attestation.sealed is not True
            or attestation.capsule_is_bearer_capability is not False
        ):
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(
                "workflow_target_context_capsule_handoff_evidence_conflict",
                "Target context capsule handoff evidence is invalid.",
            )

    def _verify_lifecycle_signature(
        self,
        attestation: WorkflowProtectedTargetContextCapsuleLifecycleAttestation,
    ) -> None:
        if (
            self._lifecycle_signature_verifier.verify_capsule_lifecycle_attestation(attestation)
            is not True
        ):
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(
                "workflow_target_context_capsule_handoff_evidence_conflict",
                "Target context capsule handoff evidence is invalid.",
            )

    @staticmethod
    def _require_full_window(
        binding: WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
        *,
        lifecycle_attestation: WorkflowProtectedTargetContextCapsuleLifecycleAttestation,
        evaluated_at: datetime,
    ) -> None:
        complete_until = evaluated_at + timedelta(seconds=1)
        if (
            complete_until > binding.effective_until
            or complete_until > lifecycle_attestation.valid_until
        ):
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(
                "workflow_target_context_capsule_handoff_evidence_conflict",
                "Target context capsule handoff evidence is invalid.",
            )

    def _validate_lease(
        self,
        lease: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
        *,
        binding: WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
        scope: WorkflowScope,
        evaluated_at: datetime,
    ) -> None:
        self._validate_historical_lease(lease, scope=scope)
        if (
            lease.consumer_binding_id != binding.binding_id
            or lease.consumer_binding_digest != binding.canonical_digest
            or lease.opening_result_id != binding.opening_result_id
            or lease.sealed_capsule_id != binding.sealed_capsule_id
            or lease.consumer_subject_id
            != WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT
            or lease.consumer_audience
            != WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            or lease.effective_state(evaluated_at=evaluated_at)
            is not (
                WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseEffectiveState
            ).ACTIVE
        ):
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(
                "workflow_target_context_capsule_handoff_repository_contract_violation",
                "Stored target context capsule handoff authorization evidence is invalid.",
            )

    def _validate_historical_lease(
        self,
        lease: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
        *,
        scope: WorkflowScope,
    ) -> None:
        if (
            lease.scope != scope
            or lease.policy_id != self._policy.policy_id
            or lease.policy_version != self._policy.policy_version
            or lease.policy_digest != self._policy.canonical_digest
            or canonical_digest(lease.digest_payload()) != lease.canonical_digest
            or lease.valid_until - lease.issued_at != timedelta(seconds=1)
            or lease.single_use is not True
            or lease.renewable is not False
            or lease.transferable is not False
            or lease.lease_is_bearer_capability is not False
            or lease.authority.target_context_capsule_handoff_authorized is not True
            or any(
                value is not False
                for name, value in lease.authority.canonical_value().items()
                if name != "target_context_capsule_handoff_authorized"
            )
        ):
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(
                "workflow_target_context_capsule_handoff_repository_contract_violation",
                "Stored target context capsule handoff authorization evidence is invalid.",
            )

    async def _require_consumer_workload(
        self,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> None:
        if (
            context.subject_id != WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT
            or context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience
            != WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
        ):
            await self._deny(
                context,
                result_code="workflow_target_context_capsule_handoff_consumer_identity_required",
            )

    async def _audit_committed_result(
        self,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
        *,
        event_kind: str,
        result_code: str,
        idempotency_key: str,
        binding_id: str,
        lease: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
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
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(
                "workflow_target_context_capsule_handoff_completion_audit_outcome_uncertain",
                "The handoff lease is committed but completion audit is unavailable.",
            ) from exc

    async def _deny_evidence(
        self,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
        idempotency_key: str,
        *,
        binding_id: str,
    ) -> NoReturn:
        await self._deny(
            context,
            result_code="workflow_target_context_capsule_handoff_evidence_conflict",
            idempotency_key=idempotency_key,
            binding_id=binding_id,
        )

    async def _deny(
        self,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
        binding_id: str = "none",
        lease: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease
        | None = None,
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
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(
                "workflow_target_context_capsule_handoff_audit_unavailable",
                "The authorization was denied and required audit is unavailable.",
            ) from exc
        raise WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(
            result_code,
            "The target context capsule handoff authorization request was denied.",
        )

    async def _audit_required(
        self,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
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
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(
                "workflow_target_context_capsule_handoff_audit_unavailable",
                "Required target context capsule handoff audit evidence is unavailable.",
            ) from exc

    async def _audit(
        self,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
        *,
        event_kind: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        binding_id: str,
        lease: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease
        | None = None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=(
                    "atlas.workflow.protected-target-context-capsule-handoff-authorization."
                    f"{event_kind}"
                ),
                schema_version="1.0",
                producer=(
                    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_HANDOFF_AUTHORIZATION_LEASE_PRODUCER
                ),
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id=(
                    "workflow.protected-target-context-capsule-handoff-authorization-leases.create"
                ),
                resource_type=(
                    "resource.workflow-protected-target-context-capsule-handoff-authorization-lease"
                ),
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "target-context-capsule-handoff-authorization-lease",
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
                    ("consumer_binding_id", binding_id),
                    ("target_context_capsule_handoff_authority", "true" if lease else "false"),
                    ("protected_artifact_access_authority", "false"),
                    ("credential_delivery_authority", "false"),
                    ("network_access_authority", "false"),
                    ("delivery_authority", "false"),
                    ("execution_authority", "false"),
                    ("infrastructure_mutation_authority", "false"),
                ),
            )
        )

    @staticmethod
    def _identifier(value: str, name: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 240 or any(c.isspace() for c in normalized):
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(
                f"workflow_target_context_capsule_handoff_{name}_invalid",
                f"{name} is invalid.",
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(
                "workflow_target_context_capsule_handoff_idempotency_key_invalid",
                "The idempotency key is invalid.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(
                f"workflow_target_context_capsule_handoff_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value


__all__ = [
    "WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE",
    "WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT",
    "WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_HANDOFF_AUTHORIZATION_LEASE_PRODUCER",
    "WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext",
    "WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseService",
]

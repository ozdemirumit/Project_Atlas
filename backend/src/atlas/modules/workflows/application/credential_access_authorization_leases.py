from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.credential_access_authorization_lease_ports import (
    WorkflowTransportCredentialAccessAuthorizationLeaseError,
    WorkflowTransportCredentialAccessAuthorizationLeaseRepository,
    WorkflowTransportCredentialAccessAuthorizationLeaseRequest,
    WorkflowTransportCredentialAccessAuthorizationLeaseStatus,
)
from atlas.modules.workflows.application.credential_assignment_snapshot_ports import (
    validate_workflow_transport_credential_assignment_snapshot,
)
from atlas.modules.workflows.domain import (
    DeploymentPhysicalTransportCredentialAssignment,
    EventPhysicalTransportCredentialAssignmentSnapshot,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseAuthority,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseEffectiveState,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseState,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationPolicy,
    WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingState,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_credential_access_authorization_policy,
)

WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE = (
    "audience.workflow-physical-transport-credential-accessor"
)
WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT = (
    "service.workflow-physical-transport-credential-accessor"
)
WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESS_AUTHORIZATION_LEASE_PRODUCER = (
    "project-atlas-workflow-physical-transport-credential-access-authorizer"
)


@dataclass(frozen=True, slots=True)
class WorkflowPhysicalTransportCredentialAccessorContext:
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
            raise ValueError("credential-access authorization context contains invalid evidence")
        if self.requested_at.tzinfo is None:
            raise ValueError("credential-access authorization requested_at must be timezone-aware")


class WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService:
    """Issues authority for one future access without opening credential material."""

    def __init__(
        self,
        *,
        authorization_repository: WorkflowTransportCredentialAccessAuthorizationLeaseRepository,
        audit_sink: AuditSink,
        policy: WorkflowEventPhysicalTransportCredentialAccessAuthorizationPolicy | None = None,
    ) -> None:
        self._repository = authorization_repository
        self._audit_sink = audit_sink
        self._policy = (
            policy
            or code_owned_workflow_event_physical_transport_credential_access_authorization_policy()
        )

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def repository(self) -> WorkflowTransportCredentialAccessAuthorizationLeaseRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowEventPhysicalTransportCredentialAccessAuthorizationPolicy:
        return self._policy

    async def authorize(
        self,
        *,
        freshness_admission_id: str,
        freshness_admission_digest: str,
        policy_id: str,
        policy_version: str,
        idempotency_key: str,
        context: WorkflowPhysicalTransportCredentialAccessorContext,
    ) -> WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease:
        await self._require_accessor_workload(context)
        try:
            admission_id = self._identifier(freshness_admission_id, "freshness_admission_id")
            admission_digest = self._digest(
                freshness_admission_digest, "freshness_admission_digest"
            )
            requested_policy_id = self._identifier(policy_id, "policy_id")
            requested_policy_version = self._identifier(policy_version, "policy_version")
            normalized_key = self._idempotency_key(idempotency_key)
        except WorkflowTransportCredentialAccessAuthorizationLeaseError as exc:
            await self._deny(context, result_code=exc.code)

        if (
            requested_policy_id != self._policy.policy_id
            or requested_policy_version != self._policy.policy_version
            or canonical_digest(self._policy.digest_payload()) != self._policy.canonical_digest
            or self._policy.validity_window_seconds != 15
            or self._policy.full_freshness_window_required is not True
            or self._policy.accessor_subject_bound is not True
            or self._policy.single_use_required is not True
        ):
            await self._deny(
                context,
                result_code="workflow_physical_transport_credential_access_authorization_policy_conflict",
                idempotency_key=normalized_key,
            )

        authoritative_now = await self._authoritative_time_or_deny(
            context, idempotency_key=normalized_key
        )
        admission = await self._repository.get_credential_assignment_freshness_admission_by_id(
            freshness_admission_id=admission_id
        )
        if admission is None:
            await self._deny_evidence(context, normalized_key)
        binding = await self._repository.get_credential_assignment_binding_by_id(
            binding_id=admission.physical_transport_credential_assignment_binding_id
        )
        if binding is None:
            await self._deny_evidence(context, normalized_key, admission=admission)
        snapshot = await self._repository.get_credential_assignment_snapshot_by_id(
            snapshot_id=admission.credential_assignment_snapshot_id
        )
        if snapshot is None:
            await self._deny_evidence(context, normalized_key, admission=admission, binding=binding)
        head = await self._repository.get_current_credential_assignment_head(
            assignment_id=admission.assignment_id
        )
        if head is None:
            await self._deny_evidence(
                context,
                normalized_key,
                admission=admission,
                binding=binding,
                snapshot=snapshot,
            )
        try:
            self._validate_chain(
                admission,
                binding=binding,
                snapshot=snapshot,
                head=head,
                scope=context.scope,
                evaluated_at=authoritative_now,
                expected_admission_digest=admission_digest,
            )
        except (ValueError, WorkflowTransportCredentialAccessAuthorizationLeaseError):
            await self._deny_evidence(
                context,
                normalized_key,
                admission=admission,
                binding=binding,
                snapshot=snapshot,
            )

        fingerprint = canonical_digest(
            {
                "accessor_subject_id": context.subject_id,
                "assignment_id": head.assignment_id,
                "assignment_revision": head.assignment_revision,
                "credential_generation": head.credential_generation,
                "freshness_admission_digest": admission_digest,
                "freshness_admission_id": admission_id,
                "rotation_epoch": head.rotation_epoch,
                "scope": context.scope.canonical_value(),
            }
        )
        candidate = self._build_lease(
            admission=admission,
            accessor_subject_id=context.subject_id,
            issued_at=authoritative_now,
        )
        await self._audit(
            context,
            event_kind="intent",
            outcome="requested",
            result_code="workflow_physical_transport_credential_access_authorization_requested",
            idempotency_key=normalized_key,
            lease=candidate,
        )

        async def required_precommit_audit() -> None:
            await self._audit(
                context,
                event_kind="authorization",
                outcome="authorized",
                result_code=(
                    "workflow_physical_transport_credential_access_authorization_"
                    "persistence_authorized"
                ),
                idempotency_key=normalized_key,
                lease=candidate,
            )

        result = await self._repository.authorize_credential_access(
            WorkflowTransportCredentialAccessAuthorizationLeaseRequest(
                expected_freshness_admission_id=admission.freshness_admission_id,
                expected_freshness_admission_digest=admission.canonical_digest,
                expected_freshness_admission_valid_until=admission.valid_until,
                expected_credential_assignment_binding_id=binding.binding_id,
                expected_credential_assignment_binding_digest=binding.canonical_digest,
                expected_credential_assignment_snapshot_id=snapshot.snapshot_id,
                expected_credential_assignment_snapshot_digest=snapshot.canonical_digest,
                expected_assignment_id=head.assignment_id,
                expected_assignment_revision=head.assignment_revision,
                expected_source_assignment_digest=head.canonical_digest,
                expected_credential_generation=head.credential_generation,
                expected_rotation_epoch=head.rotation_epoch,
                expected_assignment_activated_at=head.activated_at,
                expected_assignment_expires_at=head.expires_at,
                expected_assignment_active=head.active,
                expected_assignment_revoked=head.revoked,
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
        if result.status is WorkflowTransportCredentialAccessAuthorizationLeaseStatus.AUTHORIZED:
            if result.lease is None:
                await self._deny_evidence(context, normalized_key)
            self._validate_lease(
                result.lease,
                admission=admission,
                head=head,
                scope=context.scope,
                evaluated_at=authoritative_now,
            )
            await self._audit_committed_result(
                context,
                event_kind="created",
                result_code="workflow_physical_transport_credential_access_authorization_lease_created",
                idempotency_key=normalized_key,
                lease=result.lease,
            )
            return result.lease
        if result.status is WorkflowTransportCredentialAccessAuthorizationLeaseStatus.REPLAY:
            if result.lease is None:
                await self._deny_evidence(context, normalized_key)
            try:
                self._validate_lease(
                    result.lease,
                    admission=admission,
                    head=head,
                    scope=context.scope,
                    evaluated_at=authoritative_now,
                )
            except (ValueError, WorkflowTransportCredentialAccessAuthorizationLeaseError):
                await self._deny_evidence(context, normalized_key, admission=admission)
            await self._audit_committed_result(
                context,
                event_kind="replay",
                result_code="workflow_physical_transport_credential_access_authorization_lease_replayed",
                idempotency_key=normalized_key,
                lease=result.lease,
            )
            return result.lease

        result_codes = {
            WorkflowTransportCredentialAccessAuthorizationLeaseStatus.IDEMPOTENCY_CONFLICT: (
                "workflow_physical_transport_credential_access_authorization_idempotency_conflict"
            ),
            WorkflowTransportCredentialAccessAuthorizationLeaseStatus.EVIDENCE_CONFLICT: (
                "workflow_physical_transport_credential_access_authorization_evidence_conflict"
            ),
            WorkflowTransportCredentialAccessAuthorizationLeaseStatus.ALREADY_AUTHORIZED: (
                "workflow_physical_transport_credential_access_authorization_already_authorized"
            ),
            WorkflowTransportCredentialAccessAuthorizationLeaseStatus.PRECOMMIT_AUDIT_FAILED: (
                "workflow_physical_transport_credential_access_authorization_audit_unavailable"
            ),
        }
        await self._deny(
            context,
            result_code=result_codes[result.status],
            idempotency_key=normalized_key,
            lease=result.lease,
        )

    async def list_leases(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease, ...]:
        if not 1 <= limit <= 256:
            raise WorkflowTransportCredentialAccessAuthorizationLeaseError(
                "workflow_physical_transport_credential_access_authorization_limit_invalid",
                "The credential-access authorization lease limit is invalid.",
            )
        leases = await self._repository.list_credential_access_authorization_leases(
            scope=scope, limit=limit
        )
        for lease in leases:
            self._validate_historical_lease(lease, scope=scope)
        return leases

    def _build_lease(
        self,
        *,
        admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
        accessor_subject_id: str,
        issued_at: datetime,
    ) -> WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease:
        lease_id = (
            "workflow-physical-transport-credential-access-authorization-lease."
            + sha256(
                f"{admission.freshness_admission_id}:{accessor_subject_id}".encode()
            ).hexdigest()[:24]
        )
        values: dict[str, object] = {
            "authorization_lease_id": lease_id,
            "freshness_admission_id": admission.freshness_admission_id,
            "freshness_admission_digest": admission.canonical_digest,
            "physical_transport_credential_assignment_binding_id": (
                admission.physical_transport_credential_assignment_binding_id
            ),
            "physical_transport_credential_assignment_binding_digest": (
                admission.physical_transport_credential_assignment_binding_digest
            ),
            "credential_assignment_snapshot_id": admission.credential_assignment_snapshot_id,
            "credential_assignment_snapshot_digest": (
                admission.credential_assignment_snapshot_digest
            ),
            "assignment_id": admission.assignment_id,
            "assignment_revision": admission.assignment_revision,
            "source_assignment_digest": admission.source_assignment_digest,
            "credential_generation": admission.credential_generation,
            "rotation_epoch": admission.rotation_epoch,
            "assignment_activated_at": admission.assignment_activated_at,
            "assignment_expires_at": admission.assignment_expires_at,
            "assignment_active": admission.assignment_active,
            "assignment_non_revoked": admission.assignment_non_revoked,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "scope": admission.scope,
            "accessor_subject_id": accessor_subject_id,
            "issued_at": issued_at,
            "valid_until": issued_at + timedelta(seconds=15),
            "state": (
                WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseState
            ).AUTHORIZED_UNCONSUMED,
            "authority": (
                WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseAuthority()
            ),
        }
        payload = {
            key: value.canonical_value()
            if isinstance(
                value,
                (
                    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseAuthority,
                    WorkflowScope,
                ),
            )
            else value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(
                value, WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseState
            )
            else value
            for key, value in values.items()
        }
        return WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease(
            **cast(Any, values), canonical_digest=canonical_digest(payload)
        )

    @staticmethod
    def _validate_chain(
        admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
        *,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
        head: DeploymentPhysicalTransportCredentialAssignment,
        scope: WorkflowScope,
        evaluated_at: datetime,
        expected_admission_digest: str,
    ) -> None:
        validate_workflow_transport_credential_assignment_snapshot(snapshot, scope=scope)
        complete_until = evaluated_at + timedelta(seconds=15)
        if (
            admission.scope != scope
            or admission.canonical_digest != expected_admission_digest
            or canonical_digest(admission.digest_payload()) != admission.canonical_digest
            or admission.state.value != "admitted_current"
            or any(value is not False for value in admission.authority.canonical_value().values())
            or binding.scope != scope
            or binding.state
            is not WorkflowEventPhysicalTransportCredentialAssignmentBindingState.BOUND
            or canonical_digest(binding.digest_payload()) != binding.canonical_digest
            or any(value is not False for value in binding.authority.canonical_value().values())
            or binding.binding_id != admission.physical_transport_credential_assignment_binding_id
            or binding.canonical_digest
            != admission.physical_transport_credential_assignment_binding_digest
            or snapshot.scope != scope
            or snapshot.snapshot_id != admission.credential_assignment_snapshot_id
            or snapshot.canonical_digest != admission.credential_assignment_snapshot_digest
            or head.scope != scope
            or canonical_digest(head.digest_payload()) != head.canonical_digest
            or head.assignment_id != admission.assignment_id
            or head.assignment_revision != admission.assignment_revision
            or head.canonical_digest != admission.source_assignment_digest
            or head.credential_generation != admission.credential_generation
            or head.rotation_epoch != admission.rotation_epoch
            or head.activated_at != admission.assignment_activated_at
            or head.expires_at != admission.assignment_expires_at
            or head.active is not True
            or head.revoked is not False
            or not head.activated_at <= evaluated_at < complete_until <= head.expires_at
            or complete_until > admission.valid_until
        ):
            raise WorkflowTransportCredentialAccessAuthorizationLeaseError(
                "workflow_physical_transport_credential_access_authorization_evidence_conflict",
                "Credential-access authorization evidence is invalid.",
            )

    @classmethod
    def _validate_lease(
        cls,
        lease: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
        *,
        admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
        head: DeploymentPhysicalTransportCredentialAssignment,
        scope: WorkflowScope,
        evaluated_at: datetime,
    ) -> None:
        cls._validate_historical_lease(lease, scope=scope)
        if (
            lease.freshness_admission_id != admission.freshness_admission_id
            or lease.freshness_admission_digest != admission.canonical_digest
            or lease.assignment_id != head.assignment_id
            or lease.assignment_revision != head.assignment_revision
            or lease.source_assignment_digest != head.canonical_digest
            or lease.credential_generation != head.credential_generation
            or lease.rotation_epoch != head.rotation_epoch
            or lease.accessor_subject_id != WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT
            or lease.effective_state(evaluated_at=evaluated_at)
            is not (
                WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseEffectiveState
            ).ACTIVE
            or evaluated_at >= admission.valid_until
            or not head.active
            or head.revoked
        ):
            raise WorkflowTransportCredentialAccessAuthorizationLeaseError(
                "workflow_physical_transport_credential_access_authorization_repository_scope_violation",
                "Stored credential-access authorization evidence is invalid.",
            )

    @staticmethod
    def _validate_historical_lease(
        lease: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
        *,
        scope: WorkflowScope,
    ) -> None:
        if (
            lease.scope != scope
            or canonical_digest(lease.digest_payload()) != lease.canonical_digest
            or lease.valid_until - lease.issued_at != timedelta(seconds=15)
            or lease.authority.credential_access_authorized is not True
            or any(
                value is not False
                for name, value in lease.authority.canonical_value().items()
                if name != "credential_access_authorized"
            )
        ):
            raise WorkflowTransportCredentialAccessAuthorizationLeaseError(
                "workflow_physical_transport_credential_access_authorization_repository_scope_violation",
                "Stored credential-access authorization evidence is invalid.",
            )

    async def _authoritative_time_or_deny(
        self,
        context: WorkflowPhysicalTransportCredentialAccessorContext,
        *,
        idempotency_key: str,
    ) -> datetime:
        try:
            value = await self._repository.get_authoritative_time()
            if value.tzinfo is None:
                raise ValueError("repository time must be aware")
            return value
        except Exception:
            await self._deny(
                context,
                result_code=(
                    "workflow_physical_transport_credential_access_authorization_"
                    "authoritative_time_unavailable"
                ),
                idempotency_key=idempotency_key,
            )

    async def _require_accessor_workload(
        self, context: WorkflowPhysicalTransportCredentialAccessorContext
    ) -> None:
        if (
            context.subject_id != WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT
            or context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience
            != WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE
        ):
            await self._deny(
                context,
                result_code=(
                    "workflow_physical_transport_credential_access_authorization_"
                    "accessor_identity_required"
                ),
            )

    async def _audit_committed_result(
        self,
        context: WorkflowPhysicalTransportCredentialAccessorContext,
        *,
        event_kind: str,
        result_code: str,
        idempotency_key: str,
        lease: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
    ) -> None:
        try:
            await self._audit(
                context,
                event_kind=event_kind,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                lease=lease,
            )
        except Exception as exc:
            raise WorkflowTransportCredentialAccessAuthorizationLeaseError(
                "workflow_physical_transport_credential_access_authorization_completion_audit_outcome_uncertain",
                "The authorization lease is committed but completion audit is unavailable.",
            ) from exc

    async def _deny_evidence(
        self,
        context: WorkflowPhysicalTransportCredentialAccessorContext,
        idempotency_key: str,
        *,
        admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission
        | None = None,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding | None = None,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot | None = None,
    ) -> NoReturn:
        await self._deny(
            context,
            result_code="workflow_physical_transport_credential_access_authorization_evidence_conflict",
            idempotency_key=idempotency_key,
        )

    async def _deny(
        self,
        context: WorkflowPhysicalTransportCredentialAccessorContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
        lease: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease | None = None,
    ) -> NoReturn:
        try:
            await self._audit(
                context,
                event_kind="denied",
                outcome="denied",
                result_code=result_code,
                idempotency_key=idempotency_key,
                lease=lease,
            )
        except Exception as exc:
            raise WorkflowTransportCredentialAccessAuthorizationLeaseError(
                "workflow_physical_transport_credential_access_authorization_audit_unavailable",
                "The authorization was denied and required audit is unavailable.",
            ) from exc
        raise WorkflowTransportCredentialAccessAuthorizationLeaseError(
            result_code, "The credential-access authorization request was denied."
        )

    async def _audit(
        self,
        context: WorkflowPhysicalTransportCredentialAccessorContext,
        *,
        event_kind: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        lease: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease | None = None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=f"atlas.workflow.physical-transport-credential-access-authorization.{event_kind}",
                schema_version="1.0",
                producer=WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESS_AUTHORIZATION_LEASE_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.physical-transport-credential-access-authorization-leases.create",
                resource_type="resource.workflow-physical-transport-credential-access-authorization-lease",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "credential-access-authorization-lease",
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
                    (
                        "freshness_admission_id",
                        "none" if lease is None else lease.freshness_admission_id,
                    ),
                    ("credential_access_authority", "true" if lease is not None else "false"),
                    ("credential_resolution_authority", "false"),
                    ("credential_delivery_authority", "false"),
                    ("network_access_authority", "false"),
                    ("execution_authority", "false"),
                    ("infrastructure_mutation_authority", "false"),
                ),
            )
        )

    @staticmethod
    def _identifier(value: str, name: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 240 or any(c.isspace() for c in normalized):
            raise WorkflowTransportCredentialAccessAuthorizationLeaseError(
                f"workflow_physical_transport_credential_access_authorization_{name}_invalid",
                f"{name} is invalid.",
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowTransportCredentialAccessAuthorizationLeaseError(
                "workflow_physical_transport_credential_access_authorization_idempotency_key_invalid",
                "The idempotency key is invalid.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise WorkflowTransportCredentialAccessAuthorizationLeaseError(
                f"workflow_physical_transport_credential_access_authorization_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value


__all__ = [
    "WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE",
    "WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT",
    "WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESS_AUTHORIZATION_LEASE_PRODUCER",
    "WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService",
    "WorkflowPhysicalTransportCredentialAccessorContext",
]

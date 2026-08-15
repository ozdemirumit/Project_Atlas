from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.credential_assignment_snapshot_ports import (
    DeploymentPhysicalTransportCredentialAssignmentRegistry,
    WorkflowTransportCredentialAssignmentSnapshotError,
    WorkflowTransportCredentialAssignmentSnapshotRepository,
    WorkflowTransportCredentialAssignmentSnapshotRequest,
    WorkflowTransportCredentialAssignmentSnapshotStatus,
    WorkflowTransportRouteSnapshotReader,
    validate_workflow_transport_credential_assignment_snapshot,
)
from atlas.modules.workflows.domain import (
    DeploymentPhysicalTransportCredentialAssignment,
    EventPhysicalTransportCredentialAssignmentSnapshot,
    EventPhysicalTransportCredentialAssignmentSnapshotAuthority,
    EventPhysicalTransportCredentialAssignmentSnapshotState,
    EventPhysicalTransportRouteSnapshot,
    EventPhysicalTransportRouteSnapshotState,
    WorkflowScope,
    canonical_digest,
)

WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_AUDIENCE = (
    "audience.workflow-transport-credential-assignment-registry"
)
WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_SUBJECT = (
    "service.workflow-transport-credential-assignment-registry"
)
WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_SNAPSHOT_PRODUCER = (
    "project-atlas-workflow-transport-credential-assignment-registry"
)


@dataclass(frozen=True, slots=True)
class WorkflowTransportCredentialAssignmentRegistryContext:
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
            raise ValueError(
                "credential assignment registry context contains an invalid identifier"
            )
        if self.requested_at.tzinfo is None:
            raise ValueError("credential assignment registry requested_at must be timezone-aware")


class WorkflowTransportCredentialAssignmentSnapshotService:
    """Captures compatible deployment credential metadata without opening a credential."""

    _ASSIGNMENT_FIELDS = (
        "assignment_id",
        "assignment_revision",
        "scope",
        "route_id",
        "route_revision",
        "source_route_digest",
        "credential_requirement_profile_id",
        "credential_requirement_profile_version",
        "credential_requirement_profile_digest",
        "credential_profile_id",
        "credential_profile_version",
        "credential_profile_digest",
        "authentication_mechanism_class",
        "principal_class",
        "privilege_class",
        "target_scope_commitment",
        "credential_generation",
        "rotation_epoch",
        "activated_at",
        "expires_at",
        "broker_policy_id",
        "broker_policy_version",
        "broker_policy_digest",
    )

    def __init__(
        self,
        *,
        credential_assignment_registry: (DeploymentPhysicalTransportCredentialAssignmentRegistry),
        route_snapshot_reader: WorkflowTransportRouteSnapshotReader,
        snapshot_repository: WorkflowTransportCredentialAssignmentSnapshotRepository,
        audit_sink: AuditSink,
    ) -> None:
        self._registry = credential_assignment_registry
        self._route_snapshots = route_snapshot_reader
        self._repository = snapshot_repository
        self._audit_sink = audit_sink

    @property
    def durable(self) -> bool:
        return self._registry.durable and self._route_snapshots.durable and self._repository.durable

    @property
    def repository(self) -> WorkflowTransportCredentialAssignmentSnapshotRepository:
        return self._repository

    async def register(
        self,
        *,
        assignment_id: str,
        assignment_revision: str,
        source_assignment_digest: str,
        idempotency_key: str,
        context: WorkflowTransportCredentialAssignmentRegistryContext,
    ) -> EventPhysicalTransportCredentialAssignmentSnapshot:
        await self._require_registry_workload(context)
        try:
            normalized_assignment_id = self._identifier(assignment_id, "assignment_id")
            normalized_revision = self._identifier(assignment_revision, "assignment_revision")
            normalized_digest = self._digest(source_assignment_digest, "source_assignment_digest")
            normalized_key = self._idempotency_key(idempotency_key)
        except WorkflowTransportCredentialAssignmentSnapshotError as exc:
            await self._deny(context, result_code=exc.code)

        fingerprint = canonical_digest(
            {
                "assignment_id": normalized_assignment_id,
                "assignment_revision": normalized_revision,
                "scope": context.scope.canonical_value(),
                "snapshotter_subject_id": context.subject_id,
                "source_assignment_digest": normalized_digest,
            }
        )
        prior = await self._repository.get_credential_assignment_snapshot_request(
            scope=context.scope,
            snapshotter_subject_id=context.subject_id,
            idempotency_key=normalized_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._deny(
                    context,
                    result_code=(
                        "workflow_transport_credential_assignment_snapshot_idempotency_conflict"
                    ),
                    idempotency_key=normalized_key,
                    snapshot=prior.snapshot,
                )
            await self._validate_historical_or_deny(
                prior.snapshot,
                expected_assignment_id=normalized_assignment_id,
                expected_revision=normalized_revision,
                expected_digest=normalized_digest,
                context=context,
                idempotency_key=normalized_key,
            )
            await self._audit_committed_result(
                context,
                event_kind="replay",
                result_code="workflow_transport_credential_assignment_snapshot_replayed",
                idempotency_key=normalized_key,
                snapshot=prior.snapshot,
            )
            return prior.snapshot

        assignment = await self._registry.get_active_credential_assignment(
            assignment_id=normalized_assignment_id,
            assignment_revision=normalized_revision,
        )
        if assignment is None:
            await self._deny(
                context,
                result_code="workflow_transport_credential_assignment_snapshot_source_not_active",
                idempotency_key=normalized_key,
            )
        try:
            self._validate_source_assignment(
                assignment,
                expected_assignment_id=normalized_assignment_id,
                expected_revision=normalized_revision,
                expected_digest=normalized_digest,
                context=context,
            )
        except WorkflowTransportCredentialAssignmentSnapshotError as exc:
            await self._deny(
                context,
                result_code=exc.code,
                idempotency_key=normalized_key,
                assignment=assignment,
            )

        route = await self._route_snapshots.get_transport_route_snapshot(
            route_id=assignment.route_id,
            route_revision=assignment.route_revision,
        )
        try:
            self._validate_route_compatibility(assignment, route, context=context)
        except WorkflowTransportCredentialAssignmentSnapshotError as exc:
            await self._deny(
                context,
                result_code=exc.code,
                idempotency_key=normalized_key,
                assignment=assignment,
            )
        assert route is not None

        current = await self._repository.get_credential_assignment_snapshot(
            assignment_id=assignment.assignment_id,
            assignment_revision=assignment.assignment_revision,
        )
        if current is not None:
            await self._deny(
                context,
                result_code=(
                    "workflow_transport_credential_assignment_snapshot_competing_identity"
                    if current.snapshotter_subject_id != context.subject_id
                    else "workflow_transport_credential_assignment_snapshot_already_exists"
                ),
                idempotency_key=normalized_key,
                assignment=assignment,
                snapshot=current,
            )

        candidate = self._build_snapshot(
            assignment=assignment,
            route=route,
            snapshotter_subject_id=context.subject_id,
            captured_at=context.requested_at,
        )
        await self._audit(
            context,
            event_kind="intent",
            outcome="authorized",
            result_code=(
                "workflow_transport_credential_assignment_snapshot_persistence_authorized"
            ),
            idempotency_key=normalized_key,
            assignment=assignment,
            snapshot=candidate,
        )

        async def required_precommit_audit() -> None:
            await self._audit(
                context,
                event_kind="commit-authorization",
                outcome="authorized",
                result_code=("workflow_transport_credential_assignment_snapshot_commit_authorized"),
                idempotency_key=normalized_key,
                assignment=assignment,
                snapshot=candidate,
            )

        result = await self._repository.snapshot_credential_assignment(
            WorkflowTransportCredentialAssignmentSnapshotRequest(
                expected_source_assignment_id=normalized_assignment_id,
                expected_source_assignment_revision=normalized_revision,
                expected_source_assignment_digest=normalized_digest,
                scope=context.scope,
                snapshotter_subject_id=context.subject_id,
                requested_at=context.requested_at,
                candidate=candidate,
                idempotency_key=normalized_key,
                request_fingerprint=fingerprint,
                required_precommit_audit=required_precommit_audit,
            )
        )
        if (
            result.status is WorkflowTransportCredentialAssignmentSnapshotStatus.SNAPSHOTTED
            and result.snapshot is not None
        ):
            await self._validate_or_deny(
                result.snapshot,
                assignment=assignment,
                route=route,
                context=context,
                idempotency_key=normalized_key,
            )
            await self._audit_committed_result(
                context,
                event_kind="completion",
                result_code="workflow_transport_credential_assignment_snapshot_created",
                idempotency_key=normalized_key,
                assignment=assignment,
                snapshot=result.snapshot,
            )
            return result.snapshot
        if (
            result.status is WorkflowTransportCredentialAssignmentSnapshotStatus.REPLAY
            and result.snapshot is not None
        ):
            await self._validate_historical_or_deny(
                result.snapshot,
                expected_assignment_id=normalized_assignment_id,
                expected_revision=normalized_revision,
                expected_digest=normalized_digest,
                context=context,
                idempotency_key=normalized_key,
            )
            await self._audit_committed_result(
                context,
                event_kind="replay",
                result_code="workflow_transport_credential_assignment_snapshot_replayed",
                idempotency_key=normalized_key,
                assignment=assignment,
                snapshot=result.snapshot,
            )
            return result.snapshot

        result_code = {
            WorkflowTransportCredentialAssignmentSnapshotStatus.IDEMPOTENCY_CONFLICT: (
                "workflow_transport_credential_assignment_snapshot_idempotency_conflict"
            ),
            WorkflowTransportCredentialAssignmentSnapshotStatus.SOURCE_CONFLICT: (
                "workflow_transport_credential_assignment_snapshot_source_conflict"
            ),
            WorkflowTransportCredentialAssignmentSnapshotStatus.ALREADY_SNAPSHOTTED: (
                "workflow_transport_credential_assignment_snapshot_already_exists"
            ),
            WorkflowTransportCredentialAssignmentSnapshotStatus.PRECOMMIT_AUDIT_FAILED: (
                "workflow_transport_credential_assignment_snapshot_precommit_audit_failed"
            ),
        }.get(
            result.status,
            "workflow_transport_credential_assignment_snapshot_repository_contract_violation",
        )
        await self._deny(
            context,
            result_code=result_code,
            idempotency_key=normalized_key,
            assignment=assignment,
            snapshot=result.snapshot,
        )

    @staticmethod
    def _validate_source_assignment(
        assignment: DeploymentPhysicalTransportCredentialAssignment,
        *,
        expected_assignment_id: str,
        expected_revision: str,
        expected_digest: str,
        context: WorkflowTransportCredentialAssignmentRegistryContext,
    ) -> None:
        if (
            assignment.assignment_id != expected_assignment_id
            or assignment.assignment_revision != expected_revision
            or assignment.canonical_digest != expected_digest
            or canonical_digest(assignment.digest_payload()) != assignment.canonical_digest
            or assignment.scope != context.scope
            or not assignment.active
            or assignment.revoked
            or not assignment.activated_at <= context.requested_at < assignment.expires_at
            or assignment.privilege_class != "read-only"
            or assignment.credential_generation < 1
            or assignment.rotation_epoch < 1
        ):
            raise WorkflowTransportCredentialAssignmentSnapshotError(
                "workflow_transport_credential_assignment_snapshot_source_conflict",
                "The active deployment credential assignment no longer matches the request.",
            )

    @staticmethod
    def _validate_route_compatibility(
        assignment: DeploymentPhysicalTransportCredentialAssignment,
        route: EventPhysicalTransportRouteSnapshot | None,
        *,
        context: WorkflowTransportCredentialAssignmentRegistryContext,
    ) -> None:
        if (
            route is None
            or route.state is not EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED
            or route.scope != context.scope
            or route.route_id != assignment.route_id
            or route.route_revision != assignment.route_revision
            or route.source_route_digest != assignment.source_route_digest
            or route.credential_requirement_profile_id
            != assignment.credential_requirement_profile_id
            or route.credential_requirement_profile_version
            != assignment.credential_requirement_profile_version
            or route.credential_requirement_profile_digest
            != assignment.credential_requirement_profile_digest
            or route.authentication_mechanism_class != assignment.authentication_mechanism_class
            or route.principal_class != assignment.principal_class
            or canonical_digest(route.digest_payload()) != route.canonical_digest
            or any(route.authority.canonical_value().values())
        ):
            raise WorkflowTransportCredentialAssignmentSnapshotError(
                "workflow_transport_credential_assignment_snapshot_route_incompatible",
                "The authoritative assignment is incompatible with route evidence.",
            )

    @classmethod
    def _build_snapshot(
        cls,
        *,
        assignment: DeploymentPhysicalTransportCredentialAssignment,
        route: EventPhysicalTransportRouteSnapshot,
        snapshotter_subject_id: str,
        captured_at: datetime,
    ) -> EventPhysicalTransportCredentialAssignmentSnapshot:
        snapshot_id = (
            "event-physical-transport-credential-assignment-snapshot."
            + sha256(
                (
                    f"{assignment.assignment_id}:{assignment.assignment_revision}:"
                    f"{assignment.canonical_digest}"
                ).encode()
            ).hexdigest()[:24]
        )
        values: dict[str, object] = {
            "snapshot_id": snapshot_id,
            **{name: getattr(assignment, name) for name in cls._ASSIGNMENT_FIELDS},
            "source_assignment_digest": assignment.canonical_digest,
            "route_snapshot_id": route.snapshot_id,
            "source_non_revoked": not assignment.revoked,
            "snapshotter_subject_id": snapshotter_subject_id,
            "captured_at": captured_at,
            "state": EventPhysicalTransportCredentialAssignmentSnapshotState.SNAPSHOTTED,
            "authority": EventPhysicalTransportCredentialAssignmentSnapshotAuthority(),
        }
        digest_payload = {
            key: value.canonical_value()
            if isinstance(
                value,
                (
                    EventPhysicalTransportCredentialAssignmentSnapshotAuthority,
                    WorkflowScope,
                ),
            )
            else value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, EventPhysicalTransportCredentialAssignmentSnapshotState)
            else value
            for key, value in values.items()
        }
        return EventPhysicalTransportCredentialAssignmentSnapshot(
            **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
        )

    async def _validate_or_deny(
        self,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
        *,
        assignment: DeploymentPhysicalTransportCredentialAssignment,
        route: EventPhysicalTransportRouteSnapshot,
        context: WorkflowTransportCredentialAssignmentRegistryContext,
        idempotency_key: str,
    ) -> None:
        try:
            self._validate_snapshot(snapshot, assignment=assignment, route=route, context=context)
        except WorkflowTransportCredentialAssignmentSnapshotError as exc:
            await self._deny(
                context,
                result_code=exc.code,
                idempotency_key=idempotency_key,
                assignment=assignment,
                snapshot=snapshot,
            )

    async def _validate_historical_or_deny(
        self,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
        *,
        expected_assignment_id: str,
        expected_revision: str,
        expected_digest: str,
        context: WorkflowTransportCredentialAssignmentRegistryContext,
        idempotency_key: str,
    ) -> None:
        try:
            self._validate_historical_snapshot(
                snapshot,
                expected_assignment_id=expected_assignment_id,
                expected_revision=expected_revision,
                expected_digest=expected_digest,
                context=context,
            )
        except WorkflowTransportCredentialAssignmentSnapshotError as exc:
            await self._deny(
                context,
                result_code=exc.code,
                idempotency_key=idempotency_key,
                snapshot=snapshot,
            )

    @staticmethod
    def _validate_historical_snapshot(
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
        *,
        expected_assignment_id: str,
        expected_revision: str,
        expected_digest: str,
        context: WorkflowTransportCredentialAssignmentRegistryContext,
    ) -> None:
        validate_workflow_transport_credential_assignment_snapshot(
            snapshot,
            scope=context.scope,
        )
        expected_id = (
            "event-physical-transport-credential-assignment-snapshot."
            + sha256(
                f"{expected_assignment_id}:{expected_revision}:{expected_digest}".encode()
            ).hexdigest()[:24]
        )
        if (
            snapshot.snapshot_id != expected_id
            or snapshot.assignment_id != expected_assignment_id
            or snapshot.assignment_revision != expected_revision
            or snapshot.source_assignment_digest != expected_digest
            or snapshot.snapshotter_subject_id != context.subject_id
            or snapshot.captured_at > context.requested_at
        ):
            raise WorkflowTransportCredentialAssignmentSnapshotError(
                "workflow_transport_credential_assignment_snapshot_repository_scope_violation",
                "The repository returned invalid historical credential assignment evidence.",
            )

    @classmethod
    def _validate_snapshot(
        cls,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
        *,
        assignment: DeploymentPhysicalTransportCredentialAssignment,
        route: EventPhysicalTransportRouteSnapshot,
        context: WorkflowTransportCredentialAssignmentRegistryContext,
    ) -> None:
        expected_id = (
            "event-physical-transport-credential-assignment-snapshot."
            + sha256(
                (
                    f"{assignment.assignment_id}:{assignment.assignment_revision}:"
                    f"{assignment.canonical_digest}"
                ).encode()
            ).hexdigest()[:24]
        )
        expected_fields = {name: getattr(assignment, name) for name in cls._ASSIGNMENT_FIELDS}
        if (
            snapshot.snapshot_id != expected_id
            or snapshot.source_assignment_digest != assignment.canonical_digest
            or snapshot.route_snapshot_id != route.snapshot_id
            or any(getattr(snapshot, name) != value for name, value in expected_fields.items())
            or snapshot.scope != context.scope
            or snapshot.snapshotter_subject_id != context.subject_id
            or snapshot.captured_at > context.requested_at
            or snapshot.source_non_revoked is not True
            or snapshot.state
            is not EventPhysicalTransportCredentialAssignmentSnapshotState.SNAPSHOTTED
            or canonical_digest(snapshot.digest_payload()) != snapshot.canonical_digest
            or any(snapshot.authority.canonical_value().values())
            or snapshot.grants_endpoint_resolution_authority
            or snapshot.grants_credential_access_authority
            or snapshot.grants_network_access_authority
            or snapshot.grants_readiness_probe_authority
            or snapshot.grants_publication_authority
            or snapshot.grants_delivery_authority
            or snapshot.grants_dispatch_authority
            or snapshot.grants_execution_authority
        ):
            raise WorkflowTransportCredentialAssignmentSnapshotError(
                "workflow_transport_credential_assignment_snapshot_repository_scope_violation",
                "The repository returned incorrectly scoped credential assignment evidence.",
            )

    async def _require_registry_workload(
        self, context: WorkflowTransportCredentialAssignmentRegistryContext
    ) -> None:
        if (
            context.subject_id != WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_SUBJECT
            or context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience
            != WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_AUDIENCE
        ):
            await self._deny(
                context,
                result_code=(
                    "workflow_transport_credential_assignment_snapshot_registry_identity_required"
                ),
            )

    async def _audit_committed_result(
        self,
        context: WorkflowTransportCredentialAssignmentRegistryContext,
        *,
        event_kind: str,
        result_code: str,
        idempotency_key: str,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
        assignment: DeploymentPhysicalTransportCredentialAssignment | None = None,
    ) -> None:
        try:
            await self._audit(
                context,
                event_kind=event_kind,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                assignment=assignment,
                snapshot=snapshot,
            )
        except Exception as exc:
            raise WorkflowTransportCredentialAssignmentSnapshotError(
                "workflow_transport_credential_assignment_snapshot_completion_audit_outcome_uncertain",
                "The immutable snapshot is committed but its completion audit is unavailable.",
            ) from exc

    async def _deny(
        self,
        context: WorkflowTransportCredentialAssignmentRegistryContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
        assignment: DeploymentPhysicalTransportCredentialAssignment | None = None,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot | None = None,
    ) -> NoReturn:
        await self._audit(
            context,
            event_kind="denied",
            outcome="denied",
            result_code=result_code,
            idempotency_key=idempotency_key,
            assignment=assignment,
            snapshot=snapshot,
        )
        raise WorkflowTransportCredentialAssignmentSnapshotError(
            result_code,
            "The workflow transport credential assignment snapshot request was denied.",
        )

    async def _audit(
        self,
        context: WorkflowTransportCredentialAssignmentRegistryContext,
        *,
        event_kind: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        assignment: DeploymentPhysicalTransportCredentialAssignment | None,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot | None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=(
                    f"atlas.workflow.transport-credential-assignment-snapshot.{event_kind}"
                ),
                schema_version="1.0",
                producer=WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_SNAPSHOT_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.transport-credential-assignments.snapshot",
                resource_type=("resource.workflow-transport-credential-assignment-snapshot"),
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-transport-credential-assignment-snapshot",
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    (
                        "assignment_id",
                        "none" if assignment is None else assignment.assignment_id,
                    ),
                    ("snapshot_id", "none" if snapshot is None else snapshot.snapshot_id),
                    ("endpoint_resolution_authority", "false"),
                    ("protected_artifact_access_authority", "false"),
                    ("credential_selection_authority", "false"),
                    ("credential_access_authority", "false"),
                    ("credential_brokerage_authority", "false"),
                    ("credential_resolution_authority", "false"),
                    ("credential_delivery_authority", "false"),
                    ("network_access_authority", "false"),
                    ("readiness_probe_authority", "false"),
                    ("publication_authority", "false"),
                    ("delivery_authority", "false"),
                    ("dispatch_authority", "false"),
                    ("execution_authority", "false"),
                    ("infrastructure_mutation_authority", "false"),
                ),
            )
        )

    @staticmethod
    def _identifier(value: str, name: str) -> str:
        normalized = value.strip()
        if (
            not normalized
            or len(normalized) > 240
            or any(character.isspace() for character in normalized)
        ):
            raise WorkflowTransportCredentialAssignmentSnapshotError(
                f"workflow_transport_credential_assignment_snapshot_{name}_invalid",
                f"{name} is invalid.",
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowTransportCredentialAssignmentSnapshotError(
                "workflow_transport_credential_assignment_snapshot_idempotency_key_invalid",
                "The idempotency key is invalid.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise WorkflowTransportCredentialAssignmentSnapshotError(
                f"workflow_transport_credential_assignment_snapshot_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value


__all__ = [
    "WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_AUDIENCE",
    "WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_SUBJECT",
    "WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_SNAPSHOT_PRODUCER",
    "WorkflowTransportCredentialAssignmentRegistryContext",
    "WorkflowTransportCredentialAssignmentSnapshotService",
]

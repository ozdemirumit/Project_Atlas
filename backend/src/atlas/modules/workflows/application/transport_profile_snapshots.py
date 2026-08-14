from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.transport_profile_snapshot_ports import (
    DeploymentEventTransportProfileRegistry,
    WorkflowTransportProfileSnapshotError,
    WorkflowTransportProfileSnapshotRepository,
    WorkflowTransportProfileSnapshotRequest,
    WorkflowTransportProfileSnapshotStatus,
)
from atlas.modules.workflows.domain import (
    DeploymentEventTransportProfile,
    EventPhysicalTransportProfileSnapshot,
    EventPhysicalTransportProfileSnapshotAuthority,
    EventPhysicalTransportProfileSnapshotState,
    WorkflowScope,
    canonical_digest,
)

WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE = "audience.workflow-transport-profile-registry"
WORKFLOW_TRANSPORT_PROFILE_SNAPSHOT_PRODUCER = "project-atlas-workflow-transport-profile-registry"


@dataclass(frozen=True, slots=True)
class WorkflowTransportProfileRegistryContext:
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
            raise ValueError("transport profile registry context contains an invalid identifier")
        if self.requested_at.tzinfo is None:
            raise ValueError("transport profile registry requested_at must be timezone-aware")


class WorkflowTransportProfileSnapshotService:
    """Captures server-owned transport capabilities without selecting or probing a route."""

    def __init__(
        self,
        *,
        transport_profile_registry: DeploymentEventTransportProfileRegistry,
        snapshot_repository: WorkflowTransportProfileSnapshotRepository,
        audit_sink: AuditSink,
    ) -> None:
        self._registry = transport_profile_registry
        self._repository = snapshot_repository
        self._audit_sink = audit_sink

    @property
    def durable(self) -> bool:
        return self._registry.durable and self._repository.durable

    @property
    def repository(self) -> WorkflowTransportProfileSnapshotRepository:
        return self._repository

    async def register(
        self,
        *,
        transport_profile_id: str,
        transport_profile_revision: str,
        source_profile_digest: str,
        idempotency_key: str,
        context: WorkflowTransportProfileRegistryContext,
    ) -> EventPhysicalTransportProfileSnapshot:
        await self._require_registry_workload(context)
        try:
            normalized_profile_id = self._identifier(transport_profile_id, "transport_profile_id")
            normalized_revision = self._identifier(
                transport_profile_revision, "transport_profile_revision"
            )
            normalized_digest = self._digest(source_profile_digest, "source_profile_digest")
            normalized_key = self._idempotency_key(idempotency_key)
        except WorkflowTransportProfileSnapshotError as exc:
            await self._deny(context, result_code=exc.code)

        profile = await self._registry.get_active_transport_profile(
            transport_profile_id=normalized_profile_id,
            transport_profile_revision=normalized_revision,
        )
        if profile is None or not profile.active:
            await self._deny(
                context,
                result_code="workflow_transport_profile_snapshot_source_not_active",
                idempotency_key=normalized_key,
            )
        try:
            self._validate_source_profile(
                profile,
                expected_profile_id=normalized_profile_id,
                expected_revision=normalized_revision,
                expected_digest=normalized_digest,
                context=context,
            )
        except WorkflowTransportProfileSnapshotError as exc:
            await self._deny(
                context,
                result_code=exc.code,
                idempotency_key=normalized_key,
                profile=profile,
            )

        fingerprint = canonical_digest(
            {
                "scope": context.scope.canonical_value(),
                "snapshotter_subject_id": context.subject_id,
                "source_profile_digest": normalized_digest,
                "transport_profile_id": normalized_profile_id,
                "transport_profile_revision": normalized_revision,
            }
        )
        prior = await self._repository.get_transport_profile_snapshot_request(
            scope=context.scope,
            snapshotter_subject_id=context.subject_id,
            idempotency_key=normalized_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._deny(
                    context,
                    result_code="workflow_transport_profile_snapshot_idempotency_conflict",
                    idempotency_key=normalized_key,
                    profile=profile,
                    snapshot=prior.snapshot,
                )
            await self._validate_or_deny(
                prior.snapshot,
                profile=profile,
                context=context,
                idempotency_key=normalized_key,
            )
            await self._audit(
                context,
                outcome="succeeded",
                result_code="workflow_transport_profile_snapshot_replayed",
                idempotency_key=normalized_key,
                profile=profile,
                snapshot=prior.snapshot,
            )
            return prior.snapshot

        current = await self._repository.get_transport_profile_snapshot(
            transport_profile_id=profile.transport_profile_id,
            transport_profile_revision=profile.transport_profile_revision,
        )
        if current is not None:
            await self._deny(
                context,
                result_code=(
                    "workflow_transport_profile_snapshot_competing_identity"
                    if current.snapshotter_subject_id != context.subject_id
                    else "workflow_transport_profile_snapshot_already_exists"
                ),
                idempotency_key=normalized_key,
                profile=profile,
                snapshot=current,
            )

        candidate = self._build_snapshot(
            profile=profile,
            snapshotter_subject_id=context.subject_id,
            captured_at=context.requested_at,
        )
        await self._audit(
            context,
            outcome="succeeded",
            result_code="workflow_transport_profile_snapshot_authorized",
            idempotency_key=normalized_key,
            profile=profile,
            snapshot=candidate,
        )
        result = await self._repository.snapshot_transport_profile(
            WorkflowTransportProfileSnapshotRequest(
                expected_source_profile_id=normalized_profile_id,
                expected_source_profile_revision=normalized_revision,
                expected_source_profile_digest=normalized_digest,
                scope=context.scope,
                snapshotter_subject_id=context.subject_id,
                requested_at=context.requested_at,
                candidate=candidate,
                idempotency_key=normalized_key,
                request_fingerprint=fingerprint,
            )
        )
        if (
            result.status
            in {
                WorkflowTransportProfileSnapshotStatus.SNAPSHOTTED,
                WorkflowTransportProfileSnapshotStatus.REPLAY,
            }
            and result.snapshot is not None
        ):
            await self._validate_or_deny(
                result.snapshot,
                profile=profile,
                context=context,
                idempotency_key=normalized_key,
            )
            return result.snapshot

        result_code = {
            WorkflowTransportProfileSnapshotStatus.IDEMPOTENCY_CONFLICT: (
                "workflow_transport_profile_snapshot_idempotency_conflict"
            ),
            WorkflowTransportProfileSnapshotStatus.SOURCE_CONFLICT: (
                "workflow_transport_profile_snapshot_source_conflict"
            ),
            WorkflowTransportProfileSnapshotStatus.ALREADY_SNAPSHOTTED: (
                "workflow_transport_profile_snapshot_already_exists"
            ),
        }.get(
            result.status,
            "workflow_transport_profile_snapshot_repository_contract_violation",
        )
        await self._deny(
            context,
            result_code=result_code,
            idempotency_key=normalized_key,
            profile=profile,
            snapshot=result.snapshot,
        )

    @staticmethod
    def _validate_source_profile(
        profile: DeploymentEventTransportProfile,
        *,
        expected_profile_id: str,
        expected_revision: str,
        expected_digest: str,
        context: WorkflowTransportProfileRegistryContext,
    ) -> None:
        if (
            profile.transport_profile_id != expected_profile_id
            or profile.transport_profile_revision != expected_revision
            or profile.canonical_digest != expected_digest
            or profile.scope != context.scope
            or not profile.active
        ):
            raise WorkflowTransportProfileSnapshotError(
                "workflow_transport_profile_snapshot_source_conflict",
                "The active deployment transport profile no longer matches the exact request.",
            )

    @staticmethod
    def _build_snapshot(
        *,
        profile: DeploymentEventTransportProfile,
        snapshotter_subject_id: str,
        captured_at: datetime,
    ) -> EventPhysicalTransportProfileSnapshot:
        snapshot_id = (
            "event-physical-transport-profile-snapshot."
            + sha256(
                f"{profile.transport_profile_id}:{profile.transport_profile_revision}:"
                f"{profile.canonical_digest}".encode()
            ).hexdigest()[:24]
        )
        values: dict[str, object] = {
            "snapshot_id": snapshot_id,
            "transport_profile_id": profile.transport_profile_id,
            "transport_profile_revision": profile.transport_profile_revision,
            "source_profile_digest": profile.canonical_digest,
            "deployment_release_id": profile.deployment_release_id,
            "deployment_profile": profile.deployment_profile,
            "scope": profile.scope,
            "transport_resource_id": profile.transport_resource_id,
            "transport_resource_digest": profile.transport_resource_digest,
            "transport_implementation_id": profile.transport_implementation_id,
            "transport_implementation_version": profile.transport_implementation_version,
            "adapter_contract_id": profile.adapter_contract_id,
            "adapter_contract_version": profile.adapter_contract_version,
            "adapter_contract_digest": profile.adapter_contract_digest,
            "supported_event_contracts": profile.supported_event_contracts,
            "supported_classifications": profile.supported_classifications,
            "supported_representations": profile.supported_representations,
            "supported_encodings": profile.supported_encodings,
            "supported_delivery_semantics": profile.supported_delivery_semantics,
            "durable_delivery_supported": profile.durable_delivery_supported,
            "supported_ordering_key_kinds": profile.supported_ordering_key_kinds,
            "supported_retention_classes": profile.supported_retention_classes,
            "maximum_message_byte_count": profile.maximum_message_byte_count,
            "transport_encryption_required": profile.transport_encryption_required,
            "restricted_network_supported": profile.restricted_network_supported,
            "snapshotter_subject_id": snapshotter_subject_id,
            "captured_at": captured_at,
            "state": EventPhysicalTransportProfileSnapshotState.SNAPSHOTTED,
            "authority": EventPhysicalTransportProfileSnapshotAuthority(),
        }
        digest_payload = {
            key: value.canonical_value()
            if isinstance(value, (EventPhysicalTransportProfileSnapshotAuthority, WorkflowScope))
            else value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, EventPhysicalTransportProfileSnapshotState)
            else value
            for key, value in values.items()
        }
        return EventPhysicalTransportProfileSnapshot(
            **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
        )

    async def _validate_or_deny(
        self,
        snapshot: EventPhysicalTransportProfileSnapshot,
        *,
        profile: DeploymentEventTransportProfile,
        context: WorkflowTransportProfileRegistryContext,
        idempotency_key: str,
    ) -> None:
        try:
            self._validate_snapshot(snapshot, profile=profile, context=context)
        except WorkflowTransportProfileSnapshotError as exc:
            await self._deny(
                context,
                result_code=exc.code,
                idempotency_key=idempotency_key,
                profile=profile,
                snapshot=snapshot,
            )

    @staticmethod
    def _validate_snapshot(
        snapshot: EventPhysicalTransportProfileSnapshot,
        *,
        profile: DeploymentEventTransportProfile,
        context: WorkflowTransportProfileRegistryContext,
    ) -> None:
        expected_id = (
            "event-physical-transport-profile-snapshot."
            + sha256(
                f"{profile.transport_profile_id}:{profile.transport_profile_revision}:"
                f"{profile.canonical_digest}".encode()
            ).hexdigest()[:24]
        )
        profile_fields = (
            "transport_profile_id",
            "transport_profile_revision",
            "deployment_release_id",
            "deployment_profile",
            "scope",
            "transport_resource_id",
            "transport_resource_digest",
            "transport_implementation_id",
            "transport_implementation_version",
            "adapter_contract_id",
            "adapter_contract_version",
            "adapter_contract_digest",
            "supported_event_contracts",
            "supported_classifications",
            "supported_representations",
            "supported_encodings",
            "supported_delivery_semantics",
            "durable_delivery_supported",
            "supported_ordering_key_kinds",
            "supported_retention_classes",
            "maximum_message_byte_count",
            "transport_encryption_required",
            "restricted_network_supported",
        )
        if (
            snapshot.snapshot_id != expected_id
            or snapshot.source_profile_digest != profile.canonical_digest
            or not all(getattr(snapshot, name) == getattr(profile, name) for name in profile_fields)
            or snapshot.scope != context.scope
            or snapshot.snapshotter_subject_id != context.subject_id
            or snapshot.captured_at > context.requested_at
            or snapshot.state is not EventPhysicalTransportProfileSnapshotState.SNAPSHOTTED
            or any(snapshot.authority.canonical_value().values())
            or snapshot.grants_route_selection_authority
            or snapshot.grants_publication_authority
            or snapshot.grants_delivery_authority
            or snapshot.grants_dispatch_authority
            or snapshot.grants_execution_authority
        ):
            raise WorkflowTransportProfileSnapshotError(
                "workflow_transport_profile_snapshot_repository_scope_violation",
                "The repository returned incorrectly scoped transport capability evidence.",
            )

    async def _require_registry_workload(
        self, context: WorkflowTransportProfileRegistryContext
    ) -> None:
        if (
            context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience != WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE
        ):
            await self._deny(
                context,
                result_code="workflow_transport_profile_snapshot_registry_identity_required",
            )

    async def _deny(
        self,
        context: WorkflowTransportProfileRegistryContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
        profile: DeploymentEventTransportProfile | None = None,
        snapshot: EventPhysicalTransportProfileSnapshot | None = None,
    ) -> NoReturn:
        await self._audit(
            context,
            outcome="denied",
            result_code=result_code,
            idempotency_key=idempotency_key,
            profile=profile,
            snapshot=snapshot,
        )
        raise WorkflowTransportProfileSnapshotError(
            result_code, "The workflow transport profile snapshot request was denied."
        )

    async def _audit(
        self,
        context: WorkflowTransportProfileRegistryContext,
        *,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        profile: DeploymentEventTransportProfile | None,
        snapshot: EventPhysicalTransportProfileSnapshot | None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=(
                    "atlas.workflow.transport-profile-snapshot.succeeded"
                    if outcome == "succeeded"
                    else "atlas.workflow.transport-profile-snapshot.denied"
                ),
                schema_version="1.0",
                producer=WORKFLOW_TRANSPORT_PROFILE_SNAPSHOT_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.transport-profiles.snapshot",
                resource_type="resource.workflow-transport-profile-snapshot",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-transport-profile-snapshot",
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    (
                        "transport_profile_id",
                        "none" if profile is None else profile.transport_profile_id,
                    ),
                    ("snapshot_id", "none" if snapshot is None else snapshot.snapshot_id),
                    ("route_selection_authority", "false"),
                    ("publication_authority", "false"),
                    ("delivery_authority", "false"),
                    ("dispatch_authority", "false"),
                    ("execution_authority", "false"),
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
            raise WorkflowTransportProfileSnapshotError(
                f"workflow_transport_profile_snapshot_{name}_invalid",
                f"{name} is invalid.",
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowTransportProfileSnapshotError(
                "workflow_transport_profile_snapshot_idempotency_key_invalid",
                "The idempotency key is invalid.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise WorkflowTransportProfileSnapshotError(
                f"workflow_transport_profile_snapshot_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value


__all__ = [
    "WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE",
    "WORKFLOW_TRANSPORT_PROFILE_SNAPSHOT_PRODUCER",
    "WorkflowTransportProfileRegistryContext",
    "WorkflowTransportProfileSnapshotService",
]

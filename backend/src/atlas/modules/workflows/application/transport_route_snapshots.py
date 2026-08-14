from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.transport_route_snapshot_ports import (
    DeploymentEventTransportRouteRegistry,
    WorkflowTransportRouteSnapshotError,
    WorkflowTransportRouteSnapshotRepository,
    WorkflowTransportRouteSnapshotRequest,
    WorkflowTransportRouteSnapshotStatus,
)
from atlas.modules.workflows.domain import (
    DeploymentEventTransportRoute,
    EventPhysicalTransportRouteSnapshot,
    EventPhysicalTransportRouteSnapshotAuthority,
    EventPhysicalTransportRouteSnapshotState,
    WorkflowScope,
    canonical_digest,
)

WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE = "audience.workflow-transport-route-registry"
WORKFLOW_TRANSPORT_ROUTE_SNAPSHOT_PRODUCER = "project-atlas-workflow-transport-route-registry"


@dataclass(frozen=True, slots=True)
class WorkflowTransportRouteRegistryContext:
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
            raise ValueError("transport route registry context contains an invalid identifier")
        if self.requested_at.tzinfo is None:
            raise ValueError("transport route registry requested_at must be timezone-aware")


class WorkflowTransportRouteSnapshotService:
    """Captures opaque server-owned routes without resolving or using them."""

    _ROUTE_FIELDS = (
        "route_id",
        "route_revision",
        "route_set_id",
        "route_set_revision",
        "selection_epoch_id",
        "selection_epoch_revision",
        "deployment_release_id",
        "deployment_profile",
        "scope",
        "transport_profile_id",
        "transport_profile_revision",
        "transport_resource_id",
        "transport_resource_digest",
        "transport_implementation_id",
        "transport_implementation_version",
        "adapter_contract_id",
        "adapter_contract_version",
        "adapter_contract_digest",
        "route_kind",
        "endpoint_set_id",
        "endpoint_set_revision",
        "destination_id",
        "destination_revision",
        "routing_contract_id",
        "routing_contract_revision",
        "private_route_descriptor_commitment",
        "transport_security_policy_id",
        "transport_security_policy_version",
        "transport_security_policy_digest",
        "minimum_tls_version",
        "server_authentication_required",
        "client_authentication_required",
        "plaintext_fallback_prohibited",
        "network_policy_id",
        "network_policy_version",
        "network_policy_digest",
        "source_zone_class",
        "destination_zone_class",
        "restricted_network_enforced",
        "public_egress_prohibited",
        "proxy_mode",
        "credential_requirement_profile_id",
        "credential_requirement_profile_version",
        "credential_requirement_profile_digest",
        "authentication_mechanism_class",
        "principal_class",
    )

    def __init__(
        self,
        *,
        transport_route_registry: DeploymentEventTransportRouteRegistry,
        snapshot_repository: WorkflowTransportRouteSnapshotRepository,
        audit_sink: AuditSink,
    ) -> None:
        self._registry = transport_route_registry
        self._repository = snapshot_repository
        self._audit_sink = audit_sink

    @property
    def durable(self) -> bool:
        return self._registry.durable and self._repository.durable

    @property
    def repository(self) -> WorkflowTransportRouteSnapshotRepository:
        return self._repository

    async def register(
        self,
        *,
        route_id: str,
        route_revision: str,
        source_route_digest: str,
        idempotency_key: str,
        context: WorkflowTransportRouteRegistryContext,
    ) -> EventPhysicalTransportRouteSnapshot:
        await self._require_registry_workload(context)
        try:
            normalized_route_id = self._identifier(route_id, "route_id")
            normalized_revision = self._identifier(route_revision, "route_revision")
            normalized_digest = self._digest(source_route_digest, "source_route_digest")
            normalized_key = self._idempotency_key(idempotency_key)
        except WorkflowTransportRouteSnapshotError as exc:
            await self._deny(context, result_code=exc.code)

        route = await self._registry.get_active_transport_route(
            route_id=normalized_route_id,
            route_revision=normalized_revision,
        )
        if route is None or not route.active:
            await self._deny(
                context,
                result_code="workflow_transport_route_snapshot_source_not_active",
                idempotency_key=normalized_key,
            )
        try:
            self._validate_source_route(
                route,
                expected_route_id=normalized_route_id,
                expected_revision=normalized_revision,
                expected_digest=normalized_digest,
                context=context,
            )
        except WorkflowTransportRouteSnapshotError as exc:
            await self._deny(
                context,
                result_code=exc.code,
                idempotency_key=normalized_key,
                route=route,
            )

        fingerprint = canonical_digest(
            {
                "route_id": normalized_route_id,
                "route_revision": normalized_revision,
                "scope": context.scope.canonical_value(),
                "snapshotter_subject_id": context.subject_id,
                "source_route_digest": normalized_digest,
            }
        )
        prior = await self._repository.get_transport_route_snapshot_request(
            scope=context.scope,
            snapshotter_subject_id=context.subject_id,
            idempotency_key=normalized_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._deny(
                    context,
                    result_code="workflow_transport_route_snapshot_idempotency_conflict",
                    idempotency_key=normalized_key,
                    route=route,
                    snapshot=prior.snapshot,
                )
            await self._validate_or_deny(
                prior.snapshot,
                route=route,
                context=context,
                idempotency_key=normalized_key,
            )
            await self._audit(
                context,
                event_kind="replay",
                outcome="succeeded",
                result_code="workflow_transport_route_snapshot_replayed",
                idempotency_key=normalized_key,
                route=route,
                snapshot=prior.snapshot,
            )
            return prior.snapshot

        current = await self._repository.get_transport_route_snapshot(
            route_id=route.route_id,
            route_revision=route.route_revision,
        )
        if current is not None:
            await self._deny(
                context,
                result_code=(
                    "workflow_transport_route_snapshot_competing_identity"
                    if current.snapshotter_subject_id != context.subject_id
                    else "workflow_transport_route_snapshot_already_exists"
                ),
                idempotency_key=normalized_key,
                route=route,
                snapshot=current,
            )

        candidate = self._build_snapshot(
            route=route,
            snapshotter_subject_id=context.subject_id,
            captured_at=context.requested_at,
        )
        await self._audit(
            context,
            event_kind="authorization",
            outcome="authorized",
            result_code="workflow_transport_route_snapshot_persistence_authorized",
            idempotency_key=normalized_key,
            route=route,
            snapshot=candidate,
        )
        result = await self._repository.snapshot_transport_route(
            WorkflowTransportRouteSnapshotRequest(
                expected_source_route_id=normalized_route_id,
                expected_source_route_revision=normalized_revision,
                expected_source_route_digest=normalized_digest,
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
                WorkflowTransportRouteSnapshotStatus.SNAPSHOTTED,
                WorkflowTransportRouteSnapshotStatus.REPLAY,
            }
            and result.snapshot is not None
        ):
            await self._validate_or_deny(
                result.snapshot,
                route=route,
                context=context,
                idempotency_key=normalized_key,
            )
            return result.snapshot

        result_code = {
            WorkflowTransportRouteSnapshotStatus.IDEMPOTENCY_CONFLICT: (
                "workflow_transport_route_snapshot_idempotency_conflict"
            ),
            WorkflowTransportRouteSnapshotStatus.SOURCE_CONFLICT: (
                "workflow_transport_route_snapshot_source_conflict"
            ),
            WorkflowTransportRouteSnapshotStatus.ALREADY_SNAPSHOTTED: (
                "workflow_transport_route_snapshot_already_exists"
            ),
        }.get(
            result.status,
            "workflow_transport_route_snapshot_repository_contract_violation",
        )
        await self._deny(
            context,
            result_code=result_code,
            idempotency_key=normalized_key,
            route=route,
            snapshot=result.snapshot,
        )

    @staticmethod
    def _validate_source_route(
        route: DeploymentEventTransportRoute,
        *,
        expected_route_id: str,
        expected_revision: str,
        expected_digest: str,
        context: WorkflowTransportRouteRegistryContext,
    ) -> None:
        if (
            route.route_id != expected_route_id
            or route.route_revision != expected_revision
            or route.canonical_digest != expected_digest
            or canonical_digest(route.digest_payload()) != route.canonical_digest
            or route.scope != context.scope
            or not route.active
        ):
            raise WorkflowTransportRouteSnapshotError(
                "workflow_transport_route_snapshot_source_conflict",
                "The active deployment transport route no longer matches the exact request.",
            )

    @classmethod
    def _build_snapshot(
        cls,
        *,
        route: DeploymentEventTransportRoute,
        snapshotter_subject_id: str,
        captured_at: datetime,
    ) -> EventPhysicalTransportRouteSnapshot:
        snapshot_id = (
            "event-physical-transport-route-snapshot."
            + sha256(
                f"{route.route_id}:{route.route_revision}:{route.canonical_digest}".encode()
            ).hexdigest()[:24]
        )
        values: dict[str, object] = {
            "snapshot_id": snapshot_id,
            **{name: getattr(route, name) for name in cls._ROUTE_FIELDS},
            "source_route_digest": route.canonical_digest,
            "snapshotter_subject_id": snapshotter_subject_id,
            "captured_at": captured_at,
            "state": EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED,
            "authority": EventPhysicalTransportRouteSnapshotAuthority(),
        }
        digest_payload = {
            key: value.canonical_value()
            if isinstance(value, (EventPhysicalTransportRouteSnapshotAuthority, WorkflowScope))
            else value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, EventPhysicalTransportRouteSnapshotState)
            else value
            for key, value in values.items()
        }
        return EventPhysicalTransportRouteSnapshot(
            **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
        )

    async def _validate_or_deny(
        self,
        snapshot: EventPhysicalTransportRouteSnapshot,
        *,
        route: DeploymentEventTransportRoute,
        context: WorkflowTransportRouteRegistryContext,
        idempotency_key: str,
    ) -> None:
        try:
            self._validate_snapshot(snapshot, route=route, context=context)
        except WorkflowTransportRouteSnapshotError as exc:
            await self._deny(
                context,
                result_code=exc.code,
                idempotency_key=idempotency_key,
                route=route,
                snapshot=snapshot,
            )

    @classmethod
    def _validate_snapshot(
        cls,
        snapshot: EventPhysicalTransportRouteSnapshot,
        *,
        route: DeploymentEventTransportRoute,
        context: WorkflowTransportRouteRegistryContext,
    ) -> None:
        expected_id = (
            "event-physical-transport-route-snapshot."
            + sha256(
                f"{route.route_id}:{route.route_revision}:{route.canonical_digest}".encode()
            ).hexdigest()[:24]
        )
        if (
            snapshot.snapshot_id != expected_id
            or snapshot.source_route_digest != route.canonical_digest
            or not all(
                getattr(snapshot, name) == getattr(route, name) for name in cls._ROUTE_FIELDS
            )
            or snapshot.scope != context.scope
            or snapshot.snapshotter_subject_id != context.subject_id
            or snapshot.captured_at > context.requested_at
            or snapshot.state is not EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED
            or canonical_digest(snapshot.digest_payload()) != snapshot.canonical_digest
            or any(snapshot.authority.canonical_value().values())
            or snapshot.grants_endpoint_resolution_authority
            or snapshot.grants_route_selection_authority
            or snapshot.grants_route_binding_authority
            or snapshot.grants_credential_access_authority
            or snapshot.grants_network_access_authority
            or snapshot.grants_readiness_probe_authority
            or snapshot.grants_publication_authority
            or snapshot.grants_delivery_authority
            or snapshot.grants_dispatch_authority
            or snapshot.grants_execution_authority
        ):
            raise WorkflowTransportRouteSnapshotError(
                "workflow_transport_route_snapshot_repository_scope_violation",
                "The repository returned incorrectly scoped transport route evidence.",
            )

    async def _require_registry_workload(
        self, context: WorkflowTransportRouteRegistryContext
    ) -> None:
        if (
            context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience != WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE
        ):
            await self._deny(
                context,
                result_code="workflow_transport_route_snapshot_registry_identity_required",
            )

    async def _deny(
        self,
        context: WorkflowTransportRouteRegistryContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
        route: DeploymentEventTransportRoute | None = None,
        snapshot: EventPhysicalTransportRouteSnapshot | None = None,
    ) -> NoReturn:
        await self._audit(
            context,
            event_kind="denied",
            outcome="denied",
            result_code=result_code,
            idempotency_key=idempotency_key,
            route=route,
            snapshot=snapshot,
        )
        raise WorkflowTransportRouteSnapshotError(
            result_code, "The workflow transport route snapshot request was denied."
        )

    async def _audit(
        self,
        context: WorkflowTransportRouteRegistryContext,
        *,
        event_kind: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        route: DeploymentEventTransportRoute | None,
        snapshot: EventPhysicalTransportRouteSnapshot | None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=f"atlas.workflow.transport-route-snapshot.{event_kind}",
                schema_version="1.0",
                producer=WORKFLOW_TRANSPORT_ROUTE_SNAPSHOT_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.transport-routes.snapshot",
                resource_type="resource.workflow-transport-route-snapshot",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-transport-route-snapshot",
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    ("route_id", "none" if route is None else route.route_id),
                    ("snapshot_id", "none" if snapshot is None else snapshot.snapshot_id),
                    ("endpoint_resolution_authority", "false"),
                    ("route_selection_authority", "false"),
                    ("route_binding_authority", "false"),
                    ("credential_access_authority", "false"),
                    ("network_access_authority", "false"),
                    ("readiness_probe_authority", "false"),
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
            raise WorkflowTransportRouteSnapshotError(
                f"workflow_transport_route_snapshot_{name}_invalid", f"{name} is invalid."
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowTransportRouteSnapshotError(
                "workflow_transport_route_snapshot_idempotency_key_invalid",
                "The idempotency key is invalid.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise WorkflowTransportRouteSnapshotError(
                f"workflow_transport_route_snapshot_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value


__all__ = [
    "WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE",
    "WORKFLOW_TRANSPORT_ROUTE_SNAPSHOT_PRODUCER",
    "WorkflowTransportRouteRegistryContext",
    "WorkflowTransportRouteSnapshotService",
]

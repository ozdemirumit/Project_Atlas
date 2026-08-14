from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.endpoint_resolution_authorization_lease_ports import (
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRepository,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus,
)
from atlas.modules.workflows.domain import (
    DeploymentEventTransportRouteSelectionHead,
    EventPhysicalTransportRouteSnapshot,
    EventPhysicalTransportRouteSnapshotState,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthority,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseEffectiveState,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseState,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationPolicy,
    WorkflowEventPhysicalTransportRouteBinding,
    WorkflowEventPhysicalTransportRouteBindingState,
    WorkflowEventPhysicalTransportRouteFreshnessAdmission,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_endpoint_resolution_authorization_policy,
)

WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE = (
    "audience.workflow-physical-transport-endpoint-resolver"
)
WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLUTION_AUTHORIZATION_LEASE_PRODUCER = (
    "project-atlas-workflow-physical-transport-endpoint-resolution-authorizer"
)


@dataclass(frozen=True, slots=True)
class WorkflowPhysicalTransportEndpointResolverContext:
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
            raise ValueError("endpoint resolver context contains an invalid identifier")
        if self.requested_at.tzinfo is None:
            raise ValueError("endpoint resolution authorization requested_at must be aware")


class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseService:
    """Authorizes one resolver without materializing or consuming endpoint data."""

    def __init__(
        self,
        *,
        authorization_repository: (
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRepository
        ),
        audit_sink: AuditSink,
        policy: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationPolicy | None = None,
    ) -> None:
        self._repository = authorization_repository
        self._audit_sink = audit_sink
        self._policy = policy or (
            code_owned_workflow_event_physical_transport_endpoint_resolution_authorization_policy()
        )

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def repository(
        self,
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationPolicy:
        return self._policy

    async def authorize(
        self,
        *,
        freshness_admission_id: str,
        freshness_admission_digest: str,
        policy_id: str,
        policy_version: str,
        idempotency_key: str,
        context: WorkflowPhysicalTransportEndpointResolverContext,
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease:
        await self._require_resolver_workload(context)
        try:
            admission_id = self._identifier(
                freshness_admission_id,
                "freshness_admission_id",
            )
            admission_digest = self._digest(
                freshness_admission_digest,
                "freshness_admission_digest",
            )
            requested_policy_id = self._identifier(policy_id, "policy_id")
            requested_policy_version = self._identifier(policy_version, "policy_version")
            normalized_key = self._idempotency_key(idempotency_key)
        except WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError as exc:
            await self._deny(context, result_code=exc.code)

        if (
            requested_policy_id != self._policy.policy_id
            or requested_policy_version != self._policy.policy_version
            or canonical_digest(self._policy.digest_payload()) != self._policy.canonical_digest
            or self._policy.validity_window_seconds != 15
            or not self._policy.full_freshness_window_required
            or not self._policy.resolver_subject_bound
            or not self._policy.single_use_required
        ):
            await self._deny(
                context,
                result_code=(
                    "workflow_physical_transport_endpoint_resolution_authorization_policy_conflict"
                ),
                idempotency_key=normalized_key,
            )

        authoritative_now = await self._authoritative_time_or_deny(
            context,
            idempotency_key=normalized_key,
        )
        admission = await self._repository.get_route_freshness_admission_by_id(
            freshness_admission_id=admission_id
        )
        if admission is None:
            await self._deny_evidence(context, normalized_key)
        await self._validate_admission_or_deny(
            admission,
            expected_digest=admission_digest,
            authoritative_now=authoritative_now,
            context=context,
            idempotency_key=normalized_key,
        )

        binding = await self._repository.get_physical_transport_route_binding_by_id(
            binding_id=admission.physical_transport_route_binding_id
        )
        if binding is None:
            await self._deny_evidence(context, normalized_key)
        await self._validate_binding_or_deny(
            admission,
            binding,
            context=context,
            idempotency_key=normalized_key,
        )

        route = await self._repository.get_transport_route_snapshot_by_id(
            snapshot_id=binding.transport_route_snapshot_id
        )
        if route is None:
            await self._deny_evidence(context, normalized_key)
        await self._validate_route_or_deny(
            admission,
            binding,
            route,
            context=context,
            idempotency_key=normalized_key,
        )

        head = await self._repository.get_current_route_selection_head(
            scope=context.scope,
            route_set_id=admission.route_set_id,
        )
        if head is None:
            await self._deny_evidence(context, normalized_key)
        await self._validate_head_or_deny(
            admission,
            route,
            head,
            context=context,
            idempotency_key=normalized_key,
        )

        fingerprint = canonical_digest(
            {
                "current_selection_head_digest": head.canonical_digest,
                "current_selection_head_fencing_token_digest": head.fencing_token_digest,
                "current_selection_head_generation": head.generation,
                "current_selection_head_id": head.head_id,
                "freshness_admission_digest": admission_digest,
                "freshness_admission_id": admission_id,
                "policy_digest": self._policy.canonical_digest,
                "resolver_subject_id": context.subject_id,
                "scope": context.scope.canonical_value(),
            }
        )
        prior = await self._repository.get_endpoint_resolution_authorization_lease_request(
            scope=context.scope,
            resolver_subject_id=context.subject_id,
            idempotency_key=normalized_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._deny(
                    context,
                    result_code=(
                        "workflow_physical_transport_endpoint_resolution_authorization_"
                        "idempotency_conflict"
                    ),
                    idempotency_key=normalized_key,
                    lease=prior.lease,
                )
            await self._validate_lease_or_deny(
                prior.lease,
                admission=admission,
                binding=binding,
                route=route,
                head=head,
                authoritative_now=authoritative_now,
                context=context,
                idempotency_key=normalized_key,
            )
            await self._audit(
                context,
                event_kind="replay",
                outcome="succeeded",
                result_code=(
                    "workflow_physical_transport_endpoint_resolution_authorization_lease_replayed"
                ),
                idempotency_key=normalized_key,
                lease=prior.lease,
            )
            return prior.lease

        current = await self._repository.get_endpoint_resolution_authorization_lease(
            freshness_admission_id=admission.freshness_admission_id
        )
        if current is not None:
            await self._deny(
                context,
                result_code=(
                    "workflow_physical_transport_endpoint_resolution_authorization_competing_identity"
                    if current.resolver_subject_id != context.subject_id
                    else (
                        "workflow_physical_transport_endpoint_resolution_authorization_"
                        "already_authorized"
                    )
                ),
                idempotency_key=normalized_key,
                lease=current,
            )

        lease_id = self._lease_id(
            admission=admission,
            resolver_subject_id=context.subject_id,
            idempotency_key=normalized_key,
        )
        await self._audit(
            context,
            event_kind="authorization",
            outcome="authorized",
            result_code=(
                "workflow_physical_transport_endpoint_resolution_authorization_persistence_authorized"
            ),
            idempotency_key=normalized_key,
            authorization_lease_id=lease_id,
        )
        result = await self._repository.authorize_endpoint_resolution(
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest(
                authorization_lease_id=lease_id,
                expected_freshness_admission_id=admission.freshness_admission_id,
                expected_freshness_admission_digest=admission.canonical_digest,
                expected_freshness_admission_valid_until=admission.valid_until,
                expected_physical_transport_route_binding_id=binding.binding_id,
                expected_physical_transport_route_binding_digest=binding.canonical_digest,
                expected_transport_route_snapshot_id=route.snapshot_id,
                expected_transport_route_snapshot_digest=route.canonical_digest,
                expected_current_selection_head_id=head.head_id,
                expected_current_selection_head_digest=head.canonical_digest,
                expected_current_selection_head_generation=head.generation,
                expected_current_selection_head_fencing_token_digest=head.fencing_token_digest,
                expected_route_set_id=head.route_set_id,
                expected_route_set_revision=head.route_set_revision,
                expected_selection_epoch_id=head.selection_epoch_id,
                expected_selection_epoch_revision=head.selection_epoch_revision,
                expected_selected_route_id=head.selected_route_id,
                expected_selected_route_revision=head.selected_route_revision,
                expected_selected_route_digest=head.selected_route_digest,
                expected_selection_active=head.selection_active,
                expected_selection_eligible=head.selection_eligible,
                expected_selection_suspended=head.selection_suspended,
                expected_selection_withdrawn=head.selection_withdrawn,
                expected_selection_superseded=head.selection_superseded,
                expected_policy_id=self._policy.policy_id,
                expected_policy_version=self._policy.policy_version,
                expected_policy_digest=self._policy.canonical_digest,
                expected_validity_window_seconds=self._policy.validity_window_seconds,
                scope=context.scope,
                resolver_subject_id=context.subject_id,
                idempotency_key=normalized_key,
                request_fingerprint=fingerprint,
            )
        )
        if (
            result.status
            in {
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.AUTHORIZED,
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.REPLAY,
            }
            and result.lease is not None
        ):
            post_now = await self._authoritative_time_or_deny(
                context,
                idempotency_key=normalized_key,
                lease=result.lease,
            )
            post_head = await self._repository.get_current_route_selection_head(
                scope=context.scope,
                route_set_id=admission.route_set_id,
            )
            if post_head is None:
                await self._deny_evidence(context, normalized_key, lease=result.lease)
            await self._validate_head_or_deny(
                admission,
                route,
                post_head,
                context=context,
                idempotency_key=normalized_key,
                lease=result.lease,
            )
            await self._validate_lease_or_deny(
                result.lease,
                admission=admission,
                binding=binding,
                route=route,
                head=post_head,
                authoritative_now=post_now,
                context=context,
                idempotency_key=normalized_key,
            )
            return result.lease

        status = WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus
        result_code = {
            status.IDEMPOTENCY_CONFLICT: (
                "workflow_physical_transport_endpoint_resolution_authorization_idempotency_conflict"
            ),
            status.EVIDENCE_CONFLICT: (
                "workflow_physical_transport_endpoint_resolution_authorization_evidence_conflict"
            ),
            status.ALREADY_AUTHORIZED: (
                "workflow_physical_transport_endpoint_resolution_authorization_already_authorized"
            ),
        }.get(
            result.status,
            "workflow_physical_transport_endpoint_resolution_authorization_repository_contract_violation",
        )
        await self._deny(
            context,
            result_code=result_code,
            idempotency_key=normalized_key,
            lease=result.lease,
        )

    async def _validate_admission_or_deny(
        self,
        admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission,
        *,
        expected_digest: str,
        authoritative_now: datetime,
        context: WorkflowPhysicalTransportEndpointResolverContext,
        idempotency_key: str,
    ) -> None:
        if (
            admission.canonical_digest != expected_digest
            or canonical_digest(admission.digest_payload()) != admission.canonical_digest
            or admission.scope != context.scope
            or admission.state
            is not WorkflowEventPhysicalTransportRouteFreshnessAdmissionState.ADMITTED_CURRENT
            or admission.evaluated_at > authoritative_now
            or authoritative_now + timedelta(seconds=self._policy.validity_window_seconds)
            > admission.valid_until
            or any(admission.authority.canonical_value().values())
        ):
            await self._deny_evidence(context, idempotency_key)

    async def _validate_binding_or_deny(
        self,
        admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission,
        binding: WorkflowEventPhysicalTransportRouteBinding,
        *,
        context: WorkflowPhysicalTransportEndpointResolverContext,
        idempotency_key: str,
    ) -> None:
        if (
            binding.binding_id != admission.physical_transport_route_binding_id
            or binding.canonical_digest != admission.physical_transport_route_binding_digest
            or canonical_digest(binding.digest_payload()) != binding.canonical_digest
            or binding.scope != admission.scope
            or binding.state is not WorkflowEventPhysicalTransportRouteBindingState.BOUND
            or binding.bound_at > admission.evaluated_at
            or any(binding.authority.canonical_value().values())
        ):
            await self._deny_evidence(context, idempotency_key)

    async def _validate_route_or_deny(
        self,
        admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission,
        binding: WorkflowEventPhysicalTransportRouteBinding,
        route: EventPhysicalTransportRouteSnapshot,
        *,
        context: WorkflowPhysicalTransportEndpointResolverContext,
        idempotency_key: str,
    ) -> None:
        if (
            route.snapshot_id != admission.transport_route_snapshot_id
            or route.snapshot_id != binding.transport_route_snapshot_id
            or route.canonical_digest != admission.transport_route_snapshot_digest
            or route.canonical_digest != binding.transport_route_snapshot_digest
            or canonical_digest(route.digest_payload()) != route.canonical_digest
            or route.scope != admission.scope
            or route.state is not EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED
            or route.captured_at > binding.bound_at
            or any(route.authority.canonical_value().values())
        ):
            await self._deny_evidence(context, idempotency_key)

    async def _validate_head_or_deny(
        self,
        admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission,
        route: EventPhysicalTransportRouteSnapshot,
        head: DeploymentEventTransportRouteSelectionHead,
        *,
        context: WorkflowPhysicalTransportEndpointResolverContext,
        idempotency_key: str,
        lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease | None = None,
    ) -> None:
        if (
            canonical_digest(head.digest_payload()) != head.canonical_digest
            or head.scope != admission.scope
            or head.current is not True
            or head.selection_active is not True
            or head.selection_eligible is not True
            or head.selection_suspended
            or head.selection_withdrawn
            or head.selection_superseded
            or head.head_id != admission.current_selection_head_id
            or head.canonical_digest != admission.current_selection_head_digest
            or head.generation != admission.current_selection_head_generation
            or head.fencing_token_digest != admission.current_selection_head_fencing_token_digest
            or head.route_set_id != admission.route_set_id
            or head.route_set_revision != admission.route_set_revision
            or head.selection_epoch_id != admission.selection_epoch_id
            or head.selection_epoch_revision != admission.selection_epoch_revision
            or head.selected_route_id != admission.selected_route_id
            or head.selected_route_revision != admission.selected_route_revision
            or head.selected_route_digest != admission.selected_route_digest
            or head.route_set_id != route.route_set_id
            or head.selected_route_id != route.route_id
            or head.selected_route_revision != route.route_revision
            or head.selected_route_digest != route.source_route_digest
        ):
            await self._deny_evidence(context, idempotency_key, lease=lease)

    def _build_lease(
        self,
        *,
        authorization_lease_id: str,
        admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission,
        binding: WorkflowEventPhysicalTransportRouteBinding,
        route: EventPhysicalTransportRouteSnapshot,
        head: DeploymentEventTransportRouteSelectionHead,
        resolver_subject_id: str,
        issued_at: datetime,
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease:
        values: dict[str, object] = {
            "authorization_lease_id": authorization_lease_id,
            "freshness_admission_id": admission.freshness_admission_id,
            "freshness_admission_digest": admission.canonical_digest,
            "physical_transport_route_binding_id": binding.binding_id,
            "physical_transport_route_binding_digest": binding.canonical_digest,
            "transport_route_snapshot_id": route.snapshot_id,
            "transport_route_snapshot_digest": route.canonical_digest,
            "current_selection_head_id": head.head_id,
            "current_selection_head_digest": head.canonical_digest,
            "current_selection_head_generation": head.generation,
            "current_selection_head_fencing_token_digest": head.fencing_token_digest,
            "route_set_id": head.route_set_id,
            "route_set_revision": head.route_set_revision,
            "selection_epoch_id": head.selection_epoch_id,
            "selection_epoch_revision": head.selection_epoch_revision,
            "selected_route_id": head.selected_route_id,
            "selected_route_revision": head.selected_route_revision,
            "selected_route_digest": head.selected_route_digest,
            "selection_active": head.selection_active,
            "selection_eligible": head.selection_eligible,
            "selection_suspended": head.selection_suspended,
            "selection_withdrawn": head.selection_withdrawn,
            "selection_superseded": head.selection_superseded,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "scope": admission.scope,
            "resolver_subject_id": resolver_subject_id,
            "issued_at": issued_at,
            "valid_until": issued_at + timedelta(seconds=self._policy.validity_window_seconds),
            "state": (
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
            ),
            "authority": (
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthority()
            ),
        }
        digest_payload = {
            key: value.canonical_value()
            if isinstance(
                value,
                (
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthority,
                    WorkflowScope,
                ),
            )
            else value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(
                value,
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseState,
            )
            else value
            for key, value in values.items()
        }
        return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease(
            **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
        )

    async def _validate_lease_or_deny(
        self,
        lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
        *,
        admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission,
        binding: WorkflowEventPhysicalTransportRouteBinding,
        route: EventPhysicalTransportRouteSnapshot,
        head: DeploymentEventTransportRouteSelectionHead,
        authoritative_now: datetime,
        context: WorkflowPhysicalTransportEndpointResolverContext,
        idempotency_key: str,
    ) -> None:
        expected = self._build_lease(
            authorization_lease_id=lease.authorization_lease_id,
            admission=admission,
            binding=binding,
            route=route,
            head=head,
            resolver_subject_id=context.subject_id,
            issued_at=lease.issued_at,
        )
        authorities = (
            lease.grants_endpoint_resolution_authority,
            lease.grants_route_selection_authority,
            lease.grants_route_binding_authority,
            lease.grants_credential_access_authority,
            lease.grants_network_access_authority,
            lease.grants_readiness_probe_authority,
            lease.grants_publication_authority,
            lease.grants_delivery_authority,
            lease.grants_dispatch_authority,
            lease.grants_execution_authority,
        )
        if (
            lease != expected
            or lease.scope != context.scope
            or lease.resolver_subject_id != context.subject_id
            or lease.issued_at < admission.evaluated_at
            or lease.valid_until > admission.valid_until
            or lease.effective_state(evaluated_at=authoritative_now)
            is not (
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseEffectiveState
            ).ACTIVE
            or canonical_digest(lease.digest_payload()) != lease.canonical_digest
            or authorities != (True, False, False, False, False, False, False, False, False, False)
        ):
            await self._deny(
                context,
                result_code=(
                    "workflow_physical_transport_endpoint_resolution_authorization_"
                    "repository_scope_violation"
                ),
                idempotency_key=idempotency_key,
                lease=lease,
            )

    def _lease_id(
        self,
        *,
        admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission,
        resolver_subject_id: str,
        idempotency_key: str,
    ) -> str:
        suffix = sha256(
            (
                f"{admission.canonical_digest}:{resolver_subject_id}:"
                f"{self._policy.canonical_digest}:{idempotency_key}"
            ).encode()
        ).hexdigest()[:24]
        return f"workflow-event-physical-transport-endpoint-resolution-authorization-lease.{suffix}"

    async def _authoritative_time_or_deny(
        self,
        context: WorkflowPhysicalTransportEndpointResolverContext,
        *,
        idempotency_key: str,
        lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease | None = None,
    ) -> datetime:
        authoritative_now = await self._repository.get_authoritative_time()
        if authoritative_now.tzinfo is None:
            await self._deny(
                context,
                result_code=(
                    "workflow_physical_transport_endpoint_resolution_authorization_"
                    "repository_time_invalid"
                ),
                idempotency_key=idempotency_key,
                lease=lease,
            )
        return authoritative_now

    async def _require_resolver_workload(
        self, context: WorkflowPhysicalTransportEndpointResolverContext
    ) -> None:
        if (
            context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience != WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE
        ):
            await self._deny(
                context,
                result_code=(
                    "workflow_physical_transport_endpoint_resolution_authorization_"
                    "resolver_identity_required"
                ),
            )

    async def _deny_evidence(
        self,
        context: WorkflowPhysicalTransportEndpointResolverContext,
        idempotency_key: str,
        *,
        lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease | None = None,
    ) -> NoReturn:
        await self._deny(
            context,
            result_code=(
                "workflow_physical_transport_endpoint_resolution_authorization_evidence_conflict"
            ),
            idempotency_key=idempotency_key,
            lease=lease,
        )

    async def _deny(
        self,
        context: WorkflowPhysicalTransportEndpointResolverContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
        lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease | None = None,
    ) -> NoReturn:
        await self._audit(
            context,
            event_kind="denied",
            outcome="denied",
            result_code=result_code,
            idempotency_key=idempotency_key,
            lease=lease,
        )
        raise WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError(
            result_code,
            "The workflow physical transport endpoint resolution authorization was denied.",
        )

    async def _audit(
        self,
        context: WorkflowPhysicalTransportEndpointResolverContext,
        *,
        event_kind: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease | None = None,
        authorization_lease_id: str | None = None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=(
                    "atlas.workflow.physical-transport-endpoint-resolution-authorization."
                    f"{event_kind}"
                ),
                schema_version="1.0",
                producer=(
                    WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLUTION_AUTHORIZATION_LEASE_PRODUCER
                ),
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.physical-transport-endpoint-resolution.authorize",
                resource_type=(
                    "resource.workflow-physical-transport-endpoint-resolution-authorization-lease"
                ),
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-physical-transport-endpoint-resolution-authorization-lease",
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    (
                        "authorization_lease_id",
                        authorization_lease_id
                        or ("none" if lease is None else lease.authorization_lease_id),
                    ),
                    (
                        "freshness_admission_id",
                        "none" if lease is None else lease.freshness_admission_id,
                    ),
                    ("endpoint_resolution_authority", "true"),
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
            raise WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError(
                f"workflow_physical_transport_endpoint_resolution_authorization_{name}_invalid",
                f"{name} is invalid.",
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError(
                "workflow_physical_transport_endpoint_resolution_authorization_"
                "idempotency_key_invalid",
                "The idempotency key is invalid.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError(
                f"workflow_physical_transport_endpoint_resolution_authorization_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value


__all__ = [
    "WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLUTION_AUTHORIZATION_LEASE_PRODUCER",
    "WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE",
    "WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseService",
    "WorkflowPhysicalTransportEndpointResolverContext",
]

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.physical_route_binding_ports import (
    WorkflowEventPhysicalTransportRouteBindingError,
    WorkflowEventPhysicalTransportRouteBindingRepository,
    WorkflowEventPhysicalTransportRouteBindingRequest,
    WorkflowEventPhysicalTransportRouteBindingStatus,
)
from atlas.modules.workflows.domain import (
    EventPhysicalTransportProfileSnapshot,
    EventPhysicalTransportProfileSnapshotState,
    EventPhysicalTransportRouteSnapshot,
    EventPhysicalTransportRouteSnapshotState,
    WorkflowEventLogicalChannelBinding,
    WorkflowEventLogicalChannelBindingState,
    WorkflowEventPhysicalTransportRouteBinding,
    WorkflowEventPhysicalTransportRouteBindingAuthority,
    WorkflowEventPhysicalTransportRouteBindingPolicy,
    WorkflowEventPhysicalTransportRouteBindingState,
    WorkflowEventTransportCompatibilityAdmission,
    WorkflowEventTransportCompatibilityAdmissionState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_route_binding_policy,
)

WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDER_AUDIENCE = (
    "audience.workflow-physical-transport-route-binder"
)
WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDING_PRODUCER = (
    "project-atlas-workflow-physical-transport-route-binder"
)


@dataclass(frozen=True, slots=True)
class WorkflowPhysicalTransportRouteBinderContext:
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
            raise ValueError("physical route binder context contains an invalid identifier")
        if self.requested_at.tzinfo is None:
            raise ValueError("physical route binding requested_at must be timezone-aware")


class WorkflowEventPhysicalTransportRouteBindingService:
    """Binds exact immutable evidence without resolving or operating the route."""

    def __init__(
        self,
        *,
        binding_repository: WorkflowEventPhysicalTransportRouteBindingRepository,
        audit_sink: AuditSink,
        policy: WorkflowEventPhysicalTransportRouteBindingPolicy | None = None,
    ) -> None:
        self._repository = binding_repository
        self._audit_sink = audit_sink
        self._policy = policy or code_owned_workflow_event_physical_transport_route_binding_policy()

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def repository(self) -> WorkflowEventPhysicalTransportRouteBindingRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowEventPhysicalTransportRouteBindingPolicy:
        return self._policy

    async def bind(
        self,
        *,
        logical_channel_binding_id: str,
        logical_channel_binding_digest: str,
        transport_compatibility_admission_id: str,
        transport_compatibility_admission_digest: str,
        transport_profile_snapshot_id: str,
        transport_profile_snapshot_digest: str,
        transport_route_snapshot_id: str,
        transport_route_snapshot_digest: str,
        policy_id: str,
        policy_version: str,
        policy_digest: str,
        idempotency_key: str,
        context: WorkflowPhysicalTransportRouteBinderContext,
    ) -> WorkflowEventPhysicalTransportRouteBinding:
        await self._require_binder_workload(context)
        try:
            logical_id = self._identifier(logical_channel_binding_id, "logical_binding_id")
            logical_digest = self._digest(logical_channel_binding_digest, "logical_binding_digest")
            admission_id = self._identifier(
                transport_compatibility_admission_id, "compatibility_admission_id"
            )
            admission_digest = self._digest(
                transport_compatibility_admission_digest, "compatibility_admission_digest"
            )
            profile_id = self._identifier(transport_profile_snapshot_id, "profile_snapshot_id")
            profile_digest = self._digest(
                transport_profile_snapshot_digest, "profile_snapshot_digest"
            )
            route_id = self._identifier(transport_route_snapshot_id, "route_snapshot_id")
            route_digest = self._digest(transport_route_snapshot_digest, "route_snapshot_digest")
            requested_policy_id = self._identifier(policy_id, "policy_id")
            requested_policy_version = self._identifier(policy_version, "policy_version")
            requested_policy_digest = self._digest(policy_digest, "policy_digest")
            normalized_key = self._idempotency_key(idempotency_key)
        except WorkflowEventPhysicalTransportRouteBindingError as exc:
            await self._deny(context, result_code=exc.code)

        if (
            requested_policy_id != self._policy.policy_id
            or requested_policy_version != self._policy.policy_version
            or requested_policy_digest != self._policy.canonical_digest
            or canonical_digest(self._policy.digest_payload()) != self._policy.canonical_digest
        ):
            await self._deny(
                context,
                result_code="workflow_physical_transport_route_binding_policy_conflict",
                idempotency_key=normalized_key,
            )

        logical = await self._repository.get_event_logical_channel_binding_by_id(
            binding_id=logical_id
        )
        admission = await self._repository.get_transport_compatibility_admission_by_id(
            admission_id=admission_id
        )
        profile = await self._repository.get_transport_profile_snapshot_by_id(
            snapshot_id=profile_id
        )
        route = await self._repository.get_transport_route_snapshot_by_id(snapshot_id=route_id)
        if logical is None or admission is None or profile is None or route is None:
            await self._deny(
                context,
                result_code="workflow_physical_transport_route_binding_evidence_conflict",
                idempotency_key=normalized_key,
            )
        await self._validate_sources_or_deny(
            logical,
            admission,
            profile,
            route,
            expected_digests=(logical_digest, admission_digest, profile_digest, route_digest),
            context=context,
            idempotency_key=normalized_key,
        )

        fingerprint = canonical_digest(
            {
                "binder_subject_id": context.subject_id,
                "logical_channel_binding_digest": logical_digest,
                "logical_channel_binding_id": logical_id,
                "policy_digest": requested_policy_digest,
                "scope": context.scope.canonical_value(),
                "transport_compatibility_admission_digest": admission_digest,
                "transport_compatibility_admission_id": admission_id,
                "transport_profile_snapshot_digest": profile_digest,
                "transport_profile_snapshot_id": profile_id,
                "transport_route_snapshot_digest": route_digest,
                "transport_route_snapshot_id": route_id,
            }
        )
        prior = await self._repository.get_physical_transport_route_binding_request(
            scope=context.scope,
            binder_subject_id=context.subject_id,
            idempotency_key=normalized_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._deny(
                    context,
                    result_code="workflow_physical_transport_route_binding_idempotency_conflict",
                    idempotency_key=normalized_key,
                    binding=prior.binding,
                )
            await self._validate_binding_or_deny(
                prior.binding,
                logical=logical,
                admission=admission,
                profile=profile,
                route=route,
                context=context,
                idempotency_key=normalized_key,
            )
            await self._audit(
                context,
                event_kind="replay",
                outcome="succeeded",
                result_code="workflow_physical_transport_route_binding_replayed",
                idempotency_key=normalized_key,
                binding=prior.binding,
            )
            return prior.binding

        current = await self._repository.get_physical_transport_route_binding(
            logical_channel_binding_id=logical.binding_id
        )
        if current is not None:
            await self._deny(
                context,
                result_code=(
                    "workflow_physical_transport_route_binding_competing_identity"
                    if current.binder_subject_id != context.subject_id
                    else "workflow_physical_transport_route_binding_already_bound"
                ),
                idempotency_key=normalized_key,
                binding=current,
            )

        candidate = self._build_binding(
            logical=logical,
            admission=admission,
            profile=profile,
            route=route,
            binder_subject_id=context.subject_id,
            bound_at=context.requested_at,
        )
        await self._audit(
            context,
            event_kind="authorization",
            outcome="authorized",
            result_code="workflow_physical_transport_route_binding_persistence_authorized",
            idempotency_key=normalized_key,
            binding=candidate,
        )
        result = await self._repository.bind_physical_transport_route(
            WorkflowEventPhysicalTransportRouteBindingRequest(
                expected_logical_channel_binding_id=logical_id,
                expected_logical_channel_binding_digest=logical_digest,
                expected_transport_compatibility_admission_id=admission_id,
                expected_transport_compatibility_admission_digest=admission_digest,
                expected_transport_profile_snapshot_id=profile_id,
                expected_transport_profile_snapshot_digest=profile_digest,
                expected_transport_route_snapshot_id=route_id,
                expected_transport_route_snapshot_digest=route_digest,
                expected_policy_digest=self._policy.canonical_digest,
                scope=context.scope,
                binder_subject_id=context.subject_id,
                requested_at=context.requested_at,
                candidate=candidate,
                idempotency_key=normalized_key,
                request_fingerprint=fingerprint,
            )
        )
        if (
            result.status
            in {
                WorkflowEventPhysicalTransportRouteBindingStatus.BOUND,
                WorkflowEventPhysicalTransportRouteBindingStatus.REPLAY,
            }
            and result.binding is not None
        ):
            await self._validate_binding_or_deny(
                result.binding,
                logical=logical,
                admission=admission,
                profile=profile,
                route=route,
                context=context,
                idempotency_key=normalized_key,
            )
            return result.binding

        result_code = {
            WorkflowEventPhysicalTransportRouteBindingStatus.IDEMPOTENCY_CONFLICT: (
                "workflow_physical_transport_route_binding_idempotency_conflict"
            ),
            WorkflowEventPhysicalTransportRouteBindingStatus.EVIDENCE_CONFLICT: (
                "workflow_physical_transport_route_binding_evidence_conflict"
            ),
            WorkflowEventPhysicalTransportRouteBindingStatus.ALREADY_BOUND: (
                "workflow_physical_transport_route_binding_already_bound"
            ),
        }.get(
            result.status,
            "workflow_physical_transport_route_binding_repository_contract_violation",
        )
        await self._deny(
            context,
            result_code=result_code,
            idempotency_key=normalized_key,
            binding=result.binding,
        )

    async def _validate_sources_or_deny(
        self,
        logical: WorkflowEventLogicalChannelBinding,
        admission: WorkflowEventTransportCompatibilityAdmission,
        profile: EventPhysicalTransportProfileSnapshot,
        route: EventPhysicalTransportRouteSnapshot,
        *,
        expected_digests: tuple[str, str, str, str],
        context: WorkflowPhysicalTransportRouteBinderContext,
        idempotency_key: str,
    ) -> None:
        logical_digest, admission_digest, profile_digest, route_digest = expected_digests
        valid = all(
            (
                logical.canonical_digest == logical_digest
                and canonical_digest(logical.digest_payload()) == logical.canonical_digest
                and logical.scope == context.scope
                and logical.state is WorkflowEventLogicalChannelBindingState.BOUND
                and not any(logical.authority.canonical_value().values()),
                admission.canonical_digest == admission_digest
                and canonical_digest(admission.digest_payload()) == admission.canonical_digest
                and admission.scope == context.scope
                and admission.state is WorkflowEventTransportCompatibilityAdmissionState.ADMITTED
                and not any(admission.authority.canonical_value().values()),
                profile.canonical_digest == profile_digest
                and canonical_digest(profile.digest_payload()) == profile.canonical_digest
                and profile.scope == context.scope
                and profile.state is EventPhysicalTransportProfileSnapshotState.SNAPSHOTTED
                and not any(profile.authority.canonical_value().values()),
                route.canonical_digest == route_digest
                and canonical_digest(route.digest_payload()) == route.canonical_digest
                and route.scope == context.scope
                and route.state is EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED
                and not any(route.authority.canonical_value().values()),
            )
        )
        chain_valid = (
            admission.logical_channel_binding_id == logical.binding_id
            and admission.logical_channel_binding_digest == logical.canonical_digest
            and admission.transport_profile_snapshot_id == profile.snapshot_id
            and admission.transport_profile_snapshot_digest == profile.canonical_digest
            and admission.transport_profile_id == profile.transport_profile_id
            and admission.transport_profile_revision == profile.transport_profile_revision
            and route.transport_profile_id == profile.transport_profile_id
            and route.transport_profile_revision == profile.transport_profile_revision
            and route.transport_resource_id == profile.transport_resource_id
            and route.transport_resource_digest == profile.transport_resource_digest
            and route.transport_implementation_id == profile.transport_implementation_id
            and route.transport_implementation_version == profile.transport_implementation_version
            and route.adapter_contract_id == profile.adapter_contract_id
            and route.adapter_contract_version == profile.adapter_contract_version
            and route.adapter_contract_digest == profile.adapter_contract_digest
            and route.deployment_release_id == profile.deployment_release_id
            and route.deployment_profile == profile.deployment_profile
            and logical.scope == admission.scope == profile.scope == route.scope
        )
        policy_valid = (
            profile.transport_encryption_required
            and profile.restricted_network_supported
            and route.minimum_tls_version == self._policy.minimum_tls_version
            and route.server_authentication_required is self._policy.server_authentication_required
            and route.plaintext_fallback_prohibited is self._policy.plaintext_fallback_prohibited
            and route.restricted_network_enforced is self._policy.restricted_network_required
            and route.public_egress_prohibited is self._policy.public_egress_prohibited
            and route.proxy_mode in self._policy.allowed_proxy_modes
        )
        if not valid or not chain_valid or not policy_valid:
            await self._deny(
                context,
                result_code="workflow_physical_transport_route_binding_evidence_conflict",
                idempotency_key=idempotency_key,
            )

    def _build_binding(
        self,
        *,
        logical: WorkflowEventLogicalChannelBinding,
        admission: WorkflowEventTransportCompatibilityAdmission,
        profile: EventPhysicalTransportProfileSnapshot,
        route: EventPhysicalTransportRouteSnapshot,
        binder_subject_id: str,
        bound_at: datetime,
    ) -> WorkflowEventPhysicalTransportRouteBinding:
        binding_id = (
            "workflow-event-physical-transport-route-binding."
            + sha256(
                f"{logical.canonical_digest}:{admission.canonical_digest}:"
                f"{profile.canonical_digest}:{route.canonical_digest}:"
                f"{self._policy.canonical_digest}".encode()
            ).hexdigest()[:24]
        )
        values: dict[str, object] = {
            "binding_id": binding_id,
            "logical_channel_binding_id": logical.binding_id,
            "logical_channel_binding_digest": logical.canonical_digest,
            "transport_compatibility_admission_id": admission.compatibility_admission_id,
            "transport_compatibility_admission_digest": admission.canonical_digest,
            "transport_profile_snapshot_id": profile.snapshot_id,
            "transport_profile_snapshot_digest": profile.canonical_digest,
            "transport_route_snapshot_id": route.snapshot_id,
            "transport_route_snapshot_digest": route.canonical_digest,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "scope": logical.scope,
            "binder_subject_id": binder_subject_id,
            "bound_at": bound_at,
            "state": WorkflowEventPhysicalTransportRouteBindingState.BOUND,
            "authority": WorkflowEventPhysicalTransportRouteBindingAuthority(),
        }
        digest_payload = {
            key: value.canonical_value()
            if isinstance(
                value,
                (WorkflowEventPhysicalTransportRouteBindingAuthority, WorkflowScope),
            )
            else value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, WorkflowEventPhysicalTransportRouteBindingState)
            else value
            for key, value in values.items()
        }
        return WorkflowEventPhysicalTransportRouteBinding(
            **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
        )

    async def _validate_binding_or_deny(
        self,
        binding: WorkflowEventPhysicalTransportRouteBinding,
        *,
        logical: WorkflowEventLogicalChannelBinding,
        admission: WorkflowEventTransportCompatibilityAdmission,
        profile: EventPhysicalTransportProfileSnapshot,
        route: EventPhysicalTransportRouteSnapshot,
        context: WorkflowPhysicalTransportRouteBinderContext,
        idempotency_key: str,
    ) -> None:
        expected = self._build_binding(
            logical=logical,
            admission=admission,
            profile=profile,
            route=route,
            binder_subject_id=binding.binder_subject_id,
            bound_at=binding.bound_at,
        )
        authorities = (
            binding.grants_endpoint_resolution_authority,
            binding.grants_route_selection_authority,
            binding.grants_route_binding_authority,
            binding.grants_credential_access_authority,
            binding.grants_network_access_authority,
            binding.grants_readiness_probe_authority,
            binding.grants_publication_authority,
            binding.grants_delivery_authority,
            binding.grants_dispatch_authority,
            binding.grants_execution_authority,
        )
        if (
            binding != expected
            or binding.scope != context.scope
            or binding.binder_subject_id != context.subject_id
            or binding.bound_at > context.requested_at
            or binding.state is not WorkflowEventPhysicalTransportRouteBindingState.BOUND
            or canonical_digest(binding.digest_payload()) != binding.canonical_digest
            or any(binding.authority.canonical_value().values())
            or any(authorities)
        ):
            await self._deny(
                context,
                result_code="workflow_physical_transport_route_binding_repository_scope_violation",
                idempotency_key=idempotency_key,
                binding=binding,
            )

    async def _require_binder_workload(
        self, context: WorkflowPhysicalTransportRouteBinderContext
    ) -> None:
        if (
            context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience != WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDER_AUDIENCE
        ):
            await self._deny(
                context,
                result_code="workflow_physical_transport_route_binding_binder_identity_required",
            )

    async def _deny(
        self,
        context: WorkflowPhysicalTransportRouteBinderContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
        binding: WorkflowEventPhysicalTransportRouteBinding | None = None,
    ) -> NoReturn:
        await self._audit(
            context,
            event_kind="denied",
            outcome="denied",
            result_code=result_code,
            idempotency_key=idempotency_key,
            binding=binding,
        )
        raise WorkflowEventPhysicalTransportRouteBindingError(
            result_code, "The workflow physical transport route binding request was denied."
        )

    async def _audit(
        self,
        context: WorkflowPhysicalTransportRouteBinderContext,
        *,
        event_kind: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        binding: WorkflowEventPhysicalTransportRouteBinding | None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=f"atlas.workflow.physical-transport-route-binding.{event_kind}",
                schema_version="1.0",
                producer=WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDING_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.physical-transport-route-bindings.bind",
                resource_type="resource.workflow-physical-transport-route-binding",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-physical-transport-route-binding",
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    ("binding_id", "none" if binding is None else binding.binding_id),
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
            raise WorkflowEventPhysicalTransportRouteBindingError(
                f"workflow_physical_transport_route_binding_{name}_invalid",
                f"{name} is invalid.",
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowEventPhysicalTransportRouteBindingError(
                "workflow_physical_transport_route_binding_idempotency_key_invalid",
                "The idempotency key is invalid.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise WorkflowEventPhysicalTransportRouteBindingError(
                f"workflow_physical_transport_route_binding_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value


__all__ = [
    "WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDER_AUDIENCE",
    "WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDING_PRODUCER",
    "WorkflowEventPhysicalTransportRouteBindingService",
    "WorkflowPhysicalTransportRouteBinderContext",
]

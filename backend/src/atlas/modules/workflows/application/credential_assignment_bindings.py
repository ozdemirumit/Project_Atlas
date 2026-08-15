from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.credential_assignment_binding_ports import (
    WorkflowTransportCredentialAssignmentBindingError,
    WorkflowTransportCredentialAssignmentBindingRepository,
    WorkflowTransportCredentialAssignmentBindingRequest,
    WorkflowTransportCredentialAssignmentBindingStatus,
)
from atlas.modules.workflows.domain import (
    EventPhysicalTransportCredentialAssignmentSnapshot,
    EventPhysicalTransportCredentialAssignmentSnapshotState,
    EventPhysicalTransportRouteSnapshot,
    EventPhysicalTransportRouteSnapshotState,
    WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingAuthority,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingPolicy,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingState,
    WorkflowEventPhysicalTransportRouteBinding,
    WorkflowEventPhysicalTransportRouteBindingState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_credential_assignment_binding_policy,
)

WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_BINDER_AUDIENCE = (
    "audience.workflow-physical-transport-credential-binder"
)
_WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_BINDING_PRODUCER = (
    "project-atlas-workflow-physical-transport-credential-binder"
)


@dataclass(frozen=True, slots=True)
class WorkflowPhysicalTransportCredentialBinderContext:
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
            raise ValueError("credential binder context contains an invalid identifier")
        if self.requested_at.tzinfo is None:
            raise ValueError("credential binding requested_at must be timezone-aware")


class WorkflowEventPhysicalTransportCredentialAssignmentBindingService:
    """Binds immutable route and assignment evidence without opening a credential."""

    def __init__(
        self,
        *,
        binding_repository: WorkflowTransportCredentialAssignmentBindingRepository,
        audit_sink: AuditSink,
        policy: WorkflowEventPhysicalTransportCredentialAssignmentBindingPolicy | None = None,
    ) -> None:
        self._repository = binding_repository
        self._audit_sink = audit_sink
        self._policy = (
            policy
            or code_owned_workflow_event_physical_transport_credential_assignment_binding_policy()
        )

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def repository(self) -> WorkflowTransportCredentialAssignmentBindingRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowEventPhysicalTransportCredentialAssignmentBindingPolicy:
        return self._policy

    async def bind(
        self,
        *,
        physical_transport_route_binding_id: str,
        physical_transport_route_binding_digest: str,
        credential_assignment_snapshot_id: str,
        credential_assignment_snapshot_digest: str,
        policy_id: str,
        policy_version: str,
        policy_digest: str,
        idempotency_key: str,
        context: WorkflowPhysicalTransportCredentialBinderContext,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentBinding:
        await self._require_binder_workload(context)
        try:
            route_binding_id = self._identifier(
                physical_transport_route_binding_id,
                "physical_transport_route_binding_id",
            )
            route_binding_digest = self._digest(
                physical_transport_route_binding_digest,
                "physical_transport_route_binding_digest",
            )
            assignment_snapshot_id = self._identifier(
                credential_assignment_snapshot_id,
                "credential_assignment_snapshot_id",
            )
            assignment_snapshot_digest = self._digest(
                credential_assignment_snapshot_digest,
                "credential_assignment_snapshot_digest",
            )
            requested_policy_id = self._identifier(policy_id, "policy_id")
            requested_policy_version = self._identifier(policy_version, "policy_version")
            requested_policy_digest = self._digest(policy_digest, "policy_digest")
            normalized_key = self._idempotency_key(idempotency_key)
        except WorkflowTransportCredentialAssignmentBindingError as exc:
            await self._deny(context, result_code=exc.code)

        fingerprint = canonical_digest(
            {
                "binder_subject_id": context.subject_id,
                "credential_assignment_snapshot_digest": assignment_snapshot_digest,
                "credential_assignment_snapshot_id": assignment_snapshot_id,
                "physical_transport_route_binding_digest": route_binding_digest,
                "physical_transport_route_binding_id": route_binding_id,
                "scope": context.scope.canonical_value(),
            }
        )
        prior = await self._repository.get_credential_assignment_binding_request(
            scope=context.scope,
            binder_subject_id=context.subject_id,
            idempotency_key=normalized_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._deny(
                    context,
                    result_code=(
                        "workflow_transport_credential_assignment_binding_idempotency_conflict"
                    ),
                    idempotency_key=normalized_key,
                    binding=prior.binding,
                )
            await self._validate_historical_or_deny(
                prior.binding,
                expected_route_binding_id=route_binding_id,
                expected_route_binding_digest=route_binding_digest,
                expected_assignment_snapshot_id=assignment_snapshot_id,
                expected_assignment_snapshot_digest=assignment_snapshot_digest,
                context=context,
                idempotency_key=normalized_key,
            )
            await self._audit_committed_result(
                context,
                event_kind="replay",
                result_code="workflow_transport_credential_assignment_binding_replayed",
                idempotency_key=normalized_key,
                binding=prior.binding,
            )
            return prior.binding

        if (
            requested_policy_id != self._policy.policy_id
            or requested_policy_version != self._policy.policy_version
            or requested_policy_digest != self._policy.canonical_digest
            or canonical_digest(self._policy.digest_payload()) != self._policy.canonical_digest
        ):
            await self._deny(
                context,
                result_code="workflow_transport_credential_assignment_binding_policy_conflict",
                idempotency_key=normalized_key,
            )

        route_binding = await self._repository.get_physical_transport_route_binding_by_id(
            binding_id=route_binding_id
        )
        if route_binding is None:
            await self._deny(
                context,
                result_code="workflow_transport_credential_assignment_binding_evidence_conflict",
                idempotency_key=normalized_key,
            )
        route = await self._repository.get_transport_route_snapshot_by_id(
            snapshot_id=route_binding.transport_route_snapshot_id
        )
        assignment = await self._repository.get_credential_assignment_snapshot_by_id(
            snapshot_id=assignment_snapshot_id
        )
        if route is None or assignment is None:
            await self._deny(
                context,
                result_code="workflow_transport_credential_assignment_binding_evidence_conflict",
                idempotency_key=normalized_key,
                route_binding=route_binding,
            )
        await self._validate_sources_or_deny(
            route_binding,
            route,
            assignment,
            expected_route_binding_digest=route_binding_digest,
            expected_assignment_snapshot_digest=assignment_snapshot_digest,
            context=context,
            idempotency_key=normalized_key,
        )

        current = await self._repository.get_credential_assignment_binding(
            physical_transport_route_binding_id=route_binding.binding_id,
            credential_assignment_snapshot_id=assignment.snapshot_id,
        )
        if current is not None:
            await self._deny(
                context,
                result_code=(
                    "workflow_transport_credential_assignment_binding_competing_identity"
                    if current.binder_subject_id != context.subject_id
                    else "workflow_transport_credential_assignment_binding_already_bound"
                ),
                idempotency_key=normalized_key,
                route_binding=route_binding,
                assignment=assignment,
                binding=current,
            )

        candidate = self._build_binding(
            route_binding=route_binding,
            route=route,
            assignment=assignment,
            binder_subject_id=context.subject_id,
            bound_at=context.requested_at,
        )
        await self._audit_required(
            context,
            event_kind="intent",
            outcome="authorized",
            result_code="workflow_transport_credential_assignment_binding_persistence_authorized",
            idempotency_key=normalized_key,
            route_binding=route_binding,
            assignment=assignment,
            binding=candidate,
        )

        async def required_precommit_audit() -> None:
            await self._audit(
                context,
                event_kind="commit-authorization",
                outcome="authorized",
                result_code=("workflow_transport_credential_assignment_binding_commit_authorized"),
                idempotency_key=normalized_key,
                route_binding=route_binding,
                assignment=assignment,
                binding=candidate,
            )

        result = await self._repository.bind_credential_assignment(
            WorkflowTransportCredentialAssignmentBindingRequest(
                expected_physical_transport_route_binding_id=route_binding.binding_id,
                expected_physical_transport_route_binding_digest=route_binding.canonical_digest,
                expected_transport_route_snapshot_id=route.snapshot_id,
                expected_transport_route_snapshot_digest=route.canonical_digest,
                expected_credential_assignment_snapshot_id=assignment.snapshot_id,
                expected_credential_assignment_snapshot_digest=assignment.canonical_digest,
                expected_policy_digest=self._policy.canonical_digest,
                scope=context.scope,
                binder_subject_id=context.subject_id,
                requested_at=context.requested_at,
                candidate=candidate,
                idempotency_key=normalized_key,
                request_fingerprint=fingerprint,
                required_precommit_audit=required_precommit_audit,
            )
        )
        if (
            result.status is WorkflowTransportCredentialAssignmentBindingStatus.BOUND
            and result.binding is not None
        ):
            await self._validate_binding_or_deny(
                result.binding,
                route_binding=route_binding,
                route=route,
                assignment=assignment,
                context=context,
                idempotency_key=normalized_key,
            )
            await self._audit_committed_result(
                context,
                event_kind="completion",
                result_code="workflow_transport_credential_assignment_binding_created",
                idempotency_key=normalized_key,
                route_binding=route_binding,
                assignment=assignment,
                binding=result.binding,
            )
            return result.binding
        if (
            result.status is WorkflowTransportCredentialAssignmentBindingStatus.REPLAY
            and result.binding is not None
        ):
            await self._validate_historical_or_deny(
                result.binding,
                expected_route_binding_id=route_binding_id,
                expected_route_binding_digest=route_binding_digest,
                expected_assignment_snapshot_id=assignment_snapshot_id,
                expected_assignment_snapshot_digest=assignment_snapshot_digest,
                context=context,
                idempotency_key=normalized_key,
            )
            await self._audit_committed_result(
                context,
                event_kind="replay",
                result_code="workflow_transport_credential_assignment_binding_replayed",
                idempotency_key=normalized_key,
                route_binding=route_binding,
                assignment=assignment,
                binding=result.binding,
            )
            return result.binding

        result_code = {
            WorkflowTransportCredentialAssignmentBindingStatus.IDEMPOTENCY_CONFLICT: (
                "workflow_transport_credential_assignment_binding_idempotency_conflict"
            ),
            WorkflowTransportCredentialAssignmentBindingStatus.EVIDENCE_CONFLICT: (
                "workflow_transport_credential_assignment_binding_evidence_conflict"
            ),
            WorkflowTransportCredentialAssignmentBindingStatus.ALREADY_BOUND: (
                "workflow_transport_credential_assignment_binding_already_bound"
            ),
            WorkflowTransportCredentialAssignmentBindingStatus.PRECOMMIT_AUDIT_FAILED: (
                "workflow_transport_credential_assignment_binding_precommit_audit_failed"
            ),
        }.get(
            result.status,
            "workflow_transport_credential_assignment_binding_repository_contract_violation",
        )
        await self._deny(
            context,
            result_code=result_code,
            idempotency_key=normalized_key,
            route_binding=route_binding,
            assignment=assignment,
            binding=result.binding,
        )

    async def _validate_sources_or_deny(
        self,
        route_binding: WorkflowEventPhysicalTransportRouteBinding,
        route: EventPhysicalTransportRouteSnapshot,
        assignment: EventPhysicalTransportCredentialAssignmentSnapshot,
        *,
        expected_route_binding_digest: str,
        expected_assignment_snapshot_digest: str,
        context: WorkflowPhysicalTransportCredentialBinderContext,
        idempotency_key: str,
    ) -> None:
        valid = (
            route_binding.canonical_digest == expected_route_binding_digest
            and canonical_digest(route_binding.digest_payload()) == route_binding.canonical_digest
            and route_binding.scope == context.scope
            and route_binding.state is WorkflowEventPhysicalTransportRouteBindingState.BOUND
            and not any(route_binding.authority.canonical_value().values())
            and route.snapshot_id == route_binding.transport_route_snapshot_id
            and route.canonical_digest == route_binding.transport_route_snapshot_digest
            and canonical_digest(route.digest_payload()) == route.canonical_digest
            and route.scope == context.scope
            and route.state is EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED
            and not any(route.authority.canonical_value().values())
            and assignment.canonical_digest == expected_assignment_snapshot_digest
            and canonical_digest(assignment.digest_payload()) == assignment.canonical_digest
            and assignment.scope == context.scope
            and assignment.state
            is EventPhysicalTransportCredentialAssignmentSnapshotState.SNAPSHOTTED
            and not any(assignment.authority.canonical_value().values())
        )
        chain_valid = (
            assignment.route_snapshot_id == route.snapshot_id
            and assignment.route_id == route.route_id
            and assignment.route_revision == route.route_revision
            and assignment.source_route_digest == route.source_route_digest
            and assignment.credential_requirement_profile_id
            == route.credential_requirement_profile_id
            and assignment.credential_requirement_profile_version
            == route.credential_requirement_profile_version
            and assignment.credential_requirement_profile_digest
            == route.credential_requirement_profile_digest
            and assignment.authentication_mechanism_class == route.authentication_mechanism_class
            and assignment.principal_class == route.principal_class
            and assignment.privilege_class == self._policy.required_privilege_class
            and assignment.credential_generation > 0
            and assignment.rotation_epoch > 0
        )
        if not valid or not chain_valid:
            await self._deny(
                context,
                result_code="workflow_transport_credential_assignment_binding_evidence_conflict",
                idempotency_key=idempotency_key,
                route_binding=route_binding,
                assignment=assignment,
            )

    def _build_binding(
        self,
        *,
        route_binding: WorkflowEventPhysicalTransportRouteBinding,
        route: EventPhysicalTransportRouteSnapshot,
        assignment: EventPhysicalTransportCredentialAssignmentSnapshot,
        binder_subject_id: str,
        bound_at: datetime,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentBinding:
        binding_id = (
            "workflow-event-physical-transport-credential-assignment-binding."
            + sha256(
                (
                    f"{route_binding.binding_id}:{route_binding.canonical_digest}:"
                    f"{assignment.snapshot_id}:{assignment.canonical_digest}:"
                    f"{self._policy.canonical_digest}"
                ).encode()
            ).hexdigest()[:24]
        )
        values: dict[str, object] = {
            "binding_id": binding_id,
            "physical_transport_route_binding_id": route_binding.binding_id,
            "physical_transport_route_binding_digest": route_binding.canonical_digest,
            "transport_route_snapshot_id": route.snapshot_id,
            "transport_route_snapshot_digest": route.canonical_digest,
            "credential_assignment_snapshot_id": assignment.snapshot_id,
            "credential_assignment_snapshot_digest": assignment.canonical_digest,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "scope": route_binding.scope,
            "binder_subject_id": binder_subject_id,
            "bound_at": bound_at,
            "state": WorkflowEventPhysicalTransportCredentialAssignmentBindingState.BOUND,
            "authority": WorkflowEventPhysicalTransportCredentialAssignmentBindingAuthority(),
        }
        digest_payload = {
            key: value.canonical_value()
            if isinstance(
                value,
                (
                    WorkflowEventPhysicalTransportCredentialAssignmentBindingAuthority,
                    WorkflowScope,
                ),
            )
            else value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(
                value,
                WorkflowEventPhysicalTransportCredentialAssignmentBindingState,
            )
            else value
            for key, value in values.items()
        }
        return WorkflowEventPhysicalTransportCredentialAssignmentBinding(
            **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
        )

    async def _validate_binding_or_deny(
        self,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
        *,
        route_binding: WorkflowEventPhysicalTransportRouteBinding,
        route: EventPhysicalTransportRouteSnapshot,
        assignment: EventPhysicalTransportCredentialAssignmentSnapshot,
        context: WorkflowPhysicalTransportCredentialBinderContext,
        idempotency_key: str,
    ) -> None:
        expected = self._build_binding(
            route_binding=route_binding,
            route=route,
            assignment=assignment,
            binder_subject_id=binding.binder_subject_id,
            bound_at=binding.bound_at,
        )
        if binding != expected:
            await self._deny(
                context,
                result_code=(
                    "workflow_transport_credential_assignment_binding_repository_scope_violation"
                ),
                idempotency_key=idempotency_key,
                route_binding=route_binding,
                assignment=assignment,
                binding=binding,
            )
        await self._validate_historical_or_deny(
            binding,
            expected_route_binding_id=route_binding.binding_id,
            expected_route_binding_digest=route_binding.canonical_digest,
            expected_assignment_snapshot_id=assignment.snapshot_id,
            expected_assignment_snapshot_digest=assignment.canonical_digest,
            context=context,
            idempotency_key=idempotency_key,
        )

    async def _validate_historical_or_deny(
        self,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
        *,
        expected_route_binding_id: str,
        expected_route_binding_digest: str,
        expected_assignment_snapshot_id: str,
        expected_assignment_snapshot_digest: str,
        context: WorkflowPhysicalTransportCredentialBinderContext,
        idempotency_key: str,
    ) -> None:
        expected_id = (
            "workflow-event-physical-transport-credential-assignment-binding."
            + sha256(
                (
                    f"{expected_route_binding_id}:{expected_route_binding_digest}:"
                    f"{expected_assignment_snapshot_id}:{expected_assignment_snapshot_digest}:"
                    f"{binding.policy_digest}"
                ).encode()
            ).hexdigest()[:24]
        )
        authorities = (
            binding.grants_endpoint_resolution_authority,
            binding.grants_protected_artifact_access_authority,
            binding.grants_route_selection_authority,
            binding.grants_route_binding_authority,
            binding.grants_credential_selection_authority,
            binding.grants_credential_assignment_binding_authority,
            binding.grants_credential_access_authority,
            binding.grants_credential_brokerage_authority,
            binding.grants_credential_resolution_authority,
            binding.grants_credential_delivery_authority,
            binding.grants_network_access_authority,
            binding.grants_readiness_probe_authority,
            binding.grants_publication_authority,
            binding.grants_delivery_authority,
            binding.grants_dispatch_authority,
            binding.grants_execution_authority,
            binding.grants_infrastructure_mutation_authority,
        )
        if (
            binding.binding_id != expected_id
            or binding.physical_transport_route_binding_id != expected_route_binding_id
            or binding.physical_transport_route_binding_digest != expected_route_binding_digest
            or binding.credential_assignment_snapshot_id != expected_assignment_snapshot_id
            or binding.credential_assignment_snapshot_digest != expected_assignment_snapshot_digest
            or binding.scope != context.scope
            or binding.binder_subject_id != context.subject_id
            or binding.bound_at > context.requested_at
            or binding.state
            is not WorkflowEventPhysicalTransportCredentialAssignmentBindingState.BOUND
            or canonical_digest(binding.digest_payload()) != binding.canonical_digest
            or any(binding.authority.canonical_value().values())
            or any(authorities)
        ):
            await self._deny(
                context,
                result_code=(
                    "workflow_transport_credential_assignment_binding_repository_scope_violation"
                ),
                idempotency_key=idempotency_key,
                binding=binding,
            )

    async def _require_binder_workload(
        self,
        context: WorkflowPhysicalTransportCredentialBinderContext,
    ) -> None:
        if (
            context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience != WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_BINDER_AUDIENCE
        ):
            await self._deny(
                context,
                result_code=(
                    "workflow_transport_credential_assignment_binding_binder_identity_required"
                ),
            )

    async def _audit_committed_result(
        self,
        context: WorkflowPhysicalTransportCredentialBinderContext,
        *,
        event_kind: str,
        result_code: str,
        idempotency_key: str,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
        route_binding: WorkflowEventPhysicalTransportRouteBinding | None = None,
        assignment: EventPhysicalTransportCredentialAssignmentSnapshot | None = None,
    ) -> None:
        try:
            await self._audit(
                context,
                event_kind=event_kind,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                route_binding=route_binding,
                assignment=assignment,
                binding=binding,
            )
        except Exception as exc:
            raise WorkflowTransportCredentialAssignmentBindingError(
                "workflow_transport_credential_assignment_binding_completion_audit_outcome_uncertain",
                "The immutable binding is committed but its completion audit is unavailable.",
            ) from exc

    async def _deny(
        self,
        context: WorkflowPhysicalTransportCredentialBinderContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
        route_binding: WorkflowEventPhysicalTransportRouteBinding | None = None,
        assignment: EventPhysicalTransportCredentialAssignmentSnapshot | None = None,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding | None = None,
    ) -> NoReturn:
        try:
            await self._audit(
                context,
                event_kind="denied",
                outcome="denied",
                result_code=result_code,
                idempotency_key=idempotency_key,
                route_binding=route_binding,
                assignment=assignment,
                binding=binding,
            )
        except Exception as exc:
            raise WorkflowTransportCredentialAssignmentBindingError(
                "workflow_transport_credential_assignment_binding_audit_unavailable",
                "Required credential-assignment binding audit evidence is unavailable.",
            ) from exc
        raise WorkflowTransportCredentialAssignmentBindingError(
            result_code,
            "The workflow physical transport credential assignment binding was denied.",
        )

    async def _audit_required(
        self,
        context: WorkflowPhysicalTransportCredentialBinderContext,
        *,
        event_kind: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        route_binding: WorkflowEventPhysicalTransportRouteBinding | None,
        assignment: EventPhysicalTransportCredentialAssignmentSnapshot | None,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding | None,
    ) -> None:
        try:
            await self._audit(
                context,
                event_kind=event_kind,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                route_binding=route_binding,
                assignment=assignment,
                binding=binding,
            )
        except Exception as exc:
            raise WorkflowTransportCredentialAssignmentBindingError(
                "workflow_transport_credential_assignment_binding_audit_unavailable",
                "Required credential-assignment binding audit evidence is unavailable.",
            ) from exc

    async def _audit(
        self,
        context: WorkflowPhysicalTransportCredentialBinderContext,
        *,
        event_kind: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        route_binding: WorkflowEventPhysicalTransportRouteBinding | None,
        assignment: EventPhysicalTransportCredentialAssignmentSnapshot | None,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding | None,
    ) -> None:
        route_binding_id = (
            route_binding.binding_id
            if route_binding is not None
            else binding.physical_transport_route_binding_id
            if binding is not None
            else "none"
        )
        assignment_snapshot_id = (
            assignment.snapshot_id
            if assignment is not None
            else binding.credential_assignment_snapshot_id
            if binding is not None
            else "none"
        )
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=(
                    f"atlas.workflow.physical-transport-credential-assignment-binding.{event_kind}"
                ),
                schema_version="1.0",
                producer=_WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_BINDING_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id=("workflow.physical-transport-credential-assignment-bindings.bind"),
                resource_type=(
                    "resource.workflow-physical-transport-credential-assignment-binding"
                ),
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-physical-transport-credential-assignment-binding",
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    ("binding_id", "none" if binding is None else binding.binding_id),
                    (
                        "physical_transport_route_binding_id",
                        route_binding_id,
                    ),
                    (
                        "credential_assignment_snapshot_id",
                        assignment_snapshot_id,
                    ),
                    ("endpoint_resolution_authority", "false"),
                    ("protected_artifact_access_authority", "false"),
                    ("route_selection_authority", "false"),
                    ("route_binding_authority", "false"),
                    ("credential_selection_authority", "false"),
                    ("credential_assignment_binding_authority", "false"),
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
            raise WorkflowTransportCredentialAssignmentBindingError(
                f"workflow_transport_credential_assignment_binding_{name}_invalid",
                f"{name} is invalid.",
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowTransportCredentialAssignmentBindingError(
                "workflow_transport_credential_assignment_binding_idempotency_key_invalid",
                "The idempotency key is invalid.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise WorkflowTransportCredentialAssignmentBindingError(
                f"workflow_transport_credential_assignment_binding_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value


__all__ = [
    "WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_BINDER_AUDIENCE",
    "WorkflowEventPhysicalTransportCredentialAssignmentBindingService",
    "WorkflowPhysicalTransportCredentialBinderContext",
]

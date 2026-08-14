from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.route_freshness_admission_ports import (
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionError,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionRepository,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus,
)
from atlas.modules.workflows.domain import (
    DeploymentEventTransportRouteSelectionHead,
    EventPhysicalTransportRouteSnapshot,
    EventPhysicalTransportRouteSnapshotState,
    WorkflowEventPhysicalTransportRouteBinding,
    WorkflowEventPhysicalTransportRouteBindingState,
    WorkflowEventPhysicalTransportRouteFreshnessAdmission,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionAuthority,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionState,
    WorkflowEventPhysicalTransportRouteFreshnessPolicy,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_route_freshness_policy,
)

WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMITTER_AUDIENCE = (
    "audience.workflow-physical-transport-route-freshness-admitter"
)
WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMISSION_PRODUCER = (
    "project-atlas-workflow-physical-route-freshness-admitter"
)


@dataclass(frozen=True, slots=True)
class WorkflowPhysicalTransportRouteFreshnessAdmitterContext:
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
            raise ValueError("route freshness admitter context contains an invalid identifier")
        if self.requested_at.tzinfo is None:
            raise ValueError("route freshness admission requested_at must be timezone-aware")


class WorkflowEventPhysicalTransportRouteFreshnessAdmissionService:
    """Admits point-in-time route currentness without resolving or operating the route."""

    def __init__(
        self,
        *,
        admission_repository: WorkflowEventPhysicalTransportRouteFreshnessAdmissionRepository,
        audit_sink: AuditSink,
        policy: WorkflowEventPhysicalTransportRouteFreshnessPolicy | None = None,
    ) -> None:
        self._repository = admission_repository
        self._audit_sink = audit_sink
        self._policy = (
            policy or code_owned_workflow_event_physical_transport_route_freshness_policy()
        )

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def repository(self) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowEventPhysicalTransportRouteFreshnessPolicy:
        return self._policy

    async def admit(
        self,
        *,
        physical_transport_route_binding_id: str,
        physical_transport_route_binding_digest: str,
        policy_id: str,
        policy_version: str,
        idempotency_key: str,
        context: WorkflowPhysicalTransportRouteFreshnessAdmitterContext,
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmission:
        await self._require_admitter_workload(context)
        try:
            binding_id = self._identifier(
                physical_transport_route_binding_id, "physical_route_binding_id"
            )
            binding_digest = self._digest(
                physical_transport_route_binding_digest,
                "physical_route_binding_digest",
            )
            requested_policy_id = self._identifier(policy_id, "policy_id")
            requested_policy_version = self._identifier(policy_version, "policy_version")
            normalized_key = self._idempotency_key(idempotency_key)
        except WorkflowEventPhysicalTransportRouteFreshnessAdmissionError as exc:
            await self._deny(context, result_code=exc.code)

        if (
            requested_policy_id != self._policy.policy_id
            or requested_policy_version != self._policy.policy_version
            or canonical_digest(self._policy.digest_payload()) != self._policy.canonical_digest
            or not self._policy.unique_current_head_required
            or not self._policy.monotonic_generation_required
        ):
            await self._deny(
                context,
                result_code="workflow_physical_transport_route_freshness_policy_conflict",
                idempotency_key=normalized_key,
            )

        binding = await self._repository.get_physical_transport_route_binding_by_id(
            binding_id=binding_id
        )
        if binding is None:
            await self._deny_evidence(context, normalized_key)
        await self._validate_binding_or_deny(
            binding,
            expected_digest=binding_digest,
            context=context,
            idempotency_key=normalized_key,
        )

        route = await self._repository.get_transport_route_snapshot_by_id(
            snapshot_id=binding.transport_route_snapshot_id
        )
        if route is None:
            await self._deny_evidence(context, normalized_key)
        await self._validate_route_or_deny(
            binding,
            route,
            context=context,
            idempotency_key=normalized_key,
        )

        head = await self._repository.get_current_route_selection_head(
            scope=context.scope,
            route_set_id=route.route_set_id,
        )
        if head is None:
            await self._deny_evidence(context, normalized_key)
        await self._validate_head_or_deny(
            route,
            head,
            context=context,
            idempotency_key=normalized_key,
        )

        fingerprint = canonical_digest(
            {
                "admitter_subject_id": context.subject_id,
                "current_selection_head_digest": head.canonical_digest,
                "current_selection_head_fencing_token_digest": head.fencing_token_digest,
                "current_selection_head_generation": head.generation,
                "current_selection_head_id": head.head_id,
                "physical_transport_route_binding_digest": binding_digest,
                "physical_transport_route_binding_id": binding_id,
                "policy_digest": self._policy.canonical_digest,
                "scope": context.scope.canonical_value(),
                "transport_route_snapshot_digest": route.canonical_digest,
                "transport_route_snapshot_id": route.snapshot_id,
            }
        )
        prior = await self._repository.get_route_freshness_admission_request(
            scope=context.scope,
            admitter_subject_id=context.subject_id,
            idempotency_key=normalized_key,
        )
        if prior is not None:
            if not self._admission_remains_current(
                prior.admission,
                head=head,
                requested_at=context.requested_at,
            ):
                await self._deny(
                    context,
                    result_code=(
                        "workflow_physical_transport_route_freshness_admission_not_current"
                    ),
                    idempotency_key=normalized_key,
                    admission=prior.admission,
                )
            if prior.request_fingerprint != fingerprint:
                await self._deny(
                    context,
                    result_code=(
                        "workflow_physical_transport_route_freshness_idempotency_conflict"
                    ),
                    idempotency_key=normalized_key,
                    admission=prior.admission,
                )
            await self._validate_admission_or_deny(
                prior.admission,
                binding=binding,
                route=route,
                head=head,
                context=context,
                idempotency_key=normalized_key,
            )
            await self._audit(
                context,
                event_kind="replay",
                outcome="succeeded",
                result_code="workflow_physical_transport_route_freshness_admission_replayed",
                idempotency_key=normalized_key,
                admission=prior.admission,
            )
            return prior.admission

        current = await self._repository.get_route_freshness_admission(
            physical_transport_route_binding_id=binding.binding_id
        )
        if current is not None:
            await self._deny(
                context,
                result_code=(
                    "workflow_physical_transport_route_freshness_competing_identity"
                    if current.admitter_subject_id != context.subject_id
                    else "workflow_physical_transport_route_freshness_already_admitted"
                ),
                idempotency_key=normalized_key,
                admission=current,
            )

        candidate = self._build_admission(
            binding=binding,
            route=route,
            head=head,
            admitter_subject_id=context.subject_id,
            evaluated_at=context.requested_at,
        )
        await self._audit(
            context,
            event_kind="authorization",
            outcome="authorized",
            result_code=("workflow_physical_transport_route_freshness_persistence_authorized"),
            idempotency_key=normalized_key,
            admission=candidate,
        )
        result = await self._repository.admit_physical_transport_route_freshness(
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest(
                expected_physical_transport_route_binding_id=binding.binding_id,
                expected_physical_transport_route_binding_digest=binding.canonical_digest,
                expected_transport_route_snapshot_id=route.snapshot_id,
                expected_transport_route_snapshot_digest=route.canonical_digest,
                expected_current_selection_head_id=head.head_id,
                expected_current_selection_head_digest=head.canonical_digest,
                expected_current_selection_head_generation=head.generation,
                expected_current_selection_head_fencing_token_digest=(head.fencing_token_digest),
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
                expected_policy_digest=self._policy.canonical_digest,
                scope=context.scope,
                admitter_subject_id=context.subject_id,
                evaluated_at=context.requested_at,
                candidate=candidate,
                idempotency_key=normalized_key,
                request_fingerprint=fingerprint,
            )
        )
        if (
            result.status
            in {
                WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.ADMITTED_CURRENT,
                WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.REPLAY,
            }
            and result.admission is not None
        ):
            await self._validate_admission_or_deny(
                result.admission,
                binding=binding,
                route=route,
                head=head,
                context=context,
                idempotency_key=normalized_key,
            )
            if not self._admission_remains_current(
                result.admission,
                head=head,
                requested_at=context.requested_at,
            ):
                await self._deny(
                    context,
                    result_code=(
                        "workflow_physical_transport_route_freshness_admission_not_current"
                    ),
                    idempotency_key=normalized_key,
                    admission=result.admission,
                )
            return result.admission

        result_code = {
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.IDEMPOTENCY_CONFLICT: (
                "workflow_physical_transport_route_freshness_idempotency_conflict"
            ),
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.EVIDENCE_CONFLICT: (
                "workflow_physical_transport_route_freshness_evidence_conflict"
            ),
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.ALREADY_ADMITTED: (
                "workflow_physical_transport_route_freshness_already_admitted"
            ),
        }.get(
            result.status,
            "workflow_physical_transport_route_freshness_repository_contract_violation",
        )
        await self._deny(
            context,
            result_code=result_code,
            idempotency_key=normalized_key,
            admission=result.admission,
        )

    async def _validate_binding_or_deny(
        self,
        binding: WorkflowEventPhysicalTransportRouteBinding,
        *,
        expected_digest: str,
        context: WorkflowPhysicalTransportRouteFreshnessAdmitterContext,
        idempotency_key: str,
    ) -> None:
        if (
            binding.canonical_digest != expected_digest
            or canonical_digest(binding.digest_payload()) != binding.canonical_digest
            or binding.scope != context.scope
            or binding.state is not WorkflowEventPhysicalTransportRouteBindingState.BOUND
            or binding.bound_at > context.requested_at
            or any(binding.authority.canonical_value().values())
        ):
            await self._deny_evidence(context, idempotency_key)

    async def _validate_route_or_deny(
        self,
        binding: WorkflowEventPhysicalTransportRouteBinding,
        route: EventPhysicalTransportRouteSnapshot,
        *,
        context: WorkflowPhysicalTransportRouteFreshnessAdmitterContext,
        idempotency_key: str,
    ) -> None:
        if (
            route.snapshot_id != binding.transport_route_snapshot_id
            or route.canonical_digest != binding.transport_route_snapshot_digest
            or canonical_digest(route.digest_payload()) != route.canonical_digest
            or route.scope != binding.scope
            or route.state is not EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED
            or route.captured_at > binding.bound_at
            or any(route.authority.canonical_value().values())
        ):
            await self._deny_evidence(context, idempotency_key)

    async def _validate_head_or_deny(
        self,
        route: EventPhysicalTransportRouteSnapshot,
        head: DeploymentEventTransportRouteSelectionHead,
        *,
        context: WorkflowPhysicalTransportRouteFreshnessAdmitterContext,
        idempotency_key: str,
    ) -> None:
        if (
            canonical_digest(head.digest_payload()) != head.canonical_digest
            or head.scope != context.scope
            or head.current is not True
            or head.generation < 1
            or head.selection_active is not True
            or head.selection_eligible is not True
            or head.selection_suspended
            or head.selection_withdrawn
            or head.selection_superseded
            or head.route_set_id != route.route_set_id
            or head.route_set_revision != route.route_set_revision
            or head.selection_epoch_id != route.selection_epoch_id
            or head.selection_epoch_revision != route.selection_epoch_revision
            or head.selected_route_id != route.route_id
            or head.selected_route_revision != route.route_revision
            or head.selected_route_digest != route.source_route_digest
        ):
            await self._deny_evidence(context, idempotency_key)

    def _build_admission(
        self,
        *,
        binding: WorkflowEventPhysicalTransportRouteBinding,
        route: EventPhysicalTransportRouteSnapshot,
        head: DeploymentEventTransportRouteSelectionHead,
        admitter_subject_id: str,
        evaluated_at: datetime,
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmission:
        admission_id = (
            "workflow-event-physical-transport-route-freshness-admission."
            + sha256(
                f"{binding.canonical_digest}:{route.canonical_digest}:"
                f"{head.canonical_digest}:{self._policy.canonical_digest}:"
                f"{evaluated_at.isoformat()}".encode()
            ).hexdigest()[:24]
        )
        values: dict[str, object] = {
            "freshness_admission_id": admission_id,
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
            "scope": binding.scope,
            "admitter_subject_id": admitter_subject_id,
            "evaluated_at": evaluated_at,
            "valid_until": evaluated_at + timedelta(seconds=self._policy.validity_window_seconds),
            "state": (WorkflowEventPhysicalTransportRouteFreshnessAdmissionState.ADMITTED_CURRENT),
            "authority": WorkflowEventPhysicalTransportRouteFreshnessAdmissionAuthority(),
        }
        digest_payload = {
            key: value.canonical_value()
            if isinstance(
                value,
                (
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionAuthority,
                    WorkflowScope,
                ),
            )
            else value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, WorkflowEventPhysicalTransportRouteFreshnessAdmissionState)
            else value
            for key, value in values.items()
        }
        return WorkflowEventPhysicalTransportRouteFreshnessAdmission(
            **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
        )

    async def _validate_admission_or_deny(
        self,
        admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission,
        *,
        binding: WorkflowEventPhysicalTransportRouteBinding,
        route: EventPhysicalTransportRouteSnapshot,
        head: DeploymentEventTransportRouteSelectionHead,
        context: WorkflowPhysicalTransportRouteFreshnessAdmitterContext,
        idempotency_key: str,
    ) -> None:
        expected = self._build_admission(
            binding=binding,
            route=route,
            head=head,
            admitter_subject_id=admission.admitter_subject_id,
            evaluated_at=admission.evaluated_at,
        )
        authorities = (
            admission.grants_endpoint_resolution_authority,
            admission.grants_route_selection_authority,
            admission.grants_route_binding_authority,
            admission.grants_credential_access_authority,
            admission.grants_network_access_authority,
            admission.grants_readiness_probe_authority,
            admission.grants_publication_authority,
            admission.grants_delivery_authority,
            admission.grants_dispatch_authority,
            admission.grants_execution_authority,
        )
        if (
            admission != expected
            or admission.scope != context.scope
            or admission.admitter_subject_id != context.subject_id
            or admission.evaluated_at > context.requested_at
            or admission.state
            is not WorkflowEventPhysicalTransportRouteFreshnessAdmissionState.ADMITTED_CURRENT
            or canonical_digest(admission.digest_payload()) != admission.canonical_digest
            or any(admission.authority.canonical_value().values())
            or any(authorities)
        ):
            await self._deny(
                context,
                result_code=(
                    "workflow_physical_transport_route_freshness_repository_scope_violation"
                ),
                idempotency_key=idempotency_key,
                admission=admission,
            )

    @staticmethod
    def _admission_remains_current(
        admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission,
        *,
        head: DeploymentEventTransportRouteSelectionHead,
        requested_at: datetime,
    ) -> bool:
        return (
            requested_at < admission.valid_until
            and admission.current_selection_head_id == head.head_id
            and admission.current_selection_head_digest == head.canonical_digest
            and admission.current_selection_head_generation == head.generation
            and admission.current_selection_head_fencing_token_digest == head.fencing_token_digest
            and admission.selected_route_id == head.selected_route_id
            and admission.selected_route_revision == head.selected_route_revision
            and admission.selected_route_digest == head.selected_route_digest
            and admission.selection_active == head.selection_active
            and admission.selection_eligible == head.selection_eligible
            and admission.selection_suspended == head.selection_suspended
            and admission.selection_withdrawn == head.selection_withdrawn
            and admission.selection_superseded == head.selection_superseded
        )

    async def _require_admitter_workload(
        self, context: WorkflowPhysicalTransportRouteFreshnessAdmitterContext
    ) -> None:
        if (
            context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience
            != WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMITTER_AUDIENCE
        ):
            await self._deny(
                context,
                result_code=(
                    "workflow_physical_transport_route_freshness_admitter_identity_required"
                ),
            )

    async def _deny_evidence(
        self,
        context: WorkflowPhysicalTransportRouteFreshnessAdmitterContext,
        idempotency_key: str,
    ) -> NoReturn:
        await self._deny(
            context,
            result_code="workflow_physical_transport_route_freshness_evidence_conflict",
            idempotency_key=idempotency_key,
        )

    async def _deny(
        self,
        context: WorkflowPhysicalTransportRouteFreshnessAdmitterContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
        admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission | None = None,
    ) -> NoReturn:
        await self._audit(
            context,
            event_kind="denied",
            outcome="denied",
            result_code=result_code,
            idempotency_key=idempotency_key,
            admission=admission,
        )
        raise WorkflowEventPhysicalTransportRouteFreshnessAdmissionError(
            result_code,
            "The workflow physical transport route freshness admission request was denied.",
        )

    async def _audit(
        self,
        context: WorkflowPhysicalTransportRouteFreshnessAdmitterContext,
        *,
        event_kind: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission | None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=f"atlas.workflow.physical-transport-route-freshness.{event_kind}",
                schema_version="1.0",
                producer=WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMISSION_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.physical-transport-route-freshness.admit",
                resource_type="resource.workflow-physical-transport-route-freshness-admission",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-physical-transport-route-freshness-admission",
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    (
                        "freshness_admission_id",
                        "none" if admission is None else admission.freshness_admission_id,
                    ),
                    (
                        "current_selection_head_generation",
                        "none"
                        if admission is None
                        else str(admission.current_selection_head_generation),
                    ),
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
            raise WorkflowEventPhysicalTransportRouteFreshnessAdmissionError(
                f"workflow_physical_transport_route_freshness_{name}_invalid",
                f"{name} is invalid.",
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowEventPhysicalTransportRouteFreshnessAdmissionError(
                "workflow_physical_transport_route_freshness_idempotency_key_invalid",
                "The idempotency key is invalid.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise WorkflowEventPhysicalTransportRouteFreshnessAdmissionError(
                f"workflow_physical_transport_route_freshness_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value


__all__ = [
    "WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMISSION_PRODUCER",
    "WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMITTER_AUDIENCE",
    "WorkflowEventPhysicalTransportRouteFreshnessAdmissionService",
    "WorkflowPhysicalTransportRouteFreshnessAdmitterContext",
]

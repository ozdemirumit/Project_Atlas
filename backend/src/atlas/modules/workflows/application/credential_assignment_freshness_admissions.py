from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.credential_assignment_freshness_admission_ports import (
    WorkflowTransportCredentialAssignmentFreshnessAdmissionError,
    WorkflowTransportCredentialAssignmentFreshnessAdmissionRepository,
    WorkflowTransportCredentialAssignmentFreshnessAdmissionRequest,
    WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus,
)
from atlas.modules.workflows.application.credential_assignment_snapshot_ports import (
    validate_workflow_transport_credential_assignment_snapshot,
)
from atlas.modules.workflows.domain import (
    DeploymentPhysicalTransportCredentialAssignment,
    EventPhysicalTransportCredentialAssignmentSnapshot,
    WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingState,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionAuthority,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionState,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessPolicy,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_credential_assignment_freshness_policy,
)

WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_AUDIENCE = (
    "audience.workflow-physical-transport-credential-assignment-freshness-admitter"
)
WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_SUBJECT = (
    "service.workflow-physical-transport-credential-assignment-freshness-admitter"
)
WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMISSION_PRODUCER = (
    "project-atlas-workflow-physical-transport-credential-assignment-freshness-admitter"
)


@dataclass(frozen=True, slots=True)
class WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmitterContext:
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
            raise ValueError("credential-assignment freshness context contains invalid evidence")
        if self.requested_at.tzinfo is None:
            raise ValueError("credential-assignment freshness requested_at must be timezone-aware")


class WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionService:
    """Admits bounded assignment currentness without opening credential material."""

    _ASSIGNMENT_FIELDS = (
        "assignment_id",
        "assignment_revision",
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
        admission_repository: (WorkflowTransportCredentialAssignmentFreshnessAdmissionRepository),
        audit_sink: AuditSink,
        policy: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessPolicy | None = None,
    ) -> None:
        self._repository = admission_repository
        self._audit_sink = audit_sink
        self._policy = (
            policy
            or code_owned_workflow_event_physical_transport_credential_assignment_freshness_policy()
        )

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def repository(
        self,
    ) -> WorkflowTransportCredentialAssignmentFreshnessAdmissionRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowEventPhysicalTransportCredentialAssignmentFreshnessPolicy:
        return self._policy

    async def admit(
        self,
        *,
        physical_transport_credential_assignment_binding_id: str,
        physical_transport_credential_assignment_binding_digest: str,
        policy_id: str,
        policy_version: str,
        idempotency_key: str,
        context: WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmitterContext,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission:
        await self._require_admitter_workload(context)
        try:
            binding_id = self._identifier(
                physical_transport_credential_assignment_binding_id,
                "credential_assignment_binding_id",
            )
            binding_digest = self._digest(
                physical_transport_credential_assignment_binding_digest,
                "credential_assignment_binding_digest",
            )
            requested_policy_id = self._identifier(policy_id, "policy_id")
            requested_policy_version = self._identifier(policy_version, "policy_version")
            normalized_key = self._idempotency_key(idempotency_key)
        except WorkflowTransportCredentialAssignmentFreshnessAdmissionError as exc:
            await self._deny(context, result_code=exc.code)

        if (
            requested_policy_id != self._policy.policy_id
            or requested_policy_version != self._policy.policy_version
            or canonical_digest(self._policy.digest_payload()) != self._policy.canonical_digest
            or not self._policy.unique_current_head_required
            or not self._policy.monotonic_rotation_rank_required
            or not self._policy.active_assignment_required
            or not self._policy.non_revoked_assignment_required
            or not self._policy.assignment_expiry_bound_required
        ):
            await self._deny(
                context,
                result_code=(
                    "workflow_physical_transport_credential_assignment_freshness_policy_conflict"
                ),
                idempotency_key=normalized_key,
            )

        binding = await self._repository.get_credential_assignment_binding_by_id(
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

        snapshot = await self._repository.get_credential_assignment_snapshot_by_id(
            snapshot_id=binding.credential_assignment_snapshot_id
        )
        if snapshot is None:
            await self._deny_evidence(context, normalized_key)
        await self._validate_snapshot_or_deny(
            binding,
            snapshot,
            context=context,
            idempotency_key=normalized_key,
        )

        head = await self._repository.get_current_credential_assignment_head(
            assignment_id=snapshot.assignment_id
        )
        if head is None:
            await self._deny_evidence(context, normalized_key)
        await self._validate_head_or_deny(
            snapshot,
            head,
            evaluated_at=context.requested_at,
            context=context,
            idempotency_key=normalized_key,
        )

        fingerprint = canonical_digest(
            {
                "admitter_subject_id": context.subject_id,
                "assignment_head_digest": head.canonical_digest,
                "assignment_revision": head.assignment_revision,
                "credential_assignment_binding_digest": binding_digest,
                "credential_assignment_binding_id": binding_id,
                "credential_assignment_snapshot_digest": snapshot.canonical_digest,
                "credential_assignment_snapshot_id": snapshot.snapshot_id,
                "credential_generation": head.credential_generation,
                "rotation_epoch": head.rotation_epoch,
                "scope": context.scope.canonical_value(),
            }
        )
        candidate = self._build_admission(
            binding=binding,
            snapshot=snapshot,
            head=head,
            admitter_subject_id=context.subject_id,
            evaluated_at=context.requested_at,
            idempotency_key=normalized_key,
        )
        await self._audit(
            context,
            event_kind="intent",
            outcome="requested",
            result_code=("workflow_physical_transport_credential_assignment_freshness_requested"),
            idempotency_key=normalized_key,
            admission=candidate,
            binding=binding,
            snapshot=snapshot,
        )

        async def required_precommit_audit() -> None:
            await self._audit(
                context,
                event_kind="authorization",
                outcome="authorized",
                result_code=(
                    "workflow_physical_transport_credential_assignment_freshness_persistence_authorized"
                ),
                idempotency_key=normalized_key,
                admission=candidate,
                binding=binding,
                snapshot=snapshot,
            )

        result = await self._repository.admit_credential_assignment_freshness(
            WorkflowTransportCredentialAssignmentFreshnessAdmissionRequest(
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
                scope=context.scope,
                admitter_subject_id=context.subject_id,
                requested_at=context.requested_at,
                candidate=candidate,
                idempotency_key=normalized_key,
                request_fingerprint=fingerprint,
                required_precommit_audit=required_precommit_audit,
            )
        )
        if (
            result.status
            is WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus.ADMITTED_CURRENT
        ):
            if result.admission is None:
                await self._deny_evidence(context, normalized_key)
            await self._validate_admission_or_deny(
                result.admission,
                binding=binding,
                snapshot=snapshot,
                head=head,
                context=context,
                idempotency_key=normalized_key,
            )
            await self._audit_committed_result(
                context,
                event_kind="created",
                result_code=(
                    "workflow_physical_transport_credential_assignment_freshness_admitted"
                ),
                idempotency_key=normalized_key,
                admission=result.admission,
                binding=binding,
                snapshot=snapshot,
            )
            return result.admission
        if result.status is WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus.REPLAY:
            if result.admission is None or not self._admission_remains_current(
                result.admission,
                head=head,
                requested_at=context.requested_at,
            ):
                await self._deny_evidence(context, normalized_key)
            await self._validate_admission_or_deny(
                result.admission,
                binding=binding,
                snapshot=snapshot,
                head=head,
                context=context,
                idempotency_key=normalized_key,
            )
            await self._audit(
                context,
                event_kind="replay",
                outcome="succeeded",
                result_code=(
                    "workflow_physical_transport_credential_assignment_freshness_replayed"
                ),
                idempotency_key=normalized_key,
                admission=result.admission,
                binding=binding,
                snapshot=snapshot,
            )
            return result.admission

        result_codes = {
            WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus.IDEMPOTENCY_CONFLICT: (
                "workflow_physical_transport_credential_assignment_freshness_idempotency_conflict"
            ),
            WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus.EVIDENCE_CONFLICT: (
                "workflow_physical_transport_credential_assignment_freshness_evidence_conflict"
            ),
            WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus.PRECOMMIT_AUDIT_FAILED: (
                "workflow_physical_transport_credential_assignment_freshness_audit_unavailable"
            ),
        }
        await self._deny(
            context,
            result_code=result_codes[result.status],
            idempotency_key=normalized_key,
            admission=result.admission,
            binding=binding,
            snapshot=snapshot,
        )

    async def list_admissions(
        self,
        *,
        scope: WorkflowScope,
        limit: int = 256,
    ) -> tuple[WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission, ...]:
        if not 1 <= limit <= 256:
            raise WorkflowTransportCredentialAssignmentFreshnessAdmissionError(
                "workflow_physical_transport_credential_assignment_freshness_limit_invalid",
                "The credential-assignment freshness admission limit is invalid.",
            )
        admissions = await self._repository.list_credential_assignment_freshness_admissions(
            scope=scope,
            limit=limit,
        )
        for admission in admissions:
            self._validate_historical_admission(admission, scope=scope)
        return admissions

    def _build_admission(
        self,
        *,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
        head: DeploymentPhysicalTransportCredentialAssignment,
        admitter_subject_id: str,
        evaluated_at: datetime,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission:
        admission_id = (
            "workflow-physical-transport-credential-assignment-freshness-admission."
            + sha256(
                (
                    f"{binding.binding_id}:{snapshot.snapshot_id}:{admitter_subject_id}:"
                    f"{idempotency_key}"
                ).encode()
            ).hexdigest()[:24]
        )
        values: dict[str, object] = {
            "freshness_admission_id": admission_id,
            "physical_transport_credential_assignment_binding_id": binding.binding_id,
            "physical_transport_credential_assignment_binding_digest": binding.canonical_digest,
            "credential_assignment_snapshot_id": snapshot.snapshot_id,
            "credential_assignment_snapshot_digest": snapshot.canonical_digest,
            "assignment_id": head.assignment_id,
            "assignment_revision": head.assignment_revision,
            "source_assignment_digest": head.canonical_digest,
            "credential_generation": head.credential_generation,
            "rotation_epoch": head.rotation_epoch,
            "assignment_activated_at": head.activated_at,
            "assignment_expires_at": head.expires_at,
            "assignment_active": head.active,
            "assignment_non_revoked": not head.revoked,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "scope": binding.scope,
            "admitter_subject_id": admitter_subject_id,
            "evaluated_at": evaluated_at,
            "valid_until": min(
                evaluated_at + timedelta(seconds=self._policy.validity_window_seconds),
                head.expires_at,
            ),
            "state": (
                WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionState.ADMITTED_CURRENT
            ),
            "authority": (
                WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionAuthority()
            ),
        }
        digest_payload = {
            key: value.canonical_value()
            if isinstance(
                value,
                (
                    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionAuthority,
                    WorkflowScope,
                ),
            )
            else value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(
                value,
                WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionState,
            )
            else value
            for key, value in values.items()
        }
        return WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission(
            **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
        )

    @staticmethod
    def _validate_binding(
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
        *,
        expected_digest: str,
        scope: WorkflowScope,
    ) -> None:
        if (
            binding.canonical_digest != expected_digest
            or binding.scope != scope
            or binding.state
            is not WorkflowEventPhysicalTransportCredentialAssignmentBindingState.BOUND
            or canonical_digest(binding.digest_payload()) != binding.canonical_digest
            or any(binding.authority.canonical_value().values())
        ):
            raise WorkflowTransportCredentialAssignmentFreshnessAdmissionError(
                "workflow_physical_transport_credential_assignment_freshness_evidence_conflict",
                "Credential-assignment binding evidence is invalid.",
            )

    @staticmethod
    def _validate_snapshot(
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
        *,
        scope: WorkflowScope,
    ) -> None:
        validate_workflow_transport_credential_assignment_snapshot(snapshot, scope=scope)
        if (
            binding.credential_assignment_snapshot_id != snapshot.snapshot_id
            or binding.credential_assignment_snapshot_digest != snapshot.canonical_digest
            or binding.transport_route_snapshot_id != snapshot.route_snapshot_id
            or binding.scope != snapshot.scope
        ):
            raise WorkflowTransportCredentialAssignmentFreshnessAdmissionError(
                "workflow_physical_transport_credential_assignment_freshness_evidence_conflict",
                "Credential-assignment snapshot evidence is invalid.",
            )

    @classmethod
    def _validate_head(
        cls,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
        head: DeploymentPhysicalTransportCredentialAssignment,
        *,
        scope: WorkflowScope,
        evaluated_at: datetime,
    ) -> None:
        expected_fields = {
            name: getattr(snapshot, name)
            for name in cls._ASSIGNMENT_FIELDS
            if name not in {"assignment_revision"}
        }
        if (
            head.scope != scope
            or head.assignment_revision != snapshot.assignment_revision
            or head.canonical_digest != snapshot.source_assignment_digest
            or any(getattr(head, name) != value for name, value in expected_fields.items())
            or canonical_digest(head.digest_payload()) != head.canonical_digest
            or not head.active
            or head.revoked
            or not head.activated_at <= evaluated_at < head.expires_at
        ):
            raise WorkflowTransportCredentialAssignmentFreshnessAdmissionError(
                "workflow_physical_transport_credential_assignment_freshness_not_current",
                "The bound credential assignment is not the admissible current head.",
            )

    @classmethod
    def _validate_admission(
        cls,
        admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
        *,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
        head: DeploymentPhysicalTransportCredentialAssignment,
        scope: WorkflowScope,
    ) -> None:
        cls._validate_historical_admission(admission, scope=scope)
        if (
            admission.physical_transport_credential_assignment_binding_id != binding.binding_id
            or admission.physical_transport_credential_assignment_binding_digest
            != binding.canonical_digest
            or admission.credential_assignment_snapshot_id != snapshot.snapshot_id
            or admission.credential_assignment_snapshot_digest != snapshot.canonical_digest
            or admission.assignment_id != head.assignment_id
            or admission.assignment_revision != head.assignment_revision
            or admission.source_assignment_digest != head.canonical_digest
            or admission.credential_generation != head.credential_generation
            or admission.rotation_epoch != head.rotation_epoch
            or admission.assignment_activated_at != head.activated_at
            or admission.assignment_expires_at != head.expires_at
            or admission.assignment_active != head.active
            or admission.assignment_non_revoked != (not head.revoked)
        ):
            raise WorkflowTransportCredentialAssignmentFreshnessAdmissionError(
                "workflow_physical_transport_credential_assignment_freshness_repository_scope_violation",
                "The repository returned invalid credential-assignment freshness evidence.",
            )

    @staticmethod
    def _validate_historical_admission(
        admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
        *,
        scope: WorkflowScope,
    ) -> None:
        if (
            admission.scope != scope
            or canonical_digest(admission.digest_payload()) != admission.canonical_digest
            or admission.state.value != "admitted_current"
            or admission.assignment_active is not True
            or admission.assignment_non_revoked is not True
            or admission.credential_generation < 1
            or admission.rotation_epoch < 1
            or not admission.assignment_activated_at
            <= admission.evaluated_at
            < admission.valid_until
            <= admission.assignment_expires_at
            or admission.valid_until - admission.evaluated_at > timedelta(seconds=60)
            or any(admission.authority.canonical_value().values())
        ):
            raise WorkflowTransportCredentialAssignmentFreshnessAdmissionError(
                "workflow_physical_transport_credential_assignment_freshness_repository_scope_violation",
                "Stored credential-assignment freshness evidence is invalid.",
            )

    @staticmethod
    def _admission_remains_current(
        admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
        *,
        head: DeploymentPhysicalTransportCredentialAssignment,
        requested_at: datetime,
    ) -> bool:
        return (
            requested_at < admission.valid_until
            and head.assignment_id == admission.assignment_id
            and head.assignment_revision == admission.assignment_revision
            and head.canonical_digest == admission.source_assignment_digest
            and head.credential_generation == admission.credential_generation
            and head.rotation_epoch == admission.rotation_epoch
            and head.activated_at == admission.assignment_activated_at
            and head.expires_at == admission.assignment_expires_at
            and head.active
            and not head.revoked
            and head.activated_at <= requested_at < head.expires_at
        )

    async def _validate_binding_or_deny(
        self,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
        *,
        expected_digest: str,
        context: WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmitterContext,
        idempotency_key: str,
    ) -> None:
        try:
            self._validate_binding(binding, expected_digest=expected_digest, scope=context.scope)
        except (ValueError, WorkflowTransportCredentialAssignmentFreshnessAdmissionError):
            await self._deny_evidence(context, idempotency_key, binding=binding)

    async def _validate_snapshot_or_deny(
        self,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
        *,
        context: WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmitterContext,
        idempotency_key: str,
    ) -> None:
        try:
            self._validate_snapshot(binding, snapshot, scope=context.scope)
        except (ValueError, WorkflowTransportCredentialAssignmentFreshnessAdmissionError):
            await self._deny_evidence(
                context,
                idempotency_key,
                binding=binding,
                snapshot=snapshot,
            )

    async def _validate_head_or_deny(
        self,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
        head: DeploymentPhysicalTransportCredentialAssignment,
        *,
        evaluated_at: datetime,
        context: WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmitterContext,
        idempotency_key: str,
    ) -> None:
        try:
            self._validate_head(
                snapshot,
                head,
                scope=context.scope,
                evaluated_at=evaluated_at,
            )
        except (ValueError, WorkflowTransportCredentialAssignmentFreshnessAdmissionError):
            await self._deny_evidence(context, idempotency_key, snapshot=snapshot)

    async def _validate_admission_or_deny(
        self,
        admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
        *,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
        head: DeploymentPhysicalTransportCredentialAssignment,
        context: WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmitterContext,
        idempotency_key: str,
    ) -> None:
        try:
            self._validate_admission(
                admission,
                binding=binding,
                snapshot=snapshot,
                head=head,
                scope=context.scope,
            )
        except (ValueError, WorkflowTransportCredentialAssignmentFreshnessAdmissionError):
            await self._deny_evidence(
                context,
                idempotency_key,
                admission=admission,
                binding=binding,
                snapshot=snapshot,
            )

    async def _require_admitter_workload(
        self,
        context: WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmitterContext,
    ) -> None:
        if (
            context.subject_id
            != WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_SUBJECT
            or context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience
            != WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_AUDIENCE
        ):
            await self._deny(
                context,
                result_code=(
                    "workflow_physical_transport_credential_assignment_freshness_admitter_identity_required"
                ),
            )

    async def _audit_committed_result(
        self,
        context: WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmitterContext,
        *,
        event_kind: str,
        result_code: str,
        idempotency_key: str,
        admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
    ) -> None:
        try:
            await self._audit(
                context,
                event_kind=event_kind,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                admission=admission,
                binding=binding,
                snapshot=snapshot,
            )
        except Exception as exc:
            raise WorkflowTransportCredentialAssignmentFreshnessAdmissionError(
                "workflow_physical_transport_credential_assignment_freshness_completion_audit_outcome_uncertain",
                "The freshness admission is committed but completion audit is unavailable.",
            ) from exc

    async def _deny_evidence(
        self,
        context: WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmitterContext,
        idempotency_key: str,
        *,
        admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission
        | None = None,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding | None = None,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot | None = None,
    ) -> NoReturn:
        await self._deny(
            context,
            result_code=(
                "workflow_physical_transport_credential_assignment_freshness_evidence_conflict"
            ),
            idempotency_key=idempotency_key,
            admission=admission,
            binding=binding,
            snapshot=snapshot,
        )

    async def _deny(
        self,
        context: WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmitterContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
        admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission
        | None = None,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding | None = None,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot | None = None,
    ) -> NoReturn:
        try:
            await self._audit(
                context,
                event_kind="denied",
                outcome="denied",
                result_code=result_code,
                idempotency_key=idempotency_key,
                admission=admission,
                binding=binding,
                snapshot=snapshot,
            )
        except Exception as exc:
            raise WorkflowTransportCredentialAssignmentFreshnessAdmissionError(
                "workflow_physical_transport_credential_assignment_freshness_audit_unavailable",
                "The freshness admission was denied and required audit is unavailable.",
            ) from exc
        raise WorkflowTransportCredentialAssignmentFreshnessAdmissionError(
            result_code,
            "The workflow credential-assignment freshness request was denied.",
        )

    async def _audit(
        self,
        context: WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmitterContext,
        *,
        event_kind: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission
        | None = None,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding | None = None,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot | None = None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=(
                    "atlas.workflow.physical-transport-credential-assignment-freshness."
                    f"{event_kind}"
                ),
                schema_version="1.0",
                producer=(
                    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMISSION_PRODUCER
                ),
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id=(
                    "workflow.physical-transport-credential-assignment-freshness-admissions.create"
                ),
                resource_type=(
                    "resource.workflow-physical-transport-credential-assignment-freshness-admission"
                ),
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "credential-assignment-freshness-admission",
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
                        "credential_assignment_binding_id",
                        "none" if binding is None else binding.binding_id,
                    ),
                    (
                        "credential_assignment_snapshot_id",
                        "none" if snapshot is None else snapshot.snapshot_id,
                    ),
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
            raise WorkflowTransportCredentialAssignmentFreshnessAdmissionError(
                f"workflow_physical_transport_credential_assignment_freshness_{name}_invalid",
                f"{name} is invalid.",
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowTransportCredentialAssignmentFreshnessAdmissionError(
                "workflow_physical_transport_credential_assignment_freshness_idempotency_key_invalid",
                "The idempotency key is invalid.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise WorkflowTransportCredentialAssignmentFreshnessAdmissionError(
                f"workflow_physical_transport_credential_assignment_freshness_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value


__all__ = [
    "WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMISSION_PRODUCER",
    "WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_AUDIENCE",
    "WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_SUBJECT",
    "WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionService",
    "WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmitterContext",
]

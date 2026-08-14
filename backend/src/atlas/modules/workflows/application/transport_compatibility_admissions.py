from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.transport_compatibility_admission_ports import (
    WorkflowEventTransportCompatibilityAdmissionError,
    WorkflowEventTransportCompatibilityAdmissionRepository,
    WorkflowEventTransportCompatibilityAdmissionRequest,
    WorkflowEventTransportCompatibilityAdmissionStatus,
)
from atlas.modules.workflows.domain import (
    EventPhysicalTransportProfileSnapshot,
    EventPhysicalTransportProfileSnapshotState,
    WorkflowEventLogicalChannelBinding,
    WorkflowEventLogicalChannelBindingState,
    WorkflowEventTransportCompatibilityAdmission,
    WorkflowEventTransportCompatibilityAdmissionAuthority,
    WorkflowEventTransportCompatibilityAdmissionState,
    WorkflowEventTransportCompatibilityPolicy,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_transport_compatibility_policy,
)

WORKFLOW_TRANSPORT_COMPATIBILITY_ADMITTER_AUDIENCE = (
    "audience.workflow-transport-compatibility-admitter"
)
WORKFLOW_TRANSPORT_COMPATIBILITY_ADMISSION_PRODUCER = (
    "project-atlas-workflow-transport-compatibility-admitter"
)


@dataclass(frozen=True, slots=True)
class WorkflowTransportCompatibilityAdmitterContext:
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
            raise ValueError("transport compatibility context contains an invalid identifier")
        if self.requested_at.tzinfo is None:
            raise ValueError("transport compatibility requested_at must be timezone-aware")


class WorkflowEventTransportCompatibilityAdmissionService:
    """Admits exact declared contracts without selecting or testing a physical route."""

    def __init__(
        self,
        *,
        admission_repository: WorkflowEventTransportCompatibilityAdmissionRepository,
        audit_sink: AuditSink,
        policy: WorkflowEventTransportCompatibilityPolicy | None = None,
    ) -> None:
        self._repository = admission_repository
        self._audit_sink = audit_sink
        self._policy = policy or code_owned_workflow_event_transport_compatibility_policy()

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def repository(self) -> WorkflowEventTransportCompatibilityAdmissionRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowEventTransportCompatibilityPolicy:
        return self._policy

    async def admit(
        self,
        *,
        logical_channel_binding_id: str,
        logical_channel_binding_digest: str,
        transport_profile_snapshot_id: str,
        transport_profile_snapshot_digest: str,
        policy_id: str,
        policy_version: str,
        policy_digest: str,
        idempotency_key: str,
        context: WorkflowTransportCompatibilityAdmitterContext,
    ) -> WorkflowEventTransportCompatibilityAdmission:
        await self._require_admitter_workload(context)
        try:
            binding_id = self._identifier(logical_channel_binding_id, "binding_id")
            binding_digest = self._digest(logical_channel_binding_digest, "binding_digest")
            snapshot_id = self._identifier(transport_profile_snapshot_id, "snapshot_id")
            snapshot_digest = self._digest(transport_profile_snapshot_digest, "snapshot_digest")
            requested_policy_id = self._identifier(policy_id, "policy_id")
            requested_policy_version = self._identifier(policy_version, "policy_version")
            requested_policy_digest = self._digest(policy_digest, "policy_digest")
            normalized_key = self._idempotency_key(idempotency_key)
        except WorkflowEventTransportCompatibilityAdmissionError as exc:
            await self._deny(context, result_code=exc.code)

        if (
            requested_policy_id != self._policy.policy_id
            or requested_policy_version != self._policy.policy_version
            or requested_policy_digest != self._policy.canonical_digest
            or canonical_digest(self._policy.digest_payload()) != self._policy.canonical_digest
        ):
            await self._deny(
                context,
                result_code="workflow_transport_compatibility_policy_conflict",
                idempotency_key=normalized_key,
            )

        binding = await self._repository.get_event_logical_channel_binding_by_id(
            binding_id=binding_id
        )
        snapshot = await self._repository.get_transport_profile_snapshot_by_id(
            snapshot_id=snapshot_id
        )
        if binding is None or snapshot is None:
            await self._deny(
                context,
                result_code="workflow_transport_compatibility_evidence_not_found",
                idempotency_key=normalized_key,
                binding=binding,
                snapshot=snapshot,
            )
        await self._validate_sources_or_deny(
            binding,
            snapshot,
            expected_binding_id=binding_id,
            expected_binding_digest=binding_digest,
            expected_snapshot_id=snapshot_id,
            expected_snapshot_digest=snapshot_digest,
            context=context,
            idempotency_key=normalized_key,
        )
        await self._validate_compatibility_or_deny(
            binding,
            snapshot,
            context=context,
            idempotency_key=normalized_key,
        )

        fingerprint = canonical_digest(
            {
                "admitter_subject_id": context.subject_id,
                "logical_channel_binding_digest": binding_digest,
                "logical_channel_binding_id": binding_id,
                "policy_digest": requested_policy_digest,
                "scope": context.scope.canonical_value(),
                "transport_profile_snapshot_digest": snapshot_digest,
                "transport_profile_snapshot_id": snapshot_id,
            }
        )
        prior = await self._repository.get_transport_compatibility_admission_request(
            scope=context.scope,
            admitter_subject_id=context.subject_id,
            idempotency_key=normalized_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._deny(
                    context,
                    result_code="workflow_transport_compatibility_idempotency_conflict",
                    idempotency_key=normalized_key,
                    binding=binding,
                    snapshot=snapshot,
                    admission=prior.admission,
                )
            await self._validate_admission_or_deny(
                prior.admission,
                binding=binding,
                snapshot=snapshot,
                context=context,
                idempotency_key=normalized_key,
            )
            await self._audit(
                context,
                outcome="succeeded",
                result_code="workflow_transport_compatibility_admission_replayed",
                idempotency_key=normalized_key,
                binding=binding,
                snapshot=snapshot,
                admission=prior.admission,
            )
            return prior.admission

        current = await self._repository.get_transport_compatibility_admission(
            logical_channel_binding_id=binding.binding_id,
            transport_profile_snapshot_id=snapshot.snapshot_id,
            policy_digest=self._policy.canonical_digest,
        )
        if current is not None:
            await self._deny(
                context,
                result_code=(
                    "workflow_transport_compatibility_competing_identity"
                    if current.admitter_subject_id != context.subject_id
                    else "workflow_transport_compatibility_already_admitted"
                ),
                idempotency_key=normalized_key,
                binding=binding,
                snapshot=snapshot,
                admission=current,
            )

        candidate = self._build_admission(
            binding=binding,
            snapshot=snapshot,
            admitter_subject_id=context.subject_id,
            admitted_at=context.requested_at,
        )
        await self._audit(
            context,
            outcome="succeeded",
            result_code="workflow_transport_compatibility_admission_authorized",
            idempotency_key=normalized_key,
            binding=binding,
            snapshot=snapshot,
            admission=candidate,
        )
        result = await self._repository.admit_transport_compatibility(
            WorkflowEventTransportCompatibilityAdmissionRequest(
                expected_logical_channel_binding_id=binding_id,
                expected_logical_channel_binding_digest=binding_digest,
                expected_transport_profile_snapshot_id=snapshot_id,
                expected_transport_profile_snapshot_digest=snapshot_digest,
                expected_policy_digest=self._policy.canonical_digest,
                scope=context.scope,
                admitter_subject_id=context.subject_id,
                requested_at=context.requested_at,
                candidate=candidate,
                idempotency_key=normalized_key,
                request_fingerprint=fingerprint,
            )
        )
        if (
            result.status
            in {
                WorkflowEventTransportCompatibilityAdmissionStatus.ADMITTED,
                WorkflowEventTransportCompatibilityAdmissionStatus.REPLAY,
            }
            and result.admission is not None
        ):
            await self._validate_admission_or_deny(
                result.admission,
                binding=binding,
                snapshot=snapshot,
                context=context,
                idempotency_key=normalized_key,
            )
            return result.admission

        result_code = {
            WorkflowEventTransportCompatibilityAdmissionStatus.IDEMPOTENCY_CONFLICT: (
                "workflow_transport_compatibility_idempotency_conflict"
            ),
            WorkflowEventTransportCompatibilityAdmissionStatus.EVIDENCE_CONFLICT: (
                "workflow_transport_compatibility_evidence_conflict"
            ),
            WorkflowEventTransportCompatibilityAdmissionStatus.ALREADY_ADMITTED: (
                "workflow_transport_compatibility_already_admitted"
            ),
        }.get(
            result.status,
            "workflow_transport_compatibility_repository_contract_violation",
        )
        await self._deny(
            context,
            result_code=result_code,
            idempotency_key=normalized_key,
            binding=binding,
            snapshot=snapshot,
            admission=result.admission,
        )

    async def _validate_sources_or_deny(
        self,
        binding: WorkflowEventLogicalChannelBinding,
        snapshot: EventPhysicalTransportProfileSnapshot,
        *,
        expected_binding_id: str,
        expected_binding_digest: str,
        expected_snapshot_id: str,
        expected_snapshot_digest: str,
        context: WorkflowTransportCompatibilityAdmitterContext,
        idempotency_key: str,
    ) -> None:
        binding_valid = (
            binding.binding_id == expected_binding_id
            and binding.canonical_digest == expected_binding_digest
            and canonical_digest(binding.digest_payload()) == binding.canonical_digest
            and binding.state is WorkflowEventLogicalChannelBindingState.BOUND
            and binding.scope == context.scope
            and not any(binding.authority.canonical_value().values())
            and not binding.grants_publication_authority
            and not binding.grants_delivery_authority
            and not binding.grants_dispatch_authority
            and not binding.grants_execution_authority
        )
        snapshot_valid = (
            snapshot.snapshot_id == expected_snapshot_id
            and snapshot.canonical_digest == expected_snapshot_digest
            and canonical_digest(snapshot.digest_payload()) == snapshot.canonical_digest
            and snapshot.state is EventPhysicalTransportProfileSnapshotState.SNAPSHOTTED
            and snapshot.scope == context.scope
            and not any(snapshot.authority.canonical_value().values())
            and not snapshot.grants_route_selection_authority
            and not snapshot.grants_publication_authority
            and not snapshot.grants_delivery_authority
            and not snapshot.grants_dispatch_authority
            and not snapshot.grants_execution_authority
        )
        if not binding_valid or not snapshot_valid or binding.scope != snapshot.scope:
            await self._deny(
                context,
                result_code="workflow_transport_compatibility_evidence_conflict",
                idempotency_key=idempotency_key,
                binding=binding,
                snapshot=snapshot,
            )

    async def _validate_compatibility_or_deny(
        self,
        binding: WorkflowEventLogicalChannelBinding,
        snapshot: EventPhysicalTransportProfileSnapshot,
        *,
        context: WorkflowTransportCompatibilityAdmitterContext,
        idempotency_key: str,
    ) -> None:
        event_contract = f"{binding.event_type}|{binding.event_version}|{binding.schema_uri}"
        checks = (
            (
                binding.event_type == self._policy.event_type
                and binding.event_version == self._policy.event_version
                and binding.schema_uri == self._policy.schema_uri
                and event_contract in snapshot.supported_event_contracts,
                "workflow_transport_compatibility_event_contract_unsupported",
            ),
            (
                binding.data_classification == self._policy.data_classification
                and binding.data_classification in snapshot.supported_classifications,
                "workflow_transport_compatibility_classification_unsupported",
            ),
            (
                binding.representation_name == self._policy.representation_name
                and binding.representation_name in snapshot.supported_representations,
                "workflow_transport_compatibility_representation_unsupported",
            ),
            (
                binding.encoding == self._policy.encoding
                and binding.encoding in snapshot.supported_encodings,
                "workflow_transport_compatibility_encoding_unsupported",
            ),
            (
                binding.delivery_semantics == self._policy.delivery_semantics
                and binding.delivery_semantics in snapshot.supported_delivery_semantics,
                "workflow_transport_compatibility_delivery_semantics_unsupported",
            ),
            (
                binding.durability_required is self._policy.durability_required
                and snapshot.durable_delivery_supported,
                "workflow_transport_compatibility_durability_unsupported",
            ),
            (
                binding.ordering_key_kind == self._policy.ordering_key_kind
                and binding.ordering_key_kind in snapshot.supported_ordering_key_kinds,
                "workflow_transport_compatibility_ordering_unsupported",
            ),
            (
                binding.retention_class == self._policy.retention_class
                and binding.retention_class in snapshot.supported_retention_classes,
                "workflow_transport_compatibility_retention_unsupported",
            ),
            (
                binding.maximum_canonical_byte_count == self._policy.maximum_logical_byte_count
                and binding.maximum_canonical_byte_count <= snapshot.maximum_message_byte_count
                and binding.canonical_byte_count <= snapshot.maximum_message_byte_count,
                "workflow_transport_compatibility_message_size_insufficient",
            ),
        )
        for compatible, result_code in checks:
            if not compatible:
                await self._deny(
                    context,
                    result_code=result_code,
                    idempotency_key=idempotency_key,
                    binding=binding,
                    snapshot=snapshot,
                )

    def _build_admission(
        self,
        *,
        binding: WorkflowEventLogicalChannelBinding,
        snapshot: EventPhysicalTransportProfileSnapshot,
        admitter_subject_id: str,
        admitted_at: datetime,
    ) -> WorkflowEventTransportCompatibilityAdmission:
        admission_id = (
            "workflow-event-transport-compatibility-admission."
            + sha256(
                f"{binding.canonical_digest}:{snapshot.canonical_digest}:"
                f"{self._policy.canonical_digest}".encode()
            ).hexdigest()[:24]
        )
        values: dict[str, object] = {
            "compatibility_admission_id": admission_id,
            "logical_channel_binding_id": binding.binding_id,
            "logical_channel_binding_digest": binding.canonical_digest,
            "transport_profile_snapshot_id": snapshot.snapshot_id,
            "transport_profile_snapshot_digest": snapshot.canonical_digest,
            "transport_profile_id": snapshot.transport_profile_id,
            "transport_profile_revision": snapshot.transport_profile_revision,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "scope": binding.scope,
            "event_type": binding.event_type,
            "event_version": binding.event_version,
            "schema_uri": binding.schema_uri,
            "data_classification": binding.data_classification,
            "representation_name": binding.representation_name,
            "encoding": binding.encoding,
            "delivery_semantics": binding.delivery_semantics,
            "durability_required": binding.durability_required,
            "ordering_key_kind": binding.ordering_key_kind,
            "retention_class": binding.retention_class,
            "logical_maximum_byte_count": binding.maximum_canonical_byte_count,
            "artifact_byte_count": binding.canonical_byte_count,
            "profile_maximum_message_byte_count": snapshot.maximum_message_byte_count,
            "admitter_subject_id": admitter_subject_id,
            "admitted_at": admitted_at,
            "state": WorkflowEventTransportCompatibilityAdmissionState.ADMITTED,
            "authority": WorkflowEventTransportCompatibilityAdmissionAuthority(),
        }
        digest_payload = {
            key: value.canonical_value()
            if isinstance(
                value,
                (WorkflowEventTransportCompatibilityAdmissionAuthority, WorkflowScope),
            )
            else value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, WorkflowEventTransportCompatibilityAdmissionState)
            else value
            for key, value in values.items()
        }
        return WorkflowEventTransportCompatibilityAdmission(
            **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
        )

    async def _validate_admission_or_deny(
        self,
        admission: WorkflowEventTransportCompatibilityAdmission,
        *,
        binding: WorkflowEventLogicalChannelBinding,
        snapshot: EventPhysicalTransportProfileSnapshot,
        context: WorkflowTransportCompatibilityAdmitterContext,
        idempotency_key: str,
    ) -> None:
        expected = self._build_admission(
            binding=binding,
            snapshot=snapshot,
            admitter_subject_id=admission.admitter_subject_id,
            admitted_at=admission.admitted_at,
        )
        if (
            admission != expected
            or admission.scope != context.scope
            or admission.admitter_subject_id != context.subject_id
            or admission.admitted_at > context.requested_at
            or canonical_digest(admission.digest_payload()) != admission.canonical_digest
            or admission.state is not WorkflowEventTransportCompatibilityAdmissionState.ADMITTED
            or any(admission.authority.canonical_value().values())
            or admission.grants_route_selection_authority
            or admission.grants_route_binding_authority
            or admission.grants_credential_access_authority
            or admission.grants_publication_authority
            or admission.grants_delivery_authority
            or admission.grants_dispatch_authority
            or admission.grants_execution_authority
        ):
            await self._deny(
                context,
                result_code="workflow_transport_compatibility_repository_scope_violation",
                idempotency_key=idempotency_key,
                binding=binding,
                snapshot=snapshot,
                admission=admission,
            )

    async def _require_admitter_workload(
        self, context: WorkflowTransportCompatibilityAdmitterContext
    ) -> None:
        if (
            context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience != WORKFLOW_TRANSPORT_COMPATIBILITY_ADMITTER_AUDIENCE
        ):
            await self._deny(
                context,
                result_code="workflow_transport_compatibility_admitter_identity_required",
            )

    async def _deny(
        self,
        context: WorkflowTransportCompatibilityAdmitterContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
        binding: WorkflowEventLogicalChannelBinding | None = None,
        snapshot: EventPhysicalTransportProfileSnapshot | None = None,
        admission: WorkflowEventTransportCompatibilityAdmission | None = None,
    ) -> NoReturn:
        await self._audit(
            context,
            outcome="denied",
            result_code=result_code,
            idempotency_key=idempotency_key,
            binding=binding,
            snapshot=snapshot,
            admission=admission,
        )
        raise WorkflowEventTransportCompatibilityAdmissionError(
            result_code, "The workflow transport compatibility admission request was denied."
        )

    async def _audit(
        self,
        context: WorkflowTransportCompatibilityAdmitterContext,
        *,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        binding: WorkflowEventLogicalChannelBinding | None,
        snapshot: EventPhysicalTransportProfileSnapshot | None,
        admission: WorkflowEventTransportCompatibilityAdmission | None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=(
                    "atlas.workflow.transport-compatibility-admission.succeeded"
                    if outcome == "succeeded"
                    else "atlas.workflow.transport-compatibility-admission.denied"
                ),
                schema_version="1.0",
                producer=WORKFLOW_TRANSPORT_COMPATIBILITY_ADMISSION_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.transport-compatibility-admissions.admit",
                resource_type="resource.workflow-transport-compatibility-admission",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-transport-compatibility-admission",
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    (
                        "logical_channel_binding_id",
                        "none" if binding is None else binding.binding_id,
                    ),
                    (
                        "transport_profile_snapshot_id",
                        "none" if snapshot is None else snapshot.snapshot_id,
                    ),
                    (
                        "compatibility_admission_id",
                        "none" if admission is None else admission.compatibility_admission_id,
                    ),
                    ("route_selection_authority", "false"),
                    ("route_binding_authority", "false"),
                    ("credential_access_authority", "false"),
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
            raise WorkflowEventTransportCompatibilityAdmissionError(
                f"workflow_transport_compatibility_{name}_invalid", f"{name} is invalid."
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowEventTransportCompatibilityAdmissionError(
                "workflow_transport_compatibility_idempotency_key_invalid",
                "The idempotency key is invalid.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise WorkflowEventTransportCompatibilityAdmissionError(
                f"workflow_transport_compatibility_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value


__all__ = [
    "WORKFLOW_TRANSPORT_COMPATIBILITY_ADMISSION_PRODUCER",
    "WORKFLOW_TRANSPORT_COMPATIBILITY_ADMITTER_AUDIENCE",
    "WorkflowEventTransportCompatibilityAdmissionService",
    "WorkflowTransportCompatibilityAdmitterContext",
]

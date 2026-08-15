from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import NoReturn
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.target_context_binding_ports import (
    WorkflowEventPhysicalTransportTargetContextBindingError,
    WorkflowEventPhysicalTransportTargetContextBindingRepository,
    WorkflowEventPhysicalTransportTargetContextBindingRequest,
    WorkflowEventPhysicalTransportTargetContextBindingStatus,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportTargetContextBinding,
    WorkflowEventPhysicalTransportTargetContextBindingPolicy,
    WorkflowEventPhysicalTransportTargetContextBindingState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_target_context_binding_policy,
)

WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE = (
    "audience.workflow-physical-transport-target-context-binder"
)
WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_SUBJECT = (
    "service.workflow-physical-transport-target-context-binder"
)
WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDING_PRODUCER = (
    "project-atlas-workflow-physical-transport-target-context-binder"
)


@dataclass(frozen=True, slots=True)
class WorkflowPhysicalTransportTargetContextBinderContext:
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
            raise ValueError("target context binder context contains an invalid identifier")
        if self.requested_at.tzinfo is None:
            raise ValueError("target context binding requested_at must be timezone-aware")


class WorkflowEventPhysicalTransportTargetContextBindingService:
    """Binds protected endpoint and credential lineage without artifact access."""

    def __init__(
        self,
        *,
        binding_repository: WorkflowEventPhysicalTransportTargetContextBindingRepository,
        audit_sink: AuditSink,
        policy: WorkflowEventPhysicalTransportTargetContextBindingPolicy | None = None,
    ) -> None:
        self._repository = binding_repository
        self._audit_sink = audit_sink
        self._policy = (
            policy or code_owned_workflow_event_physical_transport_target_context_binding_policy()
        )

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def repository(self) -> WorkflowEventPhysicalTransportTargetContextBindingRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowEventPhysicalTransportTargetContextBindingPolicy:
        return self._policy

    async def bind(
        self,
        *,
        endpoint_materialization_id: str,
        endpoint_materialization_digest: str,
        credential_materialization_id: str,
        credential_materialization_digest: str,
        policy_id: str,
        policy_version: str,
        policy_digest: str,
        idempotency_key: str,
        context: WorkflowPhysicalTransportTargetContextBinderContext,
    ) -> WorkflowEventPhysicalTransportTargetContextBinding:
        await self._require_binder_workload(context)
        if not self._repository.durable:
            await self._deny(
                context,
                result_code="workflow_target_context_binding_durable_repository_required",
            )
        try:
            endpoint_id = self._identifier(
                endpoint_materialization_id, "endpoint_materialization_id"
            )
            endpoint_digest = self._digest(
                endpoint_materialization_digest, "endpoint_materialization_digest"
            )
            credential_id = self._identifier(
                credential_materialization_id, "credential_materialization_id"
            )
            credential_digest = self._digest(
                credential_materialization_digest, "credential_materialization_digest"
            )
            requested_policy_id = self._identifier(policy_id, "policy_id")
            requested_policy_version = self._identifier(policy_version, "policy_version")
            requested_policy_digest = self._digest(policy_digest, "policy_digest")
            normalized_key = self._idempotency_key(idempotency_key)
        except WorkflowEventPhysicalTransportTargetContextBindingError as exc:
            await self._deny(context, result_code=exc.code)

        if (
            requested_policy_id != self._policy.policy_id
            or requested_policy_version != self._policy.policy_version
            or requested_policy_digest != self._policy.canonical_digest
        ):
            await self._deny(
                context,
                result_code="workflow_target_context_binding_policy_mismatch",
                idempotency_key=normalized_key,
                endpoint_materialization_id=endpoint_id,
                credential_materialization_id=credential_id,
            )

        fingerprint = canonical_digest(
            {
                "binder_subject_id": context.subject_id,
                "credential_materialization_digest": credential_digest,
                "credential_materialization_id": credential_id,
                "endpoint_materialization_digest": endpoint_digest,
                "endpoint_materialization_id": endpoint_id,
                "policy_digest": self._policy.canonical_digest,
                "policy_id": self._policy.policy_id,
                "policy_version": self._policy.policy_version,
                "scope": context.scope.canonical_value(),
            }
        )
        await self._audit_required(
            context,
            event_kind="intent",
            outcome="authorized",
            result_code="workflow_target_context_binding_persistence_authorized",
            idempotency_key=normalized_key,
            endpoint_materialization_id=endpoint_id,
            credential_materialization_id=credential_id,
        )

        async def required_precommit_audit() -> None:
            await self._audit(
                context,
                event_kind="commit-authorization",
                outcome="authorized",
                result_code="workflow_target_context_binding_commit_authorized",
                idempotency_key=normalized_key,
                endpoint_materialization_id=endpoint_id,
                credential_materialization_id=credential_id,
            )

        result = await self._repository.bind_target_context(
            WorkflowEventPhysicalTransportTargetContextBindingRequest(
                expected_endpoint_materialization_id=endpoint_id,
                expected_endpoint_materialization_digest=endpoint_digest,
                expected_credential_materialization_id=credential_id,
                expected_credential_materialization_digest=credential_digest,
                expected_policy_id=self._policy.policy_id,
                expected_policy_version=self._policy.policy_version,
                expected_policy_digest=self._policy.canonical_digest,
                scope=context.scope,
                binder_subject_id=context.subject_id,
                requested_at=context.requested_at,
                idempotency_key=normalized_key,
                request_fingerprint=fingerprint,
                required_precommit_audit=required_precommit_audit,
            )
        )
        if (
            result.status
            in (
                WorkflowEventPhysicalTransportTargetContextBindingStatus.BOUND,
                WorkflowEventPhysicalTransportTargetContextBindingStatus.REPLAY,
            )
            and result.binding is not None
        ):
            await self._validate_binding_or_deny(
                result.binding,
                endpoint_materialization_id=endpoint_id,
                endpoint_materialization_digest=endpoint_digest,
                credential_materialization_id=credential_id,
                credential_materialization_digest=credential_digest,
                context=context,
                idempotency_key=normalized_key,
            )
            await self._audit_committed_result(
                context,
                event_kind=("completion" if result.status.value == "bound" else "replay"),
                result_code=(
                    "workflow_target_context_binding_created"
                    if result.status.value == "bound"
                    else "workflow_target_context_binding_replayed"
                ),
                idempotency_key=normalized_key,
                binding=result.binding,
            )
            return result.binding

        result_code = {
            WorkflowEventPhysicalTransportTargetContextBindingStatus.IDEMPOTENCY_CONFLICT: (
                "workflow_target_context_binding_idempotency_conflict"
            ),
            WorkflowEventPhysicalTransportTargetContextBindingStatus.EVIDENCE_CONFLICT: (
                "workflow_target_context_binding_evidence_conflict"
            ),
            WorkflowEventPhysicalTransportTargetContextBindingStatus.ALREADY_BOUND: (
                "workflow_target_context_binding_already_bound"
            ),
            WorkflowEventPhysicalTransportTargetContextBindingStatus.PRECOMMIT_AUDIT_FAILED: (
                "workflow_target_context_binding_precommit_audit_failed"
            ),
        }.get(
            result.status,
            "workflow_target_context_binding_repository_contract_violation",
        )
        await self._deny(
            context,
            result_code=result_code,
            idempotency_key=normalized_key,
            endpoint_materialization_id=endpoint_id,
            credential_materialization_id=credential_id,
            binding=result.binding,
        )

    async def _require_binder_workload(
        self, context: WorkflowPhysicalTransportTargetContextBinderContext
    ) -> None:
        if (
            context.subject_id != WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_SUBJECT
            or context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience
            != WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE
        ):
            await self._deny(
                context,
                result_code="workflow_target_context_binding_binder_identity_required",
            )

    async def _validate_binding_or_deny(
        self,
        binding: WorkflowEventPhysicalTransportTargetContextBinding,
        *,
        endpoint_materialization_id: str,
        endpoint_materialization_digest: str,
        credential_materialization_id: str,
        credential_materialization_digest: str,
        context: WorkflowPhysicalTransportTargetContextBinderContext,
        idempotency_key: str,
    ) -> None:
        valid = (
            binding.endpoint_materialization_id == endpoint_materialization_id
            and binding.endpoint_materialization_digest == endpoint_materialization_digest
            and binding.credential_materialization_id == credential_materialization_id
            and binding.credential_materialization_digest == credential_materialization_digest
            and binding.scope == context.scope
            and binding.binder_subject_id == context.subject_id
            and binding.policy_id == self._policy.policy_id
            and binding.policy_version == self._policy.policy_version
            and binding.policy_digest == self._policy.canonical_digest
            and binding.target_context_schema_id == self._policy.target_context_schema_id
            and binding.target_context_schema_version == self._policy.target_context_schema_version
            and binding.state is WorkflowEventPhysicalTransportTargetContextBindingState.BOUND
            and binding.bound_at.tzinfo is not None
            and binding.joint_usable_until.tzinfo is not None
            and binding.bound_at < binding.joint_usable_until
            and not any(binding.authority.canonical_value().values())
            and canonical_digest(binding.digest_payload()) == binding.canonical_digest
        )
        if not valid:
            await self._deny(
                context,
                result_code="workflow_target_context_binding_repository_contract_violation",
                idempotency_key=idempotency_key,
                endpoint_materialization_id=endpoint_materialization_id,
                credential_materialization_id=credential_materialization_id,
                binding=binding,
            )

    async def _audit_committed_result(
        self,
        context: WorkflowPhysicalTransportTargetContextBinderContext,
        *,
        event_kind: str,
        result_code: str,
        idempotency_key: str,
        binding: WorkflowEventPhysicalTransportTargetContextBinding,
    ) -> None:
        try:
            await self._audit(
                context,
                event_kind=event_kind,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                endpoint_materialization_id=binding.endpoint_materialization_id,
                credential_materialization_id=binding.credential_materialization_id,
                binding=binding,
            )
        except Exception as exc:
            raise WorkflowEventPhysicalTransportTargetContextBindingError(
                "workflow_target_context_binding_completion_audit_outcome_uncertain",
                "The immutable target context binding is committed but completion audit is "
                "unavailable.",
            ) from exc

    async def _deny(
        self,
        context: WorkflowPhysicalTransportTargetContextBinderContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
        endpoint_materialization_id: str = "none",
        credential_materialization_id: str = "none",
        binding: WorkflowEventPhysicalTransportTargetContextBinding | None = None,
    ) -> NoReturn:
        try:
            await self._audit(
                context,
                event_kind="denied",
                outcome="denied",
                result_code=result_code,
                idempotency_key=idempotency_key,
                endpoint_materialization_id=endpoint_materialization_id,
                credential_materialization_id=credential_materialization_id,
                binding=binding,
            )
        except Exception as exc:
            raise WorkflowEventPhysicalTransportTargetContextBindingError(
                "workflow_target_context_binding_audit_unavailable",
                "Required target context binding audit evidence is unavailable.",
            ) from exc
        raise WorkflowEventPhysicalTransportTargetContextBindingError(
            result_code,
            "The workflow physical transport target context binding was denied.",
        )

    async def _audit_required(
        self,
        context: WorkflowPhysicalTransportTargetContextBinderContext,
        *,
        event_kind: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        endpoint_materialization_id: str,
        credential_materialization_id: str,
    ) -> None:
        try:
            await self._audit(
                context,
                event_kind=event_kind,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                endpoint_materialization_id=endpoint_materialization_id,
                credential_materialization_id=credential_materialization_id,
            )
        except Exception as exc:
            raise WorkflowEventPhysicalTransportTargetContextBindingError(
                "workflow_target_context_binding_audit_unavailable",
                "Required target context binding audit evidence is unavailable.",
            ) from exc

    async def _audit(
        self,
        context: WorkflowPhysicalTransportTargetContextBinderContext,
        *,
        event_kind: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        endpoint_materialization_id: str,
        credential_materialization_id: str,
        binding: WorkflowEventPhysicalTransportTargetContextBinding | None = None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=(
                    f"atlas.workflow.physical-transport-target-context-binding.{event_kind}"
                ),
                schema_version="1.0",
                producer=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDING_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.physical-transport-target-context-bindings.bind",
                resource_type="resource.workflow-physical-transport-target-context-binding",
                scope_reference="/".join(context.scope.canonical_value().values()),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    ("binding_id", "none" if binding is None else binding.binding_id),
                    ("endpoint_materialization_id", endpoint_materialization_id),
                    ("credential_materialization_id", credential_materialization_id),
                    ("all_target_context_authority", "false"),
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
            raise WorkflowEventPhysicalTransportTargetContextBindingError(
                f"workflow_target_context_binding_{name}_invalid",
                f"{name} is invalid.",
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowEventPhysicalTransportTargetContextBindingError(
                "workflow_target_context_binding_idempotency_key_invalid",
                "The idempotency key is invalid.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise WorkflowEventPhysicalTransportTargetContextBindingError(
                f"workflow_target_context_binding_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value


__all__ = [
    "WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE",
    "WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_SUBJECT",
    "WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDING_PRODUCER",
    "WorkflowEventPhysicalTransportTargetContextBindingService",
    "WorkflowPhysicalTransportTargetContextBinderContext",
]

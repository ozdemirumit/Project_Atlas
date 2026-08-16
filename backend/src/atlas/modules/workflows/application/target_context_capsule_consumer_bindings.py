from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import NoReturn

from atlas.modules.workflows.application.target_context_capsule_consumer_binding_ports import (
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError,
    WorkflowTargetContextCapsuleConsumerBindingRepository,
    WorkflowTargetContextCapsuleConsumerBindingRequest,
    WorkflowTargetContextCapsuleConsumerBindingStatus,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingPolicy,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_transport_target_context_capsule_consumer_binding_policy,
)

WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_SUBJECT = (
    "service.workflow-protected-transport-target-context-capsule-binder"
)
WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE = (
    "audience.workflow-protected-transport-target-context-capsule-binder"
)


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleBinderContext:
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
            raise ValueError("target context capsule binder context contains invalid evidence")
        if self.requested_at.tzinfo is None:
            raise ValueError("target context capsule binding requested_at must be timezone-aware")


class WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService:
    """Binds capsule lineage to one code-owned consumer without external I/O."""

    def __init__(
        self,
        *,
        repository: WorkflowTargetContextCapsuleConsumerBindingRepository,
        policy: WorkflowProtectedTransportTargetContextCapsuleConsumerBindingPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._policy = policy or (
            code_owned_workflow_protected_transport_target_context_capsule_consumer_binding_policy()
        )

    @property
    def repository(self) -> WorkflowTargetContextCapsuleConsumerBindingRepository:
        return self._repository

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def policy(self) -> WorkflowProtectedTransportTargetContextCapsuleConsumerBindingPolicy:
        return self._policy

    async def bind(
        self,
        *,
        opening_result_id: str,
        opening_result_digest: str,
        policy_id: str,
        policy_version: str,
        idempotency_key: str,
        context: WorkflowProtectedTransportTargetContextCapsuleBinderContext,
    ) -> WorkflowProtectedTransportTargetContextCapsuleConsumerBinding:
        self._require_context(context)
        if not self._repository.durable:
            self._raise("target_context_capsule_consumer_binding_durable_repository_required")
        opening_id = self._identifier(opening_result_id, "opening_result_id")
        opening_digest = self._digest(opening_result_digest, "opening_result_digest")
        requested_policy_id = self._identifier(policy_id, "policy_id")
        requested_policy_version = self._identifier(policy_version, "policy_version")
        normalized_key = self._idempotency_key(idempotency_key)
        if (
            requested_policy_id != self._policy.policy_id
            or requested_policy_version != self._policy.policy_version
        ):
            self._raise("target_context_capsule_consumer_binding_policy_mismatch")

        idempotency_digest = sha256(
            "\x00".join(
                (
                    context.subject_id,
                    context.credential_audience,
                    *context.scope.canonical_value().values(),
                    normalized_key,
                )
            ).encode()
        ).hexdigest()
        fingerprint = canonical_digest(
            {
                "binder_audience": context.credential_audience,
                "binder_subject_id": context.subject_id,
                "idempotency_digest": idempotency_digest,
                "opening_result_digest": opening_digest,
                "opening_result_id": opening_id,
                "policy_digest": self._policy.canonical_digest,
                "policy_id": self._policy.policy_id,
                "policy_version": self._policy.policy_version,
                "scope": context.scope.canonical_value(),
            }
        )
        result = await self._repository.bind_target_context_capsule_consumer(
            WorkflowTargetContextCapsuleConsumerBindingRequest(
                opening_result_id=opening_id,
                opening_result_digest=opening_digest,
                expected_policy_id=self._policy.policy_id,
                expected_policy_version=self._policy.policy_version,
                expected_policy_digest=self._policy.canonical_digest,
                expected_consumer_subject_id=self._policy.consumer_subject_id,
                expected_consumer_audience=self._policy.consumer_audience,
                expected_consumer_contract_id=self._policy.consumer_contract_id,
                expected_consumer_contract_version=self._policy.consumer_contract_version,
                expected_purpose_id=self._policy.purpose_id,
                minimum_remaining_lifetime_seconds=(
                    self._policy.minimum_remaining_lifetime_seconds
                ),
                scope=context.scope,
                binder_subject_id=context.subject_id,
                binder_audience=context.credential_audience,
                requested_at=context.requested_at,
                idempotency_key=normalized_key,
                idempotency_digest=idempotency_digest,
                request_fingerprint=fingerprint,
            )
        )
        if result.status in (
            WorkflowTargetContextCapsuleConsumerBindingStatus.BOUND,
            WorkflowTargetContextCapsuleConsumerBindingStatus.REPLAY,
        ):
            if result.binding is None or not self._binding_matches(
                result.binding,
                opening_result_id=opening_id,
                opening_result_digest=opening_digest,
                idempotency_digest=idempotency_digest,
                request_fingerprint=fingerprint,
                context=context,
            ):
                self._raise("target_context_capsule_consumer_binding_repository_contract_violation")
            return result.binding
        self._raise(
            {
                WorkflowTargetContextCapsuleConsumerBindingStatus.IDEMPOTENCY_CONFLICT: (
                    "target_context_capsule_consumer_binding_idempotency_conflict"
                ),
                WorkflowTargetContextCapsuleConsumerBindingStatus.EVIDENCE_CONFLICT: (
                    "target_context_capsule_consumer_binding_evidence_conflict"
                ),
                WorkflowTargetContextCapsuleConsumerBindingStatus.ALREADY_BOUND: (
                    "target_context_capsule_consumer_binding_already_bound"
                ),
            }.get(
                result.status,
                "target_context_capsule_consumer_binding_repository_contract_violation",
            )
        )

    async def list_bindings(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleConsumerBinding, ...]:
        if not self._repository.durable:
            self._raise("target_context_capsule_consumer_binding_durable_repository_required")
        if not 1 <= limit <= 256:
            self._raise("target_context_capsule_consumer_binding_limit_invalid")
        bindings = await self._repository.list_target_context_capsule_consumer_bindings(
            scope=scope, limit=limit
        )
        if any(
            binding.scope != scope
            or binding.state
            is not WorkflowProtectedTransportTargetContextCapsuleConsumerBindingState.BOUND
            or canonical_digest(binding.digest_payload()) != binding.canonical_digest
            or any(binding.authority.canonical_value().values())
            for binding in bindings
        ):
            self._raise("target_context_capsule_consumer_binding_repository_contract_violation")
        return bindings

    def _require_context(
        self, context: WorkflowProtectedTransportTargetContextCapsuleBinderContext
    ) -> None:
        if (
            context.subject_id != WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_SUBJECT
            or context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience
            != WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE
        ):
            self._raise("target_context_capsule_consumer_binding_binder_identity_required")

    def _binding_matches(
        self,
        binding: WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
        *,
        opening_result_id: str,
        opening_result_digest: str,
        idempotency_digest: str,
        request_fingerprint: str,
        context: WorkflowProtectedTransportTargetContextCapsuleBinderContext,
    ) -> bool:
        return (
            binding.opening_result_id == opening_result_id
            and binding.opening_result_digest == opening_result_digest
            and binding.scope == context.scope
            and binding.binder_subject_id == context.subject_id
            and binding.binder_audience == context.credential_audience
            and binding.consumer_subject_id == self._policy.consumer_subject_id
            and binding.consumer_audience == self._policy.consumer_audience
            and binding.consumer_contract_id == self._policy.consumer_contract_id
            and binding.consumer_contract_version == self._policy.consumer_contract_version
            and binding.purpose_id == self._policy.purpose_id
            and binding.policy_id == self._policy.policy_id
            and binding.policy_version == self._policy.policy_version
            and binding.policy_digest == self._policy.canonical_digest
            and binding.idempotency_digest == idempotency_digest
            and binding.request_fingerprint == request_fingerprint
            and binding.capsule_is_bearer_capability is False
            and binding.bound_at.tzinfo is not None
            and binding.effective_until.tzinfo is not None
            and binding.bound_at < binding.effective_until
            and binding.state
            is WorkflowProtectedTransportTargetContextCapsuleConsumerBindingState.BOUND
            and not any(binding.authority.canonical_value().values())
            and canonical_digest(binding.digest_payload()) == binding.canonical_digest
        )

    @staticmethod
    def _identifier(value: str, name: str) -> str:
        if (
            not value
            or value != value.strip()
            or len(value) > 240
            or any(character.isspace() for character in value)
        ):
            raise WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError(
                f"target_context_capsule_consumer_binding_{name}_invalid"
            )
        return value

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            cls._raise("target_context_capsule_consumer_binding_idempotency_key_invalid")
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError(
                f"target_context_capsule_consumer_binding_{name}_invalid"
            )
        return value

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError(code)


__all__ = [
    "WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE",
    "WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_SUBJECT",
    "WorkflowProtectedTransportTargetContextCapsuleBinderContext",
    "WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService",
]

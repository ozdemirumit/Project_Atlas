from __future__ import annotations

from typing import NoReturn

from atlas.modules.workflows.application.protected_runtime_context_use_authorization_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionError,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayLookup,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayLookupRequest,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayStatus,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionRepository,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionRequest,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionWrite,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionWriteStatus,
    validate_workflow_protected_runtime_context_use_authorization_consumption_request,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_context_use_authorization_consumption_domain import (  # noqa: E501
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPolicy,
    code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy,
)

WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_AUTHORIZATION_CONSUMPTION_PRODUCER = (
    "project-atlas-workflow-protected-runtime-context-use-authorization-consumer"
)


class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService:
    """Consumes one ADR-170 lease without accessing or using protected context."""

    def __init__(
        self,
        *,
        repository: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionRepository,
        policy: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._policy = (
            policy
            or code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy()
        )

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def repository(
        self,
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPolicy:
        return self._policy

    async def consume(
        self,
        *,
        authorization_lease_id: str,
        policy_id: str,
        policy_version: str,
        idempotency_key: str,
        irreversible_consumption_acknowledged: bool,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation:
        self._require_request(
            authorization_lease_id=authorization_lease_id,
            policy_id=policy_id,
            policy_version=policy_version,
            idempotency_key=idempotency_key,
            irreversible_consumption_acknowledged=irreversible_consumption_acknowledged,
            context=context,
        )
        if not self._repository.durable:
            self._raise(
                "protected_runtime_context_use_authorization_consumption_durable_repository_required"
            )

        idempotency_digest = canonical_digest(
            {
                "consumer_subject_id": context.subject_id,
                "idempotency_key": idempotency_key,
                "scope": context.scope.canonical_value(),
            }
        )
        request_fingerprint = canonical_digest(
            {
                "authorization_lease_id": authorization_lease_id,
                "consumer_audience": context.credential_audience,
                "consumer_subject_id": context.subject_id,
                "idempotency_digest": idempotency_digest,
                "irreversible_consumption_acknowledged": True,
                "policy_digest": self._policy.canonical_digest,
                "policy_id": policy_id,
                "policy_version": policy_version,
                "scope": context.scope.canonical_value(),
            }
        )
        seed = canonical_digest(
            {
                "authorization_lease_id": authorization_lease_id,
                "idempotency_digest": idempotency_digest,
                "request_fingerprint": request_fingerprint,
            }
        )
        suffix = seed[:24]
        consumption_id = (
            f"workflow-protected-runtime-context-use-authorization-consumption.{suffix}"
        )
        consumption_claim_id = (
            f"workflow-protected-runtime-context-use-authorization-consumption-claim.{suffix}"
        )
        result_id = (
            f"workflow-protected-runtime-context-use-authorization-consumption-result.{suffix}"
        )

        # Replay is the first repository operation. This path performs no attestation,
        # protected-boundary call, runtime operation, connector call or external I/O.
        replay = await self._repository.lookup_protected_runtime_context_use_authorization_consumption_replay(  # noqa: E501
            WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayLookupRequest(
                authorization_lease_id=authorization_lease_id,
                consumption_id=consumption_id,
                consumption_claim_id=consumption_claim_id,
                result_id=result_id,
                scope=context.scope,
                consumer_subject_id=context.subject_id,
                consumer_audience=context.credential_audience,
                policy_id=self._policy.policy_id,
                policy_version=self._policy.policy_version,
                policy_digest=self._policy.canonical_digest,
                source_policy_id=self._policy.source_policy_id,
                source_policy_version=self._policy.source_policy_version,
                source_policy_digest=self._policy.source_policy_digest,
                idempotency_digest=idempotency_digest,
                request_fingerprint=request_fingerprint,
            )
        )
        historical = self._resolve_replay(replay)
        if historical is not None:
            return historical

        audit_payload: dict[str, object] = {
            "schema_id": ("audit.workflow-protected-runtime-context-use-authorization-consumption"),
            "schema_version": "1.0",
            "event_type": (
                "protected_runtime_context_use_authorization_consumed_without_runtime_use"
            ),
            "consumption_id": consumption_id,
            "consumption_claim_id": consumption_claim_id,
            "result_id": result_id,
            "authorization_lease_id": authorization_lease_id,
            "scope": context.scope.canonical_value(),
            "consumer_subject_id": context.subject_id,
            "consumer_audience": context.credential_audience,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "source_policy_id": self._policy.source_policy_id,
            "source_policy_version": self._policy.source_policy_version,
            "source_policy_digest": self._policy.source_policy_digest,
            "idempotency_digest": idempotency_digest,
            "request_fingerprint": request_fingerprint,
            "irreversible_consumption_acknowledged": True,
            "context_accessed": False,
            "context_used": False,
            "runtime_started": False,
            "runtime_resumed": False,
            "network_activity_performed": False,
            "connector_activity_performed": False,
            "dispatch_performed": False,
            "execution_performed": False,
            "infrastructure_mutation_performed": False,
        }
        request = WorkflowProtectedRuntimeContextUseAuthorizationConsumptionRequest(
            authorization_lease_id=authorization_lease_id,
            consumption_id=consumption_id,
            consumption_claim_id=consumption_claim_id,
            result_id=result_id,
            scope=context.scope,
            consumer_subject_id=context.subject_id,
            consumer_audience=context.credential_audience,
            consumer_contract_id=self._policy.consumer_contract_id,
            consumer_contract_version=self._policy.consumer_contract_version,
            purpose_id=self._policy.purpose_id,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.policy_version,
            policy_digest=self._policy.canonical_digest,
            source_policy_id=self._policy.source_policy_id,
            source_policy_version=self._policy.source_policy_version,
            source_policy_digest=self._policy.source_policy_digest,
            idempotency_digest=idempotency_digest,
            request_fingerprint=request_fingerprint,
            irreversible_consumption_acknowledged=True,
            consumption_audit_payload=audit_payload,
            consumption_audit_digest=canonical_digest(audit_payload),
        )
        validate_workflow_protected_runtime_context_use_authorization_consumption_request(request)
        return self._resolve_write(
            await self._repository.consume_protected_runtime_context_use_authorization(request)
        )

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation, ...]:
        if not self._repository.durable:
            self._raise(
                "protected_runtime_context_use_authorization_consumption_durable_repository_required"
            )
        return await self._repository.list_protected_runtime_context_use_authorization_consumption_presentations(  # noqa: E501
            scope=scope,
            limit=limit,
        )

    def _require_request(self, **values: object) -> None:
        context = values["context"]
        if not isinstance(
            context, WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext
        ):
            self._raise("protected_runtime_context_use_authorization_consumption_request_invalid")
        assert isinstance(
            context, WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext
        )
        if (
            context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.subject_id != WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT
            or context.credential_audience
            != WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            or values["policy_id"] != self._policy.policy_id
            or values["policy_version"] != self._policy.policy_version
            or values["irreversible_consumption_acknowledged"] is not True
        ):
            self._raise("protected_runtime_context_use_authorization_consumption_request_invalid")
        for name in (
            "authorization_lease_id",
            "policy_id",
            "policy_version",
            "idempotency_key",
        ):
            value = values[name]
            if (
                not isinstance(value, str)
                or not value
                or value != value.strip()
                or len(value) > (128 if name == "idempotency_key" else 240)
                or any(character.isspace() for character in value)
                or (name == "idempotency_key" and len(value) < 8)
            ):
                self._raise(
                    "protected_runtime_context_use_authorization_consumption_request_invalid"
                )

    def _resolve_replay(
        self,
        replay: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayLookup,
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation | None:
        statuses = WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayStatus
        if replay.status is statuses.NONE:
            if replay.claim is not None or replay.result is not None:
                self._raise(
                    "protected_runtime_context_use_authorization_consumption_repository_violation"
                )
            return None
        if replay.status is statuses.TERMINAL:
            if replay.claim is None or replay.result is None:
                self._raise(
                    "protected_runtime_context_use_authorization_consumption_repository_violation"
                )
            return WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation(
                replay.claim, replay.result
            )
        self._raise(
            f"protected_runtime_context_use_authorization_consumption_{replay.status.value}"
        )

    def _resolve_write(
        self,
        write: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionWrite,
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation:
        statuses = WorkflowProtectedRuntimeContextUseAuthorizationConsumptionWriteStatus
        if write.status in (statuses.CONSUMED, statuses.REPLAY):
            if write.claim is None or write.result is None:
                self._raise(
                    "protected_runtime_context_use_authorization_consumption_repository_violation"
                )
            return WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation(
                write.claim, write.result
            )
        self._raise(f"protected_runtime_context_use_authorization_consumption_{write.status.value}")

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowProtectedRuntimeContextUseAuthorizationConsumptionError(code)


__all__ = [
    "WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_AUTHORIZATION_CONSUMPTION_PRODUCER",
    "WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService",
]

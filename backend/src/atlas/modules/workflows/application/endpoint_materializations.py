from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.endpoint_materialization_ports import (
    WorkflowEventPhysicalTransportEndpointMaterializationClaimRequest,
    WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus,
    WorkflowEventPhysicalTransportEndpointMaterializationError,
    WorkflowEventPhysicalTransportEndpointMaterializationRepository,
    WorkflowEventPhysicalTransportEndpointMaterializationResultRequest,
    WorkflowEventPhysicalTransportEndpointMaterializationResultStatus,
    WorkflowEventPhysicalTransportEndpointMaterializationUncertainError,
    WorkflowPhysicalTransportEndpointMaterializer,
)
from atlas.modules.workflows.application.endpoint_resolution_authorization_leases import (
    WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE,
    WorkflowPhysicalTransportEndpointResolverContext,
)
from atlas.modules.workflows.domain import (
    EventPhysicalTransportRouteSnapshot,
    EventPhysicalTransportRouteSnapshotState,
    WorkflowEventPhysicalTransportEndpointMaterializationAttempt,
    WorkflowEventPhysicalTransportEndpointMaterializationAuthority,
    WorkflowEventPhysicalTransportEndpointMaterializationInstruction,
    WorkflowEventPhysicalTransportEndpointMaterializationPolicy,
    WorkflowEventPhysicalTransportEndpointMaterializationReceipt,
    WorkflowEventPhysicalTransportEndpointMaterializationResult,
    WorkflowEventPhysicalTransportEndpointMaterializationResultState,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseState,
    WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim,
    WorkflowEventPhysicalTransportRouteBindingState,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionState,
    canonical_digest,
    code_owned_workflow_event_physical_transport_endpoint_materialization_policy,
)

WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_MATERIALIZATION_PRODUCER = (
    "project-atlas-workflow-physical-transport-endpoint-materializer"
)


@dataclass(frozen=True, slots=True)
class _ResolvedEvidence:
    lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease
    route: EventPhysicalTransportRouteSnapshot


class WorkflowEventPhysicalTransportEndpointMaterializationService:
    """Consumes one resolver lease before crossing the protected boundary."""

    def __init__(
        self,
        *,
        repository: WorkflowEventPhysicalTransportEndpointMaterializationRepository,
        materializer: WorkflowPhysicalTransportEndpointMaterializer,
        audit_sink: AuditSink,
        policy: WorkflowEventPhysicalTransportEndpointMaterializationPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._materializer = materializer
        self._audit_sink = audit_sink
        self._policy = (
            policy or code_owned_workflow_event_physical_transport_endpoint_materialization_policy()
        )

    @property
    def repository(
        self,
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationRepository:
        return self._repository

    @property
    def durable(self) -> bool:
        return self._repository.durable

    async def materialize(
        self,
        *,
        authorization_lease_id: str,
        authorization_lease_digest: str,
        materialization_policy_id: str,
        materialization_policy_version: str,
        irreversible_consumption_acknowledged: bool,
        uncertain_outcome_requires_new_authorization_acknowledged: bool,
        idempotency_key: str,
        context: WorkflowPhysicalTransportEndpointResolverContext,
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationResult:
        self._require_request(
            authorization_lease_id=authorization_lease_id,
            authorization_lease_digest=authorization_lease_digest,
            materialization_policy_id=materialization_policy_id,
            materialization_policy_version=materialization_policy_version,
            irreversible_consumption_acknowledged=irreversible_consumption_acknowledged,
            uncertain_outcome_requires_new_authorization_acknowledged=(
                uncertain_outcome_requires_new_authorization_acknowledged
            ),
            idempotency_key=idempotency_key,
            context=context,
        )
        if not self._repository.durable:
            self._raise("endpoint_materialization_durable_repository_required")
        if (
            not self._materializer.available
            or self._materializer.materializer_contract_id
            != self._policy.required_materializer_contract_id
        ):
            self._raise("endpoint_materialization_trusted_materializer_unavailable")

        evidence = await self._load_and_validate_evidence(
            authorization_lease_id=authorization_lease_id,
            authorization_lease_digest=authorization_lease_digest,
            context=context,
        )
        fingerprint = canonical_digest(
            {
                "authorization_lease_digest": authorization_lease_digest,
                "authorization_lease_id": authorization_lease_id,
                "irreversible_consumption_acknowledged": True,
                "materialization_policy_digest": self._policy.canonical_digest,
                "materialization_policy_id": materialization_policy_id,
                "materialization_policy_version": materialization_policy_version,
                "resolver_subject_id": context.subject_id,
                "scope": context.scope.canonical_value(),
                "uncertain_outcome_requires_new_authorization_acknowledged": True,
            }
        )
        idempotency_digest = sha256(
            f"{context.subject_id}\x00{idempotency_key}".encode()
        ).hexdigest()
        seed = canonical_digest(
            {
                "authorization_lease_id": authorization_lease_id,
                "idempotency_digest": idempotency_digest,
                "request_fingerprint": fingerprint,
            }
        )
        await self._audit(
            context,
            event_kind="requested",
            outcome="requested",
            result_code="endpoint_materialization_requested",
            authorization_lease_id=authorization_lease_id,
            idempotency_key=idempotency_key,
        )
        request = WorkflowEventPhysicalTransportEndpointMaterializationClaimRequest(
            claim_id=f"workflow-endpoint-materialization-claim.{seed[:24]}",
            attempt_id=f"workflow-endpoint-materialization-attempt.{seed[:24]}",
            materialization_id=f"workflow-endpoint-materialization.{seed[:24]}",
            authorization_lease_id=authorization_lease_id,
            authorization_lease_digest=authorization_lease_digest,
            expected_freshness_admission_id=evidence.lease.freshness_admission_id,
            expected_freshness_admission_digest=evidence.lease.freshness_admission_digest,
            expected_freshness_valid_until=(await self._freshness_valid_until(evidence.lease)),
            expected_physical_transport_route_binding_id=(
                evidence.lease.physical_transport_route_binding_id
            ),
            expected_physical_transport_route_binding_digest=(
                evidence.lease.physical_transport_route_binding_digest
            ),
            expected_transport_route_snapshot_id=evidence.lease.transport_route_snapshot_id,
            expected_transport_route_snapshot_digest=(
                evidence.lease.transport_route_snapshot_digest
            ),
            expected_current_selection_head_id=evidence.lease.current_selection_head_id,
            expected_current_selection_head_digest=evidence.lease.current_selection_head_digest,
            expected_current_selection_head_generation=(
                evidence.lease.current_selection_head_generation
            ),
            expected_current_selection_head_fencing_token_digest=(
                evidence.lease.current_selection_head_fencing_token_digest
            ),
            expected_route_set_id=evidence.lease.route_set_id,
            expected_route_set_revision=evidence.lease.route_set_revision,
            expected_selection_epoch_id=evidence.lease.selection_epoch_id,
            expected_selection_epoch_revision=evidence.lease.selection_epoch_revision,
            expected_selected_route_id=evidence.lease.selected_route_id,
            expected_selected_route_revision=evidence.lease.selected_route_revision,
            expected_selected_route_digest=evidence.lease.selected_route_digest,
            expected_selection_active=evidence.lease.selection_active,
            expected_selection_eligible=evidence.lease.selection_eligible,
            expected_selection_suspended=evidence.lease.selection_suspended,
            expected_selection_withdrawn=evidence.lease.selection_withdrawn,
            expected_selection_superseded=evidence.lease.selection_superseded,
            expected_lease_state=evidence.lease.state.value,
            expected_endpoint_resolution_authorized=(
                evidence.lease.authority.endpoint_resolution_authorized
            ),
            expected_materialization_policy_id=self._policy.policy_id,
            expected_materialization_policy_version=self._policy.policy_version,
            expected_materialization_policy_digest=self._policy.canonical_digest,
            scope=context.scope,
            resolver_subject_id=context.subject_id,
            idempotency_key=idempotency_key,
            idempotency_digest=idempotency_digest,
            request_fingerprint=fingerprint,
            irreversible_consumption_acknowledged=True,
            uncertain_outcome_requires_new_authorization_acknowledged=True,
        )
        claimed = await self._repository.claim_endpoint_materialization(request)
        if claimed.status is (
            WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus.REPLAY_COMPLETED
        ):
            if claimed.result is None:
                self._uncertain("endpoint_materialization_replay_result_missing")
            return claimed.result
        if claimed.status is (
            WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus.CLAIM_ONLY_UNCERTAIN
        ):
            self._uncertain("endpoint_materialization_outcome_uncertain")
        if claimed.status is not (
            WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus.CLAIMED
        ):
            self._raise(f"endpoint_materialization_{claimed.status.value}")
        if claimed.claim is None or claimed.attempt is None or claimed.result is not None:
            self._uncertain("endpoint_materialization_claim_commit_uncertain")

        try:
            await self._audit(
                context,
                event_kind="claimed",
                outcome="consumed",
                result_code="endpoint_materialization_lease_consumed",
                authorization_lease_id=authorization_lease_id,
                idempotency_key=idempotency_key,
                materialization_id=claimed.attempt.materialization_id,
            )
        except Exception as exc:
            raise WorkflowEventPhysicalTransportEndpointMaterializationUncertainError(
                "endpoint_materialization_outcome_uncertain"
            ) from exc

        instruction = self._build_instruction(
            evidence=evidence,
            claim_id=claimed.claim.claim_id,
            attempt_id=claimed.attempt.attempt_id,
            materialization_id=claimed.attempt.materialization_id,
        )
        try:
            receipt = await self._materializer.materialize(instruction)
            self._verify_receipt(receipt, instruction)
            result = self._build_result(
                evidence=evidence,
                claim=claimed.claim,
                attempt=claimed.attempt,
                receipt=receipt,
            )
            await self._audit(
                context,
                event_kind=(
                    "completed"
                    if result.state
                    is (
                        WorkflowEventPhysicalTransportEndpointMaterializationResultState
                    ).MATERIALIZED_PROTECTED
                    else "failed"
                ),
                outcome=result.state.value,
                result_code=f"endpoint_materialization_{result.state.value}",
                authorization_lease_id=authorization_lease_id,
                idempotency_key=idempotency_key,
                materialization_id=result.materialization_id,
            )
            written = await self._repository.record_endpoint_materialization_result(
                WorkflowEventPhysicalTransportEndpointMaterializationResultRequest(
                    result=result,
                    expected_claim_digest=claimed.claim.canonical_digest,
                    expected_attempt_digest=claimed.attempt.canonical_digest,
                    expected_current_selection_head_id=(evidence.lease.current_selection_head_id),
                    expected_current_selection_head_digest=(
                        evidence.lease.current_selection_head_digest
                    ),
                    expected_current_selection_head_generation=(
                        evidence.lease.current_selection_head_generation
                    ),
                    expected_current_selection_head_fencing_token_digest=(
                        evidence.lease.current_selection_head_fencing_token_digest
                    ),
                    expected_lease_valid_until=evidence.lease.valid_until,
                )
            )
        except WorkflowEventPhysicalTransportEndpointMaterializationUncertainError:
            raise
        except Exception as exc:
            raise WorkflowEventPhysicalTransportEndpointMaterializationUncertainError(
                "endpoint_materialization_outcome_uncertain"
            ) from exc
        if (
            written.status
            not in (
                WorkflowEventPhysicalTransportEndpointMaterializationResultStatus.RECORDED,
                WorkflowEventPhysicalTransportEndpointMaterializationResultStatus.REPLAY,
            )
            or written.result is None
        ):
            self._uncertain("endpoint_materialization_result_persistence_uncertain")
        return written.result

    def _require_request(self, **values: object) -> None:
        context = values["context"]
        assert isinstance(context, WorkflowPhysicalTransportEndpointResolverContext)
        identifiers = (
            values["authorization_lease_id"],
            values["materialization_policy_id"],
            values["materialization_policy_version"],
            values["idempotency_key"],
        )
        if (
            context.actor_type != "service"
            or context.credential_audience != WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE
            or any(
                not isinstance(value, str)
                or not value
                or value != value.strip()
                or len(value) > 240
                for value in identifiers
            )
            or not isinstance(values["authorization_lease_digest"], str)
            or len(values["authorization_lease_digest"]) != 64
            or values["materialization_policy_id"] != self._policy.policy_id
            or values["materialization_policy_version"] != self._policy.policy_version
            or values["irreversible_consumption_acknowledged"] is not True
            or values["uncertain_outcome_requires_new_authorization_acknowledged"] is not True
        ):
            self._raise("endpoint_materialization_request_invalid")

    async def _load_and_validate_evidence(
        self,
        *,
        authorization_lease_id: str,
        authorization_lease_digest: str,
        context: WorkflowPhysicalTransportEndpointResolverContext,
    ) -> _ResolvedEvidence:
        lease = await self._repository.get_endpoint_resolution_authorization_lease_by_id(
            authorization_lease_id=authorization_lease_id
        )
        if lease is None:
            self._raise("endpoint_materialization_lease_not_found")
        assert lease is not None
        admission = await self._repository.get_route_freshness_admission_by_id(
            freshness_admission_id=lease.freshness_admission_id
        )
        binding = await self._repository.get_physical_transport_route_binding_by_id(
            binding_id=lease.physical_transport_route_binding_id
        )
        route = await self._repository.get_transport_route_snapshot_by_id(
            snapshot_id=lease.transport_route_snapshot_id
        )
        head = await self._repository.get_current_route_selection_head(
            scope=lease.scope, route_set_id=lease.route_set_id
        )
        now = await self._repository.get_authoritative_time()
        if (
            admission is None
            or binding is None
            or route is None
            or head is None
            or lease.canonical_digest != authorization_lease_digest
            or lease.scope != context.scope
            or lease.resolver_subject_id != context.subject_id
            or lease.state
            is not (
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseState
            ).AUTHORIZED_UNCONSUMED
            or not lease.grants_endpoint_resolution_authority
            or now >= lease.valid_until
            or admission.state
            is not WorkflowEventPhysicalTransportRouteFreshnessAdmissionState.ADMITTED_CURRENT
            or now >= admission.valid_until
            or binding.state is not WorkflowEventPhysicalTransportRouteBindingState.BOUND
            or route.state is not EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED
            or admission.canonical_digest != lease.freshness_admission_digest
            or binding.canonical_digest != lease.physical_transport_route_binding_digest
            or route.canonical_digest != lease.transport_route_snapshot_digest
            or head.canonical_digest != lease.current_selection_head_digest
            or head.head_id != lease.current_selection_head_id
            or head.generation != lease.current_selection_head_generation
            or head.fencing_token_digest != lease.current_selection_head_fencing_token_digest
            or route.route_id != lease.selected_route_id
            or route.route_revision != lease.selected_route_revision
            or route.source_route_digest != lease.selected_route_digest
            or route.route_set_id != lease.route_set_id
            or route.route_set_revision != lease.route_set_revision
            or route.selection_epoch_id != lease.selection_epoch_id
            or route.selection_epoch_revision != lease.selection_epoch_revision
            or not head.selection_active
            or not head.selection_eligible
            or head.selection_suspended
            or head.selection_withdrawn
            or head.selection_superseded
        ):
            self._raise("endpoint_materialization_evidence_invalid")
        return _ResolvedEvidence(lease=lease, route=route)

    async def _freshness_valid_until(
        self, lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease
    ) -> datetime:
        admission = await self._repository.get_route_freshness_admission_by_id(
            freshness_admission_id=lease.freshness_admission_id
        )
        if admission is None:
            self._raise("endpoint_materialization_evidence_invalid")
        return admission.valid_until

    def _build_instruction(
        self,
        *,
        evidence: _ResolvedEvidence,
        claim_id: str,
        attempt_id: str,
        materialization_id: str,
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationInstruction:
        route = evidence.route
        values: dict[str, Any] = {
            "materialization_id": materialization_id,
            "attempt_id": attempt_id,
            "consumption_claim_id": claim_id,
            "authorization_lease_id": evidence.lease.authorization_lease_id,
            "authorization_lease_digest": evidence.lease.canonical_digest,
            "transport_route_snapshot_id": route.snapshot_id,
            "transport_route_snapshot_digest": route.canonical_digest,
            "route_id": route.route_id,
            "route_revision": route.route_revision,
            "source_route_digest": route.source_route_digest,
            "endpoint_set_id": route.endpoint_set_id,
            "endpoint_set_revision": route.endpoint_set_revision,
            "destination_id": route.destination_id,
            "destination_revision": route.destination_revision,
            "routing_contract_id": route.routing_contract_id,
            "routing_contract_revision": route.routing_contract_revision,
            "private_route_descriptor_commitment": route.private_route_descriptor_commitment,
            "scope": route.scope,
            "resolver_subject_id": evidence.lease.resolver_subject_id,
            "materializer_contract_id": self._policy.required_materializer_contract_id,
            "materializer_attestor_id": self._policy.required_materializer_attestor_id,
            "protected_artifact_schema_id": self._policy.protected_artifact_schema_id,
            "protected_artifact_schema_version": self._policy.protected_artifact_schema_version,
            "protected_artifact_profile_digest": self._policy.protected_artifact_profile_digest,
            "maximum_endpoint_count": self._policy.maximum_endpoint_count,
            "lease_valid_until": evidence.lease.valid_until,
        }
        payload = {
            **values,
            "scope": route.scope.canonical_value(),
            "lease_valid_until": evidence.lease.valid_until.isoformat(),
        }
        return WorkflowEventPhysicalTransportEndpointMaterializationInstruction(
            **cast(Any, values),
            canonical_digest=canonical_digest(payload),
        )

    def _verify_receipt(
        self,
        receipt: WorkflowEventPhysicalTransportEndpointMaterializationReceipt,
        instruction: WorkflowEventPhysicalTransportEndpointMaterializationInstruction,
    ) -> None:
        if (
            receipt.materialization_id != instruction.materialization_id
            or receipt.attempt_id != instruction.attempt_id
            or receipt.consumption_claim_id != instruction.consumption_claim_id
            or receipt.instruction_digest != instruction.canonical_digest
            or receipt.materializer_contract_id != instruction.materializer_contract_id
            or receipt.attested_by != instruction.materializer_attestor_id
            or receipt.resolver_subject_id != instruction.resolver_subject_id
            or receipt.protected_artifact_schema_id != instruction.protected_artifact_schema_id
            or receipt.protected_artifact_schema_version
            != instruction.protected_artifact_schema_version
            or receipt.protected_artifact_profile_digest
            != instruction.protected_artifact_profile_digest
            or receipt.source_route_digest != instruction.source_route_digest
            or receipt.private_route_descriptor_commitment
            != instruction.private_route_descriptor_commitment
            or receipt.endpoint_count > instruction.maximum_endpoint_count
            or receipt.completed_at >= instruction.lease_valid_until
            or (
                receipt.usable_until is not None
                and receipt.usable_until > instruction.lease_valid_until
            )
        ):
            self._uncertain("endpoint_materialization_receipt_invalid")

    def _build_result(
        self,
        *,
        evidence: _ResolvedEvidence,
        claim: WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim,
        attempt: WorkflowEventPhysicalTransportEndpointMaterializationAttempt,
        receipt: WorkflowEventPhysicalTransportEndpointMaterializationReceipt,
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationResult:
        values: dict[str, Any] = {
            "materialization_id": attempt.materialization_id,
            "attempt_id": attempt.attempt_id,
            "attempt_digest": attempt.canonical_digest,
            "consumption_claim_id": claim.claim_id,
            "consumption_claim_digest": claim.canonical_digest,
            "authorization_lease_id": evidence.lease.authorization_lease_id,
            "authorization_lease_digest": evidence.lease.canonical_digest,
            "freshness_admission_id": evidence.lease.freshness_admission_id,
            "freshness_admission_digest": evidence.lease.freshness_admission_digest,
            "transport_route_snapshot_id": evidence.route.snapshot_id,
            "transport_route_snapshot_digest": evidence.route.canonical_digest,
            "scope": evidence.lease.scope,
            "resolver_subject_id": evidence.lease.resolver_subject_id,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "materializer_id": receipt.materializer_id,
            "materializer_version": receipt.materializer_version,
            "materialization_receipt_digest": receipt.canonical_digest,
            "state": receipt.state,
            "failure_class": receipt.failure_class,
            "protected_artifact_id": receipt.protected_artifact_id,
            "protected_artifact_digest": receipt.protected_artifact_digest,
            "normalized_endpoint_set_digest": receipt.normalized_endpoint_set_digest,
            "endpoint_count": receipt.endpoint_count,
            "protected_artifact_schema_id": receipt.protected_artifact_schema_id,
            "protected_artifact_schema_version": receipt.protected_artifact_schema_version,
            "protected_artifact_profile_digest": receipt.protected_artifact_profile_digest,
            "completed_at": receipt.completed_at,
            "usable_until": receipt.usable_until,
            "protected_artifact_revoked": receipt.protected_artifact_revoked,
            "cleanup_confirmed": receipt.cleanup_confirmed,
            "authority": WorkflowEventPhysicalTransportEndpointMaterializationAuthority(),
        }
        payload = {
            "attempt_digest": values["attempt_digest"],
            "attempt_id": values["attempt_id"],
            "authority": values["authority"].canonical_value(),
            "authorization_lease_digest": values["authorization_lease_digest"],
            "authorization_lease_id": values["authorization_lease_id"],
            "canonical_materialization_receipt_digest": values["materialization_receipt_digest"],
            "cleanup_confirmed": values["cleanup_confirmed"],
            "completed_at": values["completed_at"].isoformat(),
            "consumption_claim_digest": values["consumption_claim_digest"],
            "consumption_claim_id": values["consumption_claim_id"],
            "endpoint_count": values["endpoint_count"],
            "failure_class": (
                None if values["failure_class"] is None else values["failure_class"].value
            ),
            "freshness_admission_digest": values["freshness_admission_digest"],
            "freshness_admission_id": values["freshness_admission_id"],
            "materialization_id": values["materialization_id"],
            "materializer_id": values["materializer_id"],
            "materializer_version": values["materializer_version"],
            "normalized_endpoint_set_digest": values["normalized_endpoint_set_digest"],
            "policy_digest": values["policy_digest"],
            "policy_id": values["policy_id"],
            "policy_version": values["policy_version"],
            "protected_artifact_digest": values["protected_artifact_digest"],
            "protected_artifact_id": values["protected_artifact_id"],
            "protected_artifact_profile_digest": values["protected_artifact_profile_digest"],
            "protected_artifact_revoked": values["protected_artifact_revoked"],
            "protected_artifact_schema_id": values["protected_artifact_schema_id"],
            "protected_artifact_schema_version": values["protected_artifact_schema_version"],
            "resolver_subject_id": values["resolver_subject_id"],
            "scope": values["scope"].canonical_value(),
            "state": values["state"].value,
            "transport_route_snapshot_digest": values["transport_route_snapshot_digest"],
            "transport_route_snapshot_id": values["transport_route_snapshot_id"],
            "usable_until": (
                None if values["usable_until"] is None else values["usable_until"].isoformat()
            ),
        }
        return WorkflowEventPhysicalTransportEndpointMaterializationResult(
            **cast(Any, values), canonical_digest=canonical_digest(payload)
        )

    async def _audit(
        self,
        context: WorkflowPhysicalTransportEndpointResolverContext,
        *,
        event_kind: str,
        outcome: str,
        result_code: str,
        authorization_lease_id: str,
        idempotency_key: str,
        materialization_id: str = "none",
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=f"atlas.workflow.endpoint-materialization.{event_kind}",
                schema_version="1.0",
                producer=WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_MATERIALIZATION_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.physical-transport-endpoint.materialize",
                resource_type="resource.workflow-protected-endpoint-materialization",
                scope_reference="/".join(context.scope.canonical_value().values()),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    ("authorization_lease_id", authorization_lease_id),
                    ("materialization_id", materialization_id),
                    ("all_post_materialization_authority", "false"),
                ),
            )
        )

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowEventPhysicalTransportEndpointMaterializationError(code)

    @staticmethod
    def _uncertain(code: str) -> NoReturn:
        raise WorkflowEventPhysicalTransportEndpointMaterializationUncertainError(code)


__all__ = [
    "WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_MATERIALIZATION_PRODUCER",
    "WorkflowEventPhysicalTransportEndpointMaterializationService",
]

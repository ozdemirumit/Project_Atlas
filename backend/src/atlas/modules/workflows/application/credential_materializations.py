from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.credential_access_authorization_leases import (
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT,
    WorkflowPhysicalTransportCredentialAccessorContext,
)
from atlas.modules.workflows.application.credential_materialization_ports import (
    WorkflowEventPhysicalTransportCredentialMaterializationClaimRequest,
    WorkflowEventPhysicalTransportCredentialMaterializationClaimStatus,
    WorkflowEventPhysicalTransportCredentialMaterializationError,
    WorkflowEventPhysicalTransportCredentialMaterializationRepository,
    WorkflowEventPhysicalTransportCredentialMaterializationResultRequest,
    WorkflowEventPhysicalTransportCredentialMaterializationResultStatus,
    WorkflowEventPhysicalTransportCredentialMaterializationUncertainError,
    WorkflowPhysicalTransportCredentialMaterializer,
)
from atlas.modules.workflows.domain import (
    DeploymentPhysicalTransportCredentialAssignment,
    EventPhysicalTransportCredentialAssignmentSnapshot,
    EventPhysicalTransportCredentialAssignmentSnapshotState,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseState,
    WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingState,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionState,
    WorkflowEventPhysicalTransportCredentialMaterializationAttempt,
    WorkflowEventPhysicalTransportCredentialMaterializationAuthority,
    WorkflowEventPhysicalTransportCredentialMaterializationInstruction,
    WorkflowEventPhysicalTransportCredentialMaterializationPolicy,
    WorkflowEventPhysicalTransportCredentialMaterializationReceipt,
    WorkflowEventPhysicalTransportCredentialMaterializationResult,
    WorkflowEventPhysicalTransportCredentialMaterializationResultState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_credential_materialization_policy,
)

WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_MATERIALIZATION_PRODUCER = (
    "project-atlas-workflow-physical-transport-credential-materializer"
)


@dataclass(frozen=True, slots=True)
class _ResolvedCredentialEvidence:
    lease: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease
    snapshot: EventPhysicalTransportCredentialAssignmentSnapshot
    head: DeploymentPhysicalTransportCredentialAssignment


class WorkflowEventPhysicalTransportCredentialMaterializationService:
    """Consumes one credential-access lease before protected materialization."""

    def __init__(
        self,
        *,
        repository: WorkflowEventPhysicalTransportCredentialMaterializationRepository,
        materializer: WorkflowPhysicalTransportCredentialMaterializer,
        audit_sink: AuditSink,
        policy: WorkflowEventPhysicalTransportCredentialMaterializationPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._materializer = materializer
        self._audit_sink = audit_sink
        self._policy = (
            policy
            or code_owned_workflow_event_physical_transport_credential_materialization_policy()
        )

    @property
    def repository(self) -> WorkflowEventPhysicalTransportCredentialMaterializationRepository:
        return self._repository

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def policy(self) -> WorkflowEventPhysicalTransportCredentialMaterializationPolicy:
        return self._policy

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
        context: WorkflowPhysicalTransportCredentialAccessorContext,
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationResult:
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
            self._raise("credential_materialization_durable_repository_required")
        if (
            not self._materializer.available
            or self._materializer.materializer_contract_id
            != self._policy.required_materializer_contract_id
        ):
            self._raise("credential_materialization_trusted_materializer_unavailable")

        evidence = await self._load_and_validate_evidence(
            authorization_lease_id=authorization_lease_id,
            authorization_lease_digest=authorization_lease_digest,
            context=context,
        )
        idempotency_digest = sha256(
            f"{context.subject_id}\x00{idempotency_key}".encode()
        ).hexdigest()
        fingerprint = canonical_digest(
            {
                "accessor_subject_id": context.subject_id,
                "authorization_lease_digest": authorization_lease_digest,
                "authorization_lease_id": authorization_lease_id,
                "idempotency_digest": idempotency_digest,
                "irreversible_consumption_acknowledged": True,
                "materialization_policy_digest": self._policy.canonical_digest,
                "materialization_policy_id": materialization_policy_id,
                "materialization_policy_version": materialization_policy_version,
                "scope": context.scope.canonical_value(),
                "uncertain_outcome_requires_new_authorization_acknowledged": True,
            }
        )
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
            result_code="credential_materialization_requested",
            authorization_lease_id=authorization_lease_id,
            idempotency_key=idempotency_key,
        )

        async def required_precommit_audit() -> None:
            await self._audit(
                context,
                event_kind="authorized",
                outcome="authorized",
                result_code="credential_materialization_lease_consumption_authorized",
                authorization_lease_id=authorization_lease_id,
                idempotency_key=idempotency_key,
                materialization_id=f"workflow-credential-materialization.{seed[:24]}",
            )

        request = WorkflowEventPhysicalTransportCredentialMaterializationClaimRequest(
            claim_id=f"workflow-credential-materialization-claim.{seed[:24]}",
            attempt_id=f"workflow-credential-materialization-attempt.{seed[:24]}",
            materialization_id=f"workflow-credential-materialization.{seed[:24]}",
            authorization_lease_id=authorization_lease_id,
            authorization_lease_digest=authorization_lease_digest,
            expected_freshness_admission_id=evidence.lease.freshness_admission_id,
            expected_freshness_admission_digest=evidence.lease.freshness_admission_digest,
            expected_freshness_valid_until=await self._freshness_valid_until(evidence.lease),
            expected_credential_assignment_binding_id=(
                evidence.lease.physical_transport_credential_assignment_binding_id
            ),
            expected_credential_assignment_binding_digest=(
                evidence.lease.physical_transport_credential_assignment_binding_digest
            ),
            expected_credential_assignment_snapshot_id=(
                evidence.lease.credential_assignment_snapshot_id
            ),
            expected_credential_assignment_snapshot_digest=(
                evidence.lease.credential_assignment_snapshot_digest
            ),
            expected_assignment_id=evidence.lease.assignment_id,
            expected_assignment_revision=evidence.lease.assignment_revision,
            expected_source_assignment_digest=evidence.lease.source_assignment_digest,
            expected_credential_generation=evidence.lease.credential_generation,
            expected_rotation_epoch=evidence.lease.rotation_epoch,
            expected_assignment_activated_at=evidence.lease.assignment_activated_at,
            expected_assignment_expires_at=evidence.lease.assignment_expires_at,
            expected_assignment_active=evidence.lease.assignment_active,
            expected_assignment_revoked=not evidence.lease.assignment_non_revoked,
            expected_lease_state=evidence.lease.state.value,
            expected_credential_access_authorized=(
                evidence.lease.authority.credential_access_authorized
            ),
            expected_materialization_policy_id=self._policy.policy_id,
            expected_materialization_policy_version=self._policy.policy_version,
            expected_materialization_policy_digest=self._policy.canonical_digest,
            scope=context.scope,
            accessor_subject_id=context.subject_id,
            idempotency_key=idempotency_key,
            idempotency_digest=idempotency_digest,
            request_fingerprint=fingerprint,
            irreversible_consumption_acknowledged=True,
            uncertain_outcome_requires_new_authorization_acknowledged=True,
            required_precommit_audit=required_precommit_audit,
        )
        claimed = await self._repository.claim_credential_materialization(request)
        if (
            claimed.status
            is WorkflowEventPhysicalTransportCredentialMaterializationClaimStatus.REPLAY_COMPLETED
        ):
            if claimed.result is None:
                self._uncertain("credential_materialization_replay_result_missing")
            return claimed.result
        if (
            claimed.status
            is (
                WorkflowEventPhysicalTransportCredentialMaterializationClaimStatus
            ).CLAIM_ONLY_UNCERTAIN
        ):
            self._uncertain("credential_materialization_outcome_uncertain")
        if (
            claimed.status
            is not WorkflowEventPhysicalTransportCredentialMaterializationClaimStatus.CLAIMED
        ):
            self._raise(f"credential_materialization_{claimed.status.value}")
        if claimed.claim is None or claimed.attempt is None or claimed.result is not None:
            self._uncertain("credential_materialization_claim_commit_uncertain")

        instruction = self._build_instruction(
            evidence=evidence,
            claim_id=claimed.claim.claim_id,
            attempt_id=claimed.attempt.attempt_id,
            materialization_id=claimed.attempt.materialization_id,
            started_at=claimed.attempt.started_at,
        )
        receipt: WorkflowEventPhysicalTransportCredentialMaterializationReceipt | None = None
        receipt_verified = False
        try:
            receipt = await self._materializer.materialize(instruction)
            await self._verify_receipt(receipt, instruction)
            receipt_verified = True
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
                        WorkflowEventPhysicalTransportCredentialMaterializationResultState
                    ).MATERIALIZED_PROTECTED
                    else "failed"
                ),
                outcome=result.state.value,
                result_code=f"credential_materialization_{result.state.value}",
                authorization_lease_id=authorization_lease_id,
                idempotency_key=idempotency_key,
                materialization_id=result.materialization_id,
            )
            written = await self._repository.record_credential_materialization_result(
                WorkflowEventPhysicalTransportCredentialMaterializationResultRequest(
                    result=result,
                    expected_claim_digest=claimed.claim.canonical_digest,
                    expected_attempt_digest=claimed.attempt.canonical_digest,
                    expected_assignment_id=evidence.head.assignment_id,
                    expected_assignment_revision=evidence.head.assignment_revision,
                    expected_source_assignment_digest=evidence.head.canonical_digest,
                    expected_credential_generation=evidence.head.credential_generation,
                    expected_rotation_epoch=evidence.head.rotation_epoch,
                    expected_lease_valid_until=evidence.lease.valid_until,
                )
            )
        except WorkflowEventPhysicalTransportCredentialMaterializationUncertainError:
            if receipt_verified and receipt is not None:
                await self._cleanup_live_artifact(receipt)
            raise
        except Exception as exc:
            if receipt_verified and receipt is not None:
                await self._cleanup_live_artifact(receipt)
            raise WorkflowEventPhysicalTransportCredentialMaterializationUncertainError(
                "credential_materialization_outcome_uncertain"
            ) from exc
        if (
            written.status
            not in (
                WorkflowEventPhysicalTransportCredentialMaterializationResultStatus.RECORDED,
                WorkflowEventPhysicalTransportCredentialMaterializationResultStatus.REPLAY,
            )
            or written.result is None
        ):
            if receipt is not None:
                await self._cleanup_live_artifact(receipt)
            self._uncertain("credential_materialization_result_persistence_uncertain")
        return written.result

    def _require_request(self, **values: object) -> None:
        context = values["context"]
        assert isinstance(context, WorkflowPhysicalTransportCredentialAccessorContext)
        identifiers = (
            values["authorization_lease_id"],
            values["materialization_policy_id"],
            values["materialization_policy_version"],
            values["idempotency_key"],
        )
        if (
            context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.subject_id != WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT
            or context.credential_audience
            != WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE
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
            self._raise("credential_materialization_request_invalid")

    async def _load_and_validate_evidence(
        self,
        *,
        authorization_lease_id: str,
        authorization_lease_digest: str,
        context: WorkflowPhysicalTransportCredentialAccessorContext,
    ) -> _ResolvedCredentialEvidence:
        lease = await self._repository.get_credential_access_authorization_lease_by_id(
            authorization_lease_id=authorization_lease_id
        )
        if lease is None:
            self._raise("credential_materialization_lease_not_found")
        admission = await self._repository.get_credential_assignment_freshness_admission_by_id(
            freshness_admission_id=lease.freshness_admission_id
        )
        binding = await self._repository.get_credential_assignment_binding_by_id(
            binding_id=lease.physical_transport_credential_assignment_binding_id
        )
        snapshot = await self._repository.get_credential_assignment_snapshot_by_id(
            snapshot_id=lease.credential_assignment_snapshot_id
        )
        head = await self._repository.get_current_credential_assignment_head(
            assignment_id=lease.assignment_id
        )
        now = await self._repository.get_authoritative_time()
        if (
            admission is None
            or binding is None
            or snapshot is None
            or head is None
            or lease.canonical_digest != authorization_lease_digest
            or lease.scope != context.scope
            or lease.accessor_subject_id != context.subject_id
            or lease.state
            is not (
                WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseState
            ).AUTHORIZED_UNCONSUMED
            or lease.authority.credential_access_authorized is not True
            or any(
                value is not False
                for name, value in lease.authority.canonical_value().items()
                if name != "credential_access_authorized"
            )
            or not lease.issued_at <= now < lease.valid_until
            or admission.state
            is not (
                WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionState
            ).ADMITTED_CURRENT
            or not admission.evaluated_at <= now < admission.valid_until
            or binding.state
            is not WorkflowEventPhysicalTransportCredentialAssignmentBindingState.BOUND
            or snapshot.state
            is not EventPhysicalTransportCredentialAssignmentSnapshotState.SNAPSHOTTED
            or admission.canonical_digest != lease.freshness_admission_digest
            or binding.canonical_digest
            != lease.physical_transport_credential_assignment_binding_digest
            or snapshot.canonical_digest != lease.credential_assignment_snapshot_digest
            or head.canonical_digest != lease.source_assignment_digest
            or head.assignment_id != lease.assignment_id
            or head.assignment_revision != lease.assignment_revision
            or head.credential_generation != lease.credential_generation
            or head.rotation_epoch != lease.rotation_epoch
            or head.activated_at != lease.assignment_activated_at
            or head.expires_at != lease.assignment_expires_at
            or head.active is not True
            or head.revoked is not False
        ):
            self._raise("credential_materialization_evidence_invalid")
        return _ResolvedCredentialEvidence(lease=lease, snapshot=snapshot, head=head)

    async def _freshness_valid_until(
        self, lease: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease
    ) -> datetime:
        admission = await self._repository.get_credential_assignment_freshness_admission_by_id(
            freshness_admission_id=lease.freshness_admission_id
        )
        if admission is None:
            self._raise("credential_materialization_evidence_invalid")
        return admission.valid_until

    def _build_instruction(
        self,
        *,
        evidence: _ResolvedCredentialEvidence,
        claim_id: str,
        attempt_id: str,
        materialization_id: str,
        started_at: datetime,
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationInstruction:
        snapshot = evidence.snapshot
        values: dict[str, Any] = {
            "materialization_id": materialization_id,
            "attempt_id": attempt_id,
            "consumption_claim_id": claim_id,
            "authorization_lease_id": evidence.lease.authorization_lease_id,
            "authorization_lease_digest": evidence.lease.canonical_digest,
            "credential_assignment_snapshot_id": snapshot.snapshot_id,
            "credential_assignment_snapshot_digest": snapshot.canonical_digest,
            "assignment_id": snapshot.assignment_id,
            "assignment_revision": snapshot.assignment_revision,
            "source_assignment_digest": snapshot.source_assignment_digest,
            "credential_requirement_profile_id": snapshot.credential_requirement_profile_id,
            "credential_requirement_profile_version": (
                snapshot.credential_requirement_profile_version
            ),
            "credential_requirement_profile_digest": (
                snapshot.credential_requirement_profile_digest
            ),
            "credential_profile_id": snapshot.credential_profile_id,
            "credential_profile_version": snapshot.credential_profile_version,
            "credential_profile_digest": snapshot.credential_profile_digest,
            "authentication_mechanism_class": snapshot.authentication_mechanism_class,
            "principal_class": snapshot.principal_class,
            "privilege_class": snapshot.privilege_class,
            "target_scope_commitment": snapshot.target_scope_commitment,
            "credential_generation": snapshot.credential_generation,
            "rotation_epoch": snapshot.rotation_epoch,
            "broker_policy_id": snapshot.broker_policy_id,
            "broker_policy_version": snapshot.broker_policy_version,
            "broker_policy_digest": snapshot.broker_policy_digest,
            "scope": snapshot.scope,
            "accessor_subject_id": evidence.lease.accessor_subject_id,
            "materializer_contract_id": self._policy.required_materializer_contract_id,
            "materializer_attestor_id": self._policy.required_materializer_attestor_id,
            "protected_artifact_schema_id": self._policy.protected_artifact_schema_id,
            "protected_artifact_schema_version": self._policy.protected_artifact_schema_version,
            "protected_artifact_profile_digest": self._policy.protected_artifact_profile_digest,
            "started_at": started_at,
            "lease_valid_until": evidence.lease.valid_until,
        }
        return WorkflowEventPhysicalTransportCredentialMaterializationInstruction(
            **cast(Any, values), canonical_digest=canonical_digest(_canonical_payload(values))
        )

    async def _verify_receipt(
        self,
        receipt: WorkflowEventPhysicalTransportCredentialMaterializationReceipt,
        instruction: WorkflowEventPhysicalTransportCredentialMaterializationInstruction,
    ) -> None:
        invalid = (
            receipt.materialization_id != instruction.materialization_id
            or receipt.attempt_id != instruction.attempt_id
            or receipt.consumption_claim_id != instruction.consumption_claim_id
            or receipt.instruction_digest != instruction.canonical_digest
            or receipt.materializer_contract_id != instruction.materializer_contract_id
            or receipt.attested_by != instruction.materializer_attestor_id
            or receipt.accessor_subject_id != instruction.accessor_subject_id
            or receipt.protected_artifact_schema_id != instruction.protected_artifact_schema_id
            or receipt.protected_artifact_schema_version
            != instruction.protected_artifact_schema_version
            or receipt.protected_artifact_profile_digest
            != instruction.protected_artifact_profile_digest
            or receipt.source_assignment_digest != instruction.source_assignment_digest
            or receipt.credential_generation != instruction.credential_generation
            or receipt.rotation_epoch != instruction.rotation_epoch
            or (
                receipt.materialized_at is not None
                and receipt.materialized_at < instruction.started_at
            )
            or receipt.completed_at >= instruction.lease_valid_until
            or (
                receipt.usable_until is not None
                and receipt.usable_until > instruction.lease_valid_until
            )
            or (
                receipt.materialized_at is not None
                and receipt.usable_until is not None
                and receipt.usable_until - receipt.materialized_at
                > timedelta(seconds=self._policy.maximum_artifact_lifetime_seconds)
            )
        )
        if invalid:
            try:
                cleaned = await self._materializer.revoke_or_destroy(receipt)
            except Exception as exc:
                raise WorkflowEventPhysicalTransportCredentialMaterializationUncertainError(
                    "credential_materialization_cleanup_uncertain"
                ) from exc
            if cleaned is not True:
                self._uncertain("credential_materialization_cleanup_uncertain")
            self._uncertain("credential_materialization_receipt_invalid")

    async def _cleanup_live_artifact(
        self,
        receipt: WorkflowEventPhysicalTransportCredentialMaterializationReceipt,
    ) -> None:
        if (
            receipt.state
            is not (
                WorkflowEventPhysicalTransportCredentialMaterializationResultState
            ).MATERIALIZED_PROTECTED
            or receipt.protected_artifact_revoked
        ):
            return
        try:
            cleaned = await self._materializer.revoke_or_destroy(receipt)
        except Exception as exc:
            raise WorkflowEventPhysicalTransportCredentialMaterializationUncertainError(
                "credential_materialization_cleanup_uncertain"
            ) from exc
        if cleaned is not True:
            self._uncertain("credential_materialization_cleanup_uncertain")

    def _build_result(
        self,
        *,
        evidence: _ResolvedCredentialEvidence,
        claim: WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim,
        attempt: WorkflowEventPhysicalTransportCredentialMaterializationAttempt,
        receipt: WorkflowEventPhysicalTransportCredentialMaterializationReceipt,
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationResult:
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
            "credential_assignment_snapshot_id": evidence.snapshot.snapshot_id,
            "credential_assignment_snapshot_digest": evidence.snapshot.canonical_digest,
            "assignment_id": evidence.head.assignment_id,
            "assignment_revision": evidence.head.assignment_revision,
            "credential_generation": evidence.head.credential_generation,
            "rotation_epoch": evidence.head.rotation_epoch,
            "scope": evidence.lease.scope,
            "accessor_subject_id": evidence.lease.accessor_subject_id,
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
            "protected_artifact_schema_id": receipt.protected_artifact_schema_id,
            "protected_artifact_schema_version": receipt.protected_artifact_schema_version,
            "protected_artifact_profile_digest": receipt.protected_artifact_profile_digest,
            "completed_at": receipt.completed_at,
            "usable_until": receipt.usable_until,
            "protected_artifact_revoked": receipt.protected_artifact_revoked,
            "cleanup_confirmed": receipt.cleanup_confirmed,
            "authority": WorkflowEventPhysicalTransportCredentialMaterializationAuthority(),
        }
        return WorkflowEventPhysicalTransportCredentialMaterializationResult(
            **cast(Any, values), canonical_digest=canonical_digest(_canonical_payload(values))
        )

    async def _audit(
        self,
        context: WorkflowPhysicalTransportCredentialAccessorContext,
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
                event_type=f"atlas.workflow.credential-materialization.{event_kind}",
                schema_version="1.0",
                producer=WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_MATERIALIZATION_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.physical-transport-credential.materialize",
                resource_type="resource.workflow-protected-credential-materialization",
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
        raise WorkflowEventPhysicalTransportCredentialMaterializationError(code)

    @staticmethod
    def _uncertain(code: str) -> NoReturn:
        raise WorkflowEventPhysicalTransportCredentialMaterializationUncertainError(code)


def _canonical_payload(values: dict[str, Any]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for name, value in values.items():
        if isinstance(value, datetime):
            payload[name] = value.isoformat()
        elif isinstance(value, StrEnum):
            payload[name] = value.value
        elif isinstance(
            value,
            (WorkflowScope, WorkflowEventPhysicalTransportCredentialMaterializationAuthority),
        ):
            payload[name] = value.canonical_value()
        else:
            payload[name] = value
    return payload


__all__ = [
    "WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_MATERIALIZATION_PRODUCER",
    "WorkflowEventPhysicalTransportCredentialMaterializationService",
]

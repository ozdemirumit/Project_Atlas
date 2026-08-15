from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.target_context_access_authorization_lease_ports import (
    WorkflowProtectedArtifactStatusAttestationRequest,
    WorkflowProtectedArtifactStatusSignatureVerifier,
    WorkflowProtectedCredentialStatusAttestor,
    WorkflowProtectedEndpointStatusAttestor,
)
from atlas.modules.workflows.application.target_context_access_authorization_leases import (
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_SUBJECT,
    WorkflowPhysicalTransportTargetContextAccessorContext,
)
from atlas.modules.workflows.application.target_context_artifact_opening_ports import (
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningError,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningUncertainError,
    WorkflowPhysicalTransportTargetContextArtifactOpener,
    WorkflowTargetContextArtifactOpeningClaimRequest,
    WorkflowTargetContextArtifactOpeningClaimStatus,
    WorkflowTargetContextArtifactOpeningRepository,
    WorkflowTargetContextArtifactOpeningResultRequest,
    WorkflowTargetContextArtifactOpeningResultStatus,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportCredentialMaterializationResult,
    WorkflowEventPhysicalTransportCredentialMaterializationResultState,
    WorkflowEventPhysicalTransportEndpointMaterializationResult,
    WorkflowEventPhysicalTransportEndpointMaterializationResultState,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseState,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningAuthority,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningPolicy,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState,
    WorkflowEventPhysicalTransportTargetContextBinding,
    WorkflowEventPhysicalTransportTargetContextBindingState,
    WorkflowProtectedArtifactKind,
    WorkflowProtectedArtifactStatusAttestation,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_target_context_artifact_opening_policy,
)

WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ARTIFACT_OPENING_PRODUCER = (
    "project-atlas-workflow-protected-target-context-artifact-opener"
)


@dataclass(frozen=True, slots=True)
class _ResolvedOpeningEvidence:
    lease: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease
    binding: WorkflowEventPhysicalTransportTargetContextBinding
    endpoint: WorkflowEventPhysicalTransportEndpointMaterializationResult
    credential: WorkflowEventPhysicalTransportCredentialMaterializationResult
    endpoint_attestation: WorkflowProtectedArtifactStatusAttestation
    credential_attestation: WorkflowProtectedArtifactStatusAttestation


class WorkflowEventPhysicalTransportTargetContextArtifactOpeningService:
    """Consumes one lease before opening one exact protected artifact pair."""

    def __init__(
        self,
        *,
        repository: WorkflowTargetContextArtifactOpeningRepository,
        endpoint_status_attestor: WorkflowProtectedEndpointStatusAttestor,
        credential_status_attestor: WorkflowProtectedCredentialStatusAttestor,
        status_signature_verifier: WorkflowProtectedArtifactStatusSignatureVerifier,
        opener: WorkflowPhysicalTransportTargetContextArtifactOpener,
        audit_sink: AuditSink,
        policy: WorkflowEventPhysicalTransportTargetContextArtifactOpeningPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._endpoint_status_attestor = endpoint_status_attestor
        self._credential_status_attestor = credential_status_attestor
        self._status_signature_verifier = status_signature_verifier
        self._opener = opener
        self._audit_sink = audit_sink
        self._policy = policy or (
            code_owned_workflow_event_physical_transport_target_context_artifact_opening_policy()
        )

    @property
    def repository(self) -> WorkflowTargetContextArtifactOpeningRepository:
        return self._repository

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def policy(self) -> WorkflowEventPhysicalTransportTargetContextArtifactOpeningPolicy:
        return self._policy

    async def open_artifacts(
        self,
        *,
        authorization_lease_id: str,
        authorization_lease_digest: str,
        policy_id: str,
        policy_version: str,
        irreversible_consumption_acknowledged: bool,
        uncertain_outcome_requires_new_authorization_acknowledged: bool,
        idempotency_key: str,
        context: WorkflowPhysicalTransportTargetContextAccessorContext,
    ) -> WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult:
        self._require_request(
            authorization_lease_id=authorization_lease_id,
            authorization_lease_digest=authorization_lease_digest,
            policy_id=policy_id,
            policy_version=policy_version,
            irreversible_consumption_acknowledged=irreversible_consumption_acknowledged,
            uncertain_outcome_requires_new_authorization_acknowledged=(
                uncertain_outcome_requires_new_authorization_acknowledged
            ),
            idempotency_key=idempotency_key,
            context=context,
        )
        if not self._repository.durable:
            self._raise("target_context_artifact_opening_durable_repository_required")
        if (
            not self._opener.available
            or self._opener.opener_contract_id != self._policy.required_opener_contract_id
        ):
            self._raise("target_context_artifact_opening_trusted_opener_unavailable")

        evidence = await self._load_and_attest(
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
                "policy_digest": self._policy.canonical_digest,
                "policy_id": policy_id,
                "policy_version": policy_version,
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
        opening_id = f"workflow-target-context-artifact-opening.{seed[:24]}"
        await self._audit(
            context,
            event_kind="requested",
            outcome="requested",
            result_code="target_context_artifact_opening_requested",
            authorization_lease_id=authorization_lease_id,
            opening_id=opening_id,
            idempotency_key=idempotency_key,
        )

        async def required_precommit_audit() -> None:
            await self._audit(
                context,
                event_kind="authorized",
                outcome="authorized",
                result_code="target_context_artifact_opening_lease_consumption_authorized",
                authorization_lease_id=authorization_lease_id,
                opening_id=opening_id,
                idempotency_key=idempotency_key,
            )

        request = WorkflowTargetContextArtifactOpeningClaimRequest(
            claim_id=f"workflow-target-context-access-consumption-claim.{seed[:24]}",
            attempt_id=f"workflow-target-context-artifact-opening-attempt.{seed[:24]}",
            opening_id=opening_id,
            authorization_lease_id=authorization_lease_id,
            authorization_lease_digest=authorization_lease_digest,
            expected_target_context_binding_id=evidence.binding.binding_id,
            expected_target_context_binding_digest=evidence.binding.canonical_digest,
            expected_target_context_commitment=evidence.binding.target_context_commitment,
            expected_endpoint_materialization_id=evidence.endpoint.materialization_id,
            expected_endpoint_materialization_digest=evidence.endpoint.canonical_digest,
            expected_endpoint_protected_artifact_id=cast(
                str, evidence.endpoint.protected_artifact_id
            ),
            expected_endpoint_protected_artifact_digest=cast(
                str, evidence.endpoint.protected_artifact_digest
            ),
            expected_endpoint_usable_until=cast(datetime, evidence.endpoint.usable_until),
            expected_credential_materialization_id=evidence.credential.materialization_id,
            expected_credential_materialization_digest=evidence.credential.canonical_digest,
            expected_credential_protected_artifact_id=cast(
                str, evidence.credential.protected_artifact_id
            ),
            expected_credential_protected_artifact_digest=cast(
                str, evidence.credential.protected_artifact_digest
            ),
            expected_credential_usable_until=cast(datetime, evidence.credential.usable_until),
            endpoint_status_attestation=evidence.endpoint_attestation,
            credential_status_attestation=evidence.credential_attestation,
            expected_request_nonce_digest=evidence.endpoint_attestation.request_nonce_digest,
            offline_signature_verifier=self._status_signature_verifier,
            expected_policy_id=self._policy.policy_id,
            expected_policy_version=self._policy.policy_version,
            expected_policy_digest=self._policy.canonical_digest,
            expected_opener_contract_id=self._policy.required_opener_contract_id,
            expected_opener_attestor_id=self._policy.required_opener_attestor_id,
            scope=context.scope,
            accessor_subject_id=context.subject_id,
            idempotency_key=idempotency_key,
            idempotency_digest=idempotency_digest,
            request_fingerprint=fingerprint,
            irreversible_consumption_acknowledged=True,
            uncertain_outcome_requires_new_authorization_acknowledged=True,
            required_precommit_audit=required_precommit_audit,
        )
        claimed = await self._repository.claim_target_context_artifact_opening(request)
        if claimed.status is WorkflowTargetContextArtifactOpeningClaimStatus.REPLAY_COMPLETED:
            if claimed.result is None:
                self._uncertain("target_context_artifact_opening_replay_result_missing")
            return claimed.result
        if claimed.status is WorkflowTargetContextArtifactOpeningClaimStatus.CLAIM_ONLY_UNCERTAIN:
            self._uncertain("target_context_artifact_opening_outcome_uncertain")
        if claimed.status is not WorkflowTargetContextArtifactOpeningClaimStatus.CLAIMED:
            self._raise(f"target_context_artifact_opening_{claimed.status.value}")
        if claimed.claim is None or claimed.attempt is None or claimed.result is not None:
            self._uncertain("target_context_artifact_opening_claim_commit_uncertain")

        instruction = self._build_instruction(evidence=evidence, attempt=claimed.attempt)
        receipt: WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt | None = None
        try:
            receipt = await self._opener.open_paired_artifacts(instruction)
            self._verify_receipt(receipt, instruction)
            result = self._build_result(
                evidence=evidence,
                claim_digest=claimed.claim.canonical_digest,
                attempt_digest=claimed.attempt.canonical_digest,
                receipt=receipt,
            )
            await self._audit(
                context,
                event_kind=(
                    "completed"
                    if result.state
                    is (
                        WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState
                    ).OPENED_PROTECTED
                    else "failed"
                ),
                outcome=result.state.value,
                result_code=f"target_context_artifact_opening_{result.state.value}",
                authorization_lease_id=authorization_lease_id,
                opening_id=result.opening_id,
                idempotency_key=idempotency_key,
            )
            written = await self._repository.record_target_context_artifact_opening_result(
                WorkflowTargetContextArtifactOpeningResultRequest(
                    result=result,
                    expected_claim_digest=claimed.claim.canonical_digest,
                    expected_attempt_digest=claimed.attempt.canonical_digest,
                    expected_lease_valid_until=evidence.lease.valid_until,
                    expected_target_context_binding_digest=evidence.binding.canonical_digest,
                    expected_endpoint_materialization_digest=evidence.endpoint.canonical_digest,
                    expected_credential_materialization_digest=evidence.credential.canonical_digest,
                )
            )
        except WorkflowEventPhysicalTransportTargetContextArtifactOpeningUncertainError:
            if receipt is not None and receipt.sealed_capsule_id is not None:
                await self._destroy_capsule(receipt)
            raise
        except Exception as exc:
            if receipt is not None and receipt.sealed_capsule_id is not None:
                await self._destroy_capsule(receipt)
            raise WorkflowEventPhysicalTransportTargetContextArtifactOpeningUncertainError(
                "target_context_artifact_opening_outcome_uncertain"
            ) from exc
        if (
            written.status
            not in (
                WorkflowTargetContextArtifactOpeningResultStatus.RECORDED,
                WorkflowTargetContextArtifactOpeningResultStatus.REPLAY,
            )
            or written.result is None
        ):
            if receipt is not None and receipt.sealed_capsule_id is not None:
                await self._destroy_capsule(receipt)
            self._uncertain("target_context_artifact_opening_result_persistence_uncertain")
        return written.result

    async def list_results(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult, ...]:
        if not self._repository.durable:
            self._raise("target_context_artifact_opening_durable_repository_required")
        return await self._repository.list_target_context_artifact_opening_results(
            scope=scope, limit=limit
        )

    def _require_request(self, **values: object) -> None:
        context = values["context"]
        assert isinstance(context, WorkflowPhysicalTransportTargetContextAccessorContext)
        identifiers = (
            values["authorization_lease_id"],
            values["policy_id"],
            values["policy_version"],
            values["idempotency_key"],
        )
        if (
            context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.subject_id != WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_SUBJECT
            or context.credential_audience
            != WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE
            or any(
                not isinstance(value, str)
                or not value
                or value != value.strip()
                or len(value) > 240
                for value in identifiers
            )
            or not isinstance(values["authorization_lease_digest"], str)
            or len(values["authorization_lease_digest"]) != 64
            or any(
                character not in "0123456789abcdef"
                for character in values["authorization_lease_digest"]
            )
            or values["policy_id"] != self._policy.policy_id
            or values["policy_version"] != self._policy.policy_version
            or values["irreversible_consumption_acknowledged"] is not True
            or values["uncertain_outcome_requires_new_authorization_acknowledged"] is not True
            or not 8 <= len(cast(str, values["idempotency_key"])) <= 128
        ):
            self._raise("target_context_artifact_opening_request_invalid")

    async def _load_and_attest(
        self,
        *,
        authorization_lease_id: str,
        authorization_lease_digest: str,
        context: WorkflowPhysicalTransportTargetContextAccessorContext,
    ) -> _ResolvedOpeningEvidence:
        lease = await self._repository.get_target_context_access_authorization_lease_by_id(
            authorization_lease_id=authorization_lease_id
        )
        if lease is None:
            self._raise("target_context_artifact_opening_lease_not_found")
        binding = await self._repository.get_target_context_binding_by_id(
            binding_id=lease.target_context_binding_id
        )
        if binding is None:
            self._raise("target_context_artifact_opening_binding_not_found")
        endpoint = await self._repository.get_endpoint_materialization_result_by_id(
            materialization_id=binding.endpoint_materialization_id
        )
        credential = await self._repository.get_credential_materialization_result_by_id(
            materialization_id=binding.credential_materialization_id
        )
        if endpoint is None or credential is None:
            self._raise("target_context_artifact_opening_materialization_not_found")
        self._validate_base_evidence(
            lease=lease,
            binding=binding,
            endpoint=endpoint,
            credential=credential,
            authorization_lease_digest=authorization_lease_digest,
            context=context,
        )
        nonce_digest = canonical_digest(
            {
                "authorization_lease_digest": authorization_lease_digest,
                "nonce": uuid4().hex,
            }
        )
        endpoint_request = self._attestation_request(
            kind=WorkflowProtectedArtifactKind.ENDPOINT,
            materialization_id=endpoint.materialization_id,
            materialization_digest=endpoint.canonical_digest,
            binding=binding,
            nonce_digest=nonce_digest,
            context=context,
        )
        credential_request = self._attestation_request(
            kind=WorkflowProtectedArtifactKind.CREDENTIAL,
            materialization_id=credential.materialization_id,
            materialization_digest=credential.canonical_digest,
            binding=binding,
            nonce_digest=nonce_digest,
            context=context,
        )
        endpoint_attestation = await self._endpoint_status_attestor.attest_endpoint_artifact_status(
            endpoint_request
        )
        credential_attestation = (
            await self._credential_status_attestor.attest_credential_artifact_status(
                credential_request
            )
        )
        now = await self._repository.get_authoritative_time()
        self._validate_status_attestation(
            endpoint_attestation,
            request=endpoint_request,
            evaluated_at=now,
            required_attestor_id="attestor.workflow-protected-endpoint-store-status",
        )
        self._validate_status_attestation(
            credential_attestation,
            request=credential_request,
            evaluated_at=now,
            required_attestor_id="attestor.workflow-protected-credential-store-status",
        )
        if (
            self._status_signature_verifier.verify_status_attestation(endpoint_attestation)
            is not True
            or self._status_signature_verifier.verify_status_attestation(credential_attestation)
            is not True
            or not lease.issued_at <= now < lease.valid_until
            or now
            >= min(
                binding.joint_usable_until,
                cast(datetime, endpoint.usable_until),
                cast(datetime, credential.usable_until),
                endpoint_attestation.valid_until,
                credential_attestation.valid_until,
            )
        ):
            self._raise("target_context_artifact_opening_evidence_conflict")
        return _ResolvedOpeningEvidence(
            lease,
            binding,
            endpoint,
            credential,
            endpoint_attestation,
            credential_attestation,
        )

    @staticmethod
    def _validate_base_evidence(
        *,
        lease: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease,
        binding: WorkflowEventPhysicalTransportTargetContextBinding,
        endpoint: WorkflowEventPhysicalTransportEndpointMaterializationResult,
        credential: WorkflowEventPhysicalTransportCredentialMaterializationResult,
        authorization_lease_digest: str,
        context: WorkflowPhysicalTransportTargetContextAccessorContext,
    ) -> None:
        if (
            lease.canonical_digest != authorization_lease_digest
            or lease.scope != context.scope
            or lease.accessor_subject_id != context.subject_id
            or lease.state
            is not (
                WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseState
            ).AUTHORIZED_UNCONSUMED
            or lease.authority.protected_artifact_access_authorized is not True
            or any(
                value is not False
                for name, value in lease.authority.canonical_value().items()
                if name != "protected_artifact_access_authorized"
            )
            or binding.binding_id != lease.target_context_binding_id
            or binding.canonical_digest != lease.target_context_binding_digest
            or binding.target_context_commitment != lease.target_context_commitment
            or binding.scope != context.scope
            or binding.state is not WorkflowEventPhysicalTransportTargetContextBindingState.BOUND
            or any(binding.authority.canonical_value().values())
            or endpoint.materialization_id != binding.endpoint_materialization_id
            or endpoint.canonical_digest != binding.endpoint_materialization_digest
            or endpoint.state
            is not (
                WorkflowEventPhysicalTransportEndpointMaterializationResultState
            ).MATERIALIZED_PROTECTED
            or endpoint.protected_artifact_id is None
            or endpoint.protected_artifact_digest is None
            or endpoint.usable_until is None
            or endpoint.protected_artifact_revoked
            or credential.materialization_id != binding.credential_materialization_id
            or credential.canonical_digest != binding.credential_materialization_digest
            or credential.state
            is not (
                WorkflowEventPhysicalTransportCredentialMaterializationResultState
            ).MATERIALIZED_PROTECTED
            or credential.protected_artifact_id is None
            or credential.protected_artifact_digest is None
            or credential.usable_until is None
            or credential.protected_artifact_revoked
        ):
            raise WorkflowEventPhysicalTransportTargetContextArtifactOpeningError(
                "target_context_artifact_opening_evidence_conflict"
            )

    @staticmethod
    def _attestation_request(
        *,
        kind: WorkflowProtectedArtifactKind,
        materialization_id: str,
        materialization_digest: str,
        binding: WorkflowEventPhysicalTransportTargetContextBinding,
        nonce_digest: str,
        context: WorkflowPhysicalTransportTargetContextAccessorContext,
    ) -> WorkflowProtectedArtifactStatusAttestationRequest:
        return WorkflowProtectedArtifactStatusAttestationRequest(
            artifact_kind=kind,
            materialization_id=materialization_id,
            materialization_digest=materialization_digest,
            target_context_binding_id=binding.binding_id,
            target_context_binding_digest=binding.canonical_digest,
            target_context_commitment=binding.target_context_commitment,
            scope=context.scope,
            accessor_subject_id=context.subject_id,
            request_nonce_digest=nonce_digest,
            requested_at=context.requested_at,
        )

    @staticmethod
    def _validate_status_attestation(
        attestation: WorkflowProtectedArtifactStatusAttestation,
        *,
        request: WorkflowProtectedArtifactStatusAttestationRequest,
        evaluated_at: datetime,
        required_attestor_id: str,
    ) -> None:
        if (
            attestation.artifact_kind is not request.artifact_kind
            or attestation.materialization_id != request.materialization_id
            or attestation.materialization_digest != request.materialization_digest
            or attestation.target_context_binding_id != request.target_context_binding_id
            or attestation.target_context_binding_digest != request.target_context_binding_digest
            or attestation.target_context_commitment != request.target_context_commitment
            or attestation.request_nonce_digest != request.request_nonce_digest
            or attestation.protected_store_attestor_id != required_attestor_id
            or attestation.protected_store_attestor_version != "1.0"
            or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
            or attestation.observed_at > evaluated_at
            or attestation.valid_until <= evaluated_at
            or not attestation.usable
            or attestation.revoked
            or attestation.destroyed
        ):
            raise WorkflowEventPhysicalTransportTargetContextArtifactOpeningError(
                "target_context_artifact_opening_evidence_conflict"
            )

    def _build_instruction(
        self,
        *,
        evidence: _ResolvedOpeningEvidence,
        attempt: Any,
    ) -> WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction:
        values: dict[str, object] = {
            "opening_id": attempt.opening_id,
            "attempt_id": attempt.attempt_id,
            "consumption_claim_id": attempt.consumption_claim_id,
            "authorization_lease_id": evidence.lease.authorization_lease_id,
            "authorization_lease_digest": evidence.lease.canonical_digest,
            "target_context_binding_id": evidence.binding.binding_id,
            "target_context_binding_digest": evidence.binding.canonical_digest,
            "target_context_commitment": evidence.binding.target_context_commitment,
            "endpoint_materialization_id": evidence.endpoint.materialization_id,
            "endpoint_materialization_digest": evidence.endpoint.canonical_digest,
            "endpoint_protected_artifact_id": evidence.endpoint.protected_artifact_id,
            "endpoint_protected_artifact_digest": evidence.endpoint.protected_artifact_digest,
            "endpoint_status_attestation_digest": (evidence.endpoint_attestation.canonical_digest),
            "credential_materialization_id": evidence.credential.materialization_id,
            "credential_materialization_digest": evidence.credential.canonical_digest,
            "credential_protected_artifact_id": evidence.credential.protected_artifact_id,
            "credential_protected_artifact_digest": (evidence.credential.protected_artifact_digest),
            "credential_status_attestation_digest": (
                evidence.credential_attestation.canonical_digest
            ),
            "scope": evidence.binding.scope,
            "accessor_subject_id": evidence.lease.accessor_subject_id,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "opener_contract_id": self._policy.required_opener_contract_id,
            "opener_attestor_id": self._policy.required_opener_attestor_id,
            "capsule_schema_id": self._policy.capsule_schema_id,
            "capsule_schema_version": self._policy.capsule_schema_version,
            "started_at": attempt.started_at,
            "lease_valid_until": evidence.lease.valid_until,
            "joint_usable_until": evidence.binding.joint_usable_until,
            "evidence_valid_until": min(
                cast(datetime, evidence.endpoint.usable_until),
                cast(datetime, evidence.credential.usable_until),
                evidence.endpoint_attestation.valid_until,
                evidence.credential_attestation.valid_until,
            ),
        }
        return WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction(
            **cast(Any, values), canonical_digest=canonical_digest(self._payload(values))
        )

    def _verify_receipt(
        self,
        receipt: WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt,
        instruction: WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction,
    ) -> None:
        if (
            receipt.opening_id != instruction.opening_id
            or receipt.attempt_id != instruction.attempt_id
            or receipt.consumption_claim_id != instruction.consumption_claim_id
            or receipt.instruction_digest != instruction.canonical_digest
            or receipt.opener_contract_id != self._policy.required_opener_contract_id
            or receipt.attested_by != self._policy.required_opener_attestor_id
            or receipt.accessor_subject_id != instruction.accessor_subject_id
            or receipt.capsule_schema_id != self._policy.capsule_schema_id
            or receipt.capsule_schema_version != self._policy.capsule_schema_version
            or receipt.canonical_digest != canonical_digest(receipt.digest_payload())
            or not receipt.protected_sources_closed
            or not receipt.cleanup_confirmed
            or receipt.raw_endpoint_returned
            or receipt.raw_credential_returned
            or receipt.network_activity_performed
            or receipt.delivery_performed
            or receipt.runtime_use_performed
            or receipt.completed_at < instruction.started_at
            or self._opener.verify_receipt(receipt) is not True
        ):
            self._uncertain("target_context_artifact_opening_receipt_invalid")
        if (
            receipt.state
            is (
                WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState
            ).OPENED_PROTECTED
        ):
            maximum_until = min(
                instruction.lease_valid_until,
                instruction.joint_usable_until,
                instruction.evidence_valid_until,
                receipt.completed_at
                + timedelta(seconds=self._policy.maximum_capsule_lifetime_seconds),
            )
            if (
                receipt.usable_until is None
                or receipt.usable_until > maximum_until
                or not receipt.endpoint_opened
                or not receipt.credential_opened
                or not receipt.pair_commitment_verified
            ):
                self._uncertain("target_context_artifact_opening_receipt_invalid")

    def _build_result(
        self,
        *,
        evidence: _ResolvedOpeningEvidence,
        claim_digest: str,
        attempt_digest: str,
        receipt: WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt,
    ) -> WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult:
        authority = WorkflowEventPhysicalTransportTargetContextArtifactOpeningAuthority()
        values: dict[str, object] = {
            "opening_id": receipt.opening_id,
            "attempt_id": receipt.attempt_id,
            "attempt_digest": attempt_digest,
            "consumption_claim_id": receipt.consumption_claim_id,
            "consumption_claim_digest": claim_digest,
            "authorization_lease_id": evidence.lease.authorization_lease_id,
            "authorization_lease_digest": evidence.lease.canonical_digest,
            "target_context_binding_id": evidence.binding.binding_id,
            "target_context_binding_digest": evidence.binding.canonical_digest,
            "target_context_commitment": evidence.binding.target_context_commitment,
            "scope": evidence.binding.scope,
            "accessor_subject_id": evidence.lease.accessor_subject_id,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "opener_id": receipt.opener_id,
            "opener_version": receipt.opener_version,
            "opening_receipt_digest": receipt.canonical_digest,
            "state": receipt.state,
            "failure_class": receipt.failure_class,
            "sealed_capsule_id": receipt.sealed_capsule_id,
            "sealed_capsule_digest": receipt.sealed_capsule_digest,
            "capsule_is_bearer_capability": receipt.capsule_is_bearer_capability,
            "capsule_schema_id": receipt.capsule_schema_id,
            "capsule_schema_version": receipt.capsule_schema_version,
            "completed_at": receipt.completed_at,
            "usable_until": receipt.usable_until,
            "protected_sources_closed": receipt.protected_sources_closed,
            "cleanup_confirmed": receipt.cleanup_confirmed,
            "authority": authority,
        }
        return WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult(
            **cast(Any, values), canonical_digest=canonical_digest(self._payload(values))
        )

    async def _destroy_capsule(
        self, receipt: WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt
    ) -> None:
        try:
            destroyed = await self._opener.destroy_capsule(receipt)
        except Exception as exc:
            raise WorkflowEventPhysicalTransportTargetContextArtifactOpeningUncertainError(
                "target_context_artifact_opening_capsule_cleanup_uncertain"
            ) from exc
        if destroyed is not True:
            self._uncertain("target_context_artifact_opening_capsule_cleanup_uncertain")

    async def _audit(
        self,
        context: WorkflowPhysicalTransportTargetContextAccessorContext,
        *,
        event_kind: str,
        outcome: str,
        result_code: str,
        authorization_lease_id: str,
        opening_id: str,
        idempotency_key: str,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=(
                    "atlas.workflow.physical-transport-target-context-artifact-opening."
                    f"{event_kind}"
                ),
                schema_version="1.0",
                producer=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ARTIFACT_OPENING_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id=(
                    "workflow.physical-transport-target-context-artifact-openings.create"
                ),
                resource_type="resource.workflow-target-context-artifact-opening",
                scope_reference="/".join(context.scope.canonical_value().values()),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    ("authorization_lease_id", authorization_lease_id),
                    ("opening_id", opening_id),
                    ("credential_delivery_authority", "false"),
                    ("network_access_authority", "false"),
                    ("runtime_use_authority", "false"),
                    ("publication_authority", "false"),
                    ("dispatch_authority", "false"),
                    ("execution_authority", "false"),
                    ("infrastructure_mutation_authority", "false"),
                ),
            )
        )

    @staticmethod
    def _payload(values: dict[str, object]) -> dict[str, object]:
        return {
            name: (
                value.isoformat()
                if isinstance(value, datetime)
                else value.value
                if hasattr(value, "value")
                else value.canonical_value()
                if hasattr(value, "canonical_value")
                else value
            )
            for name, value in values.items()
        }

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowEventPhysicalTransportTargetContextArtifactOpeningError(code)

    @staticmethod
    def _uncertain(code: str) -> NoReturn:
        raise WorkflowEventPhysicalTransportTargetContextArtifactOpeningUncertainError(code)


__all__ = [
    "WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ARTIFACT_OPENING_PRODUCER",
    "WorkflowEventPhysicalTransportTargetContextArtifactOpeningService",
]

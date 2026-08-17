from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.protected_runtime_context_use_ports import (
    WorkflowProtectedRuntimeContextUseReceiptSignatureVerifier,
)
from atlas.modules.workflows.application.protected_runtime_start_authorization_ports import (
    WorkflowProtectedRuntimeStartAuthorizationError,
    WorkflowProtectedRuntimeStartAuthorizationLeaseRequest,
    WorkflowProtectedRuntimeStartAuthorizationLeaseStatus,
    WorkflowProtectedRuntimeStartAuthorizationPreflightRequest,
    WorkflowProtectedRuntimeStartAuthorizationPreflightStatus,
    WorkflowProtectedRuntimeStartAuthorizationPresentation,
    WorkflowProtectedRuntimeStartAuthorizationRepository,
    WorkflowProtectedRuntimeStartAuthorizationSource,
    WorkflowProtectedRuntimeStartLifecycleAttestation,
    WorkflowProtectedRuntimeStartLifecycleAttestationRequest,
    WorkflowProtectedRuntimeStartLifecycleAttestor,
    WorkflowProtectedRuntimeStartLifecycleSignatureVerifier,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_context_use_domain import (
    WorkflowProtectedRuntimeContextUseResultState,
)
from atlas.modules.workflows.domain.protected_runtime_start_authorization_domain import (
    WorkflowProtectedRuntimeStartAuthorizationAuthority,
    WorkflowProtectedRuntimeStartAuthorizationClaim,
    WorkflowProtectedRuntimeStartAuthorizationLease,
    WorkflowProtectedRuntimeStartAuthorizationLeaseState,
    WorkflowProtectedRuntimeStartAuthorizationPolicy,
    code_owned_workflow_protected_runtime_start_authorization_policy,
)

WORKFLOW_PROTECTED_RUNTIME_START_AUTHORIZATION_PRODUCER = (
    "project-atlas-workflow-protected-runtime-start-authorizer"
)


class WorkflowProtectedRuntimeStartAuthorizationService:
    """Issues a future-request lease without starting or executing any runtime."""

    def __init__(
        self,
        *,
        authorization_repository: WorkflowProtectedRuntimeStartAuthorizationRepository,
        lifecycle_attestor: WorkflowProtectedRuntimeStartLifecycleAttestor,
        lifecycle_signature_verifier: WorkflowProtectedRuntimeStartLifecycleSignatureVerifier,
        use_receipt_signature_verifier: WorkflowProtectedRuntimeContextUseReceiptSignatureVerifier,
        audit_sink: AuditSink,
        policy: WorkflowProtectedRuntimeStartAuthorizationPolicy | None = None,
    ) -> None:
        self._repository = authorization_repository
        self._lifecycle_attestor = lifecycle_attestor
        self._lifecycle_signature_verifier = lifecycle_signature_verifier
        self._use_receipt_signature_verifier = use_receipt_signature_verifier
        self._audit_sink = audit_sink
        self._policy = policy or code_owned_workflow_protected_runtime_start_authorization_policy()

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def repository(self) -> WorkflowProtectedRuntimeStartAuthorizationRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowProtectedRuntimeStartAuthorizationPolicy:
        return self._policy

    async def authorize(
        self,
        *,
        use_result_id: str,
        use_result_digest: str,
        policy_id: str,
        policy_version: str,
        idempotency_key: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> WorkflowProtectedRuntimeStartAuthorizationLease:
        self._require_workload(context)
        if not self._repository.durable:
            self._raise("workflow_protected_runtime_start_durable_repository_required")
        result_id = self._identifier(use_result_id, "use_result_id")
        result_digest = self._digest(use_result_digest, "use_result_digest")
        normalized_key = self._idempotency_key(idempotency_key)
        if policy_id != self._policy.policy_id or policy_version != self._policy.policy_version:
            self._raise("workflow_protected_runtime_start_policy_conflict")
        idempotency_digest = canonical_digest(
            {
                "idempotency_key": normalized_key,
                "scope": context.scope.canonical_value(),
                "subject_id": context.subject_id,
            }
        )
        fingerprint = canonical_digest(
            {
                "policy_digest": self._policy.canonical_digest,
                "scope": context.scope.canonical_value(),
                "subject_id": context.subject_id,
                "use_result_digest": result_digest,
                "use_result_id": result_id,
            }
        )
        preflight_request = WorkflowProtectedRuntimeStartAuthorizationPreflightRequest(
            use_result_id=result_id,
            use_result_digest=result_digest,
            scope=context.scope,
            consumer_subject_id=context.subject_id,
            consumer_audience=context.credential_audience,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.policy_version,
            policy_digest=self._policy.canonical_digest,
            idempotency_key=normalized_key,
            idempotency_digest=idempotency_digest,
            request_fingerprint=fingerprint,
            offline_signature_verifier=self._lifecycle_signature_verifier,
            offline_use_receipt_signature_verifier=self._use_receipt_signature_verifier,
        )
        try:
            preflight = await self._repository.preflight_protected_runtime_start_authorization(
                preflight_request
            )
        except WorkflowProtectedRuntimeStartAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_start_repository_unavailable")
        statuses = WorkflowProtectedRuntimeStartAuthorizationPreflightStatus
        if preflight.status is statuses.REPLAY:
            if preflight.lease is None or preflight.evaluated_at is None:
                self._raise("workflow_protected_runtime_start_repository_contract_violation")
            self._validate_historical_lease(preflight.lease, scope=context.scope)
            await self._postcommit_audit(
                context,
                result_code="workflow_protected_runtime_start_authorization_replayed",
                lease=preflight.lease,
            )
            return preflight.lease
        if preflight.status is not statuses.NONE:
            self._raise_preflight_status(preflight.status)
        if preflight.lease is not None or preflight.evaluated_at is None:
            self._raise("workflow_protected_runtime_start_repository_contract_violation")
        if not self._lifecycle_attestor.available:
            self._raise("workflow_protected_runtime_start_trusted_attestor_unavailable")
        try:
            source = await self._repository.get_protected_runtime_start_authorization_source(
                use_result_id=result_id
            )
        except WorkflowProtectedRuntimeStartAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_start_repository_unavailable")
        if source is None:
            self._raise("workflow_protected_runtime_start_evidence_conflict")
        self._validate_source(source, expected_digest=result_digest, scope=context.scope)
        nonce_digest = canonical_digest({"nonce": uuid4().hex, "request_fingerprint": fingerprint})
        attestation_request = self._attestation_request(
            source,
            nonce_digest=nonce_digest,
            requested_at=preflight.evaluated_at,
        )
        try:
            attestation = await self._lifecycle_attestor.attest_runtime_start_lifecycle(
                attestation_request
            )
        except WorkflowProtectedRuntimeStartAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_start_evidence_conflict")
        try:
            authoritative_now = await self._repository.get_authoritative_time()
        except Exception:
            self._raise("workflow_protected_runtime_start_repository_unavailable")
        self._validate_attestation(
            attestation,
            request=attestation_request,
            evaluated_at=authoritative_now,
        )
        candidate_claim, candidate = self._build_candidates(
            source=source,
            attestation=attestation,
            issued_at=authoritative_now,
            idempotency_digest=idempotency_digest,
            request_fingerprint=fingerprint,
        )
        request = WorkflowProtectedRuntimeStartAuthorizationLeaseRequest(
            source=source,
            lifecycle_attestation=attestation,
            expected_request_nonce_digest=nonce_digest,
            offline_signature_verifier=self._lifecycle_signature_verifier,
            offline_use_receipt_signature_verifier=self._use_receipt_signature_verifier,
            expected_policy_digest=self._policy.canonical_digest,
            expected_validity_window_seconds=self._policy.maximum_lifetime_seconds,
            scope=context.scope,
            consumer_subject_id=context.subject_id,
            consumer_audience=context.credential_audience,
            pre_attestation_observed_at=preflight.evaluated_at,
            requested_at=authoritative_now,
            candidate_claim=candidate_claim,
            candidate=candidate,
            idempotency_key=normalized_key,
            idempotency_digest=idempotency_digest,
            request_fingerprint=fingerprint,
        )
        try:
            outcome = await self._repository.authorize_protected_runtime_start(request)
        except WorkflowProtectedRuntimeStartAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_start_repository_unavailable")
        lease_statuses = WorkflowProtectedRuntimeStartAuthorizationLeaseStatus
        if outcome.status not in (lease_statuses.AUTHORIZED, lease_statuses.REPLAY):
            self._raise_authorization_status(outcome.status)
        if outcome.lease is None or outcome.evaluated_at is None:
            self._raise("workflow_protected_runtime_start_repository_contract_violation")
        self._validate_historical_lease(outcome.lease, scope=context.scope)
        await self._postcommit_audit(
            context,
            result_code=(
                "workflow_protected_runtime_start_authorization_created"
                if outcome.status is lease_statuses.AUTHORIZED
                else "workflow_protected_runtime_start_authorization_replayed"
            ),
            lease=outcome.lease,
        )
        return outcome.lease

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeStartAuthorizationPresentation, ...]:
        if not self._repository.durable:
            self._raise("workflow_protected_runtime_start_durable_repository_required")
        try:
            return await self._repository.list_protected_runtime_start_authorization_presentations(
                scope=scope,
                limit=max(1, min(limit, 256)),
            )
        except WorkflowProtectedRuntimeStartAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_start_repository_unavailable")

    async def get_presentation(
        self, *, scope: WorkflowScope, authorization_lease_id: str
    ) -> WorkflowProtectedRuntimeStartAuthorizationPresentation:
        lease_id = self._identifier(authorization_lease_id, "authorization_lease_id")
        if not self._repository.durable:
            self._raise("workflow_protected_runtime_start_durable_repository_required")
        try:
            presentations = await (
                self._repository.list_protected_runtime_start_authorization_presentations(
                    scope=scope,
                    authorization_lease_ids=(lease_id,),
                    limit=1,
                )
            )
        except WorkflowProtectedRuntimeStartAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_start_repository_unavailable")
        if len(presentations) != 1 or presentations[0].lease.authorization_lease_id != lease_id:
            self._raise("workflow_protected_runtime_start_authorization_not_found")
        return presentations[0]

    def _validate_source(
        self,
        source: WorkflowProtectedRuntimeStartAuthorizationSource,
        *,
        expected_digest: str,
        scope: object,
    ) -> None:
        result = source.result
        attempt = source.attempt
        claim = source.use_claim
        receipt = source.use_receipt
        if (
            result.canonical_digest != expected_digest
            or result.canonical_digest != canonical_digest(result.digest_payload())
            or attempt.canonical_digest != canonical_digest(attempt.digest_payload())
            or claim.canonical_digest != canonical_digest(claim.digest_payload())
            or receipt.canonical_digest != canonical_digest(receipt.digest_payload())
            or result.state
            is not (
                WorkflowProtectedRuntimeContextUseResultState.CONTEXT_USED_ONCE_IN_PROTECTED_BOUNDARY
            )
            or result.outcome_known is not True
            or result.context_adopted is not True
            or result.protected_runtime_context_use_performed is not True
            or result.context_terminal_non_reusable is not True
            or result.transient_material_zeroized is not True
            or result.completed_at is None
            or result.runtime_slot_post_generation is None
            or result.use_count_post != 1
            or result.executor_receipt_digest != receipt.canonical_digest
            or result.attempt_id != attempt.attempt_id
            or result.attempt_digest != attempt.canonical_digest
            or result.claim_id != claim.claim_id
            or result.claim_digest != claim.canonical_digest
            or result.use_id != attempt.use_id
            or result.use_id != claim.use_id
            or attempt.claim_id != claim.claim_id
            or attempt.claim_digest != claim.canonical_digest
            or result.authorization_consumption_result_id
            != attempt.authorization_consumption_result_id
            or result.authorization_consumption_result_id
            != claim.authorization_consumption_result_id
            or result.authorization_consumption_result_digest
            != attempt.authorization_consumption_result_digest
            or result.authorization_consumption_result_digest
            != claim.authorization_consumption_result_digest
            or result.runtime_slot_post_generation != attempt.expected_runtime_slot_post_generation
            or result.runtime_slot_commitment != attempt.runtime_slot_commitment
            or result.destination_deployment_id != attempt.destination_deployment_id
            or result.destination_generation != attempt.destination_generation
            or result.destination_fencing_token_digest != attempt.destination_fencing_token_digest
            or result.use_profile_id != self._policy_source_value("use_profile_id")
            or result.use_profile_version != self._policy_source_value("use_profile_version")
            or result.use_profile_digest != self._policy_source_value("use_profile_digest")
            or attempt.scope != scope
            or attempt.consumer_subject_id != self._policy.consumer_subject_id
            or attempt.consumer_audience != self._policy.consumer_audience
            or attempt.consumer_contract_id != self._policy.consumer_contract_id
            or attempt.consumer_contract_version != self._policy.consumer_contract_version
            or receipt.state is not result.state
            or receipt.runtime_slot_post_generation != result.runtime_slot_post_generation
            or receipt.use_count_post != result.use_count_post
            or receipt.context_adopted is not True
            or receipt.protected_runtime_context_use_performed is not True
            or receipt.context_terminal_non_reusable is not True
            or receipt.transient_material_zeroized is not True
            or receipt.completed_at != result.completed_at
            or receipt.signing_key_id != self._policy.receipt_verification_signing_key_id
            or any(result.authority.canonical_value().values())
            or any(attempt.authority.canonical_value().values())
            or any(claim.authority.canonical_value().values())
            or not self._use_receipt_signature_verifier.verify_receipt(receipt)
        ):
            self._raise("workflow_protected_runtime_start_evidence_conflict")

    def _attestation_request(
        self,
        source: WorkflowProtectedRuntimeStartAuthorizationSource,
        *,
        nonce_digest: str,
        requested_at: datetime,
    ) -> WorkflowProtectedRuntimeStartLifecycleAttestationRequest:
        result = source.result
        attempt = source.attempt
        claim = source.use_claim
        return WorkflowProtectedRuntimeStartLifecycleAttestationRequest(
            use_result_id=result.result_id,
            use_result_digest=result.canonical_digest,
            use_id=result.use_id,
            use_attempt_id=attempt.attempt_id,
            use_attempt_digest=attempt.canonical_digest,
            use_claim_id=claim.claim_id,
            use_claim_digest=claim.canonical_digest,
            use_receipt_digest=source.use_receipt.canonical_digest,
            authorization_consumption_result_id=result.authorization_consumption_result_id,
            authorization_consumption_result_digest=(
                result.authorization_consumption_result_digest
            ),
            destination_deployment_id=result.destination_deployment_id,
            destination_generation=result.destination_generation,
            destination_fencing_token_digest=result.destination_fencing_token_digest,
            runtime_slot_commitment=result.runtime_slot_commitment,
            runtime_slot_post_generation=cast(int, result.runtime_slot_post_generation),
            use_count_post=cast(int, result.use_count_post),
            use_profile_id=result.use_profile_id,
            use_profile_version=result.use_profile_version,
            use_profile_digest=result.use_profile_digest,
            runtime_start_profile_id=self._policy.runtime_start_profile_id,
            runtime_start_profile_version=self._policy.runtime_start_profile_version,
            runtime_start_profile_digest=self._policy.runtime_start_profile_digest,
            scope=attempt.scope,
            consumer_subject_id=self._policy.consumer_subject_id,
            consumer_audience=self._policy.consumer_audience,
            consumer_contract_id=self._policy.consumer_contract_id,
            consumer_contract_version=self._policy.consumer_contract_version,
            purpose_id=self._policy.purpose_id,
            request_nonce_digest=nonce_digest,
            requested_at=requested_at,
        )

    def _validate_attestation(
        self,
        attestation: WorkflowProtectedRuntimeStartLifecycleAttestation,
        *,
        request: WorkflowProtectedRuntimeStartLifecycleAttestationRequest,
        evaluated_at: datetime,
    ) -> None:
        forbidden = (
            attestation.raw_context_included,
            attestation.runtime_payload_included,
            attestation.runtime_envelope_locator_included,
            attestation.endpoint_included,
            attestation.credential_included,
            attestation.secret_included,
            attestation.bearer_token_included,
            attestation.runtime_use_authorized,
            attestation.runtime_start_authorized,
            attestation.runtime_resume_authorized,
            attestation.process_creation_authorized,
            attestation.scheduling_authorized,
            attestation.prompt_construction_authorized,
            attestation.model_inference_authorized,
            attestation.connector_activity_authorized,
            attestation.network_activity_authorized,
            attestation.readiness_probe_authorized,
            attestation.publication_authorized,
            attestation.delivery_authorized,
            attestation.dispatch_authorized,
            attestation.execution_authorized,
            attestation.infrastructure_mutation_authorized,
        )
        confirmations = (
            attestation.exact_use_result_confirmed,
            attestation.context_adoption_confirmed,
            attestation.context_terminal_non_reusable,
            attestation.runtime_envelope_current,
            attestation.runtime_envelope_inactive,
            attestation.runtime_not_started,
            attestation.runtime_not_resumed,
            attestation.process_not_created,
            attestation.destination_generation_current,
            attestation.destination_fence_current,
            attestation.runtime_slot_generation_current,
        )
        request_values = {
            name: getattr(request, name) for name in request.__slots__ if name != "requested_at"
        }
        if (
            any(getattr(attestation, name) != value for name, value in request_values.items())
            or attestation.attestor_id != self._policy.required_attestor_id
            or attestation.attestor_version != self._policy.required_attestor_version
            or attestation.signing_key_id != self._policy.verification_signing_key_id
            or attestation.observed_at < request.requested_at
            or not attestation.observed_at <= evaluated_at < attestation.valid_until
            or not all(confirmations)
            or any(forbidden)
            or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
            or not self._lifecycle_signature_verifier.verify_runtime_start_lifecycle_attestation(
                attestation
            )
        ):
            self._raise("workflow_protected_runtime_start_attestation_invalid")

    def _build_candidates(
        self,
        *,
        source: WorkflowProtectedRuntimeStartAuthorizationSource,
        attestation: WorkflowProtectedRuntimeStartLifecycleAttestation,
        issued_at: datetime,
        idempotency_digest: str,
        request_fingerprint: str,
    ) -> tuple[
        WorkflowProtectedRuntimeStartAuthorizationClaim,
        WorkflowProtectedRuntimeStartAuthorizationLease,
    ]:
        result = source.result
        attempt = source.attempt
        if (
            result.completed_at is None
            or result.runtime_slot_post_generation is None
            or result.use_count_post is None
        ):
            self._raise("workflow_protected_runtime_start_evidence_conflict")
        suffix = uuid4().hex
        source_values: dict[str, object] = {
            "use_result_id": result.result_id,
            "use_result_digest": result.canonical_digest,
            "use_id": result.use_id,
            "use_attempt_id": attempt.attempt_id,
            "use_attempt_digest": attempt.canonical_digest,
            "use_claim_id": source.use_claim.claim_id,
            "use_claim_digest": source.use_claim.canonical_digest,
            "use_receipt_digest": source.use_receipt.canonical_digest,
            "authorization_consumption_result_id": (result.authorization_consumption_result_id),
            "authorization_consumption_result_digest": (
                result.authorization_consumption_result_digest
            ),
            "use_result_state": result.state,
            "use_completed_at": result.completed_at,
            "use_result_recorded_at": result.recorded_at,
            "use_outcome_known": result.outcome_known,
            "context_adopted": result.context_adopted,
            "protected_runtime_context_use_performed": (
                result.protected_runtime_context_use_performed
            ),
            "context_terminal_non_reusable": result.context_terminal_non_reusable,
            "transient_material_zeroized": result.transient_material_zeroized,
            "destination_deployment_id": result.destination_deployment_id,
            "destination_generation": result.destination_generation,
            "destination_fencing_token_digest": result.destination_fencing_token_digest,
            "runtime_slot_commitment": result.runtime_slot_commitment,
            "runtime_slot_post_generation": result.runtime_slot_post_generation,
            "use_count_post": result.use_count_post,
            "use_profile_id": result.use_profile_id,
            "use_profile_version": result.use_profile_version,
            "use_profile_digest": result.use_profile_digest,
            "scope": attempt.scope,
            "consumer_subject_id": self._policy.consumer_subject_id,
            "consumer_audience": self._policy.consumer_audience,
            "consumer_contract_id": self._policy.consumer_contract_id,
            "consumer_contract_version": self._policy.consumer_contract_version,
            "purpose_id": self._policy.purpose_id,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
        }
        audit_payload = {
            "policy_digest": self._policy.canonical_digest,
            "request_fingerprint": request_fingerprint,
            "scope": attempt.scope.canonical_value(),
            "use_result_id": result.result_id,
        }
        claim_values = {
            **source_values,
            "claim_id": f"workflow-protected-runtime-start-claim.{suffix}",
            "request_fingerprint": request_fingerprint,
            "idempotency_digest": idempotency_digest,
            "authorization_audit_digest": canonical_digest(audit_payload),
            "claimed_at": issued_at,
            "authority": WorkflowProtectedRuntimeStartAuthorizationAuthority(),
        }
        claim = WorkflowProtectedRuntimeStartAuthorizationClaim(
            **cast(Any, claim_values),
            canonical_digest=canonical_digest(_payload(claim_values)),
        )
        effective_until = min(
            issued_at + timedelta(seconds=self._policy.maximum_lifetime_seconds),
            attestation.valid_until,
        )
        if effective_until <= issued_at:
            self._raise("workflow_protected_runtime_start_attestation_expired")
        lease_values = {
            **source_values,
            "authorization_lease_id": f"workflow-protected-runtime-start-lease.{suffix}",
            "claim_id": claim.claim_id,
            "claim_digest": claim.canonical_digest,
            "lifecycle_attestation_id": attestation.attestation_id,
            "lifecycle_attestation_digest": attestation.canonical_digest,
            "lifecycle_attestation_valid_until": attestation.valid_until,
            "runtime_start_profile_id": self._policy.runtime_start_profile_id,
            "runtime_start_profile_version": self._policy.runtime_start_profile_version,
            "runtime_start_profile_digest": self._policy.runtime_start_profile_digest,
            "issued_at": issued_at,
            "valid_until": effective_until,
            "effective_until": effective_until,
            "single_use": True,
            "renewable": False,
            "transferable": False,
            "lease_is_bearer_capability": False,
            "state": WorkflowProtectedRuntimeStartAuthorizationLeaseState.AUTHORIZED_UNCONSUMED,
            "authority": WorkflowProtectedRuntimeStartAuthorizationAuthority(
                protected_runtime_start_authority_granted=True
            ),
        }
        lease = WorkflowProtectedRuntimeStartAuthorizationLease(
            **cast(Any, lease_values),
            canonical_digest=canonical_digest(_payload(lease_values)),
        )
        return claim, lease

    def _validate_historical_lease(
        self, lease: WorkflowProtectedRuntimeStartAuthorizationLease, *, scope: object
    ) -> None:
        authority = lease.authority.canonical_value()
        dedicated = authority.pop("protected_runtime_start_authority_granted")
        if (
            lease.scope != scope
            or lease.policy_digest != self._policy.canonical_digest
            or lease.canonical_digest != canonical_digest(lease.digest_payload())
            or lease.valid_until - lease.issued_at > timedelta(seconds=1)
            or lease.valid_until > lease.lifecycle_attestation_valid_until
            or lease.single_use is not True
            or lease.renewable is not False
            or lease.transferable is not False
            or lease.lease_is_bearer_capability is not False
            or dedicated is not True
            or any(authority.values())
        ):
            self._raise("workflow_protected_runtime_start_repository_contract_violation")

    async def _postcommit_audit(
        self,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
        *,
        result_code: str,
        lease: WorkflowProtectedRuntimeStartAuthorizationLease,
    ) -> None:
        try:
            await self._audit_sink.record(
                AuditRecord(
                    event_id=f"evt_{uuid4().hex}",
                    event_type="atlas.workflow.protected-runtime-start-authorization.commit",
                    schema_version="1.0",
                    producer=WORKFLOW_PROTECTED_RUNTIME_START_AUTHORIZATION_PRODUCER,
                    producer_version=__version__,
                    occurred_at=context.requested_at,
                    correlation_id=context.correlation_id,
                    subject_id=context.subject_id,
                    actor_type=context.actor_type,
                    authentication_method=context.authentication_method,
                    assurance_level="workload",
                    permission_id="workflow.protected-runtime-start-authorizations.create",
                    resource_type="resource.workflow-protected-runtime-start-authorization-lease",
                    scope_reference="/".join(
                        (*context.scope.canonical_value().values(), "runtime-start")
                    ),
                    decision_id=context.decision_id,
                    outcome="succeeded",
                    result_code=result_code,
                    idempotency_key=None,
                    target_metadata=(
                        ("authorization_lease_id", lease.authorization_lease_id),
                        ("protected_runtime_start_request_authority", "true"),
                        ("runtime_start_authority", "false"),
                        ("runtime_resume_authority", "false"),
                        ("process_creation_authority", "false"),
                        ("model_inference_authority", "false"),
                        ("network_access_authority", "false"),
                        ("connector_activity_authority", "false"),
                        ("execution_authority", "false"),
                        ("infrastructure_mutation_authority", "false"),
                    ),
                )
            )
        except Exception:
            return

    @classmethod
    def _raise_preflight_status(
        cls, status: WorkflowProtectedRuntimeStartAuthorizationPreflightStatus
    ) -> NoReturn:
        statuses = WorkflowProtectedRuntimeStartAuthorizationPreflightStatus
        cls._raise(
            {
                statuses.IDEMPOTENCY_CONFLICT: (
                    "workflow_protected_runtime_start_idempotency_conflict"
                ),
                statuses.EVIDENCE_CONFLICT: "workflow_protected_runtime_start_evidence_conflict",
                statuses.ALREADY_AUTHORIZED: "workflow_protected_runtime_start_already_authorized",
            }.get(status, "workflow_protected_runtime_start_repository_contract_violation")
        )

    @classmethod
    def _raise_authorization_status(
        cls, status: WorkflowProtectedRuntimeStartAuthorizationLeaseStatus
    ) -> NoReturn:
        cls._raise(
            {
                WorkflowProtectedRuntimeStartAuthorizationLeaseStatus.IDEMPOTENCY_CONFLICT: (
                    "workflow_protected_runtime_start_idempotency_conflict"
                ),
                WorkflowProtectedRuntimeStartAuthorizationLeaseStatus.EVIDENCE_CONFLICT: (
                    "workflow_protected_runtime_start_evidence_conflict"
                ),
                WorkflowProtectedRuntimeStartAuthorizationLeaseStatus.ALREADY_AUTHORIZED: (
                    "workflow_protected_runtime_start_already_authorized"
                ),
            }.get(status, "workflow_protected_runtime_start_repository_contract_violation")
        )

    @staticmethod
    def _require_workload(
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> None:
        if (
            context.subject_id != WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT
            or context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience
            != WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
        ):
            WorkflowProtectedRuntimeStartAuthorizationService._raise(
                "workflow_protected_runtime_start_consumer_identity_required"
            )

    def _policy_source_value(self, name: str) -> object:
        from atlas.modules.workflows.domain.protected_runtime_context_use_domain import (
            code_owned_workflow_protected_runtime_context_use_policy,
        )

        return getattr(code_owned_workflow_protected_runtime_context_use_policy(), name)

    @staticmethod
    def _identifier(value: str, name: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 240 or any(c.isspace() for c in normalized):
            WorkflowProtectedRuntimeStartAuthorizationService._raise(
                f"workflow_protected_runtime_start_{name}_invalid"
            )
        return normalized

    @classmethod
    def _digest(cls, value: str, name: str) -> str:
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            cls._raise(f"workflow_protected_runtime_start_{name}_invalid")
        return value

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            cls._raise("workflow_protected_runtime_start_idempotency_key_invalid")
        return normalized

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowProtectedRuntimeStartAuthorizationError(
            code,
            "The protected runtime-start authorization request was denied.",
        )


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


__all__ = [
    "WORKFLOW_PROTECTED_RUNTIME_START_AUTHORIZATION_PRODUCER",
    "WorkflowProtectedRuntimeStartAuthorizationService",
]

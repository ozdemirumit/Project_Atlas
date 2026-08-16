from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.protected_runtime_context_injection_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier,
)
from atlas.modules.workflows.application.protected_runtime_context_use_authorization_ports import (
    WorkflowProtectedRuntimeContextUseAuthorizationError,
    WorkflowProtectedRuntimeContextUseAuthorizationLeaseRequest,
    WorkflowProtectedRuntimeContextUseAuthorizationLeaseStatus,
    WorkflowProtectedRuntimeContextUseAuthorizationPreflightRequest,
    WorkflowProtectedRuntimeContextUseAuthorizationPreflightStatus,
    WorkflowProtectedRuntimeContextUseAuthorizationPresentation,
    WorkflowProtectedRuntimeContextUseAuthorizationRepository,
    WorkflowProtectedRuntimeContextUseAuthorizationSource,
    WorkflowProtectedRuntimeSlotLifecycleAttestation,
    WorkflowProtectedRuntimeSlotLifecycleAttestationRequest,
    WorkflowProtectedRuntimeSlotLifecycleAttestor,
    WorkflowProtectedRuntimeSlotLifecycleSignatureVerifier,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_context_injection_consumption_domain import (
    WorkflowProtectedRuntimeContextInjectionConsumptionResultState,
)
from atlas.modules.workflows.domain.protected_runtime_context_use_authorization_domain import (
    WorkflowProtectedRuntimeContextUseAuthorizationAuthority,
    WorkflowProtectedRuntimeContextUseAuthorizationClaim,
    WorkflowProtectedRuntimeContextUseAuthorizationLease,
    WorkflowProtectedRuntimeContextUseAuthorizationLeaseState,
    WorkflowProtectedRuntimeContextUseAuthorizationPolicy,
    code_owned_workflow_protected_runtime_context_use_authorization_policy,
)

WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_AUTHORIZATION_PRODUCER = (
    "project-atlas-workflow-protected-runtime-context-use-authorizer"
)


class WorkflowProtectedRuntimeContextUseAuthorizationService:
    """Issues a bounded authorization lease but never uses protected runtime context."""

    def __init__(
        self,
        *,
        authorization_repository: WorkflowProtectedRuntimeContextUseAuthorizationRepository,
        lifecycle_attestor: WorkflowProtectedRuntimeSlotLifecycleAttestor,
        lifecycle_signature_verifier: WorkflowProtectedRuntimeSlotLifecycleSignatureVerifier,
        injector_receipt_signature_verifier: (
            WorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier
        ),
        audit_sink: AuditSink,
        policy: WorkflowProtectedRuntimeContextUseAuthorizationPolicy | None = None,
    ) -> None:
        self._repository = authorization_repository
        self._lifecycle_attestor = lifecycle_attestor
        self._lifecycle_signature_verifier = lifecycle_signature_verifier
        self._injector_receipt_signature_verifier = injector_receipt_signature_verifier
        self._audit_sink = audit_sink
        self._policy = (
            policy or code_owned_workflow_protected_runtime_context_use_authorization_policy()
        )

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def repository(self) -> WorkflowProtectedRuntimeContextUseAuthorizationRepository:
        return self._repository

    @property
    def policy(self) -> WorkflowProtectedRuntimeContextUseAuthorizationPolicy:
        return self._policy

    async def authorize(
        self,
        *,
        injection_result_id: str,
        injection_result_digest: str,
        policy_id: str,
        policy_version: str,
        idempotency_key: str,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationLease:
        self._require_workload(context)
        if not self._repository.durable:
            self._raise("workflow_protected_runtime_context_use_durable_repository_required")
        result_id = self._identifier(injection_result_id, "injection_result_id")
        result_digest = self._digest(injection_result_digest, "injection_result_digest")
        normalized_key = self._idempotency_key(idempotency_key)
        if policy_id != self._policy.policy_id or policy_version != self._policy.policy_version:
            self._raise("workflow_protected_runtime_context_use_policy_conflict")
        idempotency_digest = canonical_digest(
            {
                "idempotency_key": normalized_key,
                "scope": context.scope.canonical_value(),
                "subject_id": context.subject_id,
            }
        )
        fingerprint = canonical_digest(
            {
                "injection_result_digest": result_digest,
                "injection_result_id": result_id,
                "policy_digest": self._policy.canonical_digest,
                "scope": context.scope.canonical_value(),
                "subject_id": context.subject_id,
            }
        )
        preflight_request = WorkflowProtectedRuntimeContextUseAuthorizationPreflightRequest(
            injection_result_id=result_id,
            injection_result_digest=result_digest,
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
            offline_injector_receipt_signature_verifier=(self._injector_receipt_signature_verifier),
        )
        try:
            preflight = await (
                self._repository.preflight_protected_runtime_context_use_authorization(
                    preflight_request
                )
            )
        except WorkflowProtectedRuntimeContextUseAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_context_use_repository_unavailable")
        statuses = WorkflowProtectedRuntimeContextUseAuthorizationPreflightStatus
        if preflight.status is statuses.REPLAY:
            if preflight.lease is None or preflight.evaluated_at is None:
                self._raise("workflow_protected_runtime_context_use_repository_contract_violation")
            self._validate_historical_lease(preflight.lease, scope=context.scope)
            await self._postcommit_audit(
                context,
                result_code="workflow_protected_runtime_context_use_authorization_replayed",
                lease=preflight.lease,
            )
            return preflight.lease
        if preflight.status is not statuses.NONE:
            self._raise_preflight_status(preflight.status)
        if preflight.lease is not None or preflight.evaluated_at is None:
            self._raise("workflow_protected_runtime_context_use_repository_contract_violation")
        if not self._lifecycle_attestor.available:
            self._raise("workflow_protected_runtime_context_use_trusted_attestor_unavailable")
        try:
            source = await self._repository.get_protected_runtime_context_use_authorization_source(
                injection_result_id=result_id
            )
        except WorkflowProtectedRuntimeContextUseAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_context_use_repository_unavailable")
        if source is None:
            self._raise("workflow_protected_runtime_context_use_evidence_conflict")
        self._validate_source(source, expected_digest=result_digest, scope=context.scope)
        nonce_digest = canonical_digest({"nonce": uuid4().hex, "request_fingerprint": fingerprint})
        attestation_request = self._attestation_request(
            source,
            nonce_digest=nonce_digest,
            requested_at=preflight.evaluated_at,
        )
        try:
            attestation = await self._lifecycle_attestor.attest_runtime_slot_lifecycle(
                attestation_request
            )
        except WorkflowProtectedRuntimeContextUseAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_context_use_evidence_conflict")
        try:
            authoritative_now = await self._repository.get_authoritative_time()
        except Exception:
            self._raise("workflow_protected_runtime_context_use_repository_unavailable")
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
        request = WorkflowProtectedRuntimeContextUseAuthorizationLeaseRequest(
            source=source,
            lifecycle_attestation=attestation,
            expected_request_nonce_digest=nonce_digest,
            offline_signature_verifier=self._lifecycle_signature_verifier,
            offline_injector_receipt_signature_verifier=(self._injector_receipt_signature_verifier),
            expected_policy_digest=self._policy.canonical_digest,
            expected_validity_window_seconds=1,
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
            outcome = await self._repository.authorize_protected_runtime_context_use(request)
        except WorkflowProtectedRuntimeContextUseAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_context_use_repository_unavailable")
        lease_statuses = WorkflowProtectedRuntimeContextUseAuthorizationLeaseStatus
        if outcome.status not in (lease_statuses.AUTHORIZED, lease_statuses.REPLAY):
            self._raise_authorization_status(outcome.status)
        if outcome.lease is None or outcome.evaluated_at is None:
            self._raise("workflow_protected_runtime_context_use_repository_contract_violation")
        self._validate_historical_lease(outcome.lease, scope=context.scope)
        await self._postcommit_audit(
            context,
            result_code=(
                "workflow_protected_runtime_context_use_authorization_created"
                if outcome.status is lease_statuses.AUTHORIZED
                else "workflow_protected_runtime_context_use_authorization_replayed"
            ),
            lease=outcome.lease,
        )
        return outcome.lease

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeContextUseAuthorizationPresentation, ...]:
        if not self._repository.durable:
            self._raise("workflow_protected_runtime_context_use_durable_repository_required")
        try:
            return await (
                self._repository.list_protected_runtime_context_use_authorization_presentations(
                    scope=scope,
                    limit=max(1, min(limit, 256)),
                )
            )
        except WorkflowProtectedRuntimeContextUseAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_context_use_repository_unavailable")

    async def get_presentation(
        self, *, scope: WorkflowScope, authorization_lease_id: str
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationPresentation:
        lease_id = self._identifier(authorization_lease_id, "authorization_lease_id")
        if not self._repository.durable:
            self._raise("workflow_protected_runtime_context_use_durable_repository_required")
        try:
            presentations = await (
                self._repository.list_protected_runtime_context_use_authorization_presentations(
                    scope=scope,
                    authorization_lease_ids=(lease_id,),
                    limit=1,
                )
            )
        except WorkflowProtectedRuntimeContextUseAuthorizationError:
            raise
        except Exception:
            self._raise("workflow_protected_runtime_context_use_repository_unavailable")
        if len(presentations) != 1 or presentations[0].lease.authorization_lease_id != lease_id:
            self._raise("workflow_protected_runtime_context_use_authorization_not_found")
        return presentations[0]

    def _validate_source(
        self,
        source: WorkflowProtectedRuntimeContextUseAuthorizationSource,
        *,
        expected_digest: str,
        scope: object,
    ) -> None:
        result = source.result
        attempt = source.attempt
        claim = source.consumption_claim
        receipt = source.injector_receipt
        if (
            result.canonical_digest != expected_digest
            or result.canonical_digest != canonical_digest(result.digest_payload())
            or attempt.canonical_digest != canonical_digest(attempt.digest_payload())
            or claim.canonical_digest != canonical_digest(claim.digest_payload())
            or receipt.canonical_digest != canonical_digest(receipt.digest_payload())
            or result.state
            is not (
                WorkflowProtectedRuntimeContextInjectionConsumptionResultState.INJECTED_INTO_PROTECTED_RUNTIME_SLOT
            )
            or result.outcome_known is not True
            or result.protected_runtime_handle_consumed is not True
            or result.inert_context_injected is not True
            or result.runtime_slot_mutation_performed is not True
            or result.completed_at is None
            or result.injector_receipt_digest != receipt.canonical_digest
            or result.attempt_id != attempt.attempt_id
            or result.attempt_digest != attempt.canonical_digest
            or result.consumption_claim_id != claim.claim_id
            or result.consumption_claim_digest != claim.canonical_digest
            or result.authorization_lease_id != attempt.authorization_lease_id
            or result.authorization_lease_digest != attempt.authorization_lease_digest
            or attempt.consumption_claim_id != claim.claim_id
            or attempt.consumption_claim_digest != claim.canonical_digest
            or result.runtime_slot_post_generation != attempt.expected_runtime_slot_post_generation
            or attempt.protected_runtime_handle_usable_until.tzinfo is None
            or result.completed_at >= attempt.protected_runtime_handle_usable_until
            or result.runtime_slot_commitment != attempt.runtime_slot_commitment
            or result.destination_boundary_id != attempt.destination_boundary_id
            or result.destination_deployment_id != attempt.destination_deployment_id
            or result.destination_generation != attempt.destination_generation
            or result.destination_fencing_token_digest != attempt.destination_fencing_token_digest
            or result.runtime_slot_profile_id != self._policy.runtime_slot_profile_id
            or result.runtime_slot_profile_version != self._policy.runtime_slot_profile_version
            or result.runtime_slot_profile_digest != self._policy.runtime_slot_profile_digest
            or attempt.scope != scope
            or attempt.consumer_subject_id != self._policy.consumer_subject_id
            or attempt.consumer_audience != self._policy.consumer_audience
            or attempt.consumer_contract_id != self._policy.consumer_contract_id
            or attempt.consumer_contract_version != self._policy.consumer_contract_version
            or receipt.runtime_slot_post_generation != result.runtime_slot_post_generation
            or receipt.runtime_slot_pre_generation != result.runtime_slot_pre_generation
            or receipt.state is not result.state
            or receipt.protected_runtime_handle_consumed is not True
            or receipt.inert_context_injected is not True
            or receipt.runtime_slot_mutation_performed is not True
            or receipt.completed_at != result.completed_at
            or receipt.signing_key_id != self._policy.receipt_verification_signing_key_id
            or any(result.authority.canonical_value().values())
            or any(attempt.authority.canonical_value().values())
            or any(claim.authority.canonical_value().values())
            or not self._injector_receipt_signature_verifier.verify_receipt(receipt)
        ):
            self._raise("workflow_protected_runtime_context_use_evidence_conflict")

    def _attestation_request(
        self,
        source: WorkflowProtectedRuntimeContextUseAuthorizationSource,
        *,
        nonce_digest: str,
        requested_at: datetime,
    ) -> WorkflowProtectedRuntimeSlotLifecycleAttestationRequest:
        result = source.result
        attempt = source.attempt
        claim = source.consumption_claim
        return WorkflowProtectedRuntimeSlotLifecycleAttestationRequest(
            injection_result_id=result.result_id,
            injection_result_digest=result.canonical_digest,
            injection_id=result.injection_id,
            injection_attempt_id=attempt.attempt_id,
            injection_attempt_digest=attempt.canonical_digest,
            injection_consumption_claim_id=claim.claim_id,
            injection_consumption_claim_digest=claim.canonical_digest,
            injection_authorization_lease_id=result.authorization_lease_id,
            injection_authorization_lease_digest=result.authorization_lease_digest,
            injector_receipt_digest=source.injector_receipt.canonical_digest,
            destination_boundary_id=result.destination_boundary_id,
            destination_deployment_id=result.destination_deployment_id,
            destination_generation=result.destination_generation,
            destination_fencing_token_digest=result.destination_fencing_token_digest,
            runtime_slot_profile_id=result.runtime_slot_profile_id,
            runtime_slot_profile_version=result.runtime_slot_profile_version,
            runtime_slot_profile_digest=result.runtime_slot_profile_digest,
            runtime_slot_commitment=result.runtime_slot_commitment,
            runtime_slot_post_generation=cast(int, result.runtime_slot_post_generation),
            injected_context_usable_until=attempt.protected_runtime_handle_usable_until,
            use_profile_id=self._policy.use_profile_id,
            use_profile_version=self._policy.use_profile_version,
            use_profile_digest=self._policy.use_profile_digest,
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
        attestation: WorkflowProtectedRuntimeSlotLifecycleAttestation,
        *,
        request: WorkflowProtectedRuntimeSlotLifecycleAttestationRequest,
        evaluated_at: datetime,
    ) -> None:
        forbidden = (
            attestation.raw_context_included,
            attestation.runtime_payload_included,
            attestation.runtime_slot_locator_included,
            attestation.endpoint_included,
            attestation.credential_included,
            attestation.secret_included,
            attestation.bearer_token_included,
            attestation.runtime_use_authorized,
            attestation.runtime_start_authorized,
            attestation.runtime_resume_authorized,
            attestation.connector_activity_authorized,
            attestation.network_activity_authorized,
            attestation.readiness_probe_authorized,
            attestation.publication_authorized,
            attestation.delivery_authorized,
            attestation.dispatch_authorized,
            attestation.execution_authorized,
            attestation.infrastructure_mutation_authorized,
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
            or evaluated_at >= attestation.injected_context_usable_until
            or attestation.valid_until > attestation.injected_context_usable_until
            or not attestation.exact_runtime_slot_confirmed
            or not attestation.inert_context_present
            or not attestation.runtime_slot_inert
            or not attestation.runtime_slot_unused
            or not attestation.runtime_slot_unrevoked
            or not attestation.destination_generation_current
            or not attestation.destination_fence_current
            or not attestation.use_profile_eligible
            or any(forbidden)
            or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
            or not self._lifecycle_signature_verifier.verify_runtime_slot_lifecycle_attestation(
                attestation
            )
        ):
            self._raise("workflow_protected_runtime_context_use_attestation_invalid")

    def _build_candidates(
        self,
        *,
        source: WorkflowProtectedRuntimeContextUseAuthorizationSource,
        attestation: WorkflowProtectedRuntimeSlotLifecycleAttestation,
        issued_at: datetime,
        idempotency_digest: str,
        request_fingerprint: str,
    ) -> tuple[
        WorkflowProtectedRuntimeContextUseAuthorizationClaim,
        WorkflowProtectedRuntimeContextUseAuthorizationLease,
    ]:
        result = source.result
        attempt = source.attempt
        if result.completed_at is None or result.runtime_slot_post_generation is None:
            self._raise("workflow_protected_runtime_context_use_evidence_conflict")
        suffix = uuid4().hex
        source_values: dict[str, object] = {
            "injection_result_id": result.result_id,
            "injection_result_digest": result.canonical_digest,
            "injection_id": result.injection_id,
            "injection_attempt_id": attempt.attempt_id,
            "injection_attempt_digest": attempt.canonical_digest,
            "injection_consumption_claim_id": source.consumption_claim.claim_id,
            "injection_consumption_claim_digest": source.consumption_claim.canonical_digest,
            "injection_authorization_lease_id": result.authorization_lease_id,
            "injection_authorization_lease_digest": result.authorization_lease_digest,
            "injector_receipt_digest": source.injector_receipt.canonical_digest,
            "injection_result_state": result.state,
            "injection_completed_at": result.completed_at,
            "injection_result_recorded_at": result.recorded_at,
            "injection_deadline": result.injection_deadline,
            "inert_context_injected": result.inert_context_injected,
            "runtime_slot_mutation_performed": result.runtime_slot_mutation_performed,
            "protected_runtime_handle_consumed": result.protected_runtime_handle_consumed,
            "injection_outcome_known": result.outcome_known,
            "destination_boundary_id": result.destination_boundary_id,
            "destination_deployment_id": result.destination_deployment_id,
            "destination_generation": result.destination_generation,
            "destination_fencing_token_digest": result.destination_fencing_token_digest,
            "runtime_slot_profile_id": result.runtime_slot_profile_id,
            "runtime_slot_profile_version": result.runtime_slot_profile_version,
            "runtime_slot_profile_digest": result.runtime_slot_profile_digest,
            "runtime_slot_commitment": result.runtime_slot_commitment,
            "runtime_slot_post_generation": result.runtime_slot_post_generation,
            "injected_context_usable_until": (attempt.protected_runtime_handle_usable_until),
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
            "injection_result_id": result.result_id,
            "policy_digest": self._policy.canonical_digest,
            "request_fingerprint": request_fingerprint,
            "scope": attempt.scope.canonical_value(),
        }
        claim_values = {
            **source_values,
            "claim_id": f"workflow-protected-runtime-context-use-claim.{suffix}",
            "request_fingerprint": request_fingerprint,
            "idempotency_digest": idempotency_digest,
            "authorization_audit_digest": canonical_digest(audit_payload),
            "claimed_at": issued_at,
            "authority": WorkflowProtectedRuntimeContextUseAuthorizationAuthority(),
        }
        claim = WorkflowProtectedRuntimeContextUseAuthorizationClaim(
            **cast(Any, claim_values),
            canonical_digest=canonical_digest(_payload(claim_values)),
        )
        effective_until = min(
            issued_at + timedelta(seconds=self._policy.maximum_lifetime_seconds),
            attestation.valid_until,
            attestation.injected_context_usable_until,
        )
        if effective_until <= issued_at:
            self._raise("workflow_protected_runtime_context_use_attestation_expired")
        lease_values = {
            **source_values,
            "authorization_lease_id": (f"workflow-protected-runtime-context-use-lease.{suffix}"),
            "claim_id": claim.claim_id,
            "claim_digest": claim.canonical_digest,
            "lifecycle_attestation_id": attestation.attestation_id,
            "lifecycle_attestation_digest": attestation.canonical_digest,
            "lifecycle_attestation_valid_until": attestation.valid_until,
            "use_profile_id": self._policy.use_profile_id,
            "use_profile_version": self._policy.use_profile_version,
            "use_profile_digest": self._policy.use_profile_digest,
            "issued_at": issued_at,
            "valid_until": effective_until,
            "effective_until": effective_until,
            "single_use": True,
            "renewable": False,
            "transferable": False,
            "lease_is_bearer_capability": False,
            "state": (
                WorkflowProtectedRuntimeContextUseAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
            ),
            "authority": WorkflowProtectedRuntimeContextUseAuthorizationAuthority(
                protected_runtime_context_use_authority_granted=True
            ),
        }
        lease = WorkflowProtectedRuntimeContextUseAuthorizationLease(
            **cast(Any, lease_values),
            canonical_digest=canonical_digest(_payload(lease_values)),
        )
        return claim, lease

    def _validate_historical_lease(
        self, lease: WorkflowProtectedRuntimeContextUseAuthorizationLease, *, scope: object
    ) -> None:
        authority = lease.authority.canonical_value()
        dedicated = authority.pop("protected_runtime_context_use_authority_granted")
        if (
            lease.scope != scope
            or lease.policy_digest != self._policy.canonical_digest
            or lease.canonical_digest != canonical_digest(lease.digest_payload())
            or lease.valid_until - lease.issued_at > timedelta(seconds=1)
            or lease.injected_context_usable_until.tzinfo is None
            or lease.valid_until > lease.injected_context_usable_until
            or lease.single_use is not True
            or lease.renewable is not False
            or lease.transferable is not False
            or lease.lease_is_bearer_capability is not False
            or dedicated is not True
            or any(authority.values())
        ):
            self._raise("workflow_protected_runtime_context_use_repository_contract_violation")

    async def _postcommit_audit(
        self,
        context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
        *,
        result_code: str,
        lease: WorkflowProtectedRuntimeContextUseAuthorizationLease,
    ) -> None:
        try:
            await self._audit_sink.record(
                AuditRecord(
                    event_id=f"evt_{uuid4().hex}",
                    event_type=(
                        "atlas.workflow.protected-runtime-context-use-authorization.commit"
                    ),
                    schema_version="1.0",
                    producer=WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_AUTHORIZATION_PRODUCER,
                    producer_version=__version__,
                    occurred_at=context.requested_at,
                    correlation_id=context.correlation_id,
                    subject_id=context.subject_id,
                    actor_type=context.actor_type,
                    authentication_method=context.authentication_method,
                    assurance_level="workload",
                    permission_id="workflow.protected-runtime-context-use-authorizations.create",
                    resource_type=(
                        "resource.workflow-protected-runtime-context-use-authorization-lease"
                    ),
                    scope_reference="/".join(
                        (*context.scope.canonical_value().values(), "runtime-context-use")
                    ),
                    decision_id=context.decision_id,
                    outcome="succeeded",
                    result_code=result_code,
                    idempotency_key=None,
                    target_metadata=(
                        ("authorization_lease_id", lease.authorization_lease_id),
                        ("runtime_context_use_lease_authority", "true"),
                        ("runtime_use_authority", "false"),
                        ("runtime_start_authority", "false"),
                        ("runtime_resume_authority", "false"),
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
        cls, status: WorkflowProtectedRuntimeContextUseAuthorizationPreflightStatus
    ) -> NoReturn:
        statuses = WorkflowProtectedRuntimeContextUseAuthorizationPreflightStatus
        cls._raise(
            {
                statuses.IDEMPOTENCY_CONFLICT: (
                    "workflow_protected_runtime_context_use_idempotency_conflict"
                ),
                statuses.EVIDENCE_CONFLICT: (
                    "workflow_protected_runtime_context_use_evidence_conflict"
                ),
                statuses.ALREADY_AUTHORIZED: (
                    "workflow_protected_runtime_context_use_already_authorized"
                ),
            }.get(
                status,
                "workflow_protected_runtime_context_use_repository_contract_violation",
            )
        )

    @classmethod
    def _raise_authorization_status(
        cls, status: WorkflowProtectedRuntimeContextUseAuthorizationLeaseStatus
    ) -> NoReturn:
        cls._raise(
            {
                WorkflowProtectedRuntimeContextUseAuthorizationLeaseStatus.IDEMPOTENCY_CONFLICT: (
                    "workflow_protected_runtime_context_use_idempotency_conflict"
                ),
                WorkflowProtectedRuntimeContextUseAuthorizationLeaseStatus.EVIDENCE_CONFLICT: (
                    "workflow_protected_runtime_context_use_evidence_conflict"
                ),
                WorkflowProtectedRuntimeContextUseAuthorizationLeaseStatus.ALREADY_AUTHORIZED: (
                    "workflow_protected_runtime_context_use_already_authorized"
                ),
            }.get(
                status,
                "workflow_protected_runtime_context_use_repository_contract_violation",
            )
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
            WorkflowProtectedRuntimeContextUseAuthorizationService._raise(
                "workflow_protected_runtime_context_use_consumer_identity_required"
            )

    @staticmethod
    def _identifier(value: str, name: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 240 or any(c.isspace() for c in normalized):
            WorkflowProtectedRuntimeContextUseAuthorizationService._raise(
                f"workflow_protected_runtime_context_use_{name}_invalid"
            )
        return normalized

    @classmethod
    def _digest(cls, value: str, name: str) -> str:
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            cls._raise(f"workflow_protected_runtime_context_use_{name}_invalid")
        return value

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            cls._raise("workflow_protected_runtime_context_use_idempotency_key_invalid")
        return normalized

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowProtectedRuntimeContextUseAuthorizationError(
            code,
            "The protected runtime-context use authorization request was denied.",
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
    "WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_AUTHORIZATION_PRODUCER",
    "WorkflowProtectedRuntimeContextUseAuthorizationService",
]

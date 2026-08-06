from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.final_validation_ports import PackageFinalValidationError
from atlas.modules.connectors.application.package_approval_ports import (
    PackageApprovalError,
    PackageApprovalFinalValidationSource,
    PackageApprovalPolicySource,
    PackageApprovalRepository,
)
from atlas.modules.connectors.domain.final_validation import (
    ConnectorPackageFinalValidation,
    FinalValidationOutcome,
)
from atlas.modules.connectors.domain.package_approval import (
    ConnectorPackageApprovalDecision,
    ConnectorPackageApprovalPolicySnapshot,
    ConnectorPackageApprovalRecord,
    ConnectorPackageApprovalRequest,
    PackageApprovalOutcome,
    PackageApprovalState,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

APPROVAL_REQUEST_SCHEMA = "atlas.connector-package-approval-request.v1"
APPROVAL_DECISION_SCHEMA = "atlas.connector-package-approval-decision.v1"
APPROVAL_CREATE_PERMISSION = "connectors.package-approval-requests.create"
APPROVAL_READ_PERMISSION = "connectors.package-approval-requests.read"
APPROVAL_DECIDE_PERMISSION = "connectors.package-approval-requests.decide"


class PackageApprovalService:
    def __init__(
        self,
        *,
        repository: PackageApprovalRepository,
        final_validation_source: PackageApprovalFinalValidationSource,
        policy_source: PackageApprovalPolicySource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._final_validation_source = final_validation_source
        self._policy_source = policy_source
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> PackageApprovalRepository:
        return self._repository

    async def create_request(
        self,
        *,
        actor: AuthenticatedSubject,
        source_final_validation_id: str,
        source_final_validation_digest: str,
        package_digest: str,
        approval_policy_id: str,
        approval_policy_digest: str,
        purpose: str,
        acknowledged_request_is_not_approval: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorPackageApprovalRecord:
        self._require_enterprise_human(actor)
        if not acknowledged_request_is_not_approval:
            raise PackageApprovalError("package_approval_request_acknowledgement_required")
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise PackageApprovalError("package_approval_request_invalid")
        fingerprint = self._digest(
            {
                "source_final_validation_id": source_final_validation_id,
                "source_final_validation_digest": source_final_validation_digest,
                "package_digest": package_digest,
                "approval_policy_id": approval_policy_id,
                "approval_policy_digest": approval_policy_digest,
                "purpose": purpose,
            }
        )
        existing = await self._repository.get_request_by_create_key(
            requested_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return await self._reuse_request(existing, actor, fingerprint)

        validation, _ = await self._load_final(source_final_validation_id)
        self._require_scope(actor, validation.organization_id, validation.environment_id)
        policy = await self._policy_source.get_by_id(policy_id=approval_policy_id)
        if policy is None:
            raise PackageApprovalError("package_approval_policy_not_found")
        self._verify_policy(policy)
        now = self._clock()
        if (
            validation.canonical_digest != source_final_validation_digest
            or validation.package_digest != package_digest
            or validation.outcome is not FinalValidationOutcome.ELIGIBLE
            or not validation.eligible_for_human_approval
            or validation.promotion_blocked
            or policy.canonical_digest != approval_policy_digest
            or policy.organization_id != validation.organization_id
            or policy.environment_id != validation.environment_id
            or policy.required_final_validation_schema != validation.schema_version
            or not policy.issued_at <= now < policy.expires_at
            or validation.validated_at > now
            or now - validation.validated_at
            > timedelta(hours=policy.maximum_final_validation_age_hours)
        ):
            raise PackageApprovalError("package_approval_source_not_eligible")
        request_digest_seed = self._digest([validation.validation_id, policy.canonical_digest])
        request = ConnectorPackageApprovalRequest(
            request_id=f"connector-package-approval-request.{request_digest_seed[:24]}",
            schema_version=APPROVAL_REQUEST_SCHEMA,
            version=1,
            source_final_validation_id=validation.validation_id,
            source_final_validation_digest=validation.canonical_digest,
            source_handoff_id=validation.source_handoff_id,
            source_project_id=validation.source_project_id,
            source_actor_set_digest=validation.source_actor_set_digest,
            organization_id=validation.organization_id,
            environment_id=validation.environment_id,
            requested_by=actor.subject_id,
            purpose=purpose,
            approval_policy_id=policy.policy_id,
            approval_policy_digest=policy.canonical_digest,
            approval_policy_version=policy.policy_version,
            package_digest=validation.package_digest,
            inventory_digest=validation.inventory_digest,
            product_family=validation.product_family,
            observed_product_version=validation.observed_product_version,
            evidence_digest=validation.evidence_digest,
            final_policy_id=validation.policy_id,
            final_policy_digest=validation.policy_digest,
            final_policy_version=validation.policy_version,
            stage_count=validation.stage_count,
            passed_stage_count=validation.passed_stage_count,
            finding_count=validation.finding_count,
            limitation_count=validation.limitation_count,
            blocking_risk_count=validation.blocking_risk_count,
            created_at=now,
            expires_at=now + timedelta(minutes=policy.request_lifetime_minutes),
            canonical_digest="0" * 64,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
        )
        request = replace(request, canonical_digest=self._digest(self._request_payload(request)))
        async with self._mutation_lock:
            source_existing = await self._repository.get_request_by_source(
                source_final_validation_id=validation.validation_id
            )
            if source_existing is not None:
                if (
                    source_existing.requested_by == actor.subject_id
                    and source_existing.request_fingerprint == fingerprint
                ):
                    return self._record(replace(source_existing, reused=True), None, now)
                raise PackageApprovalError("package_approval_request_exists")
            await self._audit_request(actor, correlation_id, request)
            if not await self._repository.add_request(request):
                raced = await self._repository.get_request_by_create_key(
                    requested_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise PackageApprovalError("package_approval_request_conflict")
                self._verify_request(raced)
                request = replace(raced, reused=True)
        return self._record(request, None, now)

    async def decide(
        self,
        *,
        actor: AuthenticatedSubject,
        request_id: str,
        expected_request_version: int,
        request_digest: str,
        outcome: PackageApprovalOutcome,
        rationale: str,
        acknowledged_decision_grants_no_runtime_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorPackageApprovalRecord:
        self._require_enterprise_human(actor)
        if not acknowledged_decision_grants_no_runtime_authority:
            raise PackageApprovalError("package_approval_decision_acknowledgement_required")
        rationale = rationale.strip()
        if not 8 <= len(idempotency_key) <= 128:
            raise PackageApprovalError("package_approval_decision_invalid")
        request = await self._repository.get_request(request_id=request_id)
        if request is None:
            raise PackageApprovalError("package_approval_request_not_found")
        self._verify_request(request)
        self._require_scope(actor, request.organization_id, request.environment_id)
        policy = await self._policy_source.get_by_id(policy_id=request.approval_policy_id)
        if policy is None:
            raise PackageApprovalError("package_approval_policy_not_found")
        self._verify_policy(policy)
        validation, forbidden = await self._load_final(request.source_final_validation_id)
        now = self._clock()
        if (
            request.version != expected_request_version
            or request.canonical_digest != request_digest
            or validation.canonical_digest != request.source_final_validation_digest
            or policy.canonical_digest != request.approval_policy_digest
            or outcome not in policy.permitted_outcomes
            or not policy.minimum_rationale_length
            <= len(rationale)
            <= policy.maximum_rationale_length
        ):
            raise PackageApprovalError("package_approval_decision_binding_invalid")
        if now >= request.expires_at or not policy.issued_at <= now < policy.expires_at:
            raise PackageApprovalError("package_approval_request_expired")
        if actor.subject_id in forbidden | {request.requested_by, policy.signed_by}:
            raise PackageApprovalError("package_approval_separation_required")
        fingerprint = self._digest(
            {
                "request_id": request_id,
                "expected_request_version": expected_request_version,
                "request_digest": request_digest,
                "outcome": outcome.value,
                "rationale": rationale,
            }
        )
        existing = await self._repository.get_decision_by_create_key(
            decided_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return self._reuse_decision(request, existing, actor, fingerprint, now)
        decision_digest_seed = self._digest([request_id, outcome.value, actor.subject_id])
        decision = ConnectorPackageApprovalDecision(
            decision_id=f"connector-package-approval-decision.{decision_digest_seed[:24]}",
            schema_version=APPROVAL_DECISION_SCHEMA,
            version=1,
            request_id=request.request_id,
            request_version=request.version,
            request_digest=request.canonical_digest,
            outcome=outcome,
            decided_by=actor.subject_id,
            rationale=rationale,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            source_final_validation_id=request.source_final_validation_id,
            source_final_validation_digest=request.source_final_validation_digest,
            package_digest=request.package_digest,
            approval_policy_id=request.approval_policy_id,
            approval_policy_digest=request.approval_policy_digest,
            decided_at=now,
            canonical_digest="0" * 64,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
        )
        decision = replace(
            decision, canonical_digest=self._digest(self._decision_payload(decision))
        )
        async with self._mutation_lock:
            terminal = await self._repository.get_decision(request_id=request.request_id)
            if terminal is not None:
                raise PackageApprovalError("package_approval_decision_exists")
            await self._audit_decision(actor, correlation_id, decision)
            if not await self._repository.add_decision(decision):
                raced = await self._repository.get_decision_by_create_key(
                    decided_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise PackageApprovalError("package_approval_decision_conflict")
                self._verify_decision(raced)
                decision = replace(raced, reused=True)
        return self._record(request, decision, now)

    async def get(
        self, *, actor: AuthenticatedSubject, request_id: str, correlation_id: str
    ) -> ConnectorPackageApprovalRecord:
        self._require_enterprise_human(actor)
        request = await self._repository.get_request(request_id=request_id)
        if request is None:
            raise PackageApprovalError("package_approval_request_not_found")
        self._verify_request(request)
        self._require_scope(actor, request.organization_id, request.environment_id)
        decision = await self._repository.get_decision(request_id=request_id)
        if decision is not None:
            self._verify_decision(decision)
        await self._audit_read(actor, correlation_id, request)
        return self._record(request, decision, self._clock())

    async def publisher_attestation_source(
        self, *, request_id: str
    ) -> tuple[ConnectorPackageApprovalRecord, frozenset[str]]:
        request = await self._repository.get_request(request_id=request_id)
        if request is None:
            raise PackageApprovalError("package_approval_request_not_found")
        self._verify_request(request)
        decision = await self._repository.get_decision(request_id=request_id)
        if decision is None:
            raise PackageApprovalError("package_approval_decision_not_found")
        self._verify_decision(decision)
        policy = await self._policy_source.get_by_id(policy_id=request.approval_policy_id)
        if policy is None:
            raise PackageApprovalError("package_approval_policy_not_found")
        self._verify_policy(policy)
        validation, upstream = await self._load_final(request.source_final_validation_id)
        now = self._clock()
        record = self._record(request, decision, now)
        if (
            validation.canonical_digest != request.source_final_validation_digest
            or decision.request_digest != request.canonical_digest
            or decision.package_digest != request.package_digest
            or policy.canonical_digest != request.approval_policy_digest
            or not policy.issued_at <= now < policy.expires_at
            or not record.approval_valid
            or not record.eligible_for_publisher_governance
            or record.promotion_blocked
        ):
            raise PackageApprovalError("package_approval_not_eligible_for_attestation")
        return record, upstream | {
            request.requested_by,
            decision.decided_by,
            policy.signed_by,
        }

    async def close(self) -> None:
        await self._repository.close()

    async def _load_final(
        self, validation_id: str
    ) -> tuple[ConnectorPackageFinalValidation, frozenset[str]]:
        try:
            return await self._final_validation_source.approval_source(validation_id=validation_id)
        except PackageFinalValidationError as error:
            raise PackageApprovalError("package_approval_source_not_found") from error

    async def _reuse_request(
        self,
        request: ConnectorPackageApprovalRequest,
        actor: AuthenticatedSubject,
        fingerprint: str,
    ) -> ConnectorPackageApprovalRecord:
        if request.requested_by != actor.subject_id or request.request_fingerprint != fingerprint:
            raise PackageApprovalError("package_approval_request_idempotency_conflict")
        self._verify_request(request)
        decision = await self._repository.get_decision(request_id=request.request_id)
        return self._record(replace(request, reused=True), decision, self._clock())

    def _reuse_decision(
        self,
        request: ConnectorPackageApprovalRequest,
        decision: ConnectorPackageApprovalDecision,
        actor: AuthenticatedSubject,
        fingerprint: str,
        now: datetime,
    ) -> ConnectorPackageApprovalRecord:
        if decision.decided_by != actor.subject_id or decision.request_fingerprint != fingerprint:
            raise PackageApprovalError("package_approval_decision_idempotency_conflict")
        self._verify_decision(decision)
        return self._record(request, replace(decision, reused=True), now)

    @staticmethod
    def _record(
        request: ConnectorPackageApprovalRequest,
        decision: ConnectorPackageApprovalDecision | None,
        now: datetime,
    ) -> ConnectorPackageApprovalRecord:
        if now >= request.expires_at:
            state = PackageApprovalState.EXPIRED
        elif decision is None:
            state = PackageApprovalState.PENDING
        else:
            state = {
                PackageApprovalOutcome.APPROVE: PackageApprovalState.APPROVED,
                PackageApprovalOutcome.REJECT: PackageApprovalState.REJECTED,
                PackageApprovalOutcome.NEEDS_EVIDENCE: PackageApprovalState.NEEDS_EVIDENCE,
                PackageApprovalOutcome.DEFER: PackageApprovalState.DEFERRED,
            }[decision.outcome]
        approved = state is PackageApprovalState.APPROVED
        return ConnectorPackageApprovalRecord(
            request=request,
            decision=decision,
            state=state,
            approval_valid=approved,
            connector_approved=approved,
            connector_rejected=state is PackageApprovalState.REJECTED,
            eligible_for_publisher_governance=approved,
            promotion_blocked=not approved,
        )

    @classmethod
    def _verify_policy(cls, policy: ConnectorPackageApprovalPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != policy.canonical_digest:
            raise PackageApprovalError("package_approval_policy_integrity_failed")

    @classmethod
    def _verify_request(cls, request: ConnectorPackageApprovalRequest) -> None:
        if cls._digest(cls._request_payload(request)) != request.canonical_digest:
            raise PackageApprovalError("package_approval_request_integrity_failed")

    @classmethod
    def _verify_decision(cls, decision: ConnectorPackageApprovalDecision) -> None:
        if cls._digest(cls._decision_payload(decision)) != decision.canonical_digest:
            raise PackageApprovalError("package_approval_decision_integrity_failed")

    @classmethod
    def _request_payload(cls, request: ConnectorPackageApprovalRequest) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(request))
        for field in ("canonical_digest", "request_fingerprint", "idempotency_key", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _decision_payload(cls, decision: ConnectorPackageApprovalDecision) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(decision))
        for field in ("canonical_digest", "request_fingerprint", "idempotency_key", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _normalize(cls, value: object) -> object:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(k): cls._normalize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._normalize(v) for v in value]
        return value

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
                "ascii"
            )
        ).hexdigest()

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level
            not in {AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED}
        ):
            raise PackageApprovalError("package_approval_enterprise_human_mfa_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise PackageApprovalError("package_approval_request_not_found")

    async def _audit_request(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        request: ConnectorPackageApprovalRequest,
    ) -> None:
        await self._audit(
            actor,
            correlation_id,
            APPROVAL_CREATE_PERMISSION,
            "connector_package_approval_requested",
            request.request_id,
            request.idempotency_key,
            (("source_final_validation_id", request.source_final_validation_id),),
        )

    async def _audit_decision(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        decision: ConnectorPackageApprovalDecision,
    ) -> None:
        await self._audit(
            actor,
            correlation_id,
            APPROVAL_DECIDE_PERMISSION,
            f"connector_package_approval_{decision.outcome.value}",
            decision.request_id,
            decision.idempotency_key,
            (("decision_id", decision.decision_id), ("outcome", decision.outcome.value)),
        )

    async def _audit_read(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        request: ConnectorPackageApprovalRequest,
    ) -> None:
        await self._audit(
            actor,
            correlation_id,
            APPROVAL_READ_PERMISSION,
            "connector_package_approval_read",
            request.request_id,
            None,
            (),
        )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.package-approval",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=permission_id,
                resource_type="resource.connector.package-approval-request",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )


def build_development_package_approval_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorPackageApprovalPolicySnapshot:
    policy = ConnectorPackageApprovalPolicySnapshot(
        policy_id="connector-package-approval-policy.development",
        schema_version="atlas.connector-package-approval-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="version.1.0",
        required_final_validation_schema="atlas.connector-package-final-validation.v1",
        maximum_final_validation_age_hours=168,
        request_lifetime_minutes=1440,
        required_assurance_level=AssuranceLevel.MULTI_FACTOR,
        stage_count=1,
        quorum=1,
        permitted_outcomes=tuple(PackageApprovalOutcome),
        minimum_rationale_length=20,
        maximum_rationale_length=1000,
        signed_by="subject.package-approval-policy-owner",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return replace(
        policy,
        canonical_digest=PackageApprovalService._digest(PackageApprovalService._normalize(payload)),
    )

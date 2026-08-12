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
from atlas.modules.connectors.application.upgrade_approval_ports import (
    ConnectorUpgradeApprovalError,
    ConnectorUpgradeApprovalPolicySource,
    ConnectorUpgradeApprovalRepository,
)
from atlas.modules.connectors.application.upgrade_readiness import (
    ConnectorUpgradeReadinessService,
)
from atlas.modules.connectors.domain.upgrade_approval import (
    ConnectorUpgradeApprovalDecision,
    ConnectorUpgradeApprovalOutcome,
    ConnectorUpgradeApprovalPolicySnapshot,
    ConnectorUpgradeApprovalRecord,
    ConnectorUpgradeApprovalRequest,
    ConnectorUpgradeApprovalRevalidation,
    ConnectorUpgradeApprovalState,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

UPGRADE_APPROVAL_POLICY_SCHEMA = "atlas.connector-upgrade-approval-policy.v1"
UPGRADE_APPROVAL_REQUEST_SCHEMA = "atlas.connector-upgrade-approval-request.v1"
UPGRADE_APPROVAL_DECISION_SCHEMA = "atlas.connector-upgrade-approval-decision.v1"
UPGRADE_APPROVAL_REVALIDATION_SCHEMA = "atlas.connector-upgrade-approval-revalidation.v1"
UPGRADE_APPROVAL_CREATE_PERMISSION = "connectors.upgrade-approval-requests.create"
UPGRADE_APPROVAL_READ_PERMISSION = "connectors.upgrade-approval-requests.read"
UPGRADE_APPROVAL_DECIDE_PERMISSION = "connectors.upgrade-approval-decisions.create"
UPGRADE_APPROVAL_REVALIDATION_CREATE_PERMISSION = "connectors.upgrade-approval-revalidations.create"
UPGRADE_APPROVAL_REVALIDATION_READ_PERMISSION = "connectors.upgrade-approval-revalidations.read"
UPGRADE_APPROVAL_REVALIDATION_CHECK_IDS = (
    "connector.upgrade.revalidation.request-integrity-current",
    "connector.upgrade.revalidation.decision-integrity-current",
    "connector.upgrade.revalidation.identity-separation-current",
    "connector.upgrade.revalidation.policy-current",
    "connector.upgrade.revalidation.plan-lineage-current",
    "connector.upgrade.revalidation.expiry-current",
    "connector.upgrade.revalidation.nonexecution-boundary-intact",
)


class ConnectorUpgradeApprovalService:
    def __init__(
        self,
        *,
        repository: ConnectorUpgradeApprovalRepository,
        policy_source: ConnectorUpgradeApprovalPolicySource,
        upgrade_service: ConnectorUpgradeReadinessService,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._policy_source = policy_source
        self._upgrade_service = upgrade_service
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        record_id: str,
        candidate_receipt_id: str,
        source_plan_digest: str,
        purpose: str,
        acknowledged_request_is_not_approval_and_grants_no_execution_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorUpgradeApprovalRequest:
        self._require_enterprise_human(actor)
        if not acknowledged_request_is_not_approval_and_grants_no_execution_authority:
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_approval_acknowledgement_required"
            )
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_invalid")
        plan = await self._upgrade_service.plan(
            actor=actor,
            record_id=record_id,
            candidate_receipt_id=candidate_receipt_id,
            correlation_id=correlation_id,
        )
        now = self._clock()
        if (
            plan.canonical_digest != source_plan_digest
            or plan.source_record_id != record_id
            or plan.candidate_receipt_id != candidate_receipt_id
            or plan.plan_state != "ready_for_human_review"
            or not plan.plan_eligible
            or plan.target_configured
            or plan.blockers
            or now >= plan.expires_at
            or not plan.approval_required
            or not plan.decision_support_only
            or plan.execution_authorized
            or plan.infrastructure_mutation_performed
        ):
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_plan_not_eligible")
        policy = await self._active_policy(actor=actor, now=now)
        fingerprint = self._digest(
            {
                "plan_digest": plan.canonical_digest,
                "approval_policy_digest": policy.canonical_digest,
                "requested_by": actor.subject_id,
                "purpose": purpose,
            }
        )
        existing = await self._repository.get_by_create_key(
            requested_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return self._reuse(existing, actor, fingerprint)
        seed = self._digest(
            [
                actor.organization_id,
                self._environment_id,
                plan.canonical_digest,
                policy.canonical_digest,
            ]
        )
        request = ConnectorUpgradeApprovalRequest(
            request_id=f"connector-upgrade-approval-request.{seed[:24]}",
            schema_version=UPGRADE_APPROVAL_REQUEST_SCHEMA,
            version=1,
            source_record_id=plan.source_record_id,
            source_record_version=plan.source_record_version,
            instance_id=plan.instance_id,
            connector_id=plan.connector_id,
            plan_id=plan.plan_id,
            plan_digest=plan.canonical_digest,
            readiness_digest=plan.readiness_digest,
            current_release_version=plan.current_release_version,
            current_receipt_id=plan.current_receipt_id,
            current_receipt_digest=plan.current_receipt_digest,
            candidate_release_version=plan.candidate_release_version,
            candidate_receipt_id=plan.candidate_receipt_id,
            candidate_receipt_digest=plan.candidate_receipt_digest,
            candidate_digest=plan.candidate_digest,
            risk_level=plan.risk_level,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            requested_by=actor.subject_id,
            purpose=purpose,
            approval_policy_id=policy.policy_id,
            approval_policy_digest=policy.canonical_digest,
            approval_policy_version=policy.policy_version,
            created_at=now,
            expires_at=now + timedelta(minutes=policy.request_lifetime_minutes),
            state="pending",
            canonical_digest="0" * 64,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
        )
        request = replace(
            request,
            canonical_digest=self._digest(self._request_payload(request)),
        )
        async with self._mutation_lock:
            prior = await self._repository.get_by_plan(plan_digest=plan.canonical_digest)
            if prior is not None:
                if (
                    prior.requested_by == actor.subject_id
                    and prior.request_fingerprint == fingerprint
                ):
                    return replace(prior, reused=True)
                raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_exists")
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=UPGRADE_APPROVAL_CREATE_PERMISSION,
                result_code="connector_upgrade_approval_request_created",
                request=request,
                idempotency_key=idempotency_key,
            )
            if not await self._repository.add(request):
                raced = await self._repository.get_by_create_key(
                    requested_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise ConnectorUpgradeApprovalError(
                        "connector_upgrade_approval_request_conflict"
                    )
                self._verify_request(raced)
                return replace(raced, reused=True)
        return request

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        record_id: str,
        request_id: str,
        correlation_id: str,
    ) -> ConnectorUpgradeApprovalRequest:
        self._require_enterprise_human(actor)
        request = await self._repository.get(request_id=request_id)
        if request is None or request.source_record_id != record_id:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_not_found")
        self._verify_request(request)
        if (
            request.organization_id != actor.organization_id
            or request.environment_id != self._environment_id
        ):
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_not_found")
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=UPGRADE_APPROVAL_READ_PERMISSION,
            result_code="connector_upgrade_approval_request_read",
            request=request,
            idempotency_key=None,
        )
        return request

    async def get_record_for_plan(
        self,
        *,
        actor: AuthenticatedSubject,
        record_id: str,
        candidate_receipt_id: str,
        correlation_id: str,
    ) -> ConnectorUpgradeApprovalRecord:
        self._require_enterprise_human(actor)
        plan = await self._upgrade_service.plan(
            actor=actor,
            record_id=record_id,
            candidate_receipt_id=candidate_receipt_id,
            correlation_id=correlation_id,
        )
        request = await self._repository.get_by_plan(plan_digest=plan.canonical_digest)
        if request is None or request.source_record_id != record_id:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_not_found")
        self._require_request_scope(request, actor, record_id)
        decision = await self._repository.get_decision(request_id=request.request_id)
        if decision is not None:
            self._verify_decision(decision)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=UPGRADE_APPROVAL_READ_PERMISSION,
            result_code="connector_upgrade_approval_record_read",
            request=request,
            idempotency_key=None,
        )
        return self._record(request, decision, self._clock())

    async def decide(
        self,
        *,
        actor: AuthenticatedSubject,
        record_id: str,
        request_id: str,
        expected_request_version: int,
        expected_request_digest: str,
        outcome: ConnectorUpgradeApprovalOutcome,
        rationale: str,
        acknowledged_decision_grants_no_execution_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorUpgradeApprovalRecord:
        self._require_enterprise_human(actor)
        if not acknowledged_decision_grants_no_execution_authority:
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_approval_decision_acknowledgement_required"
            )
        rationale = rationale.strip()
        if (
            expected_request_version != 1
            or not 20 <= len(rationale) <= 1000
            or not 8 <= len(idempotency_key) <= 128
        ):
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_decision_invalid")
        request = await self._repository.get(request_id=request_id)
        if request is None:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_not_found")
        self._require_request_scope(request, actor, record_id)
        if actor.subject_id == request.requested_by:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_separation_required")
        now = self._clock()
        if (
            request.version != expected_request_version
            or request.canonical_digest != expected_request_digest
        ):
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_stale")
        if now >= request.expires_at:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_expired")
        policy = await self._active_policy(actor=actor, now=now)
        if (
            policy.policy_id != request.approval_policy_id
            or policy.policy_version != request.approval_policy_version
            or policy.canonical_digest != request.approval_policy_digest
        ):
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_policy_changed")
        plan = await self._upgrade_service.plan(
            actor=actor,
            record_id=request.source_record_id,
            candidate_receipt_id=request.candidate_receipt_id,
            correlation_id=correlation_id,
        )
        if (
            plan.plan_id != request.plan_id
            or plan.canonical_digest != request.plan_digest
            or plan.readiness_digest != request.readiness_digest
            or plan.current_receipt_id != request.current_receipt_id
            or plan.current_receipt_digest != request.current_receipt_digest
            or plan.candidate_receipt_digest != request.candidate_receipt_digest
            or plan.candidate_digest != request.candidate_digest
            or not plan.plan_eligible
            or plan.blockers
            or now >= plan.expires_at
        ):
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_plan_drifted")
        fingerprint = self._digest(
            {
                "request_digest": request.canonical_digest,
                "outcome": outcome.value,
                "decided_by": actor.subject_id,
                "rationale": rationale,
            }
        )
        replay = await self._repository.get_decision_by_key(
            decided_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if replay is not None:
            return self._reuse_decision(request, replay, actor, fingerprint, now)
        seed = self._digest([request.canonical_digest, actor.subject_id, outcome.value])
        decision = ConnectorUpgradeApprovalDecision(
            decision_id=f"connector-upgrade-approval-decision.{seed[:24]}",
            schema_version=UPGRADE_APPROVAL_DECISION_SCHEMA,
            version=1,
            request_id=request.request_id,
            request_version=request.version,
            request_digest=request.canonical_digest,
            plan_id=request.plan_id,
            plan_digest=request.plan_digest,
            outcome=outcome,
            decided_by=actor.subject_id,
            rationale=rationale,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            approval_policy_id=request.approval_policy_id,
            approval_policy_digest=request.approval_policy_digest,
            decided_at=now,
            canonical_digest="0" * 64,
            decision_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
        )
        decision = replace(
            decision,
            canonical_digest=self._digest(self._decision_payload(decision)),
        )
        async with self._mutation_lock:
            prior = await self._repository.get_decision(request_id=request.request_id)
            if prior is not None:
                return self._reuse_decision(request, prior, actor, fingerprint, now)
            await self._audit_decision(
                actor=actor,
                correlation_id=correlation_id,
                request=request,
                decision=decision,
            )
            if not await self._repository.add_decision(decision):
                raced = await self._repository.get_decision(request_id=request.request_id)
                if raced is None:
                    raise ConnectorUpgradeApprovalError(
                        "connector_upgrade_approval_decision_conflict"
                    )
                return self._reuse_decision(request, raced, actor, fingerprint, now)
        return self._record(request, decision, now)

    async def revalidate(
        self,
        *,
        actor: AuthenticatedSubject,
        record_id: str,
        request_id: str,
        expected_request_digest: str,
        expected_decision_digest: str,
        purpose: str,
        acknowledged_revalidation_grants_no_handoff_or_execution_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorUpgradeApprovalRevalidation:
        self._require_enterprise_human(actor)
        if not acknowledged_revalidation_grants_no_handoff_or_execution_authority:
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_approval_revalidation_acknowledgement_required"
            )
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_revalidation_invalid")
        request = await self._repository.get(request_id=request_id)
        if request is None:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_not_found")
        self._require_request_scope(request, actor, record_id)
        decision = await self._repository.get_decision(request_id=request.request_id)
        if decision is None:
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_approval_revalidation_approval_required"
            )
        self._verify_decision(decision)
        if (
            decision.outcome is not ConnectorUpgradeApprovalOutcome.APPROVE
            or request.canonical_digest != expected_request_digest
            or decision.canonical_digest != expected_decision_digest
        ):
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_approval_revalidation_approval_not_current"
            )
        if actor.subject_id in {request.requested_by, decision.decided_by}:
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_approval_revalidation_separation_required"
            )
        now = self._clock()
        if now >= request.expires_at:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_expired")
        policy = await self._active_policy(actor=actor, now=now)
        if (
            policy.policy_id != request.approval_policy_id
            or policy.policy_version != request.approval_policy_version
            or policy.canonical_digest != request.approval_policy_digest
            or decision.approval_policy_id != request.approval_policy_id
            or decision.approval_policy_digest != request.approval_policy_digest
        ):
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_policy_changed")
        plan = await self._upgrade_service.plan(
            actor=actor,
            record_id=request.source_record_id,
            candidate_receipt_id=request.candidate_receipt_id,
            correlation_id=correlation_id,
        )
        if (
            plan.source_record_id != request.source_record_id
            or plan.source_record_version != request.source_record_version
            or plan.instance_id != request.instance_id
            or plan.connector_id != request.connector_id
            or plan.plan_id != request.plan_id
            or plan.canonical_digest != request.plan_digest
            or plan.readiness_digest != request.readiness_digest
            or plan.current_receipt_id != request.current_receipt_id
            or plan.current_receipt_digest != request.current_receipt_digest
            or plan.candidate_receipt_id != request.candidate_receipt_id
            or plan.candidate_receipt_digest != request.candidate_receipt_digest
            or plan.candidate_digest != request.candidate_digest
            or plan.target_configured
            or not plan.plan_eligible
            or plan.blockers
            or now >= plan.expires_at
            or plan.execution_authorized
            or plan.infrastructure_mutation_performed
        ):
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_approval_revalidation_plan_drifted"
            )
        valid_until = min(request.expires_at, plan.expires_at, policy.expires_at)
        if valid_until <= now:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_revalidation_expired")
        fingerprint = self._digest(
            {
                "request_digest": request.canonical_digest,
                "decision_digest": decision.canonical_digest,
                "plan_digest": plan.canonical_digest,
                "policy_digest": policy.canonical_digest,
                "revalidated_by": actor.subject_id,
                "purpose": purpose,
            }
        )
        replay = await self._repository.get_revalidation_by_key(
            revalidated_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if replay is not None:
            return self._reuse_revalidation(replay, actor, request, decision, fingerprint)
        seed = self._digest(
            [request.canonical_digest, decision.canonical_digest, actor.subject_id, idempotency_key]
        )
        revalidation = ConnectorUpgradeApprovalRevalidation(
            revalidation_id=f"connector-upgrade-approval-revalidation.{seed[:24]}",
            schema_version=UPGRADE_APPROVAL_REVALIDATION_SCHEMA,
            version=1,
            source_record_id=request.source_record_id,
            source_record_version=request.source_record_version,
            instance_id=request.instance_id,
            connector_id=request.connector_id,
            request_id=request.request_id,
            request_version=request.version,
            request_digest=request.canonical_digest,
            decision_id=decision.decision_id,
            decision_version=decision.version,
            decision_digest=decision.canonical_digest,
            plan_id=request.plan_id,
            plan_digest=request.plan_digest,
            readiness_digest=request.readiness_digest,
            current_receipt_id=request.current_receipt_id,
            current_receipt_digest=request.current_receipt_digest,
            candidate_receipt_id=request.candidate_receipt_id,
            candidate_receipt_digest=request.candidate_receipt_digest,
            approval_policy_id=policy.policy_id,
            approval_policy_version=policy.policy_version,
            approval_policy_digest=policy.canonical_digest,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            requester_id=request.requested_by,
            approver_id=decision.decided_by,
            revalidated_by=actor.subject_id,
            purpose=purpose,
            check_ids=UPGRADE_APPROVAL_REVALIDATION_CHECK_IDS,
            revalidated_at=now,
            valid_until=valid_until,
            canonical_digest="0" * 64,
            revalidation_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
        )
        revalidation = replace(
            revalidation,
            canonical_digest=self._digest(self._revalidation_payload(revalidation)),
        )
        async with self._mutation_lock:
            await self._audit_revalidation(
                actor=actor,
                correlation_id=correlation_id,
                revalidation=revalidation,
                result_code="connector_upgrade_approval_revalidated",
                permission_id=UPGRADE_APPROVAL_REVALIDATION_CREATE_PERMISSION,
                idempotency_key=idempotency_key,
            )
            if not await self._repository.add_revalidation(revalidation):
                raced = await self._repository.get_revalidation_by_key(
                    revalidated_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None:
                    raise ConnectorUpgradeApprovalError(
                        "connector_upgrade_approval_revalidation_conflict"
                    )
                return self._reuse_revalidation(raced, actor, request, decision, fingerprint)
        return revalidation

    async def get_latest_revalidation(
        self,
        *,
        actor: AuthenticatedSubject,
        record_id: str,
        request_id: str,
        correlation_id: str,
    ) -> ConnectorUpgradeApprovalRevalidation:
        self._require_enterprise_human(actor)
        request = await self._repository.get(request_id=request_id)
        if request is None:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_not_found")
        self._require_request_scope(request, actor, record_id)
        revalidation = await self._repository.get_latest_revalidation(request_id=request_id)
        if revalidation is None:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_revalidation_not_found")
        self._verify_revalidation(revalidation)
        if (
            revalidation.request_id != request.request_id
            or revalidation.request_digest != request.canonical_digest
            or revalidation.organization_id != actor.organization_id
            or revalidation.environment_id != self._environment_id
        ):
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_revalidation_not_found")
        await self._audit_revalidation(
            actor=actor,
            correlation_id=correlation_id,
            revalidation=revalidation,
            result_code="connector_upgrade_approval_revalidation_read",
            permission_id=UPGRADE_APPROVAL_REVALIDATION_READ_PERMISSION,
            idempotency_key=None,
        )
        return revalidation

    async def close(self) -> None:
        await self._repository.close()

    async def _active_policy(
        self, *, actor: AuthenticatedSubject, now: datetime
    ) -> ConnectorUpgradeApprovalPolicySnapshot:
        policies = await self._policy_source.list_scope(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        active: list[ConnectorUpgradeApprovalPolicySnapshot] = []
        for policy in policies:
            self._verify_policy(policy)
            if policy.issued_at <= now < policy.expires_at:
                active.append(policy)
        if len(active) != 1:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_policy_unavailable")
        policy = active[0]
        if not self._assurance_satisfies(actor.assurance_level, policy.required_assurance_level):
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_assurance_insufficient")
        return policy

    def _reuse(
        self,
        request: ConnectorUpgradeApprovalRequest,
        actor: AuthenticatedSubject,
        fingerprint: str,
    ) -> ConnectorUpgradeApprovalRequest:
        if request.requested_by != actor.subject_id or request.request_fingerprint != fingerprint:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_idempotency_conflict")
        self._verify_request(request)
        return replace(request, reused=True)

    def _require_request_scope(
        self,
        request: ConnectorUpgradeApprovalRequest,
        actor: AuthenticatedSubject,
        record_id: str,
    ) -> None:
        self._verify_request(request)
        if (
            request.source_record_id != record_id
            or request.organization_id != actor.organization_id
            or request.environment_id != self._environment_id
        ):
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_not_found")

    def _reuse_decision(
        self,
        request: ConnectorUpgradeApprovalRequest,
        decision: ConnectorUpgradeApprovalDecision,
        actor: AuthenticatedSubject,
        fingerprint: str,
        now: datetime,
    ) -> ConnectorUpgradeApprovalRecord:
        self._verify_decision(decision)
        if (
            decision.request_id != request.request_id
            or decision.decided_by != actor.subject_id
            or decision.decision_fingerprint != fingerprint
        ):
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_decision_conflict")
        return self._record(request, replace(decision, reused=True), now)

    def _reuse_revalidation(
        self,
        revalidation: ConnectorUpgradeApprovalRevalidation,
        actor: AuthenticatedSubject,
        request: ConnectorUpgradeApprovalRequest,
        decision: ConnectorUpgradeApprovalDecision,
        fingerprint: str,
    ) -> ConnectorUpgradeApprovalRevalidation:
        self._verify_revalidation(revalidation)
        if (
            revalidation.revalidated_by != actor.subject_id
            or revalidation.request_id != request.request_id
            or revalidation.decision_id != decision.decision_id
            or revalidation.revalidation_fingerprint != fingerprint
        ):
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_revalidation_conflict")
        return replace(revalidation, reused=True)

    @staticmethod
    def _record(
        request: ConnectorUpgradeApprovalRequest,
        decision: ConnectorUpgradeApprovalDecision | None,
        now: datetime,
    ) -> ConnectorUpgradeApprovalRecord:
        if now >= request.expires_at:
            state = ConnectorUpgradeApprovalState.EXPIRED
        elif decision is None:
            state = ConnectorUpgradeApprovalState.PENDING
        else:
            state = {
                ConnectorUpgradeApprovalOutcome.APPROVE: ConnectorUpgradeApprovalState.APPROVED,
                ConnectorUpgradeApprovalOutcome.REJECT: ConnectorUpgradeApprovalState.REJECTED,
                ConnectorUpgradeApprovalOutcome.NEEDS_EVIDENCE: (
                    ConnectorUpgradeApprovalState.NEEDS_EVIDENCE
                ),
                ConnectorUpgradeApprovalOutcome.DEFER: ConnectorUpgradeApprovalState.DEFERRED,
            }[decision.outcome]
        approval_valid = state is ConnectorUpgradeApprovalState.APPROVED
        return ConnectorUpgradeApprovalRecord(
            request=request,
            decision=decision,
            state=state,
            approval_valid=approval_valid,
            approval_granted=approval_valid,
            decision_recorded=decision is not None,
        )

    @classmethod
    def _verify_policy(cls, policy: ConnectorUpgradeApprovalPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != policy.canonical_digest:
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_approval_policy_integrity_failed"
            )

    @classmethod
    def _verify_request(cls, request: ConnectorUpgradeApprovalRequest) -> None:
        if cls._digest(cls._request_payload(request)) != request.canonical_digest:
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_approval_request_integrity_failed"
            )

    @classmethod
    def _verify_decision(cls, decision: ConnectorUpgradeApprovalDecision) -> None:
        if cls._digest(cls._decision_payload(decision)) != decision.canonical_digest:
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_approval_decision_integrity_failed"
            )

    @classmethod
    def _verify_revalidation(cls, revalidation: ConnectorUpgradeApprovalRevalidation) -> None:
        if cls._digest(cls._revalidation_payload(revalidation)) != revalidation.canonical_digest:
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_approval_revalidation_integrity_failed"
            )

    @classmethod
    def _request_payload(cls, request: ConnectorUpgradeApprovalRequest) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(request))
        for field in ("canonical_digest", "request_fingerprint", "idempotency_key", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _decision_payload(cls, decision: ConnectorUpgradeApprovalDecision) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(decision))
        for field in ("canonical_digest", "decision_fingerprint", "idempotency_key", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _revalidation_payload(
        cls, revalidation: ConnectorUpgradeApprovalRevalidation
    ) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(revalidation))
        for field in (
            "canonical_digest",
            "revalidation_fingerprint",
            "idempotency_key",
            "reused",
        ):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    async def _audit_revalidation(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        revalidation: ConnectorUpgradeApprovalRevalidation,
        result_code: str,
        permission_id: str,
        idempotency_key: str | None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.upgrade-approval-revalidation",
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
                resource_type="resource.connector.upgrade-approval-request",
                scope_reference=revalidation.request_id,
                decision_id=revalidation.revalidation_id,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    ("plan_id", revalidation.plan_id),
                    ("handoff_ready", "false"),
                ),
            )
        )

    async def _audit_decision(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        request: ConnectorUpgradeApprovalRequest,
        decision: ConnectorUpgradeApprovalDecision,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.upgrade-approval-decision",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=UPGRADE_APPROVAL_DECIDE_PERMISSION,
                resource_type="resource.connector.upgrade-approval-request",
                scope_reference=request.request_id,
                decision_id=decision.decision_id,
                outcome="succeeded",
                result_code=f"connector_upgrade_approval_{decision.outcome.value}",
                idempotency_key=decision.idempotency_key,
                target_metadata=(
                    ("plan_id", request.plan_id),
                    ("outcome", decision.outcome.value),
                ),
            )
        )

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        request: ConnectorUpgradeApprovalRequest,
        idempotency_key: str | None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.upgrade-approval-request",
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
                resource_type="resource.connector.upgrade-approval-request",
                scope_reference=request.request_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    ("plan_id", request.plan_id),
                    ("candidate_receipt_id", request.candidate_receipt_id),
                ),
            )
        )

    @staticmethod
    def _assurance_satisfies(actual: AssuranceLevel, required: AssuranceLevel) -> bool:
        order = {
            AssuranceLevel.DEVELOPMENT: 0,
            AssuranceLevel.SINGLE_FACTOR: 1,
            AssuranceLevel.MULTI_FACTOR: 2,
            AssuranceLevel.HARDWARE_BACKED: 3,
        }
        return order[actual] >= order[required]

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level
            not in {AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED}
        ):
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_approval_enterprise_human_mfa_required"
            )

    @classmethod
    def _normalize(cls, value: object) -> object:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): cls._normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._normalize(item) for item in value]
        return value

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
                "ascii"
            )
        ).hexdigest()


def build_development_connector_upgrade_approval_policy(
    *,
    organization_id: str,
    environment_id: str,
    issued_at: datetime,
    expires_at: datetime,
) -> ConnectorUpgradeApprovalPolicySnapshot:
    policy = ConnectorUpgradeApprovalPolicySnapshot(
        policy_id="connector-upgrade-approval-policy.development",
        schema_version=UPGRADE_APPROVAL_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="version.1.0",
        request_lifetime_minutes=120,
        required_assurance_level=AssuranceLevel.MULTI_FACTOR,
        signed_by="subject.security-architecture",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return replace(
        policy,
        canonical_digest=ConnectorUpgradeApprovalService._digest(
            ConnectorUpgradeApprovalService._normalize(payload)
        ),
    )

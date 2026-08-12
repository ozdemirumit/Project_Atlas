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
    ConnectorUpgradeAuditReadinessSource,
    ConnectorUpgradeItsmChangeEvidenceSource,
    ConnectorUpgradeMaintenanceWindowEvidenceSource,
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
    ConnectorUpgradeAuditReadinessEvidence,
    ConnectorUpgradeChangeContextDraft,
    ConnectorUpgradeEvidenceReceipt,
    ConnectorUpgradeHandoffReadinessAssessment,
    ConnectorUpgradeItsmChangeEvidence,
    ConnectorUpgradeMaintenanceWindowEvidence,
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
UPGRADE_HANDOFF_READINESS_SCHEMA = "atlas.connector-upgrade-handoff-readiness.v5"
UPGRADE_HANDOFF_READINESS_READ_PERMISSION = "connectors.upgrade-handoff-readiness.read"
UPGRADE_CHANGE_CONTEXT_SCHEMA = "atlas.connector-upgrade-change-context-draft.v1"
UPGRADE_CHANGE_CONTEXT_CREATE_PERMISSION = "connectors.upgrade-change-context-drafts.create"
UPGRADE_CHANGE_CONTEXT_READ_PERMISSION = "connectors.upgrade-change-context-drafts.read"
UPGRADE_AUDIT_READINESS_EVIDENCE_SCHEMA = "atlas.connector-upgrade-audit-readiness-evidence.v1"
UPGRADE_ITSM_CHANGE_EVIDENCE_SCHEMA = "atlas.connector-upgrade-itsm-change-evidence.v1"
UPGRADE_MAINTENANCE_WINDOW_EVIDENCE_SCHEMA = (
    "atlas.connector-upgrade-maintenance-window-evidence.v1"
)
UPGRADE_EVIDENCE_RECEIPT_SCHEMA = "atlas.connector-upgrade-evidence-receipt.v1"
UPGRADE_EVIDENCE_RECEIPT_CREATE_PERMISSION = "connectors.upgrade-evidence-receipts.create"
UPGRADE_HANDOFF_APPLICABILITY_POLICY_ID = "connector-upgrade-handoff-evidence-applicability.default"
UPGRADE_HANDOFF_APPLICABILITY_POLICY_VERSION = "v2026.08.12.1"
UPGRADE_HANDOFF_CURRENT_CHECK_IDS = (
    "connector.upgrade.handoff.approval-current",
    "connector.upgrade.handoff.revalidation-current",
    "connector.upgrade.handoff.identity-separation-current",
    "connector.upgrade.handoff.policy-current",
    "connector.upgrade.handoff.plan-lineage-current",
    "connector.upgrade.handoff.prior-execution-absent",
)
UPGRADE_HANDOFF_TARGET_CHECK_IDS = (
    "connector.upgrade.handoff.target-binding-current",
    "connector.upgrade.handoff.service-impact-evidence-current",
    "connector.upgrade.handoff.runtime-health-evidence-current",
)
UPGRADE_HANDOFF_CHANGE_CHECK_IDS = (
    "connector.upgrade.handoff.itsm-change-current",
    "connector.upgrade.handoff.maintenance-window-current",
)
UPGRADE_HANDOFF_AUDIT_CHECK_ID = "connector.upgrade.handoff.audit-readiness-evidence-current"
UPGRADE_HANDOFF_ITSM_CHECK_ID = "connector.upgrade.handoff.itsm-change-current"
UPGRADE_HANDOFF_WINDOW_CHECK_ID = "connector.upgrade.handoff.maintenance-window-current"
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
        audit_readiness_source: ConnectorUpgradeAuditReadinessSource | None = None,
        itsm_change_evidence_source: ConnectorUpgradeItsmChangeEvidenceSource | None = None,
        maintenance_window_evidence_source: (
            ConnectorUpgradeMaintenanceWindowEvidenceSource | None
        ) = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._policy_source = policy_source
        self._upgrade_service = upgrade_service
        self._audit_sink = audit_sink
        self._audit_readiness_source = audit_readiness_source
        self._itsm_change_evidence_source = itsm_change_evidence_source
        self._maintenance_window_evidence_source = maintenance_window_evidence_source
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

    async def assess_handoff_readiness(
        self,
        *,
        actor: AuthenticatedSubject,
        record_id: str,
        request_id: str,
        correlation_id: str,
    ) -> ConnectorUpgradeHandoffReadinessAssessment:
        self._require_enterprise_human(actor)
        request = await self._repository.get(request_id=request_id)
        if request is None:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_not_found")
        self._require_request_scope(request, actor, record_id)
        decision = await self._repository.get_decision(request_id=request.request_id)
        revalidation = await self._repository.get_latest_revalidation(request_id=request.request_id)
        if decision is None or revalidation is None:
            raise ConnectorUpgradeApprovalError("connector_upgrade_handoff_readiness_not_found")
        self._verify_decision(decision)
        self._verify_revalidation(revalidation)
        now = self._clock()
        if (
            decision.outcome is not ConnectorUpgradeApprovalOutcome.APPROVE
            or revalidation.request_digest != request.canonical_digest
            or revalidation.decision_digest != decision.canonical_digest
            or revalidation.plan_digest != request.plan_digest
            or revalidation.organization_id != actor.organization_id
            or revalidation.environment_id != self._environment_id
            or now >= revalidation.valid_until
        ):
            raise ConnectorUpgradeApprovalError("connector_upgrade_handoff_readiness_not_current")
        policy = await self._active_policy(actor=actor, now=now)
        plan = await self._upgrade_service.plan(
            actor=actor,
            record_id=request.source_record_id,
            candidate_receipt_id=request.candidate_receipt_id,
            correlation_id=correlation_id,
        )
        if (
            policy.canonical_digest != revalidation.approval_policy_digest
            or plan.canonical_digest != revalidation.plan_digest
            or plan.readiness_digest != revalidation.readiness_digest
            or plan.source_record_version != revalidation.source_record_version
            or now >= plan.expires_at
        ):
            raise ConnectorUpgradeApprovalError("connector_upgrade_handoff_readiness_not_current")
        audit_evidence = (
            await self._audit_readiness_source.get_current(
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
                request_id=request.request_id,
            )
            if self._audit_readiness_source is not None
            else None
        )
        if audit_evidence is not None:
            self._verify_audit_readiness_evidence(audit_evidence)
        current_audit_evidence = (
            audit_evidence
            if audit_evidence is not None
            and audit_evidence.organization_id == actor.organization_id
            and audit_evidence.environment_id == self._environment_id
            and audit_evidence.request_id == request.request_id
            and audit_evidence.request_digest == request.canonical_digest
            and audit_evidence.revalidation_id == revalidation.revalidation_id
            and audit_evidence.revalidation_digest == revalidation.canonical_digest
            and audit_evidence.verified_at <= now < audit_evidence.valid_until
            else None
        )
        itsm_evidence = (
            await self._itsm_change_evidence_source.get_current(
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
                request_id=request.request_id,
            )
            if self._itsm_change_evidence_source is not None
            else None
        )
        if itsm_evidence is not None:
            self._verify_itsm_change_evidence(itsm_evidence)
        current_itsm_evidence = (
            itsm_evidence
            if itsm_evidence is not None
            and itsm_evidence.organization_id == actor.organization_id
            and itsm_evidence.environment_id == self._environment_id
            and itsm_evidence.request_id == request.request_id
            and itsm_evidence.request_digest == request.canonical_digest
            and itsm_evidence.revalidation_id == revalidation.revalidation_id
            and itsm_evidence.revalidation_digest == revalidation.canonical_digest
            and itsm_evidence.plan_id == plan.plan_id
            and itsm_evidence.plan_digest == plan.canonical_digest
            and itsm_evidence.observed_at <= now < itsm_evidence.valid_until
            else None
        )
        window_evidence = (
            await self._maintenance_window_evidence_source.get_current(
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
                request_id=request.request_id,
            )
            if self._maintenance_window_evidence_source is not None
            else None
        )
        if window_evidence is not None:
            self._verify_maintenance_window_evidence(window_evidence)
        current_window_evidence = (
            window_evidence
            if window_evidence is not None
            and current_itsm_evidence is not None
            and window_evidence.organization_id == actor.organization_id
            and window_evidence.environment_id == self._environment_id
            and window_evidence.request_id == request.request_id
            and window_evidence.request_digest == request.canonical_digest
            and window_evidence.revalidation_id == revalidation.revalidation_id
            and window_evidence.revalidation_digest == revalidation.canonical_digest
            and window_evidence.plan_id == plan.plan_id
            and window_evidence.plan_digest == plan.canonical_digest
            and window_evidence.itsm_change_evidence_id == current_itsm_evidence.evidence_id
            and window_evidence.itsm_change_evidence_digest
            == current_itsm_evidence.canonical_digest
            and window_evidence.external_record_version
            == current_itsm_evidence.external_record_version
            and window_evidence.observed_at <= now < window_evidence.valid_until
            and window_evidence.approved_start <= now < window_evidence.approved_end
            else None
        )
        applicability_policy = {
            "policy_id": UPGRADE_HANDOFF_APPLICABILITY_POLICY_ID,
            "policy_version": UPGRADE_HANDOFF_APPLICABILITY_POLICY_VERSION,
            "target_checks_required_when_target_configured": UPGRADE_HANDOFF_TARGET_CHECK_IDS,
            "always_required_change_check_ids": UPGRADE_HANDOFF_CHANGE_CHECK_IDS,
            "always_required_check_ids": (UPGRADE_HANDOFF_AUDIT_CHECK_ID,),
        }
        applicability_policy_digest = self._digest(applicability_policy)
        contextual_required = UPGRADE_HANDOFF_TARGET_CHECK_IDS if plan.target_configured else ()
        contextual_not_applicable = (
            () if plan.target_configured else UPGRADE_HANDOFF_TARGET_CHECK_IDS
        )
        required_check_ids = (
            *UPGRADE_HANDOFF_CURRENT_CHECK_IDS,
            *contextual_required,
            *UPGRADE_HANDOFF_CHANGE_CHECK_IDS,
            UPGRADE_HANDOFF_AUDIT_CHECK_ID,
        )
        not_applicable_check_ids = contextual_not_applicable
        satisfied_check_ids = (
            *UPGRADE_HANDOFF_CURRENT_CHECK_IDS,
            *((UPGRADE_HANDOFF_ITSM_CHECK_ID,) if current_itsm_evidence is not None else ()),
            *((UPGRADE_HANDOFF_WINDOW_CHECK_ID,) if current_window_evidence is not None else ()),
            *((UPGRADE_HANDOFF_AUDIT_CHECK_ID,) if current_audit_evidence is not None else ()),
        )
        missing_evidence_ids = (
            *contextual_required,
            *((UPGRADE_HANDOFF_ITSM_CHECK_ID,) if current_itsm_evidence is None else ()),
            *((UPGRADE_HANDOFF_WINDOW_CHECK_ID,) if current_window_evidence is None else ()),
            *((UPGRADE_HANDOFF_AUDIT_CHECK_ID,) if current_audit_evidence is None else ()),
        )
        blockers = tuple(
            f"connector.upgrade.handoff.blocked.{check_id.removeprefix('connector.upgrade.handoff.').removesuffix('-current')}-missing"
            for check_id in missing_evidence_ids
        )
        payload: dict[str, object] = {
            "schema_version": UPGRADE_HANDOFF_READINESS_SCHEMA,
            "source_record_id": request.source_record_id,
            "source_record_version": request.source_record_version,
            "request_digest": request.canonical_digest,
            "decision_digest": decision.canonical_digest,
            "revalidation_digest": revalidation.canonical_digest,
            "plan_digest": plan.canonical_digest,
            "assessed_by": actor.subject_id,
            "applicability_policy_id": UPGRADE_HANDOFF_APPLICABILITY_POLICY_ID,
            "applicability_policy_version": UPGRADE_HANDOFF_APPLICABILITY_POLICY_VERSION,
            "applicability_policy_digest": applicability_policy_digest,
            "audit_readiness_evidence_id": (
                current_audit_evidence.evidence_id if current_audit_evidence else None
            ),
            "audit_readiness_evidence_digest": (
                current_audit_evidence.canonical_digest if current_audit_evidence else None
            ),
            "itsm_change_evidence_id": (
                current_itsm_evidence.evidence_id if current_itsm_evidence else None
            ),
            "itsm_change_evidence_digest": (
                current_itsm_evidence.canonical_digest if current_itsm_evidence else None
            ),
            "maintenance_window_evidence_id": (
                current_window_evidence.evidence_id if current_window_evidence else None
            ),
            "maintenance_window_evidence_digest": (
                current_window_evidence.canonical_digest if current_window_evidence else None
            ),
            "required_check_ids": required_check_ids,
            "satisfied_check_ids": satisfied_check_ids,
            "not_applicable_check_ids": not_applicable_check_ids,
            "blocker_ids": blockers,
        }
        digest = self._digest(payload)
        assessment = ConnectorUpgradeHandoffReadinessAssessment(
            assessment_id=f"connector-upgrade-handoff-readiness.{digest[:24]}",
            schema_version=UPGRADE_HANDOFF_READINESS_SCHEMA,
            source_record_id=request.source_record_id,
            source_record_version=request.source_record_version,
            instance_id=request.instance_id,
            connector_id=request.connector_id,
            request_id=request.request_id,
            request_digest=request.canonical_digest,
            decision_id=decision.decision_id,
            decision_digest=decision.canonical_digest,
            revalidation_id=revalidation.revalidation_id,
            revalidation_digest=revalidation.canonical_digest,
            plan_id=plan.plan_id,
            plan_digest=plan.canonical_digest,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            assessed_by=actor.subject_id,
            applicability_policy_id=UPGRADE_HANDOFF_APPLICABILITY_POLICY_ID,
            applicability_policy_version=UPGRADE_HANDOFF_APPLICABILITY_POLICY_VERSION,
            applicability_policy_digest=applicability_policy_digest,
            audit_readiness_evidence_id=(
                current_audit_evidence.evidence_id if current_audit_evidence else None
            ),
            audit_readiness_evidence_digest=(
                current_audit_evidence.canonical_digest if current_audit_evidence else None
            ),
            itsm_change_evidence_id=(
                current_itsm_evidence.evidence_id if current_itsm_evidence else None
            ),
            itsm_change_evidence_digest=(
                current_itsm_evidence.canonical_digest if current_itsm_evidence else None
            ),
            maintenance_window_evidence_id=(
                current_window_evidence.evidence_id if current_window_evidence else None
            ),
            maintenance_window_evidence_digest=(
                current_window_evidence.canonical_digest if current_window_evidence else None
            ),
            required_check_ids=required_check_ids,
            satisfied_check_ids=cast(tuple[str, ...], payload["satisfied_check_ids"]),
            not_applicable_check_ids=not_applicable_check_ids,
            blocker_ids=blockers,
            assessed_at=now,
            evidence_valid_until=min(
                revalidation.valid_until,
                plan.expires_at,
                policy.expires_at,
                *(
                    (current_audit_evidence.valid_until,)
                    if current_audit_evidence is not None
                    else ()
                ),
                *(
                    (current_itsm_evidence.valid_until,)
                    if current_itsm_evidence is not None
                    else ()
                ),
                *(
                    (current_window_evidence.valid_until,)
                    if current_window_evidence is not None
                    else ()
                ),
            ),
            canonical_digest=digest,
            assessment_state="evidence_complete" if not blockers else "blocked",
            audit_readiness_evidence_current=current_audit_evidence is not None,
            itsm_change_evidence_current=current_itsm_evidence is not None,
            maintenance_window_evidence_current=current_window_evidence is not None,
        )
        await self._audit_revalidation(
            actor=actor,
            correlation_id=correlation_id,
            revalidation=revalidation,
            result_code=(
                "connector_upgrade_handoff_evidence_complete"
                if assessment.assessment_state == "evidence_complete"
                else "connector_upgrade_handoff_readiness_blocked"
            ),
            permission_id=UPGRADE_HANDOFF_READINESS_READ_PERMISSION,
            idempotency_key=None,
        )
        return assessment

    async def create_evidence_receipt(
        self,
        *,
        actor: AuthenticatedSubject,
        record_id: str,
        request_id: str,
        expected_readiness_digest: str,
        acknowledged_receipt_is_non_executable_and_grants_no_handoff_authority: bool,
        correlation_id: str,
    ) -> ConnectorUpgradeEvidenceReceipt:
        self._require_enterprise_human(actor)
        if not acknowledged_receipt_is_non_executable_and_grants_no_handoff_authority:
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_evidence_receipt_confirmation_required"
            )
        readiness = await self.assess_handoff_readiness(
            actor=actor,
            record_id=record_id,
            request_id=request_id,
            correlation_id=correlation_id,
        )
        now = self._clock()
        evidence_bindings = (
            readiness.audit_readiness_evidence_id,
            readiness.audit_readiness_evidence_digest,
            readiness.itsm_change_evidence_id,
            readiness.itsm_change_evidence_digest,
            readiness.maintenance_window_evidence_id,
            readiness.maintenance_window_evidence_digest,
        )
        if (
            readiness.assessment_state != "evidence_complete"
            or readiness.blocker_ids
            or readiness.canonical_digest != expected_readiness_digest
            or now >= readiness.evidence_valid_until
            or any(value is None for value in evidence_bindings)
        ):
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_evidence_receipt_readiness_not_current"
            )
        revalidation = await self._repository.get_latest_revalidation(request_id=request_id)
        if revalidation is None or revalidation.revalidation_id != readiness.revalidation_id:
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_evidence_receipt_readiness_not_current"
            )
        payload: dict[str, object] = {
            "schema_version": UPGRADE_EVIDENCE_RECEIPT_SCHEMA,
            "version": 1,
            "assessment": (readiness.assessment_id, readiness.canonical_digest),
            "request": (readiness.request_id, readiness.request_digest),
            "decision": (readiness.decision_id, readiness.decision_digest),
            "revalidation": (readiness.revalidation_id, readiness.revalidation_digest),
            "plan": (readiness.plan_id, readiness.plan_digest),
            "scope": (readiness.organization_id, readiness.environment_id),
            "created_by": actor.subject_id,
            "evidence": evidence_bindings,
            "required_check_ids": readiness.required_check_ids,
            "satisfied_check_ids": readiness.satisfied_check_ids,
            "not_applicable_check_ids": readiness.not_applicable_check_ids,
            "created_at": revalidation.revalidated_at.isoformat(),
            "valid_until": readiness.evidence_valid_until.isoformat(),
            "evidence_receipt_only": True,
            "runtime_acceptable": False,
            "approval_consumed": False,
            "handoff_ready": False,
            "handoff_artifact_issued": False,
            "target_contacted": False,
            "package_rebound": False,
            "configuration_changed": False,
            "execution_authorized": False,
            "infrastructure_mutation_performed": False,
        }
        digest = self._digest(payload)
        receipt = ConnectorUpgradeEvidenceReceipt(
            receipt_id=f"connector-upgrade-evidence-receipt.{digest[:24]}",
            schema_version=UPGRADE_EVIDENCE_RECEIPT_SCHEMA,
            version=1,
            assessment_id=readiness.assessment_id,
            assessment_digest=readiness.canonical_digest,
            request_id=readiness.request_id,
            request_digest=readiness.request_digest,
            decision_id=readiness.decision_id,
            decision_digest=readiness.decision_digest,
            revalidation_id=readiness.revalidation_id,
            revalidation_digest=readiness.revalidation_digest,
            plan_id=readiness.plan_id,
            plan_digest=readiness.plan_digest,
            organization_id=readiness.organization_id,
            environment_id=readiness.environment_id,
            created_by=actor.subject_id,
            audit_readiness_evidence_id=cast(str, readiness.audit_readiness_evidence_id),
            audit_readiness_evidence_digest=cast(str, readiness.audit_readiness_evidence_digest),
            itsm_change_evidence_id=cast(str, readiness.itsm_change_evidence_id),
            itsm_change_evidence_digest=cast(str, readiness.itsm_change_evidence_digest),
            maintenance_window_evidence_id=cast(str, readiness.maintenance_window_evidence_id),
            maintenance_window_evidence_digest=cast(
                str, readiness.maintenance_window_evidence_digest
            ),
            required_check_ids=readiness.required_check_ids,
            satisfied_check_ids=readiness.satisfied_check_ids,
            not_applicable_check_ids=readiness.not_applicable_check_ids,
            created_at=revalidation.revalidated_at,
            valid_until=readiness.evidence_valid_until,
            canonical_digest=digest,
        )
        await self._audit_revalidation(
            actor=actor,
            correlation_id=correlation_id,
            revalidation=revalidation,
            result_code="connector_upgrade_evidence_receipt_created",
            permission_id=UPGRADE_EVIDENCE_RECEIPT_CREATE_PERMISSION,
            idempotency_key=None,
        )
        return receipt

    @classmethod
    def _verify_audit_readiness_evidence(
        cls, evidence: ConnectorUpgradeAuditReadinessEvidence
    ) -> None:
        payload = {
            "schema_version": evidence.schema_version,
            "organization_id": evidence.organization_id,
            "environment_id": evidence.environment_id,
            "request_id": evidence.request_id,
            "request_digest": evidence.request_digest,
            "revalidation_id": evidence.revalidation_id,
            "revalidation_digest": evidence.revalidation_digest,
            "ledger_id": evidence.ledger_id,
            "ledger_generation": evidence.ledger_generation,
            "producer_coverage_digest": evidence.producer_coverage_digest,
            "integrity_verification_digest": evidence.integrity_verification_digest,
            "redaction_policy_digest": evidence.redaction_policy_digest,
            "retention_policy_digest": evidence.retention_policy_digest,
            "verified_at": evidence.verified_at.isoformat(),
            "valid_until": evidence.valid_until.isoformat(),
            "durable_acceptance": evidence.durable_acceptance,
            "append_only": evidence.append_only,
            "integrity_verified": evidence.integrity_verified,
            "gap_free": evidence.gap_free,
            "redaction_current": evidence.redaction_current,
            "retention_current": evidence.retention_current,
            "producer_coverage_complete": evidence.producer_coverage_complete,
            "consequential_blocking_enabled": evidence.consequential_blocking_enabled,
            "infrastructure_mutation_performed": False,
        }
        digest = cls._digest(payload)
        if (
            evidence.schema_version != UPGRADE_AUDIT_READINESS_EVIDENCE_SCHEMA
            or evidence.evidence_id != f"connector-upgrade-audit-readiness-evidence.{digest[:24]}"
            or evidence.canonical_digest != digest
        ):
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_audit_readiness_evidence_integrity_invalid"
            )

    @classmethod
    def _verify_itsm_change_evidence(cls, evidence: ConnectorUpgradeItsmChangeEvidence) -> None:
        payload = {
            "schema_version": evidence.schema_version,
            "organization_id": evidence.organization_id,
            "environment_id": evidence.environment_id,
            "request_id": evidence.request_id,
            "request_digest": evidence.request_digest,
            "revalidation_id": evidence.revalidation_id,
            "revalidation_digest": evidence.revalidation_digest,
            "plan_id": evidence.plan_id,
            "plan_digest": evidence.plan_digest,
            "adapter_id": evidence.adapter_id,
            "adapter_version": evidence.adapter_version,
            "authoritative_instance_id": evidence.authoritative_instance_id,
            "external_record_id": evidence.external_record_id,
            "external_record_version": evidence.external_record_version,
            "observed_at": evidence.observed_at.isoformat(),
            "valid_until": evidence.valid_until.isoformat(),
            "adapter_validated": evidence.adapter_validated,
            "authoritative_source": evidence.authoritative_source,
            "record_accessible": evidence.record_accessible,
            "source_version_current": evidence.source_version_current,
            "exact_plan_binding_verified": evidence.exact_plan_binding_verified,
            "record_active": evidence.record_active,
            "conflict_free": evidence.conflict_free,
            "revocation_absent": evidence.revocation_absent,
            "external_record_modified": False,
            "infrastructure_mutation_performed": False,
        }
        digest = cls._digest(payload)
        if (
            evidence.schema_version != UPGRADE_ITSM_CHANGE_EVIDENCE_SCHEMA
            or evidence.evidence_id != f"connector-upgrade-itsm-change-evidence.{digest[:24]}"
            or evidence.canonical_digest != digest
        ):
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_itsm_change_evidence_integrity_invalid"
            )

    @classmethod
    def _verify_maintenance_window_evidence(
        cls, evidence: ConnectorUpgradeMaintenanceWindowEvidence
    ) -> None:
        payload = {
            "schema_version": evidence.schema_version,
            "organization_id": evidence.organization_id,
            "environment_id": evidence.environment_id,
            "request_id": evidence.request_id,
            "request_digest": evidence.request_digest,
            "revalidation_id": evidence.revalidation_id,
            "revalidation_digest": evidence.revalidation_digest,
            "plan_id": evidence.plan_id,
            "plan_digest": evidence.plan_digest,
            "itsm_change_evidence_id": evidence.itsm_change_evidence_id,
            "itsm_change_evidence_digest": evidence.itsm_change_evidence_digest,
            "external_record_version": evidence.external_record_version,
            "window_version": evidence.window_version,
            "approved_start": evidence.approved_start.isoformat(),
            "approved_end": evidence.approved_end.isoformat(),
            "observed_at": evidence.observed_at.isoformat(),
            "valid_until": evidence.valid_until.isoformat(),
            "authoritative_source": evidence.authoritative_source,
            "window_approved": evidence.window_approved,
            "source_version_current": evidence.source_version_current,
            "exact_change_binding_verified": evidence.exact_change_binding_verified,
            "exact_plan_binding_verified": evidence.exact_plan_binding_verified,
            "inside_approved_window": evidence.inside_approved_window,
            "freeze_clear": evidence.freeze_clear,
            "conflict_free": evidence.conflict_free,
            "revocation_absent": evidence.revocation_absent,
            "external_record_modified": False,
            "infrastructure_mutation_performed": False,
        }
        digest = cls._digest(payload)
        if (
            evidence.schema_version != UPGRADE_MAINTENANCE_WINDOW_EVIDENCE_SCHEMA
            or evidence.evidence_id
            != f"connector-upgrade-maintenance-window-evidence.{digest[:24]}"
            or evidence.canonical_digest != digest
        ):
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_maintenance_window_evidence_integrity_invalid"
            )

    async def create_change_context_draft(
        self,
        *,
        actor: AuthenticatedSubject,
        record_id: str,
        request_id: str,
        expected_readiness_digest: str,
        proposed_window_start: datetime,
        proposed_window_end: datetime,
        justification: str,
        acknowledged_draft_grants_no_dispatch_approval_handoff_or_execution_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorUpgradeChangeContextDraft:
        self._require_enterprise_human(actor)
        normalized_justification = justification.strip()
        if (
            not acknowledged_draft_grants_no_dispatch_approval_handoff_or_execution_authority
            or not 20 <= len(normalized_justification) <= 1000
        ):
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_change_context_acknowledgement_required"
            )
        now = self._clock()
        if (
            proposed_window_start.tzinfo is None
            or proposed_window_end.tzinfo is None
            or proposed_window_start < now + timedelta(minutes=15)
            or proposed_window_start > now + timedelta(days=90)
            or not timedelta(minutes=15)
            <= proposed_window_end - proposed_window_start
            <= timedelta(hours=4)
        ):
            raise ConnectorUpgradeApprovalError("connector_upgrade_change_context_window_invalid")
        request = await self._repository.get(request_id=request_id)
        if request is None:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_not_found")
        self._require_request_scope(request, actor, record_id)
        revalidation = await self._repository.get_latest_revalidation(request_id=request_id)
        if revalidation is None or revalidation.revalidated_by != actor.subject_id:
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_change_context_verifier_required"
            )
        self._verify_revalidation(revalidation)
        readiness = await self.assess_handoff_readiness(
            actor=actor,
            record_id=record_id,
            request_id=request_id,
            correlation_id=correlation_id,
        )
        if readiness.canonical_digest != expected_readiness_digest:
            raise ConnectorUpgradeApprovalError("connector_upgrade_change_context_readiness_stale")
        fingerprint = self._digest(
            {
                "request_id": request_id,
                "readiness_digest": readiness.canonical_digest,
                "window": (proposed_window_start.isoformat(), proposed_window_end.isoformat()),
                "justification": normalized_justification,
                "acknowledged_no_authority": True,
            }
        )
        prior = await self._repository.get_change_context_draft_by_key(
            created_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if prior is not None:
            self._verify_change_context_draft(prior)
            if prior.request_fingerprint != fingerprint:
                raise ConnectorUpgradeApprovalError(
                    "connector_upgrade_change_context_idempotency_conflict"
                )
            await self._audit_revalidation(
                actor=actor,
                correlation_id=correlation_id,
                revalidation=revalidation,
                result_code="connector_upgrade_change_context_draft_reused",
                permission_id=UPGRADE_CHANGE_CONTEXT_CREATE_PERMISSION,
                idempotency_key=idempotency_key,
            )
            return replace(prior, reused=True)
        title = (
            f"Review connector upgrade {readiness.connector_id} for {readiness.environment_id}"
        )[:160]
        itsm_digest = self._digest(
            {
                "title": title,
                "request_digest": readiness.request_digest,
                "readiness_digest": readiness.canonical_digest,
                "window": (proposed_window_start.isoformat(), proposed_window_end.isoformat()),
                "justification": normalized_justification,
                "itsm_dispatched": False,
                "window_approved": False,
            }
        )
        payload = {
            "schema_version": UPGRADE_CHANGE_CONTEXT_SCHEMA,
            "source_record_id": readiness.source_record_id,
            "source_record_version": readiness.source_record_version,
            "instance_id": readiness.instance_id,
            "connector_id": readiness.connector_id,
            "request_id": readiness.request_id,
            "request_digest": readiness.request_digest,
            "decision_digest": readiness.decision_digest,
            "revalidation_id": readiness.revalidation_id,
            "revalidation_digest": readiness.revalidation_digest,
            "readiness_digest": readiness.canonical_digest,
            "organization_id": readiness.organization_id,
            "environment_id": readiness.environment_id,
            "created_by": actor.subject_id,
            "justification": normalized_justification,
            "window": (proposed_window_start.isoformat(), proposed_window_end.isoformat()),
            "itsm_draft_title": title,
            "itsm_draft_digest": itsm_digest,
            "request_fingerprint": fingerprint,
            "created_at": now.isoformat(),
            "valid_until": readiness.evidence_valid_until.isoformat(),
        }
        digest = self._digest(payload)
        draft = ConnectorUpgradeChangeContextDraft(
            draft_id=f"connector-upgrade-change-context-draft.{digest[:24]}",
            schema_version=UPGRADE_CHANGE_CONTEXT_SCHEMA,
            source_record_id=readiness.source_record_id,
            source_record_version=readiness.source_record_version,
            instance_id=readiness.instance_id,
            connector_id=readiness.connector_id,
            request_id=readiness.request_id,
            request_digest=readiness.request_digest,
            decision_digest=readiness.decision_digest,
            revalidation_id=readiness.revalidation_id,
            revalidation_digest=readiness.revalidation_digest,
            readiness_digest=readiness.canonical_digest,
            organization_id=readiness.organization_id,
            environment_id=readiness.environment_id,
            created_by=actor.subject_id,
            justification=normalized_justification,
            proposed_window_start=proposed_window_start,
            proposed_window_end=proposed_window_end,
            itsm_draft_title=title,
            itsm_draft_digest=itsm_digest,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            created_at=now,
            valid_until=readiness.evidence_valid_until,
            canonical_digest=digest,
        )
        if not await self._repository.add_change_context_draft(draft):
            raced = await self._repository.get_change_context_draft_by_key(
                created_by=actor.subject_id, idempotency_key=idempotency_key
            )
            if raced is None:
                raise ConnectorUpgradeApprovalError(
                    "connector_upgrade_change_context_idempotency_conflict"
                )
            self._verify_change_context_draft(raced)
            if raced.request_fingerprint != fingerprint:
                raise ConnectorUpgradeApprovalError(
                    "connector_upgrade_change_context_idempotency_conflict"
                )
            draft = replace(raced, reused=True)
        await self._audit_revalidation(
            actor=actor,
            correlation_id=correlation_id,
            revalidation=revalidation,
            result_code="connector_upgrade_change_context_draft_created",
            permission_id=UPGRADE_CHANGE_CONTEXT_CREATE_PERMISSION,
            idempotency_key=idempotency_key,
        )
        return draft

    async def get_latest_change_context_draft(
        self,
        *,
        actor: AuthenticatedSubject,
        record_id: str,
        request_id: str,
        correlation_id: str,
    ) -> ConnectorUpgradeChangeContextDraft:
        self._require_enterprise_human(actor)
        request = await self._repository.get(request_id=request_id)
        if request is None:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_not_found")
        self._require_request_scope(request, actor, record_id)
        draft = await self._repository.get_latest_change_context_draft(request_id=request_id)
        if draft is None or draft.organization_id != actor.organization_id:
            raise ConnectorUpgradeApprovalError("connector_upgrade_change_context_draft_not_found")
        self._verify_change_context_draft(draft)
        revalidation = await self._repository.get_latest_revalidation(request_id=request_id)
        if revalidation is None:
            raise ConnectorUpgradeApprovalError("connector_upgrade_change_context_draft_not_found")
        self._verify_revalidation(revalidation)
        if (
            revalidation.revalidation_id != draft.revalidation_id
            or revalidation.canonical_digest != draft.revalidation_digest
            or self._clock() >= draft.valid_until
        ):
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_change_context_draft_not_current"
            )
        current_readiness = await self.assess_handoff_readiness(
            actor=actor,
            record_id=record_id,
            request_id=request_id,
            correlation_id=correlation_id,
        )
        if current_readiness.canonical_digest != draft.readiness_digest:
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_change_context_draft_not_current"
            )
        await self._audit_revalidation(
            actor=actor,
            correlation_id=correlation_id,
            revalidation=revalidation,
            result_code="connector_upgrade_change_context_draft_read",
            permission_id=UPGRADE_CHANGE_CONTEXT_READ_PERMISSION,
            idempotency_key=None,
        )
        return draft

    @classmethod
    def _verify_change_context_draft(cls, draft: ConnectorUpgradeChangeContextDraft) -> None:
        itsm_digest = cls._digest(
            {
                "title": draft.itsm_draft_title,
                "request_digest": draft.request_digest,
                "readiness_digest": draft.readiness_digest,
                "window": (
                    draft.proposed_window_start.isoformat(),
                    draft.proposed_window_end.isoformat(),
                ),
                "justification": draft.justification,
                "itsm_dispatched": False,
                "window_approved": False,
            }
        )
        payload = {
            "schema_version": draft.schema_version,
            "source_record_id": draft.source_record_id,
            "source_record_version": draft.source_record_version,
            "instance_id": draft.instance_id,
            "connector_id": draft.connector_id,
            "request_id": draft.request_id,
            "request_digest": draft.request_digest,
            "decision_digest": draft.decision_digest,
            "revalidation_id": draft.revalidation_id,
            "revalidation_digest": draft.revalidation_digest,
            "readiness_digest": draft.readiness_digest,
            "organization_id": draft.organization_id,
            "environment_id": draft.environment_id,
            "created_by": draft.created_by,
            "justification": draft.justification,
            "window": (
                draft.proposed_window_start.isoformat(),
                draft.proposed_window_end.isoformat(),
            ),
            "itsm_draft_title": draft.itsm_draft_title,
            "itsm_draft_digest": draft.itsm_draft_digest,
            "request_fingerprint": draft.request_fingerprint,
            "created_at": draft.created_at.isoformat(),
            "valid_until": draft.valid_until.isoformat(),
        }
        if draft.itsm_draft_digest != itsm_digest or draft.canonical_digest != cls._digest(payload):
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_change_context_integrity_invalid"
            )

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

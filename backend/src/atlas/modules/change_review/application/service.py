from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.change_review.application.ports import (
    ChangeReviewError,
    ChangeReviewPacketRepository,
)
from atlas.modules.change_review.domain.packet import (
    ChangeReviewState,
    UpgradeChangeReviewPacket,
    UpgradeChangeReviewPreview,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.upgrade.application.ports import UpgradeError, UpgradeSimulationRepository
from atlas.modules.upgrade.application.service import UpgradeService
from atlas.modules.upgrade.domain.upgrade import UpgradeSimulationState

PREVIEW_SCHEMA = "atlas.upgrade-change-review-preview.v1"
PACKET_SCHEMA = "atlas.upgrade-change-review-packet.v1"
RISK_CLASS = "risk.medium"
CHANGE_CLASS = "change.reviewed-standard"
ASSUMPTIONS = (
    "assumption.maintenance-capacity-available",
    "assumption.service-owners-contactable",
    "assumption.rollback-artifacts-retained",
    "assumption.monitoring-observes-target",
)
UNKNOWNS = (
    "unknown.production-traffic-pattern",
    "unknown.customer-maintenance-acceptance",
    "unknown.external-dependency-runtime",
    "unknown.cab-decision",
)
RESIDUAL_RISKS = (
    "risk.service-interruption",
    "risk.schema-transition",
    "risk.rollback-duration-variance",
)
OWNER_ROLES = (
    "role.platform-owner",
    "role.service-owner",
    "role.security-reviewer",
    "role.change-approver",
)


class ChangeReviewService:
    def __init__(
        self,
        *,
        upgrade_service: UpgradeService,
        simulation_repository: UpgradeSimulationRepository,
        packet_repository: ChangeReviewPacketRepository,
        audit_sink: AuditSink,
        environment_id: str,
        site_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._upgrade_service = upgrade_service
        self._simulation_repository = simulation_repository
        self._packet_repository = packet_repository
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._site_id = site_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def close(self) -> None:
        await self._packet_repository.close()

    async def preview(
        self,
        *,
        actor: AuthenticatedSubject,
        source_run_id: str,
        source_run_version: int,
        backup_id: str,
        restore_validation_id: str,
        target_release_id: str,
        plan_id: str,
        plan_digest: str,
        simulation_id: str,
        simulation_digest: str,
    ) -> UpgradeChangeReviewPreview:
        try:
            plan = await self._upgrade_service.preview(
                actor=actor,
                source_run_id=source_run_id,
                backup_id=backup_id,
                restore_validation_id=restore_validation_id,
                target_release_id=target_release_id,
            )
        except UpgradeError as error:
            raise ChangeReviewError("change_review_source_evidence_invalid") from error
        if plan.source_run_version != source_run_version:
            raise ChangeReviewError("change_review_source_stale")
        if plan.plan_id != plan_id or plan.plan_digest != plan_digest:
            raise ChangeReviewError("change_review_plan_stale")
        simulation = await self._simulation_repository.get_by_id(
            actor_id=actor.subject_id, simulation_id=simulation_id
        )
        if (
            simulation is None
            or simulation.state is not UpgradeSimulationState.PASSED
            or simulation.simulation_digest != simulation_digest
            or simulation.source_run_id != plan.source_run_id
            or simulation.source_run_version != plan.source_run_version
            or simulation.plan_id != plan.plan_id
            or simulation.plan_digest != plan.plan_digest
            or simulation.backup_id != plan.backup_id
            or simulation.restore_validation_id != plan.restore_validation_id
            or not simulation.isolated_target
        ):
            raise ChangeReviewError("change_review_simulation_invalid")
        evidence_digests = (
            plan.plan_digest,
            plan.source_evidence_digest,
            plan.restore_validation_digest,
            simulation.simulation_digest,
        )
        digest = self._digest(
            {
                "schema_version": PREVIEW_SCHEMA,
                "organization_id": actor.organization_id,
                "environment_id": self._environment_id,
                "site_id": self._site_id,
                "source_run": (plan.source_run_id, plan.source_run_version),
                "release_path": (plan.source_release_id, plan.target_release_id),
                "plan": (plan.plan_id, plan.plan_digest),
                "simulation": (simulation.simulation_id, simulation.simulation_digest),
                "backup": (plan.backup_id, plan.restore_validation_id),
                "risk_class": RISK_CLASS,
                "change_class": CHANGE_CLASS,
                "services": plan.service_dependency_ids,
                "migrations": tuple(item.step_id for item in plan.migration_steps),
                "abort": plan.abort_criterion_ids,
                "rollback": plan.rollback_step_ids,
                "post_verification": plan.post_verification_check_ids,
                "assumptions": ASSUMPTIONS,
                "unknowns": UNKNOWNS,
                "residual_risks": RESIDUAL_RISKS,
                "owner_roles": OWNER_ROLES,
                "evidence_digests": evidence_digests,
                "downtime": (
                    plan.estimated_downtime_min_minutes,
                    plan.estimated_downtime_max_minutes,
                ),
                "rollback_window": plan.rollback_window_minutes,
            }
        )
        now = self._clock()
        return UpgradeChangeReviewPreview(
            preview_id=f"change-review-preview.{digest[:24]}",
            schema_version=PREVIEW_SCHEMA,
            source_run_id=plan.source_run_id,
            source_run_version=plan.source_run_version,
            plan_id=plan.plan_id,
            plan_digest=plan.plan_digest,
            simulation_id=simulation.simulation_id,
            simulation_digest=simulation.simulation_digest,
            source_release_id=plan.source_release_id,
            source_release_version=plan.source_release_version,
            target_release_id=plan.target_release_id,
            target_release_version=plan.target_release_version,
            backup_id=plan.backup_id,
            restore_validation_id=plan.restore_validation_id,
            risk_class=RISK_CLASS,
            change_class=CHANGE_CLASS,
            impacted_service_ids=plan.service_dependency_ids,
            migration_step_ids=tuple(item.step_id for item in plan.migration_steps),
            abort_criterion_ids=plan.abort_criterion_ids,
            rollback_step_ids=plan.rollback_step_ids,
            post_verification_check_ids=plan.post_verification_check_ids,
            assumption_ids=ASSUMPTIONS,
            unknown_ids=UNKNOWNS,
            residual_risk_ids=RESIDUAL_RISKS,
            owner_role_ids=OWNER_ROLES,
            evidence_digests=evidence_digests,
            estimated_downtime_min_minutes=plan.estimated_downtime_min_minutes,
            estimated_downtime_max_minutes=plan.estimated_downtime_max_minutes,
            rollback_window_minutes=plan.rollback_window_minutes,
            state=ChangeReviewState.READY,
            preview_digest=digest,
            generated_at=now,
            expires_at=min(plan.expires_at, now + timedelta(minutes=30)),
        )

    async def create_packet(
        self,
        *,
        actor: AuthenticatedSubject,
        source_run_id: str,
        source_run_version: int,
        backup_id: str,
        restore_validation_id: str,
        target_release_id: str,
        plan_id: str,
        plan_digest: str,
        simulation_id: str,
        simulation_digest: str,
        preview_id: str,
        preview_digest: str,
        preview_expires_at: datetime,
        proposed_window_start: datetime,
        proposed_window_end: datetime,
        justification: str,
        confirmed: bool,
        acknowledged_no_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> UpgradeChangeReviewPacket:
        normalized_reason = justification.strip()
        if (
            not confirmed
            or not acknowledged_no_authority
            or not 12 <= len(normalized_reason) <= 500
        ):
            raise ChangeReviewError("change_review_confirmation_required")
        now = self._clock()
        if preview_expires_at.tzinfo is None or preview_expires_at <= now:
            raise ChangeReviewError("change_review_preview_stale")
        if proposed_window_start.tzinfo is None or proposed_window_end.tzinfo is None:
            raise ChangeReviewError("change_review_window_invalid")
        duration = proposed_window_end - proposed_window_start
        if (
            proposed_window_start < now + timedelta(minutes=15)
            or proposed_window_start > now + timedelta(days=90)
            or duration < timedelta(minutes=12)
            or duration > timedelta(hours=4)
        ):
            raise ChangeReviewError("change_review_window_invalid")
        fingerprint = self._digest(
            {
                "source_run_id": source_run_id,
                "source_run_version": source_run_version,
                "backup_id": backup_id,
                "restore_validation_id": restore_validation_id,
                "target_release_id": target_release_id,
                "plan_id": plan_id,
                "plan_digest": plan_digest,
                "simulation_id": simulation_id,
                "simulation_digest": simulation_digest,
                "preview_id": preview_id,
                "preview_digest": preview_digest,
                "preview_expires_at": preview_expires_at.isoformat(),
                "window": (proposed_window_start.isoformat(), proposed_window_end.isoformat()),
                "justification": normalized_reason,
                "acknowledged_no_authority": acknowledged_no_authority,
            }
        )
        prior = await self._packet_repository.get(
            actor_id=actor.subject_id, idempotency_key=idempotency_key
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                raise ChangeReviewError("change_review_idempotency_conflict")
            return replace(prior, reused=True)
        preview = await self.preview(
            actor=actor,
            source_run_id=source_run_id,
            source_run_version=source_run_version,
            backup_id=backup_id,
            restore_validation_id=restore_validation_id,
            target_release_id=target_release_id,
            plan_id=plan_id,
            plan_digest=plan_digest,
            simulation_id=simulation_id,
            simulation_digest=simulation_digest,
        )
        if preview.preview_id != preview_id or preview.preview_digest != preview_digest:
            raise ChangeReviewError("change_review_preview_stale")
        itsm_title = (
            f"Review Atlas upgrade {preview.source_release_version} to "
            f"{preview.target_release_version}"
        )
        itsm_digest = self._digest(
            {
                "title": itsm_title,
                "change_class": preview.change_class,
                "risk_class": preview.risk_class,
                "services": preview.impacted_service_ids,
                "window": (proposed_window_start.isoformat(), proposed_window_end.isoformat()),
                "downtime": (
                    preview.estimated_downtime_min_minutes,
                    preview.estimated_downtime_max_minutes,
                ),
                "abort": preview.abort_criterion_ids,
                "rollback": preview.rollback_step_ids,
                "verification": preview.post_verification_check_ids,
                "approval_granted": False,
                "dispatch_authorized": False,
            }
        )
        packet_digest = self._digest(
            {
                "preview_digest": preview.preview_digest,
                "request_fingerprint": fingerprint,
                "itsm_draft_digest": itsm_digest,
                "evidence": preview.evidence_digests,
            }
        )
        await self._audit(
            actor,
            correlation_id,
            idempotency_key,
            "upgrade_change_review_packet_authorized",
            (("preview_digest", preview.preview_digest),),
        )
        key = f"{actor.subject_id}:{idempotency_key}:{fingerprint}"
        record = UpgradeChangeReviewPacket(
            packet_id=f"change-review-packet.{sha256(key.encode()).hexdigest()[:24]}",
            schema_version=PACKET_SCHEMA,
            state=ChangeReviewState.CREATED,
            actor_id=actor.subject_id,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            source_run_id=preview.source_run_id,
            source_run_version=preview.source_run_version,
            preview_id=preview.preview_id,
            preview_digest=preview.preview_digest,
            plan_id=preview.plan_id,
            plan_digest=preview.plan_digest,
            simulation_id=preview.simulation_id,
            simulation_digest=preview.simulation_digest,
            backup_id=preview.backup_id,
            restore_validation_id=preview.restore_validation_id,
            risk_class=preview.risk_class,
            change_class=preview.change_class,
            impacted_service_ids=preview.impacted_service_ids,
            migration_step_ids=preview.migration_step_ids,
            abort_criterion_ids=preview.abort_criterion_ids,
            rollback_step_ids=preview.rollback_step_ids,
            post_verification_check_ids=preview.post_verification_check_ids,
            assumption_ids=preview.assumption_ids,
            unknown_ids=preview.unknown_ids,
            residual_risk_ids=preview.residual_risk_ids,
            owner_role_ids=preview.owner_role_ids,
            evidence_digests=preview.evidence_digests,
            proposed_window_start=proposed_window_start,
            proposed_window_end=proposed_window_end,
            estimated_downtime_min_minutes=preview.estimated_downtime_min_minutes,
            estimated_downtime_max_minutes=preview.estimated_downtime_max_minutes,
            rollback_window_minutes=preview.rollback_window_minutes,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            itsm_draft_id=f"itsm-draft.{itsm_digest[:24]}",
            itsm_draft_title=itsm_title,
            itsm_draft_digest=itsm_digest,
            packet_digest=packet_digest,
            created_at=now,
        )
        if not await self._packet_repository.add(record):
            raced = await self._packet_repository.get(
                actor_id=actor.subject_id, idempotency_key=idempotency_key
            )
            if raced is None or raced.request_fingerprint != fingerprint:
                raise ChangeReviewError("change_review_idempotency_conflict")
            return replace(raced, reused=True)
        await self._audit(
            actor,
            correlation_id,
            idempotency_key,
            "upgrade_change_review_packet_completed",
            (("packet_id", record.packet_id), ("packet_digest", packet_digest)),
        )
        return record

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        idempotency_key: str,
        result_code: str,
        metadata: tuple[tuple[str, str], ...],
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.upgrade.change-review",
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id="platform.upgrade-change-review.create",
                resource_type="resource.platform.upgrade-change-review",
                scope_reference=(
                    f"{actor.organization_id}/{self._environment_id}/{self._site_id}/"
                    "domain.platform/resource.platform.upgrade-change-review/C2"
                ),
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )

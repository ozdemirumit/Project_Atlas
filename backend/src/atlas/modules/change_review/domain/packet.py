from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

STABLE_ID = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")


class ChangeReviewState(StrEnum):
    READY = "ready"
    CREATED = "created"


@dataclass(frozen=True, slots=True)
class UpgradeChangeReviewPreview:
    preview_id: str
    schema_version: str
    source_run_id: str
    source_run_version: int
    plan_id: str
    plan_digest: str
    simulation_id: str
    simulation_digest: str
    source_release_id: str
    source_release_version: str
    target_release_id: str
    target_release_version: str
    backup_id: str
    restore_validation_id: str
    risk_class: str
    change_class: str
    impacted_service_ids: tuple[str, ...]
    migration_step_ids: tuple[str, ...]
    abort_criterion_ids: tuple[str, ...]
    rollback_step_ids: tuple[str, ...]
    post_verification_check_ids: tuple[str, ...]
    assumption_ids: tuple[str, ...]
    unknown_ids: tuple[str, ...]
    residual_risk_ids: tuple[str, ...]
    owner_role_ids: tuple[str, ...]
    evidence_digests: tuple[str, ...]
    estimated_downtime_min_minutes: int
    estimated_downtime_max_minutes: int
    rollback_window_minutes: int
    state: ChangeReviewState
    preview_digest: str
    generated_at: datetime
    expires_at: datetime
    approval_granted: bool = False
    execution_authorized: bool = False
    dispatch_authorized: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        identifiers = (
            self.preview_id,
            self.schema_version,
            self.source_run_id,
            self.plan_id,
            self.simulation_id,
            self.source_release_id,
            self.target_release_id,
            self.backup_id,
            self.restore_validation_id,
            self.risk_class,
            self.change_class,
        )
        if any(STABLE_ID.fullmatch(item) is None for item in identifiers):
            raise ValueError("change review identifier is invalid")
        if self.source_run_version < 1 or self.generated_at >= self.expires_at:
            raise ValueError("change review source or expiry is invalid")
        if any(
            SHA256.fullmatch(item) is None
            for item in (
                *self.evidence_digests,
                self.plan_digest,
                self.simulation_digest,
                self.preview_digest,
            )
        ):
            raise ValueError("change review digest is invalid")
        for values, expected in (
            (self.impacted_service_ids, 2),
            (self.migration_step_ids, 3),
            (self.abort_criterion_ids, 4),
            (self.rollback_step_ids, 4),
            (self.post_verification_check_ids, 6),
            (self.assumption_ids, 4),
            (self.unknown_ids, 4),
            (self.residual_risk_ids, 3),
            (self.owner_role_ids, 4),
            (self.evidence_digests, 4),
        ):
            if len(values) != expected or len(set(values)) != expected:
                raise ValueError("change review evidence is incomplete")
        if not 1 <= self.estimated_downtime_min_minutes <= self.estimated_downtime_max_minutes:
            raise ValueError("change review downtime is invalid")
        if self.rollback_window_minutes < 15 or self.state is not ChangeReviewState.READY:
            raise ValueError("change review rollback or state is invalid")
        if any(
            (
                self.approval_granted,
                self.execution_authorized,
                self.dispatch_authorized,
                self.infrastructure_mutation_performed,
            )
        ):
            raise ValueError("change review preview violates safety boundaries")


@dataclass(frozen=True, slots=True)
class UpgradeChangeReviewPacket:
    packet_id: str
    schema_version: str
    state: ChangeReviewState
    actor_id: str
    organization_id: str
    environment_id: str
    site_id: str
    source_run_id: str
    source_run_version: int
    preview_id: str
    preview_digest: str
    plan_id: str
    plan_digest: str
    simulation_id: str
    simulation_digest: str
    backup_id: str
    restore_validation_id: str
    risk_class: str
    change_class: str
    impacted_service_ids: tuple[str, ...]
    migration_step_ids: tuple[str, ...]
    abort_criterion_ids: tuple[str, ...]
    rollback_step_ids: tuple[str, ...]
    post_verification_check_ids: tuple[str, ...]
    assumption_ids: tuple[str, ...]
    unknown_ids: tuple[str, ...]
    residual_risk_ids: tuple[str, ...]
    owner_role_ids: tuple[str, ...]
    evidence_digests: tuple[str, ...]
    proposed_window_start: datetime
    proposed_window_end: datetime
    estimated_downtime_min_minutes: int
    estimated_downtime_max_minutes: int
    rollback_window_minutes: int
    request_fingerprint: str
    idempotency_key: str
    itsm_draft_id: str
    itsm_draft_title: str
    itsm_draft_digest: str
    packet_digest: str
    created_at: datetime
    reused: bool = False
    approval_granted: bool = False
    execution_authorized: bool = False
    itsm_dispatched: bool = False
    notification_sent: bool = False
    workflow_executed: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        identifiers = (
            self.packet_id,
            self.schema_version,
            self.actor_id,
            self.organization_id,
            self.environment_id,
            self.site_id,
            self.source_run_id,
            self.preview_id,
            self.plan_id,
            self.simulation_id,
            self.backup_id,
            self.restore_validation_id,
            self.risk_class,
            self.change_class,
            self.itsm_draft_id,
        )
        if any(STABLE_ID.fullmatch(item) is None for item in identifiers):
            raise ValueError("change review packet identifier is invalid")
        if any(
            SHA256.fullmatch(item) is None
            for item in (
                *self.evidence_digests,
                self.preview_digest,
                self.plan_digest,
                self.simulation_digest,
                self.request_fingerprint,
                self.itsm_draft_digest,
                self.packet_digest,
            )
        ):
            raise ValueError("change review packet digest is invalid")
        evidence_sections = (
            (self.impacted_service_ids, 2),
            (self.migration_step_ids, 3),
            (self.abort_criterion_ids, 4),
            (self.rollback_step_ids, 4),
            (self.post_verification_check_ids, 6),
            (self.assumption_ids, 4),
            (self.unknown_ids, 4),
            (self.residual_risk_ids, 3),
            (self.owner_role_ids, 4),
            (self.evidence_digests, 4),
        )
        if self.source_run_version < 1 or any(
            len(values) != expected or len(set(values)) != expected
            for values, expected in evidence_sections
        ):
            raise ValueError("change review packet source is invalid")
        if (
            self.proposed_window_start.tzinfo is None
            or self.proposed_window_end.tzinfo is None
            or self.proposed_window_start >= self.proposed_window_end
        ):
            raise ValueError("change review maintenance window is invalid")
        if not 12 <= len(self.itsm_draft_title) <= 160:
            raise ValueError("change review ITSM title is invalid")
        if self.state is not ChangeReviewState.CREATED or any(
            (
                self.approval_granted,
                self.execution_authorized,
                self.itsm_dispatched,
                self.notification_sent,
                self.workflow_executed,
                self.infrastructure_mutation_performed,
            )
        ):
            raise ValueError("change review packet violates safety boundaries")

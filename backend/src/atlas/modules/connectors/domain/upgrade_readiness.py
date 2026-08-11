from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, slots=True)
class ConnectorCapabilityChange:
    capability_id: str
    change_type: str
    current_class: str | None
    candidate_class: str | None
    current_permission: str | None
    candidate_permission: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.capability_id, "upgrade capability identifier")
        if self.change_type not in {"added", "removed", "changed"}:
            raise ValueError("Upgrade capability change type is invalid")
        for capability_class in (self.current_class, self.candidate_class):
            if capability_class is not None and capability_class not in {"C0", "C1"}:
                raise ValueError("Upgrade capability class is invalid")
        for permission in (self.current_permission, self.candidate_permission):
            if permission is not None:
                validate_stable_identifier(permission, "upgrade capability permission")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeCandidate:
    receipt_id: str
    receipt_digest: str
    package_digest: str
    manifest_digest: str
    release_version: str
    publisher_id: str
    sdk_profile: str
    installed_at: datetime
    upgrade_class: str
    risk_level: str
    capability_changes: tuple[ConnectorCapabilityChange, ...]
    target_products_added: tuple[str, ...]
    target_products_removed: tuple[str, ...]
    network_destinations_added: tuple[str, ...]
    network_destinations_removed: tuple[str, ...]
    configuration_key_delta: int
    secret_reference_delta: int
    policy_review_required: bool
    configuration_migration_required: bool
    rollback_receipt_id: str
    rollback_receipt_digest: str
    review_eligible: bool
    blockers: tuple[str, ...]
    canonical_digest: str
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.receipt_id,
            self.release_version,
            self.publisher_id,
            self.sdk_profile,
            self.rollback_receipt_id,
            *self.blockers,
        ):
            validate_stable_identifier(value, "upgrade candidate identifier")
        if (
            any(
                _DIGEST.fullmatch(value) is None
                for value in (
                    self.receipt_digest,
                    self.package_digest,
                    self.manifest_digest,
                    self.rollback_receipt_digest,
                    self.canonical_digest,
                )
            )
            or self.installed_at.tzinfo is None
            or self.upgrade_class not in {"patch", "minor", "major"}
            or self.risk_level not in {"low", "medium", "high", "critical"}
            or self.review_eligible != (not self.blockers)
            or self.execution_authorized
            or self.infrastructure_mutation_performed
        ):
            raise ValueError("Connector upgrade candidate violates the readiness boundary")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeReadiness:
    schema_version: str
    source_record_id: str
    source_record_version: int
    instance_id: str
    instance_key: str
    connector_id: str
    current_release_version: str
    current_package_digest: str
    current_manifest_digest: str
    current_receipt_id: str
    current_receipt_digest: str
    target_configured: bool
    candidates: tuple[ConnectorUpgradeCandidate, ...]
    generated_at: datetime
    canonical_digest: str
    decision_support_only: bool = True
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.schema_version,
            self.source_record_id,
            self.instance_id,
            self.instance_key,
            self.connector_id,
            self.current_release_version,
            self.current_receipt_id,
        ):
            validate_stable_identifier(value, "upgrade readiness identifier")
        if (
            self.source_record_version < 1
            or any(
                _DIGEST.fullmatch(value) is None
                for value in (
                    self.current_package_digest,
                    self.current_manifest_digest,
                    self.current_receipt_digest,
                    self.canonical_digest,
                )
            )
            or self.generated_at.tzinfo is None
            or not self.decision_support_only
            or self.execution_authorized
            or self.infrastructure_mutation_performed
        ):
            raise ValueError("Connector upgrade readiness violates the decision-support boundary")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradePlanStep:
    step_id: str
    sequence: int
    phase: str
    expected_minutes: int
    requires_service_interruption: bool
    rollback_boundary: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.step_id, "connector upgrade plan step")
        if (
            self.sequence < 1
            or self.phase
            not in {
                "approval",
                "precheck",
                "quiescence",
                "package_binding",
                "configuration",
                "verification",
                "rollback_gate",
            }
            or not 0 <= self.expected_minutes <= 120
        ):
            raise ValueError("Connector upgrade plan step is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradePlan:
    plan_id: str
    schema_version: str
    source_record_id: str
    source_record_version: int
    instance_id: str
    connector_id: str
    current_release_version: str
    current_receipt_id: str
    current_receipt_digest: str
    candidate_release_version: str
    candidate_receipt_id: str
    candidate_receipt_digest: str
    readiness_digest: str
    candidate_digest: str
    risk_level: str
    target_configured: bool
    target_id: str | None
    site_id: str | None
    target_product: str | None
    plan_state: str
    plan_eligible: bool
    prerequisite_ids: tuple[str, ...]
    steps: tuple[ConnectorUpgradePlanStep, ...]
    validation_check_ids: tuple[str, ...]
    stop_condition_ids: tuple[str, ...]
    rollback_step_ids: tuple[str, ...]
    blockers: tuple[str, ...]
    unknowns: tuple[str, ...]
    estimated_interruption_min_minutes: int | None
    estimated_interruption_max_minutes: int | None
    rollback_window_minutes: int
    generated_at: datetime
    expires_at: datetime
    canonical_digest: str
    approval_required: bool = True
    decision_support_only: bool = True
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.plan_id,
            self.schema_version,
            self.source_record_id,
            self.instance_id,
            self.connector_id,
            self.current_release_version,
            self.current_receipt_id,
            self.candidate_release_version,
            self.candidate_receipt_id,
            *self.prerequisite_ids,
            *self.validation_check_ids,
            *self.stop_condition_ids,
            *self.rollback_step_ids,
            *self.blockers,
        ):
            validate_stable_identifier(value, "connector upgrade plan identifier")
        digests = (
            self.current_receipt_digest,
            self.candidate_receipt_digest,
            self.readiness_digest,
            self.candidate_digest,
            self.canonical_digest,
        )
        sequences = tuple(item.sequence for item in self.steps)
        interruption = (
            self.estimated_interruption_min_minutes,
            self.estimated_interruption_max_minutes,
        )
        if (
            self.source_record_version < 1
            or any(_DIGEST.fullmatch(value) is None for value in digests)
            or self.risk_level not in {"low", "medium", "high", "critical"}
            or self.plan_state not in {"ready_for_human_review", "blocked"}
            or self.plan_eligible != (self.plan_state == "ready_for_human_review")
            or self.plan_eligible != (not self.blockers and not self.target_configured)
            or sequences != tuple(range(1, len(self.steps) + 1))
            or len(self.steps) != 7
            or len(set(self.prerequisite_ids)) != len(self.prerequisite_ids)
            or len(set(self.validation_check_ids)) != len(self.validation_check_ids)
            or len(set(self.stop_condition_ids)) != len(self.stop_condition_ids)
            or len(set(self.rollback_step_ids)) != len(self.rollback_step_ids)
            or not self.validation_check_ids
            or not self.stop_condition_ids
            or not self.rollback_step_ids
            or self.generated_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.generated_at >= self.expires_at
            or not 15 <= self.rollback_window_minutes <= 1440
            or not self.approval_required
            or not self.decision_support_only
            or self.execution_authorized
            or self.infrastructure_mutation_performed
        ):
            raise ValueError("Connector upgrade plan violates the planning boundary")
        if self.target_configured:
            if (
                not all((self.target_id, self.site_id, self.target_product))
                or interruption != (None, None)
                or self.plan_eligible
                or not self.blockers
                or not self.unknowns
            ):
                raise ValueError("Configured connector upgrade requires impact evidence")
        elif any((self.target_id, self.site_id, self.target_product)) or interruption != (0, 0):
            raise ValueError("Unconfigured connector upgrade plan is inconsistent")

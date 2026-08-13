from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class ConnectorUpgradeApprovalOutcome(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_EVIDENCE = "needs_evidence"
    DEFER = "defer"


class ConnectorUpgradeApprovalState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_EVIDENCE = "needs_evidence"
    DEFERRED = "deferred"
    EXPIRED = "expired"


class ConnectorUpgradeEvidenceReceiptVerificationState(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    EXPIRED = "expired"
    UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeApprovalPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    request_lifetime_minutes: int
    required_assurance_level: AssuranceLevel
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.policy_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.policy_version,
            self.signed_by,
        ):
            validate_stable_identifier(value, "connector upgrade approval policy identifier")
        if (
            self.version != 1
            or not 15 <= self.request_lifetime_minutes <= 1440
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Connector upgrade approval policy contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeApprovalRequest:
    request_id: str
    schema_version: str
    version: int
    source_record_id: str
    source_record_version: int
    instance_id: str
    connector_id: str
    plan_id: str
    plan_digest: str
    readiness_digest: str
    current_release_version: str
    current_receipt_id: str
    current_receipt_digest: str
    candidate_release_version: str
    candidate_receipt_id: str
    candidate_receipt_digest: str
    candidate_digest: str
    risk_level: str
    organization_id: str
    environment_id: str
    requested_by: str
    purpose: str
    approval_policy_id: str
    approval_policy_digest: str
    approval_policy_version: str
    created_at: datetime
    expires_at: datetime
    state: str
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    separation_of_duties_required: bool = True
    approval_granted: bool = False
    decision_recorded: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.request_id,
            self.schema_version,
            self.source_record_id,
            self.instance_id,
            self.connector_id,
            self.plan_id,
            self.current_release_version,
            self.current_receipt_id,
            self.candidate_release_version,
            self.candidate_receipt_id,
            self.organization_id,
            self.environment_id,
            self.requested_by,
            self.approval_policy_id,
            self.approval_policy_version,
            self.state,
        ):
            validate_stable_identifier(value, "connector upgrade approval request identifier")
        for value in (
            self.plan_digest,
            self.readiness_digest,
            self.current_receipt_digest,
            self.candidate_receipt_digest,
            self.candidate_digest,
            self.approval_policy_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Connector upgrade approval request digest is invalid")
        if (
            self.version != 1
            or self.source_record_version < 1
            or self.risk_level not in {"low", "medium", "high", "critical"}
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 8 <= len(self.idempotency_key) <= 128
            or self.created_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.created_at
            or self.state != "pending"
            or not self.separation_of_duties_required
            or self.approval_granted
            or self.decision_recorded
            or self.execution_authorized
            or self.infrastructure_mutation_performed
        ):
            raise ValueError("Connector upgrade approval request violates the authority boundary")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeApprovalDecision:
    decision_id: str
    schema_version: str
    version: int
    request_id: str
    request_version: int
    request_digest: str
    plan_id: str
    plan_digest: str
    outcome: ConnectorUpgradeApprovalOutcome
    decided_by: str
    rationale: str
    organization_id: str
    environment_id: str
    approval_policy_id: str
    approval_policy_digest: str
    decided_at: datetime
    canonical_digest: str
    decision_fingerprint: str
    idempotency_key: str
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.decision_id,
            self.schema_version,
            self.request_id,
            self.plan_id,
            self.decided_by,
            self.organization_id,
            self.environment_id,
            self.approval_policy_id,
        ):
            validate_stable_identifier(value, "connector upgrade approval decision identifier")
        for value in (
            self.request_digest,
            self.plan_digest,
            self.approval_policy_digest,
            self.canonical_digest,
            self.decision_fingerprint,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Connector upgrade approval decision digest is invalid")
        if (
            self.version != 1
            or self.request_version != 1
            or not 20 <= len(self.rationale.strip()) <= 1000
            or not 8 <= len(self.idempotency_key) <= 128
            or self.decided_at.tzinfo is None
            or self.execution_authorized
            or self.infrastructure_mutation_performed
        ):
            raise ValueError("Connector upgrade approval decision violates the authority boundary")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeApprovalRevalidation:
    revalidation_id: str
    schema_version: str
    version: int
    source_record_id: str
    source_record_version: int
    instance_id: str
    connector_id: str
    request_id: str
    request_version: int
    request_digest: str
    decision_id: str
    decision_version: int
    decision_digest: str
    plan_id: str
    plan_digest: str
    readiness_digest: str
    current_receipt_id: str
    current_receipt_digest: str
    candidate_receipt_id: str
    candidate_receipt_digest: str
    approval_policy_id: str
    approval_policy_version: str
    approval_policy_digest: str
    organization_id: str
    environment_id: str
    requester_id: str
    approver_id: str
    revalidated_by: str
    purpose: str
    check_ids: tuple[str, ...]
    revalidated_at: datetime
    valid_until: datetime
    canonical_digest: str
    revalidation_fingerprint: str
    idempotency_key: str
    approval_current_at_revalidation: bool = True
    governance_ready: bool = True
    handoff_ready: bool = False
    target_configured: bool = False
    package_rebound: bool = False
    configuration_changed: bool = False
    target_contacted: bool = False
    handoff_artifact_issued: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.revalidation_id,
            self.schema_version,
            self.source_record_id,
            self.instance_id,
            self.connector_id,
            self.request_id,
            self.decision_id,
            self.plan_id,
            self.current_receipt_id,
            self.candidate_receipt_id,
            self.approval_policy_id,
            self.approval_policy_version,
            self.organization_id,
            self.environment_id,
            self.requester_id,
            self.approver_id,
            self.revalidated_by,
        ):
            validate_stable_identifier(value, "connector upgrade approval revalidation identifier")
        for value in (
            self.request_digest,
            self.decision_digest,
            self.plan_digest,
            self.readiness_digest,
            self.current_receipt_digest,
            self.candidate_receipt_digest,
            self.approval_policy_digest,
            self.canonical_digest,
            self.revalidation_fingerprint,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Connector upgrade approval revalidation digest is invalid")
        if (
            self.version != 1
            or self.source_record_version < 1
            or self.request_version != 1
            or self.decision_version != 1
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 8 <= len(self.idempotency_key) <= 128
            or not self.check_ids
            or len(set(self.check_ids)) != len(self.check_ids)
            or any(
                not item.startswith("connector.upgrade.revalidation.") for item in self.check_ids
            )
            or self.revalidated_at.tzinfo is None
            or self.valid_until.tzinfo is None
            or self.valid_until <= self.revalidated_at
            or len({self.requester_id, self.approver_id, self.revalidated_by}) != 3
            or not self.approval_current_at_revalidation
            or not self.governance_ready
            or any(
                (
                    self.handoff_ready,
                    self.target_configured,
                    self.package_rebound,
                    self.configuration_changed,
                    self.target_contacted,
                    self.handoff_artifact_issued,
                    self.execution_authorized,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError(
                "Connector upgrade approval revalidation violates the authority boundary"
            )


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeHandoffReadinessAssessment:
    assessment_id: str
    schema_version: str
    source_record_id: str
    source_record_version: int
    instance_id: str
    connector_id: str
    request_id: str
    request_digest: str
    decision_id: str
    decision_digest: str
    revalidation_id: str
    revalidation_digest: str
    plan_id: str
    plan_digest: str
    organization_id: str
    environment_id: str
    assessed_by: str
    applicability_policy_id: str
    applicability_policy_version: str
    applicability_policy_digest: str
    audit_readiness_evidence_id: str | None
    audit_readiness_evidence_digest: str | None
    itsm_change_evidence_id: str | None
    itsm_change_evidence_digest: str | None
    maintenance_window_evidence_id: str | None
    maintenance_window_evidence_digest: str | None
    required_check_ids: tuple[str, ...]
    satisfied_check_ids: tuple[str, ...]
    not_applicable_check_ids: tuple[str, ...]
    blocker_ids: tuple[str, ...]
    assessed_at: datetime
    evidence_valid_until: datetime
    canonical_digest: str
    assessment_state: str = "blocked"
    approval_current: bool = True
    revalidation_current: bool = True
    audit_readiness_evidence_current: bool = False
    itsm_change_evidence_current: bool = False
    maintenance_window_evidence_current: bool = False
    handoff_ready: bool = False
    handoff_artifact_issued: bool = False
    approval_consumed: bool = False
    target_contacted: bool = False
    package_rebound: bool = False
    configuration_changed: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.assessment_id,
            self.schema_version,
            self.source_record_id,
            self.instance_id,
            self.connector_id,
            self.request_id,
            self.decision_id,
            self.revalidation_id,
            self.plan_id,
            self.organization_id,
            self.environment_id,
            self.assessed_by,
            self.applicability_policy_id,
            self.applicability_policy_version,
        ):
            validate_stable_identifier(value, "connector upgrade handoff readiness identifier")
        for value in (
            self.request_digest,
            self.decision_digest,
            self.revalidation_digest,
            self.plan_digest,
            self.applicability_policy_digest,
            self.canonical_digest,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Connector upgrade handoff readiness digest is invalid")
        if self.audit_readiness_evidence_id is not None:
            validate_stable_identifier(
                self.audit_readiness_evidence_id,
                "connector upgrade audit readiness evidence identifier",
            )
        if (self.audit_readiness_evidence_id is None) != (
            self.audit_readiness_evidence_digest is None
        ) or (
            self.audit_readiness_evidence_digest is not None
            and _DIGEST.fullmatch(self.audit_readiness_evidence_digest) is None
        ):
            raise ValueError("Connector upgrade audit readiness evidence binding is invalid")
        if self.itsm_change_evidence_id is not None:
            validate_stable_identifier(
                self.itsm_change_evidence_id,
                "connector upgrade ITSM change evidence identifier",
            )
        if (self.itsm_change_evidence_id is None) != (self.itsm_change_evidence_digest is None) or (
            self.itsm_change_evidence_digest is not None
            and _DIGEST.fullmatch(self.itsm_change_evidence_digest) is None
        ):
            raise ValueError("Connector upgrade ITSM change evidence binding is invalid")
        if self.maintenance_window_evidence_id is not None:
            validate_stable_identifier(
                self.maintenance_window_evidence_id,
                "connector upgrade maintenance window evidence identifier",
            )
        if (self.maintenance_window_evidence_id is None) != (
            self.maintenance_window_evidence_digest is None
        ) or (
            self.maintenance_window_evidence_digest is not None
            and _DIGEST.fullmatch(self.maintenance_window_evidence_digest) is None
        ):
            raise ValueError("Connector upgrade maintenance window evidence binding is invalid")
        missing_check_ids = set(self.required_check_ids).difference(self.satisfied_check_ids)
        audit_check_id = "connector.upgrade.handoff.audit-readiness-evidence-current"
        itsm_check_id = "connector.upgrade.handoff.itsm-change-current"
        window_check_id = "connector.upgrade.handoff.maintenance-window-current"
        expected_blocker_ids = {
            "connector.upgrade.handoff.blocked."
            f"{item.removeprefix('connector.upgrade.handoff.').removesuffix('-current')}-missing"
            for item in missing_check_ids
        }
        if (
            self.source_record_version < 1
            or self.assessment_state
            != ("evidence_complete" if not missing_check_ids else "blocked")
            or not self.required_check_ids
            or not self.satisfied_check_ids
            or len(set(self.required_check_ids)) != len(self.required_check_ids)
            or len(set(self.satisfied_check_ids)) != len(self.satisfied_check_ids)
            or len(set(self.not_applicable_check_ids)) != len(self.not_applicable_check_ids)
            or len(set(self.blocker_ids)) != len(self.blocker_ids)
            or not set(self.satisfied_check_ids).issubset(self.required_check_ids)
            or set(self.required_check_ids).intersection(self.not_applicable_check_ids)
            or set(self.blocker_ids) != expected_blocker_ids
            or any(
                not item.startswith("connector.upgrade.handoff.")
                for item in self.required_check_ids
            )
            or any(
                not item.startswith("connector.upgrade.handoff.")
                for item in self.satisfied_check_ids
            )
            or any(
                not item.startswith("connector.upgrade.handoff.")
                for item in self.not_applicable_check_ids
            )
            or any(
                not item.startswith("connector.upgrade.handoff.blocked.")
                for item in self.blocker_ids
            )
            or self.assessed_at.tzinfo is None
            or self.evidence_valid_until.tzinfo is None
            or self.evidence_valid_until <= self.assessed_at
            or not self.approval_current
            or not self.revalidation_current
            or self.audit_readiness_evidence_current
            != (self.audit_readiness_evidence_id is not None)
            or self.audit_readiness_evidence_current != (audit_check_id in self.satisfied_check_ids)
            or self.itsm_change_evidence_current != (self.itsm_change_evidence_id is not None)
            or self.itsm_change_evidence_current != (itsm_check_id in self.satisfied_check_ids)
            or self.maintenance_window_evidence_current
            != (self.maintenance_window_evidence_id is not None)
            or self.maintenance_window_evidence_current
            != (window_check_id in self.satisfied_check_ids)
            or any(
                (
                    self.handoff_ready,
                    self.handoff_artifact_issued,
                    self.approval_consumed,
                    self.target_contacted,
                    self.package_rebound,
                    self.configuration_changed,
                    self.execution_authorized,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Connector upgrade handoff readiness violates the authority boundary")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeEvidenceReceipt:
    receipt_id: str
    schema_version: str
    version: int
    assessment_id: str
    assessment_digest: str
    request_id: str
    request_digest: str
    decision_id: str
    decision_digest: str
    revalidation_id: str
    revalidation_digest: str
    plan_id: str
    plan_digest: str
    organization_id: str
    environment_id: str
    created_by: str
    audit_readiness_evidence_id: str
    audit_readiness_evidence_digest: str
    itsm_change_evidence_id: str
    itsm_change_evidence_digest: str
    maintenance_window_evidence_id: str
    maintenance_window_evidence_digest: str
    required_check_ids: tuple[str, ...]
    satisfied_check_ids: tuple[str, ...]
    not_applicable_check_ids: tuple[str, ...]
    created_at: datetime
    valid_until: datetime
    canonical_digest: str
    evidence_receipt_only: bool = True
    runtime_acceptable: bool = False
    approval_consumed: bool = False
    handoff_ready: bool = False
    handoff_artifact_issued: bool = False
    target_contacted: bool = False
    package_rebound: bool = False
    configuration_changed: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        identifiers = (
            self.receipt_id,
            self.schema_version,
            self.assessment_id,
            self.request_id,
            self.decision_id,
            self.revalidation_id,
            self.plan_id,
            self.organization_id,
            self.environment_id,
            self.created_by,
            self.audit_readiness_evidence_id,
            self.itsm_change_evidence_id,
            self.maintenance_window_evidence_id,
        )
        for value in identifiers:
            validate_stable_identifier(value, "connector upgrade evidence receipt identifier")
        digests = (
            self.assessment_digest,
            self.request_digest,
            self.decision_digest,
            self.revalidation_digest,
            self.plan_digest,
            self.audit_readiness_evidence_digest,
            self.itsm_change_evidence_digest,
            self.maintenance_window_evidence_digest,
            self.canonical_digest,
        )
        if any(_DIGEST.fullmatch(value) is None for value in digests):
            raise ValueError("Connector upgrade evidence receipt digest is invalid")
        if (
            self.schema_version != "atlas.connector-upgrade-evidence-receipt.v1"
            or self.version != 1
            or not self.required_check_ids
            or self.required_check_ids != self.satisfied_check_ids
            or len(set(self.required_check_ids)) != len(self.required_check_ids)
            or len(set(self.not_applicable_check_ids)) != len(self.not_applicable_check_ids)
            or set(self.required_check_ids).intersection(self.not_applicable_check_ids)
            or self.created_at.tzinfo is None
            or self.valid_until.tzinfo is None
            or self.created_at >= self.valid_until
            or not self.evidence_receipt_only
            or any(
                (
                    self.runtime_acceptable,
                    self.approval_consumed,
                    self.handoff_ready,
                    self.handoff_artifact_issued,
                    self.target_contacted,
                    self.package_rebound,
                    self.configuration_changed,
                    self.execution_authorized,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Connector upgrade evidence receipt violates the authority boundary")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeEvidenceReceiptVerification:
    verification_id: str
    schema_version: str
    receipt_id: str
    receipt_digest: str
    request_id: str
    organization_id: str
    environment_id: str
    verified_by: str
    verified_at: datetime
    receipt_valid_until: datetime
    verification_state: ConnectorUpgradeEvidenceReceiptVerificationState
    reason_codes: tuple[str, ...]
    canonical_digest: str
    integrity_valid: bool = True
    current_state_compared: bool = False
    current_state_matches: bool = False
    receipt_expired: bool = False
    authenticity_proven: bool = False
    evidence_receipt_only: bool = True
    approval_consumed: bool = False
    handoff_ready: bool = False
    handoff_artifact_issued: bool = False
    target_contacted: bool = False
    package_rebound: bool = False
    configuration_changed: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.verification_id,
            self.schema_version,
            self.receipt_id,
            self.request_id,
            self.organization_id,
            self.environment_id,
            self.verified_by,
        ):
            validate_stable_identifier(value, "connector upgrade evidence receipt verification")
        if (
            self.schema_version != "atlas.connector-upgrade-evidence-receipt-verification.v1"
            or _DIGEST.fullmatch(self.receipt_digest) is None
            or _DIGEST.fullmatch(self.canonical_digest) is None
            or self.verified_at.tzinfo is None
            or self.receipt_valid_until.tzinfo is None
            or not self.reason_codes
            or any(
                not reason.startswith("connector.upgrade.evidence-receipt.")
                for reason in self.reason_codes
            )
            or not self.integrity_valid
            or self.authenticity_proven
            or not self.evidence_receipt_only
            or any(
                (
                    self.approval_consumed,
                    self.handoff_ready,
                    self.handoff_artifact_issued,
                    self.target_contacted,
                    self.package_rebound,
                    self.configuration_changed,
                    self.execution_authorized,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Connector upgrade evidence receipt verification is invalid")
        expected_state = {
            ConnectorUpgradeEvidenceReceiptVerificationState.CURRENT: (
                True,
                True,
                False,
            ),
            ConnectorUpgradeEvidenceReceiptVerificationState.STALE: (
                True,
                False,
                False,
            ),
            ConnectorUpgradeEvidenceReceiptVerificationState.EXPIRED: (
                False,
                False,
                True,
            ),
            ConnectorUpgradeEvidenceReceiptVerificationState.UNVERIFIABLE: (
                False,
                False,
                False,
            ),
        }[self.verification_state]
        if expected_state != (
            self.current_state_compared,
            self.current_state_matches,
            self.receipt_expired,
        ):
            raise ValueError("Connector upgrade evidence receipt verification state is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeAuditReadinessEvidence:
    evidence_id: str
    schema_version: str
    organization_id: str
    environment_id: str
    request_id: str
    request_digest: str
    revalidation_id: str
    revalidation_digest: str
    ledger_id: str
    ledger_generation: str
    producer_coverage_digest: str
    integrity_verification_digest: str
    redaction_policy_digest: str
    retention_policy_digest: str
    verified_at: datetime
    valid_until: datetime
    canonical_digest: str
    durable_acceptance: bool
    append_only: bool
    integrity_verified: bool
    gap_free: bool
    redaction_current: bool
    retention_current: bool
    producer_coverage_complete: bool
    consequential_blocking_enabled: bool
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.evidence_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.request_id,
            self.revalidation_id,
            self.ledger_id,
            self.ledger_generation,
        ):
            validate_stable_identifier(value, "connector upgrade audit readiness identifier")
        for value in (
            self.request_digest,
            self.revalidation_digest,
            self.producer_coverage_digest,
            self.integrity_verification_digest,
            self.redaction_policy_digest,
            self.retention_policy_digest,
            self.canonical_digest,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Connector upgrade audit readiness digest is invalid")
        if (
            self.verified_at.tzinfo is None
            or self.valid_until.tzinfo is None
            or self.valid_until <= self.verified_at
            or not all(
                (
                    self.durable_acceptance,
                    self.append_only,
                    self.integrity_verified,
                    self.gap_free,
                    self.redaction_current,
                    self.retention_current,
                    self.producer_coverage_complete,
                    self.consequential_blocking_enabled,
                )
            )
            or self.infrastructure_mutation_performed
        ):
            raise ValueError("Connector upgrade audit readiness evidence is not authoritative")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeItsmChangeEvidence:
    evidence_id: str
    schema_version: str
    organization_id: str
    environment_id: str
    request_id: str
    request_digest: str
    revalidation_id: str
    revalidation_digest: str
    plan_id: str
    plan_digest: str
    adapter_id: str
    adapter_version: str
    authoritative_instance_id: str
    external_record_id: str
    external_record_version: str
    observed_at: datetime
    valid_until: datetime
    canonical_digest: str
    adapter_validated: bool
    authoritative_source: bool
    record_accessible: bool
    source_version_current: bool
    exact_plan_binding_verified: bool
    record_active: bool
    conflict_free: bool
    revocation_absent: bool
    external_record_modified: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.evidence_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.request_id,
            self.revalidation_id,
            self.plan_id,
            self.adapter_id,
            self.adapter_version,
            self.authoritative_instance_id,
            self.external_record_id,
            self.external_record_version,
        ):
            validate_stable_identifier(value, "connector upgrade ITSM change identifier")
        for value in (
            self.request_digest,
            self.revalidation_digest,
            self.plan_digest,
            self.canonical_digest,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Connector upgrade ITSM change digest is invalid")
        if (
            self.observed_at.tzinfo is None
            or self.valid_until.tzinfo is None
            or self.valid_until <= self.observed_at
            or not all(
                (
                    self.adapter_validated,
                    self.authoritative_source,
                    self.record_accessible,
                    self.source_version_current,
                    self.exact_plan_binding_verified,
                    self.record_active,
                    self.conflict_free,
                    self.revocation_absent,
                )
            )
            or self.external_record_modified
            or self.infrastructure_mutation_performed
        ):
            raise ValueError("Connector upgrade ITSM change evidence is not authoritative")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeMaintenanceWindowEvidence:
    evidence_id: str
    schema_version: str
    organization_id: str
    environment_id: str
    request_id: str
    request_digest: str
    revalidation_id: str
    revalidation_digest: str
    plan_id: str
    plan_digest: str
    itsm_change_evidence_id: str
    itsm_change_evidence_digest: str
    external_record_version: str
    window_version: str
    approved_start: datetime
    approved_end: datetime
    observed_at: datetime
    valid_until: datetime
    canonical_digest: str
    authoritative_source: bool
    window_approved: bool
    source_version_current: bool
    exact_change_binding_verified: bool
    exact_plan_binding_verified: bool
    inside_approved_window: bool
    freeze_clear: bool
    conflict_free: bool
    revocation_absent: bool
    external_record_modified: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.evidence_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.request_id,
            self.revalidation_id,
            self.plan_id,
            self.itsm_change_evidence_id,
            self.external_record_version,
            self.window_version,
        ):
            validate_stable_identifier(value, "connector upgrade maintenance window identifier")
        for value in (
            self.request_digest,
            self.revalidation_digest,
            self.plan_digest,
            self.itsm_change_evidence_digest,
            self.canonical_digest,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Connector upgrade maintenance window digest is invalid")
        if (
            any(
                value.tzinfo is None
                for value in (
                    self.approved_start,
                    self.approved_end,
                    self.observed_at,
                    self.valid_until,
                )
            )
            or not self.approved_start <= self.observed_at < self.approved_end
            or not self.observed_at < self.valid_until <= self.approved_end
            or not all(
                (
                    self.authoritative_source,
                    self.window_approved,
                    self.source_version_current,
                    self.exact_change_binding_verified,
                    self.exact_plan_binding_verified,
                    self.inside_approved_window,
                    self.freeze_clear,
                    self.conflict_free,
                    self.revocation_absent,
                )
            )
            or self.external_record_modified
            or self.infrastructure_mutation_performed
        ):
            raise ValueError("Connector upgrade maintenance window evidence is not authoritative")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeChangeContextDraft:
    draft_id: str
    schema_version: str
    source_record_id: str
    source_record_version: int
    instance_id: str
    connector_id: str
    request_id: str
    request_digest: str
    decision_digest: str
    revalidation_id: str
    revalidation_digest: str
    readiness_digest: str
    organization_id: str
    environment_id: str
    created_by: str
    justification: str
    proposed_window_start: datetime
    proposed_window_end: datetime
    itsm_draft_title: str
    itsm_draft_digest: str
    request_fingerprint: str
    idempotency_key: str
    created_at: datetime
    valid_until: datetime
    canonical_digest: str
    state: str = "draft"
    itsm_dispatched: bool = False
    window_approved: bool = False
    handoff_ready: bool = False
    handoff_artifact_issued: bool = False
    approval_consumed: bool = False
    target_contacted: bool = False
    package_rebound: bool = False
    configuration_changed: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        identifiers = (
            self.draft_id,
            self.schema_version,
            self.source_record_id,
            self.instance_id,
            self.connector_id,
            self.request_id,
            self.revalidation_id,
            self.organization_id,
            self.environment_id,
            self.created_by,
            self.idempotency_key,
        )
        digests = (
            self.request_digest,
            self.decision_digest,
            self.revalidation_digest,
            self.readiness_digest,
            self.itsm_draft_digest,
            self.request_fingerprint,
            self.canonical_digest,
        )
        for value in identifiers:
            validate_stable_identifier(value, "connector upgrade change-context identifier")
        if (
            any(_DIGEST.fullmatch(value) is None for value in digests)
            or self.source_record_version < 1
            or not 20 <= len(self.justification) <= 1000
            or not 12 <= len(self.itsm_draft_title) <= 160
            or self.proposed_window_start.tzinfo is None
            or self.proposed_window_end.tzinfo is None
            or self.proposed_window_start >= self.proposed_window_end
            or self.created_at.tzinfo is None
            or self.valid_until.tzinfo is None
            or not self.created_at < self.valid_until
            or self.state != "draft"
            or any(
                (
                    self.itsm_dispatched,
                    self.window_approved,
                    self.handoff_ready,
                    self.handoff_artifact_issued,
                    self.approval_consumed,
                    self.target_contacted,
                    self.package_rebound,
                    self.configuration_changed,
                    self.execution_authorized,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError(
                "Connector upgrade change-context draft violates the authority boundary"
            )


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeApprovalRecord:
    request: ConnectorUpgradeApprovalRequest
    decision: ConnectorUpgradeApprovalDecision | None
    state: ConnectorUpgradeApprovalState
    approval_valid: bool
    approval_granted: bool
    decision_recorded: bool
    separation_of_duties_enforced: bool = True
    package_rebound: bool = False
    configuration_changed: bool = False
    target_contacted: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        approved = self.state is ConnectorUpgradeApprovalState.APPROVED and self.approval_valid
        if (
            self.approval_granted != approved
            or self.decision_recorded != (self.decision is not None)
            or not self.separation_of_duties_enforced
            or any(
                (
                    self.package_rebound,
                    self.configuration_changed,
                    self.target_contacted,
                    self.execution_authorized,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Connector upgrade approval record violates the authority boundary")

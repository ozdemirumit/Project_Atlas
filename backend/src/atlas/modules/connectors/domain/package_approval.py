from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class PackageApprovalOutcome(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_EVIDENCE = "needs_evidence"
    DEFER = "defer"


class PackageApprovalState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_EVIDENCE = "needs_evidence"
    DEFERRED = "deferred"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class ConnectorPackageApprovalPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_final_validation_schema: str
    maximum_final_validation_age_hours: int
    request_lifetime_minutes: int
    required_assurance_level: AssuranceLevel
    stage_count: int
    quorum: int
    permitted_outcomes: tuple[PackageApprovalOutcome, ...]
    minimum_rationale_length: int
    maximum_rationale_length: int
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
            self.required_final_validation_schema,
            self.signed_by,
        ):
            validate_stable_identifier(value, "package approval policy identifier")
        if (
            self.version != 1
            or not 1 <= self.maximum_final_validation_age_hours <= 87600
            or not 5 <= self.request_lifetime_minutes <= 10080
            or self.required_assurance_level
            not in {AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED}
            or self.stage_count != 1
            or self.quorum != 1
            or self.permitted_outcomes != tuple(PackageApprovalOutcome)
            or not 1 <= self.minimum_rationale_length <= self.maximum_rationale_length <= 4000
            or not self.signature_verified
        ):
            raise ValueError("Package approval policy contract is invalid")
        if (
            self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Package approval policy evidence is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageApprovalRequest:
    request_id: str
    schema_version: str
    version: int
    source_final_validation_id: str
    source_final_validation_digest: str
    source_handoff_id: str
    source_project_id: str
    source_actor_set_digest: str
    organization_id: str
    environment_id: str
    requested_by: str
    purpose: str
    approval_policy_id: str
    approval_policy_digest: str
    approval_policy_version: str
    package_digest: str
    inventory_digest: str
    product_family: str
    observed_product_version: str
    evidence_digest: str
    final_policy_id: str
    final_policy_digest: str
    final_policy_version: str
    stage_count: int
    passed_stage_count: int
    finding_count: int
    limitation_count: int
    blocking_risk_count: int
    created_at: datetime
    expires_at: datetime
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    final_validation_completed: bool = True
    connector_approved: bool = False
    connector_rejected: bool = False
    eligible_for_publisher_governance: bool = False
    promotion_blocked: bool = True
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.request_id,
            self.schema_version,
            self.source_final_validation_id,
            self.source_handoff_id,
            self.source_project_id,
            self.organization_id,
            self.environment_id,
            self.requested_by,
            self.approval_policy_id,
            self.approval_policy_version,
            self.product_family,
            self.final_policy_id,
            self.final_policy_version,
        ):
            validate_stable_identifier(value, "package approval request identifier")
        for value in (
            self.source_final_validation_digest,
            self.source_actor_set_digest,
            self.approval_policy_digest,
            self.package_digest,
            self.inventory_digest,
            self.evidence_digest,
            self.final_policy_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Package approval request digest is invalid")
        if (
            self.version != 1
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 8 <= len(self.idempotency_key) <= 128
            or self.created_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.created_at
            or self.stage_count <= 0
            or self.passed_stage_count != self.stage_count
            or min(self.finding_count, self.limitation_count, self.blocking_risk_count) < 0
            or self.blocking_risk_count != 0
            or not self.final_validation_completed
            or any(
                (
                    self.connector_approved,
                    self.connector_rejected,
                    self.eligible_for_publisher_governance,
                )
            )
            or not self.promotion_blocked
        ):
            raise ValueError("Package approval request contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageApprovalDecision:
    decision_id: str
    schema_version: str
    version: int
    request_id: str
    request_version: int
    request_digest: str
    outcome: PackageApprovalOutcome
    decided_by: str
    rationale: str
    organization_id: str
    environment_id: str
    source_final_validation_id: str
    source_final_validation_digest: str
    package_digest: str
    approval_policy_id: str
    approval_policy_digest: str
    decided_at: datetime
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.decision_id,
            self.schema_version,
            self.request_id,
            self.decided_by,
            self.organization_id,
            self.environment_id,
            self.source_final_validation_id,
            self.approval_policy_id,
        ):
            validate_stable_identifier(value, "package approval decision identifier")
        for value in (
            self.request_digest,
            self.source_final_validation_digest,
            self.package_digest,
            self.approval_policy_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Package approval decision digest is invalid")
        if (
            self.version != 1
            or self.request_version != 1
            or not self.rationale.strip()
            or len(self.rationale) > 4000
            or not 8 <= len(self.idempotency_key) <= 128
            or self.decided_at.tzinfo is None
        ):
            raise ValueError("Package approval decision contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageApprovalRecord:
    request: ConnectorPackageApprovalRequest
    decision: ConnectorPackageApprovalDecision | None
    state: PackageApprovalState
    approval_valid: bool
    connector_approved: bool
    connector_rejected: bool
    eligible_for_publisher_governance: bool
    promotion_blocked: bool
    package_signed: bool = False
    publisher_attested: bool = False
    connector_registered: bool = False
    connector_installed: bool = False
    connector_enabled: bool = False
    target_configured: bool = False
    credentials_resolved: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        approved = self.state is PackageApprovalState.APPROVED and self.approval_valid
        rejected = self.state is PackageApprovalState.REJECTED
        if (
            self.connector_approved != approved
            or self.eligible_for_publisher_governance != approved
            or self.connector_rejected != rejected
            or self.promotion_blocked == approved
            or any(
                (
                    self.package_signed,
                    self.publisher_attested,
                    self.connector_registered,
                    self.connector_installed,
                    self.connector_enabled,
                    self.target_configured,
                    self.credentials_resolved,
                    self.runtime_trust_granted,
                    self.execution_authorized,
                    self.deployment_approved,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Package approval projection violates the authority boundary")

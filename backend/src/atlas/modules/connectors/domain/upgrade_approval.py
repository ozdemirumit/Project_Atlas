from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")


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
            not in {AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED}
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

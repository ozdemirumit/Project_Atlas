from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class BuilderSecurityReviewState(StrEnum):
    ACCEPTED = "accepted"
    NEEDS_REMEDIATION = "needs_remediation"
    REJECTED = "rejected"


class BuilderSecurityControlDecisionKind(StrEnum):
    ACCEPTED = "accepted"
    NEEDS_REMEDIATION = "needs_remediation"
    REJECTED = "rejected"


class BuilderSecurityControl(StrEnum):
    PROVENANCE = "provenance"
    SUPPLY_CHAIN = "supply_chain"
    CREDENTIALS = "credentials"
    NETWORK = "network"
    INPUT_OUTPUT = "input_output"
    INJECTION_EXECUTION = "injection_execution"
    LOGGING_REDACTION = "logging_redaction"
    RUNNER_PRIVILEGES = "runner_privileges"
    CAPABILITY_GOVERNANCE = "capability_governance"


@dataclass(frozen=True, slots=True)
class BuilderSecurityControlAssessment:
    control: BuilderSecurityControl
    decision: BuilderSecurityControlDecisionKind
    assessment: str
    evidence_references: tuple[str, ...]
    finding_codes: tuple[str, ...]
    required_controls: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.assessment.strip() or len(self.assessment) > 1600:
            raise ValueError("Builder security assessment is outside platform bounds")
        if (
            not 1 <= len(self.evidence_references) <= 30
            or len(self.evidence_references) != len(set(self.evidence_references))
            or any(not value.strip() or len(value) > 500 for value in self.evidence_references)
        ):
            raise ValueError("Builder security evidence references are invalid")
        if len(self.finding_codes) > 30 or len(self.finding_codes) != len(set(self.finding_codes)):
            raise ValueError("Builder security finding codes are invalid")
        for code in self.finding_codes:
            validate_stable_identifier(code, "security review finding code")
        if (
            not 1 <= len(self.required_controls) <= 30
            or len(self.required_controls) != len(set(self.required_controls))
            or any(not value.strip() or len(value) > 500 for value in self.required_controls)
        ):
            raise ValueError("Builder security required controls are invalid")
        if self.decision is BuilderSecurityControlDecisionKind.ACCEPTED:
            if self.finding_codes:
                raise ValueError("Accepted security control cannot retain findings")
        elif not self.finding_codes:
            raise ValueError("Non-accepted security control requires a finding")


@dataclass(frozen=True, slots=True)
class McpBuilderSecurityReview:
    review_id: str
    schema_version: str
    version: int
    state: BuilderSecurityReviewState
    project_id: str
    project_version: int
    project_digest: str
    source_digest: str
    checkpoint_id: str
    checkpoint_digest: str
    generation_id: str
    generation_digest: str
    artifact_digest: str
    validation_id: str
    validation_digest: str
    validation_profile: str
    validator_version: str
    domain_review_id: str
    domain_review_digest: str
    domain_review_profile: str
    domain_reviewer_contract_version: str
    domain_reviewed_by: str
    organization_id: str
    environment_id: str
    reviewed_by: str
    review_profile: str
    reviewer_contract_version: str
    control_assessments: tuple[BuilderSecurityControlAssessment, ...]
    accepted_count: int
    needs_remediation_count: int
    rejected_count: int
    summary: str
    limitations: tuple[str, ...]
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    completed_at: datetime
    security_review_completed: bool = True
    security_review_accepted: bool = False
    lab_validation_completed: bool = False
    candidate_package_created: bool = False
    connector_registered: bool = False
    connector_installed: bool = False
    connector_enabled: bool = False
    network_request_performed: bool = False
    model_inference_performed: bool = False
    dependency_resolution_performed: bool = False
    malware_or_dynamic_scan_performed: bool = False
    runtime_self_test_performed: bool = False
    subprocess_invoked: bool = False
    dynamic_code_execution_performed: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value, name in (
            (self.review_id, "security review id"),
            (self.schema_version, "schema version"),
            (self.project_id, "project id"),
            (self.checkpoint_id, "checkpoint id"),
            (self.generation_id, "generation id"),
            (self.validation_id, "validation id"),
            (self.validation_profile, "validation profile"),
            (self.validator_version, "validator version"),
            (self.domain_review_id, "domain review id"),
            (self.domain_review_profile, "domain review profile"),
            (self.domain_reviewer_contract_version, "domain reviewer contract version"),
            (self.domain_reviewed_by, "domain reviewer id"),
            (self.organization_id, "organization id"),
            (self.environment_id, "environment id"),
            (self.reviewed_by, "security reviewer id"),
            (self.review_profile, "security review profile"),
            (self.reviewer_contract_version, "security reviewer contract version"),
        ):
            validate_stable_identifier(value, name)
        if self.version != 1 or self.project_version != 1:
            raise ValueError("Builder security review version is invalid")
        for value in (
            self.project_digest,
            self.source_digest,
            self.checkpoint_digest,
            self.generation_digest,
            self.artifact_digest,
            self.validation_digest,
            self.domain_review_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Builder security review digest is invalid")
        expected_controls = set(BuilderSecurityControl)
        actual_controls = {item.control for item in self.control_assessments}
        if (
            len(self.control_assessments) != len(expected_controls)
            or actual_controls != expected_controls
        ):
            raise ValueError("Builder security review controls are incomplete")
        expected_counts = (
            sum(
                item.decision is BuilderSecurityControlDecisionKind.ACCEPTED
                for item in self.control_assessments
            ),
            sum(
                item.decision is BuilderSecurityControlDecisionKind.NEEDS_REMEDIATION
                for item in self.control_assessments
            ),
            sum(
                item.decision is BuilderSecurityControlDecisionKind.REJECTED
                for item in self.control_assessments
            ),
        )
        if (
            self.accepted_count,
            self.needs_remediation_count,
            self.rejected_count,
        ) != expected_counts:
            raise ValueError("Builder security review totals are invalid")
        expected_state = (
            BuilderSecurityReviewState.REJECTED
            if self.rejected_count
            else (
                BuilderSecurityReviewState.NEEDS_REMEDIATION
                if self.needs_remediation_count
                else BuilderSecurityReviewState.ACCEPTED
            )
        )
        if self.state is not expected_state:
            raise ValueError("Builder security review state is inconsistent")
        if self.security_review_accepted != (self.state is BuilderSecurityReviewState.ACCEPTED):
            raise ValueError("Builder security review acceptance is inconsistent")
        if self.reviewed_by == self.domain_reviewed_by:
            raise ValueError("Builder security review violates separation of duties")
        if not self.summary.strip() or len(self.summary) > 1800:
            raise ValueError("Builder security review summary is outside platform bounds")
        if (
            not 1 <= len(self.limitations) <= 20
            or len(self.limitations) != len(set(self.limitations))
            or any(not value.strip() or len(value) > 500 for value in self.limitations)
        ):
            raise ValueError("Builder security review limitations are invalid")
        if self.completed_at.tzinfo is None or not 8 <= len(self.idempotency_key) <= 128:
            raise ValueError("Builder security review timestamp or idempotency key is invalid")
        if not self.security_review_completed:
            raise ValueError("Builder security review must be complete")
        if any(
            (
                self.lab_validation_completed,
                self.candidate_package_created,
                self.connector_registered,
                self.connector_installed,
                self.connector_enabled,
                self.network_request_performed,
                self.model_inference_performed,
                self.dependency_resolution_performed,
                self.malware_or_dynamic_scan_performed,
                self.runtime_self_test_performed,
                self.subprocess_invoked,
                self.dynamic_code_execution_performed,
                self.runtime_trust_granted,
                self.execution_authorized,
                self.infrastructure_mutation_performed,
            )
        ):
            raise ValueError("Builder security review violates the no-authority boundary")

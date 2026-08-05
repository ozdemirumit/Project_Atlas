from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.capabilities import CapabilityClass
from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class BuilderDomainReviewState(StrEnum):
    ACCEPTED = "accepted"
    NEEDS_EVIDENCE = "needs_evidence"
    REJECTED = "rejected"


class BuilderDomainCapabilityDecisionKind(StrEnum):
    ACCEPTED = "accepted"
    NEEDS_EVIDENCE = "needs_evidence"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class BuilderDomainCapabilityDecision:
    candidate_id: str
    confirmed_class: CapabilityClass
    decision: BuilderDomainCapabilityDecisionKind
    supported_product_versions: tuple[str, ...]
    vendor_permission: str
    authentication_assessment: str
    side_effect_assessment: str
    error_behavior_assessment: str
    health_guidance_assessment: str
    evidence_citations: tuple[str, ...]
    missing_case_codes: tuple[str, ...]
    rationale: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.candidate_id, "domain review candidate id")
        if self.confirmed_class not in {
            CapabilityClass.C0_INFORMATIONAL,
            CapabilityClass.C1_READ_ONLY,
            CapabilityClass.C5_DESTRUCTIVE,
        }:
            raise ValueError("Builder domain review class is unsupported")
        if (
            not 1 <= len(self.supported_product_versions) <= 20
            or len(self.supported_product_versions) != len(set(self.supported_product_versions))
            or any(
                not value.strip() or len(value) > 100 for value in self.supported_product_versions
            )
        ):
            raise ValueError("Builder domain review product versions are invalid")
        if not self.vendor_permission.strip() or len(self.vendor_permission) > 160:
            raise ValueError("Builder domain review permission is invalid")
        for value, name in (
            (self.authentication_assessment, "authentication assessment"),
            (self.side_effect_assessment, "side-effect assessment"),
            (self.error_behavior_assessment, "error-behavior assessment"),
            (self.health_guidance_assessment, "health-guidance assessment"),
            (self.rationale, "rationale"),
        ):
            if not value.strip() or len(value) > 1200:
                raise ValueError(f"Builder domain review {name} is outside platform bounds")
        if (
            not 1 <= len(self.evidence_citations) <= 20
            or len(self.evidence_citations) != len(set(self.evidence_citations))
            or any(not value.strip() or len(value) > 500 for value in self.evidence_citations)
        ):
            raise ValueError("Builder domain review citations are invalid")
        if len(self.missing_case_codes) > 20 or len(self.missing_case_codes) != len(
            set(self.missing_case_codes)
        ):
            raise ValueError("Builder domain review missing-case codes are invalid")
        for code in self.missing_case_codes:
            validate_stable_identifier(code, "domain review missing-case code")
        if self.decision is BuilderDomainCapabilityDecisionKind.ACCEPTED:
            if self.missing_case_codes:
                raise ValueError("Accepted domain decision cannot retain evidence gaps")
        elif not self.missing_case_codes:
            raise ValueError("Non-accepted domain decision requires an evidence gap")


@dataclass(frozen=True, slots=True)
class McpBuilderDomainReview:
    review_id: str
    schema_version: str
    version: int
    state: BuilderDomainReviewState
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
    organization_id: str
    environment_id: str
    reviewed_by: str
    review_profile: str
    reviewer_contract_version: str
    capability_decisions: tuple[BuilderDomainCapabilityDecision, ...]
    accepted_count: int
    needs_evidence_count: int
    rejected_count: int
    summary: str
    limitations: tuple[str, ...]
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    completed_at: datetime
    domain_review_completed: bool = True
    domain_review_accepted: bool = False
    security_review_completed: bool = False
    lab_validation_completed: bool = False
    candidate_package_created: bool = False
    connector_registered: bool = False
    connector_installed: bool = False
    connector_enabled: bool = False
    network_request_performed: bool = False
    model_inference_performed: bool = False
    dependency_resolution_performed: bool = False
    runtime_self_test_performed: bool = False
    subprocess_invoked: bool = False
    dynamic_code_execution_performed: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value, name in (
            (self.review_id, "domain review id"),
            (self.schema_version, "schema version"),
            (self.project_id, "project id"),
            (self.checkpoint_id, "checkpoint id"),
            (self.generation_id, "generation id"),
            (self.validation_id, "validation id"),
            (self.validation_profile, "validation profile"),
            (self.validator_version, "validator version"),
            (self.organization_id, "organization id"),
            (self.environment_id, "environment id"),
            (self.reviewed_by, "domain reviewer id"),
            (self.review_profile, "domain review profile"),
            (self.reviewer_contract_version, "reviewer contract version"),
        ):
            validate_stable_identifier(value, name)
        if self.version != 1 or self.project_version != 1:
            raise ValueError("Builder domain review version is invalid")
        for value in (
            self.project_digest,
            self.source_digest,
            self.checkpoint_digest,
            self.generation_digest,
            self.artifact_digest,
            self.validation_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Builder domain review digest is invalid")
        if not 1 <= len(self.capability_decisions) <= 100:
            raise ValueError("Builder domain review capability count is invalid")
        candidate_ids = [item.candidate_id for item in self.capability_decisions]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Builder domain review candidates must be unique")
        expected = (
            sum(
                item.decision is BuilderDomainCapabilityDecisionKind.ACCEPTED
                for item in self.capability_decisions
            ),
            sum(
                item.decision is BuilderDomainCapabilityDecisionKind.NEEDS_EVIDENCE
                for item in self.capability_decisions
            ),
            sum(
                item.decision is BuilderDomainCapabilityDecisionKind.REJECTED
                for item in self.capability_decisions
            ),
        )
        if (self.accepted_count, self.needs_evidence_count, self.rejected_count) != expected:
            raise ValueError("Builder domain review totals are invalid")
        expected_state = (
            BuilderDomainReviewState.REJECTED
            if self.rejected_count
            else (
                BuilderDomainReviewState.NEEDS_EVIDENCE
                if self.needs_evidence_count
                else BuilderDomainReviewState.ACCEPTED
            )
        )
        if self.state is not expected_state:
            raise ValueError("Builder domain review state is inconsistent")
        if self.domain_review_accepted != (self.state is BuilderDomainReviewState.ACCEPTED):
            raise ValueError("Builder domain review acceptance is inconsistent")
        if not self.summary.strip() or len(self.summary) > 1500:
            raise ValueError("Builder domain review summary is outside platform bounds")
        if (
            not 1 <= len(self.limitations) <= 20
            or len(self.limitations) != len(set(self.limitations))
            or any(not value.strip() or len(value) > 500 for value in self.limitations)
        ):
            raise ValueError("Builder domain review limitations are invalid")
        if self.completed_at.tzinfo is None or not 8 <= len(self.idempotency_key) <= 128:
            raise ValueError("Builder domain review timestamp or idempotency key is invalid")
        if not self.domain_review_completed:
            raise ValueError("Builder domain review must be complete")
        if any(
            (
                self.security_review_completed,
                self.lab_validation_completed,
                self.candidate_package_created,
                self.connector_registered,
                self.connector_installed,
                self.connector_enabled,
                self.network_request_performed,
                self.model_inference_performed,
                self.dependency_resolution_performed,
                self.runtime_self_test_performed,
                self.subprocess_invoked,
                self.dynamic_code_execution_performed,
                self.runtime_trust_granted,
                self.execution_authorized,
                self.infrastructure_mutation_performed,
            )
        ):
            raise ValueError("Builder domain review violates the no-authority boundary")

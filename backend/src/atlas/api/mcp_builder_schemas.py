from __future__ import annotations

import re
from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from atlas.api.schemas import ResponseMeta
from atlas.core.capabilities import CapabilityClass
from atlas.core.classification import DataClassification
from atlas.modules.mcp_builder.domain.candidate_handoff import (
    CandidateCapabilityEvidence,
    McpBuilderCandidateHandoff,
)
from atlas.modules.mcp_builder.domain.design_review import (
    BuilderCapabilityDecision,
    BuilderCapabilityDecisionKind,
    BuilderEntityMapping,
    McpBuilderDesignCheckpoint,
)
from atlas.modules.mcp_builder.domain.domain_review import (
    BuilderDomainCapabilityDecision,
    BuilderDomainCapabilityDecisionKind,
    McpBuilderDomainReview,
)
from atlas.modules.mcp_builder.domain.generation import (
    BuilderGeneratedFile,
    McpBuilderGeneration,
)
from atlas.modules.mcp_builder.domain.lab_validation import (
    BuilderLabCheck,
    McpBuilderLabValidation,
)
from atlas.modules.mcp_builder.domain.models import McpBuilderProject
from atlas.modules.mcp_builder.domain.security_review import (
    BuilderSecurityControl,
    BuilderSecurityControlAssessment,
    BuilderSecurityControlDecisionKind,
    McpBuilderSecurityReview,
)
from atlas.modules.mcp_builder.domain.validation import (
    BuilderValidationCheck,
    McpBuilderValidation,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"


class McpBuilderProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(default="atlas.mcp-builder-project-request.v1", pattern=STABLE_ID)
    vendor: str = Field(min_length=1, max_length=200)
    product: str = Field(min_length=1, max_length=200)
    intended_product_versions: list[str] = Field(min_length=1, max_length=20)
    target_environment: str = Field(min_length=1, max_length=200)
    sdk_profile: str = Field(pattern=STABLE_ID)
    source_id: str = Field(pattern=STABLE_ID)
    source_authority: str = Field(min_length=1, max_length=200)
    source_owner: str = Field(min_length=1, max_length=200)
    documentation_version: str = Field(min_length=1, max_length=200)
    publication_date: date
    license_id: str = Field(min_length=1, max_length=200)
    redistribution_allowed: bool
    classification: DataClassification
    source_document: str = Field(min_length=2, max_length=524_288)
    confirmed_synthetic_or_lab_only: bool


class BuilderAuthenticationSchemeData(BaseModel):
    scheme_id: str
    scheme_type: str
    scheme: str | None
    location: str | None
    bearer_format: str | None
    requires_secret_reference: bool
    supported_for_unattended_use: bool
    finding_codes: list[str]


class BuilderCapabilityCandidateData(BaseModel):
    candidate_id: str
    operation_id: str | None
    method: str
    path: str
    summary: str
    citation: str
    proposed_capability_class: str
    side_effects: list[str]
    security_scheme_ids: list[str]
    parameter_count: int
    response_codes: list[str]
    request_body_present: bool
    confidence_basis: list[str]
    clarification_codes: list[str]
    generation_blocked: bool


class BuilderFindingData(BaseModel):
    code: str
    severity: str
    location: str
    message: str
    blocking: bool


class McpBuilderProjectData(BaseModel):
    project_id: str
    schema_version: str
    version: int
    state: str
    organization_id: str
    environment_id: str
    owner_id: str
    vendor: str
    product: str
    intended_product_versions: list[str]
    target_environment: str
    sdk_profile: str
    source_id: str
    source_authority: str
    source_owner: str
    documentation_version: str
    publication_date: date
    license_id: str
    redistribution_allowed: bool
    classification: str
    openapi_version: str
    api_title: str
    api_version: str
    source_digest: str
    source_size_bytes: int
    declared_servers: list[str]
    authentication_schemes: list[BuilderAuthenticationSchemeData]
    capability_candidates: list[BuilderCapabilityCandidateData]
    findings: list[BuilderFindingData]
    canonical_digest: str
    created_at: datetime
    analyzed_at: datetime
    reused: bool
    synthetic_or_lab_only: bool
    generated_artifact_created: bool
    candidate_package_created: bool
    connector_registered: bool
    connector_installed: bool
    connector_enabled: bool
    network_request_performed: bool
    model_inference_performed: bool
    dynamic_code_execution_performed: bool
    runtime_trust_granted: bool

    @classmethod
    def from_domain(cls, project: McpBuilderProject) -> McpBuilderProjectData:
        return cls(
            **{
                field: getattr(project, field)
                for field in cls.model_fields
                if field
                not in {
                    "state",
                    "classification",
                    "intended_product_versions",
                    "declared_servers",
                    "authentication_schemes",
                    "capability_candidates",
                    "findings",
                }
            },
            state=project.state.value,
            classification=project.classification.value,
            intended_product_versions=list(project.intended_product_versions),
            declared_servers=list(project.declared_servers),
            authentication_schemes=[
                BuilderAuthenticationSchemeData(
                    scheme_id=item.scheme_id,
                    scheme_type=item.scheme_type,
                    scheme=item.scheme,
                    location=item.location,
                    bearer_format=item.bearer_format,
                    requires_secret_reference=item.requires_secret_reference,
                    supported_for_unattended_use=item.supported_for_unattended_use,
                    finding_codes=list(item.finding_codes),
                )
                for item in project.authentication_schemes
            ],
            capability_candidates=[
                BuilderCapabilityCandidateData(
                    candidate_id=item.candidate_id,
                    operation_id=item.operation_id,
                    method=item.method,
                    path=item.path,
                    summary=item.summary,
                    citation=item.citation,
                    proposed_capability_class=item.proposed_capability_class.value,
                    side_effects=list(item.side_effects),
                    security_scheme_ids=list(item.security_scheme_ids),
                    parameter_count=item.parameter_count,
                    response_codes=list(item.response_codes),
                    request_body_present=item.request_body_present,
                    confidence_basis=list(item.confidence_basis),
                    clarification_codes=list(item.clarification_codes),
                    generation_blocked=item.generation_blocked,
                )
                for item in project.capability_candidates
            ],
            findings=[
                BuilderFindingData(
                    code=item.code,
                    severity=item.severity.value,
                    location=item.location,
                    message=item.message,
                    blocking=item.blocking,
                )
                for item in project.findings
            ],
        )


class McpBuilderProjectResponse(BaseModel):
    data: McpBuilderProjectData
    meta: ResponseMeta


class BuilderEntityMappingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_entity: str = Field(pattern=STABLE_ID)
    atlas_entity: str = Field(pattern=STABLE_ID)


class BuilderCapabilityDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: str = Field(pattern=STABLE_ID)
    decision: BuilderCapabilityDecisionKind
    analyzed_class: CapabilityClass
    confirmed_class: CapabilityClass
    required_permission: str = Field(min_length=1, max_length=160)
    rationale: str = Field(min_length=1, max_length=1000)


class McpBuilderDesignCheckpointInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.mcp-builder-design-checkpoint-request.v1", pattern=STABLE_ID
    )
    project_version: int = Field(ge=1)
    project_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    connector_boundary: str = Field(min_length=1, max_length=1000)
    target_products: list[str] = Field(min_length=1, max_length=20)
    network_destinations: list[str] = Field(max_length=20)
    configuration_keys: list[str] = Field(max_length=50)
    secret_reference_ids: list[str] = Field(max_length=50)
    entity_mappings: list[BuilderEntityMappingInput] = Field(min_length=1, max_length=100)
    capability_decisions: list[BuilderCapabilityDecisionInput] = Field(min_length=1, max_length=500)


class BuilderEntityMappingData(BaseModel):
    source_entity: str
    atlas_entity: str


class BuilderCapabilityDecisionData(BaseModel):
    candidate_id: str
    decision: str
    analyzed_class: str
    confirmed_class: str
    required_permission: str
    rationale: str
    generation_eligible: bool


class McpBuilderDesignCheckpointData(BaseModel):
    checkpoint_id: str
    schema_version: str
    version: int
    project_id: str
    project_version: int
    project_digest: str
    source_digest: str
    organization_id: str
    environment_id: str
    reviewer_id: str
    connector_boundary: str
    target_products: list[str]
    network_destinations: list[str]
    configuration_keys: list[str]
    secret_reference_ids: list[str]
    entity_mappings: list[BuilderEntityMappingData]
    capability_decisions: list[BuilderCapabilityDecisionData]
    canonical_digest: str
    created_at: datetime
    ready_for_generation_design: bool
    generated_artifact_created: bool
    candidate_package_created: bool
    connector_registered: bool
    connector_installed: bool
    connector_enabled: bool
    network_request_performed: bool
    model_inference_performed: bool
    dynamic_code_execution_performed: bool
    runtime_trust_granted: bool
    execution_authorized: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(cls, checkpoint: McpBuilderDesignCheckpoint) -> McpBuilderDesignCheckpointData:
        return cls(
            **{
                field: getattr(checkpoint, field)
                for field in cls.model_fields
                if field
                not in {
                    "target_products",
                    "network_destinations",
                    "configuration_keys",
                    "secret_reference_ids",
                    "entity_mappings",
                    "capability_decisions",
                }
            },
            target_products=list(checkpoint.target_products),
            network_destinations=list(checkpoint.network_destinations),
            configuration_keys=list(checkpoint.configuration_keys),
            secret_reference_ids=list(checkpoint.secret_reference_ids),
            entity_mappings=[
                BuilderEntityMappingData(
                    source_entity=item.source_entity, atlas_entity=item.atlas_entity
                )
                for item in checkpoint.entity_mappings
            ],
            capability_decisions=[
                BuilderCapabilityDecisionData(
                    candidate_id=item.candidate_id,
                    decision=item.decision.value,
                    analyzed_class=item.analyzed_class.value,
                    confirmed_class=item.confirmed_class.value,
                    required_permission=item.required_permission,
                    rationale=item.rationale,
                    generation_eligible=item.generation_eligible,
                )
                for item in checkpoint.capability_decisions
            ],
        )


class McpBuilderDesignCheckpointResponse(BaseModel):
    data: McpBuilderDesignCheckpointData
    meta: ResponseMeta


class McpBuilderGenerationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.mcp-builder-generation-request.v1", pattern=STABLE_ID
    )
    project_version: int = Field(ge=1)
    project_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    checkpoint_id: str = Field(pattern=STABLE_ID)
    checkpoint_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    language_profile: str = Field(default="atlas.python312.v1", pattern=STABLE_ID)
    acknowledged_quarantine: bool


class BuilderGeneratedFileData(BaseModel):
    relative_path: str
    media_type: str
    sha256: str
    size_bytes: int
    source_candidate_ids: list[str]

    @classmethod
    def from_domain(cls, item: BuilderGeneratedFile) -> BuilderGeneratedFileData:
        return cls(
            relative_path=item.relative_path,
            media_type=item.media_type,
            sha256=item.sha256,
            size_bytes=item.size_bytes,
            source_candidate_ids=list(item.source_candidate_ids),
        )


class McpBuilderGenerationData(BaseModel):
    generation_id: str
    schema_version: str
    version: int
    state: str
    project_id: str
    project_version: int
    project_digest: str
    source_digest: str
    checkpoint_id: str
    checkpoint_digest: str
    organization_id: str
    environment_id: str
    requested_by: str
    language_profile: str
    template_version: str
    artifact_digest: str
    artifact_size_bytes: int
    files: list[BuilderGeneratedFileData]
    canonical_digest: str
    created_at: datetime
    artifact_published: bool
    generated_artifact_created: bool
    validation_completed: bool
    candidate_package_created: bool
    connector_registered: bool
    connector_installed: bool
    connector_enabled: bool
    network_request_performed: bool
    model_inference_performed: bool
    subprocess_invoked: bool
    dynamic_code_execution_performed: bool
    runtime_trust_granted: bool
    execution_authorized: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(cls, generation: McpBuilderGeneration) -> McpBuilderGenerationData:
        return cls(
            **{
                field: getattr(generation, field)
                for field in cls.model_fields
                if field not in {"state", "files"}
            },
            state=generation.state.value,
            files=[BuilderGeneratedFileData.from_domain(item) for item in generation.files],
        )


class McpBuilderGenerationResponse(BaseModel):
    data: McpBuilderGenerationData
    meta: ResponseMeta


class McpBuilderGeneratedFileData(BaseModel):
    generation_id: str
    state: str
    artifact_digest: str
    file: BuilderGeneratedFileData
    content: str
    content_verified: bool = True
    quarantined: bool = True
    runtime_trust_granted: bool = False
    execution_authorized: bool = False


class McpBuilderGeneratedFileResponse(BaseModel):
    data: McpBuilderGeneratedFileData
    meta: ResponseMeta


class McpBuilderValidationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.mcp-builder-validation-request.v1", pattern=STABLE_ID
    )
    project_version: int = Field(ge=1)
    project_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    checkpoint_id: str = Field(pattern=STABLE_ID)
    checkpoint_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    generation_id: str = Field(pattern=STABLE_ID)
    generation_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    artifact_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    validation_profile: str = Field(
        default="atlas.static-validation.python312.v1", pattern=STABLE_ID
    )
    acknowledged_static_only: bool


class BuilderValidationCheckData(BaseModel):
    code: str
    state: str
    severity: str
    summary: str
    evidence_paths: list[str]
    remediation: str | None

    @classmethod
    def from_domain(cls, item: BuilderValidationCheck) -> BuilderValidationCheckData:
        return cls(
            code=item.code,
            state=item.state.value,
            severity=item.severity.value,
            summary=item.summary,
            evidence_paths=list(item.evidence_paths),
            remediation=item.remediation,
        )


class McpBuilderValidationData(BaseModel):
    validation_id: str
    schema_version: str
    version: int
    state: str
    project_id: str
    project_version: int
    project_digest: str
    source_digest: str
    checkpoint_id: str
    checkpoint_digest: str
    generation_id: str
    generation_digest: str
    artifact_digest: str
    organization_id: str
    environment_id: str
    validated_by: str
    language_profile: str
    template_version: str
    validation_profile: str
    validator_version: str
    checks: list[BuilderValidationCheckData]
    passed_count: int
    failed_count: int
    skipped_count: int
    limitations: list[str]
    canonical_digest: str
    completed_at: datetime
    validation_completed: bool
    static_validation_passed: bool
    runtime_self_test_performed: bool
    dependency_resolution_performed: bool
    domain_review_completed: bool
    security_review_completed: bool
    lab_validation_completed: bool
    candidate_package_created: bool
    connector_registered: bool
    connector_installed: bool
    connector_enabled: bool
    network_request_performed: bool
    model_inference_performed: bool
    subprocess_invoked: bool
    dynamic_code_execution_performed: bool
    runtime_trust_granted: bool
    execution_authorized: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(cls, validation: McpBuilderValidation) -> McpBuilderValidationData:
        return cls(
            **{
                field: getattr(validation, field)
                for field in cls.model_fields
                if field not in {"state", "checks", "limitations"}
            },
            state=validation.state.value,
            checks=[BuilderValidationCheckData.from_domain(item) for item in validation.checks],
            limitations=list(validation.limitations),
        )


class McpBuilderValidationResponse(BaseModel):
    data: McpBuilderValidationData
    meta: ResponseMeta


class BuilderDomainCapabilityDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: str = Field(pattern=STABLE_ID)
    confirmed_class: CapabilityClass
    decision: BuilderDomainCapabilityDecisionKind
    supported_product_versions: list[str] = Field(min_length=1, max_length=20)
    vendor_permission: str = Field(min_length=1, max_length=160)
    authentication_assessment: str = Field(min_length=1, max_length=1200)
    side_effect_assessment: str = Field(min_length=1, max_length=1200)
    error_behavior_assessment: str = Field(min_length=1, max_length=1200)
    health_guidance_assessment: str = Field(min_length=1, max_length=1200)
    evidence_citations: list[str] = Field(min_length=1, max_length=20)
    missing_case_codes: list[str] = Field(max_length=20)
    rationale: str = Field(min_length=1, max_length=1200)

    @model_validator(mode="after")
    def validate_bounded_lists_and_gap_semantics(self) -> Self:
        if (
            len(self.supported_product_versions) != len(set(self.supported_product_versions))
            or any(not item.strip() or len(item) > 100 for item in self.supported_product_versions)
            or len(self.evidence_citations) != len(set(self.evidence_citations))
            or any(not item.strip() or len(item) > 500 for item in self.evidence_citations)
            or len(self.missing_case_codes) != len(set(self.missing_case_codes))
            or any(re.fullmatch(STABLE_ID, item) is None for item in self.missing_case_codes)
        ):
            raise ValueError("Domain review lists are invalid")
        if self.decision is BuilderDomainCapabilityDecisionKind.ACCEPTED:
            if self.missing_case_codes:
                raise ValueError("Accepted domain decisions cannot retain evidence gaps")
        elif not self.missing_case_codes:
            raise ValueError("Non-accepted domain decisions require an evidence gap")
        return self


class McpBuilderDomainReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.mcp-builder-domain-review-request.v1", pattern=STABLE_ID
    )
    project_version: int = Field(ge=1)
    project_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    checkpoint_id: str = Field(pattern=STABLE_ID)
    checkpoint_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    generation_id: str = Field(pattern=STABLE_ID)
    generation_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    artifact_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    validation_id: str = Field(pattern=STABLE_ID)
    validation_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    validation_profile: str = Field(pattern=STABLE_ID)
    validator_version: str = Field(pattern=STABLE_ID)
    review_profile: str = Field(default="atlas.domain-review.connector.v1", pattern=STABLE_ID)
    acknowledged_human_domain_decision: bool
    capability_decisions: list[BuilderDomainCapabilityDecisionInput] = Field(
        min_length=1, max_length=100
    )
    summary: str = Field(min_length=1, max_length=1500)


class BuilderDomainCapabilityDecisionData(BaseModel):
    candidate_id: str
    confirmed_class: str
    decision: str
    supported_product_versions: list[str]
    vendor_permission: str
    authentication_assessment: str
    side_effect_assessment: str
    error_behavior_assessment: str
    health_guidance_assessment: str
    evidence_citations: list[str]
    missing_case_codes: list[str]
    rationale: str

    @classmethod
    def from_domain(
        cls, item: BuilderDomainCapabilityDecision
    ) -> BuilderDomainCapabilityDecisionData:
        return cls(
            candidate_id=item.candidate_id,
            confirmed_class=item.confirmed_class.value,
            decision=item.decision.value,
            supported_product_versions=list(item.supported_product_versions),
            vendor_permission=item.vendor_permission,
            authentication_assessment=item.authentication_assessment,
            side_effect_assessment=item.side_effect_assessment,
            error_behavior_assessment=item.error_behavior_assessment,
            health_guidance_assessment=item.health_guidance_assessment,
            evidence_citations=list(item.evidence_citations),
            missing_case_codes=list(item.missing_case_codes),
            rationale=item.rationale,
        )


class McpBuilderDomainReviewData(BaseModel):
    review_id: str
    schema_version: str
    version: int
    state: str
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
    capability_decisions: list[BuilderDomainCapabilityDecisionData]
    accepted_count: int
    needs_evidence_count: int
    rejected_count: int
    summary: str
    limitations: list[str]
    canonical_digest: str
    completed_at: datetime
    domain_review_completed: bool
    domain_review_accepted: bool
    security_review_completed: bool
    lab_validation_completed: bool
    candidate_package_created: bool
    connector_registered: bool
    connector_installed: bool
    connector_enabled: bool
    network_request_performed: bool
    model_inference_performed: bool
    dependency_resolution_performed: bool
    runtime_self_test_performed: bool
    subprocess_invoked: bool
    dynamic_code_execution_performed: bool
    runtime_trust_granted: bool
    execution_authorized: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(cls, review: McpBuilderDomainReview) -> McpBuilderDomainReviewData:
        return cls(
            **{
                field: getattr(review, field)
                for field in cls.model_fields
                if field not in {"state", "capability_decisions", "limitations"}
            },
            state=review.state.value,
            capability_decisions=[
                BuilderDomainCapabilityDecisionData.from_domain(item)
                for item in review.capability_decisions
            ],
            limitations=list(review.limitations),
        )


class McpBuilderDomainReviewResponse(BaseModel):
    data: McpBuilderDomainReviewData
    meta: ResponseMeta


class BuilderSecurityControlAssessmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    control: BuilderSecurityControl
    decision: BuilderSecurityControlDecisionKind
    assessment: str = Field(min_length=1, max_length=1600)
    evidence_references: list[str] = Field(min_length=1, max_length=30)
    finding_codes: list[str] = Field(max_length=30)
    required_controls: list[str] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_bounded_lists_and_findings(self) -> Self:
        if (
            len(self.evidence_references) != len(set(self.evidence_references))
            or any(not item.strip() or len(item) > 500 for item in self.evidence_references)
            or len(self.finding_codes) != len(set(self.finding_codes))
            or any(re.fullmatch(STABLE_ID, item) is None for item in self.finding_codes)
            or len(self.required_controls) != len(set(self.required_controls))
            or any(not item.strip() or len(item) > 500 for item in self.required_controls)
        ):
            raise ValueError("Security review lists are invalid")
        if self.decision is BuilderSecurityControlDecisionKind.ACCEPTED:
            if self.finding_codes:
                raise ValueError("Accepted security controls cannot retain findings")
        elif not self.finding_codes:
            raise ValueError("Non-accepted security controls require a finding")
        return self


class McpBuilderSecurityReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.mcp-builder-security-review-request.v1", pattern=STABLE_ID
    )
    project_version: int = Field(ge=1)
    project_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    checkpoint_id: str = Field(pattern=STABLE_ID)
    checkpoint_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    generation_id: str = Field(pattern=STABLE_ID)
    generation_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    artifact_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    validation_id: str = Field(pattern=STABLE_ID)
    validation_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    validation_profile: str = Field(pattern=STABLE_ID)
    validator_version: str = Field(pattern=STABLE_ID)
    domain_review_id: str = Field(pattern=STABLE_ID)
    domain_review_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    domain_review_profile: str = Field(pattern=STABLE_ID)
    domain_reviewer_contract_version: str = Field(pattern=STABLE_ID)
    review_profile: str = Field(default="atlas.security-review.connector.v1", pattern=STABLE_ID)
    acknowledged_independent_security_decision: bool
    control_assessments: list[BuilderSecurityControlAssessmentInput] = Field(
        min_length=9, max_length=9
    )
    summary: str = Field(min_length=1, max_length=1800)

    @model_validator(mode="after")
    def validate_complete_control_set(self) -> Self:
        if {item.control for item in self.control_assessments} != set(BuilderSecurityControl):
            raise ValueError("Security review control set is incomplete")
        return self


class BuilderSecurityControlAssessmentData(BaseModel):
    control: str
    decision: str
    assessment: str
    evidence_references: list[str]
    finding_codes: list[str]
    required_controls: list[str]

    @classmethod
    def from_domain(
        cls, item: BuilderSecurityControlAssessment
    ) -> BuilderSecurityControlAssessmentData:
        return cls(
            control=item.control.value,
            decision=item.decision.value,
            assessment=item.assessment,
            evidence_references=list(item.evidence_references),
            finding_codes=list(item.finding_codes),
            required_controls=list(item.required_controls),
        )


class McpBuilderSecurityReviewData(BaseModel):
    review_id: str
    schema_version: str
    version: int
    state: str
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
    control_assessments: list[BuilderSecurityControlAssessmentData]
    accepted_count: int
    needs_remediation_count: int
    rejected_count: int
    summary: str
    limitations: list[str]
    canonical_digest: str
    completed_at: datetime
    security_review_completed: bool
    security_review_accepted: bool
    lab_validation_completed: bool
    candidate_package_created: bool
    connector_registered: bool
    connector_installed: bool
    connector_enabled: bool
    network_request_performed: bool
    model_inference_performed: bool
    dependency_resolution_performed: bool
    malware_or_dynamic_scan_performed: bool
    runtime_self_test_performed: bool
    subprocess_invoked: bool
    dynamic_code_execution_performed: bool
    runtime_trust_granted: bool
    execution_authorized: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(cls, review: McpBuilderSecurityReview) -> McpBuilderSecurityReviewData:
        return cls(
            **{
                field: getattr(review, field)
                for field in cls.model_fields
                if field not in {"state", "control_assessments", "limitations"}
            },
            state=review.state.value,
            control_assessments=[
                BuilderSecurityControlAssessmentData.from_domain(item)
                for item in review.control_assessments
            ],
            limitations=list(review.limitations),
        )


class McpBuilderSecurityReviewResponse(BaseModel):
    data: McpBuilderSecurityReviewData
    meta: ResponseMeta


class McpBuilderLabValidationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.mcp-builder-lab-validation-request.v1", pattern=STABLE_ID
    )
    project_version: int = Field(ge=1)
    project_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    checkpoint_id: str = Field(pattern=STABLE_ID)
    checkpoint_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    generation_id: str = Field(pattern=STABLE_ID)
    generation_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    artifact_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    validation_id: str = Field(pattern=STABLE_ID)
    validation_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    domain_review_id: str = Field(pattern=STABLE_ID)
    domain_review_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    security_review_id: str = Field(pattern=STABLE_ID)
    security_review_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    lab_profile: str = Field(default="atlas.lab-validation.python312.v1", pattern=STABLE_ID)
    acknowledged_isolated_synthetic_execution: bool


class BuilderLabCheckData(BaseModel):
    code: str
    state: str
    severity: str
    summary: str
    evidence_paths: list[str]
    remediation: str | None

    @classmethod
    def from_domain(cls, item: BuilderLabCheck) -> BuilderLabCheckData:
        return cls(
            code=item.code.value,
            state=item.state.value,
            severity=item.severity.value,
            summary=item.summary,
            evidence_paths=list(item.evidence_paths),
            remediation=item.remediation,
        )


class McpBuilderLabValidationData(BaseModel):
    lab_validation_id: str
    schema_version: str
    version: int
    state: str
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
    domain_review_id: str
    domain_review_digest: str
    domain_reviewed_by: str
    security_review_id: str
    security_review_digest: str
    security_reviewed_by: str
    organization_id: str
    environment_id: str
    operated_by: str
    lab_profile: str
    runner_contract_version: str
    runtime_version: str
    checks: list[BuilderLabCheckData]
    passed_count: int
    failed_count: int
    skipped_count: int
    child_started: bool
    child_exit_code: int | None
    duration_ms: int
    output_digest: str
    output_size_bytes: int
    artifact_file_count: int
    artifact_size_bytes: int
    workspace_removed: bool
    limitations: list[str]
    canonical_digest: str
    completed_at: datetime
    lab_validation_completed: bool
    lab_validation_passed: bool
    synthetic_fixture_used: bool
    secret_values_present: bool
    target_connected: bool
    network_request_performed: bool
    runtime_self_test_performed: bool
    subprocess_invoked: bool
    dynamic_code_execution_performed: bool
    dependency_resolution_performed: bool
    malware_or_dynamic_scan_performed: bool
    candidate_package_created: bool
    connector_registered: bool
    connector_installed: bool
    connector_enabled: bool
    runtime_trust_granted: bool
    execution_authorized: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(cls, validation: McpBuilderLabValidation) -> McpBuilderLabValidationData:
        return cls(
            **{
                field: getattr(validation, field)
                for field in cls.model_fields
                if field not in {"state", "checks", "limitations"}
            },
            state=validation.state.value,
            checks=[BuilderLabCheckData.from_domain(item) for item in validation.checks],
            limitations=list(validation.limitations),
        )


class McpBuilderLabValidationResponse(BaseModel):
    data: McpBuilderLabValidationData
    meta: ResponseMeta


class McpBuilderCandidateHandoffInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.mcp-builder-candidate-handoff-request.v1", pattern=STABLE_ID
    )
    project_version: int = Field(ge=1)
    project_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    checkpoint_id: str = Field(pattern=STABLE_ID)
    checkpoint_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    generation_id: str = Field(pattern=STABLE_ID)
    generation_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    artifact_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    validation_id: str = Field(pattern=STABLE_ID)
    validation_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    domain_review_id: str = Field(pattern=STABLE_ID)
    domain_review_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    security_review_id: str = Field(pattern=STABLE_ID)
    security_review_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    lab_validation_id: str = Field(pattern=STABLE_ID)
    lab_validation_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    handoff_profile: str = Field(default="atlas.candidate-handoff.python312.v1", pattern=STABLE_ID)
    acknowledged_unsigned_quarantined_package: bool


class CandidateCapabilityEvidenceData(BaseModel):
    candidate_id: str
    capability_class: str
    required_permission: str
    supported_product_versions: list[str]
    source_citations: list[str]

    @classmethod
    def from_domain(cls, item: CandidateCapabilityEvidence) -> CandidateCapabilityEvidenceData:
        return cls(
            candidate_id=item.candidate_id,
            capability_class=item.capability_class,
            required_permission=item.required_permission,
            supported_product_versions=list(item.supported_product_versions),
            source_citations=list(item.source_citations),
        )


class McpBuilderCandidateHandoffData(BaseModel):
    handoff_id: str
    schema_version: str
    version: int
    state: str
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
    domain_review_id: str
    domain_review_digest: str
    domain_reviewed_by: str
    security_review_id: str
    security_review_digest: str
    security_reviewed_by: str
    lab_validation_id: str
    lab_validation_digest: str
    lab_operated_by: str
    organization_id: str
    environment_id: str
    custodied_by: str
    handoff_profile: str
    archive_contract_version: str
    package_filename: str
    package_digest: str
    package_size_bytes: int
    package_entry_count: int
    generated_file_count: int
    generated_size_bytes: int
    envelope_digest: str
    signature_state: str
    capabilities: list[CandidateCapabilityEvidenceData]
    network_destinations: list[str]
    limitations: list[str]
    unsupported_behavior: list[str]
    manual_change_count: int
    canonical_digest: str
    created_at: datetime
    candidate_package_created: bool
    package_signed: bool
    publisher_attested: bool
    registry_validation_completed: bool
    connector_registered: bool
    connector_installed: bool
    connector_enabled: bool
    target_configured: bool
    credentials_resolved: bool
    runtime_trust_granted: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(cls, handoff: McpBuilderCandidateHandoff) -> McpBuilderCandidateHandoffData:
        return cls(
            **{
                field: getattr(handoff, field)
                for field in cls.model_fields
                if field
                not in {
                    "state",
                    "signature_state",
                    "capabilities",
                    "network_destinations",
                    "limitations",
                    "unsupported_behavior",
                }
            },
            state=handoff.state.value,
            signature_state=handoff.signature_state.value,
            capabilities=[
                CandidateCapabilityEvidenceData.from_domain(item) for item in handoff.capabilities
            ],
            network_destinations=list(handoff.network_destinations),
            limitations=list(handoff.limitations),
            unsupported_behavior=list(handoff.unsupported_behavior),
        )


class McpBuilderCandidateHandoffResponse(BaseModel):
    data: McpBuilderCandidateHandoffData
    meta: ResponseMeta


def design_entity_mapping(value: BuilderEntityMappingInput) -> BuilderEntityMapping:
    return BuilderEntityMapping(source_entity=value.source_entity, atlas_entity=value.atlas_entity)


def design_capability_decision(
    value: BuilderCapabilityDecisionInput,
) -> BuilderCapabilityDecision:
    return BuilderCapabilityDecision(
        candidate_id=value.candidate_id,
        decision=value.decision,
        analyzed_class=value.analyzed_class,
        confirmed_class=value.confirmed_class,
        required_permission=value.required_permission,
        rationale=value.rationale,
        generation_eligible=value.decision is BuilderCapabilityDecisionKind.INCLUDE,
    )


def domain_capability_decision(
    value: BuilderDomainCapabilityDecisionInput,
) -> BuilderDomainCapabilityDecision:
    return BuilderDomainCapabilityDecision(
        candidate_id=value.candidate_id,
        confirmed_class=value.confirmed_class,
        decision=value.decision,
        supported_product_versions=tuple(value.supported_product_versions),
        vendor_permission=value.vendor_permission,
        authentication_assessment=value.authentication_assessment,
        side_effect_assessment=value.side_effect_assessment,
        error_behavior_assessment=value.error_behavior_assessment,
        health_guidance_assessment=value.health_guidance_assessment,
        evidence_citations=tuple(value.evidence_citations),
        missing_case_codes=tuple(value.missing_case_codes),
        rationale=value.rationale,
    )


def security_control_assessment(
    value: BuilderSecurityControlAssessmentInput,
) -> BuilderSecurityControlAssessment:
    return BuilderSecurityControlAssessment(
        control=value.control,
        decision=value.decision,
        assessment=value.assessment,
        evidence_references=tuple(value.evidence_references),
        finding_codes=tuple(value.finding_codes),
        required_controls=tuple(value.required_controls),
    )

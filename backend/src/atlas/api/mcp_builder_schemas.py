from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.core.classification import DataClassification
from atlas.modules.mcp_builder.domain.models import McpBuilderProject

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

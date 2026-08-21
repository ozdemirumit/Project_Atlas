from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.modules.authorization.domain.models import AuthorizationDecision, ResourceScope
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.domain.advisory_posture import AdvisoryOnlyPosture
from atlas.modules.platform.domain.status import ComponentHealth, PlatformHealth


class AdvisoryOnlyPostureSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_id: str
    contract_version: str
    platform_mode: str
    operational_execution_enabled: bool
    process_resume_consumption_enabled: bool
    dispatch_enabled: bool
    infrastructure_mutation_enabled: bool
    ai_execution_authorized: bool
    contract_digest: str

    @classmethod
    def from_domain(cls, posture: AdvisoryOnlyPosture) -> AdvisoryOnlyPostureSchema:
        return cls(
            contract_id=posture.contract_id,
            contract_version=posture.contract_version,
            platform_mode=posture.platform_mode,
            operational_execution_enabled=posture.operational_execution_enabled,
            process_resume_consumption_enabled=posture.process_resume_consumption_enabled,
            dispatch_enabled=posture.dispatch_enabled,
            infrastructure_mutation_enabled=posture.infrastructure_mutation_enabled,
            ai_execution_authorized=posture.ai_execution_authorized,
            contract_digest=posture.contract_digest,
        )


class ComponentStatusSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: str
    required: bool
    code: str

    @classmethod
    def from_domain(cls, component: ComponentHealth) -> ComponentStatusSchema:
        return cls(
            name=component.name,
            status=component.status.value,
            required=component.required,
            code=component.code,
        )


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    service: str
    version: str
    components: list[ComponentStatusSchema] = Field(default_factory=list)


class PlatformStatusData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str
    version: str
    environment: str
    status: str
    components: list[ComponentStatusSchema]
    warnings: list[str]
    operational_posture: AdvisoryOnlyPostureSchema

    @classmethod
    def from_domain(cls, status: PlatformHealth) -> PlatformStatusData:
        return cls(
            service=status.service_name,
            version=status.service_version,
            environment=status.environment,
            status=status.status.value,
            components=[ComponentStatusSchema.from_domain(item) for item in status.components],
            warnings=list(status.warnings),
            operational_posture=AdvisoryOnlyPostureSchema.from_domain(status.operational_posture),
        )


class ResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: str
    generated_at: datetime


class PlatformStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: PlatformStatusData
    meta: ResponseMeta


class AuthenticationContextSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str
    method: str
    assurance_level: str
    authenticated_at: datetime


class IdentityScopeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: str
    environment_id: str
    site_id: str
    domain_id: str
    resource_id: str
    capability_class: str

    @classmethod
    def from_domain(cls, scope: ResourceScope) -> IdentityScopeSchema:
        return cls(
            organization_id=scope.organization_id,
            environment_id=scope.environment_id,
            site_id=scope.site_id,
            domain_id=scope.domain_id,
            resource_id=scope.resource_id,
            capability_class=scope.capability_class.value,
        )


class CurrentIdentityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str
    display_name: str
    subject_kind: str
    organization_id: str
    credential_kind: str
    role_ids: list[str]
    group_ids: list[str]
    authentication: AuthenticationContextSchema
    scope: IdentityScopeSchema
    authorization_decision_id: str
    effective_role_versions: list[str]
    effective_assignment_versions: list[str]

    @classmethod
    def from_domain(
        cls,
        subject: AuthenticatedSubject,
        scope: ResourceScope,
        decision: AuthorizationDecision,
        credential_kind: str,
    ) -> CurrentIdentityData:
        return cls(
            subject_id=subject.subject_id,
            display_name=subject.display_name,
            subject_kind=subject.kind.value,
            organization_id=subject.organization_id,
            credential_kind=credential_kind,
            role_ids=list(subject.role_ids),
            group_ids=list(subject.group_ids),
            authentication=AuthenticationContextSchema(
                provider_id=subject.provider_id,
                method=subject.authentication_method.value,
                assurance_level=subject.assurance_level.value,
                authenticated_at=subject.authenticated_at,
            ),
            scope=IdentityScopeSchema.from_domain(scope),
            authorization_decision_id=decision.decision_id,
            effective_role_versions=list(decision.role_references),
            effective_assignment_versions=list(decision.assignment_references),
        )


class CurrentIdentityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: CurrentIdentityData
    meta: ResponseMeta

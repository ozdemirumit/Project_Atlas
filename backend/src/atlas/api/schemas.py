from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.modules.platform.domain.status import ComponentHealth, PlatformHealth


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

    @classmethod
    def from_domain(cls, status: PlatformHealth) -> PlatformStatusData:
        return cls(
            service=status.service_name,
            version=status.service_version,
            environment=status.environment,
            status=status.status.value,
            components=[ComponentStatusSchema.from_domain(item) for item in status.components],
            warnings=list(status.warnings),
        )


class ResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: str
    generated_at: datetime


class PlatformStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: PlatformStatusData
    meta: ResponseMeta

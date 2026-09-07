from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.mcp_builder.domain.draft_and_supersession import (
    BuilderProjectDraft,
    BuilderProjectSupersession,
)


class BuilderDraftCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor: str = Field(min_length=1, max_length=200)
    product: str = Field(min_length=1, max_length=200)
    target_environment: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=4000)


class BuilderDraftAnalyzeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analyzed_project_id: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


class BuilderSupersessionCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    superseded_project_id: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")
    superseding_project_id: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")
    reason: str = Field(min_length=1, max_length=2000)


class BuilderDraftData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str
    organization_id: str
    environment_id: str
    owner_id: str
    vendor: str
    product: str
    target_environment: str
    notes: str
    created_at: datetime
    updated_at: datetime
    analyzed_project_id: str | None

    @classmethod
    def from_domain(cls, draft: BuilderProjectDraft) -> BuilderDraftData:
        return cls(
            draft_id=draft.draft_id,
            organization_id=draft.organization_id,
            environment_id=draft.environment_id,
            owner_id=draft.owner_id,
            vendor=draft.vendor,
            product=draft.product,
            target_environment=draft.target_environment,
            notes=draft.notes,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
            analyzed_project_id=draft.analyzed_project_id,
        )


class BuilderDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BuilderDraftData
    meta: ResponseMeta


class BuilderSupersessionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supersession_id: str
    superseded_project_id: str
    superseding_project_id: str
    reason: str
    recorded_by: str
    recorded_at: datetime

    @classmethod
    def from_domain(cls, supersession: BuilderProjectSupersession) -> BuilderSupersessionData:
        return cls(
            supersession_id=supersession.supersession_id,
            superseded_project_id=supersession.superseded_project_id,
            superseding_project_id=supersession.superseding_project_id,
            reason=supersession.reason,
            recorded_by=supersession.recorded_by,
            recorded_at=supersession.recorded_at,
        )


class BuilderSupersessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BuilderSupersessionData
    meta: ResponseMeta

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.authorization.domain.models import RoleAssignment

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"


class RoleAssignmentGrantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str = Field(pattern=STABLE_ID)
    role_id: str = Field(pattern=STABLE_ID)


class RoleAssignmentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_id: str
    subject_id: str
    role_id: str
    scope_reference: str
    valid_from: datetime
    expires_at: datetime | None

    @classmethod
    def from_domain(cls, assignment: RoleAssignment) -> RoleAssignmentData:
        return cls(
            assignment_id=assignment.assignment_id,
            subject_id=assignment.subject_id,
            role_id=assignment.role_id,
            scope_reference=assignment.scope.reference,
            valid_from=assignment.valid_from,
            expires_at=assignment.expires_at,
        )


class RoleAssignmentGrantResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[RoleAssignmentData, ...]
    meta: ResponseMeta


class RoleAssignmentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[RoleAssignmentData, ...]
    meta: ResponseMeta

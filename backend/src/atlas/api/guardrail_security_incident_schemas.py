from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.guardrails.domain.security_incident import SecurityIncidentRecord


class SecurityIncidentOpenInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger: str = Field(min_length=1, max_length=64)
    affected_references: list[str] = Field(min_length=1, max_length=100)


class SecurityIncidentContainInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_reference: str = Field(min_length=1, max_length=200)


class SecurityIncidentRecoveryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credentials_revoked: bool
    scope_assessment: str = Field(min_length=1, max_length=2000)
    improvement_reference: str = Field(min_length=1, max_length=200)


class SecurityIncidentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str
    trigger: str
    detected_at: datetime
    affected_references: list[str]
    contained_at: datetime | None
    evidence_preserved: bool
    alert_reference: str | None
    credentials_revoked: bool
    scope_assessment: str | None
    recovery_validated_at: datetime | None
    improvement_reference: str | None
    closed_at: datetime | None
    closed_by: str | None
    closer_kind: str | None

    @classmethod
    def from_domain(cls, incident: SecurityIncidentRecord) -> SecurityIncidentData:
        return cls(
            incident_id=incident.incident_id,
            trigger=incident.trigger.value,
            detected_at=incident.detected_at,
            affected_references=list(incident.affected_references),
            contained_at=incident.contained_at,
            evidence_preserved=incident.evidence_preserved,
            alert_reference=incident.alert_reference,
            credentials_revoked=incident.credentials_revoked,
            scope_assessment=incident.scope_assessment,
            recovery_validated_at=incident.recovery_validated_at,
            improvement_reference=incident.improvement_reference,
            closed_at=incident.closed_at,
            closed_by=incident.closed_by,
            closer_kind=incident.closer_kind.value if incident.closer_kind is not None else None,
        )


class SecurityIncidentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: SecurityIncidentData
    meta: ResponseMeta

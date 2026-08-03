from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from atlas.api.schemas import ResponseMeta
from atlas.modules.graph.domain.models import StorageImpactResult


class GraphEvidenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: str
    source: str
    source_version: str
    observed_at: datetime
    freshness: str
    trust_basis: str
    classification: str


class GraphEntityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    entity_type: str
    display_name: str
    domain_id: str
    observed_at: datetime
    freshness: str
    confidence_basis: str
    evidence_references: list[str]
    classification: str
    vendor: str | None
    product: str | None
    model: str | None
    lifecycle_state: str


class GraphRelationshipData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationship_id: str
    relationship_type: str
    source_entity_id: str
    target_entity_id: str
    assertion_method: str
    observed_at: datetime
    freshness: str
    confidence_basis: str
    evidence_references: list[str]
    classification: str


class ImpactPathData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: str
    entity_ids: list[str]
    relationship_ids: list[str]
    evidence_references: list[str]


class StorageImpactData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    snapshot_generated_at: datetime
    start_entity_id: str
    max_depth: int
    freshness: str
    completeness: str
    entities: list[GraphEntityData]
    relationships: list[GraphRelationshipData]
    paths: list[ImpactPathData]
    evidence: list[GraphEvidenceData]
    direct_entity_ids: list[str]
    possible_entity_ids: list[str]
    technical_service_ids: list[str]
    business_service_ids: list[str]
    unknowns: list[str]
    known_gaps: list[str]
    outage_confirmed: bool
    digital_twin_maturity: str
    data_profile: str
    safety_notice: str

    @classmethod
    def from_domain(cls, result: StorageImpactResult) -> StorageImpactData:
        return cls.model_validate(result, from_attributes=True)


class StorageImpactResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: StorageImpactData
    meta: ResponseMeta

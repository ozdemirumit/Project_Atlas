from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.classification import DataClassification


class EntityType(StrEnum):
    STORAGE_SYSTEM = "storage_system"
    SAN_SWITCH = "san_switch"
    VOLUME = "volume"
    DATASTORE = "datastore"
    VIRTUAL_MACHINE = "virtual_machine"
    HYPERVISOR_HOST = "hypervisor_host"
    HYPERVISOR_CLUSTER = "hypervisor_cluster"
    TECHNICAL_SERVICE = "technical_service"
    BUSINESS_SERVICE = "business_service"


class RelationshipType(StrEnum):
    BACKED_BY = "backed_by"
    USES = "uses"
    RUNS_ON = "runs_on"
    DEPENDS_ON = "depends_on"


class FreshnessState(StrEnum):
    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    UNKNOWN = "unknown"
    EXPIRED = "expired"


class AssertionMethod(StrEnum):
    OBSERVED = "observed"
    CALCULATED = "calculated"
    INFERRED = "inferred"
    MANUAL = "manual"


class ImpactScope(StrEnum):
    DIRECT = "direct"
    POSSIBLE = "possible"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class GraphEvidence:
    reference: str
    source: str
    source_version: str
    observed_at: datetime
    freshness: FreshnessState
    trust_basis: str
    classification: DataClassification

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.reference or not self.source or not self.trust_basis:
            raise ValueError("graph evidence requires identity, source, and trust basis")


@dataclass(frozen=True, slots=True)
class GraphObservation:
    observation_id: str
    subject_id: str
    claim_type: str
    claim_summary: str
    source: str
    source_version: str
    observed_at: datetime
    freshness: FreshnessState
    classification: DataClassification
    allowed_principals: frozenset[str]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.claim_summary.strip() or not self.allowed_principals:
            raise ValueError("observations require a claim and access policy")


@dataclass(frozen=True, slots=True)
class GraphEntity:
    entity_id: str
    entity_type: EntityType
    display_name: str
    organization_id: str
    environment_id: str
    site_id: str
    domain_id: str
    observed_at: datetime
    valid_from: datetime
    valid_to: datetime | None
    freshness: FreshnessState
    confidence_basis: str
    evidence_references: tuple[str, ...]
    classification: DataClassification
    allowed_principals: frozenset[str]
    vendor: str | None = None
    product: str | None = None
    model: str | None = None
    lifecycle_state: str = "active"

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.valid_from.tzinfo is None:
            raise ValueError("graph entity timestamps must be timezone-aware")
        if self.valid_to is not None and self.valid_to.tzinfo is None:
            raise ValueError("valid_to must be timezone-aware")
        if not self.display_name.strip() or not self.evidence_references:
            raise ValueError("graph entities require a display name and evidence")
        if not self.allowed_principals:
            raise ValueError("graph entities require an access policy")


@dataclass(frozen=True, slots=True)
class GraphRelationship:
    relationship_id: str
    relationship_type: RelationshipType
    source_entity_id: str
    target_entity_id: str
    assertion_method: AssertionMethod
    observed_at: datetime
    valid_from: datetime
    valid_to: datetime | None
    freshness: FreshnessState
    confidence_basis: str
    evidence_references: tuple[str, ...]
    classification: DataClassification
    allowed_principals: frozenset[str]

    def __post_init__(self) -> None:
        if self.source_entity_id == self.target_entity_id:
            raise ValueError("self-referencing graph relationships are not supported")
        if self.observed_at.tzinfo is None or self.valid_from.tzinfo is None:
            raise ValueError("graph relationship timestamps must be timezone-aware")
        if self.valid_to is not None and self.valid_to.tzinfo is None:
            raise ValueError("valid_to must be timezone-aware")
        if not self.evidence_references or not self.allowed_principals:
            raise ValueError("graph relationships require evidence and an access policy")


@dataclass(frozen=True, slots=True)
class GraphSnapshot:
    snapshot_id: str
    schema_version: str
    organization_id: str
    environment_id: str
    site_id: str
    generated_at: datetime
    freshness: FreshnessState
    completeness: str
    entities: tuple[GraphEntity, ...]
    relationships: tuple[GraphRelationship, ...]
    observations: tuple[GraphObservation, ...]
    evidence: tuple[GraphEvidence, ...]
    known_gaps: tuple[str, ...]
    data_profile: str

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        entity_ids = {entity.entity_id for entity in self.entities}
        evidence_refs = {record.reference for record in self.evidence}
        if len(entity_ids) != len(self.entities):
            raise ValueError("graph entity identifiers must be unique")
        if any(
            relationship.source_entity_id not in entity_ids
            or relationship.target_entity_id not in entity_ids
            for relationship in self.relationships
        ):
            raise ValueError("graph relationships must reference entities in the snapshot")
        if any(
            reference not in evidence_refs
            for entity in self.entities
            for reference in entity.evidence_references
        ):
            raise ValueError("graph entity evidence must exist in the snapshot")
        if any(
            reference not in evidence_refs
            for relationship in self.relationships
            for reference in relationship.evidence_references
        ):
            raise ValueError("graph relationship evidence must exist in the snapshot")


@dataclass(frozen=True, slots=True)
class ImpactPath:
    scope: ImpactScope
    entity_ids: tuple[str, ...]
    relationship_ids: tuple[str, ...]
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.entity_ids) != len(self.relationship_ids) + 1:
            raise ValueError("impact paths require one more entity than relationship")
        if not self.evidence_references:
            raise ValueError("impact paths require evidence")


@dataclass(frozen=True, slots=True)
class StorageImpactResult:
    snapshot_id: str
    snapshot_generated_at: datetime
    start_entity_id: str
    max_depth: int
    freshness: FreshnessState
    completeness: str
    entities: tuple[GraphEntity, ...]
    relationships: tuple[GraphRelationship, ...]
    paths: tuple[ImpactPath, ...]
    evidence: tuple[GraphEvidence, ...]
    direct_entity_ids: tuple[str, ...]
    possible_entity_ids: tuple[str, ...]
    technical_service_ids: tuple[str, ...]
    business_service_ids: tuple[str, ...]
    unknowns: tuple[str, ...]
    known_gaps: tuple[str, ...]
    outage_confirmed: bool
    digital_twin_maturity: str
    data_profile: str
    safety_notice: str

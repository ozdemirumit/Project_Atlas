from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.classification import DataClassification
from atlas.modules.graph.domain.models import (
    AssertionMethod,
    EntityType,
    FreshnessState,
    GraphEntity,
    GraphEvidence,
    GraphObservation,
    GraphRelationship,
    GraphSnapshot,
    RelationshipType,
)

DEVELOPMENT_PRINCIPALS = frozenset({"role.development.operator"})
RESTRICTED_PRINCIPALS = frozenset({"role.restricted.operator"})


def _evidence(
    reference: str,
    summary: str,
    observed_at: datetime,
    freshness: FreshnessState = FreshnessState.FRESH,
) -> GraphEvidence:
    return GraphEvidence(
        reference=reference,
        source="synthetic-opscenter-and-cmdb",
        source_version="lab-graph-1.0",
        observed_at=observed_at,
        freshness=freshness,
        trust_basis=summary,
        classification=DataClassification.INTERNAL,
    )


def _observation(
    *,
    observation_id: str,
    subject_id: str,
    claim_type: str,
    summary: str,
    observed_at: datetime,
    principals: frozenset[str] = DEVELOPMENT_PRINCIPALS,
    classification: DataClassification = DataClassification.INTERNAL,
    freshness: FreshnessState = FreshnessState.FRESH,
) -> GraphObservation:
    return GraphObservation(
        observation_id=observation_id,
        subject_id=subject_id,
        claim_type=claim_type,
        claim_summary=summary,
        source="synthetic-opscenter-and-cmdb",
        source_version="lab-graph-1.0",
        observed_at=observed_at,
        freshness=freshness,
        classification=classification,
        allowed_principals=principals,
    )


def _entity(
    *,
    observation: GraphObservation,
    entity_type: EntityType,
    display_name: str,
    organization_id: str,
    environment_id: str,
    site_id: str,
    vendor: str | None = None,
    model: str | None = None,
) -> GraphEntity:
    return GraphEntity(
        entity_id=observation.subject_id,
        entity_type=entity_type,
        display_name=display_name,
        organization_id=organization_id,
        environment_id=environment_id,
        site_id=site_id,
        domain_id=f"domain.{entity_type.value}",
        observed_at=observation.observed_at,
        valid_from=observation.observed_at,
        valid_to=None,
        freshness=observation.freshness,
        confidence_basis="Reconciled from one current authoritative synthetic observation.",
        evidence_references=(f"evidence.{observation.observation_id}",),
        classification=observation.classification,
        allowed_principals=observation.allowed_principals,
        vendor=vendor,
        product="Project Atlas synthetic dependency model",
        model=model,
    )


def _relationship(
    *,
    observation: GraphObservation,
    relationship_type: RelationshipType,
    source_entity_id: str,
    target_entity_id: str,
) -> GraphRelationship:
    return GraphRelationship(
        relationship_id=observation.subject_id,
        relationship_type=relationship_type,
        source_entity_id=source_entity_id,
        target_entity_id=target_entity_id,
        assertion_method=AssertionMethod.OBSERVED,
        observed_at=observation.observed_at,
        valid_from=observation.observed_at,
        valid_to=None,
        freshness=observation.freshness,
        confidence_basis="Reconciled from a current synthetic topology observation.",
        evidence_references=(f"evidence.{observation.observation_id}",),
        classification=observation.classification,
        allowed_principals=observation.allowed_principals,
    )


def build_synthetic_graph_snapshot(*, organization_id: str, environment: str) -> GraphSnapshot:
    observed_at = datetime(2026, 7, 21, 9, 30, tzinfo=UTC)
    environment_id = f"environment.{environment}"
    site_id = "site.local"
    entity_specs = (
        (
            "asset.storage.lab.b28",
            EntityType.STORAGE_SYSTEM,
            "VSP One B28",
            "Hitachi",
            "VSP One B28",
        ),
        ("entity.volume.erp.prod", EntityType.VOLUME, "ERP-PROD-VOL-01", None, None),
        ("entity.datastore.erp.prod", EntityType.DATASTORE, "ERP-PROD-DS-01", None, None),
        ("entity.vm.erp.app.01", EntityType.VIRTUAL_MACHINE, "erp-app-01", None, None),
        (
            "entity.service.erp.application",
            EntityType.TECHNICAL_SERVICE,
            "ERP Application Service",
            None,
            None,
        ),
        (
            "entity.business-service.erp",
            EntityType.BUSINESS_SERVICE,
            "Enterprise Resource Planning",
            None,
            None,
        ),
        ("asset.storage.lab.g400", EntityType.STORAGE_SYSTEM, "VSP G400", "Hitachi", "VSP G400"),
        ("entity.volume.analytics.lab", EntityType.VOLUME, "ANALYTICS-LAB-VOL-01", None, None),
        (
            "entity.datastore.analytics.lab",
            EntityType.DATASTORE,
            "ANALYTICS-LAB-DS-01",
            None,
            None,
        ),
        ("entity.vm.analytics.01", EntityType.VIRTUAL_MACHINE, "analytics-01", None, None),
        (
            "entity.service.analytics",
            EntityType.TECHNICAL_SERVICE,
            "Analytics Processing Service",
            None,
            None,
        ),
    )
    observations: list[GraphObservation] = []
    entities: list[GraphEntity] = []
    evidence: list[GraphEvidence] = []
    for index, (entity_id, entity_type, display_name, vendor, model) in enumerate(
        entity_specs, start=1
    ):
        observation = _observation(
            observation_id=f"obs.graph.entity.{index:02d}",
            subject_id=entity_id,
            claim_type="entity",
            summary=f"Observed canonical {entity_type.value} named {display_name}.",
            observed_at=observed_at,
        )
        observations.append(observation)
        entities.append(
            _entity(
                observation=observation,
                entity_type=entity_type,
                display_name=display_name,
                organization_id=organization_id,
                environment_id=environment_id,
                site_id=site_id,
                vendor=vendor,
                model=model,
            )
        )
        evidence.append(
            _evidence(
                f"evidence.{observation.observation_id}",
                observation.claim_summary,
                observed_at,
            )
        )

    hidden_observation = _observation(
        observation_id="obs.graph.entity.hidden",
        subject_id="entity.business-service.restricted",
        claim_type="entity",
        summary="Observed a restricted business service mapping.",
        observed_at=observed_at,
        principals=RESTRICTED_PRINCIPALS,
        classification=DataClassification.RESTRICTED,
    )
    observations.append(hidden_observation)
    entities.append(
        _entity(
            observation=hidden_observation,
            entity_type=EntityType.BUSINESS_SERVICE,
            display_name="Restricted Business Service",
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
        )
    )
    evidence.append(
        GraphEvidence(
            reference="evidence.obs.graph.entity.hidden",
            source="synthetic-restricted-cmdb",
            source_version="lab-graph-1.0",
            observed_at=observed_at,
            freshness=FreshnessState.FRESH,
            trust_basis="Restricted synthetic service mapping.",
            classification=DataClassification.RESTRICTED,
        )
    )

    relationship_specs = (
        (
            "rel.volume.erp.backed-by.b28",
            RelationshipType.BACKED_BY,
            "entity.volume.erp.prod",
            "asset.storage.lab.b28",
        ),
        (
            "rel.datastore.erp.backed-by.volume",
            RelationshipType.BACKED_BY,
            "entity.datastore.erp.prod",
            "entity.volume.erp.prod",
        ),
        (
            "rel.vm.erp.uses.datastore",
            RelationshipType.USES,
            "entity.vm.erp.app.01",
            "entity.datastore.erp.prod",
        ),
        (
            "rel.service.erp.runs-on.vm",
            RelationshipType.RUNS_ON,
            "entity.service.erp.application",
            "entity.vm.erp.app.01",
        ),
        (
            "rel.business.erp.depends-on.service",
            RelationshipType.DEPENDS_ON,
            "entity.business-service.erp",
            "entity.service.erp.application",
        ),
        (
            "rel.volume.analytics.backed-by.g400",
            RelationshipType.BACKED_BY,
            "entity.volume.analytics.lab",
            "asset.storage.lab.g400",
        ),
        (
            "rel.datastore.analytics.backed-by.volume",
            RelationshipType.BACKED_BY,
            "entity.datastore.analytics.lab",
            "entity.volume.analytics.lab",
        ),
        (
            "rel.vm.analytics.uses.datastore",
            RelationshipType.USES,
            "entity.vm.analytics.01",
            "entity.datastore.analytics.lab",
        ),
        (
            "rel.service.analytics.runs-on.vm",
            RelationshipType.RUNS_ON,
            "entity.service.analytics",
            "entity.vm.analytics.01",
        ),
    )
    relationships: list[GraphRelationship] = []
    for index, (relationship_id, relationship_type, source_id, target_id) in enumerate(
        relationship_specs, start=1
    ):
        observation = _observation(
            observation_id=f"obs.graph.relationship.{index:02d}",
            subject_id=relationship_id,
            claim_type="relationship",
            summary=f"Observed {source_id} {relationship_type.value} {target_id}.",
            observed_at=observed_at,
            freshness=(
                FreshnessState.STALE
                if relationship_id == "rel.business.erp.depends-on.service"
                else FreshnessState.FRESH
            ),
        )
        observations.append(observation)
        relationships.append(
            _relationship(
                observation=observation,
                relationship_type=relationship_type,
                source_entity_id=source_id,
                target_entity_id=target_id,
            )
        )
        evidence.append(
            _evidence(
                f"evidence.{observation.observation_id}",
                observation.claim_summary,
                observed_at,
                observation.freshness,
            )
        )

    hidden_relationship_observation = _observation(
        observation_id="obs.graph.relationship.hidden",
        subject_id="rel.business.restricted.depends-on.b28",
        claim_type="relationship",
        summary="Observed a restricted dependency on the B28 storage system.",
        observed_at=observed_at,
        principals=RESTRICTED_PRINCIPALS,
        classification=DataClassification.RESTRICTED,
    )
    observations.append(hidden_relationship_observation)
    relationships.append(
        _relationship(
            observation=hidden_relationship_observation,
            relationship_type=RelationshipType.DEPENDS_ON,
            source_entity_id="entity.business-service.restricted",
            target_entity_id="asset.storage.lab.b28",
        )
    )
    evidence.append(
        GraphEvidence(
            reference="evidence.obs.graph.relationship.hidden",
            source="synthetic-restricted-cmdb",
            source_version="lab-graph-1.0",
            observed_at=observed_at,
            freshness=FreshnessState.FRESH,
            trust_basis="Restricted synthetic dependency mapping.",
            classification=DataClassification.RESTRICTED,
        )
    )

    return GraphSnapshot(
        snapshot_id="snapshot.graph.lab.001",
        schema_version="1.0",
        organization_id=organization_id,
        environment_id=environment_id,
        site_id=site_id,
        generated_at=observed_at,
        freshness=FreshnessState.AGING,
        completeness="partial",
        entities=tuple(entities),
        relationships=tuple(relationships),
        observations=tuple(observations),
        evidence=tuple(evidence),
        known_gaps=(
            "Storage multipathing and SAN fabric redundancy are not represented.",
            "The ERP business-service dependency is stale and requires CMDB validation.",
            "Runtime availability and failover telemetry are not part of this snapshot.",
        ),
        data_profile="synthetic_lab",
    )


class SyntheticGraphSnapshotProvider:
    """Serves the fixed lab-topology snapshot. Used when no configured connector is active."""

    def __init__(self, *, organization_id: str, environment: str) -> None:
        self._organization_id = organization_id
        self._environment = environment

    async def get_snapshot(self) -> GraphSnapshot:
        return build_synthetic_graph_snapshot(
            organization_id=self._organization_id, environment=self._environment
        )

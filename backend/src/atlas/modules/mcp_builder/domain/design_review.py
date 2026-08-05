from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.capabilities import CapabilityClass
from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class BuilderCapabilityDecisionKind(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"


@dataclass(frozen=True, slots=True)
class BuilderEntityMapping:
    source_entity: str
    atlas_entity: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.source_entity, "source entity")
        validate_stable_identifier(self.atlas_entity, "Atlas entity")


@dataclass(frozen=True, slots=True)
class BuilderCapabilityDecision:
    candidate_id: str
    decision: BuilderCapabilityDecisionKind
    analyzed_class: CapabilityClass
    confirmed_class: CapabilityClass
    required_permission: str
    rationale: str
    generation_eligible: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.candidate_id, "candidate id")
        supported = {
            CapabilityClass.C0_INFORMATIONAL,
            CapabilityClass.C1_READ_ONLY,
            CapabilityClass.C5_DESTRUCTIVE,
        }
        if self.analyzed_class not in supported or self.confirmed_class not in supported:
            raise ValueError("Builder design decision class is unsupported")
        if not self.required_permission.strip() or len(self.required_permission) > 160:
            raise ValueError("Builder required permission is outside platform bounds")
        if not self.rationale.strip() or len(self.rationale) > 1000:
            raise ValueError("Builder decision rationale is outside platform bounds")
        if self.generation_eligible != (self.decision is BuilderCapabilityDecisionKind.INCLUDE):
            raise ValueError("Builder generation eligibility does not match the human decision")


@dataclass(frozen=True, slots=True)
class McpBuilderDesignCheckpoint:
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
    target_products: tuple[str, ...]
    network_destinations: tuple[str, ...]
    configuration_keys: tuple[str, ...]
    secret_reference_ids: tuple[str, ...]
    entity_mappings: tuple[BuilderEntityMapping, ...]
    capability_decisions: tuple[BuilderCapabilityDecision, ...]
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    created_at: datetime
    ready_for_generation_design: bool = True
    generated_artifact_created: bool = False
    candidate_package_created: bool = False
    connector_registered: bool = False
    connector_installed: bool = False
    connector_enabled: bool = False
    network_request_performed: bool = False
    model_inference_performed: bool = False
    dynamic_code_execution_performed: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value, name in (
            (self.checkpoint_id, "checkpoint id"),
            (self.schema_version, "schema version"),
            (self.project_id, "project id"),
            (self.organization_id, "organization id"),
            (self.environment_id, "environment id"),
            (self.reviewer_id, "reviewer id"),
        ):
            validate_stable_identifier(value, name)
        if self.version != 1 or self.project_version < 1:
            raise ValueError("Builder checkpoint version is invalid")
        for value in (
            self.project_digest,
            self.source_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Builder checkpoint digest is invalid")
        if not self.connector_boundary.strip() or len(self.connector_boundary) > 1000:
            raise ValueError("Builder connector boundary is outside platform bounds")
        if not 1 <= len(self.target_products) <= 20 or any(
            not value.strip() or len(value) > 200 for value in self.target_products
        ):
            raise ValueError("Builder target products are outside platform bounds")
        if len(self.network_destinations) > 20 or any(
            not value.strip() or len(value) > 500 for value in self.network_destinations
        ):
            raise ValueError("Builder network destinations are outside platform bounds")
        if len(self.configuration_keys) > 50 or len(self.secret_reference_ids) > 50:
            raise ValueError("Builder configuration references exceed platform bounds")
        for value in (*self.configuration_keys, *self.secret_reference_ids):
            validate_stable_identifier(value, "Builder configuration reference")
        if not 1 <= len(self.entity_mappings) <= 100:
            raise ValueError("Builder entity mappings are required")
        if not self.capability_decisions or not any(
            decision.generation_eligible for decision in self.capability_decisions
        ):
            raise ValueError("Builder checkpoint requires an eligible capability")
        candidate_ids = [decision.candidate_id for decision in self.capability_decisions]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Builder checkpoint candidate decisions must be unique")
        if self.created_at.tzinfo is None or not 8 <= len(self.idempotency_key) <= 128:
            raise ValueError("Builder checkpoint timestamp or idempotency key is invalid")
        if not self.ready_for_generation_design:
            raise ValueError("Builder checkpoint must represent a completed design decision")
        if any(
            (
                self.generated_artifact_created,
                self.candidate_package_created,
                self.connector_registered,
                self.connector_installed,
                self.connector_enabled,
                self.network_request_performed,
                self.model_inference_performed,
                self.dynamic_code_execution_performed,
                self.runtime_trust_granted,
                self.execution_authorized,
                self.infrastructure_mutation_performed,
            )
        ):
            raise ValueError("Builder checkpoint violates the no-authority boundary")

"""ATLAS-015 SS6-8: Knowledge Source Classes, Registration, and Lifecycle.

A registered *source* is a producer of many knowledge items/versions over time (a documentation
site, a runbook repository, an incident system) -- a distinct concept from the per-*item*
governance chain already built for ATLAS-027 (`knowledge.domain.models.KnowledgeLifecycle`) and
from the per-*document* materialization/publication pipeline. Neither of those represents "a
source must be registered before ingestion" (SS7) or a source's own independent enable/suspend/
retire lifecycle (SS8) -- this module does.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.classification import DataClassification
from atlas.modules.identity.domain.models import validate_stable_identifier


class KnowledgeSourceClass(StrEnum):
    """SS6's seven named source classes. "Source class affects ranking and confidence but never
    overrides authorization" (SS6) needs no code here -- it is a downstream retrieval-ranking
    concern this registration record has no authorization field for a class to override."""

    VENDOR_AUTHORITATIVE = "vendor_authoritative"
    VENDOR_ADVISORY = "vendor_advisory"
    ORGANIZATIONAL_APPROVED = "organizational_approved"
    ORGANIZATIONAL_OPERATIONAL = "organizational_operational"
    SYSTEM_GENERATED = "system_generated"
    USER_PROVIDED_AD_HOC = "user_provided_ad_hoc"
    EXTERNAL_PUBLIC = "external_public"


class KnowledgeSourceLifecycleState(StrEnum):
    """SS8's seven named states."""

    REGISTERED = "registered"
    VALIDATING = "validating"
    ACTIVE = "active"
    DEGRADED = "degraded"
    SUSPENDED = "suspended"
    RETIRING = "retiring"
    RETIRED = "retired"


_SOURCE_LIFECYCLE_TRANSITIONS: dict[
    KnowledgeSourceLifecycleState, frozenset[KnowledgeSourceLifecycleState]
] = {
    KnowledgeSourceLifecycleState.REGISTERED: frozenset({KnowledgeSourceLifecycleState.VALIDATING}),
    KnowledgeSourceLifecycleState.VALIDATING: frozenset(
        {
            KnowledgeSourceLifecycleState.ACTIVE,
            KnowledgeSourceLifecycleState.REGISTERED,
            KnowledgeSourceLifecycleState.RETIRING,
        }
    ),
    KnowledgeSourceLifecycleState.ACTIVE: frozenset(
        {
            KnowledgeSourceLifecycleState.DEGRADED,
            KnowledgeSourceLifecycleState.SUSPENDED,
            KnowledgeSourceLifecycleState.RETIRING,
        }
    ),
    KnowledgeSourceLifecycleState.DEGRADED: frozenset(
        {
            KnowledgeSourceLifecycleState.ACTIVE,
            KnowledgeSourceLifecycleState.SUSPENDED,
            KnowledgeSourceLifecycleState.RETIRING,
        }
    ),
    KnowledgeSourceLifecycleState.SUSPENDED: frozenset(
        {
            KnowledgeSourceLifecycleState.VALIDATING,
            KnowledgeSourceLifecycleState.RETIRING,
        }
    ),
    KnowledgeSourceLifecycleState.RETIRING: frozenset({KnowledgeSourceLifecycleState.RETIRED}),
    KnowledgeSourceLifecycleState.RETIRED: frozenset(),
}


def is_valid_knowledge_source_transition(
    current: KnowledgeSourceLifecycleState, target: KnowledgeSourceLifecycleState
) -> bool:
    """SS8's seven-state lifecycle, reproduced as an explicit adjacency table (mirrors
    `RunbookLifecycleState`'s and `GuardrailLifecycleStage`'s established pattern)."""
    return target in _SOURCE_LIFECYCLE_TRANSITIONS[current]


def content_from_an_unregistered_source_is_eligible_for_retrieval() -> bool:
    """SS7: "A source must be registered before ingestion." SS8: a `REGISTERED` source's
    "content is not eligible for retrieval" -- only `ACTIVE`/`DEGRADED` publish content, and
    those states are reachable only after `VALIDATING`, never directly from `REGISTERED`."""
    return is_valid_knowledge_source_transition(
        KnowledgeSourceLifecycleState.REGISTERED, KnowledgeSourceLifecycleState.ACTIVE
    )


@dataclass(frozen=True, slots=True)
class KnowledgeSourceRegistration:
    """SS7's fourteen required registration elements."""

    source_id: str
    display_name: str
    source_type: str
    source_class: KnowledgeSourceClass
    owner: str
    technical_contact: str
    acquisition_method: str
    acquisition_endpoint: str
    secret_reference_id: str
    organization_id: str
    tenant_id: str
    environment_id: str
    vendor: str
    product: str
    default_classification: DataClassification
    access_mapping_method: str
    expected_version_behavior: str
    authority_trust_rationale: str
    retention_policy: str
    deletion_policy: str
    license_or_usage_restrictions: str
    ingestion_schedule: str
    failure_policy: str
    state: KnowledgeSourceLifecycleState
    registered_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        for value, name in (
            (self.source_id, "source_id"),
            (self.organization_id, "organization_id"),
            (self.environment_id, "environment_id"),
            (self.secret_reference_id, "secret_reference_id"),
        ):
            validate_stable_identifier(value, name)
        required = (
            self.display_name,
            self.source_type,
            self.owner,
            self.technical_contact,
            self.acquisition_method,
            self.acquisition_endpoint,
            self.tenant_id,
            self.vendor,
            self.product,
            self.access_mapping_method,
            self.expected_version_behavior,
            self.authority_trust_rationale,
            self.retention_policy,
            self.deletion_policy,
            self.license_or_usage_restrictions,
            self.ingestion_schedule,
            self.failure_policy,
        )
        if not all(value.strip() for value in required):
            raise ValueError(
                "a knowledge source registration requires every SS7 registration element"
            )
        if self.registered_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("knowledge source registration timestamps must be timezone-aware")
        if self.updated_at < self.registered_at:
            raise ValueError("a source cannot be updated before it was registered")

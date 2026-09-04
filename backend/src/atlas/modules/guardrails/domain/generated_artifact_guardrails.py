"""ATLAS-047 SS22: generated artifact guardrails.

The connector/MCP package governance pipeline (ATLAS-020/ATLAS-022, `modules/connectors` and
`modules/mcp_builder`) already implements SS22's full checklist for exactly one artifact type --
connectors. This module generalizes that pattern's *shape* (a checklist of discrete, individually
trackable gates that must all clear before production use) into a type-neutral model applicable
to all eight artifact types SS22 names, without re-implementing any of the eight already-built
connector-pipeline stages themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class GeneratedArtifactType(StrEnum):
    CONNECTOR = "connector"
    CODE = "code"
    RUNBOOK = "runbook"
    WORKFLOW = "workflow"
    POLICY = "policy"
    QUERY = "query"
    REPORT = "report"
    MAPPING = "mapping"
    DETECTION_RULE = "detection_rule"


class ArtifactControlGate(StrEnum):
    """SS22's checklist, as discrete, individually trackable gates rather than one boolean --
    a caller can report exactly which gates remain, not just "not ready.\""""

    LABELED_AI_GENERATED = "labeled_ai_generated"
    ISOLATED_PRODUCTION = "isolated_production"
    SCHEMA_SCAN = "schema_scan"
    STATIC_SCAN = "static_scan"
    DEPENDENCY_SCAN = "dependency_scan"
    LICENSE_SCAN = "license_scan"
    MALWARE_SCAN = "malware_scan"
    SECRET_SCAN = "secret_scan"
    SYNTHETIC_TARGET_TESTED = "synthetic_target_tested"
    ADVERSARIAL_TESTED = "adversarial_tested"
    FAILURE_TESTED = "failure_tested"
    TIMEOUT_TESTED = "timeout_tested"
    PERMISSION_TESTED = "permission_tested"
    SCOPE_TESTED = "scope_tested"
    DOMAIN_REVIEWED = "domain_reviewed"
    SECURITY_REVIEWED = "security_reviewed"
    SIGNED = "signed"


@dataclass(frozen=True, slots=True)
class GeneratedArtifact:
    artifact_id: str
    artifact_type: GeneratedArtifactType
    model_lineage: str
    version: str
    compatibility: str
    owner_identity_id: str
    expires_at: datetime | None
    rollback_available: bool
    completed_gates: frozenset[ArtifactControlGate]
    published_by_service_id: str | None
    self_granted_permissions: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.artifact_id, "artifact_id")
        if not self.model_lineage.strip():
            raise ValueError("a generated artifact requires recorded model lineage")
        if not self.version.strip():
            raise ValueError("a generated artifact requires a version")
        if not self.compatibility.strip():
            raise ValueError("a generated artifact requires a compatibility statement")
        validate_stable_identifier(self.owner_identity_id, "owner_identity_id")
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")

    @property
    def missing_gates(self) -> frozenset[ArtifactControlGate]:
        return frozenset(ArtifactControlGate) - self.completed_gates

    @property
    def is_ready_for_production(self) -> bool:
        """SS22: every gate cleared, published by an authorized service (never by the artifact's
        own generation process), and never self-granting its own permissions."""
        return (
            not self.missing_gates
            and self.published_by_service_id is not None
            and not self.self_granted_permissions
        )

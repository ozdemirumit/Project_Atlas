from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from atlas.core.capabilities import CapabilityClass
from atlas.core.classification import DataClassification
from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_HTTP_METHODS = frozenset({"get", "head", "options", "trace", "post", "put", "patch", "delete"})


def _digest(value: str, field_name: str) -> None:
    if not _DIGEST.fullmatch(value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")


class BuilderProjectState(StrEnum):
    ANALYZED = "analyzed"
    NEEDS_CLARIFICATION = "needs_clarification"


class BuilderFindingSeverity(StrEnum):
    INFORMATIONAL = "informational"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class BuilderFinding:
    code: str
    severity: BuilderFindingSeverity
    location: str
    message: str
    blocking: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.code, "finding code")
        if not self.location.startswith("/") or len(self.location) > 512:
            raise ValueError("finding location must be a bounded JSON pointer")
        if not self.message.strip() or len(self.message) > 500:
            raise ValueError("finding message is outside platform bounds")


@dataclass(frozen=True, slots=True)
class BuilderAuthenticationScheme:
    scheme_id: str
    scheme_type: str
    scheme: str | None
    location: str | None
    bearer_format: str | None
    requires_secret_reference: bool
    supported_for_unattended_use: bool
    finding_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.scheme_id, "authentication scheme id")
        if not self.scheme_type.strip() or len(self.scheme_type) > 64:
            raise ValueError("authentication scheme type is outside platform bounds")
        for code in self.finding_codes:
            validate_stable_identifier(code, "authentication finding code")


@dataclass(frozen=True, slots=True)
class BuilderCapabilityCandidate:
    candidate_id: str
    operation_id: str | None
    method: str
    path: str
    summary: str
    citation: str
    proposed_capability_class: CapabilityClass
    side_effects: tuple[str, ...]
    security_scheme_ids: tuple[str, ...]
    parameter_count: int
    response_codes: tuple[str, ...]
    request_body_present: bool
    confidence_basis: tuple[str, ...]
    clarification_codes: tuple[str, ...]
    generation_blocked: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.candidate_id, "candidate_id")
        if self.method not in _HTTP_METHODS:
            raise ValueError("candidate method is unsupported")
        if not self.path.startswith("/") or len(self.path) > 512:
            raise ValueError("candidate path is outside platform bounds")
        if not self.summary.strip() or len(self.summary) > 500:
            raise ValueError("candidate summary is outside platform bounds")
        if not self.citation.startswith("openapi://") or len(self.citation) > 1024:
            raise ValueError("candidate citation is invalid")
        if not 0 <= self.parameter_count <= 2000:
            raise ValueError("candidate parameter count is outside platform bounds")
        if not self.side_effects or not self.confidence_basis:
            raise ValueError("candidate side effects and confidence basis are required")
        if self.proposed_capability_class not in {
            CapabilityClass.C0_INFORMATIONAL,
            CapabilityClass.C1_READ_ONLY,
            CapabilityClass.C5_DESTRUCTIVE,
        }:
            raise ValueError("candidate capability class is outside the Builder foundation")
        if self.generation_blocked != (
            self.proposed_capability_class is CapabilityClass.C5_DESTRUCTIVE
            or bool(self.clarification_codes)
        ):
            raise ValueError("candidate blocked state does not match risk evidence")
        for scheme_id in self.security_scheme_ids:
            validate_stable_identifier(scheme_id, "candidate security scheme id")
        for code in self.clarification_codes:
            validate_stable_identifier(code, "candidate clarification code")


@dataclass(frozen=True, slots=True)
class McpBuilderProject:
    project_id: str
    schema_version: str
    version: int
    state: BuilderProjectState
    organization_id: str
    environment_id: str
    owner_id: str
    vendor: str
    product: str
    intended_product_versions: tuple[str, ...]
    target_environment: str
    sdk_profile: str
    source_id: str
    source_authority: str
    source_owner: str
    documentation_version: str
    publication_date: date
    license_id: str
    redistribution_allowed: bool
    classification: DataClassification
    openapi_version: str
    api_title: str
    api_version: str
    source_digest: str
    source_size_bytes: int
    canonical_source_json: str
    declared_servers: tuple[str, ...]
    authentication_schemes: tuple[BuilderAuthenticationScheme, ...]
    capability_candidates: tuple[BuilderCapabilityCandidate, ...]
    findings: tuple[BuilderFinding, ...]
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    created_at: datetime
    analyzed_at: datetime
    synthetic_or_lab_only: bool = True
    generated_artifact_created: bool = False
    candidate_package_created: bool = False
    connector_registered: bool = False
    connector_installed: bool = False
    connector_enabled: bool = False
    network_request_performed: bool = False
    model_inference_performed: bool = False
    dynamic_code_execution_performed: bool = False
    runtime_trust_granted: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value, name in (
            (self.project_id, "project_id"),
            (self.schema_version, "schema_version"),
            (self.organization_id, "organization_id"),
            (self.environment_id, "environment_id"),
            (self.owner_id, "owner_id"),
            (self.sdk_profile, "sdk_profile"),
            (self.source_id, "source_id"),
        ):
            validate_stable_identifier(value, name)
        if self.version != 1:
            raise ValueError("Builder project version must start at one")
        if not all(
            value.strip()
            for value in (
                self.vendor,
                self.product,
                self.target_environment,
                self.source_authority,
                self.source_owner,
                self.documentation_version,
                self.license_id,
                self.api_title,
                self.api_version,
                self.canonical_source_json,
                self.idempotency_key,
            )
        ):
            raise ValueError("Builder project identity and source metadata are required")
        if not self.intended_product_versions:
            raise ValueError("intended product versions are required")
        if self.openapi_version.split(".")[:2] not in (["3", "0"], ["3", "1"]):
            raise ValueError("OpenAPI version must be 3.0 or 3.1")
        if not 1 <= self.source_size_bytes <= 524_288:
            raise ValueError("Builder source size is outside platform bounds")
        _digest(self.source_digest, "source_digest")
        _digest(self.canonical_digest, "canonical_digest")
        _digest(self.request_fingerprint, "request_fingerprint")
        if self.created_at.tzinfo is None or self.analyzed_at.tzinfo is None:
            raise ValueError("Builder project timestamps must be timezone-aware")
        if not self.synthetic_or_lab_only:
            raise ValueError("Builder foundation projects must remain synthetic or lab only")
        candidate_ids = [item.candidate_id for item in self.capability_candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Builder candidate identifiers must be unique")
        scheme_ids = [item.scheme_id for item in self.authentication_schemes]
        if len(scheme_ids) != len(set(scheme_ids)):
            raise ValueError("Builder authentication scheme identifiers must be unique")
        has_blocking = any(item.blocking for item in self.findings) or any(
            item.generation_blocked for item in self.capability_candidates
        )
        expected_state = (
            BuilderProjectState.NEEDS_CLARIFICATION
            if has_blocking or not self.capability_candidates
            else BuilderProjectState.ANALYZED
        )
        if self.state is not expected_state:
            raise ValueError("Builder project state does not match analysis evidence")
        safety = (
            self.generated_artifact_created,
            self.candidate_package_created,
            self.connector_registered,
            self.connector_installed,
            self.connector_enabled,
            self.network_request_performed,
            self.model_inference_performed,
            self.dynamic_code_execution_performed,
            self.runtime_trust_granted,
        )
        if any(safety):
            raise ValueError("Builder source analysis cannot grant runtime trust or perform work")

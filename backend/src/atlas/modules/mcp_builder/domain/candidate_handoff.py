from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_SAFE_FILENAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}\.zip$")


class CandidateHandoffState(StrEnum):
    CANDIDATE_QUARANTINED = "candidate_quarantined"


class CandidateSignatureState(StrEnum):
    UNSIGNED = "unsigned"


@dataclass(frozen=True, slots=True)
class CandidateCapabilityEvidence:
    candidate_id: str
    capability_class: str
    required_permission: str
    supported_product_versions: tuple[str, ...]
    source_citations: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.candidate_id, "candidate id")
        if self.capability_class not in {"C0", "C1"}:
            raise ValueError("Candidate handoff capability class is unsupported")
        if not self.required_permission.strip() or len(self.required_permission) > 300:
            raise ValueError("Candidate handoff permission is invalid")
        for values, name in (
            (self.supported_product_versions, "supported product versions"),
            (self.source_citations, "source citations"),
        ):
            if not values or len(values) > 50 or len(values) != len(set(values)):
                raise ValueError(f"Candidate handoff {name} are invalid")
            if any(not value.strip() or len(value) > 500 for value in values):
                raise ValueError(f"Candidate handoff {name} are invalid")


@dataclass(frozen=True, slots=True)
class McpBuilderCandidateHandoff:
    handoff_id: str
    schema_version: str
    version: int
    state: CandidateHandoffState
    project_id: str
    project_version: int
    project_digest: str
    source_digest: str
    checkpoint_id: str
    checkpoint_digest: str
    generation_id: str
    generation_digest: str
    artifact_digest: str
    validation_id: str
    validation_digest: str
    domain_review_id: str
    domain_review_digest: str
    domain_reviewed_by: str
    security_review_id: str
    security_review_digest: str
    security_reviewed_by: str
    lab_validation_id: str
    lab_validation_digest: str
    lab_operated_by: str
    organization_id: str
    environment_id: str
    custodied_by: str
    handoff_profile: str
    archive_contract_version: str
    package_filename: str
    package_digest: str
    package_size_bytes: int
    package_entry_count: int
    generated_file_count: int
    generated_size_bytes: int
    envelope_digest: str
    signature_state: CandidateSignatureState
    capabilities: tuple[CandidateCapabilityEvidence, ...]
    network_destinations: tuple[str, ...]
    limitations: tuple[str, ...]
    unsupported_behavior: tuple[str, ...]
    manual_change_count: int
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    created_at: datetime
    candidate_package_created: bool = True
    package_signed: bool = False
    publisher_attested: bool = False
    registry_validation_completed: bool = False
    connector_registered: bool = False
    connector_installed: bool = False
    connector_enabled: bool = False
    target_configured: bool = False
    credentials_resolved: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value, name in (
            (self.handoff_id, "handoff id"),
            (self.schema_version, "schema version"),
            (self.project_id, "project id"),
            (self.checkpoint_id, "checkpoint id"),
            (self.generation_id, "generation id"),
            (self.validation_id, "validation id"),
            (self.domain_review_id, "domain review id"),
            (self.domain_reviewed_by, "domain reviewer id"),
            (self.security_review_id, "security review id"),
            (self.security_reviewed_by, "security reviewer id"),
            (self.lab_validation_id, "lab validation id"),
            (self.lab_operated_by, "lab operator id"),
            (self.organization_id, "organization id"),
            (self.environment_id, "environment id"),
            (self.custodied_by, "package custodian id"),
            (self.handoff_profile, "handoff profile"),
            (self.archive_contract_version, "archive contract version"),
        ):
            validate_stable_identifier(value, name)
        if self.version != 1 or self.project_version != 1:
            raise ValueError("Candidate handoff version is invalid")
        for value in (
            self.project_digest,
            self.source_digest,
            self.checkpoint_digest,
            self.generation_digest,
            self.artifact_digest,
            self.validation_digest,
            self.domain_review_digest,
            self.security_review_digest,
            self.lab_validation_digest,
            self.package_digest,
            self.envelope_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Candidate handoff digest is invalid")
        if _SAFE_FILENAME.fullmatch(self.package_filename) is None:
            raise ValueError("Candidate handoff filename is invalid")
        if self.signature_state is not CandidateSignatureState.UNSIGNED:
            raise ValueError("Candidate handoff must remain unsigned")
        if self.custodied_by in {
            self.domain_reviewed_by,
            self.security_reviewed_by,
            self.lab_operated_by,
        }:
            raise ValueError("Candidate handoff violates separation of duties")
        if not self.capabilities or len(self.capabilities) > 100:
            raise ValueError("Candidate handoff capabilities are invalid")
        if len({item.candidate_id for item in self.capabilities}) != len(self.capabilities):
            raise ValueError("Candidate handoff capabilities are duplicated")
        if self.package_entry_count != self.generated_file_count + 1:
            raise ValueError("Candidate handoff archive entry count is invalid")
        if (
            not 1 <= self.generated_file_count <= 500
            or not 1 <= self.generated_size_bytes <= 20_000_000
        ):
            raise ValueError("Candidate handoff generated artifact bounds are invalid")
        if not 1 <= self.package_size_bytes <= 25_000_000 or self.manual_change_count != 0:
            raise ValueError("Candidate handoff archive bounds are invalid")
        for values, limit, name in (
            (self.network_destinations, 100, "network destinations"),
            (self.limitations, 30, "limitations"),
            (self.unsupported_behavior, 30, "unsupported behavior"),
        ):
            if not values or len(values) > limit or len(values) != len(set(values)):
                raise ValueError(f"Candidate handoff {name} are invalid")
            if any(not value.strip() or len(value) > 500 for value in values):
                raise ValueError(f"Candidate handoff {name} are invalid")
        if self.created_at.tzinfo is None or not 8 <= len(self.idempotency_key) <= 128:
            raise ValueError("Candidate handoff timestamp or idempotency key is invalid")
        if not self.candidate_package_created or any(
            (
                self.package_signed,
                self.publisher_attested,
                self.registry_validation_completed,
                self.connector_registered,
                self.connector_installed,
                self.connector_enabled,
                self.target_configured,
                self.credentials_resolved,
                self.runtime_trust_granted,
                self.execution_authorized,
                self.deployment_approved,
                self.infrastructure_mutation_performed,
            )
        ):
            raise ValueError("Candidate handoff violates the no-authority boundary")

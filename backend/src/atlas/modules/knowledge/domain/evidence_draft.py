from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
DRAFT_OPERATIONAL_KNOWLEDGE_CREATED = "draft_operational_knowledge_created"


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "operational evidence knowledge draft identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class OperationalEvidenceKnowledgeDraftPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_source_schema: str
    required_source_state: str
    required_adapter_id: str
    required_adapter_attestor_id: str
    required_receipt_schema: str
    draft_domain: str
    content_type: str
    source_authority: str
    language: str
    title_template_id: str
    title_template_digest: str
    maximum_source_age_minutes: int
    maximum_draft_items: int
    maximum_draft_bytes: int
    require_classification_inheritance: bool
    require_access_policy_inheritance: bool
    require_retention_policy_inheritance: bool
    require_encryption_profile_inheritance: bool
    required_assurance_level: AssuranceLevel
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.policy_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.policy_version,
            self.required_source_schema,
            self.required_source_state,
            self.required_adapter_id,
            self.required_adapter_attestor_id,
            self.required_receipt_schema,
            self.draft_domain,
            self.content_type,
            self.source_authority,
            self.language,
            self.title_template_id,
            self.signed_by,
        )
        if (
            self.version != 1
            or not 1 <= self.maximum_source_age_minutes <= 1440
            or not 1 <= self.maximum_draft_items <= 1000
            or not 1 <= self.maximum_draft_bytes <= 1_048_576
            or self.required_assurance_level is not AssuranceLevel.HARDWARE_BACKED
            or not all(
                (
                    self.require_classification_inheritance,
                    self.require_access_policy_inheritance,
                    self.require_retention_policy_inheritance,
                    self.require_encryption_profile_inheritance,
                    self.signature_verified,
                )
            )
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or not _digests(self.title_template_digest, self.canonical_digest)
        ):
            raise ValueError("Operational evidence knowledge draft policy is invalid")


@dataclass(frozen=True, slots=True)
class OperationalEvidenceKnowledgeDraftInstruction:
    draft_id: str
    organization_id: str
    environment_id: str
    source_ingestion_id: str
    source_ingestion_digest: str
    evidence_package_id: str
    evidence_schema_version: str
    evidence_content_digest: str
    evidence_metadata_digest: str
    connector_id: str
    display_name: str
    capability_id: str
    classification: str
    access_policy_id: str
    access_policy_digest: str
    retention_policy_id: str
    retention_policy_digest: str
    encryption_profile_id: str
    encryption_profile_digest: str
    evidence_item_count: int
    evidence_bytes: int
    observed_from: datetime
    observed_to: datetime
    source_ingested_at: datetime
    draft_domain: str
    content_type: str
    source_authority: str
    language: str
    title_template_id: str
    title_template_digest: str
    maximum_draft_items: int
    maximum_draft_bytes: int
    curation_policy_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.draft_id,
            self.organization_id,
            self.environment_id,
            self.source_ingestion_id,
            self.evidence_package_id,
            self.evidence_schema_version,
            self.connector_id,
            self.capability_id,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
            self.draft_domain,
            self.content_type,
            self.source_authority,
            self.language,
            self.title_template_id,
        )
        if (
            not self.display_name.strip()
            or not 1 <= self.evidence_item_count <= self.maximum_draft_items <= 1000
            or not 0 <= self.evidence_bytes <= self.maximum_draft_bytes <= 1_048_576
            or any(
                value.tzinfo is None
                for value in (self.observed_from, self.observed_to, self.source_ingested_at)
            )
            or self.observed_to < self.observed_from
            or self.source_ingested_at < self.observed_to
            or not _digests(
                self.source_ingestion_digest,
                self.evidence_content_digest,
                self.evidence_metadata_digest,
                self.access_policy_digest,
                self.retention_policy_digest,
                self.encryption_profile_digest,
                self.title_template_digest,
                self.curation_policy_digest,
            )
        ):
            raise ValueError("Operational evidence knowledge draft instruction is invalid")


@dataclass(frozen=True, slots=True)
class OperationalEvidenceKnowledgeDraftReceipt:
    draft_id: str
    schema_version: str
    version: int
    adapter_id: str
    attested_by: str
    source_ingestion_digest: str
    evidence_package_id: str
    evidence_content_digest: str
    knowledge_item_id: str
    draft_version_id: str
    draft_artifact_id: str
    draft_schema_version: str
    title: str
    draft_domain: str
    content_type: str
    source_authority: str
    language: str
    knowledge_lifecycle: str
    classification: str
    access_policy_id: str
    access_policy_digest: str
    retention_policy_id: str
    retention_policy_digest: str
    encryption_profile_id: str
    encryption_profile_digest: str
    draft_content_digest: str
    draft_metadata_digest: str
    provenance_digest: str
    draft_access_digest: str
    draft_retention_digest: str
    draft_item_count: int
    draft_bytes: int
    observed_from: datetime
    observed_to: datetime
    created_at: datetime
    immutable_draft_confirmed: bool
    encrypted_at_rest: bool
    transient_buffers_erased: bool
    artifact_channel_closed: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.draft_id,
            self.schema_version,
            self.adapter_id,
            self.attested_by,
            self.evidence_package_id,
            self.knowledge_item_id,
            self.draft_version_id,
            self.draft_artifact_id,
            self.draft_schema_version,
            self.draft_domain,
            self.content_type,
            self.source_authority,
            self.language,
            self.knowledge_lifecycle,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
        )
        if (
            self.version != 1
            or not 1 <= len(self.title.strip()) <= 200
            or self.knowledge_lifecycle != "draft"
            or not 1 <= self.draft_item_count <= 1000
            or not 0 <= self.draft_bytes <= 1_048_576
            or any(
                value.tzinfo is None
                for value in (self.observed_from, self.observed_to, self.created_at)
            )
            or self.observed_to < self.observed_from
            or self.created_at < self.observed_to
            or not all(
                (
                    self.immutable_draft_confirmed,
                    self.encrypted_at_rest,
                    self.transient_buffers_erased,
                    self.artifact_channel_closed,
                    self.signature_verified,
                )
            )
            or not _digests(
                self.source_ingestion_digest,
                self.evidence_content_digest,
                self.access_policy_digest,
                self.retention_policy_digest,
                self.encryption_profile_digest,
                self.draft_content_digest,
                self.draft_metadata_digest,
                self.provenance_digest,
                self.draft_access_digest,
                self.draft_retention_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational evidence knowledge draft receipt is invalid")


@dataclass(frozen=True, slots=True)
class OperationalEvidenceKnowledgeDraftClaim:
    claim_id: str
    schema_version: str
    version: int
    source_ingestion_id: str
    source_ingestion_digest: str
    draft_id: str
    organization_id: str
    environment_id: str
    claimed_by: str
    purpose: str
    claimed_at: datetime
    request_binding_digest: str
    idempotency_digest: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.claim_id,
            self.schema_version,
            self.source_ingestion_id,
            self.draft_id,
            self.organization_id,
            self.environment_id,
            self.claimed_by,
        )
        if (
            self.version != 1
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.claimed_at.tzinfo is None
            or not _digests(
                self.source_ingestion_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational evidence knowledge draft claim is invalid")


@dataclass(frozen=True, slots=True)
class OperationalEvidenceKnowledgeDraftRecord:
    draft_id: str
    schema_version: str
    version: int
    claim_id: str
    source_ingestion_id: str
    source_ingestion_digest: str
    organization_id: str
    environment_id: str
    source_invocation_id: str
    evidence_package_id: str
    evidence_content_digest: str
    evidence_metadata_digest: str
    connector_id: str
    instance_id: str
    capability_id: str
    knowledge_item_id: str
    draft_version_id: str
    draft_artifact_id: str
    draft_schema_version: str
    title: str
    draft_domain: str
    content_type: str
    source_authority: str
    language: str
    knowledge_lifecycle: str
    classification: str
    access_policy_id: str
    access_policy_digest: str
    retention_policy_id: str
    retention_policy_digest: str
    encryption_profile_id: str
    encryption_profile_digest: str
    draft_content_digest: str
    draft_metadata_digest: str
    provenance_digest: str
    draft_access_digest: str
    draft_retention_digest: str
    curation_policy_id: str
    curation_policy_digest: str
    curation_policy_version: str
    curation_adapter_id: str
    draft_item_count: int
    draft_bytes: int
    observed_from: datetime
    observed_to: datetime
    created_at: datetime
    instance_state: str
    curated_by: str
    purpose: str
    canonical_digest: str
    evidence_ingested: bool = True
    knowledge_item_created: bool = True
    immutable_draft_confirmed: bool = True
    encrypted_at_rest: bool = True
    transient_buffers_erased: bool = True
    artifact_channel_closed: bool = True
    domain_review_completed: bool = False
    security_review_completed: bool = False
    knowledge_approved: bool = False
    knowledge_published: bool = False
    chunks_created: bool = False
    embeddings_created: bool = False
    retrieval_published: bool = False
    model_context_available: bool = False
    graph_updated: bool = False
    scheduled: bool = False
    workflow_continued: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        _ids(
            self.draft_id,
            self.schema_version,
            self.claim_id,
            self.source_ingestion_id,
            self.organization_id,
            self.environment_id,
            self.source_invocation_id,
            self.evidence_package_id,
            self.connector_id,
            self.instance_id,
            self.capability_id,
            self.knowledge_item_id,
            self.draft_version_id,
            self.draft_artifact_id,
            self.draft_schema_version,
            self.draft_domain,
            self.content_type,
            self.source_authority,
            self.language,
            self.knowledge_lifecycle,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
            self.curation_policy_id,
            self.curation_policy_version,
            self.curation_adapter_id,
            self.instance_state,
            self.curated_by,
        )
        later_authority = (
            self.domain_review_completed,
            self.security_review_completed,
            self.knowledge_approved,
            self.knowledge_published,
            self.chunks_created,
            self.embeddings_created,
            self.retrieval_published,
            self.model_context_available,
            self.graph_updated,
            self.scheduled,
            self.workflow_continued,
            self.execution_authorized,
            self.deployment_approved,
            self.infrastructure_mutation_performed,
        )
        if (
            self.version != 1
            or self.instance_state != DRAFT_OPERATIONAL_KNOWLEDGE_CREATED
            or self.knowledge_lifecycle != "draft"
            or self.draft_domain != "domain.operational"
            or self.source_authority != "source-authority.system-generated"
            or not 1 <= len(self.title.strip()) <= 200
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 1 <= self.draft_item_count <= 1000
            or not 0 <= self.draft_bytes <= 1_048_576
            or any(
                value.tzinfo is None
                for value in (self.observed_from, self.observed_to, self.created_at)
            )
            or self.observed_to < self.observed_from
            or self.created_at < self.observed_to
            or not _digests(
                self.source_ingestion_digest,
                self.evidence_content_digest,
                self.evidence_metadata_digest,
                self.access_policy_digest,
                self.retention_policy_digest,
                self.encryption_profile_digest,
                self.draft_content_digest,
                self.draft_metadata_digest,
                self.provenance_digest,
                self.draft_access_digest,
                self.draft_retention_digest,
                self.curation_policy_digest,
                self.canonical_digest,
            )
            or not all(
                (
                    self.evidence_ingested,
                    self.knowledge_item_created,
                    self.immutable_draft_confirmed,
                    self.encrypted_at_rest,
                    self.transient_buffers_erased,
                    self.artifact_channel_closed,
                )
            )
            or any(later_authority)
        ):
            raise ValueError("Operational evidence knowledge draft record is invalid")

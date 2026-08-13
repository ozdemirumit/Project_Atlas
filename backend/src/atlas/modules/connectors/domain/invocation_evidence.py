from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
ENABLED_INVOCATION_EVIDENCE_INGESTED = "enabled_invocation_evidence_ingested"


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "connector invocation evidence identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class ConnectorInvocationEvidencePolicySnapshot:
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
    required_classification: str
    access_policy_id: str
    access_policy_digest: str
    retention_policy_id: str
    retention_policy_digest: str
    encryption_profile_id: str
    encryption_profile_digest: str
    maximum_source_age_minutes: int
    maximum_evidence_items: int
    maximum_evidence_bytes: int
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
            self.required_classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
            self.signed_by,
        )
        if (
            self.version != 1
            or not 1 <= self.maximum_source_age_minutes <= 1440
            or not 1 <= self.maximum_evidence_items <= 1000
            or not 1 <= self.maximum_evidence_bytes <= 1_048_576
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or not _digests(
                self.access_policy_digest,
                self.retention_policy_digest,
                self.encryption_profile_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Connector invocation evidence policy contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorInvocationEvidenceInstruction:
    ingestion_id: str
    organization_id: str
    environment_id: str
    source_invocation_id: str
    source_invocation_digest: str
    connector_id: str
    instance_id: str
    capability_id: str
    output_schema_digest: str
    result_policy_digest: str
    normalized_redacted_result_digest: str
    source_observation_count: int
    source_output_bytes: int
    source_started_at: datetime
    source_completed_at: datetime
    classification: str
    access_policy_id: str
    access_policy_digest: str
    retention_policy_id: str
    retention_policy_digest: str
    encryption_profile_id: str
    encryption_profile_digest: str
    maximum_evidence_items: int
    maximum_evidence_bytes: int
    ingestion_policy_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.ingestion_id,
            self.organization_id,
            self.environment_id,
            self.source_invocation_id,
            self.connector_id,
            self.instance_id,
            self.capability_id,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
        )
        if (
            not 1 <= self.source_observation_count <= self.maximum_evidence_items <= 1000
            or not 0 <= self.source_output_bytes <= self.maximum_evidence_bytes <= 1_048_576
            or self.source_started_at.tzinfo is None
            or self.source_completed_at.tzinfo is None
            or self.source_completed_at < self.source_started_at
            or not _digests(
                self.source_invocation_digest,
                self.output_schema_digest,
                self.result_policy_digest,
                self.normalized_redacted_result_digest,
                self.access_policy_digest,
                self.retention_policy_digest,
                self.encryption_profile_digest,
                self.ingestion_policy_digest,
            )
        ):
            raise ValueError("Connector invocation evidence instruction is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorInvocationEvidenceReceipt:
    ingestion_id: str
    schema_version: str
    version: int
    adapter_id: str
    attested_by: str
    source_invocation_digest: str
    normalized_redacted_result_digest: str
    evidence_package_id: str
    evidence_schema_version: str
    evidence_content_digest: str
    evidence_metadata_digest: str
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
    ingested_at: datetime
    immutable_storage_confirmed: bool
    encrypted_at_rest: bool
    transient_buffers_erased: bool
    artifact_channel_closed: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.ingestion_id,
            self.schema_version,
            self.adapter_id,
            self.attested_by,
            self.evidence_package_id,
            self.evidence_schema_version,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
        )
        if (
            self.version != 1
            or not 1 <= self.evidence_item_count <= 1000
            or not 0 <= self.evidence_bytes <= 1_048_576
            or any(
                value.tzinfo is None
                for value in (self.observed_from, self.observed_to, self.ingested_at)
            )
            or self.observed_to < self.observed_from
            or self.ingested_at < self.observed_to
            or not all(
                (
                    self.immutable_storage_confirmed,
                    self.encrypted_at_rest,
                    self.transient_buffers_erased,
                    self.artifact_channel_closed,
                    self.signature_verified,
                )
            )
            or not _digests(
                self.source_invocation_digest,
                self.normalized_redacted_result_digest,
                self.evidence_content_digest,
                self.evidence_metadata_digest,
                self.access_policy_digest,
                self.retention_policy_digest,
                self.encryption_profile_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Connector invocation evidence receipt is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorInvocationEvidenceClaim:
    claim_id: str
    schema_version: str
    version: int
    source_invocation_id: str
    source_invocation_digest: str
    ingestion_id: str
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
            self.source_invocation_id,
            self.ingestion_id,
            self.organization_id,
            self.environment_id,
            self.claimed_by,
        )
        if (
            self.version != 1
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.claimed_at.tzinfo is None
            or not _digests(
                self.source_invocation_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Connector invocation evidence claim is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorInvocationEvidenceRecord:
    ingestion_id: str
    schema_version: str
    version: int
    claim_id: str
    source_invocation_id: str
    source_invocation_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    connector_id: str
    release_version: str
    manifest_digest: str
    instance_id: str
    instance_key: str
    display_name: str
    capability_id: str
    capability_class: str
    required_permission: str
    output_schema_digest: str
    result_policy_digest: str
    normalized_redacted_result_digest: str
    evidence_package_id: str
    evidence_schema_version: str
    evidence_content_digest: str
    evidence_metadata_digest: str
    classification: str
    access_policy_id: str
    access_policy_digest: str
    retention_policy_id: str
    retention_policy_digest: str
    encryption_profile_id: str
    encryption_profile_digest: str
    ingestion_policy_id: str
    ingestion_policy_digest: str
    ingestion_policy_version: str
    ingestion_adapter_id: str
    evidence_item_count: int
    evidence_bytes: int
    observed_from: datetime
    observed_to: datetime
    ingested_at: datetime
    instance_state: str
    ingested_by: str
    purpose: str
    canonical_digest: str
    source_invocation_completed: bool = True
    evidence_ingested: bool = True
    immutable_storage_confirmed: bool = True
    encrypted_at_rest: bool = True
    transient_buffers_erased: bool = True
    artifact_channel_closed: bool = True
    knowledge_item_created: bool = False
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
            self.ingestion_id,
            self.schema_version,
            self.claim_id,
            self.source_invocation_id,
            self.organization_id,
            self.environment_id,
            self.connector_id,
            self.release_version,
            self.instance_id,
            self.instance_key,
            self.capability_id,
            self.required_permission,
            self.evidence_package_id,
            self.evidence_schema_version,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
            self.ingestion_policy_id,
            self.ingestion_policy_version,
            self.ingestion_adapter_id,
            self.instance_state,
            self.ingested_by,
        )
        if (
            self.version != 1
            or self.instance_state != ENABLED_INVOCATION_EVIDENCE_INGESTED
            or self.capability_class not in {"C0", "C1"}
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 1 <= self.evidence_item_count <= 1000
            or not 0 <= self.evidence_bytes <= 1_048_576
            or any(
                value.tzinfo is None
                for value in (self.observed_from, self.observed_to, self.ingested_at)
            )
            or self.observed_to < self.observed_from
            or self.ingested_at < self.observed_to
            or not _digests(
                self.source_invocation_digest,
                self.package_digest,
                self.manifest_digest,
                self.output_schema_digest,
                self.result_policy_digest,
                self.normalized_redacted_result_digest,
                self.evidence_content_digest,
                self.evidence_metadata_digest,
                self.access_policy_digest,
                self.retention_policy_digest,
                self.encryption_profile_digest,
                self.ingestion_policy_digest,
                self.canonical_digest,
            )
            or not all(
                (
                    self.source_invocation_completed,
                    self.evidence_ingested,
                    self.immutable_storage_confirmed,
                    self.encrypted_at_rest,
                    self.transient_buffers_erased,
                    self.artifact_channel_closed,
                )
            )
            or any(
                (
                    self.knowledge_item_created,
                    self.retrieval_published,
                    self.model_context_available,
                    self.graph_updated,
                    self.scheduled,
                    self.workflow_continued,
                    self.execution_authorized,
                    self.deployment_approved,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Connector invocation evidence record is invalid")

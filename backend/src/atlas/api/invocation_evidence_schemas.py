from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.invocation_evidence import (
    ConnectorInvocationEvidenceRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorInvocationEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-invocation-evidence-input.v1", pattern=STABLE_ID
    )
    source_invocation_id: str = Field(pattern=STABLE_ID)
    source_invocation_digest: str = Field(pattern=DIGEST)
    ingestion_policy_id: str = Field(pattern=STABLE_ID)
    ingestion_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_ingestion_is_one_way_and_does_not_publish_knowledge_or_grant_authority: bool


class ConnectorInvocationEvidenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    source_invocation_completed: bool
    evidence_ingested: bool
    immutable_storage_confirmed: bool
    encrypted_at_rest: bool
    transient_buffers_erased: bool
    artifact_channel_closed: bool
    knowledge_item_created: bool
    retrieval_published: bool
    model_context_available: bool
    graph_updated: bool
    scheduled: bool
    workflow_continued: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, record: ConnectorInvocationEvidenceRecord
    ) -> ConnectorInvocationEvidenceData:
        return cls.model_validate(record, from_attributes=True)


class ConnectorInvocationEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorInvocationEvidenceData
    meta: ResponseMeta

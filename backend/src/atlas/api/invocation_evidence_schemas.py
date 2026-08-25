from __future__ import annotations

from datetime import datetime
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.application.invocation_evidence import (
    ConnectorInvocationEvidenceOption,
)
from atlas.modules.connectors.domain.invocation_evidence import (
    ConnectorInvocationEvidenceRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorInvocationEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.connector-invocation-evidence-input.v1"] = (
        "atlas.connector-invocation-evidence-input.v1"
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


class ConnectorInvocationEvidenceInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingestion_id: str
    schema_version: str
    version: int
    source_invocation_id: str
    source_invocation_digest: str
    package_digest: str
    capability_id: str
    capability_class: Literal["C0", "C1"]
    required_permission: str
    normalized_redacted_result_digest: str
    evidence_package_id: str
    evidence_schema_version: str
    evidence_content_digest: str
    evidence_metadata_digest: str
    classification: str
    retention_policy_id: str
    retention_policy_digest: str
    ingestion_policy_id: str
    ingestion_policy_digest: str
    ingestion_policy_version: str
    evidence_item_count: int
    evidence_bytes: int
    observed_from: datetime
    observed_to: datetime
    ingested_at: datetime
    instance_state: Literal["enabled_invocation_evidence_ingested"]
    canonical_digest: str
    source_invocation_completed: Literal[True]
    evidence_ingested: Literal[True]
    immutable_storage_confirmed: Literal[True]
    encrypted_at_rest: Literal[True]
    transient_buffers_erased: Literal[True]
    artifact_channel_closed: Literal[True]
    knowledge_item_created: Literal[False]
    retrieval_published: Literal[False]
    model_context_available: Literal[False]
    graph_updated: Literal[False]
    scheduled: Literal[False]
    workflow_continued: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]
    reused: bool

    @classmethod
    def from_domain(
        cls, record: ConnectorInvocationEvidenceRecord
    ) -> ConnectorInvocationEvidenceInventoryData:
        return cls.model_validate(record, from_attributes=True)


class ConnectorInvocationEvidenceInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorInvocationEvidenceInventoryData, ...]
    meta: ResponseMeta


class ConnectorInvocationEvidenceInventoryItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorInvocationEvidenceInventoryData
    meta: ResponseMeta


class ConnectorInvocationEvidenceOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_invocation_id: str
    source_invocation_digest: str
    capability_id: str
    capability_class: Literal["C0", "C1"]
    required_permission: str
    ingestion_policy_id: str
    ingestion_policy_digest: str
    ingestion_policy_version: str
    ingestion_policy_expires_at: datetime
    required_assurance_level: Literal["single_factor", "multi_factor", "hardware_backed"]
    classification: str
    retention_policy_id: str
    maximum_evidence_items: int
    maximum_evidence_bytes: int
    resulting_instance_state: Literal["enabled_invocation_evidence_ingested"]
    irreversible_claim_required: Literal[True]
    automatic_retry_allowed: Literal[False]
    knowledge_item_created: Literal[False]
    retrieval_published: Literal[False]
    model_context_available: Literal[False]
    graph_updated: Literal[False]
    scheduled: Literal[False]
    workflow_continued: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_application(
        cls, option: ConnectorInvocationEvidenceOption
    ) -> ConnectorInvocationEvidenceOptionData:
        return cls(
            **{
                field: getattr(option, field)
                for field in ConnectorInvocationEvidenceOption.__dataclass_fields__
                if field not in {"capability_class", "required_assurance_level"}
            },
            capability_class=cast(Literal["C0", "C1"], option.capability_class),
            required_assurance_level=cast(
                Literal["single_factor", "multi_factor", "hardware_backed"],
                option.required_assurance_level.value,
            ),
            resulting_instance_state="enabled_invocation_evidence_ingested",
            irreversible_claim_required=True,
            automatic_retry_allowed=False,
            knowledge_item_created=False,
            retrieval_published=False,
            model_context_available=False,
            graph_updated=False,
            scheduled=False,
            workflow_continued=False,
            execution_authorized=False,
            deployment_approved=False,
            infrastructure_mutation_performed=False,
        )


class ConnectorInvocationEvidenceOptionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorInvocationEvidenceOptionData, ...]
    meta: ResponseMeta

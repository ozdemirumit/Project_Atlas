from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.core.classification import DataClassification
from atlas.modules.knowledge.domain.source_registration import (
    KnowledgeSourceClass,
    KnowledgeSourceLifecycleState,
    KnowledgeSourceRegistration,
)


class KnowledgeSourceRegistrationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=256)
    source_type: str = Field(min_length=1, max_length=128)
    source_class: KnowledgeSourceClass
    owner: str = Field(min_length=1, max_length=128)
    technical_contact: str = Field(min_length=1, max_length=128)
    acquisition_method: str = Field(min_length=1, max_length=128)
    acquisition_endpoint: str = Field(min_length=1, max_length=2048)
    secret_reference_id: str = Field(min_length=1, max_length=128)
    organization_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    environment_id: str = Field(min_length=1, max_length=128)
    vendor: str = Field(min_length=1, max_length=128)
    product: str = Field(min_length=1, max_length=128)
    default_classification: DataClassification
    access_mapping_method: str = Field(min_length=1, max_length=256)
    expected_version_behavior: str = Field(min_length=1, max_length=512)
    authority_trust_rationale: str = Field(min_length=1, max_length=1024)
    retention_policy: str = Field(min_length=1, max_length=512)
    deletion_policy: str = Field(min_length=1, max_length=512)
    license_or_usage_restrictions: str = Field(min_length=1, max_length=512)
    ingestion_schedule: str = Field(min_length=1, max_length=256)
    failure_policy: str = Field(min_length=1, max_length=512)


class KnowledgeSourceTransitionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: KnowledgeSourceLifecycleState


class KnowledgeSourceRegistrationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

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

    @classmethod
    def from_domain(
        cls, registration: KnowledgeSourceRegistration
    ) -> KnowledgeSourceRegistrationData:
        return cls(
            source_id=registration.source_id,
            display_name=registration.display_name,
            source_type=registration.source_type,
            source_class=registration.source_class,
            owner=registration.owner,
            technical_contact=registration.technical_contact,
            acquisition_method=registration.acquisition_method,
            acquisition_endpoint=registration.acquisition_endpoint,
            secret_reference_id=registration.secret_reference_id,
            organization_id=registration.organization_id,
            tenant_id=registration.tenant_id,
            environment_id=registration.environment_id,
            vendor=registration.vendor,
            product=registration.product,
            default_classification=registration.default_classification,
            access_mapping_method=registration.access_mapping_method,
            expected_version_behavior=registration.expected_version_behavior,
            authority_trust_rationale=registration.authority_trust_rationale,
            retention_policy=registration.retention_policy,
            deletion_policy=registration.deletion_policy,
            license_or_usage_restrictions=registration.license_or_usage_restrictions,
            ingestion_schedule=registration.ingestion_schedule,
            failure_policy=registration.failure_policy,
            state=registration.state,
            registered_at=registration.registered_at,
            updated_at=registration.updated_at,
        )


class KnowledgeSourceRegistrationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: KnowledgeSourceRegistrationData
    meta: ResponseMeta

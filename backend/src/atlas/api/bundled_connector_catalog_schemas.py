from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.bundled_catalog import BundledConnectorDescriptor
from atlas.modules.connectors.domain.instance_creation import ConnectorInstanceRecord

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class BundledConnectorInstanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.bundled-connector-instance-input.v1", pattern=STABLE_ID
    )
    catalog_item_digest: str = Field(pattern=DIGEST)
    instance_key: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    display_name: str = Field(min_length=3, max_length=200)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_instance_is_disabled_and_grants_no_authority: bool


class BundledConnectorDescriptorData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_item_id: str
    schema_version: str
    version: int
    connector_id: str
    display_name: str
    vendor_name: str
    release_version: str
    sdk_profile: str
    capability_ids: tuple[str, ...]
    capability_classes: tuple[str, ...]
    canonical_digest: str
    trusted_bundled: bool
    development_only: bool
    catalog_evidence_only: bool
    target_authority_granted: bool
    credential_authority_granted: bool
    capability_authority_granted: bool
    network_authority_granted: bool
    runtime_authority_granted: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool

    @classmethod
    def from_domain(
        cls, descriptor: BundledConnectorDescriptor
    ) -> BundledConnectorDescriptorData:
        return cls(**{field: getattr(descriptor, field) for field in cls.model_fields})


class BundledConnectorInstanceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    version: int
    organization_id: str
    environment_id: str
    connector_id: str
    release_version: str
    instance_id: str
    instance_key: str
    display_name: str
    instance_state: str
    purpose: str
    created_at: datetime
    canonical_digest: str
    eligible_for_configuration_governance: bool
    target_configured: bool
    credentials_resolved: bool
    connector_enabled: bool
    runtime_trust_granted: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(cls, record: ConnectorInstanceRecord) -> BundledConnectorInstanceData:
        return cls(**{field: getattr(record, field) for field in cls.model_fields})


class BundledConnectorCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[BundledConnectorDescriptorData, ...]
    meta: ResponseMeta


class BundledConnectorInstanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BundledConnectorInstanceData
    meta: ResponseMeta

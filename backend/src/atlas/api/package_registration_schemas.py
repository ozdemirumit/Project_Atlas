from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.package_registration import ConnectorPackageRegistrationRecord

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorPackageRegistrationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-package-registration-input.v1", pattern=STABLE_ID
    )
    source_publication_receipt_id: str = Field(pattern=STABLE_ID)
    source_publication_receipt_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    registration_policy_id: str = Field(pattern=STABLE_ID)
    registration_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_registration_grants_no_installation_or_runtime_authority: bool


class ConnectorRegisteredCapabilityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    capability_class: str
    required_permission: str


class ConnectorRegisteredManifestData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    connector_id: str
    manifest_version: str
    release_version: str
    source_status: str
    sdk_profile: str
    target_products: tuple[str, ...]
    network_destination_count: int
    configuration_key_count: int
    secret_reference_count: int
    capabilities: tuple[ConnectorRegisteredCapabilityData, ...]
    manifest_digest: str


class ConnectorPackageRegistrationRecordData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    schema_version: str
    version: int
    source_publication_receipt_id: str
    source_publication_receipt_digest: str
    source_signing_receipt_id: str
    source_signing_receipt_digest: str
    source_approval_request_id: str
    source_approval_request_digest: str
    source_final_validation_id: str
    source_final_validation_digest: str
    source_acquisition_id: str
    source_acquisition_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    package_size_bytes: int
    publisher_id: str
    connector_id: str
    release_version: str
    provenance_digest: str
    registry_profile_id: str
    registration_policy_id: str
    registration_policy_digest: str
    registration_policy_version: str
    manifest: ConnectorRegisteredManifestData
    registered_by: str
    purpose: str
    registered_at: datetime
    canonical_digest: str
    package_published: bool
    connector_registered: bool
    eligible_for_installation_governance: bool
    promotion_blocked: bool
    reused: bool
    connector_installed: bool
    connector_enabled: bool
    instance_created: bool
    target_configured: bool
    credentials_resolved: bool
    runtime_trust_granted: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool

    @classmethod
    def from_domain(
        cls, record: ConnectorPackageRegistrationRecord
    ) -> ConnectorPackageRegistrationRecordData:
        manifest = record.manifest
        return cls(
            **{
                field: getattr(record, field)
                for field in cls.model_fields
                if field not in {"manifest"}
            },
            manifest=ConnectorRegisteredManifestData(
                schema_version=manifest.schema_version,
                connector_id=manifest.connector_id,
                manifest_version=manifest.manifest_version,
                release_version=manifest.release_version,
                source_status=manifest.source_status,
                sdk_profile=manifest.sdk_profile,
                target_products=manifest.target_products,
                network_destination_count=len(manifest.network_destinations),
                configuration_key_count=manifest.configuration_key_count,
                secret_reference_count=manifest.secret_reference_count,
                capabilities=tuple(
                    ConnectorRegisteredCapabilityData(
                        capability_id=item.capability_id,
                        capability_class=item.capability_class,
                        required_permission=item.required_permission,
                    )
                    for item in manifest.capabilities
                ),
                manifest_digest=manifest.manifest_digest,
            ),
        )


class ConnectorPackageRegistrationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorPackageRegistrationRecordData
    meta: ResponseMeta

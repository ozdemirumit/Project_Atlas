from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
DISABLED_TARGET_CONFIGURED = "disabled_target_configured"


@dataclass(frozen=True, slots=True)
class ConnectorTargetProfileSnapshot:
    profile_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    site_id: str
    target_id: str
    target_type: str
    target_product: str
    target_version: str
    endpoint_origin: str
    trust_profile_id: str
    network_route_profile_id: str
    proxy_profile_id: str
    allowed_connector_ids: tuple[str, ...]
    allowed_release_versions: tuple[str, ...]
    classification: str
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.profile_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.site_id,
            self.target_id,
            self.target_type,
            self.target_version,
            self.trust_profile_id,
            self.network_route_profile_id,
            self.proxy_profile_id,
            *self.allowed_connector_ids,
            *self.allowed_release_versions,
            self.classification,
            self.signed_by,
        ):
            validate_stable_identifier(value, "connector target profile identifier")
        parsed = urlsplit(self.endpoint_origin)
        host = (parsed.hostname or "").lower()
        try:
            ipaddress.ip_address(host)
            is_ip = True
        except ValueError:
            is_ip = False
        try:
            port = parsed.port
        except ValueError:
            port = None
        if (
            self.version != 1
            or not self.allowed_connector_ids
            or not self.allowed_release_versions
            or not 1 <= len(self.target_product.strip()) <= 200
            or parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or bool(parsed.query)
            or bool(parsed.fragment)
            or not host
            or host == "localhost"
            or host.endswith(".localhost")
            or is_ip
            or port is None
            or not 1 <= port <= 65535
            or len(self.endpoint_origin) > 500
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Connector target profile contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorTargetConfigurationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_instance_record_schema: str
    required_target_profile_schema: str
    maximum_instance_age_hours: int
    maximum_target_profile_age_hours: int
    required_assurance_level: AssuranceLevel
    required_target_profile_signer_id: str
    allowed_target_types: tuple[str, ...]
    allowed_target_products: tuple[str, ...]
    allowed_endpoint_dns_suffixes: tuple[str, ...]
    allowed_endpoint_ports: tuple[int, ...]
    required_trust_profile_id: str
    required_network_route_profile_id: str
    required_proxy_profile_id: str
    required_effective_state: str
    binding_record_schema: str
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.policy_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.policy_version,
            self.required_instance_record_schema,
            self.required_target_profile_schema,
            self.required_target_profile_signer_id,
            *self.allowed_target_types,
            self.required_trust_profile_id,
            self.required_network_route_profile_id,
            self.required_proxy_profile_id,
            self.required_effective_state,
            self.binding_record_schema,
            self.signed_by,
        ):
            validate_stable_identifier(value, "target configuration policy identifier")
        if (
            self.version != 1
            or not 1 <= self.maximum_instance_age_hours <= 87600
            or not 1 <= self.maximum_target_profile_age_hours <= 87600
            or self.required_assurance_level
            not in {AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED}
            or not self.allowed_target_types
            or not self.allowed_target_products
            or any(
                not product.strip() or len(product) > 200
                for product in self.allowed_target_products
            )
            or not self.allowed_endpoint_dns_suffixes
            or any(
                not suffix.startswith(".") or len(suffix) > 253
                for suffix in self.allowed_endpoint_dns_suffixes
            )
            or not self.allowed_endpoint_ports
            or any(not 1 <= port <= 65535 for port in self.allowed_endpoint_ports)
            or self.required_effective_state != DISABLED_TARGET_CONFIGURED
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Target configuration policy contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorTargetConfigurationBinding:
    binding_id: str
    schema_version: str
    version: int
    source_instance_record_id: str
    source_instance_record_digest: str
    source_installation_receipt_id: str
    source_installation_receipt_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    connector_id: str
    release_version: str
    manifest_digest: str
    instance_id: str
    instance_key: str
    display_name: str
    owner_id: str
    target_profile_id: str
    target_profile_digest: str
    site_id: str
    target_id: str
    target_type: str
    target_product: str
    target_version: str
    configuration_policy_id: str
    configuration_policy_digest: str
    configuration_policy_version: str
    configuration_version: int
    instance_state: str
    bound_by: str
    purpose: str
    bound_at: datetime
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    package_installed: bool = True
    instance_created: bool = True
    target_configured: bool = True
    eligible_for_credential_governance: bool = True
    promotion_blocked: bool = False
    credentials_resolved: bool = False
    connector_enabled: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.binding_id,
            self.schema_version,
            self.source_instance_record_id,
            self.source_installation_receipt_id,
            self.organization_id,
            self.environment_id,
            self.connector_id,
            self.release_version,
            self.instance_id,
            self.instance_key,
            self.owner_id,
            self.target_profile_id,
            self.site_id,
            self.target_id,
            self.target_type,
            self.target_version,
            self.configuration_policy_id,
            self.configuration_policy_version,
            self.instance_state,
            self.bound_by,
        ):
            validate_stable_identifier(value, "target configuration binding identifier")
        if (
            self.version != 1
            or self.configuration_version != 1
            or any(
                _DIGEST.fullmatch(value) is None
                for value in (
                    self.source_instance_record_digest,
                    self.source_installation_receipt_digest,
                    self.package_digest,
                    self.manifest_digest,
                    self.target_profile_digest,
                    self.configuration_policy_digest,
                    self.canonical_digest,
                    self.request_fingerprint,
                )
            )
            or not 3 <= len(self.display_name.strip()) <= 200
            or not 1 <= len(self.target_product.strip()) <= 200
            or self.instance_state != DISABLED_TARGET_CONFIGURED
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 8 <= len(self.idempotency_key) <= 128
            or self.bound_at.tzinfo is None
            or not all(
                (
                    self.package_installed,
                    self.instance_created,
                    self.target_configured,
                    self.eligible_for_credential_governance,
                )
            )
            or self.promotion_blocked
            or any(
                (
                    self.credentials_resolved,
                    self.connector_enabled,
                    self.runtime_trust_granted,
                    self.execution_authorized,
                    self.deployment_approved,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Target configuration binding violates the authority boundary")
